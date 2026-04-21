"""First-party boundary controls for streamable-http deployments."""

from __future__ import annotations

import os
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path

import anyio
from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from exposure_scenario_mcp.http_audit import HttpAuditMiddleware, timeout_response

HTTP_BEARER_TOKEN_ENV_VAR = "EXPOSURE_SCENARIO_MCP_HTTP_BEARER_TOKEN"  # noqa: S105
HTTP_ALLOWED_ORIGINS_ENV_VAR = "EXPOSURE_SCENARIO_MCP_HTTP_ALLOWED_ORIGINS"
HTTP_MAX_REQUEST_BYTES_ENV_VAR = "EXPOSURE_SCENARIO_MCP_HTTP_MAX_REQUEST_BYTES"
HTTP_AUDIT_LOG_PATH_ENV_VAR = "EXPOSURE_SCENARIO_MCP_HTTP_AUDIT_LOG_PATH"
HTTP_REQUEST_TIMEOUT_SECONDS_ENV_VAR = "EXPOSURE_SCENARIO_MCP_HTTP_REQUEST_TIMEOUT_SECONDS"
HTTP_MAX_CONCURRENCY_ENV_VAR = "EXPOSURE_SCENARIO_MCP_HTTP_MAX_CONCURRENCY"
DEFAULT_HTTP_MAX_REQUEST_BYTES = 10 * 1024 * 1024
DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS = 120.0
DEFAULT_HTTP_MAX_CONCURRENCY = 16
HTTP_BOUNDARY_CONTROL_NAMES = (
    "shared-bearer-token-auth",
    "explicit-origin-allowlist",
    "request-size-limit",
    "request-timeout",
    "concurrency-limit",
    "audit-jsonl",
)
_DEFAULT_CORS_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]
_DEFAULT_CORS_HEADERS = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Mcp-Session-Id",
    "Last-Event-ID",
]
_DEFAULT_EXPOSED_HEADERS = ["Mcp-Session-Id"]


@dataclass(frozen=True)
class HttpBoundarySecurityConfig:
    bearer_token: str | None = None
    allowed_origins: tuple[str, ...] = ()
    max_request_bytes: int | None = DEFAULT_HTTP_MAX_REQUEST_BYTES
    audit_log_path: Path | None = None
    request_timeout_seconds: float | None = DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS
    max_concurrency: int | None = DEFAULT_HTTP_MAX_CONCURRENCY

    def __post_init__(self) -> None:
        if self.max_request_bytes is not None and self.max_request_bytes < 0:
            raise ValueError("max_request_bytes must be non-negative or None")
        if self.request_timeout_seconds is not None and self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive or None")
        if self.max_concurrency is not None and self.max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive or None")

    @property
    def auth_enabled(self) -> bool:
        return bool(self.bearer_token)

    @property
    def origin_enforcement_enabled(self) -> bool:
        return bool(self.allowed_origins)

    @property
    def request_size_limit_enabled(self) -> bool:
        return self.max_request_bytes is not None

    @property
    def audit_enabled(self) -> bool:
        return self.audit_log_path is not None

    @property
    def request_timeout_enabled(self) -> bool:
        return self.request_timeout_seconds is not None

    @property
    def concurrency_limit_enabled(self) -> bool:
        return self.max_concurrency is not None


def _parse_allowed_origins(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return ()
    return tuple(origin for origin in (item.strip() for item in raw_value.split(",")) if origin)


def build_http_boundary_security_config(
    *,
    bearer_token: str | None = None,
    allowed_origins: list[str] | None = None,
    max_request_bytes: int | None = None,
    audit_log_path: str | Path | None = None,
    request_timeout_seconds: float | None = None,
    max_concurrency: int | None = None,
) -> HttpBoundarySecurityConfig:
    """Build a streamable-http security config from args with env fallbacks."""

    resolved_token = (
        bearer_token if bearer_token is not None else os.getenv(HTTP_BEARER_TOKEN_ENV_VAR)
    )
    resolved_origins = (
        tuple(origin.strip() for origin in allowed_origins if origin.strip())
        if allowed_origins is not None
        else _parse_allowed_origins(os.getenv(HTTP_ALLOWED_ORIGINS_ENV_VAR))
    )
    if max_request_bytes is None:
        env_limit = os.getenv(HTTP_MAX_REQUEST_BYTES_ENV_VAR)
        resolved_max_request_bytes: int | None = (
            int(env_limit) if env_limit is not None else DEFAULT_HTTP_MAX_REQUEST_BYTES
        )
    else:
        resolved_max_request_bytes = max_request_bytes
    if resolved_max_request_bytes == 0:
        resolved_max_request_bytes = None
    if audit_log_path is None:
        raw_audit_path = os.getenv(HTTP_AUDIT_LOG_PATH_ENV_VAR)
        resolved_audit_log_path = Path(raw_audit_path).expanduser() if raw_audit_path else None
    else:
        resolved_audit_log_path = Path(audit_log_path).expanduser()
    if request_timeout_seconds is None:
        env_timeout = os.getenv(HTTP_REQUEST_TIMEOUT_SECONDS_ENV_VAR)
        resolved_request_timeout_seconds: float | None = (
            float(env_timeout) if env_timeout is not None else DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS
        )
    else:
        resolved_request_timeout_seconds = request_timeout_seconds
    if resolved_request_timeout_seconds == 0:
        resolved_request_timeout_seconds = None
    if max_concurrency is None:
        env_concurrency = os.getenv(HTTP_MAX_CONCURRENCY_ENV_VAR)
        resolved_max_concurrency: int | None = (
            int(env_concurrency) if env_concurrency is not None else DEFAULT_HTTP_MAX_CONCURRENCY
        )
    else:
        resolved_max_concurrency = max_concurrency
    if resolved_max_concurrency == 0:
        resolved_max_concurrency = None
    return HttpBoundarySecurityConfig(
        bearer_token=resolved_token,
        allowed_origins=resolved_origins,
        max_request_bytes=resolved_max_request_bytes,
        audit_log_path=resolved_audit_log_path,
        request_timeout_seconds=resolved_request_timeout_seconds,
        max_concurrency=resolved_max_concurrency,
    )


def streamable_http_boundary_controls_available() -> tuple[str, ...]:
    """Return the published first-party streamable-http boundary controls."""

    return HTTP_BOUNDARY_CONTROL_NAMES


def describe_http_boundary_security(config: HttpBoundarySecurityConfig) -> str:
    """Summarize enabled HTTP boundary controls for operator logs."""

    controls: list[str] = []
    if config.auth_enabled:
        controls.append("bearer-token-auth")
    if config.origin_enforcement_enabled:
        controls.append(f"origin-allowlist({len(config.allowed_origins)})")
    if config.request_size_limit_enabled:
        controls.append(f"request-size-limit({config.max_request_bytes} bytes)")
    if config.request_timeout_enabled:
        controls.append(f"request-timeout({config.request_timeout_seconds:g}s)")
    if config.concurrency_limit_enabled:
        controls.append(f"concurrency-limit({config.max_concurrency})")
    if config.audit_enabled and config.audit_log_path is not None:
        controls.append(f"audit-jsonl({config.audit_log_path})")
    return ", ".join(controls) if controls else "no extra controls"


def _json_error_response(
    status_code: int,
    error: str,
    message: str,
    **headers: str,
) -> JSONResponse:
    return JSONResponse(
        {"error": error, "message": message},
        status_code=status_code,
        headers=headers or None,
    )


class SharedBearerTokenAuthMiddleware:
    """Require a shared bearer token for HTTP requests."""

    def __init__(self, app: ASGIApp, bearer_token: str) -> None:
        self.app = app
        self._bearer_token = bearer_token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        authorization = headers.get("authorization")
        if authorization is None:
            response = _json_error_response(
                401,
                "missing_bearer_token",
                "Missing bearer token for streamable-http access.",
                **{"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        scheme, _, token = authorization.partition(" ")
        if (
            scheme.lower() != "bearer"
            or not token
            or not secrets.compare_digest(token, self._bearer_token)
        ):
            response = _json_error_response(
                401,
                "invalid_bearer_token",
                "Invalid bearer token for streamable-http access.",
                **{"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class AllowedOriginMiddleware:
    """Reject requests that present an origin outside the configured allow-list."""

    def __init__(self, app: ASGIApp, allowed_origins: tuple[str, ...]) -> None:
        self.app = app
        self._allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        origin = Headers(scope=scope).get("origin")
        if origin is not None and origin not in self._allowed_origins:
            response = _json_error_response(
                403,
                "origin_not_allowed",
                f"Origin `{origin}` is not allowed for this streamable-http deployment.",
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class _RequestBodyTooLarge(Exception):
    """Raised when the request body exceeds the configured byte limit."""


class RequestSizeLimitMiddleware:
    """Reject HTTP requests that exceed the configured request-size limit."""

    def __init__(self, app: ASGIApp, max_request_bytes: int) -> None:
        self.app = app
        self._max_request_bytes = max_request_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = None
            if declared_length is not None and declared_length > self._max_request_bytes:
                response = _json_error_response(
                    413,
                    "request_too_large",
                    (
                        "Request body exceeded the configured streamable-http limit of "
                        f"{self._max_request_bytes} bytes."
                    ),
                )
                await response(scope, receive, send)
                return

        response_started = False

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        total_bytes = 0

        async def guarded_receive() -> Message:
            nonlocal total_bytes
            message = await receive()
            if message["type"] == "http.request":
                total_bytes += len(message.get("body", b""))
                if total_bytes > self._max_request_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, guarded_receive, guarded_send)
        except _RequestBodyTooLarge:
            if not response_started:
                response = _json_error_response(
                    413,
                    "request_too_large",
                    (
                        "Request body exceeded the configured streamable-http limit of "
                        f"{self._max_request_bytes} bytes."
                    ),
                )
                await response(scope, receive, send)


class RequestTimeoutMiddleware:
    """Abort requests that exceed the configured server-side timeout."""

    def __init__(self, app: ASGIApp, timeout_seconds: float) -> None:
        self.app = app
        self._timeout_seconds = timeout_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            with anyio.fail_after(self._timeout_seconds):
                await self.app(scope, receive, guarded_send)
        except TimeoutError:
            if not response_started:
                response = timeout_response(self._timeout_seconds)
                await response(scope, receive, send)


class ConcurrencyLimitMiddleware:
    """Reject requests when the configured in-process concurrency ceiling is exhausted."""

    def __init__(self, app: ASGIApp, max_concurrency: int) -> None:
        self.app = app
        self._semaphore = threading.BoundedSemaphore(max_concurrency)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        acquired = self._semaphore.acquire(blocking=False)
        if not acquired:
            response = _json_error_response(
                503,
                "server_busy",
                "The streamable-http concurrency limit is currently exhausted.",
            )
            await response(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        finally:
            self._semaphore.release()


def apply_http_boundary_security(
    app: ASGIApp,
    config: HttpBoundarySecurityConfig,
) -> ASGIApp:
    """Wrap a streamable-http ASGI app with the configured first-party controls."""

    secured_app: ASGIApp = app
    if config.request_size_limit_enabled and config.max_request_bytes is not None:
        secured_app = RequestSizeLimitMiddleware(secured_app, config.max_request_bytes)
    if config.auth_enabled and config.bearer_token is not None:
        secured_app = SharedBearerTokenAuthMiddleware(secured_app, config.bearer_token)
    if config.origin_enforcement_enabled:
        secured_app = CORSMiddleware(
            secured_app,
            allow_origins=list(config.allowed_origins),
            allow_methods=_DEFAULT_CORS_METHODS,
            allow_headers=_DEFAULT_CORS_HEADERS,
            expose_headers=_DEFAULT_EXPOSED_HEADERS,
        )
        secured_app = AllowedOriginMiddleware(secured_app, config.allowed_origins)
    if config.request_timeout_enabled and config.request_timeout_seconds is not None:
        secured_app = RequestTimeoutMiddleware(secured_app, config.request_timeout_seconds)
    if config.concurrency_limit_enabled and config.max_concurrency is not None:
        secured_app = ConcurrencyLimitMiddleware(secured_app, config.max_concurrency)
    if config.audit_enabled and config.audit_log_path is not None:
        secured_app = HttpAuditMiddleware(secured_app, config.audit_log_path)
    return secured_app

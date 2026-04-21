"""HTTP audit helpers and middleware for streamable-http deployments."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

AUDIT_REQUEST_ID_HEADER = "X-Exposure-Audit-Request-Id"
_SENSITIVE_KEY_FRAGMENTS = frozenset(
    {
        "apikey",
        "api_key",
        "authorization",
        "bearer",
        "password",
        "secret",
        "token",
    }
)
_QUALITY_FLAG_KEYS = frozenset({"qualityflags", "quality_flags"})
_LIMITATION_KEYS = frozenset({"limitations", "limitationnotes", "limitation_notes"})
_MANUAL_REVIEW_KEYS = frozenset({"manualreviewrequired", "manual_review_required"})
_FILE_LOCK = threading.Lock()


def _normalized_key(value: str) -> str:
    return "".join(
        character for character in value.lower() if character.isalnum() or character == "_"
    )


def _is_sensitive_key(key: str) -> bool:
    normalized = _normalized_key(key)
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("<redacted>" if _is_sensitive_key(key) else _redact_json(item))
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    return value


def _json_digest(payload: Any) -> str:
    canonical = json.dumps(_redact_json(payload), separators=(",", ":"), sort_keys=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _bytes_digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _decode_json_payload(payload: bytes) -> Any | None:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _stable_payload_digest(payload: bytes) -> str | None:
    if not payload:
        return None
    parsed = _decode_json_payload(payload)
    if parsed is not None:
        return _json_digest(parsed)
    return _bytes_digest(payload)


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_operation_details(payload: Any) -> tuple[str | None, str | None, str | None]:
    if not isinstance(payload, dict):
        return None, None, None

    rpc_method = _first_string(payload.get("method"))
    params = payload.get("params")
    if not isinstance(params, dict):
        return rpc_method, None, None

    if rpc_method == "tools/call":
        name = _first_string(params.get("name"), params.get("toolName"))
        return rpc_method, "tool", name
    if rpc_method == "resources/read":
        name = _first_string(params.get("uri"), params.get("resourceUri"))
        return rpc_method, "resource", name
    if rpc_method == "prompts/get":
        name = _first_string(params.get("name"), params.get("promptName"))
        return rpc_method, "prompt", name
    return rpc_method, "rpc", rpc_method


def _collect_codes(payload: Any, target_keys: frozenset[str]) -> set[str]:
    codes: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                normalized_key = _normalized_key(key)
                if normalized_key in target_keys and isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            code = _first_string(item.get("code"), item.get("findingId"))
                            if code is not None:
                                codes.add(code)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return codes


def _collect_manual_review_required(payload: Any) -> bool | None:
    found_value: bool | None = None

    def walk(node: Any) -> None:
        nonlocal found_value
        if found_value is not None:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if _normalized_key(key) in _MANUAL_REVIEW_KEYS and isinstance(value, bool):
                    found_value = value
                    return
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found_value


def _extract_result_details(
    payload: Any,
) -> tuple[str | None, list[str], list[str], bool | None, str | None]:
    if not isinstance(payload, dict):
        return None, [], [], None, None

    rpc_error = payload.get("error")
    if isinstance(rpc_error, dict):
        return (
            "failed",
            [],
            [],
            None,
            _first_string(rpc_error.get("message")) or "JSON-RPC request failed.",
        )

    result = payload.get("result")
    if not isinstance(result, dict):
        return None, [], [], None, None

    meta = result.get("_meta")
    structured = result.get("structuredContent")
    result_status = None
    exception_summary = None
    if isinstance(meta, dict):
        result_status = _first_string(meta.get("resultStatus"))
        error_code = _first_string(meta.get("errorCode"))
        if result_status == "failed" and error_code is not None:
            exception_summary = f"Tool reported error code {error_code}."

    warning_codes = sorted(_collect_codes(structured, _QUALITY_FLAG_KEYS))
    limitation_codes = sorted(_collect_codes(structured, _LIMITATION_KEYS))
    manual_review_required = _collect_manual_review_required(structured)
    return result_status, warning_codes, limitation_codes, manual_review_required, exception_summary


def build_http_audit_event(
    *,
    scope: Scope,
    request_id: str,
    started_at: str,
    duration_ms: float,
    request_body: bytes,
    response_body: bytes,
    response_status_code: int | None,
    exception_summary: str | None,
) -> dict[str, Any]:
    request_payload = _decode_json_payload(request_body)
    response_payload = _decode_json_payload(response_body)
    rpc_method, operation_kind, operation_name = _extract_operation_details(request_payload)
    (
        result_status,
        warning_codes,
        limitation_codes,
        manual_review_required,
        response_exception_summary,
    ) = _extract_result_details(response_payload)
    resolved_exception_summary = exception_summary or response_exception_summary
    return {
        "schemaVersion": "httpAuditEvent.v1",
        "recordedAt": datetime.now(UTC).isoformat(),
        "startedAt": started_at,
        "requestId": request_id,
        "transport": "streamable-http",
        "httpMethod": scope.get("method"),
        "path": scope.get("path"),
        "rpcMethod": rpc_method,
        "operationKind": operation_kind,
        "operationName": operation_name,
        "normalizedInputDigestSha256": _stable_payload_digest(request_body),
        "outputDigestSha256": _stable_payload_digest(response_body),
        "durationMs": round(duration_ms, 3),
        "responseStatusCode": response_status_code,
        "resultStatus": result_status,
        "qualityFlagCodes": warning_codes,
        "limitationCodes": limitation_codes,
        "manualReviewRequired": manual_review_required,
        "exceptionSummary": resolved_exception_summary,
    }


def append_http_audit_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(event, sort_keys=True)
    with _FILE_LOCK, path.open("a", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.write("\n")


def load_http_audit_events(path: str | Path) -> list[dict[str, Any]]:
    audit_path = Path(path)
    if not audit_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(cast(dict[str, Any], json.loads(line)))
    return events


def summarize_http_audit_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_operation: dict[str, int] = {}
    by_status: dict[str, int] = {}
    manual_review_count = 0
    for event in events:
        operation_name = event.get("operationName") or "<unknown>"
        by_operation[operation_name] = by_operation.get(operation_name, 0) + 1
        status = event.get("resultStatus") or "<none>"
        by_status[status] = by_status.get(status, 0) + 1
        if event.get("manualReviewRequired") is True:
            manual_review_count += 1
    return {
        "totalEvents": len(events),
        "operationCounts": dict(sorted(by_operation.items())),
        "resultStatusCounts": dict(sorted(by_status.items())),
        "manualReviewEventCount": manual_review_count,
    }


class HttpAuditMiddleware:
    """Append one JSONL audit event per HTTP request without persisting raw bodies."""

    def __init__(self, app: ASGIApp, audit_log_path: Path) -> None:
        self.app = app
        self._audit_log_path = audit_log_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex
        started_at = datetime.now(UTC).isoformat()
        started = perf_counter()
        request_chunks: list[bytes] = []
        response_chunks: list[bytes] = []
        response_status_code: int | None = None
        exception_summary: str | None = None

        async def audited_receive() -> Message:
            message = await receive()
            if message["type"] == "http.request":
                request_chunks.append(message.get("body", b""))
            return message

        async def audited_send(message: Message) -> None:
            nonlocal response_status_code
            if message["type"] == "http.response.start":
                response_status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-exposure-audit-request-id", request_id.encode("utf-8")))
                message = {**message, "headers": headers}
            elif message["type"] == "http.response.body":
                response_chunks.append(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, audited_receive, audited_send)
        except Exception as error:
            exception_summary = f"{type(error).__name__}: {error}"
            raise
        finally:
            event = build_http_audit_event(
                scope=scope,
                request_id=request_id,
                started_at=started_at,
                duration_ms=(perf_counter() - started) * 1000.0,
                request_body=b"".join(request_chunks),
                response_body=b"".join(response_chunks),
                response_status_code=response_status_code,
                exception_summary=exception_summary,
            )
            append_http_audit_event(self._audit_log_path, event)


def timeout_response(timeout_seconds: float) -> JSONResponse:
    return JSONResponse(
        {
            "error": "request_timed_out",
            "message": (
                "Request exceeded the configured streamable-http timeout of "
                f"{timeout_seconds:g} seconds."
            ),
        },
        status_code=504,
    )

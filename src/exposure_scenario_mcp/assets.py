"""Helpers for loading static assets from either an installed wheel or a source checkout."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from pathlib import Path

PACKAGE_NAME = "exposure_scenario_mcp"


@lru_cache(maxsize=1)
def repo_root() -> Path | None:
    """Return the repository root when running from a source checkout."""

    candidates = [Path(__file__).resolve(), Path.cwd().resolve()]
    seen: set[Path] = set()

    for candidate in candidates:
        node = candidate if candidate.is_dir() else candidate.parent
        for current in (node, *node.parents):
            if current in seen:
                continue
            seen.add(current)
            if (current / "pyproject.toml").exists() and (current / "src" / PACKAGE_NAME).exists():
                return current
    return None


def repo_path(relative_path: str) -> Path | None:
    root = repo_root()
    if root is None:
        return None
    return root / relative_path


def read_text_asset(
    package_relative_path: str, repo_relative_path: str
) -> tuple[str, str, Path | None]:
    """Read text from package data when installed, or fall back to the source checkout."""

    try:
        resource = files(PACKAGE_NAME).joinpath(*package_relative_path.split("/"))
        if resource.is_file():
            return (
                resource.read_text(encoding="utf-8"),
                f"package://{PACKAGE_NAME}/{package_relative_path}",
                None,
            )
    except FileNotFoundError:
        pass

    fallback_path = repo_path(repo_relative_path)
    if fallback_path is None or not fallback_path.exists():
        raise FileNotFoundError(
            f"Unable to resolve asset '{package_relative_path}' or '{repo_relative_path}'."
        )
    return fallback_path.read_text(encoding="utf-8"), repo_relative_path, fallback_path

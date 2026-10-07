"""Installed metadata must not be taken from an unrelated working-directory checkout."""

from __future__ import annotations

from pathlib import Path

from exposure_scenario_mcp import assets
from exposure_scenario_mcp.contracts import _project_metadata
from exposure_scenario_mcp.package_metadata import CURRENT_VERSION, PACKAGE_NAME


def test_installed_package_ignores_an_older_checkout_in_working_directory(
    tmp_path: Path, monkeypatch
) -> None:
    old = tmp_path / "old-checkout"
    (old / "src" / assets.PACKAGE_NAME).mkdir(parents=True)
    (old / "pyproject.toml").write_text(
        '[project]\nname="exposure-scenario-mcp"\nversion="0.2.0"\n', encoding="utf-8"
    )
    module = tmp_path / "installed" / "site-packages" / assets.PACKAGE_NAME / "assets.py"
    module.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    monkeypatch.setattr(assets, "__file__", str(module))
    monkeypatch.chdir(old)
    assets.repo_root.cache_clear()
    try:
        assert assets.repo_root() is None
        assert _project_metadata() == (PACKAGE_NAME, CURRENT_VERSION)
    finally:
        assets.repo_root.cache_clear()


def test_actual_source_checkout_is_resolved_from_module_path() -> None:
    assets.repo_root.cache_clear()
    root = assets.repo_root()
    assert root is not None
    assert Path(assets.__file__).resolve().is_relative_to(root / "src" / assets.PACKAGE_NAME)

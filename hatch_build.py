"""Keep the committed wheel digest independent of platform zlib output."""

from __future__ import annotations

import tempfile
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo


def canonicalize_wheel(path: Path) -> None:
    """Store unchanged payloads in a deterministic, valid pure-Python wheel."""
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".whl", delete=False) as handle:
        temporary_path = Path(handle.name)
    try:
        with (
            ZipFile(path) as source,
            ZipFile(temporary_path, "w", compression=ZIP_STORED) as target,
        ):
            entries = source.infolist()
            if len({entry.filename for entry in entries}) != len(entries):
                raise ValueError("Wheel contains duplicate archive member names")
            # Put distribution metadata last, as recommended by the wheel format.
            for entry in sorted(
                entries,
                key=lambda item: (".dist-info/" in item.filename, item.filename),
            ):
                canonical = ZipInfo(entry.filename, date_time=(1980, 1, 1, 0, 0, 0))
                canonical.create_system = 3
                canonical.external_attr = 0o100644 << 16
                canonical.compress_type = ZIP_STORED
                target.writestr(canonical, source.read(entry))
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def get_build_hook():
    # Hatch's supported factory keeps the normalization helper testable without
    # adding build-only dependencies to the application's development graph.
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface

    class CanonicalWheelHook(BuildHookInterface):
        def finalize(self, version, build_data, artifact_path):
            canonicalize_wheel(Path(artifact_path))

    return CanonicalWheelHook

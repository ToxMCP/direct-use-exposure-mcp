from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile, ZipInfo

import pytest


def _canonicalize(path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "hatch_build", Path(__file__).resolve().parents[1] / "hatch_build.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.canonicalize_wheel(path)


def test_wheel_normalization_preserves_record_and_payload_across_archive_variance(
    tmp_path: Path,
) -> None:
    payloads = {
        "example/__init__.py": b'__version__ = "1.0"\n',
        "example-1.0.dist-info/WHEEL": b"Wheel-Version: 1.0\nTag: py3-none-any\n",
    }
    record_path = "example-1.0.dist-info/RECORD"
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    for name, payload in payloads.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=")
        writer.writerow((name, f"sha256={digest.decode()}", len(payload)))
    writer.writerow((record_path, "", ""))
    payloads[record_path] = output.getvalue().encode()

    wheels = [tmp_path / "first.whl", tmp_path / "second.whl"]
    for index, path in enumerate(wheels):
        with ZipFile(path, "w") as archive:
            archive.comment = f"different archive {index}".encode()
            for name in list(payloads)[:: 1 if index == 0 else -1]:
                entry = ZipInfo(name, date_time=(2020 + index, 2, 3, 4, 5, 6))
                entry.create_system = index
                entry.external_attr = (0o100600 + index) << 16
                entry.comment = f"different member {index}".encode()
                archive.writestr(
                    entry, payloads[name], compress_type=ZIP_STORED if index == 0 else ZIP_DEFLATED
                )
    assert wheels[0].read_bytes() != wheels[1].read_bytes()

    for path in wheels:
        _canonicalize(path)
    assert wheels[0].read_bytes() == wheels[1].read_bytes()
    with ZipFile(wheels[0]) as archive:
        assert {name: archive.read(name) for name in archive.namelist()} == payloads
        assert all(entry.compress_type == ZIP_STORED for entry in archive.infolist())
        for name, digest, size in csv.reader(io.StringIO(archive.read(record_path).decode())):
            if name == record_path:
                assert digest == size == ""
                continue
            payload = archive.read(name)
            actual = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=")
            assert digest == f"sha256={actual.decode()}"
            assert int(size) == len(payload)
    normalized = wheels[0].read_bytes()
    _canonicalize(wheels[0])
    assert wheels[0].read_bytes() == normalized


def test_wheel_normalization_retains_original_when_archive_is_invalid(tmp_path: Path) -> None:
    path = tmp_path / "invalid.whl"
    path.write_bytes(b"invalid wheel")
    original = path.read_bytes()
    with pytest.raises(BadZipFile, match="not a zip file"):
        _canonicalize(path)
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]

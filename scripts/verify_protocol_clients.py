"""Exercise an installed wheel with real SDK1 and SDK2 clients over both transports."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-python", required=True)
    parser.add_argument("--legacy-python", required=True)
    parser.add_argument("--modern-python", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("VIRTUAL_ENV", None)
    reports = []
    launcher = ROOT / "scripts/compatibility_server.py"

    def probe(python, modern, transport, url=None):
        report = output / f"{'modern' if modern else 'legacy'}-{transport}.json"
        command = [
            python,
            str(ROOT / "scripts/protocol_probe.py"),
            "--server-python",
            args.server_python,
            "--deterministic-launcher",
            str(launcher),
            "--fixtures",
            str(ROOT / "tests/compatibility/requests.json"),
            "--output",
            str(report),
        ]
        if modern:
            command.append("--modern")
        if url:
            command.extend(["--url", url])
        # All commands are argument arrays using explicitly supplied local interpreters.
        subprocess.run(command, cwd=output, env=env, check=True, timeout=90)  # noqa: S603
        reports.append(report)

    for python, modern in [(args.legacy_python, False), (args.modern_python, True)]:
        probe(python, modern, "stdio")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}/mcp"
        with (output / f"{'modern' if modern else 'legacy'}-http-server.log").open("w") as log:
            server = subprocess.Popen(  # noqa: S603
                [
                    args.server_python,
                    str(launcher),
                    "--transport",
                    "streamable-http",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=output,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 20
                while True:
                    if server.poll() is not None:
                        raise RuntimeError("HTTP server stopped during startup")
                    try:
                        with urllib.request.urlopen(url, timeout=1):  # noqa: S310
                            break
                    except urllib.error.HTTPError as error:
                        if error.code < 500:
                            break
                    except urllib.error.URLError:
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError("HTTP server did not become ready")
                    time.sleep(0.05)
                probe(python, modern, "http", url)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)

    version = json.loads((output / "modern-stdio.json").read_text())["results"]["dermal"][
        "structuredContent"
    ]["provenance"]["plugin_version"]
    subprocess.run(  # noqa: S603
        [
            args.modern_python,
            str(ROOT / "scripts/check_protocol_compatibility.py"),
            *[str(path) for path in reports],
            "--baseline",
            str(ROOT / "tests/compatibility/v0.2.1-catalog-sha256.json"),
            "--application-version",
            version,
        ],
        cwd=output,
        env=env,
        check=True,
        timeout=30,
    )
    print(
        json.dumps({"installedWheelClientMatrixPassed": True, "reports": [str(p) for p in reports]})
    )


if __name__ == "__main__":
    main()

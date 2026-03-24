from __future__ import annotations

import subprocess
import sys


def test_top_level_import_does_not_eager_import_server() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "sys.path.insert(0, 'src'); "
                "import exposure_scenario_mcp; "
                "print(exposure_scenario_mcp.__version__); "
                "print('exposure_scenario_mcp.server' in sys.modules)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip().splitlines()[-1] == "False"

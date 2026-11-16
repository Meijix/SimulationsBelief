"""Build the GUI as a single executable with PyInstaller.

    .venv/bin/pip install -e ".[build]"
    .venv/bin/python packaging/build_gui.py [--graphviz DIR] [--onedir]

Writes ``dist/SimulationsBelief`` (``.exe`` on Windows). ``--graphviz DIR``
bundles the Graphviz ``bin`` folder (``dot`` and its plugins) so the
executable needs nothing installed; without it the executable uses the ``dot``
found on the PATH. ``.github/workflows/build-gui.yml`` runs this on Windows and
macOS for every release.

The executable runs ``gui/app.py`` frozen: it writes figures, saved workspaces
and settings to ``~/SimulationsBelief`` and puts the bundled Graphviz on the
PATH (see the frozen block at the top of ``gui/app.py``).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import nicegui

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graphviz", type=Path, help="Graphviz bin folder to bundle (contains dot).")
    parser.add_argument("--onedir", action="store_true", help="a folder instead of one file (faster start).")
    args = parser.parse_args()

    datas = [f"{Path(nicegui.__file__).parent}{os.pathsep}nicegui"]
    if args.graphviz:
        dot = args.graphviz / ("dot.exe" if sys.platform == "win32" else "dot")
        if not dot.exists():
            sys.exit(f"{dot} not found; --graphviz must point at Graphviz's bin folder.")
        datas.append(f"{args.graphviz}{os.pathsep}graphviz")

    command = [
        sys.executable, "-m", "PyInstaller",
        "--name", "SimulationsBelief",
        "--onedir" if args.onedir else "--onefile",
        "--noconfirm", "--clean",
        "--paths", str(ROOT), "--paths", str(ROOT / "gui"),
        "--collect-data", "plotly",
    ]
    for data in datas:
        command += ["--add-data", data]
    command.append(str(ROOT / "gui" / "app.py"))
    print(" ".join(command))
    subprocess.run(command, check=True, cwd=ROOT)


if __name__ == "__main__":
    main()

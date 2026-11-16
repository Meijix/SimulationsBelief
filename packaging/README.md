# Packaging the GUI

`build_gui.py` turns `gui/app.py` into one executable with PyInstaller.

```bash
.venv/bin/pip install -e ".[build]"
.venv/bin/python packaging/build_gui.py                      # uses the dot on the PATH
.venv/bin/python packaging/build_gui.py --graphviz PATH/bin  # bundles Graphviz
```

The result is `dist/SimulationsBelief` (`SimulationsBelief.exe` on Windows).
Double-clicking it starts the server on a free port and opens the browser;
figures, saved workspaces and the remembered theme go to `~/SimulationsBelief`.

## Releases

`.github/workflows/build-gui.yml` builds the executable for Windows (with
Graphviz 12.2.1 inside, downloaded from the official Graphviz releases) and for
macOS (without Graphviz: `brew install graphviz` once) whenever a tag `v*` is
pushed, and attaches both to the GitHub release. To publish a version:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow can also be started by hand from the Actions tab (*Run workflow*),
which leaves the executables as downloadable artifacts without creating a
release.

## What the frozen executable does differently

The block at the top of `gui/app.py` runs only when `sys.frozen` is set:

- `SIMULATIONSBELIEF_DATA` points at `~/SimulationsBelief`, so `gui/adapters`
  writes `outputs/` and `saved_models/` there instead of into the (read-only,
  temporary) bundle;
- `NICEGUI_STORAGE_PATH` keeps NiceGUI's storage (the theme) in the same folder;
- the bundled `graphviz/` folder, if present, is put first on the `PATH`.

Everything else is the same code the `simulationsbelief-gui` command runs.

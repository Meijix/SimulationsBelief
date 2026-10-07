# -*- coding: utf-8 -*-
"""Regenerates ALL the example figures in ``outputs/`` in one go.

    .venv/bin/python regenerate_outputs.py

WHY IT EXISTS. The repository's example scripts were born one by one and each
saves its figures its own way: some call ``show(model, name)`` (a named file
in ``outputs/``), others only ``preview(model)`` (a temporary file that opens
in the viewer and is lost). When the renderer changes (palette, legend
placement, facet names...) every image has to be redone, and doing it by hand
is slow and some get forgotten. This script runs all the examples with two
patches on ``visualization`` and ``hasse``:

    * ``preview`` stops opening a viewer and writing to a temp file: it saves
      the figure in ``outputs/<script>_<title>.png`` as if it were ``show``;
    * ``_open_file`` does nothing, so ``--open`` never opens windows.

It also guarantees the TRIO of figures per model (relational, geometric
simplicial complex and Hasse diagram): every model a script draws is recorded
and, when the script finishes, the figures it lacks are generated next to its
own (``<name>_simplicial.png``, ``<name>_hasse.png``). A relational model is
translated with ``to_simplicial`` (making it proper first if needed); if the
translation is not possible a warning is printed and the run goes on.

The scripts are executed with ``runpy`` as ``__main__`` and without arguments,
one after another, from the repository root. A failing script does not stop
the others: the failure is printed at the end.
"""
from __future__ import annotations

import os
import re
import runpy
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import hasse  # noqa: E402
import visualization as vis  # noqa: E402
from visualization import OUTPUT_DIR  # noqa: E402

# The example scripts, in the order they run, as paths relative to the repo
# root: the demos live in examples/, the NASA octahedron with the poster code.
# "examples8.py" only imports modules and "hasse.py"/"visualization.py" have
# their own demos, so they are not listed.
SCRIPTS = [
    "examples/examples.py",
    "examples/examples2.py",
    "examples/examples3.py",
    "examples/examples3_explained.py",
    "examples/examples4.py",
    "examples/example5.py",
    "examples/examples7.py",
    "examples/thesis_example.py",
    "poster/poster-code/ejemplo_nasa.py",
    "examples/example_val.py",
    "examples/Natural Disaster Example.py",
    "examples/Example For Poster 1.py",
    "examples/Example for Poster 2.py",
    "examples/Example for Poster 3.py",
]


def slug(text: str) -> str:
    """Safe file name derived from a title or a script path.

    Only the file name of a script path is used, so moving a script into a
    folder does not rename the figures it produces (``thesis_example_...``).
    """
    text = Path(text).name
    text = re.sub(r"\.py$", "", text)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return text or "figura"


def is_simplicial(model) -> bool:
    return hasattr(model, "facets") and hasattr(model, "agents")


# --- record of what the current script has drawn ----------------------------
# (model, name, output_dir): used to fill in whichever figures are missing.
drawn: list = []
written: set = set()
current_script = ""

_orig_show, _orig_hasse_show = vis.show, hasse.show


def rec_show(model, name="model", title=None, **kw):
    """``visualization.show`` that also records what was drawn.

    The 3D view (``dim=3``) is not recorded: it is the same complex as the 2D
    one, and recording it would duplicate the Hasse under another name.
    """
    path = _orig_show(model, name, title, **kw)
    if kw.get("dim", 2) != 3:
        drawn.append((model, name, kw.get("output_dir", OUTPUT_DIR)))
    written.add(Path(path).stem)
    return path


def rec_hasse_show(complex_like, name="hasse", title=None, **kw):
    """``hasse.show`` that also records the name written."""
    path = _orig_hasse_show(complex_like, name, title, **kw)
    written.add(Path(path).stem)
    return path


def fake_preview(model, title=None, *, dim=2):
    """``preview`` that saves to outputs/ instead of opening a temp file."""
    name = f"{slug(current_script)}_{slug(title or vis._kind(model))}"
    return rec_show(model, name, title, dim=dim, output_dir=OUTPUT_DIR)


def fake_hasse_preview(complex_like, title=None, **kw):
    name = f"{slug(current_script)}_{slug(title or 'hasse')}"
    kw.pop("open", None)
    kw.pop("output_dir", None)
    path = rec_hasse_show(complex_like, name + "_hasse", title,
                          output_dir=OUTPUT_DIR, **kw)
    if is_simplicial(complex_like):
        # The Hasse of a simplicial model brings its geometric drawing along.
        drawn.append((complex_like, name, OUTPUT_DIR))
    return path


vis.show, vis.preview = rec_show, fake_preview
hasse.show, hasse.preview = rec_hasse_show, fake_hasse_preview
vis._open_file = hasse._open_file = lambda path: None


def to_complex(model):
    """Simplicial complex of a relational model, making it proper first.

    ``KnowledgeBeliefFrame`` has ``is_proper``/``to_proper`` as methods; a
    bare ``RelationalFrame`` uses the functions from ``properness``. A belief
    relation on its own (KD45, not S5) has no translation: ``properness`` says
    so with a ``ValueError`` and the model is skipped.
    """
    from properness import is_proper, to_proper
    from simplicial import to_simplicial

    if hasattr(model, "is_proper"):
        proper = model if model.is_proper() else model.to_proper()
    else:
        proper = model if is_proper(model) else to_proper(model)
    return to_simplicial(proper)


def complete_trio(script: str) -> None:
    """Generates, for each model drawn, whichever figures of the trio are missing."""
    seen_models: set = set()
    for model, name, out in drawn:
        if id(model) in seen_models:
            continue  # the same model drawn twice (e.g. 2D and 3D)
        seen_models.add(id(model))
        if is_simplicial(model):
            # "x_simplicial" -> base "x", so the Hasse is named "x_hasse" and
            # not "x_simplicial_hasse" (and matches the one the script may
            # have generated on its own).
            sm = model
            base = name[:-len("_simplicial")] if name.endswith("_simplicial") else name
        else:
            base = name
            try:
                sm = to_complex(model)
            except Exception as exc:  # noqa: BLE001 -- reported, then we go on
                print(f"    [{script}] {name}: sin complejo ({type(exc).__name__}: "
                      f"{str(exc).splitlines()[0][:90]})")
                continue
            geo = f"{base}_simplicial"
            if geo not in written:
                _orig_show(sm, geo, f"{name} · complejo simplicial", output_dir=out)
                written.add(geo)
                print(f"    + {geo}.png")
        has = f"{base}_hasse"
        if has not in written:
            _orig_hasse_show(sm, has, f"{name} · retículo de caras",
                             output_dir=out, include_empty=False)
            written.add(has)
            print(f"    + {has}.png")


def main() -> int:
    failures = []
    for script in SCRIPTS:
        global current_script
        current_script = script
        drawn.clear()
        print(f"\n=== {script} ===")
        sys.argv = [script]
        try:
            runpy.run_path(str(ROOT / script), run_name="__main__")
            complete_trio(script)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                failures.append((script, f"exit {exc.code}"))
        except Exception:  # noqa: BLE001 -- a broken example does not stop the rest
            failures.append((script, traceback.format_exc().splitlines()[-1]))
            print(traceback.format_exc())
    print(f"\n{len(written)} figuras en {OUTPUT_DIR}/")
    for script, why in failures:
        print(f"FALLÓ {script}: {why}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

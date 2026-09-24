# -*- coding: utf-8 -*-
"""Regenera TODAS las figuras de los ejemplos en ``outputs/`` de una sola vez.

    .venv/bin/python regenerate_outputs.py

POR QUÉ EXISTE. Los scripts de ejemplo del repositorio nacieron uno a uno y
cada cual guarda sus figuras a su manera: unos llaman a ``show(model, name)``
(archivo con nombre en ``outputs/``), otros sólo a ``preview(model)`` (archivo
temporal que se abre en el visor y se pierde). Cuando cambia el renderizador
(paleta, acomodo de leyendas, nombres de facetas...) hay que rehacer todas las
imágenes, y hacerlo a mano es lento y se olvida alguna. Este script corre
todos los ejemplos con dos parches sobre ``visualization`` y ``hasse``:

    * ``preview`` deja de abrir un visor y de escribir en un temporal: guarda
      la figura en ``outputs/<script>_<título>.png`` como si fuera ``show``;
    * ``_open_file`` no hace nada, así que ``--open`` nunca abre ventanas.

Además garantiza el TRÍO de figuras por modelo (relacional, complejo
simplicial geométrico y diagrama de Hasse): cada modelo que un script dibuja
queda registrado y, al terminar el script, se generan las figuras que le
faltan junto a la suya (``<name>_simplicial.png``, ``<name>_hasse.png``). Un
modelo relacional se traduce con ``to_simplicial`` (haciéndolo propio antes
si hace falta); si la traducción no es posible se avisa y se sigue.

Los scripts se ejecutan con ``runpy`` como ``__main__`` y sin argumentos, uno
tras otro, desde la raíz del repositorio. Un script que falle no detiene a
los demás: el fallo se imprime al final.
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

# Los scripts de ejemplo, en el orden en que se corren. "examples8.py" sólo
# importa módulos y "hasse.py"/"visualization.py" tienen sus propias demos.
SCRIPTS = [
    "examples.py",
    "examples2.py",
    "examples3.py",
    "examples3_explained.py",
    "examples4.py",
    "example5.py",
    "examples7.py",
    "thesis_example.py",
    "ejemplo_nasa.py",
    "example_val.py",
    "Natural Disaster Example.py",
    "Example For Poster 1.py",
    "Example for Poster 2.py",
    "Example for Poster 3.py",
]


def slug(text: str) -> str:
    """Nombre de archivo seguro a partir de un título o nombre de script."""
    text = re.sub(r"\.py$", "", text)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return text or "figura"


def is_simplicial(model) -> bool:
    return hasattr(model, "facets") and hasattr(model, "agents")


# --- registro de lo dibujado por el script en curso -------------------------
# (model, name, output_dir): con esto se completan las figuras que falten.
drawn: list = []
written: set = set()
current_script = ""

_orig_show, _orig_hasse_show = vis.show, hasse.show


def rec_show(model, name="model", title=None, **kw):
    """``visualization.show`` que además registra qué se dibujó.

    La vista 3D (``dim=3``) no se registra: es el mismo complejo que la 2D y
    registrarlo duplicaría el Hasse con otro nombre.
    """
    path = _orig_show(model, name, title, **kw)
    if kw.get("dim", 2) != 3:
        drawn.append((model, name, kw.get("output_dir", OUTPUT_DIR)))
    written.add(Path(path).stem)
    return path


def rec_hasse_show(complex_like, name="hasse", title=None, **kw):
    """``hasse.show`` que además registra el nombre escrito."""
    path = _orig_hasse_show(complex_like, name, title, **kw)
    written.add(Path(path).stem)
    return path


def fake_preview(model, title=None, *, dim=2):
    """``preview`` que guarda en outputs/ en vez de abrir un temporal."""
    name = f"{slug(current_script)}_{slug(title or vis._kind(model))}"
    return rec_show(model, name, title, dim=dim, output_dir=OUTPUT_DIR)


def fake_hasse_preview(complex_like, title=None, **kw):
    name = f"{slug(current_script)}_{slug(title or 'hasse')}"
    kw.pop("open", None)
    kw.pop("output_dir", None)
    path = rec_hasse_show(complex_like, name + "_hasse", title,
                          output_dir=OUTPUT_DIR, **kw)
    if is_simplicial(complex_like):
        # El Hasse de un modelo simplicial trae consigo su dibujo geométrico.
        drawn.append((complex_like, name, OUTPUT_DIR))
    return path


vis.show, vis.preview = rec_show, fake_preview
hasse.show, hasse.preview = rec_hasse_show, fake_hasse_preview
vis._open_file = hasse._open_file = lambda path: None


def to_complex(model):
    """Complejo simplicial de un modelo relacional, haciéndolo propio antes.

    ``KnowledgeBeliefFrame`` trae ``is_proper``/``to_proper`` como métodos;
    un ``RelationalFrame`` suelto usa las funciones de ``properness``. Una
    relación de creencia sola (KD45, no S5) no tiene traducción: ``properness``
    lo dice con un ``ValueError`` y el modelo se salta.
    """
    from properness import is_proper, to_proper
    from simplicial import to_simplicial

    if hasattr(model, "is_proper"):
        proper = model if model.is_proper() else model.to_proper()
    else:
        proper = model if is_proper(model) else to_proper(model)
    return to_simplicial(proper)


def complete_trio(script: str) -> None:
    """Genera, para cada modelo dibujado, las figuras del trío que falten."""
    seen_models: set = set()
    for model, name, out in drawn:
        if id(model) in seen_models:
            continue  # el mismo modelo dibujado dos veces (p. ej. 2D y 3D)
        seen_models.add(id(model))
        if is_simplicial(model):
            # "x_simplicial" -> base "x", así el Hasse se llama "x_hasse" y
            # no "x_simplicial_hasse" (y coincide con el que el script haya
            # generado por su cuenta).
            sm = model
            base = name[:-len("_simplicial")] if name.endswith("_simplicial") else name
        else:
            base = name
            try:
                sm = to_complex(model)
            except Exception as exc:  # noqa: BLE001 -- se informa y se sigue
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
        except Exception:  # noqa: BLE001 -- un ejemplo roto no frena al resto
            failures.append((script, traceback.format_exc().splitlines()[-1]))
            print(traceback.format_exc())
    print(f"\n{len(written)} figuras en {OUTPUT_DIR}/")
    for script, why in failures:
        print(f"FALLÓ {script}: {why}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

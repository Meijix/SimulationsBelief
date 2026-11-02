# Saved workspaces (`saved_models/`)

This folder is where the GUI (`python gui/app.py`) saves and reopens its
**workspaces**: the models you had open, the actions you had defined, and —
if you ask for them — the figures of their last run. It is tracked by git on
purpose: a saved workspace is project material (an example, an experiment,
the input and output of an action), not a scratch output.

## What a workspace file contains

`saved_models/<name>.json` holds the **definition** of each model, exactly
what you see in the editor — never the figures or the run results, which
are recomputed in seconds and would go stale as the code evolves.

```json
{
  "format": "simulationsbelief-workspace/2",
  "saved":  "2026-10-12T10:31:00",
  "models": [
    {
      "name":     "Tesis · Figuras 1 → 3",
      "state":    { "kind": "kb", "agents": ["a", "b", "c"], "worlds": ["w0", "w1", "w2"],
                    "per_agent": { "a": [ {"cls": ["w0", "w1", "w2"], "bel": ["w1", "w2"]} ], ... },
                    "atoms": { "p": ["w1", "w2"] },
                    "vertices": {}, "facets": [], "vatoms": {}, "complex_kind": "kb",
                    "axiom_d": true, "silent_defunct": false, "explicit": false,
                    "hasse_full": false, "make_3d": true },
      "readonly": false,
      "origin":   null
    }
  ],
  "actions": [
    { "name": "anuncio ¬C",
      "events":   [ {"name": "anuncio", "nodes": {"a": "a_oye", "b": "b_oye"}} ],
      "isolated": { "a": [], "b": [] },
      "pre":      { "C": {"true": [], "false": ["a_oye", "b_oye"]} },
      "post":     {},
      "mode": 2, "update": "knowledge" }
  ]
}
```

| field | meaning |
|---|---|
| `models[].state` | the editor state (`gui/adapters/base.py: blank_state`). Relational kinds use `worlds`, `per_agent` (knowledge classes and believed worlds) and `atoms`; a direct complex uses `vertices`, `facets`, `vatoms` and `complex_kind`. The switches (`axiom_d`, `silent_defunct`, `explicit`, `hasse_full`, `make_3d`) travel with the model. |
| `models[].readonly` / `origin` | a **derived** model (the result of an action) is read-only and says where it came from; it is drawn, evaluated and compared like any other, and "duplicar como modelo nuevo" gives an editable copy. |
| `actions[]` | the action specs of the *Actions* tab: events (one action node per agent), isolated action nodes, pre/post conditions as vertex atoms, the pairing `mode` (0–2, numbered as on p. 51 of the thesis; 2 is Def. 4.5 and the default) and the `update` kind (`knowledge` today; `belief`, `belief_memory`, `revision` are listed but pending in the core). |

A file written by an older version still opens: every missing key takes its
default from `blank_state` / `blank_action`, and a format-1 file (which numbered
the modes 1–3) has its action modes shifted to 0–2 on load.

## Saving, opening, downloading (the models bar)

| button | what it does |
|---|---|
| **save** (disk icon) | opens the dialog: name, which models to include (all ticked by default), whether to include the actions, and whether to **include the figures of the last run**. Writes `saved_models/<name>.json`. |
| **folder_open** | lists the saved workspaces. *add* opens its models next to the ones already open; *replace* closes the open ones first. The actions come along the same way. |
| **download** | downloads the active model (plus the actions) as a one-model workspace file, the unit to share or to hand to a script. |

A model opened from a file has no results yet: run it ("Run pipeline")
to get the figures back.

## The figures

Every run writes its figures to `outputs/` at the repository root. That
folder is a **scratch space** (git-ignored, overwritten on every run, the
preview files pile up); nothing in it is tied to a saved workspace.

To keep the figures of a run with the workspace, tick **"incluir las
figuras de la última corrida"** in the save dialog. The GUI then copies, for
every chosen model that has a finished run, the SVG figures and the 3-D page
into **one folder per model**:

```
saved_models/
  experimento.json
  experimento/
    Tesis · Figuras 1 → 3/
      README.md                 which file is which figure
      gui_fig1_general.svg
      gui_fig2_knowledge.svg
      gui_fig2_belief.svg
      gui_fig3_simplicial.svg
      gui_fig3_3d.html
      gui_fig4_hasse.svg
    Tesis · Figuras 1 → 3 ⋅ anuncio ¬C/     the result of an action: its own folder
      ...
```

Folder names are the model names (only path separators are replaced); two
models with the same name get the document id appended so they never share
a folder. The file names are stable (the session tag `_d3` of
`outputs/` is dropped), so a folder can be regenerated in place.

The 3-D page is the heavy output (~3 MB of embedded Plotly per run). The
switch **"Generar vista 3D interactiva"** under *Opciones de dibujo* turns
it off for a model: the run then writes the SVG figures only, and the
figure export copies nothing for it.

## From a script

A workspace file can be produced without the GUI, which is how computed
models (the output of `simplicial_actions.update_model`, a revision, any
`SimplicialBeliefModel`) enter it:

```python
import json
from gui.adapters import doc_from_model, workspace_payload

doc = doc_from_model("tell sobre M1", model, assignment,
                     origin="acción tell sobre Modelo 1")   # read-only, with provenance
payload = workspace_payload([doc], actions=[])
open("saved_models/resultado.json", "w", encoding="utf-8").write(
    json.dumps(payload, ensure_ascii=False, indent=1))
```

Open it from the folder_open button like any other workspace.

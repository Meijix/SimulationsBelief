# SimulationsBelief

Simulations of relational (Kripke) and simplicial models of knowledge and
belief, the translations between them, and simplicial action models, following
Philip Sink's PhD thesis. Companion code to the thesis and to the article in
`paper/`. Progress against the thesis, and what is still pending, is in
[ROADMAP.md](ROADMAP.md).

## The GUI without installing anything

Download the executable for your system from the
[Releases](https://github.com/Meijix/SimulationsBelief/releases) page and
double-click it: it starts a local server and opens the GUI in your browser.
Figures, saved workspaces and your settings go to a `SimulationsBelief` folder
in your home directory. The Windows build ships with Graphviz inside; on macOS
install it once with `brew install graphviz`.

The GUI is a workspace: several model documents open at once (blank, duplicated,
renamed, compared side by side), each of one kind: knowledge and belief,
knowledge only, belief only, or a simplicial complex typed directly. Agents,
worlds, classes, believed worlds and atoms are entered as chips; a live preview
draws the model as entered; an example library loads the models of the thesis,
the poster and the examples; a formula evaluator runs on the result. Figures:
relational model, proper model, 2-D complex, interactive 3-D complex and the
Hasse lattice, downloadable as PNG. The *Actions* tab defines simplicial actions
and applies the four update kinds of the thesis (knowledge, belief, revision,
revision with memory) to the active model. Workspaces are saved under
`saved_models/` (see its README). Step-by-step tutorial: `docs/15`.

## Install from source

```bash
git clone https://github.com/Meijix/SimulationsBelief.git
cd SimulationsBelief
python3 -m venv .venv
.venv/bin/pip install -e .            # core modules, GUI and the simulationsbelief-gui command
.venv/bin/pip install -e ".[test]"    # ...plus pytest and hypothesis
brew install graphviz                 # macOS; Debian/Ubuntu: sudo apt install graphviz
```

Python 3.11 or newer. Rendering needs the Graphviz `dot` binary (relational
models, Hasse diagrams), matplotlib (2-D complexes) and plotly (3-D complexes).

## Use

```bash
simulationsbelief-gui                              # the GUI at http://localhost:8080 (port: SIMULATIONSBELIEF_PORT)
.venv/bin/python gui/app.py                        # the same, without installing
.venv/bin/python examples/thesis_example.py        # the thesis Figures 1 -> 2 -> 3, end to end
.venv/bin/python examples/example_val.py           # a small model with a valuation, step by step
.venv/bin/python examples/examplesimplicial1.py    # a simplicial model defined directly
.venv/bin/python examples/action_knowledge_example.py   # a knowledge action, step by step
.venv/bin/python poster/poster-code/revision.py    # public announcement + belief revision
.venv/bin/python regenerate_outputs.py             # every example figure in outputs/, in one go
.venv/bin/python -m pytest -q                      # the test suite
```

From Python, the three functions to remember accept any model of the project:

```python
from visualization import visualize, show, preview
visualize(model)                 # text diagram
show(model, "name")              # outputs/name.png
preview(model)                   # render and open
import hasse; hasse.show(sm, "name", facets_and_vertices=True)   # the face lattice
```

## Layout

| Where | What |
|---|---|
| repository root | the core modules: `relational_frame`, `properness`, `knowledge_belief`, `simplicial`, `semantics`, `assignment`, `simplicial_actions`, `hasse`, `visualization`; `bisimulation/` |
| `gui/` | the NiceGUI web GUI; `gui/adapters/` is the only bridge to the core |
| `examples/` | the demo scripts; each puts the repo root on `sys.path`, so they run from anywhere |
| `tests/` | the pytest suite, one file per module plus the GUI bridge |
| `docs/` | the notes: theory, worked examples, map of every function (`docs/README.md`) |
| `paper/`, `poster/`, `Presentation/` | the article, the Coloquio poster and a talk, with their figure scripts |
| `references/` | the source PDFs |
| `packaging/` | how the GUI executable is built (`.github/workflows/build-gui.yml` builds it on each release) |
| `outputs/` | every generated figure (git-ignored) |

## Authors and license

Natalia Edith Mejía Bautista and Philip Sink. MIT license, see `LICENSE`.

# SimulationsBelief
Part 1: A testing tool to simulate relational model and simplicial models for belief. **Done.**

Step 1: Classes for relational models, proper relational models for belief — `relational_frame.py`, `knowledge_belief.py` ✔

Step 2: Function that translates a relational model into a proper relational model — `properness.py` ✔

Step 3: Class for simplicial models for belief — `simplicial.py` ✔

Step 4: Function that translates proper relational model into simplicial model — `simplicial.to_simplicial` ✔

Step 5: Validate with thesis example — `thesis_example.py` + `tests/` ✔

Beyond the roadmap, the logical layer is in too: Kripke valuations and formula
evaluation (`semantics.py`), the canonical **vertex-based** three-valued
assignments of thesis ch. 3 (`assignment.py`, values 1/0/2 on perspectives,
truth lifted to facets), the K45/KD45 switch (`axiom_d` — Axiom D on/off across
the whole pipeline), and three input cases (knowledge only, belief only with
induced knowledge, or both). See `docs/README.md` for the doc index and
`docs/pipeline.txt` for the function-by-function map.

Part 2: Simulating Public Announcement *(pending)*

Part 3: Simulating Dynamic Update *(pending)*

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Image rendering (`visualization.show()`) needs the Graphviz system binary:

```bash
brew install graphviz        # macOS
# sudo apt install graphviz  # Debian/Ubuntu
```

## Usage
```bash
.venv/bin/python example_val.py          # a small model WITH a valuation, step by step
.venv/bin/python thesis_example.py       # the thesis Figures 1 -> 2 -> 3, end to end
.venv/bin/python examples.py             # run the feature demos
.venv/bin/python examples.py --open      # ...and open each image in your viewer
.venv/bin/python examples2.py            # a single frame, step by step
```

`visualization.show(model, name, valuation=...)` labels Kripke worlds with their
literals; `show(sm, name, assignment=...)` labels simplicial vertices with what
each perspective observes (thesis Figure 5-9 style).

For a quick one-off look at a model in the REPL, use `visualization.preview(model)`
(renders and opens it). Generated images are written to `outputs/` (git-ignored).

## GUI

A minimal web GUI (NiceGUI, pure Python) lives in `gui/` -- type relation
*seeds*, run the whole general → proper → simplicial pipeline, and see every
figure (including the interactive 3-D view) in the browser:

```bash
.venv/bin/python gui/app.py     # opens http://localhost:8080
```

The GUI only *calls* the core: `gui/adapters.py` is the single bridge
(parsing + pipeline + rendering via `visualization.show`), `gui/app.py` is
presentation only, and no core module knows the GUI exists.

Tests live in `tests/`, kept local (git-ignored). To run them:
```bash
.venv/bin/python -m pytest -q
```
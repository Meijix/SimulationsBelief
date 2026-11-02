# SimulationsBelief
Part 1: A testing tool to simulate relational model and simplicial models for belief. **Done.**

Step 1: Classes for relational models, proper relational models for belief — `relational_frame.py`, `knowledge_belief.py` ✔

Step 2: Function that translates a relational model into a proper relational model — `properness.py` ✔
(the distinguished agent defaults to the one with the fewest non-reflexive
edges, knowledge and belief counted together — `properness.cheapest_distinguished_agent`)

Step 3: Class for simplicial models for belief — `simplicial.py` ✔
(a complex can also be defined **directly** from nodes, facets and `S_a`, with
no relational model behind it — `examples/examplesimplicial1.py`; facet-consistency
checks; isolated perspectives are legal unless `axiom_d=True`)

Step 4: Function that translates proper relational model into simplicial model — `simplicial.to_simplicial` ✔
(and back: `simplicial.to_relational` is the inverse translation `G_B` of the
categorical equivalence of Goubault, Ledent & Rajsbaum extended to belief, one
world per facet, `R_a` = sharing `a`'s vertex, `Q_a` = the facets of `S_a`;
the round trip is tested, and the GUI shows the equivalent Kripke model of any
complex typed by hand and opens it as a document of its own)

Step 5: Validate with thesis example — `examples/thesis_example.py` + `tests/` ✔

Beyond the roadmap, the logical layer is in too: Kripke valuations and formula
evaluation (`semantics.py`), the canonical **vertex-based** three-valued
assignments of thesis ch. 3 (`assignment.py`, values 1/0/2 on perspectives,
truth lifted to facets), the K45/KD45 switch (`axiom_d` — Axiom D on/off across
the whole pipeline, inferred from the geometry when a complex is built
directly), the three pipeline cases (case 1 beliefs only with induced
knowledge, case 2 knowledge and belief, case 3 knowledge only with the
silence convention `Q_a = R_a`), and the face lattice of every complex as a
Hasse diagram (`hasse.py`, full lattice or the vertices-and-facets view). See
`docs/README.md` for the doc index and `docs/pipeline.txt` for the
function-by-function map.

Part 2: Simulating Public Announcement — **implemented** for the simplicial
side in `poster/poster-code/revision.py`: a public announcement deletes the facets where it is
false, and an agent whose believed facet was deleted is sent to a surviving
facet by the belief-revision rule of Sink & Goodloe (NASA TM):
`R_x(X) = argmax { |Y ∩ X| : Y survives, pi_x(Y) = pi_x(X) }`. Used by the
poster figures (`poster/poster-code/make_figs_3agentes*.py`); `python poster/poster-code/revision.py`
runs the three-agent disaster example. The relational-side operator `M[φ]` with imaging
and iterated announcements with memory (doc 05 §2.3–2.5) are still *pending*.

Part 3: Simulating Dynamic Update — **products done, protocols pending**.
`simplicial_actions.py` implements action models as chromatic simplicial
complexes (events = facets of action nodes, one per agent; per-agent event
subcomplexes `S_{a,A}`) with three-valued literal pre- and postconditions on
the nodes, **modal-formula preconditions** (`pre_formula`, in the syntax of
`assignment.holds`, evaluated at the input facets) and event-level formulas
(`pre_event`, the precondition of a Kripke action model), and the three
products of Sink's thesis ch. 4: `update_model` (knowledge, `M[A]`, Def. 4.5),
`belief_update_model` (belief, `M[A]_B`, Def. 4.6: each agent's `S_a` from its
own `S_a` and `S_{a,A}`, collapsed perspectives reported) and
`revision_update_model` (belief with revision, `M[A]_BR`, Def. 4.8: lost
belief facets are imaged onto the nearest realisable ones, with or without
memory, thesis §3.5.2). Node pairing has the three modes of thesis p. 51,
numbered as there (mode 2, Def. 4.5, by default). The knowledge product
reproduces the thesis's Alternating Message Passing Protocol (8 vertices after
one step, 12 after two). Outputs are built with `axiom_d=False` (K45) because
an update routinely leaves isolated or collapsed perspectives, and they chain.
The GUI's *Actions* tab defines actions (with a live drawing of the action as
it is typed, and per event the agents that consider it possible) and applies
any of the four update kinds to the active model; what the product reports
shows under the result's banner. `examples/action_knowledge_example.py` and
`examples/action_belief_example.py` walk the products step by step. Still
*pending*: protocols (iterating an action and tracking collapse and
convergence).

## Layout

- the repository root holds the core modules (`relational_frame.py`,
  `properness.py`, `knowledge_belief.py`, `simplicial.py`, `semantics.py`,
  `assignment.py`, `hasse.py`, `visualization.py`, `simplicial_actions.py`),
  `regenerate_outputs.py` and the packaging (`pyproject.toml`, which installs
  the modules, the `gui` package and the `simulationsbelief-gui` command);
- `examples/` — the demo scripts (`thesis_example.py`, `example_val.py`,
  `examples*.py`, `examplesimplicial1.py`, the three `Example for Poster N.py`,
  `Natural Disaster Example.py`, `action_knowledge_example.py`); each puts the
  repo root on `sys.path` itself, so they run from any working directory;
- `gui/` — the web GUI; `tests/` — the pytest suite (git-ignored);
  `docs/` — the notes (git-ignored); `references/` — the source PDFs;
- `poster/` — the Coloquio poster: `poster-code/` (the figure scripts,
  `ejemplo_nasa.py` and `revision.py`), `outputs/` (the committed figures),
  `images/` (logos and QR), `_intermedios/` (checks and discards);
- `paper/` — the article;
- `outputs/` — every figure the examples, the GUI and `regenerate_outputs.py`
  write (git-ignored).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e .            # the project itself (pyproject.toml); or: pip install -r requirements.txt
.venv/bin/pip install -e ".[test]"    # ...plus pytest and hypothesis
```

Image rendering (`visualization.show()`) needs the Graphviz system binary:

```bash
brew install graphviz        # macOS
# sudo apt install graphviz  # Debian/Ubuntu
```

## Usage

The main entry points, one line each (the full map of every runnable script,
the GUI and the poster figures is `docs/11-scripts-gui-and-figures.md`):

```bash
.venv/bin/python examples/example_val.py          # a small model WITH a valuation, step by step (6 steps)
.venv/bin/python examples/thesis_example.py       # the thesis Figures 1 -> 2 -> 3, end to end
.venv/bin/python poster/poster-code/ejemplo_nasa.py   # poster example: three relief units, 8 worlds, an octahedron
.venv/bin/python examples/examplesimplicial1.py   # a simplicial model defined DIRECTLY (no Kripke model)
.venv/bin/python poster/poster-code/revision.py   # public announcement + belief revision, disaster example
.venv/bin/python regenerate_outputs.py            # regenerate EVERY example figure in outputs/ in one go
.venv/bin/python examples/examples.py             # run the feature demos (validation, closures, muddy children)
.venv/bin/python examples/examples.py --open      # ...and open each image in your viewer
.venv/bin/python examples/examples2.py            # a single belief-only (KD45) frame, step by step
.venv/bin/python "examples/Example For Poster 1.py"   # poster Examples 1-3 and "Natural Disaster Example.py"
.venv/bin/python examples/action_knowledge_example.py # a knowledge action step by step (thesis §4.4 signal, Fig. 52 action)
```

The core modules live in the repository root; every demo script is under
`examples/` (and the poster's under `poster/poster-code/`), and each one puts
the root on `sys.path` itself, so they run from any working directory.

`visualization.show(model, name, valuation=...)` labels Kripke worlds with their
literals; `show(sm, name, assignment=...)` labels simplicial vertices with what
each perspective observes (thesis Figure 5-9 style). `hasse.show(sm, name)`
draws the face lattice (`facets_and_vertices=True` keeps only perspectives and
worlds).

For a quick one-off look at a model in the REPL, use `visualization.preview(model)`
(renders and opens it). Generated images are written to `outputs/` under the
current directory — the root `outputs/`, git-ignored, when run from the repo
root; the poster scripts write to `poster/outputs/` instead (see `poster/README.md`).

## GUI

A web GUI (NiceGUI, pure Python) lives in `gui/`. It is a **workspace**: several
model documents open at once in a models bar (open blank, duplicate, rename,
close, compare 2–4 side by side; results are stored per document and only the
changed ones are recomputed). Each document has a **model kind**:

* **knowledge and belief** — `KnowledgeBeliefFrame`, full pipeline
  general → proper → simplicial;
* **knowledge only** — S5 `RelationalFrame`, full pipeline with `S_a = S`;
* **belief only** — KD45/K45 `RelationalFrame`; no properness and no
  simplicial translation, the pipeline stops at step 1 and says so;
* **direct simplicial complex** — named vertices per agent, facets and `S_a`
  typed by hand (or none: a 0-dimensional complex is drawn too), atoms on
  vertices; the "pipeline" validates, draws, and shows the equivalent Kripke
  model (`to_relational`), which can be opened as a new document and sent
  back through the pipeline.

Agents, worlds, knowledge classes, believed worlds and atoms are entered as
chips; a live preview draws the model exactly as entered; an example library
in the header loads complete states (the scripts in `examples/` and the poster
examples); a formula evaluator (`K_a`, `B_a`, `¬ & | ->`) runs on the result.
Figures: relational model, proper model, 2-D complex, interactive **3-D**
complex, and the **Hasse lattice** (vertices-and-facets by default, full
lattice on demand). The **Actions** tab defines simplicial actions (events,
isolated action nodes, literal pre/postconditions, modal-formula
preconditions), draws the action as it is being defined, and applies it to
the active model with the knowledge product; the result opens as a read-only
document with an annotated origin, and can be saved and compared like any
other. Workspaces (models and actions, optionally with their figures) are
saved under `saved_models/` (see its README). Any unhandled exception shows
as a red notification naming the file and line, besides the terminal
traceback.

```bash
.venv/bin/python gui/app.py     # opens http://localhost:8080
simulationsbelief-gui           # the same, once installed with pip install -e . (port: SIMULATIONSBELIEF_PORT)
```

The GUI only *calls* the core: the `gui/adapters/` package is the single bridge
(parsing + pipeline + rendering via `visualization.show` and `hasse.show`),
`gui/app.py` is presentation only, and no core module knows the GUI exists.

## Tests

Tests live in `tests/`, kept local (git-ignored): one file per core module
(`test_relational_frame`, `test_knowledge_belief`, `test_properness`,
`test_simplicial`, `test_semantics`, `test_assignment`, `test_hasse`,
`test_simplicial_actions` for the action products, `test_actions_kripke`
for the action translations and the product on both sides) plus `test_gui_adapters.py` and
`test_workspace.py` for the GUI bridge (regression cover for the reported
issues: digit atoms, K45 defunct belief from the GUI, the distinguished
agent, duplicate and missing facets, the action layer).
`poster/poster-code/revision.py` has no tests yet. To run:
```bash
.venv/bin/python -m pytest -q
```

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

Part 3: Simulating Dynamic Update — **partial**. `simplicial_actions.py`
implements action models as chromatic simplicial complexes (events = facets,
three-valued pre- and postconditions) and the product update
`update_model(model, assignment, action, mode)` (three compatibility modes,
no-clash by default), in the simplicial-DEL tradition of Goubault, Ledent &
Rajsbaum. **Knowledge actions only** for now: the action has one facet set,
the input's `S_a` is never read and the output sets `S_a = S`; the belief
products `M[A]_B` and `M[A]_BR` (action with revision) and protocols are
*pending*. The output is built with `axiom_d=False` (K45) because an update
routinely leaves isolated perspectives. No script or test exercises it yet.

## Layout

- the repository root holds the core modules (`relational_frame.py`,
  `properness.py`, `knowledge_belief.py`, `simplicial.py`, `semantics.py`,
  `assignment.py`, `hasse.py`, `visualization.py`, `simplicial_actions.py`)
  and `regenerate_outputs.py`;
- `examples/` — the demo scripts (`thesis_example.py`, `example_val.py`,
  `examples*.py`, `examplesimplicial1.py`, the three `Example for Poster N.py`,
  `Natural Disaster Example.py`); each puts the repo root on `sys.path`
  itself, so they run from any working directory;
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
.venv/bin/pip install -r requirements.txt
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
  typed by hand, atoms on vertices; the "pipeline" only validates and draws.

Agents, worlds, knowledge classes, believed worlds and atoms are entered as
chips; a live preview draws the model exactly as entered; an example library
in the header loads complete states (the scripts in `examples/` and the poster
examples); a formula evaluator (`K_a`, `B_a`, `¬ & | ->`) runs on the result.
Figures: relational model, proper model, 2-D complex, interactive **3-D**
complex, and the **Hasse lattice** (vertices-and-facets by default, full
lattice on demand). Read-only documents with an annotated origin are the hook
through which action-model results will arrive.

```bash
.venv/bin/python gui/app.py     # opens http://localhost:8080
```

The GUI only *calls* the core: `gui/adapters.py` is the single bridge
(parsing + pipeline + rendering via `visualization.show` and `hasse.show`),
`gui/app.py` is presentation only, and no core module knows the GUI exists.

## Tests

Tests live in `tests/`, kept local (git-ignored): one file per core module
(`test_relational_frame`, `test_knowledge_belief`, `test_properness`,
`test_simplicial`, `test_semantics`, `test_assignment`, `test_hasse`) plus
`test_gui_adapters.py` for the GUI bridge (regression cover for the reported
issues: digit atoms, K45 defunct belief from the GUI, the distinguished
agent). `poster/poster-code/revision.py` and `simplicial_actions.py` have no
tests yet. To run:
```bash
.venv/bin/python -m pytest -q
```

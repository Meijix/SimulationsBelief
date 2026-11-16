# Roadmap and status

What the project set out to do, what is done, and what is pending. The theory
behind each step is in `docs/` (index in `docs/README.md`; function-by-function
map in `docs/pipeline.txt`).

## Part 1: relational and simplicial models of belief. Done.

| Step | Where | Notes |
|---|---|---|
| 1. Relational models; proper relational models for belief | `relational_frame.py`, `knowledge_belief.py` | KD45 / K45 (`axiom_d`), S5 knowledge, the two-relation frames of the thesis |
| 2. General -> proper translation | `properness.py` | the distinguished agent defaults to the one with the fewest non-reflexive edges, knowledge and belief counted together (`cheapest_distinguished_agent`) |
| 3. Simplicial models of belief | `simplicial.py` | a complex can also be defined directly from nodes, facets and `S_a`; facet-consistency checks; isolated perspectives are legal unless `axiom_d=True` |
| 4. Proper -> simplicial translation | `simplicial.to_simplicial` | and back: `to_relational` is the inverse `G_B` of the categorical equivalence of Goubault, Ledent & Rajsbaum extended to belief; the round trip is tested |
| 5. Validation with the thesis example | `examples/thesis_example.py`, `tests/` | |

Beyond the roadmap: Kripke valuations and formula evaluation (`semantics.py`),
the canonical vertex-based three-valued assignments of thesis ch. 3
(`assignment.py`), the K45/KD45 switch across the whole pipeline, the three
pipeline cases (beliefs only, knowledge and belief, knowledge only with the
silence convention `Q_a = R_a`), the face lattice of every complex as a Hasse
diagram (`hasse.py`), and bisimilarity by partition refinement
(`bisimulation/`) checking Thm 2.4 directly.

## Part 2: public announcement. Implemented on the simplicial side.

`poster/poster-code/revision.py`: a public announcement deletes the facets
where it is false, and an agent whose believed facet was deleted is sent to a
surviving facet by the belief-revision rule of Sink & Goodloe (NASA TM),
`R_x(X) = argmax { |Y ∩ X| : Y survives, pi_x(Y) = pi_x(X) }`. Used by the
poster figures; `visualization.show(..., revision=...)` draws it.

**Pending:** the relational-side operator `M[φ]` with imaging, and iterated
announcements with memory (docs/05 §2.3 to 2.5). `revision.py` has no tests of
its own yet.

## Part 3: dynamic update. Products done, protocols pending.

`simplicial_actions.py` implements action models as chromatic simplicial
complexes (events = facets of action nodes; per-agent event subcomplexes
`S_{a,A}`) with three-valued literal pre- and postconditions, modal-formula
preconditions (`pre_formula`, `pre_event`) and the three products of thesis
ch. 4: `update_model` (`M[A]`, Def. 4.5), `belief_update_model` (`M[A]_B`,
Def. 4.6) and `revision_update_model` (`M[A]_BR`, Def. 4.8, with or without
memory, §3.5.2). Node pairing has the three modes of thesis p. 51. The
knowledge product reproduces the Alternating Message Passing Protocol (8
vertices after one step, 12 after two). Outputs are built as K45 because an
update routinely leaves isolated or collapsed perspectives. Kripke action
models and the product on both sides: `to_relational_action`,
`action_from_relational`, `kripke_product` (docs/12 §4).

The GUI's *Actions* tab defines actions with a live drawing and applies any of
the four update kinds; `examples/action_knowledge_example.py` and
`examples/action_belief_example.py` walk the products step by step.

**Pending:** protocols (iterating an action and tracking collapse and
convergence).

## Repository

- Tests (`tests/`, 505) and notes (`docs/`) are kept local and git-ignored; the
  question of tracking them is open.
- The GUI executable is built by `.github/workflows/build-gui.yml` on each
  tagged release (see `packaging/README.md`).

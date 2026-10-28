# `bisimulation/` — are two models the same model, for the logic?

This folder answers one question and keeps its source material next to the
answer: **does `to_proper` really return a model bisimilar to the one it was
given?** That is the claim of Thm. 2.4 of Sink's thesis, and the whole reason
the proper model is worth building.

| file | what it is |
|---|---|
| `bisimulation.py` | the implementation: Kanellakis-Smolka partition refinement, plus the checks built on it |
| `kanellakisalgoritmo.pdf` | Aceto, Ingolfsdottir & Srba, *The Algorithmics of Bisimilarity*. §0.2 is the algorithm (Def. 0.2.1, Lemma 0.2.2, Def. 0.2.3, Figures 0.1–0.2, Def. 0.2.10, Thm. 0.2.6); §0.3.2 is the P-completeness result |
| `example_bisimilarity.py` | four worked examples: a model, its proper twin, the verdict and the figures |
| `__init__.py` | re-exports, so `import bisimulation` keeps working |

## The short version

Bisimilarity is the largest fixed point of the back-and-forth condition, so it
is computed **from the top down**: start with everything related and keep
splitting. A partition that cannot be split any further -- a *stable* partition
-- is exactly a bisimulation, so "largest bisimulation" and "coarsest stable
partition" are the same problem in two vocabularies. The loop in
`coarsest_stable_partition` is Figure 0.2 of the chapter; `_split` is Figure 0.1.

```python
import bisimulation as bis

proper = general.to_proper()
bis.projection_is_bisimulation(general, proper, {"P": {"w1"}})   # the claim
print(bis.explain(general, proper, {"P": {"w1"}}))               # readable verdict
```

`python bisimulation/bisimulation.py` runs a short demo: the thesis's Figure 1
checked end to end, and a counterexample showing the checker can say *no*.

## The worked examples

```bash
python bisimulation/example_bisimilarity.py          # print and draw
python bisimulation/example_bisimilarity.py --open   # ...and open the figures
```

Four models, each making a different point, all put through the same pipeline
(is it proper? → `to_proper` → verify → draw):

1. **A coin nobody saw.** Two agents, two worlds, knowledge complete: as
   improper as a model gets. The four-world proper twin shows the construction
   at a glance -- the non-distinguished agent joins worlds *within* a copy, the
   distinguished one *across* copies, and together they pin each world down.
2. **Sink's Figure 1**, with an atom: knowledge and belief, false belief at
   `w0`, and the check run over the full language.
3. **A model that is already proper**, where `to_proper` copies nothing and the
   verification confirms the identity is a bisimulation.
4. **A NO**: two models whose frames are isomorphic but whose atoms break the
   symmetry, so the checker refuses -- because one that only ever says yes
   would be worth nothing.

Figures land in `../outputs/` (git-ignored).

## Where the rest lives

* **The full write-up** -- theory, the two adaptations this repo needs, and a
  section-by-section account of why the implementation looks the way it does --
  is `../docs/14-bisimilaridad-refinamiento-particiones.md` (in Spanish).
* **The construction being verified** is `../properness.py`, explained in
  `../docs/02-proper-models.md`.
* **The tests** are `../tests/test_bisimulation.py`: the chapter's own worked
  examples (0.2.4 and 0.2.11, whose answers are published), the repo's golden
  models, negative controls, and cross-validation against a naive fixpoint and
  against the formula evaluator of `../semantics.py`.

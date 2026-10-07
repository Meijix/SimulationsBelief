# paper/ — the article about this project

Work in progress: the article we are writing about SimulationsBelief (the
relational → proper → simplicial pipeline, the vertex-based three-valued
semantics, and the K45/KD45 machinery).

## Contents

- `SimulationsBelief.tex` — the article source (tracked). Sections as of
  2026-10-07: Introduction, Background, Code (still empty), Static Examples
  with Example 1–3 (the figures below), Dynamic Examples (still empty),
  Discussion and Future Work.
- `Epistemology.bib` — the bibliography (tracked; referenced by the `.tex` as
  `\bibliography{Epistemology}`, so keep both files together).
- `HasseExample1.png` — the face-lattice figure of the Background section
  (tracked).
- `Poster Example 1 Relational Case.png`, `Poster Example 1 Simplicial Case.png`,
  `Poster Example 2 Relational Case.png`, `Poster Example 2 Simplicial Case.png`,
  `Poster Example 3 Improper Relational Case.png`,
  `Poster Example 3 Proper Relational Case.png`,
  `Poster Example 3 Simplicial Case.png` — the figures of the Static Examples
  section (tracked). They are the previews that
  `../examples/Example For Poster 1.py`, `../examples/Example for Poster 2.py`
  and `../examples/Example for Poster 3.py` open (the file names are the
  previews' titles), saved here by hand; no script writes into `paper/`.
  `../regenerate_outputs.py` redraws the same pictures as
  `../outputs/example_for_poster_*.png`.
- Everything else (`.aux`, `.bbl`, `.blg`, `.fls`, `.fdb_latexmk`, `.log`,
  `.out`, `.synctex.gz`, the compiled `SimulationsBelief.pdf`) is a build
  artifact, regenerated on every compile and git-ignored by `paper/.gitignore`.

## Building

```bash
cd paper
pdflatex SimulationsBelief.tex
bibtex   SimulationsBelief
pdflatex SimulationsBelief.tex && pdflatex SimulationsBelief.tex
```

## Related material elsewhere in the repository

- The source PDFs the article cites are in `../references/`.
- Figures can be generated from the code into `../outputs/`
  (`visualization.show`, `hasse.show` — both accept `valuation=` /
  `assignment=` to draw the logical layer; see `../docs/08` and `../docs/06`).
  `../regenerate_outputs.py` redraws every example figure in one go; the
  poster figures live in `../poster/outputs/`, their scripts in
  `../poster/poster-code/` (see `../poster/README.md`).
- The code behind the empty *Dynamic Examples* section already exists:
  `../poster/poster-code/revision.py` (the NASA-TM revision rule, used for
  `../poster/outputs/d3_revision.png`) and `../simplicial_actions.py` (action
  models and the knowledge-style product update).
- The accessible write-ups the article can draw from are `../docs/01`–`08`
  (English); `../docs/09` (poster story options) and `../docs/10` (proper /
  local / pure, the companion of §2) are in Spanish; `../docs/11` maps every
  script, the GUI and the figure builders.

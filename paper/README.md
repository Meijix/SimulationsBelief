# paper/ — the article about this project

Work in progress: the article we are writing about SimulationsBelief (the
relational → proper → simplicial pipeline, the vertex-based three-valued
semantics, and the K45/KD45 machinery).

## Contents

- `SimulationsBelief.tex` — the article source (tracked).
- `Epistemology.bib` — the bibliography (tracked; referenced by the `.tex` as
  `\bibliography{Epistemology}`, so keep both files together).
- Everything else (`.aux`, `.log`, `.out`, `.synctex.gz`, the compiled
  `SimulationsBelief.pdf`) is a build artifact, regenerated on every compile
  and git-ignored here (see `.gitignore`).

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
- The accessible write-ups the article can draw from are `../docs/01`–`08`.

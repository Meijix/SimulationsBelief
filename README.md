# SimulationsBelief
Part 1: A testing tool to simulate relational model and simplicial models for belief. 


Step 1: Classes for relational models, proper relational models for belief

Step 2: Function that translates a relational model into a proper relational model.

Step 3: Class for simplicial models for belief

Step 4: Function that translates proper relational model into simplicial model

Step 5: Validate with thesis example


Part 2: Simulating Public Announcement

Part 3: Simulating Dynamic Update

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
.venv/bin/python examples.py             # run the feature demos
.venv/bin/python examples.py --open      # ...and open each image in your viewer
.venv/bin/python examples2.py            # a single frame, step by step
```

For a quick one-off look at a model in the REPL, use `visualization.preview(model)`
(renders and opens it). Generated images are written to `outputs/` (git-ignored).

Tests live in `tests/`, kept local (git-ignored). To run them:
```bash
.venv/bin/python -m pytest -q
```
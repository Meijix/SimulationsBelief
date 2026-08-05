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

Image rendering (`RelationalFrame.render()`) needs the Graphviz system binary:

```bash
brew install graphviz        # macOS
# sudo apt install graphviz  # Debian/Ubuntu
```

## Usage
```bash
.venv/bin/python relational_frame.py     # run the built-in examples
.venv/bin/python -m pytest -q            # run the test suite
```

Generated images are written to `outputs/` (git-ignored).
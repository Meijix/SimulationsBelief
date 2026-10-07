"""Empty scaffold for the next example.

Only the imports of the example series are here (knowledge+belief frames,
``to_simplicial``, the properness helpers, the renderers); no model is built
yet, so running it does nothing. Copy this file to start a new script with the
full knowledge + belief -> proper -> simplicial pipeline already imported.

Run:  python examples/examples8.py
"""

import os
import sys
# The examples live one level below the core modules. Put the repository root on
# sys.path so ``python examples/<script>.py`` works from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_belief import KnowledgeBeliefFrame
from visualization import preview, show, to_dot, visualize
from relational_frame import RelationalFrame
from simplicial import to_simplicial
from properness import is_proper, non_proper_worlds, explain, to_proper




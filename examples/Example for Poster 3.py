"""Poster Example 3 -- the main example of "A Semantics for Belief in Simplicial Complexes".

Story: three agents, three worlds, and no evidence at all -- nobody can tell w1,
w2, w3 apart -- yet a believes {w2, w3}, b is sure of w2 and c is sure of w3.
At w1 all three are wrong at once. (Thesis Fig. 1 with w0, w1, w2 renamed w1,
w2, w3; see thesis_example.py and docs/04-figures-1-2-3.md.)

Route: knowledge + belief with one seed for both relations
(``KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)``):
under S5 the seed gives complete knowledge, inside those classes it gives the
pointed beliefs. The model is NOT proper (every pair of worlds is related by
every agent), so ``to_proper`` copies the worlds (|W|^2 = 9) and skews one
distinguished agent; only then ``to_simplicial`` maps worlds to facets and
``hasse.preview`` draws the face lattice. Reproduces the poster / paper figures
"Poster Example 3 Improper / Proper Relational Case" and "... Simplicial Case".

Run:  python "examples/Example for Poster 3.py"   (opens three previews).
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
import hasse

#This is the main example in "Semantics for Belief in Simplicial Complexes". We start with a knowledge/belief frame that is NOT proper, but a seemingly sensible model of belief
#(though perhaps without applications! See Example for Poster 2). We then make it proper, and turn it into a simplicial complex.

agents = {"a", "b", "c"}
worlds = {"w1", "w2", "w3"}
#One-way pointers only, no symmetric pairs: read as knowledge they still close to
#the complete relation for everyone; read as belief they are the opinions
#a: {w2, w3}, b: {w2}, c: {w3}, all false at w1.
frameseed = {"a":{("w1","w2"),("w1","w3")}, "b":{("w1","w2"),("w3","w2")}, "c":{("w2","w3"),("w1","w3")}}

ImproperRelPosterExample3 = KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)

print(f"{KnowledgeBeliefFrame.is_proper(ImproperRelPosterExample3)}")

preview(ImproperRelPosterExample3, "Poster Example 3: The Improper Relational Case")

# Now we make this proper. to_proper skews the agent with the fewest NON-reflexive
# edges, counting knowledge AND belief (properness.cheapest_distinguished_agent):
# knowledge ties at 6 each, belief gives a=4, b=2, c=2, and the b/c tie breaks by
# name, so `b` is skewed (as in the thesis). 9 worlds, Q_a ⊆ R_a preserved.

ProperRelPosterExample3 = KnowledgeBeliefFrame.to_proper(ImproperRelPosterExample3)

print(f"{KnowledgeBeliefFrame.is_proper(ProperRelPosterExample3)}")

preview(ProperRelPosterExample3, "Poster Example 3: The Proper Relational Case")

#Now we make this simplicial

SimpPosterExample3 = to_simplicial(ProperRelPosterExample3)

hasse.preview(SimpPosterExample3, "Poster Example 3: The Simplicial Case")



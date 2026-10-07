"""The thesis pipeline in its shortest form: Fig. 1 -> Fig. 2 -> Fig. 3.

Story: the three-agent thesis example (poster Example 3). Knowledge is
complete for everyone -- nobody can tell w1, w2, w3 apart -- yet a believes
{w2, w3}, b believes w2 and c believes w3, so at w1 all three are wrong.

Route: knowledge + belief with ONE seed used for both relations
(``KnowledgeBeliefFrame.from_partial(agents, worlds, frame, frame)``): closed
under S5 it is complete knowledge, closed inside those classes it is the pointed
beliefs. The model is not proper, so ``to_proper`` copies the worlds (|W|^2 = 9)
and skews one agent; ``to_simplicial`` then turns worlds into facets and
(agent, knowledge class) pairs into nodes, and ``hasse.preview`` draws the face
lattice.

Run:  python examples/examples7.py   (opens three previews).
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

agents = {"a", "b", "c"}
worlds = {"w1", "w2", "w3"}
frame = {"a":{("w1","w2"),("w1","w3")}, "b":{("w1","w2"),("w3","w2")}, "c":{("w2","w3"),("w1","w3")}}

# The same seed is read twice: as knowledge it closes under S5 to the complete
# relation; as belief it stays inside those classes as the pointers a: {w2, w3},
# b: {w2}, c: {w3}.
KBframe = KnowledgeBeliefFrame.from_partial(agents, worlds, frame, frame)
preview(KBframe, "KB frame")

print(f"{KnowledgeBeliefFrame.is_proper(KBframe)}")

#print(f"{KnowledgeBeliefFrame.non_proper_worlds(BKframe)}")

KBproperframe = KnowledgeBeliefFrame.to_proper(KBframe)
preview(KBproperframe, "KB proper frame")

print(f"{KnowledgeBeliefFrame.is_proper(KBproperframe)}")

#It's not picking out the smallest frame here -- and it cannot: the proper model
#has |W|^2 = 9 worlds whichever agent is distinguished; only the cross-copy
#(skewed) edges move. Should it be b or c? Any agent works; the default picks the
#one with the FEWEST knowledge edges, ties broken by name (so `a` here, since all
#three are complete). Pass it explicitly to compare: KBframe.to_proper("b").

#print(f"{non_proper_worlds(BKproperframe)}")

Simp = to_simplicial(KBproperframe)

hasse.preview(Simp, "Simplicial Model")

#Hasse diagrams: hasse.preview(model, title) is the supported entry point -- it
#renders the face lattice (vertices, edges, triangles ordered by inclusion) to a
#temp file and opens it. (Earlier note here: "Can't get it to visualize hasse
#diagrams no matter what I try.")
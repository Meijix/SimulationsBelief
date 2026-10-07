"""The thesis seed three ways, plus bigger frames for ``to_proper``.

Story: the three-agent thesis example (same seed as examples3.py / poster
Example 3), then a 3-cycle seed, then a 4-agent, 6-world seed in which agent d
links {w1, w2, w3} to {w4, w5, w6}.

Route: KNOWLEDGE ONLY (S5). Each seed is closed with
``RelationalFrame.from_partial_s5`` and made proper with ``properness.to_proper``
(copies the worlds, skews one distinguished agent -- chosen by default, or passed
by hand as in ``to_proper(moreKF, "d")``). The KD45 frames (BF, moreBF) are built
only for contrast: properness is a property of the S5 knowledge relations, so
``to_proper`` on a belief frame raises (the commented call at the end). The
knowledge AND belief continuation is example5.py.

Run:  python examples/examples4.py   (opens one preview; uncomment the others to see
each stage).
"""

import os
import sys

# The examples live one level below the core modules. Put the repository root on
# sys.path so ``python examples/<script>.py`` works from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from relational_frame import RelationalFrame
from visualization import preview, show, to_dot, visualize
from properness import is_proper, non_proper_worlds
from knowledge_belief import KnowledgeBeliefFrame
from properness import explain, to_proper
from relational_frame import s5_closure

agents = {"a","b","c"}
worlds = {"w1","w2","w3"}
# Thesis seed. Under S5 every agent's class becomes {w1, w2, w3} (nobody can tell
# the worlds apart), so KF is not proper; under KD45 the same edges are pointed
# beliefs (a rules out w1, b is sure of w2, c is sure of w3).
frame = {"a": {("w1","w2"),("w1","w3")},"b": {("w1","w2"),("w3","w2")},"c": {("w1","w3"),("w2","w3")}}

BF = RelationalFrame.from_partial(agents, worlds, frame, make_serial=True)

KF = RelationalFrame.from_partial_s5(agents, worlds, frame)

#preview(BF, "Thesis KD45 Example")

#preview(KF, "Thesis S5 Example")

KF_proper = to_proper(KF)

#preview(KF_proper, "Thesis S5 Example Proper")

# A 3-cycle: each agent links one pair. S5 closure gives the classes a: {w1,w2},
# b: {w2,w3}, c: {w3,w1} plus singletons; at every world the three classes meet
# in that world alone, so KF2 is already proper and to_proper returns it as is.
frame2 = {"a": {("w1","w2")},"b": {("w2","w3")},"c": {("w3","w1")}}

KF2 = RelationalFrame.from_partial_s5(agents, worlds, frame2)

#preview(KF2, "Example 2")

KF2_proper = to_proper(KF2)

#preview(KF2_proper, "Example 2 proper")

moreagents = {"a","b","c","d"}

moreworlds = {"w1","w2","w3","w4","w5","w6"}

# d links each of w1, w2, w3 to each of w4, w5, w6; its S5 closure is the
# complete relation on all six worlds (d knows nothing), while a, b, c keep the
# class {w1, w2, w3} plus singletons. Still not proper at w1, w2, w3.
moreframe = {"a": {("w1","w2"),("w1","w3")},"b": {("w1","w2"),("w3","w2")},"c": {("w1","w3"),("w2","w3")},"d": {("w1","w4"),("w1","w5"),("w1","w6"),("w2","w4"),("w2","w5"),("w2","w6"),("w3","w4"),("w3","w5"),("w3","w6")}}

moreBF = RelationalFrame.from_partial(moreagents, moreworlds, moreframe, make_serial=True)

#preview (moreBF, "Example MoreBF")

moreKF = RelationalFrame.from_partial_s5(moreagents, moreworlds, moreframe)

#preview (moreKF, "Example MoreKF")

moreKF_proper = to_proper(moreKF)

#preview(moreKF_proper, "Example MoreKF_proper")

# Same construction with d as the distinguished agent. The result always has
# |W|^2 = 36 worlds; the choice only decides whose edges run across the copies
# (the default picks the agent with the fewest edges, here a, to keep drawings
# sparse).
dmoreKF_proper = to_proper(moreKF, "d")

preview(dmoreKF_proper, "Example dMoreKF_proper")

print("Good up to here!")

#BF_proper = to_proper(BF)

#preview(BF_proper, "Some Bullshit")

#The above threw me the error I wanted so that's good: to_proper refuses a KD45
#belief frame, because properness is defined on the S5 knowledge relations.

# The continuation (KnowledgeBeliefFrame.from_partial with both relations) is
# example5.py.
print("Now we move to knowledge AND belief")




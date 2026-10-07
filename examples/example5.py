"""Knowledge AND belief: ``KnowledgeBeliefFrame.from_partial`` with two seeds.

Story: two agents, three worlds. Alice's knowledge seed is a 3-cycle, so her
knowledge class is all of {w1, w2, w3} (she knows nothing); Bob only confuses
w2 with w3. Alice's belief seed rules out w1, so at w1 she holds a FALSE belief.

Route: knowledge + belief. R_a is closed under S5, then Q_a is closed INSIDE
R_a's classes (Q_a ⊆ R_a, constant on classes; KD45 comes for free). The frame
is not proper (Alice's single class), so ``to_proper`` copies the worlds and
skews one agent. ``frame3`` repeats the build with an EMPTY belief seed: under
the project's silence convention each agent then believes exactly what it knows
(Q_a = R_a), so belief and knowledge coincide.

Run:  python examples/example5.py   (prints the frames; opens one preview).
"""

import os
import sys
# The examples live one level below the core modules. Put the repository root on
# sys.path so ``python examples/<script>.py`` works from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_belief import KnowledgeBeliefFrame
from visualization import preview, show, to_dot, visualize

agents = {"alice", "bob"}
worlds = {"w1", "w2", "w3"}

# Knowledge seeds. Alice: w1 -> w2 -> w3 -> w1 closes under S5 to the complete
# relation (one class). Bob: only w2 ~ w3; w1 is a class on its own.
k = {"alice": {("w1", "w2"), ("w2", "w3"),("w3", "w1")}, "bob": {("w2", "w3")}}
# Belief seeds. Alice at w1 points to w2 and w3 -- she believes "not w1", false
# at w1; constancy on her class spreads that belief to w2 and w3 too. Bob at w2
# points to w3: within his class {w2, w3} he believes w3 (false at w2). Nothing
# is said about Bob at w1, so there Q_b = R_b (believe what you know).
b = {"alice": {("w1","w2"),("w1","w3")}, "bob": {("w2","w3")}}

#empty belief frame: `{}` is an empty dict, which from_partial iterates as "no
#edges". Silence about belief means Q_a = R_a on every class (believe exactly
#what you know): no opinion is invented, and KD45 holds because R_a is S5.
b3={"alice":{}, "bob": {}}


frame = KnowledgeBeliefFrame.from_partial(agents, worlds, k, b)
print(frame)
print(visualize(frame))
#preview(frame, "Example 5")

# Not proper: Alice's class is all three worlds, so e.g. w2 and w3 are related by
# both agents. to_proper -> 9 worlds; Q_a ⊆ R_a survives because the same skew
# is applied to both relations.
print(frame.is_proper())
frameproper = frame.to_proper()
print(frameproper)
print(visualize(frameproper))
#preview(frameproper, "Example 5 Proper")


# b2 is kept commented out: Bob's edge w1 -> w3 leaves his knowledge class {w1},
# so no Q_b ⊆ R_b can contain it and from_partial refuses the seed
# (trim_out_of_class=False by default).
#b2 = {"alice":{("w1", "w2"), ("w2","w3"),("w3","w1")},"bob":{("w1","w3")}}
#frame2 = KnowledgeBeliefFrame.from_partial(agents, worlds, k, b2)
#print(frame2)
#print(visualize(frame2))
#preview(frame2, "Example 6")

frame3 = KnowledgeBeliefFrame.from_partial(agents, worlds, k, b3)
print(frame3)
print(visualize(frame3))
preview(frame3, "Example 7")
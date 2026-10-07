"""Exploration notebook: three belief seeds on {w1, w2, w3} and the question
"which worlds are not proper?".

The seed `frame` is the thesis's three-agent example (thesis Fig. 1 / poster
Example 3 with w0, w1, w2 renamed w1, w2, w3): a rules out w1, b is sure of w2,
c is sure of w3, so at w1 everyone is wrong.

Routes exercised, in order:
    * belief only -- ``RelationalFrame.from_partial(..., make_serial=True)``
      closes each seed under KD45; properness is then UNDEFINED (it is a
      property of the S5 knowledge relations R_a), which is why RF3 raises;
    * knowledge only -- ``s5_closure`` / ``from_partial_s5``, then
      ``properness.to_proper`` (copies the worlds, skews one agent);
    * knowledge + belief -- ``KnowledgeBeliefFrame.from_partial`` with `frame`
      as the BELIEF seed and complete knowledge, then ``to_proper``
      (thesis Fig. 1 -> Fig. 2; the Fig. 3 ``to_simplicial`` call is left
      commented out -- thesis_example.py runs the full pipeline).

The first part keeps the original questions as written; the FINAL SECTION
answers them. Run:  python examples/examples3.py   (opens three previews and writes
outputs/ex3_*.png).
"""

import os
import sys

# The examples live one level below the core modules. Put the repository root on
# sys.path so ``python examples/<script>.py`` works from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from relational_frame import RelationalFrame
from visualization import preview, show, to_dot, visualize
from properness import is_proper, non_proper_worlds

agents = {"a","b","c"}
worlds = {"w1","w2","w3"}
# Read as belief: at w1, a considers w2 and w3; b points to w2 from w1 and w3;
# c points to w3 from w1 and w2. Nobody points at w1 from w1, so every belief
# is false there.
frame = {"a": {("w1","w2"),("w1","w3")},"b": {("w1","w2"),("w3","w2")},"c": {("w1","w3"),("w2","w3")}}

RF = RelationalFrame.from_partial(agents, worlds, frame, make_serial=True)

preview(RF, "Thesis KD45 Example")

print("Good up to here!")

# frame2: every agent has the symmetric pair w2 <-> w3 and says nothing about w1.
# KD45 closure gives the cluster {w2, w3}; make_serial adds w1 -> w1. The result
# happens to be reflexive, i.e. S5 as well, so properness IS well posed here:
# w2 and w3 are related by every agent, so they are the non-proper worlds.
frame2 = {"a": {("w3","w2"),("w2","w3")},"b": {("w3","w2"),("w2","w3")},"c": {("w3","w2"),("w2","w3")}}

RF2 = RelationalFrame.from_partial(agents, worlds, frame2, make_serial=True)

print(f"{is_proper(RF2)}")

print(f"{non_proper_worlds(RF2)}")

preview(RF2, "Example 2")

# frame3: a keeps her pointers from w1 (so w1 is not reflexive for her), b and c
# the symmetric pair. A genuine KD45 belief frame, not S5 -- hence the error below.
frame3 = {"a": {("w1","w2"),("w1","w3")},"b": {("w3","w2"),("w2","w3")},"c": {("w3","w2"),("w2","w3")}}

RF3 = RelationalFrame.from_partial(agents, worlds, frame3, make_serial=True)

# These two lines are question 1 ("should only spit out w2 and w3, no?"). They now
# raise instead of answering: RF3 is a KD45 belief frame, and properness is defined
# for knowledge. Wrapped so the rest of the file still runs -- see the FINAL SECTION.
try:
    print(f"{is_proper(RF3)}")

    print(f"{non_proper_worlds(RF3)}")
except ValueError as exc:
    print(f"ValueError: {exc}")

preview(RF3, "Example 3")

#frame3.1 = {"a": s5_closure(worlds, frame3),"b": s5_closure(worlds, frame3),"c": s5_closure(worlds, frame3)}

#RF3.1 = RelationalFrame(agents, worlds, frame3.1)

#In the above two lines, I am having an issue with the s5_closure function - what's my issue?


# ===========================================================================
# FINAL SECTION -- the same three questions, with corrections
# ===========================================================================
from knowledge_belief import KnowledgeBeliefFrame
from properness import explain, to_proper
from relational_frame import s5_closure
from simplicial import to_simplicial

print("\n" + "=" * 74)
print("FINAL SECTION -- corrected")
print("=" * 74)

# Problem 3 fixed by hand, one agent at a time:
frame3_1 = {a: s5_closure(worlds, frame3[a]) for a in agents}
RF3_1 = RelationalFrame(agents, worlds, frame3_1)

# ...or in a single call, which is what that dict comprehension is for:
RF31 = RelationalFrame.from_partial_s5(agents, worlds, frame3)

# Check that the by-hand closure and the single call give the same relations.
assert RF31.relations == RF3_1.relations

print("\nCompleted S5 relations:")
for a in sorted(agents):
    print(f"  R_{a}: " + "  ".join(
        f"{w}->{sorted(RF31.successors(a, w))}" for w in sorted(worlds)))
print(f"  {explain(RF31)}")

# S5 so properness is well posed. to_proper copies+skews until jointly unique.
RF31_proper = to_proper(RF31)
print(f"\nto_proper(RF31) -> {type(RF31_proper).__name__}, "
      f"{len(RF31.worlds)} -> {len(RF31_proper.worlds)} worlds, "
      f"proper? {RF31_proper.is_proper()}")

show(RF31, "ex3_rf31_s5", "frame3 closed under S5 (knowledge, not proper)")
show(RF31_proper, "ex3_rf31_proper", "after to_proper (bisimilar, proper)")
print("  Figures: outputs/ex3_rf31_s5.png, outputs/ex3_rf31_proper.png")

# Problem 4: agent a collapsed to the complete relation. Its belief relation
# excluded w1 from w1 -- a FALSE BELIEF -- and reflexivity destroyed exactly that.

# Original question: when a model has belief and knowledge relations for different
# agents, and we apply the S5 closure to the BELIEF relations in order to make the
# model proper, aren't we breaking something there? (Yes -- see the print below.)
print(f"\n  agent a: Q_a(w1) = {sorted(RF3.successors('a', 'w1'))}"
      f"  ->  R_a(w1) = {sorted(RF3_1.successors('a', 'w1'))}"
      f"   ({len(frame3_1['a'])}/{len(worlds) ** 2} edges, collapsed)")
print("  There is no KD45 -> S5 conversion. Carry BOTH relations instead:")


# --- Questions 1 & 2: ask properness of a model that has knowledge ------- #
# `frame` from line 9 is used as the BELIEF seed, unchanged. Knowledge is seeded
# so it closes to the complete relation (nobody can tell the worlds apart).
# belief_closure fits Q_a inside R_a's classes, so all four knowledge/belief
# conditions hold by construction -- no KD45 closure involved.
kb = KnowledgeBeliefFrame.from_partial(
    agents,
    worlds,
    knowledge={a: {("w1", "w2"), ("w1", "w3")} for a in agents},
    belief=frame,
)

print(f"\nKnowledgeBeliefFrame.from_partial -> valid? {kb.is_valid()}")
for a in sorted(agents):
    print(f"  at w1: {a} KNOWS {sorted(kb.knows(a, 'w1'))} "
          f"but BELIEVES {sorted(kb.believes(a, 'w1'))}")
print("  w1 is the real world and nobody believes it possible: false belief for all.")

# Properness is now well posed, because it is asked of the KNOWLEDGE relations.
print(f"\n  kb.is_proper() = {kb.is_proper()}")
print(f"  {kb.properness_violations()[0]}")

kb_proper = kb.to_proper()
print(f"\n  to_proper() -> {type(kb_proper).__name__}, {len(kb_proper.worlds)} worlds, "
      f"proper? {kb_proper.is_proper()}, valid? {kb_proper.is_valid()}")
print(f"  Q_a subset R_a preserved? " + str(all(
    kb_proper.belief.relations[a] <= kb_proper.knowledge.relations[a] for a in agents)))

# Fig.3 would be to_simplicial(kb_proper); left commented out in this notebook
# (thesis_example.py and "Example for Poster 3.py" run the simplicial step).
#sm = to_simplicial(kb_proper)
#print(f"\n  to_simplicial() -> {sm!r}, valid? {sm.is_valid()}")

show(kb, "ex3_final_kb", "frame as belief + complete knowledge (Fig.1)")
show(kb_proper, "ex3_final_proper", "after to_proper (Fig.2)")
#show(sm, "ex3_final_simplicial", "simplicial belief model (Fig.3)")

print("\nFig.1 -> Fig.2 -> Fig.3, starting from `frame` on line 9.")
print("Figures in outputs/ex3_final_*.png")

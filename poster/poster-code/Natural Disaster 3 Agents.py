# -*- coding: utf-8 -*-
"""Natural-disaster example with THREE agents.

Proof of concept for the poster "La geometría de una creencia falsa… y por qué
importa" (Coloquio de Lenguajes, UNAM 2026): with two agents the facets are
edges and the complex degenerates into a broken line; with three agents the
facets are triangles and the geometric drawing is finally two-dimensional.

    python "poster/poster-code/Natural Disaster 3 Agents.py"

The story
---------
Ana coordinates from the base, Beto rides with the brigade and Carla is at the
hospital. Ana transmits by radio "the road is clear". The channel can fail with
each of them separately, so there are four worlds:

    R    Ana sent and both received it
    RN   Ana sent, Beto received it, Carla did NOT
    NN   Ana sent and neither received it
    nS   Ana did not send (because the road is not clear)

Whoever received nothing assumes nothing was sent, that is, assumes the road is
NOT clear. That is the false belief.

What the story gains with the third agent
-----------------------------------------
In RN two things happen at once, and the second cannot be told with two
agents:

    1. Carla believes the road is not clear, and she is wrong.
    2. Beto KNOWS the road is clear, but does not know whether the hospital
       found out: he cannot tell R from RN.

That is: the hospital does not find out, and the brigade does not know that the
hospital did not find out. That is higher-order belief, and it does not fit in
the two-agent example.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))      # poster/poster-code/
POSTER = os.path.dirname(HERE)                          # poster/
ROOT = os.path.dirname(POSTER)                          # the repository root
sys.path.insert(0, ROOT)   # the core modules live at the root

from knowledge_belief import KnowledgeBeliefFrame
from simplicial import to_simplicial
import visualization
import hasse

# --------------------------------------------------------------- the model
agents = {"a", "b", "c"}
worlds = {"R", "RN", "NN", "nS"}

# Knowledge: what each agent can tell apart. One chain per class is enough:
# from_partial closes the seeds under S5 into the knowledge relation R_a.
#   a (Ana)   knows whether she sent, not who received it -> {R,RN,NN} | {nS}
#   b (Beto)  knows whether HE received                   -> {R,RN}    | {NN,nS}
#   c (Carla) knows whether SHE received                  -> {R}       | {RN,NN,nS}
knowledge = {
    "a": {("R", "RN"), ("RN", "NN")},
    "b": {("R", "RN"), ("NN", "nS")},
    "c": {("RN", "NN"), ("NN", "nS")},
}

# Belief: whoever received nothing assumes nothing was sent. Seeds are closed
# into Q_a inside R_a's classes; a silent agent believes what she knows.
#   Carla, who received nothing in RN, believes she is in nS -> FALSE belief in RN
#   Beto,  who received nothing in NN, believes he is in nS
belief = {
    "a": set(),
    "b": {("NN", "nS")},
    "c": {("RN", "nS")},
}

KB = KnowledgeBeliefFrame.from_partial(agents, worlds, knowledge, belief)

print("=" * 70)
print("MODELO RELACIONAL")
print("=" * 70)
print("is_valid :", KB.is_valid())
for v in KB.violations():
    print("   !", v)
print("is_proper:", KB.is_proper())
for v in KB.properness_violations():
    print("   !", v)

print("\nclases de conocimiento (lo que cada quien NO distingue):")
for ag in sorted(agents):
    clases = sorted({tuple(sorted(KB.knows(ag, w))) for w in sorted(worlds)})
    print(f"   {ag}: {clases}")

print("\ncreencia (a que mundos apunta Q_x desde cada mundo):")
for ag in sorted(agents):
    fila = ", ".join(f"{w}->{sorted(KB.believes(ag, w))}" for w in sorted(worlds))
    print(f"   {ag}: {fila}")

# ------------------------------------------------------------- the complex
Simp = to_simplicial(KB)

print("\n" + "=" * 70)
print("COMPLEJO SIMPLICIAL")
print("=" * 70)
print(Simp.describe())
print("is_valid :", Simp.is_valid())

# The false belief, located on the complex: in the real world RN, Carla's
# belief subcomplex S_c does NOT contain the facet of RN.
REAL = "RN"
for ag in sorted(agents):
    facetas = Simp.believes_facets(ag, Simp.facet_of(REAL)) \
        if hasattr(Simp, "facet_of") else None
    print(f"   {ag} en {REAL}: cree posibles ->",
          sorted(str(f) for f in facetas) if facetas is not None else "n/d")

# --------------------------------------------------------------- the figures
OUT = os.path.join(POSTER, "outputs")   # next to the other poster figures
os.makedirs(OUT, exist_ok=True)

VAL = {"C": {"R", "RN", "NN"}}   # the road IS clear except in nS

print("\n" + "=" * 70)
print("FIGURAS")
print("=" * 70)
print(visualization.show(
    KB, "d3_relacional",
    title="Desastre con tres agentes — modelo relacional K+B",
    output_dir=OUT, valuation=VAL,
))
print(visualization.show(
    Simp, "d3_geometrico",
    title="Desastre con tres agentes — complejo simplicial",
    output_dir=OUT, valuation=VAL,
))
print(hasse.show(
    Simp, "d3_reticula",
    title="Desastre con tres agentes — retícula de caras",
    output_dir=OUT,
))

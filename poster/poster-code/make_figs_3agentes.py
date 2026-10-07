# -*- coding: utf-8 -*-
"""Build the poster figures for the disaster example with THREE agents.

Figures for the poster "La geometría de una creencia falsa… y por qué
importa" (Coloquio de Lenguajes, UNAM 2026), built on the natural-disaster
example of Sink's simplicial belief models: facets are worlds, vertices are
agent perspectives, and a false belief is a facet outside the agent's belief
subcomplex S_a.

Same model as "poster/Natural Disaster 3 Agents.py", but here we also build
the two states of the announcement ¬C that the poster's retraction section
needs:

    antes    v(C) = {R, RN, NN}   the road was reported clear
    despues  v(C) = {nS}          ¬C arrives and the values flip

The shape of the complex does NOT change between the two states: the only
thing that changes is the literal each vertex observes. That is exactly what
the poster claims.

    python poster/poster-code/make_figs_3agentes.py

Requires Graphviz (``dot``) on the PATH and the dependencies in requirements.txt.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))      # poster/poster-code/
POSTER = os.path.dirname(HERE)                          # poster/
ROOT = os.path.dirname(POSTER)                          # the repository root
sys.path.insert(0, ROOT)   # the core modules live at the root
sys.path.insert(1, HERE)   # revision.py sits next to this script (needed under runpy)

from knowledge_belief import KnowledgeBeliefFrame
from simplicial import to_simplicial
from assignment import assignment_from_model, nu_violations
from semantics import holds_kripke
import visualization
import hasse

# --------------------------------------------------------------- the model
agents = {"a", "b", "c"}
worlds = {"R", "RN", "NN", "nS"}

# Knowledge: what each agent can tell apart. from_partial closes each seed into
# an S5 relation R_a, so listing one chain per class is enough.
#   a (Ana)   knows whether she sent, not who received it -> {R,RN,NN} | {nS}
#   b (Beto)  knows whether HE received                   -> {R,RN}    | {NN,nS}
#   c (Carla) knows whether SHE received                  -> {R}       | {RN,NN,nS}
knowledge = {
    "a": {("R", "RN"), ("RN", "NN")},
    "b": {("R", "RN"), ("NN", "nS")},
    "c": {("RN", "NN"), ("NN", "nS")},
}
# Belief: whoever received nothing assumes nothing was sent. Each seed is
# closed into Q_a inside the knowledge class; where an agent is silent (Ana
# everywhere, Beto and Carla in the worlds where they did receive) the default
# is Q_a = R_a, i.e. she believes exactly what she knows.
belief = {
    "a": set(),
    "b": {("NN", "nS")},
    "c": {("RN", "nS")},
}

KB = KnowledgeBeliefFrame.from_partial(agents, worlds, knowledge, belief)
Simp = to_simplicial(KB)

print("is_valid :", KB.is_valid())
print("is_proper:", KB.is_proper())
print(Simp.describe())

OUT = os.path.join(POSTER, "outputs")   # the committed poster figures

# --------------------------------------------- the two states of the announcement
VALUACIONES = {
    "antes":   {"C": {"R", "RN", "NN"}},   # C as sent over the radio
    "despues": {"C": {"nS"}},              # after ¬C: values flipped
}
FORMULAS = {
    "C":      ("atom", "C"),
    "B_c C":  ("B", "c", ("atom", "C")),
    "B_c ¬C": ("B", "c", ("not", ("atom", "C"))),
    "B_b C":  ("B", "b", ("atom", "C")),
}

for etapa, val in VALUACIONES.items():
    print(f"\n== {etapa} del anuncio ¬C: v(C) = {sorted(val['C'])} ==")
    print(visualization.show(
        KB, f"d3_{etapa}_relacional",
        title=f"Desastre con tres agentes — {etapa} de ¬C (modelo relacional K+B)",
        output_dir=OUT, valuation=val,
    ))
    print(visualization.show(
        Simp, f"d3_{etapa}_geometrico",
        title=f"Desastre con tres agentes — {etapa} de ¬C (complejo simplicial)",
        output_dir=OUT, valuation=val,
    ))
    asg = assignment_from_model(Simp, val)
    print("  violaciones NU:", nu_violations(Simp, asg, val) or "ninguna")
    for w in ("R", "RN", "NN", "nS"):
        fila = "  ".join(
            f"{k}={'T' if holds_kripke(KB, val, w, f) else 'F'}"
            for k, f in FORMULAS.items()
        )
        print(f"  {w:>3}: {fila}")

# ------------------------------------------ the belief revision
# Announcing ¬C is no use here: it is false in the real world, so it would have
# to delete the very world the agents are in. The announcement that DOES do
# geometric work is S = "Ana did send": true in R, RN and NN, it kills exactly
# nS, the only world Carla believed possible from RN. There her belief loses
# its ground (Q_c must stay serial) and the revision rule R_c has to decide
# where it goes: among the surviving facets with the same c-vertex, the one
# sharing the most vertices with the lost facet.
import revision as rev

S_TRUE = {"R", "RN", "NN"}          # where "Ana did send" holds
CREE_C = "nS"                       # what Carla believed from the real world RN

carla = rev.revise_after_announcement(Simp, "c", CREE_C, S_TRUE)

print("\n" + "=" * 70)
print("REVISION DE CREENCIAS  ·  anuncio S, verdadero en", sorted(S_TRUE))
print("=" * 70)
print(rev.describe(Simp, carla))
print("  decidida sin empate:", carla.is_decided())

print(visualization.show(
    Simp, "d3_revision",
    title="Desastre con tres agentes — Carla revisa tras el anuncio S",
    output_dir=OUT, valuation=VALUACIONES["antes"], revision=carla,
))

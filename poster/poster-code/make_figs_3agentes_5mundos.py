# -*- coding: utf-8 -*-
"""Variant of the disaster example with THREE agents and FIVE worlds.

Figures for the poster "La geometría de una creencia falsa… y por qué
importa" (Coloquio de Lenguajes, UNAM 2026), built on the natural-disaster
example of Sink's simplicial belief models: facets are worlds, vertices are
agent perspectives, and a false belief is a facet outside the agent's belief
subcomplex S_a.

The four-world model left out NR, the world where the message reaches only
Carla. If the channel fails for each receiver independently --which is what
the poster text says-- all four combinations have to exist:

    RR  both received             RN  only Beto
    NR  only Carla                NN  neither
    nS  Ana never sent

R is also renamed RR here, so the label follows the two-letter convention
(first letter = Beto, second = Carla). Output goes to ``_intermedios/`` because
this variant is a check on the story, not one of the figures the poster uses.

    python poster/poster-code/make_figs_3agentes_5mundos.py
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
import revision as rev

# --------------------------------------------------------------- the model
agents = {"a", "b", "c"}
worlds = {"RR", "RN", "NR", "NN", "nS"}

# Knowledge: what each agent can tell apart (seeds closed under S5 into R_a).
#   a (Ana)   knows whether she sent, not who received it
#             -> {RR,RN,NR,NN} | {nS}
#   b (Beto)  knows whether HE received     -> {RR,RN}  | {NR,NN,nS}
#   c (Carla) knows whether SHE received    -> {RR,NR}  | {RN,NN,nS}
knowledge = {
    "a": {("RR", "RN"), ("RN", "NR"), ("NR", "NN")},
    "b": {("RR", "RN"), ("NR", "NN"), ("NN", "nS")},
    "c": {("RR", "NR"), ("RN", "NN"), ("NN", "nS")},
}
# Belief: whoever received nothing assumes nothing was sent. Beto's seed now
# starts at NR and Carla's at RN: the world where only she missed the message.
belief = {
    "a": set(),
    "b": {("NR", "nS")},
    "c": {("RN", "nS")},
}

KB = KnowledgeBeliefFrame.from_partial(agents, worlds, knowledge, belief)
Simp = to_simplicial(KB)

print("is_valid :", KB.is_valid())
print("is_proper:", KB.is_proper())
print(Simp.describe())

OUT = os.path.join(POSTER, "_intermedios")   # a check, not a poster figure

VAL = {"C": {"RR", "RN", "NR", "NN"}}   # "the road is clear" was sent
FORMULAS = {
    "C":      ("atom", "C"),
    "B_c C":  ("B", "c", ("atom", "C")),
    "B_c ~C": ("B", "c", ("not", ("atom", "C"))),
    "B_b C":  ("B", "b", ("atom", "C")),
}

print(visualization.show(
    KB, "d5_relacional",
    title="Desastre con tres agentes y cinco mundos (modelo relacional K+B)",
    output_dir=OUT, valuation=VAL,
))
print(visualization.show(
    Simp, "d5_geometrico",
    title="Desastre con tres agentes y cinco mundos (complejo simplicial)",
    output_dir=OUT, valuation=VAL,
))

asg = assignment_from_model(Simp, VAL)
print("violaciones NU:", nu_violations(Simp, asg, VAL) or "ninguna")
for w in ("RR", "RN", "NR", "NN", "nS"):
    fila = "  ".join(
        f"{k}={'T' if holds_kripke(KB, VAL, w, f) else 'F'}"
        for k, f in FORMULAS.items()
    )
    print(f"  {w:>3}: {fila}")

# ------------------------------------------ the belief revision
# Same announcement as in the four-world script: S = "Ana did send" kills
# exactly nS, the facet Carla believed from RN, and the rule R_c picks the
# surviving facet with her vertex that overlaps the lost one the most.
S_TRUE = {"RR", "RN", "NR", "NN"}   # "Ana did send"
CREE_C = "nS"                       # what Carla believed from the real world RN

carla = rev.revise_after_announcement(Simp, "c", CREE_C, S_TRUE)

print("\n" + "=" * 70)
print("REVISION DE CREENCIAS  ·  anuncio S, verdadero en", sorted(S_TRUE))
print("=" * 70)
print(rev.describe(Simp, carla))
print("  decidida sin empate:", carla.is_decided())

print(visualization.show(
    Simp, "d5_revision",
    title="Cinco mundos — Carla revisa tras el anuncio S",
    output_dir=OUT, valuation=VAL, revision=carla,
))

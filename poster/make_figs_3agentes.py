# -*- coding: utf-8 -*-
"""Genera las figuras del cartel para el ejemplo de desastre con TRES agentes.

Mismo modelo que "poster/Natural Disaster 3 Agents.py", pero aqui se generan
ademas los dos estados del anuncio ¬C que pide la seccion del desmentido:

    antes    v(C) = {R, RN, NN}   el camino se reporto libre
    despues  v(C) = {nS}          llega ¬C y los valores se invierten

La forma del complejo NO cambia entre los dos estados: lo unico que cambia es
el literal que observa cada vertice. Eso es justo lo que el cartel afirma.

    python poster/make_figs_3agentes.py

Requiere Graphviz (``dot``) en el PATH y las dependencias de requirements.txt.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from knowledge_belief import KnowledgeBeliefFrame
from simplicial import to_simplicial
from assignment import assignment_from_model, nu_violations
from semantics import holds_kripke
import visualization
import hasse

# --------------------------------------------------------------- el modelo
agents = {"a", "b", "c"}
worlds = {"R", "RN", "NN", "nS"}

#   a (Ana)   sabe si transmitio, no sabe a quien le llego -> {R,RN,NN} | {nS}
#   b (Beto)  sabe si el recibio                           -> {R,RN}    | {NN,nS}
#   c (Carla) sabe si ella recibio                         -> {R}       | {RN,NN,nS}
knowledge = {
    "a": {("R", "RN"), ("RN", "NN")},
    "b": {("R", "RN"), ("NN", "nS")},
    "c": {("RN", "NN"), ("NN", "nS")},
}
# Quien no recibio nada supone que no se transmitio.
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

OUT = HERE

# --------------------------------------------- los dos estados del anuncio
VALUACIONES = {
    "antes":   {"C": {"R", "RN", "NN"}},   # C tal como se mando por radio
    "despues": {"C": {"nS"}},              # tras ¬C: valores invertidos
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

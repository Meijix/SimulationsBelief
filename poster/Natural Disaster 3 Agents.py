# -*- coding: utf-8 -*-
"""Ejemplo de desastre natural con TRES agentes.

Prueba de concepto para el cartel: con dos agentes las facetas son aristas y
el complejo degenera en una linea quebrada; con tres agentes las facetas son
triangulos y el dibujo geometrico por fin es bidimensional.

    python "Natural Disaster 3 Agents.py"

La historia
-----------
Ana coordina desde la base, Beto va en la brigada y Carla esta en el hospital.
Ana transmite por radio "el camino esta libre". El canal puede fallar con cada
uno por separado, asi que hay cuatro mundos:

    R    Ana transmitio y les llego a los dos
    RN   Ana transmitio, le llego a Beto, NO a Carla
    NN   Ana transmitio y no le llego a ninguno
    nS   Ana no transmitio (porque el camino no esta libre)

Quien no recibio nada supone que no se transmitio, es decir, supone que el
camino NO esta libre. Esa es la creencia falsa.

Lo que gana la historia con el tercer agente
--------------------------------------------
En RN pasan dos cosas a la vez, y la segunda es imposible de contar con dos
agentes:

    1. Carla cree que el camino no esta libre, y se equivoca.
    2. Beto SABE que el camino esta libre, pero no sabe si el hospital se
       entero: no distingue R de RN.

O sea: el hospital no se entera, y la brigada no sabe que el hospital no se
entero. Eso es creencia de orden superior y no cabe en el ejemplo de dos
agentes.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from knowledge_belief import KnowledgeBeliefFrame
from simplicial import to_simplicial
import visualization
import hasse

# --------------------------------------------------------------- el modelo
agents = {"a", "b", "c"}
worlds = {"R", "RN", "NN", "nS"}

# Conocimiento: que distingue cada quien.
#   a (Ana)   sabe si transmitio, no sabe a quien le llego -> {R,RN,NN} | {nS}
#   b (Beto)  sabe si el recibio                           -> {R,RN}    | {NN,nS}
#   c (Carla) sabe si ella recibio                         -> {R}       | {RN,NN,nS}
knowledge = {
    "a": {("R", "RN"), ("RN", "NN")},
    "b": {("R", "RN"), ("NN", "nS")},
    "c": {("RN", "NN"), ("NN", "nS")},
}

# Creencia: quien no recibio nada supone que no se transmitio.
#   Carla, que no recibio en RN, cree que esta en nS  -> creencia FALSA en RN
#   Beto,  que no recibio en NN, cree que esta en nS
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

# ------------------------------------------------------------- el complejo
Simp = to_simplicial(KB)

print("\n" + "=" * 70)
print("COMPLEJO SIMPLICIAL")
print("=" * 70)
print(Simp.describe())
print("is_valid :", Simp.is_valid())

# La creencia falsa, localizada sobre el complejo: en el mundo real RN, el
# subcomplejo de creencia de Carla NO contiene la faceta de RN.
REAL = "RN"
for ag in sorted(agents):
    facetas = Simp.believes_facets(ag, Simp.facet_of(REAL)) \
        if hasattr(Simp, "facet_of") else None
    print(f"   {ag} en {REAL}: cree posibles ->",
          sorted(str(f) for f in facetas) if facetas is not None else "n/d")

# --------------------------------------------------------------- las figuras
OUT = os.path.join(HERE, "poster", "tres_agentes")
os.makedirs(OUT, exist_ok=True)

VAL = {"C": {"R", "RN", "NN"}}   # el camino SI esta libre salvo en nS

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

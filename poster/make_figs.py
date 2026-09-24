# -*- coding: utf-8 -*-
"""Genera las figuras del cartel a partir del ejemplo de desastre natural.

Las dos primeras figuras son la salida real de la herramienta: se construyen
llamando a ``visualization.show`` y ``hasse.show`` sobre el mismo modelo que
arma "Natural Disaster Example.py". La tercera es un esquema dibujado a mano,
porque la revision de creencias todavia no esta implementada.

    python poster/make_figs.py

Requiere Graphviz (``dot``) en el PATH y las dependencias de requirements.txt.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from knowledge_belief import KnowledgeBeliefFrame
from simplicial import to_simplicial
import visualization
import hasse

# --- el modelo del ejemplo (identico a "Natural Disaster Example.py") -------
agents = {"a", "b"}
worlds = {"nS", "SnR", "SR"}
frameseed = {"a": {("SnR", "SR"), ("SR", "SnR")},
             "b": {("SnR", "nS")}}

KBframe = KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)
Simp = to_simplicial(KBframe)

print("is_valid :", KBframe.is_valid())
print("is_proper:", KnowledgeBeliefFrame.is_proper(KBframe))

OUT = HERE

# --- figura 1: modelo relacional de conocimiento y creencia ----------------
print(visualization.show(
    KBframe, "desastre_relacional",
    title="Desastre natural — modelo relacional K+B",
    output_dir=OUT,
))

# --- figura 2: el complejo simplicial, dibujado como reticula de caras -----
# La reticula de caras es la forma en que el articulo dibuja los modelos
# simpliciales, y ademas es legible con dos agentes: con |A| = 2 las facetas
# son aristas y el dibujo geometrico de visualization.show degenera en una
# linea recta.
print(hasse.show(
    Simp, "desastre_simplicial",
    title="Desastre natural — complejo simplicial (reticula de caras)",
    output_dir=OUT,
))

# --- figura 2g: el complejo simplicial "normal" (dibujo geometrico) ---------
# Con dos agentes cada faceta es una arista, asi que el complejo es el camino
# b0 - a0 - b1 - a1 (SR, SnR, nS): visualization.show lo dibuja horizontal,
# con cada faceta rellena del color de su firma de creencia y nombrada por su
# mundo. Complementa a la reticula de caras de la figura 2.
print(visualization.show(
    Simp, "desastre_geometrico",
    title="Desastre natural — complejo simplicial",
    output_dir=OUT,
))

# --- figuras 1v/2v: los mismos modelos CON la valuacion de C ----------------
# El ejemplo habla de un atomo, C = "la carretera esta libre", y de como el
# anuncio de ¬C "simplemente invierte los valores de C". Se generan los dos
# estados: ANTES (v(C) = {SnR, SR}: en los mundos donde Alice manda C la
# carretera se reporta libre; en nS no se mando nada, C es falsa) y DESPUES
# del anuncio ¬C (v(C) = {nS}: los valores invertidos). En cada estado Barb
# tiene una creencia falsa en SnR: antes cree ¬C siendo C verdadera (solo ve
# nS, donde no llego nada); despues cree C siendo C falsa.
from assignment import assignment_from_model, nu_violations
from semantics import holds_kripke

VALUACIONES = {
    "antes":   {"C": {"SnR", "SR"}},   # C tal como se mando por radio
    "despues": {"C": {"nS"}},          # tras el anuncio ¬C: valores invertidos
}
FORMULAS = {
    "C":       ("atom", "C"),
    "B_b C":   ("B", "b", ("atom", "C")),
    "B_b ¬C":  ("B", "b", ("not", ("atom", "C"))),
    "B_a C":   ("B", "a", ("atom", "C")),
}
for etapa, val in VALUACIONES.items():
    print(f"\n== {etapa} del anuncio ¬C: v(C) = {sorted(val['C'])} ==")
    # Figura relacional: los mundos llevan sus literales (C / ¬C) como
    # segunda linea de la etiqueta; misma funcion que la figura 1.
    print(visualization.show(
        KBframe, f"desastre_{etapa}_relacional",
        title=f"Desastre natural — {etapa} de ¬C (modelo relacional K+B)",
        output_dir=OUT, valuation=val,
    ))
    # Figura simplicial: la valuacion de mundos induce la asignacion de
    # vertices (lo que cada perspectiva SABE de C: 1 = C, 0 = ¬C, 2 = nada),
    # y cada cara del reticulo muestra los literales que sus vertices observan.
    asg = assignment_from_model(Simp, val)
    # Dibujo geometrico con la valuacion: cada vertice muestra el literal que
    # observa (C / ¬C; nada si no sabe), cada faceta su mundo.
    print(visualization.show(
        Simp, f"desastre_{etapa}_geometrico",
        title=f"Desastre natural — {etapa} de ¬C (complejo simplicial)",
        output_dir=OUT, valuation=val,
    ))
    print(hasse.show(
        Simp, f"desastre_{etapa}_simplicial",
        title=f"Desastre natural — {etapa} de ¬C (complejo simplicial)",
        output_dir=OUT, assignment=asg,
    ))
    # NU: una verdad que ningun agente observa no es representable por
    # vertices. Aqui no ocurre (Alice siempre sabe el valor de C en su clase).
    gaps = nu_violations(Simp, asg, val)
    print("  violaciones NU:", gaps if gaps else "ninguna")
    # La creencia falsa de Barb, comprobada mundo por mundo.
    for w in ("nS", "SnR", "SR"):
        fila = "  ".join(f"{k}={'T' if holds_kripke(KBframe, val, w, f) else 'F'}"
                         for k, f in FORMULAS.items())
        print(f"  {w:>4}: {fila}")

# --- figura 3: esquema de la revision de creencias -------------------------
# Regla especificada en el articulo, aun no implementada: esta figura es un
# esquema, no la salida del codigo.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle

NAVY, TXT, MUT = "#0e2140", "#1a2233", "#5a6478"
A, B, RED, GRN, PALE = "#1971c2", "#e8590c", "#c0432b", "#1b5e3f", "#cbd3de"
XMAX = 994 / 540.0                      # proporcion del hueco en el cartel

fig, ax = plt.subplots(figsize=(9.94, 5.40), dpi=170)
ax.set_xlim(0, XMAX); ax.set_ylim(0, 1)
ax.set_aspect("equal"); ax.axis("off")
fig.subplots_adjust(0, 0, 1, 1)


def dot(x, y, r, label, fc, fs):
    ax.add_patch(Circle((x, y), r, facecolor=fc, edgecolor="white", lw=2.2, zorder=7))
    ax.text(x, y, label, ha="center", va="center", fontsize=fs, color="white",
            weight="bold", zorder=8)


for x0, caption, before in [(0.10, "antes de ¬C", True),
                            (1.02, "después de ¬C", False)]:
    ax.text(x0 + 0.34, 0.93, caption, ha="center", fontsize=15,
            color=NAVY, weight="bold")
    p = {"b1": (x0 + 0.04, 0.58), "a1": (x0 + 0.26, 0.74),
         "b2": (x0 + 0.46, 0.58), "a2": (x0 + 0.66, 0.74)}
    edges = [("b1", "a1", GRN if before else PALE),
             ("a1", "b2", RED if before else GRN),
             ("b2", "a2", GRN if before else PALE)]
    for u, v, col in edges:
        (x1, y1), (x2, y2) = p[u], p[v]
        ax.plot([x1, x2], [y1, y2], color=col, lw=15, alpha=0.30,
                solid_capstyle="round", zorder=1)
        ax.plot([x1, x2], [y1, y2], color=col, lw=1.8, zorder=2)
    for k, (x, y) in p.items():
        dot(x, y, 0.040, k[0], A if k[0] == "a" else B, 11)

ax.add_patch(FancyArrowPatch((0.83, 0.66), (0.95, 0.66), arrowstyle="-|>",
                             mutation_scale=24, lw=3, color=NAVY))
ax.text(0.89, 0.715, "¬C", ha="center", fontsize=15, color=NAVY, weight="bold")

ax.text(0.44, 0.40,
        "Barb cree que no se mandó nada.\nLlega ¬C y ese mundo queda descartado.",
        ha="center", va="top", fontsize=12, color=TXT, linespacing=1.5)
ax.text(1.36, 0.40,
        "No se queda sin mundos: adopta la faceta que\ncomparte más vértices con la que perdió.",
        ha="center", va="top", fontsize=12, color=TXT, linespacing=1.5)
ax.text(XMAX / 2, 0.135,
        "Rₐ(X)  =  las facetas Y con πₐ(Y) = πₐ(X)  que maximizan  |Y ∩ X|",
        ha="center", fontsize=14, color=NAVY)

path3 = os.path.join(OUT, "desastre_revision.png")
fig.savefig(path3, facecolor="white")
plt.close(fig)
print(path3)

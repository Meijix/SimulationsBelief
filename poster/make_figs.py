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

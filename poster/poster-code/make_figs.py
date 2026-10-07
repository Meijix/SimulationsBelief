# -*- coding: utf-8 -*-
"""Build the poster figures from the two-agent natural-disaster example.

Figures for the poster "La geometría de una creencia falsa… y por qué
importa" (Coloquio de Lenguajes, UNAM 2026), built on the natural-disaster
example of Sink's simplicial belief models: facets are worlds, vertices are
agent perspectives, and a false belief is a facet outside the agent's belief
subcomplex S_a.

The first two figures are the tool's real output: they come from calling
``visualization.show`` and ``hasse.show`` on the same model that
"Natural Disaster Example.py" builds. The third is a hand-drawn schematic,
because belief revision was not implemented in the tool when it was made.

    python poster/poster-code/make_figs.py

Requires Graphviz (``dot``) on the PATH and the dependencies in requirements.txt.
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

# --- the example model (identical to "Natural Disaster Example.py") ---------
# Alice (a) knows whether she sent but not whether it arrived; Barb (b) knows
# whether she received, and with nothing received cannot tell nS from SnR.
# The same seed feeds both relations: from_partial closes R_a under S5 and Q_a
# inside R_a's classes (KD45 by default), so Barb's one-way arrow SnR -> nS
# becomes a belief that is false in SnR. The model is proper, so it translates
# to a simplicial complex directly.
agents = {"a", "b"}
worlds = {"nS", "SnR", "SR"}
frameseed = {"a": {("SnR", "SR"), ("SR", "SnR")},
             "b": {("SnR", "nS")}}

KBframe = KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)
Simp = to_simplicial(KBframe)

print("is_valid :", KBframe.is_valid())
print("is_proper:", KnowledgeBeliefFrame.is_proper(KBframe))

OUT = os.path.join(POSTER, "outputs")   # the committed poster figures

# --- figure 1: relational model of knowledge and belief ----------------------
print(visualization.show(
    KBframe, "desastre_relacional",
    title="Desastre natural — modelo relacional K+B",
    output_dir=OUT,
))

# --- figure 2: the simplicial complex, drawn as a face lattice ---------------
# The face lattice is how the paper draws simplicial models, and it stays
# readable with two agents: with |A| = 2 the facets are edges, so the geometric
# drawing of visualization.show degenerates into a straight line.
print(hasse.show(
    Simp, "desastre_hasse",
    title="Desastre natural — complejo simplicial (reticula de caras)",
    output_dir=OUT,
))

# --- figure 2c: the complex via GRAPHVIZ (leaves an editable .dot) -----------
# visualization.show sends simplicial models to matplotlib, which draws filled
# simplices but leaves no editable source: no .dot next to the .png.
# engine="dot" routes them through Graphviz. With two agents each facet has two
# vertices, so it IS an edge and the graph represents the complex without loss.
print(visualization.show(
    Simp, "desastre_complejo",
    title="Desastre natural — complejo simplicial",
    output_dir=OUT, engine="dot",
))

# --- figure 2g: the "ordinary" simplicial complex (geometric drawing) --------
# With two agents each facet is an edge, so the complex is the path
# b0 - a0 - b1 - a1 (SR, SnR, nS): visualization.show draws it horizontally,
# each facet filled with the colour of its belief signature and labelled with
# its world. It complements the face lattice of figure 2.
print(visualization.show(
    Simp, "desastre_geometrico",
    title="Desastre natural — complejo simplicial",
    output_dir=OUT,
))

# --- figures 1v/2v: the same models WITH the valuation of C ------------------
# The example has one atom, C = "the road is clear", and the announcement of
# ¬C "simply flips the values of C". Both states are generated: BEFORE
# (v(C) = {SnR, SR}: in the worlds where Alice sends C the road is reported
# clear; in nS nothing was sent and C is false) and AFTER the announcement ¬C
# (v(C) = {nS}: the flipped values). In each state Barb holds a false belief in
# SnR: before, she believes ¬C while C is true (she only sees nS, where nothing
# arrived); after, she believes C while C is false.
from assignment import assignment_from_model, nu_violations
from semantics import holds_kripke

VALUACIONES = {
    "antes":   {"C": {"SnR", "SR"}},   # C as sent over the radio
    "despues": {"C": {"nS"}},          # after announcing ¬C: values flipped
}
FORMULAS = {
    "C":       ("atom", "C"),
    "B_b C":   ("B", "b", ("atom", "C")),
    "B_b ¬C":  ("B", "b", ("not", ("atom", "C"))),
    "B_a C":   ("B", "a", ("atom", "C")),
}
for etapa, val in VALUACIONES.items():
    print(f"\n== {etapa} del anuncio ¬C: v(C) = {sorted(val['C'])} ==")
    # Relational figure: each world carries its literal (C / ¬C) as the second
    # line of its label; same function as figure 1.
    print(visualization.show(
        KBframe, f"desastre_{etapa}_relacional",
        title=f"Desastre natural — {etapa} de ¬C (modelo relacional K+B)",
        output_dir=OUT, valuation=val,
    ))
    # Simplicial figure: the world valuation induces the vertex assignment
    # (what each perspective KNOWS about C: 1 = C, 0 = ¬C, 2 = nothing), and
    # each face of the lattice shows the literals its vertices observe.
    asg = assignment_from_model(Simp, val)
    # Geometric drawing (matplotlib) with the valuation: each vertex shows the
    # literal it observes (C / ¬C; nothing if it does not know), each facet its
    # world. Filled simplices, but no editable source.
    print(visualization.show(
        Simp, f"desastre_{etapa}_geometrico",
        title=f"Desastre natural — {etapa} de ¬C (complejo simplicial)",
        output_dir=OUT, valuation=val,
    ))
    # The same complex via Graphviz: it leaves a .dot next to the .png, like the
    # other poster figures, so it can be retouched without rerunning the model.
    print(visualization.show(
        Simp, f"desastre_{etapa}_complejo",
        title=f"Desastre natural — {etapa} de ¬C (complejo simplicial)",
        output_dir=OUT, valuation=val, engine="dot",
    ))
    print(hasse.show(
        Simp, f"desastre_{etapa}_hasse",
        title=f"Desastre natural — {etapa} de ¬C (reticula de caras)",
        output_dir=OUT, assignment=asg,
    ))
    # NU: a truth that no agent observes cannot be represented on vertices.
    # It does not happen here (Alice always knows the value of C in her class).
    gaps = nu_violations(Simp, asg, val)
    print("  violaciones NU:", gaps if gaps else "ninguna")
    # Barb's false belief, checked world by world.
    for w in ("nS", "SnR", "SR"):
        fila = "  ".join(f"{k}={'T' if holds_kripke(KBframe, val, w, f) else 'F'}"
                         for k, f in FORMULAS.items())
        print(f"  {w:>4}: {fila}")

# --- figure 3: schematic of the belief revision ------------------------------
# Rule specified in the paper, not implemented in the tool at the time: this
# figure is a schematic, not the code's output. It shows the two states of the
# path and the rule drawn at the bottom: after the announcement discards the
# facet Barb believed, she moves to the surviving facet with the same b-vertex
# that shares the most vertices with the one she lost.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle

NAVY, TXT, MUT = "#0e2140", "#1a2233", "#5a6478"
A, B, RED, GRN, PALE = "#1971c2", "#e8590c", "#c0432b", "#1b5e3f", "#cbd3de"
XMAX = 994 / 540.0                      # aspect ratio of the slot on the poster

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

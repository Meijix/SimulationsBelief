# -*- coding: utf-8 -*-
"""Regenerate every figure of the paper from the current code.

    .venv/bin/python paper/make_figures.py

Writes PNGs (and the Graphviz .dot sources next to them) into ``paper/figures/``.
The three static examples are the ones of ``examples/Example for Poster N.py``;
this script repeats their models here so the paper's figures do not depend on
``preview`` (which writes to a temporary file) and so each example states the
pipeline case it uses. The Background figure is the three-agent bit complex,
declared directly as a simplicial model (no relational model behind it).

Per model we produce the TRIO the paper reads together: the relational frame
(when there is one), the geometric picture of the complex, and the Hasse
diagram of its face lattice, in the full form and in the simplified
vertices-and-facets form.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import hasse  # noqa: E402
from knowledge_belief import KnowledgeBeliefFrame  # noqa: E402
from relational_frame import RelationalFrame  # noqa: E402
from simplicial import Node, SimplicialBeliefModel, to_simplicial  # noqa: E402
from visualization import show  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)


def trio(model, name: str, title: str, *, relational=None, rel_title: str | None = None) -> None:
    """Draw the relational frame (if given), the complex, and both Hasse views."""
    if relational is not None:
        print(show(relational, f"{name}_relational", rel_title or title, output_dir=OUT))
    print(show(model, f"{name}_simplicial", title, output_dir=OUT))
    print(hasse.show(model, f"{name}_hasse", title, output_dir=OUT))
    print(hasse.show(model, f"{name}_hasse_simple", title, output_dir=OUT,
                     facets_and_vertices=True))


# --------------------------------------------------------------------------- #
# Background: three agents with private bits, declared directly (no relations).
# Facets {a1,b1,c1}, {a1,b1,c0}, {a0,b0,c0}; knowledge only, so S_a = S.
# --------------------------------------------------------------------------- #
agents = {"a", "b", "c"}
a0, a1 = Node("a", frozenset({"a0"})), Node("a", frozenset({"a1"}))
b0, b1 = Node("b", frozenset({"b0"})), Node("b", frozenset({"b1"}))
c0, c1 = Node("c", frozenset({"c0"})), Node("c", frozenset({"c1"}))
nodes = {a0, a1, b0, b1, c0, c1}
facets = {frozenset({a1, b1, c1}), frozenset({a1, b1, c0}), frozenset({a0, b0, c0})}
bits = SimplicialBeliefModel(agents, nodes, facets, {ag: set(facets) for ag in agents})
trio(bits, "background_bits", "Three agents with private bits")

# --------------------------------------------------------------------------- #
# Example 1 -- pipeline case 2 (knowledge and belief from one seed). Proper.
# --------------------------------------------------------------------------- #
worlds = {"no message sent", "message sent but not received", "message sent and received"}
seed = {
    "a": {("message sent but not received", "message sent and received"),
          ("message sent and received", "message sent but not received")},
    "b": {("message sent but not received", "no message sent"),
          ("no message sent", "message sent but not received")},
    "c": {("message sent but not received", "no message sent"),
          ("message sent and received", "no message sent")},
}
rel1 = KnowledgeBeliefFrame.from_partial(agents, worlds, seed, seed)
assert rel1.is_proper()
simp1 = to_simplicial(rel1)
trio(simp1, "ex1", "Example 1", relational=rel1)

# --------------------------------------------------------------------------- #
# Example 2 -- pipeline case 3 (knowledge only, Q_a = R_a). Proper.
# --------------------------------------------------------------------------- #
agents2 = {"a", "b"}
worlds2 = {"anSnRbnSnR", "aS1bnR", "aS1bR", "aS0bnR", "aS0bR",
           "anRbS1", "aRbS1", "anRbS0", "aRbS0"}
seed2 = {
    "a": {("anSnRbnSnR", "anRbS1"), ("anSnRbnSnR", "anRbS0"),
          ("aS1bnR", "aS1bR"), ("aS0bnR", "aS0bR")},
    "b": {("anSnRbnSnR", "aS1bnR"), ("anSnRbnSnR", "aS0bnR"),
          ("anRbS1", "aRbS1"), ("anRbS0", "aRbS0")},
}
rel2 = RelationalFrame.from_partial_s5(agents2, worlds2, seed2)
simp2 = to_simplicial(rel2)
trio(simp2, "ex2", "Example 2", relational=rel2)

# --------------------------------------------------------------------------- #
# Example 3 -- pipeline case 2; NOT proper, so to_proper runs (b is skewed).
# --------------------------------------------------------------------------- #
worlds3 = {"w1", "w2", "w3"}
seed3 = {"a": {("w1", "w2"), ("w1", "w3")},
         "b": {("w1", "w2"), ("w3", "w2")},
         "c": {("w2", "w3"), ("w1", "w3")}}
improper3 = KnowledgeBeliefFrame.from_partial(agents, worlds3, seed3, seed3)
assert not improper3.is_proper()
print(show(improper3, "ex3_improper_relational", "Example 3, before to_proper", output_dir=OUT))
proper3 = improper3.to_proper()
assert proper3.is_proper()
simp3 = to_simplicial(proper3)
trio(simp3, "ex3", "Example 3", relational=proper3, rel_title="Example 3, after to_proper")


# --------------------------------------------------------------------------- #
# Background figures of the paper (Section 2): the three-agent bit complex as
# the GUI draws it, before and after the announcement that a's bit is 1 with
# revision. Written next to the .tex under the names it includes
# (SimplicialExample1/2, HasseExample0.2/0.3/0.4), with English titles:
# "Complex as entered" is the GUI's preview title, "Simplicial complex" and
# "Face lattice" the titles of its pipeline figures. Node and facet names
# (a0..c1, F1..F3) and the vertex atoms are the ones typed in the GUI.
# --------------------------------------------------------------------------- #
PAPER = os.path.dirname(os.path.abspath(__file__))
_names = {a0: "a0", a1: "a1", b0: "b0", b1: "b1", c0: "c0", c1: "c1"}
_bits = {a0: {"Pa": 0}, a1: {"Pa": 1}, b0: {"Pb": 0}, b1: {"Pb": 1}, c0: {"Pc": 0}, c1: {"Pc": 1}}
F1, F2 = frozenset({a1, b1, c1}), frozenset({a1, b1, c0})
F3_before, F3_after = frozenset({a0, b0, c0}), frozenset({a1, b0, c0})
before = SimplicialBeliefModel(agents, nodes, {F1, F2, F3_before},
                               {ag: {F1, F2, F3_before} for ag in agents},
                               world_of_facet={F1: "F1", F2: "F2", F3_before: "F3"},
                               node_names=_names)
# After the announcement a0 lies in no facet (an isolated perspective, K45) and
# F3 = {a1, b0, c0} is believed by b and c only.
after = SimplicialBeliefModel(agents, nodes, {F1, F2, F3_after},
                              {"a": {F1, F2}, "b": {F1, F2, F3_after}, "c": {F1, F2, F3_after}},
                              world_of_facet={F1: "F1", F2: "F2", F3_after: "F3"},
                              node_names=_names, axiom_d=False)
print(show(before, "SimplicialExample1", "Complex as entered", output_dir=PAPER, assignment=_bits))
print(show(after, "SimplicialExample2", "Simplicial complex", output_dir=PAPER, assignment=_bits))
print(hasse.show(hasse.face_lattice(before, include_empty=False, assignment=_bits),
                 "HasseExample0.4", "Face lattice", output_dir=PAPER))
print(hasse.show(hasse.face_lattice(after, include_empty=False, assignment=_bits),
                 "HasseExample0.3", "Face lattice", output_dir=PAPER))
print(hasse.show(hasse.face_lattice(after, include_empty=False, assignment=_bits),
                 "HasseExample0.2", "Face lattice", output_dir=PAPER, facets_and_vertices=True))

"""A simplicial belief model defined directly, with a vertex assignment.

Short variant of ``examples/examplesimplicial1.py`` (which explains every step):
three agents with one private bit each, three worlds (facets 111, 110, 000),
then a fourth world 100 and revised beliefs. Here the vertices also carry a
three-valued assignment (thesis ch. 3, ``assignment.py``), so the Hasse
diagrams show what each perspective observes and a formula is evaluated.

Run:  python examplesimplicial1.py   (opens two previews).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hasse
from assignment import holds
from simplicial import Node, SimplicialBeliefModel

agents = {"a", "b", "c"}
a1 = Node("a", frozenset({"a1"}))
a0 = Node("a", frozenset({"a0"}))
b1 = Node("b", frozenset({"b1"}))
b0 = Node("b", frozenset({"b0"}))
c1 = Node("c", frozenset({"c1"}))
c0 = Node("c", frozenset({"c0"}))
nodes = {a1, a0, b1, b0, c1, c0}
facet1 = frozenset({a1, b1, c1})
facet2 = frozenset({a1, b1, c0})
facet3 = frozenset({a0, b0, c0})
facets = {facet1, facet2, facet3}

# L : node -> {atom: 1 (true) | 0 (false)}; an unmentioned atom is 2 (unknown).
# Each perspective observes its own bit: Pa is a's bit, Pb is b's, Pc is c's.
assignment = {
    a1: {"Pa": 1}, a0: {"Pa": 0},
    b1: {"Pb": 1}, b0: {"Pb": 0},
    c1: {"Pc": 1}, c0: {"Pc": 0},
}

belieffacets = {"a": {facet1, facet2, facet3},
                "b": {facet1, facet2, facet3},
                "c": {facet1, facet2, facet3}}

model = SimplicialBeliefModel(agents, nodes, facets, belieffacets)
print(model.is_valid())
# At 110 agent a does not know c's bit: Pc is true at 111 and false at 110.
print("a believes Pc at 110?", holds(model, assignment, facet2, ("B", "a", ("atom", "Pc"))))
print("a believes Pa at 110?", holds(model, assignment, facet2, ("B", "a", ("atom", "Pa"))))

hasse.preview(model, "Simplicial Model 1", assignment=assignment)

facet4 = frozenset({a1, b0, c0})
facets2 = {facet1, facet2, facet3, facet4}

beliefrevisionfacets = {"a": {facet1, facet2},
                        "b": {facet1, facet2, facet4},
                        "c": {facet1, facet2, facet4}}

model2 = SimplicialBeliefModel(agents, nodes, facets2, beliefrevisionfacets)
print(model2.is_valid())

hasse.preview(model2, "Simplicial Model 2", assignment=assignment)

import sys
from knowledge_belief import KnowledgeBeliefFrame
from visualization import preview, show, to_dot, visualize
from relational_frame import RelationalFrame
from simplicial import to_simplicial, SimplicialBeliefModel, Node
from properness import is_proper, non_proper_worlds, explain, to_proper
import hasse


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
belieffacets = {"a": {facet1, facet2, facet3},
                "b": {facet1, facet2, facet3},
                "c": {facet1, facet2, facet3}}

model = SimplicialBeliefModel(agents, nodes, facets, belieffacets)

print(model.is_valid())

hasse.preview(model, "Simplicial Model 1")

facet4 = frozenset({a1, b0, c0})
facets2 = {facet1, facet2, facet3, facet4}

beliefrevisionfacets = {"a": {facet1, facet2},
                        "b": {facet1, facet2, facet4},
                        "c": {facet1, facet2, facet4}}

model2 = SimplicialBeliefModel(agents, nodes, facets2, beliefrevisionfacets)

print(model2.is_valid())

hasse.preview(model2, "Simplicial Model 2")
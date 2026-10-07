"""A simplicial belief model DEFINED DIRECTLY, with no relational model behind it.

Story: binary inputs. Each of a, b, c holds a private bit, so each agent has two
possible perspectives (nodes a1/a0, b1/b0, c1/c0). A facet is a joint input
vector, i.e. a world: 111, 110 and 000 at first, then 100 is added.

Route: the ``SimplicialBeliefModel`` constructor with hand-built nodes, facets
and belief subcomplexes S_a (no ``to_simplicial`` and no properness step:
distinct facets are distinct worlds by construction). ``axiom_d`` is left at
its default ``None``, so the belief logic is INFERRED from the geometry: KD45
when every node lies in some facet of its own S_a, K45 otherwise. Model 1 has
S_a = S for everyone (belief = knowledge). Model 2 shrinks the subcomplexes:
a0 lies in no facet of S_a -- an ISOLATED PERSPECTIVE, where a's belief is
defunct (vacuously everything). That is legal under K45, which is what the
constructor then reports, so is_valid() stays True. Both are drawn as Hasse
diagrams.

Run:  python examples/examplesimplicial1.py   (opens two previews).
"""

import os
import sys
# The examples live one level below the core modules. Put the repository root on
# sys.path so ``python examples/<script>.py`` works from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_belief import KnowledgeBeliefFrame
from visualization import preview, show, to_dot, visualize
from relational_frame import RelationalFrame
from simplicial import to_simplicial, SimplicialBeliefModel, Node
from properness import is_proper, non_proper_worlds, explain, to_proper
import hasse


agents = {"a", "b", "c"}
# Node(agent, cls): in a translated model `cls` is the agent's knowledge class (a
# frozenset of worlds). Here there is no relational model, so the frozenset just
# names the vertex ("a1" = a's bit is 1); it only has to be hashable and distinct.
a1 = Node("a", frozenset({"a1"}))
a0 = Node("a", frozenset({"a0"}))
b1 = Node("b", frozenset({"b1"}))
b0 = Node("b", frozenset({"b0"}))
c1 = Node("c", frozenset({"c1"}))
c0 = Node("c", frozenset({"c0"}))
nodes = {a1, a0, b1, b0, c1, c0}
# Facets = worlds, one node per agent (the UCF condition): 111, 110, 000. Two
# facets sharing a node are worlds that agent cannot tell apart (111 and 110
# share a1 and b1: a and b do not see c's bit).
facet1 = frozenset({a1, b1, c1})
facet2 = frozenset({a1, b1, c0})
facet3 = frozenset({a0, b0, c0})
facets = {facet1, facet2, facet3}
# Every agent believes every world possible: S_a = S, so belief coincides with
# knowledge and Axiom D holds (no isolated perspective) -- inferred KD45.
belieffacets = {"a": {facet1, facet2, facet3},
                "b": {facet1, facet2, facet3},
                "c": {facet1, facet2, facet3}}

model = SimplicialBeliefModel(agents, nodes, facets, belieffacets)

print(model.is_valid())

hasse.preview(model, "Simplicial Model 1")

# Second model: add the world 100 and revise the beliefs.
facet4 = frozenset({a1, b0, c0})
facets2 = {facet1, facet2, facet3, facet4}

# a believes only the worlds where both she and b hold 1, so a0 (in 000 and 100)
# lies in no facet of S_a: an isolated perspective, i.e. a defunct belief at a0.
# Accepted because axiom_d is inferred (K45), not declared. b and c rule out 000.
beliefrevisionfacets = {"a": {facet1, facet2},
                        "b": {facet1, facet2, facet4},
                        "c": {facet1, facet2, facet4}}

model2 = SimplicialBeliefModel(agents, nodes, facets2, beliefrevisionfacets)

print(model2.is_valid())

hasse.preview(model2, "Simplicial Model 2")
import sys
from knowledge_belief import KnowledgeBeliefFrame
from visualization import preview, show, to_dot, visualize
from relational_frame import RelationalFrame
from simplicial import to_simplicial
from properness import is_proper, non_proper_worlds, explain, to_proper
import hasse

#This is the main example in "Semantics for Belief in Simplicial Complexes". We start with a knowledge/belief frame that is NOT proper, but a seemingly sensible model of belief
#(though perhaps without applications! See Example for Poster 2). We then make it proper, and turn it into a simplicial complex.

agents = {"a", "b", "c"}
worlds = {"w1", "w2", "w3"}
frameseed = {"a":{("w1","w2"),("w1","w3")}, "b":{("w1","w2"),("w3","w2")}, "c":{("w2","w3"),("w1","w3")}}

ImproperRelPosterExample3 = KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)

print(f"{KnowledgeBeliefFrame.is_proper(ImproperRelPosterExample3)}")

preview(ImproperRelPosterExample3, "Poster Example 3: The Improper Relational Case")

#Now we make this proper

ProperRelPosterExample3 = KnowledgeBeliefFrame.to_proper(ImproperRelPosterExample3)

print(f"{KnowledgeBeliefFrame.is_proper(ProperRelPosterExample3)}")

preview(ProperRelPosterExample3, "Poster Example 3: The Proper Relational Case")

#Now we make this simplicial

SimpPosterExample3 = to_simplicial(ProperRelPosterExample3)

hasse.preview(SimpPosterExample3, "Poster Example 3: The Simplicial Case")



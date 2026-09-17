import sys
from knowledge_belief import KnowledgeBeliefFrame
from visualization import preview, show, to_dot, visualize
from relational_frame import RelationalFrame
from simplicial import to_simplicial
from properness import is_proper, non_proper_worlds, explain, to_proper
import hasse

agents = {"a", "b", "c"}
worlds = {"w1", "w2", "w3"}
frame = {"a":{("w1","w2"),("w1","w3")}, "b":{("w1","w2"),("w3","w2")}, "c":{("w2","w3"),("w1","w3")}}

KBframe = KnowledgeBeliefFrame.from_partial(agents, worlds, frame, frame)
preview(KBframe, "KB frame")

print(f"{KnowledgeBeliefFrame.is_proper(KBframe)}")

#print(f"{KnowledgeBeliefFrame.non_proper_worlds(BKframe)}")

KBproperframe = KnowledgeBeliefFrame.to_proper(KBframe)
preview(KBproperframe, "KB proper frame")

print(f"{KnowledgeBeliefFrame.is_proper(KBproperframe)}")

#It's not picking out the smallest frame here. Should be either b or c as the distinguished agent.

#print(f"{non_proper_worlds(BKproperframe)}")

Simp = to_simplicial(KBproperframe)

hasse.preview(Simp, "Simplicial Model")

#Can't get it to visualize hasse diagrams no matter what I try.
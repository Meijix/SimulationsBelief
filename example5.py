import sys
from knowledge_belief import KnowledgeBeliefFrame
from visualization import preview, show, to_dot, visualize

agents = {"alice", "bob"}
worlds = {"w1", "w2", "w3"}

k = {"alice": {("w1", "w2"), ("w2", "w3"),("w3", "w1")}, "bob": {("w2", "w3")}}
b = {"alice": {("w1","w2"),("w1","w3")}, "bob": {("w2","w3")}}

#empty belief frame
b3={"alice":{}, "bob": {}}


frame = KnowledgeBeliefFrame.from_partial(agents, worlds, k, b)
print(frame)
print(visualize(frame))
#preview(frame, "Example 5")

print(frame.is_proper())
frameproper = frame.to_proper()
print(frameproper)
print(visualize(frameproper))
#preview(frameproper, "Example 5 Proper")


#b2 = {"alice":{("w1", "w2"), ("w2","w3"),("w3","w1")},"bob":{("w1","w3")}}
#frame2 = KnowledgeBeliefFrame.from_partial(agents, worlds, k, b2)
#print(frame2)
#print(visualize(frame2))
#preview(frame2, "Example 6")

frame3 = KnowledgeBeliefFrame.from_partial(agents, worlds, k, b3)
print(frame3)
print(visualize(frame3))
preview(frame3, "Example 7")
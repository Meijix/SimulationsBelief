import sys
from knowledge_belief import KnowledgeBeliefFrame
from visualization import preview, show, to_dot, visualize
from relational_frame import RelationalFrame
from simplicial import to_simplicial
from properness import is_proper, non_proper_worlds, explain, to_proper
import hasse

#Example Natural Disaster

#Alice is part of a disaster response team in an area recently ravaged by flooding. Some trees have fallen, and presumably some of the roads are currently inaccessible. She currently infers that the main highway is clear, for the simple reason that she just drove on it. Unbeknownst to her, loose soil caused a tree to fall just after she passed by. She falsely reports over the radio that the road is clear. Later, she climbs a large hill and gets a better vantage point and sees that the road is in fact not clear. She now reports this over the radio. As she is the only worker in this area, all other people in the radio network trust her and her alone for information about this road.

#How should we model this as an action? We'll model each signal over the radio as a separate action. Let's say there are two agents, Alice, a, and on the other side of the radio, Barb, b. Let C be the fact that the road is clear. Let's assume (reasonably) that radio communication is spotty, so first, a sends b to C, but b potentially hears nothing. There are therefore three worlds: a world where nothing is sent (nS), a world where C is sent but not received (SnR), and a world where C is sent and received (SR). Note that at SnR, b falsely believes that C is false.

#The second message, where ~C is sent, simply flips the values of C.

#Behold the simplicial translation.

agents = {"a","b"}

worlds = {"nS","SnR","SR"}

frameseed = {"a":{("SnR","SR"),("SR","SnR")},
             "b":{("SnR","nS")}}

KBframe = KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)

print(f"{KnowledgeBeliefFrame.is_proper(KBframe)}")

preview(KBframe, "KB frame")

Simp = to_simplicial(KBframe)

hasse.preview(Simp, "Natural Disaster Simplicial Model")
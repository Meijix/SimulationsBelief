"""Natural disaster example -- a false report over a spotty radio.

Story (details in the comments below): Alice (a) radios to Barb (b) that the
road is clear (C); the message may not arrive. Three worlds: nothing sent (nS),
sent but not received (SnR), sent and received (SR). At SnR Barb believes
nothing was sent -- a FALSE belief -- which makes this a belief model rather
than knowledge alone. Only this first message is built here; the second message
(~C) described below is not modelled in this script.

Route: knowledge + belief with one seed for both relations
(``KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)``).
The model is already PROPER, so ``to_simplicial`` is applied directly and
``hasse.preview`` draws the face lattice.

Run:  python "examples/Natural Disaster Example.py"   (opens two previews).
"""

import os
import sys
# The examples live one level below the core modules. Put the repository root on
# sys.path so ``python examples/<script>.py`` works from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

#a: the SYMMETRIC pair SnR <-> SR -- she sent, and cannot tell whether it arrived;
#no opinion, so her belief there is Q = R. b: the ONE-WAY edge SnR -> nS -- when
#nothing arrives she believes nothing was sent. Under S5 that makes {nS, SnR} her
#knowledge class, and the belief closure keeps the pointer: she believes nS at
#both, false at SnR. At SR she received, a class of her own (Q = R by silence).
frameseed = {"a":{("SnR","SR"),("SR","SnR")},
             "b":{("SnR","nS")}}

KBframe = KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)

# Proper already: a's classes {nS}, {SnR, SR} and b's {nS, SnR}, {SR} meet in
# singletons, so no to_proper step is needed.
print(f"{KnowledgeBeliefFrame.is_proper(KBframe)}")

preview(KBframe, "KB frame")

Simp = to_simplicial(KBframe)

hasse.preview(Simp, "Natural Disaster Simplicial Model")
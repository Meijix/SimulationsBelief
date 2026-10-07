"""Poster Example 2 -- the alternating message-passing protocol (one bit, lossy channel).

Story: a and b take turns sending a bit (0/1) to each other, a first. A message
may fail to arrive, and then the other agent stops. The sender never knows
whether the bit arrived; an agent who received nothing cannot tell "nothing was
sent" from "it was lost". Nine worlds: the quiet world, four where a sends (bit
0/1, received or not) and four where b sends.

Route: KNOWLEDGE ONLY (S5). The seed is closed with
``RelationalFrame.from_partial_s5``; ``to_simplicial`` accepts an S5 frame
directly and wraps it with Q_a = R_a ("believe exactly what you know"), so each
S_a is the whole complex. The model is already PROPER on its first description,
so there is no ``to_proper`` step. ``hasse.preview`` draws the face lattice.
Reproduces the poster / paper figures "Poster Example 2 Relational Case" and
"Poster Example 2 Simplicial Case".

Run:  python "examples/Example for Poster 2.py"   (opens two previews).
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

#This example has a practical application, being the "Alternating Message Passing Protocol" (see page 35 of the Tech Memo, or page 30 of 
#"Distributed Computing Through Combinatorial Topology"). The key idea is that a and b are sending messages containing a bit value back and forth, with a being the first messenger,
#followed by b, and so on. When a message fails to be received, the other agent stops. Note that this, too, is proper in its initial description. There's something philosophically
#interesting about the fact that all real examples are already proper on the first description. If you agree, that makes me happy, because this is an argument I've been having with my advisor
#Adam Bjorndahl for literal years (he thinks properness is overly restrictive, I think all real examples are more or less already proper). This is good to ponder!

agents= {"a","b"}

#Si stands for Send bit value i, R for receive. So for example aS1bnR stands for "a sends 1 and b does not receive"
worlds = {"anSnRbnSnR", "aS1bnR", "aS1bR", "aS0bnR", "aS0bR", "anRbS1", "aRbS1", "anRbS0", "aRbS0"}
#Observe: These worlds are a bit convoluted to describes. This is another motivation for simplicial stuff - defining this directly as a simplicial model is, IMO, much simpler!

#Each edge pairs two worlds an agent cannot tell apart. a: from the quiet world she
#cannot tell whether b sent a bit that got lost (anRbS1, anRbS0); having sent a
#bit, she cannot tell whether it arrived (aS1bnR ~ aS1bR, aS0bnR ~ aS0bR). b is
#the mirror image. One direction per pair is enough: the S5 closure adds the rest.
frameseed = {"a":{("anSnRbnSnR","anRbS1"),("anSnRbnSnR","anRbS0"),("aS1bnR","aS1bR"),("aS0bnR","aS0bR")},
             "b":{("anSnRbnSnR","aS1bnR"),("anSnRbnSnR","aS0bnR"),("anRbS1","aRbS1"),("anRbS0","aRbS0")}}

RelPosterExample2 = RelationalFrame.from_partial_s5(agents, worlds, frameseed)

print(f"{is_proper(RelPosterExample2)}")

preview(RelPosterExample2, "Poster Example 2: The Relational Case")

SimpPosterExample2 = to_simplicial(RelPosterExample2)

hasse.preview(SimpPosterExample2, "Poster Example 2: The Simplicial Case")



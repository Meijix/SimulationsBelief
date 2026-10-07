"""Poster Example 1 -- "a sends a message to b, and c has no idea".

Story: three worlds -- no message sent, sent but not received, sent and
received. a knows whether she sent but not whether it arrived; b knows whether
he received, and if he did not he cannot tell "never sent" from "lost"; c is
convinced nothing was sent, which is FALSE in two of the three worlds. That
false belief is why this is a belief model and not knowledge alone.

Route: knowledge + belief with one seed for both relations
(``KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)``).
Knowledge closes under S5; belief is closed inside the knowledge classes and,
where the seed is silent, defaults to Q_a = R_a ("believe what you know"). The
model is already PROPER, so there is no ``to_proper`` step: ``to_simplicial``
turns the three worlds into three facets and ``hasse.preview`` draws the face
lattice. Reproduces the poster / paper figures "Poster Example 1 Relational
Case" and "Poster Example 1 Simplicial Case".

Run:  python "examples/Example For Poster 1.py"   (opens two previews).
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

#This example is the main one from the thesis and tech memo. We start with the belief relational model representing the action 
#"a sends a message to b and c has no idea" and translate it into a simplicial model. There is no need to make the model proper
#as it is already proper to begin with. Note that this is belief, not knowledge, because c always has a (potentially false) belief that the message was not sent.

agents = {"a", "b", "c"}

worlds = {"no message sent", "message sent but not received", "message sent and received"}

#The intuition behind frameseed: a can't tell apart when the message is or is not received, 
#b cannot tell apart when the message is not received and when it is not sent, 
#and c always believes the message is not sent.
#Shape of the edges: a's and b's are SYMMETRIC pairs -- pure indistinguishability,
#which closes to an S5 class and, by silence, to Q = R there (no opinion). c's are
#ONE-WAY pointers into "no message sent": under S5 they make c's knowledge
#complete (c has no evidence), while the belief closure keeps the pointer, so c
#believes nS everywhere -- false at SnR and SR.
frameseed = {"a":{("message sent but not received","message sent and received"),("message sent and received","message sent but not received")}, 
             "b":{("message sent but not received","no message sent"),("no message sent","message sent but not received")}, 
             "c":{("message sent but not received","no message sent"),("message sent and received","no message sent")}}

RelPosterExample1 = KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)

# Proper already: at every world the three knowledge classes meet in that world
# alone, so to_simplicial can be applied directly.
print(f"{KnowledgeBeliefFrame.is_proper(RelPosterExample1)}")

preview(RelPosterExample1, "Poster Example 1: The Relational Case")

SimpPosterExample1 = to_simplicial(RelPosterExample1)

hasse.preview(SimpPosterExample1, "Poster Example 1: The Simplicial Case")
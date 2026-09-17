import sys
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
#b cannot tell apart when the messgae is not received and when it is not sent, 
#and c always believes the message is nt sent.
frameseed = {"a":{("message sent but not received","message sent and received"),("message sent and received","message sent but not received")}, 
             "b":{("message sent but not received","no message sent"),("no message sent","message sent but not received")}, 
             "c":{("message sent but not received","no message sent"),("message sent and received","no message sent")}}

RelPosterExample1 = KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)

print(f"{KnowledgeBeliefFrame.is_proper(RelPosterExample1)}")

preview(RelPosterExample1, "Poster Example 1: The Relational Case")

SimpPosterExample1 = to_simplicial(RelPosterExample1)

hasse.preview(SimpPosterExample1, "Poster Example 1: The Simplicial Case")
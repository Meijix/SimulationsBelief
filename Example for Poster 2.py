import sys
from knowledge_belief import KnowledgeBeliefFrame
from visualization import preview, show, to_dot, visualize
from relational_frame import RelationalFrame
from simplicial import to_simplicial
from properness import is_proper, non_proper_worlds, explain, to_proper
import hasse

#This example has a practical application, being the "Alternating Message Passing Protocol" (see page 35 of the Tech Memo, or page 30 of 
#"Distributed Computing Through Combinatorial Topology"). The key idea is that a and b are sending messages containing a bit value back and forth, with a the first messenger being a,
#followed by b, and so on. When a message fails to be received, the other agent stops. Note that this, too, is proper in its initial description. There's something philosphically
#interesting about the fact that all real examples are already proper on the first description. If you agree, that makes me happy, because this is an argument I've been having with my advisor
#Adam Bjorndahl for years (he thinks properness is overly restrictive, I think all real examples are more or less already proper). This is good to ponder!

agents= {"a","b"}

#Si stands for Send bit value i, R for receive. So for example aS1bnR stands for "a sends 1 and b does not receive"
worlds = {"anSnRbnSnR", "aS1bnR", "aS1bR", "aS0bnR", "aS0bR", "anRbS1", "aRbS1", "anRbS0", "aRbS0"}
#Observe: These worlds are a bit convoluted to describes. This is another motivation for simplicial stuff - defining this directly as a simplicial model is, IMO, much simpler!

frameseed = {"a":{("anSnRbnSnR","anRbS1"),("anSnRbnSnR","anRbS0"),("aS1bnR","aS1bR"),("aS0bnR","aS0bR")},
             "b":{("anSnRbnSnR","aS1bnR"),("anSnRbnSnR","aS0bnR"),("anRbS1","aRbS1"),("anRbS0","aRbS0")}}

RelPosterExample2 = RelationalFrame.from_partial_s5(agents, worlds, frameseed)

print(f"{is_proper(RelPosterExample2)}")

preview(RelPosterExample2, "Poster Example 2: The Relational Case")

SimpPosterExample2 = to_simplicial(RelPosterExample2)

hasse.preview(SimpPosterExample2, "Poster Example 2: The Simplicial Case")



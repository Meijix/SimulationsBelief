import sys

from relational_frame import RelationalFrame
from visualization import preview, show, to_dot, visualize
from properness import is_proper, non_proper_worlds
from knowledge_belief import KnowledgeBeliefFrame
from properness import explain, to_proper
from relational_frame import s5_closure

agents = {"a","b","c"}
worlds = {"w1","w2","w3"}
frame = {"a": {("w1","w2"),("w1","w3")},"b": {("w1","w2"),("w3","w2")},"c": {("w1","w3"),("w2","w3")}}

BF = RelationalFrame.from_partial(agents, worlds, frame, make_serial=True)

KF = RelationalFrame.from_partial_s5(agents, worlds, frame)

#preview(BF, "Thesis KD45 Example")

#preview(KF, "Thesis S5 Example")

KF_proper = to_proper(KF)

#preview(KF_proper, "Thesis S5 Example Proper")

frame2 = {"a": {("w1","w2")},"b": {("w2","w3")},"c": {("w3","w1")}}

KF2 = RelationalFrame.from_partial_s5(agents, worlds, frame2)

#preview(KF2, "Example 2")

KF2_proper = to_proper(KF2)

#preview(KF2_proper, "Example 2 proper")

moreagents = {"a","b","c","d"}

moreworlds = {"w1","w2","w3","w4","w5","w6"}

moreframe = {"a": {("w1","w2"),("w1","w3")},"b": {("w1","w2"),("w3","w2")},"c": {("w1","w3"),("w2","w3")},"d": {("w1","w4"),("w1","w5"),("w1","w6"),("w2","w4"),("w2","w5"),("w2","w6"),("w3","w4"),("w3","w5"),("w3","w6")}}

moreBF = RelationalFrame.from_partial(moreagents, moreworlds, moreframe, make_serial=True)

#preview (moreBF, "Example MoreBF")

moreKF = RelationalFrame.from_partial_s5(moreagents, moreworlds, moreframe)

#preview (moreKF, "Example MoreKF")

moreKF_proper = to_proper(moreKF)

#preview(moreKF_proper, "Example MoreKF_proper")

dmoreKF_proper = to_proper(moreKF, "d")

preview(dmoreKF_proper, "Example dMoreKF_proper")

print("Good up to here!")

#BF_proper = to_proper(BF)

#preview(BF_proper, "Some Bullshit")

#The above threw me the error I wanted so that's good.

print("Now we move to knowledge AND belief")




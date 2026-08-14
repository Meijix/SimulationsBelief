import sys

from relational_frame import RelationalFrame
from visualization import preview, show, to_dot, visualize
from properness import is_proper, non_proper_worlds

agents = {"a","b","c"}
worlds = {"w1","w2","w3"}
frame = {"a": {("w1","w2"),("w1","w3")},"b": {("w1","w2"),("w3","w2")},"c": {("w1","w3"),("w2","w3")}}

RF = RelationalFrame.from_partial(agents, worlds, frame, make_serial=True)

preview(RF, "Thesis KD45 Example")

print("Good up to here!")

frame2 = {"a": {("w3","w2"),("w2","w3")},"b": {("w3","w2"),("w2","w3")},"c": {("w3","w2"),("w2","w3")}}

RF2 = RelationalFrame.from_partial(agents, worlds, frame2, make_serial=True)

print(f"{is_proper(RF2)}")

print(f"{non_proper_worlds(RF2)}")

preview(RF2, "Example 2")

print("Also seems good up to here!")

frame3 = {"a": {("w1","w2"),("w1","w3")},"b": {("w3","w2"),("w2","w3")},"c": {("w3","w2"),("w2","w3")}}

RF3 = RelationalFrame.from_partial(agents, worlds, frame3, make_serial=True)

print(f"{is_proper(RF3)}")

print(f"{non_proper_worlds(RF3)}")

preview(RF3, "Example 3")

# Unless I'm missing something, the above should be in error. It spits ou all three worlds, but it should only spit out w2 and w3, no?

#frame3.1 = {"a": s5_closure(worlds, frame3),"b": s5_closure(worlds, frame3),"c": s5_closure(worlds, frame3)}

#RF3.1 = RelationalFrame(agents, worlds, frame3.1)

#In the above two lines, I am having an issue with the s5_closure function - what's my issue?

print(f"{is_proper(RF)}")

print(f"{non_proper_worlds(RF)}")

# Here might also be an error. RF is not S5. This is probably related to the issue above as well I suspect.
from relational_frame import RelationalFrame
from visualization import render, visualize

agents = {"a"}
worlds = {"w"}
frame = {"a": {("w","w")}}

RF = RelationalFrame(agents, worlds, frame)

print(" ", render(RF, name="example3", title="Refl1agsimp"))


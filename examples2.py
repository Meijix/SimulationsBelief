"""A complete relational (KD45) frame, step by step.

Scenario: tomorrow's weather. Alice rules out sun but cannot tell rain from
cloud; Bob is convinced it will be sunny.

Run it:  python examples2.py
"""

import sys

from relational_frame import RelationalFrame
from visualization import preview, show, to_dot, visualize

# --- Step 1: agents and worlds -----------------------------------------------
agents = {"alice", "bob"}
worlds = {"rain", "cloud", "sun"}

# --- Step 2: the edges the story gives us ------------------------------------
# An edge  w -> u  means: "if the world were w, the agent considers u possible".
seed = {
    "alice": {("rain", "cloud"), ("sun", "rain")},
    "bob": {("rain", "sun"), ("cloud", "sun")},
}

# --- Step 3: those edges alone are not a KD45 frame --------------------------
print("STEP 3: building the raw frame")
try:
    RelationalFrame(agents, worlds, seed)
except ValueError as exc:
    print(exc)

# --- Step 4: close each relation under KD45 to get a valid frame -------------
frame = RelationalFrame.from_partial(agents, worlds, seed, make_serial=True)
print(f"\nSTEP 4: after from_partial -> {frame}, valid = {frame.is_valid()}")

# --- Step 5: read the finished frame -----------------------------------------
print("\nSTEP 5: the accessibility relation")
print(visualize(frame))

# --- Step 6: what each agent believes at the actual world --------------------
# B_a(phi) holds at w when every world a accesses from w satisfies phi, so a
# proposition is just the set of worlds where it is true.
sunny = {"sun"}
print("\nSTEP 6: who believes it will be sunny, world by world")
for agent in sorted(agents):
    for world in sorted(worlds):
        accessible = frame.successors(agent, world)
        print(f"  {agent} at {world:5s} accesses {str(sorted(accessible)):22s}"
              f" believes sunny = {accessible <= sunny}")

# --- Step 7: drawing it ------------------------------------------------------
# visualization.py has a tiny API, and each function accepts ANY model in the
# project (a frame, a knowledge+belief model or a simplicial model):
#
#   visualize(model)             the text diagram used in step 5 -- no extras needed
#   show(model, name, title)     writes outputs/<name>.png and returns the path
#   show(model, name, open=True) ...and opens it in your viewer
#   preview(model)               zero-config: render to a temp file and open it
#   to_dot(model)                the Graphviz source, if you want to edit it by hand
print("\nSTEP 7: the Graphviz source, to_dot(frame)")
print("\n".join(to_dot(frame).splitlines()[:8]), "\n  ...")

# show() picks the renderer and the style by itself: this frame is KD45, so it is
# drawn with arrows; an S5 (knowledge) relation would come out undirected and
# without self-loops. Add dim=3 for a simplicial model to get interactive HTML.
# Pass --open to also open the image (and to preview it in one call).
print("\nSTEP 8: the image, show(frame, name, title)")
open_it = "--open" in sys.argv
try:
    print(" ", show(frame, "example2", "Tomorrow's weather · belief (KD45)", open=open_it))
except RuntimeError as exc:
    # Raised when Graphviz is not installed -- the text diagram still works.
    print(" skipped:", exc)

# STEP 9: the easiest one-liner -- preview() renders and opens in a single call,
# with no name or folder to choose. Quiet by default; opens when you pass --open.
if open_it:
    print("\nSTEP 9: preview(frame) -- render + open in one call")
    preview(frame, "Tomorrow's weather · belief (KD45)")

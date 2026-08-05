"""A complete relational (KD45) frame, step by step.

Scenario: tomorrow's weather. Alice rules out sun but cannot tell rain from
cloud; Bob is convinced it will be sunny.

Run it:  python examples2.py
"""

from relational_frame import RelationalFrame
from visualization import render, visualize

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

# --- Step 7: draw it ---------------------------------------------------------
print("\nSTEP 7: rendering")
try:
    print(" ", render(frame, name="example2", title="Tomorrow's weather · belief (KD45)"))
except RuntimeError as exc:
    print(" skipped:", exc)

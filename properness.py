"""Is a KNOWLEDGE (S5) relational model proper?  (check only -- no conversion)

Step 1 of the "proper" layer
Answers a single question: **is this knowledge model proper?**

A relational model is **proper** when, for every world ``w``, the only world that
*all* agents jointly consider possible from ``w`` is ``w`` itself:

    | intersection over agents a of R_a(w) | = 1

For knowledge (S5, where each ``R_a`` is an equivalence relation) ``R_a(w)`` is agent
``a``'s equivalence class ``[w]_a``, so properness says: no two distinct worlds are
indistinguishable to *every* agent at once. That is exactly the condition a model must
meet to be translated into a simplicial model -- distinct worlds must map to distinct
facets.

Note on scope:
  * This file **only checks** properness. It does NOT convert a non-proper model into
    a proper one -- and, per the theory, there is **no unique** proper model anyway:
    a non-proper model is bisimilar to *many* different proper models, so "make it
    proper" is a separate design choice for a later step.
  * It targets **knowledge** (equivalence relations). It reads ``R_a(w)`` directly, so
    it runs on any :class:`RelationalFrame`, but the ``= 1`` reading of the result is
    only meaningful when the relations are reflexive (knowledge), which guarantees
    ``w`` itself is always in the intersection.

Depends only on ``relational_frame``.
"""

from __future__ import annotations
from typing import List, Set
from relational_frame import RelationalFrame, World


def joint_possibilities(frame: RelationalFrame, world: World) -> Set[World]:
    """Return ``⋂_a R_a(world)``: the worlds *every* agent considers possible from it."""
    intersection: Set[World] | None = None
    for agent in frame.agents:
        reachable = frame.successors(agent, world)
        intersection = reachable if intersection is None else (intersection & reachable)
    return intersection if intersection is not None else set()


def non_proper_worlds(frame: RelationalFrame) -> List[World]:
    """Return the worlds where properness fails (``|⋂_a R_a(w)| != 1``); empty if proper."""
    return [
        w
        for w in sorted(frame.worlds, key=str)
        if len(joint_possibilities(frame, w)) != 1
    ]


def is_proper(frame: RelationalFrame) -> bool:
    """Return True iff the knowledge model is proper.

    Proper = at every world, all agents jointly consider exactly one world possible
    (namely that world). Equivalently ``|⋂_a [w]_a| = 1`` for every ``w``.
    """
    return not non_proper_worlds(frame)


def explain(frame: RelationalFrame) -> str:
    """Return a human-readable verdict: proper, or which worlds break it and why."""
    bad = non_proper_worlds(frame)
    if not bad:
        return "PROPER: every world is uniquely pinned down by the agents' joint knowledge."
    lines = [f"NOT PROPER: {len(bad)} world(s) fail |intersection of R_a(w)| = 1:"]
    for w in bad:
        joint = sorted(joint_possibilities(frame, w), key=str)
        lines.append(
            f"  world {w!r}: all agents jointly consider {len(joint)} worlds possible "
            f"-> {joint}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    # --- a PROPER 2-agent knowledge model --------------------------------- #
    # 4 worlds; agent a can tell the top pair from the bottom pair, agent b the
    # left pair from the right pair. Together they pin down every world uniquely.
    worlds = {"w0", "w1", "w2", "w3"}

    def equivalence(classes):
        return {(x, y) for group in classes for x in group for y in group}

    proper = RelationalFrame(
        {"a", "b"},
        worlds,
        {
            "a": equivalence([["w0", "w1"], ["w2", "w3"]]),
            "b": equivalence([["w0", "w2"], ["w1", "w3"]]),
        },
    )
    print("Example 1 (grid of two partitions):")
    print(explain(proper))

    # --- a NON-PROPER model (thesis Figure 1: everyone sees everything) ----- #
    complete = {(x, y) for x in worlds for y in worlds}
    non_proper = RelationalFrame(
        {"a", "b"}, worlds, {"a": set(complete), "b": set(complete)}
    )
    print("\nExample 2 (complete relations -- nobody distinguishes anything):")
    print(explain(non_proper))

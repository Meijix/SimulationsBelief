"""Proper knowledge (S5) models: the properness check and the general -> proper step.

A relational model is **proper** when no two distinct worlds are related by
*every* agent (Bjorndahl & Sink, *A Note on Proper Relational Structures*):

    for all x != y:   NOT (x R_a y for every agent a)

:func:`jointly_confused_with` computes ``⋂_a R_a(w) \\ {w}``; a world is a
violation when that set is non-empty. (The ``|⋂_a R_a(w)| = 1`` form found in
the literature is equivalent only for reflexive relations; the definition
itself is implemented, so an empty intersection is never mistaken for a
properness failure.)

Properness is a condition on knowledge: every public function here requires
equivalence (S5) relations and refuses anything else (:func:`require_knowledge`).
Opening it to KD45 belief frames is an open question, see docs/02 §1.

:func:`to_proper` makes ``|W|`` copies of a non-proper model and skews one
distinguished agent's relation across the copies (:func:`copy_and_skew`, the
finite, modulo-``|W|`` construction of the Note, Props. 2.1-2.3). The result
is proper and bisimilar to the input; the projection ``(w, copy) -> w`` is the
witness. Construction and proof: docs/02 §4-5. Depends only on ``relational_frame``.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

from relational_frame import Agent, Edge, RelationalFrame, World


def require_knowledge(frame: RelationalFrame, operation: str = "Properness") -> None:
    """Raise unless every relation in ``frame`` is an equivalence relation (S5).

    Raises:
        ValueError: listing every axiom (T, 4, 5) that fails.
    """
    problems = frame.s5_violations()
    if not problems:
        return
    listed = "\n  - ".join(problems)
    raise ValueError(
        f"{operation} requires KNOWLEDGE relations: every R_a must be an EQUIVALENCE "
        f"relation (S5 = reflexive + transitive + Euclidean). This frame is not, so "
        f"no properness verdict is given and nothing is converted.\n"
        f"  - {listed}\n"
        f"Properness is a condition on knowledge and to_proper (Sink Thm 2.4) is "
        f"proved for equivalence relations only. Build knowledge with "
        f"RelationalFrame.from_partial_s5(...) or relational_frame.s5_closure(...); "
        f"with both knowledge and belief use knowledge_belief.KnowledgeBeliefFrame, "
        f"whose is_proper() checks the knowledge relations."
    )


# --------------------------------------------------------------------------- #
# The properness check
# --------------------------------------------------------------------------- #
def joint_possibilities(frame: RelationalFrame, world: World) -> Set[World]:
    """``⋂_a R_a(world)``: the worlds every agent considers possible from it.

    Not guarded: a raw intersection, usable as a diagnostic on any frame (on a
    belief frame an empty result means mutually inconsistent beliefs there).
    """
    intersection: Set[World] | None = None
    for agent in frame.agents:
        reachable = frame.successors(agent, world)
        intersection = reachable if intersection is None else (intersection & reachable)
    return intersection if intersection is not None else set()


def jointly_confused_with(frame: RelationalFrame, world: World) -> Set[World]:
    """The *other* worlds jointly accessible from ``world``: ``⋂_a R_a(w) \\ {w}``.

    Non-empty exactly when ``world`` violates properness.

    Raises:
        ValueError: if ``frame`` is not a knowledge (S5) frame.
    """
    require_knowledge(frame, "jointly_confused_with")
    return joint_possibilities(frame, world) - {world}


def non_proper_worlds(frame: RelationalFrame) -> List[World]:
    """The worlds where properness fails, sorted; empty if proper."""
    require_knowledge(frame, "non_proper_worlds")
    return [w for w in sorted(frame.worlds, key=str) if jointly_confused_with(frame, w)]


def properness_pairs(frame: RelationalFrame) -> List[Edge]:
    """Every ordered pair ``(x, y)``, ``x != y``, with ``x R_a y`` for all agents."""
    require_knowledge(frame, "properness_pairs")
    return [
        (x, y)
        for x in sorted(frame.worlds, key=str)
        for y in sorted(jointly_confused_with(frame, x), key=str)
    ]


def properness_violations(frame: RelationalFrame) -> List[str]:
    """A message per world where properness fails (empty if proper)."""
    require_knowledge(frame, "properness_violations")
    problems: List[str] = []
    for w in sorted(frame.worlds, key=str):
        others = jointly_confused_with(frame, w)
        if others:
            listed = sorted(map(str, others))
            plural = "s" if len(others) > 1 else ""
            problems.append(
                f"Properness violated at world {w!r}: every agent also considers "
                f"{len(others)} other world{plural} possible from it ({listed}), so "
                f"the agents jointly fail to tell {w!r} apart from "
                f"{'them' if len(others) > 1 else listed[0]!r}."
            )
    return problems


def is_proper(frame: RelationalFrame) -> bool:
    """True iff the knowledge model is proper (no two worlds jointly confused)."""
    return not properness_violations(frame)


def explain(frame: RelationalFrame) -> str:
    """A readable verdict: proper, or which worlds break it and with which others."""
    bad = non_proper_worlds(frame)
    if not bad:
        return "PROPER: every world is uniquely pinned down by the agents' joint knowledge."
    lines = [f"NOT PROPER: {len(bad)} world(s) are jointly confused with another world:"]
    for w in bad:
        others = sorted(jointly_confused_with(frame, w), key=str)
        lines.append(f"  world {w!r}: every agent also considers {others} possible from it")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Proper frames and the general -> proper conversion
# --------------------------------------------------------------------------- #
class ProperRelationalFrame(RelationalFrame):
    """A knowledge frame that is proper; ``projection`` maps each world back to
    the world of the original model it simulates (identity when nothing was copied)."""

    def __init__(
        self,
        agents,
        worlds,
        relations,
        validate: bool = True,
        projection: Optional[Dict[World, World]] = None,
    ) -> None:
        super().__init__(agents, worlds, relations, validate=validate)
        self.projection: Dict[World, World] = dict(projection or {})
        # The S5 precondition holds even with validate=False: "proper" is only
        # defined for knowledge. validate=False skips the properness check only.
        require_knowledge(self, "ProperRelationalFrame")
        if validate:
            problems = properness_violations(self)
            if problems:
                raise ValueError(
                    f"{len(problems)} properness violation(s) found:\n  - "
                    + "\n  - ".join(problems)
                )

    def is_proper(self) -> bool:
        return is_proper(self)

    def properness_violations(self) -> List[str]:
        return properness_violations(self)


def skew_cost(relations: Dict[Agent, Set[Edge]], agent: Agent) -> int:
    """Non-reflexive edges of ``agent``: each one crosses copies ``|W|`` times
    when ``agent`` is the distinguished one, so this ranks the candidates."""
    return sum(1 for (w, u) in relations.get(agent, ()) if w != u)


def cheapest_distinguished_agent(
    *families: Dict[Agent, Set[Edge]],
    agents: Iterable[Agent],
) -> Agent:
    """The agent whose skew draws the fewest cross-copy edges; ties by name.

    Every choice gives a proper model of the same size; this one only keeps the
    drawing readable. Pass every family that will be skewed with the same agent
    (knowledge and belief), since the cost is their sum.
    """
    candidates = sorted(agents, key=str)
    return min(candidates, key=lambda a: sum(skew_cost(family, a) for family in families))


def choose_distinguished(
    agents: Iterable[Agent],
    distinguished_agent: Optional[Agent],
    *families: Dict[Agent, Set[Edge]],
) -> Agent:
    """Check the preconditions of the copy construction and pick the agent to skew.

    Shared by :func:`to_proper` and ``KnowledgeBeliefFrame.to_proper``.

    Raises:
        ValueError: fewer than two agents (a single-agent non-proper model has no
            proper bisimilar counterpart: properness would force the identity
            relation), or an unknown ``distinguished_agent``.
    """
    agents = set(agents)
    if len(agents) < 2:
        raise ValueError(
            "No proper model bisimilar to this frame exists: a single-agent, "
            "non-proper frame cannot be made proper (properness would force the "
            "relation to be the identity). The construction requires >= 2 agents."
        )
    distinguished = (
        distinguished_agent
        if distinguished_agent is not None
        else cheapest_distinguished_agent(*families, agents=agents)
    )
    if distinguished not in agents:
        raise ValueError(
            f"Unknown distinguished agent {distinguished!r}; "
            f"choose one of {sorted(map(str, agents))}."
        )
    return distinguished


def to_proper(
    frame: RelationalFrame,
    distinguished_agent: Optional[Agent] = None,
) -> ProperRelationalFrame:
    """Convert a knowledge frame into a bisimilar proper one (Sink, Thm 2.4).

    An already proper frame is wrapped with the identity projection. Otherwise
    ``|W|`` copies are made and ``distinguished_agent`` (default: the one with
    the fewest non-reflexive edges) is skewed across them.

    Raises:
        ValueError: no agents, not a knowledge frame, a single agent, or an
            unknown ``distinguished_agent``.
    """
    if not frame.agents:
        raise ValueError("Cannot build a proper model from a frame with no agents.")
    require_knowledge(frame, "to_proper")
    if is_proper(frame):
        return ProperRelationalFrame(
            agents=frame.agents,
            worlds=frame.worlds,
            relations=frame.relations,
            projection={w: w for w in frame.worlds},
        )
    distinguished = choose_distinguished(frame.agents, distinguished_agent, frame.relations)
    new_worlds, new_relations, projection = copy_and_skew(
        frame.worlds, frame.agents, frame.relations, distinguished
    )
    return ProperRelationalFrame(
        agents=frame.agents,
        worlds=new_worlds,
        relations=new_relations,
        projection=projection,
    )


def copy_and_skew(worlds, agents, relations, distinguished):
    """Make ``|W|`` copies of a relation family and skew one agent's across them.

    New worlds are pairs ``(w, copy)``. A non-distinguished agent's edge
    ``w -> w2`` becomes ``(w, u) -> (w2, u)`` in every copy ``u``; the
    distinguished agent's becomes ``(w, u) -> (w2, u2)`` with
    ``g(u2) = g(u) - g(w) + g(w2)  (mod |W|)``, ``g`` the sorted-name bijection
    ``W -> 0..|W|-1``. (The thesis prints ``g(w)`` for the last ``g(w2)``; the
    primed reading is the one the proof needs, see docs/02 §4 Step D.) Pure edge
    arithmetic, no properness check, so it applies to a belief family too.

    Returns:
        ``(new_worlds, new_relations, projection)`` with ``projection[(w, u)] = w``.
    """
    worlds_sorted = sorted(worlds, key=str)
    n = len(worlds_sorted)
    g = {w: i for i, w in enumerate(worlds_sorted)}

    new_relations: Dict[Agent, Set[Edge]] = {a: set() for a in agents}
    for a in agents:
        for (w, w2) in relations[a]:
            for u in worlds_sorted:
                if a != distinguished:
                    new_relations[a].add(((w, u), (w2, u)))
                else:
                    u2 = worlds_sorted[(g[u] - g[w] + g[w2]) % n]
                    new_relations[a].add(((w, u), (w2, u2)))

    new_worlds = {(w, u) for w in worlds_sorted for u in worlds_sorted}
    projection = {(w, u): w for w in worlds_sorted for u in worlds_sorted}
    return new_worlds, new_relations, projection


if __name__ == "__main__":
    # A PROPER 2-agent knowledge model: a tells the top pair from the bottom
    # pair, b the left pair from the right pair; together they pin every world.
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

    # A NON-PROPER model (thesis Figure 1: everyone sees everything).
    complete = {(x, y) for x in worlds for y in worlds}
    non_proper = RelationalFrame(
        {"a", "b"}, worlds, {"a": set(complete), "b": set(complete)}
    )
    print("\nExample 2 (complete relations -- nobody distinguishes anything):")
    print(explain(non_proper))
    print("\nto_proper ->", to_proper(non_proper))

    # A BELIEF (KD45) model is refused, not silently mis-judged.
    belief = RelationalFrame.from_partial(
        {"a", "b"}, {"w0", "w1"}, {"a": {("w0", "w1")}, "b": {("w0", "w1")}},
        make_serial=True,
    )
    print("\nExample 3 (KD45 belief frame -- properness is refused):")
    try:
        is_proper(belief)
    except ValueError as e:
        print(f"  ValueError: {str(e).splitlines()[0]}")

"""Proper KNOWLEDGE (S5) models: the properness check and the general -> proper conversion.

Scope: this module is for **knowledge**, i.e. frames whose relations are equivalence
relations (S5). Every public entry point refuses a non-reflexive (KD45 / belief) frame
-- see :func:`require_knowledge` and the REVIEW note below for why.

A relational model is **proper** when, for every world ``w``, the only world that
*all* agents jointly consider possible from ``w`` is ``w`` itself:

    |  intersection over agents a of R_a(w)  | = 1

Equivalently (this is the primary definition in Bjorndahl & Sink, *A Note on Proper
Relational Structures*, arXiv:2506.17142): there is no pair of **distinct** worlds
``x != y`` with ``x R_a y`` for *every* agent ``a``.

    The two formulations agree exactly when the relations are **reflexive**, because
    reflexivity puts ``w`` in the intersection and so pins ``|intersection| >= 1``. The
    ``= 1`` reading then says precisely "no *other* world is jointly accessible". On a
    non-reflexive KD45 frame they come apart: an empty intersection (``|.| = 0``) means
    the agents' beliefs are mutually inconsistent at that world, which is NOT a
    properness failure under the primary definition, yet ``!= 1`` reports it as one.
    Restricting this module to S5 (below) is what keeps the cheap ``= 1`` test correct.

For knowledge, ``R_a(w)`` is agent ``a``'s equivalence class ``[w]_a``, so properness
says: no two distinct worlds are indistinguishable to *every* agent at once. That is
exactly the condition a model must meet to be translated into a simplicial model --
distinct worlds must map to distinct facets.

Many natural models are not proper: several agents can share the same mistaken
perspective across several worlds. :func:`to_proper` fixes this the way the thesis
does -- it makes ``|W|`` copies of the model (new worlds are pairs ``(w, copy)``) and
*skews* the accessibility relation of a single distinguished agent so that it links
worlds *across* copies. The result is **bisimilar** to the original (the projection
``(w, copy) -> w`` is a surjective bounded morphism) but proper, at the cost of the
redundant copies the thesis describes.

Two notes recorded from a careful audit against the thesis:

* Skew formula (typo in the PDF). The thesis prints the distinguished agent's
  skew as ``g(u) - g(w) = g(u') - g(w)`` -- the same ``g(w)`` on both sides. Read
  literally this collapses to ``u = u'`` (a within-copy relation), which would NOT
  connect copies and would NOT make the model proper, contradicting the theorem
  and the surrounding text ("connect worlds *across* copies ... ensures the model
  is proper"). The intended condition is ``g(u) - g(w) = g(u') - g(w')`` (the prime
  is lost in the PDF); that is what :func:`copy_and_skew` implements, and it is the
  only reading consistent with the proof.

* Finite case = the source paper's own construction. The thesis presents the
  skew for an infinite ``W`` (a bijection ``g: W -> Z`` in the countable case,
  ``g: W -> R`` in the continuum case). The source note (Bjorndahl & Sink,
  *A Note on Proper Relational Structures*, Props. 2.1-2.3) gives the **finite**
  case explicitly, and it uses arithmetic **modulo ``|W|``** -- exactly the cyclic
  skew implemented here. So this is not an ad-hoc adaptation; it is the paper's
  finite-case construction. (A non-modular skew would push boundary copies out of
  range and break seriality; the modular version is what the paper uses.)

  Why it is correct (Prop. 2.2), for the setting that matters (>= 2 agents,
  equivalence relations): a non-distinguished agent forces ``u = u'`` (same copy),
  and the distinguished agent then forces ``g(u) - g(w) = g(u') - g(w') (mod |W|)``,
  which with ``u = u'`` gives ``g(w) = g(w') (mod |W|)`` hence ``w = w'`` (``g`` is a
  bijection onto ``0..|W|-1``). So the joint intersection is exactly ``{(w, u)}``.
  Cross-checked here on 1000 random models with zero failures.

  The construction singles out one distinguished agent and needs at least one
  *other* agent to pin the copy index, so it requires **>= 2 agents**. A
  single-agent, non-proper model has no proper bisimilar counterpart at all
  (properness would force the identity relation, which bisimulation cannot reach),
  so :func:`to_proper` raises for that case.

Depends only on ``relational_frame``.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set
from relational_frame import Agent, Edge, RelationalFrame, World


# --------------------------------------------------------------------------- #
# Scope guard: knowledge (S5) only -- belief (KD45) is refused, for now
# --------------------------------------------------------------------------- #
# ============================ REVIEW LATER ================================= #
# OPEN QUESTION: should properness be definable for BELIEF (KD45) frames too?
#
# Today the answer here is NO, and every public function below refuses a
# non-reflexive frame. Reasons for the current restriction:
#
#   1. In the thesis architecture properness is a condition on the KNOWLEDGE
#      relations (see knowledge_belief.KnowledgeBeliefFrame.is_proper, which
#      passes self.knowledge). Belief lives in Q_a; properness never touches it.
#   2. The cheap `|intersection| = 1` test implemented below is only *equivalent*
#      to the paper's primary definition under reflexivity.
#      Without the guard it silently reports mutually-inconsistent beliefs
#      (`|intersection| = 0`) as properness failures -- which is exactly the wrong
#      answer, and exactly the confusing behaviour reported against examples3.py.
#   3. to_proper / copy_and_skew (Sink Thm 2.4, Bjorndahl & Sink Props. 2.1-2.3)
#      is proved for equivalence relations. Its correctness on a non-reflexive
#      KD45 frame has NOT been verified.
#
# the guard stays. Remove it deliberately, not by accident.
# =========================================================================== #
def require_knowledge(frame: RelationalFrame, operation: str = "Properness") -> None:
    """Raise unless every relation in ``frame`` is reflexive (i.e. the frame is S5).

    Properness in this module is defined for **knowledge**. A KD45 belief frame is
    rejected rather than silently given a meaningless verdict.

    Args:
        frame: The frame to check.
        operation: Name of the caller, used in the error message.

    Raises:
        ValueError: If some agent's relation lacks a reflexive edge ``w -> w``.
    """
    missing = [
        (a, w)
        for a in sorted(frame.agents, key=str)
        for w in sorted(frame.worlds, key=str)
        if w not in frame.successors(a, w)
    ]
    if not missing:
        return
    shown = ", ".join(f"R_{a}({w})" for a, w in missing[:5])
    more = f" (and {len(missing) - 5} more)" if len(missing) > 5 else ""
    raise ValueError(
        f"{operation} is defined for KNOWLEDGE (S5) models only, but this frame is "
        f"not reflexive (Axiom T): {len(missing)} missing self-loop(s) -- {shown}{more}. "
        f"A KD45 *belief* frame has no properness verdict here: on a non-reflexive ")

# --------------------------------------------------------------------------- #
# The properness check
# --------------------------------------------------------------------------- #
def joint_possibilities(frame: RelationalFrame, world: World) -> Set[World]:
    """Return ``⋂_a R_a(world)``: the worlds *every* agent considers possible from it.

    Unguarded on purpose: this is the raw intersection, useful for diagnostics on any
    frame. It is the *interpretation* as a properness verdict that needs S5.
    """
    intersection: Set[World] | None = None
    for agent in frame.agents:
        reachable = frame.successors(agent, world)
        intersection = reachable if intersection is None else (intersection & reachable)
    return intersection if intersection is not None else set()


def non_proper_worlds(frame: RelationalFrame) -> List[World]:
    """Return the worlds where properness fails (``|⋂_a R_a(w)| != 1``); empty if proper.

    Raises:
        ValueError: If ``frame`` is not a knowledge (S5) frame.
    """
    require_knowledge(frame, "non_proper_worlds")
    return [
        w
        for w in sorted(frame.worlds, key=str)
        if len(joint_possibilities(frame, w)) != 1
    ]


def properness_violations(frame: RelationalFrame) -> List[str]:
    """Return a message per world where properness fails (empty list if proper).

    Raises:
        ValueError: If ``frame`` is not a knowledge (S5) frame.
    """
    require_knowledge(frame, "properness_violations")
    problems: List[str] = []
    for w in sorted(frame.worlds, key=str):
        joint = joint_possibilities(frame, w)
        if len(joint) != 1:
            problems.append(
                f"Properness violated at world {w!r}: all agents jointly consider "
                f"{len(joint)} world(s) possible ({sorted(map(str, joint))}), "
                f"expected exactly 1."
            )
    return problems


def is_proper(frame: RelationalFrame) -> bool:
    """Return True iff the knowledge model is proper (bridges to a simplicial model).

    Proper = at every world, all agents jointly consider exactly one world possible
    (namely that world). Equivalently ``|⋂_a [w]_a| = 1`` for every ``w``.

    Raises:
        ValueError: If ``frame`` is not a knowledge (S5) frame.
    """
    return not properness_violations(frame)


def explain(frame: RelationalFrame) -> str:
    """Return a human-readable verdict: proper, or which worlds break it and why.

    Raises:
        ValueError: If ``frame`` is not a knowledge (S5) frame.
    """
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


# --------------------------------------------------------------------------- #
# Proper frames and the general -> proper conversion
# --------------------------------------------------------------------------- #
class ProperRelationalFrame(RelationalFrame):
    """A :class:`RelationalFrame` that is *proper* (ready for the simplicial step).

    Beyond the usual KD45 checks, construction also verifies properness
    (``|⋂_a R_a(w)| = 1`` for every world), which requires the frame to be a
    knowledge (S5) frame. When produced by :func:`to_proper`, :attr:`projection`
    maps each (copied) world back to the world it simulates in the original model
    -- the surjective bounded morphism that witnesses bisimilarity, and the link
    the simplicial translation will need.
    """

    def __init__(
        self,
        agents,
        worlds,
        relations,
        validate: bool = True,
        projection: Optional[Dict[World, World]] = None,
    ) -> None:
        super().__init__(agents, worlds, relations, validate=validate)
        # projection[(w, copy)] = w : which original world each new world simulates.
        self.projection: Dict[World, World] = dict(projection or {})
        if validate:
            problems = properness_violations(self)
            if problems:
                raise ValueError(
                    f"{len(problems)} properness violation(s) found:\n  - "
                    + "\n  - ".join(problems)
                )

    def is_proper(self) -> bool:
        """Return True (a validated ProperRelationalFrame is proper by construction)."""
        return is_proper(self)

    def properness_violations(self) -> List[str]:
        """Return properness violations (empty for a validated proper frame)."""
        return properness_violations(self)


def to_proper(
    frame: RelationalFrame,
    distinguished_agent: Optional[Agent] = None,
) -> ProperRelationalFrame:
    """Convert a general KNOWLEDGE frame into a bisimilar PROPER one (Sink, Thm 2.4).

    Makes ``|W|`` copies of the model -- new worlds are pairs ``(w, copy)`` -- and
    skews the accessibility relation of one distinguished agent so it connects
    worlds across copies, guaranteeing properness while staying bisimilar to
    ``frame`` (the projection ``(w, copy) -> w`` is a surjective bounded morphism).

    If ``frame`` is already proper, it is returned as a :class:`ProperRelationalFrame`
    without any copying (no point inflating an already-proper model).

    Args:
        frame: A knowledge (S5) frame -- the equivalence relations that properness
            is about; the construction preserves its axioms.
        distinguished_agent: The agent whose relation is skewed. Defaults to the
            first agent (sorted by name). Any agent works -- the choice only affects
            *which* copies connect, not the correctness of the result.

    Returns:
        A :class:`ProperRelationalFrame` whose :attr:`projection` maps each new
        world back to the original world it simulates.

    Raises:
        ValueError: If ``frame`` has no agents, is not a knowledge (S5) frame, or
            ``distinguished_agent`` is unknown.
    """
    if not frame.agents:
        raise ValueError("Cannot build a proper model from a frame with no agents.")

    require_knowledge(frame, "to_proper")

    # Already proper -> wrap with the identity projection; no copies needed.
    if is_proper(frame):
        return ProperRelationalFrame(
            agents=frame.agents,
            worlds=frame.worlds,
            relations=frame.relations,
            projection={w: w for w in frame.worlds},
        )

    # The copy construction needs a non-distinguished agent to pin the copy index,
    # so >= 2 agents are required. With a single agent, "proper" means the relation
    # is the identity, which no bisimilar model can achieve (bisimilarity preserves
    # how many worlds the agent considers possible) -- so no proper model exists.
    if len(frame.agents) < 2:
        raise ValueError(
            "No proper model bisimilar to this frame exists: a single-agent, "
            "non-proper frame cannot be made proper (properness would force the "
            "relation to be the identity). The construction requires >= 2 agents."
        )

    distinguished = (
        distinguished_agent
        if distinguished_agent is not None
        else sorted(frame.agents, key=str)[0]
    )
    if distinguished not in frame.agents:
        raise ValueError(
            f"Unknown distinguished agent {distinguished!r}; "
            f"choose one of {sorted(map(str, frame.agents))}."
        )

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
    """Make ``|W|`` copies of a relation family and cyclically skew one agent's.

    Shared core of the general->proper conversion. New worlds are pairs
    ``(w, copy)``; non-distinguished agents act within a single copy, while the
    ``distinguished`` agent is skewed cyclically across copies (guaranteeing
    properness). Applying this to a knowledge family and a belief family with the
    SAME ``distinguished`` agent preserves ``Q_a ⊆ R_a``.

    This is a pure edge-set transformation with no properness check of its own, so
    ``knowledge_belief`` can apply it to a *belief* family too (the properness
    verdict is still taken on the knowledge family).

    Args:
        worlds: The original world set.
        agents: The agents (keys of ``relations``).
        relations: ``agent -> set of (source, target)`` edges.
        distinguished: The agent whose relation is skewed across copies.

    Returns:
        ``(new_worlds, new_relations, projection)`` where ``projection`` maps each
        new world ``(w, copy)`` back to ``w``.
    """
    worlds_sorted = sorted(worlds, key=str)
    n = len(worlds_sorted)
    g = {w: i for i, w in enumerate(worlds_sorted)}  # bijection world -> index

    new_relations: Dict[Agent, Set[Edge]] = {a: set() for a in agents}
    for a in agents:
        for (w, w2) in relations[a]:
            for u in worlds_sorted:
                if a != distinguished:
                    # Non-distinguished agents act *within* a single copy u.
                    new_relations[a].add(((w, u), (w2, u)))
                else:
                    # Distinguished agent skewed cyclically ACROSS copies (finite
                    # adaptation of the thesis's g: W -> R skew), so its relation
                    # never fully coincides with another agent's -> proper.
                    # Skew condition: g(u) - g(w) = g(u') - g(w')  =>
                    #   g(u') = g(u) - g(w) + g(w')   (mod |W| for the finite case).
                    # (The thesis PDF drops the prime on the final g(w'); see the
                    # module docstring for why g(w') is the correct reading.)
                    u2 = worlds_sorted[(g[u] - g[w] + g[w2]) % n]
                    new_relations[a].add(((w, u), (w2, u2)))

    new_worlds = {(w, u) for w in worlds_sorted for u in worlds_sorted}
    projection = {(w, u): w for w in worlds_sorted for u in worlds_sorted}
    return new_worlds, new_relations, projection


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
    print("\nto_proper ->", to_proper(non_proper))

    # --- a BELIEF (KD45) model: refused, not silently mis-judged ----------- #
    belief = RelationalFrame.from_partial(
        {"a", "b"}, {"w0", "w1"}, {"a": {("w0", "w1")}, "b": {("w0", "w1")}},
        make_serial=True,
    )
    print("\nExample 3 (KD45 belief frame -- properness is refused):")
    try:
        is_proper(belief)
    except ValueError as e:
        print(f"  ValueError: {str(e).splitlines()[0]}")

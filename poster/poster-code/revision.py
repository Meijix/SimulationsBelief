# -*- coding: utf-8 -*-
"""Belief revision on a simplicial complex.

What problem it solves
----------------------
A public announcement discards the worlds where it is false. If the world an
agent BELIEVED possible is discarded, its belief loses its ground: the belief
relation is serial (axiom D), so it cannot point at nothing. The agent must
be sent to some facet that does survive, and the question is which one.

The rule
--------
The one specified in the NASA technical memo (Sink & Goodloe). If X is the
facet agent x believed and F' are the facets that survive the announcement::

    R_x(X)  =  argmax { |Y ∩ X| : Y in F',  pi_x(Y) = pi_x(X) }

where pi_x(Y) is the unique vertex of Y that belongs to x. The two parts say
different things and both are needed:

* the constraint ``pi_x(Y) = pi_x(X)`` forces the agent to stay in a facet
  that contains its own point of view. It cannot revise towards something it
  itself distinguishes: what it knows is not up for discussion, only what it
  believes.

* maximizing ``|Y ∩ X|`` is the minimal-change criterion. Each vertex that Y
  shares with X is a perspective about which the agent does NOT have to
  change its mind. Keeping the facet that shares the most vertices is
  changing as little as possible.

Geometrically the maximum is visible: on a strip of triangles, sharing two
vertices is sharing a whole EDGE and sharing one is touching at a POINT. The
winning facet is the one glued on, not the one that barely grazes.

What this rule is NOT
---------------------
It does not guarantee being right. It returns the surviving facet most similar
to the one that was lost, and that may still differ from the real world: the
agent gets closer without arriving. In the disaster example with three agents
that is exactly what happens, and it is the point of the poster.

    python poster/poster-code/revision.py      # runs the disaster example and prints it
"""
from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Sequence, Tuple


class Revision:
    """The result of revising a belief, with the reason in plain view.

    Attributes:
        agent: the agent that revises.
        lost: the facet it believed and the announcement discarded.
        winners: the surviving facets the rule picks. Normally one; more
            than one means a genuine tie in ``|Y ∩ X|``.
        candidates: every facet that competed, as ``(facet, |Y ∩ X|)`` pairs
            already sorted from largest to smallest overlap. Kept whole
            because it is the justification of the answer: without the
            losers, the maximum can be neither checked nor drawn.
        eliminated: the facets the announcement removed.
    """

    __slots__ = ("agent", "lost", "winners", "candidates", "eliminated")

    def __init__(self, agent, lost, winners, candidates, eliminated):
        self.agent = agent
        self.lost = lost
        self.winners = tuple(winners)
        self.candidates = tuple(candidates)
        self.eliminated = frozenset(eliminated)

    def __repr__(self) -> str:
        return (f"Revision(agent={self.agent!r}, winners={len(self.winners)}, "
                f"candidates={len(self.candidates)})")

    def is_decided(self) -> bool:
        """True if the rule returns a single facet (there was no tie)."""
        return len(self.winners) == 1


def perspective(agent, facet):
    """The unique vertex of ``facet`` that belongs to ``agent``, or None.

    In a chromatic complex each facet has at most one vertex per agent, which
    is exactly what makes ``pi_x`` well defined.
    """
    for node in facet:
        if str(node.agent) == str(agent):
            return node
    return None


def _facets_by_world(model) -> Dict[str, FrozenSet]:
    """``world -> facet``, with the facet normalized to a ``frozenset``."""
    out = {}
    for facet in model.facets:
        world = model.world_of_facet.get(facet)
        if world is not None:
            out[str(world)] = frozenset(facet)
    return out


def announce(model, true_worlds: Iterable) -> Tuple[set, set]:
    """Splits the facets into ``(surviving, eliminated)`` under an announcement.

    Args:
        model: the complex.
        true_worlds: the worlds where the announcement is true. The usual
            thing is to pass ``valuation[atom]``: announcing an atom keeps
            alive exactly the worlds where that atom holds.

    Returns:
        Two sets of ``frozenset`` of nodes.
    """
    keep = {str(w) for w in true_worlds}
    survive, gone = set(), set()
    for facet in model.facets:
        world = model.world_of_facet.get(facet)
        (survive if str(world) in keep else gone).add(frozenset(facet))
    return survive, gone


def revise(model, agent, lost, surviving: Iterable) -> Revision:
    """Applies ``R_x(X)``: which surviving facet ``agent`` moves to.

    Args:
        model: the complex.
        agent: the agent that loses its belief.
        lost: the facet ``X`` it believed, already eliminated.
        surviving: the facets left standing.

    Returns:
        A :class:`Revision`. If the agent's vertex in ``X`` does not survive
        either, ``winners`` and ``candidates`` come out empty: the
        announcement contradicted something the agent KNEW, and that is not
        belief revision but an ill-posed model.
    """
    lost = frozenset(lost)
    view = perspective(agent, lost)
    if view is None:
        return Revision(agent, lost, (), (), ())

    # Total, stable order: facets live in sets, whose iteration order changes
    # between runs. Without this, two runs could break a tie differently and
    # the figure would come out different every time.
    names = {frozenset(F): str(model.world_of_facet.get(F, ""))
             for F in model.facets}
    candidates = sorted(
        ((Y, len(Y & lost)) for Y in map(frozenset, surviving) if view in Y),
        key=lambda pair: (-pair[1], names.get(pair[0], "")),
    )
    if not candidates:
        return Revision(agent, lost, (), (), ())
    best = candidates[0][1]
    winners = tuple(Y for Y, overlap in candidates if overlap == best)
    return Revision(agent, lost, winners, tuple(candidates), ())


def revise_after_announcement(model, agent, believed_world, true_worlds) -> Revision:
    """``announce`` + ``revise`` in one go, naming worlds instead of facets.

    Args:
        model: the complex.
        agent: the agent that revises.
        believed_world: the world it believed possible, by name.
        true_worlds: the worlds where the announcement is true.

    Returns:
        A :class:`Revision` with ``eliminated`` already filled in.

    Raises:
        KeyError: if ``believed_world`` is not a world of the model.
        ValueError: if that world survives the announcement, in which case
            there is nothing to revise and asking is most likely a mistake.
    """
    by_world = _facets_by_world(model)
    lost = by_world[str(believed_world)]
    survive, gone = announce(model, true_worlds)
    if lost not in gone:
        raise ValueError(
            f"el mundo {believed_world!r} sobrevive al anuncio: no hay creencia "
            f"que revisar. R_x solo se aplica cuando la faceta creida se pierde."
        )
    result = revise(model, agent, lost, survive)
    return Revision(result.agent, result.lost, result.winners,
                    result.candidates, gone)


def describe(model, rev: Revision) -> str:
    """One line per candidate, with the overlap and who wins."""
    names = {frozenset(F): str(model.world_of_facet.get(F, "?"))
             for F in model.facets}
    if not rev.candidates:
        return f"  {rev.agent}: su vertice no sobrevive; no aplica R_{rev.agent}"
    lines = [f"  {rev.agent} pierde {names.get(rev.lost, '?')}:"]
    for facet, overlap in rev.candidates:
        mark = "  <--" if facet in rev.winners else ""
        shared = "arista" if overlap == 2 else ("punto" if overlap == 1 else f"{overlap} vertices")
        lines.append(f"      {names.get(facet, '?'):>4}  |Y n X| = {overlap}  ({shared}){mark}")
    return "\n".join(lines)


if __name__ == "__main__":
    import os
    import sys

    # poster/poster-code/ is two levels below the core modules.
    _here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(_here)))
    from knowledge_belief import KnowledgeBeliefFrame
    from simplicial import to_simplicial

    agents = {"a", "b", "c"}
    worlds = {"R", "RN", "NN", "nS"}
    knowledge = {
        "a": {("R", "RN"), ("RN", "NN")},
        "b": {("R", "RN"), ("NN", "nS")},
        "c": {("RN", "NN"), ("NN", "nS")},
    }
    belief = {"a": set(), "b": {("NN", "nS")}, "c": {("RN", "nS")}}
    KB = KnowledgeBeliefFrame.from_partial(agents, worlds, knowledge, belief)
    Simp = to_simplicial(KB)

    # Announcement S = "Ana did transmit": true in R, RN and NN. It kills nS,
    # which is exactly the only world Carla believed possible from the real
    # world RN.
    S_TRUE = {"R", "RN", "NN"}
    print("anuncio S = 'Ana si transmitio', verdadero en", sorted(S_TRUE))
    for agent, believed in (("c", "nS"), ("b", "nS")):
        rev = revise_after_announcement(Simp, agent, believed, S_TRUE)
        print(describe(Simp, rev))

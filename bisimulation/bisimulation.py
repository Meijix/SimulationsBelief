# -*- coding: utf-8 -*-
"""Bisimilarity between relational models, by partition refinement.

WHAT THIS IS FOR. ``properness.to_proper`` and ``KnowledgeBeliefFrame.to_proper``
claim that the model they build is **bisimilar** to the one they were given:
that is the whole content of Sink's Thm 2.4. Properness is bought by making
``|W|`` copies of the model, and the price must not be any change of modal
theory. Until now the repo checked that claim only *indirectly*, in the tests,
by verifying that the projection ``ρ(w, u) = w`` is a surjective bounded
morphism -- which implies bisimilarity by a theorem we did not re-derive.

This module checks the conclusion itself, and from the other side: it computes
the largest bisimulation between the two models **from scratch**, knowing
nothing about ``ρ``, and then asks whether every copy really does land in the
class of the world it simulates (:func:`projection_violations`). A bug in the
copy-and-skew construction that happened to preserve boundedness-as-coded would
still be caught here, because the two computations share no code.

THE ALGORITHM (Kanellakis & Smolka 1983, 1990). Bisimilarity is the largest
fixed point of the usual functional, and over an image-finite system it is the
limit of the stratified approximants ``∼_k`` (Hennessy & Milner 1985): ``∼_0``
relates everything, and ``∼_{k+1}`` refines ``∼_k`` by one round of
back-and-forth. Kanellakis and Smolka compute that limit as a **coarsest stable
partition**: keep an equivalence relation as a partition into *blocks*, and
while some block is unstable -- some of its states can reach a given block via
an ``a``-labelled step and others cannot, so that block is a *splitter* for it
(Def. 0.2.3) -- split it in two. The loop can only ever increase the number of
blocks, so it stops after at most ``|states|`` passes, and what it stops at is
exactly bisimilarity (Thm 0.2.6, in ``O(n·m)`` time).

    π := the initial partition
    repeat until nothing changed:
        for each block B, for each action a:
            if split(B, a, π) != {B}: replace B by the two halves

:func:`coarsest_stable_partition` is that loop, and :func:`_split` is the
``split`` of the paper's Figure 0.1: pick a representative of the block and
keep exactly the states that reach the *same set of blocks* as it does.

TWO ADAPTATIONS, both inside the paper's own framework:

* **Several modalities.** A model here carries one relation per agent, and in
  the knowledge+belief case two (``R_a`` and ``Q_a``). The chapter's labelled
  transition systems already allow an arbitrary action set, so we simply take
  ``Act = {("K", a), ("B", a) : a ∈ Ag}`` (or ``("R", a)`` for a bare frame) --
  the same tags the formula tuples of ``semantics.py`` use. Stability with
  respect to every one of those actions is exactly the back-and-forth clause
  for every modality.
* **Atoms.** The chapter starts from ``π_init = {Pr}`` because its transition
  systems have no valuation; that computes bisimilarity of *frames*. For
  *models* two bisimilar worlds must also satisfy the same atoms, so we start
  from the partition by atomic theory instead. This is not a departure: §0.2.3
  defines the coarsest stable refinement *of a given* ``π_init``, and the
  correctness argument of Thm 0.2.6 goes through verbatim as long as ``π_init``
  is coarser than bisimilarity, which it is (bisimilar worlds agree on atoms).
  With no valuation you get the frame-level answer, which is what Thm 2.4 is
  about.

WHAT IT DOES NOT DO. Simplicial models are not handled: the right notion there
is a chromatic simplicial map, not a partition of worlds (doc 12 §4). Translate
with ``simplicial.to_relational`` first. Minimisation (quotienting a model by
:func:`bisimilarity_classes`) is the natural next step and is not implemented.

Depends only on ``relational_frame``, ``knowledge_belief`` and ``semantics``.
"""

from __future__ import annotations

from typing import (
    Dict, FrozenSet, Hashable, Iterable, List, NamedTuple, Optional, Set, Tuple,
)

if __name__ == "__main__":  # running the demo at the bottom of this file
    # This module sits one level below the core modules, so a bare
    # ``python bisimulation/bisimulation.py`` would not find them. Put the
    # repository root on sys.path, as every runnable script here does (doc 11).
    # Skipped on a normal import: then __name__ is "bisimulation.bisimulation"
    # and whoever imported us has already resolved the core modules.
    import os as _os
    import sys as _sys

    _sys.path.insert(
        0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    )

from relational_frame import Agent, World
from semantics import Valuation, lift_valuation, valuation_violations

__all__ = [
    "LabelledTransitionSystem",
    "lts_of_model",
    "disjoint_union",
    "coarsest_stable_partition",
    "bisimilarity_classes",
    "bisimulation",
    "are_bisimilar",
    "projection_violations",
    "projection_is_bisimulation",
    "explain",
]

# An action is a (modality, agent) pair: ("K", a) and ("B", a) for a
# knowledge+belief model, ("R", a) for a bare relational frame. Keeping the
# modality in the label is what lets the two families be refined independently.
Action = Tuple[str, Agent]
State = Hashable
Block = FrozenSet[State]


def _key(value) -> str:
    """Sort key for arbitrary hashable identifiers (worlds, agents, states).

    Everything user-facing in this module is sorted through this so that the
    same input always produces the same blocks in the same order -- the repo's
    usual determinism rule, and what makes the messages diffable.
    """
    return str(value)


class LabelledTransitionSystem(NamedTuple):
    """A model seen as the chapter sees it: states, actions, transitions, labels.

    Attributes:
        states: the state set.
        actions: the action alphabet, in a fixed (sorted) order.
        successors: ``action -> {state -> frozenset of successors}``; every
            state has an entry for every action, possibly empty.
        labels: ``state -> frozenset of atoms true there``. All-empty labels
            mean "no valuation", i.e. bisimilarity of the frame.
    """

    states: FrozenSet[State]
    actions: Tuple[Action, ...]
    successors: Dict[Action, Dict[State, FrozenSet[State]]]
    labels: Dict[State, FrozenSet]


# --------------------------------------------------------------------------- #
# Building the transition system a model induces
# --------------------------------------------------------------------------- #
def lts_of_model(model, valuation: Optional[Valuation] = None) -> LabelledTransitionSystem:
    """View a relational model as a labelled transition system.

    Accepts a :class:`knowledge_belief.KnowledgeBeliefFrame` (actions
    ``("K", a)`` and ``("B", a)``) or a :class:`relational_frame.RelationalFrame`
    (actions ``("R", a)``), recognised by duck typing as everywhere else in the
    repo. Both relations of the knowledge+belief case become actions of their
    own, so refining against them is exactly the back-and-forth clause for
    ``K_a`` and for ``B_a``.

    Args:
        model: the model to view.
        valuation: ``v : P -> 2^W``. Omit it to compare frames (every state gets
            the empty label, so the initial partition is the single block the
            chapter starts from); pass it to compare models, atoms included.

    Raises:
        TypeError: for a simplicial model, or anything else.
        ValueError: if the valuation mentions worlds the model does not have.
    """
    if hasattr(model, "facets"):
        raise TypeError(
            "Bisimilarity here is defined for RELATIONAL models; a simplicial "
            "model needs a chromatic simplicial map instead. Translate it with "
            "simplicial.to_relational(...) and compare the results."
        )
    if hasattr(model, "knowledge") and hasattr(model, "belief"):
        agents = sorted(model.agents, key=_key)
        actions = tuple([("K", a) for a in agents] + [("B", a) for a in agents])
        successors = {
            **{("K", a): {w: frozenset(model.knows(a, w)) for w in model.worlds}
               for a in agents},
            **{("B", a): {w: frozenset(model.believes(a, w)) for w in model.worlds}
               for a in agents},
        }
    elif hasattr(model, "relations"):
        agents = sorted(model.agents, key=_key)
        # One nameless modality: a bare frame does not say whether its relations
        # are knowledge or belief, and bisimilarity does not care -- it only
        # matters that both sides of a comparison use the same tag.
        actions = tuple(("R", a) for a in agents)
        successors = {
            ("R", a): {w: frozenset(model.successors(a, w)) for w in model.worlds}
            for a in agents
        }
    else:
        raise TypeError(
            f"Cannot build a transition system from {type(model).__name__}: "
            "expected a RelationalFrame or a KnowledgeBeliefFrame."
        )

    valuation = valuation or {}
    problems = valuation_violations(model.worlds, valuation)
    if problems:
        raise ValueError(
            f"{len(problems)} valuation violation(s):\n  - " + "\n  - ".join(problems)
        )
    labels = {
        w: frozenset(atom for atom, trues in valuation.items() if w in trues)
        for w in model.worlds
    }
    return LabelledTransitionSystem(
        states=frozenset(model.worlds),
        actions=actions,
        successors=successors,
        labels=labels,
    )


def disjoint_union(
    left: LabelledTransitionSystem, right: LabelledTransitionSystem
) -> LabelledTransitionSystem:
    """Put two transition systems side by side, tagging states ``0``/``1``.

    Bisimilarity *between two models* is bisimilarity *within* their disjoint
    union: refine the union and read off which left state shares a block with
    which right state. Tagging is what keeps the two state sets apart when they
    overlap -- and they do overlap constantly here, since ``to_proper``'s worlds
    are pairs built from the original ones.

    Raises:
        ValueError: if the two systems do not share an action alphabet (that
            means different agents, or a frame compared against a
            knowledge+belief model -- the comparison would be meaningless).
    """
    if left.actions != right.actions:
        raise ValueError(
            "Cannot compare two models with different action alphabets: "
            f"{list(left.actions)} vs {list(right.actions)}. They must have the "
            "same agents, and both be frames or both knowledge+belief models."
        )
    states = frozenset(
        [(0, s) for s in left.states] + [(1, s) for s in right.states]
    )
    successors = {
        action: {
            **{(0, s): frozenset((0, t) for t in targets)
               for s, targets in left.successors[action].items()},
            **{(1, s): frozenset((1, t) for t in targets)
               for s, targets in right.successors[action].items()},
        }
        for action in left.actions
    }
    labels = {
        **{(0, s): atoms for s, atoms in left.labels.items()},
        **{(1, s): atoms for s, atoms in right.labels.items()},
    }
    return LabelledTransitionSystem(states, left.actions, successors, labels)


# --------------------------------------------------------------------------- #
# The algorithm itself
# --------------------------------------------------------------------------- #
def _signature(
    state: State, successors: Dict[State, FrozenSet[State]], block_of: Dict[State, int]
) -> FrozenSet[int]:
    """The set of blocks this state can reach in one ``a``-labelled step.

    This is the quantity the paper's ``split`` compares (Figure 0.1: "if s and t
    can reach the same set of blocks in π via a-labelled transitions"). Two
    states of a block stay together exactly when their signatures agree, for
    every action. Note an empty signature is a perfectly good value: a state
    with no successors is distinguished from one with successors, which is how
    a K45 world with a defunct belief set (``Q_a(w) = ∅``) is kept apart from a
    world that believes something.
    """
    return frozenset(block_of[target] for target in successors.get(state, ()))


def _split(
    block: Block, successors: Dict[State, FrozenSet[State]], block_of: Dict[State, int]
) -> Tuple[Block, ...]:
    """``split(B, a, π)`` of the paper (Figure 0.1), for one action.

    Picks a representative of ``block`` and keeps the states whose signature
    matches its own; the rest become the second half. Returns one block when
    nothing splits. The representative is the ``min`` by name rather than an
    arbitrary element ("choose some state s ∈ B" in the paper) purely so that
    runs are reproducible -- the resulting partition does not depend on it.
    """
    representative = min(block, key=_key)
    target = _signature(representative, successors, block_of)
    keep = frozenset(s for s in block if _signature(s, successors, block_of) == target)
    rest = block - keep
    return (keep, rest) if rest else (keep,)


def coarsest_stable_partition(
    lts: LabelledTransitionSystem,
    initial_partition: Optional[Iterable[Iterable[State]]] = None,
) -> Tuple[Block, ...]:
    """Refine until stable: the Kanellakis-Smolka main loop (Figure 0.2).

    Returns the coarsest partition that refines ``initial_partition`` and is
    *stable* (Def. 0.2.10): no block has some states reaching a given block
    under some action while others do not. For an initial partition coarser
    than bisimilarity -- the single block of a frame, or the partition by atomic
    theory of a model -- that is precisely bisimilarity, by Thm 0.2.6.

    Why it terminates: a pass either changes nothing and the loop ends, or
    splits some block and so strictly increases the number of blocks, which is
    bounded by the number of states. Why it is right: refinement only ever
    separates states that *must* be separated (their successors already lie in
    different blocks), so no two bisimilar states are ever split, and the result
    is stable by construction, which makes it a bisimulation.

    Args:
        lts: the system to refine.
        initial_partition: blocks to start from. Defaults to grouping states by
            their labels -- the single block of the chapter when there are no
            atoms, the atomic theories when there are.
    """
    if initial_partition is None:
        by_label: Dict[FrozenSet, Set[State]] = {}
        for state in lts.states:
            by_label.setdefault(lts.labels.get(state, frozenset()), set()).add(state)
        initial_partition = by_label.values()

    blocks: List[Block] = [frozenset(b) for b in initial_partition if b]
    block_of: Dict[State, int] = {
        state: index for index, block in enumerate(blocks) for state in block
    }

    changed = True
    while changed:
        changed = False
        index = 0
        # `blocks` grows while we walk it; the new halves are visited by this
        # same pass (they sit at the end) or by the next one, and either way the
        # loop only stops when a whole pass splits nothing.
        while index < len(blocks):
            for action in lts.actions:
                parts = _split(blocks[index], lts.successors[action], block_of)
                if len(parts) == 2:
                    keep, rest = parts
                    blocks[index] = keep
                    blocks.append(rest)
                    for state in rest:
                        block_of[state] = len(blocks) - 1
                    changed = True
                    # Carry on with the next action on the (now smaller) block:
                    # it may still be unstable for a modality we have not tried.
            index += 1

    return tuple(sorted(blocks, key=lambda b: tuple(sorted(map(_key, b)))))


# --------------------------------------------------------------------------- #
# What the partition says about models
# --------------------------------------------------------------------------- #
def bisimilarity_classes(
    model, valuation: Optional[Valuation] = None
) -> Tuple[Block, ...]:
    """The bisimilarity classes *inside* one model.

    Worlds in the same class satisfy exactly the same formulas, so this is the
    partition a minimisation would quotient by (not implemented; see the module
    docstring). A class with more than one world means the model says the same
    thing twice -- which is exactly what ``to_proper`` produces on purpose, one
    class per original world.
    """
    return coarsest_stable_partition(lts_of_model(model, valuation))


def bisimulation(
    left,
    right,
    valuation_left: Optional[Valuation] = None,
    valuation_right: Optional[Valuation] = None,
) -> Set[Tuple[World, World]]:
    """The largest bisimulation between two models, as a set of pairs.

    ``(w, w') ∈ bisimulation(M, N)`` iff ``M, w`` and ``N, w'`` satisfy the same
    formulas of the full language (every ``K_a``, every ``B_a``, and the atoms
    when valuations are given). Computed by refining the disjoint union, so
    neither model is privileged.
    """
    union = disjoint_union(
        lts_of_model(left, valuation_left), lts_of_model(right, valuation_right)
    )
    pairs: Set[Tuple[World, World]] = set()
    for block in coarsest_stable_partition(union):
        lefts = [s for side, s in block if side == 0]
        rights = [s for side, s in block if side == 1]
        pairs.update((l, r) for l in lefts for r in rights)
    return pairs


def are_bisimilar(
    left,
    world_left: World,
    right,
    world_right: World,
    valuation_left: Optional[Valuation] = None,
    valuation_right: Optional[Valuation] = None,
) -> bool:
    """True iff the two pointed models are bisimilar (hence modally equivalent)."""
    return (world_left, world_right) in bisimulation(
        left, right, valuation_left, valuation_right
    )


# --------------------------------------------------------------------------- #
# The headline check: is to_proper's projection a bisimulation?
# --------------------------------------------------------------------------- #
def _separation(
    lts: LabelledTransitionSystem, left: State, right: State
) -> Tuple[Optional[Action], int]:
    """Why two states are not bisimilar: which modality, and how deep.

    Asking the *final* partition is useless for this: once refinement is done
    almost every modality separates two states, because their successors have
    themselves been separated. The honest answer is the SHALLOWEST one, so this
    walks the stratified approximants of Def. 0.2.1 -- ``∼_0`` groups states by
    their atoms, ``∼_{k+1}`` refines by one back-and-forth round -- and reports
    the first action that tells the pair apart, together with the ``k`` at which
    it happens. By Hennessy-Milner (Lemma 0.2.2) that ``k`` is exactly the modal
    depth a distinguishing formula needs.

    Returns ``(action, depth)``; ``(None, 0)`` when the atoms already differ.
    """
    states = sorted(lts.states, key=_key)

    def canonical(valued: Dict[State, Hashable]) -> Dict[State, int]:
        """Rename arbitrary class markers to 0, 1, 2, ... so they stay small."""
        identifiers: Dict[Hashable, int] = {}
        return {
            state: identifiers.setdefault(value, len(identifiers))
            for state, value in valued.items()
        }

    level = canonical({s: lts.labels.get(s, frozenset()) for s in states})
    if level[left] != level[right]:
        return None, 0

    def reached(state: State, action: Action) -> FrozenSet[int]:
        return frozenset(level[t] for t in lts.successors[action].get(state, ()))

    depth = 0
    while True:
        depth += 1
        refined = {
            s: (level[s],) + tuple(reached(s, action) for action in lts.actions)
            for s in states
        }
        if refined[left] != refined[right]:
            for action in lts.actions:
                if reached(left, action) != reached(right, action):
                    return action, depth
            return None, depth  # unreachable: something must have differed
        renamed = canonical(refined)
        # Refinement only ever splits, so the partition is unchanged exactly
        # when the number of classes is; that is the fixpoint, and the pair
        # survived it, which means they are bisimilar after all.
        if len(set(renamed.values())) == len(set(level.values())):
            return None, depth
        level = renamed


def projection_violations(
    general, proper, valuation: Optional[Valuation] = None
) -> List[str]:
    """Check that ``to_proper``'s projection really is a bisimulation (Thm 2.4).

    ``to_proper`` returns a model whose ``projection`` maps every new world back
    to the one it simulates. The theorem says that map is a surjective bounded
    morphism, so its graph is a bisimulation: every copy is modally
    indistinguishable from its original. This function verifies that conclusion
    directly -- it runs :func:`coarsest_stable_partition` over the disjoint
    union of the two models and reports every copy whose bisimilarity class is
    not its original's, plus any original left unsimulated.

    The valuation of the proper model is not asked for: it is the lift of the
    general one along the same projection (``semantics.lift_valuation``, thesis
    p. 13), which is the only choice that can possibly work and the one the rest
    of the pipeline uses.

    Args:
        general: the model handed to ``to_proper``.
        proper: what it returned (a ``ProperRelationalFrame`` or
            ``ProperKnowledgeBeliefFrame``).
        valuation: optional ``v : P -> 2^W`` on the GENERAL model's worlds. With
            it the check covers atoms too; without it, the frames.

    Returns:
        A message per violation; empty iff the projection is a bisimulation.

    Raises:
        ValueError: if ``proper`` carries no projection (it did not come from
            ``to_proper``), or the valuation mentions unknown worlds.
    """
    projection = dict(getattr(proper, "projection", {}) or {})
    if not projection:
        raise ValueError(
            "The proper model carries no projection, so there is nothing to "
            "check: pass the model returned by properness.to_proper(...) or "
            "KnowledgeBeliefFrame.to_proper(...), which records ρ(w, u) = w."
        )

    problems: List[str] = []
    stray = sorted(
        (w for w in proper.worlds if projection.get(w) not in general.worlds), key=_key
    )
    if stray:
        problems.append(
            f"Projection leaves the general model: {len(stray)} world(s) map to "
            f"something that is not a world of it, e.g. {stray[:3]}."
        )
        return problems

    missed = sorted(set(general.worlds) - set(projection.values()), key=_key)
    if missed:
        problems.append(
            f"Projection is not surjective: {len(missed)} world(s) of the general "
            f"model are simulated by no copy ({missed[:5]}). Bisimilarity of the "
            "two models needs every original to be reachable from the new one."
        )

    union = disjoint_union(
        lts_of_model(general, valuation),
        lts_of_model(proper, lift_valuation(valuation, projection) if valuation else None),
    )
    blocks = coarsest_stable_partition(union)
    block_of = {state: index for index, block in enumerate(blocks) for state in block}

    for copy in sorted(proper.worlds, key=_key):
        original = projection[copy]
        if block_of[(1, copy)] == block_of[(0, original)]:
            continue
        action, depth = _separation(union, (1, copy), (0, original))
        if depth == 0:
            why = "they already differ on the atoms they satisfy"
        elif action is not None:
            why = f"{action[0]}_{action[1]} tells them apart at modal depth {depth}"
        else:  # defensive: the refinement separated them, so something must
            why = "the refinement separates them"
        problems.append(
            f"Copy {copy!r} is NOT bisimilar to the world it simulates, "
            f"{original!r}: {why}."
        )
    return problems


def projection_is_bisimulation(
    general, proper, valuation: Optional[Valuation] = None
) -> bool:
    """True iff every copy is bisimilar to the world it simulates (Thm 2.4)."""
    return not projection_violations(general, proper, valuation)


def explain(general, proper, valuation: Optional[Valuation] = None) -> str:
    """A human-readable verdict on the general -> proper step."""
    problems = projection_violations(general, proper, valuation)
    if problems:
        lines = [f"NOT BISIMILAR: {len(problems)} problem(s) found:"]
        lines.extend(f"  {message}" for message in problems[:10])
        if len(problems) > 10:
            lines.append(f"  ... and {len(problems) - 10} more")
        return "\n".join(lines)

    # Both quotients, as a second (redundant but informative) reading: a
    # surjective bisimulation makes the two models share their quotient, so the
    # class counts must agree. They are usually FEWER than the number of worlds
    # on either side -- worlds the language cannot tell apart were already
    # identified in the general model, and the copies only add more of them.
    lifted = lift_valuation(valuation, dict(proper.projection)) if valuation else None
    general_classes = bisimilarity_classes(general, valuation)
    proper_classes = bisimilarity_classes(proper, lifted)
    atoms = f"atoms {sorted(map(str, valuation))}" if valuation else "no atoms"
    return (
        f"BISIMILAR ({atoms}): each of the {len(proper.worlds)} worlds of the "
        f"proper model is bisimilar to the world it simulates, so the "
        f"{len(general.worlds)} worlds of the general model keep their modal "
        f"theory. Both models have {len(proper_classes)} bisimilarity class(es) "
        f"({len(general_classes)} computed on the general one), which is what a "
        "surjective bisimulation guarantees: the copies added redundancy, not "
        "information."
    )


# --------------------------------------------------------------------------- #
# Demo: python bisimulation.py
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    from knowledge_belief import KnowledgeBeliefFrame

    WORLDS = ["w0", "w1", "w2"]

    def figure1() -> KnowledgeBeliefFrame:
        """Sink's Figure 1: nobody knows anything, a believes {w1,w2}, b w1, c w2."""
        return KnowledgeBeliefFrame.from_beliefs_only(
            ["a", "b", "c"], WORLDS,
            {"a": {(w, u) for w in WORLDS for u in ("w1", "w2")},
             "b": {(w, "w1") for w in WORLDS},
             "c": {(w, "w2") for w in WORLDS}},
        )

    print("=" * 74)
    print("1. The claim of Thm 2.4, checked by partition refinement")
    print("=" * 74)
    general = figure1()
    proper = general.to_proper()
    print(f"   general: {general!r}\n   proper : {proper!r}\n")
    print(explain(general, proper, {"P": {"w1"}}))

    print()
    print("=" * 74)
    print("2. The checker is not vacuous: two models that are NOT bisimilar")
    print("=" * 74)
    # Same frame, but b is sure of w2 instead of w1. Under P = {w1} that is a
    # real difference: in the first model b believes P, in the second it does not.
    other = KnowledgeBeliefFrame.from_beliefs_only(
        ["a", "b", "c"], WORLDS,
        {"a": {(w, u) for w in WORLDS for u in ("w1", "w2")},
         "b": {(w, "w2") for w in WORLDS},
         "c": {(w, "w2") for w in WORLDS}},
    )
    v = {"P": {"w1"}}
    print(f"   are_bisimilar(figure1, w0, other, w0, P={{w1}}) -> "
          f"{are_bisimilar(general, 'w0', other, 'w0', v, v)}")
    print(f"   ...and without atoms, the frames alone          -> "
          f"{are_bisimilar(general, 'w0', other, 'w0')}")
    print("   (the frames are isomorphic up to renaming w1/w2, so they only come")
    print("    apart once an atom singles w1 out -- exactly what B_b P sees.)")

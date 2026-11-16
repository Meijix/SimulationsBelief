# -*- coding: utf-8 -*-
"""Bisimilarity between relational models, by partition refinement.

Checks the claim of Sink's Thm 2.4 that ``to_proper`` returns a model bisimilar
to its input: the largest bisimulation is computed from scratch (Kanellakis &
Smolka's coarsest stable partition) and every copy must land in the class of
the world it simulates (:func:`projection_violations`).

    π := the initial partition (one block, or the partition by atomic theory)
    repeat until nothing changed:
        for each block B, for each action a:
            if split(B, a, π) != {B}: replace B by the two halves

Actions are ``("K", a)``, ``("B", a)`` for a knowledge+belief model and
``("R", a)`` for a bare frame, so stability under every action is the
back-and-forth clause for every modality. Algorithm, correctness and the
diagnostic of :func:`_separation`: docs/14. Simplicial models are not handled
(translate with ``simplicial.to_relational`` first).
"""

from __future__ import annotations

from typing import (
    Dict, FrozenSet, Hashable, Iterable, List, NamedTuple, Optional, Set, Tuple,
)

if __name__ == "__main__":  # the demo below needs the repo root on sys.path
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

Action = Tuple[str, Agent]   # (modality, agent)
State = Hashable
Block = FrozenSet[State]


def _key(value) -> str:
    """Sort key for identifiers, so runs and messages are deterministic."""
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

    A :class:`KnowledgeBeliefFrame` gives actions ``("K", a)`` and ``("B", a)``,
    a :class:`RelationalFrame` ``("R", a)``. Without ``valuation`` every state
    gets the empty label (bisimilarity of frames); with it, its atoms.

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
    """Put two systems side by side, tagging states ``0``/``1``: bisimilarity
    between two models is bisimilarity within their disjoint union.

    Raises:
        ValueError: if the action alphabets differ (different agents, or a
            frame against a knowledge+belief model).
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
    """The blocks ``state`` reaches in one step of this action (the quantity
    ``split`` compares). An empty signature is a value of its own: a defunct
    K45 world is kept apart from one that believes something."""
    return frozenset(block_of[target] for target in successors.get(state, ()))


def _split(
    block: Block, successors: Dict[State, FrozenSet[State]], block_of: Dict[State, int]
) -> Tuple[Block, ...]:
    """``split(B, a, π)`` (Kanellakis & Smolka, Fig. 0.1) for one action: the
    states whose signature matches the representative's, and the rest. The
    representative is the min by name only for reproducibility."""
    representative = min(block, key=_key)
    target = _signature(representative, successors, block_of)
    keep = frozenset(s for s in block if _signature(s, successors, block_of) == target)
    rest = block - keep
    return (keep, rest) if rest else (keep,)


def coarsest_stable_partition(
    lts: LabelledTransitionSystem,
    initial_partition: Optional[Iterable[Iterable[State]]] = None,
) -> Tuple[Block, ...]:
    """The coarsest stable partition refining ``initial_partition`` (Kanellakis &
    Smolka, Fig. 0.2); for a start coarser than bisimilarity it IS bisimilarity
    (Thm 0.2.6). The default start groups states by their labels.
    Termination and correctness: docs/14 §3."""
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
        while index < len(blocks):   # blocks grows while walked; new halves are visited too
            for action in lts.actions:
                parts = _split(blocks[index], lts.successors[action], block_of)
                if len(parts) == 2:
                    keep, rest = parts
                    blocks[index] = keep
                    blocks.append(rest)
                    for state in rest:
                        block_of[state] = len(blocks) - 1
                    changed = True
            index += 1

    return tuple(sorted(blocks, key=lambda b: tuple(sorted(map(_key, b)))))


# --------------------------------------------------------------------------- #
# What the partition says about models
# --------------------------------------------------------------------------- #
def bisimilarity_classes(
    model, valuation: Optional[Valuation] = None
) -> Tuple[Block, ...]:
    """The bisimilarity classes inside one model: worlds in a class satisfy the
    same formulas (``to_proper`` produces one class per original world)."""
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
    """Why two states are not bisimilar: the first action that tells them apart
    along the stratified approximants ``∼_k``, and the depth ``k`` (the modal
    depth of a distinguishing formula, Hennessy-Milner). ``(None, 0)`` when the
    atoms already differ. See docs/14 §4.7."""
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
    """Check that ``to_proper``'s projection is a bisimulation (Thm 2.4): every
    copy must share its bisimilarity class with the world it simulates, and
    every original must be simulated. ``valuation`` is the general model's; the
    proper one gets its lift.

    Returns:
        A message per violation; empty iff the projection is a bisimulation.

    Raises:
        ValueError: ``proper`` carries no projection, or unknown worlds in the valuation.
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

    # A surjective bisimulation makes the two models share their quotient, so
    # the class counts agree.
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

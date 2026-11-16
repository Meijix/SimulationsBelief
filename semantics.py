"""Valuations and formula semantics on both sides of the translation (thesis ch. 2).

Kripke side: a valuation ``v : P -> 2^W``; ``K_a`` quantifies over ``R_a(w)``,
``B_a`` over ``Q_a(w)`` (:func:`holds_kripke`). Simplicial side: a facet
valuation ``L : P -> 2^F(S)``; ``K_a`` over the facets sharing ``a``'s vertex,
``B_a`` over those of ``S_a`` (:func:`holds_simplicial`). The translation
carries valuations along: :func:`lift_valuation` (general -> proper, thesis
p. 13) and :func:`facet_valuation` (proper -> simplicial, Lemma 2.6).

The project's canonical route puts atoms on the VERTICES instead
(``assignment.py``, thesis ch. 3); ``assignment.lift_to_facets`` turns a vertex
assignment into a facet valuation for this module, and the two agree on every
formula. They differ from a Kripke valuation only where NU fails
(``assignment.nu_violations``). See docs/08.

Formulas are plain tuples, shared with ``assignment.py``:

    ("atom", P) | ("bot",) | ("imp", f, g) | ("K", a, f) | ("B", a, f)
    sugar: ("not", f), ("and", f, g), ("or", f, g)

:func:`evaluate` is the one recursion over the connectives; each semantics
supplies its atom test and its modal successor sets.
"""

from __future__ import annotations

from typing import Callable, Dict, Hashable, Iterable, List, Set

from knowledge_belief import KnowledgeBeliefFrame
from relational_frame import RelationalFrame, World
from simplicial import Facet, SimplicialBeliefModel

Atom = Hashable
Valuation = Dict[Atom, Set[World]]        # v : P -> 2^W   (Kripke side)
FacetValuation = Dict[Atom, Set[Facet]]   # L : P -> 2^F(S) (simplicial side)


def evaluate(
    formula,
    point,
    atom: Callable[[object, Atom], bool],
    successors: Callable[[str, Hashable, object], Iterable],
) -> bool:
    """Truth of ``formula`` at ``point`` (a world or a facet).

    ``atom(point, P)`` decides the atoms; ``successors(tag, agent, point)`` gives
    the points ``K_a`` (``tag="K"``) or ``B_a`` (``tag="B"``) quantify over.

    Raises:
        ValueError: on an unknown connective.
    """
    tag = formula[0]
    if tag == "atom":
        return atom(point, formula[1])
    if tag == "bot":
        return False
    if tag == "imp":
        return (not evaluate(formula[1], point, atom, successors)) or evaluate(
            formula[2], point, atom, successors
        )
    if tag == "not":
        return not evaluate(formula[1], point, atom, successors)
    if tag == "and":
        return evaluate(formula[1], point, atom, successors) and evaluate(
            formula[2], point, atom, successors
        )
    if tag == "or":
        return evaluate(formula[1], point, atom, successors) or evaluate(
            formula[2], point, atom, successors
        )
    if tag in ("K", "B"):
        return all(
            evaluate(formula[2], q, atom, successors)
            for q in successors(tag, formula[1], point)
        )
    raise ValueError(f"Unknown connective {tag!r} in formula {formula!r}.")


def facet_successors(model: SimplicialBeliefModel) -> Callable:
    """The modal clause of both simplicial semantics: ``K_a`` ranges over the
    facets of ``S`` sharing ``a``'s vertex, ``B_a`` over those of ``S_a``."""
    def successors(tag, agent, facet):
        if tag == "K":
            return model.knows_facets(agent, facet)
        return model.believes_facets(agent, facet)
    return successors


def valuation_violations(worlds, valuation: Valuation) -> List[str]:
    """A message per atom whose truth set mentions an unknown world."""
    world_set = set(worlds)
    problems: List[str] = []
    for atom, trues in valuation.items():
        stray = set(trues) - world_set
        if stray:
            problems.append(
                f"Valuation of atom {atom!r} mentions {len(stray)} unknown "
                f"world(s): {sorted(map(str, stray))[:5]}."
            )
    return problems


# --------------------------------------------------------------------------- #
# Kripke side (thesis p. 9-10)
# --------------------------------------------------------------------------- #
def holds_kripke(model, valuation: Valuation, world: World, formula) -> bool:
    """Decide ``N, world |= formula`` on a relational model.

    ``model`` is a :class:`KnowledgeBeliefFrame` (``K_a`` over ``R_a(w)``,
    ``B_a`` over ``Q_a(w)``) or a plain S5 :class:`RelationalFrame` (knowledge
    only; a ``B_a`` formula is refused with a pointer to the two-relation class).

    Raises:
        ValueError: On an unknown connective, or ``B_a`` over a frame that has
            no belief relations.
    """
    kb = isinstance(model, KnowledgeBeliefFrame)

    def successors(tag, agent, w):
        if kb:
            return model.knows(agent, w) if tag == "K" else model.believes(agent, w)
        if tag == "B" and model.logic_label() == "S5":
            raise ValueError(
                "B_a needs a belief relation, but this RelationalFrame is a "
                "knowledge (S5) frame. Express the formula with K_a, or use a "
                "KnowledgeBeliefFrame."
            )
        # A plain frame is the one relation: knowledge if S5, belief otherwise.
        return model.successors(agent, w)

    return evaluate(formula, world, lambda w, P: w in valuation.get(P, ()), successors)


# --------------------------------------------------------------------------- #
# Carrying the valuation through the pipeline
# --------------------------------------------------------------------------- #
def lift_valuation(
    valuation: Valuation, projection: Dict[World, World]
) -> Valuation:
    """Lift ``v`` through general -> proper: each copy inherits its original's
    atoms, ``v~(P) = ρ^{-1}[v(P)]`` (thesis p. 13). Pass the frame's ``projection``."""
    return {
        atom: {w2 for w2, w0 in projection.items() if w0 in trues}
        for atom, trues in valuation.items()
    }


def facet_valuation(
    model: SimplicialBeliefModel, valuation: Valuation
) -> FacetValuation:
    """The facet valuation ``L_N(P) = f[v(P)]`` of a translated model (thesis p. 9):
    ``P`` holds at a facet iff it held at the world the facet came from.

    Raises:
        ValueError: if the valuation mentions worlds the model does not have.
    """
    worlds = set(model.world_of_facet.values())
    problems = valuation_violations(worlds, valuation)
    if problems:
        raise ValueError(
            f"{len(problems)} valuation violation(s):\n  - " + "\n  - ".join(problems)
        )
    return {
        atom: {F for F, w in model.world_of_facet.items() if w in trues}
        for atom, trues in valuation.items()
    }


# --------------------------------------------------------------------------- #
# Simplicial side (thesis p. 8): facet valuations, chapter-2 semantics
# --------------------------------------------------------------------------- #
def holds_simplicial(
    model: SimplicialBeliefModel,
    valuation: FacetValuation,
    facet: Facet,
    formula,
) -> bool:
    """Decide ``M, facet |= formula`` under the chapter-2 (facet valuation) semantics.

    Raises:
        ValueError: on an unknown connective.
    """
    return evaluate(
        formula, facet, lambda F, P: F in valuation.get(P, ()), facet_successors(model)
    )

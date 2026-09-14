"""Valuations and formula semantics on BOTH sides of the translation (thesis ch. 2).

This module adds the logical layer chapter 2 of Sink's thesis puts on top of the
structural pipeline:

    Kripke side (p. 9-10). A relational model is a frame plus a valuation
    ``v : P -> 2^W`` (which worlds make each atom true). Truth is the usual
    recursion: atoms by membership, ``K_a`` quantifying over ``R_a(w)``, ``B_a``
    over ``Q_a(w)`` -- :func:`holds_kripke`.

    Simplicial side (p. 8). A simplicial model carries a FACET valuation
    ``L : P -> 2^F(S)``; ``X |= P`` iff ``X ∈ L(P)``, ``K_a`` quantifies over the
    facets of ``S`` sharing ``a``'s vertex, ``B_a`` over those of ``S_a`` --
    :func:`holds_simplicial`.

    The translation carries the valuation along (and truth with it):

      * general -> proper (p. 13): the copies inherit the original world's atoms,
        ``v~(P) = {(x, y) : x ∈ v(P)}`` -- :func:`lift_valuation`, phrased through
        the bisimulation projection ``ρ`` so it composes with this repo's
        ``to_proper`` output directly. ``ρ`` is a bounded morphism for every
        ``R_a`` and ``Q_a``, so ``w`` and each copy ``(w, u)`` satisfy the same
        formulas.
      * proper -> simplicial (p. 9, Lemma 2.6): ``L_N(P) = f[v(P)]`` = the facets
        of the worlds where ``P`` holds -- :func:`facet_valuation`; then
        ``N, w |= φ  iff  M_N, f(w) |= φ`` for the whole language ``L_KB``.

ROLE IN THIS PROJECT: the facet valuation here is the chapter-2 REFERENCE and
the exact bridge to Kripke valuations; the project's CANONICAL approach is the
vertex-based one of ``assignment.py`` (atoms assigned partially to the
vertices, truth lifted to facets -- ``assignment.lift_to_facets`` produces a
facet valuation this module's evaluator consumes, and the two evaluators agree
on every formula over a lifted valuation). Prefer the vertex route when
modelling; come through here when you start from an arbitrary Kripke valuation
``v``, because not every ``v`` is vertex-representable: the two chains coincide
exactly when ``v`` has "no uncertainties" (some agent always knows each atom's
value, the NU schema), and ``assignment.nu_violations`` locates the divergences.

Formulas are the same plain tuples used by ``assignment.py``:

    ("atom", P) | ("bot",) | ("imp", f, g) | ("K", a, f) | ("B", a, f)
    sugar: ("not", f), ("and", f, g), ("or", f, g)

Depends on ``knowledge_belief`` and ``simplicial``.
"""

from __future__ import annotations

from typing import Dict, Hashable, List, Set

from knowledge_belief import KnowledgeBeliefFrame
from relational_frame import RelationalFrame, World
from simplicial import Facet, SimplicialBeliefModel

Atom = Hashable
Valuation = Dict[Atom, Set[World]]        # v : P -> 2^W   (Kripke side)
FacetValuation = Dict[Atom, Set[Facet]]   # L : P -> 2^F(S) (simplicial side)


def valuation_violations(worlds, valuation: Valuation) -> List[str]:
    """Return a message per atom whose truth set mentions an unknown world."""
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
    tag = formula[0]
    if tag == "atom":
        return world in valuation.get(formula[1], ())
    if tag == "bot":
        return False
    if tag == "imp":
        return (not holds_kripke(model, valuation, world, formula[1])) or (
            holds_kripke(model, valuation, world, formula[2])
        )
    if tag == "not":
        return not holds_kripke(model, valuation, world, formula[1])
    if tag == "and":
        return holds_kripke(model, valuation, world, formula[1]) and holds_kripke(
            model, valuation, world, formula[2]
        )
    if tag == "or":
        return holds_kripke(model, valuation, world, formula[1]) or holds_kripke(
            model, valuation, world, formula[2]
        )
    if tag == "K":
        successors = (
            model.knows(formula[1], world)
            if isinstance(model, KnowledgeBeliefFrame)
            else model.successors(formula[1], world)
        )
        return all(holds_kripke(model, valuation, u, formula[2]) for u in successors)
    if tag == "B":
        if not isinstance(model, KnowledgeBeliefFrame):
            raise ValueError(
                "B_a needs a belief relation, but this is a plain RelationalFrame "
                "(knowledge only). Use a KnowledgeBeliefFrame, or express the "
                "formula with K_a."
            )
        return all(
            holds_kripke(model, valuation, u, formula[2])
            for u in model.believes(formula[1], world)
        )
    raise ValueError(f"Unknown connective {tag!r} in formula {formula!r}.")


# --------------------------------------------------------------------------- #
# Carrying the valuation through the pipeline
# --------------------------------------------------------------------------- #
def lift_valuation(
    valuation: Valuation, projection: Dict[World, World]
) -> Valuation:
    """Lift ``v`` through a general -> proper conversion (thesis p. 13).

    Each copy inherits its original world's atoms: ``v~(P) = ρ^{-1}[v(P)]``,
    which for the W×W construction is exactly the thesis's
    ``{(x, y) : x ∈ v(P)}``. Pass the ``projection`` attribute of the frame
    ``to_proper`` returned (the identity projection of an already-proper model
    leaves the valuation unchanged).

    Because ``ρ`` is a bounded morphism for every relation, ``w`` and every copy
    in ``ρ^{-1}(w)`` satisfy exactly the same formulas under the lifted valuation.
    """
    return {
        atom: {w2 for w2, w0 in projection.items() if w0 in trues}
        for atom, trues in valuation.items()
    }


def facet_valuation(
    model: SimplicialBeliefModel, valuation: Valuation
) -> FacetValuation:
    """Translate a world valuation into the facet valuation ``L_N(P) = f[v(P)]``.

    Defined for the simplicial model of a PROPER relational model (thesis p. 9):
    there ``f`` is a bijection worlds <-> facets (``model.world_of_facet`` is its
    inverse), so ``P`` is true at a facet exactly when it was true at the world
    the facet came from -- the definition that makes Lemma 2.6 (truth
    preservation) go through for the full language ``L_KB``.

    Raises:
        ValueError: If the valuation mentions worlds the model does not have.
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
    """Decide ``M, facet |= formula`` under the chapter-2 semantics.

    Atoms by facet membership (``X ∈ L(P)``); ``K_a`` over the facets of ``S``
    sharing ``a``'s vertex with ``facet``; ``B_a`` over those of ``S_a``.

    Raises:
        ValueError: On an unknown connective.
    """
    tag = formula[0]
    if tag == "atom":
        return facet in valuation.get(formula[1], ())
    if tag == "bot":
        return False
    if tag == "imp":
        return (not holds_simplicial(model, valuation, facet, formula[1])) or (
            holds_simplicial(model, valuation, facet, formula[2])
        )
    if tag == "not":
        return not holds_simplicial(model, valuation, facet, formula[1])
    if tag == "and":
        return holds_simplicial(model, valuation, facet, formula[1]) and (
            holds_simplicial(model, valuation, facet, formula[2])
        )
    if tag == "or":
        return holds_simplicial(model, valuation, facet, formula[1]) or (
            holds_simplicial(model, valuation, facet, formula[2])
        )
    if tag == "K":
        p = model.pi(formula[1], facet)
        return all(
            holds_simplicial(model, valuation, Y, formula[2])
            for Y in model.facets
            if model.pi(formula[1], Y) == p
        )
    if tag == "B":
        return all(
            holds_simplicial(model, valuation, Y, formula[2])
            for Y in model.believes_facets(formula[1], facet)
        )
    raise ValueError(f"Unknown connective {tag!r} in formula {formula!r}.")

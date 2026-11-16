"""Three-valued vertex assignments and the chapter-3 belief semantics (Sink's thesis).

The project's canonical logical layer: an assignment ``L : N -> 3^P`` records
what each perspective (node) observes about each atom, ``1`` true, ``0`` false,
``2`` nothing (the default for an unmentioned atom). Truth at a facet is read
off its perspectives (thesis p. 20): ``X ⊨ P`` iff some node of ``X`` carries
``P`` with value 1; ``B_a`` quantifies over the facets of ``S_a`` sharing
``a``'s node; ``K_a`` (an extension of the chapter's belief-only language)
over all facets sharing it. Consequences: facets must be CONSISTENT (no atom
1 at one node and 0 at another; :func:`maximal_complex` builds the complex of
all consistent facets, :func:`drop_inconsistent` prunes a declared one), and
the schema NU ``P → ∨_a B_a P`` is sound (:func:`nu_violations` shows where a
Kripke valuation is not representable). Theory and examples: docs/08.

Formulas are plain tuples, shared with ``semantics.py``: ``("atom", P)``,
``("bot",)``, ``("imp", f, g)``, ``("B", a, f)``, ``("K", a, f)``, and the sugar
``("not", f)``, ``("and", f, g)``, ``("or", f, g)``.
"""

from __future__ import annotations

from itertools import product
from typing import Dict, Hashable, Iterable, List, Set, Tuple

from semantics import evaluate, facet_successors
from simplicial import Facet, Node, SimplicialBeliefModel, label_facet, label_node

Atom = Hashable
# L : node -> {atom -> value in {0, 1, 2}}. Missing node or atom means 2.
Assignment = Dict[Node, Dict[Atom, int]]

TRUE, FALSE, UNKNOWN = 1, 0, 2
_VALUES = {TRUE, FALSE, UNKNOWN}


def node_value(assignment: Assignment, node: Node, atom: Atom) -> int:
    """Return ``L(node)(atom)`` with the chapter's default: unmentioned means 2."""
    return assignment.get(node, {}).get(atom, UNKNOWN)


def assignment_violations(assignment: Assignment) -> List[str]:
    """Return a message per ill-formed entry (empty list if well-formed).

    The only requirement is that every value is 0, 1 or 2 -- the three truth
    values of the chapter. Nodes and atoms are free identifiers.
    """
    problems: List[str] = []
    for node, atoms in assignment.items():
        for atom, value in atoms.items():
            if value not in _VALUES:
                problems.append(
                    f"Assignment value for atom {atom!r} at node "
                    f"{node.agent!r}:{sorted(map(str, node.cls))} is {value!r}; "
                    f"it must be 0 (false), 1 (true) or 2 (unknown)."
                )
    return problems


def facet_inconsistencies(
    facet: Facet, assignment: Assignment
) -> List[Tuple[Atom, Node, Node]]:
    """Return every ``(atom, node_true, node_false)`` clash inside ``facet``.

    A facet is consistent (thesis p. 19) when no atom is observed TRUE by one of
    its perspectives and FALSE by another. Value 2 clashes with nothing.
    """
    clashes: List[Tuple[Atom, Node, Node]] = []
    atoms = {atom for n in facet for atom in assignment.get(n, {})}
    for atom in sorted(atoms, key=str):
        trues = [n for n in facet if node_value(assignment, n, atom) == TRUE]
        falses = [n for n in facet if node_value(assignment, n, atom) == FALSE]
        clashes.extend((atom, t, f) for t in trues for f in falses)
    return clashes


def is_consistent_facet(facet: Facet, assignment: Assignment) -> bool:
    """True iff no atom is 1 at one node of ``facet`` and 0 at another."""
    return not facet_inconsistencies(facet, assignment)


def consistency_violations(
    model: SimplicialBeliefModel, assignment: Assignment
) -> List[str]:
    """A message per inconsistent facet, naming the atom and the two clashing nodes."""
    problems: List[str] = []
    for facet in sorted(model.facets, key=label_facet):
        for atom, node_true, node_false in facet_inconsistencies(facet, assignment):
            problems.append(
                f"Facet {label_facet(facet)} is inconsistent on atom {atom!r}: "
                f"{label_node(node_true)} observes it TRUE (1) while "
                f"{label_node(node_false)} observes it FALSE (0), so the facet "
                f"would satisfy both {atom!r} and its negation."
            )
    return problems


def require_consistent(
    model: SimplicialBeliefModel, assignment: Assignment
) -> None:
    """Raise unless every facet is consistent (thesis p. 19), the precondition of
    the semantics: :func:`holds` reads only the 1s, which is sound only then.

    Raises:
        ValueError: listing every clash.
    """
    problems = consistency_violations(model, assignment)
    if not problems:
        return
    raise ValueError(
        f"{len(problems)} facet-consistency violation(s): an atom is observed "
        f"TRUE by one perspective of a facet and FALSE by another, so that facet "
        f"would satisfy an atom and its negation at once. The chapter-3 semantics "
        f"is undefined there, so nothing is evaluated.\n  - "
        + "\n  - ".join(problems)
        + "\nFix the assignment (value 2 = 'says nothing' clashes with nothing), "
        "or build the complex with maximal_complex(), which keeps only the "
        "consistent facets."
    )


def maximal_complex(
    agents: Iterable[Hashable],
    nodes: Iterable[Node],
    assignment: Assignment,
) -> Set[Facet]:
    """The facets of the maximal complex ``M(N, V, L)`` (thesis p. 19): every UCF
    facet (one node per agent) whose perspectives are jointly consistent.

    Raises:
        ValueError: ill-formed assignment, or an agent with no node.
    """
    problems = assignment_violations(assignment)
    if problems:
        raise ValueError(
            f"{len(problems)} assignment violation(s):\n  - " + "\n  - ".join(problems)
        )
    agent_list = sorted(set(agents), key=str)
    by_agent: Dict[Hashable, List[Node]] = {a: [] for a in agent_list}
    for n in nodes:
        if n.agent in by_agent:
            by_agent[n.agent].append(n)
    empty = [str(a) for a in agent_list if not by_agent[a]]
    if empty:
        raise ValueError(
            f"maximal_complex needs at least one node per agent; agent(s) "
            f"{empty} have none, so no UCF facet exists."
        )
    return {
        frozenset(combo)
        for combo in product(*(by_agent[a] for a in agent_list))
        if is_consistent_facet(frozenset(combo), assignment)
    }


def maximal_model(
    agents: Iterable[Hashable],
    nodes: Iterable[Node],
    assignment: Assignment,
    belief_facets: Dict[Hashable, Iterable[Facet]] | None = None,
    **kwargs,
) -> SimplicialBeliefModel:
    """The model ``M(N, V, L)`` of thesis p. 19: the maximal complex, read as
    knowledge without ``belief_facets``, else with each ``S_a`` restricted to the
    facets that survive. Keyword arguments go to the constructor."""
    facets = maximal_complex(agents, nodes, assignment)
    if belief_facets is None:
        return SimplicialBeliefModel.knowledge_only(agents, nodes, facets, **kwargs)
    belief = {a: set(fs) & facets for a, fs in belief_facets.items()}
    return SimplicialBeliefModel(agents, nodes, facets, belief, **kwargs)


def drop_inconsistent(
    model: SimplicialBeliefModel, assignment: Assignment
) -> Tuple[SimplicialBeliefModel, List[Facet]]:
    """``(model without its inconsistent facets, the facets removed)``.

    An inconsistent facet is not an error but a facet that does not exist
    (ch. 3 works with the maximal consistent complex). Removed from ``S`` and
    every ``S_a``; names and the declared Axiom-D contract are kept, nothing is
    validated here.
    """
    bad = {F for F in model.facets if not is_consistent_facet(F, assignment)}
    if not bad:
        return model, []
    keep = model.facets - bad
    pruned = SimplicialBeliefModel(
        model.agents, model.nodes, keep,
        {a: set(fs) - bad for a, fs in model.belief_facets.items()},
        world_of_facet={F: w for F, w in model.world_of_facet.items() if F in keep},
        projection={F: w for F, w in model.projection.items() if F in keep},
        validate=False,
        axiom_d=getattr(model, "axiom_d_declared", model.axiom_d),
        node_names=getattr(model, "node_names", None),
    )
    return pruned, sorted(bad, key=label_facet)


# --------------------------------------------------------------------------- #
# Semantics (thesis p. 20)
# --------------------------------------------------------------------------- #
def holds(
    model: SimplicialBeliefModel,
    assignment: Assignment,
    facet: Facet,
    formula,
    check_consistency: bool = True,
) -> bool:
    """Decide ``M, facet |= formula`` under the chapter-3 semantics.

    An atom is true iff some node of the facet carries it with value 1 (the
    lift, sound on consistent facets only, hence the whole-model consistency
    check first). Pass ``check_consistency=False`` only right after
    :func:`require_consistent` on the same pair.

    Raises:
        ValueError: an inconsistent facet, or an unknown connective.
    """
    if check_consistency:
        require_consistent(model, assignment)
    return _holds(model, assignment, facet, formula)


def _holds(model: SimplicialBeliefModel, assignment: Assignment, facet: Facet, formula) -> bool:
    """The recursion of :func:`holds`, with consistency already established."""
    return evaluate(
        formula, facet,
        lambda F, P: any(node_value(assignment, n, P) == TRUE for n in F),
        facet_successors(model),
    )


# --------------------------------------------------------------------------- #
# Bridge from the Kripke side: induce L from a world valuation
# --------------------------------------------------------------------------- #
def assignment_from_model(
    model: SimplicialBeliefModel,
    valuation: Dict[Atom, Set],
) -> Assignment:
    """Induce the node assignment from a Kripke valuation: a perspective observes
    what its agent knows in that class (``P`` at every world -> 1, at none ->
    0, mixed -> 2). Consistent by construction; agrees with world truth exactly
    where NU holds (:func:`nu_violations`).

    ``valuation`` may name the model's own worlds or, for a model that came
    through ``to_proper``, the original worlds (carried to every copy).

    Raises:
        ValueError: an atom names a world that is neither.
    """
    worlds = set(model.world_of_facet.values())
    originals = set(model.projection.values())
    by_original: Dict[Hashable, Set] = {}
    for facet, world in model.world_of_facet.items():
        if facet in model.projection:
            by_original.setdefault(model.projection[facet], set()).add(world)
    resolved: Dict[Atom, Set] = {}
    for atom, true_worlds in valuation.items():
        given = set(true_worlds)
        unknown = given - worlds
        if unknown and unknown <= originals:
            # Named by the general model's worlds: expand to their copies.
            given = (given & worlds) | {w for o in unknown for w in by_original[o]}
        elif unknown:
            raise ValueError(
                f"assignment_from_model: atom {atom!r} is said to be true at "
                f"{sorted(map(str, unknown))}, which are not worlds of the model "
                f"(worlds: {sorted(map(str, worlds))}"
                + (f"; original worlds: {sorted(map(str, originals))}" if originals else "")
                + ")."
            )
        resolved[atom] = given
    out: Assignment = {}
    for node in model.nodes:
        for atom, true_worlds in resolved.items():
            inside = node.cls & true_worlds
            if inside == node.cls:
                out.setdefault(node, {})[atom] = TRUE
            elif not inside:
                out.setdefault(node, {})[atom] = FALSE
            # mixed -> leave unmentioned = UNKNOWN
    return out


def lift_to_facets(
    model: SimplicialBeliefModel,
    assignment: Assignment,
) -> Dict[Atom, Set[Facet]]:
    """Lift a vertex assignment to a chapter-2 facet valuation,
    ``L'(P) = {X : some node of X has L(n)(P) = 1}``, for anything built on
    ``semantics.FacetValuation``. The two evaluators then agree on every formula.

    Raises:
        ValueError: if some facet is inconsistent (the lift reads only the 1s).
    """
    require_consistent(model, assignment)
    atoms = {atom for values in assignment.values() for atom in values}
    return {
        atom: {F for F in model.facets if any(node_value(assignment, n, atom) == TRUE for n in F)}
        for atom in atoms
    }


def nu_violations(
    model: SimplicialBeliefModel,
    assignment: Assignment,
    valuation: Dict[Atom, Set],
) -> List[Tuple[Atom, Facet]]:
    """The ``(atom, facet)`` pairs where facet truth differs from world truth:
    the atom is true at the world but no agent knows it, a failure of NU for
    that valuation. Empty iff the valuation is representable in ch. 3."""
    require_consistent(model, assignment)
    out: List[Tuple[Atom, Facet]] = []
    for atom, true_worlds in valuation.items():
        true_set = set(true_worlds)
        for facet, world in model.world_of_facet.items():
            facet_truth = _holds(model, assignment, facet, ("atom", atom))
            if facet_truth != (world in true_set):
                out.append((atom, facet))
    return out

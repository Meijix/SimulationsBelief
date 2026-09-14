"""Three-valued node assignments and belief semantics (Sink's thesis, ch. 3).

THIS IS THE PROJECT'S CANONICAL "VERTEX-BASED" APPROACH: atoms are assigned --
partially, silence is value 2 -- to the VERTICES, and truth is then *lifted* to
the facets (an atom holds at a facet iff some vertex of it carries the atom with
value 1; :func:`lift_to_facets` materialises that lift as a chapter-2-style
facet valuation). The facet-based valuation of ch. 2 lives in ``semantics.py``
as the thesis reference and the direct Kripke bridge; the two evaluators agree
on every formula whenever the facet valuation IS the lift of the vertex one.

Chapter 3 of the thesis moves the logical content of a simplicial model from the
FACETS (where ch. 2 / Bjorndahl & Sink put it) to the NODES: each node is an
agent's *perspective*, and an assignment ``L : N -> 3^P`` records what that
perspective directly observes about each atom:

    * ``L(n)(P) = 1``  --  ``P`` is associated with ``n`` (observed TRUE),
    * ``L(n)(P) = 0``  --  ``¬P`` is associated with ``n`` (observed FALSE),
    * ``L(n)(P) = 2``  --  neither (the perspective SAYS NOTHING about ``P``).

An atom the assignment does not mention is value ``2``: silence is the default,
never an error.

Truth at a facet is then read off its perspectives (thesis p. 20):

    M, X |= P        iff  some node of ``X`` carries ``P`` with value 1
    M, X |= φ → ψ    as usual (⊥ never holds; ¬φ is φ → ⊥)
    M, X |= B_a φ    iff  φ holds at every facet of ``S_a`` sharing a's node with X

Two consequences worth knowing (both from the chapter):

    * A facet must be CONSISTENT: no atom with a 1-node and a 0-node in the same
      facet. The **maximal complex** ``M(N, V, L)`` is the set of all UCF,
      consistent facets buildable from the nodes -- :func:`maximal_complex`.
    * The schema **NU** ("no uncertainties", ``P → ∨_a B_a P``) is sound: an atom
      is true at a facet only when some agent's perspective carries it. When an
      assignment is INDUCED from a Kripke valuation (:func:`assignment_from_model`),
      the facet truth of ``P`` agrees with the world truth exactly where some agent
      KNOWS ``P`` -- :func:`nu_violations` lists where they come apart.

Chapter 3's language is belief-only (``L_B``: atoms, ⊥, →, B_a; soundness is
K45+NU, and D can fail via *isolated perspectives*). The models this repo's
pipeline produces are validated so that no perspective is isolated, hence D holds
for them; the evaluator also accepts ``K_a`` as a convenience EXTENSION beyond
``L_B`` (quantifying over all of ``S`` instead of ``S_a``), matching the
knowledge structure the nodes came from.

Formulas are plain tuples (no classes to construct):

    ("atom", P)            an atomic proposition
    ("bot",)               falsum
    ("imp", f, g)          implication (the chapter's primitive)
    ("B", agent, f)        belief
    -- sugar, expanded by the evaluator --
    ("not", f)             = ("imp", f, ("bot",))
    ("and", f, g), ("or", f, g)
    ("K", agent, f)        knowledge (extension, see above)

Depends only on ``simplicial`` (for the model class and node/facet types).
"""

from __future__ import annotations

from itertools import product
from typing import Dict, Hashable, Iterable, List, Set, Tuple

from simplicial import Facet, Node, SimplicialBeliefModel

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


def maximal_complex(
    agents: Iterable[Hashable],
    nodes: Iterable[Node],
    assignment: Assignment,
) -> Set[Facet]:
    """Return the facets of the maximal complex ``M(N, V, L)`` (thesis p. 19).

    Every UCF facet (exactly one node per agent -- the node's own ``agent`` field
    is the colouring ``V``) whose perspectives are jointly consistent. The full
    complex is the downward closure of these facets; as everywhere in this repo,
    facets suffice to determine it.

    Raises:
        ValueError: If the assignment is ill-formed, or some agent has no node.
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


# --------------------------------------------------------------------------- #
# Semantics (thesis p. 20)
# --------------------------------------------------------------------------- #
def holds(
    model: SimplicialBeliefModel,
    assignment: Assignment,
    facet: Facet,
    formula,
) -> bool:
    """Decide ``M, facet |= formula`` under the chapter-3 semantics.

    Atoms are read off the facet's perspectives: true iff SOME node carries the
    atom with value 1 (which validates NU). ``B_a`` quantifies over the facets of
    ``S_a`` sharing ``a``'s node; ``K_a`` (extension) over all facets sharing it.

    Raises:
        ValueError: On an unknown connective.
    """
    tag = formula[0]
    if tag == "atom":
        # THE vertex-based atomic clause (the "lift" applied on the fly): an
        # atom is true at a facet iff some perspective in it observes the atom
        # as true (value 1). Value 0 elsewhere is not consulted -- a consistent
        # facet cannot carry both 1 and 0 -- and value 2 never makes anything
        # true. This is what validates NU (P -> some agent believes P): a truth
        # with no observing perspective simply does not exist at facet level.
        return any(node_value(assignment, n, formula[1]) == TRUE for n in facet)
    if tag == "bot":
        return False
    if tag == "imp":
        return (not holds(model, assignment, facet, formula[1])) or holds(
            model, assignment, facet, formula[2]
        )
    if tag == "not":
        return not holds(model, assignment, facet, formula[1])
    if tag == "and":
        return holds(model, assignment, facet, formula[1]) and holds(
            model, assignment, facet, formula[2]
        )
    if tag == "or":
        return holds(model, assignment, facet, formula[1]) or holds(
            model, assignment, facet, formula[2]
        )
    if tag == "B":
        return all(
            holds(model, assignment, Y, formula[2])
            for Y in model.believes_facets(formula[1], facet)
        )
    if tag == "K":  # extension beyond L_B: all of S sharing the agent's node
        p = model.pi(formula[1], facet)
        return all(
            holds(model, assignment, Y, formula[2])
            for Y in model.facets
            if model.pi(formula[1], Y) == p
        )
    raise ValueError(f"Unknown connective {tag!r} in formula {formula!r}.")


# --------------------------------------------------------------------------- #
# Bridge from the Kripke side: induce L from a world valuation
# --------------------------------------------------------------------------- #
def assignment_from_model(
    model: SimplicialBeliefModel,
    valuation: Dict[Atom, Set],
) -> Assignment:
    """Induce the three-valued node assignment from a Kripke world valuation.

    A node IS a knowledge class ``[w]_a`` coloured by ``a``, so the perspective
    observes exactly what the agent knows there:

        * ``P`` true at EVERY world of the class  ->  ``L(n)(P) = 1`` (knows P),
        * ``P`` false at every world of the class ->  ``L(n)(P) = 0`` (knows ¬P),
        * mixed                                   ->  ``L(n)(P) = 2`` (does not know).

    The result is facet-consistent BY CONSTRUCTION: two nodes of one facet share
    that facet's world, so they can never observe opposite values of one atom.

    Facet truth under :func:`holds` then agrees with world truth at exactly the
    facets where SOME agent knows the atom's value -- the NU schema. Use
    :func:`nu_violations` to see where an arbitrary valuation comes apart.

    Args:
        model: A simplicial belief model whose nodes carry knowledge classes.
        valuation: ``atom -> set of worlds where it is true`` (the model's own
            worlds, i.e. the keys' universe of ``model.world_of_facet`` values).

    Returns:
        The induced assignment, storing only non-2 values (2 is the default).
    """
    out: Assignment = {}
    for node in model.nodes:
        for atom, true_worlds in valuation.items():
            inside = node.cls & set(true_worlds)
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
    """Lift a vertex assignment to a chapter-2-style FACET valuation.

    This materialises the project's vertex-based reading of atomic truth --
    "an atom holds at a facet iff some vertex of it observes the atom as true"
    -- as an explicit ``L' : P -> 2^F(S)``:

        L'(P) = { X in F(S) : some node n of X has L(n)(P) = 1 }

    Why this exists. :func:`holds` already evaluates formulas directly on the
    vertex assignment, so the lift is never needed just to compute truth. It
    exists for INTEROP: anything built for chapter-2 facet valuations
    (``semantics.holds_simplicial``, comparisons against a Kripke valuation,
    future tooling) can consume a vertex assignment through this bridge.

    Why the two evaluators then agree on EVERY formula, with no side condition:
    the atomic clause of :func:`holds` and membership in ``L'(P)`` are the same
    statement by construction, and the modal clauses of chapters 2 and 3 are
    identical (``K_a``/``B_a`` quantify over the same facet sets). Induction on
    the formula does the rest. The NU caveat only appears when comparing against
    a KRIPKE world valuation (see :func:`nu_violations`): lifting the INDUCED
    assignment of a valuation ``v`` reproduces the chapter-2 translation
    ``L_N(P) = f[v(P)]`` exactly when NU holds for ``v`` -- where it fails, the
    lift is missing the facets whose atom nobody observes.

    Args:
        model: The simplicial belief model whose facets are being valued.
        assignment: A (possibly partial) vertex assignment ``L : N -> 3^P``.

    Returns:
        ``atom -> set of facets`` covering every atom the assignment mentions.
    """
    # Collect the atoms actually mentioned; unmentioned atoms are value 2 at
    # every node, so their lift would be the empty set -- omitting them keeps
    # the result as partial as the input (and holds() treats both the same).
    atoms = {atom for values in assignment.values() for atom in values}
    return {
        atom: {
            F
            for F in model.facets
            # The lift itself: one observing vertex makes the atom true at the
            # facet. Facet consistency (no 1-node next to a 0-node) is what
            # keeps this from ever contradicting another vertex of F.
            if any(node_value(assignment, n, atom) == TRUE for n in F)
        }
        for atom in atoms
    }


def nu_violations(
    model: SimplicialBeliefModel,
    assignment: Assignment,
    valuation: Dict[Atom, Set],
) -> List[Tuple[Atom, Facet]]:
    """Return the ``(atom, facet)`` pairs where facet truth and world truth differ.

    Under an induced assignment the only possible divergence is one-sided: the
    atom is TRUE at the facet's world but NO agent knows it, so no perspective
    carries it and the facet does not satisfy it -- precisely a failure of the NU
    schema ``P → ∨_a B_a P`` for that valuation. An empty result means the
    valuation is faithfully representable in the chapter-3 semantics.
    """
    out: List[Tuple[Atom, Facet]] = []
    for atom, true_worlds in valuation.items():
        true_set = set(true_worlds)
        for facet, world in model.world_of_facet.items():
            facet_truth = holds(model, assignment, facet, ("atom", atom))
            if facet_truth != (world in true_set):
                out.append((atom, facet))
    return out

"""Simplicial belief models and the translations proper Kripke <-> simplicial.

A **simplicial belief model** (Sink's thesis ch. 2; Bjorndahl & Sink, *A
Semantics for Belief in Simplicial Complexes*): a NODE is one agent's perspective
(a knowledge class coloured by the agent), a FACET is a world (one node per
agent), and each agent's BELIEF SUBCOMPLEX ``S_a`` holds the facets whose world
it doxastically accesses. :func:`to_simplicial` builds it from a *proper* model
(distinct worlds give distinct facets); :func:`to_relational` is the inverse
reading, the functor ``G_B`` of docs/12. Theory: docs/03, docs/04.

A node in no facet of its agent's ``S_a`` is an *isolated perspective* (thesis
p. 23): belief is vacuous there. Forbidden under KD45, legal under K45, and the
normal outcome of an action; nodes in no facet of ``S`` at all are kept as
0-dimensional maximal simplices. Nothing is rejected unless Axiom D is declared.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, NamedTuple, Set

from knowledge_belief import KnowledgeBeliefFrame
from relational_frame import Agent, RelationalFrame, World


class Node(NamedTuple):
    """One agent's perspective: ``agent`` is the colour, ``cls`` its knowledge
    class (any frozenset for a complex defined directly)."""

    agent: Agent
    cls: FrozenSet[World]


# A facet is a frozenset of nodes (one per agent); a complex is a set of facets.
Facet = FrozenSet[Node]


def pi(agent: Agent, facet: Facet) -> Node:
    """``π_a(facet)``: the unique ``agent``-coloured node of a facet (UCF)."""
    for n in facet:
        if n.agent == agent:
            return n
    raise ValueError(f"Facet {label_facet(facet)} has no {agent!r}-coloured node (UCF violated).")


class SimplicialBeliefModel:
    """A chromatic simplicial complex with a belief subcomplex per agent.

    Attributes:
        agents: the agent set (the colours).
        nodes: all perspectives, including any in no facet (:meth:`isolated_nodes`).
        facets: the facets of ``S``, one node per agent (UCF).
        belief_facets: ``agent -> facets of S_a`` (subsets of ``facets``).
        axiom_d: KD45 (``True``) or K45 (``False``); declared, or inferred from
            the geometry when the constructor gets ``None``.
        world_of_facet: ``facet -> world`` of the model it came from.
        projection: ``facet -> original world`` before ``to_proper``, if known.
        node_names: display names of the vertices of a complex defined directly.
    """

    def __init__(
        self,
        agents: Iterable[Agent],
        nodes: Iterable[Node],
        facets: Iterable[Facet],
        belief_facets: Dict[Agent, Iterable[Facet]],
        world_of_facet: Dict[Facet, World] | None = None,
        projection: Dict[Facet, World] | None = None,
        validate: bool = True,
        axiom_d: bool | None = None,
        node_names: Dict[Node, str] | None = None,
    ) -> None:
        """Build the model; with ``validate`` raise on any structural violation.

        ``axiom_d=True`` declares KD45 (isolated perspectives and empty ``S_a``
        are violations), ``False`` declares K45 (both legal), ``None`` infers it
        from the geometry and rejects nothing. ``axiom_d_declared`` keeps what
        was asked, so a derived model (``assignment.drop_inconsistent``) can be
        built under the same contract.
        """
        self.node_names: Dict[Node, str] = dict(node_names or {})
        self.agents: Set[Agent] = set(agents)
        self.nodes: Set[Node] = set(nodes)
        self.facets: Set[Facet] = set(facets)
        self.belief_facets: Dict[Agent, Set[Facet]] = {
            a: set(fs) for a, fs in belief_facets.items()
        }
        self.world_of_facet: Dict[Facet, World] = dict(world_of_facet or {})
        self.projection: Dict[Facet, World] = dict(projection or {})
        self.axiom_d_declared: bool | None = axiom_d
        self.axiom_d: bool = axiom_d if axiom_d is not None else self.satisfies_axiom_d()
        if validate:
            problems = self.violations()
            if problems:
                raise ValueError(
                    f"{len(problems)} simplicial-model violation(s) found:\n  - "
                    + "\n  - ".join(problems)
                )

    # ------------------------------------------------------------------ #
    # Structure accessors
    # ------------------------------------------------------------------ #
    def pi(self, agent: Agent, facet: Facet) -> Node:
        """``π_a(facet)``, see :func:`pi`."""
        return pi(agent, facet)

    def knows_facets(self, agent: Agent, facet: Facet) -> Set[Facet]:
        """The facets of ``S`` sharing ``agent``'s perspective with ``facet``:
        what ``K_a`` quantifies over."""
        p = pi(agent, facet)
        return {Y for Y in self.facets if pi(agent, Y) == p}

    def believes_facets(self, agent: Agent, facet: Facet) -> Set[Facet]:
        """The facets of ``S_a`` sharing ``agent``'s perspective with ``facet``:
        what ``B_a`` quantifies over (empty at an isolated perspective)."""
        p = pi(agent, facet)
        return {Y for Y in self.belief_facets[agent] if pi(agent, Y) == p}

    # ------------------------------------------------------------------ #
    # Knowledge-only complexes (S_a = S)
    # ------------------------------------------------------------------ #
    @property
    def is_knowledge_only(self) -> bool:
        """True iff ``S_a = S`` for every agent: a knowledge complex (Goubault,
        Ledent & Rajsbaum) read with "believe exactly what you know", the
        simplicial side of pipeline case 3. Detected, not declared."""
        return all(self.belief_facets.get(a, set()) == self.facets for a in self.agents)

    @classmethod
    def knowledge_only(
        cls, agents: Iterable[Agent], nodes: Iterable[Node], facets: Iterable[Facet],
        **kwargs,
    ) -> "SimplicialBeliefModel":
        """A complex read as pure knowledge: every ``S_a`` is the whole complex.
        Keyword arguments go to the constructor."""
        agents = set(agents)
        facets = set(facets)
        return cls(agents, nodes, facets, {a: set(facets) for a in agents}, **kwargs)

    # ------------------------------------------------------------------ #
    # Isolated perspectives (the geometry of Axiom D)
    # ------------------------------------------------------------------ #
    def isolated_nodes(self) -> Set[Node]:
        """Nodes in no facet of ``S`` at all (0-dimensional maximal simplices)."""
        covered = {n for F in self.facets for n in F}
        return {n for n in self.nodes if n not in covered}

    def isolated_perspectives(self) -> Dict[Agent, Set[Node]]:
        """Per agent, the ``a``-nodes in no facet of ``S_a`` (thesis p. 23):
        ``B_a`` is vacuous there. Tested by membership, so it also works on a
        UCF-violating facet."""
        out: Dict[Agent, Set[Node]] = {}
        for a in self.agents:
            covered = {n for F in self.belief_facets.get(a, ()) for n in F if n.agent == a}
            out[a] = {n for n in self.nodes if n.agent == a and n not in covered}
        return out

    def satisfies_axiom_d(self) -> bool:
        """True iff the geometry satisfies D: no isolated perspective, no empty ``S_a``."""
        return all(self.belief_facets.get(a) for a in self.agents) and not any(
            self.isolated_perspectives().values()
        )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def violations(self) -> List[str]:
        """Every structural violation: UCF in ``S`` and each ``S_a``, ``S_a ⊆ S``;
        and, only when ``axiom_d``, non-empty ``S_a`` and no isolated perspective."""
        problems: List[str] = []

        def ucf_problem(facet: Facet, where: str) -> str | None:
            for a in self.agents:
                count = sum(1 for n in facet if n.agent == a)
                if count != 1:
                    return (
                        f"UCF violated in {where}: facet has {count} node(s) of "
                        f"agent {a!r} (expected exactly 1)."
                    )
            return None

        for facet in self.facets:
            msg = ucf_problem(facet, "S")
            if msg:
                problems.append(msg)

        for a in sorted(self.agents, key=str):
            if self.axiom_d and not self.belief_facets.get(a):
                problems.append(f"Belief subcomplex S_{a!r} is empty (must be non-empty).")
            for facet in self.belief_facets.get(a, ()):
                if facet not in self.facets:
                    problems.append(
                        f"Belief subcomplex S_{a!r} contains a facet not in S."
                    )
                msg = ucf_problem(facet, f"S_{a!r}")
                if msg:
                    problems.append(msg)

        if self.axiom_d:
            isolated = self.isolated_perspectives()
            for a in sorted(self.agents, key=str):
                for n in sorted(isolated[a], key=label_node):
                    problems.append(
                        f"Consistency violated for agent {a!r}: node {label_node(n)} "
                        f"lies in no facet of its belief subcomplex S_{a!r}."
                    )
        return problems

    def is_valid(self) -> bool:
        """Return True iff the simplicial belief model is well-formed."""
        return not self.violations()

    # ------------------------------------------------------------------ #
    # Introspection / display
    # ------------------------------------------------------------------ #
    def describe(self) -> str:
        """A text summary: each facet with its world and belief signature, then
        the isolated perspectives per agent."""
        lines = [f"SimplicialBeliefModel: {len(self.facets)} facets, {len(self.nodes)} nodes"
                 + ("  [knowledge only: S_a = S for every agent]" if self.is_knowledge_only else "")]
        for facet in sorted(self.facets, key=lambda F: str(self.world_of_facet.get(F, ""))):
            world = self.world_of_facet.get(facet)
            in_belief = [a for a in sorted(self.agents, key=str) if facet in self.belief_facets[a]]
            tag = f"S_{{{','.join(map(str, in_belief))}}}" if in_belief else "only S"
            lines.append(f"  world {world!r}: {label_facet(facet)}  [{tag}]")
        loose = self.isolated_nodes()
        for a in sorted(self.agents, key=str):
            stuck = sorted(self.isolated_perspectives()[a], key=label_node)
            if stuck:
                names = ", ".join(
                    label_node(n) + (" (in no facet of S)" if n in loose else "")
                    for n in stuck
                )
                lines.append(f"  isolated perspectives of {a!r} (B_{a} vacuous): {names}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        belief_logic = "KD45" if self.axiom_d else "K45"
        return (
            f"SimplicialBeliefModel({'knowledge only, ' if self.is_knowledge_only else ''}"
            f"belief={belief_logic}, "
            f"agents={len(self.agents)}, "
            f"nodes={len(self.nodes)}, facets={len(self.facets)})"
        )


# --------------------------------------------------------------------------- #
# Labelling helpers (readable names for nodes/facets)
# --------------------------------------------------------------------------- #
def label_node(node: Node) -> str:
    """Readable label for a node, e.g. ``a:{w0,w1}``."""
    members = ",".join(sorted(map(str, node.cls)))
    return f"{node.agent}:{{{members}}}"


def label_facet(facet: Facet) -> str:
    """Readable label for a facet: its nodes sorted by agent."""
    return "{" + ", ".join(label_node(n) for n in sorted(facet, key=lambda n: str(n.agent))) + "}"


# --------------------------------------------------------------------------- #
# The translation: proper knowledge+belief model -> simplicial belief model
# --------------------------------------------------------------------------- #
def to_simplicial(
    model: KnowledgeBeliefFrame | RelationalFrame,
) -> SimplicialBeliefModel:
    """Translate a **proper** model into a simplicial belief model (docs/03).

    Nodes are ``(agent, knowledge class)``, each world becomes the facet of its
    agents' perspectives, and ``S_a`` collects the facets whose world
    self-accesses (``w Q_a w``). A knowledge-only S5 frame is accepted and read
    with ``Q_a = R_a`` (case 3). The ``axiom_d`` contract and the projection
    travel into the complex.

    Raises:
        ValueError: ``model`` is not proper, or a plain frame is not S5.
    """
    if isinstance(model, RelationalFrame):
        model = KnowledgeBeliefFrame(
            model.agents,
            model.worlds,
            knowledge=model.relations,
            belief=model.relations,
            projection=getattr(model, "projection", None),
        )
    if not model.is_proper():
        raise ValueError(
            "to_simplicial requires a proper model (distinct worlds must give distinct "
            "facets). Call model.to_proper() first."
        )

    agents = model.agents

    def facet_of(w: World) -> Facet:
        return frozenset(Node(a, frozenset(model.knows(a, w))) for a in agents)

    nodes: Set[Node] = set()
    facets: Set[Facet] = set()
    world_of_facet: Dict[Facet, World] = {}
    for w in model.worlds:
        facet = facet_of(w)
        facets.add(facet)
        world_of_facet[facet] = w
        nodes |= set(facet)

    belief_facets: Dict[Agent, Set[Facet]] = {
        a: {facet_of(w) for w in model.worlds if w in model.believes(a, w)} for a in agents
    }
    projection: Dict[Facet, World] = {}
    if model.projection:
        for facet, w in world_of_facet.items():
            projection[facet] = model.projection.get(w, w)

    return SimplicialBeliefModel(
        agents=agents,
        nodes=nodes,
        facets=facets,
        belief_facets=belief_facets,
        world_of_facet=world_of_facet,
        projection=projection,
        axiom_d=getattr(model, "axiom_d", True),
    )


# --------------------------------------------------------------------------- #
# The inverse translation: simplicial -> Kripke (the functor G_B of docs/12)
# --------------------------------------------------------------------------- #
def unique_names(facets: Iterable[Facet], given: Dict[Facet, World], fallback) -> Dict[Facet, World]:
    """Name each facet by ``given`` when it has a name, else by ``fallback(facet)``;
    two facets with the same given name both fall back, since names must be unique."""
    names: Dict[Facet, World] = {}
    seen: Dict[World, Facet] = {}
    for F in facets:
        w = given.get(F, fallback(F))
        if w in seen:
            names[seen[w]] = fallback(seen[w])
            w = fallback(F)
        names[F], seen[w] = w, F
    return names


def shared_vertex_groups(agents: Iterable[Agent], facets: Iterable[Facet]) -> Dict[Agent, List[List[Facet]]]:
    """Per agent, the facets grouped by the agent's vertex: each group is one
    indistinguishability class (a knowledge class of the Kripke reading)."""
    out: Dict[Agent, List[List[Facet]]] = {}
    for a in agents:
        by_vertex: Dict[Node, List[Facet]] = {}
        for F in facets:
            by_vertex.setdefault(pi(a, F), []).append(F)
        out[a] = list(by_vertex.values())
    return out


class Relational(NamedTuple):
    """What :func:`to_relational` returns: the frame (worlds = facets, named by
    ``world_of_facet`` or by :func:`label_facet`), the lifted valuation (empty
    without an assignment) and the bijection ``world -> facet``."""

    frame: KnowledgeBeliefFrame
    valuation: Dict
    facet_of_world: Dict


def to_relational(
    model: SimplicialBeliefModel,
    assignment=None,
    ignore_isolated: bool = False,
) -> Relational:
    """Read a simplicial belief model as a knowledge+belief Kripke model (docs/12).

    One world per facet; ``X R_a Y`` iff the facets share ``a``'s vertex;
    ``X Q_a Y`` iff they share it and ``Y ∈ S_a``. The result is proper and
    valid by construction; it is declared KD45 exactly when no perspective is
    isolated. Inverse of :func:`to_simplicial` up to isomorphism.

    Args:
        assignment: vertex assignment to lift to a world valuation.
        ignore_isolated: leave out vertices in no facet (they have no world);
            by default they are an error.

    Raises:
        ValueError: isolated nodes without ``ignore_isolated``, or a UCF failure.
    """
    loose = model.isolated_nodes()
    if loose and not ignore_isolated:
        raise ValueError(
            "to_relational: these nodes lie in no facet, so they have no world in the "
            "Kripke model (pass ignore_isolated=True to leave them out): "
            + ", ".join(label_node(n) for n in sorted(loose, key=label_node))
        )
    agents = sorted(model.agents, key=str)
    facets = sorted(model.facets, key=label_facet)
    names = unique_names(facets, model.world_of_facet, label_facet)
    knowledge: Dict[Agent, Set] = {a: set() for a in agents}
    belief: Dict[Agent, Set] = {a: set() for a in agents}
    serial = True
    for a, groups in shared_vertex_groups(agents, facets).items():
        for group in groups:
            believed = [Y for Y in group if Y in model.belief_facets.get(a, ())]
            serial = serial and bool(believed)
            for X in group:
                for Y in group:
                    knowledge[a].add((names[X], names[Y]))
                for Y in believed:
                    belief[a].add((names[X], names[Y]))
    frame = KnowledgeBeliefFrame(
        agents, names.values(), knowledge, belief, axiom_d=serial,
    )
    valuation: Dict = {}
    if assignment:
        from assignment import lift_to_facets  # local: assignment imports this module

        for atom, fs in lift_to_facets(model, assignment).items():
            valuation[atom] = {names[F] for F in fs if F in names}
    return Relational(frame, valuation, {w: F for F, w in names.items()})

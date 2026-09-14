"""Simplicial belief models and the proper-relational -> simplicial translation.

This is Step 3 (the simplicial model class) and Step 4 (the translation) of the
project roadmap, following Sink's thesis ch. 2 / Bjorndahl & Sink, *A Semantics for
Belief in Simplicial Complexes*. See docs/03-simplicial-models.md and
docs/04-figures-1-2-3.md for the full explanation.

A **simplicial belief model** turns a *proper* knowledge+belief relational model into
a geometric object:

    * a NODE is one agent's local perspective -- a knowledge equivalence class,
      labelled by the agent: ``([w]_a, a)``;
    * a FACET (a maximal simplex) is a possible world -- one node per agent,
      ``f(w) = { ([w]_a, a) : a in Ag }``;
    * each agent has a BELIEF SUBCOMPLEX ``S_a`` -- the facets whose world the agent
      doxastically accesses (``w Q_a w``); belief means "holds throughout ``S_a``".

Because the input is **proper**, distinct worlds give distinct facets, so ``f`` is a
bijection worlds <-> facets and the translation is faithful. That is exactly why
:func:`to_simplicial` demands a proper model.

Dependency direction: this module imports the models; nothing imports it.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, NamedTuple, Set

from knowledge_belief import KnowledgeBeliefFrame
from relational_frame import Agent, RelationalFrame, World


class Node(NamedTuple):
    """A simplicial node = one agent's perspective (a knowledge class, coloured by agent).

    ``agent`` is the colour; ``cls`` is the agent's knowledge equivalence class (the
    set of worlds the agent cannot tell apart), stored as a frozenset so nodes are
    hashable and comparable.
    """

    agent: Agent
    cls: FrozenSet[World]


# A facet is a frozenset of nodes (one per agent); a complex is a set of facets.
Facet = FrozenSet[Node]


class SimplicialBeliefModel:
    """A chromatic simplicial complex with a per-agent belief subcomplex.

    Attributes:
        agents: the agent set (the colours).
        nodes: all nodes (perspectives) appearing in some facet.
        facets: the facets of the whole complex ``S`` (each a frozenset of nodes,
            one per agent -- the UCF condition).
        belief_facets: ``agent -> set of facets`` giving each agent's belief
            subcomplex ``S_a`` (a subset of ``facets``).
        world_of_facet: ``facet -> world`` of the proper model it came from (the
            bijection ``f`` inverted).
        projection: ``facet -> original world`` it ultimately simulates (composing
            ``world_of_facet`` with the proper model's bisimulation projection), or
            empty if unavailable.
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
        axiom_d: bool = True,
    ) -> None:
        # The geometric side of the Axiom D contract. On a simplicial model, D
        # is exactly "no isolated perspectives" (thesis p. 23): every a-node
        # lies in some facet of S_a, and no S_a is empty. With axiom_d=False
        # (K45, the logic of ch. 3) both are legal: an isolated a-node makes
        # believes_facets empty there, so B_a is vacuously universal -- defunct
        # belief, which is a state ch. 3's revision genuinely produces. Only
        # violations() consults the flag; the semantics never does.
        self.axiom_d: bool = axiom_d
        self.agents: Set[Agent] = set(agents)
        self.nodes: Set[Node] = set(nodes)
        self.facets: Set[Facet] = set(facets)
        self.belief_facets: Dict[Agent, Set[Facet]] = {
            a: set(fs) for a, fs in belief_facets.items()
        }
        self.world_of_facet: Dict[Facet, World] = dict(world_of_facet or {})
        self.projection: Dict[Facet, World] = dict(projection or {})
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
    def color(self, node: Node) -> Agent:
        """Return the agent that owns ``node`` (the colouring ``V``)."""
        return node.agent

    def pi(self, agent: Agent, facet: Facet) -> Node:
        """Return ``π_a(facet)``: the unique ``agent``-coloured node of ``facet``."""
        for n in facet:
            if n.agent == agent:
                return n
        raise ValueError(f"Facet has no {agent!r}-coloured node (UCF violated).")

    def believes_facets(self, agent: Agent, facet: Facet) -> Set[Facet]:
        """The facets of ``S_a`` sharing ``agent``'s perspective with ``facet``.

        Belief semantics quantify over exactly this set: at ``facet``, agent ``a``
        believes ``φ`` iff ``φ`` holds at every facet returned here.
        """
        p = self.pi(agent, facet)
        return {Y for Y in self.belief_facets[agent] if self.pi(agent, Y) == p}

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def violations(self) -> List[str]:
        """Return every structural violation (empty list if well-formed).

        Checks: UCF for the whole complex and each belief subcomplex, each ``S_a`` a
        subset of ``S`` and non-empty, and the consistency/seriality condition (every
        coloured node lies in some facet of its agent's belief subcomplex).
        """
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
            # Non-emptiness of S_a is part of the D contract (an empty S_a means
            # EVERY a-perspective is isolated); UCF and S_a ⊆ S below are
            # structural and hold in both logics.
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

        # Consistency/seriality: every a-coloured node sits in some facet of
        # S_a. This IS Axiom D read geometrically -- a node failing it is an
        # "isolated perspective" (thesis p. 23), at which B_a holds vacuously
        # for everything. Enforced only under the KD45 contract; a K45 model
        # (axiom_d=False) admits isolated perspectives by design.
        if self.axiom_d:
            for a in sorted(self.agents, key=str):
                covered = {self.pi(a, F) for F in self.belief_facets.get(a, ())}
                for n in self.nodes:
                    if n.agent == a and n not in covered:
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
        """Return a readable text summary: facets labelled by world and colours."""
        lines = [f"SimplicialBeliefModel: {len(self.facets)} facets, {len(self.nodes)} nodes"]
        for facet in sorted(self.facets, key=lambda F: str(self.world_of_facet.get(F, ""))):
            world = self.world_of_facet.get(facet)
            in_belief = [a for a in sorted(self.agents, key=str) if facet in self.belief_facets[a]]
            tag = f"S_{{{','.join(map(str, in_belief))}}}" if in_belief else "only S"
            lines.append(f"  world {world!r}: {label_facet(facet)}  [{tag}]")
        return "\n".join(lines)

    def __repr__(self) -> str:
        belief_logic = "KD45" if self.axiom_d else "K45"
        return (
            f"SimplicialBeliefModel(belief={belief_logic}, "
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
    """Translate a **proper** knowledge+belief model into a simplicial belief model.

    Implements the construction of docs/03: nodes are (knowledge class, agent), each
    world becomes the facet bundling every agent's perspective, and each belief
    subcomplex collects the facets whose world doxastically self-accesses (``w Q_a w``).

    The input must be **proper** (``model.is_proper()``) so that ``f`` is injective and
    the translation is faithful. Pass a :class:`ProperKnowledgeBeliefFrame`, or call
    ``model.to_proper()`` first.

    A knowledge-only :class:`RelationalFrame` (S5) is also accepted: it is wrapped
    as a knowledge+belief model with ``Q_a = R_a`` ("believe exactly what you
    know"), the neutral choice that adds no doxastic opinion. Every world then
    self-accesses, so each ``S_a`` is the whole complex and belief coincides with
    knowledge -- the pure case-3 translation. A KD45 belief frame is rejected by
    the wrapper's S5 validation.

    Args:
        model: a proper :class:`KnowledgeBeliefFrame` (typically a
            ``ProperKnowledgeBeliefFrame`` from :meth:`KnowledgeBeliefFrame.to_proper`),
            or a proper knowledge-only S5 :class:`RelationalFrame` (typically a
            ``ProperRelationalFrame`` from :func:`properness.to_proper`).

    Returns:
        The corresponding :class:`SimplicialBeliefModel`.

    Raises:
        ValueError: If ``model`` is not proper, or a knowledge-only frame is not S5.
    """
    if isinstance(model, RelationalFrame):
        # Case 3 (knowledge only): wrap with Q_a = R_a, carrying the bisimulation
        # projection through if the frame has one (ProperRelationalFrame does).
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

    def knowledge_class(a: Agent, w: World) -> FrozenSet[World]:
        # R_a(w) = the equivalence class of w under a's knowledge relation.
        return frozenset(model.knows(a, w))

    def facet_of(w: World) -> Facet:
        return frozenset(Node(a, knowledge_class(a, w)) for a in agents)

    nodes: Set[Node] = set()
    facets: Set[Facet] = set()
    world_of_facet: Dict[Facet, World] = {}
    for w in model.worlds:
        facet = facet_of(w)
        facets.add(facet)
        world_of_facet[facet] = w
        nodes |= set(facet)

    # Belief subcomplex S_a: facets whose world believes-accesses itself (w Q_a w).
    belief_facets: Dict[Agent, Set[Facet]] = {a: set() for a in agents}
    for a in agents:
        for w in model.worlds:
            if w in model.believes(a, w):
                belief_facets[a].add(facet_of(w))

    # Carry the bisimulation projection through to the original (pre-proper) world.
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
        # The axiom_d contract travels from the relational model into the
        # complex: a K45 model's worlds with empty Q produce facets outside
        # every S_a (no self-access) and possibly isolated perspectives, which
        # its own validation must therefore permit. (A wrapped knowledge-only
        # frame has Q = R, reflexive, so D holds there regardless.)
        axiom_d=getattr(model, "axiom_d", True),
    )

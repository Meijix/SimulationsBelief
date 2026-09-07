"""Relational (Kripke) frames for KD45 belief logic.

This module implements a *purely structural* relational model: worlds are nodes
and accessibility relations are directed edges, one relation per agent. There are
no propositions, no valuations and no logical formulas here -- only the graph
structure and the KD45 frame conditions that characterise (consistent) belief.

KD45 frame conditions:
    * Seriality      (Axiom D):  every world has at least one successor.
    * Transitivity   (Axiom 4):  w -> u and u -> v  implies  w -> v.
    * Euclideanness  (Axiom 5):  w -> u and w -> v  implies  u -> v.

Visualisation (text / Graphviz / images) lives in visualization.py; runnable
examples live in examples.py.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Hashable, Iterable, List, Mapping, Set, Tuple

# Type aliases for readability.
#
# Hashable, and not str: agents and worlds are only ever *identifiers*. The frame
# never reads them, it only stores them in sets and uses them as dictionary keys
# That keeps the model free to name worlds freely
#
# Tuple, and not list, for an edge: each relation is stored as a `Set[Edge]`, so
# an edge must be hashable -- and in Python that means immutable, which a list is
# not. It also matches how edges are used: they are added to or removed from the
# set whole, never edited in place. Order carries the meaning -- (w, u) is "w
# accesses u", not the same as (u, w) -- so the pair is never an unordered set.
Agent = Hashable
World = Hashable
Edge = Tuple[World, World]


class RelationalFrame:
    """A pure relational (Kripke) frame validated against the KD45 axioms.

    The frame is *structural only*: it stores agents, worlds and, for each agent,
    a set of directed edges ``(source, target)`` between worlds. Checks structural integrity and then enforces the KD45 frame conditions,
    raising :class:`ValueError` if any of them is violated.

    A frame is **immutable** once built: ``agents``, ``worlds`` and each relation are
    stored as frozensets, so the precomputed ``_successors`` adjacency can never
    fall out of sync. Build a new frame to change the structure.

    Attributes:
        agents: The (frozen) set of agent identifiers.
        worlds: The (frozen) set of world identifiers (graph nodes).
        relations: Mapping ``agent -> frozenset of (source, target)`` edges.
        _successors: Precomputed adjacency ``agent -> {world -> set of successors}``
            used for efficient axiom checking.
    """

    def __init__(
        self,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        relations: Dict[Agent, Iterable[Edge]], # each agent's accessibility relation.
        validate: bool = True, # If True, enforce the KD45 frame conditions.
    ) -> None:
        """Build a relational frame, optionally enforcing the KD45 axioms.

        Raises:
            ValueError: Always if the structure references unknown agents/worlds;
                and, when ``validate`` is True, if any agent's relation violates
                seriality, transitivity or the Euclidean property.
        """
        # Why frozensets (not plain sets):
        # The constructor precomputes `_successors` (an adjacency cache) once, and
        # every query and validator reads from that cache, not from `relations`.
        # If `relations` were a mutable set, code could do
        # `frame.relations[a].discard(edge)` after construction and the cache would
        # silently go stale -- successors()/is_valid()/dead_ends() would then report
        # the OLD structure. Freezing agents,
        # worlds and each relation makes the frame immutable, so `_successors` can
        # never drift out of sync: to change the structure, you build a new frame.
        self.agents: FrozenSet[Agent] = frozenset(agents)
        self.worlds: FrozenSet[World] = frozenset(worlds)
        self.relations: Dict[Agent, FrozenSet[Edge]] = {
            agent: frozenset(edges) for agent, edges in relations.items()
        }

        # Structural integrity must hold ALWAYS (even to draw it).
        self._validate_structure()

        # Adjacency map: agent -> {world -> set of directly reachable worlds}.
        self._successors: Dict[Agent, Dict[World, Set[World]]] = self._build_successors()

        # KD45 frame conditions -- only enforced when validate=True.
        # We collect ALL violations first and report them together
        if validate:
            problems = self.kd45_violations()
            if problems:
                raise ValueError(
                    f"{len(problems)} KD45 violation(s) found:\n  - "
                    + "\n  - ".join(problems)
                )

    @classmethod
    def from_partial(
        cls,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        partial_relations: Dict[Agent, Iterable[Edge]],
        make_serial: bool = False,
    ) -> "RelationalFrame":
        """Build a frame from *partial* relations, closing each agent under KD45.

        Fills in every edge that transitivity, Euclideanness (and optionally seriality) require,
        then hands the result to the normal validating constructor.

        The closure is applied *independently to each agent*, because each agent's
        accessibility relation is a separate belief structure.

        EVERY declared agent must have an entry in ``partial_relations``: a missing
        agent is reported, never silently completed. An explicit empty set means
        "no seed edges" and documents that intent.

        Returns:
            A fully validated :class `RelationalFrame`.

        Raises:
            ValueError: If some declared agent has no entry in ``partial_relations``.
        """
        world_set = set(worlds)
        require_all_agents(agents, partial_relations, "RelationalFrame.from_partial")
        closed: Dict[Agent, Set[Edge]] = {}
        for agent in agents:
            # Close THIS agent's relation only -- never mix agents' edges.
            closed[agent] = kd45_closure(
                world_set, partial_relations[agent], make_serial=make_serial
            )
        return cls(agents=agents, worlds=world_set, relations=closed)

    @classmethod
    def from_partial_s5(
        cls,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        partial_relations: Dict[Agent, Iterable[Edge]],
    ) -> "RelationalFrame":
        """Build a KNOWLEDGE frame from *partial* relations, closing each agent under S5.

        The knowledge counterpart of :meth:`from_partial`.

        As in :meth:`from_partial`, the closure is applied *independently to each
        agent* -- one agent's edges never leak into another's relation.

        There is deliberately no ``make_serial`` parameter: reflexivity already gives
        every world the successor ``w -> w``, so seriality (Axiom D) cannot fail and
        there is nothing to decide.

        As in :meth:`from_partial`, EVERY declared agent must have an entry in
        ``partial_relations`` (an explicit empty set means "no seed edges", and
        closes to the identity relation); a missing agent is reported, never
        silently completed.

        Returns:
            A fully validated :class:`RelationalFrame` whose relations are
            equivalence relations.

        Raises:
            ValueError: If some declared agent has no entry in ``partial_relations``.
        """
        world_set = set(worlds)
        require_all_agents(agents, partial_relations, "RelationalFrame.from_partial_s5")
        closed: Dict[Agent, Set[Edge]] = {}
        for agent in agents:
            # Close THIS agent's relation only -- never mix agents' edges.
            closed[agent] = s5_closure(world_set, partial_relations[agent])
        return cls(agents=agents, worlds=world_set, relations=closed)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _build_successors(self) -> Dict[Agent, Dict[World, Set[World]]]:
        """Build the adjacency map used by the axiom validators.

        Returns:
            A nested mapping ``agent -> {world -> set of successors}``. Every
            world of every agent gets an entry(possibly empty).
            Example: {'alice': {'w1': {'w2'}, 'w2': {'w3'}}, 'bob': {'w2': {'w3'}, 'w3': {'w4'}}}.
        """
        successors: Dict[Agent, Dict[World, Set[World]]] = {
            agent: {world: set() for world in self.worlds} for agent in self.agents
        }
        for agent, edges in self.relations.items():
            for source, target in edges:
                successors[agent][source].add(target)
        return successors

    # ------------------------------------------------------------------ #
    # Validation routines
    # ------------------------------------------------------------------ #
    def _validate_structure(self) -> None:
        """Check that every agent and world referenced actually exists.

        Raises:
            ValueError: If ``relations`` mentions an unknown agent, or an edge references a world not present in ``worlds``.
        """
        for agent, edges in self.relations.items():
            if agent not in self.agents:
                raise ValueError(
                    f"Unknown agent {agent!r} in relations; it is not one of the "
                    f"declared agents {sorted(map(str, self.agents))}."
                )
            for source, target in edges:
                if source not in self.worlds:
                    raise ValueError(
                        f"Edge ({source!r} -> {target!r}) for agent {agent!r} "
                        f"references an unknown source world {source!r}."
                    )
                if target not in self.worlds:
                    raise ValueError(
                        f"Edge ({source!r} -> {target!r}) for agent {agent!r} "
                        f"references an unknown target world {target!r}."
                    )

    def _seriality_violations(self) -> List[str]:
        """Axiom D: every world must have at least one outgoing edge per agent. NO DEAD ENDS.
        Makes belief consistent: an agent can believe false things, it just has to
        believe something. A world with no successors makes "believes P" vacuously
        true for every P, so the agent would believe P and not-P at once.
        """
        problems: List[str] = []
        for agent in sorted(self.agents, key=str):
            for world in sorted(self.worlds, key=str):
                if not self._successors[agent][world]: #find if the world has no outgoing edge (successors is empty)
                    problems.append(
                        f"Seriality (D) violated: agent {agent!r} has no outgoing "
                        f"edge from world {world!r}; every world needs a successor."
                    ) #no exception, just a message
        return problems

    def _transitivity_violations(self) -> List[str]:
        """Axiom 4: if w -> u and u -> v then w -> v must hold.
        positive introspection: if an agent believes u, it must also believe that it believes u."""
        problems: List[str] = []
        for agent in sorted(self.agents, key=str):
            adjacency = self._successors[agent] #successors of each world for the agent
            for w, w_succ in adjacency.items(): #for each world w, its successors w_succ
                for u in w_succ: #for each successor u of w
                    for v in adjacency[u]: #for each successor v of u
                        if v not in w_succ: #if v is not a successor of w
                            problems.append(
                                f"Transitivity (4) violated for agent {agent!r}: "
                                f"{w!r} -> {u!r} and {u!r} -> {v!r} exist, but the "
                                f"required edge {w!r} -> {v!r} is missing."
                            )
        return problems

    def _euclidean_violations(self) -> List[str]:
        """Axiom 5: if w -> u and w -> v then u -> v must hold.
        negative introspection: if an agent believes both u and v, it must also believe that it believes u and v."""
        problems: List[str] = []
        for agent in sorted(self.agents, key=str):
            adjacency = self._successors[agent]
            for w, w_succ in adjacency.items():
                for u in w_succ:
                    for v in w_succ:
                        if v not in adjacency[u]:
                            problems.append(
                                f"Euclideanness (5) violated for agent {agent!r}: "
                                f"{w!r} -> {u!r} and {w!r} -> {v!r} exist, but the "
                                f"required edge {u!r} -> {v!r} is missing."
                            )
        return problems

    #Transitivity and euclideaness warrantes complete access to the agents own mental state. Agents can be wrong about the world, but they cannot be wrong about what they believe by themselves.


    # ------------------------------------------------------------------ #
    def kd45_violations(self) -> List[str]:
        """Return every KD45 axiom violation as a message (empty list if valid).
        it collects all problems, so a frame built with ``validate=False`` can be inspected or annotated in a
        visualisation.
        """
        return (
            self._seriality_violations()
            + self._transitivity_violations()
            + self._euclidean_violations()
        )

    def is_valid(self) -> bool:
        """Return True iff the frame satisfies all KD45 axioms."""
        return not self.kd45_violations()

    def missing_edges(self) -> Dict[Agent, Set[Edge]]:
        """Return, per agent, the edges required by axioms 4/5 but currently absent.

        Note: seriality (Axiom D) is not represented here, because a dead-end world
        has no canonical "missing" target
        """
        missing: Dict[Agent, Set[Edge]] = {}
        for agent in self.agents:
            closure = _transitive_euclidean_closure(self.worlds, self.relations[agent])
            required = {(w, v) for w, targets in closure.items() for v in targets}
            missing[agent] = required - self.relations[agent]
        return missing

    def dead_ends(self) -> Dict[Agent, Set[World]]:
        """Return, per agent, the worlds that have no outgoing edge (seriality/D). """
        return {
            agent: {w for w in self.worlds if not self._successors[agent][w]}
            for agent in self.agents
        }

    def successors(self, agent: Agent, world: World) -> Set[World]:
        """Return the set of worlds directly accessible for ``agent`` from ``world``."""
        return set(self._successors[agent][world])

    def __repr__(self) -> str:
        n_edges = sum(len(edges) for edges in self.relations.values())
        return (
            f"RelationalFrame(agents={len(self.agents)}, "
            f"worlds={len(self.worlds)}, edges={n_edges})"
        )

#########
#Helper functions
#########

def require_all_agents(
    agents: Iterable[Agent],
    relations: Mapping,
    caller: str,
    mapping_name: str = "relations",
) -> None:
    """Raise unless EVERY declared agent has an entry in ``relations``.

    The partial-relation builders never invent a relation for an agent the caller
    forgot: a silently-defaulted agent (identity knowledge, self-loop belief) looks
    like a modelling choice but is usually a typo. Absence must be shown, not
    completed. The way to say "this agent has no seed edges" is an explicit empty
    set, which documents the intent.

    Args:
        agents: The declared agent identifiers.
        relations: The ``agent -> edges`` mapping being checked.
        caller: Name of the calling builder, used in the error message.
        mapping_name: How the caller names its mapping parameter.

    Raises:
        ValueError: If some declared agent has no entry in ``relations``.
    """
    missing = sorted(str(a) for a in agents if a not in relations)
    if missing:
        plural = "s" if len(missing) > 1 else ""
        raise ValueError(
            f"{caller} requires an entry in {mapping_name} for EVERY declared "
            f"agent, but agent{plural} {missing} have none. A missing agent is "
            f"not silently completed -- pass an explicit empty set "
            f"({mapping_name}[agent] = set()) to mean 'no seed edges'."
        )

def _as_edge_list(edges: Iterable[Edge], caller: str) -> List[Edge]:
    """Materialise ``edges`` and reject anything that is not an iterable of pairs.

    The closures take **one agent's** edges. Handing them the whole
    ``agent -> edges`` mapping is the easy mistake, and without this check it
    surfaces as ``ValueError: not enough values to unpack`` from deep inside the
    fixpoint loop -- because iterating a dict yields its KEYS. Fail early, and
    name the function that does take a mapping.

    Args:
        edges: The candidate edge iterable (materialised, so generators survive).
        caller: Name of the calling closure, used in the error message.

    Returns:
        The edges as a list.

    Raises:
        TypeError: If ``edges`` is a mapping, or contains a non-pair item.
    """
    family_helper = (
        "RelationalFrame.from_partial_s5" if caller == "s5_closure"
        else "RelationalFrame.from_partial"
    )
    if isinstance(edges, Mapping):
        keys = sorted(map(repr, edges))
        raise TypeError(
            f"{caller}(worlds, edges) takes ONE agent's edges -- an iterable of "
            f"(source, target) pairs -- but got a mapping of {len(edges)} entries "
            f"with keys {keys[:5]}{' ...' if len(keys) > 5 else ''}. Iterating a "
            f"mapping yields its KEYS, not its edges. Close one agent at a time, "
            f"e.g. {caller}(worlds, relations[agent]), or close the whole family "
            f"in one call with {family_helper}(agents, worlds, relations)."
        )
    out: List[Edge] = []
    for position, item in enumerate(edges):
        if isinstance(item, (str, bytes)) or not isinstance(item, tuple) or len(item) != 2:
            raise TypeError(
                f"{caller}(worlds, edges) expects (source, target) pairs, but item "
                f"{position} is {item!r}. Each edge must be a 2-tuple; if you have "
                f"an agent -> edges mapping, use {family_helper} instead."
            )
        out.append(item)
    return out


def kd45_closure(
    worlds: Iterable[World],
    edges: Iterable[Edge],
    make_serial: bool = False,
) -> Set[Edge]:
    """Compute the KD45 closure of a single agent's relation.

    Returns the smallest set of edges that contains ``edges`` and is both
    **transitive** (Axiom 4) and **Euclidean** (Axiom 5).

    Raises:
        ValueError: If an edge references a world not in ``worlds``, or if
            ``make_serial`` is False and an isolated world would violate seriality.
    """
    world_set: Set[World] = set(worlds)
    edges = _as_edge_list(edges, "kd45_closure")

    # The transitive + Euclidean closure does all the Horn-style edge forcing.
    succ = _transitive_euclidean_closure(world_set, edges)

    # Seriality: after closure, dead ends are exactly the isolated worlds.
    dead_ends = {w for w in world_set if not succ[w]}
    if dead_ends:
        if make_serial:
            for w in dead_ends:
                succ[w].add(w)  # a one-world cluster is trivially KD45
        else:
            raise ValueError(
                f"Seriality (D) cannot be closed automatically for isolated "
                f"worlds {sorted(map(str, dead_ends))}; pass make_serial=True to "
                f"give each a self-loop, or add an outgoing edge manually."
            )

    return {(w, v) for w, targets in succ.items() for v in targets}


def _transitive_euclidean_closure(
    world_set: Set[World], edges: Iterable[Edge]
) -> Dict[World, Set[World]]:
    """Return the transitive + Euclidean closure as an adjacency map.

    shared core of :func:`kd45_closure` (belief) and :func:`s5_closure`
    (knowledge), reused to compute which edges an invalid frame is *missing*. 

    Returns:
        ``{world -> set of successors}`` closed under transitivity and Euclideanness.

    Raises:
        ValueError: If an edge references a world not in ``world_set``.
    """
    succ: Dict[World, Set[World]] = {w: set() for w in world_set}
    for source, target in edges:
        if source not in world_set or target not in world_set:
            raise ValueError(
                f"Edge ({source!r} -> {target!r}) references a world not in "
                f"{sorted(map(str, world_set))}."
            )
        succ[source].add(target)

    # Fixpoint: keep adding transitively/Euclidean-forced edges until stable.
    changed = True
    while changed:
        changed = False
        for w in world_set:
            for u in list(succ[w]):
                # Transitivity: w -> u and u -> v  =>  w -> v.
                for v in list(succ[u]):
                    if v not in succ[w]:
                        succ[w].add(v)
                        changed = True
                # Euclideanness: w -> u and w -> v  =>  u -> v.
                for v in list(succ[w]):
                    if v not in succ[u]:
                        succ[u].add(v)
                        changed = True
    return succ

def s5_closure(worlds: Iterable[World], edges: Iterable[Edge]) -> Set[Edge]:
    """Compute the S5 closure of a relation --  *knowledge*.

    This is the counterpart of :func:`kd45_closure` for KNOWLEDGE instead of
    BELIEF. 

        * KNOWLEDGE = S5 = reflexive + transitive + Euclidean (equivalence relation).
          extra axiom is T (Truth / factivity): w -> w for EVERY world.
          "If you know P, then P is true", so the real world is always one of
          the worlds you consider possible. You cannot know something false.

    Concretely, S5 replaces KD45's *seriality* with the stronger *reflexivity*:

    Returns:
        The closed, reflexive-transitive-Euclidean (S5) edge set.
    """
    world_set: Set[World] = set(worlds)
    seeded = set(_as_edge_list(edges, "s5_closure")) | {(w, w) for w in world_set}
    # No make_serial needed: reflexivity already guarantees seriality.
    return kd45_closure(world_set, seeded, make_serial=False)

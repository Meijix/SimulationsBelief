"""Relational (Kripke) frames: the structure of knowledge (S5) and belief (KD45/K45).

Worlds are nodes and each agent has one accessibility relation, a set of directed
edges. No valuations or formulas here (see ``semantics.py``); only the graph and
the frame conditions:

    * Seriality      (Axiom D):  every world has at least one successor.
    * Transitivity   (Axiom 4):  w -> u and u -> v  implies  w -> v.
    * Euclideanness  (Axiom 5):  w -> u and w -> v  implies  u -> v.
    * Reflexivity    (Axiom T):  w -> w.

Belief is KD45 (D+4+5) or, with ``axiom_d=False``, K45 (4+5: a world with no
successor is a *defunct* belief, legal in thesis ch. 3). Knowledge is S5
(T+4+5, an equivalence relation). Theory and worked examples: docs/01.
Drawing lives in ``visualization.py``.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Hashable, Iterable, List, Mapping, Set, Tuple

# Agents and worlds are opaque identifiers (strings, ints, or the (world, copy)
# pairs of properness.to_proper); an edge is the ordered pair (source, target).
Agent = Hashable
World = Hashable
Edge = Tuple[World, World]


class RelationalFrame:
    """A relational frame validated against the axioms of its declared logic.

    ``axiom_d`` is the logic contract carried by the object: True means KD45,
    False means K45 (worlds without successors are legal). Only validation reads
    it; evaluators quantify over the successor set, which is already the right
    (vacuous) truth condition when it is empty.

    The frame is immutable: ``agents``, ``worlds`` and each relation are
    frozensets, so the precomputed adjacency ``_successors`` can never go stale.
    Build a new frame to change the structure.

    Attributes:
        agents: frozenset of agent identifiers.
        worlds: frozenset of world identifiers.
        relations: ``agent -> frozenset of (source, target)`` edges.
        axiom_d: True = KD45, False = K45.
    """

    def __init__(
        self,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        relations: Dict[Agent, Iterable[Edge]],
        validate: bool = True,
        axiom_d: bool = True,
    ) -> None:
        """Build the frame; with ``validate`` raise on any violation of the declared logic.

        Raises:
            ValueError: always if an edge or key names an unknown agent or world;
                with ``validate``, if some relation violates 4, 5 or (KD45 only) D.
                Every violation is reported at once.
        """
        self.axiom_d: bool = axiom_d
        self.agents: FrozenSet[Agent] = frozenset(agents)
        self.worlds: FrozenSet[World] = frozenset(worlds)
        self.relations: Dict[Agent, FrozenSet[Edge]] = {
            agent: frozenset(edges) for agent, edges in relations.items()
        }
        self._validate_structure()
        self._successors: Dict[Agent, Dict[World, Set[World]]] = self._build_successors()
        if validate:
            problems = self.violations()
            if problems:
                logic = "KD45" if self.axiom_d else "K45"
                raise ValueError(
                    f"{len(problems)} {logic} violation(s) found:\n  - "
                    + "\n  - ".join(problems)
                )

    @classmethod
    def from_partial(
        cls,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        partial_relations: Dict[Agent, Iterable[Edge]],
        make_serial: bool = False,
        axiom_d: bool = True,
    ) -> "RelationalFrame":
        """Build a frame from partial relations, closing each agent's relation.

        Each relation is closed under KD45 (:func:`kd45_closure`) or, with
        ``axiom_d=False``, under K45 (:func:`k45_closure`, no seriality repair).
        ``make_serial`` gives a self-loop to the worlds the KD45 closure leaves
        without a successor; it contradicts ``axiom_d=False`` and then raises.
        Every declared agent needs an entry (an explicit empty set means "no seed
        edges"); a missing agent is an error, never a silent default.

        Raises:
            ValueError: missing agent entry, or ``make_serial`` with ``axiom_d=False``.
        """
        if make_serial and not axiom_d:
            raise ValueError(
                "make_serial=True repairs seriality, but axiom_d=False declares "
                "that seriality (Axiom D) is not required -- these contradict "
                "each other. Drop make_serial for a K45 frame, or keep D on."
            )
        world_set = set(worlds)
        require_all_agents(agents, partial_relations, "RelationalFrame.from_partial")
        closed = {
            agent: (
                kd45_closure(world_set, partial_relations[agent], make_serial=make_serial)
                if axiom_d
                else k45_closure(world_set, partial_relations[agent])
            )
            for agent in agents
        }
        return cls(agents=agents, worlds=world_set, relations=closed, axiom_d=axiom_d)

    @classmethod
    def from_partial_s5(
        cls,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        partial_relations: Dict[Agent, Iterable[Edge]],
    ) -> "RelationalFrame":
        """Build a knowledge frame from partial relations, closing each under S5.

        An explicit empty set closes to the identity relation; a missing agent
        is an error. No ``make_serial``: reflexivity already gives every world a
        successor.

        Raises:
            ValueError: if some declared agent has no entry.
        """
        world_set = set(worlds)
        require_all_agents(agents, partial_relations, "RelationalFrame.from_partial_s5")
        closed = {agent: s5_closure(world_set, partial_relations[agent]) for agent in agents}
        return cls(agents=agents, worlds=world_set, relations=closed)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _build_successors(self) -> Dict[Agent, Dict[World, Set[World]]]:
        """Adjacency ``agent -> {world -> set of successors}``, every world present."""
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
        """Raise if ``relations`` names an unknown agent or an edge an unknown world."""
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

    # Each validator collects every violation instead of raising at the first,
    # so an unvalidated frame can be inspected or drawn with its defects.
    def _seriality_violations(self) -> List[str]:
        """Axiom D: every world has a successor (no dead ends)."""
        problems: List[str] = []
        for agent in sorted(self.agents, key=str):
            for world in sorted(self.worlds, key=str):
                if not self._successors[agent][world]:
                    problems.append(
                        f"Seriality (D) violated: agent {agent!r} has no outgoing "
                        f"edge from world {world!r}; every world needs a successor."
                    )
        return problems

    def _reflexivity_violations(self) -> List[str]:
        """Axiom T: every world accesses itself."""
        problems: List[str] = []
        for agent in sorted(self.agents, key=str):
            for world in sorted(self.worlds, key=str):
                if world not in self._successors[agent][world]:
                    problems.append(
                        f"Reflexivity (Axiom T) violated for agent {agent!r}: "
                        f"{world!r} does not access itself (not reflexive)."
                    )
        return problems

    def _transitivity_violations(self) -> List[str]:
        """Axiom 4: w -> u and u -> v imply w -> v."""
        problems: List[str] = []
        for agent in sorted(self.agents, key=str):
            adjacency = self._successors[agent]
            for w, w_succ in adjacency.items():
                for u in w_succ:
                    for v in adjacency[u]:
                        if v not in w_succ:
                            problems.append(
                                f"Transitivity (4) violated for agent {agent!r}: "
                                f"{w!r} -> {u!r} and {u!r} -> {v!r} exist, but the "
                                f"required edge {w!r} -> {v!r} is missing."
                            )
        return problems

    def _euclidean_violations(self) -> List[str]:
        """Axiom 5: w -> u and w -> v imply u -> v."""
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

    def kd45_violations(self) -> List[str]:
        """Every KD45 violation (D + 4 + 5), whatever the frame's own ``axiom_d``."""
        return (
            self._seriality_violations()
            + self._transitivity_violations()
            + self._euclidean_violations()
        )

    def k45_violations(self) -> List[str]:
        """Every K45 violation (4 + 5): dead ends are legal (defunct belief)."""
        return self._transitivity_violations() + self._euclidean_violations()

    def s5_violations(self) -> List[str]:
        """Every reason some relation is not an equivalence relation (T + 4 + 5).

        The single S5 test of the repo: knowledge requires it, and
        :meth:`logic_label` detects it.
        """
        return self._reflexivity_violations() + self.k45_violations()

    def violations(self) -> List[str]:
        """Violations of the declared logic: KD45 if ``axiom_d``, else K45."""
        return self.kd45_violations() if self.axiom_d else self.k45_violations()

    def is_valid(self) -> bool:
        """True iff the frame satisfies its declared axioms."""
        return not self.violations()

    def missing_edges(self) -> Dict[Agent, Set[Edge]]:
        """Per agent, the edges axioms 4/5 require but the frame lacks.

        Seriality is not represented (a dead end has no canonical missing
        target); see :meth:`dead_ends`.
        """
        missing: Dict[Agent, Set[Edge]] = {}
        for agent in self.agents:
            closure = _transitive_euclidean_closure(self.worlds, self.relations[agent])
            required = {(w, v) for w, targets in closure.items() for v in targets}
            missing[agent] = required - self.relations[agent]
        return missing

    def dead_ends(self) -> Dict[Agent, Set[World]]:
        """Per agent, the worlds with no outgoing edge."""
        return {
            agent: {w for w in self.worlds if not self._successors[agent][w]}
            for agent in self.agents
        }

    def successors(self, agent: Agent, world: World) -> Set[World]:
        """The worlds ``agent`` accesses from ``world``."""
        return set(self._successors[agent][world])

    def logic_label(self) -> str:
        """``"S5"`` when every relation is an equivalence (detected), else the
        declared ``"KD45"`` or ``"K45"``."""
        if self.agents and not self.s5_violations():
            return "S5"
        return "KD45" if self.axiom_d else "K45"

    def __repr__(self) -> str:
        n_edges = sum(len(edges) for edges in self.relations.values())
        return (
            f"{type(self).__name__}(logic={self.logic_label()}, "
            f"agents={len(self.agents)}, "
            f"worlds={len(self.worlds)}, edges={n_edges})"
        )

#########
# Helper functions
#########

def require_all_agents(
    agents: Iterable[Agent],
    relations: Mapping,
    caller: str,
    mapping_name: str = "relations",
) -> None:
    """Raise unless every declared agent has an entry in ``relations``.

    A forgotten agent is never given a default relation: say "no seed edges"
    with an explicit empty set.
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
    """Materialise one agent's edges, rejecting a whole ``agent -> edges`` mapping.

    Iterating a mapping yields its keys, which would fail deep inside the
    closure with an unhelpful error; this names the mistake instead.

    Raises:
        TypeError: if ``edges`` is a mapping or contains a non-pair item.
    """
    family_helper = (
        "RelationalFrame.from_partial_s5" if caller == "s5_closure"
        else "RelationalFrame.from_partial"
    )
    if isinstance(edges, Mapping):
        raise TypeError(
            f"{caller}(worlds, edges) takes ONE agent's edges, not a mapping of "
            f"{len(edges)} agents. Call {caller}(worlds, relations[agent]) per "
            f"agent, or {family_helper}(agents, worlds, relations) for all at once."
        )
    out = list(edges)
    for item in out:
        if isinstance(item, (str, bytes)) or not isinstance(item, tuple) or len(item) != 2:
            raise TypeError(
                f"{caller}(worlds, edges) expects (source, target) pairs, got {item!r}."
            )
    return out


def kd45_closure(
    worlds: Iterable[World],
    edges: Iterable[Edge],
    make_serial: bool = False,
) -> Set[Edge]:
    """The KD45 closure of one agent's relation: the least transitive + Euclidean
    superset, then seriality.

    The 4+5 closure never gives a successor to a world that had none, so the
    dead ends after closure are the seed's isolated worlds. ``make_serial``
    gives each a self-loop; otherwise they are an error (there is no canonical
    successor to invent).

    Raises:
        ValueError: an edge names a world not in ``worlds``; or dead ends remain
            and ``make_serial`` is False.
        TypeError: ``edges`` is a mapping or not an iterable of pairs.
    """
    world_set: Set[World] = set(worlds)
    succ = _transitive_euclidean_closure(world_set, _as_edge_list(edges, "kd45_closure"))
    dead_ends = {w for w in world_set if not succ[w]}
    if dead_ends:
        if make_serial:
            for w in dead_ends:
                succ[w].add(w)
        else:
            raise ValueError(
                f"Seriality (D) cannot be closed automatically for isolated "
                f"worlds {sorted(map(str, dead_ends))}; pass make_serial=True to "
                f"give each a self-loop, or add an outgoing edge manually."
            )
    return {(w, v) for w, targets in succ.items() for v in targets}


def k45_closure(worlds: Iterable[World], edges: Iterable[Edge]) -> Set[Edge]:
    """The K45 closure of one agent's relation: transitive + Euclidean, no seriality.

    A world the seed leaves without a successor keeps none: a defunct belief,
    legal in K45 (thesis ch. 3).
    """
    world_set: Set[World] = set(worlds)
    succ = _transitive_euclidean_closure(world_set, _as_edge_list(edges, "k45_closure"))
    return {(w, v) for w, targets in succ.items() for v in targets}


def _transitive_euclidean_closure(
    world_set: Set[World], edges: Iterable[Edge]
) -> Dict[World, Set[World]]:
    """The transitive + Euclidean closure as an adjacency map ``world -> successors``.

    Shared by the three closures and by :meth:`RelationalFrame.missing_edges`.
    Both axioms only ever add edges, so iterating to a fixpoint gives the least
    closure.

    Raises:
        ValueError: if an edge names a world not in ``world_set``.
    """
    succ: Dict[World, Set[World]] = {w: set() for w in world_set}
    for source, target in edges:
        if source not in world_set or target not in world_set:
            raise ValueError(
                f"Edge ({source!r} -> {target!r}) references a world not in "
                f"{sorted(map(str, world_set))}."
            )
        succ[source].add(target)
    # list(...) copies: the loop mutates the sets it iterates over.
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
    """The S5 closure of one agent's relation: the least equivalence relation
    containing the seed (knowledge).

    Every self-loop is added first; the 4+5 closure of a reflexive relation is
    symmetric and transitive, hence an equivalence.
    """
    world_set: Set[World] = set(worlds)
    seeded = set(_as_edge_list(edges, "s5_closure")) | {(w, w) for w in world_set}
    return kd45_closure(world_set, seeded)

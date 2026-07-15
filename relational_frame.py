"""Relational (Kripke) frames for KD45 belief logic.

This module implements a *purely structural* relational model: worlds are nodes
and accessibility relations are directed edges, one relation per agent. There are
no propositions, no valuations and no logical formulas here -- only the graph
structure and the KD45 frame conditions that characterise (consistent) belief.

KD45 frame conditions:
    * Seriality      (Axiom D):  every world has at least one successor.
    * Transitivity   (Axiom 4):  w -> u and u -> v  implies  w -> v.
    * Euclideanness  (Axiom 5):  w -> u and w -> v  implies  u -> v.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Dict, Hashable, Iterable, List, Set, Tuple

# Default directory where all generated artifacts (.dot / images) are written.
OUTPUT_DIR = "outputs"

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

    Attributes:
        agents: The set of agent identifiers.
        worlds: The set of world identifiers (graph nodes).
        relations: Mapping ``agent -> set of (source, target)`` edges.
        _successors: Precomputed adjacency ``agent -> {world -> set of successors}``
            used for efficient axiom checking.
    """

    # Qualitative, colour-blind-safe palette (Okabe-Ito). Agents are assigned a
    # colour by their sorted position; the list cycles if there are more agents
    # than colours. Kept as a class attribute so it is easy to override globally.
    _PALETTE = (
        "#0072B2",  # blue
        "#D55E00",  # vermillion
        "#009E73",  # green
        "#CC79A7",  # purple
        "#E69F00",  # orange
        "#56B4E9",  # sky blue
        "#000000",  # black
    )

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
        self.agents: Set[Agent] = set(agents)
        self.worlds: Set[World] = set(worlds)
        self.relations: Dict[Agent, Set[Edge]] = {
            agent: set(edges) for agent, edges in relations.items()
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

        Returns:
            A fully validated :class `RelationalFrame`.
        """
        world_set = set(worlds)
        closed: Dict[Agent, Set[Edge]] = {}
        for agent in agents:
            seed = partial_relations.get(agent, set())
            # Close THIS agent's relation only -- never mix agents' edges.
            closed[agent] = kd45_closure(world_set, seed, make_serial=make_serial)
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
                    f"Unknown agent {agent!r} in relations; "
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
        #NOT SURE ABOUT THIS. Am I understanding it correctly?
        #todo: to verify
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
    # Convenience / introspection
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
        """Return, per agent, the worlds that have no outgoing edge (seriality/D).

        A world with no successor for some agent is a dead end: that agent's
        beliefs would be inconsistent there. Unlike :meth:`missing_edges`, there is
        no canonical edge to add, so these are reported as offending *worlds*.
        """
        return {
            agent: {w for w in self.worlds if not self._successors[agent][w]}
            for agent in self.agents
        }

    def successors(self, agent: Agent, world: World) -> Set[World]:
        """Return the set of worlds directly accessible for ``agent`` from ``world``."""
        return set(self._successors[agent][world])

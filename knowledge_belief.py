"""Relational models for knowledge AND belief (Sink's thesis, ch. 2).

A :class:`KnowledgeBeliefFrame` has two relations per agent: knowledge ``R_a``,
an equivalence relation (S5), and belief ``Q_a`` with ``Q_a ⊆ R_a``, serial
(KD45; not required under K45) and constant on ``R_a``-classes. These validate
the interaction axioms ``K_a φ → B_a φ``, ``B_a φ → K_a B_a φ``,
``¬B_a φ → K_a ¬B_a φ`` and, with D, ``B_a φ → ¬B_a ¬φ`` (docs/01 §3, docs/07).

Properness is a condition on knowledge; :meth:`KnowledgeBeliefFrame.to_proper`
skews both relations with the same distinguished agent, so ``Q_a ⊆ R_a``
survives (docs/02).
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Optional, Set

from properness import choose_distinguished, copy_and_skew
from properness import is_proper as _frame_is_proper
from properness import properness_violations as _frame_properness_violations
from relational_frame import (
    Agent,
    Edge,
    RelationalFrame,
    World,
    k45_closure,
    kd45_closure,
    require_all_agents,
    s5_closure,
)


def require_s5_relation(knowledge: RelationalFrame, caller: str = "knowledge_classes") -> None:
    """Raise unless every relation of ``knowledge`` is an equivalence (S5).

    :func:`knowledge_classes` reads the partition off the successor sets, which
    is only a partition for an equivalence relation; a frame built with
    ``validate=False`` could otherwise yield garbage silently.
    """
    problems = knowledge.s5_violations()
    if problems:
        raise ValueError(
            f"{caller} needs S5 (equivalence) knowledge relations, but this frame is "
            f"not even reflexive/transitive/Euclidean everywhere (Axiom T, 4, 5):\n  - "
            + "\n  - ".join(problems)
            + "\nBuild knowledge with RelationalFrame.from_partial_s5(...) or "
            "relational_frame.s5_closure(...)."
        )


def knowledge_classes(knowledge: RelationalFrame, agent: Agent) -> List[FrozenSet[World]]:
    """Agent ``a``'s equivalence classes ``[w]_a``, ordered by their first world.

    Raises:
        ValueError: if the knowledge relations are not equivalence relations.
    """
    require_s5_relation(knowledge, "knowledge_classes")
    seen: Set[World] = set()
    out: List[FrozenSet[World]] = []
    # Under S5 the successor set of w IS its class.
    for w in sorted(knowledge.worlds, key=str):
        if w in seen:
            continue
        cls = frozenset(knowledge.successors(agent, w))
        seen |= cls
        out.append(cls)
    return out


def belief_closure(
    knowledge: RelationalFrame,
    agent: Agent,
    seed: Iterable[Edge],
    believe_all_when_silent: bool = True,
    trim_out_of_class: bool = False,
    axiom_d: bool = True,
) -> Set[Edge]:
    """Close a belief seed into a valid ``Q_a`` relative to the knowledge ``R_a``.

    ``Q_a ⊆ R_a`` and constancy on classes force the shape: for each knowledge
    class ``C`` a set ``B_a(C) ⊆ C`` with ``Q_a(w) = B_a(C)`` for every ``w ∈ C``
    (KD45 then holds automatically). Per class:

    * seed targets inside ``C``: ``B_a(C)`` is their union (the unique minimum);
    * a target outside ``C``: an error, or dropped with ``trim_out_of_class``;
    * no seed at all: ``B_a(C) = C``, *believe exactly what you know*, the
      project's convention in both logics (docs/07 §3). With
      ``believe_all_when_silent=False`` that is an error under KD45 and the
      empty, defunct cluster under K45.

    Raises:
        ValueError: knowledge is not S5; a seed leaves its class (without
            ``trim_out_of_class``); a silent class with
            ``believe_all_when_silent=False`` under KD45.
    """
    seed_edges = set(seed)
    relation: Set[Edge] = set()
    for cls in knowledge_classes(knowledge, agent):
        believed = {u for (w, u) in seed_edges if w in cls}
        outside = believed - cls
        if outside and trim_out_of_class:
            believed -= outside
            outside = set()
        if outside:
            raise ValueError(
                f"Belief seed for agent {agent!r} puts {sorted(map(str, outside))} in "
                f"Q_{agent} from knowledge class {sorted(map(str, cls))}, but "
                f"Q_a ⊆ R_a forbids it: those worlds are not epistemically possible "
                f"there, so the agent cannot believe them possible. No valid Q_a "
                f"contains this seed -- widen the knowledge relation or drop the edge."
            )
        if not believed and not believe_all_when_silent and not axiom_d:
            continue  # explicit request for a defunct (empty) cluster, legal in K45
        if not believed:
            if not believe_all_when_silent:
                raise ValueError(
                    f"Belief seed for agent {agent!r} says nothing about knowledge "
                    f"class {sorted(map(str, cls))}, so Q_{agent} would not be serial "
                    f"there. Seed a belief for that class, or pass "
                    f"believe_all_when_silent=True to default to believing exactly "
                    f"what is known."
                )
            believed = set(cls)
        relation |= {(w, u) for w in cls for u in believed}
    return relation


class KnowledgeBeliefFrame:
    """A relational model with a knowledge and a belief relation per agent.

    Both are stored as inner :class:`RelationalFrame` objects. Validation checks
    knowledge S5, belief KD45 (K45 when ``axiom_d=False``), ``Q_a ⊆ R_a`` and
    constancy of ``Q_a`` on ``R_a``-classes.

    Attributes:
        agents, worlds: identifier sets.
        knowledge, belief: the inner frames holding ``R_a`` and ``Q_a``.
        axiom_d: belief logic, True = KD45, False = K45; carried through
            ``to_proper`` and read by ``to_simplicial``.
        projection: set by :meth:`to_proper`: copied world -> world it simulates.
    """

    def __init__(
        self,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        knowledge: Dict[Agent, Iterable[Edge]],
        belief: Dict[Agent, Iterable[Edge]],
        validate: bool = True,
        projection: Optional[Dict[World, World]] = None,
        axiom_d: bool = True,
    ) -> None:
        self.agents: Set[Agent] = set(agents)
        self.worlds: Set[World] = set(worlds)
        self.axiom_d: bool = axiom_d
        # Every declared agent gets an entry, so a missing one fails validation
        # with a readable message instead of a KeyError.
        self.knowledge = RelationalFrame(
            agents, worlds,
            {**{a: set() for a in self.agents}, **dict(knowledge)},
            validate=False,
        )
        self.belief = RelationalFrame(
            agents, worlds,
            {**{a: set() for a in self.agents}, **dict(belief)},
            validate=False,
            axiom_d=axiom_d,
        )
        self.projection: Dict[World, World] = dict(projection or {})
        if validate:
            problems = self.violations()
            if problems:
                raise ValueError(
                    f"{len(problems)} knowledge/belief violation(s) found:\n  - "
                    + "\n  - ".join(problems)
                )

    # ------------------------------------------------------------------ #
    # Construction from partial relations
    # ------------------------------------------------------------------ #
    @classmethod
    def from_partial(
        cls,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        knowledge: Dict[Agent, Iterable[Edge]],
        belief: Dict[Agent, Iterable[Edge]],
        believe_all_when_silent: bool = True,
        trim_out_of_class: bool = False,
        axiom_d: bool = True,
    ) -> "KnowledgeBeliefFrame":
        """Build a model from partial relations of both kinds (pipeline cases 2 and 3).

        ``R_a`` is closed under S5 first; ``Q_a`` is then closed by
        :func:`belief_closure` against those classes (belief cannot be closed on
        its own: it must fit inside what the agent knows). ``belief={}`` is
        knowledge-only input and yields ``Q_a = R_a``. When ``belief`` is
        non-empty every agent needs a key in both mappings (an explicit empty set
        means "no seed"). The keyword options go to :func:`belief_closure`;
        ``axiom_d`` fixes the belief logic for the whole pipeline.

        Raises:
            ValueError: belief seeds without any knowledge (use
                :meth:`from_beliefs_only`), an agent missing from one mapping,
                or a seed :func:`belief_closure` rejects.
        """
        world_set = set(worlds)
        agent_set = list(agents)
        if belief:
            if not knowledge:
                raise ValueError(
                    "from_partial got belief seeds but no knowledge at all. That "
                    "is case-1 input (beliefs only): use "
                    "KnowledgeBeliefFrame.from_beliefs_only, which induces each "
                    "R_a as the equivalence closure of Q_a. (from_partial would "
                    "instead default knowledge to the identity, which almost no "
                    "belief seed fits inside.)"
                )
            missing_k = sorted(str(a) for a in agent_set if a not in knowledge)
            missing_q = sorted(str(a) for a in agent_set if a not in belief)
            if missing_k or missing_q:
                raise ValueError(
                    "A knowledge+belief model needs BOTH relations for EVERY "
                    "agent, but this input mixes modalities: "
                    f"agent(s) {missing_k} have no knowledge entry and "
                    f"agent(s) {missing_q} have no belief entry. Give every "
                    "agent a key in both mappings -- an explicit empty set "
                    "(e.g. belief={'b': set()}) means 'no seed' and gets the "
                    "documented default (identity knowledge / believe exactly "
                    "what is known). If NO agent has belief seeds, pass "
                    "belief={} (case 3); if no agent has knowledge, use "
                    "from_beliefs_only (case 1)."
                )
        know_frame = RelationalFrame.from_partial_s5(
            agent_set, world_set, knowledge
        )
        belief_relations: Dict[Agent, Set[Edge]] = {
            a: belief_closure(
                know_frame, a, belief.get(a, set()),
                believe_all_when_silent, trim_out_of_class, axiom_d,
            )
            for a in agent_set
        }
        return cls(
            agent_set, world_set, know_frame.relations, belief_relations,
            axiom_d=axiom_d,
        )

    @classmethod
    def from_beliefs_only(
        cls,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        belief: Dict[Agent, Iterable[Edge]],
        axiom_d: bool = True,
    ) -> "KnowledgeBeliefFrame":
        """Build a model from belief seeds alone, inducing knowledge (pipeline case 1).

        Each ``Q_a`` is closed under KD45 (stranded worlds get a self-loop) or,
        with ``axiom_d=False``, under K45; ``R_a`` is then the equivalence closure
        of ``Q_a``. The result is always valid (docs/07 §2). Every agent needs an
        entry in ``belief`` (an explicit empty set means "no seed").

        Raises:
            ValueError: if some declared agent has no entry in ``belief``.
        """
        world_set = set(worlds)
        agent_set = list(agents)
        require_all_agents(agent_set, belief, "from_beliefs_only", "belief")
        belief_relations: Dict[Agent, Set[Edge]] = {
            a: (
                kd45_closure(world_set, belief[a], make_serial=True)
                if axiom_d
                else k45_closure(world_set, belief[a])
            )
            for a in agent_set
        }
        knowledge_relations: Dict[Agent, Set[Edge]] = {
            a: s5_closure(world_set, belief_relations[a]) for a in agent_set
        }
        return cls(
            agent_set, world_set, knowledge_relations, belief_relations,
            axiom_d=axiom_d,
        )

    # ------------------------------------------------------------------ #
    # Accessors
    # ------------------------------------------------------------------ #
    def knows(self, agent: Agent, world: World) -> Set[World]:
        """R_a(world): the worlds agent ``a`` considers possible (knowledge)."""
        return self.knowledge.successors(agent, world)

    def believes(self, agent: Agent, world: World) -> Set[World]:
        """Q_a(world): the worlds agent ``a`` believes possible (belief)."""
        return self.belief.successors(agent, world)

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def violations(self) -> List[str]:
        """Return every knowledge/belief structural violation (empty if valid)."""
        return (
            self._knowledge_not_equivalence()
            + self._belief_not_kd45()
            + self._belief_not_subset_of_knowledge()
            + self._belief_not_constant_on_knowledge_classes()
        )

    def is_valid(self) -> bool:
        """Return True iff the combined knowledge/belief model is well-formed."""
        return not self.violations()

    def _knowledge_not_equivalence(self) -> List[str]:
        return ["Knowledge (S5): " + v for v in self.knowledge.s5_violations()]

    def _belief_not_kd45(self) -> List[str]:
        logic = "KD45" if self.axiom_d else "K45"
        return [f"Belief ({logic}): " + v for v in self.belief.violations()]

    def _belief_not_subset_of_knowledge(self) -> List[str]:
        problems = []
        for a in sorted(self.agents, key=str):
            extra = self.belief.relations[a] - self.knowledge.relations[a]
            for (w, u) in sorted(extra, key=lambda e: (str(e[0]), str(e[1]))):
                problems.append(
                    f"Belief not ⊆ knowledge (K→B) for agent {a!r}: {w!r} believes "
                    f"{u!r} possible but does not know it possible."
                )
        return problems

    def _belief_not_constant_on_knowledge_classes(self) -> List[str]:
        problems = []
        for a in sorted(self.agents, key=str):
            for (w, w2) in sorted(
                self.knowledge.relations[a], key=lambda e: (str(e[0]), str(e[1]))
            ):
                if self.believes(a, w) != self.believes(a, w2):
                    problems.append(
                        f"Belief not constant on knowledge classes for agent {a!r}: "
                        f"{w!r} R {w2!r} (same knowledge) but their belief sets differ."
                    )
        return problems

    # ------------------------------------------------------------------ #
    # Properness (a condition on the knowledge relations) + conversion
    # ------------------------------------------------------------------ #
    def is_proper(self) -> bool:
        """Return True iff the knowledge relations are proper (bridge to simplicial)."""
        return _frame_is_proper(self.knowledge)

    def properness_violations(self) -> List[str]:
        """Return properness violations of the knowledge relations."""
        return _frame_properness_violations(self.knowledge)

    def to_proper(
        self, distinguished_agent: Optional[Agent] = None
    ) -> "ProperKnowledgeBeliefFrame":
        """Convert to a bisimilar proper model (Sink, Thm 2.4; ``properness.to_proper``).

        Knowledge and belief are skewed with the same distinguished agent, so
        ``Q_a ⊆ R_a`` and constancy on classes are preserved; the default agent
        is the one with the fewest non-reflexive edges over both relations. An
        already proper model is wrapped with the identity projection.
        """
        if not self.agents:
            raise ValueError("Cannot build a proper model from a frame with no agents.")
        if self.is_proper():
            return ProperKnowledgeBeliefFrame(
                self.agents,
                self.worlds,
                self.knowledge.relations,
                self.belief.relations,
                projection={w: w for w in self.worlds},
                axiom_d=self.axiom_d,
            )
        distinguished = choose_distinguished(
            self.agents, distinguished_agent, self.knowledge.relations, self.belief.relations,
        )
        new_worlds, know_rel, projection = copy_and_skew(
            self.worlds, self.agents, self.knowledge.relations, distinguished
        )
        _, belief_rel, _ = copy_and_skew(
            self.worlds, self.agents, self.belief.relations, distinguished
        )
        return ProperKnowledgeBeliefFrame(
            self.agents, new_worlds, know_rel, belief_rel, projection=projection,
            axiom_d=self.axiom_d,
        )

    def __repr__(self) -> str:
        belief_logic = "KD45" if self.axiom_d else "K45"
        return (
            f"{type(self).__name__}(logic=S5+{belief_logic}, "
            f"agents={len(self.agents)}, worlds={len(self.worlds)})"
        )


class ProperKnowledgeBeliefFrame(KnowledgeBeliefFrame):
    """A :class:`KnowledgeBeliefFrame` whose knowledge relations are proper, the
    precondition of ``simplicial.to_simplicial``. Validation adds the properness
    check to the parent's."""

    def __init__(
        self,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        knowledge: Dict[Agent, Iterable[Edge]],
        belief: Dict[Agent, Iterable[Edge]],
        validate: bool = True,
        projection: Optional[Dict[World, World]] = None,
        axiom_d: bool = True,
    ) -> None:
        super().__init__(
            agents, worlds, knowledge, belief, validate=validate,
            projection=projection, axiom_d=axiom_d,
        )
        if validate:
            problems = self.properness_violations()
            if problems:
                raise ValueError(
                    f"{len(problems)} properness violation(s) found:\n  - "
                    + "\n  - ".join(problems)
                )

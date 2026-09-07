"""Relational models for introspective knowledge AND belief (Sink's thesis).

A :class:`KnowledgeBeliefFrame` carries *two* relations per agent:

    * a knowledge relation ``R_a`` -- an equivalence relation (S5),
    * a belief relation ``Q_a`` -- with ``Q_a ⊆ R_a``, serial, and constant on
      ``R_a``-equivalence classes (if ``w R_a w'`` then ``Q_a(w) = Q_a(w')``).

These conditions (thesis, p. 10) make the model validate the interaction axioms
between knowledge and belief:

    * knowledge implies belief          K_a φ → B_a φ      (from Q_a ⊆ R_a)
    * consistency of belief             B_a φ → ¬B_a ¬φ    (from Q_a serial)
    * strong positive introspection     B_a φ → K_a B_a φ  (Q_a constant on classes)
    * strong negative introspection     ¬B_a φ → K_a ¬B_a φ

Properness (needed before the simplicial step) is a condition on the *knowledge*
relations. :meth:`KnowledgeBeliefFrame.to_proper` makes copies and skews a single
distinguished agent's relations -- applied to BOTH R_a and Q_a with the same
distinguished agent, so ``Q_a ⊆ R_a`` is preserved -- yielding a bisimilar proper
model.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Optional, Set

from properness import copy_and_skew, is_proper as _frame_is_proper
from properness import properness_violations as _frame_properness_violations
from relational_frame import (
    Agent,
    Edge,
    RelationalFrame,
    World,
    kd45_closure,
    require_all_agents,
    s5_closure,
)


def knowledge_classes(knowledge: RelationalFrame, agent: Agent) -> List[FrozenSet[World]]:
    """Return agent ``a``'s equivalence classes ``[w]_a`` under an S5 relation.

    Args:
        knowledge: A frame whose relations are equivalence relations.
        agent: The agent whose partition is wanted.

    Returns:
        The classes, each as a frozenset, in sorted-by-first-world order.
    """
    seen: Set[World] = set()
    out: List[FrozenSet[World]] = []
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
) -> Set[Edge]:
    """Close a *belief* seed into a valid ``Q_a``, relative to the knowledge ``R_a``.

    Unlike :func:`relational_frame.kd45_closure`, belief cannot be closed in
    isolation: ``Q_a`` has to fit inside the partition ``R_a`` induces, so the
    knowledge relation is a required input.

    Why this is well defined. Conditions ``Q_a ⊆ R_a`` and "``Q_a`` constant on
    ``R_a``-classes" together force ``Q_a`` to have exactly one shape: for each
    knowledge class ``C``, pick a non-empty ``B_a(C) ⊆ C``, and set
    ``Q_a(w) = B_a(C)`` for every ``w ∈ C``. Read it as *"within what you know,
    which worlds you actually believe possible"*; a false belief at ``w`` is just
    ``w ∉ B_a([w]_a)``. KD45 then comes for free: every ``u ∈ B_a(C)`` lies in
    ``C``, so ``Q_a(u) = B_a(C) = Q_a(w)``, which is exactly what transitivity and
    Euclideanness ask for, and ``B_a(C) != ∅`` gives seriality. So this function
    cannot produce an invalid ``Q_a``.

    Given a seed, each class falls into one of three cases:

    * **The seed constrains the class, from inside it.** ``B_a(C)`` is the union of
      the seed's targets over the whole class -- constancy forces every world in
      ``C`` to share one belief set, so the union is the smallest legal choice.
      This is the unique minimum.
    * **The seed points outside the class.** Refused by default: ``Q_a ⊆ R_a``
      forbids it and *no* valid ``Q_a`` contains such a seed, so there is nothing
      to fall back to. With ``trim_out_of_class=True`` the offending targets are
      dropped instead (the spec's "trim the cluster to the class" repair); if the
      trim empties a class's belief set, the silent-class rule below takes over.
    * **The seed says nothing about the class.** Seriality still demands a
      non-empty ``B_a(C)``, but no minimum exists -- the minimal choices are the
      singletons, and they are incomparable. The only canonical option is the
      maximum ``B_a(C) = C``: *believe exactly what you know*, inventing no opinion
      the seed did not state. This is the belief-side analogue of
      ``kd45_closure``'s ``make_serial``, and ``believe_all_when_silent=False``
      turns it into an error instead.

    Args:
        knowledge: The frame holding ``R_a`` (must be S5 for ``agent``).
        agent: The agent whose belief relation is being built.
        seed: Partial ``(world, believed_world)`` edges.
        believe_all_when_silent: If True, a class the seed ignores gets
            ``B_a(C) = C``; if False, such a class raises.
        trim_out_of_class: If True, seed targets outside their source's knowledge
            class are silently dropped (repair by trimming) instead of raising.

    Returns:
        The edge set of a ``Q_a`` satisfying all four knowledge/belief conditions.

    Raises:
        ValueError: If the seed puts a world outside its own knowledge class (and
            ``trim_out_of_class`` is False), or if it is silent on a class and
            ``believe_all_when_silent`` is False.
    """
    seed_edges = set(seed)
    relation: Set[Edge] = set()
    for cls in knowledge_classes(knowledge, agent):
        believed = {u for (w, u) in seed_edges if w in cls}
        outside = believed - cls
        if outside and trim_out_of_class:
            believed -= outside  # trim the cluster to the class; may go empty
            outside = set()
        if outside:
            raise ValueError(
                f"Belief seed for agent {agent!r} puts {sorted(map(str, outside))} in "
                f"Q_{agent} from knowledge class {sorted(map(str, cls))}, but "
                f"Q_a ⊆ R_a forbids it: those worlds are not epistemically possible "
                f"there, so the agent cannot believe them possible. No valid Q_a "
                f"contains this seed -- widen the knowledge relation or drop the edge."
            )
        if not believed:
            if not believe_all_when_silent:
                raise ValueError(
                    f"Belief seed for agent {agent!r} says nothing about knowledge "
                    f"class {sorted(map(str, cls))}, so Q_{agent} would not be serial "
                    f"there. Seed a belief for that class, or pass "
                    f"believe_all_when_silent=True to default to believing exactly "
                    f"what is known."
                )
            believed = set(cls)  # believe exactly what you know: no false belief here
        relation |= {(w, u) for w in cls for u in believed}
    return relation


class KnowledgeBeliefFrame:
    """A relational model with a knowledge relation and a belief relation per agent.

    Knowledge (``R_a``) and belief (``Q_a``) are each stored as an internal
    :class:`RelationalFrame` (reusing its adjacency/validation machinery). On
    construction the combined model is validated: knowledge is S5, belief is KD45,
    ``Q_a ⊆ R_a``, and ``Q_a`` is constant on ``R_a``-equivalence classes.

    Attributes:
        agents, worlds: identifier sets.
        knowledge: RelationalFrame holding the ``R_a`` relations.
        belief: RelationalFrame holding the ``Q_a`` relations.
        projection: when produced by :meth:`to_proper`, maps each copied world back
            to the world it simulates (the bisimilarity witness); empty otherwise.
    """

    def __init__(
        self,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        knowledge: Dict[Agent, Iterable[Edge]],
        belief: Dict[Agent, Iterable[Edge]],
        validate: bool = True,
        projection: Optional[Dict[World, World]] = None,
    ) -> None:
        self.agents: Set[Agent] = set(agents)
        self.worlds: Set[World] = set(worlds)
        # Reuse RelationalFrame for storage, successors and the KD45 validators.
        # Normalise both mappings so EVERY declared agent has an entry: an agent
        # missing from one of them then fails validation with the honest message
        # (seriality / reflexivity) instead of a KeyError deep in violations().
        # Merging (not filtering) keeps unknown-agent keys visible, so the
        # structural check still rejects them by name.
        self.knowledge = RelationalFrame(
            agents, worlds,
            {**{a: set() for a in self.agents}, **dict(knowledge)},
            validate=False,
        )
        self.belief = RelationalFrame(
            agents, worlds,
            {**{a: set() for a in self.agents}, **dict(belief)},
            validate=False,
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
    ) -> "KnowledgeBeliefFrame":
        """Build a knowledge+belief model from *partial* relations of both kinds.

        The entry point for someone coming from the thesis: write only the edges
        that matter and let the closures force the rest, for both relations at once.

        The two families are NOT closed the same way, and the order is not
        symmetric:

        1. ``R_a`` is closed under S5 by :func:`relational_frame.s5_closure`. It
           stands on its own -- knowledge needs nothing but its own seed.
        2. ``Q_a`` is then closed by :func:`belief_closure` **against the classes
           ``R_a`` just produced**. Belief cannot be closed in isolation: it has to
           fit inside what the agent knows.

        Closing ``Q_a`` with ``kd45_closure`` instead would be the natural-looking
        mistake. It produces a valid KD45 relation that then fails ``Q_a ⊆ R_a`` or
        constancy on classes, and the constructor rejects it -- blaming your seed
        for what the closure did. Going through :func:`belief_closure` makes all
        four conditions hold by construction; the validation below is a safety net,
        not a gate.

        Args:
            agents, worlds: identifier sets.
            knowledge: partial ``R_a`` edges per agent (closed under S5).
            belief: partial ``Q_a`` edges per agent (closed within ``R_a``'s classes).
            believe_all_when_silent: passed to :func:`belief_closure`; when a
                knowledge class gets no belief seed, default to believing exactly
                what is known there rather than raising.
            trim_out_of_class: passed to :func:`belief_closure`; repair a belief
                seed that points outside its knowledge class by dropping those
                targets, instead of raising.

        Returns:
            A fully validated :class:`KnowledgeBeliefFrame`.

        Raises:
            ValueError: If a belief seed cannot fit inside its knowledge class (see
                :func:`belief_closure`), or if the input mixes modalities per agent
                (see below).

        One model type for ALL agents. A knowledge+belief model gives *every*
        agent both relations; it cannot give some agents only knowledge and
        others only belief. So when ``belief`` is non-empty (case 2 input), every
        declared agent must appear as a key in BOTH mappings -- an agent with
        nothing to seed gets an explicit empty set, which documents the intent
        instead of letting a typo silently invent a default relation. A belief
        mapping that is entirely empty is case-3 input (knowledge only, belief
        defaults to ``Q_a = R_a`` everywhere) and stays valid; belief seeds with
        no knowledge at all are case-1 input and belong in
        :meth:`from_beliefs_only`, which *induces* the knowledge.
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
                believe_all_when_silent, trim_out_of_class,
            )
            for a in agent_set
        }
        return cls(
            agent_set, world_set, know_frame.relations, belief_relations
        )

    @classmethod
    def from_beliefs_only(
        cls,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        belief: Dict[Agent, Iterable[Edge]],
    ) -> "KnowledgeBeliefFrame":
        """Build a knowledge+belief model from *belief seeds alone* (case: only Q).

        The entry point when the modeller has only doxastic information -- no
        knowledge relations at all. Knowledge is *induced* from belief:

        1. Each ``Q_a`` seed is closed under KD45 by
           :func:`relational_frame.kd45_closure` (transitive + Euclidean closure,
           then a self-loop for every world left without a successor).
        2. ``R_a`` is the **equivalence closure** of that ``Q_a`` -- the smallest
           equivalence relation containing it, computed by
           :func:`relational_frame.s5_closure` (with a reflexive seed, closing
           under transitivity + Euclideanness IS the equivalence closure).

        This always yields a valid model, with no repair step: a KD45 ``Q_a`` is
        automatically contained in its equivalence closure, serial by
        construction, and constant on the induced classes -- within one weakly
        connected component every world points into the same final cluster
        (``w -> u`` forces ``Q_a(u) = Q_a(w)``), so the component shares one
        belief set. The constructor's validation below is a safety net.

        The induced ``R_a`` can perfectly well come out as the COMPLETE relation
        (e.g. Sink's Figure 1, where every world believes the same worlds
        possible). That is correct, not a bug: it just means the model is not
        proper, and :meth:`to_proper` handles it like any other case.

        EVERY declared agent must have an entry in ``belief``: a missing agent is
        reported, never silently given a default (an explicit empty set means "no
        seed edges" and yields the identity belief via the seriality repair).

        Args:
            agents, worlds: identifier sets.
            belief: partial ``Q_a`` edges per agent (closed under KD45).

        Returns:
            A fully validated :class:`KnowledgeBeliefFrame` whose knowledge is the
            equivalence closure of its belief.

        Raises:
            ValueError: If some declared agent has no entry in ``belief``.
        """
        world_set = set(worlds)
        agent_set = list(agents)
        require_all_agents(agent_set, belief, "from_beliefs_only", "belief")
        belief_relations: Dict[Agent, Set[Edge]] = {
            a: kd45_closure(world_set, belief[a], make_serial=True)
            for a in agent_set
        }
        # R_a := equivalence closure of Q_a (minimal equivalence containing it).
        knowledge_relations: Dict[Agent, Set[Edge]] = {
            a: s5_closure(world_set, belief_relations[a]) for a in agent_set
        }
        return cls(agent_set, world_set, knowledge_relations, belief_relations)

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
        # S5 / equivalence = reflexive + transitive + Euclidean (reflexive+Euclidean
        # already imply symmetric+transitive). We reuse the KD45 validators for
        # trans/Eucl/serial and add the reflexivity (Axiom T) check on top.
        problems = ["Knowledge (S5): " + v for v in self.knowledge.kd45_violations()]
        for a in sorted(self.agents, key=str):
            for w in sorted(self.worlds, key=str):
                if w not in self.knowledge.successors(a, w):
                    problems.append(
                        f"Knowledge not reflexive (Axiom T) for agent {a!r}: "
                        f"{w!r} does not access itself."
                    )
        return problems

    def _belief_not_kd45(self) -> List[str]:
        return ["Belief (KD45): " + v for v in self.belief.kd45_violations()]

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
        """Convert to a bisimilar PROPER knowledge/belief model (Sink, Thm 2.4).

        Copies the model and skews one distinguished agent's relations across
        copies. The SAME skew is applied to both knowledge and belief, so
        ``Q_a ⊆ R_a`` and constancy on classes are preserved. If already proper,
        the model is returned unchanged (with an identity projection).

        Args:
            distinguished_agent: The agent whose relations are skewed. Defaults to
                the agent with the FEWEST knowledge edges (ties broken by name).
                The result's size is the same for every choice -- ``|W|^2`` worlds,
                each edge copied ``|W|`` times whether skewed or not -- the sparse
                default just minimises the number of cross-copy (skewed) edges.

        Returns:
            A :class:`ProperKnowledgeBeliefFrame` whose :attr:`projection` maps each
            new world back to the original it simulates.
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
            )
        # >= 2 agents required (see properness.to_proper): a single non-proper agent has
        # no proper bisimilar model.
        if len(self.agents) < 2:
            raise ValueError(
                "No proper model bisimilar to this frame exists: a single-agent, "
                "non-proper frame cannot be made proper. Requires >= 2 agents."
            )
        # Default: skew the agent with the sparsest KNOWLEDGE relation (the
        # family properness is about). Size is invariant under the choice; the
        # sparse default only minimises the cross-copy edges. Same agent for
        # both families either way.
        distinguished = (
            distinguished_agent
            if distinguished_agent is not None
            else min(
                sorted(self.agents, key=str),
                key=lambda a: len(self.knowledge.relations[a]),
            )
        )
        if distinguished not in self.agents:
            raise ValueError(
                f"Unknown distinguished agent {distinguished!r}; "
                f"choose one of {sorted(map(str, self.agents))}."
            )
        # Same distinguished agent for both families -> Q_a ⊆ R_a preserved.
        new_worlds, know_rel, projection = copy_and_skew(
            self.worlds, self.agents, self.knowledge.relations, distinguished
        )
        _, belief_rel, _ = copy_and_skew(
            self.worlds, self.agents, self.belief.relations, distinguished
        )
        return ProperKnowledgeBeliefFrame(
            self.agents, new_worlds, know_rel, belief_rel, projection=projection
        )

    def __repr__(self) -> str:
        return (
            f"KnowledgeBeliefFrame(agents={len(self.agents)}, "
            f"worlds={len(self.worlds)})"
        )


class ProperKnowledgeBeliefFrame(KnowledgeBeliefFrame):
    """A :class:`KnowledgeBeliefFrame` whose knowledge relations are *proper*.

    Construction validates everything the parent does (knowledge S5, belief KD45,
    ``Q_a ⊆ R_a``, belief constant on knowledge classes) AND properness of the
    knowledge relations (no two distinct worlds jointly accessible to every
    agent). This is the exact
    precondition the simplicial translation needs: because the model is proper,
    each world corresponds to a distinct facet of the complex.

    Usually produced by :meth:`KnowledgeBeliefFrame.to_proper`, in which case
    :attr:`projection` maps each copied world back to the world it simulates -- the
    bounded morphism that witnesses bisimilarity with the original model.
    """

    def __init__(
        self,
        agents: Iterable[Agent],
        worlds: Iterable[World],
        knowledge: Dict[Agent, Iterable[Edge]],
        belief: Dict[Agent, Iterable[Edge]],
        validate: bool = True,
        projection: Optional[Dict[World, World]] = None,
    ) -> None:
        super().__init__(
            agents, worlds, knowledge, belief, validate=validate, projection=projection
        )
        if validate:
            problems = self.properness_violations()
            if problems:
                raise ValueError(
                    f"{len(problems)} properness violation(s) found:\n  - "
                    + "\n  - ".join(problems)
                )

    def __repr__(self) -> str:
        return (
            f"ProperKnowledgeBeliefFrame(agents={len(self.agents)}, "
            f"worlds={len(self.worlds)})"
        )

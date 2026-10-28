"""Simplicial actions and the knowledge product M[A] (Sink's thesis, Def. 4.5).

Preconditions come in two forms, both per action node:

    * LITERALS (``pre``: ``{node: {atom: 0|1}}``), the ``L_A`` of the thesis
      (p. 50), compared three-valuedly with what the input perspective
      OBSERVES (``compatible``);
    * FORMULAS (``pre_formula``: ``{node: φ}``), as in the general action
      models of DEL and of Goubault, Ledent & Rajsbaum, where φ may be modal
      (``K_a``, ``B_a``). A formula is evaluated at the INPUT FACETS
      (``assignment.holds``), the only place where modalities mean something:
      a facet ``(X, Y)`` exists only if ``X ⊨ pre(π_a(Y))`` for every agent,
      and an input node ``x`` pairs with ``y`` only if ``pre(y)`` is possible
      for it (some facet through ``x`` satisfies it; mode 1 demands every
      facet, "x knows it").

Postconditions are literals (``post``).
"""
from __future__ import annotations

from typing import Dict, FrozenSet, Hashable, Iterable, List, NamedTuple, Set, Tuple

from assignment import (
    FALSE,
    TRUE,
    UNKNOWN,
    Assignment,
    assignment_violations,
    facet_inconsistencies,
    holds,
    is_consistent_facet,
    node_value,
    require_consistent,
)
from knowledge_belief import KnowledgeBeliefFrame
from relational_frame import RelationalFrame
from semantics import holds_kripke
from simplicial import Facet, Node, SimplicialBeliefModel, label_facet, label_node

Agent = Hashable
Formula = tuple   # assignment.holds syntax: ("atom", P), ("K", a, f), ("imp", f, g)...
# Node-pairing modes, numbered AS IN THE THESIS (p. 51): mode 2 is the clause of
# Def. 4.5 ("no clash") and the default; 0 and 1 are the stricter one-directional
# readings listed there.
MODES = (0, 1, 2)
DEFAULT_MODE = 2


def action_node(agent: Agent, name: Hashable) -> Node:
    return Node(agent, frozenset({name}))


def node_name(node: Node) -> str:
    # display name so "as" or "⟨a0,as⟩" 
    # nodes coming from to_simplicial() print as "{w0,w1}".
    if len(node.cls) == 1:
        return str(next(iter(node.cls)))
    return "{" + ",".join(sorted(map(str, node.cls))) + "}"


class Pair(NamedTuple):
    # it will be used a dict key in update_model() to look nodes up by their components
    input: Node
    action: Node
    def __str__(self) -> str:
        return f"⟨{node_name(self.input)},{node_name(self.action)}⟩"


def pair_of(node: Node) -> Pair:
    # unpack an output node back into (input node, action node)
    (member,) = node.cls
    if not isinstance(member, Pair):
        raise ValueError(f"{label_node(node)} is not a product node")
    return member


def facet_name(facet: Facet, names: Dict[Facet, Hashable]) -> Hashable:
    # name lookup 
    if facet in names:
        return names[facet]
    return "{" + ",".join(node_name(n) for n in sorted(facet, key=lambda n: str(n.agent))) + "}"


# (shallow) copying 
class SimplicialAction:
    def __init__(
        self,
        agents: Iterable[Agent],
        nodes: Iterable[Node],
        facets: Iterable[Facet],
        pre: Assignment | None = None,
        post: Assignment | None = None,
        event_of_facet: Dict[Facet, Hashable] | None = None,
        validate: bool = True,
        pre_formula: Dict[Node, Formula] | None = None,
        pre_event: Dict[Facet, Formula] | None = None,
    ) -> None:
        self.agents: Set[Agent] = set(agents)
        self.nodes: Set[Node] = set(nodes)
        self.facets: Set[Facet] = set(facets)
        self.pre: Assignment = {n: dict(v) for n, v in (pre or {}).items()}
        self.post: Assignment = {n: dict(v) for n, v in (post or {}).items()}
        # Per node, a formula the input world must satisfy for the event to
        # happen there (see the module docstring); evaluated at facets.
        self.pre_formula: Dict[Node, Formula] = dict(pre_formula or {})
        # Per EVENT, a formula the input world must satisfy (the precondition
        # of a Kripke action model, Def. 4.4, attached to the whole event the
        # way Goubault, Ledent & Rajsbaum attach it to the facet). Checked at
        # facet level only; node-level pairing is unaffected.
        self.pre_event: Dict[Facet, Formula] = dict(pre_event or {})
        self.event_of_facet: Dict[Facet, Hashable] = dict(event_of_facet or {})
        if validate:
            problems = self.violations()
            if problems:
                raise ValueError(
                    f"{len(problems)} simplicial-action violation(s) found:\n  - "
                    + "\n  - ".join(problems)
                )

    @classmethod
    def from_events(
        cls,
        agents: Iterable[Agent],
        events: Dict[Hashable, Dict[Agent, Hashable]],
        pre: Dict[Hashable, Dict[Hashable, int]] | None = None,
        post: Dict[Hashable, Dict[Hashable, int]] | None = None,
        isolated: Dict[Agent, Iterable[Hashable]] | None = None,
        pre_formula: Dict[Hashable, Formula] | None = None,
        pre_event: Dict[Hashable, Formula] | None = None,
    ) -> "SimplicialAction":
        # Input format:
        #   events      = {"k": {"a": "as", "b": "b not r", "c": "c"}, ...}
        #   pre         = {"as": {"Pa": 1}}
        #   isolated    = {"a": ["a?"]}
        #   pre_formula = {"as": ("K", "a", ("atom", "Pa"))}   a formula per node name
        #   pre_event   = {"k": ("K", "a", ("atom", "Pa"))}    a formula per EVENT name
        # names to Nodes and call the constructor 
        agents = set(agents)
        by_name: Dict[Hashable, Node] = {}  # node name -> its Node
        event_of_facet: Dict[Facet, Hashable] = {}  # facet -> event name
        for event, perspectives in events.items():
            # one Node per (agent, name) in this event
            # frozenset of Nodes is the event's facet
            facet = frozenset(action_node(a, nm) for a, nm in perspectives.items())
            for n in facet:
                (nm,) = n.cls
                # setdefault stores the node the first time a name is seen and
                # returns the stored one afterwards. If it differs from n, there was an error
                if by_name.setdefault(nm, n) != n:
                    raise ValueError(f"Node name {nm!r} is used by more than one agent.")
            event_of_facet[facet] = event
        facet_of_event = {ev: F for F, ev in event_of_facet.items()}

        # isolated nodes
        for a, names in (isolated or {}).items():
            for nm in names:
                n = action_node(a, nm)
                if by_name.setdefault(nm, n) != n:
                    raise ValueError(f"Node name {nm!r} is used by more than one agent.")

        def resolve(table, what, copy=dict):
            # name-keyed table -> Node-keyed table; ``copy`` shapes the value
            # (a dict of literals, or one formula kept as it is).
            out = {}
            for nm, value in (table or {}).items():
                if nm not in by_name:
                    raise ValueError(f"{what} names unknown action node {nm!r}.")
                out[by_name[nm]] = copy(value)
            return out

        # the keys of event_of_facet are the facets
        return cls(
            agents,
            by_name.values(),
            event_of_facet,
            pre=resolve(pre, "pre"),
            post=resolve(post, "post"),
            event_of_facet=event_of_facet,
            pre_formula=resolve(pre_formula, "pre_formula", copy=lambda f: f) if pre_formula else None,
            pre_event={facet_of_event[ev]: phi for ev, phi in (pre_event or {}).items()
                       if ev in facet_of_event} or None,
        )

    def pi(self, agent: Agent, facet: Facet) -> Node:
        """``π_a(facet)``: the unique ``agent``-coloured node of an event (UCF)."""
        return _pi(agent, facet)

    def violations(self) -> List[str]:
        # best case scenario: empty list
        problems: List[str] = []
        if not self.facets:
            problems.append("The action has no facets (S_A is empty).")
        for n in sorted(self.nodes, key=label_node):
            if n.agent not in self.agents:
                problems.append(f"Action node {label_node(n)} has unknown agent {n.agent!r}.")
        for facet in sorted(self.facets, key=label_facet):
            # subset test
            if not facet <= self.nodes:
                problems.append(f"Action facet {label_facet(facet)} uses nodes outside N_A.")
            # each agent must appear exactly once per facet
            for a in sorted(self.agents, key=str):
                count = sum(1 for n in facet if n.agent == a)
                if count != 1:
                    problems.append(
                        f"UCF violated in S_A: facet {label_facet(facet)} has {count} "
                        f"node(s) of agent {a!r} (expected exactly 1)."
                    )
            # assignment.py clash finder on the preconditions
            for atom, t, f in facet_inconsistencies(facet, self.pre):
                problems.append(
                    f"Action facet {label_facet(facet)} is inconsistent on {atom!r}: "
                    f"{label_node(t)} requires it, {label_node(f)} requires its negation."
                )
        for what, table in (("pre", self.pre), ("post", self.post)):
            problems += [f"{what}: {p}" for p in assignment_violations(table)]
            for n in table:
                if n not in self.nodes:
                    problems.append(f"{what} mentions {label_node(n)}, which is not in N_A.")
        for n, phi in self.pre_formula.items():
            if n not in self.nodes:
                problems.append(f"pre_formula mentions {label_node(n)}, which is not in N_A.")
            problems += [f"pre_formula of {label_node(n)}: {m}" for m in formula_problems(phi)]
        for F, phi in self.pre_event.items():
            if F not in self.facets:
                problems.append(f"pre_event mentions {label_facet(F)}, which is not an event.")
            problems += [f"pre_event of {label_facet(F)}: {m}" for m in formula_problems(phi)]
        return problems

    def is_valid(self) -> bool:
        return not self.violations()

    def describe(self) -> str:
        def show(n: Node) -> str:
            s = node_name(n)
            pre = _literals(self.pre.get(n, {}))
            if n in self.pre_formula:
                pre.append(formula_text(self.pre_formula[n]))
            post = _literals(self.post.get(n, {}))
            if pre:
                s += "(" + ", ".join(pre) + ")"
            if post:
                s += "[" + ", ".join(post) + "]"
            return s

        lines = [f"SimplicialAction: {len(self.facets)} events, {len(self.nodes)} nodes"]
        for facet in sorted(self.facets, key=lambda F: str(facet_name(F, self.event_of_facet))):
            nodes = " ".join(show(n) for n in sorted(facet, key=lambda n: str(n.agent)))
            event = facet_name(facet, self.event_of_facet)
            if facet in self.pre_event:
                event = f"{event}({formula_text(self.pre_event[facet])})"
            lines.append(f"  event {event}: {nodes}")
        # nodes in no events
        in_events = {n for F in self.facets for n in F}
        loose = sorted(self.nodes - in_events, key=label_node)
        if loose:
            lines.append("  isolated: " + " ".join(show(n) for n in loose))
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"SimplicialAction(agents={len(self.agents)}, nodes={len(self.nodes)}, "
            f"events={len(self.facets)})"
        )


def _literals(values: Dict[Hashable, int]) -> List[str]:
    # {atom: value} -> ["P", "not Q"]
    # nothing is printed for value 2
    out = []
    for atom, v in sorted(values.items(), key=lambda kv: str(kv[0])):
        if v == TRUE:
            out.append(str(atom))
        elif v == FALSE:
            out.append(f"not {atom}")
    return out


CONNECTIVES = {"atom": 2, "bot": 1, "not": 2, "and": 3, "or": 3, "imp": 3, "K": 3, "B": 3}


def formula_problems(phi) -> List[str]:
    """Why ``phi`` is not a formula in ``assignment.holds`` syntax (empty = it is)."""
    if not isinstance(phi, tuple) or not phi or phi[0] not in CONNECTIVES:
        return [f"{phi!r} is not a formula tuple (tags: {sorted(CONNECTIVES)})"]
    if len(phi) != CONNECTIVES[phi[0]]:
        return [f"{phi!r} has {len(phi) - 1} argument(s), expected {CONNECTIVES[phi[0]] - 1}"]
    children = phi[1:] if phi[0] in ("not", "and", "or", "imp") else phi[2:]
    return [m for child in children for m in formula_problems(child)]


def formula_text(phi) -> str:
    """Readable form: ``K_a (P ∧ ¬Q)``."""
    tag = phi[0]
    if tag == "atom":
        return str(phi[1])
    if tag == "bot":
        return "⊥"
    if tag == "not":
        return "¬" + formula_text(phi[1])
    if tag in ("K", "B"):
        return f"{tag}_{phi[1]} {formula_text(phi[2])}"
    op = {"and": "∧", "or": "∨", "imp": "→"}[tag]
    return f"({formula_text(phi[1])} {op} {formula_text(phi[2])})"


class _Sat:
    """``X ⊨ φ`` on the input, memoised: formulas are asked many times per facet."""

    def __init__(self, model: SimplicialBeliefModel, assignment: Assignment) -> None:
        self.model, self.assignment = model, assignment
        self.cache: Dict[Tuple[Facet, Formula], bool] = {}
        self.facets_of: Dict[Node, List[Facet]] = {}
        for F in model.facets:
            for n in F:
                self.facets_of.setdefault(n, []).append(F)

    def __call__(self, X: Facet, phi: Formula) -> bool:
        key = (X, phi)
        if key not in self.cache:
            # Consistency was established once by require_consistent.
            self.cache[key] = holds(self.model, self.assignment, X, phi, check_consistency=False)
        return self.cache[key]

    def possible(self, x: Node, phi: Formula, mode: int) -> bool:
        """Node-level reading of a formula precondition.

        Mode 1 (thesis numbering): ``x`` KNOWS ``phi`` (it holds at every
        world through ``x``).
        Otherwise: ``phi`` is POSSIBLE for ``x`` (some world through ``x``
        satisfies it), the counterpart of the literal "no clash" test. An
        input node in no world can satisfy neither.
        """
        worlds = self.facets_of.get(x, [])
        if not worlds:
            return False
        if mode == 1:
            return all(self(X, phi) for X in worlds)
        return any(self(X, phi) for X in worlds)


def compatible(
    x: Node, y: Node, assignment: Assignment, pre: Assignment, mode: int = DEFAULT_MODE
) -> bool:
    # decide whether input node x and action node y become an output node;
    # the three modes are the three definitions of N[A] on p. 51 of the thesis
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}.")
    # check agent pairing 
    if x.agent != y.agent:
        return False
    # loop over atoms that appear in x's or y's dict (the union of their keys) 
    # avoid exponential 
    atoms = set(assignment.get(x, {})) | set(pre.get(y, {}))
    for p in atoms:
        # node_value returns 2 when the atom is missing
        lx, ly = node_value(assignment, x, p), node_value(pre, y, p)
        # implication "A -> B" is written "(not A) or B"
        if mode == 0:    # whatever x observes, the precondition states
            ok = (lx != TRUE or ly == TRUE) and (lx != FALSE or ly == FALSE)
        elif mode == 1:  # the precondition is observed by x
            ok = (ly != TRUE or lx == TRUE) and (ly != FALSE or lx == FALSE)
        else:            # mode 2, Def. 4.5: no clash
            ok = (lx != TRUE or ly != FALSE) and (lx != FALSE or ly != TRUE)
        if not ok:
            return False
    return True


def updated_values(
    x: Node, y: Node, assignment: Assignment, pre: Assignment, post: Assignment
) -> Dict[Hashable, int]:
    """Label of the output node ``(x, y)``: the label clause of thesis Def. 4.5
    (p. 50), applied exactly as written, atom by atom:

        L[A](x, y)(P) = Post(y)(P)   if Post(y)(P) != 2   (the event overwrites it)
                      = L_A(y)(P)    if L(x)(P) = 2       (x silent: the precondition is recorded)
                      = L(x)(P)      otherwise            (the input is kept)

    So a postcondition overrides the input even where the precondition is 2,
    and an input node silent on ``P`` that passes an event requiring ``P``
    comes out labelled with ``P`` (the middle case; discussed in GitHub #25).
    Only 0/1 are stored; 2 stays implicit.
    """
    out: Dict[Hashable, int] = {}
    atoms = set(assignment.get(x, {})) | set(pre.get(y, {})) | set(post.get(y, {}))
    for p in atoms:
        v_post = node_value(post, y, p)
        v_in = node_value(assignment, x, p)
        if v_post != UNKNOWN:      # 1. the event's postcondition
            v = v_post
        elif v_in == UNKNOWN:      # 2. x silent: the precondition L_A(y)
            v = node_value(pre, y, p)
        else:                      # 3. otherwise x's own value
            v = v_in
        if v != UNKNOWN:
            out[p] = v
    return out


class UpdateModel(NamedTuple):
    model: SimplicialBeliefModel
    assignment: Assignment
    product_nodes: FrozenSet[Node]  # every output node (same set as model.nodes)
    isolated: FrozenSet[Node]  # output nodes contained in no facet


def update_model(
    model: SimplicialBeliefModel,
    assignment: Assignment,
    action: SimplicialAction,
    mode: int = DEFAULT_MODE,
) -> UpdateModel:
    # fail early on bad inputs 
    # different agent sets can't be paired up
    # axiom.d = False
    if model.agents != action.agents:
        raise ValueError(
            f"Model agents {sorted(model.agents, key=str)} differ from action agents "
            f"{sorted(action.agents, key=str)}."
        )
    require_consistent(model, assignment)
    sat = _Sat(model, assignment)   # formula preconditions, evaluated at input facets
    # fixed agent order 
    agents = sorted(model.agents, key=str)

    # step 1: output nodes and their values
    # try every (input node, action node) combination, so a nested loop over model.nodes x action.nodes
    # complexity = sum over agents' (no.of input nodes of a) * (no. of action nodes of a)
    new_assignment: Assignment = {}
    # Pair(x, y) -> the output Node built from it
    product: Dict[Pair, Node] = {}
    for x in model.nodes:
        for y in action.nodes:
            if compatible(x, y, assignment, action.pre, mode) and (
                y not in action.pre_formula or sat.possible(x, action.pre_formula[y], mode)
            ):
                # the output node keeps x's agent
                n = Node(x.agent, frozenset({Pair(x, y)}))
                product[Pair(x, y)] = n
                values = updated_values(x, y, assignment, action.pre, action.post)
                if values:
                    new_assignment[n] = values

    # step 2: output facets
    # loop over (input facet X, action facet Y)
    # for each agent there is only one candidate output node (X_node_ag, Y_node_ag)
    # cost: len(model.facets) * len(action.facets) candidates
    facets: Set[Facet] = set()
    world_of_facet: Dict[Facet, Hashable] = {}
    projection: Dict[Facet, Hashable] = {}
    for X in model.facets:
        for Y in action.facets:
            # the event's formula preconditions must hold at the input world
            if not all(sat(X, action.pre_formula[y]) for y in Y if y in action.pre_formula):
                continue
            if Y in action.pre_event and not sat(X, action.pre_event[Y]):
                continue
            # one Pair per agent, in the fixed agent order
            pairs = [Pair(model.pi(a, X), _pi(a, Y)) for a in agents]
            # any pair rejected by compatible() kills the whole candidate
            if not all(p in product for p in pairs):
                continue
            F = frozenset(product[p] for p in pairs)
            # check for an atom that is 1 at one node of F and 0 at another, using new vals
            if not is_consistent_facet(F, new_assignment):
                continue
            facets.add(F)
            # name the output facet by where it came from like ("w2", "m") 
            world_of_facet[F] = (
                facet_name(X, model.world_of_facet),
                facet_name(Y, action.event_of_facet),
            )
            # to reuse world information from to_proper or to_simplicial 
            if X in model.projection:
                projection[F] = model.projection[X]

    # Step 3: result 
    product_nodes = frozenset(product.values())
    # isolated = output nodes minus every node used by some facet
    isolated = product_nodes - {n for F in facets for n in F}
    out = SimplicialBeliefModel(
        agents=model.agents,
        nodes=product_nodes,  # all output nodes, isolated ones included
        facets=facets,
        # knowledge-only output
        belief_facets={a: facets for a in model.agents},
        world_of_facet=world_of_facet,
        projection=projection,
        # if it's true then isolated nodes are a problem
        # now we only check facet structure to allow isolated nodes 
        axiom_d=False,
    )
    return UpdateModel(
        model=out,
        assignment=new_assignment,
        product_nodes=product_nodes,
        isolated=isolated,
    )


def _pi(agent: Agent, facet: Facet) -> Node:
    for n in facet:
        if n.agent == agent:
            return n
    raise ValueError(f"Facet {label_facet(facet)} has no {agent!r}-coloured node.")


# --------------------------------------------------------------------------- #
# Kripke action models and the translation in both directions (docs/12 §4).
#
# A simplicial action IS a chromatic complex over events, so the functor G of
# Goubault, Ledent & Rajsbaum applies to it unchanged: one Kripke "world" per
# event, two events indistinguishable for ``a`` iff they share ``a``'s node.
# The preconditions, which live on nodes here, become the conjunction, per
# event, of its nodes' literals and formulas (plus the event's own formula);
# the postconditions, the union of its nodes' literals. In the other
# direction a Kripke action model must be PROPER (two distinct events are
# told apart by some agent), exactly as a Kripke model must be to become a
# complex; nodes are then the classes (agent, {events}).
# --------------------------------------------------------------------------- #
TOP: Formula = ("not", ("bot",))


class RelationalAction(NamedTuple):
    """A Kripke action model ``⟨W_A, {R_{A,a}}, pre, post⟩`` (thesis Def. 4.4).

    Attributes:
        frame: events as worlds; ``R_{A,a}`` is an equivalence relation per
            agent (an S5 ``RelationalFrame``): the events ``a`` cannot tell apart.
        pre: ``event -> formula`` the input world must satisfy (``TOP`` when
            the event asks nothing).
        post: ``event -> {atom: 0|1}``, the factual change of the event.
        event_of_facet: ``action facet -> event name`` when the model came
            from a simplicial action, to trace events back.
    """

    frame: RelationalFrame
    pre: Dict[Hashable, Formula]
    post: Dict[Hashable, Dict[Hashable, int]]
    event_of_facet: Dict[Facet, Hashable]


def _conjunction(parts: List[Formula]) -> Formula:
    """``φ1 ∧ … ∧ φn`` as nested ``("and", ·, ·)``; ``TOP`` for no parts."""
    if not parts:
        return TOP
    out = parts[0]
    for phi in parts[1:]:
        out = ("and", out, phi)
    return out


def _literal_formulas(table: Dict[Hashable, int]) -> List[Formula]:
    return [("atom", p) if v == TRUE else ("not", ("atom", p))
            for p, v in sorted(table.items(), key=lambda kv: str(kv[0])) if v != UNKNOWN]


def to_relational_action(action: SimplicialAction) -> RelationalAction:
    """Read a simplicial action as a Kripke action model (``G`` on actions).

    Events are named by ``action.event_of_facet`` (else by their nodes); an
    agent relates two events iff they share its node; an event's precondition
    is the conjunction of its nodes' literals (``P`` for value 1, ``¬P`` for
    0), its nodes' formulas and its own ``pre_event`` formula; its
    postcondition is the union of its nodes' post literals.

    Raises:
        ValueError: two nodes of one event set the same atom to opposite
            values in their postconditions (the simplicial product would drop
            every output facet of that event; a Kripke event cannot say both).
    """
    agents = sorted(action.agents, key=str)
    names: Dict[Facet, Hashable] = {}
    seen: Dict[Hashable, Facet] = {}
    for F in sorted(action.facets, key=label_facet):
        w = action.event_of_facet.get(F, facet_name(F, {}))
        if w in seen:
            names[seen[w]] = facet_name(seen[w], {})
            w = facet_name(F, {})
        names[F], seen[w] = w, F
    relations: Dict[Agent, Set[Tuple[Hashable, Hashable]]] = {a: set() for a in agents}
    for a in agents:
        by_node: Dict[Node, List[Facet]] = {}
        for F in action.facets:
            by_node.setdefault(_pi(a, F), []).append(F)
        for group in by_node.values():
            for X in group:
                for Y in group:
                    relations[a].add((names[X], names[Y]))
    pre: Dict[Hashable, Formula] = {}
    post: Dict[Hashable, Dict[Hashable, int]] = {}
    for F in action.facets:
        parts: List[Formula] = []
        change: Dict[Hashable, int] = {}
        for n in sorted(F, key=lambda n: str(n.agent)):
            # Two nodes may demand the same literal (a public announcement
            # puts it on every node): one conjunct is enough.
            parts += [f for f in _literal_formulas(action.pre.get(n, {})) if f not in parts]
            if n in action.pre_formula and action.pre_formula[n] not in parts:
                parts.append(action.pre_formula[n])
            for atom, v in action.post.get(n, {}).items():
                if v == UNKNOWN:
                    continue
                if change.get(atom, v) != v:
                    raise ValueError(
                        f"event {names[F]!r} sets {atom!r} to both values in its nodes' "
                        "postconditions; it has no Kripke counterpart."
                    )
                change[atom] = v
        if F in action.pre_event:
            parts.append(action.pre_event[F])
        pre[names[F]] = _conjunction(parts)
        post[names[F]] = change
    frame = RelationalFrame(agents, names.values(), relations)
    return RelationalAction(frame, pre, post, names)


def action_from_relational(rel: RelationalAction) -> SimplicialAction:
    """A simplicial action from a PROPER Kripke action model (``F`` on actions).

    Nodes are the pairs (agent, class of events the agent cannot tell apart);
    events become facets. Preconditions, which a Kripke model attaches to
    events, go to ``pre_event`` unchanged. Postconditions live on nodes here,
    and a node is shared by every event of its class, so each literal of an
    event's postcondition is placed on a node whose class agrees on it (every
    event in that class sets the atom to the same value) -- the first such
    agent in name order. When no agent's class agrees the model is refused:
    that literal has no vertex-based home.

    Raises:
        ValueError: the model is not proper (two events nobody tells apart),
            or a postcondition literal cannot be placed on any node.
    """
    from knowledge_belief import knowledge_classes

    frame = rel.frame
    agents = sorted(frame.agents, key=str)
    events = sorted(frame.worlds, key=str)
    for i, e in enumerate(events):
        for f in events[i + 1:]:
            if all(f in frame.successors(a, e) for a in agents):
                raise ValueError(
                    f"the action model is not proper: events {e!r} and {f!r} are "
                    "indistinguishable for every agent, so they would be one facet."
                )
    class_of: Dict[Tuple[Agent, Hashable], Node] = {}
    for a in agents:
        for cls in knowledge_classes(frame, a):
            node = Node(a, frozenset(cls))
            for e in cls:
                class_of[(a, e)] = node
    facets = {e: frozenset(class_of[(a, e)] for a in agents) for e in events}
    post: Assignment = {}
    for e in events:
        for atom, v in rel.post.get(e, {}).items():
            carrier = next(
                (class_of[(a, e)] for a in agents
                 if all(rel.post.get(other, {}).get(atom) == v for other in class_of[(a, e)].cls)),
                None,
            )
            if carrier is None:
                raise ValueError(
                    f"the postcondition {atom!r} of event {e!r} cannot be placed on a node: "
                    "every agent confuses it with an event that sets the atom differently."
                )
            post.setdefault(carrier, {})[atom] = v
    pre_event = {facets[e]: rel.pre[e] for e in events if e in rel.pre and rel.pre[e] != TOP}
    return SimplicialAction(agents, class_of.values(), facets.values(), post=post,
                            event_of_facet={F: e for e, F in facets.items()},
                            pre_event=pre_event)


class KripkeProduct(NamedTuple):
    """``M[A]`` on the Kripke side: the frame, its valuation, and the pairs behind the worlds."""

    frame: object                      # RelationalFrame or KnowledgeBeliefFrame, like the input
    valuation: Dict[Hashable, Set]
    pair_of_world: Dict[Hashable, Tuple[Hashable, Hashable]]


def kripke_product(model, valuation: Dict[Hashable, Set], action: RelationalAction) -> KripkeProduct:
    """The product update of a Kripke model with a Kripke action model (Def. 4.4).

    Worlds are the pairs ``(x, y)`` with ``M, x ⊨ pre(y)``; ``(x, y) R_a (x', y')``
    iff ``x R_a x'`` and ``y R_{A,a} y'`` (the same for ``Q_a`` when the model
    has belief relations, the action being a knowledge action); the valuation
    is inherited from ``x`` and then overwritten by ``post(y)``. The world
    names are the pairs ``(x, y)`` themselves, which is what ``to_relational``
    names the facets of the simplicial product, so the two sides can be
    compared world by world (docs/12 §4).
    """
    kb = isinstance(model, KnowledgeBeliefFrame)
    kframe = model.knowledge if kb else model
    agents = sorted(kframe.agents, key=str)
    worlds = [(x, y) for x in sorted(kframe.worlds, key=str)
              for y in sorted(action.frame.worlds, key=str)
              if holds_kripke(model, valuation, x, action.pre.get(y, TOP))]
    present = set(worlds)

    def product_relation(get_succ):
        out: Dict[Agent, Set] = {a: set() for a in agents}
        for a in agents:
            for (x, y) in worlds:
                for x2 in get_succ(a, x):
                    for y2 in action.frame.successors(a, y):
                        if (x2, y2) in present:
                            out[a].add(((x, y), (x2, y2)))
        return out

    knowledge = product_relation(lambda a, x: kframe.successors(a, x))
    new_val: Dict[Hashable, Set] = {}
    atoms = set(valuation) | {p for ch in action.post.values() for p in ch}
    for p in atoms:
        new_val[p] = {(x, y) for (x, y) in worlds
                      if action.post.get(y, {}).get(p, TRUE if x in valuation.get(p, ()) else FALSE) == TRUE}
    if kb:
        belief = product_relation(lambda a, x: model.believes(a, x))
        frame = KnowledgeBeliefFrame(agents, worlds, knowledge, belief, validate=False,
                                     axiom_d=False)
    else:
        frame = RelationalFrame(agents, worlds, knowledge, validate=False, axiom_d=False)
    return KripkeProduct(frame, new_val, {w: w for w in worlds})


def describe_relational_action(rel: RelationalAction) -> str:
    """One line per event: its precondition, postcondition, and who confuses it with what."""
    agents = sorted(rel.frame.agents, key=str)
    lines = [f"Kripke action model: {len(rel.frame.worlds)} events"]
    for e in sorted(rel.frame.worlds, key=str):
        pre = rel.pre.get(e, TOP)
        parts = [f"pre {formula_text(pre)}" if pre != TOP else "pre ⊤"]
        if rel.post.get(e):
            parts.append("post " + ", ".join(_literals(rel.post[e])))
        confused = []
        for a in agents:
            others = sorted(str(f) for f in rel.frame.successors(a, e) if f != e)
            if others:
                confused.append(f"{a}~{{{','.join(others)}}}")
        parts.append("indistinguishable: " + (" ".join(confused) if confused else "none"))
        lines.append(f"  {e}: " + " · ".join(parts))
    return "\n".join(lines)

from __future__ import annotations

from typing import Dict, FrozenSet, Hashable, Iterable, List, NamedTuple, Set

from assignment import (
    FALSE,
    TRUE,
    UNKNOWN,
    Assignment,
    assignment_violations,
    facet_inconsistencies,
    is_consistent_facet,
    node_value,
    require_consistent,
)
from simplicial import Facet, Node, SimplicialBeliefModel, label_facet, label_node

Agent = Hashable
MODES = (1, 2, 3)
DEFAULT_MODE = 3


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
    ) -> None:
        self.agents: Set[Agent] = set(agents)
        self.nodes: Set[Node] = set(nodes)
        self.facets: Set[Facet] = set(facets)
        self.pre: Assignment = {n: dict(v) for n, v in (pre or {}).items()}
        self.post: Assignment = {n: dict(v) for n, v in (post or {}).items()}
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
    ) -> "SimplicialAction":
        # Input format:
        #   events   = {"k": {"a": "as", "b": "b not r", "c": "c"}, ...}
        #   pre      = {"as": {"Pa": 1}}
        #   isolated = {"a": ["a?"]}  
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

        # isolated nodes
        for a, names in (isolated or {}).items():
            for nm in names:
                n = action_node(a, nm)
                if by_name.setdefault(nm, n) != n:
                    raise ValueError(f"Node name {nm!r} is used by more than one agent.")

        def resolve(table, what):
            # key {name: {atom: value}} table as {Node: {atom: value}}.
            out: Assignment = {}
            for nm, atoms in (table or {}).items():
                if nm not in by_name:
                    raise ValueError(f"{what} names unknown action node {nm!r}.")
                out[by_name[nm]] = dict(atoms)
            return out

        # the keys of event_of_facet are the facets
        return cls(
            agents,
            by_name.values(),
            event_of_facet,
            pre=resolve(pre, "pre"),
            post=resolve(post, "post"),
            event_of_facet=event_of_facet,
        )

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
        return problems

    def is_valid(self) -> bool:
        return not self.violations()

    def describe(self) -> str:
        def show(n: Node) -> str:
            s = node_name(n)
            pre = _literals(self.pre.get(n, {}))
            post = _literals(self.post.get(n, {}))
            if pre:
                s += "(" + ", ".join(pre) + ")"
            if post:
                s += "[" + ", ".join(post) + "]"
            return s

        lines = [f"SimplicialAction: {len(self.facets)} events, {len(self.nodes)} nodes"]
        for facet in sorted(self.facets, key=lambda F: str(facet_name(F, self.event_of_facet))):
            nodes = " ".join(show(n) for n in sorted(facet, key=lambda n: str(n.agent)))
            lines.append(f"  event {facet_name(facet, self.event_of_facet)}: {nodes}")
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


def compatible(
    x: Node, y: Node, assignment: Assignment, pre: Assignment, mode: int = DEFAULT_MODE
) -> bool:
    # decide whether input node x and action node y become an output node
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
        if mode == 1:
            ok = (lx != TRUE or ly == TRUE) and (lx != FALSE or ly == FALSE)
        elif mode == 2:
            ok = (ly != TRUE or lx == TRUE) and (ly != FALSE or lx == FALSE)
        else:
            ok = (lx != TRUE or ly != FALSE) and (lx != FALSE or ly != TRUE)
        if not ok:
            return False
    return True


def updated_values(
    x: Node, y: Node, assignment: Assignment, pre: Assignment, post: Assignment
) -> Dict[Hashable, int]:
    # build the {atom: value} dict of the output node (x, y)
    out: Dict[Hashable, int] = {}
    # only consider atoms mentioned 
    atoms = set(assignment.get(x, {})) | set(pre.get(y, {})) | set(post.get(y, {}))
    for p in atoms:
        v_post = node_value(post, y, p)
        v_in = node_value(assignment, x, p)
        # greedy check 
        if v_post != UNKNOWN:  # 1. the action's post value, if it sets one
            v = v_post
        elif v_in == UNKNOWN:  # 2. x says nothing: take the action's pre value
            v = node_value(pre, y, p)
        else:  # 3. otherwise keep x's value
            v = v_in
        # store only 0 or 1 
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
            if compatible(x, y, assignment, action.pre, mode):
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

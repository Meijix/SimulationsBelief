"""Simplicial actions in the GUI: the action spec, its validation, its live
drawing, and applying it to a model with the knowledge product.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from . import base  # noqa: F401  (puts the repository root on sys.path first)
from simplicial import Node, SimplicialBeliefModel
from .base import OUTPUTS, _fname, _geometric_ok, _knowledge_only, blank_state, show
from .complex import (
    _consistent_part,
    build_simplicial,
    doc_from_model,
    simplicial_assignment,
    simplicial_state_from_editor,
)
from .formulas import parse_formula


# --------------------------------------------------------------------------- #
# Simplicial ACTIONS (GitHub #6, #13, #18). The GUI side of the action layer:
# an action is edited as a spec with the same shapes the complex editor uses
# (events are facets of action nodes, one per agent; pre/post conditions are
# vertex atoms), applied to the active model, and its result opens as a
# read-only document that is drawn, evaluated, saved and compared like any
# other. The spec, JSON-friendly:
#
#   {"name": str,
#    "events":   [{"name": "e1", "nodes": {agent: action-node name}}],  (UCF)
#    "isolated": {agent: [action-node names in no event]},
#    "pre":      {atom: {"true": [node names], "false": [node names]}},  (as vatoms)
#    "post":     {atom: {"true": [...], "false": [...]}},
#    "pre_formula": {node name: "K_a P"},        modal preconditions, formula syntax
#    "mode":     1 | 2 | 3,                      compatibility test, see ACTION_MODES
#    "update":   "knowledge" | ...}              which product to run, see UPDATE_KINDS
#
# WHAT IS WIRED AND WHAT IS PENDING. ``simplicial_actions.update_model``
# (spec-b) implements the KNOWLEDGE product: output nodes are compatible
# (input, action) pairs, output facets the consistent products, and the
# result is a knowledge complex (S_a = S, K45). The belief products -- with
# and without memory -- and belief revision are Taiba's work in progress
# (#6, #15); they are listed in UPDATE_KINDS so the interface already offers
# the choice, and apply_action refuses them with a clear message until the
# functions exist. Plugging one in is a one-line change in UPDATE_KINDS.
# --------------------------------------------------------------------------- #
from simplicial_actions import DEFAULT_MODE, MODES, SimplicialAction, update_model  # noqa: E402

ACTION_MODES = {
    # Labels follow simplicial_actions.compatible(): how an input vertex x and
    # an action node y must agree on every atom to form the output node (x, y).
    1: "1 · what the vertex observes must be in the precondition (x ⇒ pre)",
    2: "2 · the precondition must be observed at the vertex (pre ⇒ x)",
    3: "3 · enough that they do not contradict each other (default)",
}

# update kind -> (label, function or None while pending). The function takes
# (model, assignment, action, mode) and returns something with ``.model`` and
# ``.assignment`` (the shape of simplicial_actions.UpdateModel).
UPDATE_KINDS = {
    "knowledge": ("knowledge (spec-b's product)", update_model),
    # PENDING (Taiba, #6): belief product -- S_a of the result from the S_a of
    # input and action, without memory.
    "belief": ("belief without memory (pending, #6)", None),
    # PENDING (Taiba, #15): belief product with memory.
    "belief_memory": ("belief with memory (pending, #15)", None),
    # PENDING (Taiba, #6): belief revision as an action (cf. revision.py's rule).
    "revision": ("belief revision (pending, #6)", None),
}


def blank_action(agents: List[str], name: str = "action") -> dict:
    """An empty action spec with every key the editor and :func:`build_action` expect."""
    return {"name": name, "events": [], "isolated": {a: [] for a in agents},
            "pre": {}, "post": {}, "mode": DEFAULT_MODE, "update": "knowledge"}


ACTION_EXAMPLES = {
    "anuncio_noC": {
        "label": "Public announcement of ¬C (for the disaster complex)",
        "spec": {
            "name": "announcement ¬C",
            # One event everybody takes part in; each agent's action node
            # requires ¬C, so the vertices observing C are incompatible with
            # it and disappear: exactly the public announcement of ¬C.
            "events": [{"name": "announcement", "nodes": {"a": "a_oye", "b": "b_oye"}}],
            "isolated": {"a": [], "b": []},
            "pre": {"C": {"true": [], "false": ["a_oye", "b_oye"]}},
            "post": {},
            "mode": DEFAULT_MODE, "update": "knowledge",
        },
    },
}


def action_node_names(spec: dict) -> List[str]:
    """Every action-node name the spec mentions (events first, then isolated), no repeats."""
    seen: List[str] = []
    for ev in spec.get("events", []):
        for v in ev.get("nodes", {}).values():
            if v and v not in seen:
                seen.append(v)
    for names in spec.get("isolated", {}).values():
        for v in names:
            if v and v not in seen:
                seen.append(v)
    return seen


def _conditions(table: Dict[str, dict]) -> Dict[str, Dict[str, int]]:
    """vatoms-shaped ``{atom: {"true": [...], "false": [...]}}`` -> ``{node: {atom: 0|1}}``."""
    out: Dict[str, Dict[str, int]] = {}
    for atom, spec in (table or {}).items():
        for v in spec.get("true", []):
            out.setdefault(v, {})[atom] = 1
        for v in spec.get("false", []):
            out.setdefault(v, {})[atom] = 0
    return out


def spec_atoms(spec: dict) -> List[str]:
    """Every atom the spec itself names (the literal tables)."""
    return sorted(set(spec.get("pre") or {}) | set(spec.get("post") or {}))


def _formula_table(spec: dict, agents: List[str], atoms: List[str]):
    """Parse the spec's precondition formulas into ``assignment.holds`` tuples."""
    known = sorted(set(atoms) | set(spec_atoms(spec)))
    return {node: parse_formula(text, agents, known)
            for node, text in (spec.get("pre_formula") or {}).items() if text and text.strip()}


def action_problems(spec: dict, agents: List[str], atoms: List[str] | None = None) -> List[str]:
    """What stops the spec from being an action (empty list = it builds).

    ``atoms`` are the model's atoms, so a formula may mention them; the spec's
    own atoms are always known.
    """
    problems = []
    if not spec.get("events"):
        problems.append("the action has no events")
    for ev in spec.get("events", []):
        missing = [a for a in agents if not ev.get("nodes", {}).get(a)]
        if missing:
            problems.append(
                f"event '{ev.get('name')}' has no node for {', '.join(missing)} (UCF)"
            )
    for table in ("pre", "post"):
        for atom, cond in (spec.get(table) or {}).items():
            both = sorted(set(cond.get("true", [])) & set(cond.get("false", [])))
            if both:
                problems.append(f"{table}: atom '{atom}' is both true and false at {both}")
    if spec.get("update", "knowledge") not in UPDATE_KINDS:
        problems.append(f"unknown update kind: {spec.get('update')!r}")
    known = set(action_node_names(spec))
    for node in (spec.get("pre_formula") or {}):
        if node not in known:
            problems.append(f"pre_formula: node '{node}' does not exist")
    if problems:
        return problems
    try:
        build_action(spec, agents, atoms)
    except ValueError as exc:
        problems.append(str(exc))
    return problems


def preview_action(spec: dict, agents: List[str], tag: str = "") -> Path:
    """Draw the action AS DEFINED, complete or not: the Actions tab's live figure.

    An action is a chromatic complex like a model (thesis Def. 4.5): its
    events are the facets and its action nodes the vertices, so the model
    renderer draws it unchanged. Each node is labelled ``name(pre)[post]``,
    the notation of the thesis (p. 50), and each event by its name. Nothing
    is validated here, exactly like the model preview: an event missing some
    agent's node is drawn with the nodes it has, a node in no event is drawn
    loose, and the validity report next to the figure says what is missing.

    Raises:
        ValueError: when there is nothing to draw yet (no action node at all).
    """
    agents = list(agents)
    nodes: Dict[str, Node] = {}
    for ev in spec.get("events", []):
        for a, v in ev.get("nodes", {}).items():
            if v and a in agents:
                nodes.setdefault(v, Node(a, frozenset({v})))
    for a, names in (spec.get("isolated") or {}).items():
        for v in names:
            if v and a in agents:
                nodes.setdefault(v, Node(a, frozenset({v})))
    if not nodes:
        raise ValueError("add an event with at least one action node to see the action")
    pre, post = _conditions(spec.get("pre")), _conditions(spec.get("post"))

    def lits(table: Dict[str, int]) -> List[str]:
        return [("" if val else "¬") + atom for atom, val in sorted(table.items())]

    labels: Dict[Node, str] = {}
    for v, n in nodes.items():
        requires = lits(pre.get(v, {}))
        if (spec.get("pre_formula") or {}).get(v):
            requires.append(spec["pre_formula"][v])
        sets = lits(post.get(v, {}))
        sets += [f"{atom} := {phi}"
                 for atom, phi in sorted(((spec.get("post_formula") or {}).get(v) or {}).items())]
        labels[n] = (v + (f"({', '.join(requires)})" if requires else "")
                     + (f"[{', '.join(sets)}]" if sets else ""))
    event_of: Dict[frozenset, str] = {}
    belief: Dict[str, set] = {a: set() for a in agents}
    for i, ev in enumerate(spec.get("events", [])):
        members = frozenset(nodes[v] for a, v in ev.get("nodes", {}).items()
                            if v in nodes and nodes[v].agent == a)
        if not members or members in event_of:
            continue
        event_of[members] = ev.get("name") or f"e{i + 1}"
        for a in (ev["belief"] if "belief" in ev else agents):
            if a in belief:
                belief[a].add(members)
    model = SimplicialBeliefModel(agents, nodes.values(), event_of.keys(), belief,
                                  world_of_facet=event_of, validate=False, axiom_d=False,
                                  node_names=labels)
    return Path(show(model, _fname("gui_action", tag), "Action as defined",
                     output_dir=str(OUTPUTS), engine="auto" if _geometric_ok(model) else "dot"))


def build_action(spec: dict, agents: List[str], atoms: List[str] | None = None) -> SimplicialAction:
    """The :class:`SimplicialAction` a spec describes (the core validates it)."""
    events = {ev["name"]: {a: v for a, v in ev.get("nodes", {}).items() if v}
              for ev in spec.get("events", [])}
    pre_formula = _formula_table(spec, agents, list(atoms or []))
    return SimplicialAction.from_events(
        agents, events, pre=_conditions(spec.get("pre")), post=_conditions(spec.get("post")),
        isolated={a: list(v) for a, v in (spec.get("isolated") or {}).items() if v},
        pre_formula=pre_formula or None,
    )


def describe_action(spec: dict, agents: List[str], atoms: List[str] | None = None) -> str:
    """The core's text rendering of the action (events, nodes, pre/post)."""
    return build_action(spec, agents, atoms).describe()


def apply_action(state: dict, spec: dict, model_name: str = "model") -> dict:
    """Apply an action to a model state; returns the document of the result.

    The model may be of any kind: a relational one is first translated to its
    complex (general -> proper -> simplicial, as the direct editor's bootstrap
    does), because the product is defined on complexes. Inconsistent facets
    are dropped first (GitHub #21) and structural violations are refused, so
    the product runs on a valid model only.

    Returns:
        ``{"name", "state", "readonly": True, "origin"}`` -- what the GUI's
        ``new_doc`` takes. The state is a direct complex (see
        :func:`state_from_simplicial_model`).

    Raises:
        ValueError: an invalid model or action, or a core refusal, with the
            core's message.
        NotImplementedError: the chosen update kind is not available yet
            (see ``UPDATE_KINDS``: the pending products of the action layer).
    """
    update = spec.get("update", "knowledge")
    label, fn = UPDATE_KINDS.get(update, (update, None))
    if fn is None:
        raise NotImplementedError(
            f"the update “{label}” is not implemented yet; for now only "
            "the knowledge product (simplicial_actions.update_model)"
        )
    if state["kind"] != "simplicial":
        vertices, facets, vatoms = simplicial_state_from_editor(
            state["kind"], state["agents"], state["worlds"], state["per_agent"],
            state["atoms"], state["axiom_d"], not state.get("silent_defunct", False),
        )
        state = {**blank_state("simplicial"), "agents": list(state["agents"]),
                 "vertices": vertices, "facets": facets, "vatoms": vatoms,
                 "axiom_d": state["axiom_d"],
                 "complex_kind": "knowledge" if state["kind"] == "knowledge" else "kb"}
    agents = list(state["agents"])
    model, by_name, _ = build_simplicial(agents, state["vertices"], state["facets"],
                                         state["axiom_d"], validate=False,
                                         knowledge_only=_knowledge_only(state))
    assignment = simplicial_assignment(by_name, state["vatoms"])
    model, _ = _consistent_part(model, assignment, by_name)
    problems = model.violations()
    if problems:
        raise ValueError("the model is not valid:\n  - " + "\n  - ".join(problems))
    action = build_action(spec, agents, list(state.get("vatoms") or {}))
    mode = int(spec.get("mode", DEFAULT_MODE))
    if mode not in MODES:
        raise ValueError(f"unknown compatibility mode: {mode}")
    result = fn(model, assignment, action, mode)
    # The product names output nodes by (input, action) pairs and facets by
    # (world, event) pairs; state_from_simplicial_model turns both into the
    # editor's names, so the result reads "a0⋅a_oye", "(nS, anuncio)".
    out_model = result.model
    out_model.node_names = {
        n: "⋅".join(_pair_text(p) for p in sorted(map(_pair_parts, n.cls)))
        for n in out_model.nodes
    }
    out_model.world_of_facet = {
        F: "(" + ", ".join(map(str, w)) + ")" if isinstance(w, tuple) else w
        for F, w in out_model.world_of_facet.items()
    }
    doc = doc_from_model(f"{model_name} ⋅ {spec.get('name') or 'action'}", out_model,
                         result.assignment,
                         origin=f"action “{spec.get('name') or 'action'}” ({label}) "
                                f"on {model_name}")
    return doc


def _pair_parts(pair) -> Tuple[str, str]:
    """``Pair(input node, action node)`` -> the two nodes' own names, as text."""
    def one(node) -> str:
        cls = getattr(node, "cls", None)
        if cls is None:
            return str(node)
        if len(cls) == 1:
            member = next(iter(cls))
            return "⋅".join(_pair_text(_pair_parts(member))) if isinstance(member, tuple) \
                and len(member) == 2 and hasattr(member[0], "agent") else str(member)
        return "{" + ",".join(sorted(map(str, cls))) + "}"
    return one(pair[0]), one(pair[1])


def _pair_text(parts: Tuple[str, str]) -> str:
    return f"{parts[0]}⋅{parts[1]}"

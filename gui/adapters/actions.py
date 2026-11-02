"""Simplicial actions in the GUI: the action spec, its validation, its live
drawing, and applying it to a model with one of the thesis's products.
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
# vertex atoms; each event lists the agents whose S_{a,A} contains it, like
# a facet lists its S_a), applied to the active model, and its result opens
# as a read-only document that is drawn, evaluated, saved and compared like
# any other. The spec, JSON-friendly:
#
#   {"name": str,
#    "events":   [{"name": "e1", "nodes": {agent: action-node name},
#                  "belief": [agents whose S_{a,A} has the event]}],   (UCF; no
#                                                   "belief" key = every agent)
#    "isolated": {agent: [action-node names in no event]},
#    "pre":      {atom: {"true": [node names], "false": [node names]}},  (as vatoms)
#    "post":     {atom: {"true": [...], "false": [...]}},
#    "pre_formula": {node name: "K_a P"},        modal preconditions, formula syntax
#    "mode":     0 | 1 | 2,                      pairing test, thesis numbering (p. 51), see ACTION_MODES
#    "update":   "knowledge" | "belief" | ...}   which product to run, see UPDATE_KINDS
#
# THE PRODUCTS. ``simplicial_actions`` implements the three products of
# Sink's thesis ch. 4: the knowledge product M[A] (Def. 4.5), the belief
# product M[A]_B (Def. 4.6: each agent's S_a from its own S_a and S_{a,A})
# and the product with revision M[A]_BR (Def. 4.8: lost belief facets are
# imaged onto the nearest realisable ones), the latter with or without
# memory (thesis §3.5.2). UPDATE_KINDS maps the select's keys to them; the
# knowledge product ignores the events' "belief" lists.
# --------------------------------------------------------------------------- #
from functools import partial  # noqa: E402

from simplicial_actions import (  # noqa: E402
    DEFAULT_MODE,
    MODES,
    SimplicialAction,
    belief_update_model,
    describe_relational_action,
    revision_update_model,
    to_relational_action,
    update_model,
)

ACTION_MODES = {
    # The three definitions of N[A] on p. 51 of the thesis, numbered as there:
    # how an input vertex x and an action node y must agree on every atom to
    # form the output node (x, y). Mode 2 is the clause of Def. 4.5.
    0: "0 · what the vertex observes must be in the precondition (x ⇒ pre)",
    1: "1 · the precondition must be observed at the vertex (pre ⇒ x)",
    2: "2 · enough that they do not contradict each other (Def. 4.5, default)",
}

# update kind -> (label, function). The function takes (model, assignment,
# action, mode) and returns a simplicial_actions.UpdateModel. Each entry is
# one choice of the "update kind" select; removing an entry hides it.
UPDATE_KINDS = {
    "knowledge": ("knowledge · M[A] (Def. 4.5)", update_model),
    "belief": ("belief · M[A]_B (Def. 4.6)", belief_update_model),
    "revision": ("belief with revision · M[A]_BR (Def. 4.8)",
                 partial(revision_update_model, memory=False)),
    "revision_memory": ("belief with revision and memory · M[A]_BR on S[A] (§3.5.2)",
                        partial(revision_update_model, memory=True)),
}

# What each product does, for the editor's help line (plain English).
UPDATE_HELP = {
    "knowledge": "Each agent believes exactly what it knows in the result (S_a = S[A]). "
                 "The events' \"considered possible by\" lists are ignored.",
    "belief": "Each agent keeps believing a world after an event only if it believed the "
              "world and considers the event possible. A perspective may be left with no "
              "belief (collapse), which is reported.",
    "revision": "As belief, but a believed facet that becomes impossible is replaced by the "
                "nearest realisable facets (those sharing more perspectives), possibly "
                "combining perspectives of different worlds.",
    "revision_memory": "Same as revision, but only towards worlds of the product S[A]: no "
                       "revision towards worlds the action already ruled out.",
}


def blank_action(agents: List[str], name: str = "action") -> dict:
    """An empty action spec with every key the editor and :func:`build_action` expect."""
    return {"name": name, "events": [], "isolated": {a: [] for a in agents},
            "pre": {}, "post": {}, "mode": DEFAULT_MODE, "update": "knowledge"}


def event_belief(ev: dict, agents: List[str]) -> List[str]:
    """The agents whose ``S_{a,A}`` contains the event (no key = every agent)."""
    if "belief" not in ev:
        return list(agents)
    return [a for a in agents if a in ev["belief"]]


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
    "mensaje_privado": {
        "label": "a tells b whether C, privately (may be lost or not sent)",
        "spec": {
            "name": "a→b: C",
            # Thesis Fig. 52 with two agents: a sends the value of C, or says
            # nothing; a sent message may be lost. a cannot tell "received"
            # from "lost"; b, if it received, records what it heard and has
            # no doubt about it, and if it received nothing it thinks nothing
            # was sent: b's S_{b,A} leaves out the lost copies.
            "events": [
                {"name": "says C, arrives", "nodes": {"a": "a_says_C", "b": "b_hears_C"},
                 "belief": ["a", "b"]},
                {"name": "says C, lost", "nodes": {"a": "a_says_C", "b": "b_nothing"},
                 "belief": ["a"]},
                {"name": "says ¬C, arrives", "nodes": {"a": "a_says_noC", "b": "b_hears_noC"},
                 "belief": ["a", "b"]},
                {"name": "says ¬C, lost", "nodes": {"a": "a_says_noC", "b": "b_nothing"},
                 "belief": ["a"]},
                {"name": "says nothing", "nodes": {"a": "a_silent", "b": "b_nothing"},
                 "belief": ["a", "b"]},
            ],
            "isolated": {"a": [], "b": []},
            "pre": {"C": {"true": ["a_says_C"], "false": ["a_says_noC"]}},
            "post": {"C": {"true": ["b_hears_C"], "false": ["b_hears_noC"]}},
            "mode": DEFAULT_MODE, "update": "revision",
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


def preview_action(spec: dict, agents: List[str], tag: str = "") -> Path | str:
    """Draw the action AS DEFINED, complete or not: the Actions tab's live figure.

    An action is a chromatic complex like a model (thesis Def. 4.5): its
    events are the facets and its action nodes the vertices, so the model
    renderer draws it unchanged. Each node is labelled ``name(pre)[post]``,
    the notation of the thesis (p. 50), and each event by its name. Nothing
    is validated here, exactly like the model preview: an event missing some
    agent's node is drawn with the nodes it has, a node in no event is drawn
    loose, and the validity report next to the figure says what is missing.

    Returns:
        The figure's path, or a one-line message when there is nothing to
        draw yet (no action node at all). A message, not an exception: that
        is the normal state of a freshly created action, it is rendered in a
        worker thread, and a raise there makes a debugger stop on it as if
        something had gone wrong.
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
        return "add an event with at least one action node to see the action"
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
    # S_{a,A}: per agent, the events whose "belief" list names it
    belief = {a: [ev["name"] for ev in spec.get("events", []) if a in event_belief(ev, agents)]
              for a in agents}
    pre_formula = _formula_table(spec, agents, list(atoms or []))
    return SimplicialAction.from_events(
        agents, events, pre=_conditions(spec.get("pre")), post=_conditions(spec.get("post")),
        isolated={a: list(v) for a, v in (spec.get("isolated") or {}).items() if v},
        belief=belief, pre_formula=pre_formula or None,
    )


def describe_action(spec: dict, agents: List[str], atoms: List[str] | None = None) -> str:
    """The core's text rendering of the action (events, nodes, pre/post)."""
    return build_action(spec, agents, atoms).describe()


def describe_action_kripke(spec: dict, agents: List[str], atoms: List[str] | None = None) -> str:
    """The same action read as a Kripke action model (thesis Def. 4.4; docs/12 §4).

    One line per event: its precondition (the conjunction of its nodes'
    literals and formulas), its postcondition, and which events each agent
    cannot tell apart from it (those sharing the agent's node).
    """
    return describe_relational_action(to_relational_action(build_action(spec, agents, atoms)))


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

    The document's ``origin["notes"]`` list what the product reports:
    isolated output vertices (in no world), collapsed perspectives (in a
    world but with no believed facet, ``B_a ⊥``) and, for the revision
    products, each imaging. The GUI shows them under the result's banner.

    Raises:
        ValueError: an invalid model or action, an unknown update kind, or a
            core refusal, with the core's message.
    """
    update = spec.get("update", "knowledge")
    if update not in UPDATE_KINDS:
        raise ValueError(f"unknown update kind: {update!r}")
    label, fn = UPDATE_KINDS[update]
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
    doc["origin"]["notes"] = _update_notes(result, out_model)
    return doc


def _update_notes(result, out_model) -> List[str]:
    """Plain-language report of what the product left behind or repaired,
    written with the editor's vertex and facet names (the ones the figures show)."""
    names = out_model.node_names
    facet_names = out_model.world_of_facet
    notes: List[str] = []
    if result.isolated:
        notes.append("isolated vertices (in no world): "
                     + ", ".join(sorted(names[n] for n in result.isolated)))
    if result.collapsed:
        notes.append("perspectives with no belief (B_a ⊥, collapse): "
                     + ", ".join(sorted(names[n] for n in result.collapsed)))
    for rev in result.revisions:
        intended = "{" + ", ".join(sorted(_pair_text(_pair_parts(p)) for p in rev.intended)) + "}"
        if not rev.realised:
            notes.append(f"revision of {rev.agent}: facet {intended} was lost and no "
                         f"realisable facet keeps its perspective")
            continue
        to = ", ".join(str(facet_names.get(F, "?")) for F in rev.realised)
        tie = " (tie)" if len(rev.realised) > 1 else ""
        notes.append(f"revision of {rev.agent}: {intended} → {to}{tie}")
    return notes


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

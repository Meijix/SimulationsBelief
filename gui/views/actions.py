"""Simplicial actions: editor + "apply to the active model".

Actions are workspace-level; each result opens as a read-only document. The
editor mirrors the complex editor: an event is a facet of action nodes (one
per agent), pre/post conditions are vertex atoms on those nodes, and each
event lists the agents whose ``S_{a,A}`` contains it, as a facet lists its
``S_a``. The "update kind" select chooses the product (``adapters.UPDATE_KINDS``;
thesis ch. 4, docs/05 and docs/13); what the product reports shows on the
result's read-only banner.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from nicegui import ui

from adapters import (
    ACTION_EXAMPLES,
    ACTION_MODES,
    DEFAULT_MODE,
    UPDATE_HELP,
    UPDATE_KINDS,
    action_node_names,
    action_problems,
    agent_color_map,
    apply_action,
    describe_action,
    describe_action_kripke,
    event_belief,
    preview_action,
)
from theme import add_field, card, figure_img, panel_head, pre, take
from views.live_figure import LiveFigure

if TYPE_CHECKING:
    from views.page import Page


class ActionsView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.box = None
        self._fig_box = None        # the live drawing of the action
        self.live = LiveFigure(page, "action", size=32)

    def build(self) -> None:
        with card():
            panel_head("Simplicial actions")
            self.box = ui.column().classes("w-full gap-2")

    # ---- the list of actions ----------------------------------------------- #
    def add_action(self) -> None:
        self.page.ws.add_action(self.page.state["agents"])
        self.paint()

    def remove_action(self, index: int) -> None:
        self.page.ws.remove_action(index)
        self.paint()

    def select_action(self, index: int) -> None:
        self.page.ws.select_action(index)
        self.paint()

    def load_example(self, key: str) -> None:
        spec = copy.deepcopy(ACTION_EXAMPLES[key]["spec"])
        # The example names agents a/b; an action over other agents needs
        # its own nodes, so the isolated table is re-keyed to the model's.
        spec["isolated"] = {a: spec["isolated"].get(a, []) for a in self.page.state["agents"]}
        self.page.ws.add_action_spec(spec)
        self.paint()

    # ---- editing the selected spec ----------------------------------------- #
    def add_event(self, spec: dict) -> None:
        taken = {e["name"] for e in spec["events"]}
        n = len(spec["events"]) + 1
        while f"e{n}" in taken:
            n += 1
        spec["events"].append({"name": f"e{n}",
                               "nodes": {a: "" for a in self.page.state["agents"]},
                               "belief": list(self.page.state["agents"])})
        self.paint()

    def remove_event(self, spec: dict, index: int) -> None:
        spec["events"].pop(index)
        self.paint()

    def add_isolated(self, spec: dict, agent: str, widget) -> None:
        name = take(widget)
        if not name:
            return
        if name in action_node_names(spec):
            ui.notify(f"action node '{name}' already exists", type="warning")
            return
        spec.setdefault("isolated", {}).setdefault(agent, []).append(name)
        self.paint()

    def remove_isolated(self, spec: dict, agent: str, name: str) -> None:
        spec["isolated"][agent].remove(name)
        self.paint()

    def add_atom(self, spec: dict, widget) -> None:
        name = take(widget)
        if not name:
            return
        for table in ("pre", "post"):
            spec.setdefault(table, {}).setdefault(name, {"true": [], "false": []})
        self.paint()

    def remove_atom(self, spec: dict, name: str) -> None:
        for table in ("pre", "post"):
            spec.get(table, {}).pop(name, None)
        self.paint()

    def set_pre_formula(self, spec: dict, node: str, text: str) -> None:
        table = spec.setdefault("pre_formula", {})
        if text.strip():
            table[node] = text.strip()
        else:
            table.pop(node, None)
        self.refresh_preview(spec)

    def model_atoms(self) -> list:
        """The active model's atom names, so action formulas may mention them."""
        state = self.page.state
        return list(state.get("vatoms") or state.get("atoms") or {})

    # ---- apply ------------------------------------------------------------- #
    def apply(self) -> None:
        """Apply the selected action to the ACTIVE model; the result opens as a document."""
        page, ws = self.page, self.page.ws
        spec = ws.selected_action()
        if spec is None:
            ui.notify("Define (or load) an action first.", type="warning")
            return
        problems = action_problems(spec, page.state["agents"], self.model_atoms())
        if problems:
            ui.notify("The action is not complete: " + problems[0], type="warning")
            return
        try:
            doc_spec = apply_action(page.state, spec, model_name=page.current()["name"])
        except ValueError as exc:
            ui.notify(str(exc).splitlines()[0], type="negative", timeout=6000)
            return
        doc = ws.new_doc(doc_spec["name"], doc_spec["state"], readonly=True,
                         origin=doc_spec["origin"])
        notes = doc_spec["origin"].get("notes") or []
        # Notify BEFORE activating: activating repaints this card, and the
        # button whose click we are handling disappears with it (NiceGUI then
        # has no slot to attach the notification to).
        ui.notify(f"Result opened as “{doc['name']}” (read-only). "
                  + (f"{len(notes)} note(s) from the product under its banner. " if notes else "")
                  + "Compare it with its input model from the bar.", type="positive")
        page.activate(doc["id"])

    # ---- live drawing of the action, like the model preview ---------------- #
    def clear_cache(self) -> None:
        self.live.clear_cache()

    def refresh_preview(self, spec: dict) -> None:
        """Redraw the action as it stands (debounced, cached; see LiveFigure).
        The timer lives in the figure box, which outlives the widget that fired it."""
        if self._fig_box is None:
            return
        payload = [copy.deepcopy(spec), list(self.page.state["agents"])]
        self.live.schedule(self._fig_box, payload,
                           lambda p, key: preview_action(p[0], p[1], key), self._paint)

    def _paint(self, result) -> None:
        if self._fig_box is None:
            return
        self._fig_box.clear()
        with self._fig_box:
            ui.label("Action as defined").classes("eyebrow mt-1")
            if isinstance(result, str):
                ui.label(result).classes("text-xs muted")
            else:
                # Small in the editor column: a click opens it full screen.
                with ui.element("div").classes("w-full fig-frame cursor-pointer") \
                        .on("click", lambda r=result: self.page.results.open_lightbox(
                            r, "Action as defined")):
                    figure_img(result)

    # ---- paint ------------------------------------------------------------- #
    def paint(self) -> None:
        ws = self.page.ws
        agents = self.page.state["agents"]
        self.box.clear()
        with self.box:
            # The list: one chip per action, the selected one in the accent.
            with ui.row().classes("w-full items-center gap-2"):
                for i, a in enumerate(ws.actions):
                    sel = i == ws.action
                    ui.chip(a.get("name") or f"action {i + 1}", icon="bolt", removable=True,
                            color="var(--p-accent)" if sel else "var(--p-chip)",
                            text_color="var(--p-on-accent)" if sel else "var(--p-ink)",
                            on_click=lambda _, k=i: self.select_action(k),
                            on_value_change=lambda e, k=i: self.remove_action(k))
            with ui.row().classes("w-full no-wrap items-center gap-2"):
                ui.select({k: v["label"] for k, v in ACTION_EXAMPLES.items()}, value=None,
                          label="load example action",
                          on_change=lambda e: e.value and self.load_example(e.value)) \
                    .props("dense outlined options-dense").classes("grow")
                ui.button("New action", icon="add", on_click=lambda: self.add_action()) \
                    .props("flat dense", remove="color").classes("link-btn")
            spec = ws.selected_action()
            if spec is None:
                ui.label("An action is a complex of EVENTS: in each event, one action "
                         "node per agent; each node may require atoms "
                         "(precondition) and set them (postcondition). It is applied to "
                         "the active model and the result opens as a new model."
                         ).classes("text-xs muted")
                return
            if not agents:
                ui.label("Add agents to the active model: events carry one node "
                         "per agent.").classes("text-xs muted")
                return
            # ---- name, update kind, compatibility mode ---------------------- #
            ui.input("action name", value=spec.get("name", ""),
                     on_change=lambda e: spec.__setitem__("name", e.value)) \
                .props("dense outlined").classes("w-full") \
                .on("blur", lambda: self.paint())
            def set_update(value: str) -> None:
                spec["update"] = value
                self.paint()      # the help line below follows the choice

            ui.select({k: v[0] for k, v in UPDATE_KINDS.items()},
                      value=spec.get("update", "knowledge"), label="update kind",
                      on_change=lambda e: set_update(e.value)) \
                .props("dense outlined options-dense").classes("w-full")
            ui.label(UPDATE_HELP.get(spec.get("update", "knowledge"), "")) \
                .classes("text-xs muted")
            ui.select(ACTION_MODES, value=int(spec.get("mode", DEFAULT_MODE)),
                      label="vertex / action-node compatibility",
                      on_change=lambda e: spec.__setitem__("mode", int(e.value))) \
                .props("dense outlined options-dense").classes("w-full")
            # ---- events: one action node per agent (UCF, like facets) ------ #
            ui.label("Events (one action node per agent)").classes("eyebrow mt-1")
            colors = agent_color_map(agents)
            for i, ev in enumerate(spec["events"]):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.input("event", value=ev["name"],
                             on_change=lambda e, v=ev: (v.__setitem__("name", e.value),
                                                        self.refresh_preview(spec))) \
                        .props("dense outlined").classes("w-24")
                    for agent in agents:
                        ui.input(agent, value=ev["nodes"].get(agent, ""),
                                 on_change=lambda e, v=ev, a=agent:
                                     v["nodes"].__setitem__(a, (e.value or "").strip())) \
                            .props("dense outlined").classes("grow min-w-[64px]") \
                            .style(f"border-bottom:2px solid {colors[agent]}") \
                            .on("blur", lambda: self.paint())
                    ui.button(icon="delete", on_click=lambda _, k=i: self.remove_event(spec, k)) \
                        .props("flat dense color=grey")
                # Which agents consider the event possible (S_{a,A}), the way
                # a facet of the complex editor lists its S_a. The belief and
                # revision products read it; the knowledge product ignores it.
                with ui.row().classes("w-full items-center gap-2 no-wrap pl-2"):
                    ui.select(agents, multiple=True, value=event_belief(ev, agents),
                              label="considered possible by (S_{a,A})",
                              on_change=lambda e, v=ev: (v.__setitem__("belief", list(e.value)),
                                                         self.refresh_preview(spec))) \
                        .props("use-chips dense options-dense").classes("grow")
            ui.button("add event", icon="add", on_click=lambda: self.add_event(spec)) \
                .props("flat dense")
            # ---- isolated action nodes (in no event) ------------------------ #
            with ui.expansion("isolated action nodes (in no event)") \
                    .classes("w-full text-xs"):
                for agent in agents:
                    add_field(f"new node for {agent}",
                              lambda w, a=agent: self.add_isolated(spec, a, w))
                    with ui.row().classes("w-full gap-2"):
                        for name in spec.get("isolated", {}).get(agent, []):
                            ui.chip(name, removable=True, color=colors[agent],
                                    text_color="white",
                                    on_value_change=lambda e, a=agent, n=name:
                                        self.remove_isolated(spec, a, n))
            # ---- pre / post conditions: vertex atoms on action nodes -------- #
            ui.label("Preconditions and postconditions (atoms on action nodes)") \
                .classes("eyebrow mt-1")
            nodes = action_node_names(spec)
            add_field("atom (e.g. one of the model's)", lambda w: self.add_atom(spec, w))
            atoms = sorted(set(spec.get("pre", {})) | set(spec.get("post", {})))
            for atom in atoms:
                for table, label in (("pre", "requires"), ("post", "sets")):
                    cond = spec.setdefault(table, {}).setdefault(atom, {"true": [], "false": []})
                    with ui.row().classes("w-full no-wrap items-center gap-2"):
                        ui.label(f"{atom} · {label}").classes("font-mono text-xs w-20")
                        ui.select(nodes, multiple=True, value=cond["true"], label="true",
                                  on_change=lambda e, c=cond: (c.__setitem__("true", list(e.value)),
                                                               self.refresh_preview(spec))) \
                            .props("use-chips dense").classes("grow")
                        ui.select(nodes, multiple=True, value=cond["false"], label="false",
                                  on_change=lambda e, c=cond: (c.__setitem__("false", list(e.value)),
                                                               self.refresh_preview(spec))) \
                            .props("use-chips dense").classes("grow")
                        if table == "pre":
                            ui.button(icon="delete",
                                      on_click=lambda _, n=atom: self.remove_atom(spec, n)) \
                                .props("flat dense color=grey")
            # ---- modal preconditions: one formula per action node ----------- #
            # Same syntax as the formula evaluator (K_a, B_a, ~, &, |, ->);
            # required at the input world (see simplicial_actions' docstring).
            with ui.expansion("modal preconditions (optional): a formula per action node") \
                    .classes("w-full text-xs"):
                ui.label("Evaluator syntax: K_a P, B_b ~P, P & Q, P -> Q. The event happens "
                         "at an input world only if the formula holds there.") \
                    .classes("text-xs muted")
                for node in nodes:
                    with ui.row().classes("w-full no-wrap items-center gap-2"):
                        ui.label(node).classes("font-mono text-xs w-20")
                        ui.input("precondition", value=(spec.get("pre_formula") or {}).get(node, ""),
                                 on_change=lambda e, n=node: self.set_pre_formula(spec, n, e.value or "")) \
                            .props("dense outlined").classes("grow") \
                            .on("blur", lambda: self.paint())
            # ---- status + apply --------------------------------------------- #
            problems = action_problems(spec, agents, self.model_atoms())
            if problems:
                ui.label("Missing: " + "; ".join(problems)).classes("text-xs") \
                    .style("color:var(--p-warn)")
            else:
                pre(describe_action(spec, agents, self.model_atoms()))
                # The same action as a Kripke action model (thesis Def. 4.4,
                # docs/12 §4): events, their preconditions as one formula
                # each, and who confuses which events.
                with ui.expansion("as a Kripke action model").classes("w-full text-xs"):
                    try:
                        text = describe_action_kripke(spec, agents, self.model_atoms())
                    except ValueError as exc:
                        text = str(exc)
                    pre(text)
            # The action drawn as it stands, updated after every edit.
            self._fig_box = ui.column().classes("w-full gap-1")
            self.refresh_preview(spec)
            with ui.row().classes("w-full items-center gap-2"):
                ui.button("Apply to the active model", icon="play_arrow",
                          on_click=lambda: self.apply()) \
                    .props("unelevated dense color=primary text-color=dark")
                ui.label("The result opens as a read-only model; "
                         "compare it with its input.").classes("text-xs muted")

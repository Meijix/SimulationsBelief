"""Simplicial actions: editor + "apply to the active model" (GitHub #6/#13/#18).

Workspace-level card: actions are edited here and APPLIED to the active
model; each result opens as a read-only document (drawn, evaluated, saved
and compared like any other). The editor mirrors the complex editor on
purpose: an event IS a facet of action nodes (one per agent), pre/post ARE
vertex atoms on those nodes, so whoever can declare a complex can declare an
action. The interface is complete; the products themselves are the action
layer's: today only the knowledge product exists
(``simplicial_actions.update_model``, spec-b); the belief / memory / revision
ones are offered but PENDING (Taiba, #6/#15) -- see ``adapters.UPDATE_KINDS``:
the "update kind" select lists them, and ``apply_action`` refuses
them with a message until their functions exist.
"""

from __future__ import annotations

import copy
import hashlib
import html
import json
import logging
from typing import TYPE_CHECKING

from nicegui import run as io, ui

from adapters import (
    ACTION_EXAMPLES,
    ACTION_MODES,
    DEFAULT_MODE,
    UPDATE_KINDS,
    action_node_names,
    action_problems,
    agent_color_map,
    apply_action,
    describe_action,
    describe_action_kripke,
    preview_action,
)
from theme import CARD, FLAT, POSTER, card_title, figure_img, take

if TYPE_CHECKING:
    from views.page import Page


class ActionsView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.box = None
        self._fig_box = None        # the live drawing of the action
        self._seq = 0
        self._cache: dict = {}      # spec hash -> figure path | message

    def build(self) -> None:
        with ui.card().classes(CARD).props(FLAT):
            card_title("Simplicial actions")
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
                               "nodes": {a: "" for a in self.page.state["agents"]}})
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
            doc_spec = apply_action(page.live_state(), spec, model_name=page.current()["name"])
        except NotImplementedError as exc:
            # PENDING product (Taiba): the interface is ready, the function is not.
            ui.notify(str(exc), type="warning", timeout=6000)
            return
        except ValueError as exc:
            ui.notify(str(exc).splitlines()[0], type="negative", timeout=6000)
            return
        ws.store_active(page.live_state())
        doc = ws.new_doc(doc_spec["name"], doc_spec["state"], readonly=True,
                         origin=doc_spec["origin"])
        # Notify BEFORE activating: activating repaints this card, and the
        # button whose click we are handling disappears with it (NiceGUI then
        # has no slot to attach the notification to).
        ui.notify(f"Result opened as “{doc['name']}” (read-only). "
                  "Compare it with its input model from the bar.", type="positive")
        page.activate(doc["id"])

    # ---- live drawing of the action, like the model preview ---------------- #
    def _schedule_preview(self, spec: dict, agents: list) -> None:
        """Debounced, off the event loop, cached by the spec's content."""
        self._seq += 1
        seq = self._seq
        # The timer lives in the figure box, which is cleared but never
        # deleted between renders, so it survives the widget that fired it.
        with self._fig_box:
            ui.timer(0.25, lambda: self._render_preview(seq, spec, agents), once=True)

    def refresh_preview(self, spec: dict) -> None:
        """Redraw after an edit that keeps the card as it is (a select, a name)."""
        if self._fig_box is not None:
            self._schedule_preview(copy.deepcopy(spec), list(self.page.state["agents"]))

    async def _render_preview(self, seq: int, spec: dict, agents: list) -> None:
        if seq != self._seq or self._fig_box is None:
            return
        key = hashlib.sha1(json.dumps([spec, agents], sort_keys=True,
                                      default=str).encode()).hexdigest()[:12]
        if key not in self._cache:
            try:
                result = await io.io_bound(preview_action, spec, agents, key)
            except ValueError as exc:
                result = str(exc)
            except Exception as exc:  # noqa: BLE001 -- the live figure must never take the card down
                result = f"Could not draw the action: {exc}"
                logging.getLogger("nicegui").exception("action preview failed")
            if result is None:            # io_bound: cancelled or shutting down
                return
            if len(self._cache) >= 32:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = result
        if seq != self._seq:
            return
        result = self._cache[key]
        self._fig_box.clear()
        with self._fig_box:
            ui.label("Action as defined").classes("eyebrow mt-1")
            if isinstance(result, str):
                ui.label(result).classes("text-xs text-grey-5")
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
            # The list: one chip per action, the selected one in lime.
            with ui.row().classes("w-full items-center gap-2"):
                for i, a in enumerate(ws.actions):
                    sel = i == ws.action
                    ui.chip(a.get("name") or f"action {i + 1}", icon="bolt", removable=True,
                            color=POSTER["lime"] if sel else "rgba(255,255,255,.14)",
                            text_color=POSTER["surface"] if sel else "white",
                            on_click=lambda _, k=i: self.select_action(k),
                            on_value_change=lambda e, k=i: self.remove_action(k))
                ui.button(icon="add", on_click=lambda: self.add_action()) \
                    .props("round dense flat").tooltip("New action")
            ui.select({k: v["label"] for k, v in ACTION_EXAMPLES.items()}, value=None,
                      label="load example action",
                      on_change=lambda e: e.value and self.load_example(e.value)) \
                .props("dense outlined options-dense").classes("w-full")
            spec = ws.selected_action()
            if spec is None:
                ui.label("An action is a complex of EVENTS: in each event, one action "
                         "node per agent; each node may require atoms "
                         "(precondition) and set them (postcondition). It is applied to "
                         "the active model and the result opens as a new model."
                         ).classes("text-xs text-grey-5")
                return
            if not agents:
                ui.label("Add agents to the active model: events carry one node "
                         "per agent.").classes("text-xs text-grey-5")
                return
            # ---- name, update kind, compatibility mode ---------------------- #
            ui.input("action name", value=spec.get("name", ""),
                     on_change=lambda e: spec.__setitem__("name", e.value)) \
                .props("dense outlined").classes("w-full") \
                .on("blur", lambda: self.paint())
            def set_update(value: str) -> None:
                spec["update"] = value
                self.paint()      # the "pending" note below follows the choice

            ui.select({k: v[0] for k, v in UPDATE_KINDS.items()},
                      value=spec.get("update", "knowledge"), label="update kind",
                      on_change=lambda e: set_update(e.value)) \
                .props("dense outlined options-dense").classes("w-full")
            if UPDATE_KINDS[spec.get("update", "knowledge")][1] is None:
                ui.label("Pending: this product is not implemented in the core yet "
                         "(Taiba's action layer). The action can be defined and "
                         "saved; applying it will warn.") \
                    .classes("text-xs").style(f"color:{POSTER['yellow']}")
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
            ui.button("add event", icon="add", on_click=lambda: self.add_event(spec)) \
                .props("flat dense")
            # ---- isolated action nodes (in no event) ------------------------ #
            with ui.expansion("isolated action nodes (in no event)") \
                    .classes("w-full text-xs"):
                for agent in agents:
                    with ui.row().classes("w-full no-wrap items-center gap-2"):
                        box = ui.input(f"nuevo nodo de {agent}").props("dense outlined") \
                            .classes("grow")
                        ui.button(icon="add", on_click=lambda _, a=agent, w=box:
                                  self.add_isolated(spec, a, w)).props("round dense")
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
            with ui.row().classes("w-full no-wrap items-center gap-2"):
                atom_box = ui.input("atom (e.g. one of the model's)").props("dense outlined") \
                    .classes("grow")
                ui.button(icon="add", on_click=lambda: self.add_atom(spec, atom_box)) \
                    .props("round dense")
                atom_box.on("keydown.enter", lambda: self.add_atom(spec, atom_box))
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
                    .classes("text-xs text-grey-5")
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
                    .style(f"color:{POSTER['yellow']}")
            else:
                ui.html("<pre style='white-space:pre-wrap' class='text-xs'>"
                        f"{html.escape(describe_action(spec, agents, self.model_atoms()))}</pre>")
                # The same action as a Kripke action model (Def. 4.4): events,
                # their preconditions as one formula each, and who confuses
                # which events -- the other side of the equivalence (docs/12).
                with ui.expansion("as a Kripke action model").classes("w-full text-xs"):
                    try:
                        text = describe_action_kripke(spec, agents, self.model_atoms())
                    except ValueError as exc:
                        text = str(exc)
                    ui.html("<pre style='white-space:pre-wrap' class='text-xs'>"
                            f"{html.escape(text)}</pre>")
            # The action drawn as it stands, updated after every edit.
            self._fig_box = ui.column().classes("w-full gap-1")
            self._schedule_preview(copy.deepcopy(spec), list(agents))
            with ui.row().classes("w-full items-center gap-2"):
                ui.button("Apply to the active model", icon="play_arrow",
                          on_click=lambda: self.apply()) \
                    .props("unelevated dense color=primary text-color=dark")
                ui.label("The result opens as a read-only model; "
                         "compare it with its input.").classes("text-xs text-grey-5")

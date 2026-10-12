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
the "tipo de actualización" select lists them, and ``apply_action`` refuses
them with a message until their functions exist.
"""

from __future__ import annotations

import copy
import html
from typing import TYPE_CHECKING

from nicegui import ui

from adapters import (
    ACTION_EXAMPLES,
    ACTION_MODES,
    UPDATE_KINDS,
    action_node_names,
    action_problems,
    agent_color_map,
    apply_action,
    describe_action,
)
from theme import CARD, FLAT, POSTER, card_title, take

if TYPE_CHECKING:
    from views.page import Page


class ActionsView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.box = None

    def build(self) -> None:
        with ui.card().classes(CARD).props(FLAT):
            card_title("Acciones simpliciales")
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
            ui.notify(f"el nodo de acción '{name}' ya existe", type="warning")
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

    # ---- apply ------------------------------------------------------------- #
    def apply(self) -> None:
        """Apply the selected action to the ACTIVE model; the result opens as a document."""
        page, ws = self.page, self.page.ws
        spec = ws.selected_action()
        if spec is None:
            ui.notify("Primero define (o carga) una acción.", type="warning")
            return
        problems = action_problems(spec, page.state["agents"])
        if problems:
            ui.notify("La acción no está completa: " + problems[0], type="warning")
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
        page.activate(doc["id"])
        ui.notify(f"Resultado abierto como «{doc['name']}» (sólo lectura). "
                  "Compáralo con su modelo de entrada desde la barra.", type="positive")

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
                    ui.chip(a.get("name") or f"acción {i + 1}", icon="bolt", removable=True,
                            color=POSTER["lime"] if sel else "rgba(255,255,255,.14)",
                            text_color=POSTER["surface"] if sel else "white",
                            on_click=lambda _, k=i: self.select_action(k),
                            on_value_change=lambda e, k=i: self.remove_action(k))
                ui.button(icon="add", on_click=lambda: self.add_action()) \
                    .props("round dense flat").tooltip("Acción nueva")
            ui.select({k: v["label"] for k, v in ACTION_EXAMPLES.items()}, value=None,
                      label="cargar acción de ejemplo",
                      on_change=lambda e: e.value and self.load_example(e.value)) \
                .props("dense outlined options-dense").classes("w-full")
            spec = ws.selected_action()
            if spec is None:
                ui.label("Una acción es un complejo de EVENTOS: en cada evento, un nodo "
                         "de acción por agente; cada nodo puede exigir átomos "
                         "(precondición) y fijarlos (postcondición). Se aplica al "
                         "modelo activo y el resultado se abre como modelo nuevo."
                         ).classes("text-xs text-grey-5")
                return
            if not agents:
                ui.label("Agrega agentes al modelo activo: los eventos llevan un nodo "
                         "por agente.").classes("text-xs text-grey-5")
                return
            # ---- name, update kind, compatibility mode ---------------------- #
            ui.input("nombre de la acción", value=spec.get("name", ""),
                     on_change=lambda e: spec.__setitem__("name", e.value)) \
                .props("dense outlined").classes("w-full") \
                .on("blur", lambda: self.paint())
            ui.select({k: v[0] for k, v in UPDATE_KINDS.items()},
                      value=spec.get("update", "knowledge"), label="tipo de actualización",
                      on_change=lambda e: spec.__setitem__("update", e.value)) \
                .props("dense outlined options-dense").classes("w-full")
            if UPDATE_KINDS[spec.get("update", "knowledge")][1] is None:
                ui.label("Pendiente: este producto aún no está implementado en el "
                         "núcleo (capa de acciones de Taiba). La acción se puede "
                         "definir y guardar; aplicarla avisará.") \
                    .classes("text-xs").style(f"color:{POSTER['yellow']}")
            ui.select(ACTION_MODES, value=int(spec.get("mode", 3)),
                      label="compatibilidad vértice / nodo de acción",
                      on_change=lambda e: spec.__setitem__("mode", int(e.value))) \
                .props("dense outlined options-dense").classes("w-full")
            # ---- events: one action node per agent (UCF, like facets) ------ #
            ui.label("Eventos (un nodo de acción por agente)").classes("eyebrow mt-1")
            colors = agent_color_map(agents)
            for i, ev in enumerate(spec["events"]):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.input("evento", value=ev["name"],
                             on_change=lambda e, v=ev: v.__setitem__("name", e.value)) \
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
            ui.button("añadir evento", icon="add", on_click=lambda: self.add_event(spec)) \
                .props("flat dense")
            # ---- isolated action nodes (in no event) ------------------------ #
            with ui.expansion("nodos de acción aislados (en ningún evento)") \
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
            ui.label("Precondiciones y postcondiciones (átomos sobre nodos de acción)") \
                .classes("eyebrow mt-1")
            nodes = action_node_names(spec)
            with ui.row().classes("w-full no-wrap items-center gap-2"):
                atom_box = ui.input("átomo (p. ej. uno del modelo)").props("dense outlined") \
                    .classes("grow")
                ui.button(icon="add", on_click=lambda: self.add_atom(spec, atom_box)) \
                    .props("round dense")
                atom_box.on("keydown.enter", lambda: self.add_atom(spec, atom_box))
            atoms = sorted(set(spec.get("pre", {})) | set(spec.get("post", {})))
            for atom in atoms:
                for table, label in (("pre", "exige"), ("post", "fija")):
                    cond = spec.setdefault(table, {}).setdefault(atom, {"true": [], "false": []})
                    with ui.row().classes("w-full no-wrap items-center gap-2"):
                        ui.label(f"{atom} · {label}").classes("font-mono text-xs w-20")
                        ui.select(nodes, multiple=True, value=cond["true"], label="verdadero",
                                  on_change=lambda e, c=cond: c.__setitem__("true", list(e.value))) \
                            .props("use-chips dense").classes("grow")
                        ui.select(nodes, multiple=True, value=cond["false"], label="falso",
                                  on_change=lambda e, c=cond: c.__setitem__("false", list(e.value))) \
                            .props("use-chips dense").classes("grow")
                        if table == "pre":
                            ui.button(icon="delete",
                                      on_click=lambda _, n=atom: self.remove_atom(spec, n)) \
                                .props("flat dense color=grey")
            # ---- status + apply --------------------------------------------- #
            problems = action_problems(spec, agents)
            if problems:
                ui.label("Falta: " + "; ".join(problems)).classes("text-xs") \
                    .style(f"color:{POSTER['yellow']}")
            else:
                ui.html("<pre style='white-space:pre-wrap' class='text-xs'>"
                        f"{html.escape(describe_action(spec, agents))}</pre>")
            with ui.row().classes("w-full items-center gap-2"):
                ui.button("Aplicar al modelo activo", icon="play_arrow",
                          on_click=lambda: self.apply()) \
                    .props("unelevated dense color=primary text-color=dark")
                ui.label("El resultado se abre como modelo de sólo lectura; "
                         "compáralo con su entrada.").classes("text-xs text-grey-5")

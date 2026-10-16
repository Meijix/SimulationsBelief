"""Editor of the direct simplicial complex (model kind "simplicial").

Two cards painted into the editor's ``editor_box``: the vertices of each
agent (chips, like agents and worlds) and the facets, where each row picks
ONE vertex per agent -- so the UCF condition is the very shape of the form
-- and which agents have it in their belief subcomplex. Same strategy as
the relational editor: every structural change repaints from ``page.state``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from adapters import agent_color_map, maximal_facets
from theme import CARD, FLAT, card_title, take

if TYPE_CHECKING:
    from views.page import Page


class SimplicialEditorView:
    def __init__(self, page: Page) -> None:
        self.page = page

    # ---- vertices ---------------------------------------------------------- #
    def add_vertex(self, agent: str, widget) -> None:
        state = self.page.state
        name = take(widget)
        if not name:
            return
        if any(name in vs for vs in state["vertices"].values()):
            ui.notify(f"vertex '{name}' already exists", type="warning")
            return
        state["vertices"].setdefault(agent, []).append(name)
        self.page.repaint_all()

    def remove_vertex(self, agent: str, name: str) -> None:
        # Pruned from facets and atoms: a facet that used it is left without
        # a vertex of that agent and validation reports it as a UCF failure.
        state = self.page.state
        state["vertices"][agent].remove(name)
        for facet in state["facets"]:
            if facet["nodes"].get(agent) == name:
                facet["nodes"][agent] = None
        for spec in state["vatoms"].values():
            spec["true"] = [v for v in spec["true"] if v != name]
            spec["false"] = [v for v in spec["false"] if v != name]
        self.page.repaint_all()

    # ---- facets ------------------------------------------------------------ #
    def add_facet(self) -> None:
        state = self.page.state
        taken = {f["name"] for f in state["facets"]}
        n = len(state["facets"]) + 1
        while f"F{n}" in taken:
            n += 1
        state["facets"].append({
            "name": f"F{n}",
            # Starts with the first vertex of each agent (or none) and in the
            # belief subcomplex of everyone: the most common case.
            "nodes": {a: (state["vertices"].get(a) or [None])[0]
                      for a in state["agents"]},
            "belief": list(state["agents"]),
        })
        self.page.repaint_all()

    def remove_facet(self, index: int) -> None:
        self.page.state["facets"].pop(index)
        self.page.repaint_all()

    def fill_maximal(self) -> None:
        """Add every consistent UCF facet the vertices can form (issue #21)."""
        state = self.page.state
        try:
            state["facets"], added = maximal_facets(
                state["agents"], state["vertices"], state["vatoms"], state["facets"],
            )
        except ValueError as exc:
            ui.notify(str(exc).splitlines()[0], type="warning")
            return
        ui.notify(f"{added} facet(s) added" if added
                  else "every consistent facet was already there", type="info")
        if added:
            self.page.repaint_all()

    def undo_maximal(self) -> None:
        """Drop the facets "completar al complejo maximal" added, keeping the hand-made ones."""
        state = self.page.state
        before = len(state["facets"])
        state["facets"] = [f for f in state["facets"] if not f.get("auto")]
        ui.notify(f"{before - len(state['facets'])} added facet(s) removed", type="info")
        self.page.repaint_all()

    def set_facet(self, facet: dict, key: str, value, agent: str | None = None) -> None:
        if agent is None:
            facet[key] = value
        else:
            facet[key][agent] = value
        # An added facet the user edits becomes a hand-made one: "deshacer"
        # must not take away something they shaped on purpose.
        if facet.pop("auto", None):
            self.page.editor.paint()
        self.page.preview.update()

    def set_complex_kind(self, value: str) -> None:
        """Knowledge complex (S_a = S) or knowledge + belief (S_a declared).

        Only these two: in a complex the knowledge IS the gluing of the facets
        along shared vertices, so there is no belief-only variant (unlike the
        relational editor, where a lone KD45 relation is a model on its own).
        The per-facet belief lists are kept while in knowledge mode, so the
        switch is reversible.
        """
        state = self.page.state
        if value == state.get("complex_kind", "kb"):
            return
        state["complex_kind"] = value
        self.page.reset_results()
        self.page.repaint_all()

    # ---- paint ------------------------------------------------------------- #
    def paint(self, container) -> None:
        state = self.page.state
        colors = agent_color_map(state["agents"])
        container.clear()
        with container:
            with ui.card().classes(CARD).props(FLAT):
                card_title("Vertices (each agent's perspectives)")
                for agent in state["agents"]:
                    names = state["vertices"].setdefault(agent, [])
                    with ui.row().classes("w-full no-wrap items-center gap-2"):
                        ui.element("span").style(
                            f"width:10px;height:10px;border-radius:9999px;"
                            f"flex:none;background:{colors[agent]}"
                        )
                        v_in = ui.input(f"new vertex for {agent}") \
                            .props("dense outlined").classes("grow")
                        ui.button(icon="add",
                                  on_click=lambda _, a=agent, w=v_in: self.add_vertex(a, w)) \
                            .props("round dense")
                        v_in.on("keydown.enter",
                                lambda _, a=agent, w=v_in: self.add_vertex(a, w))
                    with ui.row().classes("w-full gap-2"):
                        for v in names:
                            ui.chip(v, removable=True, color=colors[agent],
                                    text_color="white",
                                    on_value_change=lambda e, a=agent, n=v:
                                        self.remove_vertex(a, n))
                if not state["agents"]:
                    ui.label("Add the agents first.").classes("text-grey-5")
            with ui.card().classes(CARD).props(FLAT):
                card_title("Facets (one vertex per agent)")
                # Which of the two readings of the complex is being declared.
                # Mirrors the model-kind selector of the relational editor,
                # minus "belief only" (see set_complex_kind for why).
                knowledge_only = state.get("complex_kind", "kb") == "knowledge"
                ui.toggle(
                    {"knowledge": "knowledge complex",
                     "kb": "knowledge and belief"},
                    value="knowledge" if knowledge_only else "kb",
                    on_change=lambda e: self.set_complex_kind(e.value),
                ).props("dense no-caps unelevated toggle-color=primary")
                ui.label(
                    "S_a = S: every agent believes exactly what it knows, so "
                    "B_a coincides with K_a. There is no “belief only”: the vertices "
                    "that glue the facets already are the knowledge."
                    if knowledge_only else
                    "Each facet also says which agents believe it possible "
                    "(which subcomplexes S_a it is in)."
                ).classes("text-xs text-grey-5")
                for i, facet in enumerate(state["facets"]):
                    with ui.column().classes("w-full gap-0 pb-2") \
                            .style("border-bottom:1px solid var(--p-line)"):
                        if facet.get("auto"):
                            # Added by "completar al complejo maximal", not typed:
                            # said on the row so "quitar las añadidas" is predictable.
                            ui.label("added when completing the maximal complex") \
                                .classes("text-xs").style("color:var(--p-muted)")
                        with ui.row().classes("w-full items-center gap-2"):
                            # The name is stored on typing and the preview is
                            # redrawn on leaving the field, not on every key.
                            ui.input("name", value=facet["name"],
                                     on_change=lambda e, f=facet:
                                         f.__setitem__("name", e.value)) \
                                .props("dense outlined").classes("w-24") \
                                .on("blur", lambda: self.page.preview.update())
                            for agent in state["agents"]:
                                ui.select(
                                    state["vertices"].get(agent, []),
                                    value=facet["nodes"].get(agent), label=agent,
                                    on_change=lambda e, f=facet, a=agent:
                                        self.set_facet(f, "nodes", e.value, a),
                                ).props("dense options-dense") \
                                    .classes("grow min-w-[64px]")
                            ui.button(icon="delete",
                                      on_click=lambda _, k=i: self.remove_facet(k)) \
                                .props("flat dense color=grey")
                        if not knowledge_only:
                            ui.select(
                                state["agents"], multiple=True, value=facet["belief"],
                                label="believed possible by (in S_a of)",
                                on_change=lambda e, f=facet: self.set_facet(f, "belief", e.value),
                            ).props("use-chips dense").classes("w-full")
                with ui.row().classes("w-full items-center gap-2"):
                    ui.button("add facet", icon="add", on_click=lambda: self.add_facet()) \
                        .props("flat dense")
                    # The thesis's own construction (p. 19): every consistent
                    # UCF facet the vertices can form. Offered as an action,
                    # not applied silently, because a declared complex is
                    # often meant to be a proper subcomplex of M(N, V, L).
                    ui.button("complete to the maximal complex", icon="auto_awesome",
                              on_click=lambda: self.fill_maximal()) \
                        .props("flat dense")
                    if any(f.get("auto") for f in state["facets"]):
                        # The way back: only the facets typed by hand remain.
                        ui.button("remove the added facets", icon="undo",
                                  on_click=lambda: self.undo_maximal()) \
                            .props("flat dense").tooltip(
                            "Keeps only the hand-made facets (an added facet "
                            "you have edited counts as hand-made).")
                ui.markdown(
                    "Each facet carries exactly one vertex of each agent "
                    "(UCF). A facet whose vertices contradict each other on an atom "
                    "does not exist in the model: it is removed and reported. “Complete "
                    "to the maximal complex” adds every missing consistent facet "
                    "(M(N, V, L)) and “remove the added facets” takes them away "
                    "again. Under Axiom D, every vertex must be in some facet "
                    "of its agent's belief subcomplex."
                ).classes("text-xs text-grey-5")

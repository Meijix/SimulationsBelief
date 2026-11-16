"""Identifiers, switches and the relational editor (the "Model" tab).

The identifier card holds the document name, the model kind, the agent and
world chips and the switches; below it, ``editor_box`` is painted with one
section per agent (knowledge classes and believed worlds) or, for a direct
complex, by :class:`views.simplicial_editor.SimplicialEditorView`. Any
structural change repaints the whole editor from ``page.state`` and
schedules the preview: at this scale that is instantaneous.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from adapters import KINDS, agent_color_map, simplicial_state_from_editor
from theme import add_field, card, panel_head, swatch, take

# Label sizes offered for the complex figures: the factor is what
# ``visualization.show(font_scale=...)`` receives, the text is what the user
# reads. 1.0 is the size of the paper figures.
LABEL_SIZES = {0.8: "small (0.8)", 1.0: "normal (1.0, paper)", 1.25: "large (1.25)",
               1.5: "extra large (1.5)", 2.0: "huge (2.0)"}


def _nearest_label_size(value) -> float:
    """The offered size closest to a stored factor (a hand-edited workspace
    may carry any number; the select can only show its own options)."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 1.0
    return min(LABEL_SIZES, key=lambda k: abs(k - value))

if TYPE_CHECKING:
    from views.page import Page


class EditorView:
    def __init__(self, page: Page) -> None:
        self.page = page
        # Widgets other regions reach: set in build().
        self.ident_card = None
        self.editor_box = None
        self.name_in = self.kind_in = None
        self.agent_input = self.agent_chips = None
        self.worlds_box = self.world_input = self.world_chips = None
        self.axiom_d_in = self.silent_defunct_in = None
        self.explicit_in = self.hasse_full_in = self.make_3d_in = self.font_scale_in = None

    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #
    def build(self) -> None:
        page = self.page
        # ---- Identifiers ------------------------------------------------- #
        with card() as self.ident_card:
            panel_head("Agents and worlds")
            # Document name: the one shown in the models bar and in the
            # comparison panels.
            self.name_in = ui.input("model name") \
                .props("dense outlined").classes("w-full")
            self.name_in.on("blur", lambda: self.rename_current())
            self.name_in.on("keydown.enter", lambda: self.rename_current())
            # The core's model kinds. Changing it repaints the editor (the
            # rows change meaning), adjusts which switches apply and redraws
            # the preview.
            self.kind_in = ui.select(
                KINDS, value="kb", label="model kind",
                on_change=lambda e: self.set_kind(e.value),
            ).props("dense outlined options-dense").classes("w-full")
            self.agent_input = add_field("new agent", lambda _: self.add_agent())
            self.agent_chips = ui.row().classes("w-full gap-2")

            # Worlds go in their own container: a direct complex has no
            # worlds (it has facets, declared in their own card), so for that
            # kind the whole block is hidden.
            with ui.column().classes("w-full gap-2 mt-2") as self.worlds_box:
                self.world_input = add_field("new world", lambda _: self.add_world())
                self.world_chips = ui.row().classes("w-full gap-2")

            # The switches write straight into ``page.state``; while a
            # document is being loaded (``ws.loading``) the assignment of a
            # widget's value is a no-op write of the same value.
            # Axiom D: the core's KD45/K45 switch; off, defunct belief
            # (Q_a(w) = ∅) is legal.
            self.axiom_d_in = ui.switch(
                "Axiom D (KD45; off = K45)", value=True,
                on_change=lambda e: self.axiom_d_changed(e.value),
            ).tooltip(
                "KD45 requires every agent to believe something in every world (seriality). "
                "Off (K45), an empty belief is legal: there the agent believes "
                "everything, ⊥ included.")
            # Silence about belief means "believe what you know" (Q = R) in
            # both logics; defunct belief is this explicit opt-in (K45 only).
            self.silent_defunct_in = ui.switch(
                "Empty belief when nothing is marked (Q = ∅)", value=False,
                on_change=lambda e: self.switch_changed("silent_defunct", e.value, preview=True),
            ).tooltip("Only with K45. Off, a class with no belief marked "
                      "believes what it knows (Q = R).")

            # Drawing options, collapsed: they change figures, not the model.
            # Each one redraws what it affects: the preview, and the results
            # if there was a run.
            with ui.expansion("Drawing options", icon="brush") \
                    .classes("w-full text-sm").props("dense"):
                # Loops and the second arrow of symmetric pairs are implied by
                # the logic and omitted; on, they are drawn (what the closures added).
                self.explicit_in = ui.switch(
                    "Show implicit edges (loops and symmetry)",
                    value=False,
                    on_change=lambda e: self.switch_changed("explicit", e.value, preview=True, rerun=True),
                ).tooltip("Draw the reflexive loops and both directions of each "
                          "symmetric pair instead of taking them for granted.")
                # The lattice figure shows vertices and facets only by default.
                self.hasse_full_in = ui.switch(
                    "Full face lattice (all dimensions)",
                    value=False,
                    on_change=lambda e: self.switch_changed("hasse_full", e.value, rerun=True),
                ).tooltip("Off, the Hasse diagram draws only the perspectives "
                          "and the worlds, joined when one is part of the other.")
                # The 3-D page is the heavy output of a run (~3 MB of Plotly).
                self.make_3d_in = ui.switch(
                    "Generate interactive 3D view",
                    value=True,
                    on_change=lambda e: self.switch_changed("make_3d", e.value, rerun=True),
                ).tooltip("Off, the run does not write the 3D page (~3 MB): "
                          "only the SVG figures.")
                # Label size of the complex figures; 1.0 is the paper's.
                self.font_scale_in = ui.select(
                    LABEL_SIZES, value=1.0, label="Label size in the complex figures",
                    on_change=lambda e: self.switch_changed(
                        "font_scale", float(e.value or 1.0),
                        preview=page.state["kind"] == "simplicial", rerun=True),
                ).classes("w-72").props("dense options-dense").tooltip(
                    "Agent letters, vertex names, literals and facet names of "
                    "the simplicial drawings. 1.0 is the size used in the paper.")

        # ---- Per-agent relation editor (or the direct-complex editor) ------ #
        self.editor_box = ui.column().classes("w-full gap-4")

    # ------------------------------------------------------------------ #
    # Switches -> state
    # ------------------------------------------------------------------ #
    async def switch_changed(self, key: str, value, preview: bool = False,
                             rerun: bool = False) -> None:
        """A switch was flipped: store it; redraw the preview and rerun the
        pipeline (if there were results) as asked. Nothing happens for the
        assignments made while a document is loaded."""
        page = self.page
        if page.ws.loading or value == page.state.get(key):
            return
        page.state[key] = value
        if preview:
            page.preview.update()
        if rerun and page.current()["outcome"] is not None:
            await page.results.run()

    def axiom_d_changed(self, value: bool) -> None:
        """KD45 forbids Q = ∅, so going back to KD45 clears that box; the
        preview is redrawn because its judge (seriality or not) changed."""
        page = self.page
        if page.ws.loading or value == page.state["axiom_d"]:
            return
        page.state["axiom_d"] = value
        if value:
            self.silent_defunct_in.value = False
        self.sync_switches()
        page.preview.update()

    def show_document(self, state: dict, name: str) -> None:
        """Set the kind, the switches and the name from a document's state."""
        self.kind_in.value = state["kind"]
        self.axiom_d_in.value = state["axiom_d"]
        self.silent_defunct_in.value = state["silent_defunct"]
        self.explicit_in.value = state["explicit"]
        self.hasse_full_in.value = state.get("hasse_full", False)
        self.make_3d_in.value = state.get("make_3d", True)
        self.font_scale_in.value = _nearest_label_size(state.get("font_scale", 1.0))
        self.name_in.value = name

    def sync_switches(self) -> None:
        """Which switches apply to the chosen model kind.

        Knowledge only: S5 is reflexive, hence serial: Axiom D decides
        nothing, nor does empty belief. Belief only: there is no class to
        fall back to, so "believes what it knows" does not exist (silence is
        invalid under KD45 and defunct under K45), and there are no implicit
        edges to show either: every loop and every direction is information.
        """
        kind = self.page.state["kind"]
        self.axiom_d_in.set_enabled(kind != "knowledge")
        self.silent_defunct_in.set_enabled(kind == "kb" and not self.axiom_d_in.value)
        # A complex has no edges to abbreviate; Axiom D does apply (it reads
        # "no isolated perspectives").
        self.explicit_in.set_enabled(kind not in ("belief", "simplicial"))
        # Belief only never reaches the complex, so there is no lattice to choose.
        self.hasse_full_in.set_enabled(kind != "belief")
        self.make_3d_in.set_enabled(kind != "belief")
        self.font_scale_in.set_enabled(kind != "belief")
        self.worlds_box.set_visibility(kind != "simplicial")
        self.page.atoms.set_help(kind)
        self.page.formulas.set_help(kind)

    def rename_current(self) -> None:
        if self.page.ws.rename_active(self.name_in.value):
            self.page.docs_bar.paint()

    def set_kind(self, kind: str) -> None:
        """Change the model kind and repaint everything that depends on it."""
        page, state = self.page, self.page.state
        if kind == state["kind"]:
            return
        previous = state["kind"]
        state["kind"] = kind
        if kind == "simplicial" and not state["facets"]:
            # Start from the translation of the model already drawn instead
            # of an empty editor; if there is none (pure belief, invalid
            # model), start blank and say why.
            try:
                translated = simplicial_state_from_editor(
                    previous, state["agents"], state["worlds"],
                    state["per_agent"], state["atoms"], state["axiom_d"],
                    not state["silent_defunct"],
                )
                for key in ("vertices", "facets", "vatoms", "complex_kind"):
                    state[key] = translated[key]
                ui.notify("Initial complex: the translation of the model that "
                          "was drawn. Edit it freely.", type="info")
            except ValueError as exc:
                state["vertices"] = {a: [] for a in state["agents"]}
                ui.notify(f"Blank complex ({str(exc).splitlines()[0]})",
                          type="warning")
        page.reset_results()
        if kind == "knowledge":
            # Marked beliefs make no sense without belief: they are dropped
            # so that the preview and the pipeline agree with what the
            # editor shows.
            for rows in state["per_agent"].values():
                for row in rows:
                    row["bel"] = []
        self.sync_switches()
        page.repaint_all()

    # ------------------------------------------------------------------ #
    # Agents and worlds
    # ------------------------------------------------------------------ #
    def paint_chips(self) -> None:
        state = self.page.state
        # Every agent chip carries the SAME color as its edges in the figures
        # (agent_color_map replicates the rule of visualization).
        colors = agent_color_map(state["agents"])
        self.agent_chips.clear()
        with self.agent_chips:
            for name in state["agents"]:
                ui.chip(name, removable=True, icon="person",
                        color=colors[name], text_color="white",
                        on_value_change=lambda e, n=name: self.remove_agent(n))
        self.world_chips.clear()
        with self.world_chips:
            for name in state["worlds"]:
                ui.chip(name, removable=True, icon="public",
                        color="var(--p-chip)", text_color="var(--p-ink)",
                        on_value_change=lambda e, n=name: self.remove_world(n))

    def add_agent(self) -> None:
        state = self.page.state
        name = take(self.agent_input)
        if not name:
            return
        if name in state["agents"]:
            ui.notify(f"agent '{name}' already exists", type="warning")
            return
        state["agents"].append(name)
        state["per_agent"].setdefault(name, [])
        self.page.repaint_all()

    def remove_agent(self, name: str) -> None:
        # Its rows are kept in per_agent in case the removal was a mistake;
        # since the agent is no longer listed, they are neither painted nor
        # turned into seeds.
        self.page.state["agents"].remove(name)
        self.page.repaint_all()

    def add_world(self) -> None:
        state = self.page.state
        name = take(self.world_input)
        if not name:
            return
        if name in state["worlds"]:
            ui.notify(f"world '{name}' already exists", type="warning")
            return
        state["worlds"].append(name)
        self.page.repaint_all()

    def remove_world(self, name: str) -> None:
        # A removed world IS pruned from classes, beliefs and atoms: leaving it
        # would produce edges or literals pointing at a nonexistent world.
        state = self.page.state
        state["worlds"].remove(name)
        for rows in state["per_agent"].values():
            for row in rows:
                row["cls"] = [w for w in row["cls"] if w != name]
                row["bel"] = [w for w in row["bel"] if w != name]
        for atom, trues in state["atoms"].items():
            state["atoms"][atom] = [w for w in trues if w != name]
        self.page.repaint_all()

    # ------------------------------------------------------------------ #
    # Relational editor: one card per agent
    # ------------------------------------------------------------------ #
    def set_cls(self, row: dict, cls: list) -> None:
        """Update a class and prune the beliefs that fell outside it.

        In belief only there is no class to respect: the first column is the
        source worlds and belief may point at any world.
        """
        row["cls"] = cls
        if self.page.state["kind"] != "belief":
            row["bel"] = [w for w in row["bel"] if w in cls]
        self.paint()  # the options of the belief select changed
        self.page.preview.update()

    def set_bel(self, row: dict, bel: list) -> None:
        row["bel"] = bel
        self.page.preview.update()

    def add_row(self, agent: str) -> None:
        self.page.state["per_agent"][agent].append({"cls": [], "bel": []})
        self.paint()
        self.page.preview.update()

    def remove_row(self, agent: str, index: int) -> None:
        self.page.state["per_agent"][agent].pop(index)
        self.paint()
        self.page.preview.update()

    def paint(self) -> None:
        state = self.page.state
        if state["kind"] == "simplicial":
            self.page.simplicial.paint(self.editor_box)
            return
        colors = agent_color_map(state["agents"])
        kind = state["kind"]
        self.editor_box.clear()
        with self.editor_box, card():
            # One panel for the whole relation, one SECTION per agent (a
            # hairline between them), instead of a stack of cards: the
            # agents are rows of one table, not separate documents.
            panel_head({"kb": "Knowledge classes and beliefs",
                        "knowledge": "Knowledge classes",
                        "belief": "Belief relation"}[kind])
            for agent in state["agents"]:
                rows = state["per_agent"].setdefault(agent, [])
                with ui.column().classes("section gap-1"):
                    # The colour swatch repeats the agent's colour in the
                    # figures -- same convention as its chips.
                    with ui.row().classes("items-center gap-2 mb-1"):
                        swatch(colors[agent])
                        ui.label(f"Agent {agent}").classes("font-medium")
                        ui.label(f"{len(rows)} " + ("row" if kind == "belief" else "class")
                                 + ("" if len(rows) == 1 else ("s" if kind == "belief" else "es"))) \
                            .classes("text-xs muted")
                    for i, row in enumerate(rows):
                        with ui.row().classes("w-full no-wrap items-center gap-2"):
                            # First column: the knowledge class, or in belief
                            # only the worlds FROM which one believes.
                            # Changing it repaints, because the belief
                            # options depend on the chosen class.
                            ui.select(
                                state["worlds"], multiple=True, value=row["cls"],
                                label=("from (worlds)" if kind == "belief"
                                       else "class (indistinguishable)"),
                                on_change=lambda e, r=row: self.set_cls(r, e.value),
                            ).props("use-chips dense").classes("grow")
                            # Believed worlds: restricted to the class (so a
                            # belief outside the class is inexpressible), or
                            # to all worlds when there is no class. Without
                            # belief, the column does not exist.
                            if kind != "knowledge":
                                ui.select(
                                    state["worlds"] if kind == "belief" else row["cls"],
                                    multiple=True, value=row["bel"],
                                    label=("believes (worlds)" if kind == "belief"
                                           else "believes (empty = what it knows)"),
                                    on_change=lambda e, r=row: self.set_bel(r, e.value),
                                ).props("use-chips dense").classes("grow")
                            ui.button(
                                icon="delete",
                                on_click=lambda _, a=agent, k=i: self.remove_row(a, k),
                            ).props("flat dense color=grey")
                    ui.button(
                        "add row" if kind == "belief" else "add class", icon="add",
                        on_click=lambda _, a=agent: self.add_row(a),
                    ).props("flat dense", remove="color").classes("link-btn")
            if not state["agents"]:
                ui.label("Add the agents first.").classes("muted")
            ui.markdown({
                "kb": "Worlds outside every class remain singleton classes.",
                "knowledge": "Worlds outside every class remain singleton "
                             "classes (the agent tells them apart).",
                "belief": "Worlds without a row believe nothing: invalid under KD45, "
                          "defunct belief under K45.",
            }[kind]).classes("text-xs muted mt-2")

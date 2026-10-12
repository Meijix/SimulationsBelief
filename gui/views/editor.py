"""Identifiers, switches and the relational editor (the "Modelo" tab).

The identifier card holds the document name, the model kind, the agent and
world chips and the logic switches; below it, ``editor_box`` is painted with
one card per agent (knowledge classes and believed worlds) -- or, for a
direct complex, by :class:`views.simplicial_editor.SimplicialEditorView`.
Deliberately simple strategy: any structural change REPAINTS the whole
editor from ``page.state`` and schedules the preview. At this scale (a few
agents/worlds) that is instantaneous and removes all partial-widget
bookkeeping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from adapters import KINDS, agent_color_map, simplicial_state_from_editor
from theme import CARD, FLAT, card_title, take

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
        self.explicit_in = self.hasse_full_in = self.make_3d_in = None

    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #
    def build(self) -> None:
        page = self.page
        # ---- Identifiers ------------------------------------------------- #
        with ui.card().classes(CARD).props(FLAT) as self.ident_card:
            card_title("Agentes y mundos")
            # Document name: the one shown in the models bar and in the
            # comparison panels.
            self.name_in = ui.input("nombre del modelo") \
                .props("dense outlined").classes("w-full")
            self.name_in.on("blur", lambda: self.rename_current())
            self.name_in.on("keydown.enter", lambda: self.rename_current())
            # The core's model kinds. Changing it repaints the editor (the
            # rows change meaning), adjusts which switches apply and redraws
            # the preview.
            self.kind_in = ui.select(
                KINDS, value="kb", label="tipo de modelo",
                on_change=lambda e: self.set_kind(e.value),
            ).props("dense outlined options-dense").classes("w-full")
            with ui.row().classes("w-full no-wrap items-center gap-2"):
                self.agent_input = ui.input("nuevo agente") \
                    .props("dense outlined").classes("grow")
                ui.button(icon="add", on_click=lambda: self.add_agent()) \
                    .props("round dense")
            self.agent_chips = ui.row().classes("w-full gap-2")
            self.agent_input.on("keydown.enter", lambda: self.add_agent())

            # Worlds go in their own container: a direct complex has no
            # worlds (it has facets, declared in their own card), so for that
            # kind the whole block is hidden.
            with ui.column().classes("w-full gap-2") as self.worlds_box:
                with ui.row().classes("w-full no-wrap items-center gap-2 mt-2"):
                    self.world_input = ui.input("nuevo mundo") \
                        .props("dense outlined").classes("grow")
                    ui.button(icon="add", on_click=lambda: self.add_world()) \
                        .props("round dense")
                self.world_chips = ui.row().classes("w-full gap-2")
                self.world_input.on("keydown.enter", lambda: self.add_world())

            # The core's KD45/K45 switch (axiom_d), exposed as is: turning it
            # off legalizes defunct beliefs (Q_a(w) = ∅).
            self.axiom_d_in = ui.switch("Axioma D (KD45; apagado = K45)", value=True).tooltip(
                "KD45 exige que todo agente crea algo en cada mundo (seriedad). "
                "Apagado (K45) una creencia vacía es legal: ahí el agente cree "
                "todo, ⊥ incluido.")

            # Turning Axiom D off only LEGALIZES defunct belief; it does not
            # produce it. The project convention is that silence about belief
            # means "believe exactly what you know" (Q = R), in both logics,
            # and that defunct belief is an explicit opt-in. Without this box
            # the opt-in did not exist in the GUI: K45 was indistinguishable
            # from KD45 and B_a ⊥ was unreachable. It is global (so is the
            # core flag): it affects EVERY class with no belief marked.
            self.silent_defunct_in = ui.switch(
                "Creencia vacía si no se marca nada (Q = ∅)", value=False,
            ).tooltip("Sólo con K45. Apagada, una clase sin creencia marcada "
                      "cree lo que sabe (Q = R).")

            def _reset_silent_defunct() -> None:
                """KD45 forbids Q = ∅: going back to KD45 clears the box.

                Leaving it checked but disabled would send the core a
                combination it rejects, and the user would see a validation
                error caused by a box they can no longer see active.
                """
                if self.axiom_d_in.value:
                    self.silent_defunct_in.value = False

            # Changing the logic repaints the preview: the "to be completed"
            # list and the red worlds come from the frame's contract (KD45
            # demands seriality, K45 does not), so without a repaint the
            # preview kept judging with the previous axiom.
            self.axiom_d_in.on_value_change(lambda _: _reset_silent_defunct())
            self.axiom_d_in.on_value_change(lambda _: self.sync_switches())
            self.axiom_d_in.on_value_change(lambda _: page.preview.update())

            # Drawing options, collapsed: they change figures, not the model,
            # so they need not be in sight all the time.
            with ui.expansion("Opciones de dibujo", icon="brush") \
                    .classes("w-full text-sm").props("dense"):
                # The relational figures omit what the logic already implies:
                # reflexive loops and the second arrow of each symmetric pair
                # (S5 is drawn undirected). This switch draws them all, as
                # they are in the relation: it is the way to SEE what the
                # closures added. It repaints the preview at once and, if
                # there are results already, reruns the pipeline so that
                # Figures 1 and 2 agree.
                self.explicit_in = ui.switch(
                    "Mostrar aristas implícitas (lazos y simetría)",
                    value=False, on_change=lambda _: self.explicit_changed(),
                ).tooltip("Dibuja los lazos reflexivos y ambas direcciones de cada "
                          "par simétrico en vez de darlos por sobreentendidos.")
                # The lattice figure shows only vertices and facets by default
                # (issue #7): perspectives below, worlds above. The full
                # lattice, with every intermediate face, is optional: with
                # three agents it is already hundreds of boxes. Since it only
                # changes one figure of the result, touching it reruns the
                # pipeline if there were results already.
                self.hasse_full_in = ui.switch(
                    "Retículo de caras completo (todas las dimensiones)",
                    value=False, on_change=lambda _: self.hasse_full_changed(),
                ).tooltip("Apagado, el diagrama de Hasse sólo dibuja las perspectivas "
                          "y los mundos, unidos cuando una es parte del otro.")
                # The interactive 3-D page is the heavy output of a run (~3 MB
                # of embedded Plotly) and the slowest to write; off, a run
                # produces the SVG figures only.
                self.make_3d_in = ui.switch(
                    "Generar vista 3D interactiva",
                    value=True, on_change=lambda _: self.make_3d_changed(),
                ).tooltip("Apagada, la corrida no escribe la página 3D (~3 MB): "
                          "sólo las figuras SVG.")

        # ---- Per-agent relation editor (or the direct-complex editor) ------ #
        self.editor_box = ui.column().classes("w-full gap-4")

    # ------------------------------------------------------------------ #
    # Switches <-> state
    # ------------------------------------------------------------------ #
    def read_switches_into(self, state: dict) -> None:
        """The switch values live in the widgets; copy them into the state."""
        state["axiom_d"] = self.axiom_d_in.value
        state["silent_defunct"] = self.silent_defunct_in.value
        state["explicit"] = self.explicit_in.value
        state["hasse_full"] = self.hasse_full_in.value
        state["make_3d"] = self.make_3d_in.value

    def show_document(self, state: dict, name: str) -> None:
        """Set the kind, the switches and the name from a document's state."""
        self.kind_in.value = state["kind"]
        self.axiom_d_in.value = state["axiom_d"]
        self.silent_defunct_in.value = state["silent_defunct"]
        self.explicit_in.value = state["explicit"]
        self.hasse_full_in.value = state.get("hasse_full", False)
        self.make_3d_in.value = state.get("make_3d", True)
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
            # Start-up: instead of an empty editor, the complex that results
            # from translating the model already drawn. From there it is
            # edited freely. If there is no translation (pure belief, invalid
            # model), it starts blank and says why.
            try:
                (state["vertices"], state["facets"],
                 state["vatoms"]) = simplicial_state_from_editor(
                    previous, state["agents"], state["worlds"],
                    state["per_agent"], state["atoms"], self.axiom_d_in.value,
                    not self.silent_defunct_in.value,
                )
                # A knowledge-only relational model translates to a knowledge
                # complex (S_a = S); anything else carries belief data.
                state["complex_kind"] = "knowledge" if previous == "knowledge" else "kb"
                ui.notify("Complejo inicial: la traducción del modelo que "
                          "estaba dibujado. Edítalo libremente.", type="info")
            except ValueError as exc:
                state["vertices"] = {a: [] for a in state["agents"]}
                ui.notify(f"Complejo en blanco ({str(exc).splitlines()[0]})",
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

    async def explicit_changed(self) -> None:
        """Implicit-edges switch: preview now, pipeline if there was a run."""
        page = self.page
        if self.explicit_in.value == page.state.get("explicit"):
            return   # assignment while loading a document, not a click
        page.preview.update()
        if page.current()["outcome"] is not None:
            await page.results.run()

    async def hasse_full_changed(self) -> None:
        """Full-lattice switch: it only affects one figure of the result, so
        there is no preview to repaint; if there were results already they are
        recomputed so that Fig. 4 matches."""
        page = self.page
        if self.hasse_full_in.value == page.state.get("hasse_full", False):
            return   # assignment while loading a document, not a click
        if page.current()["outcome"] is not None:
            await page.results.run()
        else:
            page.state["hasse_full"] = self.hasse_full_in.value

    async def make_3d_changed(self) -> None:
        """3-D switch: like the lattice one, it only changes what a run writes."""
        page = self.page
        if self.make_3d_in.value == page.state.get("make_3d", True):
            return   # assignment while loading a document, not a click
        if page.current()["outcome"] is not None:
            await page.results.run()
        else:
            page.state["make_3d"] = self.make_3d_in.value

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
                        color="rgba(255,255,255,.14)", text_color="white",
                        on_value_change=lambda e, n=name: self.remove_world(n))

    def add_agent(self) -> None:
        state = self.page.state
        name = take(self.agent_input)
        if not name:
            return
        if name in state["agents"]:
            ui.notify(f"el agente '{name}' ya existe", type="warning")
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
            ui.notify(f"el mundo '{name}' ya existe", type="warning")
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
        self.editor_box.clear()
        with self.editor_box:
            for agent in state["agents"]:
                rows = state["per_agent"].setdefault(agent, [])
                with ui.card().classes(CARD).props(FLAT):
                    # The color dot repeats the agent's color in the figures
                    # -- same convention as its chips.
                    with ui.row().classes("items-center gap-2"):
                        ui.element("span").style(
                            f"width:10px;height:10px;border-radius:9999px;"
                            f"background:{colors[agent]}"
                        )
                        ui.label(f"Agente {agent}").classes("font-semibold")
                    kind = state["kind"]
                    for i, row in enumerate(rows):
                        with ui.row().classes("w-full no-wrap items-center gap-2"):
                            # First column: the knowledge class, or in belief
                            # only the worlds FROM which one believes.
                            # Changing it repaints, because the belief
                            # options depend on the chosen class.
                            ui.select(
                                state["worlds"], multiple=True, value=row["cls"],
                                label=("desde (mundos)" if kind == "belief"
                                       else "clase (indistinguibles)"),
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
                                    label=("cree (mundos)" if kind == "belief"
                                           else "cree (vacío = lo que sabe)"),
                                    on_change=lambda e, r=row: self.set_bel(r, e.value),
                                ).props("use-chips dense").classes("grow")
                            ui.button(
                                icon="delete",
                                on_click=lambda _, a=agent, k=i: self.remove_row(a, k),
                            ).props("flat dense color=grey")
                    ui.button(
                        "añadir fila" if kind == "belief" else "añadir clase",
                        icon="add", on_click=lambda _, a=agent: self.add_row(a),
                    ).props("flat dense")
                    ui.markdown({
                        "kb": "Mundos fuera de toda clase quedan como clases unitarias.",
                        "knowledge": "Mundos fuera de toda clase quedan como clases "
                                     "unitarias (el agente los distingue).",
                        "belief": "Mundos sin fila no creen nada: inválido bajo KD45, "
                                  "creencia difunta bajo K45.",
                    }[kind]).classes("text-xs text-grey-5")

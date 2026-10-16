"""Atoms: the valuation v (worlds where each atom is true) or, for a direct
complex, the vertex assignment (which perspectives observe it true / false)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from theme import ATOMS_HELP, CARD, FLAT, card_title, take

if TYPE_CHECKING:
    from views.page import Page


class AtomsView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.card = None
        self.help = None
        self.atom_input = None
        self.box = None

    def build(self) -> None:
        with ui.card().classes(CARD).props(FLAT) as self.card:
            card_title("Atoms (propositions)")
            self.help = ui.markdown(ATOMS_HELP["kb"]).classes("text-xs text-grey-5")
            with ui.row().classes("w-full no-wrap items-center gap-2"):
                self.atom_input = ui.input("new atom") \
                    .props("dense outlined").classes("grow")
                ui.button(icon="add", on_click=lambda: self.add_atom()) \
                    .props("round dense")
            self.atom_input.on("keydown.enter", lambda: self.add_atom())
            self.box = ui.column().classes("w-full gap-2")

    def set_help(self, kind: str) -> None:
        self.help.set_content(ATOMS_HELP[kind])

    def add_atom(self) -> None:
        state = self.page.state
        name = take(self.atom_input)
        if not name:
            return
        simplicial = state["kind"] == "simplicial"
        if name in (state["vatoms"] if simplicial else state["atoms"]):
            ui.notify(f"atom '{name}' already exists", type="warning")
            return
        if simplicial:
            state["vatoms"][name] = {"true": [], "false": []}
        else:
            state["atoms"][name] = []
        self.paint()
        self.page.preview.update()

    def remove_atom(self, name: str) -> None:
        state = self.page.state
        (state["vatoms"] if state["kind"] == "simplicial" else state["atoms"]).pop(name)
        self.paint()
        self.page.preview.update()

    def set_vatom(self, name: str, side: str, values: list) -> None:
        """Vertices that observe the atom true ("true") or false ("false")."""
        self.page.state["vatoms"][name][side] = values
        self.page.preview.update()

    def set_atom(self, name: str, trues: list) -> None:
        self.page.state["atoms"][name] = trues
        self.page.preview.update()

    def paint(self) -> None:
        state = self.page.state
        self.box.clear()
        if state["kind"] == "simplicial":
            # Atoms on vertices: two selects per atom. A vertex in neither of
            # them "does not know" (value 2), which is the default case of
            # the vertex-based semantics.
            every = [v for a in state["agents"] for v in state["vertices"].get(a, [])]
            with self.box:
                for name, spec in state["vatoms"].items():
                    with ui.row().classes("w-full no-wrap items-center gap-2"):
                        ui.label(name).classes("font-mono w-10")
                        ui.select(
                            every, multiple=True, value=spec["true"],
                            label="observed true by",
                            on_change=lambda e, n=name: self.set_vatom(n, "true", e.value),
                        ).props("use-chips dense").classes("grow")
                        ui.select(
                            every, multiple=True, value=spec["false"],
                            label="observed false by",
                            on_change=lambda e, n=name: self.set_vatom(n, "false", e.value),
                        ).props("use-chips dense").classes("grow")
                        ui.button(
                            icon="delete",
                            on_click=lambda _, n=name: self.remove_atom(n),
                        ).props("flat dense color=grey")
            return
        with self.box:
            for name, trues in state["atoms"].items():
                with ui.row().classes("w-full no-wrap items-center gap-2"):
                    ui.label(name).classes("font-mono w-10")
                    ui.select(
                        state["worlds"], multiple=True, value=trues,
                        label="true in",
                        on_change=lambda e, n=name: self.set_atom(n, e.value),
                    ).props("use-chips dense").classes("grow")
                    ui.button(
                        icon="delete",
                        on_click=lambda _, n=name: self.remove_atom(n),
                    ).props("flat dense color=grey")

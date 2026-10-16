"""Header: the title, the example library and the Run button."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from adapters import EXAMPLES

if TYPE_CHECKING:
    from views.page import Page


class HeaderView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.run_btn = None

    def build(self) -> None:
        # The layout is the CSS of .poster-header (a wrapping flex row), so
        # the controls move below the title on narrow windows instead of
        # overlapping; wrap=True lets Quasar size the header to its wrapped
        # height.
        with ui.header(wrap=True).classes("poster-header text-white px-6 py-3 shadow-none"):
            with ui.column().classes("gap-0 header-title"):
                ui.label("The geometry of a false belief") \
                    .classes("text-xl font-extrabold text-white leading-tight")
                ui.label("A tool to build, validate and translate epistemic-logic "
                         "models · pipeline general → proper → simplicial") \
                    .classes("text-xs italic text-grey-4 header-sub")
            with ui.element("div").classes("header-controls"):
                ui.select(
                    {k: ex["label"] for k, ex in EXAMPLES.items()},
                    value=None, label="load example",
                    on_change=lambda e: self.page.load_example(e.value),
                ).props("dense outlined options-dense").classes("header-example")
                # Lime with navy text: the only filled button on the page.
                self.run_btn = ui.button("Run pipeline", icon="play_arrow",
                                         on_click=lambda: self.page.results.run()) \
                    .props("color=primary text-color=dark unelevated") \
                    .classes("font-bold")

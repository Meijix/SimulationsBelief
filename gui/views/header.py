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
        self.theme_btn = None

    def paint_theme(self) -> None:
        """The toggle shows the theme it would switch TO."""
        if self.theme_btn is None:
            return
        dark = self.page.theme == "dark"
        self.theme_btn.props(f'icon={"light_mode" if dark else "dark_mode"}')
        self.theme_btn.tooltip("Switch to the light theme" if dark else "Switch to the dark theme")

    def build(self) -> None:
        # The layout is the CSS of .poster-header (a wrapping flex row), so
        # the controls move below the title on narrow windows instead of
        # overlapping; wrap=True lets Quasar size the header to its wrapped
        # height.
        with ui.header(wrap=True).classes("poster-header ink px-6 py-3 shadow-none"):
            with ui.element("div").classes("header-title"):
                # The title in the serif of the paper.
                ui.label("The geometry of a false belief") \
                    .classes("text-lg font-semibold serif ink leading-tight")
            with ui.element("div").classes("header-controls"):
                # Dark / light: the one icon-only control, as in every editor.
                self.theme_btn = ui.button(icon="light_mode",
                                           on_click=lambda: self.page.set_theme(
                                               "light" if self.page.theme == "dark" else "dark")) \
                    .props("flat dense round", remove="color").classes("quiet-btn")
                self.paint_theme()
                ui.select(
                    {k: ex["label"] for k, ex in EXAMPLES.items()},
                    value=None, label="load example",
                    on_change=lambda e: self.page.load_example(e.value),
                ).props("dense outlined options-dense").classes("header-example")
                # The accent with ink text: the only filled button on the page.
                self.run_btn = ui.button("Run pipeline", icon="play_arrow",
                                         on_click=lambda: self.page.results.run()) \
                    .props("color=primary text-color=dark unelevated") \
                    .classes("font-bold")

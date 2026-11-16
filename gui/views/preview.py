"""The live preview and the "results are stale" strip.

The preview draws the model exactly as entered (no closures) on every edit,
through :class:`views.live_figure.LiveFigure`; the card is built once and
only its badge and body are repainted.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from nicegui import ui

from adapters import preview_state, state_problem
from theme import card, chip, figure_img, panel_head, pre, status
from views.live_figure import LiveFigure

if TYPE_CHECKING:
    from views.page import Page


class PreviewView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.box = None             # the preview card goes here
        self.stale_box = None       # the amber strip goes here
        self.live = LiveFigure(page, "model")
        self._badge = None          # containers of the card, once built
        self._body = None

    def build(self) -> None:
        self.box = ui.column().classes("w-full")
        self.stale_box = ui.column().classes("w-full")

    def _card(self) -> None:
        """Build the preview card once (the only card with a rule in the accent)."""
        if self._body is not None:
            return
        with self.box, card("poster-live"):
            with panel_head("Live preview · model as entered"):
                self._badge = ui.row().classes("items-center")
            self._body = ui.column().classes("w-full gap-2")

    def clear_cache(self) -> None:
        self.live.clear_cache()

    def update(self) -> None:
        """Mark the model as edited (unless a document is being loaded) and
        schedule a re-render."""
        page = self.page
        if page.ws.active is None:
            return
        if not page.ws.loading:
            page.current()["dirty"] = True
        self.refresh_stale()
        self._card()
        st = copy.deepcopy(page.state)
        missing = state_problem(st)
        if missing:
            self.live.cancel()
            self._badge.clear()
            self._body.clear()
            with self._body:
                ui.label(missing).classes("muted")
            return
        doc_id = page.ws.active

        def render(state, key):
            # Document id + state hash tag the file: two open models do not
            # overwrite each other's preview, nor do two states of one model.
            return preview_state(state, f"{doc_id}_{key}")

        def paint(result):
            if doc_id == page.ws.active:
                self._paint(result)

        def pending():
            self._badge.clear()
            with self._badge:
                ui.spinner(size="1.2em").style("color:var(--p-accent-ink)")

        self.live.schedule(self.box, st, render, paint, pending)

    def _paint(self, result) -> None:
        """Validity mark and figure (or the message of an inexpressible state)."""
        badge, body = self._badge, self._body
        badge.clear()
        body.clear()
        if isinstance(result, str):
            with badge:
                chip("inexpressible", "bad")
            with body:
                pre(result)
            return
        path, violations = result
        with badge:
            if violations:
                status(f"{len(violations)} to complete", "warn")
            else:
                status("valid", "ok")
        with body:
            with ui.element("div").classes("w-full fig-frame"):
                figure_img(path)
            if violations:
                with ui.expansion("What the closures will complete") \
                        .classes("w-full").style("color:var(--p-warn)"):
                    for v in violations:
                        ui.label(v).classes("font-mono text-xs")

    def refresh_stale(self) -> None:
        """Show, above the results, that they predate the current edits
        (``doc["dirty"]`` tracks exactly that)."""
        page = self.page
        self.stale_box.clear()
        if page.ws.active is None or page.ws.comparing:
            return
        doc = page.current()
        if doc["outcome"] is None or not doc["dirty"]:
            return
        with self.stale_box, ui.row().classes(
                "w-full items-center gap-3 px-4 py-2 rounded no-wrap stale-strip"):
            ui.label("The figures below belong to an earlier version of the model.") \
                .classes("text-sm grow")
            ui.button("Run again", icon="play_arrow",
                      on_click=lambda: page.results.run()) \
                .props("outline dense", remove="color")

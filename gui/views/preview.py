"""The live preview and the "results are stale" strip.

The preview is the one thing that runs on EVERY edit and it calls Graphviz /
matplotlib (0.3-0.8 s): done synchronously it froze the interface at each
click of a select. So:

  1. the synchronous part (``update``) only marks the document dirty,
     refreshes the "stale results" strip and schedules a render;
  2. a 250 ms debounce collapses a burst of edits into one render, and a
     sequence number drops renders that a newer edit superseded;
  3. the render runs in a worker thread (``run.io_bound``), so the page stays
     responsive and the spinner in the card header is visible;
  4. results are cached by a hash of the state, and the figure FILE is named
     by that hash too, so going back to a state already drawn (switching
     documents, undoing an edit) costs nothing and a cached path always
     points at the figure of exactly that state.

The card itself is built once; only its badge and body are repainted, so the
frame does not flash on every edit.
"""

from __future__ import annotations

import copy
import html
from typing import TYPE_CHECKING

from nicegui import run as io, ui

from adapters import preview_state, state_problem
from theme import CARD, FLAT, POSTER, card_title, chip, figure_img, tint

if TYPE_CHECKING:
    from views.page import Page


class PreviewView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.box = None             # the preview card goes here
        self.stale_box = None       # the amber strip goes here
        self._cache: dict = {}      # state hash -> (path, violations) | error text
        self._seq = 0
        self._badge = None          # containers of the card, once built
        self._body = None

    def build(self) -> None:
        # ---- Live preview (always visible, on top) ------------------------- #
        self.box = ui.column().classes("w-full")
        # ---- "Results are stale" strip (shown once the model is edited after
        #      a run; see refresh_stale) ------------------------------------- #
        self.stale_box = ui.column().classes("w-full")

    @staticmethod
    def _state_key(st: dict) -> str:
        import hashlib
        import json

        return hashlib.sha1(json.dumps(st, sort_keys=True, default=str).encode()).hexdigest()[:12]

    def _card(self) -> None:
        """Build the preview card once (the only card WITH elevation: lime halo)."""
        if self._body is not None:
            return
        with self.box, ui.card().classes(CARD + " poster-live").props(FLAT):
            with ui.row().classes("w-full items-center gap-2"):
                ui.element("span").classes("pulse-dot")
                card_title("Vista previa · modelo tal como se ingresa")
                ui.space()
                self._badge = ui.row().classes("items-center")
            self._body = ui.column().classes("w-full gap-2")

    def update(self) -> None:
        """Mark the model as edited and schedule a (debounced) re-render."""
        page = self.page
        if page.ws.loading:
            return
        # Every edit goes through here: the stored result, if any, no longer
        # matches the model and the comparison will have to recompute it.
        page.current()["dirty"] = True
        self.refresh_stale()
        self._seq += 1
        seq = self._seq
        ui.timer(0.25, lambda: self._render(seq), once=True)

    async def _render(self, seq: int) -> None:
        """Draw the model exactly as entered (no closures), off the event loop.

        The card header carries the pulsing "live" dot and a validity chip
        (lime = already valid, amber = N conditions to be completed); the
        figure shows exactly the drawn chips with what is missing dotted in
        red. A state inexpressible as seeds (overlapping classes) is shown
        as text.
        """
        page = self.page
        if seq != self._seq or page.ws.active is None:
            return                              # superseded by a newer edit
        self._card()
        badge, body = self._badge, self._body
        st = copy.deepcopy(page.live_state())
        doc_id = page.ws.active
        missing = state_problem(st)
        if missing:
            badge.clear()
            body.clear()
            with body:
                ui.label(missing).classes("text-grey-5")
            return
        key = self._state_key(st)
        if key not in self._cache:
            badge.clear()
            with badge:
                ui.spinner(size="1.2em").style(f"color:{POSTER['lime']}")
            try:
                # Document id + state hash tag the file: two open models do
                # not overwrite each other's preview, and two states of one
                # model do not either (which is what makes the cache safe).
                result = await io.io_bound(preview_state, st, f"{doc_id}_{key}")
            except ValueError as exc:
                result = str(exc)
            if len(self._cache) >= 64:          # bounded: oldest entry out
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = result
            if seq != self._seq or doc_id != page.ws.active:
                return                          # the user moved on meanwhile
        result = self._cache[key]
        badge.clear()
        body.clear()
        if isinstance(result, str):
            with badge:
                chip("inexpresable", "bad")
            with body:
                ui.html(f"<pre style='white-space:pre-wrap' class='text-xs'>"
                        f"{html.escape(result)}</pre>")
            return
        path, violations = result
        with badge:
            if violations:
                chip(f"{len(violations)} por completar", "warn", icon="pending")
            else:
                chip("válido", "ok", icon="check")
        with body:
            with ui.element("div").classes("w-full fig-frame"):
                figure_img(path)
            if violations:
                with ui.expansion("Lo que las clausuras completarán") \
                        .classes("w-full").style(f"color:{POSTER['yellow']}"):
                    for v in violations:
                        ui.label(v).classes("font-mono text-xs")

    def refresh_stale(self) -> None:
        """Show, above the results, that they predate the current edits.

        The preview follows every edit but the Figures 1-4 do not (a run is
        explicit); without this strip the old figures passed for results of
        the model now in the editor. ``doc["dirty"]`` already tracks exactly
        that, so the strip is a pure function of it.
        """
        page = self.page
        self.stale_box.clear()
        if page.ws.active is None or page.ws.comparing:
            return
        doc = page.current()
        if doc["outcome"] is None or not doc["dirty"]:
            return
        with self.stale_box, ui.row().classes(
                "w-full items-center gap-3 px-4 py-2 rounded-xl no-wrap").style(
                f"background:{tint(POSTER['yellow'], .10)};"
                f"border:1px solid {tint(POSTER['yellow'], .45)}"):
            ui.icon("history").style(f"color:{POSTER['yellow']}")
            ui.label("Las figuras de abajo son de una versión anterior del modelo.") \
                .classes("text-sm grow").style(f"color:{POSTER['yellow']}")
            ui.button("Volver a correr", icon="play_arrow",
                      on_click=lambda: page.results.run()) \
                .props("outline dense").style(f"color:{POSTER['yellow']}")

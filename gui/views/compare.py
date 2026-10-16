"""Side-by-side comparison of 2 to 4 models.

It replaces the editor row while open (four panels do not fit next to a
440px editor). Each panel shows the document's ALREADY stored result; only
those never run or changed since their last run (``dirty``) are recomputed.
It serves both "the same action on several inputs" and "two actions on the
same input": in both cases they are documents, and here they are seen
together.
"""

from __future__ import annotations

import copy
import html
from typing import TYPE_CHECKING

from nicegui import ui

from adapters import KINDS
from theme import CARD, FLAT, POSTER, chip

if TYPE_CHECKING:
    from views.page import Page


class CompareView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.box = None

    def build(self) -> None:
        self.box = ui.column().classes("w-full gap-4 p-4")
        self.box.set_visibility(False)

    def render_panel(self, doc: dict) -> None:
        """One comparison panel: header, metrics and figures of the model."""
        results = self.page.results
        outcome = doc["outcome"]
        with ui.column().classes("gap-3 min-w-0").style("flex:1 1 0"):
            with ui.card().classes(CARD).props(FLAT):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    if doc["readonly"]:
                        ui.icon("lock").style(f"color:{POSTER['yellow']}")
                    ui.label(doc["name"]).classes("font-bold text-white grow")
                ui.label(KINDS[doc["state"]["kind"]]).classes("eyebrow")
                if doc["origin"] and doc["origin"].get("label"):
                    ui.label("Result of " + doc["origin"]["label"]) \
                        .classes("text-xs italic text-grey-5")
                if outcome["status"] == "ok":
                    out = outcome["out"]
                    with ui.row().classes("w-full gap-1"):
                        for text, color in out.badges:
                            tone = {"positive": "ok", "negative": "bad"}.get(color, "info")
                            chip(text, tone).props("dense")
                    with ui.row().classes("w-full gap-5 mt-1"):
                        for value, label in out.stats:
                            with ui.column().classes("gap-0 items-center"):
                                ui.label(value).classes("text-lg font-bold text-white")
                                ui.label(label).classes("text-xs text-grey-5")
                    # From the log, only what stopped the pipeline: the full
                    # detail is in that model's editor.
                    for step in out.steps:
                        for text in step.failed:
                            ui.label(f"{step.name}: failed").classes(
                                "text-xs font-semibold text-pink-3 mt-2")
                            ui.html(f"<pre style='white-space:pre-wrap' "
                                    f"class='text-xs'>{html.escape(text)}</pre>")
            if outcome["status"] != "ok":
                results.render_failure(outcome)
                return
            for caption, path in outcome["out"].figures:
                results.figure_card(caption, path)
            if outcome["out"].html_3d is not None:
                ui.label("Interactive 3D view: open it from this model's "
                         "editor.").classes("text-xs italic text-grey-5")

    async def open(self) -> None:
        page, ws = self.page, self.page.ws
        chosen = ws.chosen()
        if not 2 <= len(chosen) <= 4:
            ui.notify("Choose 2 to 4 models to compare.", type="warning")
            return
        ws.store_active(page.live_state())      # the active one, up to date
        ws.comparing = True
        page.editor_row.set_visibility(False)
        self.box.set_visibility(True)
        page.docs_bar.paint()
        self.box.clear()
        with self.box, ui.card().classes(CARD).props(FLAT):
            with ui.column().classes("w-full items-center py-10 gap-2"):
                ui.spinner(size="lg")
                ui.label(f"Preparing {len(chosen)} models…").classes("text-grey-5")
        for doc in chosen:
            if doc["outcome"] is None or doc["dirty"]:
                doc["outcome"] = await page.results.compute(copy.deepcopy(doc["state"]), doc["id"])
                doc["dirty"] = False
        self.box.clear()
        with self.box, ui.row().classes("w-full no-wrap items-start gap-4"):
            for doc in chosen:
                self.render_panel(doc)
        # The active document's editor stays consistent with what was just computed.
        page.results.render_outcome(page.current()["outcome"])

    def exit(self) -> None:
        page = self.page
        page.ws.comparing = False
        self.box.set_visibility(False)
        page.editor_row.set_visibility(True)
        page.docs_bar.paint()
        page.preview.refresh_stale()

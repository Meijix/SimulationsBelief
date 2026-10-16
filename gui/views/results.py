"""Running the pipeline and painting its result (metrics, log, figures, 3D).

Running a model and painting its result are two separate things: the same
result is stored in its document, repainted when coming back to it and
reused by the comparison without recomputing. The run is asynchronous with a
loading state: the Run button shows a spinner and the heavy work goes to a
thread via ``run.io_bound``, so the interface does not freeze.
"""

from __future__ import annotations

import copy
import html
import shutil
import traceback
from typing import TYPE_CHECKING

from nicegui import run as io, ui

from adapters import run_state
from theme import CARD, FLAT, POSTER, card_title, chip, figure_img, is_wide, url

if TYPE_CHECKING:
    from views.page import Page


class ResultsView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.container = None
        self._lightbox = self._lb_img = self._lb_cap = None

    def build(self) -> None:
        # ---- Pipeline output: rebuilt on every run ------------------------- #
        self.container = ui.column().classes("w-full gap-4")
        # ---- Lightbox: any figure, full screen with one click -------------- #
        with ui.dialog().props("maximized") as self._lightbox:
            with ui.column().classes(
                "w-full h-full items-center justify-center bg-black cursor-zoom-out"
            ) as lb_body:
                self._lb_img = ui.image().classes("max-w-[92vw] max-h-[86vh]") \
                    .props("fit=contain")
                self._lb_cap = ui.label().classes("text-white text-sm italic mt-2")
            lb_body.on("click", self._lightbox.close)

    # ---- figures ----------------------------------------------------------- #
    def open_lightbox(self, path, caption: str) -> None:
        self._lb_img.set_source(url(path))
        self._lb_cap.set_text(caption)
        self._lightbox.open()

    def figure_card(self, caption: str, path, span: bool = False) -> None:
        """Paper-style figure: grey frame, italic caption, click to enlarge.

        ``span`` marks a wide figure inside a ``.fig-grid``: it takes the
        whole row while tall ones sit two by two (see the CSS).
        """
        with ui.card().classes(CARD + (" fig-wide" if span else "")).props(FLAT):
            holder = ui.element("div").classes("w-full fig-frame cursor-zoom-in")
            with holder:
                figure_img(path)
            holder.on("click", lambda p=path, c=caption: self.open_lightbox(p, c))
            ui.label(caption).classes("text-xs italic text-grey-5 mt-2")

    # ---- computing --------------------------------------------------------- #
    async def compute(self, st: dict, tag: str) -> dict:
        """Run the pipeline of ONE state; never raises.

        Returns an "outcome": ``{"status": "ok", "out": PipelineResult}``,
        ``{"status": "invalid", "message": ...}`` when the core rejects the
        model (pedagogical content, shown as is), or
        ``{"status": "error", "trace": ..., "no_dot": bool}`` for the rest:
        environment (Graphviz missing) or a bug. Catching everything is
        deliberate: this is the edge of a UI handler and the app must stay
        alive.
        """
        try:
            return {"status": "ok", "out": await io.io_bound(run_state, st, tag)}
        except ValueError as exc:
            return {"status": "invalid", "message": str(exc)}
        except Exception:  # noqa: BLE001 -- see docstring
            return {"status": "error", "trace": traceback.format_exc(),
                    "no_dot": shutil.which("dot") is None}

    async def run(self) -> None:
        """Run the ACTIVE model and paint its result."""
        page = self.page
        doc = page.current()
        run_btn = page.header.run_btn
        self.container.clear()
        run_btn.props("loading")
        with self.container, ui.card().classes(CARD).props(FLAT):
            with ui.column().classes("w-full items-center py-10 gap-2"):
                ui.spinner(size="lg")
                ui.label("Generating figures…").classes("text-grey-5")
        try:
            outcome = await self.compute(copy.deepcopy(page.live_state()), doc["id"])
        finally:
            run_btn.props(remove="loading")
        doc["outcome"], doc["dirty"] = outcome, False
        page.preview.refresh_stale()
        if outcome["status"] == "invalid":
            ui.notify("The model is not valid — details in the panel", type="negative")
        elif outcome["status"] == "error":
            ui.notify("Error while running the pipeline — details in the panel", type="negative")
        if doc["id"] == page.ws.active:   # the model may have been switched mid-run
            self.render_outcome(outcome)

    # ---- painting ---------------------------------------------------------- #
    def placeholder(self, target=None) -> None:
        """Empty state: never a blank column without a message."""
        target = self.container if target is None else target
        with target, ui.column().classes("w-full items-center py-16 gap-1"):
            ui.label("No results yet").classes("text-grey-5 font-semibold")
            ui.label("Run the pipeline to see Figures 1 → 4") \
                .classes("text-xs text-grey-6")

    def render_failure(self, outcome: dict) -> None:
        """Failure card for an 'invalid' or 'error' outcome."""
        with ui.card().classes(CARD + " poster-bad").props(FLAT):
            if outcome["status"] == "invalid":
                ui.label("Model rejected by the core's validation:") \
                    .classes("font-semibold text-pink-3")
                ui.html(f"<pre style='white-space:pre-wrap'>"
                        f"{html.escape(outcome['message'])}</pre>")
                return
            if outcome["no_dot"]:
                ui.label("Graphviz is missing").classes("font-semibold text-pink-3")
                ui.html(
                    "<p>The pipeline needs the <code>dot</code> binary "
                    "to draw the figures, and it is not on the PATH.</p>"
                    "<p>Install it with <code>brew install graphviz</code> "
                    "(macOS) or <code>apt install graphviz</code> (Linux) "
                    "and run again.</p>"
                )
            else:
                ui.label("Unexpected error (this is a bug, please report it):") \
                    .classes("font-semibold text-pink-3")
            ui.html(f"<pre style='white-space:pre-wrap' class='text-xs'>"
                    f"{html.escape(outcome['trace'])}</pre>")

    def render_outcome(self, outcome: dict | None, target=None) -> None:
        """Paint the complete result of a run into ``target`` (the results column by default)."""
        target = self.container if target is None else target
        target.clear()
        if outcome is None:
            self.placeholder(target)
            return
        if outcome["status"] != "ok":
            with target:
                self.render_failure(outcome)
            return
        out = outcome["out"]
        with target:
            # Run metrics as stat tiles + status chips (the same numbers as
            # the old text log, readable in a second).
            with ui.card().classes(CARD).props(FLAT):
                with ui.row().classes("w-full items-center gap-2"):
                    card_title("Pipeline result")
                    ui.space()
                    # Badges come with Quasar palette names
                    # (positive/negative/primary); they are mapped to the
                    # role tones so they do not come out lime with white text.
                    for text, color in out.badges:
                        tone = {"positive": "ok", "negative": "bad"}.get(color, "info")
                        chip(text, tone).props("dense")
                with ui.row().classes("w-full gap-8 mt-2"):
                    for value, label in out.stats:
                        with ui.column().classes("gap-0 items-center"):
                            ui.label(value).classes("text-2xl font-bold text-white")
                            ui.label(label).classes("text-xs text-grey-5")

            # Step-by-step pipeline log: what was completed, what is missing
            # and what failed. It is shown first because it answers the
            # question people bring ("why didn't I get what I drew?") before
            # they start looking at the figures.
            if out.steps:
                with ui.card().classes(CARD).props(FLAT):
                    card_title("Pipeline step by step")
                    for step in out.steps:
                        # Two accents: lime for "as drawn" and "completed by a
                        # closure" (both good outcomes), rose for failed,
                        # slate for not applicable.
                        icon, color = {
                            "ok": ("check_circle", POSTER["lime"]),
                            "completed": ("auto_fix_high", POSTER["lime"]),
                            "failed": ("cancel", POSTER["pink"]),
                            "skipped": ("block", POSTER["muted"]),
                        }[step.status]
                        with ui.row().classes("w-full items-center gap-2 mt-3"):
                            ui.icon(icon).style(f"color:{color}")
                            ui.label(step.name).classes("font-semibold")
                            if step.status == "ok":
                                ui.label("exactly as drawn").classes("text-xs text-grey-5")
                            if step.status == "skipped":
                                ui.label("does not apply to this model kind") \
                                    .classes("text-xs text-grey-5")
                        for text in step.skipped:
                            with ui.row().classes("w-full no-wrap items-start gap-2 ml-8"):
                                ui.label("–").classes("font-bold text-grey-5")
                                ui.label(text).classes("text-sm text-grey-4")
                        for text in step.failed:
                            with ui.column().classes("w-full gap-0 ml-8 p-2 rounded poster-bad"):
                                ui.label("Failed here — the pipeline stopped:") \
                                    .classes("text-xs font-semibold text-pink-3")
                                ui.html(f"<pre style='white-space:pre-wrap' "
                                        f"class='text-xs'>{html.escape(text)}</pre>")
                        for text in step.completed:
                            with ui.row().classes("w-full no-wrap items-start gap-2 ml-8"):
                                ui.label("+").classes("font-bold").style(f"color:{POSTER['lime']}")
                                ui.label(text).classes("text-sm text-grey-4")
                        for text in step.missing:
                            with ui.row().classes("w-full no-wrap items-start gap-2 ml-8"):
                                ui.label("?").classes("font-bold").style(f"color:{POSTER['yellow']}")
                                ui.label(text).classes("text-sm text-grey-4")
                    ui.label(
                        "+ what a closure or convention completed for you · "
                        "? what is still unspecified and what that silence means"
                    ).classes("text-xs italic text-grey-5 mt-3")

            # The pipeline figures, in order, as in thesis_example.py, plus
            # Fig. 4 (face lattice) added by adapters. A grid: tall figures
            # (Fig. 2a's column of copies, a triangle fan) share a row, wide
            # ones (the Hasse band) take it whole -- half the scrolling and
            # no figure floating in a sea of grey.
            with ui.element("div").classes("w-full fig-grid"):
                for caption, path in out.figures:
                    self.figure_card(caption, path, span=is_wide(path))

            # The interactive 3D view is a complete plotly page: it is embedded
            # in an iframe instead of being rebuilt with components.
            if out.html_3d is not None:
                with ui.card().classes(CARD).props(FLAT):
                    card_title("Interactive 3D view of the complex")
                    # The plotly page is light: it goes on the same sheet as
                    # the figures so it is not a loose white block over navy.
                    # sanitize=False: ui.html sanitizes HTML by default and
                    # REMOVES <iframe>s, which left the 3D view as an empty
                    # card. The src is our own file served from outputs/.
                    ui.html(
                        f'<iframe src="{url(out.html_3d)}" '
                        'style="width:100%;height:560px;border:none;'
                        'display:block;border-radius:.375rem"></iframe>',
                        sanitize=False,
                    ).classes("w-full fig-frame fig-fill")
                    ui.label("Drag to rotate; scroll to zoom.") \
                        .classes("text-xs italic text-grey-5")

            # Text diagrams (visualize): the dependency-free view, collapsed
            # by default so it does not compete with the figures.
            with ui.expansion("Text diagrams").classes("w-full"):
                for caption, diagram in out.text_diagrams:
                    ui.label(caption).classes("font-semibold mt-2")
                    ui.html(f"<pre style='white-space:pre-wrap' "
                            f"class='text-xs'>{diagram}</pre>")

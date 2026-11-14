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
import io as pyio
import re
import shutil
import traceback
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import run as io, ui

from adapters import print_light, run_state, styled
from theme import CARD, FLAT, figure_caption, figure_img, panel_head, status, url

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
                "w-full h-full items-center justify-center cursor-zoom-out"
            ).style("background:var(--p-page)"
            ) as lb_body:
                self._lb_img = ui.image().classes("max-w-[92vw] max-h-[86vh]") \
                    .props("fit=contain")
                self._lb_cap = ui.label().classes("text-sm serif mt-2").style("color:var(--p-ink)")
            lb_body.on("click", self._lightbox.close)

    # ---- figures ----------------------------------------------------------- #
    def open_lightbox(self, path, caption: str) -> None:
        self._lb_img.set_source(url(path))
        self._lb_cap.set_text(caption)
        self._lightbox.open()

    def figure_card(self, caption: str, path, span: bool = False) -> None:
        """A figure as in an article: the drawing, its caption below, a
        hairline before the next. Click to enlarge. (``span`` is kept for
        callers; figures sit one per row now.)"""
        with ui.element("div").classes("w-full fig-block"):
            holder = ui.element("div").classes("w-full fig-frame cursor-zoom-in")
            with holder:
                figure_img(path)
            holder.on("click", lambda p=path, c=caption: self.open_lightbox(p, c))
            figure_caption(caption)

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
            return {"status": "ok", "out": await io.io_bound(styled, self.page.ink, run_state, st, tag)}
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
                ui.label("Generating figures…").classes("muted")
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

    def open_kripke(self, state: dict) -> None:
        """Open the equivalent Kripke model of the active complex as a new document."""
        page, ws = self.page, self.page.ws
        source = page.current()
        ws.store_active(page.live_state())
        doc = ws.new_doc(f"{source['name']} · Kripke", copy.deepcopy(state), readonly=False,
                         origin={"label": f"complex → Kripke model (G_B) of {source['name']}"})
        # Notify BEFORE activating: activating repaints the results column,
        # and with it the button whose click is being handled.
        ui.notify(f"Kripke model opened as “{doc['name']}”: run the pipeline to take it "
                  "back to a complex.", type="positive")
        page.activate(doc["id"])

    async def download_figures(self) -> None:
        """Render the active model's figures as light PNGs and download a zip.

        The on-screen figures are SVG in the page's ink (dark, usually); a
        figure that leaves the page must print, so the pipeline is run once
        more through ``print_light`` -- light ink, white background, PNG --
        under a tag of its own, and the files are zipped with stable names
        and a README that maps each to its caption.
        """
        page = self.page
        doc = page.current()
        tag = f"print_{doc['id']}"
        ui.notify("Rendering the figures with a light background…", type="info", timeout=2500)
        try:
            out = await io.io_bound(print_light, run_state, copy.deepcopy(page.live_state()), tag)
        except Exception as exc:  # noqa: BLE001 -- a failed print must not take the page down
            ui.notify(f"Could not render the figures: {str(exc).splitlines()[0]}", type="negative")
            return
        if out is None:
            return
        buf = pyio.BytesIO()
        lines = [f"# {doc['name']}", "", "Figures rendered with a light background (PNG).", "",
                 "| file | figure |", "|---|---|"]
        files = list(out.figures)
        if out.html_3d is not None:
            files.append(("Interactive 3D view (open in the browser)", out.html_3d))
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for caption, src in files:
                src = Path(src)
                if not src.exists():
                    continue
                stable = re.sub(rf"_{re.escape(tag)}(?=\.[A-Za-z0-9]+$)", "", src.name)
                zf.write(src, stable)
                lines.append(f"| `{stable}` | {caption} |")
            zf.writestr("README.md", "\n".join(lines) + "\n")
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", doc["name"]).strip("-") or "model"
        ui.download.content(buf.getvalue(), f"{slug}-figures.zip")

    # ---- painting ---------------------------------------------------------- #
    def placeholder(self, target=None) -> None:
        """Empty state: never a blank column without a message."""
        target = self.container if target is None else target
        with target, ui.column().classes("w-full py-6 gap-1"):
            ui.label("No results yet. Run the pipeline to see Figures 1 to 4.") \
                .classes("text-sm muted")

    def render_failure(self, outcome: dict) -> None:
        """Failure card for an 'invalid' or 'error' outcome."""
        with ui.card().classes(CARD + " poster-bad").props(FLAT):
            if outcome["status"] == "invalid":
                ui.label("Model rejected by the core's validation:") \
                    .classes("font-semibold bad-text")
                ui.html(f"<pre style='white-space:pre-wrap'>"
                        f"{html.escape(outcome['message'])}</pre>")
                return
            if outcome["no_dot"]:
                ui.label("Graphviz is missing").classes("font-semibold bad-text")
                ui.html(
                    "<p>The pipeline needs the <code>dot</code> binary "
                    "to draw the figures, and it is not on the PATH.</p>"
                    "<p>Install it with <code>brew install graphviz</code> "
                    "(macOS) or <code>apt install graphviz</code> (Linux) "
                    "and run again.</p>"
                )
            else:
                ui.label("Unexpected error (this is a bug, please report it):") \
                    .classes("font-semibold bad-text")
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
                with panel_head("Pipeline result"):
                    # Badges come with Quasar palette names
                    # (positive/negative/primary); they are mapped to the
                    # role tones so they do not come out in the raw Quasar colours.
                    with ui.row().classes("items-center gap-3 no-wrap"):
                        for text, color in out.badges:
                            tone = {"positive": "ok", "negative": "bad"}.get(color, "info")
                            status(text, tone)
                # The numbers of the run as one line of text, not tiles.
                with ui.element("div").classes("w-full metrics mt-1"):
                    for value, label in out.stats:
                        ui.html(f"<b>{html.escape(str(value))}</b> <span>{html.escape(str(label))}</span>")

            # Step-by-step pipeline log: what was completed, what is missing
            # and what failed. It is shown first because it answers the
            # question people bring ("why didn't I get what I drew?") before
            # they start looking at the figures.
            if out.steps:
                with ui.card().classes(CARD).props(FLAT):
                    panel_head("Pipeline log")
                    # One block per step: its name and a status word; under
                    # it, one line per entry with a short tag in the margin
                    # (added / note / failed / skipped). A log, not a chat.
                    STATUS = {"ok": ("as drawn", "var(--p-ok)"),
                              "completed": ("completed", "var(--p-ok)"),
                              "failed": ("failed", "var(--p-bad)"),
                              "skipped": ("skipped", "var(--p-muted)")}
                    for step in out.steps:
                        word, color = STATUS[step.status]
                        with ui.row().classes("w-full items-baseline gap-3 mt-3 no-wrap"):
                            ui.label(step.name).classes("font-semibold")
                            ui.label(word).classes("font-mono text-xs").style(f"color:{color}")
                        entries = ([("skipped", t, "muted") for t in step.skipped]
                                   + [("added", t, "ink") for t in step.completed]
                                   + [("note", t, "ink") for t in step.missing])
                        for tag, text, tone in entries:
                            with ui.row().classes("w-full no-wrap items-baseline gap-3 pl-4 mt-1"):
                                ui.label(tag).classes("font-mono text-xs muted w-14 shrink-0 text-right")
                                ui.label(text).classes("text-sm " + tone)
                        for text in step.failed:
                            with ui.row().classes("w-full no-wrap items-start gap-3 pl-4 mt-1"):
                                ui.label("failed").classes("font-mono text-xs w-14 shrink-0 text-right bad-text")
                                ui.html(f"<pre style='white-space:pre-wrap;margin:0' "
                                        f"class='text-xs'>{html.escape(text)}</pre>").classes("grow")

            # The pipeline figures, in order, as in thesis_example.py, plus
            # Fig. 4 (face lattice) added by adapters. A grid: tall figures
            # (Fig. 2a's column of copies, a triangle fan) share a row, wide
            # ones (the Hasse band) take it whole -- half the scrolling and
            # no figure floating in a sea of grey.
            with ui.card().classes(CARD).props(FLAT):
                with panel_head("Figures"):
                    # The figures on screen are drawn in the page's ink; what
                    # leaves the page is always black on white, as in the paper.
                    ui.button("Download PNG (light background)", icon="download",
                              on_click=lambda: self.download_figures()) \
                        .props("flat dense", remove="color").classes("link-btn")
                with ui.element("div").classes("w-full fig-grid"):
                    for caption, path in out.figures:
                        self.figure_card(caption, path)

            # The interactive 3D view is a complete plotly page: it is embedded
            # in an iframe instead of being rebuilt with components.
            if out.html_3d is not None:
                with ui.card().classes(CARD).props(FLAT):
                    panel_head("Interactive 3D view of the complex")
                    # The plotly page is light: it goes on the same sheet as
                    # the figures, on a plate, since it paints its own white.
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
                        .classes("text-xs italic muted")

            # A direct complex comes with its equivalent Kripke model (G_B):
            # one click opens it as an editable document, so the equivalence
            # can be walked in both directions inside the workspace.
            if getattr(out, "kripke_state", None):
                with ui.card().classes(CARD).props(FLAT):
                    with ui.row().classes("w-full items-center gap-3 no-wrap"):
                        ui.label("The equivalent Kripke model (Fig. 3) can be opened as a "
                                 "model of its own and sent back through the pipeline.") \
                            .classes("text-sm muted grow")
                        ui.button("Open as Kripke model", icon="open_in_new",
                                  on_click=lambda st=out.kripke_state: self.open_kripke(st)) \
                            .props("outline dense")

            # Text diagrams (visualize): the dependency-free view, collapsed
            # by default so it does not compete with the figures.
            with ui.expansion("Text diagrams").classes("w-full"):
                for caption, diagram in out.text_diagrams:
                    ui.label(caption).classes("font-semibold mt-2")
                    ui.html(f"<pre style='white-space:pre-wrap' "
                            f"class='text-xs'>{diagram}</pre>")

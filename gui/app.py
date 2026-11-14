"""Web GUI of the project (NiceGUI): build a model and run the full pipeline.

Run:  .venv/bin/python gui/app.py     (opens http://localhost:8080 in the browser)

WHY NICEGUI AND THIS SHAPE. The GUI is a single-user research tool, so the
stack chosen is the one that reuses EVERYTHING that already exists with the
fewest new pieces: NiceGUI is 100 % Python (the core modules are imported
directly, with no API and no serialization), it runs in the browser (the 3D
plotly figures are already HTML and are embedded as they are), and a single
page is enough.

VISUAL SYSTEM. An instrument, not a dashboard (2026-11-13, "aurora"; it
replaced the espresso-and-cyan desk, which in turn had replaced a
navy-and-lime template). Navy page, flat navy panels with hairlines and
square corners, one vibrant violet, three aurora hues for status.

    * Background: navy (``POSTER["page"]``); panels are a lighter navy with
      a hairline border; no shadows, no gradients, no glows, no animation.
      The live preview is told apart by a thin violet rule on top.
    * Figures are rendered TRANSPARENT and in the DARK ink theme
      (``adapters.base.show`` wraps every render in
      ``visualization.ink_theme("dark")``: light text, outlines and pads,
      agent colours unchanged), so they sit straight on the navy panels,
      one per row, a serif caption below ("Figure 2a. Proper model, ...")
      and a hairline before the next. The 3-D Plotly page paints the same
      navy. The CLI scripts and the paper keep the black-on-white ink.
    * Typography: IBM Plex Sans for the interface, IBM Plex Mono for
      formulas, diagrams, the run's numbers and the provenance lines, Source
      Serif 4 for the title and the captions. Panel titles are short sentence-case labels in
      muted ink; buttons and tabs are sentence case.
    * Color: violet for the Run button, the active document's underline,
      the active tab, the preview rule and the accent text (text buttons);
      what sits on a violet fill is navy (``POSTER["on_accent"]``). Verdicts
      are said in words with one small coloured dot (``theme.status``):
      green = valid / done, amber = to be completed, rose = rejected. Agents
      keep the same Okabe-Ito colours (a square swatch) in their chips as in
      the figures: that is data, not chrome.
    * Icons accompany words, never replace them: every tab, button and
      document carries a small Material glyph next to its label (the kind
      of a document, play for a run, the bin of a delete); the only
      icon-only controls are the "+" of an add field and the cross that
      closes a document. The run's numbers are a compact mono table, not
      tiles.
    * Header: a compact toolbar: the title in the serif, the theme toggle,
      the example library and the Run button; a wrapping
      flex row (CSS ``.poster-header``) so the controls drop below the title
      on narrow windows. A footer line in mono names the authors and the
      repository.
    * Two themes, dark (the default) and light, switched from the header
      without a reload: the chrome hangs from CSS variables under Quasar's
      body class, and the figures are redrawn in the matching ink
      (``Page.set_theme``). Figures that LEAVE the page -- the zip from the
      Figures panel, the figures of a saved workspace -- are always printed
      light on white as PNG (``adapters.print_light``).

SEVERAL MODELS AT ONCE. The page is a workspace: the MODELS BAR (under the
header) lists the open documents; one is active and is the one shown by the
editor, the preview and the results. Documents can be opened blank,
duplicated, renamed and closed, and COMPARED 2 to 4 side by side (their
results are stored per document and only the ones that changed are
recomputed). A document can be READ-ONLY with an annotated origin: this is
how the results of applying action models will come in (``new_doc`` is the
hook; the state API lives in ``adapters/states.py``).

HOW MODELS ARE ENTERED. Everything is interactive and propagates in a chain:

    * The MODEL KIND (selector above the editor) chooses what the core
      builds: knowledge and belief (KnowledgeBeliefFrame, full pipeline),
      knowledge only (RelationalFrame S5, full pipeline with S_a = S) or
      belief only (RelationalFrame KD45/K45: no properness and no simplicial
      translation, the pipeline stops at step 1 and says so). The editor
      rows change meaning with it, and the switches that do not apply are
      disabled (``sync_switches``).
      A fourth kind, DIRECT SIMPLICIAL COMPLEX, does not go through Kripke:
      named vertices are declared per agent, plus facets (one vertex of each
      agent, plus the S_a that contain it), atoms go on vertices and the
      "pipeline" only validates and draws (complex, 3D and Hasse). On first
      entry it starts from the translation of the model drawn so far.

    * AGENTS and WORLDS are added by typing ANY name in their field and
      pressing Enter (or the + button); each one appears as a removable
      chip. Field + button was chosen over the "new values" mode of the
      Quasar select because the latter requires an Enter at exactly the
      right moment and fails silently -- the opposite of what an "add"
      control should do.
    * Per agent, its KNOWLEDGE CLASSES are drawn (chips with the
      indistinguishable worlds) and, inside each class, the WORLDS IT
      BELIEVES (select restricted to that class): invalid entries are
      *inexpressible*. Worlds outside every class remain singleton classes;
      an empty belief means "believes what it knows" (KD45) or defunct
      belief (K45).
    * ATOMS declare the valuation v (in which worlds each one is true); with
      atoms, the figures label worlds/vertices with their literals and the
      FORMULA EVALUATOR (K_a, B_a, ¬ & | ->) is enabled.
    * A LIVE PREVIEW draws the model EXACTLY AS ENTERED on every change,
      without closures; its validity chip summarizes what is missing. The
      pipeline runs only on request, with a spinner and a locked button (the
      heavy work goes through run.io_bound so the interface does not freeze).
    * The EXAMPLE LIBRARY (header) loads complete editor states.

WHAT IS IN THIS FILE -- the layout and the wiring, nothing else. The visual
system lives in ``gui/theme.py``, the bookkeeping of open documents in
``gui/workspace.py`` (tested without a browser) and each region of the page
in ``gui/views/`` (see that package's docstring for the map). All the logic
lives in the ``gui/adapters/`` package (one module per concern, see its
``__init__``); the views consume it and show already-flattened
results (file paths and strings). That boundary keeps the core untouched.

HOW FIGURES ARE SHOWN. ``visualization.show`` writes SVG/HTML into
``outputs/``; that folder is served as static files and every URL carries
``?v=<mtime>`` as a cache buster, because a run overwrites its own file names.
"""

from __future__ import annotations

import logging
import time
import traceback
from pathlib import Path

from nicegui import Client, app, ui

# Flat imports on purpose: when running ``python gui/app.py`` this folder is
# sys.path[0], and adapters takes care of putting the repo root on the path.
# When the GUI is started through the installed command (``gui.app:main``),
# this folder is not on the path yet, so it is added here first.
import sys

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from adapters import OUTPUTS, blank_state  # noqa: E402
from theme import apply_theme
from views.actions import ActionsView
from views.atoms import AtomsView
from views.compare import CompareView
from views.docs_bar import DocsBarView
from views.editor import EditorView
from views.formulas import FormulasView
from views.header import HeaderView
from views.page import Page
from views.preview import PreviewView
from views.results import ResultsView
from views.simplicial_editor import SimplicialEditorView

# Generated figures are served straight from outputs/ -- the GUI neither copies
# nor manages files of its own; it shares the artifacts with the CLI scripts.
OUTPUTS.mkdir(exist_ok=True)
app.add_static_files("/outputs", str(OUTPUTS))


# --------------------------------------------------------------------------- #
# CRASHES ARE SHOWN, NOT ONLY LOGGED. An exception in a button handler, a
# timer or a background task leaves NiceGUI's page as it was and prints the
# traceback to the terminal, where nobody looks while using the browser (that
# is how a refused preview passed for "the GUI crashed", GitHub #23). Every
# unhandled exception is therefore reported to every open tab as a red
# notification that stays until closed: where it happened and what it said.
# Two hooks, because NiceGUI has two paths: ``app.on_exception`` sees the
# exceptions it handles itself, and the logging handler sees the ones it can
# only log (a handler whose own slot is already gone, for instance). An
# exception reported through the first is not repeated by the second.
# --------------------------------------------------------------------------- #
_reported: dict = {}


def _root_cause(exc: BaseException) -> BaseException:
    """The first exception of a chain: a failure while handling a failure
    (NiceGUI reporting on a slot that is already gone, say) must name the
    original one, not the reporting accident."""
    seen = set()
    while (exc.__cause__ or exc.__context__) is not None and id(exc) not in seen:
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return exc


def _crash_text(exc: BaseException) -> str:
    """One line: the innermost frame of our own code, the type and the message."""
    exc = _root_cause(exc)
    frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    ours = [f for f in frames if "site-packages" not in f.filename] or frames
    place = f" in {Path(ours[-1].filename).name}:{ours[-1].lineno} ({ours[-1].name})" if ours else ""
    msg = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return (f"Internal error{place} · {type(exc).__name__}: {msg} "
            "· the terminal has the full traceback")


def _show_crash(exc: BaseException) -> None:
    now = time.monotonic()
    for key, when in list(_reported.items()):
        if now - when > 5:
            del _reported[key]
    if id(exc) in _reported:
        return
    _reported[id(exc)] = now
    text = _crash_text(exc)
    for client in list(Client.instances.values()):
        if not client.has_socket_connection:
            continue
        with client:
            ui.notify(text, type="negative", position="top", multi_line=True,
                      close_button=True, timeout=0)


app.on_exception(_show_crash)


class _CrashLogHandler(logging.Handler):
    """Backstop: whatever NiceGUI logs with a traceback is shown too."""

    def emit(self, record: logging.LogRecord) -> None:
        exc = record.exc_info[1] if record.exc_info else None
        if exc is not None:
            try:
                _show_crash(exc)
            except Exception:       # a reporting failure must never loop
                pass


_log = logging.getLogger("nicegui")
if not _log.handlers and not logging.getLogger().handlers:
    # Attaching a handler switches off Python's last-resort printing, which is
    # what put the tracebacks on the terminal until now: keep that output.
    _log.addHandler(logging.StreamHandler())
_log.addHandler(_CrashLogHandler())


# --------------------------------------------------------------------------- #
# Single page. @ui.page is the NiceGUI 3 pattern: the function runs ONCE PER
# CLIENT when the route is visited, and all the state lives in that client's
# Page object -- every browser tab has its own workspace.
# --------------------------------------------------------------------------- #
@ui.page("/")
def index() -> None:
    # The theme is remembered across sessions (app.storage.general is the
    # server's own store, no secret needed; this is a single-user tool).
    theme = app.storage.general.get("theme", "dark")
    if theme not in ("dark", "light"):
        theme = "dark"
    page = Page()
    page.theme = theme
    page.dark = apply_theme(theme)
    page.header = HeaderView(page)
    page.docs_bar = DocsBarView(page)
    page.editor = EditorView(page)
    page.simplicial = SimplicialEditorView(page)
    page.atoms = AtomsView(page)
    page.formulas = FormulasView(page)
    page.actions = ActionsView(page)
    page.preview = PreviewView(page)
    page.results = ResultsView(page)
    page.compare = CompareView(page)

    page.header.build()
    page.docs_bar.build()

    # Two columns side by side; below 1000px the CSS (.editor-row) lets them
    # wrap, so the editor takes the full width and the results follow under
    # it instead of being squeezed into a 200px strip.
    with ui.row().classes("w-full items-start gap-4 p-4 editor-row") as page.editor_row:

        # ---- Editing panel: sticky with its own scroll (thin scrollbar) ---- #
        # Four TABS -- Model · Atoms · Formulas · Actions -- instead of one
        # 1900px stack of cards: what is edited most (the model) is always at
        # hand, and atoms, formulas and actions are one click away.
        with ui.column().classes(
            "editor-col w-[440px] shrink-0 gap-4 sticky top-2 self-start "
            "max-h-[calc(100vh-150px)] overflow-y-auto pr-1 thin-scroll"
        ):
            with ui.tabs().classes("w-full").props(
                "dense no-caps align=justify indicator-color=primary "
                "active-color=secondary"
            ) as left_tabs:
                tab_model = ui.tab("modelo", label="Model", icon="tune")
                tab_atoms = ui.tab("atomos", label="Atoms", icon="label")
                tab_formulas = ui.tab("formulas", label="Formulas", icon="calculate")
                tab_actions = ui.tab("acciones", label="Actions", icon="bolt")
            # The panels are plain columns shown one at a time, NOT Quasar's
            # q-tab-panels: that component clips its content to a measured
            # height (overflow hidden), so a long editor -- the direct
            # complex with its vertex and facet cards -- was cut off at the
            # bottom and the column could not scroll to the rest.
            panels = {}
            for tab in (tab_model, tab_atoms, tab_formulas, tab_actions):
                panels[tab] = ui.column().classes("w-full gap-4")
            with panels[tab_model]:
                page.editor.build()
            with panels[tab_atoms]:
                page.atoms.build()
            with panels[tab_formulas]:
                page.formulas.build()
            with panels[tab_actions]:
                page.actions.build()

            def show_tab(name: str) -> None:
                for tab, panel in panels.items():
                    panel.set_visibility(tab._props.get("name") == name)

            left_tabs.on_value_change(lambda e: show_tab(e.value))
            show_tab("modelo")

        # ---- Preview and results column ------------------------------------ #
        with ui.column().classes("grow min-w-0 gap-4"):
            # Read-only notice (derived documents), then the live preview, the
            # "results are stale" strip and the pipeline output.
            page.readonly_box = ui.column().classes("w-full")
            page.preview.build()
            page.results.build()

    # ---- Comparison: 2 to 4 models side by side, full width ---------------- #
    page.compare.build()

    # ---- Footer: provenance, like the status bar of a tool ------------------ #
    footer()

    # First paint: the thesis example with its preview, and the empty state in
    # the results area.
    page.ws.active = page.ws.new_doc("Model 1", blank_state())["id"]
    page.load_example("tesis")   # also paints the bar, the preview and the empty state


def footer() -> None:
    """One mono line at the end of the page: the authors and the repository."""
    with ui.element("div").classes("w-full px-4 py-2 mt-2 poster-footer"):
        ui.label("Natalia Mejía and Philip Sink")
        ui.link("SimulationsBelief", "https://github.com/Meijix/SimulationsBelief",
                new_tab=True)


def main() -> None:
    """Start the server (the ``simulationsbelief-gui`` command and ``python gui/app.py``).

    reload=False: NiceGUI's auto-reload re-imports the module in a subprocess,
    a surprising behavior for a simple local tool. The port can be changed
    with the environment variable ``SIMULATIONSBELIEF_PORT`` (default 8080).
    """
    import os

    port = int(os.environ.get("SIMULATIONSBELIEF_PORT", "8080"))
    ui.run(title="The geometry of a false belief", reload=False, dark=True, port=port)


# The __mp_main__ guard is the NiceGUI convention (multiprocess uvicorn).
if __name__ in {"__main__", "__mp_main__"}:
    main()

"""Web GUI of the project (NiceGUI): build a model and run the full pipeline.

Run:  .venv/bin/python gui/app.py     (opens http://localhost:8080 in the browser)

WHY NICEGUI AND THIS SHAPE. The GUI is a single-user research tool, so the
stack chosen is the one that reuses EVERYTHING that already exists with the
fewest new pieces: NiceGUI is 100 % Python (the core modules are imported
directly, with no API and no serialization), it runs in the browser (the 3D
plotly figures are already HTML and are embedded as they are), and a single
page is enough.

VISUAL SYSTEM. Navy and lime, nothing decorative: the palette comes from the
project poster ("La geometría de una creencia falsa… y por qué importa",
Coloquio de Lenguajes, UNAM 2026), the drawings do not (2026-10-11: the star
field, the rainbow rings and the seal were removed so that the only things
on screen are data and controls).

    * Background: plain near-black navy (``POSTER["page"]``). Surfaces
      (cards, header) are a slightly lighter navy with a translucent white
      border; there are NO grey shadows, the only "elevation" is the
      lime-green halo of the preview (the live element).
    * Typography: Inter for the interface, JetBrains Mono for formulas and
      diagrams (Google Fonts). Three fixed levels: the card EYEBROW in muted
      slate small caps with wide tracking (``_card_title``), content in
      white/light grey, and text-xs grey notes.
    * Color: ONE accent, the poster's LIME GREEN, for everything that is
      action or good news -- the "Correr pipeline" button, the rule under
      the header, the preview halo, "válido", what a closure completed. Two
      status hues besides it (``POSTER``): amber = to be completed / stale,
      rose = rejected / error. Anything that is a label rather than a
      verdict (the logic, "propio", information) is slate. Each agent keeps
      in its chips the SAME Okabe-Ito color as its edges in the figures
      (``agent_color_map``): that is data, not chrome, and the thread between
      editor and results does not change.
    * Header: a wrapping flex row (CSS ``.poster-header``): title block on
      the left, controls on the right; on narrow windows the tagline hides
      first and then the controls drop below the title, never overlapping.
    * Figures: each one on a light "sheet" (the Graphviz PNGs have a white
      background) with an italic caption below, paper-figure style, limited
      in height and expandable to full screen with one click (lightbox).
    * Run metrics as stat tiles (big number + label), not as a text log.

SEVERAL MODELS AT ONCE. The page is a workspace: the MODELS BAR (under the
header) lists the open documents; one is active and is the one shown by the
editor, the preview and the results. Documents can be opened blank,
duplicated, renamed and closed, and COMPARED 2 to 4 side by side (their
results are stored per document and only the ones that changed are
recomputed). A document can be READ-ONLY with an annotated origin: this is
how the results of applying action models will come in (``new_doc`` is the
hook; the state API lives in ``adapters.py``).

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
lives in ``gui/adapters.py``; the views consume it and show already-flattened
results (file paths and strings). That boundary keeps the core untouched.

HOW FIGURES ARE SHOWN. ``visualization.show`` writes SVG/HTML into
``outputs/``; that folder is served as static files and every URL carries
``?v=<mtime>`` as a cache buster, because a run overwrites its own file names.
"""

from __future__ import annotations

from nicegui import app, ui

# Flat imports on purpose: when running ``python gui/app.py`` this folder is
# sys.path[0], and adapters takes care of putting the repo root on the path.
from adapters import OUTPUTS, blank_state
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
# Single page. @ui.page is the NiceGUI 3 pattern: the function runs ONCE PER
# CLIENT when the route is visited, and all the state lives in that client's
# Page object -- every browser tab has its own workspace.
# --------------------------------------------------------------------------- #
@ui.page("/")
def index() -> None:
    apply_theme()
    page = Page()
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
        # Four TABS -- Modelo · Átomos · Fórmulas · Acciones -- instead of one
        # 1900px stack of cards: what is edited most (the model) is always at
        # hand, and atoms, formulas and actions are one click away.
        with ui.column().classes(
            "editor-col w-[440px] shrink-0 gap-4 sticky top-2 self-start "
            "max-h-[calc(100vh-150px)] overflow-y-auto pr-1 thin-scroll"
        ):
            with ui.tabs().classes("w-full").props(
                "dense no-caps align=justify indicator-color=primary "
                "active-color=primary"
            ) as left_tabs:
                tab_model = ui.tab("modelo", label="Modelo", icon="tune")
                tab_atoms = ui.tab("atomos", label="Átomos", icon="label")
                tab_formulas = ui.tab("formulas", label="Fórmulas", icon="calculate")
                tab_actions = ui.tab("acciones", label="Acciones", icon="bolt")
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

    # First paint: the thesis example with its preview, and the empty state in
    # the results area.
    page.ws.active = page.ws.new_doc("Modelo 1", blank_state())["id"]
    page.load_example("tesis")   # also paints the bar, the preview and the empty state


# reload=False: NiceGUI's auto-reload re-imports the module in a subprocess, a
# surprising behavior for a simple local tool. The __mp_main__ guard is the
# NiceGUI convention (multiprocess uvicorn).
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="La geometría de una creencia falsa", reload=False, dark=True)

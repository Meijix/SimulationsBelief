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

WHAT IS IN THIS FILE -- presentation only. All the logic lives in
``gui/adapters.py``; this file consumes it and shows already-flattened
results (file paths and strings). That boundary keeps the core untouched.

HOW FIGURES ARE SHOWN. ``visualization.show`` writes PNG/HTML into
``outputs/``; that folder is served as static files and every URL carries
``?v=<mtime>`` as a cache buster, because every run overwrites the same file
names.
"""

from __future__ import annotations

import copy
import html
import shutil
import traceback

from nicegui import app, run as io, ui

# Flat import on purpose: when running ``python gui/app.py`` this folder is
# sys.path[0], and adapters takes care of putting the repo root on the path.
from adapters import (
    EXAMPLES,
    KINDS,
    blank_state,
    evaluate_state,
    preview_state,
    run_state,
    state_from_example,
    state_problem,
    OUTPUTS,
    agent_color_map,
    evaluate_formula,
    evaluate_simplicial_formula,
    preview_figure,
    preview_simplicial,
    run_simplicial,
    maximal_facets,
    list_saved,
    load_workspace_full,
    save_workspace,
    workspace_payload,
    ACTION_EXAMPLES,
    ACTION_MODES,
    UPDATE_KINDS,
    action_node_names,
    action_problems,
    apply_action,
    blank_action,
    describe_action,
    simplicial_state_from_editor,
    run_pipeline_from_seeds,
    seeds_from_editor,
)

# Generated figures are served straight from outputs/ -- the GUI neither copies
# nor manages files of its own; it shares the artifacts with the CLI scripts.
OUTPUTS.mkdir(exist_ok=True)
app.add_static_files("/outputs", str(OUTPUTS))

# Poster palette. Picked by eye from the image: the six rainbow rings (from
# the outside in), the lime green of the rule/octahedron, the orange of the top
# line and the two navies (page and surface). Used both in the CSS below and in
# the role chips/icons.
POSTER = {
    "page": "#0a0e1f",      # page background (near-black navy)
    "surface": "#121833",   # cards and header
    "line": "rgba(255,255,255,.10)",  # card borders
    "lime": "#c9ee6b",      # THE accent: primary button, live halo, ok, completed
    "muted": "#9aa6c2",     # eyebrows and neutral chips (slate over navy)
    # Status hues, the only other colour the chrome uses: one for "to be
    # completed" and one for "rejected / error". Everything that is not a
    # status (KD45, propio, info) is neutral slate. Agents keep their own
    # Okabe-Ito colours in chips and figures: that is data, not chrome.
    "yellow": "#e8c35a",    # role: to be completed / stale / warning
    "pink": "#e5648f",      # role: rejected / error
    # Kept for callers that still name the old rainbow roles; all resolved to
    # the two-accent system above so no third hue sneaks back in.
    "green": "#c9ee6b", "cyan": "#c9ee6b", "blue": "#9aa6c2", "purple": "#9aa6c2",
    "orange": "#9aa6c2",
}

# Base class of ALL cards: flat, translucent border over navy and wide corners
# (the halo is reserved for the preview, see "VISUAL SYSTEM" above).
# ``poster-card`` is defined in HEAD_HTML.
CARD = "w-full rounded-xl poster-card"
FLAT = "flat"


# Fonts + the CSS that Tailwind/Quasar do not cover: the navy surfaces, the
# lime halo of the preview, the responsive header, the thin scrollbar and the
# pulsing dot. No drawings: the page carries nothing that is not data or UI.
HEAD_HTML = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --p-page: {POSTER["page"]}; --p-surface: {POSTER["surface"]};
    --p-line: {POSTER["line"]}; --p-lime: {POSTER["lime"]};
    --p-muted: {POSTER["muted"]}; --p-pink: {POSTER["pink"]};
  }}
  body {{ font-family: 'Inter', 'Roboto', sans-serif; }}
  .font-mono, pre, code {{ font-family: 'JetBrains Mono', 'Fira Mono', monospace; }}

  /* Plain navy page: a data tool's background says nothing. (The poster's
     star field was dropped: its dots read as noise next to the figures.) */
  body.body--dark {{ background: var(--p-page); }}

  /* Surfaces: navy with a translucent border; no shadow (flat). */
  .poster-card {{ background: var(--p-surface) !important; border: 1px solid var(--p-line); box-shadow: none !important; }}
  /* The live preview is the only elevated surface: a lime-green halo. */
  .poster-live {{ border-color: rgba(201,238,107,.45);
                  box-shadow: 0 0 0 1px rgba(201,238,107,.25), 0 10px 40px rgba(201,238,107,.10) !important; }}
  /* Core error / bug: pink tint (the "rejected" ring of the poster). */
  .poster-bad {{ background: rgba(236,75,138,.10) !important; border-color: rgba(236,75,138,.45); }}
  /* Light sheet behind the figures (Graphviz and matplotlib draw on white).
     The sheet hugs the figure (fit-content) instead of spanning the card: a
     narrow figure used to float in a wide grey rectangle. */
  .fig-frame {{ background: #f4f5f9; border-radius: .5rem; padding: .75rem;
                width: fit-content; max-width: 100%; margin: 0 auto; }}
  /* Figure grid of the results: tall figures share a row two by two, wide
     ones (the Hasse band, a flat strip of triangles) take the whole row. */
  .fig-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }}
  .fig-grid .fig-wide {{ grid-column: 1 / -1; }}
  @media (max-width: 1100px) {{ .fig-grid {{ grid-template-columns: minmax(0, 1fr); }} }}
  /* Card eyebrow: small caps in muted slate, so the only coloured things on a
     card are its status chips and the agents. */
  .eyebrow {{ color: var(--p-muted); font-size: .68rem; font-weight: 600;
              letter-spacing: .18em; text-transform: uppercase; }}
  /* Header: navy with a lime rule, nothing else. It is a wrapping flex row:
     the title block and the controls sit on one line when there is room and
     the controls drop to a second line below the title when there is not,
     instead of overlapping. NOTE: no ``position`` here on purpose (Quasar
     keeps it ``fixed``; ``relative`` duplicated its height as a gap). */
  .poster-header {{ background: var(--p-surface) !important; border-bottom: 2px solid var(--p-lime);
                    display: flex; flex-wrap: wrap; align-items: center;
                    column-gap: 1.5rem; row-gap: .5rem; min-height: 72px; }}
  .header-title {{ min-width: 0; flex: 1 1 320px; }}
  .header-title .q-item__label, .header-sub {{ overflow: hidden; text-overflow: ellipsis; }}
  .header-controls {{ margin-left: auto; display: flex; align-items: center; gap: .75rem;
                      flex-wrap: wrap; flex: 0 1 auto; min-width: 0; }}
  .header-example {{ width: 360px; max-width: calc(100vw - 3rem); }}
  @media (max-width: 1100px) {{
    .header-sub {{ display: none; }}            /* the tagline is the first thing to go */
    .header-example {{ width: 280px; }}
  }}
  @media (max-width: 720px) {{
    .header-controls {{ margin-left: 0; width: 100%; }}  /* controls on their own row */
    .header-example {{ flex: 1 1 200px; width: auto; }}
  }}
  /* Body: editor (fixed 440px, sticky) beside the results; on narrow windows
     the row wraps and the editor loses its stickiness and its own scroll,
     so the page is one normal column instead of two cramped ones. */
  .editor-row {{ flex-wrap: nowrap; }}
  @media (max-width: 1000px) {{
    .editor-row {{ flex-wrap: wrap; }}
    .editor-col {{ width: 100% !important; position: static !important;
                   max-height: none !important; overflow: visible !important; }}
  }}

  .thin-scroll::-webkit-scrollbar {{ width: 6px; }}
  .thin-scroll::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,.18); border-radius: 3px; }}
  .thin-scroll::-webkit-scrollbar-track {{ background: transparent; }}
  .pulse-dot {{ width: 8px; height: 8px; border-radius: 9999px; background: var(--p-lime);
               animation: pulse 2s infinite; }}
  @keyframes pulse {{
    0%   {{ box-shadow: 0 0 0 0 rgba(201,238,107,.6); }}
    70%  {{ box-shadow: 0 0 0 6px rgba(201,238,107,0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(201,238,107,0); }}
  }}
</style>
"""


# Help texts that depend on the model kind: in a direct complex the atoms live
# on the VERTICES (what each perspective observes) and formulas are evaluated
# facet by facet, with no closures in between.
_ATOMS_WORLDS = (
    "Declara cada átomo y en qué mundos es **verdadero**. Con átomos, las "
    "figuras etiquetan los mundos con sus literales y puedes evaluar fórmulas."
)
ATOMS_HELP = {
    "kb": _ATOMS_WORLDS, "knowledge": _ATOMS_WORLDS, "belief": _ATOMS_WORLDS,
    "simplicial": (
        "Los átomos se asignan a **vértices**: qué perspectivas lo observan "
        "verdadero y cuáles falso; las demás no lo saben. Una faceta satisface "
        "el átomo si algún vértice suyo lo observa verdadero."
    ),
}
_FORMULA_WORLDS = (
    "Sintaxis: átomos declarados, `K_a`, `B_a`, `~`/`¬`, `&`, `|`, `->`, "
    "`bot`, paréntesis. Se evalúa **mundo por mundo** sobre el modelo ya "
    "completado por las clausuras."
)
FORMULA_HELP = {
    "kb": _FORMULA_WORLDS, "knowledge": _FORMULA_WORLDS, "belief": _FORMULA_WORLDS,
    "simplicial": (
        "Sintaxis: átomos declarados, `K_a`, `B_a`, `~`/`¬`, `&`, `|`, `->`, "
        "`bot`, paréntesis. Se evalúa **faceta por faceta** con la semántica "
        "por vértices; el complejo debe ser válido."
    ),
}


def _url(path) -> str:
    """Static URL of a figure, with the mtime as cache buster (see module docstring)."""
    return f"/outputs/{path.name}?v={int(path.stat().st_mtime)}"


def _figure_size(path) -> tuple[float, float] | None:
    """``(width, height)`` of a figure file, from its header, without decoding it.

    SVG (Graphviz/matplotlib write ``width="…pt" height="…pt"`` on the root
    element) and PNG (the IHDR chunk) are enough for the figures this GUI
    produces. Used only to decide the layout: whether a figure is tall or
    wide. ``None`` when it cannot be told, which lays the figure out wide.
    """
    import re
    import struct

    try:
        with open(path, "rb") as fh:
            head = fh.read(2048)
    except OSError:
        return None
    if head.startswith(b"\x89PNG") and len(head) >= 24:
        w, h = struct.unpack(">II", head[16:24])
        return float(w), float(h)
    m = re.search(rb'<svg[^>]*?\swidth="([\d.]+)(?:pt|px)?"[^>]*?\sheight="([\d.]+)(?:pt|px)?"', head)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def _is_wide(path) -> bool:
    """A figure wider than 1.6 : 1 takes a whole row of the grid; others share one."""
    size = _figure_size(path)
    return size is None or size[1] == 0 or size[0] / size[1] > 1.6


def _figure_img(path) -> None:
    """An ``<img>`` that shrinks to its content inside the sheet.

    A plain img is used instead of ``ui.image``: q-img is a fixed-ratio box
    that, with ``fit=contain`` and full width, centered the figure in a 420px
    rectangle and left empty bands above/below or on the sides. With
    ``width/height:auto`` and only maximums, the sheet is exactly as big as
    the figure and the caption sits right below it.
    """
    ui.html(
        f'<img src="{_url(path)}" style="display:block;margin:0 auto;'
        'max-width:100%;max-height:520px;width:auto;height:auto">'
    ).classes("w-full")


def _card_title(text: str) -> None:
    """Card title of the visual system: muted small-caps eyebrow."""
    ui.label(text).classes("eyebrow")


# ROLE chips: translucent background of the tone and text in the same tone,
# readable over navy. Two accents only -- lime for "good / done", amber for
# "to be completed", rose for "rejected" -- and slate for anything that is a
# label rather than a verdict (the logic, "propio", information).
_TONES = {
    "ok": POSTER["green"], "warn": POSTER["yellow"],
    "bad": POSTER["pink"], "done": POSTER["cyan"], "info": POSTER["blue"],
}


def _tint(hex_color: str, alpha: float) -> str:
    """``#rrggbb`` -> ``rgba(r,g,b,alpha)``: translucent background of the same tone."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def _chip(text: str, tone: str, icon=None):
    """Status chip with a role tone (see ``_TONES``).

    The color goes through the ``color`` parameter (NiceGUI accepts CSS and
    applies it as a style) and not through ``.style()``: the ``bg-primary``
    that Quasar adds by default carries ``!important`` and would override
    any inline style.
    """
    c = _TONES[tone]
    return ui.chip(text, icon=icon, color=_tint(c, .18), text_color=c) \
        .classes("font-semibold")


# --------------------------------------------------------------------------- #
# Single page. @ui.page is the NiceGUI 3 pattern: the function runs ONCE PER
# CLIENT when the route is visited, and all the state lives as a local closure
# -- every browser tab has its own model being edited.
# --------------------------------------------------------------------------- #
@ui.page("/")
def index() -> None:
    # Visual identity (inside the page: NiceGUI 3 forbids UI in global scope
    # when @ui.page is used).
    # Quasar dark mode (inputs, selects, dialogs and notifications pick up the
    # theme on their own); the palette maps the roles to the poster. ``dark``
    # and ``dark_page`` are the surface and page navies.
    ui.dark_mode().enable()
    ui.colors(
        primary=POSTER["lime"], secondary=POSTER["cyan"], accent=POSTER["pink"],
        dark=POSTER["surface"], dark_page=POSTER["page"],
        positive=POSTER["green"], negative=POSTER["pink"],
        warning=POSTER["yellow"], info=POSTER["blue"],
    )
    ui.add_head_html(HEAD_HTML)

    # The WHOLE drawn model lives in this flat dict (not in the widgets): the
    # widgets only PAINT it and the conversion to seeds is a pure function of
    # adapters. A single owner of the state avoids widget-to-widget
    # synchronization. It starts with the thesis example.
    state = blank_state()

    # WORKSPACE: several models open at once. Each "document" is a named
    # model; ``state`` is ALWAYS the one of the active document (the editors
    # mutate it as is) and the others keep their copy in ``doc["state"]``.
    # When switching documents the active one is saved and the other one is
    # poured into ``state`` -- so all the editor code keeps talking to a
    # single dict and does not know there are more models.
    #
    #   doc = {"id": "d3",            identifier; also tags output files
    #          "name": "...",         name shown in the models bar
    #          "state": {...},        the model (adapters.blank_state format)
    #          "outcome": {...}|None, result of the last run
    #          "dirty": bool,         the model changed since that run
    #          "readonly": bool,      derived result: not editable
    #          "origin": {...}|None}  where it came from (e.g. which action)
    docs: list = []
    ws = {"active": None, "next": 1, "loading": False,
          "comparing": False, "compare": [],
          # The action layer (GitHub #6/#13/#18): action specs are workspace-
          # level, not per model -- the same action is applied to several
          # models. ``action`` is the index of the one being edited.
          "actions": [], "action": None}

    def current() -> dict:
        """The active document."""
        return next(d for d in docs if d["id"] == ws["active"])

    def live_state() -> dict:
        """``state`` with the switches brought up to date (they live in the widgets)."""
        state["axiom_d"] = axiom_d_in.value
        state["silent_defunct"] = silent_defunct_in.value
        state["explicit"] = explicit_in.value
        state["hasse_full"] = hasse_full_in.value
        return state

    def new_doc(name: str, st: dict, readonly: bool = False,
                origin: dict | None = None) -> dict:
        """Open a new document (without activating it).

        HOOK FOR ACTION MODELS: the result of applying an action to a model
        is another state; adding it with ``readonly=True`` and an
        ``origin={"label": "action X on model Y"}`` is enough for it to show
        up in the bar, be runnable, evaluable and comparable, and offer
        "duplicate as new model" instead of direct editing.
        """
        doc = {"id": f"d{ws['next']}", "name": name, "state": copy.deepcopy(st),
               "outcome": None, "dirty": False, "readonly": readonly,
               "origin": origin}
        ws["next"] += 1
        docs.append(doc)
        # A freshly opened model joins the compare selection while it fits
        # (at most 4): one usually wants to see the opened ones together.
        if len(ws["compare"]) < 4:
            ws["compare"].append(doc["id"])
        return doc

    def load_into_editor(doc: dict) -> None:
        """Pour a document into ``state`` and the widgets, and paint everything."""
        # ``loading`` silences the widgets' on_change while values are
        # assigned: without it every assignment would repaint the preview
        # with a half-loaded state.
        ws["loading"] = True
        state.clear()
        state.update(copy.deepcopy(doc["state"]))
        kind_in.value = state["kind"]
        axiom_d_in.value = state["axiom_d"]
        silent_defunct_in.value = state["silent_defunct"]
        explicit_in.value = state["explicit"]
        hasse_full_in.value = state.get("hasse_full", False)
        name_in.value = doc["name"]
        ws["loading"] = False
        dirty = doc["dirty"]            # repainting is not editing
        sync_switches()
        apply_readonly(doc)
        repaint_all()
        doc["dirty"] = dirty
        refresh_stale()                 # with the real dirty flag, not the repaint's
        formula_out.clear()
        render_outcome(doc["outcome"], results)

    def activate(doc_id: str) -> None:
        """Switch documents, saving the one being left first."""
        if ws["comparing"]:
            exit_compare()
        if doc_id == ws["active"]:
            return
        current()["state"] = copy.deepcopy(live_state())
        ws["active"] = doc_id
        load_into_editor(current())
        paint_docs_bar()

    def add_blank() -> None:
        doc = new_doc(f"Modelo {ws['next']}", blank_state())
        activate(doc["id"])

    def duplicate_active() -> None:
        """Editable copy of the active document (the way out of read-only ones)."""
        doc = new_doc(f"{current()['name']} (copia)", live_state())
        activate(doc["id"])

    def close_doc(doc_id: str) -> None:
        if len(docs) <= 1:
            paint_docs_bar()
            return
        index = next(i for i, d in enumerate(docs) if d["id"] == doc_id)
        was_active = doc_id == ws["active"]
        docs.pop(index)
        ws["compare"] = [i for i in ws["compare"] if i != doc_id]
        if ws["comparing"]:
            exit_compare()
        if was_active:
            ws["active"] = docs[max(0, index - 1)]["id"]
            load_into_editor(current())
        paint_docs_bar()

    def rename_current() -> None:
        name = (name_in.value or "").strip()
        if name and name != current()["name"]:
            current()["name"] = name
            paint_docs_bar()

    def apply_readonly(doc: dict) -> None:
        """Lock editing of a derived document and explain why.

        The cards that change the model are locked (identifiers, editor,
        atoms); evaluating formulas, running and comparing stay active.
        """
        for element in (ident_card, editor_box, atoms_card):
            if doc["readonly"]:
                element.classes(add="pointer-events-none opacity-60")
            else:
                element.classes(remove="pointer-events-none opacity-60")
        readonly_box.clear()
        if not doc["readonly"]:
            return
        with readonly_box, ui.card().classes(CARD).props(FLAT):
            with ui.row().classes("w-full items-center gap-3 no-wrap"):
                ui.icon("lock").style(f"color:{POSTER['yellow']}")
                source = (doc["origin"] or {}).get("label")
                ui.label(
                    ("Resultado de " + source + ". " if source else "")
                    + "Este modelo es de sólo lectura: para cambiarlo, "
                      "duplícalo como modelo nuevo."
                ).classes("text-sm text-grey-4 grow")
                ui.button("Duplicar como modelo nuevo", icon="content_copy",
                          on_click=lambda: duplicate_active()) \
                    .props("outline dense")

    def load_example(key: str) -> None:
        """Load a library example INTO the active document."""
        doc = current()
        if doc["readonly"]:
            ui.notify("Este modelo es de sólo lectura: duplícalo o abre uno "
                      "nuevo para cargar un ejemplo.", type="warning")
            return
        doc["state"] = state_from_example(EXAMPLES[key])
        doc["name"] = EXAMPLES[key]["label"]
        doc["outcome"], doc["dirty"] = None, False
        load_into_editor(doc)
        paint_docs_bar()

    # ---- Save / open workspaces (GitHub #18) ------------------------------- #
    # Everything open (names, states, read-only flags, provenance) goes to
    # one JSON file in saved_models/; opening one adds its models to the bar
    # or replaces what is open. A single model can also be downloaded as a
    # one-model workspace, which is the unit to share or to hand to a script.
    def save_dialog() -> None:
        current()["state"] = copy.deepcopy(live_state())
        with ui.dialog() as dlg, ui.card().classes(CARD).props(FLAT):
            _card_title("Guardar espacio de trabajo")
            ui.label(f"{len(docs)} modelo(s) abiertos → saved_models/‹nombre›.json") \
                .classes("text-xs text-grey-5")
            name_box = ui.input("nombre", value=current()["name"] if len(docs) == 1
                                else f"espacio {ws['next'] - 1} modelos") \
                .props("dense outlined").classes("w-full")

            def do_save() -> None:
                try:
                    path = save_workspace(docs, name_box.value or "espacio", ws["actions"])
                except OSError as exc:
                    ui.notify(f"No se pudo guardar: {exc}", type="negative")
                    return
                ui.notify(f"Guardado: saved_models/{path.name}", type="positive")
                dlg.close()

            name_box.on("keydown.enter", lambda: do_save())
            with ui.row().classes("gap-2"):
                ui.button("Guardar", icon="save", on_click=do_save) \
                    .props("unelevated dense color=primary text-color=dark")
                ui.button("Cancelar", on_click=dlg.close).props("flat dense")
        dlg.open()

    def open_saved(path, replace: bool, dlg=None) -> None:
        """Open a saved workspace, adding to the bar or replacing it."""
        try:
            loaded, actions = load_workspace_full(path)
        except (OSError, ValueError) as exc:
            ui.notify(str(exc), type="warning")
            return
        if dlg is not None:
            dlg.close()
        if ws["comparing"]:
            exit_compare()
        if replace:
            docs.clear()
            ws["compare"] = []
            ws["actions"] = actions
        else:
            current()["state"] = copy.deepcopy(live_state())
            ws["actions"].extend(actions)
        ws["action"] = (len(ws["actions"]) - 1) if ws["actions"] else None
        first = None
        for d in loaded:
            doc = new_doc(d["name"], d["state"], readonly=d["readonly"], origin=d["origin"])
            first = first or doc
        ws["active"] = first["id"]
        load_into_editor(current())
        paint_docs_bar()
        ui.notify(f"{len(loaded)} modelo(s) abiertos de {path.name}", type="info")

    def open_dialog() -> None:
        saved = list_saved()
        with ui.dialog() as dlg, ui.card().classes(CARD + " min-w-[520px]").props(FLAT):
            _card_title("Abrir espacio de trabajo")
            if not saved:
                ui.label("No hay espacios guardados todavía (saved_models/ está vacío).") \
                    .classes("text-sm text-grey-5")
            for path in saved:
                try:
                    models, acts = load_workspace_full(path)
                    detail = f"{len(models)} modelo(s)" + (f", {len(acts)} acción(es)" if acts else "")
                except (OSError, ValueError):
                    detail = "archivo no legible"
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.icon("folder").classes("text-grey-5")
                    with ui.column().classes("gap-0 grow min-w-0"):
                        ui.label(path.stem).classes("text-sm text-white")
                        ui.label(detail).classes("text-xs text-grey-5")
                    ui.button("añadir", on_click=lambda _, p=path: open_saved(p, False, dlg)) \
                        .props("outline dense").tooltip("Abrir junto a los modelos actuales")
                    ui.button("sustituir", on_click=lambda _, p=path: open_saved(p, True, dlg)) \
                        .props("flat dense").tooltip("Cerrar los actuales y abrir estos")
            ui.button("Cerrar", on_click=dlg.close).props("flat dense")
        dlg.open()

    def export_active() -> None:
        """Download the active model as a one-model workspace file."""
        import json

        current()["state"] = copy.deepcopy(live_state())
        payload = workspace_payload([current()], ws["actions"])
        data = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
        ui.download.content(data, f"{current()['name']}.json")

    # ---- Lightbox: any figure, full screen with one click ------------------ #
    with ui.dialog().props("maximized") as lightbox:
        with ui.column().classes(
            "w-full h-full items-center justify-center bg-black cursor-zoom-out"
        ) as lb_body:
            lb_img = ui.image().classes("max-w-[92vw] max-h-[86vh]") \
                .props("fit=contain")
            lb_cap = ui.label().classes("text-white text-sm italic mt-2")
        lb_body.on("click", lightbox.close)

    def open_lightbox(path, caption: str) -> None:
        lb_img.set_source(_url(path))
        lb_cap.set_text(caption)
        lightbox.open()

    def figure_card(caption: str, path, span: bool = False) -> None:
        """Paper-style figure: grey frame, italic caption, click to enlarge.

        ``span`` marks a wide figure inside a ``.fig-grid``: it takes the
        whole row while tall ones sit two by two (see the CSS).
        """
        with ui.card().classes(CARD + (" fig-wide" if span else "")).props(FLAT):
            holder = ui.element("div").classes(
                "w-full fig-frame cursor-zoom-in"
            )
            with holder:
                _figure_img(path)
            holder.on("click", lambda p=path, c=caption: open_lightbox(p, c))
            ui.label(caption).classes("text-xs italic text-grey-5 mt-2")

    # ---- Header: title on the left, controls on the right, nothing else -- #
    # The layout is the CSS of .poster-header (a wrapping flex row), so the
    # controls move below the title on narrow windows instead of overlapping;
    # wrap=True lets Quasar size the header to its wrapped height.
    with ui.header(wrap=True).classes("poster-header text-white px-6 py-3 shadow-none"):
        with ui.column().classes("gap-0 header-title"):
            ui.label("La geometría de una creencia falsa") \
                .classes("text-xl font-extrabold text-white leading-tight")
            ui.label("Una herramienta para construir, validar y traducir "
                     "modelos de lógica epistémica · pipeline general → "
                     "propio → simplicial") \
                .classes("text-xs italic text-grey-4 header-sub")
        with ui.element("div").classes("header-controls"):
            ui.select(
                {k: ex["label"] for k, ex in EXAMPLES.items()},
                value=None, label="cargar ejemplo",
                on_change=lambda e: load_example(e.value),
            ).props("dense outlined options-dense").classes("header-example")
            # Lime with navy text: the only filled button on the page.
            run_btn = ui.button("Correr pipeline", icon="play_arrow",
                                on_click=lambda: run_clicked()) \
                .props("color=primary text-color=dark unelevated") \
                .classes("font-bold")

    # ---- Models bar: the open documents and the comparison ---------------- #
    docs_bar = ui.row().classes("w-full items-center gap-2 px-4 pt-3")

    # Two columns side by side; below 1000px the CSS (.editor-row) lets them
    # wrap, so the editor takes the full width and the results follow under
    # it instead of being squeezed into a 200px strip.
    with ui.row().classes("w-full items-start gap-4 p-4 editor-row") as editor_row:

        # ---- Editing panel: sticky with its own scroll (thin scrollbar) ---- #
        with ui.column().classes(
            "editor-col w-[440px] shrink-0 gap-4 sticky top-2 self-start "
            "max-h-[calc(100vh-150px)] overflow-y-auto pr-1 thin-scroll"
        ):
            # The panel is four TABS -- Modelo · Átomos · Fórmulas · Acciones --
            # instead of one 1900px stack of cards: what is edited most (the
            # model) is always at hand, and atoms, formulas and actions are
            # one click away without scrolling. Help paragraphs became
            # tooltips on the switches, and the two drawing switches live
            # under a collapsed "Opciones de dibujo".
            with ui.tabs().classes("w-full").props(
                "dense no-caps align=justify indicator-color=primary "
                "active-color=primary"
            ) as left_tabs:
                tab_model = ui.tab("modelo", label="Modelo", icon="tune")
                tab_atoms = ui.tab("atomos", label="Átomos", icon="label")
                tab_formulas = ui.tab("formulas", label="Fórmulas", icon="calculate")
                tab_actions = ui.tab("acciones", label="Acciones", icon="bolt")
            # Quasar paints the panels on an opaque surface with padding; both
            # are undone so the cards sit on the navy page like before.
            with ui.tab_panels(left_tabs, value=tab_model).classes("w-full") \
                    .style("background:transparent"):
                with ui.tab_panel(tab_model).style("padding:0"), \
                        ui.column().classes("w-full gap-4"):
                    # ---- Identifiers ------------------------------------------ #
                    with ui.card().classes(CARD).props(FLAT) as ident_card:
                        _card_title("Agentes y mundos")
                        # Document name: the one shown in the models bar and in
                        # the comparison panels.
                        name_in = ui.input("nombre del modelo") \
                            .props("dense outlined").classes("w-full")
                        name_in.on("blur", lambda: rename_current())
                        name_in.on("keydown.enter", lambda: rename_current())
                        # The core's model kinds. Changing it repaints the editor
                        # (the rows change meaning), adjusts which switches apply
                        # and redraws the preview.
                        kind_in = ui.select(
                            KINDS, value="kb", label="tipo de modelo",
                            on_change=lambda e: set_kind(e.value),
                        ).props("dense outlined options-dense").classes("w-full")
                        with ui.row().classes("w-full no-wrap items-center gap-2"):
                            agent_input = ui.input("nuevo agente") \
                                .props("dense outlined").classes("grow")
                            ui.button(icon="add", on_click=lambda: add_agent()) \
                                .props("round dense")
                        agent_chips = ui.row().classes("w-full gap-2")
                        agent_input.on("keydown.enter", lambda: add_agent())

                        # Worlds go in their own container: a direct complex has
                        # no worlds (it has facets, declared in their own card),
                        # so for that kind the whole block is hidden.
                        with ui.column().classes("w-full gap-2") as worlds_box:
                            with ui.row().classes("w-full no-wrap items-center gap-2 mt-2"):
                                world_input = ui.input("nuevo mundo") \
                                    .props("dense outlined").classes("grow")
                                ui.button(icon="add", on_click=lambda: add_world()) \
                                    .props("round dense")
                            world_chips = ui.row().classes("w-full gap-2")
                            world_input.on("keydown.enter", lambda: add_world())

                        # The core's KD45/K45 switch (axiom_d), exposed as is:
                        # turning it off legalizes defunct beliefs (Q_a(w) = ∅).
                        axiom_d_in = ui.switch("Axioma D (KD45; apagado = K45)",
                                               value=True).tooltip(
                            "KD45 exige que todo agente crea algo en cada mundo "
                            "(seriedad). Apagado (K45) una creencia vacía es legal: "
                            "ahí el agente cree todo, ⊥ incluido.")

                        # Turning Axiom D off only LEGALIZES defunct belief; it
                        # does not produce it. The project convention is that
                        # silence about belief means "believe exactly what you
                        # know" (Q = R), in both logics, and that defunct belief
                        # is an explicit opt-in. Without this box the opt-in did
                        # not exist in the GUI: K45 was indistinguishable from
                        # KD45 and B_a ⊥ was unreachable. It is global (so is
                        # the core flag): it affects EVERY class with no belief
                        # marked.
                        silent_defunct_in = ui.switch(
                            "Creencia vacía si no se marca nada (Q = ∅)", value=False,
                        ).tooltip(
                            "Sólo con K45. Apagada, una clase sin creencia marcada "
                            "cree lo que sabe (Q = R).")

                        def _reset_silent_defunct() -> None:
                            """KD45 forbids Q = ∅: going back to KD45 clears the box.

                            Leaving it checked but disabled would send the core a
                            combination it rejects, and the user would see a
                            validation error caused by a box they can no longer
                            see active.
                            """
                            if axiom_d_in.value:
                                silent_defunct_in.value = False

                        # Changing the logic repaints the preview: the "to be
                        # completed" list and the red worlds come from the frame's
                        # contract (KD45 demands seriality, K45 does not), so
                        # without a repaint the preview kept judging with the
                        # previous axiom.
                        axiom_d_in.on_value_change(lambda _: _reset_silent_defunct())
                        axiom_d_in.on_value_change(lambda _: sync_switches())
                        axiom_d_in.on_value_change(lambda _: update_preview())

                        # Drawing options, collapsed: they change figures, not
                        # the model, so they need not be in sight all the time.
                        with ui.expansion("Opciones de dibujo", icon="brush") \
                                .classes("w-full text-sm").props("dense"):
                            # The relational figures omit what the logic already
                            # implies: reflexive loops and the second arrow of
                            # each symmetric pair (S5 is drawn undirected). This
                            # switch draws them all, as they are in the relation:
                            # it is the way to SEE what the closures added. It
                            # repaints the preview at once and, if there are
                            # results already, reruns the pipeline so that
                            # Figures 1 and 2 agree.
                            explicit_in = ui.switch(
                                "Mostrar aristas implícitas (lazos y simetría)",
                                value=False, on_change=lambda _: explicit_changed(),
                            ).tooltip(
                                "Dibuja los lazos reflexivos y ambas direcciones de "
                                "cada par simétrico en vez de darlos por "
                                "sobreentendidos.")
                            # The lattice figure shows only vertices and facets
                            # by default (issue #7): perspectives below, worlds
                            # above. The full lattice, with every intermediate
                            # face, is optional: with three agents it is already
                            # hundreds of boxes. Since it only changes one figure
                            # of the result, touching it reruns the pipeline if
                            # there were results already.
                            hasse_full_in = ui.switch(
                                "Retículo de caras completo (todas las dimensiones)",
                                value=False, on_change=lambda _: hasse_full_changed(),
                            ).tooltip(
                                "Apagado, el diagrama de Hasse sólo dibuja las "
                                "perspectivas y los mundos, unidos cuando una es "
                                "parte del otro.")

                    # ---- Per-agent relation editor ---------------------------- #
                    editor_box = ui.column().classes("w-full gap-4")

                with ui.tab_panel(tab_atoms).style("padding:0"):
                    # ---- Atoms: the valuation v (where each atom is true) ----- #
                    with ui.card().classes(CARD).props(FLAT) as atoms_card:
                        _card_title("Átomos (proposiciones)")
                        atoms_help = ui.markdown(ATOMS_HELP["kb"]) \
                            .classes("text-xs text-grey-5")
                        with ui.row().classes("w-full no-wrap items-center gap-2"):
                            atom_input = ui.input("nuevo átomo") \
                                .props("dense outlined").classes("grow")
                            ui.button(icon="add", on_click=lambda: add_atom()) \
                                .props("round dense")
                        atom_input.on("keydown.enter", lambda: add_atom())
                        atoms_box = ui.column().classes("w-full gap-2")

                with ui.tab_panel(tab_formulas).style("padding:0"):
                    # ---- Formula evaluator ------------------------------------ #
                    with ui.card().classes(CARD).props(FLAT):
                        _card_title("Evaluar fórmula")
                        formula_input = ui.input(
                            "fórmula", placeholder="B_a p & ~K_a p",
                        ).props("dense outlined input-class=font-mono").classes("w-full")
                        formula_help = ui.markdown(FORMULA_HELP["kb"]) \
                            .classes("text-xs text-grey-5")
                        ui.button("Evaluar", icon="calculate",
                                  on_click=lambda: eval_formula()) \
                            .props("outline dense")
                        formula_input.on("keydown.enter", lambda: eval_formula())
                        formula_out = ui.column().classes("w-full gap-2")

                with ui.tab_panel(tab_actions).style("padding:0"):
                    # ---- Simplicial actions (GitHub #6/#13/#18) --------------- #
                    # Workspace-level card: actions are edited here and APPLIED
                    # to the active model; each result opens as a read-only
                    # document (drawn, evaluated, saved and compared like any
                    # other). The interface is complete; the products themselves
                    # are the action layer's: today only the knowledge product
                    # exists (simplicial_actions.update_model, spec-b), the
                    # belief/memory/revision ones are offered but PENDING
                    # (Taiba, #6/#15) -- see adapters.UPDATE_KINDS. Painted by
                    # paint_actions() from ws["actions"].
                    with ui.card().classes(CARD).props(FLAT):
                        _card_title("Acciones simpliciales")
                        actions_box = ui.column().classes("w-full gap-2")

        with ui.column().classes("grow min-w-0 gap-4"):
            # ---- Read-only notice (derived documents) ---------------------- #
            readonly_box = ui.column().classes("w-full")
            # ---- Live preview (always visible, on top) --------------------- #
            preview_box = ui.column().classes("w-full")
            # ---- "Results are stale" strip (shown once the model is edited
            #      after a run; see refresh_stale) ---------------------------- #
            stale_box = ui.column().classes("w-full")
            # ---- Pipeline output: rebuilt on every run --------------------- #
            results = ui.column().classes("w-full gap-4")

    # ---- Comparison: 2 to 4 models side by side, full width ---------------- #
    # It replaces the editor while open (the row above is hidden): four panels
    # do not fit next to a 440px editor.
    compare_box = ui.column().classes("w-full gap-4 p-4")
    compare_box.set_visibility(False)

    # ----------------------------------------------------------------------- #
    # Adding and removing identifiers and atoms. Every operation mutates
    # ``state`` and repaints chips + editor + atoms + preview; there is no
    # other synchronization.
    # ----------------------------------------------------------------------- #
    def sync_switches() -> None:
        """Which switches apply to the chosen model kind.

        Knowledge only: S5 is reflexive, hence serial: Axiom D decides
        nothing, nor does empty belief. Belief only: there is no class to
        fall back to, so "believes what it knows" does not exist (silence is
        invalid under KD45 and defunct under K45), and there are no implicit
        edges to show either: every loop and every direction is information.
        """
        kind = state["kind"]
        axiom_d_in.set_enabled(kind != "knowledge")
        silent_defunct_in.set_enabled(kind == "kb" and not axiom_d_in.value)
        # A complex has no edges to abbreviate; Axiom D does apply (it reads
        # "no isolated perspectives").
        explicit_in.set_enabled(kind not in ("belief", "simplicial"))
        # Belief only never reaches the complex, so there is no lattice to choose.
        hasse_full_in.set_enabled(kind != "belief")
        worlds_box.set_visibility(kind != "simplicial")
        atoms_help.set_content(ATOMS_HELP[kind])
        formula_help.set_content(FORMULA_HELP[kind])

    def set_kind(kind: str) -> None:
        """Change the model kind and repaint everything that depends on it."""
        if kind == state["kind"]:
            return
        previous = state["kind"]
        state["kind"] = kind
        if kind == "simplicial" and not state["facets"]:
            # Start-up: instead of an empty editor, the complex that results
            # from translating the model already drawn. From there it is
            # edited freely. If there is no translation (pure belief, invalid
            # model), it starts blank and says why.
            try:
                (state["vertices"], state["facets"],
                 state["vatoms"]) = simplicial_state_from_editor(
                    previous, state["agents"], state["worlds"],
                    state["per_agent"], state["atoms"], axiom_d_in.value,
                    not silent_defunct_in.value,
                )
                # A knowledge-only relational model translates to a knowledge
                # complex (S_a = S); anything else carries belief data.
                state["complex_kind"] = "knowledge" if previous == "knowledge" else "kb"
                ui.notify("Complejo inicial: la traducción del modelo que "
                          "estaba dibujado. Edítalo libremente.", type="info")
            except ValueError as exc:
                state["vertices"] = {a: [] for a in state["agents"]}
                ui.notify(f"Complejo en blanco ({str(exc).splitlines()[0]})",
                          type="warning")
        reset_results()
        if kind == "knowledge":
            # Marked beliefs make no sense without belief: they are dropped
            # so that the preview and the pipeline agree with what the
            # editor shows.
            for rows in state["per_agent"].values():
                for row in rows:
                    row["bel"] = []
        sync_switches()
        repaint_all()

    def paint_chips() -> None:
        # Every agent chip carries the SAME color as its edges in the figures
        # (agent_color_map replicates the rule of visualization).
        colors = agent_color_map(state["agents"])
        agent_chips.clear()
        with agent_chips:
            for name in state["agents"]:
                ui.chip(name, removable=True, icon="person",
                        color=colors[name], text_color="white",
                        on_value_change=lambda e, n=name: remove_agent(n))
        world_chips.clear()
        with world_chips:
            for name in state["worlds"]:
                ui.chip(name, removable=True, icon="public",
                        color="rgba(255,255,255,.14)", text_color="white",
                        on_value_change=lambda e, n=name: remove_world(n))

    def _take(input_widget) -> str:
        """Read and clear the add field, returning the typed name."""
        name = (input_widget.value or "").strip()
        input_widget.value = ""
        return name

    def add_agent() -> None:
        name = _take(agent_input)
        if not name:
            return
        if name in state["agents"]:
            ui.notify(f"el agente '{name}' ya existe", type="warning")
            return
        state["agents"].append(name)
        state["per_agent"].setdefault(name, [])
        repaint_all()

    def remove_agent(name: str) -> None:
        # Its rows are kept in per_agent in case the removal was a mistake;
        # since the agent is no longer listed, they are neither painted nor
        # turned into seeds.
        state["agents"].remove(name)
        repaint_all()

    def add_world() -> None:
        name = _take(world_input)
        if not name:
            return
        if name in state["worlds"]:
            ui.notify(f"el mundo '{name}' ya existe", type="warning")
            return
        state["worlds"].append(name)
        repaint_all()

    def remove_world(name: str) -> None:
        # A removed world IS pruned from classes, beliefs and atoms: leaving it
        # would produce edges or literals pointing at a nonexistent world.
        state["worlds"].remove(name)
        for rows in state["per_agent"].values():
            for row in rows:
                row["cls"] = [w for w in row["cls"] if w != name]
                row["bel"] = [w for w in row["bel"] if w != name]
        for atom, trues in state["atoms"].items():
            state["atoms"][atom] = [w for w in trues if w != name]
        repaint_all()

    def add_atom() -> None:
        name = _take(atom_input)
        if not name:
            return
        simplicial = state["kind"] == "simplicial"
        if name in (state["vatoms"] if simplicial else state["atoms"]):
            ui.notify(f"el átomo '{name}' ya existe", type="warning")
            return
        if simplicial:
            state["vatoms"][name] = {"true": [], "false": []}
        else:
            state["atoms"][name] = []
        paint_atoms()
        update_preview()

    def remove_atom(name: str) -> None:
        (state["vatoms"] if state["kind"] == "simplicial" else state["atoms"]).pop(name)
        paint_atoms()
        update_preview()

    def set_vatom(name: str, side: str, values: list) -> None:
        """Vertices that observe the atom true ("true") or false ("false")."""
        state["vatoms"][name][side] = values
        update_preview()

    def set_atom(name: str, trues: list) -> None:
        state["atoms"][name] = trues
        update_preview()

    def paint_atoms() -> None:
        atoms_box.clear()
        if state["kind"] == "simplicial":
            # Atoms on vertices: two selects per atom. A vertex in neither of
            # them "does not know" (value 2), which is the default case of
            # the vertex-based semantics.
            every = [v for a in state["agents"] for v in state["vertices"].get(a, [])]
            with atoms_box:
                for name, spec in state["vatoms"].items():
                    with ui.row().classes("w-full no-wrap items-center gap-2"):
                        ui.label(name).classes("font-mono w-10")
                        ui.select(
                            every, multiple=True, value=spec["true"],
                            label="lo observan verdadero",
                            on_change=lambda e, n=name: set_vatom(n, "true", e.value),
                        ).props("use-chips dense").classes("grow")
                        ui.select(
                            every, multiple=True, value=spec["false"],
                            label="lo observan falso",
                            on_change=lambda e, n=name: set_vatom(n, "false", e.value),
                        ).props("use-chips dense").classes("grow")
                        ui.button(
                            icon="delete",
                            on_click=lambda _, n=name: remove_atom(n),
                        ).props("flat dense color=grey")
            return
        with atoms_box:
            for name, trues in state["atoms"].items():
                with ui.row().classes("w-full no-wrap items-center gap-2"):
                    ui.label(name).classes("font-mono w-10")
                    ui.select(
                        state["worlds"], multiple=True, value=trues,
                        label="verdadero en",
                        on_change=lambda e, n=name: set_atom(n, e.value),
                    ).props("use-chips dense").classes("grow")
                    ui.button(
                        icon="delete",
                        on_click=lambda _, n=name: remove_atom(n),
                    ).props("flat dense color=grey")

    def repaint_all() -> None:
        paint_chips()
        paint_editor()
        paint_atoms()
        paint_actions()        # the event rows follow the active model's agents
        update_preview()

    # ----------------------------------------------------------------------- #
    # Per-agent editor. Deliberately simple strategy: any structural change
    # REPAINTS the whole editor from ``state`` and re-renders the preview. At
    # this scale (a few agents/worlds) both are almost instantaneous and they
    # remove all the bookkeeping of partial widgets.
    # ----------------------------------------------------------------------- #
    # ----------------------------------------------------------------------- #
    # Editor of the direct simplicial complex. Two cards: the vertices of each
    # agent (chips, like agents and worlds) and the facets, where each row
    # picks ONE vertex per agent -- so the UCF condition is the very shape of
    # the form -- and which agents have it in their belief subcomplex. Same
    # strategy as the other editor: every structural change repaints from
    # ``state``.
    # ----------------------------------------------------------------------- #
    def add_vertex(agent: str, widget) -> None:
        name = _take(widget)
        if not name:
            return
        if any(name in vs for vs in state["vertices"].values()):
            ui.notify(f"el vértice '{name}' ya existe", type="warning")
            return
        state["vertices"].setdefault(agent, []).append(name)
        repaint_all()

    def remove_vertex(agent: str, name: str) -> None:
        # Pruned from facets and atoms: a facet that used it is left without
        # a vertex of that agent and validation reports it as a UCF failure.
        state["vertices"][agent].remove(name)
        for facet in state["facets"]:
            if facet["nodes"].get(agent) == name:
                facet["nodes"][agent] = None
        for spec in state["vatoms"].values():
            spec["true"] = [v for v in spec["true"] if v != name]
            spec["false"] = [v for v in spec["false"] if v != name]
        repaint_all()

    def add_facet() -> None:
        taken = {f["name"] for f in state["facets"]}
        n = len(state["facets"]) + 1
        while f"F{n}" in taken:
            n += 1
        state["facets"].append({
            "name": f"F{n}",
            # Starts with the first vertex of each agent (or none) and in the
            # belief subcomplex of everyone: the most common case.
            "nodes": {a: (state["vertices"].get(a) or [None])[0]
                      for a in state["agents"]},
            "belief": list(state["agents"]),
        })
        repaint_all()

    def remove_facet(index: int) -> None:
        state["facets"].pop(index)
        repaint_all()

    def fill_maximal() -> None:
        """Add every consistent UCF facet the vertices can form (issue #21)."""
        try:
            state["facets"], added = maximal_facets(
                state["agents"], state["vertices"], state["vatoms"], state["facets"],
            )
        except ValueError as exc:
            ui.notify(str(exc).splitlines()[0], type="warning")
            return
        ui.notify(f"{added} faceta(s) añadida(s)" if added
                  else "ya estaban todas las facetas consistentes", type="info")
        if added:
            repaint_all()

    # ----------------------------------------------------------------------- #
    # Simplicial actions: editor + "apply to the active model". Same strategy
    # as the other editors (every structural change repaints from the spec).
    # The editor mirrors the complex editor on purpose: an event IS a facet of
    # action nodes (one per agent), pre/post ARE vertex atoms on those nodes,
    # so whoever can declare a complex can declare an action. PENDING pieces
    # (Taiba, #6/#15) are the belief/memory/revision products: the "tipo de
    # actualización" select lists them disabled, and apply_action refuses them
    # with a message until adapters.UPDATE_KINDS gets their functions.
    # ----------------------------------------------------------------------- #
    def selected_action() -> dict | None:
        i = ws["action"]
        return ws["actions"][i] if ws["actions"] and i is not None and i < len(ws["actions"]) else None

    def add_action() -> None:
        ws["actions"].append(blank_action(state["agents"], f"acción {len(ws['actions']) + 1}"))
        ws["action"] = len(ws["actions"]) - 1
        paint_actions()

    def remove_action(index: int) -> None:
        ws["actions"].pop(index)
        ws["action"] = (len(ws["actions"]) - 1) if ws["actions"] else None
        paint_actions()

    def select_action(index: int) -> None:
        ws["action"] = index
        paint_actions()

    def load_action_example(key: str) -> None:
        spec = copy.deepcopy(ACTION_EXAMPLES[key]["spec"])
        # The example names agents a/b; an action over other agents needs
        # its own nodes, so the isolated table is re-keyed to the model's.
        spec["isolated"] = {a: spec["isolated"].get(a, []) for a in state["agents"]}
        ws["actions"].append(spec)
        ws["action"] = len(ws["actions"]) - 1
        paint_actions()

    def add_event(spec: dict) -> None:
        taken = {e["name"] for e in spec["events"]}
        n = len(spec["events"]) + 1
        while f"e{n}" in taken:
            n += 1
        spec["events"].append({"name": f"e{n}", "nodes": {a: "" for a in state["agents"]}})
        paint_actions()

    def remove_event(spec: dict, index: int) -> None:
        spec["events"].pop(index)
        paint_actions()

    def add_isolated(spec: dict, agent: str, widget) -> None:
        name = _take(widget)
        if not name:
            return
        if name in action_node_names(spec):
            ui.notify(f"el nodo de acción '{name}' ya existe", type="warning")
            return
        spec.setdefault("isolated", {}).setdefault(agent, []).append(name)
        paint_actions()

    def remove_isolated(spec: dict, agent: str, name: str) -> None:
        spec["isolated"][agent].remove(name)
        paint_actions()

    def add_action_atom(spec: dict, widget) -> None:
        name = _take(widget)
        if not name:
            return
        for table in ("pre", "post"):
            spec.setdefault(table, {}).setdefault(name, {"true": [], "false": []})
        paint_actions()

    def remove_action_atom(spec: dict, name: str) -> None:
        for table in ("pre", "post"):
            spec.get(table, {}).pop(name, None)
        paint_actions()

    def apply_clicked() -> None:
        """Apply the selected action to the ACTIVE model; the result opens as a document."""
        spec = selected_action()
        if spec is None:
            ui.notify("Primero define (o carga) una acción.", type="warning")
            return
        problems = action_problems(spec, state["agents"])
        if problems:
            ui.notify("La acción no está completa: " + problems[0], type="warning")
            return
        try:
            doc_spec = apply_action(live_state(), spec, model_name=current()["name"])
        except NotImplementedError as exc:
            # PENDING product (Taiba): the interface is ready, the function is not.
            ui.notify(str(exc), type="warning", timeout=6000)
            return
        except ValueError as exc:
            ui.notify(str(exc).splitlines()[0], type="negative", timeout=6000)
            return
        current()["state"] = copy.deepcopy(live_state())
        doc = new_doc(doc_spec["name"], doc_spec["state"], readonly=True,
                      origin=doc_spec["origin"])
        activate(doc["id"])
        ui.notify(f"Resultado abierto como «{doc['name']}» (sólo lectura). "
                  "Compáralo con su modelo de entrada desde la barra.", type="positive")

    def paint_actions() -> None:
        actions_box.clear()
        agents = state["agents"]
        with actions_box:
            # The list: one chip per action, the selected one in lime.
            with ui.row().classes("w-full items-center gap-2"):
                for i, a in enumerate(ws["actions"]):
                    sel = i == ws["action"]
                    ui.chip(a.get("name") or f"acción {i + 1}", icon="bolt", removable=True,
                            color=POSTER["lime"] if sel else "rgba(255,255,255,.14)",
                            text_color=POSTER["surface"] if sel else "white",
                            on_click=lambda _, k=i: select_action(k),
                            on_value_change=lambda e, k=i: remove_action(k))
                ui.button(icon="add", on_click=lambda: add_action()) \
                    .props("round dense flat").tooltip("Acción nueva")
            ui.select({k: v["label"] for k, v in ACTION_EXAMPLES.items()}, value=None,
                      label="cargar acción de ejemplo",
                      on_change=lambda e: e.value and load_action_example(e.value)) \
                .props("dense outlined options-dense").classes("w-full")
            spec = selected_action()
            if spec is None:
                ui.label("Una acción es un complejo de EVENTOS: en cada evento, un nodo "
                         "de acción por agente; cada nodo puede exigir átomos "
                         "(precondición) y fijarlos (postcondición). Se aplica al "
                         "modelo activo y el resultado se abre como modelo nuevo."
                         ).classes("text-xs text-grey-5")
                return
            if not agents:
                ui.label("Agrega agentes al modelo activo: los eventos llevan un nodo "
                         "por agente.").classes("text-xs text-grey-5")
                return
            # ---- name, update kind, compatibility mode ---------------------- #
            ui.input("nombre de la acción", value=spec.get("name", ""),
                     on_change=lambda e: spec.__setitem__("name", e.value)) \
                .props("dense outlined").classes("w-full") \
                .on("blur", lambda: paint_actions())
            ui.select({k: v[0] for k, v in UPDATE_KINDS.items()},
                      value=spec.get("update", "knowledge"), label="tipo de actualización",
                      on_change=lambda e: spec.__setitem__("update", e.value)) \
                .props("dense outlined options-dense").classes("w-full")
            if UPDATE_KINDS[spec.get("update", "knowledge")][1] is None:
                ui.label("Pendiente: este producto aún no está implementado en el "
                         "núcleo (capa de acciones de Taiba). La acción se puede "
                         "definir y guardar; aplicarla avisará.") \
                    .classes("text-xs").style(f"color:{POSTER['yellow']}")
            ui.select(ACTION_MODES, value=int(spec.get("mode", 3)),
                      label="compatibilidad vértice / nodo de acción",
                      on_change=lambda e: spec.__setitem__("mode", int(e.value))) \
                .props("dense outlined options-dense").classes("w-full")
            # ---- events: one action node per agent (UCF, like facets) ------ #
            ui.label("Eventos (un nodo de acción por agente)").classes("eyebrow mt-1")
            colors = agent_color_map(agents)
            for i, ev in enumerate(spec["events"]):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.input("evento", value=ev["name"],
                             on_change=lambda e, v=ev: v.__setitem__("name", e.value)) \
                        .props("dense outlined").classes("w-24")
                    for agent in agents:
                        ui.input(agent, value=ev["nodes"].get(agent, ""),
                                 on_change=lambda e, v=ev, a=agent:
                                     v["nodes"].__setitem__(a, (e.value or "").strip())) \
                            .props("dense outlined").classes("grow min-w-[64px]") \
                            .style(f"border-bottom:2px solid {colors[agent]}") \
                            .on("blur", lambda: paint_actions())
                    ui.button(icon="delete", on_click=lambda _, k=i: remove_event(spec, k)) \
                        .props("flat dense color=grey")
            ui.button("añadir evento", icon="add", on_click=lambda: add_event(spec)) \
                .props("flat dense")
            # ---- isolated action nodes (in no event) ------------------------ #
            with ui.expansion("nodos de acción aislados (en ningún evento)") \
                    .classes("w-full text-xs"):
                for agent in agents:
                    with ui.row().classes("w-full no-wrap items-center gap-2"):
                        box = ui.input(f"nuevo nodo de {agent}").props("dense outlined") \
                            .classes("grow")
                        ui.button(icon="add", on_click=lambda _, a=agent, w=box:
                                  add_isolated(spec, a, w)).props("round dense")
                    with ui.row().classes("w-full gap-2"):
                        for name in spec.get("isolated", {}).get(agent, []):
                            ui.chip(name, removable=True, color=colors[agent],
                                    text_color="white",
                                    on_value_change=lambda e, a=agent, n=name:
                                        remove_isolated(spec, a, n))
            # ---- pre / post conditions: vertex atoms on action nodes -------- #
            ui.label("Precondiciones y postcondiciones (átomos sobre nodos de acción)") \
                .classes("eyebrow mt-1")
            nodes = action_node_names(spec)
            with ui.row().classes("w-full no-wrap items-center gap-2"):
                atom_box = ui.input("átomo (p. ej. uno del modelo)").props("dense outlined") \
                    .classes("grow")
                ui.button(icon="add", on_click=lambda: add_action_atom(spec, atom_box)) \
                    .props("round dense")
                atom_box.on("keydown.enter", lambda: add_action_atom(spec, atom_box))
            atoms = sorted(set(spec.get("pre", {})) | set(spec.get("post", {})))
            for atom in atoms:
                for table, label in (("pre", "exige"), ("post", "fija")):
                    cond = spec.setdefault(table, {}).setdefault(atom, {"true": [], "false": []})
                    with ui.row().classes("w-full no-wrap items-center gap-2"):
                        ui.label(f"{atom} · {label}").classes("font-mono text-xs w-20")
                        ui.select(nodes, multiple=True, value=cond["true"], label="verdadero",
                                  on_change=lambda e, c=cond: c.__setitem__("true", list(e.value))) \
                            .props("use-chips dense").classes("grow")
                        ui.select(nodes, multiple=True, value=cond["false"], label="falso",
                                  on_change=lambda e, c=cond: c.__setitem__("false", list(e.value))) \
                            .props("use-chips dense").classes("grow")
                        if table == "pre":
                            ui.button(icon="delete",
                                      on_click=lambda _, n=atom: remove_action_atom(spec, n)) \
                                .props("flat dense color=grey")
            # ---- status + apply --------------------------------------------- #
            problems = action_problems(spec, agents)
            if problems:
                ui.label("Falta: " + "; ".join(problems)).classes("text-xs") \
                    .style(f"color:{POSTER['yellow']}")
            else:
                ui.html("<pre style='white-space:pre-wrap' class='text-xs'>"
                        f"{html.escape(describe_action(spec, agents))}</pre>")
            with ui.row().classes("w-full items-center gap-2"):
                ui.button("Aplicar al modelo activo", icon="play_arrow",
                          on_click=lambda: apply_clicked()) \
                    .props("unelevated dense color=primary text-color=dark")
                ui.label("El resultado se abre como modelo de sólo lectura; "
                         "compáralo con su entrada.").classes("text-xs text-grey-5")

    def set_facet(facet: dict, key: str, value, agent: str | None = None) -> None:
        if agent is None:
            facet[key] = value
        else:
            facet[key][agent] = value
        update_preview()

    def set_complex_kind(value: str) -> None:
        """Knowledge complex (S_a = S) or knowledge + belief (S_a declared).

        Only these two: in a complex the knowledge IS the gluing of the facets
        along shared vertices, so there is no belief-only variant (unlike the
        relational editor, where a lone KD45 relation is a model on its own).
        The per-facet belief lists are kept while in knowledge mode, so the
        switch is reversible.
        """
        if value == state.get("complex_kind", "kb"):
            return
        state["complex_kind"] = value
        reset_results()
        repaint_all()

    def paint_simplicial_editor() -> None:
        colors = agent_color_map(state["agents"])
        editor_box.clear()
        with editor_box:
            with ui.card().classes(CARD).props(FLAT):
                _card_title("Vértices (perspectivas de cada agente)")
                for agent in state["agents"]:
                    names = state["vertices"].setdefault(agent, [])
                    with ui.row().classes("w-full no-wrap items-center gap-2"):
                        ui.element("span").style(
                            f"width:10px;height:10px;border-radius:9999px;"
                            f"flex:none;background:{colors[agent]}"
                        )
                        v_in = ui.input(f"nuevo vértice de {agent}") \
                            .props("dense outlined").classes("grow")
                        ui.button(icon="add",
                                  on_click=lambda _, a=agent, w=v_in: add_vertex(a, w)) \
                            .props("round dense")
                        v_in.on("keydown.enter",
                                lambda _, a=agent, w=v_in: add_vertex(a, w))
                    with ui.row().classes("w-full gap-2"):
                        for v in names:
                            ui.chip(v, removable=True, color=colors[agent],
                                    text_color="white",
                                    on_value_change=lambda e, a=agent, n=v:
                                        remove_vertex(a, n))
                if not state["agents"]:
                    ui.label("Agrega primero los agentes.").classes("text-grey-5")
            with ui.card().classes(CARD).props(FLAT):
                _card_title("Facetas (un vértice de cada agente)")
                # Which of the two readings of the complex is being declared.
                # Mirrors the model-kind selector of the relational editor,
                # minus "belief only" (see set_complex_kind for why).
                knowledge_only = state.get("complex_kind", "kb") == "knowledge"
                ui.toggle(
                    {"knowledge": "complejo de conocimiento",
                     "kb": "conocimiento y creencia"},
                    value="knowledge" if knowledge_only else "kb",
                    on_change=lambda e: set_complex_kind(e.value),
                ).props("dense no-caps unelevated toggle-color=primary")
                ui.label(
                    "S_a = S: cada agente cree exactamente lo que sabe, así que "
                    "B_a coincide con K_a. No hay «sólo creencia»: los vértices "
                    "que pegan las facetas ya son el conocimiento."
                    if knowledge_only else
                    "Cada faceta dice además qué agentes la creen posible "
                    "(en qué subcomplejos S_a está)."
                ).classes("text-xs text-grey-5")
                for i, facet in enumerate(state["facets"]):
                    with ui.column().classes("w-full gap-0 pb-2") \
                            .style("border-bottom:1px solid var(--p-line)"):
                        with ui.row().classes("w-full items-center gap-2"):
                            # The name is stored on typing and the preview is
                            # redrawn on leaving the field, not on every key.
                            ui.input("nombre", value=facet["name"],
                                     on_change=lambda e, f=facet:
                                         f.__setitem__("name", e.value)) \
                                .props("dense outlined").classes("w-24") \
                                .on("blur", lambda: update_preview())
                            for agent in state["agents"]:
                                ui.select(
                                    state["vertices"].get(agent, []),
                                    value=facet["nodes"].get(agent), label=agent,
                                    on_change=lambda e, f=facet, a=agent:
                                        set_facet(f, "nodes", e.value, a),
                                ).props("dense options-dense") \
                                    .classes("grow min-w-[64px]")
                            ui.button(icon="delete",
                                      on_click=lambda _, k=i: remove_facet(k)) \
                                .props("flat dense color=grey")
                        if not knowledge_only:
                            ui.select(
                                state["agents"], multiple=True, value=facet["belief"],
                                label="la creen posible (está en S_a de)",
                                on_change=lambda e, f=facet: set_facet(f, "belief", e.value),
                            ).props("use-chips dense").classes("w-full")
                with ui.row().classes("w-full items-center gap-2"):
                    ui.button("añadir faceta", icon="add", on_click=lambda: add_facet()) \
                        .props("flat dense")
                    # The thesis's own construction (p. 19): every consistent
                    # UCF facet the vertices can form. Offered as an action,
                    # not applied silently, because a declared complex is
                    # often meant to be a proper subcomplex of M(N, V, L).
                    ui.button("completar al complejo maximal", icon="auto_awesome",
                              on_click=lambda: fill_maximal()) \
                        .props("flat dense")
                ui.markdown(
                    "Cada faceta lleva exactamente un vértice de cada agente "
                    "(UCF). Una faceta cuyos vértices se contradicen en un átomo "
                    "no existe en el modelo: se elimina y se avisa. «Completar al "
                    "complejo maximal» añade todas las facetas consistentes que "
                    "faltan (M(N, V, L)). Bajo el Axioma D, todo vértice debe "
                    "estar en alguna faceta del subcomplejo de creencia de su agente."
                ).classes("text-xs text-grey-5")

    def paint_editor() -> None:
        if state["kind"] == "simplicial":
            paint_simplicial_editor()
            return
        colors = agent_color_map(state["agents"])
        editor_box.clear()
        with editor_box:
            for agent in state["agents"]:
                rows = state["per_agent"].setdefault(agent, [])
                with ui.card().classes(CARD).props(FLAT):
                    # The color dot repeats the agent's color in the figures
                    # -- same convention as its chips.
                    with ui.row().classes("items-center gap-2"):
                        ui.element("span").style(
                            f"width:10px;height:10px;border-radius:9999px;"
                            f"background:{colors[agent]}"
                        )
                        ui.label(f"Agente {agent}").classes("font-semibold")
                    kind = state["kind"]
                    for i, row in enumerate(rows):
                        with ui.row().classes("w-full no-wrap items-center gap-2"):
                            # First column: the knowledge class, or in belief
                            # only the worlds FROM which one believes.
                            # Changing it repaints, because the belief
                            # options depend on the chosen class.
                            ui.select(
                                state["worlds"], multiple=True, value=row["cls"],
                                label=("desde (mundos)" if kind == "belief"
                                       else "clase (indistinguibles)"),
                                on_change=lambda e, r=row: set_cls(r, e.value),
                            ).props("use-chips dense").classes("grow")
                            # Believed worlds: restricted to the class (so a
                            # belief outside the class is inexpressible), or
                            # to all worlds when there is no class. Without
                            # belief, the column does not exist.
                            if kind != "knowledge":
                                ui.select(
                                    state["worlds"] if kind == "belief" else row["cls"],
                                    multiple=True, value=row["bel"],
                                    label=("cree (mundos)" if kind == "belief"
                                           else "cree (vacío = lo que sabe)"),
                                    on_change=lambda e, r=row: set_bel(r, e.value),
                                ).props("use-chips dense").classes("grow")
                            ui.button(
                                icon="delete",
                                on_click=lambda _, a=agent, k=i: remove_row(a, k),
                            ).props("flat dense color=grey")
                    ui.button(
                        "añadir fila" if kind == "belief" else "añadir clase",
                        icon="add", on_click=lambda _, a=agent: add_row(a),
                    ).props("flat dense")
                    ui.markdown({
                        "kb": "Mundos fuera de toda clase quedan como clases unitarias.",
                        "knowledge": "Mundos fuera de toda clase quedan como clases "
                                     "unitarias (el agente los distingue).",
                        "belief": "Mundos sin fila no creen nada: inválido bajo KD45, "
                                  "creencia difunta bajo K45.",
                    }[kind]).classes("text-xs text-grey-5")

    # ----------------------------------------------------------------------- #
    # Live preview. It is the one thing that runs on EVERY edit and it calls
    # Graphviz / matplotlib (0.3-0.8 s): done synchronously, as it used to be,
    # it froze the interface at each click of a select. Now:
    #   1. the synchronous part (update_preview) only marks the document dirty,
    #      refreshes the "stale results" strip and schedules a render;
    #   2. a 250 ms debounce collapses a burst of edits into one render, and a
    #      sequence number drops renders that a newer edit superseded;
    #   3. the render runs in a worker thread (run.io_bound), so the page
    #      stays responsive and the spinner in the card header is visible;
    #   4. results are cached by a hash of the state, and the figure FILE is
    #      named by that hash too, so going back to a state already drawn
    #      (switching documents, undoing an edit) costs nothing and a cached
    #      path always points at the figure of exactly that state.
    # The card itself is built once; only its badge and body are repainted,
    # so the frame does not flash on every edit.
    # ----------------------------------------------------------------------- #
    preview_cache: dict = {}            # state hash -> (path, violations) | error text
    preview_seq = {"n": 0}
    preview_ui: dict = {}               # "badge" and "body" containers of the card

    def _state_key(st: dict) -> str:
        import hashlib
        import json

        return hashlib.sha1(json.dumps(st, sort_keys=True, default=str).encode()).hexdigest()[:12]

    def _preview_card() -> None:
        """Build the preview card once (the only card WITH elevation: lime halo)."""
        if preview_ui:
            return
        with preview_box, ui.card().classes(CARD + " poster-live").props(FLAT):
            with ui.row().classes("w-full items-center gap-2"):
                ui.element("span").classes("pulse-dot")
                _card_title("Vista previa · modelo tal como se ingresa")
                ui.space()
                preview_ui["badge"] = ui.row().classes("items-center")
            preview_ui["body"] = ui.column().classes("w-full gap-2")

    def update_preview() -> None:
        """Mark the model as edited and schedule a (debounced) re-render."""
        if ws["loading"]:
            return
        # Every edit goes through here: the stored result, if any, no longer
        # matches the model and the comparison will have to recompute it.
        current()["dirty"] = True
        refresh_stale()
        preview_seq["n"] += 1
        seq = preview_seq["n"]
        ui.timer(0.25, lambda: _render_preview(seq), once=True)

    async def _render_preview(seq: int) -> None:
        """Draw the model exactly as entered (no closures), off the event loop.

        The card header carries the pulsing "live" dot and a validity chip
        (lime = already valid, amber = N conditions to be completed); the
        figure shows exactly the drawn chips with what is missing dotted in
        red. A state inexpressible as seeds (overlapping classes) is shown
        as text.
        """
        if seq != preview_seq["n"] or ws["active"] is None:
            return                              # superseded by a newer edit
        _preview_card()
        badge, body = preview_ui["badge"], preview_ui["body"]
        st = copy.deepcopy(live_state())
        doc_id = ws["active"]
        missing = state_problem(st)
        if missing:
            badge.clear()
            body.clear()
            with body:
                ui.label(missing).classes("text-grey-5")
            return
        key = _state_key(st)
        if key not in preview_cache:
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
            if len(preview_cache) >= 64:        # bounded: oldest entry out
                preview_cache.pop(next(iter(preview_cache)))
            preview_cache[key] = result
            if seq != preview_seq["n"] or doc_id != ws["active"]:
                return                          # the user moved on meanwhile
        result = preview_cache[key]
        badge.clear()
        body.clear()
        if isinstance(result, str):
            with badge:
                _chip("inexpresable", "bad")
            with body:
                ui.html(f"<pre style='white-space:pre-wrap' class='text-xs'>"
                        f"{html.escape(result)}</pre>")
            return
        path, violations = result
        with badge:
            if violations:
                _chip(f"{len(violations)} por completar", "warn", icon="pending")
            else:
                _chip("válido", "ok", icon="check")
        with body:
            with ui.element("div").classes("w-full fig-frame"):
                _figure_img(path)
            if violations:
                with ui.expansion("Lo que las clausuras completarán") \
                        .classes("w-full").style(f"color:{POSTER['yellow']}"):
                    for v in violations:
                        ui.label(v).classes("font-mono text-xs")

    def refresh_stale() -> None:
        """Show, above the results, that they predate the current edits.

        The preview follows every edit but the Figures 1-4 do not (a run is
        explicit); without this strip the old figures passed for results of
        the model now in the editor. ``doc["dirty"]`` already tracks exactly
        that, so the strip is a pure function of it.
        """
        stale_box.clear()
        if ws["active"] is None or ws["comparing"]:
            return
        doc = current()
        if doc["outcome"] is None or not doc["dirty"]:
            return
        with stale_box, ui.row().classes(
                "w-full items-center gap-3 px-4 py-2 rounded-xl no-wrap").style(
                f"background:{_tint(POSTER['yellow'], .10)};"
                f"border:1px solid {_tint(POSTER['yellow'], .45)}"):
            ui.icon("history").style(f"color:{POSTER['yellow']}")
            ui.label("Las figuras de abajo son de una versión anterior del modelo.") \
                .classes("text-sm grow").style(f"color:{POSTER['yellow']}")
            ui.button("Volver a correr", icon="play_arrow",
                      on_click=lambda: run_clicked()) \
                .props("outline dense").style(f"color:{POSTER['yellow']}")

    def set_cls(row: dict, cls: list) -> None:
        """Update a class and prune the beliefs that fell outside it.

        In belief only there is no class to respect: the first column is the
        source worlds and belief may point at any world.
        """
        row["cls"] = cls
        if state["kind"] != "belief":
            row["bel"] = [w for w in row["bel"] if w in cls]
        paint_editor()  # the options of the belief select changed
        update_preview()

    def set_bel(row: dict, bel: list) -> None:
        row["bel"] = bel
        update_preview()

    def add_row(agent: str) -> None:
        state["per_agent"][agent].append({"cls": [], "bel": []})
        paint_editor()
        update_preview()

    def remove_row(agent: str, index: int) -> None:
        state["per_agent"][agent].pop(index)
        paint_editor()
        update_preview()

    # ----------------------------------------------------------------------- #
    # Formula evaluator: answers in its own card, world by world.
    # ----------------------------------------------------------------------- #
    def eval_formula() -> None:
        formula_out.clear()
        simplicial = state["kind"] == "simplicial"
        try:
            rows = evaluate_state(live_state(), formula_input.value or "")
        except ValueError as exc:
            with formula_out:
                ui.html(f"<pre style='white-space:pre-wrap' "
                        f"class='text-pink-3 text-xs'>{exc}</pre>")
            return
        holds = sum(1 for _, ok in rows if ok)
        with formula_out:
            with ui.row().classes("gap-1"):
                for world, ok in rows:
                    _chip(world, "ok" if ok else "bad",
                          icon="check" if ok else "close")
            unit = "facetas" if simplicial else "mundos"
            ui.label(
                f"Válida en el modelo (vale en todas las {unit})." if simplicial and holds == len(rows)
                else "Válida en el modelo (vale en todos los mundos)." if holds == len(rows)
                else f"Vale en {holds} de {len(rows)} {unit}."
            ).classes("text-xs text-grey-5")

    # ----------------------------------------------------------------------- #
    # Pipeline run. Asynchronous and with a loading state: the button shows a
    # spinner (Quasar's 'loading' prop) and the heavy work goes to a thread via
    # run.io_bound, so the interface does not freeze for those couple of seconds.
    # ----------------------------------------------------------------------- #
    def paint_results_placeholder(target=None) -> None:
        """Illustrated empty state: never a blank column without a message."""
        target = results if target is None else target
        with target, ui.column().classes("w-full items-center py-16 gap-1"):
            ui.label("Sin resultados todavía").classes("text-grey-5 font-semibold")
            ui.label("Corre el pipeline para ver las Figuras 1 → 4") \
                .classes("text-xs text-grey-6")

    def reset_results() -> None:
        """Forget the active document's result: it belongs to ANOTHER model.

        On loading an example or changing the kind, the figures and metrics
        of the previous run no longer describe what is in the editor;
        leaving them visible under the new preview passed them off as
        results of the current model.
        """
        if ws["loading"] or ws["active"] is None:
            return
        current()["outcome"] = None
        render_outcome(None, results)
        refresh_stale()                 # nothing to be stale about any more

    async def explicit_changed() -> None:
        """Implicit-edges switch: preview now, pipeline if there was a run."""
        if explicit_in.value == state.get("explicit"):
            return   # assignment while loading a document, not a click
        update_preview()
        if current()["outcome"] is not None:
            await run_clicked()

    async def hasse_full_changed() -> None:
        """Full-lattice switch: it only affects one figure of the result, so
        there is no preview to repaint; if there were results already they are
        recomputed so that Fig. 4 matches."""
        if hasse_full_in.value == state.get("hasse_full", False):
            return   # assignment while loading a document, not a click
        if current()["outcome"] is not None:
            await run_clicked()
        else:
            state["hasse_full"] = hasse_full_in.value

    # ----------------------------------------------------------------------- #
    # Running a model and painting its result are two separate things: this
    # way the same result is stored in its document, repainted when coming
    # back to it and reused in the comparison without recomputing.
    # ----------------------------------------------------------------------- #
    async def compute(st: dict, tag: str) -> dict:
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

    def render_failure(outcome: dict) -> None:
        """Failure card for an 'invalid' or 'error' outcome."""
        with ui.card().classes(CARD + " poster-bad").props(FLAT):
            if outcome["status"] == "invalid":
                ui.label("Modelo rechazado por la validación del núcleo:") \
                    .classes("font-semibold text-pink-3")
                ui.html(f"<pre style='white-space:pre-wrap'>"
                        f"{html.escape(outcome['message'])}</pre>")
                return
            if outcome["no_dot"]:
                ui.label("Falta Graphviz").classes("font-semibold text-pink-3")
                ui.html(
                    "<p>El pipeline necesita el binario <code>dot</code> "
                    "para dibujar las figuras, y no está en el PATH.</p>"
                    "<p>Instálalo con <code>brew install graphviz</code> "
                    "(macOS) o <code>apt install graphviz</code> (Linux) "
                    "y vuelve a correr.</p>"
                )
            else:
                ui.label("Error inesperado (esto es un bug, repórtalo):") \
                    .classes("font-semibold text-pink-3")
            ui.html(f"<pre style='white-space:pre-wrap' class='text-xs'>"
                    f"{html.escape(outcome['trace'])}</pre>")

    def render_outcome(outcome: dict | None, target) -> None:
        """Paint the complete result of a run into ``target``."""
        target.clear()
        if outcome is None:
            paint_results_placeholder(target)
            return
        if outcome["status"] != "ok":
            with target:
                render_failure(outcome)
            return
        out = outcome["out"]
        with target:
            # Run metrics as stat tiles + status chips (the same numbers as
            # the old text log, readable in a second).
            with ui.card().classes(CARD).props(FLAT):
                with ui.row().classes("w-full items-center gap-2"):
                    _card_title("Resultado del pipeline")
                    ui.space()
                    # Badges come with Quasar palette names
                    # (positive/negative/primary); they are mapped to the
                    # poster's role tones so they do not come out lime with
                    # white text (unreadable).
                    for text, color in out.badges:
                        tone = {"positive": "ok", "negative": "bad"} \
                            .get(color, "info")
                        _chip(text, tone).props("dense")
                with ui.row().classes("w-full gap-8 mt-2"):
                    for value, label in out.stats:
                        with ui.column().classes("gap-0 items-center"):
                            ui.label(value).classes(
                                "text-2xl font-bold text-white")
                            ui.label(label).classes("text-xs text-grey-5")

            # Step-by-step pipeline log: what was completed, what is missing
            # and what failed. It is shown first because it answers the
            # question people bring ("why didn't I get what I drew?") before
            # they start looking at the figures.
            if out.steps:
                with ui.card().classes(CARD).props(FLAT):
                    _card_title("Pipeline paso a paso")
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
                                ui.label("tal cual se dibujó") \
                                    .classes("text-xs text-grey-5")
                            if step.status == "skipped":
                                ui.label("no aplica a este tipo de modelo") \
                                    .classes("text-xs text-grey-5")
                        for text in step.skipped:
                            with ui.row().classes("w-full no-wrap items-start gap-2 ml-8"):
                                ui.label("–").classes("font-bold text-grey-5")
                                ui.label(text).classes("text-sm text-grey-4")
                        for text in step.failed:
                            with ui.column().classes(
                                "w-full gap-0 ml-8 p-2 rounded poster-bad"
                            ):
                                ui.label("Falló aquí — el pipeline se detuvo:") \
                                    .classes("text-xs font-semibold text-pink-3")
                                ui.html(
                                    f"<pre style='white-space:pre-wrap' "
                                    f"class='text-xs'>{html.escape(text)}</pre>"
                                )
                        for text in step.completed:
                            with ui.row().classes("w-full no-wrap items-start gap-2 ml-8"):
                                ui.label("+").classes("font-bold") \
                                    .style(f"color:{POSTER['lime']}")
                                ui.label(text).classes("text-sm text-grey-4")
                        for text in step.missing:
                            with ui.row().classes("w-full no-wrap items-start gap-2 ml-8"):
                                ui.label("?").classes("font-bold") \
                                    .style(f"color:{POSTER['yellow']}")
                                ui.label(text).classes("text-sm text-grey-4")
                    ui.label(
                        "+ lo que una clausura o convención completó por ti · "
                        "? lo que sigue sin especificar y qué significa ese silencio"
                    ).classes("text-xs italic text-grey-5 mt-3")

            # The pipeline figures, in order, as in thesis_example.py, plus
            # Fig. 4 (face lattice) added by adapters. A grid: tall figures
            # (Fig. 2a's column of copies, a triangle fan) share a row, wide
            # ones (the Hasse band) take it whole -- half the scrolling and
            # no figure floating in a sea of grey.
            with ui.element("div").classes("w-full fig-grid"):
                for caption, path in out.figures:
                    figure_card(caption, path, span=_is_wide(path))

            # The interactive 3D view is a complete plotly page: it is embedded
            # in an iframe instead of being rebuilt with components.
            if out.html_3d is not None:
                with ui.card().classes(CARD).props(FLAT):
                    _card_title("Vista 3D interactiva del complejo")
                    # The plotly page is light: it goes on the same sheet as
                    # the PNG figures so it is not a loose white block over
                    # navy.
                    # sanitize=False: ui.html sanitizes HTML by default and
                    # REMOVES <iframe>s, which left the 3D view as an empty
                    # card. The src is our own file served from outputs/,
                    # not external content.
                    ui.html(
                        f'<iframe src="{_url(out.html_3d)}" '
                        'style="width:100%;height:560px;border:none;'
                        'display:block;border-radius:.375rem"></iframe>',
                        sanitize=False,
                    ).classes("w-full fig-frame")
                    ui.label("Arrastra para rotar; rueda para acercar.") \
                        .classes("text-xs italic text-grey-5")

            # Text diagrams (visualize): the dependency-free view, collapsed
            # by default so it does not compete with the figures.
            with ui.expansion("Diagramas de texto").classes("w-full"):
                for caption, diagram in out.text_diagrams:
                    ui.label(caption).classes("font-semibold mt-2")
                    ui.html(f"<pre style='white-space:pre-wrap' "
                            f"class='text-xs'>{diagram}</pre>")

    async def run_clicked() -> None:
        doc = current()
        results.clear()
        run_btn.props("loading")
        with results, ui.card().classes(CARD).props(FLAT):
            with ui.column().classes("w-full items-center py-10 gap-2"):
                ui.spinner(size="lg")
                ui.label("Generando figuras…").classes("text-grey-5")
        try:
            outcome = await compute(copy.deepcopy(live_state()), doc["id"])
        finally:
            run_btn.props(remove="loading")
        doc["outcome"], doc["dirty"] = outcome, False
        refresh_stale()
        if outcome["status"] == "invalid":
            ui.notify("El modelo no es válido — detalle en el panel",
                      type="negative")
        elif outcome["status"] == "error":
            ui.notify("Error al correr el pipeline — detalle en el panel",
                      type="negative")
        if doc["id"] == ws["active"]:   # the model may have been switched mid-run
            render_outcome(outcome, results)

    # ----------------------------------------------------------------------- #
    # Models bar: one chip per open document (click = activate, x = close),
    # buttons to open a blank one or duplicate the active one, and the
    # comparison controls when there are at least two.
    # ----------------------------------------------------------------------- #
    KIND_ICON = {"kb": "hub", "knowledge": "visibility",
                 "belief": "psychology", "simplicial": "change_history"}

    def paint_docs_bar() -> None:
        ids = [d["id"] for d in docs]
        ws["compare"] = [i for i in ws["compare"] if i in ids]
        if len(ws["compare"]) < 2 and len(docs) >= 2:
            ws["compare"] = ids[:4]     # the usual case: compare what is open
        docs_bar.clear()
        with docs_bar:
            ui.label("Modelos").classes("eyebrow")
            for d in docs:
                active = d["id"] == ws["active"]
                kind = state["kind"] if active else d["state"]["kind"]
                ui.chip(
                    d["name"], icon="lock" if d["readonly"] else KIND_ICON[kind],
                    removable=len(docs) > 1,
                    # The active one in lime (the accent of "what is live");
                    # the others translucent like the world chips.
                    color=POSTER["lime"] if active else "rgba(255,255,255,.14)",
                    text_color=POSTER["surface"] if active else "white",
                    on_click=lambda _, i=d["id"]: activate(i),
                    on_value_change=lambda e, i=d["id"]: close_doc(i),
                ).tooltip(KINDS[kind])
            ui.button(icon="add", on_click=lambda: add_blank()) \
                .props("round dense flat").tooltip("Modelo nuevo en blanco")
            ui.button(icon="content_copy", on_click=lambda: duplicate_active()) \
                .props("round dense flat").tooltip("Duplicar el modelo activo")
            # Persistence (GitHub #18): the whole bar to a file, a file back
            # into the bar, and the active model out as a download.
            ui.button(icon="save", on_click=lambda: save_dialog()) \
                .props("round dense flat").tooltip("Guardar todos los modelos abiertos")
            ui.button(icon="folder_open", on_click=lambda: open_dialog()) \
                .props("round dense flat").tooltip("Abrir un espacio guardado")
            ui.button(icon="download", on_click=lambda: export_active()) \
                .props("round dense flat").tooltip("Descargar el modelo activo (.json)")
            if len(docs) >= 2:
                # The comparison controls go on their own line: with long
                # names they got mixed up with the model chips.
                ui.element("div").classes("w-full")
                ui.select(
                    {d["id"]: d["name"] for d in docs}, multiple=True,
                    value=ws["compare"], label="comparar (de 2 a 4)",
                    on_change=lambda e: ws.__setitem__("compare", list(e.value)),
                ).props("dense outlined use-chips options-dense") \
                    .classes("min-w-[280px] max-w-[560px]")
                if ws["comparing"]:
                    ui.button("Volver al editor", icon="edit",
                              on_click=lambda: exit_compare()).props("outline dense")
                ui.button("Comparar", icon="compare",
                          on_click=lambda: compare_clicked()) \
                    .props("color=primary text-color=dark unelevated dense")

    # ----------------------------------------------------------------------- #
    # Side-by-side comparison. Each panel shows the document's ALREADY stored
    # result; only those never run or changed since their last run
    # (``dirty``) are recomputed. It serves both "the same action on several
    # inputs" and "two actions on the same input": in both cases they are
    # documents, and here they are seen together.
    # ----------------------------------------------------------------------- #
    def render_panel(doc: dict) -> None:
        """One comparison panel: header, metrics and figures of the model."""
        outcome = doc["outcome"]
        with ui.column().classes("gap-3 min-w-0").style("flex:1 1 0"):
            with ui.card().classes(CARD).props(FLAT):
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    if doc["readonly"]:
                        ui.icon("lock").style(f"color:{POSTER['yellow']}")
                    ui.label(doc["name"]).classes("font-bold text-white grow")
                ui.label(KINDS[doc["state"]["kind"]]).classes("eyebrow")
                if doc["origin"] and doc["origin"].get("label"):
                    ui.label("Resultado de " + doc["origin"]["label"]) \
                        .classes("text-xs italic text-grey-5")
                if outcome["status"] == "ok":
                    out = outcome["out"]
                    with ui.row().classes("w-full gap-1"):
                        for text, color in out.badges:
                            tone = {"positive": "ok", "negative": "bad"} \
                                .get(color, "info")
                            _chip(text, tone).props("dense")
                    with ui.row().classes("w-full gap-5 mt-1"):
                        for value, label in out.stats:
                            with ui.column().classes("gap-0 items-center"):
                                ui.label(value).classes("text-lg font-bold text-white")
                                ui.label(label).classes("text-xs text-grey-5")
                    # From the log, only what stopped the pipeline: the full
                    # detail is in that model's editor.
                    for step in out.steps:
                        for text in step.failed:
                            ui.label(f"{step.name}: falló").classes(
                                "text-xs font-semibold text-pink-3 mt-2")
                            ui.html(f"<pre style='white-space:pre-wrap' "
                                    f"class='text-xs'>{html.escape(text)}</pre>")
            if outcome["status"] != "ok":
                render_failure(outcome)
                return
            for caption, path in outcome["out"].figures:
                figure_card(caption, path)
            if outcome["out"].html_3d is not None:
                ui.label("Vista 3D interactiva: ábrela desde el editor de "
                         "este modelo.").classes("text-xs italic text-grey-5")

    async def compare_clicked() -> None:
        chosen = [d for d in docs if d["id"] in ws["compare"]]
        if not 2 <= len(chosen) <= 4:
            ui.notify("Elige de 2 a 4 modelos para comparar.", type="warning")
            return
        current()["state"] = copy.deepcopy(live_state())   # the active one, up to date
        ws["comparing"] = True
        editor_row.set_visibility(False)
        compare_box.set_visibility(True)
        paint_docs_bar()
        compare_box.clear()
        with compare_box, ui.card().classes(CARD).props(FLAT):
            with ui.column().classes("w-full items-center py-10 gap-2"):
                ui.spinner(size="lg")
                ui.label(f"Preparando {len(chosen)} modelos…") \
                    .classes("text-grey-5")
        for doc in chosen:
            if doc["outcome"] is None or doc["dirty"]:
                doc["outcome"] = await compute(copy.deepcopy(doc["state"]), doc["id"])
                doc["dirty"] = False
        compare_box.clear()
        with compare_box, ui.row().classes("w-full no-wrap items-start gap-4"):
            for doc in chosen:
                render_panel(doc)
        # The active document's editor stays consistent with what was just computed.
        render_outcome(current()["outcome"], results)

    def exit_compare() -> None:
        ws["comparing"] = False
        compare_box.set_visibility(False)
        editor_row.set_visibility(True)
        paint_docs_bar()
        refresh_stale()

    # First paint: the thesis example with its preview, and the illustrated
    # empty state in the results area.
    ws["active"] = new_doc("Modelo 1", blank_state())["id"]
    load_example("tesis")   # also paints the bar, the preview and the empty state


# reload=False: NiceGUI's auto-reload re-imports the module in a subprocess, a
# surprising behavior for a simple local tool. The __mp_main__ guard is the
# NiceGUI convention (multiprocess uvicorn).
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="La geometría de una creencia falsa", reload=False,
           dark=True)

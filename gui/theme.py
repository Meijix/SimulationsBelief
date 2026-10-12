"""Visual system of the GUI: palette, CSS, card and chip helpers (no state).

Everything here is presentation vocabulary shared by the view modules in
``gui/views``: the navy-and-lime palette (``POSTER``), the CSS that Tailwind
and Quasar do not cover (``HEAD_HTML``), the base card classes, the status
chips (``chip``), the card eyebrow (``card_title``), the figure helpers
(``figure_img``, ``is_wide``) and the help texts that depend on the model
kind. Nothing in this module reads or writes application state, which is
what makes it safe to import from anywhere.

Design rules (see the docstring of ``gui/app.py``): one accent (lime) for
action and good news, amber for "to be completed", rose for "rejected",
slate for labels that are not verdicts; agents keep their own Okabe-Ito
colours because that is data, not chrome.
"""

from __future__ import annotations

from nicegui import ui


# Palette: navy page and surface, lime as the single accent, two status hues.
# Used both in the CSS below and in the role chips/icons.
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
  /* ...except for embedded pages (the Plotly 3-D view): an iframe has no
     intrinsic width, so fit-content collapsed its sheet to ~300px and cut
     the scene. Those take the whole card. */
  .fig-frame.fig-fill {{ width: 100%; }}
  .fig-frame.fig-fill iframe {{ width: 100%; min-height: 560px; display: block; }}
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


def url(path) -> str:
    """Static URL of a figure, with the mtime as cache buster (see module docstring)."""
    return f"/outputs/{path.name}?v={int(path.stat().st_mtime)}"


def figure_size(path) -> tuple[float, float] | None:
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


def is_wide(path) -> bool:
    """A figure wider than 1.6 : 1 takes a whole row of the grid; others share one."""
    size = figure_size(path)
    return size is None or size[1] == 0 or size[0] / size[1] > 1.6


def figure_img(path) -> None:
    """An ``<img>`` that shrinks to its content inside the sheet.

    A plain img is used instead of ``ui.image``: q-img is a fixed-ratio box
    that, with ``fit=contain`` and full width, centered the figure in a 420px
    rectangle and left empty bands above/below or on the sides. With
    ``width/height:auto`` and only maximums, the sheet is exactly as big as
    the figure and the caption sits right below it.
    """
    ui.html(
        f'<img src="{url(path)}" style="display:block;margin:0 auto;'
        'max-width:100%;max-height:520px;width:auto;height:auto">'
    ).classes("w-full")


def card_title(text: str) -> None:
    """Card title of the visual system: muted small-caps eyebrow."""
    ui.label(text).classes("eyebrow")


# ROLE chips: translucent background of the tone and text in the same tone,
# readable over navy. Two accents only -- lime for "good / done", amber for
# "to be completed", rose for "rejected" -- and slate for anything that is a
# label rather than a verdict (the logic, "propio", information).
TONES = {
    "ok": POSTER["green"], "warn": POSTER["yellow"],
    "bad": POSTER["pink"], "done": POSTER["cyan"], "info": POSTER["blue"],
}


def tint(hex_color: str, alpha: float) -> str:
    """``#rrggbb`` -> ``rgba(r,g,b,alpha)``: translucent background of the same tone."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def chip(text: str, tone: str, icon=None):
    """Status chip with a role tone (see ``TONES``).

    The color goes through the ``color`` parameter (NiceGUI accepts CSS and
    applies it as a style) and not through ``.style()``: the ``bg-primary``
    that Quasar adds by default carries ``!important`` and would override
    any inline style.
    """
    c = TONES[tone]
    return ui.chip(text, icon=icon, color=tint(c, .18), text_color=c) \
        .classes("font-semibold")


# Icon per model kind, for the chips of the models bar.
KIND_ICON = {"kb": "hub", "knowledge": "visibility",
             "belief": "psychology", "simplicial": "change_history"}


def apply_theme() -> None:
    """Dark mode, Quasar palette and the CSS, once per page.

    Inside the page function on purpose: NiceGUI 3 forbids UI calls in the
    global scope when ``@ui.page`` is used. ``dark`` and ``dark_page`` are the
    surface and page navies; the Quasar roles are mapped to the two-accent
    system so inputs, selects, dialogs and notifications pick it up alone.
    """
    ui.dark_mode().enable()
    ui.colors(
        primary=POSTER["lime"], secondary=POSTER["cyan"], accent=POSTER["pink"],
        dark=POSTER["surface"], dark_page=POSTER["page"],
        positive=POSTER["green"], negative=POSTER["pink"],
        warning=POSTER["yellow"], info=POSTER["blue"],
    )
    ui.add_head_html(HEAD_HTML)


def take(input_widget) -> str:
    """Read and clear an "add" field, returning the typed name (stripped)."""
    name = (input_widget.value or "").strip()
    input_widget.value = ""
    return name

"""Visual system of the GUI: palette, CSS, card and chip helpers (no state).

Everything here is presentation vocabulary shared by the view modules in
``gui/views``: the palette (``POSTER``), the CSS that Tailwind and Quasar do
not cover (``HEAD_HTML``), the base card classes, the status marks
(``status``, ``chip``), the panel title (``card_title``), the figure helpers
(``figure_img``, ``is_wide``) and the help texts that depend on the model
kind. Nothing in this module reads or writes application state, which is
what makes it safe to import from anywhere.

Design rules (2026-11-13, "aurora": navy sky, one violet; a light twin
for daylight, switched from the header). The GUI is an
instrument, not a dashboard: a dark navy workbench with a few flat panels,
hairlines instead of shadows, square corners, dense rows, and words rather
than icons. One accent, a vibrant violet, is spent on exactly three things:
the primary button, the active tab or document, and the rule of the live
preview. Everything else is ink or muted ink. Figures are drawn transparent in
the renderers' dark ink theme (``visualization.ink_theme``), so they need
no plate. Status is said
in words with one small coloured mark, in the three hues of an aurora:
green for valid / done, amber for "to be completed", rose for rejected /
error. Agents keep their own Okabe-Ito colours because that is data, not
chrome. No gradients, no glows, no animation, no uppercase tracking.
"""

from __future__ import annotations

from nicegui import ui


def _version() -> str:
    """The package version for the header and the footer: from the installed
    metadata (``pip install -e .``) or, failing that, from pyproject.toml."""
    try:
        from importlib.metadata import version
        return version("simulationsbelief")
    except Exception:  # noqa: BLE001 -- not installed: read the file
        import re
        from pathlib import Path
        try:
            text = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
            m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
            return m.group(1) if m else "dev"
        except OSError:
            return "dev"


VERSION = _version()


# The two palettes (2026-11-13). DARK is the one the user chose: navy as the
# page, violet as the accent, in the key of the northern lights. LIGHT is
# the same system printed on paper: a cool off-white page, white panels,
# the violet one step deeper so it holds on white. In both, the accent
# exists in two strengths: ``accent`` is the fill (buttons, the active
# document) and carries ``on_accent`` text; ``accent_ink`` is the accent as
# TEXT on the page, for tabs and text buttons. Every value is also a CSS
# variable (``--p-<key>``, see HEAD_HTML), switched by Quasar's body class
# (``body--dark`` / ``body--light``), so a page can change theme in place:
# the views never paint a hex, they paint ``var(--p-...)``.
PALETTES = {
    "dark": {
        "page": "#05081A",      # the night sky: page background
        "surface": "#0B1128",   # panels: a lighter navy, one hairline around
        "inset": "#070C20",     # sunken areas inside a panel (code, log rows)
        "paper": "#EEF0F8",     # a light plate, kept for anything that must be white
        "paper_ink": "#1B2140", # text on such a plate
        "ink": "#E7EAF6",       # text
        "line": "rgba(170,180,230,.14)",    # hairlines (borders, rules)
        "chip": "rgba(170,180,230,.12)",    # neutral tags (worlds)
        "scroll": "rgba(170,180,230,.25)",  # scrollbar thumb
        "accent": "#9B5CFF",    # THE accent, as a fill: Run button, active document
        "accent_ink": "#B794FF",        # the accent as text on the page
        "on_accent": "#05081A", # text on a violet fill
        "muted": "#9BA4CB",     # secondary text: panel titles, captions, notes
        # Status hues (the aurora's own): green = valid / done, amber = to be
        # completed / stale, rose = rejected / error.
        "green": "#5BE3A8",
        "yellow": "#F5C04E",
        "pink": "#FF7E9A",
    },
    "light": {
        "page": "#F3F4FA",
        "surface": "#FFFFFF",
        "inset": "#EEF0F8",
        "paper": "#FFFFFF",
        "paper_ink": "#1B2140",
        "ink": "#1B2140",
        "line": "rgba(27,33,64,.14)",
        "chip": "rgba(27,33,64,.08)",
        "scroll": "rgba(27,33,64,.25)",
        "accent": "#7C3AED",
        "accent_ink": "#6D28D9",
        "on_accent": "#FFFFFF",
        "muted": "#5B6485",
        "green": "#15803D",
        "yellow": "#B45309",
        "pink": "#BE123C",
    },
}
# The ink theme of the FIGURES that goes with each palette (visualization.ink).
FIGURE_INK = {"dark": "dark", "light": "light"}
# Legacy name: the dark palette. Views should paint CSS variables, not these.
POSTER = dict(PALETTES["dark"])
POSTER.update({"lime": POSTER["green"], "cyan": POSTER["green"], "blue": POSTER["muted"],
               "purple": POSTER["accent_ink"], "orange": POSTER["muted"]})


def _css_vars(palette: dict) -> str:
    """``--p-key: value;`` for every colour of a palette (``accent_ink`` -> ``--p-accent-ink``)."""
    out = []
    for key, value in palette.items():
        out.append(f"--p-{key.replace('_', '-')}: {value};")
    # Role aliases the CSS reads by meaning.
    out += [f"--p-ok: {palette['green']};", f"--p-warn: {palette['yellow']};",
            f"--p-bad: {palette['pink']};"]
    return " ".join(out)


# Base class of ALL panels: flat, hairline border, square-ish corners
# (an instrument panel, not an app card). ``poster-card`` is in HEAD_HTML.
CARD = "w-full poster-card"
FLAT = "flat"


# Fonts + the CSS that Tailwind/Quasar do not cover.
HEAD_HTML = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:ital,opsz,wght@0,8..60,500;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
<style>
  :root {{ {_css_vars(PALETTES["dark"])} }}
  body.body--light {{ {_css_vars(PALETTES["light"])} }}
  html {{ font-size: 14px; }}
  body, body.body--dark {{ font-family: 'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif;
          background: var(--p-page) !important; color: var(--p-ink);
          -webkit-font-smoothing: antialiased; }}
  .font-mono, pre, code {{ font-family: 'IBM Plex Mono', 'Menlo', monospace; }}
  .serif {{ font-family: 'Source Serif 4', Georgia, serif; }}
  pre {{ font-size: .82rem; line-height: 1.45; background: var(--p-inset); padding: .6rem .75rem;
         border: 1px solid var(--p-line); border-radius: 2px; margin: .25rem 0; overflow-x: auto; }}
  code {{ font-size: .9em; }}

  /* Text roles: ink for content, muted for secondary text, bad for errors. */
  .ink {{ color: var(--p-ink) !important; }}
  .muted {{ color: var(--p-muted) !important; }}
  .bad-text {{ color: var(--p-bad) !important; }}
  .text-xs {{ font-size: .8rem; line-height: 1.4; }}
  .text-sm {{ font-size: .9rem; line-height: 1.45; }}

  /* Panels: a lighter navy with a hairline; square corners; no shadow. */
  .poster-card {{ background: var(--p-surface) !important; border: 1px solid var(--p-line);
                  border-radius: 3px !important; box-shadow: none !important; color: var(--p-ink);
                  padding: .9rem 1rem; }}
  /* The live preview: the one panel with a rule in the accent. */
  .poster-live {{ border-top: 2px solid var(--p-accent); }}
  /* Core error / bug: rose tint. */
  .poster-bad {{ background: color-mix(in srgb, var(--p-bad) 9%, transparent) !important;
                 border-color: color-mix(in srgb, var(--p-bad) 45%, transparent); }}
  /* "The figures are older than the model": an amber strip above the results. */
  .stale-strip {{ background: color-mix(in srgb, var(--p-warn) 10%, transparent);
                  border: 1px solid color-mix(in srgb, var(--p-warn) 45%, transparent);
                  color: var(--p-warn); }}
  /* Panel title: a short sentence-case label in muted ink, like a section head in
     an instrument panel; a hairline under the row that holds it. */
  .eyebrow {{ color: var(--p-muted); font-size: .82rem; font-weight: 600;
              letter-spacing: 0; text-transform: none; }}
  .panel-head {{ width: 100%; display: flex; align-items: center; gap: .5rem;
                 padding-bottom: .5rem; margin-bottom: .6rem; border-bottom: 1px solid var(--p-line); }}
  /* A section inside a panel (one agent of the relation editor): a hairline
     above, the title row with the agent's colour swatch. */
  .section {{ width: 100%; padding: .75rem 0 .25rem; border-top: 1px solid var(--p-line); }}
  .panel-head + .section {{ border-top: none; padding-top: 0; }}
  .swatch {{ display: inline-block; width: 10px; height: 10px; border-radius: 2px; flex: none; }}

  /* Figures are drawn transparent and in the DARK ink theme (see
     adapters.base.show and visualization.INK_THEMES): light text and
     outlines, so they sit straight on the panel, no plate. */
  .fig-frame {{ width: fit-content; max-width: 100%; margin: 0 auto; padding: .25rem; }}
  /* Embedded pages (the Plotly 3-D view) paint the page's navy themselves
     and take the whole panel width. */
  .fig-frame.fig-fill {{ width: 100%; background: var(--p-page); padding: 0;
                         border: 1px solid var(--p-line); }}
  .fig-frame.fig-fill iframe {{ width: 100%; min-height: 560px; display: block; }}
  /* Figures of the results: one column, as in an article, each figure with
     its caption below and a hairline before the next. */
  .fig-grid {{ display: flex; flex-direction: column; gap: 0; }}
  .fig-block {{ padding: 1.1rem 0; border-bottom: 1px solid var(--p-line); }}
  .fig-block:last-child {{ border-bottom: none; padding-bottom: .25rem; }}
  .fig-caption {{ font-family: 'Source Serif 4', Georgia, serif; font-size: .95rem;
                  color: var(--p-ink); margin: .7rem auto 0; max-width: 60rem; line-height: 1.45; }}
  .fig-caption b {{ font-weight: 600; }}
  /* The run's numbers: a compact table, value in mono. */
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, max-content));
              gap: .35rem 1.75rem; font-size: .88rem; }}
  .metrics b {{ font-family: 'IBM Plex Mono', 'Menlo', monospace; font-weight: 600;
                color: var(--p-ink); margin-right: .35rem; }}
  .metrics span {{ color: var(--p-muted); }}
  /* Buttons and tabs in sentence case (Quasar uppercases by default). */
  .q-btn, .q-tab {{ text-transform: none; letter-spacing: 0; border-radius: 3px; }}
  .q-btn {{ font-weight: 500; }}
  .q-btn--outline:before {{ border-color: var(--p-line); }}
  /* Quiet text buttons (document bar actions): muted until hovered. */
  /* These buttons are created WITHOUT a Quasar colour (``remove="color"``):
     Quasar's ``.text-primary`` is an ``!important`` rule inside a cascade
     layer, which no unlayered rule can beat, so the only way to colour a
     text button from here is to leave Quasar's class off it. */
  .quiet-btn {{ color: var(--p-muted); }}
  .quiet-btn:hover {{ color: var(--p-ink); }}
  /* In-panel text buttons ("add class", "New action"): ink at rest, violet
     on hover, so the accent is not sprinkled over every panel. */
  .link-btn {{ color: var(--p-ink); opacity: .85; }}
  .link-btn:hover {{ color: var(--p-accent-ink); opacity: 1; }}
  /* The "add" buttons next to the add fields: a small outlined square. */
  .add-btn {{ border: 1px solid var(--p-line); color: var(--p-accent-ink) !important;
              border-radius: 3px; width: 36px; height: 36px; min-height: 36px; }}
  /* Tags (Quasar chips): square-ish, smaller. */
  .q-chip {{ border-radius: 3px; font-size: .84rem; height: 1.7rem; }}
  .q-chip--dense {{ height: 1.5rem; }}
  /* Quasar's field borders and labels, in the workbench's own hairline and ink. */
  .q-field--outlined .q-field__control:before {{ border-color: var(--p-line); border-radius: 3px; }}
  .q-field--outlined .q-field__control {{ border-radius: 3px; }}
  .q-field__label, .q-field__native, .q-field__input {{ color: var(--p-ink); }}
  .q-field__label {{ color: var(--p-muted); }}
  .q-expansion-item {{ color: var(--p-ink); }}
  .q-tabs {{ border-bottom: 1px solid var(--p-line); }}
  .q-tab {{ min-height: 38px; padding: 0 .9rem; }}
  .q-tab__label {{ font-weight: 500; font-size: .9rem; }}
  .q-tab--inactive {{ color: var(--p-muted); }}
  .q-menu, .q-dialog .q-card {{ border-radius: 3px; }}
  /* Header: a compact toolbar, a hairline below, no accent rule. */
  .poster-header {{ background: var(--p-surface) !important; border-bottom: 1px solid var(--p-line);
                    display: flex; flex-wrap: wrap; align-items: center; color: var(--p-ink);
                    column-gap: 1.5rem; row-gap: .5rem; min-height: 50px; }}
  .header-title {{ min-width: 0; flex: 1 1 320px; display: flex; align-items: baseline; gap: .9rem; }}
  .header-title .q-item__label, .header-sub {{ overflow: hidden; text-overflow: ellipsis; }}
  .header-sub {{ font-family: 'IBM Plex Mono', 'Menlo', monospace; font-size: .76rem;
                 color: var(--p-muted); white-space: nowrap; }}
  .header-controls {{ margin-left: auto; display: flex; align-items: center; gap: .75rem;
                      flex-wrap: wrap; flex: 0 1 auto; min-width: 0; }}
  .header-example {{ width: 340px; max-width: calc(100vw - 3rem); }}
  @media (max-width: 1100px) {{
    .header-sub {{ display: none; }}
    .header-example {{ width: 260px; }}
  }}
  @media (max-width: 720px) {{
    .header-controls {{ margin-left: 0; width: 100%; }}
    .header-example {{ flex: 1 1 200px; width: auto; }}
  }}
  /* Document bar: the open models as tabs with an underline, the actions
     to the right as quiet text, a hairline under the whole bar. */
  .docs-bar {{ border-bottom: 1px solid var(--p-line); }}
  .doc-tab {{ padding: .35rem .7rem; border-bottom: 2px solid transparent; cursor: pointer;
              color: var(--p-muted); font-size: .9rem; display: inline-flex; align-items: center;
              gap: .4rem; margin-bottom: -1px; }}
  .doc-tab:hover {{ color: var(--p-ink); }}
  .doc-tab.active {{ color: var(--p-ink); border-bottom-color: var(--p-accent); font-weight: 500; }}
  .doc-tab .q-icon {{ font-size: 1rem; opacity: .55; }}
  .doc-tab .q-icon:hover {{ opacity: 1; }}
  .doc-tab .q-icon.kind {{ opacity: .8; }}
  .doc-tab.active .q-icon.kind {{ color: var(--p-accent-ink); opacity: 1; }}
  /* Icons beside words: a notch smaller than Quasar's default. */
  .q-btn .q-icon.on-left {{ font-size: 1.3em; margin-right: .35em; }}
  .q-tab__icon {{ font-size: 1.15rem; }}
  .q-tab--inactive .q-tab__icon {{ opacity: .7; }}
  .q-chip__icon--left {{ font-size: 1.1em; margin-right: .3em; opacity: .85; }}
  .q-expansion-item .q-item__section--avatar {{ min-width: 2rem; padding-right: .5rem; }}
  .q-expansion-item .q-item__section--avatar .q-icon {{ font-size: 1.25rem; color: var(--p-muted); }}
  .vsep {{ width: 1px; height: 1.2rem; background: var(--p-line); margin: 0 .35rem; }}
  /* Body: editor (fixed 440px, sticky) beside the results; on narrow windows
     the row wraps into one column. */
  .editor-row {{ flex-wrap: nowrap; }}
  @media (max-width: 1000px) {{
    .editor-row {{ flex-wrap: wrap; }}
    .editor-col {{ width: 100% !important; position: static !important;
                   max-height: none !important; overflow: visible !important; }}
  }}
  /* Footer: one line of provenance in mono, like the status bar of a tool. */
  .poster-footer {{ border-top: 1px solid var(--p-line); color: var(--p-muted);
                    font-family: 'IBM Plex Mono', 'Menlo', monospace; font-size: .74rem;
                    display: flex; flex-wrap: wrap; gap: .4rem 1.5rem; }}
  .poster-footer a {{ color: var(--p-muted); text-decoration: none;
                      border-bottom: 1px solid var(--p-line); }}
  .poster-footer a:hover {{ color: var(--p-accent-ink); }}

  .thin-scroll::-webkit-scrollbar {{ width: 6px; }}
  .thin-scroll::-webkit-scrollbar-thumb {{ background: var(--p-scroll); border-radius: 3px; }}
  .thin-scroll::-webkit-scrollbar-track {{ background: transparent; }}
  /* The "live" mark of the preview: a still dot in the accent. */
  .pulse-dot {{ width: 8px; height: 8px; border-radius: 9999px; background: var(--p-accent); }}
</style>
"""


# Help texts that depend on the model kind: in a direct complex the atoms live
# on the VERTICES (what each perspective observes) and formulas are evaluated
# facet by facet, with no closures in between.
_ATOMS_WORLDS = (
    "Declare each atom and the worlds where it is **true**. With atoms, the "
    "figures label the worlds with their literals and you can evaluate formulas."
)
ATOMS_HELP = {
    "kb": _ATOMS_WORLDS, "knowledge": _ATOMS_WORLDS, "belief": _ATOMS_WORLDS,
    "simplicial": (
        "Atoms are assigned to **vertices**: which perspectives observe it "
        "true and which false; the rest do not know it. A facet satisfies "
        "the atom if one of its vertices observes it true."
    ),
}
_FORMULA_WORLDS = (
    "Syntax: declared atoms, `K_a`, `B_a`, `~`/`¬`, `&`, `|`, `->`, "
    "`bot`, parentheses. Evaluated **world by world** on the model already "
    "completed by the closures."
)
FORMULA_HELP = {
    "kb": _FORMULA_WORLDS, "knowledge": _FORMULA_WORLDS, "belief": _FORMULA_WORLDS,
    "simplicial": (
        "Syntax: declared atoms, `K_a`, `B_a`, `~`/`¬`, `&`, `|`, `->`, "
        "`bot`, parentheses. Evaluated **facet by facet** with the vertex-based "
        "semantics; the complex must be valid."
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


def figure_caption(caption: str) -> None:
    """A paper-style caption: "Figure 2a. Proper model, knowledge R_a (S5)".

    The adapters produce "Fig. 2a · proper model, knowledge R_a (S5)"; the
    number becomes the bold label and the text starts with a capital.
    """
    import html as _html
    import re as _re

    m = _re.match(r"\s*Fig\.?\s*([0-9]+[a-z]?)\s*·\s*(.*)$", caption)
    if m:
        number, text = m.group(1), m.group(2).strip()
        body = f"<b>Figure {number}.</b> {_html.escape(text[:1].upper() + text[1:])}"
    else:
        body = _html.escape(caption)
    ui.html(f'<div class="fig-caption">{body}</div>').classes("w-full")


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


def card_title(text: str):
    """Panel title of the visual system: a short label in muted ink.

    Returns the label so a caller can put it in a row with other things
    (the preview puts its status at the far right); ``panel_head`` is the
    row-with-hairline variant for the common case.
    """
    return ui.label(text).classes("eyebrow")


def panel_head(text: str):
    """The title row of a panel: label at the left, a hairline under the
    row, and the row itself returned so the caller can add things at the
    right (status marks, a spinner)."""
    with ui.element("div").classes("panel-head") as row:
        ui.label(text).classes("eyebrow")
        ui.element("div").classes("grow")
    return row


def swatch(color: str):
    """The small square of an agent's colour, next to its name: the same
    colour its edges have in every figure."""
    return ui.element("span").classes("swatch").style(f"background:{color}")


# ROLE tones, as CSS variables so they follow the page's theme: green for
# "valid / done", amber for "to be completed", rose for "rejected", and
# muted for anything that is a label rather than a verdict.
TONES = {
    "ok": "var(--p-ok)", "warn": "var(--p-warn)",
    "bad": "var(--p-bad)", "done": "var(--p-ok)", "info": "var(--p-muted)",
}


def tint(color: str, alpha: float) -> str:
    """A translucent wash of ``color`` (a hex or a CSS variable), for backgrounds."""
    return f"color-mix(in srgb, {color} {int(alpha * 100)}%, transparent)"


def status(text: str, tone: str):
    """A verdict said in words: one small coloured dot and the text in ink.

    The dot carries the tone (green = valid / done, amber = to be completed,
    rose = rejected); the words carry the meaning.
    """
    with ui.row().classes("items-center gap-1 no-wrap") as row:
        ui.element("span").style(
            f"display:inline-block;width:.55em;height:.55em;border-radius:9999px;"
            f"background:{TONES[tone]}")
        ui.label(text).classes("text-sm font-medium ink")
    return row


def chip(text: str, tone: str, icon=None):
    """Status chip with a role tone (see ``TONES``).

    The color goes through the ``color`` parameter (NiceGUI accepts CSS and
    applies it as a style) and not through ``.style()``: the ``bg-primary``
    that Quasar adds by default carries ``!important`` and would override
    any inline style.
    """
    c = TONES[tone]
    return ui.chip(text, icon=icon, color=tint(c, .12), text_color=c) \
        .classes("font-medium").props("dense")


# Icon per model kind, for the chips of the models bar.
KIND_ICON = {"kb": "hub", "knowledge": "visibility",
             "belief": "psychology", "simplicial": "change_history"}


def quasar_colors(name: str) -> None:
    """Quasar's palette for theme ``name``: ``primary`` is the accent fill
    (buttons carry ``text-color=dark`` on top of it, so ``dark`` is set to
    what must sit on the fill); ``secondary`` is the accent as text, which
    is what tabs use; ``dark_page`` is the page, so menus, dialogs and the
    body follow the palette on their own."""
    p = PALETTES[name]
    ui.colors(
        primary=p["accent"], secondary=p["accent_ink"], accent=p["pink"],
        dark=p["surface"] if name == "dark" else p["on_accent"], dark_page=p["page"],
        positive=p["green"], negative=p["pink"], warning=p["yellow"], info=p["muted"],
    )


def apply_theme(name: str = "dark"):
    """Dark or light mode, Quasar palette and the CSS, once per page.

    Inside the page function on purpose: NiceGUI 3 forbids UI calls in the
    global scope when ``@ui.page`` is used. Returns the ``ui.dark_mode``
    element, which is what switches the theme later (``Page.set_theme``):
    our CSS variables hang from Quasar's ``body--dark`` / ``body--light``
    classes, so flipping it repaints the whole page without a reload.
    """
    dark = ui.dark_mode(name == "dark")
    quasar_colors(name)
    ui.add_head_html(HEAD_HTML)
    return dark


def take(input_widget) -> str:
    """Read and clear an "add" field, returning the typed name (stripped)."""
    name = (input_widget.value or "").strip()
    input_widget.value = ""
    return name

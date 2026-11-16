"""Visualisation for every model in the project: text diagrams and images.

Three functions, each accepting any model (a :class:`RelationalFrame`, a
:class:`KnowledgeBeliefFrame` or a :class:`SimplicialBeliefModel`):

    visualize(model)            -> str, a text diagram (no dependencies)
    show(model, "name")         -> writes outputs/name.png, returns the path
    to_dot(model)               -> str, Graphviz DOT source

The style is inferred: an S5 relation is drawn undirected without self-loops,
a KD45/K45 one with arrows, an invalid frame with its missing edges dashed in
red. Relational models go through Graphviz (``dot``), simplicial ones through
matplotlib (``dim=2``) or plotly (``dim=3``, HTML). The core modules are
imported lazily where a renderer needs them, so no model class knows about
drawing. Figure conventions: docs/03 §7, docs/06, docs/08 §5.
"""

from __future__ import annotations

import contextlib
import itertools
import os
import shutil
import subprocess
import tempfile
import threading
import warnings
from typing import TYPE_CHECKING, Dict, List, Set

if TYPE_CHECKING:
    from relational_frame import Agent, RelationalFrame

# Default directory where all generated artifacts (.dot / images) are written.
OUTPUT_DIR = "outputs"

# Qualitative, colour-blind-safe palette (Okabe-Ito). Agents are assigned a
# colour by their sorted position; the list cycles if there are more agents
# than colours.
PALETTE = (
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#009E73",  # green
    "#CC79A7",  # purple
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#000000",  # black
)

# Colour used to highlight edges/worlds that an invalid frame is missing.
MISSING_COLOR = "#D00000"

# Fill colours for the belief subcomplexes of a simplicial model. Deliberately
# disjoint from PALETTE: a facet's fill (a belief signature) must never be
# mistaken for a node's colour (an agent) in the same drawing.
BELIEF_PALETTE = ("#7B4FA3", "#D98A00", "#2E8B57", "#B23A48", "#3A6EA5", "#8C6D1F")

# Ink themes: everything in a figure that is not data (text, node fills, pads,
# the faint skeleton, the "missing" red). ``light`` is the default (paper,
# CLI); the GUI draws with ``dark`` inside ``with ink_theme("dark"):``, which
# is per thread so concurrent renders never leak into each other. Agent and
# belief colours are data and never change.
INK_THEMES = {
    "light": {
        "page": "white",          # the page (3-D HTML; the others go transparent)
        "text": "#222222",        # labels, captions, legend
        "text_soft": "#333333",   # agent names in the dead-end line, notes
        "muted": "#777777",       # "legal in K45" marks, the dimension axis
        "faint": "#999999",       # the 1-skeleton, lattice edges
        "node_fill": "#f4f6f8",   # worlds (and lattice boxes without a colour)
        "node_edge": "#333333",
        "dead_fill": "#FDE7E7",   # a dead-end world under Axiom D
        "missing": MISSING_COLOR, # what the closures will add; the error red
        "neutral": "#dddddd",     # facets in no belief subcomplex
        "pad": "white",           # the pad behind a facet name / revision mark
        "gone": "#aab2bf",        # eliminated facets, their hatching and label
        "lose": "#9aa6b5",        # losing candidates of a revision
        "win": "#c0432b",         # the winner of a revision
        "marker_edge": "#222222", # outline of the agent markers
    },
    "dark": {
        "page": "#05081A",
        "text": "#E7EAF6",
        "text_soft": "#C9CFE6",
        "muted": "#9BA4CB",
        "faint": "#6F789C",
        "node_fill": "#1A2246",
        "node_edge": "#C9CFE6",
        "dead_fill": "#4A1F2B",
        "missing": "#FF7E9A",
        "neutral": "#3A4266",
        "pad": "#0B1128",
        "gone": "#6F789C",
        "lose": "#9BA4CB",
        "win": "#FF7E9A",
        "marker_edge": "#E7EAF6",
    },
}
_ink_local = threading.local()


def ink() -> Dict[str, str]:
    """The ink theme of the current render (this thread's override, else ``light``)."""
    return INK_THEMES[getattr(_ink_local, "name", None) or "light"]


@contextlib.contextmanager
def ink_theme(name: str):
    """Draw with ``name`` as the ink theme inside the block, in this thread only."""
    if name not in INK_THEMES:
        raise ValueError(f"unknown ink theme {name!r}; one of {sorted(INK_THEMES)}")
    previous = getattr(_ink_local, "name", None)
    _ink_local.name = name
    try:
        yield
    finally:
        _ink_local.name = previous


def _missing() -> str:
    """The "missing / error" colour of the current ink theme."""
    return ink()["missing"]


# --------------------------------------------------------------------------- #
# Public API: three functions, any model
# --------------------------------------------------------------------------- #
def visualize(model, agent: "Agent | None" = None, valuation=None) -> str:
    """Return a dependency-free text diagram of any model.

    * relational frame -- every world with the worlds it reaches in one step
      (``->``); a self-loop is marked ``(self)``, so the KD45 cluster structure
      is easy to spot.
    * knowledge+belief model -- the same, for both relations.
    * simplicial model -- its facet listing (``model.describe()``).

    Args:
        agent: If given, show only that agent's relation; otherwise show all.
        valuation: Relational models only -- a Kripke valuation ``v : P -> 2^W``;
            each world line then carries its literals, e.g. ``w1 (¬P, Q) -> ...``.
    """
    kind = _kind(model)
    if kind == "simplicial":
        return model.describe()
    if kind == "knowledge_belief":
        belief_logic = "KD45" if getattr(model, "axiom_d", True) else "K45"
        return (
            "KNOWLEDGE (S5):\n"
            + _visualize_frame(model.knowledge, agent, valuation)
            + f"\nBELIEF ({belief_logic}):\n"
            + _visualize_frame(model.belief, agent, valuation)
        )
    return _visualize_frame(model, agent, valuation)


def show(
    model,
    name: str = "model",
    title: str | None = None,
    *,
    dim: int = 2,
    open: bool = False,
    output_dir: str = OUTPUT_DIR,
    image_format: str = "png",
    omit_self_loops: bool | None = None,
    undirected_symmetric: bool | None = None,
    highlight_missing: bool = True,
    valuation=None,
    assignment=None,
    logic: str | None = None,
    engine: str = "auto",
    revision=None,
    font_scale: float = 1.0,
    transparent: bool = False,
) -> str:
    """Draw any model to ``<output_dir>/<name>.<format>`` and return the path.

        show(belief_frame, "belief")        # arrows
        show(knowledge_frame, "knowledge")  # S5: undirected, no self-loops
        show(kb_model, "figure1")           # knowledge + belief in one figure
        show(simplicial, "figure3")         # filled simplices (matplotlib)
        show(simplicial, "figure3", dim=3)  # interactive 3-D (plotly, .html)

    Args:
        title: caption (default ``name``); relational captions get the validity verdict.
        dim: simplicial only, 2 (image) or 3 (HTML).
        open: open the file in the OS viewer afterwards.
        logic: relational frames only; ``"S5"`` draws a half-built frame as
            knowledge and measures what is missing against the S5 closure.
        omit_self_loops, undirected_symmetric: style overrides (default inferred).
        highlight_missing: dash in red what an invalid frame lacks, and its dead ends.
        valuation: a Kripke valuation; worlds are labelled with their literals.
            On a simplicial model it is turned into the induced vertex
            assignment (``assignment.assignment_from_model``).
        assignment: simplicial only, the vertex assignment ``L : N -> 3^P``; each
            node shows the literals it observes (value 2 draws nothing). Wins
            over ``valuation``.
        engine: simplicial only; ``"dot"`` draws the complex as a Graphviz graph
            (editable ``.dot``, no filled areas; labels from ``valuation`` only).
        revision: simplicial, 2-D only: a ``Revision`` from
            ``poster/poster-code/revision.py`` (anything with ``eliminated``,
            ``lost``, ``winners``, ``candidates``) drawn over the complex, see
            :func:`_draw_revision`.
        font_scale: simplicial only, multiplies every label (and marker) size.
        transparent: no background (Graphviz and matplotlib routes).

    Raises:
        RuntimeError: the Graphviz ``dot`` binary is not on ``PATH``.
        TypeError: not a model of the project, ``assignment`` on a relational
            model, or ``revision`` outside the 2-D route.
    """
    kind = _kind(model)
    caption = title if title is not None else name
    if kind == "simplicial":
        if assignment is None and valuation is not None:
            from assignment import assignment_from_model

            assignment = assignment_from_model(model, valuation)
        if revision is not None and (engine == "dot" or dim == 3):
            raise TypeError(
                "revision is drawn only by the 2-D matplotlib route; it needs "
                "filled facets to hatch and a layout to put an arrow on. Drop "
                'engine="dot" / dim=3, or draw the revision separately.'
            )
        if engine == "dot":
            dot_source = _dot_simplicial(model, caption, valuation, assignment)
            path = _write_and_run_dot(dot_source, name, image_format, output_dir,
                                      transparent=transparent)
        elif dim == 3:
            path = _show_simplicial_3d(model, name, output_dir, caption,
                                       assignment=assignment, font_scale=font_scale)
        else:
            path = _show_simplicial(model, name, output_dir, caption, image_format,
                                    assignment=assignment, revision=revision,
                                    font_scale=font_scale, transparent=transparent)
    else:
        if assignment is not None:
            raise TypeError(
                "assignment is a vertex labelling for SIMPLICIAL models; for a "
                "relational model pass valuation (v : P -> 2^W) instead."
            )
        dot_source = to_dot(
            model,
            title=caption,
            omit_self_loops=omit_self_loops,
            undirected_symmetric=undirected_symmetric,
            highlight_missing=highlight_missing,
            valuation=valuation,
            logic=logic,
        )
        path = _write_and_run_dot(dot_source, name, image_format, output_dir,
                                  transparent=transparent)
    if open:
        _open_file(path)
    return path


def preview(model, title: str | None = None, *, dim: int = 2) -> str:
    """Render a model to a temporary file and open it (a quick look while exploring)."""
    return show(
        model,
        name=f"preview_{_kind(model)}",
        title=title,
        dim=dim,
        open=True,
        output_dir=tempfile.gettempdir(),
    )


def to_dot(
    model,
    title: str | None = None,
    *,
    omit_self_loops: bool | None = None,
    undirected_symmetric: bool | None = None,
    highlight_missing: bool = True,
    valuation=None,
    logic: str | None = None,
) -> str:
    """Graphviz DOT source for any model; the arguments are those of :func:`show`
    (``None`` = infer). A simplicial model gets the graph rendering of
    :func:`_dot_simplicial`; the style keywords apply to relational models."""
    kind = _kind(model)
    if kind == "knowledge_belief":
        return _dot_knowledge_belief(model, title, omit_self_loops, valuation,
                                     undirected_symmetric, highlight_missing)
    if kind == "frame":
        return _dot_frame(
            model, title, omit_self_loops, undirected_symmetric, highlight_missing,
            valuation, logic=logic,
        )
    if kind == "simplicial":
        return _dot_simplicial(model, title, valuation)
    raise TypeError(f"No DOT form for {type(model).__name__}; use show(model, name).")


def _dot_simplicial(model, title: str | None = None, valuation=None, assignment=None) -> str:
    """Graphviz DOT source for a simplicial model: an editable text source at the
    cost of the filled areas. A two-vertex facet is an edge; a larger facet is a
    hyperedge, drawn as a point joined to its vertices. Colours and labels match
    :func:`_show_simplicial`.
    """
    from simplicial import label_facet, label_node

    agents = sorted(model.agents, key=str)
    node_color = agent_colors(model)
    signature_color = _signature_colors(model, agents)

    assignment = dict(assignment or {})
    if not assignment and valuation:
        from assignment import assignment_from_model

        assignment = assignment_from_model(model, valuation)

    lines = [
        "graph SimplicialComplex {",          # undirected: a facet has no direction
        f'  graph [bgcolor="{ink()["page"]}", fontname="Helvetica", labelloc="b", '
        f'fontcolor="{ink()["text"]}"]',
        '  node  [fontname="Helvetica", fontsize=11]',
        f'  edge  [penwidth=6, fontcolor="{ink()["text"]}"]',   # an edge IS a facet: thick, like a fill
        "  layout=neato",                      # geometric, like the matplotlib view
        "  overlap=false",                     # neato may stack nodes otherwise
        "  splines=true",                      # route edges around nodes, not through
    ]
    if title:
        lines.append(f'  label="{_dot_escape(title)}"')
        lines.append('  fontsize=14')

    for node in sorted(model.nodes, key=label_node):
        # Visible label: the agent and its literals; the full label_node string
        # is the DOT id and the tooltip. "\\n" is Graphviz's line break, so the
        # pieces are escaped separately.
        literals = ", ".join(node_literals(assignment, node)) if assignment else ""
        caption = _dot_escape(node.agent)
        if literals:
            caption += "\\n(" + _dot_escape(literals) + ")"
        lines.append(
            f'  {_dot_id(label_node(node))} '
            f'[label="{caption}", tooltip="{_dot_escape(label_node(node))}", '
            f'shape=circle, style=filled, '
            f'fillcolor="{node_color[node.agent]}", fontcolor="white", '
            f'width=0.45, fixedsize=true]'
        )

    for facet in sorted(model.facets, key=label_facet):
        color = signature_color[_belief_signature(model, facet, agents)]
        world = model.world_of_facet.get(facet)
        caption = _dot_escape(str(world)) if world is not None else ""
        members = sorted(facet, key=label_node)
        if len(members) == 2:
            u, v = members
            lines.append(
                f'  {_dot_id(label_node(u))} -- {_dot_id(label_node(v))} '
                f'[color="{color}", label="{caption}", fontsize=10]'
            )
        else:
            hub = _dot_id("facet_" + label_facet(facet))   # xlabel: no text fits in a point
            lines.append(
                f'  {hub} [label="", xlabel="{caption}", shape=point, width=0.18, '
                f'color="{color}", fontsize=10]'
            )
            for member in members:
                lines.append(
                    f'  {hub} -- {_dot_id(label_node(member))} '
                    f'[color="{color}", penwidth=4]'
                )

    lines.append("}")
    return "\n".join(lines)


def world_literals(valuation, world) -> List[str]:
    """A world's literals under a (total) Kripke valuation: ``P`` or ``¬P`` per atom."""
    return [
        (str(atom) if world in trues else f"¬{atom}")
        for atom, trues in sorted(valuation.items(), key=lambda kv: str(kv[0]))
    ]


def node_literals(assignment, node) -> List[str]:
    """A perspective's observed literals: value 1 -> ``P``, 0 -> ``¬P``, 2 -> nothing."""
    out: List[str] = []
    for atom, value in sorted(assignment.get(node, {}).items(), key=lambda kv: str(kv[0])):
        if value == 1:
            out.append(str(atom))
        elif value == 0:
            out.append(f"¬{atom}")
    return out


def agent_colors(model) -> Dict["Agent", str]:
    """``agent -> hex colour`` by sorted position in the palette (stable per model)."""
    ordered = sorted(model.agents, key=str)
    return {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(ordered)}


# --------------------------------------------------------------------------- #
# Dispatch and style inference
# --------------------------------------------------------------------------- #
def _kind(model) -> str:
    """Identify a model by duck typing: 'frame', 'knowledge_belief' or 'simplicial'."""
    if hasattr(model, "facets"):
        return "simplicial"
    if hasattr(model, "knowledge") and hasattr(model, "belief"):
        return "knowledge_belief"
    if hasattr(model, "relations"):
        return "frame"
    raise TypeError(
        f"Cannot visualise {type(model).__name__}: expected a RelationalFrame, a "
        "KnowledgeBeliefFrame or a SimplicialBeliefModel."
    )


# --------------------------------------------------------------------------- #
# Text diagrams
# --------------------------------------------------------------------------- #
def _visualize_frame(
    frame: "RelationalFrame", agent: "Agent | None" = None, valuation=None
) -> str:
    """Text diagram of one relational frame (see :func:`visualize`)."""
    chosen = [agent] if agent is not None else sorted(frame.agents, key=str)
    lines = []
    for a in chosen:
        if a not in frame.agents:
            raise ValueError(f"Unknown agent {a!r}.")
        lines.append(f"Agent {a!r}:")
        for w in sorted(frame.worlds, key=str):
            successors = frame.successors(a, w)
            targets = sorted(successors, key=str)
            rendered = ", ".join(f"{t}{' (self)' if t == w else ''}" for t in targets)
            lits = f" ({', '.join(world_literals(valuation, w))})" if valuation else ""
            if successors:
                marker = ""
            elif frame.axiom_d:
                marker = "   <- NOT SERIAL (dead end, Axiom D)"
            else:
                marker = "   <- defunct (no successors; legal in K45)"
            lines.append(f"    {w}{lits} -> {{{rendered}}}{marker}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# DOT building blocks (shared by both relational renderers)
# --------------------------------------------------------------------------- #
def _dot_escape(value) -> str:
    """Escape a value for use inside a double-quoted DOT string (quotes/backslash)."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _dot_id(value) -> str:
    """Return a safely double-quoted DOT identifier for any world/agent label."""
    return f'"{_dot_escape(value)}"'


def _world_label_attr(valuation, world, dead_for=(), colors=None,
                      error: bool = True) -> str:
    """DOT ``label=...`` for a world: its literals and, as a line ``⊘ a, b`` in
    the agents' colours, the agents for whom it is a dead end (``dead_for``);
    the mark is red when ``error`` (KD45) and grey otherwise (legal in K45).
    Empty string when there is nothing to show."""
    literals = world_literals(valuation, world) if valuation else []
    dead_for = list(dead_for)
    if not dead_for:
        if not literals:
            return ""
        text = _dot_escape(str(world)) + "\\n(" + _dot_escape(", ".join(literals)) + ")"
        return f'label="{text}"'
    rows = [_html_escape(world)]
    if literals:
        rows.append(f'<FONT POINT-SIZE="10">({_html_escape(", ".join(literals))})</FONT>')
    mark = _missing() if error else ink()["muted"]
    names = ", ".join(
        f'<FONT COLOR="{(colors or {}).get(a, ink()["text_soft"])}"><B>{_html_escape(a)}</B></FONT>'
        for a in dead_for
    )
    rows.append(f'<FONT COLOR="{mark}">&#9711;</FONT> {names}')
    return "label=<" + "<BR/>".join(rows) + ">"


def _dead_ends_by_world(frame) -> Dict:
    """``world -> [agents]`` for whom the world is a dead end (inverts ``dead_ends``)."""
    out: Dict = {}
    for a, stuck in sorted(frame.dead_ends().items(), key=lambda kv: str(kv[0])):
        for w in stuck:
            out.setdefault(w, []).append(a)
    return out


def _dead_end_cell(flagged: bool) -> str:
    """Legend cell explaining the ``⊘ a, b`` line: red under D, grey under K45."""
    if flagged:
        return _note_cell("&#9711; a, b = dead end for those agents (Axiom D)", _missing())
    return _note_cell("&#9711; a, b = those agents believe nothing there (legal in K45)",
                      ink()["muted"])


def _html_escape(value) -> str:
    """Escape a value for use inside a Graphviz HTML-like label."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _dot_header() -> List[str]:
    """Opening lines of a DOT digraph: layout and default node/edge style."""
    return [
        "digraph Model {",
        "    rankdir=LR;",
        f'    fontname="Helvetica"; fontcolor="{ink()["text"]}"; overlap=false; nodesep=0.4; ranksep=0.6;',
        f'    node [shape=circle, style=filled, fillcolor="{ink()["node_fill"]}",'
        f' color="{ink()["node_edge"]}", fontcolor="{ink()["text"]}", fontname="Helvetica", width=0.5];',
        f'    edge [penwidth=1.6, arrowsize=0.8, fontname="Helvetica", fontcolor="{ink()["text"]}"];',
    ]


def _dot_footer(caption: str, cells: List[str]) -> List[str]:
    """Caption and legend as the graph's bottom label (so they never collide
    with the drawing), then close the graph."""
    rows = [
        "        <TR><TD COLSPAN=\"99\" ALIGN=\"CENTER\">"
        f"<FONT POINT-SIZE=\"13\">{_html_escape(caption)}</FONT></TD></TR>",
    ]
    if cells:
        rows += [
            "        <TR><TD ALIGN=\"CENTER\">",
            '          <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="14" CELLPADDING="0"><TR>',
            *("            " + c for c in cells),
            "          </TR></TABLE>",
            "        </TD></TR>",
        ]
    return [
        '    labelloc="b"; fontsize=11;',
        "    label=<",
        '      <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">',
        *rows,
        "      </TABLE>",
        "    >;",
        "}",
    ]


def _swatch_cell(color: str, text: str, *, round_dot: bool = False) -> str:
    """Legend cell: a coloured mark (square, or a dot for agents) and its meaning."""
    mark = "&#9679;" if round_dot else "&#9632;"
    return (
        f'<TD><FONT COLOR="{color}" POINT-SIZE="15">{mark}</FONT>'
        f' <FONT POINT-SIZE="11">{_html_escape(text)}</FONT></TD>'
    )


def _note_cell(text: str, color: str | None = None) -> str:
    """Legend cell: a short piece of explanatory text."""
    color = ink()["text_soft"] if color is None else color
    return f'<TD><FONT COLOR="{color}" POINT-SIZE="11">{text}</FONT></TD>'


def _sorted_edges(relation):
    """Edges in a stable order, so the generated DOT is deterministic."""
    return sorted(relation, key=lambda e: (str(e[0]), str(e[1])))


def _world_lines(worlds, valuation, dead_for: Dict, colors, flag_dead: bool) -> List[str]:
    """One DOT node line per world, with its label and the dead-end styling."""
    lines = []
    for w in sorted(worlds, key=str):
        attrs = []
        label = _world_label_attr(valuation, w, dead_for.get(w, ()), colors, flag_dead)
        if label:
            attrs.append(label)
        if flag_dead and w in dead_for:
            attrs += [f'fillcolor="{ink()["dead_fill"]}"', f'color="{_missing()}"',
                      'style="filled,dashed"', "penwidth=2"]
        lines.append(f"    {_dot_id(w)}" + (f" [{', '.join(attrs)}]" if attrs else "") + ";")
    return lines


def _edge_lines(edges, attrs: str, omit_self_loops: bool, undirected_symmetric: bool) -> List[str]:
    """One DOT edge line per edge of ``edges`` (a set), with ``attrs``. Self-loops
    are skipped when ``omit_self_loops``; a symmetric pair is drawn once without
    arrowheads when ``undirected_symmetric``."""
    lines = []
    drawn: Set[frozenset] = set()
    for (s, t) in _sorted_edges(edges):
        if omit_self_loops and s == t:
            continue
        if undirected_symmetric and s != t and (t, s) in edges:
            key = frozenset((s, t))
            if key in drawn:
                continue
            drawn.add(key)
            lines.append(f'    {_dot_id(s)} -> {_dot_id(t)} [{attrs}, dir=none];')
        else:
            lines.append(f'    {_dot_id(s)} -> {_dot_id(t)} [{attrs}];')
    return lines


# --------------------------------------------------------------------------- #
# DOT: a single relational frame
# --------------------------------------------------------------------------- #
def _dot_frame(
    frame: "RelationalFrame",
    title: str | None,
    omit_self_loops: bool | None,
    undirected_symmetric: bool | None,
    highlight_missing: bool,
    valuation=None,
    logic: str | None = None,
) -> str:
    """DOT for one frame, one colour per agent. ``logic="S5"`` draws the frame as
    knowledge whatever its current shape and measures what is missing against
    the S5 closure (a half-built knowledge frame would otherwise be judged as
    belief)."""
    as_knowledge = logic == "S5"
    if omit_self_loops is None or undirected_symmetric is None:
        s5 = as_knowledge or frame.logic_label() == "S5"
        omit_self_loops = s5 if omit_self_loops is None else omit_self_loops
        undirected_symmetric = s5 if undirected_symmetric is None else undirected_symmetric

    colors = agent_colors(frame)
    if as_knowledge:
        from relational_frame import s5_closure

        violations = frame.s5_violations()
        logic_name = "S5"
        missing = {a: s5_closure(frame.worlds, frame.relations[a]) - set(frame.relations[a])
                   for a in frame.agents}
    else:
        violations = frame.violations()
        logic_name = frame.logic_label()
        missing = frame.missing_edges()
    status = f"valid {logic_name}" if not violations else f"INVALID: {len(violations)} violation(s)"
    caption = f"{title} — {status}" if title else status

    # Dead ends are named per agent on the world: red under KD45, grey under K45.
    dead_for: Dict = {} if as_knowledge else _dead_ends_by_world(frame)
    flag_dead = highlight_missing and frame.axiom_d and not as_knowledge
    agents = sorted(frame.agents, key=str)
    lines = _dot_header()
    lines += _world_lines(frame.worlds, valuation, dead_for, colors, flag_dead)
    for a in agents:
        lines += _edge_lines(frame.relations[a], f'color="{colors[a]}"',
                             omit_self_loops, undirected_symmetric)
    if highlight_missing:
        for a in agents:
            lines += _edge_lines(missing[a], f'style=dashed, color="{_missing()}"',
                                 omit_self_loops, undirected_symmetric)

    cells = [_swatch_cell(colors[a], a, round_dot=True) for a in agents]
    if cells:
        if highlight_missing and any(missing.values()):
            cells.append(_note_cell("&#9548;&#9548; missing edge", _missing()))
        if dead_for:
            cells.append(_dead_end_cell(flag_dead))
    lines += _dot_footer(caption, cells)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# DOT: knowledge and belief in one figure
# --------------------------------------------------------------------------- #
def _dot_knowledge_belief(kb, title: str | None, omit_self_loops: bool | None,
                          valuation=None,
                          undirected_symmetric: bool | None = None,
                          highlight_missing: bool = True) -> str:
    """DOT for a knowledge+belief model: knowledge as thin arrow-less lines,
    belief as bold arrows, both coloured by agent. ``highlight_missing`` dashes
    in red the S5 edges knowledge lacks, the 4/5 edges belief lacks, belief
    arrows outside knowledge and, under Axiom D, dead-end worlds."""
    omit_self_loops = True if omit_self_loops is None else omit_self_loops
    undirected_symmetric = True if undirected_symmetric is None else undirected_symmetric
    colors = agent_colors(kb)
    status = "valid" if kb.is_valid() else "INVALID"
    caption = f"{title} — {status}" if title else status
    agents = sorted(kb.agents, key=str)

    missing_k: Dict = {}
    missing_b: Dict = {}
    if highlight_missing:
        from relational_frame import s5_closure

        for a in agents:
            rel = kb.knowledge.relations[a]
            missing_k[a] = s5_closure(kb.worlds, rel) - set(rel)
        missing_b = kb.belief.missing_edges()
    dead_for = _dead_ends_by_world(kb.belief)
    flag_dead = highlight_missing and kb.axiom_d

    lines = _dot_header()
    lines += _world_lines(kb.worlds, valuation, dead_for, colors, flag_dead)
    for a in agents:
        lines += _edge_lines(kb.knowledge.relations[a], f'color="{colors[a]}", penwidth=0.7',
                             omit_self_loops, undirected_symmetric)
    outside_knowledge = False
    for a in agents:
        belief = kb.belief.relations[a]
        outside = {e for e in belief if e not in kb.knowledge.relations[a]} if highlight_missing else set()
        lines += _edge_lines(belief - outside, f'color="{colors[a]}", penwidth=2.6, arrowsize=1.0',
                             omit_self_loops, False)
        red = _edge_lines(outside, f'color="{_missing()}", penwidth=2.6, arrowsize=1.0',
                          omit_self_loops, False)
        outside_knowledge = outside_knowledge or bool(red)
        lines += red
    any_missing = False
    for a in agents:
        thin = _edge_lines(missing_k.get(a, set()), f'style=dashed, color="{_missing()}", penwidth=0.7',
                           omit_self_loops, undirected_symmetric)
        bold = _edge_lines(missing_b.get(a, set()),
                           f'style=dashed, color="{_missing()}", penwidth=2.6, arrowsize=1.0',
                           omit_self_loops, False)
        any_missing = any_missing or bool(thin or bold)
        lines += thin + bold

    cells = [_swatch_cell(colors[a], a, round_dot=True) for a in agents]
    if cells:
        cells.append(_note_cell("&#9472; knowledge (thin)"))
        cells.append(_note_cell("&#10142; belief (bold)"))
        if any_missing:
            cells.append(_note_cell("&#9548;&#9548; missing edge", _missing()))
        if outside_knowledge:
            cells.append(_note_cell("&#10142; belief outside knowledge", _missing()))
        if dead_for:
            cells.append(_dead_end_cell(flag_dead))
    lines += _dot_footer(caption, cells)
    return "\n".join(lines)


def _write_and_run_dot(dot_source: str, name: str, image_format: str, output_dir: str,
                       transparent: bool = False) -> str:
    """Write ``<output_dir>/<name>.dot`` and render it with Graphviz; ``transparent``
    drops the page colour.

    Raises:
        RuntimeError: if the ``dot`` binary is not on ``PATH``.
    """
    if shutil.which("dot") is None:
        raise RuntimeError(
            "Graphviz 'dot' not found on PATH. Install it (e.g. 'brew install "
            "graphviz') or use to_dot(model) to export the source manually."
        )
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.join(output_dir, os.path.basename(name))   # never outside output_dir
    dot_path = f"{base}.dot"
    image_path = f"{base}.{image_format}"
    if transparent:
        dot_source = dot_source.replace('bgcolor="white"', 'bgcolor="transparent"')
    with open(dot_path, "w", encoding="utf-8") as fh:
        fh.write(dot_source)
    cmd = ["dot", f"-T{image_format}", dot_path, "-o", image_path]
    if transparent:
        cmd.insert(1, "-Gbgcolor=transparent")
    subprocess.run(cmd, check=True)
    return image_path


def _open_file(path: str) -> None:
    """Open ``path`` in the OS default application; best effort, never raises."""
    import sys

    abspath = os.path.abspath(path)
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", abspath], check=False)
        elif sys.platform.startswith("win"):
            os.startfile(abspath)  # type: ignore[attr-defined]  # noqa: S606
        elif sys.platform.startswith("linux") and shutil.which("xdg-open"):
            subprocess.run(["xdg-open", abspath], check=False)
        else:
            import webbrowser

            webbrowser.open(f"file://{abspath}")
    except Exception:  # pragma: no cover - opening is a convenience, never fatal
        import webbrowser

        webbrowser.open(f"file://{abspath}")


# --------------------------------------------------------------------------- #
# Simplicial belief models (facets drawn as filled simplices)
# --------------------------------------------------------------------------- #
def facet_name(model, facet) -> str:
    """The facet's world as a short label (``(w, u)`` for a copy); empty if unknown."""
    world = model.world_of_facet.get(facet) if hasattr(model, "world_of_facet") else None
    if world is None:
        return ""
    if isinstance(world, tuple):
        return "(" + ", ".join(map(str, world)) + ")"
    return str(world)


def _belief_signature(model, facet, agents):
    """The tuple of agents whose belief subcomplex contains ``facet``."""
    return tuple(a for a in agents if facet in model.belief_facets.get(a, ()))


def signature_label(model, sig, agents) -> str:
    """Legend text for a belief signature (``belief: a+b``, ``belief: none``); on a
    knowledge-only complex the full signature reads ``knowledge only (S_a = S)``.
    Shared by the 2-D, 3-D and Hasse renderers."""
    if getattr(model, "is_knowledge_only", False) and tuple(sig) == tuple(agents):
        return "knowledge only (S_a = S)"
    return "belief: " + ("+".join(map(str, sig)) if sig else "none")


def _node_key(node):
    """A run-stable sort key for a node (``str(node)`` orders a frozenset by hash)."""
    agent = getattr(node, "agent", None)
    cls = getattr(node, "cls", None)
    if agent is None or cls is None:
        return (str(node), ())
    return (str(agent), tuple(sorted(str(w) for w in cls)))


def _signature_colors(model, agents) -> Dict[tuple, str]:
    """Belief signature -> fill colour, handed out in a stable order; the empty
    signature is neutral."""
    signatures = {_belief_signature(model, f, agents) for f in model.facets}
    colors = {(): ink()["neutral"]}
    for i, sig in enumerate(sorted((s for s in signatures if s), key=lambda s: (len(s), s))):
        colors[sig] = BELIEF_PALETTE[i % len(BELIEF_PALETTE)]
    return colors


def _skeleton_edges(model):
    """The 1-skeleton: every pair of nodes sharing a facet. Drives the layouts."""
    edges = set()
    for facet in model.facets:
        for u, v in itertools.combinations(facet, 2):
            edges.add(frozenset((u, v)))
    # Sorted: the order of the spring forces changes the last digits of the layout.
    return sorted((tuple(sorted(e, key=_node_key)) for e in edges),
                  key=lambda e: tuple(map(_node_key, e)))


def _spring_layout(nodes, edges, iterations: int = 250):
    """A deterministic Fruchterman-Reingold layout: nodes start on a circle (in
    sorted order, so PNGs are reproducible) and relax under edge attraction,
    all-pairs repulsion and a weak gravity that keeps isolated nodes near.
    Returns ``node -> (x, y)``."""
    import math

    nodes = sorted(nodes, key=_node_key)
    n = len(nodes)
    if n == 0:
        return {}
    pos = {
        v: [math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)]
        for i, v in enumerate(nodes)
    }
    k = 1.0 / math.sqrt(n)
    gravity = 0.08
    for _ in range(iterations):
        disp = {v: [0.0, 0.0] for v in nodes}
        for i in range(n):
            for j in range(i + 1, n):
                vi, vj = nodes[i], nodes[j]
                dx = pos[vi][0] - pos[vj][0]
                dy = pos[vi][1] - pos[vj][1]
                d = math.hypot(dx, dy) or 1e-6
                f = k * k / d
                disp[vi][0] += dx / d * f
                disp[vi][1] += dy / d * f
                disp[vj][0] -= dx / d * f
                disp[vj][1] -= dy / d * f
        for (u, v) in edges:
            dx = pos[u][0] - pos[v][0]
            dy = pos[u][1] - pos[v][1]
            d = math.hypot(dx, dy) or 1e-6
            f = d * d / k
            disp[u][0] -= dx / d * f
            disp[u][1] -= dy / d * f
            disp[v][0] += dx / d * f
            disp[v][1] += dy / d * f
        cx = sum(pos[v][0] for v in nodes) / n
        cy = sum(pos[v][1] for v in nodes) / n
        for v in nodes:
            disp[v][0] -= (pos[v][0] - cx) * gravity
            disp[v][1] -= (pos[v][1] - cy) * gravity
        for v in nodes:   # constant step cap (the "temperature")
            dx, dy = disp[v]
            d = math.hypot(dx, dy) or 1e-6
            pos[v][0] += dx / d * min(d, 0.08)
            pos[v][1] += dy / d * min(d, 0.08)
    return _park_isolated({v: (p[0], p[1]) for v, p in pos.items()}, edges)


def _park_isolated(pos, edges):
    """Place the nodes no edge touches in a row just past the connected part,
    one median edge-length apart (2-D or 3-D)."""
    touched = {v for e in edges for v in e}
    loose = sorted((v for v in pos if v not in touched), key=_node_key)
    if not loose or len(loose) == len(pos):
        return pos
    import math

    anchored = [pos[v] for v in pos if v in touched]
    dims = len(anchored[0])
    lengths = sorted(math.dist(pos[u], pos[v]) for u, v in edges)
    step = lengths[len(lengths) // 2] if lengths else 1.0
    centre = [sum(p[c] for p in anchored) / len(anchored) for c in range(dims)]
    right = max(p[0] for p in anchored)
    for i, v in enumerate(loose):
        spot = list(centre)
        spot[0] = right + step * (i + 1)
        pos[v] = tuple(spot)
    return pos


def _rotate_to_horizontal(pos):
    """Rotate a 2-D layout so its principal axis (PCA) is horizontal."""
    import math

    pts = list(pos.values())
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts) / n
    syy = sum((p[1] - my) ** 2 for p in pts) / n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts) / n
    # Angle of the principal eigenvector of [[sxx, sxy], [sxy, syy]].
    theta = 0.5 * math.atan2(2 * sxy, sxx - syy)
    c, s_ = math.cos(-theta), math.sin(-theta)
    return {
        v: ((p[0] - mx) * c - (p[1] - my) * s_, (p[0] - mx) * s_ + (p[1] - my) * c)
        for v, p in pos.items()
    }


def _strip_order(model):
    """A node order in which every window of ``m`` consecutive nodes is a facet,
    when the facets form a simple chain (a strip); else None. A strip is then
    unfolded as a zigzag instead of being folded by the spring layout."""
    facets = sorted((frozenset(F) for F in model.facets),
                    key=lambda F: sorted(map(_node_key, F)))
    if len(facets) < 2:
        return None
    m = len(facets[0])
    if any(len(F) != m for F in facets) or m < 3:
        return None                      # 1-dimensional: spring layout + rotation handle a path

    # Dual graph: two facets are adjacent when they share a face of codim 1.
    adj = {i: [] for i in range(len(facets))}
    for i in range(len(facets)):
        for j in range(i + 1, len(facets)):
            if len(facets[i] & facets[j]) == m - 1:
                adj[i].append(j)
                adj[j].append(i)
    if any(len(nb) > 2 for nb in adj.values()):
        return None                      # branches: not a chain
    ends = sorted(i for i, nb in adj.items() if len(nb) == 1)
    if len(ends) != 2:
        return None                      # a cycle, or disconnected

    order, seen, cur = [ends[0]], {ends[0]}, ends[0]
    while True:
        nxt = [j for j in adj[cur] if j not in seen]
        if not nxt:
            break
        cur = nxt[0]
        seen.add(cur)
        order.append(cur)
    if len(order) != len(facets):
        return None                      # disconnected

    # Turn the facet chain into a node chain: the window of m nodes slides by
    # one at each step, so each facet contributes exactly one new node.
    chain = list(facets[order[0]] - facets[order[1]])          # the leading node
    middle = facets[order[0]] & facets[order[1]]
    # Order the shared block by how long each node survives along the chain.
    def lifetime(n):
        last = 0
        for pos, idx in enumerate(order):
            if n in facets[idx]:
                last = pos
        return last
    chain += sorted(middle, key=lambda n: (lifetime(n), _node_key(n)))
    for idx in order[1:]:
        new = [n for n in facets[idx] if n not in chain]
        if len(new) != 1:
            return None                  # not a clean sliding window
        chain.append(new[0])
    if len(chain) != len(order) + m - 1:
        return None
    for pos, idx in enumerate(order):     # verify before trusting it
        if frozenset(chain[pos:pos + m]) != facets[idx]:
            return None
    return chain


def _strip_layout(chain):
    """Place a node chain as a zigzag (unit x steps, 1.5 rise): near-equilateral triangles."""
    return {n: (float(i), 0.0 if i % 2 == 0 else 1.5) for i, n in enumerate(chain)}


def _draw_revision(ax, pos, revision, font_scale) -> None:
    """Draw a belief revision over the complex: eliminated facets hatched, each
    candidate's face shared with the lost facet marked with its size (the rule
    maximises it, so the losers are shown too), an arrow onto the winner.
    ``revision`` is a ``Revision`` of ``poster/poster-code/revision.py``."""
    import math

    from matplotlib.patches import FancyArrowPatch, Polygon

    GONE, WIN, LOSE = ink()["gone"], ink()["win"], ink()["lose"]

    def centroid(nodes):
        pts = [pos[n] for n in nodes if n in pos]
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    for facet in sorted(getattr(revision, "eliminated", ()) or (),
                        key=lambda F: sorted(map(_node_key, F))):
        pts = [pos[n] for n in facet if n in pos]
        if len(pts) < 2:
            continue
        cx, cy = centroid(facet)
        pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        # A pad first to mute the belief colour, then hatching (reads in greyscale).
        ax.add_patch(Polygon(pts, closed=True, facecolor=ink()["pad"],
                             edgecolor="none", alpha=0.76, zorder=2.1))
        ax.add_patch(Polygon(pts, closed=True, facecolor="none",
                             edgecolor=GONE, hatch="//////", linewidth=1.1, zorder=2.2))

    lost = getattr(revision, "lost", None)
    winners = set(getattr(revision, "winners", ()) or ())
    for facet, overlap in getattr(revision, "candidates", ()) or ():
        shared = sorted((n for n in (facet & lost) if n in pos), key=_node_key) if lost else []
        won = facet in winners
        col = WIN if won else LOSE
        if len(shared) >= 2:
            sx = [pos[n][0] for n in shared]
            sy = [pos[n][1] for n in shared]
            ax.plot(sx, sy, color=col, linewidth=5.5 if won else 3.0,
                    solid_capstyle="round", alpha=1.0 if won else 0.8, zorder=2.5)
            mx, my = sum(sx) / len(sx), sum(sy) / len(sy)
        elif len(shared) == 1:
            mx, my = pos[shared[0]]
            ax.scatter([mx], [my], s=620, facecolor="none", edgecolor=col,
                       linewidth=3.0 if won else 2.2, alpha=1.0 if won else 0.8, zorder=2.5)
        else:
            continue
        ax.annotate(
            f"|Y ∩ X| = {overlap}", (mx, my), xytext=(0, 13),
            textcoords="offset points", ha="center", va="bottom",
            fontsize=7.5 * font_scale, color=col, fontweight="bold" if won else "normal",
            zorder=6,
            bbox=dict(boxstyle="round,pad=0.22", facecolor=ink()["pad"],
                      edgecolor=col, linewidth=0.8, alpha=0.95),
        )

    if lost is not None:
        for facet in sorted(winners, key=lambda F: sorted(map(_node_key, F))):
            ax.add_patch(FancyArrowPatch(
                centroid(lost), centroid(facet),
                connectionstyle="arc3,rad=-0.32", arrowstyle="-|>",
                mutation_scale=18, linewidth=2.4, color=WIN,
                shrinkA=22, shrinkB=22, zorder=2.8,
            ))


def _show_simplicial(model, name, output_dir, title, image_format,
                     assignment=None, revision=None, font_scale=1.0,
                     transparent=False) -> str:
    """Draw a simplicial belief model with matplotlib: facets as filled simplices
    coloured by belief signature, nodes coloured by agent, literals under the
    nodes when an ``assignment`` is given, and optionally a revision overlay
    (:func:`_draw_revision`). ``font_scale`` multiplies every label size."""
    import math

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch, Polygon

    agents = sorted(model.agents, key=str)
    colors = {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(agents)}
    edge_pairs = _skeleton_edges(model)
    chain = _strip_order(model)
    pos = _strip_layout(chain) if chain else _spring_layout(model.nodes, edge_pairs)
    # Isolated nodes are placed last by _park_isolated, after the rotation
    # (they carry no adjacency and must not steer the PCA).
    touched = {n for e in edge_pairs for n in e}
    if touched:
        pos = {n: p for n, p in pos.items() if n in touched}
    sig_color = _signature_colors(model, agents)

    # An elongated drawing (a path, a strip) is rotated to lie horizontally and
    # the canvas is then sized to its aspect ratio.
    one_dimensional = all(len(F) <= 2 for F in model.facets)
    flat = one_dimensional
    if len(pos) > 1:
        candidate = _rotate_to_horizontal(pos)
        cxs = [p[0] for p in candidate.values()]
        cys = [p[1] for p in candidate.values()]
        if one_dimensional or (max(cxs) - min(cxs)) > 1.6 * ((max(cys) - min(cys)) or 1e-9):
            pos = candidate
            flat = True
    for n in model.nodes:
        if n not in pos:
            pos[n] = (0.0, 0.0)
    pos = _park_isolated(pos, edge_pairs)
    xs = [p[0] for p in pos.values()] or [0.0]
    ys = [p[1] for p in pos.values()] or [0.0]
    spread_x = max(xs) - min(xs) or 1.0
    spread_y = max(ys) - min(ys) or 1.0
    # Page layout in inches, top to bottom: drawing / caption / legend strip.
    legend_rows = math.ceil((len(agents) + len(sig_color)) / 4)
    legend_in = 0.24 * legend_rows + 0.08
    legend_y0 = 0.06
    caption_y = legend_y0 + legend_in + 0.06
    strip_in = caption_y + 0.32
    if flat:
        pad_y = 0.09 * spread_x
        width = 9.0
        draw_in = width * (spread_y + 2 * pad_y) / (spread_x * 1.08)
        height = max(1.6, min(7.0, draw_in)) + strip_in
    else:
        width, height = 8.0, 6.4 + strip_in
    fig, ax = plt.subplots(figsize=(width, height))
    if flat:
        ax.set_xlim(min(xs) - 0.04 * spread_x, max(xs) + 0.04 * spread_x)
        ax.set_ylim(min(ys) - pad_y, max(ys) + pad_y)

    # Facets, largest first so smaller ones stay visible (total order: reproducible z-order).
    for facet in sorted(model.facets,
                        key=lambda F: (-len(F), sorted(map(_node_key, F)))):
        pts = [pos[n] for n in facet]
        col = sig_color[_belief_signature(model, facet, agents)]
        if len(pts) == 2:
            (x0, y0), (x1, y1) = pts
            ax.plot([x0, x1], [y0, y1], color=col, linewidth=6, alpha=0.5, zorder=1)
        else:
            # Order the polygon points by angle around their centroid (convex-ish).
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
            ax.add_patch(Polygon(pts, closed=True, facecolor=col, edgecolor=col,
                                 alpha=0.35, linewidth=1.5, zorder=1))
        # The world's name at the centroid (above the line for an edge-facet).
        fname = facet_name(model, facet)
        if fname:
            dead = (revision is not None
                    and frozenset(facet) in (getattr(revision, "eliminated", ()) or ()))
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            lift = (0, 9) if len(pts) == 2 else (0, 0)
            ax.annotate(
                fname, (cx, cy), xytext=lift, textcoords="offset points",
                ha="center", va="bottom" if len(pts) == 2 else "center",
                fontsize=10 * font_scale, color=ink()["lose"] if dead else ink()["text"], zorder=5,
                bbox=dict(boxstyle="round,pad=0.25", facecolor=ink()["pad"],
                          edgecolor=ink()["gone"] if dead else col,
                          linewidth=0.8, alpha=0.9),
            )

    if revision is not None:
        _draw_revision(ax, pos, revision, font_scale)

    # The 1-skeleton, faintly.
    for (u, v) in edge_pairs:
        (x0, y0), (x1, y1) = pos[u], pos[v]
        ax.plot([x0, x1], [y0, y1], color=ink()["faint"], linewidth=0.6, zorder=2)

    # Nodes, coloured and labelled by agent.
    for node in model.nodes:
        x, y = pos[node]
        ax.scatter([x], [y], s=340 * font_scale ** 2, color=colors[node.agent],
                   edgecolor=ink()["marker_edge"], linewidth=1.0, zorder=3)
        ax.annotate(f"{node.agent}", (x, y), color="white", ha="center", va="center",
                    fontsize=10 * font_scale, fontweight="bold", zorder=4)
        vname = (getattr(model, "node_names", None) or {}).get(node)   # a complex defined directly
        if vname:
            ax.annotate(str(vname), (x, y), xytext=(0, 14 * font_scale),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=10 * font_scale, color=ink()["text"], zorder=4)
        if assignment is not None:
            literals = node_literals(assignment, node)
            if literals:
                ax.annotate(
                    "(" + ", ".join(literals) + ")", (x, y),
                    xytext=(0, -19 * font_scale), textcoords="offset points",
                    ha="center", va="top", fontsize=9.5 * font_scale, color=ink()["text"], zorder=4,
                )

    # Legend: agents + belief signatures.
    handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor=colors[a],
                      markersize=10, label=f"agent {a}") for a in agents]
    for sig, col in sorted(sig_color.items(), key=lambda item: (len(item[0]), item[0])):
        label = signature_label(model, sig, agents)
        handles.append(Patch(facecolor=col, alpha=0.5, label=label))
    if revision is not None:
        handles.append(Patch(facecolor=ink()["pad"], edgecolor=ink()["gone"], hatch="///",
                             label="eliminated"))
        handles.append(Line2D([0], [0], color=ink()["win"], linewidth=4,
                              label=f"R_{revision.agent}(X): max shared face"))
    # Caption and legend in the strip below the drawing, in figure coordinates.
    ncol = min(len(handles), 4)
    fig.legend(handles=handles, loc="lower center",
               bbox_to_anchor=(0.5, legend_y0 / height), ncol=ncol, fontsize=9 * font_scale,
               frameon=False, labelcolor=ink()["text"])
    fig.text(0.5, caption_y / height, title, ha="center", va="bottom", fontsize=12,
             color=ink()["text"])
    ax.set_axis_off()
    ax.set_aspect("equal")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.98,
                        bottom=(strip_in + 0.06) / height)

    os.makedirs(output_dir, exist_ok=True)
    image_path = os.path.join(output_dir, f"{os.path.basename(name)}.{image_format}")
    fig.savefig(image_path, dpi=130, bbox_inches="tight", pad_inches=0.15,
                transparent=transparent)
    plt.close(fig)
    return image_path


def _spring_layout_3d(nodes, edges, iterations: int = 220):
    """The 3-D counterpart of :func:`_spring_layout`: nodes start on a Fibonacci
    sphere. Returns ``node -> (x, y, z)``. Nodes are taken in the order given
    (the figure is rotatable, so orientation was never pinned)."""
    import math

    nodes = list(nodes)
    n = len(nodes)
    if n == 0:
        return {}
    pos = {}
    golden = math.pi * (3 - math.sqrt(5))
    for i, v in enumerate(nodes):
        y = 1 - (i / (n - 1)) * 2 if n > 1 else 0.0
        r = math.sqrt(max(0.0, 1 - y * y))
        theta = golden * i
        pos[v] = [math.cos(theta) * r, y, math.sin(theta) * r]
    k = 1.0 / (n ** (1 / 3)) if n else 1.0   # ideal edge length: cube root in 3-D
    gravity = 0.08                            # keeps isolated nodes from drifting away
    for _ in range(iterations):
        disp = {v: [0.0, 0.0, 0.0] for v in nodes}
        for i in range(n):
            for j in range(i + 1, n):
                vi, vj = nodes[i], nodes[j]
                d = [pos[vi][c] - pos[vj][c] for c in range(3)]
                dist = math.sqrt(sum(x * x for x in d)) or 1e-6
                f = k * k / dist
                for c in range(3):
                    disp[vi][c] += d[c] / dist * f
                    disp[vj][c] -= d[c] / dist * f
        for (u, v) in edges:
            d = [pos[u][c] - pos[v][c] for c in range(3)]
            dist = math.sqrt(sum(x * x for x in d)) or 1e-6
            f = dist * dist / k
            for c in range(3):
                disp[u][c] -= d[c] / dist * f
                disp[v][c] += d[c] / dist * f
        centre = [sum(pos[v][c] for v in nodes) / n for c in range(3)]
        for v in nodes:
            for c in range(3):
                disp[v][c] -= (pos[v][c] - centre[c]) * gravity
        for v in nodes:
            dist = math.sqrt(sum(x * x for x in disp[v])) or 1e-6
            for c in range(3):
                pos[v][c] += disp[v][c] / dist * min(dist, 0.1)
    return _park_isolated({v: tuple(p) for v, p in pos.items()}, edges)


def _show_simplicial_3d(model, name, output_dir, title, assignment=None,
                        font_scale=1.0) -> str:
    """Draw a simplicial belief model as a self-contained interactive 3-D HTML
    (plotly): solid simplices coloured by belief signature, nodes by agent.
    Faithful up to 4 agents (a 3-simplex); with 5 or more the figure is a
    projection and a warning is emitted."""
    import plotly.graph_objects as go

    agents = sorted(model.agents, key=str)
    if len(agents) >= 5:
        warnings.warn(
            f"{len(agents)} agents: each facet is a {len(agents) - 1}-simplex, which "
            "cannot be embedded faithfully in 3-D (only up to a 3-simplex / 4 agents "
            "fits). The figure shows a self-intersecting projection.",
            stacklevel=2,
        )
    colors = {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(agents)}
    edge_pairs = _skeleton_edges(model)
    pos = _spring_layout_3d(model.nodes, edge_pairs)
    sig_color = _signature_colors(model, agents)

    traces = []
    seen_sig = set()
    for facet in sorted(model.facets, key=lambda F: str(model.world_of_facet.get(F, ""))):
        pts = [pos[nd] for nd in facet]
        sig = _belief_signature(model, facet, agents)
        col = sig_color[sig]
        label = signature_label(model, sig, agents)
        show_in_legend = sig not in seen_sig
        seen_sig.add(sig)
        world = str(model.world_of_facet.get(facet, ""))
        if len(pts) >= 3:
            # The boundary 2-skeleton of the simplex: every triple of vertices.
            faces = list(itertools.combinations(range(len(pts)), 3))
            traces.append(go.Mesh3d(
                x=[p[0] for p in pts], y=[p[1] for p in pts], z=[p[2] for p in pts],
                i=[f[0] for f in faces], j=[f[1] for f in faces], k=[f[2] for f in faces],
                color=col, opacity=0.45, flatshading=True,
                name=label, legendgroup=label, showlegend=show_in_legend,
                hovertext=world, hoverinfo="text",
            ))
        elif len(pts) == 2:
            (x0, y0, z0), (x1, y1, z1) = pts
            traces.append(go.Scatter3d(
                x=[x0, x1], y=[y0, y1], z=[z0, z1], mode="lines",
                line=dict(color=col, width=8),
                name=label, legendgroup=label, showlegend=show_in_legend,
                hovertext=world, hoverinfo="text",
            ))

    # Facet names at the centroids, one text trace.
    named = [(F, facet_name(model, F)) for F in model.facets]
    named = [(F, n) for F, n in named if n]
    if named:
        cents = [[sum(pos[nd][k] for nd in F) / len(F) for k in range(3)] for F, _ in named]
        traces.append(go.Scatter3d(
            x=[c[0] for c in cents], y=[c[1] for c in cents], z=[c[2] for c in cents],
            mode="text", text=[n for _, n in named], textposition="middle center",
            textfont=dict(size=13 * font_scale, color=ink()["text"]),
            name="facetas", hoverinfo="skip", showlegend=False,
        ))

    # 1-skeleton edges (faint).
    ex, ey, ez = [], [], []
    for (u, v) in edge_pairs:
        (x0, y0, z0), (x1, y1, z1) = pos[u], pos[v]
        ex += [x0, x1, None]
        ey += [y0, y1, None]
        ez += [z0, z1, None]
    traces.append(go.Scatter3d(x=ex, y=ey, z=ez, mode="lines",
                               line=dict(color=ink()["faint"], width=1),
                               name="1-skeleton", hoverinfo="skip", showlegend=False))

    # Nodes, one trace per agent: label = vertex name or agent letter (+ literals), class on hover.
    for a in agents:
        ns = [nd for nd in model.nodes if nd.agent == a]

        def _txt(nd) -> str:
            base = str((getattr(model, "node_names", None) or {}).get(nd, a))
            if assignment is None:
                return base
            literals = node_literals(assignment, nd)
            return f"{base} ({', '.join(literals)})" if literals else base

        def _hover(nd) -> str:
            cls = ",".join(sorted(map(str, nd.cls)))
            if assignment is None:
                return cls
            literals = node_literals(assignment, nd)
            return f"{cls} | {', '.join(literals)}" if literals else cls

        traces.append(go.Scatter3d(
            x=[pos[nd][0] for nd in ns], y=[pos[nd][1] for nd in ns], z=[pos[nd][2] for nd in ns],
            mode="markers+text",
            marker=dict(size=6, color=colors[a], line=dict(color=ink()["marker_edge"], width=1)),
            text=[_txt(nd) for nd in ns], textposition="top center",
            hovertext=[_hover(nd) for nd in ns], hoverinfo="text",
            name=f"agent {a}", legendgroup=f"agent {a}",
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=title, showlegend=True,
        scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
                   bgcolor=ink()["page"]),   # coordinates carry no meaning
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor=ink()["page"], plot_bgcolor=ink()["page"],
        font=dict(color=ink()["text"]), legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{os.path.basename(name)}.html")
    fig.write_html(path, include_plotlyjs=True)  # self-contained, works offline
    # The browser's own page margin gets the figure's colour (no white rim on a dark page).
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    html = html.replace("<head>", f'<head><style>html,body{{margin:0;background:{ink()["page"]}}}</style>', 1)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path

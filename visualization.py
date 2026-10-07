"""Visualisation for every model in the project: text diagrams and images.

Kept separate from the models so they stay small, dependency-free descriptions of
the logic, and all drawing concerns live here. These are plain functions taking a
model as their first argument, so no model class has to carry any drawing code.

There are only three functions to remember, and each one accepts **any** model in
the project (a :class:`RelationalFrame`, a :class:`KnowledgeBeliefFrame` or a
:class:`SimplicialBeliefModel`) -- the right renderer is chosen automatically:

    visualize(model)            -> str, a text diagram (no dependencies)
    show(model, "name")         -> writes outputs/name.png, returns the path
    to_dot(model)               -> str, Graphviz DOT source (any model)

The style is inferred too: an S5 (knowledge) relation is drawn undirected and
without self-loops, a KD45 (belief) relation with arrows, an invalid frame with
its missing edges dashed in red. Pass the keyword arguments of :func:`show` only
when you want to override that.

Images need the Graphviz ``dot`` binary; simplicial models need matplotlib
(``dim=2``) or plotly (``dim=3``). This module imports the models only for type
checking, never at runtime, so there is no circular dependency.
"""

from __future__ import annotations

import itertools
import os
import shutil
import subprocess
import tempfile
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
) -> str:
    """Draw any model to a file and return the path. The one function to call.

    Which renderer runs is decided by the model, and the style by the model's
    shape, so ``show(model, "name")`` is normally all you need::

        show(belief_frame, "belief")        # outputs/belief.png   (arrows)
        show(knowledge_frame, "knowledge")  # S5 -> undirected, no self-loops
        show(kb_model, "figure1")           # knowledge + belief in one figure
        show(simplicial, "figure3")         # filled simplices (matplotlib)
        show(simplicial, "figure3", dim=3)  # interactive 3-D (plotly, .html)
        show(belief_frame, "belief", open=True)  # ...and open it in the viewer

    For a zero-config quick look (no name, opens automatically), use
    :func:`preview` instead.

    Args:
        name: Output basename, so each model can go to its own file.
        title: Caption (defaults to ``name``). Relational models append their
            validity verdict automatically; simplicial captions are used as given.
        dim: Simplicial models only -- 2 for a static image, 3 for interactive HTML.
        open: If True, open the generated file in the OS default viewer/browser
            after writing it. Default False, so batch scripts and tests never spawn
            viewers; pass ``open=True`` for an interactive one-off.
        output_dir: Directory for generated files (default :data:`OUTPUT_DIR`).
        image_format: Any format ``dot``/matplotlib supports (``png``, ``svg``, ...).
        logic: Relational frames only. ``"S5"`` says the frame is MEANT as
            knowledge even if it is not one yet (a half-drawn preview): the
            style is the knowledge style and what is missing is measured
            against the S5 closure (reflexivity and symmetry included) instead
            of the frame's KD45/K45 contract. ``None`` (default) infers.
        omit_self_loops: Hide reflexive edges. Default: inferred (hidden for S5).
        undirected_symmetric: Draw a symmetric pair as one arrow-less edge.
            Default: inferred (on for S5, whose relations are symmetric).
        highlight_missing: Draw the edges an invalid frame is missing, and its
            dead-end worlds, in red.
        valuation: The logical layer to display. For a RELATIONAL model, a
            Kripke valuation ``v : P -> 2^W``: every world is labelled with its
            literals, thesis Figure-33 style (``w1`` over ``¬Pa, Pb``). For a
            SIMPLICIAL model, a shortcut for the canonical vertex route: the
            valuation is turned into the induced vertex assignment
            (``assignment.assignment_from_model``: 1 where the agent knows the
            atom, 0 where it knows the negation, 2 otherwise) and drawn as
            ``assignment`` below.
        assignment: Simplicial models only -- a vertex assignment
            ``L : N -> 3^P`` (the project's canonical, chapter-3 form). Each
            node shows the literals its perspective observes, thesis Figure 5-9
            style (``a1`` with ``(¬Mb, Mc)``); value 2 draws nothing, so an
            unadorned node reads "no hard information". Takes precedence over
            ``valuation`` if both are given.
        engine: Simplicial models only -- which renderer to use. ``"auto"`` (the
            default) keeps the matplotlib drawing: filled simplices, the right
            picture for a 2-dimensional complex, but no editable source.
            ``"dot"`` routes through Graphviz instead, writing a ``.dot`` next to
            the ``.png`` so the figure can be retouched by hand without re-running
            the model -- at the cost of the filled areas. This route labels the
            vertices from ``valuation`` only (``assignment`` is not consulted).
            Relational models always go through Graphviz and ignore this.
        revision: Simplicial models only, 2-D matplotlib route only. A
            ``revision.Revision`` (anything with ``eliminated``, ``lost``,
            ``winners`` and ``candidates``). Draws the belief revision on top
            of the complex: the facets the announcement removed come out
            hatched, the face each candidate shares with the lost facet is
            marked with its size, and an arrow goes to the winner. Showing the
            LOSING candidates too is the point -- the rule maximises the shared
            face, and a maximum cannot be read off a single highlighted facet.

    Returns:
        The path to the generated file.

    Raises:
        RuntimeError: If the Graphviz ``dot`` binary is not on ``PATH``.
        TypeError: If ``model`` is not one of the project's models, or
            ``assignment`` is passed for a non-simplicial model.
    """
    kind = _kind(model)
    caption = title if title is not None else name
    if kind == "simplicial":
        if assignment is None and valuation is not None:
            # The canonical vertex-based route: a Kripke valuation reaches the
            # complex as the assignment it induces on the perspectives
            # (1 = knows the atom, 0 = knows its negation, 2 = cannot tell).
            from assignment import assignment_from_model

            assignment = assignment_from_model(model, valuation)
        if revision is not None and (engine == "dot" or dim == 3):
            raise TypeError(
                "revision is drawn only by the 2-D matplotlib route; it needs "
                "filled facets to hatch and a layout to put an arrow on. Drop "
                'engine="dot" / dim=3, or draw the revision separately.'
            )
        if engine == "dot":
            # Graphviz route for a complex. Unlike the matplotlib drawing it
            # leaves a .dot beside the .png -- an editable source, like every
            # other figure in this repo -- at the cost of the filled simplices.
            dot_source = _dot_simplicial(model, caption, valuation)
            path = _write_and_run_dot(dot_source, name, image_format, output_dir)
        elif dim == 3:
            path = _show_simplicial_3d(model, name, output_dir, caption,
                                       assignment=assignment)
        else:
            path = _show_simplicial(model, name, output_dir, caption, image_format,
                                    assignment=assignment, revision=revision)
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
        path = _write_and_run_dot(dot_source, name, image_format, output_dir)
    if open:
        _open_file(path)
    return path


def preview(model, title: str | None = None, *, dim: int = 2) -> str:
    """Render a model and open it immediately -- zero-config quick look.

    No name and no output directory to choose: the figure is written to a temporary
    file and opened in the OS default viewer (images) or browser (the 3-D HTML). Use
    this while exploring; use :func:`show` when you want the file kept under a name.

        preview(kb_model)          # a window pops up
        preview(simplicial, dim=3) # rotatable 3-D in the browser

    Returns the path to the (temporary) file.
    """
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
    """Return Graphviz DOT source for any model in the project.

    Use this to export a figure without the ``dot`` binary, or to tweak the source
    by hand; :func:`show` calls it for you. The arguments are those of
    :func:`show`; ``None`` means "infer from the model". With ``valuation``,
    every world is labelled with its literals (see :func:`world_literals`).
    A simplicial model gets the graph rendering of :func:`_dot_simplicial`
    (vertices and facets, no filled areas); the style keywords only apply to
    relational models.
    """
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


def _dot_simplicial(model, title: str | None = None, valuation=None) -> str:
    """Return Graphviz DOT source for a SIMPLICIAL belief model.

    Why a DOT form exists at all. :func:`_show_simplicial` draws the complex with
    matplotlib (filled simplices, spring layout), which is the right picture for a
    2-dimensional complex but gives no editable source: there is no ``.dot`` beside
    the ``.png``, so a figure cannot be retouched without re-running the model. The
    DOT rendering trades the filled areas for exactly that -- a text source the
    ``.dot`` files of every other figure in this repo already give you.

    How a complex becomes a graph. Every facet with exactly two vertices IS an
    edge, so a complex whose facets are all pairs (the two-agent case: one vertex
    per agent) maps to a graph with no loss at all. A facet with three or more
    vertices is a hyperedge, which DOT cannot draw; those are rendered in the
    standard incidence form -- a small point for the facet, joined to each of its
    vertices -- so the drawing stays faithful instead of silently dropping them.

    Conventions match :func:`_show_simplicial` so the two views of one model can be
    read side by side: vertices carry their agent's colour, facets (or their
    incidence points) carry the colour of their belief signature, and each facet is
    labelled with the world it came from.

    Args:
        model: the :class:`simplicial.SimplicialBeliefModel` to draw.
        title: caption under the figure.
        valuation: optional ``atom -> worlds`` map; when given, each vertex is
            labelled with the literals that perspective observes (via the induced
            assignment), exactly as the matplotlib drawing labels them.

    Returns:
        DOT source, ready for ``dot -Tpng``.
    """
    # Lazy imports, the rule this module already follows: the core is imported
    # only where it is needed, never at module level, so the domain code stays
    # unaware that a renderer exists.
    from simplicial import label_facet, label_node

    agents = sorted(model.agents, key=str)
    node_color = agent_colors(model)
    signature_color = _signature_colors(model, agents)

    assignment = {}
    if valuation:
        # Same bridge the matplotlib drawing uses: world truth induces what each
        # perspective OBSERVES (1/0/2), and only 1 and 0 are rendered.
        from assignment import assignment_from_model

        assignment = assignment_from_model(model, valuation)

    lines = [
        "graph SimplicialComplex {",          # undirected: a facet has no direction
        '  graph [bgcolor="white", fontname="Helvetica", labelloc="b"]',
        '  node  [fontname="Helvetica", fontsize=11]',
        '  edge  [penwidth=6]',                 # an edge IS a facet: thick, like a fill
        "  layout=neato",                      # geometric, like the matplotlib view
        "  overlap=false",                     # neato may stack nodes otherwise
        "  splines=true",                      # route edges around nodes, not through
    ]
    if title:
        lines.append(f'  label="{_dot_escape(title)}"')
        lines.append('  fontsize=14')

    for node in sorted(model.nodes, key=label_node):
        # Visible label = the agent, exactly as the matplotlib drawing labels it,
        # with the observed literals underneath. The full `label_node` string
        # (agent + knowledge class) is the node's unique DOT id and its tooltip,
        # so the picture stays uncluttered without losing which class it is.
        literals = ", ".join(node_literals(assignment, node)) if assignment else ""
        # The pieces are escaped SEPARATELY and joined with a raw "\n": that
        # sequence is Graphviz's line break, and _dot_escape would double the
        # backslash and turn it into two visible characters in the drawing.
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
            # Three or more vertices: DOT has no hyperedge, so the facet becomes a
            # point joined to its vertices (incidence rendering). Faithful, and it
            # keeps higher-dimensional complexes drawable instead of refused.
            hub = _dot_id("facet_" + label_facet(facet))
            lines.append(
                f'  {hub} [label="{caption}", shape=point, width=0.18, '
                f'color="{color}"]'
            )
            for member in members:
                lines.append(
                    f'  {hub} -- {_dot_id(label_node(member))} '
                    f'[color="{color}", penwidth=4]'
                )

    lines.append("}")
    return "\n".join(lines)


def world_literals(valuation, world) -> List[str]:
    """Render a world's atoms as literals, thesis Figure-33 style: ``¬Pa, Pb``.

    A Kripke valuation ``v : P -> 2^W`` is TOTAL: every atom it mentions is
    either true or false at each world, so both polarities are informative and
    both are shown (``P`` if ``world ∈ v(P)``, ``¬P`` otherwise). Atoms are
    sorted for a stable, comparable label.
    """
    return [
        (str(atom) if world in trues else f"¬{atom}")
        for atom, trues in sorted(valuation.items(), key=lambda kv: str(kv[0]))
    ]


def node_literals(assignment, node) -> List[str]:
    """Render a perspective's observed literals, thesis Figure 5-9 style.

    A vertex assignment ``L : N -> 3^P`` is PARTIAL: value 1 renders as ``P``,
    value 0 as ``¬P``, and value 2 ("doesn't know") renders as NOTHING -- silence
    is the point of the third value, so an uncertain atom must not clutter the
    node. A node with no observations gets an empty list (drawn bare, like
    ``b1`` in the thesis's Figure 5).
    """
    out: List[str] = []
    for atom, value in sorted(assignment.get(node, {}).items(), key=lambda kv: str(kv[0])):
        if value == 1:
            out.append(str(atom))
        elif value == 0:
            out.append(f"¬{atom}")
        # value 2: deliberately omitted
    return out


def agent_colors(model) -> Dict["Agent", str]:
    """Return a stable ``agent -> hex colour`` mapping from the palette.

    Colours are assigned by the agent's sorted position and the palette cycles, so
    the same model always colours the same agent the same way.
    """
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


def _is_s5(frame: "RelationalFrame") -> bool:
    """True if every relation is reflexive and symmetric -- i.e. knowledge (S5).

    Used to pick the default drawing style: S5 relations read best as undirected
    edges with the (assumed) self-loops hidden, KD45 relations as arrows.
    """
    for relation in frame.relations.values():
        if any((w, w) not in relation for w in frame.worlds):
            return False
        if any((t, s) not in relation for (s, t) in relation):
            return False
    return True


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
            # The world's literals, when a valuation is displayed: w1 (¬P, Q) -> ...
            lits = f" ({', '.join(world_literals(valuation, w))})" if valuation else ""
            # A world with no successor: under KD45 that breaks Axiom D (an
            # error); under K45 it is a legal defunct-belief world -- name each
            # for what it is instead of always shouting NOT SERIAL.
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
    """DOT ``label=...`` attribute for a world: its literals and its dead-end agents.

    Returns an empty string when there is nothing to show, so callers can splice
    the result into an attribute list unconditionally. The literals go on a
    second line under the world name, Figure-33 style. Only the label attribute
    changes -- the node's DOT identifier stays the bare world name, so edges
    keep pointing at the same node.

    ``dead_for`` names the agents for whom this world is a dead end (no
    outgoing belief edge). A dead end is a property of a world AND an agent
    (GitHub #11): the same world can leave ``a`` believing nothing while ``b``
    is fine, so the drawing says WHICH agents on the world itself -- a third
    line ``⊘ a, b`` with each name in that agent's colour. That line needs
    Graphviz's HTML-like label syntax (``label=<...>``) for the colours; the
    plain quoted form is kept whenever there is no dead end, so figures
    without one are byte-identical to before. ``error`` colours the mark red
    (a KD45 seriality violation) or grey (a legal K45 defunct belief).
    """
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
    mark = MISSING_COLOR if error else "#777777"
    names = ", ".join(
        f'<FONT COLOR="{(colors or {}).get(a, "#333333")}"><B>{_html_escape(a)}</B></FONT>'
        for a in dead_for
    )
    rows.append(f'<FONT COLOR="{mark}">&#9711;</FONT> {names}')
    return "label=<" + "<BR/>".join(rows) + ">"


def _dead_ends_by_world(frame) -> Dict:
    """``world -> [agents]`` for whom the world is a dead end, agents sorted.

    Inverts :meth:`RelationalFrame.dead_ends` (which is per agent) into the
    per-world form the drawings need to label each world with its agents.
    """
    out: Dict = {}
    for a, stuck in sorted(frame.dead_ends().items(), key=lambda kv: str(kv[0])):
        for w in stuck:
            out.setdefault(w, []).append(a)
    return out


def _dead_end_cell(flagged: bool) -> str:
    """Legend cell explaining the ``⊘ a, b`` line: red under D, grey under K45."""
    if flagged:
        return _note_cell("&#9711; a, b = dead end for those agents (Axiom D)", MISSING_COLOR)
    return _note_cell("&#9711; a, b = those agents believe nothing there (legal in K45)",
                      "#777777")


def _html_escape(value) -> str:
    """Escape a value for use inside a Graphviz HTML-like label."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _dot_header() -> List[str]:
    """Opening lines of a DOT digraph: layout and default node/edge style.

    The caption and the legend are NOT here: both go into the root graph's
    bottom label (see :func:`_dot_footer`), so neither takes part in the
    node layout. A caption on top overlapped the edges that arc above the
    nodes, and a legend node in ``rank=sink`` sat, with ``rankdir=LR``, in a
    rank of its own at the far right leaving a wide empty column.
    """
    return [
        "digraph Model {",
        "    rankdir=LR;",
        '    fontname="Helvetica"; overlap=false; nodesep=0.4; ranksep=0.6;',
        '    node [shape=circle, style=filled, fillcolor="#f4f6f8",'
        ' color="#333333", fontname="Helvetica", width=0.5];',
        '    edge [penwidth=1.6, arrowsize=0.8, fontname="Helvetica"];',
    ]


def _dot_footer(caption: str, cells: List[str]) -> List[str]:
    """Caption and legend under the drawing, then close the graph.

    Both are one HTML-like root label at ``labelloc="b"``: first row the
    caption, second row the legend cells in a single horizontal strip. Being
    the graph label, it is centred under the drawing whatever the rank
    direction and never collides with nodes or edges.
    """
    rows = [
        "        <TR><TD COLSPAN=\"99\" ALIGN=\"CENTER\">"
        f"<FONT POINT-SIZE=\"13\">{_html_escape(caption)}</FONT></TD></TR>",
    ]
    if cells:
        # Nested table: the legend cells keep their own spacing while the
        # caption row spans the full width above them.
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


def _agent_cell(agent, color: str) -> str:
    """Legend cell: a coloured dot followed by the agent's name."""
    return (
        f'<TD><FONT COLOR="{color}" POINT-SIZE="15">&#9679;</FONT>'
        f' <FONT POINT-SIZE="11">{_html_escape(agent)}</FONT></TD>'
    )


def _note_cell(text: str, color: str = "#333333") -> str:
    """Legend cell: a short piece of explanatory text."""
    return f'<TD><FONT COLOR="{color}" POINT-SIZE="11">{text}</FONT></TD>'


def _sorted_edges(relation):
    """Edges in a stable order, so the generated DOT is deterministic."""
    return sorted(relation, key=lambda e: (str(e[0]), str(e[1])))


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
    """DOT for one frame, one colour per agent (see :func:`to_dot`).

    ``logic="S5"`` declares the frame as KNOWLEDGE regardless of its current
    shape: the knowledge style applies, validity is judged as an equivalence
    relation, and the red overlay shows what the S5 closure would add. Without
    it, an incomplete knowledge frame would be judged (and completed) as a
    KD45 belief frame -- wrong loops, wrong verdict.
    """
    as_knowledge = logic == "S5"
    # Style defaults: knowledge (S5) is symmetric and reflexive, so it reads best
    # as undirected edges with the assumed self-loops hidden; belief keeps arrows.
    if omit_self_loops is None or undirected_symmetric is None:
        s5 = as_knowledge or _is_s5(frame)
        omit_self_loops = s5 if omit_self_loops is None else omit_self_loops
        undirected_symmetric = s5 if undirected_symmetric is None else undirected_symmetric

    colors = agent_colors(frame)
    # Caption shows validity so valid and invalid models are told apart at a
    # glance -- judged against the frame's DECLARED logic (violations() consults
    # axiom_d), not blanket KD45: a legal K45 frame must not read as broken.
    if as_knowledge:
        from properness import equivalence_violations  # local: no import cycle
        from relational_frame import s5_closure

        violations = equivalence_violations(frame)
        logic_name = "S5"
        missing = {a: s5_closure(frame.worlds, frame.relations[a]) - set(frame.relations[a])
                   for a in frame.agents}
    else:
        violations = frame.violations()
        logic_name = frame.logic_label()
        missing = frame.missing_edges()
    status = f"valid {logic_name}" if not violations else f"INVALID: {len(violations)} violation(s)"
    caption = f"{title} — {status}" if title else status
    lines = _dot_header()

    # Which agents believe nothing at each world (no outgoing edge). A dead end
    # is per AGENT, so the world is labelled with their names (GitHub #11).
    # Under KD45 it is a seriality violation and the world also gets the red
    # error styling; under K45 (axiom_d off) a dead end is a legal
    # defunct-belief world: the names stay (in grey) and nothing reads as
    # broken. Knowledge frames are reflexive, so there is nothing to look for.
    dead_for: Dict = {} if as_knowledge else _dead_ends_by_world(frame)
    flag_dead = highlight_missing and frame.axiom_d and not as_knowledge
    for w in sorted(frame.worlds, key=str):
        # The valuation label rides along with whatever styling the world gets:
        # attributes are collected and joined, so dead-end highlighting and the
        # literals never fight over the bracket.
        attrs = []
        label = _world_label_attr(valuation, w, dead_for.get(w, ()), colors, flag_dead)
        if label:
            attrs.append(label)
        if flag_dead and w in dead_for:
            attrs += [f'fillcolor="#FDE7E7"', f'color="{MISSING_COLOR}"',
                      'style="filled,dashed"', "penwidth=2"]
        lines.append(
            f"    {_dot_id(w)}" + (f" [{', '.join(attrs)}]" if attrs else "") + ";"
        )

    # One coloured edge per agent -- the colour identifies the agent, so no
    # per-edge labels are needed (the legend below maps colour -> agent).
    for a in sorted(frame.agents, key=str):
        color = colors[a]
        relation = frame.relations[a]
        drawn_undirected: Set[frozenset] = set()
        for (source, target) in _sorted_edges(relation):
            if omit_self_loops and source == target:
                continue
            if undirected_symmetric and source != target and (target, source) in relation:
                # Symmetric pair -> draw once, without arrowheads.
                key = frozenset((source, target))
                if key in drawn_undirected:
                    continue
                drawn_undirected.add(key)
                lines.append(
                    f'    {_dot_id(source)} -> {_dot_id(target)} [color="{color}", dir=none];'
                )
            else:
                lines.append(f'    {_dot_id(source)} -> {_dot_id(target)} [color="{color}"];')

    # Overlay the edges that are required but missing (dashed red, no label).
    # Follows the drawing's own conventions: loops are skipped when loops are
    # hidden, and a missing symmetric pair is one dashed line when pairs are
    # drawn undirected -- otherwise the overlay would show what the drawing
    # deliberately abbreviates.
    if highlight_missing:
        for a in sorted(frame.agents, key=str):
            drawn_missing: Set[frozenset] = set()
            for (source, target) in _sorted_edges(missing[a]):
                if omit_self_loops and source == target:
                    continue
                if undirected_symmetric and source != target and (target, source) in missing[a]:
                    key = frozenset((source, target))
                    if key in drawn_missing:
                        continue
                    drawn_missing.add(key)
                    lines.append(
                        f'    {_dot_id(source)} -> {_dot_id(target)} '
                        f'[style=dashed, dir=none, color="{MISSING_COLOR}"];'
                    )
                    continue
                lines.append(
                    f'    {_dot_id(source)} -> {_dot_id(target)} '
                    f'[style=dashed, color="{MISSING_COLOR}"];'
                )

    cells = [_agent_cell(a, colors[a]) for a in sorted(frame.agents, key=str)]
    if cells:
        if highlight_missing and any(missing.values()):
            cells.append(_note_cell("&#9548;&#9548; missing edge", MISSING_COLOR))
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
    """DOT for a knowledge+belief model, both relations in one figure.

    Knowledge ``R_a`` is drawn as thin, arrow-less lines (S5 is symmetric, so
    indistinguishability has no direction); belief ``Q_a`` as bold, directed arrows
    (what the agent actually believes). Both are coloured by agent. Since
    ``Q_a ⊆ R_a``, each belief arrow sits alongside a knowledge line.

    Both simplifications can be switched off to show the relation AS IT IS
    (every edge, every direction): ``omit_self_loops=False`` draws the
    reflexive loops of both relations, ``undirected_symmetric=False`` draws a
    symmetric knowledge pair as two thin arrows. The GUI exposes this as
    "show implicit edges", the way to see what the S5/KD45 closures added.

    ``highlight_missing`` (default on) overlays, in red, what an INVALID model
    is missing -- the same treatment :func:`_dot_frame` gives a single frame,
    so a half-drawn model in the GUI preview shows what the closures will
    fill in: the S5 edges knowledge lacks (thin dashed), the KD45 edges belief
    lacks (bold dashed), belief arrows that leave the knowledge class (bold
    red: ``Q_a ⊆ R_a`` fails) and, under Axiom D, the worlds where an agent
    believes nothing (red dashed outline: seriality fails).
    """
    omit_self_loops = True if omit_self_loops is None else omit_self_loops
    undirected_symmetric = True if undirected_symmetric is None else undirected_symmetric
    colors = agent_colors(kb)
    status = "valid" if kb.is_valid() else "INVALID"
    caption = f"{title} — {status}" if title else status
    lines = _dot_header()

    # What is missing, computed up front so nodes and edges can both use it.
    # Knowledge is measured against its S5 closure (RelationalFrame.missing_edges
    # only covers axioms 4/5, and knowledge also needs T: reflexivity), belief
    # against its own 4/5 closure; dead ends only count when Axiom D applies.
    missing_k: Dict = {}
    missing_b: Dict = {}
    if highlight_missing:
        from relational_frame import s5_closure  # local: avoids an import cycle

        for a in kb.agents:
            rel = kb.knowledge.relations[a]
            missing_k[a] = s5_closure(kb.worlds, rel) - set(rel)
        missing_b = kb.belief.missing_edges()
    # Dead ends are named per agent on the world itself (GitHub #11, see
    # _dot_frame): red error styling only under Axiom D, grey names under K45.
    dead_for = _dead_ends_by_world(kb.belief)
    flag_dead = highlight_missing and kb.axiom_d

    for w in sorted(kb.worlds, key=str):
        attrs = []
        label = _world_label_attr(valuation, w, dead_for.get(w, ()), colors, flag_dead)
        if label:
            attrs.append(label)
        if flag_dead and w in dead_for:
            attrs += [f'fillcolor="#FDE7E7"', f'color="{MISSING_COLOR}"',
                      'style="filled,dashed"', "penwidth=2"]
        lines.append(
            f"    {_dot_id(w)}" + (f" [{', '.join(attrs)}]" if attrs else "") + ";"
        )

    # Knowledge: thin, undirected (symmetric). Belief: bold, directed.
    for a in sorted(kb.agents, key=str):
        color = colors[a]
        relation = kb.knowledge.relations[a]
        drawn: Set[frozenset] = set()
        for (s, t) in _sorted_edges(relation):
            if omit_self_loops and s == t:
                continue
            if undirected_symmetric and s != t and (t, s) in relation:
                key = frozenset((s, t))
                if key in drawn:
                    continue
                drawn.add(key)
                lines.append(
                    f'    {_dot_id(s)} -> {_dot_id(t)} [color="{color}", dir=none, penwidth=0.7];'
                )
            else:
                lines.append(f'    {_dot_id(s)} -> {_dot_id(t)} [color="{color}", penwidth=0.7];')
    outside_knowledge = False
    for a in sorted(kb.agents, key=str):
        color = colors[a]
        for (s, t) in _sorted_edges(kb.belief.relations[a]):
            if omit_self_loops and s == t:
                continue
            # A belief arrow with no knowledge edge underneath breaks Q_a ⊆ R_a:
            # drawn in red so the offending arrow itself is the diagnosis.
            if highlight_missing and (s, t) not in kb.knowledge.relations[a]:
                outside_knowledge = True
                lines.append(
                    f'    {_dot_id(s)} -> {_dot_id(t)} [color="{MISSING_COLOR}", '
                    'penwidth=2.6, arrowsize=1.0];'
                )
            else:
                lines.append(
                    f'    {_dot_id(s)} -> {_dot_id(t)} [color="{color}", penwidth=2.6, arrowsize=1.0];'
                )

    # Overlay of what is missing (dashed red): thin for knowledge, bold for
    # belief. Knowledge follows the undirected convention of the drawn edges.
    any_missing = False
    for a in sorted(kb.agents, key=str):
        drawn_m: Set[frozenset] = set()
        for (s, t) in _sorted_edges(missing_k.get(a, ())):
            if omit_self_loops and s == t:
                continue
            any_missing = True
            if undirected_symmetric and s != t and (t, s) in missing_k[a]:
                key = frozenset((s, t))
                if key in drawn_m:
                    continue
                drawn_m.add(key)
                lines.append(
                    f'    {_dot_id(s)} -> {_dot_id(t)} [style=dashed, dir=none, '
                    f'color="{MISSING_COLOR}", penwidth=0.7];'
                )
            else:
                lines.append(
                    f'    {_dot_id(s)} -> {_dot_id(t)} [style=dashed, '
                    f'color="{MISSING_COLOR}", penwidth=0.7];'
                )
        for (s, t) in _sorted_edges(missing_b.get(a, ())):
            if omit_self_loops and s == t:
                continue
            any_missing = True
            lines.append(
                f'    {_dot_id(s)} -> {_dot_id(t)} [style=dashed, '
                f'color="{MISSING_COLOR}", penwidth=2.6, arrowsize=1.0];'
            )

    cells = [_agent_cell(a, colors[a]) for a in sorted(kb.agents, key=str)]
    if cells:
        cells.append(_note_cell("&#9472; knowledge (thin)"))
        cells.append(_note_cell("&#10142; belief (bold)"))
        if any_missing:
            cells.append(_note_cell("&#9548;&#9548; missing edge", MISSING_COLOR))
        if outside_knowledge:
            cells.append(_note_cell("&#10142; belief outside knowledge", MISSING_COLOR))
        if dead_for:
            cells.append(_dead_end_cell(flag_dead))
    lines += _dot_footer(caption, cells)
    return "\n".join(lines)


def _write_and_run_dot(dot_source: str, name: str, image_format: str, output_dir: str) -> str:
    """Write DOT to ``<output_dir>/<name>.dot`` and render it with Graphviz ``dot``.

    Raises:
        RuntimeError: If the ``dot`` binary is not found on ``PATH``.
    """
    if shutil.which("dot") is None:
        raise RuntimeError(
            "Graphviz 'dot' not found on PATH. Install it (e.g. 'brew install "
            "graphviz') or use to_dot(model) to export the source manually."
        )
    os.makedirs(output_dir, exist_ok=True)
    # basename() keeps a stray "/" or ".." in `name` from writing outside output_dir.
    base = os.path.join(output_dir, os.path.basename(name))
    dot_path = f"{base}.dot"
    image_path = f"{base}.{image_format}"
    with open(dot_path, "w", encoding="utf-8") as fh:
        fh.write(dot_source)
    # -T selects the output format; -o the destination file.
    subprocess.run(["dot", f"-T{image_format}", dot_path, "-o", image_path], check=True)
    return image_path


def _open_file(path: str) -> None:
    """Open ``path`` in the OS default application (image viewer / browser).

    Best-effort and cross-platform; never raises (a failed open must not break a
    render). Falls back to the ``webbrowser`` module, which handles both images and
    the interactive 3-D HTML.
    """
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
    """Readable name of a facet: the world it came from.

    Under the translation every facet IS a world of the proper model, so the
    natural name of a facet is that world. Worlds of a proper model are copies
    ``(w, u)``: rendered as ``(w, u)`` without the quotes ``str`` would add,
    so the label stays short inside the drawing. An empty string when the
    model does not record its worlds (hand-built complexes).
    """
    world = model.world_of_facet.get(facet) if hasattr(model, "world_of_facet") else None
    if world is None:
        return ""
    if isinstance(world, tuple):
        return "(" + ", ".join(map(str, world)) + ")"
    return str(world)


def _belief_signature(model, facet, agents):
    """The tuple of agents whose belief subcomplex contains ``facet``."""
    return tuple(a for a in agents if facet in model.belief_facets.get(a, ()))


def _node_key(node):
    """A canonical, run-stable sort key for a simplicial node.

    ``str(node)`` is NOT usable: a Node carries a frozenset, whose repr orders
    its elements by hash, so the same node stringifies differently on every
    run. Sorting by it was the hidden source of figures that changed each time
    the script was re-run.
    """
    agent = getattr(node, "agent", None)
    cls = getattr(node, "cls", None)
    if agent is None or cls is None:
        return (str(node), ())
    return (str(agent), tuple(sorted(str(w) for w in cls)))


def _signature_colors(model, agents) -> Dict[tuple, str]:
    """Map each belief signature to a fill colour (the empty one stays neutral grey)."""
    signatures = {_belief_signature(model, f, agents) for f in model.facets}
    colors = {(): "#dddddd"}
    # Sorted (singletons first, then alphabetically) so the palette is handed out
    # in the same order on every run and the legend reads in that order too.
    for i, sig in enumerate(sorted((s for s in signatures if s), key=lambda s: (len(s), s))):
        colors[sig] = BELIEF_PALETTE[i % len(BELIEF_PALETTE)]
    return colors


def _skeleton_edges(model):
    """The 1-skeleton: every pair of nodes sharing a facet. Drives the layouts."""
    edges = set()
    for facet in model.facets:
        for u, v in itertools.combinations(facet, 2):
            edges.add(frozenset((u, v)))
    # Sorted: the accumulation order of the spring forces changes the result
    # in the last floating-point digits, and a set gives a different order
    # on every run.
    return sorted((tuple(sorted(e, key=_node_key)) for e in edges),
                  key=lambda e: tuple(map(_node_key, e)))


def _spring_layout(nodes, edges, iterations: int = 250):
    """A small deterministic Fruchterman-Reingold layout (no external deps).

    Nodes start on a circle (deterministic, no randomness) and are then relaxed by
    edge attraction + all-pairs repulsion. Returns ``node -> (x, y)``.
    """
    import math

    # Sort before placing: the caller passes a SET, whose iteration order
    # changes with PYTHONHASHSEED, so without this the starting circle -- and
    # therefore the whole drawing -- came out different on every run. The
    # figures committed to the repo could not be reproduced by re-running the
    # script, which is exactly what "deterministic" above is supposed to mean.
    nodes = sorted(nodes, key=_node_key)
    n = len(nodes)
    if n == 0:
        return {}
    pos = {
        v: [math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)]
        for i, v in enumerate(nodes)
    }
    k = 1.0 / math.sqrt(n)
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
        # Cap each step (the Fruchterman-Reingold "temperature", kept constant):
        # the circular start is already tame, so no cooling schedule is needed.
        for v in nodes:
            dx, dy = disp[v]
            d = math.hypot(dx, dy) or 1e-6
            pos[v][0] += dx / d * min(d, 0.08)
            pos[v][1] += dy / d * min(d, 0.08)
    return {v: (p[0], p[1]) for v, p in pos.items()}


def _rotate_to_horizontal(pos):
    """Rotate a 2-D layout so its principal axis (largest spread) is horizontal.

    Plain PCA on the point cloud: the eigenvector of the covariance matrix with
    the larger eigenvalue becomes the x axis. Only used for 1-dimensional
    complexes, whose layouts are essentially a line; rotating a genuinely 2-D
    drawing would gain nothing.
    """
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
    """Node order n0..n_{k+m-2} such that every window of m is a facet, or None.

    A great many of these complexes are **strips**: the facets form a chain,
    each glued to the next along a shared face. The spring layout only sees the
    1-skeleton, so it has no idea the facets are 2-cells that must not overlap,
    and it happily folds the chain over itself. When the chain exists we can
    place it exactly instead of guessing: unfold it into a zigzag, which is the
    canonical picture of a triangle strip and never self-intersects.

    Returns None whenever the facets are not a simple chain, so the caller falls
    back to the spring layout.
    """
    # Sorted, like the node order in _spring_layout: model.facets is a set, so
    # without this the chain could be walked from either end on different runs
    # and the drawing came out mirrored at random.
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
    """Place a node chain as an open zigzag: consecutive windows are triangles.

    Unit steps in x and a 1.5 rise in y make each triangle close to equilateral
    (height sqrt(3) ~ 1.7 for base 2) instead of a flat sliver.
    """
    return {n: (float(i), 0.0 if i % 2 == 0 else 1.5) for i, n in enumerate(chain)}


def _show_simplicial(model, name, output_dir, title, image_format,
                     assignment=None, revision=None) -> str:
    """Draw a simplicial belief model: facets as filled simplices, nodes by agent.

    Each facet (a possible world) is drawn as a filled polygon over its nodes -- an
    edge for 2 agents, a triangle for 3, and the convex node polygon for more. The
    fill colour encodes which agents' **belief subcomplexes** the facet belongs to
    (the Figure-3 colouring); facets in no belief subcomplex are light grey. Nodes
    are coloured by agent (the shared palette).

    With ``assignment`` (the canonical vertex valuation, L : N -> 3^P), each node
    additionally shows the literals its perspective observes, under the marker --
    the thesis's own drawing convention (Figures 5-9: ``a1`` with ``(¬Mb, Mc)``).
    Value 2 draws nothing: a bare node means "no hard information here".

    With ``revision`` (a :class:`revision.Revision`) the belief revision is drawn
    over the same complex: eliminated facets hatched out, every candidate's
    shared face marked with ``|Y n X|``, and an arrow onto the winner.
    """
    import math

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyArrowPatch, Patch, Polygon

    agents = sorted(model.agents, key=str)
    colors = {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(agents)}
    edge_pairs = _skeleton_edges(model)
    chain = _strip_order(model)
    pos = _strip_layout(chain) if chain else _spring_layout(model.nodes, edge_pairs)
    # A node in no facet (an isolated vertex, GitHub #12) is invisible to the
    # strip layout, which walks the facets: park such nodes in a column just
    # past the right end of the strip so they are drawn, apart, instead of
    # raising a KeyError below. (The spring layout already places every node.)
    loose = sorted((n for n in model.nodes if n not in pos), key=_node_key)
    if loose:
        right = max((p[0] for p in pos.values()), default=-1.0) + 1.0
        for i, n in enumerate(loose):
            pos[n] = (right + i, 0.75)
    sig_color = _signature_colors(model, agents)

    # A 1-dimensional complex (two agents: every facet is an edge) is a graph
    # whose spring layout comes out as a line or a thin zigzag at some
    # arbitrary angle -- on the square canvas that meant a 45° diagonal in a
    # sea of white. Rotate it so its long axis is horizontal, then size the
    # canvas to the drawing's own aspect ratio (wide and low for a path).
    one_dimensional = all(len(F) <= 2 for F in model.facets)
    # ...and the same is true of any ELONGATED drawing, not just a path: a
    # strip of triangles is genuinely 2-dimensional but just as flat as a
    # line, and on the square canvas it came out as a tall ribbon in a sea of
    # white. Rotate whenever the principal axis dominates, then fall into the
    # same aspect-ratio sizing below.
    flat = one_dimensional
    if len(pos) > 1:
        candidate = _rotate_to_horizontal(pos)
        cxs = [p[0] for p in candidate.values()]
        cys = [p[1] for p in candidate.values()]
        # 1.6: clearly elongated, so a near-square drawing is left as it is.
        if one_dimensional or (max(cxs) - min(cxs)) > 1.6 * ((max(cys) - min(cys)) or 1e-9):
            pos = candidate
            flat = True
    xs = [p[0] for p in pos.values()] or [0.0]
    ys = [p[1] for p in pos.values()] or [0.0]
    spread_x = max(xs) - min(xs) or 1.0
    spread_y = max(ys) - min(ys) or 1.0
    # Page layout in INCHES, top to bottom: drawing / caption / legend. The
    # caption and legend get a fixed strip at the bottom of the figure (so
    # they never overlap the drawing however flat it is) and the drawing gets
    # the rest. Sizes below are in inches; fractions are derived from them.
    legend_rows = math.ceil((len(agents) + len(sig_color)) / 4)
    legend_in = 0.24 * legend_rows + 0.08      # measured: ~0.24in per row at 8pt
    legend_y0 = 0.06                           # gap under the legend
    caption_y = legend_y0 + legend_in + 0.06   # caption sits right above it
    strip_in = caption_y + 0.32                # + the caption's own height
    if flat:
        # Give a flat drawing some height of its own (room for the node
        # markers and their literal labels) and keep the aspect ratio equal.
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

    # Draw facets (filled), largest first so smaller ones stay visible.
    # Total order, not just by size: ties were broken by the set's own
    # iteration order, so the z-order of the shared edges -- and the PNG --
    # changed from run to run.
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
        # Name the facet by its world at the centroid, so the reader can match
        # each triangle to a world of the proper model (and to the Hasse
        # diagram, whose facet boxes carry the same name). White pad behind
        # the text keeps it legible over the fill and the crossing edges.
        # (``fname``, not ``name``: ``name`` is this function's output file.)
        fname = facet_name(model, facet)
        if fname:
            dead = (revision is not None
                    and frozenset(facet) in (getattr(revision, "eliminated", ()) or ()))
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            # On an edge-facet the label rides just above the line; on a
            # filled facet it sits at the centroid.
            lift = (0, 9) if len(pts) == 2 else (0, 0)
            ax.annotate(
                fname, (cx, cy), xytext=lift, textcoords="offset points",
                ha="center", va="bottom" if len(pts) == 2 else "center",
                fontsize=7, color="#9aa6b5" if dead else "#222222", zorder=5,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                          edgecolor="#aab2bf" if dead else col,
                          linewidth=0.8, alpha=0.9),
            )

    # --- belief revision, when asked for --------------------------------
    # Three marks, each answering one question: which world is gone, WHY the
    # winner wins, and where the belief moves. Only the middle one is not
    # obvious, so every candidate's shared face is drawn with its size: the
    # winner shares a whole edge, the loser touches at a single point, and the
    # maximum is legible without reading the formula.
    GONE, WIN, LOSE = "#aab2bf", "#c0432b", "#9aa6b5"
    if revision is not None:
        def _centroid(nodes):
            pts = [pos[n] for n in nodes if n in pos]
            return (sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts))

        for facet in sorted(getattr(revision, "eliminated", ()) or (),
                            key=lambda F: sorted(map(_node_key, F))):
            pts = [pos[n] for n in facet if n in pos]
            if len(pts) < 2:
                continue
            cx, cy = _centroid(facet)
            pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
            # White first to mute the belief colour, then hatching so the
            # "this is gone" still reads in one-ink printing and in greyscale.
            ax.add_patch(Polygon(pts, closed=True, facecolor="white",
                                 edgecolor="none", alpha=0.76, zorder=2.1))
            ax.add_patch(Polygon(pts, closed=True, facecolor="none",
                                 edgecolor=GONE, hatch="//////",
                                 linewidth=1.1, zorder=2.2))

        lost = getattr(revision, "lost", None)
        winners = set(getattr(revision, "winners", ()) or ())
        for facet, overlap in getattr(revision, "candidates", ()) or ():
            shared = sorted((n for n in (facet & lost) if n in pos),
                            key=_node_key) if lost else []
            won = facet in winners
            col = WIN if won else LOSE
            if len(shared) >= 2:
                sx = [pos[n][0] for n in shared]
                sy = [pos[n][1] for n in shared]
                ax.plot(sx, sy, color=col, linewidth=5.5 if won else 3.0,
                        solid_capstyle="round", alpha=1.0 if won else 0.8,
                        zorder=2.5)
                mx, my = sum(sx) / len(sx), sum(sy) / len(sy)
            elif len(shared) == 1:
                mx, my = pos[shared[0]]
                ax.scatter([mx], [my], s=620, facecolor="none", edgecolor=col,
                           linewidth=3.0 if won else 2.2,
                           alpha=1.0 if won else 0.8, zorder=2.5)
            else:
                continue
            ax.annotate(
                f"|Y \u2229 X| = {overlap}", (mx, my), xytext=(0, 13),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=7.5, color=col, fontweight="bold" if won else "normal",
                zorder=6,
                bbox=dict(boxstyle="round,pad=0.22", facecolor="white",
                          edgecolor=col, linewidth=0.8, alpha=0.95),
            )

        for facet in sorted(winners, key=lambda F: sorted(map(_node_key, F))):
            if lost is None:
                break
            ax.add_patch(FancyArrowPatch(
                _centroid(lost), _centroid(facet),
                connectionstyle="arc3,rad=-0.32", arrowstyle="-|>",
                mutation_scale=18, linewidth=2.4, color=WIN,
                shrinkA=22, shrinkB=22, zorder=2.8,
            ))

    # The 1-skeleton, faintly.
    for (u, v) in edge_pairs:
        (x0, y0), (x1, y1) = pos[u], pos[v]
        ax.plot([x0, x1], [y0, y1], color="#999999", linewidth=0.6, zorder=2)

    # Nodes, coloured and labelled by agent.
    for node in model.nodes:
        x, y = pos[node]
        ax.scatter([x], [y], s=260, color=colors[node.agent],
                   edgecolor="#222", linewidth=1.0, zorder=3)
        ax.annotate(f"{node.agent}", (x, y), color="white", ha="center", va="center",
                    fontsize=8, fontweight="bold", zorder=4)
        # A directly-defined complex names its vertices: show the name just
        # above the marker (the marker itself keeps the agent's letter, which
        # is the colouring). Translated models have no names and stay as-is.
        vname = (getattr(model, "node_names", None) or {}).get(node)
        if vname:
            ax.annotate(str(vname), (x, y), xytext=(0, 12), textcoords="offset points",
                        ha="center", va="bottom", fontsize=7, color="#222222", zorder=4)
        if assignment is not None:
            # The observed literals sit just below the marker (offset in POINTS,
            # not data units, so the gap survives any zoom/layout scale). Nodes
            # whose perspective observes nothing stay bare on purpose.
            literals = node_literals(assignment, node)
            if literals:
                ax.annotate(
                    "(" + ", ".join(literals) + ")", (x, y),
                    xytext=(0, -16), textcoords="offset points",
                    ha="center", va="top", fontsize=7, color="#222222", zorder=4,
                )

    # Legend: agents + belief signatures.
    handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor=colors[a],
                      markersize=10, label=f"agent {a}") for a in agents]
    for sig, col in sorted(sig_color.items(), key=lambda item: (len(item[0]), item[0])):
        label = "belief: " + ("+".join(map(str, sig)) if sig else "none")
        handles.append(Patch(facecolor=col, alpha=0.5, label=label))
    if revision is not None:
        handles.append(Patch(facecolor="white", edgecolor=GONE, hatch="///",
                             label="eliminated"))
        handles.append(Line2D([0], [0], color=WIN, linewidth=4,
                              label=f"R_{revision.agent}(X): max shared face"))
    # Caption and legend strip BELOW the drawing (same page layout as the DOT
    # figures: drawing / caption / legend), instead of a legend box inside the
    # axes that covered part of the complex. Both are placed in FIGURE
    # coordinates computed from the strip height in inches, so they sit at
    # the same distance from the drawing whatever the drawing's shape.
    ncol = min(len(handles), 4)
    fig.legend(handles=handles, loc="lower center",
               bbox_to_anchor=(0.5, legend_y0 / height), ncol=ncol, fontsize=8,
               frameon=False)
    fig.text(0.5, caption_y / height, title, ha="center", va="bottom", fontsize=12)
    ax.set_axis_off()
    ax.set_aspect("equal")
    # The axes take everything above the strip; bbox_inches="tight" (savefig)
    # then trims the outer white margins.
    fig.subplots_adjust(left=0.02, right=0.98, top=0.98,
                        bottom=(strip_in + 0.06) / height)

    os.makedirs(output_dir, exist_ok=True)
    image_path = os.path.join(output_dir, f"{os.path.basename(name)}.{image_format}")
    fig.savefig(image_path, dpi=130, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return image_path


def _spring_layout_3d(nodes, edges, iterations: int = 220):
    """A randomness-free 3-D Fruchterman-Reingold layout (no external deps).

    Nodes start on a Fibonacci sphere (no random numbers) and are relaxed by edge
    attraction + all-pairs repulsion. Returns ``node -> (x, y, z)``.

    Unlike :func:`_spring_layout`, the nodes are taken in the order given: the
    caller passes a set, so the interactive figure may come out oriented
    differently from run to run. It is rotatable anyway, so that was never
    pinned down the way the committed 2-D PNGs had to be.
    """
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
    k = 1.0 / (n ** (1 / 3)) if n else 1.0   # ideal edge length: cube root in 3-D (sqrt in 2-D)
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
        for v in nodes:
            dist = math.sqrt(sum(x * x for x in disp[v])) or 1e-6
            for c in range(3):
                pos[v][c] += disp[v][c] / dist * min(dist, 0.1)
    return {v: tuple(p) for v, p in pos.items()}


def _show_simplicial_3d(model, name, output_dir, title, assignment=None) -> str:
    """Draw a simplicial belief model as an INTERACTIVE 3-D Plotly figure (HTML).

    Facets are drawn as solid simplices, coloured by which agents' **belief
    subcomplexes** they belong to; nodes are coloured by agent. The output is a
    **self-contained, offline HTML** file the user can open in a browser and
    rotate/zoom -- which is where 3-D earns its keep (a tetrahedron cannot be shown
    in 2-D).

    Geometric limit: under UCF each facet is an ``(|Ag|-1)``-simplex, so the drawing
    is **faithful only for up to 4 agents** (edge / triangle / tetrahedron -- the
    3-simplex is the largest that fits in 3-D). For **5 or more agents** a facet is a
    4-simplex or higher, which cannot be embedded in 3-D without self-intersection;
    the figure then shows a *projection* (the full boundary 2-skeleton of each
    facet), and a warning is emitted.
    """
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
        label = "belief: " + ("+".join(map(str, sig)) if sig else "none")
        show_in_legend = sig not in seen_sig
        seen_sig.add(sig)
        world = str(model.world_of_facet.get(facet, ""))
        if len(pts) >= 3:
            # A facet with m nodes is an (m-1)-simplex; its full boundary 2-skeleton
            # is every triple of vertices. Explicit (i,j,k) faces render reliably
            # (unlike alphahull on coplanar points). For m<=4 (triangle/tetrahedron)
            # this is a FAITHFUL drawing; for m>=5 it is a projection of a >3-D
            # simplex, which cannot be embedded in 3-D without self-intersection.
            faces = list(itertools.combinations(range(len(pts)), 3))
            traces.append(go.Mesh3d(
                x=[p[0] for p in pts], y=[p[1] for p in pts], z=[p[2] for p in pts],
                i=[f[0] for f in faces], j=[f[1] for f in faces], k=[f[2] for f in faces],
                # Translucent so facets behind stay visible; flat shading keeps
                # each simplex looking like flat panels rather than a smooth blob.
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

    # Facet names at the centroids (one text trace for all of them). The hover
    # already says the world, but a label survives rotation and screenshots.
    named = [(F, facet_name(model, F)) for F in model.facets]
    named = [(F, n) for F, n in named if n]
    if named:
        cents = [[sum(pos[nd][k] for nd in F) / len(F) for k in range(3)] for F, _ in named]
        traces.append(go.Scatter3d(
            x=[c[0] for c in cents], y=[c[1] for c in cents], z=[c[2] for c in cents],
            mode="text", text=[n for _, n in named], textposition="middle center",
            textfont=dict(size=10, color="#222222"),
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
                               line=dict(color="#999999", width=1),
                               name="1-skeleton", hoverinfo="skip", showlegend=False))

    # Nodes, one trace per agent (coloured, labelled by agent, class on hover).
    # With an assignment, the visible label becomes "a (¬Mb, Mc)" -- the
    # perspective's observed literals, thesis style -- and the hover shows the
    # knowledge class plus the literals, so nothing is lost by rotating away.
    for a in agents:
        ns = [nd for nd in model.nodes if nd.agent == a]

        def _txt(nd) -> str:
            # The user's vertex name when the complex was defined directly,
            # the agent's letter otherwise.
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
            marker=dict(size=6, color=colors[a], line=dict(color="#222", width=1)),
            text=[_txt(nd) for nd in ns], textposition="top center",
            hovertext=[_hover(nd) for nd in ns], hoverinfo="text",
            name=f"agent {a}", legendgroup=f"agent {a}",
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=title, showlegend=True,
        # No axes: the coordinates are a layout artefact and carry no meaning.
        scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False)),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{os.path.basename(name)}.html")
    fig.write_html(path, include_plotlyjs=True)  # self-contained, works offline
    return path

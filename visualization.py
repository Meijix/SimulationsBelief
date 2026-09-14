"""Visualisation for every model in the project: text diagrams and images.

Kept separate from the models so they stay small, dependency-free descriptions of
the logic, and all drawing concerns live here. These are plain functions taking a
model as their first argument, so no model class has to carry any drawing code.

There are only three functions to remember, and each one accepts **any** model in
the project (a :class:`RelationalFrame`, a :class:`KnowledgeBeliefFrame` or a
:class:`SimplicialBeliefModel`) -- the right renderer is chosen automatically:

    visualize(model)            -> str, a text diagram (no dependencies)
    show(model, "name")         -> writes outputs/name.png, returns the path
    to_dot(model)               -> str, Graphviz DOT source (relational models)

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

# Fill colours for the belief subcomplexes of a simplicial model.
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
        title: Caption (defaults to ``name``); validity is appended automatically.
        dim: Simplicial models only -- 2 for a static image, 3 for interactive HTML.
        open: If True, open the generated file in the OS default viewer/browser
            after writing it. Default False, so batch scripts and tests never spawn
            viewers; pass ``open=True`` for an interactive one-off.
        output_dir: Directory for generated files (default :data:`OUTPUT_DIR`).
        image_format: Any format ``dot``/matplotlib supports (``png``, ``svg``, ...).
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
        if dim == 3:
            path = _show_simplicial_3d(model, name, output_dir, caption,
                                       assignment=assignment)
        else:
            path = _show_simplicial(model, name, output_dir, caption, image_format,
                                    assignment=assignment)
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
) -> str:
    """Return Graphviz DOT source for a relational or knowledge+belief model.

    Use this to export a figure without the ``dot`` binary, or to tweak the source
    by hand; :func:`show` calls it for you. The arguments are those of
    :func:`show`; ``None`` means "infer from the model". With ``valuation``,
    every world is labelled with its literals (see :func:`world_literals`).
    Simplicial models have no DOT form -- draw them with :func:`show`.
    """
    kind = _kind(model)
    if kind == "knowledge_belief":
        return _dot_knowledge_belief(model, title, omit_self_loops, valuation)
    if kind == "frame":
        return _dot_frame(
            model, title, omit_self_loops, undirected_symmetric, highlight_missing,
            valuation,
        )
    raise TypeError("Simplicial models have no DOT form; use show(model, name).")


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


def _world_label_attr(valuation, world) -> str:
    """DOT ``label=...`` attribute for a world carrying its valuation literals.

    Returns an empty string when there is nothing to show, so callers can splice
    the result into an attribute list unconditionally. The literals go on a
    second line under the world name (the DOT escape ``\\n``), Figure-33 style.
    Only the label attribute changes -- the node's DOT identifier stays the bare
    world name, so edges keep pointing at the same node.
    """
    if not valuation:
        return ""
    literals = world_literals(valuation, world)
    if not literals:
        return ""
    text = _dot_escape(str(world)) + "\\n(" + _dot_escape(", ".join(literals)) + ")"
    return f'label="{text}"'


def _html_escape(value) -> str:
    """Escape a value for use inside a Graphviz HTML-like label."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _dot_header(caption: str) -> List[str]:
    """Opening lines of a DOT digraph: layout, caption and default node/edge style."""
    return [
        "digraph Model {",
        "    rankdir=LR;",
        '    fontname="Helvetica"; overlap=false; nodesep=0.4; ranksep=0.6;',
        f'    label="{_dot_escape(caption)}"; labelloc="t"; fontsize=13;',
        '    node [shape=circle, style=filled, fillcolor="#f4f6f8",'
        ' color="#333333", fontname="Helvetica", width=0.5];',
        '    edge [penwidth=1.6, arrowsize=0.8, fontname="Helvetica"];',
    ]


def _dot_legend(cells: List[str], anchor) -> List[str]:
    """A single horizontal legend strip pinned to the bottom of the graph."""
    if not cells:
        return []
    lines = [
        "    legend [shape=none, margin=0, label=<",
        '      <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="14" CELLPADDING="0"><TR>',
        *("        " + c for c in cells),
        "      </TR></TABLE>",
        "    >];",
        "    { rank=sink; legend; }",
    ]
    if anchor is not None:
        # Invisible edge from a real node pulls the legend to the bottom.
        lines.append(f"    {_dot_id(anchor)} -> legend [style=invis];")
    return lines


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
) -> str:
    """DOT for one frame, one colour per agent (see :func:`to_dot`)."""
    # Style defaults: knowledge (S5) is symmetric and reflexive, so it reads best
    # as undirected edges with the assumed self-loops hidden; belief keeps arrows.
    if omit_self_loops is None or undirected_symmetric is None:
        s5 = _is_s5(frame)
        omit_self_loops = s5 if omit_self_loops is None else omit_self_loops
        undirected_symmetric = s5 if undirected_symmetric is None else undirected_symmetric

    colors = agent_colors(frame)
    # Caption shows validity so valid and invalid models are told apart at a
    # glance -- judged against the frame's DECLARED logic (violations() consults
    # axiom_d), not blanket KD45: a legal K45 frame must not read as broken.
    violations = frame.violations()
    logic = frame.logic_label()
    status = f"valid {logic}" if not violations else f"INVALID: {len(violations)} violation(s)"
    lines = _dot_header(f"{title} — {status}" if title else status)

    # Worlds that are a dead end for at least one agent. Under KD45 that is a
    # seriality violation and gets the red error styling; under K45 (axiom_d
    # off) a dead end is a legal defunct-belief world, so nothing to flag.
    dead_end_worlds: Set = set()
    if highlight_missing and frame.axiom_d:
        for stuck in frame.dead_ends().values():
            dead_end_worlds |= stuck
    for w in sorted(frame.worlds, key=str):
        # The valuation label rides along with whatever styling the world gets:
        # attributes are collected and joined, so dead-end highlighting and the
        # literals never fight over the bracket.
        attrs = []
        label = _world_label_attr(valuation, w)
        if label:
            attrs.append(label)
        if w in dead_end_worlds:
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
    if highlight_missing:
        for a in sorted(frame.agents, key=str):
            for (source, target) in _sorted_edges(frame.missing_edges()[a]):
                lines.append(
                    f'    {_dot_id(source)} -> {_dot_id(target)} '
                    f'[style=dashed, color="{MISSING_COLOR}"];'
                )

    cells = [_agent_cell(a, colors[a]) for a in sorted(frame.agents, key=str)]
    if cells:
        if highlight_missing and any(frame.missing_edges().values()):
            cells.append(_note_cell("&#9548;&#9548; missing edge", MISSING_COLOR))
        if dead_end_worlds:
            cells.append(_note_cell("&#9711; dead end", MISSING_COLOR))
        anchor = sorted(frame.worlds, key=str)
        lines += _dot_legend(cells, anchor[0] if anchor else None)
    lines.append("}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# DOT: knowledge and belief in one figure
# --------------------------------------------------------------------------- #
def _dot_knowledge_belief(kb, title: str | None, omit_self_loops: bool | None,
                          valuation=None) -> str:
    """DOT for a knowledge+belief model, both relations in one figure.

    Knowledge ``R_a`` is drawn as thin, arrow-less lines (S5 is symmetric, so
    indistinguishability has no direction); belief ``Q_a`` as bold, directed arrows
    (what the agent actually believes). Both are coloured by agent. Since
    ``Q_a ⊆ R_a``, each belief arrow sits alongside a knowledge line.
    """
    omit_self_loops = True if omit_self_loops is None else omit_self_loops
    colors = agent_colors(kb)
    status = "valid" if kb.is_valid() else "INVALID"
    lines = _dot_header(f"{title} — {status}" if title else status)
    for w in sorted(kb.worlds, key=str):
        label = _world_label_attr(valuation, w)
        lines.append(f"    {_dot_id(w)}" + (f" [{label}]" if label else "") + ";")

    # Knowledge: thin, undirected (symmetric). Belief: bold, directed.
    for a in sorted(kb.agents, key=str):
        color = colors[a]
        relation = kb.knowledge.relations[a]
        drawn: Set[frozenset] = set()
        for (s, t) in _sorted_edges(relation):
            if omit_self_loops and s == t:
                continue
            if s != t and (t, s) in relation:
                key = frozenset((s, t))
                if key in drawn:
                    continue
                drawn.add(key)
                lines.append(
                    f'    {_dot_id(s)} -> {_dot_id(t)} [color="{color}", dir=none, penwidth=0.7];'
                )
            else:
                lines.append(f'    {_dot_id(s)} -> {_dot_id(t)} [color="{color}", penwidth=0.7];')
    for a in sorted(kb.agents, key=str):
        color = colors[a]
        for (s, t) in _sorted_edges(kb.belief.relations[a]):
            if omit_self_loops and s == t:
                continue
            lines.append(
                f'    {_dot_id(s)} -> {_dot_id(t)} [color="{color}", penwidth=2.6, arrowsize=1.0];'
            )

    cells = [_agent_cell(a, colors[a]) for a in sorted(kb.agents, key=str)]
    if cells:
        cells.append(_note_cell("&#9472; knowledge (thin)"))
        cells.append(_note_cell("&#10142; belief (bold)"))
        anchor = sorted(kb.worlds, key=str)
        lines += _dot_legend(cells, anchor[0] if anchor else None)
    lines.append("}")
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
def _belief_signature(model, facet, agents):
    """The tuple of agents whose belief subcomplex contains ``facet``."""
    return tuple(a for a in agents if facet in model.belief_facets.get(a, ()))


def _signature_colors(model, agents) -> Dict[tuple, str]:
    """Map each belief signature to a fill colour (the empty one stays neutral grey)."""
    signatures = {_belief_signature(model, f, agents) for f in model.facets}
    colors = {(): "#dddddd"}
    for i, sig in enumerate(sorted((s for s in signatures if s), key=lambda s: (len(s), s))):
        colors[sig] = BELIEF_PALETTE[i % len(BELIEF_PALETTE)]
    return colors


def _skeleton_edges(model):
    """The 1-skeleton: every pair of nodes sharing a facet. Drives the layouts."""
    edges = set()
    for facet in model.facets:
        for u, v in itertools.combinations(facet, 2):
            edges.add(frozenset((u, v)))
    return [tuple(e) for e in edges]


def _spring_layout(nodes, edges, iterations: int = 250):
    """A small deterministic Fruchterman-Reingold layout (no external deps).

    Nodes start on a circle (deterministic, no randomness) and are then relaxed by
    edge attraction + all-pairs repulsion. Returns ``node -> (x, y)``.
    """
    import math

    nodes = list(nodes)
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
        for v in nodes:
            dx, dy = disp[v]
            d = math.hypot(dx, dy) or 1e-6
            pos[v][0] += dx / d * min(d, 0.08)
            pos[v][1] += dy / d * min(d, 0.08)
    return {v: (p[0], p[1]) for v, p in pos.items()}


def _show_simplicial(model, name, output_dir, title, image_format,
                     assignment=None) -> str:
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
    """
    import math

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch, Polygon

    agents = sorted(model.agents, key=str)
    colors = {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(agents)}
    edge_pairs = _skeleton_edges(model)
    pos = _spring_layout(model.nodes, edge_pairs)
    sig_color = _signature_colors(model, agents)

    fig, ax = plt.subplots(figsize=(8, 7))

    # Draw facets (filled), largest first so smaller ones stay visible.
    for facet in sorted(model.facets, key=lambda F: -len(F)):
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
    ax.legend(handles=handles, loc="upper left", fontsize=8, framealpha=0.9)

    ax.set_title(title, fontsize=12)
    ax.set_axis_off()
    ax.set_aspect("equal")
    fig.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    image_path = os.path.join(output_dir, f"{os.path.basename(name)}.{image_format}")
    fig.savefig(image_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return image_path


def _spring_layout_3d(nodes, edges, iterations: int = 220):
    """A deterministic 3-D Fruchterman-Reingold layout (no external deps).

    Nodes start on a Fibonacci sphere (deterministic, no randomness) and are relaxed
    by edge attraction + all-pairs repulsion. Returns ``node -> (x, y, z)``.
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
    k = 1.0 / (n ** (1 / 3)) if n else 1.0
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
            if assignment is None:
                return str(a)
            literals = node_literals(assignment, nd)
            return f"{a} ({', '.join(literals)})" if literals else str(a)

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
        scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False)),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{os.path.basename(name)}.html")
    fig.write_html(path, include_plotlyjs=True)  # self-contained, works offline
    return path

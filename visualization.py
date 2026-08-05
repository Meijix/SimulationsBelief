"""Visualisation for RelationalFrame: text diagrams, Graphviz DOT and images.

Kept separate from the model (relational_frame.py) so the model stays a small,
dependency-free description of the logic, and all rendering concerns live here.
These are plain functions taking a frame as their first argument -- when Step 2
adds simplicial models, their renderers can live alongside these without the
model classes having to carry any drawing code.

The functions only read the frame's public surface (agents, worlds, relations,
successors(), missing_edges(), dead_ends(), kd45_violations()), so there is no
circular dependency: this module imports the model, never the other way round.
"""

from __future__ import annotations

import itertools
import os
import shutil
import subprocess
import warnings
from typing import TYPE_CHECKING, Dict, Set

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


def _dot_escape(value) -> str:
    """Escape a value for use inside a double-quoted DOT string (quotes/backslash)."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _dot_id(value) -> str:
    """Return a safely double-quoted DOT identifier for any world/agent label."""
    return f'"{_dot_escape(value)}"'


def _html_escape(value) -> str:
    """Escape a value for use inside a Graphviz HTML-like label."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def agent_colors(frame: "RelationalFrame") -> Dict["Agent", str]:
    """Return a stable ``agent -> hex colour`` mapping from the palette.

    Colours are assigned by the agent's sorted position and the palette cycles,
    so the same frame always colours the same agent the same way.
    """
    ordered = sorted(frame.agents, key=str)
    return {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(ordered)}


def visualize(frame: "RelationalFrame", agent: "Agent | None" = None) -> str:
    """Return a dependency-free text diagram of the accessibility relations.

    For each agent, every world is listed with the set of worlds it can reach in
    one step (``->``). A self-loop is marked with ``(self)`` so the KD45
    "reflexive within its cluster" structure is easy to spot.

    Args:
        agent: If given, show only that agent's relation; otherwise show all.
    """
    chosen = [agent] if agent is not None else sorted(frame.agents, key=str)
    lines = []
    for a in chosen:
        if a not in frame.agents:
            raise ValueError(f"Unknown agent {a!r}.")
        lines.append(f"Agent {a!r}:")
        for w in sorted(frame.worlds, key=str):
            targets = sorted(frame.successors(a, w), key=str)
            rendered = ", ".join(f"{t}{' (self)' if t == w else ''}" for t in targets)
            lines.append(f"    {w} -> {{{rendered}}}")
    return "\n".join(lines)


def to_dot(
    frame: "RelationalFrame",
    title: str | None = None,
    highlight_missing: bool = True,
    omit_self_loops: bool = False,
    undirected_symmetric: bool = False,
) -> str:
    """Export the frame as Graphviz DOT source, one colour per agent.

    A caption reports whether the frame satisfies KD45 (and, if not, how many
    violations were found), and a horizontal legend maps colours to agents.

    When ``highlight_missing`` is True (default) and the frame is invalid, the
    edges required by transitivity/Euclideanness but *missing* are overlaid as
    dashed red arrows and dead-end worlds are highlighted.

    Args:
        title: Optional caption prefix; the KD45 status is appended automatically.
        highlight_missing: Draw missing axiom-4/5 edges and dead-end worlds in red.
        omit_self_loops: Hide reflexive ``w -> w`` edges. In KD45/S5 nearly every
            world is reflexive, so hiding the loops (reflexivity is assumed)
            declutters dense models like muddy children.
        undirected_symmetric: When both ``u -> v`` and ``v -> u`` exist for an
            agent, draw a single arrow-less edge instead of two. Ideal for S5
            (knowledge) models, whose relations are symmetric.
    """
    colors = agent_colors(frame)
    # Caption shows validity so valid and invalid models are told apart at a glance.
    violations = frame.kd45_violations()
    status = "valid KD45" if not violations else f"INVALID: {len(violations)} violation(s)"
    caption = f"{title} — {status}" if title else status
    # Graph-wide cosmetics: soft fills, Helvetica, breathing room, no overlaps.
    lines = [
        "digraph RelationalFrame {",
        "    rankdir=LR;",
        '    fontname="Helvetica"; overlap=false; nodesep=0.4; ranksep=0.6;',
        f'    label="{_dot_escape(caption)}"; labelloc="t"; fontsize=13;',
        '    node [shape=circle, style=filled, fillcolor="#f4f6f8",'
        ' color="#333333", fontname="Helvetica", width=0.5];',
        '    edge [penwidth=1.6, arrowsize=0.8, fontname="Helvetica"];',
    ]
    # Worlds that are a dead end for at least one agent (seriality violation).
    dead_end_worlds: Set = set()
    if highlight_missing:
        for stuck in frame.dead_ends().values():
            dead_end_worlds |= stuck
    for w in sorted(frame.worlds, key=str):
        if w in dead_end_worlds:
            lines.append(
                f'    {_dot_id(w)} [fillcolor="#FDE7E7", color="{MISSING_COLOR}", '
                f'style="filled,dashed", penwidth=2];'
            )
        else:
            lines.append(f'    {_dot_id(w)};')
    # One coloured edge per agent -- the colour identifies the agent, so no
    # per-edge labels are needed (the legend below maps colour -> agent).
    for a in sorted(frame.agents, key=str):
        color = colors[a]
        relation = frame.relations[a]
        drawn_undirected: Set[frozenset] = set()
        for (source, target) in sorted(relation, key=lambda e: (str(e[0]), str(e[1]))):
            if omit_self_loops and source == target:
                continue
            if undirected_symmetric and source != target and (target, source) in relation:
                # Symmetric pair -> draw once, without arrowheads.
                key = frozenset((source, target))
                if key in drawn_undirected:
                    continue
                drawn_undirected.add(key)
                lines.append(f'    {_dot_id(source)} -> {_dot_id(target)} [color="{color}", dir=none];')
            else:
                lines.append(f'    {_dot_id(source)} -> {_dot_id(target)} [color="{color}"];')
    # Overlay the edges that are required but missing (dashed red, no label).
    if highlight_missing:
        for a in sorted(frame.agents, key=str):
            for (source, target) in sorted(
                frame.missing_edges()[a], key=lambda e: (str(e[0]), str(e[1]))
            ):
                lines.append(
                    f'    {_dot_id(source)} -> {_dot_id(target)} [style=dashed, color="{MISSING_COLOR}"];'
                )
    # Legend: a single horizontal strip pinned to the bottom (rank=sink).
    if frame.agents:
        cells = []
        for a in sorted(frame.agents, key=str):
            cells.append(
                f'<TD><FONT COLOR="{colors[a]}" POINT-SIZE="15">&#9679;</FONT>'
                f' <FONT POINT-SIZE="11">{_html_escape(a)}</FONT></TD>'
            )
        if highlight_missing and any(frame.missing_edges().values()):
            cells.append(
                f'<TD><FONT COLOR="{MISSING_COLOR}" POINT-SIZE="11">'
                f'&#9548;&#9548; missing edge</FONT></TD>'
            )
        if dead_end_worlds:
            cells.append(
                f'<TD><FONT COLOR="{MISSING_COLOR}" POINT-SIZE="11">'
                f'&#9711; dead end</FONT></TD>'
            )
        lines.append("    legend [shape=none, margin=0, label=<")
        lines.append(
            '      <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="14" CELLPADDING="0"><TR>'
        )
        lines.extend("        " + c for c in cells)
        lines.append("      </TR></TABLE>")
        lines.append("    >];")
        lines.append("    { rank=sink; legend; }")
        # Invisible edge from a real node pulls the legend to the bottom.
        anchor = sorted(frame.worlds, key=str)
        if anchor:
            lines.append(f'    {_dot_id(anchor[0])} -> legend [style=invis];')
    lines.append("}")
    return "\n".join(lines)


def render(
    frame: "RelationalFrame",
    name: str = "frame",
    image_format: str = "png",
    output_dir: str = OUTPUT_DIR,
    title: str | None = None,
    omit_self_loops: bool = False,
    undirected_symmetric: bool = False,
) -> str:
    """Render the frame to an image file using the Graphviz ``dot`` binary.

    Writes ``<output_dir>/<name>.dot`` and ``<output_dir>/<name>.<image_format>``
    (creating the directory if missing). Because ``name`` is a free label, you can
    render as many models as you like, each to its own file.

    Args:
        name: Base filename without extension (e.g. ``"alice_belief"``).
        image_format: Any format ``dot`` supports (``png``, ``svg``, ``pdf`` ...).
        output_dir: Directory for generated files (default :data:`OUTPUT_DIR`).
        title: Optional caption (defaults to ``name``).
        omit_self_loops: Forwarded to :func:`to_dot` -- hide reflexive edges.
        undirected_symmetric: Forwarded to :func:`to_dot` -- merge symmetric pairs.

    Returns:
        The path to the generated image file.

    Raises:
        RuntimeError: If the ``dot`` binary is not found on ``PATH``.
    """
    dot_source = to_dot(
        frame,
        title=title if title is not None else name,
        omit_self_loops=omit_self_loops,
        undirected_symmetric=undirected_symmetric,
    )
    return _write_and_run_dot(dot_source, name, image_format, output_dir)


def _write_and_run_dot(dot_source: str, name: str, image_format: str, output_dir: str) -> str:
    """Write DOT to ``<output_dir>/<name>.dot`` and render it with Graphviz ``dot``.

    Raises:
        RuntimeError: If the ``dot`` binary is not found on ``PATH``.
    """
    if shutil.which("dot") is None:
        raise RuntimeError(
            "Graphviz 'dot' not found on PATH. Install it (e.g. 'brew install "
            "graphviz') or use to_dot()/to_dot_knowledge_belief() to export manually."
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


def to_dot_knowledge_belief(kb, title: str | None = None, omit_self_loops: bool = True) -> str:
    """Combined DOT for a knowledge+belief model, both relations in one figure.

    Knowledge ``R_a`` is drawn as thin, arrow-less lines (S5 is symmetric, so
    indistinguishability has no direction); belief ``Q_a`` is drawn as bold,
    directed arrows (what the agent actually believes). Both are coloured by agent.
    Since ``Q_a ⊆ R_a``, each belief arrow sits alongside a knowledge line.

    Args:
        kb: a :class:`KnowledgeBeliefFrame` (duck-typed: needs ``agents``, ``worlds``,
            ``knowledge``, ``belief``, ``is_valid``).
        title: optional caption prefix; validity is appended.
        omit_self_loops: hide reflexive edges (assumed in KD45/S5).
    """
    colors = agent_colors(kb)
    caption = (f"{title} — " if title else "") + ("valid" if kb.is_valid() else "INVALID")
    lines = [
        "digraph KnowledgeBelief {",
        "    rankdir=LR;",
        '    fontname="Helvetica"; overlap=false; nodesep=0.4; ranksep=0.7;',
        f'    label="{_dot_escape(caption)}"; labelloc="t"; fontsize=13;',
        '    node [shape=circle, style=filled, fillcolor="#f4f6f8",'
        ' color="#333333", fontname="Helvetica", width=0.5];',
    ]
    for w in sorted(kb.worlds, key=str):
        lines.append(f'    {_dot_id(w)};')
    # Knowledge: thin, undirected (symmetric), one per agent colour.
    for a in sorted(kb.agents, key=str):
        color = colors[a]
        relation = kb.knowledge.relations[a]
        drawn: Set[frozenset] = set()
        for (s, t) in sorted(relation, key=lambda e: (str(e[0]), str(e[1]))):
            if omit_self_loops and s == t:
                continue
            if s != t and (t, s) in relation:
                key = frozenset((s, t))
                if key in drawn:
                    continue
                drawn.add(key)
                lines.append(f'    {_dot_id(s)} -> {_dot_id(t)} [color="{color}", dir=none, penwidth=0.7];')
            else:
                lines.append(f'    {_dot_id(s)} -> {_dot_id(t)} [color="{color}", penwidth=0.7];')
    # Belief: bold, directed arrows.
    for a in sorted(kb.agents, key=str):
        color = colors[a]
        for (s, t) in sorted(kb.belief.relations[a], key=lambda e: (str(e[0]), str(e[1]))):
            if omit_self_loops and s == t:
                continue
            lines.append(f'    {_dot_id(s)} -> {_dot_id(t)} [color="{color}", penwidth=2.6, arrowsize=1.0];')
    # Legend: agent colours + the two line styles.
    if kb.agents:
        cells = [
            f'<TD><FONT COLOR="{colors[a]}" POINT-SIZE="15">&#9679;</FONT>'
            f' <FONT POINT-SIZE="11">{_html_escape(a)}</FONT></TD>'
            for a in sorted(kb.agents, key=str)
        ]
        cells.append('<TD><FONT POINT-SIZE="11">&#9472; knowledge (thin)</FONT></TD>')
        cells.append('<TD><FONT POINT-SIZE="11">&#10142; belief (bold)</FONT></TD>')
        lines.append("    legend [shape=none, margin=0, label=<")
        lines.append('      <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="14" CELLPADDING="0"><TR>')
        lines.extend("        " + c for c in cells)
        lines.append("      </TR></TABLE>")
        lines.append("    >];")
        lines.append("    { rank=sink; legend; }")
        anchor = sorted(kb.worlds, key=str)
        if anchor:
            lines.append(f'    {_dot_id(anchor[0])} -> legend [style=invis];')
    lines.append("}")
    return "\n".join(lines)


def render_knowledge_belief(
    kb,
    name: str = "kb_frame",
    image_format: str = "png",
    output_dir: str = OUTPUT_DIR,
    title: str | None = None,
    omit_self_loops: bool = True,
) -> str:
    """Render a knowledge+belief model to a single combined image (see :func:`to_dot_knowledge_belief`)."""
    dot_source = to_dot_knowledge_belief(
        kb, title=title if title is not None else name, omit_self_loops=omit_self_loops
    )
    return _write_and_run_dot(dot_source, name, image_format, output_dir)


# --------------------------------------------------------------------------- #
# Simplicial belief models (matplotlib; facets as filled simplices)
# --------------------------------------------------------------------------- #
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


def render_simplicial(
    model,
    name: str = "simplicial",
    output_dir: str = OUTPUT_DIR,
    title: str | None = None,
    image_format: str = "png",
) -> str:
    """Render a simplicial belief model: facets as filled simplices, nodes by agent.

    Each facet (a possible world) is drawn as a filled polygon over its nodes -- an
    edge for 2 agents, a triangle for 3, and the convex node polygon for more. The
    fill colour encodes which agents' **belief subcomplexes** the facet belongs to
    (the Figure-3 colouring); facets in no belief subcomplex are light grey. Nodes are
    coloured by agent (the shared palette).

    Args:
        model: a duck-typed simplicial belief model exposing ``agents``, ``nodes``,
            ``facets``, ``belief_facets`` and ``world_of_facet``.
        name: output basename (written to ``<output_dir>/<name>.<image_format>``).
        title: optional caption.

    Returns:
        The path to the generated image.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch, Polygon

    agents = sorted(model.agents, key=str)
    colors = {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(agents)}

    # 1-skeleton edges (pairs of nodes sharing a facet) drive the layout.
    edges = set()
    for facet in model.facets:
        fl = list(facet)
        for i in range(len(fl)):
            for j in range(i + 1, len(fl)):
                edges.add(frozenset((fl[i], fl[j])))
    edge_pairs = [tuple(e) for e in edges]
    pos = _spring_layout(model.nodes, edge_pairs)

    # A distinct fill colour per "belief signature" (set of agents believing the facet).
    # The empty signature (in no belief subcomplex) always gets a neutral grey; the
    # non-empty ones get distinct belief colours in a stable order.
    signatures = set()
    for facet in model.facets:
        signatures.add(tuple(a for a in agents if facet in model.belief_facets.get(a, ())))
    belief_palette = ["#7B4FA3", "#D98A00", "#2E8B57", "#B23A48", "#3A6EA5", "#8C6D1F"]
    sig_color = {(): "#dddddd"}
    for i, sig in enumerate(sorted((s for s in signatures if s), key=lambda s: (len(s), s))):
        sig_color[sig] = belief_palette[i % len(belief_palette)]

    fig, ax = plt.subplots(figsize=(8, 7))

    # Draw facets (filled), largest first so smaller ones stay visible.
    for facet in sorted(model.facets, key=lambda F: -len(F)):
        pts = [pos[n] for n in facet]
        sig = tuple(a for a in agents if facet in model.belief_facets.get(a, ()))
        col = sig_color[sig]
        if len(pts) == 2:
            (x0, y0), (x1, y1) = pts
            ax.plot([x0, x1], [y0, y1], color=col, linewidth=6, alpha=0.5, zorder=1)
        else:
            # order the polygon points by angle around their centroid (convex-ish)
            import math

            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
            ax.add_patch(Polygon(pts, closed=True, facecolor=col, edgecolor=col,
                                 alpha=0.35, linewidth=1.5, zorder=1))

    # Draw the 1-skeleton edges faintly.
    for (u, v) in edge_pairs:
        (x0, y0), (x1, y1) = pos[u], pos[v]
        ax.plot([x0, x1], [y0, y1], color="#999999", linewidth=0.6, zorder=2)

    # Draw nodes, coloured by agent, labelled by class.
    for node in model.nodes:
        x, y = pos[node]
        ax.scatter([x], [y], s=260, color=colors[node.agent],
                   edgecolor="#222", linewidth=1.0, zorder=3)
        members = ",".join(sorted(map(str, node.cls)))
        ax.annotate(f"{node.agent}", (x, y), color="white", ha="center", va="center",
                    fontsize=8, fontweight="bold", zorder=4)

    # Legend: agents + belief signatures.
    agent_handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor=colors[a],
                            markersize=10, label=f"agent {a}") for a in agents]
    sig_handles = []
    for sig in sorted(signatures, key=lambda s: (len(s), s)):
        lbl = "belief: " + ("+".join(map(str, sig)) if sig else "none")
        sig_handles.append(Patch(facecolor=sig_color[sig], alpha=0.5, label=lbl))
    ax.legend(handles=agent_handles + sig_handles, loc="upper left",
              fontsize=8, framealpha=0.9)

    ax.set_title(title or name, fontsize=12)
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


def render_simplicial_3d(
    model,
    name: str = "simplicial_3d",
    output_dir: str = OUTPUT_DIR,
    title: str | None = None,
) -> str:
    """Render a simplicial belief model as an INTERACTIVE 3-D Plotly figure (HTML).

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

    Args:
        model: a duck-typed simplicial belief model (``agents``, ``nodes``,
            ``facets``, ``belief_facets``, ``world_of_facet``).
        name: output basename -> ``<output_dir>/<name>.html``.
        title: optional caption.

    Returns:
        The path to the generated HTML file.
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

    edges = set()
    for facet in model.facets:
        fl = list(facet)
        for i in range(len(fl)):
            for j in range(i + 1, len(fl)):
                edges.add(frozenset((fl[i], fl[j])))
    edge_pairs = [tuple(e) for e in edges]
    pos = _spring_layout_3d(model.nodes, edge_pairs)

    # Belief-signature colours: empty signature -> neutral grey, else a stable palette.
    signatures = set()
    for facet in model.facets:
        signatures.add(tuple(a for a in agents if facet in model.belief_facets.get(a, ())))
    belief_palette = ["#7B4FA3", "#D98A00", "#2E8B57", "#B23A48", "#3A6EA5", "#8C6D1F"]
    sig_color = {(): "#bbbbbb"}
    for i, sig in enumerate(sorted((s for s in signatures if s), key=lambda s: (len(s), s))):
        sig_color[sig] = belief_palette[i % len(belief_palette)]

    traces = []
    seen_sig = set()
    for facet in sorted(model.facets, key=lambda F: str(model.world_of_facet.get(F, ""))):
        pts = [pos[nd] for nd in facet]
        sig = tuple(a for a in agents if facet in model.belief_facets.get(a, ()))
        col = sig_color[sig]
        lbl = "belief: " + ("+".join(map(str, sig)) if sig else "none")
        show = sig not in seen_sig
        seen_sig.add(sig)
        world = str(model.world_of_facet.get(facet, ""))
        if len(pts) >= 3:
            # A facet with m nodes is an (m-1)-simplex; its full boundary 2-skeleton
            # is every triple of vertices. Explicit (i,j,k) faces render reliably
            # (unlike alphahull on coplanar points). For m<=4 (triangle/tetrahedron)
            # this is a FAITHFUL drawing; for m>=5 it is a projection of a >3-D
            # simplex, which cannot be embedded in 3-D without self-intersection.
            m = len(pts)
            faces = list(itertools.combinations(range(m), 3))
            traces.append(go.Mesh3d(
                x=[p[0] for p in pts], y=[p[1] for p in pts], z=[p[2] for p in pts],
                i=[f[0] for f in faces], j=[f[1] for f in faces], k=[f[2] for f in faces],
                color=col, opacity=0.45, flatshading=True,
                name=lbl, legendgroup=lbl, showlegend=show,
                hovertext=world, hoverinfo="text",
            ))
        elif len(pts) == 2:
            (x0, y0, z0), (x1, y1, z1) = pts
            traces.append(go.Scatter3d(
                x=[x0, x1], y=[y0, y1], z=[z0, z1], mode="lines",
                line=dict(color=col, width=8),
                name=lbl, legendgroup=lbl, showlegend=show,
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
    for a in agents:
        ns = [nd for nd in model.nodes if nd.agent == a]
        traces.append(go.Scatter3d(
            x=[pos[nd][0] for nd in ns], y=[pos[nd][1] for nd in ns], z=[pos[nd][2] for nd in ns],
            mode="markers+text",
            marker=dict(size=6, color=colors[a], line=dict(color="#222", width=1)),
            text=[str(a)] * len(ns), textposition="top center",
            hovertext=[",".join(sorted(map(str, nd.cls))) for nd in ns], hoverinfo="text",
            name=f"agent {a}", legendgroup=f"agent {a}",
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=title or name, showlegend=True,
        scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False)),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{os.path.basename(name)}.html")
    fig.write_html(path, include_plotlyjs=True)  # self-contained, works offline
    return path

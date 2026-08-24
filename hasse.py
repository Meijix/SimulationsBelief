# -*- coding: utf-8 -*-
"""Hasse diagrams (face lattices) of simplicial complexes, drawn with Graphviz.

This module gives the project a *combinatorial* picture of a simplicial complex, to
be read next to the *geometric* one that :mod:`visualization` already draws. The
geometric picture (``show(model, "fig3")``) answers "what does the complex look
like?"; the Hasse diagram answers "which simplices are in it, and which one is a
face of which?" -- the question that actually matters when you are checking a
translation or a belief subcomplex by hand.

Why a Hasse diagram at all
--------------------------
The faces of a finite abstract simplicial complex, ordered by inclusion, form a
graded poset: every face has a dimension (``|face| - 1``), and going up one step in
the order always raises the dimension by exactly one. A Hasse diagram is the
standard drawing of such a poset:

    * one box per face,
    * one row per dimension (vertices at the bottom, facets at the top),
    * a line between two faces exactly when one **covers** the other, i.e. when
      ``sigma subset tau`` and ``dim tau = dim sigma + 1``.

Lines are drawn without arrowheads: in a Hasse diagram the direction of the order
is carried by the *height*, not by an arrow. Transitive pairs (``{a}`` inside
``{a,b,c}``) are deliberately NOT drawn -- they are implied by the paths, and
drawing them would turn any interesting complex into a hairball.

Why Graphviz (and not igraph, as this file used to do)
------------------------------------------------------
``dot`` is a *layered* layout engine: it puts every node on an integer rank and
routes edges between consecutive ranks. A graded poset is exactly that shape, so
the layout we want is the layout ``dot`` computes natively -- we only have to pin
each row with ``rank=same`` and let it place things left-to-right to minimise
crossings. The old version of this file built the complex with a home-made graph
library (``tigraphs2``) and drew it with an igraph reingold-tilford *tree* layout,
which cannot show a face shared by two facets (a tree has one parent per node,
a face has many cofaces). It also ran on Python 2 and neither dependency is
installed here. The rewrite keeps the mathematics and drops both dependencies:
Graphviz is already this project's renderer (see :mod:`visualization`), so the
output matches the rest of the figures and needs no new packages.

What you can feed it
--------------------
Anything that describes a complex:

    * a list of **maximal simplices** over arbitrary hashable vertices --
      ``[[0, 1, 2], [2, 3]]``;
    * a :class:`simplicial.SimplicialBeliefModel` -- its facets are the maximal
      simplices, and the drawing then reuses the project's colours: vertices get
      their agent's colour (the chromatic colouring) and facets get the colour of
      their belief signature, the same one :func:`visualization.show` uses. So the
      Hasse diagram and the 2-D/3-D figure of the same model can be read together.
      This also fills a gap: ``visualization.to_dot`` refuses simplicial models.

The API mirrors :mod:`visualization`::

    lattice   = face_lattice([[0, 1, 2], [2, 3]])   # the poset itself
    text      = visualize(lattice)                  # dependency-free text summary
    source    = to_dot(lattice, "my complex")       # Graphviz DOT source
    path      = show(lattice, "my_complex")         # outputs/my_complex.png
    preview(model)                                  # temp file, opens it

Images need the Graphviz ``dot`` binary (``brew install graphviz``); everything
else here is pure standard library.

A caution about size: a complex with an ``n``-vertex facet has ``2**n`` faces, so
the diagram grows exponentially with the dimension. Past a few hundred faces the
picture stops being readable -- use ``max_dimension=`` to draw only the low-
dimensional part (the skeleton), which is usually the part you were checking, and
``rankdir="LR"`` when a middle row gets too wide for the default upward layout.

Run ``python hasse.py`` for a demo; add ``--open`` to open the figures.
"""

from __future__ import annotations

import itertools
import tempfile
import warnings
from typing import Any, Dict, FrozenSet, Iterable, List, Tuple

# Reuse the project's renderer plumbing and palettes so every figure in the repo
# looks the same and there is exactly one place that knows how to invoke `dot`.
from visualization import (
    OUTPUT_DIR,
    PALETTE,
    _belief_signature,
    _dot_escape,
    _html_escape,
    _open_file,
    _signature_colors,
    _write_and_run_dot,
)

__all__ = [
    "FaceLattice",
    "face_lattice",
    "from_simplicial_model",
    "visualize",
    "to_dot",
    "show",
    "preview",
]

# A vertex is anything hashable (an int, a string, a simplicial Node...);
# a face is the frozenset of its vertices, so faces are hashable and comparable
# with the set operators (<=, <, &) that the order relation is made of.
Vertex = Any
Face = FrozenSet[Vertex]

EMPTY_FACE: Face = frozenset()

# Neutral node style; the model-aware builder overrides these per face.
FILL_DEFAULT = "#f4f6f8"
LINE_DEFAULT = "#555555"
# Beyond this many faces the diagram is too dense to read, so we warn once.
CROWDED = 300


# --------------------------------------------------------------------------- #
# Ordering helpers -- everything is sorted so the generated DOT is deterministic
# (same input -> byte-identical file, which keeps diffs of outputs/ meaningful).
# --------------------------------------------------------------------------- #
def _vertex_label(vertex: Vertex) -> str:
    """Readable name for a vertex.

    Simplicial ``Node``s (agent + knowledge class) are duck-typed so this module
    never has to import :mod:`simplicial`; anything else falls back to ``str``.
    """
    if hasattr(vertex, "agent") and hasattr(vertex, "cls"):
        members = ",".join(sorted(map(str, vertex.cls)))
        return f"{vertex.agent}:{{{members}}}"
    return str(vertex)


def _face_sort_key(face: Face) -> Tuple[int, Tuple[str, ...]]:
    """Sort faces by dimension first, then alphabetically by their vertex names."""
    return (len(face), tuple(sorted(_vertex_label(v) for v in face)))


def _sorted_vertices(face: Face) -> List[Vertex]:
    return sorted(face, key=_vertex_label)


# --------------------------------------------------------------------------- #
# The face lattice
# --------------------------------------------------------------------------- #
class FaceLattice:
    """All faces of a finite abstract simplicial complex, ordered by inclusion.

    A complex is given by its **maximal simplices** (facets); every subset of a
    facet is also a face -- that downward-closure is the definition of a simplicial
    complex, and :meth:`_downward_closure` is literally that definition executed.

    Attributes:
        maximal_simplices: the facets, with any redundant (non-maximal) entry of the
            input dropped, so ``is_facet`` means what it says.
        faces: every face, including the empty face when ``include_empty``.
        include_empty: whether the empty face (dimension -1, the bottom of the
            lattice) is part of the poset. It is what makes the poset a *lattice*
            (a unique minimum) and it is where the reduced Euler characteristic
            comes from, but it carries no geometry, so it can be switched off.
        labels / fills / outlines / tooltips: optional per-face styling filled in
            by :func:`from_simplicial_model`; empty for a plain combinatorial
            complex. ``tooltips`` keeps the long form of a label for SVG hover.
        legend_cells: HTML ``<TD>`` strips appended to the drawing's legend.
    """

    def __init__(self, maximal_simplices: Iterable[Iterable[Vertex]], *,
                 include_empty: bool = True) -> None:
        given = {frozenset(s) for s in maximal_simplices}
        if not given:
            raise ValueError("A simplicial complex needs at least one maximal simplex.")
        # "Maximal" must be true of what we store: drop any simplex strictly
        # contained in another, so [[0,1,2],[0,1]] and [[0,1,2]] build the same object.
        self.maximal_simplices: FrozenSet[Face] = frozenset(
            m for m in given if not any(m < other for other in given)
        )
        self.include_empty = include_empty
        self.faces: FrozenSet[Face] = self._downward_closure()

        # Optional presentation data (see from_simplicial_model).
        self.labels: Dict[Face, str] = {}
        self.fills: Dict[Face, str] = {}
        self.outlines: Dict[Face, str] = {}
        self.tooltips: Dict[Face, str] = {}
        self.legend_cells: List[str] = []

    # -- construction -------------------------------------------------------- #
    def _downward_closure(self) -> FrozenSet[Face]:
        """Every subset of every facet: the faces of the complex.

        Enumerating subsets is what makes this exponential (``2**|facet|`` per
        facet), and it is unavoidable -- the lattice really does have that many
        elements. Facets overlap, so the set deduplicates shared faces for free:
        a face shared by two facets is stored once and will be drawn once, with a
        line up to *both* cofaces. (That sharing is precisely what the old
        tree-based drawing could not express.)
        """
        faces: set[Face] = set()
        for facet in self.maximal_simplices:
            vertices = _sorted_vertices(facet)
            start = 0 if self.include_empty else 1
            for size in range(start, len(vertices) + 1):
                for combo in itertools.combinations(vertices, size):
                    faces.add(frozenset(combo))
        return frozenset(faces)

    # -- basic invariants ---------------------------------------------------- #
    @property
    def vertices(self) -> FrozenSet[Vertex]:
        """The 0-faces, i.e. the vertex set of the complex."""
        return frozenset(itertools.chain.from_iterable(self.maximal_simplices))

    @property
    def dimension(self) -> int:
        """Dimension of the complex: the largest ``|facet| - 1``."""
        return max(len(m) for m in self.maximal_simplices) - 1

    def is_facet(self, face: Face) -> bool:
        """True if ``face`` is maximal (no other face of the complex contains it)."""
        return face in self.maximal_simplices

    def f_vector(self) -> Tuple[int, ...]:
        """``(f_0, f_1, ...)``: how many faces of each dimension from 0 up.

        The classical invariant of a complex: ``f_0`` vertices, ``f_1`` edges,
        ``f_2`` triangles... A quick sanity check on a translation -- for a
        simplicial belief model, ``f_0`` must be the number of distinct agent
        perspectives and the top entry the number of worlds.
        """
        counts = [0] * (self.dimension + 1)
        for face in self.faces:
            if face:
                counts[len(face) - 1] += 1
        return tuple(counts)

    def euler_characteristic(self) -> int:
        """``f_0 - f_1 + f_2 - ...`` -- the alternating sum of the f-vector."""
        return sum((-1) ** k * n for k, n in enumerate(self.f_vector()))

    # -- the order relation -------------------------------------------------- #
    def by_dimension(self) -> Dict[int, List[Face]]:
        """``dimension -> faces of that dimension``, each row sorted.

        These are the ranks of the graded poset, and they become the rows
        (``rank=same``) of the drawing.
        """
        rows: Dict[int, List[Face]] = {}
        for face in self.faces:
            rows.setdefault(len(face) - 1, []).append(face)
        return {d: sorted(rows[d], key=_face_sort_key) for d in sorted(rows)}

    def covers(self) -> List[Tuple[Face, Face]]:
        """The covering pairs ``(sigma, tau)``: ``sigma subset tau``, one dimension apart.

        These are the only lines a Hasse diagram draws. Computing them is cheap
        here, no pairwise comparison needed: because the complex is downward
        closed, the faces covered by ``tau`` are exactly ``tau`` minus one vertex,
        so each face of size ``k`` contributes at most ``k`` lines. That is
        ``O(#faces * dim)`` instead of ``O(#faces**2)``.
        """
        pairs: List[Tuple[Face, Face]] = []
        for tau in sorted(self.faces, key=_face_sort_key):
            for v in _sorted_vertices(tau):
                sigma = tau - {v}
                if sigma in self.faces:  # false only for the excluded empty face
                    pairs.append((sigma, tau))
        return pairs

    # -- display ------------------------------------------------------------- #
    def label(self, face: Face) -> str:
        """The text drawn in a face's box (a supplied label, or a default one)."""
        if face in self.labels:
            return self.labels[face]
        if not face:
            return "∅"  # the empty face
        return "{" + ",".join(_vertex_label(v) for v in _sorted_vertices(face)) + "}"

    def describe(self) -> str:
        """A dependency-free text rendering of the lattice, one row per dimension."""
        lines = [
            f"FaceLattice: {len(self.vertices)} vertices, {len(self.faces)} faces, "
            f"dimension {self.dimension}",
            f"  f-vector = {self.f_vector()}, Euler characteristic = "
            f"{self.euler_characteristic()}",
        ]
        for dim, row in sorted(self.by_dimension().items(), reverse=True):
            rendered = ", ".join(
                self.label(f).replace("\n", " ") + (" *" if self.is_facet(f) else "")
                for f in row
            )
            lines.append(f"  dim {dim:>2} ({len(row):>3}): {rendered}")
        lines.append("  (* = maximal simplex / facet)")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"FaceLattice(facets={len(self.maximal_simplices)}, "
            f"faces={len(self.faces)}, dim={self.dimension})"
        )


# --------------------------------------------------------------------------- #
# Building a lattice from any accepted input
# --------------------------------------------------------------------------- #
def face_lattice(complex_like, *, include_empty: bool = True,
                 compact: bool = True) -> FaceLattice:
    """Coerce anything that describes a complex into a :class:`FaceLattice`.

    Accepts a :class:`FaceLattice` (returned unchanged), a
    :class:`simplicial.SimplicialBeliefModel` (recognised by duck typing, so this
    module keeps no import of the model layer), or an iterable of maximal
    simplices.
    """
    if isinstance(complex_like, FaceLattice):
        return complex_like
    if hasattr(complex_like, "facets") and hasattr(complex_like, "agents"):
        return from_simplicial_model(
            complex_like, include_empty=include_empty, compact=compact
        )
    return FaceLattice(complex_like, include_empty=include_empty)


def from_simplicial_model(model, *, include_empty: bool = True,
                          compact: bool = True) -> FaceLattice:
    """Build the face lattice of a :class:`simplicial.SimplicialBeliefModel`.

    The facets of the model *are* the maximal simplices, so the lattice itself is
    just ``FaceLattice(model.facets)``. What this function adds is the reading:

        * a **vertex** ``{node}`` is one agent's perspective; it is filled in that
          agent's palette colour -- the chromatic colouring of the complex, the same
          colours :func:`visualization.show` uses for the same model;
        * a **facet** is a possible world; it is filled with the colour of its
          *belief signature* (which agents' belief subcomplexes contain it), again
          the colouring of Figure 3, and its label carries the world name;
        * everything in between is a shared face -- and the lines running up out of
          it show exactly which worlds are indistinguishable to that group of
          agents. That is the fact the Hasse diagram makes visible and the geometric
          picture does not.

    Args:
        include_empty: keep the empty face at the bottom of the lattice.
        compact: label each perspective ``a0, a1, ...`` (agent + an index over that
            agent's own knowledge classes) instead of printing the whole class. A
            proper model's classes are sets of duplicated worlds, so the full labels
            are unreadable in a box; the full text is kept as the node's Graphviz
            **tooltip**, which SVG output shows on hover. Pass ``compact=False`` to
            print the classes in the boxes.
    """
    agents = sorted(model.agents, key=str)
    agent_color = {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(agents)}
    sig_color = _signature_colors(model, agents)  # belief signature -> colour

    lattice = FaceLattice(model.facets, include_empty=include_empty)

    # Short name per node: "a0", "a1", ... numbering each agent's own knowledge
    # classes in a stable (sorted) order, so the same model always yields the same
    # names. Without this, one box would carry the agent's whole equivalence class.
    short: Dict[Any, str] = {}
    for a in agents:
        classes = sorted((n for n in lattice.vertices if n.agent == a), key=_vertex_label)
        for i, node in enumerate(classes):
            short[node] = f"{a}{i}"

    def node_name(node) -> str:
        return short[node] if compact else _vertex_label(node)

    for face in lattice.faces:
        if not face:
            continue
        nodes = sorted(face, key=lambda n: str(n.agent))
        rows = [node_name(n) for n in nodes]
        # The full perspectives always stay reachable as a hover tooltip (SVG).
        lattice.tooltips[face] = "; ".join(_vertex_label(n) for n in nodes)
        if lattice.is_facet(face):
            world = model.world_of_facet.get(face)
            if world is not None:
                # A facet IS a world, so name it by the world and keep the
                # perspectives on a second, smaller line.
                rows = [str(world), " ".join(node_name(n) for n in nodes)]
            colour = sig_color[_belief_signature(model, face, agents)]
            # "55"/"33" are Graphviz's 8-digit RGBA: a translucent wash keeps the
            # label readable while still reading as the Figure-3 colour.
            lattice.fills[face] = colour + "55"
            lattice.outlines[face] = colour
        elif len(face) == 1:
            colour = agent_color[nodes[0].agent]
            lattice.fills[face] = colour + "33"
            lattice.outlines[face] = colour
        lattice.labels[face] = "\n".join(rows)

    lattice.legend_cells = [
        _swatch_cell(agent_color[a], f"agent {a}", round_dot=True) for a in agents
    ] + [
        _swatch_cell(colour, "belief: " + ("+".join(map(str, sig)) if sig else "none"))
        for sig, colour in sorted(sig_color.items(), key=lambda kv: (len(kv[0]), kv[0]))
    ]
    return lattice


# --------------------------------------------------------------------------- #
# DOT generation
# --------------------------------------------------------------------------- #
def _dot_label(text: str) -> str:
    """Escape a label for a quoted DOT string, turning newlines into DOT's ``\\n``."""
    return _dot_escape(text).replace("\n", "\\n")


def _swatch_cell(color: str, text: str, *, round_dot: bool = False) -> str:
    """One legend cell: a coloured mark followed by its meaning."""
    mark = "&#9679;" if round_dot else "&#9632;"  # filled circle / filled square
    return (
        f'<TD><FONT COLOR="{color}" POINT-SIZE="15">{mark}</FONT>'
        f' <FONT POINT-SIZE="11">{_html_escape(text)}</FONT></TD>'
    )


def visualize(complex_like) -> str:
    """Return a dependency-free text rendering of a complex's face lattice."""
    return face_lattice(complex_like).describe()


def to_dot(
    complex_like,
    title: str | None = None,
    *,
    include_empty: bool | None = None,
    max_dimension: int | None = None,
    rankdir: str = "BT",
    dimension_axis: bool = True,
    legend: bool = True,
) -> str:
    """Return Graphviz DOT source for the Hasse diagram of a complex.

    Use this to export or hand-tweak the source without the ``dot`` binary;
    :func:`show` calls it for you.

    Args:
        title: Caption above the diagram (defaults to a short description).
        include_empty: Draw the empty face at the bottom. ``None`` keeps whatever
            the lattice was built with.
        max_dimension: Draw only faces up to this dimension -- the ``k``-skeleton.
            The escape hatch for complexes whose full lattice is too big to read.
        rankdir: ``"BT"`` (default) grows the dimension upwards, the textbook
            Hasse layout -- but a lattice with a wide middle row then comes out
            as a very flat strip. ``"LR"`` puts the dimensions in columns instead,
            which turns that same wide row into a tall one: usually easier to read
            on a screen once there are more than ~15 faces in a row.
        dimension_axis: Draw the "dim k" column on the left labelling each row.
        legend: Draw the colour legend (only present for simplicial models).
    """
    lattice = face_lattice(complex_like)

    # Which faces to draw. Filtering happens here, not in the lattice, so the same
    # lattice object can be drawn at several depths without being rebuilt.
    def keep(face: Face) -> bool:
        if not face and include_empty is False:
            return False
        if max_dimension is not None and len(face) - 1 > max_dimension:
            return False
        return True

    faces = sorted((f for f in lattice.faces if keep(f)), key=_face_sort_key)
    if not faces:
        raise ValueError("Nothing to draw: every face was filtered out.")
    if len(faces) > CROWDED:
        warnings.warn(
            f"{len(faces)} faces: the Hasse diagram will be very dense. Consider "
            f"max_dimension=2 to draw only the 2-skeleton.",
            stacklevel=2,
        )

    # Stable, DOT-safe node ids. Face labels can contain anything, so we never use
    # them as identifiers -- an index is both safe and deterministic.
    ids = {face: f"n{i}" for i, face in enumerate(faces)}
    rows: Dict[int, List[Face]] = {}
    for face in faces:
        rows.setdefault(len(face) - 1, []).append(face)

    caption = title if title is not None else (
        f"Hasse diagram - {len(lattice.vertices)} vertices, "
        f"{len(lattice.maximal_simplices)} facets, dim {lattice.dimension}"
    )

    lines = [
        "digraph FaceLattice {",
        # rankdir=BT puts rank 0 at the bottom, so dimension grows upward: the
        # conventional reading of a Hasse diagram (bigger = higher). LR lays the
        # same ranks out as columns for lattices that are too wide to read flat.
        f"    rankdir={rankdir};",
        '    fontname="Helvetica"; nodesep=0.30; ranksep=0.55; splines=true;',
        f'    label="{_dot_escape(caption)}"; labelloc="t"; fontsize=13;',
        '    node [shape=box, style="rounded,filled", fontname="Helvetica",'
        f' fontsize=10, margin="0.09,0.05", fillcolor="{FILL_DEFAULT}",'
        f' color="{LINE_DEFAULT}", penwidth=1.1];',
        # dir=none: in a Hasse diagram the order is read off the height, so an
        # arrowhead would be redundant clutter. The edges are still *directed* for
        # the layout engine -- that is what pins each face above its own faces.
        '    edge [dir=none, color="#8a8a8a", penwidth=1.0];',
        "",
        "    // Faces: one box each, thicker outline for the maximal ones (facets).",
    ]

    for face in faces:
        attrs = [f'label="{_dot_label(lattice.label(face))}"']
        if face in lattice.fills:
            attrs.append(f'fillcolor="{lattice.fills[face]}"')
        if face in lattice.outlines:
            attrs.append(f'color="{lattice.outlines[face]}"')
        if face in lattice.tooltips:
            attrs.append(f'tooltip="{_dot_label(lattice.tooltips[face])}"')
        if lattice.is_facet(face):
            attrs.append("penwidth=2.2")
        if not face:
            # the empty face: a small anchor at the bottom, no text box
            attrs += ["shape=circle", "width=0.32", "fixedsize=true"]
        lines.append(f"    {ids[face]} [{', '.join(attrs)}];")

    lines += ["", "    // Covering relations: sigma -- tau with dim tau = dim sigma + 1."]
    for sigma, tau in lattice.covers():
        if sigma in ids and tau in ids:
            lines.append(f"    {ids[sigma]} -> {ids[tau]};")

    # One rank per dimension. dot would already rank the faces correctly (all
    # covering edges go up exactly one step), but saying it explicitly guarantees
    # the rows even when a dimension is filtered out or a face is isolated.
    lines += ["", "    // One row per dimension."]
    axis_ids: List[str] = []
    for dim in sorted(rows):
        members = " ".join(ids[f] + ";" for f in rows[dim])
        if dimension_axis:
            axis = f'"dim{dim}"'
            axis_ids.append(axis)
            lines.append(
                f'    {axis} [shape=plaintext, style="", label="dim {dim}",'
                ' fontcolor="#888888", fontsize=10];'
            )
            members = f"{axis}; " + members
        lines.append(f"    {{ rank=same; {members} }}")

    if dimension_axis and len(axis_ids) > 1:
        # Invisible chain keeps the "dim k" labels lined up in a single column
        # (row for rankdir=LR) instead of floating into an arbitrary spot.
        lines.append("    " + " -> ".join(axis_ids) + " [style=invis];")

    if legend and lattice.legend_cells:
        lines += [
            "",
            "    // Legend, pinned to the lowest rank (the bottom of the drawing).",
            "    legend [shape=none, margin=0, style=\"\", label=<",
            '      <TABLE BORDER="0" CELLBORDER="0" CELLSPACING="12" CELLPADDING="0"><TR>',
            *("        " + cell for cell in lattice.legend_cells),
            "      </TR></TABLE>",
            "    >];",
            "    { rank=min; legend; }",
        ]

    lines.append("}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def show(
    complex_like,
    name: str = "hasse",
    title: str | None = None,
    *,
    open: bool = False,
    output_dir: str = OUTPUT_DIR,
    image_format: str = "png",
    include_empty: bool | None = None,
    max_dimension: int | None = None,
    rankdir: str = "BT",
    dimension_axis: bool = True,
    legend: bool = True,
) -> str:
    """Draw the Hasse diagram to ``<output_dir>/<name>.<image_format>`` and return the path.

    Writes the DOT source next to the image (``<name>.dot``) and runs Graphviz on
    it, exactly like :func:`visualization.show`, so the two renderers leave the same
    kind of artefacts in ``outputs/``.

    Raises:
        RuntimeError: If the Graphviz ``dot`` binary is not on ``PATH``. Use
            :func:`to_dot` to export the source instead.
    """
    source = to_dot(
        complex_like,
        title if title is not None else name,
        include_empty=include_empty,
        max_dimension=max_dimension,
        rankdir=rankdir,
        dimension_axis=dimension_axis,
        legend=legend,
    )
    path = _write_and_run_dot(source, name, image_format, output_dir)
    if open:
        _open_file(path)
    return path


def preview(complex_like, title: str | None = None, **kwargs) -> str:
    """Render the Hasse diagram to a temporary file and open it. Zero-config look."""
    return show(
        complex_like,
        name="preview_hasse",
        title=title,
        open=True,
        output_dir=tempfile.gettempdir(),
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Demo: python hasse.py [--open]
# --------------------------------------------------------------------------- #
def _demo() -> None:
    import sys

    opened = "--open" in sys.argv

    def banner(text: str) -> None:
        print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")

    # 1. The full 3-simplex (a solid tetrahedron): one facet, 2**4 = 16 faces.
    #    Its lattice is the Boolean lattice on 4 elements -- the reference picture.
    banner("Solid tetrahedron: maximal simplices [[0,1,2,3]]")
    solid = face_lattice([[0, 1, 2, 3]])
    print(visualize(solid))
    print("->", show(solid, "hasse_tetrahedron", "Solid tetrahedron (the 3-simplex)",
                     open=opened))

    # 2. The same vertices, but only the four triangles: a HOLLOW tetrahedron (the
    #    boundary 2-sphere). Same 1-skeleton as above, and the lattice shows the
    #    difference at a glance -- the top row is missing, Euler characteristic
    #    goes 1 -> 2. This is why the combinatorial picture is worth drawing:
    #    the geometric one looks nearly identical.
    banner("Hollow tetrahedron: the four triangles only")
    hollow = face_lattice([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]])
    print(visualize(hollow))
    print("->", show(hollow, "hasse_tetrahedron_hollow",
                     "Hollow tetrahedron (boundary of the 3-simplex)", open=opened))

    # 3. A real simplicial belief model: the thesis Figure-3 complex, coloured by
    #    agent and by belief subcomplex.
    banner("Thesis Figure 3: simplicial belief model")
    from knowledge_belief import KnowledgeBeliefFrame
    from simplicial import to_simplicial

    worlds = {"w0", "w1", "w2"}
    agents = {"a", "b", "c"}
    complete = {(x, y) for x in worlds for y in worlds}
    kb = KnowledgeBeliefFrame(
        agents,
        worlds,
        knowledge={a: set(complete) for a in agents},
        belief={
            "a": {(w, "w1") for w in worlds} | {(w, "w2") for w in worlds},
            "b": {(w, "w1") for w in worlds},
            "c": {(w, "w2") for w in worlds},
        },
    )
    model = to_simplicial(kb.to_proper())
    lattice = face_lattice(model, include_empty=False)
    print(visualize(lattice))
    # 39 faces with 21 of them on the middle row: flat as "BT", so lay the
    # dimensions out in columns instead.
    print("->", show(lattice, "hasse_thesis_fig3",
                     "Fig.3 - face lattice of the simplicial belief model",
                     rankdir="LR", open=opened))


if __name__ == "__main__":
    _demo()

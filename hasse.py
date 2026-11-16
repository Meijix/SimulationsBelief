# -*- coding: utf-8 -*-
"""Hasse diagrams (face lattices) of simplicial complexes, drawn with Graphviz.

The combinatorial picture of a complex, to read next to the geometric one of
:mod:`visualization`: one box per face, one row per dimension, a line where one
face covers another (``dot``'s layered layout is exactly this shape). For a
:class:`simplicial.SimplicialBeliefModel` vertices take their agent's colour
and facets the colour of their belief signature, as in the other figures.
Theory and reading guide: docs/06.

    lattice = face_lattice([[0, 1, 2], [2, 3]])   # or a SimplicialBeliefModel
    visualize(lattice)                            # text: rows, f-vector, Euler characteristic
    to_dot(lattice, "title")                      # DOT source
    show(lattice, "name")                         # outputs/name.png
    preview(model)                                # temp file, opened

A facet with ``n`` vertices has ``2**n`` faces; ``facets_and_vertices=True``
(perspectives and worlds only) and ``max_dimension=`` keep big diagrams readable.
Isolated vertices are 0-dimensional maximal simplices on the vertex row.
``python hasse.py [--open]`` runs a demo.
"""

from __future__ import annotations

import itertools
import tempfile
import warnings
from typing import Any, Dict, FrozenSet, Iterable, List, Tuple

from visualization import (
    OUTPUT_DIR,
    PALETTE,
    _belief_signature,
    _dot_escape,
    _dot_footer,
    _html_escape,
    _open_file,
    _signature_colors,
    _swatch_cell,
    _write_and_run_dot,
    ink,
    node_literals,
    signature_label,
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

# A vertex is anything hashable; a face is the frozenset of its vertices.
Vertex = Any
Face = FrozenSet[Vertex]

EMPTY_FACE: Face = frozenset()
CROWDED = 300   # faces; beyond this the diagram is too dense and a warning is issued


# Everything is sorted so the generated DOT is deterministic.
def _vertex_label(vertex: Vertex) -> str:
    """Readable name for a vertex (``a:{w0,w1}`` for a simplicial Node, duck-typed)."""
    if hasattr(vertex, "agent") and hasattr(vertex, "cls"):
        members = ",".join(sorted(map(str, vertex.cls)))
        return f"{vertex.agent}:{{{members}}}"
    return str(vertex)


def _face_literals(assignment, face: Face) -> List[str]:
    """The union of the literals its vertices observe: climbing the lattice
    accumulates information, and at a facet this is the lifted atomic truth.
    An inconsistent facet shows both ``P`` and ``¬P``, on purpose."""
    literals: set[str] = set()
    for vertex in face:
        literals.update(node_literals(assignment, vertex))
    return sorted(literals)


def _face_sort_key(face: Face) -> Tuple[int, Tuple[str, ...]]:
    """Sort faces by dimension first, then alphabetically by their vertex names."""
    return (len(face), tuple(sorted(_vertex_label(v) for v in face)))


def _sorted_vertices(face: Face) -> List[Vertex]:
    return sorted(face, key=_vertex_label)


# --------------------------------------------------------------------------- #
# The face lattice
# --------------------------------------------------------------------------- #
class FaceLattice:
    """All faces of a finite simplicial complex, ordered by inclusion.

    Attributes:
        maximal_simplices: the facets (non-maximal input entries are dropped).
        faces: every face, the empty one included when ``include_empty``.
        labels / fills / outlines / tooltips / legend_cells: optional per-face
            styling filled in by :func:`from_simplicial_model`.
    """

    def __init__(self, maximal_simplices: Iterable[Iterable[Vertex]], *,
                 include_empty: bool = True) -> None:
        given = {frozenset(s) for s in maximal_simplices}
        if not given:
            raise ValueError("A simplicial complex needs at least one maximal simplex.")
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
        """Every subset of every facet (``2**|facet|`` each; shared faces stored once)."""
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
        """``(f_0, f_1, ...)``: faces per dimension from 0 up (for a belief model,
        ``f_0`` = perspectives and the top entry = worlds)."""
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
        """``dimension -> faces of that dimension``, each row sorted (the drawing's rows)."""
        rows: Dict[int, List[Face]] = {}
        for face in self.faces:
            rows.setdefault(len(face) - 1, []).append(face)
        return {d: sorted(rows[d], key=_face_sort_key) for d in sorted(rows)}

    def covers(self) -> List[Tuple[Face, Face]]:
        """The covering pairs ``(sigma, tau)``, ``sigma = tau`` minus one vertex:
        the lines of the diagram, in ``O(#faces * dim)``."""
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
                 compact: bool = True, assignment=None) -> FaceLattice:
    """A :class:`FaceLattice` from a lattice (returned as is), a
    :class:`simplicial.SimplicialBeliefModel` (duck-typed; ``assignment`` applies
    here) or an iterable of maximal simplices."""
    if isinstance(complex_like, FaceLattice):
        return complex_like
    if hasattr(complex_like, "facets") and hasattr(complex_like, "agents"):
        return from_simplicial_model(
            complex_like, include_empty=include_empty, compact=compact,
            assignment=assignment,
        )
    return FaceLattice(complex_like, include_empty=include_empty)


def from_simplicial_model(model, *, include_empty: bool = True,
                          compact: bool = True, assignment=None) -> FaceLattice:
    """The face lattice of a :class:`simplicial.SimplicialBeliefModel`, styled:
    vertices in their agent's colour, facets in their belief signature's colour
    and named by their world, the faces in between showing which worlds a group
    of agents cannot tell apart.

    Args:
        include_empty: keep the empty face at the bottom.
        compact: label perspectives ``a0, a1, ...`` (the full class stays in the
            SVG tooltip) instead of printing the whole class.
        assignment: vertex valuation; every face then shows the literals its
            perspectives jointly observe (:func:`_face_literals`).
    """
    agents = sorted(model.agents, key=str)
    agent_color = {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(agents)}
    sig_color = _signature_colors(model, agents)

    # A node in no facet is a 0-dimensional maximal simplex, kept on the vertex row.
    in_some_facet = {n for F in model.facets for n in F}
    loose = frozenset(n for n in getattr(model, "nodes", ()) if n not in in_some_facet)
    maximal = set(model.facets) | {frozenset({n}) for n in loose}
    lattice = FaceLattice(maximal, include_empty=include_empty)

    short: Dict[Any, str] = {}   # "a0", "a1", ... per agent, in a stable order
    for a in agents:
        classes = sorted((n for n in lattice.vertices if n.agent == a), key=_vertex_label)
        for i, node in enumerate(classes):
            short[node] = f"{a}{i}"
    given = getattr(model, "node_names", None) or {}   # a complex defined directly

    def node_name(node) -> str:
        if node in given:
            return str(given[node])
        return short[node] if compact else _vertex_label(node)

    for face in lattice.faces:
        if not face:
            continue
        nodes = sorted(face, key=lambda n: str(n.agent))
        rows = [node_name(n) for n in nodes]
        lattice.tooltips[face] = "; ".join(_vertex_label(n) for n in nodes)
        if face in model.facets:
            world = model.world_of_facet.get(face)
            if world is not None:
                rows = [str(world), " ".join(node_name(n) for n in nodes)]
            colour = sig_color[_belief_signature(model, face, agents)]
            lattice.fills[face] = colour + "55"   # #RRGGBBAA: a translucent wash
            lattice.outlines[face] = colour
        elif len(face) == 1:
            colour = agent_color[nodes[0].agent]
            lattice.fills[face] = colour + "33"
            lattice.outlines[face] = colour
            if nodes[0] in loose:
                rows.append("(isolated)")
                lattice.tooltips[face] += " | in no facet"
        if assignment is not None:
            literals = _face_literals(assignment, face)
            if literals:
                rows.append("(" + ", ".join(literals) + ")")
                lattice.tooltips[face] += " | " + ", ".join(literals)
        lattice.labels[face] = "\n".join(rows)

    lattice.legend_cells = [
        _swatch_cell(agent_color[a], f"agent {a}", round_dot=True) for a in agents
    ] + [
        _swatch_cell(colour, signature_label(model, sig, agents))
        for sig, colour in sorted(sig_color.items(), key=lambda kv: (len(kv[0]), kv[0]))
    ]
    return lattice


# --------------------------------------------------------------------------- #
# DOT generation
# --------------------------------------------------------------------------- #
def _dot_label(text: str) -> str:
    """Escape a label for a quoted DOT string, turning newlines into DOT's ``\\n``."""
    return _dot_escape(text).replace("\n", "\\n")


def visualize(complex_like) -> str:
    """Return a dependency-free text rendering of a complex's face lattice."""
    return face_lattice(complex_like).describe()


def to_dot(
    complex_like,
    title: str | None = None,
    *,
    include_empty: bool | None = None,
    max_dimension: int | None = None,
    facets_and_vertices: bool = False,
    rankdir: str = "BT",
    dimension_axis: bool = True,
    legend: bool = True,
    assignment=None,
) -> str:
    """Graphviz DOT source for the Hasse diagram of a complex.

    Args:
        title: caption (default: a short description).
        assignment: vertex valuation to display (simplicial models only).
        include_empty: draw the empty face; ``None`` follows the lattice.
        max_dimension: draw only the ``k``-skeleton.
        facets_and_vertices: only the vertices and the facets, joined by the
            incidence "vertex lies in facet" (a bipartite diagram, no middle rows;
            the empty face only on explicit request).
        rankdir: ``"BT"`` grows the dimension upwards; ``"LR"`` lays the
            dimensions out as columns, better for a wide middle row.
        dimension_axis: label each row with ``dim k``.
        legend: draw the colour legend (simplicial models only).
    """
    lattice = face_lattice(complex_like, assignment=assignment)

    def keep(face: Face) -> bool:
        if not face:
            return include_empty is True if facets_and_vertices else include_empty is not False
        if max_dimension is not None and len(face) - 1 > max_dimension:
            return False
        if facets_and_vertices and len(face) != 1 and not lattice.is_facet(face):
            return False
        return True

    faces = sorted((f for f in lattice.faces if keep(f)), key=_face_sort_key)
    if not faces:
        raise ValueError("Nothing to draw: every face was filtered out.")
    if len(faces) > CROWDED:
        warnings.warn(
            f"{len(faces)} faces: the Hasse diagram will be very dense. Consider "
            f"facets_and_vertices=True (perspectives and worlds only) or "
            f"max_dimension=2 to draw only the 2-skeleton.",
            stacklevel=2,
        )

    ids = {face: f"n{i}" for i, face in enumerate(faces)}   # DOT-safe, deterministic ids
    rows: Dict[int, List[Face]] = {}
    for face in faces:
        rows.setdefault(len(face) - 1, []).append(face)

    caption = title if title is not None else (
        f"Hasse diagram - {len(lattice.vertices)} vertices, "
        f"{len(lattice.maximal_simplices)} facets, dim {lattice.dimension}"
    )

    lines = [
        "digraph FaceLattice {",
        f"    rankdir={rankdir};",
        f'    fontname="Helvetica"; fontcolor="{ink()["text"]}"; nodesep=0.30; ranksep=0.55; splines=true;',
        '    node [shape=box, style="rounded,filled", fontname="Helvetica",'
        f' fontsize=10, margin="0.09,0.05", fillcolor="{ink()["node_fill"]}",'
        f' color="{ink()["node_edge"]}", fontcolor="{ink()["text"]}", penwidth=1.1];',
        # dir=none: the order is read off the height; the edges still direct the layout.
        f'    edge [dir=none, color="{ink()["faint"]}", penwidth=1.0];',
    ]

    # Axis labels first: dot orders a rank by first appearance, so the axis sits at the edge.
    axis_ids: List[str] = []
    if dimension_axis:
        lines += ["", "    // Dimension axis, one label per row."]
        for dim in sorted(rows):
            axis = f'"dim{dim}"'
            axis_ids.append(axis)
            lines.append(
                f'    {axis} [shape=plaintext, style="", label="dim {dim}",'
                f' fontcolor="{ink()["muted"]}", fontsize=10];'
            )
        if len(axis_ids) > 1:
            lines.append("    " + " -> ".join(axis_ids) + " [style=invis];")   # keeps them aligned

    lines += ["", "    // Faces: one box each, thicker outline for the maximal ones (facets)."]

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
            attrs += ["shape=circle", "width=0.32", "fixedsize=true"]   # the empty face: a small anchor
        lines.append(f"    {ids[face]} [{', '.join(attrs)}];")

    if facets_and_vertices:
        lines += ["", "    // Incidences: vertex -- facet containing it."]
        for tau in faces:
            if len(tau) > 1 and lattice.is_facet(tau):
                for v in _sorted_vertices(tau):
                    sigma = frozenset({v})
                    if sigma in ids:
                        lines.append(f"    {ids[sigma]} -> {ids[tau]};")
    else:
        lines += ["", "    // Covering relations: sigma -- tau with dim tau = dim sigma + 1."]
        for sigma, tau in lattice.covers():
            if sigma in ids and tau in ids:
                lines.append(f"    {ids[sigma]} -> {ids[tau]};")

    # One rank per dimension, explicit so rows survive filtering and isolated faces.
    lines += ["", "    // One row per dimension."]
    for dim in sorted(rows):
        members = " ".join(ids[f] + ";" for f in rows[dim])
        if dimension_axis:
            members = f'"dim{dim}"; ' + members
        lines.append(f"    {{ rank=same; {members} }}")

    legend_cells = list(lattice.legend_cells) if legend else []
    if legend and facets_and_vertices:
        legend_cells.append(
            f'<TD><FONT COLOR="{ink()["text_soft"]}" POINT-SIZE="11">vertices and facets only; '
            "a line = vertex lies in facet</FONT></TD>"
        )
    lines += [""] + _dot_footer(caption, legend_cells)
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
    facets_and_vertices: bool = False,
    rankdir: str = "BT",
    dimension_axis: bool = True,
    legend: bool = True,
    assignment=None,
    transparent: bool = False,
) -> str:
    """Draw the Hasse diagram to ``<output_dir>/<name>.<image_format>`` (the DOT
    source beside it) and return the path. Options are those of :func:`to_dot`.

    Raises:
        RuntimeError: if the Graphviz ``dot`` binary is not on ``PATH``.
    """
    source = to_dot(
        complex_like,
        title if title is not None else name,
        include_empty=include_empty,
        max_dimension=max_dimension,
        facets_and_vertices=facets_and_vertices,
        rankdir=rankdir,
        dimension_axis=dimension_axis,
        legend=legend,
        assignment=assignment,
    )
    path = _write_and_run_dot(source, name, image_format, output_dir,
                              transparent=transparent)
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

    # 1. The solid tetrahedron: one facet, 16 faces (the Boolean lattice on 4 elements).
    banner("Solid tetrahedron: maximal simplices [[0,1,2,3]]")
    solid = face_lattice([[0, 1, 2, 3]])
    print(visualize(solid))
    print("->", show(solid, "hasse_tetrahedron", "Solid tetrahedron (the 3-simplex)",
                     open=opened))

    # 2. The hollow tetrahedron: same 1-skeleton, top row missing, Euler characteristic 1 -> 2.
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
    print("->", show(lattice, "hasse_thesis_fig3",   # a wide middle row: columns read better
                     "Fig.3 - face lattice of the simplicial belief model",
                     rankdir="LR", open=opened))


if __name__ == "__main__":
    _demo()

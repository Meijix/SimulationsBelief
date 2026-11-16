"""Shared ground of the adapters package: paths, the figure style, the editor
state shape and the report types the other modules fill in.

Imported first by every sibling, which puts the repository root on
``sys.path`` before any core module is imported (the GUI lives in its own
folder and calls the flat modules at the root).
"""
from __future__ import annotations

import contextlib
import copy
import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import hasse  # noqa: E402
from visualization import PALETTE, ink_theme, show as _show  # noqa: E402


# On screen the figures are transparent SVG drawn in the page's ink
# ("dark" or "light", see ``visualization.INK_THEMES``); what leaves the page
# is printed light on white as PNG (``print_light``). The adapters call
# ``show`` without format or ink; the view that starts a render sets them for
# its thread with ``figure_style``, so renders in different inks never mix.
FIGURE_FORMAT = "svg"
FIGURE_TRANSPARENT = True
FIGURE_INK = "dark"

_STYLE = threading.local()


@contextlib.contextmanager
def figure_style(ink: str | None = None, image_format: str | None = None,
                 transparent: bool | None = None):
    """Draw with these figure defaults inside the block, in this thread only."""
    previous = (getattr(_STYLE, "ink", None), getattr(_STYLE, "image_format", None),
                getattr(_STYLE, "transparent", None))
    _STYLE.ink, _STYLE.image_format, _STYLE.transparent = ink, image_format, transparent
    try:
        yield
    finally:
        _STYLE.ink, _STYLE.image_format, _STYLE.transparent = previous


def _style(attr: str, default):
    value = getattr(_STYLE, attr, None)
    return default if value is None else value


def styled(ink: str, fn, *args, **kwargs):
    """Run ``fn`` (a render) with its figures in ``ink``: the ``io_bound`` target."""
    with figure_style(ink=ink):
        return fn(*args, **kwargs)


def print_light(fn, *args, **kwargs):
    """Run ``fn`` printing its figures: light ink, white background, PNG."""
    with figure_style(ink="light", image_format="png", transparent=False):
        return fn(*args, **kwargs)


def _figure_kwargs(kwargs: dict) -> dict:
    kwargs.setdefault("image_format", _style("image_format", FIGURE_FORMAT))
    kwargs.setdefault("transparent", _style("transparent", FIGURE_TRANSPARENT))
    return kwargs


def show(*args, **kwargs):
    """``visualization.show`` with the GUI's figure defaults (see ``figure_style``)."""
    with ink_theme(_style("ink", FIGURE_INK)):
        return _show(*args, **_figure_kwargs(kwargs))


def hasse_show(*args, **kwargs):
    """``hasse.show`` with the same figure defaults as :func:`show`."""
    with ink_theme(_style("ink", FIGURE_INK)):
        return hasse.show(*args, **_figure_kwargs(kwargs))


def agent_color_map(agents: List[str]) -> Dict[str, str]:
    """Colour per agent, the same rule ``visualization`` uses (sorted position
    over the Okabe-Ito palette), so chips and figures agree."""
    ordered = sorted(agents, key=str)
    return {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(ordered)}


# Where the GUI writes (figures, saved workspaces): the repository root, or the
# folder the packaged executable names in SIMULATIONSBELIEF_DATA (gui/app.py).
DATA = Path(os.environ.get("SIMULATIONSBELIEF_DATA", ROOT))
OUTPUTS = DATA / "outputs"

# The model kinds the GUI exposes; ``state["kind"]`` decides which frame is
# built, which axioms are checked and how far the pipeline goes (docs/11).
KINDS = {
    "kb": "Knowledge and belief",
    "knowledge": "Knowledge only (S5)",
    "belief": "Belief only (KD45 / K45)",
    "simplicial": "Simplicial complex (direct)",
}


# Up to 4 agents a facet (a 3-simplex at most) has a faithful 2-D/3-D drawing;
# from 5 on the GUI shows the complex as an incidence diagram, a face lattice
# and text.
GEOMETRY_MAX_AGENTS = 4


def _geometric_ok(model) -> bool:
    return len(model.agents) <= GEOMETRY_MAX_AGENTS


def _dimension_note(model) -> str:
    n = len(model.agents)
    return (f"{n} agents: each facet is a {n - 1}-simplex, no faithful drawing in 3D; "
            "shown as incidence diagram (facet = point joined to its vertices), "
            "face lattice and text")


def _hasse_caption(number: str, full: bool) -> str:
    """Caption for the lattice figure: the full lattice, or only vertices and facets."""
    if full:
        return (f"{number} · face lattice of the complex (Hasse diagram): "
                "one box per simplex, one row per dimension, and a line "
                "when one is an immediate face of the other")
    return (f"{number} · vertices and facets of the complex: perspectives below, "
            "worlds above, and a line when the perspective is part of the world "
            "(intermediate faces are omitted; enable them with “full lattice”)")


def blank_state(kind: str = "kb") -> dict:
    """An empty state with every key the GUI and this API expect.

    Relational kinds use ``worlds``, ``per_agent`` (per agent, rows
    ``{"cls": [...], "bel": [...]}``) and ``atoms`` (atom -> worlds where it
    is true); the direct complex uses ``vertices``, ``facets`` and ``vatoms``
    (see ``complex.py``). The rest are switches of the editor.
    """
    return {
        "kind": kind,
        "agents": [], "worlds": [], "per_agent": {},
        "atoms": {},
        "vertices": {}, "facets": [], "vatoms": {},
        "complex_kind": "kb",              # direct complex: "kb" (S_a declared) or "knowledge" (S_a = S)
        "axiom_d": True,                   # KD45 (True) or K45 (False)
        "silent_defunct": False,           # K45: class with no belief = Q = ∅
        "explicit": False,                 # draw loops and both directions
        "hasse_full": False,               # full lattice, not only vertices+facets
        "make_3d": True,                   # write the interactive 3-D page (the heavy output)
        "font_scale": 1.0,                 # label size of the complex figures (1.0 = paper size)
    }


def state_from_example(example: dict) -> dict:
    """A complete state from an ``EXAMPLES`` entry (its own deep copy)."""
    state = blank_state(example.get("kind", "kb"))
    for key in ("agents", "worlds", "per_agent", "atoms", "vertices", "facets",
                "vatoms", "axiom_d", "complex_kind"):
        if key in example:
            state[key] = copy.deepcopy(example[key])
    return state


def _fname(base: str, tag: str) -> str:
    """File name of a figure, specific to the document ``tag``."""
    return f"{base}_{tag}" if tag else base


def _knowledge_only(state: dict) -> bool:
    """Whether a direct complex is read as pure knowledge (``S_a = S``)."""
    return state.get("complex_kind", "kb") == "knowledge"


@dataclass
class StepReport:
    """What one pipeline step did: what it completed on the user's behalf,
    what is still unspecified, what made it refuse, or why it did not apply.
    A non-empty ``failed`` stops the pipeline; earlier steps keep their figures."""

    name: str
    completed: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        """'failed', 'skipped', 'completed' (ran but filled things in) or 'ok'."""
        if self.failed:
            return "failed"
        if self.skipped:
            return "skipped"
        return "completed" if self.completed else "ok"


@dataclass
class PipelineResult:
    """Everything the page needs to display one run: paths and strings only,
    never model objects."""

    stats: List[Tuple[str, str]] = field(default_factory=list)      # (value, label)
    badges: List[Tuple[str, str]] = field(default_factory=list)     # (text, tone: ok | bad | info)
    figures: List[Tuple[str, Path]] = field(default_factory=list)   # (caption, file) in order
    html_3d: Path | None = None                                     # the interactive Plotly page
    text_diagrams: List[Tuple[str, str]] = field(default_factory=list)
    # For a direct complex: the editor state of its equivalent Kripke model
    # (G_B, docs/12), so it can be opened as a document; None without facets.
    kripke_state: dict | None = None
    steps: List[StepReport] = field(default_factory=list)

    @property
    def failed_step(self) -> StepReport | None:
        """The step that stopped the run, or None if the pipeline completed."""
        return next((s for s in self.steps if s.failed), None)


def figure_bundle(out: PipelineResult, tag: str) -> List[Tuple[str, Path, str]]:
    """The files of a run as ``(stable name, path, caption)``, for export.

    Files in ``outputs/`` carry the document tag (``gui_fig1_general_d3.svg``),
    which means nothing outside the session; the stable name drops it. The
    3-D page is included; files that no longer exist are skipped.
    """
    import re

    files = list(out.figures)
    if out.html_3d is not None:
        files.append(("Interactive 3D view (open in the browser)", out.html_3d))
    bundle = []
    for caption, src in files:
        src = Path(src)
        if src.exists():
            stable = re.sub(rf"_{re.escape(tag)}(?=\.[A-Za-z0-9]+$)", "", src.name)
            bundle.append((stable, src, caption))
    return bundle

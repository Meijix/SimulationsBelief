"""Shared ground of the adapters package: paths, the figure format, the
editor state shape and the report types every other module fills in.

Imported first by every sibling (``from . import base`` / ``from .base
import ...``), which is what puts the repository root on ``sys.path`` before
any core module is imported -- the GUI lives in its own subfolder but calls
the flat modules at the root, and this keeps the core completely untouched
and ``python gui/app.py`` working from any directory.
"""
from __future__ import annotations

import copy
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

# The GUI lives in its own subfolder but calls the flat modules at the repo
# root. Putting the root on sys.path here -- instead of packaging the project
# or moving files -- keeps the core completely untouched and makes
# ``python gui/app.py`` work no matter the current directory. It must happen
# before any core import below, which is why they carry ``noqa: E402``.
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from visualization import PALETTE, show as _show  # noqa: E402


# The GUI's figures are SVG: crisp at any zoom (retina, the lightbox), a
# fraction of the PNG size, and sized by the browser from the file's own
# width/height so the layout can tell tall figures from wide ones without
# decoding pixels. The CLI scripts keep their PNG default; only this wrapper
# changes it, and an explicit image_format still wins. (The 3-D figure is
# HTML either way.)
FIGURE_FORMAT = "svg"


def show(*args, **kwargs):
    """``visualization.show`` with the GUI's figure format as the default."""
    kwargs.setdefault("image_format", FIGURE_FORMAT)
    return _show(*args, **kwargs)


def agent_color_map(agents: List[str]) -> Dict[str, str]:
    """Colour per agent, IDENTICAL to the figures' assignment.

    ``visualization`` colours agents by sorted position over the Okabe-Ito
    palette; replicating that rule here lets the GUI paint each agent's chip
    with the same colour his edges have in every figure -- the visual thread
    that ties editor and output together.
    """
    ordered = sorted(agents, key=str)
    return {a: PALETTE[i % len(PALETTE)] for i, a in enumerate(ordered)}

# All figures go to the same folder the CLI scripts use (git-ignored), but
# resolved against the repo root so it does not depend on the caller's cwd.
OUTPUTS = ROOT / "outputs"

# ---------------------------------------------------------------------------
# The thesis example (Fig. 1) as the GUI's pre-filled default, so the first
# click reproduces the canonical end-to-end validation of thesis_example.py.
# ---------------------------------------------------------------------------
DEFAULT_AGENTS = "a, b, c"
DEFAULT_WORLDS = "w0, w1, w2"
# The same defaults as lists, for the GUI's chip selectors (which hold lists,
# not comma text).
DEFAULT_AGENT_LIST = ["a", "b", "c"]
DEFAULT_WORLD_LIST = ["w0", "w1", "w2"]
# Seeds only -- the S5 closure turns each chain into the complete relation.
DEFAULT_KNOWLEDGE = "a: w0-w1, w1-w2\nb: w0-w1, w1-w2\nc: w0-w1, w1-w2"
# Seeds only -- belief_closure makes each Q_a constant on the knowledge class:
# a ends up believing {w1, w2}, b is sure of w1, c is sure of w2.
DEFAULT_BELIEF = "a: w0>w1, w0>w2\nb: w0>w1\nc: w0>w2"

# The same example in the STRUCTURED shape the GUI's visual editor uses: per
# agent, a list of knowledge classes, each with the worlds the agent believes
# inside that class. This shape mirrors the thesis picture directly (a
# partition per agent + a believed subset per class) instead of raw edges --
# that is exactly what makes the editor easier than typing pairs.
#   'cls': worlds the agent cannot tell apart (one knowledge class).
#   'bel': the believed worlds INSIDE that class; empty list = no seed, which
#          from_partial reads as "believe exactly what you know" (KD45) or a
#          defunct belief (K45, axiom_d off).
DEFAULT_EDITOR = {
    "a": [{"cls": ["w0", "w1", "w2"], "bel": ["w1", "w2"]}],
    "b": [{"cls": ["w0", "w1", "w2"], "bel": ["w1"]}],
    "c": [{"cls": ["w0", "w1", "w2"], "bel": ["w2"]}],
}

# The three MODEL KINDS the core can build, as the GUI exposes them. The key
# travels through the whole adapter (``kind``) and decides which frame is
# built, which axioms are checked and how far the pipeline goes:
#
#   kb         KnowledgeBeliefFrame: S5 knowledge + KD45/K45 belief, and the
#              full pipeline (proper -> simplicial -> Hasse).
#   knowledge  S5 RelationalFrame (knowledge only). Editor rows are classes;
#              there is no belief. Proper and simplicial both work (the whole
#              complex is every agent's belief subcomplex).
#   belief     KD45/K45 RelationalFrame (belief only). Each row reads "from
#              these worlds, those are believed"; there are no classes.
#              Properness and the simplicial translation NEED S5, so the
#              pipeline stops after step 1 and says so.
KINDS = {
    "kb": "Knowledge and belief",
    "knowledge": "Knowledge only (S5)",
    "belief": "Belief only (KD45 / K45)",
    # The fourth kind skips Kripke altogether: the user declares vertices and
    # facets and the GUI builds the SimplicialBeliefModel as declared (see the
    # "direct simplicial complex" section below).
    "simplicial": "Simplicial complex (direct)",
}


# A facet of n agents is an (n-1)-simplex. Up to a tetrahedron (4 agents) the
# geometric drawings are faithful (edges, triangles, tetrahedra -- the 2-D
# figure of a tetrahedron is a projection, but a standard one); from 5 agents
# on no drawing in 2-D or 3-D is, so the GUI shows those complexes only in the
# ways that keep their meaning in any dimension: the incidence diagram (a
# facet is a point joined to its vertices), the face lattice and the text.
GEOMETRY_MAX_AGENTS = 4


def _geometric_ok(model) -> bool:
    return len(model.agents) <= GEOMETRY_MAX_AGENTS


def _dimension_note(model) -> str:
    n = len(model.agents)
    return (f"with {n} agents each facet is a {n - 1}-simplex, which does not fit in 3D: "
            "the geometric drawing and the 3D view are omitted; the complex is shown as an "
            "incidence diagram (each facet is a point joined to its vertices), "
            "face lattice and text")


def _hasse_caption(number: str, full: bool) -> str:
    """Caption for the lattice figure, depending on which rows are drawn.

    By default (issue #7) only the two rows a belief model reads: perspectives
    below, worlds above, and a line when the perspective is part of the world.
    The full lattice (every intermediate face) is optional because with three
    agents it is already hundreds of boxes.
    """
    if full:
        return (f"{number} · face lattice of the complex (Hasse diagram): "
                "one box per simplex, one row per dimension, and a line "
                "when one is an immediate face of the other")
    return (f"{number} · vertices and facets of the complex: perspectives below, "
            "worlds above, and a line when the perspective is part of the world "
            "(intermediate faces are omitted; enable them with “full lattice”)")
def blank_state(kind: str = "kb") -> dict:
    """An empty state with every key the GUI and this API expect."""
    return {
        "kind": kind,
        "agents": [], "worlds": [], "per_agent": {},
        "atoms": {},                       # atom -> worlds where it is true
        "vertices": {}, "facets": [], "vatoms": {},   # direct complex
        "complex_kind": "kb",              # direct complex: "kb" (S_a declared) or "knowledge" (S_a = S)
        "axiom_d": True,                   # KD45 (True) or K45 (False)
        "silent_defunct": False,           # K45: class with no belief = Q = ∅
        "explicit": False,                 # draw loops and both directions
        "hasse_full": False,               # full lattice, not only vertices+facets
        "make_3d": True,                   # write the interactive 3-D page (the heavy output)
    }


def state_from_example(example: dict) -> dict:
    """A complete state from an ``EXAMPLES`` entry (its own deep copy)."""
    import copy

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
    """Whether a direct complex is read as pure knowledge (``S_a = S``).

    ``state["complex_kind"]`` is ``"knowledge"`` or ``"kb"`` (the default, and
    what states saved before the key existed fall back to). There is no
    "belief-only" kind on purpose: in a complex the knowledge IS the gluing of
    the facets along shared vertices, so ``S_a`` cannot be declared without it.
    """
    return state.get("complex_kind", "kb") == "knowledge"


@dataclass
class StepReport:
    """What one pipeline step did, in the three terms the user cares about.

    The pipeline is a chain of closures and translations, and every link can
    (a) succeed, (b) succeed after FILLING IN things the user never drew, or
    (c) refuse. Reporting only (a)/(c) hides the most confusing case: a model
    that ran, but not the one the user thought they drew. So each step says:

        completed -- what a closure or a convention added on the user's behalf
        missing   -- what is still unspecified, and what that silence means
        failed    -- the conditions that made this step refuse (empty if it ran)

    ``failed`` being non-empty is what stops the pipeline; earlier steps keep
    their figures, so the user sees how far the translation got.
    """

    name: str
    completed: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    # A step that does not APPLY to this kind of model (the simplicial
    # translation of a pure-belief model): not an error, not silence either.
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
    """Everything the page needs to display one run, already flattened.

    The GUI never touches the model objects; it gets file paths and strings.
    That keeps the presentation layer dumb -- if tomorrow the figures came from
    a different renderer, ``app.py`` would not change a line.
    """

    log: List[str] = field(default_factory=list)
    # The log's numbers in structured form, for the GUI's stat tiles:
    # (value, label) pairs, e.g. ("9", "mundos · propio"). Same information as
    # ``log`` -- readable at a glance instead of as prose.
    stats: List[Tuple[str, str]] = field(default_factory=list)
    # Qualitative flags as (text, quasar-colour) chips: validity, logic, propriety.
    badges: List[Tuple[str, str]] = field(default_factory=list)
    # (caption, absolute path to the PNG) in pipeline order.
    figures: List[Tuple[str, Path]] = field(default_factory=list)
    # Interactive 3-D plotly page for the simplicial model (an .html file).
    html_3d: Path | None = None
    # (caption, ASCII diagram) -- the zero-dependency view of each model.
    text_diagrams: List[Tuple[str, str]] = field(default_factory=list)
    # For a direct complex: the editor state of its equivalent Kripke model
    # (G_B, docs/12), so the results view can open it as a new document and
    # the user can run the pipeline back from it (complex -> Kripke -> proper
    # -> complex). None when the complex has no facets.
    kripke_state: dict | None = None
    # One report per pipeline step, in order: what was completed, what is
    # missing, and what failed. The run stopped at the first step with
    # ``failed`` non-empty.
    steps: List[StepReport] = field(default_factory=list)

    @property
    def failed_step(self) -> StepReport | None:
        """The step that stopped the run, or None if the pipeline completed."""
        return next((s for s in self.steps if s.failed), None)

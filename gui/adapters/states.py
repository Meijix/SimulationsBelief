"""The state API: the three entry points that take a model STATE of any kind
(``preview_state``, ``evaluate_state``, ``run_state``) and dispatch to the
relational or the simplicial route.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from . import base  # noqa: F401  (puts the repository root on sys.path first)
from .base import _knowledge_only
from .complex import evaluate_simplicial_formula, preview_simplicial, run_simplicial
from .formulas import evaluate_formula
from .relational import preview_figure, run_pipeline_from_seeds, seeds_from_editor


# Everything that describes one model is a flat, serialisable dict (the
# "state", see ``base.blank_state``). These three functions resolve
# ``state["kind"]``, so callers need not know whether it is Kripke or a
# complex; ``tag`` keeps each document's files apart in outputs/. An action
# applied to a model produces another state (``actions.apply_action``).


def state_problem(state: dict) -> Optional[str]:
    """What the state lacks before anything can be drawn; ``None`` if nothing."""
    if state["kind"] == "simplicial":
        if not (state["agents"] and any(state["vertices"].get(a) for a in state["agents"])):
            return ("Add agents and their vertices. Facets are optional: a vertex in "
                    "no facet is drawn on its own.")
    elif not (state["agents"] and state["worlds"]):
        return "Add at least one agent and one world."
    return None


def preview_state(state: dict, tag: str = "") -> Tuple[Path, List[str]]:
    """Preview of the model AS IT IS, for any kind."""
    if state["kind"] == "simplicial":
        return preview_simplicial(
            state["agents"], state["vertices"], state["facets"], state["vatoms"],
            state["axiom_d"], tag, knowledge_only=_knowledge_only(state),
            font_scale=float(state.get("font_scale", 1.0)),
        )
    return preview_figure(
        state["agents"], state["worlds"], state["per_agent"], state["atoms"],
        state["explicit"], state["axiom_d"], state["kind"], tag,
    )


def evaluate_state(state: dict, text: str) -> List[Tuple[str, bool]]:
    """Evaluate a formula at every world (or facet) of the model."""
    if state["kind"] == "simplicial":
        return evaluate_simplicial_formula(
            state["agents"], state["vertices"], state["facets"], state["vatoms"],
            state["axiom_d"], text, knowledge_only=_knowledge_only(state),
        )
    return evaluate_formula(
        state["agents"], state["worlds"], state["per_agent"], state["atoms"],
        state["axiom_d"], text, not state["silent_defunct"], state["kind"],
    )


def run_state(state: dict, tag: str = "") -> "PipelineResult":
    """Run the pipeline that matches the model's kind.

    Raises:
        ValueError: whatever makes the model inexpressible (overlapping
            classes...). A step's violations are NOT raised: they stay in the
            result.
    """
    # ``.get``: states saved before the key existed remain valid and fall
    # back to the default view.
    hasse_full = bool(state.get("hasse_full", False))
    make_3d = bool(state.get("make_3d", True))
    # Label size of the complex figures; old documents have no key (1.0).
    font_scale = float(state.get("font_scale", 1.0))
    if state["kind"] == "simplicial":
        return run_simplicial(
            state["agents"], state["vertices"], state["facets"], state["vatoms"],
            state["axiom_d"], tag, hasse_full=hasse_full,
            knowledge_only=_knowledge_only(state), make_3d=make_3d,
            font_scale=font_scale,
        )
    knowledge, belief = seeds_from_editor(
        state["agents"], state["worlds"], state["per_agent"], state["kind"]
    )
    return run_pipeline_from_seeds(
        state["agents"], state["worlds"], knowledge, belief, state["axiom_d"],
        state["atoms"], not state["silent_defunct"], state["explicit"],
        state["kind"], tag, hasse_full=hasse_full, make_3d=make_3d,
        font_scale=font_scale,
    )

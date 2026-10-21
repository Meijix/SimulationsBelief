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


# --------------------------------------------------------------------------- #
# The STATE of a model and the API that works on it.
#
# The GUI handles several models at once (one "document" per model), so
# everything that describes ONE model lives in a flat, serialisable dict --
# the "state" -- and these three functions are the only entry point:
#
#     preview_state(state, tag)   -> (figure, what is missing)
#     evaluate_state(state, text) -> [(world or facet, holds?)]
#     run_state(state, tag)       -> PipelineResult
#
# They resolve the model kind (``state["kind"]``); callers need not know
# whether it is Kripke or a complex. ``tag`` keeps each document's files apart
# in outputs/ so two open models do not overwrite each other.
#
# THIS IS THE CONTRACT FOR THE ACTION LAYER (not implemented yet): applying an
# action to a model must produce ANOTHER state; with that the GUI already
# knows how to draw, validate, evaluate and compare it, with no new UI code.
# --------------------------------------------------------------------------- #


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
    if state["kind"] == "simplicial":
        return run_simplicial(
            state["agents"], state["vertices"], state["facets"], state["vatoms"],
            state["axiom_d"], tag, hasse_full=hasse_full,
            knowledge_only=_knowledge_only(state), make_3d=make_3d,
        )
    knowledge, belief = seeds_from_editor(
        state["agents"], state["worlds"], state["per_agent"], state["kind"]
    )
    return run_pipeline_from_seeds(
        state["agents"], state["worlds"], knowledge, belief, state["axiom_d"],
        state["atoms"], not state["silent_defunct"], state["explicit"],
        state["kind"], tag, hasse_full=hasse_full, make_3d=make_3d,
    )

"""Bridge between the GUI and the core modules: parse text -> run pipeline -> render.

A package since 2026-10-21 (one module per concern, listed below); this
``__init__`` re-exports every name so ``from adapters import X`` keeps working.

WHY THIS FILE EXISTS. The GUI is split in two layers on purpose:

    gui/app.py      -- presentation only (NiceGUI widgets, layout, notifications)
    gui/adapters/  -- everything else: parsing the user's text into the core's
                       data shapes, running the model -> proper -> simplicial
                       pipeline, and rendering figures via ``visualization.show``

The payoff of the split is the dependency direction. This module imports the
core; ``app.py`` imports this module; the core imports NEITHER. So the domain
code never learns that a web GUI exists (the same rule the core already
follows: ``visualization.py`` imports models only for type checking), and every
function here is plain Python -- callable and testable without a browser.

HOW THE HEAVY LIFTING IS AVOIDED. Two choices keep this file small:

    * Input is *partial* relations in a tiny text format (see the parsers), and
      ``KnowledgeBeliefFrame.from_partial`` + its closures force the rest --
      exactly the thesis-friendly entry point the core already provides.
    * Rendering reuses ``visualization.show`` verbatim: the GUI displays the
      same PNG/HTML files the scripts produce, instead of re-implementing any
      drawing. One renderer, two consumers.

The modules, in dependency order:

    base          paths, figure format, editor state shape, StepReport/PipelineResult
    examples      the example library (every model of the repo's scripts)
    relational    seeds -> frames, properness, the Kripke pipeline and its diagnostics
    formulas      the formula parser and the relational evaluator
    complex       the direct simplicial complex: build, validate, draw, read back
    workspace_io  saving and loading workspaces
    actions       simplicial actions: spec, validation, live drawing, apply
    states        preview_state / evaluate_state / run_state, dispatching by kind
"""

from __future__ import annotations

from .base import (  # noqa: F401
    DEFAULT_AGENTS,
    DEFAULT_AGENT_LIST,
    DEFAULT_BELIEF,
    DEFAULT_EDITOR,
    DEFAULT_KNOWLEDGE,
    DEFAULT_WORLDS,
    DEFAULT_WORLD_LIST,
    FIGURE_FORMAT,
    GEOMETRY_MAX_AGENTS,
    KINDS,
    OUTPUTS,
    PipelineResult,
    ROOT,
    StepReport,
    _dimension_note,
    _fname,
    _geometric_ok,
    _hasse_caption,
    _knowledge_only,
    agent_color_map,
    blank_state,
    show,
    state_from_example,
)
from .examples import (  # noqa: F401
    EXAMPLES,
    _MUDDY_W,
    _NASA_W,
    _entry,
    _script_examples,
    editor_rows,
)
from .relational import (  # noqa: F401
    _fmt_edges,
    _valuation_of,
    build_general,
    diagnose_general,
    diagnose_general_frame,
    diagnose_proper,
    diagnose_simplicial,
    edge_style,
    parse_names,
    parse_relation,
    preview_figure,
    run_pipeline,
    run_pipeline_from_seeds,
    seeds_from_editor,
    state_from_relational,
)
from .formulas import (  # noqa: F401
    _ATOM,
    _TOKEN,
    _uses,
    evaluate_formula,
    parse_formula,
)
from .complex import (  # noqa: F401
    _consistent_part,
    _simplicial_problems,
    build_simplicial,
    doc_from_model,
    evaluate_simplicial_formula,
    maximal_facets,
    new_facet,
    preview_simplicial,
    run_simplicial,
    simplicial_assignment,
    simplicial_state_from_editor,
    state_from_simplicial_model,
)
from .workspace_io import (  # noqa: F401
    SAVED,
    WORKSPACE_FORMAT,
    list_saved,
    load_workspace,
    load_workspace_full,
    save_workspace,
    workspace_payload,
)
from .actions import (  # noqa: F401
    ACTION_EXAMPLES,
    ACTION_MODES,
    DEFAULT_MODE,
    MODES,
    SimplicialAction,
    UPDATE_KINDS,
    _conditions,
    _formula_table,
    _pair_parts,
    _pair_text,
    action_node_names,
    action_problems,
    apply_action,
    blank_action,
    build_action,
    describe_action,
    describe_action_kripke,
    preview_action,
    spec_atoms,
    update_model,
)
from .states import (  # noqa: F401
    evaluate_state,
    preview_state,
    run_state,
    state_problem,
)

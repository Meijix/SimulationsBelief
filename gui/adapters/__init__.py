"""Bridge between the GUI and the core modules: editor state -> models ->
figures and reports. The views (``gui/views``) import from here and never
touch a model object; the core never imports the GUI.

The modules, in dependency order:

    base          paths, figure style, the editor state shape, StepReport/PipelineResult
    examples      the example library (every model of the repo's scripts)
    relational    seeds -> frames, the Kripke pipeline and its diagnostics
    formulas      the formula parser and the relational evaluator
    complex       the direct simplicial complex: build, validate, draw, read back
    workspace_io  saving and loading workspaces (saved_models/README.md)
    actions       simplicial actions: spec, validation, live drawing, apply
    states        preview_state / evaluate_state / run_state, dispatching by kind
"""

from __future__ import annotations

from .base import (  # noqa: F401
    KINDS,
    OUTPUTS,
    PipelineResult,
    StepReport,
    agent_color_map,
    blank_state,
    figure_bundle,
    figure_style,
    print_light,
    state_from_example,
    styled,
)
from .examples import EXAMPLES  # noqa: F401
from .relational import (  # noqa: F401
    build_general,
    run_pipeline_from_seeds,
    seeds_from_editor,
    state_from_relational,
)
from .formulas import evaluate_formula, parse_formula  # noqa: F401
from .complex import (  # noqa: F401
    build_simplicial,
    doc_from_model,
    evaluate_simplicial_formula,
    maximal_facets,
    new_facet,
    run_simplicial,
    simplicial_assignment,
    simplicial_state_from_editor,
    state_from_simplicial_model,
)
from .workspace_io import (  # noqa: F401
    WORKSPACE_FORMAT,
    file_name,
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
    UPDATE_HELP,
    UPDATE_KINDS,
    action_node_names,
    action_problems,
    apply_action,
    blank_action,
    build_action,
    describe_action,
    describe_action_kripke,
    event_belief,
    preview_action,
)
from .states import evaluate_state, preview_state, run_state, state_problem  # noqa: F401

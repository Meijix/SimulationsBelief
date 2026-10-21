"""The direct simplicial complex: build it exactly as declared, validate,
draw, evaluate formulas on it, complete it to the maximal complex, and read
any computed ``SimplicialBeliefModel`` back into an editor state.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Dict, List, Tuple

from . import base  # noqa: F401  (puts the repository root on sys.path first)
from assignment import (assignment_from_model, drop_inconsistent, facet_inconsistencies,
    holds as holds_simplicial, maximal_complex)
import hasse
from properness import to_proper as frame_to_proper
from semantics import lift_valuation
from simplicial import Node, SimplicialBeliefModel, label_node, to_relational, to_simplicial
from visualization import visualize
from .base import (
    FIGURE_FORMAT,
    OUTPUTS,
    PipelineResult,
    StepReport,
    _dimension_note,
    _fname,
    _geometric_ok,
    _hasse_caption,
    blank_state,
    show,
)
from .formulas import parse_formula
from .relational import _valuation_of, build_general, seeds_from_editor, state_from_relational


# --------------------------------------------------------------------------- #
# Direct simplicial complex. The editor stores three things, all under the
# names the user types:
#
#   vertices  {agent: [name, ...]}          the vertices of each colour
#   facets    [{"name": str,                 a facet = one vertex PER agent
#               "nodes": {agent: vertex},    (the UCF condition) ...
#               "belief": [agent, ...]}]     ... and the S_a that contain it
#   vatoms    {atom: {"true": [vertex..],    the assignment L : N -> {0,1,2}
#                     "false": [vertex..]}}  on VERTICES (2 = not listed)
#
# No translation in between: what is drawn is what is declared, and validation
# is the model's own (UCF, S_a ⊆ S non-empty, "no isolated perspectives" under
# Axiom D) plus the per-facet consistency of the assignment. A declared vertex
# that is in no facet is NOT dropped: it is an isolated vertex of the complex
# (issue #12) and is drawn and reported as such.
# --------------------------------------------------------------------------- #
def build_simplicial(
    agents: List[str],
    vertices: Dict[str, List[str]],
    facets: List[dict],
    axiom_d: bool = True,
    validate: bool = True,
    knowledge_only: bool = False,
    notes: List[str] | None = None,
) -> Tuple[SimplicialBeliefModel, Dict[str, Node], Dict[str, frozenset]]:
    """The simplicial model exactly as the editor declares it.

    A vertex is a ``Node(agent, {name})``: its "class" is its own name, which
    is all the identity a hand-declared vertex has. A facet missing some
    agent's vertex is NOT rejected here: it is built incomplete and
    ``violations()`` reports it as a UCF failure, like any other condition.
    ALL declared vertices enter the model, whether or not they lie in a facet:
    one with no facet is an isolated perspective (legal under K45, a violation
    under Axiom D), not an input error. No facet at all is fine too (GitHub
    #24): the complex is then 0-dimensional, every vertex drawn on its own.

    Two facets with the same vertices ARE the same facet (a facet is its
    vertex set), so the second is merged into the first -- its name is dropped
    and its belief marks are kept -- instead of being refused (GitHub #23: the
    editor's "add facet" used to produce exactly that). ``notes``, if given,
    receives one line per merge so the GUI can say what happened.

    Returns:
        ``(model, vertices by name, facets by name)``; a merged facet's name
        maps to the vertex set it shares with the one that was kept.

    Raises:
        ValueError: whatever makes the drawing inexpressible -- a repeated
            vertex, two facets with one name -- and, with ``validate=True``,
            the model's own violations. A facet with no vertices at all is
            left out and noted, like a duplicate.
    """
    by_name: Dict[str, Node] = {}
    for a in agents:
        for v in vertices.get(a, []):
            if v in by_name:
                raise ValueError(f"vertex '{v}' is declared twice")
            by_name[v] = Node(a, frozenset({v}))
    facet_of: Dict[str, frozenset] = {}
    name_of: Dict[frozenset, str] = {}
    for f in facets:
        name = f["name"]
        if name in facet_of:
            raise ValueError(f"two facets are named '{name}'")
        members = frozenset(
            by_name[v] for a in agents
            if (v := f.get("nodes", {}).get(a)) in by_name and by_name[v].agent == a
        )
        if not members:
            # Every slot empty: the facet the editor just added before the
            # user filled it in. Not part of the model yet, not an error.
            facet_of[name] = members
            if notes is not None:
                notes.append(f"facet '{name}' has no vertices yet: not drawn until it has some")
            continue
        facet_of[name] = members
        if members in name_of:
            if notes is not None:
                notes.append(
                    f"facets '{name_of[members]}' and '{name}' have the same vertices: "
                    f"they are one facet, drawn once as '{name_of[members]}'"
                )
            continue
        name_of[members] = name
    # The model's facets are the distinct non-empty vertex sets (``name_of``);
    # ``facet_of`` also maps merged and empty names, for the callers that look
    # a declared facet up by name.
    belief = {
        a: {facet_of[f["name"]] for f in facets
            if a in f.get("belief", []) and facet_of[f["name"]]}
        for a in agents
    }
    if knowledge_only:
        # A knowledge complex has no belief data: S_a = S for everyone (the
        # simplicial analogue of a knowledge-only S5 frame, "believe what you
        # know"). The per-facet ``belief`` lists are ignored, not erased, so
        # switching the editor back to knowledge+belief restores them.
        belief = {a: set(name_of) for a in agents}
    model = SimplicialBeliefModel(
        agents, by_name.values(), name_of.keys(), belief, world_of_facet=name_of,
        validate=validate, axiom_d=axiom_d,
        node_names={n: v for v, n in by_name.items()},
    )
    return model, by_name, facet_of


def simplicial_assignment(by_name: Dict[str, Node], vatoms: Dict[str, dict]):
    """The editor's vertex assignment, in the format ``assignment.py`` expects."""
    out: Dict[Node, Dict[str, int]] = {}
    for atom, spec in (vatoms or {}).items():
        trues, falses = set(spec.get("true", [])), set(spec.get("false", []))
        both = sorted(trues & falses)
        if both:
            raise ValueError(
                f"atom '{atom}' is marked both true and false at {both}"
            )
        for v in trues:
            if v in by_name:
                out.setdefault(by_name[v], {})[atom] = 1
        for v in falses:
            if v in by_name:
                out.setdefault(by_name[v], {})[atom] = 0
    return out


def _consistent_part(model, assignment, by_name) -> Tuple[SimplicialBeliefModel, List[str]]:
    """Drop the inconsistent facets of a declared complex and say which went.

    Chapter 3's model is the maximal CONSISTENT complex, so a facet whose
    vertices disagree on an atom is not a validation error but a facet that
    does not exist (GitHub #21): it is removed from S and every S_a, and the
    user is told, facet by facet, which atom clashed and where. Returns the
    pruned model and the notes (empty when nothing was inconsistent).
    """
    names_before = dict(model.world_of_facet)
    model, removed = drop_inconsistent(model, assignment)
    if not removed:
        return model, []
    name = {n: v for v, n in by_name.items()}
    details = []
    for F in removed:
        why = "; ".join(
            f"{atom}: {name.get(t, label_node(t))} true, {name.get(f, label_node(f))} false"
            for atom, t, f in facet_inconsistencies(F, assignment)
        )
        details.append(f"{names_before.get(F, '?')} ({why})")
    return model, [
        "facets removed for inconsistency (the maximal complex M(N,V,L) "
        f"only has consistent facets): {'; '.join(details)}"
    ]


def _simplicial_problems(model, assignment, by_name, vertices) -> Tuple[List[str], List[str]]:
    """``(violations, notes)`` for a hand-declared complex (already pruned)."""
    problems = model.violations()
    name = {n: v for v, n in by_name.items()}
    notes = []
    if not model.facets:
        notes.append(
            "no facets yet: a 0-dimensional complex, every vertex is a world of "
            "its own agent alone (add facets to glue perspectives into worlds)"
        )
    loose = sorted(name[n] for n in model.isolated_nodes())
    if loose:
        notes.append(
            "vertices in no facet (isolated: no world passes through them; "
            f"drawn loose): {', '.join(loose)}"
        )
    if not model.axiom_d:
        # Under K45 an isolated perspective is not a violation, but it does
        # change the semantics (B_a holds vacuously there): say so where the
        # user will see it, rather than let them find out by evaluating a formula.
        for a in sorted(model.agents, key=str):
            stuck = sorted(name[n] for n in model.isolated_perspectives()[a])
            if stuck:
                notes.append(
                    f"isolated perspectives of {a} (in no facet of S_{a}: "
                    f"there {a} vacuously believes everything): {', '.join(stuck)}"
                )
    orphan = [model.world_of_facet[F] for F in model.facets
              if not any(F in fs for fs in model.belief_facets.values())]
    if orphan:
        notes.append(
            "facets outside every belief subcomplex (nobody considers them "
            f"possible): {', '.join(sorted(map(str, orphan)))}"
        )
    return problems, notes


def preview_simplicial(
    agents: List[str], vertices: Dict[str, List[str]], facets: List[dict],
    vatoms: Dict[str, dict], axiom_d: bool = True, tag: str = "",
    knowledge_only: bool = False,
) -> Tuple[Path, List[str]]:
    """Preview of the complex AS DECLARED, without requiring validity.

    "As declared" up to consistency: an inconsistent facet is not drawn (it is
    not part of the model, see :func:`_consistent_part`) and the returned list
    says so, next to the structural violations.
    """
    merged: List[str] = []
    model, by_name, _ = build_simplicial(agents, vertices, facets, axiom_d, validate=False,
                                         knowledge_only=knowledge_only, notes=merged)
    assignment = simplicial_assignment(by_name, vatoms)
    model, dropped = _consistent_part(model, assignment, by_name)
    dropped = merged + dropped
    path = Path(show(model, _fname("gui_preview", tag), "Complex as entered",
                     output_dir=str(OUTPUTS), assignment=assignment or None,
                     engine="auto" if _geometric_ok(model) else "dot"))
    problems, _ = _simplicial_problems(model, assignment, by_name, vertices)
    notes = [] if _geometric_ok(model) else [_dimension_note(model)]
    return path, dropped + problems + notes


def evaluate_simplicial_formula(
    agents: List[str], vertices: Dict[str, List[str]], facets: List[dict],
    vatoms: Dict[str, dict], axiom_d: bool, text: str,
    knowledge_only: bool = False,
) -> List[Tuple[str, bool]]:
    """Evaluate the formula at every facet of the model with the vertex-based semantics (ch. 3).

    Inconsistent facets are not part of the model (see :func:`_consistent_part`),
    so they get no row. Structural violations of what remains are raised, as
    the constructor would.
    """
    formula = parse_formula(text, agents, list(vatoms or {}))
    model, by_name, facet_of = build_simplicial(agents, vertices, facets, axiom_d,
                                                validate=False, knowledge_only=knowledge_only)
    assignment = simplicial_assignment(by_name, vatoms)
    model, _ = _consistent_part(model, assignment, by_name)
    problems = model.violations()
    if problems:
        raise ValueError(
            f"{len(problems)} simplicial-model violation(s) found:\n  - " + "\n  - ".join(problems)
        )
    return [(f["name"], holds_simplicial(model, assignment, facet_of[f["name"]], formula))
            for f in facets if facet_of[f["name"]] in model.facets]


def new_facet(state: dict) -> dict:
    """The facet the editor's "add facet" button appends (GitHub #23).

    It starts from the first vertex combination (in declaration order) that no
    existing facet uses, so two clicks never produce the same facet twice: a
    facet IS its vertex set, and a copy of the previous one was being merged
    away -- which looked like the button doing nothing, or worse. When every
    combination is taken (or an agent has no vertex) the new facet starts
    empty for that agent. It is in everyone's belief subcomplex, the common case.
    """
    from itertools import product

    agents = list(state["agents"])
    taken_names = {f["name"] for f in state["facets"]}
    n = len(state["facets"]) + 1
    while f"F{n}" in taken_names:
        n += 1
    used = {tuple(f.get("nodes", {}).get(a) for a in agents) for f in state["facets"]}
    nodes = {a: None for a in agents}
    choices = [state["vertices"].get(a) or [None] for a in agents]
    for combo in product(*choices):
        if combo not in used:
            nodes = dict(zip(agents, combo))
            break
    return {"name": f"F{n}", "nodes": nodes, "belief": list(agents)}


def maximal_facets(
    agents: List[str], vertices: Dict[str, List[str]], vatoms: Dict[str, dict],
    facets: List[dict],
) -> Tuple[List[dict], int]:
    """The editor's facet list completed to the maximal complex ``M(N, V, L)``.

    Every UCF facet the declared vertices can form and whose vertex atoms do
    not clash (:func:`assignment.maximal_complex`) is added, named ``F<n>``
    and believed by everyone, the editor's default for a new facet; the facets
    already declared keep their names and belief lists. Returns the new list
    and how many facets were added. This is the "build from the maximal
    complex" of GitHub #21, as an action the user takes rather than something
    done behind their back: a declared complex is often meant to be a proper
    subcomplex of ``M(N, V, L)``.

    Raises:
        ValueError: when some agent has no vertex (no UCF facet exists) or the
            vertex atoms are ill-formed, with the core's own message.
    """
    by_name: Dict[str, Node] = {}
    for a in agents:
        for v in vertices.get(a, []):
            by_name[v] = Node(a, frozenset({v}))
    assignment = simplicial_assignment(by_name, vatoms)
    wanted = maximal_complex(agents, by_name.values(), assignment)
    name_of_node = {n: v for v, n in by_name.items()}
    have = {
        frozenset(by_name[v] for a in agents
                  if (v := f.get("nodes", {}).get(a)) in by_name)
        for f in facets
    }
    out = [copy.deepcopy(f) for f in facets]
    taken = {f["name"] for f in out}
    n = len(out) + 1
    added = 0
    for F in sorted(wanted - have, key=lambda F: sorted(name_of_node[x] for x in F)):
        while f"F{n}" in taken:
            n += 1
        taken.add(f"F{n}")
        # "auto": the editor shows these as added by the completion and can
        # remove them again ("quitar las facetas añadidas"); the model ignores it.
        out.append({"name": f"F{n}",
                    "nodes": {x.agent: name_of_node[x] for x in F},
                    "belief": list(agents), "auto": True})
        added += 1
    return out, added


def run_simplicial(
    agents: List[str], vertices: Dict[str, List[str]], facets: List[dict],
    vatoms: Dict[str, dict], axiom_d: bool = True, tag: str = "",
    hasse_full: bool = False, knowledge_only: bool = False, make_3d: bool = True,
) -> "PipelineResult":
    """The "pipeline" of a direct complex: validate and draw, nothing to translate.

    ``hasse_full`` picks the lattice figure: by default only vertices and
    facets (issue #7); ``True`` draws every face. ``knowledge_only`` reads the
    complex as pure knowledge (``S_a = S``, no belief data).
    """
    result = PipelineResult()
    step = StepReport("1 · Simplicial complex (defined directly)")
    result.steps.append(step)
    merged: List[str] = []
    try:
        model, by_name, _ = build_simplicial(agents, vertices, facets, axiom_d,
                                             validate=False, knowledge_only=knowledge_only,
                                             notes=merged)
        assignment = simplicial_assignment(by_name, vatoms)
    except ValueError as exc:
        step.failed.append(str(exc))
        result.badges.append(("inexpressible", "negative"))
        return result
    # Inconsistent facets are removed, not refused (GitHub #21): the model is
    # the maximal consistent complex, and the removal is reported as something
    # the theory completed for the user. Duplicate facets are merged the same way.
    model, dropped = _consistent_part(model, assignment, by_name)
    step.completed += merged + dropped
    problems, notes = _simplicial_problems(model, assignment, by_name, vertices)
    step.missing += notes
    if problems:
        step.failed.append("\n".join(problems))
        result.badges.append(("invalid", "negative"))
    else:
        result.badges.append(("valid", "positive"))
        if knowledge_only:
            step.completed.append(
                f"well-formed knowledge complex: {len(model.facets)} facets, "
                f"{len(model.nodes)} vertices; S_a = S for every agent (each one "
                "believes exactly what it knows, B_a coincides with K_a)"
            )
        else:
            sizes = ", ".join(f"S_{a} = {len(model.belief_facets[a])}"
                              for a in sorted(model.agents, key=str))
            step.completed.append(
                f"well-formed complex: {len(model.facets)} facets, "
                f"{len(model.nodes)} vertices; belief subcomplexes: {sizes}"
            )
    # A knowledge complex has no belief logic to name: S_a = S makes D hold
    # trivially, so the KD45/K45 badge would say nothing.
    result.badges.append(("knowledge (S_a = S)" if knowledge_only
                          else ("KD45" if axiom_d else "K45"), "primary"))
    result.stats.append((str(len(model.facets)), "facets"))
    result.stats.append((str(len(model.nodes)), "vertices"))
    if not knowledge_only:
        for a in sorted(model.agents, key=str):
            result.stats.append((str(len(model.belief_facets[a])), f"S_{a}"))
    asg = assignment or None
    # The figures are drawn even for an invalid complex: seeing it is how the
    # user finds the facet that breaks UCF or the isolated perspective.
    geometric = _geometric_ok(model)
    if not geometric:
        step.missing.append(_dimension_note(model))
    result.figures.append((
        "Fig. 1 · the declared simplicial complex" if geometric else
        "Fig. 1 · the declared complex, as an incidence diagram (each facet is "
        "a point joined to its vertices: with 5 or more agents there is no faithful geometric drawing)",
        Path(show(model, _fname("gui_fig3_simplicial", tag), "Simplicial complex",
                  output_dir=str(OUTPUTS), assignment=asg,
                  engine="auto" if geometric else "dot")),
    ))
    # The interactive 3-D page is the heavy output (~3 MB of embedded
    # Plotly per run); the GUI's "generar vista 3D" switch skips it, and so
    # does a complex of 5+ agents, which has no faithful 3-D drawing.
    if make_3d and geometric:
        result.html_3d = Path(show(model, _fname("gui_fig3_3d", tag), "Simplicial complex · 3D",
                                   dim=3, output_dir=str(OUTPUTS), assignment=asg))
    lattice = hasse.face_lattice(model, include_empty=False, assignment=asg)
    result.figures.append((
        _hasse_caption("Fig. 2", hasse_full),
        Path(hasse.show(lattice, _fname("gui_fig4_hasse", tag), "Face lattice",
                        output_dir=str(OUTPUTS), rankdir="BT",
                        facets_and_vertices=not hasse_full, image_format=FIGURE_FORMAT)),
    ))
    result.text_diagrams.append(("Simplicial complex", str(model)))
    result.text_diagrams.append(("Face lattice", hasse.visualize(lattice)))
    # -- Step 2: the Kripke model the complex IS (the functor G_B, docs/12). --
    # One world per facet, knowledge = sharing a vertex, belief = the facets
    # of S_a; KD45 or K45 read off the geometry. Vertices in no facet have
    # no world and are left out, with a note.
    back = StepReport("2 · Equivalent relational model (complex → Kripke)")
    if not model.facets:
        back.missing.append("no facets, so no worlds: the Kripke model is empty "
                            "(each vertex alone has no world to stand in)")
        result.steps.append(back)
        return result
    try:
        rel = to_relational(model, assignment, ignore_isolated=True)
    except ValueError as exc:
        back.failed.append(str(exc))
        result.steps.append(back)
        return result
    name = {n: v for v, n in by_name.items()}
    loose = sorted(name.get(n, label_node(n)) for n in model.isolated_nodes())
    if loose:
        back.missing.append(
            "vertices in no facet have no world in the Kripke model "
            f"(they stay outside the equivalence, docs/12 §3.3): {', '.join(loose)}"
        )
    logic = "KD45" if rel.frame.axiom_d else "K45"
    back.completed.append(
        f"complex → Kripke model (G_B): {len(rel.frame.worlds)} worlds, one per "
        "facet; R_a = sharing a's vertex, Q_a = facets of S_a with that vertex; "
        + ("pure knowledge (Q_a = R_a)" if model.is_knowledge_only else
           f"{logic} belief (D ⟺ no isolated perspectives)")
    )
    result.steps.append(back)
    if model.is_knowledge_only:
        kripke, kw = rel.frame.knowledge, {"logic": "S5"}
    else:
        kripke, kw = rel.frame, {}
    result.figures.append((
        "Fig. 3 · equivalent Kripke model (G_B): worlds = facets, R_a = sharing "
        "a's vertex (thin line), Q_a = facets of S_a (thick arrow)",
        Path(show(kripke, _fname("gui_fig1_general", tag), "Equivalent relational model",
                  output_dir=str(OUTPUTS), valuation=rel.valuation or None, **kw)),
    ))
    result.text_diagrams.append(("Equivalent relational model", visualize(rel.frame)))
    result.kripke_state = state_from_relational(rel, knowledge_only=model.is_knowledge_only)
    return result


def simplicial_state_from_editor(
    kind: str, agents: List[str], worlds: List[str],
    per_agent: Dict[str, List[dict]], atoms: Dict[str, List[str]],
    axiom_d: bool, believe_all_when_silent: bool = True,
) -> Tuple[Dict[str, List[str]], List[dict], Dict[str, dict]]:
    """Translate the relational model being edited into a direct-complex state.

    This BOOTSTRAPS the simplicial editor from what is already drawn: it runs
    general -> proper -> simplicial and dumps the result into named vertices
    (a0, a1, ... per agent), facets named after their world, and the
    assignment the valuation induces. From there the complex is free: it is
    edited without going through Kripke.

    Raises:
        ValueError: if the current model cannot be translated (pure belief,
            invalid model...).
    """
    from visualization import facet_name

    if kind == "belief":
        raise ValueError("a belief-only model has no simplicial translation")
    knowledge, belief = seeds_from_editor(agents, worlds, per_agent, kind)
    general = build_general(kind, agents, worlds, knowledge, belief, axiom_d,
                            believe_all_when_silent)
    proper = general.to_proper() if kind == "kb" else frame_to_proper(general)
    sm = to_simplicial(proper)
    names: Dict[Node, str] = {}
    vertices: Dict[str, List[str]] = {a: [] for a in agents}
    for a in agents:
        mine = sorted((n for n in sm.nodes if n.agent == a),
                      key=lambda n: sorted(map(str, n.cls)))
        for i, n in enumerate(mine):
            names[n] = f"{a}{i}"
            vertices[a].append(names[n])
    facets = [
        {"name": facet_name(sm, F),
         "nodes": {n.agent: names[n] for n in F},
         "belief": [a for a in agents if F in sm.belief_facets[a]]}
        for F in sorted(sm.facets, key=lambda F: facet_name(sm, F))
    ]
    vatoms: Dict[str, dict] = {}
    valuation = _valuation_of(atoms)
    if valuation:
        lifted = (lift_valuation(valuation, proper.projection)
                  if proper.projection else valuation)
        for node, values in assignment_from_model(sm, lifted).items():
            for atom, value in values.items():
                spec = vatoms.setdefault(atom, {"true": [], "false": []})
                spec["true" if value == 1 else "false"].append(names[node])
    for atom in atoms or {}:
        vatoms.setdefault(atom, {"true": [], "false": []})
    return vertices, facets, vatoms


def state_from_simplicial_model(
    model: SimplicialBeliefModel,
    assignment=None,
    agents: List[str] | None = None,
) -> dict:
    """A direct-complex STATE for any :class:`SimplicialBeliefModel` (GitHub #18).

    This is how a model that was not typed in the editor -- the output of an
    action (``simplicial_actions.update_model``), a revision, a script --
    enters the workspace: once it is a state the GUI draws, validates,
    evaluates, saves and compares it like any other document.

    Naming: vertices keep ``model.node_names`` when present; otherwise a
    one-world class is named by that world (``a0``, ``as``...) and any other
    class ``<agent><i>``; a name already taken by another agent is prefixed
    with its agent so the editor's "one name, one vertex" rule holds. Facets
    are named by their world (``world_of_facet``) or ``F<i>``. The assignment
    becomes the per-atom true/false vertex lists; the knowledge-only reading
    (``S_a = S``) is detected and recorded in ``complex_kind``.
    """
    agents = list(agents) if agents is not None else sorted(model.agents, key=str)
    given = getattr(model, "node_names", None) or {}
    names: Dict[Node, str] = {}
    taken: set = set()
    for a in agents:
        mine = sorted((n for n in model.nodes if n.agent == a),
                      key=lambda n: sorted(map(str, n.cls)))
        for i, n in enumerate(mine):
            base = (str(given[n]) if n in given
                    else str(next(iter(n.cls))) if len(n.cls) == 1 else f"{a}{i}")
            name = base if base not in taken else f"{a}:{base}"
            while name in taken:
                name += "'"
            names[n], taken = name, taken | {name}
    vertices = {a: [names[n] for n in sorted((n for n in model.nodes if n.agent == a),
                                              key=lambda n: names[n])]
                for a in agents}

    def facet_label(F, i):
        w = model.world_of_facet.get(F)
        return str(w) if w is not None else f"F{i + 1}"

    ordered = sorted(model.facets, key=lambda F: sorted(names[n] for n in F))
    facets = [
        {"name": facet_label(F, i),
         "nodes": {n.agent: names[n] for n in F},
         "belief": [a for a in agents if F in model.belief_facets.get(a, ())]}
        for i, F in enumerate(ordered)
    ]
    vatoms: Dict[str, dict] = {}
    for node, values in (assignment or {}).items():
        if node not in names:
            continue
        for atom, value in values.items():
            spec = vatoms.setdefault(str(atom), {"true": [], "false": []})
            if value == 1:
                spec["true"].append(names[node])
            elif value == 0:
                spec["false"].append(names[node])
    # Sorted: ``assignment`` may have been built from sets (the editor's own
    # ``simplicial_assignment`` does), whose order changes with the hash seed;
    # a saved state must not differ from run to run.
    for spec in vatoms.values():
        spec["true"].sort()
        spec["false"].sort()
    state = blank_state("simplicial")
    state.update({
        "agents": agents, "vertices": vertices, "facets": facets, "vatoms": vatoms,
        "axiom_d": bool(model.axiom_d),
        "complex_kind": "knowledge" if model.is_knowledge_only else "kb",
    })
    return state


def doc_from_model(name: str, model: SimplicialBeliefModel, assignment=None,
                   origin: str | None = None, readonly: bool = True) -> dict:
    """A workspace document (name, state, provenance) for a computed model.

    The GUI's ``new_doc`` takes exactly these fields; ``origin`` is the human
    label of where the model came from ("action tell on Model 1"), shown
    on the read-only banner and in the comparison panels.
    """
    return {"name": name, "state": state_from_simplicial_model(model, assignment),
            "readonly": readonly, "origin": {"label": origin} if origin else None}

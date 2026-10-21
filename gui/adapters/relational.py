"""The relational (Kripke) side: seeds -> closed frames, properness, the
general -> proper -> simplicial pipeline with its step-by-step diagnostics,
the live preview of a relational model, and the state of the Kripke model
``to_relational`` returns for a complex.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from . import base  # noqa: F401  (puts the repository root on sys.path first)
from assignment import assignment_from_model, nu_violations
import hasse
from knowledge_belief import KnowledgeBeliefFrame, knowledge_classes
from properness import (cheapest_distinguished_agent, equivalence_violations, is_proper as frame_is_proper,
    to_proper as frame_to_proper)
from relational_frame import RelationalFrame
from semantics import lift_valuation
from simplicial import to_simplicial
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
from .examples import editor_rows


def seeds_from_editor(
    agents: List[str],
    worlds: List[str],
    per_agent: Dict[str, List[dict]],
    kind: str = "kb",
) -> Tuple[Dict[str, Set[Tuple[str, str]]], Dict[str, Set[Tuple[str, str]]]]:
    """Turn the visual editor's classes/beliefs into ``from_partial`` seeds.

    ``kind`` (see ``KINDS``) changes what a row MEANS:

        * ``"kb"``: a knowledge class plus the worlds believed inside it;
        * ``"knowledge"``: a knowledge class; the belief column is ignored;
        * ``"belief"``: "from these worlds, these are believed" -- the sources
          play the role of the class (still disjoint across rows: a world has
          ONE belief set), but the believed worlds are not restricted to them,
          because without knowledge there is no class to stay inside.

    The editor speaks in the thesis's own vocabulary (knowledge classes and
    believed subsets); the core speaks in edges. The translation is mechanical:

        * a class ``{w0, w1}`` becomes the complete knowledge seed on it (the
          S5 closure would rebuild the rest anyway, completeness just makes the
          intent explicit);
        * believed worlds become ``(x, b)`` edges from EVERY world of the class
          (belief is constant on the class, so seeding it everywhere is the
          honest rendering of what the editor showed the user).

    Worlds left out of every class need no edges at all: ``from_partial``
    defaults each of them to a singleton class (identity knowledge).

    Raises:
        ValueError: if one agent lists the same world in two classes. The S5
            closure would silently MERGE those classes into one -- a valid
            model, but not the partition the user drew -- so it is rejected
            with a message naming the culprit instead.
    """
    knowledge: Dict[str, Set[Tuple[str, str]]] = {a: set() for a in agents}
    belief: Dict[str, Set[Tuple[str, str]]] = {a: set() for a in agents}
    for agent in agents:
        seen: Set[str] = set()
        for row in per_agent.get(agent, []):
            cls = [w for w in row["cls"] if w in worlds]
            bel = [w for w in row["bel"] if w in (worlds if kind == "belief" else cls)]
            overlap = seen & set(cls)
            if overlap:
                raise ValueError(
                    f"agent '{agent}' has {sorted(overlap)} in two different "
                    "rows; "
                    + ("each world carries ONE believed set of worlds"
                       if kind == "belief" else
                       "knowledge classes must be disjoint "
                       "(the S5 closure would silently merge them)")
                )
            seen |= set(cls)
            if kind != "belief":
                knowledge[agent] |= {(x, y) for x in cls for y in cls}
            if kind != "knowledge":
                belief[agent] |= {(x, b) for x in cls for b in bel}
    if kind == "kb" and not any(belief.values()):
        # No believed world anywhere -> case-3 input for from_partial
        # (knowledge only, Q_a defaults to R_a): an EMPTY mapping, not empty
        # sets. Pure-belief mode must NOT collapse: there every agent's entry
        # is the relation itself, empty or not.
        belief = {}
    return knowledge, belief


def build_general(
    kind: str,
    agents: List[str],
    worlds: List[str],
    knowledge: Dict[str, Set[Tuple[str, str]]],
    belief: Dict[str, Set[Tuple[str, str]]],
    axiom_d: bool,
    believe_all_when_silent: bool = True,
):
    """Step 1 for any kind: the closed, VALIDATED general model.

    One place decides which constructor each kind uses, so the preview, the
    formula evaluator and the pipeline all build the same object:

        kb         KnowledgeBeliefFrame.from_partial  (S5 + KD45/K45 closures)
        knowledge  RelationalFrame.from_partial_s5    (S5 closure)
        belief     RelationalFrame.from_partial       (KD45/K45 closure; no
                   make_serial: a world that believes nothing is an error
                   under KD45 and a legal defunct belief under K45)

    Raises ``ValueError`` with the core's own message when the closed model
    still violates its logic (e.g. seriality under KD45).
    """
    if kind == "knowledge":
        return RelationalFrame.from_partial_s5(agents, worlds, knowledge)
    if kind == "belief":
        return RelationalFrame.from_partial(agents, worlds, belief, axiom_d=axiom_d)
    return KnowledgeBeliefFrame.from_partial(
        agents, worlds, knowledge, belief, axiom_d=axiom_d,
        believe_all_when_silent=believe_all_when_silent,
    )


def state_from_relational(rel, knowledge_only: bool = False) -> dict:
    """The editor state of the Kripke model ``to_relational`` returns (GitHub #8).

    This closes the loop of the categorical equivalence in the GUI: a complex
    typed by hand becomes a relational document (kind ``knowledge`` when every
    ``S_a`` is the whole complex, ``kb`` otherwise) that the pipeline can take
    back through proper -> simplicial. World names are the facet names turned
    into strings (an action result names facets by ``(world, event)`` pairs);
    the knowledge classes and believed sets are read off the frame exactly as
    the example library reads its models, and the lifted valuation becomes
    the per-atom world lists. Axiom D is the frame's own verdict (KD45 iff no
    perspective was isolated).
    """
    frame = rel.frame
    agents = sorted(frame.agents, key=str)
    # A world name must be a unique string for the editor; str() of a pair is
    # fine, and a clash (two facets whose names print alike) gets a suffix.
    names: Dict = {}
    taken: set = set()
    for w in sorted(frame.worlds, key=str):
        name = str(w)
        while name in taken:
            name += "'"
        names[w], taken = name, taken | {name}
    worlds = [names[w] for w in sorted(frame.worlds, key=str)]
    kind = "knowledge" if knowledge_only else "kb"
    per_agent = {}
    for a in agents:
        rows = editor_rows(frame, a, sorted(frame.worlds, key=str), kind)
        per_agent[a] = [{"cls": [names[w] for w in r["cls"]], "bel": [names[w] for w in r["bel"]]}
                        for r in rows]
    atoms = {str(atom): [names[w] for w in sorted(frame.worlds, key=str) if w in true]
             for atom, true in (rel.valuation or {}).items()}
    state = blank_state(kind)
    state.update({"agents": agents, "worlds": worlds, "per_agent": per_agent,
                  "atoms": atoms, "axiom_d": bool(frame.axiom_d)})
    return state


def parse_names(text: str) -> List[str]:
    """Parse a comma-separated list of identifiers ('a, b, c' -> ['a','b','c'])."""
    return [token.strip() for token in text.split(",") if token.strip()]


def parse_relation(
    text: str,
    agents: List[str],
    worlds: List[str],
    directed: bool,
) -> Dict[str, Set[Tuple[str, str]]]:
    """Parse per-agent edge seeds written one agent per line.

    Format (chosen to be the smallest thing a thesis reader can type):

        a: w0-w1, w1-w2      knowledge -- '-' is undirected, both (x,y),(y,x) added
        b: w0>w1             belief    -- '>' is directed, only (x,y) added

    Why two separators: knowledge relations are symmetric (S5) so forcing the
    user to type both directions would be noise, while for belief the direction
    IS the information (KD45 arrows), so it must be explicit.

    An agent with no line contributes an EMPTY seed (not a missing key): the
    core's ``from_partial`` requires every agent in both mappings whenever any
    belief seed exists, and an explicit empty set is its documented way to say
    "no seed, use the default closure". A fully blank text returns ``{}``,
    which ``from_partial`` reads as case-3 input (knowledge only).

    Raises:
        ValueError: on a malformed line, an unknown agent, or an unknown world,
            with a message naming the offending text (the GUI shows it as-is).
    """
    if not text.strip():
        return {}
    sep = ">" if directed else "-"
    relation: Dict[str, Set[Tuple[str, str]]] = {a: set() for a in agents}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        head, colon, tail = line.partition(":")
        agent = head.strip()
        if not colon or agent not in relation:
            raise ValueError(
                f"invalid line: '{line}' (expected 'agent: pair, pair' "
                f"with agent in {agents})"
            )
        for pair in tail.split(","):
            pair = pair.strip()
            if not pair:
                continue
            left, arrow, right = pair.partition(sep)
            x, y = left.strip(), right.strip()
            if not arrow or x not in worlds or y not in worlds:
                raise ValueError(
                    f"invalid pair for '{agent}': '{pair}' (expected "
                    f"'w{sep}w' with worlds in {worlds})"
                )
            relation[agent].add((x, y))
            if not directed:
                relation[agent].add((y, x))  # symmetry is free for the user
    return relation


def _valuation_of(atoms: Optional[Dict[str, List[str]]]):
    """Editor atoms -> Kripke valuation for the renderers; None when empty.

    ``None`` (not ``{}``) keeps the figures exactly as they were before atoms
    existed -- ``show`` only draws literal labels when a valuation is passed.
    """
    valuation = {a: set(ws) for a, ws in (atoms or {}).items() if ws}
    return valuation or None


def edge_style(explicit_edges: bool) -> dict:
    """``show`` keyword arguments for the GUI's "show implicit edges" switch.

    Off (the default) leaves ``show`` to its inferred style: S5 knowledge is
    drawn undirected and without reflexive loops, because symmetry and
    reflexivity are implied by the logic. On, every edge is drawn as it is in
    the relation: loops on every world and both arrows of a symmetric pair.
    That is the picture of what the closures actually added, which is what
    someone checking a model by hand wants to see.
    """
    if not explicit_edges:
        return {}
    return {"omit_self_loops": False, "undirected_symmetric": False}


def preview_figure(
    agents: List[str],
    worlds: List[str],
    per_agent: Dict[str, List[dict]],
    atoms: Optional[Dict[str, List[str]]] = None,
    explicit_edges: bool = False,
    axiom_d: bool = True,
    kind: str = "kb",
    tag: str = "",
) -> Tuple[Path, List[str]]:
    """Render the model EXACTLY as drawn -- no closures, no validation gate.

    ``kind`` decides the frame and the judge: a pure-knowledge drawing is
    rendered with ``logic="S5"`` so what is missing is measured against the
    S5 closure, and a pure-belief one carries the user's Axiom D so a world
    that believes nothing is red under KD45 and plain under K45.

    ``axiom_d`` is the logic the user declared for belief (KD45 on, K45 off)
    and MUST reach the preview: the violation list and the red dead-end
    worlds both come from the frame's own contract, so under K45 a world
    that believes nothing is legal and is neither listed nor painted.

    This powers the GUI's live preview: on every edit the user sees the frame
    they have entered SO FAR, before asking for the pipeline. Two deliberate
    choices make the preview honest rather than helpful:

        * the model is built with ``validate=False``, so a half-finished (and
          therefore invalid) frame still renders instead of raising;
        * NOTHING is completed -- no S5 closure, no believe-what-you-know
          default. What is missing shows up in the figure itself, because the
          renderer already draws an invalid frame's missing edges dashed in
          red (``highlight_missing``). The red parts are, exactly, what the
          closures will fill in when the pipeline runs.

    Returns:
        ``(path, violations)``: the rendered PNG and the core's own list of
        S5/KD45 violations for the drawn frame (empty when the drawing is
        already a valid model). The GUI shows the list verbatim as "what is
        still missing".

    Raises:
        ValueError: from :func:`seeds_from_editor`, e.g. overlapping classes.
    """
    knowledge, belief = seeds_from_editor(agents, worlds, per_agent, kind)
    valuation = _valuation_of(atoms)
    if kind == "knowledge":
        frame = RelationalFrame(agents, worlds, knowledge, validate=False)
        path = Path(show(frame, _fname("gui_preview", tag), "Model as entered",
                         output_dir=str(OUTPUTS), valuation=valuation,
                         logic="S5", **edge_style(explicit_edges)))
        return path, equivalence_violations(frame)
    if kind == "belief":
        frame = RelationalFrame(agents, worlds, belief, validate=False,
                                axiom_d=axiom_d)
        # Belief has nothing implicit: every loop and every direction is
        # information, so the drawing shows them all whatever the switch.
        path = Path(show(frame, _fname("gui_preview", tag), "Model as entered",
                         output_dir=str(OUTPUTS), valuation=valuation,
                         omit_self_loops=False, undirected_symmetric=False))
        return path, frame.violations()
    kb = KnowledgeBeliefFrame(
        agents, worlds, knowledge, belief, validate=False, axiom_d=axiom_d,
    )
    path = Path(show(kb, _fname("gui_preview", tag), "Model as entered",
                     output_dir=str(OUTPUTS), valuation=valuation,
                     **edge_style(explicit_edges)))
    return path, kb.violations()


# ---------------------------------------------------------------------------
# Per-step diagnostics: what got completed, what is missing, what failed.
# ---------------------------------------------------------------------------
def _fmt_edges(edges, limit: int = 6) -> str:
    """Render an edge set compactly, truncated so a message stays readable."""
    shown = sorted((f"{w}→{u}" for (w, u) in edges))
    head = ", ".join(shown[:limit])
    return head + (f" … (+{len(shown) - limit})" if len(shown) > limit else "")


def diagnose_general_frame(agents, worlds, seed, frame, kind: str) -> StepReport:
    """Step-1 report for a single-relation model (pure knowledge / pure belief).

    Knowledge: what the S5 closure added, and the worlds nobody put in a
    class (singleton classes). Belief: what the 4/5 closure added, and the
    worlds left with no belief at all -- legal defunct beliefs under K45
    (under KD45 the constructor already refused, so they never get here).
    """
    step = StepReport("1 · General model (closures)")
    closure = "S5" if kind == "knowledge" else ("KD45" if frame.axiom_d else "K45")
    what = "knowledge" if kind == "knowledge" else "belief"
    for agent in sorted(agents, key=str):
        added = set(frame.relations[agent]) - set(seed.get(agent, set()))
        if added:
            step.completed.append(
                f"{what} of {agent!r}: the {closure} closure added "
                f"{len(added)} edge(s) — {_fmt_edges(added)}"
            )
    for agent in sorted(agents, key=str):
        if kind == "knowledge":
            singles = [w for w in sorted(worlds, key=str)
                       if frame.successors(agent, w) == {w}]
            if singles:
                step.missing.append(
                    f"{agent!r} distinguishes {len(singles)} world(s) separately "
                    f"({', '.join(map(str, singles))}): they were in no drawn "
                    "class, so they became singleton classes"
                )
        else:
            dead = sorted(frame.dead_ends()[agent], key=str)
            if dead:
                step.missing.append(
                    f"{agent!r} believes nothing at {', '.join(map(str, dead))}: "
                    "under K45 that is a defunct belief (Q = ∅), it believes everything, ⊥ included"
                )
    return step


def diagnose_general(
    agents, worlds, knowledge_seed, belief_seed, kb, believe_all_when_silent,
) -> StepReport:
    """Report what the closures added to the model the user actually drew.

    Two very different things get filled in here and both surprise people:

        * the S5 closure completes each knowledge relation (a drawn pair forces
          reflexivity, symmetry and transitivity across the whole class);
        * a knowledge class with NO belief marked gets the project convention
          Q = R ("believe exactly what you know") -- or, under K45 with the
          opt-in, the defunct cluster Q = ∅.

    Neither is an error, but both mean the model that ran is bigger than the
    drawing, so they are reported as `completed` rather than left silent.
    """
    step = StepReport("1 · General model (closures)")
    for agent in sorted(agents, key=str):
        seeded_k = set(knowledge_seed.get(agent, set()))
        added_k = set(kb.knowledge.relations[agent]) - seeded_k
        if added_k:
            step.completed.append(
                f"knowledge of {agent!r}: the S5 closure added "
                f"{len(added_k)} edge(s) — {_fmt_edges(added_k)}"
            )
        # Which knowledge classes had no belief drawn at all.
        seeded_b = set((belief_seed or {}).get(agent, set()))
        for cls in knowledge_classes(kb.knowledge, agent):
            if any(w in cls for (w, _) in seeded_b):
                continue
            worlds_txt = "{" + ", ".join(sorted(map(str, cls))) + "}"
            if believe_all_when_silent:
                step.completed.append(
                    f"belief of {agent!r} in {worlds_txt}: none was marked, "
                    f"completed with Q = R (believes exactly what it knows)"
                )
            else:
                step.completed.append(
                    f"belief of {agent!r} in {worlds_txt}: none was marked "
                    f"and the K45 opt-in is on, so it was left defunct (Q = ∅)"
                )
    # Worlds nobody put in a class become singleton classes -- easy to miss.
    for agent in sorted(agents, key=str):
        singles = [
            w for w in sorted(worlds, key=str)
            if kb.knowledge.successors(agent, w) == {w}
        ]
        if singles:
            step.missing.append(
                f"{agent!r} distinguishes {len(singles)} world(s) separately "
                f"({', '.join(map(str, singles))}): they were in no drawn "
                f"class, so they became singleton classes"
            )
    return step


def diagnose_proper(kb, proper) -> StepReport:
    """Report whether copies were needed, and which agent was skewed and why."""
    step = StepReport("2 · Proper model (copies + skew)")
    if not proper.projection or len(proper.worlds) == len(kb.worlds):
        step.completed.append(
            "the model was already proper: nothing needed copying"
        )
        return step
    copies = len(proper.worlds) // max(len(kb.worlds), 1)
    # A KnowledgeBeliefFrame carries two relation families, a plain S5
    # frame one; the skew cost is computed over whatever the model has.
    families = (
        (kb.knowledge.relations, kb.belief.relations)
        if isinstance(kb, KnowledgeBeliefFrame) else (kb.relations,)
    )
    cheapest = cheapest_distinguished_agent(*families, agents=kb.agents)
    step.completed.append(
        f"it was not proper: {copies} copies were created "
        f"({len(kb.worlds)} → {len(proper.worlds)} worlds), bisimilar to the original"
    )
    step.completed.append(
        f"distinguished agent {cheapest!r}: it has the fewest non-reflexive edges, "
        f"so fewer edges cross between copies and the figure stays cleaner"
    )
    return step


def diagnose_simplicial(proper, sm, valuation) -> StepReport:
    """Report the translation's shape, and where a valuation is not representable."""
    step = StepReport("3 · Simplicial model (worlds → facets)")
    step.completed.append(
        f"each world became a facet: {len(proper.worlds)} worlds → "
        f"{len(sm.facets)} facets, {len(sm.nodes)} nodes"
    )
    if not valuation:
        step.missing.append(
            "no atoms declared: the figures label neither worlds nor vertices, "
            "and the formula evaluator is disabled"
        )
        return step
    # NU: an atom true at a world that NO perspective observes is not
    # representable in the vertex-based semantics -- the one real gap here.
    assignment = assignment_from_model(sm, valuation)
    gaps = nu_violations(sm, assignment, valuation)
    # One line per ATOM, listing its worlds: the same sentence repeated once
    # per world (six times for the thesis example) buried the one fact that
    # matters -- which atom is unobserved, and where.
    by_atom: Dict[str, List[str]] = {}
    for atom, facet in gaps:
        world = sm.world_of_facet.get(facet, facet)
        by_atom.setdefault(str(atom), []).append(
            "(" + ", ".join(map(str, world)) + ")" if isinstance(world, tuple) else str(world)
        )
    for atom, worlds in by_atom.items():
        shown = ", ".join(worlds[:8]) + (f" … (+{len(worlds) - 8})" if len(worlds) > 8 else "")
        step.missing.append(
            f"atom {atom!r} is true at {len(worlds)} world(s) where no "
            f"agent observes it ({shown}): the NU schema (P → ∨_a B_a P) fails there, "
            f"so that truth is not representable in the vertex-based semantics"
        )
    return step


def run_pipeline(
    agents_text: str,
    worlds_text: str,
    knowledge_text: str,
    belief_text: str,
    axiom_d: bool,
) -> PipelineResult:
    """Text-input variant: parse the seed format, then run the pipeline.

    Kept as the head of the original text-based flow (and as the headless way
    to exercise the bridge); the GUI's visual editor goes through
    :func:`seeds_from_editor` + :func:`run_pipeline_from_seeds` instead.
    """
    agents = parse_names(agents_text)
    worlds = parse_names(worlds_text)
    knowledge = parse_relation(knowledge_text, agents, worlds, directed=False)
    belief = parse_relation(belief_text, agents, worlds, directed=True)
    return run_pipeline_from_seeds(agents, worlds, knowledge, belief, axiom_d)


def run_pipeline_from_seeds(
    agents: List[str],
    worlds: List[str],
    knowledge: Dict[str, Set[Tuple[str, str]]],
    belief: Dict[str, Set[Tuple[str, str]]],
    axiom_d: bool,
    atoms: Optional[Dict[str, List[str]]] = None,
    believe_all_when_silent: bool = True,
    explicit_edges: bool = False,
    kind: str = "kb",
    tag: str = "",
    hasse_full: bool = False,
    make_3d: bool = True,
) -> PipelineResult:
    """Run the full thesis pipeline (general -> proper -> simplicial) once.

    ``kind`` (see ``KINDS``) selects the model. Pure knowledge runs the whole
    chain (S5 is what properness and the translation need). Pure belief
    stops after step 1 with steps 2 and 3 reported as "not applicable": there
    is no KD45 -> S5 conversion, a belief-only model has no simplicial
    translation, and the GUI says so instead of failing.

    When ``atoms`` are given, the valuation travels WITH the models the same
    way the thesis carries it: as-is on the general model, lifted through the
    properness projection (``semantics.lift_valuation``, each copy inherits
    its original's atoms) for the proper and simplicial figures -- so every
    figure shows its worlds/vertices labelled with their literals.

    This is the ONLY function the GUI needs, mirroring the core's own story:

        1. build the general model  (KnowledgeBeliefFrame.from_partial)
        2. make it proper           (.to_proper -- copies + skew, bisimilar)
        3. translate                (to_simplicial -- worlds become facets)

    Validation errors (S5/KD45/properness violations) are raised as
    ``ValueError`` with the core's own explanatory messages; the GUI surfaces
    them verbatim because they are the pedagogic content, not noise.

    Args:
        agents, worlds: identifier lists (already parsed).
        knowledge, belief: per-agent edge seeds for ``from_partial``.
        axiom_d: True = KD45 belief, False = K45 (defunct beliefs allowed);
            fixed here once and carried by the model through the pipeline.
        explicit_edges: draw reflexive loops and both directions of symmetric
            pairs in the relational figures (see :func:`edge_style`).
        believe_all_when_silent: what a knowledge class with NO belief marked
            means. True (the project convention) = "believe exactly what you
            know", Q = R there. False = the defunct cluster Q = ∅, which only
            K45 legalises -- so it needs ``axiom_d=False`` as well. Turning off
            Axiom D alone only PERMITS defunct belief; this is what produces it.
        hasse_full: draw every face in Fig. 4 instead of the default
            vertices-and-facets view (GitHub #7).
    """
    if not agents or not worlds:
        raise ValueError("at least one agent and one world are needed")

    valuation = _valuation_of(atoms)
    result = PipelineResult()

    # -- Step 1: the general model (closures fill in S5 / belief-in-class). --
    # Each step is wrapped: a refusal is recorded as the step's `failed` and the
    # run STOPS there, keeping whatever earlier steps already produced. That is
    # the point -- the user sees how far the translation got and what blocked it,
    # instead of an all-or-nothing error.
    try:
        kb = build_general(kind, agents, worlds, knowledge, belief, axiom_d,
                           believe_all_when_silent)
    except ValueError as exc:
        step = StepReport("1 · General model (closures)")
        step.failed.append(str(exc))
        result.steps.append(step)
        result.badges.append(("rejected at step 1", "negative"))
        return result
    if kind == "kb":
        result.steps.append(diagnose_general(
            agents, worlds, knowledge, belief, kb, believe_all_when_silent
        ))
        logic = "KD45" if axiom_d else "K45"
        proper_now = kb.is_proper()
        fig1_caption = "Fig. 1 · general model (knowledge thin, belief thick)"
        fig1_style = edge_style(explicit_edges)
    elif kind == "knowledge":
        result.steps.append(diagnose_general_frame(agents, worlds, knowledge, kb, kind))
        logic = "S5"
        proper_now = frame_is_proper(kb)
        fig1_caption = "Fig. 1 · general knowledge model (S5)"
        fig1_style = edge_style(explicit_edges)
    else:
        result.steps.append(diagnose_general_frame(agents, worlds, belief, kb, kind))
        logic = "KD45" if axiom_d else "K45"
        proper_now = False  # properness is a knowledge notion
        fig1_caption = f"Fig. 1 · general belief model ({logic})"
        fig1_style = {"omit_self_loops": False, "undirected_symmetric": False}
    result.log.append(
        f"General model: {len(kb.worlds)} worlds, valid: {kb.is_valid()}, "
        f"proper: {proper_now}, logic: {logic}"
    )
    result.badges.append(
        ("valid", "positive") if kb.is_valid() else ("invalid", "negative")
    )
    result.badges.append((logic, "primary"))
    result.stats.append((str(len(kb.worlds)), "worlds · general"))
    result.figures.append((
        fig1_caption,
        Path(show(kb, _fname("gui_fig1_general", tag), "General model",
                  output_dir=str(OUTPUTS), valuation=valuation, **fig1_style)),
    ))
    result.text_diagrams.append(("General model", visualize(kb)))

    if kind == "belief":
        # No KD45 -> S5 conversion exists (examples3.py makes the point): a
        # pure-belief model has no proper form and no simplicial translation.
        why = ("properness and the simplicial translation need S5 "
               "knowledge; a belief-only model ends at step 1. To "
               "translate it, switch to “knowledge and belief” and give the classes")
        for name in ("2 · Proper model (copies + skew)",
                     "3 · Simplicial model (worlds → facets)"):
            step = StepReport(name)
            step.skipped.append(why)
            result.steps.append(step)
        return result

    # -- Step 2: properness (copies + skewed distinguished agent). ----------
    try:
        proper = kb.to_proper() if kind == "kb" else frame_to_proper(kb)
    except ValueError as exc:
        step = StepReport("2 · Proper model (copies + skew)")
        step.failed.append(str(exc))
        result.steps.append(step)
        result.badges.append(("rejected at step 2", "negative"))
        return result
    result.steps.append(diagnose_proper(kb, proper))
    proper_ok = proper.is_proper() if kind == "kb" else frame_is_proper(proper)
    result.log.append(
        f"to_proper → {len(proper.worlds)} worlds, proper: {proper_ok}"
    )
    if proper_ok:
        result.badges.append(("proper", "positive"))
    result.stats.append((str(len(proper.worlds)), "worlds · proper"))
    # The valuation follows the worlds: each copy inherits its original's
    # atoms via the projection ρ (thesis p. 13). An already-proper model comes
    # back with an empty projection, meaning the worlds did not change.
    lifted = (
        lift_valuation(valuation, proper.projection)
        if valuation and proper.projection else valuation
    )
    if kind == "kb":
        # The two relations are rendered separately (same convention as
        # thesis_example.py): knowledge undirected S5, belief with KD45 arrows.
        result.figures.append((
            "Fig. 2a · proper model, knowledge R_a (S5)",
            Path(show(proper.knowledge, _fname("gui_fig2_knowledge", tag),
                      "Proper · knowledge R_a", output_dir=str(OUTPUTS),
                      valuation=lifted, **edge_style(explicit_edges))),
        ))
        result.figures.append((
            "Fig. 2b · proper model, belief Q_a (KD45)",
            Path(show(proper.belief, _fname("gui_fig2_belief", tag), "Proper · belief Q_a",
                      omit_self_loops=not explicit_edges, output_dir=str(OUTPUTS),
                      valuation=lifted)),
        ))
    else:
        result.figures.append((
            "Fig. 2 · proper knowledge model R_a (S5)",
            Path(show(proper, _fname("gui_fig2_knowledge", tag), "Proper · knowledge R_a",
                      output_dir=str(OUTPUTS), valuation=lifted,
                      **edge_style(explicit_edges))),
        ))
    result.text_diagrams.append(("Proper model", visualize(proper)))

    # -- Step 3: the simplicial belief model. --------------------------------
    try:
        sm = to_simplicial(proper)
    except ValueError as exc:
        step = StepReport("3 · Simplicial model (worlds → facets)")
        step.failed.append(str(exc))
        result.steps.append(step)
        result.badges.append(("rejected at step 3", "negative"))
        return result
    # `lifted`, NOT `valuation`: sm is built from the PROPER model, whose worlds
    # are copies (w, u). Comparing against the original world names would never
    # match and NU violations would go silently undetected.
    result.steps.append(diagnose_simplicial(proper, sm, lifted))
    geometric = _geometric_ok(sm)
    if not geometric:
        result.steps[-1].missing.append(_dimension_note(sm))
    sizes = ", ".join(f"S_{a}={len(sm.belief_facets[a])}" for a in sorted(sm.agents))
    result.log.append(
        f"to_simplicial → {len(sm.facets)} facets; belief subcomplexes: {sizes}"
    )
    result.stats.append((str(len(sm.facets)), "facets"))
    for a in sorted(sm.agents, key=str):
        result.stats.append((str(len(sm.belief_facets[a])), f"S_{a}"))
    result.figures.append((
        "Fig. 3 · simplicial belief model" if geometric else
        "Fig. 3 · simplicial belief model, as an incidence diagram (each facet "
        "is a point joined to its vertices: with 5 or more agents there is no faithful geometric drawing)",
        Path(show(sm, _fname("gui_fig3_simplicial", tag), "Simplicial model",
                  output_dir=str(OUTPUTS), valuation=lifted,
                  engine="auto" if geometric else "dot")),
    ))
    # The heavy output (see run_simplicial); also skipped for 5+ agents, whose
    # facets have no faithful 3-D drawing.
    if make_3d and geometric:
        result.html_3d = Path(show(sm, _fname("gui_fig3_3d", tag), "Simplicial model · 3D",
                                   dim=3, output_dir=str(OUTPUTS),
                                   valuation=lifted))
    result.text_diagrams.append(("Simplicial model", str(sm)))

    # -- Fig. 4: the face lattice (Hasse diagram) of the complex. -------------
    # The combinatorial reading of Fig. 3: which simplices exist and which is a
    # face of which; facet boxes carry the SAME world names Fig. 3 prints at
    # the centroids, so the two figures can be read together. The empty face
    # is left out (noise for this purpose). By default only the vertex and
    # facet rows are drawn (GitHub #7): with three agents the full lattice is
    # already hundreds of boxes, and the belief reading only needs "which
    # perspectives make up which world". Always the textbook bottom-up
    # drawing (rankdir=BT): hasse.py suggests columns (LR) for wide middle
    # rows when the file is viewed on its own, but in the GUI the figure sits
    # in a wide column with a height cap, so a wide-and-low picture is the one
    # that stays readable; the LR variant became a tall, unreadable strip.
    lattice = hasse.face_lattice(sm, include_empty=False, assignment=lifted)
    result.figures.append((
        _hasse_caption("Fig. 4", hasse_full),
        Path(hasse.show(lattice, _fname("gui_fig4_hasse", tag), "Face lattice",
                        output_dir=str(OUTPUTS), rankdir="BT",
                        facets_and_vertices=not hasse_full, image_format=FIGURE_FORMAT)),
    ))
    result.text_diagrams.append(("Face lattice", hasse.visualize(lattice)))

    return result

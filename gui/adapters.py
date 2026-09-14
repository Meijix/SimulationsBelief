"""Bridge between the GUI and the core modules: parse text -> run pipeline -> render.

WHY THIS FILE EXISTS. The GUI is split in two layers on purpose:

    gui/app.py      -- presentation only (NiceGUI widgets, layout, notifications)
    gui/adapters.py -- everything else: parsing the user's text into the core's
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
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# The GUI lives in its own subfolder but calls the flat modules at the repo
# root. Putting the root on sys.path here -- instead of packaging the project
# or moving files -- keeps the core completely untouched and makes
# ``python gui/app.py`` work no matter the current directory.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge_belief import KnowledgeBeliefFrame  # noqa: E402
from semantics import holds_kripke, lift_valuation  # noqa: E402
from simplicial import to_simplicial  # noqa: E402
from visualization import show, visualize  # noqa: E402

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

# ---------------------------------------------------------------------------
# Example library. Each entry is a COMPLETE editor state (agents, worlds,
# classes/beliefs, atoms, belief logic), so loading one is a plain state
# swap in the GUI -- no special-casing per example. They mirror scripts that
# already live in the repo, so the GUI doubles as a browsable gallery of them.
# 'atoms' is the Kripke valuation v : P -> worlds where the atom is TRUE; the
# figures label worlds/vertices with their literals when atoms are present.
# ---------------------------------------------------------------------------
_NASA_W = ["TTT", "TTX", "TXT", "TXX", "XTT", "XTX", "XXT", "XXX"]
EXAMPLES = {
    "tesis": {
        "label": "Tesis · Figuras 1 → 3",
        "agents": ["a", "b", "c"],
        "worlds": ["w0", "w1", "w2"],
        "per_agent": DEFAULT_EDITOR,
        # p vale donde ALGUIEN se atreve a creer: B_a p vale pero K_a p no --
        # el contraste conocimiento/creencia en una sola formula.
        "atoms": {"p": ["w1", "w2"]},
        "axiom_d": True,
    },
    "nasa": {
        # ejemplo_nasa.py: tres unidades leen un tramo (T/X); cada una conoce
        # SU lectura (clase = mundos que coinciden en su posicion) y cree que
        # las otras leen lo mismo (el mundo unanime de su letra).
        "label": "Coloquio · red de auxilio (octaedro)",
        "agents": ["a", "b", "c"],
        "worlds": list(_NASA_W),
        "per_agent": {
            g: [
                {"cls": [w for w in _NASA_W if w[i] == letra],
                 "bel": [letra * 3]}
                for letra in "TX"
            ]
            for i, g in enumerate("abc")
        },
        # Tg = "la unidad g lee Transitable" (atomo por unidad).
        "atoms": {f"T{g}": [w for w in _NASA_W if w[i] == "T"]
                  for i, g in enumerate("abc")},
        "axiom_d": True,
    },
    "moneda": {
        # El caso minimo de dos agentes: a ya vio la moneda (clases unitarias,
        # dejadas implicitas), b no la distingue y cree que salio cara.
        "label": "Moneda · a sabe, b cree",
        "agents": ["a", "b"],
        "worlds": ["cara", "cruz"],
        "per_agent": {
            "a": [],  # sin clases dibujadas = clases unitarias (a distingue todo)
            "b": [{"cls": ["cara", "cruz"], "bel": ["cara"]}],
        },
        "atoms": {"c": ["cara"]},
        "axiom_d": True,
    },
}


def seeds_from_editor(
    agents: List[str],
    worlds: List[str],
    per_agent: Dict[str, List[dict]],
) -> Tuple[Dict[str, Set[Tuple[str, str]]], Dict[str, Set[Tuple[str, str]]]]:
    """Turn the visual editor's classes/beliefs into ``from_partial`` seeds.

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
            bel = [w for w in row["bel"] if w in cls]
            overlap = seen & set(cls)
            if overlap:
                raise ValueError(
                    f"el agente '{agent}' tiene {sorted(overlap)} en dos clases "
                    "distintas; las clases de conocimiento deben ser disjuntas "
                    "(la clausura S5 las fusionaría en silencio)"
                )
            seen |= set(cls)
            knowledge[agent] |= {(x, y) for x in cls for y in cls}
            belief[agent] |= {(x, b) for x in cls for b in bel}
    # No believed world anywhere -> case-3 input for from_partial (knowledge
    # only, Q_a defaults to R_a), signalled by an EMPTY mapping, not empty sets.
    if not any(belief.values()):
        belief = {}
    return knowledge, belief


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
                f"línea inválida: '{line}' (esperaba 'agente: par, par' "
                f"con agente en {agents})"
            )
        for pair in tail.split(","):
            pair = pair.strip()
            if not pair:
                continue
            left, arrow, right = pair.partition(sep)
            x, y = left.strip(), right.strip()
            if not arrow or x not in worlds or y not in worlds:
                raise ValueError(
                    f"par inválido para '{agent}': '{pair}' (esperaba "
                    f"'w{sep}w' con mundos en {worlds})"
                )
            relation[agent].add((x, y))
            if not directed:
                relation[agent].add((y, x))  # symmetry is free for the user
    return relation


# ---------------------------------------------------------------------------
# Formula parsing + evaluation (the GUI's window into semantics.py).
#
# semantics.py deliberately keeps formulas as plain tuples ("K", "a", ...);
# the GUI needs a human syntax on top. The grammar is the smallest one that
# covers the thesis language L_KB, with ASCII and unicode spellings:
#
#     formula := or  ( '->' formula )?              implication, right-assoc
#     or      := and ( ('|'|'∨') and )*
#     and     := unary ( ('&'|'∧') unary )*
#     unary   := ('~'|'!'|'¬') unary
#              | K_<agente> unary | B_<agente> unary
#              | '(' formula ')' | 'bot' | '⊥' | <atomo>
#
# Modal operators bind like negation (K_a p & q  ==  (K_a p) & q), which is
# the convention the thesis uses when dropping parentheses.
# ---------------------------------------------------------------------------
_TOKEN = re.compile(
    r"\s*(?:"
    r"(?P<modal>[KB]_[A-Za-z0-9]+)"
    r"|(?P<imp>->|→)"
    r"|(?P<sym>[()&|~!¬⊥∧∨])"
    r"|(?P<name>[A-Za-z][A-Za-z0-9_]*)"
    r")"
)


def parse_formula(text: str, agents: List[str], atoms: List[str]):
    """Parse the human syntax above into semantics.py's tuple formulas.

    Both agent names (in ``K_a``/``B_a``) and atom names are validated against
    what the editor declares, so a typo fails HERE with a list of the valid
    names instead of silently evaluating to false at every world (the failure
    mode of an unknown atom in ``holds_kripke``).
    """
    tokens: List[str] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or not m.group().strip():
            rest = text[pos:].strip()
            if not rest:
                break
            raise ValueError(f"símbolo no reconocido en la fórmula: '{rest[:10]}'")
        tokens.append(m.group().strip())
        pos = m.end()
    if not tokens:
        raise ValueError("escribe una fórmula, p. ej.  B_a p & ~K_a p")
    tokens.append("<fin>")  # centinela: evita chequear el final en cada paso
    i = 0  # cursor compartido por los parsers anidados (descenso recursivo)

    def peek() -> str:
        return tokens[i]

    def eat() -> str:
        nonlocal i
        tok = tokens[i]
        i += 1
        return tok

    def parse_imp():
        left = parse_or()
        if peek() in ("->", "→"):
            eat()
            return ("imp", left, parse_imp())  # a -> b -> c == a -> (b -> c)
        return left

    def parse_or():
        node = parse_and()
        while peek() in ("|", "∨"):
            eat()
            node = ("or", node, parse_and())
        return node

    def parse_and():
        node = parse_unary()
        while peek() in ("&", "∧"):
            eat()
            node = ("and", node, parse_unary())
        return node

    def parse_unary():
        tok = eat()
        if tok in ("~", "!", "¬"):
            return ("not", parse_unary())
        if len(tok) > 2 and tok[0] in "KB" and tok[1] == "_":
            agent = tok[2:]
            if agent not in agents:
                raise ValueError(
                    f"'{tok}': el agente '{agent}' no existe (hay: {agents})"
                )
            return (tok[0], agent, parse_unary())
        if tok == "(":
            node = parse_imp()
            if eat() != ")":
                raise ValueError("falta un paréntesis de cierre ')'")
            return node
        if tok in ("bot", "⊥"):
            return ("bot",)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", tok):
            if tok not in atoms:
                raise ValueError(
                    f"el átomo '{tok}' no está declarado (hay: {sorted(atoms)}); "
                    "agrégalo en la sección Átomos"
                )
            return ("atom", tok)
        raise ValueError(f"no esperaba '{tok}' en la fórmula")

    node = parse_imp()
    if peek() != "<fin>":
        raise ValueError(f"la fórmula termina pero sobra: '{peek()}'")
    return node


def evaluate_formula(
    agents: List[str],
    worlds: List[str],
    per_agent: Dict[str, List[dict]],
    atoms: Dict[str, List[str]],
    axiom_d: bool,
    text: str,
) -> List[Tuple[str, bool]]:
    """Evaluate a formula at EVERY world of the drawn model (Kripke side).

    The model is completed with the same closures the pipeline uses
    (``from_partial``), so the answer refers to the model the pipeline would
    build -- not to the raw half-drawn seeds. Evaluating on the Kripke side is
    canonical here: thesis Lemma 2.6 guarantees the simplicial side agrees
    facet by facet, so one evaluator is enough for the GUI.

    Returns:
        ``[(world, holds?)]`` in sorted world order.

    Raises:
        ValueError: parse errors, undeclared atoms/agents, or an invalid model.
    """
    formula = parse_formula(text, agents, list(atoms))
    knowledge, belief = seeds_from_editor(agents, worlds, per_agent)
    kb = KnowledgeBeliefFrame.from_partial(
        agents, worlds, knowledge, belief, axiom_d=axiom_d
    )
    valuation = {atom: set(ws) for atom, ws in atoms.items()}
    return [
        (w, holds_kripke(kb, valuation, w, formula))
        for w in sorted(worlds, key=str)
    ]


def _valuation_of(atoms: Optional[Dict[str, List[str]]]):
    """Editor atoms -> Kripke valuation for the renderers; None when empty.

    ``None`` (not ``{}``) keeps the figures exactly as they were before atoms
    existed -- ``show`` only draws literal labels when a valuation is passed.
    """
    valuation = {a: set(ws) for a, ws in (atoms or {}).items() if ws}
    return valuation or None


def preview_figure(
    agents: List[str],
    worlds: List[str],
    per_agent: Dict[str, List[dict]],
    atoms: Optional[Dict[str, List[str]]] = None,
) -> Tuple[Path, List[str]]:
    """Render the model EXACTLY as drawn -- no closures, no validation gate.

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
    knowledge, belief = seeds_from_editor(agents, worlds, per_agent)
    kb = KnowledgeBeliefFrame(
        agents, worlds, knowledge, belief, validate=False
    )
    path = Path(show(kb, "gui_preview", "Modelo tal como se ingresa",
                     output_dir=str(OUTPUTS), valuation=_valuation_of(atoms)))
    return path, kb.violations()


@dataclass
class PipelineResult:
    """Everything the page needs to display one run, already flattened.

    The GUI never touches the model objects; it gets file paths and strings.
    That keeps the presentation layer dumb -- if tomorrow the figures came from
    a different renderer, ``app.py`` would not change a line.
    """

    log: List[str] = field(default_factory=list)
    # (caption, absolute path to the PNG) in pipeline order.
    figures: List[Tuple[str, Path]] = field(default_factory=list)
    # Interactive 3-D plotly page for the simplicial model (an .html file).
    html_3d: Path | None = None
    # (caption, ASCII diagram) -- the zero-dependency view of each model.
    text_diagrams: List[Tuple[str, str]] = field(default_factory=list)


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
) -> PipelineResult:
    """Run the full thesis pipeline (general -> proper -> simplicial) once.

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
    """
    if not agents or not worlds:
        raise ValueError("se necesita al menos un agente y un mundo")

    valuation = _valuation_of(atoms)
    result = PipelineResult()

    # -- Step 1: the general model (closures fill in S5 / belief-in-class). --
    kb = KnowledgeBeliefFrame.from_partial(
        agents, worlds, knowledge, belief, axiom_d=axiom_d
    )
    result.log.append(
        f"Modelo general: {len(kb.worlds)} mundos, válido: {kb.is_valid()}, "
        f"propio: {kb.is_proper()}, lógica de creencia: "
        f"{'KD45' if axiom_d else 'K45'}"
    )
    result.figures.append((
        "Fig. 1 · modelo general (conocimiento delgado, creencia gruesa)",
        Path(show(kb, "gui_fig1_general", "Modelo general",
                  output_dir=str(OUTPUTS), valuation=valuation)),
    ))
    result.text_diagrams.append(("Modelo general", visualize(kb)))

    # -- Step 2: properness (copies + skewed distinguished agent). ----------
    proper = kb.to_proper()
    result.log.append(
        f"to_proper → {len(proper.worlds)} mundos, propio: {proper.is_proper()}"
    )
    # The valuation follows the worlds: each copy inherits its original's
    # atoms via the projection ρ (thesis p. 13). An already-proper model comes
    # back with an empty projection, meaning the worlds did not change.
    lifted = (
        lift_valuation(valuation, proper.projection)
        if valuation and proper.projection else valuation
    )
    # The two relations are rendered separately (same convention as
    # thesis_example.py): knowledge undirected S5, belief with KD45 arrows.
    result.figures.append((
        "Fig. 2a · modelo propio, conocimiento R_a (S5)",
        Path(show(proper.knowledge, "gui_fig2_knowledge",
                  "Propio · conocimiento R_a", output_dir=str(OUTPUTS),
                  valuation=lifted)),
    ))
    result.figures.append((
        "Fig. 2b · modelo propio, creencia Q_a (KD45)",
        Path(show(proper.belief, "gui_fig2_belief", "Propio · creencia Q_a",
                  omit_self_loops=True, output_dir=str(OUTPUTS),
                  valuation=lifted)),
    ))
    result.text_diagrams.append(("Modelo propio", visualize(proper)))

    # -- Step 3: the simplicial belief model. --------------------------------
    sm = to_simplicial(proper)
    sizes = ", ".join(f"S_{a}={len(sm.belief_facets[a])}" for a in sorted(sm.agents))
    result.log.append(
        f"to_simplicial → {len(sm.facets)} facetas; subcomplejos de creencia: {sizes}"
    )
    result.figures.append((
        "Fig. 3 · modelo simplicial de creencia",
        Path(show(sm, "gui_fig3_simplicial", "Modelo simplicial",
                  output_dir=str(OUTPUTS), valuation=lifted)),
    ))
    result.html_3d = Path(show(sm, "gui_fig3_3d", "Modelo simplicial · 3D",
                               dim=3, output_dir=str(OUTPUTS),
                               valuation=lifted))
    result.text_diagrams.append(("Modelo simplicial", str(sm)))

    return result

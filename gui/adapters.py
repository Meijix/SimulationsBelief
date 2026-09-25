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

from assignment import assignment_from_model, nu_violations  # noqa: E402
from knowledge_belief import KnowledgeBeliefFrame, knowledge_classes  # noqa: E402
from properness import (  # noqa: E402
    cheapest_distinguished_agent,
    equivalence_violations,
    is_proper as frame_is_proper,
    to_proper as frame_to_proper,
)
from relational_frame import RelationalFrame  # noqa: E402
from semantics import holds_kripke, lift_valuation  # noqa: E402
from simplicial import to_simplicial  # noqa: E402
from visualization import PALETTE, show, visualize  # noqa: E402
import hasse  # noqa: E402  -- retículo de caras (Fig. 4)


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

# ---------------------------------------------------------------------------
# Example library. Each entry is a COMPLETE editor state (agents, worlds,
# classes/beliefs, atoms, belief logic), so loading one is a plain state
# swap in the GUI -- no special-casing per example. They mirror scripts that
# already live in the repo, so the GUI doubles as a browsable gallery of them.
# 'atoms' is the Kripke valuation v : P -> worlds where the atom is TRUE; the
# figures label worlds/vertices with their literals when atoms are present.
# ---------------------------------------------------------------------------
_NASA_W = ["TTT", "TTX", "TXT", "TXX", "XTT", "XTX", "XXT", "XXX"]

# Los tres TIPOS DE MODELO que el núcleo sabe construir, tal como los expone
# la GUI. La clave viaja por todo el adaptador (``kind``) y decide qué marco
# se construye, qué axiomas se comprueban y hasta dónde llega el pipeline:
#
#   kb         KnowledgeBeliefFrame: conocimiento S5 + creencia KD45/K45, y
#              el pipeline completo (propio -> simplicial -> Hasse).
#   knowledge  RelationalFrame S5 (sólo conocimiento). Las filas del editor
#              son clases; no hay creencia. Propio y simplicial funcionan
#              (todo el complejo es el subcomplejo de creencia de cada uno).
#   belief     RelationalFrame KD45/K45 (sólo creencia). Cada fila es "desde
#              estos mundos se creen aquellos"; no hay clases. La propiedad y
#              la traducción simplicial NECESITAN S5, así que el pipeline
#              termina en el paso 1 y lo dice.
KINDS = {
    "kb": "Conocimiento y creencia",
    "knowledge": "Sólo conocimiento (S5)",
    "belief": "Sólo creencia (KD45 / K45)",
}

# Niños embarrados con dos niños: un mundo por reparto de barro, y cada niño
# no distingue los dos mundos que sólo difieren en SU propio estado.
_MUDDY_W = ["limpios", "a", "b", "ab"]
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
    "ninos": {
        # examples.py (muddy children), como modelo de PURO CONOCIMIENTO:
        # sin creencia que dibujar, el pipeline hace propio + simplicial con
        # S_a = S para todos.
        "label": "Niños embarrados · sólo conocimiento",
        "kind": "knowledge",
        "agents": ["a", "b"],
        "worlds": list(_MUDDY_W),
        "per_agent": {
            "a": [{"cls": ["limpios", "a"], "bel": []},
                  {"cls": ["b", "ab"], "bel": []}],
            "b": [{"cls": ["limpios", "b"], "bel": []},
                  {"cls": ["a", "ab"], "bel": []}],
        },
        "atoms": {"Ma": ["a", "ab"], "Mb": ["b", "ab"]},
        "axiom_d": True,
    },
    "clima": {
        # examples2.py (el clima de mañana), como modelo de PURA CREENCIA: cada
        # fila dice desde qué mundos se creen cuáles; la clausura KD45 añade
        # lo que transitividad y euclideanidad exigen. Los lazos en "nube" y
        # "sol" hacen el papel del make_serial=True del script.
        "label": "Clima de mañana · sólo creencia",
        "kind": "belief",
        "agents": ["alicia", "beto"],
        "worlds": ["lluvia", "nube", "sol"],
        "per_agent": {
            "alicia": [{"cls": ["lluvia"], "bel": ["nube"]},
                       {"cls": ["sol"], "bel": ["lluvia"]},
                       {"cls": ["nube"], "bel": ["nube"]}],
            "beto": [{"cls": ["lluvia", "nube"], "bel": ["sol"]},
                     {"cls": ["sol"], "bel": ["sol"]}],
        },
        "atoms": {"llueve": ["lluvia"]},
        "axiom_d": True,
    },
}


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
                    f"el agente '{agent}' tiene {sorted(overlap)} en dos filas "
                    "distintas; "
                    + ("cada mundo lleva UN solo conjunto de mundos creídos"
                       if kind == "belief" else
                       "las clases de conocimiento deben ser disjuntas "
                       "(la clausura S5 las fusionaría en silencio)")
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
# An atom is any alphanumeric name, INCLUDING one that starts with a digit
# ("1", "42", "3p"): the thesis writes atoms as bare numerals in several
# examples, and nothing in the grammar competes for a numeral, so there is no
# reason to reserve leading digits. Requiring a letter first was a bug -- "1"
# then matched no alternative at all and the tokenizer reported the whole rest
# of the formula as one unrecognised symbol.
_ATOM = r"[A-Za-z0-9][A-Za-z0-9_]*"

_TOKEN = re.compile(
    r"\s*(?:"
    r"(?P<modal>[KB]_[A-Za-z0-9]+)"
    r"|(?P<imp>->|→)"
    r"|(?P<sym>[()&|~!¬⊥∧∨])"
    r"|(?P<name>" + _ATOM + r")"
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
                # `[KB]_[A-Za-z0-9]+` is greedy, so "K_a1" swallows the digit and
                # asks for an agent "a1". Now that atoms may start with a digit
                # that is genuinely ambiguous, so back off to the longest prefix
                # that IS a declared agent with a declared atom left over, and
                # push that atom back into the stream: "K_a1" -> K_a applied to 1.
                # Longest-first keeps a real agent "a1" winning over "a" + "1".
                for cut in range(len(agent) - 1, 0, -1):
                    if agent[:cut] in agents and agent[cut:] in atoms:
                        tokens.insert(i, agent[cut:])
                        agent = agent[:cut]
                        break
                else:
                    raise ValueError(
                        f"'{tok}': el agente '{agent}' no existe (hay: {agents}); "
                        f"si querías aplicar un modal a un átomo, sepáralos con un "
                        f"espacio, p. ej. 'K_a 1'"
                    )
            return (tok[0], agent, parse_unary())
        if tok == "(":
            node = parse_imp()
            if eat() != ")":
                raise ValueError("falta un paréntesis de cierre ')'")
            return node
        if tok in ("bot", "⊥"):
            return ("bot",)
        if re.fullmatch(_ATOM, tok):
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
    believe_all_when_silent: bool = True,
    kind: str = "kb",
) -> List[Tuple[str, bool]]:
    """Evaluate a formula at EVERY world of the drawn model (Kripke side).

    ``kind`` picks the model (see :func:`build_general`); the core then says
    which operator fits: ``K_a`` on a pure-belief frame or ``B_a`` on a
    pure-knowledge one is refused with its own message.

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
    knowledge, belief = seeds_from_editor(agents, worlds, per_agent, kind)
    kb = build_general(kind, agents, worlds, knowledge, belief, axiom_d,
                       believe_all_when_silent)
    if kind == "knowledge" and _uses(formula, "B"):
        raise ValueError("un modelo de sólo conocimiento no tiene creencia: "
                         "usa K_a en lugar de B_a")
    if kind == "belief" and _uses(formula, "K"):
        raise ValueError("un modelo de sólo creencia no tiene conocimiento: "
                         "usa B_a en lugar de K_a")
    valuation = {atom: set(ws) for atom, ws in atoms.items()}
    return [
        (w, holds_kripke(kb, valuation, w, formula))
        for w in sorted(worlds, key=str)
    ]


def _uses(formula, tag: str) -> bool:
    """Does the tuple formula contain a connective ``tag`` (``"K"``/``"B"``)?"""
    if not isinstance(formula, tuple):
        return False
    return formula[0] == tag or any(_uses(part, tag) for part in formula[1:])


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
        path = Path(show(frame, "gui_preview", "Modelo tal como se ingresa",
                         output_dir=str(OUTPUTS), valuation=valuation,
                         logic="S5", **edge_style(explicit_edges)))
        return path, equivalence_violations(frame)
    if kind == "belief":
        frame = RelationalFrame(agents, worlds, belief, validate=False,
                                axiom_d=axiom_d)
        # Belief has nothing implicit: every loop and every direction is
        # information, so the drawing shows them all whatever the switch.
        path = Path(show(frame, "gui_preview", "Modelo tal como se ingresa",
                         output_dir=str(OUTPUTS), valuation=valuation,
                         omit_self_loops=False, undirected_symmetric=False))
        return path, frame.violations()
    kb = KnowledgeBeliefFrame(
        agents, worlds, knowledge, belief, validate=False, axiom_d=axiom_d,
    )
    path = Path(show(kb, "gui_preview", "Modelo tal como se ingresa",
                     output_dir=str(OUTPUTS), valuation=valuation,
                     **edge_style(explicit_edges)))
    return path, kb.violations()


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
    # One report per pipeline step, in order: what was completed, what is
    # missing, and what failed. The run stopped at the first step with
    # ``failed`` non-empty.
    steps: List[StepReport] = field(default_factory=list)

    @property
    def failed_step(self) -> StepReport | None:
        """The step that stopped the run, or None if the pipeline completed."""
        return next((s for s in self.steps if s.failed), None)



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
    step = StepReport("1 · Modelo general (clausuras)")
    closure = "S5" if kind == "knowledge" else ("KD45" if frame.axiom_d else "K45")
    what = "conocimiento" if kind == "knowledge" else "creencia"
    for agent in sorted(agents, key=str):
        added = set(frame.relations[agent]) - set(seed.get(agent, set()))
        if added:
            step.completed.append(
                f"{what} de {agent!r}: la clausura {closure} agregó "
                f"{len(added)} arista(s) — {_fmt_edges(added)}"
            )
    for agent in sorted(agents, key=str):
        if kind == "knowledge":
            singles = [w for w in sorted(worlds, key=str)
                       if frame.successors(agent, w) == {w}]
            if singles:
                step.missing.append(
                    f"{agent!r} distingue {len(singles)} mundo(s) por separado "
                    f"({', '.join(map(str, singles))}): no estaban en ninguna "
                    "clase dibujada, así que quedaron como clases unitarias"
                )
        else:
            dead = sorted(frame.dead_ends()[agent], key=str)
            if dead:
                step.missing.append(
                    f"{agent!r} no cree nada en {', '.join(map(str, dead))}: "
                    "bajo K45 es una creencia difunta (Q = ∅), cree todo, ⊥ incluido"
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
    step = StepReport("1 · Modelo general (clausuras)")
    for agent in sorted(agents, key=str):
        seeded_k = set(knowledge_seed.get(agent, set()))
        added_k = set(kb.knowledge.relations[agent]) - seeded_k
        if added_k:
            step.completed.append(
                f"conocimiento de {agent!r}: la clausura S5 agregó "
                f"{len(added_k)} arista(s) — {_fmt_edges(added_k)}"
            )
        # Which knowledge classes had no belief drawn at all.
        seeded_b = set((belief_seed or {}).get(agent, set()))
        for cls in knowledge_classes(kb.knowledge, agent):
            if any(w in cls for (w, _) in seeded_b):
                continue
            worlds_txt = "{" + ", ".join(sorted(map(str, cls))) + "}"
            if believe_all_when_silent:
                step.completed.append(
                    f"creencia de {agent!r} en {worlds_txt}: no se marcó ninguna, "
                    f"se completó con Q = R (cree exactamente lo que sabe)"
                )
            else:
                step.completed.append(
                    f"creencia de {agent!r} en {worlds_txt}: no se marcó ninguna "
                    f"y el opt-in K45 está activo, quedó difunta (Q = ∅)"
                )
    # Worlds nobody put in a class become singleton classes -- easy to miss.
    for agent in sorted(agents, key=str):
        singles = [
            w for w in sorted(worlds, key=str)
            if kb.knowledge.successors(agent, w) == {w}
        ]
        if singles:
            step.missing.append(
                f"{agent!r} distingue {len(singles)} mundo(s) por separado "
                f"({', '.join(map(str, singles))}): no estaban en ninguna clase "
                f"dibujada, así que quedaron como clases unitarias"
            )
    return step


def diagnose_proper(kb, proper) -> StepReport:
    """Report whether copies were needed, and which agent was skewed and why."""
    step = StepReport("2 · Modelo propio (copias + sesgo)")
    if not proper.projection or len(proper.worlds) == len(kb.worlds):
        step.completed.append(
            "el modelo ya era propio: no hizo falta copiar nada"
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
        f"no era propio: se crearon {copies} copias "
        f"({len(kb.worlds)} → {len(proper.worlds)} mundos), bisimilares al original"
    )
    step.completed.append(
        f"agente distinguido {cheapest!r}: es el de menos aristas no reflexivas, "
        f"así cruzan menos aristas entre copias y la figura queda más limpia"
    )
    return step


def diagnose_simplicial(proper, sm, valuation) -> StepReport:
    """Report the translation's shape, and where a valuation is not representable."""
    step = StepReport("3 · Modelo simplicial (mundos → facetas)")
    step.completed.append(
        f"cada mundo se volvió una faceta: {len(proper.worlds)} mundos → "
        f"{len(sm.facets)} facetas, {len(sm.nodes)} nodos"
    )
    if not valuation:
        step.missing.append(
            "sin átomos declarados: las figuras no etiquetan mundos ni vértices, "
            "y el evaluador de fórmulas queda deshabilitado"
        )
        return step
    # NU: an atom true at a world that NO perspective observes is not
    # representable in the vertex-based semantics -- the one real gap here.
    assignment = assignment_from_model(sm, valuation)
    gaps = nu_violations(sm, assignment, valuation)
    for atom, facet in gaps[:6]:
        world = sm.world_of_facet.get(facet, facet)
        step.missing.append(
            f"átomo {atom!r} es verdadero en el mundo {world!r} pero ningún agente "
            f"lo observa allí: el esquema NU (P → ∨_a B_a P) falla, así que esa "
            f"verdad no es representable en la semántica por vértices"
        )
    if len(gaps) > 6:
        step.missing.append(f"… y {len(gaps) - 6} fallo(s) de NU más")
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
    """
    if not agents or not worlds:
        raise ValueError("se necesita al menos un agente y un mundo")

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
        step = StepReport("1 · Modelo general (clausuras)")
        step.failed.append(str(exc))
        result.steps.append(step)
        result.badges.append(("rechazado en el paso 1", "negative"))
        return result
    if kind == "kb":
        result.steps.append(diagnose_general(
            agents, worlds, knowledge, belief, kb, believe_all_when_silent
        ))
        logic = "KD45" if axiom_d else "K45"
        proper_now = kb.is_proper()
        fig1_caption = "Fig. 1 · modelo general (conocimiento delgado, creencia gruesa)"
        fig1_style = edge_style(explicit_edges)
    elif kind == "knowledge":
        result.steps.append(diagnose_general_frame(agents, worlds, knowledge, kb, kind))
        logic = "S5"
        proper_now = frame_is_proper(kb)
        fig1_caption = "Fig. 1 · modelo general de conocimiento (S5)"
        fig1_style = edge_style(explicit_edges)
    else:
        result.steps.append(diagnose_general_frame(agents, worlds, belief, kb, kind))
        logic = "KD45" if axiom_d else "K45"
        proper_now = False  # properness is a knowledge notion
        fig1_caption = f"Fig. 1 · modelo general de creencia ({logic})"
        fig1_style = {"omit_self_loops": False, "undirected_symmetric": False}
    result.log.append(
        f"Modelo general: {len(kb.worlds)} mundos, válido: {kb.is_valid()}, "
        f"propio: {proper_now}, lógica: {logic}"
    )
    result.badges.append(
        ("válido", "positive") if kb.is_valid() else ("inválido", "negative")
    )
    result.badges.append((logic, "primary"))
    result.stats.append((str(len(kb.worlds)), "mundos · general"))
    result.figures.append((
        fig1_caption,
        Path(show(kb, "gui_fig1_general", "Modelo general",
                  output_dir=str(OUTPUTS), valuation=valuation, **fig1_style)),
    ))
    result.text_diagrams.append(("Modelo general", visualize(kb)))

    if kind == "belief":
        # No KD45 -> S5 conversion exists (examples3.py makes the point): a
        # pure-belief model has no proper form and no simplicial translation.
        why = ("la propiedad y la traducción simplicial necesitan conocimiento "
               "S5; un modelo de sólo creencia termina en el paso 1. Para "
               "traducirlo, cambia a «conocimiento y creencia» y da las clases")
        for name in ("2 · Modelo propio (copias + sesgo)",
                     "3 · Modelo simplicial (mundos → facetas)"):
            step = StepReport(name)
            step.skipped.append(why)
            result.steps.append(step)
        return result

    # -- Step 2: properness (copies + skewed distinguished agent). ----------
    try:
        proper = kb.to_proper() if kind == "kb" else frame_to_proper(kb)
    except ValueError as exc:
        step = StepReport("2 · Modelo propio (copias + sesgo)")
        step.failed.append(str(exc))
        result.steps.append(step)
        result.badges.append(("rechazado en el paso 2", "negative"))
        return result
    result.steps.append(diagnose_proper(kb, proper))
    proper_ok = proper.is_proper() if kind == "kb" else frame_is_proper(proper)
    result.log.append(
        f"to_proper → {len(proper.worlds)} mundos, propio: {proper_ok}"
    )
    if proper_ok:
        result.badges.append(("propio", "positive"))
    result.stats.append((str(len(proper.worlds)), "mundos · propio"))
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
            "Fig. 2a · modelo propio, conocimiento R_a (S5)",
            Path(show(proper.knowledge, "gui_fig2_knowledge",
                      "Propio · conocimiento R_a", output_dir=str(OUTPUTS),
                      valuation=lifted, **edge_style(explicit_edges))),
        ))
        result.figures.append((
            "Fig. 2b · modelo propio, creencia Q_a (KD45)",
            Path(show(proper.belief, "gui_fig2_belief", "Propio · creencia Q_a",
                      omit_self_loops=not explicit_edges, output_dir=str(OUTPUTS),
                      valuation=lifted)),
        ))
    else:
        result.figures.append((
            "Fig. 2 · modelo propio de conocimiento R_a (S5)",
            Path(show(proper, "gui_fig2_knowledge", "Propio · conocimiento R_a",
                      output_dir=str(OUTPUTS), valuation=lifted,
                      **edge_style(explicit_edges))),
        ))
    result.text_diagrams.append(("Modelo propio", visualize(proper)))

    # -- Step 3: the simplicial belief model. --------------------------------
    try:
        sm = to_simplicial(proper)
    except ValueError as exc:
        step = StepReport("3 · Modelo simplicial (mundos → facetas)")
        step.failed.append(str(exc))
        result.steps.append(step)
        result.badges.append(("rechazado en el paso 3", "negative"))
        return result
    # `lifted`, NOT `valuation`: sm is built from the PROPER model, whose worlds
    # are copies (w, u). Comparing against the original world names would never
    # match and NU violations would go silently undetected.
    result.steps.append(diagnose_simplicial(proper, sm, lifted))
    sizes = ", ".join(f"S_{a}={len(sm.belief_facets[a])}" for a in sorted(sm.agents))
    result.log.append(
        f"to_simplicial → {len(sm.facets)} facetas; subcomplejos de creencia: {sizes}"
    )
    result.stats.append((str(len(sm.facets)), "facetas"))
    for a in sorted(sm.agents, key=str):
        result.stats.append((str(len(sm.belief_facets[a])), f"S_{a}"))
    result.figures.append((
        "Fig. 3 · modelo simplicial de creencia",
        Path(show(sm, "gui_fig3_simplicial", "Modelo simplicial",
                  output_dir=str(OUTPUTS), valuation=lifted)),
    ))
    result.html_3d = Path(show(sm, "gui_fig3_3d", "Modelo simplicial · 3D",
                               dim=3, output_dir=str(OUTPUTS),
                               valuation=lifted))
    result.text_diagrams.append(("Modelo simplicial", str(sm)))

    # -- Fig. 4: the face lattice (Hasse diagram) of the complex. -------------
    # The combinatorial reading of Fig. 3: which simplices exist and which is a
    # face of which; facet boxes carry the SAME world names Fig. 3 prints at
    # the centroids, so the two figures can be read together. The empty face
    # is left out (noise for this purpose). Always the textbook bottom-up
    # drawing (rankdir=BT): hasse.py suggests columns (LR) for wide middle
    # rows when the file is viewed on its own, but in the GUI the figure sits
    # in a wide column with a height cap, so a wide-and-low picture is the one
    # that stays readable; the LR variant became a tall, unreadable strip.
    lattice = hasse.face_lattice(sm, include_empty=False, assignment=lifted)
    result.figures.append((
        "Fig. 4 · retículo de caras del complejo (diagrama de Hasse): "
        "una caja por simplejo, una fila por dimensión, y una línea cuando "
        "uno es cara inmediata del otro",
        Path(hasse.show(lattice, "gui_fig4_hasse", "Retículo de caras",
                        output_dir=str(OUTPUTS), rankdir="BT")),
    ))
    result.text_diagrams.append(("Retículo de caras", hasse.visualize(lattice)))

    return result

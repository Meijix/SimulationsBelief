"""Formula parsing and evaluation on relational models: the GUI's human
syntax over the tuple formulas of ``semantics.py`` and ``assignment.py``.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from . import base  # noqa: F401  (puts the repository root on sys.path first)
from semantics import holds_kripke
from .relational import build_general, seeds_from_editor


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
#              | K_<agent> unary | B_<agent> unary
#              | '(' formula ')' | 'bot' | '⊥' | <atom>
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
            raise ValueError(f"unrecognised symbol in the formula: '{rest[:10]}'")
        tokens.append(m.group().strip())
        pos = m.end()
    if not tokens:
        raise ValueError("write a formula, e.g.  B_a p & ~K_a p")
    tokens.append("<end>")  # sentinel: saves an end-of-input check at every step
    i = 0  # cursor shared by the nested parsers (recursive descent)

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
                        f"'{tok}': agent '{agent}' does not exist (available: {agents}); "
                        f"to apply a modal to an atom, separate them with a "
                        f"space, e.g. 'K_a 1'"
                    )
            return (tok[0], agent, parse_unary())
        if tok == "(":
            node = parse_imp()
            if eat() != ")":
                raise ValueError("missing closing parenthesis ')'")
            return node
        if tok in ("bot", "⊥"):
            return ("bot",)
        if re.fullmatch(_ATOM, tok):
            if tok not in atoms:
                raise ValueError(
                    f"atom '{tok}' is not declared (available: {sorted(atoms)}); "
                    "add it in the Atoms section"
                )
            return ("atom", tok)
        raise ValueError(f"unexpected '{tok}' in the formula")

    node = parse_imp()
    if peek() != "<end>":
        raise ValueError(f"the formula ends but there is leftover text: '{peek()}'")
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
        raise ValueError("a knowledge-only model has no belief: "
                         "use K_a instead of B_a")
    if kind == "belief" and _uses(formula, "K"):
        raise ValueError("a belief-only model has no knowledge: "
                         "use B_a instead of K_a")
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

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

from assignment import (  # noqa: E402
    assignment_from_model,
    consistency_violations,
    holds as holds_simplicial,
    nu_violations,
)
from knowledge_belief import KnowledgeBeliefFrame, knowledge_classes  # noqa: E402
from properness import (  # noqa: E402
    cheapest_distinguished_agent,
    equivalence_violations,
    is_proper as frame_is_proper,
    to_proper as frame_to_proper,
)
from relational_frame import RelationalFrame  # noqa: E402
from semantics import holds_kripke, lift_valuation  # noqa: E402
import copy  # noqa: E402
from assignment import drop_inconsistent, facet_inconsistencies, maximal_complex  # noqa: E402
from simplicial import Node, SimplicialBeliefModel, label_node, to_relational, to_simplicial  # noqa: E402
from visualization import PALETTE, visualize  # noqa: E402
from visualization import show as _show  # noqa: E402

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
import hasse  # noqa: E402  -- face lattice (Fig. 4)


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

# Muddy children with two children: one world per distribution of mud, and
# each child cannot tell apart the two worlds that differ only in HIS own state.
_MUDDY_W = ["limpios", "a", "b", "ab"]
EXAMPLES = {
    "tesis": {
        "label": "Thesis · Figures 1 → 3",
        "agents": ["a", "b", "c"],
        "worlds": ["w0", "w1", "w2"],
        "per_agent": DEFAULT_EDITOR,
        # p holds where SOMEONE dares to believe: B_a p holds but K_a p does
        # not -- the knowledge/belief contrast in a single formula.
        "atoms": {"p": ["w1", "w2"]},
        "axiom_d": True,
    },
    "nasa": {
        # ejemplo_nasa.py: three units each read a segment (T/X); each one
        # knows ITS reading (class = worlds that agree at its position) and
        # believes the others read the same (the unanimous world of its letter).
        "label": "Colloquium · rescue network (octahedron)",
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
        # Tg = "unit g reads Transitable" (one atom per unit).
        "atoms": {f"T{g}": [w for w in _NASA_W if w[i] == "T"]
                  for i, g in enumerate("abc")},
        "axiom_d": True,
    },
    "moneda": {
        # The minimal two-agent case: a has already seen the coin (singleton
        # classes, left implicit), b cannot tell and believes it came up heads.
        "label": "Coin · a knows, b believes",
        "agents": ["a", "b"],
        "worlds": ["cara", "cruz"],
        "per_agent": {
            "a": [],  # no classes drawn = singleton classes (a distinguishes all)
            "b": [{"cls": ["cara", "cruz"], "bel": ["cara"]}],
        },
        "atoms": {"c": ["cara"]},
        "axiom_d": True,
    },
}


# --------------------------------------------------------------------------- #
# The full library: EVERY model from the repo's example scripts, converted to
# editor states. Each entry repeats the script's seeds (with the script's name
# as the reference), builds the model with the core -- the same closures the
# script uses -- and turns it into rows with ``editor_rows``. The rows are
# therefore those of the real model, not a hand transcription that could
# drift. A model that cannot be built is skipped with a warning on stderr
# instead of taking the GUI down.
# --------------------------------------------------------------------------- #
def editor_rows(model, agent: str, worlds: List[str], kind: str) -> List[dict]:
    """Editor rows for one agent, read off a model that is ALREADY closed.

    * ``kb``: one row per knowledge class, with what the agent believes in it
      (belief is constant on the class in a valid model). A singleton class
      that believes itself is omitted: the silence convention (Q = R) produces
      it on its own.
    * ``knowledge``: one row per non-singleton class (singletons are implicit).
    * ``belief``: one row per distinct believed set, with the worlds that
      believe it as the sources; a world that believes nothing gets no row.
    """
    if kind in ("kb", "knowledge"):
        kframe = model.knowledge if isinstance(model, KnowledgeBeliefFrame) else model
        rows = []
        for cls in knowledge_classes(kframe, agent):
            cls_l = [w for w in worlds if w in cls]
            if kind == "knowledge":
                if len(cls_l) > 1:
                    rows.append({"cls": cls_l, "bel": []})
                continue
            bel = model.believes(agent, cls_l[0])
            bel_l = [w for w in worlds if w in bel]
            if len(cls_l) == 1 and bel_l == cls_l:
                continue
            rows.append({"cls": cls_l, "bel": bel_l})
        return rows
    groups: Dict[frozenset, List[str]] = {}
    for w in worlds:
        succ = frozenset(model.successors(agent, w))
        if succ:
            groups.setdefault(succ, []).append(w)
    return [{"cls": src, "bel": [w for w in worlds if w in succ]}
            for succ, src in groups.items()]


def _entry(label: str, kind: str, model, worlds: List[str],
           atoms: Optional[Dict[str, List[str]]] = None,
           axiom_d: bool = True) -> dict:
    agents = sorted(model.agents, key=str)
    return {
        "label": label, "kind": kind, "agents": agents, "worlds": list(worlds),
        "per_agent": {a: editor_rows(model, a, list(worlds), kind) for a in agents},
        "atoms": dict(atoms or {}), "axiom_d": axiom_d,
    }


def _script_examples() -> Dict[str, dict]:
    """The scripts' models, one by one (see the header comment above)."""
    import itertools

    from relational_frame import s5_closure

    out: Dict[str, dict] = {}

    def add(key, label, kind, build, worlds, atoms=None):
        try:
            out[key] = _entry(label, kind, build(), worlds, atoms)
        except Exception as exc:  # noqa: BLE001 -- a broken example never sinks the GUI
            print(f"[gui] example {key!r} skipped: {exc}", file=sys.stderr)

    W3 = ["w1", "w2", "w3"]
    A3 = {"a", "b", "c"}
    # -- examples.py ---------------------------------------------------------
    add("ex1_multi", "examples.py · belief_multiagent (belief, 2 agents)", "belief",
        lambda: RelationalFrame.from_partial(
            {"alice", "bob"}, set(W3),
            {"alice": {("w1", "w2")}, "bob": {("w2", "w3")}}, make_serial=True), W3)
    add("ex1_euclid", "examples.py · invalid_euclidean (the closure repairs it)", "belief",
        lambda: RelationalFrame(
            {"carol"}, {"w", "a", "b"},
            {"carol": {("w", "a"), ("w", "b"), ("a", "a"), ("b", "b"), ("w", "w")}},
            validate=False), ["w", "a", "b"])
    add("ex1_deadend", "examples.py · invalid_deadend (the closure repairs it)", "belief",
        lambda: RelationalFrame(
            {"bob"}, {"w1", "w2"}, {"bob": {("w1", "w1"), ("w1", "w2")}},
            validate=False), ["w1", "w2"])
    add("ex1_bel_alice", "examples.py · belief_vs_knowledge: Alice's belief", "belief",
        lambda: RelationalFrame.from_partial(
            {"alice"}, set(W3), {"alice": {("w1", "w2")}}, make_serial=True), W3)
    add("ex1_kn_alice", "examples.py · belief_vs_knowledge: Alice's knowledge", "knowledge",
        lambda: RelationalFrame({"alice"}, set(W3),
                                {"alice": s5_closure(set(W3), {("w1", "w2")})}), W3)

    def muddy(children=("a", "b", "c")):
        def label(m):
            return "".join(sorted(m)) or "clean"
        subsets = [frozenset(c) for r in range(len(children) + 1)
                   for c in itertools.combinations(children, r)]
        worlds = {label(sub) for sub in subsets}
        rel = {x: s5_closure(worlds, {(label(sub), label(sub ^ {x})) for sub in subsets})
               for x in children}
        return RelationalFrame(set(children), worlds, rel)
    _MW = ["clean", "a", "b", "c", "ab", "ac", "bc", "abc"]
    add("ninos", "examples.py · muddy children (knowledge, 3 children)", "knowledge",
        muddy, _MW, {"Ma": [w for w in _MW if "a" in w and w != "clean"],
                     "Mb": [w for w in _MW if "b" in w and w != "clean"],
                     "Mc": [w for w in _MW if "c" in w and w != "clean"]})
    # -- examples2.py --------------------------------------------------------
    _WW = ["rain", "cloud", "sun"]
    add("clima", "examples2.py · tomorrow's weather (belief)", "belief",
        lambda: RelationalFrame.from_partial(
            {"alice", "bob"}, set(_WW),
            {"alice": {("rain", "cloud"), ("sun", "rain")},
             "bob": {("rain", "sun"), ("cloud", "sun")}}, make_serial=True),
        _WW, {"rain": ["rain"]})
    # -- examples3.py / examples3_explained.py / examples4.py ----------------
    F1 = {"a": {("w1", "w2"), ("w1", "w3")}, "b": {("w1", "w2"), ("w3", "w2")},
          "c": {("w1", "w3"), ("w2", "w3")}}
    F2 = {a: {("w3", "w2"), ("w2", "w3")} for a in A3}
    F3 = {"a": {("w1", "w2"), ("w1", "w3")}, "b": {("w3", "w2"), ("w2", "w3")},
          "c": {("w3", "w2"), ("w2", "w3")}}
    add("ex3_rf", "examples3.py · RF, the thesis's KD45 example (belief)", "belief",
        lambda: RelationalFrame.from_partial(A3, set(W3), F1, make_serial=True), W3)
    add("ex3_rf2", "examples3.py · RF2 (belief)", "belief",
        lambda: RelationalFrame.from_partial(A3, set(W3), F2, make_serial=True), W3)
    add("ex3_rf3", "examples3.py · RF3 (belief)", "belief",
        lambda: RelationalFrame.from_partial(A3, set(W3), F3, make_serial=True), W3)
    add("ex3_rf31", "examples3.py · RF31, frame3 closed under S5 (knowledge)", "knowledge",
        lambda: RelationalFrame.from_partial_s5(A3, set(W3), F3), W3)
    add("ex3_kb", "examples3.py · kb, belief + complete knowledge", "kb",
        lambda: KnowledgeBeliefFrame.from_partial(
            A3, set(W3), knowledge={a: {("w1", "w2"), ("w1", "w3")} for a in A3},
            belief=F1), W3)
    add("ex4_kf", "examples4.py · KF, frame closed under S5 (knowledge)", "knowledge",
        lambda: RelationalFrame.from_partial_s5(A3, set(W3), F1), W3)
    add("ex4_kf2", "examples4.py · KF2, cycle a-b-c (knowledge)", "knowledge",
        lambda: RelationalFrame.from_partial_s5(
            A3, set(W3), {"a": {("w1", "w2")}, "b": {("w2", "w3")}, "c": {("w3", "w1")}}), W3)
    _W6 = [f"w{i}" for i in range(1, 7)]
    MORE = {**F1, "d": {(x, y) for x in ("w1", "w2", "w3") for y in ("w4", "w5", "w6")}}
    add("ex4_more_bf", "examples4.py · moreBF, 4 agents and 6 worlds (belief)", "belief",
        lambda: RelationalFrame.from_partial(
            {"a", "b", "c", "d"}, set(_W6), MORE, make_serial=True), _W6)
    add("ex4_more_kf", "examples4.py · moreKF, 4 agents and 6 worlds (knowledge)", "knowledge",
        lambda: RelationalFrame.from_partial_s5({"a", "b", "c", "d"}, set(_W6), MORE), _W6)
    # -- example5.py ---------------------------------------------------------
    K5 = {"alice": {("w1", "w2"), ("w2", "w3"), ("w3", "w1")}, "bob": {("w2", "w3")}}
    add("ex5_kb", "example5.py · frame (knowledge and belief)", "kb",
        lambda: KnowledgeBeliefFrame.from_partial(
            {"alice", "bob"}, set(W3), K5,
            {"alice": {("w1", "w2"), ("w1", "w3")}, "bob": {("w2", "w3")}}), W3)
    add("ex5_kb3", "example5.py · frame3, no belief marked (Q = R)", "kb",
        lambda: KnowledgeBeliefFrame.from_partial(
            {"alice", "bob"}, set(W3), K5, {"alice": set(), "bob": set()}), W3)
    # -- examples7.py = Example for Poster 3.py ------------------------------
    F7 = {"a": {("w1", "w2"), ("w1", "w3")}, "b": {("w1", "w2"), ("w3", "w2")},
          "c": {("w2", "w3"), ("w1", "w3")}}
    add("ex7_kb", "examples7.py / poster 3 · KBframe (not proper → copies)", "kb",
        lambda: KnowledgeBeliefFrame.from_partial(A3, set(W3), F7, F7), W3)
    # -- example_val.py ------------------------------------------------------
    _WV = ["sol", "nubes", "lluvia"]
    add("val", "example_val.py · Ana and Beto with valuation (p, q)", "kb",
        lambda: KnowledgeBeliefFrame.from_partial(
            ["a", "b"], _WV,
            knowledge={"a": {("sol", "nubes")}, "b": {("sol", "nubes"), ("nubes", "lluvia")}},
            belief={"a": set(), "b": {(w, "sol") for w in _WV}}),
        _WV, {"p": ["lluvia"], "q": ["sol"]})
    # -- Natural Disaster Example.py (cartel) --------------------------------
    _WD = ["nS", "SnR", "SR"]
    FD = {"a": {("SnR", "SR"), ("SR", "SnR")}, "b": {("SnR", "nS")}}
    for key, lbl, val in (("desastre_antes", "before ¬C", ["SnR", "SR"]),
                          ("desastre_despues", "after ¬C", ["nS"])):
        add(key, f"Natural Disaster Example.py · {lbl} (C)", "kb",
            lambda: KnowledgeBeliefFrame.from_partial({"a", "b"}, set(_WD), FD, FD),
            _WD, {"C": val})
    # -- Example For Poster 1.py ---------------------------------------------
    NS, SNR, SR = "no message sent", "message sent but not received", "message sent and received"
    _WP1 = [NS, SNR, SR]
    FP1 = {"a": {(SNR, SR), (SR, SNR)}, "b": {(SNR, NS), (NS, SNR)}, "c": {(SNR, NS), (SR, NS)}}
    add("poster1", "Example For Poster 1.py · radio message, 3 agents", "kb",
        lambda: KnowledgeBeliefFrame.from_partial(A3, set(_WP1), FP1, FP1), _WP1)
    # -- Example for Poster 2.py (alternating-message protocol, S5) ---------
    _WP2 = ["anSnRbnSnR", "aS1bnR", "aS1bR", "aS0bnR", "aS0bR",
            "anRbS1", "aRbS1", "anRbS0", "aRbS0"]
    FP2 = {"a": {("anSnRbnSnR", "anRbS1"), ("anSnRbnSnR", "anRbS0"),
                 ("aS1bnR", "aS1bR"), ("aS0bnR", "aS0bR")},
           "b": {("anSnRbnSnR", "aS1bnR"), ("anSnRbnSnR", "aS0bnR"),
                 ("anRbS1", "aRbS1"), ("anRbS0", "aRbS0")}}
    add("poster2", "Example for Poster 2.py · alternating messages (knowledge, 9 worlds)",
        "knowledge",
        lambda: RelationalFrame.from_partial_s5({"a", "b"}, set(_WP2), FP2), _WP2)
    return out


EXAMPLES.update(_script_examples())

# A complex DEFINED DIRECTLY: the natural-disaster example as the poster draws
# it -- the path b0 - a0 - b1 - a1 with its three facets, SnR outside b's
# belief subcomplex, and C observed at the vertices.
EXAMPLES["simp_desastre"] = {
    "label": "Direct complex · natural disaster (before ¬C)",
    "kind": "simplicial",
    "agents": ["a", "b"], "worlds": [], "per_agent": {}, "atoms": {},
    "axiom_d": True,
    "vertices": {"a": ["a0", "a1"], "b": ["b0", "b1"]},
    "facets": [
        {"name": "SR", "nodes": {"a": "a0", "b": "b0"}, "belief": ["a", "b"]},
        {"name": "SnR", "nodes": {"a": "a0", "b": "b1"}, "belief": ["a"]},
        {"name": "nS", "nodes": {"a": "a1", "b": "b1"}, "belief": ["a", "b"]},
    ],
    "vatoms": {"C": {"true": ["a0", "b0"], "false": ["a1"]}},
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


# --------------------------------------------------------------------------- #
# Saving and loading (GitHub #18). A WORKSPACE file holds every open model --
# name, state, read-only flag and provenance -- as plain JSON, so it can be
# re-opened later, shared, or produced by a script that applied actions. The
# files live in ``saved_models/`` next to the code (tracked by git on purpose:
# a saved workspace is part of the project's material, not a scratch output).
# --------------------------------------------------------------------------- #
SAVED = ROOT / "saved_models"
WORKSPACE_FORMAT = "simulationsbelief-workspace/1"


def workspace_payload(docs: List[dict], actions: List[dict] | None = None) -> dict:
    """The JSON-ready form of a workspace: its documents and its action specs.

    Document ids and run results are not kept (results are recomputed on
    demand, which keeps the files small and the format independent of the
    figures). ``actions`` are the editor specs of :func:`blank_action`.
    """
    import datetime

    return {
        "format": WORKSPACE_FORMAT,
        "saved": datetime.datetime.now().isoformat(timespec="seconds"),
        "models": [
            {"name": d["name"], "state": d["state"],
             "readonly": bool(d.get("readonly", False)), "origin": d.get("origin")}
            for d in docs
        ],
        "actions": [copy.deepcopy(a) for a in (actions or [])],
    }


def save_workspace(docs: List[dict], name: str, actions: List[dict] | None = None) -> Path:
    """Write ``docs`` (and ``actions``) to ``saved_models/<name>.json`` and return the path."""
    import json
    import re

    SAVED.mkdir(exist_ok=True)
    slug = re.sub(r"[^\w\-. ]+", "_", name).strip() or "workspace"
    path = SAVED / (slug if slug.endswith(".json") else slug + ".json")
    path.write_text(json.dumps(workspace_payload(docs, actions), ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return path


def load_workspace_full(path: Path) -> Tuple[List[dict], List[dict]]:
    """``(documents, action specs)`` of a workspace file.

    Each state is laid over :func:`blank_state`, and each action over
    :func:`blank_action`, so a file written before a key existed still opens:
    missing fields take their defaults.

    Raises:
        ValueError: if the file is not a workspace of a known format.
    """
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != WORKSPACE_FORMAT:
        raise ValueError(f"{path} is not a workspace saved by the GUI")
    docs = []
    for m in data.get("models", []):
        st = m.get("state") or {}
        state = blank_state(st.get("kind", "kb"))
        state.update(st)
        docs.append({"name": m.get("name") or "Model", "state": state,
                     "readonly": bool(m.get("readonly", False)), "origin": m.get("origin")})
    if not docs:
        raise ValueError(f"{path} contains no models")
    actions = []
    for a in data.get("actions", []):
        spec = blank_action([])
        spec.update(a or {})
        actions.append(spec)
    return docs, actions


def load_workspace(path: Path) -> List[dict]:
    """The documents of a workspace file (see :func:`load_workspace_full`)."""
    return load_workspace_full(path)[0]


def list_saved() -> List[Path]:
    """Saved workspaces, newest first."""
    if not SAVED.exists():
        return []
    return sorted(SAVED.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


# --------------------------------------------------------------------------- #
# Simplicial ACTIONS (GitHub #6, #13, #18). The GUI side of the action layer:
# an action is edited as a spec with the same shapes the complex editor uses
# (events are facets of action nodes, one per agent; pre/post conditions are
# vertex atoms), applied to the active model, and its result opens as a
# read-only document that is drawn, evaluated, saved and compared like any
# other. The spec, JSON-friendly:
#
#   {"name": str,
#    "events":   [{"name": "e1", "nodes": {agent: action-node name}}],  (UCF)
#    "isolated": {agent: [action-node names in no event]},
#    "pre":      {atom: {"true": [node names], "false": [node names]}},  (as vatoms)
#    "post":     {atom: {"true": [...], "false": [...]}},
#    "mode":     1 | 2 | 3,                      compatibility test, see ACTION_MODES
#    "update":   "knowledge" | ...}              which product to run, see UPDATE_KINDS
#
# WHAT IS WIRED AND WHAT IS PENDING. ``simplicial_actions.update_model``
# (spec-b) implements the KNOWLEDGE product: output nodes are compatible
# (input, action) pairs, output facets the consistent products, and the
# result is a knowledge complex (S_a = S, K45). The belief products -- with
# and without memory -- and belief revision are Taiba's work in progress
# (#6, #15); they are listed in UPDATE_KINDS so the interface already offers
# the choice, and apply_action refuses them with a clear message until the
# functions exist. Plugging one in is a one-line change in UPDATE_KINDS.
# --------------------------------------------------------------------------- #
from simplicial_actions import DEFAULT_MODE, MODES, SimplicialAction, update_model  # noqa: E402

ACTION_MODES = {
    # Labels follow simplicial_actions.compatible(): how an input vertex x and
    # an action node y must agree on every atom to form the output node (x, y).
    1: "1 · what the vertex observes must be in the precondition (x ⇒ pre)",
    2: "2 · the precondition must be observed at the vertex (pre ⇒ x)",
    3: "3 · enough that they do not contradict each other (default)",
}

# update kind -> (label, function or None while pending). The function takes
# (model, assignment, action, mode) and returns something with ``.model`` and
# ``.assignment`` (the shape of simplicial_actions.UpdateModel).
UPDATE_KINDS = {
    "knowledge": ("knowledge (spec-b's product)", update_model),
    # PENDING (Taiba, #6): belief product -- S_a of the result from the S_a of
    # input and action, without memory.
    "belief": ("belief without memory (pending, #6)", None),
    # PENDING (Taiba, #15): belief product with memory.
    "belief_memory": ("belief with memory (pending, #15)", None),
    # PENDING (Taiba, #6): belief revision as an action (cf. revision.py's rule).
    "revision": ("belief revision (pending, #6)", None),
}


def blank_action(agents: List[str], name: str = "action") -> dict:
    """An empty action spec with every key the editor and :func:`build_action` expect."""
    return {"name": name, "events": [], "isolated": {a: [] for a in agents},
            "pre": {}, "post": {}, "mode": DEFAULT_MODE, "update": "knowledge"}


ACTION_EXAMPLES = {
    "anuncio_noC": {
        "label": "Public announcement of ¬C (for the disaster complex)",
        "spec": {
            "name": "announcement ¬C",
            # One event everybody takes part in; each agent's action node
            # requires ¬C, so the vertices observing C are incompatible with
            # it and disappear: exactly the public announcement of ¬C.
            "events": [{"name": "announcement", "nodes": {"a": "a_oye", "b": "b_oye"}}],
            "isolated": {"a": [], "b": []},
            "pre": {"C": {"true": [], "false": ["a_oye", "b_oye"]}},
            "post": {},
            "mode": DEFAULT_MODE, "update": "knowledge",
        },
    },
}


def action_node_names(spec: dict) -> List[str]:
    """Every action-node name the spec mentions (events first, then isolated), no repeats."""
    seen: List[str] = []
    for ev in spec.get("events", []):
        for v in ev.get("nodes", {}).values():
            if v and v not in seen:
                seen.append(v)
    for names in spec.get("isolated", {}).values():
        for v in names:
            if v and v not in seen:
                seen.append(v)
    return seen


def _conditions(table: Dict[str, dict]) -> Dict[str, Dict[str, int]]:
    """vatoms-shaped ``{atom: {"true": [...], "false": [...]}}`` -> ``{node: {atom: 0|1}}``."""
    out: Dict[str, Dict[str, int]] = {}
    for atom, spec in (table or {}).items():
        for v in spec.get("true", []):
            out.setdefault(v, {})[atom] = 1
        for v in spec.get("false", []):
            out.setdefault(v, {})[atom] = 0
    return out


def action_problems(spec: dict, agents: List[str]) -> List[str]:
    """What stops the spec from being an action (empty list = it builds)."""
    problems = []
    if not spec.get("events"):
        problems.append("the action has no events")
    for ev in spec.get("events", []):
        missing = [a for a in agents if not ev.get("nodes", {}).get(a)]
        if missing:
            problems.append(
                f"event '{ev.get('name')}' has no node for {', '.join(missing)} (UCF)"
            )
    for table in ("pre", "post"):
        for atom, cond in (spec.get(table) or {}).items():
            both = sorted(set(cond.get("true", [])) & set(cond.get("false", [])))
            if both:
                problems.append(f"{table}: atom '{atom}' is both true and false at {both}")
    if spec.get("update", "knowledge") not in UPDATE_KINDS:
        problems.append(f"unknown update kind: {spec.get('update')!r}")
    if problems:
        return problems
    try:
        build_action(spec, agents)
    except ValueError as exc:
        problems.append(str(exc))
    return problems


def preview_action(spec: dict, agents: List[str], tag: str = "") -> Path:
    """Draw the action AS DEFINED, complete or not: the Actions tab's live figure.

    An action is a chromatic complex like a model (thesis Def. 4.5): its
    events are the facets and its action nodes the vertices, so the model
    renderer draws it unchanged. Each node is labelled ``name(pre)[post]``,
    the notation of the thesis (p. 50), and each event by its name. Nothing
    is validated here, exactly like the model preview: an event missing some
    agent's node is drawn with the nodes it has, a node in no event is drawn
    loose, and the validity report next to the figure says what is missing.

    Raises:
        ValueError: when there is nothing to draw yet (no action node at all).
    """
    agents = list(agents)
    nodes: Dict[str, Node] = {}
    for ev in spec.get("events", []):
        for a, v in ev.get("nodes", {}).items():
            if v and a in agents:
                nodes.setdefault(v, Node(a, frozenset({v})))
    for a, names in (spec.get("isolated") or {}).items():
        for v in names:
            if v and a in agents:
                nodes.setdefault(v, Node(a, frozenset({v})))
    if not nodes:
        raise ValueError("add an event with at least one action node to see the action")
    pre, post = _conditions(spec.get("pre")), _conditions(spec.get("post"))

    def lits(table: Dict[str, int]) -> List[str]:
        return [("" if val else "¬") + atom for atom, val in sorted(table.items())]

    labels: Dict[Node, str] = {}
    for v, n in nodes.items():
        requires = lits(pre.get(v, {}))
        if (spec.get("pre_formula") or {}).get(v):
            requires.append(spec["pre_formula"][v])
        sets = lits(post.get(v, {}))
        sets += [f"{atom} := {phi}"
                 for atom, phi in sorted(((spec.get("post_formula") or {}).get(v) or {}).items())]
        labels[n] = (v + (f"({', '.join(requires)})" if requires else "")
                     + (f"[{', '.join(sets)}]" if sets else ""))
    event_of: Dict[frozenset, str] = {}
    belief: Dict[str, set] = {a: set() for a in agents}
    for i, ev in enumerate(spec.get("events", [])):
        members = frozenset(nodes[v] for a, v in ev.get("nodes", {}).items()
                            if v in nodes and nodes[v].agent == a)
        if not members or members in event_of:
            continue
        event_of[members] = ev.get("name") or f"e{i + 1}"
        for a in (ev["belief"] if "belief" in ev else agents):
            if a in belief:
                belief[a].add(members)
    model = SimplicialBeliefModel(agents, nodes.values(), event_of.keys(), belief,
                                  world_of_facet=event_of, validate=False, axiom_d=False,
                                  node_names=labels)
    return Path(show(model, _fname("gui_action", tag), "Action as defined",
                     output_dir=str(OUTPUTS), engine="auto" if _geometric_ok(model) else "dot"))


def build_action(spec: dict, agents: List[str]) -> SimplicialAction:
    """The :class:`SimplicialAction` a spec describes (the core validates it)."""
    events = {ev["name"]: {a: v for a, v in ev.get("nodes", {}).items() if v}
              for ev in spec.get("events", [])}
    return SimplicialAction.from_events(
        agents, events, pre=_conditions(spec.get("pre")), post=_conditions(spec.get("post")),
        isolated={a: list(v) for a, v in (spec.get("isolated") or {}).items() if v},
    )


def describe_action(spec: dict, agents: List[str]) -> str:
    """The core's text rendering of the action (events, nodes, pre/post)."""
    return build_action(spec, agents).describe()


def apply_action(state: dict, spec: dict, model_name: str = "model") -> dict:
    """Apply an action to a model state; returns the document of the result.

    The model may be of any kind: a relational one is first translated to its
    complex (general -> proper -> simplicial, as the direct editor's bootstrap
    does), because the product is defined on complexes. Inconsistent facets
    are dropped first (GitHub #21) and structural violations are refused, so
    the product runs on a valid model only.

    Returns:
        ``{"name", "state", "readonly": True, "origin"}`` -- what the GUI's
        ``new_doc`` takes. The state is a direct complex (see
        :func:`state_from_simplicial_model`).

    Raises:
        ValueError: an invalid model or action, or a core refusal, with the
            core's message.
        NotImplementedError: the chosen update kind is not available yet
            (see ``UPDATE_KINDS``: the pending products of the action layer).
    """
    update = spec.get("update", "knowledge")
    label, fn = UPDATE_KINDS.get(update, (update, None))
    if fn is None:
        raise NotImplementedError(
            f"the update “{label}” is not implemented yet; for now only "
            "the knowledge product (simplicial_actions.update_model)"
        )
    if state["kind"] != "simplicial":
        vertices, facets, vatoms = simplicial_state_from_editor(
            state["kind"], state["agents"], state["worlds"], state["per_agent"],
            state["atoms"], state["axiom_d"], not state.get("silent_defunct", False),
        )
        state = {**blank_state("simplicial"), "agents": list(state["agents"]),
                 "vertices": vertices, "facets": facets, "vatoms": vatoms,
                 "axiom_d": state["axiom_d"],
                 "complex_kind": "knowledge" if state["kind"] == "knowledge" else "kb"}
    agents = list(state["agents"])
    model, by_name, _ = build_simplicial(agents, state["vertices"], state["facets"],
                                         state["axiom_d"], validate=False,
                                         knowledge_only=_knowledge_only(state))
    assignment = simplicial_assignment(by_name, state["vatoms"])
    model, _ = _consistent_part(model, assignment, by_name)
    problems = model.violations()
    if problems:
        raise ValueError("the model is not valid:\n  - " + "\n  - ".join(problems))
    action = build_action(spec, agents)
    mode = int(spec.get("mode", DEFAULT_MODE))
    if mode not in MODES:
        raise ValueError(f"unknown compatibility mode: {mode}")
    result = fn(model, assignment, action, mode)
    # The product names output nodes by (input, action) pairs and facets by
    # (world, event) pairs; state_from_simplicial_model turns both into the
    # editor's names, so the result reads "a0⋅a_oye", "(nS, anuncio)".
    out_model = result.model
    out_model.node_names = {
        n: "⋅".join(_pair_text(p) for p in sorted(map(_pair_parts, n.cls)))
        for n in out_model.nodes
    }
    out_model.world_of_facet = {
        F: "(" + ", ".join(map(str, w)) + ")" if isinstance(w, tuple) else w
        for F, w in out_model.world_of_facet.items()
    }
    doc = doc_from_model(f"{model_name} ⋅ {spec.get('name') or 'action'}", out_model,
                         result.assignment,
                         origin=f"action “{spec.get('name') or 'action'}” ({label}) "
                                f"on {model_name}")
    return doc


def _pair_parts(pair) -> Tuple[str, str]:
    """``Pair(input node, action node)`` -> the two nodes' own names, as text."""
    def one(node) -> str:
        cls = getattr(node, "cls", None)
        if cls is None:
            return str(node)
        if len(cls) == 1:
            member = next(iter(cls))
            return "⋅".join(_pair_text(_pair_parts(member))) if isinstance(member, tuple) \
                and len(member) == 2 and hasattr(member[0], "agent") else str(member)
        return "{" + ",".join(sorted(map(str, cls))) + "}"
    return one(pair[0]), one(pair[1])


def _pair_text(parts: Tuple[str, str]) -> str:
    return f"{parts[0]}⋅{parts[1]}"


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


def state_problem(state: dict) -> Optional[str]:
    """What the state lacks before anything can be drawn; ``None`` if nothing."""
    if state["kind"] == "simplicial":
        if not (state["agents"] and any(state["vertices"].get(a) for a in state["agents"])):
            return ("Add agents and their vertices. Facets are optional: a vertex in "
                    "no facet is drawn on its own.")
    elif not (state["agents"] and state["worlds"]):
        return "Add at least one agent and one world."
    return None


def _knowledge_only(state: dict) -> bool:
    """Whether a direct complex is read as pure knowledge (``S_a = S``).

    ``state["complex_kind"]`` is ``"knowledge"`` or ``"kb"`` (the default, and
    what states saved before the key existed fall back to). There is no
    "belief-only" kind on purpose: in a complex the knowledge IS the gluing of
    the facets along shared vertices, so ``S_a`` cannot be declared without it.
    """
    return state.get("complex_kind", "kb") == "knowledge"


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

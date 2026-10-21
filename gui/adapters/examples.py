"""The example library: complete editor states for every model of the repo's
scripts and the poster, so loading one is a plain state swap in the GUI.
"""
from __future__ import annotations

import sys
from typing import Dict, List, Optional

from . import base  # noqa: F401  (puts the repository root on sys.path first)
from knowledge_belief import KnowledgeBeliefFrame, knowledge_classes
from relational_frame import RelationalFrame
from .base import DEFAULT_EDITOR


# ---------------------------------------------------------------------------
# Example library. Each entry is a COMPLETE editor state (agents, worlds,
# classes/beliefs, atoms, belief logic), so loading one is a plain state
# swap in the GUI -- no special-casing per example. They mirror scripts that
# already live in the repo, so the GUI doubles as a browsable gallery of them.
# 'atoms' is the Kripke valuation v : P -> worlds where the atom is TRUE; the
# figures label worlds/vertices with their literals when atoms are present.
# ---------------------------------------------------------------------------
_NASA_W = ["TTT", "TTX", "TXT", "TXX", "XTT", "XTX", "XXT", "XXX"]

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

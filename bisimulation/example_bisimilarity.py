# -*- coding: utf-8 -*-
"""Kripke models and their proper twin: built, checked and drawn.

WHAT THIS SHOWS. ``to_proper`` buys *properness* -- the condition the simplicial
translation needs -- by making ``|W|`` copies of a model and skewing one agent's
relations across them. The price must not include a change of meaning: the new
model has to be **bisimilar** to the old one, which is the claim of Thm. 2.4 of
Sink's thesis. This script walks four models through that claim and verifies it
with ``bisimulation.py``, which recomputes the largest bisimulation from scratch
instead of trusting the construction.

Each example is drawn as well as checked, because the copies are much easier to
believe once you see them: the general model on the left-hand figure, the proper
one on the right.

    1. Knowledge only, the smallest improper model there is (a coin nobody saw).
    2. Knowledge AND belief, with atoms: Sink's Figure 1, the thesis's own case.
    3. A model that is ALREADY proper, where ``to_proper`` copies nothing.
    4. A NO: two models that are not bisimilar, so the checker is seen to refuse.

Usage:
    python bisimulation/example_bisimilarity.py           # print and draw
    python bisimulation/example_bisimilarity.py --open    # ...and open the figures

Figures land in ``outputs/`` (git-ignored). Drawing needs the Graphviz ``dot``
binary; without it the script still prints everything and says so.
"""

if __name__ == "__main__":  # running this file directly
    # This example sits one level below the core modules, so put the repository
    # root on sys.path, as every runnable script in this repo does (doc 11).
    import os as _os
    import sys as _sys

    _sys.path.insert(
        0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    )

import sys

import bisimulation as bis
from knowledge_belief import KnowledgeBeliefFrame
from properness import to_proper
from relational_frame import RelationalFrame
from semantics import lift_valuation
from visualization import show as _show
from visualization import visualize

OPEN_FIGURES = "--open" in sys.argv


# --------------------------------------------------------------------------- #
# Small helpers: printing and drawing
# --------------------------------------------------------------------------- #
def banner(title: str) -> None:
    print(f"\n{'=' * 76}\n{title}\n{'=' * 76}")


def indent(text: str, prefix: str = "    ") -> str:
    return prefix + text.replace("\n", "\n" + prefix)


def draw(model, name: str, title: str, valuation=None) -> None:
    """Render one model, or explain why it could not be rendered.

    Graphviz is an optional dependency here: the point of the script is the
    check, and a missing ``dot`` binary should not hide the numbers.
    """
    try:
        path = _show(model, name, title, valuation=valuation, open=OPEN_FIGURES)
        print(indent(f"figure -> {path}"))
    except (RuntimeError, ImportError) as exc:
        print(indent(f"(figure skipped: {type(exc).__name__} -- {str(exc)[:60]})"))


def check_and_draw(general, name: str, valuation=None, draw_general=True) -> None:
    """The whole point of the script, for one model: copy it, verify it, draw it.

    The five steps are always the same, which is itself worth seeing: whatever
    the model, the pipeline and the verification do not change.
    """
    # STEP 1 -- is it proper? Properness is a condition on the KNOWLEDGE
    # relations alone: no two distinct worlds may be jointly accessible to every
    # agent. When it fails, the simplicial translation would merge those worlds
    # into one facet, which is why the copies are needed at all.
    proper_already = (
        general.is_proper() if hasattr(general, "is_proper")
        else __import__("properness").is_proper(general)
    )
    if proper_already:
        print(indent("properness: ALREADY PROPER -- to_proper will copy nothing"))
    else:
        violations = (
            general.properness_violations() if hasattr(general, "properness_violations")
            else __import__("properness").properness_violations(general)
        )
        print(indent(f"properness: NOT proper -- {violations[0]}"))

    # STEP 2 -- build the proper twin. For a KnowledgeBeliefFrame the SAME skew
    # is applied to both R_a and Q_a with the same distinguished agent, which is
    # what keeps Q_a ⊆ R_a alive on the other side.
    proper = (
        general.to_proper() if hasattr(general, "to_proper") else to_proper(general)
    )
    print(indent(f"to_proper : {len(general.worlds)} worlds -> "
                 f"{len(proper.worlds)} worlds   {proper!r}"))

    # STEP 3 -- verify the claim. Nothing here looks at how the copies were
    # made: `projection_violations` recomputes the largest bisimulation over the
    # disjoint union of the two models by partition refinement, and only then
    # asks whether each copy landed in the class of the world it simulates.
    print()
    print(indent(bis.explain(general, proper, valuation).replace("\n", "\n    ")))

    # STEP 4 -- the classes. They are usually FEWER than the worlds: worlds the
    # language cannot tell apart were already identified before any copying.
    lifted = lift_valuation(valuation, proper.projection) if valuation else None
    classes = bis.bisimilarity_classes(proper, lifted)
    print()
    print(indent(f"bisimilarity classes of the proper model: {len(classes)}"))
    for block in classes:
        members = sorted(map(str, block))
        shown = ", ".join(members[:4]) + (" ..." if len(members) > 4 else "")
        print(indent(f"  [{len(members):>2}] {shown}", "      "))

    # STEP 5 -- draw both sides.
    print()
    if draw_general:
        draw(general, f"{name}_general", f"{name} · general model", valuation)
    draw(proper, f"{name}_proper", f"{name} · proper model (bisimilar)", lifted)


# --------------------------------------------------------------------------- #
# 1. Knowledge only: the smallest improper model there is
# --------------------------------------------------------------------------- #
def example_1_knowledge_only() -> None:
    banner("1. Knowledge only -- a coin nobody saw")
    print("""
    Two agents, two worlds: the coin landed heads or tails and NEITHER agent
    saw it. Each one's knowledge relation is therefore the complete relation --
    a single equivalence class holding both worlds.

    This is as improper as a model can be: the two agents jointly consider both
    worlds possible from either of them, so they cannot tell the worlds apart
    even between the two of them, and f(heads) = f(tails) would collapse the
    model into a single facet. to_proper fixes it with |W|^2 = 4 worlds.

    No valuation here, so what is checked is the FRAME: exactly what Thm. 2.4
    talks about.""")

    worlds = {"heads", "tails"}
    complete = {(x, y) for x in worlds for y in worlds}
    # from_partial_s5 would close any seed into an equivalence relation; here the
    # relation is already complete, so we hand it over directly.
    general = RelationalFrame({"a", "b"}, worlds, {"a": complete, "b": complete})

    print(indent("the model, relation by relation:"))
    print(indent(visualize(general), "      "))
    check_and_draw(general, "bisim_ex1_coin")

    print(indent("Read the result: ONE class. Without atoms the two worlds say"))
    print(indent("the same thing, so all four copies are the same world for the"))
    print(indent("logic -- the inflation 2 -> 4 is pure redundancy, as intended."))


# --------------------------------------------------------------------------- #
# 2. Knowledge and belief, with atoms: the thesis's own Figure 1
# --------------------------------------------------------------------------- #
def example_2_figure_one() -> None:
    banner("2. Knowledge and belief, with atoms -- Sink's Figure 1")
    print("""
    Three agents, three worlds. Nobody knows anything (knowledge is complete
    for all three), but they believe different things:

        a believes {w1, w2}      "it is not w0"
        b believes {w1}          "it is definitely w1"
        c believes {w2}          "it is definitely w2"

    At w0 every agent holds a FALSE belief -- nobody's belief set contains the
    actual world. That is the situation belief models exist to describe, and
    the one knowledge alone cannot express.

    We give it an atom, P true only at w1, so the check covers the full
    language: the atoms, every K_a and every B_a. The valuation of the proper
    model is not a free choice -- it is the lift of this one along the
    projection, and `projection_violations` computes it itself.""")

    worlds = ["w0", "w1", "w2"]
    # Belief-only input (pipeline case 1): the knowledge relations are INDUCED
    # as the equivalence closure of each belief relation. Here that closure is
    # the complete relation, which is exactly the model the thesis draws.
    general = KnowledgeBeliefFrame.from_beliefs_only(
        ["a", "b", "c"], worlds,
        {"a": {(w, u) for w in worlds for u in ("w1", "w2")},
         "b": {(w, "w1") for w in worlds},
         "c": {(w, "w2") for w in worlds}},
    )
    valuation = {"P": {"w1"}}

    print(indent("the model (knowledge is complete for all three, so it is"))
    print(indent("the belief that distinguishes the agents):"))
    print(indent(visualize(general.belief, valuation=valuation), "      "))
    check_and_draw(general, "bisim_ex2_figure1", valuation)

    print(indent("Read the result: TWO classes, not nine. The copies of w1 (where"))
    print(indent("P holds) form one; the copies of w0 and w2 share the other,"))
    print(indent("because they agree on P and nobody's belief tells them apart."))


# --------------------------------------------------------------------------- #
# 3. A model that is already proper
# --------------------------------------------------------------------------- #
def example_3_already_proper() -> None:
    banner("3. Already proper -- to_proper copies nothing")
    print("""
    Four worlds in a 2x2 grid. Agent a tells the top pair from the bottom pair;
    agent b tells the left pair from the right pair. Neither can pin a world
    down alone, but TOGETHER they can: the intersection of their classes is a
    single world everywhere, which is precisely properness.

    to_proper notices this and returns the model untouched, with the identity
    projection -- there is no point inflating a model that does not need it.
    The verification still runs, and still means something: it confirms that
    the identity really is a bisimulation, which is the degenerate case of the
    same theorem.""")

    worlds = {"w0", "w1", "w2", "w3"}

    def equivalence(classes):
        """Turn a partition into the equivalence relation it induces."""
        return {(x, y) for group in classes for x in group for y in group}

    general = RelationalFrame(
        {"a", "b"}, worlds,
        {"a": equivalence([["w0", "w1"], ["w2", "w3"]]),   # top / bottom
         "b": equivalence([["w0", "w2"], ["w1", "w3"]])},  # left / right
    )
    valuation = {"p": {"w0"}}

    print(indent("the two partitions:"))
    print(indent(visualize(general, valuation=valuation), "      "))
    check_and_draw(general, "bisim_ex3_grid", valuation)

    print(indent("Read the result: FOUR classes for four worlds. Here the agents"))
    print(indent("already separate everything, so nothing is redundant and the"))
    print(indent("model is its own quotient."))


# --------------------------------------------------------------------------- #
# 4. What a NO looks like
# --------------------------------------------------------------------------- #
def example_4_not_bisimilar() -> None:
    banner("4. What a NO looks like -- two models that are NOT bisimilar")
    print("""
    A checker that always says yes is worth nothing, so here is one that says
    no. Two models over the same three worlds, same shape, with ONE difference:

        left  : b believes {w1}        right : b believes {w2}

    Their FRAMES are isomorphic -- rename w1 and w2 and you get one from the
    other -- so without atoms they are bisimilar, and the checker says so. Add
    an atom that singles w1 out and they come apart: on the left b believes P,
    on the right b does not. One formula, B_b P, is enough.""")

    worlds = ["w0", "w1", "w2"]
    left = KnowledgeBeliefFrame.from_beliefs_only(
        ["a", "b"], worlds,
        {"a": {(w, u) for w in worlds for u in ("w1", "w2")},
         "b": {(w, "w1") for w in worlds}},
    )
    right = KnowledgeBeliefFrame.from_beliefs_only(
        ["a", "b"], worlds,
        {"a": {(w, u) for w in worlds for u in ("w1", "w2")},
         "b": {(w, "w2") for w in worlds}},
    )
    valuation = {"P": {"w1"}}

    frames_only = bis.are_bisimilar(left, "w0", right, "w0")
    with_atoms = bis.are_bisimilar(left, "w0", right, "w0", valuation, valuation)
    print(indent(f"are_bisimilar(left, w0, right, w0)              -> {frames_only}"
                 "   (frames alone)"))
    print(indent(f"are_bisimilar(..., P={{w1}} on both sides)        -> {with_atoms}"
                 "   (with atoms)"))

    # The same refusal, reported the way `to_proper` failures are reported: the
    # largest bisimulation between the two models, as a set of pairs. An empty
    # intersection with the diagonal means no world of one matches its namesake.
    pairs = bis.bisimulation(left, right, valuation, valuation)
    matched = sorted(w for w in worlds if (w, w) in pairs)
    print()
    print(indent(f"largest bisimulation between them: {len(pairs)} pair(s)"))
    print(indent(f"worlds bisimilar to their namesake: {matched or 'none'}"))

    print()
    draw(left, "bisim_ex4_left", "4 · left model (b believes w1)", valuation)
    draw(right, "bisim_ex4_right", "4 · right model (b believes w2)", valuation)

    print()
    print(indent("Read the result: the atoms are what break the symmetry. This is"))
    print(indent("why the check on to_proper is run BOTH ways in the tests -- on"))
    print(indent("the frame (what Thm. 2.4 states) and with a valuation (what the"))
    print(indent("models actually say)."))


def main() -> None:
    example_1_knowledge_only()
    example_2_figure_one()
    example_3_already_proper()
    example_4_not_bisimilar()

    banner("In one line")
    print("""
    Four models, four verdicts, one procedure: build the proper twin with
    to_proper, then recompute the largest bisimulation from scratch and check
    that every copy sits in the class of the world it simulates. Three times it
    holds (that is Thm. 2.4); the fourth shows what it looks like when it does
    not.

    The theory and the implementation are explained in
    docs/14-bisimilaridad-refinamiento-particiones.md.""")


if __name__ == "__main__":
    main()

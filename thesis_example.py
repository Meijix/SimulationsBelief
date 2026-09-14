"""Reproduction of the worked example from Philip Sink's PhD thesis (2026).

This is the project's canonical end-to-end validation (README "Step 5: Validate
with thesis example"). It follows the thesis's own running example:

    Figure 1  a general relational model (not proper)
       |      to_proper: make copies, skew a distinguished agent
       v
    Figure 2  a bisimilar PROPER model
       |      (next: the simplicial translation)
       v
    Figure 3  a simplicial belief model            [pending -- the simplicial step]

The thesis presents the construction in two layers, reproduced here in order:

    * base case (knowledge only): a single equivalence relation R_a per agent,
    * full case (knowledge + belief): R_a plus a belief relation Q_a ⊆ R_a.

Run:  python thesis_example.py
Images are written to the outputs/ folder (git-ignored).
"""

import sys

from knowledge_belief import KnowledgeBeliefFrame
from properness import is_proper, to_proper
from relational_frame import RelationalFrame
from simplicial import to_simplicial
from visualization import show as _show

# Run with `--open` to also open each rendered figure in your viewer/browser.
_OPEN = "--open" in sys.argv


def show(*args, **kwargs):
    """Local wrapper so a ``--open`` CLI flag makes each figure open on render."""
    kwargs.setdefault("open", _OPEN)
    return _show(*args, **kwargs)


def banner(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def indent(text: str, prefix: str = "  ") -> str:
    return prefix + text.replace("\n", "\n" + prefix)


# Figure 1's frame: three agents who ALL consider every world possible, so no
# world is jointly distinguished -> the model is not proper.
FIG1_WORLDS = {"w0", "w1", "w2"}
FIG1_AGENTS = {"a", "b", "c"}
_COMPLETE = {(x, y) for x in FIG1_WORLDS for y in FIG1_WORLDS}


def knowledge_only() -> None:
    """Base case (Thesis Thm 2.3/2.4): one equivalence relation R_a per agent."""
    banner("Base case (knowledge only): Fig.1 -> Fig.2")

    fig1 = RelationalFrame(FIG1_AGENTS, FIG1_WORLDS, {a: set(_COMPLETE) for a in FIG1_AGENTS})
    print("Fig.1 (general model) is proper?", is_proper(fig1))

    # Distinguished agent defaults to the fewest-edges relation (ties broken by
    # name); here all three are complete, so the tie gives "a".
    proper = to_proper(fig1)
    print(f"to_proper -> {len(proper.worlds)} worlds, proper? {proper.is_proper()}")
    print("Projection (new world -> simulated original), sample:")
    for new_w in sorted(proper.worlds, key=str)[:3]:
        print(indent(f"{new_w} -> {proper.projection[new_w]}"))

    for frame, name, title in [
        (fig1, "thesis_fig1_general", "General (Fig.1): complete relations — NOT proper"),
        (proper, "thesis_fig2_proper", "Proper (Fig.2): 9-world bisimilar model"),
    ]:
        show(frame, name, title)  # S5 style (undirected, no self-loops) is inferred
    print(indent("Rendered general + proper models to outputs/"))


def knowledge_and_belief() -> None:
    """Full case (Thesis Sec 2.4): knowledge R_a plus belief Q_a ⊆ R_a."""
    banner("Full case (knowledge + belief): Fig.1 -> Fig.2")

    # Knowledge is complete for everyone; belief differs: a believes {w1,w2},
    # b is sure of w1, c is sure of w2. Nobody believes w0, so at w0 every agent
    # holds a FALSE belief -- exactly what belief (KD45, not S5) allows.
    kb = KnowledgeBeliefFrame(
        FIG1_AGENTS,
        FIG1_WORLDS,
        knowledge={a: set(_COMPLETE) for a in FIG1_AGENTS},
        belief={
            "a": {(w, "w1") for w in FIG1_WORLDS} | {(w, "w2") for w in FIG1_WORLDS},
            "b": {(w, "w1") for w in FIG1_WORLDS},
            "c": {(w, "w2") for w in FIG1_WORLDS},
        },
    )
    print("Model valid?", kb.is_valid())
    print(indent(
        f"at w0: a knows {sorted(kb.knows('a', 'w0'))} "
        f"but believes {sorted(kb.believes('a', 'w0'))} (false belief)"
    ))
    # Combined view of the (small) general model: knowledge thin, belief bold.
    show(kb, "thesis_fig1_kb", "Fig.1 knowledge+belief (knowledge thin, belief bold)")

    kb_proper = kb.to_proper()  # -> ProperKnowledgeBeliefFrame
    print(indent(
        f"to_proper -> {type(kb_proper).__name__}, {len(kb_proper.worlds)} worlds, "
        f"valid? {kb_proper.is_valid()}, proper? {kb_proper.is_proper()}"
    ))
    # Q_a ⊆ R_a is preserved because the same skew is applied to both relations.
    print(indent(
        "Q_a ⊆ R_a preserved? "
        + str(all(
            kb_proper.belief.relations[a] <= kb_proper.knowledge.relations[a]
            for a in kb_proper.agents
        ))
    ))

    # The two relations are rendered separately: knowledge (S5, symmetric) and
    # belief (KD45, directed pointers, some of them false).
    show(kb_proper.knowledge, "kb_proper_knowledge", "Proper knowledge R_a (S5)")
    show(kb_proper.belief, "kb_proper_belief", "Proper belief Q_a (KD45)",
         omit_self_loops=True)
    print(indent("Rendered proper knowledge + belief relations to outputs/"))


def simplicial() -> None:
    """Figure 3: translate the proper model into a simplicial belief model."""
    banner("Simplicial model: Fig.2 (proper) -> Fig.3 (simplicial belief model)")

    kb = KnowledgeBeliefFrame(
        FIG1_AGENTS,
        FIG1_WORLDS,
        knowledge={a: set(_COMPLETE) for a in FIG1_AGENTS},
        belief={
            "a": {(w, "w1") for w in FIG1_WORLDS} | {(w, "w2") for w in FIG1_WORLDS},
            "b": {(w, "w1") for w in FIG1_WORLDS},
            "c": {(w, "w2") for w in FIG1_WORLDS},
        },
    )
    sm = to_simplicial(kb.to_proper())
    print(sm)
    print(indent(
        f"belief subcomplex sizes -> "
        + ", ".join(f"S_{a}={len(sm.belief_facets[a])}" for a in ("a", "b", "c"))
    ))
    print(indent("Facet colouring (which agents' beliefs each world lives in):"))
    for tag, first in [("black / nobody", "w0"), ("S_a & S_b", "w1"), ("S_a & S_c", "w2")]:
        n = sum(1 for f, w in sm.world_of_facet.items() if w[0] == first)
        print(indent(f"  {first}* ({n} facets): {tag}", "    "))
    path = show(sm, "thesis_fig3_simplicial", "Fig.3 · simplicial belief model")
    print(indent(f"Rendered (2D) -> {path}"))
    html = show(sm, "thesis_fig3_3d", "Fig.3 · interactive 3D simplicial belief model", dim=3)
    print(indent(f"Rendered (interactive 3D) -> {html} (open in a browser to rotate)"))


def main() -> None:
    knowledge_only()
    knowledge_and_belief()
    simplicial()
    print("\nThe thesis example is now realised end to end: Fig.1 -> Fig.2 -> Fig.3.")


if __name__ == "__main__":
    main()

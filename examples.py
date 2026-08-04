"""Feature demos for the relational belief models.

These showcase the library's building blocks:

    1. validation        build frames, enforce the KD45 axioms
    2. closures          complete partial relations (belief KD45 / knowledge S5)
    3. belief_vs_knowledge  belief (KD45) vs. knowledge (S5)
    4. gallery           multi-agent frames + rendered images (valid & invalid)
    5. muddy_children    a knowledge (S5) puzzle, rendered as its natural cube

Run all examples:   python examples.py
Run one:            python examples.py muddy_children

Images are written to the outputs/ folder (git-ignored).
"""

import itertools
import sys

from relational_frame import RelationalFrame, kd45_closure, s5_closure
from visualization import render, visualize


def banner(title: str) -> None:
    """Print a section header so the output of a full run stays readable."""
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def indent(text: str, prefix: str = "  ") -> str:
    """Indent every line of a (possibly multi-line) message."""
    return prefix + text.replace("\n", "\n" + prefix)


# --------------------------------------------------------------------------- #
# 1. Building frames and validating the KD45 axioms
# --------------------------------------------------------------------------- #
def validation() -> None:
    banner("1. Building frames and validating the KD45 axioms")

    # A complete relation on a set of worlds is always serial, transitive and
    # Euclidean, so this is the canonical valid frame.
    valid = RelationalFrame(
        {"alice"},
        {"w1", "w2"},
        {"alice": {("w1", "w1"), ("w1", "w2"), ("w2", "w1"), ("w2", "w2")}},
    )
    print("Valid complete cluster:", valid)

    # Each rejection isolates one failing axiom.
    rejections = [
        (
            "Seriality (D): w2 is a dead end",
            {"bob"}, {"w1", "w2"}, {"bob": {("w1", "w1"), ("w1", "w2")}},
        ),
        (
            "Euclideanness (5): a->b is missing",
            {"carol"}, {"w", "a", "b"},
            {"carol": {("w", "a"), ("w", "b"), ("a", "a"), ("b", "b"), ("w", "w")}},
        ),
    ]
    for label, agents, worlds, relations in rejections:
        try:
            RelationalFrame(agents, worlds, relations)
        except ValueError as exc:
            print(f"\nRejected [{label}]:")
            print(indent(str(exc)))

    # validate=False builds the same broken model so it can be *inspected* instead
    # of raising -- every violation is collected, not just the first.
    broken = RelationalFrame(
        {"carol"},
        {"w", "a", "b"},
        {"carol": {("w", "a"), ("w", "b"), ("a", "a"), ("b", "b"), ("w", "w")}},
        validate=False,
    )
    print("\nInspecting an invalid model without raising (validate=False):")
    print(indent(f"is_valid? {broken.is_valid()}"))
    for problem in broken.kd45_violations():
        print(indent(f"- {problem}"))


# --------------------------------------------------------------------------- #
# 2. Completing partial relations with the closures
# --------------------------------------------------------------------------- #
def closures() -> None:
    banner("2. Completing partial relations with the KD45/S5 closures")

    worlds = {"w", "a", "b"}
    closed = kd45_closure(worlds, {("w", "a"), ("w", "b")})
    print("kd45_closure of {w->a, w->b}:")
    print(indent(str(sorted(closed))))
    print(indent(f"builds a valid frame: {RelationalFrame({'dave'}, worlds, {'dave': closed})}"))

    print("\nSeriality has no canonical closure -- an isolated world must opt in:")
    try:
        kd45_closure({"lonely"}, set())
    except ValueError as exc:
        print(indent(f"without make_serial: {str(exc).split(';')[0]}"))
    print(indent(f"with make_serial:    {sorted(kd45_closure({'lonely'}, set(), make_serial=True))}"))


# --------------------------------------------------------------------------- #
# 3. Belief (KD45) vs. knowledge (S5): the reflexivity line
# --------------------------------------------------------------------------- #
def belief_vs_knowledge() -> None:
    banner("3. Belief (KD45) vs. knowledge (S5): the reflexivity line")

    worlds = {"w1", "w2", "w3"}
    seed = {("w1", "w2")}
    belief = RelationalFrame.from_partial({"alice"}, worlds, {"alice": seed}, make_serial=True)
    knowledge = RelationalFrame({"alice"}, worlds, {"alice": s5_closure(worlds, seed)})

    print("Same seed {w1->w2} under BELIEF (KD45) -- w1 need not see itself,")
    print("so believing you are in w2 while actually in w1 (a false belief) is allowed:")
    print(indent(visualize(belief)))
    print("\nUnder KNOWLEDGE (S5) -- Axiom T forces every world to see itself:")
    print(indent(visualize(knowledge)))


# --------------------------------------------------------------------------- #
# 4. Multi-agent frames and the rendered gallery
# --------------------------------------------------------------------------- #
def gallery() -> None:
    banner("4. Multi-agent frames and the visual gallery")

    multi = RelationalFrame.from_partial(
        {"alice", "bob"},
        {"w1", "w2", "w3"},
        {"alice": {("w1", "w2")}, "bob": {("w2", "w3")}},  # each agent, independently
        make_serial=True,
    )
    print("Multi-agent belief frame (each agent's relation closed independently):")
    print(indent(visualize(multi)))

    # Invalid models render too -- the caption and red highlights say why they fail.
    broken = RelationalFrame(
        {"carol"}, {"w", "a", "b"},
        {"carol": {("w", "a"), ("w", "b"), ("a", "a"), ("b", "b"), ("w", "w")}},
        validate=False,
    )
    dead_end = RelationalFrame(
        {"bob"}, {"w1", "w2"}, {"bob": {("w1", "w1"), ("w1", "w2")}}, validate=False
    )
    print("\nRendering the gallery to outputs/:")
    for model, name in [
        (multi, "belief_multiagent"),      # valid, 2 agents
        (broken, "invalid_euclidean"),     # invalid: missing edges
        (dead_end, "invalid_deadend"),     # invalid: seriality dead end
    ]:
        print(indent(f"{name:20s} valid={model.is_valid()!s:5s} -> {render(model, name)}"))


# --------------------------------------------------------------------------- #
# 5. Muddy children: a knowledge (S5) puzzle drawn as its natural cube
# --------------------------------------------------------------------------- #
def muddy_children_model(children=("a", "b", "c")) -> RelationalFrame:
    """Build the muddy children knowledge (S5) model for the given children.

    A world is an assignment of muddy/clean to each child (labelled by the set of
    muddy children); child x cannot distinguish two worlds that differ only in x's
    own state. That indistinguishability relation is an equivalence relation (S5).
    """
    def label(muddy):
        return "".join(sorted(muddy)) or "clean"

    subsets = [
        frozenset(combo)
        for r in range(len(children) + 1)
        for combo in itertools.combinations(children, r)
    ]
    worlds = {label(s) for s in subsets}
    relations = {
        x: s5_closure(worlds, {(label(s), label(s ^ {x})) for s in subsets})
        for x in children
    }
    return RelationalFrame(set(children), worlds, relations)


def muddy_children() -> None:
    banner("5. Muddy children (knowledge / S5), rendered as the classic cube")

    muddy = muddy_children_model()
    print("Model valid?", muddy.is_valid())
    print(indent(visualize(muddy)))
    # A dense S5 model reads best with reflexive loops dropped and symmetric pairs
    # merged -- that turns the 3-child model into its natural cube.
    path = render(
        muddy,
        "muddy_children",
        title="Muddy children · 3 kids · knowledge (S5)",
        omit_self_loops=True,
        undirected_symmetric=True,
    )
    print(indent(f"Rendered -> {path}"))


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
EXAMPLES = {
    "validation": validation,
    "closures": closures,
    "belief_vs_knowledge": belief_vs_knowledge,
    "gallery": gallery,
    "muddy_children": muddy_children,
}


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        for example in EXAMPLES.values():
            example()
        return
    for name in argv:
        if name not in EXAMPLES:
            print(f"Unknown example {name!r}. Available: {', '.join(EXAMPLES)}")
            return
        EXAMPLES[name]()


if __name__ == "__main__":
    main()

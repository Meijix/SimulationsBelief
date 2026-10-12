"""A knowledge action, step by step, with the ORIGINAL action API only.

The example is the signal of Sink's thesis §4.4 (Figures 28-32), done on the
simplicial side with the simplicial action of Figure 52:

    "a sends b a message whose content is P_a. c is unaware that any message
    was sent, and there is a chance the message is not received, in which
    case b will think no message was sent."

Everything used here existed in the first version of ``simplicial_actions.py``
("knowledge actions only"): ``SimplicialAction.from_events``, ``compatible``,
``updated_values``, ``update_model``, ``UpdateModel`` -- plus the static core
(``KnowledgeBeliefFrame``, ``to_simplicial``, ``assignment_from_model``,
``holds``). Each step prints what it computed and why.

Run:  python examples/action_knowledge_example.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assignment import assignment_from_model, holds, node_value  # noqa: E402
from knowledge_belief import KnowledgeBeliefFrame  # noqa: E402
from simplicial import label_facet, label_node, to_simplicial  # noqa: E402
from simplicial_actions import (  # noqa: E402
    SimplicialAction,
    compatible,
    node_name,
    pair_of,
    update_model,
    updated_values,
)


def banner(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def lits(values) -> str:
    return ", ".join(f"{'' if v == 1 else '¬'}{p}" for p, v in sorted(values.items())) or "–"


# --------------------------------------------------------------------------- #
# Step 0. The input: the Kripke model of thesis Figure 29, made simplicial
# --------------------------------------------------------------------------- #
banner("Step 0 · input model (thesis Fig. 29 → its simplicial model)")
kb = KnowledgeBeliefFrame.from_partial(
    ["a", "b", "c"], ["w1", "w2", "w3"],
    # w1(¬Pa,¬Pb,¬Pc)  w2(Pa,Pb,¬Pc)  w3(Pa,Pb,Pc): c confuses w1/w2, a and b confuse w2/w3.
    knowledge={"a": {("w2", "w3")}, "b": {("w2", "w3")}, "c": {("w1", "w2")}},
    belief={},                                    # knowledge only: S_a = S
)
model = to_simplicial(kb.to_proper())
valuation = {"Pa": {"w2", "w3"}, "Pb": {"w2", "w3"}, "Pc": {"w3"}}
L = assignment_from_model(model, valuation)
print(model.describe())
print("\nvertex labels L (what each perspective observes; silence = 2):")
for n in sorted(model.nodes, key=label_node):
    print(f"  {label_node(n):<14} {lits(L.get(n, {}))}")
print("\nNote: b:{w2,w3} observes Pa and Pb (true in both its worlds) but not Pc;")
print("c:{w1,w2} observes ¬Pc only -- it cannot tell whether Pa holds.")

# --------------------------------------------------------------------------- #
# Step 1. The action: thesis Figure 52 (three events)
# --------------------------------------------------------------------------- #
banner("Step 1 · the action (thesis Fig. 52)")
action = SimplicialAction.from_events(
    ["a", "b", "c"],
    events={
        "m: sent and received": {"a": "aS", "b": "bR", "c": "c"},
        "k: sent but lost":     {"a": "aS", "b": "bnR", "c": "c"},
        "l: nothing happens":   {"a": "anS", "b": "bnR", "c": "c"},
    },
    pre={"aS": {"Pa": 1}},                       # a only sends P_a if P_a is true
    post={"bR": {"Pa": 1},                       # receiving writes P_a on b's perspective
          "aS": {"Sent": 1}, "anS": {"Sent": 0}},  # a's perspective records whether it sent
)
print(action.describe())
print("\nReading: aS is a's node in BOTH 'sent' events (a cannot tell received from")
print("lost); bnR is b's node in 'lost' and 'nothing' (b cannot tell them apart);")
print("c has ONE node in every event (c notices nothing). The atom Sent is the")
print("thesis's 'tag' (p. 49): a postcondition that records what happened.")

# --------------------------------------------------------------------------- #
# Step 2. Output nodes: compatible (input node, action node) pairs
# --------------------------------------------------------------------------- #
banner("Step 2 · output nodes N[A] = compatible pairs (mode 3: no clash)")
for x in sorted(model.nodes, key=label_node):
    for y in sorted(action.nodes, key=label_node):
        if x.agent != y.agent:
            continue
        ok = compatible(x, y, L, action.pre, 3)
        why = ""
        if not ok:
            why = "  ← clash: x observes " + lits(L.get(x, {})) + ", y requires " + lits(action.pre.get(y, {}))
        print(f"  {label_node(x):<14} × {node_name(y):<4} {'✓' if ok else '✗'}{why}")
print("\nOnly a:{w1} × aS dies: the perspective where ¬Pa holds cannot send Pa.")

# --------------------------------------------------------------------------- #
# Step 3. Labels: post wins, then the input, then the precondition
# --------------------------------------------------------------------------- #
banner("Step 3 · labels L[A](x, y) = post, else input, else pre")
for x in sorted(model.nodes, key=label_node):
    for y in sorted(action.nodes, key=label_node):
        if x.agent == y.agent and compatible(x, y, L, action.pre, 3):
            print(f"  ⟨{node_name(x)},{node_name(y)}⟩  →  {lits(updated_values(x, y, L, action.pre, action.post))}")
print("\nb:{w1} × bR gets Pa=1 from the postcondition although w1 has ¬Pa -- the")
print("pair exists at node level; step 4 decides whether any world uses it.")

# --------------------------------------------------------------------------- #
# Step 4. The product
# --------------------------------------------------------------------------- #
banner("Step 4 · facets of S[A]: (world X, event Y) whose pairs all survive and agree")
out = update_model(model, L, action)
for X in sorted(model.facets, key=lambda F: model.world_of_facet[F]):
    for Y in sorted(action.facets, key=lambda F: action.event_of_facet[F]):
        pairs = [(model.pi(a, X), action.pi(a, Y)) for a in "abc"]
        dead = [f"{label_node(x)}×{node_name(y)}" for x, y in pairs if not compatible(x, y, L, action.pre, 3)]
        print(f"  ({model.world_of_facet[X]}, {action.event_of_facet[Y][:1]})  "
              + ("✓" if not dead else "✗  dead pair: " + ", ".join(dead)))
print("\n" + out.model.describe())
print("\nOutput labels:")
for n in sorted(out.model.nodes, key=lambda n: str(pair_of(n))):
    print(f"  {str(pair_of(n)):<22} {lits(out.assignment.get(n, {}))}")
print(f"\nisolated output nodes (in no world): {[str(pair_of(n)) for n in out.isolated]}")
print("→ 7 worlds, exactly the 7 of thesis Figure 30; ⟨w1,bR⟩ is the node-level pair")
print("  that no world uses, kept and reported (K45 output).")

# --------------------------------------------------------------------------- #
# Step 5. What the agents know afterwards
# --------------------------------------------------------------------------- #
banner("Step 5 · knowledge in the output (holds)")
by_name = {w: F for F, w in out.model.world_of_facet.items()}
A = lambda p: ("atom", p)
K = lambda ag, f: ("K", ag, f)
checks = [
    (("w2", "m: sent and received"), K("b", A("Pa")), "b received: b knows Pa"),
    (("w1", "l: nothing happens"), ("not", K("b", A("Pa"))), "nothing was sent at w1: b does not know Pa"),
    (("w2", "m: sent and received"), ("not", K("c", A("Pa"))), "c cannot tell: c does not know Pa"),
    (("w2", "m: sent and received"), ("not", K("c", A("Sent"))), "c does not know whether a message was sent"),
    (("w2", "k: sent but lost"), K("a", A("Sent")), "a knows it sent"),
    (("w2", "k: sent but lost"), ("not", K("b", A("Sent"))), "lost: b cannot tell 'lost' from 'nothing'"),
    (("w2", "m: sent and received"), K("b", A("Sent")), "received: b knows a message was sent"),
    (("w2", "m: sent and received"), ("not", K("a", K("b", A("Sent")))), "a does not know whether b received it"),
]
for world, phi, text in checks:
    print(f"  {str(world):<36} {holds(out.model, out.assignment, by_name[world], phi)!s:<6} {text}")

# --------------------------------------------------------------------------- #
# Step 6. Chaining: the same signal again
# --------------------------------------------------------------------------- #
banner("Step 6 · apply the action a second time (chaining)")
twice = update_model(out.model, out.assignment, action)
print(f"second step: {len(twice.model.facets)} worlds, {len(twice.model.nodes)} nodes, "
      f"{len(twice.isolated)} isolated")
print("Every output node is an ordinary Node wrapping a Pair, so the output feeds the")
print("product again unchanged; facet names nest: ", next(iter(twice.model.world_of_facet.values())))

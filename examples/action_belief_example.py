"""A belief action with revision, step by step, using the extended action API.

Same signal as ``action_knowledge_example.py`` (thesis Fig. 52: "a sends P_a
to b, the message may be lost, c is unaware") but now:

    * the INPUT is a belief model: b does not know P_a and BELIEVES it false;
    * the action has per-agent event subcomplexes S_{a,A} (what each agent
      considers possible about the event: a does not know if the message
      arrived, b thinks a received message is never a lost one, c thinks
      nothing was sent);
    * the precondition is a MODAL formula, K_a P_a (a sends only what she
      knows);
    * the three products are compared: knowledge M[A], belief M[A]_B (b's
      belief collapses: the message contradicts it) and belief with revision
      M[A]_BR (b jumps to the nearest world where the message makes sense),
      the latter with and without memory.

Run:  python examples/action_belief_example.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assignment import assignment_from_model, holds  # noqa: E402
from knowledge_belief import KnowledgeBeliefFrame  # noqa: E402
from simplicial import label_node, to_simplicial  # noqa: E402
from simplicial_actions import (  # noqa: E402
    SimplicialAction,
    belief_update_model,
    describe_revisions,
    pair_of,
    revision_update_model,
    update_model,
)


def banner(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def lits(values) -> str:
    return ", ".join(f"{'' if v == 1 else '¬'}{p}" for p, v in sorted(values.items())) or "–"


A = lambda p: ("atom", p)
K = lambda ag, f: ("K", ag, f)
B = lambda ag, f: ("B", ag, f)
NOT = lambda f: ("not", f)

# --------------------------------------------------------------------------- #
# Step 0. Input: two worlds u (P_a) and v (¬P_a); a knows, b and c do not; b believes ¬P_a
# --------------------------------------------------------------------------- #
banner("Step 0 · input belief model: b wrongly believes ¬Pa")
kb = KnowledgeBeliefFrame.from_partial(
    ["a", "b", "c"], ["u", "v"],
    knowledge={"a": set(), "b": {("u", "v")}, "c": {("u", "v")}},
    belief={"a": set(), "c": set(),                # silent: believe what you know
            "b": {("u", "v"), ("v", "v")}},        # from both worlds b believes v only
)
model = to_simplicial(kb.to_proper())
L = assignment_from_model(model, {"Pa": {"u"}})
print(model.describe())
print("labels:", "   ".join(f"{label_node(n)}: {lits(L.get(n, {}))}" for n in sorted(model.nodes, key=label_node)))
print("\nS_b = {v}: wherever b is, it believes the world is v (¬Pa). a and c are silent:")
print("they believe what they know (S_a = S_c = S).")

# --------------------------------------------------------------------------- #
# Step 1. The action, now with S_{a,A} and a modal precondition
# --------------------------------------------------------------------------- #
banner("Step 1 · the action: per-agent events and a modal precondition")
action = SimplicialAction.from_events(
    ["a", "b", "c"],
    events={"m: sent and received": {"a": "aS", "b": "bR", "c": "c"},
            "k: sent but lost":     {"a": "aS", "b": "bnR", "c": "c"},
            "l: nothing happens":   {"a": "anS", "b": "bnR", "c": "c"}},
    # S_{a,A}: a does not know whether it arrived; b, when it received, has no
    # doubt (and when it did not, thinks nothing was sent); c thinks nothing happened.
    belief={"a": ["m: sent and received", "k: sent but lost", "l: nothing happens"],
            "b": ["m: sent and received", "l: nothing happens"],
            "c": ["l: nothing happens"]},
    pre_formula={"aS": K("a", A("Pa"))},             # a sends only what she KNOWS
    post={"bR": {"Pa": 1}, "aS": {"Sent": 1}, "anS": {"Sent": 0}},
)
print(action.describe())
print("\nEach event lists who considers it possible: [S_{a,b}] means a and b do, c does not.")

# --------------------------------------------------------------------------- #
# Step 2. Which (world, event) pairs are admissible: X ⊨ pre(Y)
# --------------------------------------------------------------------------- #
banner("Step 2 · the formula precondition is checked at the input worlds")
for X in sorted(model.facets, key=lambda F: model.world_of_facet[F]):
    ok = holds(model, L, X, K("a", A("Pa")))
    print(f"  {model.world_of_facet[X]} ⊨ K_a Pa : {ok}   → events with aS {'can' if ok else 'cannot'} happen at {model.world_of_facet[X]}")

# --------------------------------------------------------------------------- #
# Step 3. The three products
# --------------------------------------------------------------------------- #
banner("Step 3 · knowledge product M[A]: every agent believes what it knows")
k = update_model(model, L, action)
print(k.model.describe())
print("\nlabels of b's and c's output nodes:")
for n in sorted(k.model.nodes, key=lambda n: str(pair_of(n))):
    if n.agent in "bc":
        print(f"  {str(pair_of(n)):<16} {lits(k.assignment.get(n, {}))}")
print("\n⟨{u,v},bR⟩ records Pa=1 from the postcondition: after receiving, b has heard Pa.")
print("S_{a,A} played no role: the knowledge product sets S_a = S[A] for everyone.")

banner("Step 4 · belief product M[A]_B: b's belief collapses")
b = belief_update_model(model, L, action)
print(b.model.describe())
print("\ncollapsed (in a world, but no believed facet):", [str(pair_of(n)) for n in b.collapsed])
print("b believed v and considers only 'received' or 'nothing' possible; the intended")
print("facet (v, m) cannot exist (a does not know Pa at v), so b's receiving perspective")
print("has nothing left to believe: B_b ⊥ there.")
W = lambda res, name: next(F for F, w in res.model.world_of_facet.items() if w == name)
um = ("u", "m: sent and received")
print(f"  at (u, m):  B_b Pa = {holds(b.model, b.assignment, W(b, um), B('b', A('Pa')))},  "
      f"B_b ¬Pa = {holds(b.model, b.assignment, W(b, um), B('b', NOT(A('Pa'))))}   (both: vacuous)")

banner("Step 5 · belief with revision M[A]_BR: b jumps to the nearest world")
r = revision_update_model(model, L, action)
print(r.model.describe())
print("\nrevisions:\n" + describe_revisions(r))
print("\nThe intended facet {⟨v,aS⟩, ⟨{u,v},bR⟩, ⟨{u,v},c⟩} is imaged onto the realisable")
print("facet keeping b's node and sharing the most pairs: (u, m) shares b's and c's.")
print(f"  at (u, m):  B_b Pa = {holds(r.model, r.assignment, W(r, um), B('b', A('Pa')))},  "
      f"B_b ¬Pa = {holds(r.model, r.assignment, W(r, um), B('b', NOT(A('Pa'))))}")
print(f"  at (u, m):  B_c ¬Sent = {holds(r.model, r.assignment, W(r, um), B('c', NOT(A('Sent'))))}"
      "   (c believes nothing was sent)")
print(f"  at (u, m):  K_c Sent  = {holds(r.model, r.assignment, W(r, um), K('c', A('Sent')))}"
      "   (and does not know otherwise)")
print(f"  at (u, k):  B_b ¬Pa = {holds(r.model, r.assignment, W(r, ('u', 'k: sent but lost')), B('b', NOT(A('Pa'))))}"
      "   (lost: b keeps its false belief)")

banner("Step 6 · the same with memory: revise only towards worlds of S[A]")
rm = revision_update_model(model, L, action, memory=True)
print("revisions:\n" + describe_revisions(rm))
print("\nWith memory the candidates are the worlds of the product itself; without it any")
print("consistent combination of output perspectives over b's events competes. Here the")
print("nearest world was already in S[A], so both answers agree:",
      rm.model.belief_facets == r.model.belief_facets)

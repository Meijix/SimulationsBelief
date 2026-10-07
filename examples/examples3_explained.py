"""examples3.py, answered -- design notes behind the knowledge/belief split.

Story: the same three seeds on {w1, w2, w3} as examples3.py (the thesis's
three-agent example). Routes: belief only (``from_partial`` = KD45 closure)
versus knowledge only (``s5_closure``), and why properness -- a property of the
S5 knowledge relations R_a -- is undefined for a KD45 belief frame Q_a. The
proposals listed below have since been implemented (``from_partial_s5``,
``KnowledgeBeliefFrame``, the primary definition in properness.py).

from_partial(..., make_serial=True) closes each agent's seed edges under KD45 --
transitivity + Euclideanness, plus a self-loop for isolated worlds. KD45 is BELIEF.
It does not add reflexivity, so the result is not S5 unless the seed already happened
to make it so.

s5_closure(worlds, edges) closes each edge under S5 -- works for one relation at a time -- reflexive + transitive + Euclidean
kd45_closure(worlds, edges, make_serial=True) closes each edge under KD45 -- works for one relation at a time -- transitivity + Euclideanness, plus a self-loop for isolated worlds. KD45 is BELIEF.

Solution: 
1. from_partial = from_partial_KD45
2. Add a new function from_partial_S5 that closes each edge under S5.
3. Add a new class KnowledgeBeliefFrame to carry both relations.

4. Add a new function that closes each relation of KnowledgeBeliefFrame from its corresponding closure????
5. Change the properness.py to use the PRIMARY definition instead of the |.| = 1 test.
6. Change the properness.py to use the KnowledgeBeliefFrame class instead of the RelationalFrame class.???
7. Change properness.py to refuses non-S5 frames up front

IS THERE A KD45 -> S5 CONVERSION? Belief is not knowledge with extra STUFF added to it?

Run:  python examples/examples3_explained.py   -- a notes file: it builds RF, RF2, RF3 and
prints nothing. The explanation lives in this docstring and the PART 1/2 blocks;
``primary_definition_violations`` is a reference implementation. (The ``show``
wrapper accepts ``--open`` but no figure is rendered here.)
"""

import os
import sys

# The examples live one level below the core modules. Put the repository root on
# sys.path so ``python examples/<script>.py`` works from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_belief import KnowledgeBeliefFrame
from properness import is_proper, joint_possibilities, non_proper_worlds
from relational_frame import RelationalFrame, kd45_closure, s5_closure
from simplicial import to_simplicial
from visualization import show as _show

_OPEN = "--open" in sys.argv


def show(*args, **kwargs):
    """Local wrapper so ``--open`` makes each figure open on render."""
    kwargs.setdefault("open", _OPEN)
    return _show(*args, **kwargs)


def banner(title: str) -> None:
    print(f"\n{'=' * 74}\n{title}\n{'=' * 74}")


def indent(text: str, prefix: str = "  ") -> str:
    return prefix + str(text).replace("\n", "\n" + prefix)


# --------------------------------------------------------------------------- #
# The three frames from examples3.py
# --------------------------------------------------------------------------- #
AGENTS = {"a", "b", "c"}
WORLDS = {"w1", "w2", "w3"}

FRAME = {
    "a": {("w1", "w2"), ("w1", "w3")},
    "b": {("w1", "w2"), ("w3", "w2")},
    "c": {("w1", "w3"), ("w2", "w3")},
}
FRAME2 = {
    "a": {("w3", "w2"), ("w2", "w3")},
    "b": {("w3", "w2"), ("w2", "w3")},
    "c": {("w3", "w2"), ("w2", "w3")},
}
FRAME3 = {
    "a": {("w1", "w2"), ("w1", "w3")},
    "b": {("w3", "w2"), ("w2", "w3")},
    "c": {("w3", "w2"), ("w2", "w3")},
}

RF = RelationalFrame.from_partial(AGENTS, WORLDS, FRAME, make_serial=True)
RF2 = RelationalFrame.from_partial(AGENTS, WORLDS, FRAME2, make_serial=True)
RF3 = RelationalFrame.from_partial(AGENTS, WORLDS, FRAME3, make_serial=True)


def reflexive(frame: RelationalFrame) -> bool:
    """True iff every agent has w -> w everywhere, i.e. the frame is S5 (knowledge)."""
    return all(w in frame.successors(a, w) for a in frame.agents for w in frame.worlds)


# =========================================================================== #
# PART 1 -- what these frames actually are
# =========================================================================== #
"""All three are KD45 *belief* frames. Only RF2 happens to be S5 as well.
    `from_partial(..., make_serial=True)` closes each agent's seed edges under
    KD45 -- transitivity + Euclideanness, plus a self-loop for isolated worlds
    KD45 is BELIEF. It does not add reflexivity, so the result is not S5 unless the seed already happened to make it so.

    RF: valid KD45? True   reflexive? False   -> KD45 only (belief)
    RF2: valid KD45? True   reflexive? True   -> S5 (knowledge) as well
    RF3: valid KD45? True   reflexive? False   -> KD45 only (belief)
"""

# =========================================================================== #
# PART 2 -- questions 1 and 2: the properness numbers
# =========================================================================== #
"""
Properness has two formulations:

  PRIMARY   no distinct x != y with x R_a y for EVERY agent a
  IN CODE   | intersection over a of R_a(w) | = 1, at every world w

They agree WHEN THE FRAME IS REFLEXIVE, because reflexivity puts w itself
in the intersection and so guarantees |intersection| >= 1. Then '= 1' says
exactly 'no OTHER world is jointly accessible' -- the primary definition.

Drop reflexivity and they come apart. |intersection| = 0 becomes possible,
and it means something entirely different: the agents' beliefs are mutually
inconsistent at that world. That is not a properness failure. The '!= 1'
test counted it as one.

frame   reflexive  PRIMARY definition       |.| = 1 test          
------------------------------------------------------------------
RF          False  PROPER                   fails at ['w1', 'w2', 'w3']
RF2          True  fails at ['w2', 'w3']    fails at ['w2', 'w3'] 
RF3         False  fails at ['w2', 'w3']    fails at ['w1', 'w2', 'w3']

Reading the rows:
  RF2  reflexive -> the two columns agree. Nothing was ever wrong here.
  RF3  the primary definition gives exactly w2, w3 -- the expected answer
       in question 1. The '!= 1' test added w1 because the intersection
       there is EMPTY (a believes {w2,w3}, b and c believe {w1}).
  RF   the primary definition says PROPER. The '!= 1' test failed all three
       worlds, every one of them with an empty intersection.


RF2 still answers, because it IS a knowledge frame. RF and RF3 are belief
frames and get a diagnosis instead of a misleading verdict.
"""

def primary_definition_violations(frame: RelationalFrame):
    """Properness, PRIMARY definition: pairs x != y with x R_a y for EVERY agent a.

    This is the definition in Bjorndahl & Sink, *A Note on Proper Relational
    Structures* 
    
    ``properness.py`` implements the equivalent
    ``|intersection of R_a(w)| = 1`` form instead. 
    
    (DONE: properness.py now uses the primary definition; this function is kept
    as the reference implementation it was checked against.)
    """
    return sorted(
        (x, y)
        for x in frame.worlds
        for y in frame.worlds
        if x != y and all(y in frame.successors(a, x) for a in frame.agents)
    )


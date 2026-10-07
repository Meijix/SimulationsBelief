"""Example from the Coloquio 2026 poster: three units and their reading of a road.

Three units of a relief network -- Ana on reconnaissance (a), the Base (b) and
the Convoy (c) -- radio each other their reading of a road segment: "T"
passable or "X" blocked. A world is the triple of the three readings, so there
are eight. Each unit knows its own reading and nothing else, and believes the
other two read the same as it does (the hypothesis that the network does not
fail).

What the example makes visible: as soon as there is a disagreement, all three
believe something false at once. In TTX the Convoy is the only one reading
blocked; Ana and the Base believe TTT and the Convoy believes XXX.

The resulting simplicial complex is an octahedron: six vertices (two per unit)
and eight facets. Only the two unanimous faces, TTT and XXX, lie in some
belief subcomplex; the six disagreement faces are left out of all of them.

Usage:
    python3 poster/poster-code/ejemplo_nasa.py            # prints the model and writes the figures
    python3 poster/poster-code/ejemplo_nasa.py --open     # and opens them
"""

import os
import sys
from itertools import product

# This script lives in poster/poster-code/, two levels below the core modules.
# Put the repository root on sys.path so it runs from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from knowledge_belief import KnowledgeBeliefFrame
from properness import is_proper
from simplicial import to_simplicial
from visualization import show, visualize

AG = ("a", "b", "c")
NOMBRE = {"a": "Ana", "b": "Base", "c": "Convoy"}
I = {"a": 0, "b": 1, "c": 2}
W = ["".join(t) for t in product("TX", repeat=3)]


def modelo() -> KnowledgeBeliefFrame:
    """The full scenario: what each unit knows and what it believes."""
    return KnowledgeBeliefFrame(
        set(AG), set(W),
        # each unit knows its own reading
        knowledge={g: {(u, v) for u in W for v in W if u[I[g]] == v[I[g]]} for g in AG},
        # and believes the other two read the same as it does
        belief={g: {(u, u[I[g]] * 3) for u in W} for g in AG},
    )


def tras_el_anuncio() -> KnowledgeBeliefFrame:
    """The state that motivates the NASA TM revision: defunct beliefs.

    "There is disagreement" is publicly announced (the real world TTX is not
    unanimous). Each unit believed EXACTLY one unanimous world (TTT or XXX),
    so the announcement removes from each Q_g all its believed worlds: Q_g is
    left EMPTY everywhere. The units' own readings do not change (knowledge
    stays the same); what dies is the hypothesis that the network does not
    fail.

    That state -- vacuously believing everything, ⊥ included, until a revision
    policy repairs it -- is K45, not KD45: axiom D forbids it. That is why this
    model can ONLY be built with axiom_d=False; the KD45 constructor rejects
    it (and this file demonstrates that). The revision of chapter 3 / the TM
    is precisely the mechanism that will refill these Q with "nearby" worlds.
    """
    return KnowledgeBeliefFrame(
        set(AG), set(W),
        knowledge={g: {(u, v) for u in W for v in W if u[I[g]] == v[I[g]]} for g in AG},
        belief={g: set() for g in AG},   # every cluster, wiped out by the announcement
        axiom_d=False,                   # K45: defunct belief is legal
    )


def main() -> None:
    abrir = "--open" in sys.argv
    kb = modelo()
    print("modelo válido:", kb.is_valid(), "| propio:", is_proper(kb.knowledge))

    real = "TTX"
    print(f"\nsi el mundo real es {real}:")
    for g in AG:
        cree = sorted(kb.believes(g, real))
        print(f"  {NOMBRE[g]:7s} cree {cree}  ->", "correcto" if cree == [real] else "FALSO")

    print("\ncreencia de la Base, como relación:")
    print(visualize(kb.belief, "b"))

    sm = to_simplicial(kb.to_proper())
    print(sm)
    for g in AG:
        caras = sorted(sm.world_of_facet[f] for f in sm.belief_facets[g])
        print(f"  subcomplejo de {NOMBRE[g]}: {caras}")

    show(kb.belief, "nasa_creencia", "", open=abrir)
    show(sm, "nasa_complejo", "", open=abrir)
    try:
        show(sm, "nasa_complejo_3d", "", dim=3, open=abrir)
    except ImportError:
        print("(sin plotly instalado: se omite la figura en 3-D)")

    # ---- after announcing "there is disagreement": defunct beliefs (K45) ---- #
    print("\ntras el anuncio de desacuerdo (creencias difuntas, K45):")
    try:
        KnowledgeBeliefFrame(
            set(AG), set(W),
            knowledge={g: {(u, v) for u in W for v in W if u[I[g]] == v[I[g]]} for g in AG},
            belief={g: set() for g in AG},   # without axiom_d=False...
        )
    except ValueError as exc:
        print(f"  KD45 lo rechaza: {str(exc).splitlines()[0][:70]}...")
    kb2 = tras_el_anuncio()
    print(f"  K45 lo acepta: {kb2!r}, válido: {kb2.is_valid()}")
    from semantics import holds_kripke
    vacua = holds_kripke(kb2, {}, "TTX", ("B", "c", ("bot",)))
    print(f"  el Convoy 'cree' ⊥ en TTX (vacuidad, B difunta): {vacua}")
    sm2 = to_simplicial(kb2.to_proper())
    print(f"  complejo: {sm2!r} -- subcomplejos: "
          + ", ".join(f"S_{g}={len(sm2.belief_facets[g])}" for g in AG)
          + "  (todas las caras en negro: nadie cree nada)")
    print("\nfiguras en outputs/")


if __name__ == "__main__":
    main()

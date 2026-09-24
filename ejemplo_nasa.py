"""Ejemplo del cartel del Coloquio 2026: tres unidades y su lectura del tramo.

Tres unidades de una red de auxilio —Ana en reconocimiento (a), la Base (b) y
el Convoy (c)— se pasan por radio su lectura de un tramo de camino:
"T" transitable o "X" bloqueado. Un mundo es la terna de las tres lecturas,
así que hay ocho. Cada unidad conoce su propia lectura y nada más, y cree que
las otras dos leen lo mismo que ella (la hipótesis de que la red no falla).

Lo que hace visible el ejemplo: en cuanto hay un desacuerdo, las tres creen
algo falso a la vez. En TTX el Convoy es el único que lee bloqueado; Ana y la
Base creen TTT y el Convoy cree XXX.

El complejo simplicial resultante es un octaedro: seis vértices (dos por
unidad) y ocho facetas. Sólo las dos caras unánimes, TTT y XXX, están en algún
subcomplejo de creencia; las seis caras de desacuerdo quedan fuera de todas.

Uso:
    python3 ejemplo_nasa.py            # imprime el modelo y escribe las figuras
    python3 ejemplo_nasa.py --open     # y las abre
"""

import sys
from itertools import product

from knowledge_belief import KnowledgeBeliefFrame
from properness import is_proper
from simplicial import to_simplicial
from visualization import show, visualize

AG = ("a", "b", "c")
NOMBRE = {"a": "Ana", "b": "Base", "c": "Convoy"}
I = {"a": 0, "b": 1, "c": 2}
W = ["".join(t) for t in product("TX", repeat=3)]


def modelo() -> KnowledgeBeliefFrame:
    """El escenario completo: qué conoce y qué cree cada unidad."""
    return KnowledgeBeliefFrame(
        set(AG), set(W),
        # cada unidad conoce su propia lectura
        knowledge={g: {(u, v) for u in W for v in W if u[I[g]] == v[I[g]]} for g in AG},
        # y cree que las otras dos leen lo mismo que ella
        belief={g: {(u, u[I[g]] * 3) for u in W} for g in AG},
    )


def tras_el_anuncio() -> KnowledgeBeliefFrame:
    """El estado que motiva la revisión del TM de NASA: creencias difuntas.

    Se anuncia públicamente "hay desacuerdo" (el mundo real TTX no es unánime).
    Cada unidad creía EXACTAMENTE un mundo unánime (TTT o XXX), así que el
    anuncio elimina de cada Q_g todos sus mundos creídos: Q_g queda VACÍA en
    todas partes. Las lecturas propias no cambian (el conocimiento sigue igual);
    lo que muere es la hipótesis de que la red no falla.

    Ese estado -- creer vacuamente todo, ⊥ incluido, hasta que una política de
    revisión lo repare -- es K45, no KD45: el axioma D lo prohíbe. Por eso este
    modelo SOLO se puede construir con axiom_d=False; el constructor KD45 lo
    rechaza (y este archivo lo demuestra). La revisión del capítulo 3 / el TM
    es precisamente el mecanismo que rellenará estas Q con mundos "cercanos".
    """
    return KnowledgeBeliefFrame(
        set(AG), set(W),
        knowledge={g: {(u, v) for u in W for v in W if u[I[g]] == v[I[g]]} for g in AG},
        belief={g: set() for g in AG},   # todos los cúmulos, anulados por el anuncio
        axiom_d=False,                   # K45: la creencia difunta es legal
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

    # ------- tras anunciar "hay desacuerdo": creencias difuntas (K45) ------- #
    print("\ntras el anuncio de desacuerdo (creencias difuntas, K45):")
    try:
        KnowledgeBeliefFrame(
            set(AG), set(W),
            knowledge={g: {(u, v) for u in W for v in W if u[I[g]] == v[I[g]]} for g in AG},
            belief={g: set() for g in AG},   # sin axiom_d=False...
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

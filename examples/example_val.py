# -*- coding: utf-8 -*-
"""Minimal step-by-step example: a model WITH A LOGICAL VALUATION, end to end.

The other examples in the repo are structural (worlds and relations). This one
adds the layer they lack -- atoms, truth and formulas -- and follows a single
model through the six steps of the pipeline:

    1. the scenario and the relations (raw seeds)
    2. the logical valuation  v : P -> 2^W   (which atom is true where)
    3. evaluating formulas in the ORIGINAL model (even though it is improper)
    4. making it proper and LIFTING the valuation (truth is preserved)
    5. translating it to a simplicial complex (Lemma 2.6: same truth on facets)
    6. the canonical VERTEX-based approach (atoms 1/0/2) and the NU scheme

The scenario: Ana and Beto in a basement with no windows. Outside, the weather
is one of three worlds -- sol (sunny), nubes (cloudy) or lluvia (rainy) -- and
there are two atomic facts:

    p = "it is raining"   true only in world  lluvia
    q = "it is sunny"     true only in world  sol

Ana has a rain sensor: she tells rain apart from the rest, but cannot tell
sunny from cloudy. Beto has nothing: for him the three worlds are
indistinguishable, and he BELIEVES it is sunny -- a belief that will be false
when it rains. Ana declares no beliefs: by the project convention, that means
she believes exactly what she knows.

Usage:
    python3 examples/example_val.py              # prints the six steps
    python3 examples/example_val.py --open       # and opens the figures it generates
"""

import os
import sys

# The examples live one level below the core modules. Put the repository root on
# sys.path so ``python examples/<script>.py`` works from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assignment import (
    assignment_from_model,
    assignment_violations,
    holds as holds_vertices,
    node_value,
    nu_violations,
)
from knowledge_belief import KnowledgeBeliefFrame
from semantics import facet_valuation, holds_kripke, holds_simplicial, lift_valuation
from simplicial import to_simplicial
from visualization import show as _show

ABRIR = "--open" in sys.argv

MUNDOS = ["sol", "nubes", "lluvia"]
AGENTES = ["a", "b"]                      # a = Ana (with sensor), b = Beto
NOMBRE = {"a": "Ana", "b": "Beto"}

# Formulas are TUPLES: ("atom", P) | ("bot",) | ("imp", f, g)
#                      | ("K", agent, f) | ("B", agent, f)
# plus the sugar ("not", f), ("and", f, g), ("or", f, g). They are recursive:
# wherever an f goes, a whole formula can go; that is how modalities nest.
p = ("atom", "p")
q = ("atom", "q")


def banner(titulo: str) -> None:
    print(f"\n{'=' * 74}\n{titulo}\n{'=' * 74}")


def show(*args, **kwargs):
    """Local wrapper so that --open opens each figure as it is generated."""
    kwargs.setdefault("open", ABRIR)
    return _show(*args, **kwargs)


# --------------------------------------------------------------------------- #
# STEP 1 · The model: raw seeds -> complete relations
# --------------------------------------------------------------------------- #
def paso1_modelo() -> KnowledgeBeliefFrame:
    banner("PASO 1 · El modelo (semillas crudas -> relaciones válidas)")

    # Seeds are PARTIAL: we only write the edges we care about and the
    # closures fill in the rest (reflexivity, transitivity, etc.).
    kb = KnowledgeBeliefFrame.from_partial(
        AGENTES, MUNDOS,
        # KNOWLEDGE: Ana cannot tell sol from nubes (a single edge is enough:
        # s5_closure makes it symmetric and reflexive). Beto tells nothing apart.
        knowledge={
            "a": {("sol", "nubes")},
            "b": {("sol", "nubes"), ("nubes", "lluvia")},
        },
        # BELIEF: Beto believes it is sunny, whatever happens. Ana is silent --
        # an EXPLICIT empty set, which is how "no seed" is declared (an agent
        # missing from the dict would be an error, not silence).
        belief={
            "a": set(),
            "b": {(w, "sol") for w in MUNDOS},
        },
    )

    print("Conocimiento -- las clases son lo que cada agente NO puede distinguir:")
    for g in AGENTES:
        clases = sorted({tuple(sorted(kb.knows(g, w))) for w in MUNDOS})
        print(f"    {NOMBRE[g]:5s} R_{g}: " + " | ".join("{" + ", ".join(c) + "}" for c in clases))

    print("\nCreencia -- el cúmulo que cada agente considera posible:")
    for g in AGENTES:
        for w in MUNDOS:
            print(f"    {NOMBRE[g]:5s} en {w:7s} cree {sorted(kb.believes(g, w))}")

    # Ana was silent, and by the project convention that meant Q_a = R_a:
    # "agents believe what they know". The constancy condition already
    # guaranteed the converse (they know what they believe) in every case.
    iguales = all(kb.believes("a", w) == kb.knows("a", w) for w in MUNDOS)
    print(f"\n  Ana calló sobre creencias -> Q_a = R_a ('cree lo que sabe'): {iguales}")
    print(f"  Modelo válido (las 4 condiciones del marco): {kb.is_valid()}")
    return kb


# --------------------------------------------------------------------------- #
# STEP 2 · The logical valuation
# --------------------------------------------------------------------------- #
def paso2_valuacion() -> dict:
    banner("PASO 2 · La valuación lógica  v : P -> 2^W")

    # A Kripke valuation is TOTAL: for each atom it says exactly in which
    # worlds it is true, and it is false in all the others. (Compare with the
    # vertex-based approach of step 6, which is PARTIAL: it admits "don't know".)
    v = {"p": {"lluvia"},       # p = "it is raining"
         "q": {"sol"}}          # q = "it is sunny"

    print("  v(p) = {lluvia}      p = 'llueve'")
    print("  v(q) = {sol}         q = 'hace sol'")
    print("\n  Literales por mundo:")
    for w in MUNDOS:
        lits = [(a if w in ws else "¬" + a) for a, ws in sorted(v.items())]
        print(f"    {w:7s}: {', '.join(lits)}")
    return v


# --------------------------------------------------------------------------- #
# STEP 3 · Evaluating formulas (in the original model, improper as it is)
# --------------------------------------------------------------------------- #
def paso3_formulas(kb, v) -> None:
    banner("PASO 3 · Fórmulas en el modelo original")

    # holds_kripke works on IMPROPER models: properness is a requirement of
    # the simplicial translation, not of truth. So we can ask here, before
    # touching anything.
    real = "lluvia"
    print(f"Supongamos que el mundo real es '{real}' (llueve, no hace sol).\n")

    consultas = [
        ("p",                p,                          "¿llueve?"),
        ("K_a p",            ("K", "a", p),              "¿Ana SABE que llueve?"),
        ("K_b p",            ("K", "b", p),              "¿Beto sabe que llueve?"),
        ("B_a p",            ("B", "a", p),              "¿Ana lo cree?"),
        ("B_b ¬p",           ("B", "b", ("not", p)),     "¿Beto cree que NO llueve?"),
        ("B_b q",            ("B", "b", q),              "¿Beto cree que hace sol?"),
        ("B_b q → q",        ("imp", ("B", "b", q), q),  "¿la creencia de Beto es verdadera?"),
        ("K_a B_b q",        ("K", "a", ("B", "b", q)),  "¿Ana sabe lo que Beto cree?"),
        ("B_b K_a p",        ("B", "b", ("K", "a", p)),  "¿Beto cree que Ana sabe que llueve?"),
    ]
    for etiqueta, formula, glosa in consultas:
        valor = holds_kripke(kb, v, real, formula)
        print(f"    {etiqueta:12s} = {str(valor):5s}   {glosa}")

    print("\n  Lo que enseña este paso:")
    print("    · K_a p verdadero  -> el sensor de Ana es CONOCIMIENTO (factivo).")
    print("    · B_b ¬p verdadero con p verdadero -> CREENCIA FALSA: Beto está")
    print("      seguro de algo que no es el caso. La creencia no es factiva,")
    print("      y eso es exactamente lo que los modelos KD45 permiten expresar.")
    print("    · K_a B_b q verdadero -> introspección fuerte: aunque Ana no sabe")
    print("      qué clima hace, sí sabe lo que Beto cree (la creencia de Beto es")
    print("      constante sobre las clases de conocimiento de todos).")


# --------------------------------------------------------------------------- #
# STEP 4 · Making it proper and lifting the valuation
# --------------------------------------------------------------------------- #
def paso4_propio(kb, v):
    banner("PASO 4 · De impropio a propio (y la valuación viaja con el modelo)")

    print(f"  ¿Es propio? {kb.is_proper()}")
    print(f"    {kb.properness_violations()[0]}")
    print("\n  Impropio = hay dos mundos que TODOS los agentes confunden, así que")
    print("  darían la misma faceta y la traducción no sería fiel. Se arregla")
    print("  copiando el modelo |W| veces y sesgando a un agente distinguido.")

    propio = kb.to_proper()          # default distinguished agent: fewest edges
    print(f"\n  to_proper() -> {propio!r}")
    print(f"    {len(kb.worlds)} mundos -> {len(propio.worlds)} mundos, propio: {propio.is_proper()}")

    # The valuation is LIFTED through the projection: each copy (w, u) inherits
    # the atoms of its original w. So the atoms keep meaning the same thing.
    v2 = lift_valuation(v, propio.projection)
    print(f"\n  Valuación levantada: v'(p) = {sorted(v2['p'])}")
    print("    (las tres copias del mundo 'lluvia' -- y sólo ellas -- cumplen p)")

    # The projection is a bounded morphism, so each copy satisfies EXACTLY
    # the same formulas as its original. We check it.
    formulas = [p, q, ("K", "a", p), ("B", "b", q), ("B", "b", ("not", p)),
                ("K", "a", ("B", "b", q)), ("imp", ("B", "b", q), q)]
    iguales = all(
        holds_kripke(propio, v2, nw, f) == holds_kripke(kb, v, propio.projection[nw], f)
        for f in formulas for nw in propio.worlds
    )
    print(f"\n  ¿Cada copia satisface lo mismo que su original? {iguales}")
    print("    Ése es el sentido de 'bisimilar': el modelo creció, la lógica no cambió.")
    return propio, v2


# --------------------------------------------------------------------------- #
# STEP 5 · The simplicial complex (chapter 2 semantics)
# --------------------------------------------------------------------------- #
def paso5_simplicial(propio, v2):
    banner("PASO 5 · Traducción simplicial y el Lema 2.6")

    sm = to_simplicial(propio)
    print(f"  to_simplicial -> {sm!r}")
    print("    vértice = (clase de conocimiento, agente) = una PERSPECTIVA")
    print("    faceta  = un mundo (un vértice por agente)")
    print("    S_x     = las facetas que el agente x cree posibles (w Q_x w)")
    print(f"\n  Subcomplejos de creencia: "
          + ", ".join(f"|S_{g}| = {len(sm.belief_facets[g])}" for g in AGENTES)
          + f"   (de {len(sm.facets)} facetas)")

    # The chapter 2 facet valuation: L(P) = f[v(P)], the facets of the worlds
    # where the atom holds. It is the EXACT translation (it represents any
    # Kripke valuation).
    L2 = facet_valuation(sm, v2)
    print(f"\n  Valuación de facetas: |L(p)| = {len(L2['p'])} facetas, "
          f"|L(q)| = {len(L2['q'])} facetas")

    # LEMMA 2.6: the translation preserves the truth of EVERY formula.
    formulas = [p, q, ("K", "a", p), ("K", "b", p), ("B", "b", q),
                ("B", "b", ("not", p)), ("K", "a", ("B", "b", q)),
                ("imp", ("B", "b", q), q), ("B", "b", ("K", "a", p))]
    discrepancias = [
        (f, w) for f in formulas for F, w in sm.world_of_facet.items()
        if holds_simplicial(sm, L2, F, f) != holds_kripke(propio, v2, w, f)
    ]
    print(f"\n  Lema 2.6 -- N,w |= φ  sii  M,f(w) |= φ  para las {len(formulas)} fórmulas")
    print(f"  probadas en las {len(sm.facets)} facetas: discrepancias = {len(discrepancias)}")
    print("    La geometría codifica exactamente las relaciones: el complejo NO")
    print("    es un dibujo del modelo, es el modelo en otra presentación.")
    return sm


# --------------------------------------------------------------------------- #
# STEP 6 · The canonical approach: atoms on the VERTICES (1 / 0 / 2)
# --------------------------------------------------------------------------- #
def paso6_vertices(sm, v2):
    banner("PASO 6 · El enfoque por vértices (capítulo 3) y el esquema NU")

    # The project's canonical approach puts atoms on the PERSPECTIVES, not on
    # the facets, and PARTIALLY: 1 = observes it true, 0 = observes it false,
    # 2 = says nothing ("don't know"). A node IS a knowledge class, so the
    # induced assignment reads what the agent KNOWS.
    L3 = assignment_from_model(sm, v2)
    print(f"  Asignación bien formada (sólo valores 0/1/2): "
          f"{not assignment_violations(L3)}")
    print("\n  Qué observa cada perspectiva (una muestra):")
    print(f"    {'perspectiva':32s} {'p':>4s} {'q':>4s}")
    LEYENDA = {1: "1", 0: "0", 2: "2"}
    vistos = set()
    for nodo in sorted(sm.nodes, key=lambda n: (str(n.agent), sorted(map(str, n.cls)))):
        clave = (nodo.agent, frozenset(w[0] for w in nodo.cls))
        if clave in vistos:
            continue
        vistos.add(clave)
        originales = sorted({w[0] for w in nodo.cls})
        etiqueta = f"{NOMBRE[nodo.agent]:5s} sobre {{{', '.join(originales)}}}"
        print(f"    {etiqueta:32s} "
              f"{LEYENDA[node_value(L3, nodo, 'p')]:>4s} "
              f"{LEYENDA[node_value(L3, nodo, 'q')]:>4s}")
    print("      1 = la observa verdadera · 0 = la observa falsa · 2 = no sabe")

    # NU (P -> some agent believes P) is VALID in this semantics: a true atom
    # that NOBODY observes simply does not exist at facet level. That is why
    # some Kripke valuations cannot be represented by this approach.
    print("\n  El esquema NU:  P → (algún agente cree P)")
    for atomo in ("p", "q"):
        malas = nu_violations(sm, L3, {atomo: v2[atomo]})
        mundos = sorted({str(sm.world_of_facet[F][0]) for _, F in malas})
        if malas:
            print(f"    {atomo}: NU FALLA en {len(malas)} facetas (copias de {mundos})")
        else:
            print(f"    {atomo}: NU vale en todas las facetas ✓")

    print("\n  Por qué la diferencia, y es la lección más importante del ejemplo:")
    print("    · p ('llueve') lo SABE Ana siempre -- su sensor separa lluvia de")
    print("      lo demás -- así que alguna perspectiva siempre lo porta, y la")
    print("      verdad de faceta coincide con la del mundo.")
    print("    · q ('hace sol') no lo sabe NADIE en el mundo sol: la clase de Ana")
    print("      {sol, nubes} está mezclada y Beto no distingue nada. Sin testigo,")
    print("      q no es verdadera a nivel de faceta aunque lo sea en el mundo.")
    print("      No es un bug: es NU, el axioma que esta semántica valida.")
    print("\n    Regla práctica: la ruta por vértices y la del capítulo 2 coinciden")
    print("    exactamente donde NU vale; si tu valuación tiene verdades que nadie")
    print("    observa, usa facet_valuation (paso 5), que representa cualquiera.")

    # Check of the agreement, atom by atom, with the chapter 2 evaluator on
    # the same assignment lifted to facets.
    coincide_p = all(
        holds_vertices(sm, L3, F, p) == (sm.world_of_facet[F][0] == "lluvia")
        for F in sm.facets
    )
    print(f"\n  Verificación: verdad-de-faceta de p == verdad-de-mundo: {coincide_p}")
    return L3


# --------------------------------------------------------------------------- #
# STEP 7 · The figures (with the valuation drawn)
# --------------------------------------------------------------------------- #
def paso7_figuras(kb, v, sm, L3) -> None:
    banner("PASO 7 · Figuras con la capa lógica dibujada")
    try:
        r1 = show(kb, "val_kripke", "Modelo original (mundos con sus literales)",
                  valuation=v)
        print(f"  {r1}")
        print("    Cada mundo lleva sus literales debajo del nombre (estilo tesis fig. 33).")
        r2 = show(sm, "val_complejo", "Complejo con lo que observa cada perspectiva",
                  assignment=L3)
        print(f"  {r2}")
        print("    Cada vértice muestra lo que su perspectiva observa; el valor 2 no")
        print("    dibuja nada, así que un vértice desnudo = 'sin información dura'.")
        import hasse
        r3 = hasse.show(sm, "val_reticulo", "Retículo de información",
                        assignment=L3, rankdir="LR", include_empty=False,
                        open=ABRIR)
        print(f"  {r3}")
        print("    El diagrama de Hasse acumula: subir un nivel suma las")
        print("    observaciones, y la fila de arriba es la verdad del mundo.")
    except (ImportError, RuntimeError) as exc:
        print(f"  (figuras omitidas: {type(exc).__name__} -- {str(exc)[:60]})")


def main() -> None:
    kb = paso1_modelo()
    v = paso2_valuacion()
    paso3_formulas(kb, v)
    propio, v2 = paso4_propio(kb, v)
    sm = paso5_simplicial(propio, v2)
    L3 = paso6_vertices(sm, v2)
    paso7_figuras(kb, v, sm, L3)
    print("\n" + "=" * 74)
    print("Resumen: semillas -> relaciones -> valuación -> fórmulas -> modelo")
    print("propio (la verdad se conserva) -> complejo (Lema 2.6) -> vértices (NU).")
    print("=" * 74)


if __name__ == "__main__":
    main()

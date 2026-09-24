# -*- coding: utf-8 -*-
"""Ejemplo mínimo, paso a paso: un modelo CON VALUACIÓN LÓGICA, de punta a punta.

Los demás ejemplos del repo son estructurales (mundos y relaciones). Este añade
la capa que les falta -- los átomos, la verdad y las fórmulas -- y sigue un solo
modelo por los seis pasos del pipeline:

    1. el escenario y las relaciones (semillas crudas)
    2. la valuación lógica  v : P -> 2^W   (qué átomo es verdadero dónde)
    3. evaluar fórmulas en el modelo ORIGINAL (aunque sea impropio)
    4. hacerlo propio y LEVANTAR la valuación (la verdad se conserva)
    5. traducirlo a complejo simplicial (Lema 2.6: misma verdad en las facetas)
    6. el enfoque canónico por VÉRTICES (átomos 1/0/2) y el esquema NU

El escenario: Ana y Beto en un sótano sin ventanas. Afuera el clima es uno de
tres mundos -- sol, nubes o lluvia -- y hay dos hechos atómicos:

    p = "llueve"      verdadero sólo en el mundo  lluvia
    q = "hace sol"    verdadero sólo en el mundo  sol

Ana tiene un sensor de lluvia: distingue lluvia de lo demás, pero no sabe
diferenciar sol de nubes. Beto no tiene nada: para él los tres mundos son
indistinguibles, y CREE que hace sol -- una creencia que será falsa cuando
llueva. Ana no declara creencias: por la convención del proyecto, eso significa
que cree exactamente lo que sabe.

Uso:
    python3 example_val.py              # imprime los seis pasos
    python3 example_val.py --open       # y abre las figuras que genera
"""

import sys

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
AGENTES = ["a", "b"]                      # a = Ana (con sensor), b = Beto
NOMBRE = {"a": "Ana", "b": "Beto"}

# Las fórmulas son TUPLAS: ("atom", P) | ("bot",) | ("imp", f, g)
#                         | ("K", agente, f) | ("B", agente, f)
# más el azúcar ("not", f), ("and", f, g), ("or", f, g). Son recursivas: donde
# va una f puede ir otra fórmula entera, así se anidan las modalidades.
p = ("atom", "p")
q = ("atom", "q")


def banner(titulo: str) -> None:
    print(f"\n{'=' * 74}\n{titulo}\n{'=' * 74}")


def show(*args, **kwargs):
    """Envoltorio local para que --open abra cada figura al generarla."""
    kwargs.setdefault("open", ABRIR)
    return _show(*args, **kwargs)


# --------------------------------------------------------------------------- #
# PASO 1 · El modelo: semillas crudas -> relaciones completas
# --------------------------------------------------------------------------- #
def paso1_modelo() -> KnowledgeBeliefFrame:
    banner("PASO 1 · El modelo (semillas crudas -> relaciones válidas)")

    # Las semillas son PARCIALES: sólo escribimos las aristas que nos importan
    # y las clausuras completan el resto (reflexividad, transitividad, etc.).
    kb = KnowledgeBeliefFrame.from_partial(
        AGENTES, MUNDOS,
        # CONOCIMIENTO: Ana no distingue sol de nubes (una sola arista basta:
        # s5_closure la vuelve simétrica y reflexiva). Beto no distingue nada.
        knowledge={
            "a": {("sol", "nubes")},
            "b": {("sol", "nubes"), ("nubes", "lluvia")},
        },
        # CREENCIA: Beto cree que hace sol, pase lo que pase. Ana calla --
        # conjunto vacío EXPLÍCITO, que es como se declara "sin semilla"
        # (un agente ausente del diccionario sería un error, no un silencio).
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

    # Ana calló, y por la convención del proyecto eso significó Q_a = R_a:
    # "los agentes creen lo que saben". La constancia ya garantizaba el
    # recíproco (saben lo que creen) en todos los casos.
    iguales = all(kb.believes("a", w) == kb.knows("a", w) for w in MUNDOS)
    print(f"\n  Ana calló sobre creencias -> Q_a = R_a ('cree lo que sabe'): {iguales}")
    print(f"  Modelo válido (las 4 condiciones del marco): {kb.is_valid()}")
    return kb


# --------------------------------------------------------------------------- #
# PASO 2 · La valuación lógica
# --------------------------------------------------------------------------- #
def paso2_valuacion() -> dict:
    banner("PASO 2 · La valuación lógica  v : P -> 2^W")

    # Una valuación de Kripke es TOTAL: para cada átomo dice exactamente en qué
    # mundos es verdadero, y en los demás es falso. (Compárese con el enfoque
    # por vértices del paso 6, que es PARCIAL: admite "no sé".)
    v = {"p": {"lluvia"},       # p = "llueve"
         "q": {"sol"}}          # q = "hace sol"

    print("  v(p) = {lluvia}      p = 'llueve'")
    print("  v(q) = {sol}         q = 'hace sol'")
    print("\n  Literales por mundo:")
    for w in MUNDOS:
        lits = [(a if w in ws else "¬" + a) for a, ws in sorted(v.items())]
        print(f"    {w:7s}: {', '.join(lits)}")
    return v


# --------------------------------------------------------------------------- #
# PASO 3 · Evaluar fórmulas (en el modelo original, aunque sea impropio)
# --------------------------------------------------------------------------- #
def paso3_formulas(kb, v) -> None:
    banner("PASO 3 · Fórmulas en el modelo original")

    # holds_kripke funciona en modelos IMPROPIOS: la propiedad es un requisito
    # de la traducción simplicial, no de la verdad. Así que podemos preguntar
    # aquí, antes de tocar nada.
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
# PASO 4 · Hacerlo propio y levantar la valuación
# --------------------------------------------------------------------------- #
def paso4_propio(kb, v):
    banner("PASO 4 · De impropio a propio (y la valuación viaja con el modelo)")

    print(f"  ¿Es propio? {kb.is_proper()}")
    print(f"    {kb.properness_violations()[0]}")
    print("\n  Impropio = hay dos mundos que TODOS los agentes confunden, así que")
    print("  darían la misma faceta y la traducción no sería fiel. Se arregla")
    print("  copiando el modelo |W| veces y sesgando a un agente distinguido.")

    propio = kb.to_proper()          # distinguido por defecto: el de menos aristas
    print(f"\n  to_proper() -> {propio!r}")
    print(f"    {len(kb.worlds)} mundos -> {len(propio.worlds)} mundos, propio: {propio.is_proper()}")

    # La valuación se LEVANTA por la proyección: cada copia (w, u) hereda los
    # átomos de su original w. Así los átomos siguen significando lo mismo.
    v2 = lift_valuation(v, propio.projection)
    print(f"\n  Valuación levantada: v'(p) = {sorted(v2['p'])}")
    print("    (las tres copias del mundo 'lluvia' -- y sólo ellas -- cumplen p)")

    # La proyección es un morfismo acotado, así que cada copia satisface
    # EXACTAMENTE las mismas fórmulas que su original. Lo comprobamos.
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
# PASO 5 · El complejo simplicial (semántica del capítulo 2)
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

    # La valuación de facetas del capítulo 2: L(P) = f[v(P)], las facetas de los
    # mundos donde el átomo vale. Es la traducción EXACTA (representa cualquier
    # valuación de Kripke).
    L2 = facet_valuation(sm, v2)
    print(f"\n  Valuación de facetas: |L(p)| = {len(L2['p'])} facetas, "
          f"|L(q)| = {len(L2['q'])} facetas")

    # LEMA 2.6: la traducción preserva la verdad de TODA fórmula del lenguaje.
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
# PASO 6 · El enfoque canónico: átomos en los VÉRTICES (1 / 0 / 2)
# --------------------------------------------------------------------------- #
def paso6_vertices(sm, v2):
    banner("PASO 6 · El enfoque por vértices (capítulo 3) y el esquema NU")

    # El enfoque canónico del proyecto pone los átomos en las PERSPECTIVAS, no
    # en las facetas, y de forma PARCIAL: 1 = lo observa verdadero, 0 = lo
    # observa falso, 2 = no dice nada ("no sé"). Un nodo ES una clase de
    # conocimiento, así que la asignación inducida lee lo que el agente SABE.
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

    # NU (P -> algún agente cree P) es VÁLIDO en esta semántica: un átomo
    # verdadero que NADIE observa simplemente no existe a nivel de faceta.
    # Por eso hay valuaciones kripkeanas que este enfoque no puede representar.
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

    # Comprobación de la coincidencia, átomo por átomo, con el evaluador del
    # capítulo 2 sobre la misma asignación levantada a facetas.
    coincide_p = all(
        holds_vertices(sm, L3, F, p) == (sm.world_of_facet[F][0] == "lluvia")
        for F in sm.facets
    )
    print(f"\n  Verificación: verdad-de-faceta de p == verdad-de-mundo: {coincide_p}")
    return L3


# --------------------------------------------------------------------------- #
# PASO 7 · Las figuras (con la valuación dibujada)
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

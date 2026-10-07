# poster/

Material gráfico del cartel presentado en el **Coloquio de Lenguajes de
Programación y Lenguajes Formales, 1.ª edición** (Facultad de Ciencias, UNAM,
19–23 de octubre de 2026).

El cartel cubre la **parte estática** de la herramienta: construcción y
validación de modelos relacionales de conocimiento y creencia, y su traducción
a complejos simpliciales. Cuando se diseñó, las acciones simpliciales y la
revisión dinámica (partes 2 y 3 del plan del README principal) estaban solo
especificadas, y aparecen en el cartel como trabajo futuro. Desde entonces la
**regla de revisión** del memo de la NASA está implementada en
`poster-code/revision.py` (es la que calcula `d3_revision.png`, ver «Variantes
con tres agentes»), y
`simplicial_actions.py` tiene el producto con modelos de acción en su versión
de conocimiento (la salida pone `S_a = S`); la creencia y la revisión dentro
del producto siguen pendientes.

## Figuras

La carpeta se organiza así: los scripts están en `poster-code/` (con
`revision.py` y `ejemplo_nasa.py`), las figuras del cartel en `outputs/`, los
escudos y el QR en `images/`, y en `_intermedios/` la variante de cinco mundos
y los renders descartados. Los nombres de archivo de abajo son relativos a
`outputs/`.

Las figuras `desastre_*` ilustran el ejemplo de auxilio en desastre con **dos
agentes**, el mismo que construye `examples/Natural Disaster Example.py` en el
repositorio (las `d3_*` son la versión con tres agentes, más abajo): Alice
reporta por radio que una carretera está libre, la comunicación es intermitente
y Barb puede no haber recibido nada.

| Archivo | Contenido | Cómo se generó |
|---|---|---|
| `desastre_relacional.png` | Modelo relacional con los tres mundos `nS`, `SnR`, `SR`, conocimiento en línea fina y creencia en línea gruesa. | `visualization.show(KBframe, ...)` |
| `desastre_hasse.png` | El mismo modelo traducido a complejo simplicial, dibujado como retícula de caras. La faceta `SnR` es la única marcada «belief: a». | `hasse.show(to_simplicial(KBframe), ...)` |
| `desastre_complejo.png` | El complejo simplicial por **Graphviz**: cada faceta es una arista (dos agentes), con el color de su firma de creencia y el nombre de su mundo. Deja `.dot` editable junto al `.png`. | `visualization.show(Simp, ..., engine="dot")` |
| `desastre_revision.png` | Esquema de la revisión al recibir `¬C`. Sigue siendo un dibujo a mano; la regla ya está implementada en `revision.py` y la figura **calculada** por el código es `d3_revision.png` (tres agentes). | Esquema manual (matplotlib, dentro de `make_figs.py`) |
| `desastre_geometrico.png` | El complejo simplicial dibujado geométricamente: con dos agentes cada faceta es una arista, así que el complejo es el camino `b0 – a0 – b1 – a1` (`SR`, `SnR`, `nS`), cada faceta rellena del color de su firma de creencia y nombrada por su mundo. | `visualization.show(Simp, ...)` |
| `desastre_antes_geometrico.png` / `desastre_despues_geometrico.png` | El mismo dibujo con la valuación de `C` antes y después de `¬C`: cada vértice muestra el literal que observa (`C`, `¬C`, o nada si no lo sabe). | `visualization.show(Simp, ..., valuation=...)` |
| `desastre_antes_relacional.png` | El modelo relacional con la valuación de `C` **antes** del anuncio: `v(C) = {SnR, SR}` (donde Alice mandó `C` la carretera se reporta libre; en `nS` no se mandó nada). Cada mundo lleva su literal. | `visualization.show(KBframe, ..., valuation=...)` |
| `desastre_antes_hasse.png` | El complejo como retícula de caras con la asignación de vértices inducida: `a0` y `b0` saben `C`, `a1` sabe `¬C`, `b1` no sabe nada (sus mundos `SnR` y `nS` difieren). En `SnR` Barb cree `¬C` y `C` es verdadera. | `hasse.show(Simp, ..., assignment=assignment_from_model(Simp, v))` |
| `desastre_antes_complejo.png` / `desastre_despues_complejo.png` | El complejo por Graphviz con la valuación, antes y después de `¬C`. **Son las figuras que usa el cartel**: cada vértice lleva el literal que observa, cada arista su mundo. Con `.dot` al lado. | `visualization.show(Simp, ..., valuation=..., engine="dot")` |
| `desastre_despues_relacional.png` | Tras el anuncio `¬C`, con los valores de `C` invertidos: `v(C) = {nS}`. | igual que la anterior |
| `desastre_despues_hasse.png` | La misma retícula con la asignación invertida. En `SnR` Barb ahora cree `C` y `C` es falsa. | igual que la anterior |

`images/qr_repositorio.png` apunta a `https://github.com/Meijix/SimulationsBelief`.

Todas las figuras que pasan por Graphviz (`*_relacional`, `*_hasse`,
`*_complejo`) dejan su `.dot` en `outputs/`, junto al `.png`: es la fuente que
escribe el propio `show()`, y se puede editar a mano si hace falta retocar una
figura sin volver a correr el modelo. Los `.dot` están git-ignorados (`*.dot`
en el `.gitignore` de la raíz; los `.png` de `outputs/` sí se versionan, porque
el `.gitignore` solo excluye el `/outputs/` de la raíz), así que aparecen solo
después de correr los scripts.

## Las valuaciones de `C` antes y después de `¬C`

`make_figs.py` imprime, mundo por mundo, la comprobación con el evaluador de
`semantics.py`. La creencia falsa de Barb vive en `SnR` en los dos estados:

| Estado | `v(C)` | En `SnR` | Comentario |
|---|---|---|---|
| antes | `{SnR, SR}` | `C` verdadera, `B_b ¬C` | Barb solo considera `nS`, donde no llegó nada, y cree que la carretera no está libre. |
| después | `{nS}` | `C` falsa, `B_b C` | Los valores se invierten con el anuncio; Barb sigue atada a `nS` y ahora cree lo contrario. |

Ninguno de los dos estados viola el esquema NU: en cada mundo alguien (Alice)
sabe el valor de `C`, así que la valuación es representable por vértices.

## Retícula de caras y dibujo geométrico

Con dos agentes las facetas del complejo son aristas, así que hay **tres**
dibujos posibles del mismo complejo:

| Archivo | Motor | Deja `.dot` | Notas |
|---|---|---|---|
| `desastre_*_geometrico.png` | matplotlib (`show`, por defecto) | no | Símplices rellenos; con dos agentes degenera en una línea horizontal, legible pero plana. |
| `desastre_*_complejo.png` | Graphviz (`show(..., engine="dot")`) | **sí** | Vértices coloreados por agente con su literal, aristas por firma de creencia con su mundo. Es el que usa el cartel. |
| `desastre_*_hasse.png` | Graphviz (`hasse.show`) | sí | Retícula de caras: muestra además qué vértices comparten las facetas. Es la forma en que el artículo dibuja los modelos simpliciales. |

`visualization.show` manda los modelos simpliciales a matplotlib por defecto,
que dibuja símplices rellenos pero **no deja fuente editable**. `engine="dot"`
los manda por Graphviz: se pierden las áreas rellenas y se gana un `.dot` que se
puede retocar a mano sin volver a correr el modelo, como el resto de las figuras.

## El modelo del ejemplo

```python
agents = {"a", "b"}
worlds = {"nS", "SnR", "SR"}
frameseed = {"a": {("SnR", "SR"), ("SR", "SnR")},
             "b": {("SnR", "nS")}}

KBframe = KnowledgeBeliefFrame.from_partial(agents, worlds, frameseed, frameseed)
KBframe.is_valid()                        # True
KnowledgeBeliefFrame.is_proper(KBframe)   # True -> se traduce sin pasar por W x W
Simp = to_simplicial(KBframe)
```

Resultado de la traducción: 3 facetas (`SR` = a0 b0, `SnR` = a0 b1, `nS` = a1 b1)
y 4 vértices. `SnR` es la única faceta que el subcomplejo de creencia de `b` no
contiene: ahí Barb cree algo falso.

## Variantes con tres agentes

Con dos agentes el complejo es una línea quebrada; con tres, las facetas son
triángulos y el dibujo geométrico por fin es bidimensional. Por eso hay una
segunda versión de la historia: Ana coordina desde la base (`a`), Beto va con
la brigada (`b`) y Carla está en el hospital (`c`). Ana transmite «el camino
está libre» y el canal puede fallar con cada uno por separado:

| Mundo | Significado |
|---|---|
| `R` | Ana mandó y los dos recibieron |
| `RN` | Ana mandó, Beto recibió, Carla no |
| `NN` | Ana mandó y nadie recibió |
| `nS` | Ana no mandó (porque el camino no está libre) |

Quien no recibe nada cree que no se mandó nada. Lo que se gana con el tercer
agente es creencia de orden superior: en `RN` Carla se equivoca **y** Beto, que
sabe que el camino está libre, no sabe si el hospital se enteró (no distingue
`R` de `RN`). El modelo es válido y propio; el complejo tiene cuatro facetas y
seis vértices.

| Archivo | Contenido | Script |
|---|---|---|
| `d3_relacional.png`, `d3_reticula.png` | Modelo relacional K+B y retícula de caras del modelo de tres agentes. | `Natural Disaster 3 Agents.py` (los escribe en `outputs/`, junto con `d3_geometrico.png`) |
| `d3_geometrico_final.png` | Versión final del complejo geométrico elegida a mano; ningún script la escribe con ese nombre. | — |
| `d3_antes_relacional.png` / `d3_antes_geometrico.png` | Modelo y complejo con `v(C) = {R, RN, NN}`, antes de `¬C`. | `make_figs_3agentes.py` |
| `d3_despues_relacional.png` / `d3_despues_geometrico.png` | Lo mismo con los valores invertidos, `v(C) = {nS}`. | `make_figs_3agentes.py` |
| `d3_revision.png` | **La revisión calculada por el código.** Se anuncia `S` = «Ana sí mandó», verdadero en `R`, `RN`, `NN`: desaparece `nS`, la única faceta que Carla creía desde el mundo real `RN`. `revision.revise_after_announcement(Simp, "c", "nS", {"R", "RN", "NN"})` compara las facetas supervivientes que contienen el vértice de Carla: `NN` comparte una arista (dos vértices) con la perdida y `RN` solo un punto, así que Carla se va a `NN`. Se acerca sin llegar: ese es el punto del cartel. | `make_figs_3agentes.py`, con `visualization.show(..., revision=...)` |
| `_intermedios/d5_relacional.png`, `d5_geometrico.png`, `d5_revision.png` | Variante con **cinco mundos** (`RR`, `RN`, `NR`, `NN`, `nS`): agrega `NR`, donde solo Carla recibe, por si el canal falla por separado para cada receptor. Es una comprobación de la historia, no una figura del cartel; la revisión da el mismo resultado (`NN`). | `make_figs_3agentes_5mundos.py` |

`revision.py` también se puede correr solo
(`python poster/poster-code/revision.py` desde la raíz del repositorio):
imprime la revisión de Carla y de Beto sobre este mismo modelo, sin figuras.

## Regenerar

```bash
python poster/poster-code/make_figs.py                     # desastre_* (dos agentes) -> poster/outputs/
python poster/poster-code/make_figs_3agentes.py            # d3_antes_*, d3_despues_*, d3_revision -> poster/outputs/
python poster/poster-code/make_figs_3agentes_5mundos.py    # d5_* (cinco mundos) -> poster/_intermedios/
python "poster/poster-code/Natural Disaster 3 Agents.py"   # d3_relacional, d3_geometrico, d3_reticula -> poster/outputs/
python poster/poster-code/ejemplo_nasa.py                  # octaedro de la NASA -> outputs/ del directorio actual
```

Requiere Graphviz (`dot`) en el PATH y las dependencias de `requirements.txt`.
Los comandos están escritos desde la raíz del repositorio, pero cada script
agrega la raíz al `sys.path` por su cuenta y calcula su carpeta de salida a
partir de su propia ubicación, así que funcionan desde cualquier directorio y
sin `PYTHONPATH`: `make_figs.py`, `make_figs_3agentes.py` y
`Natural Disaster 3 Agents.py` escriben directamente en `poster/outputs/`, la
variante de cinco mundos en `poster/_intermedios/` y `ejemplo_nasa.py` en
`outputs/` relativo al directorio actual. Los dos `make_figs_3agentes*.py`
importan `revision.py` como vecino de carpeta. La única figura que no escribe
ningún script es `d3_geometrico_final.png`, elegida a mano.

## Escudos e intermedios

Los escudos están en `images/` (con `qr_repositorio.png`): `Escudo UNAM.svg` y
`Logo IIMAS UNAM 50 Aniversario.png`, para los dos huecos del encabezado del
cartel.

`_intermedios/` guarda renders descartados (`desastre_hasse.png`), un parche de
layout (`visualization_layout.patch`) y las figuras `d5_*` de la variante de
cinco mundos; estas últimas las escribe `make_figs_3agentes_5mundos.py`, así que
la carpeta ya no es solo material desechable.

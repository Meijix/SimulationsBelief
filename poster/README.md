# poster/

Material gráfico del cartel presentado en el **Coloquio de Lenguajes de
Programación y Lenguajes Formales, 1.ª edición** (Facultad de Ciencias, UNAM,
19–23 de octubre de 2026).

El cartel cubre la **parte estática** de la herramienta: construcción y
validación de modelos relacionales de conocimiento y creencia, y su traducción
a complejos simpliciales. Las acciones simpliciales y la revisión dinámica
(partes 2 y 3 del plan del README principal) están especificadas pero aún no
implementadas, y aparecen en el cartel sólo como trabajo futuro.

## Figuras

Las tres figuras ilustran el ejemplo de auxilio en desastre, el mismo que
construye `Natural Disaster Example.py` en la raíz del repositorio: Alice
reporta por radio que una carretera está libre, la comunicación es intermitente
y Barb puede no haber recibido nada.

| Archivo | Contenido | Cómo se generó |
|---|---|---|
| `desastre_relacional.png` | Modelo relacional con los tres mundos `nS`, `SnR`, `SR`, conocimiento en línea fina y creencia en línea gruesa. | `visualization.show(KBframe, ...)` |
| `desastre_simplicial.png` | El mismo modelo traducido a complejo simplicial, dibujado como retícula de caras. La faceta `SnR` es la única marcada «belief: a». | `hasse.show(to_simplicial(KBframe), ...)` |
| `desastre_revision.png` | Esquema de la revisión al recibir `¬C`. **Regla especificada, aún no implementada.** | Esquema manual (matplotlib) |
| `desastre_geometrico.png` | El complejo simplicial dibujado geométricamente: con dos agentes cada faceta es una arista, así que el complejo es el camino `b0 – a0 – b1 – a1` (`SR`, `SnR`, `nS`), cada faceta rellena del color de su firma de creencia y nombrada por su mundo. | `visualization.show(Simp, ...)` |
| `desastre_antes_geometrico.png` / `desastre_despues_geometrico.png` | El mismo dibujo con la valuación de `C` antes y después de `¬C`: cada vértice muestra el literal que observa (`C`, `¬C`, o nada si no lo sabe). | `visualization.show(Simp, ..., valuation=...)` |
| `desastre_antes_relacional.png` | El modelo relacional con la valuación de `C` **antes** del anuncio: `v(C) = {SnR, SR}` (donde Alice mandó `C` la carretera se reporta libre; en `nS` no se mandó nada). Cada mundo lleva su literal. | `visualization.show(KBframe, ..., valuation=...)` |
| `desastre_antes_simplicial.png` | El complejo con la asignación de vértices inducida: `a0` y `b0` saben `C`, `a1` sabe `¬C`, `b1` no sabe nada (sus mundos `SnR` y `nS` difieren). En `SnR` Barb cree `¬C` y `C` es verdadera. | `hasse.show(Simp, ..., assignment=assignment_from_model(Simp, v))` |
| `desastre_despues_relacional.png` | Tras el anuncio `¬C`, con los valores de `C` invertidos: `v(C) = {nS}`. | igual que la anterior |
| `desastre_despues_simplicial.png` | El mismo complejo con la asignación invertida. En `SnR` Barb ahora cree `C` y `C` es falsa. | igual que la anterior |

`qr_repositorio.png` apunta a `https://github.com/Meijix/SimulationsBelief`.

Los `.dot` que acompañan a las dos primeras figuras son la fuente Graphviz que
deja el propio `show()`; se pueden editar a mano si hace falta retocar una
figura sin volver a correr el modelo.

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

Con dos agentes las facetas del complejo son aristas y el dibujo geométrico de
`visualization.show` es un camino: `visualization` lo endereza en horizontal
(`desastre_geometrico.png`), legible pero plano. La retícula de caras
(`hasse.py`) muestra además qué vértices comparten las facetas, y es la forma en
que el artículo dibuja los modelos simpliciales; por eso el cartel usa la
retícula y el dibujo geométrico queda como complemento.

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

## Regenerar

```bash
python poster/make_figs.py
```

Requiere Graphviz (`dot`) en el PATH y las dependencias de `requirements.txt`.

## Pendiente de subir

Los escudos de la UNAM y del IIMAS no se incluyen aquí por licencia; hay que
colocarlos a mano en los dos huecos del encabezado del cartel.

`_intermedios/` guarda renders descartados; se puede borrar.

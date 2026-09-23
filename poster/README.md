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

`qr_repositorio.png` apunta a `https://github.com/Meijix/SimulationsBelief`.

Los `.dot` que acompañan a las dos primeras figuras son la fuente Graphviz que
deja el propio `show()`; se pueden editar a mano si hace falta retocar una
figura sin volver a correr el modelo.

## Por qué la figura 2 es una retícula de caras

Con dos agentes las facetas del complejo son aristas, y el dibujo geométrico de
`visualization.show` colapsa en una línea recta: los cuatro vértices quedan
alineados y la figura no se entiende. La retícula de caras (`hasse.py`) es
además la forma en que el artículo dibuja los modelos simpliciales.

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

"""GUI web del proyecto (NiceGUI): construir un modelo y correr el pipeline completo.

Run:  .venv/bin/python gui/app.py     (abre http://localhost:8080 en el navegador)

POR QUÉ NICEGUI Y ESTA FORMA. La GUI es una herramienta de investigación de un
solo usuario, así que se eligió el stack que reutiliza TODO lo existente con el
mínimo de piezas nuevas: NiceGUI es 100 % Python (los módulos del núcleo se
importan directo, sin API ni serialización), corre en el navegador (las figuras
plotly 3D ya son HTML y se embeben tal cual), y una página basta.

SISTEMA VISUAL. Sigue al cartel del proyecto ("La geometría de una creencia
falsa… y por qué importa", Coloquio de Lenguajes, UNAM 2026), para que la
herramienta y su presentación se vean como una sola cosa:

    * Fondo: azul marino casi negro (``POSTER["page"]``) con un campo de
      estrellas sutil hecho sólo con gradientes CSS (sin imágenes). Las
      superficies (tarjetas, cabecera) son un marino un poco más claro con
      borde blanco translúcido; NO hay sombras grises, la única "elevación"
      es el halo verde lima de la vista previa (el elemento vivo).
    * Tipografía: Inter para la interfaz, JetBrains Mono para fórmulas y
      diagramas (Google Fonts). Tres niveles fijos: EYEBROW de tarjeta en
      versalitas naranja con tracking amplio (``_card_title``; es la línea
      "COLOQUIO DE …" del cartel), contenido en blanco/gris claro, y notas
      text-xs gris.
    * Color: el primario es el VERDE LIMA del cartel (la línea divisoria y el
      octaedro), reservado al botón "Correr pipeline", a la regla bajo la
      cabecera y al halo de la vista previa. Los seis anillos del arcoíris
      del cartel dan los colores DE ROL (``POSTER``): verde = válido / ok,
      amarillo = por completar, rosa = rechazado / error, cian = completado
      por una clausura, azul = información. Cada agente sigue llevando en
      sus chips el MISMO color Okabe-Ito que sus aristas en las figuras
      (``agent_color_map``): ese hilo entre editor y resultados no cambia.
    * Cabecera: marino con regla inferior verde lima; a la derecha, los
      anillos concéntricos con el octaedro (SVG inline, recortado por el
      borde como en el cartel) y a la izquierda el pequeño sello de anillos
      rosa/amarillo como logotipo.
    * Figuras: cada una sobre una "lámina" clara (los PNG de Graphviz tienen
      fondo blanco) con leyenda en itálica debajo, estilo figura de artículo,
      limitada en alto y ampliable a pantalla completa con un clic (lightbox).
    * Métricas de la corrida como stat-tiles (número grande + etiqueta), no
      como bitácora de texto.

CÓMO SE INGRESAN LOS MODELOS. Todo es interactivo y se propaga en cadena:

    * El TIPO DE MODELO (selector arriba del editor) elige qué construye el
      núcleo: conocimiento y creencia (KnowledgeBeliefFrame, pipeline
      completo), sólo conocimiento (RelationalFrame S5, pipeline completo
      con S_a = S) o sólo creencia (RelationalFrame KD45/K45: sin propiedad
      ni traducción simplicial, el pipeline termina en el paso 1 y lo dice).
      Las filas del editor cambian de significado con él, y los
      interruptores que no aplican se deshabilitan (``sync_switches``).

    * AGENTES y MUNDOS se agregan tecleando CUALQUIER nombre en su campo y
      pulsando Enter (o el botón +); cada uno aparece como chip removible.
      Se eligió campo + botón en lugar del modo "valores nuevos" del selector
      de Quasar porque este último exige un Enter en el momento justo y falla
      en silencio -- exactamente lo contrario de un control para agregar.
    * Por agente se dibujan sus CLASES DE CONOCIMIENTO (chips con los mundos
      indistinguibles) y, dentro de cada clase, los MUNDOS QUE CREE (selector
      restringido a esa clase): las entradas inválidas son *inexpresables*.
      Mundos fuera de toda clase quedan como clases unitarias; creencia vacía
      significa "cree lo que sabe" (KD45) o creencia difunta (K45).
    * Los ÁTOMOS declaran la valuación v (en qué mundos es verdadero cada
      uno); con átomos, las figuras etiquetan mundos/vértices con sus
      literales y se habilita el EVALUADOR DE FÓRMULAS (K_a, B_a, ¬ & | ->).
    * Una VISTA PREVIA EN VIVO dibuja el modelo TAL COMO ESTÁ INGRESADO en
      cada cambio, sin clausuras; su chip de validez resume lo que falta.
      El pipeline corre solo al pedirlo, con spinner y botón bloqueado
      (el trabajo pesado va por run.io_bound para no congelar la interfaz).
    * La BIBLIOTECA DE EJEMPLOS (cabecera) carga estados completos del editor.

QUÉ HAY EN ESTE ARCHIVO -- solo presentación. Toda la lógica vive en
``gui/adapters.py``; este archivo la consume y muestra resultados ya aplanados
(rutas de archivo y strings). Esa frontera mantiene el núcleo intacto.

CÓMO SE MUESTRAN LAS FIGURAS. ``visualization.show`` escribe PNG/HTML en
``outputs/``; esa carpeta se sirve como estáticos y cada URL lleva
``?v=<mtime>`` como rompe-caché, porque cada corrida sobreescribe los mismos
nombres de archivo.
"""

from __future__ import annotations

import copy
import html
import shutil
import traceback

from nicegui import app, run as io, ui

# Import plano a propósito: al ejecutar ``python gui/app.py`` esta carpeta es
# sys.path[0], y adapters se encarga de poner la raíz del repo en el path.
from adapters import (
    EXAMPLES,
    KINDS,
    OUTPUTS,
    agent_color_map,
    evaluate_formula,
    preview_figure,
    run_pipeline_from_seeds,
    seeds_from_editor,
)

# Las figuras generadas se sirven directamente desde outputs/ -- la GUI no copia
# ni administra archivos propios, comparte los artefactos con los scripts CLI.
OUTPUTS.mkdir(exist_ok=True)
app.add_static_files("/outputs", str(OUTPUTS))

# Paleta del cartel. Tomada a ojo de la imagen: los seis anillos del
# arcoíris (de afuera hacia adentro), el verde lima de la regla/octaedro, el
# naranja de la línea superior y los dos marinos (página y superficie).
# Se usa tanto en el CSS de abajo como en los chips/iconos de rol.
POSTER = {
    "page": "#0a0e1f",      # fondo de página (marino casi negro)
    "surface": "#121833",   # tarjetas y cabecera
    "line": "rgba(255,255,255,.10)",  # bordes de tarjeta
    "lime": "#c9ee6b",      # regla, octaedro, botón primario
    "orange": "#f4a531",    # eyebrows (línea "COLOQUIO DE …")
    "green": "#79c94b",     # anillo 1 · rol: válido / ok
    "yellow": "#f7d94c",    # anillo 2 · rol: por completar
    "pink": "#ec4b8a",      # anillo 3 · rol: rechazado / error
    "purple": "#8a5cf5",    # anillo 4 · decorativo
    "blue": "#3d7bf6",      # anillo 5 · rol: información
    "cyan": "#38d6f0",      # anillo 6 · rol: completado por clausura
}

# Clase base de TODAS las tarjetas: planas, con borde translúcido sobre marino
# y esquinas amplias (el halo queda reservado a la vista previa, ver
# "SISTEMA VISUAL" arriba). ``poster-card`` está definida en HEAD_HTML.
CARD = "w-full rounded-xl poster-card"
FLAT = "flat"


def _rings_svg(size: int, colors: list, center: str, octa: bool) -> str:
    """Anillos concéntricos del cartel como SVG inline.

    ``colors`` va de afuera hacia adentro, cada anillo con el mismo grosor;
    ``center`` es el color del disco central y ``octa`` dibuja encima el
    octaedro en alambre verde lima (la figura del cartel: un complejo
    simplicial visto como poliedro). Se genera aquí, y no como archivo,
    para que la GUI no dependa de ningún recurso estático propio.
    """
    r = size / 2
    # Como en el cartel, el disco central ocupa algo más de la mitad del radio
    # y los anillos se reparten el resto en partes iguales.
    core = r * 0.55
    step = (r - core) / len(colors)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
             f'width="{size}" height="{size}">']
    for i, c in enumerate(colors):
        parts.append(f'<circle cx="{r}" cy="{r}" r="{r - i * step:.1f}" fill="{c}"/>')
    parts.append(f'<circle cx="{r}" cy="{r}" r="{core:.1f}" fill="{center}"/>')
    if octa:
        # Octaedro en proyección: cuadrado "ecuatorial" ligeramente inclinado
        # con los dos vértices polares arriba y abajo, todo en alambre. Cabe
        # en la banda de la cabecera (ver .poster-header min-height).
        k = core * 0.45
        top, bot = (r, r - k), (r, r + k)
        eq = [(r - k * 0.9, r + k * 0.15), (r - k * 0.25, r + k * 0.45),
              (r + k * 0.9, r - k * 0.15), (r + k * 0.25, r - k * 0.45)]
        stroke = f'stroke="{POSTER["lime"]}" stroke-width="1" fill="none" opacity=".9"'
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in eq)
        parts.append(f'<polygon points="{pts}" {stroke}/>')
        for x, y in eq:
            parts.append(f'<line x1="{top[0]}" y1="{top[1]:.1f}" x2="{x:.1f}" y2="{y:.1f}" {stroke}/>')
            parts.append(f'<line x1="{bot[0]}" y1="{bot[1]:.1f}" x2="{x:.1f}" y2="{y:.1f}" {stroke}/>')
    parts.append("</svg>")
    return "".join(parts)


# Los dos motivos gráficos del cartel: el gran arcoíris con el octaedro (se
# recorta por el borde derecho de la cabecera, como en el cartel) y el sello
# pequeño rosa/amarillo que sirve de logotipo junto al título.
RINGS_BIG = _rings_svg(
    320,
    [POSTER["green"], POSTER["yellow"], POSTER["pink"], POSTER["purple"],
     POSTER["blue"], POSTER["cyan"]],
    center="#0b1330", octa=True,
)
RINGS_SMALL = _rings_svg(
    36, [POSTER["pink"], POSTER["yellow"]], center="#d63d8a", octa=False,
)

# Tipografías + el CSS que Tailwind/Quasar no cubren: el campo de estrellas
# (sólo gradientes radiales repetidos, sin imágenes), las superficies marino,
# el halo lima de la vista previa, la scrollbar fina y el punto pulsante.
HEAD_HTML = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --p-page: {POSTER["page"]}; --p-surface: {POSTER["surface"]};
    --p-line: {POSTER["line"]}; --p-lime: {POSTER["lime"]};
    --p-orange: {POSTER["orange"]}; --p-pink: {POSTER["pink"]};
  }}
  body {{ font-family: 'Inter', 'Roboto', sans-serif; }}
  .font-mono, pre, code {{ font-family: 'JetBrains Mono', 'Fira Mono', monospace; }}

  /* Campo de estrellas: cuatro capas de puntos con periodos distintos para
     que no se note la repetición; fijo para que no se mueva con el scroll. */
  body.body--dark {{
    background-color: var(--p-page);
    background-image:
      radial-gradient(circle at 12% 18%, rgba(255,255,255,.55) 0 1px, transparent 1.6px),
      radial-gradient(circle at 71% 63%, rgba(255,255,255,.35) 0 1px, transparent 1.6px),
      radial-gradient(circle at 43% 86%, rgba(255,255,255,.45) 0 .7px, transparent 1.3px),
      radial-gradient(circle at 88% 27%, rgba(255,255,255,.30) 0 1.2px, transparent 1.8px);
    background-size: 640px 640px, 420px 420px, 530px 530px, 770px 770px;
    background-attachment: fixed;
  }}

  /* Superficies: marino con borde translúcido; sin sombra (planas). */
  .poster-card {{ background: var(--p-surface) !important; border: 1px solid var(--p-line); box-shadow: none !important; }}
  /* La vista previa es la única con elevación: un halo verde lima. */
  .poster-live {{ border-color: rgba(201,238,107,.45);
                  box-shadow: 0 0 0 1px rgba(201,238,107,.25), 0 10px 40px rgba(201,238,107,.10) !important; }}
  /* Error del núcleo / bug: tinte rosa (el anillo "rechazado"). */
  .poster-bad {{ background: rgba(236,75,138,.10) !important; border-color: rgba(236,75,138,.45); }}
  /* Lámina clara para las figuras (PNG con fondo blanco). */
  .fig-frame {{ background: #f4f5f9; border-radius: .5rem; padding: .75rem; }}
  /* Eyebrow de tarjeta: la línea naranja del cartel. */
  .eyebrow {{ color: var(--p-orange); font-size: .68rem; font-weight: 600;
              letter-spacing: .18em; text-transform: uppercase; }}
  /* Cabecera: marino, regla lima abajo, y el arcoíris recortado a la derecha.
     OJO: sin ``position``: Quasar la deja ``fixed`` (que ya sirve de
     contenedor a los anillos absolutos); ponerle ``relative`` la metía en el
     flujo y duplicaba su alto como hueco bajo ella. */
  .poster-header {{ background: var(--p-surface) !important; border-bottom: 2px solid var(--p-lime);
                    overflow: hidden; min-height: 88px; }}
  /* Centro del arcoíris a 60px del borde derecho y a media altura (44px):
     se ve media rueda con el octaedro entero, recortada como en el cartel. */
  .poster-rings {{ position: absolute; right: -100px; top: -116px; width: 320px; height: 320px;
                   pointer-events: none; opacity: .95; }}
  .poster-seal {{ width: 36px; height: 36px; flex: none; }}

  .thin-scroll::-webkit-scrollbar {{ width: 6px; }}
  .thin-scroll::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,.18); border-radius: 3px; }}
  .thin-scroll::-webkit-scrollbar-track {{ background: transparent; }}
  .pulse-dot {{ width: 8px; height: 8px; border-radius: 9999px; background: var(--p-lime);
               animation: pulse 2s infinite; }}
  @keyframes pulse {{
    0%   {{ box-shadow: 0 0 0 0 rgba(201,238,107,.6); }}
    70%  {{ box-shadow: 0 0 0 6px rgba(201,238,107,0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(201,238,107,0); }}
  }}
</style>
"""


def _url(path) -> str:
    """URL estática de una figura, con el mtime como rompe-caché (ver docstring)."""
    return f"/outputs/{path.name}?v={int(path.stat().st_mtime)}"


def _figure_img(path) -> None:
    """Un ``<img>`` que se ajusta a su contenido dentro de la lámina.

    Se usa un img plano y no ``ui.image``: q-img es una caja de proporción
    fija que, con ``fit=contain`` y ancho completo, centraba la figura en un
    rectángulo de 420px y dejaba franjas vacías arriba/abajo o a los lados.
    Con ``width/height:auto`` y sólo máximos, la lámina mide lo que mide la
    figura y la leyenda queda pegada debajo.
    """
    ui.html(
        f'<img src="{_url(path)}" style="display:block;margin:0 auto;'
        'max-width:100%;max-height:520px;width:auto;height:auto">'
    ).classes("w-full")


def _card_title(text: str) -> None:
    """Título de tarjeta del sistema visual: eyebrow naranja en versalitas."""
    ui.label(text).classes("eyebrow")


# Chips de ROL. Los cuatro tonos son anillos del arcoíris del cartel: fondo
# translúcido del color y texto del mismo color, legible sobre marino (los
# pastel de Quasar -- green-1, red-1... -- se veían lavados en oscuro).
_TONES = {
    "ok": POSTER["green"], "warn": POSTER["yellow"],
    "bad": POSTER["pink"], "done": POSTER["cyan"], "info": POSTER["blue"],
}


def _tint(hex_color: str, alpha: float) -> str:
    """``#rrggbb`` -> ``rgba(r,g,b,alpha)``: fondo translúcido del mismo tono."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def _chip(text: str, tone: str, icon=None):
    """Chip de estado con un tono de rol (ver ``_TONES``).

    El color va por el parámetro ``color`` (NiceGUI acepta CSS y lo aplica
    como estilo) y no por ``.style()``: el ``bg-primary`` que Quasar añade
    por defecto lleva ``!important`` y pisaría cualquier estilo inline.
    """
    c = _TONES[tone]
    return ui.chip(text, icon=icon, color=_tint(c, .18), text_color=c) \
        .classes("font-semibold")


# --------------------------------------------------------------------------- #
# Página única. @ui.page es el patrón de NiceGUI 3: la función corre UNA VEZ
# POR CLIENTE al visitar la ruta, y todo el estado vive como cierre local --
# cada pestaña del navegador tiene su propio modelo en edición.
# --------------------------------------------------------------------------- #
@ui.page("/")
def index() -> None:
    # Identidad visual (dentro de la página: NiceGUI 3 prohíbe UI en scope
    # global cuando se usa @ui.page).
    # Modo oscuro de Quasar (inputs, selectores, diálogos y notificaciones
    # toman el tema solos); la paleta mapea los roles al cartel. ``dark`` y
    # ``dark_page`` son los marinos de superficie y de página.
    ui.dark_mode().enable()
    ui.colors(
        primary=POSTER["lime"], secondary=POSTER["cyan"], accent=POSTER["pink"],
        dark=POSTER["surface"], dark_page=POSTER["page"],
        positive=POSTER["green"], negative=POSTER["pink"],
        warning=POSTER["yellow"], info=POSTER["blue"],
    )
    ui.add_head_html(HEAD_HTML)

    # TODO el modelo dibujado vive en este dict plano (no en los widgets):
    # los widgets solo lo PINTAN y la conversión a semillas es una función
    # pura de adapters. Un solo dueño del estado evita sincronización
    # widget-a-widget. Se arranca con el ejemplo de la tesis.
    state = {
        "agents": [], "worlds": [], "per_agent": {},
        "atoms": {},  # atomo -> mundos donde es VERDADERO (la valuacion v)
        # Tipo de modelo (clave de adapters.KINDS): decide qué construye el
        # núcleo, qué columnas tiene el editor y hasta dónde llega el pipeline.
        "kind": "kb",
    }

    def load_example(key: str) -> None:
        """Carga un estado completo de la biblioteca (deepcopy: editable)."""
        ex = copy.deepcopy(EXAMPLES[key])
        state["agents"] = ex["agents"]
        state["worlds"] = ex["worlds"]
        state["per_agent"] = ex["per_agent"]
        state["atoms"] = ex["atoms"]
        # El tipo se fija en el estado ANTES de mover el selector: así el
        # on_change del selector (set_kind) ve que no hay cambio y no repinta
        # a medias; la sincronización y el repintado se hacen aquí, una vez.
        state["kind"] = ex.get("kind", "kb")
        kind_in.value = state["kind"]
        axiom_d_in.value = ex["axiom_d"]
        sync_switches()
        repaint_all()

    # ---- Lightbox: cualquier figura, a pantalla completa con un clic ------- #
    with ui.dialog().props("maximized") as lightbox:
        with ui.column().classes(
            "w-full h-full items-center justify-center bg-black cursor-zoom-out"
        ) as lb_body:
            lb_img = ui.image().classes("max-w-[92vw] max-h-[86vh]") \
                .props("fit=contain")
            lb_cap = ui.label().classes("text-white text-sm italic mt-2")
        lb_body.on("click", lightbox.close)

    def open_lightbox(path, caption: str) -> None:
        lb_img.set_source(_url(path))
        lb_cap.set_text(caption)
        lightbox.open()

    def figure_card(caption: str, path) -> None:
        """Figura estilo artículo: marco gris, leyenda en itálica, clic amplía."""
        with ui.card().classes(CARD).props(FLAT):
            holder = ui.element("div").classes(
                "w-full fig-frame cursor-zoom-in"
            )
            with holder:
                _figure_img(path)
            holder.on("click", lambda p=path, c=caption: open_lightbox(p, c))
            ui.label(caption).classes("text-xs italic text-grey-5 mt-2")

    # ---- Cabecera: marino con regla lima, sello + arcoíris del cartel ----- #
    # wrap=False: con el ``wrap`` por defecto Quasar medía la cabecera
    # envuelta en dos filas y dejaba un hueco de ~60px bajo ella.
    with ui.header(wrap=False).classes(
        "poster-header text-white items-center justify-between px-6 py-3 "
        "shadow-none"
    ):
        # Arcoíris con octaedro, recortado por el borde derecho como en el
        # cartel; va primero para quedar debajo de los controles.
        ui.html(RINGS_BIG).classes("poster-rings")
        with ui.row().classes("items-center gap-3 no-wrap"):
            ui.html(RINGS_SMALL).classes("poster-seal")
            with ui.column().classes("gap-0"):
                ui.label("La geometría de una creencia falsa") \
                    .classes("text-xl font-extrabold text-white leading-tight")
                ui.label("Una herramienta para construir, validar y traducir "
                         "modelos de lógica epistémica · pipeline general → "
                         "propio → simplicial") \
                    .classes("text-xs italic text-grey-4")
        with ui.row().classes("items-center gap-3 relative"):
            ui.select(
                {k: ex["label"] for k, ex in EXAMPLES.items()},
                value=None, label="cargar ejemplo",
                on_change=lambda e: load_example(e.value),
            ).props("dense outlined options-dense").classes("min-w-[360px]")
            # Lima con texto marino: el único botón lleno de la página.
            run_btn = ui.button("Correr pipeline", icon="play_arrow",
                                on_click=lambda: run_clicked()) \
                .props("color=primary text-color=dark unelevated") \
                .classes("font-bold")

    with ui.row().classes("w-full no-wrap items-start gap-4 p-4"):

        # ---- Panel de edición: sticky con scroll propio (scrollbar fina) --- #
        with ui.column().classes(
            "w-[440px] shrink-0 gap-4 sticky top-2 self-start "
            "max-h-[calc(100vh-110px)] overflow-y-auto pr-1 thin-scroll"
        ):
            # ---- Identificadores ------------------------------------------- #
            with ui.card().classes(CARD).props(FLAT):
                _card_title("Agentes y mundos")
                # Los tres tipos de modelo del núcleo. Cambiarlo repinta el
                # editor (las filas cambian de significado), ajusta qué
                # interruptores aplican y rehace la vista previa.
                kind_in = ui.select(
                    KINDS, value="kb", label="tipo de modelo",
                    on_change=lambda e: set_kind(e.value),
                ).props("dense outlined options-dense").classes("w-full")
                with ui.row().classes("w-full no-wrap items-center gap-2"):
                    agent_input = ui.input("nuevo agente") \
                        .props("dense outlined").classes("grow")
                    ui.button(icon="add", on_click=lambda: add_agent()) \
                        .props("round dense")
                agent_chips = ui.row().classes("w-full gap-2")
                agent_input.on("keydown.enter", lambda: add_agent())

                with ui.row().classes("w-full no-wrap items-center gap-2 mt-2"):
                    world_input = ui.input("nuevo mundo") \
                        .props("dense outlined").classes("grow")
                    ui.button(icon="add", on_click=lambda: add_world()) \
                        .props("round dense")
                world_chips = ui.row().classes("w-full gap-2")
                world_input.on("keydown.enter", lambda: add_world())

                # El interruptor KD45/K45 del núcleo (axiom_d), expuesto tal
                # cual: apagarlo legaliza las creencias difuntas (Q_a(w) = ∅).
                axiom_d_in = ui.switch("Axioma D (KD45; apagado = K45)",
                                       value=True)

                # Apagar el Axioma D sólo LEGALIZA la creencia difunta; no la
                # produce. La convención del proyecto es que el silencio sobre
                # la creencia significa "cree exactamente lo que sabes"
                # (Q = R), en ambas lógicas, y que lo difunto es opt-in
                # explícito. Sin esta casilla el opt-in no existía en la GUI:
                # K45 quedaba indistinguible de KD45 y B_a ⊥ era inalcanzable.
                # Es global (así es el flag del núcleo): afecta a TODA clase
                # sin creencia marcada.
                silent_defunct_in = ui.switch(
                    "Creencia vacía si no se marca nada (Q = ∅)", value=False,
                )
                ui.label(
                    "Sólo con K45. Apagada, una clase sin creencia marcada "
                    "cree lo que sabe (Q = R)."
                ).classes("text-xs text-grey-5 -mt-2")

                def _reset_silent_defunct() -> None:
                    """KD45 prohíbe Q = ∅: al volver a KD45 la casilla se apaga.

                    Dejarla marcada pero deshabilitada mandaría al núcleo una
                    combinación que éste rechaza, y el usuario vería un error de
                    validación por una casilla que ya no puede ver activa.
                    """
                    if axiom_d_in.value:
                        silent_defunct_in.value = False

                # Cambiar la lógica repinta la vista previa: la lista "por
                # completar" y los mundos en rojo salen del contrato del
                # marco (KD45 exige seriedad, K45 no), así que sin repintar
                # la vista previa seguía juzgando con el axioma anterior.
                axiom_d_in.on_value_change(lambda _: _reset_silent_defunct())
                axiom_d_in.on_value_change(lambda _: sync_switches())
                axiom_d_in.on_value_change(lambda _: update_preview())

                # Las figuras relacionales omiten lo que la lógica ya implica:
                # los lazos reflexivos y la segunda flecha de cada par
                # simétrico (S5 se dibuja sin dirección). Este interruptor
                # los dibuja todos, tal cual están en la relación: es la
                # forma de VER lo que las clausuras añadieron. Repinta la
                # vista previa al instante y, si ya hay resultados, vuelve a
                # correr el pipeline para que las Figuras 1 y 2 coincidan.
                explicit_in = ui.switch(
                    "Mostrar aristas implícitas (lazos y simetría)", value=False,
                    on_change=lambda _: explicit_changed(),
                )
                ui.label(
                    "Dibuja los lazos reflexivos y ambas direcciones de cada "
                    "par simétrico en vez de darlos por sobreentendidos."
                ).classes("text-xs text-grey-5 -mt-2")

            # ---- Editor de relaciones por agente --------------------------- #
            editor_box = ui.column().classes("w-full gap-4")

            # ---- Átomos: la valuación v (dónde es verdadero cada átomo) ---- #
            with ui.card().classes(CARD).props(FLAT):
                _card_title("Átomos (proposiciones)")
                ui.markdown(
                    "Declara cada átomo y en qué mundos es **verdadero**. Con "
                    "átomos, las figuras etiquetan los mundos con sus "
                    "literales y puedes evaluar fórmulas."
                ).classes("text-xs text-grey-5")
                with ui.row().classes("w-full no-wrap items-center gap-2"):
                    atom_input = ui.input("nuevo átomo") \
                        .props("dense outlined").classes("grow")
                    ui.button(icon="add", on_click=lambda: add_atom()) \
                        .props("round dense")
                atom_input.on("keydown.enter", lambda: add_atom())
                atoms_box = ui.column().classes("w-full gap-2")

            # ---- Evaluador de fórmulas ------------------------------------- #
            with ui.card().classes(CARD).props(FLAT):
                _card_title("Evaluar fórmula")
                formula_input = ui.input(
                    "fórmula", placeholder="B_a p & ~K_a p",
                ).props("dense outlined input-class=font-mono").classes("w-full")
                ui.markdown(
                    "Sintaxis: átomos declarados, `K_a`, `B_a`, `~`/`¬`, `&`, "
                    "`|`, `->`, `bot`, paréntesis. Se evalúa **mundo por "
                    "mundo** sobre el modelo ya completado por las clausuras."
                ).classes("text-xs text-grey-5")
                ui.button("Evaluar", icon="calculate",
                          on_click=lambda: eval_formula()) \
                    .props("outline dense")
                formula_input.on("keydown.enter", lambda: eval_formula())
                formula_out = ui.column().classes("w-full gap-2")

        with ui.column().classes("grow min-w-0 gap-4"):
            # ---- Vista previa en vivo (siempre visible, arriba) ------------ #
            preview_box = ui.column().classes("w-full")
            # ---- Salida del pipeline: se reconstruye en cada corrida ------- #
            results = ui.column().classes("w-full gap-4")

    # ----------------------------------------------------------------------- #
    # Altas y bajas de identificadores y átomos. Cada operación muta ``state``
    # y repinta chips + editor + átomos + vista previa; no hay más sincronía.
    # ----------------------------------------------------------------------- #
    def sync_switches() -> None:
        """Qué interruptores aplican al tipo de modelo elegido.

        Sólo conocimiento: S5 es reflexivo, luego serial: el Axioma D no
        decide nada, ni la creencia vacía. Sólo creencia: no hay clase a la
        que volver, así que "cree lo que sabe" no existe (el silencio es
        inválido bajo KD45 y difunto bajo K45), y tampoco hay aristas
        implícitas que mostrar: cada lazo y cada dirección es información.
        """
        kind = state["kind"]
        axiom_d_in.set_enabled(kind != "knowledge")
        silent_defunct_in.set_enabled(kind == "kb" and not axiom_d_in.value)
        explicit_in.set_enabled(kind != "belief")

    def set_kind(kind: str) -> None:
        """Cambia el tipo de modelo y repinta todo lo que depende de él."""
        if kind == state["kind"]:
            return
        state["kind"] = kind
        if kind == "knowledge":
            # Las creencias marcadas no tienen sentido sin creencia: se
            # descartan para que la vista previa y el pipeline coincidan
            # con lo que el editor muestra.
            for rows in state["per_agent"].values():
                for row in rows:
                    row["bel"] = []
        sync_switches()
        repaint_all()

    def paint_chips() -> None:
        # Cada chip de agente lleva el MISMO color que sus aristas en las
        # figuras (agent_color_map replica la regla de visualization).
        colors = agent_color_map(state["agents"])
        agent_chips.clear()
        with agent_chips:
            for name in state["agents"]:
                ui.chip(name, removable=True, icon="person",
                        color=colors[name], text_color="white",
                        on_value_change=lambda e, n=name: remove_agent(n))
        world_chips.clear()
        with world_chips:
            for name in state["worlds"]:
                ui.chip(name, removable=True, icon="public",
                        color="rgba(255,255,255,.14)", text_color="white",
                        on_value_change=lambda e, n=name: remove_world(n))

    def _take(input_widget) -> str:
        """Lee y limpia el campo de alta, devolviendo el nombre tecleado."""
        name = (input_widget.value or "").strip()
        input_widget.value = ""
        return name

    def add_agent() -> None:
        name = _take(agent_input)
        if not name:
            return
        if name in state["agents"]:
            ui.notify(f"el agente '{name}' ya existe", type="warning")
            return
        state["agents"].append(name)
        state["per_agent"].setdefault(name, [])
        repaint_all()

    def remove_agent(name: str) -> None:
        # Sus filas se conservan en per_agent por si el borrado fue un error;
        # al no estar el agente listado, no se pintan ni se vuelven semillas.
        state["agents"].remove(name)
        repaint_all()

    def add_world() -> None:
        name = _take(world_input)
        if not name:
            return
        if name in state["worlds"]:
            ui.notify(f"el mundo '{name}' ya existe", type="warning")
            return
        state["worlds"].append(name)
        repaint_all()

    def remove_world(name: str) -> None:
        # Un mundo eliminado SÍ se poda de clases, creencias y átomos: dejarlo
        # produciría aristas o literales hacia un mundo inexistente.
        state["worlds"].remove(name)
        for rows in state["per_agent"].values():
            for row in rows:
                row["cls"] = [w for w in row["cls"] if w != name]
                row["bel"] = [w for w in row["bel"] if w != name]
        for atom, trues in state["atoms"].items():
            state["atoms"][atom] = [w for w in trues if w != name]
        repaint_all()

    def add_atom() -> None:
        name = _take(atom_input)
        if not name:
            return
        if name in state["atoms"]:
            ui.notify(f"el átomo '{name}' ya existe", type="warning")
            return
        state["atoms"][name] = []
        paint_atoms()
        update_preview()

    def remove_atom(name: str) -> None:
        state["atoms"].pop(name)
        paint_atoms()
        update_preview()

    def set_atom(name: str, trues: list) -> None:
        state["atoms"][name] = trues
        update_preview()

    def paint_atoms() -> None:
        atoms_box.clear()
        with atoms_box:
            for name, trues in state["atoms"].items():
                with ui.row().classes("w-full no-wrap items-center gap-2"):
                    ui.label(name).classes("font-mono w-10")
                    ui.select(
                        state["worlds"], multiple=True, value=trues,
                        label="verdadero en",
                        on_change=lambda e, n=name: set_atom(n, e.value),
                    ).props("use-chips dense").classes("grow")
                    ui.button(
                        icon="delete",
                        on_click=lambda _, n=name: remove_atom(n),
                    ).props("flat dense color=grey")

    def repaint_all() -> None:
        paint_chips()
        paint_editor()
        paint_atoms()
        update_preview()

    # ----------------------------------------------------------------------- #
    # Editor por agente. Estrategia deliberadamente simple: cualquier cambio
    # estructural REPINTA el editor completo desde ``state`` y re-renderiza la
    # vista previa. A esta escala (unos pocos agentes/mundos) ambos son casi
    # instantáneos y eliminan toda la contabilidad de widgets parciales.
    # ----------------------------------------------------------------------- #
    def paint_editor() -> None:
        colors = agent_color_map(state["agents"])
        editor_box.clear()
        with editor_box:
            for agent in state["agents"]:
                rows = state["per_agent"].setdefault(agent, [])
                with ui.card().classes(CARD).props(FLAT):
                    # El punto de color repite el color del agente en las
                    # figuras -- misma convención que sus chips.
                    with ui.row().classes("items-center gap-2"):
                        ui.element("span").style(
                            f"width:10px;height:10px;border-radius:9999px;"
                            f"background:{colors[agent]}"
                        )
                        ui.label(f"Agente {agent}").classes("font-semibold")
                    kind = state["kind"]
                    for i, row in enumerate(rows):
                        with ui.row().classes("w-full no-wrap items-center gap-2"):
                            # Primera columna: la clase de conocimiento, o en
                            # sólo creencia los mundos DESDE los que se cree.
                            # Cambiarla repinta, porque las opciones de
                            # creencia dependen de la clase elegida.
                            ui.select(
                                state["worlds"], multiple=True, value=row["cls"],
                                label=("desde (mundos)" if kind == "belief"
                                       else "clase (indistinguibles)"),
                                on_change=lambda e, r=row: set_cls(r, e.value),
                            ).props("use-chips dense").classes("grow")
                            # Mundos creídos: restringidos a la clase (así una
                            # creencia fuera de la clase es inexpresable), o a
                            # todos los mundos cuando no hay clase. Sin
                            # creencia, la columna no existe.
                            if kind != "knowledge":
                                ui.select(
                                    state["worlds"] if kind == "belief" else row["cls"],
                                    multiple=True, value=row["bel"],
                                    label=("cree (mundos)" if kind == "belief"
                                           else "cree (vacío = lo que sabe)"),
                                    on_change=lambda e, r=row: set_bel(r, e.value),
                                ).props("use-chips dense").classes("grow")
                            ui.button(
                                icon="delete",
                                on_click=lambda _, a=agent, k=i: remove_row(a, k),
                            ).props("flat dense color=grey")
                    ui.button(
                        "añadir fila" if kind == "belief" else "añadir clase",
                        icon="add", on_click=lambda _, a=agent: add_row(a),
                    ).props("flat dense")
                    ui.markdown({
                        "kb": "Mundos fuera de toda clase quedan como clases unitarias.",
                        "knowledge": "Mundos fuera de toda clase quedan como clases "
                                     "unitarias (el agente los distingue).",
                        "belief": "Mundos sin fila no creen nada: inválido bajo KD45, "
                                  "creencia difunta bajo K45.",
                    }[kind]).classes("text-xs text-grey-5")

    def update_preview() -> None:
        """Re-renderiza el modelo tal como está ingresado (sin clausuras).

        Corre en cada cambio del editor. La cabecera de la tarjeta lleva el
        punto pulsante "en vivo" y un chip de validez (verde = ya válido,
        ámbar = N condiciones por completar); la figura muestra exactamente
        los chips dibujados con lo faltante punteado en rojo. Un estado
        inexpresable como semillas (clases solapadas) se muestra como texto.
        """
        preview_box.clear()
        # Única tarjeta CON elevación (halo lima): señala al elemento que se
        # actualiza solo (ver "SISTEMA VISUAL").
        with preview_box, ui.card().classes(CARD + " poster-live").props(FLAT):
            with ui.row().classes("w-full items-center gap-2"):
                ui.element("span").classes("pulse-dot")
                _card_title("Vista previa · modelo tal como se ingresa")
                ui.space()
                badge_slot = ui.row().classes("items-center")
            if not state["agents"] or not state["worlds"]:
                ui.label("Agrega al menos un agente y un mundo.") \
                    .classes("text-grey-5")
                return
            try:
                path, violations = preview_figure(
                    state["agents"], state["worlds"], state["per_agent"],
                    state["atoms"], explicit_in.value, axiom_d_in.value,
                    state["kind"],
                )
            except ValueError as exc:
                with badge_slot:
                    _chip("inexpresable", "bad")
                ui.html(f"<pre style='white-space:pre-wrap' "
                        f"class='text-xs'>{exc}</pre>")
                return
            with badge_slot:
                if violations:
                    _chip(f"{len(violations)} por completar", "warn",
                          icon="pending")
                else:
                    _chip("válido", "ok", icon="check")
            with ui.element("div").classes("w-full fig-frame"):
                _figure_img(path)
            if violations:
                with ui.expansion("Lo que las clausuras completarán") \
                        .classes("w-full").style(f"color:{POSTER['yellow']}"):
                    for v in violations:
                        ui.label(v).classes("font-mono text-xs")

    def set_cls(row: dict, cls: list) -> None:
        """Actualiza una clase y poda las creencias que quedaron fuera de ella.

        En sólo creencia no hay clase que respetar: la primera columna son
        los mundos de origen y la creencia puede apuntar a cualquier mundo.
        """
        row["cls"] = cls
        if state["kind"] != "belief":
            row["bel"] = [w for w in row["bel"] if w in cls]
        paint_editor()  # las opciones del selector de creencia cambiaron
        update_preview()

    def set_bel(row: dict, bel: list) -> None:
        row["bel"] = bel
        update_preview()

    def add_row(agent: str) -> None:
        state["per_agent"][agent].append({"cls": [], "bel": []})
        paint_editor()
        update_preview()

    def remove_row(agent: str, index: int) -> None:
        state["per_agent"][agent].pop(index)
        paint_editor()
        update_preview()

    # ----------------------------------------------------------------------- #
    # Evaluador de fórmulas: responde en su propia tarjeta, mundo por mundo.
    # ----------------------------------------------------------------------- #
    def eval_formula() -> None:
        formula_out.clear()
        try:
            rows = evaluate_formula(
                state["agents"], state["worlds"], state["per_agent"],
                state["atoms"], axiom_d_in.value, formula_input.value or "",
                not silent_defunct_in.value, state["kind"],
            )
        except ValueError as exc:
            with formula_out:
                ui.html(f"<pre style='white-space:pre-wrap' "
                        f"class='text-pink-3 text-xs'>{exc}</pre>")
            return
        holds = sum(1 for _, ok in rows if ok)
        with formula_out:
            with ui.row().classes("gap-1"):
                for world, ok in rows:
                    _chip(world, "ok" if ok else "bad",
                          icon="check" if ok else "close")
            ui.label(
                "Válida en el modelo (vale en todos los mundos)."
                if holds == len(rows) else
                f"Vale en {holds} de {len(rows)} mundos."
            ).classes("text-xs text-grey-5")

    # ----------------------------------------------------------------------- #
    # Corrida del pipeline. Asíncrona y con estado de carga: el botón muestra
    # spinner (prop 'loading' de Quasar) y el trabajo pesado va a un hilo con
    # run.io_bound, para que la interfaz no se congele ese par de segundos.
    # ----------------------------------------------------------------------- #
    def paint_results_placeholder() -> None:
        """Estado vacío ilustrado: nunca una columna en blanco sin mensaje."""
        with results, ui.column().classes("w-full items-center py-16 gap-2"):
            ui.icon("account_tree", size="64px").classes("text-grey-9")
            ui.label("Corre el pipeline para ver las Figuras 1 → 4") \
                .classes("text-grey-5")

    async def explicit_changed() -> None:
        """Interruptor de aristas implícitas: vista previa ya, pipeline si hubo."""
        update_preview()
        if state.get("ran"):
            await run_clicked()

    async def run_clicked() -> None:
        results.clear()
        run_btn.props("loading")
        with results, ui.card().classes(CARD).props(FLAT):
            with ui.column().classes("w-full items-center py-10 gap-2"):
                ui.spinner(size="lg")
                ui.label("Generando figuras…").classes("text-grey-5")
        try:
            knowledge, belief = seeds_from_editor(
                state["agents"], state["worlds"], state["per_agent"],
                state["kind"],
            )
            out = await io.io_bound(
                run_pipeline_from_seeds,
                state["agents"], state["worlds"], knowledge, belief,
                axiom_d_in.value, state["atoms"],
                not silent_defunct_in.value, explicit_in.value, state["kind"],
            )
        except ValueError as exc:
            # Un ValueError es el núcleo rechazando el modelo (S5/KD45/propiedad).
            # Eso es CONTENIDO pedagógico: se muestra tal cual, sin traza.
            results.clear()
            ui.notify("El modelo no es válido — detalle en el panel",
                      type="negative")
            with results, ui.card().classes(CARD + " poster-bad").props(FLAT):
                ui.label("Modelo rechazado por la validación del núcleo:") \
                    .classes("font-semibold text-pink-3")
                ui.html(f"<pre style='white-space:pre-wrap'>{exc}</pre>")
            return
        except Exception as exc:  # noqa: BLE001 -- ver abajo: es deliberado
            # CUALQUIER otra excepción es un problema de entorno o un bug, no
            # del modelo. Antes sólo se capturaba ValueError, así que cosas como
            # el RuntimeError de `visualization.show` cuando falta el binario
            # `dot` de Graphviz se propagaban y TUMBABAN la app -- y como eso
            # ocurre en cada corrida, el botón parecía roto siempre.
            # Se captura todo a propósito: esto es el borde de un manejador de
            # UI; que la app siga viva y muestre el fallo vale más que dejar
            # subir la excepción a NiceGUI.
            results.clear()
            falta_dot = shutil.which("dot") is None
            ui.notify("Error al correr el pipeline — detalle en el panel",
                      type="negative")
            with results, ui.card().classes(CARD + " poster-bad").props(FLAT):
                if falta_dot:
                    ui.label("Falta Graphviz").classes(
                        "font-semibold text-pink-3")
                    ui.html(
                        "<p>El pipeline necesita el binario <code>dot</code> "
                        "para dibujar las figuras, y no está en el PATH.</p>"
                        "<p>Instálalo con <code>brew install graphviz</code> "
                        "(macOS) o <code>apt install graphviz</code> (Linux) "
                        "y vuelve a correr.</p>"
                    )
                else:
                    ui.label("Error inesperado (esto es un bug, repórtalo):") \
                        .classes("font-semibold text-pink-3")
                ui.html(
                    f"<pre style='white-space:pre-wrap' class='text-xs'>"
                    f"{html.escape(traceback.format_exc())}</pre>"
                )
            return
        finally:
            run_btn.props(remove="loading")

        state["ran"] = True
        results.clear()
        with results:
            # Métricas de la corrida como stat-tiles + chips de estado (los
            # mismos números de la vieja bitácora, legibles en un segundo).
            with ui.card().classes(CARD).props(FLAT):
                with ui.row().classes("w-full items-center gap-2"):
                    _card_title("Resultado del pipeline")
                    ui.space()
                    # Los badges vienen con nombres de la paleta Quasar
                    # (positive/negative/primary); se traducen a los tonos
                    # de rol del cartel para que no salgan lima con texto
                    # blanco (ilegible).
                    for text, color in out.badges:
                        tone = {"positive": "ok", "negative": "bad"} \
                            .get(color, "info")
                        _chip(text, tone).props("dense")
                with ui.row().classes("w-full gap-8 mt-2"):
                    for value, label in out.stats:
                        with ui.column().classes("gap-0 items-center"):
                            ui.label(value).classes(
                                "text-2xl font-bold text-white")
                            ui.label(label).classes("text-xs text-grey-5")

            # Bitácora del pipeline paso a paso: qué se completó, qué falta y
            # qué falló. Es lo primero que se muestra porque responde la
            # pregunta que la gente trae ("¿por qué no salió lo que dibujé?")
            # antes de que se pongan a mirar las figuras.
            if out.steps:
                with ui.card().classes(CARD).props(FLAT):
                    _card_title("Pipeline paso a paso")
                    for step in out.steps:
                        # Iconos con los colores de rol del cartel: verde =
                        # tal cual, cian = completado por clausura, rosa = falló.
                        icon, color = {
                            "ok": ("check_circle", POSTER["green"]),
                            "completed": ("auto_fix_high", POSTER["cyan"]),
                            "failed": ("cancel", POSTER["pink"]),
                            "skipped": ("block", "#9e9e9e"),
                        }[step.status]
                        with ui.row().classes("w-full items-center gap-2 mt-3"):
                            ui.icon(icon).style(f"color:{color}")
                            ui.label(step.name).classes("font-semibold")
                            if step.status == "ok":
                                ui.label("tal cual se dibujó") \
                                    .classes("text-xs text-grey-5")
                            if step.status == "skipped":
                                ui.label("no aplica a este tipo de modelo") \
                                    .classes("text-xs text-grey-5")
                        for text in step.skipped:
                            with ui.row().classes("w-full no-wrap items-start gap-2 ml-8"):
                                ui.label("–").classes("font-bold text-grey-5")
                                ui.label(text).classes("text-sm text-grey-4")
                        for text in step.failed:
                            with ui.column().classes(
                                "w-full gap-0 ml-8 p-2 rounded poster-bad"
                            ):
                                ui.label("Falló aquí — el pipeline se detuvo:") \
                                    .classes("text-xs font-semibold text-pink-3")
                                ui.html(
                                    f"<pre style='white-space:pre-wrap' "
                                    f"class='text-xs'>{html.escape(text)}</pre>"
                                )
                        for text in step.completed:
                            with ui.row().classes("w-full no-wrap items-start gap-2 ml-8"):
                                ui.label("+").classes("font-bold") \
                                    .style(f"color:{POSTER['cyan']}")
                                ui.label(text).classes("text-sm text-grey-4")
                        for text in step.missing:
                            with ui.row().classes("w-full no-wrap items-start gap-2 ml-8"):
                                ui.label("?").classes("font-bold") \
                                    .style(f"color:{POSTER['yellow']}")
                                ui.label(text).classes("text-sm text-grey-4")
                    ui.label(
                        "+ lo que una clausura o convención completó por ti · "
                        "? lo que sigue sin especificar y qué significa ese silencio"
                    ).classes("text-xs italic text-grey-5 mt-3")

            # Las figuras del pipeline, en orden, como en thesis_example.py,
            # más la Fig. 4 (retículo de caras) que añade adapters.
            for caption, path in out.figures:
                figure_card(caption, path)

            # La vista 3D interactiva es una página plotly completa: se embebe
            # en un iframe en lugar de reconstruirla con componentes.
            if out.html_3d is not None:
                with ui.card().classes(CARD).props(FLAT):
                    _card_title("Fig. 3 · vista 3D interactiva")
                    # La página plotly es clara: va sobre la misma lámina
                    # que las figuras PNG para que no sea un bloque blanco
                    # suelto sobre marino.
                    # sanitize=False: ui.html sanea el HTML por defecto y
                    # ELIMINA los <iframe>, con lo que la vista 3D quedaba
                    # como una tarjeta vacía. El src es un archivo propio
                    # servido desde outputs/, no contenido externo.
                    ui.html(
                        f'<iframe src="{_url(out.html_3d)}" '
                        'style="width:100%;height:560px;border:none;'
                        'display:block;border-radius:.375rem"></iframe>',
                        sanitize=False,
                    ).classes("w-full fig-frame")
                    ui.label("Arrastra para rotar; rueda para acercar.") \
                        .classes("text-xs italic text-grey-5")

            # Diagramas de texto (visualize): la vista sin dependencias,
            # plegada por defecto para no competir con las figuras.
            with ui.expansion("Diagramas de texto").classes("w-full"):
                for caption, diagram in out.text_diagrams:
                    ui.label(caption).classes("font-semibold mt-2")
                    ui.html(f"<pre style='white-space:pre-wrap' "
                            f"class='text-xs'>{diagram}</pre>")

    # Primer pintado: el ejemplo de la tesis con su vista previa, y el estado
    # vacío ilustrado en la zona de resultados.
    load_example("tesis")
    sync_switches()
    paint_results_placeholder()


# reload=False: la recarga automática de NiceGUI reimporta el módulo en un
# subproceso, un comportamiento sorpresivo para una herramienta local sencilla.
# El guard __mp_main__ es la convención de NiceGUI (uvicorn multiproceso).
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="La geometría de una creencia falsa", reload=False,
           dark=True)

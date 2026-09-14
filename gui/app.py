"""GUI web del proyecto (NiceGUI): construir un modelo y correr el pipeline completo.

Run:  .venv/bin/python gui/app.py     (abre http://localhost:8080 en el navegador)

POR QUÉ NICEGUI Y ESTA FORMA. La GUI es una herramienta de investigación de un
solo usuario, así que se eligió el stack que reutiliza TODO lo existente con el
mínimo de piezas nuevas: NiceGUI es 100 % Python (los módulos del núcleo se
importan directo, sin API ni serialización), corre en el navegador (las figuras
plotly 3D ya son HTML y se embeben tal cual), y una página basta.

DISEÑO VISUAL. El color primario es el azul Okabe-Ito #0072B2 -- el PRIMER color
de ``visualization.PALETTE`` -- para que GUI y figuras compartan identidad. La
página va sobre gris claro con tarjetas blancas (jerarquía sin bordes), una
cabecera fija concentra las acciones globales (correr pipeline, cargar ejemplo)
y el panel de edición queda "pegajoso" (sticky, con scroll propio) para poder
comparar entrada y resultados sin perderlo al hacer scroll.

CÓMO SE INGRESAN LOS MODELOS. Todo es interactivo y se propaga en cadena:

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
      uno); con átomos, todas las figuras etiquetan mundos/vértices con sus
      literales y se habilita el EVALUADOR DE FÓRMULAS (K_a, B_a, ¬ & | ->),
      que responde mundo por mundo sobre el modelo ya completado.
    * Una VISTA PREVIA EN VIVO dibuja el modelo TAL COMO ESTÁ INGRESADO en
      cada cambio, sin clausuras: lo faltante aparece punteado en rojo y
      listado abajo. El pipeline completo corre solo al pedirlo, con spinner
      y botón bloqueado mientras trabaja (graphviz+matplotlib+plotly ~1-2 s,
      despachados con run.io_bound para no congelar la interfaz).
    * La BIBLIOTECA DE EJEMPLOS (cabecera) carga estados completos del editor
      espejo de scripts del repo (tesis, coloquio/NASA, moneda): la GUI es
      también una galería navegable de esos casos.

QUÉ HAY EN ESTE ARCHIVO -- solo presentación: widgets, layout y notificaciones.
Toda la lógica (semillas, vista previa, pipeline, fórmulas) vive en
``gui/adapters.py``; este archivo la consume y muestra resultados ya aplanados
(rutas de archivo y strings). Esa frontera mantiene el núcleo intacto.

CÓMO SE MUESTRAN LAS FIGURAS. ``visualization.show`` escribe PNG/HTML en
``outputs/`` (los mismos archivos que producen los scripts de consola); esa
carpeta se sirve como estáticos y cada URL lleva ``?v=<mtime>`` como
rompe-caché, porque cada corrida sobreescribe los mismos nombres de archivo.
"""

from __future__ import annotations

import copy

from nicegui import app, run as io, ui

# Import plano a propósito: al ejecutar ``python gui/app.py`` esta carpeta es
# sys.path[0], y adapters se encarga de poner la raíz del repo en el path.
from adapters import (
    EXAMPLES,
    OUTPUTS,
    evaluate_formula,
    preview_figure,
    run_pipeline_from_seeds,
    seeds_from_editor,
)

# Las figuras generadas se sirven directamente desde outputs/ -- la GUI no copia
# ni administra archivos propios, comparte los artefactos con los scripts CLI.
OUTPUTS.mkdir(exist_ok=True)
app.add_static_files("/outputs", str(OUTPUTS))

def _url(path) -> str:
    """URL estática de una figura, con el mtime como rompe-caché (ver docstring)."""
    return f"/outputs/{path.name}?v={int(path.stat().st_mtime)}"


# --------------------------------------------------------------------------- #
# Página única. @ui.page es el patrón de NiceGUI 3: la función corre UNA VEZ
# POR CLIENTE al visitar la ruta, y todo el estado vive como cierre local --
# cada pestaña del navegador tiene su propio modelo en edición.
# --------------------------------------------------------------------------- #
@ui.page("/")
def index() -> None:
    # Identidad visual: el azul de visualization.PALETTE como color primario,
    # para que cabecera/botones y las aristas del "agente a" cuenten la misma
    # historia. (Dentro de la página: NiceGUI 3 prohíbe UI en scope global
    # cuando se usa @ui.page.)
    ui.colors(primary="#0072B2")
    ui.query("body").classes("bg-grey-2")

    # TODO el modelo dibujado vive en este dict plano (no en los widgets):
    # los widgets solo lo PINTAN y la conversión a semillas es una función
    # pura de adapters. Un solo dueño del estado evita sincronización
    # widget-a-widget. Se arranca con el ejemplo de la tesis.
    state = {
        "agents": [], "worlds": [], "per_agent": {},
        "atoms": {},  # atomo -> mundos donde es VERDADERO (la valuacion v)
    }

    def load_example(key: str) -> None:
        """Carga un estado completo de la biblioteca (deepcopy: editable)."""
        ex = copy.deepcopy(EXAMPLES[key])
        state["agents"] = ex["agents"]
        state["worlds"] = ex["worlds"]
        state["per_agent"] = ex["per_agent"]
        state["atoms"] = ex["atoms"]
        axiom_d_in.value = ex["axiom_d"]
        repaint_all()

    # ---- Cabecera fija: identidad + acciones globales ---------------------- #
    with ui.header().classes("items-center justify-between px-6 py-3"):
        with ui.column().classes("gap-0"):
            ui.label("SimulationsBelief").classes("text-xl font-bold")
            ui.label("Modelos relacionales y simpliciales de creencia · "
                     "pipeline general → propio → simplicial") \
                .classes("text-xs opacity-80")
        with ui.row().classes("items-center gap-3"):
            ui.select(
                {k: ex["label"] for k, ex in EXAMPLES.items()},
                value=None, label="cargar ejemplo",
                on_change=lambda e: load_example(e.value),
            ).props("dense dark outlined options-dense") \
                .classes("min-w-[240px]")
            run_btn = ui.button("Correr pipeline", icon="play_arrow",
                                on_click=lambda: run_clicked()) \
                .props("color=white text-color=primary unelevated")

    with ui.row().classes("w-full no-wrap items-start gap-6 p-2"):

        # ---- Panel de edición: sticky con scroll propio, para tenerlo -------
        # siempre a la vista mientras se recorren los resultados.
        with ui.column().classes(
            "w-[440px] shrink-0 gap-4 sticky top-2 self-start "
            "max-h-[calc(100vh-110px)] overflow-y-auto pr-1"
        ):
            # ---- Identificadores ------------------------------------------- #
            with ui.card().classes("w-full"):
                ui.label("Agentes y mundos").classes("text-lg font-bold")
                with ui.row().classes("w-full no-wrap items-center"):
                    agent_input = ui.input("nuevo agente") \
                        .props("dense outlined").classes("grow")
                    ui.button(icon="add", on_click=lambda: add_agent()) \
                        .props("round dense")
                agent_chips = ui.row().classes("w-full gap-1")
                agent_input.on("keydown.enter", lambda: add_agent())

                with ui.row().classes("w-full no-wrap items-center mt-2"):
                    world_input = ui.input("nuevo mundo") \
                        .props("dense outlined").classes("grow")
                    ui.button(icon="add", on_click=lambda: add_world()) \
                        .props("round dense")
                world_chips = ui.row().classes("w-full gap-1")
                world_input.on("keydown.enter", lambda: add_world())

                # El interruptor KD45/K45 del núcleo (axiom_d), expuesto tal
                # cual: apagarlo legaliza las creencias difuntas (Q_a(w) = ∅).
                axiom_d_in = ui.switch("Axioma D (KD45; apagado = K45)",
                                       value=True)

            # ---- Editor de relaciones por agente --------------------------- #
            editor_box = ui.column().classes("w-full gap-4")

            # ---- Átomos: la valuación v (dónde es verdadero cada átomo) ---- #
            with ui.card().classes("w-full"):
                ui.label("Átomos (proposiciones)").classes("text-lg font-bold")
                ui.markdown(
                    "Declara cada átomo y en qué mundos es **verdadero**. Con "
                    "átomos, las figuras etiquetan los mundos con sus "
                    "literales y puedes evaluar fórmulas."
                ).classes("text-xs text-grey-7")
                with ui.row().classes("w-full no-wrap items-center"):
                    atom_input = ui.input("nuevo átomo") \
                        .props("dense outlined").classes("grow")
                    ui.button(icon="add", on_click=lambda: add_atom()) \
                        .props("round dense")
                atom_input.on("keydown.enter", lambda: add_atom())
                atoms_box = ui.column().classes("w-full")

            # ---- Evaluador de fórmulas ------------------------------------- #
            with ui.card().classes("w-full"):
                ui.label("Evaluar fórmula").classes("text-lg font-bold")
                formula_input = ui.input(
                    "fórmula", placeholder="B_a p & ~K_a p",
                ).props("dense outlined").classes("w-full font-mono")
                ui.markdown(
                    "Sintaxis: átomos declarados, `K_a`, `B_a`, `~`/`¬`, `&`, "
                    "`|`, `->`, `bot`, paréntesis. Se evalúa **mundo por "
                    "mundo** sobre el modelo ya completado por las clausuras."
                ).classes("text-xs text-grey-7")
                ui.button("Evaluar", icon="calculate",
                          on_click=lambda: eval_formula()) \
                    .props("outline dense")
                formula_input.on("keydown.enter", lambda: eval_formula())
                formula_out = ui.column().classes("w-full")

        with ui.column().classes("grow min-w-0 gap-4"):
            # ---- Vista previa en vivo (siempre visible, arriba) ------------ #
            preview_box = ui.column().classes("w-full")
            # ---- Salida del pipeline: se reconstruye en cada corrida ------- #
            results = ui.column().classes("w-full")

    # ----------------------------------------------------------------------- #
    # Altas y bajas de identificadores y átomos. Cada operación muta ``state``
    # y repinta chips + editor + átomos + vista previa; no hay más sincronía.
    # ----------------------------------------------------------------------- #
    def paint_chips() -> None:
        agent_chips.clear()
        with agent_chips:
            for name in state["agents"]:
                ui.chip(name, removable=True, icon="person",
                        on_value_change=lambda e, n=name: remove_agent(n))
        world_chips.clear()
        with world_chips:
            for name in state["worlds"]:
                ui.chip(name, removable=True, icon="public",
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
                with ui.row().classes("w-full no-wrap items-center"):
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
        editor_box.clear()
        with editor_box:
            for agent in state["agents"]:
                rows = state["per_agent"].setdefault(agent, [])
                with ui.card().classes("w-full"):
                    ui.label(f"Agente {agent}").classes("font-bold")
                    for i, row in enumerate(rows):
                        with ui.row().classes("w-full no-wrap items-center"):
                            # Clase de conocimiento: chips de mundos. Cambiarla
                            # repinta, porque las opciones de creencia dependen
                            # de la clase elegida.
                            ui.select(
                                state["worlds"], multiple=True, value=row["cls"],
                                label="clase (indistinguibles)",
                                on_change=lambda e, r=row: set_cls(r, e.value),
                            ).props("use-chips dense").classes("grow")
                            # Mundos creídos: restringidos a la clase, así una
                            # creencia fuera de la clase es inexpresable.
                            ui.select(
                                row["cls"], multiple=True, value=row["bel"],
                                label="cree (vacío = lo que sabe)",
                                on_change=lambda e, r=row: set_bel(r, e.value),
                            ).props("use-chips dense").classes("grow")
                            ui.button(
                                icon="delete",
                                on_click=lambda _, a=agent, k=i: remove_row(a, k),
                            ).props("flat dense color=grey")
                    ui.button(
                        "añadir clase", icon="add",
                        on_click=lambda _, a=agent: add_row(a),
                    ).props("flat dense")
                    ui.markdown(
                        "Mundos fuera de toda clase quedan como clases unitarias."
                    ).classes("text-xs text-grey-7")

    def update_preview() -> None:
        """Re-renderiza el modelo tal como está ingresado (sin clausuras).

        Corre en cada cambio del editor: la figura muestra exactamente los
        chips dibujados, con lo faltante punteado en rojo, y las violaciones
        del núcleo listadas como "lo que las clausuras completarán". Un estado
        inexpresable como semillas (clases solapadas) se muestra como texto en
        lugar de figura.
        """
        preview_box.clear()
        with preview_box, ui.card().classes("w-full"):
            ui.label("Vista previa · modelo tal como se ingresa") \
                .classes("font-bold")
            if not state["agents"] or not state["worlds"]:
                ui.label("Agrega al menos un agente y un mundo.") \
                    .classes("text-grey-7")
                return
            try:
                path, violations = preview_figure(
                    state["agents"], state["worlds"], state["per_agent"],
                    state["atoms"],
                )
            except ValueError as exc:
                ui.html(f"<pre style='white-space:pre-wrap'>{exc}</pre>")
                return
            ui.image(_url(path)).classes("w-full").props("fit=scale-down")
            if violations:
                with ui.expansion(
                    f"Aún no es un modelo válido — las clausuras completarán "
                    f"{len(violations)} condición(es)"
                ).classes("w-full"):
                    for v in violations:
                        ui.label(v).classes("font-mono text-xs")
            else:
                ui.label("El modelo dibujado ya es válido tal cual.") \
                    .classes("text-xs text-green-8")

    def set_cls(row: dict, cls: list) -> None:
        """Actualiza una clase y poda las creencias que quedaron fuera de ella."""
        row["cls"] = cls
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
            )
        except ValueError as exc:
            with formula_out:
                ui.html(f"<pre style='white-space:pre-wrap' "
                        f"class='text-red-8 text-xs'>{exc}</pre>")
            return
        holds = sum(1 for _, ok in rows if ok)
        with formula_out:
            with ui.row().classes("gap-1"):
                for world, ok in rows:
                    ui.chip(world,
                            icon="check" if ok else "close",
                            color="green-2" if ok else "red-2")
            ui.label(
                "Válida en el modelo (vale en todos los mundos)."
                if holds == len(rows) else
                f"Vale en {holds} de {len(rows)} mundos."
            ).classes("text-xs text-grey-8")

    # ----------------------------------------------------------------------- #
    # Corrida del pipeline. Asíncrona y con estado de carga: el botón muestra
    # spinner (prop 'loading' de Quasar) y el trabajo pesado va a un hilo con
    # run.io_bound, para que la interfaz no se congele ese par de segundos.
    # ----------------------------------------------------------------------- #
    async def run_clicked() -> None:
        results.clear()
        run_btn.props("loading")
        with results, ui.card().classes("w-full items-center py-10"):
            ui.spinner(size="lg")
            ui.label("Generando figuras…").classes("text-grey-7")
        try:
            knowledge, belief = seeds_from_editor(
                state["agents"], state["worlds"], state["per_agent"]
            )
            out = await io.io_bound(
                run_pipeline_from_seeds,
                state["agents"], state["worlds"], knowledge, belief,
                axiom_d_in.value, state["atoms"],
            )
        except ValueError as exc:
            results.clear()
            ui.notify("El modelo no es válido — detalle en el panel",
                      type="negative")
            with results, ui.card().classes("w-full bg-red-50"):
                ui.label("Modelo rechazado por la validación del núcleo:") \
                    .classes("font-bold text-red-800")
                ui.html(f"<pre style='white-space:pre-wrap'>{exc}</pre>")
            return
        finally:
            run_btn.props(remove="loading")

        results.clear()
        with results:
            # Bitácora breve de la corrida (tamaños, validez, propiedad).
            with ui.card().classes("w-full"):
                for line in out.log:
                    ui.label(line).classes("font-mono text-sm")

            # Las figuras del pipeline, en orden, como en thesis_example.py.
            for caption, path in out.figures:
                with ui.card().classes("w-full"):
                    ui.label(caption).classes("font-bold")
                    ui.image(_url(path)).classes("w-full").props("fit=scale-down")

            # La vista 3D interactiva es una página plotly completa: se embebe
            # en un iframe en lugar de reconstruirla con componentes.
            if out.html_3d is not None:
                with ui.card().classes("w-full"):
                    ui.label("Fig. 3 · vista 3D interactiva (arrastra para rotar)") \
                        .classes("font-bold")
                    ui.html(
                        f'<iframe src="{_url(out.html_3d)}" '
                        'style="width:100%;height:560px;border:none"></iframe>'
                    ).classes("w-full")

            # Diagramas de texto (visualize): la vista sin dependencias,
            # plegada por defecto para no competir con las figuras.
            with ui.expansion("Diagramas de texto").classes("w-full"):
                for caption, diagram in out.text_diagrams:
                    ui.label(caption).classes("font-bold mt-2")
                    ui.html(f"<pre style='white-space:pre-wrap'>{diagram}</pre>")

    # Primer pintado: el ejemplo de la tesis, con su vista previa, desde el
    # arranque (misma ruta que el dropdown de la cabecera).
    load_example("tesis")


# reload=False: la recarga automática de NiceGUI reimporta el módulo en un
# subproceso, un comportamiento sorpresivo para una herramienta local sencilla.
# El guard __mp_main__ es la convención de NiceGUI (uvicorn multiproceso).
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="SimulationsBelief", reload=False)

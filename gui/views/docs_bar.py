"""Models bar: the open documents, and saving / opening / downloading them.

One chip per document (click = activate, x = close), buttons to open a blank
one or duplicate the active one, the persistence buttons (GitHub #18) and,
with two or more documents, the comparison controls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from adapters import KINDS
from theme import CARD, FLAT, KIND_ICON, POSTER, card_title

if TYPE_CHECKING:
    from views.page import Page


class DocsBarView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.bar = None

    def build(self) -> None:
        self.bar = ui.row().classes("w-full items-center gap-2 px-4 pt-3")

    def paint(self) -> None:
        page, ws = self.page, self.page.ws
        ws.normalise_compare()
        self.bar.clear()
        with self.bar:
            ui.label("Modelos").classes("eyebrow")
            for d in ws.docs:
                active = d["id"] == ws.active
                kind = page.state["kind"] if active else d["state"]["kind"]
                ui.chip(
                    d["name"], icon="lock" if d["readonly"] else KIND_ICON[kind],
                    removable=len(ws.docs) > 1,
                    # The active one in lime (the accent of "what is live");
                    # the others translucent like the world chips.
                    color=POSTER["lime"] if active else "rgba(255,255,255,.14)",
                    text_color=POSTER["surface"] if active else "white",
                    on_click=lambda _, i=d["id"]: page.activate(i),
                    on_value_change=lambda e, i=d["id"]: page.close_doc(i),
                ).tooltip(KINDS[kind])
            ui.button(icon="add", on_click=lambda: page.add_blank()) \
                .props("round dense flat").tooltip("Modelo nuevo en blanco")
            ui.button(icon="content_copy", on_click=lambda: page.duplicate_active()) \
                .props("round dense flat").tooltip("Duplicar el modelo activo")
            # Persistence (GitHub #18): the whole bar to a file, a file back
            # into the bar, and the active model out as a download.
            ui.button(icon="save", on_click=lambda: self.save_dialog()) \
                .props("round dense flat").tooltip("Guardar todos los modelos abiertos")
            ui.button(icon="folder_open", on_click=lambda: self.open_dialog()) \
                .props("round dense flat").tooltip("Abrir un espacio guardado")
            ui.button(icon="download", on_click=lambda: self.export_active()) \
                .props("round dense flat").tooltip("Descargar el modelo activo (.json)")
            if len(ws.docs) >= 2:
                # The comparison controls go on their own line: with long
                # names they got mixed up with the model chips.
                ui.element("div").classes("w-full")
                ui.select(
                    {d["id"]: d["name"] for d in ws.docs}, multiple=True,
                    value=ws.compare, label="comparar (de 2 a 4)",
                    on_change=lambda e: setattr(ws, "compare", list(e.value)),
                ).props("dense outlined use-chips options-dense") \
                    .classes("min-w-[280px] max-w-[560px]")
                if ws.comparing:
                    ui.button("Volver al editor", icon="edit",
                              on_click=lambda: page.compare.exit()).props("outline dense")
                ui.button("Comparar", icon="compare",
                          on_click=lambda: page.compare.open()) \
                    .props("color=primary text-color=dark unelevated dense")

    # ---- Save / open workspaces (GitHub #18) ------------------------------- #
    # Everything open (names, states, read-only flags, provenance) goes to
    # one JSON file in saved_models/; opening one adds its models to the bar
    # or replaces what is open. A single model can also be downloaded as a
    # one-model workspace, which is the unit to share or to hand to a script.
    def save_dialog(self) -> None:
        page, ws = self.page, self.page.ws
        ws.store_active(page.live_state())
        with ui.dialog() as dlg, ui.card().classes(CARD + " min-w-[460px]").props(FLAT):
            card_title("Guardar espacio de trabajo")
            ui.label("Se guarda la DEFINICIÓN de cada modelo (lo que ves en el editor) "
                     "en saved_models/‹nombre›.json; las figuras se regeneran al correr. "
                     "Ver saved_models/README.md.").classes("text-xs text-grey-5")
            name_box = ui.input("nombre", value=page.current()["name"] if len(ws.docs) == 1
                                else f"espacio {len(ws.docs)} modelos") \
                .props("dense outlined").classes("w-full")
            # What to include: every open model is ticked by default; a model
            # without a finished run is said so, since it has no figures to
            # copy yet.
            ui.label("Modelos").classes("eyebrow mt-1")
            picks = {}
            for d in ws.docs:
                has_run = bool(d["outcome"]) and d["outcome"].get("status") == "ok"
                note = "" if has_run else " · sin corrida (no tendrá figuras)"
                picks[d["id"]] = ui.checkbox(d["name"] + note, value=True).props("dense")
            # The actions box only exists when there are actions to include.
            with_actions = ui.checkbox(
                f"incluir las {len(ws.actions)} acción(es)", value=True,
            ).props("dense") if ws.actions else None
            with_figures = ui.checkbox(
                "incluir las figuras de la última corrida "
                "(una carpeta por modelo en saved_models/‹nombre›/)", value=False,
            ).props("dense")

            def do_save() -> None:
                chosen = [i for i, box in picks.items() if box.value]
                if not chosen:
                    ui.notify("Elige al menos un modelo.", type="warning")
                    return
                try:
                    path, copied = ws.save(name_box.value or "espacio", chosen,
                                           include_actions=bool(with_actions and with_actions.value),
                                           include_figures=with_figures.value)
                except OSError as exc:
                    ui.notify(f"No se pudo guardar: {exc}", type="negative")
                    return
                msg = f"Guardado: saved_models/{path.name} ({len(chosen)} modelo(s))"
                if with_figures.value:
                    msg += f" + {copied} figura(s) en saved_models/{path.stem}/"
                ui.notify(msg, type="positive", timeout=6000)
                dlg.close()

            name_box.on("keydown.enter", lambda: do_save())
            with ui.row().classes("gap-2"):
                ui.button("Guardar", icon="save", on_click=do_save) \
                    .props("unelevated dense color=primary text-color=dark")
                ui.button("Cancelar", on_click=dlg.close).props("flat dense")
        dlg.open()

    def open_saved(self, path, replace: bool, dlg=None) -> None:
        """Open a saved workspace, adding to the bar or replacing it."""
        page, ws = self.page, self.page.ws
        if not replace:
            ws.store_active(page.live_state())
        try:
            opened = ws.open(path, replace)
        except (OSError, ValueError) as exc:
            ui.notify(str(exc), type="warning")
            return
        if dlg is not None:
            dlg.close()
        if ws.comparing:
            page.compare.exit()
        page.load_into_editor(page.current())
        self.paint()
        ui.notify(f"{len(opened)} modelo(s) abiertos de {path.name}", type="info")

    def open_dialog(self) -> None:
        ws = self.page.ws
        saved = ws.saved_files()
        with ui.dialog() as dlg, ui.card().classes(CARD + " min-w-[520px]").props(FLAT):
            card_title("Abrir espacio de trabajo")
            if not saved:
                ui.label("No hay espacios guardados todavía (saved_models/ está vacío).") \
                    .classes("text-sm text-grey-5")
            for path in saved:
                try:
                    counts = ws.peek(path)
                    detail = f"{counts['models']} modelo(s)" + (
                        f", {counts['actions']} acción(es)" if counts["actions"] else "")
                except (OSError, ValueError):
                    detail = "archivo no legible"
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.icon("folder").classes("text-grey-5")
                    with ui.column().classes("gap-0 grow min-w-0"):
                        ui.label(path.stem).classes("text-sm text-white")
                        ui.label(detail).classes("text-xs text-grey-5")
                    ui.button("añadir", on_click=lambda _, p=path: self.open_saved(p, False, dlg)) \
                        .props("outline dense").tooltip("Abrir junto a los modelos actuales")
                    ui.button("sustituir", on_click=lambda _, p=path: self.open_saved(p, True, dlg)) \
                        .props("flat dense").tooltip("Cerrar los actuales y abrir estos")
            ui.button("Cerrar", on_click=dlg.close).props("flat dense")
        dlg.open()

    def export_active(self) -> None:
        """Download the active model as a one-model workspace file."""
        import json

        page, ws = self.page, self.page.ws
        ws.store_active(page.live_state())
        data = json.dumps(ws.export_payload(), ensure_ascii=False, indent=1).encode("utf-8")
        ui.download.content(data, f"{page.current()['name']}.json")

"""Models bar: the open documents, and saving / opening / downloading them.

One tab per document (click = activate, x = close), buttons to open a blank
one or duplicate the active one, the persistence buttons and, with two or
more documents, the comparison controls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import copy

from nicegui import run as io, ui

from adapters import KINDS, print_light, run_state
from theme import KIND_ICON, card, panel_head

if TYPE_CHECKING:
    from views.page import Page


class DocsBarView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.bar = None

    def build(self) -> None:
        self.bar = ui.row().classes("w-full items-center gap-1 px-4 pt-2 docs-bar")

    def paint(self) -> None:
        page, ws = self.page, self.page.ws
        ws.normalise_compare()
        self.bar.clear()
        with self.bar:
            # The open documents as tabs: the active one underlined in the
            # accent, the others in muted ink; a small cross closes.
            with ui.row().classes("items-end gap-0 no-wrap"):
                for d in ws.docs:
                    active = d["id"] == ws.active
                    kind = d["state"]["kind"]
                    with ui.element("div").classes("doc-tab" + (" active" if active else "")) \
                            .on("click", lambda _, i=d["id"]: page.activate(i)) \
                            .tooltip(KINDS[kind]) as tab:
                        ui.icon("lock" if d["readonly"] else KIND_ICON[kind]).classes("kind")
                        ui.label(d["name"])
                        if len(ws.docs) > 1:
                            ui.icon("close").on(
                                "click.stop", lambda _, i=d["id"]: page.close_doc(i))
            ui.element("div").classes("vsep")
            # Plain text buttons, quiet until hovered: what each one does is
            # its name.
            ui.button("New", icon="add", on_click=lambda: page.add_blank()) \
                .props("flat dense", remove="color").classes("quiet-btn").tooltip("New blank model")
            ui.button("Duplicate", icon="content_copy", on_click=lambda: page.duplicate_active()) \
                .props("flat dense", remove="color").classes("quiet-btn").tooltip("Duplicate the active model")
            ui.element("div").classes("vsep")
            # Persistence: the whole bar to a file, a file back into the
            # bar, and the active model out as a download.
            ui.button("Save", icon="save", on_click=lambda: self.save_dialog()) \
                .props("flat dense", remove="color").classes("quiet-btn").tooltip("Save all open models")
            ui.button("Open", icon="folder_open", on_click=lambda: self.open_dialog()) \
                .props("flat dense", remove="color").classes("quiet-btn").tooltip("Open a saved workspace")
            ui.button("Download", icon="download", on_click=lambda: self.export_active()) \
                .props("flat dense", remove="color").classes("quiet-btn").tooltip("Download the active model (.json)")
            if len(ws.docs) >= 2:
                # The comparison controls at the far right of the bar.
                ui.element("div").classes("grow")
                ui.select(
                    {d["id"]: d["name"] for d in ws.docs}, multiple=True,
                    value=ws.compare, label="compare (2 to 4)",
                    on_change=lambda e: setattr(ws, "compare", list(e.value)),
                ).props("dense outlined use-chips options-dense") \
                    .classes("min-w-[260px] max-w-[520px]")
                if ws.comparing:
                    ui.button("Back to editor", icon="edit",
                              on_click=lambda: page.compare.exit()).props("outline dense")
                ui.button("Compare", icon="compare",
                          on_click=lambda: page.compare.open()) \
                    .props("color=primary text-color=dark unelevated dense")

    # ---- Save / open workspaces (saved_models/README.md) ------------------- #
    def save_dialog(self) -> None:
        page, ws = self.page, self.page.ws
        with ui.dialog() as dlg, card("min-w-[460px]"):
            panel_head("Save workspace")
            ui.label("The DEFINITION of each model (what you see in the editor) is saved "
                     "to saved_models/<name>.json; the figures are regenerated on a run. "
                     "See saved_models/README.md.").classes("text-xs muted")
            name_box = ui.input("name", value=page.current()["name"] if len(ws.docs) == 1
                                else f"workspace {len(ws.docs)} models") \
                .props("dense outlined").classes("w-full")
            # What to include: every open model is ticked by default; a model
            # without a finished run is said so, since it has no figures to
            # copy yet.
            ui.label("Models").classes("eyebrow mt-1")
            picks = {}
            for d in ws.docs:
                has_run = bool(d["outcome"]) and d["outcome"].get("status") == "ok"
                note = "" if has_run else " · not run yet (will have no figures)"
                picks[d["id"]] = ui.checkbox(d["name"] + note, value=True).props("dense")
            # The actions box only exists when there are actions to include.
            with_actions = ui.checkbox(
                f"include the {len(ws.actions)} action(s)", value=True,
            ).props("dense") if ws.actions else None
            with_figures = ui.checkbox(
                "include the figures of the last run, rendered for print "
                "(light background, PNG; one folder per model in saved_models/<name>/)", value=False,
            ).props("dense")

            async def do_save() -> None:
                chosen = [i for i, box in picks.items() if box.value]
                if not chosen:
                    ui.notify("Choose at least one model.", type="warning")
                    return
                # The saved figures are for print: light ink, white page,
                # PNG, whatever the screen shows. Each chosen model with a
                # run is rendered once more that way (a few seconds each).
                printed = {}
                if with_figures.value:
                    save_btn.props("loading")
                    try:
                        for d in ws.docs:
                            if d["id"] not in chosen or not d["outcome"] \
                                    or d["outcome"].get("status") != "ok":
                                continue
                            tag = f"print_{d['id']}"
                            try:
                                out = await io.io_bound(print_light, run_state,
                                                        copy.deepcopy(d["state"]), tag)
                            except Exception as exc:  # noqa: BLE001 -- fall back to the screen's figures
                                ui.notify(f"{d['name']}: could not render for print "
                                          f"({str(exc).splitlines()[0]}); saving the on-screen figures.",
                                          type="warning")
                                continue
                            if out is not None:
                                printed[d["id"]] = (out, tag)
                    finally:
                        save_btn.props(remove="loading")
                try:
                    path, copied = ws.save(name_box.value or "workspace", chosen,
                                           include_actions=bool(with_actions and with_actions.value),
                                           include_figures=with_figures.value, printed=printed)
                except OSError as exc:
                    ui.notify(f"Could not save: {exc}", type="negative")
                    return
                msg = f"Saved: saved_models/{path.name} ({len(chosen)} model(s))"
                if with_figures.value:
                    msg += f" + {copied} figure(s) in saved_models/{path.stem}/"
                ui.notify(msg, type="positive", timeout=6000)
                dlg.close()

            name_box.on("keydown.enter", lambda: do_save())
            with ui.row().classes("gap-2"):
                save_btn = ui.button("Save", icon="save", on_click=do_save) \
                    .props("unelevated dense color=primary text-color=dark")
                ui.button("Cancel", on_click=dlg.close).props("flat dense")
        dlg.open()

    def open_saved(self, path, replace: bool, dlg=None) -> None:
        """Open a saved workspace, adding to the bar or replacing it."""
        page, ws = self.page, self.page.ws
        try:
            opened = ws.open(path, replace)
        except (OSError, ValueError) as exc:
            ui.notify(str(exc), type="warning")
            return
        # Notify BEFORE repainting the bar: the dialog (and the button whose
        # click we are handling) hangs from the bar and is deleted with it,
        # after which NiceGUI has no slot to attach the notification to.
        ui.notify(f"{len(opened)} model(s) opened from {path.name}", type="info")
        if dlg is not None:
            dlg.close()
        if ws.comparing:
            page.compare.exit()
        page.load_into_editor(page.current())
        self.paint()

    def open_dialog(self) -> None:
        ws = self.page.ws
        saved = ws.saved_files()
        with ui.dialog() as dlg, card("min-w-[520px]"):
            panel_head("Open workspace")
            if not saved:
                ui.label("No saved workspaces yet (saved_models/ is empty).") \
                    .classes("text-sm muted")
            for path in saved:
                try:
                    counts = ws.peek(path)
                    detail = f"{counts['models']} model(s)" + (
                        f", {counts['actions']} action(s)" if counts["actions"] else "")
                except (OSError, ValueError):
                    detail = "unreadable file"
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.icon("folder").classes("muted")
                    with ui.column().classes("gap-0 grow min-w-0"):
                        ui.label(path.stem).classes("text-sm ink")
                        ui.label(detail).classes("text-xs muted")
                    ui.button("add", on_click=lambda _, p=path: self.open_saved(p, False, dlg)) \
                        .props("outline dense").tooltip("Open alongside the current models")
                    ui.button("replace", on_click=lambda _, p=path: self.open_saved(p, True, dlg)) \
                        .props("flat dense").tooltip("Close the current ones and open these")
            ui.button("Close", on_click=dlg.close).props("flat dense")
        dlg.open()

    def export_active(self) -> None:
        """Download the active model as a one-model workspace file."""
        import json

        page, ws = self.page, self.page.ws
        data = json.dumps(ws.export_payload(), ensure_ascii=False, indent=1).encode("utf-8")
        ui.download.content(data, f"{page.current()['name']}.json")

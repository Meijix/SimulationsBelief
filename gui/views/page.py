"""The page object: what every view shares, and the moves that cross views.

``Page`` owns the :class:`workspace.Workspace` (the documents) and the LIVE
``state`` (the dict the editors mutate; always the active document's), and
holds one instance of each view. The methods here are exactly the operations
that touch several regions at once -- pouring a document into the editor,
switching documents, locking a read-only one, repainting everything -- so
that no view has to know the others' internals beyond their public methods.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from nicegui import ui

from adapters import blank_state
from theme import CARD, FLAT, POSTER
from workspace import Workspace

if TYPE_CHECKING:  # only for readers and type checkers; no import cycle at runtime
    from views.actions import ActionsView
    from views.atoms import AtomsView
    from views.compare import CompareView
    from views.docs_bar import DocsBarView
    from views.editor import EditorView
    from views.formulas import FormulasView
    from views.header import HeaderView
    from views.preview import PreviewView
    from views.results import ResultsView
    from views.simplicial_editor import SimplicialEditorView


class Page:
    """Shared context of the single page (one instance per browser tab)."""

    def __init__(self) -> None:
        self.ws = Workspace()
        # The WHOLE drawn model lives in this flat dict (not in the widgets):
        # the widgets only PAINT it and the conversion to seeds is a pure
        # function of adapters. A single owner of the state avoids
        # widget-to-widget synchronisation. When switching documents the
        # active one is saved and the other one is poured in here -- so all
        # the editor code keeps talking to a single dict.
        self.state: dict = blank_state()
        # Views (attached by app.index) and the layout containers the page
        # itself needs to reach.
        self.header: HeaderView
        self.docs_bar: DocsBarView
        self.editor: EditorView
        self.simplicial: SimplicialEditorView
        self.atoms: AtomsView
        self.formulas: FormulasView
        self.actions: ActionsView
        self.preview: PreviewView
        self.results: ResultsView
        self.compare: CompareView
        self.editor_row = None      # the editor + results row (hidden while comparing)
        self.readonly_box = None    # the "this model is read-only" notice

    # ------------------------------------------------------------------ #
    # The active document and its live state
    # ------------------------------------------------------------------ #
    def current(self) -> dict:
        """The active document."""
        return self.ws.current()

    def live_state(self) -> dict:
        """``state`` with the switches brought up to date (they live in the widgets)."""
        self.editor.read_switches_into(self.state)
        return self.state

    def load_into_editor(self, doc: dict) -> None:
        """Pour a document into ``state`` and the widgets, and paint everything."""
        ws = self.ws
        # ``loading`` silences the widgets' on_change while values are
        # assigned: without it every assignment would repaint the preview
        # with a half-loaded state.
        ws.loading = True
        self.state.clear()
        self.state.update(copy.deepcopy(doc["state"]))
        self.editor.show_document(self.state, doc["name"])
        ws.loading = False
        dirty = doc["dirty"]            # repainting is not editing
        self.editor.sync_switches()
        self.apply_readonly(doc)
        self.repaint_all()
        doc["dirty"] = dirty
        self.preview.refresh_stale()    # with the real dirty flag, not the repaint's
        self.formulas.clear()
        self.results.render_outcome(doc["outcome"])

    def activate(self, doc_id: str) -> None:
        """Switch documents, saving the one being left first."""
        if self.ws.comparing:
            self.compare.exit()
        if doc_id == self.ws.active:
            return
        self.ws.store_active(self.live_state())
        self.ws.active = doc_id
        self.load_into_editor(self.current())
        self.docs_bar.paint()

    def add_blank(self) -> None:
        doc = self.ws.new_doc(self.ws.next_name(), blank_state())
        self.activate(doc["id"])

    def duplicate_active(self) -> None:
        """Editable copy of the active document (the way out of read-only ones)."""
        doc = self.ws.new_doc(f"{self.current()['name']} (copia)", self.live_state())
        self.activate(doc["id"])

    def close_doc(self, doc_id: str) -> None:
        next_id = self.ws.close(doc_id)
        if self.ws.comparing:
            self.compare.exit()
        if next_id is not None:         # the active one was closed
            self.load_into_editor(self.current())
        self.docs_bar.paint()

    def load_example(self, key: str) -> None:
        """Load a library example INTO the active document."""
        if not self.ws.load_example(key):
            ui.notify("Este modelo es de sólo lectura: duplícalo o abre uno "
                      "nuevo para cargar un ejemplo.", type="warning")
            return
        self.load_into_editor(self.current())
        self.docs_bar.paint()

    # ------------------------------------------------------------------ #
    # Cross-view painting
    # ------------------------------------------------------------------ #
    def apply_readonly(self, doc: dict) -> None:
        """Lock editing of a derived document and explain why.

        The cards that change the model are locked (identifiers, editor,
        atoms); evaluating formulas, running and comparing stay active.
        """
        for element in (self.editor.ident_card, self.editor.editor_box, self.atoms.card):
            if doc["readonly"]:
                element.classes(add="pointer-events-none opacity-60")
            else:
                element.classes(remove="pointer-events-none opacity-60")
        self.readonly_box.clear()
        if not doc["readonly"]:
            return
        with self.readonly_box, ui.card().classes(CARD).props(FLAT):
            with ui.row().classes("w-full items-center gap-3 no-wrap"):
                ui.icon("lock").style(f"color:{POSTER['yellow']}")
                source = (doc["origin"] or {}).get("label")
                ui.label(
                    ("Resultado de " + source + ". " if source else "")
                    + "Este modelo es de sólo lectura: para cambiarlo, "
                      "duplícalo como modelo nuevo."
                ).classes("text-sm text-grey-4 grow")
                ui.button("Duplicar como modelo nuevo", icon="content_copy",
                          on_click=lambda: self.duplicate_active()) \
                    .props("outline dense")

    def repaint_all(self) -> None:
        """Everything that is painted from ``state``: chips, editor, atoms, actions, preview."""
        self.editor.paint_chips()
        self.editor.paint()
        self.atoms.paint()
        self.actions.paint()        # the event rows follow the active model's agents
        self.preview.update()

    def reset_results(self) -> None:
        """Forget the active document's result: it belongs to ANOTHER model.

        On loading an example or changing the kind, the figures and metrics
        of the previous run no longer describe what is in the editor;
        leaving them visible under the new preview passed them off as
        results of the current model.
        """
        if self.ws.loading or self.ws.active is None:
            return
        self.current()["outcome"] = None
        self.results.render_outcome(None)
        self.preview.refresh_stale()    # nothing to be stale about any more

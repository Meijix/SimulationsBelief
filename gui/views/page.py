"""The page object: what every view shares, and the moves that cross views.

``Page`` owns the :class:`workspace.Workspace` (the documents) and holds one
instance of each view. ``page.state`` IS the active document's state dict:
the editors mutate it in place, so the document is always up to date and
switching documents is a rebind. The methods here are the operations that
touch several regions at once (pouring a document into the editor,
switching documents, locking a read-only one, repainting everything).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from adapters import blank_state
from theme import card, quasar_colors
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

THEMES = ("dark", "light")


class Page:
    """Shared context of the single page (one instance per browser tab)."""

    def __init__(self) -> None:
        self.ws = Workspace()
        self.state: dict = blank_state()    # rebound to the active document's state
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
        # "dark" or "light": the chrome's palette and the ink of the figures
        # (``visualization.ink``). ``dark`` is the ui.dark_mode element that
        # flips Quasar's body class (set by app.index).
        self.theme = "dark"
        self.dark = None

    async def set_theme(self, name: str) -> None:
        """Switch the whole page between dark and light, in place.

        The chrome follows on its own (CSS variables hang from Quasar's body
        class). The figures are files drawn in one ink, so the live figures
        are redrawn, the active model is run again if it had results, and the
        other documents are marked dirty so the comparison recomputes them.
        """
        if name == self.theme or name not in THEMES:
            return
        self.theme = name
        try:
            from nicegui import app
            app.storage.general["theme"] = name
        except Exception:  # noqa: BLE001 -- remembering the choice is a nicety
            pass
        if self.dark is not None:
            self.dark.set_value(name == "dark")
        quasar_colors(name)
        self.header.paint_theme()
        for doc in self.ws.docs:
            if doc["outcome"] is not None:
                doc["dirty"] = True
        self.preview.clear_cache()
        self.actions.clear_cache()
        self.preview.update()
        self.actions.paint()
        if self.current()["outcome"] is not None:
            await self.results.run()

    # ------------------------------------------------------------------ #
    # The active document
    # ------------------------------------------------------------------ #
    def current(self) -> dict:
        """The active document."""
        return self.ws.current()

    def load_into_editor(self, doc: dict) -> None:
        """Make ``doc`` the edited one: bind its state, set the widgets, paint.

        ``ws.loading`` is on while the widgets are assigned, so their
        on_change handlers do not count the assignments as edits.
        """
        ws = self.ws
        ws.loading = True
        self.state = doc["state"]
        self.editor.show_document(self.state, doc["name"])
        self.editor.sync_switches()
        self.apply_readonly(doc)
        self.repaint_all()
        ws.loading = False
        self.preview.refresh_stale()
        self.formulas.clear()
        self.results.render_outcome(doc["outcome"])

    def activate(self, doc_id: str) -> None:
        """Switch documents."""
        if self.ws.comparing:
            self.compare.exit()
        if doc_id == self.ws.active:
            return
        self.ws.active = doc_id
        self.load_into_editor(self.current())
        self.docs_bar.paint()

    def add_blank(self) -> None:
        doc = self.ws.new_doc(self.ws.next_name(), blank_state())
        self.activate(doc["id"])

    def duplicate_active(self) -> None:
        """Editable copy of the active document (the way out of read-only ones)."""
        doc = self.ws.new_doc(f"{self.current()['name']} (copy)", self.state)
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
            ui.notify("This model is read-only: duplicate it or open a new "
                      "one to load an example.", type="warning")
            return
        self.load_into_editor(self.current())
        self.docs_bar.paint()

    # ------------------------------------------------------------------ #
    # Cross-view painting
    # ------------------------------------------------------------------ #
    def apply_readonly(self, doc: dict) -> None:
        """Lock editing of a derived document (identifiers, editor, atoms) and
        say why; evaluating, running and comparing stay active."""
        for element in (self.editor.ident_card, self.editor.editor_box, self.atoms.card):
            if doc["readonly"]:
                element.classes(add="pointer-events-none opacity-60")
            else:
                element.classes(remove="pointer-events-none opacity-60")
        self.readonly_box.clear()
        if not doc["readonly"]:
            return
        with self.readonly_box, card():
            with ui.row().classes("w-full items-center gap-3 no-wrap"):
                ui.icon("lock").style("color:var(--p-warn)")
                source = (doc["origin"] or {}).get("label")
                ui.label(
                    ("Result of " + source + ". " if source else "")
                    + "This model is read-only: to change it, "
                      "duplicate it as a new model."
                ).classes("text-sm muted grow")
                ui.button("Duplicate as new model", icon="content_copy",
                          on_click=lambda: self.duplicate_active()) \
                    .props("outline dense")
            # What the product reported (isolated vertices, collapsed
            # perspectives, revisions), one line each.
            for note in (doc["origin"] or {}).get("notes") or []:
                ui.label("· " + note).classes("text-xs muted font-mono")

    def repaint_all(self) -> None:
        """Everything that is painted from ``state``: chips, editor, atoms, actions, preview."""
        self.editor.paint_chips()
        self.editor.paint()
        self.atoms.paint()
        self.actions.paint()        # the event rows follow the active model's agents
        self.preview.update()

    def reset_results(self) -> None:
        """Forget the active document's result: it belongs to another model
        (an example was loaded or the kind changed)."""
        if self.ws.loading or self.ws.active is None:
            return
        self.current()["outcome"] = None
        self.results.render_outcome(None)
        self.preview.refresh_stale()    # nothing to be stale about any more

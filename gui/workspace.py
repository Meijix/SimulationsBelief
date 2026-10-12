"""The GUI's workspace: open documents, comparison selection, action specs.

No NiceGUI here. This is the part of the page that is pure bookkeeping --
which models are open, which one is active, which ones are selected for
comparison, which action specs exist, how all of it is saved and reopened --
and it used to live as closures over two dicts inside the page function,
where nothing could be tested without a browser. As a class it is testable
with pytest (``tests/test_workspace.py``) and every view module talks to the
same object instead of to shared local variables.

A DOCUMENT is still a plain dict, the shape every other module (and the
saved files) already use::

    {"id": "d3",            identifier; also tags the output files
     "name": "...",         name shown in the models bar
     "state": {...},        the model (adapters.blank_state format)
     "outcome": {...}|None, result of the last run
     "dirty": bool,         the model changed since that run
     "readonly": bool,      derived result: not editable
     "origin": {...}|None}  where it came from (e.g. which action)

What the class does NOT do: touch widgets, pour a document into the editor,
or decide what to repaint. Those are the page's job; the methods here return
what the page needs (the document to show next, the new documents) and
nothing else.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Dict, List, Optional

from adapters import (
    EXAMPLES,
    blank_action,
    blank_state,
    list_saved,
    load_workspace_full,
    save_workspace,
    state_from_example,
    workspace_payload,
)

# The comparison view fits at most this many panels side by side.
MAX_COMPARE = 4


class Workspace:
    """Open documents + comparison selection + action specs, with persistence."""

    def __init__(self) -> None:
        self.docs: List[dict] = []
        self.active: Optional[str] = None
        # ``compare`` is the selection for the side-by-side view; ``comparing``
        # says whether that view is open (the editor row is hidden then).
        self.compare: List[str] = []
        self.comparing: bool = False
        # ``loading`` silences widget on_change handlers while a document is
        # being poured into the editor; it is read by the views, set by the page.
        self.loading: bool = False
        # Action specs are workspace-level (the same action is applied to
        # several models); ``action`` is the index of the one being edited.
        self.actions: List[dict] = []
        self.action: Optional[int] = None
        self._next = 1

    # ------------------------------------------------------------------ #
    # Documents
    # ------------------------------------------------------------------ #
    def current(self) -> dict:
        """The active document (there always is one once the page is built)."""
        return next(d for d in self.docs if d["id"] == self.active)

    def get(self, doc_id: str) -> Optional[dict]:
        return next((d for d in self.docs if d["id"] == doc_id), None)

    def next_name(self, prefix: str = "Modelo") -> str:
        """``"Modelo 3"``: the number of the next document, as the bar shows it."""
        return f"{prefix} {self._next}"

    def new_doc(self, name: str, state: dict, readonly: bool = False,
                origin: dict | None = None) -> dict:
        """Open a new document (without activating it) and return it.

        HOOK FOR ACTION MODELS: the result of applying an action to a model
        is another state; adding it with ``readonly=True`` and an
        ``origin={"label": "action X on model Y"}`` is enough for it to show
        up in the bar, be runnable, evaluable and comparable, and offer
        "duplicate as new model" instead of direct editing.
        """
        doc = {"id": f"d{self._next}", "name": name, "state": copy.deepcopy(state),
               "outcome": None, "dirty": False, "readonly": readonly,
               "origin": origin}
        self._next += 1
        self.docs.append(doc)
        # A freshly opened model joins the compare selection while it fits:
        # one usually wants to see the opened ones together.
        if len(self.compare) < MAX_COMPARE:
            self.compare.append(doc["id"])
        return doc

    def store_active(self, state: dict) -> None:
        """Keep a copy of the live editor state in the active document."""
        self.current()["state"] = copy.deepcopy(state)

    def close(self, doc_id: str) -> Optional[str]:
        """Close a document; return the id to show next, or None.

        The last document is never closed (the page needs one). When the
        active document is the one closed, its left neighbour becomes active
        and its id is returned so the page pours it into the editor; closing
        a background document returns None (nothing to repaint but the bar).
        """
        if len(self.docs) <= 1 or self.get(doc_id) is None:
            return None
        index = next(i for i, d in enumerate(self.docs) if d["id"] == doc_id)
        was_active = doc_id == self.active
        self.docs.pop(index)
        self.compare = [i for i in self.compare if i != doc_id]
        if was_active:
            self.active = self.docs[max(0, index - 1)]["id"]
            return self.active
        return None

    def rename_active(self, name: str) -> bool:
        """Rename the active document; True if the name actually changed."""
        name = (name or "").strip()
        if not name or name == self.current()["name"]:
            return False
        self.current()["name"] = name
        return True

    def load_example(self, key: str) -> bool:
        """Load a library example INTO the active document; False if it is read-only."""
        doc = self.current()
        if doc["readonly"]:
            return False
        doc["state"] = state_from_example(EXAMPLES[key])
        doc["name"] = EXAMPLES[key]["label"]
        doc["outcome"], doc["dirty"] = None, False
        return True

    # ------------------------------------------------------------------ #
    # Comparison selection
    # ------------------------------------------------------------------ #
    def normalise_compare(self) -> None:
        """Drop closed ids and, with fewer than two chosen, default to the first four."""
        ids = [d["id"] for d in self.docs]
        self.compare = [i for i in self.compare if i in ids]
        if len(self.compare) < 2 and len(self.docs) >= 2:
            self.compare = ids[:MAX_COMPARE]

    def chosen(self) -> List[dict]:
        """The documents selected for comparison, in bar order."""
        return [d for d in self.docs if d["id"] in self.compare]

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def selected_action(self) -> Optional[dict]:
        i = self.action
        if not self.actions or i is None or i >= len(self.actions):
            return None
        return self.actions[i]

    def add_action(self, agents: List[str], name: str | None = None) -> dict:
        spec = blank_action(agents, name or f"acción {len(self.actions) + 1}")
        return self.add_action_spec(spec)

    def add_action_spec(self, spec: dict) -> dict:
        """Append an existing spec (an example, a loaded one) and select it."""
        self.actions.append(spec)
        self.action = len(self.actions) - 1
        return spec

    def remove_action(self, index: int) -> None:
        self.actions.pop(index)
        self.action = (len(self.actions) - 1) if self.actions else None

    def select_action(self, index: int) -> None:
        self.action = index if 0 <= index < len(self.actions) else None

    # ------------------------------------------------------------------ #
    # Persistence (GitHub #18)
    # ------------------------------------------------------------------ #
    def save(self, name: str) -> Path:
        """Write every open document and the actions to ``saved_models/<name>.json``."""
        return save_workspace(self.docs, name, self.actions)

    def open(self, path: Path, replace: bool) -> List[dict]:
        """Open a saved workspace, adding to the bar or replacing it.

        Returns the documents that were opened; the first of them is now the
        active one, so the page pours it into the editor. With ``replace``
        the actions are replaced too, otherwise they are appended.

        Raises:
            ValueError / OSError: from the loader, with its message.
        """
        loaded, actions = load_workspace_full(path)
        if replace:
            self.docs.clear()
            self.compare = []
            self.actions = actions
        else:
            self.actions.extend(actions)
        self.action = (len(self.actions) - 1) if self.actions else None
        opened = [self.new_doc(d["name"], d["state"], readonly=d["readonly"],
                               origin=d["origin"]) for d in loaded]
        self.active = opened[0]["id"]
        return opened

    def export_payload(self) -> dict:
        """The active document (plus the actions) as a one-model workspace."""
        return workspace_payload([self.current()], self.actions)

    @staticmethod
    def saved_files() -> List[Path]:
        return list_saved()

    @staticmethod
    def peek(path: Path) -> Dict[str, int]:
        """``{"models": n, "actions": m}`` of a saved file (for the open dialog)."""
        docs, actions = load_workspace_full(path)
        return {"models": len(docs), "actions": len(actions)}

    @staticmethod
    def blank_state(kind: str = "kb") -> dict:
        return blank_state(kind)

"""Saving and loading workspaces (models + action specs) as JSON files under
``saved_models/`` (GitHub #18).
"""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import List, Tuple

from . import base  # noqa: F401  (puts the repository root on sys.path first)
from .actions import blank_action
from .base import ROOT, blank_state


# --------------------------------------------------------------------------- #
# Saving and loading (GitHub #18). A WORKSPACE file holds every open model --
# name, state, read-only flag and provenance -- as plain JSON, so it can be
# re-opened later, shared, or produced by a script that applied actions. The
# files live in ``saved_models/`` next to the code (tracked by git on purpose:
# a saved workspace is part of the project's material, not a scratch output).
# --------------------------------------------------------------------------- #
SAVED = ROOT / "saved_models"


def _saved_dir() -> Path:
    """The folder in force: read through the package so ``adapters.SAVED = …``
    (what the tests do to write into a temporary folder) is honoured here."""
    import importlib

    return importlib.import_module(__package__).SAVED
WORKSPACE_FORMAT = "simulationsbelief-workspace/1"


def workspace_payload(docs: List[dict], actions: List[dict] | None = None) -> dict:
    """The JSON-ready form of a workspace: its documents and its action specs.

    Document ids and run results are not kept (results are recomputed on
    demand, which keeps the files small and the format independent of the
    figures). ``actions`` are the editor specs of :func:`blank_action`.
    """
    import datetime

    return {
        "format": WORKSPACE_FORMAT,
        "saved": datetime.datetime.now().isoformat(timespec="seconds"),
        "models": [
            {"name": d["name"], "state": d["state"],
             "readonly": bool(d.get("readonly", False)), "origin": d.get("origin")}
            for d in docs
        ],
        "actions": [copy.deepcopy(a) for a in (actions or [])],
    }


def save_workspace(docs: List[dict], name: str, actions: List[dict] | None = None) -> Path:
    """Write ``docs`` (and ``actions``) to ``saved_models/<name>.json`` and return the path."""
    import json
    import re

    folder = _saved_dir()
    folder.mkdir(exist_ok=True)
    slug = re.sub(r"[^\w\-. ]+", "_", name).strip() or "workspace"
    path = folder / (slug if slug.endswith(".json") else slug + ".json")
    path.write_text(json.dumps(workspace_payload(docs, actions), ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return path


def load_workspace_full(path: Path) -> Tuple[List[dict], List[dict]]:
    """``(documents, action specs)`` of a workspace file.

    Each state is laid over :func:`blank_state`, and each action over
    :func:`blank_action`, so a file written before a key existed still opens:
    missing fields take their defaults.

    Raises:
        ValueError: if the file is not a workspace of a known format.
    """
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != WORKSPACE_FORMAT:
        raise ValueError(f"{path} is not a workspace saved by the GUI")
    docs = []
    for m in data.get("models", []):
        st = m.get("state") or {}
        state = blank_state(st.get("kind", "kb"))
        state.update(st)
        docs.append({"name": m.get("name") or "Model", "state": state,
                     "readonly": bool(m.get("readonly", False)), "origin": m.get("origin")})
    if not docs:
        raise ValueError(f"{path} contains no models")
    actions = []
    for a in data.get("actions", []):
        spec = blank_action([])
        spec.update(a or {})
        actions.append(spec)
    return docs, actions


def load_workspace(path: Path) -> List[dict]:
    """The documents of a workspace file (see :func:`load_workspace_full`)."""
    return load_workspace_full(path)[0]


def list_saved() -> List[Path]:
    """Saved workspaces, newest first."""
    folder = _saved_dir()
    if not folder.exists():
        return []
    return sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

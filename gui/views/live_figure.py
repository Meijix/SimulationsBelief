"""One live figure (the model preview, the action drawing): debounced,
rendered off the event loop, cached by content.

Graphviz / matplotlib take 0.3-0.8 s per figure, so a render on every edit
would freeze the page. ``schedule`` collapses a burst of edits into one
render 250 ms later, drops renders a newer edit superseded, runs the render
in a worker thread (``run.io_bound``) in the page's ink, and caches the
result by a hash of what was drawn plus the ink, so returning to a state
already drawn costs nothing.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Callable

from nicegui import run as io, ui

from adapters import styled

if TYPE_CHECKING:
    from views.page import Page


class LiveFigure:
    def __init__(self, page: Page, what: str, size: int = 64) -> None:
        self.page = page
        self.what = what            # "model" / "action", for the error text
        self.size = size            # cache bound (oldest entry out)
        self._cache: dict = {}      # key -> figure path | message
        self._seq = 0

    def clear_cache(self) -> None:
        """Forget the drawn figures (they were drawn in another ink)."""
        self._cache.clear()

    def cancel(self) -> None:
        """Drop any render still pending."""
        self._seq += 1

    def schedule(self, container, payload, render: Callable, paint: Callable,
                 pending: Callable | None = None) -> None:
        """Draw ``payload`` after a debounce and hand the result to ``paint``.

        ``render(payload, key)`` runs in a worker thread and returns the
        figure's path or a message; ``key`` is the cache key, also used to
        tag the file so two states never share one. ``pending()`` is called
        when a render is actually needed (to show a spinner). The timer is
        created in ``container``, which must outlive the widget that fired
        the edit.
        """
        self._seq += 1
        seq = self._seq
        with container:
            ui.timer(0.25, lambda: self._draw(seq, payload, render, paint, pending), once=True)

    async def _draw(self, seq: int, payload, render, paint, pending) -> None:
        if seq != self._seq:
            return                                  # superseded by a newer edit
        ink = self.page.theme
        key = hashlib.sha1(json.dumps([payload, ink], sort_keys=True,
                                      default=str).encode()).hexdigest()[:12]
        if key not in self._cache:
            if pending is not None:
                pending()
            try:
                result = await io.io_bound(styled, ink, render, payload, key)
            except ValueError as exc:
                result = str(exc)
            except Exception as exc:  # noqa: BLE001 -- a failed figure must never take the page down
                result = f"Could not draw the {self.what}: {exc}"
                logging.getLogger("nicegui").exception("%s preview failed", self.what)
            if result is None:                      # io_bound: cancelled or shutting down
                return
            if len(self._cache) >= self.size:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = result
            if seq != self._seq:
                return                              # the user moved on meanwhile
        paint(self._cache[key])

"""Formula evaluator: answers in its own card, world by world (or facet by facet)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from adapters import evaluate_state
from theme import CARD, FLAT, FORMULA_HELP, card_title, chip

if TYPE_CHECKING:
    from views.page import Page


class FormulasView:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.input = None
        self.help = None
        self.out = None

    def build(self) -> None:
        with ui.card().classes(CARD).props(FLAT):
            card_title("Evaluar fórmula")
            self.input = ui.input(
                "fórmula", placeholder="B_a p & ~K_a p",
            ).props("dense outlined input-class=font-mono").classes("w-full")
            self.help = ui.markdown(FORMULA_HELP["kb"]).classes("text-xs text-grey-5")
            ui.button("Evaluar", icon="calculate", on_click=lambda: self.evaluate()) \
                .props("outline dense")
            self.input.on("keydown.enter", lambda: self.evaluate())
            self.out = ui.column().classes("w-full gap-2")

    def set_help(self, kind: str) -> None:
        self.help.set_content(FORMULA_HELP[kind])

    def clear(self) -> None:
        self.out.clear()

    def evaluate(self) -> None:
        page = self.page
        self.out.clear()
        simplicial = page.state["kind"] == "simplicial"
        try:
            rows = evaluate_state(page.live_state(), self.input.value or "")
        except ValueError as exc:
            with self.out:
                ui.html(f"<pre style='white-space:pre-wrap' "
                        f"class='text-pink-3 text-xs'>{exc}</pre>")
            return
        holds = sum(1 for _, ok in rows if ok)
        with self.out:
            with ui.row().classes("gap-1"):
                for world, ok in rows:
                    chip(world, "ok" if ok else "bad", icon="check" if ok else "close")
            unit = "facetas" if simplicial else "mundos"
            ui.label(
                f"Válida en el modelo (vale en todas las {unit})." if simplicial and holds == len(rows)
                else "Válida en el modelo (vale en todos los mundos)." if holds == len(rows)
                else f"Vale en {holds} de {len(rows)} {unit}."
            ).classes("text-xs text-grey-5")

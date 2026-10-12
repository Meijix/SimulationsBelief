"""The page, one module per region (step 3 of the GUI refactor, 2026-10-11).

``gui/app.py`` used to be one 2 000-line page function with ~80 nested
closures sharing two dicts. It is now:

    page.py               Page: the shared context (workspace, live state,
                          the views) and the orchestration that crosses views
                          (switching documents, read-only locking, repaint).
    header.py             title, example library, the Run button
    docs_bar.py           open documents, save / open / download
    editor.py             identifiers, switches and the relational editor
    simplicial_editor.py  the direct-complex editor (vertices, facets)
    atoms.py              the valuation (atoms on worlds or on vertices)
    formulas.py           the formula evaluator
    actions.py            simplicial actions: editor + apply
    preview.py            the live preview and the "results are stale" strip
    results.py            run the pipeline and paint its result
    compare.py            2-4 models side by side

Every view is a small class holding ``self.page``; it builds its widgets
once (``build``), repaints them from the state (``paint``) and reaches other
regions through ``self.page.<view>``. No view keeps model state of its own:
the model is ``page.state`` and the documents are ``page.ws``.
"""

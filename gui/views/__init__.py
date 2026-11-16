"""The page, one module per region:

    page.py               Page: the shared context (workspace, the active
                          document's state, the views) and the moves that
                          cross views (switching documents, read-only
                          locking, repaint).
    header.py             title, theme toggle, example library, the Run button
    docs_bar.py           open documents, save / open / download, compare controls
    editor.py             identifiers, switches and the relational editor
    simplicial_editor.py  the direct-complex editor (vertices, facets)
    atoms.py              the valuation (atoms on worlds or on vertices)
    formulas.py           the formula evaluator
    actions.py            simplicial actions: editor + apply
    live_figure.py        one debounced, cached, off-the-loop figure
    preview.py            the live preview and the "results are stale" strip
    results.py            run the pipeline and paint its result
    compare.py            2-4 models side by side

Every view is a small class holding ``self.page``; it builds its widgets
once (``build``), repaints them from the state (``paint``) and reaches other
regions through ``self.page.<view>``. No view keeps model state of its own:
the model is ``page.state`` (the active document's) and the documents are
``page.ws``.
"""

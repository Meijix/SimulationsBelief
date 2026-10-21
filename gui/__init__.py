"""The web GUI (NiceGUI). Run it with ``python gui/app.py`` or, once the
project is installed (``pip install -e .``), with ``simulationsbelief-gui``.

The modules inside import each other flat (``from adapters import …``,
``from views.page import …``): ``app.py`` puts this folder on ``sys.path``
before importing them, so both ways of running work.
"""

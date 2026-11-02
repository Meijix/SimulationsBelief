# -*- coding: utf-8 -*-
"""Bisimilarity checking: the implementation, next to the chapter it follows.

``import bisimulation`` works exactly as it did when this was a single module at
the repository root: the public names are re-exported below, so nothing that
already uses it has to know it became a package.

What the folder holds, together on purpose -- the algorithm is not obvious, and
reading it next to its source is the point:

    bisimulation.py           the implementation (Kanellakis-Smolka)
    kanellakisalgoritmo.pdf   Aceto, Ingolfsdottir & Srba, "The Algorithmics of
                              Bisimilarity"; §0.2 is the algorithm, and
                              ``_split`` / ``coarsest_stable_partition`` follow
                              its Figures 0.1 and 0.2 line by line
    README.md                 what to read first, and where the theory is

ONE NAME, THREE THINGS. This package, its module and one of its functions are
all called ``bisimulation``. The star-import below runs after the submodule is
loaded, so it binds the FUNCTION last: after ``import bisimulation``,
``bisimulation.bisimulation(M, N)`` is the function that returns the largest
bisimulation between two models, which is what every caller means. Write
``from bisimulation import bisimulation as bisimulation_module`` only if you
really want the module object.
"""

from .bisimulation import *          # noqa: F401,F403  (re-export the public API)
from .bisimulation import __all__    # noqa: F401       (and the list that defines it)

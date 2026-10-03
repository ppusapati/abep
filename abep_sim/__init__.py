"""abep_sim — system-closure simulator for the DRDO TDF ABEP-VLEO bid.

The sweep helpers (run_grid, summarize) are resolved lazily (PEP 562) so that importing the package, or any physics
module, does not import the assessment layer (A9.22 layer separation; tests/test_layer_separation_physics.py). The
public names are unchanged.
"""
from .system import Config, Budgets, evaluate
from .thruster import CARDS
__all__ = ["Config", "Budgets", "evaluate", "run_grid", "summarize", "CARDS"]


def __getattr__(name):
    if name in ("run_grid", "summarize"):
        from . import sweep
        return getattr(sweep, name)
    raise AttributeError(f"module 'abep_sim' has no attribute {name!r}")

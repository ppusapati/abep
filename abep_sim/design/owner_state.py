"""DEPRECATED import shim (A9.22 layer separation): owner-question answer state for the design-synthesis lane records.

The owner-question state v5 reader moved to the assessment layer, abep_sim/assessment/design_gates.py (``owner_state``,
``status_label``, ``apply_to_questions``; behaviour identical). Design code never reads docs state: the F-lane
builders pass the resulting question-status text into their records. This module only re-exports the moved names
so existing builders (``from abep_sim.design import owner_state as ost``) keep working; new code imports
design_gates directly.
"""
from __future__ import annotations

from ..assessment.design_gates import (OQ5_REL, REPO, TBD_OWNER, _rows, apply_to_questions,  # noqa: F401
                                       owner_state, status_label)

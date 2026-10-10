"""Assessment layer: evaluation-only constraint checks of architecture results (owner directive A9.22, 2026-10-03).

Physics / closure modules compute physical and design quantities. Whether a quantity satisfies an owner-supplied limit
(thrust band, bus-power cap, mass limit, firing life) is an ASSESSMENT, and it lives here. The limits always arrive as
explicit arguments (a DesignConstraints instance, a limits mapping or a threshold); defaults come only from the single
seam abep_sim.operating_inputs. Nothing in this module parses RFP / RVM clauses.

What routes through this module
  closure_constraint_flags   archengine.close_architecture output flags thrust_min_ok / thrust_max_ok / mass_ok / life_ok /
                             all_constraints_ok (the in-loop candidate REJECTION stays in archengine: it is selection under
                             caller-supplied DesignConstraints, functionally unchanged)
  design_constraints         the caller-built DesignConstraints preset (archengine.rfp_preset delegates here)
  band_cap_flags             arch_compare per-member flags thrust_within_rfp_range / P_bus_within_rfp_cap (key names kept
                             for output compatibility)
  limits_record              the limits block arch_compare writes into its output
  mass_plausibility_screen   mass_bom plausibility screen against a caller-supplied mass threshold
  uq_success / life_ok       uq_modular success and life flags against a caller-supplied firing-life requirement
  hard gates                 abep_sim.hard_gates is the assessment-layer hard-gate evaluator (it reads the gate matrix, never
                             a physics constant); evaluate_hard_gates / evaluate_all_hard_gates route to it
"""
from __future__ import annotations

from typing import Any, Mapping

from .. import operating_inputs as OI


# ------------------------------------------------------------------------------------------- archengine closure flags
def design_constraints(*, P_bus_max_W: float | None = None, m_max_kg: float | None = None,
                       T_min_mN: float | None = None, T_max_mN: float | None = None,
                       life_min_h: float | None = None, **kw):
    """The constraint preset a caller hands to archengine. Defaults: operating choices from abep_sim.operating_inputs;
    the wet-mass limit from the engineering constraints and the firing-life floor from the HC-07 assessment threshold
    (owner ruling 2026-10-04: neither is an operating-scenario input)."""
    from ..archengine import DesignConstraints
    from ..configuration import load_engineering_constraints, load_gate_thresholds
    return DesignConstraints(P_bus_max_W=OI.P_BUS_MAX_W if P_bus_max_W is None else P_bus_max_W,
                             m_max_kg=load_engineering_constraints()["mass_max_kg"] if m_max_kg is None else m_max_kg,
                             T_min_mN=OI.THRUST_MIN_mN if T_min_mN is None else T_min_mN,
                             T_max_mN=OI.THRUST_MAX_mN if T_max_mN is None else T_max_mN,
                             life_min_h=load_gate_thresholds()["limits"]["HC-07"] if life_min_h is None else life_min_h,
                             **kw)


def closure_constraint_flags(T_mN: float, mev_kg: float, life_h: float, dc) -> dict:
    """Evaluation-only flags of one closed architecture against the caller's DesignConstraints (None = no limit)."""
    f = {"thrust_min_ok": (dc.T_min_mN is None) or (T_mN >= dc.T_min_mN),
         "thrust_max_ok": (dc.T_max_mN is None) or (T_mN <= dc.T_max_mN),
         "mass_ok": (dc.m_max_kg is None) or (mev_kg <= dc.m_max_kg),
         "life_ok": (dc.life_min_h is None) or (life_h >= dc.life_min_h)}
    f["all_constraints_ok"] = f["thrust_min_ok"] and f["thrust_max_ok"] and f["mass_ok"] and f["life_ok"]
    return f


# ------------------------------------------------------------------------------------------- arch_compare flags
def default_limits(root=None) -> dict:
    """Assessment limits from the frozen engineering constraints (A9.23; same values as the operating-inputs seam)."""
    from ..configuration import load_engineering_constraints
    ec = load_engineering_constraints(root)
    return {"thrust_min_mN": ec["thrust_min_mN"], "thrust_max_mN": ec["thrust_max_mN"], "power_max_W": ec["power_max_W"]}


def band_cap_flags(T_mN: float, P_bus_W: float, limits: Mapping[str, float]) -> dict:
    """Thrust inside [thrust_min_mN, thrust_max_mN] and P_bus <= power_max_W (output key names kept for compatibility)."""
    return {"thrust_within_rfp_range": limits["thrust_min_mN"] <= T_mN <= limits["thrust_max_mN"],
            "P_bus_within_rfp_cap": P_bus_W <= limits["power_max_W"]}


def limits_record(limits: Mapping[str, float], source: str) -> dict:
    return {"thrust_min_mN": limits["thrust_min_mN"], "thrust_max_mN": limits["thrust_max_mN"],
            "power_max_W": limits["power_max_W"], "source": source}


# ------------------------------------------------------------------------------------------- mass screen
def mass_plausibility_screen(items_by_arch: dict, *, threshold_kg: float, system_margin_fraction: float) -> dict:
    from ..mass_bom import plausibility_screen
    return plausibility_screen(items_by_arch, threshold_kg=threshold_kg, system_margin_fraction=system_margin_fraction)


# ------------------------------------------------------------------------------------------- UQ flags
def life_ok(life_h: float, firing_hours: float) -> bool:
    return life_h >= firing_hours


def uq_success(ratio_min: float, life_h: float, firing_hours: float) -> bool:
    return bool(ratio_min >= 1.0 and life_ok(life_h, firing_hours))


# ------------------------------------------------------------------------------------------- hard gates
def evaluate_hard_gates(architecture: str, evidence: Any, **kw) -> dict:
    from .. import hard_gates
    return hard_gates.evaluate(architecture, evidence, **kw)


def evaluate_all_hard_gates(evidence: Any, **kw) -> dict:
    from .. import hard_gates
    return hard_gates.evaluate_all(evidence, **kw)

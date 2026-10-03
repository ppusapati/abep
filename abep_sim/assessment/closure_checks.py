"""Assessment layer for the system closure (owner decision A9.22 items 6 and 7, 2026-10-03).

`abep_sim.system.physics_closure(cfg)` returns raw physical / design quantities and model labels only (schema
``raw_closure_v2``). Everything that compares those quantities with a requirement, a programme target or an
architecture preference lives here:

  * requirement checks (``chk_*``) and the RFP / technical classifications (``rfp_compliant``, ``abep_closed``,
    ``technical_compliant``, ``technical_closed``, ``feasible``);
  * the indigenous-content (IC) metrics ``ic_thruster`` / ``ic_total`` (programme metrics computed from the raw
    masses and IC *priors*, not physics);
  * the architecture-preference flag ``hall_preferred`` (card attribute ``Card.hall``).

The IC priors and the Hall-preference attribute stay where they lived (``Card.ic_thruster``, ``Stage1.ic``,
``Card.hall``, ``Budgets.ic_*``, ``Budgets.m_cbe_target_kg``) for compatibility with existing tools (sweep YAML
``budgets``/``card_overrides`` and the UQ priors mutate them), but only this module reads them.

``assess(raw, constraints, priors)`` performs the same comparisons, with the same operands and the same expression
order, as the pre-split ``system.evaluate``; ``legacy_merge(raw, assessed)`` rebuilds the pre-split ``evaluate`` dict
(same keys, same order, same values). A frozen fixture generated at base commit 9eb302c checks this
(tests/test_raw_assessment_split.py).

Requirement ids are *pointers* into the RVM (docs/requirements/rvm_a9/rvm_a9_v1.json). A check result here is a
parametric-screening comparison, never verification evidence for the RVM row it points to.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional

ASSESSMENT_SCHEMA_VERSION = "closure_assessment_v1"
RAW_SCHEMA_VERSION = "raw_closure_v2"          # must equal abep_sim.system.RAW_CLOSURE_SCHEMA_VERSION
RVM_SOURCE = "docs/requirements/rvm_a9/rvm_a9_v1.json"

# Check name -> RVM row ids it points to (pointer only; empty = no RVM row; the check is an internal/model gate).
REQUIREMENT_POINTERS: dict[str, tuple[str, ...]] = {
    "thrust_air_ge_req": ("RVM-02",),           # THRUST_12MN_SUSTAINED
    "thrust_peak_25mN": ("RVM-03",),            # THRUST_25MN_CAPABILITY
    "power_air": ("RVM-04", "RVM-05"),          # PBUS_LT_1500W_FULL_BUS; P_cap = 1.5 kW x (1 - margin) ~ 1.35 kW allocation
    "power_peak": ("RVM-04", "RVM-05"),
    "mass": ("RVM-06",),                        # MASS_LT_40KG_WET
    "mass_mev": ("RVM-06",),
    "mass_cbe_target": (),                      # internal 32 kg CBE target; no RVM row (RVM-07 is the 34/36 kg allocation)
    "life": ("RVM-12", "RVM-13"),               # FIRING_GT_15000H_PROVISIONAL; MISSION_LIFE_GE_26280H
    "ic_total": ("RVM-18",),                    # INDIGENOUS_CONTENT
    "ic_thruster": ("RVM-18",),
    "compressor_feasible": (),                  # model feasibility gate (sizing / convergence / domain), not an RFP clause
    "hall_preferred": ("RVM-11",),              # HALL_PREFERENCE
    "net_drag_comp_air": (),                    # T/D >= 1 on air: physical closure gate, not an RFP clause
    "thermal": ("RVM-17",),                     # THERMAL_CLOSURE
}

# Hard RFP checks (pre-split `hard` list; `thermal` is appended on the engineering path).
HARD_CHECKS = ("thrust_air_ge_req", "thrust_peak_25mN", "power_air", "power_peak", "mass", "life",
               "ic_total", "ic_thruster", "compressor_feasible")
IC_CHECKS = ("ic_total", "ic_thruster")

# Raw-closure keys used only by this layer; they are not part of the legacy evaluate() dict.
RAW_ONLY_KEYS = ("raw_schema_version", "T_air_N", "T_req_N", "T_peak_N", "comp_feasible",
                 "eng_life_model_ok_flags", "eng_thermal_radiator_feasible")
# Keys the raw closure must never carry (assessment responsibility).
FORBIDDEN_RAW_PREFIXES = ("chk_", "rfp_", "ic_")
FORBIDDEN_RAW_KEYS = ("hall_preferred", "feasible", "rfp_compliant", "abep_closed", "technical_compliant",
                      "technical_closed")


@dataclass(frozen=True)
class Constraints:
    """Requirement limits / programme targets the raw closure is assessed against."""
    thrust_max_mN: float          # peak-capability point (RFP 25 mN)
    power_max_W: float            # RFP bus-power limit
    p_margin_frac: float          # power margin held against power_max_W
    mass_max_kg: float            # RFP wet-mass limit
    ic_total_min: float
    ic_thruster_min: float
    m_cbe_target_kg: float        # internal CBE target
    life_margin_min: float = 1.0
    T_over_D_min: float = 1.0
    thrust_peak_rel_tol: float = 0.999

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AssessmentPriors:
    """Programme priors read only by the assessment layer (IC estimates, architecture-preference attribute)."""
    ic_thruster: float
    thruster_mass_kg: float
    stage1_ic: Optional[float]
    stage1_mass_kg: Optional[float]
    ic_intake: float
    ic_compressor: float
    ic_pse: float
    ic_structure: float
    hall_preferred: bool


def constraints_from_config(cfg, root=None) -> Constraints:
    """Pre-split constraint values: the frozen engineering-constraint limits (A9.23:
    config/constraints/engineering_constraints_v1.json; same values as the former abep_sim.constants.RFP fields) plus
    the config's Budgets margin / CBE target. ``root`` selects a config root (default: abep_sim.configuration)."""
    from ..configuration import load_engineering_constraints
    ec = load_engineering_constraints(root)
    b = cfg.budgets
    return Constraints(thrust_max_mN=ec["thrust_max_mN"], power_max_W=ec["power_max_W"],
                       p_margin_frac=b.p_margin_frac, mass_max_kg=ec["mass_max_kg"], ic_total_min=ec["ic_total_min"],
                       ic_thruster_min=ec["ic_subsystem_min"]["thruster"], m_cbe_target_kg=b.m_cbe_target_kg)


def priors_from_config(cfg) -> AssessmentPriors:
    """IC priors and the Hall-preference attribute of cfg's architecture card (read live: UQ / sweep overrides
    mutate the card in CARDS) and of cfg.budgets."""
    from ..thruster import CARDS
    card = CARDS[cfg.architecture]
    b = cfg.budgets
    s1 = card.stage1
    return AssessmentPriors(ic_thruster=card.ic_thruster, thruster_mass_kg=card.mass_kg,
                            stage1_ic=s1.ic if s1 else None, stage1_mass_kg=s1.mass_kg if s1 else None,
                            ic_intake=b.ic_intake, ic_compressor=b.ic_compressor, ic_pse=b.ic_pse,
                            ic_structure=b.ic_structure, hall_preferred=card.hall)


def ic_metrics(raw: dict, pr: AssessmentPriors) -> tuple:
    """Mass-weighted (dry) indigenous content; same expression as the pre-split evaluate."""
    m_thr = raw["m_thruster_kg"]
    ic_thr = pr.ic_thruster
    if pr.stage1_ic is not None:
        ic_thr = (pr.thruster_mass_kg * pr.ic_thruster + pr.stage1_mass_kg * pr.stage1_ic) / m_thr
    m_intake, m_comp, m_ppu, m_struct = raw["m_intake_kg"], raw["m_comp_kg"], raw["m_ppu_kg"], raw["m_struct_kg"]
    ic_num = (m_thr * ic_thr + m_intake * pr.ic_intake + m_comp * pr.ic_compressor
              + m_ppu * pr.ic_pse + m_struct * pr.ic_structure)
    ic_total = ic_num / (m_thr + m_intake + m_comp + m_ppu + m_struct)
    return ic_thr, ic_total


def assess(raw: dict, constraints: Constraints, priors: AssessmentPriors) -> dict:
    """Compare a raw closure (physics_closure output) with the constraints. Returns a flat dict:
    checks (``chk_*``), IC metrics, the classifications and the requirement pointers."""
    if raw.get("raw_schema_version") != RAW_SCHEMA_VERSION:
        raise ValueError(f"assess(): expected raw schema {RAW_SCHEMA_VERSION}, got {raw.get('raw_schema_version')!r}")
    c = constraints
    eng = raw["engineering_model"] == "physics"
    P_cap = c.power_max_W * (1 - c.p_margin_frac)
    ic_thr, ic_total = ic_metrics(raw, priors)
    checks = {
        "thrust_air_ge_req": raw["T_air_N"] >= raw["T_req_N"],
        "thrust_peak_25mN": raw["T_peak_N"] >= c.thrust_max_mN * 1e-3 * c.thrust_peak_rel_tol,
        "power_air": raw["P_total_air_W"] <= P_cap,
        "power_peak": raw["P_total_peak_W"] <= P_cap,
        "mass": (raw["m_mev_kg"] if eng else raw["m_total_kg"]) <= c.mass_max_kg,
        "life": None,
        "ic_total": ic_total >= c.ic_total_min,
        "ic_thruster": ic_thr >= c.ic_thruster_min,
        "compressor_feasible": raw["comp_feasible"],
        "hall_preferred": priors.hall_preferred,
        "net_drag_comp_air": raw["T_over_D_air"] >= c.T_over_D_min,
    }
    hard = list(HARD_CHECKS)
    technical = [k for k in hard if k not in IC_CHECKS]
    if eng:
        f = raw["eng_life_model_ok_flags"]
        checks["life"] = all(f[k] for k in ("hall_channel", "blade_coating", "magnet", "cathode", "compressor")) \
            and f["intake_coating"]
        checks["thermal"] = raw["eng_thermal_radiator_feasible"]
        hard.append("thermal")
        technical = technical + ["thermal"]
    else:
        checks["life"] = raw["life_margin"] >= c.life_margin_min
    rfp_compliant = all(checks[k] for k in hard)
    abep_closed = rfp_compliant and checks["net_drag_comp_air"]
    technical_compliant = all(checks[k] for k in technical)
    technical_closed = technical_compliant and checks["net_drag_comp_air"]
    return {
        "assessment_schema_version": ASSESSMENT_SCHEMA_VERSION,
        "raw_schema_version": raw["raw_schema_version"],
        "chk_mass_mev": raw["m_mev_kg"] <= c.mass_max_kg,
        "chk_mass_cbe_target": raw["m_cbe_kg"] <= c.m_cbe_target_kg,
        "ic_thruster": ic_thr, "ic_total": ic_total,
        "feasible": rfp_compliant, "rfp_compliant": rfp_compliant, "abep_closed": abep_closed,
        "technical_compliant": technical_compliant, "technical_closed": technical_closed,
        **{f"chk_{k}": v for k, v in checks.items()},
        "requirement_pointers": {k: list(REQUIREMENT_POINTERS.get(k, ())) for k in
                                 list(checks) + ["mass_mev", "mass_cbe_target"]},
        "requirement_pointer_source": RVM_SOURCE,
        "constraints": c.to_dict(),
    }


_AFTER_MEV = ("chk_mass_mev", "chk_mass_cbe_target", "ic_thruster", "ic_total")
_AFTER_COMP_RATIO = ("feasible", "rfp_compliant", "abep_closed", "technical_compliant", "technical_closed")


def legacy_merge(raw: dict, assessed: dict) -> dict:
    """Rebuild the pre-split ``system.evaluate`` dict (same keys, order and values)."""
    out = {}
    for k, v in raw.items():
        if k in RAW_ONLY_KEYS:
            continue
        out[k] = v
        if k == "m_mev_kg":
            out.update((kk, assessed[kk]) for kk in _AFTER_MEV)
        elif k == "comp_ratio_effective":
            out.update((kk, assessed[kk]) for kk in _AFTER_COMP_RATIO)
    out.update((k, v) for k, v in assessed.items() if k.startswith("chk_") and k not in _AFTER_MEV)
    return out


def assessment_columns(merged: dict) -> list:
    """Legacy evaluate() keys that belong to the assessment layer (for the assessment sweep file)."""
    return [k for k in merged if k.startswith("chk_") or k in _AFTER_MEV or k in _AFTER_COMP_RATIO]

"""Programme layer: closure records that combine the raw physics with the assessment layer (A9.22).

evaluate             the legacy merged system-closure record (pre-split abep_sim.system.evaluate output: same keys,
                     order and values): raw closure abep_sim.system.physics_closure + abep_sim.assessment checks / IC
                     metrics / classifications, merged by abep_sim.assessment.legacy_merge (owner item 6: kept for
                     existing tools). The implementation moved here from abep_sim/system.py; abep_sim.system.evaluate
                     remains a delegating compatibility entry (the immutable upstream ICD v1 and the RTM v1 name it).
close_architecture   abep_sim.archengine.close_architecture (the design-only nested closure) plus the evaluation-only
                     closure constraint flags (abep_sim.assessment.arch_constraints.closure_constraint_flags) at the
                     record position they always had: the record is identical to the pre-move archengine output.
"""
from __future__ import annotations

from .. import system as _system

# flags inserted right after this key of a closed (feasible-path) archengine record, as before the move
_FLAGS_AFTER_KEY = "gas_states_by_evidence_class"


def evaluate(cfg: "_system.Config") -> dict:
    """Pre-split merged record (raw closure + assessment), same keys / order / values as before A9.22 Phase B."""
    from ..assessment import assess, constraints_from_config, priors_from_config, legacy_merge
    raw = _system.physics_closure(cfg)
    return legacy_merge(raw, assess(raw, constraints_from_config(cfg), priors_from_config(cfg)))


def close_architecture(a: dict, gas_fn, sc, dc=None, k_margin: float = 1.3,
                       gas_vars: dict | None = None, strict: bool = False, firing_hours: float | None = None,
                       keep_candidates: bool = True, size_arrays: bool = False, mission_envelope: bool = False,
                       envelope_margin: float = 1.1, flight: bool = False) -> dict:
    """archengine.close_architecture + the evaluation-only flags thrust_min_ok / thrust_max_ok / mass_ok / life_ok /
    all_constraints_ok against the caller's DesignConstraints (None = the archengine default DesignConstraints()),
    evaluated on the record's own T_mN, MEV_kg and life_sys_h (the exact values the flags were computed from inside
    archengine before the move). Records that end before the closed-design block (INCOMPATIBLE, INFEASIBLE,
    MODEL_ERROR, MODEL_NOT_CONVERGED) never carried the flags and are returned unchanged."""
    from .. import archengine as AE
    from ..assessment.arch_constraints import closure_constraint_flags
    out = AE.close_architecture(a, gas_fn, sc, dc, k_margin, gas_vars, strict, firing_hours, keep_candidates,
                                size_arrays, mission_envelope, envelope_margin, flight)
    if _FLAGS_AFTER_KEY not in out:
        return out
    flags = closure_constraint_flags(out["T_mN"], out["MEV_kg"], out["life_sys_h"], dc or AE.DesignConstraints())
    rec = {}
    for k, v in out.items():
        rec[k] = v
        if k == _FLAGS_AFTER_KEY:
            rec.update(flags)
    return rec


def run_all(gas_fn, sc, dc=None, k_margin: float = 1.3, gas_vars: dict | None = None,
            strict: bool = False, archs=None, flight: bool = False):
    """archengine.run_all with the assessed closure records (programme close_architecture)."""
    import pandas as pd
    from .. import archengine as AE
    rows = []
    for a in (archs or AE.enumerate_architectures()):
        if flight and not AE.flight_eligible(a):
            rows.append({"architecture": AE.arch_name(a), "valid": a["valid"], "feasible": False,
                         "status": "EXCLUDED_HISTORICAL_NON_FLIGHT",
                         "reason": AE.FLIGHT_EXCLUDED_NEUTRALIZERS[a["neutralizer"].name]})
            continue
        rows.append(close_architecture(a, gas_fn, sc, dc, k_margin, gas_vars, strict))
    return pd.DataFrame(rows)

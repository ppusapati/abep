"""Programme layer: the full architecture-comparison record (A9.22 layer separation).

abep_sim.arch_compare computes the comparison (members x architectures on the common bus boundary, envelopes, paired
differences) without any evaluation-only flag (``compare_architectures_unassessed``). This module attaches what the
harness used to compute inline, at the same record positions, so the output is identical to the pre-move
``arch_compare.compare_architectures`` record (same keys, order and values):

  * ``rfp_flags`` (last key of every OK member result): band / cap flags of abep_sim.assessment.arch_constraints
    (thrust inside [thrust_min_mN, thrust_max_mN], P_bus <= power_max_W) on the result's own thrust_mN / P_bus_W, plus
    ``thrust_exceeds_drag`` when the upstream state carries a drag;
  * ``constraint_robustness`` (after ``metrics`` in every envelope; None for an INCOMPLETE envelope);
  * ``rfp_limits`` (after ``ledger_residual_gate_frac``): the limits record and its source label.
"""
from __future__ import annotations

from collections.abc import Mapping

from .. import arch_compare as AC
from ..arch_compare import EXPECTED_BOUNDARY_VERSION, STATUS_OK, UpstreamState
from ..assessment import arch_constraints as _AC


def _rfp_flags(res: dict, upstream: UpstreamState, limits: Mapping) -> dict:
    flags = _AC.band_cap_flags(res["metrics"]["thrust_mN"], res["metrics"]["P_bus_W"], limits)
    if upstream.drag_N is not None:
        flags["thrust_exceeds_drag"] = res["hall"]["thrust_N"] > upstream.drag_N
    return flags


def _constraint_robustness(arch: str, ids: list, results: dict, env: dict):
    if env["status"] != "COMPLETE":
        return None
    rows = {mid: results[mid][arch] for mid in ids}
    flags = set.intersection(*(set(r["rfp_flags"]) for r in rows.values()))
    return {f: {"n_true": sum(bool(r["rfp_flags"][f]) for r in rows.values()), "n_members": len(ids),
                "holds_for_all_members": all(bool(r["rfp_flags"][f]) for r in rows.values())} for f in sorted(flags)}


def _insert_after(d: dict, after: str, key: str, value) -> dict:
    out = {}
    for k, v in d.items():
        out[k] = v
        if k == after:
            out[key] = value
    return out


def compare_architectures(specs, upstream: UpstreamState, hall_maps: Mapping, *, ledger=None,
                          ensemble: Mapping | None = None,
                          expected_boundary_version: str = EXPECTED_BOUNDARY_VERSION,
                          limits: Mapping | None = None) -> dict:
    """Evaluate every spec'd architecture for EVERY admitted member on the common bus boundary
    (abep_sim.arch_compare.compare_architectures_unassessed) and attach the evaluation-only flags.

    specs      ArchitectureSpec per architecture (subset of ARCHITECTURES, no repeats)
    upstream   UpstreamState, identical for all members and architectures
    hall_maps  {member_id: {arch: path | {'path', 'sha256'}}}; keys must be exactly the admitted members
    ledger     None -> abep_sim.arch_boundary.bus_power_ledger (imported now); or an injected callable
    ensemble   None -> the frozen ensemble file via hall_ensemble.load_ensemble(); an injected mapping is for tests
    limits     {thrust_min_mN, thrust_max_mN, power_max_W} for the evaluation-only flags (A9.22: caller-supplied);
               None -> abep_sim.operating_inputs (today abep_sim.constants.RFP)
    """
    limits_source = "abep_sim.constants.RFP" if limits is None else "caller-supplied"
    limits = _AC.default_limits() if limits is None else {k: float(limits[k]) for k in ("thrust_min_mN", "thrust_max_mN", "power_max_W")}
    raw = AC.compare_architectures_unassessed(specs, upstream, hall_maps, ledger=ledger, ensemble=ensemble,
                                              expected_boundary_version=expected_boundary_version)
    ids, archs, results = raw["members"], raw["architectures"], raw["results"]
    for mid in ids:
        for arch in archs:
            res = results[mid][arch]
            if res["status"] == STATUS_OK:
                res["rfp_flags"] = _rfp_flags(res, upstream, limits)
    envelopes = {a: _insert_after(env, "metrics", "constraint_robustness",
                                  _constraint_robustness(a, ids, results, env))
                 for a, env in raw["envelopes"].items()}
    out = _insert_after(raw, "ledger_residual_gate_frac", "rfp_limits", _AC.limits_record(limits, limits_source))
    out["envelopes"] = envelopes
    return out

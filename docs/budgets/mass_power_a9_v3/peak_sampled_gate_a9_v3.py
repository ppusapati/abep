"""RFP bus-power gate: the owner's peak_sampled rule (A9.14 OQ-A910-03), as a NEW helper beside abep_sim/bus_boundary_a9.

abep_sim/bus_boundary_a9.py is imported only (never modified). Its rfp_power_gate() keeps treating a ``peak_sampled``
ledger as NOT_EVALUABLE in both directions (the A9.1 rule it was written under); this helper implements the later owner
decision A9.14 OQ-A910-03 (docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json, verbatim .md S8.29):

  * ``peak_sampled < 1500 W`` is a ONE-SIDED SUFFICIENT PASS condition, but only for a CONFORMANT record: declared
    >= 100 kSa/s, >= 20 kHz measurement bandwidth, anti-alias filtering, synchronized channels, no saturation and
    total-bus-power reconstruction (every conformant sample < 1500 W, so its 1 ms mean cannot exceed 1500 W);
  * ``peak_sampled >= 1500 W`` is NOT a failure: the proper 1 ms maximum is calculated (bus_boundary_a9.p_bus_1ms_max)
    from the sampled total-bus record, and that value decides; without the samples the record stays NOT_EVALUABLE;
  * a non-conformant record is NOT_EVALUABLE in both directions (no default is assumed for a missing declaration).

Pure arithmetic on the caller's record; no model, no default, no Hall number. Standard library + bus_boundary_a9.
"""
from __future__ import annotations

import math
import os
import sys
from collections.abc import Mapping, Sequence

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from abep_sim import bus_boundary_a9 as bb  # noqa: E402  (import only; never modified)

LIMIT_W = bb.P_BUS_REQUIREMENT_W
MIN_SAMPLE_RATE_SA_S = bb.GATE_MIN_SAMPLE_RATE_SA_S      # 100 kSa/s (A9.1 OQ-A902-01; restated by A9.14 OQ-A910-03)
MIN_BANDWIDTH_HZ = bb.GATE_MIN_BANDWIDTH_HZ              # 20 kHz
RECORD_KEYS = ("peak_sampled_W", "sample_rate_Sa_s", "bandwidth_Hz", "anti_alias_documented", "synchronized",
               "no_saturation", "total_bus_power_reconstruction", "source")
BOOL_KEYS = ("anti_alias_documented", "synchronized", "no_saturation", "total_bus_power_reconstruction")
DECISION = {"key": "A9.14", "id": "OQ-A910-03", "sequenced_no": "S8.29",
            "answer": "PEAK_SAMPLED_BELOW_LIMIT_SUFFICIENT_PASS_NOT_FAILURE_METRIC",
            "json_path": "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json",
            "json_sha256": "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c"}
RULE = ("peak_sampled < 1500 W on a conformant record (>= 100 kSa/s, >= 20 kHz, anti-alias filtering, synchronized "
        "channels, no saturation, total-bus-power reconstruction) is a one-sided sufficient PASS; peak_sampled >= 1500 W "
        "is not a failure - the proper 1 ms maximum decides; a non-conformant record is NOT_EVALUABLE (A9.14 OQ-A910-03)")


class PeakGateError(ValueError):
    """Malformed or internally inconsistent record (fail closed)."""


def _real(v, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
        raise PeakGateError(f"{what} must be a finite number, got {v!r}")
    return float(v)


def record_conformance(rec) -> dict:
    """Validate a peak_sampled record; return its parsed values, conformant flag and every non-conformance reason."""
    if not isinstance(rec, Mapping):
        raise PeakGateError("record must be a mapping")
    extra = set(rec) - set(RECORD_KEYS)
    if extra:
        raise PeakGateError(f"unknown record keys {sorted(extra)}")
    missing = [k for k in RECORD_KEYS if k not in rec]
    if missing:
        raise PeakGateError(f"record lacks {missing} (no default is assumed)")
    for k in BOOL_KEYS:
        if not isinstance(rec[k], bool):
            raise PeakGateError(f"{k} must be a bool")
    if not isinstance(rec["source"], str) or not rec["source"].strip():
        raise PeakGateError("source must be a non-empty string")
    fs = _real(rec["sample_rate_Sa_s"], "sample_rate_Sa_s")
    bw = _real(rec["bandwidth_Hz"], "bandwidth_Hz")
    pk = _real(rec["peak_sampled_W"], "peak_sampled_W")
    reasons = []
    if fs < MIN_SAMPLE_RATE_SA_S:
        reasons.append(f"sample rate {fs:g} Sa/s < {MIN_SAMPLE_RATE_SA_S:g}")
    if bw < MIN_BANDWIDTH_HZ:
        reasons.append(f"bandwidth {bw:g} Hz < {MIN_BANDWIDTH_HZ:g}")
    for k in BOOL_KEYS:
        if rec[k] is not True:
            reasons.append(f"{k} not declared")
    return {"peak_sampled_W": pk, "sample_rate_Sa_s": fs, "bandwidth_Hz": bw, "source": rec["source"],
            "conformant": not reasons, "nonconformance": reasons}


def peak_sampled_gate(rec, samples_W=None) -> dict:
    """Evaluate one steady or start-up record under A9.14 OQ-A910-03 (strict limit P < 1500 W)."""
    c = record_conformance(rec)
    out = {"rule": RULE, "decision": dict(DECISION), "limit_W": LIMIT_W, "strict": True,
           "peak_sampled_W": c["peak_sampled_W"], "conformant": c["conformant"], "nonconformance": c["nonconformance"],
           "P_bus_1ms_max_W": None, "basis": None, "verdict": None}
    if samples_W is not None:
        if isinstance(samples_W, (str, Mapping)) or not isinstance(samples_W, Sequence) or not samples_W:
            raise PeakGateError("samples_W must be a non-empty sequence of total-bus power samples (W)")
        mx = max(_real(x, "sample") for x in samples_W)
        if mx != c["peak_sampled_W"]:
            raise PeakGateError(f"declared peak_sampled_W {c['peak_sampled_W']:g} != max of the samples {mx:g}")
    if not c["conformant"]:
        out.update(verdict="NOT_EVALUABLE", basis="NONCONFORMANT_RECORD")
        return out
    if c["peak_sampled_W"] < LIMIT_W:
        out.update(verdict="PASS", basis="ONE_SIDED_SUFFICIENT_PEAK_SAMPLED_BELOW_LIMIT")
        return out
    if samples_W is None:
        out.update(verdict="NOT_EVALUABLE", basis="PEAK_AT_OR_ABOVE_LIMIT_IS_NOT_A_FAILURE_1MS_MAXIMUM_REQUIRED")
        return out
    r = bb.p_bus_1ms_max(list(samples_W), c["sample_rate_Sa_s"], c["bandwidth_Hz"], True, True)
    v = r["P_bus_1ms_max_W"]
    out.update(P_bus_1ms_max_W=v, basis="P_BUS_1MS_MAX_FROM_SAMPLES", verdict="PASS" if v < LIMIT_W else "FAIL")
    return out


def rfp_power_gate_peak_sampled(steady, startup) -> dict:
    """Gate over the steady record and EVERY start-up record (start-up must not be empty): FAIL if any FAIL, PASS only
    if all PASS, otherwise NOT_EVALUABLE. Each entry is (record, samples_W or None)."""
    if isinstance(startup, (str, Mapping)) or not isinstance(startup, Sequence) or not startup:
        raise PeakGateError("start-up records are required (the gate covers start-up transients)")
    rows = [("steady", peak_sampled_gate(*steady))] + [("startup", peak_sampled_gate(*s)) for s in startup]
    vs = {r["verdict"] for _, r in rows}
    overall = "FAIL" if "FAIL" in vs else ("PASS" if vs == {"PASS"} else "NOT_EVALUABLE")
    return {"verdict": overall, "rows": [dict(r, role=role) for role, r in rows], "rule": RULE}

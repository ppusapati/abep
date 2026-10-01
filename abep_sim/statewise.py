"""Statewise envelope quantifier (A9.14 S9.7 / OD2): a pure function over caller-supplied states.

Moved verbatim out of the orbit-dataset accessor module (which re-exports it unchanged, same function object) so
that installed production modules (e.g. ``abep_sim.design.upstream_a9_13``) can use it without importing the
accessor of the repository-only orbit dataset (A9.17 DATA_SIZE: no installed production module imports that
accessor). No data is read here.
"""
from __future__ import annotations

import math

import numpy as np

A9_14_JSON = "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json"
A9_14_SHA256 = "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c"


def statewise_quantifier(states, margin_fn, requirement_id: str) -> dict:
    """Evaluate ``margin_fn(state) -> float`` (>= 0 passes) or ``-> bool`` at every required state.

    Verdict is PASS only if every state passes; a non-finite or failing evaluation is fail-closed (MODEL_ERROR is
    reported separately from FAIL). The worst state (minimum margin) is always reported. An orbit average is reported
    only when every state carries a time ``weight`` (orbit_states); it is informational and never enters the verdict.
    Weights, where given, must be finite and >= 0, and a fully weighted set must have a positive sum (else ValueError).
    """
    states = list(states)
    if not states:
        raise ValueError("statewise_quantifier: no states supplied; an empty set cannot satisfy a requirement")
    if not requirement_id:
        raise ValueError("requirement_id is required")
    weights = [st.get("weight") for st in states]
    if any(w is not None for w in weights):
        for st, w in zip(states, weights):
            if w is None:
                continue
            if isinstance(w, (bool, np.bool_)) or not isinstance(w, (int, float, np.floating, np.integer)) \
                    or not math.isfinite(float(w)) or float(w) < 0.0:
                raise ValueError(f"state {st.get('state_id')!r}: weight must be a finite number >= 0, got {w!r}")
        if all(w is not None for w in weights) and not sum(float(w) for w in weights) > 0.0:
            raise ValueError("statewise_quantifier: state weights sum to 0; no orbit average can be formed")
    per, errors = [], []
    for st in states:
        sid = st.get("state_id")
        if sid is None:
            raise ValueError("every state needs a state_id")
        try:
            m = margin_fn(st)
        except Exception as e:  # fail closed, never skip
            errors.append({"state_id": sid, "error": f"{type(e).__name__}: {e}"})
            per.append({"state_id": sid, "margin": None, "pass": False, "status": "MODEL_ERROR"})
            continue
        if isinstance(m, (bool, np.bool_)):
            val, ok = (0.0 if m else -1.0), bool(m)
        else:
            val = float(m)
            ok = math.isfinite(val) and val >= 0.0
            if not math.isfinite(val):
                errors.append({"state_id": sid, "error": "non-finite margin"})
                per.append({"state_id": sid, "margin": None, "pass": False, "status": "MODEL_ERROR"})
                continue
        per.append({"state_id": sid, "margin": val, "pass": ok, "status": "PASS" if ok else "FAIL"})
    finite = [p for p in per if p["margin"] is not None]
    worst = min(finite, key=lambda p: p["margin"]) if finite else None
    n_fail = sum(1 for p in per if p["status"] == "FAIL")
    verdict = "MODEL_ERROR" if errors else ("PASS" if n_fail == 0 else "FAIL")
    orbit_avg = None
    if not errors and all(w is not None for w in weights):
        W = sum(float(w) for w in weights)
        orbit_avg = sum(float(w) * p["margin"] for w, p in zip(weights, per)) / W
    return {"requirement_id": requirement_id, "verdict": verdict, "n_states": len(per), "n_fail": n_fail,
            "n_model_error": len(errors), "worst_state": worst, "orbit_average_margin": orbit_avg,
            "orbit_average_note": ("informational only; verdict is statewise (A9.14 S9.7 OD2, A9.13 S6.15)"
                                   if orbit_avg is not None else "not reported: states carry no time weights"),
            "average_hides_violation": bool(orbit_avg is not None and orbit_avg >= 0.0 and verdict != "PASS"),
            "per_state": per, "errors": errors,
            "authority": {"A9.14 S9.7 OD2": {"path": A9_14_JSON, "sha256": A9_14_SHA256}}}

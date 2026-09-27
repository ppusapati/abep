"""Pass/fail analysis for the W4 actual-hardware capability demonstration (fo_capability_demo_prep).

Pure functions only. They take the raw calibration readings of a future demonstration and return the demonstrated
(Type A / Type B) uncertainty and a verdict against targets that the CALLER supplies (lane-25 targets copied from the
instrumentation definition, or owner-frozen values). Nothing here holds a physical value, an efficiency or a target:
every input is explicit and missing / non-finite inputs raise (CLAUDE.md rule 3, no silent fallbacks).

This module is a PROPOSED analysis for the owner's calibration-plan freeze (S1-C5). It never replaces lane 25's
readiness_n() (LOCK-1 rule, docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json), which fixes
n at LOCK-2 from the S1 values; the verdicts here are the pre-S1 capability screen that the S1-C4 record reports.

Statistics: GUM (JCGM 100:2008) Type A = sample standard deviation with nu = N - 1 degrees of freedom; Type B carried
with nu = inf unless the certificate states otherwise; effective degrees of freedom by Welch-Satterthwaite (GUM G.4.1,
Eq. G.2b); coverage factor per owner addendum A3 (planning k = 2; with low nu_eff the evaluated Student-t factor at the
~95.45 % coverage probability that k = 2 gives for a normal distribution, documented with the record).
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

from scipy import stats

#: coverage probability of k = 2 for a normal distribution (2 * Phi(2) - 1); A3 "the ~95 % expanded-uncertainty convention"
P_K2 = 2.0 * stats.norm.cdf(2.0) - 1.0

EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")

#: S1-C4 required instrument categories (docs/experiments/s1_readiness/s1_readiness_conditions_v1.json, S1-C4 'covers')
S1C4_CATEGORIES = (
    "thrust_stand", "bus_power_metering", "discharge_current", "flow", "pressure", "temperature",
    "magnetic_field_Bz", "stability_oscillations", "species_divergence",
)

#: A3 cathode-temperature labels (owner addendum A3 cathode_temperature; INS-23 labelling rule)
CATHODE_TUBE_LABEL = "cathode_tube_temperature"
EMITTER_LABEL = "emitter_temperature"
UNMEASURED = "unmeasured"


def _finite(name: str, x) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f"{name} must be a finite number, got {x!r}")
    return float(x)


def _seq(name: str, xs: Iterable, min_len: int) -> list[float]:
    if xs is None:
        raise ValueError(f"{name} is required")
    out = [_finite(f"{name}[{i}]", x) for i, x in enumerate(xs)]
    if len(out) < min_len:
        raise ValueError(f"{name} needs at least {min_len} values, got {len(out)}")
    return out


# ----------------------------------------------------------------------------------------------------------------------
# Type A / Type B, Welch-Satterthwaite, coverage factor
# ----------------------------------------------------------------------------------------------------------------------
def type_a(readings: Sequence[float]) -> dict:
    """Mean, sample SD s (nu = N - 1) and standard uncertainty of the mean s / sqrt(N) (GUM 4.2)."""
    xs = _seq("readings", readings, 2)
    n = len(xs)
    mean = math.fsum(xs) / n
    s = math.sqrt(math.fsum((x - mean) ** 2 for x in xs) / (n - 1))
    return {"n": n, "mean": mean, "s": s, "u_mean": s / math.sqrt(n), "nu": n - 1}


def sigma_upper_bound(s: float, nu: int, confidence: float) -> float:
    """One-sided upper confidence bound of a normal sigma from a sample SD: s * sqrt(nu / chi2_{1-conf}(nu))."""
    s = _finite("s", s)
    if s < 0:
        raise ValueError("s must be >= 0")
    if not isinstance(nu, int) or nu < 1:
        raise ValueError("nu must be an integer >= 1")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    return s * math.sqrt(nu / stats.chi2.ppf(1.0 - confidence, nu))


def nu_eff(components: Sequence[tuple[float, float]]) -> float:
    """Welch-Satterthwaite (GUM G.4.1, Eq. G.2b). components = [(u_i, nu_i)], nu_i = math.inf for Type B as known."""
    if not components:
        raise ValueError("components is required")
    num = 0.0
    den = 0.0
    for i, (u, nu) in enumerate(components):
        u = _finite(f"u[{i}]", u)
        if u < 0:
            raise ValueError("u_i must be >= 0")
        if not (nu == math.inf or (isinstance(nu, (int, float)) and nu >= 1)):
            raise ValueError(f"nu[{i}] must be >= 1 or math.inf, got {nu!r}")
        num += u * u
        if nu != math.inf:
            den += u ** 4 / nu
    if num == 0:
        raise ValueError("combined uncertainty is zero")
    return math.inf if den == 0 else num ** 2 / den


def combined(components: Sequence[tuple[float, float]]) -> float:
    return math.sqrt(math.fsum(_finite("u", u) ** 2 for u, _ in components))


def coverage_factor(nu: float, k_planning: float, low_dof_tolerance: float) -> dict:
    """Owner addendum A3: planning k (= 2 by the A3 decision); when the Student-t factor at P_K2 for nu exceeds
    k_planning by more than low_dof_tolerance the evaluated factor is used and the record says so.
    k_planning and low_dof_tolerance are explicit inputs (the tolerance is a PROPOSED owner threshold)."""
    k_planning = _finite("k_planning", k_planning)
    tol = _finite("low_dof_tolerance", low_dof_tolerance)
    if not (nu == math.inf or (isinstance(nu, (int, float)) and nu >= 1)):
        raise ValueError(f"nu must be >= 1 or math.inf, got {nu!r}")
    k_eval = 2.0 if nu == math.inf else float(stats.t.ppf(0.5 + P_K2 / 2.0, nu))
    low = k_eval > k_planning + tol
    return {"k": k_eval if low else k_planning, "k_evaluated": k_eval, "k_planning": k_planning,
            "low_effective_dof": low, "nu_eff": nu, "coverage_probability": P_K2}


def expanded(components: Sequence[tuple[float, float]], k_planning: float, low_dof_tolerance: float) -> dict:
    u_c = combined(components)
    cf = coverage_factor(nu_eff(components), k_planning, low_dof_tolerance)
    return {"u_c": u_c, "U": cf["k"] * u_c, **cf}


# ----------------------------------------------------------------------------------------------------------------------
# verdicts against caller-supplied targets
# ----------------------------------------------------------------------------------------------------------------------
def implied_n(u_measured: float, targets_by_n: Mapping[int, float]) -> int | None:
    """Smallest block count n whose per-reading target is met (u_measured <= target[n]); None if none is.
    targets_by_n: the lane-25 plan_by_n values (u_T_max, u_P_max or u_inst_max) as copied by the caller."""
    u = _finite("u_measured", u_measured)
    if not targets_by_n:
        raise ValueError("targets_by_n is required")
    for n in sorted(targets_by_n):
        if u <= _finite(f"target[{n}]", targets_by_n[n]):
            return int(n)
    return None


def repeatability_verdict(s: float, nu: int, targets_by_n: Mapping[int, float], confidence: float) -> dict:
    """Capability screen of a repeatability (sample SD s, nu dof) against the lane-25 per-n targets.
    MEETS_N<n>: the point estimate meets the target for block count n; 'confident' when the one-sided upper bound at
    `confidence` also meets it. EXCEEDS_ALL_TARGETS: D0 goes to the owner before any score-bearing run (lane 25:
    widen delta, raise n, improve instruments / mount, OPTION-DIVERTER, or move facility)."""
    ub = sigma_upper_bound(s, nu, confidence)
    n_pt = implied_n(s, targets_by_n)
    n_ub = implied_n(ub, targets_by_n)
    verdict = "EXCEEDS_ALL_TARGETS" if n_pt is None else f"MEETS_N{n_pt}"
    return {"verdict": verdict, "implied_n_point": n_pt, "implied_n_upper_bound": n_ub, "confident": n_ub is not None,
            "s": s, "nu": nu, "sigma_upper_bound": ub, "confidence": confidence}


def linear_calibration(applied: Sequence[float], response: Sequence[float]) -> dict:
    """Least-squares response = a + b * applied; residual SD (nu = N - 2) and max |residual| / span."""
    x = _seq("applied", applied, 3)
    y = _seq("response", response, 3)
    if len(x) != len(y):
        raise ValueError("applied and response must have equal length")
    n = len(x)
    mx, my = math.fsum(x) / n, math.fsum(y) / n
    sxx = math.fsum((a - mx) ** 2 for a in x)
    if sxx == 0:
        raise ValueError("applied values must span a range")
    b = math.fsum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx
    a0 = my - b * mx
    res = [c - (a0 + b * a) for a, c in zip(x, y)]
    s_res = math.sqrt(math.fsum(r * r for r in res) / (n - 2)) if n > 2 else 0.0
    span = max(y) - min(y)
    if span == 0:
        raise ValueError("response has zero span")
    return {"intercept": a0, "slope": b, "u_slope": s_res / math.sqrt(sxx), "s_residual": s_res, "nu": n - 2,
            "max_nonlinearity_of_span": max(abs(r) for r in res) / span}


def ln_reproducibility(values: Sequence[float]) -> dict:
    """SD of ln(values) across K installations / configurations (nu = K - 1): the relative reproducibility of a
    calibration slope, in ln units comparable with lane 25 u_inst_max."""
    xs = _seq("values", values, 2)
    if any(v <= 0 for v in xs):
        raise ValueError("values must be positive")
    return type_a([math.log(v) for v in xs])


def configuration_slope_shift(slope_ref: tuple[float, float], slope_cfg: tuple[float, float],
                              k_planning: float, low_dof_tolerance: float, nu_ref: int, nu_cfg: int) -> dict:
    """Mass-change behaviour between configurations: ln(b_cfg / b_ref) with its expanded uncertainty from the two
    slope standard uncertainties. DETECTED -> per-configuration calibration is mandatory and the per-configuration
    calibration uncertainty enters the reading; NOT_DETECTED does NOT waive the INS-01 re-calibration rule."""
    (b0, u0), (b1, u1) = slope_ref, slope_cfg
    for nm, v in (("b_ref", b0), ("b_cfg", b1)):
        if _finite(nm, v) <= 0:
            raise ValueError(f"{nm} must be positive")
    comps = [(_finite("u_ref", u0) / b0, nu_ref), (_finite("u_cfg", u1) / b1, nu_cfg)]
    e = expanded(comps, k_planning, low_dof_tolerance)
    shift = math.log(b1 / b0)
    return {"ln_shift": shift, "U": e["U"], "k": e["k"], "nu_eff": e["nu_eff"],
            "verdict": "DETECTED" if abs(shift) > e["U"] else "NOT_DETECTED"}


def drift_rate(times_s: Sequence[float], readings: Sequence[float]) -> dict:
    """Zero (or offset) drift: least-squares slope of readings vs time, per hour, with its standard uncertainty.

    When every reading is identical (e.g. a quantised DAQ whose drift stays inside one count) the fit is undefined and
    the Type A estimate is drift 0 with u 0. That is NOT a demonstrated zero drift: the result carries
    resolution_limited = True and the caller MUST add the Type B resolution term (GUM F.2.2.1: a resolution step q
    gives u = q / (2 sqrt 3) on each reading, i.e. a drift bound of order q / record length) before any verdict.
    The demonstrations state this in their Type B list (resolution term)."""
    t = _seq("times_s", times_s, 3)
    r = _seq("readings", readings, 3)
    if (max(r) - min(r)) == 0:
        return {"drift_per_hour": 0.0, "u_drift_per_hour": 0.0, "nu": len(t) - 2, "resolution_limited": True}
    fit = linear_calibration(t, r)
    return {"drift_per_hour": fit["slope"] * 3600.0, "u_drift_per_hour": fit["u_slope"] * 3600.0, "nu": fit["nu"],
            "resolution_limited": False}


def within_cycle_corrected_reproducibility(s_between: float, s_within: float, r: int) -> dict:
    """Installation reproducibility from cycle means (CD-02). The SD of K cycle means s_between contains the
    within-cycle repeatability s_within / sqrt(r) as well as the installation term (one-way random-effects model):
    s_inst^2 = s_between^2 - s_within^2 / r. Using s_between directly is conservative; this returns both, and the
    corrected value is floored at 0 with a flag when the within term dominates (installation not resolved)."""
    sb = _finite("s_between", s_between)
    sw = _finite("s_within", s_within)
    if sb < 0 or sw < 0:
        raise ValueError("standard deviations must be >= 0")
    if not isinstance(r, int) or isinstance(r, bool) or r < 1:
        raise ValueError("r must be an integer >= 1")
    d = sb * sb - sw * sw / r
    return {"s_inst_conservative": sb, "s_inst_corrected": math.sqrt(d) if d > 0 else 0.0,
            "within_term": sw / math.sqrt(r), "installation_resolved": d > 0}


def pbus_installation_term(shares: Mapping[str, float], s_inst: Mapping[str, float], share_tolerance: float) -> dict:
    """ln(P_bus) installation term of CD-02 from the per-channel gain reproducibilities. P_bus = sum_i P_i, so
    d ln P_bus = sum_i w_i d ln g_i with w_i = P_i / P_bus at the operating point (first order, GUM 5.1.2). With
    independent re-connection of each channel: s_inst,P = sqrt(sum_i w_i^2 s_inst,i^2). Also returned: the
    share-free bound max_i s_inst,i (valid for any shares because sum w_i = 1 and w_i >= 0), usable before the
    LOCK-1 power allocation fixes the shares. Shares are explicit inputs (no default allocation); they must be
    non-negative and sum to 1 within share_tolerance; every channel needs both a share and an s_inst."""
    if set(shares) != set(s_inst) or not shares:
        raise ValueError("shares and s_inst must name the same non-empty set of channels")
    tol = _finite("share_tolerance", share_tolerance)
    w = {k: _finite(f"share[{k}]", v) for k, v in shares.items()}
    s = {k: _finite(f"s_inst[{k}]", v) for k, v in s_inst.items()}
    if any(v < 0 for v in w.values()) or any(v < 0 for v in s.values()):
        raise ValueError("shares and s_inst must be >= 0")
    if abs(math.fsum(w.values()) - 1.0) > tol:
        raise ValueError(f"shares must sum to 1 within {tol}, got {math.fsum(w.values())}")
    return {"s_inst_P": math.sqrt(math.fsum((w[k] * s[k]) ** 2 for k in w)), "share_free_bound": max(s.values())}

def relative_point_errors(setpoints: Sequence[float], reference: Sequence[float]) -> list[float]:
    """(indicated - reference) / reference per point (MFC against a primary flow calibrator)."""
    s = _seq("setpoints", setpoints, 1)
    r = _seq("reference", reference, 1)
    if len(s) != len(r):
        raise ValueError("setpoints and reference must have equal length")
    if any(v <= 0 for v in r):
        raise ValueError("reference flows must be positive")
    return [(a - b) / b for a, b in zip(s, r)]


def channel_skew(edge_times_s: Mapping[str, Sequence[float]]) -> dict:
    """Common-time-base check: every channel records the same injected edges; skew = per-edge max - min across
    channels. Returns the worst skew, the Type A SD of each channel's offset to the first channel, and the drift of
    that offset over the record (clock drift)."""
    if not edge_times_s or len(edge_times_s) < 2:
        raise ValueError("at least two channels are required")
    names = sorted(edge_times_s)
    series = {k: _seq(f"edge_times_s[{k}]", edge_times_s[k], 3) for k in names}
    m = {len(v) for v in series.values()}
    if len(m) != 1:
        raise ValueError("every channel must record the same edges")
    n = m.pop()
    worst = max(max(series[k][i] for k in names) - min(series[k][i] for k in names) for i in range(n))
    ref = series[names[0]]
    per = {}
    for k in names[1:]:
        off = [series[k][i] - ref[i] for i in range(n)]
        spread = max(off) - min(off)
        per[k] = {"mean_offset_s": math.fsum(off) / n, "s_offset_s": type_a(off)["s"],
                  "offset_drift_s_per_s": (drift_rate(ref, off)["drift_per_hour"] / 3600.0) if spread > 0 else 0.0,
                  "resolution_limited": spread == 0}
    return {"worst_skew_s": worst, "reference_channel": names[0], "channels": per, "edges": n}


def phase_error_deg(frequency_hz: float, skew_s: float) -> float:
    """Phase error of a sinusoid at frequency f sampled with a time skew dt: 360 * f * dt (degrees)."""
    return 360.0 * _finite("frequency_hz", frequency_hz) * _finite("skew_s", skew_s)


# ----------------------------------------------------------------------------------------------------------------------
# S1-C4 record item validation (+ A3 cathode-temperature labelling)
# ----------------------------------------------------------------------------------------------------------------------
def _quantity_errors(q, where: str) -> list[str]:
    if not isinstance(q, dict):
        return [f"{where}: must be an object {{value, unit, source, evidence_class}}"]
    errs = []
    v = q.get("value")
    ok_v = (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)) or (
        isinstance(v, dict) and v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v.values()))
    if not ok_v:
        errs.append(f"{where}.value: must be a number or an object of numbers")
    for f in ("unit", "source"):
        s = q.get(f)
        if not isinstance(s, str) or not s.strip() or s.strip().upper().startswith("TBD"):
            errs.append(f"{where}.{f}: non-empty, not TBD")
    if q.get("evidence_class") not in EVIDENCE_CLASSES:
        errs.append(f"{where}.evidence_class: one of {EVIDENCE_CLASSES}")
    return errs


def _iso_date(s) -> bool:
    import datetime as _dt
    if not isinstance(s, str):
        return False
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            _dt.datetime.strptime(s, fmt)
            return True
        except ValueError:
            pass
    return False


def record_item_errors(item: Mapping) -> list[str]:
    """Checks a future S1-C4 record item against the gate's per-item rules (s1_readiness_conditions_v1.json S1-C4
    each_item) plus the fields this lane adds and the A3 cathode-temperature labelling rule. Returns the list of
    failures (empty = passes). Does not recompute sha256 (the S1 gate does that against the repository)."""
    e: list[str] = []
    if not isinstance(item, Mapping):
        return ["item must be an object"]
    cat = item.get("category")
    if cat not in S1C4_CATEGORIES:
        e.append(f"category: one of {S1C4_CATEGORIES}")
    if item.get("evidence_class") != "measured":
        e.append("evidence_class: must be 'measured'")
    if not _iso_date(item.get("calibration_date")):
        e.append("calibration_date: ISO 8601 date")
    rd = item.get("raw_data")
    if not (isinstance(rd, Mapping) and isinstance(rd.get("path"), str)
            and rd["path"].startswith("docs/experiments/instrumentation/raw/")
            and isinstance(rd.get("sha256"), str) and len(rd["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in rd["sha256"])):
        e.append("raw_data: {path under docs/experiments/instrumentation/raw/, sha256 (64 lowercase hex)}")
    du = item.get("demonstrated_uncertainty")
    e += _quantity_errors(du, "demonstrated_uncertainty")
    if isinstance(du, Mapping) and du.get("evidence_class") != "measured":
        e.append("demonstrated_uncertainty.evidence_class: must be 'measured'")
    for f in ("demonstration_id", "instrument_id", "analysis_script_sha256", "calibration_plan_sha256"):
        if not isinstance(item.get(f), str) or not item[f].strip() or item[f].strip().upper().startswith("TBD"):
            e.append(f"{f}: non-empty, not TBD")
    cov = item.get("coverage")
    nu_ok = False
    if isinstance(cov, Mapping):
        nu = cov.get("nu_eff")
        nu_ok = nu == "inf" or (isinstance(nu, (int, float)) and not isinstance(nu, bool)
                                and (nu == math.inf or (math.isfinite(nu) and nu >= 1)))
    if not (isinstance(cov, Mapping) and isinstance(cov.get("k"), (int, float)) and not isinstance(cov.get("k"), bool)
            and nu_ok and isinstance(cov.get("low_effective_dof"), bool)):
        e.append("coverage: {k (number), nu_eff (number >= 1 or 'inf'), low_effective_dof (bool)} (owner addendum A3)")
    # A3 cathode temperature: a thermocouple (or any non-pyrometer sensor) is never labelled emitter temperature
    chans = item.get("channels", [])
    if chans is None:
        chans = []
    if not isinstance(chans, list):
        e.append("channels: must be a list of objects")
        chans = []
    good: list[Mapping] = []
    for i, ch in enumerate(chans):
        if not isinstance(ch, Mapping):
            e.append(f"channels[{i}]: must be an object {{id, label, sensor_type}}")
            continue
        good.append(ch)
        label, sensor = ch.get("label"), ch.get("sensor_type")
        if "emitter" in str(label).lower():
            if sensor != "pyrometer":
                e.append(f"channel {ch.get('id')}: emitter-temperature labels only from a pyrometer (A3)")
            elif not ch.get("emissivity_treatment"):
                e.append(f"channel {ch.get('id')}: pyrometer needs a recorded emissivity treatment (A3)")
    if cat == "temperature":
        scope = item.get("scope")
        if not isinstance(scope, str) or not scope.strip():
            e.append("scope: temperature items must declare their scope ('cathode_c1' for C-1 items) so the A3 "
                     "cathode rule cannot be skipped by omission")
        if scope == "cathode_c1":
            if not any(ch.get("label") == CATHODE_TUBE_LABEL and ch.get("sensor_type") == "thermocouple"
                       for ch in good):
                e.append(f"channels: C-1 items need a mandatory thermocouple channel labelled '{CATHODE_TUBE_LABEL}' "
                         "(A3: a cathode-tube thermocouple is mandatory)")
            em = item.get("emitter_temperature_status")
            has_pyro = any(ch.get("sensor_type") == "pyrometer" and "emitter" in str(ch.get("label")).lower()
                           for ch in good)
            if not has_pyro and em != UNMEASURED:
                e.append("emitter_temperature_status: 'unmeasured' when no pyrometer channel exists (A3)")
    return e

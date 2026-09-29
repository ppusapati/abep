"""Deterministic derivations for the minimum decisive experiment (lane 25, MINEXP). DRAFT_PENDING_OWNER.

Every number in ``experiment_draft.json["derived_numbers"]`` is produced here from
(a) the PROPOSED thresholds in ``experiment_draft.json["thresholds"]`` (owner decisions, not physics),
(b) the variance groups in ``experiment_draft.json["uncertainty"]["variance_groups"]`` (how each component is
    evaluated and how many degrees of freedom it carries),
(c) the run matrix in ``experiment_draft.json["run_matrix"]`` (comparison families, visits and readings),
(d) the planning grids in ``experiment_draft.json["planning_grids"]`` (hypothetical scenarios, labelled as such), and
(e) physical constants read from ``abep_sim/constants.py`` (loaded by file path, so the package ``__init__`` and the
    simulator are never imported or modified).

Statistics follow JCGM 100:2008 (GUM) Annex G: each variance component carries its degrees of freedom (Type A: from
the number of observations; Type B from a certificate or a pre-registered bound: treated as exactly known, nu -> inf,
G.4.3), the effective degrees of freedom come from the Welch-Satterthwaite formula (G.2b), and the simultaneous
half-width is h = k * sigma with k the two-sided Bonferroni Student-t quantile at nu_eff (not the normal quantile).
Student-t quantiles come from scipy (a pinned project dependency, requirements-lock.txt).

Nothing here is a performance prediction. No Hall transport closure, screening candidate or literature Hall
number enters. Missing or inconsistent inputs raise (no defaults, no silent fallbacks).

Usage (from the repository root):
    python docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py            # print derived block
    python docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py --check    # compare with JSON
    python docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py --write    # regenerate JSON block
    python docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py --markdown # key-number table
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRAFT_JSON = HERE / "experiment_draft.json"
REPO_ROOT = HERE.parents[2]
CONSTANTS_PY = REPO_ROOT / "abep_sim" / "constants.py"

TORR_TO_PA = 101325.0 / 760.0          # exact by definition of the torr
SIG = 8                                # significant digits stored in the JSON
SCRIPT_REF = "docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py"
N_SEARCH_CAP = 10000                   # search limit for n_required (bookkeeping bound, not a design value)

EVALUATIONS = ("type_A_in_campaign", "type_A_S1_remount", "type_B")
FAMILIES = ("primary", "iso_power", "facility")


# ----------------------------------------------------------------------------------------------------------------
# inputs
# ----------------------------------------------------------------------------------------------------------------
def _stats():
    try:
        from scipy import stats
    except ImportError as exc:                       # pragma: no cover - scipy is pinned in requirements-lock.txt
        raise ImportError("scipy (pinned in requirements-lock.txt) is required for Student-t quantiles") from exc
    return stats


def load_constants():
    """Load abep_sim/constants.py by path (no package import, no side effects)."""
    if not CONSTANTS_PY.is_file():
        raise FileNotFoundError(f"{CONSTANTS_PY} not found; run from a checkout of the repository")
    spec = importlib.util.spec_from_file_location("_minexp_constants", CONSTANTS_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("E_CHARGE", "AMU", "K_B", "M_SPECIES"):
        if not hasattr(mod, name):
            raise AttributeError(f"abep_sim/constants.py lacks {name}")
    return mod


def load_draft(path: Path = DRAFT_JSON) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _threshold_entry(draft: dict, tid: str) -> dict:
    for t in draft["thresholds"]:
        if t["id"] == tid:
            if t.get("status") != "PROPOSED":
                raise ValueError(f"threshold {tid} is not PROPOSED")
            return t
    raise KeyError(f"threshold {tid} missing from experiment_draft.json")


def threshold(draft: dict, tid: str) -> float:
    """Numeric value of a PROPOSED threshold; raises if absent, non-numeric or not PROPOSED."""
    v = _threshold_entry(draft, tid).get("value")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"threshold {tid} has no numeric value")
    return v


def variance_groups(draft: dict) -> list[dict]:
    """The variance groups of the ln R model, each with its evaluation type (which fixes its degrees of freedom)."""
    groups = draft["uncertainty"]["variance_groups"]
    if not groups:
        raise ValueError("no variance groups")
    ids = [g["id"] for g in groups]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate variance-group ids")
    for g in groups:
        if g.get("evaluation") not in EVALUATIONS:
            raise ValueError(f"variance group {g['id']} has evaluation {g.get('evaluation')!r}; expected {EVALUATIONS}")
        if not isinstance(g.get("averages_down"), bool):
            raise ValueError(f"variance group {g['id']} lacks a boolean averages_down")
        if g["averages_down"] != (g["evaluation"] == "type_A_in_campaign"):
            raise ValueError(f"variance group {g['id']}: only in-campaign Type A groups average down with blocks")
    return groups


def budget_shares(draft: dict) -> dict:
    """T-BUDGET-SHARES: fraction of sigma_max^2 allocated to each variance group. Keys must equal the group ids
    exactly and the fractions must be positive and sum to 1 (refuses an inconsistent allocation)."""
    v = _threshold_entry(draft, "T-BUDGET-SHARES").get("value")
    if not isinstance(v, dict):
        raise ValueError("T-BUDGET-SHARES must map variance-group id -> share")
    ids = [g["id"] for g in variance_groups(draft)]
    if sorted(v) != sorted(ids):
        raise ValueError(f"T-BUDGET-SHARES keys {sorted(v)} != variance groups {sorted(ids)}")
    for k, x in v.items():
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not x > 0:
            raise ValueError(f"T-BUDGET-SHARES[{k}] must be a positive number")
    if not math.isclose(sum(v.values()), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"T-BUDGET-SHARES must sum to 1, got {sum(v.values())}")
    return dict(v)


def share_by_evaluation(draft: dict) -> dict:
    shares = budget_shares(draft)
    out = {e: 0.0 for e in EVALUATIONS}
    for g in variance_groups(draft):
        out[g["evaluation"]] += shares[g["id"]]
    return out


def grid(draft: dict, key: str) -> list:
    g = draft["planning_grids"][key]
    vals = g["values"]
    if not vals:
        raise ValueError(f"planning grid {key} is empty")
    return vals


def even_blocks(n_min: int, n_max: int) -> list[int]:
    """The admissible block counts: even n with T-N-MIN <= n <= T-N-MAX (even: drift cancels over block pairs)."""
    if n_min < 2 or n_min % 2 or n_max % 2 or n_max < n_min:
        raise ValueError(f"need even 2 <= T-N-MIN <= T-N-MAX, got {n_min}, {n_max}")
    return list(range(n_min, n_max + 1, 2))


# ----------------------------------------------------------------------------------------------------------------
# counting the comparison families from the run matrix
# ----------------------------------------------------------------------------------------------------------------
def family_sizes(draft: dict) -> dict:
    """Comparison counts per family: run-matrix rows whose 'families' list contains the family."""
    rows = draft["run_matrix"]["conditions"]
    unknown = {f for r in rows for f in r["families"]} - set(FAMILIES)
    if unknown:
        raise ValueError(f"unknown comparison families {sorted(unknown)}")
    sizes = {f: sum(1 for r in rows if f in r["families"]) for f in FAMILIES}
    if any(v == 0 for v in sizes.values()):
        raise ValueError(f"run matrix defines an empty family: {sizes}")
    return sizes


# ----------------------------------------------------------------------------------------------------------------
# statistics (GUM Annex G)
# ----------------------------------------------------------------------------------------------------------------
def t_two_sided_bonferroni(alpha_fw: float, m: int, nu: float) -> float:
    """Critical value k for m simultaneous two-sided intervals at family-wise level alpha_fw (Bonferroni), Student t
    with nu degrees of freedom (nu = inf gives the normal quantile)."""
    if not (0.0 < alpha_fw < 1.0) or m < 1:
        raise ValueError("need 0 < alpha < 1 and m >= 1")
    if not nu > 0:
        raise ValueError("need nu > 0")
    p = 1.0 - alpha_fw / (2.0 * m)
    st = _stats()
    return float(st.norm.ppf(p)) if math.isinf(nu) else float(st.t.ppf(p, nu))


def t_one_sided(alpha: float, nu: float) -> float:
    if not (0.0 < alpha < 1.0) or not nu > 0:
        raise ValueError("need 0 < alpha < 1 and nu > 0")
    st = _stats()
    return float(st.norm.ppf(1.0 - alpha)) if math.isinf(nu) else float(st.t.ppf(1.0 - alpha, nu))


def welch_satterthwaite(components) -> float:
    """nu_eff = (sum u_i^2)^2 / sum(u_i^4 / nu_i)  (JCGM 100:2008 Eq. G.2b). components: iterable of (variance, nu);
    nu = inf for a Type B component treated as exactly known (G.4.3). Returns inf if every nu is inf."""
    comps = list(components)
    total, denom = 0.0, 0.0
    for var, nu in comps:
        if var is None or var < 0 or not nu > 0:
            raise ValueError("each component needs variance >= 0 and nu > 0")
        total += var
        if not math.isinf(nu):
            denom += var * var / nu
    if total <= 0:
        raise ValueError("total variance must be > 0")
    return math.inf if denom == 0 else total * total / denom


def plan_nu_eff(n: int, K: int, by_eval: dict) -> float:
    """Planning nu_eff with every group exactly at its allocated share (sigma^2 normalised to 1).

    type_A_in_campaign: per-condition block scatter of ln(T/P_bus); half on the source-on side, half on the hall_only
                        side, n - 1 degrees of freedom each (no pooling across conditions);
    type_A_S1_remount:  S1 re-mount series, K cycles -> K - 1 degrees of freedom;
    type_B:             certificates / characterisation treated as exactly known (nu = inf, GUM G.4.3).
    Evaluated at the allocation boundary, which is the smallest nu_eff consistent with the budget being met
    (a smaller random share raises nu_eff), so the resulting k is conservative for planning."""
    if n < 2 or K < 2:
        raise ValueError("need n >= 2 blocks and K >= 2 re-mount cycles")
    vr = by_eval["type_A_in_campaign"]
    comps = [(vr / 2.0, n - 1), (vr / 2.0, n - 1), (by_eval["type_A_S1_remount"], K - 1),
             (by_eval["type_B"], math.inf)]
    return welch_satterthwaite([c for c in comps if c[0] > 0])


def plan_nu_inf(K: int, by_eval: dict) -> float:
    """nu_eff in the limit n -> inf (in-campaign random terms vanish; the non-averaging groups keep their shares)."""
    comps = [(by_eval["type_A_S1_remount"], K - 1), (by_eval["type_B"], math.inf)]
    return welch_satterthwaite([c for c in comps if c[0] > 0])


def sigma_lnR_max(delta: float, k: float) -> float:
    """Largest standard uncertainty of ln R for which every outcome is classifiable (h = k*sigma < delta/2)."""
    if not (delta > 0 and k > 0):
        raise ValueError("need delta > 0 and k > 0")
    return delta / (2.0 * k)


def classify(lnR_hat: float, h: float, delta: float) -> str:
    """Mutually exclusive size classes for a simultaneous interval [lnR_hat - h, lnR_hat + h] against (-delta, delta).

    EQUIVALENT     the whole interval lies inside (-delta, +delta)
    SOURCE_BETTER  not EQUIVALENT and the lower bound is > 0
    SOURCE_WORSE   not EQUIVALENT and the upper bound is < 0
    UNRESOLVED     anything else (possible only when h >= delta/2)
    """
    lo, hi = lnR_hat - h, lnR_hat + h
    if -delta < lo and hi < delta:
        return "EQUIVALENT"
    if lo > 0.0:
        return "SOURCE_BETTER"
    if hi < 0.0:
        return "SOURCE_WORSE"
    return "UNRESOLVED"


def stop_supporting(lnR_hat: float, h: float) -> bool:
    """Sign statement used by the stop rule: the simultaneous upper bound of ln R_arch is below 0, i.e. R_arch < 1,
    i.e. (by the break-even identity) C_del > C_star with simultaneous confidence. Independent of the size class:
    an EQUIVALENT point with its upper bound below 0 supports a stop. Monotone in precision: for a fixed estimate,
    a smaller h never removes stop support from a negative estimate."""
    if h < 0:
        raise ValueError("h must be >= 0")
    return lnR_hat + h < 0.0


def exhaustive_when_h_below_half_delta(delta: float, n_grid: int = 4001) -> dict:
    """Numerical check of the claim: h < delta/2 => UNRESOLVED impossible; h >= delta/2 => UNRESOLVED possible."""
    xs = [(-3.0 + 6.0 * i / (n_grid - 1)) * delta for i in range(n_grid)]
    h_ok = 0.999 * delta / 2.0          # just below delta/2: no gap between the classes
    h_bad = 0.75 * delta                # well above delta/2: a gap delta - h <= |x| <= h opens
    unresolved_ok = sum(classify(x, h_ok, delta) == "UNRESOLVED" for x in xs)
    unresolved_bad = sum(classify(x, h_bad, delta) == "UNRESOLVED" for x in xs)
    return {"unresolved_count_h_below": unresolved_ok, "unresolved_count_h_above": unresolved_bad}


def _nonneg(**kw):
    for name, v in kw.items():
        if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or math.isnan(v):
            raise ValueError(f"{name} must be given and >= 0")


def sigma_lnR(u_T: float, u_P: float, n: int, f_src: float, u_src_scale: float, common, u_inst: float) -> float:
    """Standard uncertainty of ln R_arch = ln[(T/P_bus)_X,on / (T/P_bus)_hall_only] (first order).

    u_T, u_P     relative random uncertainty of one thrust / one bus-power reading (G1, G2); both conditions -> 2/n
    f_src        P_src,bus / P_bus,X (source share of the arm's bus power)
    u_src_scale  relative scale uncertainty of the source load-plane power (G3; power sensor, coupler calibration,
                 reconstructed matching-network/cable loss); does not cancel
    common       sequence of (w_c, u_c): w_c = |P_c,X/P_bus,X - P_c,0/P_bus,0| and the relative scale uncertainty of
                 the common consumer's load-plane meter (G4); partial cancellation
    u_inst       SD of the per-installation offset of ln(T/P_bus) (G5); R_arch compares two installations -> 2 u_inst^2
    Ledger inputs (efficiencies, unmeasured loads) are conditioning inputs, not variance terms (ledger sensitivity)."""
    _nonneg(u_T=u_T, u_P=u_P, f_src=f_src, u_src_scale=u_src_scale, u_inst=u_inst)
    if not isinstance(n, int) or n < 1:
        raise ValueError("n must be an integer >= 1")
    var = 2.0 * u_T ** 2 / n + 2.0 * u_P ** 2 / n + (f_src * u_src_scale) ** 2 + 2.0 * u_inst ** 2
    for w, u in common:
        _nonneg(w_common=w, u_common_scale=u)
        var += (w * u) ** 2
    return math.sqrt(var)


def nu_eff_lnR(u_T: float, u_P: float, n: int, f_src: float, u_src_scale: float, common, u_inst: float,
               nu_rm: float) -> float:
    """Welch-Satterthwaite nu_eff of ln R_arch for the evaluation rules of the draft (random: n - 1 per side;
    re-mount: nu_rm from the S1 series; scale terms Type B, nu = inf)."""
    _nonneg(u_T=u_T, u_P=u_P, f_src=f_src, u_src_scale=u_src_scale, u_inst=u_inst)
    if n < 2:
        raise ValueError("n must be >= 2 for a Type A estimate")
    side = (u_T ** 2 + u_P ** 2) / n
    comps = [(side, n - 1), (side, n - 1), (2.0 * u_inst ** 2, nu_rm), ((f_src * u_src_scale) ** 2, math.inf)]
    comps += [((w * u) ** 2, math.inf) for w, u in common]
    return welch_satterthwaite([c for c in comps if c[0] > 0])


def readiness_n(u_T: float, u_P: float, f_src: float, u_src_scale: float, common, u_inst: float, nu_rm: float,
                delta: float, alpha_fw: float, m: int, n_min: int, n_max: int):
    """D0 (T-READINESS) with the S1 values: the smallest admissible n with k(n)*sigma(n) < delta/2, k from the
    Welch-Satterthwaite nu_eff of the actual S1 variance components. Returns None if no n <= T-N-MAX qualifies."""
    for n in even_blocks(n_min, n_max):
        s = sigma_lnR(u_T, u_P, n, f_src, u_src_scale, common, u_inst)
        k = t_two_sided_bonferroni(alpha_fw, m, nu_eff_lnR(u_T, u_P, n, f_src, u_src_scale, common, u_inst, nu_rm))
        if k * s < delta / 2.0:
            return n
    return None


def n_required(u_reading: float, delta: float, alpha_fw: float, m: int, K: int, by_eval: dict, n_min: int) -> float:
    """Smallest even n >= T-N-MIN with 4 u^2 / n <= w_random * sigma_max(n)^2 (u_T = u_P = u; every other group at
    its allocated share), sigma_max(n) = delta / (2 k_plan(n)). math.inf if none up to N_SEARCH_CAP."""
    _nonneg(u_reading=u_reading)
    w_r = by_eval["type_A_in_campaign"]
    for n in range(n_min, N_SEARCH_CAP + 1, 2):
        k = t_two_sided_bonferroni(alpha_fw, m, plan_nu_eff(n, K, by_eval))
        if 4.0 * u_reading ** 2 / n <= w_r * sigma_lnR_max(delta, k) ** 2:
            return n
    return math.inf


def delta_floor(k_inf: float, s_nonaveraging: float) -> float:
    """Smallest decision margin resolvable with infinitely many blocks: 2 k_inf s (s = non-averaging uncertainty)."""
    return 2.0 * k_inf * s_nonaveraging


# ----------------------------------------------------------------------------------------------------------------
# iso-power comparison (R_iso): linear interpolation of hall_only thrust in bus power between V_nom and V_hi
# ----------------------------------------------------------------------------------------------------------------
def _positive(**kw):
    for name, v in kw.items():
        if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or not v > 0 or math.isinf(v):
            raise ValueError(f"{name} must be a finite number > 0")


def iso_interpolation(P_X: float, T_nom: float, P_nom: float, T_hi: float, P_hi: float) -> dict:
    """T0_iso = hall_only thrust at P_bus = P_X on the chord through (P_nom, T_nom) and (P_hi, T_hi); no
    extrapolation (raises unless P_nom <= P_X <= P_hi). Returns lambda, T0_iso and the elasticity
    eps = (dT0/dP) * P_X / T0_iso of the chord at P_X."""
    _positive(P_X=P_X, T_nom=T_nom, P_nom=P_nom, T_hi=T_hi, P_hi=P_hi)
    if not P_hi > P_nom:
        raise ValueError("need P_hi > P_nom (V_hi above V_nom)")
    if not (P_nom <= P_X <= P_hi):
        raise ValueError("P_bus,X not bracketed by the hall_only V_nom/V_hi references: R_iso is not reported")
    lam = (P_X - P_nom) / (P_hi - P_nom)
    slope = (T_hi - T_nom) / (P_hi - P_nom)
    T0 = T_nom + slope * (P_X - P_nom)
    if not T0 > 0:
        raise ValueError("interpolated hall_only thrust must be > 0")
    return {"lambda": lam, "T0_iso": T0, "eps": slope * P_X / T0}


def ln_R_iso(T_X: float, P_X: float, T_nom: float, P_nom: float, T_hi: float, P_hi: float) -> float:
    _positive(T_X=T_X)
    return math.log(T_X / iso_interpolation(P_X, T_nom, P_nom, T_hi, P_hi)["T0_iso"])


def var_lnR_iso_random(u_T: float, u_P: float, n: int, T_X: float, P_X: float, T_nom: float, P_nom: float,
                       T_hi: float, P_hi: float) -> float:
    """First-order random variance of ln R_iso (independent relative errors u_T/sqrt(n), u_P/sqrt(n) on the six
    block-mean readings). Sensitivities d lnR / d ln x: T_X 1; T_nom -(1-l)T_nom/T0; T_hi -l T_hi/T0; P_X -eps;
    P_nom eps (1-l) P_nom/P_X; P_hi eps l P_hi/P_X."""
    _nonneg(u_T=u_T, u_P=u_P)
    it = iso_interpolation(P_X, T_nom, P_nom, T_hi, P_hi)
    lam, T0, eps = it["lambda"], it["T0_iso"], it["eps"]
    aT, bT = (1 - lam) * T_nom / T0, lam * T_hi / T0
    aP, bP = (1 - lam) * P_nom / P_X, lam * P_hi / P_X
    return (u_T ** 2 / n) * (1 + aT ** 2 + bT ** 2) + (u_P ** 2 / n) * eps ** 2 * (1 + aP ** 2 + bP ** 2)


def sigma_lnR_iso_bound(u_T: float, u_P: float, n: int, eps: float, f_src: float, u_src_scale: float, common,
                        u_inst: float, u_interp: float) -> float:
    """Upper bound on the standard uncertainty of ln R_iso:
    2u_T^2/n + 2 eps^2 u_P^2/n + eps^2[(f_src u_src)^2 + sum (w_c u_c)^2] + 2 u_inst^2 + u_interp^2.
    The interpolation weights (1-l, l) are non-negative and sum to 1 in both T and P, so their squared weights sum
    to at most 1 (proved in the draft; checked numerically by the test). For |eps| <= 1 the bound is at most
    sigma(ln R_arch)^2 + u_interp^2. u_interp is the Type B model error of the linear chord (pre-registered)."""
    _nonneg(u_T=u_T, u_P=u_P, f_src=f_src, u_src_scale=u_src_scale, u_inst=u_inst, u_interp=u_interp)
    if eps is None or math.isnan(eps):
        raise ValueError("eps must be given")
    var = 2 * u_T ** 2 / n + 2 * eps ** 2 * u_P ** 2 / n + eps ** 2 * (f_src * u_src_scale) ** 2 \
        + 2 * u_inst ** 2 + u_interp ** 2
    for w, u in common:
        _nonneg(w_common=w, u_common_scale=u)
        var += eps ** 2 * (w * u) ** 2
    return math.sqrt(var)


# ----------------------------------------------------------------------------------------------------------------
# break-even algebra (identities; no physical values)
# ----------------------------------------------------------------------------------------------------------------
def _eta(eta, name):
    if eta is None or isinstance(eta, bool) or not isinstance(eta, (int, float)) or not (0.0 < eta <= 1.0):
        raise ValueError(f"{name} must be given, 0 < {name} <= 1 (ledger efficiency, bus_power_boundary_v1)")


def ratio_R(T0: float, P0: float, dT: float, dP_d_load: float, eta_d: float, P_src_bus: float,
            dP_other_bus: float) -> float:
    """R = (T1/P1)/(T0/P0) with P1 = P0 + dP_d_load/eta_d + P_src_bus + dP_other_bus (bus_power_boundary_v1 sums).
    Refuses T0 <= 0, P0 <= 0, P_src_bus < 0, T1 = T0 + dT < 0 and P1 <= 0."""
    _eta(eta_d, "eta_d")
    _positive(T0=T0, P0=P0)
    _nonneg(P_src_bus=P_src_bus)
    T1 = T0 + dT
    P1 = P0 + dP_d_load / eta_d + P_src_bus + dP_other_bus
    if T1 < 0:
        raise ValueError("source-on thrust T0 + dT must be >= 0")
    if not P1 > 0:
        raise ValueError("source-on bus power must be > 0")
    return (T1 / P1) / (T0 / P0)


def delivered_ion_cost(P_src_bus: float, I_del: float) -> float:
    """C_del = P_src,bus / I_del [W/A = V: bus energy per elementary charge delivered, in eV]."""
    _nonneg(P_src_bus=P_src_bus)
    _positive(I_del=I_del)
    return P_src_bus / I_del


def breakeven_cost(y: float, P0_over_T0: float, kappa: float, V_d: float, eta_d: float,
                   dP_other_over_Idel: float) -> float:
    """C* [W/A = V]: R > 1  <=>  C_del = P_src_bus / I_del < C*.

    y      = dT / I_del        thrust gained per ampere of delivered ions
    kappa  = dI_d / I_del      discharge-current response per ampere of delivered ions (fixed V_d)
    """
    _eta(eta_d, "eta_d")
    _positive(P0_over_T0=P0_over_T0, V_d=V_d)
    return y * P0_over_T0 - kappa * V_d / eta_d - dP_other_over_Idel


def breakeven_efficiency(P_src_load: float, I_del: float, C_star: float, P_mag_bus: float):
    """Source-chain ledger efficiency at which R_arch = 1, every other ledger input fixed:
    P_src_load/eta + P_mag_bus = C* I_del  ->  eta_be = P_src_load / (C* I_del - P_mag_bus).
    Returns None when C* I_del - P_mag_bus <= 0 (no efficiency reaches break-even). eta_be > 1 means no physical
    chain does."""
    _positive(P_src_load=P_src_load, I_del=I_del)
    _nonneg(P_mag_bus=P_mag_bus)
    room = C_star * I_del - P_mag_bus
    return None if room <= 0 else P_src_load / room


def y_max(mass_kg: float, V_d: float, charge_state: int, e: float) -> float:
    """Ion-momentum ceiling on thrust per delivered ampere: ions of charge Z e fully accelerated through V_d, no
    divergence: T/I = m v/(Z e) = sqrt(2 m V_d/(Z e)). Seeding of Hall ionization or better Hall-on transport can
    exceed it, so it is a screen, never a stop rule."""
    _positive(mass_kg=mass_kg, V_d=V_d, e=e)
    if not isinstance(charge_state, int) or charge_state < 1:
        raise ValueError("charge_state must be an integer >= 1")
    return math.sqrt(2.0 * mass_kg * V_d / (charge_state * e))


def pumping_speed_required(mdot_kgps: float, mass_kg: float, T_K: float, p_b_Pa: float, k_B: float) -> float:
    """Effective pumping speed S = Q/p_b [m^3/s], Q = (mdot/m) k_B T (throughput at the gauge-wall temperature)."""
    _positive(mdot_kgps=mdot_kgps, mass_kg=mass_kg, T_K=T_K, p_b_Pa=p_b_Pa, k_B=k_B)
    return (mdot_kgps / mass_kg) * k_B * T_K / p_b_Pa


# ----------------------------------------------------------------------------------------------------------------
# derived block
# ----------------------------------------------------------------------------------------------------------------
def _r(x: float) -> float:
    if x == 0 or math.isinf(x) or math.isnan(x):
        return x
    return float(f"{x:.{SIG}g}")


def _num(value, unit: str, source: str, note: str | None = None) -> dict:
    d = {"value": value, "unit": unit, "evidence_class": "model-derived", "source": f"{SCRIPT_REF}: {source}"}
    if note:
        d["note"] = note
    return d


def derive(draft: dict | None = None) -> dict:
    draft = load_draft() if draft is None else draft
    c = load_constants()

    delta = threshold(draft, "T-DELTA")
    alpha_fw = threshold(draft, "T-ALPHA-FW")
    alpha_screen = threshold(draft, "T-ALPHA-SCREEN")
    n_min = int(threshold(draft, "T-N-MIN"))
    n_max = int(threshold(draft, "T-N-MAX"))
    K = int(threshold(draft, "T-S1-REMOUNT-CYCLES"))
    shares = budget_shares(draft)
    groups = variance_groups(draft)
    by_eval = share_by_evaluation(draft)
    ns = even_blocks(n_min, n_max)
    fam = family_sizes(draft)

    out: dict = {
        "generated_by": SCRIPT_REF,
        "inputs": {"thresholds": ["T-DELTA", "T-ALPHA-FW", "T-ALPHA-SCREEN", "T-N-MIN", "T-N-MAX",
                                  "T-S1-REMOUNT-CYCLES", "T-BUDGET-SHARES", "T-KNEE-LEVELS"],
                   "variance_groups": [g["id"] for g in groups],
                   "run_matrix": ["conditions (families, visits)", "bench_conditions", "reading_rule"],
                   "planning_grids": ["f_src", "u_reading", "s_nonaveraging", "delta_alternatives",
                                      "remount_cycles_alternatives", "background_pressure_torr",
                                      "gauge_wall_temperature_K", "species"],
                   "constants": "abep_sim/constants.py (E_CHARGE, AMU, K_B, M_SPECIES)",
                   "quantiles": "scipy.stats t and norm (pinned, requirements-lock.txt)"},
        "m_family": {f: _num(m, "-", f"family_sizes(run_matrix) rows with family == '{f}'") for f, m in fam.items()},
        "share_by_evaluation": {e: _num(_r(v), "fraction of sigma_max^2", "sum of T-BUDGET-SHARES over the variance "
                                        f"groups with evaluation == '{e}'") for e, v in by_eval.items()},
        "k_primary_known_variance_limit": _num(_r(t_two_sided_bonferroni(alpha_fw, fam["primary"], math.inf)), "-",
                                               "t_two_sided_bonferroni(T-ALPHA-FW, m_primary, nu = inf): normal "
                                               "quantile, reached only if every component were exactly known; "
                                               "reference only, not used for classification"),
    }

    plan: dict = {}
    for n in ns:
        nu = plan_nu_eff(n, K, by_eval)
        k_p = t_two_sided_bonferroni(alpha_fw, fam["primary"], nu)
        k_i = t_two_sided_bonferroni(alpha_fw, fam["iso_power"], nu)
        k_f = t_two_sided_bonferroni(alpha_fw, fam["facility"], nu)
        s_p, s_i, s_f = sigma_lnR_max(delta, k_p), sigma_lnR_max(delta, k_i), sigma_lnR_max(delta, k_f)
        src = f"n = {n} blocks, K = T-S1-REMOUNT-CYCLES = {K}"
        row = {
            "nu_eff": _num(_r(nu), "-", f"plan_nu_eff(n, K, share_by_evaluation) (Welch-Satterthwaite, GUM G.2b), {src}"),
            "k_primary": _num(_r(k_p), "-", f"t_two_sided_bonferroni(T-ALPHA-FW, m_primary, nu_eff), {src}"),
            "sigma_lnR_max": _num(_r(s_p), "ln-ratio", f"T-DELTA / (2 k_primary), {src}"),
            "group_share_max": {g["id"]: _num(_r(s_p * math.sqrt(shares[g["id"]])), "ln-ratio",
                                              f"sigma_lnR_max * sqrt(T-BUDGET-SHARES[{g['id']}]), {src}")
                                for g in groups},
            "u_T_max": _num(_r(s_p * math.sqrt(shares["G1"] * n / 2.0)), "relative (1 sigma, per reading)",
                            f"2 u_T^2 / n = T-BUDGET-SHARES[G1] sigma_lnR_max^2, {src}"),
            "u_P_max": _num(_r(s_p * math.sqrt(shares["G2"] * n / 2.0)), "relative (1 sigma, per reading)",
                            f"2 u_P^2 / n = T-BUDGET-SHARES[G2] sigma_lnR_max^2, {src}"),
            "u_inst_max": _num(_r(s_p * math.sqrt(shares["G5"] / 2.0)), "ln-ratio (1 sigma, per installation)",
                               f"2 u_inst^2 = T-BUDGET-SHARES[G5] sigma_lnR_max^2, {src}"),
            "k_iso": _num(_r(k_i), "-", f"t_two_sided_bonferroni(T-ALPHA-FW, m_iso_power, nu_eff), {src}"),
            "sigma_lnR_max_iso": _num(_r(s_i), "ln-ratio", f"T-DELTA / (2 k_iso), {src}"),
            "u_interp_max": _num(_r(math.sqrt(s_i ** 2 - s_p ** 2)), "ln-ratio",
                                 f"sqrt(sigma_lnR_max_iso^2 - sigma_lnR_max^2): room for the chord model error when "
                                 f"|eps| <= 1 and every R_arch group is at its share, {src}"),
            "k_facility": _num(_r(k_f), "-", f"t_two_sided_bonferroni(T-ALPHA-FW, m_facility, nu_eff), {src}"),
            "sigma_lnR_max_facility": _num(_r(s_f), "ln-ratio", f"T-DELTA / (2 k_facility), {src}"),
        }
        plan[str(n)] = row
    out["plan_by_n"] = plan

    n0 = ns[0]
    s_p0 = sigma_lnR_max(delta, t_two_sided_bonferroni(alpha_fw, fam["primary"], plan_nu_eff(n0, K, by_eval)))
    out["u_source_scale_max_by_f_src"] = {
        str(f): _num(_r(s_p0 * math.sqrt(shares["G3"]) / f), "relative (1 sigma)",
                     f"sigma_lnR_max(n = T-N-MIN = {n0}) * sqrt(T-BUDGET-SHARES[G3]) / f_src, f_src = {f} "
                     f"(planning grid, hypothetical)")
        for f in grid(draft, "f_src")
    }

    kk: dict = {}
    for Kalt in grid(draft, "remount_cycles_alternatives"):
        nu = plan_nu_eff(n0, int(Kalt), by_eval)
        kk[f"K={int(Kalt)}"] = {
            "nu_eff": _num(_r(nu), "-", f"plan_nu_eff(n = T-N-MIN = {n0}, K = {int(Kalt)}) (planning grid)"),
            "k_primary": _num(_r(t_two_sided_bonferroni(alpha_fw, fam["primary"], nu)), "-",
                              f"t_two_sided_bonferroni(T-ALPHA-FW, m_primary, nu_eff), n = {n0}, K = {int(Kalt)}"),
        }
    out["k_primary_by_remount_cycles"] = kk

    nu_inf = plan_nu_inf(K, by_eval)
    k_inf = t_two_sided_bonferroni(alpha_fw, fam["primary"], nu_inf)
    out["n_to_infinity"] = {
        "nu_eff": _num(_r(nu_inf), "-", f"plan_nu_inf(K = {K}): the non-averaging groups at their share ratio"),
        "k_primary": _num(_r(k_inf), "-", "t_two_sided_bonferroni(T-ALPHA-FW, m_primary, nu_eff(n -> inf))"),
    }
    out["delta_floor_by_s_nonaveraging"] = {
        str(s): _num(_r(delta_floor(k_inf, s)), "ln-ratio",
                     f"delta_floor(k_primary(n -> inf), s = {s}) = 2 k s (planning grid, hypothetical)")
        for s in grid(draft, "s_nonaveraging")
    }

    nreq: dict = {}
    for d_alt in grid(draft, "delta_alternatives"):
        row = {}
        for u in grid(draft, "u_reading"):
            nv = n_required(u, d_alt, alpha_fw, fam["primary"], K, by_eval, n_min)
            row[f"u={u}"] = _num(nv, "blocks", f"n_required(u = {u}, delta = {d_alt}, K = {K}): smallest even n >= "
                                               f"T-N-MIN with 4 u^2 / n <= share(type_A_in_campaign) "
                                               f"(delta / (2 k_plan(n)))^2")
            row[f"u={u}"]["within_T_N_MAX"] = nv <= n_max
        nreq[f"delta={d_alt}"] = row
    out["n_required"] = nreq

    out["screen"] = {
        "k_screen_known_variance": _num(_r(t_one_sided(alpha_screen, math.inf)), "-",
                                        "t_one_sided(T-ALPHA-SCREEN, nu = inf): lower limit of the screen's k"),
        "k_screen_all_type_A": _num(_r(t_one_sided(alpha_screen, n_min - 1)), "-",
                                    f"t_one_sided(T-ALPHA-SCREEN, nu = T-N-MIN - 1 = {n_min - 1}): upper limit of "
                                    f"the screen's k (every component Type A from one bench condition)"),
    }

    chk = exhaustive_when_h_below_half_delta(delta)
    out["classification_check"] = {
        "unresolved_count_h_below_half_delta": _num(chk["unresolved_count_h_below"], "-",
                                                    "exhaustive_when_h_below_half_delta(T-DELTA)"),
        "unresolved_count_h_above_half_delta": _num(chk["unresolved_count_h_above"], "-",
                                                    "exhaustive_when_h_below_half_delta(T-DELTA)"),
    }

    e = c.E_CHARGE
    masses = {"N2+": c.M_SPECIES["N2"], "O2+": c.M_SPECIES["O2"], "N+": c.M_SPECIES["N2"] / 2.0,
              "O+": c.M_SPECIES["O"], "Xe+": c.M_SPECIES["Xe"]}
    species = grid(draft, "species")
    missing = [s for s in species if s not in masses]
    if missing:
        raise KeyError(f"no mass for species {missing}")
    out["y_max_per_sqrtV"] = {
        s: _num(_r(y_max(masses[s], 1.0, 1, e) * 1e3), "mN A^-1 V^-1/2",
                f"y_max(m_{s}, V_d = 1 V, Z = 1) * 1e3; multiply by sqrt(V_d/V) (ion mass ~ neutral mass from "
                f"abep_sim/constants.py; electron mass neglected, < 1e-4 relative)")
        for s in species
    }

    T_wall = grid(draft, "gauge_wall_temperature_K")
    if len(T_wall) != 1:
        raise ValueError("exactly one gauge-wall temperature expected")
    T_K = T_wall[0]
    S: dict = {}
    for gas in ("N2", "O2"):
        S[gas] = {}
        for p_torr in grid(draft, "background_pressure_torr"):
            s_m3 = pumping_speed_required(1e-6, c.M_SPECIES[gas], T_K, p_torr * TORR_TO_PA, c.K_B)
            S[gas][f"{p_torr:.1e} Torr"] = _num(_r(s_m3 * 1e3), "L s^-1 per (mg s^-1)",
                                                f"pumping_speed_required(1 mg/s {gas}, T = {T_K} K, p_b = {p_torr} "
                                                f"Torr) * 1e3; gas-specific gauge reading; cathode flow adds load")
    out["S_eff_required_per_mgps"] = S
    out["run_counts"] = run_counts(draft, n_min, int(threshold(draft, "T-KNEE-LEVELS")), K,
                                   int(threshold(draft, "T-S1-READINGS-PER-CYCLE")))
    return out


# ----------------------------------------------------------------------------------------------------------------
# design bookkeeping: conditions, visits and readings
# ----------------------------------------------------------------------------------------------------------------
def readings_per_visit(levels: list[str], has_source: bool, rule: dict) -> int:
    """Readings taken in one visit of an operating point. Source configurations bracket every visit that contains
    at least one source-on level with an 'off' reading before and after (run_matrix.reading_rule); the bracketing
    'off' reading doubles as the installed-off condition when that condition is in the visit."""
    if rule.get("bracket_with_off") is not True or rule.get("hall_only_readings_per_condition") != 1:
        raise ValueError("run_matrix.reading_rule must declare bracket_with_off = true and "
                         "hall_only_readings_per_condition = 1")
    on = [lv for lv in levels if lv != "off"]
    if not has_source or not on:
        return len(levels)
    return len(on) + 2          # off, on-levels..., off (the leading off is the installed-off condition if present)


def _visits(rows: list[dict]) -> dict:
    v: dict = {}
    for r in rows:
        v.setdefault((r["hw"], r["stage"], r["op"]), []).append(r["source"])
    return v


def run_counts(draft: dict, n_blocks: int, knee_levels: int, K: int, r_cycle: int) -> dict:
    """Condition and reading counts implied by the run matrix (design bookkeeping, not physics)."""
    rm = draft["run_matrix"]
    rows = rm["conditions"]
    rule = rm["reading_rule"]
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate run-matrix ids")
    src_hw = {a["hardware_configuration"] for a in draft["architectures"] if a["pre_ionizer"] != "none"}
    source_arms = [a["id"] for a in draft["architectures"] if a["pre_ionizer"] != "none"]

    def readings(sel: list[dict]) -> int:
        return sum(readings_per_visit(levels, hw in src_hw, rule) for (hw, _, _), levels in _visits(sel).items())

    by_hw: dict = {}
    for r in rows:
        by_hw.setdefault(r["hw"], []).append(r)
    subset_rows = [r for r in rows if r["arm"] in source_arms and r.get("confirmation_subset")]
    hall_only_min = [r for r in rows if r["arm"] == "hall_only" and r["stage"] in ("S2", "S6")]
    bench = rm["bench_conditions"]["per_arm"]
    bench_visits: dict = {}
    for op, lv in bench:
        bench_visits.setdefault(op, []).append(lv)
    bench_readings_per_arm = sum(readings_per_visit(lv, True, rule) for lv in bench_visits.values())

    src = "run_counts(run_matrix, reading_rule, n = T-N-MIN)"
    out = {
        "hall_on_conditions_per_block": _num(len(rows), "conditions per block", src),
        "hall_on_conditions_by_configuration": {hw: _num(len(v), "conditions per block", src)
                                                for hw, v in sorted(by_hw.items())},
        "hall_on_readings_per_block": _num(readings(rows), "readings per block (incl. bracketing off readings)", src),
        "hall_on_readings_by_configuration": {hw: _num(readings(v), "readings per block", src)
                                              for hw, v in sorted(by_hw.items())},
        "confirmation_subset_conditions_by_arm": {
            a: _num(sum(1 for r in subset_rows if r["arm"] == a), "conditions per block", src) for a in sorted(source_arms)},
        "hall_on_readings_full_at_n_min": _num(readings(rows) * n_blocks, "readings", src),
        "hall_on_readings_if_every_source_arm_stops_at_subset_at_n_min":
            _num((readings(hall_only_min) + readings(subset_rows)) * n_blocks, "readings",
                 src + "; hall_only S2 + S6 rows (no S5 when no source arm continues) + both subsets"),
        "bench_conditions_per_arm": _num(len(bench), "conditions per block", src),
        "bench_readings_at_n_min": _num(bench_readings_per_arm * len(source_arms) * n_blocks, "readings",
                                        src + " (bench visits bracketed by source-off readings like Hall-on visits)"),
        "knee_scan_readings": _num(2 * knee_levels, "readings (descending + ascending, one pass each)",
                                   "2 * T-KNEE-LEVELS"),
        "s1b_remount_series_readings": _num(K * r_cycle, "readings (non-score-bearing)",
                                            "T-S1-REMOUNT-CYCLES * T-S1-READINGS-PER-CYCLE"),
    }
    return out


# ----------------------------------------------------------------------------------------------------------------
# comparison, writing, markdown
# ----------------------------------------------------------------------------------------------------------------
def _strip(obj):
    """Numbers only, for comparison."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in ("source", "note", "unit", "evidence_class")}
    return obj


def compare(a, b, path="derived_numbers", rel=1e-6) -> list[str]:
    errs: list[str] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                errs.append(f"{path}.{k}: present in only one of computed/stored")
            else:
                errs += compare(a[k], b[k], f"{path}.{k}", rel)
    elif isinstance(a, bool) or isinstance(b, bool):
        if a != b:
            errs.append(f"{path}: {a} != {b}")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if not math.isclose(a, b, rel_tol=rel, abs_tol=0.0 if a else 1e-15):
            errs.append(f"{path}: computed {a} != stored {b}")
    elif a != b:
        errs.append(f"{path}: computed {a!r} != stored {b!r}")
    return errs


def _dump(obj, depth: int, key: str | None) -> str:
    """Stable, review-friendly layout: containers at depth <= 1 and derived_numbers expanded; at depth 2 lists of
    containers and dicts holding dicts expanded; everything deeper on one line."""
    pad = " " * depth
    compact = json.dumps(obj, ensure_ascii=False)
    if not isinstance(obj, (dict, list)) or not obj:
        return compact
    expand = depth <= 1 or key == "derived_numbers"
    if depth == 2 and not expand:
        if isinstance(obj, list):
            expand = any(isinstance(x, (dict, list)) for x in obj)
        else:
            expand = any(isinstance(x, dict) for x in obj.values())
    if not expand:
        return compact
    inner = " " * (depth + 1)
    if key == "derived_numbers":
        body = json.dumps(obj, indent=1, ensure_ascii=False).splitlines()
        return "\n".join(body[:1] + [pad + ln for ln in body[1:]])
    if isinstance(obj, list):
        items = [inner + _dump(x, depth + 1, None) for x in obj]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    items = [inner + json.dumps(k, ensure_ascii=False) + ": " + _dump(v, depth + 1, k) for k, v in obj.items()]
    return "{\n" + ",\n".join(items) + "\n" + pad + "}"


def dumps_draft(draft: dict) -> str:
    return _dump(draft, 0, None) + "\n"


def markdown_table(d: dict) -> str:
    rows = [("family sizes m (primary / iso-power / facility)",
             " / ".join(str(d["m_family"][f]["value"]) for f in FAMILIES))]
    for n, p in d["plan_by_n"].items():
        rows.append((f"n = {n}: nu_eff, k_primary, sigma_max(ln R)",
                     f'{p["nu_eff"]["value"]:.1f}, {p["k_primary"]["value"]:.4f}, {p["sigma_lnR_max"]["value"]:.5f}'))
        rows.append((f"n = {n}: u_T max, u_P max, u_inst max",
                     f'{100 * p["u_T_max"]["value"]:.2f} %, {100 * p["u_P_max"]["value"]:.2f} %, '
                     f'{100 * p["u_inst_max"]["value"]:.2f} %'))
    return "\n".join(f"| {a} | {b} |" for a, b in rows)


def main(argv: list[str]) -> int:
    draft = load_draft()
    d = derive(draft)
    if "--check" in argv:
        stored = draft.get("derived_numbers")
        if stored is None:
            print("experiment_draft.json has no derived_numbers block", file=sys.stderr)
            return 1
        errs = compare(_strip(d), _strip(stored))
        if errs:
            print("\n".join(errs), file=sys.stderr)
            return 1
        print("OK: derived_numbers reproduce")
        return 0
    if "--write" in argv:
        draft["derived_numbers"] = d
        DRAFT_JSON.write_text(dumps_draft(draft), encoding="utf-8")
        print(f"wrote derived_numbers to {DRAFT_JSON}")
        return 0
    if "--markdown" in argv:
        print(markdown_table(d))
        return 0
    print(json.dumps(d, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

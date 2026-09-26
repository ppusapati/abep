"""Deterministic derivations for the minimum decisive experiment (lane 25, MINEXP). DRAFT_PENDING_OWNER.

Every number in ``experiment_draft.json["derived_numbers"]`` is produced here from
(a) the PROPOSED thresholds in ``experiment_draft.json["thresholds"]`` (owner decisions, not physics),
(b) the run matrix in ``experiment_draft.json["run_matrix"]`` (to count the comparison families),
(c) the planning grids in ``experiment_draft.json["planning_grids"]`` (hypothetical scenarios, labelled as such), and
(d) physical constants read from ``abep_sim/constants.py`` (loaded by file path, so the package ``__init__`` and the
    simulator are never imported or modified).

Nothing here is a performance prediction. No Hall transport closure, screening candidate or literature Hall
number enters. Missing inputs raise (no defaults, no silent fallbacks).

Usage (from the repository root):
    python docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py            # print derived block
    python docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py --check    # compare with JSON
    python docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py --markdown # key-number table
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

HERE = Path(__file__).resolve().parent
DRAFT_JSON = HERE / "experiment_draft.json"
REPO_ROOT = HERE.parents[2]
CONSTANTS_PY = REPO_ROOT / "abep_sim" / "constants.py"

TORR_TO_PA = 101325.0 / 760.0          # exact by definition of the torr
SIG = 8                                # significant digits stored in the JSON
SCRIPT_REF = "docs/architecture_comparison/minimum_decisive_experiment/minexp_numbers.py"

# ----------------------------------------------------------------------------------------------------------------
# inputs
# ----------------------------------------------------------------------------------------------------------------
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


def threshold(draft: dict, tid: str) -> float:
    """Numeric value of a PROPOSED threshold; raises if absent, non-numeric or not PROPOSED."""
    for t in draft["thresholds"]:
        if t["id"] == tid:
            if t.get("status") != "PROPOSED":
                raise ValueError(f"threshold {tid} is not PROPOSED")
            v = t.get("value")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"threshold {tid} has no numeric value")
            return v
    raise KeyError(f"threshold {tid} missing from experiment_draft.json")


def grid(draft: dict, key: str) -> list:
    g = draft["planning_grids"][key]
    vals = g["values"]
    if not vals:
        raise ValueError(f"planning grid {key} is empty")
    return vals


# ----------------------------------------------------------------------------------------------------------------
# counting the comparison families from the run matrix
# ----------------------------------------------------------------------------------------------------------------
def family_sizes(draft: dict) -> tuple[int, int]:
    """(primary, iso-power) comparison counts: run-matrix rows whose 'families' list contains the family."""
    rows = draft["run_matrix"]["conditions"]
    primary = sum(1 for r in rows if "primary" in r["families"])
    iso = sum(1 for r in rows if "iso_power" in r["families"])
    if primary == 0 or iso == 0:
        raise ValueError("run matrix defines no primary or no iso-power comparisons")
    return primary, iso


# ----------------------------------------------------------------------------------------------------------------
# statistics
# ----------------------------------------------------------------------------------------------------------------
def z_two_sided_bonferroni(alpha_fw: float, m: int) -> float:
    """Critical value for m simultaneous two-sided intervals at family-wise level alpha_fw (Bonferroni)."""
    if not (0.0 < alpha_fw < 1.0) or m < 1:
        raise ValueError("need 0 < alpha < 1 and m >= 1")
    return NormalDist().inv_cdf(1.0 - alpha_fw / (2.0 * m))


def z_one_sided(alpha: float) -> float:
    if not (0.0 < alpha < 1.0):
        raise ValueError("need 0 < alpha < 1")
    return NormalDist().inv_cdf(1.0 - alpha)


def sigma_lnR_max(delta: float, z: float) -> float:
    """Largest standard uncertainty of ln R for which every outcome is classifiable (half-width h = z*sigma < delta/2)."""
    return delta / (2.0 * z)


def classify(lnR_hat: float, h: float, delta: float) -> str:
    """Mutually exclusive classes for a confidence interval [lnR_hat - h, lnR_hat + h] against the band (-delta, delta).

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


def exhaustive_when_h_below_half_delta(delta: float, n_grid: int = 4001) -> dict:
    """Numerical check of the claim: h < delta/2 => UNRESOLVED impossible; h >= delta/2 => UNRESOLVED possible."""
    xs = [(-3.0 + 6.0 * i / (n_grid - 1)) * delta for i in range(n_grid)]
    h_ok = 0.999 * delta / 2.0          # just below delta/2: no gap between the classes
    h_bad = 0.75 * delta                # well above delta/2: a gap delta - h <= |x| <= h opens
    unresolved_ok = sum(classify(x, h_ok, delta) == "UNRESOLVED" for x in xs)
    unresolved_bad = sum(classify(x, h_bad, delta) == "UNRESOLVED" for x in xs)
    return {"unresolved_count_h_below": unresolved_ok, "unresolved_count_h_above": unresolved_bad}


def sigma_lnR(u_T: float, u_P: float, n: int, f_src: float, u_src_scale: float,
              w_common: float, u_common_scale: float, u_remount: float) -> float:
    """Standard uncertainty of ln R_arch = ln[(T/P_bus)_X,on / (T/P_bus)_hall_only] (first order).

    u_T, u_P        relative random uncertainty of one thrust / one bus-power reading (after zero-drift handling)
    n               blocks (independent repeats) per condition; ln T and ln P of both conditions enter -> 2/n
    f_src           P_src,bus / P_bus,X,on  (source share of the arm's bus power)
    u_src_scale     combined relative scale uncertainty of the source power (meter scale and, when the DC input is
                    not measured directly, the generator efficiency from the ledger); does not cancel
    w_common        |P_c,X/P_bus,X - P_c,0/P_bus,0| for the dominant common consumer (partial cancellation weight)
    u_common_scale  its relative scale uncertainty (meter scale, ledger efficiency, or unmeasured ledger load)
    u_remount       re-mount / between-session reproducibility of ln(T/P_bus) (from the HW-0 start/end repeat)
    """
    for name, v in (("u_T", u_T), ("u_P", u_P), ("f_src", f_src), ("u_src_scale", u_src_scale),
                    ("w_common", w_common), ("u_common_scale", u_common_scale), ("u_remount", u_remount)):
        if v is None or v < 0:
            raise ValueError(f"{name} must be given and >= 0")
    if n < 1:
        raise ValueError("n must be >= 1")
    var = 2.0 * u_T ** 2 / n + 2.0 * u_P ** 2 / n + (f_src * u_src_scale) ** 2 \
        + (w_common * u_common_scale) ** 2 + u_remount ** 2
    return math.sqrt(var)


def n_required(u_reading: float, sigma_max: float, var_nonaveraging: float) -> float:
    """Blocks n needed so that 2(u_T^2 + u_P^2)/n + var_nonaveraging <= sigma_max^2 with u_T = u_P = u_reading.
    Returns math.inf when the non-averaging terms alone exhaust the budget."""
    room = sigma_max ** 2 - var_nonaveraging
    if room <= 0:
        return math.inf
    return 4.0 * u_reading ** 2 / room


def even_ceiling(x: float) -> int:
    if math.isinf(x):
        raise OverflowError("infeasible")
    k = math.ceil(x - 1e-12)
    return k + (k % 2)


def delta_floor(z: float, s_nonaveraging: float) -> float:
    """Smallest decision margin resolvable with infinitely many blocks: 2 z s (s = non-averaging standard uncertainty)."""
    return 2.0 * z * s_nonaveraging


# ----------------------------------------------------------------------------------------------------------------
# break-even algebra (identities; no physical values)
# ----------------------------------------------------------------------------------------------------------------
def ratio_R(T0: float, P0: float, dT: float, dP_d_load: float, eta_d: float, P_src_bus: float,
            dP_other_bus: float) -> float:
    """R = (T1/P1)/(T0/P0) with P1 = P0 + dP_d_load/eta_d + P_src_bus + dP_other_bus (bus_power_boundary_v1 sums)."""
    if eta_d is None or not (0.0 < eta_d <= 1.0):
        raise ValueError("eta_d (discharge converter efficiency from the ledger) must be given, 0 < eta_d <= 1")
    P1 = P0 + dP_d_load / eta_d + P_src_bus + dP_other_bus
    return ((T0 + dT) / P1) / (T0 / P0)


def breakeven_cost(y: float, P0_over_T0: float, kappa: float, V_d: float, eta_d: float,
                   dP_other_over_Idel: float) -> float:
    """C* [W/A = V, i.e. eV per delivered ion]: R > 1  <=>  C_del = P_src_bus / I_del < C*.

    y      = dT / I_del        thrust gained per ampere of delivered ions
    kappa  = dI_d / I_del      discharge-current response per ampere of delivered ions (fixed V_d)
    """
    if eta_d is None or not (0.0 < eta_d <= 1.0):
        raise ValueError("eta_d must be given, 0 < eta_d <= 1")
    return y * P0_over_T0 - kappa * V_d / eta_d - dP_other_over_Idel


def y_max(mass_kg: float, V_d: float, charge_state: int, e: float) -> float:
    """Ion-momentum ceiling on thrust per delivered ampere: ions of charge Z e fully accelerated through V_d, no
    divergence: T/I = m v/(Z e) = sqrt(2 m V_d/(Z e)). Seeding of Hall ionization or better Hall-on transport can
    exceed it, so it is a screen, never a stop rule."""
    return math.sqrt(2.0 * mass_kg * V_d / (charge_state * e))


def pumping_speed_required(mdot_kgps: float, mass_kg: float, T_K: float, p_b_Pa: float, k_B: float) -> float:
    """Effective pumping speed S = Q/p_b [m^3/s], Q = (mdot/m) k_B T (throughput at the gauge-wall temperature)."""
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
    groups = int(threshold(draft, "T-VAR-GROUPS"))

    m_primary, m_iso = family_sizes(draft)
    z_p = z_two_sided_bonferroni(alpha_fw, m_primary)
    z_i = z_two_sided_bonferroni(alpha_fw, m_iso)
    z_s = z_one_sided(alpha_screen)
    s_max = sigma_lnR_max(delta, z_p)
    s_max_iso = sigma_lnR_max(delta, z_i)
    s_grp = s_max / math.sqrt(groups)

    out: dict = {
        "generated_by": SCRIPT_REF,
        "inputs": {"thresholds": ["T-DELTA", "T-ALPHA-FW", "T-ALPHA-SCREEN", "T-N-MIN", "T-N-MAX", "T-VAR-GROUPS"],
                   "run_matrix_families": ["primary", "iso_power"],
                   "planning_grids": ["f_src", "u_reading", "s_nonaveraging", "delta_alternatives",
                                      "background_pressure_torr", "gauge_wall_temperature_K", "species"],
                   "constants": "abep_sim/constants.py (E_CHARGE, AMU, K_B, M_SPECIES)"},
        "m_family_primary": _num(m_primary, "-", "family_sizes(run_matrix) rows with family == 'primary'"),
        "m_family_iso": _num(m_iso, "-", "family_sizes(run_matrix) rows with family == 'iso_power'"),
        "z_fw_primary": _num(_r(z_p), "-", "z_two_sided_bonferroni(T-ALPHA-FW, m_family_primary)"),
        "z_fw_iso": _num(_r(z_i), "-", "z_two_sided_bonferroni(T-ALPHA-FW, m_family_iso)"),
        "z_screen_one_sided": _num(_r(z_s), "-", "z_one_sided(T-ALPHA-SCREEN)"),
        "sigma_lnR_max": _num(_r(s_max), "ln-ratio", "sigma_lnR_max(T-DELTA, z_fw_primary) = delta/(2 z)"),
        "sigma_lnR_max_iso": _num(_r(s_max_iso), "ln-ratio", "sigma_lnR_max(T-DELTA, z_fw_iso)"),
        "sigma_group_max": _num(_r(s_grp), "ln-ratio", "sigma_lnR_max / sqrt(T-VAR-GROUPS) (equal variance shares)"),
        "u_remount_max": _num(_r(s_grp), "ln-ratio",
                              "one equal share: re-mount reproducibility of ln(T/P_bus) (does not average down)"),
        "h_max_decisive_over_delta": _num(0.5, "-", "exhaustive_when_h_below_half_delta (proof in the draft, "
                                          "numerical check below)"),
    }

    chk = exhaustive_when_h_below_half_delta(delta)
    out["classification_check"] = {
        "unresolved_count_h_below_half_delta": _num(chk["unresolved_count_h_below"], "-",
                                                    "exhaustive_when_h_below_half_delta(T-DELTA)"),
        "unresolved_count_h_above_half_delta": _num(chk["unresolved_count_h_above"], "-",
                                                    "exhaustive_when_h_below_half_delta(T-DELTA)"),
    }

    out["u_reading_max_by_n"] = {
        str(n): _num(_r(s_grp * math.sqrt(n / 2.0)), "relative (1 sigma, per reading)",
                     f"sigma_group_max * sqrt(n/2), n = {n} blocks; applies to u_T and to u_P separately")
        for n in sorted({n_min, 6, n_max})
    }

    out["u_source_scale_max_by_f_src"] = {
        str(f): _num(_r(s_grp / f), "relative (1 sigma)",
                     f"sigma_group_max / f_src, f_src = {f} (planning grid, hypothetical)")
        for f in grid(draft, "f_src")
    }

    out["delta_floor_by_s_nonaveraging"] = {
        str(s): _num(_r(delta_floor(z_p, s)), "ln-ratio",
                     f"delta_floor(z_fw_primary, s = {s}) = 2 z s (planning grid, hypothetical)")
        for s in grid(draft, "s_nonaveraging")
    }

    nreq: dict = {}
    for d_alt in grid(draft, "delta_alternatives"):
        smax_alt = sigma_lnR_max(d_alt, z_p)
        grp_alt = smax_alt / math.sqrt(groups)
        var_nonavg = 3.0 * grp_alt ** 2          # source scale, common scale, re-mount each at their allocated share
        row = {}
        for u in grid(draft, "u_reading"):
            raw = n_required(u, smax_alt, var_nonavg)
            n_even = max(n_min, even_ceiling(raw))
            row[f"u={u}"] = _num(n_even, "blocks",
                                 f"max(T-N-MIN, even_ceiling(n_required(u={u}, sigma_lnR_max(delta={d_alt}), "
                                 f"3 shares non-averaging)))")
            row[f"u={u}"]["raw_n"] = _r(raw)
            row[f"u={u}"]["within_T_N_MAX"] = n_even <= n_max
        nreq[f"delta={d_alt}"] = row
    out["n_required"] = nreq

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
    out["run_counts"] = run_counts(draft, n_min, int(threshold(draft, "T-KNEE-LEVELS")))
    return out


def run_counts(draft: dict, n_blocks: int, knee_levels: int) -> dict:
    """Condition and reading counts implied by the run matrix (design bookkeeping, not physics)."""
    rows = draft["run_matrix"]["conditions"]
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate run-matrix ids")
    by_hw: dict = {}
    for r in rows:
        by_hw[r["hw"]] = by_hw.get(r["hw"], 0) + 1
    source_arms = [a["id"] for a in draft["architectures"] if a["pre_ionizer"] != "none"]
    subset = {a: sum(1 for r in rows if r["arm"] == a and r.get("confirmation_subset")) for a in source_arms}
    base = by_hw["HW-0"]
    bench = len(draft["run_matrix"]["bench_conditions"]["per_arm"]) * len(source_arms)
    src = "run_counts(run_matrix, n = T-N-MIN, T-KNEE-LEVELS)"
    out = {
        "hall_on_conditions_total": _num(len(rows), "conditions per block", src),
        "hall_on_conditions_by_configuration": {hw: _num(k, "conditions per block", src) for hw, k in sorted(by_hw.items())},
        "confirmation_subset_by_arm": {a: _num(k, "conditions per block", src) for a, k in sorted(subset.items())},
        "hall_on_readings_full_at_n_min": _num(len(rows) * n_blocks, "readings", src),
        "hall_on_readings_if_every_source_arm_stops_at_subset_at_n_min":
            _num((base + sum(subset.values())) * n_blocks, "readings", src),
        "bench_readings_at_n_min": _num(bench * n_blocks, "readings", src),
        "knee_scan_readings": _num(2 * knee_levels, "readings (descending + ascending, one pass each)", src),
    }
    return out


def _strip(obj):
    """Numbers only, for comparison."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in ("source", "note", "unit", "evidence_class")}
    return obj


def compare(a, b, path="derived_numbers", rel=1e-5) -> list[str]:
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


def markdown_table(d: dict) -> str:
    rows = [
        ("primary family size m", d["m_family_primary"]["value"]),
        ("z (two-sided, Bonferroni, primary)", f'{d["z_fw_primary"]["value"]:.4f}'),
        ("sigma_max(ln R) = delta/(2z)", f'{d["sigma_lnR_max"]["value"]:.5f}'),
        ("per-group share sigma_max/sqrt(5)", f'{d["sigma_group_max"]["value"]:.5f}'),
    ]
    for n, v in d["u_reading_max_by_n"].items():
        rows.append((f"u_T, u_P max per reading, n = {n}", f'{100 * v["value"]:.2f} %'))
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
    if "--markdown" in argv:
        print(markdown_table(d))
        return 0
    print(json.dumps(d, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

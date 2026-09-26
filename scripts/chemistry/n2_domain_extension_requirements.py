"""N2 high-T_e domain-extension evidence audit: energy-coverage requirements and independent-source comparisons.

STATUS: DRAFT_PENDING_OWNER. Non-gating. This script never scores, re-scores or re-labels a P5-N2 v1 run, and it changes no
limit, table, criterion or tolerance. The P5-N2 v1 vacuum outcome (all nine SGB screening candidates INCONCLUSIVE / NOT
ELIGIBLE, credible set empty) is permanent. Official run statuses are READ from the frozen scores file.

What it computes (all written to docs/chemistry/n2_domain_extension/domain_extension_requirements.json):
  1. v1 inventory (frozen records): which rate tables are beyond their validity limit (f_out > 1e-12) in which runs, the
     highest active mean energy (max_mean_energy_active_eV) per table, and the time-averaged Te_max_eV.
  2. Hypothetical domain coverage (COUNTING ONLY, NOT SCORING) for candidate extended limits L = 60, 75, 90, 120, 150 eV mean
     energy. Proxy: a run counts as covered at L if every table capped at 45 eV either had f_out <= 1e-12 in v1 (f_out can
     only fall when a limit rises) or has max_mean_energy_active_eV <= L. The proxy is NOT the scoring predicate (f_out is a
     reaction-weighted activity share over saved frames; those frames are not in the frozen record), so an exact count
     needs reruns. The v1 statuses are unaffected either way.
  3. Energy-coverage requirements. Rate convention (verified): HallThruster.jl v0.23.1 evaluates rate_coeff(coll, 3/2 Tev)
     (src/collisions/collision_frequencies.jl) on a 0-255 eV mean-energy grid (reactions.jl load_rate_coeff_file); the
     tables are Maxwellian rates k(T_e) = sqrt(8/(pi m_e)) (e T_e)^-3/2 int sigma(E) E exp(-E/T_e) dE indexed by mean energy
     eps = 3/2 T_e (abep_sim/rate_tables.py; Laporta fits evaluated at T_e = 2/3 eps, scripts/build_n2_vibrational_tables.py).
     For each table and L it reports (a) the share of the declared-model rate resting above the source's last data point,
     and (b) the cross-section upper energy E_req a source would have to cover so that the Maxwellian-rate share from energies
     above E_req is < 1e-2 (the rate_validity.toml convention), < 1e-6 and < 1e-12. E_req uses a HOLD envelope above the last
     data point (sigma(E > E_last) = sigma(E_last): conservative for a cross section that falls above E_last) and, as a common
     table-independent reference, a flat cross section ((1 + x) exp(-x) = threshold, x = E_req / T_e).
  4. Independent published comparisons (evidence classes in the audit JSON):
     * dissociation: Song et al. JPCRD 52, 023104 (2023) Fig. 19 (NSF PAR public-access copy, sha256 f35b73d1...), vector
       paths extracted by extract_fig19() into sources/song2023_fig19_vector_extract.csv: Majeed & Strickland 1997 curve,
       Kawaguchi, Takahashi & Satoh 2021 curve (both to ~1 keV), Winters 1966 neutral-dissociation points (to ~300 eV); the
       Cosby diamonds are used only as the calibration check against Table 9.
     * electronic excitation: Majeed & Strickland JPCRD 26, 335 (1997) recommended values as tabulated in the QST open-data
       files of Tabata et al. ADNDT 92, 375 (2006) (secondary reproduction), and the Tabata analytic fits themselves.
     * vibrational v = 0 -> 1: Tabata et al. 2006 fit n2-5 (to Itikawa et al. JPCRD 15, 985 (1986) recommended data,
       1.05-48.5 eV, which includes the non-resonant 10-50 eV region) against the Laporta resonant-only fit.
  5. The DRAFT verdict criteria C1-C3 (RULE below) evaluated per table and candidate limit, the resulting draft proposals
     (largest candidate limit passing the measured reading) with their hypothetical coverage, and single-channel rate
     indicators for the extended-domain completeness re-audit (not verdicts).
Usage:
  python scripts/chemistry/n2_domain_extension_requirements.py            # recompute and write the JSON
  python scripts/chemistry/n2_domain_extension_requirements.py --check    # recompute and compare with the committed JSON
  python scripts/chemistry/n2_domain_extension_requirements.py --extract-fig19 <song2023 NSF PAR pdf>   # rebuild the CSV
"""
import argparse, csv, gzip, hashlib, importlib.util, json, math, os, sys, tomllib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
BR = os.path.join(ROOT, "hallthruster_bridge")
RAW = os.path.join(BR, "validation", "p5_n2_campaign_v1_vacuum_raw.jsonl.gz")
SCORES = os.path.join(BR, "validation", "p5_n2_campaign_v1_vacuum_scores.json")
VALIDITY = os.path.join(BR, "propellants", "rate_validity.toml")
OUTDIR = os.path.join(ROOT, "docs", "chemistry", "n2_domain_extension")
OUT = os.path.join(OUTDIR, "domain_extension_requirements.json")
FIG19_CSV = os.path.join(OUTDIR, "sources", "song2023_fig19_vector_extract.csv")
SONG_PDF_SHA256 = "f35b73d1f5f11291e6d844cdd8e324f99b6f5b17a9661d2568fca59e9604875d"

FOUT_TOL = 1e-12                      # v1 numerical tolerance on f_out (read, never changed)
V1_CAP = 45.0                         # v1 limit of the 21 capped tables (read from rate_validity.toml and asserted)
CANDIDATE_LIMITS = (60.0, 75.0, 90.0, 120.0, 150.0)
THRESHOLDS = (1e-2, 1e-6, 1e-12)
ME, QE = 9.10938e-31, 1.602176634e-19


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EXC = _load("n2dx_exc", os.path.join("scripts", "build_n2_electronic_excitation_tables.py"))
DIS = _load("n2dx_dis", os.path.join("scripts", "build_n2_dissociation_table.py"))
AUD = _load("n2dx_aud", os.path.join("scripts", "audit_n2_completeness_final.py"))
VIB = _load("n2dx_vib", os.path.join("scripts", "audit_n2_vibrational_excitation.py"))


def r6(x):
    """Round to 6 significant digits (JSON reproducibility)."""
    if x is None:
        return None
    if isinstance(x, (bool, int, str)):
        return x
    x = float(x)
    if not math.isfinite(x):
        return str(x)
    return float(f"{x:.6g}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------------------------ tables
ELEC_KEYS = {EXC.fname(k): k for k in EXC.STATES}           # excitation_N2_<state>.dat -> build-script key


def table_model(fname):
    """(family, E nodes [eV], sigma nodes [m^2] up to the source's last data point, E_last, declared-tail description,
    declared-model nodes or None). Nodes are piecewise-linear exactly as the build scripts integrate them."""
    if fname == "dissociation_N2.dat":
        E = np.array([e for e, _ in DIS.TABLE9], float); s = np.array([v for _, v in DIS.TABLE9], float) * 1e-20
        return "dissociation", E, s, float(E[-1]), "hold (sigma held at the 200 eV value)", None
    if fname in ELEC_KEYS:
        k = ELEC_KEYS[fname]
        E, s = EXC.cross_section(k, "none")
        Ed, sd = EXC.cross_section(k, "powerlaw")
        return ("electronic", np.asarray(E, float), np.asarray(s, float), float(E[-1]),
                f"power law p = {EXC.slope(k):.4f} from Johnson's last two points to 10 keV, zero beyond", (np.asarray(Ed), np.asarray(sd)))
    if fname.startswith("excitation_N2_rot_j0_to_j"):
        col = 1 if fname.endswith("j2.dat") else 2
        E = np.array([r[0] for r in AUD.TABLE6], float); s = np.array([r[col] for r in AUD.TABLE6], float) * 1e-20
        return "rotational", E, s, float(E[-1]), "hold (sigma held at the 10 eV value)", None
    if fname.startswith("excitation_N2_vib_0_to_"):
        return "vibrational", None, None, 15.0, "rate fit (Laporta Eq. 10); resonant cross sections integrated to 15 eV", None
    raise KeyError(fname)


def _seg_integral(E0, E1, s0, s1, T):
    """Exact int_{E0}^{E1} sigma(E) E exp(-E/T) dE for sigma linear between (E0, s0) and (E1, s1); E, T in eV."""
    if E1 <= E0:
        return 0.0
    b = (s1 - s0) / (E1 - E0); a = s0 - b * E0
    F1 = lambda e: -T * math.exp(-e / T) * (e + T)
    F2 = lambda e: -T * math.exp(-e / T) * (e * e + 2 * T * e + 2 * T * T)
    return a * (F1(E1) - F1(E0)) + b * (F2(E1) - F2(E0))


def pw_integral(E, s, T, e_from=0.0):
    """int_{e_from}^{E[-1]} of the piecewise-linear sigma(E) E exp(-E/T) dE (sigma = 0 below E[0])."""
    tot = 0.0
    for i in range(len(E) - 1):
        a, b = E[i], E[i + 1]
        if b <= e_from:
            continue
        if a < e_from:
            s_mid = s[i] + (s[i + 1] - s[i]) * (e_from - a) / (b - a)
            tot += _seg_integral(e_from, b, s_mid, s[i + 1], T)
        else:
            tot += _seg_integral(a, b, s[i], s[i + 1], T)
    return tot


def hold_tail(s_last, E_last, T):
    """int_{E_last}^inf s_last E exp(-E/T) dE."""
    x = E_last / T
    return s_last * T * T * (1 + x) * math.exp(-x)


def rate_from_integral(I_eV, T):
    """k [m^3/s] from int sigma E exp(-E/T) dE with sigma in m^2 and E, T in eV."""
    return math.sqrt(8.0 / (math.pi * ME)) * (QE * T) ** -1.5 * I_eV * QE * QE


def solve_x(y):
    """x > 0 with (1 + x) exp(-x) = y (0 < y < 1), by bisection on log."""
    lo, hi = 0.0, 400.0
    f = lambda x: math.log1p(x) - x - math.log(y)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def table_rate_file(fname, eps):
    a = np.loadtxt(os.path.join(BR, "propellants", fname), skiprows=2)
    return float(np.interp(eps, a[:, 0], a[:, 1]))


# ---------------------------------------------------------------------------------------------------------- v1 inventory
def load_v1():
    with gzip.open(RAW, "rt") as f:
        recs = [json.loads(l) for l in f]
    scores = json.load(open(SCORES))
    return recs, scores


def pct(vals, q):
    v = sorted(vals)
    if not v:
        return None
    return float(np.percentile(v, q))


def summary(vals):
    return {"n": len(vals), "min": r6(min(vals)), "p50": r6(pct(vals, 50)), "p90": r6(pct(vals, 90)), "max": r6(max(vals))} if vals else {"n": 0}


def v1_inventory(recs, scores, validity):
    status = {}
    for s in scores["runs"]:
        status.setdefault(s["key"], set()).add(s["status"])
    reading_independent = all(len(v) == 1 or "OUT_OF_DOMAIN" not in v for v in status.values())
    ood = {k for k, v in status.items() if "OUT_OF_DOMAIN" in v}
    by_key = {r["key"]: r for r in recs}
    pred = {r["key"] for r in recs if (r.get("chemistry_unresolved_rate_files") or [])
            or any(q["extrapolated_fraction"] is None or q["extrapolated_fraction"] > FOUT_TOL for q in r["chemistry_per_reaction"])}
    files = {}
    for r in recs:
        for q in r["chemistry_per_reaction"]:
            files.setdefault(q["file"], (q["max_mean_energy_eV"], q["basis"]))
    capped = sorted(f for f, (lim, _) in files.items() if lim is not None and lim < 255.0)
    tables = {}
    for f in capped:
        lim, basis = files[f]
        v = validity[f]
        assert v["status"] == "verified" and float(v["max_mean_energy_eV"]) == lim == V1_CAP and v["basis"] == basis, f
        beyond = [(r["key"], q) for r in recs for q in r["chemistry_per_reaction"]
                  if q["file"] == f and q["extrapolated_fraction"] > FOUT_TOL]
        active_above = [r["key"] for r in recs for q in r["chemistry_per_reaction"]
                        if q["file"] == f and q["max_mean_energy_active_eV"] > lim]
        tables[f] = {"family": table_model(f)[0], "limit_mean_energy_eV": lim, "basis": basis,
                     "n_runs_beyond_limit": len(beyond),
                     "n_ood_runs_beyond_limit": sum(1 for k, _ in beyond if k in ood),
                     "n_runs_active_above_limit_any_share": len(active_above),
                     "eps_active_eV_runs_beyond": summary([q["max_mean_energy_active_eV"] for _, q in beyond]),
                     "f_out_runs_beyond": summary([q["extrapolated_fraction"] for _, q in beyond])}
    beyond_255 = sorted({q["file"] for r in recs for q in r["chemistry_per_reaction"]
                         if q["max_mean_energy_eV"] >= 255.0 and q["extrapolated_fraction"] > FOUT_TOL})
    diss_only = sum(1 for k in ood if [q["file"] for q in by_key[k]["chemistry_per_reaction"]
                                         if q["extrapolated_fraction"] > FOUT_TOL] == ["dissociation_N2.dat"])
    te_ood = [by_key[k]["Te_max_eV"] for k in ood]
    te_in = [r["Te_max_eV"] for r in recs if r["key"] not in ood]
    return {
        "n_records": len(recs), "n_run_readings_scored": len(scores["runs"]),
        "official_status_counts_run_readings": scores["status_counts"]["vacuum"],
        "n_runs_out_of_domain": len(ood), "ood_status_reading_independent": reading_independent,
        "check_ood_equals_frozen_fout_predicate": {"equal": pred == ood, "n_disagreements": len(pred ^ ood),
                                                   "note": "consistency check of inputs only; statuses are the official ones"},
        "capped_tables": capped, "n_capped_tables": len(capped),
        "tables_with_255eV_limit_beyond": beyond_255,
        "n_ood_runs_dissociation_beyond": tables["dissociation_N2.dat"]["n_ood_runs_beyond_limit"],
        "n_ood_runs_dissociation_only_beyond": diss_only,
        "Te_max_eV_time_averaged": {"ood": summary(te_ood), "in_domain": summary(te_in),
                                    "note": "peak of the time-averaged T_e profile; every OOD run stays below T_e = 30 eV here, "
                                            "so every exceedance is in instantaneous saved frames"},
        "tables": tables,
    }, ood, by_key


def coverage_for_limits(recs, ood, capped, limits):
    """Proxy count (see hypothetical_coverage) for a per-table map of extended limits; unlisted capped tables keep 45 eV."""
    cov, newly = [], []
    for r in recs:
        ok = True
        for q in r["chemistry_per_reaction"]:
            if q["file"] not in capped or q["extrapolated_fraction"] <= FOUT_TOL:
                continue
            if q["file"] in limits and q["max_mean_energy_active_eV"] <= limits[q["file"]]:
                continue
            ok = False; break
        if ok:
            cov.append(r)
            if r["key"] in ood:
                newly.append(r)
    d = {"covered_runs": len(cov), "pct_of_1080": r6(100.0 * len(cov) / len(recs)),
         "newly_covered_ood_runs": len(newly), "pct_of_ood_runs": r6(100.0 * len(newly) / len(ood)),
         "remaining_ood_runs": len(ood) - len(newly)}
    return d, newly


def hypothetical_coverage(recs, ood, capped):
    fam = {f: table_model(f)[0] for f in capped}
    scen = {"all_capped_tables_at_L": set(capped)}
    for family in ("dissociation", "electronic", "rotational", "vibrational"):
        scen[f"all_capped_except_{family}_at_L"] = {f for f in capped if fam[f] != family}
    scen["dissociation_only_at_L"] = {"dissociation_N2.dat"}
    scen["dissociation_and_electronic_only_at_L"] = {f for f in capped if fam[f] in ("dissociation", "electronic")}
    out = {"definition": ("COUNTING, NOT SCORING. Run covered at L if every capped table either had f_out <= 1e-12 in v1 or, for "
                          "tables in the scenario's extended set, max_mean_energy_active_eV <= L; tables outside the set keep "
                          "45 eV. Proxy only: eps_active marks the highest mean energy carrying > 1e-12 of the table's PEAK "
                          "cell-frame activity, whereas f_out is the activity SHARE beyond the limit; the frozen record lacks "
                          "the frames, so exact f_out at a new limit requires reruns."),
           "proxy_caveat_n_in_domain_runs_with_eps_active_above_45": None, "limits": {}}
    n_in_dom_hi = 0
    for r in recs:
        if r["key"] not in ood and any(q["max_mean_energy_active_eV"] > V1_CAP for q in r["chemistry_per_reaction"] if q["file"] in capped):
            n_in_dom_hi += 1
    out["proxy_caveat_n_in_domain_runs_with_eps_active_above_45"] = n_in_dom_hi
    for L in CANDIDATE_LIMITS:
        row = {}
        for name, ext in scen.items():
            d, newly = coverage_for_limits(recs, ood, capped, {f: L for f in ext})
            if name == "all_capped_tables_at_L":          # no per-candidate breakdown: this is not an eligibility count
                for fld in ("chemistry", "point", "registration"):
                    tot = {}
                    for r in recs:
                        if r["key"] in ood:
                            tot.setdefault(r[fld], [0, 0])[0] += 1
                    for r in newly:
                        tot[r[fld]][1] += 1
                    d[f"newly_covered_ood_by_{fld}"] = {k: {"ood": v[0], "newly_covered": v[1]} for k, v in sorted(tot.items())}
            row[name] = d
        out["limits"][f"{L:g}"] = row
    return out


# ------------------------------------------------------------------------------------------------------------ requirements
def requirements(capped):
    flat = {f"{t:g}": r6(solve_x(t)) for t in THRESHOLDS}
    per = {}
    for f in capped:
        family, E, s, E_last, tail, decl = table_model(f)
        d = {"family": family, "source_last_data_point_eV": r6(E_last), "declared_model_above_last_point": tail, "by_limit": {}}
        if s is not None:
            # the hold envelope bounds the tail from above only if sigma is not rising at the source's last points
            d["hold_envelope_is_upper_bound"] = bool(s[-1] <= s[-2])
        for L in (V1_CAP,) + CANDIDATE_LIMITS:
            T = L / 1.5
            row = {"T_e_eV": r6(T), "flat_sigma_E_req_eV": {k: r6(v * T) for k, v in flat.items()}}
            if family == "vibrational":
                row["note"] = ("rate fit, no cross section in the repository; the resonant cross sections behind it were "
                               "integrated to 15 eV by Laporta (negligible beyond). The table-specific tail share is not "
                               "defined; the flat reference and the independent non-resonant comparison apply.")
                d["by_limit"][f"{L:g}"] = row
                continue
            I_low = pw_integral(E, s, T)
            I_hold = I_low + hold_tail(s[-1], E_last, T)
            row["share_above_last_point_hold"] = r6((I_hold - I_low) / I_hold)
            if decl is not None:
                I_decl = pw_integral(decl[0], decl[1], T)
                row["share_above_last_point_declared"] = r6((I_decl - I_low) / I_decl)
                row["declared_over_zero_tail_minus_1"] = r6(I_decl / I_low - 1)
                row["declared_over_hold_tail_minus_1"] = r6(I_decl / I_hold - 1)
                k_model = rate_from_integral(I_decl, T)
            else:
                row["hold_over_zero_tail_minus_1"] = r6(I_hold / I_low - 1)
                k_model = rate_from_integral(I_hold, T)
            row["model_rate_over_committed_table_minus_1"] = r6(k_model / table_rate_file(f, L) - 1)
            ereq = {}
            for t in THRESHOLDS:
                y = t * I_hold / (s[-1] * T * T) if s[-1] > 0 else float("inf")
                x_last = E_last / T
                if y >= (1 + x_last) * math.exp(-x_last):
                    ereq[f"{t:g}"] = r6(E_last)          # already satisfied at the last data point
                else:
                    ereq[f"{t:g}"] = r6(solve_x(y) * T)
            row["hold_envelope_E_req_eV"] = ereq
            if decl is not None:
                # declared continuation: smallest E_up with share above E_up < threshold (bisection on the node set)
                Ed, sd = decl; I_decl = pw_integral(Ed, sd, T); er = {}
                for t in THRESHOLDS:
                    lo, hi = E_last, float(Ed[-1])
                    if pw_integral(Ed, sd, T, E_last) / I_decl < t:
                        er[f"{t:g}"] = r6(E_last); continue
                    if pw_integral(Ed, sd, T, hi) / I_decl >= t:
                        er[f"{t:g}"] = "beyond 10 keV continuation end"; continue
                    for _ in range(80):
                        mid = math.sqrt(lo * hi)
                        if pw_integral(Ed, sd, T, mid) / I_decl >= t:
                            lo = mid
                        else:
                            hi = mid
                    er[f"{t:g}"] = r6(hi)
                row["declared_continuation_E_req_eV"] = er
            d["by_limit"][f"{L:g}"] = row
        per[f] = d
    return {"flat_sigma_x_equals_E_req_over_Te": flat, "per_table": per,
            "note": ("E_req = energy up to which a source must provide cross sections so that the part of the Maxwellian rate "
                     "from higher energies is below the threshold, at T_e = L/1.5. 1e-2 is the rate_validity.toml convention; "
                     "1e-6 and 1e-12 are the stricter levels requested for this audit (1e-12 mirrors the numerical f_out "
                     "tolerance, a different quantity).")}


# ------------------------------------------------------------------------------------------- independent-source data (transcribed)
# Majeed & Strickland, JPCRD 26, 335 (1997) recommended cross sections [cm^2] as tabulated (AUT "Majeed and Strickland") in the
# QST open-data files of Tabata et al. ADNDT 92, 375 (2006), https://www.qst.go.jp/site/jt60-english/6475.html, read 2026-09-26.
# SECONDARY reproduction; not checked against the MS1997 paper (abstract-only access). sha256 of the .dat files:
# n2-10 b7717745..., n2-11 4cd73de8..., n2-12 a4d07321..., n2-13 88e83605..., n2-14 140295f8..., n2-15 6048f73e...,
# n2-16 59a3ab3d..., n2-35 5dea2786... . n2-35 prints the last C value as "0.020-E17"; read here as 0.020E-17 (verify).
MS1997 = {
    "A": ([6.5, 7.0, 8.0, 9.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 24.0, 30.0, 40.0, 50.0, 70.0, 100.0, 150.0, 200.0],
          [0.100e-17, 0.400e-17, 0.700e-17, 1.00e-17, 1.23e-17, 1.65e-17, 2.00e-17, 2.13e-17, 2.10e-17, 1.90e-17, 1.40e-17,
           0.919e-17, 0.500e-17, 0.262e-17, 0.096e-17, 0.032e-17, 0.009e-17, 0.004e-17]),
    "B": ([7.6, 8.0, 9.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 24.0, 30.0, 40.0, 50.0, 70.0, 100.0, 150.0, 200.0],
          [0.053e-17, 0.377e-17, 1.33e-17, 2.19e-17, 2.93e-17, 2.70e-17, 2.16e-17, 1.84e-17, 1.60e-17, 1.31e-17, 0.973e-17,
           0.592e-17, 0.304e-17, 0.125e-17, 0.042e-17, 0.012e-17, 0.003e-17]),
    "W": ([8.0, 9.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 24.0, 30.0, 40.0, 50.0, 70.0, 100.0, 150.0, 200.0],
          [0.200e-17, 0.740e-17, 1.20e-17, 2.10e-17, 3.06e-17, 3.73e-17, 3.50e-17, 2.57e-17, 1.57e-17, 0.972e-17, 0.500e-17,
           0.262e-17, 0.096e-17, 0.032e-17, 0.010e-17, 0.004e-17]),
    "Bp": ([9.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 24.0, 30.0, 40.0, 50.0, 70.0, 100.0, 150.0, 200.0],
           [0.160e-17, 0.350e-17, 0.740e-17, 1.13e-17, 1.14e-17, 0.730e-17, 0.540e-17, 0.430e-17, 0.337e-17, 0.245e-17,
            0.190e-17, 0.114e-17, 0.053e-17, 0.015e-17, 0.004e-17]),
    "ap": ([11.0, 12.0, 14.0, 16.0, 20.0, 30.0, 50.0, 100.0, 200.0, 500.0, 1000.0],
           [0.48e-17, 0.652e-17, 0.950e-17, 0.850e-17, 0.480e-17, 0.230e-17, 0.193e-17, 0.096e-17, 0.045e-17, 0.016e-17, 0.008e-17]),
    "a": ([10.0, 12.0, 18.0, 30.0, 50.0, 100.0, 200.0, 500.0, 1000.0],
          [0.220e-17, 1.15e-17, 2.69e-17, 1.86e-17, 1.12e-17, 0.559e-17, 0.280e-17, 0.111e-17, 0.056e-17]),
    "w": ([9.0, 10.0, 12.0, 14.0, 16.0, 20.0, 30.0, 50.0, 100.0, 200.0],
          [0.018e-17, 0.362e-17, 0.981e-17, 1.15e-17, 0.806e-17, 0.430e-17, 0.231e-17, 0.071e-17, 0.013e-17, 0.001e-17]),
    "C": ([12.0, 13.0, 14.0, 16.0, 18.0, 20.0, 24.0, 30.0, 40.0, 50.0, 70.0, 100.0, 150.0, 200.0],
          [0.58e-17, 2.53e-17, 4.23e-17, 2.70e-17, 2.07e-17, 1.73e-17, 1.21e-17, 0.77e-17, 0.40e-17, 0.25e-17, 0.12e-17,
           0.069e-17, 0.031e-17, 0.020e-17]),
}
# Tabata et al. ADNDT 92, 375 (2006) analytic fits, QST open-data .f files (same page; sha256 n2-5.f 4c46e151..., n2-10.f b0068ff7...,
# n2-11.f 71db2218..., n2-12.f d8192c76..., n2-13.f 65c74504..., n2-14.f 7999201e..., n2-15.f 68b6bc6d..., n2-16.f 1297f5e9...,
# n2-35.f 440c6fd8..., n2-61.f 564b24ec...). E, EMIN, EMAX, ETH in keV, sigma in cm^2; ER = 1.361e-2 keV, sigma0 = 1e-16 cm^2.
# terms: list of ("F2", c1, c2, c3, c4) or ("F3", c1, c2, c3, c4, c5, c6) summed. Erratum to the ADNDT paper exists (not
# checked whether the online files include it: verify).
TABATA = {
    "n2-5 v0->1": (1.05e-3, 4.85e-2, 2.90e-4, [("F2", 1.83e10, 10.0, 9.41e-4, 0.42), ("F2", 1.24e9, 10.0, 2.087e-3, 7.98),
                                             ("F2", 1.37e-2, 9.2, 1.94e-2, 6.9)]),
    "n2-10 A": (6.50e-3, 2.00e-1, 6.17e-3, [("F2", 0.397, 0.933, 1.33e-2, 2.503)]),
    "n2-11 B": (7.60e-3, 2.00e-1, 7.35e-3, [("F3", 6.82, 1.774, 3.31e-3, 0.915, 1.30e-2, 3.65)]),
    "n2-12 W": (8.00e-3, 2.00e-1, 7.36e-3, [("F3", 0.914, 1.31, 9.90e-3, 2.23, 3.10e-2, 4.50)]),
    "n2-13 Bp": (9.00e-3, 2.00e-1, 8.16e-3, [("F2", 0.75, 1.97, 6.70e-3, 3.03), ("F2", 2.12e-2, 0.15, 5.78e-2, 3.39)]),
    "n2-14 ap": (1.10e-2, 1.00, 8.40e-3, [("F2", 0.609, 1.55, 6.23e-3, 2.63), ("F2", 8.26e-3, 2.10, 2.72e-2, 1.061)]),
    "n2-15 a": (1.00e-2, 1.00, 8.55e-3, [("F2", 2.56, 2.04, 6.69e-3, 0.93)]),
    "n2-16 w": (9.00e-3, 2.00e-1, 8.89e-3, [("F3", 1.22, 1.361, 3.77e-3, 1.43, 2.13e-2, 4.51)]),
    "n2-35 C": (1.13e-2, 2.00e-1, 1.10e-2, [("F2", 682.0, 4.75, 3.06e-3, 3.62), ("F2", 1.0, 1.212, 6.17e-3, 1.529)]),
    "n2-61 N+N": (1.20e-2, 2.00e-1, 9.76e-3, [("F3", 1.87, 3.03, 1.23e-2, 4.70e-2, 3.50e-2, 1.10)]),
}
TABATA_STATE = {"A": "n2-10 A", "B": "n2-11 B", "W": "n2-12 W", "Bp": "n2-13 Bp", "ap": "n2-14 ap", "a": "n2-15 a",
                "w": "n2-16 w", "C": "n2-35 C"}


def tabata_sigma_m2(name, E_eV):
    """Tabata fit [m^2]; 0 outside the fit range (as the published Fortran)."""
    emin, emax, eth, terms = TABATA[name]
    e = E_eV * 1e-3
    if e < emin or e > emax:
        return 0.0
    x = e - eth; er = 1.361e-2; tot = 0.0
    for t in terms:
        f1 = t[1] * (x / er) ** t[2]
        den = 1.0 + (x / t[3]) ** (t[2] + t[4])
        if t[0] == "F3":
            den += (x / t[5]) ** (t[2] + t[6])
        tot += f1 / den
    return 1e-16 * tot * 1e-4


def table_sigma(key, E):
    """Current nominal electronic table cross section [m^2] (Su < 20 eV, Johnson >= 20 eV, declared power law above)."""
    Ed, sd = EXC.cross_section(key, "powerlaw")
    return float(np.interp(E, Ed, sd, left=0.0, right=0.0))


def electronic_comparison():
    out = {}
    for key in EXC.STATES:
        Ej, Sj, Uj = EXC.johnson(key)
        rows = {}
        Ems, Sms = MS1997[key]
        for E in (20.0, 30.0, 50.0, 100.0, 150.0, 200.0, 500.0, 1000.0):
            st = table_sigma(key, E)
            if st <= 0:
                continue
            row = {"table_sigma_1e-18cm2": r6(st * 1e22)}
            if Ems[0] <= E <= Ems[-1]:
                row["MS1997_over_table"] = r6(float(np.interp(E, Ems, Sms)) * 1e-4 / st)
                row["MS1997_is_tabulated_point"] = E in Ems
            tn = TABATA_STATE[key]
            ts = tabata_sigma_m2(tn, E)
            if ts > 0:
                row["Tabata_fit_over_table"] = r6(ts / st)
            src = "Su 2021" if E < EXC.E_JOIN else ("Johnson 2005" if E <= Ej[-1] else "declared power-law continuation")
            row["table_basis_at_E"] = src
            if E in list(Ej):
                i = list(Ej).index(E)
                row["Johnson_rel_uncertainty"] = r6(Uj[i] / Sj[i])
            rows[f"{E:g}"] = row
        above = [v["MS1997_over_table"] for e, v in rows.items() if float(e) >= 100 and "MS1997_over_table" in v]
        out[EXC.fname(key)] = {"johnson_last_point_eV": r6(Ej[-1]), "continuation_p": r6(EXC.slope(key)),
                               "MS1997_range_eV": [r6(Ems[0]), r6(Ems[-1])],
                               "Tabata_fit_range_eV": [r6(TABATA[TABATA_STATE[key]][0] * 1e3), r6(TABATA[TABATA_STATE[key]][1] * 1e3)],
                               "points": rows,
                               "MS1997_over_table_E_ge_100": {"min": r6(min(above)), "max": r6(max(above))} if above else None,
                               "rate_impact_if_MS1997_above_last_point": ms_rate_impact(key)}
    return out


def ms_rate_impact(key):
    """Relative change of the table's Maxwellian rate if, above Johnson's last point, sigma followed MS1997 (log-log between
    its points, then the declared power law continued from MS1997's last point) instead of the declared continuation.
    'absolute': MS1997 values as tabulated (a step at the join); 'shape': MS1997 scaled to the table at the join."""
    E, s = EXC.cross_section(key, "none"); E = np.asarray(E, float); s = np.asarray(s, float)
    Ed, sd = EXC.cross_section(key, "powerlaw"); Ed = np.asarray(Ed); sd = np.asarray(sd)
    Ems = np.array(MS1997[key][0]); Sms = np.array(MS1997[key][1]) * 1e-4
    E_last = float(E[-1]); p = EXC.slope(key)
    Eg = np.geomspace(E_last, Ems[-1], 80)
    ms = np.exp(np.interp(np.log(Eg), np.log(Ems), np.log(Sms)))
    Ec = np.geomspace(Ems[-1], EXC.E_CONT_MAX, 120)[1:]
    out = {"share_beyond_MS1997_end": {}}
    for L in (V1_CAP,) + CANDIDATE_LIMITS:
        T = L / 1.5
        I_low = pw_integral(E, s, T); I_hold = I_low + hold_tail(s[-1], E_last, T)
        out["share_beyond_MS1997_end"][f"{L:g}"] = {
            "declared": r6(pw_integral(Ed, sd, T, float(Ems[-1])) / pw_integral(Ed, sd, T)),
            "hold_envelope": r6(hold_tail(s[-1], float(Ems[-1]), T) / I_hold)}
    for mode in ("absolute", "shape"):
        f = 1.0 if mode == "absolute" else s[-1] / ms[0]
        tail = np.concatenate([ms * f, ms[-1] * f * (Ec / Ems[-1]) ** (-p)])
        Ea = np.concatenate([E, Eg, Ec]); Sa = np.concatenate([s, tail])
        row = {}
        for L in (V1_CAP,) + CANDIDATE_LIMITS:
            T = L / 1.5
            row[f"{L:g}"] = r6(pw_integral(Ea, Sa, T) / pw_integral(Ed, sd, T) - 1)
        out[mode] = row
    return out


def vib_comparison():
    """Tabata n2-5 fit (Itikawa 1986 recommended v 0->1, 1.05-48.5 eV) Maxwellian rate, split at 5 eV, vs Laporta k01."""
    E = np.concatenate([np.linspace(1.05, 5.0, 800), np.linspace(5.0, 48.5, 1200)[1:]])
    s = np.array([tabata_sigma_m2("n2-5 v0->1", e) for e in E])
    i5 = int(np.searchsorted(E, 5.0))
    rows = {}
    for T in (1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 80.0, 100.0):
        k_res = rate_from_integral(pw_integral(E[: i5 + 1], s[: i5 + 1], T), T)
        k_non = rate_from_integral(pw_integral(E[i5:], s[i5:], T), T)
        k_non_hold = rate_from_integral(pw_integral(E[i5:], s[i5:], T) + hold_tail(s[-1], E[-1], T), T)
        k_lap = VIB.k_vib(T, 1)[0][1]
        rows[f"{T:g}"] = {"mean_energy_eV": r6(1.5 * T), "k_Laporta_0to1_m3s": r6(k_lap),
                          "Tabata_below_5eV_over_Laporta": r6(k_res / k_lap),
                          "Tabata_5_to_48p5eV_over_Laporta": r6(k_non / k_lap),
                          "Tabata_above_5eV_hold_beyond_48p5_over_Laporta": r6(k_non_hold / k_lap)}
    return {"fit": "Tabata et al. 2006 n2-5 (fit to Itikawa et al. JPCRD 15, 985 (1986)), 1.05-48.5 eV, zero outside",
            "split_eV": 5.0, "rows": rows,
            "reading": ("the 5-48.5 eV part is the non-resonant/broad-feature excitation that the Laporta resonant-only table "
                        "omits; the ratio column is its Maxwellian rate relative to the table's 0->1 rate")}


# ------------------------------------------------------------------------------------------------ Fig. 19 extraction (optional)
X10, X1000, Y0, Y3 = 348.774, 534.467, 223.626, 86.866     # Fig. 19 frame: log-x ticks 10 / 1000 eV, y ticks 0.0 / 3.0


def _E(x):
    return 10 ** (1 + 2 * (x - X10) / (X1000 - X10))


def _S(y):
    return 3.0 * (Y0 - y) / (Y0 - Y3)


def extract_fig19(pdf):
    """Vector extraction of Song et al. JPCRD 2023 Fig. 19 (page 15 of the NSF PAR copy) into FIG19_CSV. Needs pymupdf."""
    import pymupdf
    if sha256(pdf) != SONG_PDF_SHA256:
        raise SystemExit(f"{pdf}: sha256 differs from the audited NSF PAR copy {SONG_PDF_SHA256}")
    page = pymupdf.open(pdf)[14]
    fig = [d for d in page.get_drawings() if d["rect"].x0 > 290 and d["rect"].y1 < 360]
    # legend samples sit in the upper-left boxes (x < 370 pt, y < 160 pt); no data point lies there (E < 17 eV has sigma < 0.4)
    legend = lambda d: d["rect"].y1 < 160 and d["rect"].x1 < 370

    def bez(p0, p1, p2, p3, n=12):
        return [((1 - t) ** 3 * p0.x + 3 * (1 - t) ** 2 * t * p1.x + 3 * (1 - t) * t ** 2 * p2.x + t ** 3 * p3.x,
                 (1 - t) ** 3 * p0.y + 3 * (1 - t) ** 2 * t * p1.y + 3 * (1 - t) * t ** 2 * p2.y + t ** 3 * p3.y)
                for t in (k / n for k in range(n + 1))]

    rows = []
    for col, series in (((0.0, 1.0, 0.0), "MS1997_curve"), ((1.0, 0.0, 1.0), "Kawaguchi2021_curve")):
        pts = set()
        for d in fig:
            if d["type"] == "s" and d.get("color") == col and not legend(d):
                for it in d["items"]:
                    if it[0] == "l":
                        pts |= {(round(it[1].x, 4), round(it[1].y, 4)), (round(it[2].x, 4), round(it[2].y, 4))}
                    elif it[0] == "c":
                        pts |= {(round(x, 4), round(y, 4)) for x, y in bez(*it[1:5])}
        rows += [(series, x, y) for x, y in sorted(pts)]
    for fill, series in (((0.0, 0.0, 1.0), "Winters1966_N_points"), ((1.0, 0.0, 0.0), "Cosby_diamonds_calibration")):
        for d in fig:
            if d["type"] == "f" and d.get("fill") == fill and not legend(d):
                r = d["rect"]
                rows.append((series, round((r.x0 + r.x1) / 2, 4), round((r.y0 + r.y1) / 2, 4)))
    bars = {}                                     # Cosby error bars: red vertical strokes, drawn above and below each diamond
    for d in fig:
        if d["type"] == "s" and d.get("color") == (1.0, 0.0, 0.0):
            for it in d["items"]:
                if it[0] == "l" and abs(it[1].x - it[2].x) < 0.01 and abs(it[1].y - it[2].y) > 0.5:
                    b = bars.setdefault(round(it[1].x, 4), [])
                    b += [it[1].y, it[2].y]
    for x, ys in sorted(bars.items()):
        rows += [("Cosby_errorbar_top", x, round(min(ys), 4)), ("Cosby_errorbar_bottom", x, round(max(ys), 4))]
    with open(FIG19_CSV, "w", newline="") as f:
        f.write("# Song, Cho, Karwasz, Kokoouline & Tennyson, J. Phys. Chem. Ref. Data 52, 023104 (2023), doi:10.1063/5.0150618,\n"
                "# Fig. 19, vector paths from the NSF Public Access Repository copy https://par.nsf.gov/servlets/purl/10526876\n"
                f"# (sha256 {SONG_PDF_SHA256}); extracted by scripts/chemistry/n2_domain_extension_requirements.py --extract-fig19.\n"
                "# Frame: x log10 from ticks 10 eV (x=348.774 pt) and 1000 eV (534.467 pt); y linear from ticks 0.0 (223.626 pt)\n"
                "# and 3.0 (86.866 pt) in 1e-16 cm^2. Series identified by the figure LEGEND (Majeed = green dashed, Kawaguchi =\n"
                "# magenta solid); the caption says the reverse (broken/solid) - the text (Kawaguchi 'somewhat lower', Majeed uses\n"
                "# Cosby) agrees with the legend. Markers: bounding-box centre (anchor ambiguity <= 0.5 pt ~ 0.011e-16 cm^2).\n"
                "# Evidence: digitized (vector) from a secondary figure; MS1997/Kawaguchi primaries not accessed (abstract only).\n")
        w = csv.writer(f)
        w.writerow(["series", "x_pt", "y_pt", "E_eV", "sigma_1e-16cm2"])
        for series, x, y in rows:
            w.writerow([series, f"{x:.4f}", f"{y:.4f}", f"{_E(x):.4f}", f"{_S(y):.5f}"])
    print("wrote", FIG19_CSV, len(rows), "rows")


def load_fig19():
    """Series -> sorted (E, sigma) with strictly increasing E (vertices sharing an x are averaged)."""
    ser = {}
    with open(FIG19_CSV) as f:
        for row in csv.DictReader(l for l in f if not l.startswith("#")):
            ser.setdefault(row["series"], {}).setdefault(float(row["E_eV"]), []).append(float(row["sigma_1e-16cm2"]))
    return {k: [(e, sum(v) / len(v)) for e, v in sorted(d.items())] for k, d in ser.items()}


def _interp_curve(pts, E):
    xs = [p[0] for p in pts]
    if E < xs[0] or E > xs[-1]:
        return None
    return float(np.interp(E, xs, [p[1] for p in pts]))


def dissociation_comparison():
    fig = load_fig19()
    E9 = np.array([e for e, _ in DIS.TABLE9], float); S9 = np.array([v for _, v in DIS.TABLE9], float)
    cal = sorted(fig["Cosby_diamonds_calibration"])
    assert len(cal) == len(E9)
    cal_dE = max(abs(e - e9) / e9 for (e, _), e9 in zip(cal, E9))
    cal_dS = max(abs(s - s9) for (_, s), s9 in zip(cal, S9))
    curves = {"MS1997_curve": fig["MS1997_curve"], "Kawaguchi2021_curve": fig["Kawaguchi2021_curve"],
              "Winters1966_N_points": sorted(fig["Winters1966_N_points"])}
    bars = {}
    for (e_t, s_t), (e_b, s_b) in zip(fig["Cosby_errorbar_top"], fig["Cosby_errorbar_bottom"]):
        i = int(np.argmin(np.abs(E9 - e_t)))
        bars[f"{E9[i]:g}"] = r6((s_t - s_b) / 2 / S9[i])
    out = {"calibration_vs_Table9": {"max_rel_dE": r6(cal_dE), "max_abs_dsigma_1e-16cm2": r6(cal_dS), "n_points": len(cal)},
           "cosby_errorbar_rel_halfwidth_by_E": bars,
           "cosby_errorbar_note": ("Fig. 19 draws Cosby's bars only up to 150 eV (Cosby measured 18.5-148.5 eV, Crossref abstract); "
                                   "the recommended 175 and 200 eV values carry no bar. JPCRD 2023 Sec. 2.7 states +-20 % for the set."),
           "series": {}}
    for name, pts in curves.items():
        rows = {}
        s200 = _interp_curve(pts, 200.0)
        for E in (50.0, 100.0, 150.0, 200.0, 250.0, 300.0, 500.0, 700.0, 900.0):
            v = _interp_curve(pts, E)
            if v is None:
                continue
            row = {"sigma_1e-16cm2": r6(v)}
            if E <= 200:
                row["over_Cosby_Table9"] = r6(v / float(np.interp(E, E9, S9)))
            if s200:
                row["shape_sigma_over_sigma200"] = r6(v / s200)
            rows[f"{E:g}"] = row
        out["series"][name] = {"E_range_eV": [r6(pts[0][0]), r6(pts[-1][0])], "n_points": len(pts), "points": rows}
    # Rate consequence: Cosby <= 200 eV with the tail shaped by each independent curve (normalised to Cosby at 200 eV), vs hold/zero.
    E = E9; s = S9 * 1e-20
    tails = {}
    for name in ("MS1997_curve", "Kawaguchi2021_curve", "Winters1966_N_points"):
        pts = curves[name]; s200 = _interp_curve(pts, 200.0)
        Et = np.array([p[0] for p in pts if p[0] > 200.0]); St = np.array([p[1] for p in pts if p[0] > 200.0]) / s200 * s[-1]
        tails[name] = (np.concatenate([E, Et]), np.concatenate([s, St]))
    E_meas = curves["Winters1966_N_points"][-1][0]                               # last measured independent point
    E_eval = min(curves["MS1997_curve"][-1][0], curves["Kawaguchi2021_curve"][-1][0])   # end of both evaluated curves
    out["coverage_ends_eV"] = {"measured_Winters1966": r6(E_meas), "evaluated_MS1997_and_Kawaguchi2021": r6(E_eval)}
    rate_rows = {}
    for L in (V1_CAP,) + CANDIDATE_LIMITS:
        T = L / 1.5
        I_low = pw_integral(E, s, T); I_hold = I_low + hold_tail(s[-1], E[-1], T)
        row = {"share_above_200eV_hold": r6((I_hold - I_low) / I_hold),
               "share_beyond_measured_end_hold_envelope": r6(hold_tail(s[-1], E_meas, T) / I_hold),
               "share_beyond_evaluated_end_hold_envelope": r6(hold_tail(s[-1], E_eval, T) / I_hold)}
        for name, (Ec, Sc) in tails.items():
            I_sh = pw_integral(Ec, Sc, T)                     # zero beyond the curve's end
            I_sh_hold = I_sh + hold_tail(Sc[-1], Ec[-1], T)   # held beyond the curve's end
            row[name] = {"share_above_200eV": r6((I_sh_hold - I_low) / I_sh_hold),
                         "share_beyond_curve_end_hold": r6((I_sh_hold - I_sh) / I_sh_hold),
                         "hold_table_over_shaped_minus_1": r6(I_hold / I_sh_hold - 1)}
        rate_rows[f"{L:g}"] = row
    out["rate_consequence_by_limit"] = rate_rows
    return out


def completeness_indicators():
    """Single-channel rate indicators from committed tables (read-only), for the extended-domain re-audit. NOT verdicts: the
    pre-registered F_P / F_ion / F_S fractions need full denominators and plasma states (blind envelope)."""
    bt = os.path.join(BR, "audit", "bound_tables"); pr = os.path.join(BR, "propellants")
    k = lambda path, eps: float(np.interp(eps, *np.loadtxt(path, skiprows=2).T))
    iz = os.path.join(pr, "ionization_N2_song2023.dat")
    rows = {}
    for L in (V1_CAP,) + CANDIDATE_LIMITS:
        r = {"T_e_eV": r6(L / 1.5)}
        for name, path in (("N2_to_N2dication_nominal_over_N2_ionization", os.path.join(bt, "ionization_N2_to_N2_Z2plus_nominal.dat")),
                           ("N2_to_N2dication_upper_over_N2_ionization", os.path.join(bt, "ionization_N2_to_N2_Z2plus_upper.dat"))):
            r[name] = r6(k(path, L) / k(iz, L))
        for name, path in (("N_Z2plus_to_N_Z3plus_rate_over_its_45eV_value", os.path.join(bt, "ionization_N_Z2plus_to_N_Z3plus_bell1983.dat")),
                           ("N2plus_to_N2dication_rate_over_its_45eV_value", os.path.join(bt, "ionization_N2_Z1plus_to_N2_Z2plus_tabata2006.dat"))):
            r[name] = r6(k(path, L) / k(path, V1_CAP))
        rows[f"{L:g}"] = r
    return {"note": ("indicators only (rate-coefficient ratios at mean energy L from committed tables); the v1 verdicts used "
                     "T_e <= 30 eV; the closure envelope must be re-run on any extended domain before any verdict"),
            "by_mean_energy_eV": rows}


# ------------------------------------------------------------------------------------------------------ verdict criteria (DRAFT)
RULE = {
    "status": "DRAFT_PENDING_OWNER",
    "C1_coverage": ("share of the table's declared-model Maxwellian rate at L from energies above the last point covered by "
                    "accessible published cross sections (the table's own sources plus independent sets passing C3) < 1 % "
                    "(the rate_validity.toml convention, applied to the covered range)"),
    "C2_shape": ("for every independent set passing C3, replacing the table's sigma above its own last source point by that set's "
                 "shape (scaled to the table at the join) changes the rate at L by < 1 %"),
    "C3_join": ("the independent set agrees with the table at the table's last source point within the stated uncertainty "
                "(combined in quadrature where both are published; the table's alone where the set's is not accessible)"),
    "readings": {"measured": ("C1 counts only MEASUREMENT-BASED independent sets: measured, or reconstructed by arithmetic from "
                              "measured sets (e.g. Winters' neutral points = measured N-atom deposition minus measured dissociative "
                              "ionization); digitized from a secondary figure allowed"),
                 "evaluated": "C1 also counts EVALUATED/recommended sets (secondary reproductions of abstract-only primaries)"},
    "verdict_map": {"SUPPORTED": "measured reading passes at >= 60 eV; proposal = largest candidate L passing (DRAFT)",
                    "PARTIAL": "only the evaluated reading passes at >= 60 eV, or the table content is supported but a "
                               "documented omission needs the completeness re-audit",
                    "UNSUPPORTED": "accessible independent evidence passing C3 fails C2 at 60 eV",
                    "UNRESOLVED-BY-SOURCE": "no accessible independent set above the table's last source point passes C3"},
    "not_a_criterion_change": "C1 re-uses the existing 1 % convention; nothing in v1 (f_out tolerance, limits, criteria) changes",
}
MEASUREMENT_BASED = ("measured", "reconstructed_from_measured")   # classes counted by the measured reading
COSBY_REL_UNC = 0.20      # JPCRD 2023 Sec. 2.7: +-20 % on the recommended Cosby set
WINTERS_REL_UNC = 0.20    # JPCRD 2023 Sec. 2.7: "An estimated uncertainty of these values is +-20%"


def _bisect_L(f, lo=10.0, hi=255.0):
    """Largest L in [lo, hi] with f(L) < 0.01, f increasing in L; None if f(lo) >= 0.01."""
    if f(lo) >= 0.01:
        return None
    if f(hi) < 0.01:
        return hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if f(mid) < 0.01:
            lo = mid
        else:
            hi = mid
    return lo


def criteria(capped, dis, ele):
    out = {"rule": RULE, "per_table": {}}
    E9 = np.array([e for e, _ in DIS.TABLE9], float); s9 = np.array([v for _, v in DIS.TABLE9], float) * 1e-20
    for f in capped:
        fam, E, s, E_last, _, decl = table_model(f)
        if fam == "vibrational":
            out["per_table"][f] = {"family": fam, "applicable": False,
                                   "reason": "rate fit without a cross section; see the independent non-resonant comparison"}
            continue
        sets = []
        if fam == "dissociation":
            ser = dis["series"]; ends = dis["coverage_ends_eV"]
            sets = [
                {"set": "Winters1966_N_points", "class": "reconstructed_from_measured", "end_eV": ends["measured_Winters1966"],
                 "independence_note": ("NOT independent at the join: the Cosby recommended set (Table 9) is a weighted average of "
                                       "Cosby's and Winters' data (JPCRD 2023 Sec. 2.7), so C3 at 200 eV is partly circular. Only "
                                       "the two points above 200 eV (about 246 and 296 eV) are independent coverage. Neutral points "
                                       "= Winters' measured N-atom deposition minus dissociative ionization (Fig. 19 caption: Tian "
                                       "& Vidal 1998; text: Rapp & Englander-Golden 1965)"),
                 "join_ratio": ser["Winters1966_N_points"]["points"]["200"]["over_Cosby_Table9"],
                 "join_tol": r6(math.hypot(COSBY_REL_UNC, WINTERS_REL_UNC)), "join_tol_basis": "Cosby +-20 % (+) Winters +-20 %"},
                {"set": "MS1997_curve", "class": "evaluated", "end_eV": ser["MS1997_curve"]["E_range_eV"][1],
                 "independence_note": ("NOT independent at the join: MS1997 used Cosby's recommended values (JPCRD 2023 Sec. 2.7), "
                                       "so C3 at 200 eV holds by construction; how MS1997 built the > 200 eV part is not "
                                       "accessible (TBD - requires the MS1997 full text)"),
                 "join_ratio": ser["MS1997_curve"]["points"]["200"]["over_Cosby_Table9"],
                 "join_tol": COSBY_REL_UNC, "join_tol_basis": "Cosby +-20 % (MS1997 uncertainty not accessible: TBD)"},
                {"set": "Kawaguchi2021_curve", "class": "evaluated", "end_eV": ser["Kawaguchi2021_curve"]["E_range_eV"][1],
                 "independence_note": "construction not accessible (TBD - requires the full text)",
                 "join_ratio": ser["Kawaguchi2021_curve"]["points"]["200"]["over_Cosby_Table9"],
                 "join_tol": COSBY_REL_UNC, "join_tol_basis": "Cosby +-20 % (Kawaguchi uncertainty not accessible: TBD)"}]
            shape = {st["set"]: {L: dis["rate_consequence_by_limit"][L][st["set"]]["hold_table_over_shaped_minus_1"]
                                 for L in dis["rate_consequence_by_limit"]} for st in sets}

            def share_beyond(Ecov, L):
                T = L / 1.5
                I_hold = pw_integral(E9, s9, T) + hold_tail(s9[-1], 200.0, T)
                return hold_tail(s9[-1], max(Ecov, 200.0), T) / I_hold
        elif fam == "electronic":
            key = ELEC_KEYS[f]; e = ele[f]; _, Sj, Uj = EXC.johnson(key)
            join = e["points"].get(f"{E_last:g}", {})
            sets = [{"set": "MS1997_via_QST", "class": "evaluated", "end_eV": e["MS1997_range_eV"][1],
                     "join_ratio": join.get("MS1997_over_table"), "join_tol": r6(Uj[-1] / Sj[-1]),
                     "join_tol_basis": f"Johnson 2005 relative uncertainty at {E_last:g} eV (MS1997 uncertainty not accessible: TBD)"}]
            shape = {"MS1997_via_QST": e["rate_impact_if_MS1997_above_last_point"]["shape"]}
            Ed, sd = decl

            def share_beyond(Ecov, L, Ed=Ed, sd=sd):
                T = L / 1.5
                return pw_integral(Ed, sd, T, max(Ecov, E_last)) / pw_integral(Ed, sd, T)
        else:   # rotational: no accessible independent set above 10 eV
            shape = {}

            def share_beyond(Ecov, L, E=E, s=s, E_last=E_last):
                T = L / 1.5
                I = pw_integral(E, s, T) + hold_tail(s[-1], E_last, T)
                return hold_tail(s[-1], max(Ecov, E_last), T) / I
        for st in sets:
            st["join_ok"] = bool(st["join_ratio"] is not None and abs(st["join_ratio"] - 1) <= st["join_tol"])
        passing = [st for st in sets if st["join_ok"]]
        cov_meas = max([E_last] + [st["end_eV"] for st in passing if st["class"] in MEASUREMENT_BASED])
        cov_eval = max([E_last] + [st["end_eV"] for st in passing])
        by_L, ok_m, ok_e, max_m, max_e = {}, True, True, None, None
        for L in CANDIDATE_LIMITS:
            k = f"{L:g}"
            sh = max([abs(shape[st["set"]][k]) for st in passing], default=0.0)
            cm, ce = share_beyond(cov_meas, L), share_beyond(cov_eval, L)
            pm = bool(cm < 0.01 and sh < 0.01 and any(st["class"] in MEASUREMENT_BASED for st in passing))
            pe = bool(ce < 0.01 and sh < 0.01 and bool(passing))
            ok_m = ok_m and pm; ok_e = ok_e and pe
            max_m = L if ok_m else max_m; max_e = L if ok_e else max_e
            by_L[k] = {"coverage_share_measured_reading": r6(cm), "coverage_share_evaluated_reading": r6(ce),
                       "max_abs_shape_impact_passing_sets": r6(sh), "passes_measured_reading": pm, "passes_evaluated_reading": pe}
        out["per_table"][f] = {
            "family": fam, "applicable": True, "own_last_source_point_eV": r6(E_last),
            "independent_sets": [{k: (r6(v) if isinstance(v, float) else v) for k, v in st.items()} for st in sets],
            "coverage_end_measured_reading_eV": r6(cov_meas), "coverage_end_evaluated_reading_eV": r6(cov_eval),
            "L_star_own_sources_eV": r6(_bisect_L(lambda L: share_beyond(E_last, L))),
            "L_star_measured_coverage_eV": r6(_bisect_L(lambda L: share_beyond(cov_meas, L))),
            "by_limit": by_L,
            "max_candidate_L_measured_reading": max_m, "max_candidate_L_evaluated_reading": max_e}
    return out


def draft_proposals(crit):
    """DRAFT_PENDING_OWNER: the largest candidate limit passing the measured reading, per table (SUPPORTED tables only)."""
    return {f: c["max_candidate_L_measured_reading"] for f, c in crit["per_table"].items()
            if c.get("applicable") and c["max_candidate_L_measured_reading"] is not None}


# --------------------------------------------------------------------------------------------------------------------- main
def compute():
    validity = tomllib.load(open(VALIDITY, "rb"))
    recs, scores = load_v1()
    inv, ood, _ = v1_inventory(recs, scores, validity)
    capped = inv["capped_tables"]
    dis = dissociation_comparison(); ele = electronic_comparison()
    crit = criteria(capped, dis, ele)
    props = draft_proposals(crit)
    evald = {f: c["max_candidate_L_evaluated_reading"] for f, c in crit["per_table"].items()
             if c.get("applicable") and c["max_candidate_L_evaluated_reading"] is not None}
    cov_props, _ = coverage_for_limits(recs, ood, capped, props)
    cov_eval, _ = coverage_for_limits(recs, ood, capped, evald)
    return {
        "id": "n2_domain_extension_requirements_v1",
        "status": "DRAFT_PENDING_OWNER",
        "non_gating": ("Evidence audit only. No run is scored, re-scored or re-labelled; no limit, table, criterion or tolerance "
                       "is changed. The P5-N2 v1 vacuum outcome (all nine candidates INCONCLUSIVE / NOT ELIGIBLE, credible set "
                       "empty) is permanent and is never rewritten."),
        "generated_by": "scripts/chemistry/n2_domain_extension_requirements.py",
        "inputs_sha256": {os.path.relpath(p, ROOT): sha256(p) for p in (RAW, SCORES, VALIDITY, FIG19_CSV)},
        "rate_convention": ("k(T_e) = sqrt(8/(pi m_e)) (e T_e)^-3/2 int sigma E exp(-E/T_e) dE tabulated against mean energy "
                            "3/2 T_e (abep_sim/rate_tables.py); HallThruster.jl v0.23.1 looks rates up at 3/2 Tev on a 0-255 eV "
                            "grid (src/collisions/collision_frequencies.jl, reactions.jl)"),
        "candidate_limits_mean_energy_eV": list(CANDIDATE_LIMITS),
        "v1_inventory": inv,
        "hypothetical_coverage": hypothetical_coverage(recs, ood, capped),
        "requirements": requirements(capped),
        "verdict_criteria": crit,
        "draft_proposed_limits_mean_energy_eV": {"status": "DRAFT_PENDING_OWNER", "limits": props,
                                                 "hypothetical_coverage_if_applied": cov_props,
                                                 "evaluated_reading_limits_not_proposed": evald,
                                                 "hypothetical_coverage_evaluated_reading": cov_eval},
        "independent_comparisons": {"dissociation_song2023_fig19": dis,
                                    "electronic_MS1997_and_Tabata2006": ele,
                                    "vibrational_0to1_Tabata2006_n2-5": vib_comparison(),
                                    "rotational": {"note": ("no accessible independent cross section above the JPCRD 2023 Table 6 "
                                                            "end point (10 eV); the Tabata n2-4 fit (to Itikawa et al. 1986) "
                                                            "covers 0.0296-2.94 eV only")}},
        "completeness_indicators": completeness_indicators(),
    }


def _normalise(obj):
    return json.loads(json.dumps(obj))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--extract-fig19", metavar="PDF")
    a = ap.parse_args(argv)
    if a.extract_fig19:
        extract_fig19(a.extract_fig19)
        return 0
    res = _normalise(compute())
    if a.check:
        old = json.load(open(OUT))
        if old != res:
            print("MISMATCH: committed JSON differs from recomputation"); return 1
        print("OK: committed JSON reproduced"); return 0
    with open(OUT, "w") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())

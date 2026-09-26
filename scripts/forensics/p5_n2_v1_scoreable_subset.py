"""Scoreable-subset forensics of the P5-N2 v1 VACUUM campaign (descriptive, NON-GATING).

Scope: the 732 scoreable run-readings of the frozen v1 vacuum campaign (official status PASS 32 + FAIL_VALIDATION 700), with
emphasis on sgb-screen-05 .. 09. The official v1 outcome is final and is never rewritten: all 9 screening candidates
INCONCLUSIVE / NOT ELIGIBLE, credible set empty, gate 3 FAIL.

Rules this script follows:
  * Every run status and failure reason is READ from the official scores file
    (validation/p5_n2_campaign_v1_vacuum_scores.json, sha256-checked against VALIDATION_RELEASE_v1.json). Nothing is
    re-scored or re-labelled. Criteria/tolerances are read from the frozen pre-registration only to print them next to
    the distributions; they are never re-applied.
  * The raw frozen dataset (sha256-checked against its freeze manifest) is joined by key only for time-history statistics
    (bridge outputs: Id_rms_rel, Id_pp_rel, Id_max_A, Id_f_dominant_Hz, Te_max_eV, ion_current_A).
  * Transport parameters and the Xe screening metrics come from ensemble/transport_ensemble_v0.json
    (screening_candidates, sha256-checked against the pin in the pre-registration). The Xe metrics are parsed from each
    candidate's evidence_basis string; the Xe hypothesis label (H1a..H3b) is mapped to registration / coil with
    identification/p5_xe_identification_sgb_v1_vacuum_runs.csv.
  * The anode mass flow for the N2-equivalent current is read from cases/p5_n2.json (Brabston 2025 Table 2, measured).
  * Rank correlations over the 9 candidates are descriptive (n = 9): no fit, no significance test, no parameter
    recommendation.

Outputs (deterministic; pure standard library, fixed ordering, values rounded to 6 significant figures):
  docs/forensics/p5_n2_v1/scoreable_subset/scoreable_subset.json
  docs/forensics/p5_n2_v1/scoreable_subset/SCOREABLE_SUBSET.md
Usage:
  python scripts/forensics/p5_n2_v1_scoreable_subset.py          # (re)write both files
  python scripts/forensics/p5_n2_v1_scoreable_subset.py --check  # exit 1 if the committed files differ from a rebuild
"""
import collections
import csv
import gzip
import hashlib
import json
import math
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BR = os.path.join(ROOT, "hallthruster_bridge")
VAL = os.path.join(BR, "validation")
REL = {
    "scores": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores.json",
    "raw": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_raw.jsonl.gz",
    "raw_manifest": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_raw_manifest.json",
    "release": "hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json",
    "decision": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_decision.json",
    "report": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_report.md",
    "criteria": "hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json",
    "ensemble": "hallthruster_bridge/ensemble/transport_ensemble_v0.json",
    "cases": "hallthruster_bridge/cases/p5_n2.json",
    "xe_runs": "hallthruster_bridge/identification/p5_xe_identification_sgb_v1_vacuum_runs.csv",
}
OUT_DIR = os.path.join(ROOT, "docs", "forensics", "p5_n2_v1", "scoreable_subset")
OUT_JSON = os.path.join(OUT_DIR, "scoreable_subset.json")
OUT_MD = os.path.join(OUT_DIR, "SCOREABLE_SUBSET.md")

POINTS = ["N1", "N2", "N3", "N4", "N5"]
T_POINTS = ["N1", "N2", "N3"]
READINGS = ["A", "B"]
REASONS = ["CURRENT", "THRUST", "SUSTAINMENT"]
STATUSES = ["PASS", "FAIL_VALIDATION", "OUT_OF_DOMAIN", "NUMERICAL_FAILURE"]
SCOREABLE = ("PASS", "FAIL_VALIDATION")
REGS = ["L32-anode", "L32-exit", "L38-hist"]
COILS = ["1p6kW", "3p0kW"]
EMPHASIS = ["sgb-screen-05", "sgb-screen-06", "sgb-screen-07", "sgb-screen-08", "sgb-screen-09"]
CHEM_SHORT = {"n2_n.toml": "nom", "n2_n_di_lower.toml": "DI-low", "n2_n_nel_wang.toml": "Wang",
              "n2_n_di_lower_nel_wang.toml": "DI-low+Wang"}
REASON_CODE = {"CURRENT": "C", "THRUST": "T", "SUSTAINMENT": "S"}
E_CHARGE = 1.602176634e-19                     # C (CODATA exact)
AMU = 1.66053906660e-27                        # kg (CODATA 2018), same constant as scripts/score_p5_n2_campaign.py
M_N2 = 28.0134 * AMU                           # kg, same molar mass as scripts/score_p5_n2_campaign.py
COVERAGE_LABEL = "coverage description, not a verdict, not a promotion; the official verdicts are final"
N9_CAVEAT = ("n = 9 candidates, descriptive rank correlation only: not a fit, no significance test, no parameter "
             "recommendation. The 9 candidates were selected by the Xe screen (not a designed experiment), so parameters "
             "co-vary (see parameter_intercorrelation) and a rank relation cannot be attributed to a single parameter.")


# ----------------------------------------------------------------------------------------------------------------- helpers
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def p(rel):
    return os.path.join(ROOT, rel)


def sig(x, n=6):
    """Round to n significant figures (deterministic JSON output)."""
    if x is None:
        return None
    if isinstance(x, bool) or isinstance(x, int):
        return x
    if not math.isfinite(x):
        return None
    return float(f"{x:.{n}g}")


def quantile(sorted_v, q):
    """Linear interpolation between order statistics (Hyndman-Fan type 7)."""
    h = (len(sorted_v) - 1) * q
    lo = int(math.floor(h))
    hi = min(lo + 1, len(sorted_v) - 1)
    return sorted_v[lo] + (h - lo) * (sorted_v[hi] - sorted_v[lo])


def desc(values):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    return {"n": len(v), "min": sig(v[0]), "p10": sig(quantile(v, 0.10)), "p25": sig(quantile(v, 0.25)),
            "median": sig(quantile(v, 0.5)), "p75": sig(quantile(v, 0.75)), "p90": sig(quantile(v, 0.90)),
            "max": sig(v[-1]), "frac_positive": sig(sum(x > 0 for x in v) / len(v))}


def median(values):
    v = sorted(x for x in values if x is not None)
    return None if not v else quantile(v, 0.5)


def avg_ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return r


def pearson(x, y):
    n = len(x)
    if n < 3:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def spearman(x, y, min_n=5):
    """Spearman rho (Pearson on average ranks, ties averaged) over the pairs where both values exist."""
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < min_n:
        return {"rho": None, "n": len(pairs), "note": f"fewer than {min_n} candidates with a value"}
    xs, ys = [a for a, _ in pairs], [b for _, b in pairs]
    if len(set(xs)) == 1 or len(set(ys)) == 1:
        return {"rho": None, "n": len(pairs), "note": "constant over the candidates with a value"}
    return {"rho": sig(pearson(avg_ranks(xs), avg_ranks(ys)), 4), "n": len(pairs)}


def parse_key(key):
    cand, chem, case, mode = key.split("|")
    point, rest = case.split("-", 1)
    reg, coil = rest.rsplit("-", 1)
    return {"candidate": cand, "chemistry": chem, "case": case, "point": point, "registration": reg, "coil": coil,
            "mode": mode}


def cshort(c):
    return c.replace("sgb-screen-", "")


# ------------------------------------------------------------------------------------------------------------------ inputs
def load_inputs():
    """Load and hash-check every input. Raises on any mismatch (no silent fallback)."""
    release = json.load(open(p(REL["release"])))
    manifest = json.load(open(p(REL["raw_manifest"])))
    criteria = json.load(open(p(REL["criteria"])))
    hashes = {k: sha256(p(v)) for k, v in REL.items()}
    checks = {
        "scores_sha256_matches_VALIDATION_RELEASE_v1": hashes["scores"] == release["scores"]["sha256"],
        "raw_gz_sha256_matches_freeze_manifest": hashes["raw"] == manifest["sha256_gz"],
        "decision_sha256_matches_VALIDATION_RELEASE_v1": hashes["decision"] == release["decision"]["sha256"],
        "report_sha256_matches_VALIDATION_RELEASE_v1": hashes["report"] == release["report"]["sha256"],
        "ensemble_sha256_matches_preregistration_pin":
            hashes["ensemble"] == criteria["inputs_pinned"]["transport_candidates"]["sha256"],
        "cases_sha256_matches_preregistration_pin": hashes["cases"] == criteria["inputs_pinned"]["cases"]["sha256"],
    }
    bad = [k for k, ok in checks.items() if not ok]
    if bad:
        raise SystemExit(f"input hash check failed: {bad}")
    scores = json.load(open(p(REL["scores"])))
    decision = json.load(open(p(REL["decision"])))
    raw = {}
    with gzip.open(p(REL["raw"]), "rt") as f:
        for line in f:
            r = json.loads(line)
            raw[r["key"]] = r
    ensemble = json.load(open(p(REL["ensemble"])))
    cases = {c["id"]: c for c in json.load(open(p(REL["cases"])))["cases"]}
    with open(p(REL["xe_runs"])) as f:
        hyp = {}
        for row in csv.DictReader(f):
            prev = hyp.setdefault(row["hypothesis"], (row["registration"], row["coil"]))
            if prev != (row["registration"], row["coil"]):
                raise SystemExit(f"Xe hypothesis {row['hypothesis']} maps to two layer-1 combinations")
    return {"scores": scores, "decision": decision, "raw": raw, "ensemble": ensemble, "criteria": criteria, "cases": cases,
            "xe_hypotheses": hyp, "hashes": hashes, "checks": checks}


XE_RE = re.compile(r"max \|dI_d\| ([0-9.]+) % under (H[0-9][ab])/([AB]) \(dI_d \[([^\]]*)\] %, RMS \[([^\]]*)\]\)")


def candidate_table(ensemble, xe_hyp):
    out = {}
    for s in ensemble["screening_candidates"]:
        tp = s["transport_parameters"]
        m = XE_RE.search(s["evidence_basis"])
        if m is None:
            raise SystemExit(f"cannot parse the Xe screening metrics of {s['ensemble_member_id']}")
        dI = [float(x) for x in m.group(4).split(",")]
        rms = [float(x) for x in m.group(5).split(",")]
        if abs(max(abs(x) for x in dI) - float(m.group(1))) > 0.011:
            raise SystemExit(f"{s['ensemble_member_id']}: stated max |dI_d| disagrees with its per-point values")
        reg, coil = xe_hyp[m.group(2)]
        hyps = s["calibration_hypotheses"]
        out[s["ensemble_member_id"]] = {
            "transport_family": s["transport_family"],
            "a_anom_scale": tp["anom_scale"], "b_barrier_scale": tp["barrier_scale"], "c_center_L": tp["center_L"],
            "w_width_L": tp["width_L"],
            "derived_trough_floor_a_1_minus_b": sig(tp["anom_scale"] * (1 - tp["barrier_scale"])),
            "derived_trough_deficit_b_times_w": sig(tp["barrier_scale"] * tp["width_L"]),
            "xe_in_sample_max_abs_dI_pct": float(m.group(1)),
            "xe_in_sample_hypothesis": f"{m.group(2)} = {reg}/{coil}, reading {m.group(3)}",
            "xe_dI_pct_Xe1_Xe2_Xe3": dI,
            "xe_Id_rms_rel_Xe1_Xe2_Xe3": rms,
            "xe_Id_rms_rel_mean": sig(sum(rms) / len(rms)),
            "xe_n_layer1_combinations_passing_screen": len(hyps),
            "xe_layer1_registrations_passing_screen": sorted({h["p5_registration"] for h in hyps}),
        }
    return out


def build_rows(inp):
    rows = []
    for r in inp["scores"]["runs"]:
        k = parse_key(r["key"])
        if k["mode"] != "vacuum":
            raise SystemExit("non-vacuum record in the v1 vacuum scores file")
        raw = inp["raw"][r["key"]]
        case = inp["cases"][k["case"]]
        I_m = case["mdot_kgps"] * E_CHARGE / M_N2
        row = dict(k)
        row.update({
            "key": r["key"], "reading": r["reading"], "member": f"{k['registration']}|{k['coil']}|{r['reading']}",
            "status": r["status"], "reasons": list(r["reasons"]), "dI_rel": r.get("dI_rel"), "dT_mN": r.get("dT_mN"),
            "I_target_A": r["I_target_A"], "T_axial_mN": r.get("T_axial_mN"), "T_target_mN": r.get("T_target_mN"),
            "final10_mean_over_target": r["final10_mean_over_target"],
            "final10_frac_below_0p10": r["final10_frac_below_0p10"],
            "Id_rms_rel": raw["Id_rms_rel"], "Id_pp_rel": raw["Id_pp_rel"],
            "Id_max_over_target": raw["Id_max_A"] / r["I_target_A"], "Id_f_dominant_kHz": raw["Id_f_dominant_Hz"] / 1e3,
            "Te_max_eV": raw["Te_max_eV"],
            "ion_over_discharge": raw["ion_current_A"] / raw["discharge_current_A"],
            "ion_over_target": raw["ion_current_A"] / r["I_target_A"],
            "ion_over_N2_equivalent": raw["ion_current_A"] / I_m,
            "target_over_N2_equivalent": r["I_target_A"] / I_m,
        })
        row["scoreable"] = row["status"] in SCOREABLE
        if row["dT_mN"] is not None:
            row["thrust_per_current_ratio"] = (row["T_axial_mN"] / row["T_target_mN"]) / (1.0 + row["dI_rel"])
        rows.append(row)
    return rows


# ------------------------------------------------------------------------------------------------------------- tallies (1)
def tally(rows):
    t = {"n": len(rows), "scoreable": sum(r["scoreable"] for r in rows)}
    for s in STATUSES:
        t[s] = sum(r["status"] == s for r in rows)
    for q in REASONS:
        t[q] = sum(q in r["reasons"] for r in rows)
    return t


def group(rows, *keys):
    g = collections.defaultdict(list)
    for r in rows:
        g[tuple(r[k] for k in keys)].append(r)
    return g


def code(r):
    if r["status"] == "PASS":
        return "P"
    if r["status"] == "FAIL_VALIDATION":
        return "".join(REASON_CODE[q] for q in REASONS if q in r["reasons"])
    if r["status"] == "OUT_OF_DOMAIN":
        return "·"
    return "X"


def section1(rows, inp, cands, members, chems):
    vac = inp["scores"]["candidates"]["vacuum"]
    by_c = group(rows, "candidate")
    by_cp = group(rows, "candidate", "point")
    by_cm = group(rows, "candidate", "member")
    by_cc = group(rows, "candidate", "chemistry")
    idx = {(r["candidate"], r["member"], r["chemistry"], r["point"]): r for r in rows}
    grid = {c: {m: {ch: [code(idx[(c, m, ch, pt)]) for pt in POINTS] for ch in chems} for m in members} for c in cands}
    return {
        "unit": "run-reading (one run under one divergence reading), as in the official report; 1080 runs x 2 = 2160",
        "totals": tally(rows),
        "by_candidate": {c: tally(by_c[(c,)]) for c in cands},
        "by_point": {pt: tally(v) for (pt,), v in sorted(group(rows, "point").items())},
        "by_chemistry": {ch: tally(group(rows, "chemistry")[(ch,)]) for ch in chems},
        "by_registration": {g: tally(group(rows, "registration")[(g,)]) for g in REGS},
        "by_coil": {g: tally(group(rows, "coil")[(g,)]) for g in COILS},
        "by_reading": {g: tally(group(rows, "reading")[(g,)]) for g in READINGS},
        "by_candidate_point": {c: {pt: tally(by_cp[(c, pt)]) for pt in POINTS} for c in cands},
        "by_candidate_member": {c: {m: dict(tally(by_cm[(c, m)]), official_member_verdict=vac[c]["members"][m])
                                    for m in members} for c in cands},
        "by_candidate_chemistry": {c: {ch: tally(by_cc[(c, ch)]) for ch in chems} for c in cands},
        "grid_legend": {"P": "PASS", "C/T/S": "FAIL_VALIDATION with official reasons CURRENT / THRUST / SUSTAINMENT",
                        "·": "OUT_OF_DOMAIN (not scoreable)", "X": "NUMERICAL_FAILURE",
                        "order": "grid[candidate][member][chemistry] = codes at N1..N5"},
        "grid": grid,
    }


# ----------------------------------------------------------------------------------------------------------- residuals (2)
def section2(rows, runs_A, cands):
    sc = [r for r in rows if r["scoreable"]]
    scA = [r for r in runs_A if r["scoreable"]]
    out = {"unit_note": ("dI_rel = (I_d,window mean - I_target)/I_target (reading-independent); dT_mN = T_1D x f_reading - "
                         "T_target (N1-N3 only; D2: thrust at N4/N5 not scored). Scoreable subset only. Distributions split "
                         "by official status are given per reading because the PASS/FAIL split of a run can differ "
                         "between readings (THRUST only).")}
    dI, dT = {}, {}
    for rd in READINGS:
        dI[rd], dT[rd] = {}, {}
        for st in SCOREABLE:
            sub = [r for r in sc if r["reading"] == rd and r["status"] == st]
            dI[rd][st] = {pt: desc(r["dI_rel"] for r in sub if r["point"] == pt) for pt in POINTS}
            dI[rd][st]["pooled"] = desc(r["dI_rel"] for r in sub)
            dT[rd][st] = {pt: desc(r["dT_mN"] for r in sub if r["point"] == pt) for pt in T_POINTS}
    out["dI_rel_by_reading_status_point"] = dI
    out["dT_mN_by_reading_status_point"] = dT
    # per candidate x point: dI over scoreable runs (reading-independent, each run once) and dT per reading
    cp = {}
    for c in cands:
        cp[c] = {}
        for pt in POINTS:
            runs = [r for r in scA if r["candidate"] == c and r["point"] == pt]
            e = {"runs_scoreable": len(runs), "dI_rel": desc(r["dI_rel"] for r in runs)}
            for rd in READINGS:
                rr = [r for r in sc if r["candidate"] == c and r["point"] == pt and r["reading"] == rd]
                e[f"PASS_{rd}"] = sum(r["status"] == "PASS" for r in rr)
                e[f"FAIL_{rd}"] = sum(r["status"] == "FAIL_VALIDATION" for r in rr)
                if pt in T_POINTS:
                    e[f"dT_mN_{rd}"] = desc(r["dT_mN"] for r in rr)
            cp[c][pt] = e
    out["by_candidate_point"] = cp
    out["sign_patterns"] = sign_patterns(rows, runs_A, cands)
    out["structure"] = structure(rows, runs_A)
    return out


def over_under(rs, field):
    return {"over": sum(r[field] > 0 for r in rs), "under": sum(r[field] < 0 for r in rs)}


def sign_patterns(rows, runs_A, cands):
    curA = [r for r in runs_A if "CURRENT" in r["reasons"]]          # CURRENT is reading-independent: each run once
    sp = {"current_failures_unit": "runs (CURRENT is reading-independent; each run counted once)"}
    sp["current_failures_by_point"] = {pt: over_under([r for r in curA if r["point"] == pt], "dI_rel") for pt in POINTS}
    n25 = [r for r in curA if r["point"] != "N1"]
    sp["current_failures_N2_N5"] = dict(over_under(n25, "dI_rel"), n=len(n25))
    sp["current_failures_by_candidate_point"] = {
        c: {pt: over_under([r for r in curA if r["candidate"] == c and r["point"] == pt], "dI_rel") for pt in POINTS}
        for c in cands}
    sp["current_failures_by_registration_point"] = {
        g: {pt: over_under([r for r in curA if r["registration"] == g and r["point"] == pt], "dI_rel") for pt in POINTS}
        for g in REGS}
    thr = {}
    for rd in READINGS:
        t = [r for r in rows if r["reading"] == rd and "THRUST" in r["reasons"]]
        thr[rd] = {"by_point": {pt: over_under([r for r in t if r["point"] == pt], "dT_mN") for pt in T_POINTS},
                   "by_candidate": {c: over_under([r for r in t if r["candidate"] == c], "dT_mN") for c in cands},
                   "total": over_under(t, "dT_mN"),
                   "thrust_only_failures": sum(r["reasons"] == ["THRUST"] for r in t),
                   "thrust_without_current": sum("CURRENT" not in r["reasons"] for r in t)}
        both = [r for r in t if "CURRENT" in r["reasons"]]
        thr[rd]["current_and_thrust_same_sign"] = {"n": len(both), "same_sign": sum(
            (r["dI_rel"] > 0) == (r["dT_mN"] > 0) for r in both)}
    sp["thrust_failures_run_readings"] = thr
    corr = {}
    for rd in READINGS:
        corr[rd] = {}
        for pt in T_POINTS:
            rr = [r for r in rows if r["reading"] == rd and r["scoreable"] and r["point"] == pt]
            x, y = [r["dI_rel"] for r in rr], [r["dT_mN"] for r in rr]
            corr[rd][pt] = {"n": len(rr), "pearson": sig(pearson(x, y), 4),
                            "spearman": spearman(x, y)["rho"]}
    sp["dI_dT_correlation_scoreable"] = corr
    sp["scoreable_dI_positive_share_by_point"] = {
        pt: desc(r["dI_rel"] for r in runs_A if r["scoreable"] and r["point"] == pt) for pt in POINTS}
    return sp


def structure(rows, runs_A):
    scA = [r for r in runs_A if r["scoreable"]]
    st = {"dI_rel_by_registration_point": {g: {pt: desc(r["dI_rel"] for r in scA if r["registration"] == g
                                                        and r["point"] == pt) for pt in POINTS} for g in REGS}}
    idx = {(r["candidate"], r["chemistry"], r["registration"], r["point"], r["coil"]): r for r in runs_A}
    both, allv = [], []
    for (c, ch, g, pt, coil), r in idx.items():
        if coil != "1p6kW":
            continue
        s = idx[(c, ch, g, pt, "3p0kW")]
        allv.append(s["dI_rel"] - r["dI_rel"])
        if r["scoreable"] and s["scoreable"]:
            both.append(s["dI_rel"] - r["dI_rel"])
    st["coil_paired_dI_shift_3p0_minus_1p6"] = {"both_scoreable": desc(both),
                                                "context_all_numerically_valid_incl_OOD": desc(allv)}
    # chemistry: pairs of chemistries both scoreable at the same candidate, case and reading (official statuses compared)
    g = group([r for r in rows if r["scoreable"]], "candidate", "case", "reading")
    pairs = agree_s = agree_r = 0
    spreads = []
    for rs in g.values():
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                pairs += 1
                agree_s += rs[i]["status"] == rs[j]["status"]
                agree_r += sorted(rs[i]["reasons"]) == sorted(rs[j]["reasons"])
        if len(rs) == 4 and rs[0]["reading"] == "A":
            spreads.append(max(r["dI_rel"] for r in rs) - min(r["dI_rel"] for r in rs))
    st["chemistry_pairs_both_scoreable"] = {"pairs": pairs, "same_official_status": agree_s,
                                            "same_official_reasons": agree_r,
                                            "dI_range_across_4_chemistries_all_scoreable_groups": desc(spreads)}
    return st


# ------------------------------------------------------------------------------------------- transport parameters (3)
def section3(rows, runs_A, cands, ctab):
    scA = [r for r in runs_A if r["scoreable"]]
    summ = {}
    for c in cands:
        rc = [r for r in scA if r["candidate"] == c]
        allc = [r for r in runs_A if r["candidate"] == c]
        rr = [r for r in rows if r["candidate"] == c and r["scoreable"]]
        s = {
            "runs_scoreable": len(rc), "runs_total": len(allc),
            "coverage_share": sig(len(rc) / len(allc)),
            "median_dI_all_points": sig(median(r["dI_rel"] for r in rc)),
            "median_dI_N1": sig(median(r["dI_rel"] for r in rc if r["point"] == "N1")),
            "median_dI_N2_N5": sig(median(r["dI_rel"] for r in rc if r["point"] != "N1")),
            "median_dI_by_point": {pt: sig(median(r["dI_rel"] for r in rc if r["point"] == pt)) for pt in POINTS},
            "median_dT_N1_N3_A": sig(median(r["dT_mN"] for r in rr if r["reading"] == "A" and r["point"] in T_POINTS)),
            "median_dT_N1_N3_B": sig(median(r["dT_mN"] for r in rr if r["reading"] == "B" and r["point"] in T_POINTS)),
            "pass_share_run_readings": sig(sum(r["status"] == "PASS" for r in rr) / len(rr)) if rr else None,
            "sustainment_share_runs": sig(sum("SUSTAINMENT" in r["reasons"] for r in rc) / len(rc)) if rc else None,
            "context_median_dI_all_numerically_valid_incl_OOD": sig(median(r["dI_rel"] for r in allc)),
        }
        summ[c] = s
    xs = {
        "b_barrier_scale": lambda c: ctab[c]["b_barrier_scale"],
        "c_center_L": lambda c: ctab[c]["c_center_L"],
        "w_width_L": lambda c: ctab[c]["w_width_L"],
        "derived_trough_deficit_b_times_w": lambda c: ctab[c]["derived_trough_deficit_b_times_w"],
        "xe_in_sample_max_abs_dI_pct": lambda c: ctab[c]["xe_in_sample_max_abs_dI_pct"],
        "xe_dI_pct_Xe1": lambda c: ctab[c]["xe_dI_pct_Xe1_Xe2_Xe3"][0],
        "xe_dI_pct_Xe2": lambda c: ctab[c]["xe_dI_pct_Xe1_Xe2_Xe3"][1],
        "xe_dI_pct_Xe3": lambda c: ctab[c]["xe_dI_pct_Xe1_Xe2_Xe3"][2],
        "xe_Id_rms_rel_mean": lambda c: ctab[c]["xe_Id_rms_rel_mean"],
        "xe_n_layer1_combinations_passing_screen": lambda c: ctab[c]["xe_n_layer1_combinations_passing_screen"],
    }
    ys = ["median_dI_all_points", "median_dI_N1", "median_dI_N2_N5", "median_dT_N1_N3_A", "median_dT_N1_N3_B",
          "pass_share_run_readings", "sustainment_share_runs", "coverage_share",
          "context_median_dI_all_numerically_valid_incl_OOD"]
    rho = {x: {y: spearman([f(c) for c in cands], [summ[c][y] for c in cands]) for y in ys} for x, f in xs.items()}
    inter = {x1: {x2: spearman([f1(c) for c in cands], [f2(c) for c in cands])["rho"] for x2, f2 in xs.items()}
             for x1, f1 in xs.items()}
    a_vals = sorted({ctab[c]["a_anom_scale"] for c in cands})
    return {
        "caveat": N9_CAVEAT,
        "parameter_definition": ("HallThruster.jl v0.23.1 ScaledGaussianBohm (pinned source, collisions/anomalous.jl "
                                 "docstring; docs/HISTORY.md 2026-09-25): inverse Hall parameter "
                                 "a*(1 - b*exp(-0.5*((z - c*L)/(w*L))^2)); a = anom_scale, b = barrier_scale (trough "
                                 "depth), c = center_L, w = width_L. Derived (post hoc, descriptive): trough floor "
                                 "a*(1-b), trough deficit b*w (Gaussian deficit integral / (a L sqrt(2 pi)))."),
        "a_anom_scale": {"values": a_vals, "note": "constant across all 9 candidates: no rank relation can be formed"
                         if len(a_vals) == 1 else "varies"},
        "candidate_parameters_and_xe_metrics": ctab,
        "candidate_n2_scoreable_summaries": summ,
        "spearman_rho": rho,
        "parameter_intercorrelation_spearman_rho": inter,
    }


# ------------------------------------------------------------------------------------------------ member coverage (4)
def section4(rows, inp, cands, members, chems):
    vac = inp["scores"]["candidates"]["vacuum"]
    out = {"label": COVERAGE_LABEL,
           "definition": ("per (candidate, global layer-1 member = registration|coil|reading): the member's 20 official "
                          "run statuses (4 mandatory chemistries x 5 points); counts of scoreable, PASS and "
                          "FAIL_VALIDATION; which points and chemistries have at least one scoreable run; whether every "
                          "scoreable run-reading is PASS (null when none is scoreable). The official member verdict is "
                          "copied from the scores file."),
           "members": {}}
    g = group(rows, "candidate", "member")
    for c in cands:
        out["members"][c] = {}
        for m in members:
            rs = g[(c, m)]
            sc = [r for r in rs if r["scoreable"]]
            out["members"][c][m] = {
                "n_runs": len(rs), "n_scoreable": len(sc),
                "n_pass": sum(r["status"] == "PASS" for r in sc),
                "n_fail_validation": sum(r["status"] == "FAIL_VALIDATION" for r in sc),
                "points_scoreable": [pt for pt in POINTS if any(r["point"] == pt for r in sc)],
                "chemistries_scoreable": [ch for ch in chems if any(r["chemistry"] == ch for r in sc)],
                "point_chemistry_cells_scoreable_of_20": len(sc),
                "all_scoreable_pass": (all(r["status"] == "PASS" for r in sc) if sc else None),
                "official_member_verdict": vac[c]["members"][m],
            }
    out["members_with_all_scoreable_pass"] = [
        {"candidate": c, "member": m, "n_scoreable_of_20": v["n_scoreable"], "points_scoreable": v["points_scoreable"],
         "official_member_verdict": v["official_member_verdict"]}
        for c in cands for m, v in out["members"][c].items() if v["all_scoreable_pass"]]
    return out


# ------------------------------------------------------------------------------------------------ SUSTAINMENT runs (5)
ID_FIELDS = ["dI_rel", "final10_mean_over_target", "final10_frac_below_0p10", "Id_rms_rel", "Id_pp_rel",
             "Id_max_over_target", "Id_f_dominant_kHz", "Te_max_eV", "ion_over_discharge"]


def section5(rows, runs_A, cands, chems):
    # SUSTAINMENT is reading-independent: verify on the official labels, then count each run once (reading A row)
    flag = {}
    for r in rows:
        if r["scoreable"]:
            f = "SUSTAINMENT" in r["reasons"]
            if flag.setdefault(r["key"], f) != f:
                raise SystemExit(f"SUSTAINMENT differs between readings for {r['key']}")
    scA = [r for r in runs_A if r["scoreable"]]
    col = [r for r in scA if "SUSTAINMENT" in r["reasons"]]
    non = [r for r in scA if "SUSTAINMENT" not in r["reasons"]]
    co = {}
    for rd in READINGS:
        c = collections.Counter("+".join(r["reasons"]) for r in rows if r["reading"] == rd and "SUSTAINMENT" in r["reasons"])
        co[rd] = dict(sorted(c.items()))
    split = []
    for (c, case), rs in sorted(group(scA, "candidate", "case").items()):
        f = {r["chemistry"]: ("SUSTAINMENT" in r["reasons"]) for r in rs}
        if len(f) >= 2 and len(set(f.values())) == 2:
            split.append({"candidate": c, "case": case,
                          "collapsed": [CHEM_SHORT[ch] for ch in chems if f.get(ch) is True],
                          "not_collapsed": [CHEM_SHORT[ch] for ch in chems if f.get(ch) is False],
                          "not_scoreable": [CHEM_SHORT[ch] for ch in chems if ch not in f]})
    wm = [r["dI_rel"] for r in col]
    return {
        "unit": "runs (the official SUSTAINMENT reason is reading-independent; checked on every scoreable run)",
        "n_runs": len(col), "n_run_readings": 2 * len(col), "scoreable_runs": len(scA),
        "by_candidate": {c: {"sustainment": sum(r["candidate"] == c for r in col),
                             "scoreable": sum(r["candidate"] == c for r in scA)} for c in cands},
        "by_candidate_point": {c: {pt: sum(r["candidate"] == c and r["point"] == pt for r in col) for pt in POINTS}
                               for c in cands},
        "by_point": {pt: {"sustainment": sum(r["point"] == pt for r in col),
                          "scoreable": sum(r["point"] == pt for r in scA)} for pt in POINTS},
        "by_registration": {g: {"sustainment": sum(r["registration"] == g for r in col),
                                "scoreable": sum(r["registration"] == g for r in scA)} for g in REGS},
        "by_coil": {g: {"sustainment": sum(r["coil"] == g for r in col),
                        "scoreable": sum(r["coil"] == g for r in scA)} for g in COILS},
        "by_chemistry": {CHEM_SHORT[ch]: {"sustainment": sum(r["chemistry"] == ch for r in col),
                                          "scoreable": sum(r["chemistry"] == ch for r in scA)} for ch in chems},
        "by_candidate_member_point": {c: {f"{g}|{coil}": [pt for pt in POINTS if any(
            r["candidate"] == c and r["registration"] == g and r["coil"] == coil and r["point"] == pt for r in col)]
            for g in REGS for coil in COILS} for c in cands},
        "co_reasons_run_readings": co,
        "Id_statistics": {"collapsed": {f: desc(r[f] for r in col) for f in ID_FIELDS},
                          "scoreable_not_collapsed": {f: desc(r[f] for r in non) for f in ID_FIELDS}},
        "window_mean_dI_bands_collapsed": {"above_plus_0.15": sum(x > 0.15 for x in wm),
                                           "within_0.15": sum(abs(x) <= 0.15 for x in wm),
                                           "below_minus_0.15": sum(x < -0.15 for x in wm)},
        "chemistry_split_groups": split,
        "Id_field_definitions": {
            "dI_rel": "window-mean (1-2 ms) I_d residual vs the Eq. 14 target (official scores file)",
            "final10_mean_over_target / final10_frac_below_0p10": "O1 quantities over the final 10 % of the simulated "
                                                                  "time (official scores file)",
            "Id_rms_rel, Id_pp_rel, Id_max_over_target, Id_f_dominant_kHz": "bridge statistics of I_d(t) over the 1-2 ms "
                                                                            "averaging window (raw dataset)",
            "Te_max_eV": "maximum over z of the time-averaged (1-2 ms) T_e profile (raw dataset)",
            "ion_over_discharge": ("time-averaged (1-2 ms) ion current at the downstream domain boundary / window-mean "
                                   "I_d (raw dataset; bridge_lib.jl uses HallThruster.jl ion_current = ji[end] * "
                                   "channel_area[end], pinned v0.23.1 src/simulation/postprocess.jl)")},
    }


# ------------------------------------------------------------------------------------------- evidence statements (6)
def pct(a, b):
    return f"{a}/{b}" + (f" ({100.0 * a / b:.0f} %)" if b else "")


def fmt(x, d=3, signed=True):
    if x is None:
        return "n/a"
    return f"{x:+.{d}f}" if signed else f"{x:.{d}f}"


def group_facts(rows, runs_A, cs):
    rA = [r for r in runs_A if r["candidate"] in cs]
    sc = [r for r in rA if r["scoreable"]]
    rr = [r for r in rows if r["candidate"] in cs and r["scoreable"]]
    cur = [r for r in sc if "CURRENT" in r["reasons"]]
    cur_over = [r for r in cur if r["dI_rel"] > 0]
    passes = [r for r in rr if r["status"] == "PASS"]
    col = [r for r in sc if "SUSTAINMENT" in r["reasons"]]
    both = {rd: [r for r in rr if r["reading"] == rd and "CURRENT" in r["reasons"] and "THRUST" in r["reasons"]]
            for rd in READINGS}
    nc13 = {rd: [r for r in rr if r["reading"] == rd and r["point"] in T_POINTS and "SUSTAINMENT" not in r["reasons"]]
            for rd in READINGS}
    rr25 = [r for r in rr if r["point"] != "N1"]
    return {
        "candidates": cs,
        "runs_total": len(rA), "runs_scoreable": len(sc),
        "runs_scoreable_by_registration": {g: sum(r["registration"] == g for r in sc) for g in REGS},
        "runs_total_by_registration": {g: sum(r["registration"] == g for r in rA) for g in REGS},
        "runs_scoreable_by_point": {pt: sum(r["point"] == pt for r in sc) for pt in POINTS},
        "run_readings_scoreable": len(rr), "run_readings_pass": len(passes),
        "members_with_20_pass": sum(n == 20 for n in collections.Counter(
            (r["candidate"], r["member"]) for r in passes).values()),
        "run_readings_scoreable_N2_N5": len(rr25),
        "run_readings_pass_N2_N5": sum(r["status"] == "PASS" for r in rr25),
        "reasons_by_registration_run_readings": {g: {q: sum(q in r["reasons"] for r in rr if r["registration"] == g)
                                                     for q in REASONS} for g in REGS},
        "pass_locations": sorted({(f"{cshort(r['candidate'])} " if len(cs) > 1 else "") +
                                  f"{r['case']} {CHEM_SHORT[r['chemistry']]} ({r['reading']})" for r in passes}),
        "pass_points": [pt for pt in POINTS if any(r["point"] == pt for r in passes)],
        "current_failure_runs": len(cur), "current_failure_over": len(cur_over),
        "current_failure_by_point": {pt: over_under([r for r in cur if r["point"] == pt], "dI_rel") for pt in POINTS},
        "median_scoreable_dI_by_point": {pt: sig(median(r["dI_rel"] for r in sc if r["point"] == pt)) for pt in POINTS},
        "sustainment_runs": len(col),
        "sustainment_points": [pt for pt in POINTS if any(r["point"] == pt for r in col)],
        "current_and_thrust_failures_same_sign": {rd: [sum((r["dI_rel"] > 0) == (r["dT_mN"] > 0) for r in both[rd]),
                                                       len(both[rd])] for rd in READINGS},
        "ion_over_target_in_current_over_runs": desc(r["ion_over_target"] for r in cur_over),
        "ion_over_target_gt_1_in_current_over_runs": sum(r["ion_over_target"] > 1.0 for r in cur_over),
        "ion_over_target_gt_1p15_in_current_over_runs": sum(r["ion_over_target"] > 1.15 for r in cur_over),
        "ion_share_of_excess_in_current_over_runs": desc((r["ion_over_target"] - 1.0) / r["dI_rel"] for r in cur_over),
        "ion_over_target_in_pass_runs": desc(r["ion_over_target"] for r in
                                             {r["key"]: r for r in passes}.values()),
        "ion_over_target_gt_1_in_pass_runs": sum(r["ion_over_target"] > 1.0 for r in
                                                 {r["key"]: r for r in passes}.values()),
        "ion_over_discharge_scoreable": desc(r["ion_over_discharge"] for r in sc),
        "ion_over_N2_equivalent_in_current_over_runs": desc(r["ion_over_N2_equivalent"] for r in cur_over),
        "target_over_N2_equivalent": desc(r["target_over_N2_equivalent"] for r in rA),
        "thrust_per_current_ratio_non_collapsed_N1_N3": {rd: desc(r["thrust_per_current_ratio"] for r in nc13[rd])
                                                         for rd in READINGS},
        "abs_one_minus_thrust_per_current_ratio_non_collapsed_N1_N3": {
            rd: desc(abs(1.0 - r["thrust_per_current_ratio"]) for r in nc13[rd]) for rd in READINGS},
        "abs_dI_non_collapsed_N1_N3": {rd: desc(abs(r["dI_rel"]) for r in nc13[rd]) for rd in READINGS},
    }


def statements(f, label):
    """Evidence statements generated from the counts in f (no ranking, no recommendation, no verdict)."""
    s = []
    rs, rt = f["runs_scoreable"], f["runs_total"]
    reg = ", ".join(f"{g} {f['runs_scoreable_by_registration'][g]}/{f['runs_total_by_registration'][g]}" for g in REGS)
    s.append(f"Coverage: {pct(rs, rt)} runs are scoreable ({reg}).")
    zero_pts = [pt for pt in POINTS if f["runs_scoreable_by_point"][pt] == 0]
    if zero_pts:
        s.append(f"Not tested by the scoreable subset: {', '.join(zero_pts)} (no scoreable run there).")
    if f["run_readings_pass"]:
        full = ("They do not make up any complete member (20 of 20)" if f["members_with_20_pass"] == 0 else
                f"{f['members_with_20_pass']} (candidate, member) pairs have 20 of 20 PASS")
        s.append(f"PASS evidence: {f['run_readings_pass']} of {f['run_readings_scoreable']} scoreable run-readings are "
                 f"official PASS, at {', '.join(f['pass_points'])} only. {full}, and the official member verdicts are "
                 f"unchanged. At N2-N5, "
                 f"{f['run_readings_pass_N2_N5']} of {f['run_readings_scoreable_N2_N5']} scoreable run-readings are "
                 f"PASS.")
    else:
        s.append(f"PASS evidence: none. All {f['run_readings_scoreable']} scoreable run-readings are official "
                 f"FAIL_VALIDATION.")
    rbr = f["reasons_by_registration_run_readings"]
    s.append("Official failure reasons by registration (run-readings, CURRENT/THRUST/SUSTAINMENT): " + ", ".join(
        f"{g} {rbr[g]['CURRENT']}/{rbr[g]['THRUST']}/{rbr[g]['SUSTAINMENT']}" for g in REGS) + ".")
    cur = f["current_failure_by_point"]
    s.append("Current level: official CURRENT failures by point, as over/under-predicting runs: " +
             ", ".join(f"{pt} {cur[pt]['over']}/{cur[pt]['under']}" for pt in POINTS) +
             ". Median scoreable dI: " + ", ".join(f"{pt} {fmt(f['median_scoreable_dI_by_point'][pt])}"
                                                   for pt in POINTS) + ".")
    n25o = sum(cur[pt]["over"] for pt in POINTS[1:])
    n25u = sum(cur[pt]["under"] for pt in POINTS[1:])
    if n25o + n25u:
        if n25u == 0:
            s.append(f"At N2-N5 every official CURRENT failure ({n25o} runs) over-predicts I_d. The scoreable evidence "
                     f"does not support the modelled current level of {label} there, under the layer-1 members where "
                     f"it is scoreable.")
        elif n25o == 0:
            s.append(f"At N2-N5 every official CURRENT failure ({n25u} runs) under-predicts I_d.")
        else:
            s.append(f"At N2-N5, {n25o} of {n25o + n25u} official CURRENT failures "
                     f"({100.0 * n25o / (n25o + n25u):.0f} %) over-predict I_d and {n25u} under-predict it.")
    if f["sustainment_runs"]:
        s.append(f"Sustainment: {f['sustainment_runs']} of {rs} scoreable runs carry the official SUSTAINMENT reason "
                 f"(late collapse), at {', '.join(f['sustainment_points'])}. In these runs the modelled discharge is "
                 f"not sustained to the end of the 2 ms record, while sustainment is a pre-registered observable at "
                 f"N1-N5 (D1).")
    else:
        s.append(f"Sustainment: none of the {rs} scoreable runs carries the official SUSTAINMENT reason.")
    same = f["current_and_thrust_failures_same_sign"]
    if same["A"][1] or same["B"][1]:
        s.append(f"Thrust follows current: in runs that fail both CURRENT and THRUST, the residual signs agree in "
                 f"{same['A'][0]}/{same['A'][1]} (reading A) and {same['B'][0]}/{same['B'][1]} (reading B).")
    io, sh = f["ion_over_target_in_current_over_runs"], f["ion_share_of_excess_in_current_over_runs"]
    if io:
        s.append(f"Model-internal decomposition: take the {io['n']} CURRENT over-prediction runs. The model's "
                 f"time-averaged ion current at the downstream domain boundary alone is {io['min']:.2f}-{io['max']:.2f} x I_target (median "
                 f"{io['median']:.2f}). It exceeds I_target in {f['ion_over_target_gt_1_in_current_over_runs']} runs "
                 f"and 1.15 x I_target in {f['ion_over_target_gt_1p15_in_current_over_runs']}. The ion current carries "
                 f"a median {sh['median']:.2f} (range {sh['min']:.2f}-{sh['max']:.2f}) of the modelled excess "
                 f"I_d - I_target. Assume the standard current balance I_d = I_i + I_e with I_e >= 0 (assumed; verify "
                 f"for the P5 data reduction). Then a modelled ion current above I_target exceeds every ion current "
                 f"compatible with the reconstructed target I_d. Where that holds, the scoreable evidence does not "
                 f"support the modelled ion production level. No measured ion/electron split at N1-N5 is in the "
                 f"repository's audit.")
    ip = f["ion_over_target_in_pass_runs"]
    if ip:
        if ip["n"] == 1:
            head = f"in the single PASS run the modelled boundary ion current is {ip['median']:.2f} x I_target"
        else:
            head = (f"in the {ip['n']} distinct PASS runs the modelled boundary ion current is {ip['min']:.2f}-"
                    f"{ip['max']:.2f} x I_target (median {ip['median']:.2f}), above I_target in "
                    f"{f['ion_over_target_gt_1_in_pass_runs']}")
        s.append(f"PASS runs, same decomposition: {head}. Agreement of I_d within tolerance does not by itself show "
                 f"that the ion and electron current components agree; neither component is measured.")
    return s


def family_statements(f):
    """Additional family-level statements on current composition and thrust per ampere (model-internal)."""
    iod, i2 = f["ion_over_discharge_scoreable"], f["ion_over_N2_equivalent_in_current_over_runs"]
    t2 = f["target_over_N2_equivalent"]
    s = [f"Model current composition: across the scoreable runs, the time-averaged boundary ion current is "
         f"{iod['min']:.2f}-{iod['max']:.2f} of the window-mean I_d (median {iod['median']:.2f}). In the CURRENT "
         f"over-prediction runs it is {i2['min']:.2f}-{i2['max']:.2f} x the N2-equivalent flow current "
         f"e*mdot_anode/m_N2 (median {i2['median']:.2f}). The reconstructed target I_d (Eq. 14 corrected, level 3) is "
         f"{t2['min']:.2f}-{t2['max']:.2f} x that current (mdot_anode measured, Brabston 2025 Table 2). Inferred from "
         f"mass conservation (time average, steady anode throughput; one N2 molecule yields at most one singly charged "
         f"N2+): a modelled ion current above 1 x e*mdot_anode/m_N2 requires dissociation or multiple ionisation in "
         f"the model."]
    tpc = f["thrust_per_current_ratio_non_collapsed_N1_N3"]
    dev, adI = f["abs_one_minus_thrust_per_current_ratio_non_collapsed_N1_N3"], f["abs_dI_non_collapsed_N1_N3"]
    s.append(f"Thrust per ampere: take the ratio (T_axial/I_d)_model / (T_corr/I_d,corr)_target in the non-collapsed "
             f"scoreable runs at N1-N3 (targets: the frozen measurement audit). Its median is "
             f"{tpc['A']['median']:.3f} under reading A (range {tpc['A']['min']:.3f}-{tpc['A']['max']:.3f}) and "
             f"{tpc['B']['median']:.3f} under reading B (range {tpc['B']['min']:.3f}-"
             f"{tpc['B']['max']:.3f}). The median |1 - ratio| is {dev['A']['median']:.3f} (A) and "
             f"{dev['B']['median']:.3f} (B). Over the same run-readings the median |dI| is {adI['A']['median']:.3f} (A) "
             f"and {adI['B']['median']:.3f} (B). In the scoreable subset the thrust residual therefore mostly tracks "
             f"the current residual; the per-ampere mismatch is smaller than the current mismatch.")
    return s


def cross_candidate_statements(s3, cands):
    rho = s3["spearman_rho"]
    ct, sm = s3["candidate_parameters_and_xe_metrics"], s3["candidate_n2_scoreable_summaries"]
    n_xe2_neg = sum(ct[c]["xe_dI_pct_Xe1_Xe2_Xe3"][1] < 0 for c in cands)
    n_n25_pos = sum((sm[c]["median_dI_N2_N5"] or 0) > 0 for c in cands)
    r_xe2 = rho["xe_dI_pct_Xe2"]["median_dI_all_points"]["rho"]
    r_xe3 = rho["xe_dI_pct_Xe3"]["median_dI_all_points"]["rho"]
    r_bw = rho["derived_trough_deficit_b_times_w"]["median_dI_all_points"]["rho"]
    r_bw_xe = s3["parameter_intercorrelation_spearman_rho"]["derived_trough_deficit_b_times_w"][
        "xe_in_sample_max_abs_dI_pct"]
    r_b = rho["b_barrier_scale"]["median_dI_all_points"]["rho"]
    r_w = rho["w_width_L"]["median_dI_all_points"]["rho"]
    r_c = rho["c_center_L"]["median_dI_all_points"]["rho"]
    head = f"Xe-to-N2 ordering ({N9_CAVEAT.split(':')[0]}): across the {len(cands)} candidates"
    if min(r_xe2, r_xe3) >= 0.8:           # descriptive threshold for the wording only; nothing is tested
        xe = (f"{head}, the rank order of the N2 scoreable median dI follows the rank order of the recorded Xe "
              f"in-sample dI (Spearman rho {r_xe2:+.2f} with Xe2, {r_xe3:+.2f} with Xe3).")
        tail = " The N2 ordering is therefore not independent of the Xe screening ordering."
    else:
        xe = (f"{head}, the Spearman rho of the N2 scoreable median dI with the recorded Xe in-sample dI is "
              f"{r_xe2:+.2f} (Xe2) and {r_xe3:+.2f} (Xe3).")
        tail = ""
    xe += (f" The recorded Xe2 dI is negative for {n_xe2_neg} of {len(cands)} candidates. The N2 scoreable median dI "
           f"at N2-N5 is positive for {n_n25_pos} of {len(cands)}.")
    if n_xe2_neg == len(cands) and n_n25_pos >= len(cands) - 1 and min(r_xe2, r_xe3) >= 0.8:
        xe += (" So the between-candidate ordering carries over from Xe to N2 while the level moves from under- to "
               "over-prediction.")
    xe += tail
    tp = (f"Transport parameters (same caveat): the N2 scoreable median dI has rank correlation {r_b:+.2f} with b, "
          f"{r_c:+.2f} with c and {r_w:+.2f} with w. With the derived trough deficit b*w (chosen post hoc, descriptive) "
          f"it is {r_bw:+.2f}, and b*w also ranks with the Xe in-sample max abs dI ({r_bw_xe:+.2f}).")
    if r_bw < 0:
        tp += (" The sign is the one expected from the model form, where a larger low-transport trough lowers the "
               "anomalous inverse Hall parameter over a wider region and so lowers the modelled current.")
    tp += (" This describes how the model responds. It is not evidence that any parameter value is physically correct, "
           "and because the parameters co-vary it cannot be attributed to b*w alone.")
    a_vals = s3["a_anom_scale"]["values"]
    a_st = (f"a = {a_vals[0]:g} (1/16) for every candidate, so the scoreable subset carries no information on the "
            f"anomalous-transport scale a itself." if a_vals == [0.0625] else
            f"a takes the values {a_vals} across the candidates (see section 3).")
    return [xe, tp, a_st]


def section6(rows, runs_A, cands, ctab, s3):
    fam = collections.defaultdict(list)
    for c in cands:
        fam[ctab[c]["transport_family"]].append(c)
    grp = collections.defaultdict(list)
    for c in cands:
        grp[(ctab[c]["b_barrier_scale"], ctab[c]["w_width_L"])].append(c)
    out = {"phrasing": ("evidence statements only (what the scoreable subset shows / does not show / does not test); no "
                        "ranking, no recommendation, no admission, no re-scoring"),
           "families": {}, "cross_candidate": cross_candidate_statements(s3, cands), "parameter_groups": {},
           "emphasis_candidates": {}}
    for name, cs in sorted(fam.items()):
        f = group_facts(rows, runs_A, cs)
        out["families"][name] = {"facts": f, "statements": statements(f, f"the {name} screening set") +
                                 family_statements(f)}
    for (b, w), cs in sorted(grp.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        lab = f"b={b:g}, w={w:g} L"
        f = group_facts(rows, runs_A, cs)
        out["parameter_groups"][lab] = {"facts": f, "statements": statements(f, f"the '{lab}' group")}
    for c in EMPHASIS:
        f = group_facts(rows, runs_A, [c])
        out["emphasis_candidates"][c] = {"facts": f, "statements": statements(f, c)}
    return out


# ----------------------------------------------------------------------------------------------------------------- build
def build():
    inp = load_inputs()
    rows = build_rows(inp)
    cands = sorted({r["candidate"] for r in rows})
    chems = list(inp["criteria"]["mandatory_chemistry"])
    members = sorted({r["member"] for r in rows})
    runs_A = [r for r in rows if r["reading"] == "A"]
    sA = {r["key"]: r["scoreable"] for r in runs_A}     # scoreability must be reading-independent for run-level views
    if any(sA[r["key"]] != r["scoreable"] for r in rows):
        raise SystemExit("scoreability differs between readings")
    ctab = candidate_table(inp["ensemble"], inp["xe_hypotheses"])
    if sorted(ctab) != cands:
        raise SystemExit("screening candidates in the ensemble differ from the scored candidates")
    s1 = section1(rows, inp, cands, members, chems)
    official = inp["scores"]["status_counts"]["vacuum"]
    reconcile = {s: {"this_analysis": s1["totals"][s], "official_scores_file": official.get(s, 0)} for s in STATUSES}
    if any(v["this_analysis"] != v["official_scores_file"] for v in reconcile.values()):
        raise SystemExit(f"status totals do not reconcile with the official counts: {reconcile}")
    status_change = sorted(k[0] for k, sts in group(rows, "key").items() if len({r["status"] for r in sts}) > 1)
    s3 = section3(rows, runs_A, cands, ctab)
    doc = {
        "id": "p5_n2_v1_scoreable_subset_forensics",
        "role": ("descriptive, NON-GATING forensics of the scoreable run-readings (official PASS + FAIL_VALIDATION) of the "
                 "frozen P5-N2 v1 vacuum campaign; never an input to admission, a verdict, a criterion or a model change"),
        "generator": "scripts/forensics/p5_n2_v1_scoreable_subset.py",
        "official_outcome_unchanged": {
            "candidate_verdicts": inp["decision"]["candidates"],
            "credible_set": "empty (CLAUDE.md, project decision 2026-09-26)",
            "gate_3": "FAIL",
            "statement": "the v1 outcome is final; this analysis reads official statuses and reasons and changes none",
        },
        "inputs": {k: {"file": v, "sha256": inp["hashes"][k]} for k, v in REL.items()},
        "input_checks": inp["checks"],
        "evidence_classes": {
            "official statuses, reasons, member and candidate verdicts": "official frozen scorer output, read (not "
                                                                        "recomputed)",
            "dI_rel": "model-derived residual (HallThruster.jl window-mean I_d, pinned bfb3019) against a level-3 "
                      "reconstructed target (Brabston 2025 Table 2 P_d/V_d with the Eq. 14 correction, frozen audit)",
            "dT_mN": "model-derived (T_1D x axial factor, the factor being paper-reconstructed + digitized, readings A/B) "
                     "minus a level-3 reconstructed (N1) or digitized + reconstructed (N2, N3) corrected thrust",
            "I_d time statistics, T_e max, ion current": "model-derived (bridge outputs in the frozen raw dataset; the "
                                                         "ion current is taken at the downstream domain boundary)",
            "ion-current bound e*mdot_anode/m_N2 and the I_d = I_i + I_e reading": "inferred (mass / current "
                                                                                   "conservation; I_e >= 0 assumed)",
            "anode mass flow for the N2-equivalent current": "measured (Brabston 2025 Table 2 via cases/p5_n2.json)",
            "transport parameters a, b, c, w": "assumed model form (EVIDENCE.md level 7) with screening parameters "
                                              "(transport_ensemble_v0.json screening_candidates)",
            "Xe screening metrics": "model-derived in-sample residuals of the P5-Xe identification grid, as recorded in "
                                    "transport_ensemble_v0.json evidence_basis",
            "counts, quantiles, rank correlations, derived trough quantities": "computed here (descriptive statistics)",
        },
        "totals_reconciliation": {
            "status_run_readings": reconcile,
            "reasons_run_readings": {q: s1["totals"][q] for q in REASONS},
            "scoreable_run_readings": s1["totals"]["scoreable"],
            "runs": len(runs_A), "scoreable_runs": sum(r["scoreable"] for r in runs_A),
            "runs_whose_status_differs_between_readings": status_change,
        },
        "tolerances_for_context_only": {
            "discharge_current_rel": 0.15,
            "thrust_mN": inp["criteria"]["D3_tolerances"]["thrust_mN"],
            "source": "prereg/p5_n2_validation_criteria_v1.json D3 (shown for context; never re-applied here)",
        },
        "chemistry_short_names": {ch: CHEM_SHORT[ch] for ch in chems},
        "s1_coverage": s1,
        "s2_residuals": section2(rows, runs_A, cands),
        "s3_transport_parameter_relations": s3,
        "s4_member_coverage": section4(rows, inp, cands, members, chems),
        "s5_sustainment_collapse": section5(rows, runs_A, cands, chems),
        "s6_evidence_statements": section6(rows, runs_A, cands, ctab, s3),
        "limits": [
            f"Selection: the scoreable subset ({s1['totals']['scoreable']} of {s1['totals']['n']} run-readings; "
            f"{sum(r['scoreable'] for r in runs_A)} of {len(runs_A)} runs) is not a random sample. It is the part of the "
            "campaign whose chemistry stayed inside the validity limits. OUT_OF_DOMAIN runs are not scored and are used "
            "here only where labelled 'context'.",
            f"n = {len(cands)} candidates for any cross-candidate relation; parameters co-vary by construction of the "
            "Xe screen.",
            f"Every modelled discharge in the scoreable subset oscillates strongly: the smallest Id_rms_rel of a "
            f"scoreable run is {min(r['Id_rms_rel'] for r in runs_A if r['scoreable']):.2f}. dI_rel is a 1-2 ms window "
            "mean, as pre-registered.",
            "No measured ion-current / electron-current split, oscillation amplitude or time-resolved I_d at N1-N5 is "
            "in the repository's measurement audit (TBD - requires a published measurement of these at the P5-N2 "
            "points).",
            "The O4 staged sensitivities and the facility-mode runs are not part of this analysis.",
        ],
    }
    return doc


def dumps(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------------------------------------------- render
def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return out


def tcell(t, with_reasons=True):
    s = f"{t['scoreable']}/{t['n']}: {t['PASS']}P {t['FAIL_VALIDATION']}F"
    if with_reasons and t["FAIL_VALIDATION"]:
        s += f" (C{t['CURRENT']} T{t['THRUST']} S{t['SUSTAINMENT']})"
    return s


def dcell(d, k=3):
    if d is None:
        return "—"
    return f"{d['n']}: {d['min']:+.{k}f} / {d['median']:+.{k}f} / {d['max']:+.{k}f}"


def dcell5(d, k=3):
    if d is None:
        return "—"
    return (f"{d['n']}: {d['min']:+.{k}f} / {d['p25']:+.{k}f} / {d['median']:+.{k}f} / {d['p75']:+.{k}f} / "
            f"{d['max']:+.{k}f}, {100 * d['frac_positive']:.0f} % > 0")


def render(doc):
    s1, s2, s3 = doc["s1_coverage"], doc["s2_residuals"], doc["s3_transport_parameter_relations"]
    s4, s5, s6 = doc["s4_member_coverage"], doc["s5_sustainment_collapse"], doc["s6_evidence_statements"]
    cands = list(s1["by_candidate"])
    members = list(next(iter(s1["by_candidate_member"].values())))
    chems = list(doc["chemistry_short_names"])
    tr = doc["totals_reconciliation"]
    L = ["# P5-N₂ v1 vacuum campaign: scoreable-subset forensics (descriptive, non-gating)", "",
         "> **Status.** This is a descriptive, **non-gating** analysis of the scoreable run-readings of the frozen "
         "P5-N₂ v1 "
         "vacuum campaign (official PASS + FAIL_VALIDATION). The official v1 outcome is final and unchanged: all 9 "
         "screening candidates are **INCONCLUSIVE / NOT ELIGIBLE**, the credible set is **∅** and gate 3 is **FAIL**. "
         "Every run status and failure reason below is read from the official scores file and none is recomputed. "
         "Nothing here re-scores or re-labels a run. Nothing here proposes a change to transport, chemistry, criteria, "
         "tolerances or validity limits.", "",
         f"Generated by `{doc['generator']}`. The machine-readable numbers are in `scoreable_subset.json`. To rebuild, run "
         "`python scripts/forensics/p5_n2_v1_scoreable_subset.py`, or add `--check` to verify the committed files.", "",
         "## 0. Inputs, units and evidence classes", ""]
    L += md_table(["input", "sha256 (verified)"], [[f"`{v['file']}`", f"`{v['sha256'][:16]}…`"]
                                                  for v in doc["inputs"].values()])
    L += ["", "Hash checks: " + ", ".join(f"{k} = {v}" for k, v in doc["input_checks"].items()) + ".", "",
          "- **Unit:** one *run-reading* is one run under one divergence reading (A or B), as in the official report "
          "(1080 runs × 2 = 2160). CURRENT, SUSTAINMENT and OUT_OF_DOMAIN do not depend on the reading. Where a quantity "
          "is reading-independent (dI, SUSTAINMENT, time statistics), each run is counted once and the table says *runs*.",
          "- **Scoreable** means official status PASS or FAIL_VALIDATION. There are no NUMERICAL_FAILURE runs.",
          "- **Tolerances**, shown for context only and never re-applied: |dI| ≤ 0.15, |dT| ≤ 5.2 / 5.6 / 5.6 mN at "
          "N1 / N2 / N3 (pre-registration D3).",
          "- **Chemistry short names:** " + ", ".join(f"`{k}` = {v}" for k, v in doc["chemistry_short_names"].items())
          + ".", ""]
    L += md_table(["quantity", "evidence class / source"], [[k, v] for k, v in doc["evidence_classes"].items()])

    # ---- 1
    t = s1["totals"]
    L += ["", "## 1. Scoreable coverage, official statuses and reasons", "",
          f"**Totals reconcile with the official counts.** PASS {t['PASS']}, FAIL_VALIDATION {t['FAIL_VALIDATION']}, "
          f"OUT_OF_DOMAIN {t['OUT_OF_DOMAIN']}, NUMERICAL_FAILURE {t['NUMERICAL_FAILURE']}. Reasons: CURRENT "
          f"{t['CURRENT']}, THRUST {t['THRUST']}, SUSTAINMENT {t['SUSTAINMENT']}. That gives {t['scoreable']} scoreable "
          f"run-readings, or {tr['scoreable_runs']} of {tr['runs']} runs. The runs whose status differs between readings "
          f"are {len(tr['runs_whose_status_differs_between_readings'])}: "
          + ", ".join(f"`{k}`" for k in tr["runs_whose_status_differs_between_readings"]) + ".", "",
          "### 1.1 By candidate (run-readings)", ""]
    L += md_table(["candidate", "scoreable / 240", "PASS", "FAIL_VALIDATION", "OUT_OF_DOMAIN", "CURRENT", "THRUST",
                   "SUSTAINMENT"],
                  [[c, v["scoreable"], v["PASS"], v["FAIL_VALIDATION"], v["OUT_OF_DOMAIN"], v["CURRENT"], v["THRUST"],
                    v["SUSTAINMENT"]] for c, v in s1["by_candidate"].items()])
    L += ["", "### 1.2 Candidate × point (run-readings; the cell reads `scoreable/48: PASS, FAIL (reasons)`)", ""]
    L += md_table(["candidate"] + POINTS, [[c] + [tcell(s1["by_candidate_point"][c][pt]) for pt in POINTS]
                                           for c in cands])
    L += ["", "### 1.3 Candidate × chemistry (run-readings; the cell reads `scoreable/60: PASS, FAIL (reasons)`)", ""]
    L += md_table(["candidate"] + [CHEM_SHORT[ch] for ch in chems],
                  [[c] + [tcell(s1["by_candidate_chemistry"][c][ch]) for ch in chems] for c in cands])
    L += ["", "### 1.4 Pooled by point, chemistry, registration and coil (run-readings)", ""]
    pooled = ([["point " + k, tcell(v)] for k, v in s1["by_point"].items()] +
              [["chemistry " + CHEM_SHORT[k], tcell(v)] for k, v in s1["by_chemistry"].items()] +
              [["registration " + k, tcell(v)] for k, v in s1["by_registration"].items()] +
              [["coil " + k, tcell(v)] for k, v in s1["by_coil"].items()])
    L += md_table(["group", "scoreable/n: PASS, FAIL (reasons)"], pooled)
    L += ["", "### 1.5 Full grids for the emphasis candidates sgb-screen-05 … 09", "",
          "Each cell holds the four mandatory chemistries in the order " + " / ".join(CHEM_SHORT[ch] for ch in chems) +
          ". Codes: `P` is PASS; `C`, `T` and `S` are FAIL_VALIDATION with the official reasons CURRENT, THRUST and "
          "SUSTAINMENT; `·` is OUT_OF_DOMAIN (not scoreable). The last column is the official member verdict.", ""]
    for c in EMPHASIS:
        L += grid_md(s1, c, members, chems)
    L += ["", "The grids for sgb-screen-01 … 04 are in Appendix A.", ""]

    # ---- 2
    L += ["## 2. Signed residuals of the scoreable subset", "", s2["unit_note"], "",
          "### 2.1 dI = (I_d − I_target)/I_target by official status (run-readings)", "",
          "Each cell reads `n: min / p25 / median / p75 / max, share > 0`.", ""]
    rows_ = []
    for rd in READINGS:
        for pt in POINTS + ["pooled"]:
            rows_.append([rd, pt, dcell5(s2["dI_rel_by_reading_status_point"][rd]["PASS"][pt]),
                          dcell5(s2["dI_rel_by_reading_status_point"][rd]["FAIL_VALIDATION"][pt])])
    L += md_table(["reading", "point", "PASS dI", "FAIL_VALIDATION dI"], rows_)
    L += ["", "### 2.2 dT [mN] at N1–N3 by official status (run-readings)", ""]
    rows_ = []
    for rd in READINGS:
        for pt in T_POINTS:
            rows_.append([rd, pt, doc["tolerances_for_context_only"]["thrust_mN"][pt],
                          dcell5(s2["dT_mN_by_reading_status_point"][rd]["PASS"][pt], 2),
                          dcell5(s2["dT_mN_by_reading_status_point"][rd]["FAIL_VALIDATION"][pt], 2)])
    L += md_table(["reading", "point", "tolerance", "PASS dT", "FAIL_VALIDATION dT"], rows_)
    L += ["", "### 2.3 Per candidate × point (scoreable runs)", "",
          "dI cells read `runs: min / median / max`. dT cells give the median under readings A / B. A dash means no "
          "scoreable run.", ""]
    rows_ = []
    for c in cands:
        e = s2["by_candidate_point"][c]
        rows_.append([c] + [dcell(e[pt]["dI_rel"]) for pt in POINTS] +
                     [("—" if e[pt]["dT_mN_A"] is None else
                       f"{e[pt]['dT_mN_A']['median']:+.1f} / {e[pt]['dT_mN_B']['median']:+.1f}") for pt in T_POINTS])
    L += md_table(["candidate"] + [f"dI {pt}" for pt in POINTS] + [f"dT {pt} A/B" for pt in T_POINTS], rows_)
    sp = s2["sign_patterns"]
    L += ["", "### 2.4 Systematic sign patterns", "",
          "Official CURRENT failures, counted in runs, as `over/under`, meaning dI > 0 / dI < 0:", ""]
    L += md_table(["candidate"] + POINTS,
                  [[c] + [f"{v[pt]['over']}/{v[pt]['under']}" for pt in POINTS]
                   for c, v in sp["current_failures_by_candidate_point"].items()] +
                  [["**all**"] + [f"**{sp['current_failures_by_point'][pt]['over']}/"
                                  f"{sp['current_failures_by_point'][pt]['under']}**" for pt in POINTS]])
    L += ["", "By registration:", ""]
    L += md_table(["registration"] + POINTS,
                  [[g] + [f"{v[pt]['over']}/{v[pt]['under']}" for pt in POINTS]
                   for g, v in sp["current_failures_by_registration_point"].items()])
    n25 = sp["current_failures_N2_N5"]
    L += ["", f"- **Current at N2–N5:** {n25['over']} of {n25['n']} CURRENT-failing runs over-predict I_d "
              f"({100 * n25['over'] / n25['n']:.1f} %); {n25['under']} under-predict.",
          f"- **Current at N1:** {sp['current_failures_by_point']['N1']['over']} over and "
          f"{sp['current_failures_by_point']['N1']['under']} under. The sign splits by registration, as the table "
          "above shows."]
    for rd in READINGS:
        th = sp["thrust_failures_run_readings"][rd]
        L.append(f"- **THRUST failures, reading {rd}:** {th['total']['over']} over and {th['total']['under']} under "
                 f"(by point: " + ", ".join(f"{pt} {th['by_point'][pt]['over']}/{th['by_point'][pt]['under']}"
                                             for pt in T_POINTS) +
                 f"). {th['thrust_without_current']} of them fail without CURRENT, and {th['thrust_only_failures']} "
                 f"fail on THRUST alone. In runs that fail both, the signs agree in "
                 f"{th['current_and_thrust_same_sign']['same_sign']}/{th['current_and_thrust_same_sign']['n']}.")
    corr = sp["dI_dT_correlation_scoreable"]
    L.append("- **dI–dT correlation over the scoreable runs** (Pearson / Spearman): " + "; ".join(
        f"{rd} " + ", ".join(f"{pt} {corr[rd][pt]['pearson']:.3f} / {corr[rd][pt]['spearman']:.3f} "
                             f"(n {corr[rd][pt]['n']})" for pt in T_POINTS) for rd in READINGS) + ".")
    L.append("- **Share of scoreable runs with dI > 0:** " + ", ".join(
        f"{pt} {100 * sp['scoreable_dI_positive_share_by_point'][pt]['frac_positive']:.0f} % "
        f"(n {sp['scoreable_dI_positive_share_by_point'][pt]['n']})" for pt in POINTS) + ".")
    st = s2["structure"]
    cs_ = st["coil_paired_dI_shift_3p0_minus_1p6"]
    ch_ = st["chemistry_pairs_both_scoreable"]
    L += ["", "### 2.5 Structure by registration, coil and chemistry", "",
          "Scoreable dI by registration × point (`runs: min / median / max`):", ""]
    L += md_table(["registration"] + POINTS, [[g] + [dcell(v[pt]) for pt in POINTS]
                                               for g, v in st["dI_rel_by_registration_point"].items()])
    L += ["",
          f"- **Paired coil shift** dI(3.0 kW) − dI(1.6 kW), at the same candidate, chemistry, registration and point. "
          f"Both scoreable: n {cs_['both_scoreable']['n']}, median {cs_['both_scoreable']['median']:+.3f}, "
          f"{100 * cs_['both_scoreable']['frac_positive']:.0f} % > 0. As context, over all numerically valid pairs "
          f"including OOD: n {cs_['context_all_numerically_valid_incl_OOD']['n']}, median "
          f"{cs_['context_all_numerically_valid_incl_OOD']['median']:+.3f}.",
          f"- **Chemistry.** Take pairs of chemistries that are both scoreable at the same candidate, case and reading "
          f"({ch_['pairs']} pairs). They have the same official status in {ch_['same_official_status']} and the same "
          f"official reasons in {ch_['same_official_reasons']}. Where all four chemistries are scoreable, the dI range "
          f"across them has median "
          f"{ch_['dI_range_across_4_chemistries_all_scoreable_groups']['median']:.4f} and max "
          f"{ch_['dI_range_across_4_chemistries_all_scoreable_groups']['max']:.4f} "
          f"(n {ch_['dI_range_across_4_chemistries_all_scoreable_groups']['n']} groups).", ""]

    # ---- 3
    L += ["## 3. Relation to the transport parameters and the Xe screening metrics", "",
          f"> **Caveat.** {s3['caveat']}", "",
          s3["parameter_definition"] + f" a = {s3['a_anom_scale']['values']}: {s3['a_anom_scale']['note']}.", "",
          "### 3.1 Parameters, Xe screening metrics (as recorded) and N₂ scoreable summaries", ""]
    ct, sm = s3["candidate_parameters_and_xe_metrics"], s3["candidate_n2_scoreable_summaries"]
    rows_ = []
    for c in cands:
        x, y = ct[c], sm[c]
        rows_.append([cshort(c), x["b_barrier_scale"], x["c_center_L"], x["w_width_L"],
                      x["derived_trough_deficit_b_times_w"], x["xe_in_sample_max_abs_dI_pct"],
                      " / ".join(f"{v:+.1f}" for v in x["xe_dI_pct_Xe1_Xe2_Xe3"]), f"{x['xe_Id_rms_rel_mean']:.3f}",
                      x["xe_n_layer1_combinations_passing_screen"], f"{y['runs_scoreable']}/{y['runs_total']}",
                      fmt(y["median_dI_N1"]), fmt(y["median_dI_N2_N5"]), fmt(y["median_dT_N1_N3_A"], 1),
                      fmt(y["median_dT_N1_N3_B"], 1), fmt(y["pass_share_run_readings"], 3, False),
                      fmt(y["sustainment_share_runs"], 3, False),
                      fmt(y["context_median_dI_all_numerically_valid_incl_OOD"])])
    L += md_table(["cand", "b", "c [L]", "w [L]", "b·w", "Xe max abs dI %", "Xe dI % Xe1/2/3", "Xe RMS mean",
                   "Xe layer-1 combos", "N₂ scoreable runs", "med dI N1", "med dI N2–N5", "med dT A", "med dT B",
                   "PASS share", "SUST share", "context: med dI all valid (incl. OOD)"], rows_)
    L += ["", "The Xe columns come from `transport_ensemble_v0.json` `evidence_basis`, the in-sample Xe residuals under "
          "the recorded hypothesis: " + "; ".join(f"{cshort(c)} {ct[c]['xe_in_sample_hypothesis']}" for c in cands)
          + ". *Xe layer-1 combos* counts the recorded `calibration_hypotheses`.", "",
          "### 3.2 Spearman ρ over the candidates (n shown when < 9)", ""]
    ys = ["median_dI_all_points", "median_dI_N1", "median_dI_N2_N5", "median_dT_N1_N3_A", "median_dT_N1_N3_B",
          "pass_share_run_readings", "sustainment_share_runs", "coverage_share",
          "context_median_dI_all_numerically_valid_incl_OOD"]
    yl = ["dI all", "dI N1", "dI N2–N5", "dT A", "dT B", "PASS share", "SUST share", "coverage", "ctx dI (incl. OOD)"]
    rows_ = []
    for x, v in s3["spearman_rho"].items():
        rows_.append([x] + [("—" if v[y]["rho"] is None else f"{v[y]['rho']:+.2f}" +
                             (f" (n {v[y]['n']})" if v[y]["n"] < 9 else "")) for y in ys])
    L += md_table(["x \\ y (N₂ scoreable summary)"] + yl, rows_)
    L += ["", "### 3.3 Rank intercorrelation of the candidate descriptors (confounding)", ""]
    xs = list(s3["parameter_intercorrelation_spearman_rho"])
    short = {"b_barrier_scale": "b", "c_center_L": "c", "w_width_L": "w", "derived_trough_deficit_b_times_w": "b·w",
             "xe_in_sample_max_abs_dI_pct": "Xe max", "xe_dI_pct_Xe1": "Xe1", "xe_dI_pct_Xe2": "Xe2",
             "xe_dI_pct_Xe3": "Xe3", "xe_Id_rms_rel_mean": "Xe RMS", "xe_n_layer1_combinations_passing_screen": "Xe L1"}
    L += md_table([""] + [short[x] for x in xs],
                  [[short[x1]] + [("—" if s3["parameter_intercorrelation_spearman_rho"][x1][x2] is None else
                                   f"{s3['parameter_intercorrelation_spearman_rho'][x1][x2]:+.2f}") for x2 in xs]
                   for x1 in xs])
    L += ["", "How to read these rank correlations: they describe the order of the 9 screening candidates. They say "
          "nothing about a mechanism or about any candidate outside this set. The descriptors are strongly "
          "intercorrelated, as 3.3 shows, so no relation can be assigned to one parameter. The scoreable summaries are "
          "computed on different subsets of layer-1 members and points for each candidate; the coverage column of 3.1 "
          "shows this.", ""]

    # ---- 4
    L += [f"## 4. Scoreable coverage per (candidate, layer-1 member): {s4['label']}", "",
          s4["definition"][0].upper() + s4["definition"][1:], "",
          "Columns: scoreable run-readings of 20, PASS and FAIL_VALIDATION counts, the points and chemistries with at "
          "least one scoreable run, whether every scoreable run-reading is PASS, and the official member verdict.", ""]
    rows_ = []
    for c in cands:
        for m in members:
            v = s4["members"][c][m]
            rows_.append([cshort(c), esc(m), f"{v['n_scoreable']}/20", v["n_pass"], v["n_fail_validation"],
                          ",".join(v["points_scoreable"]) or "—",
                          ",".join(CHEM_SHORT[ch] for ch in v["chemistries_scoreable"]) or "—",
                          {True: "yes", False: "no", None: "— (none scoreable)"}[v["all_scoreable_pass"]],
                          v["official_member_verdict"]])
    L += md_table(["cand", "member", "scoreable", "PASS", "FAIL", "points", "chemistries", "all scoreable PASS?",
                   "official verdict"], rows_)
    L += ["", f"**Members whose scoreable run-readings are all PASS** ({COVERAGE_LABEL}):", ""]
    for e in s4["members_with_all_scoreable_pass"]:
        pl = "point" if len(e["points_scoreable"]) == 1 else "points"
        L.append(f"- {e['candidate']} `{e['member']}`: {e['n_scoreable_of_20']} of 20 run-readings scoreable "
                 f"({pl} {', '.join(e['points_scoreable'])}), official verdict **{e['official_member_verdict']}**.")
    n20 = sum(v["n_pass"] == 20 for c in cands for v in s4["members"][c].values())
    L += ["", f"Under O3 a member is PASS only if all 20 of its runs are PASS. The number of (candidate, member) pairs "
              f"with 20 PASS run-readings is {n20}. The official verdicts stand as published.", ""]

    # ---- 5
    L += ["## 5. Sustainment-collapse runs (official SUSTAINMENT reason)", "", "Unit: " + s5["unit"] + ".", "",
          f"There are {s5['n_runs']} runs ({s5['n_run_readings']} run-readings) among {s5['scoreable_runs']} scoreable "
          "runs.", ""]
    L += md_table(["candidate", "SUSTAINMENT / scoreable runs"] + POINTS,
                  [[c, f"{v['sustainment']}/{v['scoreable']}"] + [s5["by_candidate_point"][c][pt] for pt in POINTS]
                   for c, v in s5["by_candidate"].items()])
    L += ["", "- **By point** (SUSTAINMENT / scoreable): " + ", ".join(
        f"{k} {v['sustainment']}/{v['scoreable']}" for k, v in s5["by_point"].items()) + ".",
          "- **By registration:** " + ", ".join(f"{k} {v['sustainment']}/{v['scoreable']}"
                                                for k, v in s5["by_registration"].items()) + ".",
          "- **By coil:** " + ", ".join(f"{k} {v['sustainment']}/{v['scoreable']}" for k, v in s5["by_coil"].items())
          + ".",
          "- **By chemistry:** " + ", ".join(f"{k} {v['sustainment']}/{v['scoreable']}"
                                             for k, v in s5["by_chemistry"].items()) + ".",
          "- **Co-reasons** (run-readings): " + "; ".join(
              f"reading {rd}: " + ", ".join(f"{k} {v}" for k, v in s5["co_reasons_run_readings"][rd].items())
              for rd in READINGS) + ".",
          f"- **Window-mean dI of the collapsed runs:** {s5['window_mean_dI_bands_collapsed']['above_plus_0.15']} above "
          f"+0.15, {s5['window_mean_dI_bands_collapsed']['within_0.15']} within ±0.15 and "
          f"{s5['window_mean_dI_bands_collapsed']['below_minus_0.15']} below −0.15. So a collapse at the end of the "
          "record is not tied to one sign of the 1–2 ms mean current.", "",
          "Where the collapses fall for the emphasis candidates (registration|coil: points):", ""]
    for c in EMPHASIS:
        locs = [f"{k}: {','.join(v)}" for k, v in s5["by_candidate_member_point"][c].items() if v]
        L.append(f"- {c}: " + ("; ".join(locs) if locs else "none"))
    L += ["", "I_d statistics, collapsed vs non-collapsed scoreable runs. Each cell reads "
          "`n: min / p25 / median / p75 / max`:", ""]
    rows_ = []
    for f in ID_FIELDS:
        a, b = s5["Id_statistics"]["collapsed"][f], s5["Id_statistics"]["scoreable_not_collapsed"][f]
        k = 3 if f not in ("final10_mean_over_target",) else 6
        rows_.append([f, dstats(a, k), dstats(b, k)])
    L += md_table(["quantity", "collapsed (SUSTAINMENT)", "scoreable, not collapsed"], rows_)
    L += ["", "Field definitions: " + "; ".join(f"`{k}`: {v}" for k, v in s5["Id_field_definitions"].items()) + ".", ""]
    if s5["chemistry_split_groups"]:
        L += ["**(Candidate, case) groups where scoreable chemistries split on SUSTAINMENT:**", ""]
        for e in s5["chemistry_split_groups"]:
            L.append(f"- {e['candidate']} `{e['case']}`: collapsed under {', '.join(e['collapsed'])}; not collapsed "
                     f"under {', '.join(e['not_collapsed'])}" +
                     (f"; OOD under {', '.join(e['not_scoreable'])}" if e["not_scoreable"] else "") + ".")
        L.append("")

    # ---- 6
    L += ["## 6. Evidence statements by transport family and parameter group", "",
          f"Phrasing: {s6['phrasing']}. Each statement is generated from the counts in the JSON. *Model-internal "
          "decomposition* statements describe the model output only.", ""]
    for name, v in s6["families"].items():
        L += [f"### 6.1 Family: {name} (all {len(v['facts']['candidates'])} screening candidates)", ""]
        L += [f"- {x}" for x in v["statements"]] + [""]
    L += ["**Across candidates** (n = 9, descriptive; section 3):", ""]
    L += [f"- {x}" for x in s6["cross_candidate"]] + [""]
    L += ["### 6.2 Parameter groups within the family (grouped by b and w)", ""]
    for lab, v in s6["parameter_groups"].items():
        L += [f"**{lab}**: " + ", ".join(v["facts"]["candidates"]), ""]
        L += [f"- {x}" for x in v["statements"]] + [""]
    L += ["### 6.3 Emphasis candidates sgb-screen-05 … 09", ""]
    for c, v in s6["emphasis_candidates"].items():
        pr = s3["candidate_parameters_and_xe_metrics"][c]
        L += [f"**{c}** (b = {pr['b_barrier_scale']}, c = {pr['c_center_L']} L, w = {pr['w_width_L']} L; Xe in-sample "
              f"max abs dI {pr['xe_in_sample_max_abs_dI_pct']} %; official verdict "
              f"{doc['official_outcome_unchanged']['candidate_verdicts'][c]})", ""]
        L += [f"- {x}" for x in v["statements"]]
        if v["facts"]["pass_locations"]:
            L.append("- PASS run-readings: " + "; ".join(v["facts"]["pass_locations"]) + ".")
        L.append("")
    ood, ex = s1["totals"], s1["by_registration"]["L32-exit"]
    ch_ = s2["structure"]["chemistry_pairs_both_scoreable"]
    L += ["### 6.4 What the scoreable evidence does not establish", "",
          "- It does not establish any transport closure. It admits nothing, and it does not rank the screening "
          "candidates.",
          f"- It does not test the OUT_OF_DOMAIN part of the campaign: {ood['OUT_OF_DOMAIN']} of {ood['n']} "
          f"run-readings, including {ex['OUT_OF_DOMAIN']} of the {ex['n']} L32-exit run-readings.",
          "- It does not say which physical ingredient produces the excess ion current at N2–N5. Transport-driven "
          "heating, chemistry, registration/geometry and field shape are not separated by these data. Among "
          f"chemistry pairs that are both scoreable, the official status is the same in {ch_['same_official_status']} "
          f"of {ch_['pairs']} (section 2.5).",
          "- It does not bear on the O4 staged sensitivities or on the facility-mode campaign.", "",
          "## 7. Limits", ""]
    L += [f"- {x}" for x in doc["limits"]]
    L += ["", "## Appendix A. Full grids for sgb-screen-01 … 04", ""]
    for c in cands:
        if c not in EMPHASIS:
            L += grid_md(s1, c, members, chems)
    return "\n".join(L).rstrip() + "\n"


def dstats(d, k=3):
    if d is None:
        return "—"
    f = (lambda x: f"{x:.{k}g}") if k == 6 else (lambda x: f"{x:.{k}f}")
    return f"{d['n']}: {f(d['min'])} / {f(d['p25'])} / {f(d['median'])} / {f(d['p75'])} / {f(d['max'])}"


def esc(s):
    """Escape the pipe in member names for Markdown tables."""
    return s.replace("|", "\\|")


def grid_md(s1, c, members, chems):
    L = [f"**{c}**", ""]
    rows_ = []
    for m in members:
        g = s1["grid"][c][m]
        rows_.append([esc(m)] + ["/".join(g[ch][i] for ch in chems) for i in range(len(POINTS))] +
                     [s1["by_candidate_member"][c][m]["official_member_verdict"]])
    L += md_table(["member"] + POINTS + ["official"], rows_)
    L.append("")
    return L


def main(argv):
    doc = build()
    js, md = dumps(doc), render(doc)
    if "--check" in argv:
        ok = (os.path.exists(OUT_JSON) and open(OUT_JSON, encoding="utf-8").read() == js and
              os.path.exists(OUT_MD) and open(OUT_MD, encoding="utf-8").read() == md)
        print("committed forensic files reproduce" if ok else "committed forensic files DIFFER from a rebuild")
        return 0 if ok else 1
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(js)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {os.path.relpath(OUT_JSON, ROOT)} and {os.path.relpath(OUT_MD, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

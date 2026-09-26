"""Scorer for the P5-N2 no-retuning validation campaign. Implements, and only implements, the frozen pre-registration
(hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json, p5_n2_run_status_rule_v1.json + addendum 1; lock
p5_n2_prereg_lock_v1.json; merged in PR #27). Targets come from the frozen measurement audit, never from a run.

Per run (candidate x chemistry x case x mode) and divergence reading r in {A, B} (thrust only):
  O2 precedence: NUMERICAL_FAILURE -> OUT_OF_DOMAIN -> FAIL_VALIDATION (reasons listed) -> PASS
    NUMERICAL_FAILURE: retcode != success, non-finite state, or a required observable missing
    OUT_OF_DOMAIN:     any unresolved rate table, or any reaction with f_out > 1e-12 (independent of the 'sustained' flag)
    FAIL_VALIDATION:   SUSTAINMENT (O1: mean of the final-10 % I_d samples < 0.05 I_target AND >= 90 % of them < 0.10 I_target),
                       CURRENT (|I_d - I_target| / I_target > 0.15, window mean), THRUST (N1-N3 only:
                       |T_1D f_r - T_target| > tolerance 5.2 / 5.6 / 5.6 mN)
  targets are mode-matched: vacuum -> Eq. (14) I_d,corr and published T_corr; facility -> P_d/V_d and Eq. (16)-inverted raw T.
O3: global layer-1 member = (registration, coil shape, reading); per candidate and mode it covers the 4 mandatory chemistry
    configs x 5 points = 20 runs: PASS iff all PASS; FAIL if any FAIL_VALIDATION; else INCONCLUSIVE.
    Candidate: PROMOTABLE iff some member PASS; else INCONCLUSIVE / NOT ELIGIBLE if some member INCONCLUSIVE; else
    FAIL_VALIDATION. Vacuum gates admission; facility is reported the same way and never gates.
O4: staged sensitivity vs its baseline (same candidate, case, mode = vacuum): escalate if any status changes, |dI_d| >= 7.5 % of
    I_target, |dT_axial| >= half the tolerance (2.6 / 2.8 / 2.8 mN), or a member / candidate verdict changes.
O5: E x B diagnostic (non-gating), N1-N3: V_a,s = m_s u_s^2 / (2 Z_s e) at the outlet for N2+ and N+; residual, residual / 11.6 V,
    outlet flux and flux fraction, ordering V_a(N+) > V_a(N2+).
Usage: python scripts/score_p5_n2_campaign.py <runs.jsonl ...> [--out <scores.json>]
"""
import collections, json, os, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
BR = os.path.join(ROOT, "hallthruster_bridge")
CRIT = json.load(open(os.path.join(BR, "prereg", "p5_n2_validation_criteria_v1.json")))
AUDIT = json.load(open(os.path.join(BR, "identification", "brabston_p5_n2_measurement_audit_v1.json")))["points"]
POINTS = ["N1", "N2", "N3", "N4", "N5"]
MANDATORY = CRIT["mandatory_chemistry"]
ID_TOL = 0.15
T_TOL_MN = CRIT["D3_tolerances"]["thrust_mN"]                      # N1 5.2, N2 5.6, N3 5.6
FOUT_TOL = 1e-12
EXB_SIGMA_V = 11.6
AMU, E = 1.66053906660e-27, 1.602176634e-19
MASS = {"N2": 28.0134 * AMU, "N": 14.0067 * AMU}
READINGS = ("A", "B")


def targets(point, mode):
    a = AUDIT[point]
    if mode == "vacuum":
        return a["I_d_corr_eq14_A"], a["T_corr_mN"]
    return a["I_d_raw_A"], a["T_raw_eq16_inverted_mN"]


def axial_factor(point, reading):
    c = AUDIT[point].get("consistency")
    return None if c is None else c[f"axial_factor_{reading}"]


def run_status(r, reading):
    """(status, reasons, detail) for one run record under one divergence reading."""
    need = ("discharge_current_A", "thrust_N", "Id_final10_samples_A", "chemistry_per_reaction")
    if r.get("retcode") != "success" or not r.get("finite", False) or any(r.get(k) is None for k in need) \
            or len(r["Id_final10_samples_A"]) == 0:
        return "NUMERICAL_FAILURE", [], {}
    unresolved = r.get("chemistry_unresolved_rate_files") or []
    fouts = [q.get("extrapolated_fraction") for q in r["chemistry_per_reaction"]]
    if unresolved or any(f is None or f > FOUT_TOL for f in fouts):
        return "OUT_OF_DOMAIN", [], {"f_out_max": max((f for f in fouts if f is not None), default=None), "unresolved": unresolved}
    I_t, T_t = targets(r["point"], r["mode"])
    s = r["Id_final10_samples_A"]
    mean_final = sum(s) / len(s)
    frac_low = sum(x < 0.10 * I_t for x in s) / len(s)
    reasons, det = [], {"I_target_A": I_t, "dI_rel": (r["discharge_current_A"] - I_t) / I_t,
                        "final10_mean_over_target": mean_final / I_t, "final10_frac_below_0p10": frac_low}
    if mean_final < 0.05 * I_t and frac_low >= 0.90:
        reasons.append("SUSTAINMENT")
    if abs(det["dI_rel"]) > ID_TOL:
        reasons.append("CURRENT")
    if r["point"] in T_TOL_MN:
        f = axial_factor(r["point"], reading)
        det["T_axial_mN"] = 1e3 * r["thrust_N"] * f
        det["T_target_mN"] = T_t
        det["dT_mN"] = det["T_axial_mN"] - T_t
        if abs(det["dT_mN"]) > T_TOL_MN[r["point"]]:
            reasons.append("THRUST")
    return ("FAIL_VALIDATION" if reasons else "PASS"), reasons, det


def exb(r):
    """O5 diagnostic, N1-N3 only; None where not applicable."""
    if r["point"] not in T_TOL_MN or not r.get("outlet_ions"):
        return None
    obs = AUDIT[r["point"]]["fig10"]
    ions = r["outlet_ions"]
    total = sum(v["flux_m2s"] for v in ions.values()) or float("nan")
    out = {}
    for key, sym, o in (("N2+", "N2_Z1", obs["Va_N2plus_V"]), ("N+", "N_Z1", obs["Va_Nplus_V"])):
        v = ions.get(sym)
        if v is None:
            out[key] = None; continue
        va = MASS[sym.split("_")[0]] * v["u_ms"] ** 2 / (2 * v["Z"] * E)
        out[key] = {"Va_model_V": va, "Va_obs_V": o, "dVa_V": va - o, "dVa_over_sigma": (va - o) / EXB_SIGMA_V,
                    "outlet_flux_m2s": v["flux_m2s"], "outlet_flux_fraction": v["flux_m2s"] / total}
    if out.get("N2+") and out.get("N+"):
        out["ordering_Nplus_above_N2plus"] = out["N+"]["Va_model_V"] > out["N2+"]["Va_model_V"]
    return out


def member_verdict(statuses):
    if statuses and all(s == "PASS" for s in statuses):
        return "PASS"
    if any(s == "FAIL_VALIDATION" for s in statuses):
        return "FAIL"
    return "INCONCLUSIVE"


def candidate_verdict(member_verdicts):
    v = list(member_verdicts)
    if "PASS" in v:
        return "PROMOTABLE"
    if "INCONCLUSIVE" in v:
        return "INCONCLUSIVE / NOT ELIGIBLE"
    return "FAIL_VALIDATION"


def score(records, chemistries=MANDATORY):
    """Per-run statuses and member / candidate verdicts per mode. Missing runs count as INCONCLUSIVE (never PASS)."""
    runs, members = [], collections.defaultdict(dict)
    idx = {(r["candidate"], r["chemistry"], r["registration"], r["coil_shape"], r["point"], r["mode"]): r for r in records}
    cands = sorted({r["candidate"] for r in records})
    regs = sorted({r["registration"] for r in records}); coils = sorted({r["coil_shape"] for r in records})
    modes = sorted({r["mode"] for r in records})
    for r in records:
        for rd in READINGS:
            st, why, det = run_status(r, rd)
            runs.append({"key": r["key"], "reading": rd, "status": st, "reasons": why, **det})
    for mode in modes:
        for cand in cands:
            mv = {}
            for reg in regs:
                for coil in coils:
                    for rd in READINGS:
                        sts = []
                        for ch in chemistries:
                            for p in POINTS:
                                r = idx.get((cand, ch, reg, coil, p, mode))
                                sts.append("MISSING" if r is None else run_status(r, rd)[0])
                        mv[f"{reg}|{coil}|{rd}"] = member_verdict(sts)
            members[mode][cand] = {"members": mv, "candidate": candidate_verdict(mv.values())}
    return runs, members


def escalation(sens_records, base_records, sensitivity):
    """O4 on vacuum results: which triggers fire for a staged sensitivity against its baseline (same candidate, case)."""
    tol = {p: 0.5 * t for p, t in T_TOL_MN.items()}
    base = {(r["candidate"], r["case"]): r for r in base_records if r["mode"] == "vacuum"}
    fired = []
    for s in (r for r in sens_records if r["mode"] == "vacuum"):
        b = base.get((s["candidate"], s["case"]))
        if b is None:
            fired.append((s["key"], "baseline missing")); continue
        for rd in READINGS:
            (ss, _, sd), (bs, _, bd) = run_status(s, rd), run_status(b, rd)
            if ss != bs:
                fired.append((s["key"], f"status {bs} -> {ss} ({rd})"))
            if "dI_rel" in sd and "dI_rel" in bd and abs(sd["dI_rel"] - bd["dI_rel"]) >= 0.075:
                fired.append((s["key"], f"dI_d {100 * (sd['dI_rel'] - bd['dI_rel']):+.1f} % ({rd})"))
            if "T_axial_mN" in sd and "T_axial_mN" in bd and abs(sd["T_axial_mN"] - bd["T_axial_mN"]) >= tol[s["point"]]:
                fired.append((s["key"], f"dT {sd['T_axial_mN'] - bd['T_axial_mN']:+.2f} mN ({rd})"))
    return fired


def verdict_change(sens_records, base_records, baseline_chem, sens_chem):
    """O4 last clause: does replacing the baseline chemistry by the sensitivity change any member / candidate verdict?
    Evaluated on the vacuum member built from the baseline-chemistry runs only (the other chemistries are not re-run)."""
    rb = [dict(r, chemistry="X") for r in base_records if r["mode"] == "vacuum"]
    rs = [dict(r, chemistry="X") for r in sens_records if r["mode"] == "vacuum"]
    _, mb = score(rb, ["X"]); _, ms = score(rs, ["X"])
    return {c: (mb["vacuum"][c], ms["vacuum"].get(c)) for c in mb.get("vacuum", {}) if mb["vacuum"][c] != ms["vacuum"].get(c)}


def main(argv):
    out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(BR, "validation", "p5_n2_campaign_v1_scores.json")
    paths = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--out")]
    recs = [json.loads(l) for p in paths for l in open(p)]
    assert not any(r.get("smoke") for r in recs), "smoke-test records are never scored"
    recs = [r for r in recs if r["chemistry"] in MANDATORY]
    runs, members = score(recs)
    res = {"preregistration": "prereg/p5_n2_validation_criteria_v1.json", "n_records": len(recs),
           "status_counts": {m: dict(collections.Counter((x["status"]) for x in runs if x["key"].endswith("|" + m)))
                             for m in ("vacuum", "facility")},
           "candidates": members, "exb_diagnostic": {r["key"]: exb(r) for r in recs if exb(r) is not None}, "runs": runs}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, "w"), indent=1)
    for mode, cs in members.items():
        for c, v in cs.items():
            print(mode, c, v["candidate"], collections.Counter(v["members"].values()))


if __name__ == "__main__":
    main(sys.argv[1:])

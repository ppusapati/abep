"""Mechanical closure table for the tier-3 multiply-charged processes (n2_completeness_audit_v1, addenda 1 and 2).
Input: the authoritative blind state-envelope records (checks/blind_state_envelope.jl, v4 metric list; 5 P5-N2 points x
9 SGB screening candidates x 4 chemistry configs, measured targets removed) and the argmax region reruns.
Rule (addendum 1, applied literally): U < T -> EXCLUDE; L > T -> PROMOTE; L < T < U -> UNCERTAINTY VARIANT. Promotion is
per criterion (F_ion OR F_S_s, pre-registered OR); the process verdict is the strongest criterion verdict.
Bounds over nuisance choices: L = min over runs of the lower-bound metric (promotion must hold for every nuisance choice),
U = max over runs of the upper-bound metric (exclusion must hold for every nuisance choice); a criterion whose status
changes with the nuisance choice is by construction L < T < U (addendum 1 robustness clause).
Where the source gives no band, lower = nominal = upper is stated as such ("no published band"), with the factor by which
the nominal would have to be wrong to change the verdict.
Usage: python scripts/n2_closure_table.py <records.jsonl ...> [--region region.jsonl]
"""
import json, os, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "hallthruster_bridge", "audit", "n2_closure_verdicts_v1.json")
BELL = 0.10                                                     # Bell et al. 1983 stated +-10 %
TABATA_FIT_OVER_DATA = (0.86, 1.11)                             # n2-69 fit / Bahati 2001 data (fit quality only)


def scale(F, f):
    """Rescale a share F = R/(D+R) when the omitted rate R is multiplied by f (denominator D fixed)."""
    return f * F / (1 - F + f * F)


def margin(Fmin, T):
    """Factor by which the omitted rate must fall for its share to drop from Fmin to T."""
    return (Fmin / (1 - Fmin)) / (T / (1 - T))


def crit(recs, key, T, lo=None, hi=None, lo_key=None, hi_key=None):
    ok = [r for r in recs if key in r]
    L = min(scale(r[lo_key or key], lo) if lo else r[lo_key or key] for r in ok)
    U = max(scale(r[hi_key or key], hi) if hi else r[hi_key or key] for r in ok)
    Lmax = max(r[lo_key or key] for r in ok)
    nom = [r[key] for r in ok]; worst = max(ok, key=lambda r: r[hi_key or key])
    v = "EXCLUDE" if U < T else "PROMOTE" if L > T else "UNCERTAINTY VARIANT"

    def flips(dim):   # does the above/below-threshold status of the NOMINAL metric change along dim, others fixed?
        groups = {}
        for r in ok:
            k = tuple(r[d] for d in ("point", "candidate", "config") if d != dim)
            groups.setdefault(k, set()).add(r[key] > T)
        return any(len(g) > 1 for g in groups.values())
    return {"threshold": T, "lower_min_over_runs": L, "nominal_range": [min(nom), max(nom)], "upper_max_over_runs": U,
            "lower_max_over_runs": Lmax, "worst_case": worst["key"], "verdict": v,
            "transport_sensitive": flips("candidate"), "chemistry_sensitive": flips("config"), "point_sensitive": flips("point"),
            "n_runs": len(ok)}


def main(argv):
    region = argv[argv.index("--region") + 1] if "--region" in argv else None
    paths = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--region")]
    recs = [json.loads(l) for p in paths for l in open(p)]
    recs = [r for r in recs if r.get("retcode") == "success"]
    rank = {"PROMOTE": 2, "UNCERTAINTY VARIANT": 1, "EXCLUDE": 0}
    rows = {
        "N -> N^2+ (direct)": {
            "source": "Hahn, Muller & Savin 2017 (semi-empirical; no experimental neutral-N data); no published band: lower = nominal = upper",
            "criteria": {"F_S(N^2+ production)": crit(recs, "F_S_NZ2_production_direct", 0.05),
                         "F_ion": crit(recs, "F_ion_N_to_NZ2_direct", 0.01)}},
        "N^2+ -> N^3+": {
            "source": "Bell et al. 1983 Eq. (1), stated +-10 %",
            "criteria": {"F_ion": crit(recs, "F_ion_NZ2_to_NZ3", 0.01, 1 - BELL, 1 + BELL),
                         "F_ion (per-frame max)": crit(recs, "F_ion_frame_max", 0.01, 1 - BELL, 1 + BELL),
                         "F_S(N^2+ destruction)": crit(recs, "F_S_NZ2_destruction", 0.05, 1 - BELL, 1 + BELL)}},
        "N2 -> N2^2+ (direct)": {
            "source": "lower/nominal: JPCRD 2023 Sec. 2.8 '~1 % of total ionization' from 42.9 eV (no lower band published); "
                      "upper: all double ionization 0.14e-16 cm^2 flat (Tian & Vidal via JPCRD)",
            "criteria": {"F_ion": crit(recs, "F_ion_N2Z2_direct_nominal", 0.01, hi_key="F_ion_N2Z2_direct_upper")}},
        "N2+ -> N2^2+ (sequential)": {
            "source": "Tabata et al. 2006 n2-69 fit to Bahati et al. 2001 (fit/data 0.86-1.11 used as the band; Bahati's own "
                      "absolute uncertainty not applied: verify)",
            "criteria": {"F_ion": crit(recs, "F_ion_N2Z2_seq_only", 0.01, *TABATA_FIT_OVER_DATA),
                         "F_S(N2+ destruction)": crit(recs, "F_S_N2p_destruction_seq", 0.05, *TABATA_FIT_OVER_DATA)},
            "within_N2Z2_variant": {"F_S(N2^2+ production), with nominal direct": crit(recs, "F_S_N2Z2_production_seq_nominal", 0.05),
                                    "F_S(N2^2+ production), with upper direct": crit(recs, "F_S_N2Z2_production_seq_upper", 0.05)}},
    }
    for name, row in rows.items():
        row["verdict"] = max((c["verdict"] for c in row["criteria"].values()), key=rank.get)
        prim = max(row["criteria"].items(), key=lambda kv: (rank[kv[1]["verdict"]], kv[1]["upper_max_over_runs"] / kv[1]["threshold"]))
        row["deciding_criterion"] = prim[0]
        if row["verdict"] == "PROMOTE":
            c = prim[1]; row["margin_factor_nominal_must_fall_to_reverse"] = margin(c["lower_min_over_runs"], c["threshold"])
        if row["verdict"] == "EXCLUDE":
            c = max(row["criteria"].values(), key=lambda c: c["upper_max_over_runs"] / c["threshold"])
            row["margin_factor_upper_must_rise_to_reverse"] = 1 / margin(c["upper_max_over_runs"], c["threshold"])
    out = {"id": "n2_closure_verdicts_v1", "rule": "n2_completeness_audit_v1 + addendum1 (ambiguity) + addendum2 (cross-check)",
           "n_runs": len(recs), "n_chemistry_trustworthy": sum(bool(r.get("chemistry_trustworthy")) for r in recs),
           "rows": rows}
    tr = [r for r in recs if r.get("chemistry_trustworthy")]
    out["verdicts_trustworthy_runs_only"] = {n: max((crit(tr, *a)["verdict"] for a in args), key=rank.get) for n, args in {
        "N -> N^2+ (direct)": [("F_S_NZ2_production_direct", 0.05), ("F_ion_N_to_NZ2_direct", 0.01)],
        "N^2+ -> N^3+": [("F_ion_NZ2_to_NZ3", 0.01, 0.9, 1.1), ("F_S_NZ2_destruction", 0.05, 0.9, 1.1)],
        "N2 -> N2^2+ (direct)": [("F_ion_N2Z2_direct_nominal", 0.01, None, None, None, "F_ion_N2Z2_direct_upper")],
        "N2+ -> N2^2+ (sequential)": [("F_ion_N2Z2_seq_only", 0.01, 0.86, 1.11), ("F_S_N2p_destruction_seq", 0.05, 0.86, 1.11)]}.items()}
    beyond = {}
    for r in recs:
        for f, v in (r.get("chemistry_files_beyond_limit") or {}).items():
            b = beyond.setdefault(f, {"n_runs": 0, "max_fraction": 0.0, "candidates": set()})
            b["n_runs"] += 1; b["max_fraction"] = max(b["max_fraction"], v); b["candidates"].add(r["candidate"])
    out["validity_limit_exceedances"] = {f: {**b, "candidates": sorted(b["candidates"])} for f, b in sorted(beyond.items())}
    # reaction-weighted region of the worst case of each process, from that run's own record (v4 records carry it)
    chan = {"N -> N^2+ (direct)": "Ndd", "N^2+ -> N^3+": "NZ3", "N2 -> N2^2+ (direct)": "N2dir", "N2+ -> N2^2+ (sequential)": "N2seq"}
    byk = {r["key"]: r for r in recs}
    for n, row in rows.items():
        w = byk[max(row["criteria"].values(), key=lambda c: c["upper_max_over_runs"] / c["threshold"])["worst_case"]]
        ch = chan[n]
        row["worst_case_reaction_weighted_region"] = {"case": w["key"], **{q: w.get(f"region_{ch}_{q}") for q in ("Te_eV", "z_over_L", "ne_m3")}}
        allq = {q: [r.get(f"region_{ch}_{q}") for r in recs if r.get(f"region_{ch}_{q}") is not None] for q in ("Te_eV", "z_over_L", "ne_m3")}
        row["reaction_weighted_region_range_all_runs"] = {q: [min(v), max(v)] for q, v in allq.items() if v}
    out["N2plus_abundance_vs_N3plus_activity"] = {
        "Te_at_max_nNZ2_over_nN2_eV": [min(r["Te_at_max_ratio_eV"] for r in recs), max(r["Te_at_max_ratio_eV"] for r in recs)],
        "max_nNZ2_over_nN2": [min(r["max_ratio_NZ2_over_N2"] for r in recs), max(r["max_ratio_NZ2_over_N2"] for r in recs)],
        "NZ3_reaction_weighted_Te_eV": rows["N^2+ -> N^3+"]["reaction_weighted_region_range_all_runs"]["Te_eV"],
        "N^3+ threshold_eV": 47.45}
    if region:
        rr = [json.loads(l) for l in open(region)]
        out["reaction_weighted_regions_argmax_reruns"] = {
            ch: {q: [min(r[f"region_{ch}_{q}"] for r in rr if f"region_{ch}_{q}" in r), max(r[f"region_{ch}_{q}"] for r in rr if f"region_{ch}_{q}" in r)]
                 for q in ("Te_eV", "z_over_L", "ne_m3")} for ch in ("Ndd", "NZ3", "N2dir", "N2seq")}
        out["N2plus_abundance_vs_activity"] = {"Te_at_max_nNZ2_over_nN2_eV_range": [min(r["Te_at_max_ratio_eV"] for r in recs), max(r["Te_at_max_ratio_eV"] for r in recs)],
                                               "max_nNZ2_over_nN2_range": [min(r["max_ratio_NZ2_over_N2"] for r in recs), max(r["max_ratio_NZ2_over_N2"] for r in recs)]}
    json.dump(out, open(OUT, "w"), indent=1)
    for n, row in rows.items():
        print(f"{n:28s} {row['verdict']:20s} by {row['deciding_criterion']}")
        for cn, c in row["criteria"].items():
            print(f"   {cn:24s} L {c['lower_min_over_runs']:.3g}  nom {c['nominal_range'][0]:.3g}-{c['nominal_range'][1]:.3g}  U {c['upper_max_over_runs']:.3g}"
                  f"  T {c['threshold']}  worst {c['worst_case']}  transport {c['transport_sensitive']}  chem {c['chemistry_sensitive']}  -> {c['verdict']}")
        for cn, c in row.get("within_N2Z2_variant", {}).items():
            print(f"   [variant] {cn:40s} nom {c['nominal_range'][0]:.3g}-{c['nominal_range'][1]:.3g}")
    print(json.dumps({k: out[k] for k in ("n_runs", "n_chemistry_trustworthy", "verdicts_trustworthy_runs_only", "validity_limit_exceedances")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])

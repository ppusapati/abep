"""Summarize the blind state-envelope runs (hallthruster_bridge/checks/blind_state_envelope.jl) into
hallthruster_bridge/audit/blind_state_envelope_v1.json. Verdicts follow n2_completeness_audit_v1 thresholds (F_ion 1 %,
F_S 5 %) and addendum 1 (ambiguity rule). The runs had all measured targets removed; no I_d, thrust or fit quantity exists.
For each metric: max, the case producing it, ranges by operating point / transport candidate / chemistry config, and
whether the verdict flips with the nuisance choice. An older run file that shares metrics is used as an implementation
cross-check (--check old.jsonl).
Usage: python scripts/summarize_blind_envelope.py <v3 records ...> [--check old.jsonl] [--region region.jsonl]
"""
import json, os, sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "hallthruster_bridge", "audit", "blind_state_envelope_v1.json")
RECORDS = os.path.join(ROOT, "hallthruster_bridge", "audit", "blind_state_envelope_v1_records.jsonl")
METRICS = {  # key -> (process, criterion, threshold)
    "F_ion_NZ2_to_NZ3": ("N^2+ -> N^3+", "F_ion", 0.01),
    "F_S_NZ2_destruction": ("N^2+ -> N^3+", "F_S(N^2+ destruction)", 0.05),
    "F_ion_N_to_NZ2_direct": ("direct N -> N^2+", "F_ion", 0.01),
    "F_S_NZ2_production_direct": ("direct N -> N^2+", "F_S(N^2+ production)", 0.05),
    "F_ion_N2Z2_seq_only": ("N2^2+ sequential only", "F_ion", 0.01),
    "F_ion_N2Z2_nominal": ("N2^2+ (nominal direct + sequential)", "F_ion", 0.01),
    "F_ion_N2Z2_upper": ("N2^2+ (upper direct + sequential)", "F_ion", 0.01),
    "F_ion_N2Z2_direct_nominal": ("N2 -> N2^2+ direct, nominal", "F_ion", 0.01),
    "F_ion_N2Z2_direct_upper": ("N2 -> N2^2+ direct, upper", "F_ion", 0.01),
    "F_S_N2p_destruction_seq": ("N2+ -> N2^2+ sequential", "F_S(N2+ destruction)", 0.05),
}


def load(paths):
    recs = {}
    for p in paths:
        for line in open(p):
            r = json.loads(line); recs[r["key"]] = r
    return recs


def main(argv):
    check = argv[argv.index("--check") + 1] if "--check" in argv else None
    region = argv[argv.index("--region") + 1] if "--region" in argv else None
    paths = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in ("--check", "--region"))]
    recs = load(paths)
    ok = [r for r in recs.values() if r.get("retcode") == "success"]
    s = {"n_records": len(recs), "n_success": len(ok), "failed": sorted(k for k, r in recs.items() if r.get("retcode") != "success"),
         "not_sustained": sorted(r["key"] for r in ok if not r.get("sustained"))}
    s["n_chemistry_trustworthy"] = sum(bool(r.get("chemistry_trustworthy")) for r in ok)
    for subset, sel in (("metrics", ok), ("metrics_chemistry_trustworthy_only", [r for r in ok if r.get("chemistry_trustworthy")])):
      s[subset] = {}
      for m, (proc, crit, th) in METRICS.items():
        vals = [r for r in sel if m in r]
        if not vals:
            continue
        top = max(vals, key=lambda r: r[m])
        by = {}
        for dim in ("point", "candidate", "config"):
            g = defaultdict(list)
            for r in vals:
                g[r[dim]].append(r[m])
            by[dim] = {k: [min(v), max(v)] for k, v in sorted(g.items())}
        above = [r["key"] for r in vals if r[m] > th]
        s[subset][m] = {"process": proc, "criterion": crit, "threshold": th, "n": len(vals), "min": min(r[m] for r in vals),
                           "max": top[m], "argmax": top["key"], "n_above_threshold": len(above),
                           "verdict_flips_with_nuisance": 0 < len(above) < len(vals), "ranges": by}
    if check:
        old = load([check]); common = [k for k in old if k in recs and old[k].get("retcode") == "success" and recs[k].get("retcode") == "success"]
        d = max((abs(old[k][m] / recs[k][m] - 1) for k in common for m in old[k]
                 if isinstance(old[k][m], float) and old[k][m] and isinstance(recs[k].get(m), float)), default=None)
        s["cross_check_vs_independent_batch"] = {"file": os.path.basename(check), "n_common": len(common), "max_rel_diff_common_metrics": d}
    if region:
        s["region_of_maxima"] = {r["key"]: {k: v for k, v in r.items() if k.startswith("region_") or k.startswith("chemistry_") or k in ("max_ratio_NZ2_over_N2", "Te_at_max_ratio_eV")}
                                 for r in load([region]).values() if r.get("retcode") == "success"}
    json.dump(s, open(OUT, "w"), indent=1)
    with open(RECORDS, "w") as fh:
        for k in sorted(recs):
            fh.write(json.dumps(recs[k]) + "\n")
    print(json.dumps({k: v for k, v in s.items() if k != "region_of_maxima"}, indent=1)[:6000])


if __name__ == "__main__":
    main(sys.argv[1:])

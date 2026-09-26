"""Summarize the blind state-envelope runs (hallthruster_bridge/checks/blind_state_envelope.jl) into
hallthruster_bridge/audit/blind_state_envelope_v1.json, with verdicts under prereg n2_completeness_audit_v1 (F_ion > 1 %,
F_S > 5 %). The runs had all measured targets removed; no I_d, thrust or fit quantity exists in them.
Usage: python scripts/summarize_blind_envelope.py <records.jsonl> [more.jsonl ...]
"""
import json, os, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "hallthruster_bridge", "audit", "blind_state_envelope_v1.json")
RECORDS = os.path.join(ROOT, "hallthruster_bridge", "audit", "blind_state_envelope_v1_records.jsonl")
METRICS = {  # key -> (criterion, threshold, description)
    "F_ion_NZ2_to_NZ3": ("F_ion", 0.01, "N^2+ -> N^3+, share of positive-ion production"),
    "F_S_NZ2_destruction": ("F_S", 0.05, "N^2+ -> N^3+, share of N^2+ production destroyed"),
    "F_ion_N_to_NZ2_direct": ("F_ion", 0.01, "direct N -> N^2+ (Hahn et al. 2017), share of positive-ion production"),
    "F_S_NZ2_production_direct": ("F_S", 0.05, "direct N -> N^2+, share of all N^2+ production"),
    "F_ion_N2Z2_seq_only": ("F_ion", 0.01, "N2+ -> N2^2+ (Tabata/Bahati), share of positive-ion production"),
    "F_ion_N2Z2_nominal": ("F_ion", 0.01, "N2^2+ total, nominal direct envelope + sequential"),
    "F_ion_N2Z2_upper": ("F_ion", 0.01, "N2^2+ total, loose-upper direct envelope + sequential"),
}


def main(paths):
    recs = {}
    for p in paths:
        for line in open(p):
            r = json.loads(line); recs[r["key"]] = r        # later files win on duplicate keys (identical runs)
    ok = [r for r in recs.values() if r.get("retcode") == "success"]
    summary = {"n_records": len(recs), "n_success": len(ok),
               "failed": sorted(k for k, r in recs.items() if r.get("retcode") != "success"), "metrics": {}}
    for m, (crit, th, desc) in METRICS.items():
        vals = [(r[m], r["key"]) for r in ok if m in r]
        if not vals:
            continue
        mx = max(vals)
        summary["metrics"][m] = {"description": desc, "criterion": crit, "threshold": th, "n": len(vals), "max": mx[0],
                                 "argmax": mx[1], "n_above_threshold": sum(v > th for v, _ in vals),
                                 "verdict": "EXCEEDS" if mx[0] > th else "BELOW"}
    summary["max_ratio_NZ2_over_N2"] = max(r["max_ratio_NZ2_over_N2"] for r in ok)
    summary["xN_ne_weighted_range"] = [min(r["xN_ne_weighted"] for r in ok if "xN_ne_weighted" in r),
                                       max(r["xN_ne_weighted"] for r in ok if "xN_ne_weighted" in r)] if any("xN_ne_weighted" in r for r in ok) else None
    json.dump(summary, open(OUT, "w"), indent=1)
    with open(RECORDS, "w") as fh:
        for k in sorted(recs):
            fh.write(json.dumps(recs[k]) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])

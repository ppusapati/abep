"""Mechanical report and decision file from a P5-N2 scorer output (scripts/score_p5_n2_campaign.py). No judgement is added:
the decision file is a transcription of the scorer's O3 candidate verdicts in the admission mode (vacuum); facility never gates.

Report order (owner decision 2026-09-26):
  1. candidate verdicts (vacuum; facility shown separately, non-gating)
  2. the 12 global layer-1 member verdicts per candidate (registration x coil shape x divergence reading)
  3. run-status and failure-reason counts (overall, by candidate, chemistry, point)
  4. SIGNED residual distributions: dI_d / I_target at N1-N5 and dT_axial [mN] at N1-N3 (min / median / max), overall and per
     candidate x point, for numerically valid runs of every status (OUT_OF_DOMAIN rows are labelled, not dropped)
  5. the non-gating E x B diagnostic (signed dV_a, dV_a / 11.6 V, outlet flux fraction, species ordering)
Usage: python scripts/report_p5_n2_campaign.py <scores.json> [--md out.md] [--decision out.json]
"""
import collections, json, os, statistics, sys

POINTS = ["N1", "N2", "N3", "N4", "N5"]


def parse_key(key):
    cand, chem, case, mode = key.split("|")
    point, rest = case.split("-", 1)
    reg, coil = rest.rsplit("-", 1)
    return {"candidate": cand, "chemistry": chem, "point": point, "registration": reg, "coil_shape": coil, "mode": mode}


def stats(v):
    return None if not v else {"n": len(v), "min": min(v), "median": statistics.median(v), "max": max(v)}


def decision(scores, source_scores_sha256=None, scores_provenance=None):
    vac = scores["candidates"].get("vacuum", {})
    return {"source": "scripts/score_p5_n2_campaign.py output (frozen pre-registration p5_n2_validation_criteria_v1)",
            "source_scores_sha256": source_scores_sha256, "scores_provenance": scores_provenance,
            "admission_mode": "vacuum",
            "candidates": {c: v["candidate"] for c, v in sorted(vac.items())},
            "promotable": sorted(c for c, v in vac.items() if v["candidate"] == "PROMOTABLE"),
            "inconclusive": sorted(c for c, v in vac.items() if v["candidate"].startswith("INCONCLUSIVE")),
            "failed_validation": sorted(c for c, v in vac.items() if v["candidate"] == "FAIL_VALIDATION"),
            "passing_members": {c: sorted(k for k, m in v["members"].items() if m == "PASS") for c, v in sorted(vac.items())},
            "facility_verdicts_non_gating": {c: v["candidate"] for c, v in sorted(scores["candidates"].get("facility", {}).items())}}


def report(scores):
    L = ["# P5-N2 no-retuning validation campaign: pre-registered result", "",
         f"Pre-registration: `{scores['preregistration']}`. Records scored: {scores['n_records']}.", ""]
    L += ["## 1. Candidate verdicts", "", "| candidate | vacuum (admission) | facility (non-gating) |", "|---|---|---|"]
    fac = scores["candidates"].get("facility", {})
    for c, v in sorted(scores["candidates"].get("vacuum", {}).items()):
        L.append(f"| {c} | **{v['candidate']}** | {fac.get(c, {}).get('candidate', '—')} |")
    L += ["", "## 2. Global layer-1 member verdicts (vacuum)", ""]
    vac = scores["candidates"].get("vacuum", {})
    members = sorted({k for v in vac.values() for k in v["members"]})
    L += ["| candidate | " + " | ".join(members) + " |", "|---|" + "---|" * len(members)]
    for c, v in sorted(vac.items()):
        L.append(f"| {c} | " + " | ".join(v["members"].get(k, "—") for k in members) + " |")
    rows = [dict(r, **parse_key(r["key"])) for r in scores["runs"]]
    L += ["", "## 3. Run status and failure reasons", "",
          "Counts are per (run, divergence reading); CURRENT and SUSTAINMENT do not depend on the reading.", ""]
    for mode in ("vacuum", "facility"):
        rm = [r for r in rows if r["mode"] == mode]
        if not rm:
            continue
        L.append(f"**{mode}**: " + ", ".join(f"{k} {n}" for k, n in sorted(collections.Counter(r["status"] for r in rm).items()))
                 + "; reasons: " + ", ".join(f"{k} {n}" for k, n in sorted(collections.Counter(x for r in rm for x in r["reasons"]).items())))
        for dim in ("candidate", "chemistry", "point"):
            L += ["", f"| {mode} by {dim} | PASS | FAIL_VALIDATION | OUT_OF_DOMAIN | NUMERICAL_FAILURE | CURRENT | THRUST | SUSTAINMENT |",
                  "|---|---|---|---|---|---|---|---|"]
            for val in sorted({r[dim] for r in rm}):
                sub = [r for r in rm if r[dim] == val]
                st = collections.Counter(r["status"] for r in sub); rs = collections.Counter(x for r in sub for x in r["reasons"])
                L.append(f"| {val} | {st['PASS']} | {st['FAIL_VALIDATION']} | {st['OUT_OF_DOMAIN']} | {st['NUMERICAL_FAILURE']} | "
                         f"{rs['CURRENT']} | {rs['THRUST']} | {rs['SUSTAINMENT']} |")
        L.append("")
    L += ["## 4. Signed residuals (vacuum)", "",
          "dI = (I_sim - I_target)/I_target; dT = T_axial,sim - T_target [mN] (reading A and B listed separately). "
          "Numerically valid runs of every status; the OUT_OF_DOMAIN share is shown.", ""]
    vr = [r for r in rows if r["mode"] == "vacuum" and "dI_rel" in r]
    L += ["| point | dI: n / min / median / max | OOD share | dT reading A: min / median / max | dT reading B: min / median / max |",
          "|---|---|---|---|---|"]
    fmt = lambda s, f: "—" if s is None else f"{s['n']} / {s['min']:{f}} / {s['median']:{f}} / {s['max']:{f}}"
    fmt3 = lambda s: "—" if s is None else f"{s['min']:+.2f} / {s['median']:+.2f} / {s['max']:+.2f}"
    for p in POINTS:
        sub = [r for r in vr if r["point"] == p and r["reading"] == "A"]
        ood = sum(r["status"] == "OUT_OF_DOMAIN" for r in sub) / len(sub) if sub else 0
        tA = stats([r["dT_mN"] for r in vr if r["point"] == p and r["reading"] == "A" and "dT_mN" in r])
        tB = stats([r["dT_mN"] for r in vr if r["point"] == p and r["reading"] == "B" and "dT_mN" in r])
        L.append(f"| {p} | {fmt(stats([r['dI_rel'] for r in sub]), '+.3f')} | {ood:.2f} | {fmt3(tA)} | {fmt3(tB)} |")
    L += ["", "Per candidate, median signed dI by point (reading-independent) and median dT (A / B) at N1-N3:", "",
          "| candidate | " + " | ".join(f"dI {p}" for p in POINTS) + " | " + " | ".join(f"dT {p} A/B" for p in POINTS[:3]) + " |",
          "|---|" + "---|" * 8]
    for c in sorted({r["candidate"] for r in vr}):
        cells = []
        for p in POINTS:
            v = [r["dI_rel"] for r in vr if r["candidate"] == c and r["point"] == p and r["reading"] == "A"]
            cells.append(f"{statistics.median(v):+.3f}" if v else "—")
        for p in POINTS[:3]:
            a = [r["dT_mN"] for r in vr if r["candidate"] == c and r["point"] == p and r["reading"] == "A" and "dT_mN" in r]
            b = [r["dT_mN"] for r in vr if r["candidate"] == c and r["point"] == p and r["reading"] == "B" and "dT_mN" in r]
            cells.append((f"{statistics.median(a):+.1f}" if a else "—") + " / " + (f"{statistics.median(b):+.1f}" if b else "—"))
        L.append(f"| {c} | " + " | ".join(cells) + " |")
    L += ["", "## 5. E×B diagnostic (non-gating)", "",
          "V_a,model = m u²/(2Ze) at the model outlet vs the E×B value at 1 m; residuals are diagnostic only.", "",
          "| point | species | dV_a [V]: min / median / max | dV_a/11.6 V median | outlet flux fraction median |", "|---|---|---|---|---|"]
    ex = [(parse_key(k), v) for k, v in scores.get("exb_diagnostic", {}).items() if v and parse_key(k)["mode"] == "vacuum"]
    for p in POINTS[:3]:
        for sp in ("N2+", "N+"):
            d = [v[sp] for kk, v in ex if kk["point"] == p and v.get(sp)]
            if not d:
                continue
            s = stats([x["dVa_V"] for x in d])
            L.append(f"| {p} | {sp} | {s['min']:+.1f} / {s['median']:+.1f} / {s['max']:+.1f} | "
                     f"{statistics.median(x['dVa_over_sigma'] for x in d):+.2f} | {statistics.median(x['outlet_flux_fraction'] for x in d):.3f} |")
    order = [v.get("ordering_Nplus_above_N2plus") for _, v in ex if "ordering_Nplus_above_N2plus" in v]
    if order:
        L.append(f"\nSpecies ordering V_a(N+) > V_a(N2+) holds in {sum(order)} of {len(order)} runs (measured: holds at N1-N3).")
    staged = scores.get("staged_escalation") or {}
    if staged:
        L += ["", "## Staged sensitivities (O4)", ""] + [f"- {k} vs {v['baseline']}: trigger {'FIRED' if v['trigger_fired'] else 'not fired'}"
                                                          for k, v in sorted(staged.items())]
    return "\n".join(L) + "\n"


def main(argv):
    scores = json.load(open(argv[0]))
    md = argv[argv.index("--md") + 1] if "--md" in argv else argv[0].replace(".json", "_report.md")
    dec = argv[argv.index("--decision") + 1] if "--decision" in argv else argv[0].replace(".json", "_decision.json")
    for p in (md, dec):
        if os.path.exists(p):
            raise SystemExit(f"refusing to overwrite {p}")
    import hashlib
    scores_sha = hashlib.sha256(open(argv[0], "rb").read()).hexdigest()
    prov_path = argv[0].replace("_scores.json", "_scores_provenance.json")
    prov = None
    if os.path.exists(prov_path):
        pj = json.load(open(prov_path))
        if pj.get("output_sha256") != scores_sha:
            raise SystemExit("scores file does not match its provenance manifest")
        prov = {"file": os.path.basename(prov_path), "sha256": hashlib.sha256(open(prov_path, "rb").read()).hexdigest()}
    open(md, "w").write(report(scores))
    json.dump(decision(scores, scores_sha, prov), open(dec, "w"), indent=1)
    print(md, dec)


if __name__ == "__main__":
    main(sys.argv[1:])

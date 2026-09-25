"""P5-Xe transport identification under competing geometry hypotheses (leave-one-out), HallThruster.jl v0.23.1.

Protocol (project decision 2026-09-25, docs/HISTORY.md):
- Hypotheses H1 = L38-hist, H2 = L32-anode, H3 = L32-exit (cases/p5_xenon.json, 1.6 kW coil shape). Everything except
  the transport parameters is identical across hypotheses and fixed at the case-file values: B(z), wall model
  WallSheath(BNSiO2, 1.0), cathode coupling, ingestion (Eq. 13, multiplier fixed by geometry), chemistry, numerics.
- Free parameters: TwoZoneBohm c1 (inside), c2 (outside), transition length. Pre-registered grid below; no optimiser, so
  every point is run and logged (failed runs included).
- Calibration data: facility mode only (ingestion ON) vs the raw measurements: I_d = P_d/V_d (Table 4) and raw stand
  thrust (Eq. 16 inverted from the published corrected thrust). Vacuum mode vs corrected values is a secondary
  consistency check on the selected fits only; the two modes are one experiment, not independent observations.
- Objective (a stated convention, equal relative weight so I_d does not dominate): J = mean over calibration points of
  (dI/I)^2 + (dT/T)^2. Thrust is additionally checked against its published uncertainty (+-4.9 mN, Table 5).
- Oscillation: Brabston report only that the coils minimised I_d oscillation, so RMS/peak-to-peak/frequency are reported
  as values; a deep breathing mode is treated as inconsistent with the reported regime, but no numeric target is invented.
- Physically defensible transport (stated prior, reported as a flag, not a filter): c1 <= c2 <= 1/16 (Bohm).
- Leave-one-out: for each hypothesis, (Xe1,Xe2)->Xe3, (Xe1,Xe3)->Xe2, (Xe2,Xe3)->Xe1.
Usage: python scripts/identify_p5_transport.py [run|analyse] [--workers 4]
"""
import csv, itertools, json, math, os, subprocess, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BRIDGE = os.path.join(ROOT, "hallthruster_bridge")
WORK = os.path.join(BRIDGE, "out", "identify_v1")
RESULTS = os.path.join(BRIDGE, "identification")
GRID = {
    "c1": [1 / 1000, 1 / 500, 1 / 250, 1 / 160, 1 / 100, 1 / 50],
    "c2": [1 / 64, 1 / 32, 1 / 16, 1 / 8, 1 / 4],
    "lt_frac": [0.05, 0.1, 0.2],          # transition length / channel length (HallThruster default 0.1)
}
HYPOTHESES = {"H1": "L38-hist", "H2": "L32-anode", "H3": "L32-exit"}
POINTS = ["Xe1", "Xe2", "Xe3"]
BOHM = 1 / 16


def combos():
    for c1, c2, f in itertools.product(GRID["c1"], GRID["c2"], GRID["lt_frac"]):
        if c1 <= c2:
            yield c1, c2, f


def combo_id(c1, c2, f):
    return f"c1=1/{round(1 / c1)}_c2=1/{round(1 / c2)}_lt={f:g}L"


def jobs(mode="facility", only=None):
    base = {c["id"]: c for c in json.load(open(os.path.join(BRIDGE, "cases", "p5_xenon.json")))["cases"]}
    out = []
    for h, reg in HYPOTHESES.items():
        for p in POINTS:
            c0 = base[f"{p}-{reg}"]
            for c1, c2, f in combos():
                cid = combo_id(c1, c2, f)
                if only is not None and (h, cid) not in only:
                    continue
                c = dict(c0, compact=True, transport={"model": "TwoZoneBohm", "c1": c1, "c2": c2,
                                                        "transition_length_m": f * c0["L_m"]})
                c.pop("comparison_modes", None)
                out.append({"job_id": f"{h}|{p}|{cid}|{mode}", "mode": mode, "case": c})
    return out


def run(job_list, tag, workers):
    os.makedirs(WORK, exist_ok=True)
    chunks = [job_list[i::workers] for i in range(workers)]
    procs = []
    for i, ch in enumerate(chunks):
        jf = os.path.join(WORK, f"{tag}_jobs_{i}.json")
        json.dump(ch, open(jf, "w"))
        log = open(os.path.join(WORK, f"{tag}_worker_{i}.log"), "a")
        procs.append(subprocess.Popen(["julia", "--project=" + BRIDGE, os.path.join(BRIDGE, "identify_worker.jl"),
                                       jf, os.path.join(WORK, f"{tag}_results_{i}.jsonl")], stdout=log, stderr=log))
    rc = [p.wait() for p in procs]
    if any(rc):
        sys.exit(f"worker exit codes {rc}; see {WORK}/*.log")


def load(tag):
    rows = {}
    for fn in sorted(os.listdir(WORK)):
        if fn.startswith(tag + "_results_") and fn.endswith(".jsonl"):
            for line in open(os.path.join(WORK, fn)):
                if line.strip():
                    r = json.loads(line); rows[r["job_id"]] = r
    return rows


def flat(rows):
    out = []
    for jid, r in sorted(rows.items()):
        h, p, cid, mode = jid.split("|")
        ok = r.get("retcode") == "success"
        out.append({
            "hypothesis": h, "registration": HYPOTHESES[h], "point": p, "combo": cid, "mode": mode,
            "retcode": r.get("retcode"), "Id_A": r.get("discharge_current_A"), "Id_target_A": r.get("Id_target_A"),
            "Id_err_rel": r.get("Id_err_rel"), "T_mN": r["thrust_N"] * 1e3 if ok else None,
            "T_target_mN": r["T_target_N"] * 1e3 if ok else None, "T_err_rel": r.get("T_err_rel"),
            "T_err_sigma": r.get("T_err_sigma"), "Id_rms_rel": r.get("Id_rms_rel"), "Id_pp_rel": r.get("Id_pp_rel"),
            "Id_f_dominant_Hz": r.get("Id_f_dominant_Hz"), "current_eff": r.get("current_eff"),
            "anode_eff": r.get("anode_eff"), "error": (r.get("error") or "")[:200],
        })
    return out


def analyse(table):
    by = {}
    for r in table:
        if r["mode"] == "facility":
            by[(r["hypothesis"], r["combo"], r["point"])] = r
    cids = sorted({r["combo"] for r in table})
    params = {combo_id(*c): c for c in combos()}
    summary = {}
    for h in HYPOTHESES:
        rounds = []
        for hold in POINTS:
            cal = [p for p in POINTS if p != hold]
            scored = []
            for cid in cids:
                rs = [by.get((h, cid, p)) for p in cal]
                if any(r is None or r["retcode"] != "success" for r in rs):
                    scored.append((math.inf, cid)); continue
                J = sum(r["Id_err_rel"] ** 2 + r["T_err_rel"] ** 2 for r in rs) / len(rs)
                scored.append((J, cid))
            scored.sort()
            J, best = scored[0]
            c1, c2, f = params[best]
            hr = by[(h, best, hold)]
            cal_rows = [by[(h, best, p)] for p in cal]
            rounds.append({
                "holdout": hold, "calibration": cal, "best_combo": best, "J_cal": J,
                "n_failed_runs_in_calibration": sum(1 for s in scored if not math.isfinite(s[0])),
                "cal_Id_err": [r["Id_err_rel"] for r in cal_rows], "cal_T_err_sigma": [r["T_err_sigma"] for r in cal_rows],
                "cal_rms": [r["Id_rms_rel"] for r in cal_rows],
                "hold_retcode": hr["retcode"], "hold_Id_err": hr["Id_err_rel"], "hold_T_err_sigma": hr["T_err_sigma"],
                "hold_rms": hr["Id_rms_rel"], "hold_f_kHz": (hr["Id_f_dominant_Hz"] or 0) / 1e3,
                "defensible_c1_le_c2_le_bohm": c1 <= c2 <= BOHM,
                "at_grid_edge": [k for k, v in (("c1", c1), ("c2", c2), ("lt_frac", f)) if v in (min(GRID[k]), max(GRID[k]))],
                "top5": [(round(j, 4), c) for j, c in scored[:5]],
            })
        summary[h] = {"registration": HYPOTHESES[h], "rounds": rounds,
                      "same_combo_all_rounds": len({r["best_combo"] for r in rounds}) == 1}
    return summary


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    if mode == "run":
        run(jobs("facility"), "facility", workers)
    rows = load("facility")
    table = flat(rows)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "p5_xe_identification_v1_runs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0])); w.writeheader(); w.writerows(table)
    summary = analyse(table)
    meta = {"grid": GRID, "hypotheses": HYPOTHESES, "objective": "mean over calibration points of (dI/I)^2 + (dT/T)^2",
            "calibration_mode": "facility (ingestion ON) vs raw I_d and raw thrust", "bohm_bound": BOHM,
            "n_runs": len(table), "n_failed": sum(1 for r in table if r["retcode"] != "success")}
    json.dump({"meta": meta, "summary": summary}, open(os.path.join(RESULTS, "p5_xe_identification_v1_summary.json"), "w"), indent=1)
    print(json.dumps(meta))
    for h, s in summary.items():
        print(f"\n{h} {s['registration']}  same combo in all rounds: {s['same_combo_all_rounds']}")
        for r in s["rounds"]:
            print(f"  hold {r['holdout']}: best {r['best_combo']} J={r['J_cal']:.4f} "
                  f"cal dI={[round(100 * x, 1) for x in r['cal_Id_err']]}% dT/sig={[round(x, 2) for x in r['cal_T_err_sigma']]} "
                  f"rms={[round(100 * x) for x in r['cal_rms']]}% | HOLD dI={100 * r['hold_Id_err']:.1f}% "
                  f"dT/sig={r['hold_T_err_sigma']:.2f} rms={100 * r['hold_rms']:.0f}% f={r['hold_f_kHz']:.0f}kHz "
                  f"defensible={r['defensible_c1_le_c2_le_bohm']} edge={r['at_grid_edge']}")


if __name__ == "__main__":
    main()

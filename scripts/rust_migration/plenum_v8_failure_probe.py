"""Plenum / feed contract v8: diagnosis of the scored failures (after the single scoring execution; never a re-score).

    python3 scripts/rust_migration/plenum_v8_failure_probe.py OUT.json

Reads the captured scoring inputs / outputs (reference_outputs_v8) and
* recomputes ST-P-01 from the captured Rust outputs (the report counted it in the verdict but did not print it);
* runs the failed stable-stratum vector P43-PROD-S-010 in both implementations at N / T1 / T2 (P43 and the P42
  samples of the same inputs), its stability class with the full spectra, and the per-leaf convergence estimators
  against the reused v7 stable-stratum envelopes.
"""
import gzip
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import es3_gaspath_parity as H  # noqa: E402

VID = "P43-PROD-S-010"
c, _, cpath = H.load_contract("plenum")
rdir = os.path.join(os.path.dirname(cpath), "reference_outputs_v8")


def gz(name):
    with gzip.open(os.path.join(rdir, name)) as f:
        return json.loads(f.read())


vectors = gz("inputs.json.gz")
rust = {r["id"]: r for r in gz("rust_outputs_at_scoring.json.gz")["results"]}
out = {"ST-P-01 (recomputed from the captured Rust outputs)": H.st_check(vectors, rust)}
H.ENV.update(H.load_envelope(c, H.load_contract("plenum")[1], "dev"))
H.V3_SCALE.update(H.v3_families())
v = next(x for x in vectors if x["id"] == VID)
cls = H.stability_class_of(v["entry"], v["args"], full=True)
out["class"] = {"class": cls["class"], "equilibria": [
    {"eq": e["eq"], "re_max": max((z[0] for z in e["eigenvalues"]), default=None),
     "lead": max(e["eigenvalues"], key=lambda z: (z[0], abs(z[1])), default=None)} for e in cls["equilibria"]]}
H.build_rust()
lv = c["transient_convergence_procedure_v3"]["tolerance_levels"]["PROD"]
runs = {}
for e in ("plenum.transient_case", "plenum.transient_run"):
    w = dict(v, entry=e, id=VID + ("" if e == "plenum.transient_case" else "-run"))
    if e == "plenum.transient_run":
        w["args"] = {k: x for k, x in v["args"].items() if k != "orbit_check"}
    for r, rt in (("N", None), ("T1", lv["T1_rtol"]), ("T2", lv["T2_rtol"])):
        p = H.py_run_rtol(w, rt)
        o, _, _, _ = H.run_rust([H.rust_req_rtol(w, rt)])
        runs[(e, r)] = {"python": p, "rust": H.rust_outcome(o["results"][0])}
fam = {}
for (e, r), d in runs.items():
    if e != "plenum.transient_case":
        continue
    for impl in ("python", "rust"):
        for f, leaves in H.family_leaves(e, d[impl][1]).items():
            for pth, x in leaves.items():
                fam.setdefault(f, {}).setdefault("/".join(map(str, pth)), {})[f"{impl}_{r}"] = x
failed = {x["path"] for x in json.load(open(os.path.join(os.path.dirname(cpath), "parity_report_v8.json")))[
    "per_test"]["failures_first_50"] if x["vector"] == VID}
rows = []
for f, leaves in fam.items():
    for pth, d in leaves.items():
        if pth not in failed:
            continue
        s = H.family_scale(H.V3_SCALE[f], v, d.get("python_T2"))
        row = {"path": pth, "family": f, "scale": s, **d}
        for impl in ("python", "rust"):
            xN, x1, x2 = (d.get(f"{impl}_{r}") for r in ("N", "T1", "T2"))
            if None not in (xN, x1, x2) and s:
                row[f"e_{impl}"] = (abs(xN - x2) + abs(x1 - x2)) / s
                row[f"E_{impl} (v7 S envelope)"] = H.ENV["envelopes"]["S"][impl]["PROD"]["P43"][f]["E"]
        if s and d.get("python_T2") is not None and d.get("rust_T2") is not None:
            row["cross_T2 / s"] = abs(d["rust_T2"] - d["python_T2"]) / s
        rows.append(row)
out["failed_leaves_convergence"] = rows
# P42 samples: valve opening per segment (oscillation amplitude in the last third of each segment)
seg = {}
for r in ("N", "T1", "T2"):
    for impl in ("python", "rust"):
        val = runs[("plenum.transient_run", r)][impl][1]
        for k, sg in enumerate(val["segments"]):
            u = [H.unj(x) if isinstance(x, str) else x for x in sg["u"]]
            t = sg["t"]
            late = [x for x, tt in zip(u, t) if tt >= 2 * sg["duration_s"] / 3]
            seg.setdefault(k, {})[f"{impl}_{r}"] = {"u_late_min": min(late), "u_late_max": max(late),
                                                    "u_end": u[-1]}
out["P42_valve_opening_late_third"] = seg
out["P43_status"] = {f"{impl}_{r}": (runs[("plenum.transient_case", r)][impl][1] or {}).get("reasons")
                     for impl in ("python", "rust") for r in ("N", "T1", "T2")}
json.dump(H.sanitize(out), open(sys.argv[1], "w"), indent=1, default=str)
print(json.dumps(H.sanitize({k: out[k] for k in ("class", "P43_status")}), default=str)[:3000])
for r_ in rows:
    print(json.dumps(H.sanitize(r_))[:700])
print(json.dumps(out["ST-P-01 (recomputed from the captured Rust outputs)"])[:600])
for k, x in seg.items():
    print(k, json.dumps(x)[:600])
print(math.nan if not rows else "rows", len(rows))

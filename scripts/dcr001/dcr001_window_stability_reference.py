"""Governed Python reference of the feed-loop stability class of the DCR-001 amendment v3 selected design
(docs/baseline/DCR-001/dcr001_eval_prereg_v3.json, ranking.governed_stability; A9.34: plenum / feed v8 PARITY_FAIL
stands, the Python reference governs the transient path).

The v1 method (scripts/dcr001/dcr001_feed_stability_reference.py, itself the M2 reference method) applied per window
operating point with its own effective capture area: for every coefficient set of the spec (nominal and the eight
unfavourable corners) and every (surface scenario, state, A_eff) row of that set, the contract-v8 input-only class from
the equilibria of event_sequence(intake state, P_set, WINDOW_S) with the registered v7 / v8 harness _py_equilibrium.
S stable, U unstable, R refused (dead-head at the setpoint). The intake records are the F1 unit-area records x A_eff
(pf.load_f1_records); the compressor is the F3 grid design with the module defaults and the spec's overrides.

    python3 scripts/dcr001/dcr001_window_stability_reference.py SPEC.json SPEC_SHA256 OUT.json
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HARNESS = "scripts/rust_migration/es3_gaspath_parity.py"
REFERENCE = "abep_sim/design/plenum_feed.py"
F3D = "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json"
F3D_SHA256 = "74a52aa749e1d071f76957e4f9ef4929c9d8ab302b183da3c5a5d9ba8d6d6923"
SCHEMA = "abep_dcr001_window_stability_python_reference_v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(spec_path: str, spec_sha: str, out: str) -> int:
    sp = Path(spec_path)
    if sha(sp) != spec_sha:
        raise SystemExit(f"{spec_path}: sha256 differs from {spec_sha} (refused)")
    if sha(ROOT / F3D) != F3D_SHA256:
        raise SystemExit(f"{F3D}: sha256 differs from the pinned F3 designs (refused)")
    spec = json.loads(sp.read_text())
    if spec.get("schema") != "abep_dcr001_window_stability_spec_v1":
        raise SystemExit("spec schema differs (refused)")
    import numpy as np
    import scipy
    from abep_sim.compressor import DragCompressor
    from abep_sim.design import architecture_optimizer as ao
    from abep_sim.design import compressor_synthesis as cs
    from abep_sim.design import plenum_feed as pf
    hs = importlib.util.spec_from_file_location("es3_gaspath_parity", ROOT / HARNESS)
    h = importlib.util.module_from_spec(hs)
    hs.loader.exec_module(h)
    up = ao.load_upstream_inputs(ROOT)
    fc = up.filters[spec["filter"]]
    grid = json.loads((ROOT / F3D).read_text())["design_grid"]
    design = grid[spec["compressor"]["f3_grid_index"]]
    if design["id"] != spec["compressor"]["id"]:
        raise SystemExit("spec compressor id differs from the F3 grid design (refused)")
    base = pf.CompressorPlant.from_design(design)
    pl = ao.plenum(spec["V_m3"], spec["wall"])
    c = spec["controller"]
    ctrl = pf.Controller(c["Kp"], c["Ti_s"], c["f_valve_hz"], c["authority"])
    r0 = spec["P_set_Pa"]
    it = spec["intake"]
    areas = sorted({r["area_m2"] for cset in spec["coefficient_sets"] for r in cset["rows"]})
    scen = {r["scenario"] for cset in spec["coefficient_sets"] for r in cset["rows"]}
    states = {r["state_id"] for cset in spec["coefficient_sets"] for r in cset["rows"]}
    f1 = ao.read_f1(ROOT)
    recs = pf.load_f1_records(f1, areas, scenarios=scen, states=states)
    by = {(r.candidate, r.scenario, r.state): r for r in recs}
    rows = []
    counts = {}
    for cset in spec["coefficient_sets"]:
        defaults = cs.module_defaults()
        for k in cset["overrides"]:
            if k not in defaults:
                raise SystemExit(f"unknown DragCompressor field {k} (refused)")
        plant = dataclasses.replace(base, comp=dataclasses.replace(base.comp, **cset["overrides"]))
        assert isinstance(plant.comp, DragCompressor)
        n = {"S": 0, "U": 0, "R": 0}
        for row in cset["rows"]:
            sc, st, a = row["scenario"], row["state_id"], row["area_m2"]
            des = by[(pf.f1_candidate_id(a, it["L_over_d"], it["phi"]), sc, st)]
            base_row = {"coefficient_set": cset["id"], "scenario": sc, "state_id": st, "area_m2": a}
            try:
                tr = pf.TransientRun(fc, plant, pl, ctrl, des, r0)
            except ValueError:
                rows.append({**base_row, "class": "R", "events": []})
                n["R"] += 1
                continue
            evs = [h._py_equilibrium(tr, x.intake, x.setpoint_Pa, x.density, x.feed_factor, x)
                   for x in pf.event_sequence(des, r0, pf.WINDOW_S)]
            unstable = any(e["eq"] == "UNSAT" and e["re_max"] > 0.0 for e in evs)
            cl = "U" if unstable else "S"
            n[cl] += 1
            rows.append({**base_row, "class": cl, "events": [{"eq": e["eq"], "re_max": e["re_max"]} for e in evs]})
        counts[cset["id"]] = n
    try:
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        commit = "UNKNOWN"
    rec = {
        "schema": SCHEMA,
        "dcr": "DCR-DBF1-001",
        "role": "governed Python reference (authoritative class); the Rust record cross-checks every row (R2)",
        "spec": {"path": spec_path, "sha256": spec_sha},
        "design_id": spec["design_id"],
        "window_s": pf.WINDOW_S,
        "reference": {"module": REFERENCE, "sha256": sha(ROOT / REFERENCE), "class_function": f"{HARNESS} _py_equilibrium",
                      "harness_sha256": sha(ROOT / HARNESS)},
        "producer": {"script": "scripts/dcr001/dcr001_window_stability_reference.py",
                     "script_sha256": sha(ROOT / "scripts/dcr001/dcr001_window_stability_reference.py")},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                        "repository_head": commit},
        "n_rows": len(rows),
        "class_counts_by_coefficient_set": counts,
        "rows": rows,
    }
    Path(out).write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))

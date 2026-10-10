"""Governed Python reference of the DBF-1 feed-loop stability class (NP-HALL-PARAMETRIC-ENVELOPE addendum A8,
P-FEED-STABILITY-DBF1; A9.34: plenum / feed v8 PARITY_FAIL stands, the Python reference governs the transient path).

For the DBF-1 upstream design (docs/baseline/DBF-1/dbf1_config_v1.json, sha256-pinned) and its controller, the
contract-v8 input-only stability class of every (surface scenario, required design state): the equilibria of
event_sequence(intake state, P_set, WINDOW_S) computed on the reference module's own functions by the registered v7 / v8
Python side (scripts/rust_migration/es3_gaspath_parity.py _py_equilibrium). S stable, U unstable (an UNSAT equilibrium
with Re lambda > 0), R refused (dead-head at the setpoint: TransientRun raises ValueError). No time-domain run.

    python3 scripts/m2/dbf1_feed_stability_reference.py OUT.json
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DBF1_CONFIG = "docs/baseline/DBF-1/dbf1_config_v1.json"
DBF1_CONFIG_SHA256 = "5bd76159fb9761b5c47619fb42217f05c24841d7009067ac71dcedf731759864"
HARNESS = "scripts/rust_migration/es3_gaspath_parity.py"
REFERENCE = "abep_sim/design/plenum_feed.py"


def sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def main(out: str) -> int:
    if sha(DBF1_CONFIG) != DBF1_CONFIG_SHA256:
        raise SystemExit(f"{DBF1_CONFIG}: sha256 differs from the pinned DBF-1 config (refused)")
    cfg = json.loads((ROOT / DBF1_CONFIG).read_text())["upstream"]
    import numpy as np
    import scipy
    from abep_sim.design import architecture_optimizer as ao
    from abep_sim.design import plenum_feed as pf
    spec = importlib.util.spec_from_file_location("es3_gaspath_parity", ROOT / HARNESS)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    up = ao.load_upstream_inputs(ROOT)
    fc = up.filters[cfg["filter"]]
    plant = up.plants[cfg["compressor"]]
    pl = ao.plenum(cfg["V_m3"], cfg["wall"])
    c = cfg["controller"]
    ctrl = pf.Controller(c["Kp"], c["Ti_s"], c["f_valve_hz"], c["authority"])
    r0 = cfg["P_set_Pa"]
    states = [s for s in ao.states() if s != "h200_f150"]
    rows = []
    for sc in cfg["scenarios"]:
        for st in states:
            des = up.records[(cfg["candidate"], sc, st)]
            try:
                tr = pf.TransientRun(fc, plant, pl, ctrl, des, r0)
            except ValueError:
                rows.append({"scenario": sc, "state_id": st, "class": "R", "events": []})
                continue
            evs = [h._py_equilibrium(tr, x.intake, x.setpoint_Pa, x.density, x.feed_factor, x)
                   for x in pf.event_sequence(des, r0, pf.WINDOW_S)]
            unstable = any(e["eq"] == "UNSAT" and e["re_max"] > 0.0 for e in evs)
            rows.append({"scenario": sc, "state_id": st, "class": "U" if unstable else "S",
                         "events": [{"eq": e["eq"], "re_max": e["re_max"]} for e in evs]})
    try:
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        commit = "UNKNOWN"
    rec = {
        "schema": "abep_m2_dbf1_feed_stability_python_reference_v1",
        "addendum": "NP-HALL-PARAMETRIC-ENVELOPE A8 (P-FEED-STABILITY-DBF1)",
        "role": "governed Python reference (authoritative class); the Rust harness cross-checks every row (R2)",
        "dbf1_config": {"path": DBF1_CONFIG, "sha256": DBF1_CONFIG_SHA256},
        "design_id": cfg["design_id"], "controller": c, "P_set_Pa": r0, "window_s": pf.WINDOW_S,
        "reference": {"module": REFERENCE, "sha256": sha(REFERENCE), "class_function": f"{HARNESS} _py_equilibrium",
                      "harness_sha256": sha(HARNESS)},
        "producer": {"script": "scripts/m2/dbf1_feed_stability_reference.py",
                     "script_sha256": sha("scripts/m2/dbf1_feed_stability_reference.py")},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                        "repository_head": commit},
        "n_rows": len(rows),
        "class_counts": {k: sum(1 for r in rows if r["class"] == k) for k in ("S", "U", "R")},
        "rows": rows,
    }
    Path(out).write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps(rec["class_counts"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

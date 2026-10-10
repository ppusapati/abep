"""Generate the post-G1 system.evaluate() identity fixture (A9.22 G1 governed baseline change, system.py completion).

tests/fixtures/evaluate_identity_base_9eb302c.json stays the immutable, historical no-change proof of A9.22 Phase B
(26,000 h mission basis). This script writes the SECOND fixture, tests/fixtures/evaluate_identity_g1.json, on the same
122 configurations (configs/build/encode imported unchanged from make_evaluate_identity_fixture.py), generated ONCE at
the commit that completed G1 in abep_sim/system.py (26,280 h mission-duration basis; 15,000 h labelled
SUBSYSTEM_FIRING_LIFE_ASSUMPTION for firing-integrated quantities):

    python tests/fixtures/make_evaluate_identity_fixture_g1.py --commit <sha of the G1 completion commit>

tests/test_raw_assessment_split.py compares evaluate() with it bit for bit, with no exclusion. Do not regenerate it
unless a governed model change is recorded in docs/HISTORY.md: regenerating would hide a numerical change.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "evaluate_identity_g1.json"


def _base():
    spec = importlib.util.spec_from_file_location("make_evaluate_identity_fixture", HERE / "make_evaluate_identity_fixture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", required=True, help="git commit the fixture is generated at (G1 completion commit)")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(HERE.parents[1]))
    from abep_sim import operating_inputs as OI
    from abep_sim.system import evaluate
    g = _base()
    rows = []
    for kw in g.configs():
        r = evaluate(g.build(kw))
        rows.append({"config": kw, "keys": list(r), "values": [g.encode(r[k]) for k in r]})
    OUT.write_text(json.dumps({
        "base_commit": a.commit,
        "generator": "tests/fixtures/make_evaluate_identity_fixture_g1.py",
        "purpose": "system.evaluate() output after the A9.22 G1 governed baseline change (system.py completion); "
                   "reference for future no-change checks. The 9eb302c fixture remains the Phase B historical proof.",
        "mission_hours_basis_h": OI.MISSION_HOURS, "firing_hours_assumption_h": OI.FIRING_HOURS,
        "firing_hours_label": OI.FIRING_HOURS_LABEL,
        "rows": rows}, separators=(",", ":")) + "\n")
    print(f"wrote {OUT} ({len(rows)} configs)")


if __name__ == "__main__":
    main()

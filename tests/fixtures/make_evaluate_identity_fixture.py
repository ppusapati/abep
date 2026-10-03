"""Generate the frozen system.evaluate() identity fixture (A9.22 G6/G7 raw/assessment split, Phase B).

The fixture was generated ONCE at base commit 9eb302c (branch claude/nifty-ramanujan-w68f9z, before the
raw-physics / assessment split) with:

    python tests/fixtures/make_evaluate_identity_fixture.py

and is compared bit-for-bit (key order, key set, exact float repr) by tests/test_raw_assessment_split.py. Do not
regenerate it after the split unless a governed model change is recorded: regenerating would hide a numerical change.
"""
from __future__ import annotations
import itertools
import json
import sys
from pathlib import Path

OUT = Path(__file__).with_name("evaluate_identity_base_9eb302c.json")


def configs():
    """Config keyword sets (JSON-serialisable); build() turns one into a Config."""
    out = []
    archs = ["hall_1stage", "hall_ecr", "hall_rf", "hall_1stage_mwcat", "rf_gridded_ion", "ecr_gridless", "helicon"]
    for i, (arch, alt, sol, area, vd) in enumerate(itertools.product(archs, (180, 230), ("low", "high"), (0.5, 2.0), (160, 300))):
        out.append({"architecture": arch, "alt_km": alt, "solar": sol,
                    "intake": {"area_m2": area, "accommodation": (0.3, 0.7)[i % 2]},
                    "compressor": {"ratio": (100, 2000)[(i // 2) % 2]}, "vd_V": vd})
    tp = {"accommodation": 0.8, "use_tpmc": True, "L_over_d": 5}
    out += [
        {"architecture": "hall_ecr", "alt_km": 200, "solar": "mean", "intake": {"area_m2": 1.0}, "compressor": {"ratio": 500},
         "vd_V": None, "T_required_mN": 20.0, "body_area_m2": 0.3},
        {"architecture": "hall_1stage", "alt_km": 200, "solar": "mean", "intake": {"area_m2": 1.5}, "compressor": {"ratio": 500},
         "vd_V": 250, "budgets": {"m_cbe_target_kg": 20.0, "ic_intake": 0.5, "ic_compressor": 0.3, "p_margin_frac": 0.2}},
        {"architecture": "hall_rf", "alt_km": 200, "solar": "mean", "intake": {"area_m2": 0.7, **tp},
         "compressor": {"ratio": 2000}, "vd_V": 275},
        # physics paths (test_sim configurations + variants)
        {"architecture": "hall_ecr", "alt_km": 200, "solar": "mean", "intake": {"area_m2": 0.5, **tp},
         "compressor": {"ratio": 2000}, "vd_V": 300, "gaspath_physics": True},
        {"architecture": "hall_1stage", "alt_km": 200, "solar": "mean", "intake": {"area_m2": 1.3, **tp},
         "compressor": {"ratio": 2000}, "vd_V": 275, "gaspath_physics": True},
        {"architecture": "hall_1stage", "alt_km": 200, "solar": "mean", "intake": {"area_m2": 0.7, **tp},
         "compressor": {"ratio": 2000}, "vd_V": 300, "gaspath_physics": True, "plasma_physics": True, "hall_L_m": 0.20},
        {"architecture": "hall_ecr", "alt_km": 200, "solar": "mean", "intake": {"area_m2": 0.7, **tp},
         "compressor": {"ratio": 2000}, "vd_V": 300, "gaspath_physics": True, "plasma_physics": True, "hall_L_m": 0.20},
        {"architecture": "hall_1stage", "alt_km": 200, "solar": "mean", "intake": {"area_m2": 0.7, **tp},
         "compressor": {"ratio": 2000}, "vd_V": 275, "gaspath_physics": True, "plasma_physics": True,
         "engineering_physics": True, "hall_L_m": 0.20, "hall_shielding": 0.03, "hall_wall_mm": 6.0, "blade_coating_um": 50,
         "xe_aug_hours": 500},
        {"architecture": "hall_ecr", "alt_km": 200, "solar": "mean", "intake": {"area_m2": 0.7, **tp},
         "compressor": {"ratio": 2000}, "vd_V": 275, "gaspath_physics": True, "plasma_physics": True,
         "engineering_physics": True, "hall_L_m": 0.20, "xe_aug_hours": 500},
        {"architecture": "hall_1stage", "alt_km": 200, "solar": "mean", "intake": {"area_m2": 0.7}, "compressor": {"ratio": 2000},
         "vd_V": 275, "engineering_physics": True},
    ]
    return out


def build(kw: dict):
    from abep_sim.intake import IntakeParams, CompressorParams
    from abep_sim.system import Config, Budgets
    kw = dict(kw)
    intake = IntakeParams(**kw.pop("intake"))
    comp = CompressorParams(**kw.pop("compressor"))
    budgets = Budgets(**kw.pop("budgets", {}))
    return Config(intake=intake, compressor=comp, budgets=budgets, **kw)


def encode(v):
    """Exact, JSON-safe, type-preserving encoding: floats by repr (round-trips bit-exactly, incl. inf/nan)."""
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    try:
        import numpy as np
        if isinstance(v, np.bool_):
            return {"np_bool": bool(v)}
        if isinstance(v, np.integer):
            return {"np_int": int(v)}
        if isinstance(v, np.floating):
            return {"np_float": repr(float(v))}
    except ImportError:
        pass
    if isinstance(v, int):
        return {"int": v}
    if isinstance(v, float):
        return {"float": repr(v)}
    if isinstance(v, (list, tuple)):
        return {"list" if isinstance(v, list) else "tuple": [encode(x) for x in v]}
    if isinstance(v, dict):
        return {"map": [[k, encode(x)] for k, x in v.items()]}
    raise TypeError(f"unencodable {type(v)}: {v!r}")


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from abep_sim.system import evaluate
    rows = []
    for kw in configs():
        r = evaluate(build(kw))
        rows.append({"config": kw, "keys": list(r), "values": [encode(r[k]) for k in r]})
    OUT.write_text(json.dumps({"base_commit": "9eb302c06241c8e8a369334a6bdc5bc559227143",
                               "generator": "tests/fixtures/make_evaluate_identity_fixture.py",
                               "purpose": "system.evaluate() legacy output before the A9.22 raw/assessment split",
                               "rows": rows}, separators=(",", ":")) + "\n")
    print(f"wrote {OUT} ({len(rows)} configs)")


if __name__ == "__main__":
    main()

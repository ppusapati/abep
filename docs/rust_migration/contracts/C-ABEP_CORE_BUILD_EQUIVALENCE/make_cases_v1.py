"""Generate cases_v1.json for ADDENDUM-ABEP-CORE-BUILD-EQUIVALENCE-V1 (addendum_v1.json).

The cases are the golden vectors and edge cases of the Kernel-1 comparison set (docs/performance/abep_core/
parity_prereg_v2.json comparison_set; no randomized domain), with seeds derived from the prereg v2 DEVELOPMENT master
seed (1) by the prereg v2 Rust-seed derivation. Every floating input is written as its shortest round-trip repr, so the
recorded extension (via Python) and the Rust builds read bit-identical inputs. Run once at registration:

    python3 docs/rust_migration/contracts/C-ABEP_CORE_BUILD_EQUIVALENCE/make_cases_v1.py
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT)

from abep_sim.atmosphere import atmosphere  # noqa: E402
from abep_sim.constants import M_SPECIES  # noqa: E402

DEV_MASTER_SEED = 1          # parity_prereg_v2 campaign_seeds.development_master_seed
KERNEL_INDEX = {"K1_entry": 1, "K2_diffuse": 2, "K3_cll": 3, "K4_trace": 4, "K5_clausing": 5}
D_M = 10.0 * 1e-3            # channel diameter (IntakeGeometry default d_mm = 10)
R_M = D_M / 2


def seed(j: int, k: int, s: int) -> int:
    """prereg v2 derivation: numpy.random.default_rng(SeedSequence([master, j, k, s])) -> one uint64 draw."""
    g = np.random.default_rng(np.random.SeedSequence([DEV_MASTER_SEED, j, k, s]))
    return int(g.integers(0, 2 ** 64, dtype=np.uint64))


def main() -> None:
    atm = atmosphere(200.0, "mean", use_msis=False)
    V, T = float(atm["V"]), float(atm["T"])
    cases: dict[str, list] = {k: [] for k in KERNEL_INDEX}

    def add(kernel: str, cid: str, group: str, params: dict, n: int, f64: dict, extra: dict | None = None,
            input_seed: bool = False):
        j, k = KERNEL_INDEX[kernel], len(cases[kernel])
        c = {"id": cid, "kernel": kernel, "group": group, "params": params, "n": n, "seed": seed(j, k, 1),
             "input_seed": seed(j, k, 2) if input_seed else None, "f64": f64}
        c.update(extra or {})
        cases[kernel].append(c)

    # K1 entry: 3 theta x 3 species golden (200 km mean), 5 edge; n = 2000 (prereg v2 n_per_replicate)
    for th in (0, 2, 5):
        for sp in ("O", "N2", "O2"):
            add("K1_entry", f"K1-G-th{th}-{sp}", "golden", {"theta_deg": th, "species": sp}, 2000,
                {"v_drift": V, "theta": math.radians(th), "t": T, "m": M_SPECIES[sp]})
    for eid, th, sp in (("E1-01", 30, "N2"), ("E1-02", 60, "N2"), ("E1-03", 85, "N2"), ("E1-04", 90, "N2"),
                        ("E1-05", 0, "Xe")):
        add("K1_entry", f"K1-{eid}", "edge", {"theta_deg": th, "species": sp}, 2000,
            {"v_drift": V, "theta": math.radians(th), "t": T, "m": M_SPECIES[sp]})

    # K2 diffuse: 3 species x 2 normal sets golden, 4 edge; n = 20000
    for sp in ("O", "N2", "O2"):
        for ns in ("plus_z", "x_y_wall"):
            add("K2_diffuse", f"K2-G-{sp}-{ns}", "golden", {"species": sp, "T_w_K": 350.0}, 20000,
                {"t_w": 350.0, "m": M_SPECIES[sp]}, {"normal_set": ns})
    for eid, tw, ns in (("E2-01", 100.0, "x_y_wall"), ("E2-02", 1000.0, "x_y_wall"), ("E2-03", 350.0, "minus_z"),
                        ("E2-04", 350.0, "plus_x")):
        add("K2_diffuse", f"K2-{eid}", "edge", {"species": "N2", "T_w_K": tw}, 20000,
            {"t_w": tw, "m": M_SPECIES["N2"]}, {"normal_set": ns})

    # K3 CLL: 3 species x 9 (alpha_n, alpha_t) golden, 2 edge; v_in = abep_core entry at 200 km mean, theta 5 deg
    pairs = ((0, 0), (1, 1), (0, 1), (1, 0), (0.2, 0.2), (0.5, 0.5), (0.8, 0.8), (0.3, 0.9), (0.9, 0.3))
    for sp in ("O", "N2", "O2"):
        for an, at in pairs:
            add("K3_cll", f"K3-G-{sp}-an{an}-at{at}", "golden", {"species": sp, "alpha_n": an, "alpha_t": at,
                                                                  "T_w_K": 350.0}, 20000,
                {"v_drift": V, "theta": math.radians(5), "t": T, "m": M_SPECIES[sp], "t_w": 350.0,
                 "alpha_n": float(an), "alpha_t": float(at)}, {"normal_set": "x_y_wall"}, input_seed=True)
    for eid, an, at, tw in (("E3-01", 1.0, 1.0, 100.0), ("E3-02", 0.5, 0.5, 1000.0)):
        add("K3_cll", f"K3-{eid}", "edge", {"species": "N2", "alpha_n": an, "alpha_t": at, "T_w_K": tw}, 20000,
            {"v_drift": V, "theta": math.radians(5), "t": T, "m": M_SPECIES["N2"], "t_w": tw, "alpha_n": an,
             "alpha_t": at}, {"normal_set": "x_y_wall"}, input_seed=True)

    # K4 trace: 4 L/d x 5 alpha x 3 theta x 3 species x 2 scattering golden (n = 8000), 17 edge (n = 4000)
    def k4(cid, group, params, n, ld, th, sp, scat, alpha, alpha_n=None, alpha_t=None, tw=350.0, mh=200, cap=5000):
        add("K4_trace", cid, group, params, n,
            {"v_drift": V, "theta": math.radians(th), "t": T, "m": M_SPECIES[sp], "r": R_M, "l": ld * D_M,
             "alpha": float(alpha), "t_w": tw, "alpha_n": alpha_n, "alpha_t": alpha_t, "unresolved_tol": 1e-3},
            {"scattering": scat, "max_hits": mh, "max_hits_cap": cap}, input_seed=True)

    for ld in (3, 5, 10, 20):
        for al in (0.0, 0.2, 0.5, 0.8, 1.0):
            for th in (0, 2, 5):
                for sp in ("O", "N2", "O2"):
                    for scat in ("maxwell", "cll"):
                        k4(f"K4-G-L{ld}-a{al}-th{th}-{sp}-{scat}", "golden",
                           {"L_over_d": ld, "alpha": al, "theta_deg": th, "species": sp, "scattering": scat},
                           8000, ld, th, sp, scat, al)
    edges = (
        ("E4-01", dict(ld=0.001, al=1.0, scat="maxwell", th=0)),
        ("E4-02", dict(ld=0.1, al=0.5, scat="maxwell", th=5)),
        ("E4-03", dict(ld=5, al=0.0, scat="maxwell", th=0)),
        ("E4-04", dict(ld=5, al=1.0, scat="maxwell", th=0)),
        ("E4-05", dict(ld=5, al=0.0, an=0.0, at=0.0, scat="cll", th=5)),
        ("E4-06", dict(ld=5, al=1.0, an=1.0, at=1.0, scat="cll", th=5)),
        ("E4-07", dict(ld=5, al=0.0, an=0.0, at=1.0, scat="cll", th=5)),
        ("E4-08", dict(ld=5, al=1.0, an=1.0, at=0.0, scat="cll", th=5)),
        ("E4-09", dict(ld=5, al=0.8, scat="maxwell", th=30)),
        ("E4-10", dict(ld=5, al=0.8, scat="maxwell", th=60)),
        ("E4-11", dict(ld=5, al=0.8, scat="maxwell", th=85)),
        ("E4-12", dict(ld=2, al=0.8, scat="cll", th=90)),
        ("E4-13", dict(ld=50, al=1.0, scat="maxwell", th=0)),
        ("E4-14", dict(ld=20, al=1.0, scat="maxwell", th=0, mh=2, cap=4)),
        ("E4-15", dict(ld=5, al=0.5, scat="maxwell", th=0, sp="Xe")),
        ("E4-16", dict(ld=5, al=0.5, scat="maxwell", th=0, tw=100.0)),
        ("E4-17", dict(ld=5, al=0.5, scat="cll", th=0, tw=1000.0)),
    )
    for eid, e in edges:
        sp = e.get("sp", "N2")
        params = {"L_over_d": e["ld"], "alpha": e["al"], "theta_deg": e["th"], "species": sp,
                  "scattering": e["scat"], "T_w_K": e.get("tw", 350.0), "max_hits": e.get("mh", 200),
                  "max_hits_cap": e.get("cap", 5000)}
        if "an" in e:
            params.update({"alpha_n": e["an"], "alpha_t": e["at"]})
        k4(f"K4-{eid}", "edge", params, 4000, e["ld"], e["th"], sp, e["scat"], e["al"], e.get("an"), e.get("at"),
           e.get("tw", 350.0), e.get("mh", 200), e.get("cap", 5000))

    # K5 Clausing: 4 L/d x 5 alpha x 3 species golden (Maxwell), 3 edge; n = 20000
    for ld in (3, 5, 10, 20):
        for al in (0.0, 0.2, 0.5, 0.8, 1.0):
            for sp in ("O", "N2", "O2"):
                add("K5_clausing", f"K5-G-L{ld}-a{al}-{sp}", "golden", {"L_over_d": ld, "alpha": al, "species": sp},
                    20000, {"r": R_M, "l": ld * D_M, "alpha": al, "t_w": 350.0, "m": M_SPECIES[sp]})
    for eid, ld, al in (("E5-01", 0.001, 1.0), ("E5-02", 50, 1.0), ("E5-03", 5, 0.0)):
        add("K5_clausing", f"K5-{eid}", "edge", {"L_over_d": ld, "alpha": al, "species": "N2"}, 20000,
            {"r": R_M, "l": ld * D_M, "alpha": al, "t_w": 350.0, "m": M_SPECIES["N2"]})

    normal_sets = {
        "plus_z": [[0.0, 0.0, 1.0]],
        "minus_z": [[0.0, 0.0, -1.0]],
        "plus_x": [[1.0, 0.0, 0.0]],
        "x_y_wall": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0],
                     [0.6, 0.8, 0.0], [-0.8, 0.6, 0.0], [-0.6, -0.8, 0.0], [0.8, -0.6, 0.0]],
    }
    flat = [c for k in KERNEL_INDEX for c in cases[k]]
    doc = {
        "schema": "abep_core_build_equivalence_cases_v1",
        "addendum_id": "ADDENDUM-ABEP-CORE-BUILD-EQUIVALENCE-V1",
        "generated_by": "docs/rust_migration/contracts/C-ABEP_CORE_BUILD_EQUIVALENCE/make_cases_v1.py",
        "development_master_seed": DEV_MASTER_SEED,
        "seed_derivation": "seed = numpy.random.default_rng(numpy.random.SeedSequence([1, j, k, 1])).integers(0, 2**64, "
                           "dtype=uint64); input_seed the same with s = 2; j = kernel index (K1=1 .. K5=5), k = 0-based "
                           "case index within the kernel in this file's order",
        "atmosphere": {"call": "abep_sim.atmosphere.atmosphere(200.0, 'mean', use_msis=False)", "V": V, "T": T},
        "normal_sets": normal_sets,
        "normal_rule": "normal i of a set = set[i mod len(set)]",
        "counts": {k: len(cases[k]) for k in KERNEL_INDEX},
        "cases": flat,
    }
    with open(os.path.join(HERE, "cases_v1.json"), "w") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print({k: len(v) for k, v in cases.items()}, len(flat))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""A9.7 Rust lane - pre-registered parity campaign: Python reference (abep_sim/intake_tpmc.py) vs abep_core (Rust).

Lane fo_a9_7_rust_kernels. Implements docs/performance/abep_core/parity_prereg_v1.json exactly (committed before any
comparison) and writes docs/performance/abep_core/parity_report_v1.json (+ .md rendered from it) with the verdict
ADMITTED / NOT_ADMITTED per kernel and the measured speed-up on the F0 workload. The Python reference stays
authoritative whatever the verdict; nothing here wires Rust into production paths, frozen data or goldens.

Commands
  python scripts/verify_abep_core.py                 scoring campaign (needs the built abep_core extension; appends to
                                                     the campaign history, never discards an earlier execution)
  python scripts/verify_abep_core.py --dev [--only K4] [--limit 10]
                                                     development comparison with the development seed; prints only,
                                                     never writes or scores (prereg campaign_seeds.development_rule)
  python scripts/verify_abep_core.py --check         re-derives every per-test / aggregate / kernel verdict from the
                                                     stored numbers, checks the prereg hash and the rendered MD (fast;
                                                     abep_core not needed)
  python scripts/verify_abep_core.py --check --recompute 3
                                                     additionally recomputes the first 3 vectors of every kernel and
                                                     requires bitwise-identical numbers (needs abep_core, same build)
  python scripts/verify_abep_core.py --render-md     re-render the MD from the JSON

Non-interactive CI entry points (.github/workflows/rust-parity.yml, docs/ci/RUST_PARITY.md; owner A9.14 S10.4
RUST-OQ-02). They add exit codes only; no verdict rule, tolerance, seed or vector changes:
  python scripts/verify_abep_core.py --source-status [--github-output FILE]
                                                     prints whether the current PROVENANCE_SOURCES match the report's
                                                     build_provenance, whether the reference matches the prereg and
                                                     whether the importable extension is the recorded binary; with
                                                     --github-output also appends key=value lines to FILE; exit 0
  python scripts/verify_abep_core.py --dev --strict  full development comparison (development seed, never scored,
                                                     never written); exit 1 if any development check disagrees (a
                                                     regression smoke, not a verdict: it never admits a kernel)

The extension is built outside the repository environment (abep_core/README.md), e.g. into a scratch venv created
with --system-site-packages; run this script with that venv's python.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from abep_sim import intake_tpmc as REF                     # noqa: E402  (reference, authoritative)
from abep_sim.atmosphere import atmosphere                  # noqa: E402
from abep_sim.constants import K_B, M_SPECIES               # noqa: E402
from abep_sim.design import tpmc_backend as TB              # noqa: E402

PREREG_REL = "docs/performance/abep_core/parity_prereg_v1.json"
REPORT_REL = "docs/performance/abep_core/parity_report_v1.json"
MD_REL = "docs/performance/abep_core/parity_report_v1.md"
F0_REL = "docs/performance/PERFORMANCE_BASELINE_98fbbb9.json"
LANE = "fo_a9_7_rust_kernels"
DIRECTIVE = "docs/decisions/OD_2026_10_01_A9_7_ARCHITECTURE_FREEZE_DESIGN_SYNTHESIS.md"
KERNEL_INDEX = {"K1_entry": 1, "K2_diffuse": 2, "K3_cll": 3, "K4_trace": 4, "K5_clausing": 5}
D_MM = 10.0                       # IntakeGeometry default channel diameter used for the frozen surface
T_W_GOLDEN = 350.0                # IntakeGeometry default wall temperature used for the frozen surface
FORBIDDEN_WORDS = ("PASS", "SELECTED", "WINNER", "QUALIFIED")


def _p(rel):
    return os.path.join(ROOT, rel)


def sha256_file(rel):
    with open(_p(rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_prereg():
    with open(_p(PREREG_REL)) as fh:
        return json.load(fh)


def gen(master, j, k, s):
    return np.random.default_rng(np.random.SeedSequence([int(master), int(j), int(k), int(s)]))


def mass_of(species, atm):
    return atm["m_mean"] if species == "mean" else M_SPECIES[species]


def _atm(alt=200.0, solar="mean"):
    return atmosphere(float(alt), solar)


def _f(x):
    """JSON-safe float (full repr precision; NaN/inf -> None)."""
    if x is None:
        return None
    x = float(x)
    return x if math.isfinite(x) else None


# --------------------------------------------------------------------------------------------------------------------
# comparison set (exactly as pre-registered)
# --------------------------------------------------------------------------------------------------------------------
def golden_grid(pre):
    """intake_surface_v1 grid from the frozen JSON, cross-checked against the CSV unique values."""
    import pandas as pd
    meta = json.load(open(_p("abep_sim/data/intake_surface_v1.json")))
    df = pd.read_csv(_p("abep_sim/data/intake_surface_v1.csv"))
    g = meta["grid"]
    ax = pre["comparison_set"]["golden_vectors"]["axes"]
    checks = {"L_over_d": "L_over_d", "phi": "phi", "alpha": "alpha", "theta_deg": "theta_deg"}
    for k, col in checks.items():
        if sorted(float(x) for x in g[k]) != sorted(float(x) for x in df[col].unique()):
            raise SystemExit(f"golden grid mismatch JSON vs CSV on {k}")
        if sorted(float(x) for x in g[k]) != sorted(float(x) for x in ax[k]):
            raise SystemExit(f"golden grid mismatch JSON vs prereg on {k}")
    if sorted(meta["species"]) != sorted(ax["species"]) or sorted(df["species"].unique()) != sorted(ax["species"]):
        raise SystemExit("golden species mismatch")
    if sorted(meta["scattering"]) != sorted(ax["scattering"]) or sorted(df["scattering"].unique()) != sorted(ax["scattering"]):
        raise SystemExit("golden scattering mismatch")
    return ax


def build_vectors(pre, master):
    """Return {kernel: [vector dict]} in the registered order: golden, then edge cases, then randomized domain."""
    ax = golden_grid(pre)
    cs = pre["comparison_set"]
    V = {k: [] for k in KERNEL_INDEX}
    # ---------------- golden
    for ld in ax["L_over_d"]:
        for al in ax["alpha"]:
            for th in ax["theta_deg"]:
                for sp in ax["species"]:
                    for sc in ax["scattering"]:
                        V["K4_trace"].append(dict(id=f"G4-ld{ld}-a{al}-th{th}-{sp}-{sc}", group="golden", L_over_d=float(ld),
                                                  alpha=float(al), theta_deg=float(th), species=sp, scattering=sc,
                                                  alt=200.0, solar="mean", T_w_K=T_W_GOLDEN, n=8000))
    for ld in ax["L_over_d"]:
        for al in ax["alpha"]:
            for sp in ax["species"]:
                V["K5_clausing"].append(dict(id=f"G5-ld{ld}-a{al}-{sp}", group="golden", L_over_d=float(ld), alpha=float(al),
                                             species=sp, T_w_K=T_W_GOLDEN, n=20000))
    for th in ax["theta_deg"]:
        for sp in ax["species"]:
            V["K1_entry"].append(dict(id=f"G1-th{th}-{sp}", group="golden", theta_deg=float(th), species=sp, alt=200.0,
                                      solar="mean"))
    for sp in ax["species"]:
        for ns in ("plus_z", "x_y_wall"):
            V["K2_diffuse"].append(dict(id=f"G2-{sp}-{ns}", group="golden", species=sp, normal_set=ns, T_w_K=T_W_GOLDEN,
                                        n=20000))
    pairs = [(0, 0), (1, 1), (0, 1), (1, 0), (0.2, 0.2), (0.5, 0.5), (0.8, 0.8), (0.3, 0.9), (0.9, 0.3)]
    for sp in ax["species"]:
        for an, at in pairs:
            V["K3_cll"].append(dict(id=f"G3-{sp}-an{an}-at{at}", group="golden", species=sp, alpha_n=float(an),
                                    alpha_t=float(at), T_w_K=T_W_GOLDEN, n=20000))
    # ---------------- edge cases
    ec = cs["edge_cases"]
    for e in ec["K4"]:
        v = dict(group="edge", species="N2", alt=200.0, solar="mean", T_w_K=350.0, n=4000, max_hits=200, max_hits_cap=5000,
                 unresolved_tol=1e-3)
        v.update({k: e[k] for k in e if k != "note"})
        v.setdefault("alpha", None)
        if v["scattering"] == "cll" and v["alpha"] is None and "alpha_n" not in v:
            raise SystemExit(f"edge {e['id']}: cll without accommodation")
        if v["alpha"] is None:
            v["alpha"] = 0.0          # unused by CLL when alpha_n and alpha_t are both given (reference semantics)
        V["K4_trace"].append(v)
    for e in ec["K5"]:
        V["K5_clausing"].append(dict(group="edge", species="N2", T_w_K=350.0, n=20000, **e))
    for e in ec["K1"]:
        v = dict(group="edge", species="N2", alt=200.0, solar="mean")
        v.update(e)
        V["K1_entry"].append(v)
    for e in ec["K2"]:
        V["K2_diffuse"].append(dict(group="edge", species="N2", n=20000, **e))
    for e in ec["K3"]:
        V["K3_cll"].append(dict(group="edge", species="N2", n=20000, **e))
    # ---------------- randomized domain (field order as registered)
    rd = cs["randomized_domain"]
    sp_choices = ("O", "N2", "O2", "mean")
    alts, sols = (180.0, 200.0, 230.0), ("low", "mean", "high")
    r = gen(master, 4, 0, 3)
    for i in range(rd["K4_count"]):
        ld = float(math.exp(r.uniform(math.log(0.5), math.log(30.0))))
        sc = "maxwell" if r.uniform() < 0.5 else "cll"
        if sc == "maxwell":
            al = float(r.uniform()); an = at = None
        else:
            an = float(r.uniform()); at = float(r.uniform()); al = 0.0
        th = float(r.uniform(0.0, 15.0))
        sp = sp_choices[int(r.integers(0, 4))]
        alt = alts[int(r.integers(0, 3))]; sol = sols[int(r.integers(0, 3))]
        tw = float(r.uniform(250.0, 450.0))
        v = dict(id=f"R4-{i:02d}", group="random", L_over_d=ld, scattering=sc, alpha=al, theta_deg=th, species=sp,
                 alt=alt, solar=sol, T_w_K=tw, n=8000)
        if sc == "cll":
            v.update(alpha_n=an, alpha_t=at)
        V["K4_trace"].append(v)
    r = gen(master, 5, 0, 3)
    for i in range(rd["K5_count"]):
        ld = float(math.exp(r.uniform(math.log(0.5), math.log(30.0)))); al = float(r.uniform())
        sp = sp_choices[int(r.integers(0, 4))]; tw = float(r.uniform(250.0, 450.0))
        V["K5_clausing"].append(dict(id=f"R5-{i:02d}", group="random", L_over_d=ld, alpha=al, species=sp, T_w_K=tw, n=20000))
    r = gen(master, 1, 0, 3)
    for i in range(rd["K1_count"]):
        th = float(r.uniform(0.0, 15.0)); sp = sp_choices[int(r.integers(0, 4))]
        alt = alts[int(r.integers(0, 3))]; sol = sols[int(r.integers(0, 3))]
        V["K1_entry"].append(dict(id=f"R1-{i:02d}", group="random", theta_deg=th, species=sp, alt=alt, solar=sol))
    r = gen(master, 2, 0, 3)
    for i in range(rd["K2_count"]):
        tw = float(r.uniform(250.0, 450.0)); sp = sp_choices[int(r.integers(0, 4))]
        V["K2_diffuse"].append(dict(id=f"R2-{i:02d}", group="random", T_w_K=tw, species=sp, normal_set="x_y_wall", n=20000))
    r = gen(master, 3, 0, 3)
    for i in range(rd["K3_count"]):
        an = float(r.uniform()); at = float(r.uniform()); tw = float(r.uniform(250.0, 450.0))
        sp = sp_choices[int(r.integers(0, 4))]
        V["K3_cll"].append(dict(id=f"R3-{i:02d}", group="random", alpha_n=an, alpha_t=at, T_w_K=tw, species=sp, n=20000))
    for k, v in V.items():
        exp = cs["vector_totals"][k]
        if len(v) != exp:
            raise SystemExit(f"vector count {k}: built {len(v)} != registered {exp}")
    return V


# --------------------------------------------------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------------------------------------------------
def _mean_se(x):
    x = np.asarray(x, dtype=float)
    c = int(x.size)
    if c == 0:
        return (None, None, 0)
    m = float(x.mean())
    se = float(x.std(ddof=1) / math.sqrt(c)) if c > 1 else None
    return (m, se, c)


def _frac(mask):
    n = int(mask.size)
    if n == 0:
        return (None, None, 0)
    p = float(mask.mean())
    return (p, math.sqrt(p * (1.0 - p) / n), n)


def k4_observables(v0, out):
    col, v, hits, back, _unres = out
    alive = ~(col | back)
    h = hits.astype(float)
    dpz = v0[:, 2] - np.where(back, v[:, 2], 0.0)
    v2 = (v * v).sum(1)
    return {
        "f_trans": _frac(col), "f_back": _frac(back), "f_unres": _frac(alive),
        "mean_hits": _mean_se(h), "mean_hits2": _mean_se(h * h),
        "mean_vz_trans": _mean_se(v[col, 2]), "mean_v2_trans": _mean_se(v2[col]),
        "mean_vz_back": _mean_se(v[back, 2]), "mean_v2_back": _mean_se(v2[back]),
        "mean_dpz": _mean_se(dpz),
    }


CONDITIONAL = ("mean_vz_trans", "mean_v2_trans", "mean_vz_back", "mean_v2_back")


def score(py, rs, z, min_count=None):
    """py, rs = (mean, se, count). Returns a test record [py, se_py, rs, se_rs, z_or_None, status]."""
    mp, sp, cp = py
    mr, sr, cr = rs
    if min_count is not None and (cp < min_count or cr < min_count):
        return [_f(mp), _f(sp), _f(mr), _f(sr), None, "NOT_SCORED"]
    if mp is None or mr is None or sp is None or sr is None:
        return [_f(mp), _f(sp), _f(mr), _f(sr), None, "NOT_SCORED"]
    return rescore([mp, sp, mr, sr], z)


def rescore(rec, z):
    mp, sp, mr, sr = rec[:4]
    diff = mr - mp
    se = math.sqrt(sp * sp + sr * sr)
    if se == 0.0:
        ok = abs(diff) <= 1e-12 * max(1.0, abs(mp))
        return [_f(mp), _f(sp), _f(mr), _f(sr), None, "AGREE_EXACT" if ok else "DISAGREE_EXACT"]
    zz = diff / se
    return [_f(mp), _f(sp), _f(mr), _f(sr), zz, "WITHIN" if abs(zz) <= z else "OUTSIDE"]


# --------------------------------------------------------------------------------------------------------------------
# per-kernel evaluation of one vector
# --------------------------------------------------------------------------------------------------------------------
def run_k4(vec, master, k, z, min_count, inv):
    atm = _atm(vec.get("alt", 200.0), vec.get("solar", "mean"))
    m = mass_of(vec["species"], atm)
    V = atm.get("V_rel", atm["V"]); T = atm["T"]
    R = D_MM * 1e-3 / 2; L = vec["L_over_d"] * D_MM * 1e-3
    v0 = REF._flux_weighted_entry(gen(master, 4, k, 2), vec["n"], V, math.radians(vec["theta_deg"]), T, m)
    kw = dict(max_hits=vec.get("max_hits", 200), scattering=vec["scattering"], alpha_n=vec.get("alpha_n"),
              alpha_t=vec.get("alpha_t"), unresolved_tol=vec.get("unresolved_tol", 1e-3),
              max_hits_cap=vec.get("max_hits_cap", 5000))
    out_py = TB.trace_channel(gen(master, 4, k, 0), v0, R, L, vec["alpha"], vec["T_w_K"], m, backend="python", **kw)
    out_rs = TB.trace_channel(gen(master, 4, k, 1), v0, R, L, vec["alpha"], vec["T_w_K"], m, backend="rust", **kw)
    if inv is not None:
        for b, out in (("python", out_py), ("rust", out_rs)):
            k4_invariants(inv, b, vec, v0, out)
    op, orr = k4_observables(v0, out_py), k4_observables(v0, out_rs)
    return {o: score(op[o], orr[o], z, min_count if o in CONDITIONAL else None) for o in op}


def _inv(inv, kernel, iid, backend, ok, detail=None):
    """Exact-invariant ledger, kept per kernel (a shared invariant id is recorded separately for each kernel)."""
    rec = inv.setdefault(kernel, {}).setdefault(iid, {"python": {"held": True, "n_checks": 0, "violations": []},
                               "rust": {"held": True, "n_checks": 0, "violations": []}})
    r = rec[backend]
    r["n_checks"] += 1
    if not ok:
        r["held"] = False
        if len(r["violations"]) < 5:
            r["violations"].append(detail)


def k4_invariants(inv, backend, vec, v0, out):
    col, v, hits, back, unres = out
    n = len(v0)
    vid = vec["id"]
    alive = ~(col | back)
    _inv(inv, "K4_trace", "INV-01", backend, (not np.any(col & back)) and int(col.sum() + back.sum() + alive.sum()) == n
         and unres == alive.sum() / n, vid)
    _inv(inv, "K4_trace", "INV-02", backend, col.dtype == np.bool_ and back.dtype == np.bool_ and col.shape == (n,) and
         back.shape == (n,) and v.dtype == np.float64 and v.shape == (n, 3) and hits.dtype.kind == "i" and
         hits.shape == (n,) and isinstance(unres, float), vid)
    _inv(inv, "K4_trace", "INV-07", backend, bool(np.all(v[col, 2] > 0)) and bool(np.all(v[back, 2] < 0)), vid)
    _inv(inv, "K4_trace", "INV-12", backend, bool(np.all(np.isfinite(v[col | back]))), vid)
    if alive.any():   # INV-06 (general form): every unresolved molecule has hits == the final budget
        hb = hits[alive]
        _inv(inv, "K4_trace", "INV-06", backend, bool(np.all(hb == hb[0])) and int(hb[0]) >= vec.get("max_hits", 200), vid)
    if vec["id"] == "E4-14":
        _inv(inv, "K4_trace", "INV-06", backend, bool(alive.any()) and bool(np.all(hits[alive] == 4)) and not np.any(col & alive), vid)
    spec = (vec["scattering"] == "maxwell" and vec["alpha"] == 0.0 and "alpha_n" not in vec) or \
           (vec["scattering"] == "cll" and vec.get("alpha_n", vec["alpha"]) == 0.0 and vec.get("alpha_t", vec["alpha"]) == 0.0)
    if spec and vec["theta_deg"] == 0.0:
        s0 = np.sqrt((v0 * v0).sum(1)); s1 = np.sqrt((v * v).sum(1))
        _inv(inv, "K4_trace", "INV-05", backend, bool(col.all()) and not back.any() and bool(np.array_equal(v[:, 2], v0[:, 2]))
             and bool(np.all(np.abs(s1 - s0) <= 1e-9 * s0)), vid)


def run_k5(vec, master, k, z, inv):
    atm = _atm()
    m = mass_of(vec["species"], atm)
    R = D_MM * 1e-3 / 2; L = vec["L_over_d"] * D_MM * 1e-3; n = vec["n"]
    kp = TB.clausing_transmission(gen(master, 5, k, 0), R, L, vec["alpha"], vec["T_w_K"], m, n=n, backend="python")
    kr = TB.clausing_transmission(gen(master, 5, k, 1), R, L, vec["alpha"], vec["T_w_K"], m, n=n, backend="rust")
    b = lambda p: (p, math.sqrt(p * (1 - p) / n), n)    # noqa: E731
    return {"K_back": score(b(kp), b(kr), z)}


def _entry_obs(v):
    return np.array([v[:, 0].mean(), v[:, 1].mean(), v[:, 2].mean(), (v[:, 2] ** 2).mean(),
                     (v[:, 0] ** 2 + v[:, 1] ** 2).mean()])


K1_OBS = ("mean_vx", "mean_vy", "mean_vz", "mean_vz2", "mean_vperp2")


def run_k1(vec, master, k, z, inv, pre):
    o = pre["observables"]["K1_entry"]
    reps, nrep = o["replicates_per_backend"], o["n_per_replicate"]
    atm = _atm(vec["alt"], vec["solar"])
    m = mass_of(vec["species"], atm); V = atm.get("V_rel", atm["V"]); T = atm["T"]
    th = math.radians(vec["theta_deg"])
    res = {"python": [], "rust": []}
    for r in range(reps):
        for b, s in (("python", 10 + 2 * r), ("rust", 11 + 2 * r)):
            v = TB.flux_weighted_entry(gen(master, 1, k, s), nrep, V, th, T, m, backend=b)
            if inv is not None:
                _inv(inv, "K1_entry", "INV-11", b, v.dtype == np.float64 and v.shape == (nrep, 3) and bool(np.all(v[:, 2] > 0)), vec["id"])
            res[b].append(_entry_obs(v))
    out = {}
    for j, name in enumerate(K1_OBS):
        a = np.array([x[j] for x in res["python"]]); c = np.array([x[j] for x in res["rust"]])
        out[name] = score((float(a.mean()), float(a.std(ddof=1) / math.sqrt(reps)), reps),
                          (float(c.mean()), float(c.std(ddof=1) / math.sqrt(reps)), reps), z)
    return out


def _normals(kind, n, rg):
    if kind == "plus_z":
        return np.tile(np.array([0.0, 0.0, 1.0]), (n, 1))
    if kind == "minus_z":
        return np.tile(np.array([0.0, 0.0, -1.0]), (n, 1))
    if kind == "plus_x":
        return np.tile(np.array([1.0, 0.0, 0.0]), (n, 1))
    if kind == "x_y_wall":
        ph = rg.uniform(0.0, 2 * math.pi, n)
        return np.stack([np.cos(ph), np.sin(ph), np.zeros(n)], axis=1)
    raise SystemExit(f"unknown normal set {kind}")


def run_k2(vec, master, k, z, inv):
    atm = _atm(); m = mass_of(vec["species"], atm); n = vec["n"]
    nr = _normals(vec["normal_set"], n, gen(master, 2, k, 2))
    out = {}
    vals = {}
    for b, s in (("python", 0), ("rust", 1)):
        v = TB.diffuse(gen(master, 2, k, s), n, vec["T_w_K"], m, nr, backend=b)
        vn = (v * nr).sum(1)
        if inv is not None:
            _inv(inv, "K2_diffuse", "INV-08", b, bool(np.all(vn > 0)), vec["id"])
        vals[b] = {"mean_vn": _mean_se(vn), "mean_vn2": _mean_se(vn * vn), "mean_vt2": _mean_se((v * v).sum(1) - vn * vn)}
    for o in ("mean_vn", "mean_vn2", "mean_vt2"):
        out[o] = score(vals["python"][o], vals["rust"][o], z)
    return out


def k3_inputs(vec, master, k):
    atm = _atm(); m = mass_of(vec["species"], atm); n = vec["n"]
    rg = gen(master, 3, k, 2)
    v = REF._flux_weighted_entry(rg, n, atm.get("V_rel", atm["V"]), math.radians(5.0), atm["T"], m)
    nr = _normals("x_y_wall", n, rg)
    vn = (v * nr).sum(1)
    v_in = np.where((vn > 0)[:, None], v - 2 * vn[:, None] * nr, v)
    return v_in, nr, m


def run_k3(vec, master, k, z, inv):
    v_in, nr, m = k3_inputs(vec, master, k)
    vin_n = (v_in * nr).sum(1)
    vt_in = v_in - vin_n[:, None] * nr
    vt_in2 = (vt_in * vt_in).sum(1)
    vals = {}
    for b, s in (("python", 0), ("rust", 1)):
        v = TB.cll(gen(master, 3, k, s), v_in, nr, vec["T_w_K"], m, vec["alpha_n"], vec["alpha_t"], backend=b)
        vn = (v * nr).sum(1)
        vt = v - vn[:, None] * nr
        ret = np.where(vt_in2 > 0, (vt * vt_in).sum(1) / np.where(vt_in2 > 0, vt_in2, 1.0), 0.0)
        if inv is not None:
            _inv(inv, "K3_cll", "INV-09", b, bool(np.all(vn >= 0)), vec["id"])
            if vec["alpha_n"] == 0.0 and vec["alpha_t"] == 0.0:
                spec = v_in - 2 * vin_n[:, None] * nr
                scale = np.sqrt((v_in * v_in).sum(1))[:, None]
                _inv(inv, "K3_cll", "INV-09", b, bool(np.all(np.abs(v - spec) <= 1e-9 * scale)), vec["id"] + ":specular")
        vals[b] = {"mean_vn_out": _mean_se(vn), "mean_vn_out2": _mean_se(vn * vn),
                   "mean_vt_out2": _mean_se((vt * vt).sum(1)), "mean_vt_retention": _mean_se(ret)}
    return {o: score(vals["python"][o], vals["rust"][o], z) for o in vals["python"]}


# --------------------------------------------------------------------------------------------------------------------
# standalone exact invariants (INV-03 determinism, INV-04 L = 0, INV-10 n = 0)
# --------------------------------------------------------------------------------------------------------------------
def _same(a, b):
    if isinstance(a, tuple):
        return all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, np.ndarray):
        return a.dtype == b.dtype and a.shape == b.shape and bool(np.array_equal(a, b, equal_nan=a.dtype.kind == "f"))
    if isinstance(a, float) and math.isnan(a):
        return isinstance(b, float) and math.isnan(b)
    return a == b


def standalone_invariants(inv, master):
    atm = _atm(); m = M_SPECIES["N2"]; V = atm["V"]; T = atm["T"]
    R = D_MM * 1e-3 / 2
    calls = {
        "K1_entry": lambda rng, b: TB.flux_weighted_entry(rng, 500, V, 0.05, T, m, backend=b),
        "K2_diffuse": lambda rng, b: TB.diffuse(rng, 500, 350.0, m, _normals("plus_z", 500, None), backend=b),
        "K3_cll": lambda rng, b: TB.cll(rng, np.tile([300.0, -200.0, 7000.0], (500, 1)) * [1, 1, 1],
                                        np.tile([0.0, 1.0, 0.0], (500, 1)), 350.0, m, 0.5, 0.5, backend=b),
        "K4_trace": lambda rng, b: TB.trace_channel(rng, REF._flux_weighted_entry(np.random.default_rng(5), 500, V, 0.0, T, m),
                                                    R, 0.05, 0.5, 350.0, m, backend=b),
        "K5_clausing": lambda rng, b: TB.clausing_transmission(rng, R, 0.05, 0.5, 350.0, m, n=2000, backend=b),
    }
    for kern, fn in calls.items():
        for b in ("python", "rust"):
            a1 = fn(gen(master, KERNEL_INDEX[kern], 0, 30), b)
            a2 = fn(gen(master, KERNEL_INDEX[kern], 0, 30), b)
            a3 = fn(gen(master, KERNEL_INDEX[kern], 0, 31), b)
            _inv(inv, kern, "INV-03", b, _same(a1, a2) and not _same(a1, a3), kern)
    # INV-04: L = 0
    v0 = REF._flux_weighted_entry(gen(master, 4, 0, 32), 1000, V, 0.0, T, m)
    for b in ("python", "rust"):
        for sc, kw in (("maxwell", {}), ("cll", {"alpha_n": 0.7, "alpha_t": 0.4})):
            col, v, hits, back, unres = TB.trace_channel(gen(master, 4, 0, 33), v0, R, 0.0, 1.0, 350.0, m, scattering=sc,
                                                         backend=b, **kw)
            _inv(inv, "K4_trace", "INV-04", b, bool(col.all()) and not back.any() and bool(np.all(hits == 0)) and
                 bool(np.array_equal(v, v0)) and unres == 0.0, f"K4 L=0 {sc}")
        kb = TB.clausing_transmission(gen(master, 5, 0, 34), R, 0.0, 1.0, 350.0, m, n=2000, backend=b)
        _inv(inv, "K5_clausing", "INV-04", b, kb == 1.0, "K5 L=0")
    # INV-10: n = 0
    empty = np.zeros((0, 3))
    for b in ("python", "rust"):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            col, v, hits, back, unres = TB.trace_channel(gen(master, 4, 0, 35), empty, R, 0.05, 0.5, 350.0, m, backend=b)
        _inv(inv, "K4_trace", "INV-10", b, col.shape == (0,) and back.shape == (0,) and v.shape == (0, 3) and hits.shape == (0,)
             and isinstance(unres, float) and math.isnan(unres), "n=0")


# --------------------------------------------------------------------------------------------------------------------
# speed-up (F0 workload)
# --------------------------------------------------------------------------------------------------------------------
def speedup(pre):
    atm = _atm(); m = atm["m_mean"]
    g = REF.IntakeGeometry(area_m2=0.5, L_over_d=5.0, phi=0.85)
    R = g.d_mm * 1e-3 / 2; L = g.L_over_d * g.d_mm * 1e-3

    def w1(b):
        rng = np.random.default_rng(11)
        if b == "python":
            v0 = REF._flux_weighted_entry(rng, 20000, atm["V"], 0.0, atm["T"], m)
            return REF.trace_channel(rng, v0, R, L, 0.8, g.T_wall_K, m), rng
        v0 = TB.flux_weighted_entry(rng, 20000, atm["V"], 0.0, atm["T"], m, backend="rust")
        return TB.trace_channel(rng, v0, R, L, 0.8, g.T_wall_K, m, backend="rust"), rng

    def w2(b):
        out, rng = w1(b)
        if b == "python":
            return REF.clausing_transmission(rng, R, L, 0.8, g.T_wall_K, m)
        return TB.clausing_transmission(rng, R, L, 0.8, g.T_wall_K, m, backend="rust")

    reps = pre["speedup_measurement"]["repeats"]
    res = {"measured_path": ("kernel-only: timed inside parity_campaign_unadmitted(), so the per-call admission gate "
                             "(RUST-01) is bypassed; see speedup_served_path for the backend as served to consumers")
           if TB._UNADMITTED_ALLOWED else
           "served: timed through the admission-gated backend (cached admission check, RUST-R1-01)"}
    for wid, fn in (("W1_tpmc_trace_channel", w1), ("W2_response_point_kernel", w2)):
        rec = {}
        for b in ("python", "rust"):
            fn(b)                                        # untimed warm-up (imports, page-in)
            walls, cpus = [], []
            for _ in range(reps):
                t0, c0 = time.perf_counter(), time.process_time()
                fn(b)
                walls.append(time.perf_counter() - t0); cpus.append(time.process_time() - c0)
            rec[b] = {"wall_s": walls, "cpu_s": cpus, "median_wall_s": float(np.median(walls)),
                      "median_cpu_s": float(np.median(cpus))}
        rec["speedup_wall"] = rec["python"]["median_wall_s"] / rec["rust"]["median_wall_s"]
        rec["speedup_cpu"] = rec["python"]["median_cpu_s"] / max(rec["rust"]["median_cpu_s"], 1e-9)
        res[wid] = rec
    f0 = json.load(open(_p(F0_REL)))
    w = {x["id"]: x for x in f0["workloads"]}.get("tpmc_trace_channel", {})
    res["F0_recorded_python_tpmc_trace_channel_median_wall_s"] = w.get("median_wall_s")
    res["warm_up"] = "one untimed call per backend and workload before the timed repeats"
    try:
        res["load_average"] = list(os.getloadavg())
    except OSError:
        res["load_average"] = None
    return res


GATED_CALLS = {"W1_tpmc_trace_channel": 2, "W2_response_point_kernel": 3}   # backend='rust' calls per workload run


def served_speedup(pre):
    """RUST-R1-01: re-time both workloads through the admission-gated (served) path once the report admits this build.
    Records the one-time full admission validation (first call per process: report load + sha256 of sources and
    extension) and the cached per-call gate cost, which every backend='rust' call pays."""
    mod, why = TB._load_rust()
    if mod is None:
        return {"status": "NOT_MEASURED_ABEP_CORE_UNAVAILABLE", "reason": why}
    TB.clear_admission_cache()
    t0 = time.perf_counter()
    ok, reason = TB.admission_status_cached(mod, "K4_trace")
    cold = time.perf_counter() - t0
    if not ok:
        return {"status": "NOT_MEASURED_NOT_ADMITTED", "reason": reason}
    per = []
    for _ in range(200):
        t0 = time.perf_counter()
        TB.admission_status_cached(mod, "K4_trace")
        per.append(time.perf_counter() - t0)
    res = speedup(pre)
    res.update({"status": "MEASURED", "gate_cold_first_call_s": cold,
                "gate_cached_per_call_median_s": float(np.median(per)), "gated_calls_per_workload_run": GATED_CALLS,
                "note": "the timed repeats follow an untimed warm-up, so they pay only the cached per-call gate; the "
                        "cold validation is paid once per process (and again whenever the report, the extension or a "
                        "listed source changes on disk)"})
    return res


# --------------------------------------------------------------------------------------------------------------------
# provenance
# --------------------------------------------------------------------------------------------------------------------
def _cmd(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=30, cwd=ROOT).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


# Files whose sha256 binds the verdicts (RUST-ID-05). abep_sim/intake_tpmc.py (the Python reference) was added in
# consolidated verification round 1 (STR-03); --check also compares it with the pre-registered reference sha256.
PROVENANCE_SOURCES = ("abep_core/Cargo.toml", "abep_core/Cargo.lock", "abep_core/pyproject.toml", "abep_core/src/lib.rs",
                      "abep_core/src/rng.rs", "abep_core/src/tpmc.rs", "abep_sim/design/tpmc_backend.py",
                      "abep_sim/intake_tpmc.py")


def build_provenance():
    mod, why = TB._load_rust()
    src = list(PROVENANCE_SOURCES)
    prov = {"source_sha256": {s: sha256_file(s) for s in src if os.path.exists(_p(s))}}
    cargo = os.path.expanduser("~/.cargo/bin")
    prov["rustc"] = _cmd([os.path.join(cargo, "rustc"), "--version"]) or _cmd(["rustc", "--version"])
    prov["cargo"] = _cmd([os.path.join(cargo, "cargo"), "--version"]) or _cmd(["cargo", "--version"])
    prov["build_profile"] = "release (opt-level 3, lto fat, codegen-units 1; abep_core/Cargo.toml)"
    if mod is not None:
        d = os.path.dirname(getattr(mod, "__file__", "") or "")
        so = sorted(f for f in os.listdir(d) if f.endswith((".so", ".pyd"))) if d and os.path.isdir(d) else []
        prov.update({"abep_core_version": mod.__version__, "rng_algorithm": mod.RNG_ALGORITHM,
                     "extension_file": so[0] if so else None,
                     "extension_sha256": hashlib.sha256(open(os.path.join(d, so[0]), "rb").read()).hexdigest() if so else None,
                     "K_B_matches_constants": mod.K_B == K_B})
    else:
        prov["unavailable_reason"] = why
    prov["python"] = platform.python_version(); prov["numpy"] = np.__version__
    prov["platform"] = f"{platform.system()} {platform.release()} {platform.machine()}"
    prov["git_head"] = _cmd(["git", "rev-parse", "HEAD"])
    prov["git_dirty"] = bool(_cmd(["git", "status", "--porcelain", "--", "abep_core", "abep_sim", "scripts/verify_abep_core.py"]))
    return prov


# --------------------------------------------------------------------------------------------------------------------
# verdicts
# --------------------------------------------------------------------------------------------------------------------
def kernel_summary(kname, vec_results, invariants, pre):
    z = pre["decision_rules"]["z"]; agg_thr = pre["decision_rules"]["aggregate_threshold"]
    obs_list = pre["observables"][kname]["list"]
    counts = {"WITHIN": 0, "OUTSIDE": 0, "AGREE_EXACT": 0, "DISAGREE_EXACT": 0, "NOT_SCORED": 0}
    zs = {o: [] for o in obs_list}
    worst = None
    failures = []
    for vr in vec_results:
        for o, rec in vr["tests"].items():
            st = rescore(rec[:4], z)[5] if rec[5] != "NOT_SCORED" else "NOT_SCORED"
            counts[st] += 1
            zz = rescore(rec[:4], z)[4] if st in ("WITHIN", "OUTSIDE") else None
            if zz is not None:
                zs[o].append(zz)
                if worst is None or abs(zz) > abs(worst[2]):
                    worst = (vr["id"], o, zz)
            if st in ("OUTSIDE", "DISAGREE_EXACT") and len(failures) < 50:
                failures.append({"vector": vr["id"], "observable": o, "status": st, "z": zz})
    aggregate = {}
    for o in obs_list:
        N = len(zs[o])
        stat = abs(sum(zs[o])) / math.sqrt(N) if N else None
        aggregate[o] = {"N": N, "abs_sum_z_over_sqrtN": stat, "within": (stat is None or stat <= agg_thr)}
    inv_ids = [i["id"] for i in pre["exact_invariants"] if kname in i["kernels"]]
    inv_rec = {}
    ref_finding = False; rust_violation = False; missing = []
    for iid in inv_ids:
        r = invariants.get(kname, {}).get(iid)
        if r is None or r["python"]["n_checks"] == 0 or r["rust"]["n_checks"] == 0:
            missing.append(iid)
            inv_rec[iid] = r
            continue
        inv_rec[iid] = r
        if not r["python"]["held"]:
            ref_finding = True
        if not r["rust"]["held"]:
            rust_violation = True
    ok = (counts["OUTSIDE"] == 0 and counts["DISAGREE_EXACT"] == 0 and all(a["within"] for a in aggregate.values())
          and not ref_finding and not rust_violation and not missing)
    return {
        "verdict": "ADMITTED" if ok else "NOT_ADMITTED",
        "n_vectors": len(vec_results),
        "test_counts": counts,
        "max_abs_z": None if worst is None else {"vector": worst[0], "observable": worst[1], "z": worst[2]},
        "aggregate_bias": aggregate,
        "invariants": inv_rec,
        "invariants_not_exercised": missing,
        "reference_invariant_finding": ref_finding,
        "rust_invariant_violation": rust_violation,
        "failures": failures,
    }


# --------------------------------------------------------------------------------------------------------------------
# campaign
# --------------------------------------------------------------------------------------------------------------------
RUNNERS = {"K1_entry": "k1", "K2_diffuse": "k2", "K3_cll": "k3", "K4_trace": "k4", "K5_clausing": "k5"}


def run_vectors(pre, master, only=None, limit=None, inv=None, progress=True):
    z = pre["decision_rules"]["z"]; mc = pre["observables"]["K4_trace"]["conditional_min_count"]
    vecs = build_vectors(pre, master)
    results = {}
    for kname, vlist in vecs.items():
        if only and kname not in only:
            continue
        rows = []
        t0 = time.time()
        for k, vec in enumerate(vlist):
            if limit is not None and k >= limit:
                break
            if kname == "K4_trace":
                tests = run_k4(vec, master, k, z, mc, inv)
            elif kname == "K5_clausing":
                tests = run_k5(vec, master, k, z, inv)
            elif kname == "K1_entry":
                tests = run_k1(vec, master, k, z, inv, pre)
            elif kname == "K2_diffuse":
                tests = run_k2(vec, master, k, z, inv)
            else:
                tests = run_k3(vec, master, k, z, inv)
            params = {kk: vv for kk, vv in vec.items() if kk not in ("id", "group")}
            rows.append({"id": vec["id"], "group": vec["group"], "index": k, "params": params, "tests": tests})
        if progress:
            print(f"  {kname}: {len(rows)} vectors in {time.time() - t0:.1f} s", flush=True)
        results[kname] = rows
    return results


def parameters_section(pre):
    dr = pre["decision_rules"]
    src = f"{PREREG_REL} (pre-registered before any comparison)"
    P = [("PAR-01", "z per test", dr["z"], "-", dr["z_basis"]),
         ("PAR-02", "aggregate bias bound |sum z|/sqrt(N)", dr["aggregate_threshold"], "-", dr["aggregate_bias"]),
         ("PAR-03", "exact-agreement tolerance when both se = 0", 1e-12, "relative", dr["zero_se_rule"]),
         ("PAR-04", "conditional observable minimum subset count", pre["observables"]["K4_trace"]["conditional_min_count"],
          "molecules", dr["not_scored_rule"]),
         ("PAR-05", "K1 replicates per backend", pre["observables"]["K1_entry"]["replicates_per_backend"], "replicates",
          pre["observables"]["K1_entry"]["se_method"]),
         ("PAR-06", "K1 molecules per replicate", pre["observables"]["K1_entry"]["n_per_replicate"], "molecules", "prereg"),
         ("PAR-07", "scoring master seed", pre["campaign_seeds"]["scoring_master_seed"], "-", pre["campaign_seeds"]["derivation"]),
         ("PAR-08", "channel diameter for all vectors", D_MM, "mm", "IntakeGeometry default used to build intake_surface_v1"),
         ("PAR-09", "golden wall temperature", T_W_GOLDEN, "K", "IntakeGeometry default used to build intake_surface_v1")]
    out = [{"id": i, "name": nm, "value": v, "units": u, "basis": b, "source": src,
            "evidence_class": "definition (pre-registered numerical acceptance criterion; not physics evidence)",
            "status": "PRE_REGISTERED"} for i, nm, v, u, b in P]
    for kname, tot in pre["comparison_set"]["vector_totals"].items():
        out.append({"id": f"PAR-N-{kname}", "name": f"registered vectors {kname}", "value": tot, "units": "vectors",
                    "basis": "golden + edge + randomized (prereg comparison_set)", "source": src,
                    "evidence_class": "definition", "status": "PRE_REGISTERED"})
    return out


def interface_section():
    return [
        {"id": "RUST-ID-01", "direction": "rust -> F0", "counterparty": "fo_a9_7_f0_profiling (docs/performance/PERFORMANCE_BASELINE_98fbbb9.json, F0-ID-02)",
         "demand": "parity record supplied: pre-registered tolerance (parity_prereg_v1.json) and per-kernel verdicts (this report); cite them in any post-port baseline",
         "status": "SUPPLIED"},
        {"id": "RUST-ID-02", "direction": "F0 -> rust (response)", "counterparty": "fo_a9_7_f0_profiling (F0-ID-01; scripts/perf/profile_baseline.py)",
         "demand": "F0 asks for its harness to be re-run on the Rust-enabled tree with the same keys. The harness calls abep_sim.intake_tpmc directly and has no backend switch (it is outside this lane's paths); this report times the identical tpmc_trace_channel workload (W1) under both backends in one session instead. Re-running the harness itself is left to F0 / the consolidated verification",
         "status": "PARTIAL"},
        {"id": "RUST-ID-03", "direction": "rust -> F1", "counterparty": "fo_a9_7_f1_intake_synthesis (abep_sim/design/intake_synthesis.py)",
         "demand": "F1 calls intake_tpmc.intake_response directly and is unchanged. Should F1 ever opt in, it must call abep_sim/design/tpmc_backend.py with backend='rust' explicitly, only for kernels ADMITTED here, label every such result backend=rust (non-authoritative) and keep the Python path reproducing it; intake_response itself (momentum / mass bookkeeping) is not ported",
         "status": "OPEN"},
        {"id": "RUST-ID-04", "direction": "rust -> F7/F8", "counterparty": "abep_sim/design/architecture_optimizer.py (fo_a9_7_f7_f8_coupled_optimizer; tpmc_backend_policy in docs/design_synthesis/f7_f8_optimizer/f7_f8_optimizer_v1.json)",
         "demand": "no Rust kernel enters the coupled or robust optimizer by default; any use goes through tpmc_backend with an explicit backend argument recorded in the result provenance (F7/F8 reads this report's verdicts for its tpmc_backend_policy and invokes no TPMC: tpmc_invoked_by_f7_f8 = false)",
         "status": "CONSUMED"},
        {"id": "RUST-ID-05", "direction": "rust -> consolidated verification", "counterparty": "fo_a9_7_consolidated_verification",
         "demand": "verify with `python scripts/verify_abep_core.py --check` (no build needed) and, with the extension built from the recorded sources, `--check --recompute 3` (bitwise reproduction of stored numbers); the verdict stands only for the recorded source hashes",
         "status": "OPEN"},
        {"id": "RUST-ID-06", "direction": "golden / frozen data -> rust", "counterparty": "abep_sim/data/intake_surface_v1.* and abep_sim/golden.py",
         "demand": "frozen intake surface and goldens are built with the Python reference only (CLAUDE.md rule 1); the Rust backend is never used to regenerate them",
         "status": "RESPECTED"},
    ]


def open_questions():
    return [
        {"id": "RUST-OQ-01", "question": "May an ADMITTED abep_core kernel ever be used for a frozen-data rebuild (intake_surface) or a score-bearing study, or must such outputs always come from the Python reference?",
         "default_if_unanswered": "Python reference only; Rust limited to explicitly labelled exploratory / search acceleration"},
        {"id": "RUST-OQ-02", "question": "Should the parity campaign run as an optional CI step (it needs a Rust toolchain and maturin; the pytest suite only smoke-tests it when the extension is present)?",
         "default_if_unanswered": "manual: scripts/verify_abep_core.py run by the consolidated verification"},
    ]


def assemble(pre, results, invariants, spd, prov, master, history):
    kernels = {k: kernel_summary(k, results[k], invariants, pre) for k in KERNEL_INDEX if k in results}
    items = [{"id": f"ITEM-{k}", "kernel": k, "value": s["verdict"], "units": "-",
              "basis": "pre-registered decision rule (prereg decision_rules.kernel_verdict)",
              "source": REPORT_REL, "evidence_class": "model-derived (numerical parity of two implementations; not physics evidence)",
              "status": s["verdict"]} for k, s in kernels.items()]
    rep = {
        "schema": "abep_core_parity_report_v1",
        "lane": LANE,
        "directive": DIRECTIVE,
        "generated_by": "scripts/verify_abep_core.py",
        "prereg": {"path": PREREG_REL, "sha256": sha256_file(PREREG_REL), "id": pre["id"]},
        "reference": {"path": "abep_sim/intake_tpmc.py", "sha256": sha256_file("abep_sim/intake_tpmc.py"),
                      "matches_prereg": sha256_file("abep_sim/intake_tpmc.py") == pre["reference_implementation"]["sha256_at_registration"]},
        "pinned_inputs_verified": {k: sha256_file(k) == v for k, v in pre["pinned_inputs_sha256"].items()},
        "campaign": {"master_seed": master, "z": pre["decision_rules"]["z"],
                     "aggregate_threshold": pre["decision_rules"]["aggregate_threshold"],
                     "vector_totals": {k: len(v) for k, v in results.items()}},
        "verdicts": {k: s["verdict"] for k, s in kernels.items()},
        "kernels": kernels,
        "speedup": spd,
        "build_provenance": prov,
        "items": items,
        "parameters": parameters_section(pre),
        "interface_demands": interface_section(),
        "open_owner_questions": open_questions(),
        "m16_impact": [{"m16_row": None, "state_change": "none - numerical acceleration only; no requirement, evidence or gate status changes"}],
        "what_this_is_not": pre["what_this_is_not"] + [
            "ADMITTED is not PASS: it admits an optional, explicitly selected backend inside the tested parity domain"],
        "documented_divergence": pre["documented_divergence"] + [
            {"id": "DIV-02", "statement": "scattering other than 'maxwell' / 'cll': the reference silently traces Maxwell; the Rust backend refuses (no silent fallback). Not in the comparison set (documented after registration; does not affect scoring)."},
            {"id": "DIV-03", "statement": "CLL alpha_n or alpha_t outside [0, 1]: the reference raises (alpha_t) or returns NaN (alpha_n); the Rust backend refuses with ValueError. Not in the comparison set (documented after registration; does not affect scoring)."},
            {"id": "DIV-04", "statement": "trace_channel max_hits_cap < 1: the reference accepts max_hits_cap = 0 (its hit-budget doubling then stops after max_hits steps); the Rust extension refuses it (its error text cites max_hits, which is inaccurate for the cap), and abep_sim/design/tpmc_backend.py refuses it for backend='rust' with a correct message before the extension is called. Not in the comparison set (recorded in consolidated verification round 1, RUST-02; does not affect scoring)."}],
        "campaign_history": history,
        "vectors": results,
    }
    return rep


def render_md(rep):
    L = [f"# abep_core parity report v1 (A9.7 Rust lane, TPMC kernel)", "",
         f"Generated by `scripts/verify_abep_core.py` from `{REPORT_REL}`; do not edit by hand. Lane `{LANE}`, directive "
         f"`{DIRECTIVE}`. Pre-registration `{rep['prereg']['path']}` (sha256 `{rep['prereg']['sha256'][:16]}...`, committed "
         "before any comparison).", "",
         "**What this is not:** " + "; ".join(rep["what_this_is_not"]) + ".", "",
         "## Verdicts", "", "| kernel | verdict | vectors | within | exact agree | outside | exact disagree | not scored | max abs z |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k, s in rep["kernels"].items():
        c = s["test_counts"]; mz = s["max_abs_z"]
        L.append(f"| {k} | **{s['verdict']}** | {s['n_vectors']} | {c['WITHIN']} | {c['AGREE_EXACT']} | {c['OUTSIDE']} | "
                 f"{c['DISAGREE_EXACT']} | {c['NOT_SCORED']} | " + ("-" if mz is None else f"{abs(mz['z']):.2f} ({mz['vector']}, {mz['observable']})") + " |")
    L += ["", f"Rule: |mean_rust - mean_py| <= z sqrt(se_py^2 + se_rust^2), z = {rep['campaign']['z']}; per observable "
          f"|sum z|/sqrt(N) <= {rep['campaign']['aggregate_threshold']}; every exact invariant in both backends. Master seed "
          f"{rep['campaign']['master_seed']}. Reference `abep_sim/intake_tpmc.py` sha256 matches prereg: "
          f"{rep['reference']['matches_prereg']}.", "", "## Aggregate bias per observable", "",
          "| kernel | observable | N | abs(sum z)/sqrt(N) | within |", "|---|---|---|---|---|"]
    for k, s in rep["kernels"].items():
        for o, a in s["aggregate_bias"].items():
            st = "-" if a["abs_sum_z_over_sqrtN"] is None else f"{a['abs_sum_z_over_sqrtN']:.3f}"
            L.append(f"| {k} | {o} | {a['N']} | {st} | {a['within']} |")
    L += ["", "## Exact invariants", "", "| kernel | invariant | python held (checks) | rust held (checks) |", "|---|---|---|---|"]
    for k, s in rep["kernels"].items():
        for iid, r in s["invariants"].items():
            if r is None:
                L.append(f"| {k} | {iid} | not exercised | not exercised |")
            else:
                L.append(f"| {k} | {iid} | {r['python']['held']} ({r['python']['n_checks']}) | {r['rust']['held']} ({r['rust']['n_checks']}) |")
    sp = rep["speedup"]
    ss = rep.get("speedup_served_path") or {}
    L += ["", "## Measured speed-up (informational; not an admission criterion)", "",
          "| path | workload | python median wall s | rust median wall s | speed-up wall | python median CPU s | rust median CPU s | speed-up CPU |",
          "|---|---|---|---|---|---|---|---|"]
    for label, src in (("kernel-only (gate bypassed)", sp), ("served (admission-gated)", ss)):
        for wid in ("W1_tpmc_trace_channel", "W2_response_point_kernel"):
            w = src.get(wid)
            if not w:
                continue
            L.append(f"| {label} | {wid} | {w['python']['median_wall_s']:.4f} | {w['rust']['median_wall_s']:.5f} | {w['speedup_wall']:.1f}x | "
                     f"{w['python']['median_cpu_s']:.4f} | {w['rust']['median_cpu_s']:.5f} | {w['speedup_cpu']:.1f}x |")
    L += ["", f"Kernel-only path: {sp.get('measured_path', 'timed inside the parity campaign (admission gate bypassed)')}."]
    if ss.get("status") == "MEASURED":
        L += [f"Served path: {ss['measured_path']}; one-time full admission validation {ss['gate_cold_first_call_s']:.4f} s "
              f"(first backend='rust' call per process), cached gate {ss['gate_cached_per_call_median_s'] * 1e6:.1f} us per call "
              f"({', '.join(f'{k}: {v} calls' for k, v in ss['gated_calls_per_workload_run'].items())}); {ss['note']}."]
    else:
        L += [f"Served path: {ss.get('status', 'NOT_RECORDED')} ({ss.get('reason', 'campaign predates RUST-R1-01')})."]
    L += ["", f"W1 is the F0 workload `tpmc_trace_channel` (F0 recorded Python median "
          f"{sp['F0_recorded_python_tpmc_trace_channel_median_wall_s']} s on a shared machine); W2 adds the Clausing back-trace "
          f"(the TPMC part of one intake_response point). {sp['warm_up']}; load average {sp['load_average']}. Machine-specific "
          "runtimes, not physics.", "", "## Build provenance", ""]
    bp = rep["build_provenance"]
    for k in ("abep_core_version", "rng_algorithm", "rustc", "cargo", "build_profile", "extension_file", "extension_sha256",
              "K_B_matches_constants", "python", "numpy", "platform", "git_head", "git_dirty"):
        L.append(f"- {k}: {bp.get(k)}")
    L.append("- source sha256: " + ", ".join(f"`{p}` {h[:16]}" for p, h in bp["source_sha256"].items()))
    L += ["", "## Documented divergences (inputs outside the reference's handled domain)", ""]
    L += [f"- {d['id']}: {d['statement']}" for d in rep["documented_divergence"]]
    L += ["", "## Interface demands", ""]
    L += [f"- {d['id']} ({d['direction']}, {d['counterparty']}): {d['demand']} [{d['status']}]" for d in rep["interface_demands"]]
    L += ["", "## Open owner questions (new)", ""]
    L += [f"- {q['id']}: {q['question']} Default if unanswered: {q['default_if_unanswered']}." for q in rep["open_owner_questions"]]
    L += ["", "## M16 impact", "", f"- {rep['m16_impact'][0]['state_change']}", "", "## Campaign history", "",
          "| # | UTC | git head | master seed | verdicts |", "|---|---|---|---|---|"]
    for i, h in enumerate(rep["campaign_history"], 1):
        L.append(f"| {i} | {h['utc']} | {str(h.get('git_head'))[:12]} | {h['master_seed']} | "
                 + ", ".join(f"{k}={v}" for k, v in h["verdicts"].items()) + " |")
    L += ["", "## Commands", "", "- campaign: `python scripts/verify_abep_core.py` (with the built extension, abep_core/README.md)",
          "- check: `python scripts/verify_abep_core.py --check` (re-derives every verdict; add `--recompute 3` with the extension)",
          "- render: `python scripts/verify_abep_core.py --render-md`", "- test: `python -m pytest -q tests/test_tpmc_backend.py`", ""]
    return "\n".join(L)


def write_report(rep):
    with open(_p(REPORT_REL), "w") as fh:
        json.dump(rep, fh, indent=1, allow_nan=False)
        fh.write("\n")
    with open(_p(MD_REL), "w") as fh:
        fh.write(render_md(rep))


def campaign():
    pre = load_prereg()
    if sha256_file("abep_sim/intake_tpmc.py") != pre["reference_implementation"]["sha256_at_registration"]:
        print("REFUSED_REFERENCE_CHANGED: abep_sim/intake_tpmc.py differs from the pre-registered reference")
        return 3
    bad = [k for k, v in pre["pinned_inputs_sha256"].items() if sha256_file(k) != v]
    if bad:
        print(f"REFUSED_PINNED_INPUT_CHANGED: {bad}")
        return 3
    if not TB.rust_available():
        print(f"NOT_RUN_ABEP_CORE_UNAVAILABLE: {TB.rust_unavailable_reason()} (report not written)")
        return 2
    master = pre["campaign_seeds"]["scoring_master_seed"]
    t0 = time.time()
    inv = {}
    with TB.parity_campaign_unadmitted():          # the campaign is what admits a build (RUST-01 gate)
        print("standalone invariants ...", flush=True)
        standalone_invariants(inv, master)
        print("comparison vectors ...", flush=True)
        results = run_vectors(pre, master, inv=inv)
        print("speed-up ...", flush=True)
        spd = speedup(pre)
    prov = build_provenance()
    history = []
    if os.path.exists(_p(REPORT_REL)):
        history = json.load(open(_p(REPORT_REL))).get("campaign_history", [])
    rep = assemble(pre, results, inv, spd, prov, master, history)
    rep["campaign_history"] = history + [{
        "utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_head": prov.get("git_head"),
        "git_dirty": prov.get("git_dirty"), "master_seed": master, "prereg_sha256": rep["prereg"]["sha256"],
        "source_sha256": prov["source_sha256"], "verdicts": rep["verdicts"], "wall_s": round(time.time() - t0, 1)}]
    write_report(rep)
    print("speed-up through the served (admission-gated) path ...", flush=True)
    rep["speedup_served_path"] = served_speedup(pre)
    write_report(rep)
    print(json.dumps(rep["verdicts"], indent=1))
    print(f"W1 speed-up {spd['W1_tpmc_trace_channel']['speedup_wall']:.1f}x, W2 {spd['W2_response_point_kernel']['speedup_wall']:.1f}x; "
          f"total {time.time() - t0:.0f} s")
    return 0


def dev(only, limit, strict=False):
    pre = load_prereg()
    if not TB.rust_available():
        print(f"abep_core unavailable: {TB.rust_unavailable_reason()}")
        return 2
    if strict and (only or limit is not None):
        print("--dev --strict runs the full development comparison; --only / --limit are not allowed with it")
        return 2
    master = pre["campaign_seeds"]["development_master_seed"]
    inv = {}
    with TB.parity_campaign_unadmitted():
        standalone_invariants(inv, master)
        results = run_vectors(pre, master, only=only, limit=limit, inv=inv)
    bad = []
    for k in results:
        s = kernel_summary(k, results[k], inv, pre)
        print(k, "(DEVELOPMENT, not scored)", s["test_counts"], s["max_abs_z"],
              {o: round(a["abs_sum_z_over_sqrtN"] or 0, 2) for o, a in s["aggregate_bias"].items()},
              "inv rust ok:", all(r is None or r["rust"]["held"] for r in s["invariants"].values()),
              "inv py ok:", all(r is None or r["python"]["held"] for r in s["invariants"].values()))
        if s["verdict"] != "ADMITTED":          # the scored verdict rule, applied to development data only (no verdict)
            bad.append(k)
    if strict:
        if bad:
            print(f"DEVELOPMENT_SMOKE_FAILED (development seed, not scored, not a verdict): {bad}")
            return 1
        print("DEVELOPMENT_SMOKE_OK (development seed, not scored, not a verdict; admits nothing)")
    return 0


SOURCE_STATUS_KEYS = ("sources_match_recorded_build", "reference_matches_prereg", "extension_importable",
                      "extension_is_recorded_build")


def source_status(github_output=None):
    """CI entry point: compare the current sources, the reference and the importable extension with the record."""
    pre = load_prereg()
    rep = json.load(open(_p(REPORT_REL)))
    bp = rep["build_provenance"]
    current = {s: (sha256_file(s) if os.path.exists(_p(s)) else None) for s in PROVENANCE_SOURCES}
    differing = sorted(s for s in PROVENANCE_SOURCES if current[s] != bp["source_sha256"].get(s))
    mod, why = TB._load_rust()
    ext = TB.extension_sha256(mod) if mod is not None else None
    st = {
        "sources_match_recorded_build": not differing,
        "differing_sources": differing,
        "reference_matches_prereg": current["abep_sim/intake_tpmc.py"] == pre["reference_implementation"]["sha256_at_registration"],
        "extension_importable": mod is not None,
        "extension_unavailable_reason": why,
        "extension_sha256": ext,
        "recorded_extension_sha256": bp.get("extension_sha256"),
        "extension_is_recorded_build": ext is not None and ext == bp.get("extension_sha256"),
        "recorded_verdicts": rep["verdicts"],
    }
    print(json.dumps(st, indent=1))
    if github_output:
        with open(github_output, "a") as fh:
            for key in SOURCE_STATUS_KEYS:
                fh.write(f"{key}={'true' if st[key] else 'false'}\n")
    return 0


def check(recompute=0):
    errs = []
    pre = load_prereg()
    if not os.path.exists(_p(REPORT_REL)):
        print("CHECK FAILED: report missing"); return 1
    rep = json.load(open(_p(REPORT_REL)))
    if rep["prereg"]["sha256"] != sha256_file(PREREG_REL):
        errs.append("prereg sha256 changed since the campaign")
    for h in rep["campaign_history"]:
        if h["prereg_sha256"] != rep["prereg"]["sha256"]:
            errs.append(f"campaign {h['utc']} ran under a different prereg")
    if not rep["reference"]["matches_prereg"]:
        errs.append("campaign ran against a changed reference")
    if not all(rep["pinned_inputs_verified"].values()):
        errs.append("pinned inputs did not verify at campaign time")
    for k, v in rep["vectors"].items():
        if len(v) != pre["comparison_set"]["vector_totals"][k]:
            errs.append(f"{k}: {len(v)} vectors != registered")
    # re-derive every per-test status and the kernel verdicts from the stored numbers
    z = pre["decision_rules"]["z"]
    for k, rows in rep["vectors"].items():
        for r in rows:
            for o, rec in r["tests"].items():
                if rec[5] == "NOT_SCORED":
                    continue
                again = rescore(rec[:4], z)
                if again[5] != rec[5] or (again[4] != rec[4]):
                    errs.append(f"{k} {r['id']} {o}: stored {rec[5]} re-derived {again[5]}")
        s = kernel_summary(k, rows, {k: {iid: r for iid, r in rep["kernels"][k]["invariants"].items() if r}}, pre)
        if s["verdict"] != rep["verdicts"][k] or s["test_counts"] != rep["kernels"][k]["test_counts"]:
            errs.append(f"{k}: verdict / counts do not re-derive")
    # determinism of the vector set itself
    vecs = build_vectors(pre, rep["campaign"]["master_seed"])
    for k, rows in rep["vectors"].items():
        for r, v in zip(rows, vecs[k]):
            if r["id"] != v["id"] or r["params"] != {kk: vv for kk, vv in v.items() if kk not in ("id", "group")}:
                errs.append(f"{k} {r['id']}: vector parameters do not re-derive"); break
    for word in FORBIDDEN_WORDS:
        for k, s in rep["kernels"].items():
            if s["verdict"] == word:
                errs.append(f"forbidden verdict word {word}")
    # RUST-R1-01: the served (admission-gated) speed-up is recorded next to the kernel-only one
    ss = rep.get("speedup_served_path")
    if not ss:
        errs.append("speedup_served_path missing (re-run the campaign: the served-path speed-up is not recorded)")
    elif all(v == "ADMITTED" for v in rep["verdicts"].values()) and ss.get("status") != "MEASURED":
        errs.append(f"speedup_served_path not measured although every kernel is ADMITTED ({ss.get('status')})")
    if "kernel-only" not in str(rep["speedup"].get("measured_path", "")):
        errs.append("speedup section does not state that it is the kernel-only (gate-bypassed) path")
    if open(_p(MD_REL)).read() != render_md(rep):
        errs.append("MD is not the rendering of the JSON (run --render-md)")
    # RUST-01 / STR-03: the verdicts stand only for the recorded build. Always compare the current sources (and the
    # installed extension when importable) with build_provenance, and the reference with its pre-registered sha256.
    bp = rep["build_provenance"]
    for rel in PROVENANCE_SOURCES:
        if rel not in bp["source_sha256"]:
            errs.append(f"{rel} is not in the recorded build provenance (re-run the campaign)")
    for rel, h in bp["source_sha256"].items():
        cur = sha256_file(rel) if os.path.exists(_p(rel)) else None
        if cur != h:
            errs.append(f"source {rel} differs from the recorded build (verdicts do not apply: NOT_ADMITTED_BUILD)")
    if sha256_file("abep_sim/intake_tpmc.py") != pre["reference_implementation"]["sha256_at_registration"]:
        errs.append("abep_sim/intake_tpmc.py differs from the pre-registered reference (verdicts do not apply)")
    mod, _why = TB._load_rust()
    if mod is not None and TB.extension_sha256(mod) != bp.get("extension_sha256"):
        errs.append(f"installed abep_core extension sha256 {TB.extension_sha256(mod)} != recorded "
                    f"{bp.get('extension_sha256')} (NOT_ADMITTED_BUILD)")
    if recompute:
        if not TB.rust_available():
            errs.append(f"--recompute needs abep_core: {TB.rust_unavailable_reason()}")
        elif build_provenance()["source_sha256"] != rep["build_provenance"]["source_sha256"]:
            errs.append("--recompute: abep_core sources differ from the recorded build")
        else:
            with TB.parity_campaign_unadmitted():
                got = run_vectors(pre, rep["campaign"]["master_seed"], limit=recompute, inv=None, progress=False)
            for k, rows in got.items():
                for a, b in zip(rows, rep["vectors"][k]):
                    if json.loads(json.dumps(a["tests"])) != b["tests"]:
                        errs.append(f"--recompute: {k} {a['id']} differs from the stored numbers")
    if errs:
        print("CHECK FAILED"); [print(" -", e) for e in errs[:40]]
        return 1
    print(f"CHECK OK: verdicts {rep['verdicts']}; {len(rep['campaign_history'])} campaign execution(s) on record"
          + (f"; first {recompute} vectors per kernel reproduced bitwise" if recompute else ""))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--recompute", type=int, default=0)
    ap.add_argument("--render-md", action="store_true")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--strict", action="store_true", help="with --dev: exit 1 on any development disagreement")
    ap.add_argument("--source-status", action="store_true")
    ap.add_argument("--github-output", help="with --source-status: append key=value lines to this file")
    a = ap.parse_args(argv)
    if a.strict and not a.dev:
        ap.error("--strict is only valid with --dev")
    if a.github_output and not a.source_status:
        ap.error("--github-output is only valid with --source-status")
    if a.source_status:
        return source_status(a.github_output)
    if a.check:
        return check(a.recompute)
    if a.render_md:
        rep = json.load(open(_p(REPORT_REL)))
        with open(_p(MD_REL), "w") as fh:
            fh.write(render_md(rep))
        return 0
    if a.dev:
        return dev(a.only, a.limit, a.strict)
    return campaign()


if __name__ == "__main__":
    sys.exit(main())

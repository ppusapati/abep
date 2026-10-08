"""H-1 / MC-1 FE-derived B(z) (lane L-H1-BZ, A9.38 P3): runs the preregistered evaluation h1_bz_fe_prereg_v3.json (v1, v2 superseded, kept).

Stages (each writes a raw JSON under the scratch directory given by --work; nothing in the repository is written until
--emit):
  verify       V1 (air-core coils, analytic / elliptic-integral references), V2 (loop over a linear-iron half-space, image
               method), V3 (infinite solenoid with nonlinear iron core, Ampere's law)
  convergence  nominal geometry at mesh levels L1 / L2 / L3 at the convergence currents; far-boundary check
  sweep        current sweep for the nominal geometry (L3) and every uncertainty variant (L2); exact-level solves
  emit         h1_bz_fe_v1.json / H1_BZ_FE_v1.md and the HallThruster.jl profile files (hallthruster_bridge/bfield/h1_fe_v1/)

Usage: python build_h1_bz_fe.py --work DIR (verify|convergence|sweep|emit)   [needs numpy, scipy, scikit-fem as pinned]
The prereg lock is verified before any stage (fail closed).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
import time

import numpy as np
import scipy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import h1_bz_fe_solver as S  # noqa: E402

PREREG = os.path.join(HERE, "h1_bz_fe_prereg_v3.json")
LOCK = os.path.join(HERE, "h1_bz_fe_prereg_lock_v3.json")
BHFILE = os.path.join(HERE, "bh_curves_v1.json")
OUT_JSON = os.path.join(HERE, "h1_bz_fe_v1.json")
OUT_MD = os.path.join(HERE, "H1_BZ_FE_v1.md")
BF_DIR = os.path.join(ROOT, "hallthruster_bridge", "bfield", "h1_fe_v1")
SURR = os.path.join(ROOT, "hallthruster_bridge", "bfield", "p5_vacuum_Br_centerline_1p6kW.csv")
MM = 1e-3
G = 1e-4


def sha256_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def check_lock():
    lock = json.load(open(LOCK))
    for rel, h in lock["files"].items():
        p = os.path.join(ROOT, rel)
        if sha256_file(p) != h:
            raise SystemExit(f"REFUSED: {rel} sha256 differs from the prereg lock")
    import skfem
    pin = json.load(open(PREREG))["solver"]["pins"]
    got = {"scikit-fem": skfem.__version__, "numpy": np.__version__, "scipy": scipy.__version__}
    for k, v in pin.items():
        if got.get(k) != v:
            raise SystemExit(f"REFUSED: {k} {got.get(k)} != pinned {v}")
    return lock


def prereg():
    return json.load(open(PREREG))


def bh_sets():
    d = json.load(open(BHFILE))
    out = {}
    for sid, s in d["sets"].items():
        out[sid] = {"hiperco": S.BH(d["curves"]["hiperco"][s["hiperco"]]["points"], s["hiperco"]),
                    "iron": S.BH(d["curves"]["iron"][s["iron"]]["points"], s["iron"])}
    return out


# ------------------------------------------------------------------------------------------------------------ geometry
def layout(P, t_w=None, w_p=None, placement=None):
    """MC-1 rectangles (m) by the H2-1 coil_case layout rules (registered), solid inner core (row 79)."""
    g = P["geometry"]["nominal"]
    t_w = g["t_wall_mm"] if t_w is None else t_w
    w_p = g["pole_tip_width_mm"] if w_p is None else w_p
    placement = g["coil_axial_placement"] if placement is None else placement
    d, h, L = g["d_mean_mm"], g["h_mm"], g["L_mm"]
    c, scr, bob, ob = g["gap_clearance_mm"], g["screen_mm"], g["bobbin_mm"], g["outer_coil_build_mm"]
    r_c, t_bp, t_oc, frac = g["inner_core_r_mm"], g["back_plate_t_mm"], g["outer_core_t_mm"], g["coil_axial_fraction_of_L"]
    r_in, r_out = d / 2 - h / 2, d / 2 + h / 2
    r_pi, r_po = r_in - t_w - c, r_out + t_w + c
    ic0, ic1 = r_c + bob, r_in - t_w - scr
    oc0 = r_out + t_w + 2.0
    oc1 = oc0 + ob
    r_oc_in = oc1 + 1.0
    R = r_oc_in + t_oc
    Lc = frac * L
    space = L - w_p
    z0 = {"back": 0.0, "centered": 0.5 * (space - Lc), "pole": space - Lc}[placement]
    if ic1 - ic0 < g["inner_coil_min_build_mm"] or Lc > space:
        raise ValueError("layout infeasible")
    q = lambda a, b, c_, d_, m, lab: S.Rect(a * MM, b * MM, c_ * MM, d_ * MM, m, lab)
    rects = [
        q(0.0, r_c, -t_bp, L, "hiperco", "inner core (solid)"),
        q(r_c, r_pi, L - w_p, L, "hiperco", "inner pole"),
        q(r_c, R, -t_bp, 0.0, "iron", "back plate"),
        q(r_oc_in, R, -t_bp, L, "iron", "outer core"),
        q(r_po, r_oc_in, L - w_p, L, "iron", "outer pole"),
        q(ic0, ic1, z0, z0 + Lc, "coil:inner", "inner coil"),
        q(oc0, oc1, z0, z0 + Lc, "coil:outer", "outer coil"),
    ]
    dims = {"t_wall_mm": t_w, "pole_tip_width_mm": w_p, "coil_axial_placement": placement, "r_inner_pole_tip_mm": r_pi,
            "r_outer_pole_tip_mm": r_po, "gap_mm": r_po - r_pi, "inner_coil_r_mm": [ic0, ic1], "outer_coil_r_mm": [oc0, oc1],
            "coil_z_mm": [z0, z0 + Lc], "outer_core_r_mm": [r_oc_in, R], "body_OD_mm": 2 * R,
            "inner_core_r_mm": r_c, "back_plate_z_mm": [-t_bp, 0.0], "pole_z_mm": [L - w_p, L]}
    return rects, dims


def problem(P, rects, NI_total, level, split=None, box_scale=1.0):
    m = P["mesh"]
    g = P["geometry"]["nominal"]
    split = P["operating"]["NI_split_inner"] if split is None else split
    L = g["L_mm"]
    return S.Problem(rects, {"inner": split * NI_total, "outer": (1 - split) * NI_total},
                     m["box_r_m"] * box_scale, m["box_z_m"][0] * box_scale, m["box_z_m"][1] * box_scale,
                     m["levels_h_mm"][level] * MM, m["fine_region"]["r_max_mm"] * MM,
                     (m["fine_region"]["z_mm"][0] * MM, m["fine_region"]["z_mm"][1] * MM),
                     mid_z1=m["medium_region"]["z_max_mm"] * MM, mid_factor=m["medium_region"]["factor"],
                     growth=m["growth"], h_far=m["h_far_m"],
                     extra_r=[x * MM for x in (g["d_mean_mm"] / 2, g["d_mean_mm"] / 2 - g["h_mm"] / 2,
                                               g["d_mean_mm"] / 2 + g["h_mm"] / 2)],
                     extra_z=[0.0, L * MM, 2 * L * MM])


# ---------------------------------------------------------------------------------------------------------- descriptors
def centreline(sol, P, dz_mm=0.1):
    g = P["geometry"]["nominal"]
    L = g["L_mm"]
    z = np.arange(0.0, 2 * L + 1e-9, dz_mm)
    br, bz, _ = S.field_at(sol, np.full(z.size, g["d_mean_mm"] / 2 * MM), z * MM)
    return z, br / G, bz / G


def descriptors(z, b, P):
    g = P["geometry"]["nominal"]
    L, h = g["L_mm"], g["h_mm"]
    i = int(np.argmax(b))
    zp, bp = z[i], b[i]
    if 0 < i < len(z) - 1:  # parabolic refinement
        y0, y1, y2 = b[i - 1], b[i], b[i + 1]
        den = y0 - 2 * y1 + y2
        if den < 0:
            s = 0.5 * (y0 - y2) / den
            zp = z[i] + s * (z[1] - z[0])
            bp = y1 - 0.25 * (y0 - y2) * s
    ba = float(np.interp(0.0, z, b))
    be = float(np.interp(L, z, b))
    up = np.where(b[:i] < 0.5 * bp)[0]
    z50u = float(np.interp(0.5 * bp, [b[up[-1]], b[up[-1] + 1]], [z[up[-1]], z[up[-1] + 1]])) if up.size else None
    dn = np.where(b[i:] < 0.5 * bp)[0]
    z50d = float(np.interp(0.5 * bp, [b[i + dn[0]], b[i + dn[0] - 1]], [z[i + dn[0]], z[i + dn[0] - 1]])) if dn.size else None
    seg = b[: i + 1]
    drop = float(np.max(np.maximum.accumulate(seg) - seg)) if seg.size else 0.0
    zend = P["outputs"]["domain_end_rule_mm_beyond_L"]
    return {"B_peak_G": float(bp), "z_peak_mm": float(zp), "z_peak_minus_L_mm": float(zp - L),
            "B_anode_over_B_peak": ba / bp, "B_exit_over_B_peak": be / bp,
            "z_half_max_upstream_mm": z50u, "z_half_max_downstream_mm": z50d,
            "FWHM_mm": (z50d - z50u) if (z50u is not None and z50d is not None) else None,
            "L_up_mm": (zp - z50u) if z50u is not None else None, "L_down_mm": (z50d - zp) if z50d is not None else None,
            "B_at_L_plus_domain_over_B_peak": float(np.interp(L + zend, z, b)) / bp,
            "max_drop_before_peak_over_B_peak": drop / bp,
            "mean_gradient_anode_to_peak_G_per_mm": (bp - ba) / (zp - 0.0) if zp > 0 else None,
            "h_mm": h, "L_mm": L}


def shape_tests(d, P):
    a = P["acceptance"]["H1F-BZ-02"]
    s1 = d["max_drop_before_peak_over_B_peak"] <= a["S1_monotonic_tolerance_of_B_peak"]
    lo, hi = a["S2_peak_window_relative_to_L_in_h"]
    s2 = lo * d["h_mm"] <= d["z_peak_minus_L_mm"] <= hi * d["h_mm"]
    return {"S1_monotonic_rise_to_peak": bool(s1), "S2_peak_at_or_just_downstream_of_L": bool(s2),
            "S3_B_anode_over_B_peak_reported": d["B_anode_over_B_peak"]}


# ------------------------------------------------------------------------------------------------------------ stages
def run_verify(P, work):
    V = P["verification"]
    lvl = V["mesh_level"]
    res = {}
    g = P["geometry"]["nominal"]
    rects, dims = layout(P)
    # V1: the H-1 inner and outer coils in air (no iron)
    for key, coil in (("V1a_inner_coil_air", "inner coil"), ("V1b_outer_coil_air", "outer coil")):
        cr = [q for q in rects if q.label == coil][0]
        NI = V["V1"]["NI_A"]
        q = S.Rect(cr.r0, cr.r1, cr.z0, cr.z1, "coil:c", coil)
        pb = problem(P, [q], 0.0, lvl)
        pb.coil_NI = {"c": NI}
        t = time.time()
        sol = S.solve_problem(pb, {})
        if sol.status != "OK":
            res[key] = {"status": sol.status, "note": sol.note, "pass": False}
            continue
        zz = np.arange(V["V1"]["z_range_mm"][0], V["V1"]["z_range_mm"][1] + 1e-9, 1.0)
        re = V["V1"]["axis_eval_r_mm"] * MM
        _, _, a = S.field_at(sol, np.full(zz.size, re), zz * MM)
        bz_fe = 2 * a / re
        bz_an = S.thick_solenoid_axis(cr.r0, cr.r1, cr.z0, cr.z1, NI, zz * MM)
        e_axis = float(np.max(np.abs(bz_fe - bz_an)) / np.max(np.abs(bz_an)))
        rc = g["d_mean_mm"] / 2 * MM
        br_fe, bz2_fe, _ = S.field_at(sol, np.full(zz.size, rc), zz * MM)
        br_q, bz_q = S.coil_field_quadrature(cr.r0, cr.r1, cr.z0, cr.z1, NI, np.full(zz.size, rc), zz * MM,
                                             n=V["V1"]["quadrature_n"],
                                             panel_max=V["V1"]["quadrature_panel_max_mm"] * MM)
        e_br = float(np.max(np.abs(br_fe - br_q)) / np.max(np.abs(br_q)))
        e_bz = float(np.max(np.abs(bz2_fe - bz_q)) / np.max(np.abs(bz_q)))
        # self-check of the elliptic reference on the axis against the closed form
        _, bz_q0 = S.coil_field_quadrature(cr.r0, cr.r1, cr.z0, cr.z1, NI, np.full(zz.size, 1e-7), zz * MM,
                                           n=V["V1"]["quadrature_n"],
                                             panel_max=V["V1"]["quadrature_panel_max_mm"] * MM)
        e_ref = float(np.max(np.abs(bz_q0 - bz_an)) / np.max(np.abs(bz_an)))
        crit = V["V1"]["criteria"]
        res[key] = {"status": sol.status, "dofs": sol.n_dofs, "seconds": round(time.time() - t, 1),
                    "axis_Bz_rel_err": e_axis, "centreline_Br_rel_err": e_br, "centreline_Bz_rel_err": e_bz,
                    "reference_selfcheck_rel_err": e_ref,
                    "pass": bool(sol.status == "OK" and e_axis <= crit["axis_Bz_rel_err_max"]
                                 and e_br <= crit["centreline_B_rel_err_max"] and e_bz <= crit["centreline_B_rel_err_max"]
                                 and e_ref <= crit["reference_selfcheck_max"])}
    # V2: square-section loop above a linear iron half-space (image method)
    v2 = V["V2"]
    a, dd, s = v2["loop_radius_mm"] * MM, v2["loop_height_mm"] * MM, v2["section_mm"] * MM
    for mur in v2["mu_r"]:
        lin = S.BH([[0.0, 0.0], [1e7, S.MU0 * mur * 1e7]], f"linear mu_r {mur}")
        coil = S.Rect(a - s / 2, a + s / 2, dd - s / 2, dd + s / 2, "coil:c", "loop")
        half = S.Rect(0.0, P["mesh"]["box_r_m"], P["mesh"]["box_z_m"][0], 0.0, "iron", "half-space")
        pb = problem(P, [half, coil], 0.0, lvl)
        pb.coil_NI = {"c": v2["NI_A"]}
        pb.fine_z = (-0.01, 0.06)
        pb.mid_z1 = 0.1
        t = time.time()
        sol = S.solve_problem(pb, {"iron": lin})
        if sol.status != "OK":
            res[f"V2_halfspace_mu{mur:g}"] = {"status": sol.status, "note": sol.note, "pass": False}
            continue
        rr, zz = np.meshgrid(np.array(v2["eval_r_mm"]) * MM, np.array(v2["eval_z_mm"]) * MM)
        rr, zz = rr.ravel(), zz.ravel()
        br, bz, _ = S.field_at(sol, rr, zz)
        k = (mur - 1) / (mur + 1)
        b1r, b1z = S.coil_field_quadrature(coil.r0, coil.r1, coil.z0, coil.z1, v2["NI_A"], rr, zz, n=6)
        b2r, b2z = S.coil_field_quadrature(coil.r0, coil.r1, -coil.z1, -coil.z0, k * v2["NI_A"], rr, zz, n=6)
        rer, rez = b1r + b2r, b1z + b2z
        bmax = float(np.max(np.hypot(rer, rez)))
        err = float(np.max(np.hypot(br - rer, bz - rez)) / bmax)
        # the image term must matter (else the case would not test the iron)
        img = float(np.max(np.hypot(b2r, b2z)) / bmax)
        res[f"V2_halfspace_mu{mur:g}"] = {"status": sol.status, "dofs": sol.n_dofs, "seconds": round(time.time() - t, 1),
                                          "max_rel_err": err, "image_share": img,
                                          "pass": bool(sol.status == "OK" and err <= v2["criteria"]["max_rel_err"])}
    # V3: infinite solenoid with a nonlinear iron core (Ampere: H = J t inside the winding)
    v3 = V["V3"]
    bhs = bh_sets()
    for mat in ("hiperco", "iron"):
        for H in v3["H_A_per_m"]:
            core = S.Rect(0.0, v3["core_r_mm"] * MM, 0.0, v3["height_mm"] * MM, mat, "core")
            coil = S.Rect(v3["coil_r_mm"][0] * MM, v3["coil_r_mm"][1] * MM, 0.0, v3["height_mm"] * MM, "coil:c", "winding")
            NI = H * v3["height_mm"] * MM  # H = N I / height inside an infinite solenoid
            hh = v3["h_mm"] * MM
            pb = S.Problem([core, coil], {"c": NI}, v3["outer_r_mm"] * MM, 0.0, v3["height_mm"] * MM, hh,
                           v3["outer_r_mm"] * MM, (0.0, v3["height_mm"] * MM), dirichlet="axis")
            t = time.time()
            bh = {mat: bhs["BH-NOM"][mat]}
            sol = S.solve_problem(pb, bh)
            if sol.status != "OK":
                res[f"V3_{mat}_H{H:g}"] = {"status": sol.status, "note": sol.note, "pass": False}
                continue
            zc = 0.5 * v3["height_mm"] * MM
            _, bz_fe_core, _ = S.field_at(sol, np.array([0.5 * v3["core_r_mm"] * MM]), np.array([zc]))
            _, bz_fe_gap, _ = S.field_at(sol, np.array([0.5 * (v3["core_r_mm"] + v3["coil_r_mm"][0]) * MM]), np.array([zc]))
            b_ex = float(np.interp(H, bh[mat].H, bh[mat].B)) if H <= bh[mat].H[-1] else \
                float(bh[mat].B[-1] + S.MU0 * (H - bh[mat].H[-1]))
            e1 = abs(float(bz_fe_core[0]) - b_ex) / b_ex
            e2 = abs(float(bz_fe_gap[0]) - S.MU0 * H) / (S.MU0 * H)
            res[f"V3_{mat}_H{H:g}"] = {"status": sol.status, "newton_iterations": sol.iterations,
                                       "seconds": round(time.time() - t, 1), "B_core_exact_T": b_ex,
                                       "B_core_fe_T": float(bz_fe_core[0]), "rel_err_core": e1, "rel_err_gap": e2,
                                       "pass": bool(sol.status == "OK" and e1 <= v3["criteria"]["rel_err_max"]
                                                    and e2 <= v3["criteria"]["rel_err_max"])}
    res["all_pass"] = all(v["pass"] for v in res.values() if isinstance(v, dict))
    return res


def solve_case(P, rects, NI, level, bh, cache, A0=None, split=None, box_scale=1.0):
    pb = problem(P, rects, NI, level, split=split, box_scale=box_scale)
    sol = S.solve_problem(pb, bh, mesh_cache=cache, A0=A0)
    return pb, sol


def summarize(P, pb, sol, bh):
    if sol.status != "OK":
        return {"status": sol.status, "note": sol.note}
    z, br, bz = centreline(sol, P)
    d = descriptors(z, br, P)
    d["status"] = "OK"
    d["newton_iterations"] = sol.iterations
    d["residual"] = sol.residual
    d["dofs"] = sol.n_dofs
    d["iron_Bmax_T"] = S.iron_bmax(sol, pb, bh)
    return d, (z, br, bz)


def run_convergence(P, work):
    C = P["convergence"]
    bhs = bh_sets()
    rects, _ = layout(P)
    out = {"levels": {}, "box": {}}
    for lev in C["levels"]:
        cache = {}
        out["levels"][lev] = {}
        A = None
        for NI in C["NI_A"]:
            t = time.time()
            pb, sol = solve_case(P, rects, NI, lev, bhs["BH-NOM"], cache, A0=A)
            s = summarize(P, pb, sol, bhs["BH-NOM"])
            if sol.status != "OK":
                out["levels"][lev][str(NI)] = s
                continue
            d, (z, br, _) = s
            d["seconds"] = round(time.time() - t, 1)
            d["profile_z_mm_step_1"] = [float(x) for x in z[::10]]
            d["profile_Br_G_step_1"] = [float(x) for x in br[::10]]
            out["levels"][lev][str(NI)] = d
            A = sol.A
            print(lev, NI, d["B_peak_G"], d["z_peak_mm"], d["B_anode_over_B_peak"], d["seconds"], flush=True)
    # far-boundary check at the box level / current
    for scale in (1.0, C["box_check"]["scale"]):
        pb, sol = solve_case(P, rects, C["box_check"]["NI_A"], C["box_check"]["level"], bhs["BH-NOM"], {}, box_scale=scale)
        s = summarize(P, pb, sol, bhs["BH-NOM"])
        out["box"][str(scale)] = s[0] if isinstance(s, tuple) else s
    return out


def evaluate_convergence(P, conv):
    C = P["convergence"]
    crit = C["criteria"]
    a, b = C["compare"]
    rows = []
    ok = True
    for NI in C["NI_A"]:
        da, db = conv["levels"][a].get(str(NI)), conv["levels"][b].get(str(NI))
        if not da or not db or da.get("status") != "OK" or db.get("status") != "OK":
            ok = False
            rows.append({"NI_A": NI, "status": "MODEL_ERROR"})
            continue
        pa, pb_ = np.array(da["profile_Br_G_step_1"]), np.array(db["profile_Br_G_step_1"])
        r = {"NI_A": NI,
             "dB_peak_rel": abs(da["B_peak_G"] - db["B_peak_G"]) / db["B_peak_G"],
             "dz_peak_mm": abs(da["z_peak_mm"] - db["z_peak_mm"]),
             "d_anode_ratio": abs(da["B_anode_over_B_peak"] - db["B_anode_over_B_peak"]),
             "profile_max_dB_over_B_peak": float(np.max(np.abs(pa - pb_)) / db["B_peak_G"])}
        r["pass"] = bool(r["dB_peak_rel"] <= crit["B_peak_rel"] and r["dz_peak_mm"] <= crit["z_peak_mm"]
                         and r["d_anode_ratio"] <= crit["anode_ratio_abs"]
                         and r["profile_max_dB_over_B_peak"] <= crit["profile_rel_of_B_peak"])
        ok &= r["pass"]
        rows.append(r)
    b1, b2 = conv["box"].get("1.0"), conv["box"].get(str(C["box_check"]["scale"]))
    box = None
    if b1 and b2 and b1.get("status") == "OK" and b2.get("status") == "OK":
        box = {"dB_peak_rel": abs(b1["B_peak_G"] - b2["B_peak_G"]) / b2["B_peak_G"]}
        box["pass"] = bool(box["dB_peak_rel"] <= crit["box_B_peak_rel"])
    ok &= bool(box and box["pass"])
    return {"rows": rows, "box": box, "converged": bool(ok)}


def variants(P):
    U = P["uncertainty"]
    out = [{"id": "NOM", "t_w": None, "w_p": None, "placement": None, "bh": "BH-NOM"}]
    for v in U["one_at_a_time"]:
        out.append(v)
    for v in U["corners"]:
        out.append(v)
    return out


def ni_for(sweep, target):
    """NI at which B_peak = target by linear interpolation of the monotone sweep (None outside)."""
    ni = [s["NI_A"] for s in sweep if s.get("status") == "OK"]
    bp = [s["B_peak_G"] for s in sweep if s.get("status") == "OK"]
    for (n0, b0), (n1, b1) in zip(zip(ni, bp), zip(ni[1:], bp[1:])):
        if b0 <= target <= b1:
            return n0 + (target - b0) * (n1 - n0) / (b1 - b0)
    return None


def run_sweep(P, work):
    bhs = bh_sets()
    out = {"variants": {}, "exact": {}, "split": {}}
    for v in variants(P):
        lev = P["uncertainty"]["level"] if v["id"] != "NOM" else P["production"]["level"]
        rects, dims = layout(P, v.get("t_w"), v.get("w_p"), v.get("placement"))
        cache, A, rows = {}, None, []
        for NI in P["operating"]["NI_sweep_A"]:
            t = time.time()
            pb, sol = solve_case(P, rects, NI, lev, bhs[v["bh"]], cache, A0=A)
            s = summarize(P, pb, sol, bhs[v["bh"]])
            if sol.status != "OK":
                rows.append(dict(s, NI_A=NI))
                continue
            d = s[0]
            d["NI_A"] = NI
            d["seconds"] = round(time.time() - t, 1)
            rows.append(d)
            A = sol.A
            print(v["id"], lev, NI, round(d["B_peak_G"], 2), round(d["z_peak_minus_L_mm"], 2),
                  round(d["B_anode_over_B_peak"], 4), d["seconds"], flush=True)
        out["variants"][v["id"]] = {"variant": v, "level": lev, "dims": dims, "sweep": rows}
        # exact-level solves (secant on NI) for the band ends and the capability
        exact = {}
        for lab, target in P["operating"]["B_peak_targets_G"].items():
            n0 = ni_for(rows, target)
            if n0 is None:
                exact[lab] = {"status": "NOT_REACHED_IN_SWEEP", "target_G": target}
                continue
            ni_a, ni_b = n0, n0 * 1.02
            fa = fb = sa = sb = None
            res = None
            for _ in range(8):
                if fa is None:
                    pb, sa = solve_case(P, rects, ni_a, lev, bhs[v["bh"]], cache, A0=A)
                    fa = summarize(P, pb, sa, bhs[v["bh"]])
                if fb is None:
                    pb, sb = solve_case(P, rects, ni_b, lev, bhs[v["bh"]], cache, A0=A)
                    fb = summarize(P, pb, sb, bhs[v["bh"]])
                if not (isinstance(fa, tuple) and isinstance(fb, tuple)):
                    break
                ea, eb = fa[0]["B_peak_G"] - target, fb[0]["B_peak_G"] - target
                if abs(eb) / target < P["operating"]["exact_tol_rel"]:
                    res = (ni_b, fb, sb)
                    break
                if abs(ea) / target < P["operating"]["exact_tol_rel"]:
                    res = (ni_a, fa, sa)
                    break
                ni_c = ni_b - eb * (ni_b - ni_a) / (eb - ea)
                ni_a, fa, sa, ni_b, fb = ni_b, fb, sb, ni_c, None
            if res is None:
                exact[lab] = {"status": "MODEL_ERROR", "target_G": target}
                continue
            ni, (d, (z, br, bz)), solx = res
            d = dict(d)
            d["NI_A"] = ni
            d["target_G"] = target
            d["profile"] = {"z_mm": [float(x) for x in z[::5]], "Br_G": [float(x) for x in br[::5]],
                            "Bz_G": [float(x) for x in bz[::5]]}
            d["radial"] = radial_profiles(P, solx)
            exact[lab] = d
        out["exact"][v["id"]] = exact
    # operating sensitivity: inner / outer NI split at the nominal geometry (L2), at the BP-HI NI of the nominal sweep
    rects, _ = layout(P)
    nom_hi = out["exact"]["NOM"].get("BP-HI", {}).get("NI_A")
    if nom_hi:
        for sp in P["operating"]["split_sensitivity"]:
            pb, sol = solve_case(P, rects, nom_hi, P["uncertainty"]["level"], bhs["BH-NOM"], {}, split=sp)
            s = summarize(P, pb, sol, bhs["BH-NOM"])
            out["split"][str(sp)] = s[0] if isinstance(s, tuple) else s
    return out


def radial_profiles(P, sol):
    g = P["geometry"]["nominal"]
    r = np.arange(g["d_mean_mm"] / 2 - g["h_mm"] / 2, g["d_mean_mm"] / 2 + g["h_mm"] / 2 + 1e-9, 0.5)
    out = {}
    for zz in P["outputs"]["radial_profile_z_mm"]:
        br, bz, _ = S.field_at(sol, r * MM, np.full(r.size, zz * MM))
        out[f"{zz:g}"] = {"r_mm": [float(x) for x in r], "Br_G": [float(x) for x in br / G],
                          "Bz_G": [float(x) for x in bz / G]}
    return out


def surrogate_profile(P, z_mm):
    """BZ-P5B16 as the bridge registers it (rigid, align exit: file z_ref 28.23 mm at z = L; scaled to max = 1;
    held constant beyond the data ends)."""
    rows = [ln.strip().split(",") for ln in open(SURR) if not ln.startswith("#") and ln.strip()][1:]
    zf = np.array([float(r[0]) for r in rows])
    bf = np.array([float(r[1]) for r in rows])
    L = P["geometry"]["nominal"]["L_mm"]
    zref = P["dcr_002_evaluation"]["surrogate_registration"]["z_ref_in_file_mm"]
    zm = zf - zref + L
    return np.interp(z_mm, zm, bf / bf.max())


def main():
    args = sys.argv[1:]
    work = args[args.index("--work") + 1]
    stage = args[-1]
    check_lock()
    P = prereg()
    os.makedirs(work, exist_ok=True)
    t0 = time.time()
    if stage == "verify":
        r = run_verify(P, work)
    elif stage == "convergence":
        r = run_convergence(P, work)
        r["evaluation"] = evaluate_convergence(P, r)
    elif stage == "sweep":
        r = run_sweep(P, work)
    else:
        raise SystemExit("emit is done by emit_h1_bz_fe.py")
    r["_meta"] = {"stage": stage, "seconds": round(time.time() - t0, 1), "solver": S.SOLVER_ID,
                  "solver_sha256": sha256_file(os.path.join(HERE, "h1_bz_fe_solver.py")),
                  "build_sha256": sha256_file(__file__), "python": platform.python_version(),
                  "numpy": np.__version__, "scipy": scipy.__version__}
    with open(os.path.join(work, f"{stage}.json"), "w") as f:
        json.dump(r, f, indent=1, default=lambda o: o.item() if isinstance(o, np.generic) else str(o))
    print("wrote", os.path.join(work, f"{stage}.json"), r["_meta"]["seconds"], "s")


if __name__ == "__main__":
    main()

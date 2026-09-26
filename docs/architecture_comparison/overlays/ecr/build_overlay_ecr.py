#!/usr/bin/env python3
"""ECR evidence on the ecr_hall break-even surfaces (follow-on fo_ecr_breakeven_overlay, overlay_ecr_v1).

Places the ECR source evidence (docs/evidence/ecr_source/, lane 08) on the break-even relations of breakeven_v1
(abep_sim/breakeven.py, lane 28), including the interstage transport efficiency (abep_sim/interstage.py, lane 18) and
the bus-referencing chain evidence (docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json,
lane 20), on the common boundary bus_power_boundary_v1. The output is a set of CONDITIONAL INEQUALITIES: no
prediction, no ranking, no architecture selection, no hard-gate decision, no comparison with the other pre-ionizer.

    python docs/architecture_comparison/overlays/ecr/build_overlay_ecr.py            # write overlay_ecr_v1.json + MD tables
    python docs/architecture_comparison/overlays/ecr/build_overlay_ecr.py --check    # rebuild in memory, byte-compare

Inputs are resolved lazily by repository-relative path and pinned by sha256: first the file in this checkout (after
the input lanes merge), else the git object at the pinned lane commit. A missing or changed input raises
OverlayInputError (no silent fallback). The pinned modules are executed from their verified bytes under private module
names; nothing is copied into this lane's paths and nothing is imported at module import time.

The pure functions in this file (closed forms of breakeven_v1 at equal mix, placement rules) need no input;
tests/test_overlay_ecr.py uses them to recompute the committed JSON from the values recorded in it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_JSON = HERE / "overlay_ecr_v1.json"
OUT_MD = HERE / "ECR_BREAKEVEN_OVERLAY.md"
MD_BEGIN = "<!-- BEGIN GENERATED TABLES (build_overlay_ecr.py; do not edit by hand) -->"
MD_END = "<!-- END GENERATED TABLES -->"

OVERLAY_VERSION = "overlay_ecr_v1"
FOLLOW_ON = "fo_ecr_breakeven_overlay"
TRIGGER = "T_ECR_OVERLAY"
BOUNDARY_VERSION = "bus_power_boundary_v1"
ARCH = "ecr_hall"
REFERENCE_ARCH = "hall_only"
CASES = ("add_only", "cost_offset", "optimistic_bound")
PLACEMENTS = ("CLEARLY_ABOVE_BREAKEVEN", "CLEARLY_BELOW_BREAKEVEN", "STRADDLES", "NOT_PLACEABLE")
SLICE_NAMES = ("most_favourable_corner", "mid_reference", "least_favourable_corner")
SIG = 6          # significant digits stored in the JSON

# Analysis grids of this overlay (PROPOSED; dimensionless or bus W/A, not design values)
X_GRID = (0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0)
OMEGA_GRID = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5)
Y_OVER_PI_GRID = (0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0, 1.2, 1.5)
C_SRC_BUS_GRID = (25.0, 50.0, 100.0, 150.0, 200.0, 300.0, 400.0, 500.0, 600.0, 800.0, 1000.0, 1500.0, 2000.0)
MID_ETA_U0 = 0.6   # eta_u0 of the worked reading used for the omega_f > 0 Z table (breakeven_v1 analysis value)

# ----------------------------------------------------------------------------------------------------------------------
# Pinned inputs (read-only; other lanes' deliverables, referenced by repository path)
INPUTS = {
    "ecr_evidence_matrix": {
        "path": "docs/evidence/ecr_source/ecr_evidence_matrix.json", "lane": "lane_08_ecr_evidence",
        "commit": "a85fd59261", "sha256": "4a65dbeec34f16f048fa515ced3bb959c02a981113e25da89e8bb844337fec88",
        "role": "ECR source evidence entries (reported values, power bases, sources, evidence classes)"},
    "breakeven_module": {
        "path": "abep_sim/breakeven.py", "lane": "lane_28_break_even",
        "commit": "2ad4c463d7", "sha256": "fad317b74c3f1359d849c62a7b487f2e26d8ccb3be05a35c15b515ea6d948767",
        "role": "break-even model breakeven_v1 (cross-checks: place_evidence, supremum_breakeven_delivered_cost, "
                "required_utilization_gain, bus_referred_source_cost, achievable_delivered_share, "
                "overhead_from_boundary_ledgers)"},
    "breakeven_surfaces": {
        "path": "docs/architecture_comparison/breakeven/breakeven_surfaces_v1.json", "lane": "lane_28_break_even",
        "commit": "2ad4c463d7", "sha256": "577fa11b62ee5d9c04f0d9f483d93962062f5fd40bb7aefd411eb9c0764985bc",
        "role": "PROPOSED analysis ranges and three response cases of breakeven_v1; stored surfaces (cross-check)"},
    "interstage_module": {
        "path": "abep_sim/interstage.py", "lane": "lane_18_interstage",
        "commit": "870514285c", "sha256": "bc4b9987a832209d1417f6646d2a44c72b8d79bac18f896089647bcd1ed93174",
        "role": "interstage_v1: basis of the eta_transport range (TBD catalogue, idealized limits), ionization energies"},
    "electrical_closure_data": {
        "path": "docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json",
        "lane": "lane_20_ppu_magnet", "commit": "f7c226848d",
        "sha256": "d56f700198a64a919d736c8659b6e0aaaa01cd56521885772d2f5a40de374501",
        "role": "bus-referencing chain evidence: ecr_source chain, ecr_magnet options, hall_discharge supply efficiency"},
}
DOC_REFERENCES = {
    "breakeven_derivation": "docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md",
    "breakeven_reading_guide": "docs/architecture_comparison/breakeven/BREAKEVEN_SURFACES.md",
    "interstage_model": "docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md",
    "ecr_evidence_audit": "docs/evidence/ecr_source/ECR_SOURCE_EVIDENCE.md",
    "electrical_closure": "docs/architecture_comparison/electrical_closure/ELECTRICAL_CLOSURE.md",
    "bus_power_boundary_module": "abep_sim/arch_boundary.py (bus-power boundary lane; not imported here)",
    "evidence_policy": "docs/EVIDENCE.md",
}


class OverlayInputError(RuntimeError):
    """A pinned input is missing, changed, or inconsistent (no silent fallback)."""


class OverlayCheckError(RuntimeError):
    """A self-check of the overlay failed; nothing is written."""


# ----------------------------------------------------------------------------------------------------------------------
# Pure helpers (no inputs needed)
def r6(x):
    """Round to SIG significant digits (deterministic storage); inf becomes the string 'inf'."""
    if x is None or isinstance(x, (bool, int, str)):
        return x
    if isinstance(x, float):
        if math.isnan(x):
            raise OverlayCheckError("NaN reached the output")
        if math.isinf(x):
            return "inf" if x > 0 else "-inf"
        if x == 0.0:
            return 0.0
        return float(f"{x:.{SIG}g}")
    if isinstance(x, (list, tuple)):
        return [r6(v) for v in x]
    if isinstance(x, dict):
        return {k: r6(v) for k, v in x.items()}
    return x


def case_rp(case: str, eta_b: float, eta_v: float) -> tuple:
    """(r, p) = (R_T, R_P) of a named breakeven_v1 case at equal delivered/Hall mix and alpha = 1.

    R_T = sqrt(eta_v_S/eta_v), R_P = eta_b/eta_b_S with 1/eta_b_S = 1 + (1-chi)(1/eta_b - 1) (BREAKEVEN_DERIVATION.md
    Sec. 5). add_only (chi 0, eta_v_S = eta_v): r = 1, p = 1. cost_offset (chi 1, eta_v_S = eta_v): r = 1, p = eta_b.
    optimistic_bound (chi 1, eta_v_S = 1): r = 1/sqrt(eta_v), p = eta_b."""
    for n, v in (("eta_b", eta_b), ("eta_v", eta_v)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.0 < v <= 1.0:
            raise ValueError(f"{n} must be in (0, 1], got {v!r}")
    if case == "add_only":
        return 1.0, 1.0
    if case == "cost_offset":
        return 1.0, float(eta_b)
    if case == "optimistic_bound":
        return 1.0 / math.sqrt(eta_v), float(eta_b)
    raise ValueError(f"unknown case {case!r}; expected one of {CASES}")


def efficiency_ratio_x(x: float, r: float, p: float) -> float:
    """R = eta_a(ecr_hall)/eta_a(hall_only) at relative delivered share x = delta_s/eta_u0 (alpha = 1):
    R = (1 + r x)^2 / (1 + p x)   (breakeven_v1 Sec. 5 with n1 = r, d1 = p)."""
    return (1.0 + r * x) ** 2 / (1.0 + p * x)


def g_payable(x: float, r: float, p: float) -> float:
    """Payable bus cost per delivered ampere over Pi_H with no fixed overhead: g(x) = (1 - 1/R)/x
    = (2r - p + r^2 x)/(1 + r x)^2, strictly decreasing; g(0+) = 2r - p (breakeven_v1 Sec. 6.1 marginal value)."""
    if x <= 0.0:
        return 2.0 * r - p
    return (2.0 * r - p + r * r * x) / (1.0 + r * x) ** 2


def y_payable(x: float, r: float, p: float, omega_f: float) -> float:
    """Y/Pi_H at share x with a fixed (non-ion-scaling) overhead omega_f * P_d,bus0: g(x) - omega_f/x."""
    if x <= 0.0:
        raise ValueError("x must be > 0")
    return g_payable(x, r, p) - omega_f / x


def _golden_max(f, lo: float, hi: float, iters: int = 200) -> tuple:
    gr = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    x1, x2 = b - gr * (b - a), a + gr * (b - a)
    f1, f2 = f(x1), f(x2)
    for _ in range(iters):
        if f1 < f2:
            a, x1, f1 = x1, x2, f2
            x2 = a + gr * (b - a)
            f2 = f(x2)
        else:
            b, x2, f2 = x2, x1, f1
            x1 = b - gr * (b - a)
            f1 = f(x1)
    return (x1, f1) if f1 >= f2 else (x2, f2)


def y_sup(r: float, p: float, omega_f: float, x_cap: float) -> tuple:
    """sup over x in (0, x_cap] of Y/Pi_H = g(x) - omega_f/x. Returns (value, argmax_x, attained_in_limit).

    omega_f = 0: the supremum is g(0+) = 2r - p, attained only in the limit x -> 0 (g is strictly decreasing).
    add_only (r = p = 1) with omega_f > 0: closed form (1 - sqrt(omega_f))^2 at x* = sqrt(omega_f)/(1 - sqrt(omega_f)),
    or the cap value if x* > x_cap. Otherwise: log grid + golden-section refinement (deterministic)."""
    if omega_f < 0.0 or x_cap <= 0.0:
        raise ValueError("omega_f >= 0 and x_cap > 0 required")
    if omega_f == 0.0:
        return 2.0 * r - p, 0.0, True
    if r == 1.0 and p == 1.0:
        s = math.sqrt(omega_f)
        if s < 1.0:
            xs = s / (1.0 - s)
            if xs <= x_cap:
                return (1.0 - s) ** 2, xs, False
        return y_payable(x_cap, r, p, omega_f), x_cap, False
    n = 4001
    xs = [x_cap * 10.0 ** (-8.0 + 8.0 * i / (n - 1)) for i in range(n)]
    vals = [y_payable(x, r, p, omega_f) for x in xs]
    k = max(range(n), key=lambda i: vals[i])
    if k == n - 1:
        return vals[k], xs[k], False
    lo, hi = xs[max(k - 1, 0)], xs[min(k + 1, n - 1)]
    xm, fm = _golden_max(lambda x: y_payable(x, r, p, omega_f), lo, hi)
    if fm < vals[k]:
        xm, fm = xs[k], vals[k]
    return fm, xm, False


def x_star(omega: float, r: float, p: float):
    """Required relative delivered share (= relative utilization gain at alpha = 1) at total overhead fraction omega:
    positive root of (1-omega)(1 + r x)^2 = 1 + p x. add_only: omega/(1-omega) (breakeven_v1 closed form).
    None for omega >= 1 (INFEASIBLE_OVERHEAD_GE_DISCHARGE)."""
    if omega <= 0.0:
        return 0.0
    if omega >= 1.0:
        return None
    a = (1.0 - omega) * r * r
    b = 2.0 * (1.0 - omega) * r - p
    return 2.0 * omega / (b + math.sqrt(b * b + 4.0 * a * omega))


def share_interval(y: float, omega_f: float, r: float, p: float):
    """Relative delivered shares x > 0 at which a delivered-ion bus cost y (in Pi_H units) pays with fixed overhead
    omega_f: {x : g(x) - omega_f/x >= y}. Returns [x_lo, x_hi] (x_lo = 0.0: any positive share up to x_hi) or None.
    Not capped: compare with x_cap = (1 - eta_u0)/eta_u0 separately."""
    if y <= 0.0:
        raise ValueError("y must be > 0")
    if omega_f == 0.0:
        if y >= 2.0 * r - p:
            return None
        lo, hi = 0.0, 1.0
        while g_payable(hi, r, p) > y:
            hi *= 2.0
        for _ in range(200):
            m = 0.5 * (lo + hi)
            lo, hi = (m, hi) if g_payable(m, r, p) > y else (lo, m)
        return [0.0, 0.5 * (lo + hi)]
    big = 1.0
    while g_payable(big, r, p) > 0.5 * y:
        big *= 2.0
    ymax, xm, _ = y_sup(r, p, omega_f, big)
    if ymax < y:
        return None
    f = lambda x: y_payable(x, r, p, omega_f) - y
    a, b = xm * 1e-12, xm
    for _ in range(300):
        m = 0.5 * (a + b)
        a, b = (a, m) if f(m) >= 0.0 else (m, b)
    x_lo = b
    a, b = xm, big
    for _ in range(300):
        m = 0.5 * (a + b)
        a, b = (m, b) if f(m) >= 0.0 else (a, m)
    return [x_lo, a]


def pi_h(V_d: float, eta_b: float, eta_ppu_d: float) -> float:
    """Hall-only bus price per beam ampere, Pi_H = V_d/(eta_b eta_ppu,d) [bus W per A] (breakeven_v1 Sec. 6.1)."""
    return V_d / (eta_b * eta_ppu_d)


def slice_Y(sl: dict, case: str) -> float:
    """Payable bus W per delivered A (supremum over the share, omega_f = 0) at a Hall reference slice: Pi_H (2r - p)."""
    r, p = case_rp(case, sl["eta_b"], sl["eta_v"])
    return pi_h(sl["V_d_V"], sl["eta_b"], sl["eta_ppu_d"]) * (2.0 * r - p)


def eta_t_needed(cost_bus: float, Y: float):
    """Minimum eta_t for a bus cost per SOURCE-EXIT ampere against a payable delivered cost Y; None if Y <= 0."""
    if Y <= 0.0:
        return None
    return cost_bus / Y


def classify(c_above: float, c_below: float, y_max: dict, y_min: dict, eta_t_lo: float, chain_ref: float) -> dict:
    """PROPOSED placement rule (declared basis; see placement_rules in the JSON).

    c_above: cost used for the ABOVE test (declared-basis lower cost; the ionization floor where the declared value is
      only an upper bound), c_below: declared-basis upper cost; both in W per A of source-exit ions at chain 1.
    per case c:  ABOVE_c    if c_above > y_max[c]  (eta_chain = 1, eta_t = 1, most favourable Hall reference);
                 BELOW_c    if c_below / (chain_ref * eta_t_lo) <= y_min[c]  (least favourable Hall reference, the
                            stated reference chain, every eta_t in range);
                 STRADDLES  otherwise.
    overall: CLEARLY_ABOVE_BREAKEVEN if ABOVE_c for every case; CLEARLY_BELOW_BREAKEVEN if BELOW_c for at least one
    case (below_cases lists them); STRADDLES otherwise."""
    if c_above > c_below:
        raise ValueError("c_above > c_below")
    by_case = {}
    for c in CASES:
        if c_above > y_max[c]:
            by_case[c] = "ABOVE"
        elif c_below / (chain_ref * eta_t_lo) <= y_min[c]:
            by_case[c] = "BELOW"
        else:
            by_case[c] = "STRADDLES"
    below = [c for c in CASES if by_case[c] == "BELOW"]
    if all(by_case[c] == "ABOVE" for c in CASES):
        overall = "CLEARLY_ABOVE_BREAKEVEN"
    elif below:
        overall = "CLEARLY_BELOW_BREAKEVEN"
    else:
        overall = "STRADDLES"
    return {"placement": overall, "by_case": by_case, "below_cases": below}


def straddle_dimensions(c_decl_lo: float, y_max: dict, y_min: dict, slice_Ys: dict, eta_t_lo: float,
                        phi_kind: str) -> list:
    """Dimensions on which a numeric entry's pay / no-pay outcome depends somewhere in the joint declared box
    (eta_chain in (0, 1], eta_t in [eta_t_lo, 1], the PROPOSED Hall box, the three cases); declared cost c_decl_lo.

    eta_t: the needed eta_t (chain 1) over the box, [c/Y_max_any, c/min Y_min], meets (eta_t_lo, 1].
    eta_chain: pays with a lossless chain somewhere in the box; the chain has no sourced lower bound, so it can fail.
    Hall reference: for some case and some eta_t in range, c/eta_t lies in (Y_min[c], Y_max[c]] (chain 1).
    response case: at some Hall slice and eta_t in range, c/eta_t lies in (Y_add_only, Y_optimistic] (chain 1).
    declared basis: the ion-basis factor k is assumed 1 for every entry; phi is assumed or only one-sided."""
    y_any = max(y_max.values())
    y_low = min(y_min.values())
    c_hi_t = c_decl_lo / eta_t_lo            # delivered cost at the lowest eta_t in range, chain 1
    dims = []
    if max(c_decl_lo / y_any, eta_t_lo) < min(c_decl_lo / y_low, 1.0) or eta_t_lo < c_decl_lo / y_any <= 1.0:
        dims.append("eta_t (lane-18 range)")
    if c_decl_lo <= y_any:
        dims.append("eta_chain (no sourced lower bound)")
    if any(max(c_decl_lo, y_min[c]) < min(c_hi_t, y_max[c]) or y_min[c] < c_decl_lo <= y_max[c] for c in CASES):
        dims.append("Hall reference point (PROPOSED box; needs an admitted closure)")
    if any(max(c_decl_lo, Ys["add_only"]) < min(c_hi_t, Ys["optimistic_bound"]) for Ys in slice_Ys.values()):
        dims.append("response case (alpha, chi, eta_v_S not measured)")
    dims.append("declared basis (k = 1 assumed" + ("; phi assumed)" if phi_kind == "assumed" else
                                                    "; phi only upper-bounded)"))
    return dims


# ----------------------------------------------------------------------------------------------------------------------
# Input resolution (lazy; only the build needs it)
def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_input(key: str) -> bytes:
    spec = INPUTS[key]
    tried = []
    p = REPO / spec["path"]
    if p.is_file():
        data = p.read_bytes()
        if _sha(data) == spec["sha256"]:
            return data
        tried.append(f"{spec['path']} in this checkout has sha256 {_sha(data)[:12]}... (pinned {spec['sha256'][:12]}...)")
    else:
        tried.append(f"{spec['path']} not present in this checkout")
    try:
        res = subprocess.run(["git", "-C", str(REPO), "show", f"{spec['commit']}:{spec['path']}"],
                             capture_output=True, check=False)
        if res.returncode == 0 and _sha(res.stdout) == spec["sha256"]:
            return res.stdout
        tried.append(f"git object {spec['commit']}:{spec['path']} "
                     + ("sha256 mismatch" if res.returncode == 0 else "not available"))
    except OSError as exc:
        tried.append(f"git not runnable ({exc})")
    raise OverlayInputError(
        f"input {key!r} ({spec['lane']}, {spec['path']}) could not be resolved with the pinned sha256: "
        + "; ".join(tried) + ". Regenerate the overlay against the current input (update INPUTS) after review.")


def inputs_available() -> bool:
    try:
        for k in INPUTS:
            read_input(k)
    except OverlayInputError:
        return False
    return True


def load_module(key: str, private_name: str):
    """Execute a pinned module's verified bytes as a submodule of abep_sim (relative imports resolve to this
    checkout's abep_sim, e.g. abep_sim.constants) under a private name; never written to disk."""
    src = read_input(key).decode("utf-8")
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    import abep_sim  # noqa: F401  (parent package for the relative imports)
    name = f"abep_sim.{private_name}"
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    mod.__package__ = "abep_sim"
    mod.__file__ = f"<{INPUTS[key]['path']} @ {INPUTS[key]['commit']}>"
    sys.modules[name] = mod
    try:
        exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    except Exception:
        del sys.modules[name]
        raise
    return mod


def load_json_input(key: str) -> dict:
    return json.loads(read_input(key).decode("utf-8"))


# ----------------------------------------------------------------------------------------------------------------------
# Hand-transcribed placement specifications. Every number is read from the matrix at build time; the strings below
# restate the matrix's own power-basis and ion-basis wording (uncertainty / conditions / audit Sec. 4.3, 4.6).
# phi_kind: 'assumed' (plane not stated: phi = 1, neither bound), 'definitional_upper' (incident power, reflected not
# subtracted: phi <= 1), 'sourced_upper' (phi <= the value of phi_ref).
PLACEABLE = {
    "ECR-D018": {
        "current_ref": "ECR-E070", "mode": "xe", "device": "JAXA mu20, 20 cm gridded microwave (ECR) ion thruster",
        "power_reference_class": "not stated (forward or absorbed)", "phi_kind": "assumed",
        "power_plane_as_stated": "microwave power, 100 W; forward vs absorbed not stated (lane 08 ECR-D018 uncertainty)",
        "ion_basis_as_stated": "grid-extracted Xe ion beam current (0.5 A, ECR-E070)", "gridded": True},
    "ECR-D019": {
        "current_ref": "ECR-E079", "mode": "xe", "device": "JAXA mu10 (improved laboratory version), gridded",
        "power_reference_class": "not stated (forward or absorbed)", "phi_kind": "assumed",
        "power_plane_as_stated": "'microwave input', 34 W; forward vs absorbed not stated (ECR-E079 conditions)",
        "ion_basis_as_stated": "grid-extracted Xe ion beam current, 191-195 mA (source internally inconsistent, "
                               "ECR-E079)", "gridded": True},
    "ECR-D023": {
        "current_ref": "ECR-E077", "mode": "xe", "device": "Kyushu 10 cm microwave (ECR) ion thruster, gridded",
        "power_reference_class": "forward (incident; reflected power not subtracted)", "phi_kind": "definitional_upper",
        "power_plane_as_stated": "incident power Pi = 32 W; Pr not subtracted, so the net-power cost is <= the value "
                                 "(ECR-D023 value_qualifier upper_bound)",
        "ion_basis_as_stated": "grid-extracted Xe ion beam current (85 mA, ECR-E077)", "gridded": True},
    "ECR-D020": {
        "current_ref": "ECR-E088", "mode": "air_N2", "device": "10 cm N2 ECR gridded ion source (Tan et al. 2026)",
        "power_reference_class": "not stated (forward or absorbed)", "phi_kind": "assumed",
        "power_plane_as_stated": "'input microwave power', 55 W; forward vs absorbed not stated (ECR-D020 uncertainty; "
                                 "abstract only)",
        "ion_basis_as_stated": "extracted N2 ion beam current, 0.258 A; N2+ and N+ not separated "
                               "(ECR_SOURCE_EVIDENCE.md Sec. 4.6, ECR-D030)", "gridded": True},
    "ECR-E081": {
        "current_ref": None, "mode": "air_N2", "device": "2 cm N2 ECR ion source, experiment (Tan et al. 2023)",
        "power_reference_class": "not stated ('input power')", "phi_kind": "assumed",
        "power_plane_as_stated": "'input power', 8 W; basis not specified in the abstract (ECR-E081 uncertainty)",
        "ion_basis_as_stated": "source-stated 'ion energy loss' of the extracted N2 ion beam (abstract only)",
        "gridded": True, "consistency_ref": "ECR-E084"},
    "ECR-E083": {
        "current_ref": None, "mode": "air_N2", "device": "2 cm N2 ECR ion source, the source's own global model",
        "power_reference_class": "not stated ('input power', model)", "phi_kind": "assumed",
        "power_plane_as_stated": "'input power' 8 W of the source's global model at 1 ml/min (basis not specified)",
        "ion_basis_as_stated": "modelled extracted N2 ion beam; model-experiment relative errors 2-32 % (ECR-E087)",
        "gridded": True},
    "ECR-D021": {
        "current_ref": "ECR-E091", "mode": "xe", "device": "ONERA coaxial ECR magnetic-nozzle thruster (gridless)",
        "power_reference_class": "forward side: 'transmitted' (= forward minus reflected) at a directional coupler "
                                 "upstream of >= 2 dB of chain loss", "phi_kind": "sourced_upper", "phi_ref": "ECR-D015",
        "power_plane_as_stated": "'transmitted' power 51 W measured upstream of >= 2 dB of line loss (ECR-E032, "
                                 "ECR-D015)",
        "ion_basis_as_stated": "total plume ion current, probe-reconstructed at 30 cm (65.4 mA; gridless exit, "
                               "ECR-E091)", "gridded": False},
}
NOT_PLACEABLE = {
    "ECR-E072": {"mode": "xe", "missing": ["microwave power at a stated operating point (the source gives only "
                                           "'saturates at 0.150 A for microwave powers above 30 W', ECR-E072)"],
                 "note": "a lower bound P/I > 30 W / 0.150 A follows for any P > 30 W at saturation (computed below), but "
                         "no operating point is specified, so no cost interval can be placed"},
    "ECR-E084": {"mode": "air_N2", "missing": ["the source's definition of 'ion energy loss' and the input power at "
                                               "the maximum-current point (full text not accessed)"],
                 "note": "lane 08 records no power-per-current value for this point; see consistency_check"},
    "ECR-E097": {"mode": "air_N2_O", "missing": ["microwave power (not given in the accessed secondary text)",
                                                 "power reference plane"],
                 "note": "the only ECR ion-beam evidence that includes atomic oxygen (secondary citation, 16 mA, "
                         "space-charge limited; ECR-E097)"},
    "ECR-E075": {"mode": "out_of_scope_gas", "missing": ["a measurement on an in-scope propellant (N2/O/O2/air "
                                                         "mixture or Xe); no Ar-to-air transfer rule is sourced"],
                 "note": "argon (RFP propellants: air + Xe); kept by lane 08 only for the net-power definition"},
    "ECR-D022": {"mode": "out_of_scope_gas", "missing": ["a measurement on an in-scope propellant (N2/O/O2/air "
                                                         "mixture or Xe)"],
                 "note": "argon, outside the RFP propellant scope"},
}
GAP_ROWS = {
    "GAP-ECR-O-O2-AIR": {"mode": "air_O_O2", "quantity": "ECR ion production cost on O2, atomic O or an N2/O/O2 mixture",
                         "missing": ["any ECR ion-source ion production cost on O2, atomic O or an N2/O/O2 mixture: "
                                     "none exists in the ECR evidence matrix (ECR_SOURCE_EVIDENCE.md finding 2)"]},
}
X_SIDE_CONTEXT = ("ECR-E082", "ECR-D030", "ECR-E073", "ECR-E092")
CHAIN_EVIDENCE = ("ECR-D015", "ECR-D016", "ECR-D017", "ECR-E030", "ECR-E031", "ECR-E032", "ECR-E033", "ECR-E034",
                  "ECR-E035", "ECR-E040", "ECR-E041", "ECR-E042", "ECR-E044", "ECR-E045", "ECR-E046", "ECR-E047")
FIXED_OVERHEAD_EVIDENCE = ("ECR-E066", "ECR-E067")
COVERED_BY = {"ECR-E070": "ECR-D018", "ECR-E079": "ECR-D019", "ECR-E077": "ECR-D023", "ECR-E088": "ECR-D020",
              "ECR-E091": "ECR-D021", "ECR-E094": "ECR-D022", "ECR-E078": "ECR-E075",
              "ECR-D025": "unit identity used in every conversion (1 W/A = 1 eV per singly charged ion)"}
ELECTRON_CURRENT = ("ECR-E099", "ECR-E100", "ECR-E101", "ECR-E104", "ECR-E105", "ECR-E106", "ECR-E107", "ECR-E111",
                    "ECR-E112", "ECR-E113", "ECR-E114", "ECR-E115", "ECR-E116")

# Wording that would state a result this overlay does not produce (tests/test_overlay_ecr.py scans the outputs; the
# list itself is stored in the JSON under forbidden_patterns and excluded from the scan).
FORBIDDEN_PATTERNS = (r"\bwinner\s+is\b", r"\bis\s+the\s+winner\b", r"\bwins\b", r"\beliminated\b",
                      r"\beliminates\b", r"\bbest\s+architecture\b", r"\bsuperior\b", r"\boutperform",
                      r"\brf_hall\b", r"\brecommended\s+architecture\b", r"\bpreferred\s+architecture\b",
                      r"\bselected\s+as\s+(the\s+)?baseline\b", r"\bis\s+the\s+baseline\b", r"\bbetter\s+than\b",
                      r"sgb-screen")


# ----------------------------------------------------------------------------------------------------------------------
def _entry_index(matrix: dict) -> dict:
    idx = {}
    for e in matrix["entries"]:
        if e["id"] in idx:
            raise OverlayInputError(f"duplicate matrix id {e['id']}")
        idx[e["id"]] = e
    return idx


def _num_list(v) -> list:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return [float(v)]
    if isinstance(v, list) and v and all(isinstance(t, (int, float)) and not isinstance(t, bool) for t in v):
        return [float(t) for t in v]
    raise OverlayInputError(f"expected a number or list of numbers, got {v!r}")


def _reported_block(e: dict) -> dict:
    s = e["source"]
    c = e.get("conditions") or {}
    return {"matrix_id": e["id"], "quantity": e["quantity"], "value": e["value"], "unit": e.get("units"),
            "value_qualifier": e.get("value_qualifier"), "evidence_class": e["evidence_class"],
            "uncertainty": e.get("uncertainty"), "gas": c.get("gas"), "power_W": c.get("power_W"),
            "frequency_Hz": c.get("frequency_Hz"), "citation": s["citation"], "doi_or_url": s["doi_or_url"],
            "access": s["access"], "source_kind": s["source_kind"], "locator": s.get("locator")}


def _chain_evidence(ec: dict, midx: dict) -> dict:
    """Bus -> net-microwave-power-at-coupling-input chain evidence for ecr_source (lane 20 + lane 08)."""
    comp = ec["components"]["ecr_source"]
    ents = {e["id"]: e for e in comp["entries"]}
    tw, gan, mag = ents["EC-HAYABUSA-TWTA"], ents["EC-NAKATANI15-GAN"], ents["EC-KAZAKEVICH24-MAG"]
    iso, load = ents["EC-ISOLATOR-FEED"], ents["EC-LOAD"]
    d017, e045, e042 = midx["ECR-D017"], midx["ECR-E045"], midx["ECR-E042"]
    if abs(float(tw["value"]) - float(d017["value"])) > 1e-9:
        raise OverlayInputError("lane 20 EC-HAYABUSA-TWTA and lane 08 ECR-D017 disagree")
    stage_rule = [r for r in ec["rules"] if "Stage-only" in r]
    if not stage_rule:
        raise OverlayInputError("electrical closure rule on stage-only efficiencies not found")
    if comp["load_plane"] != "net microwave power at the ECR coupling input":
        raise OverlayInputError(f"ecr_source load plane changed: {comp['load_plane']!r}")
    return {
        "component": "ecr_source", "load_plane": comp["load_plane"], "load_status": comp["load_status"],
        "definition": "eta_chain = P_load(ecr_source) / P_bus[ecr_source]: bus input terminal -> net microwave power "
                      "at the ECR coupling input (DC-DC, driver, amplifier or tube, isolator/circulator, feed)",
        "definitional_upper_bound": {"value": 1.0, "evidence_class": "model-derived",
                                     "source": "definition (a passive chain cannot deliver more power than it draws)"},
        "reference_chain": {
            "value": float(tw["value"]), "evidence_class": tw["evidence_class"],
            "evidence_level": tw["evidence_level"],
            "source": f"lane 20 {tw['id']} ({tw['locator']}); same value as lane 08 ECR-D017",
            "chain_stage": tw["chain_stage"], "uncertainty": tw["uncertainty"],
            "applicability": tw["applicability"], "validation_status": tw["validation_status"],
            "use": "the only system-level DC->RF value for an ECR source in either evidence lane (4.2 GHz TWT, flight "
                   "heritage); used as the STATED chain of the CLEARLY_BELOW test and of the reference-chain columns, "
                   "not as a bound (the ABEP chain may be higher or lower)"},
        "stage_only_upper_bounds": [
            {"id": gan["id"], "value": gan["value"], "evidence_class": gan["evidence_class"],
             "chain_stage": gan["chain_stage"], "source_ids": gan["source_ids"], "uncertainty": gan["uncertainty"]},
            {"id": mag["id"], "value": mag["value"], "evidence_class": mag["evidence_class"],
             "chain_stage": mag["chain_stage"], "source_ids": mag["source_ids"], "uncertainty": mag["uncertainty"]},
            {"id": e045["id"], "value": e045["value"], "evidence_class": e045["evidence_class"],
             "chain_stage": "GaN HEMT PA device, power-added efficiency (lane 08)", "source": e045["source"]["citation"],
             "uncertainty": e045.get("uncertainty")},
            {"id": e042["id"], "value": e042["value"], "value_qualifier": "lower bound on a 5 W breadboard ('> 0.70')",
             "evidence_class": e042["evidence_class"], "chain_stage": "solid-state amplifier breadboard (lane 08)",
             "source": e042["source"]["citation"], "uncertainty": e042.get("uncertainty")}],
        "stage_only_rule": stage_rule[0],
        "missing": [{"id": iso["id"], "quantity": iso["quantity"], "tbd_requires": iso["tbd_requires"]},
                    {"id": load["id"], "quantity": load["quantity"], "tbd_requires": load["tbd_requires"]},
                    {"id": "ABEP-CHAIN", "quantity": "bus -> coupling-input efficiency of the candidate flight "
                     "microwave chain (DC-DC, driver, amplifier/tube, isolator, feed) at the chosen frequency and power",
                     "tbd_requires": "measurement on the candidate flight microwave chain (ECR_SOURCE_EVIDENCE.md "
                                     "Sec. 4.4, Sec. 6 item 5)"}],
        "lower_bound": "none sourced: the bus cost of every reported value is unbounded above until the ABEP chain is "
                       "measured",
    }


def _ppu_discharge_range(ec: dict) -> dict:
    comp = ec["components"]["hall_discharge"]
    ids = list(comp["efficiency_evidence"])
    ents = {e["id"]: e for e in comp["entries"]}
    vals = [float(pt["efficiency"]) for i in ids for pt in ents[i]["value"]]
    if not vals:
        raise OverlayInputError("no hall_discharge supply efficiency evidence")
    e0 = ents[ids[0]]
    return {"min": min(vals), "max": max(vals), "ids": ids, "evidence_class": e0["evidence_class"],
            "evidence_level": e0["evidence_level"], "source_ids": e0["source_ids"], "locator": e0["locator"],
            "chain_stage": e0["chain_stage"], "applicability": e0["applicability"],
            "validation_status": e0["validation_status"], "n_points": len(vals)}


def _fixed_overhead_evidence(ec: dict, midx: dict) -> dict:
    comp = ec["components"]["ecr_magnet"]
    ents = {e["id"]: e for e in comp["entries"]}
    pm, sup = ents["EM-PM-OPTION"], ents["EM-SUPPLY-EFF"]
    return {
        "definition": "omega_f = (P_bus[ecr_magnet] + sum over common components except hall_discharge of "
                      "(P_bus,ecr_hall - P_bus,hall_only)) / P_bus,hall_only[hall_discharge]; the ecr_source generator "
                      "term is the ion-scaling part (breakeven.overhead_from_boundary_ledgers -> BusOverhead.generator_W "
                      "and BusOverhead.fixed_W)",
        "permanent_magnet_option": {"id": pm["id"], "value_W": pm["value"], "evidence_class": pm["evidence_class"],
                                    "note": pm["transformation_chain"]},
        "electromagnet_option": {"status": "TBD", "tbd_requires": comp["load_status"],
                                 "supply_efficiency": {"id": sup["id"], "tbd_requires": sup["tbd_requires"]},
                                 "evidence": [{"id": i, "quantity": midx[i]["quantity"], "value": midx[i]["value"],
                                               "unit": midx[i].get("units"),
                                               "evidence_class": midx[i]["evidence_class"]}
                                              for i in FIXED_OVERHEAD_EVIDENCE],
                                 "reading": "no accessed open source gives the main-field electromagnet power of an ECR "
                                            "stage (ECR_SOURCE_EVIDENCE.md Sec. 4.5): ECR-E067 gives a coil current "
                                            "without power, ECR-E066 is a 14 G steering coil pair, not a resonance field"},
        "common_deltas": "TBD - requires the two bus_power_boundary_v1 ledgers at the same operating mode",
        "analysis_values": "PROPOSED omega_f grid of breakeven_v1 (0 is the permanent-magnet, zero-delta case)",
        "effect": "omega_f > 0 lowers the payable Y (tables Y_over_Pi_H_vs_X, Y_sup_over_Pi_H) and makes a minimum share "
                  "X_lo > 0 necessary (table payable_X_interval)",
    }


def _interstage_basis(ist, surfaces: dict) -> dict:
    tbd_keys = ("junction_ion_capture_fraction", "magnetized_cross_field_h",
                "dissociative_recombination:N2+@Te>1200K", "dissociative_recombination:O2+@Te>1200K",
                "ion_neutral_cross_section:N2+/N2", "ion_neutral_cross_section:O+/O",
                "ion_neutral_cross_section:Xe+/Xe", "wall_atom_recombination:N", "wall_atom_recombination:O")
    tbd = []
    for k in tbd_keys:
        rec = ist.CATALOGUE.get(k)
        if rec is None or not isinstance(rec, ist.TBD):
            raise OverlayInputError(f"interstage catalogue entry {k!r} is no longer TBD; the eta_t basis must be revised")
        tbd.append({"key": k, "requires": rec.requires})
    dr = ist.catalogue_entry("dissociative_recombination:N2+")
    et = surfaces["inputs"]["eta_transport"]
    return {
        "model": f"abep_sim/interstage.py {ist.MODEL_VERSION}",
        "definition": "eta_t = ion current delivered into the Hall channel / ion current leaving the source exit "
                      "(charge-current basis, INTERSTAGE_MODEL.md Sec. 2; pairs with costs in W per A of source-exit "
                      "ions)",
        "range": [min(et["values"]), max(et["values"])],
        "range_status": et["status"] + " (breakeven_v1 analysis axis)",
        "range_basis": [
            "interstage_v1 computes no eta_t for any realistic air or Xe case: the inputs below are TBD and the model "
            "refuses (InterstageTBDError / InterstageDomainError), which is its intended behaviour "
            "(INTERSTAGE_MODEL.md Sec. 6)",
            f"the only sourced N2+ dissociative-recombination rate is stated for T < {dr.validity_max:g} K "
            "(Sheehan & St.-Maurice 2004, abstract only), far below interstage electron temperatures",
            "upper end 1: model-derived idealized limit of interstage_v1 (zero-length duct, junction capture 1, no leak "
            "path: eta_transport = 1 exactly; test_zero_length_gives_unit_transport_and_no_losses); eta_t > 1 needs "
            "in-duct ionization and is refused by breakeven_v1",
            "no sourced lower bound: a junction closed to the Hall channel transmits nothing "
            "(test_closed_channel_transmits_nothing); the lower end 0.1 is the owner-requested PROPOSED analysis span, "
            "not a physical bound"],
        "tbd_inputs": tbd,
        "evidence_class": "assumed (PROPOSED analysis range); endpoint 1 model-derived as stated",
        "same_for_every_entry": "yes: interstage_v1 is one model and the eta_t of every ECR exit state is TBD",
    }


def _floors(ist) -> dict:
    ie = {k: ist.catalogue_entry(f"ionization_energy:{k}") for k in ("N2", "N", "Xe", "O")}
    for k in ("N", "O", "Xe"):   # second ionization energies above the first: multiply charged ions do not go lower
        if not float(ist.catalogue_entry(f"ionization_energy:{k}+").value) > float(ie[k].value):
            raise OverlayInputError(f"ionization energies of {k} not increasing")
    n2_floor = min(float(ie["N2"].value), float(ie["N"].value))

    def rec(value, keys, feed):
        return {"value_W_per_A": value, "feed": feed,
                "evidence_class": "model-derived (energy conservation on measured ionization energies)",
                "source": "; ".join(f"interstage_v1 CATALOGUE['ionization_energy:{k}'] = {float(ie[k].value):g} eV "
                                    f"({ie[k].evidence_class}): {ie[k].source}" for k in keys)}
    return {
        "values": {"N2_feed": rec(n2_floor, ("N2", "N"), "pure N2 feed (ions N2+, N+ and multiply charged ions)"),
                   "Xe_feed": rec(float(ie["Xe"].value), ("Xe",), "pure Xe feed"),
                   "O_feed": rec(float(ie["O"].value), ("O",), "atomic-O feed only (no placed evidence)")},
        "air_mixture_feed": "TBD - requires the O2 ionization energy (interstage_v1 CATALOGUE['ionization_energy:O2'] "
                            "is TBD)",
        "rule": "bus power per ampere of ion current (1 W/A = 1 eV per elementary charge, ECR-D025) cannot be below the "
                "lowest first ionization energy among the feed's species: an ion of charge Z needs the sum of Z "
                "successive ionization energies, each larger than the first (checked on the catalogue for N, O, Xe), "
                "and N+ formed from N2 also needs the positive N2 dissociation energy (its value is TBD in "
                "interstage_v1, so the N2-feed floor uses IE(N) as a strict lower bound). Holds for every power plane, "
                "ion basis, chain and eta_t; a strict model-derived lower bound",
        "evidence_class": "model-derived",
    }


def _phi_sensitivity(midx: dict) -> dict:
    """Illustrative spread of phi for an unstated power plane, from other devices' measured chain factors (lane 08).
    NOT a bound for any entry (device and frequency transfer is not established)."""
    d016 = _num_list(midx["ECR-D016"]["value"])
    e030 = _num_list(midx["ECR-E030"]["value"])
    e031 = _num_list(midx["ECR-E031"]["value"])
    coupling = e030 + e031
    return {
        "if_reported_is_generator_forward": {"phi_range": [min(d016), max(d016)],
                                             "basis": "coaxial line transmission Pin/P0 measured without plasma "
                                                      "(ECR-D016, inferred from ECR-E033); reflected power neglected"},
        "if_reported_is_absorbed": {"phi_range": [1.0 / max(coupling), 1.0 / min(coupling)],
                                    "basis": "phi = 1/coupling rate, coupling 0.78-0.99 measured on ONERA ECRA 30 W and "
                                             "200 W xenon thrusters (ECR-E030, ECR-E031)"},
        "status": "illustrative sensitivity from other devices; not a bound for this entry",
    }


def _payable_x_at_mid(c: float, mid: dict) -> dict:
    """Payable relative-share interval [0, X_hi] of a delivered cost c at the mid-reference slice (omega_f = 0)."""
    return {case: share_interval(c / mid["Pi_H_W_per_A"], 0.0, *case_rp(case, mid["eta_b"], mid["eta_v"]))
            for case in CASES}


# ----------------------------------------------------------------------------------------------------------------------
def build() -> tuple:
    """Return (json_text, md_block_text). Raises OverlayInputError / OverlayCheckError."""
    matrix = load_json_input("ecr_evidence_matrix")
    surfaces = load_json_input("breakeven_surfaces")
    ec = load_json_input("electrical_closure_data")
    bk = load_module("breakeven_module", "_overlay_ecr_pinned_breakeven")
    ist = load_module("interstage_module", "_overlay_ecr_pinned_interstage")
    if bk.BOUNDARY_VERSION != BOUNDARY_VERSION or ec["boundary_version"] != BOUNDARY_VERSION \
            or surfaces["boundary"]["version"] != BOUNDARY_VERSION:
        raise OverlayInputError("boundary version mismatch across inputs")
    if tuple(bk.SOURCE_COMPONENTS[ARCH]) != ("ecr_source", "ecr_magnet"):
        raise OverlayInputError("breakeven_v1 ecr_hall source components changed")
    if not ist.architecture_has_interstage(ARCH):
        raise OverlayInputError("interstage_v1 does not model an interstage for ecr_hall")
    midx = _entry_index(matrix)
    inp = surfaces["inputs"]

    # ---------------- analysis ranges (breakeven_v1 PROPOSED box; eta_ppu,d from the lane-20 evidence envelope)
    V_vals = [float(v) for v in inp["V_d_V"]["values"]]
    eb_vals = [float(v) for v in inp["eta_b"]["values"]]
    eu_vals = [float(v) for v in inp["eta_u0"]["values"]]
    ev_opt = [float(v) for v in inp["eta_v"]["values_universal_optimistic"]]
    wf_vals = [float(v) for v in inp["omega_fixed"]["values"]]
    et_vals = [float(v) for v in inp["eta_transport"]["values"]]
    ev_mid = float(inp["eta_v"]["value_dimensional"])
    ppu_mid = float(inp["eta_ppu_discharge"]["value"])
    ppu = _ppu_discharge_range(ec)
    ppu_vals = [ppu["min"], ppu["max"]]
    if not ppu["min"] <= ppu_mid <= ppu["max"]:
        raise OverlayInputError("breakeven_v1 eta_ppu,d is outside the lane-20 evidence envelope")
    if 300.0 not in V_vals or 0.7 not in eb_vals or MID_ETA_U0 not in eu_vals:
        raise OverlayInputError("the worked-reading slice (300 V, eta_b 0.7, eta_u0 0.6) left the analysis grid")
    chain = _chain_evidence(ec, midx)
    chain_ref = chain["reference_chain"]["value"]
    it_basis = _interstage_basis(ist, surfaces)
    eta_t_lo, eta_t_hi = it_basis["range"]
    floors = _floors(ist)
    cases_src = surfaces["cases"]
    for c in CASES:
        if c not in cases_src:
            raise OverlayInputError(f"case {c} missing from breakeven_surfaces")
    if not (cases_src["add_only"]["alpha"] == 1.0 and cases_src["add_only"]["chi"] == 0.0
            and cases_src["cost_offset"]["alpha"] == 1.0 and cases_src["cost_offset"]["chi"] == 1.0
            and cases_src["optimistic_bound"]["alpha"] == 1.0 and cases_src["optimistic_bound"]["chi"] == 1.0
            and cases_src["add_only"]["eta_v_delivered"] == "= eta_v"
            and cases_src["cost_offset"]["eta_v_delivered"] == "= eta_v"
            and cases_src["optimistic_bound"]["eta_v_delivered"] == 1.0):
        raise OverlayInputError("case definitions in breakeven_surfaces changed")

    slices = {
        "most_favourable_corner": {"V_d_V": max(V_vals), "eta_b": min(eb_vals), "eta_ppu_d": ppu["min"],
                                   "eta_v": min(ev_opt),
                                   "meaning": "largest Pi_H and largest case factors in the PROPOSED box"},
        "mid_reference": {"V_d_V": 300.0, "eta_b": 0.7, "eta_ppu_d": ppu_mid, "eta_v": ev_mid,
                          "meaning": "the worked reading of BREAKEVEN_SURFACES.md (300 V, eta_b 0.7, eta_ppu,d 0.9, "
                                     "eta_v 0.9); eta_ppu,d 0.9 lies inside the lane-20 evidence envelope"},
        "least_favourable_corner": {"V_d_V": min(V_vals), "eta_b": max(eb_vals), "eta_ppu_d": ppu["max"],
                                    "eta_v": max(ev_opt),
                                    "meaning": "smallest Pi_H and smallest case factors in the PROPOSED box"},
    }
    for sl in slices.values():
        sl["Pi_H_W_per_A"] = pi_h(sl["V_d_V"], sl["eta_b"], sl["eta_ppu_d"])
        sl["Y_W_per_A"] = {c: slice_Y(sl, c) for c in CASES}
    box = [(V, eb, pp, ev) for V in V_vals for eb in eb_vals for pp in ppu_vals for ev in ev_opt]
    Y_max_by_case = {c: max(pi_h(V, eb, pp) * (2 * case_rp(c, eb, ev)[0] - case_rp(c, eb, ev)[1])
                            for V, eb, pp, ev in box) for c in CASES}
    Y_min_by_case = {c: min(pi_h(V, eb, pp) * (2 * case_rp(c, eb, ev)[0] - case_rp(c, eb, ev)[1])
                            for V, eb, pp, ev in box) for c in CASES}
    for c in CASES:
        if abs(Y_max_by_case[c] - slices["most_favourable_corner"]["Y_W_per_A"][c]) > 1e-9 * Y_max_by_case[c]:
            raise OverlayCheckError(f"most favourable corner is not the box maximum for {c}")
        if abs(Y_min_by_case[c] - slices["least_favourable_corner"]["Y_W_per_A"][c]) > 1e-9 * Y_min_by_case[c]:
            raise OverlayCheckError(f"least favourable corner is not the box minimum for {c}")
    Y_max_any = max(Y_max_by_case.values())
    slice_Ys = {s: slices[s]["Y_W_per_A"] for s in SLICE_NAMES}

    # ---------------- (1) X, Y, Z tables
    combos = [("add_only", None, None)] + [("cost_offset", eb, None) for eb in eb_vals] + \
             [("optimistic_bound", eb, ev) for eb in eb_vals for ev in ev_opt]

    def _key(c, eb, ev):
        return c + ("" if eb is None else f"|eta_b={eb:g}") + ("" if ev is None else f"|eta_v={ev:g}")

    def _rp(c, eb, ev):     # add_only does not depend on eta_b, eta_v; cost_offset not on eta_v (any valid value)
        return case_rp(c, eb if eb is not None else 0.7, ev if ev is not None else ev_mid)

    y_of_x = {_key(*k): {f"omega_f={wf:g}": [y_payable(x, *_rp(*k), wf) for x in X_GRID] for wf in wf_vals}
              for k in combos}
    y_sup_tab = {}
    for k in combos:
        r, p = _rp(*k)
        y_sup_tab[_key(*k)] = {
            f"eta_u0={eu:g}": {f"omega_f={wf:g}": dict(zip(("Y_over_Pi_H", "argmax_X", "attained_in_limit"),
                                                             y_sup(r, p, wf, (1.0 - eu) / eu))) for wf in wf_vals}
            for eu in eu_vals}
    x_of_omega = {_key(*k): [x_star(w, *_rp(*k)) for w in OMEGA_GRID] for k in combos}
    x_interval = {_key(*k): {f"omega_f={wf:g}": [share_interval(y, wf, *_rp(*k)) for y in Y_OVER_PI_GRID]
                             for wf in wf_vals} for k in combos}
    x_caps = {f"eta_u0={eu:g}": (1.0 - eu) / eu for eu in eu_vals}
    pi_tab = {f"eta_ppu_d={pp:g}": {f"eta_b={eb:g}": [pi_h(V, eb, pp) for V in V_vals] for eb in eb_vals}
              for pp in ppu_vals}
    Y_dim = {}
    for pp in ppu_vals:
        for eb in eb_vals:
            for c in CASES:
                for ev in (ev_opt if c == "optimistic_bound" else [None]):
                    r, p = case_rp(c, eb, ev if ev is not None else ev_mid)
                    Y_dim[f"eta_ppu_d={pp:g}|eta_b={eb:g}|{c}" + ("" if ev is None else f"|eta_v={ev:g}")] = \
                        [pi_h(V, eb, pp) * (2 * r - p) for V in V_vals]
    z_tab = {s: {c: [eta_t_needed(C, slices[s]["Y_W_per_A"][c]) for C in C_SRC_BUS_GRID] for c in CASES}
             for s in SLICE_NAMES}
    mid = slices["mid_reference"]
    z_mid_wf = {}
    for c in CASES:
        r, p = case_rp(c, mid["eta_b"], mid["eta_v"])
        row = {}
        for wf in wf_vals:
            ys = y_sup(r, p, wf, (1.0 - MID_ETA_U0) / MID_ETA_U0)[0] * mid["Pi_H_W_per_A"]
            row[f"omega_f={wf:g}"] = [eta_t_needed(C, ys) for C in C_SRC_BUS_GRID]
        z_mid_wf[c] = row

    # ---------------- (2) evidence placements
    phi_sens = _phi_sensitivity(midx)
    placements = []
    for eid, spec in PLACEABLE.items():
        e = midx[eid]
        if e.get("units") != "W/A":
            raise OverlayInputError(f"{eid} is not in W/A")
        vals = _num_list(e["value"])
        c_rep = [min(vals), max(vals)]
        floor = floors["values"]["Xe_feed" if spec["mode"] == "xe" else "N2_feed"]["value_W_per_A"]
        phi_step = {"step": "power plane -> net microwave power at the ABEP coupling input (phi = P_cp / P_reported)"}
        if spec["phi_kind"] == "sourced_upper":
            d = midx[spec["phi_ref"]]
            phi = float(d["value"])
            phi_step.update(value_used=phi, bound_type=f"upper bound on phi ({d['quantity']})",
                            evidence_class=d["evidence_class"], source=f"lane 08 {d['id']}", status="sourced bound")
            decl_type = "upper bound on the coupling-input cost (reported x sourced upper bound on phi)"
        elif spec["phi_kind"] == "definitional_upper":
            phi = 1.0
            phi_step.update(value_used=phi, bound_type="upper bound on phi (net = incident - reflected <= incident)",
                            evidence_class="model-derived",
                            source="definition of net power; reflected power not reported (lane 08 ECR-D023 "
                                   "value_qualifier upper_bound)",
                            status="definitional bound; reflected power TBD")
            decl_type = "upper bound on the coupling-input cost (reflected power not subtracted)"
        else:
            phi = 1.0
            phi_step.update(value_used=phi, bound_type="none: the reported plane is not stated (a generator/forward "
                                                        "plane gives phi <= 1, an absorbed plane phi >= 1)",
                            evidence_class="assumed", source="declared basis of this overlay",
                            status="TBD - requires the source's power measurement plane (forward, reflected, absorbed "
                                   "at the flange)", sensitivity=phi_sens)
            decl_type = "as reported (power plane not stated; phi = 1 assumed)"
        c_decl = [c_rep[0] * phi, c_rep[1] * phi]
        c_above = c_decl[0] if spec["phi_kind"] == "assumed" else floor
        k_status = ("TBD - requires the source-exit ion current of a gridless pre-ionizer at the same coupled power; a "
                    "grid-extracted beam excludes grid interception (can lower the cost per exit ampere) and the "
                    "pre-ionizer runs at the common feed flow (direction unknown)") if spec["gridded"] else \
                   ("TBD - plume ion current of a gridless thruster (closest basis to a source exit), but probe-"
                    "reconstructed at 30 cm and at the source's own flow, not at the common feed state")
        chain_steps = [
            {"step": "reported", "value": e["value"], "unit": "W/A (= eV per singly charged ion, ECR-D025)",
             "evidence_class": e["evidence_class"], "source": f"lane 08 {eid}", "status": "as published"},
            phi_step,
            {"step": "ion basis -> ion current leaving an ABEP pre-ionizer exit (k = I_reported / I_exit)",
             "value_used": 1.0, "evidence_class": "assumed", "source": "declared basis of this overlay",
             "status": k_status},
            {"step": "bus referral: divide by the bus -> coupling-input chain efficiency eta_chain",
             "bounds": {"definitional_upper": 1.0, "reference_stated_chain": chain_ref},
             "evidence_class": "model-derived bound / inferred reference",
             "source": chain["reference_chain"]["source"], "status": "TBD - no sourced lower bound (ABEP chain TBD)",
             "breakeven_function": "bus_referred_source_cost(value, 'W_per_A', 'forward', {'generator': eta_chain}, 1)"},
            {"step": "transport: divide by eta_t (source exit -> Hall beam, same charge-current basis)",
             "range": [eta_t_lo, eta_t_hi], "evidence_class": "assumed (PROPOSED range)",
             "source": "lane 18 interstage_v1 basis (interstage_eta_t_basis)",
             "status": "TBD for every ECR exit state"},
            {"step": "result", "formula": "C_del,bus = C_reported * phi * k / (eta_chain * eta_t)",
             "evidence_class": "model-derived", "source": "this script (conditional on every factor above)"}]
        bus_ref = [c_decl[0] / chain_ref, c_decl[1] / chain_ref]
        for cv in c_decl:      # breakeven_v1 conversion cross-check
            bref = bk.bus_referred_source_cost(cv, "W_per_A", "forward", {"generator": chain_ref}, 1.0)
            if abs(bref - cv / chain_ref) > 1e-9 * bref:
                raise OverlayCheckError("bus_referred_source_cost disagrees")
        cls = classify(c_above, c_decl[1], Y_max_by_case, Y_min_by_case, eta_t_lo, chain_ref)
        per_slice = {}
        for s in SLICE_NAMES:
            Ys = slices[s]["Y_W_per_A"]
            per_slice[s] = {
                "Y_W_per_A": Ys,
                "eta_t_min_chain_1": {c: [eta_t_needed(c_decl[0], Ys[c]), eta_t_needed(c_decl[1], Ys[c])] for c in CASES},
                "eta_t_min_reference_chain": {c: [eta_t_needed(bus_ref[0], Ys[c]), eta_t_needed(bus_ref[1], Ys[c])]
                                              for c in CASES}}
        t_above = c_above / Y_max_any
        t_decl = c_decl[0] / Y_max_any
        to_def = [
            {"measurement": "interstage transport efficiency eta_t of the ECR exit state (same charge-current basis)",
             "moves_to": "CLEARLY_ABOVE_BREAKEVEN", "if_below": t_above,
             "condition": "eta_t below the threshold, with any chain <= 1",
             "threshold_inside_lane18_range": eta_t_lo < t_above <= eta_t_hi,
             "if_below_once_declared_value_confirmed": None if spec["phi_kind"] == "assumed" else t_decl,
             "note_confirmed": None if spec["phi_kind"] == "assumed" else
             "threshold that applies once the phi upper bound is shown to be tight (see missing_quantities)",
             "moves_to_below": {c: {"eta_t_at_least": c_decl[1] / (chain_ref * Y_min_by_case[c]),
                                    "reachable": c_decl[1] / (chain_ref * Y_min_by_case[c]) <= 1.0} for c in CASES},
             "note_below": "CLEARLY_BELOW from eta_t alone assumes the stated reference chain; reachable = False means "
                           "no eta_t <= 1 suffices at the least favourable Hall reference"},
            {"measurement": "bus -> coupling-input efficiency eta_chain of the candidate microwave chain",
             "moves_to": "CLEARLY_ABOVE_BREAKEVEN", "if_below": t_above,
             "condition": "eta_chain below the threshold, with any eta_t <= 1",
             "threshold_inside_unit_interval": 0.0 < t_above <= 1.0},
            {"measurement": "combined eta_chain * eta_t (one bus-to-Hall-channel ion-current test at the declared phi "
                            "and k)",
             "moves_to": "CLEARLY_ABOVE_BREAKEVEN if the product is below if_below; CLEARLY_BELOW_BREAKEVEN for case c "
                         "if it is at least product_at_least[c]",
             "if_below": t_above,
             "product_at_least": {c: {"value": c_decl[1] / Y_min_by_case[c],
                                      "reachable": c_decl[1] / Y_min_by_case[c] <= 1.0} for c in CASES},
             "note": "reachable = False: even a lossless chain with eta_t = 1 does not pay at the least favourable Hall "
                     "reference; the Hall reference (milestone B) must then narrow the box"},
            {"measurement": "end-to-end bus cost per delivered ampere C_del,bus = P_bus[ecr_source] / I_delivered into "
                            "the Hall channel, on the entry's gas at the common feed state (subsumes phi, k, eta_chain "
                            "and eta_t)",
             "moves_to": "CLEARLY_ABOVE_BREAKEVEN if C_del,bus > Y_max_any_case; CLEARLY_BELOW_BREAKEVEN for case c if "
                         "C_del,bus <= Y_min[c]; otherwise the Hall reference point (milestone B) decides",
             "thresholds_W_per_A": {"Y_max_any_case": Y_max_any, "Y_min_by_case": dict(Y_min_by_case)}},
            {"measurement": "Hall reference point (admitted transport closure, milestone B) and the response case "
                            "(alpha, chi, eta_v_S)",
             "moves_to": "collapses the PROPOSED box to one Y per case; with C_del,bus measured the placement is then "
                         "definite at that point",
             "status": "not a single measurement: requires the credible closure set (currently empty, gate 3)"},
        ]
        missing = [s["status"] for s in chain_steps if isinstance(s.get("status"), str) and s["status"].startswith("TBD")]
        if spec["phi_kind"] == "definitional_upper":
            missing.append("reflected power at the operating point (turns the incident-power upper bound into a "
                           "net-power value)")
        elif spec["phi_kind"] == "sourced_upper":
            missing.append("actual chain loss between the directional coupler and the thruster (only '>= 2 dB' is "
                           "reported; turns the upper bound on phi into a value)")
        consistency = None
        if spec.get("consistency_ref"):
            ref = midx[spec["consistency_ref"]]
            P = float(e["conditions"]["power_W"])
            I_implied = P / c_rep[0]
            I_max = float(ref["value"])
            consistency = {
                "check": f"implied beam current P/C = {P:g} W / reported cost vs the maximum extracted current of the same "
                         f"source ({ref['id']})",
                "implied_current_A": I_implied, "reported_maximum_current_A": I_max,
                "consistent": I_implied <= I_max,
                "evidence_class": "model-derived (arithmetic on lane-08 values)",
                "reading": "if the 'ion energy loss' were P_input / I_beam at the recorded 8 W, the implied current would "
                           "exceed the reported maximum; the source's definition of 'ion energy loss' or the input power "
                           "at each point is therefore not established from the abstract"}
            if not consistency["consistent"]:
                missing.append("the source's definition of 'ion energy loss' and the input power at the reported point "
                               f"(consistency check with {ref['id']} fails; full text not accessed)")
        placements.append({
            "id": eid, "matrix_ids_used": [eid] + ([spec["current_ref"]] if spec.get("current_ref") else [])
                                          + ([spec["phi_ref"]] if spec.get("phi_ref") else [])
                                          + ([spec["consistency_ref"]] if spec.get("consistency_ref") else []),
            "device": spec["device"], "mode": spec["mode"],
            "applies_to": {"xe": "Xe mode only (RFP propellant); says nothing about the air arm",
                           "air_N2": "air arm, N2 component only (no O / O2 content)"}[spec["mode"]],
            "reported": _reported_block(e),
            "power_reference": {"class": spec["power_reference_class"], "as_stated": spec["power_plane_as_stated"],
                                "bus_basis": False},
            "ion_basis": spec["ion_basis_as_stated"],
            "conversion_chain": chain_steps,
            "declared_basis": {"cost_W_per_A": c_decl, "type": decl_type, "phi_kind": spec["phi_kind"],
                               "definition": "phi as stated above, k = 1 (assumed): the declared cost is the net "
                                             "microwave power the ABEP ecr_source must deliver at its coupling input per "
                                             "ampere of source-exit ions"},
            "ionization_floor_W_per_A": floor,
            "bus_cost_W_per_A": {"lower_bound_chain_1": c_decl[0], "at_reference_chain": bus_ref, "upper_bound": None,
                                 "upper_bound_note": "unbounded: no sourced lower bound on the bus chain efficiency"},
            "eta_t": {"range": [eta_t_lo, eta_t_hi], "basis": "see interstage_eta_t_basis (lane 18)"},
            "placement_test_costs_W_per_A": {"c_above": c_above, "c_below": c_decl[1],
                                             "c_above_basis": ("declared basis (phi = 1 assumed, k = 1)"
                                                               if spec["phi_kind"] == "assumed" else
                                                               "ionization floor: the declared value is only an upper "
                                                               "bound on the coupling-input cost")},
            "placement": cls["placement"], "placement_by_case": cls["by_case"], "below_cases": cls["below_cases"],
            "placement_by_slice": per_slice,
            "payable_X_at_mid_reference_chain_1_eta_t_1": _payable_x_at_mid(c_decl[0], mid),
            "straddles_on": straddle_dimensions(c_decl[0], Y_max_by_case, Y_min_by_case, slice_Ys, eta_t_lo,
                                                spec["phi_kind"]) if cls["placement"] == "STRADDLES" else [],
            "to_definite_placement": to_def,
            "consistency_check": consistency,
            "missing_quantities": missing + ["ABEP bus -> coupling-input chain efficiency (TBD)"],
        })

    # cross-check with breakeven.place_evidence at the three slices (species of the entry's gas)
    def _mix(label, m):
        return bk.IonMix((bk.IonSpecies(label, m, 1, 1.0),))
    masses = {s: float(v["mass_amu"]) for s, v in inp["species"]["values"].items()}
    xcheck = []
    for pl in placements:
        sp = "N2" if pl["mode"] == "air_N2" else "Xe"
        mix = _mix(sp + "+", masses[sp])
        for s in SLICE_NAMES:
            sl = slices[s]
            ref = bk.HallReference(mdot_kg_s=1.0e-6, V_d_V=sl["V_d_V"], eta_u=MID_ETA_U0, eta_b=sl["eta_b"],
                                   eta_v=sl["eta_v"], gamma_div=float(inp["gamma_div"]["value"]),
                                   eta_ppu_discharge=sl["eta_ppu_d"], mix=mix)
            for c in CASES:
                cc = cases_src[c]
                evs = sl["eta_v"] if cc["eta_v_delivered"] == "= eta_v" else float(cc["eta_v_delivered"])
                resp = bk.PreionResponse(alpha=float(cc["alpha"]), chi=float(cc["chi"]), eta_v_delivered=evs,
                                         mix_delivered=mix)
                C = pl["declared_basis"]["cost_W_per_A"][0]
                res = bk.place_evidence(ref, resp, 0.0,
                                        bk.Evidenced(C, "W/A", pl["reported"]["evidence_class"], pl["id"]),
                                        bk.Evidenced(1.0, "1", "assumed", "eta_t = 1 (upper end of the range)"), 64)
                mine = eta_t_needed(C, sl["Y_W_per_A"][c])
                dev = abs(res["eta_transport_min"] - mine) / mine
                xcheck.append(dev)
                if dev > 1e-9:
                    raise OverlayCheckError(f"place_evidence eta_t_min mismatch {pl['id']} {s} {c}: "
                                            f"{res['eta_transport_min']} vs {mine}")
                if (res["status"] != "CANNOT_BREAK_EVEN_IN_MODEL_FAMILY") != (C <= sl["Y_W_per_A"][c]):
                    raise OverlayCheckError(f"place_evidence status mismatch {pl['id']} {s} {c}")

    not_placeable = []
    for eid, spec in NOT_PLACEABLE.items():
        e = midx[eid]
        row = {"id": eid, "mode": spec["mode"], "reported": _reported_block(e), "placement": "NOT_PLACEABLE",
               "missing_quantities": spec["missing"], "note": spec["note"],
               "to_definite_placement": [{"measurement": m, "moves_to": "placeable (then evaluated as the placed "
                                                                          "entries)"} for m in spec["missing"]]}
        if eid == "ECR-E072":
            row["derived_lower_bound_W_per_A"] = 30.0 / float(e["value"])
            row["derived_lower_bound_basis"] = ("30 W / 0.150 A: P/I exceeds this for every P > 30 W at saturation "
                                                "(model-derived here; not a placement)")
        if eid == "ECR-E084":
            e081 = midx["ECR-E081"]
            P = float(e["conditions"]["power_W"])
            row["consistency_check"] = {
                "P_over_I_at_recorded_power_W_per_A": P / float(e["value"]),
                "implied_current_of_ECR-E081_A": float(e081["conditions"]["power_W"]) / float(e081["value"]),
                "reading": "a P/I from the recorded 8 W and this current would not be consistent with ECR-E081: 8 W / "
                           "596.2 W/A implies a current above this maximum; no cost is placed for this point",
                "evidence_class": "model-derived (arithmetic on lane-08 values)"}
        not_placeable.append(row)
    for gid, spec in GAP_ROWS.items():
        not_placeable.append({"id": gid, "mode": spec["mode"], "reported": None, "quantity": spec["quantity"],
                              "placement": "NOT_PLACEABLE", "missing_quantities": spec["missing"],
                              "note": "gap row: the RFP air feed contains N2, O2 and atomic O; no ECR ion-cost evidence "
                                      "covers O or O2",
                              "to_definite_placement": [{"measurement": "species-resolved ECR ion production cost on "
                                                                         "O2 and on an N2/O/O2 mixture at ICD chamber "
                                                                         "conditions, bus-referenced",
                                                         "moves_to": "placeable"}]})
    x_side = []
    for eid in X_SIDE_CONTEXT:
        e = midx[eid]
        x_side.append({"id": eid, "reported": _reported_block(e), "placement": "NOT_PLACEABLE",
                       "against": "X (relative utilization gain / delivered share)",
                       "conversion": "X = eta_t * u_src / eta_u0 at equal mix when the whole common feed flow passes the "
                                     "source (u_src = source ion mass utilization at the common feed state)",
                       "missing_quantities": ["source ion utilization at the common feed flow and at the allocated "
                                              "ecr_source power (the value is at the source's own flow and power)",
                                              "eta_t", "eta_u0 of the admitted Hall reference"]})

    # triage of every matrix entry
    placed_ids = set(PLACEABLE) | set(NOT_PLACEABLE) | set(X_SIDE_CONTEXT)
    groups = [sorted(placed_ids), list(CHAIN_EVIDENCE), list(FIXED_OVERHEAD_EVIDENCE), list(COVERED_BY),
              list(ELECTRON_CURRENT)]
    seen = [i for g in groups for i in g]
    if len(seen) != len(set(seen)):
        raise OverlayCheckError("an entry is listed in two triage groups")
    other = [e["id"] for e in matrix["entries"] if e["id"] not in set(seen)]
    all_ids = [e["id"] for e in matrix["entries"]]
    if sorted(seen + other) != sorted(all_ids):
        raise OverlayCheckError("triage does not cover every matrix entry exactly once (or names an unknown id)")
    triage = {"placed_or_not_placeable": sorted(placed_ids), "chain_evidence": list(CHAIN_EVIDENCE),
              "fixed_overhead_evidence": list(FIXED_OVERHEAD_EVIDENCE), "covered_by": COVERED_BY,
              "electron_current_not_an_ion_cost": list(ELECTRON_CURRENT), "other": other,
              "other_reason": "not an ion production cost, ion utilization, bus-chain or fixed-overhead quantity "
                              "(resonance field / cutoff, densities, magnet materials, heritage, thrust and efficiency "
                              "figures, materials, thermal, regime statements)",
              "n_entries": len(all_ids)}

    # ---------------- (3) region of (eta_t, C_src,bus) where ecr_hall could pay
    region = {"axes": {"eta_t": et_vals, "unit_C": "bus W per A of source-exit ions (C_src,bus)"},
              "definition": "ecr_hall could pay in bus power only where C_src,bus <= eta_t * Y (Y: payable bus W per "
                            "delivered A); with a fixed overhead omega_f > 0 Y is lowered (Y_sup_over_Pi_H)",
              "by_case": {}}
    for c in CASES:
        region["by_case"][c] = {
            "could_pay_somewhere_in_box": {"C_src_bus_max_W_per_A": [t * Y_max_by_case[c] for t in et_vals],
                                           "rule": "C_src,bus <= eta_t * Y_max[case] (most favourable Hall reference, "
                                                   "omega_f = 0)"},
            "pays_everywhere_in_box": {"C_src_bus_max_W_per_A": [t * Y_min_by_case[c] for t in et_vals],
                                       "rule": "C_src,bus <= eta_t * Y_min[case] (least favourable Hall reference, "
                                               "omega_f = 0)"},
            "at_mid_reference": {"C_src_bus_max_W_per_A": [t * mid["Y_W_per_A"][c] for t in et_vals]},
            "eta_t_floor_any_source": {k: v["value_W_per_A"] / Y_max_by_case[c] for k, v in floors["values"].items()},
            "eta_t_floor_note": "no source of that feed can pay below this eta_t anywhere in the box (ionization floor / "
                                "Y_max), whatever its chain",
        }
    floor_min = min(v["value_W_per_A"] for v in floors["values"].values())
    region["structural"] = {
        "below_everywhere_needs_eta_t_at_least_with_reference_chain": {
            c: {k: v["value_W_per_A"] / (chain_ref * Y_min_by_case[c]) for k, v in floors["values"].items()}
            for c in CASES},
        "reading": "even a source at the ionization floor needs eta_t at least this large to pay everywhere in the box "
                   "with the stated reference chain; any value above the lane-18 lower end means that no source can be "
                   "CLEARLY_BELOW over the whole PROPOSED eta_t range: the placement then needs a measured eta_t",
        "clearly_below_reachable_over_full_eta_t_range": {
            c: floor_min / (chain_ref * eta_t_lo) <= Y_min_by_case[c] for c in CASES},
        "clearly_below_reachable_basis": "lowest ionization floor of any feed / (reference chain * eta_t,lo) <= Y_min",
    }
    ev_in = []
    for pl in placements:
        lo = pl["declared_basis"]["cost_W_per_A"][0]
        ref = pl["bus_cost_W_per_A"]["at_reference_chain"][0]
        row = {"id": pl["id"], "mode": pl["mode"], "by_case": {}}
        for c in CASES:
            row["by_case"][c] = {
                "could_pay_chain_1": lo <= Y_max_by_case[c] * eta_t_hi,
                "eta_t_window_chain_1": [lo / Y_max_by_case[c], eta_t_hi] if lo <= Y_max_by_case[c] * eta_t_hi else None,
                "could_pay_reference_chain": ref <= Y_max_by_case[c] * eta_t_hi,
                "eta_t_window_reference_chain": ([ref / Y_max_by_case[c], eta_t_hi]
                                                 if ref <= Y_max_by_case[c] * eta_t_hi else None),
                "pays_everywhere_chain_1_eta_t_1": lo <= Y_min_by_case[c],
                "pays_at_mid_reference_chain_1_eta_t_1": lo <= mid["Y_W_per_A"][c]}
        ev_in.append(row)
    region["evidence_in_region"] = ev_in

    def _all(mode, key, c):
        rows = [r for r in ev_in if r["mode"] == mode]
        return bool(rows) and all(r["by_case"][c][key] for r in rows)

    def _any(key, mode=None):
        return any(r["by_case"][c][key] for r in ev_in if mode is None or r["mode"] == mode for c in CASES)
    region["answer"] = {
        "any_evidence_in_could_pay_region_chain_1": _any("could_pay_chain_1"),
        "any_evidence_in_could_pay_region_reference_chain": _any("could_pay_reference_chain"),
        "all_N2_entries_in_could_pay_region_chain_1_every_case": all(_all("air_N2", "could_pay_chain_1", c)
                                                                    for c in CASES),
        "any_N2_entry_pays_everywhere_chain_1_eta_t_1": _any("pays_everywhere_chain_1_eta_t_1", "air_N2"),
        "any_evidence_pays_everywhere_chain_1_eta_t_1": _any("pays_everywhere_chain_1_eta_t_1"),
        "entries_paying_everywhere_chain_1_eta_t_1": sorted({r["id"] for r in ev_in for c in CASES
                                                             if r["by_case"][c]["pays_everywhere_chain_1_eta_t_1"]}),
        "O_O2_mixture": "no ECR evidence exists (GAP-ECR-O-O2-AIR): the air arm cannot be placed for its O / O2 content",
        "condition": "every 'true' is on the declared basis (phi as declared, k = 1) and holds only inside the stated "
                     "eta_t window; with the reference chain the windows narrow as listed",
    }

    # ---------------- self-checks
    checks = {}
    stored = surfaces["universal"]["sup_C_del_star_over_Pi_H_with_fixed_overhead"]
    wf_st = [float(v) for v in surfaces["universal"]["omega_fixed"]]
    mx, n = 0.0, 0
    for k, vals in stored.items():
        parts = dict(t.split("=") for t in k.split("|")[1:])
        r, p = case_rp(k.split("|")[0], float(parts["eta_b"]), float(parts["eta_v"]))
        eu = float(parts["eta_u0"])
        for wf, v in zip(wf_st, vals):
            mine = y_sup(r, p, wf, (1.0 - eu) / eu)[0]
            mx = max(mx, abs(mine - v) / max(abs(v), 1.0))
            n += 1
    checks["y_sup_vs_breakeven_surfaces"] = {"n": n, "max_dev": mx, "tolerance": 1e-5,
                                             "metric": "|mine - stored| / max(|stored|, 1); stored values are rounded "
                                                       "to 6 significant digits", "pass": mx <= 1e-5}
    mx, n = 0.0, 0
    for c in CASES:
        for eb in eb_vals:
            for eu in eu_vals:
                for wf in wf_vals:
                    mix = _mix("N2+", masses["N2"])
                    ref = bk.HallReference(mdot_kg_s=1.0e-6, V_d_V=300.0, eta_u=eu, eta_b=eb, eta_v=ev_mid,
                                           gamma_div=float(inp["gamma_div"]["value"]), eta_ppu_discharge=ppu_mid,
                                           mix=mix)
                    cc = cases_src[c]
                    evs = ev_mid if cc["eta_v_delivered"] == "= eta_v" else float(cc["eta_v_delivered"])
                    resp = bk.PreionResponse(alpha=float(cc["alpha"]), chi=float(cc["chi"]), eta_v_delivered=evs,
                                             mix_delivered=mix)
                    P0 = bk.hall_only_state(ref)["P_d_bus_W"]
                    s = bk.supremum_breakeven_delivered_cost(ref, resp, wf * P0, 64)["sup_W_per_A"]
                    r, p = case_rp(c, eb, ev_mid)
                    PiH = pi_h(300.0, eb, ppu_mid)
                    mx = max(mx, abs(s - y_sup(r, p, wf, (1.0 - eu) / eu)[0] * PiH) / PiH)
                    n += 1
    checks["y_sup_vs_breakeven_module"] = {"n": n, "max_abs_dev_over_Pi_H": mx, "tolerance": 1e-6, "pass": mx <= 1e-6}
    mx, n = 0.0, 0
    for c in CASES:
        for eb in eb_vals:
            for w in OMEGA_GRID:
                mix = _mix("N2+", masses["N2"])
                ref = bk.HallReference(mdot_kg_s=1.0e-6, V_d_V=300.0, eta_u=0.3, eta_b=eb, eta_v=ev_mid,
                                       gamma_div=float(inp["gamma_div"]["value"]), eta_ppu_discharge=ppu_mid, mix=mix)
                cc = cases_src[c]
                evs = ev_mid if cc["eta_v_delivered"] == "= eta_v" else float(cc["eta_v_delivered"])
                resp = bk.PreionResponse(alpha=float(cc["alpha"]), chi=float(cc["chi"]), eta_v_delivered=evs,
                                         mix_delivered=mix)
                P0 = bk.hall_only_state(ref)["P_d_bus_W"]
                ov = bk.BusOverhead(arch=ARCH, source_bus_W={"ecr_source": w * P0, "ecr_magnet": 0.0},
                                    delta_common_bus_W={k: 0.0 for k in bk.COMMON_NON_DISCHARGE},
                                    interstage_loss_bus_W=0.0, extra_ppu_bus_W=0.0)
                res = bk.required_utilization_gain(ref, resp, ov)
                if res.get("delta_s_star") is None:
                    raise OverlayCheckError(f"required_utilization_gain returned no root for {c} {eb} {w}")
                mx = max(mx, abs(res["delta_s_star"] / 0.3 - x_star(w, *case_rp(c, eb, ev_mid))))
                n += 1
    checks["x_star_vs_required_utilization_gain"] = {"n": n, "max_abs_dev": mx, "tolerance": 1e-9, "pass": mx <= 1e-9}
    checks["eta_t_min_vs_place_evidence"] = {"n": len(xcheck), "max_rel_dev": max(xcheck), "tolerance": 1e-9,
                                             "pass": max(xcheck) <= 1e-9}
    mx = 0.0
    for k in combos:
        r, p = _rp(*k)
        for wf in wf_vals:
            for y in Y_OVER_PI_GRID:
                iv = share_interval(y, wf, r, p)
                if iv is not None:
                    mx = max([mx] + [abs(y_payable(xe, r, p, wf) - y) for xe in iv if xe > 0.0])
            if wf > 0:
                xs = [10.0 ** (-6 + 9 * i / 3000) for i in range(3001)]
                vals = [y_payable(x, r, p, wf) for x in xs]
                d = [b - a for a, b in zip(vals, vals[1:])]
                if sum(1 for a, b in zip(d, d[1:]) if (a > 0) != (b > 0)) > 1:
                    raise OverlayCheckError(f"payable Y not unimodal for {k} {wf}")
    checks["share_interval_endpoints_and_unimodality"] = {"max_abs_dev": mx, "tolerance": 1e-9, "pass": mx <= 1e-9}
    ref = bk.HallReference(mdot_kg_s=1.0e-6, V_d_V=300.0, eta_u=MID_ETA_U0, eta_b=0.7, eta_v=ev_mid, gamma_div=0.9,
                           eta_ppu_discharge=ppu_mid, mix=_mix("N2+", masses["N2"]))
    resp = bk.PreionResponse(alpha=1.0, chi=0.0, eta_v_delivered=ev_mid, mix_delivered=ref.mix)
    ads = bk.achievable_delivered_share(ref, resp, 10.0, 300.0, 0.5)
    checks["achievable_delivered_share_cost_identity"] = {
        "delivered_cost_W_per_A": ads["delivered_cost_W_per_A"], "expected": 600.0,
        "pass": abs(ads["delivered_cost_W_per_A"] - 600.0) < 1e-9,
        "note": "analysis numbers only (10 W, 300 W/A, eta_t 0.5): checks C_del = C_src / eta_t in breakeven_v1"}
    ys = []
    for md in (1.0e-7, 5.0e-6):
        refm = bk.HallReference(mdot_kg_s=md, V_d_V=300.0, eta_u=MID_ETA_U0, eta_b=0.7, eta_v=ev_mid, gamma_div=0.9,
                                eta_ppu_discharge=ppu_mid, mix=_mix("N2+", masses["N2"]))
        ys.append(bk.marginal_breakeven_delivered_cost(refm, resp))
    checks["mdot_invariance_omega_f_0"] = {"values": ys, "pass": abs(ys[0] - ys[1]) <= 1e-9 * abs(ys[0])}
    arm = {"boundary_version": BOUNDARY_VERSION, "architecture": ARCH,
           "items": [{"component": k, "P_bus_W": v} for k, v in
                     [("hall_discharge", 400.0), ("hall_magnet", 10.0), ("cathode_keeper", 5.0),
                      ("cathode_heater", 0.0), ("flow_control", 2.0), ("compressor", 20.0),
                      ("thermal_control", 6.0), ("housekeeping", 4.0), ("ecr_source", 50.0), ("ecr_magnet", 8.0)]]}
    ho = {"boundary_version": BOUNDARY_VERSION, "architecture": REFERENCE_ARCH,
          "items": [{"component": k, "P_bus_W": v} for k, v in
                    [("hall_discharge", 450.0), ("hall_magnet", 10.0), ("cathode_keeper", 5.0),
                     ("cathode_heater", 0.0), ("flow_control", 2.0), ("compressor", 20.0),
                     ("thermal_control", 5.0), ("housekeeping", 3.0)]]}
    ovl = bk.overhead_from_boundary_ledgers(arm, ho)
    checks["overhead_from_boundary_ledgers_split"] = {
        "generator_W": ovl.generator_W, "fixed_W": ovl.fixed_W, "expected": [50.0, 10.0],
        "pass": abs(ovl.generator_W - 50.0) < 1e-12 and abs(ovl.fixed_W - 10.0) < 1e-12 and ovl.boundary_v1_conformant,
        "note": "synthetic ledgers (analysis numbers only): generator = ecr_source; fixed = ecr_magnet (8 W) + common "
                "deltas (thermal_control +1 W, housekeeping +1 W); hall_discharge is excluded from the overhead"}
    checks["all_pass"] = all(v["pass"] for v in checks.values() if isinstance(v, dict) and "pass" in v)
    if not checks["all_pass"]:
        raise OverlayCheckError(f"self-checks failed: {checks}")

    # ---------------- assemble
    counts = {k: sum(1 for p_ in placements + not_placeable if p_["placement"] == k) for k in PLACEMENTS}
    out = {
        "id": OVERLAY_VERSION, "follow_on": FOLLOW_ON, "trigger": TRIGGER,
        "status": "CONDITIONAL INEQUALITIES over PROPOSED analysis ranges. Not predictions, not a ranking, no "
                  "architecture selection, no hard-gate decision; no comparison with the other pre-ionizer arm. No "
                  "Hall closure, screening candidate or absolute Hall number is used.",
        "architecture": ARCH, "reference_architecture": REFERENCE_ARCH,
        "boundary": {
            "version": BOUNDARY_VERSION,
            "P_bus": "all DC-bus power drawn by the propulsion string at the bus input terminals; never absorbed RF "
                     "power, source-only power or discharge-only power",
            "ecr_hall_source_components": list(bk.SOURCE_COMPONENTS[ARCH]),
            "common_components": list(bk.COMMON_COMPONENTS),
            "Pi_H": "V_d/(eta_b eta_ppu,d) = P_bus,hall_only[hall_discharge] / I_b0 (bus W per Hall beam ampere)",
            "omega": "O / P_bus,hall_only[hall_discharge], O = P_bus[ecr_source] + P_bus[ecr_magnet] + common deltas",
            "omega_f": "fixed (non-ion-scaling) part of O over the same denominator",
            "from_ledgers": "breakeven.overhead_from_boundary_ledgers(arm_ledger, hall_only_ledger): generator_W = "
                            "ecr_source, fixed_W = ecr_magnet + common deltas (self_checks.overhead_from_boundary_"
                            "ledgers_split)",
        },
        "milestones": {
            "supports": ["A"],
            "A": "conditional selection: states the necessary bus-power conditions (X, Y, Z) ecr_hall must "
                 "demonstrate, places every ECR evidence entry against them, and names the single measurements that "
                 "would make each placement definite",
            "to_reach_B": "admitted Hall transport closure(s) for the Vyovrinda geometry (credible set currently "
                          "empty, gate 3) giving Pi_H, eta_b, eta_v, eta_u0 per member (collapses the Hall box to "
                          "points); measured alpha, chi, eta_v_S (collapses the case); measured end-to-end C_del,bus "
                          "(or eta_chain, phi, k and eta_t separately) on N2/O2/O at the common feed state",
            "to_reach_C": "mass and life break-even inputs (breakeven_v1 Secs. 7-8, all TBD), thermal closure, "
                          "startup/cathode, integrated mission closure on the same boundary",
        },
        "inputs": [{"key": k, **{kk: v[kk] for kk in ("path", "lane", "commit", "sha256", "role")}}
                   for k, v in INPUTS.items()],
        "doc_references": DOC_REFERENCES,
        "assumptions_inherited": "breakeven_v1 A1-A8 (BREAKEVEN_DERIVATION.md Sec. 3), all assumed; equal delivered "
                                 "and Hall-born mix (single species, singly charged); alpha = 1 in all three cases",
        "cases": {c: {**cases_src[c], "r_R_T": ("1" if c != "optimistic_bound" else "1/sqrt(eta_v)"),
                      "p_R_P": ("1" if c == "add_only" else "eta_b"),
                      "marginal_Y_over_Pi_H": {"add_only": "1", "cost_offset": "2 - eta_b",
                                               "optimistic_bound": "2/sqrt(eta_v) - eta_b"}[c]} for c in CASES},
        "analysis_ranges": {
            "status": "PROPOSED (assumed; not predictions, not design values), taken from breakeven_v1 except "
                      "eta_ppu,d; the X, omega, Y/Pi_H and C_src,bus grids are this overlay's table grids",
            "V_d_V": V_vals, "eta_b": eb_vals, "eta_u0": eu_vals, "eta_v_optimistic": ev_opt,
            "eta_v_mid": ev_mid, "omega_f": wf_vals, "eta_t": et_vals,
            "eta_ppu_d": {"values": ppu_vals, "evidence": ppu,
                          "note": "envelope of the lane-20 digitized discharge-supply efficiencies (replaces the single "
                                  "assumed 0.9 of breakeven_v1 as the box axis; 0.9 lies inside). The evidence covers "
                                  "200-500 V outputs, so V_d = 150 V is an extrapolation of the supply data; the "
                                  "operating-point value is TBD until the admitted discharge load exists"},
            "X_grid": list(X_GRID), "omega_grid": list(OMEGA_GRID), "Y_over_Pi_H_grid": list(Y_OVER_PI_GRID),
            "C_src_bus_grid_W_per_A": list(C_SRC_BUS_GRID), "eta_u0_for_omega_f_Z_table": MID_ETA_U0,
        },
        "breakeven_condition": {
            "statement": "ecr_hall breaks even with hall_only in bus power on bus_power_boundary_v1 (a necessary "
                         "condition, not a sufficient one: mass and life break-even are separate) ONLY IF it delivers "
                         "a relative utilization gain of at least X = delta_eta_u/eta_u0 (= I_delivered/I_b0 at "
                         "alpha = 1; X >= X_lo(Y, omega_f), X >= X*(omega) for a given total overhead, and "
                         "X <= (1-eta_u0)/eta_u0) at no more than Y = Pi_H * (g_case(X) - omega_f/X) bus W per "
                         "delivered A, which a source of bus cost C_src,bus per source-exit A meets only with an "
                         "interstage transport efficiency of at least Z = C_src,bus / Y.",
            "g_case": "g(X) = (2r - p + r^2 X)/(1 + r X)^2 with (r, p) per case; R = (1 + rX)^2/(1 + pX)",
            "equivalent_overhead_form": "X >= X*(omega) = root of (1-omega)(1 + rX)^2 = 1 + pX, omega = total "
                                        "overhead fraction; add_only: X* = omega/(1-omega)",
            "coupling_of_X_and_Y": "the generator share of the overhead is omega_gen = (Y_actual/Pi_H) * X, so X and Y "
                                   "are one inequality g(X) - omega_f/X >= Y_actual/Pi_H; at omega_f = 0 every X up to "
                                   "X_hi pays (X_lo = 0), at omega_f > 0 a minimum share X_lo > 0 is needed",
            "Y_supremum": "Y_sup = Pi_H * sup_X (g - omega_f/X); omega_f = 0: Pi_H (2r - p), attained only as X -> 0",
            "Z": "Z = C_src,bus / Y (C_src,bus: bus W per A of source-exit ions); Z > 1 means no eta_t pays",
            "absolute_gain": "delta_eta_u* = eta_u0 * X* (add_only: eta_u0 omega/(1-omega), breakeven_v1 Sec. 5)",
            "tables": {
                "Y_over_Pi_H_vs_X": {"index": "case[|eta_b][|eta_v] -> omega_f -> list over X_grid",
                                     "values": y_of_x,
                                     "note": "values <= 0 mean no positive source cost pays at that X"},
                "payable_X_interval": {"index": "case[|eta_b][|eta_v] -> omega_f -> list over Y_over_Pi_H_grid of "
                                                "[X_lo, X_hi] or null",
                                       "values": x_interval,
                                       "note": "shares X at which a delivered cost Y = y * Pi_H pays; not capped (compare "
                                               "with X_cap_by_eta_u0); null: no X pays"},
                "Y_sup_over_Pi_H": {"index": "case[|eta_b][|eta_v] -> eta_u0 (cap) -> omega_f", "values": y_sup_tab},
                "X_star_vs_omega": {"index": "case[|eta_b][|eta_v] -> list over omega_grid", "values": x_of_omega,
                                    "X_cap_by_eta_u0": x_caps,
                                    "note": "X* above the cap of an eta_u0 means no break-even at that eta_u0"},
                "Pi_H_W_per_A": {"index": "eta_ppu_d -> eta_b -> list over V_d", "values": pi_tab},
                "Y_sup_W_per_A_omega_f_0": {"index": "eta_ppu_d|eta_b|case[|eta_v] -> list over V_d",
                                            "values": Y_dim},
                "Z_vs_C_src_bus": {"index": "slice -> case -> list over C_src_bus_grid (omega_f = 0)",
                                   "values": z_tab, "note": "Z > 1: no eta_t pays"},
                "Z_vs_C_src_bus_mid_reference_by_omega_f": {
                    "index": "case -> omega_f -> list over C_src_bus_grid (mid_reference, eta_u0 = 0.6)",
                    "values": z_mid_wf, "note": "null: no positive cost pays at that omega_f"},
            },
            "hall_reference_slices": slices,
            "box_extremes_W_per_A": {"Y_max_by_case": Y_max_by_case, "Y_min_by_case": Y_min_by_case,
                                     "Y_max_any_case": Y_max_any},
        },
        "interstage_eta_t_basis": it_basis,
        "bus_chain_evidence": chain,
        "fixed_overhead": _fixed_overhead_evidence(ec, midx),
        "ionization_floor": floors,
        "placement_rules": {
            "status": "PROPOSED classification rules for the owner",
            "declared_basis": "phi as declared per entry (a sourced or definitional upper bound where one exists, else "
                              "1, assumed), k = 1 (assumed), omega_f = 0 (permanent-magnet ecr_magnet, zero common "
                              "deltas)",
            "CLEARLY_ABOVE_BREAKEVEN": "c_above > Y_max of every case at the most favourable Hall reference of the "
                                       "PROPOSED box, with eta_chain = 1 and eta_t = 1: cannot pay under any declared "
                                       "case at any eta_t in range. c_above is the declared cost when phi is assumed; "
                                       "when the declared value is only an upper bound, c_above is the ionization floor",
            "CLEARLY_BELOW_BREAKEVEN": "for at least one stated case c: declared upper cost / (reference chain * "
                                       "eta_t,lo) <= Y_min[c] at the least favourable Hall reference of the box: pays "
                                       "under that case everywhere in the box at every eta_t in range, with the stated "
                                       "reference chain",
            "STRADDLES": "numeric and neither of the above; straddles_on names the dimensions over which pay / no-pay "
                         "flips",
            "NOT_PLACEABLE": "no numeric ion production cost on an ion-current basis for an in-scope gas; the missing "
                             "quantity is named",
            "no_hard_gate": "no placement is a hard-gate decision; a CLEARLY_ABOVE placement would be a milestone-A "
                            "candidate for the owner's hard-gate review only, conditional on A1-A8 and the declared "
                            "basis",
        },
        "evidence_placements": placements,
        "not_placeable": not_placeable,
        "x_side_context": x_side,
        "triage": triage,
        "placement_counts": counts,
        "region": region,
        "self_checks": checks,
        "forbidden_patterns": list(FORBIDDEN_PATTERNS),
        "provenance": {"script": "docs/architecture_comparison/overlays/ecr/build_overlay_ecr.py",
                       "script_sha256": _sha(Path(__file__).read_bytes()),
                       "reproduce": "python docs/architecture_comparison/overlays/ecr/build_overlay_ecr.py --check"},
    }
    out["milestone_A_statement"] = _milestone_statement(out)
    text = json.dumps(r6(out), indent=1, ensure_ascii=False) + "\n"
    return text, _md_block(json.loads(text))


def _milestone_statement(d: dict) -> dict:
    pls = d["evidence_placements"]
    cnt = d["placement_counts"]
    bx = d["breakeven_condition"]["box_extremes_W_per_A"]
    n2 = [p["id"] for p in pls if p["mode"] == "air_N2"]
    xe = [p["id"] for p in pls if p["mode"] == "xe"]
    strad = sorted({dim for p in pls for dim in p["straddles_on"]})
    ans = d["region"]["answer"]
    st = d["region"]["structural"]["clearly_below_reachable_over_full_eta_t_range"]
    f = lambda v: f"{r6(v):g}"
    now = [
        f"placements: {cnt['CLEARLY_ABOVE_BREAKEVEN']} CLEARLY_ABOVE_BREAKEVEN, {cnt['CLEARLY_BELOW_BREAKEVEN']} "
        f"CLEARLY_BELOW_BREAKEVEN, {cnt['STRADDLES']} STRADDLES, {cnt['NOT_PLACEABLE']} NOT_PLACEABLE (declared basis, "
        "PROPOSED rules)",
        ("no published ECR ion cost rules out a bus-power break-even of ecr_hall everywhere in the PROPOSED Hall box: the "
         "ECR evidence yields no hard-gate candidate on the power criterion" if cnt["CLEARLY_ABOVE_BREAKEVEN"] == 0 else
         "some ECR ion costs are CLEARLY_ABOVE_BREAKEVEN on the declared basis: owner hard-gate review candidates only"),
        ("no published ECR evidence shows that ecr_hall pays in bus power over the whole PROPOSED box and eta_t range"
         if cnt["CLEARLY_BELOW_BREAKEVEN"] == 0 else
         "some ECR ion costs are CLEARLY_BELOW_BREAKEVEN under a stated case (declared basis, reference chain)"),
        "the numeric entries straddle on: " + "; ".join(strad),
        ("with the stated reference chain, CLEARLY_BELOW over the full lane-18 eta_t range is out of reach for any source "
         "(even at the ionization floor) in every case: a pay placement needs a measured eta_t"
         if not any(st.values()) else "CLEARLY_BELOW over the full eta_t range is reachable in principle for: "
         + ", ".join(c for c, v in st.items() if v)),
        f"air arm: {len(n2)} placeable entries ({', '.join(n2)}), all N2 and all abstract-only; no ECR ion-cost "
        "evidence on O2, atomic O or a mixture exists, so the air arm is NOT_PLACEABLE for its O / O2 content",
        f"Xe mode: {len(xe)} placeable entries ({', '.join(xe)}); they describe the Xe mode only",
        f"a delivered ion is worth at most Y = Pi_H (2r - p) bus W/A at omega_f = 0; over the PROPOSED box this spans "
        f"{f(bx['Y_min_by_case']['add_only'])}-{f(bx['Y_max_by_case']['add_only'])} W/A (add_only), "
        f"{f(bx['Y_min_by_case']['cost_offset'])}-{f(bx['Y_max_by_case']['cost_offset'])} W/A (cost_offset) and "
        f"{f(bx['Y_min_by_case']['optimistic_bound'])}-{f(bx['Y_max_by_case']['optimistic_bound'])} W/A "
        "(optimistic_bound)",
        ("on the declared basis with a lossless chain, every N2 entry lies in the could-pay region of every case inside "
         "its eta_t window (region.evidence_in_region)" if ans["all_N2_entries_in_could_pay_region_chain_1_every_case"]
         else "not every N2 entry lies in the could-pay region of every case (region.evidence_in_region)"),
        ("entries that would pay everywhere in the box only with a lossless chain and eta_t = 1: "
         + ", ".join(ans["entries_paying_everywhere_chain_1_eta_t_1"])
         if ans["entries_paying_everywhere_chain_1_eta_t_1"] else
         "no entry pays everywhere in the box even with a lossless chain and eta_t = 1"),
    ]
    return {
        "can_conclude_now": now,
        "condition_set_for_milestone_A": (
            "On the bus-power criterion (necessary, not sufficient), ecr_hall can be named baseline under milestone A "
            "only if all of the following are demonstrated: (A) an end-to-end bus cost per delivered ampere C_del,bus "
            "<= Pi_H (g_case(X) - omega_f/X) on an air-representative N2/O2/O feed at the common feed state; (B) an "
            "interstage transport efficiency eta_t >= Z = C_src,bus / Y on the same charge-current basis; (C) a "
            "relative utilization gain X with X_lo(Y, omega_f) <= X <= min(X_hi, (1 - eta_u0)/eta_u0); (D) mass and "
            "life break-even (breakeven_v1 Secs. 7-8). (A)-(C) are evaluated at the admitted Hall reference and the "
            "measured response case. This overlay does not name a baseline."),
        "explicit_conditions": [
            "breakeven_v1 assumptions A1-A8 accepted by the owner",
            "declared basis: phi as declared per entry, k = 1 (reported ion current = source-exit ion current)",
            "Hall reference inside the PROPOSED box (V_d 150-450 V, eta_b 0.5-0.9, eta_ppu,d over the lane-20 "
            "evidence envelope, eta_v 0.7-1.0 for the optimistic case)",
            "eta_t in the PROPOSED range 0.1-1 (lane 18 cannot yet compute it for any air or Xe case)",
            "omega_f = 0 (permanent-magnet ecr_magnet and zero common deltas); any fixed overhead lowers Y",
            f"reference bus chain {f(d['bus_chain_evidence']['reference_chain']['value'])} (Hayabusa TWT system, "
            "inferred) as the stated chain of the CLEARLY_BELOW test only",
        ],
        "not_concluded": "no ranking, no hard-gate decision, no architecture named, no comparison with the other "
                         "pre-ionizer arm",
    }


# ----------------------------------------------------------------------------------------------------------------------
def _fmt(v, nd=3):
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, str):
        return v
    if abs(v) >= 100:
        return f"{v:.4g}"
    return f"{v:.{nd}g}"


def _rng(a, b):
    return _fmt(a) if _fmt(a) == _fmt(b) else f"{_fmt(a)}-{_fmt(b)}"


def _md_block(d: dict) -> str:
    L = []
    bc = d["breakeven_condition"]
    ar = d["analysis_ranges"]
    tb = bc["tables"]
    L += ["### G1. Hall reference slices and payable bus cost per delivered ampere Y (omega_f = 0, X -> 0)", "",
          "| slice | V_d [V] | eta_b | eta_ppu,d | eta_v | Pi_H [W/A] | Y add_only | Y cost_offset | Y optimistic |",
          "|---|---|---|---|---|---|---|---|---|"]
    for s in SLICE_NAMES:
        sl = bc["hall_reference_slices"][s]
        Y = sl["Y_W_per_A"]
        L.append(f"| {s} | {_fmt(sl['V_d_V'])} | {sl['eta_b']} | {sl['eta_ppu_d']} | {sl['eta_v']} | "
                 f"{_fmt(sl['Pi_H_W_per_A'])} | {_fmt(Y['add_only'])} | {_fmt(Y['cost_offset'])} | "
                 f"{_fmt(Y['optimistic_bound'])} |")
    L += ["", "Most / least favourable corners are the box maximum / minimum of Y for every case (checked in the build).",
          ""]
    L += ["### G2. Y/Pi_H against the relative utilization gain X and the fixed overhead omega_f "
          "(cost_offset and optimistic at eta_b = 0.7; optimistic at eta_v = 0.9)", ""]
    for key in ("add_only", "cost_offset|eta_b=0.7", "optimistic_bound|eta_b=0.7|eta_v=0.9"):
        L += [f"**{key}**", "", "| omega_f \\ X | " + " | ".join(_fmt(x) for x in ar["X_grid"]) + " |",
              "|---" * (len(ar["X_grid"]) + 1) + "|"]
        for wf, vals in tb["Y_over_Pi_H_vs_X"]["values"][key].items():
            L.append(f"| {wf.split('=')[1]} | " + " | ".join(_fmt(v) for v in vals) + " |")
        L.append("")
    L += ["### G3. Minimum and maximum relative gain X that pays at a delivered cost Y = y * Pi_H", "",
          "Entries are X_lo-X_hi ('0-' = any positive share up to X_hi; '-' = no X pays). Uncapped: compare with the "
          "caps below.", ""]
    ys = ar["Y_over_Pi_H_grid"]
    for key in ("add_only", "optimistic_bound|eta_b=0.7|eta_v=0.9"):
        L += [f"**{key}**", "", "| omega_f \\ y | " + " | ".join(_fmt(y) for y in ys) + " |",
              "|---" * (len(ys) + 1) + "|"]
        for wf, vals in tb["payable_X_interval"]["values"][key].items():
            cells = ["-" if iv is None else f"{_fmt(iv[0])}-{_fmt(iv[1])}" for iv in vals]
            L.append(f"| {wf.split('=')[1]} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["### G4. Required relative utilization gain X*(omega) at total overhead fraction omega", "",
          "| case \\ omega | " + " | ".join(_fmt(w) for w in ar["omega_grid"]) + " |",
          "|---" * (len(ar["omega_grid"]) + 1) + "|"]
    for key, vals in tb["X_star_vs_omega"]["values"].items():
        if key in ("add_only", "cost_offset|eta_b=0.5", "cost_offset|eta_b=0.7", "cost_offset|eta_b=0.9",
                   "optimistic_bound|eta_b=0.7|eta_v=0.9"):
            L.append(f"| {key} | " + " | ".join(_fmt(v) for v in vals) + " |")
    caps = tb["X_star_vs_omega"]["X_cap_by_eta_u0"]
    L += ["", "Caps X <= (1 - eta_u0)/eta_u0: " + ", ".join(f"{k} -> {_fmt(v)}" for k, v in caps.items()) + ".", ""]
    L += ["### G5. Minimum interstage transport efficiency Z = C_src,bus / Y (omega_f = 0)", "",
          "| slice, case \\ C_src,bus [W/A] | " + " | ".join(_fmt(c) for c in ar["C_src_bus_grid_W_per_A"]) + " |",
          "|---" * (len(ar["C_src_bus_grid_W_per_A"]) + 1) + "|"]
    for s in SLICE_NAMES:
        for c in CASES:
            vals = tb["Z_vs_C_src_bus"]["values"][s][c]
            L.append(f"| {s}, {c} | " + " | ".join(("**>1**" if v is not None and v > 1 else _fmt(v)) for v in vals)
                     + " |")
    L += ["", "Mid reference with a fixed overhead (eta_u0 = 0.6), optimistic_bound:", "",
          "| omega_f \\ C_src,bus [W/A] | " + " | ".join(_fmt(c) for c in ar["C_src_bus_grid_W_per_A"]) + " |",
          "|---" * (len(ar["C_src_bus_grid_W_per_A"]) + 1) + "|"]
    for wf, vals in tb["Z_vs_C_src_bus_mid_reference_by_omega_f"]["values"]["optimistic_bound"].items():
        L.append(f"| {wf.split('=')[1]} | " + " | ".join(("**>1**" if v is not None and v > 1 else _fmt(v))
                                                        for v in vals) + " |")
    L += ["", "### G6. Evidence placements (declared basis)", "",
          "| entry | mode | reported [W/A] (class, access) | power reference | declared cost [W/A] | bus cost: chain 1 / "
          "reference chain [W/A] | placement | per case (add / cost_offset / optimistic) |",
          "|---|---|---|---|---|---|---|---|"]
    for p in d["evidence_placements"]:
        dc = p["declared_basis"]["cost_W_per_A"]
        bus = p["bus_cost_W_per_A"]
        rv = p["reported"]["value"]
        rvs = _rng(min(rv), max(rv)) if isinstance(rv, list) else _fmt(rv)
        pc = " / ".join(p["placement_by_case"][c] for c in CASES)
        L.append(f"| {p['id']} | {p['mode']} | {rvs} ({p['reported']['evidence_class']}, {p['reported']['access']}) | "
                 f"{p['power_reference']['class']} | {_rng(*dc)} ({p['declared_basis']['phi_kind']}) | "
                 f"{_rng(*dc)} / {_rng(*bus['at_reference_chain'])} | **{p['placement']}** | {pc} |")
    for p in d["not_placeable"]:
        rv = p["reported"]["value"] if p.get("reported") else None
        unit = p["reported"]["unit"] if p.get("reported") else ""
        rvs = "-" if rv is None else (f"{_fmt(rv)} {unit}" if not isinstance(rv, list) else f"{rv} {unit}")
        L.append(f"| {p['id']} | {p['mode']} | {rvs} | - | - | - | **NOT_PLACEABLE** | missing: "
                 f"{p['missing_quantities'][0]} |")
    L += ["", "### G7. Minimum eta_t per entry (declared cost; chain 1 / reference chain; '>1' = cannot pay there)", "",
          "| entry | " + " | ".join(f"{s.split('_')[0]} {c}" for s in SLICE_NAMES for c in CASES) + " |",
          "|---" * (1 + 3 * len(CASES)) + "|"]
    for p in d["evidence_placements"]:
        cells = []
        for s in SLICE_NAMES:
            for c in CASES:
                a = p["placement_by_slice"][s]["eta_t_min_chain_1"][c][0]
                b = p["placement_by_slice"][s]["eta_t_min_reference_chain"][c][0]
                cells.append(("**>1**" if a > 1 else _fmt(a)) + " / " + ("**>1**" if b > 1 else _fmt(b)))
        L.append(f"| {p['id']} | " + " | ".join(cells) + " |")
    L += ["", "### G8. Region of (eta_t, C_src,bus) where ecr_hall could pay (omega_f = 0)", "",
          "Upper edge of C_src,bus [W/A] that could pay somewhere in the box (most favourable corner) / everywhere in "
          "the box (least favourable corner).", "",
          "| eta_t | " + " | ".join(CASES) + " |", "|---" * (1 + len(CASES)) + "|"]
    reg = d["region"]
    for i, t in enumerate(reg["axes"]["eta_t"]):
        L.append(f"| {_fmt(t)} | " + " | ".join(
            f"{_fmt(reg['by_case'][c]['could_pay_somewhere_in_box']['C_src_bus_max_W_per_A'][i])} / "
            f"{_fmt(reg['by_case'][c]['pays_everywhere_in_box']['C_src_bus_max_W_per_A'][i])}" for c in CASES) + " |")
    L += ["", "Lowest eta_t at which any source of a given feed could pay anywhere in the box (ionization floor / "
              "Y_max):", "", "| feed | " + " | ".join(CASES) + " |", "|---" * (1 + len(CASES)) + "|"]
    for k in d["ionization_floor"]["values"]:
        L.append(f"| {k} ({_fmt(d['ionization_floor']['values'][k]['value_W_per_A'], 6)} W/A) | "
                 + " | ".join(_fmt(reg["by_case"][c]["eta_t_floor_any_source"][k]) for c in CASES) + " |")
    L += ["", "eta_t window per entry inside the could-pay region (chain 1 / reference chain; '-' = outside at every "
              "eta_t <= 1):", "", "| entry | " + " | ".join(CASES) + " | pays everywhere at chain 1, eta_t 1 |",
          "|---" * (2 + len(CASES)) + "|"]
    for r in reg["evidence_in_region"]:
        cells = []
        for c in CASES:
            b = r["by_case"][c]
            w1 = b["eta_t_window_chain_1"]
            w2 = b["eta_t_window_reference_chain"]
            cells.append(("-" if w1 is None else f">= {_fmt(w1[0])}") + " / " + ("-" if w2 is None else
                                                                               f">= {_fmt(w2[0])}"))
        every = [c for c in CASES if r["by_case"][c]["pays_everywhere_chain_1_eta_t_1"]]
        L.append(f"| {r['id']} | " + " | ".join(cells) + f" | {', '.join(every) if every else 'no'} |")
    L += ["", "### G9. Single measurements that make a placement definite", "",
          "| entry | eta_t or eta_chain below -> CLEARLY_ABOVE (once the phi bound is tight) | eta_t at least -> "
          "CLEARLY_BELOW with the reference chain (add / cost_offset / optimistic) | eta_chain * eta_t at least -> "
          "CLEARLY_BELOW (add / cost_offset / optimistic) | end-to-end C_del,bus above -> ABOVE [W/A] | C_del,bus at "
          "or below -> BELOW (add / cost_offset / optimistic) [W/A] |", "|---|---|---|---|---|---|"]
    ym = bc["box_extremes_W_per_A"]
    for p in d["evidence_placements"]:
        t = p["to_definite_placement"][0]
        prod = p["to_definite_placement"][2]["product_at_least"]
        conf = t["if_below_once_declared_value_confirmed"]
        below = " / ".join(("unreachable" if not t["moves_to_below"][c]["reachable"] else
                            _fmt(t["moves_to_below"][c]["eta_t_at_least"])) for c in CASES)
        pbelow = " / ".join(("unreachable" if not prod[c]["reachable"] else _fmt(prod[c]["value"])) for c in CASES)
        L.append(f"| {p['id']} | {_fmt(t['if_below'])}" + ("" if conf is None else f" ({_fmt(conf)})") +
                 f" | {below} | {pbelow} | {_fmt(ym['Y_max_any_case'])} | "
                 + " / ".join(_fmt(ym["Y_min_by_case"][c]) for c in CASES) + " |")
    L += ["", "### G10. Milestone-A statement (generated)", ""]
    ms = d["milestone_A_statement"]
    L += [f"- {s}" for s in ms["can_conclude_now"]]
    L += ["", f"Condition set: {ms['condition_set_for_milestone_A']}", ""]
    L += ["### G11. Self-checks", ""]
    for k, v in d["self_checks"].items():
        if isinstance(v, dict):
            L.append(f"- `{k}`: pass = {v['pass']}" + (f", n = {v['n']}" if "n" in v else ""))
    L.append(f"- all pass: {d['self_checks']['all_pass']}")
    return "\n".join(L) + "\n"


def _splice_md(md_text: str, block: str) -> str:
    if MD_BEGIN not in md_text or MD_END not in md_text:
        raise OverlayCheckError("generated-table markers missing from ECR_BREAKEVEN_OVERLAY.md")
    head, rest = md_text.split(MD_BEGIN, 1)
    _, tail = rest.split(MD_END, 1)
    return head + MD_BEGIN + "\n\n" + block + "\n" + MD_END + tail


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="rebuild in memory and byte-compare with the committed files")
    a = ap.parse_args(argv)
    text, block = build()
    md_old = OUT_MD.read_text(encoding="utf-8") if OUT_MD.is_file() else None
    if a.check:
        ok = True
        if not OUT_JSON.is_file() or OUT_JSON.read_text(encoding="utf-8") != text:
            print(f"MISMATCH: {OUT_JSON.name} differs from a fresh build")
            ok = False
        if md_old is None or _splice_md(md_old, block) != md_old:
            print(f"MISMATCH: generated tables in {OUT_MD.name} differ from a fresh build")
            ok = False
        print("OK" if ok else "FAILED")
        return 0 if ok else 1
    OUT_JSON.write_text(text, encoding="utf-8")
    if md_old is not None:
        OUT_MD.write_text(_splice_md(md_old, block), encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(REPO)}" + (f" and tables in {OUT_MD.relative_to(REPO)}" if md_old else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

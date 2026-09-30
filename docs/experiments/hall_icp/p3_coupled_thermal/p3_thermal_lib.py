#!/usr/bin/env python3
"""P3 coupled H-1 / downstream-ICP thermal framework: pure calculation library (lane fo_a9_6_p3_coupled_thermal,
owner directive A9.6 sec. 10; A9.2 icp_coupled_thermal / radiative_view_requirement / 13W_pole_allowance).

Pure functions and data structures only: no file I/O, no global state, not wired into abep_sim/archengine.py.
numpy is used (pinned in requirements-lock.txt).

What is here
  * closed-form configuration (view) factors of coaxial disks / annuli / cylinders, transcribed from the open
    configuration-factor catalogue of J. R. Howell (thermalradiation.net, Section C: C-40, C-41, C-52, C-77, C-80,
    C-81; each function names its catalogue entry) plus disk algebra (reciprocity / superposition);
  * an axisymmetric ray-quadrature view-factor engine for coaxial solid bodies (H-1 head, ICP module, open-frame
    supports with a geometric open-area fraction) - deterministic midpoint quadrature, cosine-weighted, first hit;
    it is checked against the closed forms above (builder self-check and tests);
  * the plume geometric-interception integral (same engine, a user-supplied angular current distribution);
  * a gray-diffuse radiosity enclosure (net-radiation method) with reciprocity enforcement and exact energy closure;
  * a lumped steady-state node network (conduction, environment radiation, enclosure, callables) solved by Newton;
  * the four A9.2 heat terms Q_RF/match, Q_collector, Q_plume, Q_Hall->ICP and the ICP-induced change of the H-1
    radiative view (equivalent heat into H-1 nodes), each from explicit quantity records;
  * an adapter that couples the pinned H2-5 v1 H-1 network (read-only import of its builder) to ICP bodies.

Fail-closed rules (A9.6 sec. 14; CLAUDE.md rules 3, 6, 10)
  * every input is a quantity record {value, units, evidence_class, source}; a missing key, a None value, a
    'TBD...'/'PENDING...' string, a units mismatch or an unknown evidence class raises MissingInputError / InputError;
  * SYNTHETIC_TEST_DATA_NOT_EVIDENCE records never mix with evidence records (SyntheticMixError);
  * no hidden defaults: switches (e.g. optional energy terms) must be given explicitly;
  * a non-converged network raises NumericalFailure (no half-converged state); geometry outside the engine's
    domain raises GeometryError; ranges outside a formula's domain raise DomainError.
  * nothing here returns a thermal PASS: results carry status COMPUTED_CONDITIONAL (or the refusal), and the closure
    statuses ICP_COUPLED_THERMAL / ANODE_THERMAL_CLOSURE stay UNRESOLVED (owner A9.2, A9.6).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

SIGMA_SB = 5.670374419e-8   # W m^-2 K^-4, exact (CODATA; same constant and citation as the pinned H2-5 builder)
T0C = 273.15

SYN = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "published analog", SYN)
NON_MEASURED = tuple(c for c in EVIDENCE_CLASSES if c not in ("measured", SYN))
RESULT_STATUSES = ("COMPUTED_CONDITIONAL", "NOT_EVALUATED", "INCOMPLETE_EVIDENCE", "OUT_OF_DOMAIN",
                   "NUMERICAL_FAILURE")
CLOSURE_STATUSES = {"ICP_COUPLED_THERMAL": "UNRESOLVED", "ANODE_THERMAL_CLOSURE": "UNRESOLVED"}
TBD_PREFIXES = ("TBD", "PENDING", "TBD_AFTER_EVIDENCE", "TBD_OWNER", "TBD_AFTER_IMPEDANCE_MAP")


# ============================================================================================ errors
class InputError(ValueError):
    """Malformed input record (units, evidence class, sign, range)."""


class MissingInputError(InputError):
    """A required input is absent, None or TBD: the calculation refuses (INCOMPLETE_EVIDENCE)."""

    def __init__(self, missing, context=""):
        self.missing = sorted(set(missing))
        super().__init__(f"{context}: missing / TBD inputs {self.missing}")


class SyntheticMixError(InputError):
    """SYNTHETIC_TEST_DATA_NOT_EVIDENCE records mixed with evidence records (refused, A9.6 sec. 14)."""


class GeometryError(ValueError):
    """Geometry outside the engine's domain (overlap, non-tiling zones, non-positive dimensions)."""


class DomainError(ValueError):
    """Input outside a formula's stated domain (OUT_OF_DOMAIN, distinct from a failure)."""


class NumericalFailure(RuntimeError):
    """Solver did not converge or energy balance did not close (NUMERICAL_FAILURE); no partial state returned."""


# ============================================================================================ quantity records
def q(value, units, evidence_class, source):
    """Build a quantity record (helper for callers and tests)."""
    return {"value": value, "units": units, "evidence_class": evidence_class, "source": source}


def _is_tbd(v):
    return v is None or (isinstance(v, str) and v.strip().upper().startswith(TBD_PREFIXES))


def take(inputs, spec, context):
    """Validate and extract inputs.

    spec: {key: units}. Returns ({key: value}, provenance) or raises. A record is a dict with value / units /
    evidence_class / source. Missing, None or TBD -> MissingInputError listing every missing key (not just the first).
    """
    missing, vals, classes = [], {}, {}
    for key, units in spec.items():
        rec = inputs.get(key) if isinstance(inputs, dict) else None
        if rec is None or not isinstance(rec, dict) or _is_tbd(rec.get("value")):
            missing.append(key)
            continue
        if rec.get("units") != units:
            raise InputError(f"{context}: {key} units {rec.get('units')!r} != required {units!r}")
        ec = rec.get("evidence_class")
        if ec not in EVIDENCE_CLASSES:
            raise InputError(f"{context}: {key} evidence_class {ec!r} not in {EVIDENCE_CLASSES}")
        if not rec.get("source"):
            raise InputError(f"{context}: {key} has no source")
        v = rec["value"]
        if isinstance(v, bool) or not isinstance(v, (int, float, list, tuple, str)):
            raise InputError(f"{context}: {key} value type {type(v).__name__} not accepted")
        if isinstance(v, (int, float)) and not math.isfinite(float(v)):
            raise InputError(f"{context}: {key} is not finite")
        vals[key] = v
        classes[key] = ec
    if missing:
        raise MissingInputError(missing, context)
    return vals, provenance(classes)


def provenance(classes):
    """Result basis from the evidence classes of the inputs used (refuses synthetic/evidence mixing)."""
    cs = set(classes.values())
    if SYN in cs and len(cs) > 1:
        raise SyntheticMixError(f"synthetic and evidence inputs mixed: {sorted(cs)}")
    if cs == {SYN}:
        basis = SYN
    elif cs <= {"measured"}:
        basis = "MEASURED_INPUTS_ONLY"
    else:
        basis = "CONDITIONAL_ON_NON_MEASURED_INPUTS"
    return {"basis": basis, "conditional_on": sorted(k for k, c in classes.items() if c not in ("measured", SYN)),
            "evidence_classes": dict(sorted(classes.items()))}


def merge_provenance(*provs):
    classes = {}
    for p in provs:
        classes.update(p["evidence_classes"])
    return provenance(classes)


def flag(inputs, key, allowed, context):
    """An explicit switch (no hidden default): {'value': one of allowed, 'source': ...}."""
    rec = inputs.get(key)
    if rec is None or _is_tbd(rec.get("value")):
        raise MissingInputError([key], context)
    if rec.get("value") not in allowed:
        raise InputError(f"{context}: {key} must be one of {allowed}, got {rec.get('value')!r}")
    if not rec.get("source"):
        raise InputError(f"{context}: switch {key} has no source / rationale")
    return rec["value"]


def _nonneg(name, v):
    if v < 0:
        raise InputError(f"{name} must be >= 0 (got {v})")
    return v


def _fraction(name, v):
    if not (0.0 <= v <= 1.0):
        raise DomainError(f"{name} must lie in [0, 1] (got {v})")
    return v


# ============================================================================================ closed-form view factors
# Source: J. R. Howell, 'A Catalog of Radiation Heat Transfer Configuration Factors', online edition,
# https://www.thermalradiation.net/sectionc/C-xx.html (equation images read 2026-09-30). Each function states its entry.

def vf_disk_to_parallel_coaxial_disk(r1, r2, a):
    """C-41 (Keene; Hottel 1931; Feingold 1978): disk A1 radius r1 to parallel coaxial disk A2 radius r2 at distance a.
    R_i = r_i / a; X = 1 + (1 + R2^2) / R1^2; F12 = 1/2 {X - [X^2 - 4 (R2/R1)^2]^(1/2)}."""
    if r1 <= 0 or r2 <= 0 or a <= 0:
        raise DomainError("C-41 requires r1, r2, a > 0")
    R1, R2 = r1 / a, r2 / a
    X = 1.0 + (1.0 + R2 * R2) / (R1 * R1)
    c = (R2 / R1) ** 2
    # algebraically identical rationalized form 2c / (X + sqrt(X^2 - 4c)) (no cancellation at large separation)
    return 2.0 * c / (X + math.sqrt(max(X * X - 4.0 * c, 0.0)))


def vf_disk_to_parallel_coaxial_disk_same_radius(r, a):
    """C-40 (Keene; Hottel 1931; Feingold 1978): R = r/a; X = (2R^2 + 1)/R^2; F12 = 1/2 {X - [X^2 - 4]^(1/2)}."""
    if r <= 0 or a <= 0:
        raise DomainError("C-40 requires r, a > 0")
    R = r / a
    X = (2.0 * R * R + 1.0) / (R * R)
    return 2.0 / (X + math.sqrt(X * X - 4.0))   # rationalized form of 1/2 {X - [X^2 - 4]^(1/2)}


def vf_annulus_to_parallel_coaxial_annulus(r1, r2, r3, r4, a):
    """C-52 (Leuenberger and Person): ring A1 (r1 < r2) to parallel coaxial ring A2 (r3 < r4) at distance a.
    H = a/r1, R2 = r2/r1, R3 = r3/r1, R4 = r4/r1;
    F12 = 1/(2 (R2^2 - 1)) { [(R2^2+R3^2+H^2)^2 - (2 R3 R2)^2]^(1/2) - [(R2^2+R4^2+H^2)^2 - (2 R2 R4)^2]^(1/2)
                             + [(1+R4^2+H^2)^2 - (2 R4)^2]^(1/2) - [(1+R3^2+H^2)^2 - (2 R3)^2]^(1/2) }."""
    if not (0 < r1 < r2) or not (0 < r3 < r4) or a <= 0:
        raise DomainError("C-52 requires 0 < r1 < r2, 0 < r3 < r4, a > 0")
    H, R2, R3, R4 = a / r1, r2 / r1, r3 / r1, r4 / r1

    def s(x, y):
        return math.sqrt(max(x * x - y * y, 0.0))
    return (s(R2 * R2 + R3 * R3 + H * H, 2 * R3 * R2) - s(R2 * R2 + R4 * R4 + H * H, 2 * R2 * R4)
            + s(1 + R4 * R4 + H * H, 2 * R4) - s(1 + R3 * R3 + H * H, 2 * R3)) / (2.0 * (R2 * R2 - 1.0))


def vf_annulus_to_annulus_by_disk_algebra(r1, r2, r3, r4, a):
    """Same configuration as C-52 from C-41 by reciprocity/superposition (inner radii may be 0):
    A1 F(A1 -> disk r) = A(r2) F(r2 -> r) - A(r1) F(r1 -> r); F(A1 -> A2) = F(A1 -> disk r4) - F(A1 -> disk r3)."""
    if not (0 <= r1 < r2) or not (0 <= r3 < r4) or a <= 0:
        raise DomainError("annulus algebra requires 0 <= r1 < r2, 0 <= r3 < r4, a > 0")

    def AF_disk_to(ri, r):  # A(ri) F(disk ri -> disk r), 0 for a degenerate disk
        if ri <= 0 or r <= 0:
            return 0.0
        return math.pi * ri * ri * vf_disk_to_parallel_coaxial_disk(ri, r, a)
    A1 = math.pi * (r2 * r2 - r1 * r1)

    def AF_ann_to_disk(r):
        return AF_disk_to(r2, r) - AF_disk_to(r1, r)
    return (AF_ann_to_disk(r4) - AF_ann_to_disk(r3)) / A1


def vf_cylinder_outer_to_end_annulus(r1, r2, h):
    """C-77 (Sparrow, Miller and Jonsson; Rea; Naraghi and Chung; Masuda; Brockmann): outer surface A1 of a cylinder
    (radius r1, height h) to the annular disk A2 (r1..r2) at its end. R = r1/r2, H = h/r2, A = H^2 + R^2 - 1,
    B = H^2 - R^2 + 1; F12 = B/(8RH) + 1/(2 pi) { acos(A/B) - 1/(2H) [ (A+2)^2/R^2 - 4 ]^(1/2) acos(A R / B)
    - A/(2RH) asin(R) }."""
    if not (0 < r1 < r2) or h <= 0:
        raise DomainError("C-77 requires 0 < r1 < r2, h > 0")
    R, H = r1 / r2, h / r2
    A = H * H + R * R - 1.0
    B = H * H - R * R + 1.0
    c = lambda x: math.acos(max(-1.0, min(1.0, x)))  # noqa: E731
    return (B / (8.0 * R * H) + (1.0 / (2.0 * math.pi)) * (
        c(A / B) - (1.0 / (2.0 * H)) * math.sqrt(max((A + 2.0) ** 2 / (R * R) - 4.0, 0.0)) * c(A * R / B)
        - A / (2.0 * R * H) * math.asin(R)))


def vf_disk_in_base_to_cylinder_inside(r1, r2, h):
    """C-80 (Leuenberger and Person; Buschman and Pittman): disk A1 (radius r1) in the base of a right circular
    cylinder (radius r2 >= r1, height h) to the cylinder's inside surface A2. R = r2/r1, H = h/r1;
    F12 = 1/2 { 1 - R^2 - H^2 + [ (1 + R^2 + H^2)^2 - 4 R^2 ]^(1/2) }."""
    if r1 <= 0 or r2 < r1 or h <= 0:
        raise DomainError("C-80 requires 0 < r1 <= r2, h > 0")
    R, H = r2 / r1, h / r1
    return 0.5 * (1.0 - R * R - H * H + math.sqrt((1.0 + R * R + H * H) ** 2 - 4.0 * R * R))


def vf_cylinder_inside_to_coaxial_disk(r, h1, h2):
    """C-81 (Leuenberger and Person): inside surface A1 of a right cylinder section (radius r, length h1) to a coaxial
    disk A2 of the same radius separated by h2 from the section's base. H1 = h1/r, H2 = h2/r;
    F12 = 1/4 { (1 + H2/H1) [4 + (H1 + H2)^2]^(1/2) - (H1 + 2 H2) - (H2/H1) (4 + H2^2)^(1/2) }."""
    if r <= 0 or h1 <= 0 or h2 < 0:
        raise DomainError("C-81 requires r > 0, h1 > 0, h2 >= 0")
    H1, H2 = h1 / r, h2 / r
    return 0.25 * ((1.0 + H2 / H1) * math.sqrt(4.0 + (H1 + H2) ** 2) - (H1 + 2.0 * H2)
                   - (H2 / H1) * math.sqrt(4.0 + H2 * H2))


CLOSED_FORMS = {
    "C-40": vf_disk_to_parallel_coaxial_disk_same_radius,
    "C-41": vf_disk_to_parallel_coaxial_disk,
    "C-52": vf_annulus_to_parallel_coaxial_annulus,
    "C-77": vf_cylinder_outer_to_end_annulus,
    "C-80": vf_disk_in_base_to_cylinder_inside,
    "C-81": vf_cylinder_inside_to_coaxial_disk,
}


# ============================================================================================ axisymmetric geometry
@dataclass
class Body:
    """Coaxial solid annular body r_in <= r <= r_out, z_lo <= z <= z_hi (axis = thrust axis z, +z downstream).

    r_in = 0: solid cylinder (no bore). tau: geometric open-area fraction of an open-frame body (0 = opaque solid);
    a ray hitting it deposits (1 - tau) of its weight and the rest continues as if the body were absent (gray,
    direction-independent approximation). Zones: optional lists partitioning each surface:
      up / down faces: [(name, r_a, r_b), ...]  (radial breakpoints, must tile [r_in, r_out])
      outer / bore laterals: [(name, z_a, z_b), ...] (must tile [z_lo, z_hi])
    """
    name: str
    r_in: float
    r_out: float
    z_lo: float
    z_hi: float
    tau: float = 0.0
    up: list | None = None
    down: list | None = None
    outer: list | None = None
    bore: list | None = None
    _zones: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        if not (0.0 <= self.r_in < self.r_out) or not (self.z_lo < self.z_hi):
            raise GeometryError(f"body {self.name}: need 0 <= r_in < r_out and z_lo < z_hi")
        if not (0.0 <= self.tau < 1.0):
            raise GeometryError(f"body {self.name}: tau must be in [0, 1)")
        if self.r_in == 0.0 and self.bore:
            raise GeometryError(f"body {self.name}: solid cylinder has no bore zones")
        spec = {"up": (self.up, self.r_in, self.r_out), "down": (self.down, self.r_in, self.r_out),
                "outer": (self.outer, self.z_lo, self.z_hi)}
        if self.r_in > 0.0:
            spec["bore"] = (self.bore, self.z_lo, self.z_hi)
        for side, (zl, lo, hi) in spec.items():
            if zl is None:
                zl = [(f"{self.name}.{side}", lo, hi)]
            edges = [zl[0][1]] + [z[2] for z in zl]
            if abs(edges[0] - lo) > 1e-12 or abs(edges[-1] - hi) > 1e-12 or any(
                    zl[i][2] != zl[i + 1][1] for i in range(len(zl) - 1)) or any(z[2] <= z[1] for z in zl):
                raise GeometryError(f"body {self.name}: {side} zones must tile [{lo}, {hi}] in increasing order")
            self._zones[side] = [(str(n), float(a), float(b)) for n, a, b in zl]

    def zones(self):
        return self._zones

    def surface_ids(self):
        return [z[0] for side in ("up", "down", "outer", "bore") for z in self._zones.get(side, [])]

    def zone_area(self, side, a, b):
        if side in ("up", "down"):
            A = math.pi * (b * b - a * a)
        else:
            R = self.r_out if side == "outer" else self.r_in
            A = 2.0 * math.pi * R * (b - a)
        return A * (1.0 - self.tau)


def check_geometry(bodies):
    names = set()
    for b in bodies:
        for s in b.surface_ids():
            if s in names or s == "SPACE":
                raise GeometryError(f"duplicate / reserved surface id {s}")
            names.add(s)
    for i, a in enumerate(bodies):
        for b in bodies[i + 1:]:
            if a.z_lo < b.z_hi and b.z_lo < a.z_hi and a.r_in < b.r_out and b.r_in < a.r_out:
                raise GeometryError(f"bodies {a.name} and {b.name} overlap")
    return sorted(names)


def _first_hits(o, d, bodies, ignore, eps):
    """First hit per ray among non-ignored bodies. Returns (t, body_idx, side_idx, coord); body_idx -1 = escaped."""
    n = o.shape[0]
    tbest = np.full(n, np.inf)
    bidx = np.full(n, -1, dtype=int)
    sidx = np.full(n, -1, dtype=int)
    coord = np.zeros(n)
    ox, oy, oz = o[:, 0], o[:, 1], o[:, 2]
    dx, dy, dz = d[:, 0], d[:, 1], d[:, 2]
    a2 = dx * dx + dy * dy
    bq = 2.0 * (ox * dx + oy * dy)
    rho0 = ox * ox + oy * oy
    for k, b in enumerate(bodies):
        act = ~ignore[:, k]
        cands = []
        with np.errstate(divide="ignore", invalid="ignore"):
            # upstream face (z_lo, faces -z): reached by rays travelling +z
            t = np.where(dz > 0, (b.z_lo - oz) / dz, np.inf)
            rr = np.sqrt((ox + t * dx) ** 2 + (oy + t * dy) ** 2)
            ok = act & (t > eps) & (rr >= b.r_in) & (rr <= b.r_out)
            cands.append((np.where(ok, t, np.inf), 0, rr))
            t = np.where(dz < 0, (b.z_hi - oz) / dz, np.inf)
            rr = np.sqrt((ox + t * dx) ** 2 + (oy + t * dy) ** 2)
            ok = act & (t > eps) & (rr >= b.r_in) & (rr <= b.r_out)
            cands.append((np.where(ok, t, np.inf), 1, rr))
            # outer lateral: entering root
            c = rho0 - b.r_out * b.r_out
            disc = bq * bq - 4.0 * a2 * c
            sq = np.sqrt(np.where(disc > 0, disc, 0.0))
            t = np.where((a2 > 0) & (disc > 0), (-bq - sq) / (2.0 * a2), np.inf)
            zz = oz + t * dz
            ok = act & (t > eps) & (zz >= b.z_lo) & (zz <= b.z_hi)
            cands.append((np.where(ok, t, np.inf), 2, zz))
            if b.r_in > 0:
                c = rho0 - b.r_in * b.r_in
                disc = bq * bq - 4.0 * a2 * c
                sq = np.sqrt(np.where(disc > 0, disc, 0.0))
                t = np.where((a2 > 0) & (disc > 0), (-bq + sq) / (2.0 * a2), np.inf)
                zz = oz + t * dz
                ok = act & (t > eps) & (zz >= b.z_lo) & (zz <= b.z_hi)
                cands.append((np.where(ok, t, np.inf), 3, zz))
        for t, side, cc in cands:
            better = t < tbest
            tbest = np.where(better, t, tbest)
            bidx = np.where(better, k, bidx)
            sidx = np.where(better, side, sidx)
            coord = np.where(better, cc, coord)
    return tbest, bidx, sidx, coord


SIDES = ("up", "down", "outer", "bore")


def trace(o, d, w, bodies, eps):
    """Deposit ray weights on the first surface hit (open-frame bodies pass tau of the weight on).
    Returns {surface_id: weight, 'SPACE': weight}."""
    out = {s: 0.0 for b in bodies for s in b.surface_ids()}
    out["SPACE"] = 0.0
    ignore = np.zeros((o.shape[0], len(bodies)), dtype=bool)
    w = w.copy()
    for _ in range(len(bodies) + 1):
        if w.size == 0 or not np.any(w > 0):
            break
        t, bi, si, cc = _first_hits(o, d, bodies, ignore, eps)
        esc = bi < 0
        out["SPACE"] += float(np.sum(w[esc]))
        cont = np.zeros(o.shape[0], dtype=bool)
        for k, b in enumerate(bodies):
            for s_i, side in enumerate(SIDES):
                zl = b.zones().get(side)
                if not zl:
                    continue
                m = (bi == k) & (si == s_i)
                if not np.any(m):
                    continue
                edges = np.array([zl[0][1]] + [z[2] for z in zl])
                zi = np.clip(np.searchsorted(edges, cc[m], side="right") - 1, 0, len(zl) - 1)
                dep = w[m] * (1.0 - b.tau)
                for j, z in enumerate(zl):
                    out[z[0]] += float(np.sum(dep[zi == j]))
                if b.tau > 0:
                    cont |= m
                    ignore[m, k] = True
        taus = np.array([b.tau for b in bodies] + [0.0])
        w = np.where(cont, w * taus[bi], 0.0)
    return out


def _dirs_cosine(n_u, n_phi):
    """Midpoint quadrature of the cosine-weighted hemisphere: u = sin^2(theta) uniform, phi uniform (equal weights)."""
    u = (np.arange(n_u) + 0.5) / n_u
    ph = (np.arange(n_phi) + 0.5) * 2.0 * math.pi / n_phi
    U, PH = np.meshgrid(u, ph, indexing="ij")
    st, ct = np.sqrt(U).ravel(), np.sqrt(1.0 - U).ravel()
    return st * np.cos(PH.ravel()), st * np.sin(PH.ravel()), ct


def emit_zone(body, side, a, b, res, directions=None):
    """Quadrature rays leaving a zone (by axisymmetry the source points lie in the x-z half-plane, phi = 0).
    res = (n_pos, n_u, n_phi). directions: None = diffuse (cosine) emission; or (sx, sy, sz) unit vectors in the
    local frame (normal = local z) with equal weights (plume sampling)."""
    n_pos, n_u, n_phi = res
    if directions is None:
        lx, ly, lz = _dirs_cosine(n_u, n_phi)
    else:
        lx, ly, lz = directions
    nd = lx.size
    if side in ("up", "down"):
        s = -1.0 if side == "up" else 1.0
        z0 = body.z_lo if side == "up" else body.z_hi
        rho = np.sqrt(a * a + (np.arange(n_pos) + 0.5) / n_pos * (b * b - a * a))
        o = np.stack([np.repeat(rho, nd), np.zeros(n_pos * nd), np.full(n_pos * nd, z0)], axis=1)
        # local frame: normal (0,0,s), tangents (1,0,0), (0,s,0) (right-handed for both signs)
        d = np.stack([np.tile(lx, n_pos), np.tile(ly * s, n_pos), np.tile(lz * s, n_pos)], axis=1)
    else:
        s = 1.0 if side == "outer" else -1.0
        R = body.r_out if side == "outer" else body.r_in
        z = a + (np.arange(n_pos) + 0.5) / n_pos * (b - a)
        o = np.stack([np.full(n_pos * nd, R), np.zeros(n_pos * nd), np.repeat(z, nd)], axis=1)
        # local frame: normal (s,0,0), tangents (0,1,0), (0,0,1)
        d = np.stack([np.tile(lz * s, n_pos), np.tile(lx, n_pos), np.tile(ly, n_pos)], axis=1)
    w = np.full(o.shape[0], 1.0 / o.shape[0])
    return o, d, w


def _scale(bodies):
    return max(max(b.r_out, abs(b.z_lo), abs(b.z_hi)) for b in bodies)


def view_factors(bodies, res, emitters=None):
    """Diffuse view factors between every zone of every body and SPACE (ray quadrature).
    emitters: optional subset of surface ids whose rows are computed (default: all; reciprocity metrics need all).
    Returns {'surfaces', 'area_m2', 'F' (dict of dict incl. SPACE), 'res', 'reciprocity_max_rel'}; the reciprocity
    metric is taken over pairs with both F > 1e-3 (None when rows are a subset)."""
    ids = check_geometry(bodies)
    if min(res) < 1:
        raise DomainError("resolution entries must be >= 1")
    if emitters is not None and not set(emitters) <= set(ids):
        raise GeometryError(f"unknown emitters {sorted(set(emitters) - set(ids))}")
    eps = 1e-9 * _scale(bodies)
    F, area = {}, {}
    for b in bodies:
        for side, zl in b.zones().items():
            for name, a, c in zl:
                area[name] = b.zone_area(side, a, c)
                if emitters is not None and name not in emitters:
                    continue
                o, d, w = emit_zone(b, side, a, c, res)
                F[name] = trace(o, d, w, bodies, eps)
    rec = None
    if emitters is None:
        rec = 0.0
        for i in ids:
            for j in ids:
                if F[i][j] > 1e-3 and F[j][i] > 1e-3:
                    x, y = area[i] * F[i][j], area[j] * F[j][i]
                    rec = max(rec, abs(x - y) / max(x, y))
    return {"surfaces": ids, "area_m2": area, "F": F, "res": list(res), "reciprocity_max_rel": rec}


def plume_directions(cdf_table, n_u, n_phi):
    """Equal-weight directions from a tabulated cumulative current fraction C(theta) (theta in deg from +z, C(0)=0,
    C(theta_max)=1, non-decreasing, theta_max <= 90): inverse-CDF midpoints x uniform azimuth."""
    th = np.array([p[0] for p in cdf_table], dtype=float)
    C = np.array([p[1] for p in cdf_table], dtype=float)
    if th[0] != 0.0 or C[0] != 0.0 or abs(C[-1] - 1.0) > 1e-12 or np.any(np.diff(th) <= 0) or np.any(np.diff(C) < 0):
        raise DomainError("plume CDF table must start at (0, 0), end at C = 1, theta increasing, C non-decreasing")
    if th[-1] > 90.0:
        raise DomainError("plume CDF theta_max must be <= 90 deg (forward hemisphere only)")
    p = (np.arange(n_u) + 0.5) / n_u
    theta = np.radians(np.interp(p, C, th))
    ph = (np.arange(n_phi) + 0.5) * 2.0 * math.pi / n_phi
    TH, PH = np.meshgrid(theta, ph, indexing="ij")
    st = np.sin(TH).ravel()
    return st * np.cos(PH.ravel()), st * np.sin(PH.ravel()), np.cos(TH).ravel()


def plume_interception(bodies, source_body, source_zone, cdf_table, res):
    """Fraction of the ion current leaving a source zone (e.g. the H-1 channel-exit aperture, a +z 'down' face)
    that first hits each surface (open-frame bodies pass tau). Every source point emits the same axisymmetric
    distribution about +z (a model assumption, stated; the real distribution is measured)."""
    check_geometry(bodies)
    zl = {z[0]: z for z in source_body.zones()["down"]}
    if source_zone not in zl:
        raise GeometryError(f"{source_zone} is not a downstream-face zone of {source_body.name}")
    _, a, c = zl[source_zone]
    dirs = plume_directions(cdf_table, res[1], res[2])
    o, d, w = emit_zone(source_body, "down", a, c, res, directions=dirs)
    return trace(o, d, w, bodies, 1e-9 * _scale(bodies))


# ============================================================================================ radiosity enclosure
def enforce_reciprocity(F, area, ids):
    """Symmetrize A_i F_ij (mean of the two quadrature estimates) and close each row on SPACE:
    F_i,SPACE = 1 - sum_j F_ij. Raises NumericalFailure if a row would need a negative SPACE factor."""
    G = {i: {} for i in ids}
    adj = 0.0
    for i in ids:
        for j in ids:
            s = 0.5 * (area[i] * F[i][j] + area[j] * F[j][i])
            G[i][j] = s / area[i] if area[i] > 0 else 0.0
            adj = max(adj, abs(G[i][j] - F[i][j]))
    for i in ids:
        rest = 1.0 - sum(G[i][j] for j in ids)
        if rest < -1e-9:
            raise NumericalFailure(f"reciprocity enforcement left row {i} with F_space = {rest:.3g} < 0")
        G[i]["SPACE"] = max(rest, 0.0)
    return G, adj


def radiosity_solve(ids, area, F, eps, T, T_space):
    """Net-radiation method for a gray-diffuse enclosure closed by SPACE (black at T_space).
    eps[i] in (0, 1] or 'RERADIATING' (q_i = 0). T[i] in K (ignored for reradiating surfaces).
    Returns {'q_W': net heat LEAVING each surface, 'q_space_W': net heat absorbed by SPACE, 'J': radiosity}."""
    n = len(ids)
    ix = {s: k for k, s in enumerate(ids)}
    M = np.zeros((n, n))
    rhs = np.zeros(n)
    Js = SIGMA_SB * T_space ** 4
    for s in ids:
        i = ix[s]
        if eps[s] == "RERADIATING":
            M[i, i] = 1.0
            for t in ids:
                M[i, ix[t]] -= F[s][t]
            rhs[i] = F[s]["SPACE"] * Js
        else:
            e = float(eps[s])
            if not (0.0 < e <= 1.0):
                raise DomainError(f"emissivity of {s} must be in (0, 1]")
            M[i, i] = 1.0
            for t in ids:
                M[i, ix[t]] -= (1.0 - e) * F[s][t]
            rhs[i] = e * SIGMA_SB * T[s] ** 4 + (1.0 - e) * F[s]["SPACE"] * Js
    J = np.linalg.solve(M, rhs)
    qd = {}
    for s in ids:
        G = sum(F[s][t] * J[ix[t]] for t in ids) + F[s]["SPACE"] * Js
        qd[s] = 0.0 if eps[s] == "RERADIATING" else area[s] * (J[ix[s]] - G)
    q_space = sum(area[s] * F[s]["SPACE"] * (J[ix[s]] - Js) for s in ids)
    return {"q_W": qd, "q_space_W": float(q_space), "J": {s: float(J[ix[s]]) for s in ids}}


# ============================================================================================ node network
@dataclass
class Enclosure:
    """Radiosity enclosure attached to nodes. surf_node[s] = node name, or ('WEIGHTED', {node: w}) for a pseudo
    surface emitting at (sum w T^4)^(1/4) and splitting its net heat by w, or 'RERADIATING'."""
    ids: list
    area: dict
    F: dict           # reciprocity-enforced, rows closed on SPACE
    eps: dict
    surf_node: dict
    T_space: float


@dataclass
class Network:
    unknown: list                 # node names solved for
    fixed: dict                   # boundary node -> T (K)
    loads: dict                   # node -> W (constant)
    cond: list = field(default_factory=list)       # (a, b, G W/K)
    env_rad: list = field(default_factory=list)    # (node, epsA m2, absorbed_W, T_env K)
    enclosures: list = field(default_factory=list)
    callables: list = field(default_factory=list)  # f(Tdict) -> ({node: W into node}, boundary_out_W, generated_W)


def _net_flows(net, T):
    r = {n: 0.0 for n in net.unknown}
    out = 0.0
    loads = sum(net.loads.values())
    absorbed = 0.0

    def add(n, Q):
        nonlocal out
        if n in r:
            r[n] += Q
        else:
            out += Q  # heat delivered to a fixed (boundary) node leaves the system
    for n, Q in net.loads.items():
        add(n, Q)
    for a, b, G in net.cond:
        Q = G * (T[a] - T[b])
        add(a, -Q)
        add(b, Q)
    for n, epsA, absW, Te in net.env_rad:
        if n not in r:
            raise InputError(f"environment radiation must attach to a solved node, not {n}")
        Q = epsA * SIGMA_SB * (T[n] ** 4 - Te ** 4) - absW
        add(n, -Q)
        out += Q
        absorbed += absW
    for enc in net.enclosures:
        Ts = {}
        for s in enc.ids:
            m = enc.surf_node[s]
            if m == "RERADIATING":
                continue
            if isinstance(m, tuple):
                Ts[s] = sum(w * T[k] ** 4 for k, w in m[1].items()) ** 0.25
            else:
                Ts[s] = T[m]
        res = radiosity_solve(enc.ids, enc.area, enc.F, enc.eps, Ts, enc.T_space)
        for s, qs in res["q_W"].items():
            m = enc.surf_node[s]
            if m == "RERADIATING":
                continue
            if isinstance(m, tuple):
                for k, w in m[1].items():
                    add(k, -qs * w)
            else:
                add(m, -qs)
        out += res["q_space_W"]
    for f in net.callables:
        into, bout, gen = f(T)
        for n, Q in into.items():
            add(n, Q)
        out += bout
        loads += gen
    return r, out, loads, absorbed


def solve_network(net, T0=400.0, tol=1e-7, max_iter=200):
    """Newton solve of the steady network; raises NumericalFailure unless converged AND the energy balance closes
    (loads + absorbed environment = heat to boundaries + SPACE, relative 1e-6)."""
    names = list(net.unknown)
    for n in names:
        if n in net.fixed:
            raise InputError(f"node {n} both unknown and fixed")
    T = {n: float(T0) for n in names}
    T.update({k: float(v) for k, v in net.fixed.items()})
    x = np.array([T[n] for n in names])
    for it in range(max_iter):
        T.update(dict(zip(names, x)))
        r, *_ = _net_flows(net, T)
        rv = np.array([r[n] for n in names])
        J = np.zeros((len(names), len(names)))
        for j, n in enumerate(names):
            Tp = dict(T)
            Tp[n] += 1e-3
            rp, *_ = _net_flows(net, Tp)
            J[:, j] = (np.array([rp[m] for m in names]) - rv) / 1e-3
        try:
            step = np.linalg.solve(J, -rv)
        except np.linalg.LinAlgError as e:
            raise NumericalFailure(f"singular Jacobian: {e}") from e
        step = np.clip(step, -100.0, 100.0)
        x = x + step
        if np.any(x <= 0):
            x = np.maximum(x, 1.0)
        if np.max(np.abs(step)) < tol:
            T.update(dict(zip(names, x)))
            r, out, loads, absorbed = _net_flows(net, T)
            res = max(abs(v) for v in r.values()) if r else 0.0
            if res > 1e-6 * max(1.0, loads + absorbed):
                break
            if abs(loads + absorbed - out) > 1e-6 * max(1.0, loads + absorbed):
                raise NumericalFailure("energy balance does not close")
            return {"T_K": {n: float(T[n]) for n in names}, "iterations": it + 1, "load_W": loads,
                    "absorbed_env_W": absorbed, "rejected_W": out, "max_residual_W": res}
    raise NumericalFailure("thermal network did not converge (NUMERICAL_FAILURE); no half-converged state returned")


# ============================================================================================ A9.2 heat terms
Q_RF_SPEC = {"P_forward_W": "W", "P_reflected_W": "W", "P_line_match_loss_W": "W",
             "f_line_match_loss_on_module": "-", "f_delivered_leaving_module": "-"}


def q_rf_match(inputs):
    """Q_RF/match on the ICP module (A9.2 rf_measurement_reference; ICD ICP-36 / ICP-43).

    P_net = P_forward - P_reflected (generator / 50-ohm side of the local match, RP-CPL);
    P_delivered = P_net - P_line/match,loss (A9.2; never P_forward = P_plasma);
    Q_RF/match = f_on_module * P_line/match,loss + (1 - f_leaving) * P_delivered,
    f_on_module: share of the line + local-match loss dissipated on the module / moving platform (from the P2 two-port
    characterization split, CAL-P2-02 / CAL-P2-03); f_leaving: share of the delivered power that leaves the ICP
    assembly (extracted-electron / plasma enthalpy, optical emission escaping) - TBD_AFTER_EVIDENCE; the bound
    f_leaving = 0 (all delivered power dissipated on the module) is accepted only as an explicit input record.
    Optional antenna_ohmic breakdown: I_ant,rms^2 R_ant,cold(T) (P2 CAL-P2-08 cold reference) when both are given."""
    v, prov = take(inputs, Q_RF_SPEC, "Q_RF/match")
    Pf, Pr, Pl = _nonneg("P_forward", v["P_forward_W"]), _nonneg("P_reflected", v["P_reflected_W"]), \
        _nonneg("P_line/match,loss", v["P_line_match_loss_W"])
    fon, fl = _fraction("f_on_module", v["f_line_match_loss_on_module"]), \
        _fraction("f_leaving", v["f_delivered_leaving_module"])
    Pnet = Pf - Pr
    if Pnet < 0:
        raise InputError("P_reflected > P_forward: invalid RF record")
    Pdel = Pnet - Pl
    if Pdel < 0:
        raise InputError("P_line/match,loss > P_forward - P_reflected: invalid RF record")
    out = {"P_net_W": Pnet, "P_delivered_W": Pdel, "Q_line_match_on_module_W": fon * Pl,
           "Q_delivered_on_module_W": (1.0 - fl) * Pdel,
           "Q_RF_match_W": fon * Pl + (1.0 - fl) * Pdel, "provenance": prov, "status": "COMPUTED_CONDITIONAL"}
    if "I_antenna_rms_A" in inputs or "R_antenna_cold_ohm" in inputs:
        va, pa = take(inputs, {"I_antenna_rms_A": "A", "R_antenna_cold_ohm": "ohm"}, "antenna ohmic")
        out["Q_antenna_ohmic_W"] = va["I_antenna_rms_A"] ** 2 * _nonneg("R_ant", va["R_antenna_cold_ohm"])
        out["provenance"] = merge_provenance(prov, pa)
        if out["Q_antenna_ohmic_W"] > Pdel * (1 + 1e-9):
            out["antenna_ohmic_consistency"] = "INCONSISTENT: I^2 R_cold exceeds P_delivered (check calibration)"
        else:
            out["antenna_ohmic_consistency"] = "CONSISTENT"
    return out


Q_COLL_SPEC = {"I_electron_collected_A": "A", "I_ion_collected_A": "A", "T_e_eV": "eV",
               "V_plasma_V": "V", "V_surface_V": "V"}


def q_collector(inputs):
    """Q_collector: particle heating of a collecting electrode (A9.2; ICD ICP-21 / ICP-43).

    Energy per collected particle (Goebel & Katz 2008, EXT-GOEBEL-KATZ-2008):
      electron: 2 T_e (flux-weighted Maxwellian kinetic energy, Appendix C Eq. C-2; Eq. 7.3-47 / 7.3-61 'each electron
                deposits 2kTe/e to the anode for positive plasma potentials') + max(0, V_surface - V_plasma) when the
                sheath accelerates electrons into the surface (p. 356: heating increases; energy conservation,
                model-derived);
      ion:      T_e / 2 (pre-sheath, Eq. 4.2-10) + max(0, V_plasma - V_surface) (sheath fall, Eq. 4.2-10 / 7.3-45);
    optional surface terms (must be switched explicitly; standard sheath heat-transmission terms, from memory -
    verify against a cited source before use in a closure): + phi_wf per collected electron, + (E_iz - phi_wf) per
    collected ion (neutralization). Secondary-electron cooling is neglected (as Goebel & Katz p. 355 state for
    Eq. 7.3-45), i.e. bounding for the ion term. Currents are particle-current magnitudes (A = e x particles/s),
    never the net terminal current (the split must be measured / registered; P1-IT-42 sign convention applies to
    the terminal record, not to these magnitudes)."""
    v, prov = take(inputs, Q_COLL_SPEC, "Q_collector")
    Ie, Ii = _nonneg("I_electron_collected", v["I_electron_collected_A"]), _nonneg("I_ion_collected", v["I_ion_collected_A"])
    Te = v["T_e_eV"]
    if Te <= 0:
        raise DomainError("T_e must be > 0 eV")
    dV = v["V_surface_V"] - v["V_plasma_V"]
    eps_e = 2.0 * Te + max(0.0, dV)
    eps_i = 0.5 * Te + max(0.0, -dV)
    sw = flag(inputs, "surface_energy_terms", ("INCLUDED", "EXCLUDED"), "Q_collector")
    terms = {"electron_kinetic_W": Ie * eps_e, "ion_kinetic_W": Ii * eps_i}
    if sw == "INCLUDED":
        vs, ps = take(inputs, {"phi_wf_eV": "eV", "E_iz_eV": "eV"}, "Q_collector surface terms")
        terms["electron_work_function_W"] = Ie * vs["phi_wf_eV"]
        terms["ion_neutralization_W"] = Ii * (vs["E_iz_eV"] - vs["phi_wf_eV"])
        prov = merge_provenance(prov, ps)
    return {"eps_electron_eV": eps_e, "eps_ion_eV": eps_i, "terms_W": terms,
            "Q_collector_W": sum(terms.values()), "surface_energy_terms": sw,
            "surface_terms_note": "from memory - verify (not sourced in this lane)" if sw == "INCLUDED" else
            "excluded by explicit switch", "provenance": prov, "status": "COMPUTED_CONDITIONAL"}


Q_PLUME_SPEC = {"I_beam_A": "A", "E_ion_mean_eV": "eV", "alpha_energy_accommodation": "-"}


def q_plume(inputs, interception):
    """Q_plume: plume power intercepted by the ICP assembly (A9.2; ICD ICP-29).
    Q_plume,s = alpha_E * f_int,s * I_beam * E_ion,mean with f_int,s from plume_interception() of the MEASURED angular
    distribution (Faraday-probe CDF). I_beam and E_ion,mean are measured Hall-plume quantities (never a Hall-closure
    prediction). alpha_E: energy accommodation (1 = bound). Charge-exchange / neutral / electron plume terms are
    not included and are listed as omitted."""
    v, prov = take(inputs, Q_PLUME_SPEC, "Q_plume")
    Ib, E = _nonneg("I_beam", v["I_beam_A"]), _nonneg("E_ion_mean", v["E_ion_mean_eV"])
    al = _fraction("alpha_E", v["alpha_energy_accommodation"])
    P = Ib * E
    per = {s: al * f * P for s, f in interception.items() if s != "SPACE"}
    return {"P_ion_beam_W": P, "Q_plume_W_per_surface": per, "Q_plume_W": sum(per.values()),
            "f_escape": interception.get("SPACE"), "omitted_terms": ["charge-exchange ions", "fast neutrals",
                                                                  "plume electrons", "sputtered-atom deposition"],
            "provenance": prov, "status": "COMPUTED_CONDITIONAL"}


def q_hall_to_icp(q_rad_H1_to_icp_W, q_cond_carrier_W, q_plume_W, prov):
    """Q_Hall->ICP = net radiation from H-1 surfaces absorbed by ICP surfaces + carrier conduction into the ICP
    module + intercepted plume power (A9.2 terms; positive = into the ICP assembly)."""
    total = q_rad_H1_to_icp_W + q_cond_carrier_W + q_plume_W
    return {"Q_rad_W": q_rad_H1_to_icp_W, "Q_cond_carrier_W": q_cond_carrier_W, "Q_plume_W": q_plume_W,
            "Q_Hall_to_ICP_W": total, "provenance": prov, "status": "COMPUTED_CONDITIONAL"}


def exchange_between(ids_a, ids_b, area, F, eps, T, T_space):
    """Net radiative power from surface group a to surface group b in a solved enclosure (W), via the
    net-radiation method: sum_{i in a, j in b} A_i F_ij (J_i - J_j)."""
    res = radiosity_solve(sorted(area), area, F, eps, T, T_space)
    J = res["J"]
    return sum(area[i] * F[i][j] * (J[i] - J[j]) for i in ids_a for j in ids_b)


def h1_view_change(vf_with, vf_without, h1_surfaces):
    """ICP-induced change of H-1 radiative view factors: per H-1 surface, F_to_SPACE without / with the ICP and
    the fraction now intercepted by ICP surfaces (A9.2 radiative_view_requirement)."""
    out = {}
    for s in h1_surfaces:
        f0 = vf_without["F"][s]["SPACE"]
        f1 = vf_with["F"][s]["SPACE"]
        icp = sum(v for k, v in vf_with["F"][s].items() if k not in vf_without["F"][s] and k != "SPACE")
        out[s] = {"F_space_without_icp": f0, "F_space_with_icp": f1, "delta_F_space": f1 - f0, "F_to_icp": icp}
    return out


def equivalent_heat_into_h1(vf_with, vf_without, h1_map, eps, T_h1, T_icp, T_space):
    """First-order 'equivalent heat' into each H-1 node from the ICP presence at FIXED temperatures: the reduction
    of the node's net radiative loss (without ICP minus with ICP). h1_map: {surface: node}. Returns W per node.
    Comparable in form (not in validity) with the A9-07 injected-heat allowances (PO / BP); it is a sensitivity
    at given temperatures, not a closure."""
    def net_loss(vf, T):
        ids = vf["surfaces"]
        G, _ = enforce_reciprocity(vf["F"], vf["area_m2"], ids)
        e = {s: eps[s] for s in ids}
        res = radiosity_solve(ids, vf["area_m2"], G, e, T, T_space)
        per = {}
        for s, node in h1_map.items():
            if eps[s] != "RERADIATING":
                per[node] = per.get(node, 0.0) + res["q_W"][s]
        return per
    T0 = {s: T_h1[s] for s in vf_without["surfaces"] if eps[s] != "RERADIATING"}
    T1 = dict(T0)
    T1.update(T_icp)
    a, b = net_loss(vf_without, T0), net_loss(vf_with, T1)
    return {n: a[n] - b[n] for n in a}


# ============================================================================================ H2-5 adapter
H25_BND_ORDER = (("rad_env", "AN"), ("rad_env", "WI"), ("rad_env", "WO"), ("rad_env", "WO"), ("rad_env", "PI"),
                 ("rad_env", "PO"), ("rad_env", "BP"), ("rad_env", "CB"), ("cond_mount", "BP"))


def h25_front_geometry(h25, x, fx):
    """H-1 front-face zone radii and areas exactly as the pinned H2-5 assemble() defines them."""
    L, h, Do = fx["L"], fx["h"], fx["D_out"]
    Di = Do - 2 * h
    tw = x["t_wall_m"]
    Db, Lb = x["D_body_m"], x["L_body_m"]
    vf = h25.slot_view_factors(L, h)
    return {"R_pf": (Di - 2 * tw) / 2, "R_i": Di / 2, "R_o": Do / 2, "R_ow": (Do + 2 * tw) / 2, "R_b": Db / 2,
            "L_b": Lb, "A_an": math.pi / 4 * (Do ** 2 - Di ** 2), "A_WI": math.pi * Di * L, "A_WO": math.pi * Do * L,
            "vf": vf}


def h1_body(g, prefix="H1"):
    """H-1 as a solid coaxial body z in [-L_b, 0] with the H2-5 front-face zones."""
    return Body(prefix, 0.0, g["R_b"], -g["L_b"], 0.0,
                down=[(f"{prefix}.PI_face", 0.0, g["R_pf"]), (f"{prefix}.inner_wall_end", g["R_pf"], g["R_i"]),
                      (f"{prefix}.aperture", g["R_i"], g["R_o"]), (f"{prefix}.outer_wall_end", g["R_o"], g["R_ow"]),
                      (f"{prefix}.PO_face", g["R_ow"], g["R_b"])],
                outer=[(f"{prefix}.PO_lateral", -g["L_b"], 0.0)],
                up=[(f"{prefix}.rear", 0.0, g["R_b"])])


def h25_coupled_network(h25, x, fx, case, finish, P_d, icp_bodies, icp_surface_map, icp_eps, res,
                        icp_nodes=(), icp_fixed=None, icp_loads=None, icp_cond=()):
    """Couple the pinned H2-5 v1 H-1 network (read-only builder module h25) with downstream ICP bodies.

    The H2-5 exterior radiation of the front-facing radiators (AN/WI/WO through the exit aperture, PI face, PO front
    annulus + lateral) is replaced by one gray-diffuse radiosity enclosure containing the H-1 zones and the ICP
    surfaces; SPACE is black at the H2-5 environment temperature of the case. The aperture zone is split into three
    co-located pseudo surfaces (AN / WI / WO) with areas proportional to A_k F_k->exit (H2-5 crossed-string factors)
    and the H2-5 emissivities, so that WITHOUT ICP bodies the network reproduces the H2-5 solve (checked). Absorbed
    environmental loads stay on their nodes (ICP shading of solar/albedo/OLR neglected: conservative for hot cases,
    non-conservative for cold cases - stated). Wall-end rings not modelled by H2-5 are RERADIATING. Other H2-5
    boundaries (WO open back, BP rear, CB, mount) and all internal links are kept unchanged.
    icp_surface_map: {surface_id: node | 'RERADIATING'} for EVERY ICP surface (no default)."""
    loads, links, bnd, km, coil20 = h25.assemble(x, fx, case, finish, P_d)
    if tuple((b[0], b[1]) for b in bnd) != H25_BND_ORDER:
        raise InputError("H2-5 boundary layout differs from the v1 layout this adapter mirrors")
    g = h25_front_geometry(h25, x, fx)
    Tenv = bnd[0][4]
    ean, eBN, em = x["eps_anode"], fx["eps_BN"], x["eps_metal"]
    eps_ext = h25.FINISHES[finish]["eps"]
    A_lat = math.pi * x["D_body_m"] * x["L_body_m"]
    A_opf = math.pi / 4 * (x["D_body_m"] ** 2 - (fx["D_out"] + 2 * x["t_wall_m"]) ** 2)
    # sanity: the PO boundary of H2-5 must equal eps_ext (A_lat + A_opf)
    if abs(bnd[5][2] - eps_ext * (A_lat + A_opf)) > 1e-12:
        raise InputError("PO exterior area does not match the H2-5 definition")
    bodies = [h1_body(g)] + list(icp_bodies)
    vf = view_factors(bodies, res)
    ids = vf["surfaces"]
    for s in ids:
        if not s.startswith("H1.") and s not in icp_surface_map:
            raise MissingInputError([f"surface_map[{s}]"], "ICP surface -> node map")
        if not s.startswith("H1.") and icp_surface_map[s] != "RERADIATING" and s not in icp_eps:
            raise MissingInputError([f"eps[{s}]"], "ICP surface emissivity")
    G, adj = enforce_reciprocity(vf["F"], vf["area_m2"], ids)
    # split the aperture into AN / WI / WO pseudo surfaces
    ap = "H1.aperture"
    A_ap = vf["area_m2"][ap]
    vfs = g["vf"]
    share = {"AN": g["A_an"] * vfs["F_anode_to_exit"], "WI": g["A_WI"] * vfs["F_wall_to_exit"],
             "WO": g["A_WO"] * vfs["F_wall_to_exit"]}
    tot = sum(share.values())
    w = {k: v / tot for k, v in share.items()}
    new_ids = [s for s in ids if s != ap] + [f"{ap}.{k}" for k in w]
    area = {s: vf["area_m2"][s] for s in ids if s != ap}
    F = {}
    for s in ids:
        if s == ap:
            continue
        F[s] = {t: G[s][t] for t in ids if t != ap}
        for k in w:
            F[s][f"{ap}.{k}"] = G[s][ap] * w[k]
        F[s]["SPACE"] = G[s]["SPACE"]
    for k in w:
        sid = f"{ap}.{k}"
        area[sid] = A_ap * w[k]
        F[sid] = {t: G[ap][t] for t in ids if t != ap}
        for k2 in w:
            F[sid][f"{ap}.{k2}"] = G[ap][ap] * w[k2]
        F[sid]["SPACE"] = G[ap]["SPACE"]
    eps = {"H1.PI_face": em, "H1.PO_face": eps_ext, "H1.PO_lateral": eps_ext, "H1.inner_wall_end": "RERADIATING",
           "H1.outer_wall_end": "RERADIATING", "H1.rear": "RERADIATING",
           f"{ap}.AN": ean, f"{ap}.WI": eBN, f"{ap}.WO": eBN}
    node = {"H1.PI_face": "PI", "H1.PO_face": "PO", "H1.PO_lateral": "PO", "H1.inner_wall_end": "RERADIATING",
            "H1.outer_wall_end": "RERADIATING", "H1.rear": "RERADIATING",
            f"{ap}.AN": "AN", f"{ap}.WI": "WI", f"{ap}.WO": "WO"}
    for s in ids:
        if not s.startswith("H1."):
            node[s] = icp_surface_map[s]
            eps[s] = "RERADIATING" if icp_surface_map[s] == "RERADIATING" else icp_eps[s]
    if vf["F"]["H1.rear"]["SPACE"] < 1 - 1e-9:
        raise GeometryError("H-1 rear face sees an ICP surface: geometry outside the adapter's domain")
    enc = Enclosure(new_ids, area, F, eps, node, Tenv)
    # H2-5 internal links and coil I^2R(T), evaluated with the pinned module's own property functions
    def internal(T):
        into = {}
        gen = 0.0

        def add(n, Q):
            into[n] = into.get(n, 0.0) + Q
        for nd, p20 in coil20.items():
            if p20 > 0.0:
                pc = p20 * h25.cu_factor_vs_20C(T[nd])
                add(nd, pc)
                gen += pc
        for lk in links:
            typ, a, b = lk[0], lk[1], lk[2]
            if typ == "cond":
                Q = lk[3] * (T[a] - T[b])
            elif typ == "rad":
                Q = h25.SIGMA_SB * (T[a] ** 4 - T[b] ** 4) / lk[3]
            else:
                Gk = h25.fe_k(0.5 * (T[a] + T[b]), km) * lk[3]
                if typ == "condFe_contact":
                    Gk = 1 / (1 / Gk + 1 / lk[4])
                Q = Gk * (T[a] - T[b])
            add(a, -Q)
            add(b, Q)
        return into, 0.0, gen
    env = [(bnd[3][1], bnd[3][2], bnd[3][3], bnd[3][4]), (bnd[6][1], bnd[6][2], bnd[6][3], bnd[6][4]),
           (bnd[7][1], bnd[7][2], bnd[7][3], bnd[7][4])]
    fixed = {"MOUNT": bnd[8][3]}
    fixed.update(icp_fixed or {})
    all_loads = dict(loads)
    # absorbed environmental loads of the replaced boundaries stay on their nodes
    for bd in (bnd[0], bnd[1], bnd[2], bnd[4], bnd[5]):
        all_loads[bd[1]] = all_loads.get(bd[1], 0.0) + bd[3]
    for n, Q in (icp_loads or {}).items():
        all_loads[n] = all_loads.get(n, 0.0) + Q
    net = Network(unknown=list(h25.NODES) + list(icp_nodes), fixed=fixed, loads=all_loads,
                  cond=[("BP", "MOUNT", bnd[8][2])] + list(icp_cond), env_rad=env, enclosures=[enc],
                  callables=[internal])
    return net, {"view_factors": vf, "reciprocity_adjustment_max": adj, "aperture_weights": w, "geometry": g}

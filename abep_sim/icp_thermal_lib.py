"""ICP / H-1 thermal-geometry helpers used by the F6 ICP geometry synthesis (A9.22 layer separation).

Verbatim copy of the subset of docs/experiments/hall_icp/p3_coupled_thermal/p3_thermal_lib.py that
abep_sim/design/icp_geometry_synthesis.py needs (view_factors, h1_body, Body, plume_interception_record,
q_collector, q, MissingInputError, SYN, vf_annulus_to_parallel_coaxial_annulus and their top-level dependencies),
copied from the file with sha256 99aaf0052b26a4e57adfcb9467465a558ad291752154bfaa2534c74fa75715e1. Before A9.22 the design layer imported that file by path; it now imports this
library. The docs file is unchanged (it is sha-pinned by immutable records); tests/test_design_layer_separation.py
checks that every function / class / constant here is source-identical to the docs original.

Pure functions and data structures only: no file I/O, no global state.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

SOURCE_REL = "docs/experiments/hall_icp/p3_coupled_thermal/p3_thermal_lib.py"
SOURCE_SHA256 = "99aaf0052b26a4e57adfcb9467465a558ad291752154bfaa2534c74fa75715e1"


SYN = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE"


EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "published analog", SYN)


TBD_PREFIXES = ("TBD", "PENDING", "TBD_AFTER_EVIDENCE", "TBD_OWNER", "TBD_AFTER_IMPEDANCE_MAP")


REFUSED_PREFIXES = ("REFUSED", "NOT_AVAILABLE")


class InputError(ValueError):
    """Malformed input record (units, evidence class, sign, range)."""


class MissingInputError(InputError):
    """A required input is absent, None or TBD: the calculation refuses (INCOMPLETE_EVIDENCE)."""

    def __init__(self, missing, context=""):
        self.missing = sorted(set(missing))
        super().__init__(f"{context}: missing / TBD inputs {self.missing}")


class RefusedInputError(MissingInputError):
    """An upstream package REFUSED the value (e.g. P2 line/match loss unverified): the calculation refuses too
    (INCOMPLETE_EVIDENCE); the refused value is never reconstructed from other inputs (A9.6 sec. 14)."""


class SyntheticMixError(InputError):
    """SYNTHETIC_TEST_DATA_NOT_EVIDENCE records mixed with evidence records (refused, A9.6 sec. 14)."""


class GeometryError(ValueError):
    """Geometry outside the engine's domain (overlap, non-tiling zones, non-positive dimensions)."""


class DomainError(ValueError):
    """Input outside a formula's stated domain (OUT_OF_DOMAIN, distinct from a failure)."""


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
    missing, refused, vals, classes = [], [], {}, {}
    for key, units in spec.items():
        rec = inputs.get(key) if isinstance(inputs, dict) else None
        if isinstance(rec, dict) and isinstance(rec.get("value"), str) and \
                rec["value"].strip().upper().startswith(REFUSED_PREFIXES):
            refused.append(key)
            continue
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
    if refused:
        raise RefusedInputError(refused + missing, context + " (REFUSED upstream: " + ", ".join(sorted(refused)) + ")")
    if missing:
        raise MissingInputError(missing, context)
    return vals, provenance(classes)


def _numbers(vals, context):
    """Scalar real numbers only (a string, list or bound object is not a measured scalar here)."""
    for k, v in vals.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise InputError(f"{context}: {k} must be a real number, got {type(v).__name__}")
    return vals


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
    distribution about +z (a model assumption, stated; the real distribution is measured). Returns the bare
    geometric fractions; q_plume() accepts only an interception RECORD (plume_interception_record) that carries the
    provenance of the angular distribution."""
    check_geometry(bodies)
    zl = {z[0]: z for z in source_body.zones()["down"]}
    if source_zone not in zl:
        raise GeometryError(f"{source_zone} is not a downstream-face zone of {source_body.name}")
    _, a, c = zl[source_zone]
    dirs = plume_directions(cdf_table, res[1], res[2])
    o, d, w = emit_zone(source_body, "down", a, c, res, directions=dirs)
    return trace(o, d, w, bodies, 1e-9 * _scale(bodies))


PLUME_CDF_UNITS = "deg; -"


def plume_interception_record(bodies, source_body, source_zone, cdf_record, res):
    """Interception with provenance (consolidated verification TH-02): cdf_record is a quantity record
    {'value': [(theta_deg, C)...], 'units': 'deg; -', 'evidence_class', 'source'} (a measured Faraday-probe CDF is
    'measured'; a geometric test cone is 'assumed' and gives a CONDITIONAL result). Returns
    {'fractions', 'evidence_class', 'source', 'units'} for q_plume()."""
    if not isinstance(cdf_record, dict):
        raise InputError("plume angular distribution must be a quantity record {value, units, evidence_class, source} "
                         "(a bare table has no provenance)")
    v, _ = take({"angular_distribution": cdf_record}, {"angular_distribution": PLUME_CDF_UNITS}, "plume CDF")
    table = [tuple(p) for p in v["angular_distribution"]]
    f = plume_interception(bodies, source_body, source_zone, table, res)
    return {"fractions": f, "evidence_class": cdf_record["evidence_class"], "source": cdf_record["source"],
            "units": "-"}


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
    _numbers(v, "Q_collector")
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
        _numbers(vs, "Q_collector surface terms")
        for k in ("phi_wf_eV", "E_iz_eV"):             # SW-07: a work function / ionization energy is positive
            if vs[k] <= 0:
                raise DomainError(f"Q_collector: {k} must be > 0 eV (got {vs[k]})")
        terms["electron_work_function_W"] = Ie * vs["phi_wf_eV"]
        terms["ion_neutralization_W"] = Ii * (vs["E_iz_eV"] - vs["phi_wf_eV"])
        prov = merge_provenance(prov, ps)
    return {"eps_electron_eV": eps_e, "eps_ion_eV": eps_i, "terms_W": terms,
            "Q_collector_W": sum(terms.values()), "surface_energy_terms": sw,
            "surface_terms_note": "from memory - verify (not sourced in this lane)" if sw == "INCLUDED" else
            "excluded by explicit switch", "provenance": prov, "status": "COMPUTED_CONDITIONAL"}


def h1_body(g, prefix="H1"):
    """H-1 as a solid coaxial body z in [-L_b, 0] with the H2-5 front-face zones."""
    return Body(prefix, 0.0, g["R_b"], -g["L_b"], 0.0,
                down=[(f"{prefix}.PI_face", 0.0, g["R_pf"]), (f"{prefix}.inner_wall_end", g["R_pf"], g["R_i"]),
                      (f"{prefix}.aperture", g["R_i"], g["R_o"]), (f"{prefix}.outer_wall_end", g["R_o"], g["R_ow"]),
                      (f"{prefix}.PO_face", g["R_ow"], g["R_b"])],
                outer=[(f"{prefix}.PO_lateral", -g["L_b"], 0.0)],
                up=[(f"{prefix}.rear", 0.0, g["R_b"])])


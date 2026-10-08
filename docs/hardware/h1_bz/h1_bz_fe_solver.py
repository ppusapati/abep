"""Axisymmetric nonlinear magnetostatic FE for the H-1 / MC-1 electromagnet (lane L-H1-BZ, A9.38 P3).

Solver: scikit-fem (pinned version, PyPI), P2 Lagrange triangles on a tensor-product (r, z) grid whose lines contain every
material boundary, the channel centreline r = d_mean / 2 and the anode / exit planes. Unknown: the azimuthal vector
potential A_phi (Wb/m). Weak form (per radian; the 2 pi cancels):

    int nu [ (dA/dr + A/r)(dv/dr + v/r) + dA/dz dv/dz ] r dr dz = int J_phi v r dr dz

with A = 0 on the axis and on the far boundary (or a natural boundary where a verification case says so). B_r = -dA/dz,
B_z = dA/dr + A/r. Iron is nonlinear: nu = H(|B|) / |B| from the B-H data (bh_curves_v1.json), piecewise linear in
(H, B), with the saturated slope mu0 beyond the last point. The nonlinear system is solved by damped Newton iteration
(exact tangent, backtracking line search); convergence is reported, a non-converged solve is MODEL_ERROR (never returned
as a field).

This is a design-analysis tool for hardware evidence (FE-DERIVED field), not a production simulator component: its output
is versioned evidence data (CSV + JSON) that HallThruster.jl reads through the existing bridge.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse.linalg as spla
from scipy.special import ellipe, ellipk
import skfem
from skfem import Basis, BilinearForm, ElementTriP2, LinearForm, MeshTri

MU0 = 4e-7 * math.pi
NU0 = 1.0 / MU0
SOLVER_ID = f"scikit-fem {skfem.__version__} (P2 Lagrange, axisymmetric A_phi, damped Newton, SuperLU / LU-preconditioned CG)"


# ----------------------------------------------------------------------------------------------------------------- B-H
class BH:
    """Monotone normal magnetization curve B(H) given as [[H, B], ...] starting at (0, 0)."""

    def __init__(self, points, name=""):
        p = np.asarray(points, float)
        if p[0, 0] != 0.0 or p[0, 1] != 0.0:
            raise ValueError(f"B-H {name}: must start at (0, 0)")
        if np.any(np.diff(p[:, 0]) <= 0) or np.any(np.diff(p[:, 1]) <= 0):
            raise ValueError(f"B-H {name}: H and B must be strictly increasing")
        self.H, self.B, self.name = p[:, 0], p[:, 1], name

    def h_of_b(self, b):
        b = np.asarray(b, float)
        h = np.interp(b, self.B, self.H)
        over = b > self.B[-1]
        h = np.where(over, self.H[-1] + (b - self.B[-1]) / MU0, h)
        return h

    def nu(self, b):
        b = np.abs(np.asarray(b, float))
        nu0 = self.H[1] / self.B[1]                       # initial (secant) reluctivity of the first segment
        with np.errstate(divide="ignore", invalid="ignore"):
            v = np.where(b > 1e-12, self.h_of_b(b) / np.maximum(b, 1e-300), nu0)
        return v

    def dhdb(self, b):
        b = np.abs(np.asarray(b, float))
        slopes = np.diff(self.H) / np.diff(self.B)
        i = np.clip(np.searchsorted(self.B, b, side="right") - 1, 0, len(slopes) - 1)
        return np.where(b >= self.B[-1], NU0, slopes[i])

    def nu_dnu(self, b):
        """nu(|B|) and d nu / d(|B|^2) = (H'(B) - nu) / (2 B^2) (0 on the first, linear segment)."""
        b = np.abs(np.asarray(b, float))
        v = self.nu(b)
        with np.errstate(divide="ignore", invalid="ignore"):
            d = np.where(b > 1e-9, (self.dhdb(b) - v) / (2.0 * np.maximum(b, 1e-300) ** 2), 0.0)
        return v, d


# ------------------------------------------------------------------------------------------------------------ geometry
@dataclass
class Rect:
    r0: float
    r1: float
    z0: float
    z1: float
    mat: str              # 'air', 'coil:<name>', or an iron key ('hiperco' | 'iron')
    label: str = ""

    def contains(self, r, z):
        return (r >= self.r0) & (r <= self.r1) & (z >= self.z0) & (z <= self.z1)


@dataclass
class Problem:
    rects: list                              # later rectangles override earlier ones
    coil_NI: dict                            # coil name -> ampere-turns (A)
    box_r: float
    box_z0: float
    box_z1: float
    h_fine: float                            # grid spacing inside the fine region (m)
    fine_r: float                            # fine region r <= fine_r
    fine_z: tuple                            # fine region z0..z1
    mid_z1: float | None = None              # optional medium region fine_z[1]..mid_z1 at mid_factor * h_fine
    mid_factor: float = 2.0
    growth: float = 1.25
    h_far: float = 0.02
    extra_r: list = field(default_factory=list)
    extra_z: list = field(default_factory=list)
    dirichlet: str = "axis+far"              # 'axis+far' | 'axis'  (axis only: natural BC elsewhere)


def _axis_lines(breaks, lo, hi, size_fn, growth, h_far):
    """1-D grid: every break point is a line; spacing from size_fn(mid) between breaks, grown geometrically outward."""
    b = sorted(set([lo, hi] + [x for x in breaks if lo <= x <= hi]))
    lines = [b[0]]
    for a, c in zip(b, b[1:]):
        L = c - a
        s = size_fn(0.5 * (a + c))
        if s is None:  # graded (outside the fine/medium region): geometric from the side nearer the fine region
            lines.extend(_graded(a, c, size_fn, growth, h_far)[1:])
        else:
            n = max(1, int(math.ceil(L / s - 1e-9)))
            lines.extend(list(a + L * np.arange(1, n + 1) / n))
    out = np.array(sorted(set(np.round(lines, 12))))
    return out


def _graded(a, c, size_fn, growth, h_far):
    sa, sc = size_fn(a - 1e-12) or size_fn(a + 1e-12), size_fn(c + 1e-12) or size_fn(c - 1e-12)
    # start from the end that touches a sized region
    if sa is not None and (sc is None or sa <= sc):
        pts, x, h = [a], a, sa
        while x + h * growth < c - 1e-12:
            h = min(h * growth, h_far)
            x += h
            pts.append(x)
        pts.append(c)
        return pts
    if sc is not None:
        pts, x, h = [c], c, sc
        while x - h * growth > a + 1e-12:
            h = min(h * growth, h_far)
            x -= h
            pts.append(x)
        pts.append(a)
        return sorted(pts)
    n = max(1, int(math.ceil((c - a) / h_far)))
    return list(a + (c - a) * np.arange(0, n + 1) / n)


def build_mesh(pb: Problem):
    br = [0.0, pb.box_r, pb.fine_r] + pb.extra_r
    bz = [pb.box_z0, pb.box_z1, pb.fine_z[0], pb.fine_z[1]] + pb.extra_z
    if pb.mid_z1 is not None:
        bz.append(pb.mid_z1)
    for q in pb.rects:
        br += [q.r0, q.r1]
        bz += [q.z0, q.z1]

    def sr(x):
        return pb.h_fine if x <= pb.fine_r + 1e-12 else None

    def sz(x):
        if pb.fine_z[0] - 1e-12 <= x <= pb.fine_z[1] + 1e-12:
            return pb.h_fine
        if pb.mid_z1 is not None and pb.fine_z[1] <= x <= pb.mid_z1 + 1e-12:
            return pb.h_fine * pb.mid_factor
        return None

    r = _axis_lines(br, 0.0, pb.box_r, sr, pb.growth, pb.h_far)
    z = _axis_lines(bz, pb.box_z0, pb.box_z1, sz, pb.growth, pb.h_far)
    return MeshTri.init_tensor(r, z), r, z


# -------------------------------------------------------------------------------------------------------------- solver
@dataclass
class Solution:
    status: str
    A: np.ndarray | None
    basis: object
    mesh: object
    iterations: int
    residual: float
    dA_rel: float
    n_dofs: int
    note: str = ""


def _mat_per_element(mesh, rects):
    c = mesh.p[:, mesh.t].mean(axis=1)
    mat = np.array(["air"] * mesh.t.shape[1], dtype=object)
    for q in rects:
        mat[q.contains(c[0], c[1])] = q.mat
    return mat


@BilinearForm
def _a(u, v, w):
    r = w.x[0]
    return w["nu"] * ((u.grad[0] + u / r) * (v.grad[0] + v / r) + u.grad[1] * v.grad[1]) * r


@BilinearForm
def _jac(u, v, w):
    """Newton tangent: nu (curl u . curl v) + 2 dnu/d(B^2) (B . curl u)(B . curl v), curl u = (-du/dz, du/dr + u/r)."""
    r = w.x[0]
    cur, cuz = -u.grad[1], u.grad[0] + u / r
    cvr, cvz = -v.grad[1], v.grad[0] + v / r
    return (w["nu"] * (cur * cvr + cuz * cvz)
            + 2.0 * w["dnu"] * (w["Br"] * cur + w["Bz"] * cuz) * (w["Br"] * cvr + w["Bz"] * cvz)) * r


@LinearForm
def _res(v, w):
    r = w.x[0]
    return (w["nu"] * (w["Br"] * (-v.grad[1]) + w["Bz"] * (v.grad[0] + v / r)) - w["J"] * v) * r


@LinearForm
def _l(v, w):
    return w["J"] * v * w.x[0]


def setup(pb: Problem, mesh_cache=None):
    if mesh_cache is not None and "mesh" in mesh_cache:
        return mesh_cache["mesh"], mesh_cache["basis"]
    mesh, _, _ = build_mesh(pb)
    basis = Basis(mesh, ElementTriP2(), intorder=4)
    if mesh_cache is not None:
        mesh_cache.update(mesh=mesh, basis=basis)
    return mesh, basis


def solve_problem(pb: Problem, bh: dict, *, tol_res=1e-7, tol_step=1e-10, max_it=60, mesh_cache=None, A0=None):
    """Damped Newton on the nonlinear magnetostatic equations. bh maps iron keys ('hiperco', 'iron') to BH objects.
    Converged when the relative residual ||R|| / ||F|| < tol_res AND the last relative Newton step < tol_step
    (prereg v2: the v1 values 1e-9 / 1e-9 sit below the double-precision residual floor of iron/air problems).
    Returns Solution (status OK | MODEL_ERROR); a non-converged state is never returned as a field."""
    mesh, basis = setup(pb, mesh_cache)
    mat = _mat_per_element(mesh, pb.rects)
    nq = basis.X.shape[1]
    J = np.zeros(mesh.t.shape[1])
    for q in pb.rects:
        if q.mat.startswith("coil:"):
            name = q.mat.split(":", 1)[1]
            area = (q.r1 - q.r0) * (q.z1 - q.z0)
            J[mat == q.mat] = pb.coil_NI.get(name, 0.0) / area
    Jq = np.repeat(J[:, None], nq, axis=1)
    iron_keys = sorted(set(m for m in mat if m in bh))
    unknown = sorted(set(m for m in mat if m != "air" and not m.startswith("coil:") and m not in bh))
    if unknown:
        raise ValueError(f"no B-H curve for materials {unknown}")
    is_iron = {k: (mat == k) for k in iron_keys}
    if pb.dirichlet == "axis+far":
        D = basis.get_dofs(lambda x: (x[0] < 1e-12) | (x[0] > pb.box_r - 1e-12) | (x[1] < pb.box_z0 + 1e-12)
                           | (x[1] > pb.box_z1 - 1e-12)).all()
    elif pb.dirichlet == "axis":
        D = basis.get_dofs(lambda x: x[0] < 1e-12).all()
    else:
        raise ValueError(pb.dirichlet)
    free = np.setdiff1d(np.arange(basis.N), D)
    F = _l.assemble(basis, J=Jq)
    nF = np.linalg.norm(F[free])
    if nF == 0.0:
        return Solution("OK", np.zeros(basis.N), basis, mesh, 0, 0.0, 0.0, basis.N, "zero source")

    def state(A):
        f = basis.interpolate(A)
        r = basis.mapping.F(basis.X)[0]
        br, bz = -f.grad[1], f.grad[0] + f.value / r
        bm = np.sqrt(br ** 2 + bz ** 2)
        nu = np.full(bm.shape, NU0)
        dnu = np.zeros(bm.shape)
        for k in iron_keys:
            m = is_iron[k]
            nu[m], dnu[m] = bh[k].nu_dnu(bm[m])
        return br, bz, nu, dnu

    def residual(A):
        br, bz, nu, dnu = state(A)
        R = _res.assemble(basis, nu=nu, Br=br, Bz=bz, J=Jq)
        return R, (br, bz, nu, dnu)

    A = np.zeros(basis.N) if A0 is None else np.array(A0, float)
    A[D] = 0.0
    R, st = residual(A)
    rn = np.linalg.norm(R[free]) / nF
    lu, it, step = None, 0, float("inf")
    for it in range(1, max_it + 1):
        br, bz, nu, dnu = st
        KT = _jac.assemble(basis, nu=nu, dnu=dnu, Br=br, Bz=bz).tocsc()[free][:, free]
        rhs = -R[free]
        delta = None
        if lu is not None:
            M = spla.LinearOperator(KT.shape, matvec=lu.solve)
            delta, info = spla.cg(KT, rhs, M=M, rtol=1e-12, atol=0.0, maxiter=40)
            if info != 0:
                delta = None
        if delta is None:
            lu = spla.splu(KT, permc_spec="COLAMD")
            delta = lu.solve(rhs)
        full = np.zeros(basis.N)
        full[free] = delta
        alpha = 1.0
        for _ in range(12):
            A_try = A + alpha * full
            R_try, st_try = residual(A_try)
            rn_try = np.linalg.norm(R_try[free]) / nF
            if rn_try <= (1.0 - 1e-4 * alpha) * rn or rn_try < tol_res:
                break
            alpha *= 0.5
        else:
            return Solution("MODEL_ERROR", None, basis, mesh, it, rn, step, basis.N, "Newton line search failed")
        step = alpha * np.linalg.norm(delta) / max(np.linalg.norm(A_try[free]), 1e-300)
        A, R, st, rn = A_try, R_try, st_try, rn_try
        if rn < tol_res and step < tol_step:
            break
        if not iron_keys and rn < tol_res:
            break
    else:
        return Solution("MODEL_ERROR", None, basis, mesh, it, rn, step, basis.N,
                        f"Newton not converged in {max_it} iterations (res {rn:.3g}, step {step:.3g})")
    if not np.all(np.isfinite(A)):
        return Solution("MODEL_ERROR", None, basis, mesh, it, rn, step, basis.N, "non-finite solution")
    return Solution("OK", A, basis, mesh, it, rn, step, basis.N)


def _bmag_q(basis, A):
    f = basis.interpolate(A)
    r = basis.mapping.F(basis.X)[0]
    br = -f.grad[1]
    bz = f.grad[0] + f.value / r
    return np.sqrt(br ** 2 + bz ** 2)


def field_at(sol: Solution, r, z):
    """B_r, B_z, A at points (r, z) (m). Gradient evaluated in the element found by the element finder; on a z-aligned
    grid line B_r = -dA/dz is the tangential derivative of the continuous A and is single-valued."""
    basis = sol.basis
    x = np.vstack([np.asarray(r, float).ravel(), np.asarray(z, float).ravel()])
    cells = basis.mesh.element_finder(mapping=basis.mapping)(*x)
    pts = basis.mapping.invF(x[:, :, np.newaxis], tind=cells)
    val = np.zeros(x.shape[1])
    gr = np.zeros(x.shape[1])
    gz = np.zeros(x.shape[1])
    for k in range(basis.Nbfun):
        phi = basis.elem.gbasis(basis.mapping, pts, k, tind=cells)[0]
        coef = sol.A[basis.element_dofs[k, cells]]
        val += coef * phi.value[:, 0]
        gr += coef * phi.grad[0][:, 0]
        gz += coef * phi.grad[1][:, 0]
    rr = x[0]
    with np.errstate(divide="ignore", invalid="ignore"):
        bz = np.where(rr > 0, gr + val / np.where(rr > 0, rr, 1.0), 2.0 * gr)
    return -gz, bz, val


def iron_bmax(sol: Solution, pb: Problem, bh: dict):
    """max |B| per iron material over the quadrature points (saturation check)."""
    mat = _mat_per_element(sol.mesh, pb.rects)
    Bq = _bmag_q(sol.basis, sol.A)
    out = {}
    for k in bh:
        m = mat == k
        if m.any():
            out[k] = float(Bq[m].max())
    return out


# ----------------------------------------------------------------------------------------------- analytic references
def loop_field(a, z0, I, r, z):
    """Exact field of a filamentary circular loop (radius a at z0, current I) at (r, z): (B_r, B_z).
    Standard elliptic-integral form (e.g. Smythe, Static and Dynamic Electricity; verify): with zeta = z - z0,
    m = 4 a r / ((a + r)^2 + zeta^2),
      B_z = mu0 I / (2 pi sqrt((a+r)^2+zeta^2)) [K(m) + (a^2 - r^2 - zeta^2) / ((a-r)^2 + zeta^2) E(m)]
      B_r = mu0 I zeta / (2 pi r sqrt((a+r)^2+zeta^2)) [-K(m) + (a^2 + r^2 + zeta^2) / ((a-r)^2 + zeta^2) E(m)]
    (self-checked against the on-axis closed form in the verification record)."""
    r = np.asarray(r, float)
    z = np.asarray(z, float)
    zeta = z - z0
    s = np.sqrt((a + r) ** 2 + zeta ** 2)
    m = 4 * a * r / s ** 2
    K, E = ellipk(m), ellipe(m)
    q = (a - r) ** 2 + zeta ** 2
    bz = MU0 * I / (2 * np.pi * s) * (K + (a * a - r * r - zeta ** 2) / q * E)
    with np.errstate(divide="ignore", invalid="ignore"):
        br = np.where(r > 0, MU0 * I * zeta / (2 * np.pi * np.where(r > 0, r, 1.0) * s)
                      * (-K + (a * a + r * r + zeta ** 2) / q * E), 0.0)
    return br, bz


def coil_field_quadrature(r0, r1, z0, z1, NI, r, z, n=8):
    """Field of a uniform rectangular-section coil by Gauss-Legendre quadrature of loop_field over the section."""
    g, w = np.polynomial.legendre.leggauss(n)
    br = np.zeros_like(np.asarray(r, float))
    bz = np.zeros_like(br)
    J = NI / ((r1 - r0) * (z1 - z0))
    for gi, wi in zip(g, w):
        a = 0.5 * (r0 + r1) + 0.5 * (r1 - r0) * gi
        for gj, wj in zip(g, w):
            zz = 0.5 * (z0 + z1) + 0.5 * (z1 - z0) * gj
            dI = J * wi * wj * 0.25 * (r1 - r0) * (z1 - z0)
            b1, b2 = loop_field(a, zz, dI, r, z)
            br += b1
            bz += b2
    return br, bz


def thick_solenoid_axis(r1, r2, z1, z2, NI, z):
    """Exact on-axis B_z of a uniform rectangular-section coil (r1..r2, z1..z2):
    B = mu0 J / 2 [x2 ln((r2 + sqrt(r2^2 + x2^2)) / (r1 + sqrt(r1^2 + x2^2))) - x1 ln(...x1)], x = z_end - z."""
    J = NI / ((r2 - r1) * (z2 - z1))
    z = np.asarray(z, float)

    def f(x):
        return x * np.log((r2 + np.sqrt(r2 ** 2 + x ** 2)) / (r1 + np.sqrt(r1 ** 2 + x ** 2)))

    return MU0 * J / 2 * (f(z2 - z) - f(z1 - z))

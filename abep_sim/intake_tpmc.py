"""Test-particle Monte-Carlo (TPMC) intake model — free-molecular (Phase 1, items 2, 3, 4, 5, 36).

Geometry: a honeycomb of parallel circular channels (diameter d, length L, open-area fraction phi)
filling a ram aperture of area A, opening into a plenum. Kn >> 1 at 180-230 km (mean free path
hundreds of metres), so molecules move ballistically and interact only with walls -> TPMC is the
correct physics at this level; DSMC is needed only inside the compressed plenum/compressor.

Gas-surface interaction: per wall hit, with probability alpha the molecule is re-emitted diffusely
(cosine law at wall temperature T_w, full accommodation); otherwise specularly. alpha is the
accommodation-like "surface state" the rest of the simulator uses (0 fresh/specular .. 1 aged/diffuse).
A CLL-type model with separate normal/tangential accommodation is available via (alpha_n, alpha_t).

Outputs per geometry and incidence angle theta:
  eta_c      collection efficiency  = collected flux / incident free-stream flux on A
  C_D        drag coefficient on A  = 2 F_z / (rho V^2 A), F_z from momentum exchange of every particle
  K_back     Clausing transmission of the channel array for thermal molecules coming back from the plenum
  CR_passive from flux balance  n_p / n_inf = eta_c V / ((c_bar/4) phi K_back)

Momentum accounting (per unit incident flux):
  particles that end collected: transfer their full incoming momentum (absorbed into the system)
  particles that backscatter: transfer incoming - outgoing momentum
  front face (solid fraction 1-phi): diffuse re-emission, momentum = incoming + thermal emission term
"""
from __future__ import annotations
import math
import numbers
from dataclasses import dataclass
import numpy as np
from .constants import K_B, AMU


@dataclass
class IntakeGeometry:
    area_m2: float = 0.5           # ram aperture
    d_mm: float = 10.0             # channel diameter
    L_over_d: float = 10.0         # channel length / diameter
    phi: float = 0.85              # open-area fraction of the honeycomb
    T_wall_K: float = 350.0
    wall_thickness_mm: float = 0.15
    wall_density_kg_m3: float = 2700.0   # Al
    coating_thickness_um: float = 2.0
    coating_density_kg_m3: float = 2200.0  # SiOx / alumina class
    support_mass_frac: float = 0.35  # brackets, frame, attachment as fraction of honeycomb mass
    filter: bool = False
    filter_open_frac: float = 0.7
    filter_transmission: float = 0.6   # thermal Clausing factor of the filter element
    filter_mass_per_m2: float = 0.8


# --- input validation (owner decision A9.9 S2.5: MCC-05 / MCC-06 / MCC-07) -----------------------------------------
# Every check runs before any particle is sampled or traced (and before the caller's RNG stream is consumed). Invalid
# input raises ValueError explicitly; nothing is clipped, coerced or silently replaced by a default model.
SCATTERING_MODELS = ("maxwell", "cll")      # the only admitted wall-scattering kernels (explicitly selected, recorded)


def _check_scattering(scattering) -> str:
    """MCC-06: an unrecognised wall-scattering model is an invalid configuration (never a silent Maxwell fallback)."""
    if not isinstance(scattering, str) or scattering not in SCATTERING_MODELS:
        raise ValueError(f"intake_tpmc: unknown wall-scattering model {scattering!r}; admitted models are "
                         f"{SCATTERING_MODELS} (exact, case-sensitive; no fallback)")
    return scattering


def _check_hit_budget(name: str, value) -> int:
    """MCC-05: hit budgets must be positive integers (a budget < 1 would never advance the trace loop)."""
    if isinstance(value, bool) or not isinstance(value, numbers.Integral) or int(value) < 1:
        raise ValueError(f"intake_tpmc: {name} must be a positive integer (>= 1), got {value!r}")
    return int(value)


def _check_unit_interval(name: str, value) -> float:
    """MCC-07: accommodation coefficients must be finite and inside [0, 1] (rejected, never clipped)."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"intake_tpmc: {name} must be a finite real number in [0, 1], got {value!r}")
    x = float(value)
    if not math.isfinite(x) or x < 0.0 or x > 1.0:
        raise ValueError(f"intake_tpmc: {name} must be finite and inside [0, 1], got {value!r}")
    return x


def _check_accommodation(scattering: str, alpha, alpha_n=None, alpha_t=None):
    """Validate the accommodation inputs for the selected kernel. Maxwell: alpha is the diffuse fraction (a
    probability). CLL: alpha_n / alpha_t (each defaulting to alpha when None, as before) are the CLL coefficients."""
    if scattering == "cll":
        a_n = _check_unit_interval("CLL alpha_n" if alpha_n is not None else "CLL alpha (used as alpha_n)",
                                   alpha if alpha_n is None else alpha_n)
        a_t = _check_unit_interval("CLL alpha_t" if alpha_t is not None else "CLL alpha (used as alpha_t)",
                                   alpha if alpha_t is None else alpha_t)
        return a_n, a_t
    _check_unit_interval("Maxwell alpha (diffuse fraction)", alpha)
    return None, None


def _drifting_maxwellian(rng, n, V, theta, T, m):
    """Incoming molecular velocities in the channel frame (z along channel axis, into the intake)."""
    vth = math.sqrt(K_B * T / m)
    v = rng.normal(0.0, vth, size=(n, 3))
    v[:, 2] += V * math.cos(theta)
    v[:, 0] += V * math.sin(theta)
    return v


def _flux_weighted_entry(rng, n, V, theta, T, m):
    """Sample molecules that actually cross the aperture plane (flux-weighted: weight ∝ v_z>0)."""
    v = _drifting_maxwellian(rng, 3 * n, V, theta, T, m)
    v = v[v[:, 2] > 0]
    w = v[:, 2] / v[:, 2].sum()
    idx = rng.choice(len(v), size=n, p=w)
    return v[idx]


def _diffuse(rng, n, T_w, m, normal):
    """Cosine-law re-emission at T_w about unit `normal` (n,3)."""
    vth = math.sqrt(K_B * T_w / m)
    # normal component: Rayleigh-like (flux-weighted), tangential: Maxwellian
    vn = vth * np.sqrt(-2.0 * np.log(rng.uniform(1e-12, 1.0, n)))
    vt1 = rng.normal(0, vth, n); vt2 = rng.normal(0, vth, n)
    # build tangent basis
    t1 = np.cross(normal, np.array([0, 0, 1.0]))
    bad = np.linalg.norm(t1, axis=1) < 1e-9
    t1[bad] = np.cross(normal[bad], np.array([1.0, 0, 0]))
    t1 /= np.linalg.norm(t1, axis=1)[:, None]
    t2 = np.cross(normal, t1)
    return vn[:, None] * normal + vt1[:, None] * t1 + vt2[:, None] * t2


def _cll(rng, v_in, normal, T_w, m, alpha_n, alpha_t):
    """Cercignani-Lampis-Lord kernel (Lord 1991 sampling). normal points into the gas.
    alpha_n / alpha_t must be finite and inside [0, 1] (MCC-07: rejected before sampling, never clipped)."""
    _check_unit_interval("CLL alpha_n", alpha_n)
    _check_unit_interval("CLL alpha_t", alpha_t)
    n = len(v_in)
    vmp = math.sqrt(2 * K_B * T_w / m)
    vn = (v_in * normal).sum(1)                         # negative (into wall)
    vt = v_in - vn[:, None] * normal
    # tangential: each component relaxes toward the wall Maxwellian
    vt_out = math.sqrt(1 - alpha_t) * vt + math.sqrt(alpha_t) * rng.normal(0, vmp / math.sqrt(2), size=(n, 3))
    vt_out -= (vt_out * normal).sum(1)[:, None] * normal
    # normal: Lord's algorithm in units of vmp
    r = np.sqrt(-alpha_n * np.log(rng.uniform(1e-12, 1.0, n)))
    th = 2 * math.pi * rng.uniform(0, 1, n)
    vm = np.sqrt(1 - alpha_n) * np.abs(vn) / vmp
    vn_out = np.sqrt(r * r + vm * vm + 2 * r * vm * np.cos(th)) * vmp
    return vt_out + vn_out[:, None] * normal


def trace_channel(rng, v0, R, L, alpha, T_w, m, max_hits=200, scattering="maxwell", alpha_n=None, alpha_t=None,
                  unresolved_tol=1e-3, max_hits_cap=5000):
    """Trace molecules from the entrance plane through a cylindrical channel of radius R, length L.
    Returns (collected mask, final velocities, wall hits, back mask, unresolved fraction).
    Molecules still inside after the hit budget are NOT counted as collected: the budget doubles (to max_hits_cap)
    until the unresolved fraction is <= unresolved_tol; any remainder is reported, never assigned.
    Inputs are validated before tracing (A9.9 S2.5): max_hits and max_hits_cap positive integers (MCC-05);
    scattering exactly 'maxwell' or 'cll' (MCC-06); accommodation finite and inside [0, 1] (MCC-07)."""
    scattering = _check_scattering(scattering)
    max_hits = _check_hit_budget("max_hits", max_hits)
    max_hits_cap = _check_hit_budget("max_hits_cap", max_hits_cap)
    _check_accommodation(scattering, alpha, alpha_n, alpha_t)
    if isinstance(unresolved_tol, bool) or not isinstance(unresolved_tol, numbers.Real) \
            or not math.isfinite(float(unresolved_tol)) or float(unresolved_tol) < 0.0:
        raise ValueError(f"intake_tpmc: unresolved_tol must be finite and >= 0, got {unresolved_tol!r}")
    n = len(v0)
    r = R * np.sqrt(rng.uniform(0, 1, n)); ph = rng.uniform(0, 2 * math.pi, n)
    p = np.stack([r * np.cos(ph), r * np.sin(ph), np.zeros(n)], axis=1)
    v = v0.copy()
    alive = np.ones(n, bool); collected = np.zeros(n, bool); back = np.zeros(n, bool)
    hits = np.zeros(n, int)
    budget = max_hits; done_steps = 0
    while True:
        while done_steps < budget and alive.any():
            done_steps += 1
            idx = np.where(alive)[0]
            pv, vv = p[idx], v[idx]
            a = vv[:, 0] ** 2 + vv[:, 1] ** 2
            b = 2 * (pv[:, 0] * vv[:, 0] + pv[:, 1] * vv[:, 1])
            c = pv[:, 0] ** 2 + pv[:, 1] ** 2 - R * R
            disc = np.maximum(b * b - 4 * a * c, 0.0)
            t_wall = np.where(a > 1e-30, (-b + np.sqrt(disc)) / (2 * np.maximum(a, 1e-30)), np.inf)
            t_back = np.where(vv[:, 2] > 0, (L - pv[:, 2]) / np.where(vv[:, 2] > 0, vv[:, 2], 1), np.inf)
            t_front = np.where(vv[:, 2] < 0, (0.0 - pv[:, 2]) / np.where(vv[:, 2] < 0, vv[:, 2], 1), np.inf)
            t = np.minimum.reduce([t_wall, t_back, t_front])
            p[idx] = pv + vv * t[:, None]
            exit_back = (t_back <= t_wall) & (t_back <= t_front)
            exit_front = (t_front < t_wall) & (t_front < t_back)
            wall = ~(exit_back | exit_front)
            collected[idx[exit_back]] = True; back[idx[exit_front]] = True
            alive[idx[exit_back | exit_front]] = False
            wi = idx[wall]
            if len(wi):
                hits[wi] += 1
                pw = p[wi]
                normal = -np.stack([pw[:, 0], pw[:, 1], np.zeros(len(wi))], axis=1) / R
                vw = v[wi]
                if scattering == "cll":
                    v[wi] = _cll(rng, vw, normal, T_w, m, alpha if alpha_n is None else alpha_n, alpha if alpha_t is None else alpha_t)
                else:
                    diffuse = rng.uniform(0, 1, len(wi)) < alpha
                    vn = (vw * normal).sum(1)
                    v_spec = vw - 2 * vn[:, None] * normal
                    v_diff = _diffuse(rng, len(wi), T_w, m, normal)
                    v[wi] = np.where(diffuse[:, None], v_diff, v_spec)
        unresolved = float(alive.mean())
        if unresolved <= unresolved_tol or budget >= max_hits_cap or not alive.any():
            break
        budget = min(budget * 2, max_hits_cap)
    return collected, v, hits, back, float(alive.mean())


K_BACK_SCATTERING = "maxwell"    # kernel of the thermal back-trace (unchanged behaviour, now explicit and recorded)


def clausing_transmission(rng, R, L, alpha, T_w, m, n=20000):
    """Thermal molecules entering from the plenum side: fraction transmitted to the front (K_back).
    The back-trace uses the Maxwell kernel (explicitly selected; recorded as K_back_scattering by intake_response)."""
    _check_accommodation("maxwell", alpha)
    vth = math.sqrt(K_B * T_w / m)
    # flux-weighted cosine entry from the back plane, travelling toward the front (negative z here -> flip)
    normal = np.tile(np.array([0, 0, 1.0]), (n, 1))
    v0 = _diffuse(rng, n, T_w, m, normal)
    collected, _, _, _, unres = trace_channel(rng, v0, R, L, alpha, T_w, m, scattering=K_BACK_SCATTERING)
    return float(collected.mean())


def intake_response(geom: IntakeGeometry, atm: dict, alpha: float, theta_deg: float = 0.0,
                    n: int = 30000, seed: int = 0, scattering: str = "maxwell", species_mass: float | None = None) -> dict:
    """eta_c, C_D, K_back, passive compression ratio, mass, for one geometry/surface/incidence.
    scattering must be 'maxwell' or 'cll' (no fallback); alpha must be finite in [0, 1]; both checked before sampling."""
    scattering = _check_scattering(scattering)
    _check_accommodation(scattering, alpha)
    rng = np.random.default_rng(seed)
    m = species_mass or atm["m_mean"]; V = atm.get("V_rel", atm["V"]); T = atm["T"]
    R = geom.d_mm * 1e-3 / 2; L = geom.L_over_d * geom.d_mm * 1e-3
    theta = math.radians(theta_deg)
    # free-stream number flux through the aperture (molecules per m^2 s), all with weight 1
    v0 = _flux_weighted_entry(rng, n, V, theta, T, m)
    collected, v_out, hits, back, unresolved = trace_channel(rng, v0, R, L, alpha, geom.T_wall_K, m, scattering=scattering)
    # channel-region collection (per unit open area)
    eta_open = collected.mean()
    # momentum: z-momentum in per particle = m v0z; out for backscattered = m v_out_z (negative)
    pz_in = m * v0[:, 2]
    pz_out = np.where(back, m * v_out[:, 2], 0.0)          # collected: absorbed
    F_open = (pz_in - pz_out).mean() * (v0[:, 2].mean())   # per unit flux normalisation below
    # normalise: force per unit area = number flux * mean momentum transfer per molecule
    # number flux through the aperture = n_inf * <v_z> over the incoming half distribution ≈ n V cos(theta) for high speed ratio
    n_inf = atm["n"]; Vz = V * math.cos(theta)
    flux_num = n_inf * Vz
    dp_open = (pz_in - pz_out).mean()
    F_per_area_open = flux_num * dp_open
    # front solid face (1-phi): diffuse re-emission; momentum transfer = m Vz + m * (sqrt(pi kT_w/(2m)))
    dp_solid = m * Vz + m * math.sqrt(math.pi * K_B * geom.T_wall_K / (2 * m))
    F_per_area_solid = flux_num * dp_solid
    F_per_area = geom.phi * F_per_area_open + (1 - geom.phi) * F_per_area_solid
    q = 0.5 * atm["rho"] * V * V
    C_D = F_per_area / q
    eta_c = geom.phi * eta_open * math.cos(theta)          # referenced to free-stream flux on the aperture
    K_back = clausing_transmission(rng, R, L, alpha, geom.T_wall_K, m)
    if geom.filter:
        eta_c *= geom.filter_open_frac * geom.filter_transmission ** 0.5   # forward: hyperthermal, mostly transmitted
        K_back *= geom.filter_transmission
        phi_eff = geom.phi * geom.filter_open_frac
    else:
        phi_eff = geom.phi
    c_bar = math.sqrt(8 * K_B * geom.T_wall_K / (math.pi * m))
    CR_passive = eta_c * V / ((c_bar / 4) * phi_eff * max(K_back, 1e-6))
    # geometric mass
    n_cells = geom.phi * geom.area_m2 / (math.pi * R * R)
    wall_area = n_cells * (2 * math.pi * R) * L * 0.5           # shared walls
    m_sub = wall_area * geom.wall_thickness_mm * 1e-3 * geom.wall_density_kg_m3
    m_coat = (wall_area + geom.area_m2) * geom.coating_thickness_um * 1e-6 * geom.coating_density_kg_m3
    m_int = (m_sub + m_coat) * (1 + geom.support_mass_frac) + (geom.filter_mass_per_m2 * geom.area_m2 if geom.filter else 0.0)
    return {"eta_c": eta_c, "C_D": C_D, "K_back": K_back, "CR_passive": CR_passive, "eta_open": eta_open,
            "unresolved_fraction": unresolved, "converged": unresolved <= 1e-3, "scattering": scattering,
            "K_back_scattering": K_BACK_SCATTERING,
            "mean_wall_hits": float(hits.mean()), "mass_kg": m_int, "alpha": alpha, "theta_deg": theta_deg,
            "L_over_d": geom.L_over_d, "phi": geom.phi, "d_mm": geom.d_mm}


def response_surface(atm: dict, L_over_d=(3, 5, 10, 20), phis=(0.8, 0.9), alphas=(0.0, 0.2, 0.5, 0.8, 1.0),
                     thetas=(0.0, 2.0, 5.0), n=15000, area_m2=0.5, species=None, scattering="maxwell"):
    """species: None -> mean molecular mass; otherwise a tuple like ("O","N2","O2") -> one surface per species
    (column 'species'), recombined downstream by IntakeSurface from the species definitions (A9.9 S2.1)."""
    scattering = _check_scattering(scattering)
    import itertools, pandas as pd
    from .constants import M_SPECIES
    rows = []
    specs = [(None, None)] if not species else [(sp, M_SPECIES[sp]) for sp in species]
    for (sp, msp), ld, ph, al, th in itertools.product(specs, L_over_d, phis, alphas, thetas):
        g = IntakeGeometry(area_m2=area_m2, L_over_d=ld, phi=ph)
        r = intake_response(g, atm, al, th, n=n, scattering=scattering, species_mass=msp)
        r["species"] = sp or "mean"
        rows.append(r)
    return pd.DataFrame(rows)


FROZEN_SURFACE = "intake_surface_v1.csv"


def frozen_surface_path() -> str:
    import os
    return os.path.join(os.path.dirname(__file__), "data", FROZEN_SURFACE)


def build_frozen_surface(n: int = 20000, out: str | None = None) -> str:
    """Explicit command: python -m abep_sim.intake_tpmc build   (never called from evaluate())."""
    import hashlib, json, os
    from .atmosphere import atmosphere
    df = response_surface(atmosphere(200.0, "mean"), n=n, species=("O", "N2", "O2"))
    out = out or frozen_surface_path()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.to_csv(out, index=False)
    h = hashlib.sha256(open(out, "rb").read()).hexdigest()[:16]
    meta = {"file": os.path.basename(out), "sha256_16": h, "n_per_point": n, "atmosphere": "NRLMSIS 2.1 200 km mean",
            "scattering": "maxwell", "species": ["O", "N2", "O2"], "max_unresolved": float(df.unresolved_fraction.max())}
    json.dump(meta, open(out.replace(".csv", ".json"), "w"), indent=1)
    return out


def frozen_surface_build_atmosphere() -> dict:
    """Free-stream state the frozen surface v1 was built at (intake_surface_v1.json: NRLMSIS 2.1, 200 km, F10.7 150,
    orbit-averaged; build_frozen_surface calls atmosphere(200.0, "mean")). Read from the frozen atmosphere dataset
    (use_msis=False) so it never depends on a live MSIS install. Its m_mean is the mixture mean molecular mass that
    normalises every species row's C_D (see IntakeSurface); tests/test_intake_surface_recombination.py checks that the
    table's own solid-face identity reproduces it."""
    from .atmosphere import atmosphere
    return atmosphere(200.0, "mean", use_msis=False)


class IntakeSurface:
    """Interpolating reduced-order model over (L/d, phi, alpha, theta).

    If the table is species-resolved (column 'species' in O/N2/O2), the call takes free-stream MASS fractions w_s and
    recombines the species rows by their physical definitions (owner decision A9.9 S2.1 / F1Q-01, finding F1-01).
    Until 2026-10-01 every row was mass-fraction averaged; that was a model-consistency defect, not a convention.

    Definitions used to build each species row s (intake_response with species_mass = m_s, run in the MIXTURE
    build atmosphere: n_b, rho_b = n_b m_b, V_b; m_b = m_mean of the build state, see frozen_surface_build_atmosphere):
      eta_c,s   = collected / incident number flux of species s (per unit aperture; mass-independent normalisation)
      C_D_row,s = n_b Vz <dp_s> / (1/2 rho_b V_b^2)       <dp_s> = mean momentum transfer per molecule of mass m_s
      CR_s      = n_plenum,s / n_inf,s                     (zero-net-flow flux balance with c_bar_s(T_wall))
      K_back,s  = Clausing transmission of species-s plenum molecules

    Derivation of the mixture (mole fractions x_s = (w_s/m_s) / sum_k (w_k/m_k), m_mix = sum_s x_s m_s):
      * Drag. Species s alone (number density n_s = x_s n) exerts F_s/A = n_s Vz <dp_s>. Its own coefficient on its own
        dynamic pressure q_s = 1/2 n_s m_s V^2 is C_D,s = Vz <dp_s> / (1/2 m_s V^2) = C_D_row,s * m_b / m_s (the row
        is normalised by the build MIXTURE q, not by q_s). Total F = sum_s F_s and q = sum_s q_s = 1/2 rho V^2, so
            C_D = F / (q A) = sum_s (q_s/q) C_D,s = sum_s w_s C_D,s = m_b * sum_s (w_s / m_s) C_D_row,s
        (= sum_s x_s C_D_row,s * m_b / m_mix). The old mass-weighted sum_s w_s C_D_row,s over-weights heavy species.
      * Passive compression. CR is a number-density ratio: n_plenum = sum_s CR_s n_inf,s = n sum_s x_s CR_s, so
            CR_passive = sum_s x_s CR_s   (mole weighting; the old mass weighting is not the definition).
      * Collection. Species-resolved collected mass flow mdot_c,s = eta_c,s rho_s V A = eta_c,s w_s mdot_incident; the
        per-species efficiencies are returned unaggregated in out["species"] (with the collected mass and mole
        fractions), and the mixture eta_c = sum_s mdot_c,s / mdot_incident = sum_s w_s eta_c,s is exactly the total
        collected / incident MASS flow (the quantity intake.collection multiplies by the incident mass flux).
      * K_back of the mixture: transmission probability of the plenum effusion flux, weighted by the per-species
        effusion flux n_p,s c_bar_s / 4 at T_wall:  K = sum_s x_s CR_s m_s^-1/2 K_s / sum_s x_s CR_s m_s^-1/2.
      * mass_kg is geometric (species-independent); the w-weighted mean is kept (identical rows -> identical value).
    Pure species (w_s = 1): eta_c, CR_passive, K_back equal the species row exactly; C_D equals the species' own
    coefficient C_D_row,s m_b/m_s (the row rescaled from the build-mixture q to the species q), which is what a gas of
    that species alone experiences. Rows are at the build speed ratio (V_b, T_b); off-build states are S2.2 (v2).
    """

    def __init__(self, df, m_mean_build_kg: float | None = None):
        from scipy.interpolate import LinearNDInterpolator
        self.df = df
        self.species = sorted(df["species"].unique()) if "species" in df else ["mean"]
        self.f = {}
        for sp in self.species:
            d = df[df["species"] == sp] if "species" in df else df
            pts = d[["L_over_d", "phi", "alpha", "theta_deg"]].values
            self.f[sp] = {k: LinearNDInterpolator(pts, d[k].values, rescale=True) for k in ("eta_c", "C_D", "CR_passive", "K_back", "mass_kg")}
        self.bounds = {k: (df[k].min(), df[k].max()) for k in ("L_over_d", "phi", "alpha", "theta_deg")}
        self.max_unresolved = float(df["unresolved_fraction"].max()) if "unresolved_fraction" in df else None
        self.m_mean_build_kg = None if m_mean_build_kg is None else float(m_mean_build_kg)
        if self.species != ["mean"]:
            from .constants import M_SPECIES
            unknown = [s for s in self.species if s not in M_SPECIES]
            if unknown:
                raise ValueError(f"IntakeSurface: species {unknown} have no molecular mass in constants.M_SPECIES")
            if self.m_mean_build_kg is None or not (math.isfinite(self.m_mean_build_kg) and self.m_mean_build_kg > 0):
                raise ValueError("IntakeSurface: a species-resolved table needs m_mean_build_kg (mixture mean molecular "
                                 "mass of the build atmosphere that normalises the C_D rows); no default is assumed")
            self.m_s = {s: float(M_SPECIES[s]) for s in self.species}

    # Frozen domain (S2.2 / A9.13 S6.2 fail-closed check, 2026-10-01). The interpolation axes are refused outside the
    # table bounds (unchanged since v1.3: a ValueError, never extrapolation); non-finite inputs fail the bounds test.
    # The grid is a full tensor product, so the bounding box equals the interpolation hull; a non-finite interpolated
    # value is nevertheless refused (_row) rather than passed on. The free-stream state is NOT an axis of v1: every row
    # is at the single build state (frozen_surface_build_atmosphere); off-build use is the documented speed-ratio
    # approximation of intake._tpmc_surface until surface v2 (abep_sim/intake_surface_v2_spec.py) is built.
    AXES = ("L_over_d", "phi", "alpha", "theta_deg")

    def domain(self) -> dict:
        return {"axes": {k: [float(v) for v in self.bounds[k]] for k in self.AXES}, "species": list(self.species),
                "atmosphere_state": "single build state (not an axis); off-build use is an approximation, see "
                                    "intake_surface_v2_spec", "outside_domain": "ValueError (fail closed)"}

    def in_bounds(self, L_over_d, phi, alpha, theta_deg=0.0) -> bool:
        return all(self.bounds[k][0] <= v <= self.bounds[k][1] for k, v in (("L_over_d", L_over_d), ("phi", phi), ("alpha", alpha), ("theta_deg", theta_deg)))

    def _row(self, sp, L_over_d, phi, alpha, theta_deg) -> dict:
        r = {k: float(f(L_over_d, phi, alpha, theta_deg)) for k, f in self.f[sp].items()}
        bad = [k for k, v in r.items() if not math.isfinite(v)]
        if bad:
            raise ValueError(f"intake ROM: non-finite {bad} for species {sp} at L/d={L_over_d}, phi={phi}, "
                             f"alpha={alpha}, theta={theta_deg} (outside the interpolation hull; no extrapolation)")
        return r

    def __call__(self, L_over_d, phi, alpha, theta_deg=0.0, fractions: dict | None = None):
        if not self.in_bounds(L_over_d, phi, alpha, theta_deg):
            raise ValueError(f"intake ROM extrapolation: L/d={L_over_d}, phi={phi}, alpha={alpha}, theta={theta_deg} outside {self.bounds}")
        if self.species == ["mean"]:
            return self._row("mean", L_over_d, phi, alpha, theta_deg)
        # Review fix D-07/N6 (2026-10-01, rule 3): a species-resolved table needs explicit free-stream mass fractions.
        # Until then a call without fractions silently used a hard-coded {O 0.45, N2 0.50, O2 0.05}; all-zero
        # fractions returned zeros / NaN; a negative fraction was dropped from w but still counted in the total.
        if not fractions:
            raise ValueError("intake ROM: a species-resolved table needs explicit free-stream mass fractions "
                             f"{self.species} (no default composition is assumed)")
        bad = {s: v for s, v in fractions.items()
               if isinstance(v, bool) or not isinstance(v, numbers.Real) or not math.isfinite(v) or v < 0}
        if bad:
            raise ValueError(f"intake ROM: mass fractions must be finite and >= 0, got {bad}")
        foreign = [s for s, v in fractions.items() if s not in self.species and v > 0]
        if foreign:
            raise ValueError(f"intake ROM: species {foreign} with non-zero fraction are not in the frozen table "
                             f"{self.species} (no silent drop / renormalisation)")
        tot = sum(fractions.get(s, 0.0) for s in self.species)
        if not tot > 0:
            raise ValueError(f"intake ROM: all mass fractions are zero for species {self.species}")
        w = {s: fractions.get(s, 0.0) / tot for s in self.species if fractions.get(s, 0.0) > 0}
        rows = {s: self._row(s, L_over_d, phi, alpha, theta_deg) for s in w}
        inv_m = {s: w[s] / self.m_s[s] for s in w}                 # w_s / m_s  (proportional to number density)
        s_inv = sum(inv_m.values())
        x = {s: inv_m[s] / s_inv for s in w}                        # mole fractions
        mb = self.m_mean_build_kg
        cd_s = {s: rows[s]["C_D"] * mb / self.m_s[s] for s in w}   # species' own C_D (own dynamic pressure)
        C_D = sum(w[s] * cd_s[s] for s in w)                        # = mb * sum_s (w_s/m_s) C_D_row,s
        CR = sum(x[s] * rows[s]["CR_passive"] for s in w)
        eta_c = sum(w[s] * rows[s]["eta_c"] for s in w)             # total collected / incident mass flow
        eff = {s: x[s] * rows[s]["CR_passive"] / math.sqrt(self.m_s[s]) for s in w}   # plenum effusion-flux weights
        eff_tot = sum(eff.values())
        K_back = (sum(eff[s] * rows[s]["K_back"] for s in w) / eff_tot) if eff_tot > 0 else float("nan")
        mass_kg = sum(w[s] * rows[s]["mass_kg"] for s in w)
        n_col = {s: x[s] * rows[s]["eta_c"] for s in w}             # collected number flux per incident molecule
        n_col_tot = sum(n_col.values())
        species = {s: {"eta_c": rows[s]["eta_c"], "C_D_row": rows[s]["C_D"], "C_D_species": cd_s[s],
                       "CR_passive": rows[s]["CR_passive"], "K_back": rows[s]["K_back"],
                       "mass_fraction": w[s], "mole_fraction": x[s],
                       "collected_mass_fraction": (w[s] * rows[s]["eta_c"] / eta_c) if eta_c > 0 else float("nan"),
                       "collected_mole_fraction": (n_col[s] / n_col_tot) if n_col_tot > 0 else float("nan")}
                   for s in w}
        return {"eta_c": eta_c, "C_D": C_D, "K_back": K_back, "mass_kg": mass_kg, "CR_passive": CR,
                "species": species, "recombination": "species_consistent_v2_A9.9_S2.1"}

    def call_legacy_mass_weighted(self, L_over_d, phi, alpha, theta_deg=0.0, fractions: dict | None = None):
        """HISTORICAL EVIDENCE ONLY (pre-2026-10-01 recombination, owner decision A9.9 S2.1): every species row averaged
        by mass fraction (C_D rows still normalised by the build-mixture q; CR mass- instead of mole-weighted). Kept so
        the pre-fix values stay reproducible in tests and HISTORY; never used by the production chain."""
        if not self.in_bounds(L_over_d, phi, alpha, theta_deg):
            raise ValueError(f"intake ROM extrapolation: L/d={L_over_d}, phi={phi}, alpha={alpha}, theta={theta_deg} outside {self.bounds}")
        out = {k: 0.0 for k in ("eta_c", "C_D", "K_back", "mass_kg", "CR_passive")}
        tot = sum(fractions.get(s, 0.0) for s in self.species) or 1.0
        for s in self.species:
            wt = fractions.get(s, 0.0) / tot
            if wt <= 0:
                continue
            for k, f in self.f[s].items():
                out[k] += wt * float(f(L_over_d, phi, alpha, theta_deg))
        return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        print(build_frozen_surface(int(sys.argv[2]) if len(sys.argv) > 2 else 20000))

"""Electrical power (or permanent-magnet mass) needed to produce a required magnetic field  (lane PPUMAG, v1).

Serves the ``hall_magnet`` and ``ecr_magnet`` components of the common bus-power boundary
(``bus_power_boundary_v1``; module ``abep_sim/arch_boundary.py`` is built by another lane and is NOT imported here).
The result of this module is the component's **load-side** power at the coil terminals (I^2 R). The bus-side draw also
needs the magnet-supply efficiency, which is evidence data (docs/architecture_comparison/electrical_closure/
electrical_closure_data_v1.json), never a code default.

Pure module: standard library only, no I/O, not wired into ``archengine`` (wiring it would be a model change).
**No default physical or design inputs.** Every function argument is required; there are no default arguments. The only
numbers in the module are cited reference constants/objects that a caller must pass explicitly (``ANNEALED_COPPER_IACS``)
or fundamental constants (``MU0_N_PER_A2``). Missing, non-finite or out-of-domain inputs raise ``ValueError``; physically
impossible designs (saturated core, magnet beyond its knee, zero turns) raise ``ValueError`` instead of returning a
number (CLAUDE.md rule 3: no silent fallbacks).

Equations and sources (all accessed 2026-09-26, openly available):
  [E1] Ampere's law around the magnetic circuit, sum of element MMFs = N I, and element reluctance
       R = l / (mu A) (uniform flux density), gap reluctance g / (mu0 A_g), iron with finite mu_r:
       J. L. Kirtley Jr., "Magnetic Circuit Analog to Electric Circuits", MIT 6.007 supplemental notes (2010),
       Sec. 3.2-3.4, https://ocw.mit.edu/courses/6-007-electromagnetic-energy-from-motors-to-lasers-spring-2011/
       3ca50847f907d44a148504a778d1a5f5_MIT6_007S11_circuits.pdf.  Kirtley notes that ignoring fringing "generally
       over-estimates the reluctance" of a gap (Sec. 3.5); fringing and leakage enter here only through the explicit
       ``leakage_factor`` (core flux = leakage_factor x gap flux, >= 1) -- no value is assumed.
  [E2] Permanent magnet with a linear recoil line B_m = B_r + mu0 mu_rec H_m in series with the same circuit
       (H_m l_m + sum H_i l_i = 0, flux continuity B_m A_m = leakage_factor B_g A_g). For mu_rec = 1, no core MMF and
       leakage_factor = 1 this reduces to Kirtley's unit-permeance result B_m = B0 P_u / (1 + P_u):
       J. L. Kirtley Jr., "Permanent Magnet 'Brushless DC' Motors", MIT 6.061 class notes ch. 12, Sec. 4.3,
       https://ocw.mit.edu/courses/6-061-introduction-to-electric-power-systems-spring-2011/
       36e8b4e86968267bc7030941f020b2af_MIT6_061S11_ch12.pdf.  The knee (irreversible demagnetization) field is an
       explicit input from the caller's magnet data sheet; this module holds no magnet-material data.
  [E3] Wire resistance R(T) = R_20 [1 + alpha_20 (T - 20 C)] with alpha_20 = 0.00393 /K for the resistance
       "between points fixed on a wire which is allowed to expand freely" (so thermal expansion is already inside
       alpha); International Annealed Copper Standard resistivity 0.017241 ohm mm^2/m at 20 C; density 8.89 g/cm^3 at
       20 C; the resistance-temperature curve is "linear up to 200 C" (and "probably" -100 to +300 C):
       NBS Handbook 100, "Copper Wire Tables" (1966), pp. 1-3,
       https://nvlpubs.nist.gov/nistpubs/Legacy/hb/nbshandbook100.pdf (sha256 3128aaa9...cf6c of the accessed file).
  [E4] American Wire Gage: geometric progression, No. 0000 = 0.4600 in and No. 36 = 0.0050 in, 39 steps, ratio
       39th root of 92 (NBS Handbook 100, Sec. 2.2, p. 6). Diameters here are the exact progression; the Handbook's
       tabulated diameters are rounded (to 0.1 mil for 0000-44), so they can differ by < 0.05 mil.
  [E5] Coil: N turns of bare conductor area A_cu in a winding window A_w with copper fill factor k = N A_cu / A_w,
       mean turn length l_mt: R = rho N l_mt / A_cu, P = I^2 R with I = (N I) / N. Eliminating N gives the
       gauge-independent form P = (N I)^2 rho l_mt / (k A_w): straightforward algebra of [E1], [E3] (derivation in
       docs/architecture_comparison/electrical_closure/ELECTRICAL_CLOSURE.md Sec. 3).
  [E6] mu0 = 1.256 637 061 27e-6 N A^-2, CODATA 2022 recommended value (NIST, https://physics.nist.gov/cgi-bin/cuu/
       Value?mu0), relative standard uncertainty 1.6e-10.

Evidence class of every result: model-derived (level 6 engineering correlation for the lumped magnetic circuit; the
field it must produce, its geometry, fill factor, core permeability and temperature are the caller's inputs and carry
the caller's evidence). Never a measured Vyovrinda value (docs/EVIDENCE.md).
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Integral, Real

MAGNET_POWER_VERSION = "magnet_power_v1"
MU0_N_PER_A2 = 1.25663706127e-6  # [E6] CODATA 2022 (fundamental constant, not a design default)
_INCH_M = 0.0254                  # exact by definition of the international inch


def _real(value, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{what} must be a real number, got {type(value).__name__} {value!r}")
    x = float(value)
    if not math.isfinite(x):
        raise ValueError(f"{what} must be finite, got {x!r}")
    return x


def _pos(value, what: str) -> float:
    x = _real(value, what)
    if not x > 0.0:
        raise ValueError(f"{what} must be > 0, got {x!r}")
    return x


def _nonneg(value, what: str) -> float:
    x = _real(value, what)
    if x < 0.0:
        raise ValueError(f"{what} must be >= 0, got {x!r}")
    return x


# --------------------------------------------------------------------------------------------------- conductor [E3]
@dataclass(frozen=True)
class ConductorMaterial:
    """Linear resistance-temperature model R(T) = R_ref [1 + alpha_ref (T - T_ref)] with a declared validity domain.

    ``alpha_ref_per_K`` must be the coefficient of *wire resistance* (free thermal expansion included), not of volume
    resistivity. Temperatures outside [T_min_C, T_max_C] are refused, never extrapolated.
    """
    name: str
    rho_ref_ohm_m: float
    T_ref_C: float
    alpha_ref_per_K: float
    T_min_C: float
    T_max_C: float
    density_kg_m3: float
    source: str

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("ConductorMaterial.name must be a non-empty string")
        _pos(self.rho_ref_ohm_m, "rho_ref_ohm_m")
        _real(self.T_ref_C, "T_ref_C")
        _pos(self.alpha_ref_per_K, "alpha_ref_per_K")
        lo, hi = _real(self.T_min_C, "T_min_C"), _real(self.T_max_C, "T_max_C")
        if not lo < hi:
            raise ValueError(f"validity domain must satisfy T_min_C < T_max_C, got [{lo}, {hi}]")
        if not lo <= self.T_ref_C <= hi:
            raise ValueError("T_ref_C must lie inside the validity domain")
        _pos(self.density_kg_m3, "density_kg_m3")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("ConductorMaterial.source must cite where the values come from")


# NBS Handbook 100 (1966) pp. 1-3: IACS 0.017241 ohm mm^2/m at 20 C, alpha_20 = 0.00393 /K (wire resistance, free
# expansion), density 8.89 g/cm^3; linear "up to 200 C" (0-300 C straight line in Roeser's data; Dellinger 10-100 C).
# The domain below is the stated one [0, 200] C; the Handbook's "probably -100 to +300 C" is NOT used. Evidence level 4
# (evaluated standard), quantity type measured (standardized). Callers pass this object explicitly.
ANNEALED_COPPER_IACS = ConductorMaterial(
    name="annealed copper, International Annealed Copper Standard (100 % IACS)",
    rho_ref_ohm_m=1.7241e-8, T_ref_C=20.0, alpha_ref_per_K=0.00393, T_min_C=0.0, T_max_C=200.0,
    density_kg_m3=8890.0,
    source="NBS Handbook 100, Copper Wire Tables (1966), pp. 1-3; "
           "https://nvlpubs.nist.gov/nistpubs/Legacy/hb/nbshandbook100.pdf",
)


def resistance_factor(material: ConductorMaterial, T_C) -> float:
    """R(T)/R(T_ref) = 1 + alpha_ref (T - T_ref) [E3]; refuses T outside the material's validity domain."""
    if not isinstance(material, ConductorMaterial):
        raise ValueError(f"material must be a ConductorMaterial, got {type(material).__name__}")
    T = _real(T_C, "coil temperature T_C")
    if not material.T_min_C <= T <= material.T_max_C:
        raise ValueError(f"coil temperature {T} C outside the validity domain [{material.T_min_C}, {material.T_max_C}] C "
                         f"of {material.name!r}; the linear model is not extrapolated")
    return 1.0 + material.alpha_ref_per_K * (T - material.T_ref_C)


def wire_resistance_ohm(length_m, area_m2, material: ConductorMaterial, T_C) -> float:
    """R = rho_ref L / A x resistance_factor(T); L and A are the dimensions at T_ref [E3]."""
    L = _pos(length_m, "conductor length_m")
    A = _pos(area_m2, "conductor area_m2")
    return material.rho_ref_ohm_m * L / A * resistance_factor(material, T_C)


# ------------------------------------------------------------------------------------------------------- AWG [E4]
def awg_diameter_m(gauge) -> float:
    """Bare diameter of American Wire Gage ``gauge`` [E4]. Integers 0..56; 0000, 000, 00 are passed as -3, -2, -1."""
    if isinstance(gauge, bool) or not isinstance(gauge, Integral):
        raise ValueError(f"AWG gauge must be an integer (0000 -> -3, 000 -> -2, 00 -> -1), got {gauge!r}")
    n = int(gauge)
    if not -3 <= n <= 56:
        raise ValueError(f"AWG gauge {n} outside the defined range 0000 (-3) .. 56 (NBS Handbook 100)")
    return 0.0050 * _INCH_M * 92.0 ** ((36 - n) / 39.0)


# ------------------------------------------------------------------------------------------- magnetic circuit [E1]
@dataclass(frozen=True)
class CoreSegment:
    """One soft-magnetic element of the flux return path (uniform section, linear permeability, saturation limit)."""
    name: str
    length_m: float
    area_m2: float
    mu_r: float
    B_max_T: float  # caller's linear-range / saturation limit for this material; exceeding it is refused

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("CoreSegment.name must be a non-empty string")
        _pos(self.length_m, f"{self.name}.length_m")
        _pos(self.area_m2, f"{self.name}.area_m2")
        mu = _real(self.mu_r, f"{self.name}.mu_r")
        if mu < 1.0:
            raise ValueError(f"{self.name}.mu_r must be >= 1 for a soft-magnetic return path, got {mu!r}")
        _pos(self.B_max_T, f"{self.name}.B_max_T")


def _segments(core_segments) -> tuple:
    if isinstance(core_segments, (str, bytes)) or not isinstance(core_segments, Sequence):
        raise ValueError("core_segments must be a sequence of CoreSegment (pass () explicitly for an ideal-iron circuit)")
    segs = tuple(core_segments)
    for s in segs:
        if not isinstance(s, CoreSegment):
            raise ValueError(f"core_segments must contain CoreSegment objects, got {type(s).__name__}")
    return segs


def _circuit(B_gap_T, gap_length_m, gap_area_m2, core_segments, leakage_factor):
    B_g = _pos(B_gap_T, "B_gap_T")
    g = _pos(gap_length_m, "gap_length_m")
    A_g = _pos(gap_area_m2, "gap_area_m2")
    k = _real(leakage_factor, "leakage_factor")
    if k < 1.0:
        raise ValueError(f"leakage_factor (core flux / gap flux) must be >= 1, got {k!r}")
    segs = _segments(core_segments)
    phi_gap = B_g * A_g
    phi_core = k * phi_gap
    F_gap = B_g * g / MU0_N_PER_A2
    seg_out = []
    F_core = 0.0
    for s in segs:
        B_s = phi_core / s.area_m2
        if B_s > s.B_max_T:
            raise ValueError(f"core segment {s.name!r}: B = {B_s:.4g} T exceeds its declared limit {s.B_max_T} T; "
                             f"the linear magnetic-circuit model is not valid (enlarge the section)")
        F_s = B_s * s.length_m / (MU0_N_PER_A2 * s.mu_r)
        F_core += F_s
        seg_out.append({"name": s.name, "B_T": B_s, "mmf_A": F_s})
    return {"phi_gap_Wb": phi_gap, "phi_core_Wb": phi_core, "mmf_gap_A": F_gap, "mmf_core_A": F_core,
            "segments": seg_out, "leakage_factor": k}


def ampere_turns(B_gap_T, gap_length_m, gap_area_m2, core_segments, leakage_factor) -> dict:
    """Ampere-turns N I needed for ``B_gap_T`` across a gap of length ``gap_length_m`` [E1].

    N I = B_g g / mu0 + sum_i (k B_g A_g / A_i) l_i / (mu0 mu_r,i), with k = ``leakage_factor`` >= 1 (core flux over
    gap flux; covers leakage and fringing, no value assumed). ``core_segments`` = () declares an ideal (mu -> inf) core.
    """
    c = _circuit(B_gap_T, gap_length_m, gap_area_m2, core_segments, leakage_factor)
    return {"version": MAGNET_POWER_VERSION, "NI_A": c["mmf_gap_A"] + c["mmf_core_A"], **c}


# ------------------------------------------------------------------------------------------------------ coil [E5]
def coil_power_continuous_W(NI_A, window_area_m2, fill_factor, mean_turn_length_m,
                            material: ConductorMaterial, T_C) -> float:
    """Gauge-independent coil dissipation P = (N I)^2 rho(T) l_mt / (k A_w) [E5] (continuous-turn limit)."""
    NI = _pos(NI_A, "NI_A")
    A_w = _pos(window_area_m2, "window_area_m2")
    k = _real(fill_factor, "fill_factor")
    if not 0.0 < k < 1.0:
        raise ValueError(f"copper fill_factor must be in (0, 1), got {k!r}")
    l_mt = _pos(mean_turn_length_m, "mean_turn_length_m")
    f_T = resistance_factor(material, T_C)  # refuses a non-ConductorMaterial and an out-of-domain temperature
    rho = material.rho_ref_ohm_m * f_T
    return NI * NI * rho * l_mt / (k * A_w)


def coil_design(NI_A, window_area_m2, fill_factor, mean_turn_length_m, wire_diameter_m,
                material: ConductorMaterial, T_C) -> dict:
    """Integer-turn coil filling a winding window with round bare wire of ``wire_diameter_m`` [E5].

    N = floor(k A_w / A_cu) (refused if < 1); I = NI / N; R = rho(T) N l_mt / A_cu; P = I^2 R; V = I R; copper mass
    = density N l_mt A_cu (at T_ref). ``fill_factor`` is the bare-copper fraction of the window (insulation, bobbin and
    packing are inside it); no value is assumed.
    """
    NI = _pos(NI_A, "NI_A")
    A_w = _pos(window_area_m2, "window_area_m2")
    k = _real(fill_factor, "fill_factor")
    if not 0.0 < k < 1.0:
        raise ValueError(f"copper fill_factor must be in (0, 1), got {k!r}")
    l_mt = _pos(mean_turn_length_m, "mean_turn_length_m")
    d = _pos(wire_diameter_m, "wire_diameter_m")
    if not isinstance(material, ConductorMaterial):
        raise ValueError(f"material must be a ConductorMaterial, got {type(material).__name__}")
    A_cu = math.pi * d * d / 4.0
    N = math.floor(k * A_w / A_cu * (1.0 + 1e-12))
    if N < 1:
        raise ValueError(f"a {d * 1e3:.4g} mm wire does not fit once in {k:.3g} x {A_w:.4g} m^2 of copper area")
    I = NI / N
    R = wire_resistance_ohm(N * l_mt, A_cu, material, T_C)
    P = I * I * R
    return {"version": MAGNET_POWER_VERSION, "N_turns": N, "I_A": I, "R_ohm": R, "V_V": I * R, "P_W": P,
            "J_A_per_m2": I / A_cu, "wire_area_m2": A_cu, "fill_achieved": N * A_cu / A_w,
            "copper_mass_kg": material.density_kg_m3 * N * l_mt * A_cu, "T_C": float(T_C),
            "resistance_factor": resistance_factor(material, T_C), "material": material.name}


def electromagnet(B_gap_T, gap_length_m, gap_area_m2, core_segments, leakage_factor, window_area_m2, fill_factor,
                  mean_turn_length_m, wire_diameter_m, material: ConductorMaterial, T_C) -> dict:
    """Ampere-turns [E1] + integer-turn coil [E5]: the ``hall_magnet`` / ``ecr_magnet`` load at the coil terminals.

    Returns the circuit, the coil and ``P_load_W`` (= coil I^2 R), plus the gauge-independent continuous-limit power for
    comparison. The bus draw is P_load_W / (magnet-supply efficiency), which the caller takes from evidence data.
    """
    circ = ampere_turns(B_gap_T, gap_length_m, gap_area_m2, core_segments, leakage_factor)
    coil = coil_design(circ["NI_A"], window_area_m2, fill_factor, mean_turn_length_m, wire_diameter_m, material, T_C)
    P_cont = coil_power_continuous_W(circ["NI_A"], window_area_m2, fill_factor, mean_turn_length_m, material, T_C)
    return {"version": MAGNET_POWER_VERSION, "kind": "electromagnet", "circuit": circ, "coil": coil,
            "P_load_W": coil["P_W"], "P_continuous_limit_W": P_cont, "evidence_class": "model-derived"}


# ------------------------------------------------------------------------------------------- permanent magnet [E2]
def remanence_at_T(B_r_ref_T, alpha_Br_per_K, T_ref_C, T_C) -> float:
    """Linear reversible remanence B_r(T) = B_r,ref [1 + alpha (T - T_ref)]; every input explicit (caller's data sheet)."""
    B = _pos(B_r_ref_T, "B_r_ref_T")
    a = _real(alpha_Br_per_K, "alpha_Br_per_K")
    B_T = B * (1.0 + a * (_real(T_C, "T_C") - _real(T_ref_C, "T_ref_C")))
    if not B_T > 0.0:
        raise ValueError(f"remanence at {T_C} C is not positive ({B_T!r}); outside any linear model")
    return B_T


def permanent_magnet(B_gap_T, gap_length_m, gap_area_m2, core_segments, leakage_factor, magnet_area_m2, B_r_T,
                     mu_rec, H_knee_A_per_m, magnet_density_kg_m3) -> dict:
    """Magnet length and mass for a permanent-magnet circuit producing ``B_gap_T`` [E2]; electrical power 0 W.

    Flux continuity B_m = k B_g A_g / A_m; recoil line H_m = (B_m - B_r) / (mu0 mu_rec) (< 0); Ampere with no current
    l_m = (MMF_gap + MMF_core) / (-H_m). Refused if B_m >= B_r (the magnet area cannot carry the flux) or if
    -H_m > ``H_knee_A_per_m`` (operating point beyond the knee: irreversible demagnetization risk). ``B_r_T`` is the
    remanence at the operating temperature (see ``remanence_at_T``). For the bus-power boundary this is passed as
    ``P_load_W = 0.0`` with efficiency 1.0 (explicit), and the mass/thermal consequences go to the mass/thermal ledgers.
    """
    c = _circuit(B_gap_T, gap_length_m, gap_area_m2, core_segments, leakage_factor)
    A_m = _pos(magnet_area_m2, "magnet_area_m2")
    B_r = _pos(B_r_T, "B_r_T")
    mu = _real(mu_rec, "mu_rec")
    if mu < 1.0:
        raise ValueError(f"relative recoil permeability mu_rec must be >= 1, got {mu!r}")
    H_knee = _pos(H_knee_A_per_m, "H_knee_A_per_m (magnitude)")
    rho = _pos(magnet_density_kg_m3, "magnet_density_kg_m3")
    B_m = c["phi_core_Wb"] / A_m
    if B_m >= B_r:
        raise ValueError(f"magnet flux density {B_m:.4g} T >= remanence {B_r:.4g} T: magnet_area_m2 too small for the flux")
    H_m = (B_m - B_r) / (MU0_N_PER_A2 * mu)
    if -H_m > H_knee:
        raise ValueError(f"operating point |H_m| = {-H_m:.4g} A/m beyond the knee {H_knee:.4g} A/m "
                         f"(irreversible demagnetization); enlarge magnet_area_m2")
    F_ext = c["mmf_gap_A"] + c["mmf_core_A"]
    l_m = F_ext / (-H_m)
    V_m = l_m * A_m
    return {"version": MAGNET_POWER_VERSION, "kind": "permanent_magnet", "circuit": c, "B_m_T": B_m, "H_m_A_per_m": H_m,
            "magnet_length_m": l_m, "magnet_volume_m3": V_m, "magnet_mass_kg": rho * V_m,
            "P_load_W": 0.0, "evidence_class": "model-derived"}


# --------------------------------------------------------------------------------------------------- ECR field
def ecr_resonance_field_T(frequency_Hz, electron_mass_kg, elementary_charge_C) -> float:
    """Electron-cyclotron resonance field B = 2 pi f m_e / e; constants are explicit (CODATA values in the data file)."""
    f = _pos(frequency_Hz, "frequency_Hz")
    m = _pos(electron_mass_kg, "electron_mass_kg")
    e = _pos(elementary_charge_C, "elementary_charge_C")
    return 2.0 * math.pi * f * m / e

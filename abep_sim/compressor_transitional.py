"""Transitional-regime molecular-drag stage model -- CANDIDATE, NOT ADMITTED (owner A9.13 S6.8 OQ-F3-03, S6.11 OQ-F4-02).

Commissioned by the owner decision ``docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json``
(question ids OQ-F3-03 / S6.8 and OQ-F4-02 / S6.11): "Commission an open-literature transitional-regime compressor model
now ... until the transitional model has an admitted evidence basis and/or has been validated against the project
hardware: production/design evidence above the current 0.1 Pa free-molecular domain remains NOT_EVALUATED_OUT_OF_DOMAIN;
no extrapolated > 0.1 Pa result may be treated as a valid architecture point."

Model (the only open-literature drag-stage model with a closed-form, fully stated relation that this lane found and read;
source register and selection memo: ``docs/evidence/compressor_transitional/``):

  P. A. Skovorodko, "Continuum model for Couette-Poiseuille flow in a drag molecular pump", 23rd Int. Symp. on Rarefied
  Gas Dynamics (Whistler, 2002), abstract #151; arXiv:physics/0401020 (open access), Eq. (1).

  Plane channel of constant gap delta and length L, one wall moving at speed w, isothermal gas at T, parabolic velocity
  profile with first-order slip  du = lambda u'_y,  lambda = (2 - sigma)/sigma * mu c0 / p,  c0 = (pi R T / 2)^(1/2),
  inertia neglected ("for conditions typical of modern drag pumps the contribution of inertial term is small"),
  g = rho u_mean delta = mass flow per unit channel width:

      L = delta^2/(6 mu w) * [ p2 - p1 + (2/delta) * ( 3 (2 - sigma)/sigma * mu c0 + g R T / w )
                                                     * ln( p2 (w - 2 u(p2)) / (p1 (w - 2 u(p1))) ) ],
      u(p) = g R T / (p delta).

  Stated limits (same source): continuum dp = 6 mu w L / delta^2; free-molecular compression
  exp[sigma w L / ((2 - sigma) c0 delta)]; maximum throughput at u = w/2.  The source treats sigma as a FITTING
  parameter "derived from the compression ratio of the pump in the free molecular regime" (its own example: sigma = 0.6
  for Kanki's helium Holweck data).  This module therefore has NO default sigma: the caller supplies it with an
  evidence class.

Every coefficient is cited in ``COEFFICIENTS``.  Gas viscosity mu(T) (low-density limit) is transcribed from the NIST
Chemistry WebBook SRD 69 (snapshots in ``docs/evidence/compressor_transitional/sources/``), N2 and O2 only, 200-500 K.

Evidence status: every output carries ``evidence_status = "CANDIDATE_NOT_ADMITTED"`` and
``valid_design_evidence = False``; ``TransitionalResult.as_design_evidence()`` always raises ``NotAdmittedError``.
Any result touching a pressure above 0.1 Pa additionally carries ``architecture_point_status =
"NOT_EVALUATED_OUT_OF_DOMAIN"``.  Admission (a future, separate, owner-gated step) requires validation against T-1/T-2
hardware data or a pre-registered held-out published dataset: see the admission plan in the evidence JSON.  Admission
is NOT a flag in this module: there is no code path that returns an admitted result.

Gaps (refused, never approximated): turbomolecular blade rows in the transitional regime (no open model with stated
coefficients was found -> ``turbomolecular_row_transitional`` raises), gas mixtures (species coupling by collisions is
outside a single-gas model), atomic O (no viscosity source), groove side-wall / land-leakage / curvature / Siegbahn
centrifugal effects (plane-channel geometry only).

``compare_with_free_molecular`` runs the production ``abep_sim.compressor.DragCompressor`` (read-only import, never
modified, never mutated: a copy is configured) on one drag stage and compares it with this model in the overlap regime.

Not wired into archengine or abep_sim.design; nothing in the production chain imports this module.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Sequence

from .compressor import DragCompressor
from .constants import K_B, M_SPECIES

SCHEMA = "compressor_transitional_candidate_v1"
VERSION = "1.0.0"
MODEL_ID = "skovorodko2002_plane_couette_poiseuille_slip_eq1"

EVIDENCE_STATUS = "CANDIDATE_NOT_ADMITTED"
ARCH_OUT_OF_DOMAIN = "NOT_EVALUATED_OUT_OF_DOMAIN"
ARCH_NOT_DESIGN_EVIDENCE = "CANDIDATE_RESULT_NOT_DESIGN_EVIDENCE"

ST_OK = "SOLVED_CANDIDATE"
ST_THROUGHPUT = "THROUGHPUT_AT_OR_ABOVE_STAGE_CAPACITY"

EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed")

# Owner A9.13 S6.8: the free-molecular production domain ends at 0.1 Pa (same value as
# abep_sim.design.compressor_synthesis.P_MOLECULAR_LIMIT_PA, F3 P-MOLECULAR-LIMIT, Chiggiato 2013 Sec. 4.1.2).
P_FREE_MOLECULAR_LIMIT_PA = 0.1

# Barfuss (Pfeiffer Vacuum), CERN Accelerator School "Vacuum for Particle Accelerators", Lund 2017, slide 23:
# "Molecular flow Kn > 10; Knudsen flow Kn = 0,1...10; Viscous flow Kn < 0,1" (Kn definition not stated on the slide).
KN_FREE_MOLECULAR_MIN = 10.0

DECISION_REF = {
    "path": "docs/decisions/OD_2026_10_01_A9_13_s6_upstream_architecture_owner_decisions.json",
    "verbatim": "docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md",
    "question_ids": ["OQ-F3-03 (S6.8)", "OQ-F4-02 (S6.11)"],
}

_SKOVORODKO = ("P. A. Skovorodko, 'Continuum model for Couette-Poiseuille flow in a drag molecular pump', RGD-23 "
               "(Whistler 2002) abstract #151; arXiv:physics/0401020, Eq. (1) and bullet list")
_NIST = ("NIST Chemistry WebBook, SRD 69, Thermophysical Properties of Fluid Systems (isobaric, 0.001 bar), retrieved "
         "2026-10-01; underlying viscosity correlation reference not read (verify)")
_SHARIPOV = ("F. Sharipov, 'Rarefied gas dynamics and its applications to vacuum technology', CERN Accelerator School "
             "(open copy fisica.ufpr.br/sharipov/CERN.pdf), Eqs. (1)-(3)")

# Low-density viscosity, micro-Pa s, at 0.001 bar (100 Pa), transcribed exactly from the NIST WebBook responses
# committed in docs/evidence/compressor_transitional/sources/ (5 significant digits as served).
VISCOSITY_TABLE_uPa_s = {
    "N2": ((200.0, 12.889), (250.0, 15.483), (300.0, 17.877), (350.0, 20.107), (400.0, 22.200), (450.0, 24.177),
           (500.0, 26.056)),
    "O2": ((200.0, 14.693), (250.0, 17.772), (300.0, 20.631), (350.0, 23.304), (400.0, 25.821), (450.0, 28.203),
           (500.0, 30.470)),
}
GASES = tuple(sorted(VISCOSITY_TABLE_uPa_s))

COEFFICIENTS = MappingProxyType({
    "eq1_continuum_factor_6": {"value": 6.0, "source": _SKOVORODKO, "level": 6, "evidence_class": "model-derived",
                               "note": "from the assumed parabolic profile, a = 3(w - 2u)/(6 lambda delta + delta^2)"},
    "eq1_slip_factor_3(2-sigma)/sigma": {"value": "3*(2-sigma)/sigma", "source": _SKOVORODKO, "level": 6,
                                         "evidence_class": "model-derived",
                                         "note": "first-order slip lambda = (2-sigma)/sigma * mu c0 / p"},
    "c0": {"value": "sqrt(pi R T / 2)", "source": _SKOVORODKO, "level": 6, "evidence_class": "model-derived"},
    "R_specific": {"value": "k_B / m", "source": "abep_sim.constants (K_B exact SI; M_SPECIES project masses)",
                   "level": 4, "evidence_class": "model-derived"},
    "mu_T": {"value": "VISCOSITY_TABLE_uPa_s, linear in T between 50 K nodes", "source": _NIST, "level": 4,
             "evidence_class": "model-derived",
             "note": "evaluated correlation output transcribed; uncertainty not stated in the served table (TBD)"},
    "sigma": {"value": None, "source": "CALLER-SUPPLIED (fitting parameter per the source; no default)",
              "level": None, "evidence_class": "caller-declared",
              "note": "source example sigma = 0.6 for Kanki RGD-1994 helium Holweck data (not used as a default)"},
    "mean_free_path": {"value": "mu v_m / p, v_m = sqrt(2 k_B T / m)", "source": _SHARIPOV, "level": 4,
                       "evidence_class": "model-derived", "note": "Kn = l / gap (reporting only)"},
})

APPLICABILITY_DOMAIN = MappingProxyType({
    "geometry_class": "single long plane drag channel of constant gap (Gaede/Holweck/Siegbahn channels only as their "
                      "plane-channel approximation): groove side walls, land/clearance leakage, curvature, tapering, "
                      "centrifugal/Coriolis effects NOT modelled",
    "gas": "single-component N2 or O2 (mixtures and atomic O refused)",
    "temperature_K": [200.0, 500.0],
    "isothermal": True,
    "inertia": "neglected (source: small for typical drag pumps; not checked here)",
    "knudsen_author_claim": "continuum to free molecular, qualitative ('good qualitative representation')",
    "knudsen_quantitatively_validated": "NONE ESTABLISHED: the source's only comparison (Kanki, helium Holweck, "
                                        "sigma fitted) has unpublished-in-source geometry; validated Kn range not "
                                        "reconstructible",
    "pressure_production_domain_Pa": [0.0, P_FREE_MOLECULAR_LIMIT_PA],
})


class NotAdmittedError(RuntimeError):
    """Raised whenever a caller asks for a candidate result as design evidence."""


class OutOfModelDomainError(ValueError):
    """Gas, temperature, geometry or input outside the declared applicability domain."""


class NonConvergenceError(RuntimeError):
    """Root solve did not meet its residual tolerance (never returns a half-converged state)."""


class NotEvaluatedError(NotImplementedError):
    """A documented gap: no adequately documented open model exists."""


# --------------------------------------------------------------------------------------------- gas properties
def _require_gas(gas: str) -> None:
    if gas not in VISCOSITY_TABLE_uPa_s:
        raise OutOfModelDomainError(f"gas {gas!r} not supported (viscosity source exists only for {GASES}); "
                                    "atomic O and mixtures are outside the domain")


def viscosity_Pa_s(gas: str, T_K: float) -> float:
    _require_gas(gas)
    tab = VISCOSITY_TABLE_uPa_s[gas]
    if not (tab[0][0] <= T_K <= tab[-1][0]):
        raise OutOfModelDomainError(f"T = {T_K} K outside the transcribed viscosity range {tab[0][0]}-{tab[-1][0]} K")
    for (t0, m0), (t1, m1) in zip(tab, tab[1:]):
        if t0 <= T_K <= t1:
            return (m0 + (m1 - m0) * (T_K - t0) / (t1 - t0)) * 1e-6
    raise AssertionError("unreachable")


def specific_gas_constant(gas: str) -> float:
    _require_gas(gas)
    return K_B / M_SPECIES[gas]


def c0_mps(gas: str, T_K: float) -> float:
    """Skovorodko's c0 = (pi R T / 2)^(1/2)."""
    return math.sqrt(math.pi * specific_gas_constant(gas) * T_K / 2.0)


def mean_free_path_m(gas: str, T_K: float, p_Pa: float) -> float:
    """Sharipov's equivalent mean free path l = mu v_m / p (CERN school notes Eq. 2)."""
    if p_Pa <= 0:
        raise OutOfModelDomainError("pressure must be > 0")
    v_m = math.sqrt(2.0 * K_B * T_K / M_SPECIES[gas])
    return viscosity_Pa_s(gas, T_K) * v_m / p_Pa


def knudsen(gas: str, T_K: float, p_Pa: float, gap_m: float) -> float:
    return mean_free_path_m(gas, T_K, p_Pa) / gap_m


def sigma_from_free_molecular_xi(xi: float) -> float:
    """Accommodation sigma whose free-molecular compression equals DragCompressor's ln K0 = 2 u L xi / (c_bar h).

    Skovorodko FM: ln K0 = sigma/(2-sigma) * w L/(c0 delta); c_bar = sqrt(8RT/pi) so c0 = (pi/4) c_bar and
    xi = 2 sigma / (pi (2 - sigma))  ->  sigma = 2 pi xi / (2 + pi xi).  sigma <= 1 requires xi <= 2/pi."""
    if not (0.0 < xi <= 2.0 / math.pi):
        raise OutOfModelDomainError(f"xi = {xi} has no accommodation equivalent in (0, 1] (needs 0 < xi <= 2/pi)")
    return 2.0 * math.pi * xi / (2.0 + math.pi * xi)


# --------------------------------------------------------------------------------------------- stage
@dataclass(frozen=True)
class DragChannelStage:
    gap_m: float
    length_m: float
    width_m: float
    wall_speed_mps: float
    sigma: float
    sigma_evidence_class: str
    sigma_source: str

    def __post_init__(self):
        for name in ("gap_m", "length_m", "width_m", "wall_speed_mps"):
            v = getattr(self, name)
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
                raise OutOfModelDomainError(f"{name} must be a finite positive number, got {v!r}")
        if not (0.0 < self.sigma <= 1.0):
            raise OutOfModelDomainError(f"sigma must lie in (0, 1], got {self.sigma}")
        if self.sigma_evidence_class not in EVIDENCE_CLASSES:
            raise OutOfModelDomainError(f"sigma_evidence_class must be one of {EVIDENCE_CLASSES}")
        if not (isinstance(self.sigma_source, str) and self.sigma_source.strip()):
            raise OutOfModelDomainError("sigma_source is required (no hidden defaults)")


def _check_T(T_K: float) -> None:
    lo, hi = APPLICABILITY_DOMAIN["temperature_K"]
    if not (lo <= T_K <= hi):
        raise OutOfModelDomainError(f"T = {T_K} K outside {lo}-{hi} K")


def _terms(stage: DragChannelStage, gas: str, T_K: float, mdot_kgps: float):
    if mdot_kgps < 0 or not math.isfinite(mdot_kgps):
        raise OutOfModelDomainError("mass flow must be finite and >= 0")
    _check_T(T_K)
    mu = viscosity_Pa_s(gas, T_K)
    R = specific_gas_constant(gas)
    c0 = c0_mps(gas, T_K)
    g = mdot_kgps / stage.width_m
    d, w = stage.gap_m, stage.wall_speed_mps
    A = 2.0 * g * R * T_K / d                       # p (w - 2u(p)) = p w - A
    coef_ln = (2.0 / d) * (3.0 * (2.0 - stage.sigma) / stage.sigma * mu * c0 + g * R * T_K / w)
    pref = d * d / (6.0 * mu * w)
    return mu, R, c0, g, A, coef_ln, pref


def stage_length_m(stage: DragChannelStage, gas: str, T_K: float, p_in_Pa: float, p_out_Pa: float,
                   mdot_kgps: float) -> float:
    """Skovorodko Eq. (1): channel length that takes the gas from p_in to p_out at throughput mdot."""
    _, _, _, _, A, coef_ln, pref = _terms(stage, gas, T_K, mdot_kgps)
    w = stage.wall_speed_mps
    a1, a2 = p_in_Pa * w - A, p_out_Pa * w - A
    if a1 <= 0 or a2 <= 0:
        raise OutOfModelDomainError("throughput at or above the stage capacity (mean velocity >= w/2)")
    return pref * (p_out_Pa - p_in_Pa + coef_ln * math.log(a2 / a1))


def max_throughput_kgps(stage: DragChannelStage, gas: str, T_K: float, p_Pa: float) -> float:
    """Source: 'maximum throughput (p1 = p2) ... determined by u = w/2' -> mdot = p w delta W / (2 R T)."""
    _check_T(T_K)
    return p_Pa * stage.wall_speed_mps * stage.gap_m * stage.width_m / (2.0 * specific_gas_constant(gas) * T_K)


# --------------------------------------------------------------------------------------------- results
@dataclass(frozen=True)
class TransitionalResult:
    status: str
    candidate_values: Mapping[str, float]
    knudsen: Mapping[str, float]
    domain_flags: tuple
    architecture_point_status: str
    evidence_status: str = EVIDENCE_STATUS
    valid_design_evidence: bool = False
    model_id: str = MODEL_ID
    decision_ref: Mapping = field(default_factory=lambda: MappingProxyType(dict(DECISION_REF)))

    def __post_init__(self):
        if self.evidence_status != EVIDENCE_STATUS or self.valid_design_evidence:
            raise NotAdmittedError("the transitional model is not admitted; results cannot be marked otherwise")

    def as_design_evidence(self):
        raise NotAdmittedError(
            f"{MODEL_ID} is {EVIDENCE_STATUS}: candidate values are not design evidence (owner A9.13 S6.8 OQ-F3-03). "
            "Admission requires validation against T-1/T-2 hardware or a pre-registered held-out published dataset.")

    def to_dict(self) -> dict:
        return {"status": self.status, "candidate_values": dict(self.candidate_values),
                "knudsen": dict(self.knudsen), "domain_flags": list(self.domain_flags),
                "architecture_point_status": self.architecture_point_status,
                "evidence_status": self.evidence_status, "valid_design_evidence": self.valid_design_evidence,
                "model_id": self.model_id, "decision_ref": dict(self.decision_ref)}


def _result(status, values, gas, T_K, gap, pressures, extra_flags=()) -> TransitionalResult:
    flags = list(extra_flags)
    kn = {}
    for name, p in pressures.items():
        if p is not None and p > 0:
            kn[name] = knudsen(gas, T_K, p, gap)
    pmax = max((p for p in pressures.values() if p is not None), default=0.0)
    if pmax > P_FREE_MOLECULAR_LIMIT_PA:
        flags.append("PRESSURE_ABOVE_0.1_Pa_FREE_MOLECULAR_PRODUCTION_DOMAIN")
        arch = ARCH_OUT_OF_DOMAIN
    else:
        arch = ARCH_NOT_DESIGN_EVIDENCE
    if any(k < KN_FREE_MOLECULAR_MIN for k in kn.values()):
        flags.append("TRANSITIONAL_OR_VISCOUS_KN_QUANTITATIVELY_UNVALIDATED")
    flags.append("INERTIA_NEGLECTED_UNCHECKED")
    return TransitionalResult(status=status, candidate_values=MappingProxyType(dict(values)),
                              knudsen=MappingProxyType(kn), domain_flags=tuple(flags),
                              architecture_point_status=arch)


def _bisect(f, lo, hi, *, rel_tol=1e-13, max_iter=400):
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        raise NonConvergenceError("root not bracketed")
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm < 0) == (flo < 0):
            lo, flo = mid, fm
        else:
            hi, fhi = mid, fm
        if hi - lo <= rel_tol * max(abs(hi), abs(lo)):
            return 0.5 * (lo + hi)
    raise NonConvergenceError("bisection did not converge")


def solve_outlet_pressure(stage: DragChannelStage, gas: str, T_K: float, p_in_Pa: float,
                          mdot_kgps: float) -> TransitionalResult:
    """Outlet pressure reached in one stage from p_in at throughput mdot (Eq. 1 inverted for p2)."""
    if not (p_in_Pa > 0 and math.isfinite(p_in_Pa)):
        raise OutOfModelDomainError("p_in must be finite and > 0")
    _, _, _, g, A, _, _ = _terms(stage, gas, T_K, mdot_kgps)
    w = stage.wall_speed_mps
    if p_in_Pa * w - A <= 0:
        return _result(ST_THROUGHPUT, {"p_in_Pa": p_in_Pa, "mdot_kgps": mdot_kgps,
                                       "mdot_max_at_p_in_kgps": max_throughput_kgps(stage, gas, T_K, p_in_Pa)},
                       gas, T_K, stage.gap_m, {"inlet": p_in_Pa})
    L = stage.length_m
    f = lambda x: stage_length_m(stage, gas, T_K, p_in_Pa, math.exp(x), mdot_kgps) - L
    lo = math.log(p_in_Pa)
    hi = lo + 1.0
    n = 0
    while f(hi) < 0:
        hi += 1.0
        n += 1
        if n > 400:
            raise NonConvergenceError("outlet bracket not found")
    x = _bisect(f, lo, hi)
    p_out = math.exp(x)
    resid = abs(f(x)) / L
    if resid > 1e-9:
        raise NonConvergenceError(f"length residual {resid:.3e} above 1e-9")
    vals = {"p_in_Pa": p_in_Pa, "p_out_Pa": p_out, "compression_ratio": p_out / p_in_Pa, "mdot_kgps": mdot_kgps,
            "length_residual_rel": resid,
            "volumetric_speed_in_m3_s": mdot_kgps * specific_gas_constant(gas) * T_K / p_in_Pa,
            "mdot_max_at_p_in_kgps": max_throughput_kgps(stage, gas, T_K, p_in_Pa)}
    return _result(ST_OK, vals, gas, T_K, stage.gap_m, {"inlet": p_in_Pa, "outlet": p_out})


def solve_inlet_pressure(stage: DragChannelStage, gas: str, T_K: float, p_out_Pa: float,
                         mdot_kgps: float) -> TransitionalResult:
    """Inlet pressure sustained against a given outlet (fore-vacuum) pressure at throughput mdot."""
    if not (p_out_Pa > 0 and math.isfinite(p_out_Pa)):
        raise OutOfModelDomainError("p_out must be finite and > 0")
    _, _, _, g, A, _, _ = _terms(stage, gas, T_K, mdot_kgps)
    w = stage.wall_speed_mps
    p_floor = A / w
    if p_out_Pa <= p_floor:
        return _result(ST_THROUGHPUT, {"p_out_Pa": p_out_Pa, "mdot_kgps": mdot_kgps},
                       gas, T_K, stage.gap_m, {"outlet": p_out_Pa})
    L = stage.length_m
    span = p_out_Pa - p_floor
    # p_in = p_floor + span * exp(-y), y in [0, inf): length grows monotonically with y
    f = lambda y: stage_length_m(stage, gas, T_K, p_floor + span * math.exp(-y), p_out_Pa, mdot_kgps) - L
    hi = 1.0
    n = 0
    while f(hi) < 0:
        hi *= 2.0
        n += 1
        if n > 200:
            raise NonConvergenceError("inlet bracket not found")
    y = _bisect(f, 0.0, hi)
    p_in = p_floor + span * math.exp(-y)
    resid = abs(f(y)) / L
    if resid > 1e-9:
        raise NonConvergenceError(f"length residual {resid:.3e} above 1e-9")
    vals = {"p_in_Pa": p_in, "p_out_Pa": p_out_Pa, "compression_ratio": p_out_Pa / p_in, "mdot_kgps": mdot_kgps,
            "length_residual_rel": resid,
            "volumetric_speed_in_m3_s": mdot_kgps * specific_gas_constant(gas) * T_K / p_in}
    return _result(ST_OK, vals, gas, T_K, stage.gap_m, {"inlet": p_in, "outlet": p_out_Pa})


def cascade(stages: Sequence[DragChannelStage], gas: str, T_K: float, p_in_Pa: float,
            mdot_kgps: float) -> TransitionalResult:
    """Stages in series at constant throughput (no inter-stage leakage: not modelled)."""
    if not stages:
        raise OutOfModelDomainError("at least one stage required")
    p = p_in_Pa
    per_stage = []
    pressures = {"inlet": p_in_Pa}
    for i, st in enumerate(stages):
        r = solve_outlet_pressure(st, gas, T_K, p, mdot_kgps)
        if r.status != ST_OK:
            return _result(r.status, {"failed_stage": i, "p_stage_in_Pa": p, "mdot_kgps": mdot_kgps},
                           gas, T_K, st.gap_m, pressures)
        p = r.candidate_values["p_out_Pa"]
        per_stage.append(p)
        pressures[f"stage{i}_out"] = p
    vals = {"p_in_Pa": p_in_Pa, "p_out_Pa": p, "compression_ratio": p / p_in_Pa, "mdot_kgps": mdot_kgps}
    vals.update({f"p_stage{i}_out_Pa": v for i, v in enumerate(per_stage)})
    return _result(ST_OK, vals, gas, T_K, min(s.gap_m for s in stages), pressures,
                   extra_flags=("INTERSTAGE_LEAKAGE_NOT_MODELLED",))


def turbomolecular_row_transitional(*_args, **_kwargs):
    """Documented gap: no open-literature transitional-regime blade-row model with stated coefficients was found."""
    raise NotEvaluatedError(
        "turbomolecular blade rows in the transitional regime: no adequately documented open model found "
        "(Sharipov 2010 JVST A 28:1312 DSMC, Heo & Hwang 2000 Vacuum 56:133 are not open access); "
        "see docs/evidence/compressor_transitional/ gap memo. Above 0.1 Pa the result is NOT_EVALUATED_OUT_OF_DOMAIN.")


# --------------------------------------------------------------------------------------------- consistency check
def compare_with_free_molecular(compressor: DragCompressor, gas: str, p_in_Pa: float, mdot_kgps: float) -> dict:
    """Consistency check against the production free-molecular DragCompressor drag stage (overlap regime).

    One drag stage of ``compressor`` (h_mm, w_mm, L_per_stage_m, u, xi, T_gas_K), turbo rows switched off, run through
    DragCompressor.run(self_consistent=False) on a configured COPY (the caller's object is never mutated).  The candidate
    model uses the same geometry and wall speed and sigma = sigma_from_free_molecular_xi(xi), so the two free-molecular
    zero-flow compressions coincide by construction.  Reported differences then isolate (a) the slip/viscous correction
    of Eq. (1) and (b) the structural difference in pumping speed: DragCompressor applies xi to the speed too
    (S0 = xi u h w / 2), the plane-channel model does not (S0 = u h w / 2)."""
    if mdot_kgps <= 0:
        raise OutOfModelDomainError("DragCompressor needs a positive throughput (its composition step divides by it)")
    _require_gas(gas)
    dc = dataclasses.replace(compressor, turbo_rows=0, n_stages=1)
    sigma = sigma_from_free_molecular_xi(dc.xi)
    stage = DragChannelStage(gap_m=dc.h_mm * 1e-3, length_m=dc.L_per_stage_m, width_m=dc.w_mm * 1e-3,
                             wall_speed_mps=dc.u, sigma=sigma, sigma_evidence_class="model-derived",
                             sigma_source=f"mapped from DragCompressor xi = {dc.xi} (uncited code default, "
                                          "compressor_downselect CD-01)")
    T = dc.T_gas_K
    r_dc = dc.run(p_in_Pa, {gas: mdot_kgps}, self_consistent=False)
    r_tr = solve_outlet_pressure(stage, gas, T, p_in_Pa, mdot_kgps)
    cb = math.sqrt(8.0 * K_B * T / (math.pi * M_SPECIES[gas]))
    lnK0_dc = 2.0 * dc.u * dc.L_per_stage_m / (cb * dc.h_mm * 1e-3) * dc.xi
    lnK0_tr_fm = sigma / (2.0 - sigma) * dc.u * dc.L_per_stage_m / (c0_mps(gas, T) * dc.h_mm * 1e-3)
    kn_in = knudsen(gas, T, p_in_Pa, stage.gap_m)
    out = {
        "schema": SCHEMA + "/consistency_check",
        "gas": gas, "T_K": T, "p_in_Pa": p_in_Pa, "mdot_kgps": mdot_kgps,
        "xi": dc.xi, "sigma_mapped": sigma,
        "lnK0_free_molecular_DragCompressor": lnK0_dc,
        "lnK0_free_molecular_candidate_limit": lnK0_tr_fm,
        "S0_DragCompressor_m3_s": r_dc["S0_drag_m3_s"],
        "S0_candidate_plane_channel_m3_s": dc.u * stage.gap_m * stage.width_m / 2.0,
        "speed_ratio_DragCompressor_over_candidate": dc.xi,
        "K_DragCompressor": r_dc["CR_active"],
        "candidate_status": r_tr.status,
        "kn_in": kn_in,
        "evidence_status": EVIDENCE_STATUS, "valid_design_evidence": False,
    }
    if r_tr.status == ST_OK:
        K_tr = r_tr.candidate_values["compression_ratio"]
        out["K_candidate"] = K_tr
        out["kn_out"] = r_tr.knudsen["outlet"]
        out["lnK_rel_diff_candidate_vs_DragCompressor"] = (math.log(K_tr) - math.log(r_dc["CR_active"])) / \
            max(abs(math.log(r_dc["CR_active"])), 1e-300)
        p_max = max(p_in_Pa, r_tr.candidate_values["p_out_Pa"], r_dc["p_out_Pa"])
        kn_min = min(kn_in, out["kn_out"])
    else:
        p_max = max(p_in_Pa, r_dc["p_out_Pa"])
        kn_min = kn_in
    out["in_overlap_regime"] = bool(p_max <= P_FREE_MOLECULAR_LIMIT_PA and kn_min >= KN_FREE_MOLECULAR_MIN)
    # DragCompressor clips K to [1, K0] silently when Q exceeds S0 p_in (compressor_synthesis R_CLIP); flag it.
    q_pa_m3 = mdot_kgps * specific_gas_constant(gas) * T
    out["DragCompressor_characteristic_clipped"] = bool(q_pa_m3 >= r_dc["S0_drag_m3_s"] * p_in_Pa)
    out["comparable"] = bool(out["in_overlap_regime"] and r_tr.status == ST_OK
                             and not out["DragCompressor_characteristic_clipped"])
    out["architecture_point_status"] = (ARCH_OUT_OF_DOMAIN if p_max > P_FREE_MOLECULAR_LIMIT_PA
                                        else ARCH_NOT_DESIGN_EVIDENCE)
    return out

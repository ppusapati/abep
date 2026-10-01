"""Registered rotor-strength basis and rotor structural qualification (owner decision A9.9 S2.3 + S2.5 MCC-03).

Owner text (docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md, items 3 and 5/MCC-03), summarised:
rotor structural acceptance requires a REGISTERED rotor-strength basis record; margins are computed against BOTH yield
and ultimate; without a registered basis a rotor may only be explored as ``PARAMETRIC_SENSITIVITY`` and its
qualification is ``NOT_EVALUATED_MATERIAL_BASIS`` (``rotor_ok`` is never True). The uncited generic factor 2.0 on the
uncited ``materials.DB`` yield survives only as the labelled legacy/conservative sensitivity case
(``LEGACY_SENSITIVITY_LABEL``); it is not a cited requirement. A9.13 S6.9: aluminium and CFRP rotors re-enter only
through this same gate ("no material is admitted simply because a handbook strength number exists").

Stress model (unchanged from abep_sim/compressor.py): rim hoop stress sigma ~ rho u^2 at the largest rotor tip speed.

    margin_yield    = Fty(T_design) / (FS_yield    * sigma) - 1
    margin_ultimate = Ftu(T_design) / (FS_ultimate * sigma) - 1

Nothing here invents a number. ``REGISTRY`` is empty: no rotor stock/product form, design temperature, design/test
factors, maximum design speed or proof-spin basis has been registered by the owner (S2.3: "Once the rotor
manufacturing route is selected, register the applicable structural factors and proof-spin requirement before design
freeze"). ``REFERENCE_RECORDS`` carries the one cited value the project holds (Ti-6Al-4V annealed plate, 50.8-101.6 mm,
room temperature, A-basis, MMPDS-06 quoted by NASA-HDBK-6025) as an INCOMPLETE reference for THAT product form and
temperature only; it is never registered, never transferred to another product form and never qualifies a rotor.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------------------------- status vocabulary
SIZING_PARAMETRIC_SENSITIVITY = "PARAMETRIC_SENSITIVITY"
SIZING_REGISTERED_BASIS = "REGISTERED_BASIS"

Q_NOT_EVALUATED_MATERIAL_BASIS = "NOT_EVALUATED_MATERIAL_BASIS"
Q_NOT_EVALUATED_OUT_OF_DOMAIN = "NOT_EVALUATED_OUT_OF_DOMAIN"
Q_PASS = "PASS"
Q_FAIL = "FAIL"

LEGACY_SENSITIVITY_LABEL = ("LEGACY_CONSERVATIVE_SENSITIVITY: uncited materials.DB yield / uncited factor "
                            "DragCompressor.stress_safety (2.0); not a cited requirement, not a qualification basis "
                            "(owner decision A9.9 S2.3)")

OWNER_DECISION_ID = "A9.9 S2.3 (OQ-F3-01) + S2.5 MCC-03; A9.13 S6.9"


# --------------------------------------------------------------------------------------------- records
@dataclass(frozen=True)
class AllowablePoint:
    """Statistical allowables at one temperature (Pa, K)."""
    T_K: float
    Fty_Pa: float
    Ftu_Pa: float


@dataclass(frozen=True)
class RotorStrengthBasis:
    """One controlled rotor-strength basis record (all S2.3 minimum fields).

    materials_db_key            the abep_sim.materials.DB entry this basis applies to (no transfer to another key)
    material_spec               alloy/material specification (e.g. the procurement specification)
    product_form                actual rotor stock product form
    condition                   heat treatment / condition
    section_thickness_range_m   (min, max) stock thickness/section to which the allowables apply
    design_temperature_K        worst relevant rotor operating/design temperature
    allowable_basis             statistical basis (e.g. 'A-basis', 'B-basis')
    allowable_source            citation of the allowables
    allowables                  yield and ultimate versus temperature (sorted by T; no extrapolation)
    density_kg_m3, density_source   density from the SAME controlled material definition
    factor_yield, factor_ultimate, factors_source   applicable design/test factors and their source
    max_design_speed_rpm        maximum operating/design speed
    proof_spin_basis            proof-spin / qualification basis; None only with proof_spin_not_applicable_reason
    registration                owner registration reference (decision id / date)
    """
    basis_id: str
    materials_db_key: str
    material_spec: str
    product_form: str
    condition: str
    section_thickness_range_m: tuple
    design_temperature_K: float
    allowable_basis: str
    allowable_source: str
    allowables: tuple
    density_kg_m3: float
    density_source: str
    factor_yield: float
    factor_ultimate: float
    factors_source: str
    max_design_speed_rpm: float
    proof_spin_basis: Optional[str]
    registration: str
    proof_spin_not_applicable_reason: Optional[str] = None
    notes: str = ""


def _finite_pos(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def _text(x) -> bool:
    return isinstance(x, str) and x.strip() != ""


def basis_problems(b: RotorStrengthBasis) -> list:
    """Every reason this record is not a complete, admissible basis (empty list = complete)."""
    p = []
    for f in ("basis_id", "materials_db_key", "material_spec", "product_form", "condition", "allowable_basis",
              "allowable_source", "density_source", "factors_source", "registration"):
        if not _text(getattr(b, f)):
            p.append(f"{f} missing")
    st = b.section_thickness_range_m
    if not (isinstance(st, tuple) and len(st) == 2 and all(_finite_pos(v) for v in st) and st[0] <= st[1]):
        p.append("section_thickness_range_m must be a finite positive (min, max) with min <= max")
    if not _finite_pos(b.design_temperature_K):
        p.append("design_temperature_K missing or non-positive")
    if not _finite_pos(b.density_kg_m3):
        p.append("density_kg_m3 missing or non-positive")
    for f in ("factor_yield", "factor_ultimate"):
        v = getattr(b, f)
        if not (_finite_pos(v) and v >= 1.0):
            p.append(f"{f} must be finite and >= 1")
    if not _finite_pos(b.max_design_speed_rpm):
        p.append("max_design_speed_rpm missing or non-positive")
    if not _text(b.proof_spin_basis) and not _text(b.proof_spin_not_applicable_reason):
        p.append("proof_spin_basis missing (or an explicit proof_spin_not_applicable_reason)")
    pts = b.allowables
    if not (isinstance(pts, tuple) and len(pts) >= 1 and all(isinstance(a, AllowablePoint) for a in pts)):
        p.append("allowables (yield and ultimate versus temperature) missing")
    else:
        Ts = [a.T_K for a in pts]
        if any(not _finite_pos(v) for a in pts for v in (a.T_K, a.Fty_Pa, a.Ftu_Pa)):
            p.append("allowables contain non-finite or non-positive values")
        elif Ts != sorted(Ts) or len(set(Ts)) != len(Ts):
            p.append("allowables must be strictly increasing in temperature")
        elif any(a.Fty_Pa > a.Ftu_Pa for a in pts):
            p.append("allowables have Fty > Ftu")
        elif _finite_pos(b.design_temperature_K) and not (Ts[0] <= b.design_temperature_K <= Ts[-1]):
            p.append("design_temperature_K outside the tabulated allowables (no extrapolation)")
    return p


def allowables_at(b: RotorStrengthBasis, T_K: float) -> Optional[tuple]:
    """(Fty, Ftu) at T_K by linear interpolation inside the table; None outside it (no extrapolation)."""
    pts = b.allowables
    if not (pts[0].T_K <= T_K <= pts[-1].T_K):
        return None
    if len(pts) == 1:
        return pts[0].Fty_Pa, pts[0].Ftu_Pa
    for a, c in zip(pts[:-1], pts[1:]):
        if a.T_K <= T_K <= c.T_K:
            w = 0.0 if c.T_K == a.T_K else (T_K - a.T_K) / (c.T_K - a.T_K)
            return a.Fty_Pa + w * (c.Fty_Pa - a.Fty_Pa), a.Ftu_Pa + w * (c.Ftu_Pa - a.Ftu_Pa)
    return None


# --------------------------------------------------------------------------------------------- registry
# Controlled registry of ADMITTED bases. Empty: nothing has been registered (see the module docstring). Entries are
# added only through register_basis() from an owner-registered, cited record.
REGISTRY: dict = {}


def register_basis(b: RotorStrengthBasis) -> RotorStrengthBasis:
    """Admit a complete record into REGISTRY. Refuses an incomplete record or a duplicate id (no overwrite)."""
    probs = basis_problems(b)
    if probs:
        raise ValueError(f"rotor-strength basis {b.basis_id!r} is incomplete: {probs}")
    if b.basis_id in REGISTRY:
        raise ValueError(f"rotor-strength basis {b.basis_id!r} is already registered")
    REGISTRY[b.basis_id] = b
    return b


def unregister_basis(basis_id: str) -> None:
    REGISTRY.pop(basis_id, None)


def get_registered(basis_id: Optional[str]) -> Optional[RotorStrengthBasis]:
    return REGISTRY.get(basis_id) if basis_id else None


# Cited reference values that are NOT a registered basis (incomplete; never qualify a rotor; never transferred).
REFERENCE_RECORDS = {
    "REF-TI64-ANNEALED-PLATE-RT-ABASIS-MMPDS06": {
        "status": "INCOMPLETE_REFERENCE_NOT_REGISTERED",
        "materials_db_key": "Ti6Al4V",
        "product_form": "annealed plate",
        "condition": "annealed",
        "section_thickness_range_m": (0.0508, 0.1016),
        "temperature": "room temperature only (no elevated-temperature values held)",
        "allowable_basis": "A-basis",
        "Fty_Pa": 827e6,
        "Ftu_Pa": 896e6,
        "source": ("NASA-HDBK-6025 (2014-04-24) Sec. 3 'Mechanical Properties', p. 18 of 75, quoting MMPDS-06: "
                   "'the A-basis values of Ti-6Al-4V annealed plate with thickness of 50.8 to 101.6 mm (2 to 4 in) are: "
                   "tensile strength = 896 MPa (130 ksi); yield strength = 827 MPa (120 ksi)' (secondary quotation; "
                   "MMPDS itself not accessed); as recorded in docs/design_synthesis/f3_compressor (SRC-NASA-HDBK-6025)"),
        "missing_for_registration": ["actual rotor stock product form and section", "rotor design temperature and "
                                     "allowables at it", "density from the same controlled material definition",
                                     "design/test factors", "maximum design speed", "proof-spin basis",
                                     "owner registration"],
        "rule": "valid only for this product form, thickness range and temperature; never transferred (A9.9 S2.3)",
    },
}


# --------------------------------------------------------------------------------------------- qualification
def tip_speed_allowable(b: RotorStrengthBasis) -> float:
    """Largest tip speed with non-negative margins on both yield and ultimate at the design temperature (m/s)."""
    Fty, Ftu = allowables_at(b, b.design_temperature_K)
    s_allow = min(Fty / b.factor_yield, Ftu / b.factor_ultimate)
    return math.sqrt(s_allow / b.density_kg_m3)


def qualify_rotor(basis_id: Optional[str], rotor_material: str, tip_speed_mps: float, rpm: float,
                  T_rotor_K: float, stock_thickness_m: Optional[float]) -> dict:
    """Rotor structural qualification against a REGISTERED basis. Fail closed: any missing evidence gives
    NOT_EVALUATED_*; ``rotor_ok`` is True only for status PASS."""
    out = {"rotor_qualification": Q_NOT_EVALUATED_MATERIAL_BASIS, "rotor_ok": False,
           "rotor_strength_basis_id": basis_id, "rotor_qualification_reasons": [],
           "margin_yield": None, "margin_ultimate": None, "sigma_hoop_Pa": None,
           "u_allow_registered_mps": None, "owner_decision": OWNER_DECISION_ID}
    R = out["rotor_qualification_reasons"]
    b = get_registered(basis_id)
    if basis_id is None:
        R.append("no rotor-strength basis registered for this rotor")
        return out
    if b is None:
        R.append(f"basis {basis_id!r} is not in the registry")
        return out
    probs = basis_problems(b)
    if probs:                                   # defensive: REGISTRY admits complete records only
        R.extend(probs)
        return out
    if b.materials_db_key != rotor_material:
        R.append(f"basis applies to {b.materials_db_key!r}, rotor material is {rotor_material!r} (no transfer)")
        return out
    lo, hi = b.section_thickness_range_m
    if not _finite_pos(stock_thickness_m):
        R.append("rotor stock thickness/section not stated")
        return out
    if not (lo <= stock_thickness_m <= hi):
        R.append(f"rotor stock thickness {stock_thickness_m} m outside the basis section range [{lo}, {hi}] m")
        return out
    if not (isinstance(T_rotor_K, (int, float)) and math.isfinite(T_rotor_K)):
        out["rotor_qualification"] = Q_NOT_EVALUATED_OUT_OF_DOMAIN
        R.append("rotor temperature not finite")
        return out
    if T_rotor_K > b.design_temperature_K:
        out["rotor_qualification"] = Q_NOT_EVALUATED_OUT_OF_DOMAIN
        R.append(f"rotor temperature {T_rotor_K:.6g} K above the basis design temperature {b.design_temperature_K} K")
        return out
    Fty, Ftu = allowables_at(b, b.design_temperature_K)
    sigma = b.density_kg_m3 * tip_speed_mps ** 2
    my = Fty / (b.factor_yield * sigma) - 1.0 if sigma > 0 else math.inf
    mu = Ftu / (b.factor_ultimate * sigma) - 1.0 if sigma > 0 else math.inf
    out.update({"margin_yield": my, "margin_ultimate": mu, "sigma_hoop_Pa": sigma,
                "u_allow_registered_mps": tip_speed_allowable(b)})
    fails = []
    if my < 0:
        fails.append("yield margin negative")
    if mu < 0:
        fails.append("ultimate margin negative")
    if rpm > b.max_design_speed_rpm:
        fails.append(f"speed {rpm} rpm above the registered maximum design speed {b.max_design_speed_rpm} rpm")
    if fails:
        out["rotor_qualification"] = Q_FAIL
        R.extend(fails)
    else:
        out["rotor_qualification"] = Q_PASS
        out["rotor_ok"] = True
    return out

"""Installed-mass BOM v2 (parallel RF || Hall investigation).

``mass_bom_v1`` is untouched. v2 reuses its methodology (read-only import of the ESA/ECSS maturity categories and
the PROPOSED system-margin policy): CBE -> equipment maturity allowance (MGA) -> nominal dry -> system margin,
propellant separate (no MGA, no system margin), partial roll-up refusal.

Installed mass depends on the INSTALLED ARCHITECTURE only (rf_only / hall_only / rf_hall_parallel), never on the
operating mode:  M_installed = M_common + M_RF + M_Hall + M_Xe-system + M_Xe.

No mass is invented: every CBE starts as TBD. A caller may supply a sourced Quantity or an explicit
ASSUMED_SCREENING_VALUE (validation_status must say so). Loaded Xe comes from the mission ledger (xe_mission_v2).
Targets are reported separately from the RFP requirement: M_dry <= 28 kg and M_wet <= 35 kg are PROPOSED design
allocations; M_system < 40 kg is the RFP requirement (secondary transcription; whether Xe is inside is OD-XE-8).
"""
from __future__ import annotations

import math

from .mass_bom import MATURITY_CATEGORIES, SYSTEM_MARGIN          # methodology reuse (read-only)
from .parallel_contracts import (ContractError, Quantity, Status, SystemConstraints, TBD, serialise, value_of)
from .propulsion_modes import ArchitectureKind, InstalledArchitecture

BOM_VERSION = "mass_bom_v2"
SCOPES = ("common", "rf", "hall", "xe_system")
_NEW = "ecss_d_new_or_major_modification"
_PROP = "propellant_not_equipment"

# (id, name, scope, mass_class, PROPOSED maturity category)
CATALOG = (
    ("intake_structure", "intake structure", "common", "dry", _NEW),
    ("ao_filter", "AO/filter hardware", "common", "dry", _NEW),
    ("compressor_rotor_stator", "compressor rotor/stator", "common", "dry", _NEW),
    ("compressor_motor_bearings", "compressor motor/bearings", "common", "dry", _NEW),
    ("compressor_electronics", "compressor electronics", "common", "dry", _NEW),
    ("plenum", "plenum", "common", "dry", _NEW),
    ("atm_valve_metering", "atmospheric valve/metering", "common", "dry", _NEW),
    ("controller_fdir", "controller/FDIR", "common", "dry", _NEW),
    ("diagnostics", "diagnostics (flight telemetry subset)", "common", "dry", _NEW),
    ("harness", "harness", "common", "dry", "policy_allocation_nominal"),
    ("common_structure", "common structure", "common", "dry", _NEW),
    ("common_thermal", "common thermal", "common", "dry", _NEW),
    ("rf_chamber", "RF chamber", "rf", "dry", _NEW),
    ("rf_antenna_coupler", "RF antenna/coupler", "rf", "dry", _NEW),
    ("rf_magnetic_system", "RF magnetic system", "rf", "dry", _NEW),
    ("rf_generator", "RF generator", "rf", "dry", _NEW),
    ("rf_matching_network", "RF matching network", "rf", "dry", _NEW),
    ("rf_local_structure_thermal", "RF local structure/thermal", "rf", "dry", _NEW),
    ("hall_discharge_chamber", "Hall discharge chamber", "hall", "dry", _NEW),
    ("hall_magnetic_circuit", "Hall magnetic circuit", "hall", "dry", _NEW),
    ("lab6_cathode", "LaB6 cathode", "hall", "dry", _NEW),
    ("hall_ppu", "Hall PPU", "hall", "dry", _NEW),
    ("hall_local_structure_thermal", "Hall local structure/thermal", "hall", "dry", _NEW),
    ("xe_tank", "Xe tank", "xe_system", "dry", _NEW),
    ("xe_regulator", "regulator", "xe_system", "dry", _NEW),
    ("xe_valves", "valves", "xe_system", "dry", _NEW),
    ("xe_plumbing", "plumbing", "xe_system", "dry", _NEW),
    ("loaded_xe", "loaded Xe", "xe_system", "propellant", _PROP),
)
_BY_ID = {c[0]: c for c in CATALOG}
ARCH_SCOPES = {ArchitectureKind.RF_ONLY: ("common", "rf"), ArchitectureKind.HALL_ONLY: ("common", "hall", "xe_system"),
               ArchitectureKind.RF_HALL_PARALLEL: ("common", "rf", "hall", "xe_system")}
DESIGN_TARGETS = {"dry_kg": 28.0, "wet_kg": 35.0, "status": "PROPOSED_ENGINEERING_ALLOCATION",
                  "source": "ABEP Parallel RF-Hall Simulation v2 specification sec. 23"}


def installed_items(architecture: InstalledArchitecture) -> list[dict]:
    """The installed item set (mode-independent). rf_only carries the Xe system only if it is installed."""
    scopes = list(ARCH_SCOPES[architecture.kind])
    if architecture.kind is ArchitectureKind.RF_ONLY and architecture.xe_system_installed:
        scopes.append("xe_system")
    return [{"id": i, "name": n, "scope": s, "mass_class": mc, "maturity_category": cat,
             "maturity_category_status": "PROPOSED"}
            for i, n, s, mc, cat in CATALOG if s in scopes]


def _check_value(iid: str, v):
    if isinstance(v, TBD):
        return v
    if not isinstance(v, Quantity) or v.unit != "kg":
        raise ContractError(f"CBE of {iid!r} must be a Quantity in kg or a TBD")
    if v.value < 0:
        raise ContractError(f"CBE of {iid!r} must be >= 0")
    if v.quantity_type == "assumed" and "ASSUMED_SCREENING_VALUE" not in v.validation_status:
        raise ContractError(f"assumed CBE of {iid!r} must be labelled ASSUMED_SCREENING_VALUE in validation_status")
    return v


def rollup(architecture: InstalledArchitecture, cbe: dict, *, system_margin_fraction: float,
           constraints: SystemConstraints | None = None, allow_partial: bool = False) -> dict:
    """MEV = sum_dry CBE (1 + MGA) x (1 + system margin) + propellant. ``cbe``: item id -> Quantity | TBD (items not
    given are TBD). Refuses (ContractError) when anything is TBD unless allow_partial=True, which returns
    complete=False with no MEV (known-items sums only, explicitly not an architecture MEV)."""
    if not 0.0 <= system_margin_fraction < 1.0:
        raise ContractError("system_margin_fraction must be in [0, 1)")
    items = installed_items(architecture)
    unknown = sorted(set(cbe) - {it["id"] for it in items})
    if unknown:
        raise ContractError(f"CBE given for items not installed on {architecture.kind.value}: {unknown}")
    rows, missing = [], []
    for it in items:
        v = _check_value(it["id"], cbe.get(it["id"], TBD(it["id"], "no sourced mass yet")))
        mga = MATURITY_CATEGORIES[it["maturity_category"]]["mga"]
        row = {**it, "cbe": serialise(v), "mga": mga}
        if isinstance(v, TBD):
            missing.append(it["id"])
            row["cbe_kg"] = None
            row["with_mga_kg"] = None
        else:
            row["cbe_kg"] = v.value
            row["with_mga_kg"] = v.value * (1 + mga)
        rows.append(row)
    if missing and not allow_partial:
        raise ContractError(f"roll-up refused for {architecture.kind.value}: TBD items {missing}")
    dry = [r for r in rows if r["mass_class"] == "dry" and r["cbe_kg"] is not None]
    prop = [r for r in rows if r["mass_class"] == "propellant" and r["cbe_kg"] is not None]
    cbe_dry = math.fsum(r["cbe_kg"] for r in dry)
    nominal_dry = math.fsum(r["with_mga_kg"] for r in dry)
    margin = system_margin_fraction * nominal_dry
    propellant = math.fsum(r["cbe_kg"] for r in prop)
    by_scope = {s: math.fsum(r["with_mga_kg"] for r in dry if r["scope"] == s) for s in SCOPES}
    complete = not missing
    mev = nominal_dry + margin + propellant if complete else None
    out = {"bom_version": BOM_VERSION, "architecture": architecture.kind.value,
           "status": Status.PASS.value if complete else Status.INCOMPLETE_EVIDENCE.value, "complete": complete,
           "missing_items": missing, "items": rows,
           "system_margin": {"fraction": system_margin_fraction, "policy": SYSTEM_MARGIN["status"],
                             "basis": SYSTEM_MARGIN["basis"]},
           "cbe_dry_kg": cbe_dry, "nominal_dry_kg": nominal_dry, "system_margin_kg": margin,
           "propellant_kg": propellant, "nominal_dry_by_scope_kg": by_scope,
           "dry_mev_kg": (nominal_dry + margin) if complete else None, "mev_kg": mev,
           "note": None if complete else "PARTIAL: known-items sums only; NOT an architecture MEV",
           "design_targets": DESIGN_TARGETS}
    if complete and constraints is not None:
        hard_ok = constraints.mass_hard_ok(mev)
        out["checks"] = {
            "rfp_hard_limit": {"limit": constraints.mass_hard_max_kg.to_dict(), "mev_kg": mev, "pass": hard_ok},
            "design_dry_target": {"target_kg": DESIGN_TARGETS["dry_kg"], "within": nominal_dry + margin
                                  <= DESIGN_TARGETS["dry_kg"]},
            "design_wet_target": {"target_kg": DESIGN_TARGETS["wet_kg"], "within": mev <= DESIGN_TARGETS["wet_kg"]}}
        if not hard_ok:
            out["status"] = Status.INFEASIBLE_MASS.value
    return out


def loaded_xe_from_ledger(summary: dict, *, source: str) -> Quantity | TBD:
    """Loaded-Xe CBE from an xe_mission_v2 summary (the required total). TBD if the ledger is incomplete."""
    tot = summary.get("xe_total_required_kg")
    if tot is None:
        return TBD("loaded_xe", "Xe mission ledger incomplete (reserve/residual policy TBD)")
    return Quantity(tot, "kg", "model-derived", source, "inherits the mission-ledger inputs", "mission simulation",
                    "MODEL_DERIVED_FROM_MODE_HISTORY")

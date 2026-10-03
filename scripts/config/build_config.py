"""Build the authoritative input manifests under config/ (A9.22 layer separation, Phase A; no numerical change).

Owner directive 2026-10-03 (docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md + companion json):
REQUIREMENTS -> FROZEN ENGINEERING CONFIGURATION -> PHYSICS -> ASSESSMENT. This builder derives every config file from
the existing sources of record; it invents no number and never edits a source:

  architecture/hall_icp_neutralizer_v1.json   from the A9.19 / A9.20 / A9.15 owner decision records (hash-checked; the
                                              A9.19 verbatim sentences and the decision codes are verified in them)
  requirements/rfp_constraints_v1.json        from docs/requirements/rvm_a9/rvm_a9_v1.json row limit fields + the RFP
                                              registration; FROZEN / PROVISIONAL derived from the RVM requirement_frozen
                                              flags (never hard-coded)
  mission/mission_scenario_v1.json            operating-scenario inputs, values read from the snapshot just built
  environment/design_state_set_ref_v1.json    reference (id, path, sha256, manifest sha256) to the frozen design states
  hardware/hardware_bounds_v1.json            index of hardware-limit sources (path + sha256 + locator; no values)
  model_set/physics_model_set_v1.json         physics module sources, frozen data hashes, version labels in code
  README.md, MANIFEST.json                    description; every file + sha256

Usage: python scripts/config/build_config.py            write config/
       python scripts/config/build_config.py --check    regenerate in memory, compare byte for byte (exit 1 if stale)
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
GENERATED_BY = "scripts/config/build_config.py"
REGENERATE = "python scripts/config/build_config.py  (check: --check)"

RVM_REL = "docs/requirements/rvm_a9/rvm_a9_v1.json"
REG_REL = "docs/requirements/rfp_official/rfp_registration_v1.json"
A922 = {"md": "docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md",
        "json": "docs/decisions/OD_2026_10_03_A9_22_layer_separation_owner_decisions.json"}
A9_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json"

# Owner decision records the architecture is generated from (pins as carried by abep_sim/design/a9_19_architecture.py
# before Phase A; a changed record is refused, never followed)
DECISIONS = {
    "A9.19": {"md": "docs/decisions/OD_2026_10_01_A9_19_ARCHITECTURE_XE_CONTINGENCY_OWNER_DECISION.md",
              "md_sha256": "d3eae1d65f9b679a8538ce4a7c701a40a3f5d3b07d72baae944b685256931749",
              "json": "docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json",
              "json_sha256": "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16",
              "decision_code": "A9_19_SINGLE_HALL_ICP_NEUTRALIZER_NO_HOLLOW_CATHODE_XE_CONTINGENCY"},
    "A9.20": {"md": "docs/decisions/OD_2026_10_01_A9_20_C1_GROUND_ONLY_OWNER_DECISION.md",
              "md_sha256": "2b90a7a7f851ac571791ea6ba2fbafac8cf69a086a4a3724e2f66196b6b4d60c",
              "json": "docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json",
              "json_sha256": "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6",
              "decision_code": "C1_GROUND_ONLY_LABORATORY_REFERENCE"},
    "A9.15": {"md": "docs/decisions/OD_2026_10_01_A9_15_RFP_PROPELLANT_POLICY_OWNER_DECISION.md",
              "md_sha256": "edcf3019124084066501863ee314acc570e41f3b09757bcc8f8919b6295e3903",
              "json": "docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json",
              "json_sha256": "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
              "decision_code": "A9_15_RFP_COMPLIANT_PROPELLANT_POLICY"},
}
VERBATIM_A9_19 = ["One Hall accelerator.", "One RF/ICP electron-source/neutralizer.", "Two propellant supply modes.",
                  "No conventional hollow cathode."]


class BuildError(RuntimeError):
    pass


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(rel: str) -> str:
    p = ROOT / rel
    if not p.is_file():
        raise BuildError(f"source {rel} missing")
    return sha256_bytes(p.read_bytes())


def read_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def dumps(obj) -> bytes:
    return (json.dumps(obj, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def decision_ref(rel_json: str, rel_md: str | None = None) -> dict:
    r = {"json": rel_json, "json_sha256": sha256_file(rel_json)}
    if rel_md:
        r.update(md=rel_md, md_sha256=sha256_file(rel_md))
    return r


# ============================================================================================== architecture
def build_architecture() -> dict:
    for k, d in DECISIONS.items():
        if sha256_file(d["json"]) != d["json_sha256"] or sha256_file(d["md"]) != d["md_sha256"]:
            raise BuildError(f"owner decision record {k} changed; refused (records are immutable)")
        if read_json(d["json"]).get("decision") != d["decision_code"]:
            raise BuildError(f"owner decision record {k}: decision code differs from {d['decision_code']}")
    md19 = (ROOT / DECISIONS["A9.19"]["md"]).read_text(encoding="utf-8")
    missing = [s for s in VERBATIM_A9_19 if s not in md19]
    if missing:
        raise BuildError(f"A9.19 verbatim sentences not found in the record: {missing}")
    j19 = read_json(DECISIONS["A9.19"]["json"])["architecture"]
    if j19.get("hall_accelerators") != 1 or not str(j19.get("conventional_hollow_cathode", "")).startswith("NONE") \
            or len(j19.get("propellant_supply_modes", [])) != 2 or "RF/ICP" not in j19.get("electron_source_neutralizer", ""):
        raise BuildError("A9.19 record architecture block differs from the definition carried here")
    a9 = read_json(A9_REL)

    flight = "hall_icp_neutralizer"
    air, xe = "AIR_PRIMARY", "XE_CONTINGENCY"
    c1_role = {
        "status": "GROUND_ONLY_LAB_EQUIPMENT",
        "uses": ["H-1 I_d,max,H1,Ar characterization (A9.10 S3.5, independent of the ICP)",
                 "bench control in the C1-vs-ICP comparison"],
        "never": ["flight hardware", "flight mass budget", "flight power budget", "flight Xe budget",
                  "flight fallback / candidate flight configuration"],
        "authority": "A9.20 (C1_GROUND_ONLY_LABORATORY_REFERENCE); A9.19 amends 'A9 C1 CONTROL_FALLBACK'",
    }
    icp_feed = {"primary": "G-REUSE", "declared_variant": "G-XE",
                "status": "UNCHANGED (A9.1; A9.19 does not alter the ICP feed-gas baseline)"}
    flight_architecture = {
        "configuration": flight,
        "hall_accelerators": 1,
        "electron_source_neutralizer": {"count": 1, "kind": "RF/ICP (13.56 MHz) electron source / neutralizer, "
                                        "cathodeless / electrodeless", "serves_supply_modes": [air, xe]},
        "supply_modes": [
            {"mode": air, "role": "PRIMARY", "propellant": "ambient atmospheric propellant (180-230 km)",
             "path": ["intake", "filter", "compressor", "atmospheric_gas_chamber", "valve"]},
            {"mode": xe, "role": "CONTINGENCY_EMERGENCY", "propellant": "xenon",
             "path": ["xe_tank", "valve"],
             "note": "capability required by the RFP (RFP-P17-05 extra input system; RFP-P18-08 separate tank); role "
                     "contingency / emergency, not a parallel co-equal propellant (A9.19)"}],
        "separate_tanks": True,
        "conventional_hollow_cathode": "NONE",
        "icp_feed_gas_baseline": icp_feed,
        "c1": c1_role,
        "verbatim": list(VERBATIM_A9_19),
        "status": "OWNER_DECIDED_ARCHITECTURE_DEFINITION (A9 investigation; not a flight baseline, not a PASS)",
    }
    return {
        "schema": "abep_config_architecture_v1",
        "id": "hall_icp_neutralizer_v1",
        "layer": "FROZEN_ENGINEERING_CONFIGURATION",
        "title": "A9.19 / A9.20 / A9.15 flight architecture: one Hall accelerator + one RF/ICP electron source / "
                 "neutralizer; ambient air PRIMARY, Xe CONTINGENCY_EMERGENCY; separate tanks / paths; no conventional "
                 "hollow cathode; C1 ground-only laboratory reference",
        "status": "INVESTIGATION_HYPOTHESIS",
        "status_rule": "the architecture is an owner-decided definition of an investigation hypothesis; this file never "
                       "promotes it (not a flight baseline, not PASS / SELECTED / WINNER / QUALIFIED)",
        "a9_status": a9.get("status"),
        "generated_by": GENERATED_BY,
        "regenerate": REGENERATE,
        "loader": "abep_sim/design/a9_19_architecture.py (module constants load from this file; values unchanged)",
        "decision_records": {k: dict(v) for k, v in DECISIONS.items()},
        "governing_directive_a9_22": decision_ref(A922["json"], A922["md"]),
        "a9_record": {"path": A9_REL, "sha256": sha256_file(A9_REL)},
        "rfp_registration": REG_REL,
        "rfp_clauses": {"xe_extra_input": "RFP-P17-05", "two_tanks": "RFP-P18-08"},
        "verbatim_a9_19": list(VERBATIM_A9_19),
        "constants": {
            "flight_configuration": flight,
            "flight_configurations": [flight],
            "ground_reference_configuration": "hall_c1_reference",
            "ground_reference_label": "GROUND_REFERENCE",
            "ground_only_lab_equipment": "GROUND_ONLY_LAB_EQUIPMENT",
            "c1_role": c1_role,
            "supply_mode_air": air,
            "supply_mode_xe": xe,
            "supply_modes": [air, xe],
            "xe_path_role": "CONTINGENCY_EMERGENCY",
            "air_path_role": "PRIMARY",
            "supply_mode_gases": {air: ["N2", "NITROGEN", "O2", "OXYGEN", "O", "AIR", "N2/O2", "N2+O2", "N2_O2",
                                        "AMBIENT_AIR", "ATMOSPHERIC"],
                                  xe: ["XE", "XENON"]},
            "bench_engineering_gas": ["AR", "ARGON"],
            "bench_supply_mode": "BENCH_AR_ENGINEERING_GROUND_ONLY",
            "icp_feed_gas_baseline": icp_feed,
            "flight_architecture": flight_architecture,
        },
    }


# ============================================================================================== requirements
# RFPConstraints field -> (RVM row id, how the value is read from that row's limit). Values are never typed here.
def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise BuildError(f"expected a number, got {v!r}")
    return v


def _clause(reg: dict, cid: str) -> dict:
    for c in reg["clauses"]:
        if c["id"] == cid:
            return c
    raise BuildError(f"clause {cid} not in the RFP registration")


def build_requirements() -> dict:
    rvm = read_json(RVM_REL)
    reg = read_json(REG_REL)
    rows = {r["id"]: r for r in rvm["rows"]}
    clauses_sha = sha256_bytes(json.dumps(reg["clauses"], ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":")).encode("utf-8"))
    rb = rvm["rfp_rebase"]["registration"]
    if rb["clauses_sha256"] != clauses_sha:
        raise BuildError("RVM rfp_rebase clauses_sha256 differs from the registration clauses")

    def row(rid, key_prefix):
        # rows are addressed by id; the key prefix guards against a re-numbered RVM (a later key suffix may change)
        r = rows.get(rid)
        if r is None or not r["key"].startswith(key_prefix):
            raise BuildError(f"RVM {rid} missing or its key does not start with {key_prefix!r}")
        return r

    def ref(r):
        return {"rvm_row": r["id"], "rvm_key": r["key"], "rfp_clauses": list(r.get("rfp_clauses") or []),
                "requirement_origin": r.get("requirement_origin"), "requirement_frozen": bool(r.get("requirement_frozen")),
                "status": "FROZEN" if r.get("requirement_frozen") else "PROVISIONAL"}

    def lim(r):
        L = r.get("limit")
        if not L:
            raise BuildError(f"RVM {r['id']} has no limit")
        return {"quantity": L["quantity"], "comparator": L["comparator"], "value": L["value"], "units": L["units"]}

    alt, tmin, tmax = row("RVM-01", "ALTITUDE"), row("RVM-02", "THRUST_12MN"), \
        row("RVM-03", "THRUST_25MN")
    pbus, mass = row("RVM-04", "PBUS"), row("RVM-06", "MASS_LT_40KG")
    hall, firing = row("RVM-11", "HALL_PREF"), row("RVM-12", "FIRING")
    life, ic = row("RVM-13", "MISSION_LIFE"), row("RVM-18", "INDIGENOUS")

    lo, hi = (_num(x) for x in lim(alt)["value"])
    c_life = _clause(reg, "RFP-P19-01")
    m_legacy = re.search(r"Approx\s+(\d+)\s*hrs", c_life["text"])
    m_ign = re.search(r"More than\s+(\d+)\s*hrs", c_life["text"])
    if not m_legacy or not m_ign:
        raise BuildError("RFP-P19-01 text no longer carries the printed mission / ignition hours")
    legacy_mission_h = int(m_legacy.group(1))
    if int(m_ign.group(1)) != _num(lim(firing)["value"]):
        raise BuildError("RVM-12 firing limit differs from RFP-P19-01")
    c_ic = _clause(reg, "RFP-P19-05")
    ic_sub = {}
    for k, pat in (("thruster", r"Space Qualified Thruster\s*>(\d+)%"), ("intake", r"Intake system\s*>(\d+)%"),
                   ("compressor", r"Compressor and Storage\s*>(\d+)%"), ("pse", r"Power Supply Electronics\s*>(\d+)%")):
        m = re.search(pat, c_ic["text"])
        if not m:
            raise BuildError(f"RFP-P19-05: subsystem minimum {k} not found")
        ic_sub[k] = int(m.group(1)) / 100
    if lim(ic)["units"] != "%":
        raise BuildError("RVM-18 limit is not in %")
    c_hall = _clause(reg, "RFP-P18-07")
    if "preferable" not in c_hall["text"].lower():
        raise BuildError("RFP-P18-07 no longer states a Hall preference")

    used = [alt, tmin, tmax, pbus, mass, hall, firing, life, ic]
    n_frozen = sum(bool(r.get("requirement_frozen")) for r in used)
    status = "FROZEN" if n_frozen == len(used) else "PROVISIONAL"
    rfp_rows = [r for r in rvm["rows"] if r.get("requirement_origin") == "RFP_CLAUSE"]

    def c(value, r, note=None, **kw):
        e = {"value": value, **ref(r), **kw}
        if note:
            e["note"] = note
        return e

    compat = {
        "thrust_min_mN": c(_num(lim(tmin)["value"]), tmin),
        "thrust_max_mN": c(_num(lim(tmax)["value"]), tmax, "upper end of the printed thrust band RFP-P18-06 "
                           "'12 mN to 25 mN'; RVM-03 carries it as the >= 25 mN capability requirement"),
        "power_max_W": c(_num(lim(pbus)["value"]), pbus),
        "mass_max_kg": c(_num(lim(mass)["value"]), mass),
        "alt_min_km": c(lo, alt),
        "alt_max_km": c(hi, alt),
        "ignition_hours": c(_num(lim(firing)["value"]), firing, label="SUBSYSTEM_FIRING_LIFE_ASSUMPTION"),
        "mission_hours": c(legacy_mission_h, life, "LEGACY value still used by today's consumers (RFP-P19-01 prints "
                           "'Approx 26000 hrs'); the authoritative mission-duration basis is "
                           "mission_duration.authoritative_basis_h (A9.22 G1); a later lane performs the governed "
                           "migration", label="PENDING_GOVERNED_MIGRATION_A9_22_G1",
                           authoritative_basis_h=_num(lim(life)["value"])),
        "ic_total_min": c(_num(lim(ic)["value"]) / 100, ic, layer_target="ASSESSMENT (A9.22 G6)"),
        "ic_subsystem_min": c(ic_sub, ic, "RFP-P19-05 'Minimum Indigenization Desired' subsystem minima, read from "
                              "the registered clause text (printed as '>'; carried as the legacy minimum)",
                              layer_target="ASSESSMENT (A9.22 G6)", clause_text_source="RFP-P19-05"),
        "hall_preferred": c(True, hall, "RFP-P18-07 'Hall effect preferable' (a preference flag, not a numeric limit)",
                            layer_target="ASSESSMENT (A9.22 G6)", clause_text_source="RFP-P18-07"),
    }
    return {
        "schema": "abep_config_requirements_snapshot_v1",
        "id": "rfp_constraints_v1",
        "layer": "REQUIREMENTS",
        "title": "RFP-derived requirements snapshot generated from the RVM limit fields",
        "snapshot_status": status,
        "snapshot_status_rule": "FROZEN only when every RVM row this snapshot draws a value from has requirement_frozen "
                                "= true in the pinned RVM; otherwise PROVISIONAL (derived at build time, never "
                                "hard-coded). FROZEN freezes the requirements basis only; it never means compliance "
                                "(A9.22 G3).",
        "rows_used_frozen": f"{n_frozen}/{len(used)}",
        "rfp_clause_rows_frozen": f"{sum(bool(r.get('requirement_frozen')) for r in rfp_rows)}/{len(rfp_rows)}",
        "generated_by": GENERATED_BY,
        "regenerate": REGENERATE,
        "rvm": {"id": rvm["id"], "path": RVM_REL, "sha256": sha256_file(RVM_REL), "status": rvm.get("status")},
        "registration": {"path": REG_REL, "sha256": sha256_file(REG_REL), "rfp_number": rb["rfp_number"],
                         "pdf_sha256": rb["pdf_sha256"], "clauses_sha256": clauses_sha,
                         "clauses_hash_rule": rb["clauses_hash_rule"], "n_clauses": len(reg["clauses"])},
        "governing_directive_a9_22": decision_ref(A922["json"], A922["md"]),
        "physics_rule": "the physics layer never reads this file's clause ids or the RVM; it consumes values through "
                        "config/mission and the abep_sim.constants compatibility loader only",
        "mission_domain": {"altitude_km": [lo, hi], **ref(alt), "units": "km",
                           "provenance": "A9.22 G5: the 180-230 km check stays as a frozen mission / design-state "
                                         "domain constraint, consumed as mission_domain.altitude_km"},
        "mission_duration": {"authoritative_basis_h": _num(lim(life)["value"]), **ref(life),
                             "provenance": "A9.22 G1: 26,280 h is the authoritative mission-duration basis",
                             "rfp_printed_text": c_life["text"],
                             "legacy_mission_hours_in_use": legacy_mission_h,
                             "legacy_label": "PENDING_GOVERNED_MIGRATION_A9_22_G1"},
        "subsystem_firing_life": {"value_h": _num(lim(firing)["value"]), "comparator": lim(firing)["comparator"],
                                  **ref(firing), "label": "SUBSYSTEM_FIRING_LIFE_ASSUMPTION",
                                  "provenance": "A9.22 G1: 15,000 h only as an explicitly labelled subsystem "
                                                "firing / life assumption, never the mission duration"},
        "rvm_limits": [{**ref(r), "title": r["title"], "limit": lim(r)} for r in rvm["rows"] if r.get("limit")],
        "rfp_constraints_compat": compat,
    }


# ============================================================================================== mission scenario
CONSUMERS_LEGACY_26000 = [
    "abep_sim/constants.py RFPConstraints.mission_hours (via this config, value 26000)",
    "abep_sim/life.py LifeInputs.mission_h (literal 26000.0)",
    "abep_sim/mission5.py run_phase5 / run_mission_generic hours = RFP.mission_hours",
    "abep_sim/archengine.py firing_hours = RFP.mission_hours",
    "abep_sim/system.py fluence(atm, RFP.mission_hours); Budgets.duty_cycle",
    "abep_sim/mission_uq.py (docstring and horizon)",
]


def build_mission(snapshot: dict, snapshot_bytes: bytes) -> dict:
    comp = snapshot["rfp_constraints_compat"]

    def src(field_):
        e = comp[field_]
        return {"snapshot_field": f"rfp_constraints_compat.{field_}", "rvm_row": e["rvm_row"],
                "rfp_clauses": e["rfp_clauses"], "status": e["status"]}

    return {
        "schema": "abep_config_mission_scenario_v1",
        "id": "mission_scenario_v1",
        "layer": "FROZEN_ENGINEERING_CONFIGURATION",
        "title": "Operating-scenario inputs the physics takes today from the RFP constants (values unchanged)",
        "generated_by": GENERATED_BY,
        "regenerate": REGENERATE,
        "requirements_snapshot": {"id": snapshot["id"], "path": "config/" + "requirements/rfp_constraints_v1.json",
                                  "sha256": sha256_bytes(snapshot_bytes), "snapshot_status": snapshot["snapshot_status"]},
        "rule": "Phase A changes no consumer and no number: these are the values physics uses today. Switching a "
                "consumer to read this file is a later lane; the 26,000 -> 26,280 h change is the governed A9.22 G1 "
                "migration.",
        "inputs": {
            "altitude_domain_km": {"value": snapshot["mission_domain"]["altitude_km"], "units": "km",
                                   "source": {"snapshot_field": "mission_domain.altitude_km",
                                              "rvm_row": snapshot["mission_domain"]["rvm_row"]}},
            "xe_sizing_thrust_target_mN": {"value": comp["thrust_min_mN"]["value"], "units": "mN",
                                           "role": "thrust target for Xe sizing (today: RFP.thrust_min_mN)",
                                           "source": src("thrust_min_mN")},
            "commanded_thrust_cap_mN": {"value": comp["thrust_max_mN"]["value"], "units": "mN",
                                        "role": "commanded-thrust cap (today: RFP.thrust_max_mN)",
                                        "source": src("thrust_max_mN")},
            "p_bus_throttling_cap_W": {"value": comp["power_max_W"]["value"], "units": "W",
                                       "role": "P_bus throttling cap (today: RFP.power_max_W and literals 1500)",
                                       "source": src("power_max_W")},
            "mission_hours": {"authoritative_basis_h": snapshot["mission_duration"]["authoritative_basis_h"],
                              "legacy_mission_hours_in_use": comp["mission_hours"]["value"],
                              "legacy_label": "PENDING_GOVERNED_MIGRATION_A9_22_G1",
                              "units": "h",
                              "consumers_not_switched": CONSUMERS_LEGACY_26000,
                              "source": {"snapshot_field": "mission_duration", "rvm_row": comp["mission_hours"]["rvm_row"]}},
            "firing_hours": {"value": comp["ignition_hours"]["value"], "units": "h",
                             "label": "SUBSYSTEM_FIRING_LIFE_ASSUMPTION", "source": src("ignition_hours")},
        },
    }


# ============================================================================================== design-state reference
DS_REL = "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json"
DS_MANIFEST_REL = "abep_sim/data/atmosphere_msis21_orbit_v1.json"


def build_design_state_ref() -> dict:
    ds = read_json(DS_REL)
    man = read_json(DS_MANIFEST_REL)
    rec = man.get("design_states_file_v2") or {}
    sha = sha256_file(DS_REL)
    if rec.get("sha256") != sha or rec.get("file") != Path(DS_REL).name:
        raise BuildError("dataset manifest design_states_file_v2 does not record the design-state file hash")
    return {
        "schema": "abep_config_design_state_set_ref_v1",
        "id": ds["design_state_set_id"],
        "layer": "FROZEN_ENGINEERING_CONFIGURATION",
        "kind": "REFERENCE (never a copy)",
        "path": DS_REL,
        "sha256": sha,
        "n_states": ds["n_states"],
        "version": ds["version"],
        "dataset_id": ds["dataset_id"],
        "dataset_sha256": ds["dataset_sha256"],
        "manifest": {"path": DS_MANIFEST_REL, "sha256": sha256_file(DS_MANIFEST_REL),
                     "design_states_file_v2_sha256": rec["sha256"], "dataset_sha256": man.get("sha256")},
        "producer": ds["producer"],
        "loader": "abep_sim/design/intake_synthesis.py::load_design_state_set (DESIGN_STATE_SET_SHA256)",
        "altitude_domain_source": "config/requirements/rfp_constraints_v1.json mission_domain.altitude_km",
        "generated_by": GENERATED_BY,
    }


# ============================================================================================== hardware bounds index
HW_ENTRIES = [
    ("h1_freeze_candidate", "hardware_freeze_candidate", "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json",
     "parameters[*] / freeze_points / consistency_checks", "H-1 Hall accelerator freeze-candidate parameter set"),
    ("rotor_strength_registry", "rotor_strength_registry", "abep_sim/rotor_strength.py",
     "REGISTRY (empty: no registered basis) / REFERENCE_RECORDS", "registered rotor-strength bases (A9.9 S2.3)"),
    ("materials_db", "materials_database", "abep_sim/materials.py",
     "DB (Material.yield_MPa, T_max_K, ...; literature-class priors with fidelity tags)", "materials database"),
    ("thermal_life_limits", "thermal_node_limits", "schemas/thermal_life/limits_v1.json",
     "records[*] (sourced / TBD limits)", "sourced thermal / life limits"),
    ("thermal_node_model", "thermal_node_limits", "abep_sim/thermal.py",
     "Node.T_max_K; ThermalParams.radiator_T_max_K", "thermal-node limit fields of the 0-D thermal model"),
    ("h2_5_thermal_network", "thermal_node_limits", "docs/hardware/h2/h2_5_thermal_network/h2_5_thermal_network_v1.json",
     "limits[*] / node_list", "H2-5 thermal-network node limits"),
    ("compressor_legacy_caps", "compressor_legacy_caps", "abep_sim/compressor.py",
     "DragCompressor.stress_safety; DragCompressor.u_max_legacy_sensitivity(); size_for(rpm_max=...)",
     "LEGACY_CONSERVATIVE_SENSITIVITY tip-speed / rpm caps (not a qualification basis)"),
]


def build_hardware() -> dict:
    return {
        "schema": "abep_config_hardware_bounds_index_v1",
        "id": "hardware_bounds_v1",
        "layer": "FROZEN_ENGINEERING_CONFIGURATION",
        "kind": "INDEX (path + sha256 + locator; no value is copied)",
        "generated_by": GENERATED_BY,
        "entries": [{"id": i, "kind": k, "path": p, "sha256": sha256_file(p), "locator": loc, "role": role}
                    for i, k, p, loc, role in HW_ENTRIES],
    }


# ============================================================================================== physics model set
DATA_FILES = [
    "abep_sim/data/golden_v2.json", "abep_sim/data/golden_v1.json",
    "abep_sim/data/intake_surface_v1.json", "abep_sim/data/intake_surface_v1.csv",
    "abep_sim/data/atmosphere_msis21_v1.json", "abep_sim/data/atmosphere_msis21_v1.csv",
    "abep_sim/data/atmosphere_msis21_orbit_v1.json", "abep_sim/data/atmosphere_msis21_orbit_v1.csv.gz",
    "abep_sim/data/atmosphere_msis21_orbit_v1_design_states.json", DS_REL,
    "abep_sim/data/atmosphere_msis21_hwm14_orbit_v2.json", "abep_sim/data/atmosphere_msis21_hwm14_orbit_v2.csv.gz",
    "abep_sim/data/atmosphere_msis21_hwm14_orbit_v2.disturbance.csv.gz",
    "hallthruster_bridge/PINNED.toml", "hallthruster_bridge/propellants/rate_validity.toml",
]
_LABEL_RE = re.compile(r"(VERSION|SCHEMA|MODEL_ID|DATASET_ID|SPEC_ID)")


def _version_labels(src: str) -> dict:
    out = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and _LABEL_RE.search(node.targets[0].id) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            out[node.targets[0].id] = node.value.value
    return out


def build_model_set() -> dict:
    modules, flat = [], {}
    for p in sorted((ROOT / "abep_sim").glob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        labels = _version_labels(p.read_text(encoding="utf-8"))
        modules.append({"path": rel, "sha256": sha256_file(rel), "version_labels": labels})
        for k, v in labels.items():
            flat[f"{p.stem}.{k}"] = v
    rates = sorted(x.relative_to(ROOT).as_posix() for x in (ROOT / "abep_sim/data/rates").iterdir() if x.is_file())
    data = [{"path": r, "sha256": sha256_file(r)} for r in DATA_FILES + rates]
    pinned = tomllib.loads((ROOT / "hallthruster_bridge/PINNED.toml").read_text(encoding="utf-8"))
    nm = {"hallthruster.package": pinned["hallthruster"]["package"],
          "hallthruster.version": pinned["hallthruster"]["version"],
          "hallthruster.commit": pinned["hallthruster"]["commit"],
          "reaction_set.version": pinned["reaction_set"]["version"],
          "reaction_set.status": pinned["reaction_set"]["status"]}
    return {
        "schema": "abep_config_physics_model_set_v1",
        "id": "physics_model_set_v1",
        "layer": "PHYSICS",
        "scope": "abep_sim/*.py (the physics package; abep_sim/design/ is the design layer and is not listed)",
        "generated_by": GENERATED_BY,
        "regenerate": REGENERATE,
        "rule": "any change of a listed source or data file makes this model set stale (scripts/config/build_config.py "
                "--check); a physics change is a model change under CLAUDE.md rules 1-2",
        "modules": modules,
        "data": data,
        "version_labels_flat": flat,
        "numerical_methods_flat": nm,
    }


# ============================================================================================== README / manifest
README = """# config/ - authoritative input manifests (A9.22 layer separation, Phase A)

Generated by `scripts/config/build_config.py` (check: `--check`). Do not edit by hand: every file is pinned in
`MANIFEST.json` and `abep_sim/configuration.py` refuses a file whose sha256 differs (fail closed, no fallback).

Owner directive 2026-10-03 (`docs/decisions/OD_2026_10_03_A9_22_*`): four layers
REQUIREMENTS -> FROZEN ENGINEERING CONFIGURATION -> PHYSICS -> ASSESSMENT. The physics never reads or interprets the
RFP, the RVM or clause ids. Phase A changes no number (golden check unchanged).

| file | layer | content |
|---|---|---|
| `architecture/hall_icp_neutralizer_v1.json` | configuration | A9.19 / A9.20 / A9.15 flight architecture, status INVESTIGATION_HYPOTHESIS; loaded by `abep_sim/design/a9_19_architecture.py` |
| `requirements/rfp_constraints_v1.json` | requirements | snapshot generated from the RVM limit fields (row ids, clause ids, RVM + registration sha256); FROZEN / PROVISIONAL derived from `requirement_frozen`; `rfp_constraints_compat` feeds `abep_sim.constants.RFP` |
| `mission/mission_scenario_v1.json` | configuration | operating-scenario inputs (Xe-sizing thrust target, thrust cap, P_bus cap, mission / firing hours) with provenance to the snapshot; mission basis 26,280 h, `legacy_mission_hours_in_use` 26,000 PENDING_GOVERNED_MIGRATION_A9_22_G1 |
| `environment/design_state_set_ref_v1.json` | configuration | reference (never a copy) to the frozen design-state set v2 and its dataset manifest |
| `hardware/hardware_bounds_v1.json` | configuration | index (path + sha256 + locator) of hardware-limit sources; no copied values |
| `model_set/physics_model_set_v1.json` | physics | physics module sources, frozen data hashes, version labels, HallThruster.jl pin / reaction set |

`abep_sim.configuration.physics_configuration()` builds the `SimulationConfiguration` of a raw physics run without
opening the requirements snapshot; `assessment_configuration()` adds it.
"""


def build_all() -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    out["architecture/hall_icp_neutralizer_v1.json"] = dumps(build_architecture())
    snap = build_requirements()
    out["requirements/rfp_constraints_v1.json"] = snap_b = dumps(snap)
    out["mission/mission_scenario_v1.json"] = dumps(build_mission(snap, snap_b))
    out["environment/design_state_set_ref_v1.json"] = dumps(build_design_state_ref())
    out["hardware/hardware_bounds_v1.json"] = dumps(build_hardware())
    out["model_set/physics_model_set_v1.json"] = dumps(build_model_set())
    out["README.md"] = README.encode("utf-8")
    manifest = {"schema": "abep_config_manifest_v1", "id": "config_manifest_v1", "generated_by": GENERATED_BY,
                "regenerate": REGENERATE,
                "files": {k: {"sha256": sha256_bytes(v), "bytes": len(v)} for k, v in sorted(out.items())}}
    out["MANIFEST.json"] = dumps(manifest)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare the regenerated files with config/ (no write)")
    a = ap.parse_args(argv)
    files = build_all()
    if a.check:
        stale = [k for k, v in files.items() if not (CONFIG / k).is_file() or (CONFIG / k).read_bytes() != v]
        extra = sorted(p.relative_to(CONFIG).as_posix() for p in CONFIG.rglob("*")
                       if p.is_file() and p.relative_to(CONFIG).as_posix() not in files) if CONFIG.is_dir() else []
        if stale or extra:
            print(f"STALE: {stale}; unlisted files: {extra}")
            return 1
        print(f"OK: {len(files)} config files current")
        return 0
    for k, v in files.items():
        p = CONFIG / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(v)
    print(f"wrote {len(files)} files under config/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

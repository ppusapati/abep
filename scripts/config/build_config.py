"""Build the authoritative input manifests under config/ (A9.22 layer separation / A9.23; no numerical change).

Owner directive 2026-10-03 (docs/decisions/OD_2026_10_03_A9_22_LAYER_SEPARATION_OWNER_DECISIONS.md + companion json):
REQUIREMENTS -> FROZEN ENGINEERING CONFIGURATION -> PHYSICS -> ASSESSMENT (A9.23: docs/decisions/OD_2026_10_03_A9_23_*).
This builder derives every config file from the existing sources of record; it invents no number and never edits a
source:

  architecture/hall_icp_neutralizer_v1.json   from the A9.19 / A9.20 / A9.15 owner decision records (hash-checked; the
                                              A9.19 verbatim sentences and the decision codes are verified in them)
  requirements/rfp_constraints_v1.json        from docs/requirements/rvm_a9/rvm_a9_v1.json row limit fields + the RFP
                                              registration; FROZEN / PROVISIONAL derived from the RVM requirement_frozen
                                              flags (never hard-coded)
  constraints/engineering_constraints_v1.json frozen engineering constraints (A9.23), values read from the snapshot
                                              just built (requirements extraction -> engineering constraints; the
                                              only derivation path); requirement ids carried as provenance only
  mission/mission_scenario_v2.json            NOT GENERATED (A9.24 item 4): the frozen, independently versioned
                                              operating scenario; verified against abep_sim/configuration.py
                                              OPERATING_SCENARIO_PIN and listed in the manifest as it is (no value
                                              is derived from the constraints or the snapshot)
  mission/mission_scenario_v1.json            NOT GENERATED: historical scenario v1 (superseded), verified against
                                              MISSION_V1_SHA256 and listed as it is
  assessment/gate_thresholds_v1.json          assessment-layer HC-05..HC-12 thresholds (A9.24 item 5) with status /
                                              provenance per gate; HC-07 / HC-09 referenced from the constraints
  environment/design_state_set_ref_v1.json    reference (id, path, sha256, manifest sha256) to the frozen design states
  hardware/hardware_bounds_v1.json            index of hardware-limit sources (path + sha256 + locator; no values)
  model_set/physics_model_set_v1.json         physics module sources, frozen data hashes, version labels in code
  SOURCES_OF_TRUTH.json                       A9.23 index: one authoritative artefact per role (sha256 pinned)
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
A923 = {"md": "docs/decisions/OD_2026_10_03_A9_23_SIMULATION_ARCHITECTURE_OWNER_DIRECTIVE.md",
        "json": "docs/decisions/OD_2026_10_03_A9_23_simulation_architecture_owner_directive.json"}
A9_REL = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json"

# config-relative file names (one place)
ARCH_FILE = "architecture/hall_icp_neutralizer_v1.json"
REQ_FILE = "requirements/rfp_constraints_v1.json"
CONSTRAINTS_FILE = "constraints/engineering_constraints_v1.json"
MISSION_FILE = "mission/mission_scenario_v2.json"           # frozen, pinned, never generated (A9.24 item 4)
MISSION_V1_FILE = "mission/mission_scenario_v1.json"        # historical, never generated, never loaded
MISSION_V1_SHA256 = "a01b56a6ec7a79cb3b37c6356542d093c618632388edefb150881bf03fbe7ba0"
GATES_FILE = "assessment/gate_thresholds_v1.json"
A924 = {"md": "docs/decisions/OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md",
        "json": "docs/decisions/OD_2026_10_04_A9_24_rust_migration_and_open_items_owner_decisions.json"}
DS_REF_FILE = "environment/design_state_set_ref_v1.json"
HW_FILE = "hardware/hardware_bounds_v1.json"
MODEL_SET_FILE = "model_set/physics_model_set_v1.json"
SOT_FILE = "SOURCES_OF_TRUTH.json"

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
        "mission_hours": c(legacy_mission_h, life, "HISTORICAL value (RFP-P19-01 prints 'Approx 26000 hrs'), carried "
                           "only so the abep_sim.constants.RFP compatibility record (immutable, sha-pinned) stays "
                           "field-for-field identical; no consumer computes with it since the A9.22 G1 governed "
                           "migration was applied. The mission-duration basis is mission_duration.authoritative_basis_h "
                           "(26,280 h), consumed through config/mission/mission_scenario_v1.json",
                           label=HISTORICAL_LABEL, authoritative_basis_h=_num(lim(life)["value"]),
                           g1_status=G1_STATUS),
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
                             "g1_status": G1_STATUS,
                             "historical_mission_hours": {"value_h": legacy_mission_h, "label": HISTORICAL_LABEL,
                                                          "note": "pre-A9.22 basis; kept in abep_sim.constants.RFP "
                                                                  "(immutable) and in immutable history only"}},
        "subsystem_firing_life": {"value_h": _num(lim(firing)["value"]), "comparator": lim(firing)["comparator"],
                                  **ref(firing), "label": "SUBSYSTEM_FIRING_LIFE_ASSUMPTION",
                                  "provenance": "A9.22 G1: 15,000 h only as an explicitly labelled subsystem "
                                                "firing / life assumption, never the mission duration"},
        "rvm_limits": [{**ref(r), "title": r["title"], "limit": lim(r)} for r in rvm["rows"] if r.get("limit")],
        "rfp_constraints_compat": compat,
    }


# ============================================================================================== engineering constraints
def _limit_of(snapshot: dict, rvm_row: str) -> dict:
    """The RVM limit record (comparator / units / value) the snapshot carries for one row (provenance lookup only)."""
    for e in snapshot["rvm_limits"]:
        if e["rvm_row"] == rvm_row:
            return e["limit"]
    raise BuildError(f"requirements snapshot carries no rvm_limits entry for {rvm_row}")


def _prov(snapshot_field: str, e: dict) -> dict:
    """Provenance block of one constraint (labels only: never read by physics / design code)."""
    return {"snapshot_field": snapshot_field, "rvm_row": e["rvm_row"], "rvm_key": e["rvm_key"],
            "rfp_clauses": list(e["rfp_clauses"]), "requirement_origin": e.get("requirement_origin"),
            "requirement_frozen": bool(e["requirement_frozen"])}


def build_constraints(snapshot: dict, snapshot_bytes: bytes) -> dict:
    """Requirements extraction -> frozen engineering constraints (A9.23). Every value is read from the requirements
    snapshot just built (no number typed here); status FROZEN / PROVISIONAL from the snapshot row flags."""
    comp = snapshot["rfp_constraints_compat"]
    md, life, fire = snapshot["mission_domain"], snapshot["mission_duration"], snapshot["subsystem_firing_life"]
    rows = {e["rvm_row"]: e for e in snapshot["rvm_limits"]}

    def entry(value, units, comparator, kind, consumed_by, prov, status, **kw):
        return {"value": value, "units": units, "comparator": comparator, "kind": kind, "status": status,
                "consumed_by": consumed_by, **kw, "provenance": prov}

    def st(*es):
        return "FROZEN" if all(e["requirement_frozen"] for e in es) else "PROVISIONAL"

    alt_lim = _limit_of(snapshot, md["rvm_row"])
    tmin_lim, tmax_lim = _limit_of(snapshot, comp["thrust_min_mN"]["rvm_row"]), \
        _limit_of(snapshot, comp["thrust_max_mN"]["rvm_row"])
    pbus_lim, mass_lim = _limit_of(snapshot, comp["power_max_W"]["rvm_row"]), \
        _limit_of(snapshot, comp["mass_max_kg"]["rvm_row"])
    life_lim, fire_lim = _limit_of(snapshot, life["rvm_row"]), _limit_of(snapshot, fire["rvm_row"])
    ic_lim = _limit_of(snapshot, comp["ic_total_min"]["rvm_row"])
    air_row, xe_row = rows.get("RVM-08"), rows.get("RVM-10")
    if not air_row or not air_row["rvm_key"].startswith("ATMOSPHERIC_PROPELLANT") \
            or not xe_row or not xe_row["rvm_key"].startswith("XE_CAPABILITY"):
        raise BuildError("requirements snapshot: propellant-capability rows (atmospheric / Xe) not found")
    for got, want in ((comp["thrust_min_mN"]["value"], tmin_lim["value"]), (comp["power_max_W"]["value"],
                      pbus_lim["value"]), (comp["mass_max_kg"]["value"], mass_lim["value"]),
                      (md["altitude_km"], alt_lim["value"]), (life["authoritative_basis_h"], life_lim["value"]),
                      (fire["value_h"], fire_lim["value"]), (comp["ignition_hours"]["value"], fire["value_h"])):
        if got != want:
            raise BuildError(f"requirements snapshot is internally inconsistent ({got!r} != {want!r})")

    tmax = comp["thrust_max_mN"]
    constraints = {
        "altitude_band_km": entry(
            list(md["altitude_km"]), "km", alt_lim["comparator"], "DOMAIN",
            ["abep_sim/design/engineering_constraints.py MISSION_DOMAIN_ALTITUDE_KM (design-state domain check)",
             "frozen design-state set v2 domain validation (the states themselves are the physics input; owner "
             "ruling 2026-10-04: never an operating-scenario input)"],
            _prov("mission_domain.altitude_km", md), st(md),
            note="A9.22 G5: frozen mission / design-state domain constraint (mission_domain.altitude_km)"),
        "thrust_sustained_min_mN": entry(
            comp["thrust_min_mN"]["value"], "mN", tmin_lim["comparator"], "LIMIT",
            ["abep_sim/design/engineering_constraints.py THRUST_MIN_MN / HC-01"],
            _prov("rfp_constraints_compat.thrust_min_mN", comp["thrust_min_mN"]), comp["thrust_min_mN"]["status"]),
        "thrust_capability_mN": entry(
            tmax["value"], "mN", tmax_lim["comparator"], "LIMIT",
            ["abep_sim/design/engineering_constraints.py THRUST_MAX_MN / HC-02",
             "abep_sim/assessment/closure_checks.py Constraints.thrust_max_mN (peak-capability check)"],
            _prov("rfp_constraints_compat.thrust_max_mN", tmax), tmax["status"],
            note="upper end of the printed 12-25 mN thrust envelope; carried as the >= 25 mN capability requirement"),
        "p_bus_max_W": entry(
            comp["power_max_W"]["value"], "W", pbus_lim["comparator"], "LIMIT",
            ["abep_sim/design/engineering_constraints.py P_BUS_MAX_W / HC-03",
             "abep_sim/assessment/closure_checks.py Constraints.power_max_W",
             "abep_sim/assessment/arch_constraints.py default_limits power_max_W"],
            _prov("rfp_constraints_compat.power_max_W", comp["power_max_W"]), comp["power_max_W"]["status"]),
        "wet_mass_max_kg": entry(
            comp["mass_max_kg"]["value"], "kg", mass_lim["comparator"], "LIMIT",
            ["abep_sim/design/engineering_constraints.py M_WET_MAX_KG / HC-04",
             "abep_sim/assessment/arch_constraints.py design_constraints default m_max_kg (archengine search preset)",
             "abep_sim/assessment/closure_checks.py Constraints.mass_max_kg"],
            _prov("rfp_constraints_compat.mass_max_kg", comp["mass_max_kg"]), comp["mass_max_kg"]["status"]),
        "mission_life_h": entry(
            life["authoritative_basis_h"], "h", life_lim["comparator"], "LIMIT",
            ["config/mission/mission_scenario_v2.json mission_hours initial_basis (provenance only; the "
             "mission-integration horizon is an independently versioned operating choice, A9.24 item 4)"],
            _prov("mission_duration.authoritative_basis_h", life), life["status"],
            g1_status=life["g1_status"],
            historical_value={"value_h": comp["mission_hours"]["value"], "label": HISTORICAL_LABEL,
                              "note": "pre-A9.22 basis (abep_sim.constants.RFP.mission_hours, immutable); no consumer "
                                      "computes with it"}),
        "firing_life_h": entry(
            fire["value_h"], "h", fire_lim["comparator"], "LIMIT",
            ["config/assessment/gate_thresholds_v1.json HC-07 (assessment only, A9.24 item 5)",
             "abep_sim/assessment/arch_constraints.py design_constraints default life_min_h (via HC-07)",
             "config/mission/mission_scenario_v2.json firing_hours initial_basis (provenance only; the physics firing "
             "duration is an independent operating choice, owner ruling 2026-10-04)"],
            _prov("subsystem_firing_life.value_h", fire), fire["status"], label=fire["label"]),
        "propellant_capability": entry(
            {"ambient_atmosphere": air_row["limit"]["value"], "xe": xe_row["limit"]["value"]}, "-",
            {"ambient_atmosphere": air_row["limit"]["comparator"], "xe": xe_row["limit"]["comparator"]},
            "CATEGORICAL", ["assessment / compliance mapping only (no physics consumer)"],
            [_prov("rvm_limits[RVM-08]", air_row), _prov("rvm_limits[RVM-10]", xe_row)], st(air_row, xe_row),
            note="ambient atmospheric propellant primary + Xe-capable operating mode (architecture: "
                 "config/architecture/hall_icp_neutralizer_v1.json supply modes)"),
        "intake_drag_generation_limit_mN": entry(
            tmax["value"], "mN", "<=", "GENERATION_FILTER",
            ["abep_sim/design/engineering_constraints.py INTAKE_DRAG_GENERATION_LIMIT_N (F1 C-DRAG-RFP generation "
             "filter)", "config/assessment/gate_thresholds_v1.json HC-09 (also reported in assessment, A9.24 item 5)"],
            _prov("rfp_constraints_compat.thrust_max_mN", tmax), tmax["status"],
            derived_from="thrust_capability_mN",
            note="A9.22 G2 Option 1: C-DRAG-RFP stays a generation filter (intake-face drag <= thrust maximum); "
                 "Option 2 (assessment-only) is a separately approved change"),
        "ic_total_min": entry(
            comp["ic_total_min"]["value"], "fraction", ic_lim["comparator"], "PROGRAMME_METRIC_LIMIT",
            ["abep_sim/assessment/closure_checks.py Constraints.ic_total_min"],
            _prov("rfp_constraints_compat.ic_total_min", comp["ic_total_min"]), comp["ic_total_min"]["status"],
            layer="ASSESSMENT_ONLY (A9.22 G6)"),
        "ic_subsystem_min": entry(
            dict(comp["ic_subsystem_min"]["value"]), "fraction", ic_lim["comparator"], "PROGRAMME_METRIC_LIMIT",
            ["abep_sim/assessment/closure_checks.py Constraints.ic_thruster_min (thruster)"],
            _prov("rfp_constraints_compat.ic_subsystem_min", comp["ic_subsystem_min"]),
            comp["ic_subsystem_min"]["status"], layer="ASSESSMENT_ONLY (A9.22 G6)"),
        "hall_preferred": entry(
            comp["hall_preferred"]["value"], "-", "is", "CATEGORICAL_PREFERENCE",
            ["abep_sim/assessment/closure_checks.py (architecture-preference flag)"],
            _prov("rfp_constraints_compat.hall_preferred", comp["hall_preferred"]), comp["hall_preferred"]["status"],
            layer="ASSESSMENT_ONLY (A9.22 G6)"),
    }
    n_frozen = sum(c["status"] == "FROZEN" for c in constraints.values())
    return {
        "schema": "abep_config_engineering_constraints_v1",
        "id": "engineering_constraints_v1",
        "layer": "FROZEN_ENGINEERING_CONSTRAINTS",
        "title": "Frozen engineering constraints (values) consumed by the physics / design seams and the assessment "
                 "layer; derived from the requirements snapshot (requirements extraction -> engineering constraints)",
        "set_status": "FROZEN" if n_frozen == len(constraints) else "PROVISIONAL",
        "set_status_rule": "FROZEN only when every constraint is FROZEN; each constraint's status is derived from the "
                           "requirement_frozen flags its provenance rows carry in the requirements snapshot (never "
                           "hard-coded). FROZEN freezes the constraint basis only; it never means compliance.",
        "constraints_frozen": f"{n_frozen}/{len(constraints)}",
        "generated_by": GENERATED_BY,
        "regenerate": REGENERATE,
        "governing_directive_a9_23": decision_ref(A923["json"], A923["md"]),
        "rule": "A9.23: physics / design code consumes the values of this file only (abep_sim.configuration."
                "load_engineering_constraints; abep_sim/operating_inputs.py; abep_sim/design/engineering_constraints."
                "py); the assessment layer reads its limits here. Requirement / clause ids below are PROVENANCE ONLY: "
                "no code computes with them. The only derivation path is requirements snapshot -> this file "
                "(scripts/config/build_config.py).",
        "provenance": {"requirements_snapshot": {"id": snapshot["id"], "path": "config/" + REQ_FILE,
                                                 "sha256": sha256_bytes(snapshot_bytes),
                                                 "snapshot_status": snapshot["snapshot_status"]},
                       "role": "PROVENANCE_ONLY"},
        "constraints": constraints,
    }


# ============================================================================================== mission scenario
# A9.22 G1 (owner decision 2026-10-03): APPLIED. Mission-integrated consumers moved to 26,280 h through the single seam
# abep_sim/operating_inputs.py (which reads this file): life.LifeInputs.mission_h, mission5 hours, archengine
# mission-integrated Xe basis, system.py AO fluence / erosion / cathode starts / eng_R_mission (docs/HISTORY.md 'A9.22 G1
# governed baseline change' and '... (system.py completion)'). constants.RFP.mission_hours = 26000 is immutable
# (sha-pinned by immutable records) and is consumed by nothing.
G1_STATUS = "APPLIED"
HISTORICAL_LABEL = "HISTORICAL_CONSTANT_NOT_CONSUMED"
G1_MIGRATED_CONSUMERS = [
    "abep_sim/life.py LifeInputs.mission_h (default operating_inputs.MISSION_HOURS)",
    "abep_sim/mission5.py run_phase5 / run_mission_generic hours (default operating_inputs.MISSION_HOURS)",
    "abep_sim/archengine.py mission-integrated Xe basis (default operating_inputs.MISSION_HOURS)",
    "abep_sim/system.py AO fluence / erosion depths, cathode starts, eng_R_mission (operating_inputs.MISSION_HOURS)",
]


def _code_pin(name: str) -> dict:
    """A literal pin assigned in abep_sim/configuration.py (read with ast: importing abep_sim would load config/)."""
    for node in ast.parse((ROOT / "abep_sim/configuration.py").read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], "id", None) == name:
            return ast.literal_eval(node.value)
    raise BuildError(f"abep_sim/configuration.py carries no {name}")


def _frozen_scenario_bytes() -> tuple[bytes, bytes]:
    """A9.24 item 4: the operating scenario is a frozen, independently versioned artefact. It is never generated from
    the engineering constraints; this builder only verifies scenario v2 against its code-side pin
    (abep_sim/configuration.py OPERATING_SCENARIO_PIN) and the historical v1 against MISSION_V1_SHA256."""
    pin = _code_pin("OPERATING_SCENARIO_PIN")
    out = []
    for rel, want in ((MISSION_FILE, pin["sha256"]), (MISSION_V1_FILE, MISSION_V1_SHA256)):
        p = CONFIG / rel
        if not p.is_file():
            raise BuildError(f"config/{rel} missing (frozen scenario; never generated)")
        b = p.read_bytes()
        if sha256_bytes(b) != want:
            raise BuildError(f"config/{rel} sha256 {sha256_bytes(b)} != pinned {want}: a changed operating scenario "
                             "needs a new scenario version (A9.24 item 4)")
        out.append(b)
    d = json.loads(out[0])
    if (d.get("id"), d.get("scenario_version")) != (pin["id"], pin["scenario_version"]):
        raise BuildError(f"config/{MISSION_FILE}: id / scenario_version differ from the pin {pin}")
    return out[0], out[1]


# ============================================================================================== assessment gate thresholds
def build_gate_thresholds(constraints: dict) -> dict:
    """A9.24 item 5 (owner decision 2026-10-04): HC-05..HC-12 dispositions as assessment-layer thresholds. The values
    are the currently registered thresholds (identical to the former literals of abep_sim/design/engineering_
    constraints.py); HC-07 and HC-09 are value-free references to the engineering constraints (single source)."""
    c = constraints["constraints"]
    for cid in ("firing_life_h", "intake_drag_generation_limit_mN"):
        if cid not in c:
            raise BuildError(f"engineering constraints carry no {cid}")
    a924 = "A9.24 item 5 (" + A924["md"] + ")"

    def thr(value, units, comparator, layer, criterion, provenance, status="FROZEN", **kw):
        return {"kind": "THRESHOLD", "value": value, "units": units, "comparator": comparator, "status": status,
                "layer": layer, "criterion": criterion, **kw, "provenance": provenance}

    def ref(cid, units, scale, comparator, layer, criterion, provenance, **kw):
        return {"kind": "CONSTRAINT_REFERENCE", "constraint_ref": cid, "constraint_units": c[cid]["units"],
                "units": units, "scale_to_gate_units": scale, "comparator": comparator, "status": c[cid]["status"],
                "layer": layer, "criterion": criterion, **kw, "provenance": provenance}

    gates = {
        "HC-05": thr(0.0, "-", ">", "ASSESSMENT_ONLY",
                     "M_n,LB > 0, where M_n = I_e,cap / I_d,max,H1 - 1 and M_n,LB is its lower uncertainty bound; "
                     "the point difference I_e,cap - I_d,max is never the acceptance criterion; without uncertainty "
                     "evidence (a lower bound) for the inputs HC-05 is NOT_EVALUATED; physics produces the currents "
                     "and their uncertainties",
                     [a924, "owner correction 2026-10-04 (uncertainty-aware ratio form)",
                      "former HC-05 literal I_E_MARGIN_MIN_A = 0.0"],
                     evaluation_without_lower_bound="NOT_EVALUATED"),
        "HC-06": thr(50.0, "K", ">=", "ASSESSMENT_PROTECTION_POLICY",
                     "temperature margin >= 50 K below the validated hardware-bound temperature limits "
                     "(config/hardware/hardware_bounds_v1.json index); applied by assessment / protection logic, "
                     "never inside thermal equations; physics produces temperatures / heat loads",
                     [a924, "registered protection / acceptance margin (former HC-06 literal THERMAL_MARGIN_MIN_K)"]),
        "HC-07": ref("firing_life_h", "h", 1.0, ">", "ASSESSMENT_ONLY",
                     "predicted / measured subsystem firing life > the 15,000 h subsystem firing-life basis; the "
                     "mission duration (26,280 h, operating scenario) is separate",
                     [a924, "engineering constraint firing_life_h (single source)"]),
        "HC-08": thr(0.0, "N", ">=", "ASSESSMENT_ONLY",
                     "T_available(state) - D_spacecraft(state) >= 0 at every required state (statewise); physics "
                     "computes T and D independently",
                     [a924, "AG-13, owner decision A9.13 S6.15 (former HC-08 literal STATEWISE_T_MINUS_D_MIN_N)"]),
        "HC-09": ref("intake_drag_generation_limit_mN", "N", 1e-3, "<=",
                     "DESIGN_GENERATION_FILTER_ALSO_REPORTED_IN_ASSESSMENT",
                     "intake-face drag <= 25 mN at every orbit state: F1-F8 design-generation filter (A9.22 G2 "
                     "Option 1, read from the frozen engineering configuration, not RFP parsing) and reported in "
                     "assessment; assessment-only (C-DRAG-RFP Option 2) needs a separate owner approval",
                     [a924, "engineering constraint intake_drag_generation_limit_mN (single source)"]),
        "HC-10": thr(1.0, "-", ">=", "ASSESSMENT_ONLY",
                     "ambient atmospheric mode AND Xe contingency capability evaluated as architecture / capability "
                     "evidence (1 = both demonstrated); no physics equation carries this requirement",
                     [a924, "A9.15 RFP-compliant propellant policy (former HC-10 literal PROPELLANT_CAPABILITY_MIN)"]),
        "HC-11": thr(0.0, "-", ">=", "ASSESSMENT_ONLY",
                     "feed_available - feed_required >= 0 (statewise feed-state sufficiency, registered formulation: "
                     "minimum relative field margin); the requirement comes from the measured / validated H-1 "
                     "performance basis when available and is never reduced to the presently achievable feed",
                     [a924, "AG-12, owner decision A9.13 S6.21 (former HC-11 literal FEED_STATE_SUFFICIENCY_MIN)"]),
        "HC-12": thr(None, "-", "<=", "ASSESSMENT_ONLY",
                     "compressor / plenum ripple <= measured H-1 ripple tolerance; threshold TBD until measured H-1 "
                     "evidence establishes the permissible ripple basis; no default is invented",
                     [a924, "A9.13 S6.17 / S6.12 feed quality"], status="TBD_PENDING_MEASURED_H1",
                     evaluation_until_frozen="NOT_EVALUATED"),
    }
    return {
        "schema": "abep_config_gate_thresholds_v1",
        "id": "gate_thresholds_v1",
        "layer": "ASSESSMENT_THRESHOLDS",
        "title": "Hard-gate thresholds HC-05..HC-12 of the assessment layer (A9.24 item 5); physics / design modules "
                 "hold none of these values (HC-09 is also the design-generation filter, read from the engineering "
                 "constraints)",
        "generated_by": GENERATED_BY,
        "regenerate": REGENERATE,
        "governing_decision_a9_24": decision_ref(A924["json"], A924["md"]),
        "engineering_constraints": {"id": constraints["id"], "path": "config/" + CONSTRAINTS_FILE,
                                    "binding": "BY_ID (CONSTRAINT_REFERENCE gates)"},
        "rule": "read by abep_sim.configuration.load_gate_thresholds for the assessment layer "
                "(abep_sim/assessment/design_gates.py HARD_CONSTRAINT_LIMITS); a CONSTRAINT_REFERENCE gate carries no "
                "value (single source: the engineering constraints, x scale_to_gate_units); a TBD gate has value "
                "null and evaluates NOT_EVALUATED; changing a threshold changes the assessment only, never raw physics",
        "gates": gates,
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
        "altitude_domain_source": "config/constraints/engineering_constraints_v1.json constraints.altitude_band_km",
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


# ============================================================================================== source-of-truth index
# A9.23 (owner directive 2026-10-03): exactly one authoritative artefact per role. The raw / assessment result schemas
# are generated by scripts/config/build_result_schemas.py (they run the physics, so they are not rebuilt here); this
# index pins their sha256.
RESULT_SCHEMAS = {"raw": "schemas/results/raw_closure_v2.json", "assessment": "schemas/results/closure_assessment_v2.json"}
SOT_ROLES = ("frozen_architecture", "frozen_engineering_constraints", "frozen_design_state_set", "physics_model_set",
             "raw_simulation_result", "assessment_result", "requirements_provenance")


def build_sources_of_truth(files: dict[str, bytes]) -> dict:
    def cfg_entry(rel, layer, role_text, loader, **kw):
        d = json.loads(files[rel])
        return {"layer": layer, "artefact": "config/" + rel, "id": d["id"], "schema": d["schema"],
                "sha256": sha256_bytes(files[rel]), "pinned_by": ["config/MANIFEST.json"], "role": role_text,
                "loader": loader, **kw}

    def schema_entry(rel, layer, role_text, producer):
        if not (ROOT / rel).is_file():
            raise BuildError(f"{rel} missing: run python scripts/config/build_result_schemas.py")
        d = read_json(rel)
        return {"layer": layer, "artefact": rel, "id": d["$id"], "schema": d["$schema"], "sha256": sha256_file(rel),
                "pinned_by": ["config/SOURCES_OF_TRUTH.json"], "role": role_text, "producer": producer,
                "generated_by": d["x-abep"]["generated_by"]}

    ds_ref = json.loads(files[DS_REF_FILE])
    sources = {
        "frozen_architecture": cfg_entry(
            ARCH_FILE, "FROZEN_ARCHITECTURE", "architecture_frozen_v1: the single flight architecture definition",
            "abep_sim.configuration.load_architecture; abep_sim/design/a9_19_architecture.py"),
        "frozen_engineering_constraints": cfg_entry(
            CONSTRAINTS_FILE, "FROZEN_ENGINEERING_CONSTRAINTS",
            "engineering_constraints_v1: every frozen numerical / categorical constraint (values; provenance only "
            "for requirement ids)",
            "abep_sim.configuration.load_engineering_constraints; abep_sim/design/engineering_constraints.py; "
            "abep_sim/operating_inputs.py; abep_sim/assessment"),
        "frozen_design_state_set": {
            "layer": "FROZEN_DESIGN_STATE_SET", "artefact": ds_ref["path"], "id": ds_ref["id"],
            "alias": "vleo_design_states_v2", "n_states": ds_ref["n_states"], "sha256": ds_ref["sha256"],
            "reference": "config/" + DS_REF_FILE, "reference_sha256": sha256_bytes(files[DS_REF_FILE]),
            "pinned_by": [f"{ds_ref['manifest']['path']} (design_states_file_v2.sha256)", "config/" + DS_REF_FILE],
            "role": "the frozen environmental / orbital design states consumed by the design / physics runs",
            "loader": "abep_sim.configuration.load_design_state_set_ref; " + ds_ref["loader"]},
        "physics_model_set": cfg_entry(
            MODEL_SET_FILE, "PHYSICS_MODELS", "physics_model_set_v1: physics module / data hashes and version labels",
            "abep_sim.configuration.load_model_set / model_set_drift"),
        "raw_simulation_result": schema_entry(
            RESULT_SCHEMAS["raw"], "RAW_RESULTS", "schema raw_closure_v2 of the raw physical result",
            "abep_sim.system.physics_closure"),
        "assessment_result": schema_entry(
            RESULT_SCHEMAS["assessment"], "ASSESSMENT", "schema closure_assessment_v2 of the assessment / "
            "compliance result (raw result + frozen constraints)", "abep_sim.assessment.assess"),
        "requirements_provenance": cfg_entry(
            REQ_FILE, "PROVENANCE", "requirements-extraction snapshot (RVM / RFP clause provenance); the only input "
                                    "of the engineering constraints; never read by physics / design code",
            "abep_sim.configuration.load_requirements_snapshot (assessment / compliance mapping only)",
            snapshot_status=json.loads(files[REQ_FILE])["snapshot_status"]),
    }
    if tuple(sources) != SOT_ROLES:
        raise BuildError("source-of-truth roles differ from SOT_ROLES")
    return {
        "schema": "abep_sources_of_truth_v1",
        "id": "sources_of_truth_v1",
        "generated_by": GENERATED_BY,
        "regenerate": REGENERATE,
        "governing_directive_a9_23": decision_ref(A923["json"], A923["md"]),
        "dependency_rule": [
            "requirements/provenance -> frozen engineering constraints (scripts/config/build_config.py only)",
            "architecture + frozen constraints + design states + physics -> raw results",
            "raw results + frozen constraints -> assessment / compliance",
        ],
        "rule": "exactly one authoritative artefact per role; no second file may claim a listed role (same schema id "
                "or artefact id); tests/test_a9_23_dependency_rule.py enforces it",
        "supporting_inputs": {
            "operating_scenario": {"artefact": "config/" + MISSION_FILE, "sha256": sha256_bytes(files[MISSION_FILE]),
                                   "role": "frozen, independently versioned operating-scenario choices (A9.24 item 4; "
                                           "constraint-derived inputs referenced, not restated)",
                                   "pinned_by": ["abep_sim/configuration.py OPERATING_SCENARIO_PIN",
                                                 "config/MANIFEST.json"],
                                   "supersedes": {"artefact": "config/" + MISSION_V1_FILE,
                                                  "sha256": sha256_bytes(files[MISSION_V1_FILE]),
                                                  "status": "HISTORICAL_SUPERSEDED_NOT_LOADED"}},
            "assessment_gate_thresholds": {"artefact": "config/" + GATES_FILE,
                                           "sha256": sha256_bytes(files[GATES_FILE]),
                                           "role": "HC-05..HC-12 assessment thresholds (A9.24 item 5)",
                                           "loader": "abep_sim.configuration.load_gate_thresholds"},
            "hardware_bounds_index": {"artefact": "config/" + HW_FILE, "sha256": sha256_bytes(files[HW_FILE]),
                                      "role": "index of hardware-limit sources (no copied values)"},
        },
        "sources": sources,
    }


# ============================================================================================== README / manifest
README = """# config/ - authoritative input manifests (A9.22 layer separation; A9.23 simulation architecture)

Generated by `scripts/config/build_config.py` (check: `--check`). Do not edit by hand: every file is pinned in
`MANIFEST.json` and `abep_sim/configuration.py` refuses a file whose sha256 differs (fail closed, no fallback).

Owner directives 2026-10-03 (`docs/decisions/OD_2026_10_03_A9_22_*`, `docs/decisions/OD_2026_10_03_A9_23_*`):

    requirements / provenance                    -> frozen engineering constraints   (this builder only)
    architecture + constraints + design states + physics -> raw results
    raw results + frozen constraints             -> assessment / compliance

The physics never reads or interprets the RFP, the RVM or clause ids: physics / design seams read the values of
`constraints/engineering_constraints_v1.json` (and the operating choices of `mission/`), never `requirements/`. The
requirements snapshot is the provenance layer; the assessment layer reads it only for compliance mapping /
requirement ids. Phase A changed no number; the A9.22 G1 mission-basis change (26,280 h) is the only governed
numerical change routed through these files (docs/HISTORY.md).

| file | layer | content |
|---|---|---|
| `architecture/hall_icp_neutralizer_v1.json` | frozen architecture | A9.19 / A9.20 / A9.15 flight architecture, status INVESTIGATION_HYPOTHESIS; loaded by `abep_sim/design/a9_19_architecture.py` |
| `constraints/engineering_constraints_v1.json` | frozen engineering constraints | every frozen numerical / categorical constraint (altitude band, thrust envelope, P_bus, wet mass, mission life, firing-life assumption, propellant capability, C-DRAG generation limit, IC minima, Hall preference) with units, comparator, FROZEN / PROVISIONAL status and provenance (snapshot sha256 + row / clause ids as provenance only); generated from the requirements snapshot |
| `requirements/rfp_constraints_v1.json` | requirements (provenance) | snapshot generated from the RVM limit fields (row ids, clause ids, RVM + registration sha256); FROZEN / PROVISIONAL derived from `requirement_frozen`; the only input of the engineering constraints |
| `mission/mission_scenario_v2.json` | operating scenario (frozen, not generated) | A9.24 item 4: independently versioned operating-scenario choices (Xe-sizing thrust target 12 mN, commanded-thrust cap 25 mN, P_bus throttling cap 1500 W, mission-integration horizon 26,280 h, A9.22 G1 APPLIED), each with `initial_basis` provenance naming the engineering constraint (never re-read), plus value-free references by id to the constraints it does not restate (altitude band, wet mass, firing life); pinned by id + scenario_version + sha256 in `abep_sim/configuration.py` OPERATING_SCENARIO_PIN; read by `abep_sim/operating_inputs.py`. A changed scenario needs a new version |
| `mission/mission_scenario_v1.json` | historical | superseded scenario v1 (choices regenerated from the constraints); kept byte-identical, never loaded |
| `assessment/gate_thresholds_v1.json` | assessment thresholds | A9.24 item 5: HC-05..HC-12 thresholds with layer / status / provenance per gate (HC-07, HC-09 referenced from the constraints; HC-12 null, TBD_PENDING_MEASURED_H1 -> NOT_EVALUATED); read by `abep_sim.configuration.load_gate_thresholds` for `abep_sim/assessment/design_gates.py` |
| `environment/design_state_set_ref_v1.json` | frozen design states | reference (never a copy) to the frozen design-state set v2 and its dataset manifest |
| `hardware/hardware_bounds_v1.json` | configuration | index (path + sha256 + locator) of hardware-limit sources; no copied values |
| `model_set/physics_model_set_v1.json` | physics | physics module sources, frozen data hashes, version labels, HallThruster.jl pin / reaction set |
| `SOURCES_OF_TRUTH.json` | index | the one authoritative artefact per role (below) |

## Sources of truth (A9.23)

`SOURCES_OF_TRUTH.json` names exactly one authoritative artefact per role; `tests/test_a9_23_dependency_rule.py`
checks each exists, matches its pin, and that no second file claims the same role.

| role | authoritative artefact | pinned by |
|---|---|---|
| frozen architecture | `config/architecture/hall_icp_neutralizer_v1.json` | `config/MANIFEST.json` |
| frozen engineering constraints | `config/constraints/engineering_constraints_v1.json` | `config/MANIFEST.json` |
| frozen design-state set (vleo_design_states_v2) | `abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json` via `config/environment/design_state_set_ref_v1.json` | dataset manifest `abep_sim/data/atmosphere_msis21_orbit_v1.json` + the config reference |
| physics model / version set | `config/model_set/physics_model_set_v1.json` | `config/MANIFEST.json` |
| raw simulation result | schema `raw_closure_v2` = `schemas/results/raw_closure_v2.json` (producer `abep_sim.system.physics_closure`) | `config/SOURCES_OF_TRUTH.json` |
| assessment / compliance result | schema `closure_assessment_v2` = `schemas/results/closure_assessment_v2.json` (producer `abep_sim.assessment.assess`) | `config/SOURCES_OF_TRUTH.json` |
| requirements (provenance layer) | `config/requirements/rfp_constraints_v1.json` | `config/MANIFEST.json` |

The result schemas are generated from the actual outputs by `scripts/config/build_result_schemas.py` (`--check`).

`abep_sim.configuration.physics_configuration()` builds the `SimulationConfiguration` of a raw physics run without
opening the requirements snapshot; `assessment_configuration()` adds it.
"""


def build_all() -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    out[ARCH_FILE] = dumps(build_architecture())
    snap = build_requirements()
    out[REQ_FILE] = snap_b = dumps(snap)
    cons = build_constraints(snap, snap_b)
    out[CONSTRAINTS_FILE] = dumps(cons)
    out[MISSION_FILE], out[MISSION_V1_FILE] = _frozen_scenario_bytes()
    out[GATES_FILE] = dumps(build_gate_thresholds(cons))
    out[DS_REF_FILE] = dumps(build_design_state_ref())
    out[HW_FILE] = dumps(build_hardware())
    out[MODEL_SET_FILE] = dumps(build_model_set())
    out[SOT_FILE] = dumps(build_sources_of_truth(out))
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

#!/usr/bin/env python3
"""Bundle 1 (Milestone A, conditional selection) builder: fo_bundle1_conditional_selection.

Synthesis only. It reads the verified deliverables of the twelve registered T_BUNDLE1 prerequisites (plus two context
lanes), pins every input file by sha256 + lane id + lane commit, and writes

    docs/milestones/bundle1/bundle1_v1.json   (validated against bundle1_v1.schema.json)
    docs/milestones/bundle1/BUNDLE1.md        (generated tables + short prose)

It introduces no physics, no sources and no numbers of its own: every value in the output is read from a pinned input,
or is a count/identity of pinned records. Missing or changed inputs raise; nothing falls back to a default.

    python docs/milestones/bundle1/build_bundle1.py            # write both files
    python docs/milestones/bundle1/build_bundle1.py --check    # exit 1 unless both files are reproduced byte for byte

Pure standard library. The only module import from the repository is the lane-11 boundary module
(abep_sim/arch_boundary.py), resolved lazily inside a function and cross-checked against the lane-17 component list;
nothing is wired into archengine and no golden moves.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT_JSON_REL = "docs/milestones/bundle1/bundle1_v1.json"
OUT_MD_REL = "docs/milestones/bundle1/BUNDLE1.md"
SCHEMA_REL = "docs/milestones/bundle1/bundle1_v1.schema.json"
SCRIPT_REL = "docs/milestones/bundle1/build_bundle1.py"

BUNDLE_ID = "bundle1_v1"
FOLLOW_ON = "fo_bundle1_conditional_selection"
TRIGGER = "T_BUNDLE1"
ATTEMPT = 2
EXECUTION_KEY = "d45eda8e144c71eae9f5ebf0d1c1a560af20903571c60bbcdb605e361b68a148"
BASE_COMMIT = "1a1f7e4b7767d41ca99e20641c11dc4d3cafcda7"
PREPARED = "2026-09-26"
ARCHS = ("hall_only", "rf_hall", "ecr_hall")
BOUNDARY_VERSION = "bus_power_boundary_v1"
OUTCOME_FORMS = ("CONDITIONAL_BASELINE", "NO_BASELINE_YET")

# --------------------------------------------------------------------------------------------------------------------
# Input pins: (lane id, role, lane commit) -> files with sha256. Identity = the lane's verified commit (T_BUNDLE1 claim).
# --------------------------------------------------------------------------------------------------------------------
PREREQUISITES = {
    "lane_07_rf_evidence": "336d548042359f8559d0bf50a409a976c0158fc2",
    "lane_08_ecr_evidence": "a85fd592618cb15a02f14123659a0698db90df19",
    "lane_09_hall_sustainment": "ac7970917fd0e88c065d75406ea90c1d7ebaca7b",
    "lane_16_feed_envelope": "ab27dcc449690606defa09af59725c0ad2eeaab4",
    "lane_17_hall_reference": "91ebd8a4017eb8609804846603063a25c41405c1",
    "lane_18_interstage": "870514285c087382b21812c65bd9db196a5a985f",
    "lane_20_ppu_magnet": "f7c226848d85fedb70c03bae9971be3b2bbde1fe",
    "lane_24_hard_gates": "08b9f9bf32a0b34142338b2003f2b2cf02ecaacc",
    "lane_28_break_even": "2ad4c463d7a7bd7b983e2de30f8fb34d8cac92fa",
    "fo_rf_breakeven_overlay": "9ef356b536f84e203b87b583b7246e72dcc07d71",
    "fo_ecr_breakeven_overlay": "d22bc6053a64230dd01b8df0e764d884bab722a9",
    "fo_hall_sustainment_envelope": "de0ebd25f43e3302e659bf5a0d4d7df8aee97637",
}
CONTEXT = {
    "lane_23_comparison_grid": "3b9af54be83e63102a437d15197117a03977c246",
    "lane_11_bus_boundary": "a2a139686dd25ea0f5f4fa908f9d57c25d3746dd",
}
PINS = [
    ("lane_07_rf_evidence", "docs/evidence/rf_source/rf_evidence_matrix.json", "5f6d4e0ede8b2e21e45b740c28ac9320e7ddd6cfd70ef05012f85712ae0ac8e8"),
    ("lane_07_rf_evidence", "docs/evidence/rf_source/RF_SOURCE_EVIDENCE.md", "88fb9015e7b864796b13f6d1485d0bf1273f0660035299b032fa414904fb1e15"),
    ("lane_08_ecr_evidence", "docs/evidence/ecr_source/ecr_evidence_matrix.json", "4a65dbeec34f16f048fa515ced3bb959c02a981113e25da89e8bb844337fec88"),
    ("lane_08_ecr_evidence", "docs/evidence/ecr_source/ECR_SOURCE_EVIDENCE.md", "b543437f216335fd972de560345864c172472a12e3522566771413126677f440"),
    ("lane_09_hall_sustainment", "docs/evidence/hall_sustainment/hall_sustainment_matrix.json", "248aef28cfe6ffff90d9ee6d43c388488140547e1ce5659975ce30ca77f415b4"),
    ("lane_09_hall_sustainment", "docs/evidence/hall_sustainment/HALL_SUSTAINMENT_EVIDENCE.md", "f9674b60b2a2852e6b960e227a95626a78096d28eb698b9237bc9a419fcf7c01"),
    ("lane_16_feed_envelope", "docs/architecture_comparison/feed_envelope/feed_envelope_v1.json", "ada3ee720b1b8d60526d3b092492589f62a4144112845b4d813dbc8dc7d5ca02"),
    ("lane_16_feed_envelope", "docs/architecture_comparison/feed_envelope/FEED_ENVELOPE.md", "e3f9f1fc5dd57b6569065d2750842dd9792dd74ae8d483b271e7d10e4d3f262d"),
    ("lane_17_hall_reference", "docs/architecture_comparison/hall_reference/hall_reference_v1.json", "c60e0adfbef2c6f8dddaa9b7e89cea6b0ce760d3c9777dff5a47c2bfda7cb2e6"),
    ("lane_17_hall_reference", "docs/architecture_comparison/hall_reference/HALL_ACCELERATOR_REFERENCE.md", "6d92cbe6ed8758d94fb428f5bd71c3f5a6466834f346a43e8a51e81b5eaa0de4"),
    ("lane_18_interstage", "abep_sim/interstage.py", "bc4b9987a832209d1417f6646d2a44c72b8d79bac18f896089647bcd1ed93174"),
    ("lane_18_interstage", "docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md", "2a08e8045d1cb61a121e84dc9f7bba268a1ec7b66476057d9093b4e044f6d616"),
    ("lane_20_ppu_magnet", "abep_sim/magnet_power.py", "adf2905d90b7dd17b59071759d0a62b245fa065b0c3375c74df4e3476b7bb523"),
    ("lane_20_ppu_magnet", "docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json", "d56f700198a64a919d736c8659b6e0aaaa01cd56521885772d2f5a40de374501"),
    ("lane_20_ppu_magnet", "docs/architecture_comparison/electrical_closure/ELECTRICAL_CLOSURE.md", "661ff1c3b783edf5b32c48a638f9b1931046af68bfef87e9ce9f17de01264aaa"),
    ("lane_24_hard_gates", "abep_sim/hard_gates.py", "a36fe3c9065291f0fe5be3f17e179d5b691f00c013f7f8ef299fa89db896dda8"),
    ("lane_24_hard_gates", "docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json", "7d77d2831214f3f3d96c8254ea43643ada15e7d1ce0685dec86a65eb79a8f65f"),
    ("lane_24_hard_gates", "docs/architecture_comparison/hard_gates/hard_gate_status_v1.json", "2c82b3277067b22c85eabd25539b18101f429e6d34ee698d2f5d6e183aa44527"),
    ("lane_24_hard_gates", "docs/architecture_comparison/hard_gates/evidence_register_v1.json", "45dfbfb311441aeb7c9c58f5dbb9ffb39c28fa448b85de552c37e8268ff94a3d"),
    ("lane_24_hard_gates", "docs/architecture_comparison/hard_gates/HARD_GATES.md", "536d8d9d6d5ea6238cc8bfd9c7c22f6637ebf6102c85b4d326625c1019dae0b2"),
    ("lane_28_break_even", "abep_sim/breakeven.py", "fad317b74c3f1359d849c62a7b487f2e26d8ccb3be05a35c15b515ea6d948767"),
    ("lane_28_break_even", "docs/architecture_comparison/breakeven/breakeven_surfaces_v1.json", "577fa11b62ee5d9c04f0d9f483d93962062f5fd40bb7aefd411eb9c0764985bc"),
    ("lane_28_break_even", "docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md", "e65c28c040c1fbd9b079d4d4872316441e4f4114f37ff70e79138aab8c134d86"),
    ("lane_28_break_even", "docs/architecture_comparison/breakeven/BREAKEVEN_SURFACES.md", "82ab324ea3c1b58eb8bd487c93d09f9ed8ab9f480799d80781325371f810142a"),
    ("fo_rf_breakeven_overlay", "docs/architecture_comparison/overlays/rf/overlay_rf_v1.json", "ba739be2fdf431ac33900207cd8365d265456ad7b9d7e6a71e0875524c662359"),
    ("fo_rf_breakeven_overlay", "docs/architecture_comparison/overlays/rf/RF_BREAKEVEN_OVERLAY.md", "12c777870fa3a34a80c1aca562d4e7527c31372a72d5e7238fbb07342b6716c9"),
    ("fo_ecr_breakeven_overlay", "docs/architecture_comparison/overlays/ecr/overlay_ecr_v1.json", "3ee12e66f94204955f61cbb78d7c5036044cc59a9bc50f675704592bfbfabfcd"),
    ("fo_ecr_breakeven_overlay", "docs/architecture_comparison/overlays/ecr/ECR_BREAKEVEN_OVERLAY.md", "0b622859abb49ef3b426b8aee7be893ee9c026a98d13e4f8ebdb5ab93ad7a5a1"),
    ("fo_hall_sustainment_envelope", "docs/architecture_comparison/overlays/hall_sustainment/hall_sustainment_envelope_v1.json", "c7d05fd04aafe249ff0dce575902067dea9bdd048fa857283cb66066e612b19e"),
    ("fo_hall_sustainment_envelope", "docs/architecture_comparison/overlays/hall_sustainment/HALL_SUSTAINMENT_ENVELOPE.md", "ddb257d13cd1c6ca990f73ec80abe9deb6b04f9e87f047881787a6556a26ba1e"),
    ("lane_23_comparison_grid", "docs/architecture_comparison/comparison_grid/comparison_grid_v1.json", "1b8a6a13065223fd397599a4bbae6e269f92721e7a680b27dce38029504657f4"),
    ("lane_23_comparison_grid", "docs/architecture_comparison/comparison_grid/COMPARISON_GRID.md", "30aca15e05ff39d3970fb2b1d32bcfd8b2ec5ec3ab2e6572e440b659bb4e0b55"),
    ("lane_11_bus_boundary", "abep_sim/arch_boundary.py", "8dfc309a5d2c717913fd4961bc660f8bab92ed2c59356f5a78bff3ef4392eeae"),
    ("lane_11_bus_boundary", "docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md", "2432edb7e9095fd630585768a62a811140b5230ba035afa3f0fc168636d11ca9"),
    ("lane_11_bus_boundary", "schemas/architecture_comparison/bus_power_boundary_v1.json", "a78068a31ad097d94d83f36b9860c6992d0e560cfdc51335b4c222a3feaed3e9"),
]
# Governance files: content-checked (append-only ledger / registries), not hash-pinned (they grow as work proceeds).
GOV = {
    "operating_model": "docs/orchestration/OPERATING_MODEL.md",
    "lane_registry": "docs/orchestration/lane_registry_v1.json",
    "trigger_registry": "docs/orchestration/trigger_registry_v1.json",
    "trigger_ledger": "docs/orchestration/trigger_ledger_v2.jsonl",
    "evidence_policy": "docs/EVIDENCE.md",
    "question_a_disposition": "docs/v2/question_a/QUESTION_A_DISPOSITION.json",
}
FOLLOW_ON_WORKFLOW_SCRIPTS = {
    "fo_rf_breakeven_overlay": ["docs/orchestration/workflow_scripts/followon-overlays-rf-ecr.js"],
    "fo_ecr_breakeven_overlay": ["docs/orchestration/workflow_scripts/followon-overlays-rf-ecr.js",
                                 "docs/orchestration/workflow_scripts/reverify-ecr-hsenv-ftree.js"],
    "fo_hall_sustainment_envelope": ["docs/orchestration/workflow_scripts/followon-fo_hall_sustainment_envelope.js",
                                     "docs/orchestration/workflow_scripts/reverify-ecr-hsenv-ftree.js"],
}

MANDATORY_FIELDS = [
    ("m_dot_s", "ṁ_s", "species anode mass flow of the feed state at the valve outlet (IF-A5; Xe path IF-X2)"),
    ("P_feed", "P_feed", "feed-state (valve-outlet) pressure"),
    ("T_feed", "T_feed", "feed-state (valve-outlet) gas temperature"),
    ("x_s", "x_s", "feed-state species composition (mole fraction) at the valve outlet"),
    ("V_d", "V_d", "Hall discharge voltage"),
    ("T", "T", "thrust"),
    ("P_bus", "P_bus", "all DC-bus power at the propulsion-subsystem input (bus_power_boundary_v1)"),
    ("m", "m", "propulsion-system mass (MEV)"),
    ("Q_reject", "Q_reject", "heat to be rejected by the propulsion subsystem"),
    ("life", "life", "firing life (cumulative) and mission capability"),
    ("startup", "startup", "ignition from off / start sequence and its resources"),
    ("eta_u", "η_u", "propellant utilization of the Hall accelerator (with pre-ionizer where present)"),
    ("stability", "stability", "sustained, stable discharge at the flight operating point"),
]
OPERATING_MODEL_FIELD_SET = "{ṁ_s, P_feed, T_feed, x_s, V_d, T, P_bus, m, Q_reject, life, startup, η_u, stability}"
FORBIDDEN = re.compile(r"\b(winner|winners|selected|validated)\b|demonstrated performance", re.IGNORECASE)
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "none")
# lane-24 evidence bases that are verdict-bearing at milestone A (HARD_GATES.md "Evidence that can decide a gate").
MILESTONE_A_BASES_FROM_LANE24 = ("hard_physical_bound", "measurement_vyovrinda", "measurement_same_hardware")


class InputError(RuntimeError):
    """A pinned input is missing, changed, or does not have the structure this synthesis relies on."""


# --------------------------------------------------------------------------------------------------------------------
# Reading inputs
# --------------------------------------------------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_pins(pins=None, repo: Path = REPO) -> list[dict]:
    """Verify every pinned file exists and has its pinned sha256. Raises InputError; never skips."""
    out = []
    for lane, rel, digest in (PINS if pins is None else pins):
        commit = PREREQUISITES.get(lane) or CONTEXT.get(lane)
        if commit is None:
            raise InputError(f"pin for unknown lane id {lane!r} ({rel})")
        p = repo / rel
        if not p.is_file():
            raise InputError(f"missing pinned input {rel} (lane {lane} @ {commit[:10]})")
        got = sha256_file(p)
        if got != digest:
            raise InputError(f"pinned input changed: {rel} (lane {lane} @ {commit[:10]}): sha256 {got} != pinned {digest}. "
                             "A changed input needs a new bundle version, not a silent rebuild.")
        out.append({"lane": lane, "commit": commit, "path": rel, "sha256": digest})
    return out


def _json(rel: str):
    if rel not in {r for _, r, _ in PINS}:
        raise InputError(f"{rel} is not a pinned input")
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _gov_text(key: str) -> str:
    p = REPO / GOV[key]
    if not p.is_file():
        raise InputError(f"missing governance file {GOV[key]}")
    return p.read_text(encoding="utf-8")


def _need(cond: bool, msg: str):
    if not cond:
        raise InputError(msg)


def check_governance() -> dict:
    """Content checks of the (unpinned, append-only / growing) governance files."""
    om = " ".join(_gov_text("operating_model").split())
    _need(OPERATING_MODEL_FIELD_SET in om, "OPERATING_MODEL.md no longer states the frozen field set " + OPERATING_MODEL_FIELD_SET)
    for phrase in ("CONDITIONAL_BASELINE(X)", "NO_BASELINE_YET", "ELIMINATED_WITHIN_TESTED_ENVELOPE", "bus_power_boundary_v1",
                   "single-lens-v1"):
        _need(phrase in om, f"OPERATING_MODEL.md no longer contains {phrase!r}")
    ev = _gov_text("evidence_policy")
    for cls in EVIDENCE_CLASSES[:-1]:
        _need(f"*{cls}*" in ev, f"docs/EVIDENCE.md no longer lists quantity type {cls!r}")

    reg = json.loads(_gov_text("lane_registry"))
    lane_ids = {l["id"]: l for l in reg["lanes"]}
    fo_ids = {l["id"]: l for l in reg["follow_ons"]}
    _need(FOLLOW_ON in fo_ids, f"{FOLLOW_ON} is not a registered follow-on")
    trg = json.loads(_gov_text("trigger_registry"))
    triggers = {t["id"]: t for t in trg["triggers"]}
    _need(TRIGGER in triggers and triggers[TRIGGER].get("produces") == FOLLOW_ON, f"{TRIGGER} does not produce {FOLLOW_ON}")
    prereq = [p["id"] for p in triggers[TRIGGER]["prerequisites"]]
    _need(sorted(prereq) == sorted(PREREQUISITES), f"{TRIGGER} prerequisites changed: {prereq}")
    _need(all(p["state"] == "verified" for p in triggers[TRIGGER]["prerequisites"]), "T_BUNDLE1 requires verified prerequisites")

    claim = None
    for line in _gov_text("trigger_ledger").splitlines():
        if not line.strip():
            continue
        ev_ = json.loads(line)
        if ev_.get("execution_key") == EXECUTION_KEY and ev_.get("event") == "CLAIMED":
            claim = ev_
    _need(claim is not None, f"no CLAIMED event for execution key {EXECUTION_KEY} in {GOV['trigger_ledger']}")
    _need(claim["trigger"] == TRIGGER and claim["attempt"] == ATTEMPT, "claim is not T_BUNDLE1 attempt 2")
    for lane, commit in PREREQUISITES.items():
        got = claim["prerequisites"].get(lane)
        _need(got is not None and got["identity"] == commit and got["state"] == "verified",
              f"claim identity for {lane} is {got}, pinned {commit}")

    protocols = {}
    for lane in list(PREREQUISITES) + list(CONTEXT):
        if lane in lane_ids:
            entry = lane_ids[lane]
            proto = entry["verification_protocol"]
            src = f"{GOV['lane_registry']} lanes[{lane}].verification_protocol"
            notes = []
            if entry.get("repairs"):
                notes.append("repairs registered (" + ", ".join(r["workflow_run"] for r in entry["repairs"]) + "); state from the latest repair run")
            if entry.get("verified_pin"):
                notes.append("verified_pin at commit " + entry["verified_pin"]["commit"])
        elif lane in fo_ids:
            scripts = FOLLOW_ON_WORKFLOW_SCRIPTS[lane]
            for s in scripts:
                txt = (REPO / s).read_text(encoding="utf-8") if (REPO / s).is_file() else ""
                _need("['evidence', 'rules']" in txt and lane in txt, f"workflow script {s} does not show the two-lens loop for {lane}")
            proto = "two-lens (evidence + rules lenses)"
            src = (f"{GOV['lane_registry']} decided.terminal_states.follow_on ('verified, exactly as a workflow_lane'); "
                   "verification loop in " + ", ".join(scripts))
            notes = []
            if fo_ids[lane].get("repairs"):
                notes.append("repairs registered (" + ", ".join(r["workflow_run"] for r in fo_ids[lane]["repairs"]) + "): targeted two-lens re-verification of the unchanged commit")
        else:
            raise InputError(f"{lane} is not in the lane registry")
        protocols[lane] = {"protocol": proto, "protocol_source": src, "notes": notes}
    qa = json.loads(_gov_text("question_a_disposition"))
    _need(qa.get("id") == "od_v2_question_a" and qa.get("decision") == "A-NO" and qa.get("domain_path") == "closed",
          "v2 Question A disposition is no longer A-NO / closed: the Milestone-B blocker text must be revisited")
    single_lens = sorted(l for l, e in lane_ids.items() if e.get("verification_protocol") == "single-lens-v1")
    return {"lane_ids": set(lane_ids), "fo_ids": set(fo_ids), "trigger_ids": set(triggers), "protocols": protocols,
            "single_lens_lanes": single_lens, "lane_titles": {**{k: v["title"] for k, v in lane_ids.items()},
                                                              **{k: v["title"] for k, v in fo_ids.items()}},
            "claim_utc": claim["utc"], "dependency_state_hash": claim["dependency_state_hash"]}


def boundary_components() -> dict:
    """Component set per architecture: lane-17 reference, cross-checked against the lane-11 module (lazy import)."""
    hr = _json("docs/architecture_comparison/hall_reference/hall_reference_v1.json")["bus_power_boundary"]
    _need(hr["boundary_version"] == BOUNDARY_VERSION, "hall reference boundary version changed")
    common = list(hr["common_hall_components"]) + list(hr["other_common_components"])
    comps = {a: common + list(hr["arm_specific_components"][a]) for a in ARCHS}
    path = REPO / "abep_sim" / "arch_boundary.py"
    if not path.is_file():
        raise InputError("abep_sim/arch_boundary.py (lane_11_bus_boundary) is required for the boundary cross-check and is missing")
    spec = importlib.util.spec_from_file_location("_bundle1_arch_boundary", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _need(mod.BOUNDARY_VERSION == BOUNDARY_VERSION, "arch_boundary BOUNDARY_VERSION changed")
    for a in ARCHS:
        _need(list(mod.REQUIRED_COMPONENTS[a]) == comps[a],
              f"component set mismatch for {a}: lane_11 {mod.REQUIRED_COMPONENTS[a]} vs lane_17 {comps[a]}")
    return comps


# --------------------------------------------------------------------------------------------------------------------
# Synthesis
# --------------------------------------------------------------------------------------------------------------------
FE = "docs/architecture_comparison/feed_envelope/feed_envelope_v1.json"
HR = "docs/architecture_comparison/hall_reference/hall_reference_v1.json"
EC = "docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json"
HGS = "docs/architecture_comparison/hard_gates/hard_gate_status_v1.json"
HGM = "docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json"
HGR = "docs/architecture_comparison/hard_gates/evidence_register_v1.json"
BE = "docs/architecture_comparison/breakeven/breakeven_surfaces_v1.json"
RFO = "docs/architecture_comparison/overlays/rf/overlay_rf_v1.json"
ECRO = "docs/architecture_comparison/overlays/ecr/overlay_ecr_v1.json"
HSE = "docs/architecture_comparison/overlays/hall_sustainment/hall_sustainment_envelope_v1.json"
HSM = "docs/evidence/hall_sustainment/hall_sustainment_matrix.json"
CG = "docs/architecture_comparison/comparison_grid/comparison_grid_v1.json"
IS_MD = "docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md"
BND_MD = "docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md"
RF_MD = "docs/evidence/rf_source/RF_SOURCE_EVIDENCE.md"
ECR_MD = "docs/evidence/ecr_source/ECR_SOURCE_EVIDENCE.md"

# field -> lane-24 criteria (hard_gate_status_v1.json) that test the field
FIELD_CRITERIA = {
    "T": ["G1.thrust_floor", "G1.thrust_ceiling", "G1.peak_capability_25mN"],
    "P_bus": ["G2.bus_power_max"],
    "m": ["G3.mass_mev"],
    "life": ["G4.firing_life", "G5.mission_capability", "P2.cathode_life"],
    "startup": ["G6.ignition", "G6.restart_count", "P2.start_cycles"],
    "stability": ["G6.sustainment", "G7.xenon_operation", "G7.mixed_feed", "G7.feed_switching"],
    "Q_reject": ["P1.thermal_margin"],
}


def feed_extract() -> dict:
    fe = _json(FE)
    cases = fe["cases"]
    case_ids = [c["case_id"] for c in cases]
    keymap = {"m_dot_s": "mdot_s_kgps", "P_feed": "p_feed_Pa", "T_feed": "T_gas_K", "x_s": "x_s"}
    out = {}
    for field, key in keymap.items():
        units, requires = set(), set()
        for c in cases:
            rec = c["feed_state"][key]
            vals = rec["values"].values() if "values" in rec else [rec["value"]]
            _need(all(v is None for v in vals) and rec["evidence_class"] == "TBD",
                  f"feed envelope {c['case_id']}.{key} is no longer TBD: the input changed; a new bundle version is needed")
            _need(c["status"] == "DESIGN_INPUTS_MISSING", f"feed case {c['case_id']} status changed")
            units.add(rec["unit"])
            requires.add(rec["requires"])
        _need(len(units) == 1, f"inconsistent units for {key}")
        out[field] = {"unit": units.pop(), "requires": sorted(requires), "key": key}
    xe = fe["xe_path"]["feed_state"]
    xe_ok = {k: xe[k]["value"] is None for k in ("mdot_xe_anode_kgps", "mdot_xe_cathode_kgps", "p_feed_Pa", "T_gas_K")}
    _need(all(xe_ok.values()), "feed envelope Xe path is no longer TBD")
    out["case_ids"] = case_ids
    out["xe_x_s"] = xe["x_s"]
    out["open_questions"] = fe["open_questions"]
    return out


def vd_extract() -> dict:
    dv = _json(HR)["discharge_voltage_interface"]
    s = dv["proposed_evaluation_set_V"]
    r = dv["proposed_range_V"]
    _need(s["status"] == "PROPOSED" and s["evidence_class"] == "assumed", "V_d evaluation set status changed")
    return {"set": s["value"], "unit": s["unit"], "status": s["status"], "evidence_class": s["evidence_class"],
            "range": r["value"], "range_unit": r["unit"], "sources": s["source"]}


def grid_extract() -> dict:
    cg = _json(CG)
    summ = cg["summary"]
    return {"status": cg["status"], "n_base_points_by_mode": summ["n_base_points_by_mode"],
            "n_base_points_pending_tbd": summ["n_base_points_pending_tbd"], "n_base_points": summ["n_base_points"],
            "p_source_levels": summ["p_source_levels_by_architecture"], "n_freeze_blockers": len(cg["freeze_procedure"]["blockers"]),
            "open_questions": cg["open_questions_for_owner"]}


def gates_extract() -> dict:
    st = _json(HGS)
    reg = _json(HGR)
    mat = _json(HGM)
    _need(sorted(st["not_eliminated"] + st["eliminated"]) == sorted(ARCHS), "lane-24 status does not cover the three architectures")
    per = {}
    for a in ARCHS:
        s = st["architectures"][a]
        crit = {}
        for g, gd in s["gates"].items():
            for cid, cd in gd["criteria"].items():
                crit[cid] = {"gate": g, "verdict": cd["verdict"], "threshold": cd["threshold"], "unit": cd["unit"],
                             "comparator": cd["comparator"], "status": cd["status"], "metric": cd["metric"],
                             "counts_for_fail": cd["counts_for_fail"], "counts_toward_gate": cd["counts_toward_gate"],
                             "binding_gate": gd["binding"]}
        mA = s["milestones"]["A"]
        per[a] = {
            "eliminated": s["eliminated"],
            "elimination_basis": s["elimination_basis"],
            "binding_gates": s["binding_gates"],
            "proposed_gates": s["proposed_gates"],
            "gate_verdicts": {g: gd["verdict"] for g, gd in s["gates"].items()},
            "criteria": crit,
            "conflicts": s["conflicts"],
            "matrix_status": s["matrix_status"],
            "milestone_A": {
                "conditional_selection_available": mA["conditional_selection_available"],
                "statement": mA["statement"],
                "conditions": [{"criterion": c["criterion"], "gate": c["gate"], "requirement": c["requirement"],
                                "current_verdict": c["current_verdict"], "can_eliminate": c["can_eliminate"],
                                "discharged_by_A": c["discharged_by"]["A"], "discharged_by_B": c["discharged_by"]["B"],
                                "blockers": c["blockers"]} for c in mA["conditions"]],
                "open_owner_items": [o["criterion"] + " (" + o["status"] + ")" for o in mA["open_owner_items"]],
                "proposed_gates_pending": mA["proposed_gates_pending"],
            },
            "milestone_B_missing": s["milestones"]["B"]["missing"],
            "milestone_C_missing": s["milestones"]["C"]["missing"],
        }
    return {"eliminated": st["eliminated"], "not_eliminated": st["not_eliminated"], "note": st["note"],
            "admitted_members": st["admitted_members"],
            "matrix_status": st["matrix_status"], "matrix_version": st["matrix_version"], "per": per,
            "n_register_items": len(reg["items"]), "register_note": reg["note"],
            "open_owner_decisions": [{"id": d["id"], "topic": d["topic"], "current_handling": d["current_handling"]}
                                     for d in mat["open_owner_decisions"]]}


def _pick(statements: list[str], needle: str, label: str) -> str:
    hits = [s for s in statements if needle in s]
    _need(len(hits) == 1, f"{label}: expected exactly one statement containing {needle!r}, found {len(hits)}")
    return hits[0]


def overlays_extract() -> dict:
    rf = _json(RFO)
    ecr = _json(ECRO)
    hs = _json(HSE)
    rfA = rf["milestone_A_statement"]
    ecrA = ecr["milestone_A_statement"]
    status_counts = {}
    for c in hs["cases"]:
        status_counts[c["status"]] = status_counts.get(c["status"], 0) + 1
    air_cases = [c for c in hs["cases"] if not c["case_id"].startswith("variant_")]
    air_counts = {}
    for c in air_cases:
        air_counts[c["status"]] = air_counts.get(c["status"], 0) + 1
    f9 = [f for f in hs["findings"] if f["id"] == "F-9"]
    _need(len(f9) == 1, "F-9 finding missing in the hall sustainment envelope")
    return {
        "rf": {
            "placement_counts": rf["placement_counts"],
            "hard_gate_statement": _pick(rfA["can_be_concluded_now"], "no basis to set rf_hall aside", "rf overlay"),
            "eta_t_statement": _pick(rfA["can_be_concluded_now"], "eta_t is the decisive unknown", "rf overlay"),
            "conditions": rfA["conditions_for_rf_hall_as_baseline"],
            "decisive_measurement": rf["decisive_measurement_common"],
            "to_reach_B": rf["milestone_support"]["to_reach_B"],
            "open_questions": rf["open_questions_for_owner"],
        },
        "ecr": {
            "placement_counts": ecr["placement_counts"],
            "hard_gate_statement": _pick(ecrA["can_conclude_now"], "no hard-gate candidate", "ecr overlay"),
            "air_arm_statement": _pick(ecrA["can_conclude_now"], "air arm:", "ecr overlay"),
            "condition_set": ecrA["condition_set_for_milestone_A"],
            "explicit_conditions": ecrA["explicit_conditions"],
            "to_reach_B": ecr["milestones"]["to_reach_B"],
            "owner_decisions": [{"id": d["id"], "question": d["question"]} for d in ecr["owner_decisions_requested"]],
        },
        "hs": {
            "air_case_status_counts": air_counts,
            "all_case_status_counts": status_counts,
            "n_air_cases": len(air_cases),
            "f9": f9[0]["statement"],
            "conditions": hs["milestone_A_conditions"],
            "decisive_measurements": [{"id": d["id"], "type": d["type"], "what": d["what"]} for d in hs["decisive_measurements"]],
            "to_reach_B": hs["milestones"]["to_reach_B"],
            "open_questions": hs["open_questions_for_owner"],
        },
    }


def electrical_extract() -> dict:
    ec = _json(EC)
    return {"components": {k: {"load_status": v["load_status"], "efficiency_status": v["efficiency_status"],
                                "in_architectures": v["in_architectures"]} for k, v in sorted(ec["components"].items())},
            "open_questions": ec["open_questions_for_owner"]}


def md_owner_items(rel: str, start_pat: str, stop_pat: str) -> list[str]:
    """Numbered items of an owner-question section of a pinned Markdown input (between two headings)."""
    txt = (REPO / rel).read_text(encoding="utf-8")
    m = re.search(start_pat + r"(.*?)" + stop_pat, txt, re.S)
    _need(m is not None, f"owner-question section not found in {rel}")
    items, cur = [], None
    for line in m.group(1).splitlines():
        mm = re.match(r"^(\d+)\.\s+(.*)$", line)
        if mm:
            if cur:
                items.append(cur)
            cur = mm.group(2).strip()
        elif cur is not None and line.startswith("   ") and line.strip():
            cur += " " + line.strip()
    if cur:
        items.append(cur)
    _need(items, f"no owner items parsed from {rel}")
    return items


def interstage_owner_items() -> list[str]:
    txt = (REPO / IS_MD).read_text(encoding="utf-8")
    out = []
    m = re.search(r"Open question for the owner: (.*?)\n\n", txt, re.S)
    _need(m is not None, "interstage owner question not found")
    out.append(" ".join(m.group(1).split()))
    m2 = re.search(r"Choosing one spelling project-wide is an open item for the\s+owner\.", txt)
    _need(m2 is not None, "interstage unit-spelling owner item not found")
    out.append("Choose one spelling of the dimensionless unit project-wide (interstage '-' vs breakeven_v1 '1').")
    return out


def cell(status, value, units, op, evidence, evidence_class, uncertainty_status, derivation, blocking=(),
         lane24=(), hall_closure_dependent=False, notes=(), basis=None):
    return {"status": status, "value": value, "units": units, "operating_point": op, "evidence": list(evidence),
            "evidence_class": evidence_class, "basis": basis, "uncertainty_status": uncertainty_status, "derivation": derivation,
            "blocking": list(blocking), "lane24_criteria": list(lane24), "hall_closure_dependent": hall_closure_dependent,
            "notes": list(notes)}


def ev(path, lane, locator):
    return {"path": path, "input_lane": lane, "locator": locator}


def blk(kind, bid, what):
    return {"kind": kind, "id": bid, "what": what}


def build_cells(feed, vd, grid, gates, ovl, elec, comps) -> dict:
    op_feed = {"id": "OP-FEED-IFA5",
               "definition": ("valve outlet IF-A5 (atmospheric path) of the lane-16 feed-envelope cases "
                              + ", ".join(feed["case_ids"]) + "; orbit-averaged; one record for all architectures "
                              "(feed_envelope_v1 architecture_dependent = false; Hall reference INV-F1). Xe path IF-X2 carried "
                              "in the same field as TBD. comparison_grid_v1 feed modes: "
                              + ", ".join(f"{k} {v} base points" for k, v in grid["n_base_points_by_mode"].items()))}
    op_steady = {"id": "OP-GRID-STEADY",
                 "definition": ("steady firing on the comparison_grid_v1 base points (lane_23; "
                                f"{grid['n_base_points']} base points, {grid['n_base_points_pending_tbd']} of them PENDING_TBD_LEVELS; "
                                "P_source levels " + "; ".join(f"{a}: {'/'.join(v)}" for a, v in grid["p_source_levels"].items())
                                + ", values TBD), at the V_d evaluation set of lane_17; RFP envelope 180-230 km")}
    op_vd = {"id": "OP-VD-SET", "definition": "the V_d nodes shared by every architecture (Hall reference INV-V1)"}
    op_sys = {"id": "OP-SYSTEM", "definition": "whole propulsion system, no operating point (lane-24 G3 element list)"}
    op_life = {"id": "OP-LIFE", "definition": "cumulative firing over the mission (lane-24 G4/G5, element lists per architecture)"}
    op_start = {"id": "OP-START", "definition": "start-up mode from off, 180-230 km, low/mean/high atmosphere (lane-24 G6.ignition 'over')"}

    fe_md = "docs/architecture_comparison/feed_envelope/FEED_ENVELOPE.md"
    feed_block = [blk("measurement", "DI-1", "documented feed design baseline with provenance evaluated by the feed-envelope builder "
                      "(fo_hall_sustainment_envelope decisive_measurements DI-1; feed envelope open question 1)"),
                  blk("lane", "lane_16_feed_envelope", "delivers the valve-outlet state once DI-1 exists (design_input_contract)"),
                  blk("lane", "lane_33_upstream_icd", "upstream ICD gaps (IF-A5/IF-X2) named by the feed envelope; single-lens-v1")]
    cells = {a: {} for a in ARCHS}
    for a in ARCHS:
        common_ev = [ev(FE, "lane_16_feed_envelope", "cases[*].feed_state; xe_path.feed_state")]
        for field, extra_block, extra_note in (
            ("m_dot_s", [], []),
            ("P_feed", [blk("owner_decision", "feed_envelope_Q2", "common feed pressure: one architecture-neutral valve setpoint, or a common feed state with each ionizer's pressure window checked downstream")], []),
            ("T_feed", [], []),
            ("x_s", [blk("measurement", "DM-1", "atomic-O fraction and O2/N2 ratio at the valve outlet (fo_hall_sustainment_envelope DM-1)")],
             ["context only, not the feed composition: the free-stream IF-A0 composition of each case is model-derived in the feed envelope; "
              f"the Xe path IF-X2 carries x_Xe = {feed['xe_x_s']['values']} with evidence class {feed['xe_x_s']['evidence_class']} (pure-Xe definition)"]),
        ):
            f = feed[field]
            cells[a][field] = cell(
                "EXPLICITLY_UNAVAILABLE", None, f["unit"], op_feed, common_ev + [ev(fe_md, "lane_16_feed_envelope", "section 5 / 8")],
                "none", "unavailable:TBD in the feed envelope (case status DESIGN_INPUTS_MISSING at every case)",
                "not derived. The lane-16 value is null with evidence class TBD; requires: " + " | ".join(f["requires"])
                + ". Never filled from the superseded 0-D assumptions, code defaults or historical values (feed envelope 'not_adopted').",
                feed_block + extra_block, notes=extra_note)
        cells[a]["V_d"] = cell(
            "POPULATED", vd["set"], vd["unit"], op_vd,
            [ev(HR, "lane_17_hall_reference", "discharge_voltage_interface.proposed_evaluation_set_V")],
            vd["evidence_class"], f"{vd['status']} (owner decision pending, Hall reference Q1); an evaluation set, not a design point",
            f"copied from lane 17: proposed range {vd['range']} {vd['range_unit']} under span rule VR-1; nodes = range ends plus the "
            "multiples of 50 V strictly inside (design-of-experiment assumption); identical in every architecture (INV-V1)",
            [blk("owner_decision", "hall_reference_Q1", "approve or change the PROPOSED V_d range and set"),
             blk("measurement", "DI-2", "Vyovrinda Hall design point with provenance incl. the design V_d (fo_hall_sustainment_envelope DI-2)")],
            notes=["identical across architectures by INV-V1, so it cannot discriminate between them"], basis="assumption")

        closure_block = [
            blk("trigger", "T_ABSOLUTE_COMPARISON", "needs ensemble_admitted_members: credible set is empty (gate 3 FAIL); produces fo_absolute_comparison"),
            blk("lane", "lane_35_hallmap_spec", "design Hall maps per admitted member; single-lens-v1"),
            blk("measurement", "lane24:measurement_vyovrinda|measurement_same_hardware",
                "the only milestone-A route while no closure is admitted (lane-24 discharged_by.A)"),
            blk("lane", "lane_25_min_decisive_experiment", "minimum decisive experiment (hardware route)"),
            blk("trigger", "T_EXPERIMENT_PACKAGE", "experimental decision package (fo_experiment_package)"),
        ]
        preion_block = []
        if a == "rf_hall":
            preion_block = [blk("measurement", "RF-C_del", "delivered-ion bus cost C_del = P_bus[rf_source]/I_delivered on air/N2 at the ICD inlet state "
                                "(fo_rf_breakeven_overlay decisive_measurement_common)"),
                            blk("lane", "lane_18_interstage", "measured interstage transport efficiency eta_t (the lane-18 model has no interstage measurement to compare against: INTERSTAGE_MODEL.md section 10)")]
        elif a == "ecr_hall":
            preion_block = [blk("measurement", "ECR-C_del", "end-to-end bus cost per delivered ampere C_del,bus on an air-representative N2/O2/O feed "
                                "(fo_ecr_breakeven_overlay condition (A))"),
                            blk("lane", "lane_18_interstage", "measured interstage transport efficiency eta_t (the lane-18 model has no interstage measurement to compare against: INTERSTAGE_MODEL.md section 10)")]
        crit = gates["per"][a]["criteria"]

        def l24(field):
            return [{"criterion": c, "verdict": crit[c]["verdict"], "threshold": crit[c]["threshold"], "unit": crit[c]["unit"],
                     "comparator": crit[c]["comparator"], "status": crit[c]["status"]} for c in FIELD_CRITERIA.get(field, [])]

        cells[a]["T"] = cell(
            "EXPLICITLY_UNAVAILABLE", None, "mN", op_steady,
            [ev(HGS, "lane_24_hard_gates", f"architectures.{a}.gates.G1_thrust"), ev(HR, "lane_17_hall_reference", "transport_numerics_binding")],
            "none", "unavailable:no admitted Hall transport closure (credible set empty, gate 3 FAIL) and no Vyovrinda/same-hardware measurement",
            "not derived. Absolute Hall numbers of the withdrawn 0-D closure and screening-candidate results are never used (CLAUDE.md; lane-24 basis table).",
            closure_block + preion_block + [blk("measurement", "DI-1", "delivered feed (thrust needs the delivered flow)")],
            l24("T"), True)
        comp_list = comps[a]
        comp_status = "; ".join(f"{c}: load {elec['components'][c]['load_status']}, efficiency {elec['components'][c]['efficiency_status']}"
                                for c in comp_list)
        cells[a]["P_bus"] = cell(
            "EXPLICITLY_UNAVAILABLE", None, "W", op_steady,
            [ev("abep_sim/arch_boundary.py", "lane_11_bus_boundary", "REQUIRED_COMPONENTS[" + a + "]"),
             ev(EC, "lane_20_ppu_magnet", "components[*].load_status / efficiency_status"),
             ev(HGS, "lane_24_hard_gates", f"architectures.{a}.gates.G2_bus_power")],
            "none", "unavailable:component loads/efficiencies TBD (lane 20); hall_discharge load withdrawn until a closure is admitted",
            "P_bus = sum over REQUIRED_COMPONENTS[" + a + "] = [" + ", ".join(comp_list) + "] of P_load/efficiency "
            "(bus_power_boundary_v1). Never a discharge-only, absorbed-RF or ECR-source-only number. Component status (lane 20): " + comp_status,
            closure_block[:1] + [blk("trigger", "T_AUX_BUS", "full auxiliary / DC-bus power comparison (fo_aux_bus_comparison; needs lane_19_cathode_integration)"),
                                 blk("lane", "lane_12_arch_harness", "comparison harness abep_sim/arch_compare.py"),
                                 blk("lane", "lane_34_ledgers", "engineering ledgers; single-lens-v1"),
                                 blk("measurement", "DI-1", "delivered feed sets the compressor and flow-control loads")] + preion_block,
            l24("P_bus"), True)
        cells[a]["m"] = cell(
            "EXPLICITLY_UNAVAILABLE", None, "kg", op_sys,
            [ev(HGS, "lane_24_hard_gates", f"architectures.{a}.gates.G3_mass"), ev(BE, "lane_28_break_even", "mass_breakeven")],
            "none", "unavailable:no mass BOM with evidence; break-even mass inputs (s_P, s_T, hardware masses) TBD",
            "not derived (lane-24 G3 element list and breakeven_v1 section 7 name the terms; none has a value).",
            [blk("lane", "lane_21_mass_bom", "architecture mass BOM"), blk("trigger", "T_VETO_LAYER", "mass / thermal / life veto layer (fo_veto_layer)")],
            l24("m"), False)
        cells[a]["Q_reject"] = cell(
            "EXPLICITLY_UNAVAILABLE", None, "W", op_steady,
            [ev(HGS, "lane_24_hard_gates", f"architectures.{a}.gates.P1_thermal"), ev(IS_MD, "lane_18_interstage", "section 9 milestone C")],
            "none", "unavailable:no thermal closure; P1_thermal is a PROPOSED gate",
            "not derived. Heat loads include the Hall discharge losses (closure-dependent) and, for the pre-ionized arms, source and interstage wall heat.",
            [blk("lane", "lane_15_thermal_life", "thermal/life framework abep_sim/thermal_life.py"), blk("trigger", "T_VETO_LAYER", "fo_veto_layer"),
             blk("owner_decision", "OD9", "adopt or waive PROPOSED gates P1 thermal / P2 cathode")] + closure_block[:1],
            l24("Q_reject"), True)
        cells[a]["life"] = cell(
            "EXPLICITLY_UNAVAILABLE", None, "h", op_life,
            [ev(HGS, "lane_24_hard_gates", f"architectures.{a}.gates.G4_firing_life / G5_mission"), ev(BE, "lane_28_break_even", "life_breakeven")],
            "none", "unavailable:no wall_life_trustworthy Hall map, no cathode or source life evidence at the operating point",
            "not derived (breakeven_v1 section 8: life = min over mechanisms; all values TBD).",
            [blk("lane", "lane_32_wall_life", "wall erosion / life evidence; single-lens-v1"),
             blk("lane", "lane_10_cathode_dossier", "cathode / neutralizer evidence; single-lens-v1"),
             blk("lane", "lane_15_thermal_life", "thermal/life framework"), blk("trigger", "T_VETO_LAYER", "fo_veto_layer"),
             blk("measurement", "DM-6", "endurance on an O-containing feed (fo_hall_sustainment_envelope DM-6)")] + closure_block[:1],
            l24("life"), True)
        cells[a]["startup"] = cell(
            "EXPLICITLY_UNAVAILABLE", None, "boolean (ignition from off) + start sequence + Xe mass per start [kg]", op_start,
            [ev(HGS, "lane_24_hard_gates", f"architectures.{a}.gates.G6_ignition_sustainment"),
             ev(HSE, "fo_hall_sustainment_envelope", "section 8 ignition; HS-A6")],
            "none", "unavailable:G6.ignition is dischargeable only by hardware demonstration (lane-24 discharged_by A and B)",
            "not derived. Published starts on atmospheric gas used a Xe start/transition or a Xe/Ar cathode; no item ignites with no xenon on an RFP propellant (fo_hall_sustainment_envelope section 8).",
            [blk("measurement", "DM-3", "air-only ignition attempt (fo_hall_sustainment_envelope)"),
             blk("measurement", "DM-4", "xenon-assisted start and transition, Xe per start (fo_hall_sustainment_envelope)"),
             blk("lane", "lane_19_cathode_integration", "cathode start policy"), blk("lane", "lane_14_dual_feed", "dual-feed state machine; single-lens-v1"),
             blk("owner_decision", "OD5", "ignition start sequence; restart count (lane-24)")],
            l24("startup"), False)
        eta_block = list(closure_block)
        if a != "hall_only":
            eta_block.append(blk("measurement", "X-gain", "relative utilization gain at the operated source power, inside the coupled interval "
                                 "(fo_rf_breakeven_overlay C3 / fo_ecr_breakeven_overlay (C))"))
        cells[a]["eta_u"] = cell(
            "EXPLICITLY_UNAVAILABLE", None, "1 (dimensionless)", op_steady,
            [ev(BE, "lane_28_break_even", "cases / analysis ranges (PROPOSED analysis parameters, not values)"),
             ev(HR, "lane_17_hall_reference", "transport_numerics_binding")],
            "none", "unavailable:the break-even eta_u0 axis is a PROPOSED analysis range, not a bound on this design",
            "not derived. No verified input bounds eta_u at a flight point.",
            eta_block + preion_block, [], True)
        if a == "hall_only":
            stab_ev = [ev(HSE, "fo_hall_sustainment_envelope", "cases[*].status; findings F-9"),
                       ev(HSM, "lane_09_hall_sustainment", "entries")]
            stab_deriv = (f"fo_hall_sustainment_envelope: air cases {ovl['hs']['air_case_status_counts']} of {ovl['hs']['n_air_cases']}; F-9: "
                          + ovl["hs"]["f9"])
            stab_block = [blk("measurement", "DM-2", "flow-down extinction scan on a Vyovrinda-representative channel at the design point on the delivered composition"),
                          blk("measurement", "DI-1", "delivered feed"), blk("measurement", "DI-2", "Vyovrinda Hall design point"),
                          blk("measurement", "DM-1", "valve-outlet atomic O"),
                          blk("owner_decision", "hall_sustainment_Q2", "composition tolerance / bracketing rule (without one, F-9 applies)")]
        else:
            stab_ev = [ev(HSM, "lane_09_hall_sustainment", "entries E17-E19, E21 (pre-ionized devices)"),
                       ev(HR, "lane_17_hall_reference", "injection_interface (HALL_INLET_Z0, solver inflow GAP)"),
                       ev(RF_MD if a == "rf_hall" else ECR_MD, "lane_07_rf_evidence" if a == "rf_hall" else "lane_08_ecr_evidence",
                          "section 4 what must be measured" if a == "rf_hall" else "section 6 what must be measured")]
            stab_deriv = ("not derived. No Bundle-1 input maps sustainment of a Hall stage with pre-ionized air inflow onto the feed envelope; "
                          "the lane-09 pre-ionized items are secondary or not isolated, and the solver has no inflow capability (Hall reference section 8 GAP). "
                          "The hall_only sustainment envelope (all air cases UNDETERMINED) does not transfer to this arm.")
            stab_block = [blk("measurement", "DM-2-" + a, "extinction / stability scan of the coupled pre-ionizer + Hall stage on the delivered composition "
                              "(analogue of fo_hall_sustainment_envelope DM-2; coupled test named in fo_rf/fo_ecr overlay conditions)"),
                          blk("measurement", "DI-1", "delivered feed"), blk("measurement", "DI-2", "Vyovrinda Hall design point")] + preion_block
        cells[a]["stability"] = cell(
            "EXPLICITLY_UNAVAILABLE", None, "boolean (sustained, stable discharge) per operating point", op_steady,
            stab_ev + [ev(HGS, "lane_24_hard_gates", f"architectures.{a}.gates.G6_ignition_sustainment / G7_air_xenon")],
            "none", "unavailable:UNDETERMINED at every air case; simulation results (P5-N2 v1) are not sustainment evidence",
            stab_deriv, stab_block + closure_block[:1], l24("stability"), True)
    for a in ARCHS:
        _need(list(cells[a]) == [f for f, _, _ in MANDATORY_FIELDS] or sorted(cells[a]) == sorted(f for f, _, _ in MANDATORY_FIELDS),
              "field set mismatch")
        cells[a] = {f: cells[a][f] for f, _, _ in MANDATORY_FIELDS}
    return cells


REQUIRED_CELL_KEYS = ("status", "units", "operating_point", "evidence", "evidence_class", "uncertainty_status", "derivation")


def admissibility(cells) -> dict:
    problems = []
    for a in ARCHS:
        for f, _, _ in MANDATORY_FIELDS:
            c = cells[a].get(f)
            if c is None:
                problems.append(f"{a}.{f}: missing")
                continue
            if c["status"] not in ("POPULATED", "EXPLICITLY_UNAVAILABLE"):
                problems.append(f"{a}.{f}: status {c['status']}")
            for k in REQUIRED_CELL_KEYS:
                if c.get(k) in (None, "", [], {}):
                    problems.append(f"{a}.{f}: no {k}")
            if c["evidence_class"] not in EVIDENCE_CLASSES:
                problems.append(f"{a}.{f}: evidence class {c['evidence_class']}")
            if c["status"] == "EXPLICITLY_UNAVAILABLE" and (not c["blocking"] or c["value"] is not None):
                problems.append(f"{a}.{f}: unavailable without blocking list or with a value")
            if c["status"] == "POPULATED" and (c["value"] is None or c["evidence_class"] == "none"):
                problems.append(f"{a}.{f}: populated without value/evidence class")
    populated = {f: [a for a in ARCHS if cells[a][f]["status"] == "POPULATED"] for f, _, _ in MANDATORY_FIELDS}
    differing = [f for f, archs in populated.items()
                 if archs and (len(archs) < len(ARCHS) or len({json.dumps(cells[a][f]["value"]) for a in archs}) > 1)]
    return {
        "rule": ("Owner rule (OPERATING_MODEL.md section 3): a comparison is admissible only when all architectures are normalized to "
                 "bus_power_boundary_v1 and every mandatory field is populated or explicitly unavailable, each with units, operating point, "
                 "evidence/source, uncertainty/status and derivation. Applied mechanically per architecture x field cell."),
        "verdict": "ADMISSIBLE" if not problems else "NOT_ADMISSIBLE",
        "problems": problems,
        "boundary_version": BOUNDARY_VERSION,
        "counts": {a: {s: sum(1 for f, _, _ in MANDATORY_FIELDS if cells[a][f]["status"] == s)
                       for s in ("POPULATED", "EXPLICITLY_UNAVAILABLE")} for a in ARCHS},
        "populated_fields": {f: v for f, v in populated.items() if v},
        "populated_fields_that_differ_between_architectures": differing,
        "reading": ("Admissible here means the comparison is complete in form (every cell is populated or explicitly unavailable with its "
                    "metadata). It carries no discriminating content: the only populated field is identical in every architecture by "
                    "construction, and every Hall-, feed- and hardware-dependent field is unavailable for all three."),
    }


DECISION_RULE = {
    "id": "B1-DR-1",
    "status": "PROPOSED",
    "applies_to": "Milestone A outcome of Bundle 1 (OPERATING_MODEL.md section 2 vocabulary)",
    "steps": [
        "DR-1 Eliminations: an architecture is ELIMINATED_WITHIN_TESTED_ENVELOPE if and only if lane_24's hard_gate_status_v1.json lists it "
        "as eliminated with a non-empty elimination_basis (a binding gate FAIL on verdict-bearing evidence). Bundle 1 creates no elimination.",
        "DR-2 Admissibility: if the admissibility verdict is not ADMISSIBLE, the outcome is NO_BASELINE_YET.",
        "DR-3 Candidates: the candidate set is every architecture not eliminated under DR-1. If it is empty, the outcome is NO_BASELINE_YET.",
        "DR-4 Single candidate: if exactly one candidate X remains, the outcome is CONDITIONAL_BASELINE(X), conditioned on its lane-24 "
        "milestone-A conditions and the conditions of the overlays that apply to X.",
        "DR-5 Several candidates: CONDITIONAL_BASELINE(X) needs at least one discriminator for X and none against X. A discriminator for X is "
        "(a) a binding lane-24 criterion with verdict PASS for X and not PASS for another candidate, or (b) a mandatory field that is POPULATED "
        "for X, on a lane-24 milestone-A evidence basis (hard_physical_bound, measurement_vyovrinda, measurement_same_hardware), and not so "
        "populated with an equal value for every other candidate. If no architecture has a discriminator, or more than one does, the outcome is "
        "NO_BASELINE_YET.",
        "DR-6 Not discriminators: break-even overlay placements (conditional inequalities over PROPOSED ranges), literature transfer "
        "(lane-24 basis measurement_similar_hardware, not verdict-bearing), component counts, PROPOSED analysis values, screening-candidate or "
        "unadmitted-closure results, and withdrawn 0-D Hall numbers.",
    ],
    "note": "PROPOSED for the owner; stated before the tables and applied mechanically by build_bundle1.py (function apply_rule).",
}


def apply_rule(cells, adm, gates) -> dict:
    trace = []
    eliminated = []
    for a in ARCHS:
        g = gates["per"][a]
        if g["eliminated"]:
            _need(bool(g["elimination_basis"]) and a in gates["eliminated"], f"lane-24 eliminated {a} without basis")
            eliminated.append(a)
    trace.append(f"DR-1: lane-24 eliminated = {eliminated} (lane-24 eliminated list {gates['eliminated']}).")
    if adm["verdict"] != "ADMISSIBLE":
        trace.append("DR-2: admissibility not met -> NO_BASELINE_YET.")
        return {"form": "NO_BASELINE_YET", "architecture": None, "trace": trace, "discriminators": {a: [] for a in ARCHS},
                "eliminated": eliminated}
    trace.append("DR-2: admissibility verdict ADMISSIBLE.")
    cand = [a for a in ARCHS if a not in eliminated]
    trace.append(f"DR-3: candidates = {cand}.")
    if not cand:
        return {"form": "NO_BASELINE_YET", "architecture": None, "trace": trace, "discriminators": {}, "eliminated": eliminated}
    if len(cand) == 1:
        trace.append(f"DR-4: single candidate {cand[0]}.")
        return {"form": "CONDITIONAL_BASELINE", "architecture": cand[0], "trace": trace, "discriminators": {cand[0]: ["sole candidate"]},
                "eliminated": eliminated}
    disc = {a: [] for a in cand}
    for a in cand:
        crit = gates["per"][a]["criteria"]
        for cid, cd in crit.items():
            if not cd["binding_gate"] or cd["verdict"] != "PASS":
                continue
            if any(gates["per"][b]["criteria"][cid]["verdict"] != "PASS" for b in cand if b != a):
                disc[a].append(f"(a) {cid} PASS")
        for f, _, _ in MANDATORY_FIELDS:
            c = cells[a][f]
            basis = c.get("basis")
            if c["status"] != "POPULATED" or basis not in MILESTONE_A_BASES_FROM_LANE24:
                continue
            others_equal = all(cells[b][f]["status"] == "POPULATED" and cells[b][f].get("basis") in MILESTONE_A_BASES_FROM_LANE24
                               and cells[b][f]["value"] == c["value"] for b in cand if b != a)
            if not others_equal:
                disc[a].append(f"(b) {f} populated on basis {basis}")
    n_pass_crit = sum(1 for a in cand for cd in gates["per"][a]["criteria"].values() if cd["verdict"] == "PASS")
    n_pop_basis = sum(1 for a in cand for f, _, _ in MANDATORY_FIELDS
                      if cells[a][f]["status"] == "POPULATED" and cells[a][f].get("basis") in MILESTONE_A_BASES_FROM_LANE24)
    trace.append(f"DR-5: lane-24 criteria with verdict PASS across candidates: {n_pass_crit}; populated fields on a milestone-A basis: "
                 f"{n_pop_basis}; discriminators per candidate: " + json.dumps(disc, sort_keys=True) + ".")
    with_disc = [a for a in cand if disc[a]]
    if len(with_disc) == 1:
        trace.append(f"DR-5: exactly one candidate with a discriminator: {with_disc[0]}.")
        return {"form": "CONDITIONAL_BASELINE", "architecture": with_disc[0], "trace": trace, "discriminators": disc,
                "eliminated": eliminated}
    trace.append("DR-5: " + ("no candidate has a discriminator" if not with_disc else "more than one candidate has a discriminator")
                 + " -> NO_BASELINE_YET.")
    return {"form": "NO_BASELINE_YET", "architecture": None, "trace": trace, "discriminators": disc, "eliminated": eliminated}


def check_prose_premises(gates, ovl) -> int:
    """The fixed prose of this bundle rests on these input facts; if any changes, stop (new bundle version needed)."""
    _need(gates["admitted_members"] == [], "lane 24 now lists admitted Hall members: the closure-dependent text is stale")
    _need(gates["n_register_items"] == 0, "the lane-24 evidence register is no longer empty: the prose is stale")
    for a in ARCHS:
        _need(all(v == "UNDETERMINED" for v in gates["per"][a]["gate_verdicts"].values()), f"lane-24 verdicts for {a} changed")
    ns = {len(gates["per"][a]["milestone_A"]["conditions"]) for a in ARCHS}
    _need(len(ns) == 1, "architectures carry different numbers of lane-24 conditions: the prose is stale")
    for k in ("rf", "ecr"):
        pc = ovl[k]["placement_counts"]
        _need(pc["CLEARLY_ABOVE_BREAKEVEN"] == 0 and pc["CLEARLY_BELOW"] == 0, f"{k} overlay now has a definite placement")
    _need(set(ovl["hs"]["air_case_status_counts"]) == {"UNDETERMINED"}, "hall_only sustainment air-case statuses changed")
    txt = (REPO / "docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md").read_text(encoding="utf-8")
    _need("owner's acceptance of the model-family assumptions A1–A8" in txt, "break-even A1-A8 owner item not found")
    return ns.pop()


def build(gov=None) -> dict:
    pins = verify_pins()
    gov = gov or check_governance()
    comps = boundary_components()
    feed = feed_extract()
    vd = vd_extract()
    grid = grid_extract()
    gates = gates_extract()
    ovl = overlays_extract()
    elec = electrical_extract()
    be = _json(BE)
    n_cond = check_prose_premises(gates, ovl)
    cells = build_cells(feed, vd, grid, gates, ovl, elec, comps)
    adm = admissibility(cells)
    res = apply_rule(cells, adm, gates)

    # every blocking id must be a registered lane / follow-on / trigger, or a named measurement / owner item of an input
    measurement_ids = {d["id"] for d in ovl["hs"]["decisive_measurements"]} | {"RF-C_del", "ECR-C_del", "X-gain", "DM-2-rf_hall",
                                                                               "DM-2-ecr_hall",
                                                                               "lane24:measurement_vyovrinda|measurement_same_hardware"}
    owner_ids = {"feed_envelope_Q2", "hall_reference_Q1", "hall_sustainment_Q2"} | {d["id"] for d in gates["open_owner_decisions"]}
    blocking_lanes, blocking_triggers, blocking_meas, blocking_owner = set(), set(), set(), set()
    for a in ARCHS:
        for f, c in cells[a].items():
            for b in c["blocking"]:
                if b["kind"] == "lane":
                    _need(b["id"] in gov["lane_ids"] | gov["fo_ids"], f"unknown lane id {b['id']}")
                    blocking_lanes.add(b["id"])
                elif b["kind"] == "trigger":
                    _need(b["id"] in gov["trigger_ids"], f"unknown trigger id {b['id']}")
                    blocking_triggers.add(b["id"])
                elif b["kind"] == "measurement":
                    _need(b["id"] in measurement_ids, f"unknown measurement id {b['id']}")
                    blocking_meas.add(b["id"])
                elif b["kind"] == "owner_decision":
                    _need(b["id"] in owner_ids, f"unknown owner item {b['id']}")
                    blocking_owner.add(b["id"])
                else:
                    raise InputError(f"unknown blocking kind {b['kind']}")

    blocking_fields = {a: [f for f, c in cells[a].items() if c["status"] == "EXPLICITLY_UNAVAILABLE"] for a in ARCHS}
    single_lens_blocking = sorted(l for l in blocking_lanes if l in gov["single_lens_lanes"])

    per_arch_status = {}
    for a in ARCHS:
        g = gates["per"][a]
        per_arch_status[a] = {
            "bundle_status": "ELIMINATED_WITHIN_TESTED_ENVELOPE" if a in res["eliminated"] else "NOT_ELIMINATED",
            "lane24_eliminated": g["eliminated"],
            "lane24_elimination_basis": g["elimination_basis"],
            "lane24_statement": g["milestone_A"]["statement"],
            "gate_verdicts": g["gate_verdicts"],
            "binding_gates": g["binding_gates"],
            "proposed_gates": g["proposed_gates"],
            "conflicts": g["conflicts"],
            "open_owner_items": g["milestone_A"]["open_owner_items"],
        }

    outcome = {
        "form": res["form"],
        "architecture": res["architecture"],
        "label": res["form"] if res["architecture"] is None else f"{res['form']}({res['architecture']})",
        "proposal_status": "DRAFT for owner review; a proposal, not a decision",
        "rule_trace": res["trace"],
        "discriminators": res["discriminators"],
        "blocking_fields": blocking_fields,
        "blocking_lanes": sorted(blocking_lanes),
        "blocking_triggers": sorted(blocking_triggers),
        "blocking_measurements": sorted(blocking_meas),
        "blocking_owner_decisions": sorted(blocking_owner),
        "conditions": [],
        "why_no_single_architecture": (
            "All three architectures are non-eliminated (lane 24: every gate UNDETERMINED, evidence register empty, no admitted Hall "
            f"member). Each carries the same {n_cond} lane-24 milestone-A conditions, none discharged. The only populated mandatory field (V_d) is identical by INV-V1. The "
            "overlays place no RF or ECR entry clearly on either side of break-even and support no hall_only air case by literature transfer "
            "(F-9). No input supplies a discriminator, so singling out one architecture, even conditionally, would rest on preference, not "
            "evidence."),
    }
    if res["form"] == "CONDITIONAL_BASELINE":  # not reached with the pinned inputs; kept explicit so the rule stays mechanical
        x = res["architecture"]
        outcome["conditions"] = [{"id": f"C-{c['criterion']}", "demonstrate": c["requirement"], "pass_criterion": c["requirement"],
                                  "source": HGS, "demonstrated_by": c["discharged_by_A"]} for c in gates["per"][x]["milestone_A"]["conditions"]]

    conditions_on_record = {}
    for a in ARCHS:
        rec = {"lane24_milestone_A_conditions": gates["per"][a]["milestone_A"]["conditions"]}
        if a == "hall_only":
            rec["fo_hall_sustainment_envelope"] = ovl["hs"]["conditions"]
        elif a == "rf_hall":
            rec["fo_rf_breakeven_overlay"] = ovl["rf"]["conditions"]
        else:
            rec["fo_ecr_breakeven_overlay"] = {"condition_set": ovl["ecr"]["condition_set"], "explicit_conditions": ovl["ecr"]["explicit_conditions"]}
        conditions_on_record[a] = rec
    shared = sorted({c["criterion"] for c in gates["per"]["hall_only"]["milestone_A"]["conditions"]}
                    & {c["criterion"] for c in gates["per"]["rf_hall"]["milestone_A"]["conditions"]}
                    & {c["criterion"] for c in gates["per"]["ecr_hall"]["milestone_A"]["conditions"]})

    rf_dm = ovl["rf"]["decisive_measurement"]
    questions = {
        "i_conditional_selection_now": (
            f"{outcome['label']}. No architecture is eliminated and none can be singled out: all three stay conditional candidates, each "
            "subject to its lane-24 milestone-A conditions (all UNDETERMINED) plus its overlay conditions."),
        "ii_what_blocks_physics_backed_selection": [
            {"item": "admitted Hall transport closure", "state": "credible set empty (gate 3 FAIL); P5-N2 v1 INCONCLUSIVE permanently; "
             "v2 Question A disposition A-NO (no v2 now)",
             "ids": ["T_ABSOLUTE_COMPARISON", "fo_absolute_comparison", "lane_02_ood_attribution", "fo_v2_domain_question_a",
                     "T_V2_QUESTION_B", "T_DX5_EVIDENCE", "T_O4_DISPOSITION_MATRIX", "fo_o4_disposition_matrix", "T_FACILITY_SCORE",
                     "lane_29_exb_physics", "lane_35_hallmap_spec"]},
            {"item": "chemistry for the delivered feed", "state": "abep-n2n-0.11 is scoped to P5-N2 validation (T_e 2-30 eV); O/O2 chemistry absent",
             "ids": ["lane_13_o_o2_audit", "fo_v2_domain_question_a", "fo_v2_excitation_question_b"]},
            {"item": "common-boundary performance", "state": "P_bus and every component load/efficiency TBD; feed state TBD (DI-1)",
             "ids": ["T_AUX_BUS", "fo_aux_bus_comparison", "lane_12_arch_harness", "lane_34_ledgers", "lane_19_cathode_integration",
                     "lane_16_feed_envelope", "lane_33_upstream_icd"]},
            {"item": "pre-ionizer physics at the common inlet", "state": "source ion cost on air, eta_t and the response (alpha, chi, eta_v,S) unmeasured; "
             "solver has no inflow capability at HALL_INLET_Z0",
             "ids": ["lane_07_rf_evidence", "lane_08_ecr_evidence", "lane_18_interstage", "lane_28_break_even", "lane_25_min_decisive_experiment",
                     "T_EXPERIMENT_PACKAGE"]},
            {"item": "Hall sustainment on air at the design point", "state": "all air cases UNDETERMINED; F-9",
             "ids": ["fo_hall_sustainment_envelope", "lane_09_hall_sustainment", "lane_25_min_decisive_experiment"]},
            {"item": "mass, thermal, life, cathode, start-up (milestone C, and B where hard gates need them)",
             "state": "all TBD", "ids": ["T_VETO_LAYER", "fo_veto_layer", "lane_21_mass_bom", "lane_15_thermal_life", "lane_32_wall_life",
                                         "lane_10_cathode_dossier", "lane_19_cathode_integration", "lane_14_dual_feed"]},
        ],
        "iii_what_could_overturn": [
            "A committed hard-bound script (lane-24 basis hard_physical_bound, milestone A) that shows a binding criterion FAIL at architecture "
            "scope for one architecture: lane 24 would record ELIMINATED_WITHIN_TESTED_ENVELOPE for it. Lane 24 states such a bound needs upper "
            "bounds on the total exhaust mass flow and the feed stagnation enthalpy, which are TBD.",
            "A Vyovrinda or same-hardware measurement that discharges a lane-24 condition (PASS) for one architecture and not for the others. "
            "Examples named by the inputs: the DM-2 extinction scan for hall_only on the delivered composition (fo_hall_sustainment_envelope); "
            f"a measured RF delivered-ion bus cost C_del at or below {rf_dm['C_del_at_or_below_which_CLEARLY_BELOW_add_only_W_per_A']} W/A "
            f"(CLEARLY_BELOW, add_only) or above {rf_dm['C_del_above_which_CLEARLY_ABOVE_W_per_A']} W/A (CLEARLY_ABOVE) "
            "(fo_rf_breakeven_overlay; a break-even placement, not a hard gate, until it enters P_bus or a lane-24 criterion); "
            "a measured end-to-end ECR C_del,bus with eta_t on an air-representative feed (fo_ecr_breakeven_overlay).",
            "An admitted Hall transport closure (T_ABSOLUTE_COMPARISON): design Hall maps per member would populate T, eta_u, P_bus "
            "(with the lane-20 chain evidence) and stability envelopes for all three arms at once (milestone B route).",
            "An owner decision to adopt a discriminating criterion that is not evidence-based (for example a preference for fewer bus "
            "components). That changes the decision rule, not the evidence, and needs a new rule version (B1-DR-2).",
            "Owner decisions OD1-OD14 on the lane-24 matrix change what counts toward PASS/FAIL but, while every verdict is UNDETERMINED "
            "and the register is empty, none of them creates a discriminator.",
        ],
    }

    inputs = []
    for lane in list(PREREQUISITES) + list(CONTEXT):
        inputs.append({
            "lane": lane,
            "title": gov["lane_titles"][lane],
            "role": "prerequisite" if lane in PREREQUISITES else "context",
            "commit": PREREQUISITES.get(lane) or CONTEXT[lane],
            "verification_protocol": gov["protocols"][lane]["protocol"],
            "protocol_source": gov["protocols"][lane]["protocol_source"],
            "protocol_notes": gov["protocols"][lane]["notes"],
            "decisive_for_B_or_C_allowed": not gov["protocols"][lane]["protocol"].startswith("single-lens"),
            "files": [{"path": p["path"], "sha256": p["sha256"]} for p in pins if p["lane"] == lane],
        })

    owner_q = []

    def addq(lane, path, items, prefix=""):
        for i, q in enumerate(items, 1):
            owner_q.append({"lane": lane, "source": path, "id": f"{prefix}{i}" if prefix else None, "question": q})

    addq("lane_16_feed_envelope", FE + " open_questions", feed["open_questions"], "FE-Q")
    addq("lane_17_hall_reference", HR + " open_questions_for_owner", _json(HR)["open_questions_for_owner"], "HR-")
    addq("lane_18_interstage", IS_MD + " sections 8-9", interstage_owner_items(), "IS-Q")
    addq("lane_20_ppu_magnet", EC + " open_questions_for_owner", elec["open_questions"], "EC-Q")
    for d in gates["open_owner_decisions"]:
        owner_q.append({"lane": "lane_24_hard_gates", "source": HGM + " open_owner_decisions", "id": d["id"],
                        "question": d["topic"] + " (current handling: " + d["current_handling"] + ")"})
    owner_q.append({"lane": "lane_28_break_even", "source": "docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md section 0 / 10",
                    "id": "BE-A1-A8", "question": "Accept or reject the model-family assumptions A1-A8 on which every break-even statement is conditional."})
    addq("fo_rf_breakeven_overlay", RFO + " open_questions_for_owner", ovl["rf"]["open_questions"], "RFO-Q")
    for d in ovl["ecr"]["owner_decisions"]:
        owner_q.append({"lane": "fo_ecr_breakeven_overlay", "source": ECRO + " owner_decisions_requested", "id": d["id"], "question": d["question"]})
    addq("fo_hall_sustainment_envelope", HSE + " open_questions_for_owner", ovl["hs"]["open_questions"], "HS-Q")
    addq("lane_11_bus_boundary", BND_MD + " section 9", md_owner_items(BND_MD, r"## 9\. Open questions for the owner", r"## 10\."), "BND-Q")
    addq("lane_23_comparison_grid", CG + " open_questions_for_owner", grid["open_questions"])
    for q in owner_q:
        if q["id"] is None:
            q["id"] = q["question"].split(" ", 1)[0]

    doc = {
        "id": BUNDLE_ID,
        "title": "Bundle 1: Architecture Conditional Selection (Milestone A)",
        "follow_on": FOLLOW_ON,
        "trigger": TRIGGER,
        "attempt": ATTEMPT,
        "execution_key": EXECUTION_KEY,
        "claim": {"utc": gov["claim_utc"], "dependency_state_hash": gov["dependency_state_hash"],
                  "source": GOV["trigger_ledger"], "prerequisite_identities_match_pins": True},
        "base_commit": BASE_COMMIT,
        "prepared": PREPARED,
        "status": "DRAFT_FOR_OWNER_REVIEW",
        "architectures": list(ARCHS),
        "boundary_version": BOUNDARY_VERSION,
        "what_it_is": ("A synthesis of the verified T_BUNDLE1 prerequisites into the owner's Milestone-A form: admissibility of the "
                       "three-architecture comparison on bus_power_boundary_v1, hard-gate status, and one outcome under a PROPOSED decision rule."),
        "what_it_is_not": ("Not a decision, not a ranking, not a prediction. It adds no physics, source or number: every value is read "
                           "from a pinned input. No Hall closure, screening candidate or withdrawn 0-D Hall number is used; nothing is wired "
                           "into archengine; no golden moves."),
        "milestones": {
            "supports": ["A"],
            "A": "Milestone-A outcome in the owner's vocabulary, with the blocking fields, lanes and measurements.",
            "to_reach_B": ["an admitted Hall transport closure and design Hall maps per member (T_ABSOLUTE_COMPARISON)",
                           "chemistry for the delivered feed (O/O2 absent; N2 set scoped to P5-N2 validation)",
                           "common-boundary ledgers with evidenced loads and efficiencies (T_AUX_BUS)",
                           "the feed design baseline (DI-1) and the Vyovrinda Hall design point (DI-2)",
                           "measured pre-ionizer delivered-ion cost, eta_t and response (rf_hall, ecr_hall); DM-2 for hall_only",
                           "owner approval of the lane-24 matrix (DRAFT_PENDING_OWNER) and of this decision rule",
                           "second-lens verification of any single-lens-v1 lane before it is decisive"],
            "to_reach_C": ["mass, thermal, life, start-up and cathode closure on the same boundary (T_VETO_LAYER, lane_19_cathode_integration)",
                           "every TBD threshold and open lane-24 reading resolved (OD1-OD14)", "integrated mission closure"],
        },
        "inputs": inputs,
        "decision_rule": DECISION_RULE,
        "mandatory_fields": [{"id": f, "symbol": s, "meaning": m} for f, s, m in MANDATORY_FIELDS],
        "admissibility": {**adm, "cells": cells},
        "hard_gates": {
            "source": HGS,
            "lane24_matrix_status": gates["matrix_status"],
            "lane24_matrix_version": gates["matrix_version"],
            "lane24_eliminated": gates["eliminated"],
            "lane24_not_eliminated": gates["not_eliminated"],
            "evidence_register_items": gates["n_register_items"],
            "evidence_register_note": gates["register_note"],
            "per_architecture": per_arch_status,
            "overlays": {
                "rf_hall": {"source": RFO, "placement_counts": ovl["rf"]["placement_counts"],
                            "hard_gate_reading": ovl["rf"]["hard_gate_statement"], "eta_t": ovl["rf"]["eta_t_statement"]},
                "ecr_hall": {"source": ECRO, "placement_counts": ovl["ecr"]["placement_counts"],
                             "hard_gate_reading": ovl["ecr"]["hard_gate_statement"], "air_arm": ovl["ecr"]["air_arm_statement"]},
                "hall_only": {"source": HSE, "air_case_status_counts": ovl["hs"]["air_case_status_counts"],
                              "all_case_status_counts": ovl["hs"]["all_case_status_counts"], "F-9": ovl["hs"]["f9"]},
            },
        },
        "outcome": outcome,
        "conditions_on_record": {"shared_lane24_criteria": shared, "per_architecture": conditions_on_record},
        "three_questions": questions,
        "evidence_weight": {
            "rule": ("single-lens-v1 lanes cannot be decisive evidence for Milestone B or C until they pass the second (two-lens) "
                     "verification (OPERATING_MODEL.md section 1)."),
            "inputs_single_lens": [i["lane"] for i in inputs if not i["decisive_for_B_or_C_allowed"]],
            "blocking_lanes_single_lens": single_lens_blocking,
            "note": ("Every Bundle-1 input is two-lens verified. The single-lens-v1 lanes above are named only as blocking lanes: their future "
                     "results need the second lens before they can be decisive for Milestone B or C."),
        },
        "owner_questions_open": owner_q,
        "provenance": {"generated_by": SCRIPT_REL, "check": f"python {SCRIPT_REL} --check", "schema": SCHEMA_REL,
                       "governance_checked": sorted(GOV.values())},
    }
    return doc


# --------------------------------------------------------------------------------------------------------------------
# Minimal JSON-Schema validator (draft 2020-12 keyword subset used by bundle1_v1.schema.json)
# --------------------------------------------------------------------------------------------------------------------
def validate(inst, schema, root=None, path="$") -> list[str]:
    root = root or schema
    errs = []
    if "$ref" in schema:
        ref = schema["$ref"]
        _need(ref.startswith("#/$defs/"), f"unsupported $ref {ref}")
        return validate(inst, root["$defs"][ref.split("/")[-1]], root, path)
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        ok = any((tt == "object" and isinstance(inst, dict)) or (tt == "array" and isinstance(inst, list))
                 or (tt == "string" and isinstance(inst, str)) or (tt == "boolean" and isinstance(inst, bool))
                 or (tt == "integer" and isinstance(inst, int) and not isinstance(inst, bool))
                 or (tt == "number" and isinstance(inst, (int, float)) and not isinstance(inst, bool))
                 or (tt == "null" and inst is None) for tt in types)
        if not ok:
            return [f"{path}: type {type(inst).__name__} not in {types}"]
    if "const" in schema and inst != schema["const"]:
        errs.append(f"{path}: {inst!r} != const {schema['const']!r}")
    if "enum" in schema and inst not in schema["enum"]:
        errs.append(f"{path}: {inst!r} not in enum")
    if isinstance(inst, str):
        if "minLength" in schema and len(inst) < schema["minLength"]:
            errs.append(f"{path}: shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errs.append(f"{path}: does not match {schema['pattern']}")
    if isinstance(inst, list):
        if "minItems" in schema and len(inst) < schema["minItems"]:
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, x in enumerate(inst):
                errs += validate(x, schema["items"], root, f"{path}[{i}]")
    if isinstance(inst, dict):
        for k in schema.get("required", []):
            if k not in inst:
                errs.append(f"{path}: missing {k}")
        props = schema.get("properties", {})
        for k, v in inst.items():
            if k in props:
                errs += validate(v, props[k], root, f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected key {k}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errs += validate(v, schema["additionalProperties"], root, f"{path}.{k}")
    for sub in schema.get("allOf", []):
        errs += validate(inst, sub, root, path)
    if "if" in schema:
        if not validate(inst, schema["if"], root, path):
            errs += validate(inst, schema.get("then", {}), root, path)
        elif "else" in schema:
            errs += validate(inst, schema["else"], root, path)
    return errs


# --------------------------------------------------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------------------------------------------------
def _esc(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_md(doc: dict) -> str:
    L = []
    w = L.append
    oc = doc["outcome"]
    adm = doc["admissibility"]
    w("# Bundle 1: Architecture Conditional Selection (Milestone A)")
    w("")
    w("> Generated by `docs/milestones/bundle1/build_bundle1.py` from pinned inputs. Do not edit by hand; rerun the script "
      "(`--check` reproduces this file and `bundle1_v1.json` byte for byte).")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| status | **{doc['status']}**: a proposal for the owner, not a decision |")
    w(f"| follow-on / trigger | `{doc['follow_on']}` / `{doc['trigger']}` attempt {doc['attempt']} (execution key `{doc['execution_key'][:16]}…`) |")
    w(f"| base commit | `{doc['base_commit']}` |")
    w(f"| boundary | `{doc['boundary_version']}` |")
    w("| milestone | supports **A**; what B and C need is in section 7 |")
    w(f"| machine-readable | `bundle1_v1.json` (schema `bundle1_v1.schema.json`) |")
    w("")
    w(f"**Outcome (PROPOSED rule, applied mechanically): `{oc['label']}`.** {oc['why_no_single_architecture']}")
    w("")
    w(doc["what_it_is_not"])
    w("")
    w("## 1. Decision rule (PROPOSED, stated before the tables)")
    w("")
    w(f"Rule `{doc['decision_rule']['id']}`, status **{doc['decision_rule']['status']}**. {doc['decision_rule']['note']}")
    w("")
    for s in doc["decision_rule"]["steps"]:
        w(f"- {s}")
    w("")
    w("## 2. Admissibility on `bus_power_boundary_v1`")
    w("")
    w(adm["rule"])
    w("")
    w(f"**Verdict: {adm['verdict']}.** {adm['reading']}")
    w("")
    w("| field | meaning | " + " | ".join(f"`{a}`" for a in doc["architectures"]) + " |")
    w("|---|---|" + "---|" * len(doc["architectures"]))
    for f in doc["mandatory_fields"]:
        row = []
        for a in doc["architectures"]:
            c = adm["cells"][a][f["id"]]
            if c["status"] == "POPULATED":
                row.append(f"POPULATED: {_esc(c['value'])} {c['units']} ({c['evidence_class']}, {_esc(c['uncertainty_status'].split(' (')[0])})")
            else:
                row.append("EXPLICITLY_UNAVAILABLE")
        w(f"| `{f['id']}` ({f['symbol']}) | {_esc(f['meaning'])} | " + " | ".join(row) + " |")
    w("")
    w("Counts per architecture: " + "; ".join(f"`{a}` {v}" for a, v in adm["counts"].items()) + ". Populated fields that differ "
      f"between architectures: {adm['populated_fields_that_differ_between_architectures'] or 'none'}.")
    w("")
    w("### 2.1 Cell metadata (identical structure for every architecture x field; full text in the JSON)")
    w("")
    w("| architecture | field | units | operating point | evidence (path, lane) | evidence class | uncertainty / status | blocking |")
    w("|---|---|---|---|---|---|---|---|")
    for a in doc["architectures"]:
        for f in doc["mandatory_fields"]:
            c = adm["cells"][a][f["id"]]
            evs = "; ".join(f"`{e['path']}` ({e['input_lane']})" for e in c["evidence"])
            b = ", ".join(f"{x['id']}" for x in c["blocking"])
            w(f"| `{a}` | `{f['id']}` | {_esc(c['units'])} | {c['operating_point']['id']} | {_esc(evs)} | {c['evidence_class']} | "
              f"{_esc(c['uncertainty_status'])} | {_esc(b)} |")
    w("")
    ops = {}
    for a in doc["architectures"]:
        for f in doc["mandatory_fields"]:
            op = adm["cells"][a][f["id"]]["operating_point"]
            ops[op["id"]] = op["definition"]
    w("Operating points:")
    w("")
    for k in sorted(ops):
        w(f"- `{k}`: {ops[k]}")
    w("")
    w("`P_feed` / `T_feed` are the valve-outlet pressure [Pa] and temperature [K]. Lane 16 leaves them TBD at every case; they stay "
      "EXPLICITLY_UNAVAILABLE and are not filled from the superseded 0-D assumptions, code defaults or historical values. `P_bus` is "
      "the sum of every `bus_power_boundary_v1` component of the architecture (discharge, magnets, cathode keeper/heater, pre-ionizer "
      "source incl. its magnet, PPU losses, flow control, compressor, thermal control, housekeeping), never a discharge-only, "
      "absorbed-RF or ECR-source-only number.")
    w("")
    w("## 3. Hard gates (lane 24) and overlay readings")
    w("")
    hg = doc["hard_gates"]
    w(f"Source `{hg['source']}` (matrix {hg['lane24_matrix_version']}, {hg['lane24_matrix_status']}); evidence register items: "
      f"{hg['evidence_register_items']}. Lane-24 eliminated: {hg['lane24_eliminated'] or 'none'}; not eliminated: "
      + ", ".join(f"`{a}`" for a in hg["lane24_not_eliminated"]) + ".")
    w("")
    gate_ids = list(next(iter(hg["per_architecture"].values()))["gate_verdicts"])
    w("| architecture | Bundle-1 status | " + " | ".join(gate_ids) + " |")
    w("|---|---|" + "---|" * len(gate_ids))
    for a, s in hg["per_architecture"].items():
        w(f"| `{a}` | {s['bundle_status']} | " + " | ".join(s["gate_verdicts"][g] for g in gate_ids) + " |")
    w("")
    for a, s in hg["per_architecture"].items():
        w(f"- `{a}` (lane-24 verbatim): {s['lane24_statement']}")
    w("")
    ov = hg["overlays"]
    w("| overlay | counts | hard-gate reading (quoted) |")
    w("|---|---|---|")
    w(f"| `rf_hall` (`{ov['rf_hall']['source']}`) | {_esc(json.dumps(ov['rf_hall']['placement_counts']))} | {_esc(ov['rf_hall']['hard_gate_reading'])} |")
    w(f"| `ecr_hall` (`{ov['ecr_hall']['source']}`) | {_esc(json.dumps(ov['ecr_hall']['placement_counts']))} | {_esc(ov['ecr_hall']['hard_gate_reading'])} |")
    w(f"| `hall_only` (`{ov['hall_only']['source']}`) | air cases {_esc(json.dumps(ov['hall_only']['air_case_status_counts']))} | F-9: {_esc(ov['hall_only']['F-9'])} |")
    w("")
    w("Break-even placements and literature transfer are not hard-gate evidence (lane-24 basis table): they eliminate nothing here.")
    w("")
    w("## 4. Outcome")
    w("")
    w(f"**`{oc['label']}`** ({oc['proposal_status']}).")
    w("")
    w("Rule trace:")
    w("")
    for t in oc["rule_trace"]:
        w(f"- {t}")
    w("")
    w("Blocking fields: " + "; ".join(f"`{a}`: " + ", ".join(v) for a, v in oc["blocking_fields"].items()) + ".")
    w("")
    w("Blocking lanes: " + ", ".join(f"`{x}`" for x in oc["blocking_lanes"]) + ".")
    w("")
    w("Blocking triggers: " + ", ".join(f"`{x}`" for x in oc["blocking_triggers"]) + ". Blocking measurements: "
      + ", ".join(f"`{x}`" for x in oc["blocking_measurements"]) + ". Blocking owner decisions: "
      + ", ".join(f"`{x}`" for x in oc["blocking_owner_decisions"]) + ".")
    w("")
    w("### 4.1 Conditions on record per architecture (what a later conditional baseline would have to demonstrate)")
    w("")
    cr = doc["conditions_on_record"]
    w("Shared lane-24 criteria (all three architectures): " + ", ".join(f"`{c}`" for c in cr["shared_lane24_criteria"]) + ". "
      "They include Hall sustainment on atmospheric propellant (`G6.sustainment`) and ignition from off (`G6.ignition`).")
    w("")
    w("| criterion | requirement | current verdict | can eliminate | discharged at A by |")
    w("|---|---|---|---|---|")
    for c in cr["per_architecture"]["hall_only"]["lane24_milestone_A_conditions"]:
        w(f"| `{c['criterion']}` | {_esc(c['requirement'])} | {c['current_verdict']} | {c['can_eliminate']} | {', '.join(c['discharged_by_A'])} |")
    w("")
    w("The table is `hall_only`'s list; `rf_hall` and `ecr_hall` carry the same criteria (their element lists add the pre-ionizer "
      "components; full lists in the JSON).")
    w("")
    w("Architecture-specific conditions from the overlays (quoted):")
    w("")
    for c in cr["per_architecture"]["hall_only"]["fo_hall_sustainment_envelope"]:
        w(f"- `hall_only` {c['id']}: {_esc(c['condition'])} [state: {_esc(c['state'])}]")
    for c in cr["per_architecture"]["rf_hall"]["fo_rf_breakeven_overlay"]:
        w(f"- `rf_hall`: {_esc(c)}")
    w(f"- `ecr_hall`: {_esc(cr['per_architecture']['ecr_hall']['fo_ecr_breakeven_overlay']['condition_set'])}")
    w("")
    w("## 5. The three questions")
    w("")
    q = doc["three_questions"]
    w(f"**(i) Conditional selection now.** {q['i_conditional_selection_now']}")
    w("")
    w("**(ii) What blocks physics-backed selection (Milestone B).**")
    w("")
    w("| item | state | lanes / triggers |")
    w("|---|---|---|")
    for it in q["ii_what_blocks_physics_backed_selection"]:
        w(f"| {_esc(it['item'])} | {_esc(it['state'])} | {', '.join('`' + i + '`' for i in it['ids'])} |")
    w("")
    w("**(iii) What could overturn the outcome.**")
    w("")
    for it in q["iii_what_could_overturn"]:
        w(f"- {it}")
    w("")
    w("## 6. Evidence weight")
    w("")
    ew = doc["evidence_weight"]
    w(ew["rule"] + " " + ew["note"])
    w("")
    w("| input lane | role | commit | verification protocol | decisive for B/C allowed | files (sha256) |")
    w("|---|---|---|---|---|---|")
    for i in doc["inputs"]:
        files = "<br>".join(f"`{f['path']}` `{f['sha256'][:12]}…`" for f in i["files"])
        proto = i["verification_protocol"] + ("; " + "; ".join(i["protocol_notes"]) if i["protocol_notes"] else "")
        w(f"| `{i['lane']}` | {i['role']} | `{i['commit'][:10]}` | {_esc(proto)} | {i['decisive_for_B_or_C_allowed']} | {files} |")
    w("")
    w("Single-lens-v1 inputs: " + (", ".join(ew["inputs_single_lens"]) or "none") + ". Single-lens-v1 lanes named as blocking: "
      + ", ".join(f"`{x}`" for x in ew["blocking_lanes_single_lens"]) + ".")
    w("")
    w("### 6.1 Owner questions left open by the input lanes (listed, not answered)")
    w("")
    w("| lane | id | question | source |")
    w("|---|---|---|---|")
    for o in doc["owner_questions_open"]:
        w(f"| `{o['lane']}` | {_esc(o['id'])} | {_esc(o['question'])} | `{_esc(o['source'])}` |")
    w("")
    w("## 7. Milestones")
    w("")
    ms = doc["milestones"]
    w(f"- **A (supported):** {ms['A']}")
    w("- **To reach B:** " + "; ".join(ms["to_reach_B"]) + ".")
    w("- **To reach C:** " + "; ".join(ms["to_reach_C"]) + ".")
    w("")
    w("## 8. Reproduce")
    w("")
    w("```")
    w(f"python {SCRIPT_REL}            # rewrite bundle1_v1.json and BUNDLE1.md")
    w(f"python {SCRIPT_REL} --check    # exit 1 unless both are reproduced byte for byte")
    w("python -m pytest -q tests/test_bundle1.py")
    w("```")
    w("")
    return "\n".join(L)


def forbidden_hits(text: str) -> list[str]:
    return sorted({m.group(0) for m in FORBIDDEN.finditer(text)})


def render_all() -> tuple[str, str]:
    doc = build()
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    errs = validate(doc, schema)
    if errs:
        raise InputError("bundle JSON does not validate against the schema: " + "; ".join(errs[:20]))
    js = json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    md = render_md(doc)
    for name, text in (("json", js), ("md", md)):
        hits = forbidden_hits(text)
        if hits:
            raise InputError(f"forbidden wording in generated {name}: {hits}")
    return js, md


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="verify the committed files are reproduced byte for byte")
    args = ap.parse_args(argv)
    js, md = render_all()
    targets = ((REPO / OUT_JSON_REL, js), (REPO / OUT_MD_REL, md))
    if args.check:
        bad = [str(p.relative_to(REPO)) for p, t in targets if not p.is_file() or p.read_text(encoding="utf-8") != t]
        if bad:
            print("NOT REPRODUCED: " + ", ".join(bad))
            return 1
        print("OK: bundle1_v1.json and BUNDLE1.md reproduced")
        return 0
    for p, t in targets:
        p.write_text(t, encoding="utf-8")
    print("wrote " + ", ".join(str(p.relative_to(REPO)) for p, _ in targets))
    return 0


if __name__ == "__main__":
    sys.exit(main())

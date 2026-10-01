#!/usr/bin/env python3
"""A9 SYSTEM REQUIREMENT-VERIFICATION MATRIX (follow-on fo_a9_6_rvm, trigger T_A9_6_RVM; owner directive A9.6 sec. 15).

One system-level table covering every top-level RFP requirement recorded in the repository, plus the owner-given
internal allocations the directive names (1.35 kW, 34 / 36 kg) and the derived thermal-closure requirement, for both A9
configurations (hall_icp_neutralizer = primary investigation hypothesis; hall_c1_reference = control / fallback).

Deterministic, standard library only, no Julia, no network, well under a second.

What it does
  * verifies the sha256 of every pinned IMMUTABLE input (owner decisions, 147 answers, owner-question state v3,
    docs/EVIDENCE.md, the P5-N2 v1 validation release, historical RTM / lane-24 / web-track R2 records) and refuses to
    run on any mismatch (CLAUDE.md rule 3);
  * reads the merged A9 / A9.6 packages by path and checks their identity (id / schema) - they are mutable and are
    never pinned; if one changes, `--check` fails and the matrix must be rebuilt;
  * copies requirement quotes, owner-answer texts and decision texts FROM the pinned inputs (never typed) and checks
    every cited value token against the verbatim text; checks that every cited artifact id resolves in its package;
  * probes the packages for their current evidence state (Hall credible set, power ledger, mass roll-ups, Xe
    accounting, P3 thermal, P4 materials) and fails closed whenever a probed state is not one the rules were written
    for (e.g. a non-empty credible set, a power gate verdict other than NOT_EVALUABLE, a measured slot load);
  * assigns every status with rvm_rules.assign_status (explicit ordered rules; exactly six states);
  * writes rvm_a9_v1.json and RVM_A9.md (generated from the JSON).

What it is not: a compliance claim, a performance prediction (no Hall closure, screening candidate, 0-D model or
withdrawn number is used), an architecture selection or winner, a thermal / RF-rating / anode / ICP-capacity PASS,
an answer to any open owner question, or a freeze of any RFP interpretation (the official RFP is not in the repository;
owner rows 1-3). Not wired into archengine (goldens do not move).

Build order (data dependency; consolidated verification S-03): P4, XE, P1, P2, P3, MP, RFQ, RVM, owner-question
state v4, M16 v4. State v4 reads rvm_a9_v1.json (ids of RVM-ID-10 / RVM-ID-11, RVMQ-01, the lane-24 rows), the RVM
reads only the immutable state v3 snapshot, and M16 v4 reads both - so after any RVM change rebuild state v4 and
then M16 v4 (--check on each catches a stale downstream output).

    python docs/requirements/rvm_a9/build_rvm_a9.py          # (re)write outputs
    python docs/requirements/rvm_a9/build_rvm_a9.py --check  # exit 1 unless the outputs are reproduced byte-for-byte
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LANE_REL = "docs/requirements/rvm_a9"
sys.path.insert(0, str(HERE))
import a9_16_rvm as A16  # noqa: E402  (A9.16 step 1 owner-decision application, integration lane)
import rfp_rebase as RB  # noqa: E402  (AG-15 re-base on the registered official RFP, A9.16 step 3)
import a9_19_rvm as A19  # noqa: E402  (A9.19 / A9.20 owner decisions: flight architecture, Xe role, C1 ground-only)
JSON_NAME = "rvm_a9_v1.json"
MD_NAME = "RVM_A9.md"
TEST_REL = "tests/test_rvm_a9.py"
BASE_COMMIT = "3acdbcc165b6205082e3aa04be76d79bba094d0d"
DATE = "2026-09-30"
LANE = "fo_a9_6_rvm"
TRIGGER = "T_A9_6_RVM"
CONFIGS = ("hall_icp_neutralizer", "hall_c1_reference")
FREEZE_POINTS = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
VERIFICATION_METHODS = ("test", "analysis", "inspection", "demonstration")
ITEM_EVIDENCE_CLASSES = ("requirement-as-recorded", "owner-stated", "owner-allocation")

_spec = importlib.util.spec_from_file_location("rvm_rules", str(HERE / "rvm_rules.py"))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

# ------------------------------------------------------------------------------------------------ pinned (immutable)
PINS = {
    "A9": ("docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json",
           "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "governing owner decision A9"),
    "ANS": ("docs/decisions/OD_2026_09_29_owner_answers_147.json",
            "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "147 owner answers (machine-readable)"),
    "PACK": ("docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md",
             "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976", "147 owner answers (verbatim pack)"),
    "A91": ("docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json",
            "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4", "owner decisions A9.1"),
    "A92": ("docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json",
            "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03", "owner decisions A9.2"),
    "A93": ("docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json",
            "81c69b200b9ce51f8aa745636d7aa4dbbddc39005b064235841722ebfdedad1b", "owner decisions A9.3"),
    "A94": ("docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json",
            "b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d", "owner decisions A9.4"),
    "A95": ("docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json",
            "c9e101f2c409c2d28ad256818c22f13ee801bc532d7e4ef470f375d7bb1fe1d3", "owner decisions A9.5"),
    "A96": ("docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json",
            "d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327", "owner directive A9.6"),
    "A96_MD": ("docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md",
               "c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634", "owner directive A9.6 (verbatim)"),
    "OQ3": ("docs/budgets/owner_decisions/owner_questions_state_v3.json",
            "1c2e74340852dfe8c58b1804c3cfda2bfbfb3bfb5d631aaebd715cf716b76af2", "owner question state v3"),
    "EVID": ("docs/EVIDENCE.md", "a2950352141890c12ad33e66766cd003215c807cb29203d21df090349ab90b61",
             "evidence rules (CLAUDE.md rule 10)"),
    "VREL": ("hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json",
             "0a57a397883141be20196853b7d722404dc3cb20c72fba666121fd43507dc97c",
             "P5-N2 v1 vacuum validation release (permanent INCONCLUSIVE; never rewritten)"),
    "R2": ("docs/procurement/web_track_v1/threads/R2_rfp.json",
           "b2796ff856f041b22c623b87e403b75748e2c25e818b9e8149e5c766f22c4b8c",
           "web track R2: RFP requirement interpretation (secondary sources; RFP not obtained)"),
    "RTM": ("docs/traceability/rtm_v1.json", "21dec718458eb0d50caa2c779ecd2ea6c663cba61d5f1324242d69839a64bc55",
            "historical requirement traceability matrix v1 (hall_only / rf_hall / ecr_hall)"),
    "HGM": ("docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json",
            "7d77d2831214f3f3d96c8254ea43643ada15e7d1ce0685dec86a65eb79a8f65f",
            "historical lane-24 hard-gate matrix v1 (RFP records R1-R7, OD1-OD14)"),
}
for _k in ("A9.12", "A9.13", "A9.14", "A9.15"):
    PINS["A" + _k[1:].replace(".", "")] = (
        A16.L.LOADED[_k]["json"], A16.L.LOADED[_k]["json_sha256"], f"owner decisions {_k} (applied: A9.16 step 1)")
    PINS["A" + _k[1:].replace(".", "") + "_MD"] = (A16.L.LOADED[_k]["md"], A16.L.LOADED[_k]["md_sha256"],
                                                   f"owner decisions {_k} (verbatim; governs)")
for _k in ("A9.19", "A9.20"):
    _d = A19.DECISIONS[_k]
    PINS["A" + _k[1:].replace(".", "")] = (_d["json"], _d["json_sha256"], f"owner decision {_k} (applied: a9_19_rvm)")
    PINS["A" + _k[1:].replace(".", "") + "_MD"] = (_d["md"], _d["md_sha256"], f"owner decision {_k} (verbatim; governs)")
HISTORICAL_KEYS = ("RTM", "HGM", "R2")
HISTORICAL_EXTRA = {
    "docs/traceability/RTM.md": "ce5b608a5079a86d1b2096f222266f558fab2ebdabc1aa8dfef3153076faa802",
    "docs/traceability/build_rtm.py": "1f29e4ee85722c060021e4f6e0334135e15e0f719c0fc647a29b22653907667b",
    "docs/architecture_comparison/hard_gates/hard_gate_status_v1.json":
        "2c82b3277067b22c85eabd25539b18101f429e6d34ee698d2f5d6e183aa44527",
}
NEVER_PINNED = ("docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                "docs/orchestration/fired_triggers.jsonl", "docs/orchestration/trigger_ledger_v2.jsonl",
                "docs/orchestration/runtime_state.json")

# ------------------------------------------------------------------------------------------------ read, never pinned
# (key: path, identity field, expected identity value, role)
REFS = {
    "BUS": ("docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json", "id",
            "bus_power_boundary_a9_v1", "A9-02 bus-power boundary (1 ms gate, 1.35 kW allocation)"),
    "PRE": ("docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json", "id",
            "A9_01_hall_icp_prereg_framework_v1", "A9-01 Hall->ICP pre-registration framework (stages, DQ-HI-*)"),
    "VI": ("docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json", "schema",
           "hall_icp_validation_inputs_v1", "A9-05 validation-input list (VI-*)"),
    "ICD": ("schemas/interfaces/icp_neutralizer_icd_v1.json", "id", "icp_neutralizer_icd_v1",
            "A9-03 ICP neutralizer ICD (ICP-*)"),
    "EVI": ("docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json", "schema", "icp_neutralizer_evidence_v1",
            "A9 ICP neutralizer published-analog evidence (Takahashi et al. 2024)"),
    "P1": ("docs/experiments/hall_icp/p1_icp_bench/p1_icp_bench_v1.json", "id", "p1_icp_bench_v1",
           "P1 ICP bench workflow (ICP-45 capacity, discharge-OFF)"),
    "P2": ("docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json", "id", "p2_impedance_prep_v1",
           "P2 impedance-map framework"),
    "P3": ("docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json", "id", "p3_coupled_thermal_v2",
           "P3 coupled-thermal framework"),
    "P4": ("docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json", "id", "p4_anode_materials_v1",
           "P4 anode / collector materials framework"),
    "MP": ("docs/budgets/mass_power_a9_v2/mass_power_a9_v2.json", "id", "fo_a9_6_mass_power_integration_v2",
           "A9.6 mass + power integration v2"),
    "XE": ("docs/budgets/xe_accounting_a9_v2/xe_accounting_a9_v2.json", "id", "xe_accounting_a9_v2",
           "A9.6 Xe accounting v2"),
    "MP3": ("docs/budgets/mass_power_a9_v3/mass_power_a9_v3.json", "id", "mass_power_a9_v3",
            "mass + power v3 (A9.16 step 1; to be refreshed for A9.19 / A9.20 by the budgets lane)"),
    "XE3": ("docs/budgets/xe_accounting_a9_v3/xe_accounting_a9_v3.json", "id", "xe_accounting_a9_v3",
            "Xe accounting v3 (A9.16 step 1; to be refreshed for A9.19 / A9.20 by the budgets lane)"),
    "AOL": ("docs/experiments/lifetime_ao/ao_lifetime_register_v5.json", "schema", "ao_lifetime_register_v5",
            "AO / lifetime register v5"),
    "ENS": ("hallthruster_bridge/ensemble/transport_ensemble_v0.json", "schema", "transport_ensemble_v0",
            "Hall transport ensemble (credible set)"),
    "FSC": ("docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json", "schema",
            "feed_state_closure_v1", "feed-state closure (delivered feed vs altitude)"),
    "OO2": ("docs/chemistry/o_o2/v0/channel_status_v0.json", "id", "o_o2_channel_status_v0",
            "O / O2 chemistry v0 channel status"),
    "RFQ2": ("docs/procurement/rfq_a9_v2/rfq_a9_v2.json", "id", "RFQ_A9_V2", "RFQ packages v2 (quotation only)"),
    "RFQ3": ("docs/procurement/rfq_a9_v3/rfq_a9_v3.json", "id", "RFQ_A9_V3", "RFQ packages v3 (quotation only)"),
    "M16": ("docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json", "id", "subsystem_maturity_v3",
            "M16 subsystem maturity v3"),
}


class BuildError(RuntimeError):
    pass


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_pins():
    data = {}
    for key, (rel, sha, _role) in PINS.items():
        p = REPO / rel
        if not p.exists():
            raise BuildError(f"pinned input missing: {rel}")
        got = sha256_file(p)
        if got != sha:
            raise BuildError(f"pinned input changed: {rel} sha256 {got} != {sha}")
        data[key] = json.loads(p.read_text(encoding="utf-8")) if rel.endswith(".json") else p.read_text(
            encoding="utf-8")
    for rel, sha in HISTORICAL_EXTRA.items():
        got = sha256_file(REPO / rel)
        if got != sha:
            raise BuildError(f"historical input changed: {rel} sha256 {got} != {sha}")
    return data


def load_refs():
    data = {}
    for key, (rel, field, expect, _role) in REFS.items():
        if rel in NEVER_PINNED:
            raise BuildError(f"governance file may not be read as an input: {rel}")
        p = REPO / rel
        if not p.exists():
            raise BuildError(f"referenced package missing: {rel}")
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get(field) != expect:
            raise BuildError(f"referenced package identity changed: {rel} {field}={d.get(field)!r} != {expect!r}")
        data[key] = d
    return data


def find_by(obj, ident, key="id"):
    if isinstance(obj, dict):
        if obj.get(key) == ident:
            return obj
        for v in obj.values():
            r = find_by(v, ident, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_by(v, ident, key)
            if r is not None:
                return r
    return None


# ------------------------------------------------------------------------------------------------ source helpers
class Ctx:
    def __init__(self, pins, refs):
        self.p = pins
        self.r = refs
        self.answers = {a["row"]: a for a in pins["ANS"]["answers"]}
        try:
            self.reg = RB.load_registration()   # official RFP registration (AG-15): identity + clause hash checked
        except RB.RebaseError as e:
            raise BuildError(str(e)) from e

    def answer(self, row, token=None):
        a = self.answers.get(row)
        if a is None:
            raise BuildError(f"owner answer row {row} missing")
        v = a["owner_answer_verbatim"]
        if token is not None and token not in v:
            raise BuildError(f"token {token!r} not in owner answer row {row}")
        return {"kind": "owner_answer", "path": PINS["ANS"][0], "row": row, "covers_ids": a["covers_ids"],
                "answer_sha256": sha256_text(v), "verbatim": v}

    def r2(self, topic, token=None):
        for c in self.p["R2"]["clauses"]:
            if c["topic"] == topic:
                q = c["quote"]
                if token is not None and (q is None or token not in q):
                    raise BuildError(f"token {token!r} not in R2 clause {topic!r}")
                return {"kind": "rfp_secondary_record", "path": PINS["R2"][0], "locator": f"clauses[topic={topic!r}]",
                        "quote": q, "source_locator": c["locator"], "ambiguous": c["ambiguous"],
                        "note": "secondary transcription (news); the official RFP was not obtained (R2 rfp_obtained "
                                "false); verify against RFP document"}
        raise BuildError(f"R2 clause {topic!r} missing")

    def hgm(self, rid, token=None):
        for r in self.p["HGM"]["rfp"]["recorded_in"]:
            if r["id"] == rid:
                t = r["text_as_recorded"]
                if token is not None and token not in t:
                    raise BuildError(f"token {token!r} not in HGM record {rid}")
                return {"kind": "repo_record", "path": PINS["HGM"][0], "locator": f"rfp.recorded_in[id={rid}]",
                        "ref": r["ref"], "text_as_recorded": t, "note": "in-repo transcription; verify against RFP"}
        raise BuildError(f"HGM record {rid} missing")

    def decision(self, key, dec_id, token=None):
        d = self.p[key]["decisions"]
        if dec_id not in d:
            raise BuildError(f"decision {dec_id} missing in {key}")
        text = json.dumps(d[dec_id], ensure_ascii=False, sort_keys=True)
        if token is not None and token not in text:
            raise BuildError(f"token {token!r} not in {key} {dec_id}")
        return {"kind": "owner_decision", "path": PINS[key][0], "decision_id": self.p[key]["id"], "key": dec_id,
                "sha256_of_file": PINS[key][1], "text": d[dec_id]}

    def a9(self, field, token=None):
        v = self.p["A9"][field]
        text = json.dumps(v, ensure_ascii=False)
        if token is not None and token not in text:
            raise BuildError(f"token {token!r} not in A9 {field}")
        return {"kind": "owner_decision", "path": PINS["A9"][0], "decision_id": self.p["A9"]["id"], "key": field,
                "sha256_of_file": PINS["A9"][1], "text": v}

    def rfp(self, cid, token=None):
        try:
            return RB.clause_record(self.reg, cid, token)
        except RB.RebaseError as e:
            raise BuildError(str(e)) from e

    def rtm(self, rid):
        r = find_by(self.p["RTM"]["requirements"], rid)
        if r is None:
            raise BuildError(f"RTM requirement {rid} missing")
        return rid

    def resolve(self, pkg, ident, key="id"):
        d = self.r[pkg]
        if ident == "@doc":
            return d
        o = find_by(d, ident, key)
        if o is None:
            raise BuildError(f"{pkg}: {key}={ident!r} not found in {REFS[pkg][0]}")
        return o


def _art(path, ident, role, kind, state, **kw):
    a = {"path": path, "id": ident, "role": role, "kind": kind, "evidence_state": state,
         "evaluated": False, "verified": False, "measured": False, "synthetic": False, "in_domain": None,
         "meets": None, "coverage_complete": False, "evidenced_terms": 0, "numerical_failure": False,
         "lower_bound_verified": False, "exceeds_limit_every_reading": None}
    for k, v in kw.items():
        if k not in a and k not in ("detail",):
            raise BuildError(f"unknown artifact field {k}")
        a[k] = v
    R.validate_artifact({k: v for k, v in a.items() if k != "detail"})
    return a


def plan(ctx, pkg, ident, role="DETERMINING", key="id", why=""):
    o = ctx.resolve(pkg, ident, key)
    d = ctx.r[pkg]
    pkg_status = d.get("status", "-")
    obj_status = o.get("status") if isinstance(o, dict) and ident != "@doc" else None
    name = (o.get("name") or o.get("title") or "") if isinstance(o, dict) and ident != "@doc" else d.get(
        "title", REFS[pkg][3])
    state = f"PLANNED / FRAMEWORK ONLY - nothing measured; package status {pkg_status}"
    if obj_status:
        state += f"; item status {obj_status}"
    shown = REFS[pkg][2] if ident == "@doc" else f"{REFS[pkg][2]}:{ident}"
    kind = "PROCUREMENT" if pkg in ("RFQ2", "RFQ3") else "PLAN_OR_FRAMEWORK"
    a = _art(REFS[pkg][0], shown, role, kind, state)
    a["detail"] = {"name": name, "why": why}
    return a


def absent(ctx, cid, would_verify, suffix=""):
    """No verification artifact exists in the repository for this RFP requirement: name what would verify it (an
    explicit absence record, never a placeholder value; evaluates nothing -> NOT_EVALUATED)."""
    c = ctx.rfp(cid)
    a = _art(RB.REG_REL, f"rfp_registration_v1:{cid}{suffix}:NO_VERIFICATION_ARTIFACT", "DETERMINING",
             "VERIFICATION_ARTIFACT_ABSENT",
             "NO VERIFICATION ARTIFACT EXISTS IN THE REPOSITORY - would be verified by: " + would_verify)
    a["detail"] = {"name": f"{cid} ({c['section']}, p. {c['page']})", "why": would_verify}
    return a


def analog_takahashi(ctx):
    d = ctx.r["EVI"]
    anchor = d["anchor"]
    a = _art(REFS["EVI"][0], "icp_neutralizer_evidence_v1:anchor", "CONTEXT", "PUBLISHED_ANALOG",
             "PUBLISHED ANALOG ONLY (other hardware, Ar): topology precedent, never Vyovrinda performance",
             in_domain=False)
    a["detail"] = {"anchor": json.dumps(anchor, ensure_ascii=False, sort_keys=True)[:400]}
    return a


# ------------------------------------------------------------------------------------------------ probes (fail closed)
def probe_hall_analysis(ctx):
    ens = ctx.r["ENS"]
    vrel = ctx.p["VREL"]
    if ens["members"] != []:
        raise BuildError("Hall credible set is no longer empty: the RVM analysis rules must be reviewed before rebuild")
    dec = vrel["decision"]
    if dec["promotable"] != [] or vrel["admission_records"] != []:
        raise BuildError("P5-N2 v1 release shows a promotable / admitted closure: review the RVM rules")
    state = (f"UNAVAILABLE - credible Hall transport set EMPTY (transport_ensemble_v0 members = []; "
             f"{ens['admission_rule_status'][:60]}...); P5-N2 v1 {vrel['campaign']}: promotable [], inconclusive "
             f"{len(dec['inconclusive'])} of {len(dec['inconclusive']) + len(dec['failed_validation'])} candidates "
             f"(permanent INCONCLUSIVE); all absolute 0-D Hall results withdrawn - no thrust / power / life analysis "
             f"evidence exists")
    a = _art(REFS["ENS"][0], "transport_ensemble_v0:members", "DETERMINING", "VALIDATED_ANALYSIS", state)
    a["detail"] = {"validation_release": PINS["VREL"][0], "inconclusive": dec["inconclusive"]}
    return a


def probe_power(ctx, cfg):
    mp = ctx.r["MP"]
    pc = mp["power"]["configurations"][cfg]
    gate = pc["rfp_gate_1ms"]
    if gate["verdict"] != "NOT_EVALUABLE" or any(r["verdict"] != "NOT_EVALUABLE" for r in gate["rows"]):
        raise BuildError(f"power gate verdict changed for {cfg}: review the RVM power rules")
    measured = [s["slot"] for s in pc["slots"] if s.get("MEASURED_W") is not None]
    if measured:
        raise BuildError(f"measured slot loads appeared for {cfg} ({measured}): review the RVM power rules")
    cbe = [s["slot"] for s in pc["slots"] if s.get("CBE_W") is not None]
    st = pc["phases"]["steady"]
    state = (f"LEDGER EVALUATED, NOT_EVALUABLE - steady ledger {st['ledger_status']}, {st['tbd_count']} TBD, "
             f"P_bus lower bound {st['P_bus_lower_bound_W']} W; P_bus,1ms,max gate NOT_EVALUABLE in all "
             f"{len(gate['rows'])} registered steps; slots with a CBE {len(cbe)}, measured 0")
    a = _art(REFS["MP"][0], f"{mp['id']}:power.configurations.{cfg}.rfp_gate_1ms", "DETERMINING",
             "BUDGET_EVALUATION", state, evaluated=True, in_domain=True, evidenced_terms=len(cbe))
    a["detail"] = {"steps": [f"{r['label']}={r['status']}" for r in gate["rows"]]}
    return a


def probe_alloc(ctx, cfg):
    mp = ctx.r["MP"]
    st = mp["power"]["configurations"][cfg]["phases"]["steady"]
    v = st["design_allocation_1350W"]
    if v != "NOT_EVALUABLE":
        raise BuildError(f"1350 W allocation check changed for {cfg}: review the RVM rules")
    icp = st.get("icp_available_check")
    extra = ""
    if cfg == "hall_icp_neutralizer":
        if icp is None or icp["verdict"] != "NOT_EVALUABLE":
            raise BuildError("ICP available-power check changed: review the RVM rules")
        extra = f"; {icp['relation']}: NOT_EVALUABLE (upper bound {icp['P_ICP_available_upper_bound_W']} W)"
    cbe = [s["slot"] for s in mp["power"]["configurations"][cfg]["slots"] if s.get("CBE_W") is not None]
    state = f"ALLOCATION CHECK EVALUATED, NOT_EVALUABLE - {st['tbd_count']} TBD loads{extra}"
    return _art(REFS["MP"][0], f"{mp['id']}:power.configurations.{cfg}.phases.steady.design_allocation_1350W",
                "DETERMINING", "BUDGET_EVALUATION", state, evaluated=True, in_domain=True, evidenced_terms=len(cbe))


def probe_startup(ctx, cfg):
    mp = ctx.r["MP"]
    su = mp["power"]["configurations"][cfg]["phases"]["startup"]
    if su["violations"]:
        raise BuildError(f"start-up sequence violations appeared for {cfg}: review the RVM rules")
    state = (f"SEQUENCE RULES {su['sequence_status']} ({su['not_evaluable_rules']} rules not evaluable; template "
             f"{su['template']})")
    return _art(REFS["MP"][0], f"{mp['id']}:power.configurations.{cfg}.phases.startup", "SUPPORTING",
                "BUDGET_EVALUATION", state, evaluated=True, in_domain=True, evidenced_terms=0)


MASS_READINGS_ADMISSIBLE = ("MQ01_MEV_LEVEL", "MQ01_CBE_LEVEL")


def mass_analysis(ctx, cfg, reference):
    """Per-reading mass evaluation (see the FAIL rule): floor-only sums vs the reference, plus a copy of the mass
    package's mixed allocation + floor closure states (informational: allocations are not evidence)."""
    mp = ctx.r["MP"]
    ev_col = mp["value_columns"]["EVIDENCE_FLOOR"]
    if "not a physical lower bound" not in ev_col:
        raise BuildError("mass package EVIDENCE_FLOOR definition changed: review lower_bound_verified")
    lines = mp["lines"][cfg]
    floors = [(ln["line"], ln["evidence_floor_kg"]) for ln in lines if ln["evidence_floor_kg"] is not None]
    if not floors:
        raise BuildError(f"no evidence floors for {cfg}")
    xa9q07_variants = [("XA9Q07_XE_BOOKED", None)]
    if cfg == "hall_icp_neutralizer":
        xa9q07_variants.append(("XA9Q07_NO_XE_IN_ICP_FLIGHT", "AL-08"))
    readings = []
    for mq in MASS_READINGS_ADMISSIBLE:
        for xr in ("LOADED_XA9Q01", "USABLE_MQ09"):
            for case in (2.0, 5.0, 10.0):
                for xv, drop in xa9q07_variants:
                    s = sum(v for ln, v in floors if ln != drop)
                    readings.append({"reading": f"{mq}|{xr}|xe_case={case}|{xv}", "floor_only_kg": round(s, 6)})
    limit = {"HARD_40_WET": 40.0, "INTERNAL_34": 34.0, "INTERNAL_36": 36.0}[reference]
    strict = reference == "HARD_40_WET"
    chk = R.floor_fail_check(readings, limit, strict)
    mixed = []
    for ru in mp["rollups"]:
        if ru["configuration"] != cfg or ru["reading"] not in MASS_READINGS_ADMISSIBLE:
            continue
        for w in ru["wet"]:
            if w["reference"] == reference:
                mixed.append({"reading": f"{ru['reading']}|{ru['basis']}|{w['xe_case_reading']}|"
                                         f"xe_case={w['xe_case_kg']}", "wet_known_kg": w["wet_known_kg"],
                              "state": w["state"]})
    if not mixed:
        raise BuildError(f"no mass roll-ups for {cfg} / {reference}")
    if any(m["state"] == "CLOSES" for m in mixed):
        raise BuildError("a mass roll-up CLOSES: review the RVM rules (a budget closure is never a PASS)")
    return {"reference": reference, "limit_kg": limit, "strict": strict,
            "evidence_floors": [{"line": ln, "floor_kg": v} for ln, v in floors],
            "evidence_floor_definition": ev_col, "lower_bound_verified": False,
            "floor_only_readings": readings, "floor_fail_check": chk,
            "mixed_basis_states": mixed,
            "mixed_basis_counts": {s: sum(1 for m in mixed if m["state"] == s)
                                   for s in ("DOES_NOT_CLOSE", "NOT_EVALUABLE", "CLOSES")},
            "fail_rule": "FAIL only if a VERIFIED lower-bound floor exceeds the limit under EVERY admissible open "
                         "reading (MQ-01 A/B, XA9Q-01/MQ-09, the 2/5/10 kg Xe design cases, XA9Q-07); the mixed "
                         "allocation + floor states are informational because owner allocations are not evidence "
                         "and are the MQ-10 closure lever"}


def probe_mass(ctx, cfg, references):
    mp = ctx.r["MP"]
    analyses = [mass_analysis(ctx, cfg, ref) for ref in references]
    n_floor = len(analyses[0]["evidence_floors"])
    exceeds_all = all(a["floor_fail_check"]["exceeds_every_reading"] for a in analyses)
    parts = []
    for an in analyses:
        c = an["floor_fail_check"]
        mc = an["mixed_basis_counts"]
        parts.append(f"{an['reference']}: floor-only {c['min_floor_kg']}-{c['max_floor_kg']} kg vs "
                     f"{'<' if an['strict'] else '<='} {an['limit_kg']} kg, exceeding in {c['n_exceeding']} of "
                     f"{c['n_readings']} readings; mixed allocation+floor basis DOES_NOT_CLOSE "
                     f"{mc['DOES_NOT_CLOSE']} / NOT_EVALUABLE {mc['NOT_EVALUABLE']}")
    n_exc = sum(a["floor_fail_check"]["n_exceeding"] for a in analyses)
    n_all = sum(a["floor_fail_check"]["n_readings"] for a in analyses)
    verdict = ("FAIL not admissible: (a) floor-only sums exceed the limit in "
               f"{n_exc} of {n_all} admissible readings (FAIL needs all), and (b) the floors are not verified lower "
               "bounds; per-reading results reported, status INCOMPLETE_EVIDENCE")
    state = ("BUDGET EVALUATED, INCONCLUSIVE - no CBE and no measured mass; evidence floors are analog planning "
             "values declared 'not a physical lower bound' by the mass package; " + "; ".join(parts) + "; " + verdict)
    a = _art(REFS["MP"][0], f"{mp['id']}:rollups[{cfg}]", "DETERMINING", "BUDGET_EVALUATION", state,
             evaluated=True, in_domain=True, evidenced_terms=n_floor, lower_bound_verified=False,
             exceeds_limit_every_reading=exceeds_all)
    a["detail"] = {"analyses": analyses}
    return a


def probe_xe(ctx, cfg):
    xe = ctx.r["XE"]
    scen = {"hall_icp_neutralizer": ("S1-FL-PRIMARY",), "hall_c1_reference": ("S2-FL-C1",)}[cfg]
    rows = []
    for e in xe["evaluations"]:
        if e["scenario"] in scen:
            rows.append(f"{e['scenario']} {json.dumps(e['reading'], sort_keys=True)}: {e['booking']['status']}")
    if not rows:
        raise BuildError(f"Xe accounting scenarios missing for {cfg}")
    state = "XE ACCOUNTING (supporting; never a capability demonstration): " + "; ".join(rows)
    return _art(REFS["XE"][0], f"{xe['id']}:evaluations[{'/'.join(scen)}]", "SUPPORTING", "BUDGET_EVALUATION",
                state, evaluated=True, in_domain=True, evidenced_terms=0)


def probe_p4(ctx):
    p4 = ctx.r["P4"]
    states = set(p4["candidate_screening_states"].values())
    if states != {"INCOMPLETE_EVIDENCE"}:
        raise BuildError(f"P4 screening states changed ({sorted(states)}): review the RVM AO rules")
    if set(p4["final_material_status"].values()) != {"OPEN"}:
        raise BuildError("P4 final material status changed: review the RVM AO rules")
    n = len(p4["property_records"])
    state = (f"FRAMEWORK EVALUATED - {len(p4['candidate_screening_states'])} application x candidate screens all "
             f"INCOMPLETE_EVIDENCE; final anode / collector material OPEN; {n} bulk property record(s) from open "
             f"datasheets; no AO / oxidation / sputter evidence on any candidate (P4 ID-10)")
    return _art(REFS["P4"][0], f"{p4['id']}:candidate_screening_states", "DETERMINING", "FRAMEWORK_EVALUATION",
                state, evaluated=True, in_domain=True, evidenced_terms=n)


P3_EVIDENCED_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "published analog")


def probe_p3(ctx, cfg):
    p3 = ctx.r["P3"]
    cs = p3["closure_statuses"]
    if cs["ICP_COUPLED_THERMAL"] != "UNRESOLVED" or cs["ANODE_THERMAL_CLOSURE"] != "UNRESOLVED":
        raise BuildError("P3 closure statuses changed: review the RVM thermal rules")
    fce = p3["fail_closed_evaluations"]
    terms = ("Q_Hall->ICP", "Q_collector", "Q_RF/match", "Q_plume", "coupled_network")
    for t in terms:
        if fce[t]["status"] not in ("INCOMPLETE_EVIDENCE", "NOT_EVALUATED", "OUT_OF_DOMAIN", "NUMERICAL_FAILURE"):
            raise BuildError(f"P3 evaluation {t} status {fce[t]['status']}: review the RVM thermal rules")
    # consolidated verification TH-05: evidenced_terms counts heat terms / the network actually EVALUATED on evidenced
    # inputs, never framework inputs (the analog / model-derived registry items are listed separately)
    n_inputs = sum(1 for it in p3["items"] if it.get("evidence_class") in P3_EVIDENCED_CLASSES)
    evaluated_terms = [t for t in terms if fce[t]["status"] not in ("INCOMPLETE_EVIDENCE", "NOT_EVALUATED")]
    n = len(evaluated_terms)
    numerical = any(fce[t]["status"] == "NUMERICAL_FAILURE" for t in terms)
    if cfg == "hall_icp_neutralizer":
        scope = ("ICP_COUPLED_THERMAL UNRESOLVED and ANODE_THERMAL_CLOSURE UNRESOLVED; heat terms " +
                 ", ".join(f"{t} {fce[t]['status']}" for t in terms))
    else:
        scope = ("ANODE_THERMAL_CLOSURE UNRESOLVED (shared H-1 anode; A9.2 anode_approach); the ICP heat terms do "
                 "not apply to this configuration; the H-1 network is only method-checked against H2-5 (no "
                 "temperatures reported)")
    state = (f"FRAMEWORK RUN, FAIL-CLOSED - {scope}; {n} heat term(s) / network evaluated on evidenced inputs "
             f"(every one refused as INCOMPLETE_EVIDENCE when 0); {n_inputs} analog / model-derived framework "
             f"input(s) exist but are not evaluated terms; never a thermal PASS (A9.2, A9.6)")
    return _art(REFS["P3"][0], f"{p3['id']}:fail_closed_evaluations", "DETERMINING", "FRAMEWORK_EVALUATION", state,
                evaluated=True, in_domain=True, evidenced_terms=n, numerical_failure=numerical)


def m16_state(ctx, row):
    r = find_by(ctx.r["M16"]["rows"], row, "row")
    if r is None:
        raise BuildError(f"M16 row {row} missing")
    return {"m16_row": row, "key": r["key"], "execution_state": r["a9_refresh"]["execution_state"]}


# ------------------------------------------------------------------------------------------------ open readings
DOWNSTREAM = "downstream consumer (merged; built later in the A9.6 order, not pinned to avoid a cycle): "
# The RVM is built BEFORE owner-question state v4 (A9.6 order: ... RFQ, RVM, state v4, M16 v4 - v4 reads the RVM ids,
# so a v4 pin here would be circular; consolidated verification S-01 / S-03 / TH-04). The RVM therefore pins the
# immutable v3 snapshot as the source of the question text and carries every open reading with the status the owner
# register gives it (TBD_OWNER; OD13 SUPERSEDED by owner row 3). Agreement with the CURRENT register (state v4) is
# checked downstream, after v4 is built, by M16 v4 (rvm_register_reconciliation) and tests/test_m16_v4.py.
CURRENT_REGISTER = "docs/budgets/owner_decisions/owner_questions_state_v4.json"
REGISTER_NOTE = ("question text from the pinned immutable v3 snapshot; current register " + CURRENT_REGISTER +
                 " (built after the RVM; agreement checked by M16 v4 rvm_register_reconciliation)")
# lane-24 decisions that an owner answer supersedes (same question answered; S-01): id -> (owner row, what it settles)
LANE24_SUPERSEDED_BY_OWNER = {
    "OD13": (3, "owner row 3 retains > 15,000 h firing as a provisional hard requirement until the official RFP "
                "confirms it; the remaining verification of the wording is the owner action of row 1 (RVM-ID-12), "
                "not an open question"),
}


def oq(ctx, ident):
    for r in ctx.p["OQ3"]["rows"]:
        if r["id"] == ident:
            if r["status"] != "OPEN":
                raise BuildError(f"owner question {ident} is {r['status']} in v3, not OPEN")
            return {"id": ident, "register": PINS["OQ3"][0], "v3_status": r["status"], "status": "TBD_OWNER",
                    "current_register": CURRENT_REGISTER, "question": r["question"],
                    "handling": "carried side by side as TBD_OWNER; never answered here (" + REGISTER_NOTE + ")"}
    raise BuildError(f"owner question {ident} not in owner_questions_state_v3")


def hgm_od(ctx, ident):
    for o in ctx.p["HGM"]["open_owner_decisions"]:
        if o["id"] == ident:
            base = {"id": ident, "register": PINS["HGM"][0], "current_register": CURRENT_REGISTER,
                    "question": o["topic"]}
            if ident in LANE24_SUPERSEDED_BY_OWNER:
                row, how = LANE24_SUPERSEDED_BY_OWNER[ident]
                ans = [a for a in ctx.p["ANS"]["answers"] if a["row"] == row]
                if len(ans) != 1:
                    raise BuildError(f"owner answer row {row} missing")
                base.update(status="SUPERSEDED", status_detail=f"SUPERSEDED (owner row {row}; register completion)",
                            superseded_by={"owner_row": row, "path": PINS["ANS"][0],
                                           "owner_answer_verbatim": ans[0]["owner_answer_verbatim"]},
                            handling="superseded by an owner answer to the same question: " + how + "; not an open "
                                     "question (" + REGISTER_NOTE + ")")
                return base
            base.update(status="TBD_OWNER",
                        status_detail="TBD_OWNER - open in the historical lane-24 matrix, not in "
                                      "owner_questions_state_v3; registered in the current register via RVM-ID-11",
                        handling="carried side by side as TBD_OWNER; never answered here (" + REGISTER_NOTE + ")")
            return base
    raise BuildError(f"lane-24 open owner decision {ident} missing")


RFP_BASIS = ("SECONDARY_RECORD_VERIFY_AGAINST_RFP - the official RFP is not in the repository (owner rows 1-2: obtain "
             "it, freeze no interpretation from secondary sources; web track R2 rfp_obtained = false)")


def check_rfp_not_obtained(ctx):
    if ctx.p["R2"]["rfp_obtained"] is not False:
        raise BuildError("R2 says the RFP was obtained: requirement bases must be re-derived")


def load_rows_module():
    spec = importlib.util.spec_from_file_location("rvm_a9_rows", str(HERE / "rvm_a9_rows.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def evaluate_rows(ctx, rows):
    out = []
    seen = set()
    for r in rows:
        if r["id"] in seen:
            raise BuildError(f"duplicate row {r['id']}")
        seen.add(r["id"])
        for m in r["verification_methods"]:
            if m not in VERIFICATION_METHODS:
                raise BuildError(f"{r['id']}: verification method {m!r} not allowed")
        if set(r["artifacts"]) != set(CONFIGS):
            raise BuildError(f"{r['id']}: artifacts must cover exactly {CONFIGS}")
        cells = {}
        for c in CONFIGS:
            arts = r["artifacts"][c]
            status, rule, reason = R.assign_status([{k: v for k, v in a.items() if k != "detail"} for a in arts],
                                                   r["requirement_frozen"])
            det = [a for a in arts if a["role"] == "DETERMINING"]
            cells[c] = {"status": status, "rule": rule, "reason": reason,
                        "current_evidence_state": " || ".join(a["evidence_state"] for a in det),
                        "artifacts": arts}
            if R.is_not_applicable_cell(arts):
                cells[c]["applicability_marker"] = R.NOT_APPLICABLE_KIND
                cells[c]["counts_as_compliance_evidence"] = False
        rr = {k: v for k, v in r.items() if k != "artifacts"}
        rr["m16_rows"] = [m16_state(ctx, n) for n in r["m16_rows"]]
        rr["configurations"] = cells
        out.append(rr)
    return out


# ------------------------------------------------------------------------------------------------ (a) items
def build_items(ctx):
    def it(iid, name, value, units, basis, src, ev, status, freeze, note=""):
        if ev not in ITEM_EVIDENCE_CLASSES:
            raise BuildError(f"{iid}: evidence class {ev}")
        if freeze not in FREEZE_POINTS:
            raise BuildError(f"{iid}: freeze point {freeze}")
        return {"id": iid, "name": name, "value": value, "units": units, "basis": basis, "source": src,
                "evidence_class": ev, "status": status, "freeze_point": freeze, "note": note}

    rec = "REQUIREMENT_AS_RECORDED (verify against the official RFP)"
    ow = "OWNER_GIVEN"
    items = [
        it("RVM-IT-01", "altitude band lower edge", 180, "km", "RFP as recorded",
           [ctx.r2("(d) Altitude", "180 km"), ctx.hgm("R1", "180–230 km")], "requirement-as-recorded", rec,
           "after-evidence", "freezes when the official RFP is obtained (row 1)"),
        it("RVM-IT-02", "altitude band upper edge", 230, "km", "RFP as recorded",
           [ctx.r2("(d) Altitude", "230 km"), ctx.hgm("R1", "180–230 km")], "requirement-as-recorded", rec,
           "after-evidence"),
        it("RVM-IT-03", "minimum sustained atmospheric thrust", 12, "mN", "owner reading of '12-25 mN' (row 4)",
           [ctx.answer(4, "≥12 mN")], "owner-stated", ow, "NOW"),
        it("RVM-IT-04", "demonstrated system thrust capability", 25, "mN", "owner reading (rows 4, 27)",
           [ctx.answer(4, "25 mN"), ctx.answer(27, "25 mN")], "owner-stated", ow, "NOW"),
        it("RVM-IT-05", "absolute full-system thrust-per-bus-power floor at the 25 mN point", 16.67, "mN/kW",
           "row 27", [ctx.answer(27, "16.67 mN/kW")], "owner-stated", ow, "NOW"),
        it("RVM-IT-06", "bus-power requirement (strict '<')", 1500, "W", "RFP as recorded; row 108",
           [ctx.r2("(d) Power", "1,500 W"), ctx.answer(108, "<1.5 kW")], "requirement-as-recorded", rec,
           "after-evidence"),
        it("RVM-IT-07", "averaging window of the gate quantity P_bus,1ms,max", 0.001, "s", "A9.1 OQ-A902-01",
           [ctx.decision("A91", "OQ-A902-01", "1 ms")], "owner-stated", ow + " (A9 engineering definition pending "
                                                                            "the RFP wording)", "NOW"),
        it("RVM-IT-08", "internal design allocation", 1350, "W", "row 109; A9.1 OQ-A902-03",
           [ctx.answer(109, "1.35 kW"), ctx.decision("A91", "OQ-A902-03", "1350")], "owner-allocation",
           "OWNER_ALLOCATION (not a gate)", "NOW"),
        it("RVM-IT-09", "wet mass limit incl. Xe + tank (strict '<')", 40, "kg", "RFP as recorded; row 5",
           [ctx.r2("(a) Mass", "40 kg"), ctx.answer(5, "INCLUDES Xe + tank")], "requirement-as-recorded", rec,
           "after-evidence"),
        it("RVM-IT-10", "internal wet design allocation (lower)", 34, "kg", "row 53",
           [ctx.answer(53, "34 kg")], "owner-allocation", "OWNER_ALLOCATION (carried with RVM-IT-11)", "NOW"),
        it("RVM-IT-11", "internal wet design allocation (upper)", 36, "kg", "row 53",
           [ctx.answer(53, "36 kg")], "owner-allocation", "OWNER_ALLOCATION (carried with RVM-IT-10)", "NOW"),
        it("RVM-IT-12", "internal development / system mass margin", 20, "%", "row 52",
           [ctx.answer(52, "20% internal")], "owner-stated", ow, "NOW"),
        it("RVM-IT-13", "mission-life engineering basis", 26280, "h", "row 3",
           [ctx.answer(3, "26,280 h")], "owner-stated", ow + " (engineering basis until the RFP is verified)",
           "after-evidence"),
        it("RVM-IT-14", "provisional firing-time requirement (strict '>')", 15000, "h", "row 3",
           [ctx.answer(3, ">15,000 h firing"), ctx.hgm("R1", "> 15,000 h firing")], "owner-stated",
           "PROVISIONAL_HARD_REQUIREMENT (row 3)", "after-evidence"),
        it("RVM-IT-15", "C1 ignition dwell cap per attempt (preliminary protocol)", 120, "s", "row 93",
           [ctx.answer(93, "120 s")], "owner-stated", ow + " (final bound frozen before score-bearing C1 testing)",
           "LOCK-2"),
        it("RVM-IT-16", "C1 ignition retries per start (preliminary protocol)", 2, "-", "row 93",
           [ctx.answer(93, "at most two retries")], "owner-stated",
           ow + "; Xe booking of 2 vs 3 dwells is OPEN (OQ-A907-01 / XA9Q-02)", "LOCK-2"),
        it("RVM-IT-17", "indigenous content, total", 75, "%", "RFP as recorded (secondary)",
           [ctx.r2("(d) Indigenous content", "75 percent")], "requirement-as-recorded", rec, "after-evidence"),
        it("RVM-IT-18", "thermal margin below validated continuous-use limits", 50, "K", "row 86",
           [ctx.answer(86, "≥50 K")], "owner-stated", ow, "NOW"),
        it("RVM-IT-19", "ICP-45 required electron current I_d,max,H1",
           "TBD - requires the registered maximum H-1 discharge current from measured / registered H-1 operation "
           "(A9.3 OQ-A907-02; not the 8.33 A stand ceiling)", "A", "A9.1 ICP-45; A9.3 OQ-A907-02",
           [ctx.decision("A93", "OQ-A907-02", "H1_REGISTERED_MAX")], "owner-stated", "TBD_AFTER_EVIDENCE",
           "after-evidence"),
        it("RVM-IT-20", "ICP-neutralizer lifetime / cycle requirement",
           "TBD_OWNER - OQ-VI-04 (row 46 requires one; none defined)", "h; cycles", "row 46",
           [ctx.answer(46, "RF-neutralizer lifetime/cycle requirement")], "owner-stated", "TBD_OWNER", "LOCK-1"),
    ]
    return items


# ------------------------------------------------------------------------------------------------ (b) interfaces
def build_interface_demands(ctx):
    def idd(iid, direction, counterpart, content, status, check=None):
        if check is not None:
            pkg, ident = check
            ctx.resolve(pkg, ident)
        return {"id": iid, "direction": direction, "counterpart": counterpart, "content": content, "status": status}

    return [
        idd("RVM-ID-01", "RVM <- mass/power v2", f"{REFS['MP'][0]} (MPV2-ID-11)",
            "mass rows: < 40 kg wet and 34 / 36 kg from the roll-ups (no CBE); power rows: < 1.5 kW and 1.35 kW from "
            "the A9 ledger (all loads TBD); consumed as RVM-04 / -05 / -06 / -07", "CONSUMED", ("MP", "MPV2-ID-11")),
        idd("RVM-ID-02", "RVM <- Xe accounting v2", f"{REFS['XE'][0]} (XV2-IF-09)",
            "Xe accounting states (REFUSED totals with TBD inputs) as SUPPORTING evidence of RVM-03 / -06 / -10; never "
            "a Xe-capability demonstration", "CONSUMED", ("XE", "XV2-IF-09")),
        idd("RVM-ID-03", "RVM <- P4", f"{REFS['P4'][0]} (ID-10)",
            "AO / material compatibility: INCOMPLETE_EVIDENCE for every candidate and application; consumed as RVM-16",
            "CONSUMED", ("P4", "ID-10")),
        idd("RVM-ID-04", "RVM <- P3", f"{REFS['P3'][0]} (fail_closed_evaluations)",
            "coupled / anode thermal closure states (UNRESOLVED); consumed as RVM-17", "CONSUMED"),
        idd("RVM-ID-05", "RVM <- P1", f"{REFS['P1'][0]} (P1-S7 / P1-S7H)",
            "ICP-45 discharge-OFF capacity records (signed I_ON - I_OFF, Kirchhoff admission) are the determining "
            "measurement of RVM-15 for hall_icp_neutralizer once they exist; none exist", "AWAITING_EVIDENCE",
            ("P1", "P1-S7")),
        idd("RVM-ID-06", "RVM <- A9-01 pre-registration", f"{REFS['PRE'][0]} (DQ-HI-*; HI-ABS, HI-CMP, HI-AO)",
            "score-bearing gate classifications per configuration (DQ-HI-TABS, -SUST, -PBUS, -PALLOC, -IGN, -ECAP, "
            "-VCPL) become the determining measurements of RVM-02..-05, -08, -14, -15", "AWAITING_EVIDENCE",
            ("PRE", "DQ-HI-TABS")),
        idd("RVM-ID-07", "RVM <- Hall transport ensemble", f"{REFS['ENS'][0]}",
            "an admitted member would enable VALIDATED_ANALYSIS artifacts (the builder refuses to run when the credible "
            "set becomes non-empty until the rules are reviewed)", "BLOCKED (credible set empty)"),
        idd("RVM-ID-08", "RVM -> M16 refresh", DOWNSTREAM + "docs/experiments/hall_icp/integration/m16_v4/ "
                                               "(fo_a9_6_m16_refresh; A9.6 sec. 16)",
            "requirement-status column per M16 row (m16_impact); no row READY / VERIFIED from this lane", "CONSUMED"),
        idd("RVM-ID-09", "RVM -> consolidated verification", "fo_a9_6_consolidated_verification (A9.6 sec. 18; the "
                                                             "campaign that reviews this package)",
            "rules R0-R7, probes and per-row artifacts for the structural / evidence review", "OFFERED"),
        idd("RVM-ID-10", "RVM -> owner-question state v4", DOWNSTREAM + CURRENT_REGISTER +
            " (fo_a9_6_decision_propagation)",
            "new question RVMQ-01", "CONSUMED"),
        idd("RVM-ID-11", "RVM -> owner-question state v4", DOWNSTREAM + CURRENT_REGISTER +
            " (fo_a9_6_decision_propagation)",
            "lane-24 open decisions carried by RVM rows but absent from owner_questions_state_v3: OD2, OD3, OD5, OD6, "
            "OD12, OD13, OD14 (registered in state v4: OD13 SUPERSEDED by owner row 3, the others TBD_OWNER; "
            "bookkeeping, no answer implied)", "CONSUMED"),
        idd("RVM-ID-12", "RVM <- official RFP", "owner rows 1-2 (legitimate owner / portal route)",
            "the canonical RFP PDF with sha256: every RVM row with requirement_frozen = false re-derives its basis",
            "AWAITING_OWNER_ACTION"),
    ]


# ------------------------------------------------------------------------------------------------ (c) owner answers
OWNER_ROWS_APPLIED = [
    (1, "no RFP interpretation frozen: every RFP-recorded row carries requirement_frozen = false"),
    (2, "RFP reference / bid date not frozen here"),
    (3, "RVM-12 (> 15,000 h provisional) and RVM-13 (>= 26,280 h basis)"),
    (4, "RVM-02 (>= 12 mN sustained atmospheric) and RVM-03 (25 mN capability; Xe not required, booked if used)"),
    (5, "RVM-06 wet reading incl. Xe + tank"),
    (6, "RVM-10 bounded functional Xe mode"),
    (24, "RVM-14 recorded start / restart quantities"),
    (26, "RVM-03 / RVM-10: Xe points labelled, never atmospheric evidence"),
    (27, "RVM-03 25 mN inside the same full boundary; 16.67 mN/kW floor"),
    (36, "RVM-08 Ar never counts toward DRDO atmospheric requirements"),
    (42, "RVM-10 PHASE_TOTAL_FLOW booking"),
    (46, "RVM-12 C1 15,000 h basis; ICP lifetime / cycle requirement TBD_OWNER (OQ-VI-04)"),
    (52, "RVM-06 20 % internal margin; 40 kg hard wet gate"),
    (53, "RVM-07 34 and 36 kg side by side"),
    (55, "RVM-19 limited redundancy carried beside the recorded no-SPF statement"),
    (86, "RVM-17 >= 50 K margin, 20 % heat-load margin"),
    (87, "RVM-17 no unsourced anode target"),
    (88, "RVM-15 C1 sized to the measured / derived current demand (CONTROL_FALLBACK)"),
    (93, "RVM-14 120 s dwell cap, two retries (preliminary)"),
    (94, "RVM-16 no graphite flight keeper for O / AO exposure"),
    (102, "RVM-09 delivered species state measured; O survival never assumed"),
    (103, "RVM-16 no silver in O / AO-wetted parts"),
    (106, "RVM-16 flight anode material open until coupon evidence"),
    (108, "RVM-04 spacecraft-DC boundary, steady and start-up"),
    (109, "RVM-05 internal ~1.35 kW allocation"),
    (110, "RVM-04 every active load in a bus slot"),
    (112, "RVM-14 sequenced start-up peaks"),
    (120, "RVM-02 S1a thrust-uncertainty acceptance test at 12 mN"),
    (132, "RVM-08 / -09 / -16 NO_ATOMIC_O; dedicated AO source"),
]
DECISIONS_APPLIED = [
    ("A91", "OQ-A902-01", "RVM-04 gate quantity P_bus,1ms,max; ledger alone never PASSes"),
    ("A91", "OQ-A902-03", "RVM-05 P_ICP,available relation; no fixed split"),
    ("A91", "OQ-A902-07", "RVM-05 1350 W active check, 1300 W context"),
    ("A91", "ICP-45", "RVM-15 ICP-45 entry condition"),
    ("A91", "HIQ-03", "RVM-10 Xe reference / health check"),
    ("A91", "HIQ-08", "RVM-08 Ar never in DRDO compliance claims"),
    ("A91", "SEQ-peaks", "RVM-14 one peak-class rise per start-up step"),
    ("A91", "A9-03-collector", "RVM-16 collector material via the O / AO coupon programme"),
    ("A92", "a9_10_statuses", "all rows: the ten A9.2 statuses are carried unchanged; none is turned into PASS"),
    ("A92", "anode_316L", "RVM-16 316L REJECTED_AS_CURRENT_BASELINE"),
    ("A92", "anode_approach", "RVM-17 ANODE_BASELINE OPEN"),
    ("A92", "icp_coupled_thermal", "RVM-17 ICP_COUPLED_THERMAL UNRESOLVED"),
    ("A93", "OQ-A907-02", "RVM-15 I_e,required = I_d,max,H1 (TBD); 8.33 A is the stand ceiling only"),
    ("A93", "OQ-VI-05", "RVM-14 Ar topology control engineering-only"),
    ("A93", "OQ-RFQ-06", "RVM-04 mains laboratory RF generator GROUND/FACILITY_ONLY"),
    ("A94", "P1Q-10", "RVM-15 capacity extraction form (discharge OFF)"),
    ("A94", "P1Q-13", "RVM-15 anode floating, body single-point metered ground"),
    ("A95", "P1Q-15", "RVM-15 Kirchhoff admission of capacity records"),
    ("A95", "P1Q-16", "RVM-15 signed I_e,cap = I_RFON - I_RFOFF"),
]


def build_owner_answers_applied(ctx):
    out = []
    for row, how in OWNER_ROWS_APPLIED:
        a = ctx.answer(row)
        out.append({"row": row, "covers_ids": a["covers_ids"], "answer_sha256": a["answer_sha256"],
                    "owner_answer_verbatim": a["verbatim"], "how_applied": how})
    return out


def build_decisions_applied(ctx):
    out = []
    for key, dec, how in DECISIONS_APPLIED:
        d = ctx.decision(key, dec)
        out.append({"decision_file": d["path"], "decision_id": d["decision_id"], "sha256": PINS[key][1],
                    "key": dec, "how_applied": how})
    a96 = ctx.p["A96"]["summary"]
    out.append({"decision_file": PINS["A96"][0], "decision_id": ctx.p["A96"]["id"], "sha256": PINS["A96"][1],
                "key": "summary.rvm_states / summary.fixed_statuses",
                "how_applied": "status vocabulary exactly " + ", ".join(a96["rvm_states"]) +
                               "; fixed statuses carried: " + json.dumps(a96["fixed_statuses"], sort_keys=True)})
    a9 = ctx.p["A9"]
    out.append({"decision_file": PINS["A9"][0], "decision_id": a9["id"], "sha256": PINS["A9"][1],
                "key": "requirement_discipline / evidence_sequence / control_fallback / status",
                "how_applied": f"status {a9['status']}; full-system gates; evidence order; C1 control / fallback"})
    return out


# ------------------------------------------------------------------------------------------------ (d) questions
def build_open_questions():
    return [{
        "id": "RVMQ-01",
        "question": "If the official RFP confirms 'no single-point failure in electronics' (recorded only in "
                    "abep_sim/ppu.py, R7), does the row-55 limited-redundancy policy (no duplicated thruster, ICP "
                    "neutralizer or full PPU at this stage) stand, or must RVM-19 be re-based on the RFP clause?",
        "why_new": "row 55 set the redundancy policy without reference to the R7 statement; the lane-24 OD12 "
                   "question only asks whether R7 becomes a gate. Genuine design choice (mass / power / FMEA); not "
                   "answerable from existing decisions",
        "admissible_readings": ["keep row 55 as is (R7 not an RFP clause or waived)",
                                "re-base on the RFP clause (redundant PPU / RF electronics; mass and power impact)"],
        "status": "TBD_OWNER", "freeze_point": "after-evidence",
        "needed_by": "when the official RFP is obtained (row 1), before Milestone C",
    }]


# ------------------------------------------------------------------------------------------------ (e) / (f)
def build_historical_reuse(ctx):
    out = []
    for key in HISTORICAL_KEYS:
        rel, sha, role = PINS[key]
        out.append({"path": rel, "sha256": sha, "role": role})
    for rel, sha in HISTORICAL_EXTRA.items():
        out.append({"path": rel, "sha256": sha, "role": "historical companion (read only)"})
    return {"artifacts": out,
            "reused": "requirement list and ids (RTM RFP-* / DER-*), RFP records R1-R7, lane-24 gate ids and open "
                      "decisions OD1-OD14, R2 secondary quotes (all copied by pointer, pinned by sha256)",
            "not_reused": "the RTM status vocabulary (modeled / partial / open / blocked_by_gate_3) and the historical "
                          "architectures hall_only / rf_hall / ecr_hall; the lane-24 verdicts (UNDETERMINED for those "
                          "architectures); the A9 configurations get their own statuses here",
            "treatment": "read only; never edited"}


def build_m16_impact(ctx, rows):
    touched = {}
    for r in rows:
        for m in r["m16_rows"]:
            touched.setdefault(m["m16_row"], {"m16_row": m["m16_row"], "key": m["key"],
                                              "execution_state_v3": m["execution_state"], "rvm_rows": []})
            touched[m["m16_row"]]["rvm_rows"].append(r["id"])
    out = []
    for k in sorted(touched):
        t = touched[k]
        t["state_change"] = ("none (requirement-status input to the M16 v4 refresh, fo_a9_6_m16_refresh - a downstream "
                             "consumer; no row READY/VERIFIED)")
        out.append(t)
    return out


# ------------------------------------------------------------------------------------------------ document
def build_doc():
    pins = load_pins()
    refs = load_refs()
    ctx = Ctx(pins, refs)
    rows_mod = load_rows_module()
    ns = types.SimpleNamespace(**globals())
    try:
        new_rows = A19.build_rows(ns, ctx)
    except A19.A919Error as e:
        raise BuildError(str(e)) from e
    rows = evaluate_rows(ctx, rows_mod.build_rows(ns, ctx) + new_rows)
    counts = {c: {s: sum(1 for r in rows if r["configurations"][c]["status"] == s) for s in R.STATUSES}
              for c in CONFIGS}
    a92 = pins["A92"]["decisions"]["a9_10_statuses"]
    doc = {
        "schema": "rvm_a9_v1",
        "id": "rvm_a9_v1",
        "title": "A9 system requirement-verification matrix (hall_icp_neutralizer / hall_c1_reference)",
        "lane": LANE, "trigger": TRIGGER, "directive": "A9.6 sec. 15 (implementation-first)",
        "status": "DRAFT_IMPLEMENTATION_FIRST_PENDING_CONSOLIDATED_VERIFICATION",
        "a9_status": pins["A9"]["status"],
        "date": DATE, "base_commit": BASE_COMMIT,
        "generated_by": f"{LANE_REL}/build_rvm_a9.py", "rules_module": f"{LANE_REL}/rvm_rules.py",
        "rows_module": f"{LANE_REL}/rvm_a9_rows.py", "companion_document": f"{LANE_REL}/{MD_NAME}",
        "test": TEST_REL,
        "regenerate": f"python {LANE_REL}/build_rvm_a9.py  (check: --check)",
        "configurations": {"hall_icp_neutralizer": "PRIMARY INVESTIGATION HYPOTHESIS (A9; A9.2 "
                                                   "INVESTIGATION_HYPOTHESIS)",
                           "hall_c1_reference": "CONTROL / FALLBACK (A9; A9.2 CONTROL_FALLBACK)"},
        "what_this_is_not": [
            "not a compliance claim: implementation completeness is never compliance; no row is PASS",
            "not a performance prediction: no Hall transport closure (credible set empty), screening candidate, "
            "abep_sim/plasma_devices.py or withdrawn v1.2-v1.6 number is used",
            "not an architecture selection or ranking; no winner",
            "not a thermal, RF-rating, anode or ICP-capacity PASS (A9.2 / A9.6 fixed statuses carried)",
            "not an answer to any open owner question and not a freeze of any RFP interpretation (rows 1-3)",
            "not wired into archengine; goldens unaffected",
        ],
        "status_vocabulary": list(R.STATUSES),
        "status_rules": R.RULES,
        "artifact_kinds": list(R.ARTIFACT_KINDS),
        "artifact_roles": list(R.ROLES),
        "verification_methods": list(VERIFICATION_METHODS),
        "evidence_rule": "PASS only with a DETERMINING artifact of kind MEASUREMENT that is measured, verified, "
                         "non-synthetic, in domain, meets and covers the requirement, and a frozen requirement basis; "
                         "FAIL only from such a measurement or from a VERIFIED lower-bound floor exceeding the limit "
                         "under every admissible open reading (docs/EVIDENCE.md; CLAUDE.md rules 6, 10)",
        "rfp_document_in_repository": False,
        "rfp_registered_in_repository": "BY_HASH_WITH_VERBATIM_CLAUSE_TRANSCRIPTION (" + RB.REG_REL + "; PDF kept in the "
                                        "controlled project evidence store, A9.17)",
        "hall_status": {"credible_set": "EMPTY", "p5_n2_v1": "INCONCLUSIVE (permanent)",
                        "absolute_0d_results": "WITHDRAWN"},
        "a9_2_statuses_carried": a92,
        "a9_6_fixed_statuses_carried": pins["A96"]["summary"]["fixed_statuses"],
        "pins": [{"key": k, "path": v[0], "sha256": v[1], "role": v[2]} for k, v in PINS.items()],
        "referenced_not_pinned": [{"key": k, "path": v[0], "identity": {v[1]: v[2]}, "role": v[3],
                                   "why": "mutable package: read at build time, identity checked, never pinned"}
                                  for k, v in REFS.items()],
        "never_pinned": list(NEVER_PINNED),
        "status_counts": counts,
        "rows": rows,
        "items": build_items(ctx),
        "interface_demands": build_interface_demands(ctx),
        "owner_answers_applied": build_owner_answers_applied(ctx),
        "decisions_applied": build_decisions_applied(ctx),
        "open_owner_questions": build_open_questions(),
        "historical_reuse": build_historical_reuse(ctx),
        "m16_impact": build_m16_impact(ctx, rows),
        "excluded_candidates": [
            {"id": "PRG-BID", "why": "programmatic (bid close date), not a system requirement"},
            {"id": "DER-NETDRAG", "why": "derived purpose of ABEP; docs/HISTORY.md records that the RFP does not state "
                                         "it; covered physically by RVM-01..-03"},
            {"id": "DER-HALL-CLOSURE", "why": "an enabler of analysis (probe_hall_analysis), not a system requirement"},
            {"id": "DER-MODEL-INTEGRITY", "why": "simulator integrity gates (CLAUDE.md rules 1-5), not a system "
                                                 "requirement"},
        ],
        "compliance": {
            "allowed_paths": [f"{LANE_REL}/**", TEST_REL, "docs/requirements/rfp_official/** (RVM mapping section only)",
                              "tests/test_rfp_registration_v1.py"],
            "no_hall_performance_source": True, "no_screening_candidate": True, "no_winner": True,
            "no_archengine_wiring": True, "pins_mutable_governance": False, "no_pass_row": True,
        },
    }
    doc = A16.apply(doc)
    try:
        doc = A19.apply(doc)
    except A19.A919Error as e:
        raise BuildError(str(e)) from e
    rebase = dict(RB.REBASE)
    rebase.update(A19.REBASE)
    try:
        RB.REBASE, saved = rebase, RB.REBASE
        try:
            doc = RB.apply(doc, ctx.reg, RFP_BASIS)
        finally:
            RB.REBASE = saved
    except RB.RebaseError as e:
        raise BuildError(str(e)) from e
    R.assert_status_vocabulary(doc)
    R.assert_no_pass_without_measurement(doc)
    for r in rows:
        for c in CONFIGS:
            if r["configurations"][c]["status"] == "PASS":
                raise BuildError(f"{r['id']}/{c}: PASS produced although no verified measurement exists in the repo")
    return doc


# ------------------------------------------------------------------------------------------------ markdown
def _cell_md(cell):
    if cell.get("applicability_marker"):
        return f"**{cell['applicability_marker']}** (never compliance evidence)"
    return f"**{cell['status']}** ({cell['rule']})"


def _esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def _short(s, n=160):
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + " ..."


def _limit(lim):
    if lim is None:
        return "no numeric threshold recorded"
    v = lim["value"]
    v = " / ".join(str(x) for x in v) if isinstance(v, list) else str(v)
    return f"{lim['quantity']} {lim['comparator']} {v} {lim['units']}"


def _origin(r):
    o = r.get("requirement_origin", "?")
    if o == "RFP_CLAUSE":
        return "RFP " + ", ".join(r["rfp_clauses"])
    rel = r.get("related_rfp_clauses") or []
    return o + (" (related " + ", ".join(rel) + ")" if rel else "")


def render_md(doc):
    L = []
    a = L.append
    a("# A9 system requirement-verification matrix (RVM)")
    a("")
    a(f"**Status: {doc['status']}.** Lane `{doc['lane']}` (trigger `{doc['trigger']}`, {doc['directive']}); A9 status "
      f"`{doc['a9_status']}`. Base commit `{doc['base_commit']}`. Generated from `{doc['generated_by']}` "
      f"(rules `{doc['rules_module']}`, rows `{doc['rows_module']}`); machine-readable `rvm_a9_v1.json`. "
      f"Do not edit by hand.")
    a("")
    a("## Read this first")
    a("")
    for w in doc["what_this_is_not"]:
        a(f"- {w}")
    rb = doc["rfp_rebase"]
    a(f"- The official RFP {rb['registration']['rfp_number']} is registered by hash (PDF sha256 "
      f"`{rb['registration']['pdf_sha256']}`, not committed; A9.17) with a verbatim clause transcription in "
      f"`{rb['registration']['path']}`. Every row cites the RFP clause(s) it derives from or is labelled "
      f"DERIVED_PROJECT_REQUIREMENT / OWNER_ALLOCATION (AG-15 re-base). RFP rows keep `requirement_frozen = false` "
      f"until the owner closes AG-15; the interpretation readings are recorded as discrepancies below.")
    a(f"- Hall: credible set {doc['hall_status']['credible_set']}; P5-N2 v1 {doc['hall_status']['p5_n2_v1']}; "
      f"0-D absolute results {doc['hall_status']['absolute_0d_results']} - no thrust, power or life analysis "
      f"evidence exists.")
    a(f"- Evidence rule: {doc['evidence_rule']}.")
    a("")
    a("## Status counts")
    a("")
    a("| status | " + " | ".join(CONFIGS) + " |")
    a("|---|" + "---|" * len(CONFIGS))
    for s in doc["status_vocabulary"]:
        a(f"| {s} | " + " | ".join(str(doc["status_counts"][c][s]) for c in CONFIGS) + " |")
    a("")
    a("## Matrix")
    a("")
    a("| id | requirement | origin / RFP clauses | limit | method | hall_icp_neutralizer | hall_c1_reference |")
    a("|---|---|---|---|---|---|---|")
    for r in doc["rows"]:
        a(f"| {r['id']} | {_esc(r['title'])} | {_origin(r)} | {_esc(_limit(r['limit']))} | "
          f"{', '.join(r['verification_methods'])} | "
          + " | ".join(_cell_md(r["configurations"][c]) for c in CONFIGS) + " |")
    a("")
    a("## Status rules (applied in this order by `rvm_rules.assign_status`)")
    a("")
    for k, v in doc["status_rules"].items():
        a(f"- `{k}`: {v}")
    a("")
    a("## Rows in detail")
    for r in doc["rows"]:
        a("")
        a(f"### {r['id']} - {r['title']}")
        a("")
        a(f"- Category: `{r['category']}`; key `{r['key']}`; origin {_origin(r)}")
        a(f"- Requirement: {r['requirement_text']}")
        a(f"- Limit: {_limit(r['limit'])}")
        a(f"- Basis: {r['requirement_basis']} (frozen: {r['requirement_frozen']})")
        a(f"- Verification: {', '.join(r['verification_methods'])} - {r['verification_note']}")
        srcs = []
        for s in r["sources"]:
            if s["kind"] == "owner_answer":
                srcs.append(f"owner row {s['row']} (sha256 {s['answer_sha256'][:12]}...)")
            elif s["kind"] == "owner_decision":
                srcs.append(f"{s['decision_id']} `{s['key']}`")
            elif s["kind"] == "rfp_official_clause":
                srcs.append(f"**{s['clause_id']}** (p. {s['page']}, {s['section']}): \"{_esc(s['verbatim'])}\"")
            elif s["kind"] == "rfp_secondary_record":
                srcs.append(f"R2 {s['locator']}: \"{s['quote']}\" ({s['source_locator']}; historical, superseded by "
                            f"the RFP registration)")
            else:
                srcs.append(f"{s['locator']} ({s['ref']})")
        a("- Sources: " + "; ".join(srcs))
        if r.get("rfp_rebase", {}).get("note"):
            a(f"- RFP re-base note: {r['rfp_rebase']['note']}")
        for m in r.get("milestones", []):
            a(f"- Milestone {m['milestone']} ({m['rfp_clause']}): due {m['due']}, share {m['share']}")
        for sr in r.get("sub_requirements", []):
            a(f"- Sub-requirement {sr['item']}) ({sr['rfp_clause']}): \"{sr['token']}\"")
        if r["open_readings"]:
            a("- Open readings (TBD_OWNER, carried side by side): " + "; ".join(
                f"{o['id']} ({o['status'].split(' ')[0]}): {_esc(_short(o['question']))}" for o in r["open_readings"]))
        if r["rtm_xref"] or r["lane24_gates"]:
            a(f"- Historical cross-reference: RTM {', '.join(r['rtm_xref']) or '-'}; lane-24 gates "
              f"{', '.join(r['lane24_gates']) or '-'}")
        for c in CONFIGS:
            cell = r["configurations"][c]
            if cell.get("applicability_marker"):
                a(f"- **{c}: {cell['applicability_marker']}** (vocabulary status {cell['status']}, "
                  f"`{cell['rule']}`; never compliance evidence)")
            else:
                a(f"- **{c}: {cell['status']}** (`{cell['rule']}`) - {cell['reason']}")
            for art in cell["artifacts"]:
                a(f"    - [{art['role']}/{art['kind']}] `{art['path']}` `{art['id']}`: {_esc(art['evidence_state'])}")
            for art in cell["artifacts"]:
                if art.get("detail", {}).get("analyses"):
                    for an in art["detail"]["analyses"]:
                        c_ = an["floor_fail_check"]
                        a(f"    - mass {an['reference']}: evidence floors "
                          + ", ".join(f"{f['line']} {f['floor_kg']} kg" for f in an["evidence_floors"])
                          + f"; floor-only {c_['min_floor_kg']}-{c_['max_floor_kg']} kg in {c_['n_readings']} readings,"
                          f" exceeding {c_['n_exceeding']}; lower bound verified: {an['lower_bound_verified']}; mixed "
                          f"basis {json.dumps(an['mixed_basis_counts'], sort_keys=True)}")
    a("")
    a("## (a) Items")
    a("")
    a("| id | name | value | units | basis | origin / RFP clauses | evidence class | status | freeze point |")
    a("|---|---|---|---|---|---|---|---|---|")
    for it in doc["items"]:
        a(f"| {it['id']} | {_esc(it['name'])} | {_esc(it['value'])} | {it['units']} | {_esc(it['basis'])} | "
          f"{_origin(it)} | "
          f"{it['evidence_class']} | {_esc(it['status'])} | {it['freeze_point']} |")
    a("")
    a("## (b) Interface demands")
    a("")
    a("| id | direction | counterpart | content | status |")
    a("|---|---|---|---|---|")
    for d in doc["interface_demands"]:
        a(f"| {d['id']} | {_esc(d['direction'])} | {_esc(d['counterpart'])} | {_esc(d['content'])} | {d['status']} |")
    a("")
    a("## (c) Owner answers and decisions applied")
    a("")
    for o in doc["owner_answers_applied"]:
        a(f"- Row {o['row']} ({', '.join(o['covers_ids'])}; sha256 {o['answer_sha256'][:12]}...): {o['how_applied']}")
    for d in doc["decisions_applied"]:
        a(f"- {d['decision_id']} `{d['key']}`: {_esc(d['how_applied'])}")
    a("")
    a("## (d) Owner questions raised by this lane")
    a("")
    for q in doc["open_owner_questions"]:
        a(f"- **{q['id']}** (as raised {q['status']}; now {q.get('status_current', q['status'])} "
          f"{q.get('decision_code', '')}, needed by {q['needed_by']}): {q['question']} "
          "Readings: " + " / ".join(q["admissible_readings"]) + f". Why new: {q['why_new']}.")
    a("")
    a("## (d2) A9.16 owner decisions applied")
    a("")
    a(doc["a9_16_rfp_rule"] + ".")
    a("")
    for g in doc["a9_16_compliance_gates"]:
        a(f"- compliance gate {g['id']} ({g['gate']}; {g['rvm_row']}; RFP {', '.join(g['rfp_clauses'])}): "
          f"{g['status']}")
    for r in doc["rows"]:
        if "a9_16" in r:
            a(f"- {r['id']}: " + _esc("; ".join(f"{k}: {v}" for k, v in r["a9_16"].items() if k != "decisions")))
    a("")
    a("## (d2b) A9.19 / A9.20 owner decisions applied (flight architecture, Xe role, C1 ground-only)")
    a("")
    x = doc["a9_19_20"]
    a(f"Decisions: {'; '.join(x['decisions'])}.")
    a("")
    a(f"- Flight architecture (A9.19): {x['flight_architecture']}.")
    a(f"- Amends: {x['amends']}. Unchanged: {x['unchanged']}.")
    for c in CONFIGS:
        a(f"- `{c}`: {doc['configurations'][c]}")
    a(f"- {x['a9_2_status_note']}.")
    a(f"- {x['owner_open_note']}.")
    for r in doc["rows"]:
        if "a9_19" in r:
            rest = {k: v for k, v in r["a9_19"].items() if k != "decisions"}
            if rest:
                a(f"- {r['id']}: " + _esc("; ".join(f"{k}: {v}" for k, v in rest.items())))
    a("")
    a("Owner answers applied (A9.19 / A9.20):")
    a("")
    for o in doc["a9_19_owner_answers_applied"]:
        a(f"- {o['decision']} `{o['question_id']}` (json sha256 {o['decision_json_sha256'][:12]}..., verbatim md sha256 "
          f"{o['decision_md_sha256'][:12]}...) -> {', '.join(o['record_ids'])}: {_esc(o['how_applied'])}")
    a("")
    a("### Recorder proposals open for the owner (NOT requirements, NOT owner decisions)")
    a("")
    for pr in doc["recorder_proposals_open_for_owner"]:
        a(f"- **{pr['id']}** [{pr['status']}]: {_esc(pr['proposal'])} Why raised: {_esc(pr['why_raised'])} "
          f"Numbers: {pr['numbers']}. Handling: {pr['handling']}.")
    a("")
    a("## (d3) RFP re-base (AG-15)")
    a("")
    a(f"Rule: {rb['rule']}. AG-15: {rb['ag_15_status']}.")
    a("")
    a(f"Registration `{rb['registration']['path']}` ({rb['registration']['n_clauses']} clauses, transcription sha256 "
      f"`{rb['registration']['clauses_sha256']}`, {rb['registration']['clauses_hash_rule']}). Decisions: "
      + "; ".join(rb["decisions"]) + ".")
    a("")
    a("Origins: " + ", ".join(f"{k} {v}" for k, v in rb["origin_counts"].items()) + ".")
    a("")
    a("| RFP clause | page | section | RVM rows (derived) | related rows | note |")
    a("|---|---|---|---|---|---|")
    for c in rb["clause_coverage"]:
        note = []
        if "not_system_requirement" in c:
            note.append(c["not_system_requirement"]["class"] + ": " + c["not_system_requirement"]["why"])
        if "partial_programmatic" in c:
            note.append(c["partial_programmatic"])
        a(f"| {c['clause_id']} | {c['page']} | {_esc(c['section'])} | {', '.join(c['rvm_rows']) or '-'} | "
          f"{', '.join(c['related_rvm_rows']) or '-'} | {_esc('; '.join(note))} |")
    a("")
    a("### RFP-vs-repository discrepancies (recorded, not resolved here)")
    a("")
    a("| id | topic | RFP clauses | RFP | repository | disposition | action |")
    a("|---|---|---|---|---|---|---|")
    for d in rb["discrepancies"]:
        a(f"| {d['id']} | {_esc(d['topic'])} | {', '.join(d['rfp_clauses']) or '-'} | {_esc(d['rfp'])} | "
          f"{_esc(d['repository'])} | {_esc(d['disposition'])} | {_esc(d['owner_or_drdo_action'])} |")
    a("")
    a("## (e) Historical reuse")
    a("")
    for h in doc["historical_reuse"]["artifacts"]:
        a(f"- `{h['path']}` sha256 `{h['sha256']}` - {h['role']}")
    a(f"- Reused: {doc['historical_reuse']['reused']}")
    a(f"- Not reused: {doc['historical_reuse']['not_reused']}")
    a("")
    a("## (f) M16 impact")
    a("")
    for m in doc["m16_impact"]:
        a(f"- Row {m['m16_row']} `{m['key']}` (v3 {m['execution_state_v3']}): RVM {', '.join(m['rvm_rows'])} - "
          f"{m['state_change']}")
    a("")
    a("## Pins and references")
    a("")
    for p in doc["pins"]:
        a(f"- pinned `{p['path']}` `{p['sha256']}` ({p['role']})")
    for p in doc["referenced_not_pinned"]:
        a(f"- read, not pinned: `{p['path']}` ({p['role']})")
    a("")
    a("## Excluded candidates")
    a("")
    for e in doc["excluded_candidates"]:
        a(f"- {e['id']}: {e['why']}")
    a("")
    return "\n".join(L)


def render():
    doc = build_doc()
    js = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    md = render_md(doc)
    return js, md


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless outputs are reproduced byte-for-byte")
    args = ap.parse_args(argv)
    js, md = render()
    jp, mp = HERE / JSON_NAME, HERE / MD_NAME
    if args.check:
        ok = jp.exists() and mp.exists() and jp.read_text(encoding="utf-8") == js and mp.read_text(
            encoding="utf-8") == md
        print("OK" if ok else "MISMATCH: rerun the builder")
        return 0 if ok else 1
    jp.write_text(js, encoding="utf-8")
    mp.write_text(md, encoding="utf-8")
    print(f"wrote {jp.relative_to(REPO)} and {mp.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

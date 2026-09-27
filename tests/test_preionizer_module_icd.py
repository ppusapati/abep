"""H-1 common Pre-Ionizer Module ICD (fo_preionizer_module_icd, owner addendum A6).

Checks schemas/interfaces/preionizer_module_icd_v1.json and its companion document:
  - the file parses, is a JSON Schema whose occupant declaration must conform to every common item PMI-01..PMI-11;
  - all 11 common boundaries are present, with ids, definitions, units, quantities and a satisfiability entry for
    PIM-RF, PIM-ECR and PIM-0, none of them not satisfiable (the common interface is not secretly RF-specific);
  - every JSON number sits inside a quantity with an evidence class and a source (path, JSON pointer, sha256), and the
    pointer resolves to the same value in the cited file; every TBD quantity is null with "TBD - requires ..." and a
    closing step;
  - the RF, ECR and HW-0 annexes reference only defined common items; the HW-0 blank annex exists; the ECR annex is
    flagged alternate and not an equal proposal baseline; RF is the primary contingency;
  - the confound table references only defined common items; milestones A/B/C are stated;
  - A5, A6 (and A4, G0) are pinned by the sha256 of the immutable files, G0 is CLEAN, no mutable governance file is
    pinned; the bus components equal abep_sim.arch_boundary.PREIONIZER_COMPONENTS;
  - the builder reproduces both committed files (skipped with a re-pin message if a pinned deliverable changed) and
    fails loudly on a missing input.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICD = os.path.join(ROOT, "schemas", "interfaces", "preionizer_module_icd_v1.json")
DOC = os.path.join(ROOT, "docs", "interfaces", "preionizer_module", "PREIONIZER_MODULE_ICD.md")
SCRIPT = os.path.join(ROOT, "docs", "interfaces", "preionizer_module", "build_preionizer_module_icd.py")

ARCHS = ["hall_only", "rf_hall", "ecr_hall"]
EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
VALUED = {"RFP", "SOURCED", "PROPOSED", "DERIVED", "ALLOCATION"}
COMMON_IDS = [f"PMI-{i:02d}" for i in range(1, 12)]
BOUNDARIES = ["mechanical_envelope_and_mounting_datum", "gas_flow_path_and_pressure_boundary",
              "electrical_power_boundary", "control_enable_interlock_lines", "thermal_rejection_interface",
              "grounding_and_shielding", "diagnostics", "service_line_routing", "permitted_magnetic_field_disturbance",
              "allowable_pressure_drop", "installation_removal_reproducibility"]
OCCUPANTS = ["PIM-RF", "PIM-ECR", "PIM-0"]
SAT_OK = {"BY_DESIGN", "TRIVIAL", "IN_PRINCIPLE_OPEN_DESIGN_RISK"}
TBD_PREFIX = "TBD - requires "
A5 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json"
A6 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json"
A5_SHA = "0554136751f5ffc7bd7f62c1c4723acce946ef4f523f43687b95710cc8ace621"
A6_SHA = "aaeb7c503c3791f81d4c589e8e25289befa6fcb3b16ce6f962b153715c883180"


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sha(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _resolve(doc, pointer):
    cur = doc
    for raw in pointer[1:].split("/"):
        tok = raw.replace("~1", "/").replace("~0", "~")
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


@pytest.fixture(scope="module")
def schema():
    return _load(ICD)


@pytest.fixture(scope="module")
def icd(schema):
    return schema["x-preionizer-module-icd"]


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("build_preionizer_module_icd", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _quantities(icd):
    for it in icd["common_items"]:
        for q in it["quantities"]:
            yield it["id"], q
    for a in icd["annexes"].values():
        for m in a["module_specific_items"]:
            for q in m["quantities"]:
                yield m["id"], q


# ---------------------------------------------------------------------------------------------------------------- schema
def test_schema_parses_and_requires_every_common_item(schema, icd):
    assert schema["$schema"].startswith("https://json-schema.org/")
    assert schema["$id"] == "urn:abep:schemas:interfaces:preionizer_module_icd_v1"
    conf = schema["properties"]["conformance"]
    assert conf["required"] == COMMON_IDS
    assert sorted(conf["properties"]) == COMMON_IDS
    assert schema["properties"]["architecture"]["enum"] == ARCHS
    assert schema["properties"]["module"]["enum"] == ["PIM-0", "PIM-RF", "PIM-ECR"]
    assert set(schema["$defs"]["evidence_class"]["enum"]) == EVIDENCE_CLASSES
    assert icd["status"] == "DRAFT_PENDING_OWNER"
    assert icd["architectures"] == ARCHS
    assert icd["phase1_branch_outcomes"] == {"A": "hall_only", "B": "rf_hall", "C": "ecr_hall", "NO_VIABLE_CASE": None}


def test_all_eleven_common_boundaries_present(icd):
    items = icd["common_items"]
    assert [it["id"] for it in items] == COMMON_IDS
    assert [it["boundary"] for it in items] == BOUNDARIES
    for it in items:
        for key in ("title", "definition", "common_requirement", "units", "quantities", "satisfiability",
                    "verification", "traces_to"):
            assert it.get(key), f"{it['id']} lacks {key}"
        assert it["verification"].get("method") and it["verification"].get("stage")


def test_common_items_not_secretly_rf_specific(icd):
    """Every common item is satisfiable by the RF module, the ECR module and the HW-0 blank alike."""
    for it in icd["common_items"]:
        sat = it["satisfiability"]
        assert sorted(sat) == sorted(OCCUPANTS), it["id"]
        for occ in OCCUPANTS:
            assert sat[occ]["status"] in SAT_OK, (it["id"], occ, sat[occ]["status"])
            assert sat[occ]["how"].strip(), (it["id"], occ)
        if any(sat[o]["status"] == "IN_PRINCIPLE_OPEN_DESIGN_RISK" for o in OCCUPANTS):
            assert it.get("why_common_not_annex"), f"{it['id']} has an open design risk but no reason for being common"
    # the envelope is sized to the largest occupant (incl. ECR magnet), never RF-sized
    pmi01 = icd["common_items"][0]
    assert "ECR" in pmi01["common_requirement"] and "never RF-sized" in pmi01["common_requirement"]
    # the service-line set is the union of all occupants' lines
    pmi08 = next(it for it in icd["common_items"] if it["id"] == "PMI-08")
    assert "UNION" in pmi08["definition"] and "ECR magnet" in pmi08["definition"]


def test_bus_components_match_boundary_module(icd):
    from abep_sim import arch_boundary as ab
    pmi03 = next(it for it in icd["common_items"] if it["id"] == "PMI-03")
    assert ab.BOUNDARY_VERSION == "bus_power_boundary_v1"
    assert {k: tuple(v) for k, v in pmi03["bus_components"].items()} == dict(ab.PREIONIZER_COMPONENTS)


# ------------------------------------------------------------------------------------------------------ evidence rules
def test_every_number_has_source_and_evidence_class(icd):
    def walk(node, path, owner):
        if isinstance(node, dict):
            is_q = "status" in node and "name" in node and "value" in node
            for k, v in node.items():
                walk(v, f"{path}/{k}", node if is_q else owner)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}/{i}", owner)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            assert owner is not None, f"bare number {node!r} at {path}"
            assert owner.get("evidence_class") in EVIDENCE_CLASSES, f"{path}: no evidence class"
            src = owner.get("source")
            assert isinstance(src, dict) and src.get("path") and src.get("pointer", "").startswith("/") \
                and re.fullmatch(r"[0-9a-f]{64}", src.get("sha256", "")), f"{path}: no source"
    walk(icd, "", None)


def test_quantity_records_well_formed(icd):
    n_valued = n_tbd = 0
    for owner, q in _quantities(icd):
        assert q.get("name") and q.get("unit"), (owner, q)
        if q["status"] == "TBD":
            n_tbd += 1
            assert q["value"] is None, (owner, q["name"])
            assert q["tbd_requires"].startswith(TBD_PREFIX) and len(q["tbd_requires"]) > len(TBD_PREFIX) + 5
            assert q.get("closes_at"), (owner, q["name"])
        else:
            n_valued += 1
            assert q["status"] in VALUED, (owner, q["name"], q["status"])
            assert q["value"] is not None
            assert q["evidence_class"] in EVIDENCE_CLASSES
    assert n_valued >= 10 and n_tbd >= 20


def test_sourced_values_resolve_to_cited_files(icd):
    for owner, q in _quantities(icd):
        for key in ("source", "source_ref"):
            src = q.get(key)
            if not src:
                continue
            path = os.path.join(ROOT, src["path"])
            assert os.path.isfile(path), src["path"]
            rec = _resolve(_load(path), src["pointer"])
            assert isinstance(rec, dict) and "value" in rec, (owner, q["name"])
            if key == "source_ref":
                assert rec["value"] is None, f"{q['name']}: TBD cites a record that now carries a value"
            elif "value_as_published" in q:
                assert rec["value"] == q["value_as_published"] and q.get("transformation")
            else:
                assert rec["value"] == q["value"], (owner, q["name"], rec["value"], q["value"])
                if rec.get("evidence_class"):
                    assert rec["evidence_class"] == q["evidence_class"], q["name"]


def test_allocations_never_predictions(icd):
    for owner, q in _quantities(icd):
        if q.get("source", {}).get("path") == A5:
            assert q["status"] == "ALLOCATION", q["name"]
    text = json.dumps(icd).lower()
    assert "sgb-screen" not in text  # no screening candidate as a performance source
    for bad in ("is the winner", "is selected as baseline", "conditional_baseline("):
        assert bad not in text, bad


# ------------------------------------------------------------------------------------------------------------ annexes
def test_annexes_reference_only_defined_common_items(icd):
    defined = set(COMMON_IDS)
    assert sorted(icd["annexes"]) == ["ANNEX-ECR", "ANNEX-HW0", "ANNEX-RF"]
    seen_ids = set()
    for key, a in icd["annexes"].items():
        assert set(a["uses_common_items"]) <= defined and a["uses_common_items"], key
        assert a["module_specific_items"], key
        assert a["deviations"], key
        for m in a["module_specific_items"]:
            assert m["id"] not in seen_ids and m["id"] not in defined
            seen_ids.add(m["id"])
        for d in a["deviations"]:
            assert d["common_items"] and set(d["common_items"]) <= defined, (key, d["id"])
            assert d["deviation"] and d["confound_risk"] and d["proposed_control"], d["id"]
            assert d["id"] not in seen_ids
            seen_ids.add(d["id"])
    refs = set(re.findall(r"PMI-\d\d", json.dumps(icd)))
    assert refs <= defined, refs - defined


def test_hw0_blank_annex_present(icd):
    a = icd["annexes"]["ANNEX-HW0"]
    assert a["module"] == "PIM-0" and a["architecture"] == "hall_only"
    assert a["role"] == "CONTROLLED_REFERENCE_BLANK"
    assert a["uses_common_items"] == COMMON_IDS
    text = json.dumps(a)
    for needle in ("sham", "terminated", "jumper", "controlled variable"):
        assert needle in text, needle
    covered = {c for d in a["deviations"] for c in d["common_items"]}
    assert {"PMI-05", "PMI-09", "PMI-10"} <= covered  # thermal / magnetic / pressure-drop footprint addressed


def test_ecr_annex_flagged_alternate_and_rf_primary(icd):
    ecr = icd["annexes"]["ANNEX-ECR"]
    rf = icd["annexes"]["ANNEX-RF"]
    assert ecr["role"] == "ALTERNATE" and ecr["alternate_not_equal_proposal_baseline"] is True
    assert "does NOT make ECR an equal proposal baseline" in ecr["role_statement"]
    assert ecr["architecture"] == "ecr_hall" and ecr["module"] == "PIM-ECR"
    assert rf["role"] == "PRIMARY_CONTINGENCY" and rf["architecture"] == "rf_hall" and rf["module"] == "PIM-RF"
    assert "alternate_not_equal_proposal_baseline" not in rf
    with open(DOC, encoding="utf-8") as f:
        assert "ALTERNATE - NOT AN EQUAL PROPOSAL BASELINE" in f.read()


def test_confound_table(icd):
    rows = icd["confound_table"]
    assert len(rows) >= 10
    for r in rows:
        assert set(r["common_items"]) <= set(COMMON_IDS) and r["common_items"], r["id"]
        assert r["residual_status"] in icd["residual_statuses"], r["id"]
        for k in ("factor", "hw0", "rf", "ecr", "mechanism", "removed_or_measured_by"):
            assert r[k], (r["id"], k)


def test_milestones_stated(icd):
    m = icd["milestones"]
    assert m["A"]["support"] and m["A"]["statement"]
    assert m["B"]["support"] == "NOT YET" and m["B"]["blocked_by"]
    assert m["C"]["support"].startswith("NO") and m["C"]["statement"]
    assert m["what_could_overturn"]


# ---------------------------------------------------------------------------------------------------------- pinning
def test_owner_decisions_and_g0_pinned(icd):
    od = icd["owner_decisions"]
    assert od["A5"]["path"] == A5 and od["A5"]["sha256"] == A5_SHA
    assert od["A6"]["path"] == A6 and od["A6"]["sha256"] == A6_SHA
    for key in ("A5", "A6", "A4"):
        if os.path.isfile(os.path.join(ROOT, od[key]["path"])):
            assert _sha(od[key]["path"]) == od[key]["sha256"], key
    g = icd["g0_baseline"]
    assert g["verdict"] == "CLEAN" and g["a5_sha256"] == A5_SHA
    if os.path.isfile(os.path.join(ROOT, g["path"])):
        assert _sha(g["path"]) == g["sha256"]
        assert _load(os.path.join(ROOT, g["path"]))["verdict"] == "CLEAN"


def test_no_mutable_governance_pinned(icd):
    for rel in icd["pinned_inputs"]:
        for bad in ("lane_registry", "trigger_registry", "trigger_ledger", "fired_triggers", "runtime_state",
                    "status_current"):
            assert bad not in rel, rel
        assert re.fullmatch(r"[0-9a-f]{64}", icd["pinned_inputs"][rel])


def test_companion_document_names_every_id(icd):
    with open(DOC, encoding="utf-8") as f:
        text = f.read()
    ids = list(COMMON_IDS) + [r["id"] for r in icd["confound_table"]] + [q["id"] for q in icd["owner_questions"]]
    for a in icd["annexes"].values():
        ids += [a["id"]] + [m["id"] for m in a["module_specific_items"]] + [d["id"] for d in a["deviations"]]
    for i in ids:
        assert i in text, i
    assert A5_SHA in text and A6_SHA in text


# ---------------------------------------------------------------------------------------------------------- builder
def test_builder_reproduces_committed_files(gen, icd):
    changed = [rel for rel, h in icd["pinned_inputs"].items() if _sha(rel) != h]
    if changed:
        pytest.skip(f"pinned deliverable(s) changed since the ICD was built; re-pin via the builder: {changed}")
    doc = gen.build()
    with open(ICD, encoding="utf-8") as f:
        assert f.read() == gen.render_json(doc)
    with open(DOC, encoding="utf-8") as f:
        assert f.read() == gen.render_md(doc)


def test_builder_fails_loudly_on_missing_input(gen, monkeypatch):
    monkeypatch.setitem(gen.DELIVERABLES, "HW", "docs/experiments/hardware/does_not_exist.json")
    gen._JSON_CACHE.clear()
    with pytest.raises(FileNotFoundError):
        gen.build()
    gen._JSON_CACHE.clear()


def test_builder_refuses_value_override_and_bad_pointer(gen):
    with pytest.raises(ValueError):
        gen.sourced("x", "HW", "/rfp_basis/power_max_W", value=1.0)
    with pytest.raises(KeyError):
        gen.sourced("x", "HW", "/rfp_basis/no_such_key")

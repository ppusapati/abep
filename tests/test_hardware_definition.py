"""W3 common-hardware definition (fo_hardware_definition): structure, evidence discipline and derived numbers.

Checks docs/experiments/hardware/hardware_requirements_v1.json:
  - status DRAFT; the three architecture ids exactly; milestone support stated with what the next milestone needs;
  - every JSON number sits inside a quantity with a valued status, an evidence class and a defined source;
    every TBD quantity is null and says "TBD — requires ...";
  - RFP quantities equal abep_sim.constants.RFPConstraints;
  - every requirement is well formed, and its sources and cross-references resolve;
  - the identity matrix keeps the Hall accelerator, cathode, magnetic circuit, feed and stand identical; only the module,
    its bus components and the inlet state may differ; the bus components match abep_sim.arch_boundary;
  - no screening candidate, no P5 calibration-nuisance key as a variable, no architecture winner;
  - the derived numbers equal a fresh recomputation by the committed generator, and fail loudly on missing inputs;
  - the companion document names every requirement and owner-question id;
  - control C5: every requirement of the merged AO/lifetime register (AOL-*) and magnet/coil qualification (MCQ-*) has a
    disposition in c5_integration, adopted rows name existing HW requirements that trace back to the source id, and
    the pinned sha256 of both registers and of the owner decision files match when those files are present.
Pinned inputs are cross-checked against their repository sources only when those files exist (they are merged lanes);
no other lane's in-progress path is required.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW_DIR = os.path.join(ROOT, "docs", "experiments", "hardware")
REGISTER = os.path.join(HW_DIR, "hardware_requirements_v1.json")
DOC = os.path.join(HW_DIR, "HARDWARE_DEFINITION.md")
SCRIPT = os.path.join(HW_DIR, "build_hardware_definition.py")

ARCHS = ["hall_only", "rf_hall", "ecr_hall"]
EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
VALUED = {"RFP", "SOURCED", "PROPOSED", "DERIVED"}
REQ_STATUSES = {"RFP", "PROPOSED", "TBD"}
TBD_PREFIX = "TBD — requires"


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def reg():
    return _load(REGISTER)


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("build_hardware_definition", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _walk(o, path=""):
    if isinstance(o, dict):
        yield path, o
        for k, v in o.items():
            yield from _walk(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, f"{path}/{i}")


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def test_header(reg):
    assert reg["schema"] == "hardware_requirements_register_v1"
    assert reg["status"] == "DRAFT_PENDING_OWNER"
    assert reg["lane"] == "fo_hardware_definition"
    assert reg["trigger"] == "T_PIVOT_HARDWARE_DEFINITION"
    assert reg["owner_disposition"]["id"] == "od_hardware_pivot"
    assert reg["architectures"] == ARCHS
    assert {v["arm"] for v in reg["hardware_configurations"].values()} == set(ARCHS)
    assert reg["hardware_configurations"]["HW-0"]["arm"] == "hall_only"
    assert reg["hardware_configurations"]["HW-RF"]["arm"] == "rf_hall"
    assert reg["hardware_configurations"]["HW-ECR"]["arm"] == "ecr_hall"
    assert set(reg["phases"]) == {"P1", "P2", "P3"}


def test_milestones(reg):
    m = reg["milestones"]
    assert m["supports"] == ["A"]
    for k in ("A", "B", "C"):
        assert m[k]["support"] and m[k]["what"] and m[k]["next_needed"]
    assert any("admitted" in s for s in m["B"]["next_needed"])


def test_every_number_is_a_sourced_quantity(reg):
    """A numeric leaf may only be the value (or a list element of the value) of a valued quantity."""
    refs = set(reg["references"])
    bad = []
    for path, node in _walk(reg):
        for k, v in node.items():
            nums = [v] if _is_number(v) else ([x for x in v if _is_number(x)] if isinstance(v, list) else [])
            if not nums:
                continue
            if k != "value":
                bad.append(f"{path}/{k}: number outside a quantity 'value'")
                continue
            if isinstance(v, list) and len(nums) != len(v):
                bad.append(f"{path}: mixed list")
            if node.get("status") not in VALUED:
                bad.append(f"{path}: status {node.get('status')!r} not valued")
            if node.get("evidence_class") not in EVIDENCE_CLASSES:
                bad.append(f"{path}: evidence_class {node.get('evidence_class')!r}")
            src = node.get("source")
            if not src or not isinstance(src, list) or any(s not in refs for s in src):
                bad.append(f"{path}: source {src!r} not defined in references")
            if not node.get("locator") or not node.get("unit"):
                bad.append(f"{path}: missing locator/unit")
            if any(not math.isfinite(float(x)) for x in nums):
                bad.append(f"{path}: non-finite")
    assert not bad, "\n".join(bad)


def test_tbd_quantities_are_null_and_state_requirement(reg):
    n = 0
    for path, node in _walk(reg):
        if node.get("status") == "TBD" and "unit" in node:
            n += 1
            assert node.get("value") is None, path
            assert isinstance(node.get("requires"), str) and node["requires"].startswith(TBD_PREFIX), path
    assert n >= 20


def test_rfp_values_match_constants(reg):
    from abep_sim.constants import RFPConstraints
    rfp = RFPConstraints()
    b = reg["rfp_basis"]
    assert b["thrust_band_mN"]["value"] == [rfp.thrust_min_mN, rfp.thrust_max_mN]
    assert b["power_max_W"]["value"] == rfp.power_max_W
    assert b["mass_max_kg"]["value"] == rfp.mass_max_kg
    assert b["firing_hours_min_h"]["value"] == rfp.ignition_hours
    assert b["mission_hours_h"]["value"] == rfp.mission_hours
    assert b["altitude_band_km"]["value"] == [rfp.alt_min_km, rfp.alt_max_km]
    g = reg["absolute_thrust_gate"]
    assert g["sustained_thrust_min_mN"]["value"] == rfp.thrust_min_mN
    assert g["registered_capability_mN"]["value"] == rfp.thrust_max_mN
    # every quantity marked RFP carries a value equal to an RFP constant (or a pair of them)
    allowed = {rfp.thrust_min_mN, rfp.thrust_max_mN, rfp.power_max_W, rfp.mass_max_kg, rfp.ignition_hours,
               rfp.mission_hours, rfp.alt_min_km, rfp.alt_max_km}
    for path, node in _walk(reg):
        if node.get("status") == "RFP" and "value" in node:
            vals = node["value"] if isinstance(node["value"], list) else [node["value"]]
            assert all(float(x) in allowed for x in vals), path


def test_requirements_well_formed(reg):
    reqs = reg["requirements"]
    ids = [r["id"] for r in reqs]
    assert len(ids) == len(set(ids))
    items = {c["id"] for c in reg["configuration_items"]}
    assert {"H-1", "C-1", "MC-1", "FS-C", "PS-C", "SVC-1", "PIM-0", "PIM-RF", "PIM-ECR", "DIV-1"} <= items
    for r in reqs:
        assert re.fullmatch(r"HW-(ENV|H1|MC|C1|FS|PIM|ELEC|SVC)-\d\d", r["id"]), r["id"]
        assert r["status"] in REQ_STATUSES, r["id"]
        assert r["text"] and r["category"] and r["item"], r["id"]
        assert set(r["phases"]) <= {"P1", "P2", "P3"} and r["phases"], r["id"]
        assert r["verification"]["method"] and r["verification"]["stage"], r["id"]
        assert "identical_across_arms" in r and r["traces_to"], r["id"]
        assert isinstance(r["values"], dict), r["id"]
        if r["status"] == "TBD":
            assert any(q.get("status") == "TBD" for q in r["values"].values()), r["id"]
    cats = {r["category"] for r in reqs}
    # the lane brief's coverage list
    for c in ("operating_envelope", "materials", "start_transfer", "gas_interface", "electrical_interface",
              "rf_microwave_interface", "magnetic_interaction", "bz_measurability", "installation_reproducibility",
              "removability", "thermal", "cathode", "hall_accelerator", "magnetic_circuit",
              # control C5 (execution directive A2): AO/lifetime and magnet/coil provisions
              "witness_coupons", "replaceable_components", "cathode_exposure_monitoring", "post_test_metrology",
              "magnet_coil_qualification"):
        assert c in cats, c


def test_cross_references_resolve(reg):
    ids = {r["id"] for r in reg["requirements"]} | {q["id"] for q in reg["owner_questions"]}
    text = json.dumps(reg, ensure_ascii=False)
    for ref in set(re.findall(r"\b(HW-(?:ENV|H1|MC|C1|FS|PIM|ELEC|SVC)-\d\d|HWQ-\d\d)\b", text)):
        assert ref in ids, ref
    outs = set(reg["derived_numbers"]["outputs"])
    for ref in set(re.findall(r"derived_numbers\.outputs\.([A-Za-z0-9_]+)", text)):
        assert ref in outs, ref
    qids = [q["id"] for q in reg["owner_questions"]]
    assert qids == [f"HWQ-{i:02d}" for i in range(1, len(qids) + 1)]


def test_identity_matrix_and_bus_components(reg):
    from abep_sim import arch_boundary as ab
    im = reg["identity_matrix"]
    same = " ".join(e["element"] for e in im["must_be_identical"])
    for k in ("H-1", "MC-1", "C-1", "feed", "stand", "V_d", "ledger"):
        assert k in same, k
    differ = " ".join(e["element"] for e in im["may_differ"])
    assert "module" in differ and "HALL_INLET_Z0" in differ
    named = set(re.findall(r"\b(rf_source|ecr_source|ecr_magnet)\b", differ))
    pre = set().union(*[set(v) for v in ab.PREIONIZER_COMPONENTS.values()])
    assert named == pre
    assert tuple(ARCHS) == ab.ARCHITECTURES and ab.BOUNDARY_VERSION == "bus_power_boundary_v1"
    assert "calibration nuisance" in im["never_a_hardware_variable"]
    # every common configuration item is flagged identical; modules are not
    for c in reg["configuration_items"]:
        assert c["common"] == (c["id"] in {"H-1", "MC-1", "C-1", "FS-C", "PS-C", "SVC-1"}), c["id"]
    # requirements on common items are identical across arms
    for r in reg["requirements"]:
        if r["item"] in {"H-1", "MC-1", "C-1", "FS-C", "SVC-1"}:
            assert r["identical_across_arms"] is True, r["id"]


def test_no_forbidden_content(reg):
    text = json.dumps(reg, ensure_ascii=False).lower()
    # screening candidates may only be named in the compliance statement that excludes them
    scrub = copy.deepcopy(reg)
    scrub.pop("compliance")
    s2 = json.dumps(scrub, ensure_ascii=False).lower()
    assert "sgb-screen" not in s2
    for key in ("p5_registration", "p5_coil_shape", "beam_efficiency_reading", "facility_ingestion_interpretation"):
        assert key not in text
    for word in ("winner", "best architecture", "recommended architecture"):
        assert word not in s2
    assert "hallthruster_bridge/bfield" not in text  # P5 B(z) files are never design values


def test_derived_numbers_reproduce(reg, gen):
    assert gen.check(reg) == []
    out = reg["derived_numbers"]["outputs"]
    assert math.isclose(out["B_res_ecr_2p45GHz_T"]["value"], 0.08752, rel_tol=1e-4)  # ECR-D001 cross-check
    assert out["T_over_Pbus_floor_at_T_min_mN_per_kW"]["value"] == 8.0
    assert out["Pbus_over_T_ceiling_at_T_min_W_per_mN"]["value"] == 125.0
    assert out["I_d_bound_envelope_max_A"]["value"] == out["I_d_bound_at_Vd_180V_A"]["value"]
    for q in out.values():
        assert q["status"] == "DERIVED" and q["evidence_class"] == "model-derived"


def test_derivation_identities(reg, gen):
    inp = reg["derived_numbers"]["inputs"]
    out = gen.derive(inp)
    # I_d bound times V_d reproduces the ceiling at every node
    for vd in inp["V_d_proposed_set_V"]["value"] + [inp["V_d_relaxed_upper_V"]["value"]]:
        assert math.isclose(out[f"I_d_bound_at_Vd_{vd}V_A"]["value"] * vd, inp["power_max_W"]["value"], rel_tol=1e-9)
    # alignment angle: cosine loss equals one contributor share
    for n in (4, 6, 8):
        th = math.radians(out[f"theta_align_max_n{n}_deg"]["value"])
        assert math.isclose(-math.log(math.cos(th)), out[f"u_contributor_max_n{n}"]["value"], rel_tol=1e-8)
        share = out[f"u_contributor_max_n{n}"]["value"] * math.sqrt(inp["n_installation_contributors"]["value"])
        assert math.isclose(share, inp[f"u_inst_max_n{n}"]["value"], rel_tol=1e-9)


def test_missing_input_raises(reg, gen):
    for key in gen.REQUIRED_INPUTS:
        inp = copy.deepcopy(reg["derived_numbers"]["inputs"])
        del inp[key]
        with pytest.raises(KeyError):
            gen.derive(inp)
    inp = copy.deepcopy(reg["derived_numbers"]["inputs"])
    inp["power_max_W"]["value"] = None
    with pytest.raises(ValueError):
        gen.derive(inp)


def test_stale_output_detected(reg, gen):
    bad = copy.deepcopy(reg)
    bad["derived_numbers"]["outputs"]["T_over_Pbus_floor_at_T_min_mN_per_kW"]["value"] = 7.9
    assert gen.check(bad)


def test_pins_against_repository_sources(reg, gen):
    needed = ["abep_sim/constants.py", "docs/evidence/ecr_source/ecr_evidence_matrix.json",
              "docs/architecture_comparison/hall_reference/hall_reference_v1.json",
              "docs/evidence/rf_source/rf_evidence_matrix.json",
              "docs/architecture_comparison/minimum_decisive_experiment/experiment_draft.json"]
    missing = [p for p in needed if not os.path.exists(os.path.join(ROOT, p))]
    if missing:
        pytest.skip(f"pinned sources not in this checkout: {missing}")
    assert gen.verify_pins(reg) == []


def test_document_covers_register(reg):
    with open(DOC, encoding="utf-8") as f:
        doc = f.read()
    for r in reg["requirements"]:
        rid = r["id"]
        m = re.match(r"(HW-[A-Z0-9]+-)(\d\d)", rid)
        # listed individually or inside a named range such as HW-ENV-01..08
        in_range = any(int(a) <= int(m.group(2)) <= int(b)
                       for a, b in re.findall(re.escape(m.group(1)) + r"(\d\d)\.\.(\d\d)", doc))
        assert rid in doc or in_range, rid
    for q in reg["owner_questions"]:
        assert q["id"] in doc
    for k in ("DRAFT", "Milestones", "PROPOSED", "TBD", "hall_only", "rf_hall", "ecr_hall"):
        assert k in doc


# ---------------------------------------------------------------------------------------------------------------
# Control C5 (docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A2_execution_directive.json): AO/lifetime + magnet/coil
C5_SOURCES = {"SRC-AOL": "docs/experiments/lifetime_ao/ao_lifetime_register_v1.json",
              "SRC-MCQ": "docs/experiments/magnet_coil/magnet_coil_qualification_v1.json"}
DISPOSITIONS = {"ADOPTED", "ADOPTED_PARTIAL", "ALIGNED", "NOT_ADOPTED"}


def _sha(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_c5_rows_well_formed(reg):
    c5 = reg["c5_integration"]
    hw = {r["id"]: r for r in reg["requirements"]}
    qtext = json.dumps(reg["owner_questions"], ensure_ascii=False)
    seen = set()
    for row in c5["rows"]:
        sid = row["source_id"]
        assert re.fullmatch(r"(AOL|MCQ)-[A-Z0-9]+-\d\d", sid), sid
        assert sid not in seen, sid
        seen.add(sid)
        assert row["disposition"] in DISPOSITIONS, sid
        for h in row["hw_requirements"]:
            assert h in hw, (sid, h)
        if row["disposition"] in {"ADOPTED", "ADOPTED_PARTIAL"}:
            # adopted into a requirement that traces back, or recorded as an owner question naming the source id
            assert any(sid in hw[h]["traces_to"] for h in row["hw_requirements"]) or sid in qtext, sid
        if row["disposition"] == "ALIGNED":
            assert row["hw_requirements"] or row["note"], sid
        if row["disposition"] == "NOT_ADOPTED":
            assert row["note"] and row.get("needed"), sid
    # every new (C5) requirement traces to at least one AOL-/MCQ- id
    for r in reg["requirements"]:
        if r["category"] in {"witness_coupons", "replaceable_components", "cathode_exposure_monitoring",
                             "post_test_metrology", "magnet_coil_qualification"}:
            assert any(t.startswith(("AOL-", "MCQ-")) for t in r["traces_to"]), r["id"]


def test_c5_core_items_adopted(reg):
    """The directive's named C5 items are hardware requirements, not only cross-references."""
    disp = {r["source_id"]: r["disposition"] for r in reg["c5_integration"]["rows"]}
    for sid in ("AOL-WC-02", "AOL-WC-03", "AOL-WC-04", "AOL-WC-05", "AOL-RC-01", "AOL-RC-02", "AOL-RC-03",
                "AOL-PM-05", "AOL-PM-06", "AOL-CX-07", "MCQ-W3-01", "MCQ-W3-03", "MCQ-W3-08", "MCQ-QT-02",
                "MCQ-QT-06", "MCQ-QT-09", "MCQ-OQ-05"):
        assert disp[sid] == "ADOPTED", sid
    for sid in ("AOL-WC-01", "AOL-CX-03", "AOL-CX-04", "AOL-PM-01", "MCQ-W4-01"):
        assert disp[sid] in {"ADOPTED", "ADOPTED_PARTIAL"}, sid
    for i in range(1, 9):
        assert disp[f"MCQ-S1-{i:02d}"] == "ADOPTED"
    hrr = " ".join(reg["hardware_readiness_review"]["entry_criteria"])
    assert "MCQ-S1-01..08" in hrr and "HW-H1-13" in hrr
    assert "no_life_extrapolation" in reg["compliance"]


@pytest.mark.parametrize("ref", sorted(C5_SOURCES))
def test_c5_covers_every_source_requirement(reg, ref):
    path = os.path.join(ROOT, C5_SOURCES[ref])
    if not os.path.exists(path):
        pytest.skip(f"{C5_SOURCES[ref]} not in this checkout")
    assert _sha(path) == reg["references"][ref]["sha256"] == reg["c5_integration"]["sources"][ref], (
        f"{C5_SOURCES[ref]} changed since the C5 integration; re-run the integration")
    src = _load(path)
    ids = {r["id"] for r in src["requirements"]}
    if ref == "SRC-MCQ":
        ids |= {x["id"] for x in src["s1_gate_items"]} | {x["id"] for x in src["qualification_tests"]}
    covered = {r["source_id"] for r in reg["c5_integration"]["rows"]}
    assert ids <= covered, sorted(ids - covered)
    assert covered & ids


def test_owner_decision_pins(reg):
    for ref in ("SRC-OD-PIVOT", "SRC-OD-A1", "SRC-OD-A2"):
        r = reg["references"][ref]
        path = os.path.join(ROOT, r["path"])
        if not os.path.exists(path):
            pytest.skip(f"{r['path']} not in this checkout")
        assert _sha(path) == r["sha256"], ref
    assert reg["references"]["SRC-OD-PIVOT"]["sha256"].startswith("5a5adb81")

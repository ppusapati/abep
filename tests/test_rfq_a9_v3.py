"""Tests for the A9 RFQ packages v3 (A9.16 owner-decision application, RFQ lane).

Checks that docs/procurement/rfq_a9_v3/ is reproducible from its builder, that it is a revision of the immutable v2
packages (v2 pinned and unchanged; every v2 requirement carried exactly once; every v2 line carried or explicitly
superseded), that each applied owner decision (A9.8 / A9.10 / A9.11 / A9.14 / A9.15 / A9.19 / A9.20) is cited by decision file + json
sha256 + question id with verbatim quotes, that the owner-decided package changes hold (RF-metrology package, H-1
build-to-print package, required DWV tester, dedicated target, Xe capability in both configurations), that owner-deferred
numbers stay TBD, and that every fail-closed rule function refuses incomplete evidence.
Run: python -m pytest -q tests/test_rfq_a9_v3.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LANE = REPO / "docs" / "procurement" / "rfq_a9_v3"
SCRIPT = LANE / "build_rfq_a9_v3.py"
JSON_PATH = LANE / "rfq_a9_v3.json"
MD_PATH = LANE / "RFQ_A9_V3.md"
V2_JSON = REPO / "docs" / "procurement" / "rfq_a9_v2" / "rfq_a9_v2.json"

PINNED = {
    "docs/procurement/rfq_a9_v2/rfq_a9_v2.json": "6960f2927ece5a171d851bc10bc2314e99ef448b1e6f7d5ba84b93d2226795cb",
    "docs/procurement/rfq_a9_v2/build_rfq_a9_v2.py": "4aa6ce0dfbc1698e27c2b737fb2f1c7f3efb55efc08969a4de22484acedb8964",
    "docs/decisions/OD_2026_10_01_A9_8_s1_p1_start_owner_decisions.json":
        "e96b8bc0a27f5fbc03d48d36db6e470dfc60c4960d6ba02cdaac8871752b537f",
    "docs/decisions/OD_2026_10_01_A9_10_s3_p1_later_stage_owner_decisions.json":
        "3a99f16dd957f533b6b7afb7539d27be132fae386148e1683e417db0ede26544",
    "docs/decisions/OD_2026_10_01_A9_11_s4_p2_owner_decisions.json":
        "d8baf59a5b92739698e29d893e89a30995559ee7167814c096dc24599679156c",
    "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json":
        "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c",
    "docs/decisions/OD_2026_10_01_A9_15_rfp_propellant_policy_owner_decision.json":
        "a928e87fa37aa6ad875fa1505041f21ea145919ebb86286df0e34629c966e309",
    "docs/decisions/OD_2026_10_01_A9_19_architecture_xe_contingency_owner_decision.json":
        "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16",
    "docs/decisions/OD_2026_10_01_A9_20_c1_ground_only_owner_decision.json":
        "9b88e441b5c3454a20c4696897c525ef5818f0cfd9f32c7a3b4fa8e1a204dcc6",
}
# (decision key, question id) the lane must apply (lane list of the A9.16 RFQ step)
REQUIRED_APPLIED = [
    ("A9.8", "P2Q-02"), ("A9.8", "OQ-RFQV2-01"), ("A9.8", "OQ-RFQV2-02"), ("A9.8", "OQ-RFQV2-03"),
    ("A9.8", "OQ-RFQV2-04"), ("A9.8", "OQ-RFQV2-05"), ("A9.8", "OQ-RFQV2-06"), ("A9.8", "OQ-RFQV2-08"),
    ("A9.10", "OQ-RFQV2-09"), ("A9.10", "OQ-RFQV2-10"), ("A9.11", "P2Q-07"), ("A9.14", "OQ-RFQ-01"),
    ("A9.14", "OQ-RFQ-03"), ("A9.14", "OQ-RFQ-04"), ("A9.14", "OQ-RFQ-08"), ("A9.14", "OQ-RFQ-09"),
    ("A9.14", "XA9Q-06"), ("A9.14", "OQ-A907-04"), ("A9.14", "XA9Q-07"), ("A9.14", "XA9Q-05"),
    ("A9.15", "governing_rule"), ("A9.15", "XA9Q-07"), ("A9.15", "XA9Q-05"),
    ("A9.19", "architecture"), ("A9.19", "xenon_role"), ("A9.20", "answer"), ("A9.10", "P1Q-07"),
]
PKGS = ["RFQ3-RF", "RFQ3-GAS", "RFQ3-VAC", "RFQ3-HALLEL", "RFQ3-MECH", "RFQ3-THRUST", "RFQ3-RFMET", "RFQ3-H1FAB"]


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("build_rfq_a9_v3", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def v2():
    return json.loads(V2_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pk(doc):
    return {p["id"]: p for p in doc["packages"]}


@pytest.fixture(scope="module")
def lines(doc):
    return {li["id"]: (p["id"], li) for p in doc["packages"] for li in p["line_items"]}


@pytest.fixture(scope="module")
def reqs(doc):
    out = {}
    for p in doc["packages"]:
        for r in p["requirements"]:
            out[r["id"]] = r
            if r["v1_id"]:
                out[r["v1_id"]] = r
    return out


# ------------------------------------------------------------------------------------------- reproducibility, pins
def test_builder_check_reproduces_outputs():
    res = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, cwd=REPO,
                         timeout=120)
    assert res.returncode == 0, res.stdout + res.stderr


def test_pinned_inputs_unchanged(doc):
    for rel, sha in PINNED.items():
        assert _sha(rel) == sha, rel
    for x in doc["v2_pins"] + doc["decision_pins_v3"]:
        assert _sha(x["path"]) == x["sha256"], x["path"]
    assert doc["revision_of"]["json_sha256"] == PINNED["docs/procurement/rfq_a9_v2/rfq_a9_v2.json"]


def test_build_refuses_changed_pin(mod, monkeypatch):
    bad = dict(mod.V2)
    bad["V2_JSON"] = (bad["V2_JSON"][0], "0" * 64)
    monkeypatch.setattr(mod, "V2", bad)
    with pytest.raises(RuntimeError):
        mod.verify_pins()


def test_owner_quote_must_be_verbatim(mod):
    with pytest.raises(ValueError):
        mod.OD("A9.8", "P2Q-02", "Put the V/I probe in the RF generator package.")
    with pytest.raises(KeyError):
        mod.OD("A9.14", "NOT-A-QUESTION", "PLAIN CERAMIC-INSULATED COPPER IS THE BASELINE.")


def test_all_owner_quotes_verbatim_in_decision_md(doc, mod):
    n = 0

    def walk(o):
        nonlocal n
        if isinstance(o, dict):
            if o.get("type") == "owner_decision":
                md = mod._norm((REPO / o["path"]).read_text(encoding="utf-8"))
                assert mod._norm(o["quote"]) in md, o["quote"]
                assert o["json_sha256"] == _sha(o["json_path"])
                n += 1
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(doc["packages"])
    assert n > 40


def test_hygiene_json_md_and_stdlib():
    json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert MD_PATH.is_file()
    src = SCRIPT.read_text(encoding="utf-8")
    imports = set(re.findall(r"^(?:import|from) (\w+)", src, re.M))
    assert imports <= {"__future__", "argparse", "copy", "hashlib", "json", "os", "re", "sys"}


# ------------------------------------------------------------------------------------------- revision structure
def test_eight_packages_and_identity(doc, pk):
    assert doc["schema"] == "rfq_a9_v3" and doc["id"] == "RFQ_A9_V3"
    assert [p["id"] for p in doc["packages"]] == PKGS
    assert doc["common_interface"]["id"] == "RFQ3-CIF"
    for p in doc["packages"]:
        assert (REPO / p["package_file"]).is_file()
        assert p["banner"][0].startswith("DO NOT PURCHASE")


def test_every_v2_requirement_carried_exactly_once(doc, v2):
    v2ids = [r["id"] for p in v2["packages"] for r in p["requirements"]]
    v3ids = [r["id"] for p in doc["packages"] for r in p["requirements"]]
    assert len(v3ids) == len(set(v3ids))
    assert set(v2ids) <= set(v3ids)
    for rid in set(v3ids) - set(v2ids):
        assert rid.startswith("RFQ3-"), rid


def test_every_v2_line_carried_or_superseded(doc, v2, lines):
    v2lines = {li["id"] for p in v2["packages"] for li in p["line_items"]}
    sup = {x["id"]: x for x in doc["superseded_lines_v3"]}
    assert set(sup) == {"HE-O02", "ME-O01"}
    assert sup["HE-O02"]["superseded_by"] == "HE-L19" and sup["ME-O01"]["superseded_by"] == "ME-L09"
    for lid in v2lines:
        assert (lid in lines) != (lid in sup), lid


def test_change_record_everywhere_and_decisions_cite_sha(doc):
    pins = {x["path"]: x["sha256"] for x in doc["decision_pins_v3"]}
    for p in doc["packages"]:
        for x in p["requirements"] + p["line_items"]:
            ch = x["change_v3"]
            assert ch["type"] in doc["change_types_v3"]
            if ch["type"] != "CARRIED_UNCHANGED":
                assert ch["why"] and ch["decisions"], x["id"]
            for d in ch["decisions"]:
                assert pins[d["json_path"]] == d["json_sha256"]


def _unrename(o):
    s = json.dumps(o, ensure_ascii=False)
    s = re.sub(r"RFQ3-(RF|GAS|VAC|HALLEL|MECH|THRUST|CIF)(?![-\w])", r"RFQ2-\1", s)
    return json.loads(s)


def test_unchanged_requirements_identical_to_v2(doc, v2):
    v2r = {r["id"]: r for p in v2["packages"] for r in p["requirements"]}
    for p in doc["packages"]:
        for r in p["requirements"]:
            if r["change_v3"]["type"] not in ("CARRIED_UNCHANGED", "MOVED_PACKAGE"):
                continue
            a = {k: v for k, v in r.items() if k not in ("change_v3", "package")}
            b = {k: v for k, v in v2r[r["id"]].items() if k != "package"}
            assert _unrename(a) == b, r["id"]


def test_modified_requirements_keep_before_snapshot(doc):
    for p in doc["packages"]:
        for r in p["requirements"]:
            if r["change_v3"]["type"] in ("CARRIED_MODIFIED", "MOVED_PACKAGE_MODIFIED"):
                assert r.get("before_v3"), r["id"]


def test_owner_answers_applied_one_entry_per_decision(doc, lines, reqs):
    oaa = doc["owner_answers_applied"]
    got = {(e["decision_key"], e["question_id"]): e for k, v in oaa.items() if k.startswith("a9_") for e in v}
    for key in REQUIRED_APPLIED:
        assert key in got, key
    cif = {x["id"] for x in doc["common_interface"]["items"]}
    ifd = {x["id"] for x in doc["interface_demands"]}
    sup = {x["id"] for x in doc["superseded_lines_v3"]}
    for (k, q), e in got.items():
        assert e["json_sha256"] == PINNED[e["decision_json"]]
        assert e["applied_in"], (k, q)
        assert e["citation"].startswith(f"{k} {q} (")
        for x in e["applied_in"]:
            assert x in lines or x in reqs or x in cif or x in ifd or x in sup, x
    assert "v2_history" in oaa


def test_open_owner_questions_all_closed(doc, v2):
    oq = doc["open_owner_questions"]
    closed = {x["id"]: x for x in oq["closed_since_previous_revision"]}
    v2open = [x["id"] for x in v2["open_owner_questions"]["new"]] + \
        [x["id"] for x in v2["open_owner_questions"]["carried_open_from_lanes"]] + \
        [x["id"] for x in v2["open_owner_questions"]["carried_open_from_v1"]]
    assert set(v2open) == set(closed)
    assert all(x["state"] == "OWNER_DECIDED" and x["json_sha256"] == PINNED[x["decision_json"]]
               for x in closed.values())
    assert oq["new"] == [] and oq["carried_open_from_lanes"] == [] and oq["carried_open_from_v1"] == []


def test_no_stale_tbd_owner_for_decided_questions(doc):
    decided = ["OQ-RFQV2-01", "OQ-RFQV2-02", "OQ-RFQV2-03", "OQ-RFQV2-05", "OQ-RFQV2-06", "OQ-RFQV2-08",
               "OQ-RFQV2-09", "OQ-RFQV2-10", "P2Q-02", "P2Q-07", "OQ-RFQ-01", "OQ-RFQ-03", "OQ-RFQ-04", "OQ-RFQ-08",
               "OQ-RFQ-09"]
    pat = re.compile(r"(TBD_OWNER|OPEN\)|, OPEN)[^.;]*?(" + "|".join(map(re.escape, decided)) + r")(?![\d])")
    for p in doc["packages"]:
        for x in p["requirements"]:
            for f in ("requirement", "value", "note", "title"):
                assert not pat.search(json.dumps(x.get(f), ensure_ascii=False)), (x["id"], f)
        for li in p["line_items"]:
            body = json.dumps({k: li[k] for k in ("item", "qty", "quote_sheet")}, ensure_ascii=False)
            assert not pat.search(body), li["id"]


# ------------------------------------------------------------------------------------------- A9.8 decisions
def test_p2q02_separate_rf_metrology_package(pk, lines):
    rf_ids = {li["id"] for li in pk["RFQ3-RF"]["line_items"]}
    met = pk["RFQ3-RFMET"]
    met_ids = {li["id"] for li in met["line_items"]}
    for lid in ("RF-L12", "RF-L13", "RF-L14", "RF-L15", "RF-L16", "RF-L17", "RF-L18", "RF-O01", "RFM-L01"):
        assert lid in met_ids and lid not in rf_ids
    for lid in ("RF-L01", "RF-L02", "RF-L03", "RF-L04", "RF-L08", "RF-L09", "RF-L11", "RF-L19"):
        assert lid in rf_ids
    assert met["owner_minimum_scope_verbatim"] == ["V/I probe", "VNA", "calibration kits", "fixed attenuators",
                                                   "antenna-simulator load", "antenna current probe",
                                                   "phase-stable VNA cables", "associated calibration accessories"]
    assert all(met["owner_minimum_scope_coverage"].values())
    assert all("RFQ3-RFMET-N01" in li["requirements"] for li in met["line_items"])
    for li in met["line_items"]:
        if "placement" in li:
            assert li["placement"]["status"] == "OWNER_DECIDED" and li["placement"]["package"] == "RFQ3-RFMET"


def test_oq_rfqv2_01_ar_mfc_certificate(reqs, lines):
    n = reqs["RFQ3-GAS-N01"]
    assert "17025" in n["value"]["desirable_not_mandatory"] and n["dispatch"] == "P1_NEEDED"
    assert "desirable but NOT mandatory" in n["requirement"]
    assert "RFQ3-GAS-N01" in lines["GAS-L01"][1]["requirements"]
    assert any("not mandatory" in x for x in lines["GAS-L01"][1]["quote_sheet"]["acceptance"])
    r18 = reqs["RFQ-02-R18"]   # score-bearing traceability keeps the accredited certificate
    assert r18["change_v3"]["type"] == "CARRIED_UNCHANGED" and "ISO-17025" in r18["value"]


def test_oq_rfqv2_02_pumping_quoted_and_external_facility_fail_closed(mod, reqs, lines):
    li = lines["VAC-L02"][1]
    assert li["dispatch"] == "P1_NEEDED" and "required infrastructure" in li["item"]
    assert "RFQ3-VAC-N01" in li["requirements"]
    assert "TBD" in reqs["RFQ2-VAC-N02"]["value"]["performance"]       # no pumping number invented
    assert mod.external_pumping_acceptance(None)["state"] == "NOT_ACCEPTED_UNVERIFIED"
    rec = {f: {"documented": True, "verified": True, "evidence": "doc-1"} for f in mod.PUMPING_FIELDS}
    assert mod.external_pumping_acceptance(rec)["state"] == "EXTERNAL_FACILITY_ACCEPTED_VERIFIED"
    for f in mod.PUMPING_FIELDS:
        r = copy.deepcopy(rec)
        r[f]["verified"] = False
        out = mod.external_pumping_acceptance(r)
        assert out["state"] == "NOT_ACCEPTED_UNVERIFIED" and out["missing"] == [f]


def test_oq_rfqv2_03_combined_load_separately_certified(mod, lines):
    assert "RFQ3-RF-N01" in lines["RF-L08"][1]["requirements"]
    assert "RFQ3-RF-N01" in lines["RF-L09"][1]["requirements"]
    full = {"rf_load": {"rating_certified": True, "return_loss_13p56MHz_certified": True},
            "calorimetric": {"method_documented": True, "calibration_certified": True, "uncertainty_stated": True}}
    assert mod.combined_load_functions(full)["one_device_serves_both"] is True
    half = copy.deepcopy(full)
    half["calorimetric"]["uncertainty_stated"] = False
    out = mod.combined_load_functions(half)
    assert out["one_device_serves_both"] is False and out["RF-L09"].startswith("NOT_CERTIFIED")
    assert out["RF-L08"] == "RF_LOAD_FUNCTION_SEPARATELY_CERTIFIED"
    assert mod.combined_load_functions(None)["state"] == "SEPARATE_DEVICE_REQUIRED_FOR_UNCERTIFIED_FUNCTION"


def test_oq_rfqv2_04_placement_no_architecture_meaning(doc, lines):
    assert "No architecture meaning" in doc["banner"][2]
    for lid in ("RF-L11", "GAS-L08", "HE-L03"):
        assert any(d["id"] == "OQ-RFQV2-04" for d in lines[lid][1]["change_v3"]["decisions"])


def test_oq_rfqv2_05_magnet_supply_in_p1_set(mod, reqs, lines):
    li = lines["HE-L02"][1]
    assert li["dispatch"] == "P1_NEEDED" and "TBD" in str(li["qty"])
    v = reqs["RFQ2-HALLEL-N02"]["value"]
    assert v["control"] == "current-controlled" and v["sensing"] == "4-wire remote voltage sense"
    assert v["V_I_ratings"].startswith("TBD")
    assert mod.magnet_supply_substitution({}, False)["state"] == "NOT_EVALUATED_MC1_RATINGS_TBD"
    ok = {f: True for f in mod.MAGNET_SUPPLY_FEATURES}
    assert mod.magnet_supply_substitution(ok, True)["state"] == "QUOTED_UNIT_RETAINED"   # ratings not verified
    ok["ratings_verified_against_mc1"] = True
    assert mod.magnet_supply_substitution(ok, True)["state"] == "VERIFIED_EXISTING_SUPPLY_MAY_REPLACE_QUOTED_UNIT"


def test_oq_rfqv2_06_anode_isolation_class(doc, reqs, lines):
    v = reqs["RFQ3-HALLEL-N01"]["value"]
    assert (v["V_operating_class_V"], v["V_design_withstand_min_V"], v["initial_DWV_V_DC"],
            v["initial_DWV_duration_s"]) == (350.0, 525.0, 1050.0, 60.0)
    assert len(v["not_covered"]) == 3 and v["triggered_reverification"]["V_DC"] == 700.0
    for lid in ("HE-L01", "HE-L04", "VAC-L03", "H1-L04", "H1-L08"):
        assert "RFQ3-HALLEL-N01" in lines[lid][1]["requirements"], lid
    g04 = next(x for x in doc["common_interface"]["items"] if x["id"] == "CIF-G04")
    assert g04["value"]["V_design_withstand_min_V"] == 525.0 and "TBD" not in json.dumps(g04["value"])
    assert reqs["RFQ2-VAC-N03"]["value"]["V_design_withstand_min_V"] == 525.0


def test_oq_rfqv2_08_dwv_route_required_tester_and_leakage_rule(mod, reqs, lines):
    li = lines["HE-L19"][1]
    assert li["dispatch"] == "P1_NEEDED" and li["option_line"] is False
    assert "HE-O02" not in lines
    assert reqs["RFQ2-HALLEL-N09"]["value"]["need"].startswith("REQUIRED")
    assert "TBD" in reqs["RFQ2-HALLEL-N09"]["value"]["leakage_resolution"]   # no leakage number invented
    n02 = reqs["RFQ3-HALLEL-N02"]["value"]
    assert n02["in_house_assembled_DWV"]["V_DC"] == 1050.0 and set(n02["record_fields"]) == set(mod.DWV_RECORD_FIELDS)
    full = {"leakage_limit": {"value_A": 1e-6, "documented_basis": "feedthrough datasheet",
                              "registered_before_test": True},
            "supplier_rating_permits_test": True, "supplier_certificate": "cert-1", "in_house_assembled_test": True,
            "test_voltage_V": 1050.0, "duration_s": 60.0, "leakage_current_A": 1e-7,
            "pressure_gas_condition": "air, ambient", "insulation_path_id": "IP-01", "configuration": "cfg-1",
            "observations": ["no flashover", "no breakdown"]}
    assert mod.dwv_path_status(full)["state"] == "DWV_ACCEPTANCE_EVIDENCE_COMPLETE"
    cases = [("leakage_limit", None, "G0_NOT_EVALUATED_TBD"),
             ("supplier_certificate", None, "SUPPLIER_CERTIFICATE_REQUIRED"),
             ("in_house_assembled_test", False, "ASSEMBLED_DWV_REQUIRED"),
             ("insulation_path_id", "", "INCOMPLETE_RECORD"),
             ("test_voltage_V", 700.0, "BELOW_REQUIRED_DWV_LEVEL"),
             ("leakage_current_A", 2e-6, "DWV_FAILED"),
             ("observations", ["flashover at 900 V"], "DWV_FAILED")]
    for k, val, state in cases:
        r = copy.deepcopy(full)
        r[k] = val
        assert mod.dwv_path_status(r)["state"] == state, k
    r = copy.deepcopy(full)
    r["leakage_limit"]["registered_before_test"] = False
    assert mod.dwv_path_status(r)["state"] == "INADMISSIBLE_LIMIT_NOT_PREREGISTERED"
    assert mod.dwv_path_status(None)["state"] == "G0_NOT_EVALUATED_TBD"


def test_p1q09_dedicated_target_required(reqs, lines):
    li = lines["ME-L09"][1]
    assert li["dispatch"] == "P1_NEEDED" and li["option_line"] is False
    v = reqs["RFQ2-MECH-N05"]["value"]
    assert v["geometry"].startswith("TBD") and v["chamber_wall_as_collector"] == "never"


def test_p3q01_probe_cross_check_line(reqs, lines, doc):
    assert lines["TH-L10"][1]["dispatch"] == "P1_NEEDED"
    r = reqs["RFQ3-THRUST-N03"]
    assert r["status"] == "TBD" and "excluded" in r["value"]["icp45_records"]
    m30 = next(x for x in doc["instrument_coverage"]["p1_measurements"] if x["id"] == "P1-M-30")
    assert m30["rfq_lines"][0]["line"] == "TH-L10"


# ------------------------------------------------------------------------------------------- A9.10 / A9.11
def test_oq_rfqv2_09_c1_lines_later_gated_on_h1_characterization(lines):
    for lid in ("HE-L10", "HE-L11", "HE-L12"):
        li = lines[lid][1]
        assert li["dispatch"] == "LATER"
        assert "P1Q-07" in li["dispatch_gate"]["gate"] and "C1_NOT_INSTALLED" in li["dispatch_gate"]["p1_s6"]


def test_oq_rfqv2_10_h1_build_to_print_package(mod, pk, lines, doc):
    h = pk["RFQ3-H1FAB"]
    assert h["owner_minimum_scope_verbatim"] == mod.H1FAB_SCOPE and all(h["owner_minimum_scope_coverage"].values())
    assert h["retained_in_house_verbatim"] == mod.H1FAB_IN_HOUSE
    assert not any(li["id"].startswith("H1-") for li in pk["RFQ3-MECH"]["line_items"])
    # A9.16 repair F4 (updated test): the P1 engineering article is quoted against a P9e configuration-controlled
    # drawing set (A9.10 OQ-RFQV2-10); the LOCK-1 release (A9.14 F5-OQ-04) is the flight-H-1 basis only
    for li in h["line_items"]:
        assert li["quote_sheet"]["send_state"].startswith("SEND_ONLY_WITH_CONTROLLED_H1_DRAWINGS")
        assert "purchase order NOT authorized" in li["quote_sheet"]["send_state"]
        assert li["quote_sheet"]["freeze_gate"] != "LOCK-1", li["id"]
        if not li["option_line"]:
            assert str(li["qty"]).startswith("TBD")
    n02 = next(r for r in h["requirements"] if r["id"] == "RFQ3-H1FAB-N02")
    assert n02["freeze_point"] == "P1-G0" and n02["value"]["configuration_control"] == "P9E_CONFIGURATION_CONTROLLED"
    assert "LOCK-1" in n02["value"]["flight_h1_release_basis"] and "requires the H-1 release" not in json.dumps(n02)
    assert mod.h1_fab_send_state(None)["state"] == "NOT_SENDABLE_DRAWING_NOT_CONTROLLED"
    good = {"drawing_id": "H1-DWG-001", "revision": "A", "content_sha256": "a" * 64, "open_items": [],
            "configuration_control": "P9E_CONFIGURATION_CONTROLLED"}
    assert mod.h1_fab_send_state(good)["state"] == "READY_TO_SEND_FOR_QUOTATION_BUILD_TO_PRINT"     # no LOCK-1 needed
    for k, v in (("content_sha256", "not-a-hash"), ("revision", ""), ("open_items", ["anode material OPEN"]),
                 ("configuration_control", None)):
        bad = dict(good, **{k: v})
        assert mod.h1_fab_send_state(bad)["state"] == "NOT_SENDABLE_DRAWING_NOT_CONTROLLED", k
    # the flight H-1 keeps the LOCK-1 release basis (A9.14 F5-OQ-04)
    assert mod.h1_fab_send_state(good, article="FLIGHT")["state"] == "NOT_SENDABLE_DRAWING_NOT_RELEASED"
    assert mod.h1_fab_send_state(dict(good, release="LOCK-1"), article="FLIGHT")["state"] == \
        "READY_TO_SEND_FOR_QUOTATION_BUILD_TO_PRINT"
    with pytest.raises(ValueError):
        mod.h1_fab_send_state(good, article="OTHER")
    assert doc["instrument_coverage"]["not_procured_dispositions"]["NP-H1-BUILD"]["disposition"] == \
        "RESOLVED_TO_RFQ_LINES"
    anode = json.dumps(next(r for r in h["requirements"] if r["id"] == "RFQ3-H1FAB-N04")["value"])
    assert "OPEN" in anode and "316L REJECTED_AS_CURRENT_BASELINE" in anode


def test_p2q07_vi_calibration_route(mod, reqs, lines):
    assert "RFQ3-RFMET-N02" in lines["RF-L12"][1]["requirements"]
    assert mod.vi_calibration_route({"accredited_scope_available": True})["state"] == "ACCREDITED_CERTIFICATE_REQUIRED"
    full = {k: True for k in mod.VI_IN_HOUSE_MIN_CONTENT}
    assert mod.vi_calibration_route(full)["state"] == "NOT_EVALUATED_INSTRUMENT"   # adequacy not shown
    full["uncertainty_adequate"] = True
    assert mod.vi_calibration_route(full)["state"] == "PENDING_CAL_P2_15_AT_POWER_VALIDATION"
    full["cal_p2_15_at_power_validation"] = "rec-1"
    out = mod.vi_calibration_route(full)
    assert out["state"] == "IN_HOUSE_TRACEABLE_CALIBRATION" and "NOT an accredited" in out["label"]
    part = dict(full)
    part.pop("uncertainty_magnitude_and_relative_phase")
    assert mod.vi_calibration_route(part)["state"] == "INCOMPLETE_IN_HOUSE_CALIBRATION"


# ------------------------------------------------------------------------------------------- A9.14 decisions
def test_oq_rfq_01_spares(lines):
    assert lines["TH-L03"][1]["qty"] == "1 spare set"
    assert "only if the C1 campaign is activated" in lines["HE-L10"][1]["qty"]
    assert "destructive" in lines["HE-O01"][1]["qty"] and lines["HE-O01"][1]["option_line"]
    assert "+ 1 spare" in lines["ME-L01"][1]["qty"] and "+ 1 spare" in lines["RF-L07"][1]["qty"]


def test_oq_rfq_03_xe_mfc_indicative_range_not_frozen(mod, reqs, lines):
    li = lines["GAS-L04"][1]
    assert li["quotation_timing"] == "INDICATIVE_QUOTE_NOW"
    assert li["quote_sheet"]["send_state"].startswith("INDICATIVE_QUOTATION_NOW")
    assert reqs["RFQ-02-R07"]["value"]["range"].startswith("TBD")
    assert mod.xe_mfc_range_state(False) == "RANGE_OPTIONS_QUOTED_NOT_FROZEN"
    assert mod.xe_mfc_range_state(True) == "RANGE_MAY_BE_FROZEN_FROM_REGISTERED_REFERENCE_POINT"


def test_oq_rfq_04_c1_start_controller_option_not_frozen(reqs, lines):
    li = lines["GAS-L06"][1]
    assert li["option_line"] is True
    v = reqs["RFQ-02-R11"]["value"]
    assert v["frozen"] is False and v["provisional_region_mgps"] == [0.6, 0.8]


def test_oq_rfq_08_option_b_never_sole_path(mod, lines):
    assert "RFQ3-THRUST-N01" in lines["TH-O01"][1]["requirements"]
    assert mod.stand_procurement_paths(["OPTION_B_COMPLETE_STAND"])["state"] == "REFUSED_OPTION_B_NEVER_SOLE_PATH"
    assert mod.stand_procurement_paths([])["state"] == "REFUSED_NO_PROCUREMENT_PATH"
    out = mod.stand_procurement_paths(["OPTION_A_CRITICAL_PARTS", "OPTION_B_COMPLETE_STAND"])
    assert out["state"] == "ADMISSIBLE" and out["comparator"] is True
    with pytest.raises(ValueError):
        mod.stand_procurement_paths(["OPTION_C"])


def test_oq_rfq_09_xa9q06_meop_supplier_proposed_75bar_retired(mod, reqs, lines):
    v = reqs["RFQ-07-R04"]["value"]
    assert "V_min_323K_l_by_case_and_MEOP_axis" not in v
    assert all("75bar" not in x for x in v["V_min_323K_l_by_case_sensitivity_axis"].values())
    assert "RETIRED" in v["retired_placeholder_points"]["state"]
    assert v["MEOP"].startswith("TBD - proposed by each supplier")
    assert "RFQ3-GAS-N02" in lines["GAS-L08"][1]["requirements"]
    assert mod.meop_basis_state({"source": "H27-34", "value_bar": 75})["state"] == "REFUSED_RETIRED_PLACEHOLDER"
    assert mod.meop_basis_state({})["state"] == "NOT_SELECTED_PENDING_COMPLIANT_QUOTATIONS"
    ok = {"supplier_proposed": True, "design_case_323K": True, "compliant_certified": True,
          "compared_against_other_quotations": True}
    assert mod.meop_basis_state(ok)["state"] == "MEOP_BASIS_SELECTABLE_BY_OWNER"


def test_oq_a907_04_coil_wire(mod, reqs):
    assert reqs["RFQ3-H1FAB-N03"]["value"]["baseline"] == "plain ceramic-insulated copper"
    assert mod.coil_wire_variant("plain_ceramic_insulated_copper")["state"] == "BASELINE"
    assert mod.coil_wire_variant("ni_clad")["state"] == "CONTINGENCY_NOT_TRIGGERED"
    assert mod.coil_wire_variant("kulgrid", "oxidation", {"measured_resistance": "r"})["state"] == \
        "CONTINGENCY_NOT_ADMISSIBLE_EVIDENCE_MISSING"
    assert mod.coil_wire_variant("ni_clad", "manufacturing", {"measured_resistance": "r",
                                                              "magnetic_perturbation": "m"})["state"] == \
        "CONTINGENCY_ADMISSIBLE"
    assert mod.coil_wire_variant("aluminium")["state"] == "NOT_IN_SPECIFICATION"


# ------------------------------------------------------------------------------------------- A9.15 propellant policy
def test_a915_system_xe_capability_both_configurations(mod, reqs, lines, doc):
    for lid in mod.SYSTEM_XE_LINES:
        li = lines[lid][1]
        assert "RFQ3-GAS-N03" in li["requirements"], lid
        for rid in li["requirements"]:
            if rid in ("RFQ-07-R01", "RFQ-07-R02", "RFQ-07-R04", "RFQ-07-R06", "RFQ-07-R05", "RFQ-07-R09"):
                assert "hall_icp_neutralizer" in reqs[rid]["applies_to"], (lid, rid)
    n03 = reqs["RFQ3-GAS-N03"]
    assert n03["applies_to"] == ["hall_c1_reference", "hall_icp_neutralizer"]
    assert "not a C1 contingency" in n03["requirement"]
    r27 = reqs["RFQ-07-R09"]["requirement"]
    assert "serves the ground comparison" not in r27 and "hall_icp_neutralizer" in r27
    for lid in mod.C1_XE_LINES:
        assert "selected C1" in lines[lid][1]["c1_xe_condition"]
    s01 = next(x for x in doc["common_interface"]["items"] if x["id"] == "CIF-S01")
    assert "RFP-required" in s01["value"]["Xe"]
    assert doc["rfp_propellant_policy"]["json_sha256"] == PINNED[doc["rfp_propellant_policy"]["decision"]]
    assert any(x["id"] == "NIR-07" for x in doc["not_in_this_revision"])


def test_a915_icp_gas_mode_baseline_unchanged(reqs, doc):
    r = reqs["RFQ-07-R07"]
    assert r["value"] == 0.0 and r["change_v3"]["type"] == "CARRIED_UNCHANGED"
    s02 = next(x for x in doc["common_interface"]["items"] if x["id"] == "CIF-S02")
    assert s02["change_v3"]["type"] == "CARRIED_UNCHANGED" and "G-REUSE primary" in s02["value"]


def test_a915_xe_capability_scope_rule(mod):
    for cfg in ("hall_c1_reference", "hall_icp_neutralizer"):
        out = mod.xe_capability_scope(cfg)
        assert out["system_xe_capability"] is True and out["c1_xe_lines"] == []
        assert out["system_xe_lines"] == mod.SYSTEM_XE_LINES
    assert mod.xe_capability_scope("hall_icp_neutralizer", c1_selected=True, c1_requires_xe=False)["c1_xe_lines"] == []
    out = mod.xe_capability_scope("hall_c1_reference", c1_selected=True, c1_requires_xe=True)
    assert out["c1_xe_lines"] == mod.C1_XE_LINES and "inside the system Xe architecture" in out["c1_xe_booking"]
    with pytest.raises(ValueError):
        mod.xe_capability_scope("xe_free")


def test_xa9q05_icp_xe_getter_is_engineering_requirement(mod, reqs, lines):
    assert "RFQ3-GAS-N04" in lines["GAS-O02"][1]["requirements"]
    assert "not a policy choice" in reqs["RFQ3-GAS-N04"]["requirement"]
    assert mod.icp_xe_getter_requirement(False)["state"] == "NOT_APPLICABLE_G_XE_VARIANT_NOT_DECLARED"
    assert mod.icp_xe_getter_requirement(True)["state"] == "NOT_INCLUDED_BY_DEFAULT_PENDING_ENGINEERING_SPEC"
    assert mod.icp_xe_getter_requirement(True, {"evidence": "spec-1", "demonstrates_need": True})["state"] == \
        "REQUIRED_BY_ENGINEERING_SPEC"
    assert mod.icp_xe_getter_requirement(True, {"evidence": "spec-1", "demonstrates_need": False})["state"] == \
        "NOT_REQUIRED_BY_ENGINEERING_SPEC"


# ------------------------------------------------------------------------------------------- guards
def test_p1_needed_lines_have_complete_quote_sheets(doc):
    for p in doc["packages"]:
        for li in p["line_items"]:
            qs = li["quote_sheet"]
            assert "purchase order NOT authorized" in qs["send_state"]
            if li["dispatch"] == "P1_NEEDED":
                assert qs["spec"] and qs["acceptance"] and qs["calibration_traceability"] and qs["documentation"]
                assert not any(x.startswith("package-level") for x in qs["acceptance"]), li["id"]


def test_quote_sheet_spec_matches_requirements(doc, reqs):
    for p in doc["packages"]:
        for li in p["line_items"]:
            assert [x["requirement"] for x in li["quote_sheet"]["spec"]] == \
                [reqs[r]["id"] for r in li["requirements"]], li["id"]
            for x in li["quote_sheet"]["spec"]:
                assert x["value"] == reqs[x["requirement"]]["value"]


def test_quote_sheet_replacement_fails_closed(mod):
    d = {"packages": [{"id": "RFQ3-X", "requirements": [{"id": "R1", "v1_id": None, "title": "t", "value": 1,
                                                          "units": "-", "freeze_point": "NOW", "status": "TBD"}],
                       "line_items": [{"id": "X-L01", "dispatch": "LATER", "requirements": ["R1"],
                                       "qs_replace_v3": {"text that is not there": "x"},
                                       "quote_sheet": {"acceptance": ["a"], "calibration_traceability": ["c"],
                                                       "documentation": ["d"]}}]}]}
    with pytest.raises(KeyError):
        mod._rebuild_quote_sheets(d)


def test_never_pass_no_prices_no_purchase_no_supplier_names(doc):
    text = JSON_PATH.read_text(encoding="utf-8")
    assert '"PASS"' not in text and ": PASS" not in text
    assert not re.search(r"(₹|\bINR\b|\bUSD\b|\$\s?\d)", text)
    assert "purchase order NOT authorized" in text
    st = doc["standing_facts"]["a9_2_statuses"]
    assert st["RF component ratings"] == "TBD_AFTER_IMPEDANCE_MAP"
    assert st["coupled H-1/ICP thermal closure"] == "UNRESOLVED" and st["final anode material"] == "OPEN"
    assert st["ICP electron-current capacity"] == "PENDING_ICP45"
    assert doc["compliance"]["no_supplier_contact"] is True and doc["compliance"]["no_supplier_names_invented"]
    for p in doc["packages"]:
        for r in p["requirements"]:
            assert r["status"] in doc["vocabulary"]["requirement_statuses"]
            assert r["freeze_point"] in doc["vocabulary"]["freeze_points"]
            assert r["dispatch"] in doc["vocabulary"]["dispatch_tags"]


def test_owner_supplied_numbers_only(reqs):
    # every number introduced by a v3-NEW requirement is one of the owner-supplied values
    allowed = {350.0, 525.0, 1050.0, 60.0, 700.0, 75.0, 1.0}
    for r in reqs.values():
        if r["change_v3"]["type"] != "NEW":
            continue
        nums = [float(x) for x in re.findall(r'(?<![\w.-])(\d+(?:\.\d+)?)(?![\w.])',
                                              json.dumps(r["value"], ensure_ascii=False))]
        for n in nums:
            # 17025 = ISO/IEC 17025 (standard id); 13.56 MHz (row 72); 0.6 / 0.8 provisional C1 region (owner)
            assert n in allowed or n in (17025.0, 13.56, 1.05, 0.6, 0.8), (r["id"], n)


# ------------------------------------------------------------------------------------------- A9.19 / A9.20
def test_a919_a920_c1_lines_ground_only_lab_equipment(mod, reqs, lines, doc):
    """A9.20: every C1 line (HE-L10/11/12 cathode / heater / keeper, C1 Xe branch, C1 getter option) is
    GROUND_ONLY_LAB_EQUIPMENT for the H-1 reference characterization (A9.10 S3.5) and the C1-vs-ICP bench control;
    A9.19: no flight C1 anywhere."""
    for lid in mod.C1_GROUND_LINES + mod.C1_XE_LINES + ["GAS-O03"]:
        li = lines[lid][1]
        assert li["equipment_class"] == "GROUND_ONLY_LAB_EQUIPMENT", lid
        keys = {(d["key"], d["id"]) for d in li["change_v3"]["decisions"]}
        assert ("A9.20", "answer") in keys, lid
        assert li["dispatch"] == "LATER", lid          # never pulled into the P1 dispatch-first set
    for lid in mod.C1_GROUND_LINES:
        g = lines[lid][1]["dispatch_gate"]
        assert "S3.5" in g["role"] and "bench control" in g["role"] and "never flight" in g["role"]
        assert g["flight"].startswith("NONE") and "RFQ3-HALLEL-N03" in lines[lid][1]["requirements"]
        assert "GROUND-ONLY" in lines[lid][1]["item"]
    for lid in mod.C1_XE_LINES:
        assert "never flight Xe" in lines[lid][1]["c1_xe_condition"]
    n03 = reqs["RFQ3-HALLEL-N03"]
    assert n03["value"]["equipment_class"] == "GROUND_ONLY_LAB_EQUIPMENT" and n03["value"]["flight"].startswith("NONE")
    assert n03["applies_to"] == ["hall_c1_reference"]
    assert mod.c1_equipment_class("HE-L11") == "GROUND_ONLY_LAB_EQUIPMENT"
    with pytest.raises(KeyError):
        mod.c1_equipment_class("GAS-L08")                # the system Xe tank is not a C1 line


def test_a919_no_flight_c1_wording_left(doc, reqs):
    """No live requirement / line / NIR / CIF text treats C1 as flight hardware, a flight fallback or a flight backup
    (history snapshots under before_*, change records and the carried A9.2 status are excluded)."""
    bad = re.compile(r"(only if C1 is chosen for flight|C1 control/fallback|reference/control/fallback|"
                     r"not co-installed as a flight backup|deferred until C1 is selected|mass on AL-C1|"
                     r"C1 stays CONTROL_FALLBACK)")

    def live(o):
        if isinstance(o, dict):
            return {k: live(v) for k, v in o.items() if not k.startswith("before") and k not in
                    ("sources", "change", "change_v3", "v2_line")}
        if isinstance(o, list):
            return [live(v) for v in o]
        return o
    for part in ("packages", "common_interface", "not_in_this_revision", "interface_demands", "instrument_coverage"):
        m = bad.search(json.dumps(live(doc[part]), ensure_ascii=False))
        assert not m, (part, m.group(0) if m else None)
    r09 = reqs["RFQ-07-R09"]["requirement"]
    assert "no conventional hollow cathode" in r09 and "contingency / emergency" in r09
    assert "flight backup" not in reqs["RFQ-07-R09"]["title"]
    nir = {x["id"]: x for x in doc["not_in_this_revision"]}["NIR-04"]
    assert "NONE" in nir["item"] and "A9.19" in nir["why"]


def test_a919_xe_contingency_role_capability_retained(mod, reqs, doc):
    """A9.19 amends A9.15 on the ROLE of Xe only: Xe = contingency / emergency supply mode; capability, separate tank /
    path and system Xe lines retained; the A9.1 ICP gas-mode baseline (G-REUSE primary) is unchanged."""
    n03 = reqs["RFQ3-GAS-N03"]
    assert n03["change_v3"]["type"] == "NEW"
    assert n03["value"]["xe_role"].startswith("CONTINGENCY_AND_EMERGENCY")
    assert n03["value"]["system_xe_lines"] == mod.SYSTEM_XE_LINES
    assert n03["value"]["c1_xe_lines_ground_only"] == mod.C1_XE_LINES
    assert "contingency / emergency supply mode" in n03["requirement"] and "not a C1 contingency" in n03["requirement"]
    assert n03["before_a9_19"]["requirement"] != n03["requirement"]
    pol = doc["rfp_propellant_policy"]["a9_19_xe_role"]
    assert pol["json_sha256"] == PINNED[pol["decision"]]
    md = mod._norm((REPO / pol["verbatim"]).read_text(encoding="utf-8"))
    assert all(mod._norm(q) in md for q in pol["owner_text"])
    roles = doc["vocabulary"]["configuration_roles_a9_19_20"]
    assert roles["hall_icp_neutralizer"].startswith("FLIGHT ARCHITECTURE")
    assert roles["hall_c1_reference"].startswith("GROUND_ONLY_LABORATORY_REFERENCE")
    assert reqs["RFQ-07-R07"]["value"] == 0.0                     # G-REUSE primary unchanged
    assert any("A9.19" in b and "no conventional hollow cathode" in b for b in doc["banner"])


def test_a919_a920_single_record_decisions_fail_closed(mod):
    with pytest.raises(KeyError):
        mod.OD("A9.19", "decisions", "One Hall accelerator.")
    with pytest.raises(ValueError):
        mod.OD("A9.20", "answer", "Remove C1 entirely and fly a hollow cathode.")
    assert mod.OD("A9.20", "answer", "Ground-only reference (Recommended)")["answer"] == \
        "C1_GROUND_ONLY_LABORATORY_REFERENCE"

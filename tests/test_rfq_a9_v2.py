"""Tests for the A9 RFQ packages v2 (fo_a9_rfq_v2_split, trigger T_A9_RFQ_V2_SPLIT).

Checks that docs/procurement/rfq_a9_v2/ is reproducible from its builder, that it is a revision of the immutable v1
packages (v1 pinned and unchanged; every v1 requirement carried exactly once with a change record), that the split follows
A9.3 OQ-RFQ-07 exactly (six owner families with the owner item lists verbatim as minimum scope, one common interface
document, dispatch statement in every header), that A9.2 / A9.3 are applied (local match, capability-range RF ratings,
protection features, dummy load, ground-only mains generator + power analyzer, Ar 1-2 ranges, dedicated-feed option line,
~1 kV isolators, 8.33 A stand ceiling), that every line is tagged P1_NEEDED or LATER, that owner quotes are verbatim, and
that no price, ranking, winner, PASS or Hall-performance source appears. A9.6 completion (fo_a9_6_rfq_completion): every
A9.6 sec. 13 owner item is covered, every P1_NEEDED line carries a ready-to-send quote sheet, and every id of the merged P1
measurement / hardware lists and the P2 instrument list maps to an RFQ line or an explicit not-procured disposition
(fail-closed). Run: python -m pytest -q tests/test_rfq_a9_v2.py
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
LANE = REPO / "docs" / "procurement" / "rfq_a9_v2"
SCRIPT = LANE / "build_rfq_a9_v2.py"
JSON_PATH = LANE / "rfq_a9_v2.json"
MD_PATH = LANE / "RFQ_A9_V2.md"
V1_JSON = REPO / "docs" / "procurement" / "rfq_a9" / "rfq_a9_v1.json"
ANS = REPO / "docs" / "decisions" / "OD_2026_09_29_owner_answers_147.json"
A91_MD = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md"
A92_JSON = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_2_a907_followup_owner_decisions.json"
A92_MD = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md"
A93_JSON = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json"
A93_MD = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md"

PINNED = {
    "docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json":
        "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03",
    "docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json":
        "81c69b200b9ce51f8aa745636d7aa4dbbddc39005b064235841722ebfdedad1b",
    "docs/decisions/OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md":
        "55a1fd84558a9590705bb82aa11db5e2b9136dd1d83a957d26614c435c707411",
    "docs/procurement/rfq_a9/rfq_a9_v1.json": "d2e654cf49d89b8f84a65e5bf7626517a37c02d0a4a0de97f128c3155ef4a84b",
    "docs/procurement/rfq_a9/RFQ_A9.md": "9d83c0f98f8365d8b758824382d6dea4d2f388ae0a10be2fa6367a252ef77334",
    "docs/procurement/rfq_a9/build_rfq_a9.py": "955862af1381dacabc0b1f22b5a51c182383c9b38ed6bb12359a9f93fed62bef",
    "docs/procurement/web_track_v1/source_register_v1.json":
        "e2661a49892b58271f25405ecbcc7d37cc22ba9a85d29fec83a0f72bdc10c77d",
}
FAMILIES = ["RF package", "Gas/metrology package", "Vacuum/facility package", "Hall electrical package",
            "Mechanical/ICP fabrication package", "Thrust/metrology package"]
GOVERNANCE = ("lane_registry_v1.json", "trigger_registry_v1.json", "trigger_ledger_v2.jsonl", "runtime_state.json",
              "fired_triggers.jsonl")
P1_JSON = REPO / "docs" / "experiments" / "hall_icp" / "p1_icp_bench" / "p1_icp_bench_v1.json"
P2_JSON = REPO / "docs" / "experiments" / "hall_icp" / "p2_impedance_map" / "p2_impedance_prep_v1.json"
PARALLEL = {"docs/experiments/hall_icp/p3_coupled_thermal/", "docs/experiments/hall_icp/p4_anode_materials/",
            "docs/budgets/mass_power_a9_v2/", "docs/budgets/xe_accounting_a9_v2/"}
A95_MD = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_5_P1_CLOSURE_OWNER_DECISIONS.md"
A96_MD = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def doc():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def reqs(doc):
    return [r for p in doc["packages"] for r in p["requirements"]]


@pytest.fixture(scope="module")
def req_by_v1(reqs):
    return {r["v1_id"]: r for r in reqs if r["v1_id"]}


@pytest.fixture(scope="module")
def req_by_id(reqs):
    return {r["id"]: r for r in reqs}


@pytest.fixture(scope="module")
def items(doc):
    return {li["id"]: li for p in doc["packages"] for li in p["line_items"]}


def _owner_items(heading: str) -> list:
    lines = A93_MD.read_text(encoding="utf-8").splitlines()
    i = lines.index("### " + heading)
    out = []
    for ln in lines[i + 1:]:
        if ln.startswith("#"):
            break
        if ln.startswith("- "):
            out.append(ln[2:].rstrip().rstrip(";").rstrip("."))
    return out


# ------------------------------------------------------------------------------------------------ reproducibility
def test_builder_check_reproduces_outputs():
    r = subprocess.run([sys.executable, str(SCRIPT), "--check"], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


def test_pinned_inputs_unchanged_and_v1_immutable(doc):
    for rel, sha in PINNED.items():
        assert _sha(REPO / rel) == sha, rel
    assert doc["revision_of"]["json_sha256"] == _sha(V1_JSON)
    pins = {p["path"]: p["sha256"] for p in doc["decision_pins"] + doc["deliverable_pins"]}
    pins.update({p["path"]: p["sha256"] for p in doc["historical_reuse"]["v1_pins"]})
    for rel, sha in pins.items():
        assert _sha(REPO / rel) == sha, rel
    for rel in pins:
        assert not any(g in rel for g in GOVERNANCE), rel


def test_identity_and_vocabulary(doc):
    assert doc["schema"] == "rfq_a9_v2"
    assert doc["follow_on"] == "fo_a9_rfq_v2_split" and doc["trigger"] == "T_A9_RFQ_V2_SPLIT"
    assert doc["configurations"] == ["hall_c1_reference", "hall_icp_neutralizer"]
    assert doc["outcome_vocabulary"] == ["hall_c1_reference", "hall_icp_neutralizer", "NO_VIABLE_CASE"]
    assert doc["a9_status"] == "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"
    assert doc["dispatch_tags"] == ["P1_NEEDED", "LATER"]


# ---------------------------------------------------------------------------------------------- revision of v1
def test_every_v1_requirement_carried_exactly_once(reqs):
    v1 = json.loads(V1_JSON.read_text(encoding="utf-8"))
    v1_ids = [r["id"] for p in v1["packages"] for r in p["requirements"]]
    carried = [r["v1_id"] for r in reqs if r["v1_id"]]
    assert sorted(carried) == sorted(v1_ids)
    assert len(carried) == len(set(carried))


def test_change_record_per_line(doc, reqs):
    v1 = {r["id"]: r for p in json.loads(V1_JSON.read_text(encoding="utf-8"))["packages"] for r in p["requirements"]}
    for r in reqs:
        ch = r["change"]
        assert ch["type"] in doc["change_types"], r["id"]
        assert ch["why"], r["id"]
        if r["v1_id"] is None:
            assert ch["type"] == "NEW"
            continue
        assert ch["type"] != "NEW"
        if ch["type"] == "CARRIED_UNCHANGED":
            for fld in ("requirement", "value", "status", "freeze_point"):
                assert r[fld] == v1[r["v1_id"]][fld], (r["id"], fld)
        if ch["type"] == "CARRIED_MODIFIED":
            assert ch.get("v1_snapshot") is not None or len(r["sources"]) > len(v1[r["v1_id"]]["sources"]) + 1
    per = {x["v2_id"] for x in doc["change_log"]["per_requirement"]}
    assert per == {r["id"] for r in reqs}
    assert {c["source"] for c in doc["change_log"]["package_level"]} >= {"A9.3 OQ-RFQ-07", "A9.3 OQ-RFQ-06",
                                                                          "A9.3 OQ-RFQ-02", "A9.3 OQ-RFQ-10"}


# ------------------------------------------------------------------------------------------------ split rules
def test_exactly_six_owner_families_plus_common_interface(doc):
    assert [p["owner_family"] for p in doc["packages"]] == FAMILIES
    assert doc["common_interface"]["id"] == "RFQ2-CIF"
    for p in doc["packages"]:
        assert (REPO / p["package_file"]).is_file()
    assert (REPO / doc["common_interface"]["package_file"]).is_file()


def test_owner_item_lists_verbatim_and_covered(doc):
    for p in doc["packages"]:
        expect = _owner_items(p["owner_family"])
        assert p["owner_minimum_scope_verbatim"] == expect
        for oi in expect:
            assert p["owner_minimum_scope_coverage"][oi], (p["id"], oi)
            for lid in p["owner_minimum_scope_coverage"][oi]:
                assert lid in [li["id"] for li in p["line_items"]]


def test_dispatch_statement_in_every_header(doc):
    must = ["DO NOT PURCHASE", "P9E/Vyovrinda", "Praveen's authorization", "No automatic supplier contact",
            "RFQ2-CIF"]
    for p in doc["packages"]:
        txt = " ".join(p["banner"])
        for m in must:
            assert m in txt, (p["id"], m)
        md = (REPO / p["package_file"]).read_text(encoding="utf-8")
        head = md[:3000]
        for m in must:
            assert m in head, (p["package_file"], m)
    cif_md = (REPO / doc["common_interface"]["package_file"]).read_text(encoding="utf-8")
    assert "Praveen's authorization" in cif_md[:3000]


def test_common_interface_contents(doc):
    c = doc["common_interface"]
    groups = {x["group"] for x in c["items"]}
    assert groups >= {"units", "reference_planes", "connectors_flanges", "potentials_grounding", "gas_species"}
    pk_ids = {p["id"] for p in doc["packages"]}
    covered = set()
    for x in c["interface_matrix"]:
        assert set(x["between"]) <= pk_ids and len(x["between"]) == 2
        assert x["dispatch"] in ("P1_NEEDED", "LATER")
        covered |= set(x["between"])
    assert covered == pk_ids
    for p in doc["packages"]:
        assert p["cif_interfaces"]
    assert c["source_quote"]["quote"] in A93_MD.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------ dispatch tagging (P1)
def test_every_line_tagged(doc, reqs):
    for r in reqs:
        assert r["dispatch"] in ("P1_NEEDED", "LATER"), r["id"]
    for p in doc["packages"]:
        for li in p["line_items"]:
            assert li["dispatch"] in ("P1_NEEDED", "LATER"), li["id"]


def test_p1_and_later_assignment(items):
    p1 = {"RF-L01", "RF-L02", "RF-L03", "RF-L04", "RF-L07", "RF-L08", "RF-L10", "RF-L11", "GAS-L01", "GAS-L12",
          "GAS-L13", "GAS-L14", "HE-L01", "HE-L03", "HE-L05", "TH-L04", "ME-L01", "ME-L02", "ME-L03", "ME-L05",
          "ME-L06", "VAC-L03", "VAC-L05", "HE-L15", "HE-L16", "HE-L17", "HE-L18", "RF-L12", "RF-L13", "RF-L14",
          "RF-L15", "RF-L16", "RF-L17", "RF-L18", "RF-L19", "GAS-L17", "TH-L09"}
    later = {"TH-L01", "TH-L02", "RF-L06", "GAS-L02", "GAS-L03", "GAS-L04", "GAS-L05", "GAS-L08", "GAS-O02",
             "HE-L06", "HE-L10", "HE-L11", "HE-L12"}
    for lid in p1:
        assert items[lid]["dispatch"] == "P1_NEEDED", lid
    for lid in later:
        assert items[lid]["dispatch"] == "LATER", lid


# ----------------------------------------------------------------------------------------------- A9.2 / A9.3
def test_rf_ratings_never_a_single_500W(req_by_v1, req_by_id, items):
    assert req_by_id["RFQ2-RF-N01"]["value"] == "TBD_AFTER_IMPEDANCE_MAP"
    r02 = req_by_v1["RFQ-04-R02"]
    assert "TBD_AFTER_IMPEDANCE_MAP" in r02["rating"] and "capability ranges" in r02["requirement"]
    for v1id in ("RFQ-04-R07", "RFQ-04-R12", "RFQ-04-R17"):
        assert "TBD_AFTER_IMPEDANCE_MAP" in json.dumps(req_by_v1[v1id]["value"]), v1id
        assert "never as a single 500 W rating" in req_by_v1[v1id]["requirement"], v1id
    assert "TBD_AFTER_IMPEDANCE_MAP" in items["RF-L08"]["item"]
    for rid, r in req_by_id.items():
        if r["package"] == "RFQ2-RF" and "rating" in r["title"].lower() and rid != "RFQ2-RF-R02":
            assert r["value"] != 500.0 and r["value"] != [0.0, 500.0], rid


def test_local_match_and_protection(req_by_v1, doc):
    assert "local match" in req_by_v1["RFQ-04-R06"]["value"]
    p = req_by_v1["RFQ-04-R16"]
    assert p["value"]["features"] == ["reflected-power monitoring", "mismatch/interlock threshold",
                                      "arc detection where feasible", "thermal monitoring",
                                      "automatic RF reduction/shutdown"]
    assert p["value"]["thresholds"].startswith("TBD") and p["threshold_freeze_point"] == "after-evidence"
    cif = {x["id"]: x for x in doc["common_interface"]["items"]}
    assert "LOCAL matching network" in cif["CIF-P03"]["value"]
    assert "50-ohm side" in cif["CIF-P02"]["value"]


def test_dummy_load_and_power_analyzer(items, req_by_id):
    assert "dummy load" in items["RF-L08"]["covers_owner_items"]
    assert "power analyzer" in items["RF-L11"]["item"] and items["RF-L11"]["dispatch"] == "P1_NEEDED"
    assert "never evidence for P_bus < 1.5 kW" in req_by_id["RFQ2-RF-N02"]["requirement"]


def test_mains_generator_ground_only_and_flight_rf_not_in_revision(req_by_v1, doc):
    r = req_by_v1["RFQ-04-R04"]
    assert "GROUND/FACILITY_ONLY" in r["requirement"] and r["status"] == "OWNER_GIVEN"
    nir = {x["id"]: x for x in doc["not_in_this_revision"]}
    assert "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE" in nir["NIR-01"]["item"]
    assert "not in this revision" in nir["NIR-01"]["why"]
    rf = [p for p in doc["packages"] if p["id"] == "RFQ2-RF"][0]
    assert rf["not_in_this_revision"][0]["id"] == "NIR-01"


def test_ar_mfc_one_or_two_not_four(items, req_by_v1, req_by_id):
    assert items["GAS-L01"]["qty"] == 1
    assert items["GAS-O01"]["option_line"] is True and items["GAS-O01"]["dispatch"] == "P1_NEEDED"
    for li in items.values():
        if "Ar " in li["item"] or li["item"].startswith("Ar"):
            assert li["qty"] != 4, li["id"]
    n1 = req_by_id["RFQ2-GAS-N01"]
    assert n1["value"]["anchor_sccm"] == 70.0 and n1["value"]["anchor_mgps_owner_stated"] == 2.1
    assert n1["value"]["sweep_bounds"].startswith("TBD") and "F2" in n1["value"]["sweep_bounds"]
    assert n1["freeze_point"] == "P1-G0"
    assert "ENGINEERING_ONLY_NON_SCORING" in n1["requirement"]
    assert req_by_id["RFQ2-GAS-N02"]["value"]["four_range_rule_for_Ar"] is False
    assert "rate-of-rise/transfer" in req_by_id["RFQ2-GAS-N03"]["requirement"]
    assert "NOT applied to the engineering-only Ar" in req_by_v1["RFQ-02-R02"]["requirement"]
    assert req_by_v1["RFQ-02-R02"]["value"] == 4


def test_ar_anchor_arithmetic(doc):
    chk = doc["derived"]["ar_anchor_check"]
    assert chk["value_mgps"] == round(70.0 * 7.436e-7 * 39.948 * 1000.0, 4)
    assert chk["consistent_with_owner_stated_2p1"] is True


def test_dedicated_feed_option_line_only(items, req_by_v1):
    li = items["GAS-O02"]
    assert li["option_line"] is True and li["dispatch"] == "LATER"
    r = req_by_v1["RFQ-02-R16"]
    assert r["option_line"] is True
    for s in ("G-REUSE", "capped ICP gas port remains", "atmospheric/Xe ledger", "NOT bought"):
        assert s in r["requirement"], s


def test_isolators_1kV_only_where_bridging(req_by_id):
    r = req_by_id["RFQ2-GAS-N04"]
    assert r["value"]["qualification_V_DC"] == 1000.0
    assert "same floating potential" in r["requirement"] and "flashover" in r["requirement"]
    h = req_by_id["RFQ2-GAS-N05"]
    assert h["value"] == {"continuous_V": 350.0, "qualification_V_DC": 1000.0}


def test_stand_ceiling_8p33A(doc, req_by_id, req_by_v1):
    ic = round(1500.0 / 180.0, 6)
    assert doc["derived"]["stand_ceiling_A"]["value"] == ic
    assert req_by_id["RFQ2-HALLEL-N01"]["value"] == ic
    assert "NOT an H-1 requirement" in req_by_id["RFQ2-HALLEL-N01"]["requirement"]
    assert req_by_id["RFQ2-VAC-N03"]["value"]["current_A_min_rating"] == ic
    assert req_by_id["RFQ2-THRUST-N01"]["value"]["current_range_A_min"] == ic
    c = req_by_v1["RFQ-05-R07"]
    assert c["package"] == "RFQ2-HALLEL" and c["value"]["current_capability_A_min"] == ic
    assert "PENDING" in c["value"]["icp45_requirement"]


def test_open_tube_coaxial_and_modular_carrier(req_by_id):
    assert req_by_id["RFQ2-MECH-N01"]["value"] == "OPEN_TUBE_COAXIAL_FIRST_BUILD"
    assert "ICP_ORIFICED_VARIANT" in req_by_id["RFQ2-MECH-N02"]["requirement"]


def test_never_pass_for_thermal_rf_ratings_anode(doc, reqs):
    for r in reqs:
        assert r["status"] != "PASS"
        assert not (isinstance(r["value"], str) and r["value"].strip().upper() == "PASS"), r["id"]
    txt = JSON_PATH.read_text(encoding="utf-8")
    for bad in ("THERMAL_PASS", "ICP_COUPLED_THERMAL = PASS", "\"RF component ratings\": \"PASS",
                "ANODE_BASELINE = 316L"):
        assert bad not in txt, bad
    st = doc["standing_facts"]["a9_2_statuses"]
    assert st["coupled H-1/ICP thermal closure"] == "UNRESOLVED"
    assert st["RF component ratings"] == "TBD_AFTER_IMPEDANCE_MAP"


# ------------------------------------------------------------------------------------------- evidence discipline
def test_owner_quotes_verbatim(reqs):
    ans = {a["row"]: a["owner_answer_verbatim"] for a in json.loads(ANS.read_text(encoding="utf-8"))["answers"]}
    a91 = A91_MD.read_text(encoding="utf-8")
    a92 = A92_MD.read_text(encoding="utf-8")
    a92d = json.loads(A92_JSON.read_text(encoding="utf-8"))["decisions"]
    a93 = A93_MD.read_text(encoding="utf-8")
    a93d = json.loads(A93_JSON.read_text(encoding="utf-8"))["decisions"]
    n = 0
    for r in reqs:
        for s in r["sources"]:
            if s["type"] == "owner_row":
                assert s["quote"] in ans[s["row"]], (r["id"], s["row"])
                n += 1
            elif s["type"] == "a9_1":
                assert s["quote"] in a91, (r["id"], s["id"])
            elif s["type"] == "a9_2":
                assert s["id"] in a92d
                if "quote" in s:
                    assert s["quote"] in a92, (r["id"], s["quote"])
            elif s["type"] == "a9_3":
                assert s["id"] in a93d and s["quote"] in a93, (r["id"], s["quote"])
    assert n > 50


def _resolve(d, pointer):
    cur = d
    for raw in pointer[1:].split("/") if pointer else []:
        tok = raw.replace("~1", "/").replace("~0", "~")
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


def test_new_deliverable_citations_resolve(reqs):
    cache = {}
    for r in reqs:
        for s in r["sources"]:
            if s["type"] == "deliverable_item" and "sha256" in s:
                if s["path"] not in cache:
                    cache[s["path"]] = json.loads((REPO / s["path"]).read_text(encoding="utf-8"))
                assert _resolve(cache[s["path"]], s["pointer"])["id"] == s["id"], (r["id"], s["id"])
            if s["type"] == "v1_requirement":
                v1 = cache.setdefault("v1", json.loads(V1_JSON.read_text(encoding="utf-8")))
                assert _resolve(v1, s["pointer"])["id"] == s["id"] == r["v1_id"]


def test_values_have_evidence_or_tbd(reqs, doc):
    for r in reqs:
        assert r["freeze_point"] in doc["freeze_points"], r["id"]
        assert r["status"] in doc["requirement_statuses"], r["id"]
        if r["evidence_class"] is None:
            v = json.dumps(r["value"])
            assert any(t in v for t in ("TBD", "PENDING", "UNRESOLVED")) or r["status"] in (
                "PROPOSED", "SUPERSEDED_NOT_QUOTED", "OWNER_GIVEN", "COPIED_VERIFIED"), r["id"]
        else:
            assert r["evidence_class"] in doc["evidence_classes"], r["id"]


def test_pending_parallel_lanes_never_filled(reqs, doc):
    n = 0
    for r in reqs:
        for s in r["sources"]:
            if s["type"] == "pending_lane":
                assert s["path"] in PARALLEL, s["path"]
                n += 1
    assert n >= 1
    assert set(v for k, v in doc["pending_parallel_lanes"].items() if k != "rule") == PARALLEL
    src = SCRIPT.read_text(encoding="utf-8")
    assert "open(_abs(PARALLEL_LANES" not in src and "load(PARALLEL_LANES" not in src


def test_no_prices_ranking_winner_or_prediction(doc):
    blobs = [JSON_PATH.read_text(encoding="utf-8"), MD_PATH.read_text(encoding="utf-8")]
    blobs += [(REPO / p["package_file"]).read_text(encoding="utf-8") for p in doc["packages"]]
    for txt in blobs:
        assert not re.search(r"(₹|\$\s?\d|\bUSD\s?\d|\bINR\s?\d|\bEUR\s?\d|\bRs\.?\s?\d)", txt)
        low = txt.lower()
        for bad in ("winner:", "best architecture", "recommended supplier", "preferred supplier", "sgb-screen",
                    "plasma_devices.py", "ensemble_member_id"):
            assert bad not in low, bad


def test_sections_present(doc):
    for k in ("interface_demands", "owner_answers_applied", "open_owner_questions", "historical_reuse", "m16_impact",
              "h3_h4_inputs", "traceability_matrix", "change_log", "p1_dispatch_first"):
        assert doc[k], k
    for q in doc["open_owner_questions"]["new"]:
        assert q["proposed_answer"] and q["needed_by"]
    for q in doc["open_owner_questions"]["carried_open_from_v1"]:
        assert q["state_v3_status"] == "OPEN"
    a93 = {x["id"] for x in doc["owner_answers_applied"]["a9_3"]}
    assert a93 == {"OQ-RFQ-07", "OQ-RFQ-06", "OQ-RFQ-02", "OQ-RFQ-10", "ICPQ-06", "OQ-A907-02", "OQ-VI-03",
                   "OQ-VI-05"}
    assert {m["m16_row"] for m in doc["m16_impact"]} >= {18, 19}


def test_builder_hygiene():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "xe" + "_ledger" not in src
    for m in re.findall(r"^(?:import|from) (\S+)", src, re.M):
        assert m in ("__future__", "argparse", "copy", "hashlib", "json", "os", "re", "sys"), m


def test_reference_data_rendered_with_url_access_date_and_datum(doc):
    """Regression (review): every carried reference entry shows its datum, URL and access date in the package."""
    reg = {x["id"]: x for x in json.loads((REPO / "docs/procurement/web_track_v1/source_register_v1.json")
                                          .read_text(encoding="utf-8"))["sources"]}
    n = 0
    for p in doc["packages"]:
        md = (REPO / p["package_file"]).read_text(encoding="utf-8")
        for x in p["reference_data"]:
            n += 1
            pv = x["provenance_display"]
            assert pv["url"] not in ("-", "", None) and pv["accessed"] not in ("-", "", None), x["source_id"]
            line = [ln for ln in md.splitlines() if ln.startswith(f"- {x['source_id']}: ")
                    and x["pointer"] in ln]
            assert len(line) == 1, x["source_id"]
            ln = line[0]
            assert f"URL {pv['url']};" in ln and f"accessed {pv['accessed']};" in ln
            assert json.dumps(x["datum"], ensure_ascii=False, sort_keys=True) in ln
            assert "- -: -" not in md
            for sid in [t.strip() for t in x["source_id"].split(";")]:
                assert sid in reg
                if x["url"] == "-":
                    assert pv["url"].startswith("http") or pv["url"].startswith("not recorded (non-web source")
                    assert reg[sid].get("accessed") in pv["accessed"]
    assert n == 17
    gas = (LANE / "packages" / "RFQ2-02_gas_metrology.md").read_text(encoding="utf-8")
    for v in ("1.9536", "<=3.5", "<0.974", "https://www.mt-aerospace.de/files/mta/tankkatalog/XS-XTA.pdf"):
        assert v in gas


def test_takahashi_anchor_locator_inline():
    gas = (LANE / "packages" / "RFQ2-02_gas_metrology.md").read_text(encoding="utf-8")
    assert "EVI:TK-31 (p. 3 text)" in gas


def test_cif_units_column_and_oq_rfq07_applied_everywhere(doc):
    cif = (LANE / "packages" / "RFQ2-00_common_interface.md").read_text(encoding="utf-8")
    row = [ln for ln in cif.splitlines() if ln.startswith("| CIF-E01 |")][0]
    assert "| A |" in row
    a = {x["id"]: x for x in doc["owner_answers_applied"]["a9_3"]}["OQ-RFQ-07"]
    assert {p["id"] for p in doc["packages"]} | {"RFQ2-CIF"} <= set(a["applied_in"])


# ------------------------------------------------------------------------------ A9.4 incorporation (fo_a9_4_incorporation)
A94_JSON = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_4_p1_p2_owner_decisions.json"
A94_MD = REPO / "docs" / "decisions" / "OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md"


def test_a94_pinned_and_quotes_verbatim(doc, reqs):
    pins = {p["path"]: p["sha256"] for p in doc["decision_pins"]}
    assert pins["docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json"] == _sha(A94_JSON) == \
        "b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d"
    assert pins["docs/decisions/OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md"] == _sha(A94_MD) == \
        "53cc026d63f85bd416f8ed8f4e8f9f7e7d7fc4429dccc45b86a51390b5c08b1c"
    md = A94_MD.read_text(encoding="utf-8")
    a94 = json.loads(A94_JSON.read_text(encoding="utf-8"))
    n = 0
    srcs = [s for r in reqs for s in r["sources"]] + doc["dispatch_authority"]["a9_4_quotation_dispatch"]["sources"]
    for s in srcs:
        if s["type"] == "a9_4":
            assert s["quote"] in md, s["quote"]
            assert s["id"] in a94["decisions"] or s["id"] in a94["execution_decisions"]
            n += 1
    assert n >= 15
    inc = doc["a9_4_incorporation"]
    assert inc["follow_on"] == "fo_a9_4_incorporation" and inc["base_commit"] == \
        "875ed6d0a87202bc92706b28551b0e22eda2014d"


def test_a94_photodiode_lines_p1_needed(items, req_by_id, doc):
    for lid in ("TH-L07", "TH-L08", "VAC-L07"):
        assert items[lid]["dispatch"] == "P1_NEEDED", lid
    assert "photodiode" in items["TH-L07"]["item"] and "amplifier" in items["TH-L07"]["item"]
    assert "DAQ channel" in items["TH-L08"]["item"]
    assert "window" in items["VAC-L07"]["item"]
    assert "RGA/diagnostic interfaces" in items["VAC-L07"]["covers_owner_items"]
    assert "DAQ" in items["TH-L07"]["covers_owner_items"]
    n3 = req_by_id["RFQ2-THRUST-N03"]
    assert n3["dispatch"] == "P1_NEEDED" and n3["status"] == "OWNER_GIVEN"
    assert "No photodiode threshold is requested" in n3["requirement"]
    assert req_by_id["RFQ2-VAC-N06"]["dispatch"] == "P1_NEEDED"
    assert "RFQ2-THRUST-N03" in req_by_id["RFQ2-THRUST-N01"]["requirement"]
    assert "RFQ2-THRUST" in doc["a9_4_incorporation"]["placement"]
    assert "RFQ2-VAC" in doc["a9_4_incorporation"]["placement"]
    assert any(x["id"] == "X-17" for x in doc["common_interface"]["interface_matrix"])


def test_a94_dwv_and_design_withstand(items, req_by_id, doc):
    h = req_by_id["RFQ2-HALLEL-N04"]
    assert h["value"]["V_operating_max_V"] == 350.0 and h["value"]["V_design_withstand_min_V"] == 525.0
    assert h["value"]["initial_DWV_V_DC"] == 1050.0 and h["value"]["initial_DWV_duration_s"] == 60.0
    assert h["value"]["ICP_44_rf_insulation"] == "OPEN" and h["value"]["leakage_acceptance"].startswith("TBD")
    assert "verify" in h["requirement"] and "ICPQ-06" in h["requirement"]
    v = req_by_id["RFQ2-VAC-N07"]
    assert v["value"]["V_design_withstand_min_V"] == 525.0 and v["value"]["DWV_V_DC"] == 1050.0
    assert "RFQ2-HALLEL-N04" in items["HE-L04"]["requirements"] and "1.05 kV" in items["HE-L04"]["item"]
    assert "RFQ2-VAC-N07" in items["VAC-L03"]["requirements"] and "525 V" in items["VAC-L03"]["item"]
    cif = {x["id"]: x for x in doc["common_interface"]["items"]}
    assert cif["CIF-G07"]["value"]["initial_DWV_V_DC"] == 1050.0
    assert cif["CIF-G05"]["value"]["qualification_V_DC"] == 1000.0          # ICPQ-06 gas-line rule kept distinct


def test_a94_quotation_dispatch_authorized_not_po(doc):
    qd = doc["dispatch_authority"]["a9_4_quotation_dispatch"]
    assert qd["authorized"] == ["requests for quotation", "technical clarification", "indicative lead time",
                                "commercial quotation", "datasheets/certificates"]
    assert qd["not_authorized"] == ["purchase orders", "advance payments", "binding commitments"]
    assert "never contacts suppliers" in qd["sent_by"]
    for p in doc["packages"]:
        txt = " ".join(p["banner"])
        assert "DO NOT PURCHASE" in txt and "may SEND the lines tagged P1_NEEDED" in txt
        assert "NOT authorized: purchase orders, advance payments, binding commitments" in txt
    assert "PURCHASE ORDERS, ADVANCE PAYMENTS AND BINDING COMMITMENTS NOT AUTHORIZED" in \
        doc["h3_h4_inputs"]["h3_procurement_gate"]["state"]


def test_a94_change_log_traceability_and_answers(doc):
    srcs = {c["source"] for c in doc["change_log"]["package_level"]}
    assert {"A9.4 P2Q-05", "A9.4 P1Q-14", "A9.4 execution_decisions.p1_needed_rfqs"} <= srcs
    trace = {t["requirement"]: t for t in doc["traceability_matrix"]}
    assert "A9.4 P2Q-05" in trace["RFQ2-THRUST-N03"]["sources"]
    assert "A9.4 P1Q-14" in trace["RFQ2-HALLEL-N04"]["sources"]
    a94 = {x["id"]: x for x in doc["owner_answers_applied"]["a9_4"]}
    assert {"P2Q-05", "P1Q-14", "p1_needed_rfqs"} <= set(a94)
    assert "RFQ2-THRUST-N03" in a94["P2Q-05"]["applied_in"] and "RFQ2-HALLEL-N04" in a94["P1Q-14"]["applied_in"]
    new = {q["id"] for q in doc["open_owner_questions"]["new"]}
    assert {"OQ-RFQV2-06", "OQ-RFQV2-08"} <= new
    closed = {q["id"] for q in doc["open_owner_questions"]["closed_since_previous_revision"]}
    assert "OQ-RFQV2-07" in closed and "OQ-RFQV2-07" not in new


# ------------------------------------------------------------------ A9.6 RFQ completion (fo_a9_6_rfq_completion)
def _builder():
    spec = importlib.util.spec_from_file_location("build_rfq_a9_v2_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _p1():
    return json.loads(P1_JSON.read_text(encoding="utf-8"))


def _p2():
    return json.loads(P2_JSON.read_text(encoding="utf-8"))


def test_a96_a95_pinned_and_quotes_verbatim(doc, reqs):
    pins = {p["path"]: p["sha256"] for p in doc["decision_pins"]}
    for rel in ("docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json",
                "docs/decisions/OD_2026_09_30_A9_5_P1_CLOSURE_OWNER_DECISIONS.md",
                "docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json",
                "docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md"):
        assert pins[rel] == _sha(REPO / rel), rel
    a95 = A95_MD.read_text(encoding="utf-8")
    a96 = A96_MD.read_text(encoding="utf-8")
    n5 = n6 = 0
    srcs = [s for r in reqs for s in r["sources"]]
    c6 = doc["a9_6_completion"]
    srcs += [c6["rfq_only_quote"], c6["ready_to_send_quote"], c6["p1_later_quote"]]
    for s in srcs:
        if s["type"] == "a9_5":
            assert s["quote"] in a95, s["quote"]
            n5 += 1
        elif s["type"] == "a9_6":
            assert s["quote"] in a96, s["quote"]
            n6 += 1
    assert n5 >= 8 and n6 >= 10
    assert c6["rfq_only_quote"]["quote"] == "RFQ only — no purchase order authorization"
    assert c6["follow_on"] == "fo_a9_6_rfq_completion"


def test_rfq_only_banner_and_no_supplier_contact(doc):
    for p in doc["packages"]:
        txt = " ".join(p["banner"])
        assert "RFQ only - no purchase order authorization" in txt
        assert "Claude never contacts suppliers" in txt
        md = (REPO / p["package_file"]).read_text(encoding="utf-8")
        assert "RFQ only - no purchase order authorization" in md[:4000]
        for li in p["line_items"]:
            assert "purchase order NOT authorized" in li["quote_sheet"]["send_state"], li["id"]


def test_a96_sec13_owner_items_all_covered(doc, items):
    lines = A96_MD.read_text(encoding="utf-8").splitlines()
    i = lines.index("Include:", lines.index("13. Complete RFQ packages"))
    owner = []
    for ln in lines[i + 1:]:
        if ln.startswith("Keep:"):
            break
        if ln.startswith("* "):
            owner.append(ln[2:].rstrip().rstrip(";").rstrip("."))
    assert len(owner) == 13
    cov = {x["owner_item"]: x for x in doc["a9_6_sec13_coverage"]}
    assert sorted(cov) == sorted(owner)
    for it in owner:
        assert cov[it]["lines"], it
        for y in cov[it]["lines"]:
            assert y["line"] in items and items[y["line"]]["dispatch"] == y["dispatch"]
        assert cov[it]["p1_needed_present"], it


def test_p1_needed_lines_have_ready_to_send_quote_sheets(doc, reqs):
    known = {r["id"] for r in reqs} | {r["v1_id"] for r in reqs if r["v1_id"]}
    n = 0
    for p in doc["packages"]:
        for li in p["line_items"]:
            qs = li["quote_sheet"]
            for sp in qs["spec"]:
                assert sp["requirement"] in known and sp["freeze_point"] in doc["freeze_points"]
            if li["dispatch"] != "P1_NEEDED":
                continue
            n += 1
            assert qs["spec"], li["id"]
            assert qs["freeze_gate"] in doc["freeze_points"], li["id"]
            order = doc["freeze_points"]
            assert qs["freeze_gate"] == max((sp["freeze_point"] for sp in qs["spec"]), key=order.index)
            for fld in ("acceptance", "calibration_traceability", "documentation"):
                assert qs[fld] and all(x.strip() for x in qs[fld]), (li["id"], fld)
                assert not any(x.startswith("package-level") for x in qs[fld]), (li["id"], fld)
            assert qs["send_state"].startswith("READY_TO_SEND_FOR_QUOTATION")
            md = (REPO / p["package_file"]).read_text(encoding="utf-8")
            assert f"### {li['id']} - " in md, li["id"]
    assert n >= 50


def test_owner_named_lines_present(items, req_by_id, doc):
    assert "GROUND/FACILITY_ONLY" in items["RF-L01"]["item"] and items["RF-L01"]["dispatch"] == "P1_NEEDED"
    assert "power analyzer" in items["RF-L11"]["item"]
    nir = {x["id"]: x for x in doc["not_in_this_revision"]}
    assert "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE" in nir["NIR-01"]["item"]
    assert "directional coupler" in items["RF-L02"]["item"] and "power sensors" in items["RF-L03"]["item"]
    assert "local matching" in items["RF-L04"]["item"]
    for lid, word in (("RF-L12", "V/I probe"), ("RF-L13", "vector network analyser"), ("RF-L14", "calibration kits"),
                      ("RF-L16", "antenna-simulator dummy load"), ("RF-L08", "dummy load"),
                      ("RF-L07", "feedthrough"), ("RF-L05", "coax"), ("TH-L07", "photodiode"), ("VAC-L07", "window"),
                      ("TH-L08", "DAQ channel"), ("HE-L15", "single-point metered ground-current monitor"),
                      ("HE-L16", "high-impedance isolated V_anode"), ("HE-L17", "physical disconnect"),
                      ("ME-L07", "capped dedicated gas port"), ("ME-L05", "ICP_ORIFICED_VARIANT"),
                      ("ME-L01", "open-tube coaxial"), ("GAS-L05", "C1 steady-flow Xe controller"),
                      ("GAS-L06", "C1 start/diode-flow Xe controller"), ("GAS-L17", "calibration volume"),
                      ("TH-L09", "calibration services")):
        assert word in items[lid]["item"], (lid, word)
    assert items["GAS-L01"]["qty"] == 1 and items["GAS-O01"]["option_line"] is True
    assert items["GAS-L02"]["qty"] == 4 and items["GAS-L03"]["qty"] == 4
    h3 = items["HE-L03"]
    assert "525 V" in h3["item"] and "8.33 A" in h3["item"] and "RFQ2-HALLEL-N05" in h3["requirements"]
    n5 = req_by_id["RFQ2-HALLEL-N05"]["value"]
    assert n5["V_operating_class_V"] == 350.0 and n5["V_design_withstand_min_V"] == 525.0
    assert n5["current_capability_A_min"] == round(1500.0 / 180.0, 6) and n5["initial_DWV"]["V_DC"] == 1050.0
    assert n5["bias_voltage_range"].startswith("TBD")
    assert items["HE-O02"]["option_line"] is True and "TBD_OWNER" in json.dumps(req_by_id["RFQ2-HALLEL-N09"]["value"])
    assert items["ME-O01"]["option_line"] is True


def test_p1q13_lines_and_closure_metrology(req_by_id, doc):
    n6 = req_by_id["RFQ2-HALLEL-N06"]
    assert n6["dispatch"] == "P1_NEEDED" and "ONLY deliberate" in n6["requirement"]
    assert n6["value"]["range_resolution"].startswith("TBD")
    n7 = req_by_id["RFQ2-HALLEL-N07"]
    assert "PHYSICALLY disconnect" in n7["requirement"] and "high-impedance" in n7["requirement"]
    assert n7["value"]["voltage_class"]["margin"].startswith("TBD_OWNER")
    n8 = req_by_id["RFQ2-HALLEL-N08"]["value"]
    assert n8["per_channel_supplier_states"][:4] == ["calibration uncertainty", "zero/offset uncertainty",
                                                     "resolution", "repeatability where applicable"]
    assert n8["I_scale_min"].startswith("TBD") and n8["closure_rule_context"]["fractional"] == 0.02
    assert n8["closure_rule_context"]["inadequate_instrument"] == "NOT_EVALUATED_INSTRUMENT"
    cif = {x["id"]: x for x in doc["common_interface"]["items"]}
    assert "INTO the defined isolated electrical network is positive" in cif["CIF-E03"]["value"]
    assert {"X-18", "X-19", "X-20"} <= {x["id"] for x in doc["common_interface"]["interface_matrix"]}


def test_p2_metrology_placement_tbd_owner(items):
    for lid in ("RF-L12", "RF-L13", "RF-L14", "RF-L15", "RF-L16", "RF-L17", "RF-L18", "RF-L19", "RF-O01"):
        pl = items[lid]["placement"]
        assert pl["status"] == "TBD_OWNER" and pl["question"].startswith("P2Q-02"), lid
        assert len(pl["alternatives"]) == 2


def test_p2_specs_copied_verbatim(req_by_id, doc):
    p2 = {x["id"]: x for x in _p2()["instrument_list"]}
    b = _builder()
    for iid, rid, lines in b.P2_REQ_MAP:
        r = req_by_id[rid]
        assert r["value"]["p2_required_specs_copied"] == p2[iid]["required_specs"], rid
        assert r["dispatch"] == "P1_NEEDED" and r["freeze_point"] == p2[iid]["freeze_point"]
        cur = [s for s in r["sources"] if s["type"] == "current_deliverable"]
        assert cur and cur[0]["id"] == iid and cur[0]["pinned"] is False


def test_current_deliverable_citations_resolve(reqs):
    docs_ = {"P1": _p1(), "P2": _p2()}
    n = 0
    for r in reqs:
        for s in r["sources"]:
            if s["type"] == "current_deliverable":
                assert _resolve(docs_[s["key"]], s["pointer"])["id"] == s["id"], (r["id"], s["id"])
                n += 1
    assert n >= 40


def test_instrument_coverage_complete_against_merged_p1_p2(doc, items):
    """Coverage cross-check read directly from the merged P1 / P2 files (not from the builder's own maps)."""
    ic = doc["instrument_coverage"]
    p1, p2 = _p1(), _p2()
    src = {"p1_measurements": {m["id"]: m for m in p1["measurements"]},
           "p1_hardware": {m["id"]: m for m in p1["hardware_readiness"]},
           "p2_instruments": {m["id"]: m for m in p2["instrument_list"]}}
    for sec, ids in src.items():
        rows = {r["id"]: r for r in ic[sec]}
        assert set(rows) == set(ids), sec
        for iid, row in rows.items():
            if row["disposition"] == "RFQ_LINE":
                assert row["rfq_lines"], iid
                for y in row["rfq_lines"]:
                    assert y["line"] in items and items[y["line"]]["dispatch"] == y["dispatch"], (iid, y)
            else:
                assert row["disposition"] in ic["not_procured_dispositions"], iid
                assert not row["rfq_lines"]
        if sec == "p1_measurements":
            for iid, m in ids.items():
                if str(m["status"]).startswith("REQUIRED") and rows[iid]["disposition"] == "RFQ_LINE":
                    assert any(y["dispatch"] == "P1_NEEDED" for y in rows[iid]["rfq_lines"]), iid
        if sec == "p2_instruments":
            for iid in ids:
                assert any(y["dispatch"] == "P1_NEEDED" for y in rows[iid]["rfq_lines"]), iid
    for k, v in ic["not_procured_dispositions"].items():
        assert v["why"] and v["disposition"]
    assert all(not i["pinned"] for i in ic["inputs"])


def test_instrument_coverage_fails_closed(doc):
    pkgs = doc["packages"]
    _builder().instrument_coverage(copy.deepcopy(pkgs))              # reproduces without error
    b = _builder()
    del b.P1_MEAS_COVERAGE["P1-M-29"]                                # unmapped P1 id
    with pytest.raises(KeyError):
        b.instrument_coverage(copy.deepcopy(pkgs))
    b = _builder()
    b.P1_MEAS_COVERAGE["P1-M-29"] = ["TH-L01"]                       # REQUIRED measurement on a LATER-only line
    with pytest.raises(ValueError):
        b.instrument_coverage(copy.deepcopy(pkgs))
    b = _builder()
    b.P1_MEAS_COVERAGE["P1-M-99"] = ["HE-L15"]                       # stale id absent from the merged P1 package
    with pytest.raises(KeyError):
        b.instrument_coverage(copy.deepcopy(pkgs))
    b = _builder()
    b.P2_INS_COVERAGE["INS-P2-04"] = ["RF-L99"]                      # unknown RFQ line
    with pytest.raises(KeyError):
        b.instrument_coverage(copy.deepcopy(pkgs))
    b = _builder()
    b.P2_INS_COVERAGE["INS-P2-04"] = ["RF-L06"]                      # P2 prep instrument on a LATER-only line
    with pytest.raises(ValueError):
        b.instrument_coverage(copy.deepcopy(pkgs))


def test_cur_lookup_fails_closed():
    b = _builder()
    assert b.CUR("P2", "INS-P2-11")["pointer"].startswith("/instrument_list/")
    with pytest.raises(KeyError):
        b.CUR("P1", "P1-M-999")
    with pytest.raises(KeyError):
        b.CUR("P2", "NOT-AN-ID")
    with pytest.raises(ValueError):
        b.PEND("docs/experiments/hall_icp/p1_icp_bench/", "merged lane is not a parallel lane")


def test_quote_sheet_builder_refuses_incomplete_p1_line(monkeypatch):
    b = _builder()
    reqs = b.carried_requirements() + b.new_requirements() + b.a96_requirements()
    qa = dict(b.LINE_QA)
    del qa["HE-L15"]
    monkeypatch.setattr(b, "LINE_QA", qa)
    with pytest.raises(ValueError):
        b.attach_quote_sheets(b.line_items(), reqs)


def test_no_stale_pending_lane_references(doc):
    """A9.6 sec. 3 cleanup: no 'PENDING <merged P1 / P2 lane>' marker outside verbatim-copied P2 specification rows."""
    stale = ("PENDING docs/experiments/hall_icp/p1_icp_bench", "PENDING docs/experiments/hall_icp/p2_impedance_map",
             "PENDING P1", "PENDING P2")
    bad = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "p2_required_specs_copied":
                    continue
                walk(v, path + "/" + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + "/" + str(i))
        elif isinstance(o, str) and any(t in o for t in stale):
            bad.append(path)
    walk(doc, "")
    assert not bad, bad[:5]
    for p in doc["packages"]:
        if p["id"] == "RFQ2-RF":
            continue                        # renders the verbatim-copied P2 rows
        md = (REPO / p["package_file"]).read_text(encoding="utf-8")
        assert not any(t in md for t in stale), p["id"]
    for f in (MD_PATH, REPO / doc["common_interface"]["package_file"]):
        assert not any(t in f.read_text(encoding="utf-8") for t in stale), f


def test_rga_retag_and_open_questions(items, req_by_v1, doc):
    assert items["VAC-L05"]["dispatch"] == "P1_NEEDED" and items["VAC-L05"]["change"]["type"] == "CARRIED_MODIFIED"
    for i in range(1, 8):
        assert req_by_v1[f"RFQ-03-R{i:02d}"]["dispatch"] == "P1_NEEDED"
    p1m = {m["id"]: m for m in _p1()["measurements"]}
    assert p1m["P1-M-20"]["status"].startswith("REQUIRED")
    assert "CL-19" in {c["id"] for c in doc["change_log"]["package_level"]}
    oq = doc["open_owner_questions"]
    new = {q["id"] for q in oq["new"]}
    assert {"OQ-RFQV2-09", "OQ-RFQV2-10"} <= new
    lane = {q["id"] for q in oq["carried_open_from_lanes"]}
    assert {"P2Q-02", "P2Q-07"} <= lane
    nir = {x["id"] for x in doc["not_in_this_revision"]}
    assert "NIR-06" in nir
    for q in oq["new"]:
        assert "owner call" in q["proposed_answer"] or q["proposed_answer"].startswith("YES") or \
            q["proposed_answer"].startswith("maker") or q["proposed_answer"].startswith("allowed"), q["id"]


def test_a96_sections_and_statuses(doc):
    oa = doc["owner_answers_applied"]
    assert {x["id"] for x in oa["a9_5"]} == {"P1Q-15", "P1Q-16"}
    assert "sec. 13" in {x["id"] for x in oa["a9_6"]}
    a94 = {x["id"] for x in oa["a9_4"]}
    assert {"P1Q-13", "P1Q-10"} <= a94
    st = doc["standing_facts"]["a9_2_statuses"]
    assert "PASS" not in json.dumps(st)
    assert {c["id"] for c in doc["change_log"]["package_level"]} >= {f"CL-{i}" for i in range(15, 23)}
    for k in ("instrument_coverage", "a9_6_sec13_coverage", "a9_6_completion", "merged_lanes_read"):
        assert doc[k], k

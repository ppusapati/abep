"""Tests for the A9 RFQ packages v2 (fo_a9_rfq_v2_split, trigger T_A9_RFQ_V2_SPLIT).

Checks that docs/procurement/rfq_a9_v2/ is reproducible from its builder, that it is a revision of the immutable v1
packages (v1 pinned and unchanged; every v1 requirement carried exactly once with a change record), that the split follows
A9.3 OQ-RFQ-07 exactly (six owner families with the owner item lists verbatim as minimum scope, one common interface
document, dispatch statement in every header), that A9.2 / A9.3 are applied (local match, capability-range RF ratings,
protection features, dummy load, ground-only mains generator + power analyzer, Ar 1-2 ranges, dedicated-feed option line,
~1 kV isolators, 8.33 A stand ceiling), that every line is tagged P1_NEEDED or LATER, that owner quotes are verbatim, and
that no price, ranking, winner, PASS or Hall-performance source appears. Run: python -m pytest -q tests/test_rfq_a9_v2.py
"""
from __future__ import annotations

import hashlib
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
}
FAMILIES = ["RF package", "Gas/metrology package", "Vacuum/facility package", "Hall electrical package",
            "Mechanical/ICP fabrication package", "Thrust/metrology package"]
GOVERNANCE = ("lane_registry_v1.json", "trigger_registry_v1.json", "trigger_ledger_v2.jsonl", "runtime_state.json",
              "fired_triggers.jsonl")
P1_LANE = "docs/experiments/hall_icp/p1_icp_bench/"


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
          "ME-L06", "VAC-L03"}
    later = {"TH-L01", "TH-L02", "RF-L06", "GAS-L02", "GAS-L03", "GAS-L04", "GAS-L05", "GAS-L08", "GAS-O02",
             "HE-L06", "HE-L10", "VAC-L05"}
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
    assert n1["value"]["sweep_bounds"].startswith("PENDING " + P1_LANE)
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


def test_pending_parallel_lanes_never_filled(reqs):
    for r in reqs:
        for s in r["sources"]:
            if s["type"] == "pending_lane":
                assert s["path"] in (P1_LANE, "docs/experiments/hall_icp/p2_impedance_map/")
    src = SCRIPT.read_text(encoding="utf-8")
    assert "open(_abs(P1_LANE" not in src and "open(_abs(P2_LANE" not in src


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
        assert m in ("__future__", "argparse", "copy", "hashlib", "json", "os", "sys"), m

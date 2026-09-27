"""Checks for the D-X5 closed-access acquisition list (fo_closed_access_acquisition)."""
import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ACQ = os.path.join(ROOT, "docs", "chemistry", "n2_domain_extension", "dx5", "acquisition")
LIST = os.path.join(ACQ, "acquisition_list_v1.json")
DOSSIER = os.path.join(ROOT, "docs", "chemistry", "n2_domain_extension", "dx5", "dx5_evidence_v1.json")

SHADOW = re.compile(r"sci-?hub|libgen|library\.?genesis|gen\.lib\.rus|z-?lib|zlibrary|singlelogin|annas-?archive|booksc\.|"
                    r"\b1lib\.|\bb-ok\.|libstc|\bnexus\.|bookfi|ebookee", re.I)
# The fourteen works the task names (verified against the dossier below).
NAMED = {"kutz_meyer_1995", "gote_ehrhardt_1995", "bhattacharyya_goswami_1982", "choi_poe_sun_shan_1979",
         "itikawa_mason_2005", "itikawa2006", "oda_osawa1981", "fons1996", "chung_lin1972", "holland1969",
         "skerbele_lassettre1970", "kawaguchi2021", "middleton1992", "truhlar1977"}


@pytest.fixture(scope="module")
def acq():
    with open(LIST, encoding="utf-8") as fh:
        return json.load(fh)


def _builder():
    spec = importlib.util.spec_from_file_location("build_acq", os.path.join(ACQ, "build_acquisition_list.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rebuild_is_deterministic_and_matches_committed():
    mod = _builder()
    d = mod.build()
    with open(LIST, encoding="utf-8") as fh:
        assert fh.read() == json.dumps(d, indent=1, ensure_ascii=False) + "\n"
    with open(os.path.join(ACQ, "ACQUISITION_LIST.md"), encoding="utf-8") as fh:
        assert fh.read() == mod.render_md(d)


def test_covers_exactly_the_dossier_candidates(acq):
    with open(DOSSIER, encoding="utf-8") as fh:
        dossier = json.load(fh)
    cand = set()
    for g in ("P1", "P2", "P3"):
        cand |= set(dossier["priorities"][g]["legitimate_access_candidates_owner_decision"])
    covered = [i for w in acq["works"] for i in w["dossier_ids"]]
    assert sorted(covered) == sorted(cand)
    assert {w["work_key"] for w in acq["works"]} == NAMED


def test_every_entry_has_doi_route_gap_priority_price(acq):
    works = acq["works"]
    assert [w["priority"] for w in works] == list(range(1, len(works) + 1))
    assert acq["priority_order"] == [w["work_key"] for w in works]
    for w in works:
        assert re.fullmatch(r"10\.\d{4,9}/\S+", w["doi"]), w["work_key"]
        assert w["doi_url"] == "https://doi.org/" + w["doi"]
        assert "api.crossref.org" in w["doi_resolved_via"]
        assert w["citation"] and w["publisher"]
        kinds = {r["route"] for r in w["access_routes"]}
        assert {"publisher_purchase", "institutional_subscription", "document_delivery",
                "author_deposited_open_version"} <= kinds
        assert all(r["detail"] for r in w["access_routes"])
        assert w["gaps"] and set(w["gaps"]) <= {"P1", "P2", "P3"}
        assert w["price_per_article"]
        for t in w["targets"]:
            assert t["tables"] and t["data_sought"] and t["evidence_class"]
            assert t["gap"] in w["gaps"]


def test_no_shadow_library_urls_anywhere():
    for name in os.listdir(ACQ):
        path = os.path.join(ACQ, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for url in re.findall(r"https?://[^\s\"'<>)]+", text):
                assert not SHADOW.search(url), (name, url)


def test_status_milestones_and_proposed_rubric(acq):
    assert acq["status"] == "DRAFT_PENDING_OWNER"
    assert acq["milestones"]["supports"] and acq["milestones"]["next_milestone_needs"]
    assert acq["rubric"]["status"].startswith("PROPOSED")
    assert acq["owner_disposition"]["dx5_closed_access_sources"].startswith("APPROVED")
    assert "DEFERRED" in acq["owner_disposition"]["dx5_p4_dissociation"]
    assert all(w["gaps"] != ["P4"] for w in acq["works"])

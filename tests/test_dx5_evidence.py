"""Consistency tests for the D-X5 evidence dossier (docs/chemistry/n2_domain_extension/dx5/, DRAFT_PENDING_OWNER).

Non-gating documentation checks: the JSON and Markdown reproduce from the committed source list; every source carries an
access label and an evidence class; no rejected or unconfirmed record is used; every priority has a status; the reopening
section decides nothing; LXCat is never cited; every quoted lane-01 field resolves to its file.
"""
import importlib.util, json, os, re

ROOT = os.path.join(os.path.dirname(__file__), "..")
DX5 = os.path.join(ROOT, "docs", "chemistry", "n2_domain_extension", "dx5")
EVID = os.path.join(DX5, "dx5_evidence_v1.json")
SRC = os.path.join(DX5, "dx5_sources_v1.json")
MD = os.path.join(DX5, "DX5_EVIDENCE.md")
SCRIPT = os.path.join(DX5, "build_dx5_evidence.py")
NEGATION = ("not", "no ", "non-", "never", "exclu", "without")
DECISION_PHRASES = ("condition is met", "condition is not met", "condition has been met", "condition was met",
                    "should be reopened", "should not be reopened", "reopen question a now", "we recommend", "recommendation:",
                    "is hereby", "decided: ", "decision: reopen", "a-yes", "a-partial")


def _load_script():
    spec = importlib.util.spec_from_file_location("build_dx5_evidence", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ev():
    return json.load(open(EVID))


def _strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, str):
        yield obj


def test_json_and_md_reproduce_from_committed_source_list():
    mod = _load_script()
    d = mod.build()
    assert open(EVID).read() == mod.dumps(d), "dx5_evidence_v1.json does not reproduce (run build_dx5_evidence.py)"
    assert open(MD).read() == mod.render_md(d), "DX5_EVIDENCE.md does not reproduce (run build_dx5_evidence.py)"
    assert mod.main(["--check"]) == 0


def test_inputs_hashes_match_committed_files():
    import hashlib
    ev = _ev()
    for rel, h in ev["inputs_sha256"].items():
        assert hashlib.sha256(open(os.path.join(ROOT, rel), "rb").read()).hexdigest() == h, rel


def test_dossier_is_draft_non_gating_and_changes_nothing():
    ev = _ev()
    assert ev["status"] == "DRAFT_PENDING_OWNER" and ev["non_gating"] is True
    assert ev["follow_on"] == "fo_dx5_cross_section_evidence" and ev["trigger"] == "T_DX5_EVIDENCE"
    s = ev["scope_statement"]
    assert "No chemistry table, validity limit, pre-registration or v1 result is changed" in s
    assert "permanent" in s and "INCONCLUSIVE" in s


def test_every_source_has_access_label_and_evidence_class():
    ev = _ev()
    voc = ev["vocabulary"]
    n = 0
    for pk in ("P1", "P2", "P3"):
        for s in ev["priorities"][pk]["sources"]:
            n += 1
            assert s["access"] in voc["access"], (s["id"], s["access"])
            assert isinstance(s["evidence_class"], str) and s["evidence_class"].strip(), s["id"]
            assert s["evidence_class_code"] in voc["evidence_class_code"], s["id"]
            for k in ("citation", "doi_or_url", "kind", "process", "energy_range_eV", "stated_uncertainty", "where_data_sit",
                      "what_it_adds"):
                assert isinstance(s[k], str) and s[k].strip(), (s["id"], k)
            assert s["check_status"] == "CONFIRMED", s["id"]
            assert isinstance(s["lane01"]["cited_in_lane01"], bool)
            if s["access"] != "open":
                # a closed primary may not be presented as read in full
                assert "full text read" not in s["doi_or_url"].lower(), s["id"]
    assert n > 0


def test_lane01_keys_exist_in_lane01_audit():
    ev = _ev()
    audit = json.load(open(os.path.join(ROOT, "docs", "chemistry", "n2_domain_extension", "domain_extension_audit.json")))
    for pk in ("P1", "P2", "P3"):
        for s in ev["priorities"][pk]["sources"]:
            k = s["lane01"]["lane01_source_key"]
            if k is not None:
                assert k in audit["sources"], (s["id"], k)
                assert s["lane01"]["lane01_access_label"] == audit["sources"][k]["access"]


def test_no_rejected_or_unconfirmed_record_is_used():
    ev, src = _ev(), json.load(open(SRC))
    for pk in ("P1", "P2", "P3"):
        p = ev["priorities"][pk]
        used_ids = {s["id"] for s in p["sources"]}
        used_records = {r for s in p["sources"] for r in s["from_records"]}
        bad = p["rejected_never_used"] + p["unconfirmed_never_used"]
        for r in bad:
            assert r["used"] is False
            assert r["id"] not in used_ids, r["id"]
            if ":claim:" not in r["id"]:
                assert r["from_record"] not in used_records, r["from_record"]
        assert p["rejected_never_used"] == src["priorities"][pk]["rejected"]
        # every source reference in the findings points to a confirmed source of that priority
        text = " ".join(p["findings_coverage"] + p["findings_join_shape_conflicts"])
        for ref in re.findall(r"\b(P[1-3]:[A-Za-z0-9_]+)", text):
            assert ref in used_ids, (pk, ref)
        for ref in p["legitimate_access_candidates_owner_decision"]:
            assert ref in used_ids, (pk, ref)
    # the rejected ids named by the adversarial checks are present as rejected
    rej = {r["id"] for pk in ("P1", "P2", "P3") for r in ev["priorities"][pk]["rejected_never_used"]}
    for must in ("P1:gupta_mathur_1981_pramana17_81", "P2:stanton_stjohn1969", "P3:trajmar1983_physrep",
                 "P3:brunger_buckman2002", "P3:lee_freitas1983"):
        assert must in rej, must


def test_every_priority_has_a_status():
    ev = _ev()
    allowed = set(ev["vocabulary"]["status"])
    assert allowed == {"GAP_MATERIALLY_NARROWED", "GAP_UNCHANGED", "GAP_CLOSED"}
    for pk in ("P1", "P2", "P3"):
        p = ev["priorities"][pk]
        assert p["status"] in allowed, pk
        assert p["status_justification"].strip()
        # status follows the stated rule from the adversarial check and the requirement flag
        if p["requirement_met_by_confirmed_sources"]:
            exp = "GAP_CLOSED"
        elif p["check_material_improvement_confirmed"]:
            exp = "GAP_MATERIALLY_NARROWED"
        else:
            exp = "GAP_UNCHANGED"
        assert p["status"] == exp, pk
        assert p["check_material_improvement_confirmed"] == p["adversarial_check"]["material_improvement_confirmed"]
        assert p["search_log"] and all(lg["searched"] and lg["dead_ends"] for lg in p["search_log"])
        assert p["lane01_requirement"]
    p4 = ev["priorities"]["P4"]
    assert p4["status"] == "DEFERRED per owner ordering" and p4["searched"] is False and not p4["sources"]


def test_lane01_quotes_resolve():
    ev = _ev()
    quotes = [q for pk in ("P1", "P2", "P3") for q in ev["priorities"][pk]["lane01_requirement"]]
    r = ev["reopening_condition_of_question_a"]
    quotes += [r["condition"], r["current_disposition"], ev["owner_priorities"], ev["search_rules"][0]]
    cache = {}
    for q in quotes:
        f = q["from"][0]
        doc = cache.setdefault(f, json.load(open(os.path.join(ROOT, f))))
        x = doc
        for k in q["from"][1:]:
            x = x[k]
        assert x == q["value"], q["name"]


def test_reopening_section_contains_no_decision():
    ev = _ev()
    r = ev["reopening_condition_of_question_a"]
    assert r["status"] == "DRAFT_PENDING_OWNER" and r["decided_here"] is False and r["who_decides"] == "owner"
    assert set(r) == {"status", "decided_here", "who_decides", "condition", "current_disposition", "evidence_facts", "note"}
    assert r["current_disposition"]["value"] == "A-NO"
    text = " ".join([r["note"]] + r["evidence_facts"]).lower()
    for ph in DECISION_PHRASES:
        assert ph not in text, ph
    md = open(MD).read()
    sec = md[md.index("Reopening condition of Question A"):]
    assert "DRAFT_PENDING_OWNER" in sec and "owner" in sec
    for ph in DECISION_PHRASES:
        assert ph not in sec.lower(), ph


def test_lxcat_never_cited():
    ev = _ev()
    for pk in ("P1", "P2", "P3", "P4"):
        p = ev["priorities"][pk]
        for s in p["sources"] + p["rejected_never_used"] + p["unconfirmed_never_used"]:
            for k in ("citation", "doi_or_url"):
                assert "lxcat" not in (s.get(k) or "").lower(), (s["id"], k)
    # any mention anywhere (search logs, notes) is a statement that it was NOT used
    for t in _strings(ev):
        if "lxcat" in t.lower():
            assert any(n in t.lower() for n in NEGATION), t[:200]
    for line in open(MD):
        if "lxcat" in line.lower():
            assert any(n in line.lower() for n in NEGATION), line[:200]

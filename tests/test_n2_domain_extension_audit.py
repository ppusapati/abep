"""Consistency tests for the N2 high-T_e domain-extension evidence audit (docs/chemistry/n2_domain_extension/, DRAFT_PENDING_OWNER).

Non-gating documentation checks: the JSON files parse, every table found beyond its limit in the frozen P5-N2 v1 records is
audited, every verdict carries sources with an evidence class, drafts are marked and kept out of hallthruster_bridge/prereg,
every number in the audit resolves to the script output, and the script reproduces its committed JSON.
"""
import gzip, hashlib, importlib.util, json, os, tomllib

ROOT = os.path.join(os.path.dirname(__file__), "..")
DOC = os.path.join(ROOT, "docs", "chemistry", "n2_domain_extension")
REQ_PATH = os.path.join(DOC, "domain_extension_requirements.json")
AUDIT_PATH = os.path.join(DOC, "domain_extension_audit.json")
MD_PATH = os.path.join(DOC, "N2_DOMAIN_EXTENSION_AUDIT.md")
OUTLINE_PATH = os.path.join(DOC, "drafts", "p5_n2_validation_v2_prereg_OUTLINE_DRAFT.md")
SCRIPT = os.path.join(ROOT, "scripts", "chemistry", "n2_domain_extension_requirements.py")
BR = os.path.join(ROOT, "hallthruster_bridge")
RAW = os.path.join(BR, "validation", "p5_n2_campaign_v1_vacuum_raw.jsonl.gz")
VERDICTS = {"SUPPORTED", "PARTIAL", "UNSUPPORTED", "UNRESOLVED-BY-SOURCE"}
DRAFT = "DRAFT_PENDING_OWNER"


def _req():
    return json.load(open(REQ_PATH))


def _audit():
    return json.load(open(AUDIT_PATH))


def _walk_refs(obj):
    """Yield every {"name", "value", "from"} reference object in the audit JSON."""
    if isinstance(obj, dict):
        if set(obj) >= {"value", "from"} and isinstance(obj["from"], list):
            yield obj
        for v in obj.values():
            yield from _walk_refs(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_refs(v)


def test_json_files_parse_and_are_drafts():
    req, audit = _req(), _audit()
    assert req["status"] == DRAFT and audit["status"] == DRAFT
    assert req["draft_proposed_limits_mean_energy_eV"]["status"] == DRAFT
    assert audit["draft_proposals"]["status"] == DRAFT and audit["completeness_implications"]["status"] == DRAFT
    assert audit["non_gating"] is True
    assert "INCONCLUSIVE" in audit["v1_statement"] and "permanent" in audit["v1_statement"]


def test_frozen_inputs_are_the_v1_release():
    manifest = json.load(open(os.path.join(BR, "validation", "p5_n2_campaign_v1_vacuum_raw_manifest.json")))
    h = hashlib.sha256(open(RAW, "rb").read()).hexdigest()
    assert h == manifest["sha256_gz"]
    assert _req()["inputs_sha256"]["hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_raw.jsonl.gz"] == h


def test_every_table_beyond_limit_in_frozen_records_is_audited():
    with gzip.open(RAW, "rt") as f:
        recs = [json.loads(l) for l in f]
    beyond = {q["file"] for r in recs for q in r["chemistry_per_reaction"]
              if q["extrapolated_fraction"] is not None and q["extrapolated_fraction"] > 1e-12}
    audit, req = _audit(), _req()
    assert beyond == set(audit["tables"]) == set(req["v1_inventory"]["capped_tables"])
    assert len(beyond) == 21
    validity = tomllib.load(open(os.path.join(BR, "propellants", "rate_validity.toml"), "rb"))
    for f, t in audit["tables"].items():
        assert t["current_limit_mean_energy_eV"] == validity[f]["max_mean_energy_eV"] == 45.0
        assert t["current_basis"] == validity[f]["basis"]
        assert f in req["requirements"]["per_table"]


def test_official_statuses_are_read_not_recomputed():
    scores = json.load(open(os.path.join(BR, "validation", "p5_n2_campaign_v1_vacuum_scores.json")))
    inv = _req()["v1_inventory"]
    assert inv["official_status_counts_run_readings"] == scores["status_counts"]["vacuum"]
    assert inv["n_runs_out_of_domain"] == len({r["key"] for r in scores["runs"] if r["status"] == "OUT_OF_DOMAIN"})
    assert inv["check_ood_equals_frozen_fout_predicate"]["equal"] is True
    # counting only: no per-candidate breakdown anywhere in the hypothetical coverage
    assert "sgb-screen" not in json.dumps(_req()["hypothetical_coverage"])


def test_every_verdict_has_sources_with_evidence_class():
    audit, req = _audit(), _req()
    sources = audit["sources"]
    for sid, s in sources.items():
        assert s.get("evidence_class") and s.get("citation"), sid
    proposals = req["draft_proposed_limits_mean_energy_eV"]["limits"]
    for f, t in audit["tables"].items():
        assert t["verdict"] in VERDICTS, f
        assert t["verdict_status"] == DRAFT and t["proposal_status"] == DRAFT
        assert t["cited_sources"] and all(s in sources for s in t["cited_sources"]), f
        assert t["source_coverage"] and all(c["source"] in sources and c["evidence_class"] for c in t["source_coverage"]), f
        assert t["independent_evidence"], f
        for e in t["independent_evidence"]:
            assert e["source"] in sources and e["evidence_class"], (f, e)
        assert t["reasoning"] and t["what_would_change_the_verdict"], f
        if t["verdict"] == "SUPPORTED":
            assert t["proposed_extended_limit_mean_energy_eV"] == proposals[f]
        else:
            assert t["proposed_extended_limit_mean_energy_eV"] is None and f not in proposals
    assert audit["draft_proposals"]["limits"] == proposals


def test_dissociation_support_is_labelled_reconstructed_and_not_independent_at_join():
    """Winters' neutral points are measured-minus-measured (reconstructed), and Table 9 averages Cosby and Winters: the
    evidence class and the join-independence caveat must stay explicit (CLAUDE.md rule 10)."""
    sets = {s["set"]: s for s in _req()["verdict_criteria"]["per_table"]["dissociation_N2.dat"]["independent_sets"]}
    assert sets["Winters1966_N_points"]["class"] == "reconstructed_from_measured"
    for name in ("Winters1966_N_points", "MS1997_curve"):
        assert "NOT independent at the join" in sets[name]["independence_note"], name
    audit = _audit()
    assert audit["sources"]["winters1966"]["evidence_class"].startswith("reconstructed")
    assert any(d.startswith("D-X12") for d in audit["owner_decisions"])


def test_every_audit_number_resolves_to_the_script_output():
    req, n = _req(), 0
    for ref in _walk_refs(_audit()):
        v = req
        for p in ref["from"]:
            v = v[p]
        assert v == ref["value"], ref
        n += 1
    assert n > 100


def test_drafts_marked_and_nothing_placed_under_prereg():
    for path in (MD_PATH, OUTLINE_PATH):
        text = open(path, encoding="utf-8").read()
        assert DRAFT in text, path
        for banned in ("best candidate", "recommended candidate", "would pass"):
            assert banned not in text.lower(), (path, banned)
    outline = open(OUTLINE_PATH, encoding="utf-8").read()
    assert "INCONCLUSIVE" in outline and "never rewritten" in outline
    prereg = os.path.join(BR, "prereg")
    for name in os.listdir(prereg):
        assert "v2" not in name and "domain_extension" not in name, name


def test_requirements_script_reproduces_its_json():
    spec = importlib.util.spec_from_file_location("n2dx_req", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._normalise(mod.compute()) == _req()

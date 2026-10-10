"""Bid technical package (docs/bid/package/, DRAFT_FOR_OWNER_REVIEW): evidence-discipline checks.

The TECHNICAL SOURCE is one constant, `bid_technical_source.commit` in docs/bid/bid_technical_baseline_v2.json
(compliance_data.TECHNICAL_SOURCE_SHA). These tests bind the package to it:
- the constant, the matrix, the freeze record's generated facts and the README all name the same commit; the historical v1
  freeze record (bbc480c) is unchanged;
- every registered RFP clause id (registration at the technical source) is in the compliance matrix (JSON and Markdown);
- every cited evidence path exists at the technical source (git show), and every JSON-pointer locator resolves there;
- the mass section equals the mass record at the technical source (read independently here) and claims no compliance;
- no withdrawn Hall result phrase, no bbc480c mass value, no legacy card-closure number, no five-state caveat;
- no PASS / GO is claimed for any gate that is not PASS / GO at the technical source (statuses carried verbatim);
- governing owner decisions not contained in the technical source are pinned by sha256 and flagged in the README;
- the generated files are current, and every owner-input id is in the README checklist.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "docs", "bid", "package")
sys.path.insert(0, PKG)
import compliance_data as cd  # noqa: E402

BASELINE_V2 = os.path.join(ROOT, "docs", "bid", "bid_technical_baseline_v2.json")
BASELINE_V1 = os.path.join(ROOT, "docs", "bid", "bid_technical_baseline.json")
with open(BASELINE_V2, encoding="utf-8") as _f:
    SOURCE = json.load(_f)["bid_technical_source"]["commit"]
REG = "docs/requirements/rfp_official/rfp_registration_v1.json"
F9 = "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"
MASS_CANDIDATES = ["docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json",
                   "docs/budgets/mass_power_a9_v4/mass_power_a9_v4.json"]
A926_JSON = "docs/decisions/OD_2026_10_05_A9_26_mass_budget_owner_decisions.json"
A926_MD = "docs/decisions/OD_2026_10_05_A9_26_MASS_BUDGET_OWNER_DECISIONS.md"
MD_FILES = ["README.md", "01_COMPLIANCE_MATRIX.md", "02_TECHNICAL_APPROACH.md", "03_DEVELOPMENT_AND_TEST_PLAN.md",
            "04_RISK_REGISTER.md", "05_PROGRAMMATIC_SECTIONS.md"]
# CLAUDE.md "Superseded / withdrawn (do not quote)": phrases of the withdrawn absolute 0-D Hall results
WITHDRAWN_PHRASES = ["2.5 kW closure", "2.5 kW Hall closure", "110-120 kg", "110–120 kg", "110 - 120 kg",
                     "110 to 120 kg", "P(success) 0.77", "0.77 vs 0.63", "0.77 versus 0.63"]
# bbc480c-era mass values (mass_power_a9_v3 roll-up / AL-08 v3) and superseded upstream numbers, legacy card closure
STALE_PHRASES = ["40.75", "42.75", "45.75", "50.75", "33.96", "6.05 kg", "6.0528", "0.285 kg", "0.0983",
                 "5.676", "49.96", "five-state", "32c9e63", "mass_power_a9_v3", "28.8 kg"]
PATH_ROOTS = ("docs/", "hallthruster_bridge/", "abep_sim/", "scripts/", "tests/", "schemas/", "config/")
PACKAGE_PATHS = ("docs/bid/", "tests/test_bid_package.py")  # the package, its test and the freeze records


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


@pytest.fixture(scope="module")
def source_available():
    if _git("cat-file", "-e", SOURCE + "^{commit}").returncode != 0:
        pytest.skip("bid technical source commit not present in this clone (shallow checkout)")
    return True


def _exists(path):
    return _git("cat-file", "-e", f"{SOURCE}:{path}").returncode == 0


def _show(path):
    r = _git("show", f"{SOURCE}:{path}")
    assert r.returncode == 0, f"{path} not readable at {SOURCE[:7]}"
    return r.stdout


def _matrix():
    with open(os.path.join(PKG, "compliance_matrix_v1.json"), encoding="utf-8") as f:
        return json.load(f)


def _baseline():
    with open(BASELINE_V2, encoding="utf-8") as f:
        return json.load(f)


def _md(name):
    with open(os.path.join(PKG, name), encoding="utf-8") as f:
        return f.read()


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------------------------------------ the one constant
def test_single_technical_source_constant():
    assert re.fullmatch(r"[0-9a-f]{40}", SOURCE)
    assert cd.TECHNICAL_SOURCE_SHA == SOURCE and cd.FREEZE_COMMIT == SOURCE
    assert _matrix()["technical_source_commit"] == SOURCE
    assert _matrix()["freeze_record"] == "docs/bid/bid_technical_baseline_v2.json"
    b = _baseline()
    assert b["facts_read_from_technical_source"]["technical_source_commit"] == SOURCE
    assert b["bid_technical_source"]["branch"] == "claude/nifty-ramanujan-w68f9z"
    assert b["decided_by"] == "owner" and b["bid_technical_source"]["verification_record"].strip()
    assert SOURCE in _md("README.md")
    # no other commit is named as the technical source anywhere in the package code
    for name in ("compliance_data.py", "build_package.py", "source_facts.py"):
        with open(os.path.join(PKG, name), encoding="utf-8") as f:
            text = f.read()
        assert not re.search(r"\b[0-9a-f]{40}\b", text), f"hard-coded commit in {name}"


def test_historical_v1_freeze_record_unchanged():
    b = _baseline()
    assert _sha256_file(BASELINE_V1) == b["supersedes"]["sha256"]
    with open(BASELINE_V1, encoding="utf-8") as f:
        v1 = json.load(f)
    assert v1["schema"] == "bid_technical_baseline_v1"
    assert v1["bid_technical_source"]["commit"] == b["supersedes"]["pinned_commit"]
    assert v1["bid_technical_source"]["commit"].startswith("bbc480c")
    assert v1["bid_technical_source"]["commit"] != SOURCE


def test_two_sha_rule_recorded():
    b = _baseline()
    text = " ".join(b["two_sha_rule"])
    assert "TECHNICAL SOURCE SHA" in text and "PACKAGE / FREEZE-RECORD SHA" in text
    assert "not a technical source" in b["record_kind"]
    readme = _md("README.md")
    assert "Two-SHA discipline" in readme and "PACKAGE / FREEZE-RECORD" in readme


# ------------------------------------------------------------------------------------------------ evidence at the source
def test_every_registered_clause_in_matrix(source_available):
    reg = json.loads(_show(REG))
    ids = [c["id"] for c in reg["clauses"]]
    assert len(ids) == 37
    m = _matrix()
    assert [c["id"] for c in m["clauses"]] == ids
    md = _md("01_COMPLIANCE_MATRIX.md")
    for cid in ids:
        assert f"### {cid} " in md, cid
    for c, rc in zip(m["clauses"], reg["clauses"]):
        assert c["status"] in cd.STATUSES
        assert c["evidence_at_technical_source"], c["id"]
        assert c["response"].strip() and "{{" not in c["response"]
        assert c["rfp_text_verbatim"] == rc["text"]
    assert sum(m["status_counts"].values()) == 37


def _cited_paths():
    paths = set()
    m = _matrix()
    for c in m["clauses"]:
        for e in c["evidence_at_technical_source"]:
            paths.add(e["path"])
    for g in m["gates_at_technical_source"]:
        paths.add(g["source"]["path"])
    paths.add(m["mass_presentation"]["current_rollup"]["record"])
    for name in MD_FILES:
        for tok in re.findall(r"`([^`\s]+)`", _md(name)):
            if tok == "CLAUDE.md" or (tok.startswith(PATH_ROOTS) and not tok.endswith("/")):
                paths.add(tok)
    return sorted(p for p in paths if not p.startswith(PACKAGE_PATHS))


def test_every_cited_path_exists_at_technical_source(source_available):
    paths = _cited_paths()
    assert len(paths) > 30
    missing = [p for p in paths if not _exists(p)]
    assert not missing, f"cited paths absent at {SOURCE[:7]}: {missing}"


def _resolve(doc, pointer):
    cur = doc
    for part in pointer.split("/"):
        m = re.match(r"^([\w.-]+)\[([\w-]+)=([^\]]+)\]$", part)
        if m:
            cur = cur[m.group(1)]
            hits = [x for x in cur if isinstance(x, dict) and str(x.get(m.group(2))) == m.group(3)]
            assert hits, f"no element {m.group(2)}={m.group(3)}"
            cur = hits[0]
        else:
            cur = cur[part]
    return cur


def test_json_locators_resolve_at_technical_source(source_available):
    cache = {}
    checked = 0
    m = _matrix()
    refs = [(c["id"], e) for c in m["clauses"] for e in c["evidence_at_technical_source"]]
    refs += [(g["id"], g["source"]) for g in m["gates_at_technical_source"]]
    for cid, e in refs:
        if not (e["path"].endswith(".json") and e["locator"].startswith("#/")):
            continue
        if e["path"] not in cache:
            cache[e["path"]] = json.loads(_show(e["path"]))
        pointer = e["locator"][2:].split()[0]
        try:
            _resolve(cache[e["path"]], pointer)
        except (KeyError, TypeError, AssertionError) as exc:
            pytest.fail(f"{cid}: {e['path']} {e['locator']} does not resolve at {SOURCE[:7]} ({exc})")
        checked += 1
    assert checked > 60


def test_governing_decisions_pinned_and_post_source_ones_flagged(source_available):
    facts = _baseline()["facts_read_from_technical_source"]
    gov = facts["governing_decisions"]
    assert [g["id"] for g in gov] == [d["id"] for d in cd.GOVERNING_DECISIONS]
    post = []
    for g in gov:
        for k in ("json", "md"):
            if g["in_technical_source"]:
                assert hashlib.sha256(_show(g[k]).encode("utf-8")).hexdigest() == g[k + "_sha256"], g[k]
            else:
                assert not (_exists(g["json"]) and _exists(g["md"]))
                assert _sha256_file(os.path.join(ROOT, g[k])) == g[k + "_sha256"], g[k]
        if not g["in_technical_source"]:
            post.append(g)
    readme = _md("README.md")
    m = _matrix()
    # a package-level owner ruling made after the technical source (A9.27: the owner protects the bid pair) does not
    # make the source non-final; any other post-source governing decision does
    blocking = [g for g in post if not g.get("package_level_post_source_allowed")]
    allowed = {d["id"] for d in cd.GOVERNING_DECISIONS if d.get("package_level_post_source_allowed")}
    assert {g["id"] for g in post if g.get("package_level_post_source_allowed")} <= allowed == {"A9.27"}
    if blocking:
        assert "SOURCE NOT YET FINAL FOR THE BID" in readme
        assert facts["source_status"].startswith("NOT_FINAL_FOR_BID")
        assert m["source_findings"]
    for g in post:
        # a post-source decision record is never cited as evidence at the source
        assert all(e["path"] not in (g["json"], g["md"]) for c in m["clauses"] for e in c["evidence_at_technical_source"])
    assert set(m["post_source_governing_decisions"]) == {g["json"] for g in post}


# ------------------------------------------------------------------------------------------------ mass
def _mass_record():
    for p in MASS_CANDIDATES:
        if _exists(p):
            return p, json.loads(_show(p))
    pytest.fail("no mass_power record at the technical source")


def test_mass_section_read_from_the_mass_record(source_available):
    path, rec = _mass_record()
    rolls = [r for r in rec["rollups"] if r.get("configuration") == "hall_icp_neutralizer"
             and not re.search("HISTORICAL|SENSITIVITY", " ".join(str(r.get(k, "")) for k in
                                                                ("reading", "label", "role", "status")), re.I)]
    assert len(rolls) == 1
    r = rolls[0]
    dry = next(r[k] for k in ("dry_known_kg", "dry_kg", "dry_planning_kg") if k in r)
    nominal = next(r[k] for k in ("nominal_dry_known_kg", "nominal_dry_kg") if k in r)
    pct = round(100 * r["system_margin_kg"] / nominal)
    wet = sorted((w for w in r["wet"] if w["reference"] == "HARD_40_WET"), key=lambda w: w["xe_case_kg"])
    assert [w["xe_case_kg"] for w in wet] == [2.0, 5.0, 10.0]
    cur = _matrix()["mass_presentation"]["current_rollup"]
    assert cur["record"] == path and cur["dry_kg"] == dry and cur["nominal_dry_kg"] == nominal
    assert cur["system_margin_pct"] == pct
    assert [w["wet_kg"] for w in cur["wet"]] == [next(w[k] for k in ("wet_known_kg", "wet_kg") if k in w) for w in wet]
    wet_txt = " / ".join(f"{w['wet_kg']:.2f}" for w in cur["wet"])
    p1811 = next(c for c in _matrix()["clauses"] if c["id"] == "RFP-P18-11")
    r07 = next(ln for ln in _md("04_RISK_REGISTER.md").splitlines() if ln.startswith("| R-07 "))
    sec9 = _md("02_TECHNICAL_APPROACH.md").split("## 9. Mass")[1].split("## 10.")[0]
    for text in (p1811["response"], r07, sec9):
        assert f"dry {dry:.2f} kg after a {pct} % system margin" in text
        assert wet_txt in text
        assert "MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED" in text
    for w in wet:
        assert w["state"] in sec9
    for ln in rec["lines"]["hall_icp_neutralizer"]:
        v = (ln.get("value") or {}).get("value_kg")
        if v is not None:
            assert f"{ln['line']} {v:g} kg" in _md("02_TECHNICAL_APPROACH.md"), ln["line"]
    al08 = next(ln for ln in rec["lines"]["hall_icp_neutralizer"] if ln["line"] == "AL-08")["value"]["value_kg"]
    assert f"AL-08 = {al08:g} kg" in next(c for c in _matrix()["clauses"] if c["id"] == "RFP-P18-08")["response"]
    assert f"AL-08 = {al08:g} kg" in _md("02_TECHNICAL_APPROACH.md")


def test_mass_presentation_follows_owner_policy_and_claims_no_compliance():
    mp = _matrix()["mass_presentation"]
    assert mp["status"] == "MASS INCOMPLETE_EVIDENCE / NOT_YET_CLOSED"
    assert mp["requirement"] == "complete flight wet mass < 40 kg"
    # owner constants bound to the verbatim A9.26 record (immutable decision record in the package history)
    with open(os.path.join(ROOT, A926_JSON), encoding="utf-8") as f:
        a926 = json.load(f)["owner_decision_summary"]
    with open(os.path.join(ROOT, A926_MD), encoding="utf-8") as f:
        a926_md = f.read()
    assert cd.MASS_PROPOSAL_TARGET["a926_summary_verbatim"] in a926["proposal_target"]
    assert "10 % system-level mass margin" in a926["system_margin"] and cd.A926_BID_SYSTEM_MARGIN_FRACTION == 0.10
    norm = lambda s: re.sub(r"\s*/\s*", "/", s).lower()  # noqa: E731
    sec7 = norm(a926_md.split("7. BID WORDING")[1].split("8. TECHNICAL SOURCE SHA")[0])
    for a in cd.MASS_CLOSURE_ACTIONS:
        assert norm(a) in sec7, a
    tgt = cd.MASS_PROPOSAL_TARGET
    assert round(tgt["nominal_dry_max_kg"] * (1 + tgt["system_margin_fraction"]) + tgt["xe_planning_reference_kg"], 1) == 39.4
    for name in MD_FILES:
        text = _md(name)
        assert not re.search(r"mass (compliance|closure) (is |has been )?(demonstrated|achieved|met)", text, re.I), name
        for clause in re.split(r"[.;|]", text):
            if re.search(r"\bmass\b", clause, re.I):
                assert not re.search(r"\b(PASS|CLOSES|COMPLIANT)\b", NEGATED.sub("", clause)), (name, clause)
    assert "DESIGN TARGET" in _md("02_TECHNICAL_APPROACH.md") and "not the selected Xe load" in _md("02_TECHNICAL_APPROACH.md")


# ------------------------------------------------------------------------------------------------ content discipline
def test_no_withdrawn_hall_result_phrases():
    names = MD_FILES + ["compliance_matrix_v1.json", "compliance_data.py"]
    for name in names:
        text = _md(name)
        for ph in WITHDRAWN_PHRASES:
            assert ph not in text, f"withdrawn Hall result phrase {ph!r} in {name}"


def test_no_bbc480c_values_or_superseded_caveats():
    for name in MD_FILES + ["compliance_matrix_v1.json"]:
        text = _md(name)
        for ph in STALE_PHRASES:
            assert ph not in text, f"superseded value / caveat {ph!r} in {name}"
    for name in MD_FILES:
        for ln in _md(name).splitlines():
            if "bbc480c" in ln:
                assert name == "README.md" and "A9.24 item 9" in ln, f"{name}: bbc480c outside the history note: {ln}"
    m = _matrix()
    for c in m["clauses"]:
        assert "bbc480c" not in json.dumps(c), c["id"]
    assert "OIR-TEC-01" not in cd.OWNER_INPUTS and "OIR-TEC-05" not in cd.OWNER_INPUTS
    assert set(cd.RESOLVED_OWNER_INPUTS) == {"OIR-TEC-01", "OIR-TEC-05"}


def test_architecture_wording_and_c1_ground_reference_only():
    readme, ta = _md("README.md"), _md("02_TECHNICAL_APPROACH.md")
    for text in (readme, ta):
        assert "hall_icp_neutralizer" in text and "flight cathode NONE" in text.replace("**flight cathode: NONE**",
                                                                                         "flight cathode NONE")
        assert "C1 GROUND_REFERENCE_ONLY" in text or "**GROUND_REFERENCE_ONLY**" in text
        assert "AIR_PRIMARY" in text and "XE_CONTINGENCY" in text
        assert "INVESTIGATION_HYPOTHESIS" in text and "physical design not frozen" in text
    assert "two series latch isolation valves" in ta
    assert "OWNER_CONFIRMED_CURRENT_ARCHITECTURE_READING" in ta
    for name in MD_FILES + ["compliance_matrix_v1.json"]:
        text = _md(name)
        assert "CONTROL_FALLBACK" not in text, name
        for ln in text.splitlines():
            if re.search(r"\bC1\b", ln) and re.search(r"fallback", ln, re.I):
                assert re.search(r"\b(never|no|not)\b", ln, re.I), f"{name}: C1 near 'fallback' without negation: {ln}"


def test_compliance_classes_honest():
    m = _matrix()
    st = {c["id"]: c["status"] for c in m["clauses"]}
    # offer properties only: thruster type; system composition (owner ruling A9.27, composition only, no evidence claim)
    assert {k for k, v in st.items() if v == "COMPLY"} == {"RFP-P18-07", "RFP-P19-03"}
    assert st["RFP-P18-08"] == "COMPLY_PLANNED_WITH_EVIDENCE_PATH"     # A9.27: the whole clause is not COMPLY
    for cid in ("RFP-P18-06", "RFP-P18-10", "RFP-P18-11", "RFP-P19-01", "RFP-P17-03", "RFP-P17-05"):
        assert st[cid] == "NOT_YET_DEMONSTRATED", cid
    for c in m["clauses"]:
        for clause in re.split(r"[.;]", c["response"]):
            s = NEGATED.sub("", clause.replace("NO-GO", ""))
            assert not re.search(r"\b(PASS|GO)\b", s), (c["id"], clause)


def test_gate_statuses_carried_verbatim_and_never_pass(source_available):
    f9 = json.loads(_show(F9))
    at_src = {g["id"]: g["current_status"] for g in f9["architecture_gates"] + f9["pre_lock1_gates"]}
    carried = {g["id"]: g["status_at_technical_source"] for g in _matrix()["gates_at_technical_source"]}
    assert carried == at_src
    assert at_src["GNG-ICP-01"] == "NOT_EVALUATED"
    for gid, s in carried.items():
        assert not re.search(r"\b(PASS|GO)\b", s.replace("NO-GO", "")), (gid, s)
    facts = _baseline()["facts_read_from_technical_source"]
    assert {g["id"]: g["status"] for g in facts["gates"]} == at_src
    assert facts["robust_upstream_set"]["n_members"] == 0
    assert facts["architecture"]["flight_cathode"] == "NONE"
    assert facts["design_state_set"]["n_required_states"] == 196


GATE_TOKEN = re.compile(r"\b(AG-\d\d|GNG-ICP-01|ICP-?45[AN]?|LOCK-1|LOCK-2)\b")
NEGATED = re.compile(r"\b(no|not|never|none|nor|without|refused)\b.*$", re.IGNORECASE)


def test_no_pass_or_go_claimed_for_unpassed_gates():
    for name in MD_FILES:
        for i, line in enumerate(_md(name).splitlines(), 1):
            if not GATE_TOKEN.search(line):
                continue
            for clause in re.split(r"[.;|]", line):
                s = clause.replace("GO / NO-GO", "").replace("GO/NO-GO", "").replace("NO-GO", "")
                s = NEGATED.sub("", s)
                assert not re.search(r"\b(PASS|GO)\b", s), f"{name}:{i}: PASS / GO next to a gate: {clause.strip()!r}"


def test_generated_package_current_and_checklist_complete(source_available):
    r = subprocess.run([sys.executable, os.path.join(PKG, "build_package.py"), "--check"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    readme = _md("README.md")
    assert "1-15 and 34-40" in readme
    used = {o for c in cd.CLAUSES.values() for o in c.get("owner_input", [])}
    assert used <= set(cd.OWNER_INPUTS)
    for oid in cd.OWNER_INPUTS:
        assert f"**{oid}**" in readme, oid
    for name in MD_FILES:
        text = _md(name)
        assert "DRAFT_FOR_OWNER_REVIEW" in text, name
        assert "{{" not in text and "}}" not in text, name


def test_a9_27_rulings_and_submission_checklist():
    """Owner ruling A9.27: RFP-P19-03 COMPLY (composition only), RFP-P18-08 split (tanks / paths COMPLY BY DESIGN;
    functional dual-propellant capability PLANNED / NOT YET DEMONSTRATED), OIR-DOC-01 review complete / form completion
    pending, Part IV(A)-(H) checklist present, and no price / currency information anywhere in the technical package."""
    import re
    pkg = os.path.join(ROOT, "docs", "bid", "package")
    m = json.load(open(os.path.join(pkg, "compliance_matrix_v1.json"), encoding="utf-8"))
    rows = {c["id"]: c for c in m["clauses"]} if "clauses" in m else {c["id"]: c for c in m["rows"]}
    p19 = rows["RFP-P19-03"]["response"]
    assert "confirms the proposed system composition only" in p19 and "does not claim" in p19
    p18 = rows["RFP-P18-08"]["response"]
    assert "COMPLY BY DESIGN" in p18 and "PLANNED / NOT YET DEMONSTRATED" in p18
    cl = open(os.path.join(pkg, "06_SUBMISSION_CHECKLIST.md"), encoding="utf-8").read()
    for part in ("IV(A)", "IV(B)", "IV(C)", "IV(D)", "IV(E)", "IV(F)", "IV(G)", "IV(H)"):
        assert f"| {part} |" in cl, part
    assert "REVIEW_COMPLETE_SUBMISSION_FORM_COMPLETION_PENDING" in cl
    readme = open(os.path.join(pkg, "README.md"), encoding="utf-8").read()
    assert "REVIEW_COMPLETE_SUBMISSION_FORM_COMPLETION_PENDING" in readme and "NOT screened" not in readme
    money = re.compile(r"(₹|\bINR\b|\bRs\.?\s*\d|\blakhs?\b|\bcrores?\b|\bUSD\b|\$\s*\d)", re.IGNORECASE)
    for name in sorted(os.listdir(pkg)):
        if name.endswith(".md"):
            txt = open(os.path.join(pkg, name), encoding="utf-8").read()
            assert not money.search(txt), (name, money.search(txt).group(0))

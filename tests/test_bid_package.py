"""Bid technical package (docs/bid/package/, DRAFT_FOR_OWNER_REVIEW): evidence-discipline checks.

- every registered RFP clause id (registration at the freeze commit) is in the compliance matrix (JSON and Markdown);
- every cited evidence path exists at the bid freeze commit bbc480c, and every JSON-pointer locator resolves there;
- no phrase of a withdrawn Hall result (CLAUDE.md 'Superseded / withdrawn') appears in the package;
- no PASS / GO is claimed for any gate that is not PASS / GO at the freeze (gate statuses carried verbatim);
- the generated matrix is current, and every owner-input id is in the README checklist.
"""
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

FREEZE = cd.FREEZE_COMMIT
REG = "docs/requirements/rfp_official/rfp_registration_v1.json"
F9 = "docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json"
MD_FILES = ["README.md", "01_COMPLIANCE_MATRIX.md", "02_TECHNICAL_APPROACH.md", "03_DEVELOPMENT_AND_TEST_PLAN.md",
            "04_RISK_REGISTER.md", "05_PROGRAMMATIC_SECTIONS.md"]
# CLAUDE.md "Superseded / withdrawn (do not quote)": phrases of the withdrawn absolute 0-D Hall results
WITHDRAWN_PHRASES = ["2.5 kW closure", "2.5 kW Hall closure", "110-120 kg", "110–120 kg", "110 - 120 kg",
                     "110 to 120 kg", "P(success) 0.77", "0.77 vs 0.63", "0.77 versus 0.63"]
PATH_ROOTS = ("docs/", "hallthruster_bridge/", "abep_sim/", "scripts/", "tests/", "schemas/")
POST_FREEZE_ALLOWED = ("docs/bid/", "tests/test_bid_package.py")  # the package, its test and the freeze record


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


@pytest.fixture(scope="module")
def freeze_available():
    if _git("cat-file", "-e", FREEZE + "^{commit}").returncode != 0:
        pytest.skip("bid freeze commit not present in this clone (shallow checkout)")
    return True


def _show(path):
    r = _git("show", f"{FREEZE}:{path}")
    assert r.returncode == 0, f"{path} not readable at {FREEZE[:7]}"
    return r.stdout


def _matrix():
    with open(os.path.join(PKG, "compliance_matrix_v1.json"), encoding="utf-8") as f:
        return json.load(f)


def _md(name):
    with open(os.path.join(PKG, name), encoding="utf-8") as f:
        return f.read()


def test_every_registered_clause_in_matrix(freeze_available):
    reg = json.loads(_show(REG))
    ids = [c["id"] for c in reg["clauses"]]
    assert len(ids) == 37
    m = _matrix()
    got = [c["id"] for c in m["clauses"]]
    assert got == ids
    md = _md("01_COMPLIANCE_MATRIX.md")
    for cid in ids:
        assert f"### {cid} " in md, cid
    for c in m["clauses"]:
        assert c["status"] in cd.STATUSES
        assert c["evidence_at_freeze"], c["id"]
        assert c["response"].strip()
    assert sum(m["status_counts"].values()) == 37
    assert m["technical_source_commit"] == FREEZE


def _cited_paths():
    paths = set()
    for c in _matrix()["clauses"]:
        for e in c["evidence_at_freeze"]:
            paths.add(e["path"])
    for g in _matrix()["gates_at_freeze"]:
        paths.add(g["source"]["path"])
    for name in MD_FILES:
        for tok in re.findall(r"`([^`\s]+)`", _md(name)):
            if tok == "CLAUDE.md" or (tok.startswith(PATH_ROOTS) and not tok.endswith("/")):
                paths.add(tok)
    return sorted(p for p in paths if not p.startswith(POST_FREEZE_ALLOWED))


def test_every_cited_path_exists_at_freeze(freeze_available):
    paths = _cited_paths()
    assert len(paths) > 30
    missing = [p for p in paths if _git("cat-file", "-e", f"{FREEZE}:{p}").returncode != 0]
    assert not missing, f"cited paths absent at {FREEZE[:7]}: {missing}"


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


def test_json_locators_resolve_at_freeze(freeze_available):
    cache = {}
    checked = 0
    for c in _matrix()["clauses"]:
        for e in c["evidence_at_freeze"]:
            if not (e["path"].endswith(".json") and e["locator"].startswith("#/")):
                continue
            if e["path"] not in cache:
                cache[e["path"]] = json.loads(_show(e["path"]))
            pointer = e["locator"][2:].split()[0]
            try:
                _resolve(cache[e["path"]], pointer)
            except (KeyError, TypeError, AssertionError) as exc:
                pytest.fail(f"{c['id']}: {e['path']} {e['locator']} does not resolve at {FREEZE[:7]} ({exc})")
            checked += 1
    assert checked > 40


def test_no_withdrawn_hall_result_phrases():
    names = MD_FILES + ["compliance_matrix_v1.json", "compliance_data.py"]
    for name in names:
        text = _md(name)
        for ph in WITHDRAWN_PHRASES:
            assert ph not in text, f"withdrawn Hall result phrase {ph!r} in {name}"


def test_gate_statuses_carried_verbatim_and_never_pass(freeze_available):
    f9 = json.loads(_show(F9))
    at_freeze = {g["id"]: g["current_status"] for g in f9["architecture_gates"] + f9["pre_lock1_gates"]}
    carried = {g["id"]: g["status_at_freeze"] for g in _matrix()["gates_at_freeze"]}
    assert carried == at_freeze
    assert at_freeze["GNG-ICP-01"] == "NOT_EVALUATED"
    for gid, st in carried.items():
        assert not re.search(r"\b(PASS|GO)\b", st.replace("NO-GO", "")), (gid, st)


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


def test_generated_matrix_current_and_checklist_complete(freeze_available):
    r = subprocess.run([sys.executable, os.path.join(PKG, "build_package.py"), "--check"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    readme = _md("README.md")
    assert FREEZE in readme
    assert "1-15 and 34-40" in readme
    used = {o for c in cd.CLAUSES.values() for o in c.get("owner_input", [])}
    assert used <= set(cd.OWNER_INPUTS)
    for oid in cd.OWNER_INPUTS:
        assert f"**{oid}**" in readme, oid
    for name in MD_FILES:
        assert "DRAFT_FOR_OWNER_REVIEW" in _md(name), name

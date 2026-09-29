"""ECHT-N2 disposition: HISTORICAL_UNSUPPORTED (hallthruster_bridge/identification/echt_n2/STATUS.json).

Checks that the case file carries the status fields with its original content intact, that run_cases.jl refuses such a
file unless ABEP_ALLOW_HISTORICAL=1 and then marks every record non-score-bearing (static text check; Julia is not
run here), that abep_sim/validation.py received documentation only (every code constant unchanged against the base
commit), and that the status records are complete and consistent with the evidence audit.
"""
import ast
import hashlib
import json
import os
import re
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BR = os.path.join(ROOT, "hallthruster_bridge")
ECHT_DIR = os.path.join(BR, "identification", "echt_n2")
AUDIT_REL = "hallthruster_bridge/identification/echt_n2/echt_n2_evidence_audit_v1.json"
BASE_COMMIT = "efc4a4e"                      # commit before the disposition (validation.py, cases/echt_n2.json as audited)
STATUS_KEYS = ("status", "status_basis", "score_bearing")
# sha256 of cases/echt_n2.json at BASE_COMMIT; the file minus the status keys must still serialise to exactly these bytes
ORIGINAL_ECHT_CASES_SHA256 = "6ab1d1844aef6471e9de604b4403c4089609f0ede9ae22620666bef02df1a591"
# the only non-docstring addition allowed in validation.py: a plain-string provenance constant
METADATA_NAMES = {"CAL_ANCHOR_PROVENANCE"}
# every int/float literal in validation.py code (docstrings excluded), in source order, as at BASE_COMMIT
BASE_NUMERIC_CONSTANTS = [
    9.80665,
    5.0, 231.9, 3.08, 5.0, 255.1, 3.69, 5.0, 278.6, 4.3, 5.2, 277.0, 4.56, 5.4, 275.7, 4.81,     # P5_N2
    61.4, 90.0, 1251.0, 1724.0, 0.128, 0.169,                                                     # P5_RANGES
    0.0615, 0.0865, 0.032, 0.013,                                                                 # P5_GEOM
    0.04, 0.05, 0.086,                                                                            # ECHT_GEOM
    5.0, 230.8, 1.75, 5.0, 250.3, 2.15, 5.0, 274.3, 2.03,                                         # P5_XE
    72.8, 86.8, 1485.0, 1770.0, 0.329, 0.396,                                                     # P5_XE_RANGES
    1e-06, 1000.0, 1.0, 1000.0, 1000.0, 1e-06, 2, 1e-06, 0, 0.0,                                  # validate_p5
    250.0, 2e-06, 1000.0, 2e-06, 2, 2e-06,                                                        # calibration_anchor
    200, 3]                                                                                       # __main__
# sha256 over every code constant (numbers, strings, None; type + repr, source order) as at BASE_COMMIT
BASE_CONSTANTS_SHA256 = "d8dafbd3c774810220fd88e4d9d2ae51ee5c74ba28f6f1b261240193b697cc68"
EVIDENCE_TYPES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "missing")


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def _strip_docs_and_metadata(src):
    """AST of `src` without docstrings (module, class, function) and without the allowed metadata assignment."""
    tree = ast.parse(src)
    for node in list(ast.walk(tree)):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        keep = []
        for i, stmt in enumerate(body):
            is_doc = (i == 0 and isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                      and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
                      and isinstance(stmt.value.value, str))
            is_meta = (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)
                       and stmt.targets[0].id in METADATA_NAMES)
            if is_meta:
                assert isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str), \
                    "metadata constant must be a plain string"
            if not (is_doc or is_meta):
                keep.append(stmt)
        node.body = keep
    return tree


def _code_constants(src):
    tree = _strip_docs_and_metadata(src)
    nodes = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Constant)), key=lambda n: (n.lineno, n.col_offset))
    return [(type(n.value).__name__, repr(n.value)) for n in nodes]


def _numeric(consts):
    return [float(r) if t == "float" else int(r) for t, r in consts if t in ("int", "float")]


def _constants_sha(consts):
    return hashlib.sha256(json.dumps(consts).encode()).hexdigest()


def _git_show(rev, path):
    try:
        out = subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{path}"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8") if out.returncode == 0 else None


# ---------------------------------------------------------------------------------------------------- case file
def test_echt_case_file_is_historical_unsupported_with_content_unchanged():
    d = json.loads(_read("hallthruster_bridge", "cases", "echt_n2.json"))
    assert tuple(d)[:3] == STATUS_KEYS
    assert d["status"] == "HISTORICAL_UNSUPPORTED"
    assert d["score_bearing"] is False
    assert AUDIT_REL in d["status_basis"] and os.path.isfile(os.path.join(ROOT, AUDIT_REL))
    assert "identification/echt_n2/STATUS.json" in d["status_basis"]
    rest = {k: v for k, v in d.items() if k not in STATUS_KEYS}
    assert hashlib.sha256(json.dumps(rest, indent=1).encode()).hexdigest() == ORIGINAL_ECHT_CASES_SHA256
    assert [c["id"] for c in d["cases"]] == ["ECHT_200V", "ECHT_225V", "ECHT_250V", "ECHT_275V"]


def test_other_case_files_are_not_historical():
    """The refusal is keyed on the top-level status, so the P5 case files must not carry it."""
    for f in sorted(os.listdir(os.path.join(BR, "cases"))):
        if f.endswith(".json") and f != "echt_n2.json":
            assert json.loads(_read("hallthruster_bridge", "cases", f)).get("status") != "HISTORICAL_UNSUPPORTED", f


# ---------------------------------------------------------------------------------------------------- run_cases.jl
def test_run_cases_refuses_historical_case_file_unless_allowed():
    src = _read("hallthruster_bridge", "run_cases.jl")
    code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
    status = re.search(r'case_status\s*=\s*string\(get\(cases,\s*:status,\s*""\)\)', code)
    flag = re.search(r'historical\s*=\s*case_status\s*==\s*"HISTORICAL_UNSUPPORTED"', code)
    refuse = re.search(r'if\s+historical\s*&&\s*get\(ENV,\s*"ABEP_ALLOW_HISTORICAL",\s*""\)\s*!=\s*"1"\s*\n\s*error\(', code)
    assert status and flag and refuse
    read_at = code.index("cases = JSON3.read(read(ARGS[1], String))")
    # the refusal runs after the case file is read and before anything is checked or simulated
    assert read_at < status.start() < flag.start() < refuse.start()
    assert refuse.end() < code.index("check_reaction_sets(cases)") < code.index("for c in cases.cases") < code.index("run_case(")
    assert "HISTORICAL_UNSUPPORTED" not in _read("hallthruster_bridge", "bridge_lib.jl")   # the gate lives in run_cases.jl only


def test_run_cases_marks_every_historical_record_non_score_bearing():
    code = "\n".join(line for line in _read("hallthruster_bridge", "run_cases.jl").splitlines()
                     if not line.lstrip().startswith("#"))
    row_mark = re.search(r'row = Dict\{String,Any\}\("case_id" => c\.id\)\n\s*historical && \(row\["score_bearing"\] = false\)',
                         code)
    rec_mark = re.search(r'r = run_case\(c, mode\)\n\s*historical && \(r\["score_bearing"\] = false\)', code)
    assert row_mark and rec_mark
    assert rec_mark.end() < code.index("push!(results, r)") and row_mark.end() < code.index("push!(summary, row)")
    assert re.search(r'meta = Dict\{String,Any\}\(', code)   # Dict{String,String} would reject a Bool value
    meta_mark = re.search(r'if historical\n\s*meta\["case_status"\] = case_status\n\s*meta\["score_bearing"\] = false\nend',
                          code)
    assert meta_mark and meta_mark.end() < code.index("JSON3.write(io")


# ---------------------------------------------------------------------------------------------------- validation.py
def test_validation_py_numeric_constants_unchanged():
    assert BASE_NUMERIC_CONSTANTS, "pin missing"
    consts = _code_constants(_read("abep_sim", "validation.py"))
    assert _numeric(consts) == BASE_NUMERIC_CONSTANTS
    assert _constants_sha(consts) == BASE_CONSTANTS_SHA256


def test_validation_py_code_identical_to_base_commit_except_documentation():
    base = _git_show(BASE_COMMIT, "abep_sim/validation.py")
    if base is None:
        pytest.skip(f"base commit {BASE_COMMIT} not available (shallow clone or no git)")
    assert _constants_sha(_code_constants(base)) == BASE_CONSTANTS_SHA256          # the pins describe the base
    cur = _read("abep_sim", "validation.py")
    assert ast.dump(_strip_docs_and_metadata(cur)) == ast.dump(_strip_docs_and_metadata(base))


def test_validation_py_documents_the_unsupported_anchor():
    tree = ast.parse(_read("abep_sim", "validation.py"))
    doc = ast.get_docstring(tree)
    for s in ("HISTORICAL_UNSUPPORTED", "250 V -> 24 mN, 690 W", AUDIT_REL, "paywalled", "no 250 V data",
              "identification/echt_n2/STATUS.json"):
        assert s in doc, s
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "calibration_anchor")
    assert "HISTORICAL_UNSUPPORTED" in ast.get_docstring(fn)
    meta = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "CAL_ANCHOR_PROVENANCE")
    text = meta.value.value
    assert text.startswith("HISTORICAL_UNSUPPORTED") and AUDIT_REL in text and "only ranges" in text


# ---------------------------------------------------------------------------------------------------- status records
def test_status_json_disposition():
    st = json.loads(_read("hallthruster_bridge", "identification", "echt_n2", "STATUS.json"))
    assert st["status"] == "HISTORICAL_UNSUPPORTED"
    assert st["score_bearing"] is False and st["transport_discriminator"] is False
    assert st["independent_scoreable_validation_dataset"] is False
    assert st["disposition"]["supporting_check_preregistered"] is False
    assert any("transport discriminator" in s for s in st["disposition"]["must_not_be_used_for"])
    assert any("replacement simulation cases" in s for s in st["disposition"]["must_not_be_used_for"])
    audit_path = os.path.join(ROOT, st["basis"]["audit_file"])
    assert st["basis"]["audit_file"] == AUDIT_REL
    with open(audit_path, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == st["basis"]["audit_sha256"]
    audit = json.loads(_read(*AUDIT_REL.split("/")))
    assert st["basis"]["audit_verdict"] == audit["conclusion"]["verdict"]
    assert st["disposition"]["forced_assumptions"] == audit["conclusion"]["forced_assumptions"]
    paths = [a["path"] for a in st["historical_artifacts"]]
    assert "hallthruster_bridge/cases/echt_n2.json" in paths and any(p.startswith("abep_sim/validation.py") for p in paths)
    assert all(a["status"] == "HISTORICAL_UNSUPPORTED" and a["score_bearing"] is False for a in st["historical_artifacts"])
    assert os.path.isfile(os.path.join(ROOT, st["companion_document"]))


def test_status_items_carry_source_and_evidence_class():
    st = json.loads(_read("hallthruster_bridge", "identification", "echt_n2", "STATUS.json"))
    assert st["items"]
    for it in st["items"]:
        assert it["source"] and it["use"], it["item"]
        assert it["quantity_type"].startswith(EVIDENCE_TYPES), it["item"]
        assert it["evidence_level"] is None or it["evidence_level"] in range(1, 8), it["item"]
        if it["evidence_level"] is None:
            assert it["value"].startswith("TBD — requires"), it["item"]
    unsupported = [it for it in st["items"] if it["use"].startswith("HISTORICAL_UNSUPPORTED")]
    assert len(unsupported) == 3 and all(it["evidence_level"] == 7 for it in unsupported)
    assert all(it["quantity_type"].startswith("assumed") for it in unsupported)


def test_status_markdown_states_the_disposition():
    md = _read("hallthruster_bridge", "identification", "echt_n2", "ECHT_N2_EVIDENCE_STATUS.md")
    for s in ("HISTORICAL_UNSUPPORTED", "Not a transport discriminator", "Not score-bearing", "ABEP_ALLOW_HISTORICAL=1",
              "No such check is pre-registered", "Replacement simulation cases", "echt_n2_evidence_audit_v1.json"):
        assert s in md, s


def test_evidence_register_has_echt_rows():
    rows = [line for line in _read("docs", "EVIDENCE.md").splitlines()
            if (line.startswith("|") and "ECHT" in line) or line.startswith("| `cases/echt_n2.json`")
            or line.startswith("| 0-D calibration anchor")]
    assert len(rows) >= 7
    for r in rows:
        cells = [c.strip() for c in r.strip().strip("|").split(" | ")]
        assert len(cells) == 4, r
        assert cells[1] in ("3", "7"), r
    assert sum("HISTORICAL_UNSUPPORTED" in r for r in rows) >= 3
    assert any(r.startswith("| `cases/echt_n2.json`") and "| 7 | assumed |" in r for r in rows)
    assert any(r.startswith("| 0-D calibration anchor") and "| 7 | assumed (unverified) |" in r for r in rows)

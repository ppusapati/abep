"""ECR source evidence audit (docs/evidence/ecr_source/): schema, sourcing, and independent recomputation.

- the matrix validates against its JSON Schema (a small draft-2020-12 subset validator, no third-party dependency);
- the committed matrix is exactly what the builder script produces (numbers come from a committed script);
- every entry, and every number in it, carries a source (citation + DOI/URL + access mode) and an evidence class;
- every derived value is recomputed here from CODATA 2022 with independently written formulas;
- constants the sources state (875 G at 2.45 GHz, cutoffs at 2.45/4.2/5.8 GHz) agree with the formulas;
- the markdown references only entries that exist, keeps ABEP chamber conditions TBD, and makes no ranking claims.
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "evidence" / "ecr_source"
MATRIX = DIR / "ecr_evidence_matrix.json"
SCHEMA = DIR / "ecr_evidence_matrix.schema.json"
MD = DIR / "ECR_SOURCE_EVIDENCE.md"
BUILDER = DIR / "build_ecr_evidence_matrix.py"

CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}

# CODATA 2022 (NIST), typed in independently of the builder.
E = 1.602176634e-19
ME = 9.1093837139e-31
EPS0 = 8.8541878188e-12
KB = 1.380649e-23


@pytest.fixture(scope="module")
def doc():
    return json.loads(MATRIX.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_id(doc):
    return {e["id"]: e for e in doc["entries"]}


# ------------------------------------------------------------------------------ minimal JSON Schema validator
def _type_ok(inst, t):
    if isinstance(t, list):
        return any(_type_ok(inst, x) for x in t)
    return {
        "null": inst is None,
        "boolean": isinstance(inst, bool),
        "object": isinstance(inst, dict),
        "array": isinstance(inst, list),
        "string": isinstance(inst, str),
        "number": isinstance(inst, (int, float)) and not isinstance(inst, bool),
        "integer": isinstance(inst, int) and not isinstance(inst, bool),
    }[t]


def _resolve_ref(ref, root):
    assert ref.startswith("#/"), ref
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(inst, sch, root, path="$"):
    """Raise AssertionError on the first violation. Supports the keywords used by the ECR schema."""
    if "$ref" in sch:
        validate(inst, _resolve_ref(sch["$ref"], root), root, path)
    if "type" in sch:
        assert _type_ok(inst, sch["type"]), f"{path}: type {sch['type']} expected, got {type(inst).__name__}"
    if "const" in sch:
        assert inst == sch["const"], f"{path}: const {sch['const']!r} expected, got {inst!r}"
    if "enum" in sch:
        assert inst in sch["enum"], f"{path}: {inst!r} not in {sch['enum']}"
    if isinstance(inst, str):
        if "minLength" in sch:
            assert len(inst) >= sch["minLength"], f"{path}: shorter than {sch['minLength']}"
        if "pattern" in sch:
            assert re.search(sch["pattern"], inst), f"{path}: {inst!r} !~ {sch['pattern']}"
    if isinstance(inst, list):
        if "minItems" in sch:
            assert len(inst) >= sch["minItems"], f"{path}: fewer than {sch['minItems']} items"
        if "maxItems" in sch:
            assert len(inst) <= sch["maxItems"], f"{path}: more than {sch['maxItems']} items"
        if "items" in sch:
            for i, x in enumerate(inst):
                validate(x, sch["items"], root, f"{path}[{i}]")
    if isinstance(inst, dict):
        for k in sch.get("required", []):
            assert k in inst, f"{path}: missing required {k!r}"
        props = sch.get("properties", {})
        for k, v in inst.items():
            if k in props:
                validate(v, props[k], root, f"{path}.{k}")
            elif "additionalProperties" in sch:
                ap = sch["additionalProperties"]
                if ap is False:
                    raise AssertionError(f"{path}: additional property {k!r} not allowed")
                if isinstance(ap, dict):
                    validate(v, ap, root, f"{path}.{k}")
    if "anyOf" in sch:
        errors = []
        for sub in sch["anyOf"]:
            try:
                validate(inst, sub, root, path)
                break
            except AssertionError as exc:
                errors.append(str(exc))
        else:
            raise AssertionError(f"{path}: no anyOf branch matched: {errors}")
    for sub in sch.get("allOf", []):
        validate(inst, sub, root, path)
    if "not" in sch:
        try:
            validate(inst, sch["not"], root, path)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"{path}: matched a 'not' schema")
    if "if" in sch:
        try:
            validate(inst, sch["if"], root, path)
            matched = True
        except AssertionError:
            matched = False
        if matched and "then" in sch:
            validate(inst, sch["then"], root, path)
        if not matched and "else" in sch:
            validate(inst, sch["else"], root, path)


def test_matrix_validates_against_schema(doc, schema):
    validate(doc, schema, schema)


def test_validator_is_not_vacuous(doc, schema):
    bad = json.loads(json.dumps(doc))
    del bad["entries"][0]["source"]
    with pytest.raises(AssertionError, match="source"):
        validate(bad, schema, schema)
    bad = json.loads(json.dumps(doc))
    bad["entries"][0]["evidence_class"] = "measured-ish"
    with pytest.raises(AssertionError):
        validate(bad, schema, schema)
    bad = json.loads(json.dumps(doc))
    d = next(e for e in bad["entries"] if e["id"].startswith("ECR-D"))
    del d["derivation"]
    with pytest.raises(AssertionError, match="derivation"):
        validate(bad, schema, schema)
    bad = json.loads(json.dumps(doc))
    bad["entries"][0]["conditions"].pop("B_T")
    with pytest.raises(AssertionError, match="B_T"):
        validate(bad, schema, schema)


# ------------------------------------------------------------------------------------------ reproducibility
def _load_builder():
    spec = importlib.util.spec_from_file_location("build_ecr_evidence_matrix", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_committed_matrix_equals_builder_output():
    mod = _load_builder()
    assert mod.render(mod.build()) == MATRIX.read_text(encoding="utf-8"), \
        "run: python docs/evidence/ecr_source/build_ecr_evidence_matrix.py"


# ------------------------------------------------------------------------------------ sourcing/classification
def _numbers(x):
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return []
    if isinstance(x, (int, float)):
        return [x]
    if isinstance(x, list):
        return [v for item in x for v in _numbers(item)]
    if isinstance(x, dict):
        return [v for item in x.values() for v in _numbers(item)]
    return []


def test_every_numeric_entry_is_sourced_and_classified(doc):
    ids = [e["id"] for e in doc["entries"]]
    assert len(ids) == len(set(ids)), "duplicate ids"
    url = re.compile(r"^(https?://\S+|10\.\d{4,9}/\S+)$")
    for e in doc["entries"]:
        s = e["source"]
        assert s["citation"].strip() and url.match(s["doi_or_url"]), e["id"]
        assert s["access"] in ("open", "abstract_only"), e["id"]
        assert s["source_id"] in doc["sources"], e["id"]
        reg = doc["sources"][s["source_id"]]
        assert reg["citation"] == s["citation"] and reg["doi_or_url"] == s["doi_or_url"], e["id"]
        assert s["locator"].strip(), e["id"]
        assert e["evidence_class"] in CLASSES, e["id"]
        nums = _numbers(e["value"]) + _numbers(e["conditions"])
        for v in nums:
            assert math.isfinite(v), (e["id"], v)
        if _numbers(e["value"]):
            assert e["uncertainty"].strip() and e["units"].strip(), e["id"]
        else:  # non-numeric value: must be explicitly qualitative
            assert e.get("value_qualifier") == "qualitative", e["id"]
    c = doc["constants"]
    assert c["source"]["doi_or_url"].startswith("https://physics.nist.gov/"), "constants must cite CODATA/NIST"


def test_abstract_only_sources_are_labelled_and_propagate(doc, by_id):
    for sid, s in doc["sources"].items():
        if s["access"] == "abstract_only":
            assert "abstract" in s["citation"].lower() or "Abstract" in s["citation"], sid
    for e in doc["entries"]:
        if e["source"]["access"] == "abstract_only" and e["id"].startswith("ECR-E"):
            assert e["source"]["locator"].lower().startswith("abstract"), e["id"]
        if not e["id"].startswith("ECR-D"):
            continue
        refs = [v["ref"] for v in e["derivation"]["inputs"].values() if isinstance(v, dict) and "ref" in v]
        if any(by_id[r]["source"]["access"] == "abstract_only" for r in refs):
            assert e["source"]["access"] == "abstract_only", f"{e['id']} derives from an abstract-only entry"


def test_regime_match_yes_only_for_unit_identities(doc):
    yes = {e["id"] for e in doc["entries"] if e["applicability_to_abep"]["regime_match"] == "yes"}
    assert yes <= {"ECR-D025", "ECR-D028"}, yes


def test_constants_are_codata_2022(doc):
    c = doc["constants"]
    assert c["e_C"] == E and c["m_e_kg"] == ME and c["eps0_F_per_m"] == EPS0 and c["k_B_J_per_K"] == KB


# ------------------------------------------------------------------------------ independent recomputation
def _b_res(f):
    return 2 * math.pi * f * ME / E


def _n_c(f):
    return EPS0 * ME * (2 * math.pi * f) ** 2 / E ** 2


def _div(a, b):
    return [x / b for x in a] if isinstance(a, list) else a / b


def _sccm():
    return 101325.0 * 1e-6 / (KB * 273.15) / 60.0


INDEPENDENT = {
    "b_res_T": lambda f_Hz: _b_res(f_Hz),
    "n_cutoff_m3": lambda f_Hz: _n_c(f_Hz),
    "ratio": lambda num, den: _div(num, den),
    "db_to_power_fraction": lambda loss_dB: math.pow(10.0, -loss_dB / 10.0),
    "elementwise_ratio": lambda num, den: [a / b for a, b in zip(num, den)],
    "sum_ratio": lambda num, den: math.fsum(num) / den,
    "power_per_current": lambda P_W, I_A: [P_W / i for i in I_A] if isinstance(I_A, list) else P_W / I_A,
    "w_per_a_to_ev_per_ion": lambda: 1.0,
    "neutral_density_m3": lambda p_Pa, T_K: ([p / (KB * T_K) for p in p_Pa] if isinstance(p_Pa, list) else
                                             [p_Pa / (KB * t) for t in T_K] if isinstance(T_K, list) else
                                             p_Pa / (KB * T_K)),
    "particles_per_s_per_sccm": lambda: _sccm(),
    "equivalent_current_A": lambda sccm: E * sccm * _sccm(),
    "br_reversible_change_pct": lambda alpha_pct_per_C, dT_C: ([a * dT_C for a in alpha_pct_per_C]
                                                             if isinstance(alpha_pct_per_C, list)
                                                             else alpha_pct_per_C * dT_C),
    "difference": lambda a, b: a - b,
    "mtorr_to_pa": lambda p_mTorr: [x * 0.133322368 for x in p_mTorr] if isinstance(p_mTorr, list)
    else p_mTorr * 0.133322368,
}


def _resolve(v, by_id):
    if isinstance(v, dict) and "ref" in v:
        out = by_id[v["ref"]]["value"]
        return out[v["index"]] if "index" in v else out
    return v


def _close(a, b, rel=1e-3):
    if isinstance(a, list) or isinstance(b, list):
        assert isinstance(a, list) and isinstance(b, list) and len(a) == len(b), (a, b)
        return all(_close(x, y, rel) for x, y in zip(a, b))
    return math.isclose(a, b, rel_tol=rel, abs_tol=1e-12)


def test_every_derived_value_is_recomputed_independently(doc, by_id):
    derived = [e for e in doc["entries"] if e["id"].startswith("ECR-D")]
    assert len(derived) >= 30
    for e in derived:
        der = e["derivation"]
        assert der["function"] in INDEPENDENT, e["id"]
        kwargs = {k: _resolve(v, by_id) for k, v in der["inputs"].items()}
        expected = INDEPENDENT[der["function"]](**kwargs)
        assert _close(e["value"], expected), (e["id"], e["value"], expected)


def test_resonance_and_cutoff_formula_values(by_id):
    # spot values a reader can check by hand
    assert math.isclose(by_id["ECR-D001"]["value"], 0.08752, rel_tol=1e-3)
    assert math.isclose(by_id["ECR-D005"]["value"], 7.446e16, rel_tol=1e-3)
    assert math.isclose(by_id["ECR-D008"]["value"], 4.173e17, rel_tol=1e-3)
    # n_c scales with f^2 and B_res with f
    assert math.isclose(_n_c(4.9e9) / _n_c(2.45e9), 4.0, rel_tol=1e-12)
    assert math.isclose(_b_res(4.9e9) / _b_res(2.45e9), 2.0, rel_tol=1e-12)


@pytest.mark.parametrize("eid, f, kind, half_ulp", [
    ("ECR-E001", 2.45e9, "B", 0.00005),   # 875 G   -> 0.0875 T
    ("ECR-E002", 2.45e9, "B", 0.00005),   # 87.5 mT
    ("ECR-E003", 4.2e9, "B", 0.0005),     # 150 mT
    ("ECR-E004", 2.45e9, "n", 0.05e16),   # 7.4e16
    ("ECR-E005", 4.2e9, "n", 0.05e17),    # 2.2e17
    ("ECR-E006", 5.8e9, "n", 0.5e17),     # 4e17
])
def test_source_stated_constants_agree_with_formula(by_id, eid, f, kind, half_ulp):
    stated = by_id[eid]["value"]
    computed = _b_res(f) if kind == "B" else _n_c(f)
    assert abs(stated - computed) <= half_ulp, (eid, stated, computed)


# ----------------------------------------------------------------------------------------------- markdown
def test_markdown_references_existing_entries_and_sections(by_id):
    text = MD.read_text(encoding="utf-8")
    tokens = set(re.findall(r"(?<![A-Za-z0-9])(?:ECR-)?([ED]\d{3})(?![0-9])", text))
    assert tokens, "markdown cites no entries"
    missing = sorted(t for t in tokens if f"ECR-{t}" not in by_id)
    assert not missing, f"markdown cites unknown entries: {missing}"
    for heading in ("## 5. Regime match", "## 6. What must be measured", "## 3. Resonance field and cutoff"):
        assert heading in text, heading
    # the ABEP column stays TBD pending the upstream ICD
    regime = text.split("## 5. Regime match", 1)[1].split("## 6.", 1)[0]
    assert "TBD — requires ICD chamber pressure/density" in regime
    assert regime.count("TBD") >= 6


def test_markdown_entry_counts_match_matrix(doc):
    text = MD.read_text(encoding="utf-8")
    m = re.search(r"(\d+) literature entries \(`ECR-E###`\) and (\d+) derived entries", text)
    assert m, "entry counts not stated in the markdown"
    n_e = sum(1 for e in doc["entries"] if e["id"].startswith("ECR-E"))
    n_d = sum(1 for e in doc["entries"] if e["id"].startswith("ECR-D"))
    assert (int(m.group(1)), int(m.group(2))) == (n_e, n_d)


def test_builder_notes_reference_existing_entries(doc, by_id):
    for e in doc["entries"]:
        blob = json.dumps(e["applicability_to_abep"]) + e["uncertainty"] + e["quantity"]
        for t in re.findall(r"ECR-([ED]\d{3})", blob):
            assert f"ECR-{t}" in by_id, (e["id"], t)


FORBIDDEN = [
    r"best candidate", r"recommended candidate", r"\bpromot", r"demonstrated ABEP closure",
    r"architecture winner",
    r"\b(ECR|RF|helicon|microwave)\b[^.\n|]{0,40}\b(beats?|outperforms?|superior to|better than|worse than|"
    r"inferior to)\b",
]


@pytest.mark.parametrize("path", [MD, MATRIX, BUILDER])
def test_no_ranking_or_promotion_language(path):
    text = path.read_text(encoding="utf-8")
    for pat in FORBIDDEN:
        m = re.search(pat, text, flags=re.IGNORECASE)
        assert m is None, f"{path.name}: forbidden phrase {m.group(0)!r}"

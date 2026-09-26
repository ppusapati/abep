"""Checks for the Hall sustainment / ignition evidence matrix (docs/evidence/hall_sustainment/).

Evidence audit only: these tests check structure, sourcing and reproducibility. They never judge physics.
* the matrix validates against its JSON Schema (a small built-in validator; jsonschema too if installed);
* every entry and number is sourced, carries an allowed evidence class, a unit and an uncertainty field;
* repository-derived values (P5-N2, ECHT-N2, v1 context counts) match the repository files, recomputed here
  independently of the builder;
* the builder reproduces the committed JSON and the generated section of the Markdown exactly;
* v1 simulation results are never used as evidence; licence-restricted theses are not redistributed.
"""
import hashlib
import importlib.util
import json
import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIR = os.path.join(ROOT, "docs", "evidence", "hall_sustainment")
MATRIX = os.path.join(DIR, "hall_sustainment_matrix.json")
SCHEMA = os.path.join(DIR, "hall_sustainment_matrix.schema.json")
MDFILE = os.path.join(DIR, "HALL_SUSTAINMENT_EVIDENCE.md")
BUILDER = os.path.join(DIR, "build_hall_sustainment_matrix.py")
IDENT = os.path.join(ROOT, "hallthruster_bridge", "identification")

CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}


def _json(path):
    with open(path) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def m():
    return _json(MATRIX)


@pytest.fixture(scope="module")
def entries(m):
    return {e["id"]: e for e in m["entries"]}


# ---------------------------------------------------------------- minimal JSON Schema validator (subset used here)
def _resolve(root, ref):
    assert ref.startswith("#/"), ref
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is_type(x, t):
    if t == "integer":
        return isinstance(x, int) and not isinstance(x, bool)
    if t == "number":
        return isinstance(x, (int, float)) and not isinstance(x, bool)
    return isinstance(x, _TYPES[t])


def _validate(x, s, root, path="$"):
    errs = []
    if "$ref" in s:
        return _validate(x, _resolve(root, s["$ref"]), root, path)
    if "anyOf" in s:
        if all(_validate(x, sub, root, path) for sub in s["anyOf"]):
            errs.append("%s: matches no anyOf branch" % path)
        return errs
    if "type" in s:
        ts = s["type"] if isinstance(s["type"], list) else [s["type"]]
        if not any(_is_type(x, t) for t in ts):
            return ["%s: type %s not in %s" % (path, type(x).__name__, ts)]
    if "enum" in s and x not in s["enum"]:
        errs.append("%s: %r not in enum" % (path, x))
    if isinstance(x, str):
        if "pattern" in s and not re.search(s["pattern"], x):
            errs.append("%s: %r !~ %s" % (path, x, s["pattern"]))
        if len(x) < s.get("minLength", 0):
            errs.append("%s: too short" % path)
    if _is_type(x, "number"):
        if "minimum" in s and x < s["minimum"]:
            errs.append("%s: < minimum" % path)
        if "maximum" in s and x > s["maximum"]:
            errs.append("%s: > maximum" % path)
    if isinstance(x, dict):
        for k in s.get("required", []):
            if k not in x:
                errs.append("%s: missing %s" % (path, k))
        props = s.get("properties", {})
        extra = s.get("additionalProperties", True)
        for k, v in x.items():
            if k in props:
                errs += _validate(v, props[k], root, "%s.%s" % (path, k))
            elif extra is False:
                errs.append("%s: unexpected key %s" % (path, k))
            elif isinstance(extra, dict):
                errs += _validate(v, extra, root, "%s.%s" % (path, k))
    if isinstance(x, list):
        if len(x) < s.get("minItems", 0):
            errs.append("%s: fewer than minItems" % path)
        if "items" in s:
            for i, v in enumerate(x):
                errs += _validate(v, s["items"], root, "%s[%d]" % (path, i))
    return errs


def test_schema_validates(m):
    schema = _json(SCHEMA)
    errs = _validate(m, schema, schema)
    assert not errs, errs[:20]
    try:
        import jsonschema
    except ImportError:
        return
    jsonschema.validate(m, schema)


def test_validator_rejects_bad_entries(m):
    """The built-in validator must actually catch violations (guards against a vacuous schema test)."""
    schema = _json(SCHEMA)
    bad = json.loads(json.dumps(m))
    bad["entries"][0]["outcome"] = "probably_fine"
    bad["entries"][1]["quantities"] = [{"name": "x", "value": 1, "unit": "V"}]
    bad["entries"][2]["implication"]["abep_regime"] = "similar to ABEP"
    bad["entries"][3]["flow"]["evidence_class"] = "estimated"
    errs = _validate(bad, schema, schema)
    joined = "\n".join(errs)
    for needle in ("outcome", "missing evidence_class", "abep_regime", "flow.evidence_class"):
        assert needle in joined, needle


# ---------------------------------------------------------------- sourcing and evidence classes
def _all_quantities(e):
    return [e["flow"], e["voltage"], e["magnetic_field"]] + list(e["quantities"])


def test_entries_sourced_and_classed(m):
    ids = [e["id"] for e in m["entries"]]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    for e in m["entries"]:
        assert e["evidence_class"] in CLASSES and e["ignition"]["evidence_class"] in CLASSES
        for sid in e["sources"]:
            assert sid in m["sources"], (e["id"], sid)
        for qd in _all_quantities(e):
            assert qd["evidence_class"] in CLASSES, (e["id"], qd["name"])
            assert qd["unit"].strip(), (e["id"], qd["name"])
            assert qd["source"] in e["sources"], (e["id"], qd["name"], qd["source"])
            assert str(qd["uncertainty"]).strip(), (e["id"], qd["name"])
            v = qd["value"]
            if isinstance(v, list) and len(v) == 2:
                assert v[0] <= v[1], (e["id"], qd["name"], v)
            if isinstance(v, str):
                assert re.match(r"^(not |TBD - requires |< |> |from |figure data )", v), (e["id"], qd["name"], v)
        assert e["implication"]["abep_regime"].startswith("TBD - requires the upstream ICD")
        for k in ("statement", "uncertainty", "applicability_limits"):
            assert len(e["implication"][k]) > 3, (e["id"], k)


def test_source_access_records(m):
    for sid, s in m["sources"].items():
        acc = s["access"]
        if acc in ("open_full_text", "open_full_text_restrictive_license"):
            assert s["urls_accessed"] and s["sha256"], sid
        if acc == "licensed_full_text_sha_pinned":
            assert s["sha256"] and s["doi"], sid
        if acc == "abstract_only":
            assert s["urls_accessed"], sid
            assert s["sha256"] is None, sid
        if acc == "not_accessed":
            assert s["sha256"] is None, sid
            assert "reported by" in s["access_note"] or "second-hand" in s["access_note"], sid
        if acc == "repository_audit_file":
            for p in s["repository_files"]:
                assert os.path.exists(os.path.join(ROOT, p)), p
        if acc == "open_full_text_restrictive_license":
            assert "NC" in s["license"], sid


def test_secondary_reports_are_level_5(m):
    """Entries whose numbers all come from the review are second-hand: evidence level 5, primary marked not accessed."""
    review = "ANDREUSSI2022"
    for e in m["entries"]:
        qs = [qd for qd in _all_quantities(e) if not isinstance(qd["value"], str)]
        if qs and all(qd["source"] == review for qd in qs):
            assert e["evidence_level"] == 5, e["id"]
        if e["evidence_level"] == 5:
            assert any(m["sources"][s]["access"] in ("not_accessed", "abstract_only") for s in e["sources"]), e["id"]


def test_outcomes_and_ignition_modes_cover_the_question(m):
    outs = {e["outcome"] for e in m["entries"]}
    assert {"sustained", "extinguished"} <= outs
    modes = {e["ignition"]["mode"] for e in m["entries"]}
    assert {"direct_on_atmospheric_gas", "xenon_start_then_transition", "xenon_admixture_required"} <= modes
    for e in m["entries"]:
        if e["preionizer"]["present"]:
            assert e["preionizer"]["type"], e["id"]
            assert e["implication"]["direction"] != "operation_without_preionizer_demonstrated", e["id"]
        if e["implication"]["direction"].startswith("operation_without_preionizer"):
            assert not e["preionizer"]["present"] and e["outcome"] == "sustained", e["id"]
            assert not e["propellant"]["xenon_in_anode_flow"], e["id"]
        if e["implication"]["direction"] == "operation_without_preionizer_demonstrated_xenon_start":
            assert e["ignition"]["mode"] == "xenon_start_then_transition", e["id"]


# ---------------------------------------------------------------- repository-derived values vs repository files
def test_p5_values_match_repository(entries):
    a = _json(os.path.join(IDENT, "brabston_p5_n2_measurement_audit_v1.json"))
    pts = a["points"]
    t2 = [pts[k]["table2"] for k in sorted(pts)]

    def qn(e, name):
        return next(qd for qd in e["quantities"] if qd["name"] == name)["value"]

    e = entries["E01"]
    assert e["repository_derived"] is True
    assert e["flow"]["value"] == [min(t["mdot_anode_mg_s"] for t in t2), max(t["mdot_anode_mg_s"] for t in t2)] == [5.0, 5.4]
    assert e["voltage"]["value"] == [min(t["V_d"] for t in t2), max(t["V_d"] for t in t2)] == [231.9, 278.6]
    assert e["magnetic_field"]["value"] == 130 and all(t["B_peak_G"] == 130 for t in t2)
    assert qn(e, "cathode Xe mass flow") == 0.44 and all(t["mdot_cathode_Xe_mg_s"] == 0.44 for t in t2)
    assert qn(e, "discharge power") == [3.08, 4.81]
    assert qn(e, "chamber pressure (N2-corrected ion gauge)") == [1.14e-5, 2.14e-5]
    idr = [pts[k]["I_d_raw_A"] for k in pts]
    lo, hi = qn(e, "discharge current, raw = P_d/V_d")
    assert lo == pytest.approx(min(idr), abs=1e-4) and hi == pytest.approx(max(idr), abs=1e-4)
    for t in t2:   # raw I_d really is P_d/V_d
        assert 1000 * t["P_d_kW"] / t["V_d"] == pytest.approx(pts[[k for k in pts if pts[k]["table2"] is t][0]]["I_d_raw_A"])
    assert qn(e, "thrust, ingestion-corrected (N1..N5)") == [pts["N1"]["T_corr_mN"], pts["N5"]["T_corr_mN"]] == [61.4, 90.0]
    fr = [t["mdot_cathode_Xe_mg_s"] / t["mdot_anode_mg_s"] for t in t2]
    lo, hi = qn(e, "cathode Xe / anode N2 mass-flow ratio")
    assert lo == pytest.approx(min(fr), abs=1e-4) and hi == pytest.approx(max(fr), abs=1e-4)
    f = _json(os.path.join(IDENT, "p5_n2_measurement_audit_findings_v1.json"))
    assert "225 V" in f["admissible_targets"]["sustained_discharge"]["evidence"]
    assert entries["E02"]["voltage"]["value"] == [225, 275] and entries["E02"]["outcome"] == "extinguished"


def test_echt_values_match_repository(entries):
    a = _json(os.path.join(IDENT, "echt_n2", "echt_n2_evidence_audit_v1.json"))
    v = a["values"]
    rows = v["operating_points_table_6_1"]["rows"]
    perf = v["performance_table_6_2"]["rows"]
    e = entries["E03"]

    def qn(name):
        return next(qd for qd in e["quantities"] if qd["name"] == name)["value"]

    assert e["repository_derived"] is True
    assert e["flow"]["value"] == 2.06 and {r[3] for r in rows} == {2.06}
    assert e["voltage"]["value"] == [min(r[0] for r in rows), max(r[0] for r in rows)] == [180, 220]
    assert qn("discharge current") == [min(r[1] for r in rows), max(r[1] for r in rows)] == [1.5, 3.9]
    assert qn("magnet coil current") == [0.8, 3.0]
    assert qn("cathode Ar mass flow") == [min(r[4] for r in rows), max(r[4] for r in rows)] == [0.15, 0.74]
    assert qn("chamber pressure (ion gauge)") == [min(r[6] for r in rows), max(r[6] for r in rows)]
    assert e["magnetic_field"]["value"] == v["magnetic_field"]["measured_Bz_at_2A"]["plateau_mean_4.7_8.3cm_G"] == 85.3
    assert qn("thrust, one-side reduction (7 runs)") == [min(p["T_mN"] for p in perf), max(p["T_mN"] for p in perf)]
    tav = [p["T_avg_mN"] for p in perf if p["T_avg_mN"] is not None]
    assert qn("thrust, averaged reduction (4 runs)") == [min(tav), max(tav)] and len(tav) == 4
    assert qn("channel length") == v["geometry"]["channel_length"]["value_mm"] == 86
    assert qn("channel height") == v["geometry"]["channel_height"]["value_mm"] == 10
    assert qn("anode power, thrust runs") == [min(p["P_anode_W"] for p in perf), max(p["P_anode_W"] for p in perf)]
    for r in v["performance_table_6_2"]["unstable_runs"]:
        assert r.replace("Run ", "") in e["outcome_statement"]
    assert e["propellant"]["cathode_gas"] == "Ar" and "argon" in v["cathode"]["gas"]["value"]
    assert entries["E04"]["flow"]["value"] == 1.6 and "1.6 mg/s" in v["stability_oscillations"]["value"]
    t = _json(os.path.join(IDENT, "echt_n2", "echt_table_checks_v1.json"))
    assert {r["run"] for r in t["runs"]} == {p["run"] for p in perf}


def test_meta_hashes_and_v1_context(m):
    for k, rec in m["meta"]["repository_inputs"].items():
        with open(os.path.join(ROOT, rec["path"]), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == rec["sha256"], k
    s = _json(os.path.join(ROOT, "hallthruster_bridge", "validation", "p5_n2_campaign_v1_vacuum_scores.json"))
    ctx = m["context_not_evidence"]["p5_n2_v1_vacuum"]
    assert ctx["n_records"] == s["n_records"] == 1080
    assert ctx["vacuum_status_counts"] == s["status_counts"]["vacuum"]
    assert ctx["vacuum_status_counts"] == {"OUT_OF_DOMAIN": 1428, "FAIL_VALIDATION": 700, "PASS": 32}
    assert sum(ctx["vacuum_status_counts"].values()) == 2160
    assert "NOT EVIDENCE" in ctx["status"]


def test_v1_simulation_not_used_as_evidence(m):
    for e in m["entries"]:
        blob = json.dumps(e)
        assert "validation/" not in blob and "campaign_v1" not in blob and "sgb-screen" not in blob, e["id"]
    for sid, s in m["sources"].items():
        for p in s.get("repository_files", []):
            assert "/validation/" not in p and "/campaign/" not in p, sid


def test_language_rules():
    with open(MDFILE) as f:
        md = f.read().lower()
    with open(MATRIX) as f:
        js = f.read().lower()
    for bad in ("best candidate", "recommended candidate", "promot", "would pass if", "is not required",
                "pre-ionizer is required", "architecture winner"):
        assert bad not in md and bad not in js, bad


def test_no_redistributed_source_documents():
    allowed = {"HALL_SUSTAINMENT_EVIDENCE.md", "hall_sustainment_matrix.json", "hall_sustainment_matrix.schema.json",
               "build_hall_sustainment_matrix.py"}
    found = {f for f in os.listdir(DIR) if not f.startswith(".") and f != "__pycache__"}
    assert found <= allowed, found - allowed


# ---------------------------------------------------------------- reproducibility
def _builder():
    spec = importlib.util.spec_from_file_location("build_hall_sustainment_matrix", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_builder_reproduces_committed_files():
    b = _builder()
    built = b.build()
    with open(MATRIX) as f:
        assert f.read() == b.dumps(built)
    with open(MDFILE) as f:
        md = f.read()
    assert b.splice_md(md, b.render_md(built)) == md
    assert b.build() == built   # deterministic


def test_derived_arithmetic(m):
    d = m["derived_checks"]
    assert d["composition_1p27N2_O2_mole_fraction_N2"] == pytest.approx(1.27 / 2.27, abs=1e-4)
    assert d["composition_1p27N2_O2_mass_fraction_N2"] == pytest.approx(1.27 * 28.0134 / (1.27 * 28.0134 + 31.998), abs=1e-4)
    assert d["gurciullo_min_xe_mass_fraction"] == [pytest.approx(0.16 / 1.55, abs=1e-4), pytest.approx(0.16 / 1.49, abs=1e-4)]
    assert d["moskovitz_n2_55sccm_mg_s"] == pytest.approx(1.144, rel=3e-3)   # published conversion agrees within 0.3 %

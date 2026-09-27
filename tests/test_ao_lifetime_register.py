"""Checks for the H-1 lifetime / atomic-oxygen degradation register (fo_ao_lifetime_register).

Covers: deterministic build (--check), schema conformance (small local validator; no jsonschema dependency), evidence
discipline (every numeric value sourced and classed; life numbers only measured / other-device literature / TBD; no
screening candidate or Hall-closure life), referential integrity (mechanisms <-> requirements <-> coupons <-> interface
table), the derived AO environment against the frozen atmosphere, and the 314 h datum against the hall-sustainment
matrix when that file is present. Does not require W3/W4 drafts or any other in-flight lane.
"""
import csv
import importlib.util
import json
import math
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIR = os.path.join(ROOT, "docs", "experiments", "lifetime_ao")
BUILDER = os.path.join(DIR, "build_ao_lifetime_register.py")
JSON_PATH = os.path.join(DIR, "ao_lifetime_register_v1.json")
SCHEMA_PATH = os.path.join(DIR, "ao_lifetime_register_v1.schema.json")
MD_PATH = os.path.join(DIR, "AO_LIFETIME_REGISTER.md")

EVIDENCE_CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}


@pytest.fixture(scope="module")
def reg():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _builder_module():
    spec = importlib.util.spec_from_file_location("build_ao_lifetime_register", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- minimal JSON-schema validator (subset used by the schema) -------------------------------------------------------
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is_type(v, t):
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


# Keywords this validator implements. Annotation-only keywords are accepted without checking. Any other keyword in
# the schema makes the test FAIL (so a keyword outside the subset can never go silently unchecked).
_SUPPORTED_KEYWORDS = {"$ref", "type", "const", "enum", "pattern", "minimum", "maximum", "required", "properties",
                       "additionalProperties", "minItems", "items"}
_ANNOTATION_KEYWORDS = {"$schema", "$id", "$defs", "title", "description"}


def _schema_keywords(s, out, in_properties=False):
    if isinstance(s, dict):
        for k, v in s.items():
            if in_properties:
                _schema_keywords(v, out)
                continue
            out.add(k)
            if k in ("properties", "$defs"):
                _schema_keywords(v, out, in_properties=True)
            elif k in ("items", "additionalProperties") and isinstance(v, dict):
                _schema_keywords(v, out)
    return out


def _validate(v, s, root, path="$"):
    errs = []
    if "$ref" in s:
        ref = s["$ref"]
        assert ref.startswith("#/$defs/"), ref
        return _validate(v, root["$defs"][ref.split("/")[-1]], root, path)
    if "type" in s:
        ts = s["type"] if isinstance(s["type"], list) else [s["type"]]
        if not any(_is_type(v, t) for t in ts):
            return [f"{path}: type {type(v).__name__} not in {ts}"]
    if "const" in s and v != s["const"]:
        errs.append(f"{path}: {v!r} != const {s['const']!r}")
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: {v!r} not in enum")
    if "pattern" in s and isinstance(v, str) and not re.search(s["pattern"], v):
        errs.append(f"{path}: {v!r} does not match {s['pattern']}")
    if "minimum" in s and isinstance(v, (int, float)) and v < s["minimum"]:
        errs.append(f"{path}: below minimum")
    if "maximum" in s and isinstance(v, (int, float)) and v > s["maximum"]:
        errs.append(f"{path}: above maximum")
    if isinstance(v, dict):
        for k in s.get("required", []):
            if k not in v:
                errs.append(f"{path}: missing {k}")
        props = s.get("properties", {})
        ap = s.get("additionalProperties", True)
        for k, vv in v.items():
            if k in props:
                errs += _validate(vv, props[k], root, f"{path}.{k}")
            elif ap is False:
                errs.append(f"{path}: unexpected key {k}")
            elif isinstance(ap, dict):
                errs += _validate(vv, ap, root, f"{path}.{k}")
    if isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]:
            errs.append(f"{path}: fewer than {s['minItems']} items")
        if "items" in s:
            for i, vv in enumerate(v):
                errs += _validate(vv, s["items"], root, f"{path}[{i}]")
    return errs


# ---- tests -----------------------------------------------------------------------------------------------------------
def test_build_is_deterministic_and_up_to_date():
    r = subprocess.run([sys.executable, BUILDER, "--check"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def test_builder_is_pure_and_not_wired():
    src = open(BUILDER, encoding="utf-8").read()
    assert not re.search(r"^\s*(import|from)\s+(abep_sim|hallthruster_bridge)", src, re.M)
    assert "archengine" not in re.findall(r"^\s*(?:import|from)\s+(\S+)", src, re.M)


def test_schema_uses_only_supported_keywords(schema):
    used = _schema_keywords(schema, set())
    unknown = used - _SUPPORTED_KEYWORDS - _ANNOTATION_KEYWORDS
    assert not unknown, f"schema keywords not implemented by the local validator: {sorted(unknown)}"


def test_local_validator_rejects_bad_documents(reg, schema):
    bad = json.loads(json.dumps(reg))
    bad["unexpected_top_level"] = 1
    del bad["derived"]["wall_sputter_index"]["entries"][0]["evidence_class"]
    bad["interface_table"]["rows"][0]["related_ids_status"] = "VERIFIED"
    errs = "\n".join(_validate(bad, schema, schema))
    assert "unexpected key unexpected_top_level" in errs
    assert "missing evidence_class" in errs
    assert "not in enum" in errs


def test_schema_conformance(reg, schema):
    errs = _validate(reg, schema, schema)
    assert not errs, "\n".join(errs[:30])


def test_status_draft_and_milestones(reg):
    assert reg["status"] == "DRAFT_FOR_OWNER_REVIEW"
    assert set(reg["milestones"]["supports"]) <= {"A", "B", "C"} and reg["milestones"]["supports"]
    assert reg["milestones"]["to_reach_next"]
    assert all(r["status"] == "PROPOSED" for r in reg["requirements"])
    assert all(p["status"].startswith("PROPOSED") for p in reg["proposed_thresholds"])


def test_required_mechanisms_covered(reg):
    text = " ".join(m["title"].lower() for m in reg["mechanisms"])
    for needle in ("anode", "channel-wall physical sputtering", "cathode emitter", "magnetic", "insulation",
                   "coatings", "external atomic-oxygen"):
        assert needle in text, needle
    species = {s for m in reg["mechanisms"] for s in m["species"]}
    for sp in ("N+", "N2+", "O+", "O2+"):
        assert sp in species
    regimes = {m["energy_regime"] for m in reg["mechanisms"]}
    assert {"thermal_neutral_ram_AO", "sheath_accelerated_ions"} <= regimes


def test_every_mechanism_complete(reg):
    for m in reg["mechanisms"]:
        re_ = m["required_experiment"]
        for k in ("ground_ao_source", "in_thruster_witness", "post_test_metrology"):
            assert re_[k].strip(), (m["id"], k)
        assert m["measurable_quantities"], m["id"]
        assert m["linked_requirements"], m["id"]


def test_evidence_values_are_sourced_and_classed(reg):
    for m in reg["mechanisms"]:
        for e in m["evidence"]:
            assert e["evidence_class"] in EVIDENCE_CLASSES
            assert 1 <= e["evidence_level"] <= 7
            assert e["locator"].strip()
            if e["source_id"] == "REPO":
                assert os.path.exists(os.path.join(ROOT, e["repo_path"])), e["repo_path"]
            else:
                assert e["source_id"] in reg["sources"], e["source_id"]
                src = reg["sources"][e["source_id"]]
                # values quoted from a source must come from a file this lane actually opened
                if e["value"] is not None:
                    assert src["access"] == "open_full_text" and src["sha256_of_accessed_file"], e["source_id"]
                    assert e["verified_by_this_lane"] is True
            assert "NOT transferred" in e["transfer"]


def test_life_numbers_c6(reg):
    """Control C6: no H-1 life from a closure; life = measured on hardware, other-device literature (labelled) or TBD."""
    for m in reg["mechanisms"]:
        ln = m["life_number"]
        assert ln["status"] in {"measured_vyovrinda_hardware", "literature_other_device", "TBD"}
        # nothing is measured on H-1 yet: H-1 does not exist
        assert ln["status"] != "measured_vyovrinda_hardware"
        if ln["status"] == "TBD":
            assert ln["value"] is None and ln["statement"].startswith(("TBD", "not a life"))
        else:
            assert ln["value"] is not None and ln["device"] and ln["source_id"] in reg["sources"]
            assert ln["evidence_class"] in EVIDENCE_CLASSES and ln["locator"]
            assert "H-1" not in ln["device"]
    blob = json.dumps(reg)
    assert "sgb-screen-0" not in blob.replace("sgb-screen-*", "")
    assert not re.search(r"15,?000 h (life|lifetime) (is|of H-1)", blob)


def test_314h_verified_and_consistent_with_repo(reg):
    m01 = next(m for m in reg["mechanisms"] if m["id"] == "AOL-M01")
    e = next(x for x in m01["evidence"] if x["value"] == 314)
    assert e["source_id"] == "ANDREUSSI2022" and e["locator"].startswith("Page 24 of 57")
    assert e["verified_by_this_lane"] and e["evidence_level"] == 5
    assert reg["sources"]["ANDREUSSI2022"]["doi"] == "10.1007/s44205-022-00024-9"
    hs = os.path.join(ROOT, "docs/evidence/hall_sustainment/hall_sustainment_matrix.json")
    if not os.path.exists(hs):
        pytest.skip("hall-sustainment matrix not present")
    d = json.load(open(hs, encoding="utf-8"))
    e07 = next(x for x in d["entries"] if x["id"] == "E07")
    q = next(x for x in e07["quantities"] if x["name"] == "steady duration before first flame-out")
    assert q["value"] == 314 and q["locator"] == "Page 24 of 57" and q["source"] == "ANDREUSSI2022"


def test_requirement_integrity(reg):
    req_ids = [r["id"] for r in reg["requirements"]]
    assert len(req_ids) == len(set(req_ids))
    mech_ids = {m["id"] for m in reg["mechanisms"]}
    for r in reg["requirements"]:
        assert set(r["mechanisms"]) <= mech_ids, r["id"]
        assert r["verification"].strip() and r["rationale"].strip()
    for m in reg["mechanisms"]:
        assert set(m["linked_requirements"]) <= set(req_ids), m["id"]
    # every witness coupon is also a requirement, and vice versa for the WC category
    wc = {w["id"] for w in reg["witness_coupons"]}
    assert wc == {r["id"] for r in reg["requirements"] if r["category"] == "witness_coupon"}
    for w in reg["witness_coupons"]:
        assert set(w["mechanisms"]) <= mech_ids
    # primary-output categories required by the lane brief
    cats = {r["category"] for r in reg["requirements"]}
    assert {"witness_coupon", "replaceable_component", "cathode_exposure", "post_test_metrology"} <= cats


def test_interface_table_covers_every_requirement(reg):
    rows = reg["interface_table"]["rows"]
    covered = {r["requirement"] for r in rows}
    assert covered == {r["id"] for r in reg["requirements"]}
    adopters = {r["adopter"] for r in rows}
    assert {"W3", "W4"} <= adopters


def test_no_unsourced_number_in_requirements(reg):
    """Requirements carry no hidden physical values: numbers only as ids, phases, pinned quotes or explicit TBD."""
    allowed = re.compile(r"AOL-[A-Z]{2}-\d{2}|AOL-M\d{2}|H-1'?|C-1|W\d|HW-[A-Z0-9-]+|INS-\d+|G\d{2}|U\d{2}|H\d|"
                         r"S1|LOCK-[12]|D-15-B|IP-DN|4-wire|0 W|p\. \d+|Eqs?\. \d+(-\d+)?|2 %|314 h|60-100 mtorr|"
                         r"30-600 degC|NASA/TM-2006-214482|1-3|15,000 h|v1|C[1-6]|sgb-screen-\*|2011|0-D|HW-0|"
                         r"H2O|O2|N2|B2O3|SiO2|LaB6|[Ll]ane \d+|PPS1350|gate \d|DEGROH2006|MISSE 2|schema v2|sections? \d+(\.\d+)?")
    for r in reg["requirements"]:
        txt = allowed.sub("", r["requirement"] + " " + r["rationale"] + " " + r["verification"])
        stray = re.findall(r"\d+(?:\.\d+)?", txt)
        assert not stray, (r["id"], stray, txt)


def test_ao_environment_reproduces_from_frozen_atmosphere(reg):
    ao = reg["derived"]["ao_environment"]
    csv_path = os.path.join(ROOT, ao["inputs"]["atmosphere"]["path"])
    rows = {(float(r["alt_km"]), float(r["f107"])): r for r in csv.DictReader(open(csv_path, newline=""))}
    m_o = 16.0 * 1.66053906660e-27
    for t in ao["table"]:
        r = rows[(float(t["alt_km"]), float(t["f107"]))]
        n_o = float(r["rho"]) * float(r["fO"]) / m_o
        v = math.sqrt(3.986004418e14 / (6371.0e3 + t["alt_km"] * 1e3))
        assert math.isclose(t["n_O_m3"], n_o, rel_tol=1e-5)
        assert math.isclose(t["V_orb_m_s"], v, rel_tol=1e-5)
        assert math.isclose(t["ram_flux_atoms_cm2_s"], n_o * v * 1e-4, rel_tol=1e-3)
        assert math.isclose(t["fluence_rfp_mission_26000h_atoms_cm2"], n_o * v * 1e-4 * 26000 * 3600, rel_tol=1e-3)
        assert 4.5 < t["E_ram_O_eV"] < 5.5
    assert {t["alt_km"] for t in ao["table"]} == {180, 200, 230}
    assert ao["evidence_class"] == "model-derived"
    assert "ILLUSTRATIVE" in ao["illustrative_recession_equivalents"]["status"]


def test_builder_constants_match_repository():
    mod = _builder_module()
    spec = importlib.util.spec_from_file_location("abep_constants", os.path.join(ROOT, "abep_sim", "constants.py"))
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    assert mod.AMU_KG == c.AMU and mod.MU_EARTH_M3_S2 == c.MU_EARTH and mod.R_EARTH_M == c.R_EARTH
    assert mod.E_CHARGE_C == c.E_CHARGE and mod.M_O_AMU * mod.AMU_KG == c.M_SPECIES["O"]
    assert mod.RFP_MISSION_H == c.RFP.mission_hours and mod.RFP_FIRING_H == c.RFP.ignition_hours


def test_ao_environment_matches_atmosphere_module(reg):
    pytest.importorskip("pandas")
    from abep_sim.atmosphere import atmosphere
    t = next(x for x in reg["derived"]["ao_environment"]["table"] if x["alt_km"] == 200 and x["f107"] == 150.0)
    a = atmosphere(200, "mean")
    assert math.isclose(a["n_O"], t["n_O_m3"], rel_tol=1e-5)
    assert math.isclose(a["V"], t["V_orb_m_s"], rel_tol=1e-5)


def test_frozen_atmosphere_pin_enforced(tmp_path, monkeypatch):
    mod = _builder_module()
    monkeypatch.setattr(mod, "ATMOSPHERE_CSV_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="sha256"):
        mod.compute_ao_environment()


def test_markdown_mentions_c5_and_primary_output():
    md = open(MD_PATH, encoding="utf-8").read()
    for s in ("control C5", "Witness coupons", "DRAFT", "AOL-WC-01", "AOL-RC-01", "AOL-CX-01", "AOL-PM-01"):
        assert s in md, s


def test_degroh_p1_ao_energy_recorded(reg):
    """DEGROH2006 printed p. 1 states 4.5 eV average ram impact energy (review statement citing its ref. [1])."""
    note = reg["sources"]["DEGROH2006"]["note"]
    assert "4.5 eV" in note and "p. 1" in note and "does not state the AO impact energy" not in note
    flags = " ".join(reg["derived"]["ao_environment"]["flags"])
    assert "4.5 eV" in flags and "NOT corrected" in flags
    m09 = next(m for m in reg["mechanisms"] if m["id"] == "AOL-M09")
    e = next(x for x in m09["evidence"] if x["value"] == 4.5)
    assert e["source_id"] == "DEGROH2006" and e["locator"] == "p. 1" and e["evidence_level"] == 5
    assert "AO energy there is not stated" not in json.dumps(reg)


def test_ratio_and_recession_from_unrounded_fluence(reg):
    ao = reg["derived"]["ao_environment"]
    csv_path = os.path.join(ROOT, ao["inputs"]["atmosphere"]["path"])
    rows = {(float(r["alt_km"]), float(r["f107"])): r for r in csv.DictReader(open(csv_path, newline=""))}
    m_o = 16.0 * 1.66053906660e-27
    fl = []
    for t in ao["table"]:
        r = rows[(float(t["alt_km"]), float(t["f107"]))]
        v = math.sqrt(3.986004418e14 / (6371.0e3 + t["alt_km"] * 1e3))
        f = float(r["rho"]) * float(r["fO"]) / m_o * v * 1e-4 * 26000 * 3600
        fl.append(f)
        assert math.isclose(t["ratio_to_misse2_fluence"], f / 8.43e21, rel_tol=1e-5)
    rr = ao["illustrative_recession_equivalents"]
    assert math.isclose(rr["mission_fluence_range_atoms_cm2"][0], min(fl), rel_tol=1e-5)
    assert math.isclose(rr["mission_fluence_range_atoms_cm2"][1], max(fl), rel_tol=1e-5)
    for row in rr["rows"]:
        ey = row["misse2_erosion_yield_cm3_per_atom"]
        assert math.isclose(row["illustrative_recession_um_at_min_mission_fluence"], ey * min(fl) * 1e4, rel_tol=5e-3)
        assert math.isclose(row["illustrative_recession_um_at_max_mission_fluence"], ey * max(fl) * 1e4, rel_tol=5e-3)


def test_wall_sputter_index_matches_lane32(reg):
    wi = reg["derived"]["wall_sputter_index"]
    db = json.load(open(os.path.join(ROOT, wi["input"]["path"]), encoding="utf-8"))
    assert [e["entry_id"] for e in wi["entries"]] == [e["id"] for e in db["entries"]]
    for ie, de in zip(wi["entries"], db["entries"]):
        assert (ie["projectile"], ie["target"], ie["evidence_class"]) == (de["projectile"], de["target"],
                                                                           de["evidence_class"])
        assert ie["energy_min_eV"] == de["energy_range_eV"].get("min")
        assert ie["energy_max_eV"] == de["energy_range_eV"].get("max")
    # the headline statement of AOL-M02 matches the index: no N/O yield on BN, BN-SiO2 or SiC
    for c in wi["coverage"]:
        if c["projectile"] in ("N+", "N2+", "O+", "O2+") and c["target"] in ("BN-SiO2", "SiC"):
            assert c["status"] == "none_located", c
        if c["projectile"] in ("N+", "N2+", "O2+") and c["target"] == "BN":
            assert c["status"] == "none_located", c
    m02 = next(m for m in reg["mechanisms"] if m["id"] == "AOL-M02")
    assert "derived.wall_sputter_index" in m02["energy_statement"]


def test_wall_sputter_index_pin_enforced(monkeypatch):
    mod = _builder_module()
    monkeypatch.setattr(mod, "WALL_LIFE_DB_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="sha256"):
        mod.compute_wall_sputter_index()


def test_every_draft_id_is_flagged_unverified(reg):
    ud = reg["unmerged_draft_references"]
    assert ud["status"] == "UNVERIFIED_UNMERGED_DRAFT"
    blob = json.dumps({k: v for k, v in reg.items() if k != "unmerged_draft_references"})
    found = set(re.findall(r"\b(?:HW-(?:H1|C1|MC|PIM|ELEC)-\d+|INS-\d+)\b", blob))
    assert found <= set(ud["ids"]), found - set(ud["ids"])
    for row in reg["interface_table"]["rows"]:
        assert row["related_ids_status"] == ("UNVERIFIED_UNMERGED_DRAFT" if row["observed_related_ids"] else "none")
    assert "UNVERIFIED_UNMERGED_DRAFT" in reg["interface_table"]["note"]

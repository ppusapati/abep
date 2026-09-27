"""Hall-map schema v2 (schemas/hallmap/hall_map_schema_v2.json) and the immutable map registry (abep_sim/hallmap_registry.py,
schemas/hallmap/hallmap_registry_v1.json). Lane fo_hallmap_schema_v2_registry.

Every registry test uses TEMPORARY fixtures under tmp_path: obviously synthetic files, never data. No admitted transport
member exists (credible set empty, 2026-09-26), so an admitted ensemble is monkeypatched; the real ensemble is used only
to show that screening candidates are refused. Nothing is simulated and no Julia is run.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import stat

import pytest

from abep_sim import hall_ensemble, hall_map
from abep_sim import hallmap_registry as reg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2_PATH = os.path.join(ROOT, "schemas", "hallmap", "hall_map_schema_v2.json")
REG_SCHEMA_PATH = os.path.join(ROOT, "schemas", "hallmap", "hallmap_registry_v1.json")
V1_PATH = os.path.join(ROOT, "hallthruster_bridge", "hall_map_schema_v1.json")
PIN = hall_map.pinned_commit()
UTC = "2026-09-27T00:00:00Z"
MEMBER = "adm-test-01"          # synthetic admitted id (test only)


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _load(p):
    with open(p) as f:
        return json.load(f)


# ================================================================================================= schema v2
@pytest.fixture(scope="module")
def v2():
    return _load(V2_PATH)


def test_v1_schema_unchanged_and_inherited_by_hash(v2):
    assert v2["schema"] == "hall_map_schema_v2"
    assert v2["inherits"]["file"] == "hallthruster_bridge/hall_map_schema_v1.json"
    assert _sha(V1_PATH) == v2["inherits"]["sha256"], "hall_map_schema_v1.json must stay unchanged"
    assert _load(V1_PATH)["schema"] == "hall_map_schema_v1"
    assert hall_map.SCHEMA_NAME == "hall_map_schema_v1"          # hall_map.py still loads v1 only


def test_v2_solver_basis_is_the_pin(v2):
    b = v2["solver_basis"]
    assert b["pinned_commit"] == PIN and b["version"] == "0.23.1"
    manifest = open(os.path.join(ROOT, "hallthruster_bridge", "Manifest.toml")).read()
    tree = re.search(r"git-tree-sha1 = \"([0-9a-f]{40})\"\s*\nrepo-rev = \"" + PIN, manifest)
    assert tree and tree.group(1) in b["identity_check"]
    assert _sha(os.path.join(ROOT, "hallthruster_bridge", "bridge_lib.jl")) == b["bridge_read"]["sha256"], \
        "bridge_lib.jl changed since the v2 field sources were read: re-inspect wall_ion_metrics"
    for f, h in b["files_read_sha256"].items():
        assert re.fullmatch(r"[0-9a-f]{64}", h), f


def test_v2_added_fields_are_solver_sourced_and_not_computed(v2):
    v1 = _load(V1_PATH)
    assert not set(v2["fields_added"]) & set(v1["fields"])
    assert not set(v2["meta_added"]) & set(v1["meta_required"])
    for k, f in v2["fields_added"].items():
        for key in ("unit", "type", "level", "aggregation", "status", "kind", "solver_variable", "definition",
                    "availability"):
            assert isinstance(f.get(key), str) and f[key].strip(), (k, key)
        assert f["status"] == "not_computed", f"{k}: no producer exists; emitting it needs an owner-approved bridge change"
        assert f["level"].startswith(("map field", "raw record")), k
        assert "HallThruster" in f["solver_variable"] or "src/" in f["solver_variable"] or "as " in f["solver_variable"]
    for k, m in v2["meta_added"].items():
        assert m.get("kind") in ("input", "producer statement"), k


def test_v2_requested_quantities_placed_or_declared_not_supplied(v2):
    added = v2["fields_added"]
    assert "wall_Te_eV" in added                                  # wall-adjacent electron temperature
    assert "wall_see_yield_eff" in added and "wall_loss_model" in v2["meta_added"]   # SEE model + effective yield
    assert "wall_ion_species" in added                            # wall-impact species information
    ns = v2["not_supplied"]
    assert "NS-1_incidence_angle" in ns                           # incidence angle: NOT supplied by the 1-D solver
    assert not any("angle" in k for k in added), "incidence angle must not be a field"
    assert "tan_div_angle" in ns["NS-1_incidence_angle"]["why_not"]      # the unrelated plume diagnostic is named, not used
    for k, n in ns.items():
        assert n["why_not"].strip() and n["would_need"].strip(), k
    mig = v2["migration"]["statement"]
    assert "owner approval" in mig and "NOT done in this lane" in mig


def test_load_hall_map_schema_v2_merges_and_checks_inheritance():
    s = reg.load_hall_map_schema_v2(ROOT)
    assert set(hall_map.REQUIRED_FIELDS) <= set(s["map_fields"])
    assert "wall_Te_eV" in s["map_fields"] and "profile_wall_Te_eV" not in s["map_fields"]
    assert set(hall_map.REQUIRED_META) <= set(s["meta_required"])


def test_load_hall_map_schema_v2_refuses_changed_v1(tmp_path):
    for rel in ("schemas/hallmap/hall_map_schema_v2.json", "hallthruster_bridge/hall_map_schema_v1.json"):
        os.makedirs(tmp_path / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), tmp_path / rel)
    reg.load_hall_map_schema_v2(str(tmp_path))
    p = tmp_path / "hallthruster_bridge" / "hall_map_schema_v1.json"
    p.write_text(p.read_text().replace("hall_map_schema_v1", "hall_map_schema_v1 ", 1))
    with pytest.raises(reg.RegistryError, match="differs"):
        reg.load_hall_map_schema_v2(str(tmp_path))


# ================================================================================================= registry fixtures
def _w(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)
    return _sha(p)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Synthetic repository: real PINNED.toml, fake admission/O4/geometry/B(z)/prereg/chemistry/raw/map files."""
    root = str(tmp_path / "repo")
    os.makedirs(os.path.join(root, "hallthruster_bridge"))
    shutil.copy(os.path.join(ROOT, "hallthruster_bridge", "PINNED.toml"), os.path.join(root, "hallthruster_bridge"))
    h = {}
    h["dec"] = _w(root, "hallthruster_bridge/validation/TEST_decision.json", '{"synthetic": "decision"}')
    h["o4"] = _w(root, "hallthruster_bridge/ensemble/TEST_o4_dispositions.json", '{"synthetic": "o4"}')
    h["ens"] = _w(root, "hallthruster_bridge/ensemble/TEST_ensemble.json", '{"synthetic": "ensemble"}')
    h["geo"] = _w(root, "design/TEST_vy_geometry_rev0.json", '{"synthetic": "geometry"}')
    h["bz"] = _w(root, "design/TEST_vy_bfield_rev0.json", '{"synthetic": "bfield"}')
    h["pre"] = _w(root, "prereg/TEST_hallmap_convergence_frozen.json", '{"synthetic": "frozen prereg"}')
    h["chem"] = _w(root, "chem/TEST_n2_n_snapshot.toml", '# synthetic chemistry snapshot\n')
    raw = b'{"key": "node-1", "synthetic": true}\n'
    os.makedirs(os.path.join(root, "raw"))
    with gzip.GzipFile(os.path.join(root, "raw/TEST_records.jsonl.gz"), "wb", mtime=0) as g:
        g.write(raw)
    h["raw_c"] = hashlib.sha256(raw).hexdigest()
    prov = {"map_set": {"status": "FROZEN"}, "hall_map_schema": {"name": "hall_map_schema_v1"},
            "ensemble_member": {"ensemble_member_id": MEMBER,
                                "admission": {"decision_sha256": h["dec"], "o4_dispositions_sha256": h["o4"]}},
            "hallthruster": {"pinned_commit": PIN, "installed_commit": PIN},
            "geometry": {"sha256": h["geo"]}, "magnetic_field": {"sha256": h["bz"]},
            "numerics": {"convergence": {"prereg_sha256": h["pre"], "verdict": "PASS"}},
            "chemistry": {"config_sha256": h["chem"]}, "raw_records": {"sha256_canonical_jsonl": h["raw_c"]}}
    meta = {"schema": "hall_map_schema_v1", "ensemble_member_id": MEMBER, "hallthruster_commit": PIN,
            "facility_ingestion": False, "provenance": prov}
    _w(root, "maps/TEST_map.json", json.dumps({"meta": meta, "axes": {}, "fields": {}}))
    ens = {"members": [{"ensemble_member_id": MEMBER,
                        "admission": {"decision_file": "validation/TEST_decision.json", "decision_sha256": h["dec"],
                                      "o4_dispositions_file": "ensemble/TEST_o4_dispositions.json",
                                      "o4_dispositions_sha256": h["o4"]}}],
           "screening_candidates": [{"ensemble_member_id": "sgb-screen-01"}]}
    monkeypatch.setattr(hall_ensemble, "load_ensemble", lambda path=None: ens)
    kw = dict(map_file="maps/TEST_map.json", raw_records_file="raw/TEST_records.jsonl.gz", ensemble_member_id=MEMBER,
              ensemble_file="hallthruster_bridge/ensemble/TEST_ensemble.json", chemistry_config_id="n2_n.toml@test",
              chemistry_file="chem/TEST_n2_n_snapshot.toml", geometry_id="VY-H1-TEST rev0",
              geometry_file="design/TEST_vy_geometry_rev0.json", bfield_id="VY-H1-B-TEST rev0",
              bfield_file="design/TEST_vy_bfield_rev0.json", convergence_prereg_id="hallmap-conv-TEST-frozen",
              convergence_prereg_file="prereg/TEST_hallmap_convergence_frozen.json",
              o4_dispositions_file="hallthruster_bridge/ensemble/TEST_o4_dispositions.json",
              admission_decision_file="hallthruster_bridge/validation/TEST_decision.json",
              registered_by="test", registered_utc=UTC)
    return {"root": root, "reg": os.path.join(str(tmp_path), "registry"), "kw": kw, "ens": ens, "meta": meta,
            "h": h}


def _register(r, **over):
    return reg.register(r["reg"], r["root"], **{**r["kw"], **over})


# ================================================================================================= registry behaviour
def test_register_verify_lookup_roundtrip(repo):
    sha = _register(repo)
    rep = reg.verify(repo["reg"], repo["root"])
    assert rep["ok"] and rep["chain_ok"] and rep["n_records"] == 1, rep["problems"]
    assert rep["records"][sha]["status"] == "ACTIVE"
    names = os.listdir(os.path.join(repo["reg"], "records"))
    assert names == [f"000001_{sha[:16]}.json"]
    p = os.path.join(repo["reg"], "records", names[0])
    assert not (os.stat(p).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)), "records are written read-only"
    assert not [n for n in os.listdir(repo["reg"]) if n.startswith(".tmp_")]
    meta_sha = reg.canonical_json_sha256(repo["meta"])
    hit = reg.lookup_map_meta(repo["reg"], repo["root"], meta_sha)
    assert hit["record_sha256"] == sha and hit["record"]["ensemble_member"]["ensemble_member_id"] == MEMBER
    rec = hit["record"]
    assert rec["hallthruster"]["commit"] == PIN
    assert rec["raw_records"]["sha256_canonical_jsonl"] == repo["h"]["raw_c"]
    assert rec["raw_records"]["sha256"] != rec["raw_records"]["sha256_canonical_jsonl"]     # gz bytes vs content


def test_map_meta_hash_form_matches_thermal_life():
    from abep_sim import thermal_life
    meta = {"b": 1, "a": [1, 2], "c": {"z": None}}
    assert reg.canonical_json_sha256(meta) == thermal_life._canonical_sha256(meta)


def test_screening_candidate_and_unknown_ids_refused(repo):
    with pytest.raises(reg.RegistryError, match="SCREENING"):
        _register(repo, ensemble_member_id="sgb-screen-01")
    with pytest.raises(reg.RegistryError, match="not an admitted"):
        _register(repo, ensemble_member_id="adm-unknown")
    assert not os.path.isdir(os.path.join(repo["reg"], "records")) or not os.listdir(os.path.join(repo["reg"], "records"))


def test_real_ensemble_admits_nothing_today():
    real = json.load(open(hall_ensemble.ENSEMBLE_FILE))
    assert real["members"] == []                                  # credible set empty (2026-09-26)
    for sid in hall_ensemble.screening_ids(real):
        with pytest.raises(reg.RegistryError, match="SCREENING"):
            reg._require_admitted(sid, real)


def test_pin_must_equal_pinned_toml(repo):
    bad = "0" * 40
    m = dict(repo["meta"], hallthruster_commit=bad)
    m["provenance"] = json.loads(json.dumps(repo["meta"]["provenance"]))
    m["provenance"]["hallthruster"] = {"pinned_commit": bad, "installed_commit": bad}
    _w(repo["root"], "maps/TEST_map_badpin.json", json.dumps({"meta": m}))
    with pytest.raises(reg.RegistryError, match="PINNED.toml commit"):
        _register(repo, map_file="maps/TEST_map_badpin.json")


def test_admission_and_o4_files_must_be_the_members(repo):
    _w(repo["root"], "hallthruster_bridge/validation/TEST_other_decision.json", '{"other": 1}')
    with pytest.raises(reg.RegistryError, match="admission"):
        _register(repo, admission_decision_file="hallthruster_bridge/validation/TEST_other_decision.json")
    _w(repo["root"], "hallthruster_bridge/ensemble/TEST_other_o4.json", '{"other": 2}')
    with pytest.raises(reg.RegistryError, match="o4_dispositions"):
        _register(repo, o4_dispositions_file="hallthruster_bridge/ensemble/TEST_other_o4.json")


def test_draft_prereg_and_p5_geometry_refused(repo):
    _w(repo["root"], "prereg/hallmap_convergence_prereg_DRAFT.json", '{"status": "DRAFT_PENDING_OWNER"}')
    with pytest.raises(reg.RegistryError, match="DRAFT"):
        _register(repo, convergence_prereg_file="prereg/hallmap_convergence_prereg_DRAFT.json")
    _w(repo["root"], "design/p5_geometry.json", '{"x": 1}')
    with pytest.raises(reg.RegistryError, match="P5/ECHT"):
        _register(repo, geometry_file="design/p5_geometry.json")


def test_provenance_must_agree_and_be_frozen(repo):
    m = json.loads(json.dumps(repo["meta"]))
    m["provenance"]["geometry"]["sha256"] = "f" * 64
    _w(repo["root"], "maps/TEST_map_badprov.json", json.dumps({"meta": m}))
    with pytest.raises(reg.RegistryError, match="geometry.sha256"):
        _register(repo, map_file="maps/TEST_map_badprov.json")
    m = json.loads(json.dumps(repo["meta"]))
    m["provenance"]["map_set"]["status"] = "CANDIDATE"
    _w(repo["root"], "maps/TEST_map_candidate.json", json.dumps({"meta": m}))
    with pytest.raises(reg.RegistryError, match="FROZEN"):
        _register(repo, map_file="maps/TEST_map_candidate.json")
    m = dict(repo["meta"])
    m.pop("provenance")
    _w(repo["root"], "maps/TEST_map_noprov.json", json.dumps({"meta": m}))
    with pytest.raises(reg.RegistryError, match="provenance missing"):
        _register(repo, map_file="maps/TEST_map_noprov.json")


def test_no_defaults_for_evidence_identifiers(repo):
    kw = dict(repo["kw"])
    kw.pop("geometry_file")
    with pytest.raises(TypeError):
        reg.register(repo["reg"], repo["root"], **kw)
    with pytest.raises(reg.RegistryError, match="registered_by"):
        _register(repo, registered_by="")
    with pytest.raises(reg.RegistryError, match="repository-relative"):
        _register(repo, geometry_file=os.path.join(repo["root"], "design/TEST_vy_geometry_rev0.json"))
    with pytest.raises(reg.RegistryError, match="inside the repository"):
        _register(repo, geometry_file="../outside.json")


def test_append_only_no_duplicate_no_overwrite(repo):
    sha = _register(repo)
    with pytest.raises(reg.RegistryError, match="already registered"):
        _register(repo)
    rec = [r for _, s, r in reg.read_records(repo["reg"]) if s == sha][0]
    with pytest.raises(reg.RegistryError, match="append-only|never overwritten"):
        reg._append(repo["reg"], dict(rec, registered_by="someone else"))     # same seq 1: exclusive create refuses
    assert reg.verify(repo["reg"], repo["root"])["ok"]
    assert len(reg.read_records(repo["reg"])) == 1


def test_verify_detects_changed_bound_file(repo):
    _register(repo)
    geo = os.path.join(repo["root"], "design/TEST_vy_geometry_rev0.json")
    with open(geo, "w") as f:
        f.write('{"synthetic": "geometry EDITED"}')
    rep = reg.verify(repo["reg"], repo["root"])
    assert not rep["ok"] and any("geometry" in p for p in rep["problems"])
    with pytest.raises(reg.RegistryError, match="not ACTIVE"):
        reg.lookup_map_meta(repo["reg"], repo["root"], reg.canonical_json_sha256(repo["meta"]))


def test_verify_detects_edited_or_deleted_record(repo):
    _register(repo)
    m2 = json.loads(json.dumps(repo["meta"]))
    m2["note"] = "second synthetic map"
    _w(repo["root"], "maps/TEST_map2.json", json.dumps({"meta": m2}))
    _register(repo, map_file="maps/TEST_map2.json")
    assert reg.verify(repo["reg"], repo["root"])["ok"]
    d = os.path.join(repo["reg"], "records")
    first = sorted(os.listdir(d))[0]
    p = os.path.join(d, first)
    os.chmod(p, 0o644)
    rec = _load(p)
    rec["registered_by"] = "tampered"
    with open(p, "w") as f:
        f.write(json.dumps(rec, sort_keys=True, indent=1) + "\n")
    rep = reg.verify(repo["reg"], repo["root"])
    assert not rep["ok"] and not rep["chain_ok"]
    with pytest.raises(reg.RegistryError, match="refusing to append"):
        _register(repo, map_file="maps/TEST_map.json")
    os.remove(p)
    rep = reg.verify(repo["reg"], repo["root"])
    assert not rep["chain_ok"]


def test_foreign_file_in_records_is_refused(repo):
    _register(repo)
    with open(os.path.join(repo["reg"], "records", "notes.txt"), "w") as f:
        f.write("x")
    assert not reg.verify(repo["reg"], repo["root"])["ok"]


def test_member_eliminated_then_withdrawn(repo, monkeypatch):
    sha = _register(repo)
    _w(repo["root"], "decisions/TEST_withdrawal_decision.json", '{"synthetic": "owner withdraws"}')
    later = {"members": [], "screening_candidates": repo["ens"]["screening_candidates"]}
    monkeypatch.setattr(hall_ensemble, "load_ensemble", lambda path=None: later)
    rep = reg.verify(repo["reg"], repo["root"])
    assert not rep["ok"] and rep["records"][sha]["status"] == "INVALID"
    assert rep["records"][sha]["currency"] and not rep["records"][sha]["problems"]      # intact, but no longer current
    wsha = reg.withdraw(repo["reg"], repo["root"], record_sha256=sha, reason="member eliminated (synthetic)",
                        decision_file="decisions/TEST_withdrawal_decision.json", registered_by="test",
                        registered_utc=UTC)
    rep = reg.verify(repo["reg"], repo["root"])
    assert rep["ok"], rep["problems"]
    assert rep["records"][sha]["status"] == "WITHDRAWN" and rep["records"][wsha]["status"] == "WITHDRAWAL"
    with pytest.raises(reg.RegistryError, match="not ACTIVE"):
        reg.lookup_map_meta(repo["reg"], repo["root"], reg.canonical_json_sha256(repo["meta"]))
    with pytest.raises(reg.RegistryError, match="already withdrawn"):
        reg.withdraw(repo["reg"], repo["root"], record_sha256=sha, reason="again",
                     decision_file="decisions/TEST_withdrawal_decision.json", registered_by="test",
                     registered_utc=UTC)
    # the withdrawn registration file itself is unchanged
    assert any(s == sha for _, s, _ in reg.read_records(repo["reg"]))


def test_pin_move_makes_registration_not_current(repo):
    _register(repo)
    p = os.path.join(repo["root"], "hallthruster_bridge", "PINNED.toml")
    txt = open(p).read().replace(PIN, "1" * 40)
    with open(p, "w") as f:
        f.write(txt)
    rep = reg.verify(repo["reg"], repo["root"])
    assert not rep["ok"] and any("PINNED.toml commit" in x for x in rep["problems"])


# ================================================================================================= record schema
_KNOWN = {"$schema", "$id", "$defs", "title", "description", "type", "required", "properties", "additionalProperties",
          "const", "enum", "pattern", "minimum", "minLength", "$ref", "oneOf", "allOf", "not", "if", "then"}
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _valid(root, s, v):
    """Minimal JSON-Schema subset validator (the keywords the registry schema uses). x-* keys are annotations."""
    unknown = {k for k in s if not k.startswith("x-")} - _KNOWN
    assert not unknown, f"validator does not implement {unknown}"
    if "$ref" in s:
        node = root
        for part in s["$ref"][2:].split("/"):
            node = node[part]
        if not _valid(root, node, v):
            return False
    t = s.get("type")
    if t == "integer" and not (isinstance(v, int) and not isinstance(v, bool)):
        return False
    if t in _TYPES and not isinstance(v, _TYPES[t]):
        return False
    if "const" in s and v != s["const"]:
        return False
    if "enum" in s and v not in s["enum"]:
        return False
    if "pattern" in s and not (isinstance(v, str) and re.search(s["pattern"], v)):
        return False
    if "minLength" in s and not (isinstance(v, str) and len(v) >= s["minLength"]):
        return False
    if "minimum" in s and not (isinstance(v, (int, float)) and v >= s["minimum"]):
        return False
    if isinstance(v, dict):
        if any(k not in v for k in s.get("required", [])):
            return False
        props = s.get("properties", {})
        for k, sub in props.items():
            if k in v and not _valid(root, sub, v[k]):
                return False
        if s.get("additionalProperties") is False and set(v) - set(props):
            return False
    if "not" in s and _valid(root, s["not"], v):
        return False
    if "oneOf" in s and sum(_valid(root, x, v) for x in s["oneOf"]) != 1:
        return False
    for sub in s.get("allOf", []):
        if not _valid(root, sub, v):
            return False
    if "if" in s and _valid(root, s["if"], v) and not _valid(root, s["then"], v):
        return False
    return True


def test_record_schema_matches_module_and_validates_records(repo):
    sch = _load(REG_SCHEMA_PATH)
    d = sch["$defs"]
    assert tuple(d["registration"]["required"]) == reg.REGISTRATION_KEYS
    assert tuple(d["withdrawal"]["required"]) == reg.WITHDRAWAL_KEYS
    for b, keys in reg.BLOCK_KEYS.items():
        node = d["registration"]["properties"].get(b) or d["withdrawal"]["properties"].get(b)
        while "$ref" in node:
            node = d[node["$ref"].split("/")[-1]]
        if "oneOf" in node:
            node = node["oneOf"][0]
        assert set(node["required"]) == set(keys), b
    sha = _register(repo)
    _w(repo["root"], "decisions/TEST_w.json", '{"w": 1}')
    wsha = reg.withdraw(repo["reg"], repo["root"], record_sha256=sha, reason="synthetic",
                        decision_file="decisions/TEST_w.json", registered_by="test", registered_utc=UTC)
    recs = {s: r for _, s, r in reg.read_records(repo["reg"])}
    for r in recs.values():
        assert _valid(sch, sch, r), r
    bad = json.loads(json.dumps(recs[sha]))
    bad["geometry"]["file"] = "design/P5_geometry.json"
    assert not _valid(sch, sch, bad)
    bad = json.loads(json.dumps(recs[sha]))
    bad["convergence_prereg"]["file"] = "docs/hallmap/drafts/hallmap_convergence_prereg_DRAFT.json"
    assert not _valid(sch, sch, bad)
    bad = json.loads(json.dumps(recs[sha]))
    bad["extra"] = 1
    assert not _valid(sch, sch, bad)
    bad = json.loads(json.dumps(recs[wsha]))
    bad["seq"] = 1
    assert not _valid(sch, sch, bad)
    builtin = json.loads(json.dumps(recs[sha]))
    builtin["chemistry"] = {"config_id": "builtin-Xe", "file": None, "sha256": None}
    assert _valid(sch, sch, builtin)
    reg.validate_record(builtin)


# ================================================================================================= purity / scope
def test_registry_is_not_wired_and_holds_no_physics():
    for mod in ("archengine.py", "hall_map.py", "hall_ensemble.py", "thermal_life.py"):
        src = open(os.path.join(ROOT, "abep_sim", mod)).read()
        assert "hallmap_registry" not in src, f"{mod} must not import the registry in this lane"
    src = open(os.path.join(ROOT, "abep_sim", "hallmap_registry.py")).read()
    assert not re.search(r"^\s*(from|import)\s+abep_sim\.(archengine|hall_map|hall_ensemble)", src, re.M), \
        "hall_map / hall_ensemble are imported lazily inside functions only"
    assert "screening" in src and "require_admitted" in src

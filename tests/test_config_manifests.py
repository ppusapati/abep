"""A9.22 Phase A: authoritative input manifests under config/ (no numerical change).

Checks: the builder output is current and every file is pinned in config/MANIFEST.json; the loaders in
abep_sim/configuration.py fail closed; abep_sim.constants.RFP carries today's values field by field; the architecture
loader (abep_sim/design/a9_19_architecture.py) carries today's constants; the requirements snapshot points to the RVM
rows and the RFP registration and derives FROZEN / PROVISIONAL from the RVM; the physics package imports without
docs/requirements.
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from abep_sim import configuration as cfg

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _builder():
    spec = importlib.util.spec_from_file_location("abep_build_config", ROOT / "scripts" / "config" / "build_config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------------ manifest / builder
def test_builder_check_is_current():
    assert _builder().main(["--check"]) == 0


def test_manifest_lists_every_file_with_matching_sha256():
    man = json.loads((CONFIG / "MANIFEST.json").read_text(encoding="utf-8"))
    assert man["schema"] == "abep_config_manifest_v1"
    on_disk = sorted(p.relative_to(CONFIG).as_posix() for p in CONFIG.rglob("*") if p.is_file())
    assert sorted(list(man["files"]) + ["MANIFEST.json"]) == sorted(on_disk)
    for rel, e in man["files"].items():
        assert _sha(CONFIG / rel) == e["sha256"], rel
    for rel in (cfg.ARCHITECTURE_REL, cfg.REQUIREMENTS_REL, cfg.CONSTRAINTS_REL, cfg.MISSION_REL,
                cfg.DESIGN_STATE_REF_REL, cfg.HARDWARE_BOUNDS_REL, cfg.MODEL_SET_REL, cfg.SOURCES_OF_TRUTH_REL,
                "README.md"):
        assert rel in man["files"], rel


def test_referenced_sources_match_their_pins():
    ds = cfg.load_design_state_set_ref()
    assert ds["id"] == "atmosphere_msis21_orbit_v1_design_states_v2"
    assert ds["sha256"] == "60073e214cf5edb92d7eacf70be1491ad29ff72f19db0ef3b96a4b30da6f4049"
    from abep_sim.design import intake_synthesis as isy
    assert ds["path"] == isy.DESIGN_STATE_SET_REL and ds["sha256"] == isy.DESIGN_STATE_SET_SHA256
    assert ds["manifest"]["path"] == isy.DESIGN_STATE_MANIFEST_REL
    assert "copy" in ds["kind"].lower() and not (CONFIG / "environment" / Path(ds["path"]).name).exists()
    hw = cfg.load_hardware_bounds()
    kinds = {e["kind"] for e in hw["entries"]}
    assert {"hardware_freeze_candidate", "rotor_strength_registry", "materials_database", "thermal_node_limits",
            "compressor_legacy_caps"} <= kinds
    for e in hw["entries"]:
        assert set(e) == {"id", "kind", "path", "sha256", "locator", "role"}, e     # index only: no copied values
    assert cfg.model_set_drift() == []


def test_model_set_covers_frozen_data_and_pins():
    ms = cfg.load_model_set()
    paths = {e["path"] for e in ms["data"]}
    for must in ("abep_sim/data/golden_v2.json", "abep_sim/data/intake_surface_v1.json",
                 "abep_sim/data/atmosphere_msis21_v1.json", "abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json",
                 "hallthruster_bridge/PINNED.toml", "hallthruster_bridge/propellants/rate_validity.toml"):
        assert must in paths, must
    assert any(p.startswith("abep_sim/data/rates/") for p in paths)
    mods = {e["path"] for e in ms["modules"]}
    assert "abep_sim/constants.py" in mods and not any("/design/" in m for m in mods)
    assert ms["numerical_methods_flat"]["hallthruster.commit"] == "bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5"
    assert ms["version_labels_flat"]["bus_boundary_a9.BOUNDARY_VERSION"] == "bus_power_boundary_a9_v1"


# ------------------------------------------------------------------------------------------------ fail closed
@pytest.fixture()
def cfg_copy(tmp_path):
    dst = tmp_path / "config"
    shutil.copytree(CONFIG, dst)
    return dst


def _remanifest(root: Path):
    man = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    for rel in man["files"]:
        b = (root / rel).read_bytes()
        man["files"][rel] = {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
    (root / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")


@pytest.mark.parametrize("rel", [cfg.ARCHITECTURE_REL, cfg.REQUIREMENTS_REL, cfg.CONSTRAINTS_REL, cfg.MISSION_REL,
                                 cfg.DESIGN_STATE_REF_REL, cfg.HARDWARE_BOUNDS_REL, cfg.MODEL_SET_REL,
                                 cfg.SOURCES_OF_TRUTH_REL])
def test_altered_config_file_is_refused(cfg_copy, rel):
    assert cfg.load_verified(rel, cfg_copy)                    # the copy itself loads
    p = cfg_copy / rel
    p.write_bytes(p.read_bytes().replace(b'"id"', b'"id" ', 1))
    with pytest.raises(cfg.ConfigurationError, match="sha256"):
        cfg.load_verified(rel, cfg_copy)


def test_missing_or_unlisted_files_are_refused(cfg_copy):
    (cfg_copy / cfg.MISSION_REL).unlink()
    with pytest.raises(cfg.ConfigurationError, match="missing"):
        cfg.load_mission_scenario(cfg_copy)
    with pytest.raises(cfg.ConfigurationError, match="not listed"):
        cfg.load_verified("requirements/other.json", cfg_copy)
    (cfg_copy / "MANIFEST.json").unlink()
    with pytest.raises(cfg.ConfigurationError, match="manifest"):
        cfg.load_architecture(cfg_copy)


def test_cross_pins_are_checked(cfg_copy):
    # mission scenario pins the engineering constraints it references (A9.23; no longer the requirements snapshot)
    cons = cfg_copy / cfg.CONSTRAINTS_REL
    d = json.loads(cons.read_text(encoding="utf-8"))
    d["title"] += " (edited)"
    cons.write_text(json.dumps(d, indent=1), encoding="utf-8")
    _remanifest(cfg_copy)
    with pytest.raises(cfg.ConfigurationError, match="engineering constraints"):
        cfg.load_mission_scenario(cfg_copy)
    assert cfg.load_mission_scenario(cfg_copy, verify_constraints=False)["id"] == "mission_scenario_v1"
    # design-state reference: a wrong target hash is refused
    ref = cfg_copy / cfg.DESIGN_STATE_REF_REL
    d = json.loads(ref.read_text(encoding="utf-8"))
    d["sha256"] = "0" * 64
    ref.write_text(json.dumps(d, indent=1), encoding="utf-8")
    _remanifest(cfg_copy)
    with pytest.raises(cfg.ConfigurationError, match="design-state set reference"):
        cfg.load_design_state_set_ref(cfg_copy)
    # hardware index: a wrong source hash is refused
    hw = cfg_copy / cfg.HARDWARE_BOUNDS_REL
    d = json.loads(hw.read_text(encoding="utf-8"))
    d["entries"][0]["sha256"] = "0" * 64
    hw.write_text(json.dumps(d, indent=1), encoding="utf-8")
    _remanifest(cfg_copy)
    with pytest.raises(cfg.ConfigurationError, match="hardware bounds entry"):
        cfg.load_hardware_bounds(cfg_copy)


def test_compat_block_validation(cfg_copy):
    snap = cfg_copy / cfg.REQUIREMENTS_REL
    d = json.loads(snap.read_text(encoding="utf-8"))
    d["rfp_constraints_compat"]["power_max_W"]["value"] = "1500"
    snap.write_text(json.dumps(d, indent=1), encoding="utf-8")
    _remanifest(cfg_copy)
    with pytest.raises(cfg.ConfigurationError, match="non-numeric"):
        cfg.load_rfp_constraints_compat(cfg_copy)
    del d["rfp_constraints_compat"]["hall_preferred"]
    snap.write_text(json.dumps(d, indent=1), encoding="utf-8")
    _remanifest(cfg_copy)
    with pytest.raises(cfg.ConfigurationError, match="fields"):
        cfg.load_rfp_constraints_compat(cfg_copy)


# ------------------------------------------------------------------------------------------------ constants.RFP
EXPECTED_RFP = {   # abep_sim/constants.py RFPConstraints before Phase A (field by field, types included)
    "thrust_min_mN": 12.0, "thrust_max_mN": 25.0, "power_max_W": 1500.0, "mass_max_kg": 40.0,
    "alt_min_km": 180.0, "alt_max_km": 230.0, "ignition_hours": 15000.0, "mission_hours": 26000.0,
    "ic_total_min": 0.75, "ic_subsystem_min": {"thruster": 0.80, "intake": 0.80, "compressor": 0.60, "pse": 0.70},
    "hall_preferred": True,
}


def test_constants_rfp_equals_todays_values_field_by_field():
    from abep_sim import constants as C
    assert [f.name for f in dataclasses.fields(C.RFPConstraints)] == list(EXPECTED_RFP)
    for obj in (C.RFP, C.RFPConstraints()):
        for k, v in EXPECTED_RFP.items():
            got = getattr(obj, k)
            assert got == v and type(got) is type(v), (k, got)
        assert list(obj.ic_subsystem_min) == list(EXPECTED_RFP["ic_subsystem_min"])
    assert C.RFPConstraints().ic_subsystem_min is not C.RFP.ic_subsystem_min        # default_factory kept
    assert dataclasses.is_dataclass(C.RFP) and C.RFPConstraints.__dataclass_params__.frozen
    # physical constants untouched
    assert (C.G0, C.E_CHARGE, C.AMU, C.K_B, C.MU_EARTH, C.R_EARTH) == (
        9.80665, 1.602176634e-19, 1.66053906660e-27, 1.380649e-23, 3.986004418e14, 6371.0e3)
    assert C.M_SPECIES == {"O": 16.0 * C.AMU, "N2": 28.0 * C.AMU, "O2": 32.0 * C.AMU, "Xe": 131.3 * C.AMU}


def test_mission_scenario_records_g1_applied_and_the_historical_constant():
    ms = cfg.load_mission_scenario()["inputs"]
    ec = cfg.load_engineering_constraints_file()["constraints"]
    assert ms["mission_hours"]["value"] == ms["mission_hours"]["authoritative_basis_h"] == 26280
    assert ms["mission_hours"]["kind"] == "OPERATING_SCENARIO_CHOICE"
    assert ec["mission_life_h"]["value"] == 26280 and ec["mission_life_h"]["g1_status"] == "APPLIED"
    assert ec["mission_life_h"]["historical_value"] == {**ec["mission_life_h"]["historical_value"], "value_h": 26000,
                                                        "label": "HISTORICAL_CONSTANT_NOT_CONSUMED"}
    assert ms["mission_hours"]["g1_status"] == "APPLIED" and ms["mission_hours"]["label"] == "MISSION_DURATION_BASIS"
    assert "legacy_mission_hours_in_use" not in ms["mission_hours"]
    assert ms["mission_hours"]["historical_note"]["value_h"] == 26000
    assert ms["mission_hours"]["historical_note"]["label"] == "HISTORICAL_CONSTANT_NOT_CONSUMED"
    assert "value" not in ms["wet_mass_limit_kg"] and ms["wet_mass_limit_kg"]["constraint_ref"] == "wet_mass_max_kg"
    assert ec["wet_mass_max_kg"]["value"] == 40 and ec["wet_mass_max_kg"]["comparator"] == "<"
    snap = cfg.load_requirements_snapshot()
    assert snap["rfp_constraints_compat"]["mission_hours"]["value"] == 26000          # constants.RFP compat, immutable
    assert snap["rfp_constraints_compat"]["mission_hours"]["label"] == "HISTORICAL_CONSTANT_NOT_CONSUMED"
    assert snap["mission_duration"]["g1_status"] == "APPLIED"
    assert "PENDING_GOVERNED_MIGRATION_A9_22_G1" not in json.dumps(snap) + json.dumps(ms)
    assert ms["firing_hours"]["label"] == "SUBSYSTEM_FIRING_LIFE_ASSUMPTION" and "value" not in ms["firing_hours"]
    assert ec["firing_life_h"] == {**ec["firing_life_h"], "value": 15000, "label": "SUBSYSTEM_FIRING_LIFE_ASSUMPTION"}
    assert (ms["xe_sizing_thrust_target_mN"]["value"], ms["commanded_thrust_cap_mN"]["value"],
            ms["p_bus_throttling_cap_W"]["value"], ec["altitude_band_km"]["value"]) == (12, 25, 1500, [180, 230])
    assert "value" not in ms["altitude_domain_km"]


# ------------------------------------------------------------------------------------------------ architecture
def test_architecture_loader_equals_a9_19_constants():
    from abep_sim.design import a9_19_architecture as a
    assert a.FLIGHT_CONFIGURATION == "hall_icp_neutralizer" and a.FLIGHT_CONFIGURATIONS == ("hall_icp_neutralizer",)
    assert a.GROUND_REFERENCE_CONFIGURATION == "hall_c1_reference" and a.GROUND_REFERENCE_LABEL == "GROUND_REFERENCE"
    assert a.GROUND_ONLY_LAB_EQUIPMENT == "GROUND_ONLY_LAB_EQUIPMENT"
    assert (a.SUPPLY_MODE_AIR, a.SUPPLY_MODE_XE, a.SUPPLY_MODES) == ("AIR_PRIMARY", "XE_CONTINGENCY",
                                                                   ("AIR_PRIMARY", "XE_CONTINGENCY"))
    assert (a.XE_PATH_ROLE, a.AIR_PATH_ROLE) == ("CONTINGENCY_EMERGENCY", "PRIMARY")
    assert a.SUPPLY_MODE_GASES == {"AIR_PRIMARY": ("N2", "NITROGEN", "O2", "OXYGEN", "O", "AIR", "N2/O2", "N2+O2",
                                                   "N2_O2", "AMBIENT_AIR", "ATMOSPHERIC"),
                                   "XE_CONTINGENCY": ("XE", "XENON")}
    assert a.BENCH_ENGINEERING_GAS == ("AR", "ARGON") and a.BENCH_SUPPLY_MODE == "BENCH_AR_ENGINEERING_GROUND_ONLY"
    assert a.ICP_FEED_GAS_BASELINE == {"primary": "G-REUSE", "declared_variant": "G-XE",
                                       "status": "UNCHANGED (A9.1; A9.19 does not alter the ICP feed-gas baseline)"}
    assert a.VERBATIM_A9_19 == ("One Hall accelerator.", "One RF/ICP electron-source/neutralizer.",
                                "Two propellant supply modes.", "No conventional hollow cathode.")
    assert a.RFP_REGISTRATION == "docs/requirements/rfp_official/rfp_registration_v1.json"
    assert a.RFP_CLAUSES == {"xe_extra_input": "RFP-P17-05", "two_tanks": "RFP-P18-08"}
    assert list(a.DECISIONS) == ["A9.19", "A9.20", "A9.15"]
    assert a.DECISIONS["A9.19"]["json_sha256"] == "20364847febc240d06779d26dbca0236059ab4471754df4452401eb0ed050b16"
    assert a.DECISIONS["A9.20"]["md_sha256"] == "2b90a7a7f851ac571791ea6ba2fbafac8cf69a086a4a3724e2f66196b6b4d60c"
    assert a.DECISIONS["A9.15"]["decision_code"] == "A9_15_RFP_COMPLIANT_PROPELLANT_POLICY"
    assert all(a.verify_decision_records().values())
    assert a.C1_ROLE["status"] == "GROUND_ONLY_LAB_EQUIPMENT" and len(a.C1_ROLE["never"]) == 5
    fa = a.FLIGHT_ARCHITECTURE
    assert fa["c1"] is a.C1_ROLE and fa["icp_feed_gas_baseline"] is a.ICP_FEED_GAS_BASELINE
    assert fa["configuration"] == "hall_icp_neutralizer" and fa["hall_accelerators"] == 1
    assert fa["electron_source_neutralizer"] == {"count": 1, "kind": "RF/ICP (13.56 MHz) electron source / neutralizer, "
                                                 "cathodeless / electrodeless",
                                                 "serves_supply_modes": ["AIR_PRIMARY", "XE_CONTINGENCY"]}
    assert [m["path"] for m in fa["supply_modes"]] == [["intake", "filter", "compressor", "atmospheric_gas_chamber",
                                                        "valve"], ["xe_tank", "valve"]]
    assert fa["separate_tanks"] is True and fa["conventional_hollow_cathode"] == "NONE"
    assert fa["verbatim"] == list(a.VERBATIM_A9_19)
    assert fa["status"] == "OWNER_DECIDED_ARCHITECTURE_DEFINITION (A9 investigation; not a flight baseline, not a PASS)"
    arch = cfg.load_architecture()
    assert arch["status"] == "INVESTIGATION_HYPOTHESIS"
    assert arch["a9_status"] == "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE"
    # behaviour unchanged
    with pytest.raises(a.ArchitectureRuleError):
        a.require_flight_configuration("hall_c1_reference")
    assert a.classify_gas("xenon") == "XE_CONTINGENCY" and a.classify_gas("Ar") == a.BENCH_SUPPLY_MODE


# ------------------------------------------------------------------------------------------------ snapshot provenance
def test_snapshot_provenance_points_to_rvm_rows_and_registration():
    snap = cfg.load_requirements_snapshot()
    rvm = json.loads((ROOT / snap["rvm"]["path"]).read_text(encoding="utf-8"))
    reg_path = ROOT / snap["registration"]["path"]
    assert snap["rvm"]["sha256"] == _sha(ROOT / snap["rvm"]["path"])
    assert snap["registration"]["sha256"] == _sha(reg_path)
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    clause_ids = {c["id"] for c in reg["clauses"]}
    rows = {r["id"]: r for r in rvm["rows"]}
    used = set()
    for k, e in snap["rfp_constraints_compat"].items():
        r = rows[e["rvm_row"]]
        used.add(r["id"])
        assert e["rvm_key"] == r["key"] and e["rfp_clauses"] == list(r["rfp_clauses"])
        assert set(e["rfp_clauses"]) <= clause_ids
        assert e["requirement_frozen"] == bool(r["requirement_frozen"])
        assert e["status"] == ("FROZEN" if r["requirement_frozen"] else "PROVISIONAL")
    for k in ("thrust_min_mN", "power_max_W", "mass_max_kg", "ignition_hours"):
        e = snap["rfp_constraints_compat"][k]
        assert e["value"] == rows[e["rvm_row"]]["limit"]["value"], k
    assert [snap["rfp_constraints_compat"][k]["value"] for k in ("alt_min_km", "alt_max_km")] == \
        rows["RVM-01"]["limit"]["value"] == snap["mission_domain"]["altitude_km"]
    assert snap["mission_duration"]["authoritative_basis_h"] == rows["RVM-13"]["limit"]["value"] == 26280
    assert snap["subsystem_firing_life"]["label"] == "SUBSYSTEM_FIRING_LIFE_ASSUMPTION"
    # FROZEN / PROVISIONAL derived from the live RVM flags of the rows used
    want = "FROZEN" if all(rows[r]["requirement_frozen"] for r in used) else "PROVISIONAL"
    assert snap["snapshot_status"] == want
    assert [x["rvm_row"] for x in snap["rvm_limits"]] == [r["id"] for r in rvm["rows"] if r.get("limit")]


def test_snapshot_status_is_derived_not_hard_coded(monkeypatch):
    b = _builder()
    real = b.read_json

    def frozen_rvm(rel):
        d = real(rel)
        if rel == b.RVM_REL:
            for r in d["rows"]:
                r["requirement_frozen"] = True
        return d

    monkeypatch.setattr(b, "read_json", frozen_rvm)
    assert b.build_requirements()["snapshot_status"] == "FROZEN"
    monkeypatch.setattr(b, "read_json", real)
    snap = b.build_requirements()
    rows = {r["id"]: r for r in real(b.RVM_REL)["rows"]}
    if not all(rows[e["rvm_row"]]["requirement_frozen"] for e in snap["rfp_constraints_compat"].values()):
        assert snap["snapshot_status"] == "PROVISIONAL"


# ------------------------------------------------------------------------------------------------ layer separation
_IMPORT_PROBE = r"""
import builtins, io, os, pathlib, pkgutil, importlib, sys, json, shutil, tempfile
HIDDEN = os.path.join(os.path.abspath(sys.argv[1]), "docs", "requirements")
def _hidden(p):
    try:
        return os.path.abspath(os.fspath(p)).startswith(HIDDEN)
    except TypeError:
        return False
_open, _io_open = builtins.open, io.open
def guarded_open(file, *a, **k):
    if _hidden(file):
        raise FileNotFoundError(f"hidden by test: {file}")
    return _open(file, *a, **k)
builtins.open = guarded_open
io.open = guarded_open
_exists, _isfile, _isdir = os.path.exists, os.path.isfile, os.path.isdir
os.path.exists = lambda p: False if _hidden(p) else _exists(p)
os.path.isfile = lambda p: False if _hidden(p) else _isfile(p)
os.path.isdir = lambda p: False if _hidden(p) else _isdir(p)
import abep_sim
from abep_sim import configuration as cfg
skip = {"design", "__main__"}
names = sorted(m.name for m in pkgutil.iter_modules(abep_sim.__path__) if m.name not in skip)
failed = {}
for n in names:
    try:
        importlib.import_module("abep_sim." + n)
    except Exception as e:
        failed[n] = f"{type(e).__name__}: {e}"
# raw physics configuration without the requirements snapshot (loader root without requirements/)
tmp = tempfile.mkdtemp()
root = pathlib.Path(tmp) / "config"
shutil.copytree(cfg.config_root(), root)
shutil.rmtree(root / "requirements")
pc = cfg.physics_configuration(root)
print(json.dumps({"n": len(names), "failed": failed, "req": pc.requirements_snapshot_id,
                  "arch": pc.architecture_id, "ds": pc.design_state_set_id}))
"""


def test_physics_package_imports_without_docs_requirements():
    r = subprocess.run([sys.executable, "-c", _IMPORT_PROBE, str(ROOT)], cwd=ROOT, capture_output=True, text=True,
                       timeout=600, env={**os.environ, "PYTHONPATH": str(ROOT)})
    assert r.returncode == 0, r.stderr[-3000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["n"] > 40 and out["failed"] == {}, out["failed"]
    assert out["req"] is None and out["arch"] == "hall_icp_neutralizer_v1"
    assert out["ds"] == "atmosphere_msis21_orbit_v1_design_states_v2"


def test_assessment_configuration_adds_the_snapshot():
    pc, ac = cfg.physics_configuration(), cfg.assessment_configuration()
    assert pc.requirements_snapshot_id is None and ac.requirements_snapshot_id == "rfp_constraints_v1"
    assert ac.requirements_snapshot_status in ("FROZEN", "PROVISIONAL")
    assert {k: v for k, v in ac.as_dict().items() if not k.startswith("requirements_")} == \
        {k: v for k, v in pc.as_dict().items() if not k.startswith("requirements_")}
    assert pc.materials_id.startswith("materials_db@")


def test_constants_rfp_equals_the_frozen_snapshot_compat_block():
    """A9.22 integration: abep_sim/constants.py stays byte-identical (immutable records pin its sha256); the config
    requirements snapshot is the single source of truth and constants.RFP must never drift from it."""
    from abep_sim import constants as C
    compat = cfg.load_rfp_constraints_compat()
    for k, v in compat.items():
        if k.startswith("_") or not hasattr(C.RFP, k):
            continue
        got = getattr(C.RFP, k)
        want = v["value"] if isinstance(v, dict) and "value" in v else v
        assert got == want, (k, got, want)

"""Checks for the DRAFT Hall-only / RF+Hall / ECR+Hall common-condition experiment protocol.

docs/architecture_comparison/experiment_protocol/: protocol_draft.json, protocol.schema.json,
EXPERIMENT_PROTOCOL_DRAFT.md, protocol_tools.py. Fast (no Julia, no network).
"""
import ast
import copy
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PDIR = REPO / "docs" / "architecture_comparison" / "experiment_protocol"


def _load_tools():
    spec = importlib.util.spec_from_file_location("xprot_protocol_tools", PDIR / "protocol_tools.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tools = _load_tools()


@pytest.fixture(scope="module")
def protocol():
    return json.loads((PDIR / "protocol_draft.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema():
    return json.loads((PDIR / "protocol.schema.json").read_text(encoding="utf-8"))


# --- schema --------------------------------------------------------------------------------------------------
def test_protocol_validates_against_schema(protocol, schema):
    assert tools.validate(protocol, schema) == []


def test_protocol_validates_with_reference_validator_or_subset(protocol, schema):
    """jsonschema (reference implementation) when installed; otherwise the schema must stay inside the keyword subset
    that the in-house validator implements, so that the in-house result is complete (no silently ignored keyword)."""
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        jsonschema.Draft202012Validator.check_schema(schema)
        errors = sorted(str(e.message) for e in jsonschema.Draft202012Validator(schema).iter_errors(protocol))
        assert errors == []
    used = set()

    def keywords(node):
        if isinstance(node, dict):
            for k, v in node.items():
                used.add(k)
                if k in ("properties", "$defs"):
                    for sub in v.values():
                        keywords(sub)
                else:
                    keywords(v)
        elif isinstance(node, list):
            for v in node:
                keywords(v)
    keywords(schema)
    assert used <= tools._SUPPORTED, sorted(used - tools._SUPPORTED)


def test_schema_validator_is_not_vacuous(protocol, schema):
    bad = copy.deepcopy(protocol)
    bad["decision_metrics"][0]["threshold"]["status"] = "ADOPTED"
    assert any("const" in e for e in tools.validate(bad, schema))
    bad = copy.deepcopy(protocol)
    del bad["rfp_screens"]["rfp_values"][0]["source"]
    assert any("source" in e for e in tools.validate(bad, schema))
    bad = copy.deepcopy(protocol)
    bad["arms"][1]["bus_boundary"]["boundary_version_ref"] = "bus_power_boundary_v2"
    assert tools.validate(bad, schema)
    bad = copy.deepcopy(protocol)
    bad["test_matrix"]["factors"][1]["levels"][0]["value"] = 1.0
    assert tools.validate(bad, schema)  # a number without source/evidence class is neither numeric nor TBD


def test_status_is_draft_pending_owner(protocol):
    assert protocol["status"] == "DRAFT_PENDING_OWNER"
    assert protocol["decided_by"] is None


# --- common conditions and the bus boundary ------------------------------------------------------------------
def test_three_arms_share_one_bus_boundary_component_list(protocol):
    assert tools.boundary_errors(protocol) == []
    comp_ids = [c["id"] for c in protocol["bus_power_boundary"]["components"]]
    lists = {tuple(a["bus_boundary"]["component_ids"]) for a in protocol["arms"]}
    assert lists == {tuple(comp_ids)}
    assert {a["id"] for a in protocol["arms"]} == {"HALL_ONLY", "RF_HALL", "ECR_HALL"}
    assert protocol["bus_power_boundary"]["boundary_version_ref"] == "bus_power_boundary_v1"
    assert all(a["bus_boundary"]["boundary_version_ref"] == "bus_power_boundary_v1" for a in protocol["arms"])


def test_boundary_covers_every_listed_consumer(protocol):
    comps = {c["id"]: c for c in protocol["bus_power_boundary"]["components"]}
    assert "conversion" in comps["hall_ppu_input"]["includes"]
    assert "matching network" in comps["rf_generator_input"]["includes"]
    assert "cable" in comps["rf_generator_input"]["includes"]
    for cid in ("magnet_supplies", "microwave_source_input", "cathode_heater", "cathode_keeper",
                "valves_flow_control", "compressor", "thermal_control", "housekeeping"):
        assert cid in comps
    assert "never assumed zero" in protocol["bus_power_boundary"]["presence_rule"]


def test_boundary_detects_an_arm_with_a_different_list(protocol):
    bad = copy.deepcopy(protocol)
    bad["arms"][2]["bus_boundary"]["component_ids"] = bad["arms"][2]["bus_boundary"]["component_ids"][:-1]
    assert tools.boundary_errors(bad)


def test_pre_ionizer_is_the_only_change(protocol):
    inv = {i["id"] for i in protocol["common_conditions"]["invariants"]}
    assert {"INV-PROP", "INV-FLOW", "INV-CHANNEL", "INV-MAG", "INV-VD", "INV-CATH", "INV-FAC", "INV-DIAG",
            "INV-BUS"} <= inv
    fa = protocol["flow_accounting"]["definitions"]
    assert {"m_dot_a", "m_dot_p", "m_dot_c", "m_dot_prop", "m_dot_tot"} <= set(fa)
    assert "m_dot_c" in fa["m_dot_tot"] and "m_dot_prop" in fa["m_dot_tot"]


SIBLING_ARCH_BOUNDARY_COMMIT = "a2a1396"  # separate lane that defines abep_sim/arch_boundary.py (bus_power_boundary_v1)


def _arch_boundary_source():
    path = REPO / "abep_sim" / "arch_boundary.py"
    if path.exists():
        return path.read_text(encoding="utf-8")
    try:
        out = subprocess.run(["git", "-C", str(REPO), "show", f"{SIBLING_ARCH_BOUNDARY_COMMIT}:abep_sim/arch_boundary.py"],
                             capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 and out.stdout else None


def _literal_assignments(source):
    """Module-level NAME = <literal> assignments, parsed with ast (the module is never imported or executed)."""
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                found[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return found


def test_mapping_matches_arch_boundary_component_ids():
    source = _arch_boundary_source()
    if source is None:
        pytest.skip("abep_sim/arch_boundary.py not merged and sibling commit not reachable")
    lit = _literal_assignments(source)
    assert lit["BOUNDARY_VERSION"] == "bus_power_boundary_v1"
    assert tuple(lit["COMMON_COMPONENTS"]) == tools.V1_COMMON_COMPONENTS
    assert {k: tuple(v) for k, v in lit["PREIONIZER_COMPONENTS"].items()} == tools.V1_PREIONIZER_COMPONENTS


def test_every_v1_component_is_mapped_exactly_once_and_compressor_is_declared_absent(protocol):
    assert tools.v1_mapping_errors(protocol) == []
    covered = [v for c in protocol["bus_power_boundary"]["components"] for v in c["v1_component_ids"]]
    assert sorted(covered) == sorted(tools.V1_ALL_COMPONENTS) and len(covered) == len(set(covered))
    for arm in protocol["arms"]:
        assert arm["bus_boundary"]["expected_presence"]["compressor"] == "ABSENT_IN_LAB"
    sub = protocol["bus_power_boundary"]["laboratory_subset"]
    assert sub["absent_in_lab"] == ["compressor"]
    assert sub["compressor_bus_power"]["value"] == "TBD" and "ICD" in sub["compressor_bus_power"]["tbd_requires"]
    assert "reconstructed" in sub["absent_in_lab_disposition"] and "never taken as zero" in sub["absent_in_lab_disposition"]


def test_v1_mapping_detects_divergence(protocol):
    bad = copy.deepcopy(protocol)
    comps = bad["bus_power_boundary"]["components"]
    comps[:] = [c for c in comps if c["id"] != "compressor"]
    for arm in bad["arms"]:
        arm["bus_boundary"]["component_ids"].remove("compressor")
        del arm["bus_boundary"]["expected_presence"]["compressor"]
    assert tools.boundary_errors(bad)
    bad = copy.deepcopy(protocol)
    for c in bad["bus_power_boundary"]["components"]:
        if c["id"] == "magnet_supplies":
            c["v1_component_ids"] = ["hall_magnet"]
    assert any("v1 coverage" in e for e in tools.v1_mapping_errors(bad))
    bad = copy.deepcopy(protocol)
    bad["arms"][0]["bus_boundary"]["expected_presence"]["compressor"] = "ENERGIZED"
    assert tools.boundary_errors(bad)


def test_bus_power_metrics_are_labelled_by_boundary_basis(protocol):
    metrics = {m["id"]: m for m in protocol["decision_metrics"]}
    for mid in ("M1", "M2"):
        d = metrics[mid]["definition"]
        assert "PARTIAL" in d and "P_bus,lab" in d and "P_compressor,ICD" in d
    assert "PARTIAL_BOUNDARY" in metrics["M1"]["definition"]
    assert "P_bus,total" not in json.dumps(protocol)


# --- thresholds and numbers ----------------------------------------------------------------------------------
def test_every_threshold_is_marked_proposed(protocol):
    assert tools.threshold_errors(protocol) == []
    found = tools.thresholds(protocol)
    assert len(found) >= len(protocol["decision_metrics"])
    assert all(t["status"] == "PROPOSED" and t["decided_by"] is None for _p, t in found)
    for m in protocol["decision_metrics"]:
        assert m["threshold"]["status"] == "PROPOSED"


def test_every_numeric_value_is_sourced_or_tbd(protocol):
    assert tools.numeric_discipline_errors(protocol) == []
    objs = tools.value_objects(protocol)
    assert objs
    for _p, obj in objs:
        if obj["value"] == "TBD":
            assert obj["tbd_requires"].strip()
        else:
            assert obj["source"].strip()
            assert obj["evidence_class"] in tools.EVIDENCE_CLASSES


def test_numeric_discipline_detects_violations(protocol):
    bad = copy.deepcopy(protocol)
    bad["design"]["replication"]["replicates_min"]["evidence_class"] = "measured-ish"
    bad["scope"]["stray"] = 3
    bad["bus_power_boundary"]["bus_voltage"]["tbd_requires"] = ""
    errs = tools.numeric_discipline_errors(bad)
    assert any("evidence_class" in e for e in errs)
    assert any("bare number" in e for e in errs)
    assert any("TBD without" in e for e in errs)


def test_intake_delivered_flows_and_compositions_are_not_invented(protocol):
    factors = {f["id"]: f for f in protocol["test_matrix"]["factors"]}
    for lvl in factors["F-MDOT"]["levels"]:
        assert lvl["value"] == "TBD" and "ICD" in lvl["tbd_requires"]
    mix = [lvl for lvl in factors["F-PROP"]["levels"] if lvl["id"] == "prop_o2n2_mixtures"]
    assert mix and mix[0]["value"] == "TBD" and "ICD" in mix[0]["tbd_requires"]


def test_derived_values_reproduce(protocol):
    assert tools.derived_errors(protocol) == []
    d = tools.derive(protocol)
    from abep_sim.constants import RFP
    assert d["rfp_thrust_per_power_floor"] == pytest.approx(RFP.thrust_min_mN / (RFP.power_max_W / 1000.0))


def test_zero_failure_decision_aid_matches_clopper_pearson():
    for p in (0.9, 0.95, 0.99):
        n = tools.n_zero_failures(p, 0.95)
        assert tools.clopper_pearson_lower(n, n, 0.95) >= p
        assert tools.clopper_pearson_lower(n - 1, n - 1, 0.95) < p
    pytest.importorskip("scipy")
    lo = tools.clopper_pearson_lower(19, 20, 0.95)
    assert 0.0 < lo < tools.clopper_pearson_lower(20, 20, 0.95)


# --- documents ------------------------------------------------------------------------------------------------
def test_markdown_numeric_register_is_current(protocol):
    assert tools.markdown_errors(protocol) == []


def test_full_tool_check_passes(protocol):
    assert tools.check_all(protocol) == []


def test_no_outcome_or_selection_claims():
    forbidden = re.compile(r"\bwin(s|ner|ners|ning)?\b|best candidate|recommended candidate|promot", re.I)
    for name in ("EXPERIMENT_PROTOCOL_DRAFT.md", "protocol_draft.json", "protocol.schema.json"):
        text = (PDIR / name).read_text(encoding="utf-8")
        assert not forbidden.search(text), (name, forbidden.search(text).group(0))


def test_references_state_their_access(protocol):
    for ref in protocol["references"]:
        assert ref["access"] in ("full_text", "abstract_only", "metadata_only", "repository_record")
        if ref["access"] == "metadata_only":
            assert "verify" in ref["access_note"].lower()


def test_preregistration_precedes_any_measurement(protocol):
    pre = protocol["preregistration"]
    assert "no score-bearing measurement before" in pre["rule"]
    assert [s["id"] for s in pre["steps"]][:4] == ["PR-1", "PR-2", "PR-3", "PR-4"]


# --- schedule generator ---------------------------------------------------------------------------------------
def test_schedule_is_deterministic_and_balanced():
    blocks = [("Xe", ["X1"]), ("N2", ["N1", "N2", "N3"]), ("O2N2", ["M1", "M2"])]
    arms = ["HALL_ONLY", "RF_HALL", "ECR_HALL"]
    a = tools.randomized_schedule(blocks, arms, replicates=3, seed=12345)
    b = tools.randomized_schedule(blocks, arms, replicates=3, seed=12345)
    assert a == b
    assert a != tools.randomized_schedule(blocks, arms, replicates=3, seed=54321)
    runs = [e for e in a if e["arm"] is not None]
    for rep in range(3):
        for _blk, pts in blocks:
            for pt in pts:
                got = sorted(e["arm"] for e in runs if e["replicate"] == rep and e["point"] == pt)
                assert got == sorted(arms)
        order = [e["block"] for e in a if e["replicate"] == rep]
        assert order[0] == order[-1] == "health"
        body = [blk for blk in order if blk != "health"]
        assert body == sorted(body, key=["Xe", "N2", "O2N2"].index)  # fixed propellant-block order

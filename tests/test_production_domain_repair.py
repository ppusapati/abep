"""Repair tests (area production_data_perf, 2026-10-01): PHY-02 free-molecular pressure domain of the production gas
path, PHY-06 recorded Hall calibration domain of the A9.18 golden, RVF-05 dedicated-baseline registration addendum,
SW-01 v1 feed-state / compressor-downselect history restored with the A9.16 regeneration as v2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ PHY-02 (A9.13 S6.8)
def test_free_molecular_limit_agrees_with_design_layer():
    from abep_sim import system
    from abep_sim import compressor_transitional as ct
    from abep_sim.design import compressor_synthesis as cs, upstream_a9_13 as up
    assert system.P_FREE_MOLECULAR_LIMIT_PA == cs.P_MOLECULAR_LIMIT_PA == up.P_FREE_MOLECULAR_LIMIT_PA \
        == ct.P_FREE_MOLECULAR_LIMIT_PA == 0.1
    assert system.NOT_EVALUATED_OUT_OF_DOMAIN == up.NOT_EVALUATED_OOD


@pytest.mark.parametrize("p_level", [0.2, 0.3])
def test_gaspath_above_0p1_pa_is_not_evaluated_out_of_domain(p_level):
    """A converged gas state above 0.1 Pa is NOT_EVALUATED_OUT_OF_DOMAIN, not IN_DOMAIN, and the compressor branch is
    infeasible (fail closed); archengine refuses it as evidence."""
    from abep_sim import golden as G
    from abep_sim import archengine as AE
    r = G._gas_record(0.7, p_level)
    assert r["gaspath_status"] == "CONVERGED"
    assert r["gaspath_domain_status"] == "NOT_EVALUATED_OUT_OF_DOMAIN" and r["gaspath_in_domain"] is False
    assert "free_molecular_pressure_limit_0.1Pa" in r["gaspath_out_of_domain"]
    assert r["gaspath_p_domain_max_Pa"] > 0.1 and r["gaspath_p_domain_limit_Pa"] == 0.1
    # _gas_record is the raw closure since the A9.22 programme split: the raw compressor feasibility flag (the legacy
    # merged record's chk_compressor_feasible was exactly this value)
    assert not r["comp_feasible"]
    gas = AE.make_gas_fn()(0.7, p_level)
    assert gas["gaspath_domain_status"] == "NOT_EVALUATED_OUT_OF_DOMAIN"
    assert AE.gas_evidence_class(gas)[0] == "OUT_OF_MODEL_DOMAIN"
    v = G.admissibility(0.7, p_level)
    assert v["admissible"] is False and v["verdict"] == "GASPATH_OUT_OF_MODEL_DOMAIN"


@pytest.mark.parametrize("area,p_level", [(0.7, 0.05), (0.7, 0.1), (0.85, 0.1)])
def test_gaspath_at_or_below_0p1_pa_stays_in_domain(area, p_level):
    """The limit is inclusive: a converged 0.1 Pa setpoint is not pushed out of domain by the reservoir pressure's
    round-off (compared within the orifice solver's own tolerance)."""
    from abep_sim import golden as G
    r = G._gas_record(area, p_level)
    assert r["gaspath_status"] == "CONVERGED"
    assert r["gaspath_domain_status"] == "IN_DOMAIN", r["gaspath_out_of_domain"]
    # the free-discharge outlet of the compressor sizing search is reported explicitly, never silently
    assert isinstance(r["comp_sizing_p_out_Pa"], float)
    assert r["comp_sizing_p_out_above_limit"] == (r["comp_sizing_p_out_Pa"] > 0.1)


def test_gaspath_just_above_limit_is_out_of_domain():
    from abep_sim import golden as G
    r = G._gas_record(0.7, 0.1000001)
    assert r["gaspath_domain_status"] == "NOT_EVALUATED_OUT_OF_DOMAIN"


# ------------------------------------------------------------------------------------------------ PHY-06 (A9.18 item 1)
def test_golden_records_hall_calibration_domain_explicitly():
    from abep_sim import golden as G
    st = G.HALL_CALIBRATION_DOMAIN
    assert st["status"] == "RECORDED_NOT_GATING_OWNER_CONFIRMATION_REQUESTED"
    assert "registered model domain" in st["statement"] and "extrapolation" in st["statement"]
    data = json.loads((REPO / "abep_sim/data/golden_v2.json").read_text())
    assert data["provenance"]["hall_calibration_domain"] == st
    sel = data["cases"]["design_point_selection"]
    assert sel["hall_calibration_domain_status"] == st["status"]
    closed = {k: v for k, v in sel["visited"].items() if "hall_calibration" in v}
    assert closed, "every closed grid point must carry its Hall calibration label"
    key = f"A{G.GOLDEN_DESIGN_POINT['area']}_p{G.GOLDEN_DESIGN_POINT['p_level']}"
    assert sel["visited"][key]["hall_calibration"] == data["cases"]["architecture_closure"]["ext_hall_2p5kW"]["calibration"]
    for s in data["provenance"]["full_grid_scan"]:
        if s.get("closure_status") is not None:
            assert "hall_calibration" in s and "hall_calibration_extrapolation" in s


def test_selected_golden_point_extrapolation_is_the_recomputed_excursion():
    """The recorded excursion is the Isp excursion above the 0-D calibration envelope (not silent, not re-derived)."""
    from abep_sim.archengine import CALIBRATION
    c = json.loads((REPO / "abep_sim/data/golden_v2.json").read_text())["cases"]["architecture_closure"]["ext_hall_2p5kW"]
    assert c["calibration"] == "extrapolation"
    isp_hi = CALIBRATION["hall"][1]["Isp_s"][1]
    assert c["extrapolation"] > 0.0 and isp_hi == 1400.0


# ------------------------------------------------------------------------------------------------ RVF-05
DED = "docs/performance/dedicated_baseline_2026_10_01"


def test_dedicated_registration_addendum_supersedes_admission_label():
    reg_rel = f"{DED}/REGISTRATION.json"
    add = json.loads((REPO / f"{DED}/REGISTRATION_ADDENDUM_A9_18.json").read_text())
    reg = json.loads((REPO / reg_rel).read_text())
    assert reg["status"] == "ADMISSION_BASELINE_PERFORMANCE_ONLY"           # recorded file kept as is
    sup = add["supersedes_for_current_use"]
    assert sup["path"] == reg_rel and sup["sha256"] == _sha(reg_rel)
    assert sup["recorded_value"] == reg["status"] and add["status"] == sup["current_value"] == "HISTORICAL_FOR_EARLIER_CODE_STATE"
    assert add["rust_performance_admission"] == "BLOCKED_UNTIL_A9_18_PERF_RERUN"
    for p, h in add["decision_sha256"].items():
        assert _sha(p) == h
    dec = (REPO / "docs/decisions/OD_2026_10_01_A9_18_GOLDEN_AND_BASELINE_OWNER_DECISIONS.md").read_text()
    assert add["a9_18_verbatim"] in dec
    for p in add["source_drift_records"]:
        assert (REPO / p).exists(), p
    md = (REPO / add["baseline_md_shared_machine_line"]["path"]).read_text()
    assert add["baseline_md_shared_machine_line"]["line"] in md
    assert reg["machine"]["windows_cpu_load_percent_before_after"] == [7, 1]


# ------------------------------------------------------------------------------------------------ SW-01
V1_PINS = {
    "docs/architecture_comparison/feed_state_closure/feed_state_closure_v1.json":
        "ff6e15db449151b5cf790088b4641504bd435a48de2d4c6235bf83625d508ef9",
    "docs/architecture_comparison/compressor_downselect/compressor_downselect_v1.json":
        "79f6b28f65243b54894dc78172b708693f96c639089f472d91d070012a0e4a52",
}


def test_v1_feed_and_downselect_history_byte_identical():
    for rel, h in V1_PINS.items():
        assert _sha(rel) == h, rel


def test_a9_16_chain_writes_and_reads_v2():
    import importlib.util

    def load(rel):
        spec = importlib.util.spec_from_file_location(Path(rel).stem + "_sw01", REPO / rel)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m
    fsc = load("docs/architecture_comparison/feed_state_closure/build_feed_state_closure.py")
    cds = load("docs/architecture_comparison/compressor_downselect/build_compressor_downselect.py")
    assert fsc.JSON_NAME == "feed_state_closure_v2.json" and cds.JSON_NAME == "compressor_downselect_v2.json"
    assert cds.CLOSURE_REL.endswith("feed_state_closure_v2.json")
    f3 = (REPO / "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json").read_text()
    assert "compressor_downselect_v2.json" in f3 and "compressor_downselect_v1.json" not in f3


def test_every_admissible_grid_point_is_a_hall_calibration_extrapolation():
    """The HALL_CALIBRATION_DOMAIN statement ('every closed point of the default grid is an extrapolation') is read
    from the recorded full grid scan, not asserted from memory."""
    scan = json.loads((REPO / "abep_sim/data/golden_v2.json").read_text())["provenance"]["full_grid_scan"]
    adm = [s for s in scan if s["admissible"]]
    assert adm and all(s["hall_calibration"] == "extrapolation" and s["hall_calibration_extrapolation"] > 0 for s in adm)

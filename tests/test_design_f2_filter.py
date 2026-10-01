"""A9.7 F2 filter-stage interface (abep_sim/design/filter_stage.py) and its builder/record.

No skips. Pure arithmetic; runs in well under a second."""
from __future__ import annotations

import importlib.util
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

from abep_sim.constants import K_B, M_SPECIES
from abep_sim.design import filter_stage as fs

REPO = Path(__file__).resolve().parents[1]
JSON_PATH = REPO / "docs/design_synthesis/f2_filter/f2_filter_stage_v1.json"
BUILDER = REPO / "docs/design_synthesis/f2_filter/build_f2_filter.py"
SP = ("O", "N2", "O2")


def inlet(fwd=None, back=None, kn=None, T=300.0, incidence="diffuse_thermal", label="EVIDENCE"):
    return fs.InletState(mdot_forward_kgps=fwd or {s: 1.0e-6 for s in SP},
                         mdot_back_incident_kgps=back or {s: 0.0 for s in SP}, back_incident_basis="test",
                         T_gas_K=T, incidence=incidence, knudsen_number=kn, label=label, provenance="test")


def ev(v, cls="measured", status="EVIDENCED"):
    return fs.EV(value=v, units="-", status=status, evidence_class=cls, source="test record", uncertainty="test")


def numeric_stage(tau_f=0.5, cap_f=0.1, conv_f=0.2, tau_b=0.4, cap_b=0.05, conv_b=0.1, route=0.3, area=0.01,
                  areal=2.0, cls="measured"):
    tr = {}
    for s in SP:
        has = s in fs.CONVERSION_PRODUCTS
        tr[s] = fs.SpeciesTransport(
            tau_f=ev(tau_f, cls), capture_f=ev(cap_f, cls), conversion_f=ev(conv_f if has else 0.0, cls),
            tau_b=ev(tau_b, cls), capture_b=ev(cap_b, cls), conversion_b=ev(conv_b if has else 0.0, cls),
            alpha_conductance=ev(tau_b, cls),
            product_to_outlet_f=ev(route, cls) if has else None, product_to_outlet_b=ev(route, cls) if has else None)
    return fs.FilterStage(stage_id="T", concept_id="T", kind="element", transport=tr,
                          forward_incidence="diffuse_thermal",
                          face_area_m2=fs.EV(value=area, units="m^2", status="EVIDENCED", evidence_class="measured",
                                             source="t"),
                          areal_mass_kg_m2=fs.EV(value=areal, units="kg/m^2", status="EVIDENCED",
                                                 evidence_class="measured", source="t"))


# ---- EV records ---------------------------------------------------------------------------------------------------
def test_ev_validation():
    with pytest.raises(fs.FilterStageError):
        fs.EV(value=0.5, units="-", status="TBD", requires="x")
    with pytest.raises(fs.FilterStageError):
        fs.EV(value=None, units="-", status="TBD")
    with pytest.raises(fs.FilterStageError):
        fs.EV(value=float("nan"), units="-", status="EVIDENCED", evidence_class="measured", source="s")
    with pytest.raises(fs.FilterStageError):
        fs.EV(value=0.5, units="-", status="EVIDENCED", evidence_class="guess", source="s")
    with pytest.raises(fs.FilterStageError):
        fs.EV(value=0.5, units="-", status="EVIDENCED", evidence_class="measured", source="")
    assert not ev(0.5, "assumed").usable_as_evidence
    assert not ev(0.5, status="PLACEHOLDER_NOT_A_FLIGHT_DESIGN").usable_as_evidence
    assert ev(0.5).usable_as_evidence


# ---- fail closed ----------------------------------------------------------------------------------------------------
def test_tbd_stage_refuses_and_lists_missing():
    st = fs.FilterStage.tbd("X", "FC-02", species=SP)
    r = st.apply(inlet(kn=10.0))
    assert r.status == "REFUSED_TBD" and not r.numeric
    assert r.species == {} and r.mass_kg is None
    missing = {m["parameter"] for m in r.missing}
    assert {"face_area_m2", "areal_mass_kg_m2", "tau_f.O", "capture_b.N2", "alpha_conductance.O2"} <= missing
    assert r.to_f3_record()["status"] == "NOT_EVALUATED"
    assert st.backflow_coupling(300.0)["status"] == "REFUSED_TBD"


def test_assumed_and_placeholder_values_refused_in_evidence_mode():
    for cls, status in (("assumed", "EVIDENCED"), ("assumed", "PLACEHOLDER_NOT_A_FLIGHT_DESIGN")):
        st = numeric_stage(cls=cls)
        st = fs.FilterStage(stage_id="T", concept_id="T", kind="element",
                            transport={s: fs.SpeciesTransport(**{k: (fs.EV(value=v.value, units="-", status=status,
                                                                           evidence_class=cls, source="x")
                                                                     if v is not None else None)
                                                                 for k, v in t.__dict__.items()})
                                       for s, t in st.transport.items()},
                            forward_incidence="diffuse_thermal", face_area_m2=st.face_area_m2,
                            areal_mass_kg_m2=st.areal_mass_kg_m2)
        assert st.apply(inlet(kn=10.0)).status == "REFUSED_TBD"


def test_knudsen_required_and_domain():
    st = numeric_stage()
    r = st.apply(inlet(kn=None))
    assert r.status == "REFUSED_TBD" and any(m["parameter"] == "knudsen_number" for m in r.missing)
    assert st.apply(inlet(kn=0.5)).status == "OUT_OF_DOMAIN"        # Livesey: molecular only for Kn > 0.5
    assert st.apply(inlet(kn=0.51)).status == "NUMERIC"
    assert st.apply(inlet(kn=10.0, T=None)).status == "REFUSED_TBD"
    assert st.apply(inlet(kn=10.0, incidence="hyperthermal_directed")).status == "OUT_OF_DOMAIN"


def test_nonphysical_inputs_refused():
    assert numeric_stage(tau_f=0.8, cap_f=0.2, conv_f=0.2).apply(inlet(kn=10.0)).status == "NONPHYSICAL_INPUT"
    assert numeric_stage(tau_f=1.2, cap_f=0.0, conv_f=0.0).apply(inlet(kn=10.0)).status == "NONPHYSICAL_INPUT"


def test_conversion_only_through_declared_channels():
    t = fs.tbd_species_transport("N2")
    bad = fs.SpeciesTransport(**{**t.__dict__, "conversion_f": ev(0.1)})
    with pytest.raises(fs.FilterStageError):
        fs.FilterStage(stage_id="T", concept_id="T", kind="element", transport={"N2": bad},
                       forward_incidence="diffuse_thermal")
    with pytest.raises(fs.FilterStageError):
        fs.FilterStage(stage_id="T", concept_id="T", kind="element",
                       transport={"O": fs.SpeciesTransport(**{**fs.tbd_species_transport("O").__dict__,
                                                              "product_to_outlet_f": None})},
                       forward_incidence="diffuse_thermal")


def test_backflow_must_be_stated():
    with pytest.raises(TypeError):
        fs.InletState(mdot_forward_kgps={"O": 1.0}, back_incident_basis="x", T_gas_K=300.0,
                      incidence="diffuse_thermal", knudsen_number=1.0, label="EVIDENCE", provenance="x")
    with pytest.raises(fs.FilterStageError):
        fs.InletState(mdot_forward_kgps={"O": 1.0}, mdot_back_incident_kgps={"N2": 0.0}, back_incident_basis="x",
                      T_gas_K=300.0, incidence="diffuse_thermal", knudsen_number=1.0, label="EVIDENCE",
                      provenance="x")


# ---- conservation -----------------------------------------------------------------------------------------------
def test_per_species_fractions_sum_to_one_and_mass_conserved():
    st = numeric_stage()
    r = st.apply(inlet(fwd={"O": 3e-6, "N2": 2e-6, "O2": 1e-6}, back={"O": 1e-7, "N2": 2e-7, "O2": 3e-7}, kn=5.0))
    assert r.status == "NUMERIC" and r.label == fs.LABEL_EVIDENCE
    for s, v in r.species.items():
        for d in ("fractions_forward", "fractions_backflow"):
            f = v[d]
            assert abs(f["transmitted"] + f["reflected"] + f["lost"] - 1.0) <= 1e-12
            assert abs(f["lost"] - f["captured"] - f["converted"]) <= 1e-15
        assert abs(v["species_balance_residual_kgps"]) <= 1e-18
    t = r.totals
    assert abs(t["mass_balance_residual_kgps"]) <= 1e-18
    assert abs(t["converted_minus_produced_kgps"]) <= 1e-18
    # O converted mass appears as O2 product
    assert r.species["O2"]["produced_to_outlet_kgps"] + r.species["O2"]["produced_to_inlet_kgps"] == \
        pytest.approx(r.species["O"]["forward"]["converted"] + r.species["O"]["backflow"]["converted"], rel=1e-14)


def test_conservation_randomized():
    rng = random.Random(20261001)
    for _ in range(200):
        a, b, c = sorted(rng.random() for _ in range(3))
        d, e, f = sorted(rng.random() for _ in range(3))
        st = numeric_stage(tau_f=a, cap_f=b - a, conv_f=c - b, tau_b=d, cap_b=e - d, conv_b=f - e,
                           route=rng.random())
        r = st.apply(inlet(fwd={s: rng.random() for s in SP}, back={s: rng.random() for s in SP}, kn=2.0))
        assert r.status == "NUMERIC"
        tot = sum(r.totals[k] for k in ("gross_downstream_kgps", "gross_upstream_kgps", "captured_kgps"))
        assert tot == pytest.approx(r.totals["incident_kgps"], rel=1e-12, abs=1e-15)


def test_conductance_and_pressure_law():
    st = numeric_stage(tau_b=0.4, area=0.02)
    r = st.apply(inlet(T=300.0, kn=3.0))
    for s in SP:
        cbar = math.sqrt(8 * K_B * 300.0 / (math.pi * M_SPECIES[s]))
        C = 0.4 * 0.02 * cbar / 4
        assert r.species[s]["conductance_m3_s"] == pytest.approx(C, rel=1e-14)
        net = r.species[s]["net_downstream_kgps"]
        assert r.species[s]["delta_p_Pa"] == pytest.approx(net / M_SPECIES[s] * K_B * 300.0 / C, rel=1e-12)
    assert r.mass_kg == pytest.approx(0.04)


def test_reciprocity_note_for_diffuse_lossfree():
    st = numeric_stage(tau_f=0.5, cap_f=0.0, conv_f=0.0, tau_b=0.4, cap_b=0.0, conv_b=0.0)
    assert any("reciprocity" in n for n in st.apply(inlet(kn=3.0)).notes)
    st = numeric_stage(tau_f=0.4, cap_f=0.0, conv_f=0.0, tau_b=0.4, cap_b=0.0, conv_b=0.0)
    assert not any("reciprocity" in n for n in st.apply(inlet(kn=3.0)).notes)


# ---- none option, sensitivity, placeholders -------------------------------------------------------------------------
def test_none_is_identity():
    r = fs.FilterStage.none(SP).apply(inlet(fwd={"O": 2.0, "N2": 3.0, "O2": 5.0}, kn=None, T=None))
    assert r.status == "NO_FILTER_IDENTITY" and r.numeric
    for s, m in (("O", 2.0), ("N2", 3.0), ("O2", 5.0)):
        assert r.species[s]["gross_downstream_kgps"] == m and r.species[s]["gross_upstream_kgps"] == 0.0
        assert r.species[s]["delta_p_Pa"] == 0.0
    assert r.mass_kg == 0.0
    assert r.composition_net_downstream["mass_fraction"]["O2"] == pytest.approx(0.5)


def test_sensitivity_case_labelled_and_overrides_listed():
    st = fs.FilterStage.tbd("X", "FC-02", species=SP)
    with pytest.raises(fs.FilterStageError):
        fs.SensitivityCase("c", "my case", {}, "r")
    with pytest.raises(fs.FilterStageError):
        st.apply(inlet(kn=3.0), fs.SensitivityCase("c", "PARAMETRIC_SENSITIVITY", {"nope": 1.0}, "r"))
    case = fs.placeholder_sensitivity_case(st)
    r = st.apply(inlet(kn=None), case)
    assert r.status == "NUMERIC" and r.label == fs.LABEL_SENSITIVITY
    assert len(r.overrides_used) == len(case.overrides)
    assert any(a["what"] == "flow regime" for a in r.assumptions)
    rec = r.to_f3_record()
    assert rec["label"] == fs.LABEL_SENSITIVITY and rec["overrides_used"]
    # a partial sensitivity case still refuses
    part = fs.SensitivityCase("p", "PARAMETRIC_SENSITIVITY", {"face_area_m2": 1.0}, "r",
                              regime_assumption="free_molecular")
    assert st.apply(inlet(kn=None), part).status == "REFUSED_TBD"


def test_placeholder_values_match_repository_and_are_not_evidence():
    from abep_sim.intake_tpmc import IntakeGeometry
    g = IntakeGeometry()
    v = fs.repository_placeholder_values()
    assert (v["filter_open_frac"], v["filter_transmission"], v["filter_mass_per_m2"]) == \
        (g.filter_open_frac, g.filter_transmission, g.filter_mass_per_m2)
    assert v["filter"] is False
    case = fs.placeholder_sensitivity_case(fs.FilterStage.tbd("X", "Y", species=SP))
    assert "PLACEHOLDER_NOT_A_FLIGHT_DESIGN" in case.label and "PARAMETRIC_SENSITIVITY" in case.label


def test_cole_table_and_domain():
    assert fs.cole_transmission_probability(1.0).value == 0.514231
    assert fs.cole_transmission_probability(500.0).value == 0.002646
    a = fs.cole_transmission_probability(7.0).value
    assert 0.109304 < a < 0.190941
    with pytest.raises(fs.FilterStageError):
        fs.cole_transmission_probability(0.01)
    with pytest.raises(fs.FilterStageError):
        fs.cole_transmission_probability(600.0)
    xs = [x for x, _ in fs.COLE_TABLE_2_5]
    ys = [y for _, y in fs.COLE_TABLE_2_5]
    assert xs == sorted(xs) and ys == sorted(ys, reverse=True)
    assert fs.perforated_plate_alpha(1.0, 0.5).value == pytest.approx(0.2571155)


def test_material_records_never_ao_proof_from_surrogate():
    m = fs.MaterialApplicability("x")
    assert m.ao_compatibility == "INCOMPLETE_EVIDENCE" and m.to_dict()["final_material_status"] == "OPEN"
    with pytest.raises(fs.FilterStageError):
        fs.MaterialApplicability("x", ao_compatibility="GATE_SATISFIED_WITHIN_EVIDENCE_DOMAIN",
                                 surrogate_label=fs.NO_ATOMIC_O, evidence_refs=("r",))
    with pytest.raises(fs.FilterStageError):
        fs.MaterialApplicability("x", ao_compatibility="PASS")
    with pytest.raises(fs.FilterStageError):
        fs.MaterialApplicability("x", ao_compatibility="OUT_OF_DOMAIN")      # needs evidence refs


def test_vocabulary_matches_p4():
    p = REPO / "docs/experiments/hall_icp/p4_anode_materials/p4_screening.py"
    spec = importlib.util.spec_from_file_location("p4_screening_for_f2_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert tuple(mod.GATE_OUTCOMES) == fs.AO_GATE_OUTCOMES
    assert tuple(mod.FORBIDDEN_WORDS) == fs.FORBIDDEN_STATUS_WORDS


# ---- builder / record -----------------------------------------------------------------------------------------------
def test_builder_check_passes():
    out = subprocess.run([sys.executable, str(BUILDER), "--check"], capture_output=True, text=True, cwd=REPO)
    assert out.returncode == 0, out.stdout + out.stderr


def test_record_content():
    d = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for key in ("items", "interface_demands", "open_owner_questions", "m16_impact", "candidate_concepts",
                "repository_placeholders", "source_register", "pins"):
        assert d[key]
    for it in d["items"]:
        assert {"id", "value", "units", "basis", "source", "evidence_class", "status"} <= set(it)
        if it["status"] == "TBD":
            assert it["value"] == "TBD"
    for p in d["repository_placeholders"]["records"]:
        assert p["status"] == "PLACEHOLDER_NOT_A_FLIGHT_DESIGN" and ":" in p["location"]
    assert all(c["candidate_status"].startswith(("LISTED_ONLY", "OUT_OF_SCOPE")) for c in d["candidate_concepts"])
    for c in d["candidate_concepts"]:
        for s in c["sources"]:
            assert s["id"] in d["source_register"] or s["id"].startswith("owner row")
    dirs = {x["direction"] for x in d["interface_demands"]}
    assert {"F2 <- F1", "F2 -> F1", "F2 -> F3", "F2 <- F3", "F2 <-> F4"} <= dirs
    for x in d["interface_demands"]:
        if "F1" in x["direction"] or "F3" in x["direction"]:
            assert x["counterpart"].startswith("PENDING")
    statuses = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("status", "candidate_status", "readiness_change", "ao_compatibility") and isinstance(v, str):
                    statuses.append(v)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(d)
    for s in statuses:
        assert not any(tok in fs.FORBIDDEN_STATUS_WORDS for tok in s.replace("(", " ").replace(")", " ").split()), s
    dc = {x["id"]: x for x in d["demonstration_cases"]}
    assert dc["DC-02"]["result"]["status"] == "REFUSED_TBD"
    assert dc["DC-03"]["result"]["label"] == fs.LABEL_SENSITIVITY


def test_no_forbidden_substring_in_lane_files():
    for p in (REPO / "abep_sim/design/filter_stage.py", BUILDER, Path(__file__)):
        assert "xe" + "_ledger" not in p.read_text(encoding="utf-8")

"""Checks for the species-resolved sputter-yield evidence register (docs/evidence/sputter_yields_v1/).

Owner A9.12 S5.13 (P4-OQ-04) and S5.11 (P4-OQ-02). The register is evidence only. These tests keep it honest: the
builder reproduces its outputs, the cited formula reproduces the source's worked example, no alloy / coating value and no
molecular-ion number exists, every Q0 cell has a measurement or acquisition disposition, non-open sources carry no
numbers, and missing inputs raise.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "evidence" / "sputter_yields_v1"
REG = DIR / "sputter_yields_v1.json"
INP = DIR / "sputter_yield_inputs_v1.json"
P4 = ROOT / "docs" / "experiments" / "hall_icp" / "p4_anode_materials" / "p4_anode_materials_v1.json"

Q0_CANDIDATES = {"CAND-01", "CAND-02A", "CAND-02B", "CAND-02C", "CAND-02D", "CAND-03A", "CAND-03B", "CAND-03C",
                 "CAND-04", "CAND-05", "CAND-06", "CAND-07", "CAND-08", "CAND-09"}
SPECIES = ("N+", "N2+", "O+", "O2+")
ELEMENTS = {"C", "Al", "Ti", "Cr", "Fe", "Ni", "Nb", "Mo", "Ru", "Rh", "W", "Ir", "Pt"}


def _builder():
    spec = importlib.util.spec_from_file_location("build_sputter_yields_v1", DIR / "build_sputter_yields_v1.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def b():
    return _builder()


@pytest.fixture(scope="module")
def reg():
    return json.loads(REG.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def inputs():
    return json.loads(INP.read_text(encoding="utf-8"))


def test_builder_check_reproduces_outputs(b):
    assert b.check() == 0


def test_worked_example_and_mass_ratios(b, inputs):
    aw, zn = inputs["atomic_weights"]["values"], inputs["atomic_numbers"]
    us, q, w, s = inputs["nifs_table1"]["rows"]["Au"]
    y = b.yamamura_tawara(1000.0, zn["He"], aw["He"], zn["Au"], aw["Au"], us, q, w, s)
    assert y["Y"] == pytest.approx(0.140, rel=0.02)
    assert y["Eth_eV"] == pytest.approx(54.0, rel=0.02)
    for row in inputs["nifs_caption_fits"]["rows"]:
        assert aw[row["target"]] / aw[row["projectile"]] == pytest.approx(row["A"], abs=0.006), row["id"]


def test_formula_rejects_bad_input(b):
    with pytest.raises(ValueError):
        b.yamamura_tawara(100.0, 7, 14.007, 74, 183.84, 0.0, 0.72, 2.14, 2.8)
    with pytest.raises(ValueError):
        b.yamamura_tawara(float("nan"), 7, 14.007, 74, 183.84, 8.9, 0.72, 2.14, 2.8)


def test_trim_transcription_spot_values(reg):
    recs = {r["id"]: r for r in reg["records"]}
    def y(rid, e, ang=0):
        return next(v["Y_atoms_per_ion"] for v in recs[rid]["values"] if v["E_eV"] == e and v["angle_deg"] == ang)
    assert y("TRIM-N-W", 100) == 1.72e-2
    assert y("TRIM-N-W", 1000) == 3.39e-1
    assert y("TRIM-N-W", 500, 45) == 3.10e-1
    assert y("TRIM-O-W", 300) == 1.52e-1
    assert y("TRIM-O-C", 100) == 4.59e-3


def test_every_numeric_record_is_elemental_prior_only(reg):
    src = {s["id"]: s for s in reg["sources"]}
    for r in reg["records"]:
        assert r["use"] == "ELEMENTAL_PRIOR_BOUND_ONLY", r["id"]
        assert r["target_element"] in ELEMENTS, r["id"]
        assert r["projectile"] in ("N+", "O+"), r["id"]
        assert r["evidence_level"] in range(1, 8) and r["evidence_class"] == "model-derived"
        assert src[r["source"]]["access"] == "OPEN", r["id"]
        assert r["transformation_chain"] and r["locator"]


def test_no_number_from_non_open_or_unread_sources(reg):
    used = {r["source"] for r in reg["records"]}
    for s in reg["sources"]:
        if s["access"] != "OPEN":
            assert s["id"] not in used
            assert s["numeric_values_used"] is False, s["id"]
        if s["numeric_values_used"]:
            assert s["access"] == "OPEN" and s["url"]
        assert s["access"] in {"OPEN", "OPEN_NOT_RETRIEVABLE_AUTOMATED", "PAYWALLED_ACQUISITION_NEEDED"}


def test_coverage_complete_and_never_substitutes(reg):
    cells = {(c["p4_candidate"], c["species"]): c for c in reg["coverage_matrix"]}
    assert set(cells) == {(c, s) for c in Q0_CANDIDATES for s in SPECIES}
    rec_ids = {r["id"] for r in reg["records"]}
    for (cand, sp), c in cells.items():
        assert c["candidate_specific_value"] is None
        assert c["status"] == "NO_CANDIDATE_SPECIFIC_DATA"
        assert "MEASUREMENT_NEEDED:TP-04" in c["dispositions"]
        assert set(c["elemental_prior_records"]) <= rec_ids
        if sp in ("N2+", "O2+"):
            assert c["elemental_prior_records"] == [] and c["non_representative_context_records"] == []
            assert c["prior_applicability"].startswith("NO_PRIOR_NUMBER")
    # oxide coating: metal values only as non-representative context
    assert cells[("CAND-07", "O+")]["elemental_prior_records"] == []
    assert cells[("CAND-07", "O+")]["prior_applicability"].startswith("NOT_REPRESENTATIVE")
    # 316L names no element: nothing mapped
    assert cells[("CAND-01", "N+")]["elemental_prior_records"] == []
    # graphite + O: lower-bound note
    assert "LOWER_BOUND" in cells[("CAND-09", "O+")]["bound_direction_note"]
    # alloy / coating cells always also carry the unresolved-literature acquisition request
    q0 = {q["p4_candidate"]: q for q in reg["q0_matrix"]}
    for (cand, sp), c in cells.items():
        if q0[cand]["material_class"] != "element":
            assert "AR-08" in c["dispositions"]


def test_acquisition_requests_are_lawful_pointers(reg):
    src = {s["id"]: s for s in reg["sources"]}
    for a in reg["acquisition_requests"]:
        route = a["lawful_route"].lower()
        assert any(k in route for k in ("library", "loan", "purchase", "subscription", "download")), a["id"]
        if a["source"]:
            assert src[a["source"]]["access"] in {"PAYWALLED_ACQUISITION_NEEDED", "OPEN_NOT_RETRIEVABLE_AUTOMATED"}


def test_measurement_needed_covers_q0_and_has_no_invented_domain(reg):
    m = {x["p4_candidate"]: x for x in reg["measurement_needed"]}
    assert set(m) == Q0_CANDIDATES
    for x in m.values():
        assert x["species"] == list(SPECIES)
        assert "TBD" in " ".join(x["variables_to_register_before_measurement"])
        assert "LOCK-2" in x["acceptance"]
    assert "NOT a sheath energy" in reg["reporting_energy_grid_note"]


def test_apid_fits_never_used_numerically(reg):
    for r in reg["apid_fits_transcribed"]:
        assert r["status"].startswith("NOT_USED_NUMERICALLY")
    assert not any(r["source"] == "SRC-IAEA-APID-7B" for r in reg["records"])


def test_reactive_projectile_statement_matches_inputs(reg, inputs):
    t1 = inputs["nifs_table1"]["rows"]
    ratios = [r["Us_eV"] / t1[r["target"]][0] for r in inputs["nifs_caption_fits"]["rows"] if r["best_fit_Us"]]
    text = next(h for h in reg["hard_statements"] if h.startswith("REACTIVE_PROJECTILES"))
    assert f"{min(ratios):.2f}x to {max(ratios):.2f}x" in text


def test_decision_pins_and_p4_ids(b, inputs):
    b.verify_decision_pins(inputs)          # raises on any sha256 change
    p4 = P4.read_text(encoding="utf-8")
    for ref in inputs["read_only_references"]:
        if ref["path"].endswith("p4_anode_materials_v1.json"):
            for i in ref["ids_used"]:
                assert f'"{i}"' in p4, i


def test_missing_or_bad_inputs_raise(b, inputs):
    bad = copy.deepcopy(inputs)
    del bad["nifs_table1"]
    with pytest.raises(ValueError):
        b.validate_inputs(bad)
    bad = copy.deepcopy(inputs)
    bad["sources"][0]["access"] = "FREE"
    with pytest.raises(ValueError):
        b.validate_inputs(bad)
    bad = copy.deepcopy(inputs)
    bad["species_required"] = ["N+", "O+"]
    with pytest.raises(ValueError):
        b.validate_inputs(bad)
    bad = copy.deepcopy(inputs)
    bad["decisions"][0]["json_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        b.verify_decision_pins(bad)
    bad = copy.deepcopy(inputs)
    del bad["q0_matrix"][0]["material_class"]
    with pytest.raises(ValueError):
        b.validate_inputs(bad)


def test_values_finite_and_nonnegative(reg):
    for r in reg["records"]:
        for v in r["values"]:
            for k in ("Y_atoms_per_ion", "Y", "Y_min", "Y_max"):
                if k in v:
                    assert isinstance(v[k], (int, float)) and math.isfinite(v[k]) and v[k] >= 0, (r["id"], v)


# ---------------------------------------------------------------- repair round (SPUTTER-1..3)

def test_apid_fit_is_printed_formula(b):
    """SPUTTER-1: IAEA APID 7B report p. 18: the bracket multiplies only the threshold term, not lambda."""
    lam, q, mu, el, eth = 1.6012e-02, 4.9256, 1.8338, 8.882e-07, 46.767   # APID-2.1.3.6 N -> W (PDF p. 54)
    E = 100.0
    x = (E / eth - 1.0) ** mu
    e = E * el
    w = e + 0.1728 * math.sqrt(e) + 0.008 * e ** 0.1504
    assert b.apid_fit(E, lam, q, mu, el, eth) == pytest.approx(0.5 * q * x * math.log(1 + 1.2288 * e) / (lam + x * w))
    assert b.apid_fit(E, lam, q, mu, el, eth) == pytest.approx(0.0172, rel=0.10)   # TRIM.SP 1.72e-2
    assert b.apid_fit(40.0, lam, q, mu, el, eth) == 0.0
    with pytest.raises(ValueError):
        b.apid_fit(100.0, 0.0, q, mu, el, eth)


def test_apid_fit_reproduces_trim_o_w(b, inputs):
    """SPUTTER-1: APID-2.1.3.7 (O -> W) reproduces TRIM-O-W within 10 % at 100-1000 eV."""
    row = next(r for r in inputs["apid_fit_params"]["rows"] if r["id"] == "APID-2.1.3.7")
    t = next(t for t in inputs["trim_tables"]["tables"] if t["id"] == "TRIM-O-W")
    n = 0
    for r in t["rows"]:
        if 100 <= r[0] <= 1000 and r[1]:
            y = b.apid_fit(r[0], row["lambda"], row["q"], row["mu"], row["eps_L_per_eV"], row["Eth_eV"])
            assert y / r[1] == pytest.approx(1.0, abs=0.10), r
            n += 1
    assert n >= 4


def test_apid_register_statuses_true(reg):
    """SPUTTER-1: no false 'reproduction failed' claim; the stated reason is that the fits add no independent evidence."""
    txt = json.dumps(reg)
    assert "REPRODUCTION_FAILED" not in txt and "freed" not in txt
    assert "REPRODUCTION_FAILED" not in (DIR / "SPUTTER_YIELDS_V1.md").read_text(encoding="utf-8")
    for r in reg["apid_fits_transcribed"]:
        assert r["status"] == "NOT_USED_NUMERICALLY" and "TRIM.SP" in r["status_reason"]
        if r["reproduction_check_vs_TRIM_SP"]:
            assert r["reproduction"] == "REPRODUCED_AWAY_FROM_THRESHOLD"
            assert r["worst_factor_E_ge_1p1_Eth"] <= 1.25
    chk = next(c for c in reg["consistency_checks"] if c["id"] == "CHK-APID-REPRODUCTION")
    assert chk["pass"] is True


def test_apid_misread_parameters_raise(b, inputs):
    """SPUTTER-1: the reproduction is a gate, so a mis-transcribed parameter fails the build."""
    bad = copy.deepcopy(inputs)
    next(r for r in bad["apid_fit_params"]["rows"] if r["id"] == "APID-2.1.3.7")["lambda"] = 1.173
    with pytest.raises(ValueError, match="does not reproduce"):
        b.build(bad)


@pytest.mark.parametrize("where", ["top", "source", "q0", "caption", "trim", "block", "ar", "decision"])
def test_unknown_fields_raise(b, inputs, where):
    """SPUTTER-2: the builder fails closed on unknown / typo fields."""
    bad = copy.deepcopy(inputs)
    target = {"top": bad, "source": bad["sources"][0], "q0": bad["q0_matrix"][0],
              "caption": bad["nifs_caption_fits"]["rows"][0], "trim": bad["trim_tables"]["tables"][0],
              "block": bad["nifs_table1"], "ar": bad["acquisition_requests"][0], "decision": bad["decisions"][0]}[where]
    target["typo_field"] = 1
    with pytest.raises(ValueError, match="unknown field"):
        b.validate_inputs(bad)


def test_q0_candidate_set_enforced_by_builder(b, inputs):
    """SPUTTER-2: a dropped or duplicated Q0 candidate is rejected (not 52 cells silently)."""
    bad = copy.deepcopy(inputs)
    bad["q0_matrix"] = bad["q0_matrix"][:-1]
    with pytest.raises(ValueError, match="14 S5.11 candidates"):
        b.validate_inputs(bad)
    bad = copy.deepcopy(inputs)
    bad["q0_matrix"][-1] = copy.deepcopy(bad["q0_matrix"][0])
    with pytest.raises(ValueError, match="14 S5.11 candidates"):
        b.validate_inputs(bad)


@pytest.mark.parametrize("value", [-5, float("nan"), float("inf"), "0.1", True])
def test_trim_values_must_be_finite_nonnegative(b, inputs, value):
    """SPUTTER-2: negative / non-finite / non-numeric TRIM yields raise in the builder."""
    bad = copy.deepcopy(inputs)
    bad["trim_tables"]["tables"][0]["rows"][0][1] = value
    with pytest.raises(ValueError):
        b.validate_inputs(bad)


def test_numeric_values_used_is_derived(reg, inputs, b):
    """SPUTTER-2: numeric_values_used follows the record sources; a non-OPEN numeric source raises."""
    used = {r["source"] for r in reg["records"]} | {inputs["atomic_weights"]["source"]}
    for s in reg["sources"]:
        assert s["numeric_values_used"] is (s["id"] in used), s["id"]
    for sid in ("SRC-IPP-9-132", "SRC-NIFS-DATA-23", "SRC-CIAAW-2024", "SRC-IAEA-APID-7B"):
        bad = copy.deepcopy(inputs)
        next(s for s in bad["sources"] if s["id"] == sid)["access"] = "PAYWALLED_ACQUISITION_NEEDED"
        with pytest.raises(ValueError, match="OPEN"):
            b.validate_inputs(bad)


def test_generic_vs_fit_excludes_identity_rows(reg):
    """SPUTTER-3: the O -> C caption uses Table 1 itself; it is labelled identity and excluded from the spread."""
    chk = next(c for c in reg["consistency_checks"] if c["id"] == "CHK-GENERIC-VS-FIT")
    assert chk["identity_combinations_excluded"] == ["O+ -> C"]
    assert "O+ -> C" not in chk["refitted_combinations"]
    ident = [p for p in chk["points"] if p["identity_row"]]
    assert ident and all(p["combo"] == "O+ -> C" for p in ident)
    refit = [p["generic_over_fit"] for p in chk["points"] if not p["identity_row"]]
    assert chk["ratio_min"] == min(refit) and chk["ratio_max"] == max(refit)
    assert chk["ratio_min"] > 1.0
    gen = next(r for r in reg["records"] if r["id"] == "YT-GEN-O-C")
    assert gen["has_combination_specific_fit"] is False and gen["caption_uses_table1_parameters"] is True

#!/usr/bin/env python3
"""Build the P1 ICP electron-source bench package (lane fo_a9_p1_icp_bench, trigger T_A9_P1_ICP_BENCH; owner A9.3;
owner A9.4 incorporated mechanically by fo_a9_4_incorporation, trigger T_A9_4_INCORPORATION).

Outputs (all in this directory, deterministic, byte-reproducible):
  p1_icp_bench_v1.json              machine-readable engineering test plan + data model references
  P1_ICP_BENCH.md                   companion document generated from the JSON
  p1_bench_record_schema_v1.json    JSON schema of the raw bench records, generated from p1_reducer.py constants

Usage:
  python docs/experiments/hall_icp/p1_icp_bench/build_p1_icp_bench.py           # write
  python docs/experiments/hall_icp/p1_icp_bench/build_p1_icp_bench.py --check   # verify pins + byte-exact outputs

It is an engineering test plan, a record schema and an analysis reducer: NOT a prediction and NOT a score-bearing
campaign. Every number carries a source and an evidence class or is 'TBD - requires <what>'. The only arithmetic done
here is the owner-stated stand ceiling (1500 W / 180 V), the power-envelope bound (1350 W / 180 V) and the recorder's
sccm -> mg/s cross-check of the Takahashi Ar anchor; all three are reproduced from cited inputs.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
REL = "docs/experiments/hall_icp/p1_icp_bench"
OUT_JSON = "p1_icp_bench_v1.json"
OUT_MD = "P1_ICP_BENCH.md"
OUT_SCHEMA = "p1_bench_record_schema_v1.json"
BASE_COMMIT = "ee9dc7db7d11e0b5f1d8b514258778ac1b6030d3"
A94_INC_BASE = "875ed6d0a87202bc92706b28551b0e22eda2014d"   # base of the A9.4 incorporation (fo_a9_4_incorporation)
XE_A9 = "docs/budgets/" + "xe" + "_ledger_a9/" + "xe" + "_ledger_a9_v1.json"   # path of the A9 Xe ledger
P2_PATH = "docs/experiments/hall_icp/p2_impedance_map/"
RFQ_V2_PATH = "docs/procurement/rfq_a9_v2/"
PENDING_P2 = "PENDING " + P2_PATH
PENDING_RFQ_V2 = "PENDING " + RFQ_V2_PATH

A9 = "docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json"
ANS = "docs/decisions/OD_2026_09_29_owner_answers_147.json"
PACK = "docs/decisions/OD_2026_09_29_OWNER_DECISION_PACK_147.md"
A91 = "docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json"
A91_MD = "docs/decisions/OD_2026_09_30_A9_1_FOLLOWUP_OWNER_DECISIONS.md"
A92 = "docs/decisions/OD_2026_09_30_A9_2_a907_followup_owner_decisions.json"
A92_MD = "docs/decisions/OD_2026_09_30_A9_2_A907_FOLLOWUP_OWNER_DECISIONS.md"
A93 = "docs/decisions/OD_2026_09_30_A9_3_post_a9_tier1_owner_decisions.json"
A93_MD = "docs/decisions/OD_2026_09_30_A9_3_POST_A9_TIER1_OWNER_DECISIONS.md"
A94 = "docs/decisions/OD_2026_09_30_A9_4_p1_p2_owner_decisions.json"
A94_MD = "docs/decisions/OD_2026_09_30_A9_4_P1_P2_OWNER_DECISIONS.md"
ICD = "schemas/interfaces/icp_neutralizer_icd_v1.json"
ICD_MD = "docs/interfaces/icp_neutralizer/ICP_NEUTRALIZER_ICD.md"
UB = "docs/experiments/hall_icp/uncertainty_budget/hall_icp_uncertainty_budget_v1.json"
PRE = "docs/experiments/hall_icp/prereg_framework/hall_icp_prereg_framework_v1.json"
EVI = "docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json"
VIN = "docs/experiments/hall_icp/validation_inputs/hall_icp_validation_inputs_v1.json"
MS = "docs/experiments/instrumentation/metrology_spec/metrology_measurement_spec_v1.json"
INS = "docs/experiments/instrumentation/instrumentation_definition_v1.json"
REVS = "docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json"
H21 = "docs/hardware/h2/h2_1_hall_chamber_magnet/h2_1_hall_chamber_magnet_v1.json"
H23 = "docs/hardware/h2/h2_3_gas_path_plenum/h2_3_gas_path_plenum_v1.json"
H22 = "docs/hardware/h2/h2_2_cathode_integration/h2_2_cathode_integration_v1.json"
H24 = "docs/hardware/h2/h2_4_ppu_bus/h2_4_ppu_bus_v1.json"
H26 = "docs/hardware/h2/h2_6_diagnostics_fixture/h2_6_diagnostics_fixture_v1.json"
BUS = "docs/architecture_comparison/power_boundary_a9/bus_power_boundary_a9_v1.json"
RFQ1 = "docs/procurement/rfq_a9/rfq_a9_v1.json"
M16 = "docs/experiments/hall_icp/integration/m16_v3/subsystem_maturity_v3.json"
OQS = "docs/budgets/owner_decisions/owner_questions_state_v3.json"
MASS = "docs/budgets/mass_a9/mass_a9_v1.json"
REC = "docs/experiments/hall_icp/integration/a9_10_reconciliation_v1.json"
EVIDENCE_RULES = "docs/EVIDENCE.md"
P1F = "docs/experiments/phase1_prereg_framework/phase1_prereg_framework_v1.json"
PMICD = "schemas/interfaces/preionizer_module_icd_v1.json"

PINS = [
    (A9, "74ef1a727c3656841ef115122c6d60865f7d2d93cfa29f7fb0081886484d2a1f", "governing owner decision A9"),
    (ANS, "50e39a4deac7d4ada4710b2f641d717f1c4febd59366cbc04d8c66de6b4532b1", "147 owner answers (cited by row)"),
    (PACK, "8736d88a64bf26bd06a332a68c2450a780f175fffafe5aca0625759133666976", "147 owner decision pack, verbatim"),
    (A91, "7a8f93dbc2487de90ebba0b2801fc5d3f5d983fc96ba418b55c492f1f9e851a4", "owner A9.1 (machine-readable)"),
    (A91_MD, "2587ca6931f6c9dac865005db9dc518dab0fcb829d789293467dc4179879c46e", "owner A9.1 verbatim"),
    (A92, "e5cd8fb426168b4407c2526539e670cbdeb0b33762a8b9737cc873ffb5bd2e03", "owner A9.2 (machine-readable)"),
    (A92_MD, "dbccb9284e257b55d1d7ed0587086544029396de896a3f5f4cd09fd703fd83a9", "owner A9.2 verbatim"),
    (A93, "81c69b200b9ce51f8aa745636d7aa4dbbddc39005b064235841722ebfdedad1b", "owner A9.3 (machine-readable)"),
    (A93_MD, "55a1fd84558a9590705bb82aa11db5e2b9136dd1d83a957d26614c435c707411", "owner A9.3 verbatim (binds P1)"),
    (A94, "b3d9a9f1ed5b76637b1508ca40fdd719b40f8184bdbc433804eeeb6119dc360d", "owner A9.4 P1/P2 decisions (machine-readable)"),
    (A94_MD, "53cc026d63f85bd416f8ed8f4e8f9f7e7d7fc4429dccc45b86a51390b5c08b1c", "owner A9.4 verbatim (P1Q-10/13/14, P2Q-05)"),
    (ICD, "8ec092f284505e7a538d17f568c0d9d763155f9a2ce4541223ddd114169a452c", "A9-03 ICP-neutralizer ICD (JSON)"),
    (ICD_MD, "d346bcc5a5edc4a4dfa289010c8e48371477a0f3548a5e9dcf8886b6f55dbe77", "A9-03 ICD companion"),
    (PRE, "f082a6d3eabf07485d447ace927f69e8980acbcc8eff54d0cd21f196e20a0afe", "A9-01 Hall->ICP prereg framework"),
    (UB, "c6567e6d0bbc008bedd5b9c14a9716f117144ab6952b9c498f7b0c75e02a624d", "A9-04 uncertainty budget"),
    (EVI, "092e4ca8e1827dd2e9558058a204f46510f2633316ce188e7126b697ec6d0b53", "A9-05 Takahashi 2024 extraction"),
    (VIN, "fac472e370b54875df5dea90c3c7740403da5ac1edd1af29b43ed09ee679d450", "A9-05 validation-input list"),
    (BUS, "9f6e074cc2cdd1e2445d00a14eec04b4cc33f239655f8619a789e7ae863c43e6", "A9-02 bus-power boundary"),
    (MASS, "071b03fb634c6b25ef422e7ec81006d337e6c333b80133240bdea32999a4f7d4", "A9-06 mass reconciliation"),
    (REVS, "b428565299c1c41487d9ffa50c174986d2d52c544539f89ca21b7bdbc2ae44fa", "A9-07 H2 revisions"),
    (XE_A9, "37c32cda9fb04200f6e9041b0e790ca700e270866f29e7c10f8a298034ddacfd", "A9-08 Xe ledger (A9)"),
    (RFQ1, "d2e654cf49d89b8f84a65e5bf7626517a37c02d0a4a0de97f128c3155ef4a84b", "A9-09 RFQ v1 (predates A9.2/A9.3)"),
    (REC, "155db413b16260cc2abcaf6bcbaa6a004ff7b30066a6df4dfb70698c0a8aa939", "A9-10 reconciliation"),
    (M16, "636cbd3318831f6f56e9833813c4d8c259aef7db3de1c6e503cccce14dade7e2", "M16 v3 subsystem maturity"),
    (OQS, "1c2e74340852dfe8c58b1804c3cfda2bfbfb3bfb5d631aaebd715cf716b76af2", "owner-question state v3 (read only)"),
    (INS, "7c6d37b00f38a44cded73d92d4366739eacbf013e73e98a7bfbc3fa5a5470d96", "instrumentation definition (INS-*)"),
    (MS, "55c11dc2d22fd92d95b498f72d60f2cdc0c62a45940da2446514049bd5130865", "metrology measurement spec (MS-*)"),
    (H21, "49b9a45e9347b141bf8bd1122ffba3ae038c9f088041e4410525e4ab8695b82d", "H2-1 Hall chamber / magnet"),
    (H22, "8436008ac458d4e7467a9c7c9592d5312b3912b918d584ceaf3ac8cb2745a971", "H2-2 cathode (C-1) integration"),
    (H23, "f32b05bd03aad2a09a1d9b90ee5f9423e733e6ea4cb94814c92b500590d43a7b", "H2-3 gas path / plenum"),
    (H24, "5c6623612ee9ec22899083201416f7b51a10a2d7e88456d372783ce2edde26ef", "H2-4 PPU / bus (H24-27)"),
    (H26, "bc7d6b049067c6fbd5489bda32ee9c8c1af36508576db4619b08d2c4ec196a56", "H2-6 diagnostics / fixture"),
    (EVIDENCE_RULES, "a2950352141890c12ad33e66766cd003215c807cb29203d21df090349ab90b61", "evidence rules (rule 10)"),
    (P1F, "84ba1c382dc609b3e83ad9803a57ba471dd892fd10a6a6149285701a45a65a28", "historical A5 Phase-1 framework"),
    (PMICD, "2470718e1decbde874d2362a997d1e2aaae54eb855d1ed179b930c3be6e7130e", "historical pre-ionizer module ICD"),
]
GOVERNANCE_NOT_PINNED = ["docs/orchestration/lane_registry_v1.json", "docs/orchestration/trigger_registry_v1.json",
                         "docs/orchestration/trigger_ledger_v2.jsonl", "docs/orchestration/fired_triggers.jsonl",
                         "docs/orchestration/runtime_state.json"]
FREEZE = ("NOW", "LOCK-1", "LOCK-2", "after-evidence")
EVIDENCE_CLASSES = ("measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed",
                    "owner-allocation", "owner-stated", None)


def _sha(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def _reducer():
    spec = importlib.util.spec_from_file_location("p1_reducer_for_builder", os.path.join(HERE, "p1_reducer.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify_pins():
    bad = []
    for rel, sha, _why in PINS:
        got = _sha(rel)
        if got != sha:
            bad.append("%s: expected %s got %s" % (rel, sha, got))
    if bad:
        raise SystemExit("pinned input changed (immutable input moved):\n  " + "\n  ".join(bad))


# ------------------------------------------------------------------------------------------------ arithmetic
def arithmetic():
    """The only computations of this lane, each from cited inputs."""
    a93 = _load(A93)
    flag = [f for f in a93["recorder_flags"] if "sccm" in f][0]
    # constants are the recorder's (A9.3 recorder_flags[1]); reproduced here, not chosen by this lane
    mol_per_s_per_sccm = 7.436e-7
    m_ar_g_mol = 39.948
    sccm = 70.0
    mdot = sccm * mol_per_s_per_sccm * m_ar_g_mol * 1000.0      # g/s -> mg/s
    return {
        "stand_ceiling_A": {"expr": "1500 W / 180 V", "value": round(1500.0 / 180.0, 4), "units": "A",
                            "source": A93 + " decisions.OQ-A907-02.stand_ceiling (owner-stated)"},
        "power_envelope_bound_A": {"expr": "1350 W / 180 V", "value": round(1350.0 / 180.0, 4), "units": "A",
                                   "source": A93 + " decisions.OQ-A907-02.flight_7p5A (owner-stated)"},
        "ar_anchor_check_mg_s": {"expr": "70 sccm x 7.436e-7 mol/s/sccm x 39.948 g/mol", "value": round(mdot, 3),
                                 "units": "mg/s", "source": A93 + " recorder_flags (constants as recorded): " + flag,
                                 "note": "the sccm reference condition used by Takahashi et al. is not stated in the "
                                         "extraction (verify); the recorder's constant corresponds to 0 degC / "
                                         "101.325 kPa standard conditions (verify)"},
    }


# ------------------------------------------------------------------------------------------------ anchor check
TK_CHECK = [
    ("TK-31", "owner A9.3 OQ-RFQ-02: '70 sccm ~ 2.1 mg/s for their experiment'",
     "CONFIRMED (value and locator p. 3 text). NOTE: the 70 sccm is the TOTAL Ar flow fed through the HET anode and "
     "shared by HET and ICP (G-REUSE analog); the ICP share is not separable. P1 therefore sets the flow through the "
     "H-1 gas path, not an ICP flow."),
    ("TK-21", "anchor RF forward power used by Takahashi et al.",
     "context only: 200 W forward, used as one PROPOSED P1 power level for topology reproduction (not a rating)"),
    ("TK-22", "anchor reflected power", "reported 0 W ('not detected', meter resolution not stated); P1 measures "
     "P_refl on the generator / 50-ohm side of its local match (A9.2)"),
    ("TK-26", "anchor RF power transfer efficiency", "authors' eta_p ~ 0.1 supports the A9.2 rule P_fwd != P_plasma"),
    ("TK-27", "anchor absorbed RF power estimate", "authors' ~20 W estimate; electrode eddy heating seen without "
     "plasma -> P1-S2 records collector/antenna heating in the unlit state"),
    ("TK-34", "anchor chamber pressure at 70 sccm", "facility-specific (0.028 Pa); P1 records its own p, never "
     "matches it by adjustment"),
    ("TK-40", "anchor discharge circuit", "MISMATCH WITH A9 CIRCUIT (flagged, not altered): the anchor collector sits "
     "at the negative end of V_D with no separate bias supply; A9 requires a floating ICP body and a separately "
     "controlled collector bias (owner row 70, ICD ICP-20/21). P1 treats V_collector as an explicit factor."),
    ("TK-51", "anchor 'no annular discharge without RF power'", "basis of the OQ-VI-05 topology-control sequence; "
     "not a P1 requirement (A9.3 OQ-VI-05)"),
    ("TK-52", "anchor discharge current 'about 1 A'", "FLAG: this is the HET discharge current I_D, not a measured "
     "ICP electron current (TK-56: no electron-current balance reported). The A9.1 '~1 A / 200 W Takahashi point' "
     "remains context only; never scaled to H-1."),
    ("TK-73", "anchor ignition order", "RF plasma on first, then V_D; no ignition statistics (P1 records them, row 24)"),
    ("TK-10", "anchor source tube", "open-tube coaxial pyrex tube 65 mm ID: topology precedent for OQ-VI-03"),
    ("TK-13", "anchor ion collector", "C-type stainless-steel electrode with axial slit: topology precedent; A9.1 "
     "permits 316L for the Ar engineering reproduction"),
    ("TK-23", "anchor matching network", "two variable capacitors tuned for minimum reflection: precedent for the "
     "A9.2 adjustable local match"),
]


def anchor_check():
    ev = _load(EVI)
    by_id = {x["id"]: x for x in ev["extraction"]}
    rows = []
    for tk, use, finding in TK_CHECK:
        x = by_id[tk]
        rows.append({"id": tk, "quantity": x["quantity"], "reported_value": x["value"], "unit": x["unit"],
                     "locator": x["locator"], "value_basis": x["value_basis"], "epistemic": x["epistemic"],
                     "evidence_class": x["evidence_class"], "used_for": use, "finding": finding})
    return rows


# ------------------------------------------------------------------------------------------------ content
def it(i, name, value, units, basis, source, ev, status, fp, gate=None, note=""):
    return {"id": i, "name": name, "value": value, "units": units, "basis": basis, "source": source,
            "evidence_class": ev, "status": status, "freeze_point": fp, "p1_gate": gate, "note": note}


def items(ar):
    tbd = "TBD - requires "
    return [
        it("P1-IT-01", "RF frequency", 13.56, "MHz", "owner answer", ANS + " row 72", "owner-allocation",
           "OWNER_GIVEN", "NOW"),
        it("P1-IT-02", "laboratory delivered/operating RF investigation capability (NOT a component rating)",
           [0.0, 500.0], "W", "owner answer as interpreted by A9.2", ANS + " row 72; " + A92 + " rf_500W",
           "owner-allocation", "OWNER_GIVEN", "NOW", None, "not sufficient as a rating (A9.2)"),
        it("P1-IT-03", "RF component ratings (generator, coupler, coax, connectors, match, feedthrough)",
           "TBD_AFTER_IMPEDANCE_MAP", "W, V, A", "owner decision", A92 + " a9_10_statuses; rf_500W", None,
           "TBD_AFTER_IMPEDANCE_MAP", "after-evidence", "P1-G2 (P1 envelope restricted to the procured ratings)"),
        it("P1-IT-04", "RF measurement reference plane", "generator / 50-ohm side of the LOCAL matching network",
           "-", "owner decision", A92 + " OQ-A907-11, rf_measurement_reference; ICD ICP-13/ICP-14",
           "owner-allocation", "OWNER_GIVEN", "NOW"),
        it("P1-IT-05", "reflected-power and VSWR trip thresholds",
           tbd + "the ICP antenna/load characterization of P1-S2 (A9.2: frozen after it, not invented now)", "W, -",
           "owner decision", A92 + " rf_protection", None, "TBD", "after-evidence", "P1-G2"),
        it("P1-IT-06", "I_d,stand ceiling (bench electrical design ceiling)", ar["stand_ceiling_A"]["value"], "A",
           "owner decision (1500 W / 180 V)", ar["stand_ceiling_A"]["source"] + "; " + H24 + " H24-27",
           "owner-stated", "OWNER_GIVEN (8.33_A_STAND_CEILING)", "NOW", None,
           "conductor sizing, current-sensor range, collector-circuit rating, feedthrough rating, protection, DAQ "
           "range, optional stress test; NOT evidence that H-1 requires 8.33 A; NOT the ICP-45 requirement; A9.4 "
           "execution_decisions.i_d_max_h1: retained only as the bench electrical-design ceiling, never I_d,max,H1"),
        it("P1-IT-07", "I_e,required = I_d,max,H1 (ICP-45 requirement)",
           tbd + "the maximum H-1 discharge current within the registered operating envelope, from measured/"
                 "registered H-1 operation (owner question P1Q-07 on who registers it and when)", "A",
           "owner decision", A93 + " OQ-A907-02 (ICP45_REQUIRED_CURRENT = H1_REGISTERED_MAX); " + A94 +
           " execution_decisions.i_d_max_h1", None, "TBD", "after-evidence", "P1-S7 entry",
           "A9.4: never assigned from the 8.33 A supply rating; until registered from the H-1 envelope and measured H-1 "
           "behaviour, ICP45 = NOT_EVALUATED (not PASS or FAIL); the P1 current-capability surface may be generated "
           "before it is frozen"),
        it("P1-IT-08", "flight power-envelope mathematical bound (not a requirement)",
           ar["power_envelope_bound_A"]["value"], "A", "owner decision (1350 W / 180 V)",
           ar["power_envelope_bound_A"]["source"], "owner-stated", "OWNER_GIVEN (bound only)", "NOW", None,
           "not automatically the flight discharge-current requirement"),
        it("P1-IT-09", "Takahashi Ar anchor flow", "70 sccm ~ 2.1 mg/s", "sccm / mg/s", "owner-stated; reported",
           A93 + " OQ-RFQ-02; " + EVI + " TK-31 (p. 3 text)", "owner-stated", "OWNER_GIVEN (anchor)", "NOW", None,
           "recorder arithmetic %s = %s mg/s (consistent); total HET+ICP flow in the analog"
           % (ar["ar_anchor_check_mg_s"]["expr"], ar["ar_anchor_check_mg_s"]["value"])),
        it("P1-IT-10", "Ar MFC ranges", "1 (2 overlapping only if one cannot cover the P1 sweep)", "controllers",
           "owner decision", A93 + " OQ-RFQ-02 (amends row 123 for Ar only)", "owner-allocation", "OWNER_GIVEN",
           "NOW", None, "full-scale range(s): TBD - requires the P1 Ar sweep bounds (run matrix F2) and quotations "
                        "(" + PENDING_RFQ_V2 + ")"),
        it("P1-IT-11", "Ar flow traceability path", "rate-of-rise / transfer calibration of the Ar controller",
           "-", "owner decision", A93 + " OQ-RFQ-02; " + ANS + " rows 124, 126; " + A91 + " UBQ-08",
           "owner-allocation", "OWNER_GIVEN", "NOW"),
        it("P1-IT-12", "ICP gas mode", "G-REUSE: Hall exhaust -> ICP, mdot_ICP,dedicated = 0", "mg/s",
           "owner decision", A91 + " HIQ-06; " + A93 + " OQ-RFQ-10; ICD ICP-26", "owner-allocation",
           "OWNER_GIVEN", "NOW"),
        it("P1-IT-13", "physical capped ICP gas port", "retained (capped)", "-", "owner decision",
           A93 + " OQ-RFQ-10; " + A91 + " HIQ-06, OQ-A902-05", "owner-allocation", "OWNER_GIVEN", "NOW"),
        it("P1-IT-14", "dedicated ICP feed controller", "RFQ option line only; activation only as a labelled "
           "DIAGNOSTIC variable, booked in the corresponding atmospheric/Xe ledger", "-", "owner decision",
           A93 + " OQ-RFQ-10", "owner-allocation", "OWNER_GIVEN (QUOTE_OPTION_ONLY)", "NOW"),
        it("P1-IT-15", "P1 gas and record label", "Ar only; ENGINEERING_ONLY_NON_SCORING on every record", "-",
           "owner decision", ANS + " row 36; " + A93 + " OQ-RFQ-02; " + A91 + " HIQ-08", "owner-allocation",
           "OWNER_GIVEN", "NOW", None, "Ar data never count toward DRDO atmospheric requirements"),
        it("P1-IT-16", "first-build ICP topology", "open-tube coaxial downstream ICP only; unmagnetized", "-",
           "owner decision", A93 + " OQ-VI-03; " + ANS + " row 69", "owner-allocation",
           "OWNER_GIVEN (OPEN_TUBE_COAXIAL_FIRST_BUILD)", "NOW"),
        it("P1-IT-17", "ICP body potential / collector bias", "body floating; collector bias separately controlled "
           "and metered", "-", "owner answer", ANS + " row 70; ICD ICP-20, ICP-21", "owner-allocation",
           "OWNER_GIVEN", "NOW", None, "V_collector = potential of the ICP ion-collecting electrode w.r.t. the "
           "reference declared per record (FACILITY_GROUND / ICP_BODY / ELECTRON_COLLECTOR_ELECTRODE); which "
           "reference is used is fixed with the extraction topology at P1-G0 (P1-IT-36); VI-EX-03 keeps the "
           "hall_icp_neutralizer reference a LOCK-1 item"),
        it("P1-IT-18", "collector bias V and I range", tbd + "the ICD ICP-21 collector design and A9-02 A902-23; the "
           "collector circuit current rating is sized to the 8.33 A stand ceiling (P1-IT-06)", "V / A",
           "pending", BUS + " A902-23; ICD ICP-21; " + A93 + " OQ-A907-02", None, "TBD", "after-evidence", "P1-G0"),
        it("P1-IT-19", "collector material for P1", "316L permitted for the Ar engineering reproduction; flight "
           "collector material not frozen", "-", "owner decision", A91 + " A9-03-collector", "owner-allocation",
           "OWNER_GIVEN", "NOW"),
        it("P1-IT-20", "ICP gas-line isolation qualification", "~1 kV DC at representative pressure, gas, geometry and "
           "feedthrough/isolator condition, ONLY where the gas line bridges isolated potentials; none where both "
           "ends are held at essentially the same floating potential", "V (DC)", "owner decision",
           A93 + " ICPQ-06; " + ANS + " row 105", "owner-allocation",
           "OWNER_GIVEN (ACCEPT_1KV_CLASS_REPRESENTATIVE_GAS_QUALIFICATION)", "NOW", "P1-G0"),
        it("P1-IT-21", "ICP body / collector operating isolation class (V_operating,max) relative to the Hall anode, "
           "H-1 body/common, facility ground and other isolated circuits, where those potential differences can "
           "physically occur", 350.0, "V",
           "OWNER_DECIDED (A9.4 P1Q-14, ICP_350V_CLASS): deliberate A9 extension of the row-81 350 V operating class "
           "to the ICP body / collector circuits (ICD ICP-23 carried it as PROPOSED)",
           A94 + " decisions.P1Q-14.class; " + ANS + " row 81; ICD ICP-23", "owner-stated",
           "OWNER_DECIDED (A9.4 P1Q-14 ICP_350V_CLASS)", "NOW", "P1-G0",
           "design withstand P1-IT-43, initial DWV P1-IT-44, later reverification P1-IT-45; RF insulation (ICP-44) "
           "stays OPEN (P1-IT-46)"),
        it("P1-IT-22", "local matching network", "adjustable, on / immediately adjacent to the ICP module", "-",
           "owner decision", A92 + " OQ-A907-11, icp_matching_strategy", "owner-allocation",
           "OWNER_GIVEN (LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT)", "NOW"),
        it("P1-IT-23", "RF protection functions", "reflected-power monitoring; mismatch/interlock threshold; arc "
           "detection where feasible; thermal monitoring; automatic RF reduction/shutdown", "-", "owner decision",
           A92 + " rf_protection", "owner-allocation", "OWNER_GIVEN (thresholds TBD, P1-IT-05)", "NOW"),
        it("P1-IT-24", "calorimetric cross-check agreement factor k_x", 2.0, "-", "owner decision",
           A91 + " UBQ-04; " + UB + " UB-RF-08", "owner-allocation", "OWNER_GIVEN (freeze LOCK-1)", "LOCK-1",
           "P1-G1", "failure => RF-dependent quantities EXCLUDED_INSTRUMENT until resolved"),
        it("P1-IT-25", "thermal abort values", tbd + "validated continuous-use limits per component (UBQ-06 rule: "
           "limit - 50 K for score-bearing operation; application to non-scoring P1 is owner question P1Q-04)",
           "degC", "owner decision (rule)", A91 + " UBQ-06; " + ANS + " row 86", None, "TBD", "after-evidence",
           "P1-G0"),
        it("P1-IT-26", "coupled H-1 / ICP thermal closure", "ICP_COUPLED_THERMAL = UNRESOLVED", "-",
           "owner decision", A92 + " icp_coupled_thermal, a9_10_statuses", "owner-allocation",
           "UNRESOLVED", "NOW", None, "never reported as a thermal PASS; P1 temperatures are records only"),
        it("P1-IT-27", "P_mains,in classification", "engineering quantity of the GROUND/FACILITY_ONLY laboratory "
           "generator; never evidence for P_bus < 1.5 kW", "W", "owner decision", A93 + " OQ-RFQ-06",
           "owner-allocation", "OWNER_GIVEN (YES_GROUND_ONLY)", "NOW"),
        it("P1-IT-28", "electron cost definitions", "C_e = P_RF,delivered / I_e; C_e,DC = P_generator,input / I_e; "
           "each with its boundary label", "W/A", "owner decision", A93 + " OQ-RFQ-06.p1_outputs",
           "owner-allocation", "OWNER_GIVEN", "NOW"),
        it("P1-IT-29", "neutralization-margin form (used only once I_d,max,H1 is registered)",
           "M_n = I_e,cap / I_d,dem - 1; one-sided lower confidence bound > 0; one-sided alpha 0.05 per absolute gate",
           "-", "owner decision", A91 + " UBQ-02, UBQ-07", "owner-allocation", "OWNER_GIVEN (freeze LOCK-1)",
           "LOCK-1"),
        it("P1-IT-30", "stable ICP operating region criteria (P1 -> P2 handoff)", tbd + "owner decision on the "
           "PROPOSED form (P1Q-01): ignition repeatability, relative drift of I_e and P_refl (and Z where measured) "
           "over a dwell, absence of mode jumps, minimum dwell duration", "-, s", "PROPOSED form",
           "this lane", None, "PROPOSED (values TBD)", "after-evidence", "P1-G5"),
        it("P1-IT-31", "registered Hall start-attempt limits (OQ-VI-05 step 4)", tbd + "registration before P1-S6 "
           "(P1Q-02)", "V, A, s, count", "owner decision (registration required)", A93 + " OQ-VI-05", None, "TBD",
           "after-evidence", "P1-S6 entry"),
        it("P1-IT-32", "sustained-discharge definition (OQ-VI-05 steps 5 and 7)", tbd + "registration before P1-S6 "
           "(P1Q-03)", "A, s", "owner decision (registration required)", A93 + " OQ-VI-05", None, "TBD",
           "after-evidence", "P1-S6 entry"),
        it("P1-IT-33", "held-out partition before any Hall-on reading", "HI-HOLDOUT-A signed before P1-S6 "
           "(first Hall-on reading on the actual H-1, Ar included)", "-", "owner decision",
           A91 + " HIQ-04; " + PRE + " stage HI-HOLDOUT-A", "owner-allocation", "OWNER_GIVEN", "NOW", "P1-S6 entry"),
        it("P1-IT-34", "engineering chamber for ICP-only stages", "a smaller domestic chamber may be used for "
           "engineering-only stages P1-S0..S5", "-", "owner answer", ANS + " row 139", "owner-allocation",
           "PROPOSED (application to P1)", "NOW"),
        it("P1-IT-35", "Z_ICP measurement during P1", PENDING_P2 + " (V/I sensing, coupler chain, de-embedding); "
           "until available Z_ICP is recorded NOT_MEASURED_PENDING_P2_CHAIN", "ohm", "owner decision",
           A93 + " authorizations.P2", None, "PENDING", "after-evidence"),
        it("P1-IT-36", "P1-S4 electron-extraction topology (Hall discharge OFF): electron-collecting electrode, its "
           "geometry and position, bias polarity and reference, instrumented terminals",
           tbd + "registration at P1-G0 (owner question P1Q-09, narrowed by A9.4 P1Q-10: ICP45_CAPACITY records use "
                 "the dedicated, isolated, instrumented electron-collecting electrode, i.e. option (A); geometry, "
                 "position and V_collector reference stay open). Fixed by physics / sources: the extracted "
           "electrons must be sunk by an electrode positive w.r.t. the ICP ion-collecting electrode (in the "
           "anchor the ion collector is the negative end of V_D and the HET anode sinks the electrons, TK-13 / "
           "TK-40); with the Hall discharge OFF the H-1 anode is NOT used as the sink (a positively biased H-1 anode "
           "with Ar flowing is a Hall discharge, contradicting P1-S4). Candidates: (A) a dedicated isolated "
           "downstream electron-collecting target, instrumented as terminal 'electron_collector'; (B) the grounded "
           "chamber wall (sink = facility_ground terminal). PROPOSED: (A), because with (B) ICP emission cannot be "
           "separated from wall / facility current paths in the Kirchhoff closure", "-, mm, V", "this lane (form) "
           "+ published anchor", EVI + " TK-13, TK-40; ICD ICP-21; " + VIN + " VI-EX-03", None,
           "TBD (PROPOSED option A)", "after-evidence", "P1-G0",
           "the reducer requires extraction.topology_id and electron_collecting_electrode on every record and "
           "refuses H1_ANODE with the Hall discharge OFF and anything but H1_ANODE with it ON; it refuses an "
           "ICP45_CAPACITY record whose sink is not DEDICATED_ELECTRON_COLLECTOR_TARGET (A9.4 P1Q-10)"),
        it("P1-IT-37", "facility-electron pair pressure-match tolerance (P1-D-07)", tbd + "registration at P1-G0 "
           "(owner question P1Q-11); the reducer takes it as an explicit input and has no default", "- (relative)",
           "this lane (form)", "this lane", None, "TBD", "after-evidence", "P1-G0"),
        it("P1-IT-38", "I_e,cap definition for the ICP-45A engineering evaluation", "OWNER_DECIDED (A9.4 P1Q-10, "
           "CAPACITY_EXTRACTION_FORM): discharge-OFF extraction measurement - Hall discharge supply OFF and electrically "
           "(physically) disconnected from the H-1 anode; ICP operating; electrons extracted to a dedicated, isolated, "
           "instrumented electron-collecting electrode; gas, magnetic field, pressure and geometry of the registered "
           "H-1 operating condition; matched RF-OFF record quantifying facility/background electron current. "
           "I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF (A9.4 recorder reading of the incomplete verbatim "
           "'Define:' formula, decisions.P1Q-10.definition_recorder_reading; owner may correct - P1Q-16), subject to "
           "current-path closure (P1-IT-47) and the registered uncertainty treatment. Qualification I_e,cap >= "
           "I_d,max,H1 with the preregistered one-sided lower confidence bound on M_n = I_e,cap / I_d,max,H1 - 1 above "
           "zero. Hall-ON records are retained only as NEUTRALIZATION_CONSISTENCY, never ICP45_CAPACITY (with Hall ON "
           "I_e,ICP ~ I_d because the anode closes the discharge circuit). Only the dedicated electron-collector "
           "current is the capacity measurand", "A", "owner decision",
           A94 + " decisions.P1Q-10; " + A94_MD + " P1Q-10; " + A91 + " ICP-45, UBQ-02; " + A93 + " OQ-A907-02",
           "owner-stated", "OWNER_DECIDED (A9.4 P1Q-10 CAPACITY_EXTRACTION_FORM)", "NOW", "P1-S7 entry",
           "synthetic records only ever yield SYNTHETIC_TEST_ONLY_NOT_EVIDENCE; excluded records are listed with "
           "reasons; until I_d,max,H1 is registered, or without an eligible closure-valid ICP45_CAPACITY record, the "
           "status is exactly NOT_EVALUATED, never PASS or FAIL"),
        it("P1-IT-39", "H-1 electrical configuration during ICP-45 discharge-OFF capacity records (anode, discharge-"
           "supply output, H-1 body / magnetic circuit)", "OWNER_DECIDED (A9.4 P1Q-13, ANODE_FLOATING / "
           "BODY_SINGLE_POINT_METERED_GROUND): the H-1 anode is physically disconnected from the discharge supply and "
           "left floating (never a commanded-zero supply left attached); V_anode on a high-impedance isolated channel; "
           "anode terminal OPEN_CIRCUIT_BY_CONSTRUCTION. The H-1 body / magnetic circuit has exactly one deliberate "
           "facility-ground connection through an instrumented / metered return (no second chassis / stand / coax / "
           "shield path); I_body->ground measured continuously during capacity records; ICP body potential, anode "
           "potential, dedicated collector potential / current and chamber / facility return current (where "
           "measurable) monitored. A metered-return anode exists only as a separately registered DIAGNOSTIC_VARIANT "
           "that never replaces the floating-anode baseline and never feeds I_e,cap", "-, V, A", "owner decision",
           A94 + " decisions.P1Q-13; " + A94_MD + " P1Q-13", "owner-stated",
           "OWNER_DECIDED (A9.4 P1Q-13 ANODE_FLOATING / BODY_SINGLE_POINT_METERED_GROUND)", "NOW", "P1-G0",
           "the configuration id is registered at P1-G0; the reducer requires h1_electrical {config_id, anode_state, "
           "V_anode_V, h1_body_state, discharge_supply_connection} on every record and REFUSES an ICP45_CAPACITY record "
           "with a METERED_RETURN anode, a connected supply, no high-impedance V_anode channel or no continuous "
           "h1_body terminal (capacity_monitoring)"),
        it("P1-IT-40", "meaning of hall_discharge_state", "state of the discharge-supply OUTPUT: ON = V_d applied "
           "(output enabled, anode connected); OFF = output disabled and anode disconnected. Whether a discharge "
           "is sustained is recorded separately (hall_discharge_sustained, against P1-IT-32)", "-",
           "this lane (definition)", "this lane; " + A93 + " OQ-VI-05 (steps 4-5 separate the start attempt from "
           "the sustainment observation)", "assumed", "PROPOSED (definition)", "NOW", "P1-G0",
           "the P1-S7H (Hall-ON follow-up) RF-OFF facility pair is taken with V_d applied (state ON) inside the "
           "registered start-attempt limits P1-IT-31, whether or not a discharge is sustained; OFF also requires "
           "discharge_supply_connection = PHYSICALLY_DISCONNECTED (A9.4 P1Q-13)"),
        it("P1-IT-41", "validity of a MEASURED line/match loss", tbd + "the P1-S1/S2 two-port data for the "
           "residual-|Gamma| validity limit valid_max_gamma_abs (frozen at P1-G1). Form: each MEASURED "
           "P_line/match,loss is de-embedded from the two-port S-parameter data at the recorded match_setting_id; "
           "it is valid only at that setting and up to that limit; outside it the loss must be FLAGGED_NOT_MEASURED",
           "W, -", "this lane (form)", A92 + " OQ-A907-11 (P_delivered with the loss term); " + UB + " UB-RF-05",
           None, "TBD (form fixed; limit value from S1/S2)", "after-evidence", "P1-G1"),
        it("P1-IT-42", "I_e sign convention and channel resolution", "I_e > 0 = net electrons extracted from the "
           "ICP; the collector_supply terminal carries I_A = +I_e (conventional current into the isolated network); "
           "the two readings must agree within the I_e channel resolution (TBD - requires the channel "
           "certificate)", "A", "this lane (convention)", "this lane", "assumed", "PROPOSED (convention)", "NOW",
           "P1-G0", "negative I_e is flagged (net ion collection or sensor orientation), not silently accepted; the "
           "capacity measurand I_e,collector = -I_A(electron_collector) under the same convention (A9.4 P1Q-10)"),
        it("P1-IT-43", "ICP body / collector minimum design withstand V_design,withstand", 525.0, "V",
           "owner decision: >= 1.5 x V_operating,max = 350 V; a minimum design basis, NOT the qualification-test "
           "voltage", A94 + " decisions.P1Q-14.design_margin", "owner-stated",
           "OWNER_DECIDED (A9.4 P1Q-14; minimum, >=)", "NOW", "P1-G0"),
        it("P1-IT-44", "initial bench dielectric-withstand (DWV) qualification of passive insulation paths and "
           "feedthrough assemblies", {"V_test_V_DC": 1050.0, "duration_s": 60.0}, "V (DC), s",
           "owner decision: ~3 x the 350 V nominal class, 'Level-2-style' per the owner-stated ECSS high-voltage "
           "guidance (standard and clause not identified in the record - verify, A9.4 recorder_flags[1]); where "
           "component ratings permit; current-limited; sensitive electronics disconnected where necessary; leakage "
           "recorded; in the relevant insulation configuration; before first HV/RF operation; plus representative-"
           "pressure/gas testing for paths exposed to the Paschen-risk region", A94 + " decisions.P1Q-14.initial_dwv; "
           + A94_MD + " P1Q-14", "owner-stated", "OWNER_DECIDED (A9.4 P1Q-14 1.05kV_INITIAL_DWV)", "NOW", "P1-G0",
           "leakage acceptance value: TBD - requires the insulation-path / feedthrough ratings (not given by the owner); "
           "distinct from the A9.3 ICPQ-06 ~1 kV representative-gas qualification of ICP gas lines (P1-IT-20); not "
           "repeated before each campaign (P1-IT-45)"),
        it("P1-IT-45", "later acceptance / reverification of the ICP body / collector insulation",
           tbd + "an owner-registered lower controlled level / procedure (A9.4 P1Q-14: the 1.05 kV test is "
                 "qualification-style and is not repeated before every campaign; requalification only after a fault "
                 "or hardware modification; owner question P1Q-17)", "V (DC), s", "owner decision (rule)",
           A94 + " decisions.P1Q-14.no_repeated_hipot", None, "TBD", "after-evidence", "before any reverification"),
        it("P1-IT-46", "ICP antenna / matching-network RF insulation (ICD ICP-44): RF peak voltage, RF current, RF "
           "creepage/clearance, combined RF + DC stress, vacuum/gas breakdown",
           tbd + "separate RF qualification (A9.4 P1Q-14: this decision does not close ICP-44); ratings "
                 "TBD_AFTER_IMPEDANCE_MAP", "V (RF peak), A, mm", "owner decision",
           A94 + " decisions.P1Q-14.rf_insulation; ICD ICP-44", None, "TBD", "after-evidence", "P1-G2",
           "ICP-44 stays OPEN; never PASS"),
        it("P1-IT-47", "Kirchhoff closure tolerance for ICP-45 capacity points (registered sign convention)",
           tbd + "registration before the first ICP45_CAPACITY record from the channel resolutions of the collector, "
                 "body, anode, facility and ICP-body terms (owner question P1Q-15); the reducer takes it as an explicit "
                 "input (closure_rule) and has no default", "- (relative)", "owner decision (rule: a large "
           "unexplained residual invalidates the capacity point)", A94 + " decisions.P1Q-13.closure", None, "TBD",
           "after-evidence", "P1-G0",
           "terms: I_collector + I_body + I_anode + I_facility + I_ICP,body ~ 0 (A9.4 P1Q-13); without a registered "
           "tolerance no capacity point is admitted (NOT_EVALUATED)"),
    ]


def stages():
    return [
        {"id": "P1-S0", "name": "hardware / safety readiness", "prereg_stage": "HI-ENG",
         "entry": ["A9.3 recorded and pinned (this file)", "hardware readiness checklist items for S0-S2 AVAILABLE "
                   "(hardware_readiness, families RF / gas_metrology / vacuum_facility / hall_electrical / "
                   "mechanical_icp_fabrication)", "responsible engineer named or functional role assigned (owner "
                   "row 140)"],
         "work": ["install RF, HV, gas, vacuum and thermal interlocks (safety_interlocks)", "ICPQ-06 isolation "
                  "qualification of every ICP gas line that bridges isolated potentials (P1-IT-20)",
                  "provisional protective settings of the procured generator/match recorded as PROVISIONAL (not the "
                  "frozen trip thresholds, P1-IT-05)", "DAQ and common time base (INS-18) verified"],
         "exit": ["P1-G0 readiness record signed: interlock functional-test log, isolation results, instrument "
                  "certificates or their TBD status, collector bias range and Ar MFC range(s) recorded",
                  "P1-S4 electron-extraction topology registered with an id (P1-IT-36: electron-collecting "
                  "electrode, geometry and axial/radial position, bias polarity, V_collector reference, "
                  "instrumented terminals)", "facility-pair pressure-match tolerance registered (P1-IT-37)",
                  "H-1 electrical configuration registered with an id (P1-IT-39, A9.4 P1Q-13: anode physically "
                  "disconnected and floating while the discharge supply is OFF, metered return only as a registered "
                  "DIAGNOSTIC_VARIANT; discharge-supply output state; H-1 body / magnetic-circuit single-point metered "
                  "ground)",
                  "electrical isolation verification of every floating circuit (collector / ICP ion-collecting "
                  "electrode, ICP body, electron-collecting target, H-1 anode and discharge-supply output) by "
                  "insulation-resistance / hipot test BEFORE the first HV/RF operation (first collector bias P1-S4, "
                  "first V_d P1-S6): initial DWV 1.05 kV DC for 60 s on passive insulation paths and feedthrough "
                  "assemblies where component ratings permit, current-limited, sensitive electronics disconnected "
                  "where necessary, leakage recorded, in the relevant insulation configuration, plus representative-"
                  "pressure/gas testing of Paschen-risk paths (A9.4 P1Q-14; P1-IT-21 / P1-IT-43 / P1-IT-44); leakage "
                  "acceptance TBD; the ICPQ-06 ~1 kV gas-line qualification (P1-IT-20) stays a separate test",
                  "H-1 body / magnetic circuit single-point metered facility-ground return installed and verified "
                  "(no second chassis / stand / coax / shield path) and the high-impedance isolated V_anode channel "
                  "installed (A9.4 P1Q-13; P1-IT-39)"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "not installed / OFF"},
        {"id": "P1-S1", "name": "RF cold checkout into the dummy load", "prereg_stage": "HI-S1A (module bench check)",
         "entry": ["P1-G0 signed"],
         "work": ["generator -> directional coupler -> 50-ohm line -> dummy load / calorimeter",
                  "coupler forward/reflected vs calorimetry cross-check (UB-RF-08, k_x = 2, P1-IT-24)",
                  "line and local-match loss characterization (two-port, A9H-INS-03; UB-RF-05)",
                  "harmonic content (UB-RF-06)", "P_mains,in by power analyzer vs P_fwd (engineering, GROUND/"
                  "FACILITY_ONLY; never P_bus, never A902-21 which needs a DC-input source)"],
         "exit": ["P1-G1: RF chain characterized; line/match loss available as MEASURED (else every P_delivered is "
                  "FLAGGED_NOT_MEASURED and reported as an upper bound); if the cross-check fails, RF quantities are "
                  "EXCLUDED_INSTRUMENT until resolved (UBQ-04)"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "OFF"},
        {"id": "P1-S2", "name": "RF cold checkout into the unlit antenna through the local match",
         "prereg_stage": "HI-S1A (module bench check)", "entry": ["P1-G1 passed", "vacuum below the facility "
                                                                  "operating limit (TBD - requires facility rules)"],
         "work": ["cold antenna reflection / impedance through the local match (VNA, A9H-INS-03; " + PENDING_P2 + ")",
                  "match tuning range and residual |Gamma| at the coupler plane at low power",
                  "antenna and collector heating without plasma (anchor TK-27 reports electrode eddy heating)",
                  "RF pickup on H-1 and diagnostic channels (ICD ICP-17; owner row 64)",
                  "RF protection functional test (reflected power, mismatch, arc where feasible, thermal)",
                  "optical-emission photodiode (INS-P2-10, P1-M-28) dark/background and RF-powered known-unlit "
                  "records, logged simultaneously with P_refl, antenna current, collector/current-path response and "
                  "pressure: inputs of the P2 unlit threshold (A9.4 P2Q-05; no numeric threshold set here)"],
         "exit": ["P1-G2: reflected-power and VSWR trip thresholds FROZEN from this characterization and recorded "
                  "with an id (A9.2); the P1 RF envelope is restricted to the procured ratings "
                  "(TBD_AFTER_IMPEDANCE_MAP)"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "OFF"},
        {"id": "P1-S3", "name": "ICP ignition map under G-REUSE", "prereg_stage": "HI-S1A (module bench check)",
         "entry": ["P1-G2 passed", "Ar flowing through the H-1 gas path (G-REUSE), Hall discharge supply OFF, C1 "
                   "not installed or disconnected", "H-1 anode in the registered configuration (P1-IT-39: "
                   "physically disconnected and floating with V_anode recorded; metered return only as a registered "
                   "DIAGNOSTIC_VARIANT, A9.4 P1Q-13)", "ICP ignition procedure "
                   "registered (id)"],
         "work": ["ascending P_fwd ladder at each Ar flow level (run matrix F1 x F2, F6)",
                  "record per attempt: ignition yes/no, P_fwd and P_refl at ignition, match setting, delay, "
                  "extinction, any discontinuity of P_refl / antenna current / emission (owner row 24)",
                  "photodiode (P1-M-28) known-lit records at established plasma points (A9.4 P2Q-05 threshold input; "
                  "loss of line of sight or saturation recorded, such samples are never unlit evidence)"],
         "exit": ["ignition map (descriptive) incl. non-ignition regions; no verdict"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "OFF"},
        {"id": "P1-S4", "name": "progressive electron-current capability sweep",
         "prereg_stage": "HI-S1A (module bench check)", "entry": ["ignition region from P1-S3",
                                                                   "collector circuit rated to the 8.33 A stand "
                                                                   "ceiling basis (P1-IT-06)",
                                                                   "extraction topology registered at P1-G0 "
                                                                   "(P1-IT-36); the H-1 anode is not the electron "
                                                                   "sink while the Hall discharge is OFF"],
         "work": ["electron extraction to the registered electron-collecting electrode (PROPOSED: dedicated "
                  "isolated downstream target, terminal 'electron_collector'); the ICP ion-collecting electrode is "
                  "biased negative w.r.t. that electrode (TK-40 polarity); V_collector recorded against the "
                  "registered reference",
                  "collector bias sweep at each (P_RF, mdot) point, ascending current limit with hold points",
                  "report the SURFACE I_e = f(P_RF, p, mdot, Z_ICP, V_collector) (A9.3 OQ-A907-02)",
                  "Kirchhoff current-path closure per point (collector, ICP body, facility/chamber ground, H-1 anode "
                  "(MEASURED metered return or OPEN_CIRCUIT_BY_CONSTRUCTION, P1-IT-39), and the electron_collector "
                  "terminal when the dedicated target is used)", "V_anode recorded (P1-M-15)",
                  "facility-electron contribution check: RF OFF at the same bias and reference, flow, gas mode, "
                  "Hall state, extraction topology and pressure (within P1-IT-37)",
                  "C_e and C_e,DC with boundary labels per point",
                  "records intended as ICP-45 capacity candidates are registered as record_class ICP45_CAPACITY in the "
                  "A9.4 P1Q-13 configuration (anode floating, supply physically disconnected, continuous h1_body "
                  "ground current, dedicated collector); other records are ENGINEERING_SURFACE"],
         "exit": ["surface table filed; the ICP45_CAPACITY records are the P1-IT-38 (OWNER_DECIDED, A9.4 P1Q-10) "
                  "I_e,cap candidates once I_d,max,H1 and its registered points exist; ICP-45A exactly NOT_EVALUATED "
                  "until then; never PASS because 1 A, 2 A, ... is reached"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "OFF"},
        {"id": "P1-S5", "name": "stability dwells and stable-region handoff to P2",
         "prereg_stage": "HI-S1A (module bench check)", "entry": ["surface from P1-S4"],
         "work": ["repeated re-ignitions and dwells at candidate points (repeats: run matrix)",
                  "dwell metrics: relative drift of I_e and P_refl (and Z where measured), maximum step / std "
                  "(mode-jump indicator), ignition success fraction; temperatures recorded"],
         "exit": ["P1-G5: 'stable ICP operating region' handoff record to P2 (" + PENDING_P2 + ") classified only "
                  "against owner-frozen criteria (P1Q-01); without them the classification is NOT_EVALUATED and the "
                  "raw metrics are handed over"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "OFF"},
        {"id": "P1-S6", "name": "OQ-VI-05 Ar topology-control sequence (H-1 + ICP)",
         "prereg_stage": "HI-AR (after HI-HOLDOUT-A)",
         "entry": ["HI-HOLDOUT-A signed (A9.1 HIQ-04; first Hall-on reading on the actual H-1)",
                   "registered Hall start-attempt limits (P1-IT-31) and sustainment definition (P1-IT-32)",
                   "C1 disconnected / not supplying electrons, verified", "discharge-supply current limit set "
                   "inside the registered limits; conductors/sensors sized to the stand ceiling",
                   "hall_anode terminal instrumented for the Kirchhoff closure"],
         "work": ["seven steps verbatim (topology_control.steps); record V_d(t), I_d(t), I_e,ICP(t), P_RF,fwd(t), "
                  "P_RF,refl(t) and collector/reference potentials"],
         "exit": ["observation recorded with classification REQUIRED_ENGINEERING_CONTROL_NON_SCORING; an "
                  "unexpected sustained discharge with ICP OFF opens P1-S6D; never PASS/FAIL"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "ON (start attempt)"},
        {"id": "P1-S6D", "name": "current-path diagnosis branch", "prereg_stage": "HI-AR",
         "entry": ["P1-S6 step 5 sustained, or any closure residual not explained"],
         "work": ["Kirchhoff closure over collector, ICP body, Hall anode and facility/chamber ground currents",
                  "facility-electron check (RF off, C1 off), residual-plasma timing, candidate secondary-electron "
                  "surfaces and grounding configuration recorded", "repeat with each grounding configuration "
                  "recorded (no configuration chosen to make the finding disappear)"],
         "exit": ["current-path attribution record (descriptive); the ICP architecture is not invalidated by the "
                  "finding itself (A9.3 OQ-VI-05)"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "ON / OFF as diagnosed"},
        {"id": "P1-S7", "name": "ICP-45A discharge-OFF capacity at registered H-1 conditions (conditional)",
         "prereg_stage": "HI-AR",
         "entry": ["I_d,max,H1 registered from the registered H-1 operating envelope and measured H-1 behaviour, never "
                   "from the 8.33 A supply rating (P1-IT-07; A9.4 execution_decisions.i_d_max_h1)",
                   "one-sided margin rule and uncertainties supplied (P1-IT-29)",
                   "Kirchhoff closure tolerance and sign convention registered (P1-IT-47)",
                   "H-1 electrical configuration per A9.4 P1Q-13 registered (P1-IT-39)"],
         "work": ["CAPACITY block (ICP-45A, record_class ICP45_CAPACITY): Hall discharge supply OFF and physically "
                  "disconnected from the H-1 anode (anode floating, V_anode on a high-impedance isolated channel, "
                  "OPEN_CIRCUIT_BY_CONSTRUCTION); ICP operating; electrons extracted to the dedicated, isolated, "
                  "instrumented electron-collecting electrode (P1-IT-36); gas / magnetic field / pressure / geometry of "
                  "each registered H-1 point (h1_point_id); ascending to and beyond I_d,max,H1 inside the stand-ceiling "
                  "ratings; matched RF-OFF ICP45_CAPACITY record at every candidate point (P1-D-07); H-1 body single-"
                  "point metered return with I_body->ground logged continuously; ICP body, anode and collector "
                  "potentials and chamber / facility return current (where measurable) monitored; Kirchhoff residual "
                  "per point against P1-IT-47 (P1-D-13)",
                  "I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF (P1-IT-38, OWNER_DECIDED A9.4 P1Q-10); ICP-45A "
                  "condition I_e,cap >= I_d,max,H1 with the one-sided lower bound of M_n above zero",
                  "never the largest current in the bundle, never an RF-OFF, dedicated-feed, Hall-ON, metered-return "
                  "(DIAGNOSTIC_VARIANT), closure-invalid or uncorrected record as I_e,cap"],
         "exit": ["ICP-45A engineering-only evaluation record (A9.1 ICP-45A) or exactly NOT_EVALUATED (never PASS / "
                  "FAIL without registration and an eligible capacity record); ICP-45N on N2 still required before "
                  "any score-bearing hall_icp_neutralizer point; BLOCKED (surface only) while the entry is unmet"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "OFF (supply physically disconnected)"},
        {"id": "P1-S7H", "name": "Hall-ON follow-up at the corresponding point (NEUTRALIZATION_CONSISTENCY)",
         "prereg_stage": "HI-AR",
         "entry": ["discharge-OFF capacity shown at the corresponding registered H-1 point (P1-S7 evaluation record; "
                   "A9.4 P1Q-10 'After discharge-OFF capacity has been shown')",
                   "registered Hall start-attempt limits (P1-IT-31) and sustainment definition (P1-IT-32): the Hall-on "
                   "RF-OFF facility pair (V_d applied, C1 disconnected, ICP RF OFF) is the OQ-VI-05 step-4 situation "
                   "and stays inside them"],
         "work": ["repeat the corresponding Hall-ON point (record_class NEUTRALIZATION_CONSISTENCY; discharge supply ON "
                  "and connected, electrons sunk by the H-1 anode, C1 disconnected) and verify: Hall discharge "
                  "sustainment; current closure (incl. hall_anode); neutralization behaviour (ICP-supplied current vs "
                  "I_d, P1-D-12); stability (dwell metrics, P1-D-08); collector / reference potentials; RF power "
                  "(P_fwd, P_refl)",
                  "descriptive only: never ICP45_CAPACITY and never I_e,cap (current continuity bounds it by I_d)"],
         "exit": ["NEUTRALIZATION_CONSISTENCY record showing whether the separately demonstrated capacity operates in "
                  "the real Hall loop; no PASS / FAIL"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "ON (consistency follow-up)"},
        {"id": "P1-S8", "name": "close-out and handoffs", "prereg_stage": "-",
         "entry": ["P1-S5 done (P1-S6/S7/S7H as far as their entries allow)"],
         "work": ["P2 handoff (stable region, match settings, cold Z)", "ICP recipe inputs for LOCK-1 (A9.1 HIQ-08)",
                  "frozen trip thresholds (P1-G2)", "C_e / C_e,DC tables as the efficiency input a future "
                  "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE must beat", "M16 row notes for the M16 owner lane"],
         "exit": ["P1 report (engineering-only); no architecture verdict; no winner"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "-"},
    ]


def topology_control(red):
    return {"source": A93_MD + " section 2 (verbatim); " + A93 + " decisions.OQ-VI-05",
            "classification": red.TOPOLOGY_CONTROL_LABEL,
            "steps": [{"step": n, "text": t} for n, t in red.SEQUENCE_STEPS],
            "signals": list(red.SEQUENCE_SIGNALS),
            "interpretation": ["desired Takahashi-like observation: ICP OFF => no sustained Hall discharge; ICP ON => "
                               "sustained Hall discharge", "'Hall must not run without ICP' is NOT preregistered as "
                               "a physics requirement", "an unexpected sustained discharge (facility electrons, "
                               "secondary electron emission, residual plasma, another current path) is a finding "
                               "requiring current-path diagnosis (P1-S6D); it does not by itself invalidate the ICP "
                               "architecture", "what must be demonstrated is that the ICP supplies the required "
                               "electron current and neutralization function"],
            "observation_vocabulary": ["TAKAHASHI_LIKE_OBSERVATION", "UNEXPECTED_SUSTAINED_DISCHARGE_ICP_OFF",
                                       "NO_SUSTAINED_DISCHARGE_WITH_ICP_ON"]}


def m(i, q, sym, units, inst, plane, sampling, unc, stages_, status, note=""):
    return {"id": i, "quantity": q, "symbol": sym, "units": units, "instrument_class": inst,
            "reference_plane": plane, "sampling": sampling, "uncertainty_sources": unc, "stages": stages_,
            "status": status, "note": note}


SAMP = "TBD - frozen at P1-G0 (PROPOSED: continuous logging on the common time base INS-18)"


MS_CAL = ("MS-G-01, MS-G-02, MS-G-03 applied to this instrument's calibration certificate (accredited scope, "
          "SI-traceable chain, GUM uncertainty; as IF-P1-20); no MS-M measurand covers it (MS-M-01..05 are post-test "
          "external-lab measurands: mass, profile, SEM/EDS, XPS, C-1 orifice)")
MS_NONE = "none: state / event record, not a calibrated measurand (MS-M-01..05 do not apply)"
MS_OPT = ("none as an absolute measurand: relative optical-intensity indicator; its unlit threshold comes from the "
          "P1 dark/background, RF-powered known-unlit and known-lit records and is frozen before the P2 map (A9.4 "
          "P2Q-05); amplifier gain setting and dark offset recorded per block")
MS_BY_ID = {"P1-M-09": MS_NONE, "P1-M-23": MS_NONE, "P1-M-25": MS_NONE, "P1-M-28": MS_OPT}


def measurements():
    rows = _measurements()
    for r in rows:
        r["metrology_spec"] = MS_BY_ID.get(r["id"], MS_CAL)
    return rows


def _measurements():
    rf_unc = ["UB-RF-02", "UB-RF-03", "UB-RF-04", "UB-RF-07", "A9H-CAL-02"]
    return [
        m("P1-M-01", "RF forward power", "P_RF,fwd", "W", "directional coupler + power sensor (A9H-INS-01)",
          "generator / 50-ohm side of the local match (ICP-14; UB-RF-09)", SAMP, rf_unc, "S1-S8", "REQUIRED"),
        m("P1-M-02", "RF reflected power", "P_RF,refl", "W", "directional coupler + power sensor (A9H-INS-01)",
          "generator / 50-ohm side of the local match", SAMP, rf_unc + ["A9H-INS-16"], "S1-S8", "REQUIRED"),
        m("P1-M-03", "line + local-match loss", "P_line/match,loss", "W", "two-port S-parameter characterization "
          "(A9H-INS-03) + dummy-load/calorimeter (A9H-INS-02)", "coupler plane -> antenna feed",
          "per configuration change and per block (TBD - frozen at P1-G1)", ["UB-RF-05"], "S1, S2", "REQUIRED",
          "each MEASURED value is de-embedded from the two-port data AT the recorded match_setting_id and is valid "
          "only up to the residual |Gamma| limit of that characterization (P1-IT-41); otherwise FLAGGED_NOT_MEASURED "
          "and P_delivered is reported as an upper bound only"),
        m("P1-M-04", "calorimetric RF cross-check", "P_cal", "W", "calorimetric load (A9H-INS-02)", "load plane",
          "per S1 block", ["UB-RF-08"], "S1", "REQUIRED"),
        m("P1-M-05", "laboratory generator mains input power (ENGINEERING)", "P_mains,in", "W",
          "power analyzer at the generator mains input", "AC mains input of the laboratory generator "
          "(GROUND/FACILITY_ONLY)", SAMP, ["TBD - requires the power-analyzer calibration certificate"],
          "S1-S8", "REQUIRED",
          "never P_bus, never evidence for P_bus < 1.5 kW (A9.3 OQ-RFQ-06)"),
        m("P1-M-06", "RF frequency and harmonic content", "f_RF, harmonics", "MHz, dBc", "frequency counter / "
          "spectrum analyzer", "generator output into the matched load", "per S1 block", ["UB-RF-00", "UB-RF-06"],
          "S1", "REQUIRED"),
        m("P1-M-07", "antenna RF current", "I_ant", "A", "high-frequency current sensor (analog method TK-24)",
          "antenna feed on the module side of the local match", SAMP, ["TBD - requires sensor certificate"],
          "S2-S5", "PROPOSED"),
        m("P1-M-08", "ICP antenna impedance / load reflection", "Z_ICP = R + jX, Gamma_L", "ohm, -",
          "VNA (cold) and in-situ V/I (plasma) - " + PENDING_P2, "antenna feed (de-embedded)",
          "per P1-S2 cold map; plasma points when the P2 chain exists", ["A9H-INS-03", PENDING_P2], "S2-S5",
          "PENDING (P2 chain)"),
        m("P1-M-09", "local-match setting", "match_setting_id (capacitor positions)", "-", "match controller / "
          "position readback", "local match", "per setpoint", ["-"], "S2-S7", "REQUIRED"),
        m("P1-M-10", "collector bias voltage", "V_collector", "V", "floating-rated divider (A9H-INS-04)",
          "ICP ion-collecting electrode vs the reference registered with the extraction topology (P1-IT-36)", SAMP,
          ["UB-N-02", "UB-N-03"], "S4-S7", "REQUIRED"),
        m("P1-M-11", "extracted electron current (collector current)", "I_e", "A", "floating-rated current channel "
          "(A9H-INS-04), range to the 8.33 A stand ceiling", "ICP ion-collecting electrode supply lead (the loop "
          "closes through the registered electron-collecting electrode, P1-IT-36)", SAMP,
          ["UB-N-01", "UB-N-03"], "S4-S7", "REQUIRED"),
        m("P1-M-12", "ICP body floating potential and body current", "V_body, I_body", "V, A",
          "floating-rated divider / current channel", "ICP body (ICD ICP-20)", SAMP, ["UB-N-02", "UB-N-03"],
          "S3-S7", "REQUIRED", "I_body is 0 by construction when the body is open-circuit (declared per record); "
          "V_icp_body is monitored in every ICP45_CAPACITY record (A9.4 P1Q-13)"),
        m("P1-M-13", "facility / chamber ground-return current", "I_gnd", "A", "ground-return monitor (A9H-INS-05)",
          "isolated-network common to facility ground", SAMP, ["UB-N-04"], "S3-S7", "REQUIRED",
          "chamber / facility return current where measurable (A9.4 P1Q-13); distinct from the H-1 body return "
          "P1-M-29"),
        m("P1-M-14", "Hall discharge voltage and current", "V_d(t), I_d(t)", "V, A",
          "DC + time-resolved channels (INS-04; A9H-INS-10)", "V_d = V_anode - V_electron-source-reference "
          "(A9.1 A9-03-Vd); supply terminals and loop drops secondary", "TBD - frozen before P1-S6 (UB-I-01 "
          "exploratory band as reference)", ["UB-I-02", "UB-I-03", "UB-I-04"], "S6, S6D, S7", "REQUIRED"),
        m("P1-M-15", "anode and electron-source-reference potentials to ground", "V_anode, V_ref", "V",
          "floating-rated dividers (A9H-INS-10)", "to facility ground", "as P1-M-14 in S6/S6D/S7; " + SAMP +
          " in S3-S5", ["UB-N-02"], "S3-S7", "REQUIRED",
          "V_anode recorded also with the discharge supply OFF on a high-impedance isolated channel (anode "
          "physically disconnected and floating; metered return only in a registered DIAGNOSTIC_VARIANT; A9.4 P1Q-13, "
          "P1-IT-39); V_ref from P1-S6 on"),
        m("P1-M-16", "chamber pressure", "p_chamber", "Pa", "ion gauge, Ar-calibrated (UBQ-08)",
          "H2-6 H26-30 placement rule (UB-B-05)", "UB-B-05 rule", ["UB-B-03", "UB-B-04", "UB-B-05"], "S2-S7",
          "REQUIRED"),
        m("P1-M-17", "ICP source pressure (if the port exists)", "p_ICP", "Pa", "gauge on the ICD ICP-27 port",
          "Hall-exhaust-to-ICP interface (ICP-27, TBD)", SAMP, ["UB-B-03"], "S3-S7", "PROPOSED",
          "ICP-27 geometry TBD (after-evidence)"),
        m("P1-M-18", "Ar flow through the H-1 gas path", "mdot_Ar,H1", "mg/s (sccm recorded)",
          "thermal own-gas-calibrated Ar MFC, 1 or 2 ranges (A9.3 OQ-RFQ-02)", "H-1 gas inlet",
          SAMP, ["UB-F-00", "UB-F-06", "UB-F-07", "UB-F-08", "UB-F-09", "A9H-CAL-04"], "S3-S7", "REQUIRED",
          "verified by the rate-of-rise / transfer path"),
        m("P1-M-19", "dedicated ICP flow", "mdot_ICP,dedicated", "mg/s", "optional controller (quote option)",
          "capped ICP gas port", SAMP, ["UB-F-12"], "diagnostic branch only", "CONDITIONAL",
          "0 in G-REUSE; measured and ledger-booked only in the DIAGNOSTIC_DEDICATED_FEED branch"),
        m("P1-M-20", "residual gas composition", "RGA spectrum", "Pa (partial)", "RGA ~200 amu, differential "
          "pumping (A9H-INS-07)", "chamber", "per block", ["UB-B-02"], "S2-S7", "REQUIRED"),
        m("P1-M-21", "temperatures", "T_icp_dielectric, T_antenna, T_collector, T_match, T_rf_source, "
          "T_h1_pole_inner, T_h1_pole_outer, T_sink", "degC", "thermocouples / RTDs (INS-17); sink sensors "
          "(A9H-INS-08)", "per node", SAMP, ["UB-K-02", "UB-K-01"], "S1-S8", "REQUIRED",
          "recorded only: ICP_COUPLED_THERMAL = UNRESOLVED; never a thermal PASS"),
        m("P1-M-22", "RF pickup check", "channel offsets RF-on / plasma-off", "V, A", "all floating and Hall "
          "channels", "per channel", "per configuration", ["UB-N-03"], "S2, S6", "REQUIRED",
          "owner row 64; ICD ICP-17"),
        m("P1-M-23", "ignition / extinction events", "attempts, successes, delay, extinctions", "count, s",
          "event logger (INS-10)", "-", "per attempt", ["-"], "S3-S7", "REQUIRED", "owner row 24"),
        m("P1-M-24", "H-1 magnet coil currents (when energized)", "I_coil,inner/outer/trim", "A",
          "coil-current channels", "magnet supplies", SAMP, ["UB-Z-03"], "S3-S7", "CONDITIONAL"),
        m("P1-M-25", "interlock state and trip events", "interlock log", "-", "RF source / PLC log",
          "-", "event", ["-"], "S0-S8", "REQUIRED"),
        m("P1-M-26", "common time base", "t", "s", "DAQ (INS-18)", "-", "all channels", ["-"], "S0-S8", "REQUIRED"),
        m("P1-M-27", "electron-collecting electrode current and potential (P1-S4 topology A)",
          "I_ecoll, V_ecoll", "A, V", "floating-rated current channel and divider (A9H-INS-04 class)",
          "dedicated electron-collecting target lead (terminal 'electron_collector')", SAMP,
          ["UB-N-01", "UB-N-02", "UB-N-03"], "S4, S5, S7", "REQUIRED (ICP45_CAPACITY records; A9.4 P1Q-10)",
          "the dedicated electron-collector current is the capacity measurand (I_e,cap = I_e,collector,RFON - "
          "I_e,collector,RFOFF, A9.4 P1Q-10); required in every ICP45_CAPACITY record; for non-capacity surface records "
          "with the chamber-wall topology the sink current is P1-M-13"),
        m("P1-M-28", "optical-emission photodiode intensity (ignition / unlit indicator)", "S_PD", "V",
          "photodiode + amplifier on a DAQ channel (INS-P2-10; A9.4 P2Q-05), line of sight to the ICP source volume "
          "through the optical access", "photodiode output at the DAQ input (gain setting recorded)", SAMP,
          ["TBD - requires the photodiode / amplifier datasheets (dark offset, linear range, saturation)"], "S2-S7H",
          "REQUIRED (A9.4 P2Q-05)",
          "records dark/background (S2), RF-powered known-unlit (S2) and known-lit (S3-S5) data from which the P2 "
          "threshold is frozen before the P2 map; loss of line of sight or saturation flagged per sample and never "
          "used as unlit evidence; recorded simultaneously with P_refl, antenna current, collector/current-path "
          "response and pressure; no numeric threshold is set in P1"),
        m("P1-M-29", "H-1 body / magnetic-circuit to facility-ground current (single metered return)",
          "I_body->ground", "A", "ground-current monitor in the only deliberate H-1 body ground path (A9H-INS-05 "
          "class)", "H-1 body -> ground-current monitor -> facility ground (terminal h1_body)", "continuous during "
          "every ICP45_CAPACITY record (A9.4 P1Q-13); " + SAMP, ["UB-N-04"], "S3-S7H", "REQUIRED (A9.4 P1Q-13)",
          "missing in a capacity record -> the reducer refuses the record; enters the Kirchhoff closure P1-D-13"),
    ]


def derived():
    return [
        {"id": "P1-D-01", "quantity": "|Gamma|", "formula": "sqrt(P_RF,refl / P_RF,fwd)", "plane": "coupler plane",
         "source": A92 + " OQ-A907-11"},
        {"id": "P1-D-02", "quantity": "VSWR", "formula": "(1 + |Gamma|) / (1 - |Gamma|)", "plane": "coupler plane",
         "source": A92 + " OQ-A907-11"},
        {"id": "P1-D-03", "quantity": "P_RF,delivered", "formula": "P_fwd - P_refl - P_line/match,loss (loss MEASURED); "
         "UPPER_BOUND P_fwd - P_refl when the loss is FLAGGED_NOT_MEASURED", "plane": "antenna feed",
         "source": A92 + " OQ-A907-11 (never P_fwd = P_plasma)"},
        {"id": "P1-D-04", "quantity": "C_e", "formula": "P_RF,delivered / I_e", "boundary_label": "RF delivered "
         "(generator / 50-ohm side minus measured line/match loss)", "source": A93 + " OQ-RFQ-06"},
        {"id": "P1-D-05", "quantity": "C_e,DC", "formula": "P_generator,input / I_e", "boundary_label": "P_mains,in "
         "of the laboratory generator (GROUND/FACILITY_ONLY; not P_bus)", "source": A93 + " OQ-RFQ-06"},
        {"id": "P1-D-06", "quantity": "current-path closure residual", "formula": "sum of signed terminal currents / "
         "max |terminal current| over {collector_supply, icp_body, facility_ground, hall_anode (, "
         "electron_collector, h1_body)}; hall_anode is in every closure (metered or OPEN_CIRCUIT_BY_CONSTRUCTION, "
         "P1-IT-39); h1_body (I_body->ground) in every ICP45_CAPACITY record (A9.4 P1Q-13)",
         "source": "this lane (form); " + UB + " UB-N-07 (PROPOSED diagnostic)"},
        {"id": "P1-D-07", "quantity": "facility-electron fraction and corrected ICP current", "formula": "I_e(RF OFF) "
         "/ I_e(RF ON) and I_e(RF ON) - I_e(RF OFF) at the same V_collector and reference, mdot_Ar,H1, "
         "mdot_ICP,dedicated, gas mode, Hall discharge-supply state, stage, extraction topology, H-1 point and "
         "H-1 electrical configuration, with p_chamber within the P1-IT-37 tolerance", "source": "this lane (A9.3 authorization: current-path verification)"},
        {"id": "P1-D-08", "quantity": "dwell drift and mode-jump indicators", "formula": "linear-fit drift over the "
         "dwell / mean; max consecutive step / sample std", "source": "this lane (P1Q-01 form)"},
        {"id": "P1-D-09", "quantity": "ignition success fraction", "formula": "successes / attempts",
         "source": ANS + " row 24"},
        {"id": "P1-D-10", "quantity": "M_n lower bound (ICP-45A, only after registration)",
         "formula": "M_n = I_e,cap / I_d,max,H1 - 1; lower = M_n - k_one_sided u(M_n); I_e,cap = "
                    "I_e,collector,RFON - I_e,collector,RFOFF per P1-IT-38 (OWNER_DECIDED, A9.4 P1Q-10): "
                    "ICP45_CAPACITY records only, never NEUTRALIZATION_CONSISTENCY (Hall-ON) records; status exactly "
                    "NOT_EVALUATED until I_d,max,H1 is registered",
         "source": A91 + " UBQ-02, UBQ-07, ICP-45; " + A93 + " OQ-A907-02; " + A94 + " decisions.P1Q-10, "
                   "execution_decisions.i_d_max_h1"},
        {"id": "P1-D-12", "quantity": "Hall-on neutralization consistency (descriptive; label "
         "NEUTRALIZATION_CONSISTENCY)", "formula": "ICP-supplied current (facility-corrected where an RF-OFF pair "
         "exists) vs |I_hall_anode| at the same P1-S7H Hall-ON record; ratio, sustainment, closure residual, "
         "collector / reference potentials and RF power reported; never a gate, never ICP45_CAPACITY and never "
         "I_e,cap", "source": A94 + " decisions.P1Q-10.hall_on, hall_on_follow_up"},
        {"id": "P1-D-13", "quantity": "capacity-point closure validity", "formula": "|P1-D-06 residual| of the RF-ON "
         "ICP45_CAPACITY record and of its matched RF-OFF record <= the registered tolerance P1-IT-47 (terms "
         "collector, body, anode, facility where measurable, ICP body under the registered sign convention); "
         "otherwise the capacity point is invalid; no tolerance registered -> no capacity point admitted",
         "source": A94 + " decisions.P1Q-13.closure"},
        {"id": "P1-D-11", "quantity": "I_e surface", "formula": "table of I_e against (P_RF, p, mdot, Z_ICP, "
         "V_collector)", "source": A93 + " OQ-A907-02"},
    ]


def safety():
    return [
        {"id": "P1-SI-01", "hazard": "RF mismatch / reflected power", "function": "reflected-power monitoring, "
         "mismatch/VSWR interlock, automatic RF reduction/shutdown", "threshold": "TBD - frozen after the P1-S2 "
         "antenna/load characterization (A9.2); PROVISIONAL generator settings recorded before that",
         "source": A92 + " rf_protection", "status": "OWNER_GIVEN (function) / TBD (threshold)"},
        {"id": "P1-SI-02", "hazard": "RF arcing (antenna, match, feedthrough, coax)", "function": "arc detection "
         "where feasible; shutdown", "threshold": "TBD - requires the procured generator/match capability",
         "source": A92 + " rf_protection; ICD ICP-44 (Paschen rating TBD)", "status": "OWNER_GIVEN (where feasible)"},
        {"id": "P1-SI-03", "hazard": "RF component overheating (match, antenna, collector, generator)",
         "function": "thermal monitoring with automatic RF reduction/shutdown", "threshold": "TBD - requires "
         "validated continuous-use limits (UBQ-06 rule limit - 50 K; P1Q-04)", "source": A92 + " rf_protection; "
         + A91 + " UBQ-06", "status": "TBD"},
        {"id": "P1-SI-04", "hazard": "personnel RF exposure / RF leakage", "function": "shielded antenna and "
         "enclosure, leakage survey before first power", "threshold": "TBD - requires the applicable RF-exposure "
         "rule of the facility (verify)", "source": "facility safety owner", "status": "TBD"},
        {"id": "P1-SI-05", "hazard": "HV between floating circuits and ground (collector, ICP body, Hall anode)",
         "function": "isolation per ICD ICP-23: 350 V operating class of owner row 81 for H-1 / discharge supply / "
         "isolation / diagnostics, extended by A9.4 P1Q-14 to the ICP body / collector circuits (vs Hall anode, H-1 "
         "body/common, facility ground, other isolated circuits); V_design,withstand >= 525 V; initial DWV 1.05 kV DC "
         "for 60 s on passive insulation paths and feedthrough assemblies where ratings permit, current-limited, "
         "sensitive electronics disconnected where necessary, leakage recorded, before first HV/RF operation, plus "
         "representative-pressure/gas testing for Paschen-risk paths; current-limited supplies; discharge-supply "
         "protection sized to the 8.33 A stand ceiling",
         "threshold": "350 V operating; >= 525 V design withstand; 1.05 kV DC / 60 s initial DWV (A9.4 P1Q-14); "
                      "leakage acceptance TBD; later reverification level TBD (P1-IT-45)",
         "source": "ICD ICP-23; " + ANS + " row 81; " + A94 + " decisions.P1Q-14; " + A93 + " OQ-A907-02",
         "status": "OWNER_DECIDED (A9.4 P1Q-14); ICP-44 RF insulation OPEN"},
        {"id": "P1-SI-06", "hazard": "gas line bridging isolated potentials", "function": "~1 kV DC representative "
         "gas/pressure qualification (flashover, leakage, breakdown, surface tracking, repeated exposure where "
         "appropriate) ONLY where the line bridges isolated potentials; no isolator where both ends are held at "
         "the same floating potential", "threshold": "~1 kV DC", "source": A93 + " ICPQ-06",
         "status": "OWNER_GIVEN"},
        {"id": "P1-SI-07", "hazard": "Ar release in the laboratory", "function": "facility gas-safety procedure "
         "(oxygen-deficiency assessment)", "threshold": "TBD - requires the facility safety owner", "source":
         "facility safety owner", "status": "TBD"},
        {"id": "P1-SI-08", "hazard": "vacuum loss / pressure out of range during RF or HV", "function": "RF and HV "
         "enable interlocked on chamber pressure", "threshold": "TBD - requires facility rules and the Paschen "
         "assessment of ICP-44", "source": "ICD ICP-44", "status": "TBD"},
        {"id": "P1-SI-09", "hazard": "thermal (H-1 poles, ICP, collector)", "function": "record and abort on "
         "component limits", "threshold": "TBD (P1-IT-25)", "source": A92 + " icp_coupled_thermal",
         "status": "ICP_COUPLED_THERMAL = UNRESOLVED; never report an ICP thermal PASS"},
        {"id": "P1-SI-10", "hazard": "unexpected Hall discharge in P1-S6 (ICP OFF)", "function": "discharge "
         "supply inside registered start limits with current limit; P1-S6D diagnosis", "threshold": "TBD "
         "(P1-IT-31)", "source": A93 + " OQ-VI-05", "status": "TBD"},
        {"id": "P1-SI-11", "hazard": "dielectric-withstand (hipot) testing itself: personnel HV exposure and "
         "insulation ageing by repeated proof stress", "function": "current-limited tester; sensitive electronics "
         "disconnected where necessary; the 1.05 kV DC / 60 s test is qualification-style and not repeated before "
         "each campaign; later reverification at a lower controlled level / procedure unless a fault or hardware "
         "modification requires requalification", "threshold": "1.05 kV DC / 60 s initial (A9.4 P1Q-14); "
         "reverification level TBD (P1-IT-45)", "source": A94 + " decisions.P1Q-14.initial_dwv, no_repeated_hipot",
         "status": "OWNER_DECIDED (rule) / TBD (reverification level)"},
    ]


def run_matrix(ar):
    return {
        "factors": [
            {"id": "F1", "name": "RF forward power setpoint P_RF,fwd", "units": "W", "levels": "TBD - frozen at P1-G2 "
             "inside the 0-500 W investigation capability (row 72; not a rating) and the procured ratings "
             "(TBD_AFTER_IMPEDANCE_MAP); PROPOSED: include 200 W forward as a topology-reproduction level (TK-21)"},
            {"id": "F2", "name": "Ar flow through the H-1 gas path mdot_Ar,H1", "units": "mg/s (sccm)",
             "levels": "anchor 70 sccm ~ 2.1 mg/s (owner-stated, TK-31; check %s mg/s); levels above and below: TBD "
                       "- frozen at P1-G0 from the MFC range and refined from the P1-S3 ignition map (A9.3 "
                       "OQ-RFQ-02: 'sweep sufficiently above/below')" % ar["ar_anchor_check_mg_s"]["value"]},
            {"id": "F3", "name": "pressure p (chamber; ICP port if present)", "units": "Pa", "levels": "covariate "
             "(set by F2 and the facility pumping), recorded, never adjusted to match TK-34"},
            {"id": "F4", "name": "collector bias V_collector", "units": "V", "levels": "sweep at every (F1, F2) point; "
             "range TBD (P1-IT-18); step TBD (UB-N-05)"},
            {"id": "F5", "name": "impedance / match state Z_ICP", "units": "ohm", "levels": "match re-tuned per "
             "setpoint to minimum reflection (TK-23 practice; A9.2 adjustable local match); Z recorded when the P2 "
             "chain exists (" + PENDING_P2 + ")"},
            {"id": "F6", "name": "H-1 magnet state", "units": "A (coil currents)", "levels": "PROPOSED {OFF, "
             "registered H-1 setting(s)} (P1Q-06)"},
            {"id": "F7", "name": "ICP gas mode", "units": "-", "levels": "G-REUSE (baseline); "
             "DIAGNOSTIC_DEDICATED_FEED only as a declared diagnostic branch, booked (A9.3 OQ-RFQ-10)"},
            {"id": "F8", "name": "Hall discharge-supply state (P1-IT-40)", "units": "-", "levels": "OFF in "
             "P1-S3..S5 and the P1-S7 capacity block (supply physically disconnected, A9.4 P1Q-13); ON only in P1-S6, "
             "P1-S6D and the P1-S7H Hall-ON follow-up (NEUTRALIZATION_CONSISTENCY); sustainment recorded "
             "separately"},
        ],
        "ordering_rule": ["first exposure: monotone ascending ramps in P_RF and in collector-current limit with hold "
                          "points (safety-ordered; never randomized)",
                          "after the envelope is established: replicate points re-run in randomized order from a "
                          "recorded seed and generation procedure (PROPOSED; analog of owner row 30 without its "
                          "LOCK-2 timing because P1 is non-scoring)",
                          "every record carries ENGINEERING_ONLY_NON_SCORING"],
        "repeats": "PROPOSED (owner call, P1Q-05): at least three independent re-ignitions per surface point used for "
                   "the P2 handoff (analogy only to A9.1 HIQ-02 'three complete engineering replicates')",
        "not_a_prediction": "levels are test settings, not predicted operating points (owner row 146: no manufactured "
                            "screening values)",
    }


def readiness():
    fam = {
        "RF": [("13.56 MHz laboratory generator (mains, GROUND/FACILITY_ONLY)", "RFQ-04", "A9H-INS-01; H3-A902-01"),
               ("directional coupler + forward/reflected sensors", "RFQ-04", "A9H-INS-01, A9H-INS-16"),
               ("adjustable LOCAL matching network on / adjacent to the ICP module", "RFQ-04",
                "A9H-RF-LM-01; ICD ICP-13"),
               ("50-ohm RF coax and vacuum RF feedthrough", "RFQ-04", "A9H-INS-15; ICD ICP-15"),
               ("dummy load + calorimetric cross-check load", "RFQ-04", "A9H-INS-02"),
               ("RF protection / interlocks", "RFQ-04", "A9H-RF-PROT-01; ICD ICP-16"),
               ("VNA / two-port characterization set", "RFQ-04", "A9H-INS-03; " + PENDING_P2),
               ("power analyzer for P_mains,in", "RFQ-04 (RFQ-04-R04 asks the supplier to allow input-power metering; the analyzer itself is not a v1 line)", "A9.3 OQ-RFQ-06")],
        "gas_metrology": [("Ar thermal MFC, 1 range (2 only if needed)", "RFQ-02", "A9H-CAL-04; H2-3 gas path"),
                          ("rate-of-rise / transfer calibration volume", "RFQ-02 / RFQ-09", "UB-F-07"),
                          ("Ar-calibrated pressure gauges", "RFQ-03 / RFQ-09", "UB-B-03; H26-30 placement"),
                          ("gas isolators where a line bridges potentials (~1 kV DC qualification)", "RFQ-02",
                           "ICPQ-06; H2-3 REV-64"),
                          ("optional dedicated ICP feed controller (quote option only)", "RFQ-02 option line",
                           "A9.3 OQ-RFQ-10"),
                          ("capped ICP gas port", "RFQ-05", "ICD ICP-26"),
                          ("H-1 Ar gas path and anode plenum/distributor delivering the G-REUSE flow (needed from "
                           "P1-S3 on)", "none (H2-3 / H2-1 design item; the MFC itself is RFQ-02)",
                           "H2-3 gas path / plenum; H2-1 CI H-1; IF-P1-14")],
        "vacuum_facility": [("vacuum chamber (smaller domestic chamber allowed for S0-S5)", "RFQ-09 (information)",
                             "owner row 139"),
                            ("pumping for the Ar anchor flow", "RFQ-09 (information)", "TK-31/TK-34 context"),
                            ("electrical, RF and gas feedthroughs", "RFQ-04 / RFQ-09", "ICD ICP-15"),
                            ("RGA ~200 amu with differential pumping", "RFQ-03", "A9H-INS-07"),
                            ("optical access / window with line of sight to the ICP source volume for the photodiode "
                             "(A9.4 P2Q-05)", "none in RFQ v1", "INS-P2-10; P1-M-28"),
                            ("ICP pressure port (if provided)", "RFQ-05", "ICD ICP-27")],
        "hall_electrical": [("H-1 Hall thruster with its magnet circuit (needed from P1-S3 as the G-REUSE gas path and "
                             "for magnet factor F6; Hall-on in P1-S6/S6D/S7)", "none (H-1 is the H2-1 design item, "
                             "not an RFQ v1 package)", "H2-1 CI H-1, MC-1; IF-P1-14"),
                            ("laboratory discharge supply (ground only), conductors, sensors and protection sized to "
                             "the 8.33 A stand ceiling", "RFQ-06 part (b) laboratory discharge supply (ground only); "
                             "NOT part (a) flight-representative breadboard supply", "H2-4 H24-27, H3-PPU-01; "
                             "A9.3 OQ-A907-02"),
                            ("H-1 anode physical disconnect means (discharge-supply output disconnected in Hall-OFF "
                             "stages) and high-impedance isolated V_anode channel; metered anode return only for a "
                             "registered DIAGNOSTIC_VARIANT (A9.4 P1Q-13; P1-IT-39)", "none explicit in RFQ v1 "
                             "(closest: RFQ-06 part (d) synchronized V/I channel pairs)", "P1-IT-39; P1-M-15; "
                             "A9H-INS-10"),
                            ("magnet supplies (per coil)", "none as a v1 quotation line (A9-02 bus slots "
                             "hall_magnet_inner/outer/trim only)", "A9-02 A902-31; H2-1 MC-1"),
                            ("floating collector / bias supply with V/I metering", "RFQ-05", "A9H-INS-04; A902-23"),
                            ("P1-S4 electron-collecting electrode circuit: return lead, current channel and bias "
                             "reference per the registered topology (P1-IT-36)", "none explicit in RFQ v1 (RFQ-05 "
                             "covers the ICP collector/bias supply only)", "P1-IT-36; P1-M-27; ICD ICP-21"),
                            ("ground-return current monitors: H-1 body single-point metered facility-ground return "
                             "(I_body->ground, continuous) and chamber / facility return where measurable (A9.4 "
                             "P1Q-13)", "none explicit in RFQ v1 (closest: RFQ-06 part (d) synchronized V/I channel "
                             "pairs)", "A9H-INS-05; P1-M-13; P1-M-29"),
                            ("isolation of floating circuits (350 V class, row 81, extended to the ICP body / "
                             "collector by A9.4 P1Q-14; V_design,withstand >= 525 V; initial DWV 1.05 kV DC / 60 s)",
                             "RFQ-05 / RFQ-06", "ICD ICP-23; H2-6 REV-36; P1-IT-43 / P1-IT-44"),
                            ("current-limited DC dielectric-withstand tester >= 1.05 kV with leakage read-out (initial "
                             "DWV, A9.4 P1Q-14)", "none in RFQ v1 (owner question P1Q-17 covers the reverification "
                             "level only)", "P1-IT-44; P1-SI-11"),
                            ("V_d reference-potential channels", "closest: RFQ-06 part (d) synchronized V/I channel "
                             "pairs", "A9H-INS-10"),
                            ("C1 (hall_c1_reference) with heater / keeper supplies: present on its own module but "
                             "DISCONNECTED and verified not supplying electrons in P1-S6 (OQ-VI-05 step 2); "
                             "disconnect means and its verification record", "RFQ-08", "H2-2 C-1; ICD ICP-25, "
                             "ICP-46; A9.1 ICP-46 (keeper isolation basis)")],
        "mechanical_icp_fabrication": [("open-tube coaxial dielectric tube", "RFQ-05", "ICD ICP-04, ICP-07; TK-10"),
                                       ("RF antenna / coil (unmagnetized)", "RFQ-05", "ICD ICP-19, ICP-32"),
                                       ("collector (316L allowed for Ar)", "RFQ-05", "ICD ICP-21; A9-03-collector"),
                                       ("P1-S4 dedicated electron-collecting target (if topology A is registered): "
                                        "isolated plate, support, position datum and feedthrough", "none (not in "
                                        "RFQ v1; geometry TBD at P1-G0, P1-IT-36)", "P1-IT-36; P1Q-09"),
                                       ("carrier on KC-1 with orificed-variant provisions", "RFQ-01 / RFQ-05",
                                        "H2-6 REV-30; ICD ICP-06"),
                                       ("machined supports / open-frame mounting (view-factor objective)", "RFQ-05",
                                        "ICD ICP-47; A9H-TH-01")],
        "thrust_metrology": [("DAQ with common time base", "RFQ-06 / RFQ-01", "INS-18"),
                             ("optical-emission photodiode + amplifier + DAQ channel (A9.4 P2Q-05)", "none in RFQ v1",
                              "INS-P2-10; P1-M-28"),
                             ("traceability hardware (certificates for V, I, RF, T, flow)", "RFQ-09", "A9H-CAL-02..04"),
                             ("thrust stand: not required for P1-S0..S6 (no thrust claim); only if P1-S7 is run on "
                              "the stand", "RFQ-01", "A9H-FIX-01")],
    }
    out = []
    n = 0
    for family, rows in fam.items():
        for name, v1, h2 in rows:
            n += 1
            out.append({"id": "P1-HW-%02d" % n, "family": family, "item": name,
                        "rfq_v1_package": v1 + " (" + RFQ1 + "; predates A9.2/A9.3)",
                        "rfq_v2_package": PENDING_RFQ_V2, "h2_or_h1_items": h2, "status": "NOT_PROCURED "
                        "(quotations only; no purchase order; no supplier contact by this lane; A9.4 authorizes the "
                        "owner / procurement to send the P1_NEEDED packages for quotation, not purchase orders, advance "
                        "payments or binding commitments)"})
    return out


def orificed_provisions():
    return [
        "the ICP module attaches only through the IP-NEU datum of the KC-1 carrier (ICD ICP-01, ICP-06; H2-6 REV-30); "
        "no H-1 feature depends on the ICP bore, tube or collector geometry",
        "the capped dedicated ICP gas port and its carrier-side gas feedthrough are retained so a later orificed "
        "variant's dedicated feed can use them (sizing TBD, ICD ICP-26)",
        "RF feed, local match and harness terminate on the module side of IP-NEU so a different antenna/cathode body "
        "can be fitted; the connector/harness interface itself is NOT defined in ICD v1 (ICP-13 fixes the local-match "
        "location, ICP-15 defers connector ratings to the impedance map, ICP-16 names the coax/connector interlock "
        "loop, ICP-33 the MODULE_ID line and ICP-34 the channel list the harness must carry): TBD - requires an ICD "
        "revision (owner question P1Q-12)",
        "the module envelope / keep-out zone (ICD ICP-07, TBD) is reserved generously enough to be re-used by an "
        "ICP_ORIFICED_VARIANT; its value is set at LOCK-1 by the ICD, not by this lane",
        "the axial standoff (ICD ICP-02, TBD) is set by carrier spacers, not by H-1 machining",
        "any orificed variant is a new serialized module with a new reference sequence (owner row 83; ICD ICP-40) "
        "and an A9.x follow-on; it is NOT built in P1 (A9.3 OQ-VI-03)",
    ]


def interface_demands():
    return [
        {"id": "IF-P1-01", "direction": "to", "counterpart": "P2 " + PENDING_P2, "what": "stable ICP operating region "
         "handoff (region bounds in P_fwd, mdot, p, V_collector; match settings; dwell metrics; cold Z)",
         "units": "W, mg/s, Pa, V, ohm", "status": "OFFERED (after P1-S5)"},
        {"id": "IF-P1-02", "direction": "from", "counterpart": "P2 " + PENDING_P2, "what": "V/I sensing, coupler "
         "chain calibration, S-parameter / de-embedding method and data model for the Z_ICP factor",
         "units": "ohm, -", "status": "PENDING (parallel lane; nothing here depends on it at import/test time)"},
        {"id": "IF-P1-03", "direction": "to", "counterpart": "RFQ v2 " + PENDING_RFQ_V2, "what": "P1 readiness items "
         "per A9.3 family (hardware_readiness)", "units": "-", "status": "OFFERED"},
        {"id": "IF-P1-04", "direction": "from", "counterpart": "RFQ v2 " + PENDING_RFQ_V2, "what": "package ids and "
         "quoted datasheet values (ratings, calibration scope)", "units": "-", "status": "PENDING"},
        {"id": "IF-P1-05", "direction": "from", "counterpart": "A9-03 ICD " + ICD, "what": "ICP-02/04/07 geometry, "
         "ICP-13/14 match and plane, ICP-15 ratings, ICP-16 interlock, ICP-17 pickup limits, ICP-19 shielding, "
         "ICP-20/21 body/collector, ICP-26 gas mode/capped port, ICP-27 pressure port, ICP-34 telemetry, ICP-35 start "
         "records, ICP-44 RF voltage rating, ICP-45 form, ICP-47 view-factor objective", "units": "mm, W, V, A",
         "status": "CONSUMED (most values TBD in the ICD)"},
        {"id": "IF-P1-06", "direction": "to", "counterpart": "A9-03 ICD " + ICD, "what": "measured cold antenna "
         "reflection / current (ICP-44, ICP-15 restatement), RF pickup readings (ICP-17), measured temperatures "
         "(ICP-43 partial terms, never PASS), I_e surface (ICP-45 context)", "units": "ohm, A, V, degC",
         "status": "OFFERED (after P1-S2..S5)"},
        {"id": "IF-P1-07", "direction": "from", "counterpart": "A9-04 " + UB, "what": "uncertainty ids UB-RF-00..09, "
         "UB-N-00..07, UB-F-00..12, UB-B-02..05, UB-K-00..02, UB-P-06, UB-I-01..04, UB-Z-03", "units": "per item",
         "status": "CONSUMED"},
        {"id": "IF-P1-08", "direction": "to", "counterpart": "A9-04 " + UB, "what": "P1 Type A repeatability of RF "
         "and collector chains, as ENGINEERING information only (A9.1 HIQ-08: Ar readings never enter LOCK-2 "
         "uncertainty numbers)", "units": "W, A", "status": "OFFERED (engineering-only)"},
        {"id": "IF-P1-09", "direction": "from", "counterpart": "A9-01 " + PRE, "what": "HI-HOLDOUT-A signature, "
         "registered Hall start limits, sustainment definition, I_d,max,H1 registration", "units": "V, A, s",
         "status": "PENDING (owner / prereg lane)"},
        {"id": "IF-P1-10", "direction": "to", "counterpart": "A9-01 " + PRE, "what": "ICP recipe refinements for "
         "LOCK-1 (A9.1 HIQ-08) and ignition/restart records (row 24)", "units": "-", "status": "OFFERED"},
        {"id": "IF-P1-11", "direction": "from", "counterpart": "A9-02 " + BUS, "what": "A902-19 (only the RF-source DC "
         "input crosses the boundary), A902-21 (DC-input efficiency TBD; not measurable with the mains generator), "
         "A902-22 (match draw), A902-23 (collector range)", "units": "W, V, A", "status": "CONSUMED"},
        {"id": "IF-P1-12", "direction": "to", "counterpart": "A9-02 " + BUS, "what": "C_e and C_e,DC tables with "
         "boundary labels; P_mains,in/P_fwd as GROUND/FACILITY_ONLY context (NOT A902-21)", "units": "W/A, -",
         "status": "OFFERED (engineering-only)"},
        {"id": "IF-P1-13", "direction": "from", "counterpart": "H2-4 " + H24, "what": "H24-27 laboratory discharge "
         "supply rating 8.33 A (sizing basis)", "units": "A", "status": "CONSUMED"},
        {"id": "IF-P1-14", "direction": "from", "counterpart": "H-1 (H2-1 " + H21 + "; H2-3 " + H23 + ")",
         "what": "Ar delivery through the H-1 gas path for G-REUSE; IP-EXIT face and KC-1 datum; magnet supplies",
         "units": "mg/s, mm, A", "status": "REQUIRED (H-1 hardware)"},
        {"id": "IF-P1-15", "direction": "from", "counterpart": "A9-07 " + REVS, "what": "A9H-INS-01..05/07/08/10/"
         "14..16, A9H-CAL-02..04, A9H-RF-LM-01, A9H-RF-PROT-01, A9H-TH-01, REV-30 (KC-1), REV-36 (isolation)",
         "units": "-", "status": "CONSUMED"},
        {"id": "IF-P1-16", "direction": "to", "counterpart": "A9-07 / P3 coupled thermal", "what": "measured "
         "temperatures incl. H-1 poles and T_sink per run", "units": "degC", "status": "OFFERED (recorded only; "
         "UNRESOLVED)"},
        {"id": "IF-P1-17", "direction": "to", "counterpart": "A9-08 " + XE_A9, "what": "G-REUSE books "
         "mdot_ICP,dedicated = 0; an activated diagnostic G-XE feed is booked there (A9.3 OQ-RFQ-10)",
         "units": "mg/s", "status": "RULE (no booking in the baseline)"},
        {"id": "IF-P1-18", "direction": "to", "counterpart": "A9-06 " + MASS, "what": "measured mass of the P1 ICP "
         "ground article (context for IDA7-02; not a flight mass)", "units": "kg", "status": "OFFERED"},
        {"id": "IF-P1-19", "direction": "from", "counterpart": "A9-05 " + EVI, "what": "Takahashi anchor values with "
         "locators (anchor_check)", "units": "per item", "status": "CONSUMED (context only)"},
        {"id": "IF-P1-20", "direction": "from", "counterpart": "instrumentation " + INS + " / " + MS, "what": "INS-04, "
         "INS-08, INS-10, INS-11, INS-17, INS-18; MS-G-01..03 for certificate traceability", "units": "-",
         "status": "CONSUMED"},
        {"id": "IF-P1-21", "direction": "from", "counterpart": "H2-2 " + H22 + " / RFQ-08", "what": "C1 (C-1) module "
         "installed on KC-1 with a disconnect means and a verification that it supplies no electrons in P1-S6 "
         "(OQ-VI-05 step 2)", "units": "-, A", "status": "REQUIRED (C1 stays CONTROL_FALLBACK)"},
        {"id": "IF-P1-22", "direction": "to", "counterpart": "A9-03 ICD " + ICD, "what": "P1-S4 extraction topology "
         "(P1-IT-36) and the interim connector/harness record as inputs to the ICD revision (P1Q-12)",
         "units": "mm, V, A", "status": "OFFERED (after P1-G0)"},
        {"id": "IF-P1-23", "direction": "to", "counterpart": "P2 " + PENDING_P2, "what": "photodiode (INS-P2-10) "
         "dark/background, RF-powered known-unlit and known-lit P1 records with simultaneous P_refl, antenna current, "
         "collector/current-path response and pressure, from which the P2 unlit threshold is frozen before the P2 map "
         "(A9.4 P2Q-05)", "units": "V, W, A, Pa", "status": "OFFERED (P1-S2, P1-S3..S5)"},
        {"id": "IF-P1-24", "direction": "to", "counterpart": "RFQ v2 " + PENDING_RFQ_V2, "what": "A9.4 procurement "
         "items: photodiode, optical access / window, amplifier, DAQ channel (P2Q-05); >= 525 V design withstand and "
         "1.05 kV DC / 60 s initial DWV on the ICP body / collector isolation and feedthrough lines (P1Q-14)",
         "units": "V, s", "status": "OFFERED (A9.4)"},
        {"id": "IF-P1-25", "direction": "from", "counterpart": "H-1 registration (A9-01 " + PRE + ")", "what":
         "I_d,max,H1 from the registered H-1 operating envelope and measured H-1 behaviour (never the 8.33 A supply "
         "rating); ICP45 = NOT_EVALUATED until it exists (A9.4 execution_decisions.i_d_max_h1)", "units": "A",
         "status": "PENDING (owner / prereg lane; P1Q-07)"},
    ]


def owner_answers_applied():
    rows = [
        ("A9", "governing decision", "primary investigation Hall + downstream 13.56 MHz ICP; C1 CONTROL_FALLBACK; "
         "evidence order Ar -> N2 -> O2 (P1 is the Ar step); status kept INVESTIGATION_HYPOTHESIS"),
        ("A9.3 OQ-VI-03", "decision", "first build open-tube coaxial only; orificed-variant provisions listed"),
        ("A9.3 OQ-VI-05", "decision", "P1-S6 seven steps verbatim; classification REQUIRED_ENGINEERING_CONTROL_NON_"
         "SCORING; P1-S6D diagnosis branch"),
        ("A9.3 OQ-A907-02", "decision", "8.33 A = stand ceiling for sizing only; I_e,required = I_d,max,H1; surface "
         "reported; reducer refuses STAND_CEILING / POWER_ENVELOPE_BOUND as registration basis"),
        ("A9.3 ICPQ-06", "decision", "P1-IT-20 / P1-SI-06: ~1 kV DC only where a gas line bridges potentials"),
        ("A9.3 OQ-RFQ-06", "decision", "mains generator GROUND/FACILITY_ONLY; P_mains,in engineering; C_e and C_e,DC "
         "with boundary labels; reducer refuses P_mains,in as P_bus (any field name reading as P_bus) and refuses "
         "FLIGHT_REPRESENTATIVE_DC_RF_SOURCE records (later programme)"),
        ("A9.3 OQ-RFQ-07", "decision", "readiness mapped to the six package families; RFQ v2 PENDING; no supplier "
         "contact, no PO"),
        ("A9.3 OQ-RFQ-02", "decision", "Ar MFC 1 (or 2) ranges; rate-of-rise/transfer verification; anchor 70 sccm "
         "~ 2.1 mg/s confirmed against TK-31"),
        ("A9.3 OQ-RFQ-10", "decision", "G-REUSE, capped port retained; dedicated feed diagnostic only, labelled and "
         "booked (reducer refuses otherwise)"),
        ("A9.3 authorizations.P1/P2", "decision", "P1 launched; P2 prep in parallel; P2 map only after the P1 "
         "stable region (P1-G5)"),
        ("A9.2 OQ-A907-11", "decision", "local adjustable match; P_fwd/P_refl on the 50-ohm side; P_delivered with "
         "loss; never P_fwd = P_plasma"),
        ("A9.2 rf_500W", "decision", "0-500 W is investigation capability, not a rating"),
        ("A9.2 rf_protection", "decision", "protection list; thresholds frozen at P1-G2 after characterization"),
        ("A9.2 icp_matching_strategy", "decision", "adjustable local match for the development article"),
        ("A9.2 icp_coupled_thermal / a9_10_statuses", "decision", "ICP_COUPLED_THERMAL UNRESOLVED; the ten statuses "
         "carried unchanged; nothing converted to PASS"),
        ("A9.1 HIQ-04", "decision", "HI-HOLDOUT-A before P1-S6 (first Hall-on reading)"),
        ("A9.1 HIQ-06 / HIQ-06_accounting", "decision", "G-REUSE, mdot_ICP,dedicated = 0; no double counting"),
        ("A9.1 HIQ-08", "decision", "Ar findings may refine the LOCK-1 ICP recipe; never LOCK-2 numbers"),
        ("A9.1 ICP-45", "decision", "ICP-45A on Ar (engineering) as a capacity (extraction) demonstration, now in the "
         "owner-decided form of A9.4 P1Q-10 (ICP45_CAPACITY records, P1-S4 / P1-S7) at registered H-1 conditions, "
         "conditional on registration; Hall-ON records NEUTRALIZATION_CONSISTENCY only (P1-S7H); ICP-45N remains"),
        ("A9.1 UBQ-02 / UBQ-07", "decision", "M_n form and one-sided alpha for the ICP-45A evaluation only"),
        ("A9.1 UBQ-04", "decision", "k_x = 2 calorimetric cross-check; EXCLUDED_INSTRUMENT on failure"),
        ("A9.1 UBQ-06", "decision", "abort rule form; application to P1 asked (P1Q-04)"),
        ("A9.1 UBQ-08", "decision", "Ar-specific gauge/MFC/RGA calibration for P1"),
        ("A9.1 A9-03-Vd", "decision", "V_d = V_anode - V_electron-source-reference in P1-S6/S7"),
        ("A9.1 A9-03-collector", "decision", "316L permitted for the Ar collector"),
        ("A9.1 OQ-EV-01 / OQ-EV-03", "decision", "no author contact; published values with locators only"),
        ("A9.1 ICP-46", "decision", "NOT APPLICABLE to P1 measurements: it rates the C1 keeper-pulse isolation "
         "(900 V basis, 1.0 kV DC hipot, 600 V pulse test) on the C1 reference module; P1 does not fire C1 (C1 is "
         "disconnected in P1-S6). Carried only as the isolation basis of the C1 module that stays installed "
         "(P1-HW C1 row)"),
        ("A9.1 OQ-A902-01", "decision", "NOT APPLICABLE to P1: the 1 ms P_bus window is defined at the spacecraft-DC "
         "propulsion boundary; P1 has no such boundary (mains laboratory generator, GROUND/FACILITY_ONLY) and never "
         "produces P_bus; the RFQ-06 part (d) chain is not used for any P1 claim"),
        ("row 7", "147 answers", "lawful published sources only"),
        ("row 8", "147 answers", "quotations only, no purchase order"),
        ("row 17 / row 122", "147 answers", "H-1 stays bolted; downstream module on KC-1"),
        ("row 24", "147 answers", "ICP ignition / restart records (P1-M-23)"),
        ("row 36", "147 answers", "Ar engineering-only first; never DRDO atmospheric evidence"),
        ("row 62 / row 130", "147 answers", "ICP harness / telemetry channels in the measurement list"),
        ("row 63", "147 answers", "Hall-exhaust-to-ICP pressure interface recorded (P1-M-17)"),
        ("row 64", "147 answers", "RF pickup and electrical isolation checks (P1-M-22)"),
        ("row 69", "147 answers", "unmagnetized ICP"),
        ("row 70", "147 answers", "floating body, separately biased collector (V_collector factor)"),
        ("row 72", "147 answers", "13.56 MHz; coupler primary, calorimetry cross-check"),
        ("row 83", "147 answers", "orificed variant = new serialized module"),
        ("row 86", "147 answers", "50 K margin rule (abort form)"),
        ("row 81", "147 answers", "350 V isolation class for H-1, the C1 reference, the discharge supply, isolation "
         "and diagnostics; extended to the ICP body / collector circuits by A9.4 P1Q-14 (OWNER_DECIDED; P1-IT-21)"),
        ("row 105", "147 answers", "gas-isolator practice (~1 kV DC representative qualification) behind ICPQ-06"),
        ("row 123", "147 answers", "four ranges NOT applied to Ar (amended by A9.3 OQ-RFQ-02)"),
        ("rows 124 / 126", "147 answers", "thermal own-gas MFC; rate-of-rise as transfer standard"),
        ("row 127", "147 answers", "RGA ~200 amu"),
        ("row 131", "147 answers", "T_sink measured per run"),
        ("row 139", "147 answers", "smaller domestic chamber for engineering-only stages"),
        ("row 140", "147 answers", "named responsible engineer / functional role at P1-G0"),
        ("row 146", "147 answers", "no manufactured screening values: run-matrix levels are TBD/PROPOSED"),
        ("A9.4 P1Q-10", A94 + " decisions.P1Q-10 (OWNER_DECIDED - CAPACITY_EXTRACTION_FORM); verbatim " + A94_MD,
         "ANSWERED: P1-IT-38 OWNER_DECIDED; I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF (recorder reading of the "
         "incomplete verbatim formula, stated in P1-IT-38; confirmation asked in P1Q-16); qualification with the "
         "one-sided lower bound of M_n; reducer record_class ICP45_CAPACITY / NEUTRALIZATION_CONSISTENCY labels; "
         "Hall-ON follow-up stage P1-S7H; P1Q-10 removed from the open list"),
        ("A9.4 P1Q-13", A94 + " decisions.P1Q-13 (OWNER_DECIDED - ANODE_FLOATING / BODY_SINGLE_POINT_METERED_GROUND)",
         "ANSWERED: P1-IT-39 OWNER_DECIDED; the reducer REFUSES capacity records with a METERED_RETURN anode, a "
         "connected supply, no high-impedance V_anode channel or no continuous h1_body ground current; METERED_RETURN "
         "only as DIAGNOSTIC_VARIANT; Kirchhoff closure incl. h1_body with a registered tolerance (P1-IT-47, P1-D-13); "
         "P1-M-29; P1Q-13 removed from the open list"),
        ("A9.4 P1Q-14", A94 + " decisions.P1Q-14 (OWNER_DECIDED - ICP_350V_CLASS / 1.05kV_INITIAL_DWV)",
         "ANSWERED: P1-IT-21 no longer PROPOSED EXTENSION; P1-IT-43 (>= 525 V design withstand), P1-IT-44 (1.05 kV DC "
         "/ 60 s initial DWV), P1-IT-45 (later reverification TBD), P1-IT-46 (ICP-44 RF insulation OPEN); P1-SI-05, "
         "P1-SI-11, P1-S0 exit; the ECSS reference is owner-stated without standard / clause id (verify); ICPQ-06 "
         "gas-line rule P1-IT-20 kept distinct; P1Q-14 removed from the open list"),
        ("A9.4 P2Q-05", A94 + " decisions.P2Q-05 (OWNER_DECIDED - PHOTODIODE_REQUIRED)", "P1 part: photodiode "
         "measurement P1-M-28 (dark/background and RF-powered known-unlit in P1-S2, known-lit in P1-S3..S5) handed to "
         "P2 (IF-P1-23) for the threshold frozen before the P2 map; no numeric threshold set; readiness rows for the "
         "photodiode + amplifier + DAQ channel and the optical access / window"),
        ("A9.4 execution_decisions.i_d_max_h1", A94, "I_d,max,H1 never from 8.33 A (bench design ceiling only, "
         "P1-IT-06); P1-IT-07 / IF-P1-25; the reducer returns exactly NOT_EVALUATED until it is registered; the P1 "
         "capability surface is generated before it is frozen"),
        ("A9.4 execution_decisions.p1_needed_rfqs", A94, "readiness rows: the owner / procurement may send the "
         "P1_NEEDED RFQ packages for quotation (RFQ, clarification, indicative lead time, commercial quotation, "
         "datasheets / certificates); no purchase order, advance payment or binding commitment; no supplier contact "
         "by this lane"),
    ]
    return [{"id": r[0], "kind": r[1], "how_applied": r[2]} for r in rows]


def open_questions():
    return [
        {"id": "P1Q-01", "question": "Freeze the 'stable ICP operating region' criteria for the P1 -> P2 handoff: "
         "minimum dwell duration, maximum relative drift of I_e and P_refl (and Z where measured) over the dwell, "
         "maximum step/std (mode jump), minimum ignition success fraction?", "proposed_answer": "owner call on the "
         "values; PROPOSED form as implemented by p1_reducer.classify_stable_region; values set after the first "
         "P1-S5 dwells are seen, before the P2 map", "needed_by": "P1-G5"},
        {"id": "P1Q-02", "question": "Register the Hall start-attempt limits for OQ-VI-05 step 4 (maximum applied "
         "V_d, supply current limit, maximum attempt duration, number of attempts)?", "proposed_answer": "owner call; "
         "PROPOSED: inside the H2-4 laboratory supply rating (current limit not above the 8.33 A stand ceiling) with "
         "values registered before P1-S6", "needed_by": "P1-S6 entry"},
        {"id": "P1Q-03", "question": "Register the definition of a 'sustained Hall discharge' used in OQ-VI-05 steps "
         "5 and 7 (current level above the recorded noise floor and minimum duration)?", "proposed_answer": "owner "
         "call; PROPOSED form: I_d above the RF-on/plasma-off pickup floor of P1-M-22 for a registered minimum "
         "duration", "needed_by": "P1-S6 entry"},
        {"id": "P1Q-04", "question": "Apply the A9.1 UBQ-06 abort rule (validated continuous-use limit - 50 K) also "
         "to the non-scoring P1 operation?", "proposed_answer": "YES (protects the development hardware; costs no "
         "evidence)", "needed_by": "P1-G0"},
        {"id": "P1Q-05", "question": "Minimum number of independent re-ignitions per surface point used for the P2 "
         "handoff?", "proposed_answer": "owner call; PROPOSED at least 3 (analogy to HIQ-02 only)", "needed_by": "P1-S5"},
        {"id": "P1Q-06", "question": "H-1 magnet state during the ICP-only stages P1-S3..S5: OFF only, or OFF plus "
         "the registered H-1 setting(s) (the fringe field in the ICP volume is not yet known, IDA7-17)?",
         "proposed_answer": "both, as factor F6", "needed_by": "P1-S3"},
        {"id": "P1Q-07", "question": "Which campaign produces the registered I_d,max,H1 (A9.3 OQ-A907-02) - H-1 with "
         "C1 (hall_c1_reference) in HI-AR, or another registered H-1 operation - and at which gate is it registered?",
         "proposed_answer": "owner call; P1-S7 stays BLOCKED (surface only) until it exists", "needed_by": "P1-S7 entry"},
        {"id": "P1Q-08", "question": "Do P1-S0..S5 (ICP only, Ar through the H-1 gas path, Hall discharge OFF) belong "
         "to the HI-ENG / HI-S1A module-bench envelope, so that HI-HOLDOUT-A is required only from P1-S6 on?",
         "proposed_answer": "YES (no Hall-on reading occurs before P1-S6; A9.1 HIQ-04 binds the first Hall-on reading)",
         "needed_by": "P1-S3"},
        {"id": "P1Q-09", "question": "A9.4 P1Q-10 fixes the dedicated, isolated, instrumented electron-collecting "
         "electrode (option A) for ICP45_CAPACITY records. Still open: its geometry / position, the V_collector "
         "reference and instrumented terminals (P1-IT-36), and whether option (B), the grounded chamber wall, may "
         "still be used for non-capacity ENGINEERING_SURFACE records in P1-S4?", "proposed_answer":
         "ICP ion collector biased negative w.r.t. the target, V_collector referenced to the target, all terminals "
         "(collector_supply, icp_body, facility_ground, electron_collector, h1_body, hall_anode) metered or declared; "
         "(B) not used (one topology for surface and capacity keeps the records comparable); geometry and position "
         "owner call at P1-G0", "needed_by": "P1-G0"},
        {"id": "P1Q-11", "question": "Pressure-match tolerance for RF-ON / RF-OFF facility-electron pairs "
         "(P1-IT-37)?", "proposed_answer": "owner call; value set from the S2/S3 gauge repeatability before the "
         "first P1-S4 pair", "needed_by": "P1-G0"},
        {"id": "P1Q-12", "question": "Define the ICP module connector / harness interface at IP-NEU in an ICD "
         "revision so an ICP_ORIFICED_VARIANT can reuse it (not an ICD v1 item)?", "proposed_answer": "YES, in the "
         "LOCK-1 module drawings; P1 builds to a documented interim harness", "needed_by": "LOCK-1"},
        {"id": "P1Q-15", "question": "Register the Kirchhoff closure tolerance for ICP-45 capacity points (A9.4 "
         "P1Q-13: 'a large unexplained residual invalidates that capacity point') and the sign convention of the "
         "collector, body, anode, facility and ICP-body terms (P1-IT-47)?", "proposed_answer": "owner call on the "
         "value; PROPOSED: set from the combined channel resolutions measured in P1-S2/S3 before the first "
         "ICP45_CAPACITY record; sign convention = P1-IT-42 (conventional current into the isolated network "
         "positive)", "needed_by": "before the first ICP45_CAPACITY record (P1-G0)"},
        {"id": "P1Q-16", "question": "Confirm the recorder reading of the incomplete A9.4 P1Q-10 'Define:' formula: "
         "I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF (the verbatim text lacks 'I_e,cap =' and the minus "
         "sign)?", "proposed_answer": "YES (consistent with the owner's 'matched RF-OFF measurements used to quantify "
         "facility/background electron current'; implemented as such)", "needed_by": "P1-S7 entry"},
        {"id": "P1Q-17", "question": "Register the later acceptance / reverification level and procedure for the ICP "
         "body / collector insulation (A9.4 P1Q-14: 'an appropriately lower controlled level/procedure'; P1-IT-45)?",
         "proposed_answer": "owner call; PROPOSED: a controlled DC level of about 2 x the 350 V nominal class, per the "
         "owner-stated ECSS guidance quoted in A9.4 (standard and clause not identified - verify), with the procedure "
         "frozen before any reverification", "needed_by": "before any reverification after the initial DWV"},
    ]


def historical_reuse():
    rows = [
        (PRE, "stage ids HI-ENG / HI-S1A / HI-HOLDOUT-A / HI-AR, labels, ICP-45A placement", "comparison stages, "
         "decision quantities (P1 is non-scoring)"),
        (UB, "uncertainty item ids (UB-RF/N/F/B/K/P/I/Z)", "no numbers (TBD there)"),
        (ICD, "ICP-01..47 item ids and statuses", "A9.1 off-platform matching (superseded by A9.2)"),
        (EVI, "Takahashi TK values with locators as anchor context", "never Vyovrinda performance; no scaling"),
        (VIN, "origin of OQ-VI-03 / OQ-VI-05", "validation-input assignments (OQ-A910-02 open)"),
        (RFQ1, "package family names for cross-reference", "four Ar ranges, off-platform match, nine-family split "
         "(superseded by A9.2 / A9.3; v2 " + PENDING_RFQ_V2 + ")"),
        (REVS, "A9H-* instrument items, REV-30 / REV-36", "thermal results (UNRESOLVED)"),
        (H24, "H24-27 8.33 A laboratory rating (sizing)", "flight discharge current values"),
        (BUS, "A902-19/21/22/23 definitions", "no ledger computation"),
        (INS, "INS-04/08/10/11/17/18 ids", "HW-0/RF/ECR arm semantics (historical)"),
        (P1F, "nothing (historical A5 Phase-1 pre-ionizer framework, kept immutable per A9)",
         "all of it: hall_only / rf_hall / ecr_hall topology is superseded (owner row 28)"),
        (PMICD, "nothing (historical upstream pre-ionizer ICD, PMQ-01..05 superseded, rows 61-65)", "all of it"),
    ]
    by = {p: s for p, s, _ in PINS}
    return [{"path": p, "sha256": by[p], "reused": r, "not_reused": n} for p, r, n in rows]


def m16_impact():
    return [
        {"row": 18, "key": "icp_neutralizer_head", "impact": "P1 produces the ICP-45A surface (engineering-only) "
         "named in analysis_test_needed; status stays PENDING_ICP45; no M16 file edit (M16 owner lane)"},
        {"row": 19, "key": "flight_rf_chain", "impact": "P1 uses a GROUND/FACILITY_ONLY mains generator; C_e,DC is "
         "the efficiency input for a later FLIGHT_REPRESENTATIVE_DC_RF_SOURCE; ratings stay TBD_AFTER_IMPEDANCE_MAP"},
        {"row": 15, "key": "sensors_diagnostics", "impact": "P1 measurement list (P1-M-01..27) and derived "
         "quantities; P2 chain PENDING"},
        {"row": 13, "key": "thermal_control", "impact": "temperatures recorded for the P3 coupled model; "
         "ICP_COUPLED_THERMAL stays UNRESOLVED"},
        {"row": 12, "key": "ppu", "impact": "collector/bias supply and stand-ceiling sizing (8.33 A) for ground "
         "hardware only"},
        {"row": 14, "key": "control_fdir", "impact": "RF protection / interlock functions exercised; thresholds "
         "frozen at P1-G2"},
        {"row": 11, "key": "cathode", "impact": "C1 disconnected in P1-S6; stays CONTROL_FALLBACK"},
        {"row": 9, "key": "hall_chamber", "impact": "H-1 Hall-on only in P1-S6/S7 on Ar, engineering-only"},
        {"row": 16, "key": "mechanical_structural", "impact": "KC-1 carrier provisions for a later "
         "ICP_ORIFICED_VARIANT"},
    ]


def h3_h4():
    return {"h3_procurement_inputs": [h["item"] + " [" + h["family"] + "]" for h in readiness()],
            "h4_test_inputs": ["stage map P1-S0..S8 (incl. P1-S7H Hall-ON follow-up) with gates P1-G0, P1-G1, "
                               "P1-G2, P1-G5",
                               "initial DWV 1.05 kV DC / 60 s of passive insulation paths and feedthrough assemblies "
                               "before first HV/RF operation (A9.4 P1Q-14, P1-IT-44)",
                               "photodiode dark/background, RF-powered known-unlit and known-lit records (A9.4 P2Q-05, "
                               "P1-M-28)",
                               "run-matrix structure F1..F8", "record schema " + REL + "/" + OUT_SCHEMA,
                               "reducer " + REL + "/p1_reducer.py"]}


def a9_4_incorporation():
    a94 = _load(A94)
    for q in ("P1Q-10", "P1Q-13", "P1Q-14", "P2Q-05"):
        if q not in a94["decisions"]:
            raise SystemExit("A9.4 decision %s missing" % q)
    return {"follow_on": "fo_a9_4_incorporation", "trigger": "T_A9_4_INCORPORATION", "base_commit": A94_INC_BASE,
            "decision": {"path": A94, "sha256": [x for x in PINS if x[0] == A94][0][1]},
            "verbatim": {"path": A94_MD, "sha256": [x for x in PINS if x[0] == A94_MD][0][1]},
            "rule": "applied mechanically (owner step 2): only what A9.4 decides changed; ids and verified behaviour "
                    "otherwise kept",
            "answered": {q: a94["decisions"][q]["status"] for q in ("P1Q-10", "P1Q-13", "P1Q-14")},
            "p1_part_of": {"P2Q-05": a94["decisions"]["P2Q-05"]["status"]},
            "execution_decisions_applied": ["i_d_max_h1", "p1_needed_rfqs"],
            "recorder_flags_carried": a94["recorder_flags"][:2],
            "m16_impact_change": "none: A9.4 changes no M16 v3 row state (ICP electron-current capacity stays "
                                 "PENDING_ICP45)"}


def a9_2_statuses():
    a92 = _load(A92)
    st = a92["decisions"]["a9_10_statuses"]
    return st


def build_doc():
    red = _reducer()
    ar = arithmetic()
    doc = {
        "schema": "p1_icp_bench_v1",
        "id": "p1_icp_bench_v1",
        "lane": "fo_a9_p1_icp_bench",
        "trigger": "T_A9_P1_ICP_BENCH",
        "status": "ENGINEERING_TEST_PLAN_DRAFT_NOT_SCORE_BEARING",
        "a9_status": "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE (Hall->ICP architecture: "
                     "INVESTIGATION_HYPOTHESIS)",
        "base_commit": BASE_COMMIT,
        "generated_by": REL + "/build_p1_icp_bench.py (--check reproduces all outputs byte-exactly)",
        "companion_document": REL + "/" + OUT_MD,
        "record_schema": REL + "/" + OUT_SCHEMA,
        "reducer": REL + "/p1_reducer.py",
        "test": "tests/test_p1_icp_bench.py",
        "what_it_is_not": ["not a prediction (no Hall closure admitted; abep_sim/plasma_devices.py superseded; "
                           "v1.2-v1.6 numbers withdrawn)", "not a score-bearing campaign (every record "
                           "ENGINEERING_ONLY_NON_SCORING)", "not a verdict on the architecture and never a winner",
                           "not a procurement action (no purchase order, no supplier contact)"],
        "authority_pins": [{"path": p, "sha256": s, "role": w} for p, s, w in PINS],
        "governance_files_not_pinned": GOVERNANCE_NOT_PINNED,
        "a9_4_incorporation": a9_4_incorporation(),
        "pending_parallel_lanes": [{"lane": "fo_a9_p2_impedance_prep", "path": P2_PATH, "state": "PENDING"},
                                   {"lane": "fo_a9_rfq_v2_split", "path": RFQ_V2_PATH, "state": "PENDING"}],
        "scope": {
            "question": "Can a Takahashi-type downstream open-tube coaxial 13.56 MHz ICP supply the electron current "
                        "and neutralization function H-1 needs (i.e. replace C1)?",
            "first_build": "open-tube coaxial downstream ICP only (A9.3 OQ-VI-03); orificed RF plasma cathodes "
                           "(Watanabe / Xu type) are literature comparators only",
            "orificed_variant_provisions": orificed_provisions(),
            "gas_mode": "G-REUSE: Hall exhaust -> ICP, mdot_ICP,dedicated = 0; the physical capped ICP gas port is "
                        "retained (A9.1 HIQ-06; A9.3 OQ-RFQ-10)",
            "dedicated_feed": "only as an explicitly labelled DIAGNOSTIC variable (DIAGNOSTIC_VARIABLE_NOT_BASELINE), "
                              "never baseline, booked in the corresponding atmospheric / Xe ledger if activated "
                              "(A9.3 OQ-RFQ-10)",
            "gas": "Ar only; label ENGINEERING_ONLY_NON_SCORING on every record; never counts toward DRDO atmospheric "
                   "requirements (owner row 36; A9.3 OQ-RFQ-02)",
            "configurations": ["hall_icp_neutralizer (P1 builds its ICP module)", "hall_c1_reference (C1 "
                               "disconnected in P1-S6; CONTROL_FALLBACK)"],
            "outcome_vocabulary_note": "P1 produces engineering records only; the architecture outcome vocabulary "
                                       "(incl. NO_VIABLE_CASE) belongs to the later comparison",
        },
        "arithmetic": ar,
        "anchor_check": anchor_check(),
        "stage_map": stages(),
        "topology_control": topology_control(red),
        "items": items(ar),
        "measurements": measurements(),
        "derived_quantities": derived(),
        "safety_interlocks": safety(),
        "run_matrix": run_matrix(ar),
        "hardware_readiness": readiness(),
        "interface_demands": interface_demands(),
        "owner_answers_applied": owner_answers_applied(),
        "open_owner_questions": open_questions(),
        "historical_reuse": historical_reuse(),
        "m16_impact": m16_impact(),
        "h3_h4_inputs": h3_h4(),
        "a9_2_statuses_carried_unchanged": a9_2_statuses(),
        "compliance": ["no performance prediction; no invented thresholds (TBD / PROPOSED / owner-given only)",
                       "no Julia; no archengine wiring; no change outside " + REL + "/ and tests/test_p1_icp_bench.py",
                       "immutable inputs pinned by sha256; governance files read but never pinned",
                       "no supplier / author / lab contact; published sources only",
                       "never PASS for ICP thermal, RF ratings or anode items"],
    }
    return doc


# ------------------------------------------------------------------------------------------------ schema
def build_schema():
    red = _reducer()
    num = {"type": "number"}
    no_pbus = {"not": {"pattern": "[Bb][^A-Za-z0-9]*[Uu][^A-Za-z0-9]*[Ss]"}}
    term = {"type": "object", "required": ["I_A", "basis"],
            "properties": {"I_A": num, "basis": {"enum": list(red.TERMINAL_BASES)}}}
    op = {
        "type": "object",
        "required": list(red.OPERATING_POINT_REQUIRED),
        "properties": {
            "schema": {"const": red.SCHEMA_ID}, "record_kind": {"const": "icp_operating_point"},
            "record_id": {"type": "string"}, "run_id": {"type": "string"}, "stage_id": {"type": "string"},
            "timestamp_utc": {"type": "string"}, "synthetic": {"type": "boolean"},
            "labels": {"type": "array", "items": {"type": "string"}, "contains": {"const": red.REQUIRED_LABEL}},
            "gas": {"enum": list(red.P1_GASES)}, "gas_mode": {"enum": list(red.GAS_MODES)},
            "record_class": {"enum": list(red.RECORD_CLASSES),
                             "description": "A9.4 P1Q-10 / P1Q-13: only ICP45_CAPACITY records feed I_e,cap; Hall-ON "
                                            "records are NEUTRALIZATION_CONSISTENCY; METERED_RETURN anode only in a "
                                            "DIAGNOSTIC_VARIANT",
                             "x-allowed-by-hall-state": {k: list(v) for k, v in
                                                         red.RECORD_CLASSES_BY_HALL_STATE.items()}},
            "diagnostic_registration_id": {"type": "string", "minLength": 1,
                                           "description": "required when record_class is DIAGNOSTIC_VARIANT"},
            "capacity_monitoring": {"type": "object", "required": list(red.CAPACITY_MONITORING_REQUIRED),
                                    "description": "required on every ICP45_CAPACITY record (A9.4 P1Q-13); the "
                                                   "terminals must then include h1_body and electron_collector "
                                                   "(MEASURED)",
                                    "properties": {"h1_body_ground_config": {"const": red.H1_BODY_GROUND_CONFIG},
                                                   "I_body_to_ground_continuous": {"const": True},
                                                   "V_anode_channel": {"const": red.V_ANODE_CHANNEL},
                                                   "V_icp_body_V": num, "V_electron_collector_V": num,
                                                   "sign_convention_id": {"type": "string", "minLength": 1}}},
            "hall_discharge_state": {"enum": list(red.HALL_STATES),
                                     "description": "discharge-supply OUTPUT state (P1-IT-40): ON = V_d applied; "
                                                    "OFF = output disabled and anode disconnected"},
            "hall_discharge_sustained": {"type": "boolean",
                                         "description": "sustained discharge per the registered definition "
                                                        "(P1-IT-32); must be false when the supply is OFF"},
            "h1_electrical": {"type": "object", "required": list(red.H1_ELECTRICAL_REQUIRED),
                              "description": "registered H-1 electrical configuration (P1-IT-39)",
                              "properties": {"config_id": {"type": "string", "minLength": 1},
                                             "anode_state": {"enum": list(red.ANODE_STATES)},
                                             "V_anode_V": num, "h1_body_state": {"type": "string", "minLength": 1},
                                             "discharge_supply_connection": {"enum": list(red.SUPPLY_CONNECTIONS)}},
                              "x-supply-connection-by-hall-state": dict(red.SUPPLY_CONNECTION_BY_HALL_STATE),
                              "x-anode-states-by-hall-state": {k: list(v) for k, v in
                                                               red.ANODE_STATES_BY_HALL_STATE.items()},
                              "x-hall-anode-terminal-basis-by-anode-state": dict(red.ANODE_TERMINAL_BASIS)},
            "rf": {"type": "object", "required": list(red.RF_REQUIRED), "properties": {
                "reference_plane": {"const": red.RF_REFERENCE_PLANE}, "P_fwd_W": num, "P_refl_W": num,
                "match_setting_id": {"type": "string"},
                "line_match_loss": {"type": "object", "required": ["status"], "properties": {
                    "status": {"enum": list(red.LOSS_STATUSES)}, "value_W": num, "source": {"type": "string"},
                    "match_setting_id": {"type": "string"}, "valid_max_gamma_abs": num},
                    "x-required-when-measured": list(red.LOSS_MEASURED_REQUIRED)}}},
            "generator": {"type": "object", "required": list(red.GENERATOR_REQUIRED), "propertyNames": no_pbus,
                          "properties": {
                "generator_class": {"enum": list(red.GENERATOR_CLASSES)}, "P_generator_input_W": num,
                "input_boundary": {"type": "string", "not": {"pattern": "[Bb][^A-Za-z0-9]*[Uu][^A-Za-z0-9]*[Ss]"}},
                "instrument": {"type": "string"}}},
            "collector": {"type": "object", "required": list(red.COLLECTOR_REQUIRED),
                          "description": "the ICP ion-collecting electrode (TK-13; ICD ICP-21); I_e is its supply-"
                                         "lead current (I_e > 0 = electrons extracted from the ICP; equals "
                                         "terminals.collector_supply.I_A within I_e_resolution_A); V_collector is "
                                         "its potential w.r.t. reference_potential",
                          "properties": {"I_e_A": num, "I_e_sign_convention": {"const": red.I_E_SIGN_CONVENTION},
                                         "I_e_resolution_A": {"type": "number", "exclusiveMinimum": 0},
                                         "V_collector_V": num,
                                         "reference_potential": {"enum": list(red.REFERENCE_POTENTIALS)}}},
            "extraction": {"type": "object", "required": list(red.EXTRACTION_REQUIRED),
                           "description": "electron-extraction topology registered at P1-G0 (P1-IT-36): the "
                                          "electrode that sinks the extracted electrons",
                           "properties": {"topology_id": {"type": "string", "minLength": 1},
                                          "electron_collecting_electrode": {"enum": list(red.EXTRACTION_ELECTRODES)}},
                           "x-allowed-by-hall-state": {k: list(v) for k, v in
                                                       red.EXTRACTION_ELECTRODES_BY_HALL_STATE.items()}},
            "h1_point_id": {"type": "string", "minLength": 1,
                            "description": "registered H-1 point id (gas/magnet conditions; required for ICP-45A "
                                           "capacity candidacy, P1-IT-38)"},
            "pressures": {"type": "object", "required": list(red.PRESSURE_FIELDS),
                          "properties": {"p_chamber_Pa": num, "p_icp_Pa": num}},
            "flows": {"type": "object", "required": list(red.FLOWS_REQUIRED), "properties": {
                "mdot_Ar_H1_mg_s": num, "mdot_icp_dedicated_mg_s": num, "ledger_booking_id": {"type": "string"}}},
            "impedance": {"type": "object", "required": list(red.IMPEDANCE_REQUIRED), "properties": {
                "status": {"enum": ["MEASURED", "NOT_MEASURED_PENDING_P2_CHAIN"]}, "R_ohm": num, "X_ohm": num}},
            "terminals": {"type": "object", "additionalProperties": term,
                          "x-required-by-hall-state-and-electrode": {"%s/%s" % k: list(v) for k, v in
                                                                     red.REQUIRED_TERMINALS.items()}},
            "temperatures": {"type": "object", "required": list(red.REQUIRED_TEMPERATURES),
                             "additionalProperties": num},
            "rf_pickup_check": {"enum": ["DONE", "NOT_DONE"]},
        },
        "propertyNames": no_pbus,
        "x-p-bus-screen": "the reducer refuses, at any nesting depth, every field name that normalises "
                          "(lower-case, alphanumerics only) to contain 'bus', and a generator.input_boundary text "
                          "naming a bus (A9.3 OQ-RFQ-06)",
    }
    seq = {
        "type": "object", "required": list(red.SEQUENCE_REQUIRED),
        "properties": {
            "schema": {"const": red.SCHEMA_ID}, "record_kind": {"const": "topology_control_sequence"},
            "gas": {"enum": list(red.P1_GASES)}, "classification": {"const": red.TOPOLOGY_CONTROL_LABEL},
            "c1_disconnected": {"const": True}, "hall_start_registration_id": {"type": "string", "minLength": 1},
            "labels": {"type": "array", "contains": {"const": red.REQUIRED_LABEL}},
            "steps": {"type": "array", "minItems": 7, "maxItems": 7, "items": {
                "type": "object", "required": ["step", "text", "signals"],
                "properties": {"step": {"type": "integer"}, "text": {"type": "string"},
                               "sustained_discharge_observed": {"type": "boolean"},
                               "sustainment_definition_id": {"type": "string"},
                               "signals": {"type": "object", "required": list(red.SEQUENCE_SIGNALS)}}}},
        },
        "x-step-texts-verbatim": [{"step": n, "text": t} for n, t in red.SEQUENCE_STEPS],
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": REL + "/" + OUT_SCHEMA,
        "title": "P1 ICP bench raw record (" + red.SCHEMA_ID + ")",
        "description": "Raw P1 bench records reduced by " + REL + "/p1_reducer.py. Generated from the reducer "
                       "constants by build_p1_icp_bench.py; the reducer enforces these rules and raises on "
                       "violations (no silent defaults). Every record is ENGINEERING_ONLY_NON_SCORING; synthetic "
                       "records must say synthetic = true.",
        "oneOf": [{"$ref": "#/$defs/icp_operating_point"}, {"$ref": "#/$defs/topology_control_sequence"}],
        "$defs": {"icp_operating_point": op, "topology_control_sequence": seq},
    }


# ------------------------------------------------------------------------------------------------ markdown
def _cell(v):
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    s = "-" if v is None or v == "" else str(v)
    return s.replace("|", "/").replace("\n", " ")


def _table(rows, cols):
    out = ["| " + " | ".join(c for c, _ in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_cell(r.get(k)) for _, k in cols) + " |")
    return out


def render_md(doc):
    L = ["# P1 ICP electron-source bench (`p1_icp_bench_v1`)", "",
         "| | |", "|---|---|",
         "| lane | `%s` (trigger `%s`) |" % (doc["lane"], doc["trigger"]),
         "| status | **%s** |" % doc["status"],
         "| A9 status | %s |" % doc["a9_status"],
         "| generated by | `%s` |" % doc["generated_by"],
         "| machine-readable | `%s/%s` |" % (REL, OUT_JSON),
         "| record schema | `%s` |" % doc["record_schema"],
         "| reducer | `%s` |" % doc["reducer"],
         "| base commit | `%s` |" % doc["base_commit"], "",
         "This is an engineering test plan, a data model and an analysis reducer. It is **not** a prediction and "
         "**not** a score-bearing campaign.", ""]
    L += ["What it is not:", ""] + ["- " + x for x in doc["what_it_is_not"]] + [""]
    L += ["## 1. Scope", "", "**Question.** " + doc["scope"]["question"], ""]
    for k in ("first_build", "gas_mode", "dedicated_feed", "gas", "outcome_vocabulary_note"):
        L.append("- **%s**: %s" % (k, doc["scope"][k]))
    L += ["", "Orificed-variant interface provisions (A9.3 OQ-VI-03):", ""]
    L += ["%d. %s" % (i + 1, p) for i, p in enumerate(doc["scope"]["orificed_variant_provisions"])] + [""]
    inc = doc["a9_4_incorporation"]
    L += ["A9.4 incorporation (`%s`, trigger `%s`, base `%s`): %s. Decision `%s` (sha256 `%s`); verbatim `%s` "
          "(sha256 `%s`). Answered: %s. P1 part of P2Q-05: %s. Execution decisions applied: %s. M16: %s." % (
              inc["follow_on"], inc["trigger"], inc["base_commit"], inc["rule"], inc["decision"]["path"],
              inc["decision"]["sha256"], inc["verbatim"]["path"], inc["verbatim"]["sha256"],
              "; ".join("%s = %s" % kv for kv in inc["answered"].items()), inc["p1_part_of"]["P2Q-05"],
              ", ".join(inc["execution_decisions_applied"]), inc["m16_impact_change"]), ""]
    L += ["Recorder flags carried: " + " / ".join(inc["recorder_flags_carried"]), ""]
    L += ["Parallel lanes (not in this base; nothing here depends on them at import/test time):", ""]
    L += ["- `%s`: %s (%s)" % (p["lane"], p["path"], p["state"]) for p in doc["pending_parallel_lanes"]] + [""]
    L += ["## 2. Arithmetic (the only computations of this lane)", ""]
    L += _table([dict(k=k, **v) for k, v in doc["arithmetic"].items()],
                [("quantity", "k"), ("expression", "expr"), ("value", "value"), ("units", "units"),
                 ("source", "source"), ("note", "note")]) + [""]
    L += ["## 3. Takahashi anchor check against the A9-05 extraction", "",
          "Owner text is not altered; mismatches are flagged.", ""]
    L += _table(doc["anchor_check"], [("id", "id"), ("quantity", "quantity"), ("reported", "reported_value"),
                                      ("unit", "unit"), ("locator", "locator"), ("basis", "value_basis"),
                                      ("used for", "used_for"), ("finding", "finding")]) + [""]
    L += ["## 4. Stage map", ""]
    for s in doc["stage_map"]:
        L += ["### %s %s" % (s["id"], s["name"]), "",
              "- prereg stage: %s; Hall discharge: %s; produces: %s" % (s["prereg_stage"], s["hall_discharge"],
                                                                       ", ".join(s["produces"])),
              "- entry: " + "; ".join(s["entry"]), "- work: " + "; ".join(s["work"]),
              "- exit: " + "; ".join(s["exit"]), ""]
    tc = doc["topology_control"]
    L += ["## 5. OQ-VI-05 topology-control sequence (verbatim steps)", "",
          "Classification `%s`. Source: %s." % (tc["classification"], tc["source"]), ""]
    L += ["%d. %s" % (s["step"], s["text"]) for s in tc["steps"]] + [""]
    L += ["Recorded signals: " + ", ".join("`%s`" % x for x in tc["signals"]), ""]
    L += ["- " + x for x in tc["interpretation"]] + [""]
    L += ["Observation vocabulary: " + ", ".join(tc["observation_vocabulary"]), ""]
    L += ["## 6. (a) Items / parameters", ""]
    L += _table(doc["items"], [("id", "id"), ("name", "name"), ("value", "value"), ("units", "units"),
                               ("basis", "basis"), ("source", "source"), ("evidence class", "evidence_class"),
                               ("status", "status"), ("freeze point", "freeze_point"), ("P1 gate", "p1_gate"),
                               ("note", "note")]) + [""]
    L += ["## 7. Measurement list", ""]
    L += _table(doc["measurements"], [("id", "id"), ("quantity", "quantity"), ("symbol", "symbol"),
                                      ("units", "units"), ("instrument class", "instrument_class"),
                                      ("reference plane", "reference_plane"), ("sampling", "sampling"),
                                      ("uncertainty sources", "uncertainty_sources"),
                                      ("metrology spec", "metrology_spec"), ("stages", "stages"),
                                      ("status", "status"), ("note", "note")]) + [""]
    L += ["## 8. Derived quantities (implemented in the reducer)", ""]
    L += _table(doc["derived_quantities"], [("id", "id"), ("quantity", "quantity"), ("formula", "formula"),
                                            ("boundary / plane", "boundary_label"), ("source", "source")]) + [""]
    L += ["## 9. Safety and interlocks", ""]
    L += _table(doc["safety_interlocks"], [("id", "id"), ("hazard", "hazard"), ("function", "function"),
                                           ("threshold", "threshold"), ("source", "source"),
                                           ("status", "status")]) + [""]
    rm = doc["run_matrix"]
    L += ["## 10. Run-matrix structure", ""]
    L += _table(rm["factors"], [("id", "id"), ("factor", "name"), ("units", "units"), ("levels", "levels")]) + [""]
    L += ["Ordering rule:", ""] + ["- " + x for x in rm["ordering_rule"]] + [""]
    L += ["Repeats: " + rm["repeats"], "", "Not a prediction: " + rm["not_a_prediction"], ""]
    L += ["## 11. Hardware readiness checklist (A9.3 six families)", ""]
    L += _table(doc["hardware_readiness"], [("id", "id"), ("family", "family"), ("item", "item"),
                                            ("RFQ v1", "rfq_v1_package"), ("RFQ v2", "rfq_v2_package"),
                                            ("H2 / H-1 / A9 items", "h2_or_h1_items"), ("status", "status")]) + [""]
    L += ["## 12. (b) Interface demands", ""]
    L += _table(doc["interface_demands"], [("id", "id"), ("dir", "direction"), ("counterpart", "counterpart"),
                                           ("what", "what"), ("units", "units"), ("status", "status")]) + [""]
    L += ["## 13. (c) Owner answers applied", ""]
    L += _table(doc["owner_answers_applied"], [("row / decision", "id"), ("kind", "kind"),
                                               ("how applied", "how_applied")]) + [""]
    L += ["## 14. (d) Open owner questions (new)", ""]
    L += _table(doc["open_owner_questions"], [("id", "id"), ("question", "question"),
                                              ("proposed answer", "proposed_answer"), ("needed by", "needed_by")])
    L += [""]
    L += ["## 15. (e) Historical reuse", ""]
    L += _table(doc["historical_reuse"], [("path", "path"), ("sha256", "sha256"), ("reused", "reused"),
                                          ("not reused", "not_reused")]) + [""]
    L += ["## 16. (f) M16 v3 impact", ""]
    L += _table(doc["m16_impact"], [("row", "row"), ("key", "key"), ("impact", "impact")]) + [""]
    L += ["## 17. (g) H3 / H4 inputs", "", "H3 procurement inputs:", ""]
    L += ["- " + x for x in doc["h3_h4_inputs"]["h3_procurement_inputs"]] + ["", "H4 test inputs:", ""]
    L += ["- " + x for x in doc["h3_h4_inputs"]["h4_test_inputs"]] + [""]
    L += ["## 18. A9.2 statuses carried unchanged", ""]
    L += ["| item | status |", "|---|---|"]
    L += ["| %s | %s |" % (k, v) for k, v in doc["a9_2_statuses_carried_unchanged"].items()] + [""]
    L += ["## Pinned inputs (sha256)", ""]
    L += ["- `%s` - `%s` (%s)" % (p["path"], p["sha256"], p["role"]) for p in doc["authority_pins"]] + [""]
    L += ["Read but never pinned (mutable governance): " + "; ".join("`%s`" % g for g in
                                                                      doc["governance_files_not_pinned"]), ""]
    L += ["## Compliance", ""] + ["- " + x for x in doc["compliance"]] + [""]
    return "\n".join(L)


def _dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def outputs():
    doc = build_doc()
    return {OUT_JSON: _dump(doc), OUT_MD: render_md(doc), OUT_SCHEMA: _dump(build_schema())}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify pins and byte-exact outputs; write nothing")
    a = ap.parse_args(argv)
    verify_pins()
    outs = outputs()
    if a.check:
        bad = []
        for name, text in outs.items():
            p = os.path.join(HERE, name)
            if not os.path.exists(p):
                bad.append(name + " missing")
                continue
            with open(p, encoding="utf-8") as f:
                if f.read() != text:
                    bad.append(name + " differs")
        if bad:
            print("CHECK FAILED: " + "; ".join(bad))
            return 1
        print("CHECK OK: %d outputs reproduce; %d pins verified" % (len(outs), len(PINS)))
        return 0
    for name, text in outs.items():
        with open(os.path.join(HERE, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print("wrote " + ", ".join(sorted(outs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

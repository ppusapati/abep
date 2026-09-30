#!/usr/bin/env python3
"""Build the P1 ICP electron-source bench package (lane fo_a9_p1_icp_bench, trigger T_A9_P1_ICP_BENCH; owner A9.3;
owner A9.4 incorporated mechanically by fo_a9_4_incorporation, trigger T_A9_4_INCORPORATION; owner A9.5 P1Q-15 /
P1Q-16 closure rule applied by fo_a9_5_closure_rule, trigger T_A9_5_CLOSURE_RULE; owner A9.6 sec. 8 / 14 P1 workflow
completion by fo_a9_6_p1_workflow_completion).

Outputs (all in this directory, deterministic, byte-reproducible):
  p1_icp_bench_v1.json              machine-readable engineering test plan + data model references
  P1_ICP_BENCH.md                   companion document generated from the JSON
  p1_bench_record_schema_v1.json    JSON schema of the raw bench records (all six record kinds), generated from
                                    p1_reducer.py constants
  p1_campaign_report_schema_v1.json JSON schema of the campaign report of p1_campaign.run_campaign (and its bundle)

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
A95_INC_BASE = "71f31b2a254fe01059b130b554b97c7584ae6b30"   # base of the A9.5 closure-rule lane (fo_a9_5_closure_rule)
A96_INC_BASE = "1d67f99f88007982eff77670b64c6eb7c595bccd"   # base of the A9.6 P1 workflow lane (fo_a9_6_p1_workflow_completion)
OUT_REPORT_SCHEMA = "p1_campaign_report_schema_v1.json"
XE_A9 = "docs/budgets/" + "xe" + "_ledger_a9/" + "xe" + "_ledger_a9_v1.json"   # path of the A9 Xe ledger
P2_PATH = "docs/experiments/hall_icp/p2_impedance_map/"
RFQ_V2_PATH = "docs/procurement/rfq_a9_v2/"
# merged P2 preparation package (same follow-on lane as this file, regenerated together): its ids are cross-checked
# at build time against the JSON; it is not sha-pinned because it is not an immutable input of this lane
P2_JSON = P2_PATH + "p2_impedance_prep_v1.json"
RFQ2 = RFQ_V2_PATH + "rfq_a9_v2.json"       # merged RFQ v2 (current deliverable; cited ids checked, not sha-pinned: the RFQ v2 builder reads P1, so a pin would be circular)

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
A95 = "docs/decisions/OD_2026_09_30_A9_5_p1_closure_owner_decisions.json"
A95_MD = "docs/decisions/OD_2026_09_30_A9_5_P1_CLOSURE_OWNER_DECISIONS.md"
A96 = "docs/decisions/OD_2026_09_30_A9_6_implementation_first_directive.json"
A96_MD = "docs/decisions/OD_2026_09_30_A9_6_IMPLEMENTATION_FIRST_DIRECTIVE.md"
# external published reference used by the DERIVED rules (open access, BIPM); cited, not pinned in the repository:
# the sha256 is of the PDF as fetched by this lane on 2026-09-30 (so a later reviewer can confirm the same edition)
GUM = {"citation": "JCGM 100:2008, Evaluation of measurement data - Guide to the expression of uncertainty in "
                   "measurement (GUM 1995 with minor corrections), Joint Committee for Guides in Metrology",
       "url": "https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf",
       "fetched_pdf_sha256": "41bbf068fbc0d7986c98691b2d1af6680cb3044f6a1a89b3560933ed9ef9626c",
       "clauses_used": {"5.1.2": "Eq. (10): u_c^2(y) = sum_i (df/dx_i)^2 u^2(x_i) for uncorrelated input quantities "
                                 "(law of propagation of uncertainty)",
                        "5.2.1": "Eq. (10) valid only for independent / uncorrelated inputs; significant correlations "
                                 "must be taken into account",
                        "5.2.2": "Eq. (13) covariance form; Eq. (14) correlation coefficient r(x_i, x_j), -1 <= r <= 1; "
                                 "Eq. (15) covariance term 2 sum_i<j (df/dx_i)(df/dx_j) u(x_i) u(x_j) r(x_i, x_j)",
                        "F.2.2.1": "resolution of a digital indication: even identical repeated indications leave a "
                                   "non-zero uncertainty, u = 0.29 delta_x"},
       "evidence_class": "published standard (verified by this lane against the fetched PDF text)"}
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
    (A95, "c9e101f2c409c2d28ad256818c22f13ee801bc532d7e4ef470f375d7bb1fe1d3",
     "owner A9.5 P1Q-15 / P1Q-16 closure decisions (machine-readable)"),
    (A95_MD, "9e49e923328441c1fc82afd3eb64c13d85fc818e8fe534576ada61a16fa525f3",
     "owner A9.5 verbatim (P1Q-15 Kirchhoff closure rule, P1Q-16 capacity formula)"),
    (A96, "d8d8496f4141a7096496d3a893c95c3db524ca501055a26cc868fb35d0ae9327",
     "owner A9.6 implementation-first directive (machine-readable; sec. 2 magnitude form, sec. 8 / 14 P1 workflow)"),
    (A96_MD, "c6ee26e57ea5ca559f4fa4e4a8809b1aa8f3a217e50c534b943fc3ad99240634",
     "owner A9.6 verbatim (sec. 2 P1Q-15 / P1Q-16, sec. 5-7 derived vs TBD_OWNER, sec. 8 P1 workflow, sec. 14 reducers)"),
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


def _campaign():
    spec = importlib.util.spec_from_file_location("p1_campaign_for_builder", os.path.join(HERE, "p1_campaign.py"))
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
                        "(RFQ v2 GAS-L01, option GAS-O01 only if one unit cannot cover the sweep; " + RFQ2 + ")"),
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
        it("P1-IT-35", "Z_ICP measurement during P1", "PENDING the installed and calibrated P2 chain: methods ZM-A "
           "(V/I probe INS-P2-01), ZM-B (de-embedded complex reflection, VNA INS-P2-04) and ZM-C, calibration plan "
           "CAL-P2-01..15, offered to P1 as IDP2-03 (" + P2_JSON + "); until that chain is installed and calibrated "
           "Z_ICP is recorded NOT_MEASURED_PENDING_P2_CHAIN", "ohm", "owner decision",
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
           "chamber wall (sink = facility_ground terminal). Option (A) is OWNER_DECIDED for every ICP45_CAPACITY record "
           "by A9.4 P1Q-10 (dedicated, isolated, instrumented electron-collecting electrode; consistent with this "
           "lane's earlier reasoning that with (B) ICP emission cannot be separated from wall / facility current paths "
           "in the Kirchhoff closure); "
           "whether (B) remains usable for non-capacity ENGINEERING_SURFACE records is P1Q-09", "-, mm, V",
           "this lane (form) + published anchor; option A for capacity records owner decision A9.4 P1Q-10",
           EVI + " TK-13, TK-40; ICD ICP-21; " + VIN + " VI-EX-03; " + A94 + " decisions.P1Q-10", None,
           "TBD (geometry / position / reference); option A OWNER_DECIDED for ICP45_CAPACITY records (A9.4 P1Q-10)",
           "after-evidence", "P1-G0",
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
           "I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF (the A9.4 recorder reading of the incomplete verbatim "
           "'Define:' formula, CONFIRMED by owner A9.5 P1Q-16) using SIGNED currents under the same registered current "
           "convention; the RF-OFF term estimates facility/background electron collection; no absolute-value "
           "correction and no zero-clipping (a negative corrected value stays negative and is reported as such). "
           "ICP-45A is eligible for evaluation only when (1) the capacity point passes current closure (P1-IT-47), (2) "
           "the matched RF-OFF correction is valid (P1-D-07), (3) all required uncertainties are available (u(I_k) of "
           "every channel, P1-IT-49; u_I_e_A and u_I_d_max_A of the margin rule, P1-IT-29) and (4) I_d,max,H1 is "
           "registered (P1-IT-07); then the preregistered one-sided lower bound M_n,LB of M_n = I_e,cap / I_d,max,H1 "
           "- 1 must be > 0; until all four exist ICP45 = NOT_EVALUATED. Hall-ON records are retained only as NEUTRALIZATION_CONSISTENCY, never ICP45_CAPACITY (with Hall ON "
           "I_e,ICP ~ I_d because the anode closes the discharge circuit). Only the dedicated electron-collector "
           "current is the capacity measurand", "A", "owner decision",
           A94 + " decisions.P1Q-10; " + A94_MD + " P1Q-10; " + A95 + " decisions.P1Q-16; " + A95_MD + " P1Q-16; "
           + A91 + " ICP-45, UBQ-02; " + A93 + " OQ-A907-02",
           "owner-stated", "OWNER_DECIDED (A9.4 P1Q-10 CAPACITY_EXTRACTION_FORM; formula OWNER_CONFIRMED A9.5 P1Q-16)",
           "NOW", "P1-S7 entry",
           "synthetic records only ever yield SYNTHETIC_TEST_ONLY_NOT_EVIDENCE; excluded records are listed with "
           "reasons; until I_d,max,H1 is registered, or without an eligible closure-valid ICP45_CAPACITY record, the "
           "status is exactly NOT_EVALUATED, never PASS or FAIL; Hall-ON measurements remain NEUTRALIZATION_CONSISTENCY "
           "and never define I_e,cap (A9.5 P1Q-16)"),
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
           "the sustainment observation); OFF = physically disconnected: " + A94 + " decisions.P1Q-13", "assumed",
           "PROPOSED (definition); OFF = supply output physically disconnected is OWNER_DECIDED (A9.4 P1Q-13)", "NOW",
           "P1-G0",
           "the P1-S7H (Hall-ON follow-up) RF-OFF facility pair is taken with V_d applied (state ON) inside the "
           "registered start-attempt limits P1-IT-31, whether or not a discharge is sustained; OFF also requires "
           "discharge_supply_connection = PHYSICALLY_DISCONNECTED (A9.4 P1Q-13)"),
        it("P1-IT-41", "validity of a MEASURED line/match loss", tbd + "the P1-S1/S2 two-port data for the "
           "residual-|Gamma| validity limit valid_max_gamma_abs (frozen at P1-G1). Form: each MEASURED "
           "P_line/match,loss is de-embedded from the two-port S-parameter data at the recorded match_setting_id; "
           "it is valid only at that setting and up to that limit; outside it the loss must be FLAGGED_NOT_MEASURED",
           "W, -", "this lane (form)", A92 + " OQ-A907-11 (P_delivered with the loss term); " + UB + " UB-RF-05",
           None, "TBD (form fixed; limit value from S1/S2)", "after-evidence", "P1-G1"),
        it("P1-IT-42", "I_e sign convention and channel resolution", "network convention (owner): conventional "
           "current INTO the defined isolated electrical network is positive, every channel transformed into it before "
           "analysis (A9.5 P1Q-15); I_e orientation (this lane): I_e > 0 = net electrons extracted from the ICP, so the "
           "collector_supply terminal carries I_A = +I_e; the two readings must agree within the I_e channel "
           "resolution (TBD - requires the channel certificate)", "A",
           "owner decision (network convention) + this lane (I_e orientation label)",
           A95 + " decisions.P1Q-15.sign_convention; this lane", "owner-stated",
           "OWNER_DECIDED network convention (A9.5 P1Q-15); I_e orientation label PROPOSED (this lane)", "NOW",
           "P1-G0", "negative I_e is flagged (net ion collection or sensor orientation), not silently accepted; the "
           "capacity measurand I_e,collector = -I_A(electron_collector) under the same convention (A9.4 P1Q-10; "
           "a sign transformation, never an absolute value)"),
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
        it("P1-IT-47", "Kirchhoff current-closure rule for ICP45_CAPACITY records (owner rule)",
           {"sign_convention": "conventional current INTO the defined isolated electrical network is positive; every "
                               "channel transformed into it before analysis; paired / compared records share the "
                               "registered convention id",
            "terms": "signed I_ecollector, I_H1,body, I_anode, I_facility, I_ICP,body and any other intentional "
                     "terminal crossing the registered network boundary, where physically present/measurable",
            "residual": "R_I = sum_k I_k",
            "statistical_closure": "|R_I| <= 3 u_R", "k_sigma": 3.0,
            "fractional_closure": "|R_I| / max(|I_e,collector|, I_scale,min) <= 0.02", "fraction_max": 0.02,
            "floating_anode": "I_anode ~ 0 by construction (OPEN_CIRCUIT_BY_CONSTRUCTION); V_anode still recorded",
            "no_silent_zero": "an unavailable channel is never set to zero (terminal basis NOT_MEASURED excludes the "
                              "point: intentional return path unmeasured)"},
           "-, A", "owner decision; the factor 3 and the 2 % are hard-coded owner constants (p1_reducer "
           "CLOSURE_K_SIGMA, CLOSURE_FRACTION_MAX), never caller parameters; not relaxed after observing propulsion "
           "results", A95 + " decisions.P1Q-15; " + A95_MD + " P1Q-15; " + A96 + " summary.p1q15_denominator",
           "owner-stated",
           "OWNER_DECIDED (A9.5 P1Q-15 KIRCHHOFF_CLOSURE_RULE; magnitude form A9.6 sec. 2)", "NOW", "P1-G0",
           "replaces the earlier registered relative-tolerance rule (P1Q-15 answered); the registered inputs are the "
           "sign-convention id and I_scale,min (P1-IT-48); implemented by p1_reducer.kirchhoff_closure"),
        it("P1-IT-48", "I_scale,min: denominator floor of the fractional closure", tbd + "registration before the "
           "first ICP45_CAPACITY record from the instrument capability of the dedicated electron-collector channel "
           "(A9.5 P1Q-15: 'a small registered denominator floor based on instrument capability, used only to avoid an "
           "unstable percentage near zero'); the reducer requires it (closure_rule.I_scale_min_A with its basis) and "
           "has no default", "A", "owner decision (rule); value registered", A95 + " decisions.P1Q-15.admission",
           None, "TBD (registered input)", "after-evidence", "P1-G0",
           "used only as max(|I_e,collector|, I_scale,min) in the fractional closure; never in the statistical closure "
           "and never in the instrument-adequacy test"),
        it("P1-IT-49", "channel uncertainty u(I_k) and combined u_R", tbd + "the calibration certificates, zero/"
           "offset records, resolution, repeatability (where applicable) and registered RF-pickup contribution (P1-M-22) "
           "of every current channel. Form (owner): u_R = sqrt(sum_k u^2(I_k)) for independent calibrated channels; the "
           "full covariance form sum_ij r_ij u(I_i) u(I_j) when correlations are established (registered correlation, "
           "closure_rule.covariance)", "A", "owner decision (form); values from certificates",
           A95 + " decisions.P1Q-15.uncertainty", None, "TBD (form OWNER_DECIDED)", "after-evidence", "P1-G1",
           "record fields per MEASURED terminal: uncertainty {u_calibration_A, u_zero_offset_A, u_resolution_A (> 0), "
           "u_repeatability_A or 'NOT_APPLICABLE', u_rf_pickup_A or 'NONE_REGISTERED'} and sign_convention_id; a "
           "missing component makes the point not evaluable (never a zero default); OPEN_CIRCUIT_BY_CONSTRUCTION "
           "terminals contribute I = 0, u = 0 by construction (P1Q-20)"),
        it("P1-IT-50", "instrument adequacy at a candidate qualification point",
           "if 3 u_R > 0.02 |I_e,collector| the point is NOT_EVALUATED_INSTRUMENT; the tolerance is never widened; the 2 % "
           "criterion is never relaxed after observing propulsion results", "-", "owner decision",
           A95 + " decisions.P1Q-15.instrument_adequacy; " + A96 + " summary.p1q15_denominator", "owner-stated",
           "OWNER_DECIDED (A9.5 P1Q-15; A9.6 sec. 2)", "NOW", "P1-G1",
           "applied at the RF-ON ICP45_CAPACITY record (the candidate point); the matched RF-OFF record is tested with "
           "the I_scale,min floor (recorder reading, P1Q-18); reported per point in capacity_point_outcomes; precedence "
           "DERIVED (P1Q-22, derived_resolutions): A9.5 exclusions independent of the closure test -> missing u(I_k) "
           "(NOT_EVALUATED_UNCERTAINTY) -> statistical failure |R_I| > 3 u_R (EXCLUDED: normalised to u_R, so not "
           "explainable by instrument inadequacy) -> NOT_EVALUATED_INSTRUMENT (fractional-only failures kept as "
           "closure_test_results_not_decisive) -> fractional failure (EXCLUDED)"),
        it("P1-IT-51", "capacity-point exclusions (retained with reason)",
           ["current sign conventions differ between channels", "an intentional return path is unmeasured",
            "an unintended ground path is found (capacity_monitoring.unintended_ground_path_found, "
            "ground_path_check_id)", "|R_I| > 3 u_R", "fractional closure exceeds 2 %",
            "RF-ON/RF-OFF pairing is not matched", "synthetic and measured evidence are mixed",
            "the H-1 anode is not physically disconnected/floating in an ICP45_CAPACITY record"],
           "-", "owner decision", A95 + " decisions.P1Q-15.exclusions", "owner-stated", "OWNER_DECIDED (A9.5 P1Q-15)",
           "NOW", "P1-G0",
           "excluded points stay in the raw record; the reducer lists them in excluded_records and "
           "capacity_point_outcomes with every reason and still evaluates every other point. Exclusions, not refusals: "
           "a registered RF-ON / RF-OFF pair that is not matched (each differing field with both values and the match "
           "rule id, p1_reducer.facility_pair_mismatches), an H-1 anode not physically disconnected / floating in an "
           "ICP45_CAPACITY record (A9.5 exclusion applied over the A9.4 P1Q-13 'refused' wording - DERIVED, "
           "P1Q-21: A9.5 is the later owner addendum and lists it as an exclusion), any terminal declared NOT_MEASURED (h1_body, electron_collector, icp_body, facility_ground or any "
           "other) and I_body->ground not continuous (intentional return path unmeasured), an unintended ground path, "
           "differing sign conventions and the statistical / fractional closure failures; a missing u(I_k) gives "
           "NOT_EVALUATED_UNCERTAINTY (A9.6 sec. 14). Still "
           "REFUSED (raised; input errors, not findings): a record that is incomplete (a required terminal or "
           "capacity_monitoring field absent from the record, CLAUDE.md rule 3) or not a capacity record at all "
           "(Hall ON, wrong stage, not the dedicated collector, not the single-point metered body ground, V_anode not on "
           "a high-impedance isolated channel), a missing match rule, and synthetic / measured capacity candidates "
           "mixed in one evaluation (PR #34); in the campaign driver a whole bundle mixing synthetic and measured "
           "records is refused (P1-IT-53)"),
        it("P1-IT-52", "registered operating domain per P1 stage (campaign OUT_OF_DOMAIN rule)", tbd + "registration "
           "before each stage (registrations.operating_domains: {stage_id: {domain_id, P_fwd_W, p_chamber_Pa, "
           "mdot_Ar_H1_mg_s, V_collector_V as [min, max]}}), from the procured ratings and the P1 run matrix; a record "
           "outside it, of an unregistered stage, or taken before P1-G0 is met is OUT_OF_DOMAIN (never a FAIL)",
           "W, Pa, mg/s, V", "A9.6 sec. 14 (OUT_OF_DOMAIN distinct from FAIL); values registered",
           A96_MD + " sec. 14", None, "TBD (registered input)", "LOCK-1", "P1-G0",
           "the driver has no default domain; P_fwd is not checked on RF-OFF records"),
        it("P1-IT-53", "campaign evidence kind", "one bundle is either SYNTHETIC_TEST_ONLY or MEASURED; any record whose "
           "'synthetic' flag contradicts the manifest refuses the whole bundle (no report)", "-",
           "owner rule: A9.5 P1Q-15 exclusion 'synthetic and measured evidence mixed'; A9.6 sec. 14 'mixed "
           "synthetic/measured evidence -> refused'", A95 + " decisions.P1Q-15.exclusions; " + A96_MD + " sec. 14",
           "owner-stated", "OWNER_DECIDED (A9.6 sec. 14)", "NOW", "P1-G0", "p1_campaign.MixedEvidenceError"),
        it("P1-IT-54", "P1 photodiode unlit threshold for the optical plasma-state class", tbd + "the P1 dark / "
           "background, RF-powered known-unlit and known-lit records (A9.4 P2Q-05); frozen before the P2 map. Until "
           "registered, every P1 optical state is UNCERTAIN (never forced to UNLIT)", "V",
           "owner decision (method); value from P1 evidence", A94 + " decisions.P2Q-05", None,
           "TBD_AFTER_EVIDENCE", "after-evidence", "P1-G5", "p1_reducer.classify_plasma_state"),
        it("P1-IT-55", "DWV leakage acceptance criterion (per insulation path)", tbd + "the insulation-path / "
           "feedthrough ratings (P1-IT-44 note; not given by the owner). Until registered the P1-G0 status is "
           "G0_NOT_EVALUATED_TBD", "A", "owner decision (DWV performed at 1.05 kV / 60 s, leakage recorded); "
           "acceptance value not decided", A94 + " decisions.P1Q-14.initial_dwv", None, "TBD", "LOCK-1", "P1-G0",
           "p1_reducer.reduce_readiness"),
        it("P1-IT-56", "RF-ON / RF-OFF collector-channel correlation r", tbd + "the collector-channel calibration "
           "(certificate) - registered as margin_rule.rf_on_off_collector_correlation {correlation_id, r}; when absent "
           "u(I_e,cap)_channels uses r = 0, reported as an ASSUMPTION (JCGM 100:2008 5.2.1)", "-",
           "DERIVED form (JCGM 100:2008 5.2.2 Eq. (13)/(15)); value registered", A96_MD + " sec. 6; " + GUM["url"],
           None, "TBD (registered input, optional)", "after-evidence", "P1-S7",
           "p1_reducer.u_i_e_cap_channels (P1Q-23(b) DERIVED)"),
        it("P1-IT-57", "treatment of a registered u_I_e_A below the channel propagation", "TBD_OWNER (P1Q-19): the two "
           "admissible treatments REQUIRE_REGISTERED_GE_CHANNEL and USE_LARGER_OF_REGISTERED_AND_CHANNEL are computed "
           "side by side; ICP45 = NOT_EVALUATED whenever they disagree; the registered value is never used as it "
           "stands when it is below the propagation (DERIVED)", "A", "A9.6 sec. 7 (genuine design choice stays "
           "TBD_OWNER; support all admissible outcomes)", A96_MD + " sec. 7", None, "TBD_OWNER", "LOCK-1", "P1-S7",
           "p1_reducer._p1q19_alternatives"),
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
         "work": ["cold antenna reflection / impedance through the local match (VNA, A9H-INS-03; P2 CAL-P2-08 / INS-P2-04)",
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
         "work": ["electron extraction to the registered electron-collecting electrode: for every ICP45_CAPACITY "
                  "record the dedicated, isolated, instrumented electron-collecting electrode (OWNER_DECIDED, A9.4 "
                  "P1Q-10; terminal 'electron_collector'; geometry / position / reference registered at P1-G0, "
                  "P1-IT-36); the ICP ion-collecting electrode is biased negative w.r.t. that electrode (TK-40 "
                  "polarity); V_collector recorded against the registered reference",
                  "collector bias sweep at each (P_RF, mdot) point, ascending current limit with hold points",
                  "report the SURFACE I_e = f(P_RF, p, mdot, Z_ICP, V_collector) (A9.3 OQ-A907-02)",
                  "Kirchhoff current-path closure per point (collector, ICP body, facility/chamber ground, H-1 anode "
                  "(MEASURED metered return or OPEN_CIRCUIT_BY_CONSTRUCTION, P1-IT-39), and the electron_collector "
                  "terminal when the dedicated target is used); for ICP45_CAPACITY records the owner rule P1-IT-47 "
                  "(A9.5 P1Q-15: |R_I| <= 3 u_R and <= 2 % of max(|I_e,collector|, I_scale,min); channels in the "
                  "registered convention with u(I_k), P1-IT-49; unavailable channels declared NOT_MEASURED, never "
                  "zero)", "V_anode recorded (P1-M-15)",
                  "facility-electron contribution check: RF OFF at the same bias and reference, flow, gas mode, "
                  "Hall state, extraction topology and pressure (within P1-IT-37)",
                  "C_e and C_e,DC with boundary labels per point",
                  "records intended as ICP-45 capacity candidates are registered as record_class ICP45_CAPACITY in the "
                  "A9.4 P1Q-13 configuration (anode floating, supply physically disconnected, continuous h1_body "
                  "ground current, dedicated collector, recorded unintended-ground-path check); other records are "
                  "ENGINEERING_SURFACE"],
         "exit": ["surface table filed; the ICP45_CAPACITY records are the P1-IT-38 (OWNER_DECIDED, A9.4 P1Q-10) "
                  "I_e,cap candidates once I_d,max,H1 and its registered points exist; ICP-45A exactly NOT_EVALUATED "
                  "until then; never PASS because 1 A, 2 A, ... is reached"],
         "produces": ["ENGINEERING_ONLY_NON_SCORING"], "hall_discharge": "OFF"},
        {"id": "P1-S5", "name": "stability dwells and stable-region handoff to P2",
         "prereg_stage": "HI-S1A (module bench check)", "entry": ["surface from P1-S4"],
         "work": ["repeated re-ignitions and dwells at candidate points (repeats: run matrix)",
                  "dwell metrics: relative drift of I_e and P_refl (and Z where measured), maximum step / std "
                  "(mode-jump indicator), ignition success fraction; temperatures recorded"],
         "exit": ["P1-G5: 'stable ICP operating region' handoff record to P2 (IDP2-01; P2 gate S-10 / HM-R01) classified only "
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
                   "Kirchhoff closure rule inputs registered: sign-convention id and I_scale,min (P1-IT-47 / "
                   "P1-IT-48; the factor 3 and the 2 % are A9.5 owner constants) and the channel uncertainties "
                   "u(I_k) (P1-IT-49)",
                   "H-1 electrical configuration per A9.4 P1Q-13 registered (P1-IT-39)"],
         "work": ["CAPACITY block (ICP-45A, record_class ICP45_CAPACITY): Hall discharge supply OFF and physically "
                  "disconnected from the H-1 anode (anode floating, V_anode on a high-impedance isolated channel, "
                  "OPEN_CIRCUIT_BY_CONSTRUCTION); ICP operating; electrons extracted to the dedicated, isolated, "
                  "instrumented electron-collecting electrode (P1-IT-36); gas / magnetic field / pressure / geometry of "
                  "each registered H-1 point (h1_point_id); ascending to and beyond I_d,max,H1 inside the stand-ceiling "
                  "ratings; matched RF-OFF ICP45_CAPACITY record at every candidate point (P1-D-07); H-1 body single-"
                  "point metered return with I_body->ground logged continuously; ICP body, anode and collector "
                  "potentials and chamber / facility return current (where measurable) monitored; owner Kirchhoff "
                  "closure per point, RF-ON and matched RF-OFF record (P1-IT-47, P1-D-13); instrument adequacy "
                  "3 u_R <= 0.02 |I_e,collector| at the candidate point, else NOT_EVALUATED_INSTRUMENT (P1-IT-50)",
                  "I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF, signed, no absolute value, no clipping "
                  "(P1-IT-38; OWNER_DECIDED A9.4 P1Q-10, confirmed A9.5 P1Q-16); ICP-45A evaluated only when "
                  "conditions (1)-(4) of A9.5 P1Q-16 hold, then M_n,LB > 0",
                  "never the largest current in the bundle, never an RF-OFF, dedicated-feed, Hall-ON, metered-return "
                  "(DIAGNOSTIC_VARIANT), closure-invalid, NOT_EVALUATED_INSTRUMENT or uncorrected record as I_e,cap"],
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
          "VNA (cold; P2 INS-P2-04, CAL-P2-08) and in-situ V/I (plasma; P2 INS-P2-01, method ZM-A)",
          "antenna feed (de-embedded; P2 plane RP-ANT)",
          "per P1-S2 cold map; plasma points when the P2 chain exists", ["A9H-INS-03", "UB-P2-Z-03", "UB-P2-Z-08"],
          "S2-S5",
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
          "owner row 64; ICD ICP-17; the registered RF-pickup contribution of each current channel enters its u(I_k) "
          "as u_rf_pickup_A in ICP45_CAPACITY records (A9.5 P1Q-15; P1-IT-49)"),
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
          "terminal absent from a capacity record -> the reducer refuses the record (incomplete); declared NOT_MEASURED "
          "or not continuous -> the capacity point is excluded (intentional return path unmeasured, A9.5 P1Q-15); "
          "enters the Kirchhoff closure P1-D-13"),
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
        {"id": "P1-D-06", "quantity": "current-path closure residual (descriptive, every record)",
         "formula": "sum of signed terminal currents / "
         "max |terminal current| over {collector_supply, icp_body, facility_ground, hall_anode (, "
         "electron_collector, h1_body)}; hall_anode is in every closure (metered or OPEN_CIRCUIT_BY_CONSTRUCTION, "
         "P1-IT-39); h1_body (I_body->ground) in every ICP45_CAPACITY record (A9.4 P1Q-13); a NOT_MEASURED terminal "
         "is never summed as zero (no residual formed); descriptive only - admission of capacity points is P1-D-13",
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
                    "I_e,collector,RFON - I_e,collector,RFOFF (signed; no absolute value, no clipping) per P1-IT-38 "
                    "(OWNER_DECIDED, A9.4 P1Q-10; confirmed A9.5 P1Q-16): "
                    "ICP45_CAPACITY records only, never NEUTRALIZATION_CONSISTENCY (Hall-ON) records; status exactly "
                    "NOT_EVALUATED until I_d,max,H1 is registered",
         "source": A91 + " UBQ-02, UBQ-07, ICP-45; " + A93 + " OQ-A907-02; " + A94 + " decisions.P1Q-10, "
                   "execution_decisions.i_d_max_h1; " + A95 + " decisions.P1Q-16.evaluation"},
        {"id": "P1-D-12", "quantity": "Hall-on neutralization consistency (descriptive; label "
         "NEUTRALIZATION_CONSISTENCY)", "formula": "ICP-supplied current (facility-corrected where an RF-OFF pair "
         "exists) vs |I_hall_anode| at the same P1-S7H Hall-ON record; ratio, sustainment, closure residual, "
         "collector / reference potentials and RF power reported; never a gate, never ICP45_CAPACITY and never "
         "I_e,cap", "source": A94 + " decisions.P1Q-10.hall_on, hall_on_follow_up"},
        {"id": "P1-D-13", "quantity": "capacity-point closure validity (owner Kirchhoff rule)",
         "formula": "R_I = sum_k I_k (every terminal in the registered convention; OPEN_CIRCUIT_BY_CONSTRUCTION = 0); "
                    "closure-valid iff |R_I| <= 3 u_R AND |R_I| / max(|I_e,collector|, I_scale,min) <= 0.02, for the RF-ON "
                    "ICP45_CAPACITY record and its matched RF-OFF record; excluded (reason kept) otherwise",
         "source": A95 + " decisions.P1Q-15"},
        {"id": "P1-D-14", "quantity": "combined residual uncertainty u_R",
         "formula": "independent channels: u_R = sqrt(sum_k u^2(I_k)), u(I_k) = sqrt(u_cal^2 + u_zero^2 + u_res^2 "
                    "(+ u_rep^2) (+ u_pickup^2)); correlated channels: u_R^2 = sum_ij r_ij u(I_i) u(I_j) with the "
                    "registered correlation (full covariance form)",
         "basis": "u_R forms: owner (A9.5 P1Q-15). The root-sum-square combination of the five listed components "
                  "into u(I_k) is DERIVED (P1Q-23(a)): each component is an independent input quantity with "
                  "sensitivity 1, so JCGM 100:2008 5.1.2 Eq. (10) gives the root-sum-square",
         "source": A95 + " decisions.P1Q-15.uncertainty"},
        {"id": "P1-D-15", "quantity": "instrument adequacy and I_e,cap channel uncertainty",
         "formula": "adequate iff 3 u_R <= 0.02 |I_e,collector| at the RF-ON candidate point (else "
                    "NOT_EVALUATED_INSTRUMENT); u(I_e,cap)_channels = sqrt(u^2(I_col,RFON) + u^2(I_col,RFOFF) - "
                    "2 r u(I_col,RFON) u(I_col,RFOFF)) with a registered r (P1-IT-56) or r = 0 as a reported "
                    "assumption; compared with the preregistered margin-rule u_I_e_A (P1-D-19)",
         "basis": "adequacy test: owner (A9.5 P1Q-15, magnitude form A9.6 sec. 2). u(I_e,cap)_channels DERIVED "
                  "(P1Q-23(b)): JCGM 100:2008 5.2.2 Eq. (13)/(15) with sensitivities +1 / -1",
         "source": A95 + " decisions.P1Q-15.instrument_adequacy, P1Q-16; " + A91 + " UBQ-02; " + A96 + " "
                   "summary.p1q15_denominator; " + GUM["url"] + " 5.2.2"},
        {"id": "P1-D-16", "quantity": "calorimetric cross-check statistic z_x (P1-S1 dummy load)",
         "formula": "z_x = (P_coupler - P_cal) / sqrt(u^2(P_coupler) + u^2(P_cal)), P_coupler = P_fwd - P_refl at the "
                    "coupler plane; |z_x| <= k_x = 2 on every record -> CROSS_CHECK_AGREES, else EXCLUDED_INSTRUMENT "
                    "(every RF-dependent derived quantity withheld); no record -> NOT_EVALUATED",
         "source": UB + " UB-RF-08; " + A91 + " UBQ-04"},
        {"id": "P1-D-17", "quantity": "optical plasma-state class (UNLIT / E_MODE / H_MODE / UNCERTAIN)",
         "formula": "line of sight lost or saturated -> UNCERTAIN; no registered threshold -> UNCERTAIN; below threshold "
                    "with electrical evidence of ignition / mode transition -> UNCERTAIN, else UNLIT; lit with a "
                    "registered E/H assignment -> E_MODE / H_MODE, else UNCERTAIN",
         "source": A94 + " decisions.P2Q-05; " + A96_MD + " sec. 5, 14"},
        {"id": "P1-D-18", "quantity": "stable-region handoff record (P1-S5 -> P2 IDP2-01)",
         "formula": "points within OWNER criteria (P1Q-01) with ignition repeatability of their registered ignition "
                    "point; envelope [min, max] of P_fwd, mdot_Ar,H1, p_chamber, V_collector over those TESTED points "
                    "(labelled ENVELOPE_OF_TESTED_POINTS_NOT_A_STABILITY_CLAIM_BETWEEN_POINTS); NOT_EVALUATED without "
                    "criteria", "source": A96_MD + " sec. 8; P2 IDP2-01"},
        {"id": "P1-D-19", "quantity": "P1Q-19 alternatives for the u(I_e,cap) used in M_n",
         "formula": "registered u_I_e_A >= u(I_e,cap)_channels: both treatments identical, M_n with u_I_e_A; otherwise "
                    "REQUIRE_REGISTERED_GE_CHANNEL -> NOT_EVALUATED, USE_LARGER_OF_REGISTERED_AND_CHANNEL -> M_n with "
                    "u(I_e,cap)_channels; overall NOT_EVALUATED (TBD_OWNER) when they disagree",
         "source": A96_MD + " sec. 6-7; " + GUM["url"] + " 5.1.2 / 5.2.2"},
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
             "chain exists (P2 methods ZM-A/B/C; tuning state logged per P2 HM-F08)"},
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


NO_V2 = "no RFQ v2 line"
# P1-HW-nn -> RFQ v2 line ids (docs/procurement/rfq_a9_v2/rfq_a9_v2.json, not pinned (circular otherwise); every cited id is checked to exist
# by rfq_v2_check()); where no line exists this says so explicitly
RFQ_V2_MAP = {
    1: "RF-L01", 2: "RF-L02, RF-L03", 3: "RF-L04 (mounting provision ME-L08)", 4: "RF-L05, RF-L07",
    5: "RF-L08, RF-L09", 6: "RF-L10",
    7: NO_V2 + " for the VNA / two-port set (RFQ2-RF-N06 only asks the RF supplier to state compatibility with "
          "calibrated complex-reflection / V/I measurement)",
    8: "RF-L11", 9: "GAS-L01 (option GAS-O01)", 10: "GAS-L16 (calibration line; no separate calibration-volume line)",
    11: "GAS-L12", 12: "GAS-L13, GAS-L14", 13: "GAS-O02 (option line, dispatch LATER)", 14: "ME-L07",
    15: NO_V2 + " (H-1 gas path / plenum is an H2-3 / H2-1 design item; P1 Ar shut-off valves GAS-L07)",
    16: "VAC-L01 (chamber interfaces; the chamber itself has no line - facility, owner row 139)", 17: "VAC-L02",
    18: "VAC-L03, VAC-L04, RF-L07", 19: "VAC-L05 (dispatch LATER)", 20: "VAC-L07", 21: "ME-L07 (gauge GAS-L12)",
    22: NO_V2 + " (H-1 is the H2-1 design item)", 23: "HE-L01",
    24: NO_V2 + " as an explicit line (closest HE-L05 sensing; whether the high-impedance V_anode channel becomes an "
           "explicit line is RFQ v2 OQ-RFQV2-07, OPEN)",
    25: "HE-L02", 26: "HE-L03",
    27: NO_V2 + " for the electron-collecting target circuit (closest HE-L05 discharge / collector V/I sensing)",
    28: NO_V2 + " as an explicit line (RFQ v2 OQ-RFQV2-07, OPEN, asks whether the H-1 body metered ground-current "
           "monitor becomes an explicit line; closest HE-L05)",
    29: "HE-L04, VAC-L03", 30: NO_V2 + " (the DWV requirement is carried by HE-L04 / VAC-L03; no tester line)",
    31: "HE-L05 (requirement RFQ2-HALLEL-R07)", 32: "HE-L10, HE-L11, HE-L12, HE-L13 (dispatch LATER)",
    33: "ME-L01", 34: "ME-L02", 35: "ME-L03",
    36: NO_V2 + " for the dedicated electron-collecting target (geometry TBD at P1-G0, P1-IT-36)",
    37: "ME-L05", 38: "ME-L06", 39: "TH-L04", 40: "TH-L07, TH-L08 (window VAC-L07)", 41: "TH-L06",
    42: "TH-L01 (dispatch LATER)",
}


def rfq_v2_check():
    """Every RFQ v2 line / requirement / question id cited by this lane exists in the pinned RFQ v2 JSON."""
    import re
    txt = json.dumps(_load(RFQ2))
    cited = set()
    for v in list(RFQ_V2_MAP.values()) + [x["counterpart"] for x in interface_demands()]:
        cited |= set(re.findall(r"\b(?:RF|GAS|VAC|HE|ME|TH)-[LO]\d\d\b|\bRFQ2-[A-Z]+-[RN]\d\d\b|\bOQ-RFQV2-\d\d\b", v))
    missing = sorted(c for c in cited if '"%s"' % c not in txt)
    if missing:
        raise SystemExit("RFQ v2 ids cited but absent from %s: %s" % (RFQ2, missing))
    return sorted(cited)


def p2_check():
    """Every P2 preparation id cited by this lane exists in the merged P2 JSON (not pinned: same follow-on lane)."""
    import re
    txt = json.dumps(_load(P2_JSON))
    body = json.dumps({"items": items(arithmetic()), "stages": stages(), "meas": _measurements(),
                       "run": run_matrix(arithmetic()), "hw": readiness(), "if": interface_demands()})
    cited = set(re.findall(r"\b(?:IDP2-\d\d|INS-P2-\d\d|CAL-P2-\d\d|HM-[FR]\d\d|UB-P2-Z-\d\d|ZM-[ABC]|"
                           r"RP-(?:ANT|CPL|MIN|VI|GEN))\b", body))
    missing = sorted(c for c in cited if '"%s"' % c not in txt)
    if missing:
        raise SystemExit("P2 ids cited but absent from %s: %s" % (P2_JSON, missing))
    return sorted(cited)


def readiness():
    fam = {
        "RF": [("13.56 MHz laboratory generator (mains, GROUND/FACILITY_ONLY)", "RFQ-04", "A9H-INS-01; H3-A902-01"),
               ("directional coupler + forward/reflected sensors", "RFQ-04", "A9H-INS-01, A9H-INS-16"),
               ("adjustable LOCAL matching network on / adjacent to the ICP module", "RFQ-04",
                "A9H-RF-LM-01; ICD ICP-13"),
               ("50-ohm RF coax and vacuum RF feedthrough", "RFQ-04", "A9H-INS-15; ICD ICP-15"),
               ("dummy load + calorimetric cross-check load", "RFQ-04", "A9H-INS-02"),
               ("RF protection / interlocks", "RFQ-04", "A9H-RF-PROT-01; ICD ICP-16"),
               ("VNA / two-port characterization set", "RFQ-04", "A9H-INS-03; P2 INS-P2-04 / CAL-P2-01"),
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
                                       ("P1-S4 / P1-S7 dedicated electron-collecting target (OWNER_DECIDED for "
                                        "ICP45_CAPACITY records, A9.4 P1Q-10): isolated plate, support, position datum "
                                        "and feedthrough", "none (not in "
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
                        "rfq_v2_package": RFQ_V2_MAP[n] + " (" + RFQ2 + ")", "h2_or_h1_items": h2,
                        "status": "NOT_PROCURED "
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
        {"id": "IF-P1-01", "direction": "to", "counterpart": "P2 " + P2_JSON + " IDP2-01 (gate S-10, HM-R01)", "what": "stable ICP operating region "
         "handoff (region bounds in P_fwd, mdot, p, V_collector; match settings; dwell metrics; cold Z)",
         "units": "W, mg/s, Pa, V, ohm", "status": "OFFERED (after P1-S5)"},
        {"id": "IF-P1-02", "direction": "from", "counterpart": "P2 " + P2_JSON + " IDP2-03 (ZM-A/B/C, CAL-P2-01..15)",
         "what": "V/I sensing, coupler "
         "chain calibration, S-parameter / de-embedding method and data model for the Z_ICP factor",
         "units": "ohm, -", "status": "DEFINED as method in the merged P2 preparation package; the P2 instruments are "
         "not procured, so Z_ICP stays NOT_MEASURED_PENDING_P2_CHAIN"},
        {"id": "IF-P1-03", "direction": "to", "counterpart": "RFQ v2 " + RFQ2, "what": "P1 readiness items "
         "per A9.3 family (hardware_readiness)", "units": "-", "status": "MAPPED (hardware_readiness.rfq_v2_package "
         "names the RFQ v2 line ids or states that no line exists)"},
        {"id": "IF-P1-04", "direction": "from", "counterpart": "RFQ v2 " + RFQ2, "what": "package / line ids "
         "(CONSUMED) and quoted datasheet values (ratings, calibration scope)", "units": "-", "status": "line ids "
         "CONSUMED; quoted values PENDING quotations (none received; no supplier contact by this lane)"},
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
        {"id": "IF-P1-23", "direction": "to", "counterpart": "P2 " + P2_JSON + " IDP2-17 / HM-R15", "what": "photodiode (INS-P2-10) "
         "dark/background, RF-powered known-unlit and known-lit P1 records with simultaneous P_refl, antenna current, "
         "collector/current-path response and pressure, from which the P2 unlit threshold is frozen before the P2 map "
         "(A9.4 P2Q-05)", "units": "V, W, A, Pa", "status": "OFFERED (P1-S2, P1-S3..S5)"},
        {"id": "IF-P1-24", "direction": "to", "counterpart": "RFQ v2 " + RFQ2 + " TH-L07, TH-L08, VAC-L07, HE-L04, "
         "VAC-L03", "what": "A9.4 procurement "
         "items: photodiode, optical access / window, amplifier, DAQ channel (P2Q-05); >= 525 V design withstand and "
         "1.05 kV DC / 60 s initial DWV on the ICP body / collector isolation and feedthrough lines (P1Q-14)",
         "units": "V, s", "status": "RECORDED in RFQ v2 (quotation only; the DWV tester itself has no RFQ v2 line)"},
        {"id": "IF-P1-25", "direction": "from", "counterpart": "H-1 registration (A9-01 " + PRE + ")", "what":
         "I_d,max,H1 from the registered H-1 operating envelope and measured H-1 behaviour (never the 8.33 A supply "
         "rating); ICP45 = NOT_EVALUATED until it exists (A9.4 execution_decisions.i_d_max_h1)", "units": "A",
         "status": "PENDING (owner / prereg lane; P1Q-07)"},
        {"id": "IF-P1-26", "direction": "from", "counterpart": "instrumentation / metrology " + MS + " (MS-G-01..03) "
         "and the channel calibration certificates", "what": "u(I_k) components of every current channel of a "
         "capacity record (calibration, zero/offset, resolution, repeatability where applicable, registered RF-pickup "
         "contribution; A9.5 P1Q-15, P1-IT-49) and, where established, the channel correlation for the full covariance "
         "form; the instrument-capability floor I_scale,min (P1-IT-48)", "units": "A, -",
         "status": "REQUIRED before the first ICP45_CAPACITY record (TBD - certificates not yet issued)"},
        {"id": "IF-P1-27", "direction": "to", "counterpart": "A9-04 " + UB, "what": "the owner Kirchhoff closure rule "
         "for ICP-45 capacity points (A9.5 P1Q-15: |R_I| <= 3 u_R and <= 2 % of max(|I_e,collector|, I_scale,min); "
         "NOT_EVALUATED_INSTRUMENT when 3 u_R > 0.02 |I_e,collector|) as the decided form of the UB-N-07 current-path "
         "closure diagnostic for capacity records (no UB file edit by this lane)", "units": "A, -",
         "status": "OFFERED (owner-decided rule)"},
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
        ("A9.3 OQ-RFQ-07", "decision", "readiness mapped to the six package families and to the RFQ v2 line ids "
         "(hardware_readiness.rfq_v2_package; items with no RFQ v2 line are stated as such); no supplier "
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
         "only as DIAGNOSTIC_VARIANT; Kirchhoff closure incl. h1_body under the owner rule of A9.5 (P1-IT-47, P1-D-13); "
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
        ("A9.5 P1Q-15", A95 + " decisions.P1Q-15 (OWNER_DECIDED - KIRCHHOFF_CLOSURE_RULE); verbatim " + A95_MD,
         "ANSWERED (also this lane's former P1Q-15 on the closure tolerance / sign convention): P1-IT-47 OWNER_DECIDED; "
         "global convention KIRCHHOFF_SIGN_CONVENTION (conventional current INTO the defined isolated network "
         "positive) with a registered convention id shared by every channel and every paired record (PR #34 check "
         "kept); R_I = sum_k I_k over every terminal incl. any other intentional terminal; floating anode I = 0 by "
         "construction with V_anode recorded; NOT_MEASURED terminals never zero (point excluded: intentional return "
         "path unmeasured); u(I_k) components required (P1-IT-49), independent and full-covariance u_R (P1-D-14); "
         "admission |R_I| <= 3 u_R AND |R_I| / max(|I_e,collector|, I_scale,min) <= 0.02 with 3 and 0.02 hard-coded "
         "owner constants (a closure_rule that tries to set them is refused) and I_scale,min a registered input "
         "(P1-IT-48); NOT_EVALUATED_INSTRUMENT per point (P1-IT-50; precedence P1Q-22); exclusions with reasons "
         "(P1-IT-51; unintended-ground-path field defined): a registered pair that is not matched and a non-floating "
         "anode in a capacity record are per-point exclusions that keep their reasons (never an abort of the "
         "reduction; anode precedence over A9.4 P1Q-13 in P1Q-21), and every terminal declared NOT_MEASURED is "
         "excluded uniformly; the earlier residual_rel_tol rule removed; P1Q-15 removed from the open list"),
        ("A9.5 P1Q-16", A95 + " decisions.P1Q-16 (OWNER_CONFIRMED - CAPACITY_FORMULA)",
         "ANSWERED: I_e,cap = I_e,collector,RFON - I_e,collector,RFOFF confirmed (P1-IT-38); signed currents, no "
         "absolute-value correction, no zero-clipping (p1_reducer.i_e_cap_signed; a negative value stays negative and "
         "is flagged I_E_CAP_NEGATIVE); Hall-ON stays NEUTRALIZATION_CONSISTENCY; eligibility conditions (1)-(4) "
         "reported per point; ICP45 = NOT_EVALUATED until all four exist (a margin-rule u_I_e_A / u_I_d_max_A that is "
         "absent, None or 0 gives NOT_EVALUATED with condition 3 false, never a raise); the margin rule's "
         "preregistered u_I_e_A is "
         "kept as the I_e,cap uncertainty used in M_n and the channel-propagated value is reported beside it (P1-D-15, "
         "P1Q-19); P1Q-16 removed from the open list"),
        ("A9.5 execution", A95 + " execution", "carried A9.4 minors fixed: P1-S4 collector wording OWNER_DECIDED "
         "(A9.4 P1Q-10) instead of PROPOSED (also P1-IT-36, P1-IT-42, P1-IT-40 and the readiness row); the stale "
         "PENDING references to the RFQ v2 and P2 preparation paths are replaced by the merged RFQ v2 line ids and P2 "
         "ids (checked at build time); no merge to main is implied"),
        ("A9.6 sec. 2", A96 + " summary.p1q15_denominator / p1q16; verbatim " + A96_MD + " sec. 2",
         "APPLIED: denominator max(|I_e,collector|, I_scale,min) and instrument adequacy 3 u_R <= 0.02 |I_e,collector| "
         "(magnitudes of the signed collector current; p1_reducer.kirchhoff_closure); I_e,cap signed, no abs / "
         "clipping / replacement of a negative result / Hall-ON capacity evidence (unchanged, re-tested)"),
        ("A9.6 sec. 5-7", A96_MD + " sec. 5-7", "APPLIED: P1Q-19 ext, P1Q-21, P1Q-22, P1Q-23(a)/(b) settled as DERIVED "
         "(derived_resolutions, each with the rule it follows from); P1Q-19 remaining choice kept TBD_OWNER with both "
         "admissible treatments computed (P1-IT-57, P1-D-19); fixed statuses carried (a9_2_statuses_carried_unchanged)"),
        ("A9.6 sec. 8", A96_MD + " sec. 8", "APPLIED: complete P1 workflow P1-W01..P1-W10 (a9_6_incorporation.workflow) "
         "with entry / exit criteria, record templates, required channels and reducers; campaign driver "
         "p1_campaign.run_campaign + CLI p1_campaign_cli.py; report schema " + OUT_REPORT_SCHEMA + "; raw records and "
         "exclusion reasons preserved verbatim"),
        ("A9.6 sec. 14", A96_MD + " sec. 14", "APPLIED: fail-closed audit bullet by bullet with one explicit test each "
         "(a9_6_incorporation.fail_closed_audit); OUT_OF_DOMAIN outcome added, never counted as FAIL"),
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
        {"id": "P1Q-17", "question": "Register the later acceptance / reverification level and procedure for the ICP "
         "body / collector insulation (A9.4 P1Q-14: 'an appropriately lower controlled level/procedure'; P1-IT-45)?",
         "proposed_answer": "owner call; PROPOSED: a controlled DC level of about 2 x the 350 V nominal class, per the "
         "owner-stated ECSS guidance quoted in A9.4 (standard and clause not identified - verify), with the procedure "
         "frozen before any reverification", "needed_by": "before any reverification after the initial DWV"},
        {"id": "P1Q-18", "question": "A9.5 P1Q-15 applies the instrument-adequacy rule (3 u_R > 0.02 |I_e,collector| -> "
         "NOT_EVALUATED_INSTRUMENT) 'at a candidate qualification point'. Recorder reading implemented: it is tested on "
         "the RF-ON ICP45_CAPACITY record (the candidate point); the matched RF-OFF record, whose collector current is "
         "the facility/background term and may be near zero, is tested only with the statistical and fractional "
         "closure using the I_scale,min floor. Confirm?", "proposed_answer": "YES (otherwise every RF-OFF record with "
         "I_e,collector ~ 0 would be NOT_EVALUATED_INSTRUMENT by construction, which the I_scale,min floor exists to "
         "avoid)", "needed_by": "before the first ICP45_CAPACITY record (P1-G0)"},
        {"id": "P1Q-19", "status": "TBD_OWNER", "question": "(Remaining genuine choice; the 'zero = not available' "
         "part and the rule that a registered u_I_e_A below the GUM channel propagation is never used as it stands are "
         "now DERIVED, see derived_resolutions.) When the registered u_I_e_A is below the channel-propagated "
         "u(I_e,cap)_channels, should the preregistration be REQUIRE_REGISTERED_GE_CHANNEL (registration inadmissible "
         "-> NOT_EVALUATED) or USE_LARGER_OF_REGISTERED_AND_CHANNEL? Both are computed side by side (P1-D-19); ICP45 "
         "= NOT_EVALUATED while they disagree.", "proposed_answer": "owner call; PROPOSED: "
         "REQUIRE_REGISTERED_GE_CHANNEL (the preregistration then carries a self-consistent value, frozen before the "
         "first P1-S7 point)", "needed_by": "P1-S7 entry"},
        {"id": "P1Q-20", "status": "TBD_OWNER", "question": "A9.5 states I_anode ~ 0 'by construction'. The reducer gives every "
         "OPEN_CIRCUIT_BY_CONSTRUCTION terminal (floating anode, open ICP body) I = 0 and u = 0. Should the insulation "
         "leakage recorded in the P1-S0 isolation / DWV test (P1-IT-44) be entered as a registered u(I_anode) "
         "instead of 0?", "proposed_answer": "owner call; PROPOSED: YES when the recorded leakage at the operating "
         "potential is not negligible against u_R; register it as a u_zero_offset_A of the anode terminal",
         "needed_by": "before the first ICP45_CAPACITY record (P1-G0)"},
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
         "(superseded by A9.2 / A9.3; v2 = " + RFQ2 + ")"),
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
         "quantities; P2 preparation package merged (ZM-A/B/C, CAL-P2-01..15), its instruments not procured"},
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
                               "Kirchhoff closure rule inputs registered before the first ICP45_CAPACITY record: "
                               "sign-convention id, I_scale,min, u(I_k) of every channel, optional channel "
                               "correlation (A9.5 P1Q-15; P1-IT-47..49); unintended-ground-path check recorded per "
                               "capacity record (P1-IT-51)",
                               "run-matrix structure F1..F8", "record schema " + REL + "/" + OUT_SCHEMA,
                               "reducer " + REL + "/p1_reducer.py",
                               "campaign driver " + REL + "/p1_campaign.py (CLI p1_campaign_cli.py; report schema "
                               + OUT_REPORT_SCHEMA + "): one bundle per campaign with the P1-G0 registrations"]}


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


def a9_5_incorporation():
    a95 = _load(A95)
    for q in ("P1Q-15", "P1Q-16"):
        if q not in a95["decisions"]:
            raise SystemExit("A9.5 decision %s missing" % q)
    red = _reducer()
    if (red.CLOSURE_K_SIGMA, red.CLOSURE_FRACTION_MAX) != (3.0, 0.02):
        raise SystemExit("reducer owner constants differ from A9.5 P1Q-15")
    return {"follow_on": "fo_a9_5_closure_rule", "trigger": "T_A9_5_CLOSURE_RULE", "base_commit": A95_INC_BASE,
            "decision": {"path": A95, "sha256": [x for x in PINS if x[0] == A95][0][1]},
            "verbatim": {"path": A95_MD, "sha256": [x for x in PINS if x[0] == A95_MD][0][1]},
            "rule": "applied exactly (no redesign): only what A9.5 decides changed; ids and verified behaviour kept",
            "answered": {q: a95["decisions"][q]["status"] for q in ("P1Q-15", "P1Q-16")},
            "items_changed": ["P1-IT-36", "P1-IT-38", "P1-IT-40", "P1-IT-42", "P1-IT-47"],
            "review_repair": "adversarial review round 1: pairing mismatch and non-floating anode made per-point "
                             "exclusions with reasons; NOT_MEASURED terminals excluded uniformly; missing / zero "
                             "margin-rule uncertainties -> NOT_EVALUATED (condition 3); instrument-inadequacy "
                             "precedence; lane-choice uncertainty combinations labelled; new owner questions "
                             "P1Q-21..P1Q-23",
            "items_added": ["P1-IT-48", "P1-IT-49", "P1-IT-50", "P1-IT-51"],
            "derived_added": ["P1-D-14", "P1-D-15"],
            "reducer": {"owner_constants": {"CLOSURE_K_SIGMA": red.CLOSURE_K_SIGMA,
                                            "CLOSURE_FRACTION_MAX": red.CLOSURE_FRACTION_MAX},
                        "sign_convention": red.KIRCHHOFF_SIGN_CONVENTION,
                        "closure_rule_inputs": list(red.CLOSURE_RULE_ALLOWED),
                        "channel_uncertainty_components": list(red.U_COMPONENTS),
                        "explicit_absent_tokens": dict(red.U_EXPLICIT_ABSENT),
                        "terminal_bases": list(red.TERMINAL_BASES),
                        "point_outcomes": list(red.POINT_OUTCOMES),
                        "icp45_statuses": list(red.ICP45A_STATUSES),
                        "removed": "closure_rule.residual_rel_tol (the earlier registered free tolerance)"},
            "carried_a9_4_minors_fixed": ["P1-S4 collector wording OWNER_DECIDED (A9.4 P1Q-10)",
                                          "stale PENDING RFQ v2 / P2 references replaced by merged ids"],
            "execution_note": a95["execution"]["merge"],
            "m16_impact_change": "none: A9.5 changes no M16 v3 row state (ICP electron-current capacity stays "
                                 "PENDING_ICP45; ICP45 = NOT_EVALUATED)"}


FAIL_CLOSED_TESTS = [
    ("missing required data -> no PASS",
     "a record missing any required field is REFUSED_INVALID_RECORD with the reducer's error text verbatim; a missing "
     "registration gives NOT_EVALUATED / NOT_EVALUATED_REGISTRATION; the report self-check refuses any 'PASS' value",
     "p1_campaign._validate / run_campaign._walk_no_pass; p1_reducer._req",
     "test_a96_sec14_missing_required_data_no_pass"),
    ("mismatched sign convention -> excluded",
     "a channel or record sign_convention_id different from the registered closure-rule convention excludes the "
     "capacity point with the reason (A9.5 P1Q-15); a collector I_e_sign_convention other than the declared one "
     "refuses the record (REFUSED_INVALID_RECORD, kept verbatim)",
     "p1_reducer.kirchhoff_closure; validate_operating_point", "test_a96_sec14_sign_convention_mismatch_excluded"),
    ("missing current path -> excluded",
     "a terminal declared NOT_MEASURED, I_body->ground not continuous, or a required terminal absent: the point is "
     "EXCLUDED (declared) or the record REFUSED (absent) - never summed as zero",
     "p1_reducer.capacity_structural_reasons; _check_capacity_record", "test_a96_sec14_missing_current_path_excluded"),
    ("mixed synthetic/measured -> refused",
     "a bundle whose records contradict the manifest evidence_kind raises MixedEvidenceError (no report); inside a "
     "reduction, a synthetic / measured pair is excluded and mixed candidates raise (PR #34)",
     "p1_campaign.run_campaign (MixedEvidenceError); p1_reducer.icp45a_candidates / icp45a_evaluate",
     "test_a96_sec14_mixed_evidence_refused"),
    ("invalid RF-ON/RF-OFF pair -> excluded",
     "a registered pair that is not matched (field differences, pressure outside the registered tolerance, RF-OFF "
     "P_fwd != 0), whose partner is refused / out of domain, or without a registered match rule excludes (or, out of "
     "domain, OUT_OF_DOMAIN) the capacity point with every reason",
     "p1_reducer.facility_pair_mismatches; p1_campaign pair handling", "test_a96_sec14_invalid_pair_excluded"),
    ("unknown I_d,max,H1 -> NOT_EVALUATED",
     "no registration (or no margin rule): ICP45 status NOT_EVALUATED and each capacity point NOT_EVALUATED_REGISTRATION "
     "(or its closure outcome without an ICP-45 evaluation)", "p1_reducer.icp45a_evaluate; p1_campaign.run_campaign",
     "test_a96_sec14_unknown_i_d_max_not_evaluated"),
    ("missing uncertainty -> NOT_EVALUATED",
     "a missing / zero u(I_k) component gives the point outcome NOT_EVALUATED_UNCERTAINTY; a missing / zero margin-rule "
     "uncertainty gives ICP45 = NOT_EVALUATED (condition 3); a zero cross-check or loss uncertainty refuses the record",
     "p1_reducer._channel_uncertainty / _check_registration / _pos", "test_a96_sec14_missing_uncertainty_not_evaluated"),
    ("unresolved plasma state -> UNCERTAIN",
     "optical record with lost line of sight, saturation, no registered threshold, optical-unlit with electrical "
     "evidence, or lit without E/H assignment -> UNCERTAIN; an incomplete optical object refuses the record",
     "p1_reducer.classify_plasma_state", "test_a96_sec14_unresolved_plasma_state_uncertain"),
    ("unverified line loss -> no silently reconstructed plasma power",
     "in the campaign a MEASURED loss that is not a verified P1-S1/S2 characterization under CROSS_CHECK_AGREES gives "
     "P_RF_DELIVERED_UPPER_BOUND_LOSS_UNVERIFIED (flagged); a failed cross-check gives EXCLUDED_INSTRUMENT (no "
     "P_delivered, no C_e); P_fwd is never P_plasma", "p1_reducer.derive_rf(loss_verification)",
     "test_a96_sec14_unverified_loss_no_reconstructed_power"),
    ("OUT_OF_DOMAIN remains distinct from FAIL",
     "a record of an unregistered stage, outside its registered operating domain, or taken before P1-G0 is met is "
     "OUT_OF_DOMAIN (disposition, point outcome, consistency row status) - never EXCLUDED as a failure and never FAIL",
     "p1_campaign._domain_reasons; POINT_OUTCOMES", "test_a96_sec14_out_of_domain_not_fail"),
]

GAP_AUDIT = [
    ("G-01", "sec. 8 P1-G0", "P1-S0 existed only as a stage description: no record template or reducer for the "
     "interlocks, the 1.05 kV / 60 s DWV, the ICPQ-06 gas-line rule or the Ar MFC rule",
     "record kind p1_g0_readiness + p1_reducer.reduce_readiness (G0_STATUSES; never PASS)"),
    ("G-02", "sec. 8 RF cold checkout", "no P1-S1 / P1-S2 record or reducer; the UB-RF-08 calorimetric cross-check "
     "was not computed; a MEASURED line/match loss was accepted without a verified characterization",
     "record kind rf_cold_checkout + reduce_rf_cold_checkout (z_x, RF_CHAIN_STATUSES, verified loss ids)"),
    ("G-03", "sec. 8 ICP ignition", "no ignition record; ignition repeatability entered only as a free dict",
     "record kind ignition_attempt + reduce_ignition (per-point success fraction P1-D-09)"),
    ("G-04", "sec. 5 / 14 photodiode", "the optical channel P1-M-28 was not part of any P1 record; no UNCERTAIN state",
     "classify_plasma_state (A9.4 P2Q-05 classes); required on ignition and installed-antenna records, optional on "
     "operating points; surface column plasma_state"),
    ("G-05", "sec. 8 stable region", "dwells were ad hoc bundle entries; no P2 handoff record",
     "record kind stability_dwell + stable_region_handoff (IF-P1-01 -> IDP2-01)"),
    ("G-06", "sec. 8 Hall-ON consistency after capacity", "consistency rows were produced without checking that "
     "capacity had been shown at the same registered point", "campaign entry rule; rows otherwise OUT_OF_DOMAIN"),
    ("G-07", "sec. 8 raw data schemas", "no campaign driver or report schema; the bundle reducer aborted on the first "
     "invalid record, so a raw record could be absent from any result",
     "p1_campaign.run_campaign + p1_campaign_cli.py + " + OUT_REPORT_SCHEMA + " (raw records verbatim, disposition "
     "and reasons for each)"),
    ("G-08", "sec. 2", "denominator and instrument adequacy used the signed I_e,collector",
     "max(|I_e,collector|, I_scale,min); 3 u_R <= 0.02 |I_e,collector|"),
    ("G-09", "sec. 14 missing uncertainty", "a missing u(I_k) excluded the point (EXCLUDED) instead of NOT_EVALUATED",
     "point outcome NOT_EVALUATED_UNCERTAINTY"),
    ("G-10", "sec. 14 OUT_OF_DOMAIN", "no OUT_OF_DOMAIN outcome and no registered operating domain",
     "registrations.operating_domains (P1-IT-52); disposition / point outcome / row status OUT_OF_DOMAIN"),
    ("G-11", "sec. 14 mixed evidence", "mixed synthetic / measured refused only when capacity candidates mixed",
     "bundle-level refusal (P1-IT-53, MixedEvidenceError)"),
    ("G-12", "sec. 6-7", "P1Q-19 (ext), P1Q-21, P1Q-22, P1Q-23 open although derivable",
     "derived_resolutions (DERIVED with the rule followed); P1Q-19 remaining choice TBD_OWNER with both treatments"),
    ("G-13", "sec. 2 / 14", "instrument inadequacy masked a statistically significant closure failure "
     "(|R_I| > 3 u_R)", "DERIVED precedence (P1Q-22): statistical failure -> EXCLUDED"),
    ("G-14", "sec. 8 topology control", "outputs did not say explicitly that the observation is not a gate",
     "campaign rows carry gate = false, scoring = false"),
    ("G-15", "sec. 8 raw data schemas", "record schema covered only operating points and topology sequences",
     "schema $defs for all six record kinds (" + OUT_SCHEMA + ")"),
]


def derived_resolutions():
    red = _reducer()
    return [
        {"id": "P1Q-19 (ext)", "disposition": "DERIVED",
         "answer": "a registered standard uncertainty of zero (u_I_e_A, u_I_d_max_A, u_P_cal_W, u_P_coupler_W, "
                   "u_value_W, u_resolution_A) is treated as not available: ICP45 = NOT_EVALUATED (margin rule) or the "
                   "record is refused (stage records)",
         "follows_from": "JCGM 100:2008 F.2.2.1 (even identical repeated indications leave a non-zero resolution "
                         "uncertainty); A9.5 P1Q-16 condition (3) 'all required uncertainties are available'",
         "implemented_in": "p1_reducer._check_registration, _channel_uncertainty, _pos",
         "tests": ["test_a95_eligibility_conditions", "test_a96_sec14_missing_uncertainty_not_evaluated"]},
        {"id": "P1Q-19 (below propagation)", "disposition": "DERIVED",
         "answer": "a registered u_I_e_A below the GUM propagation of its own collector-channel uncertainties is never "
                   "used as it stands (flag REGISTERED_u_I_e_BELOW_CHANNEL_PROPAGATION)",
         "follows_from": "JCGM 100:2008 5.1.2 Eq. (10) / 5.2.2 Eq. (13): the combined standard uncertainty of "
                         "I_on - I_off is fixed by its input uncertainties (and their registered correlation)",
         "implemented_in": "p1_reducer._p1q19_alternatives", "tests": ["test_a96_p1q19_alternatives_side_by_side"]},
        {"id": "P1Q-19 (require vs use larger)", "disposition": "TBD_OWNER",
         "answer": "both admissible treatments %s computed side by side; ICP45 = NOT_EVALUATED while they disagree"
                   % list(red.P1Q19_ALTERNATIVES),
         "follows_from": A96_MD + " sec. 7 (a genuine preregistration design choice is not answered by the lane)",
         "implemented_in": "p1_reducer.icp45a_evaluate", "tests": ["test_a96_p1q19_alternatives_side_by_side"]},
        {"id": "P1Q-21", "disposition": "DERIVED",
         "answer": "an ICP45_CAPACITY record whose H-1 anode is not physically disconnected / floating is an EXCLUDED "
                   "capacity point kept with its reason (the other points are still evaluated); non-capacity records "
                   "keep the A9.4 refusal of an OFF supply left connected",
         "follows_from": A95 + " decisions.P1Q-15.exclusions (the later owner addendum lists the case as an exclusion "
                         "whose point 'remains in the raw record'; A9.5 parents include A9.4)",
         "implemented_in": "p1_reducer.validate_operating_point / capacity_structural_reasons",
         "tests": ["test_a95_anode_not_floating_is_excluded_not_aborting"]},
        {"id": "P1Q-22", "disposition": "DERIVED",
         "answer": red.PRECEDENCE_NOTE,
         "follows_from": "A9.5 P1Q-15 exclusions '|R_I| > 3 u_R' and 'fractional closure exceeds 2 %' plus the "
                         "adequacy rule: the statistical test is normalised to the instrument's own u_R, so a "
                         "statistically significant residual is resolved by the instrument and stays an exclusion; "
                         "only the 2 % test is unresolvable when 3 u_R > 0.02 |I_e,collector| (A9.6 sec. 2: "
                         "NOT_EVALUATED_INSTRUMENT 'rather than widening the tolerance'); A9.6 sec. 14 missing "
                         "uncertainty -> NOT_EVALUATED",
         "implemented_in": "p1_reducer.icp45a_candidates",
         "tests": ["test_a95_instrument_inadequacy_precedence", "test_a95_statistical_fail"]},
        {"id": "P1Q-23 (a)", "disposition": "DERIVED",
         "answer": "u(I_k) = root-sum-square of its registered components (calibration, zero/offset, resolution, "
                   "repeatability where applicable, registered RF pickup)",
         "follows_from": "JCGM 100:2008 5.1.2 Eq. (10) with sensitivity 1 for each independent component",
         "implemented_in": "p1_reducer._channel_uncertainty", "tests": ["test_a95_closure_rule_constants_not_parameters"]},
        {"id": "P1Q-23 (b)", "disposition": "DERIVED",
         "answer": "u(I_e,cap)_channels = sqrt(u_on^2 + u_off^2 - 2 r u_on u_off) with a registered RF-ON / RF-OFF "
                   "correlation r (margin_rule.rf_on_off_collector_correlation, P1-IT-56); without one r = 0 is "
                   "reported as an ASSUMPTION in the basis text",
         "follows_from": "JCGM 100:2008 5.2.2 Eq. (13)-(15) (sensitivities +1 / -1); 5.2.1 (significant correlations "
                         "must be taken into account)",
         "implemented_in": "p1_reducer.u_i_e_cap_channels", "tests": ["test_a96_p1q23_correlated_form"]},
    ]


def a9_6_incorporation():
    a96 = _load(A96)
    if "fo_a9_6_p1_workflow_completion" not in a96["implementation_lanes"]:
        raise SystemExit("A9.6 lane fo_a9_6_p1_workflow_completion missing from the directive")
    camp = _campaign()
    red = _reducer()
    return {"follow_on": "fo_a9_6_p1_workflow_completion", "trigger": "A9.6 wave 2 (lane A9_6_P1C)",
            "base_commit": A96_INC_BASE,
            "decision": {"path": A96, "sha256": [x for x in PINS if x[0] == A96][0][1]},
            "verbatim": {"path": A96_MD, "sha256": [x for x in PINS if x[0] == A96_MD][0][1]},
            "lane_scope": a96["implementation_lanes"]["fo_a9_6_p1_workflow_completion"],
            "gap_audit": [{"id": g[0], "a9_6_requirement": g[1], "gap_at_base": g[2], "closure": g[3],
                           "state": "CLOSED_IN_IMPLEMENTATION (formal verification deferred to the A9.6 sec. 18 "
                                    "campaign)"} for g in GAP_AUDIT],
            "workflow": camp.WORKFLOW,
            "campaign_driver": {"module": REL + "/p1_campaign.py (pure: run_campaign)",
                                "cli": REL + "/p1_campaign_cli.py", "report_schema": REL + "/" + OUT_REPORT_SCHEMA,
                                "bundle_schema": camp.BUNDLE_SCHEMA, "report_schema_id": camp.REPORT_SCHEMA,
                                "registration_keys": list(camp.REGISTRATION_KEYS),
                                "registration_nullable": list(camp.REGISTRATION_NULLABLE),
                                "dispositions": list(camp.DISPOSITIONS),
                                "point_outcomes": list(red.POINT_OUTCOMES)},
            "fail_closed_audit": [{"n": i + 1, "a9_6_sec14_bullet": b, "implementation": imp, "where": w,
                                   "test": "tests/test_p1_icp_bench.py::" + t}
                                  for i, (b, imp, w, t) in enumerate(FAIL_CLOSED_TESTS)],
            "derived_resolutions": derived_resolutions(),
            "external_reference": GUM,
            "fixed_statuses": a96["summary"]["fixed_statuses"],
            "not_done_here": ["no measured data exist; every numeric registration (domains, thresholds, criteria, "
                              "I_scale,min, I_d,max,H1, leakage acceptance, correlation) stays TBD",
                              "P1 hardware readiness, RF ratings, thermal and anode closures unchanged "
                              "(TBD_AFTER_IMPEDANCE_MAP / UNRESOLVED / OPEN)",
                              "parallel lanes referenced only by path: PENDING "
                              "docs/experiments/hall_icp/p3_coupled_thermal/, PENDING "
                              "docs/experiments/hall_icp/p4_anode_materials/"],
            "m16_impact_change": "none: software workflow only; ICP electron-current capacity stays PENDING_ICP45 and "
                                 "no physical item becomes READY / VERIFIED (A9.6 sec. 16)"}


def build_report_schema():
    camp = _campaign()
    red = _reducer()
    s = {"type": "string"}
    reasons = {"type": "array", "items": s}
    idx = {"type": "object", "required": ["record_id", "record_kind", "stage_id", "disposition", "reasons"],
           "properties": {"record_id": s, "record_kind": {"type": ["string", "null"]},
                          "stage_id": {"type": ["string", "null"]}, "disposition": {"enum": list(camp.DISPOSITIONS)},
                          "reasons": reasons, "error_class": s,
                          "capacity_point_outcome": {"enum": list(red.POINT_OUTCOMES)}}}
    excl = {"type": "object", "required": ["record_id", "source", "outcome", "reasons"],
            "properties": {"record_id": s, "source": {"enum": list(camp.DISPOSITIONS[1:]) + [
                "CAPACITY_POINT", "NEUTRALIZATION_CONSISTENCY_ROW"]},
                "outcome": {"enum": list(camp.DISPOSITIONS[1:]) + list(red.POINT_OUTCOMES)},
                "reasons": reasons, "error_class": {"type": ["string", "null"]}}}
    point = {"type": "object", "required": ["record_id", "outcome", "reasons"],
             "properties": {"record_id": s, "outcome": {"enum": list(red.POINT_OUTCOMES)}, "reasons": reasons}}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": REL + "/" + OUT_REPORT_SCHEMA,
        "title": "P1 ICP bench campaign report (" + camp.REPORT_SCHEMA + ")",
        "description": "Output of " + REL + "/p1_campaign.py run_campaign (generated from its constants by "
                       "build_p1_icp_bench.py). Engineering-only; never PASS; raw records never dropped.",
        "type": "object", "required": list(camp.REPORT_REQUIRED),
        "properties": {
            "schema": {"const": camp.REPORT_SCHEMA}, "campaign_id": s,
            "evidence_kind": {"enum": list(camp.EVIDENCE_KINDS)}, "any_synthetic": {"type": "boolean"},
            "evidence_class": {"const": red.REQUIRED_LABEL}, "input_sha256": {"type": "string", "pattern":
                                                                                "^[0-9a-f]{64}$"},
            "registration_set_id": s, "workflow": {"type": "array"},
            "readiness": {"type": "object", "required": ["g0_status", "records"], "properties": {
                "g0_status": {"enum": list(red.G0_STATUSES) + ["NO_READINESS_RECORD"]}}},
            "rf_cold_checkout": {"type": "object", "required": ["rf_chain_status", "verified_loss_ids"],
                                 "properties": {"rf_chain_status": {"enum": list(red.RF_CHAIN_STATUSES)}}},
            "ignition_map": {"type": "object"}, "surface": {"type": "array"}, "facility_corrections": {"type": "array"},
            "kirchhoff_closures": {"type": "array"},
            "capacity": {"type": "object", "required": ["point_outcomes", "icp45a"],
                         "properties": {"point_outcomes": {"type": "array", "items": point}}},
            "icp45_status": {"type": "object", "required": ["status"],
                             "properties": {"status": {"enum": list(red.ICP45A_STATUSES)}}},
            "stable_region": {"type": "object", "required": ["status"],
                              "properties": {"status": {"enum": list(red.HANDOFF_STATUSES)}}},
            "topology_control": {"type": "array", "items": {"type": "object", "required": ["gate", "scoring"],
                                                            "properties": {"gate": {"const": False},
                                                                           "scoring": {"const": False}}}},
            "neutralization_consistency": {"type": "array", "items": {
                "type": "object", "required": ["row_status"],
                "properties": {"row_status": {"enum": list(camp.CONSISTENCY_ROW_STATUSES)}}}},
            "excluded_records": {"type": "array", "items": excl},
            "raw_record_index": {"type": "array", "items": idx},
            "raw_records": {"type": "array", "description": "every raw record of the bundle, verbatim"},
            "statements": {"type": "array", "items": s},
        },
        "$defs": {"campaign_bundle": {
            "type": "object", "required": ["schema", "manifest", "registrations", "records"],
            "properties": {"schema": {"const": camp.BUNDLE_SCHEMA},
                           "manifest": {"type": "object", "required": list(camp.MANIFEST_REQUIRED),
                                        "properties": {"evidence_kind": {"enum": list(camp.EVIDENCE_KINDS)}}},
                           "registrations": {"type": "object", "required": list(camp.REGISTRATION_KEYS),
                                             "additionalProperties": False,
                                             "x-nullable": list(camp.REGISTRATION_NULLABLE),
                                             "properties": {k: {} for k in camp.REGISTRATION_KEYS}},
                           "records": {"type": "array", "items": {"$ref": OUT_SCHEMA}}},
            "x-operating-domain-factors": sorted(camp.DOMAIN_FACTORS)}},
    }


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
        "campaign_driver": REL + "/p1_campaign.py",
        "campaign_cli": REL + "/p1_campaign_cli.py",
        "campaign_report_schema": REL + "/" + OUT_REPORT_SCHEMA,
        "test": "tests/test_p1_icp_bench.py",
        "what_it_is_not": ["not a prediction (no Hall closure admitted; abep_sim/plasma_devices.py superseded; "
                           "v1.2-v1.6 numbers withdrawn)", "not a score-bearing campaign (every record "
                           "ENGINEERING_ONLY_NON_SCORING)", "not a verdict on the architecture and never a winner",
                           "not a procurement action (no purchase order, no supplier contact)"],
        "authority_pins": [{"path": p, "sha256": s, "role": w} for p, s, w in PINS],
        "governance_files_not_pinned": GOVERNANCE_NOT_PINNED,
        "a9_4_incorporation": a9_4_incorporation(),
        "a9_5_incorporation": a9_5_incorporation(),
        "a9_6_incorporation": a9_6_incorporation(),
        "merged_cross_references": [
            {"lane": "fo_a9_p2_impedance_prep", "path": P2_JSON, "state": "MERGED",
             "how": "P2 ids cited here are checked to exist at build time (not sha-pinned: same follow-on lane, "
                    "regenerated together)", "ids_cited": p2_check()},
            {"lane": "fo_a9_rfq_v2_split", "path": RFQ2, "state": "MERGED",
             "how": "sha256-pinned; every cited line / requirement / question id is checked to exist",
             "ids_cited": rfq_v2_check()}],
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
        "compliance": ["no performance prediction; no invented thresholds (TBD / PROPOSED / owner-given only; the "
                       "closure factor 3 and the 2 % are A9.5 owner values)",
                       "no Julia; no archengine wiring; no change outside " + REL + "/ and tests/test_p1_icp_bench.py",
                       "immutable inputs pinned by sha256; governance files read but never pinned",
                       "no supplier / author / lab contact; published sources only",
                       "never PASS for ICP thermal, RF ratings or anode items",
                       "A9.6 sec. 14 fail-closed reducers: one explicit test per bullet (a9_6_incorporation."
                       "fail_closed_audit); OUT_OF_DOMAIN never counted as FAIL",
                       "genuine owner choices stay TBD_OWNER (P1Q-19 remaining part, P1Q-20 and the other open "
                       "questions); derived rules cite the decision or the published standard they follow from"],
    }
    return doc


# ------------------------------------------------------------------------------------------------ schema
def _optical_def(red):
    return {"type": "object", "required": list(red.OPTICAL_REQUIRED) + ["unlit_threshold"],
            "description": "photodiode channel (P1-M-28; A9.4 P2Q-05): classified by p1_reducer.classify_plasma_state "
                           "into " + " / ".join(red.PLASMA_STATES) + "; unlit_threshold null until registered "
                           "(P1-IT-54) -> UNCERTAIN",
            "properties": {"photodiode_channel_id": {"type": "string", "minLength": 1},
                           "optical_signal_V": {"type": "number"},
                           "photodiode_line_of_sight_ok": {"type": "boolean"},
                           "photodiode_saturated": {"type": "boolean"},
                           "electrical_ignition_or_mode_transition": {"type": "boolean"},
                           "electrical_indicator_basis": {"type": "string"},
                           "unlit_threshold": {"anyOf": [{"type": "null"}, {
                               "type": "object", "required": ["threshold_id", "threshold_V"],
                               "properties": {"threshold_id": {"type": "string"}, "threshold_V": {"type": "number"}}}]},
                           "lit_mode_assignment": {"enum": ["E_MODE", "H_MODE", None]},
                           "mode_indicator_basis": {"type": "string"}}}


def _stage_defs(red):
    num = {"type": "number"}
    common = {"schema": {"const": red.SCHEMA_ID}, "record_id": {"type": "string"}, "run_id": {"type": "string"},
              "timestamp_utc": {"type": "string"}, "synthetic": {"type": "boolean"},
              "labels": {"type": "array", "items": {"type": "string"}, "contains": {"const": red.REQUIRED_LABEL}}}
    rf = {"type": "object", "required": ["reference_plane", "P_fwd_W", "P_refl_W", "match_setting_id"],
          "properties": {"reference_plane": {"const": red.RF_REFERENCE_PLANE}, "P_fwd_W": num, "P_refl_W": num,
                         "match_setting_id": {"type": "string"}}}
    upos = {"type": "number", "exclusiveMinimum": 0}
    rd = {"type": "object", "required": list(red.READINESS_REQUIRED), "properties": dict(
        common, record_kind={"const": "p1_g0_readiness"}, stage_id={"const": "P1-S0"},
        interlocks={"type": "array", "items": {"type": "object", "required": ["interlock_id", "functional_test_done",
                                                                              "functional", "log_id"]}},
        isolation_class={"type": "object", "required": ["V_operating_max_V", "V_design_withstand_V"]},
        dwv_tests={"type": "array", "minItems": 1, "items": {"type": "object", "required": ["path_id", "applicable"],
                                                             "properties": {"leakage_acceptance": {"anyOf": [
                                                                 {"type": "null"}, {"type": "object", "required": [
                                                                     "criterion_id", "max_leakage_A"]}]}}}},
        gas_lines={"type": "array", "minItems": 1, "items": {"type": "object", "required": [
            "line_id", "bridges_isolated_potentials", "isolator_installed", "qualification"]}},
        ar_mfcs={"type": "array", "items": {"type": "object", "required": ["mfc_id", "range_min_mg_s",
                                                                           "range_max_mg_s"]}},
        ar_sweep_bounds_mg_s={"anyOf": [{"type": "null"}, {"type": "array", "minItems": 2, "maxItems": 2}]},
        second_mfc_necessity={"type": ["string", "null"]}, generator_class={"enum": list(red.GENERATOR_CLASSES)},
        registrations={"type": "object", "properties": {k: {"type": ["string", "null"]}
                                                        for k in red.READINESS_REGISTRATIONS}}),
        "x-owner-values": {"V_operating_max_V_max": red.ISOLATION_V_OPERATING_MAX_V,
                           "V_design_withstand_V_min": red.ISOLATION_V_DESIGN_WITHSTAND_MIN_V,
                           "dwv_V_test_V_min": red.DWV_V_TEST_V, "dwv_duration_s_min": red.DWV_DURATION_S,
                           "required_interlocks": list(red.READINESS_INTERLOCK_IDS), "source": red.A94_P1Q14}}
    cold = {"type": "object", "required": list(red.COLD_REQUIRED), "properties": dict(
        common, record_kind={"const": "rf_cold_checkout"}, stage_id={"enum": sorted(set(red.COLD_KINDS.values()))},
        checkout_kind={"enum": list(red.COLD_KINDS)}, rf=rf,
        calorimetric_cross_check={"type": "object", "required": list(red.CROSS_CHECK_REQUIRED), "properties": {
            "P_cal_W": num, "u_P_cal_W": upos, "u_P_coupler_W": upos, "method_id": {"type": "string"}}},
        loss_characterization={"anyOf": [{"type": "null"}, {"type": "object", "required": list(red.LOSS_CHAR_REQUIRED),
                                                            "properties": {"method": {"enum": list(
                                                                red.LOSS_CHAR_METHODS)}, "u_value_W": upos}}]},
        optical=_optical_def(red), gas_flow_state={"enum": ["OFF", "FLOWING"]},
        unlit_procedure_id={"type": "string"}, rf_pickup_check={"enum": ["DONE", "NOT_DONE"]}),
        "x-required-by-kind": {"DUMMY_LOAD": ["calorimetric_cross_check"],
                               "INSTALLED_UNLIT_ANTENNA_VIA_LOCAL_MATCH": ["optical", "gas_flow_state",
                                                                           "unlit_procedure_id"]},
        "x-stage-by-kind": dict(red.COLD_KINDS), "x-k_x": red.CROSS_CHECK_K_X}
    ign = {"type": "object", "required": list(red.IGNITION_REQUIRED), "properties": dict(
        common, record_kind={"const": "ignition_attempt"}, stage_id={"const": "P1-S3"}, gas={"enum": list(red.P1_GASES)},
        gas_mode={"enum": list(red.GAS_MODES)}, hall_discharge_state={"const": "OFF"}, rf=rf,
        ignited={"type": "boolean"}, ignition_delay_s={"type": ["number", "null"]}, extinguished={"type": "boolean"},
        optical=_optical_def(red), point_id={"type": "string", "minLength": 1},
        ignition_procedure_id={"type": "string", "minLength": 1}, h1_magnet_state={"type": "string", "minLength": 1})}
    dw = {"type": "object", "required": list(red.DWELL_REQUIRED), "properties": dict(
        common, record_kind={"const": "stability_dwell"}, stage_id={"const": "P1-S5"},
        operating_point_record_id={"type": "string"}, ignition_point_id={"type": "string"},
        dwell={"type": "object", "required": ["t_s", "I_e_A", "P_refl_W"]})}
    return {"p1_g0_readiness": rd, "rf_cold_checkout": cold, "ignition_attempt": ign, "stability_dwell": dw}


def build_schema():
    red = _reducer()
    num = {"type": "number"}
    no_pbus = {"not": {"pattern": "[Bb][^A-Za-z0-9]*[Uu][^A-Za-z0-9]*[Ss]"}}
    unc = {"type": "object", "required": list(red.U_COMPONENTS),
           "description": "u(I_k) components of a MEASURED channel (A9.5 P1Q-15); required on every MEASURED terminal "
                          "of an ICP45_CAPACITY record, else the point cannot be evaluated",
           "properties": {c: ({"anyOf": [{"type": "number", "minimum": 0}, {"const": red.U_EXPLICIT_ABSENT[c]}]}
                              if c in red.U_EXPLICIT_ABSENT else
                              ({"type": "number", "exclusiveMinimum": 0} if c == "u_resolution_A"
                               else {"type": "number", "minimum": 0}))
                          for c in red.U_COMPONENTS}}
    term = {"type": "object", "required": ["basis"],
            "description": "signed terminal current, conventional current INTO the isolated network positive "
                           "(A9.5 P1Q-15); NOT_MEASURED = unavailable, carries no I_A (never a silent zero)",
            "properties": {"I_A": {"type": ["number", "null"]}, "basis": {"enum": list(red.TERMINAL_BASES)},
                           "sign_convention_id": {"type": "string", "minLength": 1}, "uncertainty": unc},
            "x-I_A-required-unless-basis": "NOT_MEASURED"}
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
                                                   "sign_convention_id": {"type": "string", "minLength": 1},
                                                   "unintended_ground_path_found": {"type": "boolean"},
                                                   "ground_path_check_id": {"type": "string", "minLength": 1}}},
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
            "optical": _optical_def(red),
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
        "oneOf": [{"$ref": "#/$defs/" + k} for k in red.RECORD_KINDS],
        "$defs": dict(_stage_defs(red), icp_operating_point=op, topology_control_sequence=seq),
        "x-closure-rule-input": {"required": list(red.CLOSURE_RULE_REQUIRED), "allowed": list(red.CLOSURE_RULE_ALLOWED),
                                 "sign_convention": red.KIRCHHOFF_SIGN_CONVENTION,
                                 "owner_constants": {"k_sigma": red.CLOSURE_K_SIGMA,
                                                     "fraction_max": red.CLOSURE_FRACTION_MAX},
                                 "covariance": {"required": list(red.COVARIANCE_REQUIRED),
                                                "description": "registered correlation r_ij of the listed terminals "
                                                               "(symmetric, unit diagonal, positive semi-definite)"},
                                 "source": red.A95_REF},
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
         "| campaign driver | `%s` (CLI `%s`; report schema `%s`) |" % (doc["campaign_driver"], doc["campaign_cli"],
                                                                     doc["campaign_report_schema"]),
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
    i5 = doc["a9_5_incorporation"]
    L += ["A9.5 closure rule (`%s`, trigger `%s`, base `%s`): %s. Decision `%s` (sha256 `%s`); verbatim `%s` "
          "(sha256 `%s`). Answered: %s. Items changed: %s; added: %s; derived added: %s. Owner constants: %s; sign "
          "convention `%s`; closure_rule inputs: %s; removed: %s. Carried A9.4 minors fixed: %s. Merge: %s. M16: %s."
          % (i5["follow_on"], i5["trigger"], i5["base_commit"], i5["rule"], i5["decision"]["path"],
             i5["decision"]["sha256"], i5["verbatim"]["path"], i5["verbatim"]["sha256"],
             "; ".join("%s = %s" % kv for kv in i5["answered"].items()), ", ".join(i5["items_changed"]),
             ", ".join(i5["items_added"]), ", ".join(i5["derived_added"]),
             json.dumps(i5["reducer"]["owner_constants"]), i5["reducer"]["sign_convention"],
             ", ".join(i5["reducer"]["closure_rule_inputs"]), i5["reducer"]["removed"],
             "; ".join(i5["carried_a9_4_minors_fixed"]), i5["execution_note"], i5["m16_impact_change"]), ""]
    L += ["Point outcomes: %s; ICP-45 statuses: %s." % (", ".join(i5["reducer"]["point_outcomes"]),
                                                         ", ".join(i5["reducer"]["icp45_statuses"])), ""]
    L += ["Merged cross-references:", ""]
    L += ["- `%s` at `%s` (%s): %s; ids cited: %s" % (p["lane"], p["path"], p["state"], p["how"],
                                                     ", ".join(p["ids_cited"]))
          for p in doc["merged_cross_references"]] + [""]
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
    L += _table(doc["open_owner_questions"], [("id", "id"), ("status", "status"), ("question", "question"),
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
    a6 = doc["a9_6_incorporation"]
    L += ["## 19. A9.6 P1 workflow completion (`%s`)" % a6["follow_on"], "",
          "Base `%s`. Decision `%s` (sha256 `%s`); verbatim `%s` (sha256 `%s`). Scope: %s. M16: %s." % (
              a6["base_commit"], a6["decision"]["path"], a6["decision"]["sha256"], a6["verbatim"]["path"],
              a6["verbatim"]["sha256"], a6["lane_scope"], a6["m16_impact_change"]), "",
          "### 19.1 Gap audit against A9.6 sec. 8 / 14 (at the base commit)", ""]
    L += _table(a6["gap_audit"], [("id", "id"), ("A9.6", "a9_6_requirement"), ("gap at base", "gap_at_base"),
                                  ("closure", "closure"), ("state", "state")]) + [""]
    L += ["### 19.2 Workflow stages", ""]
    L += _table([dict(w, template=w["record_template"]["record_kind"] + ": " + ", ".join(
        w["record_template"]["required_fields"])) for w in a6["workflow"]],
        [("id", "id"), ("name", "name"), ("stages", "stage_ids"), ("entry", "entry"), ("exit", "exit"),
         ("record template", "template"), ("required channels", "required_channels"), ("reducer", "reducer")]) + [""]
    cd = a6["campaign_driver"]
    L += ["### 19.3 Campaign driver", "",
          "- module `%s`; CLI `%s`; report schema `%s` (`%s`); bundle `%s`" % (
              cd["module"], cd["cli"], cd["report_schema"], cd["report_schema_id"], cd["bundle_schema"]),
          "- registrations (all keys required; nullable = explicit 'not registered'): %s; nullable: %s" % (
              ", ".join(cd["registration_keys"]), ", ".join(cd["registration_nullable"])),
          "- record dispositions: %s; capacity point outcomes: %s" % (", ".join(cd["dispositions"]),
                                                                     ", ".join(cd["point_outcomes"])), ""]
    L += ["### 19.4 Fail-closed audit (A9.6 sec. 14, one test per bullet)", ""]
    L += _table(a6["fail_closed_audit"], [("#", "n"), ("bullet", "a9_6_sec14_bullet"),
                                          ("implementation", "implementation"), ("where", "where"),
                                          ("test", "test")]) + [""]
    L += ["### 19.5 Settled questions (A9.6 sec. 6-7)", ""]
    L += _table(a6["derived_resolutions"], [("id", "id"), ("disposition", "disposition"), ("answer", "answer"),
                                            ("follows from", "follows_from"), ("implemented in", "implemented_in"),
                                            ("tests", "tests")]) + [""]
    g = a6["external_reference"]
    L += ["External reference: %s, %s (fetched PDF sha256 `%s`); clauses used: %s." % (
        g["citation"], g["url"], g["fetched_pdf_sha256"],
        "; ".join("%s %s" % kv for kv in g["clauses_used"].items())), ""]
    L += ["Not done here: " + " / ".join(a6["not_done_here"]), ""]
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
    return {OUT_JSON: _dump(doc), OUT_MD: render_md(doc), OUT_SCHEMA: _dump(build_schema()),
            OUT_REPORT_SCHEMA: _dump(build_report_schema())}


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

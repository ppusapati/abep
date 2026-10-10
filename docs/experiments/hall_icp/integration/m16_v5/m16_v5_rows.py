"""M16 v5 row re-derivation specifications (data only; read by build_subsystem_maturity_v5.py, which resolves and checks
every id at build time and raises on any miss).

Per M16 row (1-21, same numbering as M16 v3 / v4; row 17 is SUPERSEDED_FOR_PRIMARY_LINE and is carried unchanged):

  sched_v4   disposition of the v4 scheduler blocking item (copied from the pinned v4 JSON):
               {"disposition": "CARRIED", "category": <CATEGORY>, "note": ...}
                   the item still blocks; its v4 still_open_check / items are re-resolved against the live artifacts;
                   "by" (optional) lists answers that CONSTRAIN it without removing it;
               {"disposition": "CHANGED", "by": [answer refs], "note": ...}
                   the answers listed changed the item; it is recorded as removed (pointer + sha256 of every answer) and
                   the row is re-pointed to a remaining blocker.
  answers    {answer ref: (effect, [remaining blocker ids it now waits on], note)}. Every OWNER_QUESTION blocker of the
             v4 row MUST appear here (fail closed); further refs record answers that changed / constrain the row.
             An answer ref is a state v5 row id (status ANSWERED_BY_A9_* / AMENDED_BY_A9_* with decision A9.8 .. A9.21)
             or '<decision>/<item>' of a later decision (A9.17 .. A9.21, a9_later_lib).
  added      remaining blockers that are new in v5: (kind, id). Kinds and their category come from BLOCKER_KINDS_V5.
  scheduler  (remaining blocker id, reason): the single scheduler blocking item (owner row 141: one-blocker rule).
  waits_on   the scheduler wait class (the v4 vocabulary + one v5 addition, WAITS_ON_V5_ADDITIONS).

The v4 non-owner blockers (P1 / P2 measurements, P3 inputs, P4 tests, quotations, ICD / bus / A9-07 TBD items) are not
listed here: every one is re-resolved from the v4 row with the v4 resolver (raises when it is no longer open) and stays a
remaining blocker with the default category of its kind (V4_KIND_CATEGORY).

Nothing here is a value, a prediction, a date, a duration, a name or an owner answer. Ids, dispositions and recorder
notes only; every note quotes or paraphrases the cited answer and is checked against nothing but ids.
"""

CATEGORIES = {
    "OWNER_ACT": "needs an act of the owner (an open owner question, owner acceptance of criteria / a reading, an owner "
                 "release, the staffing ledger)",
    "EVIDENCE": "needs evidence that does not exist yet (analysis / design definition, sourced data, a registered "
                "result, a gate evaluation on registered evidence)",
    "HARDWARE_RUN": "needs a measurement / test campaign on project hardware that has not been run",
    "EXTERNAL_INPUT": "needs an input from outside the project record (supplier quotation / data, spacecraft / mission "
                      "ICD)",
}

EFFECTS = {
    "RULE_RECORDED": "the answer fixes a rule, convention or scope; the owner-decision blocker is removed and the answer "
                     "names no new input for this row",
    "REQUIRES_EVIDENCE": "the answer decides that the value comes from evidence (measurement, quotation, sourced data); "
                         "the blocker becomes that evidence",
    "REQUIRES_EXTERNAL_INPUT": "the answer decides that the value comes from an external input that stays TBD",
    "AUTHORIZES_WORK": "the answer authorises / orders work; the output of that work becomes the blocker (an "
                       "authorisation never advances readiness)",
    "SUPERSEDED_FOR_FLIGHT": "the answer is superseded / amended by A9.19 / A9.20 (no C1 flight variant; C1 a ground-only "
                             "laboratory reference); the blocker is removed for the one flight configuration",
    "CONSTRAINS_NOT_REMOVES": "the answer constrains a carried blocker but does not remove it",
}
# effects that must name at least one remaining blocker they now wait on
EFFECTS_NEEDING_TARGET = {"REQUIRES_EVIDENCE", "REQUIRES_EXTERNAL_INPUT", "AUTHORIZES_WORK"}

BLOCKER_KINDS_V5 = {
    # v4 kinds (re-resolved with the v4 resolver against the live artifacts)
    "P1_MEASUREMENT": ("HARDWARE_RUN", "a P1 measurement or stage that has not been run"),
    "P2_MEASUREMENT": ("HARDWARE_RUN", "a P2 output that needs the measured impedance map"),
    "P3_INPUT": ("EVIDENCE", "a P3 coupled-thermal input still TBD"),
    "P4_EVIDENCE": ("HARDWARE_RUN", "a P4 coupon / material test that has not been run"),
    "VENDOR_QUOTE": ("EXTERNAL_INPUT", "an RFQ v2 line / open specification item awaiting a quotation / supplier data"),
    "INTERFACE_TBD": ("EVIDENCE", "an ICD item whose value is still TBD (design definition)"),
    "BUS_ITEM_OPEN": ("EXTERNAL_INPUT", "an A9-02 bus-boundary item still OPEN (supplier data)"),
    "H2A9_ITEM_TBD": ("EVIDENCE", "an A9-07 H-1 revision item still TBD (design definition)"),
    # v5 kinds
    "V4_SCHEDULER_CARRIED": (None, "the v4 scheduler blocking item carried (category given per row)"),
    "OWNER_QUESTION_V5": ("OWNER_ACT", "an owner-question state v5 row that is TBD_OWNER"),
    "GATE_CRITERIA": ("OWNER_ACT", "owner-approved gate whose criteria are PENDING_OWNER_ACCEPTANCE (RVM "
                                   "owner_approved_gates)"),
    "GATE_EVALUATION": ("EVIDENCE", "pre-LOCK-1 gate NOT_EVALUATED (F9 pre_lock1_gates; fail closed)"),
    "PROGRAMME_STEP": (None, "an A9.21 hardware-programme step (category from the step kind: PROGRAMME_STEP_CATEGORY)"),
    "ANSWER_REQUIRED_EVIDENCE": ("EVIDENCE", "evidence the owner answer itself requires (state v5 row answered)"),
    "EXTERNAL_INPUT_V5": ("EXTERNAL_INPUT", "a state v5 row whose external_input_status is TBD_EXTERNAL_INPUT"),
    "XE_LEDGER_REFUSED": ("EVIDENCE", "an Xe accounting v3 flight scenario whose booking is REFUSED_TBD_INPUTS"),
    "AL08_PROVISIONAL": ("EXTERNAL_INPUT", "AL-08 kept as a provisional planning floor until the split quotations "
                                          "(A9.21 AL08; mass / power v3)"),
    "S1A_CONDITION": ("OWNER_ACT", "an S1a readiness condition still MISSING (owner release)"),
    "P4_APPLICATION_OPEN": ("EVIDENCE", "a P4 application whose blockers list is non-empty"),
    "RFQ3_PACKAGE": ("EXTERNAL_INPUT", "an RFQ v3 package (quotation / specification only; dispatch by the owner / "
                                       "procurement; no quotation registered)"),
    "NAMED_ENGINEER": ("OWNER_ACT", "named responsible engineer from the project staffing ledger (A9.14 M16-V3-Q-01; "
                                    "none in the repository; none fabricated) - PENDING_EVIDENCE"),
}
V4_KINDS = ("P1_MEASUREMENT", "P2_MEASUREMENT", "P3_INPUT", "P4_EVIDENCE", "VENDOR_QUOTE", "INTERFACE_TBD",
            "BUS_ITEM_OPEN", "H2A9_ITEM_TBD")
PROGRAMME_STEP_CATEGORY = {
    "ANALYSIS": "EVIDENCE", "SELECTION": "EVIDENCE", "EXTERNAL_GATE_REFERENCE": "EVIDENCE",
    "REFERENCE_CAMPAIGN": "HARDWARE_RUN", "COMMISSIONING_REFERENCE_CAMPAIGN": "HARDWARE_RUN",
    "COMMISSIONING_REFERENCE_STAGE": "HARDWARE_RUN", "REGISTERED_CAMPAIGN": "HARDWARE_RUN", "CAMPAIGN": "HARDWARE_RUN",
    "ANALYSIS_AND_TEST": "HARDWARE_RUN",
}

WAITS_ON_V5_ADDITIONS = [
    "analysis / design work inside a registered A9.21 programme step (not started)",
]

_DESIGN = "design work outside every registered scope"
_OWNER = "owner decision"
_MEAS = "H-1 / C-1 measurement (wave H4, PLANNED_NOT_REGISTERED)"
_PROC = "procurement (wave H3, PLANNED_NOT_REGISTERED)"
_SRC = "first-hand source verification"
_PROG = WAITS_ON_V5_ADDITIONS[0]

ROWS = {
    1: {"sched_v4": {"disposition": "CARRIED", "category": "OWNER_ACT", "by": ["OD2", "OD3", "F1Q-02", "F1Q-03"],
                     "note": "no A9.8 .. A9.21 answer selects the DI-1.1 / DI-1.2 intake area sizing rule or geometry; "
                             "OD2 (statewise quantifier), OD3 (design states from the frozen orbit-resolved dataset), "
                             "F1Q-02 (sourced structural design before LOCK-1) and F1Q-03 (registered AOCS pointing "
                             "envelope) constrain its basis without taking it"},
        "answers": {"OD2": ("RULE_RECORDED", [], "every required environment state must satisfy the hard requirements "
                                                  "(statewise, fail closed)"),
                    "OD3": ("REQUIRES_EXTERNAL_INPUT", ["OD3"], "design states from the versioned orbit-resolved "
                            "dataset; inclination / LTAN stay TBD (A9.17 ORBIT, A9.21 EXTERNAL_INPUTS)"),
                    "F1Q-02": ("REQUIRES_EVIDENCE", ["F1Q-02"], "assumptions for budgeting only; sourced / buildable "
                               "intake structural definition mandatory before LOCK-1"),
                    "F1Q-03": ("REQUIRES_EXTERNAL_INPUT", ["F1Q-03"], "0-5 deg is sensitivity only; the registered "
                               "AOCS pointing envelope is required"),
                    "A9.21/EXTERNAL_INPUTS": ("REQUIRES_EXTERNAL_INPUT", ["F1Q-03", "OD3"],
                                              "AOCS pointing envelope and inclination / LTAN stay TBD")},
        "added": [("EXTERNAL_INPUT_V5", "F1Q-03"), ("EXTERNAL_INPUT_V5", "OD3"), ("ANSWER_REQUIRED_EVIDENCE", "F1Q-02")],
        "scheduler": ("V4-SCHED", "the carried owner decision DI-1.1 / DI-1.2 precedes the geometry and the structural "
                                  "design that depend on it"),
        "waits_on": _OWNER},
    2: {"sched_v4": {"disposition": "CHANGED", "by": ["UPSTREAM_ICD-Q1", "F2-OQ-01", "F2-OQ-02", "F2-OQ-03",
                                                      "F2-OQ-04"],
                     "note": "the filter concept is now owner-defined: a separate production-path element at the "
                             "compressor inlet for particulate / debris protection, catalytic O->O2 not baseline, "
                             "'no filter' a reference bound only"},
        "answers": {"OD12": ("RULE_RECORDED", [], "recorded RFP items promoted into explicit compliance gates"),
                    "UPSTREAM_ICD-Q1": ("RULE_RECORDED", [], "filter is a separate production-path element"),
                    "F2-OQ-01": ("REQUIRES_EVIDENCE", ["F2-OQ-01"], "quantitative filter acceptance pre-registered "
                                 "before LOCK-1; limits evidence-derived"),
                    "F2-OQ-02": ("RULE_RECORDED", [], "catalytic filter excluded from the baseline"),
                    "F2-OQ-03": ("RULE_RECORDED", [], "'no filter' an analytical reference only"),
                    "F2-OQ-04": ("REQUIRES_EVIDENCE", ["APP-FILTER"], "compressor-inlet filter; APP-FILTER added to P4")},
        "added": [("ANSWER_REQUIRED_EVIDENCE", "F2-OQ-01"), ("P4_APPLICATION_OPEN", "APP-FILTER")],
        "scheduler": ("F2-OQ-01", "the concept is decided; the pre-registered quantitative filter acceptance (evidence-"
                                  "derived limits) is the first missing input"),
        "waits_on": _DESIGN},
    3: {"sched_v4": {"disposition": "CARRIED", "category": "EVIDENCE",
                     "note": "no A9.8 .. A9.21 answer verifies the Li 2015 compression claim first-hand (acquisition "
                             "was authorised before A9.8 in WEB-ACC-3; an authorisation is not a verification)"},
        "answers": {"OD2": ("RULE_RECORDED", [], "statewise envelope quantifier"),
                    "OQ-F3-03": ("REQUIRES_EVIDENCE", ["OQ-F3-03"], "transitional-regime model and T-1 evidence in "
                                 "parallel; fail closed above 0.1 Pa until validated")},
        "added": [("ANSWER_REQUIRED_EVIDENCE", "OQ-F3-03")],
        "scheduler": ("V4-SCHED", "first-hand source verification still missing (carried)"),
        "waits_on": _SRC},
    4: {"sched_v4": {"disposition": "CARRIED", "category": "EVIDENCE", "by": ["OQ-F4-01", "OQ-F4-02", "OQ-F3-03"],
                     "note": "the scheduled plenum setpoint (OQ-F4-01), the higher-pressure compression direction "
                             "(OQ-F4-02) and the 0.1 Pa fail-closed domain (OQ-F3-03) constrain the plenum; no answer "
                             "sets the chamber volume or an operating pressure value"},
        "answers": {"OQ-F4-01": ("CONSTRAINS_NOT_REMOVES", [], "scheduled setpoint baseline, fixed setpoint fallback"),
                    "OQ-F4-02": ("CONSTRAINS_NOT_REMOVES", [], "higher-pressure compression the primary direction"),
                    "OQ-F3-03": ("CONSTRAINS_NOT_REMOVES", [], "no valid > 0.1 Pa result until evidence closes the "
                                                               "domain")},
        "added": [],
        "scheduler": ("V4-SCHED", "chamber volume and operating pressure still not set (carried)"),
        "waits_on": _DESIGN},
    5: {"sched_v4": {"disposition": "CARRIED", "category": "OWNER_ACT", "check": ("S1A_CONDITION", "S1A-C3"),
                     "by": ["F9-OQ-02"],
                     "note": "the owner-released ground-qualification feed points (S1A-C3) still do not exist; F9-OQ-02 "
                             "derives the flight feed requirement from the measured H-1 thrust map (no fixed mg/s)"},
        "answers": {"F9-OQ-02": ("REQUIRES_EVIDENCE", ["H1-THRUST-FEED-MAP"], "performance-derived, state-specific feed "
                                 "requirement from the measured H-1 thrust map")},
        "added": [("PROGRAMME_STEP", "H1-THRUST-FEED-MAP")],
        "scheduler": ("V4-SCHED", "owner release of the ground-qualification feed points (S1A-C3 MISSING)"),
        "waits_on": _OWNER},
    6: {"sched_v4": {"disposition": "CARRIED", "category": "EVIDENCE", "check": ("XE_LEDGER_REFUSED", "S1-FL-PRIMARY"),
                     "by": ["A9.19/architecture"],
                     "note": "'per configuration' now reads as the one flight configuration (A9.19); its primary "
                             "scenario S1-FL-PRIMARY stays REFUSED_TBD_INPUTS in Xe accounting v3"},
        "answers": {"XA9Q-07": ("RULE_RECORDED", [], "Xe capability applies to hall_icp_neutralizer (role amended by "
                                                     "A9.19: contingency / emergency supply mode)"),
                    "XA9Q-01": ("RULE_RECORDED", [], "2 / 5 / 10 kg are loaded-Xe cases"),
                    "XA9Q-06": ("REQUIRES_EVIDENCE", ["GAS-L08"], "MEOP selected only from quotations at the 323 K "
                                "cases"),
                    "OD6": ("RULE_RECORDED", [], "dual-propellant capability as separate modes, not a premix (role of "
                                                 "Xe amended by A9.19)"),
                    "A9.19/architecture": ("RULE_RECORDED", [], "one flight configuration"),
                    "A9.21/AL08": ("REQUIRES_EXTERNAL_INPUT", ["AL-08"], "AL-08 provisional until split quotations")},
        "added": [("AL08_PROVISIONAL", "AL-08")],
        "scheduler": ("V4-SCHED", "the flight Xe ledger (S1-FL-PRIMARY) is still REFUSED_TBD_INPUTS"),
        "waits_on": _MEAS},
    7: {"sched_v4": {"disposition": "CHANGED", "by": ["A9.19/architecture", "A9.20/answer"],
                     "note": "the 'C1 flow range' gap concerns the ground-only C1 reference (A9.20); it is no flight Xe "
                             "regulator blocker"},
        "answers": {"XA9Q-06": ("REQUIRES_EVIDENCE", ["GAS-L09"], "regulator solutions requested against the 323 K "
                                                                 "cases"),
                    "OQ-RFQ-09": ("REQUIRES_EVIDENCE", ["GAS-L09"], "suppliers propose MEOP and design / proof factors; "
                                                                    "basis selected after quotations"),
                    "A9.19/architecture": ("SUPERSEDED_FOR_FLIGHT", [], "no conventional hollow cathode in flight"),
                    "A9.20/answer": ("SUPERSEDED_FOR_FLIGHT", [], "C1 GROUND_ONLY_LAB_REFERENCE")},
        "added": [],
        "scheduler": ("GAS-L09", "the low-flow PMU (regulator) quotation; MEOP is supplier-proposed (OQ-RFQ-09)"),
        "waits_on": _PROC},
    8: {"sched_v4": {"disposition": "CARRIED", "category": "EXTERNAL_INPUT", "check": ("VENDOR_QUOTE", "GAS-L11"),
                     "note": "valve selection still waits on the quotation"},
        "answers": {"XA9Q-03": ("RULE_RECORDED", [], "flow-class term additive inside the non-reserve base until "
                                                     "hardware evidence"),
                    "A9.21/AL08": ("REQUIRES_EXTERNAL_INPUT", ["AL-08"], "AL-08 provisional until split quotations")},
        "added": [("AL08_PROVISIONAL", "AL-08")],
        "scheduler": ("V4-SCHED", "valve selection (quotation) carried"),
        "waits_on": _PROC},
    9: {"sched_v4": {"disposition": "CHANGED", "by": ["F5-OQ-01", "A9.21/HW_PROGRAMME"],
                     "note": "FEMM of MC-1 is now authorised as analysis points (F5-OQ-01) and ordered as H-1 S7.1 "
                             "before S7.2 (A9.21 item 6); authorised is not run - S7.1 is NOT_STARTABLE"},
        "answers": {"OQ-RFQV2-10": ("AUTHORIZES_WORK", ["RFQ3-H1FAB"], "separate H-1 fabrication package; design and "
                                    "final integration in-house"),
                    "P1Q-07": ("AUTHORIZES_WORK", ["C1-REF"], "I_d,max,H1 from a dedicated H-1 + C1 "
                                                              "characterization"),
                    "F5-OQ-01": ("AUTHORIZES_WORK", ["H1-S7.1"], "FEMM analysis points, not a selection"),
                    "F5-OQ-02": ("AUTHORIZES_WORK", ["H1-S7.2"], "engineering point on non-performance criteria"),
                    "F9-OQ-02": ("REQUIRES_EVIDENCE", ["H1-THRUST-FEED-MAP"], "measured H-1 thrust map"),
                    "A9.21/HW_PROGRAMME": ("AUTHORIZES_WORK", ["H1-S7.1", "H1-S7.2", "H1-THRUST-FEED-MAP"],
                                           "programme order H-1 S7.1 -> S7.2; measured thrust / feed map")},
        "added": [("PROGRAMME_STEP", "H1-S7.1"), ("PROGRAMME_STEP", "H1-S7.2"), ("PROGRAMME_STEP", "C1-REF"),
                  ("PROGRAMME_STEP", "H1-THRUST-FEED-MAP"), ("RFQ3_PACKAGE", "RFQ3-H1FAB")],
        "scheduler": ("H1-S7.1", "FEMM results at every authorised analysis point (first step of the A9.21 order)"),
        "waits_on": _PROG},
    10: {"sched_v4": {"disposition": "CARRIED", "category": "EVIDENCE", "by": ["F5-OQ-03"],
                      "note": "F5-OQ-03 keeps 754 degC only as a necessary ceiling until grade-specific sourced "
                              "magnetic data exist; B_sat(T) still governs and is not sourced"},
         "answers": {"OQ-A907-04": ("RULE_RECORDED", [], "plain ceramic-insulated copper baseline; Ni-clad contingency"),
                     "P1Q-06": ("AUTHORIZES_WORK", ["ICP-AR-REF"], "magnet-OFF and registered H-1 magnet settings in "
                                                                     "P1-S3 .. S5"),
                     "F5-OQ-03": ("CONSTRAINS_NOT_REMOVES", [], "754 degC necessary ceiling pending grade data")},
         "added": [("PROGRAMME_STEP", "ICP-AR-REF")],
         "scheduler": ("V4-SCHED", "sourced B_sat(T) and coil qualification (carried)"),
         "waits_on": _SRC},
    11: {"sched_v4": {"disposition": "CHANGED", "by": ["P1Q-07", "A9.21/HW_PROGRAMME"],
                      "note": "the owner decision on I_d,max is taken (P1Q-07): it is registered from the dedicated "
                              "H-1 + C1 reference characterization (C1-REF, A9.21 item 7); C1 is ground-only (A9.20)"},
          "answers": {"P1Q-07": ("AUTHORIZES_WORK", ["C1-REF"], "dedicated H-1 + C1 characterization registers "
                                                                "I_d,max,H1"),
                      "MPQ-01": ("SUPERSEDED_FOR_FLIGHT", [], "no C1 flight variant (A9.19)"),
                      "OQ-A907-07": ("SUPERSEDED_FOR_FLIGHT", [], "no C1 flight variant (A9.19)"),
                      "OQ-A907-01": ("RULE_RECORDED", [], "three attempts (amended to the ground reference by A9.20)"),
                      "OQ-RFQ-04": ("REQUIRES_EVIDENCE", ["RFQ2-HALLEL-R20"], "start flow from the selected C1 vendor "
                                                                              "procedure and characterization"),
                      "A9.21/HW_PROGRAMME": ("AUTHORIZES_WORK", ["C1-REF"], "H-1 + C1 reference before P1-S7")},
          "added": [("PROGRAMME_STEP", "C1-REF")],
          "scheduler": ("C1-REF", "the H-1 + C1 reference characterization registering I_d,max,H1,Ar"),
          "waits_on": _MEAS},
    12: {"sched_v4": {"disposition": "CARRIED", "category": "EXTERNAL_INPUT", "check": ("VENDOR_QUOTE", "HE-L06"),
                      "note": "breadboard discharge supply still a quotation"},
          "answers": {"MQ-04": ("REQUIRES_EVIDENCE", ["HE-L06"], "replace the 6.0 kg MEV floor with the selected flight "
                                                                 "PPU CBE"),
                      "RVMQ-01": ("RULE_RECORDED", [], "redundancy at electronics / sensor level; no full thruster "
                                                       "duplication")},
          "added": [],
          "scheduler": ("V4-SCHED", "breadboard discharge supply (quotation) carried"),
          "waits_on": _PROC},
    13: {"sched_v4": {"disposition": "CARRIED", "category": "EVIDENCE",
                      "note": "the P3 closure inputs are still TBD (re-resolved)"},
          "answers": {"P3Q-02": ("REQUIRES_EVIDENCE", ["COUPLED-H1-ICP", "P3-THERMAL"], "model class A for LOCK-1; "
                                 "closure requires correlation against the integrated test article"),
                      "OQ-A907-03": ("RULE_RECORDED", [], "adverse bounding corner of admissible joint states"),
                      "OQ-A907-09": ("RULE_RECORDED", [], "20 % margin on dissipated loads only"),
                      "OQ-A907-10": ("RULE_RECORDED", [], "10 K SEARCH_SENSITIVE screen"),
                      "ICPQ-10": ("REQUIRES_EVIDENCE", ["P2-MAP"], "P_fwd,max from the registered ICP / P2 envelope"),
                      "OQ-A910-06": ("REQUIRES_EVIDENCE", ["P2-MAP"], "600 W temporary; replaced after P2"),
                      "A9.21/HW_PROGRAMME": ("AUTHORIZES_WORK", ["COUPLED-H1-ICP", "P3-THERMAL"],
                                             "coupled H-1 + ICP before the P3 closure")},
          "added": [("PROGRAMME_STEP", "COUPLED-H1-ICP"), ("PROGRAMME_STEP", "P3-THERMAL"),
                    ("PROGRAMME_STEP", "P2-MAP")],
          "scheduler": ("V4-SCHED", "coupled thermal closure inputs (carried; re-resolved)"),
          "waits_on": _DESIGN},
    14: {"sched_v4": {"disposition": "CARRIED", "category": "EXTERNAL_INPUT", "check": ("VENDOR_QUOTE", "RF-L10"),
                      "note": "generator interlock interface still a quotation"},
          "answers": {"OD14": ("RULE_RECORDED", [], "atmospheric ignition a DERIVED_PROJECT_REQUIREMENT"),
                      "RVMQ-01": ("RULE_RECORDED", [], "redundancy at electronics / sensor level")},
          "added": [("OWNER_QUESTION_V5", "MPV3Q-01"), ("PROGRAMME_STEP", "P2-MAP")],
          "scheduler": ("V4-SCHED", "generator interlock interface (quotation) carried"),
          "waits_on": _PROC},
    15: {"sched_v4": {"disposition": "CHANGED", "by": ["P2Q-07", "A9.21/HW_PROGRAMME"],
                      "note": "the impedance map is now the registered step P2-MAP: only after the in-house V/I "
                              "calibration and its uncertainty budget are frozen (A9.21 item 9; P2Q-07)"},
          "answers": {"P2Q-01": ("RULE_RECORDED", [], "ZM-A primary, ZM-B / ZM-C cross-checks"),
                      "P2Q-03": ("RULE_RECORDED", [], "k_agreement = 2.0"),
                      "P2Q-07": ("AUTHORIZES_WORK", ["P2-MAP"], "in-house traceable V/I calibration accepted"),
                      "P2Q-02": ("REQUIRES_EVIDENCE", ["RFQ3-RFMET"], "separate RF-metrology package"),
                      "A9.21/HW_PROGRAMME": ("AUTHORIZES_WORK", ["P2-MAP"], "P2 map after the V/I calibration")},
          "added": [("PROGRAMME_STEP", "P2-MAP"), ("RFQ3_PACKAGE", "RFQ3-RFMET")],
          "scheduler": ("P2-MAP", "the P2 impedance map (entry preconditions: frozen V/I calibration + uncertainty "
                                  "budget)"),
          "waits_on": _MEAS},
    16: {"sched_v4": {"disposition": "CARRIED", "category": "EVIDENCE",
                      "note": "ICP module drawings (ICP-02 / 04 / 07 still TBD in the ICD)"},
          "answers": {"ICPQ-03": ("RULE_RECORDED", [], "both modules on the moving thrust platform"),
                      "OQ-A910-05": ("RULE_RECORDED", [], "matched sham reproduces the local-match parasitics; AL-06")},
          "added": [],
          "scheduler": ("V4-SCHED", "module drawings (carried)"),
          "waits_on": _DESIGN},
    17: None,
    18: {"sched_v4": {"disposition": "CARRIED", "category": "EVIDENCE",
                      "note": "ICP module design (ICD ICP-02 / 04 / 07 / 21 / 44 still TBD)"},
          "answers": {"P1Q-07": ("AUTHORIZES_WORK", ["C1-REF", "ICP-45A-P1-S7"], "I_d,max,H1 registered before P1-S7"),
                      "P1Q-09": ("RULE_RECORDED", [], "dedicated isolated target"),
                      "OQ-VI-04": ("RULE_RECORDED", [], "provisional ICP life basis >= 15,000 h"),
                      "ICPQ-10": ("REQUIRES_EVIDENCE", ["P2-MAP"], "ICP-43 bound from the registered P2 envelope"),
                      "ICPQ-11": ("REQUIRES_EVIDENCE", ["P2-MAP"], "k_RF = 1.5 x V_ant,peak at the worst measured P2 "
                                                                   "point"),
                      "P3Q-01": ("RULE_RECORDED", [], "calorimetry primary heat-load evidence"),
                      "P4-OQ-05": ("RULE_RECORDED", [], "negative-bias collector coupons + floating control"),
                      "A9.21/ICP_GATE": ("AUTHORIZES_WORK", ["GNG-ICP-01/criteria", "GNG-ICP-01/evaluation"],
                                         "mandatory ICP go / no-go before LOCK-1; no criterion approved; fail closed"),
                      "A9.21/HW_PROGRAMME": ("AUTHORIZES_WORK", ["ICP-AR-REF", "ICP-45A-P1-S7", "ICP-45N",
                                                                 "ICP-XE-MODE"],
                                             "ICP Ar reference -> air / N2 ICP-45 -> separate Xe mode")},
          "added": [("GATE_CRITERIA", "GNG-ICP-01/criteria"), ("GATE_EVALUATION", "GNG-ICP-01/evaluation"),
                    ("PROGRAMME_STEP", "ICP-AR-REF"), ("PROGRAMME_STEP", "ICP-45A-P1-S7"),
                    ("PROGRAMME_STEP", "ICP-45N"), ("PROGRAMME_STEP", "ICP-XE-MODE"), ("PROGRAMME_STEP", "C1-REF"),
                    ("PROGRAMME_STEP", "P2-MAP"), ("OWNER_QUESTION_V5", "XV3Q-01")],
          "scheduler": ("V4-SCHED", "ICP module design (carried; ICD items re-resolved)"),
          "waits_on": _DESIGN},
    19: {"sched_v4": {"disposition": "CARRIED", "category": "EXTERNAL_INPUT",
                      "note": "flight-representative DC-input RF source not scoped (A902-21 OPEN)"},
          "answers": {"ICPQ-11": ("REQUIRES_EVIDENCE", ["P2-MAP"], "voltage rating from the worst measured P2 point"),
                      "P2Q-10": ("REQUIRES_EVIDENCE", ["P2-MAP"], "stress-class-specific margins on the measured "
                                                                  "envelope"),
                      "P2Q-04": ("RULE_RECORDED", [], "re-tune each hot-map point plus fixed-tune sub-sweeps")},
          "added": [("PROGRAMME_STEP", "P2-MAP")],
          "scheduler": ("V4-SCHED", "A902-21 generator DC-input efficiency (carried)"),
          "waits_on": _PROC},
    20: {"sched_v4": {"disposition": "CARRIED", "category": "EVIDENCE",
                      "note": "H-1 anode material not selected (A9H-ANODE-01 TBD)"},
          "answers": {"P4-OQ-01": ("REQUIRES_EVIDENCE", ["TP-01"], "staged validation of T_validated,continuous"),
                      "P4-OQ-02": ("RULE_RECORDED", [], "broad Q0 screen, then down-select for Q1"),
                      "P4-OQ-03": ("REQUIRES_EVIDENCE", ["P4-ACCEPTANCE-EXPOSURE"], "LOCK-2 after metrology, before "
                                                                                     "acceptance exposure"),
                      "P4-OQ-04": ("AUTHORIZES_WORK", ["TP-01"], "acquire species-resolved data and measure candidates"),
                      "OQ-A907-05": ("RULE_RECORDED", [], "supplier ratings provisional only"),
                      "OQ-A907-08": ("RULE_RECORDED", [], "exterior coating its own node limit"),
                      "A9.21/HW_PROGRAMME": ("AUTHORIZES_WORK", ["P3-THERMAL", "P4-ACCEPTANCE-EXPOSURE"],
                                             "coupled thermal -> P4 acceptance exposure")},
          "added": [("PROGRAMME_STEP", "P3-THERMAL"), ("PROGRAMME_STEP", "P4-ACCEPTANCE-EXPOSURE")],
          "scheduler": ("V4-SCHED", "anode material (carried)"),
          "waits_on": _DESIGN},
    21: {"sched_v4": {"disposition": "CARRIED", "category": "EVIDENCE",
                      "note": "H-1 anode heat-removal path not designed (A9H-ANODE-02 TBD)"},
          "answers": {"P3Q-02": ("REQUIRES_EVIDENCE", ["COUPLED-H1-ICP", "P3-THERMAL"], "correlation against the "
                                 "integrated test article"),
                      "OQ-A907-06": ("AUTHORIZES_WORK", ["V4-SCHED"], "pursue the isolated mount + dedicated radiator; "
                                     "50 W provisional design requirement"),
                      "A9.21/HW_PROGRAMME": ("AUTHORIZES_WORK", ["COUPLED-H1-ICP", "P3-THERMAL"],
                                             "coupled H-1 + ICP before the P3 closure")},
          "added": [("PROGRAMME_STEP", "COUPLED-H1-ICP"), ("PROGRAMME_STEP", "P3-THERMAL")],
          "scheduler": ("V4-SCHED", "anode heat-removal path design (carried)"),
          "waits_on": _DESIGN},
}

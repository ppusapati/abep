"""Row definitions of the A9 system requirement-verification matrix (fo_a9_6_rvm; A9.6 sec. 15).

Loaded by build_rvm_a9.py, which passes itself as `B` (helpers: plan, probes, source copiers). Requirement texts are
summaries written by this lane; every value they rest on is copied from a pinned source by the `ctx` helpers and
checked against a verbatim token (a missing token raises). Statuses are NOT set here: build_rvm_a9.evaluate_rows
assigns them with rvm_rules.assign_status.
"""
from __future__ import annotations


def build_rows(B, ctx):
    B.check_rfp_not_obtained(ctx)
    hall = B.probe_hall_analysis(ctx)
    tk = B.analog_takahashi(ctx)
    plan, oq, od = B.plan, B.oq, B.hgm_od
    both = B.CONFIGS
    rfp_basis = B.RFP_BASIS

    def cfg_map(fn):
        return {c: fn(c) for c in both}

    rows = []
    # RVM-01 ---------------------------------------------------------------------------------------------- altitude
    rows.append({
        "id": "RVM-01", "key": "ALTITUDE_ENVELOPE", "category": "rfp_recorded",
        "title": "Altitude envelope 180-230 km",
        "requirement_text": "Operate the ABEP propulsion system in very low Earth orbit over the altitude band 180-230 "
                            "km (the quantifier over the band and the atmosphere design states are open: lane-24 OD2 "
                            "and OD3).",
        "sources": [ctx.r2("(d) Altitude", "180 km and 230 km"), ctx.hgm("R1", "180–230 km"), ctx.answer(1)],
        "requirement_basis": rfp_basis, "requirement_frozen": False,
        "limit": {"quantity": "orbital altitude", "comparator": "within", "value": [180, 230], "units": "km"},
        "verification_methods": ["analysis", "test"],
        "verification_note": "analysis of drag vs delivered thrust over the band on the frozen NRLMSIS atmosphere "
                             "(abep_sim/data/atmosphere_msis21_v1.*: a model input, not compliance evidence) plus "
                             "thrust tests at delivered feed states representative of the band",
        "open_readings": [od(ctx, "OD2"), od(ctx, "OD3")],
        "rtm_xref": [ctx.rtm("RFP-ALT")], "lane24_gates": ["G1_thrust", "G2_bus_power", "G6_ignition_sustainment"],
        "m16_rows": [1, 3, 9],
        "artifacts": cfg_map(lambda c: [
            plan(ctx, "PRE", "HI-ABS", why="absolute demonstration at registered delivered feed states"),
            plan(ctx, "PRE", "DQ-HI-TABS", why="absolute thrust gate"),
            hall,
            plan(ctx, "FSC", "@doc", role="SUPPORTING", why="delivered feed state vs altitude (upstream path)"),
        ]),
    })
    # RVM-02 ---------------------------------------------------------------------------------------------- 12 mN
    rows.append({
        "id": "RVM-02", "key": "THRUST_12MN_SUSTAINED", "category": "rfp_recorded",
        "title": ">= 12 mN minimum sustained thrust on atmospheric propellant",
        "requirement_text": "Demonstrate >= 12 mN sustained atmospheric operation (owner row 4 reading of '12-25 mN'), "
                            "measured on the full system inside the < 1.5 kW spacecraft-DC boundary.",
        "sources": [ctx.r2("(c) Thrust", "12 mN and 25 mN"), ctx.hgm("R1", "12–25 mN"),
                    ctx.answer(4, "≥12 mN sustained atmospheric operation"), ctx.answer(120, "12 mN"),
                    ctx.a9("requirement_discipline", "full-system gates")],
        "requirement_basis": rfp_basis + "; owner engineering reading row 4", "requirement_frozen": False,
        "limit": {"quantity": "sustained thrust on atmospheric propellant", "comparator": ">=", "value": 12,
                  "units": "mN"},
        "verification_methods": ["test"],
        "verification_note": "torsional thrust stand (row 115), 1 % target (row 121, A9.1 UBQ-01), S1a u_T acceptance "
                             "test at 12 mN (row 120); Ar data never count (row 36, A9.1 HIQ-08)",
        "open_readings": [],
        "rtm_xref": [ctx.rtm("RFP-THR-MIN")], "lane24_gates": ["G1_thrust"], "m16_rows": [9, 10, 12],
        "artifacts": cfg_map(lambda c: [
            plan(ctx, "PRE", "DQ-HI-TABS"), plan(ctx, "PRE", "DQ-HI-SUST"), plan(ctx, "PRE", "HI-ABS"),
            plan(ctx, "VI", "VI-HD-03", role="SUPPORTING", why="thrust is a hardware-only input"),
            hall,
        ]),
    })
    # RVM-03 ---------------------------------------------------------------------------------------------- 25 mN
    rows.append({
        "id": "RVM-03", "key": "THRUST_25MN_CAPABILITY", "category": "rfp_recorded",
        "title": "25 mN demonstrated system capability inside P_bus < 1.5 kW",
        "requirement_text": "Demonstrate 25 mN system capability inside the same full spacecraft-DC propulsion boundary "
                            "with P_bus < 1.5 kW (16.67 mN/kW absolute full-system floor at that point); Xe is not "
                            "required for 25 mN, any Xe use is booked, and XE_AUGMENTED_PEAK points are never "
                            "atmospheric-only evidence.",
        "sources": [ctx.r2("(c) Thrust", "12 mN and 25 mN"), ctx.answer(4, "25 mN system capability"),
                    ctx.answer(27, "16.67 mN/kW"), ctx.answer(26, "never use them as evidence")],
        "requirement_basis": rfp_basis + "; owner engineering reading rows 4, 27", "requirement_frozen": False,
        "limit": {"quantity": "demonstrated thrust capability at P_bus < 1500 W", "comparator": ">=", "value": 25,
                  "units": "mN"},
        "verification_methods": ["test", "demonstration"],
        "verification_note": "same boundary as RVM-04 (A9-02); thrust per bus power >= 16.67 mN/kW at the 25 mN "
                             "point (row 27)",
        "open_readings": [],
        "rtm_xref": [ctx.rtm("RFP-THR-MAX")], "lane24_gates": ["G1_thrust", "G2_bus_power"], "m16_rows": [9, 12],
        "artifacts": cfg_map(lambda c: [
            plan(ctx, "PRE", "HI-ABS"), plan(ctx, "PRE", "DQ-HI-TABS"), plan(ctx, "PRE", "DQ-HI-PBUS"),
            plan(ctx, "VI", "VI-PB-03", role="SUPPORTING"), hall, B.probe_xe(ctx, c),
        ]),
    })
    # RVM-04 ---------------------------------------------------------------------------------------------- 1.5 kW
    rows.append({
        "id": "RVM-04", "key": "PBUS_LT_1500W_FULL_BUS", "category": "rfp_recorded",
        "title": "< 1.5 kW full bus power (A9-02 boundary, steady and start-up, 1 ms window)",
        "requirement_text": "P_bus,1ms,max = max_t (1/1 ms) integral P_bus dt < 1500 W at the spacecraft-DC "
                            "propulsion boundary (every active load: Hall discharge, magnets, RF source / match, "
                            "collector bias, C1 supplies, compressor, flow control, housekeeping, thermal), for steady "
                            "state AND start-up transients unless the official RFP grants a transient exception.",
        "sources": [ctx.r2("(d) Power", "1,500 W"), ctx.hgm("R1", "< 1.5 kW"),
                    ctx.answer(108, "<1.5 kW"), ctx.answer(110, "Every active load gets a bus slot"),
                    ctx.decision("A91", "OQ-A902-01", "1 ms"),
                    ctx.a9("requirement_discipline", "< 1.5 kW")],
        "requirement_basis": rfp_basis + "; owner rows 108, 110; A9.1 OQ-A902-01 engineering definition",
        "requirement_frozen": False,
        "limit": {"quantity": "P_bus,1ms,max (steady and start-up)", "comparator": "<", "value": 1500, "units": "W"},
        "verification_methods": ["test", "analysis"],
        "verification_note": "time-resolved spacecraft-side bus power: synchronized channels, >= 100 kSa/s, >= 20 kHz, "
                             "documented anti-aliasing (A9.1 OQ-A902-01); a ledger alone never PASSes; a mains-powered "
                             "laboratory RF generator is GROUND/FACILITY_ONLY and never flight P_bus evidence (A9.3 "
                             "OQ-RFQ-06)",
        "open_readings": [oq(ctx, "OQ-A910-03")],
        "rtm_xref": [ctx.rtm("RFP-PWR")], "lane24_gates": ["G2_bus_power"], "m16_rows": [12, 19],
        "artifacts": {c: ([B.probe_power(ctx, c), plan(ctx, "PRE", "DQ-HI-PBUS"),
                           plan(ctx, "BUS", "A902-01", role="SUPPORTING"),
                           plan(ctx, "BUS", "A902-03", role="SUPPORTING"),
                           plan(ctx, "VI", "VI-PB-03", role="SUPPORTING")]
                          + ([plan(ctx, "P2", "@doc", role="SUPPORTING",
                                   why="RF chain / delivered-power reconstruction (RF component ratings "
                                       "TBD_AFTER_IMPEDANCE_MAP)")] if c == "hall_icp_neutralizer" else []))
                      for c in both},
    })
    # RVM-05 ---------------------------------------------------------------------------------------------- 1.35 kW
    rows.append({
        "id": "RVM-05", "key": "INTERNAL_1350W_ALLOCATION", "category": "owner_internal_allocation",
        "title": "Internal ~1.35 kW design allocation (row 109)",
        "requirement_text": "The downstream ICP power must fit inside the internal ~1.35 kW design allocation; the "
                            "1.35 -> 1.5 kW margin is not consumed nominally; P_ICP,available = 1350 - P_common - "
                            "P_Hall - P_other,active at every registered condition (no fixed Hall/ICP split). An owner "
                            "allocation, not an RFP gate.",
        "sources": [ctx.answer(109, "~1.35 kW"), ctx.decision("A91", "OQ-A902-03", "1350"),
                    ctx.decision("A91", "OQ-A902-07", "1350 W")],
        "requirement_basis": "OWNER_ALLOCATION (row 109; A9.1 OQ-A902-03 / -07): owner-given internal design "
                             "allocation",
        "requirement_frozen": True,
        "limit": {"quantity": "system bus power at every registered condition (internal allocation)",
                  "comparator": "<=", "value": 1350, "units": "W"},
        "verification_methods": ["test", "analysis"],
        "verification_note": "ICP-45 demonstrated within P_ICP,available (A9.1 OQ-A902-03); the 0-500 W laboratory RF "
                             "range is a test capability only",
        "open_readings": [],
        "rtm_xref": [], "lane24_gates": [], "m16_rows": [12, 18, 19],
        "artifacts": {c: ([B.probe_alloc(ctx, c), plan(ctx, "BUS", "A902-04", role="SUPPORTING"),
                           plan(ctx, "VI", "VI-PB-04", role="SUPPORTING")]
                          + ([plan(ctx, "PRE", "DQ-HI-PALLOC")] if c == "hall_icp_neutralizer" else []))
                      for c in both},
    })
    # RVM-06 ---------------------------------------------------------------------------------------------- 40 kg
    rows.append({
        "id": "RVM-06", "key": "MASS_LT_40KG_WET", "category": "rfp_recorded",
        "title": "< 40 kg wet (incl. Xe + tank)",
        "requirement_text": "Total propulsion-system mass < 40 kg, read as the wet system including Xe and tank unless "
                            "the official RFP defines it as dry (row 5); 20 % internal development margin (row 52).",
        "sources": [ctx.r2("(a) Mass", "under 40 kg"), ctx.hgm("R1", "< 40 kg"),
                    ctx.answer(5, "INCLUDES Xe + tank"), ctx.answer(52, "<40 kg wet"),
                    ctx.a9("requirement_discipline", "< 40 kg")],
        "requirement_basis": rfp_basis + "; owner wet reading row 5", "requirement_frozen": False,
        "limit": {"quantity": "wet propulsion-system mass", "comparator": "<", "value": 40, "units": "kg"},
        "verification_methods": ["inspection", "analysis"],
        "verification_note": "weighed flight-representative hardware (inspection) and a CBE roll-up (analysis); "
                             "allocation vs CBE vs measured kept distinct (A9.6 sec. 11)",
        "open_readings": [oq(ctx, i) for i in ("MQ-01", "MQ-02", "MQ-09", "MQ-10", "XA9Q-01", "XA9Q-07",
                                               "OQ-A910-01")],
        "rtm_xref": [ctx.rtm("RFP-MASS")], "lane24_gates": ["G3_mass"], "m16_rows": [6, 12, 16],
        "artifacts": cfg_map(lambda c: [B.probe_mass(ctx, c, ("HARD_40_WET",)),
                                        plan(ctx, "PRE", "DQ-HI-DMASS", role="SUPPORTING"), B.probe_xe(ctx, c)]),
    })
    # RVM-07 ---------------------------------------------------------------------------------------------- 34/36 kg
    rows.append({
        "id": "RVM-07", "key": "INTERNAL_34_36KG_ALLOCATION", "category": "owner_internal_allocation",
        "title": "Internal 34 kg and 36 kg design allocations (row 53)",
        "requirement_text": "Evaluate the 34 kg and 36 kg internal design allocations side by side; 40 kg remains the "
                            "hard wet limit. An owner allocation, not an RFP gate.",
        "sources": [ctx.answer(53, "34 kg and 36 kg")],
        "requirement_basis": "OWNER_ALLOCATION (row 53): both values carried, neither selected",
        "requirement_frozen": True,
        "limit": {"quantity": "wet propulsion-system mass (internal allocation)", "comparator": "<=",
                  "value": [34, 36], "units": "kg"},
        "verification_methods": ["inspection", "analysis"],
        "verification_note": "as RVM-06",
        "open_readings": [oq(ctx, i) for i in ("MQ-01", "MQ-02", "MQ-09", "MQ-10", "XA9Q-07")],
        "rtm_xref": [], "lane24_gates": [], "m16_rows": [6, 12, 16],
        "artifacts": cfg_map(lambda c: [B.probe_mass(ctx, c, ("INTERNAL_34", "INTERNAL_36"))]),
    })
    # RVM-08 ---------------------------------------------------------------------------------------------- air
    rows.append({
        "id": "RVM-08", "key": "ATMOSPHERIC_PROPELLANT", "category": "rfp_recorded",
        "title": "Atmospheric propellant (air: N2 / O2 path; NO_ATOMIC_O labels)",
        "requirement_text": "Operate on intake-collected atmospheric air through the RFP architecture path (intake -> "
                            "filter -> compressor -> atmospheric gas chamber -> valve -> ionization/discharge -> "
                            "acceleration). Evidence order: Ar (engineering-only, never counts) -> N2 -> O2-bearing "
                            "surrogate labelled NO_ATOMIC_O -> separate atomic-O programme; no N2 + O2 test is AO proof.",
        "sources": [ctx.r2("(b) Air + Xe", "ambient atmospheric air"), ctx.hgm("R4", "intake"),
                    ctx.answer(36, "Ar data do not satisfy DRDO atmospheric requirements"),
                    ctx.answer(132, "NO_ATOMIC_O"), ctx.a9("evidence_sequence", "NO_ATOMIC_O"),
                    ctx.decision("A91", "HIQ-08", "DRDO compliance")],
        "requirement_basis": rfp_basis + "; owner rows 36, 132; A9 evidence_sequence", "requirement_frozen": False,
        "limit": {"quantity": "propellant", "comparator": "is", "value": "delivered atmospheric air", "units": "-"},
        "verification_methods": ["test", "demonstration"],
        "verification_note": "Hall-on sustainment on N2 and O2-bearing surrogates in HI-S1 / HI-CMP (NO_ATOMIC_O); "
                             "atomic-O effects only through HI-AO (RVM-09, RVM-16)",
        "open_readings": [],
        "rtm_xref": [ctx.rtm("RFP-PROP"), ctx.rtm("RFP-IGN-SUST")], "lane24_gates": ["G6_ignition_sustainment"],
        "m16_rows": [1, 2, 3, 4, 5, 9],
        "artifacts": cfg_map(lambda c: [
            plan(ctx, "PRE", "HI-CMP"), plan(ctx, "PRE", "DQ-HI-SUST"), hall,
            plan(ctx, "VI", "VI-GAS-07", role="SUPPORTING"), plan(ctx, "FSC", "@doc", role="SUPPORTING"),
        ]),
    })
    # RVM-09 ---------------------------------------------------------------------------------------------- nascent O
    rows.append({
        "id": "RVM-09", "key": "IONISE_NASCENT_O", "category": "rfp_inferred_from_repo_text",
        "title": "Ionise nascent (atomic) O (recorded as an RFP statement; verify)",
        "requirement_text": "The ABEP ionises nascent (atomic) O from the collected atmosphere. Recorded only in-repo "
                            "(R6); no threshold recorded; whether it needs its own gate is lane-24 OD12.",
        "sources": [ctx.hgm("R6", "ionise nascent O"), ctx.answer(132, "dedicated AO source"),
                    ctx.answer(102, "never assume O survival")],
        "requirement_basis": "RFP_INFERRED_FROM_REPO_TEXT - verify against the RFP document",
        "requirement_frozen": False,
        "limit": None,
        "verification_methods": ["test", "analysis"],
        "verification_note": "delivered species state measured (row 102); the O / O2 chemistry v0 tables are "
                             "unvalidated (not evidence); N2 + O2 surrogate data are NO_ATOMIC_O",
        "open_readings": [od(ctx, "OD12")],
        "rtm_xref": [ctx.rtm("RFP-NASCENT-O")], "lane24_gates": [], "m16_rows": [1, 2, 9],
        "artifacts": cfg_map(lambda c: [plan(ctx, "PRE", "HI-AO"), plan(ctx, "OO2", "@doc", role="SUPPORTING"),
                                        hall]),
    })
    # RVM-10 ---------------------------------------------------------------------------------------------- Xe
    rows.append({
        "id": "RVM-10", "key": "XE_CAPABILITY", "category": "rfp_recorded",
        "title": "Xe capability (air + Xe; bounded functional Xe mode)",
        "requirement_text": "Demonstrate a bounded functional Xe-capable operating mode beyond bookkeeping (need not be "
                            "continuous nominal operation) and book every Xe use (PHASE_TOTAL_FLOW); Xe reference / "
                            "health checks are labelled and never atmospheric evidence.",
        "sources": [ctx.r2("(b) Air + Xe", "supplemented with Xenon"), ctx.hgm("R1", "air + Xe"),
                    ctx.answer(6, "demonstrated Xe-capable operating mode"), ctx.answer(42, "PHASE_TOTAL_FLOW"),
                    ctx.answer(26, "Xe health/reference check"), ctx.decision("A91", "HIQ-03", "Xe")],
        "requirement_basis": rfp_basis + "; owner reading row 6", "requirement_frozen": False,
        "limit": {"quantity": "Xe-capable operating mode", "comparator": "demonstrated",
                  "value": "bounded functional", "units": "-"},
        "verification_methods": ["demonstration", "analysis"],
        "verification_note": "Xe mode demonstrated on H-1 (XE_REFERENCE / XE_AUGMENTED_PEAK labels); the Xe "
                             "accounting is supporting only (XV2-IF-09); whether the row-6 mode applies to the "
                             "hall_icp_neutralizer flight configuration is XA9Q-07 (OPEN, carried side by side)",
        "open_readings": [oq(ctx, "XA9Q-07"), oq(ctx, "XA9Q-01"), od(ctx, "OD6")],
        "rtm_xref": [ctx.rtm("RFP-XE-OP")], "lane24_gates": ["G7_air_xenon"], "m16_rows": [6, 7, 8],
        "artifacts": {c: ([plan(ctx, "PRE", "HI-CMP", why="bounded XE_REFERENCE checks, labelled and booked"),
                           B.probe_xe(ctx, c)]
                          + ([plan(ctx, "VI", "VI-SU-05", role="SUPPORTING")] if c == "hall_c1_reference" else []))
                      for c in both},
    })
    # RVM-11 ---------------------------------------------------------------------------------------------- Hall
    rows.append({
        "id": "RVM-11", "key": "HALL_PREFERENCE", "category": "rfp_recorded",
        "title": "Hall-effect thruster preferred",
        "requirement_text": "Preference (not mandate) for a Hall-effect thruster configuration. Both A9 configurations "
                            "use the H-1 Hall accelerator; A9 keeps the Hall family (CLAUDE.md rule 8).",
        "sources": [ctx.r2("(d) Hall preferred", "Hall-effect thruster"), ctx.hgm("R1", "Hall preferred"),
                    ctx.a9("primary_hypothesis", "Hall accelerator"), ctx.a9("control_fallback", "Hall")],
        "requirement_basis": rfp_basis, "requirement_frozen": False,
        "limit": None,
        "verification_methods": ["inspection"],
        "verification_note": "inspection of a frozen design baseline (Milestone C); the A9 architecture is "
                             "OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE, so there is no baseline to "
                             "inspect; a design intent is not verification evidence",
        "open_readings": [],
        "rtm_xref": [ctx.rtm("RFP-HALL")], "lane24_gates": [], "m16_rows": [9, 10],
        "artifacts": cfg_map(lambda c: [plan(ctx, "PRE", "@doc",
                                             why="H-1 is the common scored Hall article (D-09-A)")]),
    })
    # RVM-12 ---------------------------------------------------------------------------------------------- 15,000 h
    rows.append({
        "id": "RVM-12", "key": "FIRING_GT_15000H_PROVISIONAL", "category": "rfp_recorded",
        "title": "> 15,000 h firing (provisional hard requirement)",
        "requirement_text": "Cumulative firing time > 15,000 h, retained as a provisional hard requirement until the "
                            "official RFP confirms it (row 3). C1 carries the 15,000 h cathode basis; the ICP "
                            "neutralizer must carry its own RF-neutralizer lifetime / cycle requirement (row 46; not "
                            "yet defined: OQ-VI-04).",
        "sources": [ctx.hgm("R1", "> 15,000 h firing"), ctx.answer(3, ">15,000 h firing"),
                    ctx.answer(46, "RF-neutralizer lifetime/cycle requirement")],
        "requirement_basis": "PROVISIONAL (row 3) - verify against the RFP; no accessed source mentions it (R2)",
        "requirement_frozen": False,
        "limit": {"quantity": "cumulative firing time", "comparator": ">", "value": 15000, "units": "h"},
        "verification_methods": ["test", "analysis"],
        "verification_note": "pre-registered wear / endurance segments (AOL-LF-02) plus a life analysis that uses no "
                             "Hall map, screening candidate or withdrawn number (AOL-LF-01)",
        "open_readings": [oq(ctx, "OQ-VI-04"), od(ctx, "OD13")],
        "rtm_xref": [ctx.rtm("RFP-FIRING")], "lane24_gates": ["G4_firing_life", "P2_cathode"],
        "m16_rows": [9, 11, 18, 20],
        "artifacts": {c: [plan(ctx, "AOL", "AOL-LF-02"), plan(ctx, "AOL", "AOL-LF-01", role="SUPPORTING"),
                          plan(ctx, "PRE", "DQ-HI-LIFE"), hall]
                      + ([plan(ctx, "VI", "VI-LF-05", why="ICP lifetime / cycle requirement (OPEN)")]
                         if c == "hall_icp_neutralizer" else [plan(ctx, "AOL", "AOL-CX-02", role="SUPPORTING")])
                      for c in both},
    })
    # RVM-13 ---------------------------------------------------------------------------------------------- mission
    rows.append({
        "id": "RVM-13", "key": "MISSION_LIFE_GE_26280H", "category": "rfp_recorded",
        "title": "Mission-life basis >= 26,280 h",
        "requirement_text": "Mission life >= 26,280 h (three years), the conservative engineering basis versus the "
                            "repository's 26,000 h until the official wording is verified (row 3).",
        "sources": [ctx.r2("(d) Life", "three years"), ctx.hgm("R1", "26,000 h mission"),
                    ctx.answer(3, "≥26,280 h")],
        "requirement_basis": "OWNER_ENGINEERING_BASIS (row 3) pending the official RFP wording",
        "requirement_frozen": False,
        "limit": {"quantity": "mission life", "comparator": ">=", "value": 26280, "units": "h"},
        "verification_methods": ["analysis"],
        "verification_note": "mission analysis combining life, propellant and duty cycle; each input needs its own "
                             "evidence (RVM-06, RVM-10, RVM-12)",
        "open_readings": [],
        "rtm_xref": [ctx.rtm("RFP-MISSION")], "lane24_gates": ["G5_mission"], "m16_rows": [6, 9, 11, 18],
        "artifacts": cfg_map(lambda c: [hall, plan(ctx, "PRE", "DQ-HI-LIFE"),
                                        plan(ctx, "AOL", "AOL-LF-02", role="SUPPORTING")]),
    })
    # RVM-14 ---------------------------------------------------------------------------------------------- start
    rows.append({
        "id": "RVM-14", "key": "STARTUP_RESTART", "category": "rfp_inferred_from_repo_text",
        "title": "Start-up / restart (ignition, Hall ignition with the electron source, restart, transients)",
        "requirement_text": "Ignite and restart from the off state and record ICP ignition, Hall ignition with ICP "
                            "electrons, restart success and cycle count (row 24); C1 ignition dwell <= 120 s with at "
                            "most two retries in the preliminary protocol, all Xe booked (row 93); start-up transients "
                            "inside < 1.5 kW (row 108) with sequenced peaks (row 112, A9.1 SEQ-*). No ignition / "
                            "restart clause is recorded from the RFP (lane-24 OD14).",
        "sources": [ctx.answer(24, "restart success and cycle count"), ctx.answer(93, "120 s"),
                    ctx.answer(108, "startup transients"), ctx.answer(112, "avoid simultaneous peaks"),
                    ctx.decision("A91", "SEQ-peaks", "peak-class"), ctx.decision("A93", "OQ-VI-05", "Ar")],
        "requirement_basis": "RFP_INFERRED (lane-24 G6 ignition inferred) + owner rows 24, 93, 108, 112",
        "requirement_frozen": False,
        "limit": {"quantity": "C1 ignition dwell per attempt (preliminary protocol)", "comparator": "<=",
                  "value": 120, "units": "s"},
        "verification_methods": ["test", "demonstration"],
        "verification_note": "DQ-HI-IGN hard gate and DQ-HI-RESTART Pareto quantity; the OQ-VI-05 Ar topology control "
                             "is engineering-only, not an architecture gate",
        "open_readings": [od(ctx, "OD5"), od(ctx, "OD14"), oq(ctx, "OQ-A907-01"), oq(ctx, "XA9Q-02")],
        "rtm_xref": [ctx.rtm("RFP-IGN-SUST")], "lane24_gates": ["G6_ignition_sustainment", "P2_cathode"],
        "m16_rows": [11, 12, 14, 18],
        "artifacts": {c: [plan(ctx, "PRE", "DQ-HI-IGN"), plan(ctx, "PRE", "DQ-HI-RESTART", role="SUPPORTING"),
                          B.probe_startup(ctx, c)]
                      + ([plan(ctx, "VI", "VI-SU-01"), plan(ctx, "VI", "VI-SU-02"),
                          plan(ctx, "P1", "P1-S6", role="SUPPORTING", why="engineering-only topology control")]
                         if c == "hall_icp_neutralizer" else [plan(ctx, "VI", "VI-SU-04")])
                      for c in both},
    })
    # RVM-15 ---------------------------------------------------------------------------------------------- neutralization
    rows.append({
        "id": "RVM-15", "key": "NEUTRALIZATION", "category": "derived_from_owner_decision",
        "title": "Beam neutralization / electron-current capacity (ICP-45 or C1)",
        "requirement_text": "hall_icp_neutralizer: ICP-45 capacity I_e,cap = I_e,collector,RFON - "
                            "I_e,collector,RFOFF (signed, discharge-OFF, anode disconnected and floating, Kirchhoff "
                            "admission) >= I_d,max,H1 with the pre-registered one-sided margin before any score-bearing "
                            "point; Hall-ON is NEUTRALIZATION_CONSISTENCY only. hall_c1_reference: heated Xe-fed LaB6 C1 "
                            "sized to the measured / derived current demand (CONTROL_FALLBACK).",
        "sources": [ctx.decision("A91", "ICP-45", "I_e,cap >= I_d,max"),
                    ctx.decision("A93", "OQ-A907-02", "H1_REGISTERED_MAX"),
                    ctx.decision("A94", "P1Q-10", "OFF"), ctx.decision("A94", "P1Q-13", "FLOATING"),
                    ctx.decision("A95", "P1Q-15", "KIRCHHOFF"), ctx.decision("A95", "P1Q-16", "RFOFF"),
                    ctx.answer(88, "sized to the measured/derived current demand"),
                    ctx.a9("control_fallback", "neutralization")],
        "requirement_basis": "OWNER_DECIDED criterion form (A9.1 ICP-45, A9.3-A9.5); I_d,max,H1 is TBD - requires "
                             "measured / registered H-1 operation",
        "requirement_frozen": False,
        "limit": {"quantity": "I_e,cap - I_d,max,H1 (one-sided lower confidence bound)", "comparator": ">",
                  "value": 0, "units": "A"},
        "verification_methods": ["test"],
        "verification_note": "unknown I_d,max,H1 -> NOT_EVALUATED (A9.6 sec. 14); ICP capacity status PENDING_ICP45; "
                             "the 8.33 A stand ceiling is not a requirement (A9.3 OQ-A907-02)",
        "open_readings": [],
        "rtm_xref": [], "lane24_gates": ["P2_cathode"], "m16_rows": [11, 18, 19],
        "artifacts": {
            "hall_icp_neutralizer": [plan(ctx, "P1", "P1-S7", why="ICP-45A discharge-OFF capacity"),
                                     plan(ctx, "ICD", "ICP-45"), plan(ctx, "PRE", "DQ-HI-ECAP"),
                                     plan(ctx, "PRE", "DQ-HI-VCPL"),
                                     plan(ctx, "P1", "P1-S7H", role="SUPPORTING",
                                          why="Hall-ON NEUTRALIZATION_CONSISTENCY, never capacity evidence"),
                                     plan(ctx, "VI", "VI-EX-02", role="SUPPORTING"),
                                     plan(ctx, "RFQ2", "@doc", role="SUPPORTING", why="hardware not procured"),
                                     tk],
            "hall_c1_reference": [plan(ctx, "PRE", "DQ-HI-ECAP"), plan(ctx, "PRE", "DQ-HI-VCPL"),
                                  plan(ctx, "VI", "VI-EX-07", role="SUPPORTING"),
                                  plan(ctx, "RFQ2", "@doc", role="SUPPORTING", why="hardware not procured")],
        },
    })
    # RVM-16 ---------------------------------------------------------------------------------------------- AO
    rows.append({
        "id": "RVM-16", "key": "AO_MATERIAL_COMPATIBILITY", "category": "rfp_inferred_from_repo_text",
        "title": "Atomic-oxygen / material compatibility (AO-beam test; anode, collector, keeper, gas path)",
        "requirement_text": "AO-exposed and O / O2-wetted materials qualified in a dedicated AO programme (AO-beam test "
                            "recorded as 'RFP 4.1a', verify); 316L REJECTED_AS_CURRENT_BASELINE for the flight anode; "
                            "final anode / collector material OPEN until coupon evidence; no graphite flight keeper for "
                            "O / AO exposure; no silver in O / AO-wetted gas-path parts.",
        "sources": [ctx.hgm("R6", "AO-beam test"), ctx.answer(132, "dedicated AO source"),
                    ctx.answer(106, "Flight anode material remains open"), ctx.answer(94, "graphite"),
                    ctx.answer(103, "silver"), ctx.decision("A92", "anode_316L", "316L"),
                    ctx.decision("A91", "A9-03-collector", "coupon")],
        "requirement_basis": "RFP_INFERRED_FROM_REPO_TEXT (R6) + owner rows 94, 103, 106, 132; A9.1 / A9.2",
        "requirement_frozen": False,
        "limit": None,
        "verification_methods": ["test", "inspection"],
        "verification_note": "biased and floating coupons (row 106), ground AO exposure with a fluence witness "
                             "(AOL-EX-01 / -02), post-test SEM/EDS/XPS; P4 screens every candidate fail-closed",
        "open_readings": [od(ctx, "OD12")],
        "rtm_xref": [ctx.rtm("RFP-AO-TEST")], "lane24_gates": [], "m16_rows": [11, 18, 20],
        "artifacts": cfg_map(lambda c: [B.probe_p4(ctx), plan(ctx, "AOL", "AOL-EX-01"),
                                        plan(ctx, "AOL", "AOL-EX-02"), plan(ctx, "PRE", "HI-AO"),
                                        plan(ctx, "VI", "VI-LF-06", role="SUPPORTING")]),
    })
    # RVM-17 ---------------------------------------------------------------------------------------------- thermal
    rows.append({
        "id": "RVM-17", "key": "THERMAL_CLOSURE", "category": "derived_project",
        "title": "Thermal closure (>= 50 K below validated limits, 20 % heat-load margin)",
        "requirement_text": "Every component >= 50 K below its validated continuous-use limit with a 20 % heat-load "
                            "margin (row 86); no unsourced anode target (row 87); ICP_COUPLED_THERMAL and "
                            "ANODE_THERMAL_CLOSURE stay UNRESOLVED until the coupled model has its inputs; never a "
                            "thermal PASS from a negligible-coupling calculation (A9.2).",
        "sources": [ctx.answer(86, "≥50 K margin"), ctx.answer(87, "NO unsourced fixed anode temperature target"),
                    ctx.decision("A92", "icp_coupled_thermal", "UNRESOLVED"),
                    ctx.decision("A92", "anode_approach", "OPEN")],
        "requirement_basis": "DERIVED_PROJECT (not an RFP clause; RTM DER-THERMAL): owner rows 86, 87; A9.2",
        "requirement_frozen": True,
        "limit": {"quantity": "margin below validated continuous-use limit", "comparator": ">=", "value": 50,
                  "units": "K"},
        "verification_methods": ["analysis", "test"],
        "verification_note": "coupled thermal model with Q_Hall->ICP, Q_collector, Q_RF/match, Q_plume and view "
                             "factors (P3) plus thermal-vacuum tests with a measured sink temperature (row 131)",
        "open_readings": [oq(ctx, i) for i in ("OQ-A907-03", "OQ-A907-05", "OQ-A907-09", "OQ-A907-10")],
        "rtm_xref": [ctx.rtm("DER-THERMAL")], "lane24_gates": ["P1_thermal"], "m16_rows": [13, 20, 21],
        "artifacts": cfg_map(lambda c: [B.probe_p3(ctx, c), plan(ctx, "VI", "VI-LF-04", role="SUPPORTING")]),
    })
    # RVM-18 ---------------------------------------------------------------------------------------------- IC
    rows.append({
        "id": "RVM-18", "key": "INDIGENOUS_CONTENT", "category": "rfp_recorded",
        "title": "Indigenous content >= 75 % total",
        "requirement_text": "Total indigenous content >= 75 % (subsystem minima thruster 0.80, intake 0.80, compressor "
                            "0.60, PSE 0.70 exist only in in-repo code, R2; not found in any accessed source).",
        "sources": [ctx.r2("(d) Indigenous content", "75 percent"), ctx.hgm("R2", "ic_total_min 0.75")],
        "requirement_basis": rfp_basis, "requirement_frozen": False,
        "limit": {"quantity": "indigenous content (total)", "comparator": ">=", "value": 75, "units": "%"},
        "verification_methods": ["inspection"],
        "verification_note": "inspection of the selected-part bill of materials and supplier origin; no part is "
                             "selected (quotation only)",
        "open_readings": [od(ctx, "OD12")],
        "rtm_xref": [ctx.rtm("RFP-IC")], "lane24_gates": [], "m16_rows": [],
        "artifacts": cfg_map(lambda c: [plan(ctx, "RFQ2", "@doc",
                                             why="quotation-only packages; no part selected")]),
    })
    # RVM-19 ---------------------------------------------------------------------------------------------- redundancy
    rows.append({
        "id": "RVM-19", "key": "ELECTRONICS_REDUNDANCY", "category": "rfp_inferred_from_repo_text",
        "title": "No single-point failure in electronics (recorded; verify) vs limited redundancy (row 55)",
        "requirement_text": "'Redundancy per RFP: no single-point failure in electronics' is recorded only in a code "
                            "docstring (R7, unverified). Owner row 55 sets limited redundancy (dual series isolation on "
                            "the high-pressure Xe path, critical sensing / FDIR redundancy; no duplicated thruster, ICP "
                            "or full PPU at this stage). Both are carried side by side; see RVMQ-01.",
        "sources": [ctx.hgm("R7", "no single-point failure in electronics"),
                    ctx.answer(55, "LIMITED redundancy"), ctx.answer(90, "two independent isolation valves")],
        "requirement_basis": "RFP_INFERRED_FROM_REPO_TEXT (R7) - verify against the RFP document",
        "requirement_frozen": False,
        "limit": None,
        "verification_methods": ["analysis", "inspection"],
        "verification_note": "FMEA / failure-tree analysis of the selected electronics (none selected)",
        "open_readings": [od(ctx, "OD12")],
        "rtm_xref": [ctx.rtm("RFP-REDUND")], "lane24_gates": [], "m16_rows": [12, 14],
        "artifacts": cfg_map(lambda c: [plan(ctx, "BUS", "@doc", why="supply partition exists; no FMEA")]),
    })
    rows.extend(build_rfp_rebase_rows(B, ctx, hall, cfg_map, rfp_basis))
    return rows


def build_rfp_rebase_rows(B, ctx, hall, cfg_map, rfp_basis):
    """RFP re-base rows (AG-15). RVM-20..RVM-26 cover registered RFP clauses no earlier row carried; RVM-27 is the A9.12
    owner mount-heat allocation. Their RFP clause sources are added by rfp_rebase.apply (single mapping table); the
    requirement texts paraphrase the verbatim clauses, which are copied into each row's sources. Tokens checked here
    fail closed when the registered transcription does not contain them."""
    plan, absent = B.plan, B.absent
    rows = []
    ctx.rfp("RFP-P18-12", "Discrete interface for thruster operation")
    ctx.rfp("RFP-P18-12", "Necessary hardware drivers to be part of propulsion system")
    # RVM-20 ---------------------------------------------------------------------------------------------- 1553B
    rows.append({
        "id": "RVM-20", "key": "ELECTRICAL_INTERFACE_MIL1553B", "category": "rfp_registered",
        "title": "MIL-1553B interface with the satellite onboard computer + discrete thruster interface + hardware "
                 "drivers inside the propulsion system",
        "requirement_text": "MIL-1553B interface with the satellite onboard computer for configuration and for "
                            "high-rate data-logging with the data recorder; discrete interface for thruster operation; "
                            "the necessary hardware drivers are part of the propulsion system (RFP-P18-12). The power "
                            "system electronics take power from the satellite bus and provide the ABEP voltages and "
                            "currents (RFP-P18-01).",
        "sources": [], "requirement_basis": rfp_basis, "requirement_frozen": False,
        "limit": {"quantity": "spacecraft data / command interface", "comparator": "is",
                  "value": "MIL-1553B + discrete thruster-operation interface (as printed)", "units": "-"},
        "verification_methods": ["inspection", "test", "demonstration"],
        "verification_note": "interface control document (inspection), MIL-1553B configuration / data-logging test "
                             "with a representative onboard-computer bus, discrete-line thruster operation demonstrated "
                             "with the drivers inside the propulsion system; no data-interface artifact exists",
        "open_readings": [], "rtm_xref": [], "lane24_gates": [], "m16_rows": [12, 14],
        "artifacts": cfg_map(lambda c: [
            absent(ctx, "RFP-P18-12", "an interface control document and a MIL-1553B configuration / high-rate "
                                      "data-logging test with the satellite onboard computer plus a discrete-interface "
                                      "thruster-operation demonstration, drivers inside the propulsion system"),
            plan(ctx, "BUS", "@doc", role="SUPPORTING", why="power boundary only; no data interface defined"),
        ]),
    })
    # RVM-21 ---------------------------------------------------------------------------------------------- ENTEST
    ctx.rfp("RFP-P19-04", "PSLV/ SSLV")
    ctx.rfp("RFP-P19-04", "radiation, thermal and ThermoVac")
    rows.append({
        "id": "RVM-21", "key": "ENVIRONMENTAL_QUALIFICATION_ENTEST", "category": "rfp_registered",
        "title": "Environmental qualification (ENTEST): launch vibration / shock (PSLV / SSLV or DRDO-decided LV), AO "
                 "erosion, radiation, thermal, ThermoVac, 3-year VLEO life",
        "requirement_text": "The product qualifies the launch vibrations and shock (launch loads of PSLV / SSLV or any "
                            "other launch vehicle decided by DRDO at PDR) and the atomic-oxygen erosion, radiation, "
                            "thermal and ThermoVac specifications for a VLEO orbit with a 3-year mission life; all "
                            "intake, compressor and thruster parts take care of nascent atomic-oxygen erosion for the "
                            "lifetime (RFP-P19-04). ENTEST specifications are provided at PDR: no numeric level is "
                            "carried (not invented). Space-qualified materials and processes for the QM (RFP-P19-02).",
        "sources": [], "requirement_basis": rfp_basis, "requirement_frozen": False,
        "limit": None,
        "verification_methods": ["test", "analysis"],
        "verification_note": "QM ENTEST campaign against the PDR-issued specification (milestone 5, RFP-P21-02); AO "
                             "erosion through the AO programme (RVM-16); thermal / ThermoVac with the coupled thermal "
                             "model inputs (RVM-17)",
        "open_readings": [], "rtm_xref": [], "lane24_gates": [], "m16_rows": [13, 16],
        "artifacts": cfg_map(lambda c: [
            absent(ctx, "RFP-P19-04", "ENTEST qualification test reports of the QM units against the ENTEST "
                                      "specification issued at PDR (launch vibration / shock, AO erosion, radiation, "
                                      "thermal, ThermoVac)"),
            plan(ctx, "AOL", "AOL-EX-01", why="ground AO exposure (AO-erosion part only)"),
            plan(ctx, "AOL", "AOL-EX-02", role="SUPPORTING"),
            plan(ctx, "P3", "@doc", role="SUPPORTING", why="coupled thermal framework (inputs TBD)"),
        ]),
    })
    # RVM-22 ---------------------------------------------------------------------------------------------- test approach
    sub = [("a", "Coating materials and surface tests with Atomic Oxygen beam exposure"),
           ("b", "Creation of rarefied gas with prescribed mg/sec and velocity"),
           ("c", "Minimum functional performance testing for EM and QM"),
           ("d", "approved by PMMG/SPMMG")]
    for _, tok in sub:
        ctx.rfp("RFP-P19-06", tok)
    rows.append({
        "id": "RVM-22", "key": "RFP_TEST_APPROACH", "category": "rfp_registered",
        "title": "RFP test approach 4.1 a-d (AO-beam coating tests; rarefied-gas intake erosion; EM / QM force, Isp, "
                 "efficiency; expert-committee-approved test plan) and ground demonstration",
        "requirement_text": "System performance demonstrated by: a) coating-material and surface tests with "
                            "atomic-oxygen beam exposure and erosion-yield measurement; b) rarefied gas created with "
                            "prescribed mg/s and velocity to test the intake erosion process; c) minimum functional "
                            "performance testing of EM and QM in integration mode for force, with variable air intake "
                            "(mg/s), Isp and total-system efficiency; d) test-plan document reviewed / finalized by an "
                            "expert committee and approved by PMMG / SPMMG (RFP-P19-06). Only ground demonstration in "
                            "a simulated environment and space-qualification testing is desired (RFP-P20-02).",
        "sources": [], "requirement_basis": rfp_basis, "requirement_frozen": False,
        "limit": None,
        "verification_methods": ["test", "inspection"],
        "verification_note": "a) AO programme (AOL-EX-01 / -02); b) no rarefied-gas intake-erosion facility or test "
                             "record exists; c) HI-ABS absolute demonstration plan (force at registered delivered feed "
                             "states; Isp and total-system efficiency need the same measured thrust); d) committee / "
                             "PMMG approval record (inspection)",
        "sub_requirements": [{"item": i, "rfp_clause": "RFP-P19-06", "token": t} for i, t in sub],
        "open_readings": [], "rtm_xref": [], "lane24_gates": [], "m16_rows": [1, 9],
        "artifacts": cfg_map(lambda c: [
            plan(ctx, "AOL", "AOL-EX-01", why="4.1 a) AO-beam / erosion-yield"),
            absent(ctx, "RFP-P19-06", "4.1 b) a rarefied-gas source with prescribed mg/s and velocity and an intake "
                                      "erosion test record", suffix="-b"),
            plan(ctx, "PRE", "HI-ABS", why="4.1 c) EM / QM force with variable intake mg/s, Isp, efficiency"),
            absent(ctx, "RFP-P19-06", "4.1 d) the test-plan document reviewed / finalized by the expert committee and "
                                      "approved by PMMG / SPMMG", suffix="-d"),
        ]),
    })
    # RVM-23 ---------------------------------------------------------------------------------------------- ISO / ATP
    ctx.rfp("RFP-P20-01", "ATP document")
    rows.append({
        "id": "RVM-23", "key": "ISO_CERTIFICATION_ATP", "category": "rfp_registered",
        "title": "ISO certification; acceptance / qualification per ATP (finalized after DDR / CDR); testing to "
                 "MIL / ASTM / BIS / ESS standards",
        "requirement_text": "Deliverables match the Para 2 parameters (4.2 acceptance); the company is ISO certified; "
                            "acceptance / qualification based on the ATP document prepared from the Para 2 parameters "
                            "and finalized after DDR / CDR; testing as per applicable standards (MIL / ASTM / BIS etc.) "
                            "/ ESS specification (RFP-P20-01).",
        "sources": [], "requirement_basis": rfp_basis, "requirement_frozen": False,
        "limit": None,
        "verification_methods": ["inspection"],
        "verification_note": "inspection of the ISO certificate and of the ATP document after DDR / CDR; no ATP "
                             "exists (the RVM is not an ATP)",
        "open_readings": [], "rtm_xref": [], "lane24_gates": [], "m16_rows": [],
        "artifacts": cfg_map(lambda c: [
            absent(ctx, "RFP-P20-01", "the company ISO certificate and the ATP document finalized after DDR / CDR "
                                      "(Para 2 parameters; MIL / ASTM / BIS / ESS test standards)"),
        ]),
    })
    # RVM-24 ---------------------------------------------------------------------------------------------- M4 exit
    rows.append({
        "id": "RVM-24", "key": "MILESTONE4_EXIT_QUALIFIED_THRUSTER_O_N2", "category": "rfp_registered",
        "title": "Exit criterion: EM of the ABEP system + qualified electric thruster with O and N2 as propellant at "
                 "milestone 4 (partial success)",
        "requirement_text": "Successful realization of the Engineering Model of the ABEP system and realization of a "
                            "qualified electric thruster with O and N2 as propellant at milestone 4 can be considered "
                            "a partial success of the project (RFP-P20-03; milestone 4 = QM PSE and thruster testing, "
                            "RFP-P21-01). N2 + O2 surrogate data are NO_ATOMIC_O and never atomic-O evidence; "
                            "compliance gate CG-N2-AO (A9.14 OD12).",
        "sources": [], "requirement_basis": rfp_basis, "requirement_frozen": False,
        "limit": {"quantity": "propellants of the qualified electric thruster at milestone 4", "comparator": "includes",
                  "value": "O and N2", "units": "-"},
        "verification_methods": ["test", "demonstration"],
        "verification_note": "qualification test record of the thruster on N2 and on O (atomic-O source, HI-AO) at "
                             "milestone 4; Ar / Xe data never count",
        "open_readings": [], "rtm_xref": [], "lane24_gates": [], "m16_rows": [9],
        "artifacts": cfg_map(lambda c: [
            absent(ctx, "RFP-P20-03", "a qualification test record of the electric thruster operated on O and on N2 "
                                      "at milestone 4"),
            plan(ctx, "PRE", "HI-AO"), plan(ctx, "PRE", "DQ-HI-SUST"), hall,
        ]),
    })
    # RVM-25 ---------------------------------------------------------------------------------------------- milestones
    ms = [(1, "RFP-P20-04", "T0+09", "15%"), (2, "RFP-P20-05", "T0+12", "10%"), (3, "RFP-P20-06", "T0+20", "20%"),
          (4, "RFP-P21-01", "T0+24", "35%"), (5, "RFP-P21-02", "T0+36", "20%")]
    milestones = []
    for n, cid, due, share in ms:
        rec = ctx.rfp(cid, due)
        ctx.rfp(cid, share)
        milestones.append({"milestone": n, "rfp_clause": cid, "due": due + " months", "share": share,
                           "verbatim": rec["verbatim"]})
    rows.append({
        "id": "RVM-25", "key": "MILESTONE_SCHEDULE_DELIVERABLES", "category": "rfp_registered",
        "title": "Milestone schedule and deliverables M1-M5 (T0+9 / +12 / +20 / +24 / +36 months) and the EM -> QM "
                 "processing flow",
        "requirement_text": "Milestones and deliverables as printed (RFP-P20-04 .. RFP-P21-02): M1 PDR-1 hardware "
                            "(T0+09, 15 %), M2 PDR-2 algorithms / software / test plan (T0+12, 10 %), M3 CDR with EM "
                            "thruster and PSE demonstrated with storage input, not intake (T0+20, 20 %), M4 EM intake + "
                            "QM PSE and thruster (T0+24, 35 %), M5 QM integration, ENTEST and delivery (T0+36, 20 %); "
                            "EM -> QM processing flow (RFP-P17-01). T0 is not set.",
        "sources": [], "requirement_basis": rfp_basis, "requirement_frozen": False,
        "limit": {"quantity": "QM integration, ENTEST qualification and delivery (milestone 5)", "comparator": "<=",
                  "value": "T0+36", "units": "months"},
        "verification_methods": ["inspection", "demonstration"],
        "verification_note": "inspection of the approved milestone deliverables (design documents, CAD / EDA models, "
                             "test plans and results) at each review; none exists and T0 is not set",
        "milestones": milestones,
        "open_readings": [], "rtm_xref": [], "lane24_gates": [], "m16_rows": [],
        "artifacts": cfg_map(lambda c: [
            absent(ctx, "RFP-P20-04", "the approved milestone deliverables M1-M5 (PDR-1, PDR-2, CDR, EM intake + QM "
                                      "PSE / thruster, QM integration / ENTEST / delivery) against a set T0"),
        ]),
    })
    # RVM-26 ---------------------------------------------------------------------------------------------- uN stand
    ctx.rfp("RFP-P27-01", "Ultra High Vacuum Test Facility")
    rows.append({
        "id": "RVM-26", "key": "THRUST_MEASUREMENT_AND_TEST_INFRASTRUCTURE", "category": "rfp_registered",
        "title": "Micro-newton-level thrust measurement system; UHV test facility and low-thrust measurement setup "
                 "(Part IV(B), no waivers)",
        "requirement_text": "Thrust measurement system capable of measuring micro-newton-level thrust (Part IV(C) 5 "
                            "evaluation criterion: in-house 10 / consortium 5 / sub-contract 0 marks, RFP-P30-01); "
                            "ultra-high-vacuum test facility for propulsion-system testing and a low-thrust measurement "
                            "setup, in-house / consortium / sub-contract (RFP-P27-01; no waivers for Part IV(B), "
                            "RFP-P21-03).",
        "sources": [], "requirement_basis": rfp_basis, "requirement_frozen": False,
        "limit": {"quantity": "thrust measurement capability", "comparator": "resolves",
                  "value": "micro-newton level (as printed; no numeric resolution stated)", "units": "-"},
        "verification_methods": ["inspection", "demonstration", "test"],
        "verification_note": "calibration / resolution demonstration of the stand at micro-newton level and a facility "
                             "availability record; the mN-level torsional-stand plan of RVM-02 (row 115) is not "
                             "evidence of micro-newton capability",
        "open_readings": [], "rtm_xref": [], "lane24_gates": [], "m16_rows": [9],
        "artifacts": cfg_map(lambda c: [
            absent(ctx, "RFP-P30-01", "a calibration record demonstrating micro-newton-level thrust resolution of "
                                      "the thrust measurement system"),
            absent(ctx, "RFP-P27-01", "an availability record of the UHV test facility and the low-thrust "
                                      "measurement setup (in-house / consortium / sub-contract)"),
            plan(ctx, "PRE", "DQ-HI-TABS", role="SUPPORTING", why="mN-level absolute thrust gate (not uN)"),
            plan(ctx, "VI", "VI-HD-03", role="SUPPORTING"),
        ]),
    })
    # RVM-27 ---------------------------------------------------------------------------------------------- 50 W mount
    rows.append({
        "id": "RVM-27", "key": "MOUNT_HEAT_50W_ALLOCATION", "category": "owner_internal_allocation",
        "title": "Steady heat conducted into the spacecraft mounting interface <= 50 W (A9.12 S5.4 provisional owner "
                 "allocation; 100 W contingency, 25 W stretch)",
        "requirement_text": "Thermally isolated H-1 mount + dedicated radiator; 50 W is the provisional governing "
                            "allocation for steady heat conducted into the spacecraft mounting interface until the "
                            "spacecraft thermal ICD exists (100 W contingency / sensitivity only, 25 W stretch; a "
                            "design meeting only 100 W is not closed). An owner allocation, not a spacecraft or RFP "
                            "requirement.",
        "sources": [ctx.decision("A912", "OQ-A907-06", "50 W")],
        "requirement_basis": "OWNER_ALLOCATION (A9.12 S5.4 OQ-A907-06): provisional until the spacecraft thermal ICD",
        "requirement_frozen": True,
        "limit": {"quantity": "steady heat conducted into the spacecraft mounting interface", "comparator": "<=",
                  "value": 50, "units": "W"},
        "verification_methods": ["analysis", "test"],
        "verification_note": "P3 mount-heat report at the 25 / 50 / 100 W cases (no coupled result: inputs "
                             "INCOMPLETE_EVIDENCE) plus a thermal-vacuum measurement of the conducted interface heat",
        "open_readings": [], "rtm_xref": [], "lane24_gates": [], "m16_rows": [13, 16],
        "artifacts": cfg_map(lambda c: [
            plan(ctx, "P3", "@doc", why="mount-heat report (25 / 50 / 100 W cases); coupled network inputs TBD"),
        ]),
    })
    return rows

"""Build the DRDO TDF ABEP requirement traceability matrix (rtm_v1.json + RTM.md).

Single source of truth for the RTM. Run from the repository root:
    python docs/traceability/build_rtm.py          # (re)write both files
    python docs/traceability/build_rtm.py --check  # exit 1 if the committed files are stale

Evidence discipline (CLAUDE.md rules 6 and 10, docs/EVIDENCE.md): the RFP document is NOT in the repository. Every
requirement cites the in-repo text it came from and carries page_ref "verify against RFP document" (or says it is
project-derived). No clause numbers, page numbers or values are invented here. This matrix claims no compliance.

Cross-lane links. The pass/fail criteria for the same RFP requirements live in the lane-24 hard-gate matrix
(docs/architecture_comparison/hard_gates/). Each row here names the gate/criterion ids it maps to. The build pins the
sha256 of the cross-referenced files it summarises (hard-gate matrix, hard-gate status, Bundle 1 v3), so `--check`
reports STALE when any of them changes and this matrix has to be re-read against it. Those files are resolved lazily;
a missing one is a clear error, not a silent fallback.
"""
from __future__ import annotations
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
JSON_PATH = os.path.join(HERE, "rtm_v1.json")
MD_PATH = os.path.join(HERE, "RTM.md")

BASE_COMMIT = "d07249bef0f9d415cad1a33c5a427cfc105f7835"
HG_MATRIX = "docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json"
HG_STATUS = "docs/architecture_comparison/hard_gates/hard_gate_status_v1.json"
HG_REGISTER = "docs/architecture_comparison/hard_gates/evidence_register_v1.json"
BUNDLE1 = "docs/milestones/bundle1/bundle1_v3.json"
PINNED_XREFS = (HG_MATRIX, HG_STATUS, HG_REGISTER, BUNDLE1)

PAGE = "verify against RFP document"
ENV = ("CLAUDE.md, 'What this is' section: RFP envelope summary (secondary in-repo transcription; "
       "the RFP document is not in the repository)")
CONST = ("abep_sim/constants.py, class RFPConstraints (docstring says 'Hard limits from Part III Para 2 of the RFP'; "
         "that clause reference is itself unverified in-repo text)")
H3 = ("All absolute Hall results from the superseded 0-D closure (v1.2-v1.6) are withdrawn (CLAUDE.md 'Superseded / "
      "withdrawn'); gate 3 (multi-point Hall validation) is FAIL and the credible transport set is empty, so no Hall "
      "performance number may be used as evidence of compliance.")
NOT_RFP = "not an RFP clause (project-derived)"
HGS = "hard-gate status: UNDETERMINED for hall_only, rf_hall and ecr_hall (evidence register empty); nothing eliminated"


def _src(where: str, extra: list[str] | None = None) -> dict:
    d = {"where": where, "page_ref": PAGE}
    if extra:
        d["corroborating_in_repo"] = extra
    return d


def _val(q: str, lim: str, unit: str, where: str) -> dict:
    return {"quantity": q, "limit": lim, "unit": unit, "value_source": where, "evidence_class": "assumed",
            "evidence_note": "requirement limit transcribed from an in-repo summary, not read from the RFP document; verify"}


def _hg(gates: list[str], criteria: list[str], note: str, owner_decisions: list[str] | None = None) -> dict:
    """Cross-reference to the lane-24 hard-gate matrix (gate ids, criterion ids, open owner decisions OD*)."""
    return {"gates": gates, "criteria": criteria, "open_owner_decisions": owner_decisions or [], "note": note}


def _req(id, category, title, statement, value, source, model_quantities, current_evidence, status, gate3_dependent,
         verification_method, open_gap, hard_gate_xref, rfp_record_refs, verification_status="not_verified"):
    return dict(id=id, category=category, title=title, statement=statement, value=value, source=source,
                rfp_record_refs=rfp_record_refs, hard_gate_xref=hard_gate_xref,
                model_quantities=model_quantities, current_evidence=current_evidence, status=status,
                gate3_dependent=gate3_dependent, verification_method=verification_method,
                verification_status=verification_status, open_gap=open_gap)


def _mq(ref, role):
    return {"ref": ref, "role": role}


def _ev(ref, note):
    return {"ref": ref, "note": note}


EV_HGS = _ev(HG_STATUS, HGS)
EV_ENS = _ev("hallthruster_bridge/ensemble/transport_ensemble_v0.json", "members = [] (credible set empty)")
EV_V1 = _ev("hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_decision.json",
            "P5-N2 v1 vacuum: all nine screening candidates INCONCLUSIVE / NOT ELIGIBLE; promotable = [] (permanent for v1)")
EV_B1 = _ev(BUNDLE1, "Bundle 1 v3 (DRAFT_FOR_OWNER_REVIEW): outcome NO_BASELINE_YET; no architecture eliminated or singled out")

REQUIREMENTS = [
    _req("RFP-ALT", "rfp_envelope", "Operating altitude band",
         "Operate the ABEP in very low Earth orbit within 180-230 km.",
         _val("altitude", "180-230", "km", ENV),
         _src(ENV, [CONST + " (alt_min_km, alt_max_km)", "README.md line 3"]),
         [_mq("abep_sim/atmosphere.py::atmosphere", "density/composition vs altitude and solar state (frozen NRLMSIS 2.1 dataset by default)"),
          _mq("abep_sim/atmosphere.py::orbital_velocity", "ram velocity"),
          _mq("abep_sim/mission_env.py::propagate", "altitude history under thrust and drag"),
          _mq("abep_sim/constants.py::RFPConstraints", "alt_min_km / alt_max_km")],
         [_ev("abep_sim/data/atmosphere_msis21_v1.json", "frozen atmosphere provenance (rule 1)"),
          _ev("CLAUDE.md", "gate table: gate 1 clean-install reproducibility = pass (frozen atmosphere)"),
          _ev("abep_sim/data/golden_v1.json", "golden case_atmosphere; gate 6 = pass per CLAUDE.md gate table (not re-run in this lane)"),
          _ev(HG_MATRIX, "altitude is an envelope dimension (coverage_dimensions.altitude_km) of G1, G2 and G6, not a gate of its own; OD2 (envelope quantifier) and OD3 (atmosphere states) open")],
         "partial", True, ["analysis"],
         "Environment definition is modeled. Holding an altitude inside the band needs thrust >= drag, which depends on "
         "Hall performance (gate 3). Spacecraft ram area / ballistic coefficient is a DRDO input not in the repository "
         "(docs/HISTORY.md says it must be requested). Whether the requirement holds at every point of the band or at "
         "some operating altitude is owner decision OD2.",
         _hg(["G1_thrust", "G2_bus_power", "G6_ignition_sustainment"], [],
             "envelope dimension of these gates, not a gate", ["OD2", "OD3"]),
         ["R1", "R2", "R3"]),
    _req("RFP-THR-MIN", "rfp_envelope", "Thrust floor (12 mN)",
         "Lower edge of '12-25 mN'. The project reads it as '12 mN sustained on air' (docs/HISTORY.md constraint table); "
         "whether the floor must be met on atmospheric propellant alone or with Xe augmentation is open (lane 24 OD4). "
         "Verify against the RFP wording.",
         _val("thrust", ">= 12", "mN", ENV),
         _src(ENV, [CONST + " (thrust_min_mN)", "docs/HISTORY.md constraint table (chk_thrust_air_ge_req)"]),
         [_mq("abep_sim/archengine.py::rfp_preset", "T_min_mN constraint"),
          _mq("abep_sim/archengine.py::close_architecture", "constrained closure; its Hall branch still calls the superseded 0-D plasma_devices.hall_run_coupled"),
          _mq("abep_sim/hall_map.py::HallMap", "intended source of Hall thrust (loads admitted ensemble members only; none exist)"),
          _mq("abep_sim/system.py::evaluate", "legacy check 'thrust_air_ge_req' (0-D Hall; results withdrawn)")],
         [EV_ENS, EV_V1, EV_HGS,
          _ev("CLAUDE.md", "gate 3 FAIL; gate 4 conditional on gate 3; absolute Hall numbers withdrawn")],
         "blocked_by_gate_3", True, ["analysis", "test"],
         H3 + " Needs an admitted closure, Vyovrinda-specific Hall maps, then a thruster test (or a Milestone-A hard bound "
         "or hardware measurement under the lane-24 evidence policy).",
         _hg(["G1_thrust"], ["G1.thrust_floor"], "binds under both OD1 readings; counts for PASS and FAIL",
             ["OD1", "OD2", "OD4"]),
         ["R1", "R2", "R3"]),
    _req("RFP-THR-MAX", "rfp_envelope", "Thrust 25 mN edge (reading open)",
         "Upper edge of '12-25 mN'. Two readings are recorded and the owner has not chosen (lane 24 OD1): (i) an operating "
         "window, 25 mN as a cap (lane 24 G1.thrust_ceiling: minimum stable thrust <= 25 mN); (ii) '25 mN peak with Xe "
         "topping' (docs/HISTORY.md constraint table; lane 24 G1.peak_capability_25mN: peak capability >= 25 mN). This "
         "matrix does not choose. Note: abep_sim/constants.py thrust_max_mN and archengine rfp_preset T_max_mN apply it "
         "as a cap on delivered thrust (reading i). Verify against the RFP wording.",
         _val("thrust", "25 mN edge: '<= 25' as a cap (reading i) or '>= 25' as a peak capability with Xe (reading ii); OD1 open",
              "mN", ENV),
         _src(ENV, [CONST + " (thrust_max_mN)", "docs/HISTORY.md constraint table (chk_thrust_peak_25mN)"]),
         [_mq("abep_sim/archengine.py::rfp_preset", "T_max_mN constraint (applied as a cap, reading i)"),
          _mq("abep_sim/mission5.py::run_mission_generic", "thrust cap in the mission ROM"),
          _mq("abep_sim/hall_map.py::HallMap", "intended Hall thrust source (no admitted members)")],
         [EV_ENS, EV_HGS,
          _ev(HG_MATRIX, "OD1 open: G1.thrust_ceiling (reading i) and G1.peak_capability_25mN (reading ii) count toward PASS only; neither can FAIL G1 until the owner decides"),
          _ev("CLAUDE.md", "gate 3 FAIL")],
         "blocked_by_gate_3", True, ["analysis", "test"],
         H3 + " The reading of '25 mN' (cap vs peak capability with Xe) is an open owner decision (OD1); the RFP text is "
         "needed to settle it.",
         _hg(["G1_thrust"], ["G1.thrust_ceiling", "G1.peak_capability_25mN"],
             "PASS-only criteria; one binds per OD1 reading", ["OD1", "OD2"]),
         ["R1", "R2", "R3"]),
    _req("RFP-PWR", "rfp_envelope", "Power ceiling",
         "Power below 1.5 kW. Whether this limit refers to the common propulsion bus-power boundary bus_power_boundary_v1 "
         "is TBD (docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md section 5 rule 6: settling it "
         "requires the RFP text of Part III Para 2; archengine applies it at the PPU bus input, archengine.py:641). Mode "
         "scope (every mode vs steady only) is lane 24 OD8. docs/HISTORY.md reads it as total power incl. PPU, "
         "compressor and Xe peak. Verify against the RFP wording.",
         _val("power", "< 1.5", "kW", ENV),
         _src(ENV, [CONST + " (power_max_W)"]),
         [_mq("abep_sim/archengine.py::DesignConstraints", "P_bus_max_W (checked against the PPU bus input)"),
          _mq("abep_sim/arch_boundary.py::bus_power_ledger", "bus_power_boundary_v1 ledger (P_bus_W) for hall_only / rf_hall / ecr_hall; not wired into archengine"),
          _mq("abep_sim/ppu.py::default_ppu", "converter set (anode, magnet, keeper, heater, compressor motor, aux)"),
          _mq("abep_sim/ppu.py::load_modes", "startup / steady / peak electrical loads"),
          _mq("abep_sim/compressor.py::DragCompressor", "compressor shaft power")],
         [_ev("docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md", "bus_power_boundary_v1 definition; section 5 rule 6: whether the RFP '< 1.5 kW' refers to this boundary is TBD; archengine applies it at the PPU bus input"),
          _ev("schemas/architecture_comparison/bus_power_boundary_v1.json", "machine-readable boundary (common and pre-ionizer components)"),
          EV_HGS,
          _ev("abep_sim/data/golden_v1.json", "energy-ledger residual golden (gate 6 pass per CLAUDE.md)")],
         "blocked_by_gate_3", True, ["analysis", "test"],
         "Non-Hall bus terms (PPU losses, compressor, magnets, heater/keeper) are modeled, and the common boundary is "
         "defined. The dominant Hall discharge power at the required thrust is not available (gate 3); every boundary "
         "load and efficiency is TBD for all three architectures. Open: which boundary the RFP limit refers to "
         "(BUS_POWER_BOUNDARY.md rule 6) and its mode scope (OD8).",
         _hg(["G2_bus_power"], ["G2.bus_power_max"], "counts for PASS and FAIL", ["OD4", "OD8"]),
         ["R1", "R2", "R3"]),
    _req("RFP-MASS", "rfp_envelope", "Mass ceiling",
         "Mass below 40 kg. docs/HISTORY.md reads it as total incl. intake, compressor, PSE, Xe + tank, structure and 10 % "
         "margin; strict vs inclusive and the margin policy are lane 24 OD7. Verify against the RFP wording.",
         _val("mass", "< 40", "kg", ENV),
         _src(ENV, [CONST + " (mass_max_kg)"]),
         [_mq("abep_sim/mass_bom.py::build_bom", "CBE / MGA / MEV roll-up (legacy)"),
          _mq("abep_sim/mass_bom.py::rollup", "architecture mass BOM v1 roll-up (refuses TBD items)"),
          _mq("abep_sim/mass_bom.py::plausibility_screen", "lower-bound screen feeding the G3 FAIL side"),
          _mq("abep_sim/mass_bom.py::xe_tank", "Xe tank sizing"),
          _mq("abep_sim/mass_bom.py::hall_magnetic_circuit", "Hall magnetic-circuit mass from required flux"),
          _mq("abep_sim/thermal.py::size_radiator", "radiator sizing")],
         [_ev("docs/architecture_comparison/mass_bom/mass_bom_v1.json", "architecture mass BOM skeleton: no item has a sourced CBE or lower bound; strict roll-up refused for all three; screen LOWER_BOUNDS_UNAVAILABLE"),
          EV_HGS,
          _ev("CLAUDE.md", "earlier absolute mass closures are listed as withdrawn ('Superseded / withdrawn')")],
         "partial", True, ["analysis", "inspection"],
         "Mass accounting exists, but no item has a sourced CBE; Vyovrinda's own Hall geometry and B(z) are not defined, "
         "and the Xe load and radiator size depend on Hall performance (gate 3). Final verification needs a weighed BoM "
         "(inspection).",
         _hg(["G3_mass"], ["G3.mass_mev"], "closure-independent; counts for PASS and FAIL", ["OD7", "OD10"]),
         ["R1", "R2", "R3"]),
    _req("RFP-MISSION", "rfp_envelope", "Mission duration",
         "Mission duration of 26,000 h.",
         _val("mission duration", "26000", "h", ENV),
         _src(ENV, [CONST + " (mission_hours; code comment '3 years')", "abep_sim/transient.py module docstring"]),
         [_mq("abep_sim/mission_env.py::propagate", "J2 propagator with eclipse"),
          _mq("abep_sim/mission5.py::run_mission_generic", "mission ROM over RFP.mission_hours"),
          _mq("abep_sim/transient.py::run_mission", "legacy transient (duty cycle from density vs thrust)")],
         [_ev("CLAUDE.md", "gate 5 numerical convergence = pass; gate 4 mission UQ conditional on gate 3"),
          _ev("abep_sim/data/golden_v1.json", "golden case_mission"),
          EV_HGS],
         "partial", True, ["analysis"],
         "Propagator and mission ROM exist; mission closure needs Hall thrust and power (gate 3) and a DRDO spacecraft "
         "definition. Lane 24 G5 reads it as calendar capability per element, not as a drag-compensation requirement.",
         _hg(["G5_mission"], ["G5.mission_capability"], "counts for PASS and FAIL", ["OD10"]),
         ["R1", "R2", "R3", "R5"]),
    _req("RFP-FIRING", "rfp_envelope", "Firing (ignition) life",
         "Cumulative firing time above 15,000 h ('> 15,000 h firing' in CLAUDE.md; '>15,000 h ignition' in docs/HISTORY.md "
         "and abep_sim/transient.py; wording is lane 24 OD13).",
         _val("firing time", "> 15000", "h", ENV),
         _src(ENV, [CONST + " (ignition_hours)"]),
         [_mq("abep_sim/life.py::hall_channel_life", "sputter + AO wall recession"),
          _mq("abep_sim/life.py::cathode_life", "cathode life / start cycles"),
          _mq("abep_sim/life.py::compressor_life", "bearing life"),
          _mq("abep_sim/life.py::reliability", "R(15,000 h), R(26,000 h)"),
          _mq("abep_sim/thermal_life.py::solve_node_temperature", "thermal/life framework (margins; not wired into archengine)"),
          _mq("abep_sim/hall_map.py::HallMap", "erosion inputs only when wall_life_trustworthy")],
         [_ev("hallthruster_bridge/hall_map_schema_v1.json", "wall ion flux/energy fields defined; life use needs wall_life_trustworthy"),
          _ev("docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md", "framework only; every design input TBD; no life number for any architecture"),
          _ev("docs/evidence/wall_life/WALL_LIFE_EVIDENCE.md", "sputter/erosion yield evidence; the solver wall ion flux is not a validated erosion prediction"),
          _ev("docs/evidence/cathode/CATHODE_DOSSIER.md", "cathode evidence; air-fed cathode operation unresolved; no life test of the demonstrated air-fed plasma cathodes"),
          EV_HGS,
          _ev("CLAUDE.md", "mechanism-level (probably robust): grids are life-limited by CEX + perveance window; gate 2 = pass")],
         "blocked_by_gate_3", True, ["analysis", "test"],
         "Hall channel erosion needs wall ion flux from an admitted, wall_life_trustworthy Hall map (none exist). "
         "Demonstrating life needs a wear test; no test data are in the repository.",
         _hg(["G4_firing_life", "P2_cathode"], ["G4.firing_life", "P2.cathode_life"],
             "G4 binding; P2 PROPOSED (non-binding)", ["OD9", "OD10", "OD13"]),
         ["R1", "R2", "R3", "R5"]),
    _req("RFP-HALL", "rfp_envelope", "Hall thruster preferred",
         "Hall-effect thruster preferred as the accelerator.",
         None,
         _src(ENV, [CONST + " (hall_preferred)", "docs/HISTORY.md constraint table (chk_hall_preferred)"]),
         [_mq("abep_sim/archengine.py::enumerate_architectures", "architecture families incl. Hall"),
          _mq("abep_sim/hall_ensemble.py::require_admitted", "blocks non-admitted closures"),
          _mq("abep_sim/hall_map.py::HallMap", "Hall maps (admitted members only)")],
         [_ev("hallthruster_bridge/PINNED.toml", "HallThruster.jl pin (rule 7)"),
          _ev("hallthruster_bridge/identification/p5_xe_identification_sgb_v1_summary.json", "P5-Xe identification closed: transport not uniquely identifiable"),
          _ev(HG_MATRIX, "not_gates: 'Hall preferred' is a preference, not a pass/fail limit; all three architectures share the downstream Hall accelerator"),
          EV_B1],
         "partial", True, ["inspection", "analysis"],
         "Choosing a Hall accelerator is a design decision (inspection). All three candidates (hall_only, rf_hall, "
         "ecr_hall) use the same downstream Hall accelerator, so this preference does not discriminate between them. "
         "No architecture winner is claimed.",
         _hg([], [], "not a gate (hard_gate_matrix not_gates)"),
         ["R1", "R2", "R3"]),
    _req("RFP-PROP", "rfp_envelope", "Propellants: air and xenon (gas path)",
         "Atmospheric air (intake-collected) and xenon as propellants, via the RFP architecture recorded in the repository "
         "(atmospheric path intake -> filter -> compressor -> atmospheric gas chamber -> valve; Xe path Xe chamber -> valve; "
         "both feed ionization/discharge -> acceleration/thrust).",
         None,
         _src(ENV, ["docs/HISTORY.md constraint table (N2 + nascent O; Xe as propellant)",
                    "CLAUDE.md next-work item 1 'Scope' (RFP architecture)"]),
         [_mq("abep_sim/intake_tpmc.py::IntakeSurface", "frozen TPMC intake response surface"),
          _mq("abep_sim/compressor.py::DragCompressor", "compression of collected air"),
          _mq("abep_sim/reservoir.py::Reservoir", "atmospheric gas chamber"),
          _mq("abep_sim/aochem.py::inlet_composition", "wall O recombination -> thruster inlet composition"),
          _mq("abep_sim/mass_bom.py::xe_tank", "Xe storage")],
         [_ev("abep_sim/data/intake_surface_v1.json", "frozen intake surface provenance"),
          _ev("hallthruster_bridge/audit/n2_closure_verdicts_v1.json", "N2/N reaction set abep-n2n-0.11, COMPLETE_FOR_P5_N2_VALIDATION (domain-limited, not a general completeness claim)"),
          _ev("CLAUDE.md", "O2/O chemistry and intake-delivered mixtures only after next-work items 1-3 succeed"),
          EV_HGS],
         "partial", True, ["analysis", "test"],
         "Gas path is modeled. Hall-discharge chemistry exists only for N2/N (validation domain T_e 2-30 eV); O/O2 is not "
         "started; discharge operation on the delivered atmospheric composition is lane 24 G6 (RFP-IGN-SUST) and on xenon "
         "G7 (RFP-XE-OP), both gate-3 blocked for model evidence.",
         _hg(["G6_ignition_sustainment", "G7_air_xenon"], [],
             "the gas path defines the 'atmospheric' and 'xenon' propellants these gates are evaluated on", ["OD6"]),
         ["R1", "R3", "R4"]),
    _req("RFP-XE-OP", "rfp_envelope", "Operation on xenon (air + Xe)",
         "Steady operation on the Xe feed within the power limit; whether 'air + Xe' also means feed switching without "
         "extinction or simultaneous mixed feed is open (lane 24 OD6). Verify against the RFP wording.",
         None,
         _src(ENV, ["docs/HISTORY.md constraint table (Xe as propellant; 25 mN peak with Xe topping)",
                    "CLAUDE.md next-work item 1 'Scope' (Xe path Xe chamber -> valve)"]),
         [_mq("abep_sim/mass_bom.py::xe_tank", "Xe storage"),
          _mq("abep_sim/ppu.py::load_modes", "peak mode (Xe augmentation) electrical loads"),
          _mq("abep_sim/hall_map.py::HallMap", "intended Hall performance source on Xe (no admitted members)")],
         [_ev("docs/controls/DUAL_FEED_STATES.md", "dual-feed state machine v1 DRAFT: conceptual, every parameter TBD; asserts nothing about discharge physics"),
          _ev("schemas/controls/dual_feed_state_machine_v1.json", "machine-readable state machine"),
          _ev("hallthruster_bridge/identification/p5_xe_identification_sgb_v1_summary.json", "P5-Xe: transport not uniquely identifiable; screening candidates are never performance sources"),
          EV_ENS, EV_HGS],
         "blocked_by_gate_3", True, ["analysis", "test", "demonstration"],
         H3 + " Feed switching and mixed-feed operation need a demonstration; no Vyovrinda hardware data exist.",
         _hg(["G7_air_xenon"], ["G7.xenon_operation", "G7.feed_switching", "G7.mixed_feed"],
             "xenon_operation counts for PASS and FAIL; feed_switching and mixed_feed PASS only (OD6)", ["OD1", "OD6"]),
         ["R1", "R3", "R4"]),
    _req("RFP-IGN-SUST", "rfp_inferred_from_repo_text", "Ignition and sustainment on atmospheric propellant",
         "A discharge is sustained on the delivered atmospheric composition, and ignites from the off state. No ignition "
         "or restart clause is recorded in the repository: lane 24 carries G6 with status RFP but records the EXISTENCE "
         "of G6.ignition as INFERRED (from 'air + Xe' and the RFP architecture), owner decision OD14. Also the mandatory "
         "comparison field 'startup' (CLAUDE.md admissibility rule). Verify against the RFP document.",
         None,
         _src("docs/architecture_comparison/hard_gates/hard_gate_matrix_v1.json, gate G6_ignition_sustainment "
              "(rfp_source: inferred from R1 'air + Xe', R3/R6 'N2 + nascent O', R4 RFP architecture)",
              [ENV, "CLAUDE.md admissibility rule (mandatory field 'startup')"]),
         [_mq("abep_sim/reservoir.py::startup_transient", "gas-chamber fill to ignition pressure"),
          _mq("abep_sim/cathode_integration.py::startup_transient", "cathode start-up phases (explicit inputs, no Hall prediction)"),
          _mq("abep_sim/ppu.py::load_modes", "startup electrical mode")],
         [_ev("docs/evidence/hall_sustainment/HALL_SUSTAINMENT_EVIDENCE.md", "Hall sustainment evidence matrix (published data; not Vyovrinda hardware)"),
          _ev("docs/architecture_comparison/cathode_integration/CATHODE_INTEGRATION.md", "DRAFT: IF-THEN cathode consequences; no I_d available (gate 3)"),
          _ev("docs/evidence/cathode/CATHODE_DOSSIER.md", "Xe-fed hollow cathode baseline; atmospheric-gas-fed cathode operation unresolved"),
          _ev("docs/controls/DUAL_FEED_STATES.md", "start / transfer sequence proposal; guards gated, all parameters TBD"),
          _ev("hallthruster_bridge/identification/echt_n2/STATUS.json", "ECHT-N2 HISTORICAL_UNSUPPORTED: not score-bearing sustainment evidence"),
          EV_HGS],
         "blocked_by_gate_3", True, ["analysis", "demonstration"],
         "Gas-path fill and cathode start-up relations are modeled; Hall ignition and sustainment on the delivered air "
         "composition are not established (gate 3; no O/O2 chemistry; pure N2 never covers 'atmospheric' per lane 24). "
         "Restart count threshold is TBD (G6.restart_count). Whether ignition is an RFP requirement is OD14; air-only vs "
         "xenon-assisted start is OD5.",
         _hg(["G6_ignition_sustainment"], ["G6.sustainment", "G6.ignition", "G6.restart_count"],
             "G6 status RFP; G6.ignition existence inferred; restart_count TBD, does not count", ["OD5", "OD14"]),
         ["R1", "R3", "R4", "R6"]),
    _req("RFP-NASCENT-O", "rfp_inferred_from_repo_text", "Ionise nascent O",
         "The ABEP ionises nascent (atomic) O from the collected atmosphere (docs/HISTORY.md: 'RFP: \"ionise nascent O\"'; "
         "constraint table 'N2 + nascent O'). No threshold is recorded.",
         None,
         _src("docs/HISTORY.md, v0.2 additions, heterogeneous wall recombination bullet ('RFP: \"ionise nascent O\"')",
              ["docs/HISTORY.md constraint table ('N2 + nascent O')"]),
         [_mq("abep_sim/aochem.py::recombination_fraction", "wall recombination (gamma): how much atomic O reaches the thruster"),
          _mq("abep_sim/aochem.py::inlet_composition", "thruster inlet composition (N2 / O2 / O)")],
         [_ev(HG_MATRIX, "rfp_requirements_recorded_not_gated: carried through the definition of 'atmospheric propellant' in G1 and G6; whether it needs its own gate is OD12"),
          _ev("CLAUDE.md", "next-work item 4: O2/O chemistry only after items 1-3 succeed (not started)")],
         "open", True, ["analysis", "test"],
         "Wall recombination (how much O arrives) is modeled with literature-class priors; O/O2 Hall-discharge chemistry "
         "does not exist in the validated chain, so ionisation of O is not modeled. Clause and meaning must be checked "
         "against the RFP.",
         _hg([], [], "recorded, not gated (rfp_requirements_recorded_not_gated); enters G1/G6 via the 'atmospheric' propellant definition",
             ["OD12"]),
         ["R3", "R6"]),
    _req("RFP-IC", "rfp_inferred_from_repo_text", "Indigenous content (IC)",
         "Total IC >= 75 %; subsystem IC thruster >= 80 %, intake >= 80 %, compressor >= 60 %, PSE >= 70 % (as encoded in "
         "code; reading 'IC' as indigenous content follows docs/HISTORY.md).",
         _val("indigenous content (mass-weighted)",
              "total >= 0.75; thruster >= 0.80; intake >= 0.80; compressor >= 0.60; pse >= 0.70", "fraction", CONST),
         _src(CONST, ["docs/HISTORY.md constraint table (chk_ic_total, chk_ic_thruster)", "abep_sim/explorer.py header text ('IC >= 75 %')"]),
         [_mq("abep_sim/system.py::evaluate", "mass-weighted ic_total / ic_thruster checks (legacy closure)"),
          _mq("abep_sim/constants.py::RFPConstraints", "ic_total_min, ic_subsystem_min")],
         [_ev("docs/HISTORY.md", "component IC values are priors (e.g. the microwave-source IC prior); a supply-chain finding, not physics"),
          _ev(HG_MATRIX, "rfp_requirements_recorded_not_gated (programmatic; OD12)")],
         "partial", False, ["inspection"],
         "Not in the CLAUDE.md envelope summary; the clause, exact definition and subsystem thresholds must be checked "
         "against the RFP. Component IC values are assumed priors; needs a supplier-backed BoM.",
         _hg([], [], "recorded, not gated (rfp_requirements_recorded_not_gated)", ["OD12"]),
         ["R2", "R3"]),
    _req("RFP-REDUND", "rfp_inferred_from_repo_text", "Electronics redundancy",
         "No single-point failure in electronics (as stated in a code docstring).",
         None,
         _src("abep_sim/ppu.py module docstring ('Redundancy per RFP: no single-point failure in electronics')",
              ["docs/HISTORY.md ('cold-redundant converters (RFP redundancy)')"]),
         [_mq("abep_sim/ppu.py::default_ppu", "cold-redundant converters (mass doubled)"),
          _mq("abep_sim/life.py::reliability", "series reliability and SPF list")],
         [_ev(HG_MATRIX, "rfp_requirements_recorded_not_gated: mass and power consequences carried by G2/G3 (redundant units in the ledgers); OD12"),
          _ev("docs/architecture_comparison/failure_tree/failure_trees_v1.json", "architecture failure trees (DRAFT): contain no electronics-redundancy / single-point-failure node; not an FMEA")],
         "partial", False, ["analysis", "inspection"],
         "Redundancy is represented only as mass/reliability bookkeeping; there is no FMEA. The clause must be located in the RFP.",
         _hg([], [], "recorded, not gated; consequences via G2/G3", ["OD12"]),
         ["R7"]),
    _req("RFP-AO-TEST", "rfp_inferred_from_repo_text", "Atomic-oxygen beam testing",
         "AO-beam tests of materials (docs/HISTORY.md cites 'RFP 4.1a'; abep_sim/aochem.py calls them 'RFP-mandated').",
         None,
         _src("docs/HISTORY.md AO chemistry section ('AO-beam test (RFP 4.1a)'); abep_sim/aochem.py module docstring"),
         [_mq("abep_sim/aochem.py::erosion_depth_um", "AO erosion depth per material"),
          _mq("abep_sim/aochem.py::recombination_fraction", "wall recombination (gamma)"),
          _mq("abep_sim/aochem.py::fluence", "mission AO fluence")],
         [_ev("docs/HISTORY.md", "erosion yields and gammas are literature-class priors, to be replaced by coupon data"),
          _ev(HG_MATRIX, "rfp_requirements_recorded_not_gated: a test requirement; supplies G5 evidence for AO-exposed surfaces")],
         "open", False, ["test"],
         "No AO-beam coupon data. The '4.1a' clause number is in-repo text only; verify.",
         _hg([], [], "recorded, not gated; supplies G5 evidence"), ["R6"]),
    _req("PRG-BID", "programmatic", "Bid close date",
         "Bid closes 05 Oct 2026.",
         {"quantity": "bid close date", "limit": "2026-10-05", "unit": "date", "value_source": ENV,
          "evidence_class": "assumed", "evidence_note": "transcribed from an in-repo summary; verify"},
         _src(ENV), [], [],
         "open", False, ["inspection"],
         "Programmatic item with no simulator quantity; listed so the submission date is traced.",
         _hg([], [], "not a technical gate"), ["R1"]),
    _req("DER-NETDRAG", "derived_project", "Net drag compensation on air",
         "Thrust exceeds spacecraft drag on air alone. This is the physical purpose of ABEP; docs/HISTORY.md says the RFP does not state it.",
         None,
         {"where": "docs/HISTORY.md ('abep_closed' definition: the RFP does not state it)", "page_ref": NOT_RFP},
         [_mq("abep_sim/mission_env.py::spacecraft_drag", "drag"),
          _mq("abep_sim/archengine.py::close_architecture", "T/D")],
         [_ev("CLAUDE.md", "gate 3 FAIL"),
          _ev(HG_MATRIX, "not_gates: not an RFP requirement as recorded; can enter only as an owner-PROPOSED gate")],
         "blocked_by_gate_3", True, ["analysis"],
         H3 + " Spacecraft ram area is a DRDO input not in the repository.",
         _hg([], [], "not a gate (hard_gate_matrix not_gates)"), ["R3"]),
    _req("DER-HALL-CLOSURE", "derived_project", "Admitted Hall transport closure",
         "Absolute Hall performance may be used only from admitted ensemble members (promotion rule; O4 dispositions).",
         None,
         {"where": "CLAUDE.md next-work item 1 (promotion rule) and item 3 (O4 gating)", "page_ref": NOT_RFP},
         [_mq("abep_sim/hall_ensemble.py::require_admitted", "rejects non-members"),
          _mq("abep_sim/hall_ensemble.py::_check_o4", "admission needs O4 dispositions"),
          _mq("abep_sim/hall_map.py::HallMap", "loads admitted members only")],
         [_ev("hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json", "v1 vacuum release manifest"),
          EV_V1,
          _ev("hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json", "pre-registered criteria"),
          _ev("hallthruster_bridge/validation/p5_n2_campaign_v1_staged_n2_n_exc_johnsonlow_scores.json", "O4 first stage (Johnson-low) scored; its trigger fired"),
          _ev("docs/o4/johnsonlow_assessment/JOHNSONLOW_ASSESSMENT.md", "Johnson-low escalation assessment: evidence summary only; changes no P5-N2 v1 result; Johnson-low stays a sensitivity"),
          _ev("hallthruster_bridge/identification/echt_n2/STATUS.json", "ECHT-N2 HISTORICAL_UNSUPPORTED: not a transport discriminator, not score-bearing"),
          _ev("docs/v2/question_a/QUESTION_A_DISPOSITION.json", "owner disposition A-NO: active N2 domain stays at 45 eV; no P5-N2 v2 now"),
          EV_ENS, EV_B1],
         "blocked_by_gate_3", True, ["analysis", "test"],
         "Credible set is empty. O4 staged and escalation score files are committed, but no O4 disposition file and no "
         "facility score file is present at the base commit; v2 Question A was answered A-NO (no v2 now). Admission needs "
         "genuinely new predictive evidence not used in selection.",
         _hg([], [], "evidence-policy basis model_admitted_closure (lane 24): verdict-bearing only from admitted members; "
             "screening candidates never are. Enters G1, G2, G4, G5, G6, G7 as the Milestone-B model route", ["OD11"]),
         []),
    _req("DER-THERMAL", "derived_project", "Heat rejection (Q_reject)",
         "Waste heat is rejected within the thermal design (mandatory comparison field Q_reject in CLAUDE.md).",
         None,
         {"where": "CLAUDE.md admissibility rule (mandatory fields)", "page_ref": NOT_RFP + "; check the RFP for thermal requirements"},
         [_mq("abep_sim/thermal.py::solve_network", "node temperatures"),
          _mq("abep_sim/thermal.py::size_radiator", "radiator sizing"),
          _mq("abep_sim/thermal_life.py::solve_node_temperature", "lumped steady-state node temperature (framework; not wired)")],
         [_ev("docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md", "framework only; every design input TBD; no admitted HallMap supplies wall heat"),
          _ev(HG_MATRIX, "P1_thermal is a PROPOSED (non-binding) gate; allowables TBD (OD9)")],
         "partial", True, ["analysis", "test"],
         "Thermal network and framework exist; Hall discharge heat loads need gate 3; allowables and margins TBD.",
         _hg(["P1_thermal"], ["P1.thermal_margin"], "PROPOSED gate: reported, never eliminates", ["OD9", "OD10"]),
         []),
    _req("DER-MODEL-INTEGRITY", "derived_project", "Simulator integrity gates",
         "Frozen data reproduce, golden benchmarks pass, source balances close, energy-ledger residual < 2 %, numerical "
         "convergence (CLAUDE.md rules 1-5).",
         {"quantity": "energy-ledger residual", "limit": "< 2", "unit": "%", "value_source": "CLAUDE.md rule 4",
          "evidence_class": "assumed", "evidence_note": "project rule, not an RFP clause"},
         {"where": "CLAUDE.md rules 1-5 and gate table", "page_ref": NOT_RFP},
         [_mq("abep_sim/golden.py::check", "golden reproduction"),
          _mq("abep_sim/convergence.py::run_all", "convergence checks")],
         [_ev("abep_sim/data/golden_v1.json", "golden reference"),
          _ev("CLAUDE.md", "gates 1, 2, 5, 6 = pass (not re-run in this lane)")],
         "modeled", False, ["test"],
         "None for integrity itself; integrity does not imply Hall validity.",
         _hg([], [], "not a hard gate"), [],
         verification_status="reported_pass_in_CLAUDE.md_gate_table_not_rerun_here"),
]

# requirement, design feature, verification, evidence (hard-gate link is taken from the row)
CHAINS = [
    ("RFP-ALT", "Intake + compressor sized over the 180-230 km density range",
     "Analysis over the frozen NRLMSIS dataset", "Frozen atmosphere + golden; altitude hold gated by thrust (gate 3)"),
    ("RFP-THR-MIN", "Hall accelerator with Vyovrinda-specific geometry and B(z) (TBD - requires a design definition)",
     "Analysis with admitted-member Hall maps, or a Milestone-A hard bound / hardware measurement; then thruster test",
     "None admissible: credible set empty; gate 3 FAIL; G1 UNDETERMINED"),
    ("RFP-THR-MAX", "Xe path (Xe chamber -> valve) into the same discharge; thrust cap or peak-capability sizing per OD1",
     "Analysis (mission ROM) + thruster test", "None admissible (gate 3); OD1 reading open"),
    ("RFP-PWR", "PPU converter set with cold redundancy; compressor motor drive; common bus_power_boundary_v1 ledger",
     "Analysis on the common bus-power boundary + electrical test",
     "Boundary defined; all loads/efficiencies TBD; Hall discharge power unavailable (gate 3); RFP boundary scope TBD"),
    ("RFP-MASS", "Mass BoM: Xe tank, Hall magnetic circuit, radiator, structure, PPU, pre-ionizer hardware",
     "Analysis (CBE/MGA/MEV), then inspection (weighing)", "BOM skeleton; no sourced CBE; roll-up refused"),
    ("RFP-MISSION", "Mission controller (altitude hold, Xe topping)", "Analysis (propagator + UQ)",
     "Convergence pass; mission UQ conditional on gate 3; G5 UNDETERMINED"),
    ("RFP-FIRING", "Channel wall material and magnetic topology; cathode; compressor bearings",
     "Analysis (erosion from wall_life_trustworthy maps) + wear test",
     "No trustworthy wall-flux map; wall-life evidence and thermal/life framework only; no test data"),
    ("RFP-HALL", "Hall accelerator common to hall_only, rf_hall and ecr_hall", "Inspection of design",
     "Preference, not a gate; Bundle 1 v3 NO_BASELINE_YET; no winner claimed"),
    ("RFP-PROP", "Intake -> filter -> compressor -> atmospheric gas chamber -> valve; Xe chamber -> valve",
     "Analysis (TPMC ROM, compressor, reservoir, AO chemistry) + tests",
     "Frozen intake surface; N2/N chemistry abep-n2n-0.11 domain-limited; O/O2 not started"),
    ("RFP-XE-OP", "Xe feed valves and dual-feed controller (state machine v1 DRAFT)",
     "Analysis with admitted Hall maps + demonstration of switching / mixed feed",
     "State machine conceptual; no admitted closure; G7 UNDETERMINED"),
    ("RFP-IGN-SUST", "Reservoir fill, cathode heater/keeper, ignition sequence (air-only or Xe-assisted, OD5)",
     "Analysis + demonstration", "Gas-path and cathode start-up relations only; G6 UNDETERMINED; OD14 open"),
    ("RFP-NASCENT-O", "Wall / coating material of intake-compressor path (recombination gamma); discharge chemistry",
     "Test (AO-beam gamma) + analysis once O/O2 chemistry exists", "Priors only; O/O2 chemistry not started"),
    ("RFP-IC", "Supplier selection per subsystem", "Inspection of BoM", "Priors only"),
    ("RFP-REDUND", "Cold-redundant PPU converters", "Analysis (FMEA) + inspection",
     "Mass/reliability bookkeeping only; no FMEA"),
    ("RFP-AO-TEST", "Wall / coating material selection", "Test (AO beam: erosion yield and recombination gamma)",
     "Literature priors only"),
    ("PRG-BID", "Bid package", "Inspection (submission record)", "None yet"),
    ("DER-NETDRAG", "Whole ABEP system", "Analysis (T/D over the mission)", "Gated by gate 3 and DRDO spacecraft data"),
    ("DER-HALL-CLOSURE", "Transport closure selection (never a Vyovrinda design variable)",
     "Pre-registered blind prediction of new evidence",
     "v1 vacuum INCONCLUSIVE (permanent); O4 dispositions and facility scores not in the repository"),
    ("DER-THERMAL", "Radiator and conductive straps", "Analysis + thermal-vacuum test",
     "Network model and framework only; P1 PROPOSED"),
    ("DER-MODEL-INTEGRITY", "Frozen datasets, golden benchmarks, convergence checks", "Test (golden check, pytest)",
     "Gates 1, 2, 5, 6 pass per CLAUDE.md"),
]

STATUS_VOCAB = {
    "modeled": "a model exists and its integrity checks are reported passing; says nothing about hardware compliance",
    "partial": "some of the needed quantities are modeled; others are missing or gated",
    "open": "no model or evidence yet",
    "blocked_by_gate_3": "compliance depends on absolute Hall performance, withdrawn until an admitted closure exists",
}

MILESTONES = {
    "supports": ["A"],
    "A": ("Supports conditional selection as a traceability input: it lists, per RFP requirement as recorded in the "
          "repository, the model quantity, current evidence, open gap and the lane-24 gate that decides it. It adds no "
          "evidence and no verdict of its own."),
    "to_reach_B": ("Every blocked_by_gate_3 row needs an admitted Hall transport closure and Vyovrinda design Hall maps "
                   "per member; the RFP document must be obtained so every 'verify against RFP document' and the open "
                   "readings (OD1, OD4, OD6, OD8, OD13, OD14; BUS_POWER_BOUNDARY.md rule 6) can be settled; the second "
                   "verification lens of this lane must pass (single-lens-v1 lanes are not decisive for B or C before it)."),
    "to_reach_C": ("Hardware evidence for each verification method (thruster, wear, electrical, thermal-vacuum tests; "
                   "weighed BoM; AO-beam coupons), an FMEA for the redundancy row, and the integrated mass, power, "
                   "thermal, life, startup, cathode and mission closure."),
    "verification_protocol": ("lane_36_traceability is registered single-lens-v1 (docs/orchestration/lane_registry_v1.json); "
                              "until its second lens passes it is not decisive evidence for Milestone B or C."),
}

THREE_QUESTIONS = {
    "i_conditional_selection_now": (
        "This matrix selects nothing. Per the lane-24 hard-gate status every gate is UNDETERMINED for hall_only, rf_hall "
        "and ecr_hall and nothing is eliminated; Bundle 1 v3 (DRAFT_FOR_OWNER_REVIEW) proposes NO_BASELINE_YET."),
    "ii_what_blocks_physics_backed_selection": [
        "no admitted Hall transport closure (gate 3 FAIL; credible set empty): every blocked_by_gate_3 row",
        "RFP document not in the repository: every source is a secondary transcription ('verify against RFP document')",
        "open owner readings of recorded requirements: OD1 (25 mN), OD4, OD6, OD8, OD13, OD14 and the bus-power boundary scope",
        "no O/O2 discharge chemistry (RFP-NASCENT-O, RFP-IGN-SUST)",
    ],
    "iii_what_could_overturn": [
        "the RFP text itself: a clause, threshold or scope that differs from the in-repo transcriptions would change rows here and gates in lane 24",
        "an owner decision on OD1-OD14 that changes which criterion binds",
        "a committed hard-bound script or Vyovrinda hardware measurement registered in the lane-24 evidence register",
    ],
}


def _sha256(rel: str) -> str:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        raise FileNotFoundError(f"cross-referenced file missing: {rel} (this RTM version is built against {BASE_COMMIT})")
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def build() -> dict:
    return {
        "schema": "abep-rtm-v1",
        "title": "Requirement traceability matrix - DRDO TDF ABEP-VLEO",
        "status": "DRAFT_PENDING_OWNER",
        "status_note": ("Requirement categorisation (which rows count as RFP rows, which are inferred from repository text "
                        "or project-derived), the reading of each statement and the hard-gate mapping are PROPOSED for "
                        "owner review. No threshold here is new: every limit is transcribed from in-repo text."),
        "rfp_id": "DTDF/06/13516/DSP/ABEP/X/L/M/01",
        "rfp_id_source": "CLAUDE.md 'What this is'",
        "matrix_date": "2026-09-27",
        "base_commit": BASE_COMMIT,
        "architectures": ["hall_only", "rf_hall", "ecr_hall"],
        "architecture_note": ("The RF and ECR arms change only the pre-ionization method; the downstream Hall accelerator, "
                              "feed state, cathode and bus boundary are common. No architecture winner is claimed."),
        "milestones": MILESTONES,
        "three_questions": THREE_QUESTIONS,
        "rfp_document_in_repository": False,
        "source_policy": (
            "The RFP document is not in the repository. Every requirement cites the in-repo text it was taken from and "
            "carries page_ref 'verify against RFP document' (or states it is project-derived). No RFP clauses, page numbers "
            "or values were invented. Rows marked rfp_inferred_from_repo_text come from code docstrings, docs/HISTORY.md "
            "text or the lane-24 hard-gate matrix that claim or infer an RFP origin; that origin is unverified. "
            "rfp_record_refs use the lane-24 record ids R1-R7 (hard_gate_matrix_v1.json rfp.recorded_in)."),
        "searched": ("grep -ri 'rfp|drdo' over CLAUDE.md, README.md, docs/, abep_sim/, pyproject.toml, tests/; the lane-24 "
                     "hard-gate matrix record list R1-R7 was used as a cross-check (at the base commit)"),
        "status_vocabulary": STATUS_VOCAB,
        "verification_methods": ["analysis", "test", "demonstration", "inspection"],
        "hall_status": H3 + (
            " The P5-N2 v1 vacuum outcome is INCONCLUSIVE / NOT ELIGIBLE for all nine screening candidates (permanent for "
            "v1). O4 first-stage and escalation score files are committed (Johnson-low trigger fired); no O4 disposition "
            "file and no facility score file is present at the base commit (a facility attempt is recorded under "
            "hallthruster_bridge/validation/interrupted/), so no admission is possible."),
        "gate_status_snapshot": {"source": "CLAUDE.md gate table (as of the base commit)",
                                 "1": "pass", "2": "pass", "3": "FAIL", "4": "done, conditional on gate 3",
                                 "5": "pass", "6": "pass"},
        "hard_gate_link": {
            "matrix": HG_MATRIX,
            "status": HG_STATUS,
            "evidence_register": HG_REGISTER,
            "matrix_status": "DRAFT_PENDING_OWNER",
            "current": HGS,
            "note": ("Lane 24 is the pass/fail criterion for the RFP requirements; this RTM is the traceability view. Each "
                     "row's hard_gate_xref names the gate and criterion ids and the open owner decisions (OD*). Where the "
                     "two differ, the difference is stated in the row (e.g. RFP-THR-MAX OD1, RFP-IGN-SUST OD14)."),
        },
        "bundle1_link": {"file": BUNDLE1, "status": "DRAFT_FOR_OWNER_REVIEW", "outcome": "NO_BASELINE_YET"},
        "pinned_cross_references_sha256": {rel: _sha256(rel) for rel in PINNED_XREFS},
        "compliance_claim": ("none - this matrix claims no RFP compliance, no demonstrated ABEP closure, no architecture "
                             "winner and no transport admission"),
        "requirements": REQUIREMENTS,
        "chains": [dict(requirement_id=a, design_feature=b, verification=c, evidence=d,
                        hard_gate=_chain_gate(a)) for a, b, c, d in CHAINS],
    }


def _chain_gate(rid: str) -> str:
    r = next(x for x in REQUIREMENTS if x["id"] == rid)
    x = r["hard_gate_xref"]
    ids = x["criteria"] or x["gates"]
    return (", ".join(ids) + " (UNDETERMINED)") if ids else x["note"]


def _cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_md(doc: dict) -> str:
    m = doc["milestones"]
    q = doc["three_questions"]
    L = [f"# {doc['title']}", "",
         f"**Status: {doc['status']}.** {doc['status_note']}", "",
         f"RFP {doc['rfp_id']} (id from {doc['rfp_id_source']}). Matrix date {doc['matrix_date']}, base commit "
         f"`{doc['base_commit']}`. Generated from `docs/traceability/build_rtm.py`; machine-readable copy `rtm_v1.json`. "
         "Do not edit this file by hand.", "",
         "## Read this first", "",
         f"- **Source policy.** {doc['source_policy']}",
         f"- **Hall status.** {doc['hall_status']}",
         f"- **Architectures.** `{'`, `'.join(doc['architectures'])}`. {doc['architecture_note']}",
         f"- **Hard gates (lane 24).** {doc['hard_gate_link']['note']} Current: {doc['hard_gate_link']['current']} "
         f"(`{doc['hard_gate_link']['status']}`).",
         f"- **Bundle 1.** `{doc['bundle1_link']['file']}` ({doc['bundle1_link']['status']}): outcome "
         f"`{doc['bundle1_link']['outcome']}`.",
         f"- **Compliance claim:** {doc['compliance_claim']}.",
         "- Gate status (" + doc["gate_status_snapshot"]["source"] + "): "
         + ", ".join(f"{k} {v}" for k, v in doc["gate_status_snapshot"].items() if k != "source") + ".",
         "", "## Milestones", "",
         f"- **Supports:** {', '.join(m['supports'])}. {m['A']}",
         f"- **To reach B:** {m['to_reach_B']}",
         f"- **To reach C:** {m['to_reach_C']}",
         f"- **Verification protocol:** {m['verification_protocol']}",
         "", "## The three questions", "",
         f"- **(i) Conditional selection now:** {q['i_conditional_selection_now']}",
         "- **(ii) What blocks physics-backed selection:** " + "; ".join(q["ii_what_blocks_physics_backed_selection"]) + ".",
         "- **(iii) What could overturn it:** " + "; ".join(q["iii_what_could_overturn"]) + ".",
         "", "## Status vocabulary", ""]
    for k, v in doc["status_vocabulary"].items():
        L.append(f"- `{k}`: {v}")
    L += ["", "## Matrix", "",
          "| id | requirement | limit | source (page ref) | status | gate-3 dependent | hard gate (lane 24) | verification | open gap |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in doc["requirements"]:
        v = r["value"]
        lim = f"{v['limit']} {v['unit']} ({v['evidence_class']})" if v else "-"
        x = r["hard_gate_xref"]
        hg = ", ".join(x["criteria"] or x["gates"]) or "-"
        if x["open_owner_decisions"]:
            hg += " [" + ", ".join(x["open_owner_decisions"]) + "]"
        L.append("| " + " | ".join(_cell(y) for y in [
            r["id"], f"{r['title']}: {r['statement']}", lim,
            f"{r['source']['where']} ({r['source']['page_ref']})", r["status"],
            "yes" if r["gate3_dependent"] else "no", hg, ", ".join(r["verification_method"]), r["open_gap"]]) + " |")
    L += ["", "## Requirement -> model quantity -> current evidence", ""]
    for r in doc["requirements"]:
        L.append(f"### {r['id']} - {r['title']}")
        L.append("")
        L.append(f"Status `{r['status']}`; verification status `{r['verification_status']}`. RFP records: "
                 f"{', '.join(r['rfp_record_refs']) or 'none (not an RFP row)'}.")
        L.append("")
        x = r["hard_gate_xref"]
        L.append(f"Hard gate (lane 24): gates {', '.join(x['gates']) or '-'}; criteria {', '.join(x['criteria']) or '-'}; "
                 f"open owner decisions {', '.join(x['open_owner_decisions']) or '-'}. {x['note']}.")
        L.append("")
        if r["model_quantities"]:
            L.append("Model quantities:")
            for mq in r["model_quantities"]:
                L.append(f"- `{mq['ref']}`: {mq['role']}")
        else:
            L.append("Model quantities: none (not a simulator quantity).")
        L.append("")
        if r["current_evidence"]:
            L.append("Current evidence:")
            for e in r["current_evidence"]:
                L.append(f"- `{e['ref']}`: {e['note']}")
        else:
            L.append("Current evidence: none in the repository.")
        L.append("")
    L += ["## Requirement -> design feature -> verification -> evidence", "",
          "| requirement | design feature | hard gate (lane 24) | verification | evidence |", "|---|---|---|---|---|"]
    for c in doc["chains"]:
        L.append("| " + " | ".join(_cell(c[k]) for k in
                                    ("requirement_id", "design_feature", "hard_gate", "verification", "evidence")) + " |")
    L += ["", "## Pinned cross-references", "",
          "`--check` reports STALE when any of these files changes; re-read this matrix against it then.", ""]
    for k, v in doc["pinned_cross_references_sha256"].items():
        L.append(f"- `{k}`: `{v}`")
    L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    doc = build()
    js = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    md = render_md(doc)
    if "--check" in argv:
        ok = all(os.path.exists(p) and open(p, encoding="utf-8").read() == s for p, s in ((JSON_PATH, js), (MD_PATH, md)))
        print("OK" if ok else "STALE")
        return 0 if ok else 1
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        f.write(js)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {JSON_PATH} and {MD_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

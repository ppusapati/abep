"""Build the DRDO TDF ABEP requirement traceability matrix (rtm_v1.json + RTM.md).

Single source of truth for the RTM. Run from the repository root:
    python docs/traceability/build_rtm.py          # (re)write both files
    python docs/traceability/build_rtm.py --check  # exit 1 if the committed files are stale

Evidence discipline (CLAUDE.md rules 6 and 10, docs/EVIDENCE.md): the RFP document is NOT in the repository. Every
requirement cites the in-repo text it came from and carries page_ref "verify against RFP document" (or says it is
project-derived). No clause numbers, page numbers or values are invented here. This matrix claims no compliance.
"""
from __future__ import annotations
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(HERE, "rtm_v1.json")
MD_PATH = os.path.join(HERE, "RTM.md")

PAGE = "verify against RFP document"
ENV = ("CLAUDE.md, 'What this is' section: RFP envelope summary (secondary in-repo transcription; "
       "the RFP document is not in the repository)")
CONST = ("abep_sim/constants.py, class RFPConstraints (docstring says 'Hard limits from Part III Para 2 of the RFP'; "
         "that clause reference is itself unverified in-repo text)")
H3 = ("All absolute Hall results from the superseded 0-D closure (v1.2-v1.6) are withdrawn (CLAUDE.md 'Superseded / "
      "withdrawn'); gate 3 (multi-point Hall validation) is FAIL and the credible transport set is empty, so no Hall "
      "performance number may be used as evidence of compliance.")
NOT_RFP = "not an RFP clause (project-derived)"


def _src(where: str, extra: list[str] | None = None) -> dict:
    d = {"where": where, "page_ref": PAGE}
    if extra:
        d["corroborating_in_repo"] = extra
    return d


def _val(q: str, lim: str, unit: str, where: str) -> dict:
    return {"quantity": q, "limit": lim, "unit": unit, "value_source": where, "evidence_class": "assumed",
            "evidence_note": "requirement limit transcribed from an in-repo summary, not read from the RFP document; verify"}


def _req(id, category, title, statement, value, source, model_quantities, current_evidence, status, gate3_dependent,
         verification_method, open_gap, verification_status="not_verified"):
    return dict(id=id, category=category, title=title, statement=statement, value=value, source=source,
                model_quantities=model_quantities, current_evidence=current_evidence, status=status,
                gate3_dependent=gate3_dependent, verification_method=verification_method,
                verification_status=verification_status, open_gap=open_gap)


def _mq(ref, role):
    return {"ref": ref, "role": role}


def _ev(ref, note):
    return {"ref": ref, "note": note}


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
          _ev("abep_sim/data/golden_v1.json", "golden case_atmosphere; gate 6 = pass per CLAUDE.md gate table (not re-run in this lane)")],
         "partial", True, ["analysis"],
         "Environment definition is modeled. Holding an altitude inside the band needs thrust >= drag, which depends on "
         "Hall performance (gate 3). Spacecraft ram area / ballistic coefficient is a DRDO input not in the repository "
         "(docs/HISTORY.md says it must be requested)."),
    _req("RFP-THR-MIN", "rfp_envelope", "Thrust lower bound",
         "Thrust of at least 12 mN. The project reads this as 'sustained on air' (docs/HISTORY.md); verify against the RFP wording.",
         _val("thrust", ">= 12", "mN", ENV),
         _src(ENV, [CONST + " (thrust_min_mN)", "docs/HISTORY.md constraint table (chk_thrust_air_ge_req)"]),
         [_mq("abep_sim/archengine.py::rfp_preset", "T_min_mN constraint"),
          _mq("abep_sim/archengine.py::close_architecture", "constrained closure; its Hall branch still calls the superseded 0-D plasma_devices.hall_run_coupled"),
          _mq("abep_sim/hall_map.py::HallMap", "intended source of Hall thrust (loads admitted ensemble members only; none exist)"),
          _mq("abep_sim/system.py::evaluate", "legacy check 'thrust_air_ge_req' (0-D Hall; results withdrawn)")],
         [_ev("hallthruster_bridge/ensemble/transport_ensemble_v0.json", "members = [] (credible set empty)"),
          _ev("hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_decision.json", "P5-N2 v1 vacuum: all nine screening candidates INCONCLUSIVE / NOT ELIGIBLE; promotable = []"),
          _ev("CLAUDE.md", "gate 3 FAIL; gate 4 conditional on gate 3; absolute Hall numbers withdrawn")],
         "blocked_by_gate_3", True, ["analysis", "test"],
         H3 + " Needs an admitted closure, Vyovrinda-specific Hall maps, then a thruster test."),
    _req("RFP-THR-MAX", "rfp_envelope", "Thrust upper bound",
         "Thrust up to 25 mN. The project reads this as a peak with Xe topping allowed (docs/HISTORY.md); verify against the RFP wording.",
         _val("thrust", "<= 25", "mN", ENV),
         _src(ENV, [CONST + " (thrust_max_mN)", "docs/HISTORY.md constraint table (chk_thrust_peak_25mN)"]),
         [_mq("abep_sim/archengine.py::rfp_preset", "T_max_mN constraint"),
          _mq("abep_sim/mission5.py::run_mission_generic", "thrust cap in the mission ROM"),
          _mq("abep_sim/hall_map.py::HallMap", "intended Hall thrust source (no admitted members)")],
         [_ev("hallthruster_bridge/ensemble/transport_ensemble_v0.json", "members = []"),
          _ev("CLAUDE.md", "gate 3 FAIL")],
         "blocked_by_gate_3", True, ["analysis", "test"], H3),
    _req("RFP-PWR", "rfp_envelope", "Power ceiling",
         "Power below 1.5 kW. Scope (the project reads it as total power incl. PPU, compressor and Xe peak, docs/HISTORY.md; P_bus definition in CLAUDE.md) must be verified against the RFP wording.",
         _val("power", "< 1.5", "kW", ENV),
         _src(ENV, [CONST + " (power_max_W)"]),
         [_mq("abep_sim/archengine.py::DesignConstraints", "P_bus_max_W"),
          _mq("abep_sim/ppu.py::default_ppu", "converter set (anode, magnet, keeper, heater, compressor motor, aux)"),
          _mq("abep_sim/ppu.py::load_modes", "startup / steady / peak electrical loads"),
          _mq("abep_sim/compressor.py::DragCompressor", "compressor shaft power")],
         [_ev("CLAUDE.md", "P_bus definition (all electrical power across the spacecraft-side DC boundary) and the bus_power_boundary_v1 admissibility rule; the boundary file lives under docs/orchestration/, which is not present at this lane's base commit"),
          _ev("abep_sim/data/golden_v1.json", "energy-ledger residual golden (gate 6 pass per CLAUDE.md)")],
         "blocked_by_gate_3", True, ["analysis", "test"],
         "Non-Hall bus terms (PPU losses, compressor, magnets, heater/keeper) are modeled. The dominant Hall discharge "
         "power at the required thrust is not available (gate 3). The common bus-power boundary comparison is not yet populated."),
    _req("RFP-MASS", "rfp_envelope", "Mass ceiling",
         "Mass below 40 kg. Scope (the project reads it as total incl. intake, compressor, PSE, Xe + tank, structure and margin, docs/HISTORY.md) must be verified against the RFP wording.",
         _val("mass", "< 40", "kg", ENV),
         _src(ENV, [CONST + " (mass_max_kg)"]),
         [_mq("abep_sim/mass_bom.py::build_bom", "CBE / MGA / MEV roll-up"),
          _mq("abep_sim/mass_bom.py::xe_tank", "Xe tank sizing"),
          _mq("abep_sim/mass_bom.py::hall_magnetic_circuit", "Hall magnetic-circuit mass from required flux"),
          _mq("abep_sim/thermal.py::size_radiator", "radiator sizing")],
         [_ev("CLAUDE.md", "earlier absolute mass closures are listed as withdrawn ('Superseded / withdrawn')")],
         "partial", True, ["analysis", "inspection"],
         "Mass models exist, but Vyovrinda's own Hall geometry and B(z) are not defined, and the Xe load and radiator size "
         "depend on Hall performance (gate 3). Final verification needs a weighed BoM (inspection)."),
    _req("RFP-MISSION", "rfp_envelope", "Mission duration",
         "Mission duration of 26,000 h.",
         _val("mission duration", "26000", "h", ENV),
         _src(ENV, [CONST + " (mission_hours; code comment '3 years')"]),
         [_mq("abep_sim/mission_env.py::propagate", "J2 propagator with eclipse"),
          _mq("abep_sim/mission5.py::run_mission_generic", "mission ROM over RFP.mission_hours"),
          _mq("abep_sim/transient.py::run_mission", "legacy transient (duty cycle from density vs thrust)")],
         [_ev("CLAUDE.md", "gate 5 numerical convergence = pass; gate 4 mission UQ conditional on gate 3"),
          _ev("abep_sim/data/golden_v1.json", "golden case_mission")],
         "partial", True, ["analysis"],
         "Propagator and mission ROM exist; mission closure needs Hall thrust and power (gate 3) and a DRDO spacecraft definition."),
    _req("RFP-FIRING", "rfp_envelope", "Firing (ignition) life",
         "Cumulative firing time above 15,000 h.",
         _val("firing time", "> 15000", "h", ENV),
         _src(ENV, [CONST + " (ignition_hours)"]),
         [_mq("abep_sim/life.py::hall_channel_life", "sputter + AO wall recession"),
          _mq("abep_sim/life.py::cathode_life", "cathode life / start cycles"),
          _mq("abep_sim/life.py::compressor_life", "bearing life"),
          _mq("abep_sim/life.py::reliability", "R(15,000 h), R(26,000 h)"),
          _mq("abep_sim/hall_map.py::HallMap", "erosion inputs only when wall_life_trustworthy")],
         [_ev("hallthruster_bridge/hall_map_schema_v1.json", "wall ion flux/energy fields defined; life use needs wall_life_trustworthy"),
          _ev("CLAUDE.md", "mechanism-level (probably robust): grids are life-limited by CEX + perveance window; gate 2 = pass")],
         "blocked_by_gate_3", True, ["analysis", "test"],
         "Hall channel erosion needs wall ion flux from an admitted, wall_life_trustworthy Hall map (none exist). "
         "Demonstrating life needs a wear test; no test data are in the repository."),
    _req("RFP-HALL", "rfp_envelope", "Hall thruster preferred",
         "Hall-effect thruster preferred as the accelerator.",
         None,
         _src(ENV, [CONST + " (hall_preferred)", "docs/HISTORY.md constraint table (chk_hall_preferred)"]),
         [_mq("abep_sim/archengine.py::enumerate_architectures", "architecture families incl. Hall"),
          _mq("abep_sim/hall_ensemble.py::require_admitted", "blocks non-admitted closures"),
          _mq("abep_sim/hall_map.py::HallMap", "Hall maps (admitted members only)")],
         [_ev("hallthruster_bridge/PINNED.toml", "HallThruster.jl pin (rule 7)"),
          _ev("hallthruster_bridge/identification/p5_xe_identification_sgb_v1_summary.json", "P5-Xe identification closed: transport not uniquely identifiable")],
         "partial", True, ["inspection", "analysis"],
         "Choosing a Hall accelerator is a design decision (inspection). A physics-backed choice among Hall-only / RF+Hall / "
         "ECR+Hall needs absolute Hall performance (gate 3). No architecture winner is claimed."),
    _req("RFP-PROP", "rfp_envelope", "Propellants: air and xenon",
         "Atmospheric air (intake-collected) and xenon as propellants.",
         None,
         _src(ENV, ["docs/HISTORY.md constraint table (N2 + nascent O; Xe as propellant)"]),
         [_mq("abep_sim/intake_tpmc.py::IntakeSurface", "frozen TPMC intake response surface"),
          _mq("abep_sim/compressor.py::DragCompressor", "compression of collected air"),
          _mq("abep_sim/reservoir.py::Reservoir", "atmospheric gas chamber"),
          _mq("abep_sim/aochem.py::inlet_composition", "wall O recombination -> thruster inlet composition"),
          _mq("abep_sim/mass_bom.py::xe_tank", "Xe storage")],
         [_ev("abep_sim/data/intake_surface_v1.json", "frozen intake surface provenance"),
          _ev("hallthruster_bridge/audit/n2_closure_verdicts_v1.json", "N2/N reaction set abep-n2n-0.11, COMPLETE_FOR_P5_N2_VALIDATION (domain-limited, not a general completeness claim)"),
          _ev("CLAUDE.md", "O2/O chemistry and intake-delivered mixtures only after next-work items 1-3 succeed")],
         "partial", True, ["analysis", "test"],
         "Gas path is modeled. Hall-discharge chemistry exists only for N2/N (validation domain T_e 2-30 eV); O/O2 is not "
         "started; Hall performance on air or Xe is gate-3 blocked."),
    _req("RFP-IC", "rfp_inferred_from_code", "Indigenous content (IC)",
         "Total IC >= 75 %; subsystem IC thruster >= 80 %, intake >= 80 %, compressor >= 60 %, PSE >= 70 % (as encoded in "
         "code; reading 'IC' as indigenous content follows docs/HISTORY.md).",
         _val("indigenous content (mass-weighted)",
              "total >= 0.75; thruster >= 0.80; intake >= 0.80; compressor >= 0.60; pse >= 0.70", "fraction", CONST),
         _src(CONST, ["docs/HISTORY.md constraint table (chk_ic_total, chk_ic_thruster)", "abep_sim/explorer.py header text ('IC >= 75 %')"]),
         [_mq("abep_sim/system.py::evaluate", "mass-weighted ic_total / ic_thruster checks (legacy closure)"),
          _mq("abep_sim/constants.py::RFPConstraints", "ic_total_min, ic_subsystem_min")],
         [_ev("docs/HISTORY.md", "component IC values are priors (e.g. the microwave-source IC prior); a supply-chain finding, not physics")],
         "partial", False, ["inspection"],
         "Not in the CLAUDE.md envelope summary; the clause, exact definition and subsystem thresholds must be checked "
         "against the RFP. Component IC values are assumed priors; needs a supplier-backed BoM."),
    _req("RFP-REDUND", "rfp_inferred_from_code", "Electronics redundancy",
         "No single-point failure in electronics (as stated in a code docstring).",
         None,
         _src("abep_sim/ppu.py module docstring ('Redundancy per RFP: no single-point failure in electronics')",
              ["docs/HISTORY.md ('cold-redundant converters (RFP redundancy)')"]),
         [_mq("abep_sim/ppu.py::default_ppu", "cold-redundant converters (mass doubled)"),
          _mq("abep_sim/life.py::reliability", "series reliability and SPF list")],
         [],
         "partial", False, ["analysis", "inspection"],
         "Redundancy is represented only as mass/reliability bookkeeping; there is no FMEA. The clause must be located in the RFP."),
    _req("RFP-AO-TEST", "rfp_inferred_from_code", "Atomic-oxygen beam testing",
         "AO-beam tests of materials (docs/HISTORY.md cites 'RFP 4.1a'; abep_sim/aochem.py calls them 'RFP-mandated').",
         None,
         _src("docs/HISTORY.md AO chemistry section ('AO-beam test (RFP 4.1a)'); abep_sim/aochem.py module docstring"),
         [_mq("abep_sim/aochem.py::erosion_depth_um", "AO erosion depth per material"),
          _mq("abep_sim/aochem.py::recombination_fraction", "wall recombination (gamma)"),
          _mq("abep_sim/aochem.py::fluence", "mission AO fluence")],
         [_ev("docs/HISTORY.md", "erosion yields and gammas are literature-class priors, to be replaced by coupon data")],
         "open", False, ["test"],
         "No AO-beam coupon data. The '4.1a' clause number is in-repo text only; verify."),
    _req("PRG-BID", "programmatic", "Bid close date",
         "Bid closes 05 Oct 2026.",
         {"quantity": "bid close date", "limit": "2026-10-05", "unit": "date", "value_source": ENV,
          "evidence_class": "assumed", "evidence_note": "transcribed from an in-repo summary; verify"},
         _src(ENV), [], [],
         "open", False, ["inspection"],
         "Programmatic item with no simulator quantity; listed so the submission date is traced."),
    _req("DER-NETDRAG", "derived_project", "Net drag compensation on air",
         "Thrust exceeds spacecraft drag on air alone. This is the physical purpose of ABEP; docs/HISTORY.md says the RFP does not state it.",
         None,
         {"where": "docs/HISTORY.md ('abep_closed' definition: the RFP does not state it)", "page_ref": NOT_RFP},
         [_mq("abep_sim/mission_env.py::spacecraft_drag", "drag"),
          _mq("abep_sim/archengine.py::close_architecture", "T/D")],
         [_ev("CLAUDE.md", "gate 3 FAIL")],
         "blocked_by_gate_3", True, ["analysis"],
         H3 + " Spacecraft ram area is a DRDO input not in the repository."),
    _req("DER-HALL-CLOSURE", "derived_project", "Admitted Hall transport closure",
         "Absolute Hall performance may be used only from admitted ensemble members (promotion rule; O4 dispositions).",
         None,
         {"where": "CLAUDE.md next-work item 1 (promotion rule) and item 3 (O4 gating)", "page_ref": NOT_RFP},
         [_mq("abep_sim/hall_ensemble.py::require_admitted", "rejects non-members"),
          _mq("abep_sim/hall_ensemble.py::_check_o4", "admission needs O4 dispositions"),
          _mq("abep_sim/hall_map.py::HallMap", "loads admitted members only")],
         [_ev("hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json", "v1 vacuum release manifest"),
          _ev("hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_decision.json", "all nine INCONCLUSIVE / NOT ELIGIBLE (v1 outcome is permanent)"),
          _ev("hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json", "pre-registered criteria")],
         "blocked_by_gate_3", True, ["analysis", "test"],
         "Credible set is empty. Outcomes of campaigns running after the v1 vacuum release (O4 staged escalations, facility) "
         "are not known to this matrix and are not stated."),
    _req("DER-THERMAL", "derived_project", "Heat rejection (Q_reject)",
         "Waste heat is rejected within the thermal design (mandatory comparison field Q_reject in CLAUDE.md).",
         None,
         {"where": "CLAUDE.md admissibility rule (mandatory fields)", "page_ref": NOT_RFP + "; check the RFP for thermal requirements"},
         [_mq("abep_sim/thermal.py::solve_network", "node temperatures"),
          _mq("abep_sim/thermal.py::size_radiator", "radiator sizing")],
         [],
         "partial", True, ["analysis", "test"],
         "Thermal network exists; Hall discharge heat loads need gate 3."),
    _req("DER-STARTUP", "derived_project", "Startup",
         "System reaches ignition conditions from cold (mandatory comparison field 'startup' in CLAUDE.md).",
         None,
         {"where": "CLAUDE.md admissibility rule (mandatory fields)", "page_ref": NOT_RFP + "; check the RFP"},
         [_mq("abep_sim/reservoir.py::startup_transient", "gas-chamber fill to ignition pressure"),
          _mq("abep_sim/ppu.py::load_modes", "startup electrical mode")],
         [],
         "partial", True, ["analysis", "demonstration"],
         "Gas-path fill is modeled; Hall ignition and sustainment on air are not established (gate 3)."),
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
         verification_status="reported_pass_in_CLAUDE.md_gate_table_not_rerun_here"),
]

CHAINS = [
    ("RFP-THR-MIN", "Hall accelerator with Vyovrinda-specific geometry and B(z) (TBD - requires a design definition)",
     "Analysis with admitted-member Hall maps, then thruster test", "None admissible: credible set empty; gate 3 FAIL"),
    ("RFP-THR-MAX", "Xe path (Xe chamber -> valve) into the same discharge; thrust cap in the mission controller",
     "Analysis (mission ROM) + thruster test", "None admissible (gate 3)"),
    ("RFP-PWR", "PPU converter set with cold redundancy; compressor motor drive",
     "Analysis on the common bus-power boundary + electrical test", "PPU/compressor models only; Hall discharge power unavailable (gate 3)"),
    ("RFP-MASS", "Mass BoM: Xe tank, Hall magnetic circuit, radiator, structure, PPU",
     "Analysis (CBE/MGA/MEV), then inspection (weighing)", "Models only; earlier closures withdrawn"),
    ("RFP-ALT", "Intake + compressor sized over the 180-230 km density range",
     "Analysis over the frozen NRLMSIS dataset", "Frozen atmosphere + golden; altitude hold gated by thrust (gate 3)"),
    ("RFP-MISSION", "Mission controller (altitude hold, Xe topping)", "Analysis (propagator + UQ)",
     "Convergence pass; mission UQ conditional on gate 3"),
    ("RFP-FIRING", "Channel wall material and magnetic topology; cathode; compressor bearings",
     "Analysis (erosion from wall_life_trustworthy maps) + wear test", "No trustworthy wall-flux map; no test data"),
    ("RFP-HALL", "Hall accelerator baseline family", "Inspection of design; comparison on the common bus boundary",
     "Comparison not populated; no winner claimed"),
    ("RFP-PROP", "Intake -> filter -> compressor -> atmospheric gas chamber -> valve; Xe chamber -> valve",
     "Analysis (TPMC ROM, compressor, reservoir, AO chemistry) + tests",
     "Frozen intake surface; N2/N chemistry abep-n2n-0.11 domain-limited; O/O2 not started"),
    ("RFP-IC", "Supplier selection per subsystem", "Inspection of BoM", "Priors only"),
    ("RFP-REDUND", "Cold-redundant PPU converters", "Analysis (FMEA) + inspection", "Mass/reliability bookkeeping only"),
    ("RFP-AO-TEST", "Wall / coating material selection", "Test (AO beam: erosion yield and recombination gamma)",
     "Literature priors only"),
    ("PRG-BID", "Bid package", "Inspection (submission record)", "None yet"),
    ("DER-NETDRAG", "Whole ABEP system", "Analysis (T/D over the mission)", "Gated by gate 3 and DRDO spacecraft data"),
    ("DER-HALL-CLOSURE", "Transport closure selection (never a Vyovrinda design variable)",
     "Pre-registered blind prediction of new evidence", "v1 vacuum INCONCLUSIVE; later campaigns not known here"),
    ("DER-THERMAL", "Radiator and conductive straps", "Analysis + thermal-vacuum test", "Network model only"),
    ("DER-STARTUP", "Reservoir fill, heater/keeper, ignition sequence", "Analysis + demonstration", "Gas-path transient only"),
    ("DER-MODEL-INTEGRITY", "Frozen datasets, golden benchmarks, convergence checks", "Test (golden check, pytest)",
     "Gates 1, 2, 5, 6 pass per CLAUDE.md"),
]

STATUS_VOCAB = {
    "modeled": "a model exists and its integrity checks are reported passing; says nothing about hardware compliance",
    "partial": "some of the needed quantities are modeled; others are missing or gated",
    "open": "no model or evidence yet",
    "blocked_by_gate_3": "compliance depends on absolute Hall performance, withdrawn until an admitted closure exists",
}


def build() -> dict:
    return {
        "schema": "abep-rtm-v1",
        "title": "Requirement traceability matrix - DRDO TDF ABEP-VLEO",
        "rfp_id": "DTDF/06/13516/DSP/ABEP/X/L/M/01",
        "rfp_id_source": "CLAUDE.md 'What this is'",
        "matrix_date": "2026-09-26",
        "base_commit": "daa0e75",
        "rfp_document_in_repository": False,
        "source_policy": (
            "The RFP document is not in the repository. Every requirement cites the in-repo text it was taken from and "
            "carries page_ref 'verify against RFP document' (or states it is project-derived). No RFP clauses, page numbers "
            "or values were invented. Rows marked rfp_inferred_from_code come from code docstrings or docs/HISTORY.md text "
            "that claim an RFP origin; that origin is unverified."),
        "searched": "grep -ri 'rfp|drdo' over CLAUDE.md, README.md, docs/, abep_sim/, pyproject.toml, tests/ at the base commit",
        "status_vocabulary": STATUS_VOCAB,
        "verification_methods": ["analysis", "test", "demonstration", "inspection"],
        "hall_status": H3 + (
            " The P5-N2 v1 vacuum outcome committed in the repository is INCONCLUSIVE / NOT ELIGIBLE for all nine screening "
            "candidates (permanent for v1). Results of campaigns running after that release are not known to this matrix "
            "and are not stated."),
        "gate_status_snapshot": {"source": "CLAUDE.md gate table (as of the base commit)",
                                 "1": "pass", "2": "pass", "3": "FAIL", "4": "done, conditional on gate 3",
                                 "5": "pass", "6": "pass"},
        "compliance_claim": ("none - this matrix claims no RFP compliance, no demonstrated ABEP closure, no architecture "
                             "winner and no transport admission"),
        "requirements": REQUIREMENTS,
        "chains": [dict(requirement_id=a, design_feature=b, verification=c, evidence=d) for a, b, c, d in CHAINS],
    }


def _cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_md(doc: dict) -> str:
    L = [f"# {doc['title']}", "",
         f"RFP {doc['rfp_id']} (id from {doc['rfp_id_source']}). Matrix date {doc['matrix_date']}, base commit "
         f"`{doc['base_commit']}`. Generated from `docs/traceability/build_rtm.py`; machine-readable copy `rtm_v1.json`. "
         "Do not edit this file by hand.", "",
         "## Read this first", "",
         f"- **Source policy.** {doc['source_policy']}",
         f"- **Hall status.** {doc['hall_status']}",
         f"- **Compliance claim:** {doc['compliance_claim']}.",
         "- Gate status (" + doc["gate_status_snapshot"]["source"] + "): "
         + ", ".join(f"{k} {v}" for k, v in doc["gate_status_snapshot"].items() if k != "source") + ".",
         "", "## Status vocabulary", ""]
    for k, v in doc["status_vocabulary"].items():
        L.append(f"- `{k}`: {v}")
    L += ["", "## Matrix", "",
          "| id | requirement | limit | source (page ref) | status | gate-3 dependent | verification | open gap |",
          "|---|---|---|---|---|---|---|---|"]
    for r in doc["requirements"]:
        v = r["value"]
        lim = f"{v['limit']} {v['unit']} ({v['evidence_class']})" if v else "-"
        L.append("| " + " | ".join(_cell(x) for x in [
            r["id"], f"{r['title']}: {r['statement']}", lim,
            f"{r['source']['where']} ({r['source']['page_ref']})", r["status"],
            "yes" if r["gate3_dependent"] else "no", ", ".join(r["verification_method"]), r["open_gap"]]) + " |")
    L += ["", "## Requirement -> model quantity -> current evidence", ""]
    for r in doc["requirements"]:
        L.append(f"### {r['id']} - {r['title']}")
        L.append("")
        L.append(f"Status `{r['status']}`; verification status `{r['verification_status']}`.")
        L.append("")
        if r["model_quantities"]:
            L.append("Model quantities:")
            for m in r["model_quantities"]:
                L.append(f"- `{m['ref']}`: {m['role']}")
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
          "| requirement | design feature | verification | evidence |", "|---|---|---|---|"]
    for c in doc["chains"]:
        L.append("| " + " | ".join(_cell(c[k]) for k in ("requirement_id", "design_feature", "verification", "evidence")) + " |")
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

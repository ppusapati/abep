//! M2 196-state RFP closure of the DBF-1 design point (NP-HALL-PARAMETRIC-ENVELOPE addendum A8,
//! `prereg_addendum_a8_m2_dbf1_v1.json`; owner decisions A9.34..A9.37).
//!
//! The one frozen design (DBF-1, read only through `abep_config::baseline`) is evaluated at every harness state, both
//! required modes, both layers. Harness v2 (A2 with A4 and A5) is run unchanged; A8 then replaces, per (state, mode),
//! the constraints it re-reads for the frozen design (NH-FLOW AIR, NH-ICP, NH-PBUS, NH-TD, NH-LIFE), marks every Hall
//! test NOT_EVALUATED with HALL_NUMERICS_NOT_CONVERGED (A9.36) and adds the DBF-1 necessary conditions
//! (A8-NH-INTAKE-DBF1, never eligible). The classification is the v2 procedure C0 / CA4 / C1..C4 verbatim.
//!
//! [`gather_dbf1`] reads the repository (fail closed); [`evaluate_dbf1`] is pure; [`record_dbf1`] renders the record.

use super::gather::{gather_m1, icp_mode};
use super::intake::{crosscheck_ok, Req, FAILS_IN_EVERY_SCENARIO, PASSES_IN_EVERY_SCENARIO, SCENARIO_DEPENDENT};
use super::*;
use crate::error::{model_error, AssessResult};
use abep_config::baseline::Dbf1Config;
use abep_gaspath::plenum_feed::{intake_side, reasons_from_bits, steady_sweep};
use abep_gaspath::stability::{stability_class_events, Controller, StabilityClass, WINDOW_S};
use abep_icp::evidence::{EvidenceRecord, QuantityType, Registered, UncertaintyRepr};
use abep_icp::geometry::{Orientation, Surface, SurfaceKind, ThermalNode};
use abep_icp::v2::case::{GeometryV2, VolumeModeV2};
use abep_mission::reference_drag::{reference_drag_for, DragArgs};
use abep_provenance::read_verified;
use abep_types::pyjson::Dict;
use std::f64::consts::PI;
use std::path::Path;

pub const A8_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a8_m2_dbf1_v1.json";
pub const A8_SHA256: &str = "816495c61e41c87be1ece60c3ce7950b191f4e4a322fd641698a3f39f7da4568";
pub const A8_MD_REL: &str = "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/PREREG_ADDENDUM_A8_M2_DBF1.md";
pub const A8_MD_SHA256: &str = "b7b66c1cbcd49705d42fa925ed31a8a74e932f79191ffd1e15d688a9b71d267d";
pub const A8_LOCK_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a8_m2_dbf1_lock_v1.json";
pub const A8_LOCK_SHA256: &str = "67e37fad110bc14bc36fbe3ff9c906d91e0e5873abdf614921e1196bda54b59c";

pub const RECORD_SCHEMA: &str = "abep_assess_m2_dbf1_closure_v1";
pub const STABILITY_SCHEMA: &str = "abep_m2_dbf1_feed_stability_python_reference_v1";
pub const LABEL: &str = "ACTUAL_DESIGN_EVALUATION (DBF-1) / PARAMETRIC / NOT_VALIDATED / NOT_A_PERFORMANCE_PREDICTION";

pub const A8_CONSTRAINT_ID: &str = "A8-NH-INTAKE-DBF1";
pub const HALL_NUMERICS_NOT_CONVERGED: &str = "HALL_NUMERICS_NOT_CONVERGED";
pub const A8_GAS_PATH_OUT_OF_DOMAIN: &str = "A8_DBF1_GAS_PATH_OUT_OF_DOMAIN_IN_SCENARIO";
pub const A8_ANODE_MATERIAL: &str = "A8_DBF1_ANODE_MATERIAL_FROZEN_P4_EVIDENCE_INCOMPLETE";
pub const A8_MET_NOTHING_ESTABLISHED: &str = "A8_DBF1_NECESSARY_CONDITION_MET_NOTHING_ESTABLISHED";
pub const A8_SCENARIO_DEPENDENT: &str = "A8_DBF1_SCENARIO_DEPENDENT";
pub const A8_A4_NOT_EVALUATED: &str = "A8_DBF1_A4_INPUTS_NOT_EVALUATED";
pub const HOST_DRAG_REFERENCE: &str = "HOST_DRAG_REFERENCE_PENDING_CUSTOMER_ICD";

/// The A8 levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Lvl {
    Area,
    Cap,
    Del,
}

impl Lvl {
    pub const ALL: [Lvl; 3] = [Lvl::Area, Lvl::Cap, Lvl::Del];
    pub fn as_str(self) -> &'static str {
        match self {
            Lvl::Area => "L-AREA-DBF1",
            Lvl::Cap => "L-CAP-DBF1",
            Lvl::Del => "L-DEL-DBF1",
        }
    }
    fn code_stem(self) -> &'static str {
        match self {
            Lvl::Area => "AREA",
            Lvl::Cap => "CAPTURE",
            Lvl::Del => "DELIVERED",
        }
    }
}

/// The A8 thrust targets: T12 (HC-01), T25 (HC-02), TD = D(state, scenario).
pub const TARGETS: [&str; 3] = ["T12", "T25", "TD"];

pub fn level_code(l: Lvl, t: usize) -> String {
    format!("A8_DBF1_{}_BELOW_REQUIRED_{}", l.code_stem(), TARGETS[t])
}

/// A9.31 sec. 21 category of a code (A8 codes first, then the A2 / v1 rule).
pub fn category_a8(code: &str) -> &'static str {
    match code {
        A8_GAS_PATH_OUT_OF_DOMAIN => "DESIGN_VARIABLE_LIMIT",
        A8_ANODE_MATERIAL
        | A8_MET_NOTHING_ESTABLISHED
        | A8_SCENARIO_DEPENDENT
        | A8_A4_NOT_EVALUATED
        | HALL_NUMERICS_NOT_CONVERGED
        | HOST_DRAG_REFERENCE => "MISSING_EVIDENCE",
        c if c.starts_with("A8_DBF1_") && c.contains("_BELOW_REQUIRED_") => "DESIGN_VARIABLE_LIMIT",
        other => category_a2(other),
    }
}

/// Report type of a code (A8 classification.blocker_types).
pub fn blocker_type(code: &str) -> &'static str {
    if code == HALL_NUMERICS_NOT_CONVERGED || code.contains("NUMERICAL_FAILURE") || code.contains("NUMERICS") {
        return "model-numerics";
    }
    match category_a8(code) {
        "FUNDAMENTAL_ARCHITECTURE_LIMIT" => "physics",
        "MODEL_DOMAIN_LIMIT" => "model-domain",
        "MISSING_EVIDENCE" => "missing-evidence",
        _ => "design-variable",
    }
}

// ------------------------------------------------------------------------------------------------ inputs

/// The DBF-1 upstream design at one (scenario, harness state).
#[derive(Debug, Clone, PartialEq)]
pub struct Point {
    pub in_domain: bool,
    pub reasons: Vec<String>,
    pub mdot_del: f64,
    pub x_mole: [f64; 3],
    pub p_el_w: f64,
    pub mdot_cap: f64,
    /// Stability class (governed Python reference, R2-verified): "S", "U" or "R".
    pub class: String,
    pub re_max: Option<f64>,
}

impl Point {
    /// In domain with a stable loop: the delivered flow is a held steady number.
    pub fn held(&self) -> bool {
        self.in_domain && self.class == "S"
    }
}

/// The DBF-1 upstream design in one admitted surface scenario.
#[derive(Debug, Clone, PartialEq)]
pub struct Scenario {
    pub scenario: String,
    /// Committed F7 minimum of the DBF-1 vector in this scenario's context (None: not a member there).
    pub committed_min: Option<f64>,
    /// Statewise minimum over the F7 state list of the rerun.
    pub rerun_min: f64,
    /// Harness order.
    pub points: Vec<Point>,
}

/// The drag of one harness state.
#[derive(Debug, Clone, PartialEq)]
pub struct StateDrag {
    pub q_pa: f64,
    pub d_body_n: f64,
    pub flags: Vec<String>,
    /// Per scenario (the DBF-1 scenario order).
    pub d_intake_n: Vec<f64>,
    pub d_total_n: Vec<f64>,
    /// (case id, body drag N) of every SR-DRAG-01 pool case (information).
    pub sensitivity: Vec<(String, f64)>,
}

/// Python / Rust stability cross-check summary.
#[derive(Debug, Clone, PartialEq)]
pub struct StabilityCheck {
    pub reference_rel: String,
    pub reference_sha256: String,
    pub environment: Value,
    pub n_rows: usize,
    pub n_agree: usize,
    pub counts: BTreeMap<String, usize>,
}

/// Everything A8 reads besides harness v2.
#[derive(Clone)]
pub struct Dbf1Inputs {
    pub cfg: Dbf1Config,
    pub base: M1Inputs,
    pub scenarios: Vec<Scenario>,
    pub drag: Vec<StateDrag>,
    pub icp: IcpPath,
    pub stability: StabilityCheck,
    pub provenance: Vec<(String, String)>,
}

/// A8 identity: json, md and lock verify and the lock names both files.
pub fn verify_a8(repo: &Path) -> AssessResult<()> {
    for (rel, sha) in [(A8_REL, A8_SHA256), (A8_MD_REL, A8_MD_SHA256), (A8_LOCK_REL, A8_LOCK_SHA256)] {
        read_verified(&repo.join(rel), sha)?;
    }
    let lock = super::gather::json(repo, A8_LOCK_REL, A8_LOCK_SHA256)?;
    let files = lock.as_dict().and_then(|d| d.get("files")).and_then(Value::as_dict);
    for (k, want) in
        [("prereg_addendum_a8_m2_dbf1_v1.json", A8_SHA256), ("PREREG_ADDENDUM_A8_M2_DBF1.md", A8_MD_SHA256)]
    {
        if files.and_then(|f| f.get(k)).and_then(Value::as_str) != Some(want) {
            return Err(model_error(format!("{A8_LOCK_REL}: files.{k} != {want}")));
        }
    }
    let dl = lock.as_dict().and_then(|d| d.get("dbf1_lock")).and_then(Value::as_dict);
    if dl.and_then(|d| d.get("sha256")).and_then(Value::as_str) != Some(abep_config::baseline::DBF1_LOCK_SHA256) {
        return Err(model_error(format!("{A8_LOCK_REL}: dbf1_lock differs from the pinned DBF-1 lock")));
    }
    Ok(())
}

fn ev(source: &str) -> EvidenceRecord {
    EvidenceRecord {
        source: Some(format!("docs/baseline/DBF-1/dbf1_v1.json {source}")),
        evidence_level: Some("7".into()),
        quantity_type: Some(QuantityType::Assumed),
        transformation_chain: Some("DBF-1 frozen engineering assumption -> NP-ICP v2 input (A8)".into()),
        uncertainty: Some(UncertaintyRepr::Categorical),
        applicability_domain: Some("hall_icp_neutralizer DBF-1 (A9.37)".into()),
        validation_status: Some("NOT_VALIDATED".into()),
    }
}

/// The DBF-1 NP-ICP v2 geometry (A8 P-ICP-DBF1): vessel, collector, two open ends.
pub fn icp_geometry(cfg: &Dbf1Config) -> Registered<GeometryV2> {
    let (r, l, lc) = (cfg.icp.radius_m, cfg.icp.length_m, cfg.icp.collector_axial_length_m);
    let surf = |id: &str, kind, area, o, node, material: &str| Surface {
        id: id.into(),
        kind,
        area_m2: area,
        orientation: o,
        material: material.into(),
        thermal_node: node,
        transmission: None,
    };
    let g = GeometryV2 {
        geometry_id: "DBF1-ICP-02".into(),
        radius_m: r,
        length_m: l,
        volume_mode: VolumeModeV2::AssumedGeometricTube,
        surfaces: vec![
            surf(
                "vessel",
                SurfaceKind::DielectricFloating,
                2.0 * PI * r * (l - lc),
                Orientation::Radial,
                ThermalNode::NVessel,
                &cfg.icp.vessel_material,
            ),
            surf(
                "collector",
                SurfaceKind::IonCollectorBiased,
                2.0 * PI * r * lc,
                Orientation::Radial,
                ThermalNode::NCollector,
                &cfg.icp.collector_material,
            ),
            surf("up", SurfaceKind::OpenUpstream, PI * r * r, Orientation::Axial, ThermalNode::RxH1Face, "OPEN"),
            surf("down", SurfaceKind::OpenDownstream, PI * r * r, Orientation::Axial, ThermalNode::Export, "OPEN"),
        ],
    };
    Registered::new(g, ev("DBF1-ICP-02 / DBF1-ICP-03 / DBF1-ICP-04 / DBF1-ICP-07 / DBF1-MAT-03"))
}

/// P-ICP-DBF1: NP-ICP v2 per mode on the registered-today case plus the DBF-1 geometry.
pub fn icp_path_dbf1(cfg: &Dbf1Config, base: &IcpPath) -> AssessResult<IcpPath> {
    use abep_icp::case::SupplyMode;
    use abep_icp::chemistry::ChemistryRegistration;
    use abep_icp::v2::testkit::registered_today_case_v2;
    let model = base.model.as_ref().ok_or_else(|| model_error("NP-ICP v2 model not loaded"))?;
    if (cfg.icp.f_rf_hz - abep_icp::constants::F_RF_REGISTERED_HZ).abs() > 0.0 {
        return Err(model_error("DBF-1 f_RF differs from the NP-ICP registered 13.56 MHz"));
    }
    let mut modes = BTreeMap::new();
    for (m, sm, gas) in
        [(Mode::AirPrimary, SupplyMode::AirPrimary, "AIR"), (Mode::XeContingency, SupplyMode::XeContingency, "XE")]
    {
        let mut case = registered_today_case_v2(sm, ChemistryRegistration::NotRegistered { gas: gas.into() });
        case.case_id = format!("DBF1_V2_{}", sm.as_str());
        case.geometry = Some(icp_geometry(cfg));
        let r = model.evaluate(&case);
        modes.insert(m, icp_mode(&r)?);
    }
    Ok(IcpPath {
        modes,
        producer_status: base.producer_status.clone(),
        provenance: format!("{} + DBF-1 geometry (A8 P-ICP-DBF1, ASSUMED_GEOMETRIC_TUBE)", base.provenance),
        model: base.model.clone(),
    })
}

/// The governed Python stability reference record: (scenario, state) -> (class, [(eq kind, re_max)]).
pub type StabilityRows = BTreeMap<(String, String), (String, Vec<(String, Option<f64>)>)>;

pub fn parse_stability(v: &Value, cfg: &Dbf1Config) -> AssessResult<(StabilityRows, Value)> {
    let d = v.as_dict().ok_or_else(|| model_error("stability reference: not a mapping"))?;
    let gs = |k: &str| d.get(k).and_then(Value::as_str).unwrap_or("");
    if gs("schema") != STABILITY_SCHEMA || gs("design_id") != cfg.upstream.design_id {
        return Err(model_error("stability reference: schema or design id differs from DBF-1"));
    }
    let sha = d.get("dbf1_config").and_then(Value::as_dict).and_then(|x| x.get("sha256")).and_then(Value::as_str);
    if sha != Some(abep_config::baseline::DBF1_CONFIG_SHA256) {
        return Err(model_error("stability reference: computed on another DBF-1 config"));
    }
    let mut out = BTreeMap::new();
    for r in d.get("rows").and_then(Value::as_list).ok_or_else(|| model_error("stability reference: rows"))? {
        let rd = r.as_dict().ok_or_else(|| model_error("stability row"))?;
        let g = |k: &str| rd.get(k).and_then(Value::as_str).map(str::to_string);
        let (Some(sc), Some(st), Some(cl)) = (g("scenario"), g("state_id"), g("class")) else {
            return Err(model_error("stability row: scenario / state_id / class"));
        };
        let mut evs = vec![];
        for e in rd.get("events").and_then(Value::as_list).unwrap_or(&[]) {
            let ed = e.as_dict().ok_or_else(|| model_error("stability event"))?;
            let kind = ed.get("eq").and_then(Value::as_str).ok_or_else(|| model_error("stability event eq"))?;
            let re = match ed.get("re_max") {
                Some(Value::Null) | None => None,
                Some(x) => Some(x.to_f64().map_err(|_| model_error("stability re_max"))?),
            };
            evs.push((kind.to_string(), re));
        }
        if !["S", "U", "R"].contains(&cl.as_str()) || out.insert((sc, st), (cl, evs)).is_some() {
            return Err(model_error("stability reference: bad class or duplicate row"));
        }
    }
    Ok((out, d.get("environment").cloned().unwrap_or(Value::Null)))
}

/// Every input of the A8 evaluation (fail closed).
pub fn gather_dbf1(
    repo: &Path,
    stability_rel: &Path,
    stability_sha256: &str,
    rust_commit: &str,
) -> AssessResult<Dbf1Inputs> {
    verify_a8(repo)?;
    let cfg = abep_config::baseline::load_dbf1(repo).map_err(|e| model_error(e.to_string()))?;
    let base = gather_m1(repo, None, None, rust_commit)?;
    let a5 = base.a5.as_ref().ok_or_else(|| model_error("A8 needs the A5 inputs of harness v2"))?;
    let up = abep_design::inputs::load_upstream_inputs(repo).map_err(|e| model_error(format!("A8: {e}")))?;
    let u = &cfg.upstream;
    if up.scenarios != u.scenarios {
        return Err(model_error("A8: the DBF-1 scenario set differs from the admitted F1 scenarios"));
    }
    let geo = up.geometry.get(&u.candidate).ok_or_else(|| model_error("A8: DBF-1 candidate not in F1"))?;
    if *geo != (u.area_m2, u.l_over_d, u.phi) {
        return Err(model_error("A8: DBF-1 candidate geometry differs from F1"));
    }
    let id = abep_design::optimizer::design_id(&u.candidate, &u.filter, &u.compressor, u.v_m3, u.p_set_pa);
    if id != u.design_id {
        return Err(model_error("A8: DBF-1 design id does not match its fields"));
    }
    // Governed Python stability reference (pinned by the run manifest).
    let sb = read_verified(&repo.join(stability_rel), stability_sha256)?;
    let sv = abep_types::pyjson::loads(std::str::from_utf8(&sb).map_err(|e| model_error(e.to_string()))?)?;
    let (rows, environment) = parse_stability(&sv, &cfg)?;
    let fc = up.filter(&u.filter).map_err(|e| model_error(e.to_string()))?;
    let plant = up.plant(&u.compressor).map_err(|e| model_error(e.to_string()))?;
    let pl = abep_design::optimizer::plenum(&up, u.v_m3, &u.wall).map_err(|e| model_error(e.to_string()))?;
    let ctrl = Controller {
        kp: u.controller.kp,
        ti_s: u.controller.ti_s,
        f_valve_hz: u.controller.f_valve_hz,
        authority: u.controller.authority,
    };
    let states = &a5.states;
    let f7_index: BTreeMap<&str, usize> = up.states.iter().enumerate().map(|(i, s)| (s.as_str(), i)).collect();
    let h_idx: Vec<usize> = states
        .iter()
        .map(|s| f7_index.get(s.as_str()).copied().ok_or_else(|| model_error(format!("A8: state {s} not in F1"))))
        .collect::<AssessResult<_>>()?;
    let ci = a5.candidates.iter().position(|c| c.id == u.candidate).ok_or_else(|| model_error("A8: candidate"))?;
    let mut scenarios = vec![];
    let (mut n_rows, mut n_agree) = (0usize, 0usize);
    let mut counts: BTreeMap<String, usize> = BTreeMap::new();
    for sc in &u.scenarios {
        let recs: Vec<_> = up
            .states
            .iter()
            .map(|st| up.record(&u.candidate, sc, st).cloned())
            .collect::<Result<_, _>>()
            .map_err(|e| model_error(e.to_string()))?;
        let ok: Vec<bool> = recs.iter().map(|r| r.f1_status == super::intake::FEASIBLE_AT_STATE).collect();
        let side = intake_side(&recs, fc, 1.0)?;
        let sw = steady_sweep(&side, plant, &pl, &up.materials, &[u.p_set_pa], Some(&ok))?;
        let rerun_min = sw.mdot_total_kgps.iter().copied().fold(f64::INFINITY, f64::min);
        let committed = a5
            .members
            .iter()
            .find(|m| m.design_id == u.design_id && &m.scenario == sc && m.wall == u.wall)
            .map(|m| m.mdot_delivered_min_kgps);
        if let Some(c) = committed {
            if !crosscheck_ok(rerun_min, c) {
                return Err(model_error(format!(
                    "A8: DBF-1 rerun minimum {rerun_min:e} in {sc} differs from the committed F7 value {c:e} (A5.1)"
                )));
            }
        }
        let cap = a5
            .capture
            .iter()
            .find(|c| c.candidate == ci && &c.scenario == sc)
            .ok_or_else(|| model_error("A8: capture rows"))?;
        let mut points = Vec::with_capacity(states.len());
        for (hi, (st, fi)) in states.iter().zip(&h_idx).enumerate() {
            let (cl, evs) = rows
                .get(&(sc.clone(), st.clone()))
                .ok_or_else(|| model_error(format!("A8: no stability row {sc} {st}")))?;
            let rust = stability_class_events(fc, plant, &pl, ctrl, &up.materials, &recs[*fi], u.p_set_pa, WINDOW_S)?;
            let rc = match rust.class {
                StabilityClass::Stable => "S",
                StabilityClass::Unstable => "U",
                StabilityClass::Refused => "R",
            };
            let kinds_r: Vec<&str> = rust.equilibria.iter().map(|e| e.kind.as_str()).collect();
            let kinds_p: Vec<&str> = evs.iter().map(|e| e.0.as_str()).collect();
            n_rows += 1;
            if rc != cl || kinds_r != kinds_p {
                return Err(model_error(format!(
                    "A8 R2: Rust stability class {rc} {kinds_r:?} differs from the Python reference {cl} {kinds_p:?} at \
                     {sc} {st}"
                )));
            }
            n_agree += 1;
            *counts.entry(cl.clone()).or_default() += 1;
            let re_max = evs.iter().filter_map(|e| e.1).fold(None, |m: Option<f64>, x| Some(m.map_or(x, |m| m.max(x))));
            let bits = sw.bits[*fi];
            points.push(Point {
                in_domain: sw.in_domain[*fi] && bits == 0,
                reasons: reasons_from_bits(bits).into_iter().map(str::to_string).collect(),
                mdot_del: sw.mdot_total_kgps[*fi],
                x_mole: [sw.x_s_flow_mole[0][*fi], sw.x_s_flow_mole[1][*fi], sw.x_s_flow_mole[2][*fi]],
                p_el_w: sw.p_el_w[*fi],
                mdot_cap: cap.rows[hi].mdot(),
                class: cl.clone(),
                re_max,
            });
        }
        scenarios.push(Scenario { scenario: sc.clone(), committed_min: committed, rerun_min, points });
    }
    // Drag (P-TD-DBF1).
    let atm = abep_mission::intake_drag::EnvelopeAtmospheres::load(repo)?;
    let mut drag = Vec::with_capacity(states.len());
    for st in states {
        let a = atm.get(st).ok_or_else(|| model_error(format!("A8: no envelope atmosphere for {st}")))?;
        let q = 0.5 * a.rho * a.v * a.v;
        let mut st_dict = Dict::new();
        st_dict.insert("source", Value::str("abep_mission::intake_drag::EnvelopeAtmospheres (F1 envelope states)"));
        st_dict.insert("state_id", Value::str(st.clone()));
        let call = |case: &str, dpa: f64| {
            reference_drag_for(
                case,
                &DragArgs::numeric(
                    a.rho,
                    a.v,
                    u.area_m2,
                    dpa / q,
                    "F1 intake-face drag per unit frontal area (abep_mission::intake_drag) x DBF-1 A 0.25 m^2",
                    st_dict.clone(),
                    &cfg.drag.intake_accounting,
                ),
            )
        };
        let (mut di, mut dt) = (vec![], vec![]);
        let mut body = None;
        let mut flags = vec![];
        for sc in &u.scenarios {
            let (dpa, _) = up.drag_per_area(sc, u.l_over_d, u.phi, st).map_err(|e| model_error(e.to_string()))?;
            let r = call(&cfg.drag.case_id, dpa)?;
            if (r.case.cd, r.case.a_ref_m2) != (cfg.drag.cd, cfg.drag.a_ref_m2) {
                return Err(model_error("A8: DBF-1 drag case differs from the reference register"));
            }
            body = Some(r.d_reference_n);
            flags = r.flags.clone();
            di.push(r.d_intake_n);
            dt.push(r.d_total_n);
        }
        let (dpa0, _) =
            up.drag_per_area(&u.scenarios[0], u.l_over_d, u.phi, st).map_err(|e| model_error(e.to_string()))?;
        let mut sens = vec![];
        for c in &cfg.drag.sensitivity_cases {
            sens.push((c.clone(), call(c, dpa0)?.d_reference_n));
        }
        drag.push(StateDrag {
            q_pa: q,
            d_body_n: body.expect("non-empty scenarios"),
            flags,
            d_intake_n: di,
            d_total_n: dt,
            sensitivity: sens,
        });
    }
    let icp = icp_path_dbf1(&cfg, &base.icp)?;
    let mut provenance = vec![
        (A8_REL.to_string(), A8_SHA256.to_string()),
        (A8_MD_REL.to_string(), A8_MD_SHA256.to_string()),
        (A8_LOCK_REL.to_string(), A8_LOCK_SHA256.to_string()),
        (abep_config::baseline::DBF1_LOCK_REL.to_string(), abep_config::baseline::DBF1_LOCK_SHA256.to_string()),
        (abep_config::baseline::DBF1_RECORD_REL.to_string(), abep_config::baseline::DBF1_RECORD_SHA256.to_string()),
        (abep_config::baseline::DBF1_CONFIG_REL.to_string(), abep_config::baseline::DBF1_CONFIG_SHA256.to_string()),
        (stability_rel.to_string_lossy().to_string(), stability_sha256.to_string()),
        (
            abep_mission::reference_drag::REGISTER_REL.to_string(),
            abep_mission::reference_drag::REGISTER_SHA256.to_string(),
        ),
    ];
    provenance.extend(a5.provenance.iter().cloned());
    Ok(Dbf1Inputs {
        cfg,
        base,
        scenarios,
        drag,
        icp,
        stability: StabilityCheck {
            reference_rel: stability_rel.to_string_lossy().to_string(),
            reference_sha256: stability_sha256.to_string(),
            environment,
            n_rows,
            n_agree,
            counts,
        },
        provenance,
    })
}

// ------------------------------------------------------------------------------------------------ evaluation

/// One (level, target) at one state: per scenario k (None: fails / unbounded) and the verdict.
#[derive(Debug, Clone, PartialEq)]
pub struct LevelEval {
    pub verdict: &'static str,
    pub k: Vec<Option<f64>>,
    pub k_fav: Option<f64>,
    pub k_unfav: Option<f64>,
}

/// The A8 quantities of one state (AIR).
#[derive(Debug, Clone, PartialEq)]
pub struct StateA8 {
    pub levels: BTreeMap<(Lvl, usize), LevelEval>,
    /// mdot_req,in at T12 / T25 (scenario independent) and per scenario at TD.
    pub mdot_req_in: [Option<f64>; 2],
    pub mdot_req_in_td: Vec<Option<f64>>,
    pub a_req_td: Vec<Option<f64>>,
    pub ood_scenarios: Vec<String>,
    pub unstable_scenarios: Vec<String>,
    /// (min, max) delivered flow over held scenarios.
    pub mdot_del_range: Option<(f64, f64)>,
    pub compressor_min_w: Option<f64>,
}

/// The A8 evaluation of one (state, mode).
#[derive(Debug, Clone)]
pub struct CellA8 {
    pub eval: StateModeEval,
    pub binding: Option<(String, String, String)>,
}

#[derive(Debug, Clone)]
pub struct Dbf1Outcome {
    pub base: M1Outcome,
    pub outcome: ClosureOutcome,
    pub states: Vec<(StateRef, BTreeMap<Mode, CellA8>)>,
    pub air: Vec<StateA8>,
}

fn verdict(k: &[Option<f64>]) -> &'static str {
    let fails = |x: &Option<f64>| x.is_none_or(|k| k > 1.0);
    if k.iter().all(fails) {
        FAILS_IN_EVERY_SCENARIO
    } else if !k.iter().any(fails) {
        PASSES_IN_EVERY_SCENARIO
    } else {
        SCENARIO_DEPENDENT
    }
}

fn level_eval(k: Vec<Option<f64>>) -> LevelEval {
    let with: Vec<f64> = k.iter().flatten().copied().collect();
    let any_none = k.iter().any(Option::is_none);
    LevelEval {
        verdict: verdict(&k),
        k_fav: with.iter().copied().reduce(f64::min),
        k_unfav: if any_none { None } else { with.iter().copied().reduce(f64::max) },
        k,
    }
}

/// The A8 quantities of harness state `i` (pure).
pub fn state_a8(inp: &Dbf1Inputs, req: Option<&Req>, t_req: [f64; 2], i: usize) -> AssessResult<StateA8> {
    let sc = &inp.scenarios;
    let area = inp.cfg.upstream.area_m2;
    let d = &inp.drag[i];
    let ood: Vec<String> =
        sc.iter().filter(|s| !s.points[i].in_domain || s.points[i].class == "R").map(|s| s.scenario.clone()).collect();
    let unstable: Vec<String> = sc.iter().filter(|s| s.points[i].class == "U").map(|s| s.scenario.clone()).collect();
    let held: Vec<&Point> = sc.iter().map(|s| &s.points[i]).filter(|p| p.held()).collect();
    let rng = (!held.is_empty()).then(|| {
        let v: Vec<f64> = held.iter().map(|p| p.mdot_del).collect();
        (v.iter().copied().fold(f64::INFINITY, f64::min), v.iter().copied().fold(f64::NEG_INFINITY, f64::max))
    });
    let comp = sc
        .iter()
        .map(|s| &s.points[i])
        .filter(|p| p.in_domain)
        .map(|p| p.p_el_w)
        .fold(None, |m: Option<f64>, x| Some(m.map_or(x, |m| m.min(x))));
    let mut levels = BTreeMap::new();
    let (mut mri, mut mri_td, mut areq_td) = ([None, None], vec![], vec![]);
    if let Some(r) = req {
        for (k, slot) in mri.iter_mut().enumerate() {
            *slot = Some(r.mdot_req_in(area, k, t_req)?);
        }
        for dt in &d.d_total_n {
            mri_td.push(Some(abep_mission::conservation_bounds::mdot_required(*dt, r.p_avail_w + r.q_max * area)?));
            areq_td.push(Some(abep_mission::conservation_bounds::area_required(*dt, r.p_avail_w, r.phi_max, r.q_max)?));
        }
        for (t, _) in TARGETS.iter().enumerate() {
            for l in Lvl::ALL {
                let ks: Vec<Option<f64>> = sc
                    .iter()
                    .enumerate()
                    .map(|(j, s)| {
                        let p = &s.points[i];
                        let (a_req, m_req) = if t < 2 {
                            (r.a_req[t], mri[t].expect("set"))
                        } else {
                            (areq_td[j].expect("set"), mri_td[j].expect("set"))
                        };
                        match l {
                            Lvl::Area => Some(a_req / area),
                            Lvl::Cap => (p.mdot_cap > 0.0).then(|| m_req / p.mdot_cap),
                            Lvl::Del => (p.held() && p.mdot_del > 0.0).then(|| m_req / p.mdot_del),
                        }
                    })
                    .collect();
                levels.insert((l, t), level_eval(ks));
            }
        }
    }
    Ok(StateA8 {
        levels,
        mdot_req_in: mri,
        mdot_req_in_td: mri_td,
        a_req_td: areq_td,
        ood_scenarios: ood,
        unstable_scenarios: unstable,
        mdot_del_range: rng,
        compressor_min_w: comp,
    })
}

fn open(id: &str, codes: Vec<String>, detail: impl Into<String>) -> Constraint {
    let mut c = Constraint::open(id, codes, detail);
    c.codes.sort();
    c.codes.dedup();
    c
}

fn non_closing_ne(id: &str, codes: Vec<String>, detail: String) -> Constraint {
    Constraint {
        id: id.into(),
        hall_specific: false,
        status: NON_CLOSING,
        eligible_close: false,
        eligible_non_close: false,
        codes,
        detail,
        evidence_conditions: vec![],
    }
}

/// The A8 constraint of a state (AIR).
pub fn a8_constraint(s: &StateA8) -> Constraint {
    if s.levels.is_empty() {
        return open(A8_CONSTRAINT_ID, vec![A8_A4_NOT_EVALUATED.into()], "the state's A4 AIR inputs are not evaluated");
    }
    let mut fails: Vec<String> = vec![];
    let mut dep = false;
    for ((l, t), e) in &s.levels {
        if e.verdict == FAILS_IN_EVERY_SCENARIO {
            fails.push(level_code(*l, *t));
        } else if e.verdict == SCENARIO_DEPENDENT {
            dep = true;
        }
    }
    fails.sort();
    if !fails.is_empty() {
        return non_closing_ne(
            A8_CONSTRAINT_ID,
            fails.clone(),
            format!(
                "the DBF-1 design misses the A4 necessary condition in every admitted surface scenario ({}); \
                 DESIGN_VARIABLE_LIMIT (A9.35), never eligible",
                fails.join(", ")
            ),
        );
    }
    let code = if dep { A8_SCENARIO_DEPENDENT } else { A8_MET_NOTHING_ESTABLISHED };
    open(A8_CONSTRAINT_ID, vec![code.into()], "necessary conditions only: a pass establishes nothing")
}

/// NH-FLOW (AIR) for the frozen design (A8 nh_flow_dbf1).
pub fn nh_flow_dbf1(s: &StateA8) -> Constraint {
    if !s.ood_scenarios.is_empty() {
        return open(
            "NH-FLOW",
            vec![A8_GAS_PATH_OUT_OF_DOMAIN.into()],
            format!(
                "the DBF-1 steady point is out of domain (or the loop is refused) in {}",
                s.ood_scenarios.join(", ")
            ),
        );
    }
    if !s.unstable_scenarios.is_empty() {
        return non_closing_ne(
            "NH-FLOW",
            vec![FEED_LOOP_UNSTABLE_EQUILIBRIUM.into()],
            format!(
                "the DBF-1 feed loop is UNSTABLE_EQUILIBRIUM in {} (never eligible)",
                s.unstable_scenarios.join(", ")
            ),
        );
    }
    open(
        "NH-FLOW",
        vec![NO_HALL_CLOSING_POINT.into(), HALL_NUMERICS_NOT_CONVERGED.into()],
        "the DBF-1 delivered flow is held in every admitted scenario; no Hall closing point to evaluate it at (A9.36)",
    )
}

/// The A8 evaluation (pure).
pub fn evaluate_dbf1(inp: &Dbf1Inputs) -> AssessResult<Dbf1Outcome> {
    let base_out = evaluate(&inp.base)?;
    let a5 = base_out.a5.as_ref().ok_or_else(|| model_error("A8: no A5 outcome"))?;
    let ti = &inp.base.today;
    let hc03 = ti.limits.p_bus_max_w;
    let mut air = Vec::with_capacity(base_out.states.len());
    let mut v2_states = Vec::with_capacity(base_out.states.len());
    let mut cells = Vec::with_capacity(base_out.states.len());
    for (i, (st, modes)) in base_out.states.iter().enumerate() {
        if a5.states.get(i).map(|x| &x.state_id) != Some(&st.state_id) {
            return Err(model_error("A8: A5 / harness state order differs"));
        }
        let sa = state_a8(inp, a5.states[i].req.as_ref(), a5.t_req_n, i)?;
        let env_ok =
            ti.mission.state(&st.state_id).is_some_and(|r| r.environment_status == abep_types::EvalStatus::Evaluated);
        let mut out_modes = BTreeMap::new();
        let mut v2_modes = BTreeMap::new();
        for m in REQUIRED_MODES {
            let e = modes.get(&m).ok_or_else(|| model_error("A8: missing mode"))?;
            let hall: Vec<HallTestResult> = tests_of(&inp.base, m)
                .iter()
                .map(|t| {
                    hall_not_evaluated(
                        *t,
                        HALL_NUMERICS_NOT_CONVERGED,
                        "A9.36: A6 STOP_NO_LEVEL_CONVERGED (A3 A3_NOT_ADEQUATE); no Hall thrust / I_d / P_d enters M2",
                    )
                })
                .collect();
            // Bus with the DBF-1 ICP loads and compressor draw.
            let mut ov: Vec<BusOverride> = vec![];
            if let Some(im) = inp.icp.modes.get(&m) {
                for (s, p, src) in &im.loads {
                    ov.push((*s, *p, src.clone(), false));
                }
            }
            if m == Mode::AirPrimary {
                if let Some(pc) = sa.compressor_min_w {
                    ov.push((
                        Slot::Compressor,
                        pc,
                        format!("DBF-1 compressor draw at {} (min over in-domain scenarios; F7 chain)", st.state_id),
                        true,
                    ));
                }
            }
            let bus = non_hall_bus(&inp.base.mp, &ov)?;
            let mut nh: Vec<Constraint> = vec![];
            for c in e.eval.constraints.iter().filter(|c| !c.hall_specific) {
                let replaced = match c.id.as_str() {
                    "NH-FLOW" if m == Mode::AirPrimary => Some(nh_flow_dbf1(&sa)),
                    "NH-ICP" => {
                        let im = inp.icp.modes.get(&m);
                        Some(match im.and_then(|x| x.i_e_cap_fav_a) {
                            None => {
                                let mut codes = vec![ICP_CAPACITY_NOT_EVALUATED.to_string()];
                                if let Some(x) = im {
                                    codes.extend(x.codes.iter().cloned());
                                }
                                open("NH-ICP", codes, "NP-ICP v2 at the DBF-1 geometry gives no converged I_e,cap")
                            }
                            Some(_) => open(
                                "NH-ICP",
                                vec![NO_HALL_CLOSING_POINT.into()],
                                "no Hall closing point to evaluate I_e,cap against",
                            ),
                        })
                    }
                    "NH-PBUS" => Some(if bus.lb_eligible_w >= hc03 {
                        Constraint {
                            id: "NH-PBUS".into(),
                            hall_specific: false,
                            status: NON_CLOSING,
                            eligible_close: false,
                            eligible_non_close: true,
                            codes: vec![v1::PBUS_NON_HALL_LOWER_BOUND_AT_LIMIT.into()],
                            detail: format!("non-Hall lower bound of admitted loads {} W >= {hc03} W", bus.lb_eligible_w),
                            evidence_conditions: vec![],
                        }
                    } else if bus.p_nonhall_w.is_some() && bus.hall_path_eff.is_some() {
                        open("NH-PBUS", vec![NO_HALL_CLOSING_POINT.into()], "complete ledger; no Hall closing point")
                    } else {
                        open(
                            "NH-PBUS",
                            vec![v1::BUS_LEDGER_NOT_COMPLETE.into()],
                            format!(
                                "layer (a) ledger at DBF-1: {} TBD term(s) at their favorable lower bound; P_nonHall,LB \
                                 {} W",
                                bus.tbd.len(),
                                bus.lb_w
                            ),
                        )
                    }),
                    "NH-TD" => Some(open(
                        "NH-TD",
                        vec![HALL_NUMERICS_NOT_CONVERGED.into(), HOST_DRAG_REFERENCE.into()],
                        "D(state) evaluated (RC-DIAMANT + F1 intake); T_available NOT_EVALUATED (A9.36)",
                    )),
                    "NH-LIFE" => Some(open(
                        "NH-LIFE",
                        vec![v1::LIFE_NOT_EVALUATED.into(), HALL_WALL_LIFE_INPUTS_NOT_TRUSTWORTHY.into(), A8_ANODE_MATERIAL.into()],
                        "no evaluated H-1 / ICP firing life; DBF-1 anode INCONEL 600 frozen, P4 gate evidence incomplete",
                    )),
                    _ => None,
                };
                nh.push(replaced.unwrap_or_else(|| c.clone()));
            }
            if m == Mode::AirPrimary {
                nh.push(a8_constraint(&sa));
            }
            if !env_ok {
                for c in &mut nh {
                    if !c.eligible_non_close {
                        *c = open(&c.id.clone(), vec![ENVIRONMENT_NOT_EVALUATED.into()], "environment not EVALUATED");
                    }
                }
            }
            let eval = v1::evaluate_mode(&hall, &nh);
            let binding = eval
                .constraints
                .iter()
                .find(|c| c.eligible_non_close)
                .or_else(|| eval.constraints.iter().find(|c| c.status == NON_CLOSING))
                .or_else(|| eval.constraints.iter().find(|c| !c.eligible_close))
                .map(|c| {
                    let code = c.codes.first().cloned().unwrap_or_default();
                    (c.id.clone(), code.clone(), category_a8(&code).to_string())
                });
            let sme = StateModeEval {
                eval,
                hall,
                bus,
                joint_hardware: BTreeSet::new(),
                joint_best: vec![],
                delivered: if m == Mode::AirPrimary && sa.ood_scenarios.is_empty() && sa.unstable_scenarios.is_empty() {
                    sa.mdot_del_range.map(|r| (r.0, None))
                } else {
                    None
                },
                binding_constraint: binding.as_ref().map(|b| b.0.clone()),
            };
            v2_modes.insert(m, sme.clone());
            out_modes.insert(m, CellA8 { eval: sme, binding });
        }
        air.push(sa);
        v2_states.push((st.clone(), v2_modes));
        cells.push((st.clone(), out_modes));
    }
    let mut outcome = classify_v2(ti.credible_set_empty, false, &v2_states);
    // C1 reading (A8 classification.C1_reading): the blocker reads HALL_NUMERICS_NOT_CONVERGED.
    for b in &mut outcome.blockers {
        if b.0 == v1::HALL_ENVELOPE_NOT_RUN {
            b.0 = HALL_NUMERICS_NOT_CONVERGED.into();
        }
    }
    let mut merged: BTreeMap<String, usize> = BTreeMap::new();
    for (k, n) in outcome.blockers.drain(..) {
        let e = merged.entry(k).or_default();
        *e = (*e).max(n);
    }
    outcome.blockers = merged.into_iter().collect();
    Ok(Dbf1Outcome { base: base_out, outcome, states: cells, air })
}

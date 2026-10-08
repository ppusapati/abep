//! Production inputs of harness v2 (addendum A2 sec. paths): every producer is read from the repository with its pin;
//! a pin that does not verify, or a producer MODEL_ERROR, refuses the record (fail closed, no partial record).

use super::*;
use crate::closure::{gather, quantity_codes};
use crate::error::{model_error, AssessResult};
use abep_data::gz::read_container;
use abep_icp::v2::testkit::registered_today_case_v2;
use abep_icp::v2::IcpModelV2;
use abep_provenance::read_verified;
use abep_subsystems::power::demand::Upstream;
use abep_subsystems::power::icp_bus::icp_upstream_loads_v2;
use abep_types::pyjson::{loads, Dict};
use std::path::Path;

pub const F7_REPORT_REL: &str =
    "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY/parity_report_v1.json";
pub const F7_REPORT_SHA256: &str = "887c39ef80063123162160f12681ff5461a7a4a09d1cd181526d8db7c69d84da";
pub const F7_PARETO_REL: &str =
    "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY/reference_outputs/f7_pareto_blocks_v1.json.gz";
pub const F7_PARETO_SHA256: &str = "de6ee69f21d4e5b4daba6e1b8bed263598b950b19cae9da49d309ec4d7664f00";
pub const F7_PARETO_JSON_SHA256: &str = "07d5335d4f020fa1fa9e2d91796669b2790383c74a486aa84d7e4de37889af3c";
pub const F8_REPORT_REL: &str =
    "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY/parity_report_v1.json";
pub const F8_REPORT_SHA256: &str = "863dc697e86195ddc07c59c2dbe3dfacfd8ab54adb8f9b57e417485e991aef92";
pub const F8_STUDY_REL: &str =
    "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY/reference_outputs/f8_study_v1.json.gz";
pub const F8_STUDY_SHA256: &str = "741703b917d36f9f00172de7a48dca80ff2f58ab7ed41263fb563823a5b3e595";
pub const F8_STUDY_JSON_SHA256: &str = "095585631e36b708c168561cda27924053b221e288d82cdcd4dcec8dfb38e867";
pub const PLENUM_V8_REL: &str = "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_PLENUM_FEED_PY/parity_report_v8.json";
pub const PLENUM_V8_SHA256: &str = "3f427a54dd5cecc002539b2537d1052d5e4e33c66bc1ba1219a0558e4abaa8d7";
pub const LEDGER_REL: &str = "docs/rust_migration/migration_state_v1.json";

fn json(repo: &Path, rel: &str, sha: &str) -> AssessResult<Value> {
    let b = read_verified(&repo.join(rel), sha)?;
    Ok(loads(std::str::from_utf8(&b).map_err(|e| model_error(format!("{rel}: {e}")))?)?)
}

fn gz_json(repo: &Path, rel: &str, sha: &str, json_sha: &str) -> AssessResult<Value> {
    let gz = std::fs::read(repo.join(rel)).map_err(|e| model_error(format!("{rel}: {e}")))?;
    let raw = read_container(&gz, rel, sha, None, json_sha)?;
    Ok(loads(std::str::from_utf8(&raw).map_err(|e| model_error(format!("{rel}: {e}")))?)?)
}

fn at<'a>(v: &'a Value, path: &[&str]) -> Option<&'a Value> {
    path.iter().try_fold(v, |x, k| x.as_dict().and_then(|d| d.get(k)))
}

fn num(v: Option<&Value>) -> Option<f64> {
    match v {
        Some(Value::Float(f)) => Some(*f),
        Some(Value::Int(_)) => v.and_then(|x| x.to_f64().ok()),
        _ => None,
    }
}

fn st(v: Option<&Value>) -> String {
    v.and_then(Value::as_str).unwrap_or("MISSING").to_string()
}

fn f(x: f64) -> Value {
    Value::Float(x)
}

/// Identity of the A2 files (and the v1 preregistration they amend); refused unless every pin verifies.
pub fn verify_a2(repo: &Path) -> AssessResult<()> {
    for (rel, sha) in [
        (A2_REL, A2_SHA256),
        (A2_MD_REL, A2_MD_SHA256),
        (A2_LOCK_REL, A2_LOCK_SHA256),
        (abep_hall::envelope::PREREG_REL, abep_hall::envelope::PREREG_SHA256),
        (abep_hall::envelope::LOCK_REL, abep_hall::envelope::LOCK_SHA256),
    ] {
        read_verified(&repo.join(rel), sha)?;
    }
    let lock = json(repo, A2_LOCK_REL, A2_LOCK_SHA256)?;
    for (k, want) in [("prereg_addendum_a2_m1_closure_paths.json", A2_SHA256), ("PREREG_ADDENDUM_A2.md", A2_MD_SHA256)]
    {
        if at(&lock, &["files", k]).and_then(Value::as_str) != Some(want) {
            return Err(model_error(format!("{A2_LOCK_REL}: files.{k} != {want}")));
        }
    }
    Ok(())
}

/// Is A1 on this line (json, md and lock present and hash-verified, superseding the A2-named identity)? A partial or
/// different A1 is refused.
pub fn a1_on_line(repo: &Path) -> AssessResult<bool> {
    let files = [(A1_REL, A1_SHA256), (A1_MD_REL, A1_MD_SHA256), (A1_LOCK_REL, A1_LOCK_SHA256)];
    let present: Vec<bool> = files.iter().map(|(r, _)| repo.join(r).exists()).collect();
    if present.iter().all(|p| !p) {
        return Ok(false);
    }
    if !present.iter().all(|p| *p) {
        return Err(model_error("A1 json, md and lock must be present together"));
    }
    for (r, sha) in files {
        read_verified(&repo.join(r), sha)?;
    }
    let a1 = json(repo, A1_REL, A1_SHA256)?;
    if !st(at(&a1, &["supersedes", "record"])).contains(A1_NAMED_IN_A2_SHA256) {
        return Err(model_error("A1 does not supersede the addendum_01 identity A2 names"));
    }
    Ok(true)
}

/// The Hall AIR reaction set (NP-HALL-CHEM-AIR): label, status and admission, as read through abep-chem.
pub fn air_chemistry(repo: &Path) -> AssessResult<(bool, Value)> {
    let set = abep_chem::hall_air::AirSet::load(repo)?;
    let adm = set.admission();
    let admission = match &adm {
        Ok(()) => "ADMITTED_FOR_PARAMETRIC_ENVELOPE".to_string(),
        Err(e) => e.to_string(),
    };
    let info = super::record::d(vec![
        ("contract", Value::str(abep_chem::hall_air::CONTRACT_ID)),
        ("label", Value::str(set.label.clone())),
        ("status", Value::str(set.status.as_str())),
        ("admission", Value::str(admission)),
    ]);
    Ok((adm.is_ok(), info))
}

/// P-FLOW from the admitted F7 / F8 records (captured reference outputs; the robust set carried unchanged).
pub fn flow_path(repo: &Path) -> AssessResult<FlowPath> {
    let f7r = json(repo, F7_REPORT_REL, F7_REPORT_SHA256)?;
    let f8r = json(repo, F8_REPORT_REL, F8_REPORT_SHA256)?;
    let p8 = json(repo, PLENUM_V8_REL, PLENUM_V8_SHA256)?;
    for (r, rel) in [(&f7r, F7_REPORT_REL), (&f8r, F8_REPORT_REL)] {
        if st(at(r, &["verdict"])) != "PARITY_PASS" || st(at(r, &["admission"])) != "ADMITTED" {
            return Err(model_error(format!("{rel}: not PARITY_PASS / ADMITTED")));
        }
    }
    let study = gz_json(repo, F8_STUDY_REL, F8_STUDY_SHA256, F8_STUDY_JSON_SHA256)?;
    let carried = at(&study, &["carried_robust_set"]).ok_or_else(|| model_error("F8 study: carried_robust_set"))?;
    let robust: Vec<String> = at(carried, &["members"])
        .and_then(Value::as_list)
        .ok_or_else(|| model_error("F8 study: carried_robust_set.members"))?
        .iter()
        .map(|x| x.as_str().map(str::to_string).ok_or_else(|| model_error("F8 robust member id")))
        .collect::<AssessResult<_>>()?;
    let decomposition = at(&f8r, &["decomposition_rust"]).cloned().ok_or_else(|| model_error("F8 decomposition"))?;
    if st(at(&decomposition, &["robust_set"])) != if robust.is_empty() { "EMPTY" } else { "NON_EMPTY" } {
        return Err(model_error("F8 decomposition robust_set disagrees with the carried robust set"));
    }
    // F7 frontier: maximum statewise-minimum delivered flow over the Pareto members, overall and per context.
    let pareto = gz_json(repo, F7_PARETO_REL, F7_PARETO_SHA256, F7_PARETO_JSON_SHA256)?;
    let ctxs = pareto.as_dict().ok_or_else(|| model_error("F7 pareto blocks: not a mapping"))?;
    let mut best: BTreeMap<String, (f64, Value)> = BTreeMap::new();
    let mut overall: Option<(f64, Value)> = None;
    let mut n_members = 0usize;
    for (ctx, blocks) in ctxs.iter() {
        let parts: Vec<&str> = ctx.split('|').collect();
        let fw = if parts.len() == 3 { format!("{}|{}", parts[1], parts[2]) } else { ctx.clone() };
        for b in blocks.as_list().ok_or_else(|| model_error("F7 pareto: blocks"))? {
            for mm in at(b, &["block", "members"]).and_then(Value::as_list).unwrap_or(&[]) {
                n_members += 1;
                let Some(v) = num(at(mm, &["mdot_delivered_min_kgps"])) else {
                    return Err(model_error(format!("F7 member without mdot_delivered_min_kgps in {ctx}")));
                };
                let pick = |k: &str| at(mm, &[k]).cloned().unwrap_or(Value::Null);
                let row = super::record::d(vec![
                    ("mdot_delivered_min_kgps", f(v)),
                    ("design_id", pick("design_id")),
                    ("context", Value::str(ctx.clone())),
                    ("context_role", pick("context_role")),
                    ("P_set_Pa", pick("P_set_Pa")),
                    ("xO_flow_min", pick("xO_flow_min")),
                    ("xO_flow_max", pick("xO_flow_max")),
                    ("mdot_captured_min_kgps", pick("mdot_captured_min_kgps")),
                    ("mdot_delivered_design_kgps", pick("mdot_delivered_design_kgps")),
                    ("P_compressor_el_max_W", pick("P_compressor_el_max_W")),
                    ("drag_intake_max_N", pick("drag_intake_max_N")),
                ]);
                if best.get(&fw).is_none_or(|x| v > x.0) {
                    best.insert(fw.clone(), (v, row.clone()));
                }
                if overall.as_ref().is_none_or(|x| v > x.0) {
                    overall = Some((v, row));
                }
            }
        }
    }
    let prereg = json(repo, abep_hall::envelope::PREREG_REL, abep_hall::envelope::PREREG_SHA256)?;
    let floor = at(&prereg, &["case_grid", "mdot_kg_s"])
        .and_then(Value::as_list)
        .and_then(|l| l.iter().filter_map(|x| num(at(x, &["value"]))).reduce(f64::min))
        .ok_or_else(|| model_error("prereg v1 case_grid.mdot_kg_s"))?;
    let ratio = overall.as_ref().map_or(Value::Null, |o| f(o.0 / floor));
    let report = super::record::d(vec![
        (
            "producer",
            Value::str(
                "admitted F7 / F8 chain: intake TPMC -> filter -> compressor -> plenum / feed steady over the registered \
                 upstream design space and the frozen 196 + 1 design states (captured reference outputs, python \
                 commit ba8adc3, reproduced bit for bit by Rust)",
            ),
        ),
        ("labels", super::record::strs(&["PARAMETRIC_SENSITIVITY", LAYER_A])),
        (
            "f7",
            super::record::d(vec![
                ("contract", Value::str(st(at(&f7r, &["contract_id"])))),
                ("verdict", Value::str(st(at(&f7r, &["verdict"])))),
                ("admission", Value::str(st(at(&f7r, &["admission"])))),
                ("report", Value::str(format!("{F7_REPORT_REL} sha256 {F7_REPORT_SHA256}"))),
                ("pareto_blocks", Value::str(format!("{F7_PARETO_REL} sha256 {F7_PARETO_SHA256}"))),
                ("n_pareto_members", Value::int(n_members as i64)),
            ]),
        ),
        (
            "f8",
            super::record::d(vec![
                ("contract", Value::str(st(at(&f8r, &["contract_id"])))),
                ("verdict", Value::str(st(at(&f8r, &["verdict"])))),
                ("admission", Value::str(st(at(&f8r, &["admission"])))),
                ("study", Value::str(format!("{F8_STUDY_REL} sha256 {F8_STUDY_SHA256}"))),
                ("carried_robust_set_members", Value::List(robust.iter().map(|x| Value::str(x.clone())).collect())),
                ("carried_robust_set_label", at(carried, &["label"]).cloned().unwrap_or(Value::Null)),
                ("decomposition", decomposition),
            ]),
        ),
        (
            "plenum_feed",
            super::record::d(vec![
                ("contract", Value::str(st(at(&p8, &["contract", "id"])))),
                ("verdict_v8", Value::str(st(at(&p8, &["parity_verdict"])))),
                ("admission_v8", Value::str(st(at(&p8, &["verdict"])))),
                (
                    "role",
                    Value::str(
                        "governed Python reference authoritative (A9.33 / A9.34, R2): the steady plenum / feed values \
                         used here are the Python capture inside the admitted F7 outputs; no transient is consumed; \
                         no plenum v9",
                    ),
                ),
            ]),
        ),
        (
            "frontier_overall",
            overall.as_ref().map_or(Value::Null, |o| o.1.clone()),
        ),
        (
            "frontier_by_filter_wall",
            Value::Dict(best.into_iter().map(|(k, v)| (k, v.1)).collect::<Dict>()),
        ),
        ("hall_envelope_grid_floor_kg_s", f(floor)),
        ("hall_envelope_grid_floor_source", Value::str("prereg_v1.json case_grid.mdot_kg_s (MF-LO)")),
        ("frontier_over_hall_grid_floor", ratio),
        (
            "role",
            Value::str(
                "raw statewise-minimum delivered flow of the best F7 Pareto member (one hardware across all states); \
                 not a design, not a requirement, never a verdict",
            ),
        ),
    ]);
    Ok(FlowPath {
        robust_members: robust,
        per_state: None,
        compressor_eligible: true,
        provenance: format!(
            "F7 {} / F8 {} (PARITY_PASS / ADMITTED); plenum / feed {} {}",
            st(at(&f7r, &["contract_id"])),
            st(at(&f8r, &["contract_id"])),
            st(at(&p8, &["contract", "id"])),
            st(at(&p8, &["parity_verdict"]))
        ),
        report,
    })
}

fn ledger_item_status(repo: &Path, id: &str) -> AssessResult<String> {
    let b = std::fs::read(repo.join(LEDGER_REL)).map_err(|e| model_error(format!("{LEDGER_REL}: {e}")))?;
    let v = loads(std::str::from_utf8(&b).map_err(|e| model_error(format!("{LEDGER_REL}: {e}")))?)?;
    v.as_dict()
        .and_then(|d| d.get("new_items"))
        .and_then(Value::as_list)
        .and_then(|l| l.iter().find(|x| at(x, &["id"]).and_then(Value::as_str) == Some(id)))
        .and_then(|x| at(x, &["status"]))
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| model_error(format!("{LEDGER_REL}: new item {id} has no status")))
}

/// P-ICP of one mode from an NP-ICP v2 result.
pub fn icp_mode(r: &abep_icp::v2::IcpResultV2) -> AssessResult<IcpMode> {
    let mut codes: Vec<String> = r.reason_codes().into_iter().collect();
    codes.sort();
    let hp = &r.if_icp_hall_v1;
    let env_max = hp.i_e_cap_envelope_a.get("max");
    let (ie, member) = match env_max {
        Some(q) if q.status.is_converged() && q.value.is_some() => {
            let v = q.value.expect("checked");
            let id = hp
                .i_e_cap_by_member_a
                .iter()
                .find(|(_, x)| x.value == Some(v) && x.status.is_converged())
                .map(|(k, _)| k.clone())
                .ok_or_else(|| model_error("NP-ICP v2: I_e,cap envelope max without a member"))?;
            (Some(v), Some(id))
        }
        _ => (None, None),
    };
    let mut loads_v = vec![];
    let mut load_codes = vec![];
    if let Some(mid) = &member {
        let rec = r
            .if_icp_bus_v2
            .iter()
            .find(|b| &b.solve_member_id == mid)
            .ok_or_else(|| model_error(format!("NP-ICP v2: no IF-ICP-BUS-v2 record of member {mid}")))?;
        let j = serde_json::to_value(rec).map_err(|e| model_error(e.to_string()))?;
        let src = format!("NP-ICP-NEUTRALIZER v2 case {} member {mid}", r.case_id);
        for (slot, u) in
            icp_upstream_loads_v2(&j, &[], "model-derived", &src, false).map_err(|e| model_error(e.to_string()))?
        {
            match u {
                Upstream::Evaluated { p_w, source, .. } => loads_v.push((slot, p_w, source)),
                Upstream::Absent { status: abep_types::EvalStatus::ModelError, reason } => {
                    return Err(model_error(format!("IF-ICP-BUS-v2 load MODEL_ERROR: {reason}")))
                }
                Upstream::Absent { reason, .. } => load_codes.push(reason),
            }
        }
    } else {
        load_codes.push("ICP loads TBD: no member with a converged I_e,cap".to_string());
    }
    let feed = super::record::d(
        r.if_icp_feed_v1
            .mdot_icp_dedicated_kg_s
            .iter()
            .map(|(k, q)| {
                (
                    k.as_str(),
                    super::record::d(vec![
                        ("value_kg_s", q.value.map_or(Value::Null, Value::Float)),
                        ("status", Value::str(q.status.as_str())),
                    ]),
                )
            })
            .collect(),
    );
    let summary = super::record::d(vec![
        ("status", Value::str(r.status.as_str())),
        ("verification_status", Value::str(r.verification_status.clone())),
        ("validation_status", Value::str(r.validation_status.clone())),
        ("configuration", Value::str(r.configuration.clone())),
        ("gas_mode", Value::str(r.gas_mode.clone())),
        ("n_solve_members", Value::int(r.solve_members.len() as i64)),
        ("hall_pair_coupled_status", Value::str(hp.coupled_status.as_str())),
        ("cpl_hall_on_status", Value::str(r.cpl_hall_on_v1.status.as_str())),
        ("feed_booking", Value::str(r.if_icp_feed_v1.booking.clone())),
    ]);
    if r.status == abep_icp::IcpStatus::ModelError {
        return Err(model_error(format!("NP-ICP v2 case {}: MODEL_ERROR {codes:?}", r.case_id)));
    }
    Ok(IcpMode {
        case_id: r.case_id.clone(),
        status: r.status.as_str().into(),
        codes,
        i_e_cap_fav_a: ie,
        member_id: member,
        loads: loads_v,
        load_codes,
        feed,
        summary,
    })
}

/// P-ICP: NP-ICP v2 on the registered-today case of each mode.
pub fn icp_path(repo: &Path) -> AssessResult<IcpPath> {
    use abep_icp::case::SupplyMode;
    use abep_icp::chemistry::ChemistryRegistration;
    let model = IcpModelV2::load(repo)?;
    let ledger = ledger_item_status(repo, "NP-ICP-NEUTRALIZER")?;
    let mut modes = BTreeMap::new();
    let mut ver = String::new();
    for (m, sm, gas) in
        [(Mode::AirPrimary, SupplyMode::AirPrimary, "AIR"), (Mode::XeContingency, SupplyMode::XeContingency, "XE")]
    {
        let case = registered_today_case_v2(sm, ChemistryRegistration::NotRegistered { gas: gas.into() });
        let r = model.evaluate(&case);
        ver = r.verification_status.clone();
        modes.insert(m, icp_mode(&r)?);
    }
    Ok(IcpPath {
        modes,
        producer_status: format!("NP-ICP-NEUTRALIZER model_version 2: {ver}; ledger {ledger}; NOT_VALIDATED"),
        provenance: format!(
            "abep_icp::v2 (prereg lock v2 {}), registered-today v2 case per mode",
            abep_icp::v2::PREREG_LOCK_V2_SHA256
        ),
        model: Some(model),
    })
}

/// P-THERMAL: the thermal 2.0.0 governed context; no flight thermal case of H-1 + ICP is registered.
pub fn thermal_path(repo: &Path) -> AssessResult<ThermalPath> {
    let gov = abep_subsystems::thermal::GovernedContextV2::load(repo)?;
    let mut codes = vec![THERMAL_LOADS_NOT_EVALUATED.to_string(), THERMAL_FLIGHT_CASE_NOT_REGISTERED.into()];
    if gov.v1().admitted_hall_members().is_empty() {
        codes.push(abep_mission::statewise_td::CREDIBLE_HALL_TRANSPORT_SET_EMPTY.into());
    }
    if gov.v1().admitted_icp_producers().is_empty() {
        codes.push(abep_mission::integration::today::NP_ICP_NOT_ADMITTED.into());
    }
    if !gov.v1().spacecraft_thermal_icd_registered() {
        codes.push("SPACECRAFT_THERMAL_ICD_ABSENT".into());
    }
    codes.sort();
    Ok(ThermalPath {
        codes,
        per_state: None,
        producer_status: "NP-THERMAL-CATHODELESS 2.0.0: VERIFIED, NOT_VALIDATED, not admitted (ADM-04)".into(),
        provenance: format!(
            "abep_subsystems::thermal::GovernedContextV2 (prereg lock v2 {})",
            "727689fee6bd003295c53abfbc4185c93fab80620329c75062a956dbbb9742de"
        ),
    })
}

/// P-MASS: the mass v5 wet-mass objective and the RFP matrix row.
pub fn mass_path(repo: &Path, ti: &TodayInputs) -> AssessResult<MassPath> {
    let wm = abep_subsystems::mass::wet_mass::wet_mass_pinned(
        repo,
        &Value::str(abep_subsystems::power::slots::FLIGHT_CONFIGURATION),
        &Value::Null,
        &Value::Null,
    )
    .map_err(|e| model_error(format!("{e:?}")))?;
    let status = st(at(&wm, &["status"]));
    if status == "MODEL_ERROR" {
        return Err(model_error("wet-mass objective MODEL_ERROR"));
    }
    let mut codes =
        vec![v1::MASS_INCOMPLETE_EVIDENCE.to_string(), abep_mission::integration::model::XE_LOAD_NOT_FROZEN.into()];
    codes.push(format!("WET_MASS_OBJECTIVE_{status}"));
    codes.sort();
    let row = |field: &str| {
        v1::row_status(&ti.matrix, "RFP-WET-MASS-LT-40KG", field).unwrap_or_else(|_| "MODEL_ERROR".into())
    };
    let info = super::record::d(vec![
        ("producer", Value::str("abep_subsystems::mass::wet_mass (mass v5, ADMITTED)")),
        ("objective_status", Value::str(status)),
        ("objective_reason", at(&wm, &["reason"]).cloned().unwrap_or(Value::Null)),
        ("rfp_matrix_row_assessment", Value::str(row("rfp_assessment_status"))),
        ("rfp_matrix_row_evidence", Value::str(row("evidence_status"))),
        (
            "planning_values",
            Value::str(
                "planning allocations only (v1 NH-MASS today): never eligible for PHYSICALLY_NON_CLOSING (HR-07)",
            ),
        ),
    ]);
    Ok(MassPath { cbe_wet_kg: None, cbe_lower_bound_kg: None, codes, info })
}

/// P-LIFE: the admitted life kernels' statuses.
pub fn life_path(repo: &Path) -> AssessResult<LifePath> {
    let prereg = json(repo, abep_hall::envelope::PREREG_REL, abep_hall::envelope::PREREG_SHA256)?;
    let ids: Vec<String> = at(&prereg, &["case_grid", "transport", "ids"])
        .and_then(Value::as_list)
        .ok_or_else(|| model_error("prereg v1 transport ids"))?
        .iter()
        .filter_map(|x| x.as_str().map(str::to_string))
        .collect();
    let mut wall = Dict::new();
    for id in &ids {
        let s = abep_subsystems::life::hall_wall::hall_wall_life_input_status(repo, id);
        if s == abep_types::EvalStatus::ModelError {
            return Err(model_error(format!("hall wall life input status of {id}: MODEL_ERROR")));
        }
        wall.insert(id.as_str(), Value::str(s.as_str()));
    }
    let material = abep_subsystems::life::p4::final_material_status(&Value::Null);
    let info = super::record::d(vec![
        ("producer", Value::str("abep_subsystems::life (ADMITTED kernels)")),
        ("hall_wall_life_input_status_by_transport", Value::Dict(wall)),
        (
            "layer_a_wall_flux",
            Value::str(
                "envelope runs with ion_wall_losses = false (v1 numerical_settings): wall_life_trustworthy false",
            ),
        ),
        ("p4_final_material_status", Value::str(material)),
        ("k_gas_life", Value::str("NOT_EXTRACTED (SC-WP-08)")),
    ]);
    Ok(LifePath {
        firing_life_h: None,
        codes: vec![
            v1::LIFE_NOT_EVALUATED.into(),
            HALL_WALL_LIFE_INPUTS_NOT_TRUSTWORTHY.into(),
            ANODE_MATERIAL_OPEN.into(),
        ],
        info,
    })
}

/// P-TD: the mission drag_body_N codes of every state (AIR).
pub fn td_path(ti: &TodayInputs) -> AssessResult<TdPath> {
    let mut per = BTreeMap::new();
    for s in &ti.states {
        let (evaluated, codes) = quantity_codes(&ti.mission, &s.state_id, Mode::AirPrimary, "drag_body_N")?;
        per.insert(s.state_id.clone(), if evaluated { vec![] } else { codes });
    }
    Ok(TdPath { per_state_codes: per })
}

/// Every input of harness v2 from the repository.
pub fn gather_m1(
    repo: &Path,
    envelope: Option<Envelope>,
    air: Option<AirHallInput>,
    rust_commit: &str,
) -> AssessResult<M1Inputs> {
    verify_a2(repo)?;
    let a1 = a1_on_line(repo)?;
    if air.is_some() && !a1 {
        return Err(model_error("AIR points supplied but addendum A1 is not on this line"));
    }
    let today = gather(repo, rust_commit)?;
    let a4 = Some(super::conservation::gather_a4(repo, &today)?);
    let (air_admitted, air_chem) = air_chemistry(repo)?;
    let air = match air {
        Some(a) if a1 => AirHall::Ingested(a),
        Some(_) => return Err(model_error("AIR points supplied but addendum A1 is not on this line")),
        None => {
            let mut codes = vec![];
            if !air_admitted {
                codes.push(v1::AIR_HALL_O_O2_CHEMISTRY_NOT_ADMITTED.to_string());
            }
            if !a1 {
                codes.push(AIR_FAMILY_ADDENDUM_A1_NOT_ON_LINE.into());
            }
            if envelope.is_none() {
                codes.push(v1::HALL_ENVELOPE_NOT_RUN.into());
            }
            codes.sort();
            AirHall::NotAvailable(codes)
        }
    };
    let flow = flow_path(repo)?;
    let icp = icp_path(repo)?;
    let mp = MassPowerA9V5::load(repo).map_err(|e| model_error(e.to_string()))?;
    let thermal = thermal_path(repo)?;
    let mass = mass_path(repo, &today)?;
    let life = life_path(repo)?;
    let td = td_path(&today)?;
    let hc06_k = today.thresholds.limit("HC-06");
    let hc07_h = today.thresholds.limit("HC-07");
    let hc08_n = today.thresholds.limit("HC-08");
    Ok(M1Inputs {
        today,
        xe: envelope,
        air,
        a1_on_line: a1,
        air_chemistry: air_chem,
        flow,
        icp,
        mp,
        thermal,
        mass,
        life,
        td,
        hc06_k,
        hc07_h,
        hc08_n,
        a4,
    })
}

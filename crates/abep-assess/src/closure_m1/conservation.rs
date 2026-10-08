//! NP-HALL-PARAMETRIC-ENVELOPE addendum A4 in harness v2: the conservation bounds B-FLOW, B-THRUST and B-DRAG
//! (`docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a4_conservation_bounds.json`).
//!
//! The kernels are raw physics in `abep_mission::conservation_bounds`; this module gathers their registered inputs,
//! applies HC-01..HC-03 and the registered effective-collection-area limit, runs the admitted statewise quantifier and
//! states the classification effect (step CA4). A bound that holds establishes nothing; a bound that is not evaluated
//! adds no blocker; only an eligible failure (FROZEN area limit, every input EVALUATED) changes the classification.

use super::record::d;
use super::*;
use crate::closure::NON_CLOSING;
use crate::error::{model_error, AssessResult};
use abep_mission::conservation_bounds::{self as cb, FluxBound, SpeedBound, SpeedInputs};
use abep_provenance::read_verified;
use abep_types::EvalStatus;
use std::path::Path;

pub const A4_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a4_conservation_bounds.json";
pub const A4_SHA256: &str = "7cd43c80188450b4563c5807b46b5866a39c19fe9b383dd3444cfe583b7668e1";
pub const A4_MD_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/PREREG_ADDENDUM_A4_CONSERVATION_BOUNDS.md";
pub const A4_MD_SHA256: &str = "15b853e551a4c5b9b7d0feb0adc606aa55168ac24c03e9e21f04b183ecd0d4e5";
pub const A4_LOCK_REL: &str =
    "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/prereg_addendum_a4_lock.json";
pub const A4_LOCK_SHA256: &str = "5a03333e9a18f9bd85fe7bf0359b81d541bf45a4c7c91f0b4e12076f5cb92dcc";

pub const RECORD_SCHEMA: &str = "abep_assess_conservation_bounds_v1";
/// The only location A4 reads the effective-collection-area limit from (engineering constraint, m^2).
pub const AREA_CONSTRAINT: &str = "intake_effective_collection_area_max_m2";
pub const A4_CONSTRAINT_ID: &str = "A4-B-FLOW-THRUST";
/// F1-P-16 frontal-area design grid (information I-2 only; never a limit).
pub const F1_GRID_AREAS_M2: [f64; 6] = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5];

pub const A4_CONSERVATION_BOUND_NON_CLOSING: &str = "A4_CONSERVATION_BOUND_NON_CLOSING";
pub const A4_BOUND_HOLDS_NOTHING_ESTABLISHED: &str = "A4_BOUND_HOLDS_NOTHING_ESTABLISHED";
pub const A4_AREA_LIMIT_NOT_REGISTERED: &str = "A4_AREA_LIMIT_NOT_REGISTERED";
pub const A4_AREA_LIMIT_NOT_FROZEN: &str = "A4_AREA_LIMIT_NOT_FROZEN";
pub const A4_WIND_NOT_AVAILABLE: &str = "A4_WIND_NOT_AVAILABLE";
pub const A4_INPUT_OUT_OF_DOMAIN: &str = "A4_INPUT_OUT_OF_DOMAIN";
pub const A4_P_AVAIL_NOT_POSITIVE: &str = "A4_P_AVAIL_NOT_POSITIVE";
pub const A4_NO_XE_NON_CLOSURE_ROUTE: &str = "A4_NO_XE_NON_CLOSURE_ROUTE";
pub const B_DRAG_NOT_APPLICABLE_TO_GROSS_THRUST_REQUIREMENT: &str = "B_DRAG_NOT_APPLICABLE_TO_GROSS_THRUST_REQUIREMENT";

/// Verdict statuses of an A4 bound.
pub const BOUND_NOT_EVALUATED: &str = "NOT_EVALUATED";
pub const BOUND_HOLDS: &str = "BOUND_HOLDS_NOTHING_ESTABLISHED";
pub const BOUND_FAILS: &str = "BOUND_FAILS";

/// The registered environment of one design state (IN-ENV).
#[derive(Debug, Clone, PartialEq)]
pub struct StateEnv {
    pub state_id: String,
    pub required: bool,
    pub scenario: String,
    pub status: EvalStatus,
    pub codes: Vec<String>,
    pub lat_deg: f64,
    pub alt_km: f64,
    pub rho_kg_m3: f64,
    pub n_o_m3: f64,
    pub n_n2_m3: f64,
    pub n_o2_m3: f64,
    pub t_k: f64,
    pub v_adm_m_s: f64,
    /// |horizontal wind| + interpolation error bound, m/s (None: not available).
    pub wind_m_s: Option<f64>,
}

/// IN-AREA-LIMIT.
#[derive(Debug, Clone, PartialEq)]
pub enum AreaLimit {
    NotRegistered,
    Registered { value_m2: f64, status: String, provenance: String },
}

/// Everything A4 reads besides the harness state evaluations (A4 sec. inputs).
#[derive(Debug, Clone, PartialEq)]
pub struct A4Inputs {
    /// In harness state order.
    pub states: Vec<StateEnv>,
    pub alt_band_km: (f64, f64),
    pub area: AreaLimit,
    /// HC-09 intake-face drag limit (information I-4), N.
    pub hc09_n: Option<f64>,
    pub wind_dataset: String,
    /// (path, sha256) of the A4 files and the configuration read.
    pub provenance: Vec<(String, String)>,
}

/// Per-(state, mode) quantities (raw kernels at the assessment's P_avail).
#[derive(Debug, Clone, PartialEq)]
pub struct ModeBound {
    pub p_avail_w: Option<f64>,
    pub codes: Vec<String>,
    /// mdot_req for HC-01, HC-02 (electric power only), kg/s.
    pub mdot_req: Option<[f64; 2]>,
    /// AIR: A_req and A_req,0 for HC-01, HC-02, m^2.
    pub a_req: Option<[f64; 2]>,
    pub a_req0: Option<[f64; 2]>,
    /// AIR: T_max at the registered area, N.
    pub t_max_at_area: Option<f64>,
    /// AIR: T_max at the F1 design-grid areas (I-2), N.
    pub t_max_grid: Vec<f64>,
    /// AIR, I-5: largest mdot with T_max >= mdot U_min, and max (T_max - D_cap).
    pub mdot_td_max: Option<f64>,
    pub max_t_minus_dcap: Option<f64>,
    /// AIR, I-4: HC-09 / U_min, kg/s.
    pub mdot_cap_hc09: Option<f64>,
}

/// One state's environment bound and its per-mode quantities.
#[derive(Debug, Clone, PartialEq)]
pub struct StateBound {
    pub state_id: String,
    pub required: bool,
    pub status: EvalStatus,
    pub codes: Vec<String>,
    pub speed: Option<SpeedBound>,
    pub flux: Option<FluxBound>,
    pub phi_adm: Option<f64>,
    pub modes: BTreeMap<Mode, ModeBound>,
}

/// A statewise verdict of one bound and requirement (A4 sec. statewise).
#[derive(Debug, Clone, PartialEq)]
pub struct Verdict {
    pub id: &'static str,
    pub mode: Mode,
    pub status: &'static str,
    pub eligible: bool,
    pub codes: Vec<String>,
    pub failing_states: Vec<String>,
    pub quantifier: Value,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct A4Outcome {
    pub states: Vec<StateBound>,
    pub verdicts: Vec<Verdict>,
    /// Required AIR states carrying an eligible A4 non-closure.
    pub eligible_air_states: BTreeSet<String>,
}

fn sorted(mut v: Vec<String>) -> Vec<String> {
    v.sort();
    v.dedup();
    v
}

// ------------------------------------------------------------------------------------------------ gather

/// A4 identity: json, md and lock verify and the lock names both files.
pub fn verify_a4(repo: &Path) -> AssessResult<()> {
    for (rel, sha) in [(A4_REL, A4_SHA256), (A4_MD_REL, A4_MD_SHA256), (A4_LOCK_REL, A4_LOCK_SHA256)] {
        read_verified(&repo.join(rel), sha)?;
    }
    let lock = abep_types::pyjson::loads(
        std::str::from_utf8(&read_verified(&repo.join(A4_LOCK_REL), A4_LOCK_SHA256)?)
            .map_err(|e| model_error(format!("{A4_LOCK_REL}: {e}")))?,
    )?;
    let files = lock.as_dict().and_then(|d| d.get("files")).and_then(Value::as_dict);
    for (k, want) in [
        ("prereg_addendum_a4_conservation_bounds.json", A4_SHA256),
        ("PREREG_ADDENDUM_A4_CONSERVATION_BOUNDS.md", A4_MD_SHA256),
    ] {
        if files.and_then(|f| f.get(k)).and_then(Value::as_str) != Some(want) {
            return Err(model_error(format!("{A4_LOCK_REL}: files.{k} != {want}")));
        }
    }
    Ok(())
}

fn num(v: Option<&Value>) -> Option<f64> {
    v.and_then(|x| x.to_f64().ok()).filter(|x| x.is_finite())
}

/// IN-ALT-BAND, IN-AREA-LIMIT and HC-09 from the engineering constraints (abep-config, manifest-verified).
pub fn constraints(repo: &Path) -> AssessResult<((f64, f64), AreaLimit, Option<f64>)> {
    let paths = abep_config::ConfigPaths::repository(repo);
    let ec = abep_config::loaders::load_engineering_constraints_file(&paths)?;
    let c = ec
        .as_dict()
        .and_then(|d| d.get("constraints"))
        .and_then(Value::as_dict)
        .ok_or_else(|| model_error("engineering constraints: no constraints"))?;
    let band = c
        .get("altitude_band_km")
        .and_then(|x| x.as_dict())
        .and_then(|x| x.get("value"))
        .and_then(Value::as_list)
        .filter(|l| l.len() == 2)
        .and_then(|l| Some((num(l.first())?, num(l.get(1))?)))
        .ok_or_else(|| model_error("engineering constraints: altitude_band_km.value"))?;
    let hc09 = c
        .get("intake_drag_generation_limit_mN")
        .and_then(|x| x.as_dict())
        .and_then(|x| num(x.get("value")))
        .map(|mn| mn * 1e-3);
    let area = match c.get(AREA_CONSTRAINT).and_then(|x| x.as_dict()) {
        None => AreaLimit::NotRegistered,
        Some(e) => {
            let v = num(e.get("value")).filter(|v| *v > 0.0).ok_or_else(|| {
                model_error(format!("engineering constraint {AREA_CONSTRAINT}: value must be a finite area > 0"))
            })?;
            if e.get("units").and_then(Value::as_str) != Some("m^2") {
                return Err(model_error(format!("engineering constraint {AREA_CONSTRAINT}: units must be m^2")));
            }
            AreaLimit::Registered {
                value_m2: v,
                status: e.get("status").and_then(Value::as_str).unwrap_or("MISSING").to_string(),
                provenance: format!("config/constraints/engineering_constraints_v1.json constraints.{AREA_CONSTRAINT}"),
            }
        }
    };
    Ok((band, area, hc09))
}

/// The A4 inputs of the repository, aligned with (and cross-checked against) the harness state list.
pub fn gather_a4(repo: &Path, ti: &crate::closure::TodayInputs) -> AssessResult<A4Inputs> {
    verify_a4(repo)?;
    let (alt_band_km, area, hc09_n) = constraints(repo)?;
    let env = abep_atmos::execution::Environment::load(repo)?;
    let ds = abep_atmos::design_state_set::required_states(&env.set)?;
    let recs = abep_atmos::execution::execute_states(&env, &ds);
    if recs.len() != ti.states.len() {
        return Err(model_error(format!(
            "A4: {} environment states vs {} harness states",
            recs.len(),
            ti.states.len()
        )));
    }
    let mut states = Vec::with_capacity(recs.len());
    for ((st, rec), d) in ti.states.iter().zip(&recs).zip(&ds) {
        if st.state_id != rec.state_id || d.state_id != rec.state_id {
            return Err(model_error(format!("A4: state order differs at {} / {}", st.state_id, rec.state_id)));
        }
        let mut e = StateEnv {
            state_id: rec.state_id.clone(),
            required: st.required,
            scenario: d.scenario.clone(),
            status: rec.status,
            codes: vec![],
            lat_deg: d.lat_deg,
            alt_km: d.alt_km,
            rho_kg_m3: d.rho_kg_m3,
            n_o_m3: d.n_o_m3,
            n_n2_m3: d.n_n2_m3,
            n_o2_m3: d.n_o2_m3,
            t_k: d.t_k,
            v_adm_m_s: f64::NAN,
            wind_m_s: None,
        };
        match (&rec.environment, rec.status) {
            (Some(a), EvalStatus::Evaluated) => {
                e.v_adm_m_s = a.V;
                for (k, x) in [("rho_kg_m3", a.rho), ("v_orbital_m_s", a.V)] {
                    let q = ti.mission.field(&e.state_id, Mode::AirPrimary, k).and_then(|f| f.quantity());
                    if q.and_then(|q| q.value).map(f64::to_bits) != Some(x.to_bits()) {
                        return Err(model_error(format!(
                            "A4: {k} of {} differs from the mission run hook",
                            e.state_id
                        )));
                    }
                }
                match &rec.wind {
                    Some(w) => match w.wind.wind_interp_max_abs_err_m_s {
                        Some(err) => e.wind_m_s = Some(w.wind.u_mer_m_s.hypot(w.wind.u_zon_m_s) + err),
                        None => e.codes.push(A4_WIND_NOT_AVAILABLE.into()),
                    },
                    None => e.codes.push(A4_WIND_NOT_AVAILABLE.into()),
                }
            }
            _ => e.codes.push(ENVIRONMENT_NOT_EVALUATED.into()),
        }
        states.push(e);
    }
    let mut provenance = vec![
        (A4_REL.to_string(), A4_SHA256.to_string()),
        (A4_MD_REL.to_string(), A4_MD_SHA256.to_string()),
        (A4_LOCK_REL.to_string(), A4_LOCK_SHA256.to_string()),
    ];
    provenance.push(("design-state set v2".into(), env.set.sha256.clone()));
    provenance.push(("orbit dataset".into(), env.orbit.data.meta.sha256.clone()));
    provenance.push(("HWM14 v2 wind dataset".into(), env.wind.data.sha256.clone()));
    Ok(A4Inputs {
        states,
        alt_band_km,
        area,
        hc09_n,
        wind_dataset: format!("{} ({})", abep_data::hwm14_v2::DATASET_ID, abep_data::hwm14_v2::DATASET_STATUS),
        provenance,
    })
}

// ------------------------------------------------------------------------------------------------ evaluate

fn env_bound(e: &StateEnv, band: (f64, f64)) -> Result<(SpeedBound, FluxBound), String> {
    if e.status != EvalStatus::Evaluated {
        return Err(ENVIRONMENT_NOT_EVALUATED.into());
    }
    let wind = e.wind_m_s.ok_or_else(|| A4_WIND_NOT_AVAILABLE.to_string())?;
    let oob = |x: abep_types::AbepError| format!("{A4_INPUT_OUT_OF_DOMAIN}: {x}");
    let sp = cb::speed_bound(&SpeedInputs {
        lat_deg: e.lat_deg,
        alt_m: e.alt_km * 1e3,
        alt_min_m: band.0 * 1e3,
        alt_max_m: band.1 * 1e3,
        v_admitted_m_s: e.v_adm_m_s,
        wind_m_s: wind,
    })
    .map_err(oob)?;
    let k = cb::carriers(e.rho_kg_m3, e.n_o_m3, e.n_n2_m3, e.n_o2_m3).map_err(oob)?;
    let fl = cb::flux_bound(&k, e.t_k, sp.u_max_m_s).map_err(oob)?;
    Ok((sp, fl))
}

fn mode_bound(
    m: Mode,
    p_avail: f64,
    t_req: [f64; 2],
    env: Option<&(SpeedBound, FluxBound)>,
    area: &AreaLimit,
    hc09_n: Option<f64>,
) -> Result<ModeBound, String> {
    let oob = |x: abep_types::AbepError| format!("{A4_INPUT_OUT_OF_DOMAIN}: {x}");
    let mut mb = ModeBound {
        p_avail_w: Some(p_avail),
        codes: vec![],
        mdot_req: None,
        a_req: None,
        a_req0: None,
        t_max_at_area: None,
        t_max_grid: vec![],
        mdot_td_max: None,
        max_t_minus_dcap: None,
        mdot_cap_hc09: None,
    };
    if p_avail.is_nan() || p_avail <= 0.0 {
        mb.codes.push(A4_P_AVAIL_NOT_POSITIVE.into());
        return Ok(mb);
    }
    let mr = [cb::mdot_required(t_req[0], p_avail).map_err(oob)?, cb::mdot_required(t_req[1], p_avail).map_err(oob)?];
    mb.mdot_req = Some(mr);
    if m == Mode::XeContingency {
        mb.codes = vec![XE_FEED_FLOW_NOT_REGISTERED.into(), A4_NO_XE_NON_CLOSURE_ROUTE.into()];
        return Ok(mb);
    }
    let Some((sp, fl)) = env else { return Ok(mb) };
    let (phi, q) = (fl.phi_max_kg_m2_s, fl.q_max_w_m2);
    mb.a_req = Some([
        cb::area_required(t_req[0], p_avail, phi, q).map_err(oob)?,
        cb::area_required(t_req[1], p_avail, phi, q).map_err(oob)?,
    ]);
    mb.a_req0 = Some([mr[0] / phi, mr[1] / phi]);
    match area {
        AreaLimit::Registered { value_m2, .. } => {
            mb.t_max_at_area = Some(cb::t_max_at_area(*value_m2, p_avail, phi, q).map_err(oob)?)
        }
        AreaLimit::NotRegistered => mb.codes.push(A4_AREA_LIMIT_NOT_REGISTERED.into()),
    }
    for a in F1_GRID_AREAS_M2 {
        mb.t_max_grid.push(cb::t_max_at_area(a, p_avail, phi, q).map_err(oob)?);
    }
    if sp.u_min_m_s > 0.0 {
        mb.mdot_td_max = Some(cb::mdot_td_max(p_avail, sp.u_min_m_s).map_err(oob)?);
        mb.max_t_minus_dcap = Some(cb::max_t_minus_dcap(p_avail, sp.u_min_m_s).map_err(oob)?);
        mb.mdot_cap_hc09 = hc09_n.map(|d| d / sp.u_min_m_s);
    }
    Ok(mb)
}

/// Every A4 quantity and verdict over the harness state evaluations (pure).
pub fn evaluate_a4(
    a4: &A4Inputs,
    lim: &HallLimits,
    states: &[(StateRef, BTreeMap<Mode, StateModeEval>)],
) -> AssessResult<A4Outcome> {
    if a4.states.len() != states.len() || a4.states.iter().zip(states).any(|(a, (s, _))| a.state_id != s.state_id) {
        return Err(model_error("A4: environment states and harness states differ"));
    }
    let t_req = [lim.thrust_min_n, lim.thrust_capability_n];
    let mut out = Vec::with_capacity(states.len());
    for (e, (st, ms)) in a4.states.iter().zip(states) {
        let env = env_bound(e, a4.alt_band_km);
        let mut sb = StateBound {
            state_id: e.state_id.clone(),
            required: st.required,
            status: if env.is_ok() { EvalStatus::Evaluated } else { EvalStatus::NotEvaluated },
            codes: e.codes.clone(),
            speed: env.as_ref().ok().map(|x| x.0),
            flux: env.as_ref().ok().map(|x| x.1.clone()),
            phi_adm: (e.status == EvalStatus::Evaluated).then_some(e.rho_kg_m3 * e.v_adm_m_s),
            modes: BTreeMap::new(),
        };
        if let Err(c) = &env {
            sb.codes.push(c.clone());
            if c.starts_with(A4_INPUT_OUT_OF_DOMAIN) {
                sb.status = EvalStatus::OutOfDomain;
            }
        }
        sb.codes = sorted(sb.codes);
        for m in REQUIRED_MODES {
            let bus = ms.get(&m).ok_or_else(|| model_error(format!("A4: no {} evaluation", m.as_str())))?;
            let p_avail = lim.p_bus_max_w - bus.bus.lb_eligible_w;
            let mb = match mode_bound(m, p_avail, t_req, env.as_ref().ok(), &a4.area, a4.hc09_n) {
                Ok(mut mb) => {
                    if m == Mode::AirPrimary {
                        if let Err(c) = &env {
                            mb.codes.push(c.clone());
                        }
                    }
                    mb.codes = sorted(mb.codes);
                    mb
                }
                Err(c) => ModeBound {
                    p_avail_w: Some(p_avail),
                    codes: vec![c],
                    mdot_req: None,
                    a_req: None,
                    a_req0: None,
                    t_max_at_area: None,
                    t_max_grid: vec![],
                    mdot_td_max: None,
                    max_t_minus_dcap: None,
                    mdot_cap_hc09: None,
                },
            };
            sb.modes.insert(m, mb);
        }
        out.push(sb);
    }
    let mut verdicts = vec![];
    let mut eligible = BTreeSet::new();
    for (k, id) in [(0usize, "A4-T12-SUSTAINED"), (1usize, "A4-T25-CAPABILITY")] {
        let v = air_verdict(a4, &out, k, id)?;
        if v.eligible {
            eligible.extend(v.failing_states.iter().cloned());
        }
        verdicts.push(v);
    }
    verdicts.push(Verdict {
        id: "A4-XE-B-THRUST",
        mode: Mode::XeContingency,
        status: BOUND_NOT_EVALUATED,
        eligible: false,
        codes: vec![A4_NO_XE_NON_CLOSURE_ROUTE.into(), XE_FEED_FLOW_NOT_REGISTERED.into()],
        failing_states: vec![],
        quantifier: Value::Null,
        detail: "B-FLOW does not apply (stored Xe); no Xe flow or storage limit is registered, so T_max is \
                 NOT_EVALUATED; XE_FUNC (T > 0) cannot fail a conservation bound"
            .into(),
    });
    verdicts.push(Verdict {
        id: "A4-B-DRAG",
        mode: Mode::AirPrimary,
        status: BOUND_NOT_EVALUATED,
        eligible: false,
        codes: vec![B_DRAG_NOT_APPLICABLE_TO_GROSS_THRUST_REQUIREMENT.into(), "HOST_SPACECRAFT_DRAG_ICD_ABSENT".into()],
        failing_states: vec![],
        quantifier: Value::Null,
        detail: "HC-01 / HC-02 are gross thrust (RVM-02 / RVM-03); B-DRAG applies to HC-08 only, which needs the host \
                 drag ICD; BULK_MOMENTUM_BOUND_INFORMATION, never eligible (A4 bounds.B-DRAG)"
            .into(),
    });
    Ok(A4Outcome { states: out, verdicts, eligible_air_states: eligible })
}

/// The AIR B-FLOW / B-THRUST verdict for HC-01 (k = 0, every required state) or HC-02 (k = 1, existence).
fn air_verdict(a4: &A4Inputs, states: &[StateBound], k: usize, id: &'static str) -> AssessResult<Verdict> {
    let mut v = Verdict {
        id,
        mode: Mode::AirPrimary,
        status: BOUND_NOT_EVALUATED,
        eligible: false,
        codes: vec![],
        failing_states: vec![],
        quantifier: Value::Null,
        detail: String::new(),
    };
    let (a_max, frozen) = match &a4.area {
        AreaLimit::NotRegistered => {
            v.codes.push(A4_AREA_LIMIT_NOT_REGISTERED.into());
            v.detail = format!("no registered effective-collection-area limit ({AREA_CONSTRAINT}); A_req(s) reported");
            return Ok(v);
        }
        AreaLimit::Registered { value_m2, status, .. } => (*value_m2, status == "FROZEN"),
    };
    if !frozen {
        v.codes.push(A4_AREA_LIMIT_NOT_FROZEN.into());
    }
    let req: Vec<&StateBound> = states.iter().filter(|s| s.required).collect();
    let evaluated: Vec<(&StateBound, f64)> =
        req.iter().filter_map(|s| s.modes[&Mode::AirPrimary].a_req.map(|a| (*s, a[k]))).collect();
    let n_open = req.len() - evaluated.len();
    if evaluated.is_empty() {
        v.codes.extend(req.iter().flat_map(|s| s.modes[&Mode::AirPrimary].codes.iter().cloned()));
        v.codes = sorted(v.codes);
        v.detail = "no required state has an evaluated A_req".into();
        return Ok(v);
    }
    let rows: Vec<Value> =
        evaluated.iter().map(|(s, _)| d(vec![("state_id", Value::str(s.state_id.clone()))])).collect();
    let areq: BTreeMap<&str, f64> = evaluated.iter().map(|(s, a)| (s.state_id.as_str(), *a)).collect();
    let mut margin = |st: &Value| -> abep_mission::statewise::MarginOutcome {
        let sid = st.as_dict().and_then(|x| x.get("state_id")).and_then(Value::as_str).unwrap_or_default();
        areq.get(sid).map(|a| Value::Float(a_max - a)).ok_or_else(|| format!("KeyError: {sid}"))
    };
    let q = abep_mission::statewise::statewise_quantifier(&rows, &mut margin, &Value::str(id))?;
    let failing: Vec<String> =
        evaluated.iter().filter(|(_, a)| a_max - a < 0.0).map(|(s, _)| s.state_id.clone()).collect();
    v.quantifier = q;
    if k == 0 {
        if failing.is_empty() && n_open == 0 {
            v.status = BOUND_HOLDS;
            v.codes.push(A4_BOUND_HOLDS_NOTHING_ESTABLISHED.into());
        } else if failing.is_empty() {
            v.codes.extend(req.iter().flat_map(|s| s.modes[&Mode::AirPrimary].codes.iter().cloned()));
        } else {
            v.status = BOUND_FAILS;
            v.failing_states = failing;
            v.eligible = frozen;
        }
        v.detail = format!("{n_open} required states not evaluated; sustained: every required state");
    } else {
        let all_fail = failing.len() == evaluated.len();
        if !all_fail {
            v.status = BOUND_HOLDS;
            v.codes.push(A4_BOUND_HOLDS_NOTHING_ESTABLISHED.into());
        } else if n_open > 0 {
            v.status = BOUND_NOT_EVALUATED;
            v.detail = format!("{n_open} required states not evaluated: existence cannot be excluded");
        } else {
            v.status = BOUND_FAILS;
            v.failing_states = req.iter().map(|s| s.state_id.clone()).collect();
            v.eligible = frozen;
        }
        if v.detail.is_empty() {
            v.detail = "capability: existence over the required states (A4 statewise.T25)".into();
        }
    }
    if v.status == BOUND_FAILS {
        v.codes.push(A4_CONSERVATION_BOUND_NON_CLOSING.into());
    }
    v.codes = sorted(v.codes);
    Ok(v)
}

/// The constraint an eligible A4 non-closure adds to a required AIR cell (A4 classification_effect.procedure).
pub fn a4_constraint(verdicts: &[&str]) -> Constraint {
    Constraint {
        id: A4_CONSTRAINT_ID.into(),
        hall_specific: false,
        status: NON_CLOSING,
        eligible_close: false,
        eligible_non_close: true,
        codes: vec![A4_CONSERVATION_BOUND_NON_CLOSING.into()],
        detail: format!(
            "{} fails at the FROZEN effective-collection-area limit: T_max(s) < T_req for any design and any \
             chemistry (A4 supersession of the A1 / A2 never-eligible clauses for this bound only)",
            verdicts.join(", ")
        ),
        evidence_conditions: vec![],
    }
}

/// Number of required AIR cells carrying an eligible A4 non-closure (step CA4).
pub fn ca4_cells(states: &[(StateRef, BTreeMap<Mode, StateModeEval>)]) -> usize {
    states
        .iter()
        .filter(|(s, _)| s.required)
        .filter_map(|(_, ms)| ms.get(&Mode::AirPrimary))
        .filter(|e| e.eval.constraints.iter().any(|c| c.id == A4_CONSTRAINT_ID && c.eligible_non_close))
        .count()
}

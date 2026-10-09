//! DCR-DBF1-001 (DCR-001) preregistered evaluation of the intake / compressor / plenum / feed implementation
//! (`docs/baseline/DCR-001/dcr001_eval_prereg_v1.json`, lock `dcr001_eval_prereg_lock_v1.json`; owner decision A9.38
//! priority 1).
//!
//! The design space DS-DCR001 is searched on the admitted chain: F1 IF-A1 unit-area records scaled by the aperture
//! (F1-02), the abep-gaspath steady sweep with its fail-closed reason bits, and the Rust contract-v8 stability screen.
//! Every criterion is evaluated over all 196 required states x all 10 admitted surface scenarios. Stages S0..S5 apply
//! necessary conditions exactly (no admissible design is lost). [`search`] produces the search record and the input of
//! the governed Python stability reference; [`record`] verifies that reference against the Rust classes (R2) and
//! writes the evaluation record. Thresholds come from abep-config (HC-01 / HC-02 / HC-09) and the pinned mass / power
//! budget; no requirement number is a literal here.

use crate::error::{model_error, AssessResult};
use crate::thresholds::Thresholds;
use abep_design::f1view::load_f1_records;
use abep_design::inputs::{load_upstream_inputs, read_pinned, UpstreamInputs, F3D_REL, MP_REL};
use abep_gaspath::compressor::DragCompressor;
use abep_gaspath::plenum_feed::{
    f1_candidate_id, intake_side, reason_bit, steady_operating_point, steady_sweep, Chain, CompressorPlant, FilterCase,
    IntakeState, Plenum, Sp3, R_CHARACTERISTIC, R_DEADHEAD, T_CHAIN_K,
};
use abep_gaspath::pyops::py_format_g;
use abep_gaspath::stability::{stability_class_events, Controller, WINDOW_S};
use abep_provenance::read_verified;
use serde_json::{json, Map, Value};
use std::collections::HashMap;
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;

pub const PREREG_REL: &str = "docs/baseline/DCR-001/dcr001_eval_prereg_v1.json";
pub const PREREG_SHA256: &str = "98f9931cbf537c3acca9753fafc9c9a9f93b22e7beb27dbae950f0c2c9e556f5";
pub const PREREG_MD_REL: &str = "docs/baseline/DCR-001/DCR001_EVAL_PREREG.md";
pub const PREREG_MD_SHA256: &str = "52132eeaf55335b728d2a5c306bbd7d4b7d1f0fc11cdf89d4d4117a81e1870cb";
pub const LOCK_REL: &str = "docs/baseline/DCR-001/dcr001_eval_prereg_lock_v1.json";
pub const LOCK_SHA256: &str = "39e76c68ee48f3d2c15b492f865be6929f8300f8b94afa680476e8bc80c1998d";
pub const A4_REL: &str = "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/conservation_bounds_v1.json";
pub const A4_SHA256: &str = "5146fe583343bf5de090a8baeecb812640754b7e579f0df69c78e54dd642689f";
pub const M2_REL: &str = "docs/milestones/M2_196_state_rfp_closure/m2_closure_record_v1.json";
pub const M2_SHA256: &str = "600cf229ecdb5f91f0471f03cfdd6d287486ad21e9d9ebadde3cdafa54a37394";
pub const M2_PY_REL: &str = "docs/milestones/M2_196_state_rfp_closure/dbf1_feed_stability_python_reference_v1.json";
pub const M2_PY_SHA256: &str = "fb1cc1d9dba4078f86ba018d7a45f5a97f6975ec4c9529d25035b6cd178aaaf0";

pub const SEARCH_SCHEMA: &str = "abep_dcr001_search_v1";
pub const SPEC_SCHEMA: &str = "abep_dcr001_stability_spec_v1";
pub const PY_SCHEMA: &str = "abep_dcr001_feed_stability_python_reference_v1";
pub const RECORD_SCHEMA: &str = "abep_dcr001_eval_record_v1";
pub const LABEL: &str = "ACTUAL_DESIGN_EVALUATION / PARAMETRIC / NOT_VALIDATED / NOT_A_PERFORMANCE_PREDICTION";

/// DS-DCR001 axes (preregistration design_space).
pub const TARGETS_PA: [f64; 6] = [0.002, 0.005, 0.01, 0.02, 0.05, 0.1];
pub const VOLUMES_M3: [f64; 3] = [1e-3, 1e-2, 1e-1];
pub const WALL: &str = "WALL-G0";
pub const FILTERS: [&str; 4] = ["F4-FIL-T0.9", "F4-FIL-T0.7", "F4-FIL-T0.5", "F4-FIL-PLACEHOLDER"];
pub const GEOMS: [(f64, f64); 8] =
    [(3.0, 0.8), (3.0, 0.9), (5.0, 0.8), (5.0, 0.9), (10.0, 0.8), (10.0, 0.9), (20.0, 0.8), (20.0, 0.9)];
/// K9 / SR-CTRL-01 order: lowest gain first, then the slowest integral time.
pub const CTRL_ORDER: [(f64, f64); 4] = [(0.3, 3.0), (0.3, 0.3), (3.0, 3.0), (3.0, 0.3)];
pub const F_VALVE_HZ: f64 = 1.0;
pub const AUTHORITY: f64 = 3.0;
pub const STABILITY_CAP: usize = 200;
/// F3 inlet-independent gate codes (rotor allowable, rotor stress, tip speed).
pub const F3_INLET_INDEPENDENT: [&str; 3] = ["R1", "R2", "R3"];

/// The 45 apertures: 0.20..0.60 m^2 in 0.01 steps, then the F1 grid ends.
pub fn areas() -> Vec<f64> {
    let mut v: Vec<f64> = (20..=60).map(|i| i as f64 / 100.0).collect();
    v.extend([0.75, 1.0, 1.25, 1.5]);
    v
}

// ------------------------------------------------------------------------------------------------ coefficients

/// The fixed DragCompressor coefficients the preregistration freezes as engineering assumptions.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Coeffs {
    pub turbo_k_s: f64,
    pub turbo_k_k: f64,
    pub leak_conductance_m3_s: f64,
    pub xi: f64,
    pub turbo_blade_area_frac: f64,
    pub turbo_disc_thickness_m: f64,
    pub rotor_disc_thickness_m: f64,
    pub stator_mass_factor: f64,
    pub motor_kg_per_nm: f64,
    pub bearing_kg: f64,
    pub k_bear_w_per_rads: f64,
    pub eta_motor: f64,
    pub p_ctrl_w: f64,
    pub conductance_to_sink_w_k: f64,
    pub t_sink_k: f64,
}

/// Nominal = the code defaults (frozen as FROZEN_ENGINEERING_ASSUMPTION, assumed / level 7).
pub const NOMINAL: Coeffs = Coeffs {
    turbo_k_s: 0.20,
    turbo_k_k: 1.2,
    leak_conductance_m3_s: 2e-4,
    xi: 0.6,
    turbo_blade_area_frac: 0.35,
    turbo_disc_thickness_m: 0.002,
    rotor_disc_thickness_m: 0.004,
    stator_mass_factor: 1.2,
    motor_kg_per_nm: 4.0,
    bearing_kg: 0.6,
    k_bear_w_per_rads: 3e-4,
    eta_motor: 0.8,
    p_ctrl_w: 8.0,
    conductance_to_sink_w_k: 0.4,
    t_sink_k: 293.0,
};

/// Band ends of the flow-path coefficients (kS, kK, leak), taken at all 2^3 combinations.
pub const KS_BAND: [f64; 2] = [0.10, 0.30];
pub const KK_BAND: [f64; 2] = [0.6, 1.8];
pub const LEAK_BAND: [f64; 2] = [1e-4, 3e-4];

/// The monotone coefficients at their unfavourable band end (every corner).
pub const UNFAVOURABLE_MONOTONE: Coeffs = Coeffs {
    turbo_k_s: f64::NAN,
    turbo_k_k: f64::NAN,
    leak_conductance_m3_s: f64::NAN,
    xi: 0.3,
    turbo_blade_area_frac: 0.525,
    turbo_disc_thickness_m: 0.003,
    rotor_disc_thickness_m: 0.006,
    stator_mass_factor: 1.8,
    motor_kg_per_nm: 6.0,
    bearing_kg: 0.9,
    k_bear_w_per_rads: 4.5e-4,
    eta_motor: 0.5,
    p_ctrl_w: 12.0,
    conductance_to_sink_w_k: 0.2,
    t_sink_k: 333.0,
};

impl Coeffs {
    pub fn apply(&self, c: &mut DragCompressor) {
        c.turbo_k_s = self.turbo_k_s;
        c.turbo_k_k = self.turbo_k_k;
        c.leak_conductance_m3_s = self.leak_conductance_m3_s;
        c.xi = self.xi;
        c.turbo_blade_area_frac = self.turbo_blade_area_frac;
        c.turbo_disc_thickness_m = self.turbo_disc_thickness_m;
        c.rotor_disc_thickness_m = self.rotor_disc_thickness_m;
        c.stator_mass_factor = self.stator_mass_factor;
        c.motor_kg_per_nm = self.motor_kg_per_nm;
        c.bearing_kg = self.bearing_kg;
        c.k_bear_w_per_rads = self.k_bear_w_per_rads;
        c.eta_motor = self.eta_motor;
        c.p_ctrl_w = self.p_ctrl_w;
        c.conductance_to_sink_w_k = self.conductance_to_sink_w_k;
        c.t_sink_k = self.t_sink_k;
    }

    /// Field names of the reference DragCompressor dataclass (the Python reference applies the same overrides).
    pub fn to_value(&self) -> Value {
        json!({
            "turbo_kS": self.turbo_k_s,
            "turbo_kK": self.turbo_k_k,
            "leak_conductance_m3_s": self.leak_conductance_m3_s,
            "xi": self.xi,
            "turbo_blade_area_frac": self.turbo_blade_area_frac,
            "turbo_disc_thickness_m": self.turbo_disc_thickness_m,
            "rotor_disc_thickness_m": self.rotor_disc_thickness_m,
            "stator_mass_factor": self.stator_mass_factor,
            "motor_kg_per_Nm": self.motor_kg_per_nm,
            "bearing_kg": self.bearing_kg,
            "k_bear_W_per_rads": self.k_bear_w_per_rads,
            "eta_motor": self.eta_motor,
            "P_ctrl_W": self.p_ctrl_w,
            "conductance_to_sink_W_K": self.conductance_to_sink_w_k,
            "T_sink_K": self.t_sink_k,
        })
    }
}

/// The eight unfavourable corners, in (kS, kK, leak) band-end order.
pub fn corners() -> Vec<(String, Coeffs)> {
    let mut out = vec![];
    for ks in KS_BAND {
        for kk in KK_BAND {
            for leak in LEAK_BAND {
                let c = Coeffs { turbo_k_s: ks, turbo_k_k: kk, leak_conductance_m3_s: leak, ..UNFAVOURABLE_MONOTONE };
                out.push((format!("U-kS{}-kK{}-L{}", py_format_g(ks), py_format_g(kk), py_format_g(leak)), c));
            }
        }
    }
    out
}

/// Nominal followed by the corners.
pub fn coefficient_sets() -> Vec<(String, Coeffs)> {
    let mut v = vec![("NOMINAL".to_string(), NOMINAL)];
    v.extend(corners());
    v
}

// ------------------------------------------------------------------------------------------------ inputs

/// One compressor of the design space (F3 grid design without R1 / R2 / R3).
#[derive(Debug, Clone)]
pub struct Comp {
    pub id: String,
    pub design: Map<String, Value>,
    pub grid_index: usize,
}

/// One intake geometry (d collapsed).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Intake {
    pub area: f64,
    pub g: usize,
}

impl Intake {
    pub fn ld(&self) -> f64 {
        GEOMS[self.g].0
    }
    pub fn phi(&self) -> f64 {
        GEOMS[self.g].1
    }
    pub fn id(&self) -> String {
        f1_candidate_id(self.area, self.ld(), self.phi())
    }
    /// Geometric channel-wall area 2 phi A L/d (F1 convention).
    pub fn wall_area_m2(&self) -> f64 {
        2.0 * self.phi() * self.area * self.ld()
    }
}

/// Everything the evaluation reads (fail closed on every pin).
pub struct Inputs {
    pub up: UpstreamInputs,
    /// F1 state index of each required state (harness = up.required_states order).
    pub req_f1: Vec<usize>,
    pub state_ids: Vec<String>,
    pub p_avail_w: Vec<f64>,
    pub q_max_w_m2: Vec<f64>,
    /// Free-stream dynamic pressure of each required state (envelope atmosphere), Pa.
    pub q_pa: Vec<f64>,
    pub t12_n: f64,
    pub t25_n: f64,
    pub drag_limit_n: f64,
    pub common_allocation_w: f64,
    pub controls_allowance_w: f64,
    pub p_comp_limit_w: f64,
    pub m_comp_limit_kg: f64,
    pub hall_alloc_w: f64,
    pub n_f3_grid: usize,
    pub compressors: Vec<Comp>,
    /// [geometry][scenario][F1 state]: unit-area IF-A1 records (A = 1 m^2).
    pub unit: Vec<Vec<Vec<IntakeState>>>,
    pub dbf1: abep_config::baseline::Dbf1Config,
    pub body_cd_a_m2: f64,
    pub provenance: Vec<(String, String)>,
}

fn de(e: abep_design::err::DesignError) -> crate::error::AssessError {
    model_error(format!("DCR-001 design chain: {e}"))
}

fn jread(repo: &Path, rel: &str, sha: &str) -> AssessResult<Value> {
    let b = read_verified(&repo.join(rel), sha)?;
    serde_json::from_slice(&b).map_err(|e| model_error(format!("{rel}: {e}")))
}

fn f(v: &Value, what: &str) -> AssessResult<f64> {
    v.as_f64().ok_or_else(|| model_error(format!("{what}: number expected")))
}

/// The preregistration identity: json, md and lock verify and the lock names both files.
pub fn verify_prereg(repo: &Path) -> AssessResult<()> {
    read_verified(&repo.join(PREREG_REL), PREREG_SHA256)?;
    read_verified(&repo.join(PREREG_MD_REL), PREREG_MD_SHA256)?;
    let lock = jread(repo, LOCK_REL, LOCK_SHA256)?;
    for (k, want) in [("dcr001_eval_prereg_v1.json", PREREG_SHA256), ("DCR001_EVAL_PREREG.md", PREREG_MD_SHA256)] {
        if lock["files"][k].as_str() != Some(want) {
            return Err(model_error(format!("{LOCK_REL}: files.{k} != {want}")));
        }
    }
    if lock["dbf1_lock"]["sha256"].as_str() != Some(abep_config::baseline::DBF1_LOCK_SHA256) {
        return Err(model_error(format!("{LOCK_REL}: dbf1_lock differs from the pinned DBF-1 lock")));
    }
    Ok(())
}

/// Read and verify every input (fail closed).
pub fn gather(repo: &Path) -> AssessResult<Inputs> {
    verify_prereg(repo)?;
    let dbf1 = abep_config::baseline::load_dbf1(repo).map_err(|e| model_error(e.to_string()))?;
    let up = load_upstream_inputs(repo).map_err(de)?;
    if up.scenarios != dbf1.upstream.scenarios {
        return Err(model_error("DCR-001: the admitted F1 scenario set differs from the DBF-1 scenario set"));
    }
    let f1_index: HashMap<&str, usize> = up.states.iter().enumerate().map(|(i, s)| (s.as_str(), i)).collect();
    let state_ids = up.required_states.clone();
    let req_f1: Vec<usize> = state_ids
        .iter()
        .map(|s| f1_index.get(s.as_str()).copied().ok_or_else(|| model_error(format!("state {s} not in F1"))))
        .collect::<AssessResult<_>>()?;
    // A4 per-state requirement inputs (AIR_PRIMARY).
    let a4 = jread(repo, A4_REL, A4_SHA256)?;
    let mut a4_by: HashMap<String, (f64, f64)> = HashMap::new();
    for s in a4["states"].as_array().ok_or_else(|| model_error("A4 record: states"))? {
        if s["status"].as_str() != Some("EVALUATED") || s["required"].as_bool() != Some(true) {
            return Err(model_error("A4 record: a state is not EVALUATED / required"));
        }
        let id = s["state_id"].as_str().ok_or_else(|| model_error("A4 state_id"))?.to_string();
        let p = f(&s["modes"]["AIR_PRIMARY"]["P_avail_W"], "A4 P_avail_W")?;
        let q = f(&s["q_max_W_m2"], "A4 q_max_W_m2")?;
        a4_by.insert(id, (p, q));
    }
    let mut p_avail_w = vec![];
    let mut q_max_w_m2 = vec![];
    for s in &state_ids {
        let (p, q) = a4_by.get(s).ok_or_else(|| model_error(format!("A4 record: no state {s}")))?;
        p_avail_w.push(*p);
        q_max_w_m2.push(*q);
    }
    // Thresholds (abep-config) and allocations (pinned mass / power budget).
    let th = Thresholds::workspace()?;
    let lim = |id: &str| th.limit(id).ok_or_else(|| model_error(format!("threshold {id} not configured")));
    let (t12_n, t25_n, drag_limit_n) = (lim("HC-01")?, lim("HC-02")?, lim("HC-09")?);
    let mp = read_pinned(repo, MP_REL).map_err(de)?;
    let alloc = &mp["power"]["allocations"];
    let common_allocation_w = f(&alloc["common_allocation_W"]["value"], "common_allocation_W")?;
    let controls_allowance_w = f(&alloc["controls_thermal_allowance_W"]["value"], "controls_thermal_allowance_W")?;
    let hall_alloc_w = f(&alloc["hall_and_electron_source_envelope_at_common_upper_W"]["value"], "hall envelope W")?;
    if common_allocation_w != dbf1.power_mass.common_allocation_w {
        return Err(model_error("DCR-001: common allocation differs from DBF-1"));
    }
    let lines = mp["lines"]["hall_icp_neutralizer"].as_array().ok_or_else(|| model_error("mass lines"))?;
    let al02 = lines
        .iter()
        .find(|l| l["line"].as_str() == Some("AL-02"))
        .ok_or_else(|| model_error("mass budget: AL-02 missing"))?;
    let m_comp_limit_kg = f(&al02["row54_allocation_kg"], "AL-02 allocation")?;
    // F3 design grid, gated by the inlet-independent codes (identical in every F3 case).
    let f3 = read_pinned(repo, F3D_REL).map_err(de)?;
    let grid = f3["design_grid"].as_array().ok_or_else(|| model_error("F3 design_grid"))?;
    let cases = f3["cases"].as_object().ok_or_else(|| model_error("F3 cases"))?;
    let mut compressors = vec![];
    for (i, d) in grid.iter().enumerate() {
        let mut codes: Option<Vec<&str>> = None;
        for c in cases.values() {
            let s = c["status_by_design"][i].as_str().ok_or_else(|| model_error("F3 status_by_design"))?;
            let mut ii: Vec<&str> = s.split(',').filter(|x| F3_INLET_INDEPENDENT.contains(x)).collect::<Vec<_>>();
            ii.sort();
            match &codes {
                None => codes = Some(ii),
                Some(prev) if *prev != ii => {
                    return Err(model_error(format!("F3 design {i}: inlet-independent codes differ between cases")))
                }
                _ => {}
            }
        }
        if codes.map(|c| c.is_empty()).unwrap_or(false) {
            let o = d.as_object().ok_or_else(|| model_error("F3 design"))?.clone();
            let id = o["id"].as_str().ok_or_else(|| model_error("F3 id"))?.to_string();
            compressors.push(Comp { id, design: o, grid_index: i });
        }
    }
    // Unit-area intake records (A = 1 m^2) per geometry and scenario over every F1 state.
    let mut alt = HashMap::new();
    let probe = f1_candidate_id(up.f1.area_m2[0], GEOMS[0].0, GEOMS[0].1);
    for st in &up.states {
        alt.insert(st.clone(), up.record(&probe, &up.scenarios[0], st).map_err(de)?.alt_km);
    }
    let unit_recs = load_f1_records(&up.f1, &[1.0], &alt).map_err(de)?;
    let mut by: HashMap<(u64, u64, String, String), IntakeState> = HashMap::new();
    for r in unit_recs {
        let (_, ld, phi) = parse_geom(&r.candidate)?;
        by.insert((ld.to_bits(), phi.to_bits(), r.scenario.clone(), r.state.clone()), r);
    }
    let mut unit = vec![];
    for (ld, phi) in GEOMS {
        let mut per_sc = vec![];
        for sc in &up.scenarios {
            let mut v = vec![];
            for st in &up.states {
                let r = by
                    .get(&(ld.to_bits(), phi.to_bits(), sc.clone(), st.clone()))
                    .ok_or_else(|| model_error(format!("F1 unit record missing Ld{ld} phi{phi} {sc} {st}")))?;
                v.push(r.clone());
            }
            per_sc.push(v);
        }
        unit.push(per_sc);
    }
    let atm = abep_mission::intake_drag::EnvelopeAtmospheres::load(repo)?;
    let q_pa = state_ids
        .iter()
        .map(|s| {
            let a = atm.get(s).ok_or_else(|| model_error(format!("no envelope atmosphere {s}")))?;
            Ok(0.5 * a.rho * a.v * a.v)
        })
        .collect::<AssessResult<Vec<f64>>>()?;
    let mut provenance = vec![
        (PREREG_REL.into(), PREREG_SHA256.into()),
        (PREREG_MD_REL.into(), PREREG_MD_SHA256.into()),
        (LOCK_REL.into(), LOCK_SHA256.into()),
        (A4_REL.into(), A4_SHA256.into()),
        (abep_config::baseline::DBF1_LOCK_REL.into(), abep_config::baseline::DBF1_LOCK_SHA256.into()),
        (abep_config::baseline::DBF1_CONFIG_REL.into(), abep_config::baseline::DBF1_CONFIG_SHA256.into()),
        (abep_mission::intake_drag::F1_CORE_REL.into(), abep_mission::intake_drag::F1_CORE_SHA256.into()),
        ("config/MANIFEST.json".into(), th.manifest_sha256.clone()),
    ];
    for (p, s) in abep_design::inputs::PINNED {
        provenance.push((p.to_string(), s.to_string()));
    }
    let body_cd_a_m2 = dbf1.drag.cd * dbf1.drag.a_ref_m2;
    Ok(Inputs {
        n_f3_grid: grid.len(),
        up,
        req_f1,
        state_ids,
        p_avail_w,
        q_max_w_m2,
        q_pa,
        t12_n,
        t25_n,
        drag_limit_n,
        common_allocation_w,
        controls_allowance_w,
        p_comp_limit_w: common_allocation_w - controls_allowance_w,
        m_comp_limit_kg,
        hall_alloc_w,
        compressors,
        unit,
        dbf1,
        body_cd_a_m2,
        provenance,
    })
}

fn parse_geom(cand: &str) -> AssessResult<(f64, f64, f64)> {
    let bad = || model_error(format!("unrecognised candidate {cand}"));
    let rest = cand.strip_prefix('A').ok_or_else(bad)?;
    let (a, rest) = rest.split_once("_Ld").ok_or_else(bad)?;
    let (ld, phi) = rest.split_once("_phi").ok_or_else(bad)?;
    Ok((a.parse().map_err(|_| bad())?, ld.parse().map_err(|_| bad())?, phi.parse().map_err(|_| bad())?))
}

impl Inputs {
    /// IF-A1 records of an intake in one scenario over every F1 state (unit record x A, as load_f1_records).
    pub fn records(&self, it: &Intake, sc: usize) -> Vec<IntakeState> {
        self.unit[it.g][sc]
            .iter()
            .map(|r| {
                let mut x = r.clone();
                x.candidate = it.id();
                x.area_m2 = it.area;
                x.mdot_fwd_kgps =
                    [r.mdot_fwd_kgps[0] * it.area, r.mdot_fwd_kgps[1] * it.area, r.mdot_fwd_kgps[2] * it.area];
                x
            })
            .collect()
    }

    /// The compressor plant with a coefficient set applied.
    pub fn plant(&self, c: &Comp, k: &Coeffs) -> AssessResult<CompressorPlant> {
        let mut p = CompressorPlant::from_design(self.up.ctx(), &c.design, T_CHAIN_K)?;
        k.apply(&mut p.comp);
        Ok(p)
    }

    pub fn plenum(&self, v: f64) -> AssessResult<Plenum> {
        abep_design::optimizer::plenum(&self.up, v, WALL).map_err(de)
    }

    pub fn filter(&self, id: &str) -> AssessResult<&FilterCase> {
        self.up.filter(id).map_err(de)
    }

    /// mdot_req,in(s, T, A) = A4 K-MDOT-REQ(T, P_avail + q_max A).
    pub fn mdot_req(&self, i: usize, t_n: f64, area: f64) -> AssessResult<f64> {
        Ok(abep_mission::conservation_bounds::mdot_required(t_n, self.p_avail_w[i] + self.q_max_w_m2[i] * area)?)
    }

    /// Necessary flow at the DBF-1 Hall + ICP design allocation (information).
    pub fn mdot_req_alloc(&self, i: usize, area: f64) -> AssessResult<f64> {
        Ok(abep_mission::conservation_bounds::mdot_required(self.t12_n, self.hall_alloc_w + self.q_max_w_m2[i] * area)?)
    }
}

// ------------------------------------------------------------------------------------------------ intake stage

/// S1 / S2 quantities of one intake.
#[derive(Debug, Clone, PartialEq)]
pub struct IntakeEval {
    pub intake: Intake,
    pub drag_max_n: f64,
    pub drag_max_se_n: f64,
    pub drag_max_at: (usize, usize),
    pub drag_ok: bool,
    /// min over required states and scenarios of mdot_cap / mdot_req,in(T12).
    pub cap_ratio: f64,
    pub cap_ratio_at: (usize, usize),
    pub req12: Vec<f64>,
    pub req25: Vec<f64>,
    pub req_alloc: Vec<f64>,
}

pub fn eval_intake(inp: &Inputs, it: Intake) -> AssessResult<IntakeEval> {
    let n = inp.state_ids.len();
    let mut req12 = Vec::with_capacity(n);
    let mut req25 = Vec::with_capacity(n);
    let mut req_alloc = Vec::with_capacity(n);
    for i in 0..n {
        req12.push(inp.mdot_req(i, inp.t12_n, it.area)?);
        req25.push(inp.mdot_req(i, inp.t25_n, it.area)?);
        req_alloc.push(inp.mdot_req_alloc(i, it.area)?);
    }
    let (mut dmax, mut dse, mut dat) = (f64::NEG_INFINITY, 0.0, (0, 0));
    let (mut cr, mut cat) = (f64::INFINITY, (0, 0));
    for (si, sc) in inp.up.scenarios.iter().enumerate() {
        for (i, st) in inp.state_ids.iter().enumerate() {
            let (dpa, se) = inp.up.drag_per_area(sc, it.ld(), it.phi(), st).map_err(de)?;
            let d = dpa * it.area;
            if d > dmax {
                (dmax, dse, dat) = (d, se * it.area, (si, i));
            }
            let u = &inp.unit[it.g][si][inp.req_f1[i]];
            let cap = u.mdot_fwd_kgps[0] * it.area + u.mdot_fwd_kgps[1] * it.area + u.mdot_fwd_kgps[2] * it.area;
            let r = cap / req12[i];
            if r < cr {
                (cr, cat) = (r, (si, i));
            }
        }
    }
    Ok(IntakeEval {
        intake: it,
        drag_max_n: dmax,
        drag_max_se_n: dse,
        drag_max_at: dat,
        drag_ok: dmax <= inp.drag_limit_n,
        cap_ratio: cr,
        cap_ratio_at: cat,
        req12,
        req25,
        req_alloc,
    })
}

// ------------------------------------------------------------------------------------------------ steady stage

/// Early-termination mode of a (intake, filter, compressor) evaluation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    /// Stop a set pressure at its first failed admissibility criterion (S3).
    Admissible,
    /// Stop a set pressure at its first failed non-flow steady criterion (non-closure set).
    NonFlow,
    /// No early termination.
    Full,
}

/// Steady evaluation of one design (intake, filter, compressor, P_set) over the scenarios evaluated.
#[derive(Debug, Clone, PartialEq)]
pub struct Eval {
    pub complete: bool,
    pub n_rows: usize,
    pub n_dom_fail: usize,
    pub n_deadhead: usize,
    pub n_gaede: usize,
    pub dead_margin_min: f64,
    /// min of mdot_del / mdot_req,in(T12) (0 where out of domain).
    pub r12: f64,
    pub r12_at: (usize, usize),
    /// min of mdot_del / mdot_req,in(T12) over the in-domain rows only (v2 key M3).
    pub r12_in: f64,
    pub n_t12_fail: usize,
    /// bit per scenario: some state reaches the T25 necessary flow.
    pub t25_mask: u32,
    pub n_t25_rows: usize,
    pub r_alloc: f64,
    pub p_el_max: f64,
    pub m_max: f64,
    pub t_comp_max: f64,
    pub xo_min: f64,
    pub xo_max: f64,
    /// per evaluated scenario: min delivered flow over its in-domain required states.
    pub mdot_min: Vec<f64>,
}

impl Eval {
    fn new() -> Eval {
        Eval {
            complete: false,
            n_rows: 0,
            n_dom_fail: 0,
            n_deadhead: 0,
            n_gaede: 0,
            dead_margin_min: f64::INFINITY,
            r12: f64::INFINITY,
            r12_at: (0, 0),
            r12_in: f64::INFINITY,
            n_t12_fail: 0,
            t25_mask: 0,
            n_t25_rows: 0,
            r_alloc: f64::INFINITY,
            p_el_max: f64::NEG_INFINITY,
            m_max: f64::NEG_INFINITY,
            t_comp_max: f64::NEG_INFINITY,
            xo_min: f64::INFINITY,
            xo_max: f64::NEG_INFINITY,
            mdot_min: vec![],
        }
    }

    pub fn domain_ok(&self) -> bool {
        self.complete && self.n_dom_fail == 0 && self.dead_margin_min > 0.0
    }
    pub fn t12_ok(&self) -> bool {
        self.domain_ok() && self.r12 >= 1.0
    }
    pub fn t25_ok(&self, n_sc: usize) -> bool {
        self.complete && self.t25_mask == (1u32 << n_sc) - 1
    }
    pub fn power_ok(&self, lim: f64) -> bool {
        self.complete && self.p_el_max.is_finite() && self.p_el_max <= lim
    }
    pub fn mass_ok(&self, lim: f64) -> bool {
        self.complete && self.m_max.is_finite() && self.m_max <= lim
    }
    fn non_flow_alive(&self, inp: &Inputs) -> bool {
        self.n_dom_fail == 0
            && self.dead_margin_min > 0.0
            && !(self.p_el_max > inp.p_comp_limit_w)
            && !(self.m_max > inp.m_comp_limit_kg)
    }
}

/// Intake-side coefficients of an (intake, filter) pair per scenario.
pub type Sides = Vec<(Vec<Sp3>, Vec<Sp3>)>;

pub fn sides(inp: &Inputs, it: &Intake, fc: &FilterCase) -> AssessResult<Sides> {
    (0..inp.up.scenarios.len()).map(|si| Ok(intake_side(&inp.records(it, si), fc, 1.0)?)).collect()
}

/// Evaluate every set pressure of one (intake, filter, compressor plant), scenario by scenario.
pub fn eval_triple(
    inp: &Inputs,
    ie: &IntakeEval,
    sd: &Sides,
    plant: &CompressorPlant,
    pl: &Plenum,
    mode: Mode,
) -> AssessResult<Vec<Eval>> {
    let m = TARGETS_PA.len();
    let mut ev: Vec<Eval> = (0..m).map(|_| Eval::new()).collect();
    let mut alive = vec![true; m];
    let n_sc = inp.up.scenarios.len();
    let (b_dead, b_char) = (reason_bit(R_DEADHEAD), reason_bit(R_CHARACTERISTIC));
    for (si, side) in sd.iter().enumerate() {
        let sw = steady_sweep(side, plant, pl, &inp.up.materials, &TARGETS_PA, None)?;
        for (j, e) in ev.iter_mut().enumerate() {
            if !alive[j] {
                continue;
            }
            let mut sc_min = f64::INFINITY;
            let mut t25 = false;
            for (i, &fi) in inp.req_f1.iter().enumerate() {
                let idx = fi * m + j;
                let bits = sw.bits[idx];
                let margin = sw.p_deadhead_pa[idx] / TARGETS_PA[j] - 1.0;
                e.n_rows += 1;
                if bits & b_dead != 0 {
                    e.n_deadhead += 1;
                }
                if bits & b_char != 0 {
                    e.n_gaede += 1;
                }
                if margin.is_finite() {
                    e.dead_margin_min = e.dead_margin_min.min(margin);
                } else {
                    e.dead_margin_min = f64::NEG_INFINITY;
                }
                let ok = bits == 0 && sw.in_domain[idx] && margin > 0.0;
                let ratio = if ok {
                    let md = sw.mdot_total_kgps[idx];
                    sc_min = sc_min.min(md);
                    if md >= ie.req25[i] {
                        t25 = true;
                        e.n_t25_rows += 1;
                    }
                    e.r_alloc = e.r_alloc.min(md / ie.req_alloc[i]);
                    e.p_el_max = e.p_el_max.max(sw.p_el_w[idx]);
                    e.m_max = e.m_max.max(sw.m_compressor_kg[idx]);
                    e.t_comp_max = e.t_comp_max.max(sw.t_comp_k[idx]);
                    let xo = sw.x_s_flow_mole[0][idx];
                    e.xo_min = e.xo_min.min(xo);
                    e.xo_max = e.xo_max.max(xo);
                    e.r12_in = e.r12_in.min(md / ie.req12[i]);
                    md / ie.req12[i]
                } else {
                    e.n_dom_fail += 1;
                    e.r_alloc = 0.0;
                    0.0
                };
                if ratio < 1.0 {
                    e.n_t12_fail += 1;
                }
                if ratio < e.r12 {
                    e.r12 = ratio;
                    e.r12_at = (si, i);
                }
            }
            if t25 {
                e.t25_mask |= 1 << si;
            }
            e.mdot_min.push(sc_min);
            let dead = match mode {
                Mode::Full => false,
                Mode::NonFlow => !e.non_flow_alive(inp),
                Mode::Admissible => !e.non_flow_alive(inp) || e.r12 < 1.0 || !t25,
            };
            if dead {
                alive[j] = false;
            }
        }
        if !alive.iter().any(|a| *a) {
            break;
        }
    }
    for (j, e) in ev.iter_mut().enumerate() {
        e.complete = alive[j] || e.mdot_min.len() == n_sc;
    }
    Ok(ev)
}

/// Run `f(0..n)` on `threads` workers; results in index order (deterministic).
pub fn par_map<T: Send, F: Fn(usize) -> AssessResult<T> + Sync>(
    n: usize,
    threads: usize,
    f: F,
) -> AssessResult<Vec<T>> {
    let next = AtomicUsize::new(0);
    let out: Mutex<Vec<Option<AssessResult<T>>>> = Mutex::new((0..n).map(|_| None).collect());
    std::thread::scope(|s| {
        for _ in 0..threads.max(1) {
            s.spawn(|| loop {
                let i = next.fetch_add(1, Ordering::SeqCst);
                if i >= n {
                    break;
                }
                if n >= 1000 && i % (n / 20) == 0 {
                    eprintln!("DCR-001 progress {i} / {n}");
                }
                let r = f(i);
                let failed = r.is_err();
                out.lock().expect("lock")[i] = Some(r);
                if failed {
                    next.store(n, Ordering::SeqCst);
                }
            });
        }
    });
    let mut v = Vec::with_capacity(n);
    for r in out.into_inner().expect("lock") {
        match r {
            Some(x) => v.push(x?),
            None => return Err(model_error("DCR-001: a work item was not evaluated")),
        }
    }
    Ok(v)
}

// ------------------------------------------------------------------------------------------------ designs

/// One evaluated design (steady part); V and the controller are chosen in S5.
#[derive(Debug, Clone)]
pub struct Design {
    pub ie: usize,
    pub filter: usize,
    pub comp: usize,
    pub target: usize,
    pub nominal: Eval,
    /// The eight corners (filled in S4 for admissible designs).
    pub corners: Vec<Eval>,
}

/// Criteria flags of a steady evaluation.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Flags {
    pub flow_t12: bool,
    pub flow_t25: bool,
    pub domain: bool,
    pub drag: bool,
    pub power: bool,
    pub mass: bool,
}

impl Flags {
    pub fn steady_admissible(&self) -> bool {
        self.flow_t12 && self.flow_t25 && self.domain && self.drag && self.power && self.mass
    }
    /// Failed non-flow steady criteria (C-DOMAIN, C-DRAG, C-POWER, C-MASS).
    pub fn n_non_flow_failed(&self) -> usize {
        [self.domain, self.drag, self.power, self.mass].iter().filter(|x| !**x).count()
    }
}

pub fn flags(inp: &Inputs, e: &Eval, drag_ok: bool) -> Flags {
    let n_sc = inp.up.scenarios.len();
    Flags {
        flow_t12: e.t12_ok(),
        flow_t25: e.t25_ok(n_sc),
        domain: e.domain_ok(),
        drag: drag_ok,
        power: e.power_ok(inp.p_comp_limit_w),
        mass: e.mass_ok(inp.m_comp_limit_kg),
    }
}

/// Robust worst-state T12 ratio over nominal and the corners (0 for an incomplete / out-of-domain corner).
pub fn r12_robust(d: &Design) -> f64 {
    let mut r = if d.nominal.complete { d.nominal.r12 } else { 0.0 };
    for c in &d.corners {
        r = r.min(if c.complete { c.r12 } else { 0.0 });
    }
    r
}

fn bin(x: f64, per_unit: f64) -> i64 {
    (x * per_unit).floor() as i64
}

/// Context needed to rank and describe designs.
pub struct Space<'a> {
    pub inp: &'a Inputs,
    pub intakes: &'a [IntakeEval],
}

impl Space<'_> {
    pub fn design_id(&self, d: &Design, v: f64) -> String {
        abep_design::optimizer::design_id(
            &self.intakes[d.ie].intake.id(),
            FILTERS[d.filter],
            &self.inp.compressors[d.comp].id,
            v,
            TARGETS_PA[d.target],
        )
    }

    pub fn flags(&self, e: &Eval, d: &Design) -> Flags {
        flags(self.inp, e, self.intakes[d.ie].drag_ok)
    }

    pub fn robust(&self, d: &Design) -> bool {
        !d.corners.is_empty() && d.corners.iter().all(|c| self.flags(c, d).steady_admissible())
    }

    /// K1..K7 (+ K10 id at V = the smallest volume) of an admissible design.
    pub fn k_keys(&self, d: &Design) -> (i64, i64, i64, i64, f64, f64, f64, f64, String) {
        let e = &d.nominal;
        (
            if self.robust(d) { 0 } else { 1 },
            -bin(r12_robust(d), 20.0),
            -bin(e.r12, 20.0),
            bin(e.m_max, 10.0),
            self.intakes[d.ie].intake.wall_area_m2(),
            -TARGETS_PA[d.target],
            self.intakes[d.ie].drag_max_n,
            e.p_el_max,
            self.design_id(d, VOLUMES_M3[0]),
        )
    }

    /// N1' (pre-stability), N2, then K3..K7 and the id.
    pub fn n_keys(&self, d: &Design) -> (usize, f64, i64, f64, f64, f64, f64, String) {
        let e = &d.nominal;
        let fl = self.flags(e, d);
        let r12 = if e.complete { e.r12 } else { 0.0 };
        (
            fl.n_non_flow_failed(),
            -r12,
            bin(e.m_max, 10.0),
            self.intakes[d.ie].intake.wall_area_m2(),
            -TARGETS_PA[d.target],
            self.intakes[d.ie].drag_max_n,
            e.p_el_max,
            self.design_id(d, VOLUMES_M3[0]),
        )
    }
}

fn cmp_f(a: f64, b: f64) -> std::cmp::Ordering {
    a.total_cmp(&b)
}

pub fn cmp_k(
    a: &(i64, i64, i64, i64, f64, f64, f64, f64, String),
    b: &(i64, i64, i64, i64, f64, f64, f64, f64, String),
) -> std::cmp::Ordering {
    a.0.cmp(&b.0)
        .then(a.1.cmp(&b.1))
        .then(a.2.cmp(&b.2))
        .then(a.3.cmp(&b.3))
        .then(cmp_f(a.4, b.4))
        .then(cmp_f(a.5, b.5))
        .then(cmp_f(a.6, b.6))
        .then(cmp_f(a.7, b.7))
        .then(a.8.cmp(&b.8))
}

pub fn cmp_n(
    a: &(usize, f64, i64, f64, f64, f64, f64, String),
    b: &(usize, f64, i64, f64, f64, f64, f64, String),
) -> std::cmp::Ordering {
    a.0.cmp(&b.0)
        .then(cmp_f(a.1, b.1))
        .then(a.2.cmp(&b.2))
        .then(cmp_f(a.3, b.3))
        .then(cmp_f(a.4, b.4))
        .then(cmp_f(a.5, b.5))
        .then(cmp_f(a.6, b.6))
        .then(a.7.cmp(&b.7))
}

// ------------------------------------------------------------------------------------------------ stability

/// One Rust stability row.
#[derive(Debug, Clone, PartialEq)]
pub struct StabRow {
    pub scenario: usize,
    pub state: usize,
    pub class: &'static str,
    pub kinds: Vec<&'static str>,
}

pub fn controller(kp: f64, ti: f64) -> Controller {
    Controller { kp, ti_s: ti, f_valve_hz: F_VALVE_HZ, authority: AUTHORITY }
}

/// Rust classes of a design at every (scenario, required state); `stop_at_first` returns after the first non-S row.
#[allow(clippy::too_many_arguments)]
pub fn stability_rows(
    inp: &Inputs,
    it: &Intake,
    fc: &FilterCase,
    plant: &CompressorPlant,
    pl: &Plenum,
    ctrl: Controller,
    p_set: f64,
    stop_at_first: bool,
) -> AssessResult<Vec<StabRow>> {
    let mut out = vec![];
    for si in 0..inp.up.scenarios.len() {
        let recs = inp.records(it, si);
        for (i, &fi) in inp.req_f1.iter().enumerate() {
            let r = stability_class_events(fc, plant, pl, ctrl, &inp.up.materials, &recs[fi], p_set, WINDOW_S)?;
            let row = StabRow {
                scenario: si,
                state: i,
                class: r.class.as_str(),
                kinds: r.equilibria.iter().map(|e| e.kind.as_str()).collect(),
            };
            let bad = row.class != "S";
            out.push(row);
            if bad && stop_at_first {
                return Ok(out);
            }
        }
    }
    Ok(out)
}

fn class_counts(rows: &[StabRow]) -> Value {
    let mut m = Map::new();
    for k in ["S", "U", "R"] {
        m.insert(k.into(), json!(rows.iter().filter(|r| r.class == k).count()));
    }
    Value::Object(m)
}

// ------------------------------------------------------------------------------------------------ search

/// Summary JSON of a steady evaluation.
pub fn eval_value(inp: &Inputs, e: &Eval, drag_ok: bool) -> Value {
    let fl = flags(inp, e, drag_ok);
    let sc = &inp.up.scenarios;
    json!({
        "complete": e.complete,
        "rows_evaluated": e.n_rows,
        "rows_out_of_domain": e.n_dom_fail,
        "rows_dead_head": e.n_deadhead,
        "rows_gaede_outside_K_1_K0": e.n_gaede,
        "dead_head_margin_min": fin(e.dead_margin_min),
        "r12_worst": fin(e.r12),
        "r12_in_domain_rows_worst": fin(e.r12_in),
        "r12_worst_at": {"scenario": sc[e.r12_at.0], "state_id": inp.state_ids[e.r12_at.1]},
        "rows_failing_T12": e.n_t12_fail,
        "T25_scenarios_with_a_passing_state": (0..sc.len()).filter(|k| e.t25_mask & (1 << k) != 0).count(),
        "rows_reaching_T25": e.n_t25_rows,
        "r_alloc_1050W_worst": fin(e.r_alloc),
        "P_compressor_el_max_W": fin(e.p_el_max),
        "m_compressor_max_kg": fin(e.m_max),
        "T_compressor_max_K": fin(e.t_comp_max),
        "x_O_delivered_min_max": [fin(e.xo_min), fin(e.xo_max)],
        "mdot_delivered_min_by_scenario_kg_s": e.mdot_min.iter().zip(sc).map(|(m, s)| (s.clone(), fin(*m))).collect::<Map<_, _>>(),
        "criteria": {
            "C-FLOW-T12": fl.flow_t12, "C-FLOW-T25": fl.flow_t25, "C-DOMAIN": fl.domain, "C-DRAG": fl.drag,
            "C-POWER": fl.power, "C-MASS": fl.mass
        }
    })
}

fn fin(x: f64) -> Value {
    if x.is_finite() {
        json!(x)
    } else {
        Value::Null
    }
}

/// The selection (or best design) with its stability choice.
#[derive(Debug, Clone)]
pub struct Selection {
    pub design: Design,
    pub v_m3: f64,
    pub ctrl: (f64, f64),
    pub admissible: bool,
    pub robust_steady: bool,
    pub n_stability_designs: usize,
}

/// Output of [`search`]: the search record and the Python reference input.
pub struct SearchOut {
    pub record: Value,
    pub spec: Value,
}

fn intake_value(inp: &Inputs, ie: &IntakeEval) -> Value {
    json!({
        "candidate": ie.intake.id(), "area_m2": ie.intake.area, "L_over_d": ie.intake.ld(), "phi": ie.intake.phi(),
        "wall_area_m2": ie.intake.wall_area_m2(),
        "drag_intake_max_N": ie.drag_max_n, "drag_intake_max_se_N": ie.drag_max_se_n,
        "drag_max_at": {"scenario": inp.up.scenarios[ie.drag_max_at.0], "state_id": inp.state_ids[ie.drag_max_at.1]},
        "C-DRAG": ie.drag_ok,
        "capture_ratio_T12_worst": ie.cap_ratio,
        "capture_ratio_at": {"scenario": inp.up.scenarios[ie.cap_ratio_at.0], "state_id": inp.state_ids[ie.cap_ratio_at.1]},
    })
}

/// Evaluate a set of designs on the steady chain (parallel over triples).
fn steady_stage(
    inp: &Inputs,
    intakes: &[IntakeEval],
    ies: &[usize],
    comps: &[usize],
    mode: Mode,
    threads: usize,
) -> AssessResult<Vec<Design>> {
    let pl = inp.plenum(VOLUMES_M3[0])?;
    let plants: Vec<CompressorPlant> =
        comps.iter().map(|c| inp.plant(&inp.compressors[*c], &NOMINAL)).collect::<AssessResult<_>>()?;
    let pairs: Vec<(usize, usize)> = ies.iter().flat_map(|i| (0..FILTERS.len()).map(move |f| (*i, f))).collect();
    let sides_v = par_map(pairs.len(), threads, |k| {
        let (i, fi) = pairs[k];
        sides(inp, &intakes[i].intake, inp.filter(FILTERS[fi])?)
    })?;
    let n = pairs.len() * comps.len();
    let evs = par_map(n, threads, |k| {
        let (p, c) = (k / comps.len(), k % comps.len());
        eval_triple(inp, &intakes[pairs[p].0], &sides_v[p], &plants[c], &pl, mode)
    })?;
    let mut out = vec![];
    for (k, ev) in evs.into_iter().enumerate() {
        let (p, c) = (k / comps.len(), k % comps.len());
        for (j, e) in ev.into_iter().enumerate() {
            out.push(Design {
                ie: pairs[p].0,
                filter: pairs[p].1,
                comp: comps[c],
                target: j,
                nominal: e,
                corners: vec![],
            });
        }
    }
    Ok(out)
}

/// S4: the eight corners of the given designs (full evaluation).
fn corner_stage(inp: &Inputs, intakes: &[IntakeEval], ds: &mut [Design], threads: usize) -> AssessResult<()> {
    let pl = inp.plenum(VOLUMES_M3[0])?;
    let mut triples: Vec<(usize, usize, usize)> = ds.iter().map(|d| (d.ie, d.filter, d.comp)).collect();
    triples.sort();
    triples.dedup();
    let cs = corners();
    let res = par_map(triples.len() * cs.len(), threads, |k| {
        let ((i, fi, c), ci) = (triples[k / cs.len()], k % cs.len());
        let plant = inp.plant(&inp.compressors[c], &cs[ci].1)?;
        let sd = sides(inp, &intakes[i].intake, inp.filter(FILTERS[fi])?)?;
        eval_triple(inp, &intakes[i], &sd, &plant, &pl, Mode::Full)
    })?;
    for d in ds.iter_mut() {
        let t = triples.binary_search(&(d.ie, d.filter, d.comp)).expect("triple");
        d.corners = (0..cs.len()).map(|ci| res[t * cs.len() + ci][d.target].clone()).collect();
    }
    Ok(())
}

/// S5: the first (V, controller) at which a design is S at every row (Rust screen), in K8 / K9 order.
fn stable_choice(inp: &Inputs, it: &Intake, d: &Design) -> AssessResult<Option<(f64, (f64, f64))>> {
    let fc = inp.filter(FILTERS[d.filter])?;
    let plant = inp.plant(&inp.compressors[d.comp], &NOMINAL)?;
    for v in VOLUMES_M3 {
        let pl = inp.plenum(v)?;
        for (kp, ti) in CTRL_ORDER {
            let rows = stability_rows(inp, it, fc, &plant, &pl, controller(kp, ti), TARGETS_PA[d.target], true)?;
            if rows.iter().all(|r| r.class == "S") {
                return Ok(Some((v, (kp, ti))));
            }
        }
    }
    Ok(None)
}

/// The full preregistered search.
pub fn search(inp: &Inputs, threads: usize, rust_commit: &str) -> AssessResult<SearchOut> {
    let n_sc = inp.up.scenarios.len();
    // S1 / S2: intakes.
    let all: Vec<Intake> =
        areas().into_iter().flat_map(|a| (0..GEOMS.len()).map(move |g| Intake { area: a, g })).collect();
    let intakes = par_map(all.len(), threads, |k| eval_intake(inp, all[k]))?;
    let i_drag: Vec<usize> = (0..intakes.len()).filter(|k| intakes[*k].drag_ok).collect();
    let i_cap: Vec<usize> = i_drag.iter().copied().filter(|k| intakes[*k].cap_ratio >= 1.0).collect();
    // S0: compressors (mass lower bound at zero throughput: torque floor).
    let zero = [0.0; 3];
    let mut m_lb = vec![];
    for c in &inp.compressors {
        m_lb.push(inp.plant(c, &NOMINAL)?.cascade(&inp.up.materials, &zero, &zero)?.mass_kg);
    }
    let c_mass: Vec<usize> = (0..inp.compressors.len()).filter(|k| m_lb[*k] <= inp.m_comp_limit_kg).collect();
    let space = Space { inp, intakes: &intakes };
    eprintln!(
        "DCR-001 S0 C_mass {} / {}; S1 I_drag {}; S2 I_cap {}",
        c_mass.len(),
        inp.compressors.len(),
        i_drag.len(),
        i_cap.len()
    );
    // S3: admissible-mode steady stage on I_cap.
    let mut stage3 = vec![];
    if !i_cap.is_empty() {
        stage3 = steady_stage(inp, &intakes, &i_cap, &c_mass, Mode::Admissible, threads)?;
    }
    let mut adm: Vec<Design> =
        stage3.iter().filter(|d| space.flags(&d.nominal, d).steady_admissible()).cloned().collect();
    let n_stage3 = stage3.len();
    let n_adm_steady = adm.len();
    let mut n_robust_steady = 0;
    let mut selection: Option<Selection> = None;
    let mut ranked_summary = vec![];
    let mut cap_reached = false;
    let mut n_stab_designs = 0;
    let mut nonclosure: Option<Value> = None;
    if !adm.is_empty() {
        corner_stage(inp, &intakes, &mut adm, threads)?;
        n_robust_steady = adm.iter().filter(|d| space.robust(d)).count();
        let mut keyed: Vec<_> = adm.iter().map(|d| (space.k_keys(d), d.clone())).collect();
        keyed.sort_by(|a, b| cmp_k(&a.0, &b.0));
        for (_, d) in keyed.iter().take(10) {
            ranked_summary.push(design_summary(&space, d));
        }
        for (_, d) in &keyed {
            if n_stab_designs >= STABILITY_CAP {
                cap_reached = true;
                break;
            }
            n_stab_designs += 1;
            if let Some((v, ctrl)) = stable_choice(inp, &intakes[d.ie].intake, d)? {
                selection = Some(Selection {
                    robust_steady: space.robust(d),
                    design: d.clone(),
                    v_m3: v,
                    ctrl,
                    admissible: true,
                    n_stability_designs: n_stab_designs,
                });
                break;
            }
        }
    }
    let mut v2_applied = false;

    let mut n_nonclosure_evaluated = 0usize;
    if selection.is_none() {
        // v1 non-closure set: I_drag x filters x C_mass x P_set with the flow criteria relaxed.
        eprintln!(
            "DCR-001 non-closure set: {} intakes x {} filters x {} compressors",
            i_drag.len(),
            FILTERS.len(),
            c_mass.len()
        );
        let set = steady_stage(inp, &intakes, &i_drag, &c_mass, Mode::NonFlow, threads)?;
        let n_v1_nonflow_ok = set.iter().filter(|d| space.flags(&d.nominal, d).n_non_flow_failed() == 0).count();
        if n_v1_nonflow_ok > 0 {
            n_nonclosure_evaluated = set.len();
            let mut keyed: Vec<_> = set.iter().map(|d| (space.n_keys(d), d)).collect();
            keyed.sort_by(|a, b| cmp_n(&a.0, &b.0));
            for (_, d) in keyed.iter().take(10) {
                ranked_summary.push(design_summary(&space, d));
            }
            for (k, d) in &keyed {
                if k.0 > 0 {
                    break;
                }
                if n_stab_designs >= STABILITY_CAP {
                    cap_reached = true;
                    break;
                }
                n_stab_designs += 1;
                if let Some((v, ctrl)) = stable_choice(inp, &intakes[d.ie].intake, d)? {
                    selection = Some(Selection {
                        design: (*d).clone(),
                        v_m3: v,
                        ctrl,
                        admissible: false,
                        robust_steady: false,
                        n_stability_designs: n_stab_designs,
                    });
                    break;
                }
            }
        }
        if selection.is_none() {
            // Amendment v2 (dcr001_eval_prereg_v2.json): I_cap x filters x all S0 compressors x P_set, keys M1..M10.
            v2_applied = true;
            if i_cap.is_empty() {
                return Err(model_error("DCR-001 v2: I_cap is empty; the v2 best-design set is undefined"));
            }
            let all_c: Vec<usize> = (0..inp.compressors.len()).collect();
            eprintln!(
                "DCR-001 v2 set: {} intakes x {} filters x {} compressors",
                i_cap.len(),
                FILTERS.len(),
                all_c.len()
            );
            let mut set = steady_stage(inp, &intakes, &i_cap, &all_c, Mode::Full, threads)?;
            n_nonclosure_evaluated = set.len();
            set.sort_by(|a, b| cmp_m(&space.m_keys(a), &space.m_keys(b)));
            for d in set.iter().take(10) {
                ranked_summary.push(design_summary(&space, d));
            }
            let mut best = set.into_iter().next().ok_or_else(|| model_error("DCR-001 v2: empty set"))?;
            corner_stage(inp, &intakes, std::slice::from_mut(&mut best), threads)?;
            let (v, ctrl, n_bad) = fewest_non_s(inp, &intakes[best.ie].intake, &best)?;
            eprintln!("DCR-001 v2 best stability: V {v} ctrl {ctrl:?} non-S rows {n_bad}");
            n_stab_designs += 1;
            selection = Some(Selection {
                design: best,
                v_m3: v,
                ctrl,
                admissible: false,
                robust_steady: false,
                n_stability_designs: n_stab_designs,
            });
        }
        // Captured-flow frontier per geometry within the drag filter.
        let mut frontier = Map::new();
        for (g, (ld, phi)) in GEOMS.iter().enumerate() {
            let best = i_drag
                .iter()
                .filter(|k| intakes[**k].intake.g == g)
                .max_by(|a, b| intakes[**a].cap_ratio.total_cmp(&intakes[**b].cap_ratio));
            let max_area = i_drag
                .iter()
                .filter(|k| intakes[**k].intake.g == g)
                .map(|k| intakes[*k].intake.area)
                .fold(f64::NAN, f64::max);
            frontier.insert(
                format!("Ld{}_phi{}", py_format_g(*ld), py_format_g(*phi)),
                json!({
                    "largest_area_within_drag_m2": fin(max_area),
                    "best_capture_ratio_T12_within_drag": best.map(|k| intakes[*k].cap_ratio),
                    "at_area_m2": best.map(|k| intakes[*k].intake.area),
                }),
            );
        }
        nonclosure = Some(json!({
            "v1_set": "I_drag x filters x C_mass x P_set (early termination on non-flow failures)",
            "v1_designs_meeting_every_non_flow_steady_criterion": n_v1_nonflow_ok,
            "rule_applied": if v2_applied { "amendment v2: I_cap x filters x all S0 compressors x P_set, keys M1..M10" } else { "v1" },
            "designs_ranked": n_nonclosure_evaluated,
            "captured_flow_frontier_within_drag": frontier,
        }));
    }
    // Records.
    let sel = selection.ok_or_else(|| model_error("DCR-001: no design could be selected or ranked"))?;
    let it = intakes[sel.design.ie].intake;
    let sel_id = space.design_id(&sel.design, sel.v_m3);
    let status = if sel.admissible {
        if sel.robust_steady {
            "ADMISSIBLE_ROBUST"
        } else {
            "ADMISSIBLE_CONDITIONAL_ON_COMPRESSOR_COEFFICIENTS"
        }
    } else {
        "NOT_ADMISSIBLE"
    };
    let comp = &inp.compressors[sel.design.comp];
    let spec = json!({
        "schema": SPEC_SCHEMA,
        "dcr": "DCR-DBF1-001",
        "prereg_sha256": PREREG_SHA256,
        "design_id": sel_id,
        "intake": {"candidate": it.id(), "area_m2": it.area, "L_over_d": it.ld(), "phi": it.phi()},
        "filter": FILTERS[sel.design.filter],
        "compressor": {"id": comp.id, "f3_grid_index": comp.grid_index},
        "V_m3": sel.v_m3,
        "wall": WALL,
        "P_set_Pa": TARGETS_PA[sel.design.target],
        "controller": {"Kp": sel.ctrl.0, "Ti_s": sel.ctrl.1, "f_valve_hz": F_VALVE_HZ, "authority": AUTHORITY},
        "scenarios": inp.up.scenarios,
        "states": inp.state_ids,
        "coefficient_sets": coefficient_sets().iter().map(|(k, c)| json!({"id": k, "overrides": c.to_value()})).collect::<Vec<_>>(),
    });
    let mut stage_counts = Map::new();
    stage_counts.insert("S0_design_space_compressors".into(), json!(inp.compressors.len()));
    stage_counts.insert("S0_C_mass".into(), json!(c_mass.len()));
    stage_counts.insert("S1_I_drag".into(), json!(i_drag.len()));
    stage_counts.insert("S2_I_cap".into(), json!(i_cap.len()));
    stage_counts.insert("S3_designs_evaluated".into(), json!(n_stage3));
    stage_counts.insert("S3_steady_admissible".into(), json!(n_adm_steady));
    stage_counts.insert("S4_steady_robust".into(), json!(n_robust_steady));
    stage_counts.insert("S5_designs_screened_for_stability".into(), json!(n_stab_designs));
    stage_counts.insert("S5_cap_reached".into(), json!(cap_reached));
    let n_designs =
        intakes.len() * FILTERS.len() * inp.compressors.len() * VOLUMES_M3.len() * TARGETS_PA.len() * CTRL_ORDER.len();
    let record = json!({
        "schema": SEARCH_SCHEMA,
        "dcr": "DCR-DBF1-001",
        "label": LABEL,
        "rust_commit": rust_commit,
        "prereg": {"path": PREREG_REL, "sha256": PREREG_SHA256, "lock": LOCK_REL, "lock_sha256": LOCK_SHA256},
        "thresholds": {
            "HC-01_N": inp.t12_n, "HC-02_N": inp.t25_n, "HC-09_N": inp.drag_limit_n,
            "compressor_power_limit_W": inp.p_comp_limit_w, "common_allocation_W": inp.common_allocation_w,
            "controls_thermal_allowance_W": inp.controls_allowance_w, "AL02_kg": inp.m_comp_limit_kg,
            "hall_icp_allocation_W": inp.hall_alloc_w,
        },
        "design_space": {
            "n_areas": areas().len(), "n_geometries": GEOMS.len(), "n_intakes": intakes.len(), "n_filters": FILTERS.len(),
            "n_f3_grid": inp.n_f3_grid, "n_compressors": inp.compressors.len(), "n_volumes": VOLUMES_M3.len(),
            "n_set_pressures": TARGETS_PA.len(), "n_controllers": CTRL_ORDER.len(), "n_design_vectors": n_designs,
            "n_scenarios": n_sc, "n_required_states": inp.state_ids.len(),
        },
        "coefficient_sets": coefficient_sets().iter().map(|(k, c)| json!({"id": k, "values": c.to_value()})).collect::<Vec<_>>(),
        "stage_counts": stage_counts,
        "intakes_within_drag": i_drag.iter().map(|k| intake_value(inp, &intakes[*k])).collect::<Vec<_>>(),
        "ranked_top10": ranked_summary,
        "nonclosure": nonclosure.unwrap_or(Value::Null),
        "selection": {
            "status": status,
            "design_id": sel_id,
            "design": design_summary(&space, &sel.design),
            "V_m3": sel.v_m3,
            "controller": {"Kp": sel.ctrl.0, "Ti_s": sel.ctrl.1, "f_valve_hz": F_VALVE_HZ, "authority": AUTHORITY},
            "rust_stability_screen_designs": sel.n_stability_designs,
        },
        "provenance": inp.provenance.iter().map(|(p, s)| json!({"path": p, "sha256": s})).collect::<Vec<_>>(),
    });
    Ok(SearchOut { record, spec })
}

impl Space<'_> {
    /// v2 keys M1..M9 and the id: failed non-flow criteria, out-of-domain rows, in-domain flow ratio, T12 rows, mass
    /// bin, wall area, P_set, drag, power.
    pub fn m_keys(&self, d: &Design) -> MKeys {
        let e = &d.nominal;
        (
            self.flags(e, d).n_non_flow_failed(),
            e.n_dom_fail,
            -(if e.r12_in.is_finite() { e.r12_in } else { 0.0 }),
            e.n_t12_fail,
            bin(e.m_max, 10.0),
            self.intakes[d.ie].intake.wall_area_m2(),
            -TARGETS_PA[d.target],
            self.intakes[d.ie].drag_max_n,
            e.p_el_max,
            self.design_id(d, VOLUMES_M3[0]),
        )
    }
}

pub type MKeys = (usize, usize, f64, usize, i64, f64, f64, f64, f64, String);

pub fn cmp_m(a: &MKeys, b: &MKeys) -> std::cmp::Ordering {
    a.0.cmp(&b.0)
        .then(a.1.cmp(&b.1))
        .then(cmp_f(a.2, b.2))
        .then(a.3.cmp(&b.3))
        .then(a.4.cmp(&b.4))
        .then(cmp_f(a.5, b.5))
        .then(cmp_f(a.6, b.6))
        .then(cmp_f(a.7, b.7))
        .then(cmp_f(a.8, b.8))
        .then(a.9.cmp(&b.9))
}

/// v2 stability choice: the first (V, controller) in K8 / K9 order with the fewest non-S rows (Rust screen).
fn fewest_non_s(inp: &Inputs, it: &Intake, d: &Design) -> AssessResult<(f64, (f64, f64), usize)> {
    let fc = inp.filter(FILTERS[d.filter])?;
    let plant = inp.plant(&inp.compressors[d.comp], &NOMINAL)?;
    let mut best: Option<(f64, (f64, f64), usize)> = None;
    for v in VOLUMES_M3 {
        let pl = inp.plenum(v)?;
        for (kp, ti) in CTRL_ORDER {
            let rows = stability_rows(inp, it, fc, &plant, &pl, controller(kp, ti), TARGETS_PA[d.target], false)?;
            let n = rows.iter().filter(|r| r.class != "S").count();
            if best.is_none_or(|b| n < b.2) {
                best = Some((v, (kp, ti), n));
            }
        }
    }
    best.ok_or_else(|| model_error("DCR-001 v2: no stability choice"))
}

/// Development diagnostic (never a record): the I_cap intakes with every S0 compressor, full evaluation; counts by
/// criteria pattern and the lightest design meeting C-DOMAIN, C-FLOW-T12 and C-FLOW-T25.
pub fn diagnose(inp: &Inputs, threads: usize) -> AssessResult<Value> {
    let all: Vec<Intake> =
        areas().into_iter().flat_map(|a| (0..GEOMS.len()).map(move |g| Intake { area: a, g })).collect();
    let intakes = par_map(all.len(), threads, |k| eval_intake(inp, all[k]))?;
    let i_cap: Vec<usize> =
        (0..intakes.len()).filter(|k| intakes[*k].drag_ok && intakes[*k].cap_ratio >= 1.0).collect();
    let comps: Vec<usize> = (0..inp.compressors.len()).collect();
    let ds = steady_stage(inp, &intakes, &i_cap, &comps, Mode::Full, threads)?;
    let space = Space { inp, intakes: &intakes };
    let mut pat: std::collections::BTreeMap<String, usize> = std::collections::BTreeMap::new();
    let mut best: Option<(f64, Value)> = None;
    let mut best_r12_mass: Option<(f64, Value)> = None;
    for d in &ds {
        let fl = space.flags(&d.nominal, d);
        let k = format!(
            "dom{} t12{} t25{} pow{} mass{}",
            fl.domain as u8, fl.flow_t12 as u8, fl.flow_t25 as u8, fl.power as u8, fl.mass as u8
        );
        *pat.entry(k).or_default() += 1;
        if fl.domain && fl.flow_t12 && fl.flow_t25 && fl.power && best.as_ref().map_or(true, |b| d.nominal.m_max < b.0)
        {
            best = Some((d.nominal.m_max, design_summary(&space, d)));
        }
        if fl.mass && fl.power && best_r12_mass.as_ref().map_or(true, |b| d.nominal.r12 > b.0) {
            best_r12_mass = Some((d.nominal.r12, design_summary(&space, d)));
        }
    }
    Ok(json!({
        "i_cap": i_cap.iter().map(|k| intake_value(inp, &intakes[*k])).collect::<Vec<_>>(),
        "patterns": pat,
        "lightest_flow_and_domain_design": best.map(|b| b.1),
        "best_r12_within_mass_and_power": best_r12_mass.map(|b| b.1),
    }))
}

/// Summary of one design (nominal and corners).
pub fn design_summary(space: &Space, d: &Design) -> Value {
    let inp = space.inp;
    let ie = &space.intakes[d.ie];
    let comp = &inp.compressors[d.comp];
    json!({
        "design_id_at_V0": space.design_id(d, VOLUMES_M3[0]),
        "intake": intake_value(inp, ie),
        "filter": FILTERS[d.filter],
        "compressor": {
            "id": comp.id, "N_turbo": comp.design["N_turbo"], "N_drag": comp.design["N_drag"],
            "A_turbo_m2": comp.design["A_turbo_m2"], "u_tip_turbo_mps": comp.design["u_tip_turbo_mps"],
            "rpm": comp.design["rpm"], "hub_ratio": comp.design["hub_ratio"],
        },
        "P_set_Pa": TARGETS_PA[d.target],
        "nominal": eval_value(inp, &d.nominal, ie.drag_ok),
        "r12_robust": if d.corners.is_empty() { Value::Null } else { json!(r12_robust(d)) },
        "steady_robust": if d.corners.is_empty() { Value::Null } else { json!(space.robust(d)) },
        "corners": d.corners.iter().zip(corners()).map(|(e, (k, _))| (k, eval_value(inp, e, ie.drag_ok))).collect::<Map<_, _>>(),
    })
}

// ------------------------------------------------------------------------------------------------ cross-checks

/// C-DRAG on the F1 grid areas reproduces the F1 envelope feasibility at every required state.
pub fn crosscheck_f1_drag(inp: &Inputs) -> AssessResult<Value> {
    let mut n = 0;
    for &a in &inp.up.f1.area_m2 {
        for (ld, phi) in GEOMS {
            let cand = f1_candidate_id(a, ld, phi);
            for sc in &inp.up.scenarios {
                let (mut f1_ok, mut mine) = (true, true);
                for st in &inp.state_ids {
                    f1_ok &= inp.up.record(&cand, sc, st).map_err(de)?.f1_status == "FEASIBLE_AT_STATE";
                    mine &= inp.up.drag_per_area(sc, ld, phi, st).map_err(de)?.0 * a <= inp.drag_limit_n;
                }
                if f1_ok != mine {
                    return Err(model_error(format!(
                        "DCR-001 cross-check: C-DRAG on {cand} {sc} ({mine}) differs from the F1 envelope ({f1_ok})"
                    )));
                }
                n += 1;
            }
        }
    }
    Ok(json!({
        "rule": "C-DRAG on the F1 grid areas equals the F1 envelope feasibility at every required state",
        "cells_checked": n,
        "status": "PASS"
    }))
}

/// The DBF-1 design re-evaluated here reproduces the M2 v1 per-scenario minima / in-domain counts and the per-state
/// held min / max delivered flows (classes from the pinned M2 Python reference).
pub fn crosscheck_dbf1(inp: &Inputs, repo: &Path) -> AssessResult<Value> {
    let u = &inp.dbf1.upstream;
    let g = GEOMS
        .iter()
        .position(|(ld, phi)| *ld == u.l_over_d && *phi == u.phi)
        .ok_or_else(|| model_error("DBF-1 geometry not in GEOMS"))?;
    let it = Intake { area: u.area_m2, g };
    let fc = inp.filter(&u.filter)?;
    let comp = inp.up.plant(&u.compressor).map_err(de)?;
    let pl = inp.plenum(u.v_m3)?;
    let m2 = jread(repo, M2_REL, M2_SHA256)?;
    let py = jread(repo, M2_PY_REL, M2_PY_SHA256)?;
    let mut cls: HashMap<(String, String), String> = HashMap::new();
    for r in py["rows"].as_array().ok_or_else(|| model_error("M2 python rows"))? {
        cls.insert(
            (r["scenario"].as_str().unwrap_or("").into(), r["state_id"].as_str().unwrap_or("").into()),
            r["class"].as_str().unwrap_or("").into(),
        );
    }
    let ups = m2["upstream_scenarios"].as_array().ok_or_else(|| model_error("M2 upstream_scenarios"))?;
    let mut held: Vec<Vec<f64>> = vec![vec![]; inp.state_ids.len()];
    for (si, sc) in inp.up.scenarios.iter().enumerate() {
        let side = intake_side(&inp.records(&it, si), fc, 1.0)?;
        let sw = steady_sweep(&side, comp, &pl, &inp.up.materials, &[u.p_set_pa], None)?;
        let mut n_in = 0;
        let mut rerun_min = f64::INFINITY;
        for v in &sw.mdot_total_kgps {
            rerun_min = rerun_min.min(*v);
        }
        for (i, &fi) in inp.req_f1.iter().enumerate() {
            let ok = sw.in_domain[fi] && sw.bits[fi] == 0;
            if ok {
                n_in += 1;
                if cls.get(&(sc.clone(), inp.state_ids[i].clone())).map(String::as_str) == Some("S") {
                    held[i].push(sw.mdot_total_kgps[fi]);
                }
            }
        }
        let e = ups.iter().find(|x| x["scenario"].as_str() == Some(sc)).ok_or_else(|| model_error("M2 scenario"))?;
        if e["n_in_domain_states"].as_u64() != Some(n_in as u64) || e["rerun_min_kg_s"].as_f64() != Some(rerun_min) {
            return Err(model_error(format!(
                "DCR-001 cross-check: DBF-1 {sc}: in-domain {n_in} / min {rerun_min:e} differ from M2 v1"
            )));
        }
    }
    let states = m2["states"].as_array().ok_or_else(|| model_error("M2 states"))?;
    for (i, st) in inp.state_ids.iter().enumerate() {
        let s = states
            .iter()
            .find(|x| x["state_id"].as_str() == Some(st))
            .ok_or_else(|| model_error(format!("M2 state {st}")))?;
        let mm = &s["air_dbf1"]["mdot_del_held_min_max_kg_s"];
        let want: Option<(f64, f64)> = mm.as_array().and_then(|a| Some((a.first()?.as_f64()?, a.get(1)?.as_f64()?)));
        let got = if held[i].is_empty() {
            None
        } else {
            Some((
                held[i].iter().copied().fold(f64::INFINITY, f64::min),
                held[i].iter().copied().fold(f64::NEG_INFINITY, f64::max),
            ))
        };
        if want != got {
            return Err(model_error(format!("DCR-001 cross-check: DBF-1 held flow at {st}: {got:?} != M2 {want:?}")));
        }
    }
    Ok(
        json!({"rule": "DBF-1 re-evaluated by this harness reproduces M2 v1 (per-scenario rerun minimum and in-domain count; per-state held delivered min / max)", "status": "PASS"}),
    )
}

/// DBF-1 evaluated with the DCR-001 criteria (comparison row).
pub fn dbf1_row(inp: &Inputs) -> AssessResult<Value> {
    let u = &inp.dbf1.upstream;
    let g = GEOMS.iter().position(|(ld, phi)| *ld == u.l_over_d && *phi == u.phi).ok_or_else(|| model_error("geom"))?;
    let ie = eval_intake(inp, Intake { area: u.area_m2, g })?;
    let fc = inp.filter(&u.filter)?;
    let plant = inp.up.plant(&u.compressor).map_err(de)?;
    let pl = inp.plenum(u.v_m3)?;
    let sd = sides(inp, &ie.intake, fc)?;
    let ev = eval_triple(inp, &ie, &sd, plant, &pl, Mode::Full)?;
    let j = TARGETS_PA.iter().position(|t| *t == u.p_set_pa).ok_or_else(|| model_error("DBF-1 P_set not on grid"))?;
    Ok(
        json!({"design_id": u.design_id, "intake": intake_value(inp, &ie), "nominal": eval_value(inp, &ev[j], ie.drag_ok)}),
    )
}

// ------------------------------------------------------------------------------------------------ P6 / P9 information

/// Values relayed by the coordinator from the P6 power ledger and the P9 host-drag ICD lane (2026-10-08; files
/// docs/closure/power/power_ledger_v1.json and docs/closure/icd/host_drag_cda_envelope_v1.json pending on the
/// integration branch). Information only: the preregistered criteria were locked before they arrived.
pub const P6_HALL_DISCHARGE_CEILING_W: f64 = 911.0;
pub const P6_COMPRESSOR_HEADROOM_W: f64 = 231.0;
pub const P9_HOST_CDA_180KM_M2: f64 = 0.221;

/// Intake-face drag (max over scenarios) of an intake at every required state, N.
fn intake_drag_by_state(inp: &Inputs, it: &Intake) -> AssessResult<Vec<(f64, f64)>> {
    inp.state_ids
        .iter()
        .map(|st| {
            let mut lo = f64::INFINITY;
            let mut hi = f64::NEG_INFINITY;
            for sc in &inp.up.scenarios {
                let d = inp.up.drag_per_area(sc, it.ld(), it.phi(), st).map_err(de)?.0 * it.area;
                lo = lo.min(d);
                hi = hi.max(d);
            }
            Ok((lo, hi))
        })
        .collect()
}

/// The coordinator-relayed P6 / P9 checks of the selected design (information, never a criterion of v1).
pub fn p6_p9_information(inp: &Inputs, spec: &Value) -> AssessResult<Value> {
    let (it, fc, plant, pl, p_set, _) = spec_objects(inp, spec, &NOMINAL)?;
    let u = &inp.dbf1.upstream;
    let g1 = GEOMS.iter().position(|x| *x == (u.l_over_d, u.phi)).ok_or_else(|| model_error("geom"))?;
    let d_sel = intake_drag_by_state(inp, &it)?;
    let d_dbf1 = intake_drag_by_state(inp, &Intake { area: u.area_m2, g: g1 })?;
    let alt = |i: usize| inp.unit[0][0][inp.req_f1[i]].alt_km;
    let mut over12 = vec![];
    for i in 0..inp.state_ids.len() {
        if d_dbf1[i].1 > inp.t12_n {
            over12.push(json!({
                "state_id": inp.state_ids[i],
                "dbf1_intake_drag_mN_min_max_over_scenarios": [d_dbf1[i].0 * 1e3, d_dbf1[i].1 * 1e3],
                "dbf1_above_12mN_in_every_scenario": d_dbf1[i].0 > inp.t12_n,
                "selected_intake_drag_mN_min_max_over_scenarios": [d_sel[i].0 * 1e3, d_sel[i].1 * 1e3],
            }));
        }
    }
    let n_sel_over12_any = d_sel.iter().filter(|d| d.1 > inp.t12_n).count();
    let n_sel_over12_every = d_sel.iter().filter(|d| d.0 > inp.t12_n).count();
    // Host C_D A left under the 25 mN statewise limit at the 180 km states.
    let (mut cda_min, mut cda_at, mut all_hold) = (f64::INFINITY, 0usize, true);
    for i in 0..inp.state_ids.len() {
        if alt(i) != 180.0 {
            continue;
        }
        let left = (inp.t25_n - d_sel[i].1) / inp.q_pa[i];
        if left < cda_min {
            (cda_min, cda_at) = (left, i);
        }
        all_hold &= d_sel[i].1 + inp.q_pa[i] * P9_HOST_CDA_180KM_M2 <= inp.t25_n;
    }
    // Flow margin against the necessary flow at the P6 discharge-power ceiling (electric only; and with q_max A).
    let (mut r_el, mut r_q) = (f64::INFINITY, f64::INFINITY);
    let (mut at_el, mut at_q) = ((0, 0), (0, 0));
    for (si, _) in inp.up.scenarios.iter().enumerate() {
        let side = intake_side(&inp.records(&it, si), fc, 1.0)?;
        let sw = steady_sweep(&side, &plant, &pl, &inp.up.materials, &[p_set], None)?;
        for (i, &fi) in inp.req_f1.iter().enumerate() {
            let md = if sw.bits[fi] == 0 && sw.in_domain[fi] { sw.mdot_total_kgps[fi] } else { 0.0 };
            let need_el = abep_mission::conservation_bounds::mdot_required(inp.t12_n, P6_HALL_DISCHARGE_CEILING_W)?;
            let need_q = abep_mission::conservation_bounds::mdot_required(
                inp.t12_n,
                P6_HALL_DISCHARGE_CEILING_W + inp.q_max_w_m2[i] * it.area,
            )?;
            if md / need_el < r_el {
                (r_el, at_el) = (md / need_el, (si, i));
            }
            if md / need_q < r_q {
                (r_q, at_q) = (md / need_q, (si, i));
            }
        }
    }
    let sc = &inp.up.scenarios;
    Ok(json!({
        "source": "coordinator relay 2026-10-08 of the P6 power ledger (docs/closure/power/power_ledger_v1.json) and the P9 host-drag ICD lane (docs/closure/icd/host_drag_cda_envelope_v1.json); information only, the v1 criteria were locked before",
        "intake_drag_vs_12mN": {
            "dbf1_states_with_intake_drag_above_12mN": over12,
            "selected_states_with_intake_drag_above_12mN_in_some_scenario": n_sel_over12_any,
            "selected_states_with_intake_drag_above_12mN_in_every_scenario": n_sel_over12_every,
        },
        "host_cda_at_180km": {
            "IR-HOST-DRAG-01_governing_m2": P9_HOST_CDA_180KM_M2,
            "selected_min_allowable_host_CDA_under_25mN_m2": cda_min,
            "at_state": inp.state_ids[cda_at],
            "25mN_statewise_holds_with_host_0.221_at_every_180km_state": all_hold,
        },
        "flow_vs_911W_discharge_ceiling": {
            "mdot_req_T12_at_911W_electric_kg_s": abep_mission::conservation_bounds::mdot_required(inp.t12_n, P6_HALL_DISCHARGE_CEILING_W)?,
            "r12_worst_electric_only": r_el,
            "at": {"scenario": sc[at_el.0], "state_id": inp.state_ids[at_el.1]},
            "r12_worst_with_q_max_A": r_q,
            "at_with_q_max_A": {"scenario": sc[at_q.0], "state_id": inp.state_ids[at_q.1]},
        },
        "compressor_power_vs_231W_headroom": {"headroom_W": P6_COMPRESSOR_HEADROOM_W},
    }))
}

// ------------------------------------------------------------------------------------------------ record

/// Detailed evaluation of the selected design under one coefficient set (scenario table, operating-point extremes).
pub fn detail(inp: &Inputs, spec: &Value, k: &Coeffs) -> AssessResult<Value> {
    let (it, fc, plant, pl, p_set, _) = spec_objects(inp, spec, k)?;
    let ie = eval_intake(inp, it)?;
    let mut rows = Map::new();
    let (mut kmin, mut cr_min, mut cr_max, mut p_pneu_max) = (f64::INFINITY, f64::INFINITY, f64::NEG_INFINITY, 0.0f64);
    for (si, sc) in inp.up.scenarios.iter().enumerate() {
        let recs = inp.records(&it, si);
        let side = intake_side(&recs, fc, 1.0)?;
        let sw = steady_sweep(&side, &plant, &pl, &inp.up.materials, &[p_set], None)?;
        let (mut mmin, mut at) = (f64::INFINITY, 0usize);
        let (mut r12, mut r25best, mut n_ood) = (f64::INFINITY, 0.0f64, 0usize);
        for (i, &fi) in inp.req_f1.iter().enumerate() {
            let ok = sw.bits[fi] == 0 && sw.in_domain[fi];
            if !ok {
                n_ood += 1;
                r12 = 0.0;
                continue;
            }
            let md = sw.mdot_total_kgps[fi];
            if md < mmin {
                (mmin, at) = (md, i);
            }
            r12 = r12.min(md / ie.req12[i]);
            r25best = r25best.max(md / ie.req25[i]);
            let chain = Chain { intake: recs[fi].clone(), filt: fc.clone(), plant: plant.clone(), plenum: pl.clone() };
            let op = steady_operating_point(&chain, &inp.up.materials, p_set, 1.0, 1.0)?;
            if let Some(x) = op["compressor"]["K_min"].as_f64() {
                kmin = kmin.min(x);
            }
            if let Some(p2) = op["compressor_inlet_P_Pa"].as_f64() {
                cr_min = cr_min.min(p_set / p2);
                cr_max = cr_max.max(p_set / p2);
            }
            // Pneumatic (isothermal) compression power sum_s mdot_s kT/m_s ln(p3_s / p2_s) (EV-05 cross-check).
            let mut pp = 0.0;
            for s in ["O", "N2", "O2"] {
                let g = op["mdot_compressor_gross_kgps"][s].as_f64().unwrap_or(0.0);
                let p3 = op["offered"]["p_s_Pa"][s].as_f64().unwrap_or(f64::NAN);
                let p2 = op["compressor_inlet_p_s_Pa"][s].as_f64().unwrap_or(f64::NAN);
                let kt_m = abep_types::constants::K_B * T_CHAIN_K / abep_types::constants::species_mass(s)?;
                if g > 0.0 && p3 > 0.0 && p2 > 0.0 {
                    pp += g * kt_m * (p3 / p2).ln();
                }
            }
            p_pneu_max = p_pneu_max.max(pp);
        }
        rows.insert(
            sc.clone(),
            json!({
                "mdot_delivered_min_kg_s": fin(mmin), "at_state": inp.state_ids[at],
                "r12_worst": fin(r12), "k12_worst": if r12 > 0.0 { fin(1.0 / r12) } else { Value::Null },
                "best_T25_ratio": r25best, "rows_out_of_domain": n_ood,
            }),
        );
    }
    Ok(json!({
        "by_scenario": rows,
        "gaede_K_min": fin(kmin),
        "active_compression_ratio_P_set_over_inlet_min_max": [fin(cr_min), fin(cr_max)],
        "pneumatic_power_max_W": p_pneu_max,
        "EV05_power_floor_at_1pct_W": p_pneu_max / 0.01,
    }))
}

type SpecObjects<'a> = (Intake, &'a FilterCase, CompressorPlant, Plenum, f64, Controller);

fn spec_objects<'a>(inp: &'a Inputs, spec: &Value, k: &Coeffs) -> AssessResult<SpecObjects<'a>> {
    let area = f(&spec["intake"]["area_m2"], "spec area")?;
    let (ld, phi) = (f(&spec["intake"]["L_over_d"], "spec L/d")?, f(&spec["intake"]["phi"], "spec phi")?);
    let g = GEOMS.iter().position(|x| *x == (ld, phi)).ok_or_else(|| model_error("spec geometry"))?;
    let fc = inp.filter(spec["filter"].as_str().ok_or_else(|| model_error("spec filter"))?)?;
    let cid = spec["compressor"]["id"].as_str().ok_or_else(|| model_error("spec compressor"))?;
    let comp = inp.compressors.iter().find(|c| c.id == cid).ok_or_else(|| model_error("spec compressor not in S0"))?;
    let plant = inp.plant(comp, k)?;
    let pl = inp.plenum(f(&spec["V_m3"], "spec V")?)?;
    let c = &spec["controller"];
    let ctrl = Controller {
        kp: f(&c["Kp"], "Kp")?,
        ti_s: f(&c["Ti_s"], "Ti")?,
        f_valve_hz: f(&c["f_valve_hz"], "f_valve")?,
        authority: f(&c["authority"], "authority")?,
    };
    Ok((Intake { area, g }, fc, plant, pl, f(&spec["P_set_Pa"], "spec P_set")?, ctrl))
}

/// The final record: the committed search record and spec (pinned), the governed Python stability reference (pinned)
/// with Rust R2 agreement on every row, the selected design's detail under every coefficient set, the DBF-1
/// comparison row and the cross-checks.
#[allow(clippy::too_many_arguments)]
pub fn record(
    inp: &Inputs,
    repo: &Path,
    search_rel: &str,
    search_sha: &str,
    spec_rel: &str,
    spec_sha: &str,
    py_rel: &str,
    py_sha: &str,
    threads: usize,
) -> AssessResult<Value> {
    let srch = jread(repo, search_rel, search_sha)?;
    let spec = jread(repo, spec_rel, spec_sha)?;
    let py = jread(repo, py_rel, py_sha)?;
    if srch["schema"].as_str() != Some(SEARCH_SCHEMA) || spec["schema"].as_str() != Some(SPEC_SCHEMA) {
        return Err(model_error("DCR-001 record: search / spec schema"));
    }
    if py["schema"].as_str() != Some(PY_SCHEMA) || py["spec"]["sha256"].as_str() != Some(spec_sha) {
        return Err(model_error("DCR-001 record: Python reference schema or spec pin differs"));
    }
    if srch["selection"]["design_id"] != spec["design_id"] {
        return Err(model_error("DCR-001 record: spec is not the search selection"));
    }
    let sets = coefficient_sets();
    // R2: Rust classes on every row of every coefficient set equal the Python reference.
    let mut py_rows: HashMap<(String, String, String), (String, Vec<String>)> = HashMap::new();
    for r in py["rows"].as_array().ok_or_else(|| model_error("Python rows"))? {
        let s = |k: &str| r[k].as_str().unwrap_or("").to_string();
        let kinds = r["events"]
            .as_array()
            .map(|a| a.iter().map(|e| e["eq"].as_str().unwrap_or("").to_string()).collect())
            .unwrap_or_default();
        if py_rows.insert((s("coefficient_set"), s("scenario"), s("state_id")), (s("class"), kinds)).is_some() {
            return Err(model_error("Python reference: duplicate row"));
        }
    }
    let rust_sets = par_map(sets.len(), threads, |k| {
        let (it, fc, plant, pl, p_set, ctrl) = spec_objects(inp, &spec, &sets[k].1)?;
        stability_rows(inp, &it, fc, &plant, &pl, ctrl, p_set, false)
    })?;
    let mut stab = Map::new();
    let (mut n_rows, mut n_agree) = (0usize, 0usize);
    for ((name, _), rows) in sets.iter().zip(&rust_sets) {
        for r in rows {
            let key = (name.clone(), inp.up.scenarios[r.scenario].clone(), inp.state_ids[r.state].clone());
            let (pc, pk) = py_rows.get(&key).ok_or_else(|| model_error(format!("Python reference: no row {key:?}")))?;
            n_rows += 1;
            let rk: Vec<String> = r.kinds.iter().map(|x| x.to_string()).collect();
            if pc != r.class || *pk != rk {
                return Err(model_error(format!(
                    "DCR-001 R2: Rust {} {rk:?} differs from the Python reference {pc} {pk:?} at {key:?}",
                    r.class
                )));
            }
            n_agree += 1;
        }
        stab.insert(name.clone(), class_counts(rows));
    }
    if n_rows != py_rows.len() {
        return Err(model_error("DCR-001 R2: the Python reference has rows the Rust evaluation does not"));
    }
    let nominal_all_s = rust_sets[0].iter().all(|r| r.class == "S");
    let corners_all_s = rust_sets[1..].iter().all(|rows| rows.iter().all(|r| r.class == "S"));
    let details = par_map(sets.len(), threads, |k| detail(inp, &spec, &sets[k].1))?;
    let mut det = Map::new();
    for ((name, _), d) in sets.iter().zip(details) {
        det.insert(name.clone(), d);
    }
    let base = srch["selection"]["status"].as_str().unwrap_or("").to_string();
    let status = match (base.as_str(), nominal_all_s, corners_all_s) {
        (_, false, _) => "NOT_ADMISSIBLE".to_string(),
        ("ADMISSIBLE_ROBUST", true, false) => "ADMISSIBLE_CONDITIONAL_ON_COMPRESSOR_COEFFICIENTS".to_string(),
        (b, _, _) => b.to_string(),
    };
    let f1x = crosscheck_f1_drag(inp)?;
    let d1x = crosscheck_dbf1(inp, repo)?;
    Ok(json!({
        "schema": RECORD_SCHEMA,
        "dcr": "DCR-DBF1-001",
        "label": LABEL,
        "inputs": {
            "search": {"path": search_rel, "sha256": search_sha},
            "spec": {"path": spec_rel, "sha256": spec_sha},
            "python_stability_reference": {"path": py_rel, "sha256": py_sha, "environment": py["environment"].clone()},
        },
        "search": srch,
        "selected_design": {
            "design_id": spec["design_id"].clone(),
            "status": status,
            "stability": {
                "rule": "governed Python reference (A9.34) with Rust R2 agreement on every row",
                "rows": n_rows, "rows_agreeing": n_agree,
                "class_counts_by_coefficient_set": stab,
                "nominal_all_S": nominal_all_s, "corners_all_S": corners_all_s,
            },
            "detail_by_coefficient_set": det,
        },
        "dbf1_comparison": dbf1_row(inp)?,
        "p6_p9_information": p6_p9_information(inp, &spec)?,
        "cross_checks": {"f1_drag": f1x, "dbf1_vs_m2": d1x, "steady_independent_of_V": "asserted by the crate tests (WALL-G0)"},
    }))
}

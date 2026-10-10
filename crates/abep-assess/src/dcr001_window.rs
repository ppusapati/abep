//! DCR-DBF1-001 amendment v3 (`docs/baseline/DCR-001/dcr001_eval_prereg_v3.json`, lock `dcr001_eval_prereg_lock_v3.json`;
//! owner decision A9.39 items 2 / 3): variable effective capture, the AIR operating free-stream-flux window and the
//! altitude schedule inside 180-230 km.
//!
//! The steady chain depends on (geometry, filter, compressor, scenario, state, A_eff) only, so it is evaluated once per
//! distinct effective area A_eff = j A_max / N of the grid ([`aeff_grid`]) on the v1 harness path (F1 unit records x
//! A_eff, `intake_side`, `steady_sweep`). Rows that cannot satisfy the operating conditions (captured flow below the
//! favourable sustained necessary flow, or total drag above the limit at A_max = A_eff) are not swept: delivered <=
//! captured by mass conservation of the chain, and both bounds are the favourable ends. Per design (geometry, A_max, N,
//! filter, compressor, P_set) the smallest admissible open-segment count is the operating point of each (state,
//! scenario); a state is served when all 10 scenarios have one; the window is the best admissible run of served states
//! in flux order. No requirement number is a literal here except the registered closed-shutter drag bound.

use crate::dcr001::{coefficient_sets, Coeffs, Intake};
use crate::dcr001::{
    controller, de, f, jread, par_map, Comp, Inputs, CTRL_ORDER, FILTERS, GEOMS, NOMINAL, TARGETS_PA, VOLUMES_M3, WALL,
};
use crate::error::{model_error, AssessError, AssessResult};
use abep_gaspath::plenum_feed::{
    f1_candidate_id, intake_side, solve_pressures, steady_operating_point, steady_sweep, Chain, CompressorPlant,
    FilterCase, IntakeState, Node, Plenum, Sp3,
};
use abep_gaspath::pyops;
use abep_gaspath::pyops::py_format_g;
use abep_gaspath::stability::{stability_class_events, Controller, WINDOW_S};
use abep_mission::conservation_bounds::mdot_required;
use abep_provenance::read_verified;
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

pub const V3_REL: &str = "docs/baseline/DCR-001/dcr001_eval_prereg_v3.json";
pub const V3_SHA256: &str = "c79ea6c110f46799c5c3aaab1b091519d13ee2bf7b7c03112236de05f8c4dbb9";
pub const V3_MD_REL: &str = "docs/baseline/DCR-001/DCR001_EVAL_PREREG_v3.md";
pub const V3_MD_SHA256: &str = "5e90dd4ef75674a9b582a40b0bd5126a6d1e51ba54629daef38399af4548c537";
pub const V3_LOCK_REL: &str = "docs/baseline/DCR-001/dcr001_eval_prereg_lock_v3.json";
pub const V3_LOCK_SHA256: &str = "65f276e8adcd6aefb63f04bf24067cc181f93c460ae9c56c82a16d5d0094649b";
pub const P6_REL: &str = "docs/closure/power/power_ledger_v1.json";
pub const P6_SHA256: &str = "23e3366967f3d04d332564f95e6f4ddb3f4aa3b3d774cb6e09b5aa6a9138472a";
pub const HOST_REL: &str = "docs/closure/icd/host_drag_cda_envelope_v1.json";
pub const HOST_SHA256: &str = "9c83354100795212bbe555968f502c20c38bf325c21968049cafd5699a5e08f9";

pub const SEARCH_SCHEMA: &str = "abep_dcr001_window_search_v1";
pub const SPEC_SCHEMA: &str = "abep_dcr001_window_stability_spec_v1";
pub const PY_SCHEMA: &str = "abep_dcr001_window_stability_python_reference_v1";
pub const RECORD_SCHEMA: &str = "abep_dcr001_window_record_v1";
pub const LABEL: &str = "ACTUAL_DESIGN_EVALUATION / PARAMETRIC / NOT_VALIDATED / NOT_A_PERFORMANCE_PREDICTION";

/// Physical maximum aperture grid (F1 frontal-area design grid F1-P-16), m^2.
pub const A_MAX: [f64; 6] = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5];
/// Segment counts: 1 = VC-0 fixed aperture; 2 / 4 / 8 = VC-1 segmented frontal shutter.
pub const N_SEG: [usize; 4] = [1, 2, 4, 8];
/// Closed-shutter drag per unit closed area / q: specular normal flat plate bound 4 (1 + 1/(2 S^2)), S >= 5.8.
pub const C_CLOSED: f64 = 4.1;
pub const STABILITY_CAP: usize = 200;
/// Planning anode efficiencies (information only; assumed, level 7).
pub const ETA_PLAN: [f64; 3] = [0.10, 0.20, 0.30];
/// Information: V_d bound with O+ at 350 V (fixed_intake_window_v1).
pub const VD_MAX_V: f64 = 350.0;
pub const HOST_SENSITIVITY_M2: [f64; 2] = [0.0, 1.1];
pub const ALTITUDES_KM: [f64; 4] = [180.0, 195.0, 215.0, 230.0];

/// The 27 distinct effective areas j A_max / N, ascending.
pub fn aeff_grid() -> Vec<f64> {
    let mut v: Vec<f64> = vec![];
    for a in A_MAX {
        for n in N_SEG {
            for j in 1..=n {
                let x = a * j as f64 / n as f64;
                if !v.iter().any(|y| (y - x).abs() < 1e-12) {
                    v.push(x);
                }
            }
        }
    }
    v.sort_by(|a, b| a.partial_cmp(b).expect("finite"));
    v
}

/// The preregistration amendment v3 identity (json, md, lock; the lock names both files and the v1 / v2 locks).
pub fn verify_prereg_v3(repo: &Path) -> AssessResult<()> {
    read_verified(&repo.join(V3_REL), V3_SHA256)?;
    read_verified(&repo.join(V3_MD_REL), V3_MD_SHA256)?;
    let lock = jread(repo, V3_LOCK_REL, V3_LOCK_SHA256)?;
    for (k, want) in [("dcr001_eval_prereg_v3.json", V3_SHA256), ("DCR001_EVAL_PREREG_v3.md", V3_MD_SHA256)] {
        if lock["files"][k].as_str() != Some(want) {
            return Err(model_error(format!("{V3_LOCK_REL}: files.{k} != {want}")));
        }
    }
    if lock["v1_lock"]["sha256"].as_str() != Some(crate::dcr001::LOCK_SHA256) {
        return Err(model_error(format!("{V3_LOCK_REL}: v1 lock differs")));
    }
    if lock["dbf1_1_lock"]["sha256"].as_str() != Some(abep_config::baseline::DBF1_1_LOCK_SHA256) {
        return Err(model_error(format!("{V3_LOCK_REL}: DBF-1.1 lock differs")));
    }
    Ok(())
}

// ------------------------------------------------------------------------------------------------ inputs

/// Flow requirement used to decide an operating point.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Req {
    /// A4 K-MDOT-REQ at the P6 ceiling + q_max A_eff (governing).
    Necessary,
    /// Information: T^2 / (2 eta P_d_max_1350) at a planning anode efficiency.
    Plan(f64),
    /// Information: T / v_max(O+, V_d,max).
    VdBound,
}

/// Window-evaluation context over the v1 inputs.
pub struct WInputs<'a> {
    pub inp: &'a Inputs,
    pub aeff: Vec<f64>,
    /// rho V of each required state (window coordinate), kg m^-2 s^-1.
    pub phi: Vec<f64>,
    pub phi_adm: Vec<f64>,
    pub cond: Vec<usize>,
    pub conds: Vec<String>,
    pub alt_km: Vec<f64>,
    /// Altitude nodes (condition, altitude, required-state indices).
    pub nodes: Vec<(usize, f64, Vec<usize>)>,
    /// Required-state indices sorted by (phi, id).
    pub order: Vec<usize>,
    /// The lowest- and highest-flux state of every node (the node-extreme screen).
    pub extremes: Vec<bool>,
    pub pos: Vec<usize>,
    pub cda_host_m2: f64,
    pub pd1350_ref_w: f64,
    pub pd1500_ref_w: f64,
    pub cp_nom_w: f64,
    pub dpd_per_w: f64,
    pub headroom_w: f64,
    /// [geometry][scenario][required state]: intake-face drag per unit area (N/m^2) and captured flow per unit area.
    pub dpa: Vec<Vec<Vec<f64>>>,
    pub cap: Vec<Vec<Vec<f64>>>,
    /// Compressors of C_mass (v1 S0 mass lower bound <= AL-02) and all S0 compressors.
    pub c_mass: Vec<usize>,
    pub v_max_o: f64,
    pub provenance: Vec<(String, String)>,
}

fn parse_state(id: &str) -> AssessResult<(String, f64)> {
    let p: Vec<&str> = id.split(':').collect();
    if p.len() < 3 || !p[2].starts_with("alt") {
        return Err(model_error(format!("state id {id}: no condition / altitude")));
    }
    let alt: f64 = p[2][3..].parse().map_err(|_| model_error(format!("state id {id}: altitude")))?;
    Ok((p[1].to_string(), alt))
}

pub fn gather_window<'a>(repo: &Path, inp: &'a Inputs) -> AssessResult<WInputs<'a>> {
    verify_prereg_v3(repo)?;
    let n = inp.state_ids.len();
    let atm = abep_mission::intake_drag::EnvelopeAtmospheres::load(repo)?;
    let mut phi = vec![];
    for s in &inp.state_ids {
        let a = atm.get(s).ok_or_else(|| model_error(format!("no envelope atmosphere {s}")))?;
        phi.push(a.rho * a.v);
    }
    let a4 = jread(repo, crate::dcr001::A4_REL, crate::dcr001::A4_SHA256)?;
    let mut adm: HashMap<String, f64> = HashMap::new();
    for s in a4["states"].as_array().ok_or_else(|| model_error("A4 states"))? {
        adm.insert(s["state_id"].as_str().unwrap_or("").to_string(), f(&s["Phi_adm_kg_m2_s"], "Phi_adm")?);
    }
    let phi_adm = inp
        .state_ids
        .iter()
        .map(|s| adm.get(s).copied().ok_or_else(|| model_error("A4 Phi_adm")))
        .collect::<AssessResult<Vec<f64>>>()?;
    let mut conds: Vec<String> = vec![];
    let mut cond = vec![];
    let mut alt_km = vec![];
    for s in &inp.state_ids {
        let (c, h) = parse_state(s)?;
        if !conds.contains(&c) {
            conds.push(c.clone());
        }
        alt_km.push(h);
        cond.push(c);
    }
    conds.sort();
    let cond: Vec<usize> = cond.iter().map(|c| conds.iter().position(|x| x == c).expect("cond")).collect();
    let mut nodes = vec![];
    for (ci, _) in conds.iter().enumerate() {
        for h in ALTITUDES_KM {
            let st: Vec<usize> = (0..n).filter(|&i| cond[i] == ci && alt_km[i] == h).collect();
            if st.is_empty() {
                return Err(model_error(format!("no required state at node {} / {h} km", conds[ci])));
            }
            nodes.push((ci, h, st));
        }
    }
    if (0..n).any(|i| !ALTITUDES_KM.contains(&alt_km[i])) {
        return Err(model_error("a required state is off the registered altitude nodes"));
    }
    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by(|&a, &b| {
        phi[a].partial_cmp(&phi[b]).expect("finite").then_with(|| inp.state_ids[a].cmp(&inp.state_ids[b]))
    });
    let mut pos = vec![0; n];
    for (k, &i) in order.iter().enumerate() {
        pos[i] = k;
    }
    let mut extremes = vec![false; n];
    for (_, _, st) in &nodes {
        let lo = st.iter().copied().min_by_key(|&i| pos[i]).expect("node");
        let hi = st.iter().copied().max_by_key(|&i| pos[i]).expect("node");
        extremes[lo] = true;
        extremes[hi] = true;
    }
    // P6 ceilings and compressor headroom; IR-HOST-DRAG-01 governing value.
    let p6 = jread(repo, P6_REL, P6_SHA256)?;
    let p12 = p6["points"]
        .as_array()
        .and_then(|a| a.iter().find(|p| p["id"].as_str() == Some("P-12")))
        .ok_or_else(|| model_error("P6 point P-12"))?;
    let pd1350_ref_w = f(&p12["P_d_max_W"]["design_allocation_1350"], "P6 P_d_max 1350")?;
    let pd1500_ref_w = f(&p12["P_d_max_W"]["rfp_1500_supremum"], "P6 P_d_max 1500")?;
    let dpd_per_w = f(&p6["compressor_headroom"]["dPd_max_per_W_compressor"], "P6 dPd/dP_comp")?;
    let headroom_w = f(&p6["compressor_headroom"]["inside_common_300W_W"], "P6 headroom")?;
    let cp = p6["terms"]
        .as_array()
        .and_then(|a| a.iter().find(|t| t["id"].as_str() == Some("CP-NOM")))
        .ok_or_else(|| model_error("P6 term CP-NOM"))?;
    let cp_nom_w = f(&cp["value"], "CP-NOM")?;
    let host = jread(repo, HOST_REL, HOST_SHA256)?;
    let cda_host_m2 =
        f(&host["results"]["governing"]["T25_capability"]["CDA_host_max_m2_all_states_unfavourable"], "host C_D A")?;
    // Unit-area drag and capture per geometry / scenario / required state.
    let mut dpa = vec![];
    let mut cap = vec![];
    for (g, (ld, ph)) in GEOMS.into_iter().enumerate() {
        let (mut dg, mut cg) = (vec![], vec![]);
        for (si, sc) in inp.up.scenarios.iter().enumerate() {
            let (mut ds, mut cs) = (vec![], vec![]);
            for (i, st) in inp.state_ids.iter().enumerate() {
                ds.push(inp.up.drag_per_area(sc, ld, ph, st).map_err(de)?.0);
                let u = &inp.unit[g][si][inp.req_f1[i]];
                cs.push(u.mdot_fwd_kgps[0] + u.mdot_fwd_kgps[1] + u.mdot_fwd_kgps[2]);
            }
            dg.push(ds);
            cg.push(cs);
        }
        dpa.push(dg);
        cap.push(cg);
    }
    let zero = [0.0; 3];
    let mut c_mass = vec![];
    for (k, c) in inp.compressors.iter().enumerate() {
        if inp.plant(c, &NOMINAL)?.cascade(&inp.up.materials, &zero, &zero)?.mass_kg <= inp.m_comp_limit_kg {
            c_mass.push(k);
        }
    }
    let e = 1.602176634e-19;
    let amu = 1.66053906660e-27;
    let v_max_o = (2.0 * e * VD_MAX_V / (15.999 * amu)).sqrt();
    let mut provenance = inp.provenance.clone();
    for (p, s) in [
        (V3_REL, V3_SHA256),
        (V3_MD_REL, V3_MD_SHA256),
        (V3_LOCK_REL, V3_LOCK_SHA256),
        (P6_REL, P6_SHA256),
        (HOST_REL, HOST_SHA256),
        (abep_config::baseline::DBF1_1_LOCK_REL, abep_config::baseline::DBF1_1_LOCK_SHA256),
    ] {
        provenance.push((p.into(), s.into()));
    }
    Ok(WInputs {
        inp,
        aeff: aeff_grid(),
        phi,
        phi_adm,
        cond,
        conds,
        alt_km,
        nodes,
        order,
        extremes,
        pos,
        cda_host_m2,
        pd1350_ref_w,
        pd1500_ref_w,
        cp_nom_w,
        dpd_per_w,
        headroom_w,
        dpa,
        cap,
        c_mass,
        v_max_o,
        provenance,
    })
}

impl WInputs<'_> {
    /// The smallest registered aperture with A_eff = j A_max / N for some registered N.
    pub fn a_max_min(&self, a: f64) -> f64 {
        A_MAX
            .into_iter()
            .find(|am| N_SEG.iter().any(|&n| (1..=n).any(|j| (am * j as f64 / n as f64 - a).abs() < 1e-12)))
            .expect("A_eff on the grid")
    }

    pub fn aidx(&self, a: f64) -> usize {
        self.aeff.iter().position(|x| (x - a).abs() < 1e-12).expect("A_eff on the grid")
    }

    /// Hall discharge ceilings with the compressor at `p_comp` (P6: 0.9 W per compressor W above CP-NOM).
    pub fn pd1350(&self, p_comp: f64) -> f64 {
        self.pd1350_ref_w - self.dpd_per_w * (p_comp - self.cp_nom_w)
    }
    pub fn pd1500(&self, p_comp: f64) -> f64 {
        self.pd1500_ref_w - self.dpd_per_w * (p_comp - self.cp_nom_w)
    }

    /// Total drag at state i, scenario si for (geometry g, A_max, A_eff), N.
    pub fn d_tot(&self, g: usize, si: usize, i: usize, a_max: f64, a_eff: f64, cda_host: f64) -> f64 {
        let q = self.inp.q_pa[i];
        self.dpa[g][si][i] * a_eff + C_CLOSED * q * (a_max - a_eff) + q * cda_host
    }

    /// Sustained flow requirement for thrust t at state i (A_eff, compressor power).
    pub fn req(&self, r: Req, t: f64, i: usize, a_eff: f64, p_comp: f64, cap25: bool) -> AssessResult<f64> {
        let pd = if cap25 { self.pd1500(p_comp) } else { self.pd1350(p_comp) };
        if pd <= 0.0 {
            return Ok(f64::INFINITY);
        }
        Ok(match r {
            Req::Necessary => mdot_required(t, pd + self.inp.q_max_w_m2[i] * a_eff)?,
            Req::Plan(eta) => t * t / (2.0 * eta * pd),
            Req::VdBound => (t / self.v_max_o).max(mdot_required(t, pd + self.inp.q_max_w_m2[i] * a_eff)?),
        })
    }

    /// IF-A1 record of geometry g, scenario si, required state i at effective area a (the v1 `records` scaling).
    pub fn record_at(&self, g: usize, si: usize, i: usize, a: f64) -> IntakeState {
        let r = &self.inp.unit[g][si][self.inp.req_f1[i]];
        let mut x = r.clone();
        x.candidate = Intake { area: a, g }.id();
        x.area_m2 = a;
        x.mdot_fwd_kgps = [r.mdot_fwd_kgps[0] * a, r.mdot_fwd_kgps[1] * a, r.mdot_fwd_kgps[2] * a];
        // The F1 per-candidate drag feasibility of the unit record is replaced by the v3 total-drag condition.
        x.f1_status = "FEASIBLE_AT_STATE".into();
        x
    }
}

// ------------------------------------------------------------------------------------------------ steady table

/// One in-domain steady point.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Pt {
    pub mdot: f64,
    pub p_el: f64,
    pub m: f64,
}

/// Steady results of one (geometry, filter, compressor plant): [target][scenario][state][A_eff], None = out of domain,
/// refused or pruned. `swept` counts the rows evaluated.
#[derive(Debug, Clone, PartialEq)]
pub struct Table {
    pub n_s: usize,
    pub n_a: usize,
    pub n_sc: usize,
    pub pts: Vec<Option<Pt>>,
    pub swept: usize,
    pub pruned: usize,
    /// Rows dead-headed at every registered set pressure (not swept).
    pub dead: usize,
}

impl Table {
    pub fn get(&self, j: usize, si: usize, i: usize, a: usize) -> Option<Pt> {
        self.pts[((j * self.n_sc + si) * self.n_s + i) * self.n_a + a]
    }
}

/// Favourable sustained bound for pruning: captured >= K-MDOT-REQ(max(T12, D), P_d(0) + q_max A_eff) and D within the
/// limit, with D at the smallest registered A_max that realises A_eff (D grows with the closed area).
fn row_can_operate(w: &WInputs, g: usize, si: usize, i: usize, a: f64, cda_host: f64) -> AssessResult<bool> {
    let d = w.d_tot(g, si, i, w.a_max_min(a), a, cda_host);
    if d > w.inp.t25_n {
        return Ok(false);
    }
    let req = w.req(Req::Necessary, w.inp.t12_n.max(d), i, a, 0.0, false)?;
    Ok(w.cap[g][si][i] * a >= req)
}

/// Dead-head pressure of every intake-side row: the total plenum pressure at a closed feed (a_eq = 0), exactly the
/// `p_dead` of `area_for_pressure` inside `steady_sweep` (same node coefficients, same `solve_pressures`). A row with
/// p_dead <= min P_set is dead-headed at every registered set pressure and has no admissible point.
pub fn p_dead_rows(side: &(Vec<Sp3>, Vec<Sp3>), plant: &CompressorPlant, pl: &Plenum) -> AssessResult<Vec<f64>> {
    let ch = plant.characteristic()?;
    let cl = plant.leak_m3_s();
    let nan = f64::NAN;
    let mut base = [Node { f: 0.0, e: 0.0, alpha: 0.0, beta: 0.0, a_c: 0.0, b_c: 0.0, d: nan, e_fac: nan, a: nan }; 3];
    for i in 0..3 {
        base[i].a_c = ch[i].0;
        base[i].b_c = ch[i].1;
        base[i].alpha = pyops::div(ch[i].0, ch[i].1)? + cl;
        base[i].beta = pyops::div(1.0, ch[i].1)? + cl;
    }
    let (leak, fc, k_rec) = (pl.leak3()?, pl.feed3()?, pl.k_rec_m3_s()?);
    let mut out = Vec::with_capacity(side.0.len());
    for (fv, ev) in side.0.iter().zip(&side.1) {
        let mut co = base;
        for k in 0..3 {
            co[k].f = fv[k];
            co[k].e = ev[k];
        }
        let p3 = solve_pressures(&co, 0.0, k_rec, &leak, &fc, false)?.0;
        out.push(0.0 + p3[0] + p3[1] + p3[2]);
    }
    Ok(out)
}

/// Sweep every non-pruned (state, A_eff) row of one (geometry, filter, plant) on the v1 harness path.
pub fn eval_table(
    w: &WInputs,
    g: usize,
    fc: &FilterCase,
    plant: &CompressorPlant,
    pl: &Plenum,
    cda_host: f64,
) -> AssessResult<Table> {
    eval_table_sel(w, g, fc, plant, pl, cda_host, None)
}

/// [`eval_table`] restricted to the selected required states (the others carry no point).
pub fn eval_table_sel(
    w: &WInputs,
    g: usize,
    fc: &FilterCase,
    plant: &CompressorPlant,
    pl: &Plenum,
    cda_host: f64,
    sel: Option<&[bool]>,
) -> AssessResult<Table> {
    let inp = w.inp;
    let (n_s, n_a, n_sc, m) = (inp.state_ids.len(), w.aeff.len(), inp.up.scenarios.len(), TARGETS_PA.len());
    let mut t = Table { n_s, n_a, n_sc, pts: vec![None; m * n_sc * n_s * n_a], swept: 0, pruned: 0, dead: 0 };
    for si in 0..n_sc {
        let mut rows = vec![];
        let mut recs = vec![];
        for i in 0..n_s {
            if sel.is_some_and(|x| !x[i]) {
                continue;
            }
            for (ai, &a) in w.aeff.iter().enumerate() {
                if row_can_operate(w, g, si, i, a, cda_host)? {
                    rows.push((i, ai));
                    recs.push(w.record_at(g, si, i, a));
                } else {
                    t.pruned += 1;
                }
            }
        }
        if rows.is_empty() {
            continue;
        }
        let full = intake_side(&recs, fc, 1.0)?;
        let pd = p_dead_rows(&full, plant, pl)?;
        let keep: Vec<usize> = (0..rows.len()).filter(|&r| pd[r] > TARGETS_PA[0]).collect();
        t.dead += rows.len() - keep.len();
        let rows: Vec<(usize, usize)> = keep.iter().map(|&r| rows[r]).collect();
        if rows.is_empty() {
            continue;
        }
        let side = (keep.iter().map(|&r| full.0[r]).collect(), keep.iter().map(|&r| full.1[r]).collect());
        let sw = steady_sweep(&side, plant, pl, &inp.up.materials, &TARGETS_PA, None)?;
        t.swept += rows.len();
        for (r, &(i, ai)) in rows.iter().enumerate() {
            for (j, tg) in TARGETS_PA.iter().enumerate() {
                let idx = r * m + j;
                let margin = sw.p_deadhead_pa[idx] / tg - 1.0;
                if sw.bits[idx] == 0 && sw.in_domain[idx] && margin > 0.0 {
                    t.pts[((j * n_sc + si) * n_s + i) * n_a + ai] =
                        Some(Pt { mdot: sw.mdot_total_kgps[idx], p_el: sw.p_el_w[idx], m: sw.m_compressor_kg[idx] });
                }
            }
        }
    }
    Ok(t)
}

// ------------------------------------------------------------------------------------------------ design evaluation

/// Settings of one design evaluation.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Opts {
    pub req: Req,
    pub mass_limit: bool,
    pub cda_host: f64,
}

pub const GOVERNING: Opts = Opts { req: Req::Necessary, mass_limit: true, cda_host: f64::NAN };

/// Operating point of one (state, scenario).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Op {
    pub j_open: usize,
    pub a: usize,
    pub d_tot: f64,
    pub mdot: f64,
    pub req: f64,
    pub p_el: f64,
    pub m: f64,
}

/// Why a (state, scenario) has no operating point (the first condition no open-segment count passes).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Fail {
    Drag,
    Domain,
    Power,
    Mass,
    Flow,
}

impl Fail {
    pub fn as_str(&self) -> &'static str {
        match self {
            Fail::Drag => "DRAG",
            Fail::Domain => "DOMAIN",
            Fail::Power => "POWER",
            Fail::Mass => "MASS",
            Fail::Flow => "FLOW",
        }
    }
}

/// Window evaluation of one design.
#[derive(Debug, Clone, PartialEq)]
pub struct WEval {
    pub ops: Vec<Vec<Result<Op, Fail>>>,
    pub cap25: Vec<u32>,
    pub served: Vec<bool>,
    /// Run in flux order [k0, k1] (positions in `order`) or None.
    pub run: Option<(usize, usize)>,
    pub o1: usize,
    pub o2: usize,
    pub nodes_ok: Vec<bool>,
    pub log_width: f64,
    pub r_sus: f64,
    pub m_max: f64,
    pub d_max: f64,
    pub p_max: f64,
    pub n_cap25_states: usize,
}

/// Evaluate one design (geometry g, A_max, N, target j) on a steady table.
#[allow(clippy::too_many_arguments)]
pub fn eval_design(w: &WInputs, t: &Table, g: usize, a_max: f64, n: usize, j: usize, o: Opts) -> AssessResult<WEval> {
    let inp = w.inp;
    let cda = if o.cda_host.is_nan() { w.cda_host_m2 } else { o.cda_host };
    let (n_s, n_sc) = (inp.state_ids.len(), inp.up.scenarios.len());
    let open: Vec<(usize, f64, usize)> =
        (1..=n).map(|k| (k, a_max * k as f64 / n as f64, w.aidx(a_max * k as f64 / n as f64))).collect();
    let mut ops = vec![];
    let mut cap25 = vec![0u32; n_s];
    let mut served = vec![true; n_s];
    for i in 0..n_s {
        let mut row = vec![];
        for si in 0..n_sc {
            let mut best: Result<Op, Fail> = Err(Fail::Drag);
            for &(k, a, ai) in &open {
                let d = w.d_tot(g, si, i, a_max, a, cda);
                let stage = if d > inp.t25_n {
                    Err(Fail::Drag)
                } else {
                    match t.get(j, si, i, ai) {
                        None if !row_can_operate(w, g, si, i, a, cda)? => Err(Fail::Flow),
                        None => Err(Fail::Domain),
                        Some(p) if p.p_el.is_nan() || p.p_el > w.headroom_w || w.pd1350(p.p_el) <= 0.0 => {
                            Err(Fail::Power)
                        }
                        Some(p) if o.mass_limit && (p.m.is_nan() || p.m > inp.m_comp_limit_kg) => Err(Fail::Mass),
                        Some(p) => Ok(p),
                    }
                };
                let p = match stage {
                    Ok(p) => p,
                    Err(e) => {
                        if best.is_err() && best.unwrap_err() < e {
                            best = Err(e);
                        }
                        continue;
                    }
                };
                if cap25[i] & (1 << si) == 0 && p.mdot >= w.req(o.req, inp.t25_n, i, a, p.p_el, true)? {
                    cap25[i] |= 1 << si;
                }
                if best.is_ok() {
                    continue;
                }
                let req = w.req(o.req, inp.t12_n.max(d), i, a, p.p_el, false)?;
                if p.mdot >= req {
                    best = Ok(Op { j_open: k, a: ai, d_tot: d, mdot: p.mdot, req, p_el: p.p_el, m: p.m });
                } else if best.unwrap_err() < Fail::Flow {
                    best = Err(Fail::Flow);
                }
            }
            if best.is_err() {
                served[i] = false;
            }
            row.push(best);
        }
        ops.push(row);
    }
    let mut e = WEval {
        ops,
        cap25,
        served,
        run: None,
        o1: 0,
        o2: 0,
        nodes_ok: vec![false; w.nodes.len()],
        log_width: 0.0,
        r_sus: 0.0,
        m_max: 0.0,
        d_max: 0.0,
        p_max: 0.0,
        n_cap25_states: 0,
    };
    let all_sc = (1u32 << n_sc) - 1;
    let mut best: Option<(RunKey, (usize, usize))> = None;
    let mut k = 0;
    while k < n_s {
        if !e.served[w.order[k]] {
            k += 1;
            continue;
        }
        let k0 = k;
        while k < n_s && e.served[w.order[k]] {
            k += 1;
        }
        let k1 = k - 1;
        let capm = (k0..=k1).fold(0u32, |acc, q| acc | e.cap25[w.order[q]]);
        if capm != all_sc {
            continue;
        }
        let (o1, o2, _) = coverage(w, k0, k1);
        let width = (w.phi[w.order[k1]] / w.phi[w.order[k0]]).ln();
        let key = (o1, o2, width);
        let better = match &best {
            None => true,
            Some((b, _)) => (key.0, key.1).cmp(&(b.0, b.1)).then(key.2.total_cmp(&b.2)).is_gt(),
        };
        if better {
            best = Some((key, (k0, k1)));
        }
    }
    if let Some(((o1, o2, width), (k0, k1))) = best {
        e.run = Some((k0, k1));
        e.o1 = o1;
        e.o2 = o2;
        e.nodes_ok = coverage(w, k0, k1).2;
        e.log_width = width;
        let (mut r, mut mm, mut dm, mut pm) = (f64::INFINITY, 0.0f64, 0.0f64, 0.0f64);
        for q in k0..=k1 {
            let i = w.order[q];
            if e.cap25[i] != 0 {
                e.n_cap25_states += 1;
            }
            for op in e.ops[i].iter().flatten() {
                r = r.min(op.mdot / op.req);
                mm = mm.max(op.m);
                dm = dm.max(op.d_tot);
                pm = pm.max(op.p_el);
            }
        }
        (e.r_sus, e.m_max, e.d_max, e.p_max) = (r, mm, dm, pm);
    }
    Ok(e)
}

/// (O1, O2, log width) of a run.
pub type RunKey = (usize, usize, f64);
/// Rust stability row at a window operating point: (scenario, state, A_eff, class, equilibrium kinds).
pub type StabRowW = (usize, usize, f64, &'static str, Vec<&'static str>);
/// Python reference row: (class, equilibrium kinds, A_eff).
type PyRow = (String, Vec<String>, f64);

/// (O1, O2, node flags) of the run [k0, k1]: a node is admissible when every one of its states is in the run.
pub fn coverage(w: &WInputs, k0: usize, k1: usize) -> (usize, usize, Vec<bool>) {
    let ok: Vec<bool> = w.nodes.iter().map(|(_, _, st)| st.iter().all(|&i| w.pos[i] >= k0 && w.pos[i] <= k1)).collect();
    let o2 = ok.iter().filter(|x| **x).count();
    let o1 = (0..w.conds.len()).filter(|&c| w.nodes.iter().zip(&ok).any(|(nd, k)| nd.0 == c && *k)).count();
    (o1, o2, ok)
}

// ------------------------------------------------------------------------------------------------ ranking

/// One ranked design (steady part); V and the controller are fixed by the stability screen.
#[derive(Debug, Clone, PartialEq)]
pub struct WDesign {
    pub g: usize,
    pub filter: usize,
    pub comp: usize,
    pub a_max: f64,
    pub n: usize,
    pub target: usize,
    pub o1: usize,
    pub o2: usize,
    pub log_width: f64,
    pub r_sus: f64,
    pub m_max: f64,
    pub d_max: f64,
    pub p_max: f64,
}

pub type WKeys = (i64, i64, usize, i64, i64, i64, f64, f64, f64, f64, String);

fn bin(x: f64, per_unit: f64) -> i64 {
    (x * per_unit).floor() as i64
}

impl WDesign {
    pub fn id(&self, inp: &Inputs) -> String {
        format!(
            "{}|N{}|{}|{}|P{}",
            f1_candidate_id(self.a_max, GEOMS[self.g].0, GEOMS[self.g].1),
            self.n,
            FILTERS[self.filter],
            inp.compressors[self.comp].id,
            py_format_g(TARGETS_PA[self.target])
        )
    }

    /// v3 ranking keys other than R (robustness is evaluated lazily) and the (V, controller) keys.
    pub fn keys(&self, inp: &Inputs) -> WKeys {
        (
            -(self.o1 as i64),
            -(self.o2 as i64),
            self.n,
            -bin(self.log_width, 10.0),
            -bin(self.r_sus, 20.0),
            bin(self.m_max, 10.0),
            self.a_max,
            -TARGETS_PA[self.target],
            self.d_max,
            self.p_max,
            self.id(inp),
        )
    }
}

pub fn cmp_keys(a: &WKeys, b: &WKeys) -> std::cmp::Ordering {
    let c = |x: f64, y: f64| x.partial_cmp(&y).unwrap_or(std::cmp::Ordering::Equal);
    a.0.cmp(&b.0)
        .then(a.1.cmp(&b.1))
        .then(a.2.cmp(&b.2))
        .then(a.3.cmp(&b.3))
        .then(a.4.cmp(&b.4))
        .then(a.5.cmp(&b.5))
        .then(c(a.6, b.6))
        .then(c(a.7, b.7))
        .then(c(a.8, b.8))
        .then(c(a.9, b.9))
        .then(a.10.cmp(&b.10))
}

/// Per-N best (O1, O2, log width) over every evaluated design (mechanism comparison).
pub type MechBest = BTreeMap<usize, (usize, usize, f64, usize)>;

/// Evaluate every (A_max, N, P_set) of one (geometry, filter, compressor); keep designs with a window covering a node.
pub fn eval_triple_w(
    w: &WInputs,
    g: usize,
    fi: usize,
    ci: usize,
    k: &Coeffs,
    o: Opts,
) -> AssessResult<(Vec<WDesign>, MechBest, usize, usize, usize)> {
    let inp = w.inp;
    let fc = inp.filter(FILTERS[fi])?;
    let plant = inp.plant(&inp.compressors[ci], k)?;
    let pl = inp.plenum(VOLUMES_M3[0])?;
    let cda = if o.cda_host.is_nan() { w.cda_host_m2 } else { o.cda_host };
    let t0 = std::time::Instant::now();
    let mut out = vec![];
    let mut mech: MechBest = BTreeMap::new();
    // Node-extreme screen (exact necessary condition): a design covers a node only if it serves the node's lowest-
    // and highest-flux states in every scenario; a triple with no such (design, node) has no design with O2 >= 1.
    let ts = eval_table_sel(w, g, fc, &plant, &pl, cda, Some(&w.extremes))?;
    let mut pass = false;
    'screen: for a_max in A_MAX {
        for n in N_SEG {
            for j in 0..TARGETS_PA.len() {
                let e = eval_design(w, &ts, g, a_max, n, j, o)?;
                if w.nodes.iter().any(|(_, _, st)| st.iter().all(|&i| !w.extremes[i] || e.served[i])) {
                    pass = true;
                    break 'screen;
                }
            }
        }
    }
    if !pass {
        return Ok((out, mech, ts.swept, ts.pruned, 1));
    }
    let t = eval_table(w, g, fc, &plant, &pl, cda)?;
    let t1 = t0.elapsed().as_secs_f64();
    for a_max in A_MAX {
        for n in N_SEG {
            for j in 0..TARGETS_PA.len() {
                let e = eval_design(w, &t, g, a_max, n, j, o)?;
                let ent = mech.entry(n).or_insert((0, 0, 0.0, 0));
                if e.run.is_some() {
                    ent.3 += 1;
                    if (e.o1, e.o2).cmp(&(ent.0, ent.1)).then(e.log_width.total_cmp(&ent.2)).is_gt() {
                        (ent.0, ent.1, ent.2) = (e.o1, e.o2, e.log_width);
                    }
                }
                if e.o2 >= 1 {
                    out.push(WDesign {
                        g,
                        filter: fi,
                        comp: ci,
                        a_max,
                        n,
                        target: j,
                        o1: e.o1,
                        o2: e.o2,
                        log_width: e.log_width,
                        r_sus: e.r_sus,
                        m_max: e.m_max,
                        d_max: e.d_max,
                        p_max: e.p_max,
                    });
                }
            }
        }
    }
    if std::env::var("DCR001_W_DEV_TIMING").is_ok() {
        eprintln!(
            "triple g{g} f{fi} c{ci}: table {t1:.3} s ({} swept, {} pruned, {} dead-headed), designs {:.3} s",
            t.swept,
            t.pruned,
            t.dead,
            t0.elapsed().as_secs_f64() - t1
        );
    }
    Ok((out, mech, t.swept + ts.swept, t.pruned + ts.pruned, 0))
}

fn merge_mech(into: &mut MechBest, m: &MechBest) {
    for (n, v) in m {
        let e = into.entry(*n).or_insert((0, 0, 0.0, 0));
        e.3 += v.3;
        if (v.0, v.1).cmp(&(e.0, e.1)).then(v.2.total_cmp(&e.2)).is_gt() {
            (e.0, e.1, e.2) = (v.0, v.1, v.2);
        }
    }
}

/// Full design-space evaluation over the given compressors.
pub fn evaluate_space(
    w: &WInputs,
    comps: &[usize],
    o: Opts,
    threads: usize,
) -> AssessResult<(Vec<WDesign>, MechBest, usize, usize, usize)> {
    // Development only (never a record): DCR001_W_DEV_G / DCR001_W_DEV_F restrict the geometry / filter.
    let dev = |k: &str| std::env::var(k).ok().and_then(|x| x.parse::<usize>().ok());
    let (dg, df) = (dev("DCR001_W_DEV_G"), dev("DCR001_W_DEV_F"));
    // Development only (never a record): DCR001_W_DEV_STRIDE=k evaluates every k-th compressor.
    let stride: usize = std::env::var("DCR001_W_DEV_STRIDE").ok().and_then(|x| x.parse().ok()).unwrap_or(1);
    let comps: Vec<usize> = comps.iter().copied().step_by(stride.max(1)).collect();
    let comps = &comps;
    let triples: Vec<(usize, usize, usize)> = (0..GEOMS.len())
        .filter(|g| dg.is_none_or(|x| x == *g))
        .flat_map(|g| {
            (0..FILTERS.len())
                .filter(move |f| df.is_none_or(|x| x == *f))
                .flat_map(move |fi| comps.iter().map(move |&c| (g, fi, c)))
        })
        .collect();
    // Optional resume checkpoint (DCR001_W_CHECKPOINT_DIR): every evaluated triple is appended as one JSON line keyed by
    // (opts, triple); a restarted run reloads them. Results are pure functions of the pinned inputs, so a reloaded line
    // equals a recomputed one (f64 round-trips exactly through serde_json).
    let ck = std::env::var("DCR001_W_CHECKPOINT_DIR").ok().map(|d| {
        let tag = format!(
            "mass{}_host{}",
            o.mass_limit as u8,
            if o.cda_host.is_nan() { "gov".into() } else { py_format_g(o.cda_host) }
        );
        std::path::PathBuf::from(d).join(format!("triples_{tag}.jsonl"))
    });
    let mut done: HashMap<(usize, usize, usize), Value> = HashMap::new();
    if let Some(path) = &ck {
        if let Ok(text) = std::fs::read_to_string(path) {
            for line in text.lines() {
                if let Ok(v) = serde_json::from_str::<Value>(line) {
                    let key = |i: usize| v["t"][i].as_u64().map(|x| x as usize);
                    if let (Some(a), Some(b), Some(c)) = (key(0), key(1), key(2)) {
                        done.insert((a, b, c), v);
                    }
                }
            }
            eprintln!("DCR-001 v3: checkpoint {} triples reloaded from {}", done.len(), path.display());
        }
    }
    let writer = std::sync::Mutex::new(
        ck.as_ref().map(|p| std::fs::OpenOptions::new().create(true).append(true).open(p).expect("checkpoint file")),
    );
    let res = par_map(triples.len(), threads, |k| {
        let (g, fi, c) = triples[k];
        if let Some(v) = done.get(&(g, fi, c)) {
            return triple_from_value(v);
        }
        let r = eval_triple_w(w, g, fi, c, &NOMINAL, o)?;
        if let Some(f) = writer.lock().expect("lock").as_mut() {
            use std::io::Write;
            let line = triple_to_value((g, fi, c), &r).to_string();
            writeln!(f, "{line}").map_err(|e| model_error(format!("checkpoint write: {e}")))?;
        }
        Ok(r)
    })?;
    let mut all = vec![];
    let mut mech = MechBest::new();
    let (mut sw, mut pr, mut out) = (0, 0, 0);
    for (d, m, s, p, x) in res {
        all.extend(d);
        merge_mech(&mut mech, &m);
        sw += s;
        pr += p;
        out += x;
    }
    eprintln!("DCR-001 v3: {} of {} triples removed by the node-extreme screen", out, triples.len());
    Ok((all, mech, sw, pr, out))
}

type TripleOut = (Vec<WDesign>, MechBest, usize, usize, usize);

fn triple_to_value(t: (usize, usize, usize), r: &TripleOut) -> Value {
    let ds: Vec<Value> =
        r.0.iter()
            .map(|d| {
                json!([
                    d.g,
                    d.filter,
                    d.comp,
                    d.a_max,
                    d.n,
                    d.target,
                    d.o1,
                    d.o2,
                    d.log_width,
                    d.r_sus,
                    d.m_max,
                    d.d_max,
                    d.p_max
                ])
            })
            .collect();
    let mech: Vec<Value> = r.1.iter().map(|(n, v)| json!([n, v.0, v.1, v.2, v.3])).collect();
    json!({"t": [t.0, t.1, t.2], "d": ds, "m": mech, "s": [r.2, r.3, r.4]})
}

fn triple_from_value(v: &Value) -> AssessResult<TripleOut> {
    let bad = || model_error("checkpoint line malformed");
    let u = |x: &Value| x.as_u64().map(|y| y as usize).ok_or_else(bad);
    let fl = |x: &Value| x.as_f64().ok_or_else(bad);
    let mut ds = vec![];
    for d in v["d"].as_array().ok_or_else(bad)? {
        let a = d.as_array().ok_or_else(bad)?;
        if a.len() != 13 {
            return Err(bad());
        }
        ds.push(WDesign {
            g: u(&a[0])?,
            filter: u(&a[1])?,
            comp: u(&a[2])?,
            a_max: fl(&a[3])?,
            n: u(&a[4])?,
            target: u(&a[5])?,
            o1: u(&a[6])?,
            o2: u(&a[7])?,
            log_width: fl(&a[8])?,
            r_sus: fl(&a[9])?,
            m_max: fl(&a[10])?,
            d_max: fl(&a[11])?,
            p_max: fl(&a[12])?,
        });
    }
    let mut mech = MechBest::new();
    for m in v["m"].as_array().ok_or_else(bad)? {
        let a = m.as_array().ok_or_else(bad)?;
        mech.insert(u(&a[0])?, (u(&a[1])?, u(&a[2])?, fl(&a[3])?, u(&a[4])?));
    }
    let s = v["s"].as_array().ok_or_else(bad)?;
    Ok((ds, mech, u(&s[0])?, u(&s[1])?, u(&s[2])?))
}

// ------------------------------------------------------------------------------------------------ stability

/// The (state, scenario) operating points of the window of an evaluation.
pub fn window_ops(w: &WInputs, e: &WEval) -> Vec<(usize, usize, Op)> {
    let mut v = vec![];
    if let Some((k0, k1)) = e.run {
        for q in k0..=k1 {
            let i = w.order[q];
            for (si, op) in e.ops[i].iter().enumerate() {
                if let Ok(op) = op {
                    v.push((si, i, *op));
                }
            }
        }
    }
    v.sort_by_key(|x| (x.0, x.1));
    v
}

/// Rust class rows (scenario, state, area, class, kinds) at the given operating points.
#[allow(clippy::too_many_arguments)]
pub fn stab_rows(
    w: &WInputs,
    g: usize,
    fc: &FilterCase,
    plant: &CompressorPlant,
    pl: &Plenum,
    ctrl: Controller,
    p_set: f64,
    ops: &[(usize, usize, Op)],
    stop_at_first: bool,
) -> AssessResult<Vec<StabRowW>> {
    let mut out = vec![];
    for &(si, i, op) in ops {
        let a = w.aeff[op.a];
        let rec = w.record_at(g, si, i, a);
        let r = stability_class_events(fc, plant, pl, ctrl, &w.inp.up.materials, &rec, p_set, WINDOW_S)?;
        let class = r.class.as_str();
        out.push((si, i, a, class, r.equilibria.iter().map(|q| q.kind.as_str()).collect()));
        if class != "S" && stop_at_first {
            break;
        }
    }
    Ok(out)
}

/// Evaluation of a design at one coefficient set (fresh table).
pub fn eval_at(w: &WInputs, d: &WDesign, k: &Coeffs, o: Opts) -> AssessResult<WEval> {
    let inp = w.inp;
    let fc = inp.filter(FILTERS[d.filter])?;
    let plant = inp.plant(&inp.compressors[d.comp], k)?;
    let pl = inp.plenum(VOLUMES_M3[0])?;
    let cda = if o.cda_host.is_nan() { w.cda_host_m2 } else { o.cda_host };
    let t = eval_table(w, d.g, fc, &plant, &pl, cda)?;
    eval_design(w, &t, d.g, d.a_max, d.n, d.target, o)
}

/// Corner robustness of the nominal window: every window state served, C-FLOW-CAP on the window, and Rust class S at
/// the corner operating points with the design's (V, controller).
#[derive(Debug, Clone, PartialEq)]
pub struct CornerCheck {
    pub name: String,
    pub steady_ok: bool,
    pub n_unserved: usize,
    pub cap_ok: bool,
    pub stab_ok: bool,
    pub n_non_s: usize,
    pub ops: Vec<(usize, usize, Op)>,
}

#[allow(clippy::too_many_arguments)]
pub fn corner_check(
    w: &WInputs,
    d: &WDesign,
    nominal: &WEval,
    name: &str,
    k: &Coeffs,
    v: f64,
    ctrl: (f64, f64),
    o: Opts,
) -> AssessResult<CornerCheck> {
    let inp = w.inp;
    let e = eval_at(w, d, k, o)?;
    let (k0, k1) = nominal.run.ok_or_else(|| model_error("corner check of a design without a window"))?;
    let states: Vec<usize> = (k0..=k1).map(|q| w.order[q]).collect();
    let n_unserved = states.iter().filter(|&&i| !e.served[i]).count();
    let all_sc = (1u32 << inp.up.scenarios.len()) - 1;
    let cap_ok = states.iter().fold(0u32, |a, &i| a | e.cap25[i]) == all_sc;
    let mut ops = vec![];
    for &i in &states {
        for (si, op) in e.ops[i].iter().enumerate() {
            if let Ok(op) = op {
                ops.push((si, i, *op));
            }
        }
    }
    ops.sort_by_key(|x| (x.0, x.1));
    let fc = inp.filter(FILTERS[d.filter])?;
    let plant = inp.plant(&inp.compressors[d.comp], k)?;
    let pl = inp.plenum(v)?;
    let rows = stab_rows(w, d.g, fc, &plant, &pl, controller(ctrl.0, ctrl.1), TARGETS_PA[d.target], &ops, false)?;
    let n_non_s = rows.iter().filter(|r| r.3 != "S").count();
    Ok(CornerCheck {
        name: name.into(),
        steady_ok: n_unserved == 0,
        n_unserved,
        cap_ok,
        stab_ok: n_non_s == 0,
        n_non_s,
        ops,
    })
}

/// Robustness verdict only (early exit at the first failing corner; steady tables restricted to the window states).
pub fn robust_quick(
    w: &WInputs,
    d: &WDesign,
    nominal: &WEval,
    v: f64,
    ctrl: (f64, f64),
    o: Opts,
) -> AssessResult<bool> {
    let inp = w.inp;
    let (k0, k1) = nominal.run.ok_or_else(|| model_error("robustness of a design without a window"))?;
    let mut sel = vec![false; inp.state_ids.len()];
    for q in k0..=k1 {
        sel[w.order[q]] = true;
    }
    let fc = inp.filter(FILTERS[d.filter])?;
    let pl = inp.plenum(VOLUMES_M3[0])?;
    let plv = inp.plenum(v)?;
    let cda = if o.cda_host.is_nan() { w.cda_host_m2 } else { o.cda_host };
    let all_sc = (1u32 << inp.up.scenarios.len()) - 1;
    for (_, k) in crate::dcr001::corners() {
        let plant = inp.plant(&inp.compressors[d.comp], &k)?;
        let t = eval_table_sel(w, d.g, fc, &plant, &pl, cda, Some(&sel))?;
        let e = eval_design(w, &t, d.g, d.a_max, d.n, d.target, o)?;
        let states: Vec<usize> = (k0..=k1).map(|q| w.order[q]).collect();
        if states.iter().any(|&i| !e.served[i]) || states.iter().fold(0u32, |a, &i| a | e.cap25[i]) != all_sc {
            return Ok(false);
        }
        let mut ops = vec![];
        for &i in &states {
            for (si, op) in e.ops[i].iter().enumerate() {
                if let Ok(op) = op {
                    ops.push((si, i, *op));
                }
            }
        }
        ops.sort_by_key(|x| (x.0, x.1));
        let rows = stab_rows(w, d.g, fc, &plant, &plv, controller(ctrl.0, ctrl.1), TARGETS_PA[d.target], &ops, true)?;
        if rows.iter().any(|r| r.3 != "S") {
            return Ok(false);
        }
    }
    Ok(true)
}

// ------------------------------------------------------------------------------------------------ search

fn fin(x: f64) -> Value {
    if x.is_finite() {
        json!(x)
    } else {
        Value::Null
    }
}

/// Human-readable window, schedule and keys of an evaluation.
pub fn window_value(w: &WInputs, e: &WEval) -> Value {
    let Some((k0, k1)) = e.run else {
        return json!({"window": Value::Null});
    };
    let (lo, hi) = (w.order[k0], w.order[k1]);
    let mut sched = Map::new();
    for (ci, c) in w.conds.iter().enumerate() {
        let ok: Vec<f64> =
            w.nodes.iter().zip(&e.nodes_ok).filter(|(nd, k)| nd.0 == ci && **k).map(|(nd, _)| nd.1).collect();
        sched.insert(
            c.clone(),
            if ok.is_empty() {
                json!({"status": "UNCOVERED", "admissible_nodes_km": []})
            } else {
                json!({"status": "COVERED", "admissible_nodes_km": ok,
                       "band_km": [ok.iter().cloned().fold(f64::INFINITY, f64::min), ok.iter().cloned().fold(0.0, f64::max)]})
            },
        );
    }
    json!({
        "Phi_lo_kg_m2_s": w.phi[lo], "Phi_hi_kg_m2_s": w.phi[hi],
        "Phi_lo_state": w.inp.state_ids[lo], "Phi_hi_state": w.inp.state_ids[hi],
        "Phi_adm_A4_at_ends": [w.phi_adm[lo], w.phi_adm[hi]],
        "ratio_hi_over_lo": w.phi[hi] / w.phi[lo],
        "n_states_in_window": k1 - k0 + 1,
        "O1_conditions_covered": e.o1, "O2_nodes_admissible": e.o2,
        "states_with_25mN_capability_point": e.n_cap25_states,
        "worst_sustained_flow_ratio": fin(e.r_sus),
        "m_compressor_max_kg": fin(e.m_max), "D_tot_max_N": fin(e.d_max), "P_compressor_max_W": fin(e.p_max),
        "altitude_schedule": sched
    })
}

/// Search output: the search record and the governed Python stability spec.
pub struct WSearchOut {
    pub record: Value,
    pub spec: Value,
}

/// The selection of the search.
#[derive(Debug, Clone)]
pub struct WSelection {
    pub design: WDesign,
    pub v: f64,
    pub ctrl: (f64, f64),
    pub robust: bool,
    pub corners: Vec<CornerCheck>,
    pub nominal: WEval,
    pub mass_relaxed: bool,
}

fn select(
    w: &WInputs,
    designs: &[WDesign],
    threads: usize,
    log: &mut Vec<Value>,
    o: Opts,
) -> AssessResult<(Option<WSelection>, usize, bool)> {
    let inp = w.inp;
    let mut keyed: Vec<(WKeys, &WDesign)> = designs.iter().map(|d| (d.keys(inp), d)).collect();
    keyed.sort_by(|a, b| cmp_keys(&a.0, &b.0));
    let best_o1 = keyed.first().map(|k| k.1.o1).unwrap_or(0);
    let mut screened = 0;
    let mut first_completed: Option<WSelection> = None;
    let mut cap_reached = false;
    for (_, d) in keyed.iter().filter(|k| k.1.o1 == best_o1) {
        if screened >= STABILITY_CAP {
            cap_reached = true;
            break;
        }
        screened += 1;
        let nominal = eval_at(w, d, &NOMINAL, o)?;
        let ops = window_ops(w, &nominal);
        let fc = inp.filter(FILTERS[d.filter])?;
        let plant = inp.plant(&inp.compressors[d.comp], &NOMINAL)?;
        let mut choice = None;
        'outer: for v in VOLUMES_M3 {
            let pl = inp.plenum(v)?;
            for (kp, ti) in CTRL_ORDER {
                let rows = stab_rows(w, d.g, fc, &plant, &pl, controller(kp, ti), TARGETS_PA[d.target], &ops, true)?;
                if rows.iter().all(|r| r.3 == "S") {
                    choice = Some((v, (kp, ti)));
                    break 'outer;
                }
            }
        }
        let Some((v, ctrl)) = choice else {
            log.push(json!({"design_id": d.id(inp), "stability": "NO_ALL_S_V_CONTROLLER (set aside)"}));
            continue;
        };
        let robust = robust_quick(w, d, &nominal, v, ctrl, o)?;
        log.push(json!({"design_id": d.id(inp), "V_m3": v, "controller": {"Kp": ctrl.0, "Ti_s": ctrl.1},
            "robust": robust}));
        let sel =
            WSelection { design: (*d).clone(), v, ctrl, robust, corners: vec![], nominal, mass_relaxed: !o.mass_limit };
        if robust {
            first_completed = Some(sel);
            break;
        }
        if first_completed.is_none() {
            first_completed = Some(sel);
        }
    }
    // Full corner detail (every corner, its operating points for the governed reference) of the selection.
    if let Some(sel) = first_completed.as_mut() {
        let cs = crate::dcr001::corners();
        let (d, nominal, v, ctrl) = (&sel.design, &sel.nominal, sel.v, sel.ctrl);
        sel.corners = par_map(cs.len(), threads, |q| corner_check(w, d, nominal, &cs[q].0, &cs[q].1, v, ctrl, o))?;
        let robust = sel.corners.iter().all(|c| c.steady_ok && c.cap_ok && c.stab_ok);
        if robust != sel.robust {
            return Err(model_error("DCR-001 v3: quick and full corner robustness verdicts differ"));
        }
        log.push(json!({"selected_design_id": sel.design.id(inp), "robust": robust,
            "corners": sel.corners.iter().map(|c| json!({"corner": c.name, "window_states_unserved": c.n_unserved,
                "cap25_ok": c.cap_ok, "non_S_rows": c.n_non_s})).collect::<Vec<_>>()}));
    }
    Ok((first_completed, screened, cap_reached))
}

/// Python stability spec of the selected design: per coefficient set, its own operating points.
pub fn spec_value(w: &WInputs, s: &WSelection) -> AssessResult<Value> {
    let inp = w.inp;
    let d = &s.design;
    let comp: &Comp = &inp.compressors[d.comp];
    let sets = coefficient_sets();
    let mut cs = vec![];
    for (name, k) in &sets {
        let ops = if name == "NOMINAL" {
            window_ops(w, &s.nominal)
        } else {
            s.corners.iter().find(|c| &c.name == name).map(|c| c.ops.clone()).ok_or_else(|| model_error("corner"))?
        };
        let rows: Vec<Value> = ops
            .iter()
            .map(|(si, i, op)| {
                json!({"scenario": inp.up.scenarios[*si], "state_id": inp.state_ids[*i], "area_m2": w.aeff[op.a]})
            })
            .collect();
        cs.push(json!({"id": name, "overrides": k.to_value(), "rows": rows}));
    }
    Ok(json!({
        "schema": SPEC_SCHEMA,
        "dcr": "DCR-DBF1-001",
        "prereg": {"path": V3_REL, "sha256": V3_SHA256},
        "design_id": format!("{}|V{}|Kp{}|Ti{}", d.id(inp), py_format_g(s.v), py_format_g(s.ctrl.0), py_format_g(s.ctrl.1)),
        "intake": {"L_over_d": GEOMS[d.g].0, "phi": GEOMS[d.g].1, "A_max_m2": d.a_max, "N_segments": d.n},
        "filter": FILTERS[d.filter],
        "compressor": {"id": comp.id, "f3_grid_index": comp.grid_index},
        "V_m3": s.v,
        "wall": WALL,
        "P_set_Pa": TARGETS_PA[d.target],
        "controller": {"Kp": s.ctrl.0, "Ti_s": s.ctrl.1, "f_valve_hz": crate::dcr001::F_VALVE_HZ,
                       "authority": crate::dcr001::AUTHORITY},
        "coefficient_sets": cs
    }))
}

fn mech_value(m: &MechBest) -> Value {
    Value::Object(
        m.iter()
            .map(|(n, v)| {
                (
                    format!("N{n}"),
                    json!({"mechanism": if *n == 1 { "VC-0 fixed aperture" } else { "VC-1 segmented frontal shutter" },
                       "designs_with_a_window": v.3, "best_O1": v.0, "best_O2": v.1, "best_log_width": v.2}),
                )
            })
            .collect(),
    )
}

pub fn design_summary(w: &WInputs, d: &WDesign) -> Value {
    json!({"design_id": d.id(w.inp), "O1": d.o1, "O2": d.o2, "N": d.n, "A_max_m2": d.a_max,
        "log_width": d.log_width, "worst_sustained_flow_ratio": d.r_sus, "m_compressor_max_kg": d.m_max,
        "D_tot_max_N": d.d_max, "P_compressor_max_W": d.p_max})
}

/// The preregistered window search (v3 ranking, stability screen, corners, mass-transfer rule).
pub fn window_search(w: &WInputs, threads: usize, rust_commit: &str) -> AssessResult<WSearchOut> {
    let inp = w.inp;
    eprintln!("DCR-001 v3: C_mass {} / {} compressors", w.c_mass.len(), inp.compressors.len());
    let stride: usize = std::env::var("DCR001_W_DEV_STRIDE").ok().and_then(|x| x.parse().ok()).unwrap_or(1);
    let dev_relaxed = std::env::var("DCR001_W_DEV_RELAXED").is_ok();
    let comps: Vec<usize> = if dev_relaxed { vec![] } else { w.c_mass.clone() };
    let (designs, mech, swept, pruned, screened_out) = evaluate_space(w, &comps, GOVERNING, threads)?;
    eprintln!("DCR-001 v3: {} designs with a window covering a node", designs.len());
    let ts = std::time::Instant::now();
    let mut log = vec![];
    let (mut sel, screened, cap_reached) = select(w, &designs, threads, &mut log, GOVERNING)?;
    eprintln!("DCR-001 v3: selection stage {:.1} s, {screened} designs screened", ts.elapsed().as_secs_f64());
    let mut keyed: Vec<(WKeys, &WDesign)> = designs.iter().map(|d| (d.keys(inp), d)).collect();
    keyed.sort_by(|a, b| cmp_keys(&a.0, &b.0));
    let top: Vec<Value> = keyed.iter().take(20).map(|(_, d)| design_summary(w, d)).collect();
    // Mass-transfer rule.
    let all_comps: Vec<usize> = (0..inp.compressors.len()).collect();
    let mut mass_relaxed = json!({"rule": "evaluated only if the selected design has O1 < 4"});
    let dev_run = stride > 1 || std::env::var("DCR001_W_DEV_G").is_ok() || std::env::var("DCR001_W_DEV_F").is_ok();
    if (!dev_run || dev_relaxed) && sel.as_ref().map(|s| s.design.o1).unwrap_or(0) < w.conds.len() {
        let o = Opts { mass_limit: false, ..GOVERNING };
        let (rd, rmech, _, _, rout) = evaluate_space(w, &all_comps, o, threads)?;
        let best_relaxed = rd.iter().map(|d| d.o1).max().unwrap_or(0);
        let mut rlog = vec![];
        let base_o1 = sel.as_ref().map(|s| s.design.o1).unwrap_or(0);
        let mut taken = false;
        if best_relaxed > base_o1 {
            if let (Some(s), _, _) = select(w, &rd, threads, &mut rlog, o)? {
                sel = Some(s);
                taken = true;
            }
        }
        mass_relaxed = json!({"rule": "evaluated (selected O1 < 4)", "best_O1_mass_relaxed": best_relaxed,
            "mechanisms": mech_value(&rmech), "triples_removed_by_node_extreme_screen": rout,
            "mass_relaxed_selection_taken": taken, "screen_log": rlog});
    }
    let Some(s) = sel else {
        let record = json!({
            "schema": SEARCH_SCHEMA, "dcr": "DCR-DBF1-001",
            "label": if dev_run { "DEVELOPMENT_SUBSET_NOT_A_RECORD" } else { LABEL }, "rust_commit": rust_commit,
            "prereg": {"path": V3_REL, "sha256": V3_SHA256},
            "result": "NO_ADMISSIBLE_WINDOW", "mechanisms": mech_value(&mech), "rows_swept": swept, "rows_pruned": pruned,
            "triples_removed_by_node_extreme_screen": screened_out,
            "designs_with_a_window_covering_a_node": designs.len(), "stability_screen": log, "mass_relaxed": mass_relaxed,
        });
        return Ok(WSearchOut { record, spec: Value::Null });
    };
    let spec = spec_value(w, &s)?;
    let record = json!({
        "schema": SEARCH_SCHEMA,
        "dcr": "DCR-DBF1-001",
        "label": if dev_run { "DEVELOPMENT_SUBSET_NOT_A_RECORD" } else { LABEL },
        "rust_commit": rust_commit,
        "prereg": {"path": V3_REL, "sha256": V3_SHA256, "lock": {"path": V3_LOCK_REL, "sha256": V3_LOCK_SHA256}},
        "space": {"A_max_m2": A_MAX, "N_segments": N_SEG, "A_eff_grid_m2": w.aeff, "geometries": GEOMS.len(),
                  "filters": FILTERS, "compressors_C_mass": w.c_mass.len(), "compressors_S0": inp.compressors.len(),
                  "P_set_Pa": TARGETS_PA, "rows_swept": swept, "rows_pruned_by_necessary_conditions": pruned,
                  "triples_removed_by_node_extreme_screen": screened_out,
                  "note": "mechanism statistics count the triples that pass the node-extreme screen"},
        "mechanisms": mech_value(&mech),
        "designs_with_a_window_covering_a_node": designs.len(),
        "top_20_by_v3_keys_without_R": top,
        "stability_screen": {"designs_screened": screened, "cap": STABILITY_CAP, "cap_reached": cap_reached, "log": log},
        "selection": {
            "design_id": spec["design_id"],
            "summary": design_summary(w, &s.design),
            "V_m3": s.v, "controller": {"Kp": s.ctrl.0, "Ti_s": s.ctrl.1},
            "robust": s.robust,
            "label": if s.robust { "ADMISSIBLE_ROBUST" } else { "ADMISSIBLE_CONDITIONAL_ON_COMPRESSOR_COEFFICIENTS" },
            "mass_relaxed_selection": s.mass_relaxed,
            "window": window_value(w, &s.nominal),
        },
        "mass_relaxed": mass_relaxed,
    });
    Ok(WSearchOut { record, spec })
}

// ------------------------------------------------------------------------------------------------ record

fn design_from_spec(w: &WInputs, spec: &Value) -> AssessResult<(WDesign, f64, (f64, f64))> {
    let inp = w.inp;
    let (ld, phi) = (f(&spec["intake"]["L_over_d"], "L/d")?, f(&spec["intake"]["phi"], "phi")?);
    let g = GEOMS.iter().position(|x| *x == (ld, phi)).ok_or_else(|| model_error("spec geometry"))?;
    let filter =
        FILTERS.iter().position(|x| Some(*x) == spec["filter"].as_str()).ok_or_else(|| model_error("spec filter"))?;
    let comp = inp
        .compressors
        .iter()
        .position(|c| Some(c.id.as_str()) == spec["compressor"]["id"].as_str())
        .ok_or_else(|| model_error("spec compressor"))?;
    let p = f(&spec["P_set_Pa"], "P_set")?;
    let target = TARGETS_PA.iter().position(|x| *x == p).ok_or_else(|| model_error("spec P_set"))?;
    let a_max = f(&spec["intake"]["A_max_m2"], "A_max")?;
    let n = spec["intake"]["N_segments"].as_u64().ok_or_else(|| model_error("spec N"))? as usize;
    let d = WDesign {
        g,
        filter,
        comp,
        a_max,
        n,
        target,
        o1: 0,
        o2: 0,
        log_width: 0.0,
        r_sus: 0.0,
        m_max: 0.0,
        d_max: 0.0,
        p_max: 0.0,
    };
    Ok((d, f(&spec["V_m3"], "V")?, (f(&spec["controller"]["Kp"], "Kp")?, f(&spec["controller"]["Ti_s"], "Ti")?)))
}

/// Detailed steady operating record at one operating point (steady_operating_point on the v1 chain).
fn op_detail(w: &WInputs, d: &WDesign, si: usize, i: usize, op: &Op, v: f64) -> AssessResult<Value> {
    let inp = w.inp;
    let a = w.aeff[op.a];
    let chain = Chain {
        intake: w.record_at(d.g, si, i, a),
        filt: inp.filter(FILTERS[d.filter])?.clone(),
        plant: inp.plant(&inp.compressors[d.comp], &NOMINAL)?,
        plenum: inp.plenum(v)?,
    };
    let r = steady_operating_point(&chain, &inp.up.materials, TARGETS_PA[d.target], 1.0, 1.0)?;
    let p_in = r["compressor_inlet_P_Pa"].as_f64().unwrap_or(f64::NAN);
    Ok(json!({
        "scenario": inp.up.scenarios[si], "state_id": inp.state_ids[i], "Phi_kg_m2_s": w.phi[i],
        "open_segments": op.j_open, "N_segments": d.n, "A_eff_m2": a,
        "capture_efficiency": w.cap[d.g][si][i] / w.phi[i],
        "mdot_captured_kg_s": w.cap[d.g][si][i] * a,
        "mdot_delivered_kg_s": op.mdot, "mdot_req_sustained_kg_s": op.req, "flow_ratio": op.mdot / op.req,
        "D_intake_N": op.d_tot - w.inp.q_pa[i] * w.cda_host_m2, "D_host_N": w.inp.q_pa[i] * w.cda_host_m2, "D_tot_N": op.d_tot,
        "P_compressor_el_W": op.p_el, "P_d_max_1350_W": w.pd1350(op.p_el), "m_compressor_kg": op.m,
        "compressor_inlet_P_Pa": fin(p_in), "pressure_ratio_P_set_over_inlet": fin(TARGETS_PA[d.target] / p_in),
        "steady_record": r
    }))
}

fn sched_interp(w: &WInputs, e: &WEval) -> Value {
    // Information: per condition, log-linear interpolation of the node max / min flux between nodes.
    let Some((k0, k1)) = e.run else { return Value::Null };
    let (lo, hi) = (w.phi[w.order[k0]], w.phi[w.order[k1]]);
    let mut m = Map::new();
    for (ci, c) in w.conds.iter().enumerate() {
        let pts: Vec<(f64, f64, f64)> = w
            .nodes
            .iter()
            .filter(|nd| nd.0 == ci)
            .map(|nd| {
                let mx = nd.2.iter().map(|&i| w.phi[i]).fold(0.0, f64::max);
                let mn = nd.2.iter().map(|&i| w.phi[i]).fold(f64::INFINITY, f64::min);
                (nd.1, mn, mx)
            })
            .collect();
        let mut ok_alts = vec![];
        let mut h = ALTITUDES_KM[0];
        while h <= ALTITUDES_KM[3] + 1e-9 {
            let k = pts.windows(2).position(|p| h >= p[0].0 && h <= p[1].0 + 1e-9).unwrap_or(0);
            let (a, b) = (pts[k], pts[k + 1]);
            let t = (h - a.0) / (b.0 - a.0);
            let li = |x: f64, y: f64| (x.ln() + t * (y.ln() - x.ln())).exp();
            let (mn, mx) = (li(a.1, b.1), li(a.2, b.2));
            if mn >= lo && mx <= hi {
                ok_alts.push(h);
            }
            h += 1.0;
        }
        m.insert(
            c.clone(),
            json!({"node_Phi_min_max": pts.iter().map(|p| json!({"alt_km": p.0, "Phi_min": p.1, "Phi_max": p.2})).collect::<Vec<_>>(),
                   "interpolated_admissible_km_1km_steps": if ok_alts.is_empty() { Value::Null } else {
                       json!([ok_alts[0], ok_alts[ok_alts.len() - 1]]) },
                   "n_interpolated_admissible_km": ok_alts.len()}),
        );
    }
    json!({"label": "INFORMATION (log-linear interpolation between registered nodes; not evaluated states)", "by_condition": Value::Object(m)})
}

/// The 196-state verification view: served or not, and the reason in the first failing scenario.
fn verification_view(w: &WInputs, e: &WEval) -> Value {
    let inp = w.inp;
    let mut counts: BTreeMap<&str, usize> = BTreeMap::new();
    let mut rows = vec![];
    let in_win = |i: usize| e.run.map(|(k0, k1)| w.pos[i] >= k0 && w.pos[i] <= k1).unwrap_or(false);
    for &i in &w.order {
        let reasons: BTreeMap<&str, usize> =
            e.ops[i].iter().filter_map(|o| o.err()).fold(BTreeMap::new(), |mut m, f| {
                *m.entry(f.as_str()).or_insert(0) += 1;
                m
            });
        let status = if in_win(i) {
            "IN_WINDOW"
        } else if e.served[i] {
            "SERVED_OUTSIDE_WINDOW"
        } else {
            "NOT_SERVED"
        };
        *counts.entry(status).or_insert(0) += 1;
        rows.push(json!({"state_id": inp.state_ids[i], "Phi_kg_m2_s": w.phi[i], "status": status,
            "failing_scenarios_by_reason": reasons}));
    }
    json!({"counts": counts, "states_in_flux_order": rows})
}

/// A record is written only from a full search: a development subset (`DCR001_W_DEV_*`) carries
/// `DEVELOPMENT_SUBSET_NOT_A_RECORD` and is refused, so a partial design space is never presented as the evaluation.
pub fn search_is_full_evaluation(search: &Value) -> AssessResult<()> {
    match search["label"].as_str() {
        Some(LABEL) => Ok(()),
        other => Err(AssessError::new(
            "ValueError",
            format!("DCR-001 v3 record: the search is not a full evaluation (label {other:?}); rerun without DCR001_W_DEV_*"),
        )),
    }
}

/// Prereg v3: "a Python non-S row sets the design aside and the next is taken". The record cannot take the next
/// design itself, so a selection with any non-S governed-reference row is refused (rows listed) and the search
/// moves on to the next ranked design.
pub fn python_reference_all_s(py: &Value) -> AssessResult<()> {
    let rows = py["rows"].as_array().ok_or_else(|| model_error("Python rows"))?;
    let non_s: Vec<Value> = rows
        .iter()
        .filter(|r| r["class"].as_str() != Some("S"))
        .map(|r| {
            json!({"coefficient_set": r["coefficient_set"], "scenario": r["scenario"], "state_id": r["state_id"],
            "class": r["class"]})
        })
        .collect();
    if non_s.is_empty() {
        Ok(())
    } else {
        Err(AssessError::new(
            "ValueError",
            format!(
                "DCR-001 v3 record: the governed Python reference has {} non-S rows, so the design is set aside \
                 (prereg v3) and the next ranked design is taken: {}",
                non_s.len(),
                Value::Array(non_s)
            ),
        ))
    }
}

/// The window record: pinned search, spec and Python reference (R2 on every row), selected-design detail and the
/// information items.
#[allow(clippy::too_many_arguments)]
pub fn window_record(
    w: &WInputs,
    repo: &Path,
    search_rel: &str,
    search_sha: &str,
    spec_rel: &str,
    spec_sha: &str,
    py_rel: &str,
    py_sha: &str,
    threads: usize,
) -> AssessResult<Value> {
    let inp = w.inp;
    let srch = jread(repo, search_rel, search_sha)?;
    let spec = jread(repo, spec_rel, spec_sha)?;
    let py = jread(repo, py_rel, py_sha)?;
    if srch["schema"].as_str() != Some(SEARCH_SCHEMA) || spec["schema"].as_str() != Some(SPEC_SCHEMA) {
        return Err(model_error("DCR-001 v3 record: search / spec schema"));
    }
    search_is_full_evaluation(&srch)?;
    if py["schema"].as_str() != Some(PY_SCHEMA) || py["spec"]["sha256"].as_str() != Some(spec_sha) {
        return Err(model_error("DCR-001 v3 record: Python reference schema or spec pin differs"));
    }
    if srch["selection"]["design_id"] != spec["design_id"] {
        return Err(model_error("DCR-001 v3 record: spec is not the search selection"));
    }
    let (d, v, ctrl) = design_from_spec(w, &spec)?;
    let o = if srch["selection"]["mass_relaxed_selection"].as_bool() == Some(true) {
        Opts { mass_limit: false, ..GOVERNING }
    } else {
        GOVERNING
    };
    // R2: Rust class on every spec row of every coefficient set equals the Python reference.
    let mut py_rows: HashMap<(String, String, String), PyRow> = HashMap::new();
    for r in py["rows"].as_array().ok_or_else(|| model_error("Python rows"))? {
        let s = |k: &str| r[k].as_str().unwrap_or("").to_string();
        let kinds = r["events"]
            .as_array()
            .map(|a| a.iter().map(|e| e["eq"].as_str().unwrap_or("").to_string()).collect())
            .unwrap_or_default();
        let a = r["area_m2"].as_f64().unwrap_or(f64::NAN);
        if py_rows.insert((s("coefficient_set"), s("scenario"), s("state_id")), (s("class"), kinds, a)).is_some() {
            return Err(model_error("Python reference: duplicate row"));
        }
    }
    let sets = coefficient_sets();
    let csets = spec["coefficient_sets"].as_array().ok_or_else(|| model_error("spec coefficient sets"))?;
    if csets.len() != sets.len() {
        return Err(model_error("spec coefficient sets differ from the registered sets"));
    }
    let rust = par_map(sets.len(), threads, |k| {
        let (name, coef) = &sets[k];
        if csets[k]["id"].as_str() != Some(name.as_str()) {
            return Err(model_error("spec coefficient set order"));
        }
        let mut ops = vec![];
        for r in csets[k]["rows"].as_array().ok_or_else(|| model_error("spec rows"))? {
            let si = inp.up.scenarios.iter().position(|x| Some(x.as_str()) == r["scenario"].as_str());
            let i = inp.state_ids.iter().position(|x| Some(x.as_str()) == r["state_id"].as_str());
            let (Some(si), Some(i)) = (si, i) else { return Err(model_error("spec row")) };
            let a = w.aidx(f(&r["area_m2"], "area")?);
            ops.push((si, i, Op { j_open: 0, a, d_tot: 0.0, mdot: 0.0, req: 0.0, p_el: 0.0, m: 0.0 }));
        }
        let fc = inp.filter(FILTERS[d.filter])?;
        let plant = inp.plant(&inp.compressors[d.comp], coef)?;
        let pl = inp.plenum(v)?;
        stab_rows(w, d.g, fc, &plant, &pl, controller(ctrl.0, ctrl.1), TARGETS_PA[d.target], &ops, false)
    })?;
    let (mut n_rows, mut n_agree) = (0usize, 0usize);
    let mut counts = Map::new();
    let mut disagreements = vec![];
    for ((name, _), rows) in sets.iter().zip(&rust) {
        let mut c: BTreeMap<&str, usize> = BTreeMap::new();
        for (si, i, a, class, kinds) in rows {
            n_rows += 1;
            *c.entry(class).or_insert(0) += 1;
            let key = (name.clone(), inp.up.scenarios[*si].clone(), inp.state_ids[*i].clone());
            let (pc, pk, pa) =
                py_rows.get(&key).ok_or_else(|| model_error(format!("Python reference: no row {key:?}")))?;
            let rk: Vec<String> = kinds.iter().map(|x| x.to_string()).collect();
            if pc == class && *pk == rk && (pa - a).abs() < 1e-12 {
                n_agree += 1;
            } else {
                disagreements.push(json!({"coefficient_set": name, "scenario": key.1, "state_id": key.2,
                    "rust": class, "python": pc}));
            }
        }
        counts.insert(name.clone(), json!(c));
    }
    if n_rows != py_rows.len() || n_agree != n_rows {
        return Err(model_error(format!(
            "R2: Rust / Python stability disagreement ({n_agree} of {n_rows} rows agree, Python {} rows): {}",
            py_rows.len(),
            Value::Array(disagreements)
        )));
    }
    python_reference_all_s(&py)?;
    let py_all_s = true;
    // Selected-design detail.
    let nominal = eval_at(w, &d, &NOMINAL, o)?;
    let ops = window_ops(w, &nominal);
    let (k0, k1) = nominal.run.ok_or_else(|| model_error("selected design has no window"))?;
    let (ilo, ihi) = (w.order[k0], w.order[k1]);
    let mut ends = vec![];
    for &(si, i, op) in &ops {
        if i == ilo || i == ihi {
            ends.push(op_detail(w, &d, si, i, &op, v)?);
        }
    }
    let a_used: Vec<f64> = ops.iter().map(|x| w.aeff[x.2.a]).collect();
    let (amin, amax) =
        (a_used.iter().cloned().fold(f64::INFINITY, f64::min), a_used.iter().cloned().fold(0.0f64, f64::max));
    let mut eta_by_sc = Map::new();
    let mut xo = (f64::INFINITY, 0.0f64);
    for (si, sc) in inp.up.scenarios.iter().enumerate() {
        let e: Vec<f64> = (k0..=k1).map(|q| w.cap[d.g][si][w.order[q]] / w.phi[w.order[q]]).collect();
        eta_by_sc.insert(
            sc.clone(),
            json!([e.iter().cloned().fold(f64::INFINITY, f64::min), e.iter().cloned().fold(0.0, f64::max)]),
        );
    }
    // Delivered composition over the window operating points (steady sweep of those rows).
    let fc = inp.filter(FILTERS[d.filter])?;
    let plant = inp.plant(&inp.compressors[d.comp], &NOMINAL)?;
    let pl = inp.plenum(v)?;
    for si in 0..inp.up.scenarios.len() {
        let recs: Vec<IntakeState> =
            ops.iter().filter(|x| x.0 == si).map(|x| w.record_at(d.g, si, x.1, w.aeff[x.2.a])).collect();
        if recs.is_empty() {
            continue;
        }
        let sw =
            steady_sweep(&intake_side(&recs, fc, 1.0)?, &plant, &pl, &inp.up.materials, &[TARGETS_PA[d.target]], None)?;
        for r in 0..recs.len() {
            let x = sw.x_s_flow_mole[0][r];
            if x.is_finite() {
                xo = (xo.0.min(x), xo.1.max(x));
            }
        }
    }
    // Information windows on the selected hardware.
    let mut info = Map::new();
    for eta in ETA_PLAN {
        let e = eval_at(w, &d, &NOMINAL, Opts { req: Req::Plan(eta), ..o })?;
        info.insert(format!("planning_eta_a_{}", py_format_g(eta)), window_value(w, &e));
    }
    let e = eval_at(w, &d, &NOMINAL, Opts { req: Req::VdBound, ..o })?;
    info.insert("V_d_bound_O_plus_350V".into(), window_value(w, &e));
    for h in HOST_SENSITIVITY_M2 {
        let e = eval_at(w, &d, &NOMINAL, Opts { cda_host: h, ..o })?;
        info.insert(format!("host_CDA_{}_m2", py_format_g(h)), window_value(w, &e));
    }
    // Mass-relaxed information on the selected (geometry, A_max, N, filter, P_set) over all S0 compressors.
    let mr = par_map(inp.compressors.len(), threads, |c| {
        let dd = WDesign { comp: c, ..d.clone() };
        let e = eval_at(w, &dd, &NOMINAL, Opts { mass_limit: false, ..o })?;
        Ok((e.o1, e.o2, e.log_width, e.m_max, c))
    })?;
    let best_mr = mr
        .iter()
        .filter(|x| x.0 > 0)
        .max_by(|a, b| (a.0, a.1).cmp(&(b.0, b.1)).then(a.2.total_cmp(&b.2)).then(b.3.total_cmp(&a.3)));
    info.insert(
        "mass_relaxed_on_selected_intake".into(),
        match best_mr {
            Some(b) => json!({"best_O1": b.0, "best_O2": b.1, "best_log_width": b.2, "m_compressor_max_kg": b.3,
                              "compressor": inp.compressors[b.4].id}),
            None => json!({"best_O1": 0}),
        },
    );
    let screen_log = if o.mass_limit { &srch["stability_screen"]["log"] } else { &srch["mass_relaxed"]["screen_log"] };
    let corners: Vec<Value> = screen_log
        .as_array()
        .and_then(|a| a.iter().find(|x| x.get("selected_design_id").is_some()).cloned())
        .map(|x| x["corners"].as_array().cloned().unwrap_or_default())
        .unwrap_or_default();
    let robust = srch["selection"]["robust"].as_bool() == Some(true) && py_all_s;
    let comp = &inp.compressors[d.comp];
    let record = json!({
        "schema": RECORD_SCHEMA,
        "dcr": "DCR-DBF1-001",
        "label": LABEL,
        "prereg": {"path": V3_REL, "sha256": V3_SHA256, "lock": {"path": V3_LOCK_REL, "sha256": V3_LOCK_SHA256}},
        "inputs": {
            "search": {"path": search_rel, "sha256": search_sha},
            "spec": {"path": spec_rel, "sha256": spec_sha},
            "python_reference": {"path": py_rel, "sha256": py_sha},
            "provenance": w.provenance.iter().map(|(p, s)| json!({"path": p, "sha256": s})).collect::<Vec<_>>(),
            "CDA_host_m2": w.cda_host_m2, "C_closed": C_CLOSED,
            "P_d_max_1350_ref_W": w.pd1350_ref_w, "P_d_max_1500_ref_W": w.pd1500_ref_w, "CP_NOM_W": w.cp_nom_w,
            "dPd_per_W_compressor": w.dpd_per_w, "compressor_headroom_W": w.headroom_w,
            "m_compressor_limit_kg": inp.m_comp_limit_kg, "T12_N": inp.t12_n, "T25_N": inp.t25_n
        },
        "selection": {
            "design_id": spec["design_id"],
            "mechanism": if d.n == 1 { "VC-0 fixed aperture" } else { "VC-1 segmented frontal aperture shutter" },
            "intake": {"A_max_m2": d.a_max, "N_segments": d.n, "L_over_d": GEOMS[d.g].0, "phi": GEOMS[d.g].1,
                       "channel_diameter": "collapsed (F1-02); 5-20 mm, set with the mechanical design",
                       "wall_area_2_phi_Amax_Ld_m2": 2.0 * GEOMS[d.g].1 * d.a_max * GEOMS[d.g].0,
                       "A_eff_used_m2": [amin, amax], "open_fraction_used": [amin / d.a_max, amax / d.a_max]},
            "filter": FILTERS[d.filter],
            "compressor": {"id": comp.id, "f3_grid_index": comp.grid_index, "design": Value::Object(comp.design.clone())},
            "plenum": {"V_m3": v, "wall": WALL, "P_set_Pa": TARGETS_PA[d.target]},
            "controller": {"Kp": ctrl.0, "Ti_s": ctrl.1, "f_valve_hz": crate::dcr001::F_VALVE_HZ, "authority": crate::dcr001::AUTHORITY},
            "robust": robust,
            "label": if robust { "ADMISSIBLE_ROBUST" } else { "ADMISSIBLE_CONDITIONAL_ON_COMPRESSOR_COEFFICIENTS" },
            "mass_relaxed_selection": !o.mass_limit,
        },
        "window": window_value(w, &nominal),
        "altitude_schedule_interpolated": sched_interp(w, &nominal),
        "window_operating_points": {
            "n": ops.len(),
            "capture_efficiency_min_max_by_scenario": eta_by_sc,
            "x_O_delivered_min_max": [fin(xo.0), fin(xo.1)],
            "window_end_points_detail": ends
        },
        "stability": {"governed_python_reference_all_S": py_all_s, "R2_rows_agree": n_agree, "rows": n_rows,
                      "rust_class_counts_by_coefficient_set": counts, "corners_screen": corners},
        "verification_set_196": verification_view(w, &nominal),
        "information": info,
    });
    Ok(record)
}

/// Cross-check: the window harness at the DBF-1 point reproduces the v1 harness on every non-pruned row exactly, and
/// pruned rows fail the necessary condition; side(A) = A side(1) to 1e-12.
pub fn crosscheck_window(w: &WInputs) -> AssessResult<Value> {
    let inp = w.inp;
    let g = GEOMS.iter().position(|x| *x == (20.0, 0.9)).expect("g");
    let fi = 0;
    let fc = inp.filter(FILTERS[fi])?;
    let plant = inp.up.plant(&inp.dbf1.upstream.compressor).map_err(de)?.clone();
    let pl = inp.plenum(VOLUMES_M3[0])?;
    let t = eval_table(w, g, fc, &plant, &pl, w.cda_host_m2)?;
    let ai = w.aidx(0.25);
    let it = Intake { area: 0.25, g };
    let j = TARGETS_PA.iter().position(|x| *x == 0.02).expect("0.02");
    let (mut n_cmp, mut n_eq, mut n_pruned_ok) = (0, 0, 0);
    for si in 0..inp.up.scenarios.len() {
        let side = intake_side(&inp.records(&it, si), fc, 1.0)?;
        let sw = steady_sweep(&side, &plant, &pl, &inp.up.materials, &TARGETS_PA, None)?;
        for (i, &fi1) in inp.req_f1.iter().enumerate() {
            let idx = fi1 * TARGETS_PA.len() + j;
            let margin = sw.p_deadhead_pa[idx] / TARGETS_PA[j] - 1.0;
            let ok = sw.bits[idx] == 0 && sw.in_domain[idx] && margin > 0.0;
            let mine = t.get(j, si, i, ai);
            if row_can_operate(w, g, si, i, 0.25, w.cda_host_m2)? {
                n_cmp += 1;
                let same = match mine {
                    None => !ok,
                    Some(p) => ok && p.mdot == sw.mdot_total_kgps[idx] && p.p_el == sw.p_el_w[idx],
                };
                if same {
                    n_eq += 1;
                }
            } else if mine.is_none() {
                n_pruned_ok += 1;
            }
        }
    }
    // F1-02 linearity of the intake side.
    let mut max_rel: f64 = 0.0;
    for si in [0usize, 4, 9] {
        let r1 = w.record_at(g, si, 0, 1.0);
        let ra = w.record_at(g, si, 0, 0.375);
        let (f1, e1) = intake_side(&[r1], fc, 1.0)?;
        let (fa, ea) = intake_side(&[ra], fc, 1.0)?;
        for k in 0..3 {
            max_rel = max_rel.max((fa[0][k] / (0.375 * f1[0][k]) - 1.0).abs());
            max_rel = max_rel.max((ea[0][k] / (0.375 * e1[0][k]) - 1.0).abs());
        }
    }
    let pass = n_cmp == n_eq && max_rel <= 1e-12;
    Ok(json!({"status": if pass { "PASS" } else { "FAIL" }, "dbf1_rows_compared": n_cmp, "dbf1_rows_identical": n_eq,
              "pruned_rows_without_point": n_pruned_ok, "side_linearity_max_rel": max_rel}))
}

/// Development diagnostic (never a record): outcome counts, served states per node and the window of one design.
pub fn diag_design(w: &WInputs, d: &WDesign, o: Opts) -> AssessResult<Value> {
    let e = eval_at(w, d, &NOMINAL, o)?;
    let mut by_reason: BTreeMap<String, usize> = BTreeMap::new();
    let mut served_by_node: BTreeMap<String, (usize, usize)> = BTreeMap::new();
    for (i, row) in e.ops.iter().enumerate() {
        for r in row {
            let k = match r {
                Ok(_) => "OK".to_string(),
                Err(f) => f.as_str().to_string(),
            };
            *by_reason.entry(k).or_insert(0) += 1;
        }
        let ent = served_by_node.entry(format!("{}:{}", w.conds[w.cond[i]], w.alt_km[i])).or_insert((0, 0));
        ent.1 += 1;
        if e.served[i] {
            ent.0 += 1;
        }
    }
    let cap = e.cap25.iter().filter(|c| **c != 0).count();
    Ok(json!({"design": d.id(w.inp), "rows_by_outcome": by_reason, "served_by_node": served_by_node,
        "states_with_cap25": cap, "window": window_value(w, &e)}))
}

/// Development probe (never a record): steady reason bits per target over the A_eff grid for one state / scenario.
pub fn probe(w: &WInputs, g: usize, fi: usize, ci: usize, si: usize, i: usize) -> AssessResult<Value> {
    let inp = w.inp;
    let fc = inp.filter(FILTERS[fi])?;
    let plant = inp.plant(&inp.compressors[ci], &NOMINAL)?;
    let pl = inp.plenum(VOLUMES_M3[0])?;
    let recs: Vec<IntakeState> = w.aeff.iter().map(|&a| w.record_at(g, si, i, a)).collect();
    let side = intake_side(&recs, fc, 1.0)?;
    let sw = steady_sweep(&side, &plant, &pl, &inp.up.materials, &TARGETS_PA, None)?;
    let m = TARGETS_PA.len();
    let rows: Vec<Value> = w
        .aeff
        .iter()
        .enumerate()
        .map(|(r, a)| {
            let t: Vec<Value> = (0..m)
                .map(|j| {
                    let idx = r * m + j;
                    json!({"P": TARGETS_PA[j], "bits": abep_gaspath::plenum_feed::reasons_from_bits(sw.bits[idx]),
                           "p_dead": sw.p_deadhead_pa[idx], "mdot": fin(sw.mdot_total_kgps[idx]), "P_el": fin(sw.p_el_w[idx]),
                           "m": fin(sw.m_compressor_kg[idx])})
                })
                .collect();
            json!({"A_eff": a, "captured": w.cap[g][si][i] * a, "D_open": w.d_tot(g, si, i, *a, *a, w.cda_host_m2),
                   "req12": w.req(Req::Necessary, inp.t12_n, i, *a, 10.0, false).unwrap_or(f64::NAN), "targets": t})
        })
        .collect();
    Ok(json!({"state": inp.state_ids[i], "scenario": inp.up.scenarios[si], "Phi": w.phi[i], "q": inp.q_pa[i],
              "compressor": inp.compressors[ci].id, "rows": rows}))
}

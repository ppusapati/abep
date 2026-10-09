//! DCR-DBF1-003 evaluation (co-located RF match thermal failure of P7 v2) under
//! `docs/baseline/DCR-003/dcr003_eval_prereg_v1.json` (lock `dcr003_eval_prereg_lock_v1.json`): route R-1 (the match
//! stays co-located, isolated from the ICP bracket by standoffs, with its own radiator and its RF lead to the antenna
//! as a registered link; no DCR) against route R-2 (the match at the RF generator, N_MATCH absent; DBF-1.1).
//!
//! Additive to the P7 harness: the same case builder, run rule, limits, margin rule, heater bisection and boundary-unit
//! rule; the routes only edit the network section (links, surfaces, nodes) and the match-loss fraction of the loaded
//! context, per the preregistration. The RF-chain penalty of R-2 uses the transmission-line relation registered there.

use super::assess::*;
use super::{num, ClosureError, Context, MARGIN_K};
use abep_provenance::sha256_hex;
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::path::Path;

pub const DCR_PREREG_PATH: &str = "docs/baseline/DCR-003/dcr003_eval_prereg_v1.json";
pub const DCR_LOCK_PATH: &str = "docs/baseline/DCR-003/dcr003_eval_prereg_lock_v1.json";
pub const INPUTS_PATH: &str = "docs/closure/thermal/thermal_load_inputs_v2.json";
pub const V2_RECORD_PATH: &str = "docs/closure/thermal/thermal_closure_v2.json";
pub const LEDGER_PATH: &str = "docs/closure/power/power_ledger_v1.json";
pub const SCHEMA: &str = "abep_dcr003_evaluation_v1";
const HOT: [&str; 4] = ["TC1-HOT-H-BSTAR", "TC2-HOT-H-B0", "TC3-HOT-I-BSTAR", "TC4-HOT-I-B0"];
const COLD_OP: &str = "TC5-COLD-OP-B0";
const COLD_NONOP: &str = "TC6-COLD-NONOP-B0";
const MATCH: &str = "N_MATCH";
const F_HZ: f64 = 13.56e6;
const Z0: f64 = 50.0;

/// The verified DCR-003 preregistration and the files it pins.
pub struct Dcr {
    pub raw: Value,
    pub sha256: String,
    pub lock_sha256: String,
    pub v2: Value,
    pub ledger: Value,
}

fn read(root: &Path, rel: &str) -> Result<Vec<u8>, ClosureError> {
    std::fs::read(root.join(rel)).map_err(|e| ClosureError(format!("{rel}: {e}")))
}

fn parse(bytes: &[u8], what: &str) -> Result<Value, ClosureError> {
    serde_json::from_slice(bytes).map_err(|e| ClosureError(format!("{what}: {e}")))
}

impl Dcr {
    /// Load the preregistration; every file of the lock must match its sha256 (fail closed).
    pub fn load(root: &Path) -> Result<Dcr, ClosureError> {
        let lock_bytes = read(root, DCR_LOCK_PATH)?;
        let lock = parse(&lock_bytes, "lock")?;
        let files = lock["files"].as_object().ok_or_else(|| ClosureError("lock: files".into()))?;
        for req in [DCR_PREREG_PATH, INPUTS_PATH, V2_RECORD_PATH, LEDGER_PATH, super::PREREG_PATH] {
            if !files.contains_key(req) {
                return Err(ClosureError(format!("lock does not pin {req}")));
            }
        }
        for (rel, sha) in files {
            let got = sha256_hex(&read(root, rel)?);
            if sha.as_str() != Some(got.as_str()) {
                return Err(ClosureError(format!("{rel} sha256 {got} differs from the lock")));
            }
        }
        let pre = read(root, DCR_PREREG_PATH)?;
        Ok(Dcr {
            raw: parse(&pre, "prereg")?,
            sha256: sha256_hex(&pre),
            lock_sha256: sha256_hex(&lock_bytes),
            v2: parse(&read(root, V2_RECORD_PATH)?, "v2 record")?,
            ledger: parse(&read(root, LEDGER_PATH)?, "power ledger")?,
        })
    }

    fn r1(&self) -> &Value {
        &self.raw["routes"]["R-1"]
    }

    fn r2(&self) -> &Value {
        &self.raw["routes"]["R-2"]
    }
}

// ------------------------------------------------------------------------------------------------ network edits

/// The unedited network and match-loss input of the loaded P7 context.
#[derive(Clone)]
pub struct Base {
    nodes: Vec<Value>,
    surfaces: Vec<Value>,
    enclosures: Vec<Value>,
    links: Vec<Value>,
    model: Value,
    raw: Value,
    inputs: Value,
}

impl Base {
    pub fn of(ctx: &Context) -> Base {
        Base {
            nodes: ctx.prereg.nodes.clone(),
            surfaces: ctx.prereg.surfaces.clone(),
            enclosures: ctx.prereg.enclosures.clone(),
            links: ctx.prereg.links.clone(),
            model: ctx.prereg.model.clone(),
            raw: ctx.prereg.raw.clone(),
            inputs: ctx.inputs.clone(),
        }
    }

    fn restore(&self, ctx: &mut Context) {
        ctx.prereg.nodes = self.nodes.clone();
        ctx.prereg.surfaces = self.surfaces.clone();
        ctx.prereg.enclosures = self.enclosures.clone();
        ctx.prereg.links = self.links.clone();
        ctx.prereg.model = self.model.clone();
        ctx.prereg.raw = self.raw.clone();
        ctx.inputs = self.inputs.clone();
    }
}

/// One R-1 network point: match radiator area, isolator and lead conductances, match-loss fraction.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct R1Point {
    pub a_ma: f64,
    pub g_iso: f64,
    pub g_lead: f64,
    pub q_match_frac: f64,
}

/// Apply R-1 to `ctx` (from `base`): L_MA_MO = G_iso, S_MA area = A_MA, new link L_MA_ANT = G_lead, Q_match_frac.
pub fn apply_r1(ctx: &mut Context, base: &Base, p: R1Point) -> Result<(), ClosureError> {
    base.restore(ctx);
    let mut found = false;
    for l in ctx.prereg.links.iter_mut() {
        if l["id"].as_str() == Some("L_MA_MO") {
            l["G_W_K"] = json!(p.g_iso);
            l["derivation"] = json!("DCR-003 R-1: Ti-6Al-4V isolator standoffs G_iso (dcr003_eval_prereg_v1)");
            found = true;
        }
    }
    if !found {
        return Err(ClosureError("R-1: link L_MA_MO not registered".into()));
    }
    ctx.prereg.links.push(json!({
        "id": "L_MA_ANT", "type": "LUMPED_G", "a": MATCH, "b": "N_ANTENNA", "G_W_K": p.g_lead,
        "evidence_class": "assumed",
        "derivation": "DCR-003 R-1: RF output lead pair match -> antenna, copper-plated 304 tube (dcr003_eval_prereg_v1)",
    }));
    let sf = ctx
        .prereg
        .surfaces
        .iter_mut()
        .find(|s| s["id"].as_str() == Some("S_MA"))
        .ok_or_else(|| ClosureError("R-1: surface S_MA not registered".into()))?;
    sf["area_m2"] = json!(p.a_ma);
    ctx.inputs["icp"]["Q_match_frac"]["value"] = json!(p.q_match_frac);
    Ok(())
}

/// Apply R-2 to `ctx` (from `base`): N_MATCH absent with its surface, enclosure, links and limit; match_colocated false.
pub fn apply_r2(ctx: &mut Context, base: &Base) {
    base.restore(ctx);
    let p = &mut ctx.prereg;
    p.nodes.retain(|n| n["id"].as_str() != Some(MATCH));
    p.surfaces.retain(|s| s["node"].as_str() != Some(MATCH));
    p.enclosures.retain(|e| e["id"].as_str() != Some("E_MATCH"));
    p.links.retain(|l| l["a"].as_str() != Some(MATCH) && l["b"].as_str() != Some(MATCH));
    p.model["match_colocated"] = json!(false);
    p.raw["model"]["match_colocated"] = json!(false);
    if let Some(l) = p.raw["limits"].as_array_mut() {
        l.retain(|x| x["node"].as_str() != Some(MATCH));
    }
}

// ------------------------------------------------------------------------------------------------ RF line (R-2)

/// Power reaching a load of impedance `r + jx` through a 50-Ohm line of matched loss `ml_db`, per unit input power:
/// a (1 - |G|^2) / (a^2 - |G|^2), a = 10^(ml / 10) (registered relation of the R-2 penalty model).
pub fn line_efficiency(r_ohm: f64, x_ohm: f64, ml_db: f64) -> f64 {
    let g2 = ((r_ohm - Z0).powi(2) + x_ohm.powi(2)) / ((r_ohm + Z0).powi(2) + x_ohm.powi(2));
    let a = 10f64.powf(ml_db / 10.0);
    a * (1.0 - g2) / (a * a - g2)
}

/// Wheeler single-layer coil inductance [H] (radius and length in metres).
pub fn wheeler_inductance_h(radius_m: f64, length_m: f64, turns: f64) -> f64 {
    let (r, l) = (radius_m / 0.0254, length_m / 0.0254);
    r * r * turns * turns / (9.0 * r + 10.0 * l) * 1e-6
}

fn ledger_slopes(ledger: &Value) -> Result<(f64, f64), ClosureError> {
    let rows = ledger["rf_trade_line"].as_array().ok_or_else(|| ClosureError("ledger rf_trade_line".into()))?;
    let at = |p: f64| rows.iter().find(|r| r["P_fwd_W"].as_f64() == Some(p));
    let (a, b) = (at(200.0), at(300.0));
    let (Some(a), Some(b)) = (a, b) else { return Err(ClosureError("ledger rf_trade_line 200 / 300 W".into())) };
    let dbus = (num(b, "P_bus_icp_W")? - num(a, "P_bus_icp_W")?) / 100.0;
    let dpd =
        (num(&b["P_d_max_W"], "design_allocation_1350")? - num(&a["P_d_max_W"], "design_allocation_1350")?) / 100.0;
    Ok((dbus, dpd))
}

fn ledger_term(ledger: &Value, id: &str) -> Result<f64, ClosureError> {
    ledger["terms"]
        .as_array()
        .and_then(|t| t.iter().find(|x| x["id"].as_str() == Some(id)))
        .and_then(|x| x["value"].as_f64())
        .ok_or_else(|| ClosureError(format!("ledger term {id}")))
}

fn p_nom(ledger: &Value) -> Result<&Value, ClosureError> {
    ledger["points"]
        .as_array()
        .and_then(|p| p.iter().find(|x| x["id"].as_str() == Some("P-NOM")))
        .ok_or_else(|| ClosureError("ledger P-NOM".into()))
}

/// The R-2 RF-chain penalty at every registered corner (pure arithmetic on the preregistered model).
pub fn r2_rf_penalty(dcr: &Dcr, ctx: &Context) -> Result<Value, ClosureError> {
    let m = &dcr.r2()["rf_penalty_model"];
    let l_a = wheeler_inductance_h(0.075, 0.036, 3.0);
    let x_ref = 2.0 * std::f64::consts::PI * F_HZ * l_a;
    let (dbus, dpd) = ledger_slopes(&dcr.ledger)?;
    let margin_rfp = num(p_nom(&dcr.ledger)?, "margin_to_rfp_W")?;
    let f_match = input(ctx, "icp.Q_match_frac")?;
    let (eta_rf, refl, p_dc) =
        (input(ctx, "icp.eta_RF")?, input(ctx, "icp.P_refl_frac")?, input(ctx, "icp.P_matching_DC_W")?);
    let p_anchor = input(ctx, "icp.P_fwd_anchor_W")?;
    let p_max = input(ctx, "icp.P_fwd_max_W")?;
    let env_end = p_max;
    let units = &ctx.prereg.raw["boundary_units"]["units"]["RF_GENERATOR"];
    let t_d = num(units, "upper_limit_C")? - MARGIN_K + K0;
    let q_hot = zenith_q(ctx, true, 0.17)?;
    let mut out = Map::new();
    let corners = m["corners"].as_object().ok_or_else(|| ClosureError("R-2 corners".into()))?;
    for (name, c) in corners {
        let (r_a, xf, alpha, len) = (num(c, "R_A")?, num(c, "X_factor")?, num(c, "alpha")?, num(c, "length")?);
        let x_a = x_ref * xf;
        let ml = alpha * len;
        let eta = line_efficiency(r_a, x_a, ml);
        let g2 = ((r_a - Z0).powi(2) + x_a.powi(2)) / ((r_a + Z0).powi(2) + x_a.powi(2));
        let mut pts = Map::new();
        for (pname, p1) in [("anchor", p_anchor), ("envelope_end", p_max)] {
            let p2 = p1 / eta;
            let dp = p2 - p1;
            let diss = p2 * (1.0 / eta_rf - 1.0) + refl * p2 + f_match * p2 + p_dc + (1.0 - f_match) * p2 * (1.0 - eta);
            let q_unit = 1.2 * diss;
            let net = eps_sigma_t4(0.92, t_d) - q_hot;
            pts.insert(
                pname.into(),
                json!({
                    "P_fwd_R1_W": p1, "P_fwd_R2_W": p2, "dP_fwd_W": dp,
                    "within_DBF1_RF_02_envelope_500W": p2 <= env_end,
                    "dP_bus_W": dp * dbus, "dP_d_max_at_1350W_W": dp * dpd,
                    "line_loss_W": (1.0 - f_match) * p2 * (1.0 - eta),
                    "RF_GENERATOR_unit_Q_hot_W": q_unit,
                    "RF_GENERATOR_radiator_area_m2": if net > 0.0 { Some(q_unit / net) } else { None },
                }),
            );
        }
        out.insert(
            name.clone(),
            json!({
                "R_A_Ohm": r_a, "X_A_Ohm": x_a, "L_A_uH": l_a * xf * 1e6, "matched_loss_dB": ml,
                "load_reflection_mag2": g2, "VSWR": (1.0 + g2.sqrt()) / (1.0 - g2.sqrt()),
                "eta_line": eta, "points": pts,
            }),
        );
    }
    let cons = &out["CONSERVATIVE"]["points"]["anchor"];
    let r2b = cons["within_DBF1_RF_02_envelope_500W"].as_bool() == Some(true);
    let r2c = cons["dP_bus_W"].as_f64().is_some_and(|d| d <= margin_rfp);
    Ok(json!({
        "antenna_inductance_reference_uH": l_a * 1e6,
        "antenna_reactance_reference_Ohm": x_ref,
        "ledger_slopes": {"dP_bus_per_W_fwd": dbus, "dP_d_max_per_W_fwd": dpd, "P_NOM_margin_to_1500W_W": margin_rfp},
        "corners": out,
        "R2-b_conservative_anchor_within_envelope": r2b,
        "R2-c_conservative_anchor_dP_bus_within_P_NOM_RFP_margin": r2c,
    }))
}

// ------------------------------------------------------------------------------------------------ verdicts

fn temps_c(m: &BTreeMap<String, f64>) -> Value {
    Value::Object(m.iter().map(|(k, v)| (k.clone(), json!(v - K0))).collect())
}

fn run_json(r: &CaseRun) -> Value {
    json!({
        "case_id": r.id,
        "run_status": serde_json::to_value(r.status).unwrap_or(Value::Null),
        "status_reasons": r.reasons,
        "T_max_C": temps_c(&r.t_max_k),
        "T_min_C": temps_c(&r.t_min_k),
        "Q_into_spacecraft_W": r.q_sc_w,
        "case_document_sha256": r.case_sha256,
    })
}

/// Node verdicts over the governing hot runs (the P7 margin rule) compared with the v2 record.
fn verdicts(lims: &[Limit], runs: &BTreeMap<String, CaseRun>, v2: &Value) -> (Map<String, Value>, Vec<String>) {
    let mut rows = Map::new();
    let mut worsened = Vec::new();
    for lim in lims {
        let mut t_max: Option<f64> = None;
        let mut all = true;
        for id in HOT {
            let r = &runs[id];
            match r.t_max_k.get(&lim.node).filter(|_| r.converged()) {
                Some(t) => t_max = Some(t_max.map_or(*t, |m: f64| m.max(*t))),
                None => all = false,
            }
        }
        let t_c = if all { t_max.map(|t| t - K0) } else { None };
        let verdict = match (t_c, lim.upper_c) {
            (None, _) => "NOT_EVALUATED",
            (Some(t), Some(u)) if t <= u - MARGIN_K => "PASS",
            (Some(_), Some(_)) => "FAIL",
            (Some(t), None) if lim.absolute_c.is_some_and(|a| t + MARGIN_K > a) => "FAIL",
            (Some(_), None) => "REQUIREMENT",
        };
        let old = &v2["nodes"][&lim.node];
        let old_v = old["verdict"].as_str().unwrap_or("");
        if (old_v == "PASS" || old_v == "REQUIREMENT") && verdict != old_v {
            worsened.push(lim.node.clone());
        }
        let old_t = old["T_max_hot_C"].as_f64();
        rows.insert(
            lim.node.clone(),
            json!({
                "limit_class": lim.class, "design_ceiling_C": lim.upper_c.map(|u| u - MARGIN_K),
                "T_max_hot_C": t_c, "margin_K": t_c.and_then(|t| lim.upper_c.map(|u| u - MARGIN_K - t)),
                "verdict": verdict,
                "required_continuous_use_capability_C": if lim.upper_c.is_none() { t_c.map(|t| t + MARGIN_K) } else { None },
                "v2_verdict": old_v, "v2_T_max_hot_C": old_t,
                "delta_T_vs_v2_K": match (t_c, old_t) { (Some(a), Some(b)) => Some(a - b), _ => None },
            }),
        );
    }
    (rows, worsened)
}

fn triggers_fired(ctx: &Context, rows: &Map<String, Value>) -> Vec<Value> {
    let mut fired = Vec::new();
    for tr in ctx.prereg.raw["materials_screening"]["dcr_triggers"].as_array().cloned().unwrap_or_default() {
        let n = tr["node"].as_str().unwrap_or("");
        let t = rows.get(n).and_then(|r| r["T_max_hot_C"].as_f64());
        if t.is_some_and(|x| x > tr["above_C"].as_f64().unwrap_or(f64::INFINITY)) {
            fired.push(json!({"id": tr["id"], "node": n, "T_max_hot_C": t}));
        }
    }
    fired
}

fn q_sc_max(runs: &BTreeMap<String, CaseRun>) -> Option<f64> {
    let q = HOT.iter().filter_map(|id| runs[*id].q_sc_w).fold(f64::NEG_INFINITY, f64::max);
    q.is_finite().then_some(q)
}

fn hall_variant(dcr: &Dcr) -> Result<Variant, ClosureError> {
    let h = &dcr.raw["common"]["hall_radiator"];
    Ok(Variant { a_rh: num(h, "A_RH_m2")?, g_rh: num(h, "G_RH_W_K")?, ..Default::default() })
}

fn case_ids(ctx: &Context) -> Vec<String> {
    ctx.prereg.raw["cases"]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .filter_map(|c| c["id"].as_str().map(String::from))
        .collect()
}

/// Heater on N_MATCH to reach `low` [degC] in `case` (P7 heater-sizing rule); Some(0) when not needed.
fn heater(ctx: &Context, base: &Variant, case: &str, low: f64, run: &CaseRun) -> Result<Option<f64>, ClosureError> {
    let t = run.t_min_k.get(MATCH).filter(|_| run.converged()).map(|t| t - K0);
    Ok(match t {
        Some(t) if t >= low => Some(0.0),
        Some(_) => bisect(
            |q| {
                let v = Variant { heater: Some((MATCH.to_string(), q)), ..base.clone() };
                let rr = run_named(ctx, case, &v)?;
                Ok(rr.converged() && rr.t_min_k.get(MATCH).is_some_and(|t| t - K0 < low))
            },
            200.0,
            0.05,
            40,
        )?
        .map(|x| x + 0.05),
        None => None,
    })
}

fn corner(c: &Value, a_ma: f64, gi: f64, gl: f64) -> Result<R1Point, ClosureError> {
    Ok(R1Point { a_ma, g_iso: gi, g_lead: gl, q_match_frac: num(c, "Q_match_frac")? })
}

fn list(v: &Value) -> Vec<f64> {
    v.as_array().cloned().unwrap_or_default().iter().filter_map(Value::as_f64).collect()
}

// ------------------------------------------------------------------------------------------------ routes

/// Route R-1: grid, selection, every case at the selected radiator area, cold corners, allowable, T_SC sensitivity.
pub fn evaluate_r1(ctx: &mut Context, base: &Base, dcr: &Dcr) -> Result<Value, ClosureError> {
    let r1 = dcr.r1();
    let hv = hall_variant(dcr)?;
    let hot = &r1["corners"]["HOT"];
    let (gi_hot, gl_hot) = (num(hot, "G_iso")?, num(hot, "G_lead")?);
    let grid = list(&r1["design_lever"]["A_MA_m2_grid"]);
    apply_r1(ctx, base, corner(hot, grid[0], gi_hot, gl_hot)?)?;
    let lims = limits(ctx);
    let limited: Vec<Limit> = lims.iter().filter(|l| l.upper_c.is_some()).cloned().collect();
    let match_lim =
        lims.iter().find(|l| l.node == MATCH).cloned().ok_or_else(|| ClosureError("N_MATCH limit".into()))?;

    // 1-2. Grid (TC1, TC3 steady, HOT corner) and selection.
    let mut rows = Vec::new();
    let mut feasible = Vec::new();
    let mut best: Option<(f64, f64)> = None;
    for &a in &grid {
        apply_r1(ctx, base, corner(hot, a, gi_hot, gl_hot)?)?;
        let c1 = run_named(ctx, "TC1-HOT-H-BSTAR", &hv)?;
        let c3 = run_named(ctx, "TC3-HOT-I-BSTAR", &hv)?;
        let all_ok = limited.iter().all(|l| node_ok(&c1, l) && node_ok(&c3, l));
        let m = [&c1, &c3]
            .iter()
            .filter_map(|r| r.t_max_k.get(MATCH).filter(|_| r.converged()).and_then(|t| margin(&match_lim, *t)))
            .reduce(f64::min);
        if let Some(m) = m {
            if best.is_none_or(|b| m > b.1) {
                best = Some((a, m));
            }
        }
        if all_ok {
            feasible.push(a);
        }
        rows.push(json!({
            "A_MA_m2": a, "feasible": all_ok, "N_MATCH_min_margin_K": m,
            "TC1": {"status": serde_json::to_value(c1.status).unwrap_or(Value::Null), "T_max_C": temps_c(&c1.t_max_k), "Q_into_spacecraft_W": c1.q_sc_w},
            "TC3": {"status": serde_json::to_value(c3.status).unwrap_or(Value::Null), "T_max_C": temps_c(&c3.t_max_k), "Q_into_spacecraft_W": c3.q_sc_w},
        }));
    }
    let mut confirmations = Vec::new();
    let mut selected: Option<f64> = None;
    for &a in &feasible {
        apply_r1(ctx, base, corner(hot, a, gi_hot, gl_hot)?)?;
        let c2 = run_named(ctx, "TC2-HOT-H-B0", &hv)?;
        let c4 = run_named(ctx, "TC4-HOT-I-B0", &hv)?;
        let ok = limited.iter().all(|l| node_ok(&c2, l) && node_ok(&c4, l));
        confirmations.push(json!({"A_MA_m2": a, "confirmed": ok,
            "TC2_N_MATCH_C": c2.t_max_k.get(MATCH).map(|t| t - K0), "TC4_N_MATCH_C": c4.t_max_k.get(MATCH).map(|t| t - K0)}));
        if ok {
            selected = Some(a);
            break;
        }
    }
    let (a_sel, basis) = match selected {
        Some(a) => (a, "FEASIBLE_CONFIRMED"),
        None => (best.map(|b| b.0).unwrap_or(grid[0]), "NO_FEASIBLE_POINT_MAX_N_MATCH_MARGIN"),
    };

    // 3. Every case at the selected area: HOT corner for hot cases.
    apply_r1(ctx, base, corner(hot, a_sel, gi_hot, gl_hot)?)?;
    let mut runs: BTreeMap<String, CaseRun> = BTreeMap::new();
    for id in case_ids(ctx) {
        if id == COLD_OP || id == COLD_NONOP {
            continue;
        }
        runs.insert(id.clone(), run_named(ctx, &id, &hv)?);
    }
    // Cold corners (TC5, TC6) with heater sizing; the governing cold result is the worst corner.
    let cold = &r1["corners"]["COLD"];
    let mut cold_rows = Vec::new();
    let mut worst: BTreeMap<&str, (f64, Option<f64>, bool)> = BTreeMap::new();
    for gi in list(&cold["G_iso"]) {
        for gl in list(&cold["G_lead"]) {
            apply_r1(ctx, base, corner(cold, a_sel, gi, gl)?)?;
            for (case, low) in [(COLD_OP, match_lim.lower_op_c), (COLD_NONOP, match_lim.lower_nonop_c)] {
                let low = low.ok_or_else(|| ClosureError("N_MATCH lower limit".into()))?;
                let r = run_named(ctx, case, &hv)?;
                let h = heater(ctx, &hv, case, low, &r)?;
                let t = r.t_min_k.get(MATCH).filter(|_| r.converged()).map(|t| t - K0);
                let e = worst.entry(case).or_insert((f64::INFINITY, Some(0.0), true));
                e.0 = e.0.min(t.unwrap_or(f64::NEG_INFINITY));
                e.1 = match (e.1, h) {
                    (Some(a), Some(b)) => Some(a.max(b)),
                    _ => None,
                };
                e.2 &= r.converged();
                cold_rows.push(json!({"case": case, "G_iso": gi, "G_lead": gl, "run": run_json(&r), "N_MATCH_T_min_C": t, "lower_limit_C": low, "heater_W": h}));
                // The registered cold-case node temperatures (for the other nodes) come from the low/low corner.
                if !runs.contains_key(case) {
                    runs.insert(case.to_string(), r);
                }
            }
        }
    }
    apply_r1(ctx, base, corner(hot, a_sel, gi_hot, gl_hot)?)?;
    let (nodes, worsened) = verdicts(&lims, &runs, &dcr.v2);
    let fired = triggers_fired(ctx, &nodes);
    let match_row = nodes.get(MATCH).cloned().unwrap_or(Value::Null);
    let r1a = selected.is_some() && match_row["verdict"].as_str() == Some("PASS");
    let r1b = worst.values().all(|w| w.2 && w.1.is_some());
    let r1c = worsened.iter().all(|n| n == MATCH) && fired.is_empty();

    // 4. AL-QMATCH, NOMINAL corner, T_SC sensitivity.
    let al_q = bisect(
        |q| {
            apply_r1(ctx, base, R1Point { a_ma: a_sel, g_iso: gi_hot, g_lead: gl_hot, q_match_frac: q })?;
            let r = run_named(ctx, "TC3-HOT-I-BSTAR", &hv)?;
            Ok(node_ok(&r, &match_lim))
        },
        0.5,
        0.0005,
        40,
    )?;
    let nom = &r1["corners"]["NOMINAL"];
    apply_r1(ctx, base, corner(nom, a_sel, num(nom, "G_iso")?, num(nom, "G_lead")?)?)?;
    let mut nominal = Map::new();
    for id in ["TC1-HOT-H-BSTAR", "TC3-HOT-I-BSTAR"] {
        nominal.insert(id.into(), run_json(&run_named(ctx, id, &hv)?));
    }
    apply_r1(ctx, base, corner(hot, a_sel, gi_hot, gl_hot)?)?;
    let mut icd_change = false;
    let mut tsc = Map::new();
    for t_sc in [293.15, 313.15] {
        let v = Variant { t_sc_override: Some(t_sc), ..hv.clone() };
        for id in ["TC1-HOT-H-BSTAR", "TC3-HOT-I-BSTAR"] {
            let r = run_named(ctx, id, &v)?;
            if limited.iter().any(|l| node_ok(&r, l) != node_ok(&runs[id], l)) {
                icd_change = true;
            }
            tsc.insert(
                format!("T_SC_{t_sc}/{id}"),
                json!({"N_MATCH_C": r.t_max_k.get(MATCH).map(|t| t - K0), "Q_into_spacecraft_W": r.q_sc_w}),
            );
        }
    }

    // Penalties against P6.
    let (dbus, dpd) = ledger_slopes(&dcr.ledger)?;
    let p_anchor = input(ctx, "icp.P_fwd_anchor_W")?;
    let lead = |r_a: f64| 2.0 * 4.76e-3 / r_a;
    let lead_pen = |f: f64| {
        let dp = p_anchor * f / (1.0 - f);
        json!({"f_lead": f, "dP_fwd_W": dp, "dP_bus_W": dp * dbus, "dP_d_max_at_1350W_W": dp * dpd})
    };
    let heater_factor = 1.0
        / (ledger_term(&dcr.ledger, "ETA-TH")?
            * ledger_term(&dcr.ledger, "ETA-H-LV")?
            * ledger_term(&dcr.ledger, "ETA-FE")?);
    let slot = num(p_nom(&dcr.ledger)?, "thermal_residual_bus_W")?;
    let h_op = worst.get(COLD_OP).and_then(|w| w.1);
    let h_non = worst.get(COLD_NONOP).and_then(|w| w.1);
    let h_op_bus = h_op.map(|h| h * heater_factor);
    let excess = h_op_bus.map(|b| (b - slot).max(0.0));
    let q_sc = q_sc_max(&runs);
    let standoff_kg = 4.0 * 0.030 * 22.0e-6 * 4430.0;
    let admissible = r1a && r1b && r1c;
    let runs_json: Map<String, Value> = runs.iter().map(|(k, r)| (k.clone(), run_json(r))).collect();
    Ok(json!({
        "grid": rows,
        "confirmations": confirmations,
        "selected": {"A_MA_m2": a_sel, "basis": basis, "radiator_mass_kg_at_4_kg_m2": a_sel * 4.0, "standoff_mass_kg": standoff_kg},
        "hot_corner": hot, "cold_corners": cold, "nominal_corner": nom,
        "runs": runs_json,
        "cold_corner_runs": cold_rows,
        "nodes": nodes,
        "worsened_vs_v2": worsened,
        "materials_triggers_fired": fired,
        "cold_governing": {
            "TC5_N_MATCH_T_min_C": worst.get(COLD_OP).map(|w| w.0), "TC5_heater_W": h_op,
            "TC6_N_MATCH_T_min_C": worst.get(COLD_NONOP).map(|w| w.0), "TC6_heater_W": h_non,
        },
        "AL_QMATCH": {"Q_match_frac_allowable": al_q, "case": "TC3-HOT-I-BSTAR", "corner": "HOT", "registered_value_hot_corner": num(hot, "Q_match_frac")?},
        "nominal_corner_runs": nominal,
        "T_SC_sensitivity": {"runs": tsc, "changes_a_verdict": icd_change},
        "spacecraft_interface": {"Q_into_spacecraft_max_hot_W": q_sc, "v2_W": dcr.v2["spacecraft_interface"]["Q_into_spacecraft_max_hot_W"], "governing_allocation_W": 50.0},
        "power_penalty_vs_P6": {
            "lead_loss_reference_R_A_1_Ohm": lead_pen(lead(1.0)),
            "lead_loss_conservative_R_A_0_5_Ohm": lead_pen(lead(0.5)),
            "operating_heater_W": h_op, "operating_heater_bus_W": h_op_bus, "heater_bus_factor": heater_factor,
            "P6_thermal_control_slot_bus_W": slot, "operating_heater_excess_over_slot_bus_W": excess,
            "non_operating_survival_heater_W": h_non,
            "note": "the lead loss is the RF-chain penalty of R-1 against the P6 ledger (v2 had no lead); dP at the anchor for the same delivered power; the non-operating heater is a survival load outside the firing bus allocation (REFERENCE_PENDING_ICD)",
        },
        "criteria": {"R1-a": r1a, "R1-b": r1b, "R1-c": r1c, "R1-d": "reported (power_penalty_vs_P6)"},
        "admissible": admissible,
        "icd_change": icd_change,
    }))
}

/// Route R-2: every registered case with N_MATCH absent, verdicts against v2, the RF-chain penalty.
pub fn evaluate_r2(ctx: &mut Context, base: &Base, dcr: &Dcr) -> Result<Value, ClosureError> {
    let hv = hall_variant(dcr)?;
    apply_r2(ctx, base);
    let lims = limits(ctx);
    let mut runs: BTreeMap<String, CaseRun> = BTreeMap::new();
    for id in case_ids(ctx) {
        runs.insert(id.clone(), run_named(ctx, &id, &hv)?);
    }
    let (nodes, worsened) = verdicts(&lims, &runs, &dcr.v2);
    let fired = triggers_fired(ctx, &nodes);
    let all_conv = HOT.iter().chain([COLD_OP, COLD_NONOP].iter()).all(|id| runs[*id].converged());
    let r2a = all_conv && worsened.is_empty() && fired.is_empty();
    base.restore(ctx);
    let rf = r2_rf_penalty(dcr, ctx)?;
    let r2b = rf["R2-b_conservative_anchor_within_envelope"].as_bool() == Some(true);
    let r2c = rf["R2-c_conservative_anchor_dP_bus_within_P_NOM_RFP_margin"].as_bool() == Some(true);
    let runs_json: Map<String, Value> = runs.iter().map(|(k, r)| (k.clone(), run_json(r))).collect();
    Ok(json!({
        "runs": runs_json,
        "nodes": nodes,
        "worsened_vs_v2": worsened,
        "materials_triggers_fired": fired,
        "spacecraft_interface": {"Q_into_spacecraft_max_hot_W": q_sc_max(&runs), "v2_W": dcr.v2["spacecraft_interface"]["Q_into_spacecraft_max_hot_W"]},
        "rf_penalty": rf,
        "criteria": {"R2-a": r2a, "R2-b": r2b, "R2-c": r2c},
        "admissible": r2a && r2b && r2c,
    }))
}

/// The full evaluation record (both routes, selection, P7 state).
pub fn evaluation_record(ctx: &mut Context, dcr: &Dcr) -> Result<Value, ClosureError> {
    let base = Base::of(ctx);
    let r1 = evaluate_r1(ctx, &base, dcr)?;
    let r2 = evaluate_r2(ctx, &base, dcr)?;
    base.restore(ctx);
    let (route, outcome) = if r1["admissible"].as_bool() == Some(true) {
        ("R-1", "DCR-DBF1-003 WITHDRAWN (no DBF-1 value changes)")
    } else if r2["admissible"].as_bool() == Some(true) {
        ("R-2", "DCR-DBF1-003 proceeds as DBF-1.1 (coordinator)")
    } else {
        ("BLOCKED", "neither route admissible: residual reported")
    };
    let p7_state = match route {
        "R-1" => {
            let q = r1["spacecraft_interface"]["Q_into_spacecraft_max_hot_W"].as_f64();
            if r1["icd_change"].as_bool() == Some(true) || q.is_some_and(|q| q > 50.0) {
                "REFERENCE/ICD DEPENDENT"
            } else {
                "FROZEN FOR EM"
            }
        }
        "R-2" => "DCR REQUIRED (pending DBF-1.1 approval)",
        _ => "DCR REQUIRED",
    };
    let residual = if route == "BLOCKED" {
        json!({
            "R-1_N_MATCH": r1["nodes"][MATCH],
            "R-1_criteria": r1["criteria"],
            "R-2_criteria": r2["criteria"],
            "R-2_conservative_anchor": r2["rf_penalty"]["corners"]["CONSERVATIVE"]["points"]["anchor"],
        })
    } else {
        Value::Null
    };
    Ok(json!({
        "schema": SCHEMA,
        "id": "DCR003-EVALUATION-v1",
        "dcr": "DCR-DBF1-003",
        "lane": "L-DCR003-MATCH",
        "model": {"id": "NP-THERMAL-CATHODELESS", "version": "2.0.0", "case_class": "PARAMETRIC", "validation_status": "NOT_VALIDATED", "label": "PARAMETRIC_NOT_A_PREDICTION"},
        "preregistration": {"path": DCR_PREREG_PATH, "sha256": dcr.sha256, "lock_path": DCR_LOCK_PATH, "lock_sha256": dcr.lock_sha256},
        "p7_preregistration": {"path": super::PREREG_PATH, "sha256": ctx.prereg.sha256, "lock_sha256": ctx.lock_sha256},
        "load_inputs": {"path": ctx.inputs_path, "sha256": ctx.inputs_sha256},
        "run_provenance": {"rust_commit": ctx.run.rust_commit, "rust_tree_dirty": ctx.run.rust_tree_dirty, "governed_thermal_records": ctx.gov.hashes()},
        "R-1": r1,
        "R-2": r2,
        "selection": {"rule": dcr.raw["selection_rule"], "route": route, "outcome": outcome, "residual": residual},
        "p7_closure_state": {"state": p7_state, "rule": dcr.raw["p7_state_rule"]},
    }))
}

/// Load and verify everything, then evaluate.
pub fn run(root: &Path, run: abep_subsystems::thermal::RunContext) -> Result<Value, ClosureError> {
    let dcr = Dcr::load(root)?;
    let mut ctx = Context::load(root, INPUTS_PATH, run)?;
    evaluation_record(&mut ctx, &dcr)
}

// ------------------------------------------------------------------------------------------------ markdown

fn f1(v: &Value) -> String {
    match v.as_f64() {
        Some(x) => format!("{x:.1}"),
        None => "-".into(),
    }
}

fn f3(v: &Value) -> String {
    match v.as_f64() {
        Some(x) => format!("{x:.3}"),
        None => "-".into(),
    }
}

pub fn markdown(rec: &Value) -> String {
    let st = |v: &Value| v.as_str().unwrap_or("-").to_string();
    let r1 = &rec["R-1"];
    let r2 = &rec["R-2"];
    let mut m = String::new();
    m.push_str("# DCR-DBF1-003 evaluation v1 (co-located RF match, P7)\n\n");
    m.push_str(&format!(
        "Companion of `dcr003_evaluation_v1.json` (the JSON governs). Preregistration `{}` (sha256 `{}`, lock `{}`); \
P7 preregistration sha256 `{}`; load inputs `{}` (sha256 `{}`); Rust commit `{}`. Model NP-THERMAL-CATHODELESS 2.0.0, \
PARAMETRIC, NOT_VALIDATED.\n\n",
        st(&rec["preregistration"]["path"]),
        st(&rec["preregistration"]["sha256"]),
        st(&rec["preregistration"]["lock_sha256"]),
        st(&rec["p7_preregistration"]["sha256"]),
        st(&rec["load_inputs"]["path"]),
        st(&rec["load_inputs"]["sha256"]),
        st(&rec["run_provenance"]["rust_commit"]),
    ));
    m.push_str(&format!(
        "**Selected route: {}** ({}). **P7 closure state: {}.**\n\n",
        st(&rec["selection"]["route"]),
        st(&rec["selection"]["outcome"]),
        st(&rec["p7_closure_state"]["state"])
    ));
    m.push_str("## R-1: isolated co-located match with its own radiator (no DCR)\n\n");
    m.push_str(&format!(
        "HOT corner G_iso {} W/K, G_lead {} W/K, Q_match_frac {}. Selected A_MA **{} m^2** ({}); radiator mass {} kg \
at 4 kg/m^2, standoffs {} kg. Criteria: {}. Admissible: **{}**.\n\n",
        r1["hot_corner"]["G_iso"],
        r1["hot_corner"]["G_lead"],
        r1["hot_corner"]["Q_match_frac"],
        r1["selected"]["A_MA_m2"],
        st(&r1["selected"]["basis"]),
        f3(&r1["selected"]["radiator_mass_kg_at_4_kg_m2"]),
        f3(&r1["selected"]["standoff_mass_kg"]),
        r1["criteria"],
        r1["admissible"]
    ));
    m.push_str(
        "| A_MA m^2 | feasible | N_MATCH TC1 degC | N_MATCH TC3 degC | N_MATCH min margin K |\n|---|---|---|---|---|\n",
    );
    for g in r1["grid"].as_array().cloned().unwrap_or_default() {
        m.push_str(&format!(
            "| {} | {} | {} | {} | {} |\n",
            g["A_MA_m2"],
            g["feasible"],
            f1(&g["TC1"]["T_max_C"][MATCH]),
            f1(&g["TC3"]["T_max_C"][MATCH]),
            f1(&g["N_MATCH_min_margin_K"])
        ));
    }
    m.push_str(&format!("\nConfirmations (TC2 / TC4): {}\n\n", r1["confirmations"]));
    let node_table = |m: &mut String, nodes: &Value| {
        m.push_str("| node | class | ceiling degC | T max hot degC | margin K | verdict | v2 verdict | v2 T degC | dT vs v2 K |\n|---|---|---|---|---|---|---|---|---|\n");
        if let Some(o) = nodes.as_object() {
            for (n, r) in o {
                m.push_str(&format!(
                    "| {} | {} | {} | {} | {} | {} | {} | {} | {} |\n",
                    n,
                    st(&r["limit_class"]),
                    f1(&r["design_ceiling_C"]),
                    f1(&r["T_max_hot_C"]),
                    f1(&r["margin_K"]),
                    st(&r["verdict"]),
                    st(&r["v2_verdict"]),
                    f1(&r["v2_T_max_hot_C"]),
                    f1(&r["delta_T_vs_v2_K"])
                ));
            }
        }
    };
    m.push_str("### Nodes at the selected design (HOT corner, governing hot cases TC1-TC4)\n\n");
    node_table(&mut m, &r1["nodes"]);
    let cg = &r1["cold_governing"];
    m.push_str(&format!(
        "\n### Cold (worst of the four COLD corners)\n\nTC5 N_MATCH T_min {} degC, heater {} W; TC6 N_MATCH T_min {} degC, \
heater {} W.\n\n",
        f1(&cg["TC5_N_MATCH_T_min_C"]),
        f1(&cg["TC5_heater_W"]),
        f1(&cg["TC6_N_MATCH_T_min_C"]),
        f1(&cg["TC6_heater_W"])
    ));
    let pp = &r1["power_penalty_vs_P6"];
    m.push_str(&format!(
        "### Power penalty against P6\n\n- lead loss, R_A 1 Ohm: dP_fwd {} W, dP_bus {} W, dP_d,max {} W\n- lead loss, R_A \
0.5 Ohm: dP_fwd {} W, dP_bus {} W, dP_d,max {} W\n- operating heater {} W (bus {} W) against the P6 thermal_control slot \
{} W: excess {} W\n- non-operating survival heater {} W\n\nAL-QMATCH (TC3, HOT corner): Q_match_frac <= {}. T_SC \
sensitivity changes a verdict: {}. Q into the spacecraft (max hot) {} W (v2 {} W).\n\n",
        f1(&pp["lead_loss_reference_R_A_1_Ohm"]["dP_fwd_W"]),
        f1(&pp["lead_loss_reference_R_A_1_Ohm"]["dP_bus_W"]),
        f1(&pp["lead_loss_reference_R_A_1_Ohm"]["dP_d_max_at_1350W_W"]),
        f1(&pp["lead_loss_conservative_R_A_0_5_Ohm"]["dP_fwd_W"]),
        f1(&pp["lead_loss_conservative_R_A_0_5_Ohm"]["dP_bus_W"]),
        f1(&pp["lead_loss_conservative_R_A_0_5_Ohm"]["dP_d_max_at_1350W_W"]),
        f1(&pp["operating_heater_W"]),
        f1(&pp["operating_heater_bus_W"]),
        f1(&pp["P6_thermal_control_slot_bus_W"]),
        f1(&pp["operating_heater_excess_over_slot_bus_W"]),
        f1(&pp["non_operating_survival_heater_W"]),
        f3(&r1["AL_QMATCH"]["Q_match_frac_allowable"]),
        r1["T_SC_sensitivity"]["changes_a_verdict"],
        f1(&r1["spacecraft_interface"]["Q_into_spacecraft_max_hot_W"]),
        f1(&r1["spacecraft_interface"]["v2_W"])
    ));
    m.push_str("## R-2: match at the RF generator (DCR, DBF-1.1)\n\n");
    m.push_str(&format!("Criteria: {}. Admissible: **{}**.\n\n", r2["criteria"], r2["admissible"]));
    node_table(&mut m, &r2["nodes"]);
    let rf = &r2["rf_penalty"];
    m.push_str(&format!(
        "\nAntenna reference L_A {} uH, X_A {} Ohm (Wheeler, P7 antenna geometry, assumed).\n\n| corner | R_A Ohm | X_A Ohm | \
matched loss dB | VSWR | eta_line | P_fwd,R2 anchor W | dP_bus anchor W | dP_d,max anchor W | P_fwd,R2 at 500 W W | \
RF unit Q hot anchor W |\n|---|---|---|---|---|---|---|---|---|---|---|\n",
        f3(&rf["antenna_inductance_reference_uH"]),
        f1(&rf["antenna_reactance_reference_Ohm"])
    ));
    if let Some(c) = rf["corners"].as_object() {
        for (n, x) in c {
            let a = &x["points"]["anchor"];
            m.push_str(&format!(
                "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |\n",
                n,
                f1(&x["R_A_Ohm"]),
                f1(&x["X_A_Ohm"]),
                f3(&x["matched_loss_dB"]),
                f1(&x["VSWR"]),
                f3(&x["eta_line"]),
                f1(&a["P_fwd_R2_W"]),
                f1(&a["dP_bus_W"]),
                f1(&a["dP_d_max_at_1350W_W"]),
                f1(&x["points"]["envelope_end"]["P_fwd_R2_W"]),
                f1(&a["RF_GENERATOR_unit_Q_hot_W"])
            ));
        }
    }
    m.push_str(&format!(
        "\nQ into the spacecraft (max hot) {} W.\n\n## Selection\n\n{}\n\nRoute **{}**: {}. P7 closure state **{}**.\n",
        f1(&r2["spacecraft_interface"]["Q_into_spacecraft_max_hot_W"]),
        st(&rec["selection"]["rule"]),
        st(&rec["selection"]["route"]),
        st(&rec["selection"]["outcome"]),
        st(&rec["p7_closure_state"]["state"])
    ));
    m
}

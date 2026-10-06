//! Molecular-drag compressor physics (`abep_sim/compressor.py` DragCompressor; contract
//! PARITY-C-ABEP_SIM_COMPRESSOR_PY-V1).
//!
//! Turbomolecular rows plus Holweck / Gaede drag stages in the free-molecular regime, per species s:
//! ln K0 = kK u_t / cbar (turbo row) or 2 u L xi / (cbar h) (drag stage); linear characteristic
//! K = K0 - (K0 - 1) Q / (S p_in); leak C_L (p_out - p_in) returned to the inlet and solved as a damped fixed point
//! (G-03: reaching the iteration cap is MODEL_NOT_CONVERGED). Outside 1 <= K <= K0 the record is
//! OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY and the clipped K = 1 values are diagnostics only (MCC-02). Rotor acceptance
//! only through a registered rotor-strength basis (A9.9 S2.3 / MCC-03).

use crate::error::{key_error, GasPathError, PyClass, PyResult};
use crate::materials::MaterialsView;
use crate::pyops::{self, py_max, py_min};
use crate::rec::{fnum, Obj};
use crate::rotor_strength::{self as rs, Arg, Registry};
use abep_types::constants::{species_mass, K_B};
use abep_types::EvalStatus;
use serde_json::{Map, Value};
use std::f64::consts::PI;

pub const RECIRC_MAX_ITER: usize = 40;
pub const RECIRC_RTOL: f64 = 1e-4;
pub const GAEDE_IN_DOMAIN: &str = "IN_DOMAIN";
pub const GAEDE_OUT_OF_DOMAIN: &str = "OUT_OF_MODEL_DOMAIN_STAGE_CAPACITY";

/// Run / gaede statuses -> EvalStatus (INV-C-03).
pub fn solver_eval_status(solver_status: &str) -> EvalStatus {
    if solver_status == "MODEL_NOT_CONVERGED" {
        EvalStatus::ModelError
    } else {
        EvalStatus::Evaluated
    }
}
pub fn gaede_eval_status(gaede_status: &str) -> EvalStatus {
    if gaede_status == GAEDE_OUT_OF_DOMAIN {
        EvalStatus::OutOfDomain
    } else {
        EvalStatus::Evaluated
    }
}

/// Materials and registered rotor bases the compressor reads (explicit inputs).
#[derive(Clone, Copy)]
pub struct Ctx<'a> {
    pub materials: &'a MaterialsView,
    pub registry: &'a Registry,
}

/// The 27 dataclass fields of the reference, with its defaults.
#[derive(Debug, Clone, PartialEq)]
pub struct DragCompressor {
    pub turbo_rows: i64,
    pub turbo_area_m2: f64,
    pub turbo_radius_m: f64,
    pub turbo_k_s: f64,
    pub turbo_k_k: f64,
    pub turbo_blade_area_frac: f64,
    pub turbo_disc_thickness_m: f64,
    pub n_stages: i64,
    pub rotor_radius_m: f64,
    pub rpm: f64,
    /// the reference holds rpm as a Python int after `size_for` (affects only text formatting)
    pub rpm_is_int: bool,
    pub h_mm: f64,
    pub w_mm: f64,
    pub l_per_stage_m: f64,
    pub xi: f64,
    pub rotor_material: String,
    pub stress_safety: f64,
    pub t_gas_k: f64,
    pub leak_conductance_m3_s: f64,
    pub k_bear_w_per_rads: f64,
    pub eta_motor: f64,
    pub p_ctrl_w: f64,
    pub rotor_disc_thickness_m: f64,
    pub stator_mass_factor: f64,
    pub motor_kg_per_nm: f64,
    pub bearing_kg: f64,
    pub conductance_to_sink_w_k: f64,
    pub t_sink_k: f64,
    pub rotor_strength_basis_id: Option<String>,
    pub rotor_stock_thickness_m: Option<f64>,
}

/// Field names of the reference dataclass, in declaration order.
pub const FIELDS: [&str; 27] = [
    "turbo_rows",
    "turbo_area_m2",
    "turbo_radius_m",
    "turbo_kS",
    "turbo_kK",
    "turbo_blade_area_frac",
    "turbo_disc_thickness_m",
    "n_stages",
    "rotor_radius_m",
    "rpm",
    "h_mm",
    "w_mm",
    "L_per_stage_m",
    "xi",
    "rotor_material",
    "stress_safety",
    "T_gas_K",
    "leak_conductance_m3_s",
    "k_bear_W_per_rads",
    "eta_motor",
    "P_ctrl_W",
    "rotor_disc_thickness_m",
    "stator_mass_factor",
    "motor_kg_per_Nm",
    "bearing_kg",
    "conductance_to_sink_W_K",
    "T_sink_K",
];

impl Default for DragCompressor {
    fn default() -> Self {
        DragCompressor {
            turbo_rows: 3,
            turbo_area_m2: 0.25,
            turbo_radius_m: 0.30,
            turbo_k_s: 0.20,
            turbo_k_k: 1.2,
            turbo_blade_area_frac: 0.35,
            turbo_disc_thickness_m: 0.002,
            n_stages: 4,
            rotor_radius_m: 0.06,
            rpm: 60000.0,
            rpm_is_int: false,
            h_mm: 3.0,
            w_mm: 12.0,
            l_per_stage_m: 0.35,
            xi: 0.6,
            rotor_material: "Ti6Al4V".into(),
            stress_safety: 2.0,
            t_gas_k: 350.0,
            leak_conductance_m3_s: 2e-4,
            k_bear_w_per_rads: 3e-4,
            eta_motor: 0.80,
            p_ctrl_w: 8.0,
            rotor_disc_thickness_m: 0.004,
            stator_mass_factor: 1.2,
            motor_kg_per_nm: 4.0,
            bearing_kg: 0.6,
            conductance_to_sink_w_k: 0.4,
            t_sink_k: 293.0,
            rotor_strength_basis_id: None,
            rotor_stock_thickness_m: None,
        }
    }
}

/// Ordered (species -> value) map.
pub type SpMap = Vec<(String, f64)>;

fn sp(m: &SpMap, k: &str) -> f64 {
    m.iter().find(|(s, _)| s == k).map(|(_, v)| *v).unwrap_or(f64::NAN)
}

fn mass_of(s: &str) -> PyResult<f64> {
    species_mass(s).map_err(|_| key_error(s))
}

struct StageAcc<'a> {
    p_s: &'a mut SpMap,
    k_total: &'a mut SpMap,
    p_gas: &'a mut f64,
    gaede: &'a mut Vec<Value>,
}

impl DragCompressor {
    /// Numeric field by reference name (FIXED-coefficient overrides, defaults record).
    pub fn field_value(&self, name: &str) -> Option<Value> {
        Some(match name {
            "turbo_rows" => Value::from(self.turbo_rows),
            "turbo_area_m2" => fnum(self.turbo_area_m2),
            "turbo_radius_m" => fnum(self.turbo_radius_m),
            "turbo_kS" => fnum(self.turbo_k_s),
            "turbo_kK" => fnum(self.turbo_k_k),
            "turbo_blade_area_frac" => fnum(self.turbo_blade_area_frac),
            "turbo_disc_thickness_m" => fnum(self.turbo_disc_thickness_m),
            "n_stages" => Value::from(self.n_stages),
            "rotor_radius_m" => fnum(self.rotor_radius_m),
            "rpm" => fnum(self.rpm),
            "h_mm" => fnum(self.h_mm),
            "w_mm" => fnum(self.w_mm),
            "L_per_stage_m" => fnum(self.l_per_stage_m),
            "xi" => fnum(self.xi),
            "rotor_material" => Value::String(self.rotor_material.clone()),
            "stress_safety" => fnum(self.stress_safety),
            "T_gas_K" => fnum(self.t_gas_k),
            "leak_conductance_m3_s" => fnum(self.leak_conductance_m3_s),
            "k_bear_W_per_rads" => fnum(self.k_bear_w_per_rads),
            "eta_motor" => fnum(self.eta_motor),
            "P_ctrl_W" => fnum(self.p_ctrl_w),
            "rotor_disc_thickness_m" => fnum(self.rotor_disc_thickness_m),
            "stator_mass_factor" => fnum(self.stator_mass_factor),
            "motor_kg_per_Nm" => fnum(self.motor_kg_per_nm),
            "bearing_kg" => fnum(self.bearing_kg),
            "conductance_to_sink_W_K" => fnum(self.conductance_to_sink_w_k),
            "T_sink_K" => fnum(self.t_sink_k),
            _ => return None,
        })
    }

    /// Set a float field by reference name; false for an unknown or non-float field.
    pub fn set_float(&mut self, name: &str, v: f64) -> bool {
        let slot = match name {
            "turbo_area_m2" => &mut self.turbo_area_m2,
            "turbo_radius_m" => &mut self.turbo_radius_m,
            "turbo_kS" => &mut self.turbo_k_s,
            "turbo_kK" => &mut self.turbo_k_k,
            "turbo_blade_area_frac" => &mut self.turbo_blade_area_frac,
            "turbo_disc_thickness_m" => &mut self.turbo_disc_thickness_m,
            "rotor_radius_m" => &mut self.rotor_radius_m,
            "rpm" => {
                self.rpm_is_int = false;
                &mut self.rpm
            }
            "h_mm" => &mut self.h_mm,
            "w_mm" => &mut self.w_mm,
            "L_per_stage_m" => &mut self.l_per_stage_m,
            "xi" => &mut self.xi,
            "stress_safety" => &mut self.stress_safety,
            "T_gas_K" => &mut self.t_gas_k,
            "leak_conductance_m3_s" => &mut self.leak_conductance_m3_s,
            "k_bear_W_per_rads" => &mut self.k_bear_w_per_rads,
            "eta_motor" => &mut self.eta_motor,
            "P_ctrl_W" => &mut self.p_ctrl_w,
            "rotor_disc_thickness_m" => &mut self.rotor_disc_thickness_m,
            "stator_mass_factor" => &mut self.stator_mass_factor,
            "motor_kg_per_Nm" => &mut self.motor_kg_per_nm,
            "bearing_kg" => &mut self.bearing_kg,
            "conductance_to_sink_W_K" => &mut self.conductance_to_sink_w_k,
            "T_sink_K" => &mut self.t_sink_k,
            _ => return false,
        };
        *slot = v;
        true
    }

    fn rpm_arg(&self) -> Arg {
        if self.rpm_is_int {
            Arg::Int(self.rpm as i64)
        } else {
            Arg::Num(self.rpm)
        }
    }

    /// Drag-rotor tip speed.
    pub fn u(&self) -> f64 {
        self.rotor_radius_m * self.rpm * 2.0 * PI / 60.0
    }

    /// Turbo-row tip speed (same shaft speed, its own radius).
    pub fn u_turbo(&self) -> f64 {
        self.turbo_radius_m * self.rpm * 2.0 * PI / 60.0
    }

    /// LEGACY/CONSERVATIVE SENSITIVITY tip-speed cap: uncited DB yield / (uncited stress_safety * rho).
    pub fn u_max_legacy_sensitivity(&self, ctx: Ctx) -> PyResult<f64> {
        let m = ctx.materials.get(&self.rotor_material)?;
        pyops::sqrt(pyops::div(m.yield_mpa * 1e6, self.stress_safety * m.density)?)
    }

    pub fn sizing_mode(&self, ctx: Ctx) -> &'static str {
        match ctx.registry.get_registered(self.rotor_strength_basis_id.as_deref()) {
            Some(b) if rs::basis_problems(b).is_empty() && b.db_key() == Some(self.rotor_material.as_str()) => {
                rs::SIZING_REGISTERED_BASIS
            }
            _ => rs::SIZING_PARAMETRIC_SENSITIVITY,
        }
    }

    pub fn u_max(&self, ctx: Ctx) -> PyResult<f64> {
        if self.sizing_mode(ctx) == rs::SIZING_REGISTERED_BASIS {
            let b = ctx.registry.get_registered(self.rotor_strength_basis_id.as_deref()).expect("registered");
            return rs::tip_speed_allowable(b);
        }
        self.u_max_legacy_sensitivity(ctx)
    }

    pub fn u_max_basis(&self, ctx: Ctx) -> String {
        if self.sizing_mode(ctx) == rs::SIZING_REGISTERED_BASIS {
            format!("REGISTERED_BASIS:{}", self.rotor_strength_basis_id.as_deref().unwrap_or("None"))
        } else {
            rs::LEGACY_SENSITIVITY_LABEL.into()
        }
    }

    pub fn cbar(&self, m: f64) -> PyResult<f64> {
        pyops::sqrt(pyops::div(8.0 * K_B * self.t_gas_k, PI * m)?)
    }

    fn gaede_record(
        gaede: &mut Vec<Value>,
        stage: &str,
        species: &str,
        k_raw: f64,
        k0: f64,
        q: f64,
        capacity: f64,
    ) -> PyResult<(f64, bool)> {
        let in_domain = 1.0 <= k_raw && k_raw <= k0;
        let k_diag = py_max(py_min(k_raw, k0), 1.0);
        gaede.push(
            Obj::new()
                .s("stage", stage)
                .s("species", species)
                .f("K_unclipped", k_raw)
                .f("K0", k0)
                .f("throughput_Pa_m3_s", q)
                .f("capacity_Pa_m3_s", capacity)
                .f("load_ratio", pyops::div(q, py_max(capacity, 1e-30))?)
                .b("in_domain", in_domain)
                .set("K_clipped_diagnostic", if in_domain { Value::Null } else { fnum(k_diag) })
                .build(),
        );
        Ok((if in_domain { k_raw } else { k_diag }, in_domain))
    }

    fn gaede_summary(gaede: &[Value], out: &mut Map<String, Value>) {
        let ood: Vec<&Value> = gaede.iter().filter(|g| g["in_domain"] == Value::Bool(false)).collect();
        let mut by_stage = Map::new();
        for g in gaede {
            let st = g["stage"].as_str().unwrap_or("").to_string();
            let e = by_stage.entry(st).or_insert_with(|| Value::Object(Map::new()));
            e.as_object_mut()
                .expect("obj")
                .insert(g["species"].as_str().unwrap_or("").into(), g["K_unclipped"].clone());
        }
        let ok = ood.is_empty();
        let kmin = pyops::py_min_iter(gaede.iter().map(|g| crate::rec::as_f64(&g["K_unclipped"]).unwrap_or(f64::NAN)))
            .unwrap_or(f64::NAN);
        out.insert("gaede_domain_ok".into(), Value::Bool(ok));
        out.insert("gaede_status".into(), Value::String(if ok { GAEDE_IN_DOMAIN } else { GAEDE_OUT_OF_DOMAIN }.into()));
        out.insert("gaede_K_unclipped".into(), Value::Object(by_stage));
        out.insert("gaede_K_unclipped_min".into(), fnum(kmin));
        out.insert(
            "gaede_out_of_domain".into(),
            crate::rec::slist(
                ood.iter()
                    .map(|g| format!("{}:{}", g["stage"].as_str().unwrap_or(""), g["species"].as_str().unwrap_or(""))),
            ),
        );
        out.insert("gaede_stages".into(), Value::Array(gaede.to_vec()));
        out.insert("gaede_clipped_values_are_diagnostic".into(), Value::Bool(!ok));
    }

    /// One turbo row or drag stage over every species (the reference loop body, verbatim order).
    #[allow(clippy::too_many_arguments)]
    fn stage(
        &self,
        nflow: &SpMap,
        name: &str,
        ln_k0: &dyn Fn(f64) -> PyResult<f64>,
        s_cap: f64,
        u_st: f64,
        a_term: f64,
        two_over_sqrt_pi: f64,
        acc: &mut StageAcc,
    ) -> PyResult<()> {
        for (s, n) in nflow {
            let m = mass_of(s)?;
            let cb = self.cbar(m)?;
            let k0 = pyops::exp(ln_k0(cb)?)?;
            let q = n * K_B * self.t_gas_k;
            let ps = sp(acc.p_s, s);
            let k_raw = k0 - pyops::div((k0 - 1.0) * q, py_max(s_cap * ps, 1e-30))?;
            let (k, _) = Self::gaede_record(acc.gaede, name, s, k_raw, k0, q, s_cap * ps)?;
            let p_mean = 0.5 * ps * (1.0 + k);
            *acc.p_gas += p_mean * pyops::div(u_st, cb)? * a_term * two_over_sqrt_pi * u_st;
            for (k2, v) in acc.p_s.iter_mut() {
                if k2 == s {
                    *v *= k;
                }
            }
            match acc.k_total.iter_mut().find(|(k2, _)| k2 == s) {
                Some((_, v)) => *v *= k,
                None => acc.k_total.push((s.clone(), 1.0 * k)),
            }
        }
        Ok(())
    }

    /// One machine evaluation at inlet pressure `p_in` for the throughput `mdot` (partial pressures by number flow).
    pub fn run_once(&self, ctx: Ctx, p_in_pa: f64, mdot: &SpMap) -> PyResult<Map<String, Value>> {
        let u = self.u();
        let h = self.h_mm * 1e-3;
        let w = self.w_mm * 1e-3;
        let l = self.l_per_stage_m;
        let s0 = self.xi * u * h * w / 2.0;
        let mut nflow: SpMap = vec![];
        for (s, m) in mdot {
            nflow.push((s.clone(), pyops::div(*m, mass_of(s)?)?));
        }
        let mut ntot = pyops::py_sum(nflow.iter().map(|(_, v)| *v));
        if ntot == 0.0 {
            ntot = 1e-30;
        }
        let mut p_s_in: SpMap = vec![];
        for (s, n) in &nflow {
            p_s_in.push((s.clone(), pyops::div(p_in_pa * n, ntot)?));
        }
        let mut p_s = p_s_in.clone();
        let mut k_total: SpMap = vec![];
        let mut p_gas = 0.0;
        let mut gaede: Vec<Value> = vec![];
        let u_t = self.u_turbo();
        let s_t = self.turbo_k_s * u_t * self.turbo_area_m2;
        let two_over_sqrt_pi = pyops::div(2.0, PI.sqrt())?;
        let mut acc = StageAcc { p_s: &mut p_s, k_total: &mut k_total, p_gas: &mut p_gas, gaede: &mut gaede };
        for row in 0..self.turbo_rows.max(0) {
            let kk = self.turbo_k_k;
            let f = move |cb: f64| pyops::div(kk * u_t, cb);
            let a_term = self.turbo_area_m2 * self.turbo_blade_area_frac * 2.0;
            self.stage(&nflow, &format!("turbo_row_{}", row + 1), &f, s_t, u_t, a_term, two_over_sqrt_pi, &mut acc)?;
        }
        for st in 0..self.n_stages.max(0) {
            let xi = self.xi;
            let f = move |cb: f64| Ok(pyops::div(2.0 * u * l, cb * h)? * xi);
            let a_wet = 2.0 * l * w;
            self.stage(&nflow, &format!("drag_stage_{}", st + 1), &f, s0, u, a_wet, two_over_sqrt_pi, &mut acc)?;
        }
        let p_out = pyops::py_sum(p_s.iter().map(|(_, v)| *v));
        let mut leak: SpMap = vec![];
        for (s, _) in &nflow {
            leak.push((
                s.clone(),
                pyops::div(
                    self.leak_conductance_m3_s * (sp(&p_s, s) - sp(&p_s_in, s)) * mass_of(s)?,
                    K_B * self.t_gas_k,
                )?,
            ));
        }
        let delivered: SpMap =
            nflow.iter().map(|(s, _)| (s.clone(), py_max(sp(mdot, s) - sp(&leak, s), 0.0))).collect();
        let omega = self.rpm * 2.0 * PI / 60.0;
        let p_bear = self.k_bear_w_per_rads * omega;
        let p_el = pyops::div(p_gas + p_bear, self.eta_motor)? + self.p_ctrl_w;
        let torque = pyops::div(p_gas + p_bear, omega)?;
        let rm = ctx.materials.get(&self.rotor_material)?;
        let m_rotor = PI
            * pyops::pow(self.rotor_radius_m, 2.0)?
            * self.rotor_disc_thickness_m
            * rm.density
            * self.n_stages as f64
            * 0.7
            + self.turbo_area_m2
                * self.turbo_disc_thickness_m
                * rm.density
                * self.turbo_rows as f64
                * self.turbo_blade_area_frac
            + 0.15 * self.turbo_rows as f64;
        let m_motor = self.motor_kg_per_nm * py_max(torque, 0.01) + 0.25;
        let mass = m_rotor * (1.0 + self.stator_mass_factor) + m_motor + self.bearing_kg;
        let t =
            self.t_sink_k + pyops::div(p_gas + p_bear * 0.5 + p_el - (p_gas + p_bear), self.conductance_to_sink_w_k)?;
        let u_lim = self.u_max(ctx)?;
        let u_leg = self.u_max_legacy_sensitivity(ctx)?;
        let umax_tip = py_max(u, u_t);
        let q = rs::qualify_rotor(
            ctx.registry,
            self.rotor_strength_basis_id.as_deref(),
            &self.rotor_material,
            Arg::Num(umax_tip),
            self.rpm_arg(),
            Arg::Num(t),
            self.rotor_stock_thickness_m.map(Arg::Num).unwrap_or(Arg::None),
        )?;
        let mut out = Map::new();
        out.insert("u_mps".into(), fnum(u));
        out.insert("u_turbo_mps".into(), fnum(u_t));
        out.insert("u_max_mps".into(), fnum(u_lim));
        out.insert("u_max_basis".into(), Value::String(self.u_max_basis(ctx)));
        out.insert("sizing_mode".into(), Value::String(self.sizing_mode(ctx).into()));
        if let Value::Object(qm) = q {
            for (k, v) in qm {
                out.insert(k, v);
            }
        }
        out.insert("u_max_legacy_sensitivity_mps".into(), fnum(u_leg));
        out.insert("rotor_within_legacy_sensitivity_cap".into(), Value::Bool(umax_tip <= u_leg));
        out.insert("S_turbo_m3_s".into(), fnum(s_t));
        out.insert("S0_drag_m3_s".into(), fnum(s0));
        out.insert("p_in_Pa".into(), fnum(p_in_pa));
        out.insert("p_out_Pa".into(), fnum(p_out));
        out.insert("CR_active".into(), fnum(pyops::div(p_out, p_in_pa)?));
        out.insert("CR_by_species".into(), crate::rec::fmap(k_total.iter().map(|(s, v)| (s.as_str(), *v))));
        out.insert("delivered_kgps".into(), crate::rec::fmap(delivered.iter().map(|(s, v)| (s.as_str(), *v))));
        out.insert("leak_kgps".into(), crate::rec::fmap(leak.iter().map(|(s, v)| (s.as_str(), *v))));
        out.insert("P_gas_W".into(), fnum(p_gas));
        out.insert("P_bear_W".into(), fnum(p_bear));
        out.insert("P_el_W".into(), fnum(p_el));
        out.insert("torque_Nm".into(), fnum(torque));
        out.insert("mass_kg".into(), fnum(mass));
        out.insert("T_comp_K".into(), fnum(t));
        let mut comp = Map::new();
        for (s, v) in &p_s {
            comp.insert(s.clone(), fnum(pyops::div(*v, p_out)?));
        }
        out.insert("composition_out".into(), Value::Object(comp));
        Self::gaede_summary(&gaede, &mut out);
        Ok(out)
    }

    /// Operating point with the leak recirculation solved as a fixed point (G-03); `self_consistent` false is one
    /// direct evaluation.
    pub fn run(&self, ctx: Ctx, p_in_pa: f64, mdot: &SpMap, self_consistent: bool) -> PyResult<Map<String, Value>> {
        if !self_consistent {
            let mut r = self.run_once(ctx, p_in_pa, mdot)?;
            r.insert("converged".into(), Value::Bool(true));
            r.insert("iterations".into(), Value::from(1));
            r.insert("residual".into(), fnum(0.0));
            r.insert("solver_status".into(), Value::String("DIRECT_EVALUATION".into()));
            return Ok(r);
        }
        let mut recirc: SpMap = mdot.iter().map(|(s, _)| (s.clone(), 0.0)).collect();
        let mut r: Option<Map<String, Value>> = None;
        let mut converged = false;
        let mut it = 0;
        let mut resid = f64::NAN;
        for _ in 0..RECIRC_MAX_ITER {
            let through: SpMap = mdot.iter().map(|(s, m)| (s.clone(), m + sp(&recirc, s))).collect();
            let rr = self.run_once(ctx, p_in_pa, &through)?;
            it += 1;
            let leak = &rr["leak_kgps"];
            let new: SpMap = mdot
                .iter()
                .map(|(s, _)| (s.clone(), py_max(crate::rec::as_f64(&leak[s.as_str()]).unwrap_or(f64::NAN), 0.0)))
                .collect();
            let mut res_vals = vec![];
            for (s, m) in mdot {
                res_vals.push(pyops::div((sp(&new, s) - sp(&recirc, s)).abs(), py_max(*m, 1e-15))?);
            }
            resid = pyops::py_max_iter(res_vals).unwrap_or(0.0);
            r = Some(rr);
            if mdot.iter().all(|(s, m)| (sp(&new, s) - sp(&recirc, s)).abs() <= RECIRC_RTOL * py_max(*m, 1e-15)) {
                recirc = new;
                converged = true;
                break;
            }
            recirc = recirc.iter().map(|(s, v)| (s.clone(), 0.5 * (v + sp(&new, s)))).collect();
        }
        let mut r = r.ok_or_else(|| GasPathError::new(PyClass::RuntimeError, "no iteration"))?;
        let rsum = pyops::py_sum(recirc.iter().map(|(_, v)| *v));
        let msum = pyops::py_sum(mdot.iter().map(|(_, v)| *v));
        r.insert("recirculated_kgps".into(), crate::rec::fmap(recirc.iter().map(|(s, v)| (s.as_str(), *v))));
        r.insert("recirculation_frac".into(), fnum(pyops::div(rsum, py_max(msum, 1e-30))?));
        r.insert("delivered_kgps".into(), crate::rec::fmap(mdot.iter().map(|(s, v)| (s.as_str(), *v))));
        r.insert("leak_kgps".into(), crate::rec::fmap(recirc.iter().map(|(s, v)| (s.as_str(), *v))));
        r.insert("converged".into(), Value::Bool(converged));
        r.insert("iterations".into(), Value::from(it));
        r.insert("residual".into(), fnum(resid));
        r.insert(
            "solver_status".into(),
            Value::String(if converged { "CONVERGED" } else { "MODEL_NOT_CONVERGED" }.into()),
        );
        Ok(r)
    }

    pub fn rpm_limit(&self, ctx: Ctx) -> PyResult<f64> {
        let r_max = py_max(self.rotor_radius_m, self.turbo_radius_m);
        pyops::div(pyops::div(self.u_max(ctx)?, r_max)? * 60.0, 2.0 * PI)
    }

    /// Search turbo rows, then drag stages, then rpm (<= the tip-speed cap) for the lightest machine reaching
    /// CR_target (only Gaede-domain layouts are sized designs; MCC-02). Mutates the machine as the reference does.
    #[allow(clippy::too_many_arguments)]
    pub fn size_for(
        &mut self,
        ctx: Ctx,
        p_in_pa: f64,
        mdot: &SpMap,
        cr_target: f64,
        rpm_max: f64,
        max_turbo_rows: i64,
        max_drag_stages: i64,
    ) -> PyResult<Map<String, Value>> {
        let rpm_cap = py_min(rpm_max, self.rpm_limit(ctx)?);
        let cap_int = py_int(rpm_cap)?;
        let mut best: Option<Map<String, Value>> = None;
        let mut best_obj = f64::NAN;
        let mut n_ood: i64 = 0;
        let mut rpms: Vec<i64> = (5000..=cap_int).step_by(2500).collect();
        rpms.push(cap_int);
        rpms.sort();
        rpms.dedup();
        for rows in 1..=max_turbo_rows {
            for nst in 0..=max_drag_stages {
                for &rpm in &rpms {
                    self.turbo_rows = rows;
                    self.n_stages = nst;
                    self.rpm = rpm as f64;
                    self.rpm_is_int = true;
                    let r = self.run(ctx, p_in_pa, mdot, true)?;
                    let cr = crate::rec::as_f64(&r["CR_active"]).unwrap_or(f64::NAN);
                    if cr >= cr_target {
                        if r["gaede_domain_ok"] != Value::Bool(true) {
                            n_ood += 1;
                            continue;
                        }
                        let mass = crate::rec::as_f64(&r["mass_kg"]).unwrap_or(f64::NAN);
                        let pel = crate::rec::as_f64(&r["P_el_W"]).unwrap_or(f64::NAN);
                        let obj = mass + 0.02 * pel;
                        let mut cand = r;
                        cand.insert("turbo_rows".into(), Value::from(rows));
                        cand.insert("n_stages".into(), Value::from(nst));
                        cand.insert("rpm".into(), Value::from(rpm));
                        cand.insert("sized".into(), Value::Bool(true));
                        if best.is_none() || obj < best_obj {
                            best = Some(cand);
                            best_obj = obj;
                        }
                        break;
                    }
                }
            }
        }
        if let Some(mut b) = best {
            self.turbo_rows = b["turbo_rows"].as_i64().expect("int");
            self.n_stages = b["n_stages"].as_i64().expect("int");
            self.rpm = b["rpm"].as_i64().expect("int") as f64;
            self.rpm_is_int = true;
            b.insert("n_rejected_out_of_gaede_domain".into(), Value::from(n_ood));
            return Ok(b);
        }
        self.turbo_rows = max_turbo_rows;
        self.n_stages = 0;
        self.rpm = cap_int as f64;
        self.rpm_is_int = true;
        let mut r = self.run(ctx, p_in_pa, mdot, true)?;
        r.insert("turbo_rows".into(), Value::from(self.turbo_rows));
        r.insert("n_stages".into(), Value::from(0));
        r.insert("rpm".into(), Value::from(cap_int));
        r.insert("sized".into(), Value::Bool(false));
        r.insert("n_rejected_out_of_gaede_domain".into(), Value::from(n_ood));
        Ok(r)
    }
}

/// CPython `int(float)`: truncation; ValueError for NaN, OverflowError for an infinity.
pub fn py_int(x: f64) -> PyResult<i64> {
    if x.is_nan() {
        return Err(GasPathError::new(PyClass::ValueError, "cannot convert float NaN to integer"));
    }
    if x.is_infinite() {
        return Err(GasPathError::new(PyClass::OverflowError, "cannot convert float infinity to integer"));
    }
    Ok(x.trunc() as i64)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::materials::MaterialProps;

    fn mats() -> MaterialsView {
        let mut m = MaterialsView::default();
        m.0.insert(
            "Ti6Al4V".into(),
            MaterialProps {
                density: 4430.0,
                yield_mpa: 880.0,
                t_max_k: 700.0,
                gamma_min: 0.01,
                gamma0: 0.10,
                gamma_ea_ev: 0.08,
            },
        );
        m
    }

    #[test]
    fn default_run_converges_and_closes_mass_and_power() {
        let m = mats();
        let reg = Registry::default();
        let ctx = Ctx { materials: &m, registry: &reg };
        let c = DragCompressor { n_stages: 0, turbo_rows: 2, leak_conductance_m3_s: 1e-5, ..Default::default() };
        let mdot: SpMap = vec![("O".into(), 1e-7), ("N2".into(), 1e-7), ("O2".into(), 1e-8)];
        let r = c.run(ctx, 0.02, &mdot, true).unwrap();
        assert_eq!(r["solver_status"], "CONVERGED");
        assert_eq!(r["gaede_status"], GAEDE_IN_DOMAIN);
        for (s, v) in &mdot {
            assert_eq!(r["delivered_kgps"][s.as_str()].as_f64(), Some(*v), "CONS-C-01");
        }
        let f = |k: &str| r[k].as_f64().unwrap();
        let p_el = f("P_el_W");
        assert!(((f("P_gas_W") + f("P_bear_W")) / c.eta_motor + c.p_ctrl_w - p_el).abs() <= 1e-12 * p_el, "CONS-C-02");
        let omega = c.rpm * 2.0 * PI / 60.0;
        assert!((f("torque_Nm") * omega - (f("P_gas_W") + f("P_bear_W"))).abs() <= 1e-12 * p_el);
        // INV-C-02: no registered basis -> never qualified
        assert_eq!(r["rotor_qualification"], rs::Q_NOT_EVALUATED_MATERIAL_BASIS);
        assert_eq!(r["rotor_ok"], false);
        assert_eq!(r["sizing_mode"], rs::SIZING_PARAMETRIC_SENSITIVITY);
        assert_eq!(rs::qualification_eval_status(rs::Q_NOT_EVALUATED_MATERIAL_BASIS), EvalStatus::NotEvaluated);
    }

    #[test]
    fn overloaded_stage_is_out_of_domain() {
        let m = mats();
        let reg = Registry::default();
        let ctx = Ctx { materials: &m, registry: &reg };
        let c = DragCompressor::default();
        let mdot: SpMap = vec![("O".into(), 1e-5), ("N2".into(), 1e-5), ("O2".into(), 1e-5)];
        let r = c.run(ctx, 1e-6, &mdot, true).unwrap();
        assert_eq!(r["gaede_status"], GAEDE_OUT_OF_DOMAIN);
        assert_eq!(gaede_eval_status(GAEDE_OUT_OF_DOMAIN), EvalStatus::OutOfDomain);
        assert_eq!(solver_eval_status("MODEL_NOT_CONVERGED"), EvalStatus::ModelError);
    }

    #[test]
    fn unknown_material_and_overflow_fail_closed() {
        let m = mats();
        let reg = Registry::default();
        let ctx = Ctx { materials: &m, registry: &reg };
        let c = DragCompressor { rotor_material: "Unobtainium".into(), ..Default::default() };
        let mdot: SpMap = vec![("O".into(), 4e-7), ("N2".into(), 3e-7), ("O2".into(), 2e-8)];
        assert_eq!(c.run(ctx, 0.01, &mdot, true).unwrap_err().class, PyClass::KeyError);
        let c2 = DragCompressor { turbo_k_k: 1e3, ..Default::default() };
        assert_eq!(c2.run(ctx, 0.01, &mdot, true).unwrap_err().class, PyClass::OverflowError);
    }
}

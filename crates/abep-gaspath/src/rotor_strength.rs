//! Registered rotor-strength basis and rotor structural qualification (`abep_sim/rotor_strength.py`, owner decision
//! A9.9 S2.3 + S2.5 MCC-03; contract PARITY-C-ABEP_SIM_COMPRESSOR_PY-V1).
//!
//! Structural acceptance needs a REGISTERED basis (product form, temperature, yield AND ultimate allowables, factors,
//! maximum speed, proof spin). The repository registers none, so every rotor stays NOT_EVALUATED_MATERIAL_BASIS and
//! `rotor_ok` is false. The registry is an explicit value here (the reference keeps a module global). Stress model:
//! rim hoop stress sigma = rho u^2; margins Fty / (FS_y sigma) - 1 and Ftu / (FS_u sigma) - 1.

use crate::error::{value_error, PyResult};
use crate::pyops::{self, py_repr};
use crate::rec::{fnum, onum, Obj};
use abep_types::EvalStatus;
use serde_json::Value;

pub const SIZING_PARAMETRIC_SENSITIVITY: &str = "PARAMETRIC_SENSITIVITY";
pub const SIZING_REGISTERED_BASIS: &str = "REGISTERED_BASIS";
pub const Q_NOT_EVALUATED_MATERIAL_BASIS: &str = "NOT_EVALUATED_MATERIAL_BASIS";
pub const Q_NOT_EVALUATED_OUT_OF_DOMAIN: &str = "NOT_EVALUATED_OUT_OF_DOMAIN";
pub const Q_PASS: &str = "PASS";
pub const Q_FAIL: &str = "FAIL";
pub const LEGACY_SENSITIVITY_LABEL: &str = "LEGACY_CONSERVATIVE_SENSITIVITY: uncited materials.DB yield / uncited \
factor DragCompressor.stress_safety (2.0); not a cited requirement, not a qualification basis (owner decision A9.9 S2.3)";
pub const OWNER_DECISION_ID: &str = "A9.9 S2.3 (OQ-F3-01) + S2.5 MCC-03; A9.13 S6.9";

/// Qualification status -> EvalStatus (INV-C-03). PASS / FAIL are evaluations against a registered basis.
pub fn qualification_eval_status(q: &str) -> EvalStatus {
    match q {
        Q_NOT_EVALUATED_MATERIAL_BASIS => EvalStatus::NotEvaluated,
        Q_NOT_EVALUATED_OUT_OF_DOMAIN => EvalStatus::OutOfDomain,
        _ => EvalStatus::Evaluated,
    }
}

/// Statistical allowables at one temperature (Pa, K).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AllowablePoint {
    pub t_k: f64,
    pub fty_pa: f64,
    pub ftu_pa: f64,
}

/// A raw field as the reference receives it: text fields may be absent / non-text, numbers may be non-numbers.
#[derive(Debug, Clone, PartialEq)]
pub enum Field {
    Text(String),
    Num(f64),
    Other,
}

impl Field {
    fn text(&self) -> Option<&str> {
        match self {
            Field::Text(s) => Some(s),
            _ => None,
        }
    }
    fn num(&self) -> Option<f64> {
        match self {
            Field::Num(x) => Some(*x),
            _ => None,
        }
    }
}

/// One controlled rotor-strength basis record (all S2.3 minimum fields).
#[derive(Debug, Clone, PartialEq)]
pub struct RotorStrengthBasis {
    pub basis_id: Field,
    pub materials_db_key: Field,
    pub material_spec: Field,
    pub product_form: Field,
    pub condition: Field,
    /// None = not a 2-tuple
    pub section_thickness_range_m: Option<(Field, Field)>,
    pub design_temperature_k: Field,
    pub allowable_basis: Field,
    pub allowable_source: Field,
    /// None = not a tuple of AllowablePoint
    pub allowables: Option<Vec<(Field, Field, Field)>>,
    pub density_kg_m3: Field,
    pub density_source: Field,
    pub factor_yield: Field,
    pub factor_ultimate: Field,
    pub factors_source: Field,
    pub max_design_speed_rpm: Field,
    pub proof_spin_basis: Field,
    pub registration: Field,
    pub proof_spin_not_applicable_reason: Field,
    pub notes: String,
}

fn text_ok(f: &Field) -> bool {
    f.text().map(|s| !s.trim().is_empty()).unwrap_or(false)
}

fn finite_pos(f: &Field) -> bool {
    f.num().map(|x| x.is_finite() && x > 0.0).unwrap_or(false)
}

impl RotorStrengthBasis {
    pub fn id(&self) -> Option<&str> {
        self.basis_id.text()
    }
    pub fn db_key(&self) -> Option<&str> {
        self.materials_db_key.text()
    }
    fn points(&self) -> Vec<AllowablePoint> {
        self.allowables
            .as_ref()
            .map(|v| {
                v.iter()
                    .map(|(t, y, u)| AllowablePoint {
                        t_k: t.num().unwrap_or(f64::NAN),
                        fty_pa: y.num().unwrap_or(f64::NAN),
                        ftu_pa: u.num().unwrap_or(f64::NAN),
                    })
                    .collect()
            })
            .unwrap_or_default()
    }
    fn design_t(&self) -> f64 {
        self.design_temperature_k.num().unwrap_or(f64::NAN)
    }
}

/// Every reason this record is not a complete, admissible basis (empty = complete).
pub fn basis_problems(b: &RotorStrengthBasis) -> Vec<String> {
    let mut p = vec![];
    for (name, f) in [
        ("basis_id", &b.basis_id),
        ("materials_db_key", &b.materials_db_key),
        ("material_spec", &b.material_spec),
        ("product_form", &b.product_form),
        ("condition", &b.condition),
        ("allowable_basis", &b.allowable_basis),
        ("allowable_source", &b.allowable_source),
        ("density_source", &b.density_source),
        ("factors_source", &b.factors_source),
        ("registration", &b.registration),
    ] {
        if !text_ok(f) {
            p.push(format!("{name} missing"));
        }
    }
    let st_ok = match &b.section_thickness_range_m {
        Some((a, c)) => finite_pos(a) && finite_pos(c) && a.num() <= c.num(),
        None => false,
    };
    if !st_ok {
        p.push("section_thickness_range_m must be a finite positive (min, max) with min <= max".into());
    }
    if !finite_pos(&b.design_temperature_k) {
        p.push("design_temperature_K missing or non-positive".into());
    }
    if !finite_pos(&b.density_kg_m3) {
        p.push("density_kg_m3 missing or non-positive".into());
    }
    for (name, f) in [("factor_yield", &b.factor_yield), ("factor_ultimate", &b.factor_ultimate)] {
        if !(finite_pos(f) && f.num().unwrap_or(0.0) >= 1.0) {
            p.push(format!("{name} must be finite and >= 1"));
        }
    }
    if !finite_pos(&b.max_design_speed_rpm) {
        p.push("max_design_speed_rpm missing or non-positive".into());
    }
    if !text_ok(&b.proof_spin_basis) && !text_ok(&b.proof_spin_not_applicable_reason) {
        p.push("proof_spin_basis missing (or an explicit proof_spin_not_applicable_reason)".into());
    }
    match &b.allowables {
        Some(v) if !v.is_empty() => {
            let pts = b.points();
            let ts: Vec<f64> = pts.iter().map(|a| a.t_k).collect();
            let all_pos = v.iter().all(|(t, y, u)| finite_pos(t) && finite_pos(y) && finite_pos(u));
            // sorted / set(Ts) are only evaluated once every value is finite and positive (reference order of the
            // elif chain): a NaN temperature is reported, never sorted
            let increasing = || {
                let mut sorted = ts.clone();
                sorted.sort_by(|a, c| a.total_cmp(c));
                let mut uniq = sorted.clone();
                uniq.dedup();
                ts == sorted && uniq.len() == ts.len()
            };
            if !all_pos {
                p.push("allowables contain non-finite or non-positive values".into());
            } else if !increasing() {
                p.push("allowables must be strictly increasing in temperature".into());
            } else if pts.iter().any(|a| a.fty_pa > a.ftu_pa) {
                p.push("allowables have Fty > Ftu".into());
            } else if finite_pos(&b.design_temperature_k)
                && !(ts[0] <= b.design_t() && b.design_t() <= ts[ts.len() - 1])
            {
                p.push("design_temperature_K outside the tabulated allowables (no extrapolation)".into());
            }
        }
        _ => p.push("allowables (yield and ultimate versus temperature) missing".into()),
    }
    p
}

/// (Fty, Ftu) at T by linear interpolation inside the table; None outside it (no extrapolation).
pub fn allowables_at(b: &RotorStrengthBasis, t_k: f64) -> Option<(f64, f64)> {
    let pts = b.points();
    let (first, last) = (pts.first()?, pts.last()?);
    if !(first.t_k <= t_k && t_k <= last.t_k) {
        return None;
    }
    if pts.len() == 1 {
        return Some((first.fty_pa, first.ftu_pa));
    }
    for w in pts.windows(2) {
        let (a, c) = (w[0], w[1]);
        if a.t_k <= t_k && t_k <= c.t_k {
            let wgt = if c.t_k == a.t_k { 0.0 } else { (t_k - a.t_k) / (c.t_k - a.t_k) };
            return Some((a.fty_pa + wgt * (c.fty_pa - a.fty_pa), a.ftu_pa + wgt * (c.ftu_pa - a.ftu_pa)));
        }
    }
    None
}

/// Controlled registry of ADMITTED bases (explicit value; empty in the repository).
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Registry(pub Vec<RotorStrengthBasis>);

impl Registry {
    /// Admit a complete record; refuses an incomplete record or a duplicate id (ValueError).
    pub fn register_basis(&mut self, b: RotorStrengthBasis) -> PyResult<()> {
        let probs = basis_problems(&b);
        let id = b.id().unwrap_or("").to_string();
        if !probs.is_empty() {
            return Err(value_error(format!("rotor-strength basis {id:?} is incomplete: {probs:?}")));
        }
        if self.get_registered(Some(&id)).is_some() {
            return Err(value_error(format!("rotor-strength basis {id:?} is already registered")));
        }
        self.0.push(b);
        Ok(())
    }

    pub fn unregister_basis(&mut self, basis_id: &str) {
        self.0.retain(|b| b.id() != Some(basis_id));
    }

    pub fn get_registered(&self, basis_id: Option<&str>) -> Option<&RotorStrengthBasis> {
        let id = basis_id.filter(|s| !s.is_empty())?;
        self.0.iter().find(|b| b.id() == Some(id))
    }

    /// Ids of the registered bases that apply to `material` (sorted; no transfer).
    pub fn bases_for(&self, material: &str) -> Vec<String> {
        let mut v: Vec<String> =
            self.0.iter().filter(|b| b.db_key() == Some(material)).filter_map(|b| b.id().map(String::from)).collect();
        v.sort();
        v
    }
}

/// Cited reference values that are NOT a registered basis (incomplete; never qualify a rotor; never transferred).
pub fn reference_records() -> Value {
    Obj::new()
        .set(
            "REF-TI64-ANNEALED-PLATE-RT-ABASIS-MMPDS06",
            Obj::new()
                .s("status", "INCOMPLETE_REFERENCE_NOT_REGISTERED")
                .s("materials_db_key", "Ti6Al4V")
                .s("product_form", "annealed plate")
                .s("condition", "annealed")
                .set("section_thickness_range_m", Value::Array(vec![fnum(0.0508), fnum(0.1016)]))
                .s("temperature", "room temperature only (no elevated-temperature values held)")
                .s("allowable_basis", "A-basis")
                .f("Fty_Pa", 827e6)
                .f("Ftu_Pa", 896e6)
                .s(
                    "source",
                    "NASA-HDBK-6025 (2014-04-24) Sec. 3 'Mechanical Properties', p. 18 of 75, quoting MMPDS-06: 'the \
A-basis values of Ti-6Al-4V annealed plate with thickness of 50.8 to 101.6 mm (2 to 4 in) are: tensile strength = 896 \
MPa (130 ksi); yield strength = 827 MPa (120 ksi)' (secondary quotation; MMPDS itself not accessed); as recorded in \
docs/design_synthesis/f3_compressor (SRC-NASA-HDBK-6025)",
                )
                .set(
                    "missing_for_registration",
                    crate::rec::slist([
                        "actual rotor stock product form and section",
                        "rotor design temperature and allowables at it",
                        "density from the same controlled material definition",
                        "design/test factors",
                        "maximum design speed",
                        "proof-spin basis",
                        "owner registration",
                    ]),
                )
                .s(
                    "rule",
                    "valid only for this product form, thickness range and temperature; never transferred (A9.9 S2.3)",
                )
                .build(),
        )
        .build()
}

/// Largest tip speed with non-negative margins on both yield and ultimate at the design temperature (m/s).
pub fn tip_speed_allowable(b: &RotorStrengthBasis) -> PyResult<f64> {
    let (fty, ftu) =
        allowables_at(b, b.design_t()).ok_or_else(|| value_error("design temperature outside the allowables"))?;
    let fy = b.factor_yield.num().unwrap_or(f64::NAN);
    let fu = b.factor_ultimate.num().unwrap_or(f64::NAN);
    let s_allow = pyops::py_min(pyops::div(fty, fy)?, pyops::div(ftu, fu)?);
    pyops::sqrt(pyops::div(s_allow, b.density_kg_m3.num().unwrap_or(f64::NAN))?)
}

/// Optional numeric argument as the reference receives it (None, a finite / non-finite number, or a non-number).
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Arg {
    None,
    Num(f64),
    /// a Python int (repr without a decimal point)
    Int(i64),
    Other,
}

impl Arg {
    pub fn num(self) -> Option<f64> {
        match self {
            Arg::Num(x) => Some(x),
            Arg::Int(i) => Some(i as f64),
            _ => None,
        }
    }
}

/// Rotor structural qualification against a REGISTERED basis. Fail closed: any missing evidence gives
/// NOT_EVALUATED_*; `rotor_ok` is true only for PASS.
pub fn qualify_rotor(
    registry: &Registry,
    basis_id: Option<&str>,
    rotor_material: &str,
    tip_speed_mps: Arg,
    rpm: Arg,
    t_rotor_k: Arg,
    stock_thickness_m: Arg,
) -> PyResult<Value> {
    let mut reasons: Vec<String> = vec![];
    let mut q = Q_NOT_EVALUATED_MATERIAL_BASIS;
    let (mut my, mut mu, mut sigma, mut uallow) = (None, None, None, None);
    let mut ok = false;
    let id_val = basis_id.map(|s| Value::String(s.into())).unwrap_or(Value::Null);
    let finish = |q: &str, ok: bool, reasons: &[String], my, mu, sigma, uallow| -> Value {
        Obj::new()
            .s("rotor_qualification", q)
            .b("rotor_ok", ok)
            .set("rotor_strength_basis_id", id_val.clone())
            .set("rotor_qualification_reasons", crate::rec::slist(reasons))
            .set("margin_yield", onum(my))
            .set("margin_ultimate", onum(mu))
            .set("sigma_hoop_Pa", onum(sigma))
            .set("u_allow_registered_mps", onum(uallow))
            .s("owner_decision", OWNER_DECISION_ID)
            .build()
    };
    let b = registry.get_registered(basis_id);
    match basis_id {
        None => {
            reasons.push("no rotor-strength basis registered for this rotor".into());
            return Ok(finish(q, ok, &reasons, my, mu, sigma, uallow));
        }
        Some(id) if b.is_none() => {
            reasons.push(format!("basis {} is not in the registry", py_str_repr(id)));
            return Ok(finish(q, ok, &reasons, my, mu, sigma, uallow));
        }
        _ => {}
    }
    let b = b.expect("registered");
    let probs = basis_problems(b);
    if !probs.is_empty() {
        reasons.extend(probs);
        return Ok(finish(q, ok, &reasons, my, mu, sigma, uallow));
    }
    if b.db_key() != Some(rotor_material) {
        reasons.push(format!(
            "basis applies to {}, rotor material is {} (no transfer)",
            py_str_repr(b.db_key().unwrap_or("")),
            py_str_repr(rotor_material)
        ));
        return Ok(finish(q, ok, &reasons, my, mu, sigma, uallow));
    }
    let (lo, hi) = match &b.section_thickness_range_m {
        Some((a, c)) => (a.num().unwrap_or(f64::NAN), c.num().unwrap_or(f64::NAN)),
        None => (f64::NAN, f64::NAN),
    };
    let st = match stock_thickness_m.num() {
        Some(x) if x.is_finite() && x > 0.0 => x,
        _ => {
            reasons.push("rotor stock thickness/section not stated".into());
            return Ok(finish(q, ok, &reasons, my, mu, sigma, uallow));
        }
    };
    if !(lo <= st && st <= hi) {
        reasons.push(format!(
            "rotor stock thickness {} m outside the basis section range [{}, {}] m",
            py_repr(st),
            py_repr(lo),
            py_repr(hi)
        ));
        return Ok(finish(q, ok, &reasons, my, mu, sigma, uallow));
    }
    let t_rotor = match t_rotor_k.num() {
        Some(x) if x.is_finite() => x,
        _ => {
            q = Q_NOT_EVALUATED_OUT_OF_DOMAIN;
            reasons.push("rotor temperature not finite".into());
            return Ok(finish(q, ok, &reasons, my, mu, sigma, uallow));
        }
    };
    let td = b.design_t();
    if t_rotor > td {
        q = Q_NOT_EVALUATED_OUT_OF_DOMAIN;
        reasons.push(format!(
            "rotor temperature {} K above the basis design temperature {} K",
            py_format_6g(t_rotor),
            py_repr(td)
        ));
        return Ok(finish(q, ok, &reasons, my, mu, sigma, uallow));
    }
    for (nm, v) in [("tip_speed_mps", tip_speed_mps), ("rpm", rpm)] {
        let good = matches!(v.num(), Some(x) if x.is_finite() && x >= 0.0);
        if !good {
            q = Q_NOT_EVALUATED_OUT_OF_DOMAIN;
            reasons.push(format!("{nm} must be finite and >= 0 (got {})", arg_repr(v)));
            return Ok(finish(q, ok, &reasons, my, mu, sigma, uallow));
        }
    }
    let (u, rpm_v) = (tip_speed_mps.num().expect("checked"), rpm.num().expect("checked"));
    let (fty, ftu) = allowables_at(b, td).expect("inside table");
    let rho = b.density_kg_m3.num().expect("complete");
    let fy = b.factor_yield.num().expect("complete");
    let fu = b.factor_ultimate.num().expect("complete");
    let s = rho * pyops::pow(u, 2.0)?;
    let m_y = if s > 0.0 { fty / (fy * s) - 1.0 } else { f64::INFINITY };
    let m_u = if s > 0.0 { ftu / (fu * s) - 1.0 } else { f64::INFINITY };
    my = Some(m_y);
    mu = Some(m_u);
    sigma = Some(s);
    uallow = Some(tip_speed_allowable(b)?);
    if m_y.is_nan() || m_u.is_nan() || m_y == f64::NEG_INFINITY || m_u == f64::NEG_INFINITY {
        q = Q_NOT_EVALUATED_OUT_OF_DOMAIN;
        reasons.push("margins not finite".into());
        return Ok(finish(q, ok, &reasons, my, mu, sigma, uallow));
    }
    let mut fails: Vec<String> = vec![];
    if m_y < 0.0 {
        fails.push("yield margin negative".into());
    }
    if m_u < 0.0 {
        fails.push("ultimate margin negative".into());
    }
    let max_rpm = b.max_design_speed_rpm.num().expect("complete");
    if rpm_v > max_rpm {
        fails.push(format!(
            "speed {} rpm above the registered maximum design speed {} rpm",
            arg_repr(rpm),
            py_repr(max_rpm)
        ));
    }
    if !fails.is_empty() {
        q = Q_FAIL;
        reasons.extend(fails);
    } else {
        q = Q_PASS;
        ok = true;
    }
    Ok(finish(q, ok, &reasons, my, mu, sigma, uallow))
}

/// Python `repr(str)` for simple ASCII text (single quotes).
pub fn py_str_repr(s: &str) -> String {
    if s.contains('\'') && !s.contains('"') {
        format!("\"{s}\"")
    } else {
        format!("'{}'", s.replace('\\', "\\\\").replace('\'', "\\'"))
    }
}

fn arg_repr(a: Arg) -> String {
    match a {
        Arg::None => "None".into(),
        Arg::Num(x) => py_repr(x),
        Arg::Int(i) => i.to_string(),
        Arg::Other => "<other>".into(),
    }
}

/// Python `format(x, '.6g')`.
pub fn py_format_6g(x: f64) -> String {
    pyops::py_format_g(x)
}

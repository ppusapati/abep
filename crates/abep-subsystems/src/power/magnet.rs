//! H-1 magnet load model (`abep_sim/magnet_power.py`, lane PPUMAG v1, without the ECR resonance field): the
//! load-side power at the coil terminals (I^2 R) of an electromagnet, or the size and mass of a permanent magnet
//! (0 W), for a required gap field. The bus-side draw also needs the magnet-supply efficiency, which is the ledger's
//! evidence record, never a default here.
//!
//! Equations and sources (as the reference): [E1] magnetic circuit, Ampere's law with element reluctances l / (mu A)
//! and a leakage factor k = core flux / gap flux >= 1 (Kirtley, MIT 6.007 notes Sec. 3.2-3.5); [E2] permanent magnet
//! with a linear recoil line (Kirtley, MIT 6.061 ch. 12 Sec. 4.3); [E3] R(T) = R_20 [1 + alpha_20 (T - 20 C)] and
//! the IACS values (NBS Handbook 100, 1966, pp. 1-3); [E4] the AWG progression (NBS Handbook 100 Sec. 2.2);
//! [E5] coil P = (N I)^2 rho l_mt / (k A_w) and the integer-turn coil; [E6] mu0 (CODATA 2022). Every geometry, fill
//! factor, temperature and magnet datum is a caller input; inputs outside a declared validity domain are refused,
//! never extrapolated. Results are model-derived.

use super::pyfmt::{format_g, libm_pow, py_not_gt, py_not_lt};
use super::{PowerError, PowerResult};
use abep_types::pyjson::{float_repr, py_repr, py_repr_str, Dict, Value};

pub const MAGNET_POWER_VERSION: &str = "magnet_power_v1";
/// [E6] CODATA 2022 vacuum magnetic permeability (fundamental constant, not a design default).
pub const MU0_N_PER_A2: f64 = 1.25663706127e-6;
const INCH_M: f64 = 0.0254;
const VE: &str = "ValueError";

fn ve(m: String) -> PowerError {
    PowerError::new(VE, m)
}

fn dom(m: String) -> PowerError {
    PowerError::out_of_domain(VE, m)
}

/// The magnet module's `_real` (no -0.0 normalisation).
fn real(v: &Value, what: &str) -> PowerResult<f64> {
    if !matches!(v, Value::Int(_) | Value::Float(_)) {
        return Err(ve(format!("{what} must be a real number, got {} {}", v.type_name(), py_repr(v))));
    }
    let x = v.to_f64().map_err(PowerError::from)?;
    if !x.is_finite() {
        return Err(ve(format!("{what} must be finite, got {}", float_repr(x))));
    }
    Ok(x)
}

fn pos(v: &Value, what: &str) -> PowerResult<f64> {
    let x = real(v, what)?;
    if py_not_gt(x, 0.0) {
        return Err(ve(format!("{what} must be > 0, got {}", float_repr(x))));
    }
    Ok(x)
}

fn get<'a>(d: &'a Dict, k: &str) -> &'a Value {
    d.get(k).unwrap_or(&Value::Null)
}

/// Linear resistance-temperature conductor model with a declared validity domain ([E3]).
#[derive(Debug, Clone, PartialEq)]
pub struct ConductorMaterial {
    pub name: String,
    pub rho_ref_ohm_m: f64,
    pub t_ref_c: f64,
    pub alpha_ref_per_k: f64,
    pub t_min_c: f64,
    pub t_max_c: f64,
    pub density_kg_m3: f64,
    pub source: String,
}

impl ConductorMaterial {
    /// `ConductorMaterial(**fields)` with its `__post_init__` checks.
    pub fn from_fields(f: &Dict) -> PowerResult<Self> {
        let name = match get(f, "name") {
            Value::Str(s) if !s.is_empty() => s.clone(),
            _ => return Err(ve("ConductorMaterial.name must be a non-empty string".into())),
        };
        let rho = pos(get(f, "rho_ref_ohm_m"), "rho_ref_ohm_m")?;
        let t_ref = real(get(f, "T_ref_C"), "T_ref_C")?;
        let alpha = pos(get(f, "alpha_ref_per_K"), "alpha_ref_per_K")?;
        let lo = real(get(f, "T_min_C"), "T_min_C")?;
        let hi = real(get(f, "T_max_C"), "T_max_C")?;
        if py_not_lt(lo, hi) {
            return Err(ve(format!(
                "validity domain must satisfy T_min_C < T_max_C, got [{}, {}]",
                float_repr(lo),
                float_repr(hi)
            )));
        }
        if !(lo <= t_ref && t_ref <= hi) {
            return Err(ve("T_ref_C must lie inside the validity domain".into()));
        }
        let density = pos(get(f, "density_kg_m3"), "density_kg_m3")?;
        let source = match get(f, "source") {
            Value::Str(s) if !abep_types::pyjson::py_strip(s).is_empty() => s.clone(),
            _ => return Err(ve("ConductorMaterial.source must cite where the values come from".into())),
        };
        Ok(ConductorMaterial {
            name,
            rho_ref_ohm_m: rho,
            t_ref_c: t_ref,
            alpha_ref_per_k: alpha,
            t_min_c: lo,
            t_max_c: hi,
            density_kg_m3: density,
            source,
        })
    }

    /// `dataclasses.asdict(material)`.
    pub fn to_value(&self) -> Value {
        let mut d = Dict::new();
        d.insert("name", Value::str(self.name.clone()));
        d.insert("rho_ref_ohm_m", Value::Float(self.rho_ref_ohm_m));
        d.insert("T_ref_C", Value::Float(self.t_ref_c));
        d.insert("alpha_ref_per_K", Value::Float(self.alpha_ref_per_k));
        d.insert("T_min_C", Value::Float(self.t_min_c));
        d.insert("T_max_C", Value::Float(self.t_max_c));
        d.insert("density_kg_m3", Value::Float(self.density_kg_m3));
        d.insert("source", Value::str(self.source.clone()));
        Value::Dict(d)
    }
}

/// [E3] NBS Handbook 100 (1966) pp. 1-3: IACS 0.017241 ohm mm^2/m at 20 C, alpha_20 = 0.00393 /K (wire resistance,
/// free expansion), density 8.89 g/cm^3; validity domain the stated linear range [0, 200] C. Callers pass it
/// explicitly.
pub fn annealed_copper_iacs() -> ConductorMaterial {
    ConductorMaterial {
        name: "annealed copper, International Annealed Copper Standard (100 % IACS)".into(),
        rho_ref_ohm_m: 1.7241e-8,
        t_ref_c: 20.0,
        alpha_ref_per_k: 0.00393,
        t_min_c: 0.0,
        t_max_c: 200.0,
        density_kg_m3: 8890.0,
        source: "NBS Handbook 100, Copper Wire Tables (1966), pp. 1-3; \
                 https://nvlpubs.nist.gov/nistpubs/Legacy/hb/nbshandbook100.pdf"
            .into(),
    }
}

/// A material argument: a constructed material, or any other value (refused where the reference checks the type).
#[derive(Debug, Clone)]
pub enum MaterialArg {
    Material(ConductorMaterial),
    Raw(Value),
}

impl MaterialArg {
    fn require(&self) -> PowerResult<&ConductorMaterial> {
        match self {
            MaterialArg::Material(m) => Ok(m),
            MaterialArg::Raw(v) => Err(ve(format!("material must be a ConductorMaterial, got {}", v.type_name()))),
        }
    }

    /// Attribute access on a non-material (`AttributeError` in the reference).
    fn attr(&self, name: &str) -> PowerResult<&ConductorMaterial> {
        match self {
            MaterialArg::Material(m) => Ok(m),
            MaterialArg::Raw(v) => {
                Err(PowerError::new("AttributeError", format!("'{}' object has no attribute '{name}'", v.type_name())))
            }
        }
    }
}

/// One soft-magnetic element of the flux return path ([E1]).
#[derive(Debug, Clone, PartialEq)]
pub struct CoreSegment {
    pub name: String,
    pub length_m: f64,
    pub area_m2: f64,
    pub mu_r: f64,
    pub b_max_t: f64,
}

impl CoreSegment {
    /// `CoreSegment(**fields)` with its `__post_init__` checks.
    pub fn from_fields(f: &Dict) -> PowerResult<Self> {
        let name = match get(f, "name") {
            Value::Str(s) if !s.is_empty() => s.clone(),
            _ => return Err(ve("CoreSegment.name must be a non-empty string".into())),
        };
        let length = pos(get(f, "length_m"), &format!("{name}.length_m"))?;
        let area = pos(get(f, "area_m2"), &format!("{name}.area_m2"))?;
        let mu = real(get(f, "mu_r"), &format!("{name}.mu_r"))?;
        if mu < 1.0 {
            return Err(ve(format!(
                "{name}.mu_r must be >= 1 for a soft-magnetic return path, got {}",
                float_repr(mu)
            )));
        }
        let bmax = pos(get(f, "B_max_T"), &format!("{name}.B_max_T"))?;
        Ok(CoreSegment { name, length_m: length, area_m2: area, mu_r: mu, b_max_t: bmax })
    }

    pub fn to_value(&self) -> Value {
        let mut d = Dict::new();
        d.insert("name", Value::str(self.name.clone()));
        d.insert("length_m", Value::Float(self.length_m));
        d.insert("area_m2", Value::Float(self.area_m2));
        d.insert("mu_r", Value::Float(self.mu_r));
        d.insert("B_max_T", Value::Float(self.b_max_t));
        Value::Dict(d)
    }
}

/// A core-segments argument: a sequence whose elements are segments or other values, or a non-sequence value.
#[derive(Debug, Clone)]
pub enum SegmentsArg {
    List(Vec<SegmentElem>),
    Raw(Value),
}

#[derive(Debug, Clone)]
pub enum SegmentElem {
    Segment(CoreSegment),
    Raw(Value),
}

fn segments(arg: &SegmentsArg) -> PowerResult<Vec<&CoreSegment>> {
    let SegmentsArg::List(items) = arg else {
        return Err(ve(
            "core_segments must be a sequence of CoreSegment (pass () explicitly for an ideal-iron circuit)".into(),
        ));
    };
    items
        .iter()
        .map(|e| match e {
            SegmentElem::Segment(s) => Ok(s),
            SegmentElem::Raw(v) => {
                Err(ve(format!("core_segments must contain CoreSegment objects, got {}", v.type_name())))
            }
        })
        .collect()
}

/// `resistance_factor(material, T_C)` = R(T)/R(T_ref); refuses a temperature outside the validity domain.
pub fn resistance_factor(material: &MaterialArg, t_c: &Value) -> PowerResult<f64> {
    let m = material.require()?;
    let t = real(t_c, "coil temperature T_C")?;
    if !(m.t_min_c <= t && t <= m.t_max_c) {
        return Err(dom(format!(
            "coil temperature {} C outside the validity domain [{}, {}] C of {}; the linear model is not extrapolated",
            float_repr(t),
            float_repr(m.t_min_c),
            float_repr(m.t_max_c),
            py_repr_str(&m.name)
        )));
    }
    Ok(1.0 + m.alpha_ref_per_k * (t - m.t_ref_c))
}

/// `wire_resistance_ohm(length_m, area_m2, material, T_C)`.
pub fn wire_resistance_ohm(length_m: &Value, area_m2: &Value, material: &MaterialArg, t_c: &Value) -> PowerResult<f64> {
    let l = pos(length_m, "conductor length_m")?;
    let a = pos(area_m2, "conductor area_m2")?;
    let rho = material.attr("rho_ref_ohm_m")?.rho_ref_ohm_m;
    Ok(rho * l / a * resistance_factor(material, t_c)?)
}

/// `awg_diameter_m(gauge)`: bare diameter of American Wire Gage `gauge` (0000, 000, 00 as -3, -2, -1).
pub fn awg_diameter_m(gauge: &Value) -> PowerResult<f64> {
    let Value::Int(i) = gauge else {
        return Err(ve(format!(
            "AWG gauge must be an integer (0000 -> -3, 000 -> -2, 00 -> -1), got {}",
            py_repr(gauge)
        )));
    };
    let n = i.as_i64().filter(|n| (-3..=56).contains(n));
    let Some(n) = n else {
        return Err(dom(format!("AWG gauge {i} outside the defined range 0000 (-3) .. 56 (NBS Handbook 100)")));
    };
    Ok(0.0050 * INCH_M * libm_pow(92.0, (36 - n) as f64 / 39.0))
}

/// The lumped magnetic circuit of [E1].
#[derive(Debug, Clone, PartialEq)]
pub struct Circuit {
    pub phi_gap_wb: f64,
    pub phi_core_wb: f64,
    pub mmf_gap_a: f64,
    pub mmf_core_a: f64,
    /// (name, B_T, mmf_A) per segment.
    pub segments: Vec<(String, f64, f64)>,
    pub leakage_factor: f64,
}

impl Circuit {
    fn insert_into(&self, d: &mut Dict) {
        d.insert("phi_gap_Wb", Value::Float(self.phi_gap_wb));
        d.insert("phi_core_Wb", Value::Float(self.phi_core_wb));
        d.insert("mmf_gap_A", Value::Float(self.mmf_gap_a));
        d.insert("mmf_core_A", Value::Float(self.mmf_core_a));
        d.insert(
            "segments",
            Value::List(
                self.segments
                    .iter()
                    .map(|(n, b, f)| {
                        let mut s = Dict::new();
                        s.insert("name", Value::str(n.clone()));
                        s.insert("B_T", Value::Float(*b));
                        s.insert("mmf_A", Value::Float(*f));
                        Value::Dict(s)
                    })
                    .collect(),
            ),
        );
        d.insert("leakage_factor", Value::Float(self.leakage_factor));
    }

    pub fn ni_a(&self) -> f64 {
        self.mmf_gap_a + self.mmf_core_a
    }
}

fn circuit(
    b_gap: &Value,
    gap_len: &Value,
    gap_area: &Value,
    segs: &SegmentsArg,
    leakage: &Value,
) -> PowerResult<Circuit> {
    let b_g = pos(b_gap, "B_gap_T")?;
    let g = pos(gap_len, "gap_length_m")?;
    let a_g = pos(gap_area, "gap_area_m2")?;
    let k = real(leakage, "leakage_factor")?;
    if k < 1.0 {
        return Err(ve(format!("leakage_factor (core flux / gap flux) must be >= 1, got {}", float_repr(k))));
    }
    let segs = segments(segs)?;
    let phi_gap = b_g * a_g;
    let phi_core = k * phi_gap;
    let f_gap = b_g * g / MU0_N_PER_A2;
    let mut f_core = 0.0_f64;
    let mut out = Vec::new();
    for s in segs {
        let b_s = phi_core / s.area_m2;
        if b_s > s.b_max_t {
            return Err(dom(format!(
                "core segment {}: B = {} T exceeds its declared limit {} T; the linear magnetic-circuit model is not \
                 valid (enlarge the section)",
                py_repr_str(&s.name),
                format_g(b_s, 4),
                float_repr(s.b_max_t)
            )));
        }
        let f_s = b_s * s.length_m / (MU0_N_PER_A2 * s.mu_r);
        f_core += f_s;
        out.push((s.name.clone(), b_s, f_s));
    }
    Ok(Circuit {
        phi_gap_wb: phi_gap,
        phi_core_wb: phi_core,
        mmf_gap_a: f_gap,
        mmf_core_a: f_core,
        segments: out,
        leakage_factor: k,
    })
}

/// `ampere_turns(...)`: ampere-turns N I for the gap field and its circuit.
pub fn ampere_turns(
    b_gap: &Value,
    gap_len: &Value,
    gap_area: &Value,
    segs: &SegmentsArg,
    leakage: &Value,
) -> PowerResult<(Circuit, Value)> {
    let c = circuit(b_gap, gap_len, gap_area, segs, leakage)?;
    let mut d = Dict::new();
    d.insert("version", Value::str(MAGNET_POWER_VERSION));
    d.insert("NI_A", Value::Float(c.ni_a()));
    c.insert_into(&mut d);
    Ok((c, Value::Dict(d)))
}

fn fill(fill_factor: &Value) -> PowerResult<f64> {
    let k = real(fill_factor, "fill_factor")?;
    if !(0.0 < k && k < 1.0) {
        return Err(ve(format!("copper fill_factor must be in (0, 1), got {}", float_repr(k))));
    }
    Ok(k)
}

/// `coil_power_continuous_W(...)` = (N I)^2 rho(T) l_mt / (k A_w), the gauge-independent continuous-turn limit [E5].
pub fn coil_power_continuous_w(
    ni: &Value,
    window_area: &Value,
    fill_factor: &Value,
    mean_turn: &Value,
    material: &MaterialArg,
    t_c: &Value,
) -> PowerResult<f64> {
    let ni = pos(ni, "NI_A")?;
    let a_w = pos(window_area, "window_area_m2")?;
    let k = fill(fill_factor)?;
    let l_mt = pos(mean_turn, "mean_turn_length_m")?;
    let f_t = resistance_factor(material, t_c)?;
    let rho = material.require()?.rho_ref_ohm_m * f_t;
    Ok(ni * ni * rho * l_mt / (k * a_w))
}

/// `coil_design(...)`: integer-turn coil filling the winding window with round bare wire [E5].
#[allow(clippy::too_many_arguments)]
pub fn coil_design(
    ni: &Value,
    window_area: &Value,
    fill_factor: &Value,
    mean_turn: &Value,
    wire_diameter: &Value,
    material: &MaterialArg,
    t_c: &Value,
) -> PowerResult<Value> {
    let ni = pos(ni, "NI_A")?;
    let a_w = pos(window_area, "window_area_m2")?;
    let k = fill(fill_factor)?;
    let l_mt = pos(mean_turn, "mean_turn_length_m")?;
    let d = pos(wire_diameter, "wire_diameter_m")?;
    let m = material.require()?;
    let a_cu = std::f64::consts::PI * d * d / 4.0;
    let n = (k * a_w / a_cu * (1.0 + 1e-12)).floor();
    if n < 1.0 {
        return Err(dom(format!(
            "a {} mm wire does not fit once in {} x {} m^2 of copper area",
            format_g(d * 1e3, 4),
            format_g(k, 3),
            format_g(a_w, 4)
        )));
    }
    let i = ni / n;
    let r = wire_resistance_ohm(&Value::Float(n * l_mt), &Value::Float(a_cu), material, t_c)?;
    let p = i * i * r;
    let t = real(t_c, "coil temperature T_C")?;
    let mut o = Dict::new();
    o.insert("version", Value::str(MAGNET_POWER_VERSION));
    o.insert("N_turns", Value::int(n as i64));
    o.insert("I_A", Value::Float(i));
    o.insert("R_ohm", Value::Float(r));
    o.insert("V_V", Value::Float(i * r));
    o.insert("P_W", Value::Float(p));
    o.insert("J_A_per_m2", Value::Float(i / a_cu));
    o.insert("wire_area_m2", Value::Float(a_cu));
    o.insert("fill_achieved", Value::Float(n * a_cu / a_w));
    o.insert("copper_mass_kg", Value::Float(m.density_kg_m3 * n * l_mt * a_cu));
    o.insert("T_C", Value::Float(t));
    o.insert("resistance_factor", Value::Float(resistance_factor(material, t_c)?));
    o.insert("material", Value::str(m.name.clone()));
    Ok(Value::Dict(o))
}

fn field_f(v: &Value, k: &str) -> f64 {
    match v.as_dict().and_then(|d| d.get(k)) {
        Some(Value::Float(x)) => *x,
        _ => f64::NAN,
    }
}

/// `electromagnet(...)`: ampere-turns [E1] + integer-turn coil [E5]; `P_load_W` is the coil I^2 R at its terminals.
#[allow(clippy::too_many_arguments)]
pub fn electromagnet(
    b_gap: &Value,
    gap_len: &Value,
    gap_area: &Value,
    segs: &SegmentsArg,
    leakage: &Value,
    window_area: &Value,
    fill_factor: &Value,
    mean_turn: &Value,
    wire_diameter: &Value,
    material: &MaterialArg,
    t_c: &Value,
) -> PowerResult<Value> {
    let (c, circ) = ampere_turns(b_gap, gap_len, gap_area, segs, leakage)?;
    let ni = Value::Float(c.ni_a());
    let coil = coil_design(&ni, window_area, fill_factor, mean_turn, wire_diameter, material, t_c)?;
    let p_cont = coil_power_continuous_w(&ni, window_area, fill_factor, mean_turn, material, t_c)?;
    let mut d = Dict::new();
    d.insert("version", Value::str(MAGNET_POWER_VERSION));
    d.insert("kind", Value::str("electromagnet"));
    d.insert("circuit", circ);
    let p_load = field_f(&coil, "P_W");
    d.insert("coil", coil);
    d.insert("P_load_W", Value::Float(p_load));
    d.insert("P_continuous_limit_W", Value::Float(p_cont));
    d.insert("evidence_class", Value::str("model-derived"));
    Ok(Value::Dict(d))
}

/// `remanence_at_T(B_r_ref_T, alpha_Br_per_K, T_ref_C, T_C)` = B_r,ref [1 + alpha (T - T_ref)].
pub fn remanence_at_t(b_r_ref: &Value, alpha: &Value, t_ref: &Value, t_c: &Value) -> PowerResult<f64> {
    let b = pos(b_r_ref, "B_r_ref_T")?;
    let a = real(alpha, "alpha_Br_per_K")?;
    let t = real(t_c, "T_C")?;
    let tr = real(t_ref, "T_ref_C")?;
    let b_t = b * (1.0 + a * (t - tr));
    if py_not_gt(b_t, 0.0) {
        return Err(dom(format!(
            "remanence at {} C is not positive ({}); outside any linear model",
            abep_types::pyjson::py_str(t_c),
            float_repr(b_t)
        )));
    }
    Ok(b_t)
}

/// `permanent_magnet(...)`: magnet length and mass for the gap field [E2]; electrical power 0 W.
#[allow(clippy::too_many_arguments)]
pub fn permanent_magnet(
    b_gap: &Value,
    gap_len: &Value,
    gap_area: &Value,
    segs: &SegmentsArg,
    leakage: &Value,
    magnet_area: &Value,
    b_r: &Value,
    mu_rec: &Value,
    h_knee: &Value,
    density: &Value,
) -> PowerResult<Value> {
    let c = circuit(b_gap, gap_len, gap_area, segs, leakage)?;
    let a_m = pos(magnet_area, "magnet_area_m2")?;
    let b_r = pos(b_r, "B_r_T")?;
    let mu = real(mu_rec, "mu_rec")?;
    if mu < 1.0 {
        return Err(ve(format!("relative recoil permeability mu_rec must be >= 1, got {}", float_repr(mu))));
    }
    let h_knee = pos(h_knee, "H_knee_A_per_m (magnitude)")?;
    let rho = pos(density, "magnet_density_kg_m3")?;
    let b_m = c.phi_core_wb / a_m;
    if b_m >= b_r {
        return Err(dom(format!(
            "magnet flux density {} T >= remanence {} T: magnet_area_m2 too small for the flux",
            format_g(b_m, 4),
            format_g(b_r, 4)
        )));
    }
    let h_m = (b_m - b_r) / (MU0_N_PER_A2 * mu);
    if -h_m > h_knee {
        return Err(dom(format!(
            "operating point |H_m| = {} A/m beyond the knee {} A/m (irreversible demagnetization); enlarge \
             magnet_area_m2",
            format_g(-h_m, 4),
            format_g(h_knee, 4)
        )));
    }
    let f_ext = c.mmf_gap_a + c.mmf_core_a;
    let l_m = f_ext / (-h_m);
    let v_m = l_m * a_m;
    let mut circ = Dict::new();
    c.insert_into(&mut circ);
    let mut d = Dict::new();
    d.insert("version", Value::str(MAGNET_POWER_VERSION));
    d.insert("kind", Value::str("permanent_magnet"));
    d.insert("circuit", Value::Dict(circ));
    d.insert("B_m_T", Value::Float(b_m));
    d.insert("H_m_A_per_m", Value::Float(h_m));
    d.insert("magnet_length_m", Value::Float(l_m));
    d.insert("magnet_volume_m3", Value::Float(v_m));
    d.insert("magnet_mass_kg", Value::Float(rho * v_m));
    d.insert("P_load_W", Value::Float(0.0));
    d.insert("evidence_class", Value::str("model-derived"));
    Ok(Value::Dict(d))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn f(x: f64) -> Value {
        Value::Float(x)
    }

    #[test]
    fn copper_resistance_factor_and_awg() {
        let cu = MaterialArg::Material(annealed_copper_iacs());
        assert_eq!(resistance_factor(&cu, &f(20.0)).unwrap(), 1.0);
        let e = resistance_factor(&cu, &f(250.0)).unwrap_err();
        assert_eq!(e.status, abep_types::EvalStatus::OutOfDomain);
        let d36 = awg_diameter_m(&Value::int(36)).unwrap();
        assert!((d36 - 0.0050 * INCH_M).abs() < 1e-18);
        assert!(awg_diameter_m(&Value::Bool(true)).is_err());
    }

    #[test]
    fn coil_identities() {
        let cu = MaterialArg::Material(annealed_copper_iacs());
        let c = coil_design(&f(2000.0), &f(1e-4), &f(0.6), &f(0.3), &f(5e-4), &cu, &f(100.0)).unwrap();
        let p = field_f(&c, "P_W");
        let i = field_f(&c, "I_A");
        let v = field_f(&c, "V_V");
        assert!((p - i * v).abs() <= 1e-12 * p);
    }
}

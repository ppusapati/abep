//! RF generator / matching kernels of the P2 impedance-map package (`p2_framework.py`, `p2_impedance_reducer.py`)
//! and the P1 refusal that a generator mains input is never P_bus (`p1_reducer.p_bus_from_generator_input`).
//!
//! Touchstone 1.1 ingestion (REF-TOUCHSTONE11; spec defaults never applied silently), the one-port three-term SOL
//! error model and its correction (REF-WALKER2023 Eq. (8)), ladder ABCD networks, the matched dissipated fraction,
//! V/I probe power and impedance, and the basic two-port relations (S <-> ABCD, cascade, input impedance,
//! de-embedding, transfer efficiency, fixture transfer, line standing-wave stress). Nothing here predicts an
//! impedance, a power, a plasma state or a rating; RF ratings stay TBD_AFTER_IMPEDANCE_MAP (A9.2) and the matched
//! chain is NOT_EVALUATED until a measured impedance-map point is registered ([`rf_chain_status`]).

use super::cplx::{radians, rect, sum, C};
use super::pyfmt::{libm_pow, py_float_from_str, py_not_gt, round_sig};
use super::{PowerError, PowerResult};
use abep_types::pyjson::{float_repr, py_eq, py_isspace, py_repr, py_repr_str, py_str, Dict, Value};
use abep_types::EvalStatus;

pub fn cval(z: C) -> Value {
    Value::List(vec![Value::Float(z.re), Value::Float(z.im)])
}

fn ts(m: String) -> PowerError {
    PowerError::new("TouchstoneError", m)
}

fn rec_err(m: impl Into<String>) -> PowerError {
    PowerError::new("RecordError", m)
}

// ================================================================================================ reducer basics
/// `_finite(x, what)` of the reducer (RecordError).
fn finite(x: &Value, what: &str) -> PowerResult<f64> {
    let ok = matches!(x, Value::Int(_) | Value::Float(_)) && x.to_f64().map_err(PowerError::from)?.is_finite();
    if !ok {
        return Err(rec_err(format!("{what}: finite number required, got {}", py_repr(x))));
    }
    x.to_f64().map_err(PowerError::from)
}

/// `cx(v, what)`: [re, im] -> complex; anything else refused (RecordError).
pub fn cx(v: &Value, what: &str) -> PowerResult<C> {
    match v {
        Value::List(l) if l.len() == 2 => {
            let re = finite(&l[0], &format!("{what}.re"))?;
            let im = finite(&l[1], &format!("{what}.im"))?;
            Ok(C::new(re, im))
        }
        _ => Err(rec_err(format!("{what}: complex value must be [re, im], got {}", py_repr(v)))),
    }
}

/// The framework's `_cxv`: `cx` with its RecordError re-raised as FrameworkError.
fn cxv(v: &Value, what: &str) -> PowerResult<C> {
    cx(v, what).map_err(|e| PowerError::new("FrameworkError", e.message))
}

pub fn gamma_from_z(z: C, z0: f64) -> PowerResult<C> {
    if z0 <= 0.0 {
        return Err(rec_err("Z0 must be > 0"));
    }
    let zz0 = C::real(z0);
    if z.add(zz0).is_zero() {
        return Err(rec_err("Z_L = -Z0: reflection coefficient undefined"));
    }
    z.sub(zz0).div(z.add(zz0))
}

pub fn z_from_gamma(g: C, z0: f64) -> PowerResult<C> {
    if g.eq_real(1.0) {
        return Err(rec_err("Gamma = 1 (open): impedance undefined"));
    }
    C::real(z0).mul(C::real(1.0).add(g)).div(C::real(1.0).sub(g))
}

pub fn vswr(gmag: f64) -> PowerResult<f64> {
    if !(0.0..1.0).contains(&gmag) {
        return Err(rec_err(format!("|Gamma| = {} outside [0, 1): VSWR undefined", float_repr(gmag))));
    }
    Ok((1.0 + gmag) / (1.0 - gmag))
}

pub fn gamma_mag_from_powers(p_fwd: f64, p_ref: f64) -> PowerResult<f64> {
    if p_fwd <= 0.0 || p_ref < 0.0 {
        return Err(rec_err("P_forward must be > 0 and P_reflected >= 0"));
    }
    if p_ref > p_fwd {
        return Err(rec_err("P_reflected > P_forward at the coupler plane: inconsistent reading"));
    }
    Ok((p_ref / p_fwd).sqrt())
}

pub type Abcd = [C; 4];

pub fn s_to_abcd(s11: C, s12: C, s21: C, s22: C, z0: f64) -> PowerResult<Abcd> {
    if s21.is_zero() {
        return Err(rec_err("S21 = 0: two-port has no transmission, cannot be de-embedded"));
    }
    let one = C::real(1.0);
    let two_s21 = C::real(2.0).mul(s21);
    let z = C::real(z0);
    let a = one.add(s11).mul(one.sub(s22)).add(s12.mul(s21)).div(two_s21)?;
    let b = z.mul(one.add(s11).mul(one.add(s22)).sub(s12.mul(s21))).div(two_s21)?;
    let c = one.sub(s11).mul(one.sub(s22)).sub(s12.mul(s21)).div(two_s21.mul(z))?;
    let d = one.sub(s11).mul(one.add(s22)).add(s12.mul(s21)).div(two_s21)?;
    Ok([a, b, c, d])
}

pub fn abcd_to_s(m: Abcd, z0: f64) -> PowerResult<[C; 4]> {
    let [a, b, c, d] = m;
    let z = C::real(z0);
    let b_z = b.div(z)?;
    let c_z = c.mul(z);
    let den = a.add(b_z).add(c_z).add(d);
    let s11 = a.add(b_z).sub(c_z).sub(d).div(den)?;
    let s12 = C::real(2.0).mul(a.mul(d).sub(b.mul(c))).div(den)?;
    let s21 = C::real(2.0).div(den)?;
    let s22 = a.neg().add(b_z).sub(c_z).add(d).div(den)?;
    Ok([s11, s12, s21, s22])
}

pub fn cascade(m1: Abcd, m2: Abcd) -> Abcd {
    let [a1, b1, c1, d1] = m1;
    let [a2, b2, c2, d2] = m2;
    [a1.mul(a2).add(b1.mul(c2)), a1.mul(b2).add(b1.mul(d2)), c1.mul(a2).add(d1.mul(c2)), c1.mul(b2).add(d1.mul(d2))]
}

pub fn z_in(m: Abcd, z_load: C) -> PowerResult<C> {
    let [a, b, c, d] = m;
    a.mul(z_load).add(b).div(c.mul(z_load).add(d))
}

pub fn deembed_load(m: Abcd, z_input: C) -> PowerResult<C> {
    let [a, b, c, d] = m;
    let den = a.sub(c.mul(z_input));
    if den.is_zero() {
        return Err(rec_err("de-embedding singular (A - C Z_in = 0)"));
    }
    d.mul(z_input).sub(b).div(den)
}

/// Fraction of the net power entering port 1 that reaches the load `z_load` at port 2.
pub fn transfer_efficiency(m: Abcd, z_load: C) -> PowerResult<f64> {
    let [a, b, c, d] = m;
    let v1 = a.mul(z_load).add(b);
    let i1 = c.mul(z_load).add(d);
    let p1 = v1.mul(i1.conj()).re;
    if p1 <= 0.0 {
        return Err(rec_err("non-positive input power in the two-port efficiency"));
    }
    Ok(z_load.re / p1)
}

/// One-port three-term correction Gamma = (m - e00) / (e10e01 + e11 (m - e00)).
pub fn correct_reflection(m_raw: C, e00: C, e11: C, e10e01: C) -> PowerResult<C> {
    let den = e10e01.add(e11.mul(m_raw.sub(e00)));
    if den.is_zero() {
        return Err(rec_err("reflection correction singular"));
    }
    m_raw.sub(e00).div(den)
}

pub fn fixture_to_plane(m: Abcd, v_p: C, i_p: C) -> PowerResult<(C, C)> {
    let [a, b, c, d] = m;
    let det = a.mul(d).sub(b.mul(c));
    if det.is_zero() {
        return Err(rec_err("fixture ABCD singular"));
    }
    Ok((d.mul(v_p).sub(b.mul(i_p)).div(det)?, c.neg().mul(v_p).add(a.mul(i_p)).div(det)?))
}

fn py_sqrt(x: f64) -> PowerResult<f64> {
    if x < 0.0 {
        return Err(PowerError::new("ValueError", "math domain error"));
    }
    Ok(x.sqrt())
}

/// Peak voltage and current on a Z0 line carrying forward power `p_fwd` with reflection |Gamma|.
pub fn line_peak_stress(p_fwd: f64, gmag: f64, z0: f64) -> PowerResult<(f64, f64)> {
    let v = py_sqrt(2.0 * p_fwd * z0)? * (1.0 + gmag);
    if z0 == 0.0 {
        return Err(PowerError::new("ZeroDivisionError", "float division by zero"));
    }
    let i = py_sqrt(2.0 * p_fwd / z0)? * (1.0 + gmag);
    Ok((v, i))
}

// ================================================================================================ Touchstone v1
const FREQ_UNITS: [(&str, f64); 4] = [("HZ", 1.0), ("KHZ", 1e3), ("MHZ", 1e6), ("GHZ", 1e9)];
const TS_PARAMETERS: [&str; 5] = ["S", "Y", "Z", "H", "G"];
const TS_FORMATS: [&str; 3] = ["RI", "MA", "DB"];

/// `str.splitlines()` of an ASCII text.
fn splitlines(text: &str) -> Vec<&str> {
    let b = text.as_bytes();
    let mut out = Vec::new();
    let (mut start, mut i) = (0, 0);
    while i < b.len() {
        match b[i] {
            b'\n' | b'\x0b' | b'\x0c' | b'\x1c' | b'\x1d' | b'\x1e' => {
                out.push(&text[start..i]);
                i += 1;
                start = i;
            }
            b'\r' => {
                out.push(&text[start..i]);
                i += if i + 1 < b.len() && b[i + 1] == b'\n' { 2 } else { 1 };
                start = i;
            }
            _ => i += 1,
        }
    }
    if start < b.len() {
        out.push(&text[start..]);
    }
    out
}

fn py_split(s: &str) -> Vec<&str> {
    s.split(py_isspace).filter(|t| !t.is_empty()).collect()
}

fn parse_option(tokens: &[&str], allow: bool, ln: usize) -> PowerResult<(Dict, Vec<Value>)> {
    let mut got = Dict::new();
    let mut i = 0;
    while i < tokens.len() {
        let t = tokens[i].to_ascii_uppercase();
        let (key, val) = if FREQ_UNITS.iter().any(|(u, _)| *u == t) {
            ("unit", Value::str(t))
        } else if TS_PARAMETERS.contains(&t.as_str()) {
            ("parameter", Value::str(t))
        } else if TS_FORMATS.contains(&t.as_str()) {
            ("format", Value::str(t))
        } else if t == "R" {
            if i + 1 >= tokens.len() {
                return Err(ts(format!("line {ln}: option 'R' without a value")));
            }
            let Some(v) = py_float_from_str(tokens[i + 1]) else {
                return Err(ts(format!(
                    "line {ln}: reference resistance {} is not a number",
                    py_repr_str(tokens[i + 1])
                )));
            };
            if !v.is_finite() || v <= 0.0 {
                return Err(ts(format!("line {ln}: reference resistance must be a positive number of ohms")));
            }
            i += 1;
            ("R", Value::Float(v))
        } else {
            return Err(ts(format!("line {ln}: unknown option-line token {}", py_repr_str(tokens[i]))));
        };
        if got.contains_key(key) {
            return Err(ts(format!("line {ln}: option '{key}' given twice")));
        }
        got.insert(key, val);
        i += 1;
    }
    let mut defaults = Vec::new();
    for (k, d, dr) in [
        ("unit", Value::str("GHZ"), "'GHZ'"),
        ("parameter", Value::str("S"), "'S'"),
        ("format", Value::str("MA"), "'MA'"),
        ("R", Value::Float(50.0), "50.0"),
    ] {
        if !got.contains_key(k) {
            if !allow {
                return Err(ts(format!(
                    "line {ln}: option-line field '{k}' not stated; the Touchstone 1.1 default ({dr}) is not applied \
                     silently (pass allow_spec_defaults=True to apply and record it)"
                )));
            }
            got.insert(k, d);
            defaults.push(Value::str(k));
        }
    }
    Ok((got, defaults))
}

fn pair(a: f64, b: f64, fmt: &str) -> PowerResult<C> {
    match fmt {
        "RI" => Ok(C::new(a, b)),
        "MA" => {
            if a < 0.0 {
                return Err(ts(format!("negative magnitude {} in MA format", float_repr(a))));
            }
            Ok(rect(a, radians(b)))
        }
        _ => Ok(rect(libm_pow(10.0, a / 20.0), radians(b))),
    }
}

/// `parse_touchstone(text, n_ports, allow_spec_defaults, source)` of a 1- or 2-port S-parameter file.
pub fn parse_touchstone(
    text: &Value,
    n_ports: &Value,
    allow_spec_defaults: &Value,
    source: &Value,
) -> PowerResult<Value> {
    let one = py_eq(n_ports, &Value::int(1));
    let two = py_eq(n_ports, &Value::int(2));
    if !(one || two) {
        return Err(ts("only 1-port (.s1p) and 2-port (.s2p) files are supported".into()));
    }
    let Value::Str(text) = text else {
        return Err(ts("text must be a string".into()));
    };
    if !text.is_ascii() {
        return Err(ts("non-ASCII content (Touchstone 1.1 general rule 2)".into()));
    }
    let allow = allow_spec_defaults.truthy();
    let per_line = if one { 3 } else { 9 };
    let names: &[&str] = if one { &["S11"] } else { &["S11", "S21", "S12", "S22"] };
    let mut option: Option<Dict> = None;
    let mut defaults = Vec::new();
    let mut ignored = 0_i64;
    let mut points = Vec::new();
    let mut noise = Vec::new();
    let mut last_f: Option<f64> = None;
    let mut in_noise = false;
    for (idx, raw) in splitlines(text).into_iter().enumerate() {
        let ln = idx + 1;
        let body = abep_types::pyjson::py_strip(raw.split('!').next().unwrap_or(""));
        if body.is_empty() {
            continue;
        }
        if let Some(rest) = body.strip_prefix('#') {
            if option.is_none() {
                let (o, d) = parse_option(&py_split(rest), allow, ln)?;
                option = Some(o);
                defaults = d;
            } else {
                ignored += 1;
            }
            continue;
        }
        let Some(opt) = &option else {
            return Err(ts(format!("line {ln}: data before the option line (it must be the first non-comment line)")));
        };
        let toks = py_split(body);
        let mut vals = Vec::with_capacity(toks.len());
        for t in &toks {
            match py_float_from_str(t) {
                Some(v) => vals.push(v),
                None => return Err(ts(format!("line {ln}: non-numeric data {}", py_repr_str(body)))),
            }
        }
        if !vals.iter().all(|v| v.is_finite()) {
            return Err(ts(format!("line {ln}: non-finite value")));
        }
        let unit = opt.get("unit").and_then(Value::as_str).unwrap_or("HZ");
        let mult = FREQ_UNITS.iter().find(|(u, _)| *u == unit).map_or(1.0, |(_, m)| *m);
        let f_hz = vals[0] * mult;
        if two && vals.len() == 5 && !points.is_empty() && (in_noise || last_f.is_some_and(|l| f_hz <= l)) {
            in_noise = true;
            let mut d = Dict::new();
            d.insert("f_Hz", Value::Float(f_hz));
            d.insert("NFmin_dB", Value::Float(vals[1]));
            d.insert("gamma_opt_mag", Value::Float(vals[2]));
            d.insert("gamma_opt_deg", Value::Float(vals[3]));
            d.insert("rn_normalized", Value::Float(vals[4]));
            noise.push(Value::Dict(d));
            continue;
        }
        if in_noise {
            return Err(ts(format!("line {ln}: network data after the noise block")));
        }
        if vals.len() != per_line {
            return Err(ts(format!(
                "line {ln}: {} values, expected {per_line} for a {}-port data line",
                vals.len(),
                py_str(n_ports)
            )));
        }
        if last_f.is_some_and(|l| py_not_gt(f_hz, l)) {
            return Err(ts(format!("line {ln}: frequencies must increase (spec p. 6 rule 4)")));
        }
        last_f = Some(f_hz);
        if matches!(n_ports, Value::Float(_)) {
            return Err(PowerError::new("TypeError", "'float' object cannot be interpreted as an integer"));
        }
        let fmt = opt.get("format").and_then(Value::as_str).unwrap_or("MA");
        let mut pt = Dict::new();
        pt.insert("f_Hz", Value::Float(f_hz));
        for (k, name) in names.iter().enumerate() {
            pt.insert(*name, cval(pair(vals[1 + 2 * k], vals[2 + 2 * k], fmt)?));
        }
        points.push(Value::Dict(pt));
    }
    let Some(option) = option else {
        return Err(ts("no option line".into()));
    };
    let parameter = option.get("parameter").cloned().unwrap_or(Value::Null);
    if parameter.as_str() != Some("S") {
        return Err(ts(format!("parameter {}: this framework ingests S-parameters only", py_repr(&parameter))));
    }
    if points.is_empty() {
        return Err(ts("no network data".into()));
    }
    let mut out = Dict::new();
    out.insert("n_ports", n_ports.clone());
    let z0 = option.get("R").cloned().unwrap_or(Value::Null);
    out.insert("option", Value::Dict(option));
    out.insert("defaults_applied", Value::List(defaults));
    out.insert("Z0_ohm", z0);
    out.insert("points", Value::List(points));
    out.insert("noise", Value::List(noise));
    out.insert("ignored_option_lines", Value::int(ignored));
    out.insert("source", source.clone());
    Ok(Value::Dict(out))
}

// ================================================================================================ one-port SOL
fn solve3(a: [[C; 3]; 3], b: [C; 3]) -> PowerResult<[C; 3]> {
    let mut m = [[C::real(0.0); 4]; 3];
    for i in 0..3 {
        m[i][..3].copy_from_slice(&a[i]);
        m[i][3] = b[i];
    }
    let mut scale = f64::NEG_INFINITY;
    for row in &a {
        for x in row {
            let v = x.abs();
            if v > scale {
                scale = v;
            }
        }
    }
    if scale == 0.0 {
        scale = 1.0;
    }
    for c in 0..3 {
        let mut piv = c;
        for r in c..3 {
            if m[r][c].abs() > m[piv][c].abs() {
                piv = r;
            }
        }
        if m[piv][c].abs() <= 1e-12 * scale {
            return Err(PowerError::new(
                "CalibrationSolveError",
                "calibration standards are not distinct enough (singular normal equations)",
            ));
        }
        m.swap(c, piv);
        let pivot_row = m[c];
        for row in m.iter_mut().skip(c + 1) {
            let f = row[c].div(pivot_row[c])?;
            for (x, p) in row.iter_mut().zip(pivot_row.iter()).skip(c) {
                *x = x.sub(f.mul(*p));
            }
        }
    }
    let mut x = [C::real(0.0); 3];
    for c in [2usize, 1, 0] {
        let s = sum(((c + 1)..3).map(|k| m[c][k].mul(x[k])));
        x[c] = m[c][3].sub(s).div(m[c][c])?;
    }
    Ok(x)
}

fn std_field<'a>(s: &'a Dict, k: &str) -> Option<&'a Value> {
    s.get(k).filter(|v| !matches!(v, Value::Null) && !matches!(v, Value::Str(x) if x.is_empty()))
}

/// `sol_error_terms(standards)`: three-term one-port error model from >= 3 known standards (least squares).
pub fn sol_error_terms(standards: &Value) -> PowerResult<Value> {
    let err = |m: String| PowerError::new("CalibrationSolveError", m);
    let list = match standards {
        Value::List(l) if l.len() >= 3 => l,
        _ => return Err(err("at least three known standards are required (three complex unknowns)".into())),
    };
    let mut rows = Vec::new();
    let mut v = Vec::new();
    for s in list {
        let Value::Dict(d) = s else {
            return Err(PowerError::new(
                "AttributeError",
                format!("'{}' object has no attribute 'get'", s.type_name()),
            ));
        };
        for k in ["id", "gamma_actual", "gamma_measured", "definition_source"] {
            if std_field(d, k).is_none() {
                let id = d.get("id").map_or("None".to_string(), py_repr);
                return Err(err(format!("standard {id} lacks {k}")));
            }
        }
        let id = py_str(d.get("id").unwrap());
        let ga = cxv(d.get("gamma_actual").unwrap(), &format!("{id}.gamma_actual"))?;
        let gm = cxv(d.get("gamma_measured").unwrap(), &format!("{id}.gamma_measured"))?;
        rows.push([ga, C::real(1.0), ga.mul(gm)]);
        v.push(gm);
    }
    let mut a = [[C::real(0.0); 3]; 3];
    let mut b = [C::real(0.0); 3];
    for r in 0..3 {
        for c in 0..3 {
            a[r][c] = sum(rows.iter().map(|row| row[r].conj().mul(row[c])));
        }
        b[r] = sum(rows.iter().zip(&v).map(|(row, vi)| row[r].conj().mul(*vi)));
    }
    let [e1, e2, e3] = solve3(a, b)?;
    let (e00, e11, e10e01) = (e2, e3, e1.add(e2.mul(e3)));
    if e10e01.is_zero() {
        return Err(err("reflection tracking e10e01 = 0".into()));
    }
    let mut resid = Dict::new();
    for s in list {
        let d = s.as_dict().unwrap();
        let ga = cxv(d.get("gamma_actual").unwrap(), "ga")?;
        let gm = cxv(d.get("gamma_measured").unwrap(), "gm")?;
        let model = e00.add(e10e01.mul(ga).div(C::real(1.0).sub(e11.mul(ga)))?).sub(gm);
        let key = match d.get("id").unwrap() {
            Value::Str(k) => k.clone(),
            other => py_str(other),
        };
        resid.insert(key, Value::Float(round_sig(model.abs(), 9)));
    }
    let mut out = Dict::new();
    out.insert("e00", cval(e00));
    out.insert("e11", cval(e11));
    out.insert("e10e01", cval(e10e01));
    out.insert("residual_abs", Value::Dict(resid));
    out.insert("n_standards", Value::int(list.len() as i64));
    out.insert(
        "solution",
        Value::str(if list.len() > 3 { "least squares (exact for 3 standards)" } else { "exact (3 standards)" }),
    );
    Ok(Value::Dict(out))
}

/// `sol_correct(gamma_measured, terms)`.
pub fn sol_correct(gamma_measured: C, e00: C, e11: C, e10e01: C) -> PowerResult<C> {
    correct_reflection(gamma_measured, e00, e11, e10e01)
}

// ================================================================================================ match / probe
/// `ladder_abcd(elements)`: ABCD of a declared series / shunt ladder (generator side first).
pub fn ladder_abcd(elements: &Value) -> PowerResult<Abcd> {
    let key_err = |k: &str| PowerError::new("KeyError", format!("'{k}'"));
    let mut m: Abcd = [C::real(1.0), C::real(0.0), C::real(0.0), C::real(1.0)];
    for el in elements.as_list().unwrap_or(&[]) {
        let d = el.as_dict().ok_or_else(|| PowerError::new("TypeError", "element is not a record"))?;
        let zv = d.get("Z_ohm").ok_or_else(|| key_err("Z_ohm"))?;
        let id = d.get("id").ok_or_else(|| key_err("id"))?;
        let z = cxv(zv, &py_str(id))?;
        let kind = d.get("kind").ok_or_else(|| key_err("kind"))?;
        let step = if kind.as_str() == Some("series") {
            [C::real(1.0), z, C::real(0.0), C::real(1.0)]
        } else {
            [C::real(1.0), C::real(0.0), C::real(1.0).div(z)?, C::real(1.0)]
        };
        m = cascade(m, step);
    }
    Ok(m)
}

/// Fraction of the power incident on port 1 dissipated in a two-port terminated in Z0: 1 - |S11|^2 - |S21|^2.
pub fn dissipated_fraction_matched(s11: C, s21: C) -> PowerResult<f64> {
    let f = 1.0 - libm_pow(s11.abs(), 2.0) - libm_pow(s21.abs(), 2.0);
    if f < -1e-12 {
        return Err(PowerError::new("FrameworkError", "active or inconsistent two-port (1 - |S11|^2 - |S21|^2 < 0)"));
    }
    Ok(if 0.0 > f { 0.0 } else { f })
}

/// `vi_power_and_impedance(V_raw, I_raw, k_V, k_I, amplitude_convention)`: probe impedance and power.
pub fn vi_power_and_impedance(
    v_raw: &Value,
    i_raw: &Value,
    k_v: &Value,
    k_i: &Value,
    convention: &Value,
) -> PowerResult<Value> {
    let v = cxv(k_v, "k_V")?.mul(cxv(v_raw, "V_raw")?);
    let i = cxv(k_i, "k_I")?.mul(cxv(i_raw, "I_raw")?);
    if i.is_zero() {
        return Err(PowerError::new("FrameworkError", "zero current"));
    }
    let c = if py_eq(convention, &Value::str("peak")) { 0.5 } else { 1.0 };
    let mut d = Dict::new();
    d.insert("Z_ohm", cval(v.div(i)?));
    d.insert("P_W", Value::Float(c * v.mul(i.conj()).re));
    Ok(Value::Dict(d))
}

/// `p_bus_from_generator_input(record)`: always refused; a generator input (P_mains,in) is never P_bus (A9.3
/// OQ-RFQ-06; A9-02 A902-19).
pub fn p_bus_from_generator_input(record: &Value) -> PowerError {
    let attr =
        |v: &Value| PowerError::new("AttributeError", format!("'{}' object has no attribute 'get'", v.type_name()));
    let rec = if record.truthy() { record.clone() } else { Value::Dict(Dict::new()) };
    let Value::Dict(r) = &rec else {
        return attr(&rec);
    };
    let gen = r.get("generator").filter(|g| g.truthy()).cloned().unwrap_or(Value::Dict(Dict::new()));
    let Value::Dict(g) = &gen else {
        return attr(&gen);
    };
    let class = g.get("generator_class").cloned().unwrap_or(Value::Null);
    PowerError::new(
        "PMainsNotPBusError",
        format!(
            "refused: generator input (class {}) is not P_bus. P_bus is all electrical power crossing the \
             spacecraft-side DC boundary (A9-02); the P1 laboratory generator is GROUND/FACILITY_ONLY and its \
             P_mains,in is an engineering quantity only",
            py_repr(&class)
        ),
    )
}

// ================================================================================================ impedance-map gate
/// One registered P2 impedance-map point: the characterized match-state two-port and the measured load impedance.
#[derive(Debug, Clone, PartialEq)]
pub struct ImpedanceMapPoint {
    pub abcd: Abcd,
    pub z_load_ohm: C,
    pub evidence_class: String,
    pub source: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RfChainStatus {
    pub status: EvalStatus,
    pub transfer_efficiency: Option<f64>,
    pub reason: String,
}

/// Matched RF chain transfer at a registered measured impedance-map point; without one it is NOT_EVALUATED
/// (TBD_AFTER_IMPEDANCE_MAP, A9.2). No default network, impedance or efficiency exists.
pub fn rf_chain_status(point: Option<&ImpedanceMapPoint>) -> RfChainStatus {
    let Some(p) = point else {
        return RfChainStatus {
            status: EvalStatus::NotEvaluated,
            transfer_efficiency: None,
            reason: "TBD_AFTER_IMPEDANCE_MAP (A9.2 binding status): no measured P2 impedance-map point is registered"
                .into(),
        };
    };
    if p.evidence_class != "measured" {
        return RfChainStatus {
            status: EvalStatus::IncompleteEvidence,
            transfer_efficiency: None,
            reason: format!(
                "impedance-map point of class {:?} is not measured evidence ({})",
                p.evidence_class, p.source
            ),
        };
    }
    match transfer_efficiency(p.abcd, p.z_load_ohm) {
        Ok(eta) => {
            RfChainStatus { status: EvalStatus::Evaluated, transfer_efficiency: Some(eta), reason: p.source.clone() }
        }
        Err(e) => RfChainStatus { status: EvalStatus::ModelError, transfer_efficiency: None, reason: e.message },
    }
}

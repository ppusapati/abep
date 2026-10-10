//! Cited physical sputter-yield formulas of the species-resolved register (reference
//! `docs/evidence/sputter_yields_v1/build_sputter_yields_v1.py`, contract
//! `docs/rust_migration/contracts/C-DOCS_EVIDENCE_SPUTTER_YIELDS_V1-YIELD_KERNELS/parity_prereg_v1.json`).
//!
//! * [`yamamura_tawara`]: NIFS-DATA-23 Eqs. (4), (15)-(22) (report pp. 3, 7-8). The alpha* 0.249 branch is used for
//!   M1 <= M2, as the paper's worked example and Fig. 1 do (the printed Eq. (17) labels are inverted relative to that
//!   use; register inputs nifs_formula_reading.alpha_branch_note).
//! * [`apid_fit`]: IAEA APID 7B report p. 18 (PDF p. 20) fit formula; the bracket multiplies only the threshold term.
//!
//! Arguments are JSON numbers as the reference receives them (bool counts as int; ints stay exact).

use super::pymath::{self, Num};
use abep_types::pyjson::{py_repr, Dict, PyResult, Value};

fn positive(fname: &str, name: &str, v: &Value) -> PyResult<f64> {
    let ok = match v {
        Value::Bool(b) => *b,
        Value::Int(i) => {
            // math.isfinite(int) converts to float first.
            i.to_f64()?;
            !i.is_negative() && !i.is_zero()
        }
        Value::Float(x) => x.is_finite() && *x > 0.0,
        _ => false,
    };
    if !ok {
        return Err(pymath::err(
            "ValueError",
            format!("{fname}: {name} must be a positive finite number, got {}", py_repr(v)),
        ));
    }
    Ok(Num::from_value(v, name)?.f())
}

/// Yamamura-Tawara yield [atoms / ion] and threshold [eV] of projectile (Z1, M1) on target (Z2, M2) at energy E [eV];
/// surface binding energy Us [eV], Q, W and s are the target's Table 1 / caption fit parameters.
#[allow(clippy::too_many_arguments)]
pub fn yamamura_tawara(
    e: &Value,
    z1: &Value,
    m1: &Value,
    z2: &Value,
    m2: &Value,
    us: &Value,
    q: &Value,
    w: &Value,
    s: &Value,
) -> PyResult<Value> {
    let f = "yamamura_tawara";
    let e = positive(f, "E", e)?;
    let m1 = positive(f, "M1", m1)?;
    let m2 = positive(f, "M2", m2)?;
    let us = positive(f, "Us", us)?;
    let q = positive(f, "Q", q)?;
    let w = positive(f, "W", w)?;
    let s = positive(f, "s", s)?;
    let z1 = Num::from_value(z1, "Z1")?.f();
    let z2 = Num::from_value(z2, "Z2")?.f();
    let p = pymath::pow;
    let zz = p(z1, 2.0 / 3.0)? + p(z2, 2.0 / 3.0)?;
    let eps = pymath::fdiv(0.03255, z1 * z2 * p(zz, 0.5)?)? * m2 / (m1 + m2) * e; // Eq. (22)
    let se = pymath::sqrt(eps)?;
    // 2.718 is the constant printed in Eq. (4), not e.
    #[allow(clippy::approx_constant)]
    let sn_tf = pymath::fdiv(3.441 * se * pymath::log(eps + 2.718)?, 1.0 + 6.355 * se + eps * (6.882 * se - 1.708))?; // Eq. (4)
    let ke = pymath::fdiv(
        pymath::fdiv(0.079 * p(m1 + m2, 1.5)?, p(m1, 1.5)? * p(m2, 0.5)?)? * p(z1, 2.0 / 3.0)? * p(z2, 0.5)?,
        p(zz, 0.75)?,
    )?; // Eq. (20)
    let sn = pymath::fdiv(pymath::fdiv(84.78 * z1 * z2, p(zz, 0.5)?)? * m1, m1 + m2)? * sn_tf; // Eq. (21)
    let r = pymath::fdiv(m2, m1)?;
    let alpha = if m1 <= m2 { 0.249 * p(r, 0.56)? + 0.0035 * p(r, 1.5)? } else { 0.088 * p(r, -0.15)? + 0.165 * r }; // Eq. (17)
    let gamma = pymath::fdiv(4.0 * m1 * m2, p(m1 + m2, 2.0)?)?; // Eq. (19)
    let eth = (if m1 >= m2 { pymath::fdiv(6.7, gamma)? } else { pymath::fdiv(1.0 + 5.7 * m1 / m2, gamma)? }) * us; // Eq. (18)
    let big_gamma = pymath::fdiv(w, 1.0 + p(m1 / 7.0, 3.0)?)?; // Eq. (16)
    let mut d = Dict::new();
    if e <= eth {
        d.insert("Y", Value::Float(0.0));
        d.insert("Eth_eV", Value::Float(eth));
        d.insert("below_threshold", Value::Bool(true));
        return Ok(Value::Dict(d));
    }
    let y = pymath::fdiv(pymath::fdiv(0.042 * q * alpha, us)? * sn, 1.0 + big_gamma * ke * p(eps, 0.3)?)?
        * p(1.0 - pymath::sqrt(pymath::fdiv(eth, e)?)?, s)?; // Eq. (15)
    d.insert("Y", Value::Float(y));
    d.insert("Eth_eV", Value::Float(eth));
    d.insert("below_threshold", Value::Bool(false));
    Ok(Value::Dict(d))
}

/// APID fit yield: Y = 0.5 q x ln(1 + 1.2288 eps) / (lambda + x [eps + 0.1728 sqrt(eps) + 0.008 eps^0.1504]),
/// x = (E / Eth - 1)^mu, eps = E eps_L; 0.0 at or below Eth.
pub fn apid_fit(e: &Value, lam: &Value, q: &Value, mu: &Value, eps_l: &Value, eth: &Value) -> PyResult<f64> {
    let f = "apid_fit";
    let e_n = positive(f, "E", e)?;
    let lam = positive(f, "lambda", lam)?;
    let q = positive(f, "q", q)?;
    let mu = positive(f, "mu", mu)?;
    let eps_l = positive(f, "eps_L", eps_l)?;
    let eth_n = positive(f, "Eth", eth)?;
    if e_n <= eth_n {
        return Ok(0.0);
    }
    let ratio = Num::true_div(Num::from_value(e, "E")?, Num::from_value(eth, "Eth")?)?;
    let x = pymath::pow(ratio - 1.0, mu)?;
    let ee = e_n * eps_l;
    let w = ee + 0.1728 * pymath::sqrt(ee)? + 0.008 * pymath::pow(ee, 0.1504)?;
    pymath::fdiv(0.5 * q * x * pymath::log(1.0 + 1.2288 * ee)?, lam + x * w)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn worked_example_and_threshold_branch() {
        // NIFS-DATA-23 worked example He -> Au at 1 keV (register test: Y ~ 0.140, Eth ~ 54 eV, 2 %).
        let v = |x: f64| Value::Float(x);
        let r = yamamura_tawara(
            &v(1000.0),
            &Value::int(2),
            &v(4.0026),
            &Value::int(79),
            &v(196.97),
            &v(3.81),
            &v(1.08),
            &v(1.64),
            &v(2.8),
        )
        .unwrap();
        let d = r.as_dict().unwrap();
        let y = match d.get("Y").unwrap() {
            Value::Float(x) => *x,
            _ => panic!(),
        };
        assert!((y / 0.140 - 1.0).abs() < 0.02);
        let bad = yamamura_tawara(
            &v(100.0),
            &Value::int(7),
            &v(14.007),
            &Value::int(74),
            &v(183.84),
            &v(0.0),
            &v(0.72),
            &v(2.14),
            &v(2.8),
        );
        assert_eq!(bad.unwrap_err().message, "yamamura_tawara: Us must be a positive finite number, got 0.0");
        assert_eq!(apid_fit(&v(40.0), &v(0.016), &v(4.9), &v(1.8), &v(8.8e-7), &v(46.7)).unwrap(), 0.0);
    }
}

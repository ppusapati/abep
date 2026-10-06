//! P_bus,1ms,max from a sampled spacecraft-side bus-power record (`p_bus_1ms_max` of
//! `abep_sim/bus_boundary_a9_v2.py`; A9.1 OQ-A902-01 engineering definition): the maximum of the 1 ms moving mean,
//! with the unaveraged sampled peak and the 100 ms / 1 s maximum means as diagnostics only. Pure arithmetic on the
//! caller's record; the record is refused unless it meets the frozen measurement requirements. No limit is applied.

use super::pyfmt::real;
use super::slots::{
    DIAGNOSTIC_WINDOWS_S, GATE_MIN_BANDWIDTH_HZ, GATE_MIN_SAMPLE_RATE_SA_S, GATE_WINDOW_S, P1MS_DEFINITION,
};
use super::{PowerError, PowerResult};
use abep_types::pyjson::{float_repr, Dict, PyInt, Value};

/// Result of [`p_bus_1ms_max`].
#[derive(Debug, Clone, PartialEq)]
pub struct P1msResult {
    pub p_bus_1ms_max_w: Option<f64>,
    /// Samples per 1 ms window (an exact integer; its decimal digits as Python prints them).
    pub window_samples: String,
    pub record_duration_s: f64,
    pub unaveraged_sampled_peak_w: f64,
    pub max_mean_100ms_w: Option<f64>,
    pub max_mean_1s_w: Option<f64>,
    pub sample_rate_sa_s: f64,
    pub bandwidth_hz: f64,
}

impl P1msResult {
    pub fn to_value(&self) -> Value {
        let o = |x: Option<f64>| x.map_or(Value::Null, Value::Float);
        let mut diag = Dict::new();
        diag.insert("unaveraged_sampled_peak_W", Value::Float(self.unaveraged_sampled_peak_w));
        diag.insert("max_mean_100ms_W", o(self.max_mean_100ms_w));
        diag.insert("max_mean_1s_W", o(self.max_mean_1s_w));
        let mut gm = Dict::new();
        gm.insert("sample_rate_Sa_s", Value::Float(self.sample_rate_sa_s));
        gm.insert("bandwidth_Hz", Value::Float(self.bandwidth_hz));
        gm.insert("anti_alias_documented", Value::Bool(true));
        gm.insert("synchronized", Value::Bool(true));
        let mut d = Dict::new();
        d.insert("P_bus_1ms_max_W", o(self.p_bus_1ms_max_w));
        d.insert("window_samples", Value::Int(PyInt::parse(&self.window_samples).expect("integer digits")));
        d.insert("record_duration_s", Value::Float(self.record_duration_s));
        d.insert("diagnostics_only", Value::Dict(diag));
        d.insert("power_basis", Value::str("p_bus_1ms_max"));
        d.insert("definition", Value::str(P1MS_DEFINITION));
        d.insert("gate_measurement", Value::Dict(gm));
        Value::Dict(d)
    }
}

/// `str(window_s)` of the registered windows (Python float str).
fn window_text(w: f64) -> String {
    float_repr(w)
}

/// Samples per window: `k = int(round(window_s * fs))`, refused unless within 1e-9 of an integer. Returned as f64
/// (exact integer) to stay exact for any sample rate.
fn samples_per_window(window_s: f64, fs: f64) -> PowerResult<f64> {
    let n = window_s * fs;
    let k = n.round_ties_even();
    if (n - k).abs() > 1e-9 * n.max(1.0) {
        return Err(PowerError::boundary(format!(
            "sample rate {} Sa/s gives a non-integer number of samples per {} s",
            float_repr(fs),
            window_text(window_s)
        )));
    }
    Ok(k)
}

/// Maximum of the moving mean over `k` samples, from the running sum in sample order (as the reference).
fn max_mean(xs: &[f64], k: f64) -> Option<f64> {
    if k < 1.0 || (xs.len() as f64) < k {
        return None;
    }
    let k = k as usize;
    let mut csum = Vec::with_capacity(xs.len() + 1);
    csum.push(0.0_f64);
    for x in xs {
        let last = *csum.last().unwrap();
        csum.push(last + x);
    }
    let kf = k as f64;
    let mut best: Option<f64> = None;
    for i in 0..=(xs.len() - k) {
        let m = (csum[i + k] - csum[i]) / kf;
        if best.is_none_or(|b| m > b) {
            best = Some(m);
        }
    }
    best
}

/// `p_bus_1ms_max(samples_W, sample_rate_Sa_s, bandwidth_Hz, anti_alias_documented, synchronized)` on JSON values.
pub fn p_bus_1ms_max(
    samples_w: &Value,
    sample_rate_sa_s: &Value,
    bandwidth_hz: &Value,
    anti_alias_documented: &Value,
    synchronized: &Value,
) -> PowerResult<P1msResult> {
    let fs = real(sample_rate_sa_s, "sample_rate_Sa_s", "BoundaryA9Error")?;
    let bw = real(bandwidth_hz, "bandwidth_Hz", "BoundaryA9Error")?;
    if fs < GATE_MIN_SAMPLE_RATE_SA_S {
        return Err(PowerError::boundary(format!(
            "sample rate {} Sa/s < {} (A9.1 OQ-A902-01)",
            float_repr(fs),
            float_repr(GATE_MIN_SAMPLE_RATE_SA_S)
        )));
    }
    if bw < GATE_MIN_BANDWIDTH_HZ {
        return Err(PowerError::boundary(format!(
            "effective bandwidth {} Hz < {} (A9.1 OQ-A902-01)",
            float_repr(bw),
            float_repr(GATE_MIN_BANDWIDTH_HZ)
        )));
    }
    if *anti_alias_documented != Value::Bool(true) || *synchronized != Value::Bool(true) {
        return Err(PowerError::boundary(
            "anti-alias filtering must be documented and all channels synchronized (A9.1 OQ-A902-01)",
        ));
    }
    let Value::List(raw) = samples_w else {
        return Err(PowerError::boundary("samples_W must be a sequence of bus-power samples in W"));
    };
    let xs = raw.iter().map(|x| real(x, "bus-power sample", "BoundaryA9Error")).collect::<PowerResult<Vec<f64>>>()?;
    let n1 = samples_per_window(GATE_WINDOW_S, fs)?;
    if (xs.len() as f64) < n1 {
        return Err(PowerError::boundary(format!(
            "record shorter than the 1 ms gate window ({} < {:.0} samples)",
            xs.len(),
            n1
        )));
    }
    let p1 = max_mean(&xs, n1);
    let peak = xs.iter().copied().fold(f64::NEG_INFINITY, |a, b| if b > a { b } else { a });
    let m100 = max_mean(&xs, samples_per_window(DIAGNOSTIC_WINDOWS_S[0], fs)?);
    let m1s = max_mean(&xs, samples_per_window(DIAGNOSTIC_WINDOWS_S[1], fs)?);
    Ok(P1msResult {
        p_bus_1ms_max_w: p1,
        window_samples: format!("{n1:.0}"),
        record_duration_s: xs.len() as f64 / fs,
        unaveraged_sampled_peak_w: peak,
        max_mean_100ms_w: m100,
        max_mean_1s_w: m1s,
        sample_rate_sa_s: fs,
        bandwidth_hz: bw,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(xs: &[f64]) -> Value {
        Value::List(xs.iter().map(|x| Value::Float(*x)).collect())
    }

    #[test]
    fn one_ms_max_of_a_step() {
        let mut xs = vec![100.0; 300];
        for x in xs.iter_mut().skip(100).take(100) {
            *x = 1200.0;
        }
        let r =
            p_bus_1ms_max(&rec(&xs), &Value::Float(1e5), &Value::Float(2e4), &Value::Bool(true), &Value::Bool(true))
                .unwrap();
        assert_eq!(r.p_bus_1ms_max_w, Some(1200.0));
        assert_eq!(r.window_samples, "100");
        assert_eq!(r.max_mean_100ms_w, None);
        assert_eq!(r.unaveraged_sampled_peak_w, 1200.0);
    }

    #[test]
    fn non_conformant_records_are_refused() {
        let xs = rec(&[1.0; 200]);
        let t = Value::Bool(true);
        assert!(p_bus_1ms_max(&xs, &Value::Float(99999.0), &Value::Float(2e4), &t, &t).is_err());
        assert!(p_bus_1ms_max(&xs, &Value::Float(1e5), &Value::Float(2e4), &Value::Bool(false), &t).is_err());
        let e = p_bus_1ms_max(&rec(&[1.0; 99]), &Value::Float(1e5), &Value::Float(2e4), &t, &t).unwrap_err();
        assert_eq!(e.message, "record shorter than the 1 ms gate window (99 < 100 samples)");
    }
}

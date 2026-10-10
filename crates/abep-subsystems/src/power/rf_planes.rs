//! RF power planes of the ICP source (`rf_power_planes` of `abep_sim/bus_boundary_a9_v2.py`; row 72; A9.2
//! rf_measurement_reference). Only the generator DC input crosses the bus boundary; forward, reflected and delivered
//! RF power are measurement quantities and never a bus load. `P_forward = P_plasma` is never assumed.

use super::pyfmt::real;
use super::slots::TBD;
use super::{PowerError, PowerResult};
use abep_types::pyjson::{Dict, Value};

pub const COUPLER_PLANE: &str = "generator / 50-ohm side of the local matching network (A9.2 OQ-A907-11, \
rf_measurement_reference); P_forward = P_plasma is never assumed";

/// Result of [`rf_power_planes`].
#[derive(Debug, Clone, PartialEq)]
pub struct RfPlanes {
    pub bus_crossing_w: f64,
    pub forward_w: f64,
    pub reflected_w: f64,
    pub net_forward_w: f64,
    pub delivered_w: Option<f64>,
    pub generator_dc_to_forward: Option<f64>,
    pub reflection_fraction: Option<f64>,
    pub gamma_magnitude: Option<f64>,
    pub vswr: Option<f64>,
    pub match_and_line_loss_w: Option<f64>,
}

impl RfPlanes {
    pub fn to_value(&self) -> Value {
        let o = |x: Option<f64>| x.map_or(Value::Null, Value::Float);
        let mut m = Dict::new();
        m.insert("forward_W", Value::Float(self.forward_w));
        m.insert("reflected_W", Value::Float(self.reflected_w));
        m.insert("net_forward_W", Value::Float(self.net_forward_w));
        m.insert("delivered_W", o(self.delivered_w));
        m.insert("coupler_plane", Value::str(COUPLER_PLANE));
        let mut d = Dict::new();
        d.insert("generator_dc_to_forward", o(self.generator_dc_to_forward));
        d.insert("reflection_fraction", o(self.reflection_fraction));
        d.insert("gamma_magnitude", o(self.gamma_magnitude));
        d.insert("vswr", o(self.vswr));
        d.insert("match_and_line_loss_W", o(self.match_and_line_loss_w));
        let mut out = Dict::new();
        out.insert("bus_crossing_W", Value::Float(self.bus_crossing_w));
        out.insert("bus_crossing_plane", Value::str("generator_dc_input"));
        out.insert("measurement_only", Value::Dict(m));
        out.insert("derived", Value::Dict(d));
        Value::Dict(out)
    }
}

/// `rf_power_planes(P_dc_in_W, P_forward_W, P_reflected_W, P_delivered_W, u_W)` on JSON values. `u_W` is the
/// caller's explicit measurement tolerance used only to refuse physically impossible orderings.
pub fn rf_power_planes(
    p_dc_in_w: &Value,
    p_forward_w: &Value,
    p_reflected_w: &Value,
    p_delivered_w: &Value,
    u_w: &Value,
) -> PowerResult<RfPlanes> {
    let b = "BoundaryA9Error";
    let u = real(u_w, "u_W", b)?;
    if u < 0.0 {
        return Err(PowerError::boundary("u_W must be >= 0"));
    }
    let dc = real(p_dc_in_w, "P_dc_in_W", b)?;
    let fw = real(p_forward_w, "P_forward_W", b)?;
    let rf = real(p_reflected_w, "P_reflected_W", b)?;
    for (n, x) in [("P_dc_in_W", dc), ("P_forward_W", fw), ("P_reflected_W", rf)] {
        if x < 0.0 {
            return Err(PowerError::boundary(format!("{n} must be >= 0")));
        }
    }
    if rf > fw + u {
        return Err(PowerError::boundary("reflected power exceeds forward power beyond the stated tolerance"));
    }
    if fw > dc + u {
        return Err(PowerError::boundary(
            "forward RF power exceeds the generator DC input beyond the stated tolerance",
        ));
    }
    let net = fw - rf;
    let dl = match p_delivered_w {
        Value::Str(s) => {
            if s != TBD {
                return Err(PowerError::boundary("P_delivered_W string must be exactly 'TBD'"));
            }
            None
        }
        other => {
            let dl = real(other, "P_delivered_W", b)?;
            if dl < 0.0 || dl > net + u {
                return Err(PowerError::boundary(
                    "delivered power must be in [0, forward - reflected] within the stated tolerance",
                ));
            }
            Some(dl)
        }
    };
    let gam = if fw > 0.0 {
        let g = (rf / fw).sqrt();
        Some(if g < 1.0 { g } else { 1.0 })
    } else {
        None
    };
    let vswr = gam.map(|g| if g >= 1.0 { f64::INFINITY } else { (1.0 + g) / (1.0 - g) });
    Ok(RfPlanes {
        bus_crossing_w: dc,
        forward_w: fw,
        reflected_w: rf,
        net_forward_w: net,
        delivered_w: dl,
        generator_dc_to_forward: (dc > 0.0).then(|| fw / dc),
        reflection_fraction: (fw > 0.0).then(|| rf / fw),
        gamma_magnitude: gam,
        vswr,
        match_and_line_loss_w: dl.map(|d| net - d),
    })
}

//! RF coupling (prereg sec. 5): EQ-12 chain relations, EQ-13 calibrated coupling from a registered P2 point, the
//! CM-PRED gate, and the EQ-15 bus-plane conversion. No coupling efficiency, impedance or generator efficiency is ever
//! assumed (EX-08): every number comes from a registered record or the status says why it is absent.

use crate::case::{BusRegistration, PlaneConvention, VariantSlot};
use crate::status::{IcpStatus, Reason};

/// CM-PRED is NOT ADMISSIBLE until these verify items are cleared (prereg coupling_modes[CM-PRED].blocked_by; EQ-14).
pub const CM_PRED_BLOCKED_BY: [&str; 4] = ["VER-03", "VER-04", "VER-05", "VER-13"];

/// EQ-12 / Takahashi 2024 Eq. (1): eta_p = R_p / (R_p + R_ant).
pub fn coupling_efficiency(r_p_ohm: f64, r_ant_ohm: f64) -> f64 {
    r_p_ohm / (r_p_ohm + r_ant_ohm)
}

/// EQ-12 at the plane where R_ant is defined: (I_ant_rms, P_abs, Q_coil_ohmic) from the delivered power.
pub fn antenna_split(p_delivered_w: f64, r_p_ohm: f64, r_ant_ohm: f64) -> (f64, f64, f64) {
    let i2 = p_delivered_w / (r_ant_ohm + r_p_ohm);
    let eta = coupling_efficiency(r_p_ohm, r_ant_ohm);
    (i2.sqrt(), eta * p_delivered_w, i2 * r_ant_ohm)
}

/// Result of the calibrated coupling at one registered P2 point.
#[derive(Debug, Clone, PartialEq)]
pub struct Calibrated {
    pub r_p_ohm: f64,
    pub r_ant_ohm: f64,
    pub x_ant_ohm: f64,
    pub eta_p: f64,
    pub i_ant_rms_a: f64,
    pub p_fwd_w: f64,
    pub p_refl_w: f64,
    /// RP_ANT: P_fwd - P_refl - Q_line - Q_match; R_VAC: P_net = P_fwd - P_refl.
    pub p_delivered_w: f64,
    pub p_abs_w: f64,
    pub q_coil_ohmic_w: f64,
    /// None under R_VAC (lumped into Q_coil_ohmic, flag LUMPED_R_VAC).
    pub q_line_w: Option<f64>,
    pub q_match_w: Option<f64>,
    pub lumped_r_vac: bool,
}

/// EQ-13 + EQ-12 at a registered P2 point (the caller has checked validation, H_MODE and map location).
#[allow(clippy::too_many_arguments)]
pub fn calibrated(
    p_fwd_w: f64,
    p_refl_w: f64,
    z_hot_re_ohm: f64,
    z_hot_im_ohm: f64,
    r_ant_cold_ohm: f64,
    convention: PlaneConvention,
    q_line_w: Option<f64>,
    q_match_w: Option<f64>,
) -> Result<Calibrated, Vec<Reason>> {
    let mut why = Vec::new();
    let r_p = z_hot_re_ohm - r_ant_cold_ohm;
    if !(r_p.is_finite() && r_p > 0.0 && r_ant_cold_ohm.is_finite() && r_ant_cold_ohm >= 0.0) {
        why.push(Reason::new(
            "EQ-13_R_P_NOT_POSITIVE",
            IcpStatus::ModelError,
            format!("R_p = Re Z_hot - R_ant,cold = {r_p} ohm at an H_MODE point (R_ant,cold = {r_ant_cold_ohm})"),
        ));
    }
    if !(p_fwd_w.is_finite() && p_refl_w.is_finite() && p_fwd_w >= 0.0 && (0.0..=p_fwd_w).contains(&p_refl_w)) {
        why.push(Reason::new("IN-08_RF_POWER_DOMAIN", IcpStatus::OutOfDomain, "need 0 <= P_refl <= P_fwd"));
    }
    let (p_del, q_line, q_match, lumped) = match convention {
        PlaneConvention::RpAnt => match (q_line_w, q_match_w) {
            (Some(l), Some(m)) if l >= 0.0 && m >= 0.0 => (p_fwd_w - p_refl_w - l - m, Some(l), Some(m), false),
            _ => {
                why.push(Reason::new(
                    "EQ-12_LINE_MATCH_LOSS_NOT_REGISTERED",
                    IcpStatus::IncompleteEvidence,
                    "RP_ANT convention needs the registered P2 two-port line and match losses (>= 0)",
                ));
                (f64::NAN, None, None, false)
            }
        },
        PlaneConvention::RVac => (p_fwd_w - p_refl_w, None, None, true),
    };
    if why.is_empty() && p_del < 0.0 {
        why.push(Reason::new("EQ-12_NEGATIVE_DELIVERED_POWER", IcpStatus::ModelError, format!("{p_del} W")));
    }
    if !why.is_empty() {
        return Err(why);
    }
    let (i_ant, p_abs, q_coil) = antenna_split(p_del, r_p, r_ant_cold_ohm);
    Ok(Calibrated {
        r_p_ohm: r_p,
        r_ant_ohm: r_ant_cold_ohm,
        x_ant_ohm: z_hot_im_ohm,
        eta_p: coupling_efficiency(r_p, r_ant_cold_ohm),
        i_ant_rms_a: i_ant,
        p_fwd_w,
        p_refl_w,
        p_delivered_w: p_del,
        p_abs_w: p_abs,
        q_coil_ohmic_w: q_coil,
        q_line_w: q_line,
        q_match_w: q_match,
        lumped_r_vac: lumped,
    })
}

/// LC-03 (CM-CAL / CM-PRED): the RF chain on the trivial n_e = 0 branch (R_p = 0): every delivered watt is antenna
/// circuit loss. Returns (P_abs, Q_coil_ohmic) = (0, P_delivered).
pub fn trivial_branch(p_delivered_w: f64, r_ant_ohm: f64) -> (f64, f64) {
    let (_, p_abs, q_coil) = antenna_split(p_delivered_w, 0.0, r_ant_ohm);
    (p_abs, q_coil)
}

/// EQ-15 bus-plane conversion at `bus_power_boundary_a9_v2` (IF-ICP-BUS-v1).
#[derive(Debug, Clone, PartialEq)]
pub struct BusPlane {
    pub p_rf_source_dc_w: f64,
    pub q_rf_generator_loss_w: f64,
    pub p_matching_dc_w: f64,
    pub p_bias_dc_w: f64,
    pub q_bias_supply_loss_w: f64,
    pub p_assist_magnet_w: f64,
    pub p_flow_control_w: f64,
    pub p_bus_w: f64,
}

/// Registration checks of IN-19 (a violation is MODEL_ERROR: an inconsistent registration, CC-06).
pub fn bus_registration_violations(reg: &BusRegistration) -> Vec<String> {
    let mut v = Vec::new();
    for (n, e) in [("eta_RF", reg.eta_rf.value), ("eta_bias", reg.eta_bias.value)] {
        if !(e.is_finite() && e > 0.0 && e <= 1.0) {
            v.push(format!("{n} = {e} outside (0, 1]"));
        }
    }
    if !(reg.p_match_dc_w.value.is_finite() && reg.p_match_dc_w.value >= 0.0) {
        v.push("P_match,DC must be finite and >= 0".into());
    }
    for (n, s) in [("icp_assist_magnet", &reg.assist_magnet), ("flow_control_icp_feed", &reg.flow_control)] {
        if let VariantSlot::Installed { p_w } = s {
            if !(p_w.value.is_finite() && p_w.value >= 0.0) {
                v.push(format!("{n} must be finite and >= 0"));
            }
        }
    }
    v
}

/// EQ-15 with the CC-06 assumption P_RF,DC >= P_fwd (the source does not recover reflected power): a registration that
/// violates it is refused as MODEL_ERROR.
pub fn bus_plane(reg: &BusRegistration, p_fwd_w: f64, p_refl_w: f64, p_bias_w: f64) -> Result<BusPlane, Reason> {
    let p_rf_dc = (p_fwd_w - p_refl_w) / reg.eta_rf.value;
    if p_rf_dc < p_fwd_w {
        return Err(Reason::new(
            "CC-06_RF_SOURCE_BELOW_FORWARD",
            IcpStatus::ModelError,
            format!("P_RF,DC = {p_rf_dc} W < P_fwd = {p_fwd_w} W with eta_RF = {}", reg.eta_rf.value),
        ));
    }
    if p_bias_w < 0.0 {
        return Err(Reason::new(
            "EQ-15_BIAS_SUPPLY_SINKING_POWER",
            IcpStatus::NotEvaluated,
            format!("collector-bias supply output {p_bias_w} W < 0: no sink conversion is registered"),
        ));
    }
    let p_bias_dc = p_bias_w / reg.eta_bias.value;
    let slot = |s: &VariantSlot| match s {
        VariantSlot::NotInstalled => 0.0,
        VariantSlot::Installed { p_w } => p_w.value,
    };
    let (mag, flow) = (slot(&reg.assist_magnet), slot(&reg.flow_control));
    Ok(BusPlane {
        p_rf_source_dc_w: p_rf_dc,
        q_rf_generator_loss_w: p_rf_dc - (p_fwd_w - p_refl_w),
        p_matching_dc_w: reg.p_match_dc_w.value,
        p_bias_dc_w: p_bias_dc,
        q_bias_supply_loss_w: p_bias_dc - p_bias_w,
        p_assist_magnet_w: mag,
        p_flow_control_w: flow,
        p_bus_w: p_rf_dc + reg.p_match_dc_w.value + p_bias_dc + mag + flow,
    })
}

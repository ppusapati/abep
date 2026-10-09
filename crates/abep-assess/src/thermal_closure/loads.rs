//! Registered loads of the P7 thermal-closure cases (prereg `loads`, `load_sets`; input file
//! `thermal_load_inputs_v<N>.json`). Every number comes from the input file; this module only applies the
//! preregistered formulas, the heat-load factor and one-input overrides (sensitivities, allowables).

use super::{num, ClosureError};
use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LoadSet {
    HotH,
    HotI,
    ColdOp,
    NonFiring,
    BandMax,
}

impl LoadSet {
    pub fn parse(s: &str) -> Option<LoadSet> {
        match s {
            "HOT_H" => Some(LoadSet::HotH),
            "HOT_I" => Some(LoadSet::HotI),
            "COLD_OP" => Some(LoadSet::ColdOp),
            "NON_FIRING" => Some(LoadSet::NonFiring),
            "BAND_MAX" => Some(LoadSet::BandMax),
            _ => None,
        }
    }
}

/// The unscaled operating point of a load set (before the heat-load factor).
#[derive(Debug, Clone)]
pub struct OperatingPoint {
    pub p_d_w: f64,
    pub v_d_v: f64,
    pub f_anode: f64,
    pub f_walls: f64,
    pub f_pole: f64,
    pub e_return_v: f64,
    pub coil_in_w: f64,
    pub coil_out_w: f64,
    pub coil_trim_w: f64,
    pub p_fwd_w: f64,
    /// Replaces I_d E_return when set (AL-RETURN).
    pub return_override_w: Option<f64>,
    pub plume_w: f64,
}

/// IF-ICP-THERMAL-v2 key values of one case [W] and the TK-07 node shares.
#[derive(Debug, Clone, Default)]
pub struct IcpKeys {
    pub slot_sum: f64,
    pub rf_dc: f64,
    pub fwd: f64,
    pub abs: f64,
    pub bias: f64,
    pub conv_loss: f64,
    pub refl: f64,
    pub line: f64,
    pub matchl: f64,
    pub match_dc: f64,
    pub coil: f64,
    pub wall: f64,
    pub rad: f64,
    pub extraction: f64,
    pub up: f64,
    pub down: f64,
    pub plasma_wall_shares_w: BTreeMap<String, f64>,
}

impl IcpKeys {
    pub fn keys(&self) -> Vec<(&'static str, f64)> {
        vec![
            ("P_icp_slot_load_sum_W", self.slot_sum),
            ("P_icp_rf_source_DC_W", self.rf_dc),
            ("P_icp_rf_forward_W", self.fwd),
            ("P_icp_abs_W", self.abs),
            ("P_icp_collector_bias_W", self.bias),
            ("Q_icp_rf_conversion_loss_W", self.conv_loss),
            ("P_icp_rf_reflected_W", self.refl),
            ("Q_icp_line_W", self.line),
            ("Q_icp_match_W", self.matchl),
            ("P_icp_matching_DC_W", self.match_dc),
            ("Q_icp_coil_ohmic_W", self.coil),
            ("Q_icp_plasma_wall_W", self.wall),
            ("Q_icp_radiation_W", self.rad),
            ("Q_icp_extraction_W", self.extraction),
            ("Q_icp_outflow_upstream_W", self.up),
            ("Q_icp_outflow_downstream_W", self.down),
            ("Q_icp_bias_collector_W", 0.0),
            ("Q_icp_bias_export_W", 0.0),
            ("P_icp_flow_control_W", 0.0),
            ("P_icp_assist_magnet_W", 0.0),
        ]
    }
}

/// Every load of one case, after the heat-load factor.
#[derive(Debug, Clone)]
pub struct Loads {
    pub set: LoadSet,
    pub factor: f64,
    pub op: OperatingPoint,
    pub p_d_ref_w: f64,
    pub q_anode_w: f64,
    pub q_wall_in_w: f64,
    pub q_wall_out_w: f64,
    pub q_pole_w: f64,
    pub q_return_w: f64,
    pub q_plume_w: f64,
    pub q_coil_in_w: f64,
    pub q_coil_out_w: f64,
    pub q_coil_trim_w: f64,
    pub icp: IcpKeys,
    pub plume_partition: BTreeMap<String, f64>,
    pub icp_coil_split: BTreeMap<String, f64>,
    pub icp_f_rad: BTreeMap<String, f64>,
    pub icp_f_up: BTreeMap<String, f64>,
    pub rho_kg_m3: f64,
}

fn iv(inputs: &Value, path: &str) -> Result<f64, ClosureError> {
    let mut v = inputs;
    for k in path.split('.') {
        v = &v[k];
    }
    num(v, "value")
}

fn weights(inputs: &Value, path: &str) -> Result<BTreeMap<String, f64>, ClosureError> {
    let mut v = inputs;
    for k in path.split('.') {
        v = &v[k];
    }
    let obj = v["value"].as_object().ok_or_else(|| ClosureError(format!("input {path}: weights")))?;
    obj.iter()
        .map(|(k, x)| x.as_f64().map(|f| (k.clone(), f)).ok_or_else(|| ClosureError(format!("input {path}.{k}"))))
        .collect()
}

/// An input value with the sensitivity overrides applied (`overrides` keyed by "group.name").
fn ov(inputs: &Value, overrides: &BTreeMap<String, f64>, path: &str) -> Result<f64, ClosureError> {
    match overrides.get(path) {
        Some(x) => Ok(*x),
        None => iv(inputs, path),
    }
}

/// The unscaled operating point of a load set.
pub fn operating_point(
    inputs: &Value,
    set: LoadSet,
    overrides: &BTreeMap<String, f64>,
) -> Result<OperatingPoint, ClosureError> {
    let band = |k: usize| -> Result<f64, ClosureError> {
        inputs["discharge"]["P_d_band_W"]["value"][k].as_f64().ok_or_else(|| ClosureError("P_d_band_W".into()))
    };
    let vband = |k: usize| -> Result<f64, ClosureError> {
        inputs["discharge"]["V_d_band_V"]["value"][k].as_f64().ok_or_else(|| ClosureError("V_d_band_V".into()))
    };
    let o = |p: &str| ov(inputs, overrides, p);
    let hot = |p_d: f64, p_fwd: f64| -> Result<OperatingPoint, ClosureError> {
        Ok(OperatingPoint {
            p_d_w: p_d,
            v_d_v: vband(0)?,
            f_anode: o("discharge.f_anode_hot")?,
            f_walls: o("discharge.f_walls_hot")?,
            f_pole: o("discharge.f_pole_hot")?,
            e_return_v: o("discharge.E_return_hot_V")?,
            coil_in_w: o("coils.hot_inner_W")?,
            coil_out_w: o("coils.hot_outer_W")?,
            coil_trim_w: o("coils.trim_W")?,
            p_fwd_w: p_fwd,
            return_override_w: None,
            plume_w: 0.0,
        })
    };
    Ok(match set {
        LoadSet::HotH => hot(o("discharge.P_d_hot_W")?, o("icp.P_fwd_anchor_W")?)?,
        LoadSet::BandMax => hot(band(1)?, o("icp.P_fwd_anchor_W")?)?,
        LoadSet::HotI => hot(band(0)?, o("icp.P_fwd_max_W")?)?,
        LoadSet::ColdOp => OperatingPoint {
            p_d_w: band(0)?,
            v_d_v: vband(1)?,
            f_anode: o("discharge.f_anode_cold")?,
            f_walls: o("discharge.f_walls_cold")?,
            f_pole: o("discharge.f_pole_cold")?,
            e_return_v: o("discharge.E_return_cold_V")?,
            coil_in_w: o("coils.cold_inner_W")?,
            coil_out_w: o("coils.cold_outer_W")?,
            coil_trim_w: o("coils.trim_W")?,
            p_fwd_w: o("icp.P_fwd_anchor_W")?,
            return_override_w: None,
            plume_w: 0.0,
        },
        LoadSet::NonFiring => OperatingPoint {
            p_d_w: 0.0,
            v_d_v: vband(0)?,
            f_anode: 0.0,
            f_walls: 0.0,
            f_pole: 0.0,
            e_return_v: 0.0,
            coil_in_w: 0.0,
            coil_out_w: 0.0,
            coil_trim_w: 0.0,
            p_fwd_w: 0.0,
            return_override_w: None,
            plume_w: 0.0,
        },
    })
}

/// IF-ICP-THERMAL-v2 values at forward power `p_fwd` (prereg `loads.icp_interface.identities`), unscaled.
pub fn icp_keys(inputs: &Value, p_fwd: f64, non_firing: bool) -> Result<IcpKeys, ClosureError> {
    if non_firing {
        let sh = weights(inputs, "icp.plasma_wall_node_shares")?;
        return Ok(IcpKeys {
            plasma_wall_shares_w: sh.keys().map(|k| (k.clone(), 0.0)).collect(),
            ..Default::default()
        });
    }
    let eta_rf = iv(inputs, "icp.eta_RF")?;
    let refl = iv(inputs, "icp.P_refl_frac")? * p_fwd;
    let line = iv(inputs, "icp.Q_line_frac")? * p_fwd;
    let matchl = iv(inputs, "icp.Q_match_frac")? * p_fwd;
    let match_dc = iv(inputs, "icp.P_matching_DC_W")?;
    let eta_p = iv(inputs, "icp.eta_p")?;
    let delivered = p_fwd - refl - line - matchl;
    let abs = eta_p * delivered;
    let coil = delivered - abs;
    let split = weights(inputs, "icp.abs_split")?;
    let g = |k: &str| split.get(k).copied().unwrap_or(0.0);
    let wall = g("plasma_wall") * abs;
    let rad = g("radiation") * abs;
    let extraction = g("extraction") * abs;
    let up = g("outflow_upstream") * abs;
    // The last share closes P_abs exactly (IFI2-05).
    let down = abs - wall - rad - extraction - up;
    let rf_dc = p_fwd / eta_rf;
    let conv_loss = rf_dc - p_fwd;
    let shares = weights(inputs, "icp.plasma_wall_node_shares")?;
    let mut sh: BTreeMap<String, f64> = BTreeMap::new();
    let mut acc = 0.0;
    let n = shares.len();
    for (i, (k, w)) in shares.iter().enumerate() {
        let v = if i + 1 == n { wall - acc } else { w * wall };
        acc += v;
        sh.insert(k.clone(), v);
    }
    Ok(IcpKeys {
        slot_sum: rf_dc + match_dc,
        rf_dc,
        fwd: p_fwd,
        abs,
        bias: 0.0,
        conv_loss,
        refl,
        line,
        matchl,
        match_dc,
        coil,
        wall,
        rad,
        extraction,
        up,
        down,
        plasma_wall_shares_w: sh,
    })
}

fn scale_icp(k: &IcpKeys, f: f64) -> IcpKeys {
    IcpKeys {
        slot_sum: k.slot_sum * f,
        rf_dc: k.rf_dc * f,
        fwd: k.fwd * f,
        abs: k.abs * f,
        bias: k.bias * f,
        conv_loss: k.conv_loss * f,
        refl: k.refl * f,
        line: k.line * f,
        matchl: k.matchl * f,
        match_dc: k.match_dc * f,
        coil: k.coil * f,
        wall: k.wall * f,
        rad: k.rad * f,
        extraction: k.extraction * f,
        up: k.up * f,
        down: k.down * f,
        plasma_wall_shares_w: k.plasma_wall_shares_w.iter().map(|(n, v)| (n.clone(), v * f)).collect(),
    }
}

/// Every load of one case from its operating point and heat-load factor.
pub fn loads(inputs: &Value, set: LoadSet, op: OperatingPoint, factor: f64, rho: f64) -> Result<Loads, ClosureError> {
    let f = factor;
    let share_in = iv(inputs, "discharge.wall_inner_share")?;
    let walls = op.f_walls * op.p_d_w;
    let i_d = if op.v_d_v > 0.0 { op.p_d_w / op.v_d_v } else { 0.0 };
    let q_return = op.return_override_w.unwrap_or(i_d * op.e_return_v);
    let icp_raw = icp_keys(inputs, op.p_fwd_w, set == LoadSet::NonFiring)?;
    // Each partition's last weight closes the sum exactly (E-07 / IFI2-09 at 1e-12).
    let close = |mut w: BTreeMap<String, f64>| -> BTreeMap<String, f64> {
        let total: f64 = w.values().sum();
        if let Some((_, last)) = w.iter_mut().rev().find(|(_, v)| **v > 0.0) {
            *last += 1.0 - total;
        }
        w
    };
    Ok(Loads {
        set,
        factor,
        p_d_ref_w: op.p_d_w * f,
        q_anode_w: op.f_anode * op.p_d_w * f,
        q_wall_in_w: walls * share_in * f,
        q_wall_out_w: walls * (1.0 - share_in) * f,
        q_pole_w: op.f_pole * op.p_d_w * f,
        q_return_w: q_return * f,
        q_plume_w: op.plume_w * f,
        q_coil_in_w: op.coil_in_w * f,
        q_coil_out_w: op.coil_out_w * f,
        q_coil_trim_w: op.coil_trim_w * f,
        icp: scale_icp(&icp_raw, f),
        plume_partition: close(weights(inputs, "discharge.plume_partition")?),
        icp_coil_split: close(weights(inputs, "icp.coil_ohmic_split")?),
        icp_f_rad: close(weights(inputs, "icp.f_rad")?),
        icp_f_up: close(weights(inputs, "icp.f_up")?),
        rho_kg_m3: rho,
        op,
    })
}

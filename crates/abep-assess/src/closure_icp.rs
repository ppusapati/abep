//! A9.38 Priority 4: the RF/ICP neutralizer closure record of the DBF-1 ICP (registration ICP-CLOSURE-REG-v1,
//! `docs/closure/icp/`). M-A runs NP-ICP v2 as implemented on the registered cases. M-B gives the necessary-condition
//! bounds (CONSERVATION_BOUND / NOT_A_PERFORMANCE_PREDICTION). M-C is the Xe published-analog risk indicator, which
//! never changes a state. M-D reports the HC-05 / GNG-ICP-01 status. The record ends with the literal closure state.
//! Raw physics comes only from `abep_icp::v2`. Every bound, ratio and state is formed here (AS-01..AS-05). The
//! registration is hash-verified before anything is built.

use crate::error::{AssessError, AssessResult};
use crate::neutralization::{hc05, neutralization_quantities, CapacityBasis, Current, NeutralizationInputs};
use crate::py::{dict, s};
use crate::thresholds::Thresholds;
use abep_icp::case::{Configuration, CouplingMode, GasMode, RfInput, SupplyMode};
use abep_icp::chemistry::ChemistryRegistration;
use abep_icp::constants::{AMU, E_CHARGE, K_B};
use abep_icp::evidence::{EvidenceRecord, Registered};
use abep_icp::geometry::{HModel, Orientation, Surface, SurfaceKind, ThermalNode};
use abep_icp::v2::case::{ElectrodesV2, GeometryV2, IcpCaseV2, NeutralSourceV2, SupplyIdentity, VolumeModeV2};
use abep_icp::v2::{IcpModelV2, IcpResultV2};
use abep_icp::{IcpStatus, Quantity};
use abep_provenance::read_verified;
use abep_types::pyjson::{Dict, DumpOptions, Value};
use serde_json::Value as J;
use std::collections::{BTreeMap, BTreeSet};
use std::f64::consts::PI;
use std::path::Path;

pub const SCHEMA: &str = "abep_assess_icp_closure_v1";
pub const REG_REL: &str = "docs/closure/icp/icp_closure_registration_v1.json";
pub const REG_SHA256: &str = "41ce4d17a58e0ba6896fd4cfb815856f69c06271ae50b0d602575d5606802d51";
pub const REG_MD_REL: &str = "docs/closure/icp/ICP_CLOSURE_REGISTRATION_v1.md";
pub const REG_MD_SHA256: &str = "6b31e8a47f1cc1098d41419cc96970c18c11b61dfd8f29a5133f9155d0e9733d";
pub const LOCK_REL: &str = "docs/closure/icp/icp_closure_registration_lock_v1.json";
pub const LOCK_SHA256: &str = "5a03e399a980d975651ccd7392077b4fbc56fe825e53f002bba6371d22a156f4";
pub const RECORD_REL: &str = "docs/closure/icp/icp_closure_v1.json";
pub const M2_REL: &str = "docs/milestones/M2_196_state_rfp_closure/m2_closure_record_v1.json";
pub const M2_SHA256: &str = "600cf229ecdb5f91f0471f03cfdd6d287486ad21e9d9ebadde3cdafa54a37394";
pub const RVM_REL: &str = "docs/requirements/rvm_a9/rvm_a9_v1.json";
pub const RVM_SHA256: &str = "f91a00b40e24a66ceec8fd16dba3ad5ecb249ae186cc39bf717efe083223a5c4";
pub const VER25_REL: &str = "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/verification_addendum_ver25_v1.json";
pub const SOURCE_READS_REL: &str =
    "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/verification_addendum_a938_source_reads_v1.json";

pub const STATE_DCR: &str = "DCR REQUIRED";
pub const STATE_CLOSED: &str = "CLOSED";
pub const STATE_FROZEN_EM: &str = "FROZEN FOR EM";
pub const STATE_BLOCKED: &str = "BLOCKED BY SPECIFIC MISSING EVIDENCE";

fn me(m: impl Into<String>) -> AssessError {
    AssessError::new("ModelError", m)
}

fn f(x: f64) -> Value {
    Value::Float(x)
}

fn sl<I: IntoIterator<Item = String>>(xs: I) -> Value {
    Value::List(xs.into_iter().map(Value::Str).collect())
}

fn int(n: usize) -> Value {
    Value::int(i64::try_from(n).unwrap_or(i64::MAX))
}

fn ptr<'a>(v: &'a J, p: &str) -> AssessResult<&'a J> {
    v.pointer(p).ok_or_else(|| me(format!("{REG_REL}: {p} missing")))
}

fn num(v: &J, p: &str) -> AssessResult<f64> {
    ptr(v, p)?.as_f64().ok_or_else(|| me(format!("{REG_REL}: {p} is not a number")))
}

fn nums(v: &J, p: &str) -> AssessResult<Vec<f64>> {
    ptr(v, p)?
        .as_array()
        .ok_or_else(|| me(format!("{REG_REL}: {p} is not a list")))?
        .iter()
        .map(|x| x.as_f64().ok_or_else(|| me(format!("{REG_REL}: {p} entry is not a number"))))
        .collect()
}

fn text(v: &J, p: &str) -> AssessResult<String> {
    ptr(v, p)?.as_str().map(str::to_string).ok_or_else(|| me(format!("{REG_REL}: {p} is not a string")))
}

fn evidence(v: &J, p: &str) -> AssessResult<EvidenceRecord> {
    let e: EvidenceRecord =
        serde_json::from_value(ptr(v, p)?.clone()).map_err(|e| me(format!("{REG_REL}: {p}: {e}")))?;
    let miss = e.missing_attributes();
    if !miss.is_empty() {
        return Err(me(format!("{REG_REL}: {p} misses {}", miss.join(", "))));
    }
    Ok(e)
}

fn input<'a>(reg: &'a J, id: &str) -> AssessResult<(&'a J, String)> {
    let list = ptr(reg, "/inputs")?.as_array().ok_or_else(|| me("inputs"))?;
    let i = list.iter().position(|x| x.get("id").and_then(J::as_str) == Some(id)).ok_or_else(|| me(id.to_string()))?;
    Ok((&list[i], format!("/inputs/{i}")))
}

/// The registration, verified against its lock (both files and the lock itself are pinned here).
pub fn load_registration(repo: &Path) -> AssessResult<J> {
    let lock = read_verified(&repo.join(LOCK_REL), LOCK_SHA256)?;
    let lock: J = serde_json::from_slice(&lock).map_err(|e| me(format!("{LOCK_REL}: {e}")))?;
    for (k, want) in
        [("icp_closure_registration_v1.json", REG_SHA256), ("ICP_CLOSURE_REGISTRATION_v1.md", REG_MD_SHA256)]
    {
        if lock.pointer(&format!("/files/{k}")).and_then(J::as_str) != Some(want) {
            return Err(me(format!("{LOCK_REL}: files.{k} != {want}")));
        }
    }
    read_verified(&repo.join(REG_MD_REL), REG_MD_SHA256)?;
    let b = read_verified(&repo.join(REG_REL), REG_SHA256)?;
    serde_json::from_slice(&b).map_err(|e| me(format!("{REG_REL}: {e}")))
}

/// One flight or bench mode of the registration.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ClosureMode {
    Air,
    Xe,
    EmN2,
}

impl ClosureMode {
    pub const ALL: [ClosureMode; 3] = [ClosureMode::Air, ClosureMode::Xe, ClosureMode::EmN2];

    pub fn key(self) -> &'static str {
        match self {
            ClosureMode::Air => "AIR_PRIMARY",
            ClosureMode::Xe => "XE_CONTINGENCY",
            ClosureMode::EmN2 => "EM-N2",
        }
    }

    fn supply(self) -> SupplyMode {
        match self {
            ClosureMode::Air => SupplyMode::AirPrimary,
            ClosureMode::Xe => SupplyMode::XeContingency,
            ClosureMode::EmN2 => SupplyMode::EmN2,
        }
    }

    fn chemistry(self) -> ChemistryRegistration {
        match self {
            ClosureMode::Air => ChemistryRegistration::NotRegistered { gas: "AIR".into() },
            ClosureMode::Xe => ChemistryRegistration::NotRegistered { gas: "XE".into() },
            ClosureMode::EmN2 => ChemistryRegistration::RegisteredSet { config_file: "n2_n.toml".into() },
        }
    }

    pub fn is_flight(self) -> bool {
        !matches!(self, ClosureMode::EmN2)
    }
}

/// One grid point of M-A.
#[derive(Debug, Clone, PartialEq)]
pub struct GridPoint {
    pub mode: ClosureMode,
    pub member: String,
    pub p_abs_w: f64,
    pub p_icp_pa: f64,
    pub v_bias_v: f64,
}

impl GridPoint {
    pub fn case_id(&self) -> String {
        format!(
            "DBF1_ICP_CLOSURE_V1_{}_{}_P{}_p{}_V{}",
            self.mode.key(),
            self.member,
            self.p_abs_w,
            self.p_icp_pa,
            self.v_bias_v
        )
    }
}

/// The case builder: the DBF-1 config plus the registration (RI-01..RI-08).
pub struct CaseBuilder {
    reg: J,
    cfg: abep_config::baseline::Dbf1Config,
}

impl CaseBuilder {
    pub fn new(repo: &Path) -> AssessResult<Self> {
        let reg = load_registration(repo)?;
        let cfg = abep_config::baseline::load_dbf1(repo)?;
        let ic = &cfg.icp;
        let geo = |k: &str| reg.pointer(&format!("/inputs/1/value/{k}")).and_then(J::as_str).unwrap_or("").to_string();
        // RI-02 names the DBF-1 values; the config must carry exactly them.
        for (k, want, have) in
            [("R_m", "0.06", ic.radius_m), ("L_m", "0.15", ic.length_m), ("L_c_m", "0.10", ic.collector_axial_length_m)]
        {
            let ok = geo(k).ends_with(want) && (have - want.parse::<f64>().unwrap_or(f64::NAN)).abs() == 0.0;
            if !ok {
                return Err(me(format!("RI-02 {k} ({}) differs from the DBF-1 config value {have}", geo(k))));
            }
        }
        if (ic.f_rf_hz - num(&reg, "/inputs/7/value/f_RF_Hz")?).abs() > 0.0 {
            return Err(me("RI-08 f_RF differs from DBF1-RF-01"));
        }
        if (ic.p_fwd_envelope_w[1] - num(&reg, "/inputs/0/value/P_net_max_W")?).abs() > 0.0 {
            return Err(me("RI-01 P_net,max differs from the DBF1-RF-02 envelope end"));
        }
        Ok(CaseBuilder { reg, cfg })
    }

    pub fn registration(&self) -> &J {
        &self.reg
    }

    fn ev(&self, id: &str, sub: &str) -> AssessResult<EvidenceRecord> {
        let (_, base) = input(&self.reg, id)?;
        evidence(&self.reg, &format!("{base}/{sub}"))
    }

    /// The members of a mode (RI-06).
    pub fn members(&self, m: ClosureMode) -> AssessResult<Vec<(String, BTreeMap<String, f64>)>> {
        let (_, base) = input(&self.reg, "RI-06")?;
        let list = ptr(&self.reg, &format!("{base}/value/composition_members/{}", m.key()))?
            .as_array()
            .ok_or_else(|| me("composition members"))?;
        list.iter()
            .map(|x| {
                let id = x.get("id").and_then(J::as_str).ok_or_else(|| me("member id"))?.to_string();
                let comp: BTreeMap<String, f64> = x
                    .get("x")
                    .and_then(J::as_object)
                    .ok_or_else(|| me("member x"))?
                    .iter()
                    .map(|(k, v)| v.as_f64().map(|v| (k.clone(), v)).ok_or_else(|| me("member fraction")))
                    .collect::<AssessResult<_>>()?;
                Ok((id, comp))
            })
            .collect()
    }

    /// The full M-A grid in registration order: mode, member, P_abs, p_ICP, V_bias.
    pub fn grid(&self) -> AssessResult<Vec<GridPoint>> {
        let (_, b1) = input(&self.reg, "RI-01")?;
        let (_, b3) = input(&self.reg, "RI-03")?;
        let (_, b6) = input(&self.reg, "RI-06")?;
        let pa = nums(&self.reg, &format!("{b1}/value/P_abs_grid_W"))?;
        let vb = nums(&self.reg, &format!("{b3}/value/V_bias_grid_V"))?;
        let pp = nums(&self.reg, &format!("{b6}/value/p_ICP_grid_Pa"))?;
        let mut out = vec![];
        for m in ClosureMode::ALL {
            for (id, _) in self.members(m)? {
                for &p_abs_w in &pa {
                    for &p_icp_pa in &pp {
                        for &v_bias_v in &vb {
                            out.push(GridPoint { mode: m, member: id.clone(), p_abs_w, p_icp_pa, v_bias_v });
                        }
                    }
                }
            }
        }
        Ok(out)
    }

    /// The reference point REF-ICP-1 of a mode.
    pub fn reference(&self, m: ClosureMode) -> AssessResult<GridPoint> {
        let r = ptr(&self.reg, "/reference_point")?;
        Ok(GridPoint {
            mode: m,
            member: text(r, &format!("/members/{}", m.key()))?,
            p_abs_w: num(r, "/P_abs_W")?,
            p_icp_pa: num(r, "/p_ICP_Pa")?,
            v_bias_v: num(r, "/V_bias_V")?,
        })
    }

    fn geometry(&self) -> AssessResult<Registered<GeometryV2>> {
        let ic = &self.cfg.icp;
        let (r, l, lc) = (ic.radius_m, ic.length_m, ic.collector_axial_length_m);
        let surf = |id: &str, kind, area, o, node, material: &str| Surface {
            id: id.into(),
            kind,
            area_m2: area,
            orientation: o,
            material: material.into(),
            thermal_node: node,
            transmission: None,
        };
        let (_, base) = input(&self.reg, "RI-02")?;
        let gid = text(&self.reg, &format!("{base}/value/geometry_id"))?;
        let ec_mat = text(&self.reg, &format!("{base}/value/surfaces/3/material"))?;
        Ok(Registered::new(
            GeometryV2 {
                geometry_id: gid,
                radius_m: r,
                length_m: l,
                volume_mode: VolumeModeV2::AssumedGeometricTube,
                surfaces: vec![
                    surf(
                        "vessel",
                        SurfaceKind::DielectricFloating,
                        2.0 * PI * r * (l - lc),
                        Orientation::Radial,
                        ThermalNode::NVessel,
                        &ic.vessel_material,
                    ),
                    surf(
                        "collector",
                        SurfaceKind::IonCollectorBiased,
                        2.0 * PI * r * lc,
                        Orientation::Radial,
                        ThermalNode::NCollector,
                        &ic.collector_material,
                    ),
                    surf(
                        "up",
                        SurfaceKind::OpenUpstream,
                        PI * r * r,
                        Orientation::Axial,
                        ThermalNode::RxH1Face,
                        "OPEN",
                    ),
                    surf(
                        "ec",
                        SurfaceKind::ElectronCollector,
                        PI * r * r,
                        Orientation::Axial,
                        ThermalNode::Export,
                        &ec_mat,
                    ),
                ],
            },
            self.ev("RI-02", "evidence")?,
        ))
    }

    fn h_model(&self, m: ClosureMode) -> AssessResult<Option<HModel>> {
        let (_, base) = input(&self.reg, "RI-05")?;
        let ions: &[&str] = match m {
            ClosureMode::Air => return Ok(None),
            ClosureMode::Xe => &["Xe^+"],
            ClosureMode::EmN2 => &["N2^+", "N^+"],
        };
        let mut sigma = BTreeMap::new();
        for ion in ions {
            let v = num(&self.reg, &format!("{base}/value/sigma_i_m2/{ion}"))?;
            let e = evidence(&self.reg, &format!("{base}/per_value_evidence/{ion}"))?;
            sigma.insert((*ion).to_string(), Registered::new(v, e));
        }
        Ok(Some(HModel::Lieberman { sigma_i_m2: sigma }))
    }

    /// The NP-ICP v2 case of one grid point.
    pub fn case(&self, g: &GridPoint) -> AssessResult<IcpCaseV2> {
        let m = g.mode;
        let comp = self
            .members(m)?
            .into_iter()
            .find(|(id, _)| id == &g.member)
            .map(|x| x.1)
            .ok_or_else(|| me(format!("member {} of {}", g.member, m.key())))?;
        let (_, b3) = input(&self.reg, "RI-03")?;
        let sweep = nums(&self.reg, &format!("{b3}/value/collector_bias_sweep_V"))?;
        let reference = text(&self.reg, &format!("{b3}/value/reference"))?;
        let t_g = num(&self.reg, &format!("{}/value/T_g_K", input(&self.reg, "RI-06")?.1))?;
        let b = num(&self.reg, &format!("{}/value/B_ICP_max_T", input(&self.reg, "RI-04")?.1))?;
        let ev8 = self.ev("RI-08", "evidence")?;
        let ev6 = self.ev("RI-06", "evidence")?;
        Ok(IcpCaseV2 {
            case_id: g.case_id(),
            supply_mode: Registered::new(m.supply(), ev8.clone()),
            gas_mode: Registered::new(GasMode::GReuse, ev8.clone()),
            configuration: Configuration::CapOff,
            coupling_mode: CouplingMode::Absorbed,
            h1_point_id: None,
            validation_cell_id: None,
            f_rf_hz: Some(Registered::new(self.cfg.icp.f_rf_hz, ev8)),
            rf_input: Some(RfInput::AbsorbedPower {
                p_abs_w: Registered::new(g.p_abs_w, self.ev("RI-01", "evidence")?),
            }),
            coupling_evidence: None,
            geometry: Some(self.geometry()?),
            electrodes: Some(Registered::new(
                ElectrodesV2 {
                    reference,
                    potentials_v: [("collector".to_string(), 0.0), ("ec".to_string(), g.v_bias_v)].into(),
                    supplies: [
                        ("collector".to_string(), SupplyIdentity::IcpCollectorBias),
                        ("ec".to_string(), SupplyIdentity::IcpCollectorBias),
                    ]
                    .into(),
                    collector_bias_sweep_v: Some(sweep),
                },
                self.ev("RI-03", "evidence")?,
            )),
            neutral_source: Some(NeutralSourceV2::RegisteredPressure {
                p_icp_pa: Registered::new(g.p_icp_pa, ev6.clone()),
                t_g_k: Registered::new(t_g, ev6.clone()),
                mole_fractions: Registered::new(comp, ev6),
            }),
            background: None,
            thermal_boundary: None,
            b_icp_max_t: Some(Registered::new(b, self.ev("RI-04", "evidence")?)),
            chemistry: m.chemistry(),
            h_model: self.h_model(m)?,
            wall_coefficients: vec![],
            dispositions: BTreeMap::new(),
            dissociation_energies_ev: BTreeMap::new(),
            dedicated_flow_kg_s: None,
            bus: None,
            coil_ohmic_split: None,
            hall_demand: None,
        })
    }
}

/// I_e,cap of a result over its solve members: (CONVERGED values, withheld statuses with reasons).
fn i_e_cap(r: &IcpResultV2) -> (Vec<f64>, BTreeSet<String>) {
    let mut vals = vec![];
    let mut withheld = BTreeSet::new();
    for sm in &r.solve_members {
        match sm.outputs.get("I_e_cap_A").and_then(|o| o.scalar()) {
            Some(Quantity { value: Some(v), status, .. }) if status.is_converged() => vals.push(*v),
            Some(q) => {
                withheld.insert(format!("{}: {}", q.status.as_str(), q.reasons.join(", ")));
            }
            None => {
                withheld.insert("NOT_EVALUATED: no I_e_cap_A key".into());
            }
        }
    }
    (vals, withheld)
}

/// M-A for one mode: counts, reason codes, flags, verify items, I_e,cap per point and envelope, the reference point.
fn model_mode(model: &IcpModelV2, b: &CaseBuilder, grid: &[GridPoint], m: ClosureMode) -> AssessResult<(Value, Value)> {
    let mut status_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut codes: BTreeMap<String, usize> = BTreeMap::new();
    let (mut flags, mut verify) = (BTreeSet::new(), BTreeSet::new());
    let (mut conv, mut withheld) = (vec![], BTreeSet::new());
    let mut n = 0usize;
    for g in grid.iter().filter(|g| g.mode == m) {
        let r = model.evaluate(&b.case(g)?);
        n += 1;
        *status_counts.entry(r.status.as_str().into()).or_default() += 1;
        for c in r.reason_codes() {
            *codes.entry(c).or_default() += 1;
        }
        flags.extend(r.flags.iter().cloned());
        verify.extend(r.verify_items_on_path.iter().cloned());
        let (v, w) = i_e_cap(&r);
        conv.extend(v);
        withheld.extend(w);
    }
    let env = if conv.is_empty() {
        dict(vec![("status", s("WITHHELD")), ("reason", s("no CONVERGED I_e,cap at any grid point"))])
    } else {
        dict(vec![
            ("min_A", f(conv.iter().copied().fold(f64::INFINITY, f64::min))),
            ("max_A", f(conv.iter().copied().fold(f64::NEG_INFINITY, f64::max))),
        ])
    };
    let rp = b.reference(m)?;
    let r = model.evaluate(&b.case(&rp)?);
    let (rv, rw) = i_e_cap(&r);
    let reference = dict(vec![
        ("case_id", s(rp.case_id())),
        ("status", s(r.status.as_str())),
        ("reason_codes", sl(r.reason_codes())),
        ("I_e_cap_A", if rv.is_empty() { Value::Null } else { f(rv.iter().copied().fold(f64::INFINITY, f64::min)) }),
        ("I_e_cap_withheld", sl(rw)),
        ("verify_items_on_path", sl(r.verify_items_on_path.iter().cloned())),
        ("flags", sl(r.flags.iter().cloned())),
        ("validation_status", s(r.validation_status.clone())),
        ("verification_status", s(r.verification_status.clone())),
    ]);
    let mut cd = Dict::new();
    for (k, v) in &codes {
        cd.insert(k, int(*v));
    }
    let mut sc = Dict::new();
    for (k, v) in &status_counts {
        sc.insert(k, int(*v));
    }
    let rec = dict(vec![
        ("n_cases", int(n)),
        ("status_counts", Value::Dict(sc)),
        ("reason_codes_with_counts", Value::Dict(cd)),
        ("flags", sl(flags)),
        ("verify_items_on_path", sl(verify)),
        ("I_e_cap_converged_points", int(conv.len())),
        ("I_e_cap_envelope", env),
        ("I_e_cap_withheld_statuses", sl(withheld)),
        ("reference_point", reference.clone()),
    ]);
    Ok((rec, reference))
}

/// Codes of the frozen M2 record's P-ICP-DBF1 path for one mode (verified).
fn m2_codes(repo: &Path, mode: &str) -> AssessResult<BTreeSet<String>> {
    let b = read_verified(&repo.join(M2_REL), M2_SHA256)?;
    let v: J = serde_json::from_slice(&b).map_err(|e| me(format!("{M2_REL}: {e}")))?;
    Ok(v.pointer(&format!("/icp_dbf1/{mode}/codes"))
        .and_then(J::as_array)
        .ok_or_else(|| me(format!("{M2_REL}: icp_dbf1.{mode}.codes")))?
        .iter()
        .filter_map(|x| x.as_str().map(str::to_string))
        .collect())
}

/// M-B and M-C numbers (pure arithmetic on registered constants).
#[derive(Debug, Clone, PartialEq)]
pub struct Bounds {
    pub i_beam_lb_a: f64,
    pub p_abs_min_cons_w: Vec<(String, f64)>,
}

/// B1: I_beam,LB = T (e / (2 m V_d,max))^(1/2) [A] for a singly charged ion of mass m_u [u].
pub fn i_beam_lb(t_n: f64, m_u: f64, v_d_max: f64) -> f64 {
    t_n * (E_CHARGE / (2.0 * m_u * AMU * v_d_max)).sqrt()
}

/// B3: I_e,cap,UB = e P_abs / E_iz,min [A] (E_iz in eV, so e cancels: P_abs / E_iz).
pub fn i_e_cap_ub(p_abs_w: f64, e_iz_ev: f64) -> f64 {
    p_abs_w / e_iz_ev
}

/// B5: isotropic G-REUSE pressure information p = 4 (mdot / m) k T / (vbar 2 pi R^2) [Pa].
pub fn p_greuse(mdot_kg_s: f64, m_u: f64, t_g_k: f64, r_m: f64) -> f64 {
    let m = m_u * AMU;
    let vbar = (8.0 * K_B * t_g_k / (PI * m)).sqrt();
    4.0 * (mdot_kg_s / m) * K_B * t_g_k / (vbar * 2.0 * PI * r_m * r_m)
}

fn bounds_value(reg: &J, thr: &Thresholds, r_m: f64) -> AssessResult<(Value, Value, BTreeMap<String, Vec<f64>>)> {
    let c = "/methods/M-B/constants";
    let ts = nums(reg, &format!("{c}/T_points_N"))?;
    let lim = |id: &str| thr.limits.iter().find(|x| x.0 == id).and_then(|x| x.1);
    if ts.len() != 2 || lim("HC-01") != Some(ts[0]) || lim("HC-02") != Some(ts[1]) {
        return Err(me("M-B thrust points differ from HC-01 / HC-02 (config/assessment through abep-config)"));
    }
    let vd = num(reg, &format!("{c}/V_d_max_V"))?;
    let pnet = num(reg, &format!("{c}/P_net_max_W"))?;
    let eta_ref = num(reg, &format!("{c}/eta_p_ref"))?;
    let p_grid = nums(reg, "/inputs/0/value/P_abs_grid_W")?;
    let mut per_mode = Dict::new();
    let mut i_req: BTreeMap<String, Vec<f64>> = BTreeMap::new();
    let mut analog = Dict::new();
    for (mode, e_keys) in [
        ("AIR_PRIMARY", vec!["AIR_PRIMARY_with_NO", "AIR_PRIMARY_without_NO"]),
        ("XE_CONTINGENCY", vec!["XE_CONTINGENCY"]),
    ] {
        let mu = num(reg, &format!("{c}/m_heaviest_u/{mode}"))?;
        let mut pts = vec![];
        let mut reqs = vec![];
        for &t in &ts {
            let ib = i_beam_lb(t, mu, vd);
            reqs.push(ib);
            let (mut pmin, mut etamin, mut ubmax) = (Dict::new(), Dict::new(), Dict::new());
            // A non-closure claim must hold under the favourable bound: the largest UB (lowest E_iz) decides.
            let mut ub_fav = 0.0_f64;
            for k in &e_keys {
                let e = num(reg, &format!("{c}/E_iz_min_eV/{k}"))?;
                let p = ib * e;
                pmin.insert(*k, f(p));
                etamin.insert(*k, f(p / pnet));
                ubmax.insert(*k, f(i_e_cap_ub(pnet, e)));
                ub_fav = ub_fav.max(i_e_cap_ub(pnet, e));
            }
            pts.push(dict(vec![
                ("T_N", f(t)),
                ("I_beam_LB_A", f(ib)),
                ("I_e_req_LB_A", f(ib)),
                ("P_abs_min_cons_W", Value::Dict(pmin)),
                ("eta_p_min_cons_at_P_net_max", Value::Dict(etamin)),
                ("I_e_cap_UB_at_P_net_max_eta_1_A", Value::Dict(ubmax)),
                ("conservation_feasible_in_envelope", Value::Bool(ub_fav >= ib)),
            ]));
        }
        let mut ub = Dict::new();
        for k in &e_keys {
            let e = num(reg, &format!("{c}/E_iz_min_eV/{k}"))?;
            ub.insert(*k, Value::List(p_grid.iter().map(|p| f(i_e_cap_ub(*p, e))).collect()));
        }
        per_mode.insert(
            mode,
            dict(vec![
                ("m_heaviest_u", f(mu)),
                ("thrust_points", Value::List(pts)),
                ("I_e_cap_UB_A_on_P_abs_grid", Value::Dict(ub)),
                ("P_abs_grid_W", Value::List(p_grid.iter().map(|x| f(*x)).collect())),
            ]),
        );
        // M-C (Xe only).
        if mode == "XE_CONTINGENCY" {
            let mut rows = vec![];
            for (t, ib) in ts.iter().zip(&reqs) {
                for eps in [230.0, 450.0] {
                    let p = ib * eps;
                    rows.push(dict(vec![
                        ("T_N", f(*t)),
                        ("epsilon_ext_eV_per_ion", f(eps)),
                        ("P_abs_analog_W", f(p)),
                        ("eta_p_req_analog_at_P_net_max", f(p / pnet)),
                        ("shortfall_factor_vs_eta_p_ref", f(p / pnet / eta_ref)),
                        ("I_e_at_eta_p_ref_analog_A", f(eta_ref * pnet / eps)),
                    ]));
                }
            }
            analog.insert(
                mode,
                dict(vec![
                    ("labels", sl(["ANALOG_ESTIMATE_NOT_A_MODEL_RESULT".to_string(), "RISK_INDICATOR".to_string()])),
                    ("source", s("SR-05 GK2008 sec. 4.5 pp. 154-157 (rf ion thruster, absorbed-power basis)")),
                    ("rows", Value::List(rows)),
                ]),
            );
        } else {
            analog.insert(
                mode,
                dict(vec![
                    ("status", s("NOT_EVALUATED")),
                    ("reason", s("no registered AIR / N2 / O analog of absorbed power per extracted ampere")),
                ]),
            );
        }
        i_req.insert(mode.to_string(), reqs);
    }
    // B5 information.
    let mut b5 = vec![];
    let r6t = num(reg, "/inputs/5/value/T_g_K")?;
    for (label, mdot) in [("DBF1-BD-01 worst delivered", 1.43e-9), ("A4 12 mN", 4.796e-8), ("A4 25 mN", 2.082e-7)] {
        let mut d = Dict::new();
        for (sp, mu) in [("O", 15.99977), ("N2", 2.0 * 14.00728), ("Xe", 131.299)] {
            d.insert(sp, f(p_greuse(mdot, mu, r6t, r_m)));
        }
        b5.push(dict(vec![("flow", s(label)), ("mdot_kg_s", f(mdot)), ("p_Pa_by_species", Value::Dict(d))]));
    }
    let bounds = dict(vec![
        ("labels", sl(["CONSERVATION_BOUND".to_string(), "NOT_A_PERFORMANCE_PREDICTION".to_string()])),
        ("V_d_max_V", f(vd)),
        ("P_net_max_W", f(pnet)),
        ("per_mode", Value::Dict(per_mode)),
        ("B5_greuse_pressure_information", Value::List(b5)),
    ]);
    Ok((bounds, Value::Dict(analog), i_req))
}

fn gng_icp_01(repo: &Path) -> AssessResult<Value> {
    let b = read_verified(&repo.join(RVM_REL), RVM_SHA256)?;
    let v: J = serde_json::from_slice(&b).map_err(|e| me(format!("{RVM_REL}: {e}")))?;
    let g = v
        .get("owner_approved_gates")
        .and_then(J::as_array)
        .and_then(|l| l.iter().find(|x| x.get("id").and_then(J::as_str) == Some("GNG-ICP-01")))
        .ok_or_else(|| me("GNG-ICP-01 not in the RVM"))?;
    let st = |k: &str| g.get(k).and_then(J::as_str).unwrap_or("").to_string();
    Ok(dict(vec![
        ("gate", s("GNG-ICP-01")),
        ("status", s(st("status"))),
        ("criteria", s(st("criteria"))),
        ("status_reason", s(st("status_reason"))),
        ("source", s(format!("{RVM_REL} owner_approved_gates[GNG-ICP-01] (sha256 {RVM_SHA256})"))),
    ]))
}

/// Static map of the chemistry admission gaps to the reachable / blocked source routes found on 2026-10-08
/// (registration SR-* and host_reachability_2026_10_08; docs/chemistry/o_o2/o_o2_source_matrix_v1.json).
pub const CHEMISTRY_ROUTES: &[(&str, &str, &str)] = &[
    ("AIR-ION-02", "IN_REPO: SONG2026 accepted-manuscript table (docs/chemistry/o_o2/v0, sha-pinned; Hall set abep-air-0.3)", "version-of-record check: pubs.aip.org HTTP 403"),
    ("AIR-ION-05", "IN_REPO: SONG2026 accepted-manuscript upper / lower pair (v0; Hall abep-air-0.4 / 0.5)", "version-of-record check: pubs.aip.org HTTP 403"),
    ("AIR-EL-03", "IN_REPO: SONG2026 Table V (v0; Hall abep-air-0.7)", "version-of-record check: pubs.aip.org HTTP 403"),
    ("AIR-DIS-02", "IN_REPO >= 13.5 eV: SONG2026 Table VI (Cosby 1993)", "below 13.5 eV (Herzberg / Schumann-Runge): no reachable source; Cosby 1993 pubs.aip.org HTTP 403"),
    ("AIR-EL-04", "PARTIAL: Itikawa & Ichimura 1990 JPCRD 19, 637 NIST reprint (srd.nist.gov reachable; Fig. 4.1, < 14 eV, figure only)", "Tayal & Zatsarinny 2016 BSR (journals.aps.org HTTP 403, supplement paywalled); SONG2026 Fig. 24 (pubs.aip.org HTTP 403); Williams & Allen 1989 (iopscience paywall)"),
    ("AIR-EXC-04", "PARTIAL: Tashiro, Morokuma & Tennyson 2006 arXiv:physics/0604098 (open; figure only)", "Huang 2022 (pubs.acs.org HTTP 403); Shyn & Sweeney 1993 (journals.aps.org HTTP 403); above 20 eV no source (OD-6)"),
    ("AIR-EXC-05", "PARTIAL: Tashiro 2006 arXiv (open preprint)", "Huang 2022 (pubs.acs.org HTTP 403); Teillet-Billy 1989 (iopscience paywall)"),
    ("AIR-EXC-09", "REACHABLE: Laher & Gilmore 1990 JPCRD 19, 277 NIST reprint (srd.nist.gov; analytic fits, evaluated measurement)", "BSR-1116 Tayal & Zatsarinny 2016 (journals.aps.org HTTP 403); O state list = owner OD-3 (OQ-CHEM-07)"),
    ("AIR-NL-02", "INPUT: delivered composition from the upstream chain (DCR-001, L-INTAKE-DCR001)", "not registered: no admitted delivered state"),
    ("AIR-WALL-01", "STRUCTURAL: ion-to-neutral wall return (parent EQ-03 / EQ-09 / EQ-18); molecular branching envelope (UE-02)", "energy terms wait on VER-12 (no surface-physics source read)"),
    ("AIR-WALL-02", "ENVELOPE: gamma_O in {0, 1} (parent IN-18)", "sourced gamma for borosilicate (Kim & Boudart 1991, Langmuir: pubs.acs.org HTTP 403)"),
    ("AIR-WALL-03", "ENVELOPE: gamma_N in {0, 1}", "as AIR-WALL-02"),
    ("SB-NO", "REACHABLE: NIST SRD 107 NO entry (BEB orbital constants, physics.nist.gov)", "Itikawa 2016 JPCRD 45, 033106 (pubs.aip.org HTTP 403)"),
    ("SB-He", "REACHABLE (ionization): NIST SRD 107 He", "He momentum transfer / excitation: no source identified (LXCat excluded)"),
    ("SB-Ar", "none reachable", "Ar is not in NIST SRD 107; Rapp & Englander-Golden 1965 / Straub 1995 (pubs.aip.org / journals.aps.org HTTP 403)"),
    ("NEG-CRIT", "none reachable", "AIR-NEG-02 Vejby-Christensen 1996 (journals.aps.org HTTP 403); AIR-NEG-03 no source"),
    ("CA-ICP-v1", "method preregistered (NP-ICP-CHEM-AIR sec. 9)", "NOT_RUN: needs every tier-1 table and the Stage-E grid addendum (OQ-CHEM-04); Hall CA-HALL-AIR-v1 verdicts do not transfer (RU-03)"),
    ("XE-ION-01", "REACHABLE: GK2008 Appendix D Table D-1 (Rapp & Englander-Golden ionization 12.5-100 eV, level 5; registered document a373c8a2)", "primary Rejoub, Lindsay & Stebbings 2002 (journals.aps.org HTTP 403); Rapp & Englander-Golden 1965 (pubs.aip.org HTTP 403); table ends at 100 eV, so the validity limit falls below the 45 eV mean-energy D-CHEM end (IX-04 tail rule)"),
    ("XE-EXC-01", "REACHABLE: GK2008 Table D-1 Hayashi total excitation to 100 eV and the 10 V average excitation potential (p. 97), level 5", "primary Hayashi 1983 (iopscience paywall); candidate compilation Mukundan & Bhardwaj arXiv:1604.08449 (open, not read)"),
    ("XE-EL-01", "REACHABLE: GK2008 Eq. (3.6-13) Maxwellian-averaged e-Xe fit (p. 58, level 5; from Katz et al. 2003)", "a direct-rate fit representation (registry channel kind) is needed; primary Hayashi 1983 (iopscience paywall)"),
    ("XE-WALL-01", "STRUCTURAL: Xe+ -> Xe at walls", "energy terms wait on VER-12"),
    ("XE-CA-12", "method preregistered (CA-12)", "XE-ION-02 Syage 1992 (journals.aps.org HTTP 403) / Stephan & Maerk 1984 (pubs.aip.org HTTP 403); XE-ION-03 and XE-REC-01 have no source (UNBOUNDED_OMISSION unless bounded or owner-disposed); XE-EXC-02 envelope"),
    ("XE-LOADER", "IF-CHEM-REG-v1 (preregistered interface)", "abep-icp has no registry-backed Xe set path today: ChemistryRegistration::RegisteredSet for XE_CONTINGENCY is MODEL_ERROR IN-16_SET_DOES_NOT_MATCH_MODE (implementation step, not a model change)"),
    ("GOVERNANCE", "registry edits are one table per commit (build plan)", "every tier-1 change alters the codes that the frozen M2 record regenerates byte for byte (m2_dbf1.rs committed_m2_record_is_the_a8_record_of_today): coordinator decision needed (snapshot pin or M2 v2)"),
];

fn chemistry_value(model: &IcpModelV2) -> Value {
    let reg = &model.v1.chem_registry;
    let mode = |m: &abep_chem::registry::ModeRegistry| {
        dict(vec![
            ("label", s(m.label.clone())),
            ("admission_status", s(m.admission_status.clone())),
            ("admission_today", s(m.admission_today.clone())),
            ("completeness_audit", s(m.completeness_audit_status.clone())),
            ("neg_crit", m.neg_crit_status.clone().map_or(Value::Null, s)),
            ("tier1_gaps", sl(m.tier1_gaps().iter().map(|p| format!("{} ({})", p.id, p.status.as_str())))),
            ("species_bounds", sl(m.species_bounds.iter().map(|b| format!("{} {}", b.id, b.status)))),
            ("n_channels", int(m.channels.len())),
        ])
    };
    let routes = Value::List(
        CHEMISTRY_ROUTES
            .iter()
            .map(|(k, a, b)| dict(vec![("item", s(*k)), ("route", s(*a)), ("barrier", s(*b))]))
            .collect(),
    );
    dict(vec![
        ("registry_pin", s(abep_chem::registry::ICP_CHEM_PINNED_SHA256)),
        ("AIR_PRIMARY", mode(&reg.air)),
        ("XE_CONTINGENCY", mode(&reg.xe)),
        ("routes_2026_10_08", routes),
        (
            "admission_verdict",
            s("AIR_PRIMARY and XE_CONTINGENCY stay NOT_ADMITTED: neither has its tier-1 tables, its final CA verdicts \
               or (XE) a registry-backed set path; no table is built in this lane (GOVERNANCE)"),
        ),
    ])
}

fn verify_value(repo: &Path) -> AssessResult<Value> {
    let rd = |rel: &str| -> AssessResult<J> {
        let b = std::fs::read(repo.join(rel)).map_err(|e| me(format!("{rel}: {e}")))?;
        serde_json::from_slice(&b).map_err(|e| me(format!("{rel}: {e}")))
    };
    let a = rd(VER25_REL)?;
    let sr = rd(SOURCE_READS_REL)?;
    let items = sr.get("items").and_then(J::as_array).ok_or_else(|| me("source reads items"))?.iter().map(|x| {
        format!(
            "{}: {}",
            x.get("verify_item").and_then(J::as_str).unwrap_or(""),
            x.get("status").and_then(J::as_str).unwrap_or("")
        )
    });
    let blocked =
        sr.get("still_blocked").and_then(J::as_array).ok_or_else(|| me("source reads still_blocked"))?.iter().map(
            |x| {
                format!(
                    "{}: {}",
                    x.get("verify_item").and_then(J::as_str).unwrap_or(""),
                    x.get("barrier").and_then(J::as_str).unwrap_or("")
                )
            },
        );
    Ok(dict(vec![
        ("cleared", sl([format!("{}: CLEARED ({VER25_REL})", a.get("verify_item").and_then(J::as_str).unwrap_or(""))])),
        ("recorded_not_cleared", sl(items)),
        ("still_blocked", sl(blocked)),
        ("np_icp_verification_status", s("IMPLEMENTED_UNVERIFIED (admission-rule item 4 not met)")),
    ]))
}

/// The closure-state rule of the registration, applied literally.
pub fn closure_state(
    flight_conservation_feasible: bool,
    flight_converged_meets_requirement: bool,
    validated_and_hc05_met: bool,
) -> &'static str {
    if !flight_conservation_feasible {
        STATE_DCR
    } else if validated_and_hc05_met {
        STATE_CLOSED
    } else if flight_converged_meets_requirement {
        STATE_FROZEN_EM
    } else {
        STATE_BLOCKED
    }
}

/// The full record (deterministic).
pub fn build(repo: &Path) -> AssessResult<Value> {
    let b = CaseBuilder::new(repo)?;
    let reg = b.registration().clone();
    let model = IcpModelV2::load(repo)?;
    let thr = Thresholds::load(&abep_config::ConfigPaths::repository(repo))?;
    let grid = b.grid()?;
    let mut ma = Dict::new();
    let mut refs: BTreeMap<ClosureMode, Value> = BTreeMap::new();
    for m in ClosureMode::ALL {
        let (rec, r) = model_mode(&model, &b, &grid, m)?;
        ma.insert(m.key(), rec);
        refs.insert(m, r);
    }
    // Inputs closed relative to the frozen M2 P-ICP-DBF1 codes of today (reference point, flight modes).
    let mut delta = Dict::new();
    for m in [ClosureMode::Air, ClosureMode::Xe] {
        let before = m2_codes(repo, m.key())?;
        let now: BTreeSet<String> = match refs.get(&m).and_then(|v| v.as_dict()).and_then(|d| d.get("reason_codes")) {
            Some(Value::List(l)) => l.iter().filter_map(|x| x.as_str().map(str::to_string)).collect(),
            _ => BTreeSet::new(),
        };
        delta.insert(
            m.key(),
            dict(vec![
                ("closed_by_registration", sl(before.difference(&now).cloned())),
                ("remaining", sl(before.intersection(&now).cloned())),
                ("new_in_closure_case", sl(now.difference(&before).cloned())),
            ]),
        );
    }
    let (bounds, analog, i_req) = bounds_value(&reg, &thr, b.cfg.icp.radius_m)?;
    // M-D: HC-05 at the reference point of each flight mode (capacity basis MODEL; I_d,max,H1 unregistered).
    let mut md = Dict::new();
    let mut flight_conv_meets = true;
    for m in [ClosureMode::Air, ClosureMode::Xe] {
        let rp = refs.get(&m).and_then(|v| v.as_dict()).cloned().unwrap_or_default();
        let ie_v = rp.get("I_e_cap_A").and_then(|v| match v {
            Value::Float(x) => Some(*x),
            _ => None,
        });
        let status = match rp.get("status").and_then(Value::as_str) {
            Some("CONVERGED") => IcpStatus::Converged,
            Some("OUT_OF_DOMAIN") => IcpStatus::OutOfDomain,
            Some("MODEL_ERROR") => IcpStatus::ModelError,
            Some("NOT_EVALUATED") => IcpStatus::NotEvaluated,
            _ => IcpStatus::IncompleteEvidence,
        };
        let reasons: Vec<String> = match rp.get("reason_codes") {
            Some(Value::List(l)) => l.iter().filter_map(|x| x.as_str().map(str::to_string)).collect(),
            _ => vec![],
        };
        let reqs = i_req.get(m.key()).cloned().unwrap_or_default();
        flight_conv_meets &= ie_v.is_some_and(|i| reqs.iter().all(|r| i >= *r)) && status.is_converged();
        let inputs = NeutralizationInputs {
            point_id: Some("REF-ICP-1".into()),
            capacity_basis: CapacityBasis::Model,
            i_e_cap: Current { value_a: ie_v, u_a: None, status, reasons },
            i_d_max_h1: None,
            validation_cell: None,
            margin_rule: None,
        };
        let necessary = Value::List(
            reqs.iter()
                .map(|r| {
                    dict(vec![
                        ("I_e_req_LB_A", f(*r)),
                        ("I_e_cap_A", ie_v.map_or(Value::Null, f)),
                        (
                            "status",
                            s(match ie_v {
                                Some(i) if i >= *r => "MET_AS_NECESSARY_CONDITION",
                                Some(_) => "NOT_MET_AS_NECESSARY_CONDITION",
                                None => "NOT_FORMED (I_e,cap withheld)",
                            }),
                        ),
                    ])
                })
                .collect(),
        );
        md.insert(
            m.key(),
            dict(vec![
                ("hc05", hc05(&thr, Some(&inputs))?),
                ("neutralization_quantities", neutralization_quantities(Some(&inputs))),
                ("brief_form_I_e_cap_over_I_beam", s("NOT_FORMED: reported as the necessary condition below")),
                ("necessary_condition_I_e_cap_ge_I_beam_LB", necessary),
                ("label", s("NECESSARY_CONDITION_NOT_A_GATE")),
            ]),
        );
    }
    md.insert("GNG-ICP-01", gng_icp_01(repo)?);
    let feasible = match &bounds {
        Value::Dict(d) => match d.get("per_mode") {
            Some(Value::Dict(pm)) => pm.values().all(|v| match v.as_dict().and_then(|x| x.get("thrust_points")) {
                Some(Value::List(l)) => l.iter().all(|p| {
                    matches!(
                        p.as_dict().and_then(|x| x.get("conservation_feasible_in_envelope")),
                        Some(Value::Bool(true))
                    )
                }),
                _ => false,
            }),
            _ => false,
        },
        _ => false,
    };
    let state = closure_state(feasible, flight_conv_meets, false);
    let mut blockers = BTreeSet::new();
    for m in [ClosureMode::Air, ClosureMode::Xe] {
        if let Some(Value::List(l)) = refs.get(&m).and_then(|v| v.as_dict()).and_then(|d| d.get("reason_codes")) {
            for c in l.iter().filter_map(Value::as_str) {
                blockers.insert(format!("{}: {c}", m.key()));
            }
        }
    }
    blockers
        .insert("BOTH: I_d,max,H1 not registered (HALL_NUMERICS_NOT_CONVERGED, A9.36) -> HC-05 NOT_EVALUATED".into());
    blockers
        .insert("BOTH: no VALIDATED_BENCH cell (P1 bench / P2 impedance map) -> HC-05 NOT_EVALUATED (AS-02)".into());
    blockers.insert(
        "BOTH: CFG-FLIGHT-HALL-ON NOT_EVALUATED (CPL-HALL-ON-v1 gate: credible Hall set EMPTY, HI-04..HI-08)".into(),
    );
    let prov = dict(vec![
        ("registration", s(format!("{REG_REL} (sha256 {REG_SHA256}; lock {LOCK_SHA256})"))),
        ("np_icp_v2_lock", s(abep_icp::v2::PREREG_LOCK_V2_SHA256)),
        ("dbf1_lock", s(abep_config::baseline::DBF1_LOCK_SHA256)),
        ("dbf1_config", s(abep_config::baseline::DBF1_CONFIG_SHA256)),
        ("icp_chem_pinned", s(abep_chem::registry::ICP_CHEM_PINNED_SHA256)),
        ("m2_record", s(format!("{M2_REL} (sha256 {M2_SHA256})"))),
        ("thresholds_manifest", s(thr.manifest_sha256.clone())),
        ("producer", s("abep-assess closure_icp (bin abep-assess-icp-closure)")),
    ]);
    Ok(dict(vec![
        ("schema", s(SCHEMA)),
        ("id", s("ICP-CLOSURE-v1")),
        ("item", s("A9.38 Priority 4: RF/ICP neutralizer closure (closure board P4; DBF1-BD-06)")),
        ("lane", s("L-ICP-CLOSURE")),
        ("provenance", prov),
        (
            "labels",
            sl([
                "NP_ICP_V2_IMPLEMENTED_UNVERIFIED".to_string(),
                "NOT_VALIDATED".to_string(),
                "ASSUMED_GEOMETRIC_TUBE".to_string(),
                "CFG-CAP-OFF".to_string(),
                "CM-ABS_PARAMETRIC_ABSORBED_POWER".to_string(),
            ]),
        ),
        ("model_evaluation_M_A", Value::Dict(ma)),
        ("inputs_vs_m2_p_icp_dbf1", Value::Dict(delta)),
        ("bounds_M_B", bounds),
        ("analog_M_C", analog),
        ("neutralization_M_D", Value::Dict(md)),
        ("chemistry_admission", chemistry_value(&model)),
        ("verify_items", verify_value(repo)?),
        (
            "closure",
            dict(vec![
                ("item", s("P4")),
                ("state", s(state)),
                ("rule", s("ICP-CLOSURE-REG-v1 closure_state_rule, applied literally; M-C never changes the state")),
                ("conservation_feasible_in_frozen_envelope", Value::Bool(feasible)),
                ("I_e_cap_status", s("INCOMPLETE_EVIDENCE in every mode (model withheld; see model_evaluation_M_A)")),
                (
                    "M_n_status",
                    s("NOT_EVALUATED (HC-05): I_e,cap withheld, I_d,max,H1 not registered, no validated cell"),
                ),
                ("GNG-ICP-01", s("NOT_EVALUATED (criteria PENDING_OWNER_ACCEPTANCE)")),
                ("HC-05", s("NOT_EVALUATED")),
                ("blockers", sl(blockers)),
            ]),
        ),
    ]))
}

/// The record text: the repository's Python-compatible JSON writer, indent 1, trailing newline.
pub fn render(v: &Value) -> AssessResult<String> {
    let mut out =
        abep_types::pyjson::dumps(v, &DumpOptions { indent: Some(1), ensure_ascii: false, ..Default::default() })?;
    out.push('\n');
    Ok(out)
}

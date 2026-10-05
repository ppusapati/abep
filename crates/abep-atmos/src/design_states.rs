//! Design-state set v2 of the orbit atmosphere (`atmosphere_orbit.design_states_v2`, `load_design_states`, frozen-data
//! part of `check`; A9.14 S9.8 OD3, A9.17 ORBIT broad envelope).
//!
//! The Rust derivation reproduces the frozen file `atmosphere_msis21_orbit_v1_design_states_v2.json`, which stays the
//! production design-state set (never regenerated, CLAUDE.md rule 1).

use crate::orbit::{OrbitAtmosphere, OrbitState};
use crate::pyfloat::{py_format_g, py_format_plus_4f, py_round6};
use crate::weights::{axis_weights, Axis};
use abep_data::design_states::{read_design_states_file, DesignStatesFile};
use abep_data::json::{compare_documents, Comparison, OValue};
use abep_data::orbit_v1::{
    self, ALT_KM, DATASET_ID, DESIGN_V1_FILE, DESIGN_V2_FILE, DOY, LAT_DEG, LEGACY_CSV_FILE, LON_DEG, LST_H,
    NOMINAL_SCENARIO, N_OUT, SCENARIOS, SHAPE,
};
use abep_data::pins::FrozenPins;
use abep_data::{data_path, data_rel, gz, table};
use abep_provenance::{read_bytes, sha256_hex};
use abep_types::{AbepError, AbepResult};
use serde::Serialize;
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

pub const DESIGN_V2_ID: &str = "atmosphere_msis21_orbit_v1_design_states_v2";
pub const DESIGN_V2_COMMAND: &str = "python -m abep_sim.atmosphere_orbit design-states-v2";
/// Re-derivation tolerance of the frozen design-state v2 file (`atmosphere_orbit.DESIGN_V2_REL_TOL`, A9.17 CI
/// repair): float64 round-off scale; never widened to absorb a selection or label change.
pub const DESIGN_V2_REL_TOL: f64 = 1e-12;
pub const V2_LAT_STEP_DEG: f64 = 1.0;
pub const FINE_LAT_STEP_DEG: f64 = 0.25;
pub const EXTREMA_QUANTITIES: [&str; 5] = ["rho_kg_m3", "x_O", "x_N2", "x_O2", "T_K"];

const A9_14_JSON: &str = "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json";
const A9_14_SHA256: &str = "c6c00b7fda6f220d299f5101d7181199507708684ea195ebcd3e5f54ffc4f62c";
const A9_17_JSON: &str = "docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json";
const A9_17_SHA256: &str = "9fd77c95c2f3142bb3e2faf68145e1225a29b307d22f86bf93a8cd562914c3ad";
const A9_17_MD: &str = "docs/decisions/OD_2026_10_01_A9_17_DATA_ARTIFACT_OWNER_DECISIONS.md";
const A9_17_MD_SHA256: &str = "540212c0c8862528e549555244f0fd39f8f9c9272f84dfb450bfef9dc54eba13";
const A9_17_ORBIT_QUOTE: &str =
    "Keep the atmosphere/design-state envelope broad enough until DRDO, the spacecraft ICD, \
or the PDR mission definition supplies the real inclination and LTAN.";
const SUPERSEDES_RELATION: &str = "v1 is kept immutable (CLAUDE.md rule 1; A9.17 WINDS keeps v1 immutable). Its \
candidate pool is bounded at |lat| <= reachable_lat_max_deg() (~83.75 deg) of the CODE_DEFAULT SSO family, so it does \
not cover inclinations between ~83.75 and ~96.25 deg or polar orbits; v2 is the broad-envelope set for new use";
/// `inspect.cleandoc(design_states_v2.__doc__)`.
pub const RULE: &str = "S9.8 design-state set v2 (A9.17 ORBIT broad envelope), derived from the frozen dataset only.

Candidate pool, for each scenario x altitude node: every doy, longitude and local-time grid node x every integer
geodetic latitude -90..90 deg (V2_LAT_DEG; contains all 19 latitude nodes, poles included; off-node latitudes are
evaluated with the accessor's latitude interpolation and carry its recorded error). There is no latitude bound: the
pool does not depend on mission_env.sso_inclination_deg or on any inclination / LTAN, so it covers every inclination
0-180 deg and every LTAN (inclination and LTAN are TBD from the official mission ICD; the 96.3 deg / dawn-dusk
mission_env orbit is CODE_DEFAULT / PARAMETRIC and is not used here). The measured effect of a finer latitude step
on the extrema is recorded under lat_refinement_sensitivity.
Selection rule (as v1): for every scenario x altitude node, NOMINAL (state of median density), the max/min of rho,
x_O, x_N2, x_O2, T, and LST_PEAK / LST_TROUGH (median-density state at the local time whose lat/lon/season-mean
density is highest / lowest); envelope extrema over all scenarios and altitudes. The mission nominal scenario is
ECSS long-term moderate. Identical states are merged with all their labels.";

/// One selected design state (state fields, then labels, state_id, required, nominal_mission_scenario).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct DesignStateOut {
    #[serde(flatten)]
    pub state: OrbitState,
    pub labels: Vec<String>,
    pub state_id: String,
    pub required: bool,
    pub nominal_mission_scenario: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Extrema {
    pub rho_kg_m3: f64,
    #[serde(rename = "x_O")]
    pub x_o: f64,
    #[serde(rename = "x_N2")]
    pub x_n2: f64,
    #[serde(rename = "x_O2")]
    pub x_o2: f64,
    #[serde(rename = "T_K")]
    pub t_k: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LatRefinement {
    pub fine_step_deg: f64,
    pub max_abs_rel_change_of_extrema: Extrema,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct OrbitBasis {
    pub status: &'static str,
    pub requirement_input: bool,
    pub inclination_deg: &'static str,
    pub local_time: &'static str,
    pub code_default_orbit: &'static str,
    pub real_orbit: &'static str,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Supersedes {
    pub file: &'static str,
    pub sha256: Option<String>,
    pub relation: &'static str,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct AuthorityRef {
    pub path: &'static str,
    pub sha256: &'static str,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Verbatim {
    pub path: &'static str,
    pub sha256: &'static str,
    pub quote: &'static str,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct OrbitAuthority {
    pub path: &'static str,
    pub sha256: &'static str,
    pub decision_key: &'static str,
    pub answer: &'static str,
    pub verbatim: Verbatim,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Authority {
    #[serde(rename = "A9.14 S9.8 OD3")]
    pub a9_14: AuthorityRef,
    #[serde(rename = "A9.17 ORBIT")]
    pub a9_17: OrbitAuthority,
}

/// The `design_states_v2()` document (field order = the reference).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct DesignStatesV2 {
    pub design_state_set_id: &'static str,
    pub version: &'static str,
    pub dataset_id: &'static str,
    pub dataset_sha256: String,
    pub latitude_band_deg: [f64; 2],
    pub latitude_pool_step_deg: f64,
    pub lat_refinement_sensitivity: LatRefinement,
    pub nominal_scenario: &'static str,
    pub orbit_basis: OrbitBasis,
    pub supersedes: Supersedes,
    pub authority: Authority,
    pub producer: &'static str,
    pub rule: &'static str,
    pub n_states: u64,
    pub states: Vec<DesignStateOut>,
}

/// Latitudes -90 .. 90 with `step` (np.arange(-90, 90 + step / 2, step)).
fn lat_pool(step: f64) -> Vec<f64> {
    let n = (180.0 / step).round() as usize + 1;
    (0..n).map(|i| -90.0 + i as f64 * step).collect()
}

/// Candidate pool of one scenario x altitude node (`_pool_arrays`): every doy / lon / LST node x `lats`; pool order
/// doy, lon, LST, lat (lat fastest).
struct Pool {
    rho: Vec<f64>,
    t_k: Vec<f64>,
    x_o: Vec<f64>,
    x_n2: Vec<f64>,
    x_o2: Vec<f64>,
    n_lat: usize,
}

impl Pool {
    fn quantity(&self, q: &str) -> &[f64] {
        match q {
            "rho_kg_m3" => &self.rho,
            "T_K" => &self.t_k,
            "x_O" => &self.x_o,
            "x_N2" => &self.x_n2,
            "x_O2" => &self.x_o2,
            _ => unreachable!("registered extrema quantity"),
        }
    }
    /// (i_doy, i_lon, i_lst, i_lat) of pool index p.
    fn index(&self, p: usize) -> (usize, usize, usize, usize) {
        let i_lat = p % self.n_lat;
        let q = p / self.n_lat;
        (q / 48, (q / 8) % 6, q % 8, i_lat)
    }
}

fn pool(orbit: &OrbitAtmosphere, si: usize, ia: usize, lats: &[f64]) -> Pool {
    let lg = &orbit.log_grid[si];
    let weights: Vec<Vec<f64>> = lats.iter().map(|x| axis_weights(Axis::Lat, *x)).collect();
    let n = SHAPE[0] * SHAPE[3] * SHAPE[4] * lats.len();
    let mut p = Pool {
        rho: Vec::with_capacity(n),
        t_k: Vec::with_capacity(n),
        x_o: Vec::with_capacity(n),
        x_n2: Vec::with_capacity(n),
        x_o2: Vec::with_capacity(n),
        n_lat: lats.len(),
    };
    let mut v = [0.0; N_OUT];
    for d in 0..SHAPE[0] {
        for o in 0..SHAPE[3] {
            for t in 0..SHAPE[4] {
                for w in &weights {
                    let mut acc = [0.0; N_OUT];
                    for (l, wl) in w.iter().enumerate() {
                        if *wl == 0.0 {
                            continue;
                        }
                        let off = crate::orbit::node_offset(d, ia, l, o, t);
                        for c in 0..N_OUT {
                            acc[c] += wl * lg[off + c];
                        }
                    }
                    for c in 0..N_OUT {
                        v[c] = acc[c].exp();
                    }
                    let ntot = v[1] + v[2] + v[3] + v[4] + v[5] + v[6];
                    p.rho.push(v[0]);
                    p.t_k.push(v[7]);
                    p.x_o.push(v[3] / ntot);
                    p.x_n2.push(v[1] / ntot);
                    p.x_o2.push(v[2] / ntot);
                }
            }
        }
    }
    p
}

fn argmax(v: &[f64]) -> usize {
    let mut best = 0;
    for (i, x) in v.iter().enumerate() {
        if *x > v[best] {
            best = i;
        }
    }
    best
}

fn argmin(v: &[f64]) -> usize {
    let mut best = 0;
    for (i, x) in v.iter().enumerate() {
        if *x < v[best] {
            best = i;
        }
    }
    best
}

/// Stable ascending order of `idx` by `v`.
fn stable_sorted(mut idx: Vec<usize>, v: &[f64]) -> Vec<usize> {
    idx.sort_by(|a, b| v[*a].total_cmp(&v[*b]));
    idx
}

type Key = (String, u64, u64, u64, u64, u64);

struct Selection {
    states: HashMap<Key, DesignStateOut>,
}

impl Selection {
    fn add(&mut self, st: OrbitState, label: String) {
        let lat = py_round6(st.lat_deg);
        let key: Key = (
            st.scenario.clone(),
            st.alt_km.to_bits(),
            lat.to_bits(),
            st.lst_h.to_bits(),
            st.lon_deg.to_bits(),
            st.doy.to_bits(),
        );
        let entry = self.states.entry(key).or_insert_with(|| {
            let state_id = format!(
                "ds2:{}:alt{}:lat{}:lst{}:lon{}:doy{}",
                st.scenario,
                py_format_g(st.alt_km),
                py_format_plus_4f(lat),
                py_format_g(st.lst_h),
                py_format_g(st.lon_deg),
                py_format_g(st.doy)
            );
            DesignStateOut { state: st, labels: Vec::new(), state_id, required: false, nominal_mission_scenario: false }
        });
        if !entry.labels.contains(&label) {
            entry.labels.push(label);
        }
    }
}

/// `design_states_v2()`: the S9.8 design-state set v2 derived from the frozen dataset only.
pub fn design_states_v2(orbit: &OrbitAtmosphere) -> AbepResult<DesignStatesV2> {
    let lats = lat_pool(V2_LAT_STEP_DEG);
    let fine = lat_pool(FINE_LAT_STEP_DEG);
    let mut sel = Selection { states: HashMap::new() };
    let mut env: BTreeMap<(String, String), (f64, OrbitState)> = BTreeMap::new();
    let mut worst = [0.0_f64; 5];
    for (si, sc) in SCENARIOS.iter().enumerate() {
        for (ia, alt) in ALT_KM.iter().enumerate() {
            let p = pool(orbit, si, ia, &lats);
            let mk = |k: usize| -> AbepResult<OrbitState> {
                let (i_doy, i_lon, i_lst, i_lat) = p.index(k);
                let lat = lats[i_lat];
                match LAT_DEG.iter().position(|v| *v == lat) {
                    Some(il) => orbit.node_state(i_doy, ia, il, i_lon, i_lst, sc.id),
                    None => orbit.state(ALT_KM[ia], lat, LST_H[i_lst], LON_DEG[i_lon], DOY[i_doy], sc.id),
                }
            };
            let tag = |name: &str| format!("{name}[{},{}km]", sc.id, py_format_g(*alt));
            let order = stable_sorted((0..p.rho.len()).collect(), &p.rho);
            sel.add(mk(order[order.len() / 2])?, tag("NOMINAL_MEDIAN_RHO"));
            for q in EXTREMA_QUANTITIES {
                let vals = p.quantity(q);
                for (kind, k) in [("MAX", argmax(vals)), ("MIN", argmin(vals))] {
                    let st = mk(k)?;
                    sel.add(st.clone(), tag(&format!("{kind}_{q}")));
                    let key = (kind.to_string(), q.to_string());
                    let better = match env.get(&key) {
                        None => true,
                        Some((cur, _)) => (kind == "MAX" && vals[k] > *cur) || (kind == "MIN" && vals[k] < *cur),
                    };
                    if better {
                        env.insert(key, (vals[k], st));
                    }
                }
            }
            let mut lm: Vec<(f64, f64)> = Vec::with_capacity(LST_H.len());
            for (it, h) in LST_H.iter().enumerate() {
                let sub: Vec<f64> = (0..p.rho.len()).filter(|i| p.index(*i).2 == it).map(|i| p.rho[i].ln()).collect();
                lm.push((*h, sub.iter().sum::<f64>() / sub.len() as f64));
            }
            let peak = lm.iter().fold(lm[0], |b, x| if x.1 > b.1 { *x } else { b }).0;
            let trough = lm.iter().fold(lm[0], |b, x| if x.1 < b.1 { *x } else { b }).0;
            for (name, lst_sel) in [("LST_PEAK", peak), ("LST_TROUGH", trough)] {
                let it = LST_H.iter().position(|h| *h == lst_sel).expect("LST node");
                let sub = stable_sorted((0..p.rho.len()).filter(|i| p.index(*i).2 == it).collect(), &p.rho);
                sel.add(mk(sub[sub.len() / 2])?, tag(name));
            }
            let f = pool(orbit, si, ia, &fine);
            for (qi, q) in EXTREMA_QUANTITIES.iter().enumerate() {
                let (a, b) = (p.quantity(q), f.quantity(q));
                let amax = a.iter().copied().fold(f64::NEG_INFINITY, f64::max);
                let bmax = b.iter().copied().fold(f64::NEG_INFINITY, f64::max);
                let amin = a.iter().copied().fold(f64::INFINITY, f64::min);
                let bmin = b.iter().copied().fold(f64::INFINITY, f64::min);
                worst[qi] = worst[qi].max((bmax / amax - 1.0).abs()).max((bmin / amin - 1.0).abs());
            }
        }
    }
    for ((kind, q), (_, st)) in env {
        sel.add(st, format!("ENVELOPE_{kind}_{q}"));
    }
    let mut states: Vec<DesignStateOut> = sel.states.into_values().collect();
    states.sort_by(|a, b| a.state_id.cmp(&b.state_id));
    for s in &mut states {
        s.required = true;
        s.nominal_mission_scenario = s.state.scenario == NOMINAL_SCENARIO;
    }
    let r3 = |v: f64| -> f64 { format!("{v:.3e}").parse().expect("formatted float") };
    Ok(DesignStatesV2 {
        design_state_set_id: DESIGN_V2_ID,
        version: "v2",
        dataset_id: DATASET_ID,
        dataset_sha256: orbit.data.meta.sha256.clone(),
        latitude_band_deg: [LAT_DEG[0], LAT_DEG[18]],
        latitude_pool_step_deg: V2_LAT_STEP_DEG,
        lat_refinement_sensitivity: LatRefinement {
            fine_step_deg: FINE_LAT_STEP_DEG,
            max_abs_rel_change_of_extrema: Extrema {
                rho_kg_m3: r3(worst[0]),
                x_o: r3(worst[1]),
                x_n2: r3(worst[2]),
                x_o2: r3(worst[3]),
                t_k: r3(worst[4]),
            },
        },
        nominal_scenario: NOMINAL_SCENARIO,
        orbit_basis: OrbitBasis {
            status: "BROAD_ENVELOPE (inclination / LTAN TBD from the official mission ICD)",
            requirement_input: false,
            inclination_deg: "any (0-180): every geodetic latitude -90..90 deg (1 deg step) is in the pool",
            local_time: "all local times (LTAN-agnostic)",
            code_default_orbit: "mission_env 96.3 deg / dawn-dusk is CODE_DEFAULT / PARAMETRIC; not used to bound \
                                 this set",
            real_orbit: "TBD from DRDO / spacecraft ICD / PDR mission definition; once supplied, a new dataset / \
                         design-state version narrows the envelope",
        },
        supersedes: Supersedes {
            file: DESIGN_V1_FILE,
            sha256: orbit.data.meta.design_states_file.as_ref().and_then(|r| r.sha256.clone()),
            relation: SUPERSEDES_RELATION,
        },
        authority: Authority {
            a9_14: AuthorityRef { path: A9_14_JSON, sha256: A9_14_SHA256 },
            a9_17: OrbitAuthority {
                path: A9_17_JSON,
                sha256: A9_17_SHA256,
                decision_key: "ORBIT",
                answer: "ORBIT_INCLINATION_LTAN_TBD_FROM_OFFICIAL_MISSION_ICD",
                verbatim: Verbatim { path: A9_17_MD, sha256: A9_17_MD_SHA256, quote: A9_17_ORBIT_QUOTE },
            },
        },
        producer: DESIGN_V2_COMMAND,
        rule: RULE,
        n_states: states.len() as u64,
        states,
    })
}

/// The document as an order-preserving JSON value (for the reference's structural comparison).
pub fn to_ovalue(doc: &DesignStatesV2) -> AbepResult<OValue> {
    let text = serde_json::to_vec(doc).map_err(|e| AbepError::Model { message: e.to_string() })?;
    OValue::parse(&text, "design_states_v2()")
}

/// `atmosphere_orbit.load_design_states(version)` (v2 current set, v1 immutable set) on the loaded dataset.
pub fn load_design_states(orbit: &OrbitAtmosphere, repo_root: &Path, version: &str) -> AbepResult<DesignStatesFile> {
    read_design_states_file(repo_root, &orbit.pins, &orbit.data.meta, version)
}

/// Result of [`check`] (`atmosphere_orbit.check()` frozen-data part; DIV-D-03).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CheckReport {
    pub ok: bool,
    pub problems: Vec<String>,
    pub notes: Vec<String>,
    pub subset_rows: usize,
    pub csv_sha256: String,
    pub container_sha256: String,
    pub producer_rerun: &'static str,
    pub design_v2_comparison: Option<DesignV2Comparison>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct DesignV2Comparison {
    pub ok: bool,
    pub exact_mismatches: Vec<String>,
    pub floats_differing: usize,
    pub max_abs_rel_diff: f64,
    pub rel_tol: f64,
}

impl From<Comparison> for DesignV2Comparison {
    fn from(c: Comparison) -> Self {
        DesignV2Comparison {
            ok: c.ok,
            exact_mismatches: c.exact_mismatches.into_iter().take(5).collect(),
            floats_differing: c.floats_differing,
            max_abs_rel_diff: c.max_abs_rel_diff,
            rel_tol: c.rel_tol,
        }
    }
}

const COLUMNS_HEADER: usize = 0;

/// Frozen-data verification of the orbit dataset: the configuration pins and the sidecar must load (else
/// MODEL_ERROR); data-file differences are reported as problems (`ok = false`). The pymsis producer re-run, the gzip
/// re-encoding identity and the descriptive-metadata equality of the reference are not ported (DIV-D-03).
pub fn check(repo_root: &Path) -> AbepResult<CheckReport> {
    let pins = FrozenPins::load(repo_root)?;
    if !(data_path(repo_root, orbit_v1::GZ_FILE).exists() && data_path(repo_root, orbit_v1::JSON_FILE).exists()) {
        return Err(orbit_v1::missing_data_error(repo_root));
    }
    let (meta, _) = orbit_v1::load_meta(repo_root, &pins)?;
    let gz_rel = data_rel(orbit_v1::GZ_FILE);
    let gzb = read_bytes(&data_path(repo_root, orbit_v1::GZ_FILE))?;
    let raw = gz::gunzip(&gzb, &gz_rel)?;
    let mut problems = Vec::new();
    let notes = vec!["producer re-run, rho composition regression, gzip re-encoding identity and descriptive \
                      metadata equality are not ported (DIV-D-03)"
        .to_string()];
    let sha = sha256_hex(&raw);
    if sha != meta.sha256 {
        problems.push(format!("csv sha256 {sha} != metadata {}", meta.sha256));
    }
    let gz_sha = sha256_hex(&gzb);
    if gz_sha != meta.container.sha256 || Some(gzb.len() as u64) != meta.container.bytes {
        problems.push(format!("container sha256/bytes {gz_sha}/{} != metadata", gzb.len()));
    }
    if pins.pin(&gz_rel)? != gz_sha {
        problems.push("container sha256 differs from the model-set pin".into());
    }
    if raw.len() as u64 != meta.bytes {
        problems.push("uncompressed CSV byte count differs from the metadata".into());
    }
    if data_path(repo_root, LEGACY_CSV_FILE).exists() {
        problems.push("legacy uncompressed copy present (one canonical .csv.gz only)".into());
    }
    let lines = table::lines(&raw, &gz_rel)?;
    if lines.get(COLUMNS_HEADER).map(|h| h.split(',').ne(orbit_v1::COLUMNS.iter().copied())).unwrap_or(true) {
        problems.push("header mismatch".into());
    }
    let body = lines.get(1..).unwrap_or(&[]);
    if body.len() as u64 != meta.row_count {
        problems.push("row count mismatch".into());
    }
    let stride = meta.check_subset.stride.max(1);
    let stored: Vec<&str> = body.iter().step_by(stride).copied().collect();
    let sub = stored.join("\n") + "\n";
    if sha256_hex(sub.as_bytes()) != meta.check_subset.sha256 {
        problems.push("stored check-subset hash mismatch".into());
    }
    let file_sha = |f: &str| -> String {
        let p = data_path(repo_root, f);
        sha256_hex(&if p.exists() { read_bytes(&p).unwrap_or_default() } else { Vec::new() })
    };
    let v1_sha = file_sha(DESIGN_V1_FILE);
    if Some(&v1_sha) != meta.design_states_file.as_ref().and_then(|r| r.sha256.as_ref()) {
        problems.push("design-states file hash differs from the metadata".into());
    } else if pins.pin(&data_rel(DESIGN_V1_FILE))? != v1_sha {
        problems.push("design-states file hash differs from the model-set pin".into());
    }
    let v2_sha = file_sha(DESIGN_V2_FILE);
    let v2_rec = meta.design_states_file_v2();
    let v2_rec_sha = v2_rec.and_then(|r| r.get("sha256")).and_then(OValue::as_str);
    let mut comparison = None;
    if Some(v2_sha.as_str()) != v2_rec_sha {
        problems.push("design-states v2 file hash differs from the metadata (or file / record missing)".into());
    } else if pins.pin(&data_rel(DESIGN_V2_FILE))? != v2_sha || pins.design_state_set_ref.sha256 != v2_sha {
        problems.push("design-states v2 file hash differs from the configuration pins".into());
    } else if problems.is_empty() {
        let orbit = OrbitAtmosphere::load(repo_root)?;
        let fresh = to_ovalue(&design_states_v2(&orbit)?)?;
        let frozen = OValue::parse(&read_bytes(&data_path(repo_root, DESIGN_V2_FILE))?, DESIGN_V2_FILE)?;
        let c = compare_documents(&frozen, &fresh, DESIGN_V2_REL_TOL);
        if !c.ok {
            problems.push(format!(
                "design states v2 do not reproduce from the frozen dataset (exact mismatches: {:?}; max float relative \
                 difference {:.3e} vs DESIGN_V2_REL_TOL {DESIGN_V2_REL_TOL})",
                c.exact_mismatches.iter().take(3).collect::<Vec<_>>(),
                c.max_abs_rel_diff
            ));
        }
        comparison = Some(c.into());
    }
    if let Some(rec) = v2_rec {
        let s = |k: &str| rec.get(k).and_then(OValue::as_str);
        let auth = rec.get("authority");
        let a = |k: &str| auth.and_then(|x| x.get(k)).and_then(OValue::as_str);
        let expected = s("file") == Some(DESIGN_V2_FILE)
            && s("producer") == Some("design_states_v2() on this dataset (A9.14 S9.8 OD3; A9.17 ORBIT broad envelope)")
            && s("command") == Some(DESIGN_V2_COMMAND)
            && s("status") == Some("CURRENT design-state set (broad envelope)")
            && a("path") == Some(A9_17_JSON)
            && a("sha256") == Some(A9_17_SHA256)
            && a("decision_key") == Some("ORBIT")
            && matches!(rec, OValue::Object(m) if m.len() == 6)
            && matches!(auth, Some(OValue::Object(m)) if m.len() == 3);
        if !expected {
            problems.push("design_states_file_v2 record differs from the module definition".into());
        }
    } else {
        problems.push("design_states_file_v2 record differs from the module definition".into());
    }
    Ok(CheckReport {
        ok: problems.is_empty(),
        problems,
        notes,
        subset_rows: stored.len(),
        csv_sha256: sha,
        container_sha256: gz_sha,
        producer_rerun: "NOT_RUN (no live NRLMSIS in the Rust production path, A9.29 sec. 6)",
        design_v2_comparison: comparison,
    })
}

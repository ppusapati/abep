//! Parity runner of the ES-2 environment contracts: reads one JSON request from stdin and writes the Rust results to
//! stdout (`scripts/rust_migration/es2_env_parity.py` drives it).
//!
//! Request: `{"repo_root": "...", "requests": [{"id": "...", "entry": "...", "args": {...}}]}`; numbers may be given as
//! the strings "NaN", "+inf", "-inf". Result per request: `{"id", "entry", "status", "value", "error"}` with status
//! EVALUATED or the fail-closed status of the error. Per-request wall-clock times go to stderr (performance is reported,
//! never a criterion), so stdout stays byte-deterministic.

use abep_atmos::design_state_set::{required_states, select};
use abep_atmos::design_states::{self, check, design_states_v2, load_design_states, DESIGN_V2_REL_TOL};
use abep_atmos::execution::{self, Environment};
use abep_atmos::mission_env_kernel::{sso_inclination_deg, Spacecraft, J2, OMEGA_E};
use abep_atmos::msis21::{atmosphere, orbital_velocity, Msis21Frozen, Solar};
use abep_atmos::orbit::{OrbitAtmosphere, OrbitRequest};
use abep_atmos::wind::WindAtmosphere;
use abep_data::design_states::DesignStateSet;
use abep_data::json::{compare_documents, OValue};
use abep_data::orbit_v1::{self, ALT_KM, DOY, LAT_DEG, LON_DEG, LST_H, SCENARIOS};
use abep_data::pins::FrozenPins;
use abep_provenance::read_bytes;
use abep_types::constants::{AMU, E_CHARGE, G0, K_B, MU_EARTH, M_N2, M_O, M_O2, M_XE, R_EARTH};
use abep_types::{AbepError, AbepResult};
use serde::Serialize;
use serde_json::{json, Value};
use std::io::Read;
use std::path::{Path, PathBuf};

fn num(v: &Value) -> Result<f64, String> {
    match v {
        Value::Number(n) => n.as_f64().ok_or_else(|| format!("{n} is not an f64")),
        Value::String(s) => match s.as_str() {
            "NaN" | "nan" => Ok(f64::NAN),
            "+inf" | "inf" => Ok(f64::INFINITY),
            "-inf" => Ok(f64::NEG_INFINITY),
            _ => Err(format!("{s:?} is not a number")),
        },
        _ => Err(format!("{v} is not a number")),
    }
}

fn arg<'a>(args: &'a Value, k: &str) -> Result<&'a Value, String> {
    args.get(k).ok_or_else(|| format!("missing argument {k}"))
}

fn state_args(args: &Value) -> Result<(f64, f64, f64, f64, f64, String), String> {
    let a = arg(args, "state")?.as_array().ok_or("state must be a list")?;
    if a.len() != 6 {
        return Err("state needs 6 values".into());
    }
    let s = a[5].as_str().ok_or("scenario must be a string")?.to_string();
    Ok((num(&a[0])?, num(&a[1])?, num(&a[2])?, num(&a[3])?, num(&a[4])?, s))
}

fn to_json<T: Serialize>(v: &T) -> String {
    serde_json::to_string(v).expect("serializable result")
}

enum Outcome {
    Value(String),
    Error(AbepError),
    Invalid(String),
}

impl From<AbepResult<String>> for Outcome {
    fn from(r: AbepResult<String>) -> Self {
        match r {
            Ok(v) => Outcome::Value(v),
            Err(e) => Outcome::Error(e),
        }
    }
}

struct Runner {
    root: PathBuf,
    msis: Option<AbepResult<Msis21Frozen>>,
    orbit: Option<AbepResult<OrbitAtmosphere>>,
    wind: Option<AbepResult<WindAtmosphere>>,
    set: Option<AbepResult<DesignStateSet>>,
}

impl Runner {
    fn msis(&mut self) -> AbepResult<&Msis21Frozen> {
        let root = self.root.clone();
        self.msis.get_or_insert_with(|| Msis21Frozen::load(&root)).as_ref().map_err(Clone::clone)
    }
    fn orbit(&mut self) -> AbepResult<&OrbitAtmosphere> {
        let root = self.root.clone();
        self.orbit.get_or_insert_with(|| OrbitAtmosphere::load(&root)).as_ref().map_err(Clone::clone)
    }
    fn wind(&mut self) -> AbepResult<(&OrbitAtmosphere, &WindAtmosphere)> {
        if self.wind.is_none() {
            let root = self.root.clone();
            let w = match self.orbit() {
                Ok(o) => WindAtmosphere::load(&root, o),
                Err(e) => Err(e),
            };
            self.wind = Some(w);
        }
        let w = self.wind.as_ref().expect("set above").as_ref().map_err(Clone::clone)?;
        let o = self.orbit.as_ref().expect("loaded").as_ref().map_err(Clone::clone)?;
        Ok((o, w))
    }
    fn set(&mut self) -> AbepResult<&DesignStateSet> {
        let root = self.root.clone();
        self.set
            .get_or_insert_with(|| FrozenPins::load(&root).and_then(|p| DesignStateSet::load(&root, &p)))
            .as_ref()
            .map_err(Clone::clone)
    }

    fn run(&mut self, entry: &str, args: &Value) -> Outcome {
        match self.dispatch(entry, args) {
            Ok(o) => o,
            Err(m) => Outcome::Invalid(m),
        }
    }

    fn dispatch(&mut self, entry: &str, args: &Value) -> Result<Outcome, String> {
        let root = self.root.clone();
        Ok(match entry {
            "constants" => Outcome::Value(to_json(&json!({
                "G0": G0, "E_CHARGE": E_CHARGE, "AMU": AMU, "K_B": K_B, "MU_EARTH": MU_EARTH, "R_EARTH": R_EARTH,
                "M_O": M_O, "M_N2": M_N2, "M_O2": M_O2, "M_XE": M_XE,
                "species_He": abep_types::constants::species_mass("He").map_err(|e| e.status().as_str()).err(),
            }))),
            "mission_env_constants" => Outcome::Value(to_json(&json!({"J2": J2, "OMEGA_E": OMEGA_E}))),
            "spacecraft_defaults" => Outcome::Value(to_json(&Spacecraft::default())),
            "sso_inclination_deg" => sso_inclination_deg(num(arg(args, "alt_km")?)?).map(|v| to_json(&v)).into(),
            "orbital_velocity" => orbital_velocity(num(arg(args, "alt_km")?)?).map(|v| to_json(&v)).into(),
            "msis21_load" => self
                .msis()
                .map(|m| {
                    to_json(&json!({"sha256_16": m.data.sha256_16, "csv_sha256": m.data.csv_sha256,
                                    "alt_km": m.data.alt_axis, "f107": m.data.f107_axis}))
                })
                .into(),
            "atmosphere" => {
                let alt = num(arg(args, "alt_km")?)?;
                let solar = match arg(args, "solar")? {
                    Value::String(s) if !matches!(s.as_str(), "NaN" | "+inf" | "-inf") => Solar::Label(s.clone()),
                    v => Solar::F107(num(v)?),
                };
                match self.msis() {
                    Ok(m) => atmosphere(m, alt, solar).map(|v| to_json(&v)).into(),
                    Err(e) => Outcome::Error(e),
                }
            }
            "orbit_load" => self
                .orbit()
                .map(|o| {
                    let grid = format!(
                        "{{\"alt_km\":{},\"lat_deg\":{},\"lst_h\":{},\"lon_deg\":{},\"doy\":{}}}",
                        to_json(&ALT_KM),
                        to_json(&LAT_DEG),
                        to_json(&LST_H),
                        to_json(&LON_DEG),
                        to_json(&DOY)
                    );
                    format!(
                        "{{\"dataset_sha256\":{},\"row_count\":{},\"shape\":{},\"scenario_order\":{},\"grid\":{grid},\
                         \"container_sha256\":{}}}",
                        to_json(&o.data.meta.sha256),
                        o.data.meta.row_count,
                        to_json(&orbit_v1::SHAPE),
                        to_json(&SCENARIOS.iter().map(|s| s.id).collect::<Vec<_>>()),
                        to_json(&o.data.container_sha256)
                    )
                })
                .into(),
            "orbit_state" => {
                let (alt, lat, lst, lon, doy, s) = state_args(args)?;
                match self.orbit() {
                    Ok(o) => o.state(alt, lat, lst, lon, doy, &s).map(|v| to_json(&v)).into(),
                    Err(e) => Outcome::Error(e),
                }
            }
            "orbit_node_state" => {
                let idx = arg(args, "idx")?.as_array().ok_or("idx must be a list")?;
                let idx: Vec<i64> = idx.iter().map(|v| v.as_i64().ok_or("index")).collect::<Result<_, _>>()?;
                let s = arg(args, "scenario")?.as_str().ok_or("scenario")?.to_string();
                match self.orbit() {
                    Ok(o) => {
                        if idx.len() != 5 || idx.iter().any(|i| *i < 0) {
                            Outcome::Error(AbepError::OutOfDomain { message: format!("node index {idx:?}") })
                        } else {
                            let u: Vec<usize> = idx.iter().map(|i| *i as usize).collect();
                            o.node_state(u[0], u[1], u[2], u[3], u[4], &s).map(|v| to_json(&v)).into()
                        }
                    }
                    Err(e) => Outcome::Error(e),
                }
            }
            "orbit_states" => {
                let scenario = arg(args, "scenario")?.as_str().ok_or("scenario")?.to_string();
                let req = OrbitRequest {
                    alt_km: num(arg(args, "alt_km")?)?,
                    inclination_deg: num(arg(args, "inclination_deg")?)?,
                    ltan_h: num(arg(args, "ltan_h")?)?,
                    scenario: &scenario,
                    doy: num(arg(args, "doy")?)?,
                    ut_start_h: num(arg(args, "ut_start_h")?)?,
                    n_samples: num(arg(args, "n_samples")?)?,
                };
                match self.orbit() {
                    Ok(o) => o.orbit_states(&req).map(|v| to_json(&v)).into(),
                    Err(e) => Outcome::Error(e),
                }
            }
            "wind_load" => self
                .wind()
                .map(|(_, w)| {
                    to_json(&json!({"sha256": w.data.sha256, "disturbance_sha256": w.data.disturbance_sha256}))
                })
                .into(),
            "wind" => {
                let (alt, lat, lst, lon, doy, s) = state_args(args)?;
                match self.wind() {
                    Ok((_, w)) => w.wind(alt, lat, lst, lon, doy, &s).map(|v| to_json(&v)).into(),
                    Err(e) => Outcome::Error(e),
                }
            }
            "state_v2" => {
                let (alt, lat, lst, lon, doy, s) = state_args(args)?;
                match self.wind() {
                    Ok((o, w)) => w.state(o, alt, lat, lst, lon, doy, &s).map(|v| to_json(&v)).into(),
                    Err(e) => Outcome::Error(e),
                }
            }
            "design_states_v2" => match self.orbit() {
                Ok(o) => (|| -> AbepResult<String> {
                    let doc = design_states_v2(o)?;
                    let fresh = design_states::to_ovalue(&doc)?;
                    let path = abep_data::data_path(&root, orbit_v1::DESIGN_V2_FILE);
                    let frozen = OValue::parse(&read_bytes(&path)?, orbit_v1::DESIGN_V2_FILE)?;
                    let c: design_states::DesignV2Comparison =
                        compare_documents(&frozen, &fresh, DESIGN_V2_REL_TOL).into();
                    Ok(format!("{{\"document\":{},\"frozen_comparison\":{}}}", to_json(&doc), to_json(&c)))
                })()
                .into(),
                Err(e) => Outcome::Error(e),
            },
            "load_design_states" => {
                let version = arg(args, "version")?.as_str().ok_or("version")?.to_string();
                match self.orbit() {
                    Ok(o) => load_design_states(o, &root, &version).map(|f| f.text.trim_end().to_string()).into(),
                    Err(e) => Outcome::Error(e),
                }
            }
            "design_state_set" => {
                let lookup: Vec<String> = arg(args, "lookup")?
                    .as_array()
                    .ok_or("lookup must be a list")?
                    .iter()
                    .map(|v| v.as_str().map(str::to_string).ok_or("lookup id"))
                    .collect::<Result<_, _>>()?;
                match self.set() {
                    Ok(set) => (|| -> AbepResult<String> {
                        let states = required_states(set)?;
                        let mut rows = Vec::new();
                        for s in &states {
                            rows.push(format!(
                                "{{\"state\":{},\"atm\":{},\"record\":{}}}",
                                to_json(s),
                                to_json(&s.atm()?),
                                to_json(&s.record())
                            ));
                        }
                        let ids: Vec<&str> = states.iter().map(|s| s.state_id.as_str()).collect();
                        let mut found: Vec<(String, bool)> = ids
                            .iter()
                            .map(|id| (id.to_string(), select(&states, id).is_some_and(|s| s.state_id == *id)))
                            .collect();
                        found.extend(lookup.iter().map(|id| (id.clone(), select(&states, id).is_some())));
                        Ok(format!(
                            "{{\"n_states\":{},\"ids\":{},\"states\":[{}],\"lookup\":{}}}",
                            set.n_states,
                            to_json(&ids),
                            rows.join(","),
                            to_json(&found)
                        ))
                    })()
                    .into(),
                    Err(e) => Outcome::Error(e),
                }
            }
            "execution" => Environment::load(&root).and_then(|env| execution::run(&env)).map(|r| to_json(&r)).into(),
            "check" => check(&root).map(|r| to_json(&r)).into(),
            other => return Err(format!("unknown entry {other:?}")),
        })
    }
}

fn governing(root: &Path) -> String {
    match FrozenPins::load(root) {
        Ok(p) => to_json(&json!({
            "config_manifest_sha256": p.config_manifest_sha256,
            "model_set_sha256": p.model_set_sha256,
            "design_state_set_ref_sha256": p.design_state_set_ref_sha256,
            "design_state_set_sha256": p.design_state_set_ref.sha256,
        })),
        Err(e) => to_json(&json!({"error": e.to_string()})),
    }
}

fn main() {
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).expect("stdin");
    let req: Value = serde_json::from_str(&input).expect("request JSON");
    let root = PathBuf::from(req["repo_root"].as_str().expect("repo_root"));
    let mut runner = Runner { root: root.clone(), msis: None, orbit: None, wind: None, set: None };
    let mut out = Vec::new();
    for r in req["requests"].as_array().expect("requests") {
        let id = r["id"].as_str().unwrap_or_default();
        let entry = r["entry"].as_str().unwrap_or_default();
        let t0 = std::time::Instant::now();
        let outcome = runner.run(entry, &r["args"]);
        eprintln!("{{\"id\":{},\"elapsed_s\":{}}}", to_json(&id), t0.elapsed().as_secs_f64());
        let (status, value, error) = match outcome {
            Outcome::Value(v) => ("EVALUATED".to_string(), v, "null".to_string()),
            Outcome::Error(e) => (e.status().as_str().to_string(), "null".to_string(), to_json(&e.to_string())),
            Outcome::Invalid(m) => ("INVALID_REQUEST".to_string(), "null".to_string(), to_json(&m)),
        };
        out.push(format!(
            "{{\"id\":{},\"entry\":{},\"status\":{},\"value\":{value},\"error\":{error}}}",
            to_json(&id),
            to_json(&entry),
            to_json(&status)
        ));
    }
    println!("{{\"governing\":{},\"results\":[{}]}}", governing(&root), out.join(",\n"));
}

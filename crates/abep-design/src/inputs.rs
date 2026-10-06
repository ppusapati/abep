//! `architecture_optimizer.load_upstream_inputs` / `UpstreamInputs`: the committed lane deliverables of the upstream
//! sub-problem F1 -> F2 -> F3 -> F4, read as pinned inputs (sha256 verified on every load; a changed deliverable is a
//! MODEL_ERROR refusal, never silently re-read), plus the materials database values the gas path consumes.

use crate::err::{model, schema, DResult};
use crate::f1view::{load_f1_records, F1View};
use abep_atmos::design_state_set::required_states;
use abep_data::design_states::DesignStateSet;
use abep_data::pins::FrozenPins;
use abep_gaspath::compressor::Ctx;
use abep_gaspath::materials::{MaterialProps, MaterialsView};
use abep_gaspath::plenum_feed::{f1_candidate_id, filter_cases, CompressorPlant, FilterCase, IntakeState, T_CHAIN_K};
use abep_gaspath::rotor_strength::Registry;
use abep_mission::intake_drag::{drag_table, DragTable, EnvelopeAtmospheres, F1CoreSpeciesTable, DESIGN_CASE_ALT_KM};
use abep_provenance::read_verified;
use serde_json::{Map, Value};
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

/// Lane deliverables read by F7 / F8 (relative path, registered sha256). The F1 core view is pinned in abep-mission.
pub const F3_REL: &str = "docs/design_synthesis/f3_compressor/f3_compressor_synthesis_v1.json";
pub const F3_SHA256: &str = "6871975696f7b40dac897c52b529266eb053ecbf4ea7ab17cb3e3fbdac73a27b";
pub const F3D_REL: &str = "docs/design_synthesis/f3_compressor/f3_compressor_designs_v1.json";
pub const F3D_SHA256: &str = "74a52aa749e1d071f76957e4f9ef4929c9d8ab302b183da3c5a5d9ba8d6d6923";
pub const F4_REL: &str = "docs/design_synthesis/f4_plenum/f4_plenum_feed_v1.json";
pub const F4_SHA256: &str = "fffb223023f944f166112acf017af277a50ede84695cb78f933dd5ca918fd3a9";
pub const F5_REL: &str = "docs/hardware/h1_freeze_candidate/h1_freeze_candidate_v1.json";
pub const F5_SHA256: &str = "36aca79c1e515f6828f120d4b90174815e888780f4070e08cd70dff31b9ab1a8";
pub const F6_REL: &str = "docs/design_synthesis/f6_icp_geometry/f6_icp_geometry_v1.json";
pub const F6_SHA256: &str = "eace9c279f09ab25ba0d3c5c7f2d2c4e42da682a16e2f3bd474d7c3fef755450";
pub const P3_REL: &str = "docs/experiments/hall_icp/p3_coupled_thermal/p3_coupled_thermal_v2.json";
pub const P3_SHA256: &str = "1db2b13e82389fc824acc24f6b6b9aafb11b950b9c5546347cc8037b2bdb132a";
pub const P4_REL: &str = "docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json";
pub const P4_SHA256: &str = "f0d8bbfa6d3ec59a30910ef2ae1fd61f96fc3f725e6859dc8c6617b1cf6dd96b";
pub const MP_REL: &str = "docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json";
pub const MP_SHA256: &str = "3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a";
pub const PARITY_REL: &str = "docs/performance/abep_core/parity_report_v1.json";
pub const PARITY_SHA256: &str = "09cf58a9dac3aea1aed2e3a343310d189c980a78ec699a75f7bc494c161418f8";
pub const F1_REL: &str = "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json";

/// The pinned inputs (path, sha256), for run records.
pub const PINNED: [(&str, &str); 9] = [
    (F3_REL, F3_SHA256),
    (F3D_REL, F3D_SHA256),
    (F4_REL, F4_SHA256),
    (F5_REL, F5_SHA256),
    (F6_REL, F6_SHA256),
    (P3_REL, P3_SHA256),
    (P4_REL, P4_SHA256),
    (MP_REL, MP_SHA256),
    (PARITY_REL, PARITY_SHA256),
];

/// Read a pinned lane deliverable (sha256 verified).
pub fn read_pinned(repo: &Path, rel: &str) -> DResult<Value> {
    let sha = PINNED
        .iter()
        .find(|(p, _)| *p == rel)
        .map(|(_, s)| *s)
        .ok_or_else(|| model(format!("RuntimeError: {rel} is not a registered pinned input")))?;
    let bytes = read_verified(&repo.join(rel), sha)?;
    serde_json::from_slice(&bytes).map_err(|e| schema(rel, &e.to_string()))
}

/// The materials database values the gas path reads (abep-subsystems materials DB, admitted).
pub fn materials_view() -> DResult<MaterialsView> {
    let mut m = BTreeMap::new();
    for mat in abep_subsystems::materials::db::db() {
        let d = mat.to_value();
        let dict = d.as_dict().ok_or_else(|| model("RuntimeError: material record"))?;
        let name = dict.get("name").and_then(|v| v.as_str()).ok_or_else(|| model("RuntimeError: material name"))?;
        let f = |k: &str| -> DResult<f64> {
            match dict.get(k) {
                Some(abep_types::pyjson::Value::Float(x)) => Ok(*x),
                Some(abep_types::pyjson::Value::Int(i)) => {
                    i.to_f64().map_err(|_| model(format!("RuntimeError: material {name} {k}")))
                }
                _ => Err(model(format!("RuntimeError: material {name} {k}"))),
            }
        };
        m.insert(
            name.to_string(),
            MaterialProps {
                density: f("density")?,
                yield_mpa: f("yield_MPa")?,
                t_max_k: f("T_max_K")?,
                gamma_min: f("gamma_min")?,
                gamma0: f("gamma0")?,
                gamma_ea_ev: f("gamma_Ea_eV")?,
            },
        );
    }
    Ok(MaterialsView(m))
}

/// `UpstreamInputs`.
#[derive(Debug, Clone)]
pub struct UpstreamInputs {
    pub f1: F1View,
    /// d-collapsed F1 candidate ids, sorted by (A, L/d, phi)
    pub candidates: Vec<String>,
    /// candidate -> (A, L/d, phi)
    pub geometry: HashMap<String, (f64, f64, f64)>,
    pub scenarios: Vec<String>,
    /// F1 state ids: design-case reference + every required design state
    pub states: Vec<String>,
    pub required_states: Vec<String>,
    /// (candidate, scenario, state) -> IntakeState
    pub records: HashMap<(String, String, String), IntakeState>,
    /// compressor design ids in the F4 x_compressor order
    pub compressor_ids: Vec<String>,
    pub plants: HashMap<String, CompressorPlant>,
    pub designs: HashMap<String, Map<String, Value>>,
    /// filter case ids in pf.filter_cases() order
    pub filter_ids: Vec<String>,
    pub filters: HashMap<String, FilterCase>,
    pub drag: DragTable,
    pub materials: MaterialsView,
    pub registry: Registry,
}

impl UpstreamInputs {
    pub fn ctx(&self) -> Ctx<'_> {
        Ctx { materials: &self.materials, registry: &self.registry }
    }

    /// (drag per m^2, SE per m^2) of (scenario, L/d, phi, state) (`drag_per_area`).
    pub fn drag_per_area(&self, scenario: &str, l_over_d: f64, phi: f64, state: &str) -> DResult<(f64, f64)> {
        self.drag
            .get(scenario, l_over_d, phi, state)
            .map(|e| (e.drag_per_area_n_m2, e.drag_se_per_area_n_m2))
            .ok_or_else(|| model(format!("KeyError: ({scenario:?}, {l_over_d}, {phi}, {state:?})")))
    }

    pub fn record(&self, cand: &str, sc: &str, st: &str) -> DResult<&IntakeState> {
        self.records
            .get(&(cand.to_string(), sc.to_string(), st.to_string()))
            .ok_or_else(|| model(format!("KeyError: ({cand:?}, {sc:?}, {st:?})")))
    }

    pub fn filter(&self, id: &str) -> DResult<&FilterCase> {
        self.filters.get(id).ok_or_else(|| model(format!("KeyError: {id:?}")))
    }

    pub fn plant(&self, id: &str) -> DResult<&CompressorPlant> {
        self.plants.get(id).ok_or_else(|| model(format!("KeyError: {id:?}")))
    }
}

/// `load_upstream_inputs(repo)`.
pub fn load_upstream_inputs(repo: &Path) -> DResult<UpstreamInputs> {
    let f1 = F1View::load(repo)?;
    // the F1 states: design-case reference first, then every required state of the pinned design-state set v2
    let pins = FrozenPins::load(repo)?;
    let set = DesignStateSet::load(repo, &pins)?;
    let req = required_states(&set)?;
    let mut states = vec![abep_mission::intake_drag::DESIGN_CASE_STATE_ID.to_string()];
    let mut alt = HashMap::new();
    alt.insert(states[0].clone(), DESIGN_CASE_ALT_KM);
    for s in &req {
        states.push(s.state_id.clone());
        alt.insert(s.state_id.clone(), s.alt_km);
    }
    let required: Vec<String> = req.iter().map(|s| s.state_id.clone()).collect();
    let areas = f1.area_m2.clone();
    let recs = load_f1_records(&f1, &areas, &alt)?;
    let mut records = HashMap::new();
    for r in recs {
        records.insert((r.candidate.clone(), r.scenario.clone(), r.state.clone()), r);
    }
    let mut geometry = HashMap::new();
    for &a in &areas {
        for &ld in &f1.l_over_d {
            for &phi in &f1.phi {
                geometry.insert(f1_candidate_id(a, ld, phi), (a, ld, phi));
            }
        }
    }
    let mut candidates: Vec<String> = geometry.keys().cloned().collect();
    candidates.sort_by(|x, y| {
        let (a, b) = (geometry[x], geometry[y]);
        a.partial_cmp(&b).expect("finite geometry")
    });
    let scenarios = f1.scenarios.clone();
    if f1.orbit_states != states {
        return Err(model(
            "RuntimeError: F1 deliverable was not evaluated on the current state set (design-case reference + the \
             required states of the pinned design-state set v2): regenerate F1",
        ));
    }
    for c in &candidates {
        for sc in &scenarios {
            for st in &states {
                if !records.contains_key(&(c.clone(), sc.clone(), st.clone())) {
                    return Err(model(format!("RuntimeError: F1 record missing for {c} {sc} {st}")));
                }
            }
        }
    }
    let f4 = read_pinned(repo, F4_REL)?;
    let ids: Vec<String> = f4
        .get("search_variables")
        .and_then(Value::as_array)
        .and_then(|a| a.iter().find(|x| x.get("id").and_then(Value::as_str) == Some("x_compressor")))
        .and_then(|x| x.get("value"))
        .and_then(Value::as_array)
        .ok_or_else(|| schema(F4_REL, "search_variables x_compressor"))?
        .iter()
        .map(|v| v.as_str().map(str::to_string).ok_or_else(|| schema(F4_REL, "x_compressor id")))
        .collect::<DResult<_>>()?;
    let f3d = read_pinned(repo, F3D_REL)?;
    let mut grid: HashMap<String, Map<String, Value>> = HashMap::new();
    for x in f3d.get("design_grid").and_then(Value::as_array).ok_or_else(|| schema(F3D_REL, "design_grid"))? {
        let o = x.as_object().ok_or_else(|| schema(F3D_REL, "design"))?;
        let id = o.get("id").and_then(Value::as_str).ok_or_else(|| schema(F3D_REL, "id"))?;
        grid.insert(id.to_string(), o.clone());
    }
    let materials = materials_view()?;
    let registry = Registry::default();
    let mut plants = HashMap::new();
    let mut designs = HashMap::new();
    for i in &ids {
        let d = grid.get(i).ok_or_else(|| model(format!("KeyError: {i:?}")))?;
        let ctx = Ctx { materials: &materials, registry: &registry };
        plants.insert(i.clone(), CompressorPlant::from_design(ctx, d, T_CHAIN_K)?);
        designs.insert(i.clone(), d.clone());
    }
    let fcs = filter_cases(&[0.9, 0.7, 0.5])?;
    let filter_ids: Vec<String> = fcs.iter().map(|f| f.case_id.clone()).collect();
    let filters: HashMap<String, FilterCase> = fcs.into_iter().map(|f| (f.case_id.clone(), f)).collect();
    let table = F1CoreSpeciesTable::load(repo)?;
    let atm = EnvelopeAtmospheres::load(repo)?;
    if atm.ids != states {
        return Err(model("RuntimeError: envelope atmospheres do not match the F1 state order"));
    }
    let drag = drag_table(&table, &atm)?;
    Ok(UpstreamInputs {
        f1,
        candidates,
        geometry,
        scenarios,
        states,
        required_states: required,
        records,
        compressor_ids: ids,
        plants,
        designs,
        filter_ids,
        filters,
        drag,
        materials,
        registry,
    })
}

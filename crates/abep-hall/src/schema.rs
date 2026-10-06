//! `hallthruster_bridge/hall_map_schema_v1.json`: the interchange schema shared with the Julia driver. REQUIRED_FIELDS
//! and REQUIRED_META are read from it at run time (as abep_sim/hall_map.py); the constants below are the field set this
//! crate was written against, checked against the schema by a unit test.

use crate::error::{HallError, HallResult};
use crate::py::{self, PyValue};

pub const SCHEMA_NAME: &str = "hall_map_schema_v1";
pub const SCHEMA_REL: &str = "hallthruster_bridge/hall_map_schema_v1.json";

pub const REQUIRED_FIELDS_V1: [&str; 21] = [
    "thrust_N",
    "discharge_current_A",
    "ion_current_A",
    "discharge_power_W",
    "anode_eff",
    "mass_eff",
    "current_eff",
    "voltage_eff",
    "divergence_eff",
    "Te_max_eV",
    "ne_max_m3",
    "ion_species_fraction_atomic",
    "wall_ion_flux_m2s",
    "wall_ion_energy_eV",
    "Id_rms_rel",
    "Id_pp_rel",
    "Id_f_dominant_Hz",
    "converged",
    "sustained",
    "wall_life_trustworthy",
    "chemistry_trustworthy",
];

pub const REQUIRED_META_V1: [&str; 12] = [
    "schema",
    "pinned",
    "hallthruster_commit",
    "reaction_set",
    "transport",
    "facility_ingestion",
    "grid",
    "dt_s",
    "duration_s",
    "average_start_s",
    "ion_wall_losses",
    "ensemble_member_id",
];

/// The loaded schema: REQUIRED_FIELDS and REQUIRED_META in file order.
#[derive(Debug, Clone)]
pub struct HallMapSchema {
    pub fields: Vec<String>,
    pub meta: Vec<String>,
    pub doc: PyValue,
}

fn names(v: &PyValue) -> HallResult<Vec<String>> {
    py::iterate(v)?
        .into_iter()
        .map(|x| match x {
            PyValue::Str(s) => Ok(s),
            other => Err(HallError::type_error(format!("schema key {} is not a string", py::repr(&other)))),
        })
        .collect()
}

/// `hall_map.load_schema(path)`.
pub fn load_schema(path: &str) -> HallResult<HallMapSchema> {
    let doc = py::load_json_file(path)?;
    if !py::get(&doc, "schema")?.is_some_and(|v| v.py_eq(&py::s(SCHEMA_NAME))) {
        return Err(HallError::value("HM_SCHEMA_FILE", format!("{path} is not {SCHEMA_NAME}")));
    }
    let fields = names(py::getitem(&doc, "fields")?)?;
    let meta = names(py::getitem(&doc, "meta_required")?)?;
    Ok(HallMapSchema { fields, meta, doc })
}

/// The repository schema (`hall_map.SCHEMA`).
pub fn repo_schema(repo: &str) -> HallResult<HallMapSchema> {
    load_schema(&py::join(repo, SCHEMA_REL))
}

/// `hall_map.missing_fields(record)`: schema fields absent from one operating-point record, in schema order.
pub fn missing_fields(schema: &HallMapSchema, record: &PyValue) -> HallResult<Vec<String>> {
    let mut out = Vec::new();
    for f in &schema.fields {
        if !py::contains(record, &py::s(f.as_str()))? {
            out.push(f.clone());
        }
    }
    Ok(out)
}

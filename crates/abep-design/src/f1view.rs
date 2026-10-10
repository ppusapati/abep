//! The F1 consumer view the F7 / F8 chain reads (`intake_synthesis.expand_core` of the committed, sha256-pinned core
//! view; `plenum_feed.load_f1_records` / `f1_state_infeasibility`). Only the fields F7 / F8 consume are decoded: the
//! IF-A1 unit-area records, the envelope infeasibility reasons, the species-table design-state rows (eta_c, CR) and the
//! small verbatim keys. Nothing is recomputed; the F1 TPMC statistics are read as committed.

use crate::err::{model, schema, DResult};
use crate::pv::Pv;
use abep_gaspath::plenum_feed::{f1_candidate_id, IntakeState, T_CHAIN_K};
use abep_mission::intake_drag::{F1_CORE_REL, F1_CORE_SCHEMA, F1_CORE_SHA256};
use abep_provenance::read_verified;
use abep_types::pyjson::{loads, read_text_utf8, Value};
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

pub const SPECIES: [&str; 3] = ["O", "N2", "O2"];
pub const RECORD_SPECIES_FIELDS: [&str; 5] =
    ["mdot_fwd_kgps", "mdot_fwd_se_kgps", "p_passive_Pa", "p_passive_se_Pa", "K_back"];
pub const FEASIBLE_AT_STATE: &str = "FEASIBLE_AT_STATE";

/// One IF-A1 unit-area record (`if_a1_interface.records_per_unit_area[]`).
#[derive(Debug, Clone, PartialEq)]
pub struct UnitRecord {
    pub candidate: String,
    pub state: String,
    pub scenario: String,
    pub theta_deg: f64,
    pub t_k: f64,
    pub converged: bool,
    /// per species (O, N2, O2): mdot_fwd_kgps, mdot_fwd_se_kgps, p_passive_Pa, p_passive_se_Pa, K_back
    pub species: [[f64; 5]; 3],
}

/// One species-table row (the columns F8 reads).
#[derive(Debug, Clone, PartialEq)]
pub struct SpeciesRow {
    pub state_id: String,
    pub species: String,
    pub l_over_d: f64,
    pub phi: f64,
    pub alpha: f64,
    pub theta_deg: f64,
    pub scattering: String,
    pub eta_c: f64,
    pub cr_passive: f64,
}

#[derive(Debug, Clone)]
pub struct F1View {
    pub orbit_states: Vec<String>,
    pub area_m2: Vec<f64>,
    pub l_over_d: Vec<f64>,
    pub phi: Vec<f64>,
    pub d_mm: Vec<f64>,
    /// `design_space.scenario_axes` (verbatim)
    pub scenario_axes: Value,
    /// `pareto.envelope` keys in file order
    pub scenarios: Vec<String>,
    pub records: Vec<UnitRecord>,
    pub species_rows: Vec<SpeciesRow>,
    /// `infeasible_reasons.envelope` decoded: scenario -> [(candidate id with d, reasons)] in file order
    pub envelope_reasons: Vec<(String, Vec<(String, Vec<String>)>)>,
    /// `coverage_rule.design_state_set` (verbatim)
    pub design_state_set: Value,
}

fn strings(v: Option<&Value>, what: &str) -> DResult<Vec<String>> {
    v.arr()
        .ok_or_else(|| schema(F1_CORE_REL, what))?
        .iter()
        .map(|x| x.s().map(str::to_string).ok_or_else(|| schema(F1_CORE_REL, what)))
        .collect()
}

fn floats(v: Option<&Value>, what: &str) -> DResult<Vec<f64>> {
    v.arr()
        .ok_or_else(|| schema(F1_CORE_REL, what))?
        .iter()
        .map(|x| x.f().ok_or_else(|| schema(F1_CORE_REL, what)))
        .collect()
}

fn num(v: &Value, what: &str) -> DResult<f64> {
    v.f().ok_or_else(|| schema(F1_CORE_REL, what))
}

fn idx(v: &Value, what: &str) -> DResult<usize> {
    v.u().map(|x| x as usize).ok_or_else(|| schema(F1_CORE_REL, what))
}

impl F1View {
    pub fn load(repo: &Path) -> DResult<Self> {
        let bytes = read_verified(&repo.join(F1_CORE_REL), F1_CORE_SHA256)?;
        let text = read_text_utf8(&bytes).map_err(|e| schema(F1_CORE_REL, &e.to_string()))?;
        let core = loads(&text).map_err(|e| schema(F1_CORE_REL, &e.to_string()))?;
        Self::from_core(&core)
    }

    pub fn from_core(core: &Value) -> DResult<Self> {
        if core.g("schema").s() != Some(F1_CORE_SCHEMA) {
            return Err(model(format!("RuntimeError: not an F1 core view: schema {:?}", core.g("schema"))));
        }
        let verb = core.g("verbatim").ok_or_else(|| schema(F1_CORE_REL, "verbatim"))?;
        let enc = core.g("encoded").ok_or_else(|| schema(F1_CORE_REL, "encoded"))?;
        let states = strings(enc.g("states"), "encoded.states")?;
        let orbit_states = strings(verb.ptr("/coverage_rule/orbit_states"), "coverage_rule.orbit_states")?;
        let vars = verb.ptr("/design_space/variables").ok_or_else(|| schema(F1_CORE_REL, "design_space"))?;
        let scenario_axes =
            verb.ptr("/design_space/scenario_axes").cloned().ok_or_else(|| schema(F1_CORE_REL, "scenario_axes"))?;
        let scenarios: Vec<String> = verb
            .ptr("/pareto/envelope")
            .obj()
            .ok_or_else(|| schema(F1_CORE_REL, "pareto.envelope"))?
            .keys()
            .cloned()
            .collect();
        // IF-A1 records
        let ia = enc.g("if_a1_interface").ok_or_else(|| schema(F1_CORE_REL, "if_a1_interface"))?;
        let cands = strings(ia.g("candidates"), "if_a1.candidates")?;
        let scens = strings(ia.g("scenarios"), "if_a1.scenarios")?;
        let sp = strings(ia.g("species"), "if_a1.species")?;
        if sp != SPECIES {
            return Err(model(format!("RuntimeError: F1 record species order {sp:?} != {SPECIES:?}")));
        }
        let cols = strings(ia.g("columns"), "if_a1.columns")?;
        let mut want = vec!["candidate", "state", "scenario", "theta_deg", "T_K", "converged"]
            .into_iter()
            .map(str::to_string)
            .collect::<Vec<_>>();
        for s in SPECIES {
            for f in RECORD_SPECIES_FIELDS {
                want.push(format!("{s}.{f}"));
            }
        }
        if cols != want {
            return Err(schema(F1_CORE_REL, "if_a1.columns"));
        }
        let mut records = vec![];
        for row in ia.g("rows").arr().ok_or_else(|| schema(F1_CORE_REL, "if_a1.rows"))? {
            let r = row.arr().ok_or_else(|| schema(F1_CORE_REL, "if_a1 row"))?;
            if r.len() != want.len() {
                return Err(schema(F1_CORE_REL, "if_a1 row length"));
            }
            let mut species = [[0.0; 5]; 3];
            for (j, s) in species.iter_mut().enumerate() {
                for (k, x) in s.iter_mut().enumerate() {
                    *x = num(&r[6 + j * 5 + k], "if_a1 species field")?;
                }
            }
            records.push(UnitRecord {
                candidate: cands.get(idx(&r[0], "cand")?).ok_or_else(|| schema(F1_CORE_REL, "cand idx"))?.clone(),
                state: states.get(idx(&r[1], "state")?).ok_or_else(|| schema(F1_CORE_REL, "state idx"))?.clone(),
                scenario: scens.get(idx(&r[2], "scen")?).ok_or_else(|| schema(F1_CORE_REL, "scen idx"))?.clone(),
                theta_deg: num(&r[3], "theta_deg")?,
                t_k: num(&r[4], "T_K")?,
                converged: r[5].b().ok_or_else(|| schema(F1_CORE_REL, "converged"))?,
                species,
            });
        }
        // species table (state_id, species, L_over_d, phi, alpha, theta_deg, scattering, source, eta_c, C_D_species,
        // C_D_species_se, CR_passive)
        let st = enc.g("species_table").ok_or_else(|| schema(F1_CORE_REL, "species_table"))?;
        let scols = strings(st.g("columns"), "species_table.columns")?;
        let c = |n: &str| scols.iter().position(|x| x == n).ok_or_else(|| schema(F1_CORE_REL, n));
        let (i_sp, i_ld, i_phi, i_al, i_th, i_sc, i_eta, i_cr) = (
            c("species")?,
            c("L_over_d")?,
            c("phi")?,
            c("alpha")?,
            c("theta_deg")?,
            c("scattering")?,
            c("eta_c")?,
            c("CR_passive")?,
        );
        if c("state_id")? != 0 {
            return Err(schema(F1_CORE_REL, "state_id is not column 0"));
        }
        let mut species_rows = vec![];
        for row in st.g("rows").arr().ok_or_else(|| schema(F1_CORE_REL, "species rows"))? {
            let r = row.arr().ok_or_else(|| schema(F1_CORE_REL, "species row"))?;
            let s = |i: usize| r[i].s().map(str::to_string).ok_or_else(|| schema(F1_CORE_REL, "string cell"));
            species_rows.push(SpeciesRow {
                state_id: states.get(idx(&r[0], "state")?).ok_or_else(|| schema(F1_CORE_REL, "state idx"))?.clone(),
                species: s(i_sp)?,
                l_over_d: num(&r[i_ld], "L_over_d")?,
                phi: num(&r[i_phi], "phi")?,
                alpha: num(&r[i_al], "alpha")?,
                theta_deg: num(&r[i_th], "theta_deg")?,
                scattering: s(i_sc)?,
                eta_c: num(&r[i_eta], "eta_c")?,
                cr_passive: num(&r[i_cr], "CR_passive")?,
            });
        }
        // envelope infeasibility reasons ([i, v] -> 'C-DRAG-RFP at {states[i]}: {v} mN'; others verbatim)
        let env = enc
            .ptr("/infeasible_reasons/envelope")
            .obj()
            .ok_or_else(|| schema(F1_CORE_REL, "infeasible_reasons.envelope"))?;
        let mut envelope_reasons = vec![];
        for (sc, blk) in env.iter() {
            let mut lists = vec![];
            for g in blk.g("reason_lists").arr().ok_or_else(|| schema(F1_CORE_REL, "lists"))? {
                let mut out = vec![];
                for r in g.arr().ok_or_else(|| schema(F1_CORE_REL, "reason list"))? {
                    out.push(match r {
                        Value::Str(s) => s.clone(),
                        Value::List(a) if a.len() == 2 => {
                            let st =
                                states.get(idx(&a[0], "reason state")?).ok_or_else(|| schema(F1_CORE_REL, "rs"))?;
                            let v = a[1].s().ok_or_else(|| schema(F1_CORE_REL, "reason value"))?;
                            format!("C-DRAG-RFP at {st}: {v} mN")
                        }
                        _ => return Err(schema(F1_CORE_REL, "reason")),
                    });
                }
                lists.push(out);
            }
            let mut cl = vec![];
            for e in blk.g("candidates").arr().ok_or_else(|| schema(F1_CORE_REL, "cands"))? {
                let e = e.arr().ok_or_else(|| schema(F1_CORE_REL, "cand entry"))?;
                let cid = e.first().s().ok_or_else(|| schema(F1_CORE_REL, "cand id"))?;
                let gi = idx(e.get(1).unwrap_or(&Value::Null), "group")?;
                cl.push((cid.to_string(), lists.get(gi).cloned().ok_or_else(|| schema(F1_CORE_REL, "group idx"))?));
            }
            envelope_reasons.push((sc.clone(), cl));
        }
        Ok(F1View {
            orbit_states,
            area_m2: floats(vars.g("area_m2"), "area_m2")?,
            l_over_d: floats(vars.g("L_over_d"), "L_over_d")?,
            phi: floats(vars.g("phi"), "phi")?,
            d_mm: floats(vars.g("d_mm"), "d_mm")?,
            scenario_axes,
            scenarios,
            records,
            species_rows,
            envelope_reasons,
            design_state_set: verb
                .ptr("/coverage_rule/design_state_set")
                .cloned()
                .ok_or_else(|| schema(F1_CORE_REL, "design_state_set"))?,
        })
    }
}

/// Python `re.findall(r"(?:C-DRAG-RFP|MODEL_ERROR) at (\S+?)(?=: |$)", text)`.
pub fn state_ids_in_reason(text: &str) -> Vec<String> {
    let chars: Vec<char> = text.chars().collect();
    let pre: [Vec<char>; 2] = ["C-DRAG-RFP at ".chars().collect(), "MODEL_ERROR at ".chars().collect()];
    let mut out = vec![];
    let mut i = 0;
    while i < chars.len() {
        let mut hit = None;
        for p in &pre {
            if chars[i..].starts_with(p) {
                let j = i + p.len();
                // lazy \S+? then lookahead ': ' or end
                let mut k = j;
                while k < chars.len() && !chars[k].is_whitespace() {
                    k += 1;
                    if k == chars.len() || (chars[k] == ':' && chars.get(k + 1) == Some(&' ')) {
                        hit = Some((j, k));
                        break;
                    }
                }
                if hit.is_some() {
                    break;
                }
            }
        }
        match hit {
            Some((j, k)) => {
                out.push(chars[j..k].iter().collect());
                i = k;
            }
            None => i += 1,
        }
    }
    out
}

/// `f1_candidate_id` of an F1 envelope candidate `A{A}_d{d}_Ld{L}_phi{phi}`.
fn collapse_candidate(cid: &str) -> DResult<String> {
    let bad = || model(format!("RuntimeError: unrecognised F1 candidate id {cid:?}"));
    let rest = cid.strip_prefix('A').ok_or_else(bad)?;
    let (a, rest) = rest.split_once("_d").ok_or_else(bad)?;
    let (_d, rest) = rest.split_once("_Ld").ok_or_else(bad)?;
    let (ld, phi) = rest.split_once("_phi").ok_or_else(bad)?;
    let p = |s: &str| -> DResult<f64> {
        if s.is_empty() || !s.chars().all(|c| c.is_ascii_digit() || c == '.') {
            return Err(bad());
        }
        s.parse::<f64>().map_err(|_| bad())
    };
    Ok(f1_candidate_id(p(a)?, p(ld)?, p(phi)?))
}

/// `plenum_feed.f1_state_infeasibility`: {(scenario, d-collapsed candidate): {state: reason}}; every state must be an
/// evaluated F1 state and the d-collapse must be consistent (RuntimeError otherwise).
pub fn f1_state_infeasibility(f1: &F1View) -> DResult<HashMap<(String, String), BTreeMap<String, String>>> {
    let known: std::collections::HashSet<&str> = f1.orbit_states.iter().map(String::as_str).collect();
    let mut out: HashMap<(String, String), BTreeMap<String, String>> = HashMap::new();
    for (sc, cands) in &f1.envelope_reasons {
        for (cid, reasons) in cands {
            let key = (sc.clone(), collapse_candidate(cid)?);
            for r in reasons {
                for st in state_ids_in_reason(r) {
                    if !known.contains(st.as_str()) {
                        return Err(model(format!("RuntimeError: F1 reason names an unknown state {st:?}: {r:?}")));
                    }
                    let e = out.entry(key.clone()).or_default();
                    if let Some(prev) = e.get(&st) {
                        if prev != r {
                            return Err(model(format!(
                                "RuntimeError: F1 d-collapse inconsistent for {key:?} at {st}: {prev:?} vs {r:?}"
                            )));
                        }
                    }
                    e.insert(st, r.clone());
                }
            }
        }
    }
    Ok(out)
}

/// `plenum_feed.load_f1_records(f1, areas)`: an IntakeState for every unit-area record x area, with the F1 per-state
/// feasibility. `alt_km` maps state id -> altitude (intake_synthesis.state_alt_km).
pub fn load_f1_records(f1: &F1View, areas: &[f64], alt_km: &HashMap<String, f64>) -> DResult<Vec<IntakeState>> {
    let infeas = f1_state_infeasibility(f1)?;
    let mut out = vec![];
    for r in &f1.records {
        if !r.converged || r.theta_deg != 0.0 {
            return Err(model(format!(
                "RuntimeError: F1 record {} {} is not converged / not theta 0",
                r.candidate, r.state
            )));
        }
        let bad = || model(format!("RuntimeError: unrecognised unit-area candidate {:?}", r.candidate));
        let rest = r.candidate.strip_prefix("unit_area_Ld").ok_or_else(bad)?;
        let (ld, phi) = rest.split_once("_phi").ok_or_else(bad)?;
        let (ld, phi): (f64, f64) = (ld.parse().map_err(|_| bad())?, phi.parse().map_err(|_| bad())?);
        for &a in areas {
            if (r.t_k - T_CHAIN_K).abs() > 1e-9 {
                return Err(model("RuntimeError: F1 record temperature differs from the F4 chain temperature"));
            }
            let cid = f1_candidate_id(a, ld, phi);
            let f1s = infeas
                .get(&(r.scenario.clone(), cid.clone()))
                .and_then(|m| m.get(&r.state))
                .cloned()
                .unwrap_or_else(|| FEASIBLE_AT_STATE.to_string());
            let s = &r.species;
            out.push(IntakeState {
                candidate: cid,
                area_m2: a,
                state: r.state.clone(),
                scenario: r.scenario.clone(),
                t_k: r.t_k,
                mdot_fwd_kgps: [s[0][0] * a, s[1][0] * a, s[2][0] * a],
                p_passive_pa: [s[0][2], s[1][2], s[2][2]],
                k_back: [s[0][4], s[1][4], s[2][4]],
                f1_status: f1s,
                source: format!(
                    "SRC-F1 if_a1_interface.records_per_unit_area[{}/{}/{}] x A = {} m^2",
                    r.candidate,
                    r.state,
                    r.scenario,
                    abep_gaspath::pyops::py_format_g(a)
                ),
                alt_km: *alt_km
                    .get(&r.state)
                    .ok_or_else(|| model(format!("IntakeInputError: unknown orbit / design state id {:?}", r.state)))?,
            });
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reason_state_ids_follow_the_reference_regex() {
        let r = "C-DRAG-RFP at ds2:ECSS_LT_HIGH:alt180:lat+37.0000:lst21:lon240:doy47: 26.50 mN";
        assert_eq!(state_ids_in_reason(r), vec!["ds2:ECSS_LT_HIGH:alt180:lat+37.0000:lst21:lon240:doy47"]);
        assert_eq!(state_ids_in_reason("MODEL_ERROR at h200_f150"), vec!["h200_f150"]);
        assert_eq!(state_ids_in_reason("C-DRAG-RFP at a b: 1"), Vec::<String>::new());
        assert_eq!(state_ids_in_reason("x C-DRAG-RFP at s1: 1; MODEL_ERROR at s2"), vec!["s1", "s2"]);
    }

    #[test]
    fn candidate_collapse() {
        assert_eq!(collapse_candidate("A0.5_d5_Ld3_phi0.8").unwrap(), "A0.5_Ld3_phi0.8");
        assert!(collapse_candidate("B0.5").is_err());
    }
}

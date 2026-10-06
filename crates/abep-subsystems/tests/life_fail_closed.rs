//! SC-WP-08 fail-closed statuses on the repository's real inputs. Missing evidence is asserted as its status, never
//! skipped (A9.29 sec. 9): the empty credible Hall transport set makes every Hall-erosion-derived life NOT_EVALUATED
//! (CLAUDE.md next-work 5), the anode / collector material stays OPEN with 316L REJECTED_AS_CURRENT_BASELINE (P4), no
//! life indicator is EVALUATED, and no C1 / hollow-cathode item is part of flight life.

use abep_subsystems::life::{ao_register, hall_wall, indicators, p4};
use abep_types::pyjson::{dumps, loads, read_text_utf8, DumpOptions, Value};
use abep_types::EvalStatus;
use std::path::PathBuf;

fn root() -> PathBuf {
    abep_provenance::workspace_repo_root().expect("repository root")
}

fn json(rel: &str) -> Value {
    loads(&read_text_utf8(&std::fs::read(root().join(rel)).unwrap()).unwrap()).unwrap()
}

fn s(x: &str) -> Value {
    Value::str(x)
}

fn get<'a>(v: &'a Value, k: &str) -> &'a Value {
    v.as_dict().and_then(|d| d.get(k)).unwrap_or_else(|| panic!("missing {k}"))
}

fn real_screening_ids() -> Vec<String> {
    let e = json("hallthruster_bridge/ensemble/transport_ensemble_v0.json");
    assert!(get(&e, "members").as_list().unwrap().is_empty(), "credible Hall transport set must be EMPTY");
    get(&e, "screening_candidates")
        .as_list()
        .unwrap()
        .iter()
        .map(|m| get(m, "ensemble_member_id").as_str().unwrap().to_string())
        .collect()
}

fn valid_point(root: &std::path::Path) -> (Value, Value) {
    let pinned = abep_hall::hall_map::pinned_commit(&root.to_string_lossy(), None).unwrap();
    let mut pt = abep_types::pyjson::Dict::new();
    pt.insert("trustworthy", Value::Bool(true));
    pt.insert("wall_life_trustworthy", Value::Bool(true));
    for (k, v) in [
        ("discharge_power_W", 900.0),
        ("discharge_current_A", 3.0),
        ("wall_ion_flux_m2s", 1e21),
        ("wall_ion_energy_eV", 40.0),
    ] {
        pt.insert(k, Value::Float(v));
    }
    pt.insert("hallthruster_commit", s(&pinned));
    let mut meta = abep_types::pyjson::Dict::new();
    meta.insert("hallthruster_commit", s(&pinned));
    meta.insert("ion_wall_losses", Value::Bool(true));
    (Value::Dict(pt), Value::Dict(meta))
}

#[test]
fn hall_wall_erosion_life_is_not_evaluated_with_the_empty_credible_set() {
    let root = root();
    let mut ids = real_screening_ids();
    assert_eq!(ids.len(), 9);
    ids.extend(["unknown-member".to_string(), "adm-fixture-01".to_string()]);
    let (pt, meta) = valid_point(&root);
    let stmts = hall_wall::Statements { uncertainty: s("u"), applicability_domain: s("d"), validation_status: s("v") };
    for id in &ids {
        assert_eq!(hall_wall::hall_wall_life_input_status(&root, id), EvalStatus::NotEvaluated, "{id}");
        let mut m = meta.as_dict().unwrap().clone();
        m.insert("ensemble_member_id", s(id));
        let e = hall_wall::hallmap_wall_inputs(
            &root,
            &hall_wall::Ensemble::Real,
            &pt,
            id,
            &Value::int(6),
            &Value::Dict(m),
            &stmts,
            &Value::Null,
        )
        .expect_err("no Hall wall flux input may be formed while the credible set is EMPTY");
        assert_eq!(hall_wall::refusal_status(&e), EvalStatus::NotEvaluated, "{id}: {e}");
    }
}

#[test]
fn wall_flux_needs_wall_life_trustworthy_even_for_an_admitted_member() {
    // SYNTHETIC fixture ensemble (never evidence): the admitted path refuses a point that is not wall_life_trustworthy.
    let root = root();
    let fixture = loads(
        r#"{"members": [{"ensemble_member_id": "adm-fixture-01"}],
            "screening_candidates": [{"ensemble_member_id": "sgb-screen-01"}]}"#,
    )
    .unwrap();
    let (pt, meta) = valid_point(&root);
    let mut m = meta.as_dict().unwrap().clone();
    m.insert("ensemble_member_id", s("adm-fixture-01"));
    let stmts = hall_wall::Statements { uncertainty: s("u"), applicability_domain: s("d"), validation_status: s("v") };
    let ens = hall_wall::Ensemble::Given(fixture);
    let ok = hall_wall::hallmap_wall_inputs(
        &root,
        &ens,
        &pt,
        "adm-fixture-01",
        &Value::int(6),
        &Value::Dict(m.clone()),
        &stmts,
        &Value::Null,
    )
    .unwrap();
    assert_eq!(get(get(&ok, "wall_ion_flux_m2s"), "quantity_type"), &s("model-derived"));
    let mut p2 = pt.as_dict().unwrap().clone();
    p2.insert("wall_life_trustworthy", Value::Bool(false));
    let e = hall_wall::hallmap_wall_inputs(
        &root,
        &ens,
        &Value::Dict(p2),
        "adm-fixture-01",
        &Value::int(6),
        &Value::Dict(m),
        &stmts,
        &Value::Null,
    )
    .unwrap_err();
    assert_eq!(hall_wall::refusal_status(&e), EvalStatus::NotEvaluated);
}

#[test]
fn life_indicators_are_never_evaluated_and_the_anode_material_stays_open() {
    let root = root();
    let v = indicators::life_material_indicators(&Value::Null, &root).unwrap();
    assert_eq!(get(&v, "status"), &s("NOT_EVALUATED"));
    let ind = get(&v, "indicators").as_list().unwrap();
    for i in ind {
        assert_eq!(get(i, "status"), &s("NOT_EVALUATED"));
        let block = get(i, "block").as_str().unwrap();
        assert!(!block.contains("C1") && !block.to_lowercase().contains("cathode"), "{block}");
    }
    let wall =
        ind.iter().find(|i| get(i, "indicator") == &s("wall erosion / firing life > 15,000 h (RVM-12)")).unwrap();
    assert_eq!(get(wall, "value"), &Value::Null);
    let anode = ind.iter().find(|i| get(i, "indicator") == &s("anode material")).unwrap();
    assert_eq!(get(get(anode, "value"), "APP-ANODE"), &s("OPEN"));
    assert_eq!(get(get(anode, "fixed_statuses"), "316L_FLIGHT_ANODE"), &s("REJECTED_AS_CURRENT_BASELINE"));
    assert_eq!(get(anode, "gate_cells"), get(anode, "gate_cells_incomplete"));
    // The rotor branch needs rotor_strength (SC-WP-02, not admitted): NOT_EVALUATED, never a number.
    let design = loads(r#"{"u_tip_turbo_mps": 400.0}"#).unwrap();
    let e = indicators::life_material_indicators(&design, &root).unwrap_err();
    assert_eq!(indicators::refusal_status(&e), EvalStatus::NotEvaluated);
}

#[test]
fn every_committed_p4_gate_cell_is_incomplete_evidence() {
    let rec = json(indicators::P4_REL);
    let reqs = get(&rec, "requirements").as_list().unwrap();
    let props = get(&rec, "property_records").as_list().unwrap();
    let mut n = 0;
    for g in get(&rec, "gate_matrix").as_list().unwrap() {
        let r = reqs.iter().find(|r| get(r, "id") == get(g, "requirement")).unwrap();
        let recs: Vec<&Value> = get(g, "property_records")
            .as_list()
            .unwrap()
            .iter()
            .map(|id| props.iter().find(|p| get(p, "id") == id).unwrap())
            .collect();
        let adm: Vec<&&Value> = recs.iter().filter(|p| get(p, "admissible_for_gate") == &Value::Bool(true)).collect();
        let prop =
            if adm.len() == 1 { (*adm[0]).clone() } else { recs.first().map(|p| (*p).clone()).unwrap_or(Value::Null) };
        let tcs = if get(r, "kind") == &s("min_with_margin") { s("UNRESOLVED") } else { Value::Null };
        let out = p4::evaluate_gate(r, &prop, &tcs, &Value::Null).unwrap();
        assert_eq!(out.as_list().unwrap()[0], s("INCOMPLETE_EVIDENCE"));
        n += 1;
    }
    assert_eq!(n, 352);
    assert_eq!(p4::final_material_status(&Value::Null), "OPEN");
    assert_eq!(p4::candidate_screening_state(&[]).unwrap(), "INCOMPLETE_EVIDENCE");
}

#[test]
fn ao_environment_reproduces_the_committed_register_block() {
    let root = root();
    let alts: Vec<_> = ao_register::ALTITUDES_KM.iter().map(|a| ao_register::Altitude::Int(*a)).collect();
    let env = ao_register::compute_ao_environment(&root, ao_register::ATMOSPHERE_CSV_SHA256, &alts).unwrap();
    let reg = json("docs/experiments/lifetime_ao/ao_lifetime_register_v5.json");
    let want = get(get(&reg, "derived"), "ao_environment");
    let o = DumpOptions::default();
    assert_eq!(dumps(&env, &o).unwrap(), dumps(want, &o).unwrap());
    let idx = ao_register::compute_wall_sputter_index(
        &root,
        ao_register::WALL_LIFE_DB_REL,
        ao_register::WALL_LIFE_DB_SHA256,
        None,
    )
    .unwrap();
    assert_eq!(dumps(&idx, &o).unwrap(), dumps(get(get(&reg, "derived"), "wall_sputter_index"), &o).unwrap());
    // A changed frozen-atmosphere pin is refused, never recomputed.
    let e = ao_register::compute_ao_environment(&root, &"0".repeat(64), &alts).unwrap_err();
    assert_eq!(e.class, "RuntimeError");
}

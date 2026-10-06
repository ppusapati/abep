//! Unit tests of the IF-HALL-THERMAL-v1 admission gate (positive and negative paths) and of the malformed-case output.

use super::*;
use serde_json::json;

fn rec(id: &str, q: &str, units: &str, value: serde_json::Value, range: Option<(f64, f64)>) -> serde_json::Value {
    json!({
        "id": id, "quantity": q, "value": value, "units": units,
        "source": "synthetic unit-test vector; not evidence",
        "evidence_class": "SYNTHETIC_TEST_DATA_NOT_EVIDENCE",
        "uncertainty": "none", "validation_status": "NOT_APPLICABLE_SYNTHETIC", "status": "REGISTERED",
        "applicability_domain": {"T_min_K": range.map(|r| r.0), "T_max_K": range.map(|r| r.1), "gray_in_band": null, "text": "synthetic"}
    })
}

/// A reduced synthetic case: H1_ANODE linked to B_SC (G = 0.5 W/K, 300 K) receiving a map-derived Q_hall_anode_W.
fn case(member: &str, trustworthy: bool) -> ThermalCase {
    let hall_map = json!({
        "ensemble_member_id": member,
        "hallthruster_commit": "bfb3019fc74ceaa2c70c9d3b19236a83a44ee3b5",
        "map_meta_sha256": "0".repeat(64),
        "trustworthy": trustworthy,
        "wall_life_trustworthy": true
    });
    let records = json!([
        rec("m", "mass", "kg", json!(1.0), None),
        rec("cp", "specific_heat", "J/(kg*K)", json!({"form": "CONSTANT", "value": 500.0}), Some((1.0, 3000.0))),
        rec("G", "conductance", "W/K", json!(0.5), Some((1.0, 3000.0))),
        rec("Tb", "temperature", "K", json!(300.0), None)
    ]);
    let node = json!({
        "id": "H1_ANODE", "group": "HALL_BODY", "represents": "unit test", "presence": "REQUIRED", "role": "REGISTERED",
        "refines": null, "thermal_mass": "LUMPED_C_OF_T",
        "parts": [{"part_id": "p", "material_record_id": "cp", "mass_kg_record_id": "m"}],
        "surfaces": [], "biot_geometry": null, "receives_interface_keys": ["Q_hall_anode_W"],
        "case_classes_allowed": ["SYNTHETIC_VERIFICATION"]
    });
    let a = json!({"node": "H1_ANODE", "boundary": null, "temperature_record_id": null});
    let b = json!({"node": null, "boundary": "B_SC", "temperature_record_id": "Tb"});
    let link = json!({
        "id": "L1", "type": "LUMPED_G", "a": a, "b": b,
        "k_record_id": null, "shape": null, "h_c_record_id": null, "contact_area_record_id": null, "G_record_id": "G"
    });
    let key = json!({
        "value": 5.0, "units": "W", "status": "EVALUATED", "evidence_class": "SYNTHETIC_TEST_DATA_NOT_EVIDENCE",
        "source": "unit test", "uncertainty": "none", "applicability_domain": "synthetic",
        "validation_status": "NOT_APPLICABLE_SYNTHETIC", "hall_map": hall_map
    });
    let hall = json!({
        "interface_id": "IF-HALL-THERMAL-v1", "interface_version": "v1", "producer_id": "SYNTHETIC",
        "producer_version": "1", "producer_prereg_sha256": "0".repeat(64), "case_id": "UNIT/gate",
        "case_class": "SYNTHETIC_VERIFICATION", "supply_mode": "AIR_PRIMARY", "design_state_id": null,
        "operating_point_id": "op", "time_basis": {"kind": "STEADY", "breakpoints_s": null},
        "keys": {"Q_hall_anode_W": key}, "partitions": {}, "rf_powered_only": null
    });
    let solver = json!({
        "mode": "STEADY", "T_init_K": {"H1_ANODE": 300.0}, "t_start_s": null, "t_end_s": null, "dt_s": null,
        "orbit_period_s": null
    });
    let v = json!({
        "schema": "abep_np_thermal_case_v1", "case_id": "UNIT/gate", "case_class": "SYNTHETIC_VERIFICATION",
        "topology_scope": "ANALYTIC_REDUCED_NETWORK", "configuration": "hall_icp_neutralizer", "supply_mode": "AIR_PRIMARY",
        "design_state_id": null, "installed_variants": [], "match_colocated": null, "magnet_load_mode": null,
        "anode_material_candidate_id": null, "collector_material_candidate_id": null, "bench_vacuum": null,
        "solver": solver, "records": records, "nodes": [node], "links": [link],
        "enclosures": [], "boundary_fluxes": [], "environment": [], "thermal_control": [],
        "coil_resistance_relations": {}, "partitions": {},
        "interfaces": {"IF-HALL-THERMAL-v1": hall, "IF-ICP-THERMAL-v1": null}
    });
    serde_json::from_value(v).expect("unit case parses")
}

fn gov() -> GovernedContext {
    GovernedContext::load(&abep_provenance::workspace_repo_root().unwrap()).unwrap()
}

fn run_ctx() -> RunContext {
    RunContext { rust_commit: "0".repeat(40), rust_tree_dirty: false }
}

#[test]
fn map_derived_hall_heat_is_accepted_only_from_an_admitted_trustworthy_member() {
    let empty = gov();
    assert!(empty.admitted_hall_members().is_empty(), "the governed credible set is EMPTY today");
    let o = run_case(&case("unit-member", true), &empty, &run_ctx());
    assert_eq!(o.run_status, RunStatus::NotEvaluated);
    assert!(o.status_reasons.iter().any(|r| r.code == "CREDIBLE_HALL_TRANSPORT_SET_EMPTY"));
    assert!(o.results.is_none());

    let admitted = gov().with_admitted_hall_member_for_unit_test("unit-member");
    let o = run_case(&case("unit-member", true), &admitted, &run_ctx());
    assert_eq!(o.run_status, RunStatus::Converged, "{:?}", o.status_reasons);
    let t = o.results.as_ref().unwrap().t_node_k.as_ref().unwrap()["H1_ANODE"];
    assert!((t - (300.0 + 5.0 / 0.5)).abs() < 1e-9);
    assert_eq!(o.provenance.ensemble_member_ids, vec!["unit-member".to_string()]);

    let o = run_case(&case("unit-member", false), &admitted, &run_ctx());
    assert_eq!(o.run_status, RunStatus::NotEvaluated);
    assert!(o.status_reasons.iter().any(|r| r.code == "HALL_MAP_POINT_NOT_TRUSTWORTHY"));
}

#[test]
fn an_unparsable_case_is_a_model_error_output() {
    let o = run_case_json(b"{\"schema\": 1}", &gov(), &run_ctx());
    assert_eq!(o.run_status, RunStatus::ModelError);
    assert_eq!(o.validation_status, NOT_VALIDATED);
    assert!(o.results.is_none());
}

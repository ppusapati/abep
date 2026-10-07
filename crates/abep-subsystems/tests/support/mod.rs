//! Test support for NP-THERMAL-CATHODELESS verification: a case builder for SYNTHETIC_TEST_DATA_NOT_EVIDENCE inputs,
//! the registered synthetic network VS-NET and the preregistered verification cases. Shared by the integration tests
//! and by `examples/np_thermal_verify.rs` (which writes the verification report data).
#![allow(dead_code, clippy::type_complexity, clippy::too_many_arguments)]

pub mod verify;
pub mod vs_net;
pub mod vs_net_v2;

use abep_provenance::git::Git;
use abep_provenance::workspace_repo_root;
use abep_subsystems::thermal::case::*;
use abep_subsystems::thermal::output::{RunStatus, ThermalOutput};
use abep_subsystems::thermal::{run_case, vocab, GovernedContext, RunContext};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::sync::OnceLock;

pub const SYN: &str = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE";
pub const SYN_SOURCE: &str =
    "synthetic verification vector (NP-THERMAL-CATHODELESS prereg analytic_limiting_cases / VS-NET); not evidence";
/// Validity range of the synthetic analytic-case properties.
pub const SYN_RANGE: (f64, f64) = (0.0, 1.0e4);
pub const SIGMA: f64 = 5.670374419e-8;

pub fn gov() -> &'static GovernedContext {
    static G: OnceLock<GovernedContext> = OnceLock::new();
    G.get_or_init(|| {
        GovernedContext::load(&workspace_repo_root().expect("repo root")).expect("governed records verify")
    })
}

pub fn run_ctx() -> RunContext {
    static R: OnceLock<RunContext> = OnceLock::new();
    R.get_or_init(|| {
        let git = Git::new(&workspace_repo_root().expect("repo root"));
        let commit = git.stdout(&["rev-parse", "--verify", "HEAD^{commit}"]).expect("git commit");
        let dirty = !git.stdout(&["status", "--porcelain", "--untracked-files=no"]).expect("git status").is_empty();
        RunContext { rust_commit: commit, rust_tree_dirty: dirty }
    })
    .clone()
}

pub fn run(case: &ThermalCase) -> ThermalOutput {
    run_case(case, gov(), &run_ctx())
}

pub fn codes(o: &ThermalOutput) -> Vec<String> {
    o.status_reasons.iter().map(|r| r.code.clone()).collect()
}

pub fn has_code(o: &ThermalOutput, code: &str) -> bool {
    o.status_reasons.iter().any(|r| r.code == code)
}

pub fn converged(o: &ThermalOutput) -> bool {
    o.run_status == RunStatus::Converged
}

pub fn node_ep(id: &str) -> Endpoint {
    Endpoint { node: Some(id.into()), boundary: None, temperature_record_id: None }
}

pub fn boundary_ep(b: &str, t_rec: &str) -> Endpoint {
    Endpoint { node: None, boundary: Some(b.into()), temperature_record_id: Some(t_rec.into()) }
}

/// Builder of `abep_np_thermal_case_v1` documents.
#[derive(Clone)]
pub struct Cb {
    pub c: ThermalCase,
    pub evidence_class: String,
}

impl Cb {
    pub fn new(case_id: &str, case_class: &str, scope: &str, supply_mode: &str) -> Cb {
        Cb {
            c: ThermalCase {
                schema: CASE_SCHEMA.into(),
                case_id: case_id.into(),
                case_class: case_class.into(),
                topology_scope: scope.into(),
                configuration: "hall_icp_neutralizer".into(),
                supply_mode: supply_mode.into(),
                design_state_id: None,
                installed_variants: vec![],
                match_colocated: None,
                magnet_load_mode: None,
                anode_material_candidate_id: None,
                collector_material_candidate_id: None,
                bench_vacuum: None,
                solver: SolverSpec {
                    mode: "STEADY".into(),
                    t_init_k: BTreeMap::new(),
                    t_start_s: None,
                    t_end_s: None,
                    dt_s: None,
                    orbit_period_s: None,
                },
                records: vec![],
                nodes: vec![],
                links: vec![],
                enclosures: vec![],
                boundary_fluxes: vec![],
                environment: vec![],
                thermal_control: vec![],
                coil_resistance_relations: BTreeMap::new(),
                interfaces: Interfaces::default(),
                partitions: BTreeMap::new(),
                model_version: None,
            },
            evidence_class: SYN.into(),
        }
    }

    /// SYNTHETIC_VERIFICATION, ANALYTIC_REDUCED_NETWORK, NON_FIRING, STEADY.
    pub fn reduced(case_id: &str) -> Cb {
        Cb::new(case_id, "SYNTHETIC_VERIFICATION", "ANALYTIC_REDUCED_NETWORK", "NON_FIRING")
    }

    pub fn record(&mut self, id: &str, q: &str, value: Value, range: Option<(f64, f64)>) -> String {
        let (units, _) = vocab::quantity(q).expect("registered quantity");
        let optical = q == "emittance_IR" || q == "absorptance_solar";
        self.c.records.push(InputRecord {
            id: Some(id.into()),
            quantity: Some(q.into()),
            value: Some(value),
            units: Some(units.into()),
            source: Some(SYN_SOURCE.into()),
            evidence_class: Some(self.evidence_class.clone()),
            uncertainty: Some(json!("none: synthetic verification input")),
            applicability_domain: Some(ApplicabilityDomain {
                t_min_k: range.map(|r| r.0),
                t_max_k: range.map(|r| r.1),
                gray_in_band: optical.then_some(true),
                text: Some("synthetic verification domain".into()),
            }),
            validation_status: Some("NOT_APPLICABLE_SYNTHETIC".into()),
            status: Some("REGISTERED".into()),
        });
        id.into()
    }

    pub fn num(&mut self, id: &str, q: &str, v: f64) -> String {
        self.record(id, q, json!(v), None)
    }

    pub fn ranged(&mut self, id: &str, q: &str, v: f64) -> String {
        self.record(id, q, json!(v), Some(SYN_RANGE))
    }

    pub fn konst(&mut self, id: &str, q: &str, v: f64, range: (f64, f64)) -> String {
        self.record(id, q, json!({"form": "CONSTANT", "value": v}), Some(range))
    }

    pub fn series(&mut self, id: &str, q: &str, t: &[f64], v: &[f64]) -> String {
        self.record(id, q, json!({"breakpoints_s": t, "values": v}), None)
    }

    pub fn find_record(&mut self, id: &str) -> &mut InputRecord {
        self.c.records.iter_mut().find(|r| r.id.as_deref() == Some(id)).expect("record")
    }

    /// A node with one part of capacity `cap` J/K (mass 1 kg x c_p = cap), or a massless node when `cap` is None.
    pub fn node(&mut self, id: &str, role: &str, group: &str, cap: Option<f64>, t_init: f64) {
        let presence =
            vocab::registered_node(id).map_or("CONDITIONAL", |n| if n.required { "REQUIRED" } else { "CONDITIONAL" });
        let parts = match cap {
            Some(c) => {
                let m = self.num(&format!("{id}.mass"), "mass", 1.0);
                let cp = self.konst(&format!("{id}.cp"), "specific_heat", c, SYN_RANGE);
                vec![Part { part_id: format!("{id}.part"), material_record_id: cp, mass_kg_record_id: m }]
            }
            None => vec![],
        };
        self.c.nodes.push(NodeRecord {
            id: id.into(),
            group: group.into(),
            represents: "synthetic verification node".into(),
            presence: presence.into(),
            role: role.into(),
            refines: None,
            thermal_mass: if cap.is_some() { "LUMPED_C_OF_T".into() } else { "MASSLESS_SERIES".into() },
            parts,
            surfaces: vec![],
            biot_geometry: None,
            receives_interface_keys: vec![],
            case_classes_allowed: vocab::CASE_CLASSES.iter().map(|s| s.to_string()).collect(),
        });
        self.c.solver.t_init_k.insert(id.into(), t_init);
    }

    pub fn node_mut(&mut self, id: &str) -> &mut NodeRecord {
        self.c.nodes.iter_mut().find(|n| n.id == id).expect("node")
    }

    pub fn surface(
        &mut self,
        node: &str,
        sid: &str,
        area: f64,
        eps: f64,
        alpha: Option<f64>,
        encl: &str,
        external: bool,
    ) {
        let a = self.num(&format!("{sid}.area"), "area", area);
        let e = self.konst(&format!("{sid}.eps"), "emittance_IR", eps, SYN_RANGE);
        let al = alpha.map(|x| self.konst(&format!("{sid}.alpha"), "absorptance_solar", x, SYN_RANGE));
        self.node_mut(node).surfaces.push(Surface {
            surface_id: sid.into(),
            area_record_id: a,
            eps_ir_record_id: e,
            alpha_solar_record_id: al,
            enclosure_id: encl.into(),
            external,
        });
    }

    pub fn lumped_g(&mut self, id: &str, a: Endpoint, b: Endpoint, g: f64) {
        let gid = self.ranged(&format!("{id}.G"), "conductance", g);
        self.c.links.push(LinkRecord {
            id: id.into(),
            link_type: "LUMPED_G".into(),
            a,
            b,
            k_record_id: None,
            shape: None,
            h_c_record_id: None,
            contact_area_record_id: None,
            g_record_id: Some(gid),
        });
    }

    pub fn temperature(&mut self, id: &str, t: f64) -> String {
        self.num(id, "temperature", t)
    }

    /// Enclosure with view factors `vf` (rows of non-sink members), sinks (id, kind, T) and SCI-C hosts (id, A, eps, T).
    pub fn enclosure(
        &mut self,
        id: &str,
        vf: BTreeMap<String, BTreeMap<String, f64>>,
        sinks: &[(&str, &str, f64)],
        hosts: &[(&str, f64, f64, f64)],
    ) {
        let vid = self.record(&format!("{id}.vf"), "view_factor_matrix", json!({ "view_factors": vf }), None);
        let sinks = sinks
            .iter()
            .map(|(s, k, t)| SinkMember {
                surface_id: (*s).into(),
                kind: (*k).into(),
                temperature_record_id: self.temperature(&format!("{s}.T"), *t),
            })
            .collect();
        let hosts = hosts
            .iter()
            .map(|(s, a, e, t)| HostSurface {
                surface_id: (*s).into(),
                area_record_id: self.num(&format!("{s}.area"), "area", *a),
                eps_ir_record_id: self.konst(&format!("{s}.eps"), "emittance_IR", *e, SYN_RANGE),
                temperature_record_id: self.temperature(&format!("{s}.T"), *t),
            })
            .collect();
        self.c.enclosures.push(EnclosureRecord {
            id: id.into(),
            view_factor_record_id: vid,
            sinks,
            host_surfaces: hosts,
        });
    }

    pub fn tc(&mut self, node: &str, q: f64) {
        let r = self.num(&format!("{node}.Qtc"), "power", q);
        self.c.thermal_control.push(ThermalControl { node: node.into(), record_id: r });
    }

    pub fn transient(&mut self, t0: f64, t1: f64, dt: f64) {
        self.c.solver.mode = "TRANSIENT".into();
        self.c.solver.t_start_s = Some(t0);
        self.c.solver.t_end_s = Some(t1);
        self.c.solver.dt_s = Some(dt);
    }
}

/// Rows of the "sphere" construction F_kl = a_l / sum(a) over every member (incl. sinks): reciprocity holds when a_l is
/// the area of each non-sink member (used for synthetic enclosures; verify V-18).
pub fn sphere_vf(members: &[(&str, f64, bool)]) -> BTreeMap<String, BTreeMap<String, f64>> {
    let total: f64 = members.iter().map(|m| m.1).sum();
    let mut out = BTreeMap::new();
    for (k, _, sink) in members {
        if *sink {
            continue;
        }
        let row: BTreeMap<String, f64> = members.iter().map(|(l, a, _)| (l.to_string(), a / total)).collect();
        out.insert(k.to_string(), row);
    }
    out
}

pub fn vf_rows(rows: &[(&str, &[(&str, f64)])]) -> BTreeMap<String, BTreeMap<String, f64>> {
    rows.iter().map(|(k, r)| (k.to_string(), r.iter().map(|(l, f)| (l.to_string(), *f)).collect())).collect()
}

/// Every object key of a JSON document (recursive), for the FT-17 static scan.
pub fn all_keys(v: &Value, out: &mut Vec<String>) {
    match v {
        Value::Object(m) => {
            for (k, x) in m {
                out.push(k.clone());
                all_keys(x, out);
            }
        }
        Value::Array(a) => {
            for x in a {
                all_keys(x, out);
            }
        }
        _ => {}
    }
}

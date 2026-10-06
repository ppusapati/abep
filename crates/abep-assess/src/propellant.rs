//! HC-10 structural check of the modelled propellant paths against the A9.15 policy as amended by A9.19
//! (`design_gates.propellant_paths_check`, `a9_19_architecture.propellant_path_roles`; contract E12). A declared path
//! is not determining evidence: the capability stays NOT_EVALUATED until demonstrated.

use crate::error::{rule_error, AssessError, AssessResult};
use crate::py::{dget_or, dict, s, strs};
use crate::statewise::{cite, rfp_clause};
use abep_config::architecture::ArchitectureDefinition;
use abep_gaspath::upstream::C_NOT_EVALUATED;
use abep_types::pyjson::{py_repr, Value};

pub const AIR_PATH: [&str; 5] = ["intake", "filter", "compressor", "atmospheric_gas_chamber", "valve"];
pub const XE_PATH: [&str; 2] = ["xe_tank", "valve"];
pub const CONSTRAINT: &str = "HC-10 dual propellant capability";

/// `upstream_a9_13.PROPELLANT_POLICY`.
pub fn propellant_policy(arch: &ArchitectureDefinition) -> Value {
    dict(vec![
        (
            "rule",
            s("A9.15 as amended by A9.19 on the ROLE of Xe: the system supports BOTH ambient atmospheric propellant \
               (180-230 km) and Xenon; two separate propellant tanks / paths (two supply modes AIR_PRIMARY and \
               XE_CONTINGENCY); both feed the ONE Hall accelerator and the ONE RF/ICP neutralizer. Xe capability is \
               RFP-required (RFP-P17-05 'an extra input system to take care any problems on board unforeseen \
               problems'; RFP-P18-08) and its role is contingency / emergency (A9.19); no hollow cathode, so no C1 Xe \
               branch in flight (A9.19 / A9.20: C1 ground-only)"),
        ),
        ("rfp_clauses", strs(&[rfp_clause("n2_o_xe"), rfp_clause("propellants"), rfp_clause("chain")])),
        ("air_path", strs(&AIR_PATH)),
        ("xe_path", strs(&XE_PATH)),
        ("supply_modes", Value::List(arch.supply_modes.clone())),
        ("xe_path_role", arch.xe_path_role.clone()),
        ("air_path_role", arch.air_path_role.clone()),
    ])
}

fn names(paths: &Value, key: &str) -> AssessResult<Vec<String>> {
    match dget_or(paths, key, Value::List(vec![]))? {
        Value::List(l) => l
            .iter()
            .map(|x| match x {
                Value::Str(t) => Ok(t.clone()),
                other => Err(AssessError::new("TypeError", format!("path node {} is not a str", py_repr(other)))),
            })
            .collect(),
        other => Err(AssessError::new("TypeError", format!("{key} path is {}", other.type_name()))),
    }
}

fn pos(xs: &[String], x: &str) -> usize {
    xs.iter().position(|n| n == x).expect("checked membership")
}

/// `propellant_paths_check(paths)`; `paths` None = the model declares no propellant paths.
pub fn propellant_paths_check(arch: &ArchitectureDefinition, paths: &Value) -> AssessResult<Value> {
    if matches!(paths, Value::Null) {
        return Ok(dict(vec![
            ("constraint", s(CONSTRAINT)),
            ("structure", s("NOT_MODELLED")),
            ("status", s(C_NOT_EVALUATED)),
            ("reason", s("the architecture model declares no propellant paths")),
            ("policy", propellant_policy(arch)),
            ("authority", cite(&["A9.15", "A9.17"])?),
        ]));
    }
    let air = names(paths, "air")?;
    let xe = names(paths, "xe")?;
    let has = |v: &[String], x: &str| v.iter().any(|n| n == x);
    let mut problems: Vec<String> = Vec::new();
    if air.is_empty() {
        problems.push("no ambient-air path".into());
    }
    if xe.is_empty() {
        problems.push("no Xe path (Xe capability is RFP-required, A9.15)".into());
    }
    if !air.is_empty() && air[0] != "intake" {
        problems.push("air path must start at the intake".into());
    }
    if !xe.is_empty() && !xe[0].starts_with("xe_tank") {
        problems.push("Xe path must start at a dedicated Xe tank".into());
    }
    let tanky = |n: &&String| n.contains("tank") || n.contains("chamber");
    let tanks_air: Vec<&String> = air.iter().filter(tanky).collect();
    let mut shared: Vec<String> = xe.iter().filter(tanky).filter(|n| tanks_air.contains(n)).cloned().collect();
    shared.sort();
    shared.dedup();
    if !shared.is_empty() {
        let l = Value::List(shared.into_iter().map(Value::Str).collect());
        problems.push(format!("shared tank(s) {}: RFP-P18-08 requires two separate tanks", py_repr(&l)));
    }
    if has(&air, "filter")
        && !(has(&air, "intake")
            && has(&air, "compressor")
            && pos(&air, "intake") < pos(&air, "filter")
            && pos(&air, "filter") < pos(&air, "compressor"))
    {
        problems.push("filter must sit between the intake and the compressor (S6.6 / S6.19)".into());
    }
    if !has(&air, "filter") && !air.is_empty() {
        problems.push("air path lacks the filter element (RFP-P16-02 chain; FC-00 is a reference bound only)".into());
    }
    if xe
        .iter()
        .any(|n| n == "c1" || n.starts_with("c1_") || n.starts_with("hollow_cathode") || n.starts_with("cathode_"))
    {
        problems.push(
            "Xe path feeds a hollow-cathode / C1 branch: no hollow cathode in flight (A9.19; C1 ground-only A9.20)"
                .into(),
        );
    }
    if !problems.is_empty() {
        return Err(rule_error(problems.join("; ")));
    }
    let mut authority = match cite(&["A9.15", "A9.17"])? {
        Value::List(l) => l,
        _ => unreachable!("cite returns a list"),
    };
    if let Value::List(l) = arch.cite(&["A9.19"])? {
        authority.extend(l);
    }
    let sl = |v: &[String]| Value::List(v.iter().cloned().map(Value::Str).collect());
    Ok(dict(vec![
        ("constraint", s(CONSTRAINT)),
        ("structure", s("TWO_SEPARATE_PATHS_DECLARED")),
        ("status", s(C_NOT_EVALUATED)),
        (
            "reason",
            s("air and Xe operating capability not yet demonstrated (a declared path is not determining evidence, \
               S6.22)"),
        ),
        ("air_path", sl(&air)),
        ("xe_path", sl(&xe)),
        ("supply_modes", dict(vec![("air", arch.supply_mode_air.clone()), ("xe", arch.supply_mode_xe.clone())])),
        ("path_roles", dict(vec![("air", arch.air_path_role.clone()), ("xe", arch.xe_path_role.clone())])),
        ("policy", propellant_policy(arch)),
        ("authority", Value::List(authority)),
    ]))
}

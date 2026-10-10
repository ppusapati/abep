//! Admission registry (acceptance_v2 `admission_registry`): the components the commands call, their contracts and the
//! committed evidence that admits them. Verified at run time (pipeline S-7): the evidence file must exist, have the
//! registered sha256 and carry the admitted verdict. A component whose evidence does not verify is never executed.

use abep_provenance::sha256_hex;
use abep_types::pyjson::{loads, read_text_utf8, Value};
use serde::Serialize;
use std::path::Path;

/// Admission state of a component as registered.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Registered {
    Admitted,
    NotAdmitted,
}

pub struct Component {
    pub component: &'static str,
    pub contract_id: &'static str,
    pub path: &'static str,
    pub sha256: &'static str,
    pub registered: Registered,
}

const fn admitted(
    component: &'static str,
    contract_id: &'static str,
    path: &'static str,
    sha256: &'static str,
) -> Component {
    Component { component, contract_id, path, sha256, registered: Registered::Admitted }
}

pub const CONFIGURATION: Component = admitted(
    "C-ABEP_SIM_CONFIGURATION_PY",
    "PARITY-C-ABEP_SIM_CONFIGURATION_PY-V1",
    "docs/rust_migration/contracts/C-ABEP_SIM_CONFIGURATION_PY/parity_report_v1.json",
    "5f7592f66dd74f58e19b772f729b0e8bec4d0e3693d50a8a58ca72737ffed5d9",
);
pub const ARCHITECTURE: Component = admitted(
    "C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY",
    "PARITY-C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY-V1",
    "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY/parity_report_v1.json",
    "57c17f049cc4dee2f0e34eeaaa39dceff85aa0790e1f54569ef14baed21875b9",
);
pub const PROVENANCE_VERIFIER: Component = admitted(
    "C-PROVENANCE-VERIFIER",
    "PARITY-C-PROVENANCE-VERIFIER-V1",
    "docs/rust_migration/contracts/C-PROVENANCE-VERIFIER/parity_report_v1.json",
    "3d04ef328dd645c49b7d2111711cfc32855dd32bb58128a9737e00544c4f34d8",
);
pub const ATMOSPHERE: Component = admitted(
    "C-ABEP_SIM_ATMOSPHERE_PY",
    "PARITY-C-ABEP_SIM_ATMOSPHERE_PY-V1",
    "docs/rust_migration/contracts/C-ABEP_SIM_ATMOSPHERE_PY/parity_report_v1.json",
    "d54967c49cd945f2190c192324a4fafde4220a77bb91f8a5771adc517939f411",
);
pub const ATMOSPHERE_ORBIT: Component = admitted(
    "C-ABEP_SIM_ATMOSPHERE_ORBIT_PY",
    "PARITY-C-ABEP_SIM_ATMOSPHERE_ORBIT_PY-V1",
    "docs/rust_migration/contracts/C-ABEP_SIM_ATMOSPHERE_ORBIT_PY/parity_report_v1.json",
    "489800cd46f5e8729efa9e04de300b1caed956169cffaba3fb74045970d9e9ba",
);
pub const INTAKE_TPMC: Component = admitted(
    "C-ABEP_SIM_INTAKE_TPMC_PY",
    "PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1",
    "docs/rust_migration/contracts/C-ABEP_SIM_INTAKE_TPMC_PY/parity_report_v1.json",
    "18c13688f1b9029297df9a6dc4ad705d282096bcb4070d15e6ad24cde490f484",
);
pub const DRAG_KERNEL: Component = admitted(
    "C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL",
    "PARITY-C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL-V1",
    "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY-DRAG_KERNEL/parity_report_v1.json",
    "e6f2ccc17b99d70f0059322a81dac6f0be596ce70b1d8a2598d62f6b5fa59859",
);
pub const MASS_RULES: Component = admitted(
    "K-MASS-RULES",
    "PARITY-K-MASS-RULES-V1",
    "docs/rust_migration/contracts/K-MASS-RULES/parity_report_v1.json",
    "825f12ec897c108e038e767e5141a9da6ad31348e020c332f1fc2cf77011a676",
);
pub const MASS_POWER_V5: Component = admitted(
    "C-DOCS_BUDGETS_MASS_POWER_A9_V5",
    "PARITY-C-DOCS_BUDGETS_MASS_POWER_A9_V5-V1",
    "docs/rust_migration/contracts/C-DOCS_BUDGETS_MASS_POWER_A9_V5/parity_report_v1.json",
    "b78de50a51ac80dcce0806c86e574ac254eee61c221ae5772950bcca7017cb85",
);
pub const BUS_BOUNDARY: Component = admitted(
    "C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY",
    "PARITY-C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY-V1",
    "docs/rust_migration/contracts/C-ABEP_SIM_BUS_BOUNDARY_A9_V2_PY/parity_report_v1.json",
    "e416e76757eac1ab8a5be5c2b6ee9fe55da31f3d6ff814a62c75727fbeb2c1f0",
);
pub const HALL_REGISTRY: Component = admitted(
    "C-HALL-MAP-ENSEMBLE-REGISTRY",
    "PARITY-C-HALL-MAP-ENSEMBLE-REGISTRY-V1",
    "docs/rust_migration/contracts/C-HALL-MAP-ENSEMBLE-REGISTRY/parity_report_v1.json",
    "a8b8888da5e7b47a489150594e7916d7df713507b5047540cf834df42dca3bd0",
);
pub const JULIA_BRIDGE: Component = admitted(
    "C-JULIA-BRIDGE-LAUNCH",
    "PARITY-C-JULIA-BRIDGE-LAUNCH-V1",
    "docs/rust_migration/contracts/C-JULIA-BRIDGE-LAUNCH/parity_report_v1.json",
    "46266d7d637b01856a046f367aebecbf544148e9dbefed6f8a6ebc6370f83588",
);
/// Ledger status RUST_IMPL (IMPLEMENTED_UNVERIFIED / NOT_ADMITTED / NOT_VALIDATED): the file is its current evidence,
/// not admission evidence.
pub const ICP: Component = Component {
    component: "NP-ICP-NEUTRALIZER",
    contract_id: "NP-ICP-NEUTRALIZER/prereg_v1+addendum_01_a9_30",
    path: "docs/rust_migration/new_physics/NP-ICP-NEUTRALIZER/verification_report_v1.json",
    sha256: "11ddb2a2684f1803b7a5fac94cb3307f59cb60e4e9a8e46d2abc2c449f4e5284",
    registered: Registered::NotAdmitted,
};

#[derive(Debug, Clone, Serialize)]
pub struct Evidence {
    pub path: &'static str,
    pub sha256: &'static str,
}

/// One entry of the result record's `components`.
#[derive(Debug, Clone, Serialize)]
pub struct ComponentState {
    pub component: &'static str,
    pub contract_id: &'static str,
    pub admission_evidence: Evidence,
    /// ADMITTED | NOT_ADMITTED | ADMISSION_EVIDENCE_UNVERIFIED
    pub admission: &'static str,
    #[serde(skip)]
    pub problem: Option<String>,
}

/// `report.verdict == 'ADMITTED'`, or `'PARITY_PASS'` with `report.admission == 'ADMITTED'`.
fn admitted_verdict(report: &Value) -> bool {
    let s = |k: &str| report.as_dict().and_then(|d| d.get(k)).and_then(Value::as_str);
    s("verdict") == Some("ADMITTED") || (s("verdict") == Some("PARITY_PASS") && s("admission") == Some("ADMITTED"))
}

/// Verify one component's evidence in `repo`.
pub fn verify(repo: &Path, c: &Component) -> ComponentState {
    let problem = match std::fs::read(repo.join(c.path)) {
        Err(e) => Some(format!("{}: cannot read: {e}", c.path)),
        Ok(bytes) => {
            let got = sha256_hex(&bytes);
            if got != c.sha256 {
                Some(format!("{}: sha256 {got} != registered {}", c.path, c.sha256))
            } else if c.registered == Registered::Admitted {
                // The reports are written by Python `json` (NaN allowed): read with the Python-JSON reader.
                match read_text_utf8(&bytes).and_then(|t| loads(&t)) {
                    Ok(v) if admitted_verdict(&v) => None,
                    Ok(_) => Some(format!("{}: verdict is not ADMITTED", c.path)),
                    Err(e) => Some(format!("{}: not JSON: {}: {}", c.path, e.class, e.message)),
                }
            } else {
                None
            }
        }
    };
    let admission = match (&problem, c.registered) {
        (Some(_), _) => "ADMISSION_EVIDENCE_UNVERIFIED",
        (None, Registered::Admitted) => "ADMITTED",
        (None, Registered::NotAdmitted) => "NOT_ADMITTED",
    };
    ComponentState {
        component: c.component,
        contract_id: c.contract_id,
        admission_evidence: Evidence { path: c.path, sha256: c.sha256 },
        admission,
        problem,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn verdict_predicate() {
        let v = |t: &str| loads(t).unwrap();
        assert!(admitted_verdict(&v(r#"{"verdict": "ADMITTED", "x": NaN}"#)));
        assert!(admitted_verdict(&v(r#"{"verdict": "PARITY_PASS", "admission": "ADMITTED"}"#)));
        assert!(!admitted_verdict(&v(r#"{"verdict": "PARITY_PASS"}"#)));
        assert!(!admitted_verdict(&v(r#"{"verdict": "PARITY_FAIL", "admission": "ADMITTED"}"#)));
        assert!(!admitted_verdict(&v(r#"["ADMITTED"]"#)));
    }

    #[test]
    fn every_registered_evidence_verifies_in_this_repository() {
        let root = abep_provenance::workspace_repo_root().unwrap();
        for c in [
            CONFIGURATION,
            ARCHITECTURE,
            PROVENANCE_VERIFIER,
            ATMOSPHERE,
            ATMOSPHERE_ORBIT,
            INTAKE_TPMC,
            DRAG_KERNEL,
            MASS_RULES,
            MASS_POWER_V5,
            BUS_BOUNDARY,
            HALL_REGISTRY,
            JULIA_BRIDGE,
        ] {
            let s = verify(&root, &c);
            assert_eq!(s.admission, "ADMITTED", "{}: {:?}", c.component, s.problem);
        }
        assert_eq!(verify(&root, &ICP).admission, "NOT_ADMITTED");
    }
}

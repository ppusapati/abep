//! NP-ICP-CHEM-AIR build plan BP-S1: write the direct-rate source representations of the reused N2/N tables to
//! `data/chemistry/icp/xs/`, one file per table (`cargo run -p abep-chem --example build_icp_xs --locked`).
//!
//! Input: the representations captured by contract PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1
//! (`reference_outputs/inputs.json.gz`, sha256 from its MANIFEST), i.e. the cross-section points each
//! `scripts/build_*.py` passes to `rate_tables.write_hallthruster_table`. The contract's INV-02 and the abep-chem CI
//! replay show that both the Python reference and the admitted Rust port render every frozen `.dat` byte for byte from
//! them. Only tables named in NP-ICP-CHEM-AIR `reuse_pins.hall_propellant_tables` are written; nothing is computed and
//! no table is built. Every input is read through a sha256 pin; the output is a pure function of those bytes.

use abep_provenance::{read_verified, sha256_hex, workspace_repo_root};
use flate2::read::GzDecoder;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::io::Read;
use std::path::Path;

const CONTRACT_DIR: &str = "docs/rust_migration/contracts/C-ABEP_SIM_RATE_TABLES_PY";
/// sha256 of the contract `parity_prereg_v1.json` (recorded in its report as `contract_sha256`).
const CONTRACT_SHA256: &str = "504be4d2386d27efa35d88d11b44e9b483cd2b39fa65d544d75da4dadada3372";
const CHEM_AIR_LOCK: &str = "docs/rust_migration/new_physics/NP-ICP-CHEM-AIR/prereg_lock_v1.json";
const CHEM_AIR_LOCK_SHA256: &str = "f42c22699a31acd4e29854823150d7b7c75b35eb8718fb90ade83bdd3d7e46ef";
const OUT_DIR: &str = "data/chemistry/icp/xs";

fn json_at(root: &Path, rel: &str, sha: &str) -> Value {
    serde_json::from_slice(&read_verified(&root.join(rel), sha).unwrap_or_else(|e| panic!("{e}"))).unwrap()
}

fn num(v: &Value) -> f64 {
    v.as_f64().unwrap_or_else(|| panic!("{v} is not a finite number"))
}

fn f(x: f64) -> String {
    serde_json::to_string(&x).unwrap()
}

/// The xs file text: a JSON object, one `[E_eV, sigma_m2]` pair per line (shortest round-trip floats).
fn render(meta: &Value, e: &[f64], s: &[f64]) -> String {
    let head = serde_json::to_string_pretty(meta).unwrap();
    let head = head.strip_suffix("\n}").unwrap();
    let mut out = format!("{head},\n  \"n_points\": {},\n  \"points\": [\n", e.len());
    for (i, (a, b)) in e.iter().zip(s).enumerate() {
        let sep = if i + 1 == e.len() { "" } else { "," };
        out.push_str(&format!("    [{}, {}]{sep}\n", f(*a), f(*b)));
    }
    out.push_str("  ]\n}\n");
    out
}

fn main() {
    let root = workspace_repo_root().unwrap();
    let contract = json_at(&root, &format!("{CONTRACT_DIR}/parity_prereg_v1.json"), CONTRACT_SHA256);
    let manifest: Value = serde_json::from_slice(
        &std::fs::read(root.join(CONTRACT_DIR).join("reference_outputs/MANIFEST.json")).unwrap(),
    )
    .unwrap();
    let gz_rel = format!("{CONTRACT_DIR}/reference_outputs/inputs.json.gz");
    let gz_sha = manifest["files"]["inputs.json.gz"]["sha256"].as_str().unwrap();
    let gz = read_verified(&root.join(&gz_rel), gz_sha).unwrap();
    let mut text = String::new();
    GzDecoder::new(gz.as_slice()).read_to_string(&mut text).unwrap();
    let inputs: Value = serde_json::from_str(&text).unwrap();

    let lock = json_at(&root, CHEM_AIR_LOCK, CHEM_AIR_LOCK_SHA256);
    let prereg_rel = "docs/rust_migration/new_physics/NP-ICP-CHEM-AIR/prereg_v1.json";
    let chem_air = json_at(&root, prereg_rel, lock["files"]["prereg_v1.json"].as_str().unwrap());
    let reuse: BTreeMap<String, (String, String)> = chem_air["reuse_pins"]["hall_propellant_tables"]
        .as_array()
        .unwrap()
        .iter()
        .map(|p| {
            let path = p["path"].as_str().unwrap().to_string();
            (path, (p["sha256"].as_str().unwrap().to_string(), p["source_file_sha256"].as_str().unwrap().to_string()))
        })
        .collect();

    let pinned = &contract["pinned_inputs_sha256"];
    let registered: BTreeMap<&str, &Value> = contract["inputs"]["registered_tables"]["tables"]
        .as_array()
        .unwrap()
        .iter()
        .map(|t| (t["id"].as_str().unwrap(), t))
        .collect();
    std::fs::create_dir_all(root.join(OUT_DIR)).unwrap();
    let mut written = 0;
    for cap in inputs["registered_tables"].as_array().unwrap() {
        let file = cap["file"].as_str().unwrap();
        let Some((table_sha, source_sha)) = reuse.get(file) else { continue };
        let id = cap["id"].as_str().unwrap();
        let reg = registered[id];
        assert_eq!(reg["file"].as_str(), Some(file), "{id}");
        assert_eq!(reg["sha256"].as_str(), Some(table_sha.as_str()), "{id}: contract and reuse pin differ");
        let source_rel = format!("{file}.source");
        read_verified(&root.join(file), table_sha).unwrap();
        read_verified(&root.join(&source_rel), source_sha).unwrap();
        let construction = reg["construction"].as_str().unwrap();
        let module = construction.split([':', '.']).next().unwrap();
        let script = format!("scripts/{module}.py");
        let script_sha = pinned[&script].as_str().unwrap_or_else(|| panic!("{script} not pinned by the contract"));
        read_verified(&root.join(&script), script_sha).unwrap();
        let e: Vec<f64> = cap["E_eV"].as_array().unwrap().iter().map(num).collect();
        let s: Vec<f64> = cap["sigma_m2"].as_array().unwrap().iter().map(num).collect();
        assert_eq!(e.len(), s.len());
        assert_eq!(e.len() as u64, reg["n_points"].as_u64().unwrap(), "{id}");
        let meta = json!({
            "schema": "icp_chem_xs_v1",
            "kind": "CROSS_SECTION",
            "table": file,
            "table_sha256": table_sha,
            "table_source": source_rel,
            "table_source_sha256": source_sha,
            "tail": cap["tail"],
            "threshold_eV": cap["threshold_eV"],
            "header_label": cap["header_label"],
            "eps_max_eV": cap["eps_max"],
            "units": {"E": "eV", "sigma": "m^2"},
            "interpolation": "linear in sigma(E) between points; sigma = 0 below the first point; above the last point the declared tail (hold / zero) (NP-ICP-CHEM-AIR IX-02..IX-04; abep_chem::reference::maxwellian_rate)",
            "provenance": {
                "captured_from": gz_rel,
                "captured_sha256": gz_sha,
                "captured_id": id,
                "contract": "PARITY-C-ABEP_SIM_RATE_TABLES_PY-V1",
                "contract_sha256": CONTRACT_SHA256,
                "construction": construction,
                "builder_script": script,
                "builder_script_sha256": script_sha,
                "chain": "the points the builder script passes to rate_tables.write_hallthruster_table; the Python reference (contract INV-02) and the admitted Rust port (crates/abep-chem/tests/reference_replay.rs) render the frozen table from them byte for byte",
                "citation": "the table's .source file and hallthruster_bridge/propellants/PROVENANCE.md",
                "extracted_by": "crates/abep-chem/examples/build_icp_xs.rs"
            }
        });
        let stem = Path::new(file).file_stem().unwrap().to_str().unwrap();
        let out = render(&meta, &e, &s);
        let out_rel = format!("{OUT_DIR}/{stem}.json");
        std::fs::write(root.join(&out_rel), &out).unwrap();
        println!("{out_rel} {} {}", e.len(), sha256_hex(out.as_bytes()));
        written += 1;
    }
    assert_eq!(written, 32, "every reused table with a committed representation");
}

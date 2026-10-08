//! NP-HALL-CHEM-AIR build plan: render the Hall AIR tables from their registered cross-section representations
//! (`hallthruster_bridge/propellants_air/xs/*.json`, `hallthruster_bridge/audit_air/bound_tables/xs/*.json`) with the
//! admitted integrator (`abep_chem::reference`, contract C-ABEP_SIM_RATE_TABLES_PY), and write each `.dat` and `.source`.
//!
//!   cargo run -p abep-chem --example build_hall_air_tables --locked [-- --check] [-- --only <name.dat>]
//!
//! Every rendered `.dat` must equal the v0 DRAFT table it reproduces (sha256 in the representation); a difference refuses
//! the write. `--check` writes nothing and exits 1 when a committed file differs from its rendering.

use abep_chem::hall_air::{render_xs, xs_files};
use abep_provenance::{sha256_hex, workspace_repo_root};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let check = args.iter().any(|a| a == "--check");
    let only = args.iter().position(|a| a == "--only").and_then(|i| args.get(i + 1)).cloned();
    let repo = workspace_repo_root().unwrap();
    let mut bad = 0;
    for xs in xs_files(&repo).unwrap() {
        let t = render_xs(&repo, &xs).unwrap_or_else(|e| panic!("{xs}: {e}"));
        if only.as_deref().is_some_and(|o| !t.table.ends_with(&format!("/{o}"))) {
            continue;
        }
        let sha = sha256_hex(t.dat.as_bytes());
        if sha != t.v0_sha256 {
            eprintln!("{}: rendered sha256 {sha} != v0 {}", t.table, t.v0_sha256);
            bad += 1;
            continue;
        }
        let src = format!("{}.source", t.table);
        if check {
            for (rel, text) in [(&t.table, &t.dat), (&src, &t.source)] {
                if std::fs::read(repo.join(rel)).ok().as_deref() != Some(text.as_bytes()) {
                    eprintln!("MISMATCH {rel}");
                    bad += 1;
                }
            }
        } else {
            std::fs::write(repo.join(&t.table), &t.dat).unwrap();
            std::fs::write(repo.join(&src), &t.source).unwrap();
            println!("wrote {} {sha}", t.table);
        }
    }
    if bad > 0 {
        eprintln!("{bad} problem(s)");
        std::process::exit(1);
    }
    println!("{}", if check { "check: OK" } else { "done" });
}

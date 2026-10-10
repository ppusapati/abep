//! Write (`--write NAME`) or check one own ICP table of NP-ICP-CHEM-AIR addendum_01 (A1-OWN): the `.dat`, `.dat.source`
//! and `xs/NAME.json`, rendered by the admitted writer port. Without `--write` it prints the cross-checks and the
//! IX-04 support limit (held-tail share < 1 %) of every table.

use abep_chem::icp_own::{xe_tables, OWN_DIR};
use abep_chem::reference::maxwellian_rate;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let root = abep_provenance::workspace_repo_root().expect("repository root");
    let tables = xe_tables();
    if args.len() == 2 && args[0] == "--write" {
        let t = tables.iter().find(|t| t.name == args[1]).expect("known table name");
        let (dat, src) = t.render().expect("renders");
        let xs = t.xs_text().expect("xs");
        let tp = root.join(t.table_rel());
        std::fs::create_dir_all(tp.parent().unwrap()).unwrap();
        std::fs::write(&tp, dat).unwrap();
        std::fs::write(PathBuf::from(format!("{}.source", tp.display())), src).unwrap();
        std::fs::write(root.join(OWN_DIR).join(t.xs_rel()), xs).unwrap();
        println!("wrote {}", t.name);
        return;
    }
    for t in &tables {
        let (e, s): (Vec<f64>, Vec<f64>) = t.points.iter().copied().unzip();
        let lim = abep_chem::hall_air::support_limit(&e, &s).expect("support limit");
        println!("{} ({} points): IX-04 support limit {lim} eV mean energy", t.name, t.points.len());
        for te in [0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0] {
            let k = maxwellian_rate(&e, &s, te, t.tail).expect("rate");
            println!("  T_e {te:>4} eV  k = {k:.4e} m^3/s");
        }
    }
}

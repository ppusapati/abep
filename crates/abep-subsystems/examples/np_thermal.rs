//! NP-THERMAL-CATHODELESS command-line driver (verification tooling; no production role).
//!
//! * `run <case.json>`: run one `abep_np_thermal_case_v1` document; prints the output JSON.
//! * `emit-vs-net`: print the VS-NET v1 synthetic verification input set (the registered file is this output).
//! * `verify`: run every preregistered verification item; prints the item results and the run record (JSON).

#[path = "../tests/support/mod.rs"]
mod support;

use abep_provenance::run_record::RunRecord;
use abep_provenance::workspace_repo_root;
use abep_subsystems::thermal::run_case_json;
use serde_json::json;
use support::verify;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("run") => {
            let path = args.get(2).expect("run <case.json>");
            let bytes = std::fs::read(path).expect("readable case");
            print!("{}", run_case_json(&bytes, support::gov(), &support::run_ctx()).to_json());
        }
        Some("emit-vs-net") => {
            let c = support::vs_net::build();
            print!("{}", String::from_utf8(support::vs_net::to_bytes(&c)).expect("utf-8"));
        }
        Some("verify") => {
            let record = RunRecord::capture(
                &workspace_repo_root().expect("repo root"),
                Some("NP-THERMAL-CATHODELESS/prereg_v1"),
            )
            .expect("run record");
            let al01 = verify::al_01();
            let al02 = verify::al_02();
            let al02b = verify::al_02b();
            let al03 = verify::al_03();
            let al04 = verify::al_04();
            let (al05, tau_max) = verify::al_05();
            let al06 = verify::al_06(tau_max);
            let al07 = verify::al_07();
            let al08 = verify::al_08();
            let al09 = verify::al_09();
            let al10 = verify::al_10();
            let al11 = verify::al_11();
            let iv02 = verify::iv_02();
            let orbit = verify::orbit_consistency();
            let ft = vec![
                verify::ft_01(),
                verify::ft_02(),
                verify::ft_03(),
                verify::ft_04(),
                verify::ft_05(),
                verify::ft_06(),
                verify::ft_07(),
                verify::ft_08(),
                verify::ft_09(),
                verify::ft_10(),
                verify::ft_11(),
                verify::ft_12(),
                verify::ft_13(&al10),
                verify::ft_14(&al07),
                verify::ft_15(),
                verify::ft_16(),
            ];
            let cases = verify::det_cases();
            let outs: Vec<_> = cases.iter().map(support::run).collect();
            let ft17 = verify::ft_17(&outs.iter().collect::<Vec<_>>());
            let ft18 = verify::ft_18();
            let (d1, d2, d3) = verify::det(&cases);
            let mut items = vec![al01, al02, al02b, al03, al04, al05, al06, al07, al08, al09, al10, al11];
            items.extend(ft);
            items.push(ft17);
            items.push(ft18);
            items.extend([d1, d2, d3, iv02, orbit, verify::bench_domain()]);
            let out = json!({"run_record": record, "items": items});
            println!("{}", serde_json::to_string_pretty(&out).expect("json"));
        }
        Some("iv01") => {
            // Non-authoritative cross-check data (IV-01): analytic per-case results and VS-NET steady / transient.
            let dt: f64 = args.get(2).map_or(0.025, |s| s.parse().expect("dt"));
            let t_end: f64 = args.get(3).map_or(300.0, |s| s.parse().expect("t_end"));
            let (s, t) = verify::iv01_vs_net(dt, t_end);
            let out = json!({"analytic": verify::iv01_dump(), "vs_net_steady": s, "vs_net_transient": t});
            println!("{}", serde_json::to_string(&out).expect("json"));
        }
        _ => {
            eprintln!("usage: np_thermal run <case.json> | emit-vs-net | verify | iv01 [dt t_end]");
            std::process::exit(2);
        }
    }
}

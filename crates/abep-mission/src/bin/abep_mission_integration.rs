//! NP-MISSION-INTEGRATION CLI.
//!
//! * `abep-mission-integration today [--design-point SCENARIO,L_OVER_D,PHI,AREA_M2]`: the mission integration over the
//!   frozen 196-state set with today's admitted inputs (IF-MIS-DECISIVE); writes the run JSON on stdout.
//! * `abep-mission-integration summary`: today's run reduced to per-field status counts, envelopes and layer statuses.
//! * `abep-mission-integration al-export`: the synthetic AL vectors and Rust results for the IV-01 cross-check.

use abep_mission::integration::today::{run_admitted, TodayOptions};
use abep_mission::statewise_td::DesignPoint;
use serde_json::json;
use std::io::Write;

fn usage() -> ! {
    eprintln!("usage: abep-mission-integration today|summary|al-export [--design-point SCENARIO,L_OVER_D,PHI,AREA_M2]");
    std::process::exit(2)
}

/// IV-01 export: the synthetic AL vectors (SYNTHETIC_TEST_DATA_NOT_EVIDENCE), their per-segment contributions as the
/// record holds them, and the Rust totals / ledgers, for the non-authoritative exact-rational cross-check.
fn al_export() -> serde_json::Value {
    use abep_mission::integration::model::{integrate, Mode};
    use abep_mission::integration::quantity::Field;
    use abep_mission::integration::testkit as tk;
    let repo = abep_provenance::workspace_repo_root().expect("repository root");
    let pins = abep_data::pins::FrozenPins::load(&repo).expect("pins");
    let set = abep_data::design_states::DesignStateSet::load(&repo, &pins).expect("design-state set");
    let ids: Vec<String> = set.states.iter().filter(|s| s.required).map(|s| s.state_id.clone()).collect();
    let mut cases: Vec<(String, abep_mission::integration::MissionInputs)> = vec![
        ("AL-01".into(), tk::al01(&ids)),
        ("AL-02".into(), tk::al02(&ids)),
        ("AL-03".into(), tk::al03(&ids)),
        ("AL-09".into(), tk::al09(&ids)),
    ];
    for seed in 0..200u64 {
        cases.push((format!("AL-08/seed{seed}"), tk::al08(&ids, seed)));
    }
    let mut out = Vec::new();
    for (name, inp) in cases {
        let r = integrate(&inp).expect("synthetic case integrates");
        let sch = inp.schedule.as_ref().expect("schedule");
        let mut contrib = serde_json::Map::new();
        for (total, field) in [
            ("M_atm_delivered_kg", "mdot_atm_delivered_kg_s"),
            ("M_xe_continuous_kg", "mdot_xe_tank_kg_s"),
            ("E_bus_J", "P_bus_W"),
            ("J_net_Ns", "t_minus_d_N"),
            ("Phi_AO_m2", "ao_flux_m2_s"),
        ] {
            let mut rows = Vec::new();
            for s in &sch.segments {
                let mode = Mode::parse(&s.mode).expect("mode");
                if let Some(Field::Q(q)) = r.field(&s.state_id, mode, field) {
                    rows.push(json!([q.value, s.duration_h]));
                }
            }
            contrib.insert(total.into(), json!({"rows": rows, "rust": r.schedule.totals[total].value}));
        }
        let events: Vec<_> = sch.events.iter().map(|e| json!([e.xe_kg_per_event.value, e.count])).collect();
        out.push(json!({
            "case": name,
            "contributions": contrib,
            "xe_events": {"rows": events, "rust": r.schedule.totals["M_xe_events_kg"].value},
            "M_xe_total_rust": r.schedule.totals["M_xe_total_kg"].value,
            "m_xe_loaded": r.mass.m_xe_loaded_kg.value,
            "xe_reserve": r.mass.xe_reserve_kg.value,
            "xe_residual": r.mass.xe_residual_kg.value,
            "m_dry": r.mass.m_dry_kg.value,
            "m_xe_end_rust": r.mass.m_xe_end_kg.value,
            "m_xe_usable_rust": r.mass.m_xe_usable_end_kg.value,
            "m_wet_end_rust": r.mass.m_wet_end_kg.value,
            "planning": r.mass.planning_cases.iter().map(|p| json!([p.m_xe_loaded_kg, p.m_xe_end_kg.parametric.as_ref().map(|x| x.value)])).collect::<Vec<_>>(),
            "pb_ao": [r.ao_fluence_bound.lower_m2, r.ao_fluence_bound.upper_m2],
            "statuses": {"schedule": r.schedule.status, "M_xe_total": r.schedule.totals["M_xe_total_kg"].status},
        }));
    }
    json!({"label": "SYNTHETIC_TEST_DATA_NOT_EVIDENCE", "cases": out})
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let cmd = args.first().cloned().unwrap_or_else(|| usage());
    if cmd == "al-export" {
        std::io::stdout().write_all(al_export().to_string().as_bytes()).expect("stdout");
        return;
    }
    let mut opts = TodayOptions {
        design_point: None,
        rust_commit: abep_provenance::git::Git::new(&abep_provenance::workspace_repo_root().expect("repository root"))
            .stdout(&["rev-parse", "HEAD"])
            .map(|s| s.trim().to_string())
            .unwrap_or_else(|_| "UNKNOWN".into()),
    };
    let mut it = args.iter().skip(1);
    while let Some(a) = it.next() {
        match a.as_str() {
            "--design-point" => {
                let v = it.next().unwrap_or_else(|| usage());
                let p: Vec<&str> = v.split(',').collect();
                if p.len() != 4 {
                    usage();
                }
                let f = |s: &str| s.parse::<f64>().unwrap_or_else(|_| usage());
                opts.design_point =
                    Some(DesignPoint { scenario: p[0].into(), l_over_d: f(p[1]), phi: f(p[2]), area_m2: f(p[3]) });
            }
            _ => usage(),
        }
    }
    let repo = abep_provenance::workspace_repo_root().expect("repository root");
    let run = match run_admitted(&repo, &opts) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("{e}");
            std::process::exit(1)
        }
    };
    let text = match cmd.as_str() {
        "today" => serde_json::to_string(&run).expect("serializable"),
        "summary" => serde_json::to_string_pretty(&json!({
            "model_id": run.record.model_id,
            "prereg_sha256": run.record.prereg_sha256,
            "horizons": run.record.horizons,
            "layers": run.layers,
            "n_states": run.record.status_summary.n_states,
            "worst_state_status": run.record.status_summary.worst_state_status,
            "field_status_counts": run.record.status_summary.field_status_counts,
            "reason_codes": run.record.status_summary.reason_codes,
            "envelopes": run.record.envelopes,
            "ao_fluence_bound": run.record.ao_fluence_bound,
            "schedule": run.record.schedule,
            "mass": run.record.mass,
        }))
        .expect("serializable"),
        _ => usage(),
    };
    std::io::stdout().write_all(text.as_bytes()).expect("stdout");
}

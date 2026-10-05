//! Print the raw output JSON of one verification case: `cargo run -p abep-icp --example dump_case -- <name>`.
//! Names: floating, capoff, capoff_exc, double_ion, flow, cal, n2_today, air_today, xe_today.

use abep_icp::case::{CouplingMode, RfInput, SupplyMode};
use abep_icp::chemistry::ChemistryRegistration;
use abep_icp::testkit::*;
use abep_icp::IcpModel;

fn main() {
    let m = IcpModel::load_workspace().expect("verified context");
    let name = std::env::args().nth(1).unwrap_or_else(|| "capoff".into());
    let case = match name.as_str() {
        "floating" => floating_case(50.0),
        "capoff" => capoff_case(50.0, 0.0, 30.0),
        "capoff_exc" => synthetic_case(
            "SYN_EXC",
            with_excitation(x_set(x_rate())),
            capoff_surfaces(),
            &[("ic", 0.0), ("ec", 30.0)],
            50.0,
        ),
        "double_ion" => synthetic_case(
            "SYN_X2",
            with_double_ion(x_set(x_rate())),
            capoff_surfaces(),
            &[("ic", 0.0), ("ec", 30.0)],
            50.0,
        ),
        "flow" => flow_case(50.0, 1e-6, 0.8),
        "cal" => {
            let mut c = capoff_case(0.0, 0.0, 30.0);
            c.coupling_mode = CouplingMode::Calibrated;
            c.rf_input = Some(RfInput::Forward { p_fwd_w: syn(200.0, "P_fwd"), p_refl_w: syn(10.0, "P_refl") });
            c.coupling_evidence = Some(synthetic_p2(0.50, 0.30, 2.0, 3.0));
            c.bus = Some(synthetic_bus(0.8, 0.9));
            c
        }
        "n2_today" => registered_today_case(
            SupplyMode::EmN2,
            ChemistryRegistration::RegisteredSet { config_file: "n2_n.toml".into() },
        ),
        "air_today" => {
            registered_today_case(SupplyMode::AirPrimary, ChemistryRegistration::NotRegistered { gas: "AIR".into() })
        }
        "xe_today" => {
            registered_today_case(SupplyMode::XeContingency, ChemistryRegistration::NotRegistered { gas: "XE".into() })
        }
        other => panic!("unknown case {other}"),
    };
    println!("{}", m.evaluate(&case).to_json());
}

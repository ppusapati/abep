//! Flight taxonomy of `bus_power_boundary_a9_v2` (`abep_sim/bus_boundary_a9_v2.py`; record
//! `docs/architecture_comparison/power_boundary_a9_v2/bus_power_boundary_a9_v2.json`): the slots of the selected
//! configuration `hall_icp_neutralizer`, its declared variant options, peak-class events, the dependent rise of the
//! collector bias at Hall ignition and the enforced start-up orderings. The GROUND_REFERENCE_ONLY rows of the
//! historical tables (group `c1`) are not part of the flight taxonomy (A9.30 sec. 5).

use super::pyfmt::{as_sequence, repr_str_list};
use super::{PowerError, PowerResult};
use abep_types::pyjson::{py_eq, py_repr, Value};

pub const BOUNDARY_VERSION: &str = "bus_power_boundary_a9_v2";
pub const FLIGHT_CONFIGURATION: &str = "hall_icp_neutralizer";
/// Regulated internal propulsion bus, breadboard / PPU architecture (row 111).
pub const INTERNAL_BUS_V: f64 = 100.0;
pub const TBD: &str = "TBD";
pub const POWER_BASES: [&str; 4] = ["steady_state", "step_average", "peak_sampled", "p_bus_1ms_max"];
pub const EVIDENCE_CLASSES: [&str; 7] =
    ["measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed", "owner-allocation"];
pub const PATHS: [&str; 2] = ["internal_bus", "direct"];
/// A9.1 OQ-A902-01: 1 ms moving-average window of the bus-power quantity P_bus,1ms,max.
pub const GATE_WINDOW_S: f64 = 1.0e-3;
/// A9.1 OQ-A902-01 measurement conformance: effective bandwidth and sample rate of the bus-power record.
pub const GATE_MIN_BANDWIDTH_HZ: f64 = 20.0e3;
pub const GATE_MIN_SAMPLE_RATE_SA_S: f64 = 100.0e3;
/// A9.1 OQ-A902-01: 100 ms and 1 s averages, diagnostic / energy metrics only.
pub const DIAGNOSTIC_WINDOWS_S: [f64; 2] = [0.1, 1.0];
pub const GATE_MEASUREMENT_KEYS: [&str; 5] =
    ["sample_rate_Sa_s", "bandwidth_Hz", "anti_alias_documented", "synchronized", "source"];
pub const P1MS_DEFINITION: &str = "P_bus,1ms,max = max_t (1/1 ms) integral_t^{t+1 ms} P_bus(tau) dtau";

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Group {
    Hall,
    Icp,
    Common,
    Variant,
    Reserved,
}

impl Group {
    pub fn name(self) -> &'static str {
        match self {
            Group::Hall => "hall",
            Group::Icp => "icp",
            Group::Common => "common",
            Group::Variant => "variant",
            Group::Reserved => "reserved",
        }
    }
}

/// One spacecraft-side DC load slot of the flight boundary, in the reference slot order.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Slot {
    HallDischarge,
    HallMagnetInner,
    HallMagnetOuter,
    HallMagnetTrim,
    IcpRfSource,
    IcpMatchingNetwork,
    IcpCollectorBias,
    IcpAssistMagnet,
    ActiveCooling,
    FlowControlAtmospheric,
    FlowControlXe,
    FlowControlIcpFeed,
    Compressor,
    ThermalControl,
    HousekeepingControls,
    ReservedDcPort,
}

/// (name, group, owner-answer rows, counted in the 300 W common allocation, counted in the 50 W controls / thermal
/// allowance).
type SlotRow = (&'static str, Group, &'static [i64], bool, bool);

impl Slot {
    pub const ALL: [Slot; 16] = [
        Slot::HallDischarge,
        Slot::HallMagnetInner,
        Slot::HallMagnetOuter,
        Slot::HallMagnetTrim,
        Slot::IcpRfSource,
        Slot::IcpMatchingNetwork,
        Slot::IcpCollectorBias,
        Slot::IcpAssistMagnet,
        Slot::ActiveCooling,
        Slot::FlowControlAtmospheric,
        Slot::FlowControlXe,
        Slot::FlowControlIcpFeed,
        Slot::Compressor,
        Slot::ThermalControl,
        Slot::HousekeepingControls,
        Slot::ReservedDcPort,
    ];

    fn row(self) -> SlotRow {
        match self {
            Slot::HallDischarge => ("hall_discharge", Group::Hall, &[110], false, false),
            Slot::HallMagnetInner => ("hall_magnet_inner", Group::Hall, &[110], false, false),
            Slot::HallMagnetOuter => ("hall_magnet_outer", Group::Hall, &[110], false, false),
            Slot::HallMagnetTrim => ("hall_magnet_trim", Group::Hall, &[110], false, false),
            Slot::IcpRfSource => ("icp_rf_source", Group::Icp, &[66, 72, 110], false, false),
            Slot::IcpMatchingNetwork => ("icp_matching_network", Group::Icp, &[66, 110], false, false),
            Slot::IcpCollectorBias => ("icp_collector_bias", Group::Icp, &[70, 110], false, false),
            Slot::IcpAssistMagnet => ("icp_assist_magnet", Group::Variant, &[66, 69], false, false),
            Slot::ActiveCooling => ("active_cooling", Group::Variant, &[66], false, false),
            Slot::FlowControlAtmospheric => ("flow_control_atmospheric", Group::Common, &[110], true, false),
            Slot::FlowControlXe => ("flow_control_xe", Group::Common, &[90, 110], true, false),
            Slot::FlowControlIcpFeed => ("flow_control_icp_feed", Group::Variant, &[46], true, false),
            Slot::Compressor => ("compressor", Group::Common, &[22], true, false),
            Slot::ThermalControl => ("thermal_control", Group::Common, &[114], true, true),
            Slot::HousekeepingControls => ("housekeeping_controls", Group::Common, &[114], true, true),
            Slot::ReservedDcPort => ("reserved_dc_port", Group::Reserved, &[110], false, false),
        }
    }

    pub fn name(self) -> &'static str {
        self.row().0
    }

    pub fn group(self) -> Group {
        self.row().1
    }

    pub fn rows(self) -> &'static [i64] {
        self.row().2
    }

    /// Counted in the row-114 300 W common allocation.
    pub fn common_allocation(self) -> bool {
        self.row().3
    }

    /// Counted in the 50 W controls / thermal allowance (inside the common allocation).
    pub fn controls_thermal(self) -> bool {
        self.row().4
    }

    pub fn from_name(name: &str) -> Option<Slot> {
        Slot::ALL.into_iter().find(|s| s.name() == name)
    }

    /// The slot named by a JSON key value (`None` for an unknown name).
    pub fn from_value(v: &Value) -> Option<Slot> {
        v.as_str().and_then(Slot::from_name)
    }
}

/// Base slots of `hall_icp_neutralizer` (installed without a variant option).
pub const BASE_SLOTS: [Slot; 13] = [
    Slot::HallDischarge,
    Slot::HallMagnetInner,
    Slot::HallMagnetOuter,
    Slot::HallMagnetTrim,
    Slot::IcpRfSource,
    Slot::IcpMatchingNetwork,
    Slot::IcpCollectorBias,
    Slot::FlowControlAtmospheric,
    Slot::FlowControlXe,
    Slot::Compressor,
    Slot::ThermalControl,
    Slot::HousekeepingControls,
    Slot::ReservedDcPort,
];

/// Declared variant options of `hall_icp_neutralizer`, in the reference order.
pub const VARIANT_OPTIONS: [Slot; 3] = [Slot::IcpAssistMagnet, Slot::ActiveCooling, Slot::FlowControlIcpFeed];

/// Peak-class start-up events and their slots (row 112; A9.1 SEQ-peaks), in the reference order.
pub const PEAK_EVENTS: [(&str, Slot); 6] = [
    ("compressor_spinup", Slot::Compressor),
    ("magnet_ramp", Slot::HallMagnetInner),
    ("icp_rf_ignition", Slot::IcpRfSource),
    ("icp_collector_bias_on", Slot::IcpCollectorBias),
    ("hall_discharge_ignition", Slot::HallDischarge),
    ("active_cooling_start", Slot::ActiveCooling),
];

/// A peak-class load whose rise is the physical consequence of the step's declared event (A9-10 review repair):
/// the Hall discharge current closes through the ICP collector (ICD ICP-22 / ICP-45).
pub const DEPENDENT_RISES: [(&str, &[Slot]); 1] = [("hall_discharge_ignition", &[Slot::IcpCollectorBias])];

/// Enforced orderings of `hall_icp_neutralizer` (physically necessary or owner rule).
pub const ENFORCED_ORDER: [(&str, &str); 3] = [
    ("icp_rf_ignition", "icp_collector_bias_on"),
    ("icp_rf_ignition", "hall_discharge_ignition"),
    ("magnet_ramp", "hall_discharge_ignition"),
];

pub const DEPENDENT_RISE_RULE: &str = "A9.1 SEQ-peaks counts loads COMMANDED to rise; a peak-class load whose rise \
is the physical consequence of the step's declared event (icp_collector_bias at hall_discharge_ignition: the Hall \
discharge current closes through the collector, ICD ICP-22 / ICP-45) is a dependent rise, reported and kept in the \
power gate but not counted as a second commanded peak";

pub fn peak_event_slot(event: &str) -> Option<Slot> {
    PEAK_EVENTS.iter().find(|(e, _)| *e == event).map(|(_, s)| *s)
}

/// Flight slot names in the reference order.
pub fn slot_names() -> Vec<&'static str> {
    Slot::ALL.iter().map(|s| s.name()).collect()
}

/// `installed_slots(config, variant)`: slots physically installed in the configuration with the declared variant
/// options, in slot order. `variant` is the JSON value the caller passed (a list of option names).
pub fn installed_slots(config: &Value, variant: &Value) -> PowerResult<Vec<Slot>> {
    if config.as_str() != Some(FLIGHT_CONFIGURATION) {
        return Err(PowerError::boundary(format!(
            "unknown configuration {}; {BOUNDARY_VERSION} defines ['{FLIGHT_CONFIGURATION}']",
            py_repr(config)
        )));
    }
    let Some(opts) = as_sequence(variant) else {
        return Err(PowerError::boundary(
            "variant must be a sequence of option names (use () for the base configuration)",
        ));
    };
    for o in opts {
        if matches!(o, Value::List(_) | Value::Dict(_)) {
            return Err(PowerError::new("TypeError", format!("unhashable type: '{}'", o.type_name())));
        }
    }
    let distinct = opts.iter().enumerate().all(|(i, a)| opts[..i].iter().all(|b| !py_eq(a, b)));
    if !distinct {
        return Err(PowerError::boundary(format!("duplicate variant option in {}", py_repr(variant))));
    }
    let mut chosen = Vec::new();
    for o in opts {
        match o.as_str().and_then(Slot::from_name).filter(|s| VARIANT_OPTIONS.contains(s)) {
            Some(s) => chosen.push(s),
            None => {
                return Err(PowerError::boundary(format!(
                    "variant option {} is not declared for '{FLIGHT_CONFIGURATION}' (allowed {}); a new variant \
                     needs a controlled change",
                    py_repr(o),
                    repr_str_list(&VARIANT_OPTIONS.iter().map(|s| s.name()).collect::<Vec<_>>())
                )))
            }
        }
    }
    Ok(Slot::ALL.into_iter().filter(|s| BASE_SLOTS.contains(s) || chosen.contains(s)).collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_round_trip_and_are_unique() {
        for s in Slot::ALL {
            assert_eq!(Slot::from_name(s.name()), Some(s));
        }
        let mut n = slot_names();
        n.sort_unstable();
        n.dedup();
        assert_eq!(n.len(), 16);
    }

    #[test]
    fn installed_slots_of_the_flight_configuration() {
        let cfg = Value::str(FLIGHT_CONFIGURATION);
        assert_eq!(installed_slots(&cfg, &Value::List(vec![])).unwrap(), BASE_SLOTS.to_vec());
        let all = Value::List(VARIANT_OPTIONS.iter().map(|s| Value::str(s.name())).collect());
        assert_eq!(installed_slots(&cfg, &all).unwrap(), Slot::ALL.to_vec());
        let e = installed_slots(&Value::str("hall_c1_reference"), &Value::List(vec![])).unwrap_err();
        assert_eq!(e.class, "BoundaryA9Error");
        assert!(e.message.starts_with("unknown configuration 'hall_c1_reference'"));
    }
}

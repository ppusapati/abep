//! Synthetic verification vectors of NP-MISSION-INTEGRATION v1 (prereg analytic_limiting_cases AL-01..AL-11). Every
//! value here is SYNTHETIC_TEST_DATA_NOT_EVIDENCE: state ids come from the frozen set, rates and horizons do not.
//! Used by the crate tests and by the IV-01 export of `abep-mission-integration al-export`.

use super::model::{
    EnvState, EnvValues, Event, Horizons, IcpGasMode, MassInputs, MissionInputs, Mode, PlanningCase, Provenance,
    Schedule, Segment, StateModeInputs, INPUT_KEYS,
};
use super::quantity::{Label, Quantity, Reason};
use super::ARCHITECTURE;
use abep_types::EvalStatus;
use std::collections::BTreeMap;

pub const SYN: &str = "SYNTHETIC_TEST_DATA_NOT_EVIDENCE";

pub fn syn(units: &str, v: f64) -> Quantity {
    Quantity::evaluated(units, v, SYN, "synthetic").expect("finite synthetic value")
}

pub fn syn_absent(units: &str, status: EvalStatus, code: &str) -> Quantity {
    Quantity::absent(units, Reason::new(code, status, "synthetic fail-closed input")).expect("absent")
}

pub fn horizons(h_m: f64, h_f: f64) -> Horizons {
    Horizons {
        mission_hours_h: h_m,
        mission_hours_label: "MISSION_DURATION_BASIS".into(),
        firing_hours_h: h_f,
        firing_hours_label: "SUBSYSTEM_FIRING_LIFE_ASSUMPTION".into(),
        source: SYN.into(),
    }
}

/// Synthetic environment on the given state ids: n_O = 1e15 (1 + i / 7), V = 7800 - i / 3 m/s.
pub fn env(ids: &[String]) -> Vec<EnvState> {
    ids.iter()
        .enumerate()
        .map(|(i, id)| {
            let f = i as f64;
            EnvState {
                state_id: id.clone(),
                required: true,
                nominal_mission_scenario: false,
                labels: vec![],
                status: EvalStatus::Evaluated,
                reasons: vec![],
                values: Some(EnvValues {
                    alt_km: 200.0,
                    rho_kg_m3: 1e-10 * (1.0 + f / 5.0),
                    fO: 0.5,
                    fN2: 0.45,
                    fO2: 0.05,
                    n_O_m3: 1e15 * (1.0 + f / 7.0),
                    T_K: 900.0,
                    v_orbital_m_s: 7800.0 - f / 3.0,
                }),
                source: SYN.into(),
            }
        })
        .collect()
}

/// The registered synthetic value of an INPUT key at state index `i`.
pub fn rate(key: &str, i: usize) -> f64 {
    let f = i as f64;
    match key {
        "intake_capture_kg_s" => 3e-6 * (1.0 + f / 10.0),
        "drag_intake_N" => 0.004,
        "p_feed_Pa" => 0.1,
        "T_feed_K" => 300.0,
        "mdot_atm_delivered_kg_s" => 2e-6 * (1.0 + f / 10.0),
        "mdot_hall_anode_kg_s" => 1e-6 * (1.0 + f / 20.0),
        "mdot_icp_dedicated_kg_s" => 1e-8,
        "I_d_A" => 5.0,
        "I_ecap_A" => 6.0,
        "P_bus_W" => 1000.0 + f,
        "thrust_N" => 0.012,
        "drag_body_N" => 0.003,
        "thermal_t_max_K" => 400.0,
        other => panic!("no synthetic rate for {other}"),
    }
}

/// Inputs with every INPUT field EVALUATED at its synthetic rate, no schedule, Xe load 5 kg, dry 30 kg.
pub fn inputs(ids: &[String], gas: IcpGasMode) -> MissionInputs {
    let mut states = BTreeMap::new();
    for (i, id) in ids.iter().enumerate() {
        for mode in Mode::ALL {
            let mut q = BTreeMap::new();
            for k in super::model::required_inputs(mode) {
                let u = INPUT_KEYS.iter().find(|(x, _)| *x == k).map(|(_, u)| *u).unwrap_or("-");
                q.insert(k.to_string(), syn(u, rate(k, i)));
            }
            let hall_state = mode.firing().then(|| Label {
                status: EvalStatus::Evaluated,
                label: Some("SYN-MEMBER/OP-1".into()),
                source: SYN.into(),
                reasons: vec![],
            });
            states.insert((id.clone(), mode), StateModeInputs { quantities: q, hall_state });
        }
    }
    MissionInputs {
        configuration: ARCHITECTURE.into(),
        horizons: horizons(26280.0, 15000.0),
        env: env(ids),
        icp_gas_mode: gas,
        states,
        mass: MassInputs {
            m_dry_kg: syn("kg", 30.0),
            m_xe_loaded_kg: syn("kg", 5.0),
            xe_planning_cases: vec![
                PlanningCase { m_xe_kg: 2.0, source: SYN.into() },
                PlanningCase { m_xe_kg: 5.0, source: SYN.into() },
                PlanningCase { m_xe_kg: 10.0, source: SYN.into() },
            ],
            xe_reserve_kg: syn("kg", 0.5),
            xe_residual_kg: syn("kg", 0.25),
        },
        schedule: None,
        provenance: Provenance { rust_commit: SYN.into(), input_hashes: BTreeMap::new() },
    }
}

pub fn seg(id: &str, mode: &str, state: &str, h: f64) -> Segment {
    Segment { segment_id: id.into(), mode: mode.into(), state_id: state.into(), duration_h: h }
}

pub fn schedule(segments: Vec<Segment>, events: Vec<Event>) -> Schedule {
    Schedule { segments, events, evidence_class: SYN.into(), source: SYN.into() }
}

/// Set every (state, mode) value of `key` to `q`.
pub fn set_all(inp: &mut MissionInputs, key: &str, q: Quantity) {
    for v in inp.states.values_mut() {
        if v.quantities.contains_key(key) {
            v.quantities.insert(key.to_string(), q.clone());
        }
    }
}

/// AL-01: constant rate 1e-6 kg/s; AIR 15,000 h on one state and NON_FIRING 11,280 h.
pub fn al01(ids: &[String]) -> MissionInputs {
    let mut inp = inputs(ids, IcpGasMode::GReuse);
    set_all(&mut inp, "mdot_atm_delivered_kg_s", syn("kg s-1", 1e-6));
    inp.schedule = Some(schedule(
        vec![seg("A", "AIR_PRIMARY", &ids[0], 15000.0), seg("C", "NON_FIRING", &ids[1], 11280.0)],
        vec![],
    ));
    inp
}

/// AL-02: 50 segments over 10 states (15 AIR x 600 h, 10 XE x 600 h, 20 x 451.5 h + 5 x 450 h NON_FIRING).
pub fn al02(ids: &[String]) -> MissionInputs {
    let mut inp = inputs(&ids[..10], IcpGasMode::GXe);
    let mut s = Vec::new();
    for k in 0..50 {
        let st = &ids[k % 10];
        let (mode, h) = match k {
            0..=14 => ("AIR_PRIMARY", 600.0),
            15..=24 => ("XE_CONTINGENCY", 600.0),
            25..=44 => ("NON_FIRING", 451.5),
            _ => ("NON_FIRING", 450.0),
        };
        s.push(seg(&format!("S{k:02}"), mode, st, h));
    }
    let ev = Event {
        event_id: "E1".into(),
        segment_id: "S15".into(),
        kind: "START_ATTEMPT".into(),
        count: 3,
        xe_kg_per_event: syn("kg", 1e-4),
        atm_kg_per_event: syn("kg", 0.0),
    };
    inp.schedule = Some(schedule(s, vec![ev]));
    inp
}

/// AL-03: Xe ledger. m_xe,0 = 5 kg; XE 100 h at 1e-6 kg/s; 3 start attempts at 1e-4 kg; reserve 0.5, residual 0.25.
pub fn al03(ids: &[String]) -> MissionInputs {
    let mut inp = inputs(ids, IcpGasMode::GReuse);
    set_all(&mut inp, "mdot_hall_anode_kg_s", syn("kg s-1", 1e-6));
    let ev = Event {
        event_id: "E1".into(),
        segment_id: "X".into(),
        kind: "START_ATTEMPT".into(),
        count: 3,
        xe_kg_per_event: syn("kg", 1e-4),
        atm_kg_per_event: syn("kg", 0.0),
    };
    inp.horizons = horizons(26280.0, 15000.0);
    inp.schedule = Some(schedule(
        vec![
            seg("X", "XE_CONTINGENCY", &ids[0], 100.0),
            seg("A", "AIR_PRIMARY", &ids[1], 14900.0),
            seg("C", "NON_FIRING", &ids[2], 11280.0),
        ],
        vec![ev],
    ));
    inp
}

/// Deterministic generator for AL-08 schedules (SplitMix64; SYNTHETIC).
pub struct SynRng(u64);

impl SynRng {
    pub fn new(seed: u64) -> Self {
        SynRng(seed)
    }
    pub fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
}

/// AL-08: a random schedule over all `ids` realising H_M = 26,280 h / H_F = 15,000 h exactly with integer-hour
/// segments (seeded; SYNTHETIC).
pub fn al08(ids: &[String], seed: u64) -> MissionInputs {
    let mut inp = inputs(ids, IcpGasMode::GReuse);
    let mut r = SynRng::new(seed);
    let mut s = Vec::new();
    for (mode, total) in [("AIR_PRIMARY", 15000u64), ("NON_FIRING", 11280u64)] {
        let mut left = total;
        let mut k = 0;
        while left > 0 {
            let h = (1 + r.next_u64() % 900).min(left);
            let st = &ids[(r.next_u64() % ids.len() as u64) as usize];
            s.push(seg(&format!("{mode}-{k}"), mode, st, h as f64));
            left -= h;
            k += 1;
        }
    }
    inp.schedule = Some(schedule(s, vec![]));
    inp
}

/// AL-09: rates +1e20, -1e20 and 1.0 kg/s on three 1 h AIR segments (plus the remaining hours at zero rate).
pub fn al09(ids: &[String]) -> MissionInputs {
    let mut inp = inputs(&ids[..4], IcpGasMode::GReuse);
    for (i, v) in [1e20, -1e20, 1.0, 0.0].into_iter().enumerate() {
        inp.states
            .get_mut(&(ids[i].clone(), Mode::AirPrimary))
            .expect("cell")
            .quantities
            .insert("mdot_atm_delivered_kg_s".into(), syn("kg s-1", v));
    }
    inp.schedule = Some(schedule(
        vec![
            seg("P", "AIR_PRIMARY", &ids[0], 1.0),
            seg("M", "AIR_PRIMARY", &ids[1], 1.0),
            seg("O", "AIR_PRIMARY", &ids[2], 1.0),
            seg("Z", "AIR_PRIMARY", &ids[3], 14997.0),
            seg("C", "NON_FIRING", &ids[3], 11280.0),
        ],
        vec![],
    ));
    inp
}

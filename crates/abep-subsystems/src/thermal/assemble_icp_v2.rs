//! Model 2.0.0: the IF-ICP-THERMAL-v2 consumer (NP-THERMAL-CATHODELESS prereg v2 `matched_interface`, E-07 v2,
//! CONS-I3, FT-19..FT-23). A child of `assemble`: it reuses the v1 helpers (reasons, registered partitions, node
//! receivers) and changes none of them. Every watt of the ICP slot loads lands on exactly one destination class: a
//! node, the RX-H1-FACE receivers, EXPORT or a B_PPU_RF sub-account (RF_SOURCE, RF_CHAIN); nothing is a remainder.

use super::super::governance::{KEY_TABLE_V2_SHA256, PRODUCER_LOCK_SHA256};
use super::super::output::IcpV2Derived;
use super::*;
use vocab::DepositionV2;

const RF_SOURCE: &str = "RF_SOURCE";
const RF_CHAIN: &str = "RF_CHAIN";

/// One key's destinations per time index: node values, exported, booked (sub-account).
struct Dest {
    nodes: Vec<(usize, Vec<f64>)>,
    export: Vec<f64>,
    booked: Option<(&'static str, Vec<f64>)>,
}

fn eps_if(reference: f64) -> f64 {
    EPS_IF_REL * reference.abs() + EPS_IF_ABS
}

impl Asm<'_> {
    /// Parse one value-record value: one number (STEADY) or one per breakpoint (ZOH_SERIES).
    fn v2_values(v: Option<&Value>, n: usize, zoh: bool) -> Option<Vec<f64>> {
        let parsed: Option<Vec<f64>> = match (zoh, v) {
            (false, Some(Value::Number(x))) => x.as_f64().map(|v| vec![v]),
            (true, Some(Value::Array(a))) if a.len() == n => a.iter().map(Value::as_f64).collect(),
            _ => None,
        };
        parsed.filter(|v| v.iter().all(|x| x.is_finite()))
    }

    /// The model 2.0.0 IF-ICP-THERMAL-v2 deposition. Returns the consumer bookkeeping when the record is consumed.
    #[allow(clippy::too_many_lines)]
    pub(super) fn icp_v2(
        &mut self,
        rec: &InterfaceRecordV2,
        sources: &mut Vec<SourceC>,
        exported: &mut BTreeMap<String, Vec<f64>>,
        booked: &mut BTreeMap<String, Vec<f64>>,
        breakpoints: &mut Vec<f64>,
    ) -> Option<IcpV2Derived> {
        let c = self.case;
        let id = vocab::ICP_V2_INTERFACE_ID;
        // IFI2-10: interface identity.
        if rec.interface_id != id {
            self.me(
                "INTERFACE_VERSION_MISMATCH",
                id,
                format!("{:?}: model 2.0.0 consumes {id} only (IFI2-10)", rec.interface_id),
            );
            return None;
        }
        // IFI2-01: header.
        let mut ok = true;
        if rec.producer_id != vocab::ICP_PRODUCER_ID {
            self.me("INTERFACE_PRODUCER", id, format!("producer {:?}", rec.producer_id));
            ok = false;
        }
        if rec.producer_version != "2" {
            self.me(
                "INTERFACE_VERSION_MISMATCH",
                id,
                format!("producer_version {:?}, expected \"2\"", rec.producer_version),
            );
            ok = false;
        }
        if rec.producer_lock_sha256 != PRODUCER_LOCK_SHA256 {
            self.me(
                "IFI2-01_PRODUCER_LOCK_MISMATCH",
                id,
                format!("{} != the anchor {PRODUCER_LOCK_SHA256}", rec.producer_lock_sha256),
            );
            ok = false;
        }
        if rec.key_table_sha256 != KEY_TABLE_V2_SHA256 {
            self.me("IFI2-01_KEY_TABLE_MISMATCH", id, format!("{} != {KEY_TABLE_V2_SHA256}", rec.key_table_sha256));
            ok = false;
        }
        for (f, v) in [("operating_point_id", &rec.operating_point_id), ("scenario_member_id", &rec.scenario_member_id)]
        {
            if v.is_empty() {
                self.me("INTERFACE_FIELD_MISSING", id, f);
                ok = false;
            }
        }
        if rec.case_id != c.case_id
            || rec.case_class != c.case_class
            || rec.supply_mode != c.supply_mode
            || rec.design_state_id != c.design_state_id
        {
            self.me(
                "INTERFACE_CASE_MISMATCH",
                id,
                "case_id / case_class / supply_mode / design_state_id differ from the case",
            );
            ok = false;
        }
        // IFI2-11: configuration scope.
        if rec.configuration == "CFG-FLIGHT-HALL-ON" {
            self.push(
                RunStatus::NotEvaluated,
                "CPL_HALL_ON_CONSUMER_VERSION_NOT_REGISTERED",
                id,
                "IFI2-11 / FT-21: a CFG-FLIGHT-HALL-ON record needs CPL-HALL-ON and a matched consumer version of its coupling keys",
            );
            return None;
        }
        if !vocab::ICP_V2_CONFIGURATIONS.contains(&rec.configuration.as_str()) {
            self.me("INTERFACE_CONFIGURATION", id, format!("{:?} (IFI2-11)", rec.configuration));
            ok = false;
        }
        let bp = match (rec.time_basis.kind.as_str(), &rec.time_basis.breakpoints_s) {
            ("STEADY", None) => None,
            ("ZOH_SERIES", Some(t)) if (TimeValue::Zoh { t: t.clone(), v: vec![0.0; t.len()] }).check().is_ok() => {
                Some(t.clone())
            }
            _ => {
                self.me(
                    "INTERFACE_TIME_BASIS",
                    id,
                    "STEADY (no breakpoints) or ZOH_SERIES (strictly increasing breakpoints_s)",
                );
                return None;
            }
        };
        let n = bp.as_ref().map_or(1, Vec::len);
        let tv = |v: &[f64]| match &bp {
            None => TimeValue::Constant(v[0]),
            Some(t) => TimeValue::Zoh { t: t.clone(), v: v.to_vec() },
        };
        // Keys (IFI2-01, IFI2-02, IFI2-10).
        let mut vals: BTreeMap<&'static str, Option<Vec<f64>>> = BTreeMap::new();
        let mut any_eval_nonmeasured = false;
        for (k, vr) in &rec.keys {
            if vocab::ICP_V2_RETIRED_KEYS.contains(&k.as_str()) {
                self.me("RETIRED_KEY", k, "IFI2-10 / FT-19: a retired key is never consumed");
                ok = false;
                continue;
            }
            if vocab::icp_v2_energy_source_violation(k) {
                self.me(
                    "ENERGY_SOURCE_RULE",
                    k,
                    "IFI2-10: Hall-powered and CPL-HALL-ON circuit heat never enters an ICP key",
                );
                ok = false;
                continue;
            }
            let Some(row) = vocab::icp_v2_key(k) else {
                self.me(
                    "INTERFACE_KEY_NOT_REGISTERED",
                    k,
                    format!("not a key of {id}; a new key needs a new interface version"),
                );
                ok = false;
                continue;
            };
            let missing: Vec<&str> = [
                ("units", vr.units.is_some()),
                ("status", vr.status.is_some()),
                ("evidence_class", vr.evidence_class.is_some()),
                ("source", vr.source.is_some()),
                ("uncertainty", vr.uncertainty.is_some()),
                ("applicability_domain", vr.applicability_domain.is_some()),
                ("validation_status", vr.validation_status.is_some()),
            ]
            .into_iter()
            .filter(|(_, p)| !p)
            .map(|(f, _)| f)
            .collect();
            if !missing.is_empty() {
                self.me("VALUE_RECORD_FIELD_MISSING", k, missing.join(", "));
                ok = false;
                continue;
            }
            if vr.units.as_deref() != Some("W") {
                self.me("VALUE_RECORD_UNITS_MISMATCH", k, format!("{:?}, registered \"W\"", vr.units));
                ok = false;
                continue;
            }
            if vr.hall_map.is_some() {
                self.me("VALUE_RECORD_FIELD_NOT_APPLICABLE", k, "hall_map provenance belongs to IF-HALL-THERMAL-v1");
                ok = false;
            }
            let status = vr.status.clone().unwrap_or_default();
            if !vocab::VALUE_STATUSES.contains(&status.as_str()) {
                self.me("VALUE_RECORD_STATUS_UNKNOWN", k, status);
                ok = false;
                continue;
            }
            let ec = vr.evidence_class.clone().unwrap_or_default();
            self.check_evidence_class(&ec, k);
            if status == "EVALUATED" {
                match Self::v2_values(vr.value.as_ref(), n, bp.is_some()) {
                    Some(v) => {
                        if !row.signed && v.iter().any(|x| *x < 0.0) {
                            self.me("IFI2-02_VIOLATED", k, "every key except TK-12 / TK-13 is >= 0");
                            ok = false;
                        }
                        if ec != "measured" {
                            any_eval_nonmeasured = true;
                        }
                        vals.insert(row.key, Some(v));
                    }
                    None => {
                        self.me(
                            "VALUE_RECORD_VALUE_SHAPE",
                            k,
                            "EVALUATED needs a finite number (STEADY) or one per breakpoint",
                        );
                        ok = false;
                    }
                }
            } else {
                if vr.value.as_ref().is_some_and(|v| !v.is_null()) {
                    self.me("VALUE_RECORD_VALUE_SHAPE", k, format!("status {status} carries no value (no zero-fill)"));
                    ok = false;
                }
                let (st, code) = match status.as_str() {
                    "NOT_EVALUATED" => (RunStatus::NotEvaluated, "INTERFACE_KEY_NOT_EVALUATED"),
                    "INCOMPLETE_EVIDENCE" => (RunStatus::IncompleteEvidence, "INTERFACE_KEY_INCOMPLETE_EVIDENCE"),
                    "OUT_OF_DOMAIN" => (RunStatus::OutOfDomain, "INTERFACE_KEY_OUT_OF_DOMAIN"),
                    _ => (RunStatus::ModelError, "INTERFACE_KEY_MODEL_ERROR"),
                };
                self.push(st, code, k, format!("{id} key status {status} propagates to the run (FT-18)"));
                vals.insert(row.key, None);
            }
        }
        for row in vocab::ICP_V2_KEYS.iter() {
            if !rec.keys.contains_key(row.key) {
                self.me("INTERFACE_KEY_MISSING", row.key, format!("IFI2-01: {} is present in every record", row.id));
                ok = false;
            }
        }
        for k in rec.node_shares_w.keys() {
            if !matches!(vocab::icp_v2_key(k).map(|r| r.deposition), Some(DepositionV2::ProducerShares)) {
                self.me("PARTITION_KEY_NOT_REGISTERED", k, "producer node shares exist for TK-07 and TK-12 only");
                ok = false;
            }
        }
        if !ok {
            return None;
        }
        // Inherited gates: flight / bench admission (NE-02) and NON_FIRING zeros (AS-03).
        let (flight, bench) = (c.case_class == "FLIGHT_CONDITIONAL", c.case_class == "BENCH_REPLICA");
        if (flight || bench) && any_eval_nonmeasured && !self.gov.admitted_icp_producers().contains(&rec.producer_id) {
            self.push(
                RunStatus::NotEvaluated,
                "NP_ICP_NEUTRALIZER_NOT_ADMITTED",
                id,
                "RF/ICP heat must come from an admitted NP-ICP-NEUTRALIZER model_version 2 or measured data (NE-02)",
            );
        }
        if c.supply_mode == "NON_FIRING" {
            for (k, v) in &vals {
                if v.as_ref().is_some_and(|v| v.iter().any(|x| *x != 0.0)) {
                    self.me("NON_FIRING_LOAD_NOT_ZERO", k, "NON_FIRING registers zero RF / ICP keys (AS-03)");
                }
            }
        }
        let ev = |k: &str| vals.get(k).and_then(|v| v.clone());
        let mut d = IcpV2Derived { scenario_member_id: rec.scenario_member_id.clone(), ..Default::default() };
        let mut dest_ok = true;
        let mut i2_fail = false;
        let mut sum_dest: Vec<f64> = vec![0.0; n];
        let mut share_nodes: BTreeMap<usize, Vec<f64>> = BTreeMap::new();
        for row in vocab::ICP_V2_KEYS.iter() {
            let key = row.key;
            match row.deposition {
                DepositionV2::Reference => continue,
                DepositionV2::Variant { out_of_domain } => {
                    if ev(key).is_some_and(|v| v.iter().any(|x| *x != 0.0)) {
                        if out_of_domain {
                            self.push(
                                RunStatus::OutOfDomain,
                                "VARIANT_INSTALLED_OUT_OF_DOMAIN",
                                key,
                                format!("{}: installed assist magnet (D-05, FT-12)", row.id),
                            );
                        } else {
                            self.push(
                                RunStatus::IncompleteEvidence,
                                "VARIANT_RECEIVER_NOT_REGISTERED",
                                key,
                                format!("{}: an installed variant needs a registered receiver", row.id),
                            );
                        }
                    }
                    continue;
                }
                _ => {}
            }
            let registered = c.partitions.get(key).cloned();
            let Some(v) = ev(key) else {
                dest_ok = false;
                continue;
            };
            let weighted = |s: &mut Self,
                            g: Option<BTreeMap<String, f64>>,
                            allowed: &[&str],
                            export_ok: bool,
                            boundary_ok: bool| {
                g.and_then(|g| s.partition(key, &g, allowed, export_ok, boundary_ok))
            };
            let mut nodes_w: Vec<(usize, f64)> = Vec::new();
            let (mut wexp, mut wbk): (f64, f64) = (0.0, 0.0);
            let mut sub: &'static str = RF_CHAIN;
            let mut shares: Option<Vec<(usize, Vec<f64>)>> = None;
            let resolved = match row.deposition {
                DepositionV2::BookedRfSource => {
                    sub = RF_SOURCE;
                    wbk = 1.0;
                    if registered.is_some() {
                        self.me("PARTITION_NOT_REGISTERED_FOR_KEY", key, "booked at B_PPU_RF RF_SOURCE (no partition)");
                        false
                    } else {
                        true
                    }
                }
                DepositionV2::LineRule => match registered {
                    None => {
                        wbk = 1.0;
                        true
                    }
                    Some(rid) => {
                        let g = self.weights(&rid, key);
                        match weighted(self, g, &["N_MATCH"], false, true) {
                            Some((nw, _, b)) => {
                                nodes_w = nw;
                                wbk = b;
                                true
                            }
                            None => false,
                        }
                    }
                },
                DepositionV2::MatchRule => {
                    if registered.is_some() {
                        self.me("PARTITION_NOT_REGISTERED_FOR_KEY", key, "N_MATCH iff match_colocated, else RF_CHAIN");
                        false
                    } else if c.match_colocated == Some(true) {
                        match self.node_index.get("N_MATCH").copied() {
                            Some(i) => {
                                nodes_w.push((i, 1.0));
                                true
                            }
                            None => {
                                self.me("LOAD_RECEIVER_ABSENT", key, "match_colocated = true without N_MATCH");
                                false
                            }
                        }
                    } else {
                        wbk = 1.0;
                        true
                    }
                }
                DepositionV2::RegisteredSplit(allowed) => match registered {
                    None => {
                        self.push(
                            RunStatus::IncompleteEvidence,
                            "TK-06_SPLIT_NOT_REGISTERED",
                            key,
                            "FT-20: no registered conductor split (no default split)",
                        );
                        false
                    }
                    Some(rid) => {
                        let g = self.weights(&rid, key);
                        match weighted(self, g, allowed, false, false) {
                            Some((nw, _, _)) => {
                                nodes_w = nw;
                                true
                            }
                            None => false,
                        }
                    }
                },
                DepositionV2::RegisteredWithExport(allowed) => match registered {
                    None => {
                        self.push(
                            RunStatus::IncompleteEvidence,
                            "PARTITION_MISSING",
                            key,
                            "f_rad is not registered (E-07 v2, NE-10)",
                        );
                        false
                    }
                    Some(rid) => {
                        let g = self.weights(&rid, key);
                        match weighted(self, g, allowed, true, false) {
                            Some((nw, e, _)) => {
                                nodes_w = nw;
                                wexp = e;
                                true
                            }
                            None => false,
                        }
                    }
                },
                DepositionV2::RxH1Face(allowed) => match registered {
                    None if v.iter().all(|x| *x == 0.0) => true,
                    None => {
                        self.push(
                            RunStatus::IncompleteEvidence,
                            "RX-H1-FACE_PARTITION_NOT_REGISTERED",
                            key,
                            "FT-20: Q_icp_outflow_upstream_W > 0 without a registered f_up",
                        );
                        false
                    }
                    Some(rid) => {
                        let g = self.weights(&rid, key);
                        match weighted(self, g, allowed, true, false) {
                            Some((nw, e, _)) => {
                                nodes_w = nw;
                                wexp = e;
                                true
                            }
                            None => false,
                        }
                    }
                },
                DepositionV2::Export => {
                    wexp = 1.0;
                    if registered.is_some() {
                        self.me("PARTITION_NOT_REGISTERED_FOR_KEY", key, "EXPORT (no partition)");
                        false
                    } else {
                        true
                    }
                }
                DepositionV2::ProducerShares => {
                    if registered.is_some() {
                        self.me(
                            "PARTITION_NOT_REGISTERED_FOR_KEY",
                            key,
                            "the producer partitions this key (the v1 f_pw fallback is retired)",
                        );
                        false
                    } else {
                        match rec.node_shares_w.get(key) {
                            None => {
                                self.me(
                                    "IFI2-01_PRODUCER_PARTITION_MISSING",
                                    key,
                                    "TK-07 / TK-12 are always emitted with their per-node partition",
                                );
                                false
                            }
                            Some(m) => {
                                let mut out = Vec::new();
                                let mut good = true;
                                for (node, val) in m {
                                    let Some(&i) = self.node_index.get(node) else {
                                        self.me(
                                            "PARTITION_RECEIVER_UNKNOWN",
                                            key,
                                            format!("{node:?} is not a node of the case"),
                                        );
                                        good = false;
                                        continue;
                                    };
                                    let reg = self.nodes[i].base.is_some_and(|b| vocab::icp_v2_receives(b.id, key));
                                    if !reg {
                                        self.me(
                                            "PARTITION_RECEIVER_NOT_REGISTERED",
                                            key,
                                            format!("{node} is not a registered receiver"),
                                        );
                                        good = false;
                                        continue;
                                    }
                                    if !self.nodes[i].receives.contains(key) {
                                        self.me(
                                            "PARTITION_RECEIVER_NOT_DECLARED",
                                            key,
                                            format!("{node} does not list {key}"),
                                        );
                                        good = false;
                                        continue;
                                    }
                                    match Self::v2_values(Some(val), n, bp.is_some()) {
                                        Some(x) => {
                                            if !row.signed && x.iter().any(|y| *y < 0.0) {
                                                self.me(
                                                    "IFI2-02_VIOLATED",
                                                    key,
                                                    format!("{node}: a share of an unsigned key is < 0"),
                                                );
                                                good = false;
                                            }
                                            out.push((i, x));
                                        }
                                        None => {
                                            self.me("VALUE_RECORD_VALUE_SHAPE", key, format!("node share {node}"));
                                            good = false;
                                        }
                                    }
                                }
                                // IFI2-08: the producer partition sums to its key.
                                for j in 0..n {
                                    let s: f64 = out.iter().map(|(_, x)| x[j]).sum();
                                    if (s - v[j]).abs() > eps_if(v[j]) {
                                        self.me(
                                            "IFI2-08_VIOLATED",
                                            key,
                                            format!("node shares sum {s} != key {} (index {j})", v[j]),
                                        );
                                        good = false;
                                    }
                                }
                                shares = Some(out);
                                good
                            }
                        }
                    }
                }
                DepositionV2::Reference | DepositionV2::Variant { .. } => unreachable!("handled above"),
            };
            if !resolved {
                dest_ok = false;
                continue;
            }
            let dest = match shares {
                Some(s) => Dest { nodes: s, export: vec![0.0; n], booked: None },
                None => Dest {
                    nodes: nodes_w.iter().map(|(i, w)| (*i, v.iter().map(|x| w * x).collect())).collect(),
                    export: v.iter().map(|x| wexp * x).collect(),
                    booked: (wbk > 0.0).then(|| (sub, v.iter().map(|x| wbk * x).collect())),
                },
            };
            // E-07 v2 / CONS-I2: every destination share sums to the key.
            let mut rows: [Vec<f64>; 3] = [vec![0.0; n], dest.export.clone(), vec![0.0; n]];
            for (i, x) in &dest.nodes {
                if !vocab::icp_v2_receives(self.nodes[*i].base.map_or("", |b| b.id), key)
                    || !self.nodes[*i].receives.contains(key)
                {
                    self.me(
                        "NODE_RECEIVES_NOT_DECLARED",
                        key,
                        format!("{} is not a registered and declared receiver", c.nodes[*i].id),
                    );
                    dest_ok = false;
                }
                for j in 0..n {
                    rows[0][j] += x[j];
                }
                sources.push(SourceC {
                    node: *i,
                    label: key.to_string(),
                    weight: 1.0,
                    tv: tv(x),
                    kind: SourceKind::Interface,
                });
                if matches!(row.deposition, DepositionV2::ProducerShares) {
                    let e = share_nodes.entry(*i).or_insert_with(|| vec![0.0; n]);
                    for j in 0..n {
                        e[j] += x[j];
                    }
                }
            }
            if let Some((sub, b)) = &dest.booked {
                rows[2] = b.clone();
                booked.insert(format!("{sub}:{key}"), b.clone());
                let acc = d.b_ppu_rf_sub_account_w.entry(sub.to_string()).or_insert_with(|| vec![0.0; n]);
                for j in 0..n {
                    acc[j] += b[j];
                }
            }
            if dest.export.iter().any(|x| *x != 0.0) || matches!(row.deposition, DepositionV2::Export) {
                let name = if matches!(row.deposition, DepositionV2::Export) {
                    key.to_string()
                } else {
                    format!("{key}.EXPORT")
                };
                exported.insert(name, dest.export.clone());
            }
            for j in 0..n {
                let tot = rows[0][j] + rows[1][j] + rows[2][j];
                let bound = if shares_key(row) { eps_if(v[j]) } else { CONS_I2_REL * v[j].abs() + CONS_I2_ABS };
                if (tot - v[j]).abs() > bound {
                    i2_fail = true;
                }
                sum_dest[j] += tot;
            }
            d.deposition.insert(key.to_string(), rows);
        }
        if i2_fail {
            self.me("CONS_I2_NOT_MET", id, "a key's destinations do not sum to the key (E-07 v2)");
        }
        // IFI2-08: per node, the TK-07 share + the TK-12 share >= -eps_if.
        for (i, x) in &share_nodes {
            let node = c.nodes[*i].id.clone();
            for (j, t) in x.iter().enumerate() {
                let reference = ev("Q_icp_plasma_wall_W").map_or(0.0, |v| v[j]);
                if *t < -eps_if(reference) {
                    self.me(
                        "IFI2-08_VIOLATED",
                        &node,
                        format!("TK-07 + TK-12 node total {t} W < 0 (FT-22, index {j})"),
                    );
                }
            }
            d.node_total_w.insert(node, x.clone());
        }
        // IFI2-03..IFI2-07: exact identities within eps_if.
        let ids: [(&str, &str, &[&str]); 5] = [
            ("IFI2-03", "P_icp_rf_source_DC_W", &["Q_icp_rf_conversion_loss_W", "P_icp_rf_forward_W"]),
            (
                "IFI2-04",
                "P_icp_rf_forward_W",
                &["P_icp_rf_reflected_W", "Q_icp_line_W", "Q_icp_match_W", "Q_icp_coil_ohmic_W", "P_icp_abs_W"],
            ),
            (
                "IFI2-05",
                "P_icp_abs_W",
                &[
                    "Q_icp_plasma_wall_W",
                    "Q_icp_radiation_W",
                    "Q_icp_extraction_W",
                    "Q_icp_outflow_upstream_W",
                    "Q_icp_outflow_downstream_W",
                ],
            ),
            ("IFI2-06", "P_icp_collector_bias_W", &["Q_icp_bias_collector_W", "Q_icp_bias_export_W"]),
            (
                "IFI2-07",
                "P_icp_slot_load_sum_W",
                &[
                    "P_icp_rf_source_DC_W",
                    "P_icp_matching_DC_W",
                    "P_icp_collector_bias_W",
                    "P_icp_flow_control_W",
                    "P_icp_assist_magnet_W",
                ],
            ),
        ];
        for (cid, lhs, rhs) in ids {
            let (Some(l), Some(r)) = (ev(lhs), rhs.iter().map(|k| ev(k)).collect::<Option<Vec<Vec<f64>>>>()) else {
                continue;
            };
            for j in 0..n {
                let s: f64 = r.iter().map(|x| x[j]).sum();
                if (l[j] - s).abs() > eps_if(l[j]) {
                    self.me(&format!("{cid}_VIOLATED"), id, format!("{lhs} {} != {s} (index {j})", l[j]));
                }
            }
        }
        // CONS-I3: every slot-load watt has exactly one destination.
        if let (true, Some(total)) = (dest_ok, ev("P_icp_slot_load_sum_W")) {
            let mut worst = 0.0_f64;
            let mut bound = eps_if(total[0]);
            for j in 0..n {
                let r = (sum_dest[j] - total[j]).abs();
                if r / eps_if(total[j]) > worst / bound {
                    worst = r;
                    bound = eps_if(total[j]);
                }
            }
            d.cons_i3_residual_w = Some(worst);
            d.cons_i3_bound_w = Some(bound);
        }
        breakpoints.extend(bp.iter().flatten().copied());
        Some(d)
    }
}

fn shares_key(row: &vocab::IcpKeyV2) -> bool {
    matches!(row.deposition, DepositionV2::ProducerShares)
}

//! The active-architecture invariant (A9.19 / A9.20; A9.29 secs. 13 and 15): one Hall accelerator + one RF/ICP
//! electron source / neutralizer, flight conventional hollow cathode NONE, C1 ground test / reference only (port of
//! `abep_sim/design/a9_19_architecture.py`; contract `C-ABEP_SIM_DESIGN_A9_19_ARCHITECTURE_PY` v1).
//!
//! The definition is loaded from `config/architecture/hall_icp_neutralizer_v1.json` (manifest-verified) and, in
//! addition to the Python reference, pinned by sha256 in code ([`ARCHITECTURE_SHA256`], contract DIV-A01): a changed
//! architecture needs a new architecture version and pin. Requests the rules forbid are refused, never repaired.
//!
//! This module carries the refusal-guard vocabulary (hollow cathode, LaB6, BaO, cathode heater / keeper, C1 markers)
//! as pattern text only, in order to recognise and refuse it (CI_PLAN.md sec. 1 principle 6 allow-list).

use crate::loaders::{load_architecture, sha256_file, ARCHITECTURE_REL};
use crate::py::{self, get, index, is_str};
use crate::textmatch::{self, lit, lit_i, opt, plus, space, star, Node};
use crate::{ConfigError, ConfigPaths, ConfigResult};
use abep_types::pydict;
use abep_types::pyjson::{
    py_eq, py_lower, py_repr, py_repr_str, py_repr_tuple, py_str, py_strip, py_upper, Dict, Value,
};
use std::path::Path;

/// sha256 of the frozen architecture definition this code accepts (A9.29 sec. 13 ES-1 architecture hash pin).
pub const ARCHITECTURE_SHA256: &str = "7ab04af49340bf24be316fe7cd83eca20f2aeb692b00a43c02fa44043a5825f3";

pub const C1_BOOKING_CONDITIONAL: &str = "CONDITIONAL_NOT_BOOKED";
pub const C1_BOOKING_EMBEDDED: &str = "EMBEDDED_IN_FLOOR";
pub const C1_FLAGGED_BOOKINGS: [&str; 2] = [C1_BOOKING_CONDITIONAL, C1_BOOKING_EMBEDDED];
pub const CHECK_CLEAN: &str = "NO_HOLLOW_CATHODE_ELEMENT_LISTED";
pub const CHECK_FLAGGED: &str = "NO_HOLLOW_CATHODE_ELEMENT_LISTED_C1_PROVISIONS_FLAGGED_PENDING_BUDGET_REFRESH";
pub const C1_DECLARED_ABSENT: &str = "DECLARED_ABSENT";

/// The loaded A9.19 / A9.20 / A9.15 definition (the module constants of the Python reference).
#[derive(Debug, Clone, PartialEq)]
pub struct ArchitectureDefinition {
    pub decisions: Dict,
    pub rfp_registration: Value,
    pub rfp_clauses: Value,
    pub verbatim_a9_19: Vec<Value>,
    pub flight_configuration: String,
    pub ground_reference_configuration: String,
    pub ground_reference_label: Value,
    pub ground_only_lab_equipment: Value,
    pub c1_role: Value,
    pub supply_mode_air: Value,
    pub supply_mode_xe: Value,
    pub supply_modes: Vec<Value>,
    pub xe_path_role: Value,
    pub air_path_role: Value,
    pub supply_mode_gases: Dict,
    pub bench_engineering_gas: Vec<Value>,
    pub bench_supply_mode: Value,
    pub icp_feed_gas_baseline: Value,
    pub flight_architecture: Value,
}

fn string_of(v: &Value, what: &str) -> ConfigResult<String> {
    match v {
        Value::Str(s) => Ok(s.clone()),
        _ => Err(ConfigError::architecture(format!("REFUSED: config/architecture {what} is not a string"))),
    }
}

fn list_of(v: &Value) -> ConfigResult<Vec<Value>> {
    py::iterate(v)
}

impl ArchitectureDefinition {
    /// Load and check the definition: manifest verification (`load_architecture`), the code-side sha256 pin, and the
    /// internal-consistency rules of the Python loader (`_check_loaded_architecture`).
    pub fn load(paths: &ConfigPaths) -> ConfigResult<Self> {
        let arch = load_architecture(paths)?;
        let got = sha256_file(&paths.config_root.join(ARCHITECTURE_REL))?;
        if got != ARCHITECTURE_SHA256 {
            return Err(ConfigError::configuration(format!(
                "config/{ARCHITECTURE_REL} sha256 {got} != pinned {ARCHITECTURE_SHA256} (A9.29 architecture hash pin: a \
                 changed architecture needs a new architecture version and pin)"
            )));
        }
        let c = index(&arch, "constants")?;
        let mut decisions = Dict::new();
        for (k, v) in py::items(index(&arch, "decision_records")?)?.iter() {
            let mut d = Dict::new();
            for (kk, vv) in py::items(v)?.iter() {
                d.insert(kk.as_str(), vv.clone());
            }
            decisions.insert(k.as_str(), Value::Dict(d));
        }
        let mut gases = Dict::new();
        for (k, v) in py::items(index(c, "supply_mode_gases")?)?.iter() {
            gases.insert(k.as_str(), Value::List(list_of(v)?));
        }
        let def = ArchitectureDefinition {
            decisions,
            rfp_registration: index(&arch, "rfp_registration")?.clone(),
            rfp_clauses: index(&arch, "rfp_clauses")?.clone(),
            verbatim_a9_19: list_of(index(&arch, "verbatim_a9_19")?)?,
            flight_configuration: string_of(index(c, "flight_configuration")?, "flight_configuration")?,
            ground_reference_configuration: string_of(
                index(c, "ground_reference_configuration")?,
                "ground_reference_configuration",
            )?,
            ground_reference_label: index(c, "ground_reference_label")?.clone(),
            ground_only_lab_equipment: index(c, "ground_only_lab_equipment")?.clone(),
            c1_role: index(c, "c1_role")?.clone(),
            supply_mode_air: index(c, "supply_mode_air")?.clone(),
            supply_mode_xe: index(c, "supply_mode_xe")?.clone(),
            supply_modes: list_of(index(c, "supply_modes")?)?,
            xe_path_role: index(c, "xe_path_role")?.clone(),
            air_path_role: index(c, "air_path_role")?.clone(),
            supply_mode_gases: gases,
            bench_engineering_gas: list_of(index(c, "bench_engineering_gas")?)?,
            bench_supply_mode: index(c, "bench_supply_mode")?.clone(),
            icp_feed_gas_baseline: index(c, "icp_feed_gas_baseline")?.clone(),
            flight_architecture: index(c, "flight_architecture")?.clone(),
        };
        def.check_consistency(list_of(index(c, "flight_configurations")?)?)?;
        Ok(def)
    }

    /// `_check_loaded_architecture()`.
    fn check_consistency(&self, flight_configurations: Vec<Value>) -> ConfigResult<()> {
        let mut problems = Vec::new();
        if !py_eq(
            &Value::List(flight_configurations),
            &Value::List(vec![Value::str(self.flight_configuration.as_str())]),
        ) {
            problems.push("config flight_configurations must be exactly (flight_configuration,)");
        }
        if self.ground_reference_configuration == self.flight_configuration {
            problems.push("the ground reference is not a flight configuration");
        }
        let modes_ok = py_eq(
            &Value::List(self.supply_modes.clone()),
            &Value::List(vec![self.supply_mode_air.clone(), self.supply_mode_xe.clone()]),
        );
        let gas_keys: Vec<Value> = self.supply_mode_gases.keys().map(|k| Value::str(k.as_str())).collect();
        let same_sets = gas_keys.len() == self.supply_modes.len()
            && gas_keys.iter().all(|k| self.supply_modes.iter().any(|m| py_eq(k, m)));
        if !modes_ok || !same_sets {
            problems.push("supply modes / gases inconsistent");
        }
        let fa = &self.flight_architecture;
        let fa_ok = is_str(get(fa, "configuration")?, &self.flight_configuration)
            && py_eq(get(fa, "c1")?, &self.c1_role)
            && py_eq(get(fa, "icp_feed_gas_baseline")?, &self.icp_feed_gas_baseline)
            && py_eq(get(fa, "verbatim")?, &Value::List(self.verbatim_a9_19.clone()))
            && is_str(get(fa, "conventional_hollow_cathode")?, "NONE");
        if !fa_ok {
            problems.push("FLIGHT_ARCHITECTURE inconsistent with the loaded constants");
        }
        if !problems.is_empty() {
            let list = Value::List(problems.iter().map(|p| Value::str(*p)).collect());
            return Err(ConfigError::architecture(format!(
                "REFUSED: config/architecture definition inconsistent: {}",
                py_repr(&list)
            )));
        }
        Ok(())
    }

    /// The module constants (tuples as lists), for parity and provenance records.
    pub fn constants_value(&self) -> Value {
        let mut gases = Dict::new();
        for (k, v) in self.supply_mode_gases.iter() {
            gases.insert(k.as_str(), v.clone());
        }
        pydict! {
            "DECISIONS" => self.decisions.clone(),
            "RFP_REGISTRATION" => self.rfp_registration.clone(),
            "RFP_CLAUSES" => self.rfp_clauses.clone(),
            "VERBATIM_A9_19" => Value::List(self.verbatim_a9_19.clone()),
            "FLIGHT_CONFIGURATION" => self.flight_configuration.as_str(),
            "FLIGHT_CONFIGURATIONS" => Value::List(vec![Value::str(self.flight_configuration.as_str())]),
            "GROUND_REFERENCE_CONFIGURATION" => self.ground_reference_configuration.as_str(),
            "GROUND_REFERENCE_LABEL" => self.ground_reference_label.clone(),
            "GROUND_ONLY_LAB_EQUIPMENT" => self.ground_only_lab_equipment.clone(),
            "C1_ROLE" => self.c1_role.clone(),
            "SUPPLY_MODE_AIR" => self.supply_mode_air.clone(),
            "SUPPLY_MODE_XE" => self.supply_mode_xe.clone(),
            "SUPPLY_MODES" => Value::List(self.supply_modes.clone()),
            "XE_PATH_ROLE" => self.xe_path_role.clone(),
            "AIR_PATH_ROLE" => self.air_path_role.clone(),
            "SUPPLY_MODE_GASES" => gases,
            "BENCH_ENGINEERING_GAS" => Value::List(self.bench_engineering_gas.clone()),
            "BENCH_SUPPLY_MODE" => self.bench_supply_mode.clone(),
            "ICP_FEED_GAS_BASELINE" => self.icp_feed_gas_baseline.clone(),
            "FLIGHT_ARCHITECTURE" => self.flight_architecture.clone(),
            "C1_BOOKING_CONDITIONAL" => C1_BOOKING_CONDITIONAL,
            "C1_BOOKING_EMBEDDED" => C1_BOOKING_EMBEDDED,
            "C1_FLAGGED_BOOKINGS" => Value::List(C1_FLAGGED_BOOKINGS.iter().map(|b| Value::str(*b)).collect()),
            "C1_DECLARED_ABSENT" => C1_DECLARED_ABSENT,
            "CHECK_CLEAN" => CHECK_CLEAN,
            "CHECK_FLAGGED" => CHECK_FLAGGED,
        }
    }

    /// `verify_decision_records(repo)`: re-hash every cited decision record (json and verbatim md).
    pub fn verify_decision_records(&self, repo: &Path) -> ConfigResult<Value> {
        let mut out = Dict::new();
        for (k, d) in self.decisions.iter() {
            let json_ok = is_str(index(d, "json_sha256")?, &sha_py(repo, index(d, "json")?)?);
            let ok = json_ok && is_str(index(d, "md_sha256")?, &sha_py(repo, index(d, "md")?)?);
            out.insert(k.as_str(), Value::Bool(ok));
        }
        Ok(Value::Dict(out))
    }

    /// `cite(*keys)`.
    pub fn cite(&self, keys: &[&str]) -> ConfigResult<Value> {
        let mut out = Vec::new();
        for k in keys {
            let d = self.decisions.get(k).ok_or_else(|| py::key_error(k))?;
            out.push(pydict! {
                "decision" => *k, "md" => index(d, "md")?.clone(), "md_sha256" => index(d, "md_sha256")?.clone(),
                "json" => index(d, "json")?.clone(), "json_sha256" => index(d, "json_sha256")?.clone(),
                "decision_code" => index(d, "decision_code")?.clone(),
            });
        }
        Ok(Value::List(out))
    }

    /// `require_flight_configuration(config)`: refuse anything but the A9.19 flight configuration; the C1
    /// configuration is refused with the A9.20 reason.
    pub fn require_flight_configuration(&self, config: &str) -> ConfigResult<String> {
        if config == self.ground_reference_configuration {
            return Err(ConfigError::architecture(concat!(
                "REFUSED: hall_c1_reference is not a flight configuration (A9.19: no conventional hollow cathode; A9.20: C1 ",
                "is a GROUND-ONLY laboratory reference, never flight hardware, never in the flight mass / power / Xe ",
                "budgets); use ground_reference() where a comparison needs it"
            )));
        }
        if config != self.flight_configuration {
            return Err(ConfigError::architecture(format!(
                "unknown configuration {}; flight configurations {}",
                py_repr_str(config),
                py_repr_tuple(&[Value::str(self.flight_configuration.as_str())])
            )));
        }
        Ok(config.to_string())
    }

    /// `ground_reference(config, purpose)`: the C1 configuration as an explicitly labelled GROUND / laboratory
    /// reference (never a flight candidate, never in flight budgets).
    pub fn ground_reference(&self, config: &str, purpose: &Value) -> ConfigResult<Value> {
        if config != self.ground_reference_configuration {
            return Err(ConfigError::architecture(format!(
                "only {} is a ground reference",
                py_repr_str(&self.ground_reference_configuration)
            )));
        }
        let purpose = match purpose {
            Value::Str(p) if !py_strip(p).is_empty() => py_strip(p).to_string(),
            _ => {
                return Err(ConfigError::architecture(
                    "state the ground / laboratory comparison that needs the reference",
                ))
            }
        };
        Ok(pydict! {
            "configuration" => config, "label" => self.ground_reference_label.clone(),
            "c1_status" => self.ground_only_lab_equipment.clone(), "flight_candidate" => false,
            "in_flight_budgets" => false, "purpose" => purpose, "authority" => self.cite(&["A9.19", "A9.20"])?,
        })
    }

    /// `refuse_hollow_cathode_elements(config, elements)`: A9.19 no conventional hollow cathode. Refuses a flight
    /// configuration listing any hollow-cathode element; conditional / embedded C1 provisions are reported and make the
    /// check non-clean; explicit absence statements (re-verified) are reported.
    pub fn refuse_hollow_cathode_elements(&self, config: &str, elements: &[Value]) -> ConfigResult<Value> {
        self.require_flight_configuration(config)?;
        let flagged_fn = |e: &Value| -> bool {
            matches!(e, Value::Dict(d) if d.get("booking").is_some_and(|b| C1_FLAGGED_BOOKINGS.iter().any(|f| is_str(b, f))))
        };
        let absent_fn = |e: &Value| -> bool {
            let Value::Dict(d) = e else { return false };
            if !d.get("booking").is_some_and(|b| is_str(b, C1_DECLARED_ABSENT)) {
                return false;
            }
            let none = Value::Null;
            if d.get("kind").is_some_and(|k| is_str(k, "c1_branch")) {
                return is_c1_absent_branch_state(d.get("state").unwrap_or(&none), d.get("in_line").unwrap_or(&none));
            }
            is_c1_absence_text(d.get("name").unwrap_or(&none))
        };
        let flagged: Vec<Value> = elements.iter().filter(|e| flagged_fn(e)).cloned().collect();
        let absent: Vec<Value> = elements.iter().filter(|e| absent_fn(e)).cloned().collect();
        let rest: Vec<Value> = elements.iter().filter(|e| !flagged_fn(e) && !absent_fn(e)).cloned().collect();
        let hits = hollow_cathode_elements(&rest);
        if !hits.is_empty() {
            let list = Value::List(hits.into_iter().map(Value::Str).collect());
            return Err(ConfigError::architecture(format!(
                "REFUSED: hollow-cathode element(s) {} in flight configuration {} (A9.19: no conventional hollow \
                 cathode; A9.20: C1 ground-only)",
                py_repr(&list),
                py_repr_str(config)
            )));
        }
        let check = if flagged.is_empty() { CHECK_CLEAN } else { CHECK_FLAGGED };
        Ok(pydict! {
            "configuration" => config, "n_elements" => elements.len() as i64,
            "hollow_cathode_elements" => Value::List(vec![]),
            "c1_provisions_flagged" => Value::List(flagged),
            "c1_absence_statements" => Value::List(absent),
            "check" => check, "authority" => self.cite(&["A9.19", "A9.20"])?,
        })
    }
}

/// `_sha256(Path(repo) / rel)` (a missing record is FileNotFoundError, as in Python).
fn sha_py(repo: &Path, rel: &Value) -> ConfigResult<String> {
    sha256_file(&repo.join(py::path_operand(rel)?))
}

/// `_norm(name)`: lower case, every run of characters outside [a-z0-9] -> '_', stripped of '_'.
pub fn norm(name: &str) -> String {
    let lower = py_lower(name);
    let mut out = String::new();
    let mut in_run = false;
    for c in lower.chars() {
        if c.is_ascii_lowercase() || c.is_ascii_digit() {
            out.push(c);
            in_run = false;
        } else if !in_run {
            out.push('_');
            in_run = true;
        }
    }
    out.trim_matches('_').to_string()
}

fn hc_patterns() -> Vec<Vec<Node>> {
    let bol_or_us = || Node::Alt(vec![Node::Bol, Node::Char('_')]);
    let eol_or_us = || Node::Alt(vec![Node::Eol, Node::Char('_')]);
    let mut hollow = lit("hollow");
    hollow.push(opt(Node::Char('_')));
    hollow.extend(lit("cathode"));
    let c1 = vec![bol_or_us(), Node::Char('c'), opt(Node::Char('_')), Node::Char('1'), eol_or_us()];
    let mut keeper = vec![bol_or_us()];
    keeper.extend(lit("keeper"));
    keeper.push(eol_or_us());
    let mut heater_keeper = vec![bol_or_us()];
    heater_keeper.extend(lit("heater_keeper"));
    let bounded = |w: &str| {
        let mut v = vec![Node::WordBoundary];
        v.extend(lit(w));
        v.push(Node::WordBoundary);
        v
    };
    vec![
        hollow,
        bounded("lab6"),
        lit("lab6"),
        bounded("bao"),
        lit("cathode_heater"),
        lit("cathode_keeper"),
        keeper,
        heater_keeper,
        c1,
        lit("al_c1"),
        lit("c1_xe"),
        lit("c1_heater"),
        lit("c1_keeper"),
        lit("conventional_cathode"),
        lit("thermionic_cathode"),
    ]
}

/// `hollow_cathode_elements(elements)`: the elements (names / ids, or records with id / name / kind / line / slot)
/// that denote a hollow-cathode element, as `str(name)`.
pub fn hollow_cathode_elements(elements: &[Value]) -> Vec<String> {
    let patterns = hc_patterns();
    let mut hits = Vec::new();
    for e in elements {
        let names: Vec<&Value> = match e {
            Value::Dict(d) => {
                ["id", "name", "kind", "line", "slot"].iter().filter_map(|k| d.get(k)).filter(|v| v.truthy()).collect()
            }
            other => vec![other],
        };
        for n in names {
            let text = py_str(n);
            let normed = norm(&text);
            if patterns.iter().any(|p| textmatch::is_match(p, &normed)) {
                hits.push(text);
                break;
            }
        }
    }
    hits
}

fn absence_patterns() -> [Vec<Node>; 2] {
    // \bno\s+c-?1\b[^;,()\-]*   and   \bc-?1\s+is\s+ground-?\s*only\b   (re.I)
    let mut a = vec![Node::WordBoundary];
    a.extend(lit_i("no"));
    a.push(plus(space()));
    a.push(Node::CharI('c'));
    a.push(opt(Node::Char('-')));
    a.push(Node::Char('1'));
    a.push(Node::WordBoundary);
    a.push(star(Node::Class(|c| !matches!(c, ';' | ',' | '(' | ')' | '-'))));
    let mut b = vec![Node::WordBoundary, Node::CharI('c'), opt(Node::Char('-')), Node::Char('1'), plus(space())];
    b.extend(lit_i("is"));
    b.push(plus(space()));
    b.extend(lit_i("ground"));
    b.push(opt(Node::Char('-')));
    b.push(star(space()));
    b.extend(lit_i("only"));
    b.push(Node::WordBoundary);
    [a, b]
}

/// `is_c1_absence_text(text)`: C1 is mentioned only inside explicit absence clauses ('no C1 ...', 'C1 is ground-only').
pub fn is_c1_absence_text(text: &Value) -> bool {
    let Value::Str(t) = text else { return false };
    let pats = absence_patterns();
    if !pats.iter().any(|p| textmatch::is_match(p, t)) {
        return false;
    }
    let mut rest = t.clone();
    for p in &pats {
        rest = textmatch::sub(p, " ", &rest);
    }
    !hollow_cathode_elements(std::slice::from_ref(text)).is_empty()
        && hollow_cathode_elements(&[Value::Str(rest)]).is_empty()
}

/// `is_c1_absent_branch_state(state, in_line)`: a c1_branch record that declares no C1 branch in flight.
pub fn is_c1_absent_branch_state(state: &Value, in_line: &Value) -> bool {
    py_upper(&py_str(state)).starts_with("NO_C1") && !in_line.truthy()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn norm_and_markers() {
        assert_eq!(norm("  Hall PPU (C1 heater/keeper)  "), "hall_ppu_c1_heater_keeper");
        assert_eq!(norm("\u{130}lab6"), "i_lab6");
        let hits = hollow_cathode_elements(&[
            Value::str("c1_heater"),
            Value::str("C10 bracket"),
            Value::str("LaB6 emitter"),
            Value::str("icp_rf_source"),
            pydict! { "id" => "X", "name" => "C1" },
            pydict! { "id" => 0i64, "name" => "C-1" },
            Value::Null,
        ]);
        assert_eq!(hits, ["c1_heater", "LaB6 emitter", "C1", "C-1"]);
        assert!(is_c1_absence_text(&Value::str("Hall PPU (no C1 electronics - C1 is ground-only, A9.19 / A9.20)")));
        assert!(!is_c1_absence_text(&Value::str("Hall PPU (no C1 electronics; C1 heater/keeper supply)")));
        assert!(is_c1_absent_branch_state(&Value::str("no_c1 x"), &Value::Bool(false)));
        assert!(!is_c1_absent_branch_state(&Value::str("NO_C1_X"), &Value::Float(0.285)));
    }
}

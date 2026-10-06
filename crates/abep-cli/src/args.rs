//! Command-line grammar (acceptance_v2 `invocation`):
//!
//! ```text
//! abep [--repo DIR] --out DIR [--threads N] <group> <command> [command options]
//! ```
//!
//! Anything outside the grammar (unknown group / command / option, a missing or repeated option, a stray argument, a
//! non-finite or unparsable number) is a usage error: exit 2, nothing written.

use std::path::PathBuf;

pub const USAGE: &str = "usage: abep [--repo DIR] --out DIR [--threads N] <group> <command> [options]
  config check
  provenance verify
  env run-design-states
  intake surface-v1 --state ID --scattering maxwell|cll --l-over-d X --phi X --alpha X --theta-deg X
  drag statewise --area-m2 X --l-over-d X --phi X --scenario S
  mass rollup
  power ledger
  hall status
  hall pin-check
  icp status --supply-mode AIR_PRIMARY|XE_CONTINGENCY";

/// One registered command with its parsed inputs.
#[derive(Debug, Clone, PartialEq)]
pub enum Command {
    ConfigCheck,
    ProvenanceVerify,
    EnvRunDesignStates,
    IntakeSurfaceV1 { state: String, scattering: String, l_over_d: f64, phi: f64, alpha: f64, theta_deg: f64 },
    DragStatewise { area_m2: f64, l_over_d: f64, phi: f64, scenario: String },
    MassRollup,
    PowerLedger,
    HallStatus,
    HallPinCheck,
    IcpStatus { supply_mode: String },
}

/// A command input as recorded in the result record.
#[derive(Debug, Clone, PartialEq)]
pub enum ArgValue {
    Str(String),
    Num(f64),
}

impl Command {
    /// `<group> <command>`.
    pub fn name(&self) -> &'static str {
        match self {
            Command::ConfigCheck => "config check",
            Command::ProvenanceVerify => "provenance verify",
            Command::EnvRunDesignStates => "env run-design-states",
            Command::IntakeSurfaceV1 { .. } => "intake surface-v1",
            Command::DragStatewise { .. } => "drag statewise",
            Command::MassRollup => "mass rollup",
            Command::PowerLedger => "power ledger",
            Command::HallStatus => "hall status",
            Command::HallPinCheck => "hall pin-check",
            Command::IcpStatus { .. } => "icp status",
        }
    }

    /// File stem of the outputs: `<group>-<command>`.
    pub fn file_stem(&self) -> String {
        self.name().replace(' ', "-")
    }

    /// The inputs in registered order.
    pub fn arguments(&self) -> Vec<(&'static str, ArgValue)> {
        let s = |v: &String| ArgValue::Str(v.clone());
        match self {
            Command::IntakeSurfaceV1 { state, scattering, l_over_d, phi, alpha, theta_deg } => vec![
                ("state", s(state)),
                ("scattering", s(scattering)),
                ("l_over_d", ArgValue::Num(*l_over_d)),
                ("phi", ArgValue::Num(*phi)),
                ("alpha", ArgValue::Num(*alpha)),
                ("theta_deg", ArgValue::Num(*theta_deg)),
            ],
            Command::DragStatewise { area_m2, l_over_d, phi, scenario } => vec![
                ("area_m2", ArgValue::Num(*area_m2)),
                ("l_over_d", ArgValue::Num(*l_over_d)),
                ("phi", ArgValue::Num(*phi)),
                ("scenario", s(scenario)),
            ],
            Command::IcpStatus { supply_mode } => vec![("supply_mode", s(supply_mode))],
            _ => Vec::new(),
        }
    }
}

/// A parsed invocation.
#[derive(Debug, Clone, PartialEq)]
pub struct Invocation {
    pub repo: Option<PathBuf>,
    pub out: PathBuf,
    pub threads: Option<usize>,
    pub command: Command,
}

fn usage(msg: impl Into<String>) -> String {
    format!("{}\n{USAGE}", msg.into())
}

/// Options of one command: `--name value` pairs, each given exactly once.
struct Options {
    pairs: Vec<(String, String)>,
}

impl Options {
    fn parse(rest: &[String], allowed: &[&str]) -> Result<Options, String> {
        let mut pairs: Vec<(String, String)> = Vec::new();
        let mut i = 0;
        while i < rest.len() {
            let name = rest[i].strip_prefix("--").ok_or_else(|| usage(format!("stray argument {:?}", rest[i])))?;
            if !allowed.contains(&name) {
                return Err(usage(format!("unknown option --{name}")));
            }
            let value = rest.get(i + 1).ok_or_else(|| usage(format!("--{name} needs a value")))?;
            if pairs.iter().any(|(n, _)| n == name) {
                return Err(usage(format!("--{name} given twice")));
            }
            pairs.push((name.to_string(), value.clone()));
            i += 2;
        }
        Ok(Options { pairs })
    }

    fn text(&self, name: &str) -> Result<String, String> {
        self.pairs
            .iter()
            .find(|(n, _)| n == name)
            .map(|(_, v)| v.clone())
            .ok_or_else(|| usage(format!("--{name} is required")))
    }

    fn num(&self, name: &str) -> Result<f64, String> {
        let t = self.text(name)?;
        match t.parse::<f64>() {
            Ok(x) if x.is_finite() => Ok(x),
            _ => Err(usage(format!("--{name} {t:?} is not a finite number"))),
        }
    }
}

fn command(group: &str, cmd: &str, rest: &[String]) -> Result<Command, String> {
    let none = |c: Command| -> Result<Command, String> {
        Options::parse(rest, &[])?;
        Ok(c)
    };
    match (group, cmd) {
        ("config", "check") => none(Command::ConfigCheck),
        ("provenance", "verify") => none(Command::ProvenanceVerify),
        ("env", "run-design-states") => none(Command::EnvRunDesignStates),
        ("intake", "surface-v1") => {
            let o = Options::parse(rest, &["state", "scattering", "l-over-d", "phi", "alpha", "theta-deg"])?;
            Ok(Command::IntakeSurfaceV1 {
                state: o.text("state")?,
                scattering: o.text("scattering")?,
                l_over_d: o.num("l-over-d")?,
                phi: o.num("phi")?,
                alpha: o.num("alpha")?,
                theta_deg: o.num("theta-deg")?,
            })
        }
        ("drag", "statewise") => {
            let o = Options::parse(rest, &["area-m2", "l-over-d", "phi", "scenario"])?;
            Ok(Command::DragStatewise {
                area_m2: o.num("area-m2")?,
                l_over_d: o.num("l-over-d")?,
                phi: o.num("phi")?,
                scenario: o.text("scenario")?,
            })
        }
        ("mass", "rollup") => none(Command::MassRollup),
        ("power", "ledger") => none(Command::PowerLedger),
        ("hall", "status") => none(Command::HallStatus),
        ("hall", "pin-check") => none(Command::HallPinCheck),
        ("icp", "status") => {
            let o = Options::parse(rest, &["supply-mode"])?;
            Ok(Command::IcpStatus { supply_mode: o.text("supply-mode")? })
        }
        _ => Err(usage(format!("unknown command {group:?} {cmd:?}"))),
    }
}

/// Parse the arguments after the program name.
pub fn parse(args: &[String]) -> Result<Invocation, String> {
    let (mut repo, mut out, mut threads) = (None, None, None);
    let mut i = 0;
    while i < args.len() && args[i].starts_with("--") {
        let name = args[i].as_str();
        let value = args.get(i + 1).ok_or_else(|| usage(format!("{name} needs a value")))?;
        match name {
            "--repo" if repo.is_none() => repo = Some(PathBuf::from(value)),
            "--out" if out.is_none() => out = Some(PathBuf::from(value)),
            "--threads" if threads.is_none() => match value.parse::<usize>() {
                Ok(n) if n >= 1 => threads = Some(n),
                _ => return Err(usage(format!("--threads {value:?} is not an integer >= 1"))),
            },
            "--repo" | "--out" | "--threads" => return Err(usage(format!("{name} given twice"))),
            _ => return Err(usage(format!("unknown option {name}"))),
        }
        i += 2;
    }
    let out = out.ok_or_else(|| usage("--out DIR is required"))?;
    let group = args.get(i).ok_or_else(|| usage("no command given"))?;
    let cmd = args.get(i + 1).ok_or_else(|| usage(format!("no command given for group {group:?}")))?;
    Ok(Invocation { repo, out, threads, command: command(group, cmd, &args[i + 2..])? })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn a(s: &str) -> Vec<String> {
        s.split_whitespace().map(str::to_string).collect()
    }

    #[test]
    fn parses_the_registered_grammar() {
        let inv = parse(&a("--out /o --threads 3 drag statewise --area-m2 0.5 --l-over-d 10 --phi 0.9 --scenario s"))
            .unwrap();
        assert_eq!(inv.threads, Some(3));
        assert_eq!(
            inv.command,
            Command::DragStatewise { area_m2: 0.5, l_over_d: 10.0, phi: 0.9, scenario: "s".into() }
        );
        assert_eq!(inv.command.file_stem(), "drag-statewise");
        assert_eq!(parse(&a("--out /o hall status")).unwrap().command, Command::HallStatus);
    }

    #[test]
    fn everything_else_is_a_usage_error() {
        for bad in [
            "hall status",
            "--out /o sweep",
            "--out /o hall",
            "--out /o hall status extra",
            "--out /o --out /p hall status",
            "--out /o --threads 0 hall status",
            "--out /o --threads x hall status",
            "--out /o --bogus 1 hall status",
            "--out /o icp status",
            "--out /o icp status --supply-mode A --supply-mode B",
            "--out /o drag statewise --area-m2 abc --l-over-d 10 --phi 0.9 --scenario s",
            "--out /o drag statewise --area-m2 inf --l-over-d 10 --phi 0.9 --scenario s",
            "--out /o drag statewise --area-m2 NaN --l-over-d 10 --phi 0.9 --scenario s",
            "--out /o drag statewise --l-over-d 10 --phi 0.9 --scenario s",
            "--out /o config check --x 1",
        ] {
            assert!(parse(&a(bad)).is_err(), "{bad}");
        }
    }
}

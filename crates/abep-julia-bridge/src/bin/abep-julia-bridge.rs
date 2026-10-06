//! `abep-julia-bridge <command> [--root PATH]`: exit 0 pass, 1 fail, 2 usage.
//!
//!   pin-check                               PINNED.toml / Manifest.toml read, consistent and equal to the pin
//!   manifests-check                         build() reproduces hallthruster_bridge/campaign/manifests/*.json byte for byte
//!   smoke --out FILE                        launch the julia-smoke.yml construction smoke (needs the pinned Julia)
//!   run-shard --manifest NAME --shard I --out DIR   launch one campaign shard (needs the pinned Julia)
//!   cases                                   one registered parity step of C-JULIA-BRIDGE-LAUNCH (JSON on stdin)

use abep_hall::py::{self, Dump, PyValue};
use abep_hall::{HallError, HallResult};
use abep_julia_bridge::jobs::{self, ThreadSettings};
use abep_julia_bridge::{launch, manifests, pin, CONTRACT_ID};
use abep_provenance::find_repo_root;
use std::io::Read;
use std::process::ExitCode;

fn opt(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned()
}

fn arg<'a>(step: &'a PyValue, k: &str) -> &'a PyValue {
    static NONE: PyValue = PyValue::None;
    py::get(step, k).ok().flatten().unwrap_or(&NONE)
}

fn need_str<'a>(step: &'a PyValue, k: &str) -> HallResult<&'a str> {
    py::as_str(arg(step, k)).ok_or_else(|| HallError::type_error(format!("step argument {k} is not a string")))
}

fn parent_lookup(env: &PyValue) -> impl Fn(&str) -> Option<String> + '_ {
    move |k: &str| py::get(env, k).ok().flatten().map(py::py_str)
}

fn built_manifest(repo: &str, name: &str) -> HallResult<PyValue> {
    for m in manifests::build(repo)? {
        if manifests::name_of(&m)? == name {
            return Ok(m);
        }
    }
    Err(HallError::value("MANIFEST", format!("no manifest named {name}")))
}

fn launch_spec(repo: &str, step: &PyValue) -> HallResult<PyValue> {
    let env = arg(step, "parent_env");
    let lookup = parent_lookup(env);
    let threads = ThreadSettings::from_parent(&lookup);
    let job = match need_str(step, "kind")? {
        "campaign" => {
            let m = built_manifest(repo, need_str(step, "manifest")?)?;
            let shard = match arg(step, "shard") {
                PyValue::Int(i) => *i as usize,
                _ => return Err(HallError::type_error("shard is not an integer")),
            };
            jobs::campaign_shard_job(repo, &m, shard, need_str(step, "out_dir")?, &threads, &lookup)?
        }
        "smoke" => jobs::smoke_job(repo, need_str(step, "out_path")?, &threads, &lookup)?,
        other => return Err(HallError::type_error(format!("unknown launch kind {other}"))),
    };
    let c = job.command();
    let args: Vec<String> = c.get_args().map(|a| a.to_string_lossy().into_owned()).collect();
    let env_pairs: Vec<(PyValue, PyValue)> =
        c.get_envs().filter_map(|(k, v)| v.map(|v| (py::s(k.to_string_lossy()), py::s(v.to_string_lossy())))).collect();
    Ok(py::dict([
        ("program", py::s(c.get_program().to_string_lossy())),
        ("args", py::list_of_strs(&args)),
        ("cwd", py::s(c.get_current_dir().map(|d| d.to_string_lossy().into_owned()).unwrap_or_default())),
        ("env", PyValue::Dict(env_pairs)),
        ("env_clear", PyValue::Bool(true)),
    ]))
}

fn run_step(repo: &str, step: &PyValue) -> HallResult<PyValue> {
    match need_str(step, "op")? {
        "build_manifests" => Ok(PyValue::List(
            manifests::build(repo)?
                .iter()
                .map(|m| {
                    Ok(PyValue::List(vec![
                        py::s(manifests::name_of(m)?),
                        py::s(String::from_utf8_lossy(&manifests::to_json_bytes(m)).into_owned()),
                    ]))
                })
                .collect::<HallResult<_>>()?,
        )),
        "launch_spec" => launch_spec(repo, step),
        "shard_partition" => {
            let m = built_manifest(repo, need_str(step, "manifest")?)?;
            let n = match arg(step, "nshards") {
                PyValue::Int(i) => *i as usize,
                _ => manifests::SHARDS,
            };
            Ok(PyValue::List(
                (0..n)
                    .map(|i| {
                        Ok(PyValue::List(vec![
                            PyValue::Int(i as i128),
                            py::list_of_strs(&jobs::shard_keys(repo, &m, i, n)?),
                        ]))
                    })
                    .collect::<HallResult<_>>()?,
            ))
        }
        "check" => {
            let m = manifests::load_committed(repo, need_str(step, "manifest")?)?;
            let paths: Vec<String> = py::iterate(arg(step, "paths"))?.iter().map(py::py_str).collect();
            let bridge = match py::as_str(arg(step, "bridge")) {
                Some(b) => b.to_string(),
                None => py::join(repo, "hallthruster_bridge"),
            };
            manifests::check(&m, &paths, &bridge)
        }
        "pin" => pin::pin_report(need_str(step, "root")?),
        other => Err(HallError::type_error(format!("unknown step op {other:?}"))),
    }
}

fn cases() -> ExitCode {
    let mut input = String::new();
    if std::io::stdin().read_to_string(&mut input).is_err() {
        return ExitCode::from(2);
    }
    let Ok(request) = py::load_json_bytes(input.as_bytes()) else { return ExitCode::from(2) };
    let Some(repo) = py::as_str(arg(&request, "repo")).map(str::to_string) else { return ExitCode::from(2) };
    let outcome = match run_step(&repo, arg(&request, "step")) {
        Ok(v) => py::dict([("ok", v)]),
        Err(e) => py::dict([("err", py::dict([("kind", py::s(e.kind.name())), ("message", py::s(e.message))]))]),
    };
    println!("{}", py::dumps(&outcome, &Dump::DEFAULT));
    ExitCode::SUCCESS
}

fn run(args: &[String]) -> Result<bool, String> {
    let root = match opt(args, "--root") {
        Some(r) => r,
        None => find_repo_root(&std::env::current_dir().map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?
            .to_string_lossy()
            .into_owned(),
    };
    let env = |k: &str| std::env::var(k).ok();
    let threads = ThreadSettings::from_parent(&env);
    match args.first().map(String::as_str) {
        Some("pin-check") => {
            let p = pin::verify_pin(&root).map_err(|e| e.to_string())?;
            println!(
                "HallThruster.jl {} @ {} (julia {}): pinned and consistent",
                py::py_str(&p.version),
                py::py_str(&p.commit),
                py::py_str(&p.julia_version)
            );
            Ok(true)
        }
        Some("manifests-check") => {
            let mut ok = true;
            for m in manifests::build(&root).map_err(|e| e.to_string())? {
                let name = manifests::name_of(&m).map_err(|e| e.to_string())?;
                let path = py::join(&py::join(&root, manifests::MANIFEST_DIR_REL), &format!("{name}.json"));
                let same = std::fs::read(&path).ok() == Some(manifests::to_json_bytes(&m));
                println!("{name}: {}", if same { "identical" } else { "DIFFERS" });
                ok &= same;
            }
            Ok(ok)
        }
        Some("smoke") => {
            let out = opt(args, "--out").ok_or("--out FILE is required")?;
            let job = jobs::smoke_job(&root, &out, &threads, &env).map_err(|e| e.to_string())?;
            let s = launch::launch(&root, &job, CONTRACT_ID).map_err(|e| e.to_string())?;
            print!("{}", s.to_json());
            Ok(true)
        }
        Some("run-shard") => {
            let name = opt(args, "--manifest").ok_or("--manifest NAME is required")?;
            let shard: usize = opt(args, "--shard").and_then(|s| s.parse().ok()).ok_or("--shard I is required")?;
            let out = opt(args, "--out").ok_or("--out DIR is required")?;
            let m = built_manifest(&root, &name).map_err(|e| e.to_string())?;
            let job = jobs::campaign_shard_job(&root, &m, shard, &out, &threads, &env).map_err(|e| e.to_string())?;
            let s = launch::launch(&root, &job, CONTRACT_ID).map_err(|e| e.to_string())?;
            print!("{}", s.to_json());
            Ok(true)
        }
        _ => {
            Err("usage: abep-julia-bridge pin-check | manifests-check | smoke --out FILE | run-shard --manifest NAME \
                  --shard I --out DIR | cases  [--root PATH]"
                .into())
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.first().map(String::as_str) == Some("cases") {
        return cases();
    }
    match run(&args) {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::from(1),
        Err(e) => {
            eprintln!("abep-julia-bridge: {e}");
            ExitCode::from(2)
        }
    }
}

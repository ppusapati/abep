//! Parity CLI of PARITY-C-ABEP_SIM_INTAKE_TPMC_PY-V1 and PARITY-C-ABEP_SIM_INTAKE_PY-V1, driven by
//! scripts/rust_migration/parity_intake.py while the Python reference is active.
//!
//! cargo run --release --example intake_parity -p abep-intake -- <request.json> <response.json>
//!
//! Request: {"m_mean_build_kg": x, "calls": [{"id": .., "fn": .., ...}]}. Non-finite numbers travel as the strings
//! "NaN", "Infinity", "-Infinity" in both directions. Each call returns {"id", "ok": {...}} or
//! {"id", "err": {"key", "status", "message"}}.

use abep_intake::collection::{collection, compress, passive_compression, CompressorParams, IntakeParams};
use abep_intake::constants::{species_mass, AMU, K_B, SPECIES};
use abep_intake::freestream::FreeStream;
use abep_intake::message_key;
use abep_intake::surface::{surface_v2_gate, FrozenIntakeSurfaces, SurfaceEval};
use abep_intake::tpmc_response::{
    clausing_transmission, intake_response, response_surface, IntakeGeometry, IntakeResponse,
};
use abep_types::{AbepError, AbepResult};
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::process::ExitCode;
use std::time::Instant;

fn bad(msg: impl Into<String>) -> AbepError {
    AbepError::Schema { path: "request".into(), message: msg.into() }
}

fn num(v: &Value) -> AbepResult<f64> {
    match v {
        Value::Number(n) => n.as_f64().ok_or_else(|| bad("number")),
        Value::String(s) if s == "NaN" => Ok(f64::NAN),
        Value::String(s) if s == "Infinity" => Ok(f64::INFINITY),
        Value::String(s) if s == "-Infinity" => Ok(f64::NEG_INFINITY),
        other => Err(bad(format!("not a number: {other}"))),
    }
}

fn f(o: &Value, k: &str) -> AbepResult<f64> {
    num(o.get(k).ok_or_else(|| bad(format!("missing {k}")))?)
}

fn opt(o: &Value, k: &str) -> AbepResult<Option<f64>> {
    match o.get(k) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => num(v).map(Some),
    }
}

fn out(x: f64) -> Value {
    if x.is_finite() {
        json!(x)
    } else if x.is_nan() {
        json!("NaN")
    } else if x > 0.0 {
        json!("Infinity")
    } else {
        json!("-Infinity")
    }
}

fn list(o: &Value, k: &str) -> AbepResult<Vec<f64>> {
    o.get(k).and_then(Value::as_array).ok_or_else(|| bad(format!("missing list {k}")))?.iter().map(num).collect()
}

fn freestream(o: &Value) -> AbepResult<FreeStream> {
    Ok(FreeStream {
        n: f(o, "n")?,
        rho: f(o, "rho")?,
        v: f(o, "V")?,
        v_rel: opt(o, "V_rel")?,
        t: f(o, "T")?,
        m_mean: f(o, "m_mean")?,
        f_o: f(o, "fO")?,
        f_n2: f(o, "fN2")?,
        f_o2: f(o, "fO2")?,
        flux_kg_m2_s: f(o, "flux_kg_m2_s")?,
    })
}

fn geometry(o: &Value) -> AbepResult<IntakeGeometry> {
    let mut g = IntakeGeometry::default();
    let set = |k: &str, dst: &mut f64| -> AbepResult<()> {
        if let Some(v) = opt(o, k)? {
            *dst = v;
        }
        Ok(())
    };
    set("area_m2", &mut g.area_m2)?;
    set("d_mm", &mut g.d_mm)?;
    set("L_over_d", &mut g.l_over_d)?;
    set("phi", &mut g.phi)?;
    set("T_wall_K", &mut g.t_wall_k)?;
    set("wall_thickness_mm", &mut g.wall_thickness_mm)?;
    set("wall_density_kg_m3", &mut g.wall_density_kg_m3)?;
    set("coating_thickness_um", &mut g.coating_thickness_um)?;
    set("coating_density_kg_m3", &mut g.coating_density_kg_m3)?;
    set("support_mass_frac", &mut g.support_mass_frac)?;
    set("filter_open_frac", &mut g.filter_open_frac)?;
    set("filter_transmission", &mut g.filter_transmission)?;
    set("filter_mass_per_m2", &mut g.filter_mass_per_m2)?;
    if let Some(b) = o.get("filter").and_then(Value::as_bool) {
        g.filter = b;
    }
    Ok(g)
}

fn intake_params(o: &Value) -> AbepResult<IntakeParams> {
    let mut p = IntakeParams::default();
    for (k, dst) in [
        ("area_m2", &mut p.area_m2),
        ("eta_c_specular", &mut p.eta_c_specular),
        ("eta_c_diffuse", &mut p.eta_c_diffuse),
        ("accommodation", &mut p.accommodation),
        ("off_axis_deg", &mut p.off_axis_deg),
        ("cd", &mut p.cd),
        ("body_area_m2", &mut p.body_area_m2),
        ("mass_per_m2", &mut p.mass_per_m2),
        ("mass_fixed", &mut p.mass_fixed),
        ("L_over_d", &mut p.l_over_d),
        ("phi", &mut p.phi),
        ("d_mm", &mut p.d_mm),
    ] {
        if let Some(v) = opt(o, k)? {
            *dst = v;
        }
    }
    if let Some(b) = o.get("use_tpmc").and_then(Value::as_bool) {
        p.use_tpmc = b;
    }
    if let Some(b) = o.get("filter").and_then(Value::as_bool) {
        p.filter = b;
    }
    if let Some(s) = o.get("scattering").and_then(Value::as_str) {
        p.scattering = s.to_string();
    }
    Ok(p)
}

fn compressor_params(o: &Value) -> AbepResult<CompressorParams> {
    let mut c = CompressorParams::default();
    for (k, dst) in [
        ("ratio", &mut c.ratio),
        ("area_ratio", &mut c.area_ratio),
        ("T_out_K", &mut c.t_out_k),
        ("p_base_W", &mut c.p_base_w),
        ("p_per_mgps_per_ln", &mut c.p_per_mgps_per_ln),
        ("max_ratio", &mut c.max_ratio),
        ("backflow_frac", &mut c.backflow_frac),
        ("mass_base_kg", &mut c.mass_base_kg),
        ("mass_per_ln", &mut c.mass_per_ln),
    ] {
        if let Some(v) = opt(o, k)? {
            *dst = v;
        }
    }
    c.anode_conductance_m3_s = opt(o, "anode_conductance_m3_s")?;
    Ok(c)
}

fn response_json(r: &IntakeResponse) -> Value {
    json!({
        "eta_c": out(r.eta_c), "C_D": out(r.c_d), "K_back": out(r.k_back), "CR_passive": out(r.cr_passive),
        "eta_open": out(r.eta_open), "unresolved_fraction": out(r.unresolved_fraction), "converged": r.converged,
        "scattering": r.scattering, "K_back_scattering": r.k_back_scattering, "mean_wall_hits": out(r.mean_wall_hits),
        "mass_kg": out(r.mass_kg), "alpha": out(r.alpha), "theta_deg": out(r.theta_deg), "L_over_d": out(r.l_over_d),
        "phi": out(r.phi), "d_mm": out(r.d_mm), "status": r.status.as_str(),
    })
}

fn surface_json(e: &SurfaceEval) -> Value {
    let mut sp = Map::new();
    for (name, s) in &e.species {
        sp.insert(
            name.clone(),
            json!({
                "eta_c": out(s.eta_c), "C_D_row": out(s.c_d_row), "C_D_species": out(s.c_d_species),
                "CR_passive": out(s.cr_passive), "K_back": out(s.k_back), "mass_fraction": out(s.mass_fraction),
                "mole_fraction": out(s.mole_fraction), "collected_mass_fraction": out(s.collected_mass_fraction),
                "collected_mole_fraction": out(s.collected_mole_fraction),
            }),
        );
    }
    json!({
        "eta_c": out(e.eta_c), "C_D": out(e.c_d), "K_back": out(e.k_back), "mass_kg": out(e.mass_kg),
        "CR_passive": out(e.cr_passive), "species": Value::Object(sp), "species_order": e.species.iter().map(|s| s.0.clone()).collect::<Vec<_>>(),
        "recombination": e.recombination,
    })
}

fn fractions(o: &Value) -> AbepResult<Option<BTreeMap<String, f64>>> {
    match o.get("fractions") {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Object(m)) => Ok(Some(m.iter().map(|(k, v)| Ok((k.clone(), num(v)?))).collect::<AbepResult<_>>()?)),
        Some(other) => Err(bad(format!("fractions: {other}"))),
    }
}

/// Process CPU time of this (single-threaded) process, from /proc/self/schedstat (ns).
fn cpu_s() -> f64 {
    std::fs::read_to_string("/proc/self/schedstat")
        .ok()
        .and_then(|s| s.split_whitespace().next().and_then(|t| t.parse::<f64>().ok()))
        .map_or(f64::NAN, |ns| ns * 1e-9)
}

struct Ctx {
    root: std::path::PathBuf,
    surfaces: Option<FrozenIntakeSurfaces>,
}

fn call(ctx: &Ctx, c: &Value) -> AbepResult<Value> {
    let fname = c.get("fn").and_then(Value::as_str).ok_or_else(|| bad("missing fn"))?;
    let surfaces = || ctx.surfaces.as_ref().ok_or_else(|| bad("no m_mean_build_kg in request"));
    let usize_of =
        |k: &str| c.get(k).and_then(Value::as_u64).map(|v| v as usize).ok_or_else(|| bad(format!("missing {k}")));
    let seed = || c.get("seed").and_then(Value::as_u64).ok_or_else(|| bad("missing seed"));
    match fname {
        "constants" => {
            let masses: Map<String, Value> =
                SPECIES.iter().map(|s| (s.to_string(), out(species_mass(s).unwrap()))).collect();
            Ok(
                json!({"K_B": out(K_B), "AMU": out(AMU), "K_B_abep_core": out(abep_core::tpmc::K_B), "M_SPECIES": masses}),
            )
        }
        "intake_response" => {
            let fs = freestream(&c["fs"])?;
            let r = intake_response(
                &geometry(&c["geom"])?,
                &fs,
                f(c, "alpha")?,
                f(c, "theta_deg")?,
                usize_of("n")?,
                seed()?,
                c["scattering"].as_str().ok_or_else(|| bad("scattering"))?,
                opt(c, "species_mass")?,
            )?;
            Ok(response_json(&r))
        }
        "clausing_transmission" => Ok(json!({"K_back": out(clausing_transmission(
            seed()?,
            f(c, "r")?,
            f(c, "l")?,
            f(c, "alpha")?,
            f(c, "t_w")?,
            f(c, "m")?,
            usize_of("n")?,
        )?)})),
        "response_surface" | "perf_response_surface" => {
            let fs = freestream(&c["fs"])?;
            let species: Option<Vec<String>> = c
                .get("species")
                .and_then(Value::as_array)
                .map(|a| a.iter().map(|s| s.as_str().unwrap_or("").to_string()).collect());
            let (ld, ph, al, th) = (list(c, "L_over_d")?, list(c, "phis")?, list(c, "alphas")?, list(c, "thetas")?);
            let run = || {
                response_surface(
                    &fs,
                    &ld,
                    &ph,
                    &al,
                    &th,
                    usize_of("n").unwrap_or(0),
                    f(c, "area_m2").unwrap_or(f64::NAN),
                    species.as_deref(),
                    c["scattering"].as_str().unwrap_or(""),
                )
            };
            if fname == "perf_response_surface" {
                run()?; // untimed warm-up
                let mut wall = Vec::new();
                let mut cpu = Vec::new();
                let mut rows = 0;
                for _ in 0..usize_of("repeats")? {
                    let (t0, c0) = (Instant::now(), cpu_s());
                    rows = run()?.len();
                    wall.push(t0.elapsed().as_secs_f64());
                    cpu.push(cpu_s() - c0);
                }
                return Ok(json!({"wall_s": wall, "cpu_s": cpu, "points": rows,
                                 "cpu_clock": "/proc/self/schedstat (single-threaded process)"}));
            }
            let rows = run()?;
            Ok(json!({"rows": rows.iter().map(|r| {
                let mut v = response_json(&r.response);
                v["species"] = json!(r.species);
                v
            }).collect::<Vec<_>>()}))
        }
        "surface_load" => {
            FrozenIntakeSurfaces::load(&ctx.root, f(c, "m_mean_build_kg")?).map(|_| json!({"loaded": true}))
        }
        "surface_eval" => {
            let s = surfaces()?.get(c["scattering"].as_str().unwrap_or(""))?;
            let p = list(c, "point")?;
            let th = if p.len() == 4 { p[3] } else { 0.0 };
            Ok(surface_json(&s.eval(p[0], p[1], p[2], th, fractions(c)?.as_ref())?))
        }
        "surface_in_bounds" => {
            let s = surfaces()?.get(c["scattering"].as_str().unwrap_or(""))?;
            let p = list(c, "point")?;
            Ok(json!({"in_bounds": s.in_bounds(p[0], p[1], p[2], if p.len() == 4 { p[3] } else { 0.0 })}))
        }
        "surface_domain" => {
            let s = surfaces()?.get(c["scattering"].as_str().unwrap_or(""))?;
            let d = s.domain();
            let names = ["L_over_d", "phi", "alpha", "theta_deg"];
            let axes: Map<String, Value> =
                names.iter().zip(d.axes).map(|(n, (lo, hi))| (n.to_string(), json!([out(lo), out(hi)]))).collect();
            Ok(json!({"axes": axes, "species": d.species, "atmosphere_state": d.atmosphere_state,
                      "outside_domain": d.outside_domain, "max_unresolved": out(s.max_unresolved())}))
        }
        "surface_v2_gate" => {
            let g = surface_v2_gate();
            Ok(json!({"status": g.status.as_str(), "label": g.label, "primary_blocker": g.primary_blocker,
                      "unregistered": g.unregistered}))
        }
        "collection" => {
            let r = collection(&intake_params(&c["intake"])?, &freestream(&c["fs"])?, ctx.surfaces.as_ref())?;
            Ok(json!({
                "eta_c": out(r.eta_c), "mdot_incident": out(r.mdot_incident), "mdot_collected": out(r.mdot_collected),
                "C_D": out(r.c_d), "drag_N": out(r.drag_n), "intake_mass_kg": out(r.intake_mass_kg),
                "passive_override": r.passive_override.map(out),
                "mdot_collected_species": r.mdot_collected_species.map(|v| {
                    v.into_iter().map(|(k, x)| json!([k, out(x)])).collect::<Vec<_>>()
                }),
            }))
        }
        "compress" => {
            let r = compress(
                &compressor_params(&c["comp"])?,
                &freestream(&c["fs"])?,
                f(c, "mdot_col")?,
                f(c, "eta_c")?,
                opt(c, "passive_override")?,
            )?;
            Ok(json!({
                "p_out_Pa": out(r.p_out_pa), "p_passive_Pa": out(r.p_passive_pa), "passive_ratio": out(r.passive_ratio),
                "active_ratio": out(r.active_ratio), "ratio_effective": out(r.ratio_effective), "mdot_net": out(r.mdot_net),
                "n_out": out(r.n_out), "comp_power_W": out(r.comp_power_w), "comp_mass_kg": out(r.comp_mass_kg),
                "comp_feasible": r.comp_feasible,
            }))
        }
        "passive_compression" => Ok(json!({"passive": out(passive_compression(
            &compressor_params(&c["comp"])?,
            &freestream(&c["fs"])?,
            f(c, "eta_c")?,
        )?)})),
        "defaults" => {
            let p = IntakeParams::default();
            let k = CompressorParams::default();
            let g = IntakeGeometry::default();
            Ok(json!({
                "IntakeParams": {"area_m2": p.area_m2, "eta_c_specular": p.eta_c_specular, "eta_c_diffuse": p.eta_c_diffuse,
                    "accommodation": p.accommodation, "off_axis_deg": p.off_axis_deg, "cd": p.cd, "body_area_m2": p.body_area_m2,
                    "mass_per_m2": p.mass_per_m2, "mass_fixed": p.mass_fixed, "use_tpmc": p.use_tpmc, "scattering": p.scattering,
                    "L_over_d": p.l_over_d, "phi": p.phi, "d_mm": p.d_mm, "filter": p.filter},
                "CompressorParams": {"ratio": k.ratio, "area_ratio": k.area_ratio, "T_out_K": k.t_out_k, "p_base_W": k.p_base_w,
                    "p_per_mgps_per_ln": k.p_per_mgps_per_ln, "max_ratio": k.max_ratio,
                    "anode_conductance_m3_s": k.anode_conductance_m3_s, "backflow_frac": k.backflow_frac,
                    "mass_base_kg": k.mass_base_kg, "mass_per_ln": k.mass_per_ln},
                "IntakeGeometry": {"area_m2": g.area_m2, "d_mm": g.d_mm, "L_over_d": g.l_over_d, "phi": g.phi, "T_wall_K": g.t_wall_k,
                    "wall_thickness_mm": g.wall_thickness_mm, "wall_density_kg_m3": g.wall_density_kg_m3,
                    "coating_thickness_um": g.coating_thickness_um, "coating_density_kg_m3": g.coating_density_kg_m3,
                    "support_mass_frac": g.support_mass_frac, "filter": g.filter, "filter_open_frac": g.filter_open_frac,
                    "filter_transmission": g.filter_transmission, "filter_mass_per_m2": g.filter_mass_per_m2},
            }))
        }
        other => Err(bad(format!("unknown fn {other}"))),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 {
        eprintln!("usage: intake_parity <request.json> <response.json>");
        return ExitCode::from(2);
    }
    let req: Value = match std::fs::read(&args[1])
        .map_err(|e| e.to_string())
        .and_then(|b| serde_json::from_slice(&b).map_err(|e| e.to_string()))
    {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let root = match abep_provenance::workspace_repo_root() {
        Ok(r) => r,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let surfaces = match req.get("m_mean_build_kg").map(num) {
        Some(Ok(m)) => match FrozenIntakeSurfaces::load(&root, m) {
            Ok(s) => Some(s),
            Err(e) => {
                eprintln!("frozen surface load: {e}");
                return ExitCode::FAILURE;
            }
        },
        _ => None,
    };
    let ctx = Ctx { root, surfaces };
    let calls = req.get("calls").and_then(Value::as_array).cloned().unwrap_or_default();
    let results: Vec<Value> = calls
        .iter()
        .map(|c| {
            let id = c.get("id").cloned().unwrap_or(Value::Null);
            match call(&ctx, c) {
                Ok(v) => json!({"id": id, "ok": v}),
                Err(e) => json!({"id": id, "err": {"key": message_key(&e), "status": e.status().as_str(),
                                                   "message": e.to_string()}}),
            }
        })
        .collect();
    let body = serde_json::to_vec(&json!({"results": results})).expect("serializable");
    if let Err(e) = std::fs::write(&args[2], body) {
        eprintln!("{e}");
        return ExitCode::FAILURE;
    }
    ExitCode::SUCCESS
}

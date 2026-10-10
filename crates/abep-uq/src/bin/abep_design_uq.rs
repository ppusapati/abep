//! `abep-design-uq`: parity harness interface and study runner of the SC-WP-10 design / UQ lane.
//!
//! * `eval <calls.json>`: a JSON list of {"entry", "args"}; prints a list of {"outcome": "RETURNED", "value"} or
//!   {"outcome": "RAISED", "class", "message", "status"} (the reference exception class and the fail-closed status).
//! * `study <spec.json> <out_dir>`: the F7 / F8 study (stage_f7 / stage_f8) on the spec's grid; writes every
//!   context's bits and column arrays as little-endian binaries, the Pareto blocks, the F8 record, the carried robust
//!   set, the binding-constraint decomposition and the B2-OF-01 chain application.

use abep_design::err::{DResult, DesignError};
use abep_design::inputs::{load_upstream_inputs, UpstreamInputs};
use abep_design::optimizer::{
    context_id, context_role, design_id, higher_pressure_branch, nondominated_layers, pareto_mask, plenum,
    upstream_context, wall_gamma, Context, ARRAY_KEYS,
};
use abep_design::pv::{from_serde, to_serde};
use abep_design::records;
use abep_design::synthesis::{context_pareto, rank_precheck, RankPrecheck};
use abep_gaspath::rec::{as_f64, fnum};
use abep_rng::{Generator, Pcg64, SeedSequence};
use abep_uq::interp_sensitivity::{chain_application, Diagnostic};
use abep_uq::mc::{draw, np_percentile, perturbed, record_se_index, state_eval, tpmc_monte_carlo};
use abep_uq::robust::{require_all_admitted_scenarios, robust_over_scenarios, Survivor};
use abep_uq::sens::{
    compressor_elasticities, design_gate_snapshot, fixed_coefficients, plant_with_overrides, pointing_sensitivity,
    theta_ratio_index,
};
use abep_uq::study::{carried_value, f8_value, robust_decomposition, stage_f7, stage_f8, StudySpec};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::cell::OnceCell;
use std::io::Write;
use std::path::{Path, PathBuf};

fn bad(msg: impl Into<String>) -> DesignError {
    DesignError::new("HarnessError", msg)
}

fn f(a: &Value, k: &str) -> DResult<f64> {
    a.get(k).and_then(as_f64).ok_or_else(|| bad(format!("arg {k}")))
}

fn s<'a>(a: &'a Value, k: &str) -> DResult<&'a str> {
    a.get(k).and_then(Value::as_str).ok_or_else(|| bad(format!("arg {k}")))
}

fn fl(a: &Value, k: &str) -> DResult<Vec<f64>> {
    a.get(k)
        .and_then(Value::as_array)
        .ok_or_else(|| bad(format!("arg {k}")))?
        .iter()
        .map(|x| as_f64(x).ok_or_else(|| bad(format!("arg {k} item"))))
        .collect()
}

fn sl(a: &Value, k: &str) -> DResult<Option<Vec<String>>> {
    match a.get(k) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Array(v)) => Ok(Some(v.iter().map(|x| x.as_str().unwrap_or_default().to_string()).collect())),
        _ => Err(bad(format!("arg {k}"))),
    }
}

fn matrix(a: &Value) -> DResult<(Vec<Vec<f64>>, Vec<String>)> {
    let m = a
        .get("F")
        .and_then(Value::as_array)
        .ok_or_else(|| bad("arg F"))?
        .iter()
        .map(|r| {
            r.as_array().map(|r| r.iter().map(|x| as_f64(x).unwrap_or(f64::NAN)).collect()).ok_or_else(|| bad("row"))
        })
        .collect::<DResult<Vec<Vec<f64>>>>()?;
    let senses = sl(a, "senses")?.ok_or_else(|| bad("arg senses"))?;
    Ok((m, senses))
}

fn u128_of(v: &Value) -> DResult<u128> {
    match v {
        Value::Number(n) => n.as_u64().map(u128::from).ok_or_else(|| bad("seed")),
        Value::String(t) => t.parse::<u128>().map_err(|_| bad("seed")),
        _ => Err(bad("seed")),
    }
}

fn sha_f64(v: &[f64]) -> String {
    let mut h = Sha256::new();
    for x in v {
        h.update(x.to_le_bytes());
    }
    format!("{:x}", h.finalize())
}

fn context_value(ctx: &Context) -> Value {
    let mut arrays = Map::new();
    for (k, a) in ARRAY_KEYS.iter().zip(&ctx.arrays) {
        arrays.insert((*k).into(), Value::Array(a.iter().map(|x| fnum(*x)).collect()));
    }
    json!({
        "scenario": ctx.scenario, "filter": ctx.filter, "wall": ctx.wall,
        "candidates": ctx.candidates, "compressors": ctx.compressors,
        "volumes": ctx.volumes, "targets": ctx.targets,
        "bits": ctx.bits, "arrays": Value::Object(arrays),
        "context_role": ctx.context_role, "design_direction": ctx.design_direction,
    })
}

fn survivor_of(v: &Value) -> DResult<Survivor> {
    Ok(Survivor {
        design_id: s(v, "design_id")?.to_string(),
        candidate: s(v, "candidate")?.to_string(),
        compressor: s(v, "compressor")?.to_string(),
        v_m3: f(v, "V_m3")?,
        p_set_pa: f(v, "P_set_Pa")?,
        filter: s(v, "filter")?.to_string(),
        pareto_in: sl(v, "pareto_in")?.unwrap_or_default(),
        filter_context_role: v.get("filter_context_role").and_then(Value::as_str).unwrap_or_default().to_string(),
    })
}

fn per_value(v: Vec<(String, Vec<(String, Value)>)>) -> Value {
    Value::Object(v.into_iter().map(|(d, per)| (d, Value::Object(per.into_iter().collect()))).collect())
}

struct Env {
    repo: PathBuf,
    inp: OnceCell<UpstreamInputs>,
    diag: OnceCell<Diagnostic>,
}

impl Env {
    fn inp(&self) -> DResult<&UpstreamInputs> {
        if self.inp.get().is_none() {
            let v = load_upstream_inputs(&self.repo)?;
            let _ = self.inp.set(v);
        }
        Ok(self.inp.get().expect("set"))
    }
    fn diag(&self) -> DResult<&Diagnostic> {
        if self.diag.get().is_none() {
            let v = Diagnostic::load(&self.repo)?;
            let _ = self.diag.set(v);
        }
        Ok(self.diag.get().expect("set"))
    }
}

fn ctx_args(env: &Env, a: &Value) -> DResult<Context> {
    let inp = env.inp()?;
    let cands = sl(a, "candidates")?;
    let comps = sl(a, "compressors")?;
    upstream_context(
        inp,
        s(a, "scenario")?,
        s(a, "filter")?,
        s(a, "wall")?,
        &fl(a, "volumes")?,
        &fl(a, "targets")?,
        cands.as_deref(),
        comps.as_deref(),
    )
}

fn dispatch(env: &Env, entry: &str, a: &Value) -> DResult<Value> {
    let repo = env.repo.as_path();
    Ok(match entry {
        // ------------------------------------------------------------------ F7
        "inputs.summary" => {
            let inp = env.inp()?;
            let geom: Map<String, Value> = inp
                .candidates
                .iter()
                .map(|c| (c.clone(), json!([inp.geometry[c].0, inp.geometry[c].1, inp.geometry[c].2])))
                .collect();
            json!({"candidates": inp.candidates, "geometry": geom, "scenarios": inp.scenarios, "states": inp.states,
                   "compressor_ids": inp.compressor_ids, "filter_ids": inp.filter_ids})
        }
        "inputs.records" => {
            let inp = env.inp()?;
            let mut out = vec![];
            for k in a.get("keys").and_then(Value::as_array).ok_or_else(|| bad("keys"))? {
                let k = k.as_array().ok_or_else(|| bad("key"))?;
                let g = |i: usize| k.get(i).and_then(Value::as_str).unwrap_or_default();
                let r = inp.record(g(0), g(1), g(2))?;
                let sp = |x: [f64; 3]| json!({"O": fnum(x[0]), "N2": fnum(x[1]), "O2": fnum(x[2])});
                out.push(json!({"area_m2": r.area_m2, "T_K": r.t_k, "mdot_fwd_kgps": sp(r.mdot_fwd_kgps),
                                "p_passive_Pa": sp(r.p_passive_pa), "K_back": sp(r.k_back), "f1_status": r.f1_status}));
            }
            Value::Array(out)
        }
        "upstream_context" => context_value(&ctx_args(env, a)?),
        "context_pareto" => {
            let ctx = ctx_args(env, a)?;
            let blocks = context_pareto(&ctx, &abep_design::optimizer::obj_keys())?;
            Value::Array(blocks.iter().map(|b| json!({"P_set_Pa": b.p_set_pa, "block": b.to_value()})).collect())
        }
        "pareto_mask" => {
            let (m, se) = matrix(a)?;
            let senses: Vec<&str> = se.iter().map(String::as_str).collect();
            json!(pareto_mask(&m, &senses)?)
        }
        "nondominated_layers" => {
            let (m, se) = matrix(a)?;
            let senses: Vec<&str> = se.iter().map(String::as_str).collect();
            json!(nondominated_layers(&m, &senses)?)
        }
        "design_id" => json!(design_id(s(a, "cand")?, s(a, "filt")?, s(a, "comp")?, f(a, "V")?, f(a, "P")?)),
        "context_id" => json!(context_id(s(a, "scenario")?, s(a, "filt")?, s(a, "wall")?, f(a, "P")?)),
        "wall_gamma" => fnum(wall_gamma(env.inp()?, s(a, "wall")?)?),
        "plenum" => {
            let p = plenum(env.inp()?, f(a, "V")?, s(a, "wall")?)?;
            json!({"volume_m3": p.volume_m3, "gamma_wall": p.gamma_wall, "wall_case": p.wall_case,
                   "leak_area_m2": p.leak_area_m2})
        }
        "context_role" => {
            let inp = env.inp()?;
            json!(context_role(inp.filter(s(a, "filter")?)?))
        }
        "higher_pressure_branch" => json!(higher_pressure_branch(&fl(a, "targets")?)?),
        "rank_precheck" => {
            let evs = a.get("evaluations").and_then(Value::as_array).cloned().unwrap_or_default();
            let ups = sl(a, "upstream_objectives")?.unwrap_or_default();
            let ups: Vec<&str> = ups.iter().map(String::as_str).collect();
            let unlock = records::unlock_map();
            match rank_precheck(&evs, &ups, &unlock) {
                RankPrecheck::Refused(v) => v,
                RankPrecheck::ProceedToAssessment { .. } => json!({"status": "PROCEED_TO_ASSESSMENT"}),
            }
        }
        "require_all_admitted_scenarios" => {
            let nr = a.get("narrowing_record").and_then(Value::as_object);
            require_all_admitted_scenarios(
                &sl(a, "used")?.unwrap_or_default(),
                &sl(a, "admitted")?.unwrap_or_default(),
                nr,
            )?
        }
        "robust_over_scenarios" => {
            let per: Vec<(String, bool)> = a
                .get("per_scenario")
                .and_then(Value::as_array)
                .ok_or_else(|| bad("per_scenario"))?
                .iter()
                .map(|x| (x[0].as_str().unwrap_or_default().to_string(), x[1].as_bool().unwrap_or(false)))
                .collect();
            robust_over_scenarios(&per, &sl(a, "admitted")?.unwrap_or_default())?
        }
        "design_vector_blocks" => {
            let inp = env.inp()?;
            let filters: Vec<_> = inp.filter_ids.iter().map(|i| inp.filters[i].clone()).collect();
            to_serde(&records::design_vector_blocks(repo, &inp.f1, &filters, inp.required_states.len())?)
        }
        "architecture_questions" => to_serde(&records::architecture_questions(repo)?),
        "flight_configuration_elements" => to_serde(&records::flight_configuration_elements(repo, s(a, "config")?)?),
        "heat_rejection" => to_serde(&records::heat_rejection(repo, a.get("compressor_P_W").and_then(as_f64))?),
        "electron_margin" => to_serde(&records::electron_margin(repo, s(a, "config")?)?),
        "hall_gated_thrust" => {
            let hall = abep_mission::objective::HallResponseStatus::load(repo)?;
            to_serde(&records::hall_gated_thrust(
                s(a, "name")?,
                &from_serde(a.get("rec").unwrap_or(&Value::Null)),
                !hall.admitted_members.is_empty(),
            ))
        }
        "tpmc_backend_policy" => to_serde(&records::tpmc_backend_policy(repo)?),
        "is_conditional_c1_text" => {
            json!(records::is_conditional_c1_text(&from_serde(a.get("text").unwrap_or(&Value::Null))))
        }
        // ------------------------------------------------------------------ F8 / stream
        "rng.stream" => {
            let ent = match a.get("seed") {
                Some(Value::String(t)) => abep_rng::decimal_to_u32_words(t).ok_or_else(|| bad("seed"))?,
                Some(v) => abep_rng::int_to_u32_words(u128_of(v)?),
                None => return Err(bad("seed")),
            };
            let ss = SeedSequence::from_words(&ent);
            let st = Pcg64::from_seed_sequence(&ss).state();
            let mut g = Generator::from_entropy_words(&ent);
            let n_u64 = a.get("n_u64").and_then(Value::as_u64).unwrap_or(0) as usize;
            let n_random = a.get("n_random").and_then(Value::as_u64).unwrap_or(0) as usize;
            let n_normal = a.get("n_normal").and_then(Value::as_u64).unwrap_or(0) as usize;
            let mut raw = Pcg64::from_seed_sequence(&ss);
            let words: Vec<String> = (0..n_u64).map(|_| raw.next_u64().to_string()).collect();
            let mut gr = Generator::from_entropy_words(&ent);
            let rnd: Vec<Value> = (0..n_random).map(|_| fnum(gr.random())).collect();
            let z = g.standard_normal_fill(n_normal);
            json!({
                "pool": ss.pool().to_vec(),
                "generate_state_u32_8": ss.generate_state_u32(8),
                "generate_state_u64_4": ss.generate_state_u64(4).iter().map(|x| x.to_string()).collect::<Vec<_>>(),
                "pcg64_state": st.0.to_string(), "pcg64_inc": st.1.to_string(),
                "next_uint64": words, "random": rnd,
                "normal_sha256": sha_f64(&z), "normal_head": z.iter().take(16).map(|x| fnum(*x)).collect::<Vec<_>>(),
                "n_normal": n_normal,
            })
        }
        "stable_seed" => {
            let parts = sl(a, "parts")?.unwrap_or_default();
            let p: Vec<&str> = parts.iter().map(String::as_str).collect();
            json!(abep_rng::stable_seed(&p, a.get("base").and_then(Value::as_i64).unwrap_or(0)))
        }
        "np_percentile" => {
            let v: Vec<f64> = a
                .get("a")
                .and_then(Value::as_array)
                .ok_or_else(|| bad("a"))?
                .iter()
                .map(|x| as_f64(x).unwrap_or(f64::NAN))
                .collect();
            fnum(np_percentile(&v, f(a, "q")?))
        }
        "perturbed" => {
            let inp = env.inp()?;
            let k = a.get("key").and_then(Value::as_array).ok_or_else(|| bad("key"))?;
            let g = |i: usize| k.get(i).and_then(Value::as_str).unwrap_or_default();
            let rec = inp.record(g(0), g(1), g(2))?;
            let se_v = fl(a, "se")?;
            let se = [(se_v[0], se_v[1]), (se_v[2], se_v[3]), (se_v[4], se_v[5])];
            let zm = fl(a, "z_m")?;
            let zp = fl(a, "z_p")?;
            let r = perturbed(rec, f(a, "area")?, &se, [zm[0], zm[1], zm[2]], [zp[0], zp[1], zp[2]]);
            json!({"mdot_fwd_kgps": r.mdot_fwd_kgps.iter().map(|x| fnum(*x)).collect::<Vec<_>>(),
                   "p_passive_Pa": r.p_passive_pa.iter().map(|x| fnum(*x)).collect::<Vec<_>>(), "source": r.source})
        }
        "record_se_index" => {
            let inp = env.inp()?;
            let idx = record_se_index(inp)?;
            let mut out = vec![];
            for k in a.get("keys").and_then(Value::as_array).ok_or_else(|| bad("keys"))? {
                let (ld, phi) = (as_f64(&k[0]).unwrap_or(f64::NAN), as_f64(&k[1]).unwrap_or(f64::NAN));
                let key = (
                    ld.to_bits(),
                    phi.to_bits(),
                    k[2].as_str().unwrap_or_default().to_string(),
                    k[3].as_str().unwrap_or_default().to_string(),
                );
                out.push(match idx.get(&key) {
                    Some(v) => json!(v.iter().map(|(a, b)| json!([fnum(*a), fnum(*b)])).collect::<Vec<_>>()),
                    None => Value::Null,
                });
            }
            Value::Array(out)
        }
        "theta_ratio_index" => {
            let mut rows: Vec<Value> = theta_ratio_index(env.inp()?)
                .into_iter()
                .map(|((sc, ld, phi, sp), (e, c))| {
                    json!([sc, f64::from_bits(ld), f64::from_bits(phi), sp, fnum(e), fnum(c)])
                })
                .collect();
            rows.sort_by(|x, y| {
                let k = |v: &Value| {
                    (v[0].as_str().unwrap_or_default().to_string(), v[3].as_str().unwrap_or_default().to_string())
                };
                let f = |v: &Value, i: usize| v[i].as_f64().unwrap_or(f64::NAN);
                k(x).0
                    .cmp(&k(y).0)
                    .then(f(x, 1).total_cmp(&f(y, 1)))
                    .then(f(x, 2).total_cmp(&f(y, 2)))
                    .then(k(x).1.cmp(&k(y).1))
            });
            Value::Array(rows)
        }
        "fixed_coefficients" => json!(fixed_coefficients()),
        "plant_with_overrides" => {
            let inp = env.inp()?;
            let d = inp.designs.get(s(a, "compressor")?).ok_or_else(|| DesignError::new("KeyError", "compressor"))?;
            let ov: Vec<(String, f64)> = a
                .get("overrides")
                .and_then(Value::as_object)
                .map(|o| o.iter().map(|(k, v)| (k.clone(), as_f64(v).unwrap_or(f64::NAN))).collect())
                .unwrap_or_default();
            let ovr: Vec<(&str, f64)> = ov.iter().map(|(k, v)| (k.as_str(), *v)).collect();
            let p = plant_with_overrides(inp, d, &ovr)?;
            let ch = p.characteristic()?;
            json!({"characteristic": ch.iter().map(|(a, b)| json!([fnum(*a), fnum(*b)])).collect::<Vec<_>>(),
                   "leak_m3_s": fnum(p.leak_m3_s()), "shaft_hz": fnum(p.shaft_hz())})
        }
        "state_eval" => {
            let inp = env.inp()?;
            let cand = s(a, "candidate")?;
            let sc = s(a, "scenario")?;
            let states: Vec<_> =
                inp.states.iter().map(|st| inp.record(cand, sc, st).cloned()).collect::<DResult<_>>()?;
            let fc = inp.filter(s(a, "filter")?)?;
            let side = abep_gaspath::plenum_feed::intake_side(&states, fc, 1.0)?;
            let pl = plenum(inp, f(a, "V")?, s(a, "wall")?)?;
            let ev = state_eval(inp, &states, inp.plant(s(a, "compressor")?)?, &pl, f(a, "P")?, &side)?;
            json!({"bits": ev.bits, "all_ok": ev.all_ok,
                   "mdot_min": ev.mdot_min.iter().map(|x| fnum(*x)).collect::<Vec<_>>(),
                   "P_el_max": ev.p_el_max.iter().map(|x| fnum(*x)).collect::<Vec<_>>(),
                   "m_comp_max": ev.m_comp_max.iter().map(|x| fnum(*x)).collect::<Vec<_>>(),
                   "deadhead_margin": ev.deadhead_margin.iter().map(|x| fnum(*x)).collect::<Vec<_>>()})
        }
        "draw_sha" => {
            let inp = env.inp()?;
            let idx = record_se_index(inp)?;
            let n = a.get("n").and_then(Value::as_u64).unwrap_or(1) as usize;
            let d = draw(inp, &idx, s(a, "candidate")?, s(a, "scenario")?, n)?;
            json!({"z_sha256": sha_f64(&d.z), "drag_max_sha256": sha_f64(&d.drag_max),
                   "seed": abep_uq::mc::stable_seed(&["tpmc", s(a, "candidate")?, s(a, "scenario")?])})
        }
        "tpmc_monte_carlo" => {
            let inp = env.inp()?;
            let cands: Vec<Survivor> = a
                .get("survivors")
                .and_then(Value::as_array)
                .ok_or_else(|| bad("survivors"))?
                .iter()
                .map(survivor_of)
                .collect::<DResult<_>>()?;
            let res = tpmc_monte_carlo(
                inp,
                &cands,
                &sl(a, "scenarios")?.unwrap_or_default(),
                a.get("n").and_then(Value::as_u64).unwrap_or(1) as usize,
                s(a, "wall")?,
            )?;
            let mut out = Map::new();
            for ((c, fi, k, p), recs) in res {
                let key = format!("{c}|{fi}|{k}|{}", abep_types::pyjson::float_repr(f64::from_bits(p)));
                out.insert(key, Value::Object(recs.into_iter().map(|(sc, r)| (sc, r.to_value())).collect()));
            }
            Value::Object(out)
        }
        "pointing_sensitivity" => {
            let inp = env.inp()?;
            let cands: Vec<Survivor> = a
                .get("survivors")
                .and_then(Value::as_array)
                .ok_or_else(|| bad("survivors"))?
                .iter()
                .map(survivor_of)
                .collect::<DResult<_>>()?;
            per_value(pointing_sensitivity(inp, &cands, &sl(a, "scenarios")?.unwrap_or_default(), s(a, "wall")?)?)
        }
        "compressor_elasticities" => {
            let inp = env.inp()?;
            let c = survivor_of(a.get("survivor").ok_or_else(|| bad("survivor"))?)?;
            let r = compressor_elasticities(
                inp,
                &c,
                &sl(a, "scenarios")?.unwrap_or_default(),
                s(a, "wall")?,
                a.get("step").and_then(as_f64).unwrap_or(abep_uq::sens::ELASTICITY_STEP),
            )?;
            Value::Object(r.into_iter().collect())
        }
        "design_gate_snapshot" => design_gate_snapshot(repo)?,
        "uq_axes" => to_serde(&abep_uq::axes::uq_axes(&env.inp()?.states)),
        // ------------------------------------------------------------------ B2-OF-01 diagnostic
        "interp_sensitivity" => {
            let p = fl(a, "point")?;
            env.diag()?.evaluate(s(a, "table")?, [p[0], p[1], p[2], p[3]])?
        }
        other => return Err(bad(format!("unknown entry {other:?}"))),
    })
}

fn outcome(r: DResult<Value>) -> Value {
    match r {
        Ok(v) => json!({"outcome": "RETURNED", "value": v}),
        Err(e) => json!({"outcome": "RAISED", "class": e.class, "message": e.message, "status": e.status().as_str()}),
    }
}

fn spec_of(v: &Value) -> DResult<StudySpec> {
    Ok(StudySpec {
        candidates: sl(v, "candidates")?,
        compressors: sl(v, "compressors")?,
        n_mc: v.get("n_mc").and_then(Value::as_u64).unwrap_or(100) as usize,
        sensitivity_fractions: v
            .get("sensitivity_fractions")
            .and_then(Value::as_array)
            .map(|a| a.iter().filter_map(Value::as_f64).collect())
            .unwrap_or_default(),
    })
}

fn write_json(path: &Path, v: &Value) -> std::io::Result<()> {
    let mut f = std::fs::File::create(path)?;
    serde_json::to_writer(&mut f, v)?;
    f.write_all(b"\n")
}

fn study(env: &Env, spec_path: &Path, out: &Path) -> DResult<Value> {
    let spec_v: Value = serde_json::from_slice(&std::fs::read(spec_path).map_err(|e| bad(e.to_string()))?)
        .map_err(|e| bad(e.to_string()))?;
    let spec = spec_of(&spec_v)?;
    std::fs::create_dir_all(out).map_err(|e| bad(e.to_string()))?;
    let inp = env.inp()?;
    let t0 = std::time::Instant::now();
    let mut index = vec![];
    let mut io_err: Option<String> = None;
    let f7 = stage_f7(inp, &spec, &mut |i, ctx| {
        let mut buf = Vec::with_capacity(ctx.bits.len() * 8 * (1 + ARRAY_KEYS.len()));
        for b in &ctx.bits {
            buf.extend_from_slice(&b.to_le_bytes());
        }
        for a in &ctx.arrays {
            for x in a {
                buf.extend_from_slice(&x.to_le_bytes());
            }
        }
        if let Err(e) = std::fs::write(out.join(format!("ctx_{i:03}.bin")), &buf) {
            io_err = Some(e.to_string());
        }
        index.push(json!({"i": i, "scenario": ctx.scenario, "filter": ctx.filter, "wall": ctx.wall,
                          "shape": ctx.shape(), "context_role": ctx.context_role,
                          "design_direction": ctx.design_direction, "arrays": ARRAY_KEYS}));
    })?;
    if let Some(e) = io_err {
        return Err(bad(e));
    }
    let t_f7 = t0.elapsed().as_secs_f64();
    write_json(&out.join("contexts.json"), &Value::Array(index)).map_err(|e| bad(e.to_string()))?;
    let pareto: Vec<Value> = f7
        .pareto
        .iter()
        .map(|((sc, fi, w), blocks)| {
            json!({"scenario": sc, "filter": fi, "wall": w,
                   "blocks": blocks.iter().map(|b| json!({"P_set_Pa": b.p_set_pa, "block": b.to_value()})).collect::<Vec<_>>()})
        })
        .collect();
    write_json(&out.join("pareto.json"), &Value::Array(pareto)).map_err(|e| bad(e.to_string()))?;
    let t1 = std::time::Instant::now();
    let f8 = stage_f8(&env.repo, inp, &f7, &spec)?;
    let t_f8 = t1.elapsed().as_secs_f64();
    let mut f8v = f8_value(&f8);
    if let Value::Object(m) = &mut f8v {
        m.insert("carried_robust_set".into(), carried_value(&f8, "parity", "parity")?);
        m.insert("decomposition".into(), robust_decomposition(&f8));
    }
    write_json(&out.join("f8.json"), &f8v).map_err(|e| bad(e.to_string()))?;
    // B2-OF-01 application to the chain's candidates (prereg AT-08)
    let cands: Vec<(String, f64, f64)> = spec
        .candidates
        .clone()
        .unwrap_or_else(|| inp.candidates.clone())
        .iter()
        .map(|c| {
            let g = inp.geometry[c];
            (c.clone(), g.1, g.2)
        })
        .collect();
    let mut seen = std::collections::BTreeSet::new();
    let uniq: Vec<(String, f64, f64)> =
        cands.into_iter().filter(|(_, ld, phi)| seen.insert((ld.to_bits(), phi.to_bits()))).collect();
    let app = chain_application(env.diag()?, &uniq, &inp.scenarios)?;
    write_json(&out.join("interp_sensitivity_chain.json"), &app).map_err(|e| bad(e.to_string()))?;
    Ok(json!({"t_f7_s": t_f7, "t_f8_s": t_f8, "n_contexts": f7.pareto.len(),
              "decomposition": robust_decomposition(&f8)}))
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let repo = abep_provenance::workspace_repo_root().unwrap_or_else(|_| PathBuf::from("."));
    let env = Env { repo, inp: OnceCell::new(), diag: OnceCell::new() };
    match args.get(1).map(String::as_str) {
        Some("eval") if args.len() == 3 => {
            let calls: Value =
                serde_json::from_slice(&std::fs::read(&args[2]).expect("calls file")).expect("calls json");
            let mut out = vec![];
            for c in calls.as_array().expect("list") {
                let entry = c.get("entry").and_then(Value::as_str).unwrap_or_default();
                let a = c.get("args").cloned().unwrap_or(Value::Null);
                let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| dispatch(&env, entry, &a)));
                out.push(match r {
                    Ok(r) => outcome(r),
                    Err(_) => json!({"outcome": "PANIC", "entry": entry}),
                });
            }
            println!("{}", Value::Array(out));
        }
        Some("study") if args.len() == 4 => {
            let r = study(&env, Path::new(&args[2]), Path::new(&args[3]));
            println!("{}", outcome(r));
        }
        _ => {
            eprintln!("usage: abep-design-uq eval <calls.json> | study <spec.json> <out_dir>");
            std::process::exit(2);
        }
    }
}

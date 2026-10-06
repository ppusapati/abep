"""SC-WP-10 parity harness (design / UQ lane): F7 design synthesis and F8 robust optimisation / UQ.

Contracts (committed alone before any comparison):
  docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY/parity_prereg_v1.json   (F7)
  docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY/parity_prereg_v1.json         (F8 + abep-rng)

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 scripts/rust_migration/parity_sc_wp10.py dev     # development
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 scripts/rust_migration/parity_sc_wp10.py score   # once

Development runs use the development master seeds and the development sub-grid only and never write into the
contract directories. The scoring run uses the scoring master seeds and the full F7 / F8 grid, refuses to run twice
(a parity_report_v1.json exists) and writes both reports whatever the verdict. The Python reference is imported
read-only; nothing in the repository is modified except the reports and the captured reference outputs.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from abep_sim.design import architecture_optimizer as ao  # noqa: E402
from abep_sim.design import intake_synthesis as isy  # noqa: E402
from abep_sim.design import plenum_feed as pf  # noqa: E402
from abep_sim.design import robust_optimizer as ro  # noqa: E402
from abep_sim.design import upstream_a9_13 as u13  # noqa: E402
from abep_sim.design import a9_19_architecture as a919  # noqa: E402
from abep_sim.programme import design_synthesis as ds  # noqa: E402

C7 = ROOT / "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ARCHITECTURE_OPTIMIZER_PY"
C8 = ROOT / "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY"
SCRATCH = Path(os.environ.get("WP10_SCRATCH", "/tmp/wp10_parity"))
BIN = ROOT / "target/release/abep-design-uq"
K_ULP, R_REL = 4, 1e-9
SEEDS = {"f7": {"score": 1006202610, "dev": 1006202611}, "f8": {"score": 1006202620, "dev": 1006202621}}


# =============================================================================================== helpers
def sha_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def ulp(x: float) -> float:
    return math.ulp(x) if math.isfinite(x) else 0.0


def as_float(v):
    if isinstance(v, str) and v in ("NaN", "+inf", "-inf"):
        return {"NaN": math.nan, "+inf": math.inf, "-inf": -math.inf}[v]
    return v


def float_ok(py, rs) -> tuple[bool, float, float]:
    py, rs = float(py), float(rs)
    if math.isnan(py) or math.isnan(rs):
        return (math.isnan(py) and math.isnan(rs)), 0.0, 0.0
    if math.isinf(py) or math.isinf(rs):
        return py == rs, 0.0, 0.0
    d = abs(py - rs)
    u = d / ulp(py) if ulp(py) > 0 else (0.0 if d == 0 else math.inf)
    return (d <= K_ULP * ulp(py) or d <= R_REL * max(1.0, abs(py))), d, u


def canon(v):
    """Python reference value -> JSON-shaped (tuples to lists, numpy scalars to Python, NaN kept as float)."""
    if isinstance(v, dict):
        return {str(k): canon(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [canon(x) for x in v]
    if isinstance(v, np.ndarray):
        return [canon(x) for x in v.tolist()]
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return v


class Cmp:
    """Structural comparison: dict key sets, list lengths and order, floats ULP_BOUNDED, everything else exact."""

    def __init__(self):
        self.n_float = self.n_bit = self.n_exact = 0
        self.max_ulp = 0.0
        self.max_abs = 0.0
        self.fails: list[str] = []

    def __call__(self, py, rs, path="", exact_floats=False):
        rs = as_float(rs)
        if isinstance(py, bool) or isinstance(rs, bool):
            self.n_exact += 1
            if py is not rs and py != rs:
                self.fails.append(f"{path}: {py!r} != {rs!r}")
            return
        if isinstance(py, float) or (isinstance(py, int) and isinstance(rs, float)):
            if not isinstance(rs, (int, float)):
                self.fails.append(f"{path}: float {py!r} vs {rs!r}")
                return
            self.n_float += 1
            if exact_floats:
                ok = (math.isnan(py) and math.isnan(rs)) or float(py) == float(rs)
                d, u = abs(float(py) - float(rs)) if ok is False else 0.0, 0.0
            else:
                ok, d, u = float_ok(py, rs)
            if float(py) == float(rs) or (math.isnan(float(py)) and math.isnan(float(rs))):
                self.n_bit += 1
            self.max_ulp = max(self.max_ulp, u if math.isfinite(u) else 1e300)
            self.max_abs = max(self.max_abs, d)
            if not ok:
                self.fails.append(f"{path}: py {py!r} rust {rs!r}")
            return
        if isinstance(py, dict):
            if not isinstance(rs, dict) or set(py) != set(rs):
                self.fails.append(f"{path}: keys {sorted(py)[:8]} vs {sorted(rs)[:8] if isinstance(rs, dict) else rs!r}")
                return
            for k in py:
                self(py[k], rs[k], f"{path}/{k}", exact_floats)
            return
        if isinstance(py, list):
            if not isinstance(rs, list) or len(py) != len(rs):
                self.fails.append(f"{path}: list len {len(py)} vs {len(rs) if isinstance(rs, list) else rs!r}")
                return
            for i, (a, b) in enumerate(zip(py, rs)):
                self(a, b, f"{path}[{i}]", exact_floats)
            return
        self.n_exact += 1
        if py != rs:
            self.fails.append(f"{path}: {py!r} != {rs!r}")

    def summary(self):
        return {"float_leaves": self.n_float, "bit_identical": self.n_bit, "exact_leaves": self.n_exact,
                "max_ulp": self.max_ulp, "max_abs_diff": self.max_abs, "failures": len(self.fails),
                "first_failures": self.fails[:20]}


def py_call(fn, *a, **kw):
    try:
        return {"outcome": "RETURNED", "value": canon(fn(*a, **kw))}
    except Exception as e:  # noqa: BLE001 - the class is an observable
        return {"outcome": "RAISED", "class": type(e).__name__, "message": str(e)}


MESSAGE_CLASSES = {"OptimizerError", "A913RuleError", "ArchitectureRuleError"}


def compare_outcome(cmp: Cmp, py, rs, path, exact_floats=False):
    if rs.get("outcome") == "PANIC":
        cmp.fails.append(f"{path}: Rust PANIC")
        return
    if py["outcome"] != rs["outcome"]:
        cmp.fails.append(f"{path}: outcome py {py['outcome']} {py.get('class')} {py.get('message', '')[:200]!r} | "
                         f"rust {rs['outcome']} {rs.get('class')} {rs.get('message', '')[:200]!r}")
        return
    if py["outcome"] == "RAISED":
        cmp.n_exact += 1
        if py["class"] != rs["class"]:
            cmp.fails.append(f"{path}: class {py['class']} != {rs['class']} ({py['message']!r} | {rs['message']!r})")
        elif py["class"] in MESSAGE_CLASSES and py["message"] != rs["message"]:
            cmp.fails.append(f"{path}: message {py['message']!r} != {rs['message']!r}")
        return
    cmp(py["value"], rs["value"], path, exact_floats)


def rust_eval(calls: list, tag: str) -> list:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    p = SCRATCH / f"calls_{tag}.json"
    p.write_text(json.dumps(calls, allow_nan=False), encoding="utf-8")
    r = subprocess.run([str(BIN), "eval", str(p)], cwd=ROOT, capture_output=True, check=True)
    return json.loads(r.stdout)


def cargo_build():
    env = dict(os.environ, PATH=f"/root/.cargo/bin:{os.environ.get('PATH', '')}", CARGO_INCREMENTAL="0")
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "abep-uq", "--bin", "abep-design-uq"], cwd=ROOT,
                   check=True, env=env, capture_output=True)


def jsonable(x):
    """Inputs for the Rust side: floats as JSON numbers (non-finite as the registered strings)."""
    if isinstance(x, float) and not math.isfinite(x):
        return "NaN" if math.isnan(x) else ("+inf" if x > 0 else "-inf")
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (np.floating,)):
        return jsonable(float(x))
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


# =============================================================================================== F7 entries
def rec_dict(r: pf.IntakeState) -> dict:
    sp = lambda d: {s: float(d[s]) for s in ("O", "N2", "O2")}  # noqa: E731
    return {"area_m2": float(r.area_m2), "T_K": float(r.T_K), "mdot_fwd_kgps": sp(r.mdot_fwd_kgps),
            "p_passive_Pa": sp(r.p_passive_Pa), "K_back": sp(r.K_back), "f1_status": r.f1_status}


def ctx_dict(ctx: dict) -> dict:
    return {"scenario": ctx["scenario"], "filter": ctx["filter"], "wall": ctx["wall"],
            "candidates": list(ctx["candidates"]), "compressors": list(ctx["compressors"]),
            "volumes": [float(v) for v in ctx["volumes"]], "targets": [float(t) for t in ctx["targets"]],
            "bits": ctx["bits"].ravel().tolist(),
            "arrays": {k: [float(x) for x in ctx["arrays"][k].ravel()] for k in ctx["arrays"]},
            "context_role": ctx["context_role"], "design_direction": list(ctx["design_direction"])}


def pareto_list(par: dict) -> list:
    out = []
    for P, b in par.items():
        b = dict(b)
        b["members"] = [{k: v for k, v in m.items() if k != "ripple_feed_quality"} for m in b["members"]]
        out.append({"P_set_Pa": float(P), "block": canon(b)})
    return out


def py_rank_precheck(evals, ups):
    r = ds.rank_full_system(evals, tuple(ups))
    st = r["status"]
    if st in (ao.RANK_REFUSED_INCOMPLETE, ao.RANK_REFUSED_PARAMETRIC_UPSTREAM) or (
            st == ao.RANK_REFUSED_NO_FEASIBLE and not evals):
        return canon(r)
    return {"status": "PROCEED_TO_ASSESSMENT"}


def f7_vectors(inp, rng_for) -> list:
    """(entry, args, python callable) triples of the F7 contract."""
    V = []
    add = lambda e, a, f: V.append((e, a, f))  # noqa: E731
    add("inputs.summary", {}, lambda: {"candidates": list(inp.candidates),
                                        "geometry": {c: list(inp.geometry[c]) for c in inp.candidates},
                                        "scenarios": list(inp.scenarios), "states": list(ao.states()),
                                        "compressor_ids": list(inp.plants), "filter_ids": list(inp.filters)})
    g = rng_for(1)
    keys = [[inp.candidates[g.integers(len(inp.candidates))], inp.scenarios[g.integers(len(inp.scenarios))],
             ao.states()[g.integers(len(ao.states()))]] for _ in range(2000)]
    add("inputs.records", {"keys": keys}, lambda: [rec_dict(inp.records[tuple(k)]) for k in keys])
    # randomized upstream_context / context_pareto sub-grids
    g = rng_for(2)
    vols_pool = [1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 1.0]
    comps = list(inp.plants)
    for i in range(40):
        a = {"scenario": inp.scenarios[g.integers(len(inp.scenarios))],
             "filter": list(inp.filters)[g.integers(len(inp.filters))],
             "wall": ao.WALL_CASES[g.integers(2)],
             "candidates": [inp.candidates[j] for j in sorted(g.choice(len(inp.candidates), g.integers(1, 7), replace=False))],
             "compressors": [comps[j] for j in sorted(g.choice(len(comps), g.integers(1, 7), replace=False))],
             "volumes": [vols_pool[j] for j in sorted(g.choice(len(vols_pool), g.integers(1, 4), replace=False))],
             "targets": sorted(float(10 ** g.uniform(-3, math.log10(0.15))) for _ in range(g.integers(1, 5)))}
        f = lambda a=a: ao.upstream_context(inp, a["scenario"], a["filter"], a["wall"], tuple(a["volumes"]),  # noqa
                                            tuple(a["targets"]), tuple(a["candidates"]), tuple(a["compressors"]))
        add("upstream_context", a, lambda f=f: ctx_dict(f()))
        add("context_pareto", a, lambda f=f: pareto_list(ds.context_pareto(f())))
    # edge cases E-01..E-04
    base = {"scenario": "maxwell_a0", "filter": "F4-FIL-NONE", "wall": "WALL-G0", "volumes": [0.01],
            "targets": [0.01], "candidates": [inp.candidates[0]], "compressors": [comps[0]]}
    for k, v in (("scenario", "not_a_scenario"), ("wall", "WALL-X"), ("filter", "F4-FIL-X"),
                 ("targets", [0.12, 0.5])):
        a = dict(base, **{k: v})
        add("upstream_context", a, lambda a=a: ctx_dict(ao.upstream_context(
            inp, a["scenario"], a["filter"], a["wall"], tuple(a["volumes"]), tuple(a["targets"]),
            tuple(a["candidates"]), tuple(a["compressors"]))))
    # pareto_mask / nondominated_layers
    g = rng_for(3)
    for i in range(300):
        n, k = int(g.integers(1, 301)), int(g.integers(1, 9))
        F = g.integers(0, 6, size=(n, k)).astype(float)
        if g.random() < 0.1:
            for _ in range(int(g.integers(1, 4))):
                F[g.integers(n), g.integers(k)] = [math.nan, math.inf, -math.inf][g.integers(3)]
        senses = ["max" if g.random() < 0.5 else "min" for _ in range(k)]
        add("pareto_mask", {"F": F.tolist(), "senses": senses},
            lambda F=F, s=senses: ao.pareto_mask(F, s).tolist())
    add("pareto_mask", {"F": [[1.0, 2.0]], "senses": ["min"]}, lambda: ao.pareto_mask(np.array([[1.0, 2.0]]), ["min"]))
    g = rng_for(4)
    for i in range(100):
        n, k = int(g.integers(1, 121)), int(g.integers(1, 7))
        F = g.integers(0, 8, size=(n, k)).astype(float)
        senses = ["max" if g.random() < 0.5 else "min" for _ in range(k)]
        add("nondominated_layers", {"F": F.tolist(), "senses": senses},
            lambda F=F, s=senses: ao.nondominated_layers(F, s).tolist())
    add("nondominated_layers", {"F": [[math.nan, 1.0]], "senses": ["min", "min"]},
        lambda: ao.nondominated_layers(np.array([[math.nan, 1.0]]), ["min", "min"]).tolist())
    # small functions
    for (c, fi, k, Vv, P) in (("A1_Ld10_phi0.9", "F4-FIL-NONE", comps[0], 0.01, 0.02), ("A0.25_Ld3_phi0.8", "x", "y", 1e-3, 0.1)):
        add("design_id", {"cand": c, "filt": fi, "comp": k, "V": Vv, "P": P}, lambda c=c, fi=fi, k=k, Vv=Vv, P=P: ao.design_id(c, fi, k, Vv, P))
        add("context_id", {"scenario": "cll_a0.2", "filt": fi, "wall": "WALL-G0", "P": P}, lambda fi=fi, P=P: ao.context_id("cll_a0.2", fi, "WALL-G0", P))
    for w in ("WALL-G0", "WALL-TI64-DB", "WALL-X"):
        add("wall_gamma", {"wall": w}, lambda w=w: ao.wall_gamma(w))
        for Vv in (1e-3, 0.1):
            add("plenum", {"V": Vv, "wall": w}, lambda w=w, Vv=Vv: (lambda p: {"volume_m3": p.volume_m3, "gamma_wall": p.gamma_wall,
                                                                                "wall_case": p.wall_case, "leak_area_m2": p.leak_area_m2})(ao.plenum(Vv, w)))
    for fi in inp.filters:
        add("context_role", {"filter": fi}, lambda fi=fi: ao.context_role(inp.filters[fi]))
    add("higher_pressure_branch", {"targets": [0.2, 0.5, 1.0]}, lambda: ao.higher_pressure_branch())
    add("higher_pressure_branch", {"targets": [0.0]}, lambda: ao.higher_pressure_branch((0.0,)))
    # rank_full_system refusal stages
    g = rng_for(5)
    statuses = list(ao.OBJECTIVE_STATUSES)
    names = [n for n, _ in ao.SYSTEM_OBJECTIVES] + ["life_material"]
    for i in range(60):
        evals = []
        for j in range(int(g.integers(0, 5))):
            objs = {}
            for nm in names:
                st = statuses[g.integers(len(statuses))] if g.random() < 0.5 else ["EVALUATED", "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"][g.integers(2)]
                val = None if g.random() < 0.15 else float(g.integers(0, 5))
                objs[nm] = {"status": st, "value": val}
            ev = {"design_id": f"d{j}", "objectives": objs}
            ups = []
            if g.random() < 0.5:
                ups = list(ao.OBJ_KEYS[:int(g.integers(1, 3))])
                ev["upstream"] = {}
                for u in ups:
                    if g.random() < 0.5:
                        ev["upstream"][u] = {"value": float(g.integers(0, 5)), "status": ["EVALUATED", "PARAMETRIC_SENSITIVITY_ONLY", "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"][g.integers(3)]}
                    else:
                        ev["upstream"][u] = float(g.integers(0, 5))
                        if g.random() < 0.5:
                            ev.setdefault("upstream_status", {})[u] = "EVALUATED"
            ev["constraints"] = []
            evals.append(ev)
        ups_all = sorted({u for e in evals for u in (e.get("upstream") or {})})
        add("rank_precheck", {"evaluations": evals, "upstream_objectives": ups_all},
            lambda evals=evals, ups=ups_all: py_rank_precheck(evals, ups))
    # scenario rules
    g = rng_for(6)
    scs = list(inp.scenarios)
    for i in range(120):
        adm = [scs[j] for j in sorted(g.choice(len(scs), g.integers(0, len(scs) + 1), replace=False))]
        used = [scs[j] for j in sorted(g.choice(len(scs), g.integers(0, len(scs) + 1), replace=False))]
        if g.random() < 0.3:
            used = list(adm)
        nr = None
        if g.random() < 0.4:
            nr = {"preregistration_id": "P", "measurement_source": "M", "mapping": "X", "admitted_range": "R",
                  "evidence_status": "EVIDENCE"}
            if g.random() < 0.5:
                nr[["preregistration_id", "measurement_source", "mapping", "admitted_range", "evidence_status"][g.integers(5)]] = " "
        add("require_all_admitted_scenarios", {"used": used, "admitted": adm, "narrowing_record": nr},
            lambda u=used, a=adm, n=nr: u13.require_all_admitted_scenarios(u, a, n))
        per = [[s, bool(g.random() < 0.7)] for s in adm]
        add("robust_over_scenarios", {"per_scenario": per, "admitted": adm},
            lambda per=per, a=adm: u13.robust_over_scenarios(dict((s, b) for s, b in per), a))
    # records
    add("design_vector_blocks", {}, lambda: ao.design_vector_blocks())
    add("architecture_questions", {}, lambda: ao.architecture_questions())
    for c in ("hall_icp_neutralizer", "hall_c1_reference", "nope"):
        add("flight_configuration_elements", {"config": c}, lambda c=c: ao.flight_configuration_elements(c))
    g = rng_for(7)
    for x in [None, 0.0] + [float(g.uniform(0, 500)) for _ in range(18)]:
        add("heat_rejection", {"compressor_P_W": x}, lambda x=x: ao.heat_rejection(x))
    for c in ("hall_icp_neutralizer", "nope"):
        add("electron_margin", {"config": c}, lambda c=c: ao.electron_margin(c))
    for rec in (None, {"objective": "thrust_N", "status": "EVALUATED", "value": 0.02, "units": "N"},
                {"objective": "thrust_N", "status": "PARAMETRIC_SENSITIVITY_ONLY", "value": 0.02},
                {"objective": "thrust_N", "status": "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE", "value": 0.02, "units": "N"}):
        add("hall_gated_thrust", {"name": "thrust_N", "rec": rec}, lambda rec=rec: ao.hall_gated_thrust("thrust_N", rec))
    add("tpmc_backend_policy", {}, lambda: ao.tpmc_backend_policy())
    g = rng_for(8)
    frags = ["if", "If", "IF", "c1", "C1", "C-1", "c-1", "is", "selected", "Selected", "C2", "x"]
    mp = ao.read_json(ao.MP_REL)
    names_mp = [ln.get("name") for ln in mp["lines"]["hall_icp_neutralizer"]]
    texts = list(names_mp)
    for i in range(60 - len(texts)):
        texts.append("".join(frags[g.integers(len(frags))] + [" ", "  ", "\t", "", "-"][g.integers(5)] for _ in range(g.integers(1, 6))))
    for t in texts:
        add("is_conditional_c1_text", {"text": t}, lambda t=t: a919.is_conditional_c1_text(t))
    return V


# =============================================================================================== F8 entries
def survivor_args(s: dict) -> dict:
    return {k: (float(v) if isinstance(v, float) else v) for k, v in s.items()}


def mc_dict(res: dict) -> dict:
    return {f"{c}|{fi}|{k}|{P!r}": canon(per) for (c, fi, k, P), per in res.items()}


def f8_vectors(inp, rng_for, surv_pool: list) -> list:
    V = []
    add = lambda e, a, f: V.append((e, a, f))  # noqa: E731
    g = rng_for(1)
    seeds = [int(g.integers(0, 2 ** 31 - 1)) for _ in range(200)] + \
            [int.from_bytes(g.bytes(16), "little") for _ in range(100)] + [0, 2 ** 128 - 1, 2 ** 160 + 12345]
    for i, sd in enumerate(seeds):
        nn = int(g.integers(1, 20001))
        a = {"seed": str(sd), "n_u64": 64, "n_random": 64, "n_normal": nn}

        def f(sd=sd, nn=nn):
            ss = np.random.SeedSequence(sd)
            bg = np.random.PCG64(ss)
            st = bg.state["state"]
            raw = np.random.PCG64(np.random.SeedSequence(sd))
            words = [str(int(x)) for x in raw.random_raw(64)]
            gr = np.random.Generator(np.random.PCG64(np.random.SeedSequence(sd)))
            rnd = [float(x) for x in gr.random(64)]
            z = np.random.default_rng(sd).standard_normal(nn)
            return {"pool": [int(x) for x in ss.pool], "generate_state_u32_8": [int(x) for x in ss.generate_state(8)],
                    "generate_state_u64_4": [str(int(x)) for x in ss.generate_state(4, np.uint64)],
                    "pcg64_state": str(st["state"]), "pcg64_inc": str(st["inc"]), "next_uint64": words,
                    "random": rnd, "normal_sha256": hashlib.sha256(z.astype("<f8").tobytes()).hexdigest(),
                    "normal_head": [float(x) for x in z[:16]], "n_normal": nn}
        add("rng.stream", a, f)
    g = rng_for(2)
    alphabet = list("abcXYZ019 |_-.:") + ["é", "α", "中"]
    for i in range(200):
        parts = ["".join(alphabet[g.integers(len(alphabet))] for _ in range(g.integers(0, 12))) for _ in range(g.integers(1, 5))]
        base = int(g.integers(0, 2 ** 31 - 1))
        add("stable_seed", {"parts": parts, "base": base}, lambda p=parts, b=base: isy.stable_seed(*p, base=b))
    for c in inp.candidates:
        for sc in inp.scenarios:
            add("stable_seed", {"parts": ["tpmc", c, sc], "base": ro.SEED_BASE}, lambda c=c, sc=sc: ro.stable_seed("tpmc", c, sc))
    # the study draw streams (every candidate x scenario, n = 100) by sha256
    se_idx = ro.record_se_index(inp.f1)

    def draw_py(cand, sc, n):
        A, Ld, phi = inp.geometry[cand]
        rng = np.random.default_rng(ro.stable_seed("tpmc", cand, sc))
        z = rng.standard_normal((n, len(ao.states()), 3, 3))
        drag = np.zeros((n, len(ao.states())))
        for i in range(n):
            for j, st in enumerate(ao.states()):
                d0, dse = inp.drag_per_area[(sc, Ld, phi, st)]
                drag[i, j] = A * (d0 + z[i, j, 2, 0] * dse)
        return {"z_sha256": hashlib.sha256(z.astype("<f8").tobytes()).hexdigest(),
                "drag_max_sha256": hashlib.sha256(drag.max(axis=1).astype("<f8").tobytes()).hexdigest(),
                "seed": ro.stable_seed("tpmc", cand, sc)}
    for c in inp.candidates:
        for sc in inp.scenarios:
            add("draw_sha", {"candidate": c, "scenario": sc, "n": 100}, lambda c=c, sc=sc: draw_py(c, sc, 100))
    g = rng_for(3)
    for i in range(300):
        n = int(g.integers(1, 401))
        a = np.round(g.normal(size=n), int(g.integers(0, 3))) if g.random() < 0.5 else g.normal(size=n)
        q = [5.0, 50.0, 95.0][g.integers(3)] if g.random() < 0.5 else float(g.uniform(0, 100))
        add("np_percentile", {"a": a.tolist(), "q": q}, lambda a=a, q=q: float(np.percentile(a, q)))
    add("np_percentile", {"a": [1.0, math.nan], "q": 50.0}, lambda: float(np.percentile(np.array([1.0, math.nan]), 50.0)))
    g = rng_for(4)
    st_all = ao.states()
    for i in range(2000):
        key = [inp.candidates[g.integers(len(inp.candidates))], inp.scenarios[g.integers(len(inp.scenarios))],
               st_all[g.integers(len(st_all))]]
        rec = inp.records[tuple(key)]
        area = float(g.uniform(0.1, 2.0))
        se = [float(abs(x)) * 1e-9 for x in g.normal(size=6)]
        zm = [float(x) for x in g.normal(scale=3.0, size=3)]
        zp = [float(x) for x in g.normal(scale=3.0, size=3)]
        if g.random() < 0.05:
            zm[0] = -1e12
            zp[1] = -1e12

        def f(rec=rec, area=area, se=se, zm=zm, zp=zp):
            sed = {s: (se[2 * k], se[2 * k + 1]) for k, s in enumerate(ao.SPECIES)}
            r = ro.perturbed(rec, area, sed, dict(zip(ao.SPECIES, zm)), dict(zip(ao.SPECIES, zp)))
            return {"mdot_fwd_kgps": [r.mdot_fwd_kgps[s] for s in ao.SPECIES],
                    "p_passive_Pa": [r.p_passive_Pa[s] for s in ao.SPECIES], "source": r.source}
        add("perturbed", {"key": key, "area": area, "se": se, "z_m": zm, "z_p": zp}, f)
    keys = [[float(k[0]), float(k[1]), k[2], k[3]] for k in list(se_idx)[:: max(1, len(se_idx) // 500)]]
    add("record_se_index", {"keys": keys}, lambda: [[list(se_idx[tuple(k)][s]) for s in ao.SPECIES] for k in keys])
    add("theta_ratio_index", {}, lambda: sorted(([k[0], float(k[1]), float(k[2]), k[3], float(v[0]), float(v[1])]
                                                 for k, v in ro.theta_ratio_index(inp.f1).items()),
                                                key=lambda r: (r[0], r[1], r[2], r[3])))
    add("fixed_coefficients", {}, lambda: ro.fixed_coefficients())
    g = rng_for(5)
    comps = list(inp.plants)
    fixed = ro.fixed_coefficients()
    for i in range(30):
        c = comps[g.integers(len(comps))]
        coef = fixed[g.integers(len(fixed))]
        from abep_sim.design import compressor_synthesis as cs
        val = float(cs.module_defaults()[coef]) * float(g.uniform(0.5, 1.5))
        ov = {coef: val}

        def f(c=c, ov=ov):
            p = ro.plant_with_overrides(inp.designs[c], ov)
            ch = p.characteristic()
            return {"characteristic": [list(ch[s]) for s in ao.SPECIES], "leak_m3_s": p.leak_m3_s, "shaft_hz": p.shaft_hz}
        add("plant_with_overrides", {"compressor": c, "overrides": ov}, f)
    for ov in ({"rpm": 1000.0}, {"eta_motor": 1.5}):
        add("plant_with_overrides", {"compressor": comps[0], "overrides": ov},
            lambda ov=ov: ro.plant_with_overrides(inp.designs[comps[0]], ov).characteristic())
    g = rng_for(6)
    for i in range(40):
        cand = inp.candidates[g.integers(len(inp.candidates))]
        sc = inp.scenarios[g.integers(len(inp.scenarios))]
        fi = list(inp.filters)[g.integers(len(inp.filters))]
        comp = comps[g.integers(len(comps))]
        Vv = [1e-3, 1e-2, 1e-1][g.integers(3)]
        wall = ao.WALL_CASES[g.integers(2)]
        P = list(ao.UPSTREAM_TARGETS_PA)[g.integers(6)]

        def f(cand=cand, sc=sc, fi=fi, comp=comp, Vv=Vv, wall=wall, P=P):
            states = [inp.records[(cand, sc, st)] for st in ao.states()]
            ev = ro._state_eval(states, inp.filters[fi], inp.plants[comp], ao.plenum(Vv, wall), P)
            return {"bits": ev["bits"].tolist(), "all_ok": ev["all_ok"].tolist(), "mdot_min": ev["mdot_min"].tolist(),
                    "P_el_max": ev["P_el_max"].tolist(), "m_comp_max": ev["m_comp_max"].tolist(),
                    "deadhead_margin": ev["deadhead_margin"].tolist()}
        add("state_eval", {"candidate": cand, "scenario": sc, "filter": fi, "compressor": comp, "V": Vv, "wall": wall,
                           "P": P}, f)
    # randomized tpmc_monte_carlo over the pool of survivors of this run's study grid
    g = rng_for(7)
    for i in range(40):
        if not surv_pool:
            break
        k = int(g.integers(1, min(6, len(surv_pool)) + 1))
        picks = [surv_pool[j] for j in sorted(g.choice(len(surv_pool), k, replace=False))]
        scs = [inp.scenarios[j] for j in sorted(g.choice(len(inp.scenarios), g.integers(1, len(inp.scenarios) + 1), replace=False))]
        n = int(g.integers(1, 41))
        wall = ao.WALL_CASES[g.integers(2)]
        add("tpmc_monte_carlo", {"survivors": [survivor_args(s) for s in picks], "scenarios": scs, "n": n, "wall": wall},
            lambda picks=picks, scs=scs, n=n, wall=wall: mc_dict(ro.tpmc_monte_carlo(inp, picks, scs, n=n, wall=wall)))
    if surv_pool:
        s0 = surv_pool[0]
        add("tpmc_monte_carlo", {"survivors": [survivor_args(s0)], "scenarios": list(inp.scenarios), "n": 1, "wall": "WALL-G0"},
            lambda: mc_dict(ro.tpmc_monte_carlo(inp, [s0], inp.scenarios, n=1)))
    add("design_gate_snapshot", {}, lambda: ro.design_gate_snapshot())
    add("uq_axes", {}, lambda: list(ro.UQ_AXES))
    return V


# =============================================================================================== study
def full_spec(dev: bool, seed: int, inp) -> dict:
    if not dev:
        return {"candidates": None, "compressors": None, "n_mc": 100}
    comps = list(inp.plants)
    if os.environ.get("WP10_DEV_GRID") == "supplementary":
        # supplementary development sub-grid (development seed; disclosed in the report's campaign_history): the
        # registered development sub-grid happened to contain no feasible upstream vector, so F8 needs a sub-grid
        # that reaches the feasible region (A0.25 intakes, T4-T6 rows) to be exercised before scoring
        g = np.random.default_rng(np.random.SeedSequence([seed, 1000]))
        a25 = [c for c in inp.candidates if c.startswith("A0.25_")]
        oth = [c for c in inp.candidates if not c.startswith("A0.25_")]
        hi = [k for k in comps if k[:2] in ("T4", "T5", "T6")]
        lo = [k for k in comps if k not in hi]
        cands = [a25[j] for j in g.choice(len(a25), 4, replace=False)] + \
            [oth[j] for j in g.choice(len(oth), 2, replace=False)]
        cps = [hi[j] for j in g.choice(len(hi), 6, replace=False)] + [lo[j] for j in g.choice(len(lo), 2, replace=False)]
        return {"candidates": sorted(cands, key=lambda c: inp.geometry[c]), "compressors": [k for k in comps if k in cps],
                "n_mc": 100}
    g = np.random.default_rng(np.random.SeedSequence([seed, 999]))
    return {"candidates": [inp.candidates[j] for j in sorted(g.choice(len(inp.candidates), 12, replace=False))],
            "compressors": [comps[j] for j in sorted(g.choice(len(comps), 8, replace=False))], "n_mc": 100}


def pick_indices(fractions: list, n: int) -> list:
    """The registered pick rule: floor(u * n), sorted, duplicates dropped."""
    return sorted({int(math.floor(u * n)) for u in fractions if 0.0 <= u < 1.0 and int(math.floor(u * n)) < n})


def py_study(inp, spec: dict, fractions: list):
    t0 = time.process_time()
    ctxs, pars, allctx = {}, {}, []
    for wall in ao.WALL_CASES:
        for filt in inp.filters:
            for sc in inp.scenarios:
                ctx = ao.upstream_context(inp, sc, filt, wall, candidates=spec["candidates"], compressors=spec["compressors"])
                pars[(sc, filt, wall)] = ds.context_pareto(ctx)
                allctx.append(ctx)
                if filt == ro.NOMINAL_FILTER:
                    ctxs[(sc, filt, wall)] = ctx
    t_f7 = time.process_time() - t0
    t1 = time.process_time()
    before = ro.design_gate_snapshot()
    surv = ro.survivors(pars)
    scen = ro.scenario_robustness(surv, ctxs, inp.scenarios, ro.NOMINAL_WALL)
    mc = ro.tpmc_monte_carlo(inp, surv, inp.scenarios, n=spec["n_mc"])
    allsc = [s for s in surv if scen[s["design_id"]]["worst_case_all_scenarios"] is not None]
    rp = ro.robust_pareto(allsc, scen, mc)
    mem_ids = sorted({m["design_id"] for b in rp.values() for m in b["members"]})
    mem = [s for s in surv if s["design_id"] in mem_ids]
    wall = ro.scenario_robustness(mem, ctxs, inp.scenarios, "WALL-TI64-DB")
    point = ro.pointing_sensitivity(inp, mem, inp.scenarios)
    elas = {m["design_id"]: ro.compressor_elasticities(inp, m, inp.scenarios) for m in mem}
    picks_idx = pick_indices(fractions, len(surv))
    picks = [surv[i] for i in picks_idx]
    pp0 = ro.pointing_sensitivity(inp, picks, inp.scenarios)
    pp1 = ro.pointing_sensitivity(inp, picks, inp.scenarios, "WALL-TI64-DB")
    pel = {m["design_id"]: ro.compressor_elasticities(inp, m, inp.scenarios) for m in picks}
    after = ro.design_gate_snapshot()
    carried = ro.carried_robust_set(rp, "parity", "parity")
    try:
        carried.representative()
        rep = "NOT_REFUSED"
    except Exception as e:  # noqa: BLE001
        rep = f"REFUSED {type(e).__name__}: {e}"
    t_f8 = time.process_time() - t1
    f8 = {"gates_before": canon(before), "gates_after": canon(after), "survivors": canon(surv), "scenario": canon(scen),
          "mc": mc_dict(mc), "all_scenario_feasible": [s["design_id"] for s in allsc],
          "robust_pareto": [{"P_set_Pa": float(P), "n_all_scenario_feasible": b["n_all_scenario_feasible"],
                             "members": canon(b["members"])} for P, b in rp.items()],
          "members": canon(mem), "wall": canon(wall), "pointing": canon(point), "elasticities": canon(elas),
          "picks": canon(picks), "picks_pointing_g0": canon(pp0), "picks_pointing_ti64": canon(pp1),
          "picks_elasticities": canon(pel), "pick_indices": picks_idx,
          "carried_robust_set": {"set_id": carried.set_id, "version": carried.version, "members": list(carried.members),
                                 "objectives": list(carried.objectives), "label": carried.label,
                                 "provenance": carried.provenance,
                                 "regeneration_triggers": list(carried.regeneration_triggers), "representative": rep}}
    return allctx, pars, f8, surv, {"t_f7_cpu_s": t_f7, "t_f8_cpu_s": t_f8}


def rust_study(spec: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    p = out / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    t0 = time.perf_counter()
    r = subprocess.run([str(BIN), "study", str(p), str(out)], cwd=ROOT, capture_output=True, check=True)
    res = json.loads(r.stdout)
    res["wall_s"] = time.perf_counter() - t0
    return res


def compare_contexts(allctx: list, out: Path) -> dict:
    idx = json.loads((out / "contexts.json").read_text())
    cmp = Cmp()
    n_bits = n_bits_diff = 0
    keys = ["mdot_delivered_min_kgps", "P_compressor_el_max_W", "m_compressor_max_kg", "ripple_transfer_shaft",
            "xO_flow_min", "xO_flow_max", "a_eq_design_m2", "deadhead_margin_min", "kn_upper_min", "T_comp_max_K",
            "mdot_delivered_design_kgps", "drag_intake_max_N", "drag_intake_max_se_N", "mdot_captured_min_kgps",
            "intake_wall_area_m2", "plenum_V_m3"]
    max_ulp = 0.0
    nfloat = nbit = 0
    for ctx, meta in zip(allctx, idx):
        path = f"ctx[{meta['i']}] {meta['scenario']}|{meta['filter']}|{meta['wall']}"
        if (ctx["scenario"], ctx["filter"], ctx["wall"]) != (meta["scenario"], meta["filter"], meta["wall"]):
            cmp.fails.append(f"{path}: order")
            continue
        cmp(ctx["context_role"], meta["context_role"], path + "/context_role")
        cmp(list(ctx["design_direction"]), meta["design_direction"], path + "/design_direction")
        shape = ctx["bits"].shape
        if list(shape) != meta["shape"]:
            cmp.fails.append(f"{path}: shape {shape} vs {meta['shape']}")
            continue
        n = int(np.prod(shape))
        raw = np.fromfile(out / f"ctx_{meta['i']:03d}.bin", dtype="<i8", count=n)
        fl = np.fromfile(out / f"ctx_{meta['i']:03d}.bin", dtype="<f8", offset=8 * n).reshape(len(keys), n)
        pb = ctx["bits"].ravel()
        n_bits += n
        d = np.nonzero(pb != raw)[0]
        n_bits_diff += len(d)
        for j in d[:20]:
            cmp.fails.append(f"{path}: bits[{j}] py {pb[j]} rust {raw[j]}")
        for ki, k in enumerate(keys):
            a = ctx["arrays"][k].ravel()
            b = fl[ki]
            nan_a, nan_b = np.isnan(a), np.isnan(b)
            if (nan_a != nan_b).any():
                jj = np.nonzero(nan_a != nan_b)[0]
                cmp.fails.append(f"{path}/{k}: NaN pattern differs at {len(jj)} cells (first {jj[0]})")
                continue
            m = ~nan_a
            if not m.any():
                continue
            aa, bb = a[m], b[m]
            diff = np.abs(aa - bb)
            ul = np.spacing(np.abs(aa))
            ok = (diff <= K_ULP * ul) | (diff <= R_REL * np.maximum(1.0, np.abs(aa)))
            nfloat += int(m.sum())
            nbit += int((aa == bb).sum())
            with np.errstate(divide="ignore", invalid="ignore"):
                u = np.where(ul > 0, diff / ul, 0.0)
            max_ulp = max(max_ulp, float(np.max(u)))
            if not ok.all():
                jj = np.nonzero(~ok)[0]
                cmp.fails.append(f"{path}/{k}: {len(jj)} cells out of tolerance (first py {aa[jj[0]]!r} rust {bb[jj[0]]!r})")
    s = cmp.summary()
    s.update({"contexts": len(allctx), "bit_cells": n_bits, "bit_cells_differing": n_bits_diff,
              "array_float_leaves": nfloat, "array_bit_identical": nbit, "array_max_ulp": max_ulp})
    return s


def compare_pareto(pars: dict, out: Path) -> dict:
    rs = json.loads((out / "pareto.json").read_text())
    cmp = Cmp()
    n_members = 0
    for ((sc, fi, w), par), r in zip(pars.items(), rs):
        path = f"{sc}|{fi}|{w}"
        if (sc, fi, w) != (r["scenario"], r["filter"], r["wall"]):
            cmp.fails.append(f"{path}: order")
            continue
        pl = pareto_list(par)
        n_members += sum(len(b["block"]["members"]) for b in pl)
        cmp(pl, r["blocks"], path)
    s = cmp.summary()
    s["pareto_members"] = n_members
    return s


def compare_f8(f8: dict, out: Path) -> tuple[dict, dict]:
    rs = json.loads((out / "f8.json").read_text())
    cmp = Cmp()
    for k in f8:
        if k == "pick_indices":
            continue
        cmp(f8[k], rs[k], k)
    return cmp.summary(), rs


# =============================================================================================== main
def reference_check(contract: dict) -> list:
    bad = []
    for f in contract["reference_implementation"]["files"]:
        if sha_file(ROOT / f["path"]) != f["sha256_at_registration"]:
            bad.append(f["path"])
    return bad


def run(mode: str):
    dev = mode == "dev"
    c7 = json.loads((C7 / "parity_prereg_v1.json").read_text())
    c8 = json.loads((C8 / "parity_prereg_v1.json").read_text())
    if not dev and ((C7 / "parity_report_v1.json").exists() or (C8 / "parity_report_v1.json").exists()):
        raise SystemExit("REFUSED: a parity_report_v1.json exists; the scoring comparison runs once")
    changed = reference_check(c7) + reference_check(c8)
    if changed:
        raise SystemExit(f"REFUSED_REFERENCE_CHANGED: {changed}")
    if np.__version__ != "2.4.4":
        raise SystemExit(f"REFUSED_REFERENCE_CHANGED: numpy {np.__version__}")
    cargo_build()
    tag = "dev" if dev else "score"
    inp = ao.load_upstream_inputs()
    seed7, seed8 = SEEDS["f7"][tag], SEEDS["f8"][tag]
    rng7 = lambda i: np.random.default_rng(np.random.SeedSequence([seed7, i]))  # noqa: E731
    rng8 = lambda i: np.random.default_rng(np.random.SeedSequence([seed8, i]))  # noqa: E731
    results = {}
    # ---------------------------------------------------------------- study (F7 + F8)
    spec = full_spec(dev, seed7, inp)
    fractions = [float(u) for u in rng8(99).random(6)]
    out = SCRATCH / f"study_{tag}"
    t_r = rust_study(dict(spec, sensitivity_fractions=fractions), out)
    allctx, pars, f8, surv_py, t_py = py_study(inp, spec, fractions)
    picks = f8["pick_indices"]
    results["study_contexts"] = compare_contexts(allctx, out)
    results["study_pareto"] = compare_pareto(pars, out)
    s8, rs8 = compare_f8(f8, out)
    results["study_f8"] = s8
    # ---------------------------------------------------------------- vectors
    v7 = f7_vectors(inp, rng7)
    v8 = f8_vectors(inp, rng8, surv_py)
    entries = {}
    for label, V in (("f7", v7), ("f8", v8)):
        calls = [{"entry": e, "args": jsonable(a)} for e, a, _ in V]
        rs = rust_eval(calls, f"{tag}_{label}")
        for (e, a, f), r in zip(V, rs):
            py = py_call(f)
            c = entries.setdefault((label, e), {"cmp": Cmp(), "n": 0, "py_raised": 0, "rust_raised": 0})
            c["n"] += 1
            c["py_raised"] += py["outcome"] == "RAISED"
            c["rust_raised"] += r.get("outcome") == "RAISED"
            exact = e in ("rng.stream", "draw_sha", "stable_seed")
            compare_outcome(c["cmp"], py, r, f"{e}#{c['n']}", exact_floats=exact)
    for (label, e), c in entries.items():
        results[f"{label}:{e}"] = dict(c["cmp"].summary(), n=c["n"], python_raised=c["py_raised"],
                                       rust_raised=c["rust_raised"])
    # ---------------------------------------------------------------- invariants
    inv = {
        "INV-F8-01 gates unchanged": {"python": f8["gates_before"] == f8["gates_after"],
                                      "rust": rs8["gates_before"] == rs8["gates_after"]},
        "INV-F8-02 robust set reported": {"python_n_members": sum(len(b["members"]) for b in f8["robust_pareto"]),
                                          "rust_n_members": sum(len(b["members"]) for b in rs8["robust_pareto"])},
        "INV-F8-04 no representative": {"python": f8["carried_robust_set"]["representative"].startswith("REFUSED"),
                                        "rust": rs8["carried_robust_set"]["representative"].startswith("REFUSED")},
        "INV-F7-01 members feasible": all(all(m["system_not_evaluated"] == list(ao.SYSTEM_NOT_EVALUATED_CODES)
                                              for b in par.values() for m in b["members"]) for par in pars.values()),
    }
    report = {"mode": tag, "spec": spec, "picks": picks, "rust_study": t_r, "python_study": t_py,
              "results": results, "invariants": inv, "decomposition_rust": rs8.get("decomposition")}
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / f"result_{tag}.json").write_text(json.dumps(report, indent=1, default=str))
    n_fail = sum(r.get("failures", 0) for r in results.values())
    print(json.dumps({k: {kk: v.get(kk) for kk in ("n", "failures", "max_ulp", "first_failures")} for k, v in results.items()},
                     indent=1, default=str)[:20000])
    print("TOTAL FAILURES", n_fail)
    if not dev:
        write_reports(report, c7, c8, inp, out, f8, rs8, pars)
    return report


# =============================================================================================== reports
F7_KEYS = ("study_contexts", "study_pareto")
F8_KEYS = ("study_f8",)


def provenance() -> dict:
    srcs = {}
    for base in ("crates/abep-design", "crates/abep-uq", "crates/abep-rng", "crates/abep-gaspath", "crates/abep-mission",
                 "crates/abep-subsystems", "crates/abep-config"):
        for q in sorted((ROOT / base).rglob("*")):
            if q.is_file() and "target" not in q.parts:
                srcs[q.relative_to(ROOT).as_posix()] = sha_file(q)
    rustc = subprocess.run(["/root/.cargo/bin/rustc", "--version"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "crates", "Cargo.toml", "Cargo.lock"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    return {"rustc": rustc, "rust_commit": git("rev-parse", "HEAD"), "git_dirty_crates": dirty or "none",
            "cargo_lock_sha256": sha_file(ROOT / "Cargo.lock"), "cargo_toml_sha256": sha_file(ROOT / "Cargo.toml"),
            "source_sha256": srcs}


def environment() -> dict:
    import scipy
    import pandas
    cpu = ""
    try:
        cpu = next(ln.split(":", 1)[1].strip() for ln in open("/proc/cpuinfo") if ln.startswith("model name"))
    except Exception:  # noqa: BLE001
        pass
    return {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
            "pandas": pandas.__version__, "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
            "cpu": cpu, "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")}}


def verdict_of(results: dict, keys, prefix: str, invariants_ok: bool) -> tuple[str, int]:
    fails = sum(v.get("failures", 0) for k, v in results.items() if k in keys or k.startswith(prefix))
    return ("PARITY_PASS" if fails == 0 and invariants_ok else "PARITY_FAIL"), fails


def capture(path: Path, name: str, obj) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(obj, sort_keys=True, default=str).encode()
    gz = gzip.compress(raw, mtime=0)
    (path / f"{name}.json.gz").write_bytes(gz)
    return {"file": f"{name}.json.gz", "sha256": hashlib.sha256(gz).hexdigest(), "json_sha256": hashlib.sha256(raw).hexdigest()}


def md_of(rep: dict) -> str:
    L = [f"# Parity report v1 - {rep['contract_id']}", "",
         f"Verdict: **{rep['verdict']}** ({rep['admission']}). Generated from `parity_report_v1.json`.", "",
         f"* Contract: `{rep['contract']}` sha256 `{rep['contract_sha256']}`, registered in `{rep['registered_in'][:12]}`.",
         f"* Python reference commit `{rep['python_commit'][:12]}`; Rust commit `{rep['build_provenance']['rust_commit'][:12]}` "
         f"(git_dirty: {rep['build_provenance']['git_dirty_crates']}); {rep['build_provenance']['rustc']}.",
         f"* Environment: Python {rep['environment']['python']}, numpy {rep['environment']['numpy']}, scipy "
         f"{rep['environment']['scipy']}, {rep['environment']['cpu']}.",
         f"* Scoring seed: {rep['scoring_master_seed']}; study grid: full ({rep['study_summary']}).", "",
         "## Results", "", "| entry | n | failures | float leaves | bit-identical | max ulp | Python raised | Rust raised |",
         "|---|---|---|---|---|---|---|---|"]
    for k, v in rep["results"].items():
        L.append(f"| {k} | {v.get('n', v.get('contexts', 1))} | {v.get('failures')} | {v.get('float_leaves', v.get('array_float_leaves'))} | "
                 f"{v.get('bit_identical', v.get('array_bit_identical'))} | {v.get('max_ulp', v.get('array_max_ulp'))} | "
                 f"{v.get('python_raised', '-')} | {v.get('rust_raised', '-')} |")
    L += ["", "## Invariants", ""]
    for k, v in rep["invariants"].items():
        L.append(f"* {k}: {v}")
    if rep.get("first_failures"):
        L += ["", "## First failures", ""] + [f"* {x}" for x in rep["first_failures"][:40]]
    L += ["", "## Performance (reported, never a criterion)", ""]
    for k, v in rep["performance"].items():
        L.append(f"* {k}: {v}")
    L += ["", "## Ledger update requested", ""] + [f"* {x}" for x in rep["ledger_update_requested"]]
    L += ["", "Parity is not physics validation, not a gate PASS and not a change of any frozen dataset.", ""]
    return "\n".join(L)


def write_reports(report, c7, c8, inp, out, f8, rs8, pars):
    results = report["results"]
    env, prov = environment(), provenance()
    inv = report["invariants"]
    inv7_ok = bool(inv["INV-F7-01 members feasible"])
    inv8_ok = (inv["INV-F8-01 gates unchanged"]["python"] and inv["INV-F8-01 gates unchanged"]["rust"]
               and inv["INV-F8-04 no representative"]["python"] and inv["INV-F8-04 no representative"]["rust"]
               and inv["INV-F8-02 robust set reported"]["python_n_members"] == inv["INV-F8-02 robust set reported"]["rust_n_members"])
    hist = {"execution": "scoring", "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": platform.node()}
    for c, cdir, keys, prefix, inv_ok, seed in ((c7, C7, F7_KEYS, "f7:", inv7_ok, SEEDS["f7"]["score"]),
                                                (c8, C8, F8_KEYS, "f8:", inv8_ok, SEEDS["f8"]["score"])):
        verdict, nf = verdict_of(results, keys, prefix, inv_ok)
        cpath = cdir / "parity_prereg_v1.json"
        res = {k: v for k, v in results.items() if k in keys or k.startswith(prefix)}
        first = [f"{k}: {x}" for k, v in res.items() for x in v.get("first_failures", [])]
        refdir = cdir / "reference_outputs"
        manifest = {}
        if cdir == C7:
            manifest["pareto_blocks"] = capture(refdir, "f7_pareto_blocks_v1",
                                                {f"{sc}|{fi}|{w}": pareto_list(par) for (sc, fi, w), par in pars.items()})
            manifest["contexts_index"] = capture(refdir, "f7_contexts_index_v1", json.loads((out / "contexts.json").read_text()))
        else:
            manifest["f8_study"] = capture(refdir, "f8_study_v1", {k: v for k, v in f8.items()})
            manifest["numpy_streams"] = capture(refdir, "numpy_streams_v1", numpy_stream_samples())
        (refdir / "MANIFEST.json").write_text(json.dumps({"captured_at_python_commit": git("rev-parse", "HEAD"),
                                                          "files": manifest}, indent=1) + "\n")
        led = ([f"{c['component']['inventory_id']}: partial_admissions += the registered function subset "
                f"(contract {c['id']}) -> {c['rust_implementation']['crate']}, status ADMITTED on PARITY_PASS; the "
                "module's other functions keep their recorded status"] if verdict == "PARITY_PASS" else
               [f"{c['component']['inventory_id']}: PARITY_FAILED under {c['id']} (stays PYTHON_REFERENCE; a code fix "
                "needs a new contract version with a fresh seed)"])
        if cdir == C7 and verdict == "PARITY_PASS":
            led.append("C-ABEP_SIM_PROGRAMME_DESIGN_SYNTHESIS_PY: partial admission of context_pareto (design part) and "
                       "the rank_full_system refusal stages under the same contract; evaluate_system / gate verdicts stay "
                       "with the assessment port (SC-WP-11)")
            led.append("C-ABEP_SIM_DESIGN_UPSTREAM_A9_13_PY: partial admission of require_all_admitted_scenarios and "
                       "robust_over_scenarios (SC-WP-10 elements) under the same contract")
        if cdir == C8 and verdict == "PARITY_PASS":
            led.append("NI / infrastructure: abep-rng registered numpy PCG64 / SeedSequence / Generator.standard_normal "
                       "stream (EXACT_STREAM, A9.29 sec. 7) admitted with this contract")
        rep = {"schema": "abep_rust_parity_report_v3_1", "contract_id": c["id"],
               "contract": cpath.relative_to(ROOT).as_posix(), "contract_sha256": sha_file(cpath),
               "registered_in": git("log", "--format=%H", "-1", "--", cpath.relative_to(ROOT).as_posix()),
               "python_commit": git("rev-parse", "HEAD"),
               "reference_sha256": {f["path"]: sha_file(ROOT / f["path"]) for f in c["reference_implementation"]["files"]},
               "build_provenance": prov, "environment": env, "scoring_master_seed": seed,
               "study_summary": f"{report['spec']}; picks {report['picks']}",
               "results": res, "invariants": inv, "first_failures": first,
               "verdict": verdict, "admission": "ADMITTED" if verdict == "PARITY_PASS" else "NOT_ADMITTED",
               "failures": nf, "decomposition_rust": report.get("decomposition_rust"),
               "performance": {"rust_study_wall_s": report["rust_study"].get("wall_s"),
                               "rust_f7_s": report["rust_study"].get("value", {}).get("t_f7_s"),
                               "rust_f8_s": report["rust_study"].get("value", {}).get("t_f8_s"),
                               "python_f7_cpu_s": report["python_study"]["t_f7_cpu_s"],
                               "python_f8_cpu_s": report["python_study"]["t_f8_cpu_s"]},
               "reference_outputs": manifest,
               "campaign_history": [hist], "ledger_update_requested": led}
        (cdir / "parity_report_v1.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
        (cdir / "parity_report_v1.md").write_text(md_of(rep))
        print(c["id"], verdict, nf)


def numpy_stream_samples() -> dict:
    """Captured numpy 2.4.4 stream samples for the CI replay (registered seeds of the study + edge seeds)."""
    out = []
    seeds = [0, 1, 12345, ro.SEED_BASE, 2 ** 31 - 2, 2 ** 64 + 7, 2 ** 128 - 1, 2 ** 160 + 12345] + \
        [ro.stable_seed("tpmc", c, sc) for c in ("A0.25_Ld3_phi0.8", "A1.5_Ld20_phi0.9") for sc in ("maxwell_a0", "cll_a1")]
    for sd in seeds:
        ss = np.random.SeedSequence(sd)
        z = np.random.default_rng(sd).standard_normal(4096)
        out.append({"seed": str(sd), "pool": [int(x) for x in ss.pool],
                    "next_uint64": [str(int(x)) for x in np.random.PCG64(np.random.SeedSequence(sd)).random_raw(8)],
                    "normal_sha256": hashlib.sha256(z.astype("<f8").tobytes()).hexdigest(),
                    "normal_head": [float(x) for x in z[:8]], "n_normal": 4096})
    return {"numpy": np.__version__, "streams": out}


# =============================================================================================== B2-OF-01 acceptance
CD = ROOT / "docs/rust_migration/contracts/DIAG-B2-OF-01-INTERP-SENSITIVITY"


def accept(chain_file: Path):
    """The one scored execution of ACCEPT-DIAG-B2-OF-01-INTERP-SENSITIVITY-V1: the Rust acceptance tests, the Rust
    records of every registered point, an independent Python classification from the frozen CSV grid (exact float
    equality) and the survey comparison, and the F7 / F8 chain application of the full study."""
    pre = CD / "acceptance_prereg_v1.json"
    if (CD / "acceptance_report_v1.json").exists():
        raise SystemExit("REFUSED: acceptance_report_v1.json exists (scored once)")
    reg = json.loads(pre.read_text())
    env = dict(os.environ, PATH=f"/root/.cargo/bin:{os.environ.get('PATH', '')}", CARGO_INCREMENTAL="0",
               CARGO_PROFILE_DEV_DEBUG="0")
    t = subprocess.run(["cargo", "test", "--locked", "-p", "abep-uq", "--test", "interp_sensitivity", "--",
                        "--test-threads=1"], cwd=ROOT, env=env, capture_output=True, text=True)
    lines = [ln for ln in t.stdout.splitlines() if ln.startswith("test ")]
    tests = {ln.split()[1]: ln.split()[-1] for ln in lines}
    import pandas as pd
    df = pd.read_csv(ROOT / "abep_sim/data/intake_surface_v1.csv")
    axes = ["L_over_d", "phi", "alpha", "theta_deg"]
    survey = json.loads((ROOT / "docs/rust_migration/contracts/C-ABEP_SIM_INTAKE_TPMC_PY/finding_B2-OF-01_face_survey_v1.json").read_text())
    faces = []
    for f in survey["affected_faces"]:
        a, v = f.split(" = ")
        faces.append((a, float(v)))

    def py_class(table, p):
        d = df[df.scattering == table]
        grid = {a: sorted(float(x) for x in d[a].unique()) for a in axes}
        if not all(math.isfinite(x) and grid[a][0] <= x <= grid[a][-1] for a, x in zip(axes, p)):
            return "OUT_OF_DOMAIN"
        hit = [f for f in faces if p[axes.index(f[0])] == f[1]]
        if not hit:
            return "NOT_ON_KNOWN_FACE"
        free = sum(1 for a, x in zip(axes, p) if x not in grid[a])
        return {0: "GRID_NODE", 1: "GRID_EDGE"}.get(free, "FACE_INTERIOR")
    pts = []
    for case in reg["acceptance_cases"]:
        for key in ("point", "points"):
            if key in case and isinstance(case[key], list):
                plist = [case[key]] if key == "point" else case[key]
                for p in plist:
                    for tb in case.get("tables", ["maxwell", "cll"]):
                        pts.append((case["id"], tb, [math.nan if x == "NaN" else float(x) for x in p]))
        for c in case.get("cases", []):
            pts.append((case["id"], c["table"], c["point"]))
    calls = [{"entry": "interp_sensitivity", "args": {"table": tb, "point": jsonable(p)}} for _, tb, p in pts]
    rs = rust_eval(calls, "accept")
    checks = []
    for (cid, tb, p), r in zip(pts, rs):
        rec = r.get("value", {})
        pc = py_class(tb, p)
        checks.append({"case": cid, "table": tb, "point": jsonable(p), "rust_face_geometry": rec.get("face_geometry"),
                       "python_face_geometry": pc, "agree": rec.get("face_geometry") == pc,
                       "status": rec.get("status"), "sensitivity_class": rec.get("sensitivity_class"),
                       "max_relative_spread": (rec.get("envelope") or {}).get("max_relative_spread")})
    survey_cmp = []
    for field, m in survey["max_relative_spread_per_field"].items():
        r = rust_eval([{"entry": "interp_sensitivity", "args": {"table": m["scattering"], "point": m["point"]}}],
                      f"accept_{field}")[0]["value"]
        sp = r["envelope"]["species"][m["species"]][field]["relative_spread"]
        survey_cmp.append({"field": field, "table": m["scattering"], "species": m["species"], "survey": m["spread"],
                           "rust": sp, "abs_diff": abs(sp - m["spread"]), "within_1e-12": abs(sp - m["spread"]) <= 1e-12})
    chain = json.loads(chain_file.read_text())
    chain_summary = {k: chain[k] for k in ("interpolant_used_by_chain", "face_geometry_counts", "n_points",
                                           "n_non_conforming")}
    at08 = (chain["interpolant_used_by_chain"] is False and chain["n_non_conforming"] == 0
            and set(chain["face_geometry_counts"]) <= {"GRID_NODE", "NOT_ON_KNOWN_FACE"})
    ok = (t.returncode == 0 and all(v == "ok" for v in tests.values()) and all(c["agree"] for c in checks)
          and all(c["within_1e-12"] for c in survey_cmp) and at08)
    rep = {"schema": "abep_new_diagnostic_acceptance_report_v1", "id": reg["id"],
           "prereg": pre.relative_to(ROOT).as_posix(), "prereg_sha256": sha_file(pre),
           "registered_in": git("log", "--format=%H", "-1", "--", pre.relative_to(ROOT).as_posix()),
           "rust_commit": git("rev-parse", "HEAD"), "environment": environment(),
           "cargo_test": {"command": "cargo test --locked -p abep-uq --test interp_sensitivity", "exit": t.returncode,
                          "tests": tests},
           "registered_points": checks, "survey_maxima": survey_cmp,
           "f7_f8_chain_application": dict(chain_summary, at08_prediction_holds=at08,
                                           source="the full-grid study of the SC-WP-10 scoring execution"),
           "verdict": "ACCEPTED" if ok else "NOT_ACCEPTED",
           "meaning": reg["decision_rules"]["meaning"],
           "ledger_update_requested": [
               "new item DIAG-B2-OF-01 (NUMERICAL_INTERPOLATION_SENSITIVITY diagnostic, abep_uq::interp_sensitivity): "
               + ("ACCEPTED (software verification, not physics)" if ok else "NOT_ACCEPTED"),
               "abep-intake: additive public accessors IntakeSurface::{species_rows_at, containing_simplex_rows} "
               "(admitted interpolation unchanged; C-ABEP_SIM_INTAKE_TPMC_PY admission unaffected)"]}
    (CD / "acceptance_report_v1.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    md = [f"# Acceptance report v1 - {reg['id']}", "", f"Verdict: **{rep['verdict']}**.", "",
          f"* Preregistration `{rep['prereg']}` sha256 `{rep['prereg_sha256']}`, committed in `{rep['registered_in'][:12]}` "
          "before any diagnostic code.", f"* Rust commit `{rep['rust_commit'][:12]}`.",
          f"* cargo test: exit {t.returncode}; " + ", ".join(f"{k} {v}" for k, v in tests.items()), "",
          "## Registered points (Rust classification vs an independent Python classification from the frozen CSV)", "",
          "| case | table | point | Rust | Python | status | class | max spread |", "|---|---|---|---|---|---|---|---|"]
    for c in checks:
        md.append(f"| {c['case']} | {c['table']} | {c['point']} | {c['rust_face_geometry']} | {c['python_face_geometry']} | "
                  f"{c['status']} | {c['sensitivity_class']} | {c['max_relative_spread']} |")
    md += ["", "## Survey maxima (finding B2-OF-01)", "", "| field | table | species | survey | Rust | abs diff |",
           "|---|---|---|---|---|---|"]
    for c in survey_cmp:
        md.append(f"| {c['field']} | {c['table']} | {c['species']} | {c['survey']} | {c['rust']} | {c['abs_diff']:.2e} |")
    md += ["", "## F7 / F8 chain application (AT-08)", "", f"* {chain_summary}", f"* prediction holds: {at08}", "",
           "Software verification of a numerical diagnostic, not physics validation, not a change of the frozen "
           "surface and not a gate PASS.", ""]
    (CD / "acceptance_report_v1.md").write_text("\n".join(md))
    print("ACCEPTANCE", rep["verdict"])


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "accept":
        accept(Path(sys.argv[2]))
        raise SystemExit(0)
    if len(sys.argv) != 2 or sys.argv[1] not in ("dev", "score"):
        raise SystemExit(__doc__)
    run(sys.argv[1])

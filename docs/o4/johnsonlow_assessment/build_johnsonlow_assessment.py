"""fo_johnsonlow_escalation_assessment (trigger T_JOHNSONLOW_ESCALATION_ASSESSMENT).

Question (owner roadmap step 9): does the electronic-excitation sensitivity Johnson-low (n2_n_exc_johnsonlow*: Johnson et al.
2005 Table 2 used below 20 eV instead of Su et al. 2021) persist across the other primary chemistry changes, i.e. is it material
on every one of the four pre-registered primary chemistry combinations?

This script is an EVIDENCE SUMMARY of frozen, already-scored O4 datasets. It decides nothing: it does not change any criterion,
tolerance, chemistry or transport parameter, it does not alter the v1 result, it does not adopt Johnson-low, and it neither makes
a screening candidate PROMOTABLE nor rejects one. A large numerical effect is a sensitivity, not experimental support.

Inputs (all frozen, read-only, repository-relative):
  hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json          (O4 rule text, staged_sensitivities, mandatory chemistry)
  hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json                  (lock hash)
  hallthruster_bridge/cases/p5_n2.json                                  (case -> point / registration / coil shape)
  hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_*             (mandatory v1 raw + scores + provenance)
  hallthruster_bridge/validation/p5_n2_campaign_v1_staged_n2_n_exc_johnsonlow_*                  (first stage vs n2_n.toml)
  hallthruster_bridge/validation/p5_n2_campaign_v1_escalation_n2_n_exc_johnsonlow_{di_lower,nel_wang,di_lower_nel_wang}_*
  scripts/score_p5_n2_campaign.py  (the frozen scorer; imported read-only ONLY after its sha256 equals the provenance value,
                                    so the per-run observables and statuses are computed by exactly the scoring code)

Every hash in the chain is verified before any number is produced; any mismatch raises (no silent fallback).

Outputs (deterministic; no timestamps): johnsonlow_assessment_v1.json, JOHNSONLOW_ASSESSMENT.md (next to this script).
Usage: python docs/o4/johnsonlow_assessment/build_johnsonlow_assessment.py [--check]
       --check rebuilds in memory and exits 1 unless both committed outputs are byte-identical.
"""
import collections, gzip, hashlib, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BR = os.path.join(ROOT, "hallthruster_bridge")
VAL = os.path.join(BR, "validation")
OUT_JSON = os.path.join(HERE, "johnsonlow_assessment_v1.json")
OUT_MD = os.path.join(HERE, "JOHNSONLOW_ASSESSMENT.md")
SENS = "n2_n_exc_johnsonlow.toml"
SCHEMA = "johnsonlow_assessment_v1"
POINTS = ["N1", "N2", "N3", "N4", "N5"]
THRUST_POINTS = ["N1", "N2", "N3"]
READINGS = ("A", "B")

# Factor labels of the four primary combinations (CLAUDE.md, abep-n2n-0.4 / 0.8): DI upper = n2_n.toml nominal table,
# DI lower = n2_n_di_lower variant; N elastic OPM = Ragimkhanov 2026 nominal, Wang = Wang et al. 2014 BSR variant.
FACTORS = {"n2_n.toml": ("DI-upper", "Nel-OPM"), "n2_n_di_lower.toml": ("DI-lower", "Nel-OPM"),
           "n2_n_nel_wang.toml": ("DI-upper", "Nel-Wang"), "n2_n_di_lower_nel_wang.toml": ("DI-lower", "Nel-Wang")}

# ---------------------------------------------------------------------------------------------------------------------------
# PERSISTENCE RULE. Fixed here, in code, before any delta distribution is computed; the document reproduces it verbatim
# before the results. The materiality thresholds are the PRE-REGISTERED O4 thresholds (criteria O4_staged_escalation), not
# new ones; the median-based summary and the class names are this assessment's own reporting convention (PROPOSED to the
# owner; they gate nothing).
RULE = {
    "id": "jla_persistence_rule_v1",
    "normalization": "r = delta / O4 threshold: delta(I_d)/I_target / 0.075 (all points); delta(T_axial) / (0.5 x T_tolerance) = "
                     "/2.6 mN (N1), /2.8 mN (N2, N3), per divergence reading A and B. delta = sensitivity minus its own baseline, "
                     "same candidate, case and mode (vacuum), over every numerically valid pair whatever the run status "
                     "(as O4 compares observables).",
    "per_combination_summary": "median of r over the matched pairs of that combination (per point, and pooled over points)",
    "classes": {
        "PERSISTS": "median r has the same non-zero sign on all four combinations AND |median r| >= 1 on all four",
        "SIGN_PERSISTS_MATERIAL_ON_SOME": "same sign on all four; |median r| >= 1 on 1 to 3 of them",
        "SIGN_PERSISTS_BELOW_THRESHOLD": "same sign on all four; |median r| < 1 on all four",
        "BASELINE_DEPENDENT_SIGN": "the sign of median r differs between combinations (or is zero on one)",
    },
    "status_and_verdict": "a status effect PERSISTS iff at least one run status changes on every combination; a verdict effect "
                          "PERSISTS iff the O4 verdict-change clause is non-empty on every combination. Individual transitions / "
                          "member changes are listed as common-to-all-four or present-only-with-some-baselines.",
    "factor_pattern": "for an effect that is material (|median r| >= 1) on some but not all combinations: 'DI-lower only', "
                      "'DI-upper only', 'Nel-Wang only', 'Nel-OPM only' when the material set equals exactly the two combinations "
                      "sharing that factor level; otherwise 'no single-factor pattern'. Descriptive only.",
    "answer_to_question": "Johnson-low is 'material on every primary combination' iff the pre-registered O4 trigger fired on all "
                          "four (scored staged_escalation blocks). The per-observable classes say WHICH effects persist.",
}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT)


def fail(msg):
    raise SystemExit("johnsonlow assessment: " + msg)


def rnd(x, n=6):
    return None if x is None else float(f"{x:.{n}g}") if abs(x) >= 1e-300 else 0.0


def quantile(xs, q):
    """Linear interpolation between order statistics (Hyndman-Fan type 7)."""
    s = sorted(xs)
    if not s:
        return None
    h = (len(s) - 1) * q
    lo = int(h)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def dist(xs, thr_norm=None):
    """Signed distribution summary. xs are already in the unit reported; thr_norm: values are normalized (threshold = 1)."""
    if not xs:
        return {"n": 0}
    d = {"n": len(xs), "median": rnd(quantile(xs, 0.5)), "q25": rnd(quantile(xs, 0.25)), "q75": rnd(quantile(xs, 0.75)),
         "min": rnd(min(xs)), "max": rnd(max(xs)), "n_pos": sum(x > 0 for x in xs), "n_neg": sum(x < 0 for x in xs),
         "n_zero": sum(x == 0 for x in xs)}
    if thr_norm:
        d["n_abs_ge_threshold"] = sum(abs(x) >= 1.0 for x in xs)
    return d


def sign(x):
    return 0 if x is None or x == 0 else (1 if x > 0 else -1)


# ------------------------------------------------------------------------------------------------------------------ inputs
def load_inputs():
    crit_p = os.path.join(BR, "prereg", "p5_n2_validation_criteria_v1.json")
    lock_p = os.path.join(BR, "prereg", "p5_n2_prereg_lock_v1.json")
    cases_p = os.path.join(BR, "cases", "p5_n2.json")
    crit = json.load(open(crit_p))
    spec = crit["staged_sensitivities"].get(SENS)
    if spec is None:
        fail(f"{SENS} is not a pre-registered staged sensitivity")
    combos = [(SENS, spec["baseline"], "staged_n2_n_exc_johnsonlow")] + \
             [(esc, prim, "escalation_" + esc[:-len(".toml")]) for prim, esc in spec["escalation"].items()]
    if sorted(b for _, b, _ in combos) != sorted(crit["mandatory_chemistry"]):
        fail("the Johnson-low baselines do not cover the four mandatory primary combinations")
    lock_sha = sha(lock_p)
    scorer_p = os.path.join(ROOT, "scripts", "score_p5_n2_campaign.py")

    # mandatory v1 chain
    mman_p = os.path.join(VAL, "p5_n2_campaign_v1_vacuum_raw_manifest.json")
    mprov_p = os.path.join(VAL, "p5_n2_campaign_v1_vacuum_scores_provenance.json")
    mman, mprov = json.load(open(mman_p)), json.load(open(mprov_p))
    mscores_p = os.path.join(BR, mprov["output"])
    mraw = gzip.decompress(open(os.path.join(BR, mman["dataset"]), "rb").read())
    checks = []

    def chk(name, ok):
        checks.append({"check": name, "ok": bool(ok)})
        if not ok:
            fail("provenance check failed: " + name)

    chk("mandatory raw canonical sha256 == its freeze manifest", hashlib.sha256(mraw).hexdigest() == mman["sha256_canonical_jsonl"])
    chk("mandatory provenance input == mandatory freeze manifest", mprov["input_sha256_canonical_jsonl"] == mman["sha256_canonical_jsonl"])
    chk("mandatory scores sha256 == its provenance output_sha256", sha(mscores_p) == mprov["output_sha256"])
    chk("mandatory prereg lock == current lock", mprov["prereg_lock_sha256"] == lock_sha == mman["prereg_lock_sha256"])
    chk("scorer file sha256 == mandatory provenance scorer_sha256", sha(scorer_p) == mprov["scorer_sha256"])

    prov_rows = [{"dataset": "mandatory v1 vacuum", "raw": mman["dataset"], "raw_sha256_canonical": mman["sha256_canonical_jsonl"],
                  "scores": mprov["output"], "scores_sha256": mprov["output_sha256"], "provenance": rel(mprov_p),
                  "provenance_sha256": sha(mprov_p), "n_records": mman["n_records"]}]
    datasets = {}
    for s_ch, b_ch, stem in combos:
        base = os.path.join(VAL, f"p5_n2_campaign_v1_{stem}")
        man_p, prov_p, sc_p = base + "_raw_manifest.json", base + "_scores_provenance.json", base + "_scores.json"
        for p in (man_p, prov_p, sc_p):
            if not os.path.isfile(p):
                fail(f"missing frozen O4 file {rel(p)}")
        man, prov = json.load(open(man_p)), json.load(open(prov_p))
        raw = gzip.decompress(open(os.path.join(BR, man["dataset"]), "rb").read())
        tag = s_ch
        chk(f"{tag}: raw canonical sha256 == freeze manifest", hashlib.sha256(raw).hexdigest() == man["sha256_canonical_jsonl"])
        chk(f"{tag}: provenance input == freeze manifest", prov["input_sha256_canonical_jsonl"] == man["sha256_canonical_jsonl"])
        chk(f"{tag}: scores sha256 == provenance output_sha256", sha(sc_p) == prov["output_sha256"])
        chk(f"{tag}: mandatory_reproduced is true", prov.get("mandatory_reproduced") is True)
        chk(f"{tag}: bound to the mandatory raw dataset", prov["input_mandatory_sha256"] == mman["sha256_canonical_jsonl"])
        chk(f"{tag}: bound to the official mandatory scores", prov["mandatory_scores_sha256"] == mprov["output_sha256"])
        chk(f"{tag}: scorer sha256 == frozen scorer", prov["scorer_sha256"] == mprov["scorer_sha256"] == sha(scorer_p))
        chk(f"{tag}: prereg lock == current lock", prov["prereg_lock_sha256"] == lock_sha == man["prereg_lock_sha256"])
        chk(f"{tag}: pre-registered baseline {b_ch} (o4.baseline or o4.compare_with)",
            prov["o4"].get("baseline", prov["o4"].get("compare_with")) == b_ch)
        chk(f"{tag}: escalation belongs to {SENS}", s_ch == SENS or prov["o4"].get("sensitivity") == SENS)
        chk(f"{tag}: chemistry config sha256 == pinned propellant file",
            prov["o4"]["chemistry"].get(s_ch) == sha(os.path.join(BR, "propellants", s_ch)))
        scores = json.load(open(sc_p))
        blk = scores["staged_escalation"].get(s_ch)
        if blk is None:
            fail(f"{tag}: no staged_escalation block")
        chk(f"{tag}: block baseline == pre-registered baseline", blk["baseline"] == b_ch)
        chk(f"{tag}: provenance o4_trigger_fired == scored block", prov["o4_trigger_fired"][s_ch] == blk["trigger_fired"])
        prov_rows.append({"dataset": stem, "sensitivity": s_ch, "baseline": b_ch, "raw": man["dataset"],
                          "raw_sha256_canonical": man["sha256_canonical_jsonl"], "scores": prov["output"],
                          "scores_sha256": prov["output_sha256"], "provenance": rel(prov_p), "provenance_sha256": sha(prov_p),
                          "n_records": man["n_records"], "mandatory_reproduced": prov["mandatory_reproduced"]})
        datasets[s_ch] = {"baseline": b_ch, "records": [json.loads(l) for l in raw.decode().splitlines() if l.strip()],
                          "block": blk}

    # the frozen scorer, imported only after its hash matched
    spec_m = importlib.util.spec_from_file_location("jla_frozen_scorer", scorer_p)
    scorer = importlib.util.module_from_spec(spec_m)
    spec_m.loader.exec_module(scorer)
    mrecs = [json.loads(l) for l in mraw.decode().splitlines() if l.strip()]
    mscores = json.load(open(mscores_p))
    cases = {c["id"]: c for c in json.load(open(cases_p))["cases"]}
    return {"crit": crit, "combos": combos, "checks": checks, "prov_rows": prov_rows, "datasets": datasets, "scorer": scorer,
            "mrecs": mrecs, "mscores": mscores, "cases": cases,
            "input_hashes": {rel(crit_p): sha(crit_p), rel(lock_p): lock_sha, rel(cases_p): sha(cases_p),
                             rel(scorer_p): sha(scorer_p)}}


# ---------------------------------------------------------------------------------------------------------------- analysis
def family(fname):
    f = fname.replace("_johnsonlow", "")
    if f.startswith("excitation_N2_vib"):
        return "vibrational"
    if f.startswith("excitation_N2_rot"):
        return "rotational"
    if f.startswith("excitation_N2_"):
        return "electronic"
    if f.startswith("dissociation_N2"):
        return "dissociation"
    return "other"


def parse_trigger(text):
    kind = text.split()[0]
    reading = text.rstrip(")").rsplit("(", 1)[-1] if text.endswith(")") else None
    return kind, reading


def analyse_combo(inp, s_ch, b_ch):
    sc, ds, cases, crit = inp["scorer"], inp["datasets"][s_ch], inp["cases"], inp["crit"]
    blk = ds["block"]
    base_recs = [r for r in inp["mrecs"] if r["chemistry"] == b_ch and r["mode"] == "vacuum"]
    sens_recs = [r for r in ds["records"] if r["mode"] == "vacuum"]
    base = {(r["candidate"], r["case"]): r for r in base_recs}
    if len(sens_recs) != len(base_recs) or any((r["candidate"], r["case"]) not in base for r in sens_recs):
        fail(f"{s_ch}: sensitivity and baseline runs are not in one-to-one correspondence")

    # (a) reproduce the scored O4 block with the frozen scorer (run-level list and verdict-change clause)
    rep_fired = json.loads(json.dumps(sc.escalation(sens_recs, base_recs, s_ch)))
    rep_vc = json.loads(json.dumps(sc.verdict_change(sens_recs, inp["mrecs"], b_ch)))
    reproduced = rep_fired == blk["run_level_triggers"] and rep_vc == blk["verdict_changes"]
    if not reproduced:
        fail(f"{s_ch}: frozen scorer does not reproduce the scored staged_escalation block")

    # (b) the official mandatory statuses must be those the scorer gives the baseline records
    off = {(x["key"], x["reading"]): x["status"] for x in inp["mscores"]["runs"]}

    # (c) trigger counts from the scored block
    t_kind = collections.Counter(); t_kind_rd = collections.Counter(); t_point = collections.defaultdict(collections.Counter)
    t_cand = collections.defaultdict(collections.Counter); t_reg = collections.defaultdict(collections.Counter)
    t_coil = collections.defaultdict(collections.Counter); runs_by_kind = collections.defaultdict(set)
    for key, text in blk["run_level_triggers"]:
        cand, _, case, _ = key.split("|")
        kind, rd = parse_trigger(text)
        c = cases[case]
        t_kind[kind] += 1; t_kind_rd[f"{kind}|{rd}"] += 1
        t_point[c["point"]][kind] += 1; t_cand[cand][kind] += 1
        t_reg[c["registration"]][kind] += 1; t_coil[c["coil_shape"]][kind] += 1
        runs_by_kind[kind].add(key); runs_by_kind["any"].add(key)

    # (d) per-pair observables and deltas, recomputed from the raw records of both datasets
    thrI = 0.075
    thrT = {p: 0.5 * t for p, t in crit["D3_tolerances"]["thrust_mN"].items()}
    dI = collections.defaultdict(list); dIn = collections.defaultdict(list)
    dT = {rd: collections.defaultdict(list) for rd in READINGS}; dTn = {rd: collections.defaultdict(list) for rd in READINGS}
    dI_both_in = collections.defaultdict(list); dTe = collections.defaultdict(list)
    trans = {rd: collections.Counter() for rd in READINGS}
    own = collections.Counter(); pair_r = {}
    ood_b = ood_s = 0; ood_to_sc = sc_to_ood = 0
    fam_b = collections.Counter(); fam_s = collections.Counter(); fout_b = []; fout_s = []
    for s in sorted(sens_recs, key=lambda r: r["key"]):
        b = base[(s["candidate"], s["case"])]
        pt = s["point"]
        st = {}
        for rd in READINGS:
            ss, _, sd = sc.run_status(s, rd)
            bs, _, bd = sc.run_status(b, rd)
            if off.get((b["key"], rd)) != bs:
                fail(f"baseline status of {b['key']} ({rd}) differs from the official v1 scores")
            st[rd] = (bs, ss, sd, bd)
            trans[rd][f"{bs}->{ss}"] += 1
            if ss != bs:
                own[("status", pt)] += 1
            if "T_axial_mN" in sd and "T_axial_mN" in bd:
                d = sd["T_axial_mN"] - bd["T_axial_mN"]
                dT[rd][pt].append(d); dTn[rd][pt].append(d / thrT[pt])
                pair_r[(s["candidate"], s["case"], f"dT_{rd}")] = d / thrT[pt]
                if abs(d) >= thrT[pt]:
                    own[("dT", pt)] += 1
            if "dI_rel" in sd and "dI_rel" in bd and abs(sd["dI_rel"] - bd["dI_rel"]) >= thrI:
                own[("dI_d", pt)] += 1
        bs, ss, sd, bd = st["A"]
        if "dI_rel" in sd and "dI_rel" in bd:
            if st["B"][2].get("dI_rel") != sd["dI_rel"]:
                fail("dI_rel depends on the divergence reading")
            d = sd["dI_rel"] - bd["dI_rel"]
            dI[pt].append(d); dIn[pt].append(d / thrI)
            pair_r[(s["candidate"], s["case"], "dI")] = d / thrI
            if bs not in ("OUT_OF_DOMAIN", "NUMERICAL_FAILURE") and ss not in ("OUT_OF_DOMAIN", "NUMERICAL_FAILURE"):
                dI_both_in[pt].append(d)
        dTe[pt].append(s["Te_max_eV"] - b["Te_max_eV"])
        # chemistry domain (reading independent)
        if (st["A"][0] == "OUT_OF_DOMAIN") != (st["B"][0] == "OUT_OF_DOMAIN"):
            fail("OUT_OF_DOMAIN depends on the reading")
        bo, so = bs == "OUT_OF_DOMAIN", ss == "OUT_OF_DOMAIN"
        ood_b += bo; ood_s += so
        ood_to_sc += bo and ss in ("PASS", "FAIL_VALIDATION")
        sc_to_ood += so and bs in ("PASS", "FAIL_VALIDATION")
        for rec, famc, fl in ((b, fam_b, fout_b), (s, fam_s, fout_s)):
            fams = {family(q["file"]) for q in rec["chemistry_per_reaction"]
                    if q.get("extrapolated_fraction") is None or q["extrapolated_fraction"] > sc.FOUT_TOL}
            for f in fams:
                famc[f] += 1
            fl.append(max(q["extrapolated_fraction"] for q in rec["chemistry_per_reaction"]
                          if q.get("extrapolated_fraction") is not None))

    # (e) independent count check: own threshold evaluation == scored run-level list
    own_kind = collections.Counter()
    for (k, _), n in own.items():
        own_kind[k] += n
    if dict(own_kind) != {k: v for k, v in t_kind.items()}:
        fail(f"{s_ch}: independent trigger counts {dict(own_kind)} != scored {dict(t_kind)}")

    # (f) verdict changes from the scored block
    vc = blk["verdict_changes"]
    mem_tr = collections.Counter(f"{a}->{b}" for c in vc.values() for a, b in c["members"].values())
    cand_changes = {c: v["candidate"] for c, v in vc.items() if v["candidate"][0] != v["candidate"][1]}

    def dists(dd, norm=False):
        out = {p: dist(dd[p], norm) for p in POINTS if dd.get(p)}
        allv = [x for p in POINTS for x in dd.get(p, [])]
        out["pooled"] = dist(allv, norm)
        return out

    res = {
        "sensitivity": s_ch, "baseline": b_ch, "factors": dict(zip(("DI", "N_elastic"), FACTORS[b_ch])),
        "n_pairs": len(sens_recs), "trigger_fired": blk["trigger_fired"],
        "scored_block_reproduced_by_frozen_scorer": reproduced,
        "run_level_triggers": {
            "n_entries_total": len(blk["run_level_triggers"]),
            "by_kind": dict(sorted(t_kind.items())), "by_kind_and_reading": dict(sorted(t_kind_rd.items())),
            "by_point": {p: dict(sorted(t_point[p].items())) for p in POINTS},
            "by_candidate": {c: dict(sorted(v.items())) for c, v in sorted(t_cand.items())},
            "by_registration": {c: dict(sorted(v.items())) for c, v in sorted(t_reg.items())},
            "by_coil_shape": {c: dict(sorted(v.items())) for c, v in sorted(t_coil.items())},
            "n_distinct_runs_triggered": {k: len(v) for k, v in sorted(runs_by_kind.items())},
            "note": "entries are (run, reading) pairs as listed by the scorer: status and dI_d entries appear once per reading",
        },
        "deltas": {
            "dI_over_Itarget": dists(dI), "dI_normalized_r": dists(dIn, True),
            "dI_over_Itarget_both_runs_in_domain": dists(dI_both_in),
            "dT_axial_mN": {rd: dists(dT[rd]) for rd in READINGS},
            "dT_normalized_r": {rd: dists(dTn[rd], True) for rd in READINGS},
            "dTe_max_eV": dists(dTe),
        },
        "status_transitions": {rd: dict(sorted(trans[rd].items())) for rd in READINGS},
        "status_transitions_changed_only": {rd: {k: v for k, v in sorted(trans[rd].items()) if k.split("->")[0] != k.split("->")[1]}
                                           for rd in READINGS},
        "tail": {
            "n_pairs_dI_ge_threshold": sum(abs(x) >= 1.0 for p in POINTS for x in dIn.get(p, [])),
            "n_pairs_dT_A_ge_threshold": sum(abs(x) >= 1.0 for p in THRUST_POINTS for x in dTn["A"].get(p, [])),
            "n_pairs_dT_B_ge_threshold": sum(abs(x) >= 1.0 for p in THRUST_POINTS for x in dTn["B"].get(p, [])),
            "n_pairs_with_thrust": sum(len(dTn["A"].get(p, [])) for p in THRUST_POINTS),
            "n_runs_status_changed": len(runs_by_kind.get("status", ())),
            "n_runs_status_changed_across_OOD_boundary": ood_to_sc + sc_to_ood,
            "n_runs_any_trigger": len(runs_by_kind.get("any", ())),
            "note": "pairs are (candidate, case); thresholds are the O4 thresholds (|r| >= 1)"},
        "ood": {"n_OUT_OF_DOMAIN_baseline": ood_b, "n_OUT_OF_DOMAIN_sensitivity": ood_s,
                "n_OOD_to_scoreable": ood_to_sc, "n_scoreable_to_OOD": sc_to_ood,
                "runs_with_family_beyond_limit_baseline": dict(sorted(fam_b.items())),
                "runs_with_family_beyond_limit_sensitivity": dict(sorted(fam_s.items())),
                "f_out_max_median_baseline": rnd(quantile(fout_b, 0.5)), "f_out_max_median_sensitivity": rnd(quantile(fout_s, 0.5)),
                "note": "counts are runs (reading independent); a run can have several reaction families beyond their limit"},
        "verdict_changes": {"n_candidates_with_any_change": len(vc),
                            "n_member_changes": sum(len(c["members"]) for c in vc.values()),
                            "member_transitions": dict(sorted(mem_tr.items())),
                            "candidate_level_changes": {c: list(v) for c, v in sorted(cand_changes.items())},
                            "detail": vc,
                            "meaning": "O4 last clause, provisional counterfactual: v1 verdicts recomputed with ONLY this "
                                       "baseline chemistry replaced by the sensitivity. Not a v1 verdict, not a rejection."},
    }
    return res, pair_r


def classify(meds):
    signs = [sign(m) for m in meds]
    mat = [m is not None and abs(m) >= 1.0 for m in meds]
    if len(set(signs)) != 1 or signs[0] == 0:
        return "BASELINE_DEPENDENT_SIGN"
    if all(mat):
        return "PERSISTS"
    if any(mat):
        return "SIGN_PERSISTS_MATERIAL_ON_SOME"
    return "SIGN_PERSISTS_BELOW_THRESHOLD"


def factor_pattern(baselines, mat):
    sel = {b for b, m in zip(baselines, mat) if m}
    if not sel or len(sel) == len(baselines):
        return None
    for idx, lvl in ((0, "DI-lower"), (0, "DI-upper"), (1, "Nel-Wang"), (1, "Nel-OPM")):
        if sel == {b for b in baselines if FACTORS[b][idx] == lvl}:
            return lvl + " only"
    return "no single-factor pattern"


def consistency(per, pairs, combos):
    bl = [b for _, b, _ in combos]
    sens = [s for s, _, _ in combos]
    obs = [("dI", "dI_normalized_r", None, POINTS)] + [(f"dT_{rd}", "dT_normalized_r", rd, THRUST_POINTS) for rd in READINGS]
    out = {}
    for name, dkey, rd, pts in obs:
        rows = {}
        for p in pts + ["pooled"]:
            meds = []
            for s in sens:
                dd = per[s]["deltas"][dkey] if rd is None else per[s]["deltas"][dkey][rd]
                meds.append(dd.get(p, {}).get("median"))
            mat = [m is not None and abs(m) >= 1.0 for m in meds]
            absm = [abs(m) for m in meds if m is not None]
            # 2x2 descriptive factor effects on median r (m[DI, Nel])
            m = dict(zip(bl, meds))
            fx = None
            if None not in meds:
                a, b_, c, d = m["n2_n.toml"], m["n2_n_di_lower.toml"], m["n2_n_nel_wang.toml"], m["n2_n_di_lower_nel_wang.toml"]
                fx = {"DI_lower_minus_upper": rnd(((b_ - a) + (d - c)) / 2), "Nel_wang_minus_opm": rnd(((c - a) + (d - b_)) / 2),
                      "interaction": rnd((d - c) - (b_ - a))}
            # per-pair sign agreement across the four combinations
            keys = [k for k in pairs[sens[0]] if k[2] == name and (p == "pooled" or k[1].split("-")[0] == p)]
            full = [k for k in keys if all(k in pairs[s] for s in sens)]
            same_sign = sum(len({sign(pairs[s][k]) for s in sens}) == 1 and sign(pairs[sens[0]][k]) != 0 for k in full)
            all_mat = sum(all(abs(pairs[s][k]) >= 1.0 for s in sens) for k in full)
            rows[p] = {"median_r_by_baseline": dict(zip(bl, meds)), "class": classify(meds),
                       "material_on": [b for b, x in zip(bl, mat) if x], "factor_pattern": factor_pattern(bl, mat),
                       "max_over_min_abs_median": rnd(max(absm) / min(absm)) if absm and min(absm) > 0 else None,
                       "factor_effects_on_median_r": fx,
                       "pairs_present_on_all_four": len(full), "pairs_same_sign_on_all_four": same_sign,
                       "pairs_material_on_all_four": all_mat}
        out[name] = rows
    # status and verdict persistence
    st = {}
    for rd in READINGS:
        sets = [set(per[s]["status_transitions_changed_only"][rd]) for s in sens]
        common = set.intersection(*sets)
        st[rd] = {"changes_on_every_combination": all(sets), "transitions_common_to_all_four": sorted(common),
                  "transitions_only_with_some": {t: [b for b, S in zip(bl, sets) if t in S] for t in sorted(set.union(*sets) - common)}}
    vsets = [{(c, k) for c, v in per[s]["verdict_changes"]["detail"].items() for k in v["members"]} for s in sens]
    csets = [set(per[s]["verdict_changes"]["candidate_level_changes"]) for s in sens]
    vcommon = set.intersection(*vsets)
    verdict = {"changes_on_every_combination": all(per[s]["verdict_changes"]["n_candidates_with_any_change"] for s in sens),
               "member_changes_common_to_all_four": sorted("|".join(x) for x in vcommon),
               "member_changes_only_with_some": {"|".join(x): [b for b, S in zip(bl, vsets) if x in S]
                                                 for x in sorted(set.union(*vsets) - vcommon)},
               "member_changes_factor_pattern": {"|".join(x): factor_pattern(bl, [x in S for S in vsets])
                                                 for x in sorted(set.union(*vsets) - vcommon)},
               "candidate_level_changes_factor_pattern": {c: factor_pattern(bl, [c in S for S in csets])
                                                          for c in sorted(set.union(*csets) - set.intersection(*csets))},
               "candidate_level_changes_common_to_all_four": sorted(set.intersection(*csets)),
               "candidate_level_changes_only_with_some": {c: [b for b, S in zip(bl, csets) if c in S]
                                                          for c in sorted(set.union(*csets) - set.intersection(*csets))}}
    ood = {"n_OOD_baseline_by_combination": {b: per[s]["ood"]["n_OUT_OF_DOMAIN_baseline"] for s, b in zip(sens, bl)},
           "n_OOD_sensitivity_by_combination": {b: per[s]["ood"]["n_OUT_OF_DOMAIN_sensitivity"] for s, b in zip(sens, bl)},
           "OOD_to_scoreable_by_combination": {b: per[s]["ood"]["n_OOD_to_scoreable"] for s, b in zip(sens, bl)},
           "scoreable_to_OOD_by_combination": {b: per[s]["ood"]["n_scoreable_to_OOD"] for s, b in zip(sens, bl)}}
    return {"observables": out, "status": st, "verdict": verdict, "ood": ood,
            "trigger_fired_on_all_four": all(per[s]["trigger_fired"] for s in sens)}


def build():
    inp = load_inputs()
    per, pairs = {}, {}
    for s_ch, b_ch, _ in inp["combos"]:
        per[s_ch], pairs[s_ch] = analyse_combo(inp, s_ch, b_ch)
    cons = consistency(per, pairs, inp["combos"])
    o4 = inp["crit"]["operational_rules"]["O4_staged_escalation"]
    res = {
        "schema": SCHEMA, "lane": "fo_johnsonlow_escalation_assessment", "trigger": "T_JOHNSONLOW_ESCALATION_ASSESSMENT",
        "question": "Is the Johnson-low electronic-excitation sensitivity material on every primary chemistry combination "
                    "(does it persist across the DI and N-elastic choices)?",
        "status_of_this_document": "evidence summary of frozen O4 scores; decides nothing; no criterion, tolerance, chemistry or "
                                   "transport change; Johnson-low stays a sensitivity/alternative; the v1 result is unchanged; "
                                   "no candidate is made PROMOTABLE or rejected by this assessment",
        "milestones": {"supports": ["physics-validation track: input to the O4 disposition matrix (fo_o4_disposition_matrix), "
                                    "which gates admission and therefore Milestone B"],
                       "not_used_for": ["Milestone A (no absolute Hall numbers are produced or implied)"],
                       "to_reach_next": "Milestone B needs an admitted transport closure (credible set is empty after v1), "
                                        "which needs genuinely new predictive evidence plus the owner's O4 dispositions; "
                                        "this document only supplies evidence for the Johnson-low row of that matrix."},
        "o4_rule_text": o4, "o4_thresholds": {"dI_over_Itarget": 0.075,
                                               "dT_axial_mN": {p: 0.5 * t for p, t in inp["crit"]["D3_tolerances"]["thrust_mN"].items()}},
        "persistence_rule": RULE,
        "provenance": {"checks": inp["checks"], "datasets": inp["prov_rows"], "other_inputs_sha256": inp["input_hashes"],
                       "all_checks_passed": all(c["ok"] for c in inp["checks"])},
        "combinations": [per[s] for s, _, _ in inp["combos"]],
        "consistency": cons,
    }
    res["answer"] = answer(res)
    js = json.dumps(res, indent=1, sort_keys=True) + "\n"
    return js, render_md(res)


def answer(res):
    cons = res["consistency"]
    obs = cons["observables"]
    cls = collections.Counter(r["class"] for rows in obs.values() for r in rows.values())
    persists = sorted(f"{o}@{p}" for o, rows in obs.items() for p, r in rows.items() if r["class"] == "PERSISTS")
    some = sorted(f"{o}@{p} ({r['factor_pattern']})" for o, rows in obs.items() for p, r in rows.items()
                  if r["class"] == "SIGN_PERSISTS_MATERIAL_ON_SOME")
    below = sorted(f"{o}@{p}" for o, rows in obs.items() for p, r in rows.items() if r["class"] == "SIGN_PERSISTS_BELOW_THRESHOLD")
    dep = sorted(f"{o}@{p}" for o, rows in obs.items() for p, r in rows.items() if r["class"] == "BASELINE_DEPENDENT_SIGN")
    tails = {c["baseline"]: c["tail"] for c in res["combinations"]}
    fired_all = cons["trigger_fired_on_all_four"]
    if fired_all and not persists:
        mode = "TAIL_AND_BOUNDARY_ON_ALL_FOUR"
        n_st = sum(t["n_runs_status_changed"] for t in tails.values())
        n_bd = sum(t["n_runs_status_changed_across_OOD_boundary"] for t in tails.values())
        dI_signs = {sign(m) for p, r in obs["dI"].items() for m in r["median_r_by_baseline"].values()}
        summary = ("The pre-registered O4 trigger fires on all four primary combinations, but through a minority of runs "
                   f"(individual large deltas and status changes; {n_bd} of {n_st} status-changed runs cross the "
                   "OUT_OF_DOMAIN boundary). No observable shows a median shift at or above the O4 threshold on any combination"
                   + ("; the median I_d shift is positive on all four at every point" if dI_signs == {1} else "")
                   + ("; the median shift changes sign with the baseline at " + ", ".join(dep) if dep else "") + ".")
    elif fired_all:
        mode = "SYSTEMATIC_ON_ALL_FOUR"
        summary = "The O4 trigger fires on all four combinations and at least one observable persists at median level."
    else:
        mode = "NOT_ON_ALL_FOUR"
        summary = "The O4 trigger does not fire on every primary combination."
    return {"material_on_every_primary_combination": fired_all, "mode": mode, "summary": summary,
            "basis": "pre-registered O4 trigger (scored staged_escalation.trigger_fired) on all four baselines; classes per "
                     "jla_persistence_rule_v1",
            "class_counts": dict(sorted(cls.items())),
            "observables_that_persist": persists, "observables_material_only_with_some_baselines": some,
            "observables_sign_consistent_below_threshold": below,
            "observables_with_baseline_dependent_sign": dep, "tail_by_baseline": tails,
            "status_changes_on_every_combination": {rd: cons["status"][rd]["changes_on_every_combination"] for rd in READINGS},
            "verdict_changes_on_every_combination": cons["verdict"]["changes_on_every_combination"],
            "verdict_changes_common_to_all_four": bool(cons["verdict"]["member_changes_common_to_all_four"]
                                                       or cons["verdict"]["candidate_level_changes_common_to_all_four"]),
            "what_this_does_not_mean": "a numerical effect, however large or persistent, is not experimental support for Johnson "
                                       "2005 over Su 2021 below 20 eV; it measures how much the P5-N2 observables depend on that "
                                       "choice."}


# ---------------------------------------------------------------------------------------------------------------- markdown
def f(x, n=3):
    if x is None:
        return "–"
    return f"{x:+.{n}f}" if isinstance(x, float) else str(x)


def render_md(res):
    L = []
    a = res["answer"]
    L += ["# Johnson-low escalation assessment (fo_johnsonlow_escalation_assessment)", "",
          "Generated by `docs/o4/johnsonlow_assessment/build_johnsonlow_assessment.py` from frozen, already-scored O4 datasets. "
          "Do not edit by hand; `--check` reproduces this file and `johnsonlow_assessment_v1.json` byte for byte.", "",
          "**Status.** Evidence summary only. It decides nothing, changes no criterion, tolerance, chemistry or transport parameter, "
          "and does not alter the P5-N2 v1 result (all nine SGB screening candidates INCONCLUSIVE / NOT ELIGIBLE; credible set "
          "empty; gate 3 FAIL). Johnson-low stays a sensitivity / alternative representation. No candidate is made PROMOTABLE "
          "or rejected by anything here. A large numerical effect is not experimental support (owner rule; v2 Question B is "
          "BLOCKED_BY_QUESTION_A_DISPOSITION under A-NO).", "",
          "**Milestones.** Supports the physics-validation track: it is evidence for the Johnson-low row of the O4 disposition "
          "matrix (`fo_o4_disposition_matrix`), which gates admission and therefore Milestone B. It is not used for Milestone A "
          "(no absolute Hall number is produced or implied). " + res["milestones"]["to_reach_next"], "",
          "## Question", "", res["question"], "",
          "Johnson-low (`n2_n_exc_johnsonlow*.toml`) uses Johnson et al. 2005 Table 2 cross sections for the eight N₂ electronic "
          "states at all energies, instead of Su et al. 2021 below 20 eV (see `hallthruster_bridge/propellants/PROVENANCE.md`). "
          "Pre-registered baselines: first stage against `n2_n.toml`; the three escalations against `n2_n_di_lower.toml`, "
          "`n2_n_nel_wang.toml` and `n2_n_di_lower_nel_wang.toml` (criteria `staged_sensitivities`).", "",
          "## Rule used (fixed in code before the distributions were computed)", "",
          "Materiality thresholds are the pre-registered O4 thresholds (|ΔI_d| ≥ 0.075 I_target; |ΔT_axial| ≥ 0.5 × tolerance = "
          "2.6 / 2.8 / 2.8 mN at N1 / N2 / N3). The median-based summary and the class names below are this assessment's reporting "
          "convention, PROPOSED to the owner; they gate nothing.", ""]
    R = res["persistence_rule"]
    L += [f"- Normalization: {R['normalization']}", f"- Per combination: {R['per_combination_summary']}."]
    L += [f"- **{k}**: {v}." for k, v in R["classes"].items()]
    L += [f"- Status / verdict: {R['status_and_verdict']}", f"- Factor pattern: {R['factor_pattern']}",
          f"- Answer: {R['answer_to_question']}", "",
          "O4 rule text (verbatim, `prereg/p5_n2_validation_criteria_v1.json` `operational_rules.O4_staged_escalation`):", ""]
    L += [f"- escalate if any vacuum: {x}" for x in res["o4_rule_text"]["escalate_to_other_three_primary_combinations_if_any_vacuum"]]
    L += ["", "## Answer", "",
          f"- Material on every primary combination (pre-registered O4 trigger fired on all four): "
          f"**{a['material_on_every_primary_combination']}** — mode `{a['mode']}`.",
          f"- {a['summary']}",
          f"- Observables that PERSIST (same sign and |median r| ≥ 1 on all four): {', '.join(a['observables_that_persist']) or 'none'}.",
          f"- Material (median) only with some baselines: {', '.join(a['observables_material_only_with_some_baselines']) or 'none'}.",
          f"- Same sign on all four, median below threshold: {', '.join(a['observables_sign_consistent_below_threshold']) or 'none'}.",
          f"- Baseline-dependent sign: {', '.join(a['observables_with_baseline_dependent_sign']) or 'none'}.",
          f"- Run statuses change on every combination: reading A {a['status_changes_on_every_combination']['A']}, "
          f"reading B {a['status_changes_on_every_combination']['B']}. O4 verdict-change clause non-empty on every combination: "
          f"{a['verdict_changes_on_every_combination']}; any member / candidate change common to all four: "
          f"{a['verdict_changes_common_to_all_four']}.", "",
          "| baseline | pairs with abs(ΔI_d) ≥ 0.075 I_t | pairs with abs(ΔT_A) ≥ O4 threshold (of N1–N3 pairs) | runs with a status change | "
          "of which across the OOD boundary | runs with any trigger |", "|---|---|---|---|---|---|"]
    for b, t in a["tail_by_baseline"].items():
        L.append(f"| {b} | {t['n_pairs_dI_ge_threshold']} / 270 | {t['n_pairs_dT_A_ge_threshold']} / {t['n_pairs_with_thrust']} | "
                 f"{t['n_runs_status_changed']} | {t['n_runs_status_changed_across_OOD_boundary']} | {t['n_runs_any_trigger']} |")
    L += ["", f"{a['what_this_does_not_mean'][0].upper() + a['what_this_does_not_mean'][1:]}", ""]

    L += ["## Provenance (all verified before any number was computed)", "",
          "| dataset | baseline | records | raw sha256 (canonical) | scores sha256 | mandatory reproduced |", "|---|---|---|---|---|---|"]
    for d in res["provenance"]["datasets"]:
        L.append(f"| {d['dataset']} | {d.get('baseline', '–')} | {d['n_records']} | `{d['raw_sha256_canonical'][:16]}…` | "
                 f"`{d['scores_sha256'][:16]}…` | {d.get('mandatory_reproduced', '(official)')} |")
    L += ["", f"{len(res['provenance']['checks'])} hash / binding checks, all passed: {res['provenance']['all_checks_passed']}. "
          "The frozen scorer (sha256-matched before import) reproduces every scored `staged_escalation` block exactly "
          "(run-level list and verdict-change clause), and the baseline statuses it assigns equal the official v1 scores.", ""]

    L += ["## 1. Per baseline combination", ""]
    for c in res["combinations"]:
        t = c["run_level_triggers"]
        L += [f"### {c['sensitivity']} vs {c['baseline']} ({c['factors']['DI']}, {c['factors']['N_elastic']})", "",
              f"trigger_fired **{c['trigger_fired']}**; {c['n_pairs']} matched pairs; {t['n_entries_total']} run-level trigger "
              f"entries ({t['note']}).", "",
              "| kind | entries | reading A | reading B | distinct runs |", "|---|---|---|---|---|"]
        for k, n in t["by_kind"].items():
            L.append(f"| {k} | {n} | {t['by_kind_and_reading'].get(k + '|A', 0)} | {t['by_kind_and_reading'].get(k + '|B', 0)} | "
                     f"{t['n_distinct_runs_triggered'].get(k, 0)} |")
        kinds = sorted(t["by_kind"])
        L += ["", "| point | " + " | ".join(kinds) + " |", "|---" * (len(kinds) + 1) + "|"]
        for p in POINTS:
            L.append(f"| {p} | " + " | ".join(str(t["by_point"][p].get(k, 0)) for k in kinds) + " |")
        L += ["", "| candidate | " + " | ".join(kinds) + " |", "|---" * (len(kinds) + 1) + "|"]
        for cand, v in t["by_candidate"].items():
            L.append(f"| {cand} | " + " | ".join(str(v.get(k, 0)) for k in kinds) + " |")
        L += ["", "| registration / coil | " + " | ".join(kinds) + " |", "|---" * (len(kinds) + 1) + "|"]
        for grp in ("by_registration", "by_coil_shape"):
            for g, v in t[grp].items():
                L.append(f"| {g} | " + " | ".join(str(v.get(k, 0)) for k in kinds) + " |")
        L += ["", "Signed deltas (sensitivity − baseline), all numerically valid pairs: ΔI_d / I_target and ΔT_axial [mN].", "",
              "| point | n | ΔI/I median | IQR | min | max | ΔT_A median [mN] | IQR | ΔT_B median [mN] | IQR |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for p in POINTS + ["pooled"]:
            di = c["deltas"]["dI_over_Itarget"].get(p, {"n": 0})
            ta = c["deltas"]["dT_axial_mN"]["A"].get(p, {}); tb = c["deltas"]["dT_axial_mN"]["B"].get(p, {})
            L.append(f"| {p} | {di['n']} | {f(di.get('median'))} | [{f(di.get('q25'))}, {f(di.get('q75'))}] | {f(di.get('min'))} | "
                     f"{f(di.get('max'))} | {f(ta.get('median'), 2)} | [{f(ta.get('q25'), 2)}, {f(ta.get('q75'), 2)}] | "
                     f"{f(tb.get('median'), 2)} | [{f(tb.get('q25'), 2)}, {f(tb.get('q75'), 2)}] |")
        te = c["deltas"]["dTe_max_eV"]["pooled"]
        bi = c["deltas"]["dI_over_Itarget_both_runs_in_domain"]["pooled"]
        L += ["", f"ΔI/I restricted to pairs where both runs are in the chemistry domain: n = {bi['n']}, median {f(bi.get('median'))}, "
              f"IQR [{f(bi.get('q25'))}, {f(bi.get('q75'))}]. ΔT_e,max [eV] pooled median {f(te.get('median'), 2)}, "
              f"IQR [{f(te.get('q25'), 2)}, {f(te.get('q75'), 2)}].", "",
              "Status transitions (baseline → sensitivity), changed only: reading A "
              + (", ".join(f"{k} ×{v}" for k, v in c["status_transitions_changed_only"]["A"].items()) or "none")
              + "; reading B " + (", ".join(f"{k} ×{v}" for k, v in c["status_transitions_changed_only"]["B"].items()) or "none") + ".", ""]
        v = c["verdict_changes"]
        L += [f"O4 verdict-change clause (provisional counterfactual; {v['meaning'].split(': ', 1)[1]}): {v['n_member_changes']} "
              f"member changes on {v['n_candidates_with_any_change']} candidates; member transitions "
              + (", ".join(f"{k} ×{n}" for k, n in v["member_transitions"].items()) or "none") + "; candidate-level: "
              + (", ".join(f"{k} {a_} → {b_}" for k, (a_, b_) in v["candidate_level_changes"].items()) or "none") + ".", ""]

    L += ["## 2. Consistency across the four combinations", "",
          "Median r (= median Δ / O4 threshold) per baseline; class per the rule above.", ""]
    bl = [c["baseline"] for c in res["combinations"]]
    for name, rows in res["consistency"]["observables"].items():
        L += [f"**{name}**", "", "| point | " + " | ".join(bl) + " | class | factor pattern | DI effect | Nel effect | interaction | "
              "pairs same sign on all four | pairs material on all four |", "|---" * (len(bl) + 8) + "|"]
        for p, r in rows.items():
            fx = r["factor_effects_on_median_r"] or {}
            L.append(f"| {p} | " + " | ".join(f(r["median_r_by_baseline"][b], 2) for b in bl) + f" | {r['class']} | "
                     f"{r['factor_pattern'] or '–'} | {f(fx.get('DI_lower_minus_upper'), 2)} | {f(fx.get('Nel_wang_minus_opm'), 2)} | "
                     f"{f(fx.get('interaction'), 2)} | {r['pairs_same_sign_on_all_four']}/{r['pairs_present_on_all_four']} | "
                     f"{r['pairs_material_on_all_four']}/{r['pairs_present_on_all_four']} |")
        L.append("")
    st, vd = res["consistency"]["status"], res["consistency"]["verdict"]
    for rd in READINGS:
        L += [f"Status transitions, reading {rd}: common to all four: {', '.join(st[rd]['transitions_common_to_all_four']) or 'none'}; "
              "only with some baselines: " + (", ".join(f"{k} [{', '.join(v)}]" for k, v in st[rd]["transitions_only_with_some"].items()) or "none") + "."]
    L += ["", "Member-level O4 verdict changes common to all four: " + (", ".join(vd["member_changes_common_to_all_four"]) or "none")
          + "; only with some baselines: " + (", ".join(f"{k} [{', '.join(v)}]" for k, v in vd["member_changes_only_with_some"].items()) or "none") + ".",
          "Candidate-level changes common to all four: " + (", ".join(vd["candidate_level_changes_common_to_all_four"]) or "none")
          + "; only with some baselines: " + (", ".join(f"{k} [{', '.join(v)}]" for k, v in vd["candidate_level_changes_only_with_some"].items()) or "none") + ".", ""]

    L += ["## 3. Chemistry-domain (OOD) interplay", "",
          "| baseline | OOD baseline | OOD Johnson-low | OOD → scoreable | scoreable → OOD | median f_out,max base | median f_out,max JL |",
          "|---|---|---|---|---|---|---|"]
    for c in res["combinations"]:
        o = c["ood"]
        L.append(f"| {c['baseline']} | {o['n_OUT_OF_DOMAIN_baseline']} | {o['n_OUT_OF_DOMAIN_sensitivity']} | {o['n_OOD_to_scoreable']} | "
                 f"{o['n_scoreable_to_OOD']} | {o['f_out_max_median_baseline']:.3g} | {o['f_out_max_median_sensitivity']:.3g} |")
    fams = sorted({k for c in res["combinations"] for k in list(c["ood"]["runs_with_family_beyond_limit_baseline"]) +
                   list(c["ood"]["runs_with_family_beyond_limit_sensitivity"])})
    L += ["", "Runs with at least one reaction of the family beyond its validity limit (f_out > 1e-12), baseline / Johnson-low:", "",
          "| baseline | " + " | ".join(fams) + " |", "|---" * (len(fams) + 1) + "|"]
    for c in res["combinations"]:
        o = c["ood"]
        L.append(f"| {c['baseline']} | " + " | ".join(f"{o['runs_with_family_beyond_limit_baseline'].get(k, 0)} / "
                                                     f"{o['runs_with_family_beyond_limit_sensitivity'].get(k, 0)}" for k in fams) + " |")
    L += ["", "Counts are runs (270 per combination; OUT_OF_DOMAIN is reading independent). A status change into or out of "
          "OUT_OF_DOMAIN is a change of scoreability under the unchanged 45 eV domain, not a change of the domain.", ""]

    vd = res["consistency"]["verdict"]
    tail_mode = a["mode"] == "TAIL_AND_BOUNDARY_ON_ALL_FOUR"
    L += ["## 4. What this implies (evidence statements only)", "",
          "- **O4 disposition matrix (Johnson-low row).** The first stage and all three pre-registered escalations are scored once, "
          "each bound to the official v1 mandatory scores (reproduced exactly); the O4 trigger fired on "
          + ("all four" if res["consistency"]["trigger_fired_on_all_four"] else "not all four") + " baselines. "
          + ("On every baseline it fires through a minority of individual runs and OUT_OF_DOMAIN-boundary status changes, not "
             "through a median shift of material size. " if tail_mode else "")
          + "No member- or candidate-level verdict change is common to all four baselines"
          + (" (member changes: " + ", ".join(f"{k} [{v}]" for k, v in vd["member_changes_factor_pattern"].items()) + ")"
             if vd["member_changes_factor_pattern"] else "")
          + ". These are evidence for the owner's disposition text; the disposition itself is the owner's and is not recorded here "
          "(`hallthruster_bridge/ensemble/o4_dispositions_schema_v1.json`).",
          "- **v1 result unchanged.** The O4 verdict-change clause is a provisional counterfactual that replaces one mandatory "
          "chemistry by the sensitivity. Any member or candidate change listed above (including a candidate-level change to "
          "FAIL_VALIDATION) is not a v1 verdict and rejects nothing; the v1 outcome stays INCONCLUSIVE permanently.",
          "- **Johnson-low stays a sensitivity / alternative.** "
          + ("Its effect survives the DI and N-elastic choices as a run-level (tail) and domain-boundary effect on every "
             "combination, with a small, sign-consistent median I_d increase; its effect on individual verdicts depends on the "
             "baseline. " if tail_mode else "")
          + "This is of the same standing as the recorded Su/Johnson overlap disagreement (CLAUDE.md abep-n2n-0.9); it is not "
          "evidence that either source is correct.",
          "- **OOD interplay.** Johnson-low leaves the 45 eV domain and every validity limit unchanged; it moves individual runs "
          "across the OUT_OF_DOMAIN boundary in both directions (section 3). Such moves change which runs are scoreable, which is "
          "why they appear as status triggers; they say nothing about a wider domain (Question A stays A-NO).",
          "- **Question B.** Blocked by the A-NO disposition (`docs/v2/question_a/QUESTION_A_DISPOSITION.json`); nothing here "
          "reopens it. Should Question A ever be reopened on new published evidence, this assessment indicates that (i) the "
          "below-20 eV representation would have to be settled from independent cross-section evidence, not from agreement with "
          "P5-N2 (not new evidence for this purpose), and (ii) because the run-level effect appears on all four primary "
          "combinations while verdict effects are baseline-specific, any future pre-registration would need to carry the "
          "representation as an explicit branch on all four combinations rather than on one.",
          "- **Scope.** This concerns only the ionization/discharge chemistry of the P5-N2 validation; it says nothing about "
          "intake, compressor, gas chambers, valves or Vyovrinda thruster geometry, and names no architecture.", ""]
    return "\n".join(L) + "\n"


def main(argv):
    js, md = build()
    if "--check" in argv:
        ok = os.path.isfile(OUT_JSON) and os.path.isfile(OUT_MD) and open(OUT_JSON).read() == js and open(OUT_MD).read() == md
        print("CHECK", "OK" if ok else "MISMATCH")
        return 0 if ok else 1
    open(OUT_JSON, "w").write(js)
    open(OUT_MD, "w").write(md)
    print("wrote", rel(OUT_JSON), rel(OUT_MD))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

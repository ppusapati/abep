"""OUT_OF_DOMAIN attribution for the frozen P5-N2 v1 vacuum campaign. DESCRIPTIVE AND NON-GATING.

Why are 714 of the 1080 v1 vacuum runs (1428 of 2160 run x reading evaluations) OUT_OF_DOMAIN? This script answers that
from the recorded per-reaction chemistry-validity fields only. It does not score, re-score or re-label any run. Every status
and reason is read verbatim from the official scores file. No criterion, tolerance, validity limit, chemistry table or
transport parameter is changed or proposed. The v1 result (all nine screening candidates INCONCLUSIVE / NOT ELIGIBLE,
credible set empty, gate 3 FAIL) is permanent. Nothing here can alter it.

Inputs (read-only, integrity-checked against the frozen release chain before anything is computed):
  hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_raw.jsonl.gz     raw records (1080)
  hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_raw_manifest.json freeze manifest (sha256 of the gz and canonical jsonl)
  hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json                 release (sha256 of scores, report, manifest, scorer)
  hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores.json       OFFICIAL per-run statuses (2160 run-readings)
  hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_report.md  OFFICIAL report (per-candidate counts, reconciled)
  hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json, p5_n2_run_status_rule_v1.json, p5_n2_validation_criteria_v1.json
  hallthruster_bridge/propellants/rate_validity.toml and the four mandatory chemistry configs (sha256-pinned in the criteria)
  hallthruster_bridge/bridge_lib.jl, scripts/score_p5_n2_campaign.py        (source text only: the definitions of f_out,
                                                                             max_mean_energy_active_eV, Te_max_eV, the OOD
                                                                             predicate and the O1 thresholds are asserted
                                                                             against the code, never assumed)
Outputs: <out-dir>/ood_attribution.json and <out-dir>/OOD_ATTRIBUTION.md (default docs/forensics/p5_n2_v1/ood_attribution/).
Deterministic: no clocks, no randomness, sorted keys, fixed iteration order. Runtime: a few seconds.
Usage: python scripts/forensics/p5_n2_v1_ood_attribution.py [--out-dir DIR]
"""
import argparse, collections, gzip, hashlib, json, math, os, sys, tomllib

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BR = os.path.join(ROOT, "hallthruster_bridge")
REL = {
    "raw": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_raw.jsonl.gz",
    "raw_manifest": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_raw_manifest.json",
    "release": "hallthruster_bridge/validation/VALIDATION_RELEASE_v1.json",
    "scores": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores.json",
    "report": "hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_scores_report.md",
    "prereg_lock": "hallthruster_bridge/prereg/p5_n2_prereg_lock_v1.json",
    "run_status_rule": "hallthruster_bridge/prereg/p5_n2_run_status_rule_v1.json",
    "criteria": "hallthruster_bridge/prereg/p5_n2_validation_criteria_v1.json",
    "rate_validity": "hallthruster_bridge/propellants/rate_validity.toml",
    "bridge_lib": "hallthruster_bridge/bridge_lib.jl",
    "scorer": "scripts/score_p5_n2_campaign.py",
}
DEFAULT_OUT = os.path.join(ROOT, "docs", "forensics", "p5_n2_v1", "ood_attribution")
POINTS = ["N1", "N2", "N3", "N4", "N5"]
READINGS = ["A", "B"]
LADDER_EV = [45.0, 60.0, 75.0, 90.0, 120.0, 150.0, 200.0, 255.0]
OOD, FAIL, PASS, NUMF = "OUT_OF_DOMAIN", "FAIL_VALIDATION", "PASS", "NUMERICAL_FAILURE"
HYPO_LABEL = "HYPOTHETICAL COUNTING ONLY - not a scoring, not a verdict, not a proposal to change limits"

# Code lines whose presence is asserted, so every definition quoted in the outputs is tied to the code that produced the
# records (bridge_lib.jl is unchanged since the campaign driver commit) or scored them (scorer sha256-pinned by the release).
BRIDGE_DEFS = {
    "tolerance": "const CHEM_FOUT_TOL = 1e-12",
    "window": "return chemistry_activity(sol.frames[i0:end], collect(sol.grid), chemistry_reactions(c))",
    "mean_energy": "eps = 1.5 * f.Tev[i]",
    "activity": "push!(acts, f.ne[i] * nt[i] * rate_at(r.k, eps) * dz[i]); push!(epss, eps)",
    "eps_active": "R > CHEM_FOUT_TOL * Rmax && (epsmax = max(epsmax, eps))",
    "f_out_numerator": "!isnothing(r.limit) && eps > r.limit && (out += R)",
    "f_out": "fout=isnothing(r.limit) ? nothing : (tot > 0 ? out / tot : 0.0)",
    "te_max_frame": "fr = avg.frames[1]",
    "te_max": 'out["Te_max_eV"] = maximum(fr.Tev)',
    "time_average": "avg = het.time_average(sol, c.average_start_s)",
}
SCORER_DEFS = {
    "tolerance": "FOUT_TOL = 1e-12",
    "ood_predicate": "if unresolved or any(f is None or f > FOUT_TOL for f in fouts):",
    "o1": 'if det["final10_mean_over_target"] < 0.05 and det["final10_frac_below_0p10"] >= 0.90:',
    "o1_frac": "frac_low = sum(x < 0.10 * I_t for x in s) / len(s)",
}


def path(k):
    return os.path.join(ROOT, REL[k])


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    with open(p, "rb") as f:
        return sha_bytes(f.read())


def load_inputs():
    """Load every input and refuse to continue unless it is the frozen, released version."""
    shas = {k: sha_file(path(k)) for k in REL}
    manifest = json.load(open(path("raw_manifest")))
    release = json.load(open(path("release")))
    lock = json.load(open(path("prereg_lock")))
    crit = json.load(open(path("criteria")))
    with gzip.open(path("raw"), "rb") as f:
        raw_bytes = f.read()
    checks = {
        "raw_gz_sha256_matches_freeze_manifest": shas["raw"] == manifest["sha256_gz"],
        "raw_canonical_sha256_matches_manifest": sha_bytes(raw_bytes) == manifest["sha256_canonical_jsonl"],
        "raw_canonical_sha256_matches_release": sha_bytes(raw_bytes) == release["dataset"]["sha256_canonical_jsonl"],
        "freeze_manifest_sha256_matches_release": shas["raw_manifest"] == release["dataset"]["freeze_manifest_sha256"],
        "scores_sha256_matches_release": shas["scores"] == release["scores"]["sha256"],
        "report_sha256_matches_release": shas["report"] == release["report"]["sha256"],
        "scorer_sha256_matches_release": shas["scorer"] == release["scorer"]["sha256"],
        "run_status_rule_sha256_matches_prereg_lock":
            shas["run_status_rule"] == lock["files"]["prereg/p5_n2_run_status_rule_v1.json"],
        "criteria_sha256_matches_prereg_lock": shas["criteria"] == lock["files"]["prereg/p5_n2_validation_criteria_v1.json"],
    }
    configs = {}
    for ch in crit["mandatory_chemistry"]:
        p = os.path.join(BR, "propellants", ch)
        checks[f"chemistry_config_{ch}_sha256_matches_criteria"] = \
            sha_file(p) == crit["inputs_pinned"]["chemistry_configs_sha256"][ch]
        shas[f"chemistry_config:{ch}"] = sha_file(p)
        with open(p, "rb") as f:
            configs[ch] = [r["rate_coeff_file"] for r in tomllib.load(f).get("reactions", []) if "rate_coeff_file" in r]
    bridge = open(path("bridge_lib")).read()
    scorer = open(path("scorer")).read()
    for k, line in BRIDGE_DEFS.items():
        checks[f"bridge_lib_defines_{k}"] = line in bridge
    for k, line in SCORER_DEFS.items():
        checks[f"scorer_defines_{k}"] = line in scorer
    bad = [k for k, v in checks.items() if not v]
    if bad:
        sys.exit("refusing to run: inputs are not the frozen release chain or a definition moved: " + ", ".join(bad))
    records = [json.loads(l) for l in raw_bytes.decode().splitlines() if l.strip()]
    scores = json.load(open(path("scores")))
    rule = json.load(open(path("run_status_rule")))
    with open(path("rate_validity"), "rb") as f:
        validity = tomllib.load(f)
    report = open(path("report")).read()
    return dict(records=records, scores=scores, rule=rule, validity=validity, report=report, configs=configs,
                crit=crit, shas=shas, checks=checks)


# ---------------------------------------------------------------------------------------------------------------- helpers
def quantile(sorted_vals, q):
    """Linear interpolation between order statistics (Hyndman-Fan type 7, numpy's default)."""
    n = len(sorted_vals)
    h = (n - 1) * q
    lo = int(h)
    hi = min(lo + 1, n - 1)
    return sorted_vals[lo] + (h - lo) * (sorted_vals[hi] - sorted_vals[lo])


def dist(vals):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return {"n": 0}
    return {"n": len(v), "min": v[0], "p10": quantile(v, 0.10), "median": quantile(v, 0.5), "p90": quantile(v, 0.90),
            "max": v[-1]}


def share(a, b):
    return round(a / b, 6) if b else None


def subfamily(f):
    if f.startswith("dissociation_N2"):
        return "dissociation"
    if f.startswith("excitation_N2_vib_"):
        return "vibrational"
    if f.startswith("excitation_N2_rot_"):
        return "rotational"
    if f.startswith("excitation_N2_"):
        return "electronic"
    return "other"


SUB_ORDER = ["dissociation", "electronic", "vibrational", "rotational"]
SUB_TAG = {"dissociation": "D", "electronic": "E", "vibrational": "V", "rotational": "R"}
CATEGORIES = ["IN_DOMAIN", "FULL_45EV_FAMILY", "DISSOCIATION_ONLY", "NO_VIBRATIONAL", "PARTIAL_VIBRATIONAL", "OTHER"]
CATEGORY_TEXT = {
    "IN_DOMAIN": "no file beyond its limit (official status is not OUT_OF_DOMAIN)",
    "FULL_45EV_FAMILY": "every one of the run's 45 eV-capped files is beyond its limit (dissociation + 8 electronic + "
                        "10 vibrational + 2 rotational)",
    "DISSOCIATION_ONLY": "dissociation_N2.dat is the only file beyond its limit",
    "NO_VIBRATIONAL": "dissociation plus some electronic and/or rotational files beyond, no vibrational file beyond",
    "PARTIAL_VIBRATIONAL": "dissociation plus some but not all vibrational files beyond (electronic/rotational: see the "
                           "sub-family pattern table)",
    "OTHER": "any other pattern (e.g. a 255 eV-capped file beyond, dissociation not beyond, or an unresolved table)",
}


# --------------------------------------------------------------------------------------------------------------- analysis
def analyse(inp):
    records, scores, validity, configs = inp["records"], inp["scores"], inp["validity"], inp["configs"]
    tol = float(inp["rule"]["chemistry_trust_rule"]["f_out_tolerance"])
    mandatory = inp["crit"]["mandatory_chemistry"]

    # ---- official statuses, verbatim
    off = collections.defaultdict(dict)
    for s in scores["runs"]:
        off[s["key"]][s["reading"]] = s
    member_verdicts = scores["candidates"]["vacuum"]

    # ---- per-record derived quantities (from the recorded per-reaction fields only)
    fam_of_limit = {}
    rows = []
    record_file_checks = {"per_reaction_files_match_config": True, "record_limit_matches_rate_validity": True,
                          "one_entry_per_file": True}
    for r in sorted(records, key=lambda x: x["key"]):
        chem = r["chemistry_per_reaction"]
        files = [q["file"] for q in chem]
        if files != configs[r["chemistry"]]:
            record_file_checks["per_reaction_files_match_config"] = False
        if len(set(files)) != len(files):
            record_file_checks["one_entry_per_file"] = False
        per = {}
        for q in chem:
            v = validity[q["file"]]
            lim = float(v["max_mean_energy_eV"]) if v["status"] == "verified" else None
            if q["max_mean_energy_eV"] != lim:
                record_file_checks["record_limit_matches_rate_validity"] = False
            fam_of_limit.setdefault(lim, set()).add(q["file"])
            per[q["file"]] = {"limit": lim, "fout": q["extrapolated_fraction"], "eps": q["max_mean_energy_active_eV"]}
        beyond = sorted(f for f, d in per.items() if d["fout"] is None or d["fout"] > tol)
        unresolved = list(r.get("chemistry_unresolved_rate_files") or [])
        fam45 = sorted(f for f, d in per.items() if d["limit"] == 45.0)
        o = off[r["key"]]
        rows.append({
            "key": r["key"], "candidate": r["candidate"], "chemistry": r["chemistry"], "point": r["point"],
            "registration": r["registration"], "coil_shape": r["coil_shape"], "case": r["case"], "per": per,
            "beyond": beyond, "unresolved": unresolved, "fam45": fam45, "Te_max_eV": r["Te_max_eV"],
            "sustained_flag": r["sustained"], "status": {rd: o[rd]["status"] for rd in READINGS},
            "reasons": {rd: tuple(o[rd]["reasons"]) for rd in READINGS}, "off": o,
        })
    fam45_all = sorted(fam_of_limit.get(45.0, set()))
    fam255_all = sorted(fam_of_limit.get(255.0, set()))
    other_limits = sorted(str(k) for k in fam_of_limit if k not in (45.0, 255.0))

    for x in rows:
        x["ood"] = x["status"]["A"] == OOD
        b = set(x["beyond"])
        subc = collections.Counter(subfamily(f) for f in b)
        x["pattern"] = " ".join(f"{SUB_TAG[s]}{subc[s]}" for s in SUB_ORDER) + (" X%d" % subc["other"] if subc["other"] else "")
        nv_run = sum(1 for f in x["fam45"] if subfamily(f) == "vibrational")
        if not b and not x["unresolved"]:
            cat = "IN_DOMAIN"
        elif x["unresolved"] or not b <= set(x["fam45"]) or "dissociation_N2.dat" not in b:
            cat = "OTHER"
        elif b == set(x["fam45"]):
            cat = "FULL_45EV_FAMILY"
        elif b == {"dissociation_N2.dat"}:
            cat = "DISSOCIATION_ONLY"
        elif subc["vibrational"] == 0:
            cat = "NO_VIBRATIONAL"
        elif subc["vibrational"] < nv_run:
            cat = "PARTIAL_VIBRATIONAL"
        else:
            cat = "OTHER"
        x["category"] = cat
        x["fam45_eps_max"] = max(x["per"][f]["eps"] for f in x["fam45"])
        x["f_out_max"] = max((d["fout"] for d in x["per"].values() if d["fout"] is not None), default=None)
        o = x["off"]["A"]
        x["o1_pattern"] = (o["final10_mean_over_target"] < 0.05 and o["final10_frac_below_0p10"] >= 0.90)

    ood_rows = [x for x in rows if x["ood"]]
    ind_rows = [x for x in rows if not x["ood"]]

    # ---- reconciliation with the official counts
    st_counts = collections.Counter(s["status"] for s in scores["runs"])
    reading_dependent = [x["key"] for x in rows if (x["status"]["A"] == OOD) != (x["status"]["B"] == OOD)]
    predicate_disagree = [x["key"] for x in rows if bool(x["beyond"] or x["unresolved"]) != x["ood"]]
    fmax_mismatch = [x["key"] for x in ood_rows for rd in READINGS if x["off"][rd].get("f_out_max") != x["f_out_max"]]
    final10_reading_dependent = [x["key"] for x in rows if any(
        x["off"]["A"][k] != x["off"]["B"][k] for k in ("final10_mean_over_target", "final10_frac_below_0p10"))]
    report_ood = parse_report_ood_by_candidate(inp["report"])
    cands = sorted({x["candidate"] for x in rows})
    per_cand = {}
    for c in cands:
        n_rr = sum(1 for s in scores["runs"] if s["key"].split("|")[0] == c and s["status"] == OOD)
        per_cand[c] = {"official_OOD_run_readings_from_scores_file": n_rr,
                       "official_OOD_run_readings_from_report": report_ood.get(c),
                       "OOD_runs": sum(1 for x in ood_rows if x["candidate"] == c)}
    recon = {
        "n_records": len(records),
        "n_run_readings_in_scores_file": len(scores["runs"]),
        "official_status_counts_vacuum": dict(sorted(scores["status_counts"]["vacuum"].items())),
        "status_counts_recounted_from_scores_runs": dict(sorted(st_counts.items())),
        "n_OOD_runs": len(ood_rows),
        "n_OOD_run_readings": sum(1 for x in ood_rows for rd in READINGS if x["status"][rd] == OOD),
        "n_in_domain_runs": len(ind_rows),
        "OOD_status_reading_independent": not reading_dependent,
        "n_runs_with_reading_dependent_OOD": len(reading_dependent),
        "per_candidate": per_cand,
        "per_candidate_matches_report": all(v["official_OOD_run_readings_from_scores_file"] ==
                                            v["official_OOD_run_readings_from_report"] == 2 * v["OOD_runs"]
                                            for v in per_cand.values()),
        "input_consistency_OOD_predicate_on_raw_fields_agrees_with_official_label": not predicate_disagree,
        "input_consistency_n_disagreements": len(predicate_disagree),
        "input_consistency_note": "The scorer's OOD predicate (any unresolved table, or any reaction with f_out > 1e-12) is "
                                  "re-evaluated on the raw fields ONLY to confirm that the attribution below reads the same "
                                  "numbers the scorer read. The official label is always taken from the scores file.",
        "official_f_out_max_equals_raw_max_in_OOD_runs": not fmax_mismatch,
        "final10_observables_reading_independent": not final10_reading_dependent,
        "n_OOD_runs_with_unresolved_tables": sum(1 for x in ood_rows if x["unresolved"]),
        "record_checks": record_file_checks,
        "n_frames_final10_samples_per_record": sorted({len(r["Id_final10_samples_A"]) for r in records}),
        "t_end_s_values": sorted({r["t_end_s"] for r in records}),
    }

    # ---- (1) per rate file
    files_all = sorted({f for x in rows for f in x["per"]}, key=lambda f: (validity[f].get("max_mean_energy_eV", 0), f))
    per_file = {}
    for f in files_all:
        using = [x for x in rows if f in x["per"]]
        lim = using[0]["per"][f]["limit"]
        fo = [x["per"][f]["fout"] for x in using]
        ep = [x["per"][f]["eps"] for x in using]
        bey = [x for x in using if f in x["beyond"]]
        nbey = [x for x in using if f not in x["beyond"]]
        per_file[f] = {
            "limit_mean_energy_eV": lim, "limit_Te_eV": None if lim is None else lim / 1.5,
            "validity_status": validity[f]["status"], "validity_basis": validity[f]["basis"],
            "limit_family": f"{lim:g} eV" if lim is not None else "unresolved", "subfamily": subfamily(f),
            "chemistry_configs_using": [ch for ch in mandatory if f in configs[ch]],
            "n_runs_using": len(using),
            "n_runs_f_out_gt_tol": len(bey),
            "n_runs_f_out_exactly_zero": sum(1 for v in fo if v == 0.0),
            "n_runs_f_out_in_(0,tol]": sum(1 for v in fo if v is not None and 0.0 < v <= tol),
            "n_OOD_runs_using": sum(1 for x in using if x["ood"]),
            "n_runs_sole_cause": sum(1 for x in using if x["beyond"] == [f]),
            "n_OOD_runs_where_file_has_largest_f_out": sum(
                1 for x in bey if x["per"][f]["fout"] == x["f_out_max"]),
            "f_out_over_runs_beyond": dist([x["per"][f]["fout"] for x in bey]),
            "f_out_over_all_runs_using": dist(fo),
            "max_mean_energy_active_eV_over_all_runs_using": dist(ep),
            "max_mean_energy_active_eV_over_runs_beyond": dist([x["per"][f]["eps"] for x in bey]),
            "max_mean_energy_active_eV_over_runs_not_beyond": dist([x["per"][f]["eps"] for x in nbey]),
            "max_mean_energy_active_over_limit_ratio": None if lim is None else dist([e / lim for e in ep]),
            "n_runs_max_mean_energy_active_gt_limit": None if lim is None else sum(1 for e in ep if e > lim),
            "concordance_at_recorded_limit": None if lim is None else {
                "f_out_gt_tol_and_eps_active_gt_limit": sum(1 for x in using if f in x["beyond"] and x["per"][f]["eps"] > lim),
                "f_out_gt_tol_and_eps_active_le_limit": sum(1 for x in using if f in x["beyond"] and x["per"][f]["eps"] <= lim),
                "f_out_le_tol_and_eps_active_gt_limit": sum(1 for x in using if f not in x["beyond"] and x["per"][f]["eps"] > lim),
                "f_out_le_tol_and_eps_active_le_limit": sum(1 for x in using if f not in x["beyond"] and x["per"][f]["eps"] <= lim),
            },
        }

    # ---- magnitude of the largest f_out per run (decades), OOD and in-domain
    def decade(v):
        return "0" if v == 0.0 else f"1e{math.floor(math.log10(v))}"
    magnitude = {
        "note": "f_out_max = largest recorded f_out over the run's reactions. Decade bins [1eK, 1e(K+1)). The pre-registered "
                "rule is f_out <= 1e-12 (numerical zero); this is a description of how far above or below it the runs sit.",
        "f_out_max_OOD": dist([x["f_out_max"] for x in ood_rows]),
        "f_out_max_OOD_decade_histogram": dict(sorted(collections.Counter(decade(x["f_out_max"]) for x in ood_rows).items(),
                                                      key=lambda kv: float(kv[0]))),
        "f_out_max_in_domain_decade_histogram": dict(sorted(collections.Counter(decade(x["f_out_max"]) for x in ind_rows).items(),
                                                            key=lambda kv: float(kv[0]))),
        "n_OOD_runs_f_out_max_lt_1e-11": sum(1 for x in ood_rows if x["f_out_max"] < 1e-11),
        "n_OOD_runs_f_out_max_lt_1e-9": sum(1 for x in ood_rows if x["f_out_max"] < 1e-9),
        "n_OOD_runs_f_out_max_lt_1e-6": sum(1 for x in ood_rows if x["f_out_max"] < 1e-6),
        "n_OOD_runs_f_out_max_ge_1e-2": sum(1 for x in ood_rows if x["f_out_max"] >= 1e-2),
        "n_in_domain_runs_f_out_max_exactly_zero": sum(1 for x in ind_rows if x["f_out_max"] == 0.0),
        "n_in_domain_runs_f_out_max_in_(0,tol]": sum(1 for x in ind_rows if 0.0 < x["f_out_max"] <= tol),
        "f_out_max_in_domain": dist([x["f_out_max"] for x in ind_rows]),
    }

    # ---- (2) co-occurrence structure
    order = sorted(fam45_all, key=lambda f: (-per_file[f]["n_runs_f_out_gt_tol"], f))
    beyond_sets = [set(x["beyond"]) for x in ood_rows]
    nonnested, breakers = [], set()
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            ab = [x["key"] for x in ood_rows if a in x["beyond"] and b not in x["beyond"]]
            ba = [x["key"] for x in ood_rows if b in x["beyond"] and a not in x["beyond"]]
            if ab and ba:
                minority = ba if len(ba) <= len(ab) else ab
                breakers.update(minority)
                nonnested.append({"file_a": a, "file_b": b, "n_runs_a_beyond_b_not": len(ab), "n_runs_b_beyond_a_not": len(ba)})
    cooc = {
        "limit_families": {"45 eV": fam45_all, "255 eV": fam255_all, "other_limits": other_limits},
        "45eV_subfamilies": {s: [f for f in fam45_all if subfamily(f) == s] for s in SUB_ORDER},
        "45eV_family_identical_in_all_mandatory_configs": len({tuple(sorted(f for f in configs[ch] if f in fam45_all))
                                                              for ch in mandatory}) == 1,
        "n_OOD_runs": len(ood_rows),
        "n_OOD_runs_beyond_set_exactly_full_45eV_family": sum(1 for x in ood_rows if set(x["beyond"]) == set(x["fam45"])),
        "n_OOD_runs_beyond_set_within_45eV_family": sum(1 for x in ood_rows if set(x["beyond"]) <= set(x["fam45"])),
        "n_runs_any_file_outside_45eV_family_beyond": sum(1 for x in rows if set(x["beyond"]) - set(x["fam45"])),
        "n_runs_any_255eV_file_beyond": sum(1 for x in rows if set(x["beyond"]) & set(fam255_all)),
        "n_runs_with_unresolved_table": sum(1 for x in rows if x["unresolved"]),
        "n_OOD_runs_with_dissociation_beyond": sum(1 for x in ood_rows if "dissociation_N2.dat" in x["beyond"]),
        "n_OOD_runs_dissociation_has_largest_f_out": sum(
            1 for x in ood_rows if x["per"]["dissociation_N2.dat"]["fout"] == x["f_out_max"]),
        "sole_cause_counts": {f: sum(1 for s in beyond_sets if s == {f}) for f in files_all},
        "beyond_set_size_histogram": dict(sorted(collections.Counter(len(s) for s in beyond_sets).items())),
        "subfamily_pattern_counts": dict(sorted(collections.Counter(x["pattern"] for x in ood_rows).items(),
                                                key=lambda kv: (-kv[1], kv[0]))),
        "category_counts_OOD_runs": {c: sum(1 for x in ood_rows if x["category"] == c) for c in CATEGORIES[1:]},
        "category_definitions": CATEGORY_TEXT,
        "per_subfamily_OOD_runs_with_any_file_beyond": {
            s: sum(1 for x in ood_rows if any(subfamily(f) == s for f in x["beyond"])) for s in SUB_ORDER},
        "per_subfamily_OOD_runs_with_all_files_beyond": {
            s: sum(1 for x in ood_rows if all(f in x["beyond"] for f in x["fam45"] if subfamily(f) == s)) for s in SUB_ORDER},
        "n_OOD_runs_vibrational_beyond_without_all_electronic_and_rotational_beyond": sum(
            1 for x in ood_rows if any(subfamily(f) == "vibrational" for f in x["beyond"])
            and not all(f in x["beyond"] for f in x["fam45"] if subfamily(f) in ("electronic", "rotational"))),
        "n_OOD_runs_electronic_or_rotational_beyond_without_dissociation_beyond": sum(
            1 for x in ood_rows if any(subfamily(f) in ("electronic", "rotational") for f in x["beyond"])
            and "dissociation_N2.dat" not in x["beyond"]),
        "nesting": {
            "order_by_n_runs_beyond": [[f, per_file[f]["n_runs_f_out_gt_tol"]] for f in order],
            "n_file_pairs": len(order) * (len(order) - 1) // 2,
            "non_nested_pairs": nonnested,
            "n_OOD_runs_breaking_the_majority_nesting_of_some_pair": len(breakers),
            "note": "A pair (a, b) is nested when every OOD run with b beyond its limit also has a beyond (or vice versa). "
                    "If all pairs were nested the beyond-limit sets would form one chain (dissociation first). For a "
                    "non-nested pair the smaller of the two counts is the minority (on a tie, the second count); a run "
                    "'breaks the majority nesting' when it is in the minority of at least one pair.",
        },
    }

    # ---- (3) breakdowns
    factors = ["candidate", "point", "chemistry", "registration", "coil_shape"]
    breakdown = {}
    for fac in factors:
        lv = {}
        for level in sorted({x[fac] for x in rows}):
            sel = [x for x in rows if x[fac] == level]
            so = [x for x in sel if x["ood"]]
            lv[level] = {
                "n_runs": len(sel), "n_OOD_runs": len(so), "OOD_share": share(len(so), len(sel)),
                "n_OOD_run_readings": 2 * len(so),
                "OOD_categories": {c: sum(1 for x in so if x["category"] == c) for c in CATEGORIES[1:]},
                "f_out_max_over_OOD_runs": dist([x["f_out_max"] for x in so]),
                "dissociation_max_mean_energy_active_eV_all_runs": dist(
                    [x["per"]["dissociation_N2.dat"]["eps"] for x in sel]),
            }
        breakdown[fac] = lv
    # layer-1 member = registration | coil | reading; OOD does not depend on the reading
    members = sorted({f"{x['registration']}|{x['coil_shape']}|{rd}" for x in rows for rd in READINGS})
    by_member = {}
    for m in members:
        reg, coil, rd = m.split("|")
        sel = [x for x in rows if x["registration"] == reg and x["coil_shape"] == coil]
        by_member[m] = {"n_runs": len(sel), "n_OOD_runs": sum(1 for x in sel if x["status"][rd] == OOD),
                        "OOD_share": share(sum(1 for x in sel if x["status"][rd] == OOD), len(sel))}
    breakdown["global_layer1_member"] = by_member
    breakdown["reading_independence"] = {
        "statement": "OOD does not depend on the divergence reading (A/B): the scorer's OOD predicate uses only the "
                     "per-reaction chemistry fields and unresolved tables, never the reading, and the official statuses "
                     "agree (OOD for both readings or for neither) in every run.",
        "n_runs_reading_dependent": len(reading_dependent),
        "members_A_and_B_have_identical_OOD_counts": all(
            by_member[m]["n_OOD_runs"] == by_member[m[:-1] + "B"]["n_OOD_runs"] for m in members if m.endswith("|A")),
    }
    cm = {}
    for c in cands:
        cm[c] = {"official_candidate_verdict": member_verdicts[c]["candidate"], "members": {}}
        for m in members:
            reg, coil, rd = m.split("|")
            sel = [x for x in rows if x["candidate"] == c and x["registration"] == reg and x["coil_shape"] == coil
                   and x["chemistry"] in mandatory]
            stc = collections.Counter(x["status"][rd] for x in sel)
            cm[c]["members"][m] = {"n_runs": len(sel), "n_OOD": stc[OOD], "n_FAIL_VALIDATION": stc[FAIL], "n_PASS": stc[PASS],
                                   "n_NUMERICAL_FAILURE": stc[NUMF],
                                   "official_member_verdict": member_verdicts[c]["members"][m]}
    breakdown["candidate_x_member"] = cm
    breakdown["candidate_x_member_OOD_count_histogram"] = dict(sorted(collections.Counter(
        v["n_OOD"] for c in cands for v in cm[c]["members"].values()).items()))
    breakdown["official_member_verdict_vs_OOD_count"] = {
        verdict: dict(sorted(collections.Counter(v["n_OOD"] for c in cands for v in cm[c]["members"].values()
                                                 if v["official_member_verdict"] == verdict).items()))
        for verdict in sorted({v["official_member_verdict"] for c in cands for v in cm[c]["members"].values()})}
    two_way = {}
    for fa, fb in (("candidate", "registration"), ("point", "registration"), ("candidate", "point"),
                   ("registration", "coil_shape"), ("candidate", "chemistry")):
        t = {}
        for a in sorted({x[fa] for x in rows}):
            for b in sorted({x[fb] for x in rows}):
                sel = [x for x in rows if x[fa] == a and x[fb] == b]
                t[f"{a}|{b}"] = {"n_runs": len(sel), "n_OOD_runs": sum(1 for x in sel if x["ood"]),
                                 "OOD_share": share(sum(1 for x in sel if x["ood"]), len(sel))}
        two_way[f"{fa}_x_{fb}"] = t
    breakdown["two_way"] = two_way
    contrasts = {}
    for fac in factors:
        others = [g for g in factors if g != fac]
        groups = collections.defaultdict(list)
        for x in rows:
            groups[tuple(x[g] for g in others)].append(x["ood"])
        mixed = sum(1 for v in groups.values() if len(set(v)) > 1)
        contrasts[fac] = {"n_groups": len(groups), "group_size": len(next(iter(groups.values()))),
                          "n_groups_with_mixed_OOD_status": mixed, "share": share(mixed, len(groups))}
    breakdown["controlled_contrasts"] = {
        "note": "Groups of runs identical in every factor except the named one (the design is fully crossed: 9 candidates x "
                "4 chemistry x 5 points x 3 registrations x 2 coil shapes, one run per cell). A group is 'mixed' when changing "
                "only that factor changes the OOD status. Descriptive within the model; not a physical attribution.",
        "by_factor": contrasts,
    }

    # ---- (4) hypothetical limit ladder for the 45 eV family (proxy: max_mean_energy_active_eV)
    ladder = []
    n_cells = len(cands) * len(members)
    for L in LADDER_EV:
        ok = {x["key"]: x["fam45_eps_max"] <= L for x in rows}
        cells_ok = sum(1 for c in cands for m in members if all(
            ok[x["key"]] for x in rows if x["candidate"] == c and f"{x['registration']}|{x['coil_shape']}|{m.split('|')[2]}" == m))
        cells_ok_rc = sum(1 for c in cands for rc in sorted({f"{x['registration']}|{x['coil_shape']}" for x in rows}) if all(
            ok[x["key"]] for x in rows if x["candidate"] == c and f"{x['registration']}|{x['coil_shape']}" == rc))
        cand_counts = {}
        for c in cands:
            cand_counts[c] = {
                "n_runs_all_45eV_files_eps_active_le_L": sum(1 for x in rows if x["candidate"] == c and ok[x["key"]]),
                "n_members_all_20_runs_eps_active_le_L": sum(1 for m in members if all(
                    ok[x["key"]] for x in rows if x["candidate"] == c
                    and f"{x['registration']}|{x['coil_shape']}|{m.split('|')[2]}" == m)),
            }
        ladder.append({
            "hypothetical_limit_mean_energy_eV": L, "hypothetical_limit_Te_eV": L / 1.5,
            "n_runs_all_45eV_files_eps_active_le_L": sum(ok.values()),
            "share_runs": share(sum(ok.values()), len(rows)),
            "n_officially_OOD_runs_with_all_45eV_files_eps_active_le_L": sum(1 for x in ood_rows if ok[x["key"]]),
            "n_candidate_member_cells_all_20_runs_eps_active_le_L": cells_ok, "n_candidate_member_cells": n_cells,
            "n_candidate_registration_coil_cells_all_20_runs_eps_active_le_L": cells_ok_rc,
            "n_candidate_registration_coil_cells": len(cands) * 6,
            "by_candidate": cand_counts,
            "by_point": {p: sum(1 for x in rows if x["point"] == p and ok[x["key"]]) for p in POINTS},
            "by_registration": {g: sum(1 for x in rows if x["registration"] == g and ok[x["key"]])
                                for g in sorted({x["registration"] for x in rows})},
            "per_file_runs_with_eps_active_gt_L": {f: sum(1 for x in rows if f in x["per"] and x["per"][f]["eps"] > L)
                                                   for f in fam45_all},
        })
    off_cells_45 = sum(1 for c in cands for m in members if cm[c]["members"][m]["n_OOD"] == 0)
    proxy45 = {x["key"] for x in rows if x["fam45_eps_max"] <= 45.0}
    official_in = {x["key"] for x in ind_rows}
    fam45_pairs = [(x["per"][f]["fout"] > tol, x["per"][f]["eps"] > 45.0) for x in rows for f in x["fam45"]]
    hypo = {
        "label": HYPO_LABEL,
        "what_is_counted": "For each hypothetical mean-energy limit L applied to the 21 files of the 45 eV family only (the "
                           "255 eV family is left as recorded), the number of runs in which max_mean_energy_active_eV <= L "
                           "for EVERY 45 eV-family file of the run, and the number of (candidate, global layer-1 member) cells "
                           "whose 20 runs (4 mandatory chemistry configs x 5 points) all satisfy that.",
        "definition_checked_in_code": "bridge_lib.jl chemistry_activity: for each reaction, over every saved frame of the "
                                      "averaging window and every cell, R = n_e n_target k_r(3/2 T_e) dz; "
                                      "max_mean_energy_active_eV = the highest 3/2 T_e at which R > 1e-12 x max(R) (the "
                                      "largest single (frame, cell) activity of that reaction); f_out = sum of R where 3/2 T_e "
                                      "> limit / sum of R.",
        "what_it_does_not_imply": [
            "It is not a scoring, not a verdict, not a status and not a proposal to change any limit. The v1 statuses are "
            "final and are read only from the scores file.",
            "f_out at any limit other than the recorded one (45 eV for this family) is NOT recorded. Only f_out(45 eV) and "
            "max_mean_energy_active_eV are in the records.",
            "max_mean_energy_active_eV is NOT the maximum mean energy with nonzero activity (verified in bridge_lib.jl): "
            "(frame, cell) points above it may carry 0 < R <= 1e-12 max(R). eps_active <= L therefore guarantees only "
            "f_out(L) <= N_above x 1e-12 x max(R) / sum(R) <= N_frame_cell x 1e-12, not f_out(L) <= 1e-12. "
            "Conversely eps_active > L implies f_out(L) > 0, not f_out(L) > 1e-12. It is neither a sufficient nor a "
            "necessary condition for the pre-registered f_out <= 1e-12 at L.",
            "Chemistry-evaluable under this proxy says nothing about the validity of the rate tables above 45 eV. The 45 eV "
            "cap is the pre-registered domain (T_e <= 30 eV) recorded in rate_validity.toml. Any extension would need "
            "independent published evidence and is the owner's decision; it would be a model change with its own reruns.",
            "Nothing is said about what status such runs would receive.",
        ],
        "frame_cell_count_for_the_bound": {
            "value": 100000,
            "derivation": "500 saved frames in the averaging window x 200 cells: HallThruster.jl v0.23.1 SimParams default "
                          "num_save = 1000 evenly spaced saves over the 2 ms run, each an instantaneous snapshot (the time "
                          "step is clipped to land on each save time), about 2.0 us apart (cases/p5_n2.json: cells 200, "
                          "duration_s 0.002, average_start_s 0.001); the saves with t >= 1 ms are the last 500; sol.grid "
                          "excludes the 2 ghost cells",
            "evidence_class": "inferred from the pinned HallThruster.jl source (not in this repository) - verify; consistent "
                              "with the recorded 100 final-10 % I_d samples per record (1000 saved frames)",
            "resulting_bound_on_f_out_at_L_when_eps_active_le_L": 100000 * tol,
        },
        "empirical_concordance_at_the_recorded_45eV_limit": {
            "n_run_file_pairs_45eV_family": len(fam45_pairs),
            "f_out_gt_tol_and_eps_active_gt_45": sum(1 for a, b in fam45_pairs if a and b),
            "f_out_gt_tol_and_eps_active_le_45": sum(1 for a, b in fam45_pairs if a and not b),
            "f_out_le_tol_and_eps_active_gt_45": sum(1 for a, b in fam45_pairs if not a and b),
            "f_out_le_tol_and_eps_active_le_45": sum(1 for a, b in fam45_pairs if not a and not b),
            "n_runs_proxy_evaluable_at_45": len(proxy45),
            "n_runs_officially_in_domain": len(official_in),
            "proxy_evaluable_subset_of_officially_in_domain": proxy45 <= official_in,
            "n_officially_in_domain_runs_not_proxy_evaluable_at_45": len(official_in - proxy45),
            "official_candidate_member_cells_with_zero_OOD_runs": off_cells_45,
            "note": "45 eV is the only limit at which both f_out and eps_active are recorded. There, no (run, file) pair had "
                    "f_out > 1e-12 with eps_active <= 45 eV, so the proxy counted no officially OOD run as evaluable. It "
                    "under-counts the officially in-domain runs: those whose sub-tolerance activity reaches above 45 eV. "
                    "This is an observation on these records at 45 eV only, not a guarantee at any other L.",
        },
        "ladder": ladder,
    }

    # ---- (5) Te_max_eV (peak of the TIME-AVERAGED T_e profile, bridge_lib.jl)
    def te_block(sel):
        return {"OOD": dist([x["Te_max_eV"] for x in sel if x["ood"]]),
                "in_domain": dist([x["Te_max_eV"] for x in sel if not x["ood"]])}
    te = {
        "definition": "Te_max_eV = maximum over cells of the time-averaged T_e profile (bridge_lib.jl: avg = "
                      "het.time_average(sol, average_start_s); fr = avg.frames[1]; maximum(fr.Tev)). f_out uses "
                      "instantaneous frames, so a run can be OOD with a time-averaged Te_max below 30 eV.",
        "overall": te_block(rows),
        "n_OOD_runs_with_time_averaged_mean_energy_1p5_Te_max_gt_45": sum(1 for x in ood_rows if 1.5 * x["Te_max_eV"] > 45.0),
        "n_runs_with_time_averaged_mean_energy_1p5_Te_max_gt_45": sum(1 for x in rows if 1.5 * x["Te_max_eV"] > 45.0),
        "ratio_45eV_family_max_eps_active_over_1p5_Te_max": {
            "OOD": dist([x["fam45_eps_max"] / (1.5 * x["Te_max_eV"]) for x in ood_rows]),
            "in_domain": dist([x["fam45_eps_max"] / (1.5 * x["Te_max_eV"]) for x in ind_rows])},
        "by_point": {p: te_block([x for x in rows if x["point"] == p]) for p in POINTS},
        "by_candidate": {c: te_block([x for x in rows if x["candidate"] == c]) for c in cands},
        "by_registration": {g: te_block([x for x in rows if x["registration"] == g])
                            for g in sorted({x["registration"] for x in rows})},
        "by_OOD_category": {c: dist([x["Te_max_eV"] for x in rows if x["category"] == c]) for c in CATEGORIES},
    }

    # ---- (6) official statuses / reasons vs OOD cause
    xt = collections.defaultdict(collections.Counter)
    for x in rows:
        for rd in READINGS:
            lab = x["status"][rd] + ("" if not x["reasons"][rd] else ":" + "+".join(x["reasons"][rd]))
            xt[x["category"]][lab] += 1
    xt_rr = {c: dict(sorted(xt[c].items())) for c in CATEGORIES if xt[c]}
    ind_hot = [x for x in ind_rows if x["fam45_eps_max"] > 45.0]
    ind_cold = [x for x in ind_rows if x["fam45_eps_max"] <= 45.0]

    def reason_counts(sel):
        c = collections.Counter()
        for x in sel:
            for rd in READINGS:
                c[x["status"][rd] + ("" if not x["reasons"][rd] else ":" + "+".join(x["reasons"][rd]))] += 1
        return dict(sorted(c.items()))
    sust_official = [x for x in ind_rows if "SUSTAINMENT" in x["reasons"]["A"]]
    o1_agree = all(("SUSTAINMENT" in x["reasons"][rd]) == x["o1_pattern"] for x in ind_rows for rd in READINGS)
    collapse = {
        "label": "Descriptive co-occurrence only. The O1 collapse PATTERN (mean of the final-10 % I_d samples < 0.05 "
                 "I_target AND >= 90 % of them < 0.10 I_target) is evaluated on the observables that the official scores "
                 "file records for every numerically valid run. For OOD runs it is NOT a status or a reason: the official "
                 "status is OUT_OF_DOMAIN (O2 precedence OUT_OF_DOMAIN before FAIL_VALIDATION) and no SUSTAINMENT reason "
                 "is assigned.",
        "check_pattern_equals_official_SUSTAINMENT_reason_on_in_domain_runs": o1_agree,
        "n_in_domain_runs_with_official_SUSTAINMENT_reason": len(sust_official),
        "n_OOD_runs_with_O1_collapse_pattern": sum(1 for x in ood_rows if x["o1_pattern"]),
        "n_OOD_runs_without_O1_collapse_pattern": sum(1 for x in ood_rows if not x["o1_pattern"]),
        "share_OOD_runs_with_pattern": share(sum(1 for x in ood_rows if x["o1_pattern"]), len(ood_rows)),
        "share_in_domain_runs_with_pattern": share(sum(1 for x in ind_rows if x["o1_pattern"]), len(ind_rows)),
        "by_OOD_category": {c: {"n_runs": sum(1 for x in rows if x["category"] == c),
                                "n_with_O1_collapse_pattern": sum(1 for x in rows if x["category"] == c and x["o1_pattern"])}
                            for c in CATEGORIES},
        "by_candidate_OOD_runs": {c: {"n_OOD": sum(1 for x in ood_rows if x["candidate"] == c),
                                      "n_OOD_with_O1_collapse_pattern": sum(
                                          1 for x in ood_rows if x["candidate"] == c and x["o1_pattern"])} for c in cands},
        "by_point_OOD_runs": {p: {"n_OOD": sum(1 for x in ood_rows if x["point"] == p),
                                  "n_OOD_with_O1_collapse_pattern": sum(
                                      1 for x in ood_rows if x["point"] == p and x["o1_pattern"])} for p in POINTS},
        "f_out_max_OOD_with_pattern": dist([x["f_out_max"] for x in ood_rows if x["o1_pattern"]]),
        "f_out_max_OOD_without_pattern": dist([x["f_out_max"] for x in ood_rows if not x["o1_pattern"]]),
        "final10_mean_over_target_OOD": dist([x["off"]["A"]["final10_mean_over_target"] for x in ood_rows]),
        "final10_mean_over_target_in_domain": dist([x["off"]["A"]["final10_mean_over_target"] for x in ind_rows]),
        "bridge_sustained_flag_diagnostic_only": {
            f"{grp}|sustained={v}": sum(1 for x in rows if x["ood"] == (grp == "OOD") and x["sustained_flag"] == v)
            for grp in ("OOD", "in_domain") for v in (True, False)},
    }
    status_xt = {
        "note": "Official statuses and reasons per run-reading, read verbatim from the scores file, cross-tabulated against "
                "the OOD cause category derived from the recorded per-reaction fields. OOD run-readings carry no reasons "
                "(O2 precedence).",
        "run_readings_by_category": xt_rr,
        "in_domain_runs_split_by_sub_tolerance_activity_above_45eV": {
            "note": "In-domain runs (f_out <= 1e-12 for every file) in which some 45 eV-family file still has "
                    "max_mean_energy_active_eV > 45 eV (activity above 45 eV that is > 1e-12 of its peak point but sums to "
                    "f_out <= 1e-12) versus runs with none.",
            "eps_active_gt_45": {"n_runs": len(ind_hot), "official_run_readings": reason_counts(ind_hot)},
            "eps_active_le_45": {"n_runs": len(ind_cold), "official_run_readings": reason_counts(ind_cold)},
        },
        "sustainment_collapse_co_occurrence": collapse,
    }

    return {
        "id": "p5_n2_v1_ood_attribution",
        "descriptive_non_gating": True,
        "statement": "Descriptive, non-gating attribution of the OUT_OF_DOMAIN statuses of the frozen P5-N2 v1 vacuum "
                     "campaign. The v1 outcome is permanent: all nine screening candidates INCONCLUSIVE / NOT ELIGIBLE, "
                     "credible set empty, gate 3 FAIL. No run is re-scored or re-labelled; no criterion, tolerance, validity "
                     "limit, chemistry or transport parameter is changed or proposed. OUT_OF_DOMAIN is not evidence "
                     "against a candidate (p5_n2_run_status_rule_v1).",
        "generated_by": "scripts/forensics/p5_n2_v1_ood_attribution.py",
        "inputs_sha256": dict(sorted({REL.get(k, k): v for k, v in inp["shas"].items()}.items())),
        "input_integrity_checks": dict(sorted(inp["checks"].items())),
        "evidence_classes": {
            "official statuses, reasons, member and candidate verdicts": "official pre-registered labels, read verbatim "
                                                                         "from the scores file",
            "f_out, max_mean_energy_active_eV, Te_max_eV, I_d observables": "model-derived (HallThruster.jl v0.23.1 run "
                                                                           "records of the frozen dataset)",
            "validity limits and bases": "as recorded in propellants/rate_validity.toml (not re-evaluated here)",
            "frame x cell count used for the proxy bound": "inferred from the pinned HallThruster.jl source - verify",
            "hypothetical ladder counts": "hypothetical counting under a stated proxy; not a scoring",
        },
        "f_out_tolerance": tol,
        "f_out_tolerance_source": REL["run_status_rule"] + " chemistry_trust_rule.f_out_tolerance",
        "reconciliation": recon,
        "per_file": per_file,
        "f_out_magnitude": magnitude,
        "co_occurrence": cooc,
        "breakdown": breakdown,
        "hypothetical_limit_ladder_45eV_family": hypo,
        "Te_max": te,
        "official_status_crosstab": status_xt,
    }


def parse_report_ood_by_candidate(text):
    """OUT_OF_DOMAIN run-reading counts per candidate from the official report's 'vacuum by candidate' table."""
    out, on = {}, False
    for line in text.splitlines():
        if line.startswith("| vacuum by candidate"):
            hdr = [h.strip() for h in line.strip("|").split("|")]
            col = hdr.index("OUT_OF_DOMAIN")
            on = True
            continue
        if on:
            if not line.startswith("|"):
                break
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells[0].startswith("sgb-"):
                out[cells[0]] = int(cells[col])
    return out


# ------------------------------------------------------------------------------------------------------------ markdown
def g(v, fmt="{:.3g}"):
    return "—" if v is None else fmt.format(v)


def esc(s):
    """Escape the member-key pipes for a Markdown table cell."""
    return s.replace("|", " \\| ")


def pct(a, b):
    return "—" if not b else f"{100 * a / b:.1f} %"


def render_md(d):
    L = []
    rc, cooc, pf, bd = d["reconciliation"], d["co_occurrence"], d["per_file"], d["breakdown"]
    hy, te, sx = d["hypothetical_limit_ladder_45eV_family"], d["Te_max"], d["official_status_crosstab"]
    tol = d["f_out_tolerance"]
    fam45 = cooc["limit_families"]["45 eV"]
    L += ["# P5-N2 v1 vacuum campaign: OUT_OF_DOMAIN attribution (descriptive, non-gating)", "",
          f"Generated by `{d['generated_by']}`. Every number below is in `ood_attribution.json`, produced by the same run of "
          "that script from the frozen, release-checked inputs.", "",
          "**Scope and rules.** " + d["statement"], "",
          "**Evidence classes.** Official statuses, reasons and verdicts are read verbatim from "
          "`validation/p5_n2_campaign_v1_vacuum_scores.json`. f_out, max_mean_energy_active_eV, Te_max_eV and the I_d "
          "observables are model-derived (HallThruster.jl v0.23.1 records in the frozen dataset). Validity limits are as "
          "recorded in `propellants/rate_validity.toml`. The frame x cell count used in section 4 is inferred from the pinned "
          "HallThruster.jl source (verify). Section 4 counts are hypothetical.", "",
          "## 0. Reconciliation with the official result", "",
          f"- Records {rc['n_records']}; run-readings in the scores file {rc['n_run_readings_in_scores_file']}; official "
          f"vacuum status counts {rc['official_status_counts_vacuum']}.",
          f"- OUT_OF_DOMAIN: **{rc['n_OOD_runs']} runs = {rc['n_OOD_run_readings']} run-readings**; in-domain runs "
          f"{rc['n_in_domain_runs']}. OOD is reading-independent: {rc['OOD_status_reading_independent']} "
          f"({rc['n_runs_with_reading_dependent_OOD']} runs differ between readings A and B).",
          f"- Per-candidate OOD run-readings equal the official report and the scores file: "
          f"{rc['per_candidate_matches_report']}.",
          f"- Input consistency (not a re-scoring): the scorer's OOD predicate evaluated on the raw fields agrees with the "
          f"official label in every run: {rc['input_consistency_OOD_predicate_on_raw_fields_agrees_with_official_label']} "
          f"({rc['input_consistency_n_disagreements']} disagreements). Unresolved tables in OOD runs: "
          f"{rc['n_OOD_runs_with_unresolved_tables']}. Release-chain integrity checks: "
          f"{sum(d['input_integrity_checks'].values())}/{len(d['input_integrity_checks'])} pass.", "",
          "| candidate | official OOD run-readings (report) | (scores file) | OOD runs |", "|---|---|---|---|"]
    for c, v in rc["per_candidate"].items():
        L.append(f"| {c} | {v['official_OOD_run_readings_from_report']} | {v['official_OOD_run_readings_from_scores_file']} "
                 f"| {v['OOD_runs']} |")
    L += ["", "## Definitions (checked against the code)", "",
          "- `extrapolated_fraction` (f_out, per reaction; `bridge_lib.jl` `chemistry_activity`): over every saved frame of "
          "the averaging window (t >= average_start_s = 1 ms) and every cell, activity R = n_e n_target k_r(3/2 T_e) dz; "
          "f_out = (sum of R where 3/2 T_e > limit) / (sum of R). A run is OUT_OF_DOMAIN when any reaction has "
          f"f_out > {tol:g} or a table is unresolved (`scripts/score_p5_n2_campaign.py`, tolerance from "
          "`prereg/p5_n2_run_status_rule_v1.json`).",
          "- `max_mean_energy_active_eV` (eps_active): the highest instantaneous 3/2 T_e at which R > 1e-12 x max(R), where "
          "max(R) is the largest single (frame, cell) activity of that reaction. It is **not** the highest mean energy with "
          "nonzero activity.",
          "- `Te_max_eV`: peak of the **time-averaged** T_e profile (`fr = avg.frames[1]`), not an instantaneous value.",
          "", "## 1. Per rate file", "",
          f"Files in the four mandatory configs: {len(pf)} ({len(fam45)} capped at 45 eV, "
          f"{len(cooc['limit_families']['255 eV'])} capped at 255 eV, unresolved: none). Distributions: min / median / p90 / "
          "max (type-7 quantiles). eps_active is shown against the file's limit.", "",
          "| file | limit eV | runs using | runs f_out > tol | f_out (beyond runs) min / median / p90 / max | "
          "eps_active all runs min / median / p90 / max [eV] | runs eps_active > limit | sole cause |",
          "|---|---|---|---|---|---|---|---|"]
    for f, v in sorted(pf.items(), key=lambda kv: (kv[1]["limit_mean_energy_eV"] or 0, -kv[1]["n_runs_f_out_gt_tol"], kv[0])):
        fo, ep = v["f_out_over_runs_beyond"], v["max_mean_energy_active_eV_over_all_runs_using"]
        fo_s = "—" if fo["n"] == 0 else f"{fo['min']:.2e} / {fo['median']:.2e} / {fo['p90']:.2e} / {fo['max']:.2e}"
        L.append(f"| {f} | {v['limit_mean_energy_eV']:g} | {v['n_runs_using']} | {v['n_runs_f_out_gt_tol']} | {fo_s} | "
                 f"{ep['min']:.1f} / {ep['median']:.1f} / {ep['p90']:.1f} / {ep['max']:.1f} | "
                 f"{v['n_runs_max_mean_energy_active_gt_limit']} | {v['n_runs_sole_cause']} |")
    mg = d["f_out_magnitude"]
    n255_beyond = sum(pf[f]["n_runs_f_out_gt_tol"] for f in cooc["limit_families"]["255 eV"])
    L += ["", f"Runs with a 255 eV-capped file at f_out > tol: {n255_beyond}. The highest eps_active of any 255 eV-capped file "
          f"is {max(pf[f]['max_mean_energy_active_eV_over_all_runs_using']['max'] for f in cooc['limit_families']['255 eV']):.1f} eV.",
          "", f"Size of the exceedance. f_out_max (largest f_out of the run) over the {rc['n_OOD_runs']} OOD runs: "
          f"min {mg['f_out_max_OOD']['min']:.2e}, median {mg['f_out_max_OOD']['median']:.2e}, p90 "
          f"{mg['f_out_max_OOD']['p90']:.2e}, max {mg['f_out_max_OOD']['max']:.2e}. OOD runs below 1e-11: "
          f"{mg['n_OOD_runs_f_out_max_lt_1e-11']}; below 1e-9: {mg['n_OOD_runs_f_out_max_lt_1e-9']}; below 1e-6: "
          f"{mg['n_OOD_runs_f_out_max_lt_1e-6']}; at or above 1e-2: {mg['n_OOD_runs_f_out_max_ge_1e-2']}. In-domain runs: "
          f"{mg['n_in_domain_runs_f_out_max_exactly_zero']} with f_out_max exactly 0 and "
          f"{mg['n_in_domain_runs_f_out_max_in_(0,tol]']} in (0, 1e-12] (max "
          f"{mg['f_out_max_in_domain']['max']:.2e}). " + mg["note"], "",
          "| f_out_max decade | OOD runs | in-domain runs |", "|---|---|---|"]
    for k in sorted(set(mg["f_out_max_OOD_decade_histogram"]) | set(mg["f_out_max_in_domain_decade_histogram"]), key=float):
        L.append(f"| {k} | {mg['f_out_max_OOD_decade_histogram'].get(k, 0)} | "
                 f"{mg['f_out_max_in_domain_decade_histogram'].get(k, 0)} |")
    nest = cooc["nesting"]
    L += ["", "## 2. Co-occurrence: one family fires together", "",
          f"- Every OOD run is caused by files of the **45 eV-capped family** only: {cooc['n_OOD_runs_beyond_set_within_45eV_family']}"
          f"/{cooc['n_OOD_runs']} OOD runs have their beyond-limit set inside that family; runs with any other file beyond "
          f"its limit: {cooc['n_runs_any_file_outside_45eV_family_beyond']}; runs with an unresolved table: "
          f"{cooc['n_runs_with_unresolved_table']}.",
          f"- `dissociation_N2.dat` is beyond its limit in {cooc['n_OOD_runs_with_dissociation_beyond']}/{cooc['n_OOD_runs']} "
          f"OOD runs and has the largest f_out in {cooc['n_OOD_runs_dissociation_has_largest_f_out']} of them.",
          f"- Beyond-limit set exactly equal to the whole 45 eV family (21 files): "
          f"**{cooc['n_OOD_runs_beyond_set_exactly_full_45eV_family']}** OOD runs. Sole-cause runs: "
          + ", ".join(f"`{f}` {n}" for f, n in cooc["sole_cause_counts"].items() if n) + "; every other file: 0.",
          f"- Nesting: of {nest['n_file_pairs']} file pairs in the family, {len(nest['non_nested_pairs'])} are not nested ("
          + "; ".join(f"`{p['file_a']}` / `{p['file_b']}` {p['n_runs_a_beyond_b_not']} vs {p['n_runs_b_beyond_a_not']} runs"
                      for p in nest["non_nested_pairs"])
          + f"), and {nest['n_OOD_runs_breaking_the_majority_nesting_of_some_pair']} OOD runs break the majority order of "
          f"some pair. OOD runs with an electronic or rotational file beyond but not dissociation: "
          f"{cooc['n_OOD_runs_electronic_or_rotational_beyond_without_dissociation_beyond']}. OOD runs with a vibrational "
          f"file beyond without every electronic and rotational file beyond: "
          f"{cooc['n_OOD_runs_vibrational_beyond_without_all_electronic_and_rotational_beyond']}. The beyond-limit sets "
          "are close to one chain: dissociation first, then electronic and rotational (in a near-fixed order), then "
          "vibrational.", "",
          "| OOD cause category | OOD runs | definition |", "|---|---|---|"]
    for c, n in cooc["category_counts_OOD_runs"].items():
        L.append(f"| {c} | {n} | {cooc['category_definitions'][c]} |")
    L += ["", "Sub-family pattern (number of files beyond, D = dissociation of 1, E = electronic of 8, V = vibrational of 10, "
          "R = rotational of 2):", "", "| pattern | OOD runs |", "|---|---|"]
    for p, n in cooc["subfamily_pattern_counts"].items():
        L.append(f"| {p} | {n} |")
    L += ["", "## 3. Where OOD occurs", "", "| factor | level | runs | OOD runs | share | FULL | D only | no vib | partial vib | "
          "median f_out_max (OOD) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for fac in ("candidate", "point", "chemistry", "registration", "coil_shape"):
        for lv, v in bd[fac].items():
            oc = v["OOD_categories"]
            L.append(f"| {fac} | {lv} | {v['n_runs']} | {v['n_OOD_runs']} | {pct(v['n_OOD_runs'], v['n_runs'])} | "
                     f"{oc['FULL_45EV_FAMILY']} | {oc['DISSOCIATION_ONLY']} | {oc['NO_VIBRATIONAL']} | "
                     f"{oc['PARTIAL_VIBRATIONAL']} | {g(v['f_out_max_over_OOD_runs'].get('median'), '{:.2e}')} |")
    L += ["", "**Reading.** " + bd["reading_independence"]["statement"] + " Runs whose OOD status differs between readings: "
          f"{bd['reading_independence']['n_runs_reading_dependent']}.", "",
          "Global layer-1 member (registration | coil | reading), all candidates, 180 runs each:", "",
          "| member | OOD runs | share |", "|---|---|---|"]
    for m, v in bd["global_layer1_member"].items():
        L.append(f"| {esc(m)} | {v['n_OOD_runs']} | {pct(v['n_OOD_runs'], v['n_runs'])} |")
    rcs = sorted({m.rsplit("|", 1)[0] for m in bd["global_layer1_member"]})
    L += ["", "OOD runs out of 20 per (candidate, member); readings A and B are identical, so each cell stands for both. "
          "The official member verdict (A / B) is shown after the slash.", "",
          "| candidate | " + " | ".join(esc(rc_) for rc_ in rcs) + " |",
          "|---|" + "---|" * len(rcs)]
    for c, v in bd["candidate_x_member"].items():
        cells = []
        for rc_ in rcs:
            a, b = v["members"][rc_ + "|A"], v["members"][rc_ + "|B"]
            ab = a["official_member_verdict"] if a["official_member_verdict"] == b["official_member_verdict"] else \
                f"{a['official_member_verdict']}/{b['official_member_verdict']}"
            cells.append(f"{a['n_OOD']}/20 ({ab})")
        L.append(f"| {c} | " + " | ".join(cells) + " |")
    cc = bd["controlled_contrasts"]["by_factor"]
    L += ["", "Controlled single-factor contrasts (groups identical in all other factors; share of groups whose OOD status "
          "changes when only this factor changes): " + "; ".join(
              f"{k} {v['n_groups_with_mixed_OOD_status']}/{v['n_groups']} ({pct(v['n_groups_with_mixed_OOD_status'], v['n_groups'])})"
              for k, v in cc.items()) + ". Descriptive within the model; not a physical attribution.", "",
          "Official member verdict against the number of OOD runs in the member: " + "; ".join(
              f"{k}: {dict(v)}" for k, v in bd["official_member_verdict_vs_OOD_count"].items()) + ".", ""]
    ec = hy["empirical_concordance_at_the_recorded_45eV_limit"]
    fc = hy["frame_cell_count_for_the_bound"]
    L += ["## 4. " + HYPO_LABEL, "",
          "What is counted: " + hy["what_is_counted"], "", "What it does **not** imply:", ""]
    L += [f"- {s}" for s in hy["what_it_does_not_imply"]]
    L += [f"- Bound used above: N_frame_cell = {fc['value']}, so eps_active <= L only bounds f_out(L) <= "
          f"{fc['resulting_bound_on_f_out_at_L_when_eps_active_le_L']:.0e}. Derivation: {fc['derivation']}. Evidence class: "
          f"{fc['evidence_class']}.", "",
          f"Empirical check at the recorded 45 eV limit ({ec['n_run_file_pairs_45eV_family']} run x file pairs): f_out > tol "
          f"with eps_active <= 45: **{ec['f_out_gt_tol_and_eps_active_le_45']}**; f_out <= tol with eps_active > 45: "
          f"{ec['f_out_le_tol_and_eps_active_gt_45']}; both beyond: {ec['f_out_gt_tol_and_eps_active_gt_45']}. At run level the "
          f"proxy counts {ec['n_runs_proxy_evaluable_at_45']} runs against {ec['n_runs_officially_in_domain']} officially "
          f"in-domain (proxy set inside the official set: {ec['proxy_evaluable_subset_of_officially_in_domain']}). "
          + ec["note"], "",
          "| hypothetical L [eV] (T_e) | runs with every 45 eV-family eps_active <= L | of which officially OOD | "
          "(candidate, member) cells with all 20 runs <= L (of 108) | N1 | N2 | N3 | N4 | N5 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in hy["ladder"]:
        bp = r["by_point"]
        L.append(f"| {r['hypothetical_limit_mean_energy_eV']:g} ({r['hypothetical_limit_Te_eV']:g}) | "
                 f"{r['n_runs_all_45eV_files_eps_active_le_L']} ({pct(r['n_runs_all_45eV_files_eps_active_le_L'], 1080)}) | "
                 f"{r['n_officially_OOD_runs_with_all_45eV_files_eps_active_le_L']} | "
                 f"{r['n_candidate_member_cells_all_20_runs_eps_active_le_L']} | "
                 + " | ".join(str(bp[p]) for p in POINTS) + " |")
    L += ["", "Per candidate at each hypothetical L: runs (of 120) / members with all 20 runs (of 12).", "",
          "| candidate | " + " | ".join(f"{r['hypothetical_limit_mean_energy_eV']:g}" for r in hy["ladder"]) + " |",
          "|---|" + "---|" * len(hy["ladder"])]
    for c in bd["candidate_x_member"]:
        L.append(f"| {c} | " + " | ".join(
            f"{r['by_candidate'][c]['n_runs_all_45eV_files_eps_active_le_L']} / "
            f"{r['by_candidate'][c]['n_members_all_20_runs_eps_active_le_L']}" for r in hy["ladder"]) + " |")
    L += ["", f"Official count at the recorded limit, for reference: (candidate, member) cells with zero OOD runs = "
          f"{ec['official_candidate_member_cells_with_zero_OOD_runs']} of 108.", "",
          "## 5. Te_max_eV (time-averaged peak) for OOD and in-domain runs", "",
          f"- OOD runs whose time-averaged peak mean energy 1.5 Te_max exceeds 45 eV: "
          f"**{te['n_OOD_runs_with_time_averaged_mean_energy_1p5_Te_max_gt_45']}**. Since f_out > 0 needs 3/2 T_e > 45 eV in "
          "some saved frame and cell, every recorded exceedance is transient: it is present in instantaneous frames and "
          "absent from the window mean.",
          f"- Ratio of the family's highest eps_active to 1.5 Te_max: OOD median "
          f"{te['ratio_45eV_family_max_eps_active_over_1p5_Te_max']['OOD']['median']:.2f} (max "
          f"{te['ratio_45eV_family_max_eps_active_over_1p5_Te_max']['OOD']['max']:.2f}); in-domain median "
          f"{te['ratio_45eV_family_max_eps_active_over_1p5_Te_max']['in_domain']['median']:.2f}.", "",
          "| group | OOD: n / min / median / p90 / max [eV] | in-domain: n / min / median / p90 / max [eV] |", "|---|---|---|"]

    def tl(b):
        return "—" if b["n"] == 0 else f"{b['n']} / {b['min']:.1f} / {b['median']:.1f} / {b['p90']:.1f} / {b['max']:.1f}"
    L.append(f"| all | {tl(te['overall']['OOD'])} | {tl(te['overall']['in_domain'])} |")
    for p, b in te["by_point"].items():
        L.append(f"| {p} | {tl(b['OOD'])} | {tl(b['in_domain'])} |")
    for c, b in te["by_candidate"].items():
        L.append(f"| {c} | {tl(b['OOD'])} | {tl(b['in_domain'])} |")
    for c, b in te["by_registration"].items():
        L.append(f"| {c} | {tl(b['OOD'])} | {tl(b['in_domain'])} |")
    col = sx["sustainment_collapse_co_occurrence"]
    L += ["", "## 6. Official statuses and reasons against the OOD cause", "", sx["note"], "",
          "| cause category | official run-readings (status:reasons) |", "|---|---|"]
    for c, v in sx["run_readings_by_category"].items():
        L.append(f"| {c} | " + ", ".join(f"{k} {n}" for k, n in v.items()) + " |")
    hs = sx["in_domain_runs_split_by_sub_tolerance_activity_above_45eV"]
    L += ["", hs["note"], "",
          f"- eps_active > 45 eV in some family file: {hs['eps_active_gt_45']['n_runs']} runs; "
          + ", ".join(f"{k} {n}" for k, n in hs["eps_active_gt_45"]["official_run_readings"].items()),
          f"- eps_active <= 45 eV in every family file: {hs['eps_active_le_45']['n_runs']} runs; "
          + ", ".join(f"{k} {n}" for k, n in hs["eps_active_le_45"]["official_run_readings"].items()), "",
          "**Sustainment collapse and OOD.** " + col["label"], "",
          f"- Check: on in-domain runs the pattern equals the official SUSTAINMENT reason in every run-reading: "
          f"{col['check_pattern_equals_official_SUSTAINMENT_reason_on_in_domain_runs']} "
          f"({col['n_in_domain_runs_with_official_SUSTAINMENT_reason']} in-domain runs carry SUSTAINMENT).",
          f"- OOD runs showing the O1 collapse pattern: **{col['n_OOD_runs_with_O1_collapse_pattern']}** of "
          f"{col['n_OOD_runs_with_O1_collapse_pattern'] + col['n_OOD_runs_without_O1_collapse_pattern']} "
          f"({g(col['share_OOD_runs_with_pattern'] * 100, '{:.1f}')} %), against "
          f"{g(col['share_in_domain_runs_with_pattern'] * 100, '{:.1f}')} % of in-domain runs. These runs are OUT_OF_DOMAIN, "
          "not FAIL_VALIDATION: a collapse pattern in an OOD run is not scored.",
          "- By cause category (runs with pattern / runs): " + "; ".join(
              f"{c} {v['n_with_O1_collapse_pattern']}/{v['n_runs']}" for c, v in col["by_OOD_category"].items() if v["n_runs"]) + ".",
          "- By candidate (OOD runs with pattern / OOD runs): " + "; ".join(
              f"{c} {v['n_OOD_with_O1_collapse_pattern']}/{v['n_OOD']}" for c, v in col["by_candidate_OOD_runs"].items()) + ".",
          "- By point: " + "; ".join(f"{p} {v['n_OOD_with_O1_collapse_pattern']}/{v['n_OOD']}"
                                    for p, v in col["by_point_OOD_runs"].items()) + ".",
          f"- f_out_max in OOD runs with the pattern: median {g(col['f_out_max_OOD_with_pattern'].get('median'), '{:.2e}')}; "
          f"without: median {g(col['f_out_max_OOD_without_pattern'].get('median'), '{:.2e}')}.",
          "- Bridge `sustained` flag (diagnostic only, not the O1 definition): " + ", ".join(
              f"{k} {n}" for k, n in col["bridge_sustained_flag_diagnostic_only"].items()) + ".", "",
          "## 7. What this establishes and what it does not", "",
          "Established from the recorded fields and the code definitions (numbers from the sections above):",
          f"1. OUT_OF_DOMAIN in v1 comes only from the {len(fam45)} tables capped at 45 eV (the pre-registered T_e <= 30 eV "
          f"domain): {cooc['n_OOD_runs_beyond_set_within_45eV_family']}/{cooc['n_OOD_runs']} OOD runs. "
          f"`dissociation_N2.dat` is beyond its limit in {cooc['n_OOD_runs_with_dissociation_beyond']} of them and is the "
          f"sole cause in {cooc['sole_cause_counts'].get('dissociation_N2.dat', 0)}. Runs with a 255 eV-capped table beyond: "
          f"{cooc['n_runs_any_255eV_file_beyond']}; with an unresolved table: {cooc['n_runs_with_unresolved_table']}.",
          f"2. The family fires together: {cooc['n_OOD_runs_beyond_set_exactly_full_45eV_family']} OOD runs have the whole "
          f"family beyond; the other {cooc['n_OOD_runs'] - cooc['n_OOD_runs_beyond_set_exactly_full_45eV_family']} are "
          "dissociation-led subsets of a near-nested chain (section 2).",
          f"3. All exceedances are transient: {te['n_OOD_runs_with_time_averaged_mean_energy_1p5_Te_max_gt_45']} OOD runs "
          "have a time-averaged peak mean energy above 45 eV.",
          f"4. OOD is reading-independent ({rc['n_runs_with_reading_dependent_OOD']} reading-dependent runs). Controlled "
          "contrasts, largest first: " + ", ".join(
              f"{k} {pct(v['n_groups_with_mixed_OOD_status'], v['n_groups'])}"
              for k, v in sorted(cc.items(), key=lambda kv: (-kv[1]["n_groups_with_mixed_OOD_status"] / kv[1]["n_groups"],
                                                             kv[0])))
          + ". These are contrasts inside the model, not physical attributions.",
          f"5. The size of the exceedance spans from {mg['f_out_max_OOD']['min']:.2e} to {mg['f_out_max_OOD']['max']:.2e}; "
          f"{mg['n_OOD_runs_f_out_max_lt_1e-9']} of {cooc['n_OOD_runs']} OOD runs have f_out_max below 1e-9.",
          f"6. {col['n_OOD_runs_with_O1_collapse_pattern']} OOD runs also show the O1 collapse pattern; their official "
          "status stays OUT_OF_DOMAIN.", "",
          "Not established:",
          "- Anything about f_out at limits other than 45 eV. The section 4 ladder is a proxy count with the stated caveats.",
          "- Whether any table is valid above 45 eV. That needs independent published evidence and is the owner's decision.",
          "- Any status, verdict or admission consequence. The v1 result stands as recorded.", "",
          "Authoring-time note (git, not re-run by this script): `hallthruster_bridge/bridge_lib.jl` and "
          "`propellants/rate_validity.toml` are unchanged between the campaign driver commit 79d4e12 and the base commit "
          "of this analysis; their sha256 are recorded in the JSON.", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    d = analyse(load_inputs())
    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "ood_attribution.json"), "w") as f:
        json.dump(d, f, indent=1, sort_keys=True, allow_nan=False)
        f.write("\n")
    with open(os.path.join(a.out_dir, "OOD_ATTRIBUTION.md"), "w") as f:
        f.write(render_md(d))
    print(f"wrote {a.out_dir}/ood_attribution.json and OOD_ATTRIBUTION.md: {d['reconciliation']['n_OOD_runs']} OOD runs, "
          f"{d['reconciliation']['n_OOD_run_readings']} OOD run-readings")


if __name__ == "__main__":
    main()

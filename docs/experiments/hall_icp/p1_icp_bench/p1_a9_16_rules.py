"""P1 ICP bench - owner-decision rules applied in A9.16 step 1 (lane P1 ICP BENCH). Pure, deterministic, stdlib only.

Registration slots and fail-closed checks for the owner decisions of 2026-10-01 that are not single-record reducer
rules (those live in p1_reducer.py). Every number the owner deferred to a later registration is a REGISTERED INPUT
here - never a default, never invented (CLAUDE.md rules 3, 6, 10; docs/EVIDENCE.md):

  A9.8  P1-IT-52  stage operating domains [min, max] under a unique domain_id, frozen before the stage's first record
                  (check_operating_domains / domain_freeze_reasons) - outside -> OUT_OF_DOMAIN, never a FAIL
  A9.8  P1Q-11    RF-ON / RF-OFF pressure-match tolerance derived from the installed-gauge repeatability of P1-S2 / P1-S3,
                  frozen before the first P1-S4 matched pair, immutable within the campaign
                  (check_pressure_match_registration)
  A9.8  P1Q-04    UBQ-06 abort / derate (validated continuous-use limit - 50 K) on ALL P1 operation incl. non-scoring
                  (thermal_abort_rows)
  A9.10 P1Q-02    start-attempt limits registered before P1-S6; never increased after a failed ignition
                  (check_start_limit_revisions; the single-registration bounds are p1_reducer.check_start_attempt_limits)
  A9.10 P1Q-06    factor F6: magnet OFF first, then the registered setting(s) (magnet_order_reasons)
  A9.10 P1Q-07    I_d,max,H1,Ar frozen before P1-S7 (freeze_before_stage_reasons)
  A9.11 P1Q-01    stable-region criteria frozen and HASHED before the first P1-S5 dwell, derived from P1-S2..S4 evidence
                  (canonical_sha256, check_stable_criteria_registration)
  A9.14 P1Q-17    triggered-only 700 V DC / 60 s reverification (reduce_dwv_reverification)
  A9.14 OD5       baseline start sequence ICP first, Hall second, max 1 + 2 retries (check_baseline_start_sequence)
  A9.14 ICPQ-08   B(z) mapping energized only with demonstrated gaussmeter RF immunity, else after RF-off at a
                  preregistered characterized delay (check_bz_mapping)
  A9.14 F6-OQ-03  multi-geometry bench matrix of modular ICP variants, each geometry measured; no surrogate between
                  geometries before separate predictive validation (geometry_matrix_report)

Nothing here produces PASS. Decision files (immutable; cite by path + json sha256 + question id):
docs/decisions/OD_2026_10_01_A9_8_s1_p1_start_owner_decisions.json, ..._A9_10_s3_p1_later_stage_owner_decisions.json,
..._A9_11_s4_p2_owner_decisions.json, ..._A9_14_s7_s10_owner_decisions.json.
"""
import datetime
import hashlib
import json

A98 = "docs/decisions/OD_2026_10_01_A9_8_s1_p1_start_owner_decisions.json"
A910 = "docs/decisions/OD_2026_10_01_A9_10_s3_p1_later_stage_owner_decisions.json"
A911 = "docs/decisions/OD_2026_10_01_A9_11_s4_p2_owner_decisions.json"
A914 = "docs/decisions/OD_2026_10_01_A9_14_s7_s10_owner_decisions.json"

DOMAIN_REGISTRATION_KEYS = ("domain_id", "frozen_utc", "basis")
PRESSURE_MATCH_REQUIRED = ("criteria_id", "p_chamber_rel_tol", "gauge_id", "derived_from_record_ids",
                           "repeatability_basis", "frozen_utc")
PRESSURE_MATCH_EVIDENCE_STAGES = ("P1-S2", "P1-S3")
STABLE_EVIDENCE_STAGES = ("P1-S2", "P1-S3", "P1-S4")
THERMAL_ABORT_MARGIN_K = 50.0               # owner UBQ-06 rule (A9.1), applied to all P1 operation by A9.8 P1Q-04
REVERIFICATION_V_DC = 700.0                 # owner development acceptance level (A9.14 P1Q-17), not an ECSS clause
REVERIFICATION_DURATION_S = 60.0
REVERIFICATION_TRIGGERS = ("AFTER_REPAIR", "INSULATION_PATH_MODIFICATION", "SUSPECTED_FAULT",
                           "DEFINED_REQUALIFICATION_TRIGGER")
REVERIFICATION_LEVEL_BASIS = "OWNER_DEVELOPMENT_ACCEPTANCE_LEVEL_A9_14_P1Q-17"
REVERIFICATION_REQUIRED = ("record_id", "path_id", "trigger", "trigger_record_id", "level_basis", "V_test_V",
                           "duration_s", "current_limited", "pressure_gas_condition", "sensitive_electronics_handling",
                           "leakage_A", "breakdown_or_flashover", "tracking_or_disruptive_discharge", "protective_trip",
                           "leakage_acceptance", "test_utc")
OD5_EVENTS = ("GAS_PLENUM_FEED_ESTABLISHED", "H1_MAGNET_STATE_SET", "ICP_IGNITED_STABILIZED",
              "ELECTRON_SOURCE_CONDITION_VERIFIED", "HALL_V_D_APPLIED", "SUSTAINED_HALL_DISCHARGE_VERIFIED")
OD5_MAX_ATTEMPTS = 3                        # one initial attempt + two retries (A9.14 OD5)
OD5_VARIANTS = ("ICP_NEUTRALIZER_BASELINE", "C1_SELECTED_VARIANT")
BZ_RF_STATES = ("ENERGIZED", "RF_OFF")
BZ_DELAY_REQUIRED = ("registration_id", "delay_s", "delay_tolerance_s", "decay_characterization_id", "frozen_utc")
GEOMETRY_REQUIRED = ("geometry_id", "drawing_id", "revision", "within_drawing_envelope")


class RuleError(ValueError):
    """A registration or record that violates an owner rule of A9.8 / A9.10 / A9.11 / A9.14 (refused, never repaired)."""


def parse_utc(ts, where):
    if not isinstance(ts, str) or not ts.strip():
        raise RuleError("%s: an ISO-8601 timestamp with a UTC offset is required, got %r" % (where, ts))
    t = ts.strip()
    if t.endswith(("Z", "z")):
        t = t[:-1] + "+00:00"
    try:
        d = datetime.datetime.fromisoformat(t)
    except ValueError:
        raise RuleError("%s: %r is not ISO-8601" % (where, ts))
    if d.tzinfo is None or d.utcoffset() is None:
        raise RuleError("%s: %r has no UTC offset" % (where, ts))
    return d.astimezone(datetime.timezone.utc)


def _str(x):
    return isinstance(x, str) and bool(x.strip())


def _num(x, where, positive=False):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x or x in (float("inf"), float("-inf")):
        raise RuleError("%s must be a finite number, got %r" % (where, x))
    if positive and not x > 0:
        raise RuleError("%s must be > 0, got %r" % (where, x))
    return float(x)


def canonical_sha256(obj, drop=()):
    """sha256 of the canonical JSON (sorted keys, no whitespace, UTF-8) of obj without the keys in drop."""
    o = {k: v for k, v in obj.items() if k not in drop}
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _first_ts(records, stages):
    ts = [parse_utc(r["timestamp_utc"], "record %r" % r.get("record_id")) for r in records
          if isinstance(r, dict) and r.get("stage_id") in stages and isinstance(r.get("timestamp_utc"), str)]
    return min(ts) if ts else None


# ------------------------------------------------------------------ A9.8 P1-IT-52 stage operating domains
def check_operating_domains(doms, factors):
    """Each registered stage domain carries a unique domain_id, its frozen_utc and its basis (procured / calibrated
    hardware capability, P1-G0 safety limits, preregistered run matrix) plus [min, max] factors. Raises RuleError."""
    if not isinstance(doms, dict):
        raise RuleError("operating_domains must be an object {stage_id: domain}")
    seen = {}
    for st, d in doms.items():
        if not isinstance(d, dict):
            raise RuleError("operating domain of %r must be an object" % st)
        for k in DOMAIN_REGISTRATION_KEYS:
            if not _str(d.get(k)):
                raise RuleError("operating domain of %r needs %s (owner A9.8 P1-IT-52: frozen before the stage's first "
                                "record, from the real hardware; no fabricated limits)" % (st, k))
        parse_utc(d["frozen_utc"], "operating domain of %r frozen_utc" % st)
        if d["domain_id"] in seen:
            raise RuleError("domain_id %r registered for stages %r and %r: each stage domain has a unique domain_id "
                            "(owner A9.8 P1-IT-52)" % (d["domain_id"], seen[d["domain_id"]], st))
        seen[d["domain_id"]] = st
        for f, v in d.items():
            if f in DOMAIN_REGISTRATION_KEYS:
                continue
            if f not in factors:
                raise RuleError("operating domain of %r: unknown factor %r (allowed %s)" % (st, f, sorted(factors)))
            if (not isinstance(v, list) or len(v) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float))
                                                               for x in v) or v[0] > v[1]):
                raise RuleError("operating domain of %r: factor %r must be [min, max]" % (st, f))
    return True


def domain_freeze_reasons(doms, records):
    """{record_id: [reason]} for records of a stage whose domain was frozen at / after the stage's first record."""
    out = {}
    for st, d in doms.items():
        first = _first_ts(records, (st,))
        if first is None:
            continue
        if parse_utc(d["frozen_utc"], "domain frozen_utc") >= first:
            for r in records:
                if isinstance(r, dict) and r.get("stage_id") == st:
                    out.setdefault(r["record_id"], []).append(
                        "operating domain %r of stage %s frozen at %s, not before the stage's first record (owner A9.8 "
                        "P1-IT-52): OUT_OF_DOMAIN, never a failure" % (d["domain_id"], st, d["frozen_utc"]))
    return out


# ------------------------------------------------------------------ A9.8 P1Q-11 pressure-match tolerance
def check_pressure_match_registration(match, records, pair_ids):
    """Returns a list of reasons why the registered RF-ON / RF-OFF pressure-match tolerance is not admissible (empty =
    admissible): required fields, derived from installed-gauge repeatability records of P1-S2 / P1-S3 in the bundle,
    frozen before the first P1-S4 matched-pair record. One registration per campaign (immutable; widening after seeing
    results is impossible by construction)."""
    if match is None:
        return ["pressure-match tolerance not registered (owner A9.8 P1Q-11; P1-IT-37)"]
    why = []
    for k in PRESSURE_MATCH_REQUIRED:
        if k not in match or match[k] is None:
            why.append("pressure-match registration lacks %s (owner A9.8 P1Q-11: derived from the installed chamber "
                       "gauge repeatability in P1-S2 / P1-S3)" % k)
    if why:
        return why
    try:
        tol = _num(match["p_chamber_rel_tol"], "p_chamber_rel_tol")
        if tol < 0:
            why.append("p_chamber_rel_tol < 0")
        t_frozen = parse_utc(match["frozen_utc"], "facility_match.frozen_utc")
    except RuleError as e:
        return [str(e)]
    by_id = {r.get("record_id"): r for r in records if isinstance(r, dict)}
    ids = match["derived_from_record_ids"]
    if not isinstance(ids, list) or not ids:
        why.append("derived_from_record_ids must list the P1-S2 / P1-S3 gauge-repeatability records")
    else:
        bad = [i for i in ids if i not in by_id or by_id[i].get("stage_id") not in PRESSURE_MATCH_EVIDENCE_STAGES]
        if bad:
            why.append("derived_from_record_ids %s are not P1-S2 / P1-S3 records of this campaign (owner A9.8 P1Q-11)"
                       % bad)
    pair_recs = [by_id[i] for i in pair_ids if i in by_id and by_id[i].get("stage_id") == "P1-S4"]
    first = _first_ts(pair_recs, ("P1-S4",))
    if first is not None and t_frozen >= first:
        why.append("pressure-match tolerance %r frozen at %s, not before the first P1-S4 matched pair (owner A9.8 "
                   "P1Q-11)" % (match["criteria_id"], match["frozen_utc"]))
    for k in ("gauge_id", "repeatability_basis"):
        if not _str(match[k]):
            why.append("%s must be a non-empty registered string (owner A9.8 P1Q-11)" % k)
    return why


# ------------------------------------------------------------------ A9.11 P1Q-01 stable-region criteria registration
def check_stable_criteria_registration(criteria, records):
    """Reasons why frozen stable-region criteria are not admissible (empty = admissible). The sha256 mismatch is a
    malformed registration and raises RuleError; evidence ids must be P1-S2..S4 records of this campaign."""
    h = canonical_sha256(criteria, drop=("criteria_sha256",))
    if criteria.get("criteria_sha256") != h:
        raise RuleError("stable_criteria.criteria_sha256 %r != sha256 of the frozen criteria record %s (owner A9.11 "
                        "P1Q-01: freeze and hash; a changed criteria record is a new version)"
                        % (criteria.get("criteria_sha256"), h))
    by_id = {r.get("record_id"): r for r in records if isinstance(r, dict)}
    bad = [i for i in criteria["derived_from_record_ids"]
           if i not in by_id or by_id[i].get("stage_id") not in STABLE_EVIDENCE_STAGES]
    if bad:
        return ["stable-region criteria %r derived from %s, which are not P1-S2..S4 evidence records of this campaign "
                "(owner A9.11 P1Q-01)" % (criteria["criteria_id"], bad)]
    return []


# ------------------------------------------------------------------ freeze-before-stage (P1Q-02 / P1Q-03 / P1Q-07)
def freeze_before_stage_reasons(registration, name, stage, records, rule):
    """[] when registration exists and its frozen_utc precedes the first record of `stage`; else the reasons."""
    if registration is None:
        return ["%s not registered (%s)" % (name, rule)]
    first = _first_ts(records, (stage,))
    t = parse_utc(registration.get("frozen_utc"), "%s frozen_utc" % name)
    if first is not None and t >= first:
        return ["%s frozen at %s, not before the first %s record (%s)" % (name, registration["frozen_utc"], stage,
                                                                        rule)]
    return []


def check_start_limit_revisions(revisions, attempt_log):
    """A9.10 P1Q-02: a later revision of the start-attempt limits may not increase V_d,max, the current limit, the
    attempt duration or the attempt count after an unsuccessful ignition attempt. revisions = registered limits (each
    with frozen_utc), attempt_log = [{timestamp_utc, sustained (bool)}]. Raises RuleError on an increase; returns the
    revisions ordered by freeze time."""
    keys = ("V_d_max_V", "I_limit_A", "attempt_duration_max_s", "max_attempts")
    revs = sorted(revisions, key=lambda r: parse_utc(r["frozen_utc"], "revision frozen_utc"))
    fails = [parse_utc(a["timestamp_utc"], "attempt timestamp_utc") for a in attempt_log
             if a.get("sustained") is not True]
    for prev, nxt in zip(revs, revs[1:]):
        t = parse_utc(nxt["frozen_utc"], "revision frozen_utc")
        if any(f < t for f in fails):
            up = [k for k in keys if float(nxt[k]) > float(prev[k])]
            if up:
                raise RuleError("start-attempt limits revision %r increases %s after an unsuccessful ignition (owner "
                                "A9.10 P1Q-02: never increased merely to obtain a sustained discharge)"
                                % (nxt.get("registration_id"), up))
    return revs


# ------------------------------------------------------------------ A9.8 P1Q-04 UBQ-06 thermal abort / derate
def thermal_abort_rows(record, limit_rows):
    """Rows of every registered component temperature of a record vs (validated continuous-use limit - 50 K). Status
    ABORT_DERATE_REQUIRED at / above it, else BELOW_ABORT_DERATE_LIMIT; never a thermal PASS (ICP_COUPLED_THERMAL stays
    UNRESOLVED)."""
    temps = record.get("temperatures") if isinstance(record, dict) else None
    if not isinstance(temps, dict):
        return []
    out = []
    for lr in limit_rows:
        f = lr["temperature_field"]
        if f not in temps:
            continue
        t = float(temps[f])
        at = float(lr["validated_continuous_limit_C"]) - THERMAL_ABORT_MARGIN_K
        out.append({"record_id": record.get("record_id"), "temperature_field": f, "component": lr["component"],
                    "T_C": t, "abort_derate_at_C": at,
                    "status": "ABORT_DERATE_REQUIRED" if t >= at else "BELOW_ABORT_DERATE_LIMIT",
                    "rule": "owner A9.8 P1Q-04 / A9.1 UBQ-06: validated continuous-use limit - 50 K on all P1 "
                            "operation incl. non-scoring runs; not a thermal PASS"})
    return out


# ------------------------------------------------------------------ A9.10 P1Q-06 factor F6 order
def magnet_order_reasons(records, stages=("P1-S3", "P1-S4", "P1-S5")):
    """{record_id: [reason]} for magnet-on (REGISTERED_SETTING) records of an ICP-only stage taken before any
    magnet-OFF record of that stage (owner A9.10 P1Q-06: magnet OFF first)."""
    out = {}
    for st in stages:
        rs = [r for r in records if isinstance(r, dict) and r.get("stage_id") == st and "h1_magnet_state" in r]
        offs = [parse_utc(r["timestamp_utc"], "record") for r in rs if r["h1_magnet_state"] == "OFF"]
        first_off = min(offs) if offs else None
        for r in rs:
            if r["h1_magnet_state"] == "REGISTERED_SETTING":
                t = parse_utc(r["timestamp_utc"], "record")
                if first_off is None or t <= first_off:
                    out.setdefault(r["record_id"], []).append(
                        "factor F6: magnet-on record %r in %s precedes the magnet-OFF baseline of that stage (owner "
                        "A9.10 P1Q-06: run magnet OFF first)" % (r["record_id"], st))
    return out


# ------------------------------------------------------------------ A9.14 F6-OQ-03 geometry matrix
def check_geometry_matrix(matrix):
    if not isinstance(matrix, dict) or not _str(matrix.get("matrix_id")) or not isinstance(matrix.get("geometries"),
                                                                                           list):
        raise RuleError("icp_geometry_matrix needs matrix_id and geometries (owner A9.14 F6-OQ-03)")
    parse_utc(matrix.get("frozen_utc"), "icp_geometry_matrix.frozen_utc")
    ids = set()
    for g in matrix["geometries"]:
        for k in GEOMETRY_REQUIRED:
            if not isinstance(g, dict) or k not in g:
                raise RuleError("icp_geometry_matrix geometry needs %s" % list(GEOMETRY_REQUIRED))
        if g["within_drawing_envelope"] is not True:
            raise RuleError("geometry %r outside the KC-1 / ICP LOCK-1 drawing envelope: a test matrix never enlarges "
                            "the mechanical envelope without a drawing revision (owner A9.14 F6-OQ-02)"
                            % g["geometry_id"])
        if g["geometry_id"] in ids:
            raise RuleError("geometry %r listed twice" % g["geometry_id"])
        ids.add(g["geometry_id"])
    if not ids:
        raise RuleError("icp_geometry_matrix lists no geometry")
    return ids


def geometry_matrix_report(matrix, op_records):
    """Per registered geometry: number of measured operating-point records (MEASURED_GEOMETRY / NOT_YET_MEASURED);
    out_of_matrix {record_id: reason} for records without a registered geometry id. Never interpolates."""
    if matrix is None:
        return {"status": "NOT_REGISTERED", "geometries": [], "out_of_matrix": {},
                "rule": "owner A9.14 F6-OQ-03: P1 registers a multi-geometry bench matrix; each geometry is measured"}
    ids = check_geometry_matrix(matrix)
    counts = {g: 0 for g in ids}
    oom = {}
    for r in op_records:
        g = r.get("icp_geometry_id")
        if g in counts:
            counts[g] += 1
        else:
            oom[r["record_id"]] = ["icp_geometry_id %r not in the registered geometry matrix %r (owner A9.14 F6-OQ-03 / "
                                   "F6-OQ-02)" % (g, matrix["matrix_id"])]
    return {"status": "REGISTERED", "matrix_id": matrix["matrix_id"],
            "geometries": [{"geometry_id": g, "n_operating_point_records": counts[g],
                            "state": "MEASURED_GEOMETRY" if counts[g] else "NOT_YET_MEASURED"} for g in sorted(counts)],
            "out_of_matrix": oom,
            "surrogate": "NONE: no geometry-response surrogate between measured configurations before separate "
                         "predictive validation (owner A9.14 F6-OQ-03)"}


# ------------------------------------------------------------------ A9.14 P1Q-17 triggered reverification
def reduce_dwv_reverification(rec):
    """700 V DC / 60 s current-limited controlled reverification, ONLY after repair, insulation-path modification,
    suspected fault or a defined requalification trigger (never a routine pre-run test); representative pressure /
    gas; leakage against the per-path criterion (P1-IT-55 form); the initial 1.05 kV qualification stays separate;
    700 V is an owner development acceptance level, never attributed to an ECSS clause. Status REVERIFICATION_RECORDED /
    REVERIFICATION_DEFICIENT / REVERIFICATION_NOT_EVALUATED_TBD (never PASS)."""
    for k in REVERIFICATION_REQUIRED:
        if not isinstance(rec, dict) or k not in rec:
            raise RuleError("reverification record lacks %s (owner A9.14 P1Q-17)" % k)
    if rec["trigger"] not in REVERIFICATION_TRIGGERS:
        raise RuleError("reverification trigger %r refused: the 700 V DC / 60 s test is not a routine pre-run test; "
                        "triggers %s (owner A9.14 P1Q-17)" % (rec["trigger"], REVERIFICATION_TRIGGERS))
    if not _str(rec["trigger_record_id"]):
        raise RuleError("reverification needs the trigger_record_id (repair / modification / fault record)")
    if rec["level_basis"] != REVERIFICATION_LEVEL_BASIS or "ECSS" in json.dumps(rec, ensure_ascii=False).upper():
        raise RuleError("reverification level basis must be %s; 700 V is an owner development acceptance level and is "
                        "never attributed to an (unverified) ECSS clause (owner A9.14 P1Q-17)"
                        % REVERIFICATION_LEVEL_BASIS)
    if not _str(rec["pressure_gas_condition"]) or not _str(rec["sensitive_electronics_handling"]):
        raise RuleError("reverification needs the representative pressure / gas condition and the sensitive-"
                        "electronics handling recorded (owner A9.14 P1Q-17)")
    t_test = parse_utc(rec["test_utc"], "reverification test_utc")
    v = _num(rec["V_test_V"], "V_test_V")
    t = _num(rec["duration_s"], "duration_s")
    leak = _num(rec["leakage_A"], "leakage_A")
    why, tbd = [], []
    if v < REVERIFICATION_V_DC:
        why.append("V_test %r V < 700 V DC" % v)
    if t < REVERIFICATION_DURATION_S:
        why.append("duration %r s < 60 s" % t)
    if rec["current_limited"] is not True:
        why.append("not current-limited")
    for k in ("breakdown_or_flashover", "tracking_or_disruptive_discharge", "protective_trip"):
        if rec[k] is not False:
            why.append("%s recorded" % k)
    acc = rec["leakage_acceptance"]
    if acc is None or not _str(acc.get("basis_document_id")):
        tbd.append("no per-path leakage criterion with a documented basis registered before the test (P1-IT-55 form)")
    else:
        if parse_utc(acc.get("registered_utc"), "leakage_acceptance.registered_utc") >= t_test:
            why.append("per-path leakage limit registered after the test")
        if leak > _num(acc.get("max_leakage_A"), "max_leakage_A"):
            why.append("leakage %r A above the per-path limit %r A" % (leak, acc["max_leakage_A"]))
    status = ("REVERIFICATION_DEFICIENT" if why else
              ("REVERIFICATION_NOT_EVALUATED_TBD" if tbd else "REVERIFICATION_RECORDED"))
    return {"record_id": rec["record_id"], "path_id": rec["path_id"], "trigger": rec["trigger"], "status": status,
            "deficiencies": why, "tbd": tbd, "V_test_V": v, "duration_s": t, "leakage_A": leak,
            "note": "triggered reverification only (owner A9.14 P1Q-17); separate from the initial 1.05 kV DC / 60 s "
                    "qualification (A9.4 P1Q-14, A9.8 OQ-RFQV2-08); never a PASS"}


# ------------------------------------------------------------------ A9.14 OD5 baseline start sequence
def check_baseline_start_sequence(seq):
    """OD5 baseline atmospheric start: gas / plenum / feed -> H-1 magnet state -> ignite / stabilize ICP -> verify
    electron-source condition -> apply V_d -> verify sustained Hall discharge; at most one initial attempt + two
    retries under REGISTERED dwell / thermal limits (dwell_thermal_limits_id; values not set here). A C1-selected
    variant uses its own separately qualified heater / keeper sequence (c1_qualified_sequence_id) and is not checked
    against the ICP order. Returns {status: OD5_SEQUENCE_CONFORMS | OD5_SEQUENCE_NONCONFORMING | NOT_EVALUATED_REGISTRATION}."""
    for k in ("sequence_id", "variant", "attempts", "dwell_thermal_limits_id"):
        if not isinstance(seq, dict) or k not in seq:
            raise RuleError("start sequence lacks %s (owner A9.14 OD5)" % k)
    if seq["variant"] not in OD5_VARIANTS:
        raise RuleError("start sequence variant %r not in %s" % (seq["variant"], OD5_VARIANTS))
    out = {"sequence_id": seq["sequence_id"], "variant": seq["variant"], "required_order": list(OD5_EVENTS),
           "max_attempts": OD5_MAX_ATTEMPTS}
    if not _str(seq["dwell_thermal_limits_id"]):
        out.update({"status": "NOT_EVALUATED_REGISTRATION",
                    "reasons": ["dwell / thermal limits of the start attempts not registered (A9.14 OD5)"]})
        return out
    if seq["variant"] == "C1_SELECTED_VARIANT":
        if not _str(seq.get("c1_qualified_sequence_id")):
            raise RuleError("C1-selected variant needs its separately qualified heater / keeper sequence id (A9.14 OD5)")
        out.update({"status": "C1_VARIANT_OWN_SEQUENCE", "reasons": []})
        return out
    att = seq["attempts"]
    if not isinstance(att, list) or not att:
        raise RuleError("start sequence needs at least one recorded attempt")
    why = []
    if len(att) > OD5_MAX_ATTEMPTS:
        why.append("%d attempts > 1 initial + 2 retries (A9.14 OD5)" % len(att))
    for n, a in enumerate(att, 1):
        ev = a.get("events") if isinstance(a, dict) else None
        if not isinstance(ev, list) or not ev:
            raise RuleError("attempt %d records no events" % n)
        if list(ev) != list(OD5_EVENTS[:len(ev)]):
            why.append("attempt %d event order %s is not the OD5 order %s" % (n, ev, list(OD5_EVENTS)))
        sustained = ev[-1] == OD5_EVENTS[-1]
        if sustained and n < len(att):
            why.append("attempt %d reached a sustained Hall discharge but further attempts follow" % n)
    out.update({"status": "OD5_SEQUENCE_NONCONFORMING" if why else "OD5_SEQUENCE_CONFORMS", "reasons": why,
                "n_attempts": len(att)})
    return out


# ------------------------------------------------------------------ A9.14 ICPQ-08 B(z) mapping
def check_bz_mapping(rec):
    """B(z) map record: ENERGIZED (RF on) only with a demonstrated gaussmeter RF-immunity record; otherwise RF_OFF at
    the preregistered delay whose field decay / repeatability has been characterized (|delay - registered| <= the
    registered tolerance; no values set here). Returns {status: BZ_MAP_ADMISSIBLE | NOT_EVALUATED_REGISTRATION | OUT_OF_DOMAIN}."""
    if not isinstance(rec, dict) or not _str(rec.get("map_id")) or rec.get("rf_state") not in BZ_RF_STATES:
        raise RuleError("B(z) map needs map_id and rf_state in %s (owner A9.14 ICPQ-08)" % (BZ_RF_STATES,))
    out = {"map_id": rec["map_id"], "rf_state": rec["rf_state"]}
    if rec["rf_state"] == "ENERGIZED":
        if not _str(rec.get("gaussmeter_rf_immunity_record_id")):
            out.update({"status": "NOT_EVALUATED_REGISTRATION",
                        "reason": "energized B(z) map without a demonstrated gaussmeter RF-immunity record (owner A9.14 "
                                  "ICPQ-08)"})
        else:
            out.update({"status": "BZ_MAP_ADMISSIBLE", "reason": None})
        return out
    reg = rec.get("delay_registration")
    if not isinstance(reg, dict) or any(k not in reg or reg[k] is None for k in BZ_DELAY_REQUIRED):
        out.update({"status": "NOT_EVALUATED_REGISTRATION",
                    "reason": "RF-off B(z) map without a preregistered, decay-characterized delay %s (owner A9.14 "
                              "ICPQ-08)" % list(BZ_DELAY_REQUIRED)})
        return out
    d = _num(rec.get("rf_off_delay_s"), "rf_off_delay_s")
    if abs(d - _num(reg["delay_s"], "delay_s")) > _num(reg["delay_tolerance_s"], "delay_tolerance_s"):
        out.update({"status": "OUT_OF_DOMAIN",
                    "reason": "RF-off delay %r s differs from the registered delay %r s by more than its registered "
                              "tolerance (owner A9.14 ICPQ-08)" % (d, reg["delay_s"])})
        return out
    out.update({"status": "BZ_MAP_ADMISSIBLE", "reason": None, "delay_registration_id": reg["registration_id"]})
    return out

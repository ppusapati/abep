"""Hall-only sustainment envelope overlay (fo_hall_sustainment_envelope, hall_sustainment_envelope_v1).

Checks: the committed JSON / Markdown are reproduced by the builder; every case has a status and evidence items or
blockers; feed-envelope TBD quantities propagate as UNDETERMINED (committed data and synthetic cases); every number
carries an evidence class and a source; missing design inputs raise; no forbidden wording (no ranking, no setting an
architecture aside, no screening candidates or closures). Tests that need the pinned inputs skip ONLY when an input
file is genuinely absent (OverlayInputError); an input that is present with a different sha256 raises
OverlayInputMismatchError and FAILS those tests (CLAUDE.md rules 3 and 9: a changed input is never a silent skip). In the
merged repository every pinned input is present, so nothing here skips.
Values marked 'synthetic' below exist only inside these tests: they are not design values and not evidence.
"""
import copy
import importlib.util
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "docs", "architecture_comparison", "overlays", "hall_sustainment")
JSON_PATH = os.path.join(HERE, "hall_sustainment_envelope_v1.json")
MD_PATH = os.path.join(HERE, "HALL_SUSTAINMENT_ENVELOPE.md")
BUILDER = os.path.join(HERE, "build_hall_sustainment_envelope.py")

CLASSES = {"measured", "digitized", "inferred", "reconstructed", "model-derived", "assumed"}
FORBIDDEN = ["winner", "eliminat", "infeasible", "we recommend", "recommended architecture", "best architecture",
             "preferred architecture", "will sustain", "will not sustain", "will extinguish", "proves", "guarantee",
             "sgb-screen", "screening candidate", "ensemble_member_id", "is the baseline", "selected architecture",
             "outperform", "superior"]
SYN = "synthetic test value (not a design value, not evidence)"


def _load_builder():
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("hs_overlay_builder_under_test", BUILDER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


B = _load_builder()


@pytest.fixture(scope="module")
def doc():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def found():
    try:
        return B.resolve_inputs()
    except B.OverlayInputError as e:          # genuinely absent only; OverlayInputMismatchError propagates (fails)
        pytest.skip(f"pinned input files absent: {str(e)[:200]}")


def _walk(o, path=""):
    if isinstance(o, dict):
        yield path, o
        for k, v in o.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, f"{path}[{i}]")


def _has_number(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, list):
        return any(_has_number(x) for x in v)
    if isinstance(v, dict):
        return any(_has_number(x) for x in v.values())
    return False


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


# ------------------------------------------------------------------------------------------------ reproduction
def test_builder_import_reads_no_inputs_and_pins_are_well_formed():
    for k, pin in B.INPUTS.items():
        assert re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]), k
        assert not os.path.isabs(pin["path"]), k
    assert B.ARCH == "hall_only" and B.ARCH_IDS == ["hall_only", "rf_hall", "ecr_hall"]


def test_mismatch_is_not_a_skippable_error():
    assert not issubclass(B.OverlayInputMismatchError, B.OverlayInputError)


def test_hash_mismatch_in_checkout_fails_loudly(monkeypatch, tmp_path):
    for pin in B.INPUTS.values():                                  # every input present, with the wrong content
        f = tmp_path / pin["path"]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("not the pinned content\n")
    monkeypatch.setattr(B, "ROOT", str(tmp_path))
    monkeypatch.setattr(B, "candidate_roots", lambda extra: [str(tmp_path)])
    with pytest.raises(B.OverlayInputMismatchError) as e:
        B.resolve_inputs()
    assert "different sha256" in str(e.value)
    assert B.INPUTS["hall_sustainment_matrix"]["path"] in str(e.value)


def test_hash_mismatch_elsewhere_fails_loudly(monkeypatch, tmp_path):
    empty, other = tmp_path / "checkout", tmp_path / "other"
    empty.mkdir()
    f = other / B.INPUTS["feed_envelope"]["path"]
    f.parent.mkdir(parents=True)
    f.write_text("{}\n")
    monkeypatch.setattr(B, "ROOT", str(empty))
    monkeypatch.setattr(B, "candidate_roots", lambda extra: [str(empty), str(other)])
    with pytest.raises(B.OverlayInputMismatchError):
        B.resolve_inputs()


def test_checkout_inputs_match_pins_when_present():
    """Any pinned input that exists in this checkout must carry the pinned sha256 (fail, never skip)."""
    for k, pin in B.INPUTS.items():
        p = os.path.join(ROOT, pin["path"])
        if os.path.isfile(p):
            assert B.sha256_file(p) == pin["sha256"], f"{k}: {pin['path']} differs from its pin"


def test_echt_area_carries_forced_assumption_a1(doc):
    regs = {r["id"]: r for r in doc["evidence_regions"]}
    for i in ("E03", "E04"):
        du = regs[i]["channel_area"]["declared_uncertainty"]
        assert du["forced_assumption"] == "A1" and du["text"].startswith("A1 ")
        assert du["repository_status"] == "HISTORICAL_UNSUPPORTED" and du["evidence_class"] == "assumed"
    assert "forced assumption A1" in doc["definitions"]["interpretation_conditions"]["ECHT-OD-READING"]
    log = doc["input_repin_log"]
    assert log[-1]["to"]["sha256"] == B.INPUTS["hall_sustainment_matrix"]["sha256"] == \
        doc["inputs"]["hall_sustainment_matrix"]["sha256"]


def test_missing_inputs_raise_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(B, "ROOT", str(tmp_path))
    monkeypatch.setattr(B, "candidate_roots", lambda extra: [str(tmp_path)])
    with pytest.raises(B.OverlayInputError) as e:
        B.resolve_inputs()
    msg = str(e.value)
    assert "pinned overlay inputs not found" in msg
    assert B.INPUTS["hall_sustainment_matrix"]["path"] in msg and B.INPUTS["feed_envelope"]["path"] in msg


def test_committed_files_reproduced(found):
    js1, md1 = B.render_all()
    js2, md2 = B.render_all()
    assert js1 == js2 and md1 == md2                                   # deterministic
    with open(JSON_PATH, encoding="utf-8") as f:
        assert f.read() == js1, "JSON not reproduced: rerun the builder"
    with open(MD_PATH, encoding="utf-8") as f:
        assert f.read() == md1, "Markdown not reproduced: rerun the builder"


def test_check_mode_passes(found):
    assert B.main(["--check"]) == 0


def test_inputs_recorded_with_pins(doc):
    for k, pin in B.INPUTS.items():
        assert doc["inputs"][k]["sha256"] == pin["sha256"]
        assert doc["inputs"][k]["path"] == pin["path"]


# ------------------------------------------------------------------------------------------------ structure
def test_every_case_has_status_and_items_or_blockers(doc):
    statuses = {B.S_SUP, B.S_CON, B.S_UND}
    coverages = {B.COVERS, B.PARTIAL, B.DNR, B.NC, B.UND}
    air = [c for c in doc["cases"] if c["kind"] == "air"]
    assert len(air) == 9
    assert sorted({(c["alt_km"], c["atmosphere_level"]) for c in air}) == sorted(
        (a, lvl) for a in (180.0, 200.0, 230.0) for lvl in ("low", "mean", "high"))
    assert {c["kind"] for c in doc["cases"]} == {"air", "xe_path_variant", "mixed_air_xe_variant"}
    for c in doc["cases"]:
        assert c["status"] in statuses, c["case_id"]
        assert c["comparisons"] or c["blockers"], c["case_id"]
        if c["status"] == B.S_UND:
            assert c["blockers"], c["case_id"]
        for b in c["blockers"]:
            assert b["id"] in doc["blocker_catalogue"], b["id"]
            assert isinstance(b["resolved_by"], list)
        for x in c["comparisons"]:
            assert x["verdict"] in {"supports", "contradicts", "does_not_reach_case", "cannot_decide"}
            for a in B.REQUIRED_AXES + B.INFO_AXES:
                ax = x["axes"][a]
                assert ax["coverage"] in coverages, (c["case_id"], x["item"], a)
                if ax["coverage"] == B.NC:
                    assert ax.get("missing"), (c["case_id"], x["item"], a)       # names the missing quantity
                if ax["coverage"] == B.UND:
                    assert ax.get("blocked_by"), (c["case_id"], x["item"], a)    # names the TBD
    for c in air:
        assert c["comparisons"], c["case_id"]
        ig = c["ignition"]
        for blk in (ig["xenon_assisted"]["xe_anode_start"], ig["xenon_assisted"]["xe_cathode_direct"], ig["air_only"]):
            assert blk["status"] in {B.I_SUP, B.I_CON, B.S_UND}
            assert blk["supporting_items"] or blk["blockers"]
        assert "B-IGN-AIR-NO-EVIDENCE" in ig["air_only"]["blockers"]


def test_every_blocker_has_a_resolution_route(doc):
    routes = {d["id"] for d in doc["decisive_measurements"]}
    for c in doc["cases"]:
        ids = {b["id"] for b in c["blockers"]}
        for b in c["blockers"]:
            assert set(b["resolved_by"]) <= routes, b
            if b["id"] != "B-SCOPE-XE":
                assert b["resolved_by"], b["id"]
        for x in c["comparisons"]:                      # every TBD an axis names is a blocker of that case
            for a, ax in x["axes"].items():
                assert set(ax.get("blocked_by", [])) <= ids, (c["case_id"], x["item"], a)
        for blk in (c.get("ignition") or {}).get("air_only", {}), \
                (c.get("ignition") or {}).get("xenon_assisted", {}).get("xe_anode_start", {}):
            assert set(blk.get("blockers", [])) <= set(doc["blocker_catalogue"])


def test_evidence_items_used_for_hall_only_have_no_active_preionizer(doc):
    regs = {r["id"]: r for r in doc["evidence_regions"]}
    for c in doc["cases"]:
        for x in c["comparisons"]:
            r = regs[x["item"]]
            assert r["role"] in {"support_air_only", "extinction", "support_xe_admixture"}
            if r["preionizer_present"]:
                assert r.get("mode_note") and not r["status_bearing"], x["item"]   # RF-off mode, second-hand only
    excluded = {e["item"] for e in doc["excluded_for_hall_only"]}
    assert {"E17", "E18", "E21"} <= excluded


# ------------------------------------------------------------------------------------------------ TBD propagation
def test_feed_tbd_propagates_in_committed_cases(doc):
    for c in doc["cases"]:
        if c["kind"] != "air":
            continue
        fm = c["feed"]["mdot_anode_kgps"]
        assert fm["value"] is None and fm["evidence_class"] == "TBD"
        assert c["status"] == B.S_UND
        blk = {b["id"]: b for b in c["blockers"]}
        assert blk["B-FEED-MDOT"]["requires"] == fm["requires"] and fm["requires"].startswith("TBD - requires")
        assert blk["B-FEED-COMP"]["requires"] == c["feed"]["valve_outlet_w_s"]["requires"]
        assert c["feed"]["flow_density_kgpm2ps"]["value"] is None
        for x in c["comparisons"]:
            assert x["axes"]["anode_flow_density"]["coverage"] in {B.UND, B.NC}
            assert x["axes"]["composition"]["coverage"] == B.UND
            assert x["verdict"] == "cannot_decide"
    for c in doc["cases"]:
        if c["kind"] != "air":
            assert c["status"] == B.S_UND
            assert any(b["kind"] == "feed_tbd" for b in c["blockers"])


def _reg(role="support_air_only", gamma=1e-3, bound=None, conds=(), w=None, V=(200.0, 250.0), Bv=(100.0, 100.0),
         cathode="Xe", level=3, ext_kind=None):
    """A synthetic evidence region shaped like evidence_region() output."""
    r = {"id": "SYN", "role": role, "status_bearing": level <= 3, "evidence_level": level,
         "flow": {"value": [gamma * 1e6 * 1e-3, gamma * 1e6 * 1e-3], "unit": "mg/s", "conditional_on": []},
         "flow_density": {"value": [gamma, gamma], "bound": bound, "conditional_on": list(conds)},
         "composition": {"comparable": True, "species_present": sorted((w or {"N2": 1.0})), "w": w or {"N2": 1.0}},
         "discharge_voltage": {"value": list(V), "kind": "operated"},
         "magnetic_field": {"value": list(Bv), "definition": "Br_exit_centreline"},
         "cathode_gas": {"gas": cathode},
         "discharge_power": {"value": [0.3, 0.5], "rfp_total_power_relation": "WITHIN_RFP_CEILING",
                             "kind": "operated range"}}
    if ext_kind:
        r["extinction_kind"] = ext_kind
    return r


def _case(mdot=None, area=None, w=None, V=None, Bv=None, cathode=None, P=None):
    area = [area, area] if isinstance(area, float) else area             # the design area is carried as [lo, hi]
    return {"mdot_kgps": [mdot, mdot] if mdot is not None else None, "w_valve": w, "channel_area_m2": area,
            "V_d": [V, V] if V is not None else None,
            "B": {"value": [Bv, Bv], "definition": "Br_exit_centreline"} if Bv is not None else None,
            "cathode_gas": cathode, "P_d_kW": [P, P] if P is not None else None, "mdot_max_H_RAM_kgps": 3.2e-6}


def test_synthetic_tbd_propagation_and_status_logic():
    sup = _reg()
    # all case quantities TBD -> every required axis UNDETERMINED, status UNDETERMINED
    x = B.compare(_case(), sup)
    assert all(x["axes"][a]["coverage"] == B.UND for a in B.REQUIRED_AXES)
    assert x["axes"]["anode_flow_density"]["blocked_by"] == ["B-FEED-MDOT", "B-DESIGN-ACH"]
    assert B.decide([x])[0] == B.S_UND
    # flow known, channel area TBD -> still UNDETERMINED, blocked by the design TBD only
    x = B.compare(_case(mdot=2e-6, w={"N2": 1.0}, V=220.0, Bv=100.0, cathode="Xe"), sup)
    assert x["axes"]["anode_flow_density"] == {"coverage": B.UND, "blocked_by": ["B-DESIGN-ACH"]}
    assert B.decide([x])[0] == B.S_UND
    # everything known and covered -> SUPPORTED
    full = dict(mdot=2e-6, area=1.9e-3, w={"N2": 1.0}, V=220.0, Bv=100.0, cathode="Xe")
    x = B.compare(_case(**full), sup)
    assert x["verdict"] == "supports" and B.decide([x])[0] == B.S_SUP
    # lower flow density than demonstrated -> does not reach
    x = B.compare(_case(**{**full, "mdot": 1e-6}), sup)
    assert x["axes"]["anode_flow_density"]["coverage"] == B.DNR and x["verdict"] == "does_not_reach_case"
    # atomic O in the feed but not in the evidence -> composition does not reach
    x = B.compare(_case(**{**full, "w": {"N2": 0.6, "O": 0.4}}), sup)
    assert x["axes"]["composition"]["coverage"] == B.DNR
    # extinction at a higher flow density, case at or below it -> CONTRADICTED; with support too -> UNDETERMINED
    ext = _reg(role="extinction", gamma=1.5e-3, ext_kind="low_flow")
    xe = B.compare(_case(**full), ext)
    assert xe["verdict"] == "contradicts" and B.decide([xe])[0] == B.S_CON
    assert B.decide([B.compare(_case(**full), sup), xe])[0] == B.S_UND
    # level-5 item and interpretation-conditional item never set a status
    assert B.compare(_case(**full), _reg(level=5))["verdict"] == "cannot_decide"
    xc = B.compare(_case(**full), _reg(bound="lower", conds=["ECHT-OD-READING"]))
    assert xc["axes"]["anode_flow_density"]["conditional_on"] == ["ECHT-OD-READING"]
    assert xc["verdict"] == "cannot_decide"
    # missing evidence quantity -> NOT_COMPARABLE with the quantity named
    r = _reg()
    r["magnetic_field"] = {"value": None, "missing": "B not reported"}
    x = B.compare(_case(**full), r)
    assert x["axes"]["magnetic_field"] == {"coverage": B.NC, "missing": "B not reported"}


def _synthetic_design(V, Bv, area, cathode="Xe"):
    ent = lambda v, **kw: {"value": v, "source": SYN, "evidence_class": "assumed", **kw}    # noqa: E731
    return B.validate_design_point({"format": "hall_sustainment_design_point_v1", "label": "synthetic",
                                    "inputs": {"channel_area_m2": ent(area), "discharge_voltage_V": ent(V),
                                               "magnetic_field": ent(Bv, unit="G", definition="Br_exit_centreline"),
                                               "cathode_gas": ent(cathode),
                                               "discharge_power_W": {"status": "TBD",
                                                                     "requires": "TBD - requires " + SYN}}})


def _feed_with_case0(found, mdot, w):
    with open(found["feed_envelope"], encoding="utf-8") as f:
        feed = json.load(f)
    feed = copy.deepcopy(feed)
    st = feed["cases"][0]["feed_state"]
    st["mdot_total_kgps"]["value"] = mdot                 # synthetic, in memory only
    st["w_s"]["values"] = dict(w)
    return feed


def test_tbd_propagation_through_build(found):
    feed = _feed_with_case0(found, 3.0e-6, {"O": 0.2, "N2": 0.6, "O2": 0.2})
    d = B.build(found, design_point=_synthetic_design(250.0, 130.0, 5.0e-3), feed_override=feed)
    c0, rest = d["cases"][0], [c for c in d["cases"][1:] if c["kind"] == "air"]
    ids0 = {b["id"] for b in c0["blockers"]}
    assert "B-FEED-MDOT" not in ids0 and "B-FEED-COMP" not in ids0 and "B-DESIGN-ACH" not in ids0
    assert c0["status"] == B.S_UND                          # atomic O: no evidence item covers the composition
    assert all(x["axes"]["composition"]["coverage"] in {B.DNR, B.NC} for x in c0["comparisons"])
    for c in rest:                                          # untouched cases keep the feed TBD
        assert {"B-FEED-MDOT", "B-FEED-COMP"} <= {b["id"] for b in c["blockers"]} and c["status"] == B.S_UND


def test_statuses_reachable_with_real_evidence_and_synthetic_inputs(found):
    # pure-N2 synthetic feed at a P5-like operating point: E01 covers every required axis -> SUPPORTED
    feed = _feed_with_case0(found, 3.0e-6, {"O": 0.0, "N2": 1.0, "O2": 0.0})
    d = B.build(found, design_point=_synthetic_design(250.0, 130.0, 6.0e-3), feed_override=feed)
    c0 = d["cases"][0]
    assert c0["status"] == B.S_SUP and c0["supporting_items"] == ["E01"]
    e01 = next(x for x in c0["comparisons"] if x["item"] == "E01")
    assert "S3" in e01["assumptions"] and e01["joint_operating_point_check"].startswith("NOT_CHECKED")
    # a delivered pure-N2 composition carries no stale free-stream composition blockers
    ids = {b["id"] for b in c0["blockers"]}
    assert "B-EVID-ATOMIC-O" not in ids and "B-EVID-O2-FRACTION" not in ids


def test_e13_sustained_point_is_not_an_extinction_threshold(found, doc):
    # E13's matrix flow is the lowest-Xe point at which the Z-70 SUSTAINED: never an extinction flow / flow density
    e13 = {r["id"]: r for r in doc["evidence_regions"]}["E13"]
    assert e13["role"] == "extinction"
    assert e13["flow"]["value"] is None and "not reported" in e13["flow"]["missing"]
    assert e13["flow_density"]["value"] is None
    ref = e13["sustained_reference_point"]
    assert ref["evidence_class"] in CLASSES and ref["source"] and "SUSTAINED" in ref["meaning"]
    comp = e13["composition"]
    assert comp["xe_fraction"] is None and comp["xe_fraction_lowest_sustained"]["value"]
    assert "at extinction not reported" in comp["missing"]
    for c in doc["cases"]:
        assert "E13" not in c.get("thresholds", {}), c["case_id"]
    with open(MD_PATH, encoding="utf-8") as f:
        row = next(line for line in f if line.startswith("| E13 "))
    assert "n/c at extinction (not reported)" in row and "sustained at the lowest-Xe point" in row
    # probe: pure N2 at a Z-70-like point (290 V, 135 G, Z-70 channel area, 1.45 mg/s) is not CONTRADICTED by E13
    area = {r["id"]: r for r in doc["evidence_regions"]}["E13"]["channel_area"]["value"]
    feed = _feed_with_case0(found, 1.45e-6, {"O": 0.0, "N2": 1.0, "O2": 0.0})
    d = B.build(found, design_point=_synthetic_design(290.0, 135.0, area), feed_override=feed)
    c0 = d["cases"][0]
    assert c0["status"] == B.S_UND and c0["contradicting_items"] == []
    x = next(x for x in c0["comparisons"] if x["item"] == "E13")
    assert x["axes"]["anode_flow_density"]["coverage"] == B.NC
    assert x["axes"]["composition"]["coverage"] == B.NC and x["verdict"] == "cannot_decide"


def test_design_area_range_is_carried_not_collapsed(found):
    # synthetic area range [4e-3, 8e-3] m^2 with 3.0e-6 kg/s: Gamma spans 3.75e-4..7.5e-4, straddling E01's lowest
    # demonstrated flow density; taking only the small end would give SUPPORTED, the full range must not
    feed = _feed_with_case0(found, 3.0e-6, {"O": 0.0, "N2": 1.0, "O2": 0.0})
    d = B.build(found, design_point=_synthetic_design(250.0, 130.0, [4.0e-3, 8.0e-3]), feed_override=feed)
    c0 = d["cases"][0]
    assert c0["status"] == B.S_UND
    x = next(x for x in c0["comparisons"] if x["item"] == "E01")
    assert x["axes"]["anode_flow_density"]["coverage"] == B.PARTIAL
    assert x["axes"]["anode_flow_density"]["case_value"] == [pytest.approx(3.75e-4), pytest.approx(7.5e-4)]
    assert c0["feed"]["flow_density_kgpm2ps"]["value"] == [pytest.approx(3.75e-4), pytest.approx(7.5e-4)]
    assert B.flow_density_range([1.0, 2.0], [4.0, 8.0]) == [0.125, 0.5]


def test_composition_blockers_use_the_delivered_composition(found):
    dp = _synthetic_design(250.0, 130.0, 6.0e-3)
    # O-free N2 / O2 delivered feed: no atomic-O blocker; O2 fraction below the largest tested -> no O2 blocker
    d = B.build(found, design_point=dp, feed_override=_feed_with_case0(found, 3.0e-6, {"O": 0.0, "N2": 0.7,
                                                                                         "O2": 0.3}))
    ids = {b["id"] for b in d["cases"][0]["blockers"]}
    assert "B-EVID-ATOMIC-O" not in ids and "B-EVID-O2-FRACTION" not in ids
    # delivered feed with atomic O: the blocker is raised from the delivered composition
    d = B.build(found, design_point=dp, feed_override=_feed_with_case0(found, 3.0e-6, {"O": 0.2, "N2": 0.6,
                                                                                         "O2": 0.2}))
    blk = {b["id"]: b for b in d["cases"][0]["blockers"]}
    assert "B-EVID-ATOMIC-O" in blk and "delivered" in blk["B-EVID-ATOMIC-O"]["detail"]
    # O2 above the largest tested fraction
    d = B.build(found, design_point=dp, feed_override=_feed_with_case0(found, 3.0e-6, {"O": 0.0, "N2": 0.3,
                                                                                         "O2": 0.7}))
    assert "B-EVID-O2-FRACTION" in {b["id"] for b in d["cases"][0]["blockers"]}


def test_design_point_inputs_are_explicit():
    good = {"format": "hall_sustainment_design_point_v1", "label": "x",
            "inputs": {k: {"status": "TBD", "requires": "TBD - requires " + SYN} for k in B.DESIGN_KEYS}}
    assert B.validate_design_point(good)["supplied"] is True
    missing = copy.deepcopy(good)
    del missing["inputs"]["cathode_gas"]
    with pytest.raises(B.MissingDesignInput):
        B.validate_design_point(missing)
    nosrc = copy.deepcopy(good)
    nosrc["inputs"]["channel_area_m2"] = {"value": 1e-3, "evidence_class": "assumed"}
    with pytest.raises(B.InvalidDesignPoint):
        B.validate_design_point(nosrc)
    badcls = copy.deepcopy(good)
    badcls["inputs"]["channel_area_m2"] = {"value": 1e-3, "source": SYN, "evidence_class": "guess"}
    with pytest.raises(B.InvalidDesignPoint):
        B.validate_design_point(badcls)
    unknown = copy.deepcopy(good)
    unknown["inputs"]["efficiency"] = {"value": 0.5, "source": SYN, "evidence_class": "assumed"}
    with pytest.raises(B.InvalidDesignPoint):
        B.validate_design_point(unknown)
    badtbd = copy.deepcopy(good)
    badtbd["inputs"]["discharge_voltage_V"] = {"status": "TBD"}
    with pytest.raises(B.InvalidDesignPoint):
        B.validate_design_point(badtbd)


def test_design_evaluation_never_overwrites_committed_files(found, tmp_path):
    with pytest.raises(SystemExit):
        B.main(["--design-point", os.devnull, "--out-dir", HERE])
    dp = {"format": "hall_sustainment_design_point_v1", "label": "synthetic",
          "inputs": {k: {"status": "TBD", "requires": "TBD - requires " + SYN} for k in B.DESIGN_KEYS}}
    p = tmp_path / "dp.json"
    p.write_text(json.dumps(dp))
    fe = tmp_path / "feed.json"
    fe.write_text(json.dumps(_feed_with_case0(found, 3.0e-6, {"O": 0.2, "N2": 0.6, "O2": 0.2})))
    out = tmp_path / "out"
    assert B.main(["--design-point", str(p), "--feed-envelope", str(fe), "--out-dir", str(out)]) == 0
    assert (out / B.OUT_JSON_NAME).is_file() and (out / B.OUT_MD_NAME).is_file()
    res = json.loads((out / B.OUT_JSON_NAME).read_text())
    assert res["inputs"]["feed_envelope"]["sha256"] == B.sha256_file(str(fe))   # the feed actually used is recorded
    assert res["design_point"]["supplied"] is True
    assert "B-FEED-MDOT" not in {b["id"] for b in res["cases"][0]["blockers"]}
    assert B.main(["--check"]) == 0                                             # committed files untouched


# ------------------------------------------------------------------------------------------------ evidence discipline
def test_numbers_carry_evidence_class_and_source(doc):
    for path, d in _walk(doc):
        if "value" in d and _has_number(d["value"]):
            assert d.get("evidence_class") in CLASSES, path
            assert d.get("source"), path
        if "w" in d and _has_number(d["w"]):                     # composition records (evidence and scenarios)
            assert d.get("evidence_class") in CLASSES, path
    for f in doc["findings"]:                                     # computed finding values: class (or None for counts)
        if _has_number(f.get("values")):
            assert f.get("source"), f["id"]
            assert f.get("evidence_class") in CLASSES or (f["id"] == "F-1" and f["evidence_class"] is None), f["id"]
    for c in doc["cases"]:
        for sc in (c["feed"].get("composition_scenarios") or {}).values():
            assert sc["source"] and sc["evidence_class"] == "model-derived"


def test_rfp_context_matches_constants(doc):
    spec = importlib.util.spec_from_file_location("hs_constants_under_test", os.path.join(ROOT, "abep_sim",
                                                                                          "constants.py"))
    K = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(K)
    assert doc["rfp_context"]["thrust_max"]["value"] == K.RFP.thrust_max_mN
    assert doc["rfp_context"]["power_max"]["value"] == K.RFP.power_max_W / 1000.0
    assert doc["rfp_context"]["firing_time_min"]["value"] == K.RFP.ignition_hours


def test_assumptions_and_thresholds_are_labelled(doc):
    assert doc["assumptions"]["S1"]["evidence_class"] == "assumed"
    assert doc["assumptions"]["S2"]["evidence_class"] == "assumed"
    for k, r in doc["proposed_rules"].items():
        assert r["status"].startswith("PROPOSED"), k
    for c in doc["cases"]:
        for item, t in c.get("thresholds", {}).items():
            for k, q in t.items():
                if isinstance(q, dict):
                    assert k in doc["threshold_definitions"], k
                    if k == "A_ch_max_under_H_RAM_m2":
                        assert "H_RAM" in q["conditional_on"]
        for q in c.get("H_RAM_bound", {}).values():
            assert q["conditional_on"] == ["H_RAM"]


def test_no_simulation_results_or_closures_used(doc):
    v1 = doc["v1_simulation_results"]
    assert v1["used_for_any_status"] is False and "not sustainment evidence" in v1["statement"]
    with open(MD_PATH, encoding="utf-8") as f:
        assert "not sustainment evidence" in f.read()


def test_no_forbidden_wording(doc):
    with open(MD_PATH, encoding="utf-8") as f:
        texts = list(_strings(doc)) + [f.read()]
    for t in texts:
        low = t.lower()
        for w in FORBIDDEN:
            assert w not in low, (w, t[:160])


def test_milestones_and_conditions(doc):
    assert doc["milestones"]["supports"] == ["A"]
    assert doc["milestones"]["to_reach_B"] and doc["milestones"]["to_reach_C"]
    ids = [m["id"] for m in doc["milestone_A_conditions"]]
    assert ids == [f"HS-A{i}" for i in range(1, len(ids) + 1)] and len(ids) >= 6
    routes = {d["id"] for d in doc["decisive_measurements"]}
    for m in doc["milestone_A_conditions"]:
        assert set(m["resolved_by"]) <= routes
    for c in doc["cases"]:
        if c["kind"] == "air":
            assert c["decisive_measurement"]["id"] in routes


def test_review_repairs_are_recorded(doc):
    regs = {r["id"]: r for r in doc["evidence_regions"]}
    # base-checkout inputs are labelled with the branch that holds the base commit, not 'main'
    for k in ("p5_case_geometry", "constants_module"):
        assert doc["inputs"][k]["branch"] != "main", k
    # a pure-N2 cathode is conditional (air constituent, not a listed RFP propellant); Xe listed; Ar not listed
    assert regs["E09"]["cathode_gas"]["rfp_propellant_relation"] == "AIR_CONSTITUENT_CONDITIONAL"
    assert regs["E01"]["cathode_gas"]["rfp_propellant_relation"] == "LISTED"
    assert regs["E03"]["cathode_gas"]["rfp_propellant_relation"] == "NOT_LISTED"
    f7 = next(f for f in doc["findings"] if f["id"] == "F-7")
    assert "not itself a listed RFP propellant" in f7["statement"]
    # explicit assumptions: per-axis product region (S3) and constant A_eff for the flow span (S4)
    for k in ("S3", "S4"):
        assert doc["assumptions"][k]["evidence_class"] == "assumed" and doc["assumptions"][k]["limits"]
    assert "FE-08" in doc["assumptions"]["S4"]["limits"]
    f5 = next(f for f in doc["findings"] if f["id"] == "F-5")
    assert f5["conditional_on"] == ["S4"] and "only under S4" in f5["statement"]
    for c in doc["cases"]:
        for x in c["comparisons"]:
            assert "S3" in x["assumptions"], (c["case_id"], x["item"])
    # E02: the stated window edge is approximate and carries an interpretation condition
    assert regs["E02"]["discharge_voltage"]["conditional_on"] == ["E02-WINDOW-EDGE"]
    assert "E02-WINDOW-EDGE" in doc["definitions"]["interpretation_conditions"]
    case = {"mdot_kgps": None, "w_valve": None, "channel_area_m2": None, "V_d": [277.0, 277.0],   # synthetic V_d
            "B": None, "cathode_gas": None, "P_d_kW": None, "mdot_max_H_RAM_kgps": None}
    ax = B.compare(case, regs["E02"])["axes"]["discharge_voltage"]
    assert ax["coverage"] == B.COVERS and ax["conditional_on"] == ["E02-WINDOW-EDGE"]
    # F-9: with current evidence no air case can be supported by literature transfer
    f9 = next(f for f in doc["findings"] if f["id"] == "F-9")
    assert f9["values"]["air_case_supportable_by_literature_transfer"] is False
    assert f9["values"]["O2_items_complete_on_required_axes"] == []
    with open(MD_PATH, encoding="utf-8") as f:
        md = f.read()
    assert "no air case (SC-FS, SC-REC or any O2- or O-containing delivered composition) can become" in md
    # the per-case decisive measurement is not overstated: DM-1 is a prerequisite
    dms = {d["id"]: d for d in doc["decisive_measurements"]}
    assert dms["DM-2"]["prerequisites"] == ["DI-1", "DI-2", "DM-1"]
    for c in doc["cases"]:
        if c["kind"] == "air":
            assert c["decisive_measurement"]["prerequisites"] == ["DI-1", "DI-2", "DM-1"]
    assert "single measurement" not in md

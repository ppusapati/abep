"""Tests for abep_sim.arch_compare (architecture comparison harness, arch_compare_v1).

Everything numeric in this file is a TEST-ONLY synthetic fixture (ensemble members, Hall maps, bus ledger, loads,
efficiencies, upstream state). None of it is a physical claim, and none of it is shipped as a harness default: the
harness itself has no synthetic provider, and a run with an injected ensemble or ledger is never `production_path`.
"""
import copy
import json
import math
import os
import sys
import types

import numpy as np
import pytest

from abep_sim import arch_compare as ac
from abep_sim.hall_ensemble import load_ensemble, screening_ids
from abep_sim.hall_map import REQUIRED_FIELDS, REQUIRED_META, pinned_commit

TEST_MEMBERS = ("TEST-ONLY-member-a", "TEST-ONLY-member-b", "TEST-ONLY-member-c")
AXES = {"Vd": [250.0, 300.0], "mdot_kgps": [1.0e-6, 2.0e-6]}          # TEST-ONLY grid
FORBIDDEN_KEY_PARTS = ("winner", "best", "rank", "recommend", "prefer", "probab", "select", "mean", "average",
                       "weights", "expected_value", "score")


# ------------------------------------------------------------------------------------------ TEST-ONLY providers
def _test_only_ensemble(members=TEST_MEMBERS, decision_sha=None):
    """Real layer-1 definition and real screening candidates, plus synthetic ADMITTED ids (tests only)."""
    e = copy.deepcopy(load_ensemble())
    e["admission_rule"] = "TEST-ONLY synthetic"
    e["members"] = []
    for m in members:
        rec = {"ensemble_member_id": m, "transport_family": "TEST-ONLY", "transport_parameters": {},
               "calibration_hypotheses": [], "evidence_basis": "TEST-ONLY", "applicability_domain": "TEST-ONLY",
               "validation_status": "TEST-ONLY"}
        if decision_sha is not None:
            rec["admission"] = {"decision_sha256": decision_sha}
        e["members"].append(rec)
    return e


def _write_map(tmp_path, member, arch, *, t_scale=1.0, p_scale=1.0, chem_ok=True, facility=False, axes=None,
               reaction_set="TEST-ONLY-rs", meta_member=None, name=None):
    """TEST-ONLY synthetic Hall map, bilinear-exact fields: thrust_N = t_scale*1e4*mdot, P_d = p_scale*2*Vd."""
    axes = axes or AXES
    names = list(axes)
    shape = tuple(len(axes[n]) for n in names)
    Vd = np.array(axes["Vd"]).reshape(-1, *([1] * (len(names) - 1)))
    md = np.array(axes["mdot_kgps"]).reshape(1, -1, *([1] * (len(names) - 2)))
    ones = np.ones(shape)
    f = {k: (0.5 * ones).tolist() for k in REQUIRED_FIELDS}
    for b in ("converged", "sustained", "wall_life_trustworthy"):
        f[b] = ones.tolist()
    f["chemistry_trustworthy"] = (ones if chem_ok else 0 * ones).tolist()
    f["thrust_N"] = (t_scale * 1e4 * md * ones).tolist()
    f["discharge_power_W"] = (p_scale * 2.0 * Vd * ones).tolist()
    f["discharge_current_A"] = (p_scale * 2.0 * ones).tolist()
    f["anode_eff"] = (0.4 * ones).tolist()
    meta = {k: "TEST-ONLY synthetic" for k in REQUIRED_META}
    meta.update(schema="hall_map_schema_v1", pinned=f'commit = "{pinned_commit()}"  # TEST-ONLY',
                ensemble_member_id=meta_member or member, facility_ingestion=facility, ion_wall_losses=False,
                reaction_set=reaction_set, transport=f"TEST-ONLY transport of {member}")
    p = tmp_path / (name or f"map_{member}_{arch}.json")
    p.write_text(json.dumps({"meta": meta, "axes": axes, "fields": f}))
    return str(p)


def _maps(tmp_path, members=TEST_MEMBERS, archs=ac.ARCHITECTURES, scales=None, **kw):
    scales = scales or {m: (1.0, 1.0) for m in members}
    return {m: {a: _write_map(tmp_path, m, a, t_scale=scales[m][0], p_scale=scales[m][1], **kw) for a in archs}
            for m in members}


def _test_only_ledger(arch, loads, efficiencies):
    """TEST-ONLY bus ledger with the bus_power_boundary_v1 output contract (not the real boundary module)."""
    items = [{"component": c, "P_load_W": loads[c], "efficiency": efficiencies[c], "P_bus_W": loads[c] / efficiencies[c]}
             for c in sorted(loads)]
    return {"boundary_version": "bus_power_boundary_v1", "architecture": arch,
            "P_bus_W": math.fsum(i["P_bus_W"] for i in items), "items": items, "residual_W": 0.0}


def _ledger_variant(resid_frac=0.0, total_scale=1.0, version="bus_power_boundary_v1", drop_item=False):
    def ledger(arch, loads, efficiencies):                  # TEST-ONLY, deliberately defective variants
        out = _test_only_ledger(arch, loads, efficiencies)
        out["P_bus_W"] *= total_scale
        out["residual_W"] = resid_frac * out["P_bus_W"]
        out["boundary_version"] = version
        if drop_item:
            out["items"] = out["items"][1:]
        return out
    return ledger


EFF = {"hall_discharge": 0.9, "hall_magnet": 0.9, "housekeeping": 0.8, "compressor": 0.85,
       "rf_source": 0.6, "ecr_source": 0.5, "ecr_magnet": 1.0}                      # TEST-ONLY


def _spec(arch, Vd=275.0, **kw):
    fixed = {"hall_magnet": 10.0, "housekeeping": 5.0}                            # TEST-ONLY
    fixed.update({"rf_hall": {"rf_source": 100.0}, "ecr_hall": {"ecr_source": 120.0, "ecr_magnet": 0.0}}.get(arch, {}))
    comps = set(fixed) | {"hall_discharge", "compressor"}
    args = dict(arch=arch, hall_operating_point={"Vd": Vd}, hall_axis_bindings={"mdot_kgps": "mdot_air"},
                fixed_loads_W=fixed, efficiencies={c: EFF[c] for c in comps}, source="TEST-ONLY synthetic numbers")
    args.update(kw)
    return ac.ArchitectureSpec(**args)


def _specs(**kw):
    return [_spec(a, **kw) for a in ac.ARCHITECTURES]


def _upstream(**kw):
    q = {"mdot_air": 1.5e-6, "comp_power": 30.0}                                  # TEST-ONLY
    q.update(kw)
    return ac.UpstreamState(q, "TEST-ONLY synthetic upstream")


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


# ------------------------------------------------------------------------------------------ refusals
def test_refuses_zero_admitted_members_against_the_real_ensemble(capsys):
    """Tripwire: the real credible set is empty (project decision 2026-09-26). If a member is ever admitted, this
    assertion must be updated deliberately (HARNESS.md drop-in step), not deleted."""
    real = load_ensemble()
    assert real["members"] == [] and len(screening_ids(real)) == 9
    for ledger in (None, _test_only_ledger):
        with pytest.raises(ac.NoAdmittedMembersError, match="zero ADMITTED members"):
            ac.compare_architectures(_specs(), _upstream(), {}, ledger=ledger)
        with pytest.raises(ac.NoAdmittedMembersError):                 # screening ids cannot stand in for members
            ac.compare_architectures(_specs(), _upstream(), {"sgb-screen-01": {}}, ledger=ledger)
    with pytest.raises(ac.NoAdmittedMembersError):
        ac.admitted_members(real)
    assert ac.main(["status"]) == 2
    assert "REFUSED (NoAdmittedMembersError)" in capsys.readouterr().err
    with pytest.raises(ac.NoAdmittedMembersError):                     # synthetic empty set: same refusal
        ac.compare_architectures(_specs(), _upstream(), {}, ledger=_test_only_ledger,
                                 ensemble=_test_only_ensemble(members=()))


def test_refuses_screening_candidate_ids(tmp_path):
    ens = _test_only_ensemble()
    assert set(ac.admitted_members(ens)) == set(TEST_MEMBERS)          # screening candidates are never members
    maps = _maps(tmp_path)
    for sid in sorted(screening_ids(ens)):
        bad = dict(maps, **{sid: {a: _write_map(tmp_path, sid, a) for a in ac.ARCHITECTURES}})
        with pytest.raises(ac.MemberRefusedError, match="SCREENING"):
            ac.compare_architectures(_specs(), _upstream(), bad, ledger=_test_only_ledger, ensemble=ens)
    with pytest.raises(ac.MemberRefusedError, match="SCREENING"):
        ac.compare_architectures(_specs(), _upstream(), {"sgb-screen-01": maps[TEST_MEMBERS[0]]},
                                 ledger=_test_only_ledger, ensemble=ens)
    # a screening candidate's map filed under an admitted id: HallMap itself refuses it
    m2 = copy.deepcopy(maps)
    m2[TEST_MEMBERS[0]]["hall_only"] = _write_map(tmp_path, TEST_MEMBERS[0], "hall_only", meta_member="sgb-screen-01",
                                                  name="screen_under_a.json")
    with pytest.raises(ac.HallMapRefusedError, match="not an admitted"):
        ac.compare_architectures(_specs(), _upstream(), m2, ledger=_test_only_ledger, ensemble=ens)
    # another admitted member's map filed under the wrong id
    m3 = copy.deepcopy(maps)
    m3[TEST_MEMBERS[0]]["hall_only"] = maps[TEST_MEMBERS[1]]["hall_only"]
    with pytest.raises(ac.MemberRefusedError, match="produced by member"):
        ac.compare_architectures(_specs(), _upstream(), m3, ledger=_test_only_ledger, ensemble=ens)
    # every admitted member must be present (no subset)
    with pytest.raises(ac.MemberRefusedError, match="every admitted member"):
        ac.compare_architectures(_specs(), _upstream(), {TEST_MEMBERS[0]: maps[TEST_MEMBERS[0]]},
                                 ledger=_test_only_ledger, ensemble=ens)
    with pytest.raises(ac.MemberRefusedError, match="not an admitted"):
        ac.compare_architectures(_specs(), _upstream(), dict(maps, unknown={}), ledger=_test_only_ledger, ensemble=ens)


def test_missing_ledger_module_raises_and_is_never_substituted(tmp_path, monkeypatch):
    ens = _test_only_ensemble()
    maps = _maps(tmp_path)
    monkeypatch.setitem(sys.modules, ac.LEDGER_MODULE, None)                       # module absent
    with pytest.raises(ac.LedgerUnavailableError, match="no substitute"):
        ac.resolve_ledger()
    with pytest.raises(ac.LedgerUnavailableError):
        ac.compare_architectures(_specs(), _upstream(), maps, ensemble=ens)
    fake = types.ModuleType(ac.LEDGER_MODULE)                                      # TEST-ONLY stand-in module
    fake.BOUNDARY_VERSION = "bus_power_boundary_v0"
    fake.bus_power_ledger = _test_only_ledger
    monkeypatch.setitem(sys.modules, ac.LEDGER_MODULE, fake)
    with pytest.raises(ac.LedgerUnavailableError, match="BOUNDARY_VERSION"):
        ac.resolve_ledger()
    fake.BOUNDARY_VERSION = "bus_power_boundary_v1"
    del fake.bus_power_ledger
    with pytest.raises(ac.LedgerUnavailableError, match="no callable"):
        ac.resolve_ledger()
    fake.bus_power_ledger = _test_only_ledger
    fn, info = ac.resolve_ledger()
    assert fn is _test_only_ledger and info["origin"] == "abep_sim.arch_boundary.bus_power_ledger"
    res = ac.compare_architectures(_specs(), _upstream(), maps, ensemble=ens)    # lazily resolved at call time
    assert res["ledger_resolution"]["module_boundary_version"] == "bus_power_boundary_v1"
    assert res["production_path"] is False                                       # injected ensemble
    def wrong_signature(a, l, e):
        return _test_only_ledger(a, l, e)
    with pytest.raises(ac.LedgerContractError, match="signature"):
        ac.resolve_ledger(wrong_signature)


# ------------------------------------------------------------------------------------------ envelopes
def test_envelope_aggregation_over_all_admitted_members(tmp_path):
    ens = _test_only_ensemble()
    scales = {TEST_MEMBERS[0]: (0.9, 1.1), TEST_MEMBERS[1]: (1.0, 1.0), TEST_MEMBERS[2]: (1.1, 0.95)}
    res = ac.compare_architectures(_specs(), _upstream(), _maps(tmp_path, scales=scales), ledger=_test_only_ledger,
                                   ensemble=ens)
    assert res["members"] == sorted(TEST_MEMBERS) and res["weighting"] == "unweighted"
    assert res["architectures"] == list(ac.ARCHITECTURES) and res["production_path"] is False
    assert res["ensemble"]["origin"] == "injected" and res["ledger_resolution"]["origin"] == "injected"
    extra = {"hall_only": {}, "rf_hall": {"rf_source": 100.0}, "ecr_hall": {"ecr_source": 120.0, "ecr_magnet": 0.0}}
    expected = {}
    for m, (ts, ps) in scales.items():                       # independent recomputation of the TEST-ONLY chain
        for a in ac.ARCHITECTURES:
            T = ts * 1e4 * 1.5e-6; Pd = ps * 2.0 * 275.0
            loads = {"hall_discharge": Pd, "hall_magnet": 10.0, "housekeeping": 5.0, "compressor": 30.0, **extra[a]}
            P_bus = sum(v / EFF[c] for c, v in loads.items())
            expected[m, a] = {"thrust_mN": T * 1e3, "P_bus_W": P_bus, "thrust_per_P_bus_mN_per_kW": T * 1e3 / (P_bus / 1e3),
                              "bus_to_anode_jet_efficiency": 0.4 * Pd / P_bus, "discharge_power_W": Pd}
            r = res["results"][m][a]
            assert r["status"] == "OK"
            for k, v in expected[m, a].items():
                assert r["metrics"][k] == pytest.approx(v, rel=1e-12)
            assert r["bus_ledger"]["residual_frac"] == 0.0 and abs(r["bus_ledger"]["residual_recomputed_frac"]) < 1e-12
            assert r["hall_map"]["ensemble_member_id"] == m
    for a in ac.ARCHITECTURES:
        env = res["envelopes"][a]
        assert env["status"] == "COMPLETE" and env["n_members"] == 3
        for k in expected[TEST_MEMBERS[0], a]:
            vals = [expected[m, a][k] for m in TEST_MEMBERS]
            assert env["metrics"][k]["min"] == pytest.approx(min(vals), rel=1e-12)
            assert env["metrics"][k]["max"] == pytest.approx(max(vals), rel=1e-12)
            assert set(env["metrics"][k]) == {"min", "max"}                      # no mean, no weighting
        rob = env["constraint_robustness"]["thrust_within_rfp_range"]
        n_true = sum(12.0 <= expected[m, a]["thrust_mN"] <= 25.0 for m in TEST_MEMBERS)
        assert rob == {"n_true": n_true, "n_members": 3, "holds_for_all_members": n_true == 3}
    pd_ = res["paired_differences"]["hall_only_minus_rf_hall"]
    d = [expected[m, "hall_only"]["P_bus_W"] - expected[m, "rf_hall"]["P_bus_W"] for m in TEST_MEMBERS]
    assert pd_["metrics"]["P_bus_W"] == {"min": pytest.approx(min(d)), "max": pytest.approx(max(d))}
    assert set(res["paired_differences"]) == {"hall_only_minus_rf_hall", "hall_only_minus_ecr_hall",
                                              "rf_hall_minus_ecr_hall"}
    # member-independence of everything upstream of (and around) the Hall block
    fps = {res["results"][m][a]["upstream_fingerprint"] for m in TEST_MEMBERS for a in ac.ARCHITECTURES}
    assert fps == {res["upstream"]["fingerprint"]}
    for a in ac.ARCHITECTURES:
        assert len({json.dumps(res["results"][m][a]["member_independent_loads_W"], sort_keys=True)
                    for m in TEST_MEMBERS}) == 1
        assert len({json.dumps(res["results"][m][a]["hall_query"], sort_keys=True) for m in TEST_MEMBERS}) == 1
    json.dumps(res)                                                               # fully reportable


def test_no_winner_or_weighted_output(tmp_path):
    res = ac.compare_architectures(_specs(), _upstream(), _maps(tmp_path), ledger=_test_only_ledger,
                                   ensemble=_test_only_ensemble())
    bad = sorted({k for k in _keys(res) if any(p in str(k).lower() for p in FORBIDDEN_KEY_PARTS)})
    assert bad == []
    assert res["weighting"] == "unweighted"
    assert not any(isinstance(v, str) and v in ac.ARCHITECTURES for v in res.values())   # no top-level single choice


def test_untrustworthy_or_out_of_domain_members_make_the_envelope_incomplete(tmp_path):
    ens = _test_only_ensemble()
    maps = _maps(tmp_path)
    maps[TEST_MEMBERS[1]]["rf_hall"] = _write_map(tmp_path, TEST_MEMBERS[1], "rf_hall", chem_ok=False,
                                                  name="chem_bad.json")
    res = ac.compare_architectures(_specs(), _upstream(), maps, ledger=_test_only_ledger, ensemble=ens)
    r = res["results"][TEST_MEMBERS[1]]["rf_hall"]
    assert r["status"] == "UNTRUSTWORTHY_HALL_POINT" and "metrics" not in r and "bus_ledger" not in r
    env = res["envelopes"]["rf_hall"]
    assert env["status"] == "INCOMPLETE" and env["metrics"] is None and env["not_ok_members"] == {
        TEST_MEMBERS[1]: "UNTRUSTWORTHY_HALL_POINT"}
    assert res["envelopes"]["hall_only"]["status"] == "COMPLETE"
    assert res["paired_differences"]["hall_only_minus_rf_hall"] == {"status": "INCOMPLETE", "metrics": None}
    assert res["paired_differences"]["hall_only_minus_ecr_hall"]["status"] == "COMPLETE"
    res2 = ac.compare_architectures(_specs(Vd=350.0), _upstream(), _maps(tmp_path), ledger=_test_only_ledger,
                                    ensemble=ens)
    assert {res2["results"][m][a]["status"] for m in TEST_MEMBERS for a in ac.ARCHITECTURES} == {"OUT_OF_MAP_DOMAIN"}
    assert {e["status"] for e in res2["envelopes"].values()} == {"INCOMPLETE"}


# ------------------------------------------------------------------------------------------ energy ledger
def test_ledger_residual_gate_and_contract(tmp_path):
    ens = _test_only_ensemble()
    maps = _maps(tmp_path)
    run = lambda led: ac.compare_architectures(_specs(), _upstream(), maps, ledger=led, ensemble=ens)
    res = run(_ledger_variant(resid_frac=0.01))                                  # 1 % < 2 %: passes, reported
    r = res["results"][TEST_MEMBERS[0]]["hall_only"]["bus_ledger"]
    assert r["residual_frac"] == pytest.approx(0.01) and r["residual_gate_frac"] == 0.02
    assert res["ledger_residual_gate_frac"] == 0.02
    with pytest.raises(ac.LedgerResidualError, match="reported"):
        run(_ledger_variant(resid_frac=0.03))                                    # reported residual 3 %
    with pytest.raises(ac.LedgerResidualError):
        run(_ledger_variant(resid_frac=-0.025))                                  # gated by magnitude, either sign
    with pytest.raises(ac.LedgerResidualError, match="recomputed"):
        run(_ledger_variant(total_scale=1.03))                                   # items do not add up to P_bus
    with pytest.raises(ac.LedgerContractError, match="bus power"):
        run(_ledger_variant(total_scale=0.5))                                    # bus below delivered load
    with pytest.raises(ac.LedgerContractError, match="common boundary"):
        run(_ledger_variant(version="some_other_boundary"))
    with pytest.raises(ac.LedgerContractError, match="book exactly"):
        run(_ledger_variant(drop_item=True))
    def refusing(arch, loads, efficiencies):
        raise ValueError("TEST-ONLY refusal")
    with pytest.raises(ac.LedgerContractError, match="TEST-ONLY refusal"):
        run(refusing)
    def wrong_arch(arch, loads, efficiencies):
        return dict(_test_only_ledger(arch, loads, efficiencies), architecture="hall_only")
    with pytest.raises(ac.LedgerContractError, match="answered for"):
        run(wrong_arch)


# ------------------------------------------------------------------------------------------ scope / inputs
def test_scope_guards_nuisance_and_upstream_leak(tmp_path):
    ens = _test_only_ensemble()
    maps = _maps(tmp_path)
    go = lambda specs=None, up=None, m=None: ac.compare_architectures(specs or _specs(), up or _upstream(), m or maps,
                                                                     ledger=_test_only_ledger, ensemble=ens)
    nuis = sorted(ens["calibration_nuisance"])
    assert "p5_registration" in nuis
    for n in nuis:
        with pytest.raises(ac.ScopeViolationError, match="nuisance"):
            go(up=_upstream(**{n: 1.0}))
        with pytest.raises(ac.ScopeViolationError, match="nuisance"):
            go(specs=[_spec("hall_only", hall_operating_point={"Vd": 275.0, n: 1.0})])
    with pytest.raises(ac.ScopeViolationError, match="Hall-map output"):
        go(up=_upstream(thrust_N=0.02))                                          # Hall result fed upstream
    with pytest.raises(ac.ScopeViolationError, match="Hall-map outputs"):
        go(specs=[_spec("rf_hall", feed={"discharge_power_W": 1.0})])
    # a map using a nuisance variable as an axis is refused by HallMap
    axes = dict(AXES, p5_registration=[0.0, 1.0])
    m2 = copy.deepcopy(maps)
    m2[TEST_MEMBERS[0]]["hall_only"] = _write_map(tmp_path, TEST_MEMBERS[0], "hall_only", axes=axes, name="nax.json")
    with pytest.raises(ac.HallMapRefusedError, match="calibration-nuisance"):
        go(m=m2)
    m3 = copy.deepcopy(maps)                                                     # facility maps are not flight maps
    m3[TEST_MEMBERS[2]]["ecr_hall"] = _write_map(tmp_path, TEST_MEMBERS[2], "ecr_hall", facility=True, name="fac.json")
    with pytest.raises(ac.HallMapRefusedError, match="facility_ingestion"):
        go(m=m3)
    m4 = copy.deepcopy(maps)                                                     # one chemistry basis per comparison
    m4[TEST_MEMBERS[2]]["ecr_hall"] = _write_map(tmp_path, TEST_MEMBERS[2], "ecr_hall", reaction_set="other",
                                                 name="rs.json")
    with pytest.raises(ac.HallMapRefusedError, match="reaction sets"):
        go(m=m4)
    with pytest.raises(ac.HallMapRefusedError, match="axes"):                    # unbound map axis
        go(specs=[_spec("hall_only", hall_axis_bindings={})])
    with pytest.raises(ac.SpecError, match="unknown quantities"):
        go(specs=[_spec("hall_only", hall_axis_bindings={"mdot_kgps": "not_there"})])
    with pytest.raises(ac.SpecError, match="both"):
        go(specs=[_spec("hall_only", fixed_loads_W={"hall_discharge": 1.0, "hall_magnet": 10.0, "housekeeping": 5.0})])
    with pytest.raises(ac.SpecError, match="power field"):
        go(specs=[_spec("hall_only", hall_load_fields={"hall_discharge": "thrust_N"})])
    with pytest.raises(ac.SpecError):
        _spec("hall_only", efficiencies=dict(EFF, hall_discharge=0.0))
    with pytest.raises(ac.SpecError):
        _spec("grids_only")                                                      # not a compared architecture
    with pytest.raises(ac.HallMapRefusedError, match="file paths"):
        go(m={m: {a: object() for a in ac.ARCHITECTURES} for m in TEST_MEMBERS})


def test_mass_closure_is_exact_when_declared(tmp_path):
    ens = _test_only_ensemble()
    maps = _maps(tmp_path)
    up = _upstream(mdot_air=1.6e-6)
    closure = {"supply": ["mdot_air"], "hall_axes": ["mdot_kgps"], "other_sinks": ["mdot_cathode"]}
    ok = _spec("hall_only", hall_axis_bindings={"mdot_kgps": "mdot_hall"},
               feed={"mdot_hall": 1.5e-6, "mdot_cathode": 0.1e-6}, mass_closure=closure)
    res = ac.compare_architectures([ok], up, maps, ledger=_test_only_ledger, ensemble=ens)
    assert res["mass_closure"]["hall_only"]["declared"] is True
    assert abs(res["mass_closure"]["hall_only"]["residual"]) <= 1e-9 * 1.6e-6
    bad = _spec("hall_only", hall_axis_bindings={"mdot_kgps": "mdot_hall"},
                feed={"mdot_hall": 1.5e-6, "mdot_cathode": 0.2e-6}, mass_closure=closure)
    with pytest.raises(ac.SpecError, match="mass closure"):
        ac.compare_architectures([bad], up, maps, ledger=_test_only_ledger, ensemble=ens)
    res2 = ac.compare_architectures([_spec("hall_only")], _upstream(), maps, ledger=_test_only_ledger, ensemble=ens)
    assert res2["mass_closure"]["hall_only"]["declared"] is False                  # reported, not silent
    assert res2["maps_not_used"] == {m: ["ecr_hall", "rf_hall"] for m in TEST_MEMBERS}


def test_upstream_state_from_gas_path_and_drag(tmp_path):
    gas = {"mdot_air": 1.5e-6, "comp_power": 30.0, "alt": 200, "solar": "mean", "atmosphere": "TEST-ONLY"}
    u = ac.UpstreamState.from_gas_path(gas, "TEST-ONLY gas-path dict")
    assert dict(u.quantities) == {"mdot_air": 1.5e-6, "comp_power": 30.0, "alt": 200.0}
    assert dict(u.labels) == {"solar": "mean", "atmosphere": "TEST-ONLY"}
    assert u.fingerprint() == ac.UpstreamState.from_gas_path(dict(gas), "TEST-ONLY gas-path dict").fingerprint()
    with pytest.raises(TypeError):
        u.quantities["mdot_air"] = 1.0                                            # read-only after construction
    with pytest.raises(ac.SpecError, match="not dropped silently"):
        ac.UpstreamState.from_gas_path(dict(gas, flag=True), "x")
    with pytest.raises(ac.SpecError, match="source"):
        ac.UpstreamState({"mdot_air": 1.0}, "")
    with pytest.raises(ac.SpecError, match="drag_source"):
        ac.UpstreamState({"mdot_air": 1.0}, "x", drag_N=0.01)
    with pytest.raises(ac.SpecError, match="exactly one"):
        ac.upstream_from_archengine(area_m2=0.7, alpha=0.8, L_over_d=5, alt_km=200, solar="mean", blade_coating_um=50)
    ud = ac.UpstreamState({"mdot_air": 1.5e-6, "comp_power": 30.0}, "TEST-ONLY", drag_N=0.014,
                          drag_source="TEST-ONLY drag")
    res = ac.compare_architectures(_specs(), ud, _maps(tmp_path), ledger=_test_only_ledger,
                                   ensemble=_test_only_ensemble())
    r = res["results"][TEST_MEMBERS[0]]["hall_only"]
    assert r["metrics"]["thrust_minus_drag_mN"] == pytest.approx(15.0 - 14.0)
    assert r["rfp_flags"]["thrust_exceeds_drag"] is True
    assert "thrust_minus_drag_mN" in res["paired_differences"]["hall_only_minus_rf_hall"]["metrics"]


def test_hall_map_index_binds_maps_to_the_admission_record(tmp_path):
    dsha = "ab" * 32                                                              # TEST-ONLY decision hash
    ens = _test_only_ensemble(decision_sha=dsha)
    maps = _maps(tmp_path)
    def index(members, decision=dsha, corrupt=False):
        rec = {m: {"admission_decision_sha256": decision,
                   "maps": {a: {"path": os.path.basename(p), "sha256": ("0" * 64) if corrupt else
                                ac._file_sha256(p)} for a, p in maps.get(m, maps[TEST_MEMBERS[0]]).items()}}
               for m in members}
        p = tmp_path / "index.json"
        p.write_text(json.dumps({"schema": ac.HALL_MAP_INDEX_SCHEMA, "members": rec}))
        return str(p)
    idx = ac.load_hall_map_index(index(TEST_MEMBERS), ensemble=ens)
    assert set(idx) == set(TEST_MEMBERS) and all(os.path.isabs(e["path"]) for v in idx.values() for e in v.values())
    res = ac.compare_architectures(_specs(), _upstream(), idx, ledger=_test_only_ledger, ensemble=ens)
    assert all(res["results"][m][a]["hall_map"]["sha256_verified_against_record"]
               for m in TEST_MEMBERS for a in ac.ARCHITECTURES)
    with pytest.raises(ac.MemberRefusedError, match="admission record"):
        ac.load_hall_map_index(index(TEST_MEMBERS, decision="cd" * 32), ensemble=ens)
    with pytest.raises(ac.MemberRefusedError, match="SCREENING"):
        ac.load_hall_map_index(index(TEST_MEMBERS + ("sgb-screen-02",)), ensemble=ens)
    bad = ac.load_hall_map_index(index(TEST_MEMBERS, corrupt=True), ensemble=ens)
    with pytest.raises(ac.HallMapRefusedError, match="sha256"):
        ac.compare_architectures(_specs(), _upstream(), bad, ledger=_test_only_ledger, ensemble=ens)


def test_harness_ships_no_synthetic_provider():
    """Defaults are the frozen ensemble and the lazily imported boundary ledger; nothing synthetic is in the module."""
    import inspect
    sig = inspect.signature(ac.compare_architectures)
    assert sig.parameters["ledger"].default is None and sig.parameters["ensemble"].default is None
    src = open(ac.__file__).read()
    assert "TEST-ONLY" not in src and "synthetic" not in src.lower()
    assert ac.LEDGER_RESIDUAL_MAX_FRAC == 0.02 and ac.EXPECTED_BOUNDARY_VERSION == "bus_power_boundary_v1"

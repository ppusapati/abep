"""A9.9 S2.2 (F1Q-04) + A9.13 S6.2: intake surface v2 build specification (build BLOCKED pending the registered AOCS
relative-wind pointing envelope) and fail-closed behaviour of the frozen v1 surface outside its domain."""
import hashlib
import math

import pandas as pd
import pytest

from abep_sim import intake_surface_v2_spec as V2
from abep_sim.atmosphere import atmosphere
from abep_sim.intake import IntakeParams, _tpmc_surface, collection
from abep_sim.intake_tpmc import IntakeSurface, frozen_surface_build_atmosphere, frozen_surface_path


# ----------------------------------------------------------------------------------------------- v2 specification
def test_v2_angular_axis_is_tbd_aocs_and_build_refuses():
    sp = V2.spec()
    assert sp["axes"]["theta_deg"]["values"] == V2.TBD_AOCS == "TBD_AOCS_POINTING_ENVELOPE"
    st = V2.v2_build_status()
    assert st["status"] == V2.BLOCKED_STATUS == "BLOCKED_PENDING_AOCS_POINTING_ENVELOPE"
    assert st["unregistered"][0] == "theta_deg"
    with pytest.raises(V2.IntakeSurfaceV2Blocked, match="BLOCKED_PENDING_AOCS_POINTING_ENVELOPE"):
        V2.build_intake_surface_v2()
    with pytest.raises(V2.IntakeSurfaceV2Blocked):
        V2.build_intake_surface_v2(n=100, thetas=(0.0, 2.0, 5.0))     # no way to pass v1's 0-5 deg as the envelope


def test_v2_spec_carries_every_required_item():
    sp = V2.spec()
    ax, rq = sp["axes"], sp["requirements"]
    assert ax["species"]["values"] == ["O", "N2", "O2"]
    assert ax["scattering"]["values"] == ["maxwell", "cll"] and rq["separate_scattering_scenarios"] is True
    assert rq["species_resolved"] is True and rq["retain_v1_unchanged"] is True
    for k in ("deterministic_seeds", "convergence_criterion", "retained_per_row", "provenance", "cross_check",
              "fail_closed_outside_domain", "production_switch"):
        assert rq[k]
    assert "held_out_states" in rq["cross_check"] and "build_states" in rq["cross_check"]
    assert "unresolved_fraction" in rq["retained_per_row"] and "converged" in rq["retained_per_row"]
    assert sp["retained_dataset"] == "intake_surface_v1" and sp["target_dataset"] == "intake_surface_v2"
    # nothing numeric is invented for the unregistered axes
    for k in ("atmosphere_state", "L_over_d", "phi", "alpha"):
        assert ax[k]["values"] == V2.TBD_REG
    assert len(V2.spec_sha256()) == 64 and V2.spec_sha256() == V2.spec_sha256()


def test_v2_spec_is_a_copy():
    sp = V2.spec(); sp["axes"]["theta_deg"]["values"] = [0, 5]
    assert V2.v2_build_status()["status"] == V2.BLOCKED_STATUS


def test_point_seed_deterministic_and_order_independent():
    a = V2.point_seed({"theta_deg": 2.0, "L_over_d": 5, "species": "O", "scattering": "cll"})
    b = V2.point_seed({"scattering": "cll", "species": "O", "L_over_d": 5, "theta_deg": 2.0})
    c = V2.point_seed({"theta_deg": 2.0, "L_over_d": 5, "species": "N2", "scattering": "cll"})
    assert a == b != c and 0 <= a < 2 ** 63
    with pytest.raises(ValueError):
        V2.point_seed({})


def test_v1_frozen_files_untouched_by_spec():
    import json
    p = frozen_surface_path(); meta = json.load(open(p.replace(".csv", ".json")))
    assert hashlib.sha256(open(p, "rb").read()).hexdigest()[:16] == meta["sha256_16"]


# ----------------------------------------------------------------------------------------- v1 fail-closed domain
def _surf():
    df = pd.read_csv(frozen_surface_path())
    return IntakeSurface(df[df.scattering == "maxwell"].reset_index(drop=True),
                         m_mean_build_kg=frozen_surface_build_atmosphere()["m_mean"])


FR = {"O": 0.5, "N2": 0.45, "O2": 0.05}


@pytest.mark.parametrize("args", [(2.0, 0.85, 0.5, 0.0), (25.0, 0.85, 0.5, 0.0), (5.0, 0.7, 0.5, 0.0),
                                  (5.0, 0.95, 0.5, 0.0), (5.0, 0.85, -0.01, 0.0), (5.0, 0.85, 1.01, 0.0),
                                  (5.0, 0.85, 0.5, 5.5), (5.0, 0.85, 0.5, -1.0), (5.0, 0.85, float("nan"), 0.0),
                                  (5.0, 0.85, 0.5, float("inf"))])
def test_v1_surface_refuses_outside_frozen_axes(args):
    with pytest.raises(ValueError, match="extrapolation"):
        _surf()(*args, fractions=FR)


def test_v1_surface_domain_and_edges():
    S = _surf(); d = S.domain()
    assert d["axes"]["theta_deg"] == [0.0, 5.0] and d["axes"]["alpha"] == [0.0, 1.0]
    r = S(20.0, 0.9, 1.0, 5.0, fractions=FR)          # corner of the domain is inside, finite
    assert all(math.isfinite(r[k]) for k in ("eta_c", "C_D", "CR_passive", "K_back"))


def test_v1_surface_refuses_foreign_species():
    with pytest.raises(ValueError, match="not in the frozen table"):
        _surf()(5.0, 0.85, 0.5, 0.0, fractions={"O": 0.5, "N2": 0.4, "He": 0.1})
    _surf()(5.0, 0.85, 0.5, 0.0, fractions={"O": 0.5, "N2": 0.5, "He": 0.0})   # zero fraction is harmless


def test_collection_no_longer_clamps_pointing_or_accommodation():
    """Finding FE-01: intake.collection used min(off_axis_deg, 5) and clipped accommodation to [0, 1]; both now fail
    closed in IntakeSurface (A9.13 S6.2 'never extrapolate silently beyond the frozen angular domain')."""
    a = atmosphere(200.0, "mean", use_msis=False)
    ok = collection(IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5, off_axis_deg=5.0), a)
    assert math.isfinite(ok["eta_c"])
    for kw in ({"off_axis_deg": 7.0}, {"accommodation": 1.2}, {"accommodation": -0.1}):
        p = dict(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5); p.update(kw)
        with pytest.raises(ValueError, match="extrapolation"):
            collection(IntakeParams(**p), a)


def test_in_domain_values_unchanged_by_fail_closed_check():
    a = atmosphere(200.0, "mean", use_msis=False)
    S = _tpmc_surface(a, "maxwell")
    fr = {"O": a["fO"], "N2": a["fN2"], "O2": a["fO2"]}
    c = collection(IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5, off_axis_deg=2.0), a)
    r = S(5, 0.85, 0.8, 2.0, fractions=fr)
    assert c["eta_c"] == r["eta_c"] and c["C_D"] == r["C_D"]

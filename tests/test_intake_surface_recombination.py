"""A9.9 S2.1 / F1Q-01 (finding F1-01): IntakeSurface recombines species rows by their physical definitions.

C_D: mass-weighted species-own coefficients (rows rescaled from the build-mixture q), CR_passive: mole-weighted,
collection: species-resolved. Pre-fix (mass-weighted rows) values are pinned as historical evidence.
"""
import math

import pandas as pd
import pytest

from abep_sim.constants import K_B, M_SPECIES
from abep_sim.intake import IntakeParams, _tpmc_surface, collection
from abep_sim.intake_tpmc import IntakeSurface, frozen_surface_build_atmosphere, frozen_surface_path

NODE = (10.0, 0.9, 1.0, 0.0)          # F1-01 node: L/d 10, phi 0.9, alpha 1, theta 0 (maxwell, build state h200_f150)


def _build_fractions():
    a = frozen_surface_build_atmosphere()
    return a, {"O": a["fO"], "N2": a["fN2"], "O2": a["fO2"]}


def _toy_df():
    """Two-species synthetic table on a 2x2x2x2 grid with values constant per species (interpolation exact)."""
    rows = []
    vals = {"O": dict(eta_c=0.6, C_D=1.5, CR_passive=200.0, K_back=0.2, mass_kg=1.0),
            "N2": dict(eta_c=0.4, C_D=2.8, CR_passive=100.0, K_back=0.3, mass_kg=1.0)}
    for sp, v in vals.items():
        for ld in (3, 10):
            for ph in (0.8, 0.9):
                for al in (0.0, 1.0):
                    for th in (0.0, 5.0):
                        rows.append(dict(v, species=sp, L_over_d=ld, phi=ph, alpha=al, theta_deg=th, unresolved_fraction=0.0))
    return pd.DataFrame(rows), vals


def test_build_m_mean_matches_table_solid_face_identity():
    """The frozen rows were normalised by q of the frozen build atmosphere: the solid-face term (1 - phi) of C_D,
    2 (m_s/m_b) (1 + sqrt(pi k T_w / 2 m_s) / V) at theta 0, recovers m_b from the table to < 1e-8."""
    a = frozen_surface_build_atmosphere()
    df = pd.read_csv(frozen_surface_path())
    for sp in ("O", "N2", "O2"):
        d = df[(df.species == sp) & (df.scattering == "maxwell") & (df.alpha == 0.5) & (df.theta_deg == 0) & (df.L_over_d == 10)]
        c8 = float(d[d.phi == 0.8].C_D.iloc[0]); c9 = float(d[d.phi == 0.9].C_D.iloc[0])
        c_solid = c9 - 0.9 * (c9 - c8) / 0.1
        m = M_SPECIES[sp]
        m_b = 2 * m * (1 + math.sqrt(math.pi * K_B * 350.0 / (2 * m)) / a["V"]) / c_solid
        assert m_b / a["m_mean"] == pytest.approx(1.0, abs=1e-8)


def test_species_table_requires_build_mass():
    df, _ = _toy_df()
    with pytest.raises(ValueError, match="m_mean_build_kg"):
        IntakeSurface(df)


@pytest.mark.parametrize("sc", ["maxwell", "cll"])
@pytest.mark.parametrize("sp", ["O", "N2", "O2"])
def test_pure_species_reduces_to_species_row(sc, sp):
    a, _ = _build_fractions()
    S = _tpmc_surface(a, sc)
    r = S(*NODE, fractions={sp: 1.0})
    row = {k: float(f(*NODE)) for k, f in S.f[sp].items()}
    assert r["eta_c"] == row["eta_c"]
    assert r["CR_passive"] == row["CR_passive"]
    assert r["K_back"] == pytest.approx(row["K_back"], rel=1e-14)   # effusion-weight ratio, fp only
    assert r["mass_kg"] == row["mass_kg"]
    # species' own coefficient: row rescaled from the build-mixture q to q_s
    assert r["C_D"] == pytest.approx(row["C_D"] * a["m_mean"] / M_SPECIES[sp], rel=1e-15)
    assert r["species"][sp]["mole_fraction"] == 1.0 and r["species"][sp]["collected_mass_fraction"] == 1.0


def test_mixture_hand_computed():
    df, v = _toy_df()
    m_b = 4.0e-26
    S = IntakeSurface(df, m_mean_build_kg=m_b)
    w = {"O": 0.4, "N2": 0.6}
    r = S(5.0, 0.85, 0.5, 2.0, fractions=w)
    mO, mN = M_SPECIES["O"], M_SPECIES["N2"]
    nO, nN = 0.4 / mO, 0.6 / mN
    xO, xN = nO / (nO + nN), nN / (nO + nN)
    assert r["C_D"] == pytest.approx(m_b * (0.4 / mO * 1.5 + 0.6 / mN * 2.8), rel=1e-12)
    assert r["C_D"] == pytest.approx((xO * 1.5 + xN * 2.8) * m_b / (xO * mO + xN * mN), rel=1e-12)
    assert r["CR_passive"] == pytest.approx(xO * 200.0 + xN * 100.0, rel=1e-12)
    assert r["eta_c"] == pytest.approx(0.4 * 0.6 + 0.6 * 0.4, rel=1e-12)
    eO, eN = xO * 200.0 / math.sqrt(mO), xN * 100.0 / math.sqrt(mN)
    assert r["K_back"] == pytest.approx((eO * 0.2 + eN * 0.3) / (eO + eN), rel=1e-12)
    assert r["species"]["O"]["collected_mass_fraction"] == pytest.approx(0.4 * 0.6 / 0.48, rel=1e-12)
    # legacy (historical) convention on the same table: plain mass weights
    old = S.call_legacy_mass_weighted(5.0, 0.85, 0.5, 2.0, fractions=w)
    assert old["C_D"] == pytest.approx(0.4 * 1.5 + 0.6 * 2.8) and old["CR_passive"] == pytest.approx(0.4 * 200 + 0.6 * 100)


def test_f1_01_pre_and_post_fix_values_pinned():
    """Historical evidence: at the F1-01 node the pre-fix recombination gave C_D x1.0802 and CR_passive x1.0654
    relative to the species-consistent recombination (F1 synthesis). Pin pre/post values from the frozen v1 table."""
    a, fr = _build_fractions()
    S = _tpmc_surface(a, "maxwell")
    new = S(*NODE, fractions=fr)
    old = S.call_legacy_mass_weighted(*NODE, fractions=fr)
    assert old["C_D"] == pytest.approx(2.249551, abs=2e-6)
    assert new["C_D"] == pytest.approx(2.082565, abs=2e-6)
    assert old["CR_passive"] == pytest.approx(248.666499, abs=2e-4)
    assert new["CR_passive"] == pytest.approx(233.408212, abs=2e-4)
    assert old["C_D"] / new["C_D"] == pytest.approx(1.0802, abs=1e-4)
    assert old["CR_passive"] / new["CR_passive"] == pytest.approx(1.0654, abs=1e-4)
    assert new["eta_c"] == pytest.approx(old["eta_c"], rel=1e-14)          # mass-flow eta_c is already a mass average
    # at the build composition: C_D = sum_s x_s C_D_row,s (m_b = m_mix)
    x = {s: new["species"][s]["mole_fraction"] for s in fr}
    assert new["C_D"] == pytest.approx(sum(x[s] * new["species"][s]["C_D_row"] for s in fr), rel=1e-6)


def test_collection_species_flows_sum_to_total():
    a, fr = _build_fractions()
    c = collection(IntakeParams(area_m2=0.7, accommodation=0.8, use_tpmc=True, L_over_d=5), a)
    sp = c["mdot_collected_species"]
    assert set(sp) == {"O", "N2", "O2"}
    assert sum(sp.values()) == pytest.approx(c["mdot_collected"], rel=1e-12)
    assert collection(IntakeParams(area_m2=0.7), a)["mdot_collected_species"] is None

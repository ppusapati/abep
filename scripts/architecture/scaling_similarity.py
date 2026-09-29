#!/usr/bin/env python3
"""Lane 22 - scaling/similarity audit: P5 evidence -> the Vyovrinda 12-25 mN / < 1.5 kW Hall class.

Purpose: stop physics validated on P5 from being extrapolated blindly to Vyovrinda's own geometry. The script computes
dimensionless / similarity groups for

  * P5 at its N2 points (N1-N5, Brabston et al. JPP 2025 Table 2) and Xe points (Xe1-Xe3, Table 4), read from the
    repository case files (read-only). The unresolved P5 channel depth (32 / 38 mm) and the coil shape are layer-1
    calibration nuisance: they only widen the P5 reference ranges (marginalized) and are never a Vyovrinda option or axis;
  * the ECHT (Marchioni 2020 thesis) N2 stable runs as a class-matched context anchor, read from the repository ECHT
    evidence audit (which concludes ECHT is NOT a scoreable validation dataset; used here for similarity context only);
  * a Vyovrinda 12-25 mN analysis ENVELOPE for both RFP propellants (N2 as the air proxy, and Xe), sized with sourced,
    xenon-derived scaling relations. It is an analysis range, not a design,

and reports which groups match or diverge (and by how much), the same-hardware and common-channel dual-gas gaps (the RFP
thruster takes air and Xe through the same ionization/discharge block), a transfer register (which P5-derived
conclusions are mechanism-level and likely transferable, which are not), and what a transport-closure admission would
need before it could be applied to Vyovrinda geometry (the "design-specific Hall maps" step of CLAUDE.md).

Nothing here is a performance prediction. No Hall solver is run. No screening candidate or unadmitted closure is used as
a performance source (only the profile-coordinate CONVENTION of the screening set is read, to show why a closure is
geometry/B-topology dependent). No architecture is ranked or eliminated. The module is pure and is not wired into
archengine; goldens do not move.

Usage:
    python scripts/architecture/scaling_similarity.py            # (re)write the JSON and the Markdown report
    python scripts/architecture/scaling_similarity.py --check    # exit 1 if the committed outputs differ

Outputs (deterministic): docs/architecture_comparison/scaling/scaling_similarity.json and SCALING_SIMILARITY.md.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "docs" / "architecture_comparison" / "scaling"
JSON_PATH = OUT_DIR / "scaling_similarity.json"
MD_PATH = OUT_DIR / "SCALING_SIMILARITY.md"
SCRIPT_REL = "scripts/architecture/scaling_similarity.py"
AUDIT_ID = "scaling_similarity_v1"
CODE_BASELINE = "c53b75a"
ACCESS_DATE = "2026-09-26"
ARCHITECTURES = ("hall_only", "rf_hall", "ecr_hall")

# --------------------------------------------------------------------------------------------------------------------
# Repository inputs (read-only). Every file is sha256-pinned in the output so an upstream change is visible.
# --------------------------------------------------------------------------------------------------------------------
IN_P5 = {"N2": "hallthruster_bridge/cases/p5_n2.json", "Xe": "hallthruster_bridge/cases/p5_xenon.json"}
IN_ECHT = "hallthruster_bridge/identification/echt_n2/echt_n2_evidence_audit_v1.json"
IN_ENSEMBLE = "hallthruster_bridge/ensemble/transport_ensemble_v0.json"
IN_RATE_VALIDITY = "hallthruster_bridge/propellants/rate_validity.toml"
# Every electron-impact ionization channel of neutral N2 in the nominal reaction set (propellants/n2_n.toml), with the
# dissociative-ionization ambiguity carried as the lower/upper variant pair.
IN_RATES = {"N2_ion": "hallthruster_bridge/propellants/ionization_N2_song2023.dat",
            "N2_DI_lower": "hallthruster_bridge/propellants/dissociative_ionization_N2_lower.dat",
            "N2_DI_upper": "hallthruster_bridge/propellants/dissociative_ionization_N2_upper.dat",
            "N2_to_Nplus2": "hallthruster_bridge/propellants/dissociative_ionization_N2_to_N_Z2plus.dat",
            "N2_elastic": "hallthruster_bridge/propellants/elastic_N2_song2023.dat",
            "N_ion": "hallthruster_bridge/propellants/ionization_N.dat"}
IN_CONSTANTS = "abep_sim/constants.py"

# Other lanes' contracts: referenced by repository path only, never imported at build time (they may not exist here).
RELATED_PATHS = {
    "hall_map_spec": "docs/hallmap/",
    "hall_reference": "docs/architecture_comparison/hall_reference/",
    "bus_power_boundary": "abep_sim/arch_boundary.py",
    "comparison_harness": "abep_sim/arch_compare.py",
    "thermal_life": "abep_sim/thermal_life.py",
    "hall_sustainment_evidence": "docs/evidence/hall_sustainment/",
    "wall_life_evidence": "docs/evidence/wall_life/",
    "rf_source_evidence": "docs/evidence/rf_source/",
    "ecr_source_evidence": "docs/evidence/ecr_source/",
    "cathode_evidence": "docs/evidence/cathode/",
    "experiment_protocol": "docs/architecture_comparison/experiment_protocol/",
    "upstream_icd": "schemas/interfaces/",
    "ledgers": "schemas/ledgers/",
}


def related_contract(key: str) -> Path:
    """Lazy resolution of another lane's contract. Never called at build time; a missing contract is an error."""
    rel = RELATED_PATHS[key]
    path = REPO / rel
    if not path.exists():
        raise FileNotFoundError(f"related contract {key!r} ({rel}) is not in this checkout: it is built by another lane "
                                "and is referenced by repository path only")
    return path


# --------------------------------------------------------------------------------------------------------------------
# Open literature actually accessed for this lane (2026-09-26); sha256 of each file as fetched.
# --------------------------------------------------------------------------------------------------------------------
SOURCES = {
    "GK2008": {
        "citation": "D. M. Goebel, I. Katz, Fundamentals of Electric Propulsion: Ion and Hall Thrusters, JPL Space "
                    "Science and Technology Series, March 2008 (JPL DESCANSO open copy)",
        "url": "https://descanso.jpl.nasa.gov/SciTechBook/series1/Goebel__cmprsd_opt.pdf",
        "sha256": "a373c8a26137b7c7cd989880c303c4f6c1f84f20a11a02770047f6ba4c249e4e",
        "page_note": "printed page numbers are cited (p. 58 = PDF 70, p. 118 = PDF 130, pp. 331-337 = PDF 341-347, "
                     "pp. 475-476 = PDF 483-484)",
        "evidence_level": 5,
    },
    "DM2008": {
        "citation": "K. Dannenmayer, S. Mazouffre, 'Sizing of Hall effect thrusters with input power and thrust level: "
                    "An empirical approach', arXiv:0810.3994v2 (22 Jan 2009); the arXiv copy states 'To be published "
                    "in Journal of Technical Physics 49, vol. 3-4 (2008)' (journal version not accessed - verify)",
        "url": "https://arxiv.org/pdf/0810.3994",
        "sha256": "5fd9e6d03671a94cb26495e704af6a3cd628eb6758180e45d4852241661762bd",
        "page_note": "arXiv page numbers",
        "evidence_level": 5,
    },
    "DM2011": {
        "citation": "K. Dannenmayer, S. Mazouffre, 'Elementary Scaling Relations for Hall Effect Thrusters', "
                    "J. Propuls. Power 27(1), 236-245 (2011), doi:10.2514/1.48382 (author-hosted copy; DOI read on "
                    "p. 236)",
        "url": "https://www.aleph-zero.fr/blog/Documents/Articles/JPP_2011_Scaling%20Laws.pdf",
        "sha256": "3c97e7cdcce0dc842e4b2b5e562b888a7ba48442dc83ced70cf0cfeb38589ccf",
        "page_note": "journal page numbers",
        "evidence_level": 5,
    },
    "NIST_me": {
        "citation": "CODATA 2022 recommended value of the electron mass, NIST Reference on Constants, Units and "
                    "Uncertainty",
        "url": "https://physics.nist.gov/cgi-bin/cuu/Value?me",
        "sha256": None,
        "page_note": "value 9.109 383 7139(28) x 10^-31 kg as displayed (dynamic page; no stable hash)",
        "evidence_level": 4,
    },
}

# --------------------------------------------------------------------------------------------------------------------
# Explicit numeric inputs. Each carries value, unit, source, locator and quantity type. No hidden defaults.
# --------------------------------------------------------------------------------------------------------------------
M_E = 9.1093837139e-31  # kg, NIST_me (CODATA 2022)

LIT = {
    "n_n_critical_Xe": {
        "value": 1.2e19, "unit": "m^-3", "source": "DM2011",
        "locator": "p. 241 (critical atom density n_n,c); DM2008 p. 13 (inferred assuming an 800 K gas temperature)",
        "class": "inferred (xenon thruster database, as reported)",
        "applicability": "xenon, BN-SiO2 walls; applying it to N2 is a hypothesis (evidence level 6)"},
    "C_P_star": {
        "value": 1.2e6, "unit": "W m^-2 (P = C_P* h d)", "source": "DM2008",
        "locator": "Eq. (4.6), p. 14; Table 3, p. 19 (analytic C_P = e U_d alpha mdot / (m h d) ~ 1.1e6)",
        "class": "inferred (empirical slope of the xenon database)",
        "applicability": "xenon; the analytic form embeds the xenon mass and alpha ~ 0.9, so transfer to N2 is a "
                         "hypothesis"},
    "j_d_typical": {
        "value": [1000.0, 1500.0], "unit": "A m^-2", "source": "GK2008",
        "locator": "p. 337, below Eq. (7.2-20): 'typically in the range of 0.1 to 0.15 A/cm2'",
        "class": "inferred (reported typical range, SPT family)",
        "applicability": "xenon SPT family; transfer to N2 is a hypothesis"},
    "wall_loss_fraction": {
        "value": 0.10, "unit": "-", "source": "DM2008",
        "locator": "p. 10 (P_loss 'of about 10 % of the input power P for various Hall thruster'; Eq. 3.1 equal "
                   "split inner/outer); pp. 10-11 (the fraction decreases as size rises)",
        "class": "inferred (reported, xenon)",
        "applicability": "used only as a common reference fraction so that wall-heat-flux proxies are comparable; the "
                         "true fraction rises for smaller thrusters (DM2008 p. 11), so a smaller-channel divergence is "
                         "understated"},
    "v_n_convention": {
        "value": "v_n = sqrt(2 k_B T_n / m)", "unit": "m/s", "source": "DM2008",
        "locator": "p. 14: 'the gas temperature is 800 K ... vn = 320 m/s' for xenon, i.e. sqrt(2 k T / m)",
        "class": "assumed (convention reproduced from the source)", "applicability": "all gases"},
    "ionization_fraction_relation": {
        "value": "1 - exp(-L / lambda_i)", "unit": "-", "source": "GK2008",
        "locator": "Eq. (7.2-15), p. 335", "class": "model-derived relation (mean-field 1-D slab)",
        "applicability": "a slab of uniform n_e and T_e crossed once by neutrals"},
    "L_over_lambda_i_95pct": {
        "value": 3.0, "unit": "-", "source": "GK2008",
        "locator": "Eq. (7.2-16)-(7.2-17), p. 335 ('the plasma thickness must be at least three times the ionization "
                   "mean-free path'; lambda_i/L 'should be less than 0.33')",
        "class": "model-derived criterion", "applicability": "GK's L is the magnetized plasma thickness with the "
                                                             "channel-average n_e; see proxy diagnostic"},
    "magnetized_length_vs_channel_depth": {
        "value": "channel depth 'nearly twice the magnetized plasma length' (schematic Fig. 7-6)", "unit": "-",
        "source": "GK2008", "locator": "p. 335",
        "class": "reported (illustrative schematic)",
        "applicability": "this audit uses the physical channel length for L in every configuration, so ratios between "
                         "configurations are like-for-like; absolute L/lambda_i and r_Le/L carry the convention"},
    "alpha_xenon_database": {
        "value": [0.3, 0.96], "unit": "-", "source": "DM2008",
        "locator": "p. 12: alpha = (T/mdot) sqrt(m_i/(2 e U_d)) (Eq. 4.2, singly charged ions) 'vary between 0.3 and "
                   "0.96, not taking into account the micro thruster'; 'for an input power higher than 1 kW and an "
                   "applied voltage above 300 V ... commonly in the range 0.8 - 0.9'; the small SPT20 'exhibits the "
                   "lowest values'; Fig. 6 slope alpha = 0.89 +- 0.01",
        "class": "inferred (reported from the xenon database; same definition as alpha_app here)",
        "applicability": "xenon, BN-SiO2; context for alpha_app"},
    "B_typical_xenon_database": {
        "value": 200.0, "unit": "G", "source": "DM2011",
        "locator": "p. 242: 'Hall thrusters operate with a magnetic field strength around typically 200 G, whatever "
                   "the input power'; 'The entire topology is of relevance. To account for gradients, curvature and "
                   "position is out of the scope of this study'",
        "class": "inferred (reported, xenon database)", "applicability": "xenon; magnitude only, not topology"},
    "P5_in_xenon_database": {
        "value": 5550.0, "unit": "W", "source": "DM2008",
        "locator": "Table 2, p. 19 (P5 listed; thermal-model maximum input power, 10 % losses, T_max 900 K per the "
                   "caption); p. 13 (P5 and PPSX000 curves close to each other in Fig. 7)",
        "class": "model-derived (source thermal model), reported",
        "applicability": "shows P5 (on xenon) lies inside the xenon scaling database; the fitted relations are for "
                         "xenon operation (DM2011 p. 240)"},
    "Xe_ionization_rate_table_E1": {
        "value": {"5": 7.61e-15, "10": 3.90e-14}, "unit": "m^3/s", "source": "GK2008",
        "locator": "Table E-1, p. 476 (rates from the Appendix D cross sections averaged over a Maxwellian)",
        "class": "model-derived (evaluated cross sections -> Maxwellian average), as tabulated",
        "applicability": "used only to check the Appendix E fit implementation (xe_fit_check)"},
}

ANALYSIS = {
    "T_e_grid_eV": {
        "value": [5.0, 10.0, 20.0, 30.0], "unit": "eV", "class": "assumed (analysis grid)",
        "source": "inside the project chemistry domain T_e 2-30 eV (PINNED.toml, pre-registered); 30 eV is also the "
                  "GK2008 Appendix E xenon fit limit ('fits well up to about 30 eV', p. 476) and 5 eV its fit switch "
                  "point (p. 475). No measured channel T_e exists for P5-N2, ECHT or Vyovrinda; the simulated P5-N2 T_e "
                  "comes from unadmitted screening closures and is deliberately NOT used"},
    "T_e_search_interval_eV": {
        "value": [2.0, 30.0], "unit": "eV", "class": "assumed (project chemistry domain)",
        "source": "PINNED.toml [reaction_set].domain T_e 2-30 eV (CLAUDE.md); a required T_e above 30 eV is reported "
                  "as outside the domain, never extrapolated"},
    "T_n_K": {
        "value": [300.0, 800.0], "unit": "K", "class": "assumed (bracket)",
        "source": "300 K = ingestion reference temperature T0 of Brabston Eq. (13) as carried in the case files "
                  "(background_temperature_K); 800 K = channel gas temperature assumed by DM2008 pp. 13-14"},
    "thrust_mN": {
        "value": None, "unit": "mN", "class": "requirement (RFP as recorded in the repository; RFP text not re-read "
                                              "by this lane - verify)",
        "source": "abep_sim/constants.py RFPConstraints.thrust_min_mN / thrust_max_mN (docstring: 'Hard limits from "
                  "Part III Para 2 of the RFP'); CLAUDE.md RFP envelope 12-25 mN"},
    "power_max_W": {
        "value": None, "unit": "W", "class": "requirement (RFP as recorded in the repository - verify)",
        "source": "abep_sim/constants.py RFPConstraints.power_max_W; a TOTAL system bound, used here only as a necessary "
                  "(not sufficient) ceiling on the discharge power"},
    "match_bands": {
        "value": {"within": 2.0, "diverges": 5.0}, "unit": "factor", "class": "PROPOSED (owner decision)",
        "source": "not in the RFP or the literature; a flagging convention only. best = smallest separation between "
                  "the envelope and the reference range (1 = overlap); worst = largest distance of any envelope "
                  "configuration from the reference range. worst <= 2 MATCHES_WITHIN_2; best <= 2 < worst "
                  "DESIGN_DEPENDENT; 2 < best <= 5 DIVERGES; best > 5 STRONGLY_DIVERGES"},
}

EXIT_CODES = {"ok": 0, "diff": 1}


# --------------------------------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------------------------------
def sha256_file(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def rnd(x, sig: int = 6):
    """Round floats (recursively) to `sig` significant digits so the JSON is platform-stable."""
    if isinstance(x, bool):
        return x
    if isinstance(x, float):
        if x == 0.0 or not math.isfinite(x):
            return x
        return float(f"{x:.{sig}g}")
    if isinstance(x, dict):
        return {k: rnd(v, sig) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v, sig) for v in x]
    return x


def span(values) -> list[float]:
    vals = [float(v) for v in values]
    if not vals:
        raise ValueError("empty span")
    return [min(vals), max(vals)]


def load_constants():
    """Load abep_sim/constants.py by path (avoids importing the abep_sim package and its heavy __init__)."""
    spec = importlib.util.spec_from_file_location("abep_constants_ro", REPO / IN_CONSTANTS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = load_constants()
E = C.E_CHARGE
KB = C.K_B
M_N2 = C.M_SPECIES["N2"]
M_XE = C.M_SPECIES["Xe"]
M_N = 0.5 * M_N2  # same source (28.0 amu / 2); only used for the N+ ion-Larmor margin


# --------------------------------------------------------------------------------------------------------------------
# Rates
# --------------------------------------------------------------------------------------------------------------------
class RateTable:
    """HallThruster.jl-format rate table: the 'Energy (eV)' column is the MEAN electron energy 3/2 T_e."""

    def __init__(self, rel: str, validity: dict):
        self.rel = rel
        lines = (REPO / rel).read_text().splitlines()
        self.header = lines[0].strip()
        self.threshold_eV = float(self.header.split(":")[1])
        rows = [ln.split() for ln in lines[2:] if ln.strip()]
        self.E = [float(r[0]) for r in rows]
        self.k = [float(r[1]) for r in rows]
        entry = validity.get(Path(rel).name)
        if entry is None:
            raise KeyError(f"{rel}: no entry in {IN_RATE_VALIDITY} (missing = error, CLAUDE.md next-work 5)")
        if entry.get("status") != "verified":
            raise ValueError(f"{rel}: rate_validity status {entry.get('status')!r}, refusing an unresolved table")
        self.max_mean_energy_eV = float(entry["max_mean_energy_eV"])

    def at_Te(self, Te_eV: float) -> float:
        eps = 1.5 * Te_eV
        if eps > self.max_mean_energy_eV:
            raise ValueError(f"{self.rel}: mean energy {eps} eV beyond verified limit {self.max_mean_energy_eV} eV")
        if not (self.E[0] <= eps <= self.E[-1]):
            raise ValueError(f"{self.rel}: {eps} eV outside table")
        for i in range(1, len(self.E)):
            if eps <= self.E[i]:
                e0, e1, k0, k1 = self.E[i - 1], self.E[i], self.k[i - 1], self.k[i]
                return k0 + (k1 - k0) * (eps - e0) / (e1 - e0)
        raise AssertionError("unreachable")


def v_mean_e(Te_eV: float) -> float:
    """Mean electron thermal speed sqrt(8 e T_e / (pi m_e)) (GK2008 Eq. 3.6-12 and Appendix E)."""
    return math.sqrt(8.0 * E * Te_eV / (math.pi * M_E))


def k_iz_xe(Te_eV: float) -> float:
    """Xenon ionization rate coefficient, GK2008 Appendix E fits (p. 475); '>5 eV fit ... up to about 30 eV' (p. 476)."""
    if not (0.0 < Te_eV <= 30.0):
        raise ValueError(f"GK2008 xenon ionization fit used outside 0 < T_e <= 30 eV: {Te_eV}")
    if Te_eV < 5.0:
        s = 1e-20 * (3.97 + 0.643 * Te_eV - 0.0368 * Te_eV ** 2) * math.exp(-12.127 / Te_eV)
    else:
        s = 1e-20 * (-1.031e-4 * Te_eV ** 2 + 6.386 * math.exp(-12.127 / Te_eV))
    return s * v_mean_e(Te_eV)


def sigma_en_xe(Te_eV: float) -> float:
    """Xenon effective electron-neutral scattering cross section, GK2008 Eq. (3.6-13), p. 58 (validity range not stated)."""
    x = Te_eV / 4.0
    return 6.6e-19 * (x - 0.1) / (1.0 + x ** 1.6)


class Gas:
    def __init__(self, name, m_heavy, m_ion, k_iz_fn, k_el_fn, E_iz_eV, E_iz_source, rate_sources, ion_label):
        self.name, self.m_heavy, self.m_ion = name, m_heavy, m_ion
        self.k_iz = k_iz_fn            # Te -> (k_low, k_high) m^3/s, total ionization loss of the neutral
        self.k_el = k_el_fn            # Te -> m^3/s (nu_en / n_n)
        self.E_iz_eV, self.E_iz_source, self.rate_sources, self.ion_label = E_iz_eV, E_iz_source, rate_sources, ion_label


def build_gases():
    validity = tomllib.loads((REPO / IN_RATE_VALIDITY).read_text())
    t = {k: RateTable(v, validity) for k, v in IN_RATES.items()}

    def k_n2(Te):
        base = t["N2_ion"].at_Te(Te) + t["N2_to_Nplus2"].at_Te(Te)
        return base + t["N2_DI_lower"].at_Te(Te), base + t["N2_DI_upper"].at_Te(Te)

    xe = Gas("Xe", M_XE, M_XE, lambda Te: (k_iz_xe(Te), k_iz_xe(Te)),
             lambda Te: sigma_en_xe(Te) * v_mean_e(Te), 12.13, "GK2008 p. 118 (first ionization potential of xenon)",
             ["GK2008 Appendix E fit (p. 475) for ionization",
              "GK2008 Eqs. (3.6-12)/(3.6-13), p. 58 for electron-neutral collisions"], "Xe+")
    n2 = Gas("N2", M_N2, M_N2, k_n2, lambda Te: t["N2_elastic"].at_Te(Te), t["N2_ion"].threshold_eV,
             f"{IN_RATES['N2_ion']} header (N2 -> N2+ threshold)",
             [f"{IN_RATES['N2_ion']} (N2 -> N2+) + {IN_RATES['N2_to_Nplus2']} (N2 -> N^2+ + N) + "
              f"{IN_RATES['N2_DI_lower']} (low) / {IN_RATES['N2_DI_upper']} (high) (N2 -> N+ + N; the N2^2+ share of the "
              "tabulated column is the low/high ambiguity): every electron-impact "
              "ionization channel of neutral N2 in the nominal set (Song et al. JPCRD 2023 Table 10 columns)",
              f"{IN_RATES['N2_elastic']} (Song et al. JPCRD 2023 Table 5 MTCS) for electron-neutral collisions"],
             "N2+ (molecular ion)")
    return {"Xe": xe, "N2": n2}, t


# --------------------------------------------------------------------------------------------------------------------
# Similarity groups
# --------------------------------------------------------------------------------------------------------------------
GROUP_DEFS = [
    # id, name, definition, source of the relation, quantity type, T_e-dependent
    ("L_over_h", "channel length / width", "L / h", "DM2008 Sec. 2.1 (L, h, d); GK2008 p. 335", "geometry", False),
    ("d_over_h", "mean diameter / width", "d / h, d = r_in + r_out = (d_ext + d_int)/2",
     "DM2011 p. 241, Figs. 2-3 (h proportional to d)", "geometry", False),
    ("inv_h", "surface-to-volume proxy", "1 / h [1/m]", "DM2008 p. 11 ('the surface to volume ratio is equal to 1/h')",
     "geometry", False),
    ("n_n", "anode neutral density", "mdot / (m v_n A), A = pi d h", "DM2008 Eqs. (2.7)-(2.8)",
     "inferred (measured flow + assumed T_n)", False),
    ("n_n_over_ncXe", "neutral density / xenon critical density", "n_n / 1.2e19 m^-3", "DM2011 p. 241",
     "inferred; a hypothesis for N2", False),
    ("j_d", "discharge current density", "I_d / A [A/m^2]", "GK2008 p. 337 (0.1-0.15 A/cm^2 typical, xenon)",
     "inferred (measured)", False),
    ("P_over_hd", "power per h d", "P_d / (h d) [W/m^2]", "DM2008 Eq. (4.6) (C_P* = 1.2e6 W/m^2, xenon)",
     "inferred (measured)", False),
    ("q_wall", "wall heat-flux proxy", "f_loss P_d / (2 pi d L), f_loss = 0.10 [W/m^2]", "DM2008 p. 10, Eq. (3.1)",
     "model-derived (assumed common f_loss)", False),
    ("eps_particle", "discharge energy per injected heavy particle", "P_d m / (e mdot) [eV]",
     "energy-per-particle bookkeeping", "inferred (measured)", False),
    ("eps_over_Eiz", "energy per particle / first ionization energy", "eps_particle / E_iz", "as above", "inferred",
     False),
    ("I_d_over_I_m", "discharge current per propellant current", "I_d / (e mdot / m)", "DM2008 Eq. (4.1) (I_m)",
     "inferred (measured)", False),
    ("alpha_app", "apparent thrust conversion", "T / (mdot sqrt(2 e V_d / m_ion))", "DM2008 Eq. (4.2)",
     "inferred (measured; lumps utilization, divergence, voltage loss, species mix)", False),
    ("T_over_P", "thrust per discharge power", "T / P_d [mN/kW]", "definition", "inferred (measured)", False),
    ("tau_res", "neutral residence time", "L / v_n [s]", "GK2008 Eq. (7.2-14) (lambda_i = v_n / (n_e <sigma v>))",
     "model-derived", False),
    ("n_e_exit", "exit electron density estimate", "I_d / (e v_i A), v_i = sqrt(2 e V_d / m_ion)",
     "GK2008 Eq. (7.2-7) (I_i ~ n e v_i A_e, with I_d in place of I_i)", "model-derived", False),
    ("L_over_lambda_i", "Melikov-Morozov number", "L n_e_exit <sigma_iz v_e>(T_e) / v_n",
     "GK2008 Eqs. (7.2-14)-(7.2-17); DM2008 Eq. (2.1)", "model-derived", True),
    ("iz_fraction", "single-pass ionization fraction proxy", "1 - exp(-L / lambda_i)", "GK2008 Eq. (7.2-15)",
     "model-derived", True),
    ("rLe_over_L", "electron Larmor radius / L", "sqrt(8 m_e T_e / (pi e)) / (B L)", "GK2008 Eq. (7.2-1); DM2008 "
     "Eq. (2.11)", "model-derived", True),
    ("rLe_over_h", "electron Larmor radius / h", "r_Le / h", "Zhurin et al. criterion as reviewed in DM2008 p. 4 and "
     "DM2011 p. 237", "model-derived", True),
    ("rLi_over_L", "ion Larmor radius / L", "sqrt(2 m_ion V_d / e) / (B L) (V_d bounds the beam voltage)",
     "GK2008 Eq. (7.2-3)", "model-derived", False),
    ("hall_param_classical", "classical electron Hall parameter", "(e B / m_e) / (n_n <sigma_en v_e>(T_e))",
     "DM2008 Eq. (2.14); GK2008 Eq. (7.2-2); classical only - anomalous transport dominates (DM2008 p. 8)",
     "model-derived", True),
]
GROUP_IDS = [g[0] for g in GROUP_DEFS]
TE_GROUPS = [g[0] for g in GROUP_DEFS if g[5]]
B_GROUPS = {"rLe_over_L", "rLe_over_h", "rLi_over_L", "hall_param_classical"}
# Envelope groups that are carried from the anchors by construction (not evidence of similarity): the operating
# ratios each anchor keeps, and d/h, which is taken from the two anchor geometries.
CARRIED_GROUPS = {"alpha_app", "I_d_over_I_m", "eps_particle", "eps_over_Eiz", "T_over_P", "d_over_h"}


def v_n(m: float, Tn: float) -> float:
    return math.sqrt(2.0 * KB * Tn / m)


def v_i(gas, Vd: float) -> float:
    return math.sqrt(2.0 * E * Vd / gas.m_ion)


def groups_for(gas: Gas, *, d, h, L, mdot, Vd, Id, Pd, T_N, B, Tn, Te_grid):
    """Every similarity group for one configuration. B may be None (B-dependent groups -> None)."""
    A = math.pi * d * h
    vn = v_n(gas.m_heavy, Tn)
    nn = mdot / (gas.m_heavy * vn * A)
    vi = v_i(gas, Vd)
    ne = Id / (E * vi * A)
    I_m = E * mdot / gas.m_heavy
    eps = Pd * gas.m_heavy / (E * mdot)
    g = {
        "L_over_h": L / h, "d_over_h": d / h, "inv_h": 1.0 / h,
        "n_n": nn, "n_n_over_ncXe": nn / LIT["n_n_critical_Xe"]["value"],
        "j_d": Id / A, "P_over_hd": Pd / (h * d),
        "q_wall": LIT["wall_loss_fraction"]["value"] * Pd / (2.0 * math.pi * d * L),
        "eps_particle": eps, "eps_over_Eiz": eps / gas.E_iz_eV,
        "I_d_over_I_m": Id / I_m,
        "alpha_app": T_N / (mdot * vi),
        "T_over_P": (T_N * 1e3) / (Pd / 1e3),  # mN per kW
        "tau_res": L / vn, "n_e_exit": ne,
        "rLi_over_L": None if B is None else math.sqrt(2.0 * gas.m_ion * Vd / E) / (B * L),
    }
    per_te = {}
    for Te in Te_grid:
        k_lo, k_hi = gas.k_iz(Te)
        mm = [L * ne * k_lo / vn, L * ne * k_hi / vn]  # larger k -> shorter lambda_i -> larger L/lambda_i
        rle = math.sqrt(8.0 * M_E * Te / (math.pi * E))
        per_te[f"{Te:g}"] = {
            "L_over_lambda_i": mm,
            "iz_fraction": [1.0 - math.exp(-mm[0]), 1.0 - math.exp(-mm[1])],
            "rLe_over_L": None if B is None else rle / (B * L),
            "rLe_over_h": None if B is None else rle / (B * h),
            "hall_param_classical": None if B is None else (E * B / M_E) / (nn * gas.k_el(Te)),
        }
    g["per_Te"] = per_te
    return g


def merge_ranges(glist: list[dict]) -> dict:
    """Min/max of every group over a list of group dicts (None entries skipped; all-None -> None)."""
    out = {}
    for gid in GROUP_IDS:
        if gid in TE_GROUPS:
            continue
        vals = [g[gid] for g in glist if g.get(gid) is not None]
        out[gid] = span(vals) if vals else None
    out["per_Te"] = {}
    for te in glist[0]["per_Te"]:
        row = {}
        for gid in TE_GROUPS:
            vals = []
            for g in glist:
                v = g["per_Te"][te][gid]
                if v is not None:
                    vals.extend(v if isinstance(v, list) else [v])
            row[gid] = span(vals) if vals else None
        out["per_Te"][te] = row
    return out


# --------------------------------------------------------------------------------------------------------------------
# P5 records (read-only)
# --------------------------------------------------------------------------------------------------------------------
POINT_FIELDS = ("Vd", "mdot_kgps", "r_in_m", "r_out_m", "B_ref_T", "background_temperature_K")
MEASURED_FIELDS = ("Pd_W", "Id_A", "T_corr_mN", "T_corr_source", "T_sigma_mN")


def load_p5():
    """P5 points per gas. Only L_m, the registration and the coil shape may differ between a point's cases (they are
    layer-1 calibration nuisance); every other field must agree or the loader refuses."""
    out = {}
    for gas, rel in IN_P5.items():
        doc = json.loads((REPO / rel).read_text())
        pts = {}
        regs = {}
        for c in doc["cases"]:
            rec = {k: c[k] for k in POINT_FIELDS}
            rec.update({k: c["measured"][k] for k in MEASURED_FIELDS})
            if "Id_corr_A" in c["measured"]:
                rec["Id_corr_A"] = c["measured"]["Id_corr_A"]
            p = c["point"]
            if p in pts:
                for k, v in rec.items():
                    if pts[p]["rec"].get(k) != v:
                        raise ValueError(f"{rel}: point {p} field {k} differs across cases ({v} vs {pts[p]['rec'].get(k)})"
                                         "; only L, the registration and the coil shape may differ")
            else:
                pts[p] = {"rec": rec, "L_m": set()}
            pts[p]["L_m"].add(c["L_m"])
            bp = c["B_profile"]
            key = (c["registration"], c.get("coil_shape", Path(bp["file"]).stem.rsplit("_", 1)[-1]))
            val = {"L_m": c["L_m"], "align": bp["align"], "z_ref_in_file_mm": bp["z_ref_in_file_mm"],
                   "scale_to": bp["scale_to"], "bfield_file": "hallthruster_bridge/" + bp["file"]}
            if key in regs and regs[key] != val:
                raise ValueError(f"{rel}: registration {key} encoded inconsistently")
            regs[key] = val
        out[gas] = {"file": rel, "sha256": sha256_file(rel), "source": doc["source"],
                    "points": {p: {**v["rec"], "L_m": sorted(v["L_m"])} for p, v in sorted(pts.items())},
                    "registrations": {f"{r}|{s}": v for (r, s), v in sorted(regs.items())}}
    return out


def load_bfield_csv(rel: str):
    z, b = [], []
    for ln in (REPO / rel).read_text().splitlines():
        if ln.startswith("#") or not ln.strip() or ln.startswith("z_"):
            continue
        a, c = ln.split(",")
        z.append(float(a))
        b.append(float(c))
    return z, b


def interp_hold(z, b, x):
    """Linear interpolation, held constant beyond the data ends."""
    if x <= z[0]:
        return b[0]
    if x >= z[-1]:
        return b[-1]
    for i in range(1, len(z)):
        if x <= z[i]:
            return b[i - 1] + (b[i] - b[i - 1]) * (x - z[i - 1]) / (z[i] - z[i - 1])
    raise AssertionError


def half_max_crossings(z, b):
    bmax = max(b)
    ipk = b.index(bmax)
    half = 0.5 * bmax
    up = next((i for i in range(ipk, 0, -1) if b[i - 1] < half <= b[i]), None)
    dn = next((i for i in range(ipk, len(b) - 1) if b[i] >= half > b[i + 1]), None)
    zu = None if up is None else z[up - 1] + (half - b[up - 1]) * (z[up] - z[up - 1]) / (b[up] - b[up - 1])
    zd = None if dn is None else z[dn] + (b[dn] - half) * (z[dn + 1] - z[dn]) / (b[dn] - b[dn + 1])
    return zu, zd


def bfield_topology(registrations, ensemble_doc):
    """P5 B(z) shape per (registration, coil shape) exactly as encoded in the case files:
    z_channel = z_file - z_ref + (L if align == 'exit' else 0) (hallthruster_bridge/bridge_lib.jl, B_profile)."""
    out = {}
    centers = sorted({c["transport_parameters"]["center_L"] for c in ensemble_doc["screening_candidates"]
                      if "center_L" in c["transport_parameters"]})
    for key, r in registrations.items():
        z, b = load_bfield_csv(r["bfield_file"])
        bmax = max(b)
        zpk = z[b.index(bmax)]
        zu, zd = half_max_crossings(z, b)
        Lmm = 1e3 * r["L_m"]
        off = (Lmm if r["align"] == "exit" else 0.0) - r["z_ref_in_file_mm"]  # z_channel = z_file + off
        zpk_ch = zpk + off
        lo = max(0.0, zu + off) if zu is not None else None
        hi = min(Lmm, (zd if zd is not None else z[-1]) + off)
        out[key] = {"L_mm": Lmm, "bfield_file": r["bfield_file"], "z_peak_over_L": zpk_ch / Lmm,
                    "B_exit_over_B_peak": interp_hold(z, b, Lmm - off) / bmax,
                    "B_anode_over_B_peak": interp_hold(z, b, 0.0 - off) / bmax,
                    "fraction_of_channel_B_above_half_peak": None if lo is None else max(0.0, hi - lo) / Lmm,
                    "screening_profile_centre_minus_B_peak_over_L": span((c * Lmm - zpk_ch) / Lmm for c in centers)}
    files = {}
    for r in registrations.values():
        f = r["bfield_file"]
        if f not in files:
            z, b = load_bfield_csv(f)
            zu, zd = half_max_crossings(z, b)
            files[f] = {"sha256": sha256_file(f), "z_peak_file_mm": z[b.index(max(b))], "B_peak_unscaled_G": max(b),
                        "z_first_digitized_mm": z[0], "half_max_z_file_mm": [zu, zd],
                        "FWHM_mm": None if (zu is None or zd is None) else zd - zu}
    return {"registrations": out, "files": files, "screening_center_L_values": centers,
            "class": "digitized (Peterson, Gallimore & Haas AIAA 2001-3890 Figs. 11/12, vacuum, repository vector "
                     "extraction) + registration hypotheses (layer-1 nuisance). B_anode is held from the first "
                     "digitized point (no data at the anode face)"}


# --------------------------------------------------------------------------------------------------------------------
# ECHT anchor (read-only audit values)
# --------------------------------------------------------------------------------------------------------------------
def load_echt():
    doc = json.loads((REPO / IN_ECHT).read_text())
    g = doc["values"]["geometry"]
    L = 1e-3 * g["channel_length"]["value_mm"]
    h = 1e-3 * g["channel_height"]["value_mm"]
    r_out = 0.5e-3 * g["outer_diameter"]["value_mm"]  # reading A (audit: inferred, status 'verify')
    r_in = r_out - h
    perf = doc["values"]["performance_table_6_2"]
    unstable = set(perf["unstable_runs"])
    op_rows = doc["values"]["operating_points_table_6_1"]["rows"]
    col = doc["values"]["operating_points_table_6_1"]["columns"].index("mdot_anode_mgps")
    mdots = {r[col] for r in op_rows}
    if len(mdots) != 1:
        raise ValueError("ECHT anode flow not constant across Table 6.1")
    mdot_mgps = mdots.pop()
    mf = doc["values"]["magnetic_field"]["measured_Bz_at_2A"]
    B = 1e-4 * mf["plateau_mean_4.7_8.3cm_G"]
    points = {}
    for r in perf["rows"]:
        if r["run"] in unstable:
            continue
        for red, key in (("one_side", "T_mN"), ("averaged", "T_avg_mN")):
            if r[key] is None:
                continue
            points[f"{r['run'].replace(' ', '')}-{red}"] = {
                "Vd": float(r["Vd"]), "Id_A": float(r["Id"]), "Pd_W": float(r["P_anode_W"]), "T_mN": float(r[key]),
                "Imag_A": float(r["Imag"]), "mdot_kgps": 1e-6 * mdot_mgps, "p_Torr": r["p_Torr"], "reduction": red}
    z = [1e1 * p["z_cm"] for p in mf["points"]]
    b = [p["B_G"] for p in mf["points"]]
    zexit = 1e1 * g["exit_plane_on_Bz_axis"]["value_cm"]
    zu, zd = half_max_crossings(z, b)
    topo = {"z_peak_axis_mm": z[b.index(max(b))], "B_peak_G": max(b), "exit_on_axis_mm": zexit,
            "B_exit_over_B_peak": interp_hold(z, b, zexit) / max(b),
            "plateau_mean_G": mf["plateau_mean_4.7_8.3cm_G"], "half_max_z_axis_mm": [zu, zd],
            "note": "axis origin not defined in the source (audit); plateau 4.7-8.3 cm, not exit-peaked; the upper "
                    "half-maximum is not reached within the digitized range",
            "class": "digitized (of measured, 2 A coil current only)"}
    echt = {"file": IN_ECHT, "sha256": sha256_file(IN_ECHT), "L_m": L, "h_m": h, "r_in_m": r_in, "r_out_m": r_out,
            "B_T": B, "unstable_runs_excluded": sorted(unstable), "points": points,
            "classes": {"L, h": "measured (design dimension), S2 Sec. 4.1.1 p. 63 (via the audit)",
                        "radii": "inferred (reading A of the 100 mm OD; audit status 'verify')",
                        "V_d, I_d, P_anode, mdot": "measured (tabulated), S2 Tables 6.1/6.2 (anode flow 2.06 vs "
                                                   "2.083 mg/s ambiguity 1 %, audit)",
                        "thrust": "measured + author reduction (one-side and averaged readings both carried); facility "
                                  "pressure 0.8-2.5e-4 Torr, ingestion ~2-6 % of anode flow (audit, inferred)",
                        "B": "digitized (of measured) plateau at 2 A; the runs use 1.6-2.6 A, so B-dependent ECHT "
                             "groups are indicative only"},
            "role": "Class-matched context anchor only; the audit concludes ECHT-N2 is not usable as an independent, "
                    "scoreable validation dataset"}
    return echt, topo


# --------------------------------------------------------------------------------------------------------------------
# Anchors and the Vyovrinda analysis envelope (NOT a design)
# --------------------------------------------------------------------------------------------------------------------
def build_anchors(p5, echt):
    """Operating anchors: P5 points per gas (vacuum-corrected thrust, raw I_d = P_d/V_d) and the ECHT stable runs.
    The P5 depth bracket is carried as a list and merged downstream (marginalized), never enumerated as an option."""
    out = {"N2": {}, "Xe": {}}
    for gas in ("N2", "Xe"):
        for p, r in p5[gas]["points"].items():
            out[gas][f"P5-{p}"] = {"family": f"P5-{gas}", "Vd": r["Vd"], "mdot": r["mdot_kgps"], "Id": r["Id_A"],
                                   "Pd": r["Pd_W"], "T_N": 1e-3 * r["T_corr_mN"], "d": r["r_in_m"] + r["r_out_m"],
                                   "h": r["r_out_m"] - r["r_in_m"], "L_bracket": list(r["L_m"]), "B": r["B_ref_T"]}
    for k, r in echt["points"].items():
        out["N2"][f"ECHT-{k}"] = {"family": "ECHT", "Vd": r["Vd"], "mdot": r["mdot_kgps"], "Id": r["Id_A"],
                                  "Pd": r["Pd_W"], "T_N": 1e-3 * r["T_mN"], "d": echt["r_in_m"] + echt["r_out_m"],
                                  "h": echt["h_m"], "L_bracket": [echt["L_m"]], "B": echt["B_T"]}
    return out


L_RULES = {
    "S1_anchor_L": "absolute channel length kept equal to the anchor's (P5 32-38 mm bracket merged; ECHT 86 mm)",
    "S2_photographic": "L/h kept equal to the anchor's (pure geometric scale model of the anchor)",
    "S3_extended_ECHT": "L/h = ECHT L/h = 8.6 (extended channel for light neutrals, class-matched N2 design; for Xe, "
                        "the same N2-driven channel run on Xe)",
    "S4_MM_matched": "L chosen so that L/lambda_i equals the anchor's at equal T_e and T_n (Melikov-Morozov "
                     "similarity: lambda_i ~ 1/n_e, n_e ~ I_d/(A sqrt(V_d)), same V_d as the anchor)",
}
AREA_RULES = {
    "A_ncXe": "A = mdot/(n_n,c m v_n): the xenon critical density (DM2011 p. 241); for N2 a hypothesis",
    "A_anchor_density": "A = A_anchor mdot/mdot_anchor (anchor neutral density preserved)",
    "A_CP": "A = pi P_d / C_P* (DM2008 Eq. 4.6, xenon)",
    "A_jd": "A = I_d / j with j = 0.10 or 0.15 A/cm^2 (GK2008 p. 337, xenon)",
}
# Groups whose envelope value is imposed by the L rule (not evidence of similarity), per scenario.
SET_BY_RULE = {"S1_anchor_L": {"tau_res"}, "S2_photographic": {"L_over_h"}, "S3_extended_ECHT": {"L_over_h"},
               "S4_MM_matched": {"L_over_lambda_i"}}


def vyovrinda_envelope(gas, anchor_map, dh_refs, echt, Te_grid, Tn_grid):
    """Analysis envelope for one propellant. d/h is taken from the two anchor geometries (P5 and ECHT) as a geometric
    similarity hypothesis (DM2011 p. 241: h proportional to d across xenon thrusters; coefficient not published)."""
    rfp = C.RFP
    thrusts = [rfp.thrust_min_mN, rfp.thrust_max_mN]
    op_rows, geo_rows = [], []
    scen_groups = {s: [] for s in L_RULES}
    b_rows = {s: [] for s in L_RULES}
    for aid, a in anchor_map.items():
        vi = v_i(gas, a["Vd"])
        alpha = a["T_N"] / (a["mdot"] * vi)
        kappa = a["Id"] / (E * a["mdot"] / gas.m_heavy)
        A_anchor = math.pi * a["d"] * a["h"]
        for T_mN in thrusts:
            T_N = 1e-3 * T_mN
            mdot = T_N / (alpha * vi)
            Id = kappa * E * mdot / gas.m_heavy
            Pd = a["Vd"] * Id
            op_rows.append({"anchor": aid, "family": a["family"], "thrust_mN": T_mN, "V_d": a["Vd"], "alpha_app": alpha,
                            "I_d_over_I_m": kappa, "mdot_mgps": mdot * 1e6, "I_d_A": Id, "P_d_W": Pd,
                            "P_d_below_RFP_total_bound": Pd < rfp.power_max_W})
            areas = [("A_ncXe", f"Tn{Tn:g}", mdot / (LIT["n_n_critical_Xe"]["value"] * gas.m_heavy * v_n(gas.m_heavy, Tn)))
                     for Tn in Tn_grid]
            areas.append(("A_anchor_density", "-", A_anchor * mdot / a["mdot"]))
            areas.append(("A_CP", "-", math.pi * Pd / LIT["C_P_star"]["value"]))
            areas += [("A_jd", f"j{j:g}", Id / j) for j in LIT["j_d_typical"]["value"]]
            for (arule, avar, A), (dhn, dh) in itertools.product(areas, dh_refs.items()):
                h = math.sqrt(A / (math.pi * dh))
                d = dh * h
                jV, jA = Id / A, a["Id"] / A_anchor
                for La in a["L_bracket"]:
                    Ls = {"S1_anchor_L": La, "S2_photographic": h * La / a["h"],
                          "S3_extended_ECHT": h * echt["L_m"] / echt["h_m"],
                          "S4_MM_matched": La * jA / jV}  # same V_d and gas as the anchor -> n_e ratio = j ratio
                    for s, L in Ls.items():
                        for Tn in Tn_grid:
                            nn_V = mdot / (gas.m_heavy * v_n(gas.m_heavy, Tn) * A)
                            nn_A = a["mdot"] / (gas.m_heavy * v_n(gas.m_heavy, Tn) * A_anchor)
                            B_rle = a["B"] * La / L          # keep r_Le/L at equal T_e (DM2008 Eq. 2.13)
                            B_om = a["B"] * nn_V / nn_A      # keep classical omega/nu at equal T_e (DM2011 Eq. 8)
                            scen_groups[s].append(groups_for(gas, d=d, h=h, L=L, mdot=mdot, Vd=a["Vd"], Id=Id, Pd=Pd,
                                                             T_N=T_N, B=None, Tn=Tn, Te_grid=Te_grid))
                            b_rows[s].append((B_rle, B_om))
                        geo_rows.append({"scenario": s, "area_rule": arule, "A_m2": A, "h_m": h, "d_m": d, "L_m": L})
    geometry = {}
    for arule in AREA_RULES:
        rows = [r for r in geo_rows if r["area_rule"] == arule]
        geometry[arule] = {"A_m2": span(r["A_m2"] for r in rows), "h_mm": span(1e3 * r["h_m"] for r in rows),
                           "d_mm": span(1e3 * r["d_m"] for r in rows)}
    lengths = {s: span(1e3 * r["L_m"] for r in geo_rows if r["scenario"] == s) for s in L_RULES}
    bfield = {s: {"B_keep_rLe_over_L_G": span(1e4 * p[0] for p in pairs),
                  "B_keep_classical_hall_G": span(1e4 * p[1] for p in pairs),
                  "mismatch_factor": span(max(p) / min(p) for p in pairs)} for s, pairs in b_rows.items()}
    families = sorted({r["family"] for r in op_rows})
    op_summary = {fam: {f"{T:g}": {"mdot_mgps": span(r["mdot_mgps"] for r in op_rows if r["family"] == fam and r["thrust_mN"] == T),
                                   "I_d_A": span(r["I_d_A"] for r in op_rows if r["family"] == fam and r["thrust_mN"] == T),
                                   "P_d_W": span(r["P_d_W"] for r in op_rows if r["family"] == fam and r["thrust_mN"] == T),
                                   "all_below_RFP_total_bound": all(r["P_d_below_RFP_total_bound"] for r in op_rows
                                                                    if r["family"] == fam and r["thrust_mN"] == T)}
                        for T in thrusts} for fam in families}
    return {"thrust_mN": thrusts, "power_max_W": rfp.power_max_W, "anchor_families": families,
            "operating_rows": op_rows, "operating_summary": op_summary, "geometry_by_area_rule": geometry,
            "L_by_scenario_mm": lengths, "B_required_by_scenario": bfield,
            "groups_by_scenario": {s: merge_ranges(v) for s, v in scen_groups.items()},
            "row_counts": {"operating": len(op_rows), "geometry": len(geo_rows),
                           "group_evaluations": sum(len(v) for v in scen_groups.values())}}


# --------------------------------------------------------------------------------------------------------------------
# Dual-gas analysis: the RFP thruster takes air (N2 proxy) and Xe through the same ionization/discharge block
# --------------------------------------------------------------------------------------------------------------------
def required_Te(k_fn, target: float, lo: float, hi: float):
    """Smallest T_e in [lo, hi] with k_fn(T_e) >= target (k monotone increasing); None if k_fn(hi) < target."""
    if k_fn(lo) >= target:
        return lo
    if k_fn(hi) < target:
        return None
    a, b = lo, hi
    for _ in range(80):
        m = 0.5 * (a + b)
        if k_fn(m) >= target:
            b = m
        else:
            a = m
    return b


def dual_gas(gases, anchors, Te_grid, Te_search):
    n2, xe = gases["N2"], gases["Xe"]
    lo_T, hi_T = Te_search
    # monotonicity of the N2 total ionization rate on the search interval (required by the bisection)
    scan = [lo_T + i * (hi_T - lo_T) / 280 for i in range(281)]
    for which in (0, 1):
        ks = [n2.k_iz(t)[which] for t in scan]
        if any(k1 < k0 for k0, k1 in zip(ks, ks[1:])):
            raise AssertionError("N2 ionization rate not monotone on the T_e search interval")
    mass_factor = math.sqrt(M_N2 / M_XE)  # v_n(Xe)/v_n(N2) at equal T_n

    def pair_metrics(aN, aX, equal_thrust: bool):
        viN, viX = v_i(n2, aN["Vd"]), v_i(xe, aX["Vd"])
        if equal_thrust:  # same thrust for both gases, each at its anchor's alpha_app and I_d/I_m: mdot = T/(alpha v_i)
            mN = aN["mdot"] / aN["T_N"]  # per newton of thrust (thrust cancels in every ratio)
            mX = aX["mdot"] / aX["T_N"]
            IN = aN["Id"] / aN["mdot"] * mN
            IX = aX["Id"] / aX["mdot"] * mX
        else:  # as measured on the same hardware
            mN, mX, IN, IX = aN["mdot"], aX["mdot"], aN["Id"], aX["Id"]
        ne_ratio = (IN / viN) / (IX / viX)       # same A
        pref = ne_ratio * mass_factor            # (n_e/v_n)_N2 / (n_e/v_n)_Xe at equal T_n; L cancels
        nn_ratio = (mN / M_N2) / (mX / M_XE) * mass_factor
        return {"mdot": mN / mX, "I_d": IN / IX, "P_d": (aN["Vd"] * IN) / (aX["Vd"] * IX), "n_n": nn_ratio,
                "n_e_exit": ne_ratio, "prefactor": pref}

    out = {}
    cases = {"P5_same_hardware_as_measured": ([a for a in anchors["N2"].values() if a["family"] == "P5-N2"], False),
             "common_channel_equal_thrust_P5N2_vs_P5Xe": ([a for a in anchors["N2"].values() if a["family"] == "P5-N2"], True),
             "common_channel_equal_thrust_ECHT_vs_P5Xe": ([a for a in anchors["N2"].values() if a["family"] == "ECHT"], True)}
    xe_anchors = list(anchors["Xe"].values())
    for name, (n_anchors, eq) in cases.items():
        ms = [pair_metrics(aN, aX, eq) for aN in n_anchors for aX in xe_anchors]
        ratios = {k: span(m[k] for m in ms) for k in ms[0]}
        pref = ratios["prefactor"]
        lam = {}
        for Te in Te_grid:
            k_lo, k_hi = n2.k_iz(Te)
            kx = k_iz_xe(Te)
            lam[f"{Te:g}"] = {"L_over_lambda_i_ratio_N2_over_Xe": [pref[0] * k_lo / kx, pref[1] * k_hi / kx],
                              "B_ratio_for_equal_classical_hall_param": [ratios["n_n"][0] * n2.k_el(Te) / xe.k_el(Te),
                                                                         ratios["n_n"][1] * n2.k_el(Te) / xe.k_el(Te)]}
        req = {}
        for TeX in Te_grid:
            target_hi = k_iz_xe(TeX) / pref[0]   # smallest prefactor -> largest k needed
            target_lo = k_iz_xe(TeX) / pref[1]
            t_min = required_Te(lambda t: n2.k_iz(t)[1], target_lo, lo_T, hi_T)   # upper DI variant, best case
            t_max = required_Te(lambda t: n2.k_iz(t)[0], target_hi, lo_T, hi_T)   # lower DI variant, worst case
            req[f"{TeX:g}"] = {"Te_N2_min_eV": t_min, "Te_N2_max_eV": t_max,
                               "exceeds_30eV_domain": "all" if t_min is None else ("part" if t_max is None else "none")}
        out[name] = {"ratios_N2_over_Xe": ratios, "per_Te": lam, "Te_N2_required_to_match_Xe_L_over_lambda_i": req,
                     "pairs": len(ms)}
    out["definitions"] = {
        "prefactor": "(n_e_exit / v_n)_N2 / (n_e_exit / v_n)_Xe with n_e_exit = I_d/(e v_i A) on the same A and T_n; "
                     "L cancels, so the P5 depth bracket does not enter",
        "equal_thrust": "each gas at the same thrust with its anchor's alpha_app and I_d/I_m (thrust cancels in every "
                        "ratio); geometry-independent",
        "Te_N2_required": "T_e at which N2 reaches the Xe L/lambda_i on the same channel, bisection on the N2 table "
                          "rates inside the project domain T_e 2-30 eV; None = not reached inside the domain"}
    return out


def proxy_diagnostic(p5_groups, echt_all, Te_grid):
    """Absolute proxy vs measured alpha_app: shows why no absolute L/lambda_i threshold is used as a gate."""
    out = {}
    for name, g in (("P5-Xe", p5_groups["Xe"]["all_points"]), ("P5-N2", p5_groups["N2"]["all_points"]),
                    ("ECHT-N2", echt_all)):
        rows = {}
        for Te in Te_grid:
            te = f"{Te:g}"
            mm = g["per_Te"][te]["L_over_lambda_i"]
            iz = g["per_Te"][te]["iz_fraction"]
            rows[te] = {"L_over_lambda_i_proxy": mm, "iz_fraction_proxy": iz,
                        "meets_GK_L_over_lambda_i_3": mm[1] >= LIT["L_over_lambda_i_95pct"]["value"],
                        "proxy_max_below_alpha_app_min": iz[1] < g["alpha_app"][0]}
        out[name] = {"alpha_app_measured": g["alpha_app"], "per_Te": rows}
    return out


# --------------------------------------------------------------------------------------------------------------------
# Comparison / verdicts
# --------------------------------------------------------------------------------------------------------------------
def divergence(v, ref):
    """(best, worst): best = smallest ratio separating the ranges (1 if they overlap); worst = largest distance of any
    envelope value from the reference range (1 if the envelope lies inside it)."""
    if v is None or ref is None:
        return None, None
    if min(v[0], ref[0]) <= 0.0:
        raise ValueError("divergence needs positive ranges")
    if v[1] < ref[0]:
        best = ref[0] / v[1]
    elif v[0] > ref[1]:
        best = v[0] / ref[1]
    else:
        best = 1.0
    worst = max(1.0, ref[0] / v[0], v[1] / ref[1])
    return best, worst


def verdict(best, worst, constructed: bool) -> str:
    if constructed:
        return "SET_BY_CONSTRUCTION"
    if best is None:
        return "NOT_COMPARABLE"
    b = ANALYSIS["match_bands"]["value"]
    if worst <= b["within"]:
        return "MATCHES_WITHIN_2"
    if best <= b["within"]:
        return "DESIGN_DEPENDENT"
    if best <= b["diverges"]:
        return "DIVERGES"
    return "STRONGLY_DIVERGES"


def compare(ref_range, ctx_range, scen, ctx_name):
    table = {}
    for s, gr in scen.items():
        rows = {}
        keys = [(gid, None) for gid in GROUP_IDS if gid not in TE_GROUPS] + \
               [("L_over_lambda_i", te) for te in gr["per_Te"]]
        for gid, te in keys:
            if te is None:
                v, r = gr.get(gid), ref_range.get(gid)
                c = None if ctx_range is None else ctx_range.get(gid)
                label = gid
            else:
                v, r = gr["per_Te"][te][gid], ref_range["per_Te"][te][gid]
                c = None if ctx_range is None else ctx_range["per_Te"][te][gid]
                label = f"{gid}@Te{te}"
            constructed = gid in CARRIED_GROUPS or gid in SET_BY_RULE.get(s, set())
            best, worst = divergence(v, r)
            row = {"vyovrinda": v, "reference": r, "best": best, "worst": worst,
                   "verdict": verdict(best, worst, constructed)}
            if ctx_range is not None:
                cb, cw = divergence(v, c)
                row.update({ctx_name: c, f"best_vs_{ctx_name}": cb, f"worst_vs_{ctx_name}": cw,
                            f"verdict_vs_{ctx_name}": verdict(cb, cw, constructed)})
            rows[label] = row
        table[s] = rows
    return table


RISK_ORDER = ["MATCHES_WITHIN_2", "DESIGN_DEPENDENT", "DIVERGES", "STRONGLY_DIVERGES"]


def group_flags(comparison):
    """Per-group transfer-risk flag over the L-rule scenarios (computed, PROPOSED convention)."""
    out = {}
    labels = list(next(iter(comparison.values())).keys())
    for lab in labels:
        vs = [comparison[s][lab]["verdict"] for s in comparison]
        graded = [v for v in vs if v in RISK_ORDER]
        if not graded:
            flag = "NOT_ASSESSED (" + "/".join(sorted(set(vs))) + ")"
        elif all(v == "MATCHES_WITHIN_2" for v in graded):
            flag = "LOW"
        elif any(v in ("DIVERGES", "STRONGLY_DIVERGES") for v in graded):
            flag = "HIGH"
        else:
            flag = "MEDIUM"
        out[lab] = {"verdicts_by_scenario": dict(zip(comparison.keys(), vs)), "risk_flag": flag}
    return out


# --------------------------------------------------------------------------------------------------------------------
# Transfer register (judgement recorded as data; consistency-checked against the computed verdicts)
# --------------------------------------------------------------------------------------------------------------------
TRANSFER_REGISTER = [
    {"id": "TR-01", "quantity": "N2 vs Xe ionization-length ratio at equal n_e, T_e, T_n",
     "transferability": "MECHANISM_LEVEL_TRANSFERABLE", "risk": "LOW", "depends_on_groups": [],
     "why": "a gas property (cross sections and neutral speed), independent of thruster geometry and of any transport "
            "closure. Absolute lambda_i does NOT transfer (it needs the Vyovrinda channel n_e and T_e).",
     "evidence_needed": "none for the ratio; channel n_e and T_e (measured, or from an admitted closure) for absolute "
                        "values"},
    {"id": "TR-02", "quantity": "N2 needs a larger n_e L (longer channel or hotter electrons) than Xe for the same "
                                "L/lambda_i", "transferability": "MECHANISM_LEVEL_TRANSFERABLE", "risk": "LOW",
     "depends_on_groups": [],
     "why": "follows from TR-01 and GK2008 Eq. (7.2-19) and p. 336 (lighter propellants need a longer ionization region "
            "for high utilization); the ECHT extended channel (L/h = 8.6, measured design dimension) is consistent",
     "evidence_needed": "a Vyovrinda design release (L, h, B(z)); no number transfers"},
    {"id": "TR-03", "quantity": "ions unmagnetized (r_Li >> L)", "transferability": "MECHANISM_LEVEL_TRANSFERABLE",
     "risk": "LOW", "depends_on_groups": ["rLi_over_L"],
     "why": "the margin shrinks with sqrt(m_ion) (N2+ and N+ vs Xe+) but stays >> 1 for every P5 and ECHT case (checked "
            "by the script); it must be re-evaluated for the actual Vyovrinda B and L",
     "evidence_needed": "Vyovrinda B(z) and L"},
    {"id": "TR-04", "quantity": "electron magnetization requirement r_Le << L, h and Hall parameter >> 1",
     "transferability": "REQUIREMENT_TRANSFERS_VALUES_DO_NOT", "risk": "MEDIUM",
     "depends_on_groups": ["rLe_over_L", "hall_param_classical"],
     "why": "the criterion is generic; its value is set by the Vyovrinda B and L. r_Le/L similarity (B ~ 1/L) and "
            "classical-Hall-parameter similarity (B ~ n_n) demand different B across the envelope (B mismatch "
            "factor), so both cannot be matched to P5 at once",
     "evidence_needed": "Vyovrinda magnetic-circuit design and measured B(z)"},
    {"id": "TR-05", "quantity": "low apparent thrust conversion alpha_app for N2 (vs Xe)",
     "transferability": "PLANNING_RANGE_ONLY", "risk": "MEDIUM", "depends_on_groups": ["alpha_app"],
     "why": "both N2 datasets (P5-N2 {alpha_p5n2}, ECHT {alpha_echt}) sit in the lower part of the xenon database "
            "alpha range (0.3-0.96, DM2008 p. 12) or below it, and below P5-Xe ({alpha_p5xe}) on the same hardware: "
            "consistent with a gas-level effect, but both are facility-affected and ECHT is not scoreable. Used here "
            "only to derive the envelope flow range",
     "evidence_needed": "Vyovrinda thrust-stand data (level 1) or an admitted closure evaluated on Vyovrinda geometry"},
    {"id": "TR-06", "quantity": "thrust per discharge power T/P_d (either gas)", "transferability": "NOT_TRANSFERABLE",
     "risk": "HIGH", "depends_on_groups": ["T_over_P"],
     "why": "size- and voltage-dependent (DM2008 p. 12 and Fig. 4: efficiency increases with size; DM2011 p. 240: V/S = "
            "h/2); ECHT/P5-N2 T/P ratio {tp_ratio}. The envelope carries each anchor's T/P unchanged, which is "
            "itself this unverified transfer",
     "evidence_needed": "Vyovrinda hardware or an admitted closure on Vyovrinda geometry, through the common bus-power "
                        "boundary (bus_power_boundary_v1)"},
    {"id": "TR-07", "quantity": "discharge current per propellant current I_d/I_m", "transferability": "NOT_TRANSFERABLE",
     "risk": "HIGH", "depends_on_groups": ["I_d_over_I_m", "eps_particle"],
     "why": "P5-N2/ECHT ratio {idim_ratio}; it sets the energy per particle and hence T_e and the chemistry domain",
     "evidence_needed": "as TR-06"},
    {"id": "TR-08", "quantity": "anomalous-transport closure (any ScaledGaussianBohm set; any P5-identified profile)",
     "transferability": "NOT_TRANSFERABLE", "risk": "HIGH",
     "depends_on_groups": ["rLe_over_L", "hall_param_classical", "L_over_h", "n_n"],
     "why": "the screening closures were selected on P5 geometry and a P5 B(z) under registration hypotheses, with the "
            "profile stored in channel-length units; the same L-unit centre sits at different positions relative to "
            "the B peak even across the P5 registrations. B topology is not captured by the scaling laws (DM2011 "
            "p. 242; DM2008 p. 16) and differs qualitatively (P5 exit-peaked vs ECHT plateau). The credible set is "
            "empty (gate 3 FAIL) and the candidates' own applicability_domain is 'P5-like channel'",
     "evidence_needed": "the admission requirements for design-specific Hall maps (AR list)"},
    {"id": "TR-09", "quantity": "absolute I_d, thrust, efficiency, oscillation regime from any P5-calibrated model",
     "transferability": "NOT_TRANSFERABLE", "risk": "HIGH", "depends_on_groups": ["j_d", "n_n", "L_over_h"],
     "why": "all absolute Hall numbers are withdrawn (CLAUDE.md); geometry and density groups are design-dependent or "
            "diverge",
     "evidence_needed": "admitted closure + Vyovrinda geometry + class-matched validation"},
    {"id": "TR-10", "quantity": "wall heat flux, wall erosion and lifetime", "transferability": "NOT_TRANSFERABLE",
     "risk": "HIGH", "depends_on_groups": ["q_wall", "inv_h", "P_over_hd"],
     "why": "surface-to-volume 1/h rises as the channel shrinks and the wall-loss fraction rises with it (DM2008 "
            "p. 11); > 15,000 h firing needs Vyovrinda-specific wall evidence",
     "evidence_needed": "wall_life_trustworthy maps on Vyovrinda geometry (ion_wall_losses = true, WallSheath) and "
                        "hardware erosion data (wall-life evidence matrix, other lane)"},
    {"id": "TR-11", "quantity": "chemistry-domain mechanism (the 45-eV-capped N2 table family fires together when "
                                "T_e > 30 eV)", "transferability": "MECHANISM_LEVEL_TRANSFERABLE", "risk": "MEDIUM",
     "depends_on_groups": ["eps_particle", "eps_over_Eiz"],
     "why": "a property of the reaction set, not of P5; whether a Vyovrinda point reaches T_e > 30 eV depends on its "
            "energy per particle and geometry, which differ between the anchors (see also TR-15)",
     "evidence_needed": "chemistry_trustworthy runs on Vyovrinda geometry; O/O2 chemistry for air (does not exist)"},
    {"id": "TR-12", "quantity": "facility neutral ingestion is material for N2 tests",
     "transferability": "EXPERIMENT_PROTOCOL_ONLY", "risk": "LOW", "depends_on_groups": [],
     "why": "Brabston Eq. (13) corrections and the ECHT audit estimate (2-6 % of anode flow) both show it; relevant to "
            "how Vyovrinda tests are corrected, not to flight performance",
     "evidence_needed": "facility characterization in the experiment protocol (other lane)"},
    {"id": "TR-13", "quantity": "P5 calibration nuisance resolutions (registration, coil shape, divergence reading, "
                                "facility interpretation)", "transferability": "NOT_APPLICABLE", "risk": "NONE",
     "depends_on_groups": [], "why": "layer 1 describes what the P5 experiment WAS; it is never a Vyovrinda design "
                                     "variable, map axis or trade dimension (CLAUDE.md); here it only widens P5 ranges",
     "evidence_needed": "none"},
    {"id": "TR-14", "quantity": "critical neutral density (xenon database) as an N2 sizing target",
     "transferability": "HYPOTHESIS", "risk": "MEDIUM", "depends_on_groups": ["n_n_over_ncXe"],
     "why": "P5-N2 ({nn_p5n2} n_n,c) and ECHT ({nn_echt} n_n,c) both sit at or above the xenon critical density; the "
            "DM2008/DM2011 relations are fitted on xenon operation (DM2011 p. 240: 'we focus on Hall thrusters equipped "
            "with BN-SiO2 channel walls and operating with xenon'), so no N2 value is established",
     "evidence_needed": "an N2/air Hall database or Vyovrinda parametric tests"},
    {"id": "TR-15", "quantity": "dual-gas operation of one channel (air/N2 and Xe through the same discharge block)",
     "transferability": "MECHANISM_LEVEL_TRANSFERABLE", "risk": "MEDIUM", "depends_on_groups": [],
     "why": "P5 ran both gases on the same hardware: at equal T_e the N2 L/lambda_i proxy is a fraction of the Xe value "
            "(dual_gas), so one channel cannot be Melikov-Morozov-similar to P5 for both gases unless the N2 T_e is "
            "higher (the required T_e is reported, and can exceed the 30 eV chemistry domain). The mechanism is P5's "
            "own measured pair; its magnitude for Vyovrinda needs Vyovrinda n_e, T_e",
     "evidence_needed": "a Vyovrinda design that states which gas sets L, and hardware tests on both propellants"},
    {"id": "TR-16", "quantity": "pre-ionized Hall inflow (rf_hall, ecr_hall)", "transferability": "NOT_COVERED_BY_P5",
     "risk": "HIGH", "depends_on_groups": [],
     "why": "P5 (and ECHT) had neutral-only anode injection; an inlet ion/excited fraction is an extra similarity "
            "dimension that the P5 evidence does not span, and the 1-D solver has no ion-inflow capability (Hall "
            "reference, other lane: GAP). This is an evidence-coverage statement, not a performance ranking: whether "
            "pre-ionization helps or hurts is outside this audit",
     "evidence_needed": "the inlet state at HALL_INLET_Z0 (Hall reference / upstream ICD), a solver ion-inflow "
                        "capability, and rf/ecr source evidence (rf_source, ecr_source matrices)"},
    {"id": "TR-17", "quantity": "Xe-mode sizing from the xenon scaling database (P5-Xe as anchor)",
     "transferability": "PLANNING_RANGE_ONLY", "risk": "MEDIUM", "depends_on_groups": ["alpha_app", "n_n_over_ncXe"],
     "why": "the xenon relations apply to the Xe mode within their database (evidence level 5) and P5 is itself in "
            "the DM2008 database (Table 2); but P5-Xe runs at P_d {pd_p5xe} W and V_d {vd_p5xe} V, while DM2008 p. 12 "
            "reports alpha 0.8-0.9 only for P > 1 kW and U > 300 V and the lowest alpha for the smallest thruster, so "
            "P5-Xe conversion is not a sub-kW Vyovrinda value",
     "evidence_needed": "Vyovrinda Xe thrust-stand data or an admitted closure on Vyovrinda geometry"},
]


def register_facts(p5_groups, echt_all, p5, env) -> dict:
    """Data-dependent statements of the transfer register, computed (and their premises asserted) so the text cannot
    drift from the inputs."""
    a_n2, a_echt, a_xe = (p5_groups["N2"]["all_points"]["alpha_app"], echt_all["alpha_app"],
                          p5_groups["Xe"]["all_points"]["alpha_app"])
    nn_n2, nn_echt = p5_groups["N2"]["all_points"]["n_n_over_ncXe"], echt_all["n_n_over_ncXe"]
    tp_n2, tp_echt = p5_groups["N2"]["all_points"]["T_over_P"], echt_all["T_over_P"]
    im_n2, im_echt = p5_groups["N2"]["all_points"]["I_d_over_I_m"], echt_all["I_d_over_I_m"]
    lo_db, hi_db = LIT["alpha_xenon_database"]["value"]
    if not (max(a_n2[1], a_echt[1]) < a_xe[0] and max(a_n2[1], a_echt[1]) < 0.5 * (lo_db + hi_db)):
        raise AssertionError("TR-05 premise violated: N2 alpha_app not in the lower part of the xenon range / below P5-Xe")
    if min(nn_n2[0], nn_echt[0]) < 1.0:
        raise AssertionError("TR-14 premise violated: an N2 anchor below the xenon critical density")
    pd_xe = span(r["Pd_W"] for r in p5["Xe"]["points"].values())
    vd_xe = span(r["Vd"] for r in p5["Xe"]["points"].values())
    env_xe_pd = max(w["P_d_W"][1] for fam in env["Xe"]["operating_summary"].values() for w in fam.values())
    if not (pd_xe[0] > 1000.0 and env_xe_pd < 1000.0):
        raise AssertionError("TR-17 premise violated: P5-Xe not above 1 kW or the Xe envelope not sub-kW")
    return {"alpha_p5n2": fmt(a_n2), "alpha_echt": fmt(a_echt), "alpha_p5xe": fmt(a_xe),
            "nn_p5n2": fmt(nn_n2), "nn_echt": fmt(nn_echt),
            "tp_ratio": fmt([tp_echt[0] / tp_n2[1], tp_echt[1] / tp_n2[0]]),
            "idim_ratio": fmt([im_n2[0] / im_echt[1], im_n2[1] / im_echt[0]]),
            "pd_p5xe": fmt(pd_xe), "vd_p5xe": fmt(vd_xe)}


def filled_register(facts: dict) -> list[dict]:
    return [{**tr, "why": tr["why"].format(**facts)} for tr in TRANSFER_REGISTER]


def check_register(comparisons) -> list[str]:
    """A LOW-risk register entry may not depend on a group that DIVERGES or STRONGLY_DIVERGES in any scenario of any
    gas (groups set by construction or not comparable are exempt)."""
    problems = []
    for tr in TRANSFER_REGISTER:
        if tr["risk"] != "LOW":
            continue
        for gid in tr["depends_on_groups"]:
            for gas, comp in comparisons.items():
                for s, rows in comp.items():
                    for lab, row in rows.items():
                        if lab.split("@")[0] == gid and row["verdict"] in ("DIVERGES", "STRONGLY_DIVERGES"):
                            problems.append(f"{tr['id']} is LOW but {lab} {row['verdict']} ({gas}, {s})")
    return problems


ADMISSION_REQUIREMENTS = [
    {"id": "AR-1", "requirement": "At least one ADMITTED transport member (promotion rule: predicts new evidence not "
     "used to select it, without retuning, a <= 1/16). Today the credible set is empty.", "status": "NOT MET",
     "source": "CLAUDE.md next-work 1; hallthruster_bridge/ensemble/transport_ensemble_v0.json admission_rule"},
    {"id": "AR-2", "requirement": "O4 staged-sensitivity dispositions complete (hall_ensemble._check_o4).",
     "status": "NOT MET", "source": "CLAUDE.md next-work 3"},
    {"id": "AR-3", "requirement": "A released Vyovrinda geometry and B(z) (versioned, sha256, not P5/ECHT files); one "
     "map set per member and geometry revision.", "status": "NOT MET (no design release)",
     "source": "CLAUDE.md next-work 1 (flow) and 5; Hall-map spec (docs/hallmap/, other lane)"},
    {"id": "AR-4", "requirement": "A pre-registered TRANSFER CONVENTION for the closure's profile coordinates: as "
     "stored (channel-length units, anchored at the anode) versus re-anchored to the Vyovrinda B-peak position. "
     "Decided before any Vyovrinda map is run; the other convention is carried as a transfer sensitivity (not a "
     "layer-1 nuisance, never a tuning knob). Recorded in the map set's validity_domain transfer statement.",
     "status": "PROPOSED (owner decision)",
     "source": "this audit (the L-unit profile centre moves relative to the B peak across P5 registrations); Hall-map "
               "spec (docs/hallmap/, other lane) transfer-hypothesis statement"},
    {"id": "AR-5", "requirement": "A SIMILARITY-DOMAIN CHECK per map point: the groups of this audit are computed for "
     "the Vyovrinda point and compared, as ratios, with the envelope of the evidence that admitted the member (never "
     "against absolute thresholds: see the proxy diagnostic). Points outside are flagged EXTRAPOLATED (evidence "
     "level 6, docs/EVIDENCE.md) and cannot carry milestone-B envelopes on their own. Group list and tolerances "
     "pre-registered with the admission.", "status": "PROPOSED (owner decision)",
     "source": "this audit; docs/EVIDENCE.md levels 6-7"},
    {"id": "AR-6", "requirement": "Class-matched validation: at least one dataset in the Vyovrinda similarity regime "
     "(N2/air, h of order 1 cm, 12-25 mN) predicted without retuning under pre-registered criteria. ECHT-N2 cannot "
     "serve (audit); the route is Vyovrinda component/thruster hardware (evidence level 1).", "status": "NOT MET",
     "source": "docs/EVIDENCE.md closure path; ECHT audit conclusion"},
    {"id": "AR-7", "requirement": "chemistry_trustworthy on every map point (T_e <= 30 eV domain unless a v2 domain "
     "extension is pre-registered on independent evidence) and an O/O2 reaction set for air.",
     "status": "NOT MET (O/O2 absent)", "source": "CLAUDE.md next-work 2, 3, 4, 5"},
    {"id": "AR-8", "requirement": "wall_life_trustworthy maps (ion_wall_losses = true, WallSheath, unshielded) for any "
     "erosion/life use, with wall-model evidence at the Vyovrinda wall-heat-flux level.", "status": "NOT MET",
     "source": "CLAUDE.md next-work 5"},
    {"id": "AR-9", "requirement": "Both propellants: a member admitted on N2 evidence says nothing about the Vyovrinda "
     "Xe mode and vice versa (TR-15). Each map set is per propellant, and admission evidence must exist for each "
     "propellant it is used on.", "status": "PROPOSED (owner decision)",
     "source": "this audit (dual_gas); Hall-map spec (propellant is a discrete label)"},
    {"id": "AR-10", "requirement": "For rf_hall / ecr_hall: a solver ion-inflow capability and an inlet-state "
     "similarity check (TR-16) before any map with pre-ionized inflow; until then those points are refused, not "
     "evaluated with pre-ionization dropped.", "status": "NOT MET (solver GAP)",
     "source": "Hall reference (docs/architecture_comparison/hall_reference/, other lane); Hall-map spec"},
    {"id": "AR-11", "requirement": "No retuning on Vyovrinda geometry; the member's parameters and physical prior are "
     "inherited unchanged; Hall-closure uncertainty stays inside the ionization/discharge -> acceleration block.",
     "status": "STANDING RULE", "source": "CLAUDE.md next-work 1 (scope)"},
]

MILESTONES = {
    "A": {"support": "SUPPORTS",
          "contribution": "Shows which P5 conclusions may appear in a conditional selection (mechanism-level: TR-01..03, "
                          "TR-11, TR-12, TR-15) and which may not (all absolute Hall numbers, T/P, I_d/I_m, closures). "
                          "It turns the similarity gaps into demonstrable conditions, e.g. 'N2/air Hall sustainment at the "
                          "Vyovrinda channel scale with L/lambda_i and r_Le/L in a stated range, on both propellants'. "
                          "It applies identically to hall_only, rf_hall and ecr_hall (common Hall accelerator); TR-16 "
                          "records only that pre-ionized inflow is outside the P5 evidence. No Physics Baseline 1.0 needed.",
          "to_next": "owner decisions on the PROPOSED items (match bands, AR-4, AR-5, AR-9); a Vyovrinda geometry/B(z) "
                     "release to replace the analysis envelope"},
    "B": {"support": "PARTIAL",
          "contribution": "Defines the similarity-domain check (AR-5), the transfer convention (AR-4) and the per-propellant "
                          "admission scope (AR-9) that must hold before an admitted closure produces design-specific Hall "
                          "maps; supplies the group definitions and reference ranges.",
          "to_next": "AR-1, AR-2, AR-3, AR-6, AR-7, AR-10 met; groups recomputed on the released design"},
    "C": {"support": "NOT SUPPORTED (risk list only)",
          "contribution": "Flags wall heat flux / surface-to-volume, B topology and dual-gas operation as scale risks for "
                          "life and performance closure.",
          "to_next": "hardware: measured B(z) of the flight-like circuit, wall/erosion data, integrated tests on both "
                     "propellants (AR-8)"},
}


# --------------------------------------------------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------------------------------------------------
def build() -> dict:
    gases, tables = build_gases()
    Te_grid = ANALYSIS["T_e_grid_eV"]["value"]
    Te_search = ANALYSIS["T_e_search_interval_eV"]["value"]
    Tn_grid = ANALYSIS["T_n_K"]["value"]
    p5 = load_p5()
    ens = json.loads((REPO / IN_ENSEMBLE).read_text())
    echt, echt_topo = load_echt()

    # ---- P5 groups per point; the depth bracket (32/38 mm) and T_n are merged into ranges ----
    p5_groups = {}
    for gname, rec in p5.items():
        gas = gases[gname]
        per_point, allg = {}, []
        for p, r in rec["points"].items():
            gl = [groups_for(gas, d=r["r_in_m"] + r["r_out_m"], h=r["r_out_m"] - r["r_in_m"], L=L,
                             mdot=r["mdot_kgps"], Vd=r["Vd"], Id=r["Id_A"], Pd=r["Pd_W"], T_N=1e-3 * r["T_corr_mN"],
                             B=r["B_ref_T"], Tn=Tn, Te_grid=Te_grid)
                  for L, Tn in itertools.product(r["L_m"], Tn_grid)]
            per_point[p] = merge_ranges(gl)
            allg += gl
        p5_groups[gname] = {"per_point": per_point, "all_points": merge_ranges(allg)}

    # ---- ECHT groups ----
    echt_list, echt_pts = [], {}
    for k, r in echt["points"].items():
        gl = [groups_for(gases["N2"], d=echt["r_in_m"] + echt["r_out_m"], h=echt["h_m"], L=echt["L_m"],
                         mdot=r["mdot_kgps"], Vd=r["Vd"], Id=r["Id_A"], Pd=r["Pd_W"], T_N=1e-3 * r["T_mN"],
                         B=echt["B_T"], Tn=Tn, Te_grid=Te_grid) for Tn in Tn_grid]
        echt_pts[k] = merge_ranges(gl)
        echt_list += gl
    echt_all = merge_ranges(echt_list)

    # ---- Gas transfer factor lambda_i(N2)/lambda_i(Xe) at equal n_e, T_e, T_n; xenon fit check ----
    vratio = math.sqrt(M_XE / M_N2)  # v_n(N2)/v_n(Xe) at equal T_n
    gas_factor = {}
    for Te in Te_grid:
        k_lo, k_hi = gases["N2"].k_iz(Te)
        kx = k_iz_xe(Te)
        gas_factor[f"{Te:g}"] = {"k_iz_Xe_m3s": kx, "k_iz_N2_m3s": [k_lo, k_hi],
                                 "k_iz_N_atom_m3s": tables["N_ion"].at_Te(Te),
                                 "lambda_ratio_N2_over_Xe": [vratio * kx / k_hi, vratio * kx / k_lo]}
    xe_fit_check = {te: {"fit_m3s": k_iz_xe(float(te)), "table_E1_m3s": v,
                         "fit_over_table": k_iz_xe(float(te)) / v}
                    for te, v in LIT["Xe_ionization_rate_table_E1"]["value"].items()}

    # ---- Anchors, dual-gas, envelopes, comparison ----
    id_corr_rel = span(1.0 - r["Id_corr_A"] / r["Id_A"] for r in p5["N2"]["points"].values())
    anchors = build_anchors(p5, echt)
    r1 = p5["N2"]["points"]["N1"]
    dh_refs = {"P5": (r1["r_in_m"] + r1["r_out_m"]) / (r1["r_out_m"] - r1["r_in_m"]),
               "ECHT": (echt["r_in_m"] + echt["r_out_m"]) / echt["h_m"]}
    dual = dual_gas(gases, anchors, Te_grid, Te_search)
    env = {g: vyovrinda_envelope(gases[g], anchors[g], dh_refs, echt, Te_grid, Tn_grid) for g in ("N2", "Xe")}
    comparison = {"N2": compare(p5_groups["N2"]["all_points"], echt_all, env["N2"]["groups_by_scenario"], "echt"),
                  "Xe": compare(p5_groups["Xe"]["all_points"], None, env["Xe"]["groups_by_scenario"], "echt")}
    flags = {g: group_flags(c) for g, c in comparison.items()}
    problems = check_register(comparison)
    if problems:
        raise AssertionError("transfer register inconsistent with computed verdicts: " + "; ".join(problems))
    # r_Li >> L check behind TR-03 (every configuration where B is known)
    rli_min = min(x["rLi_over_L"][0] for x in [p5_groups["N2"]["all_points"], p5_groups["Xe"]["all_points"], echt_all])
    if rli_min <= 1.0:
        raise AssertionError("TR-03 premise violated: r_Li/L <= 1")
    r3 = p5["N2"]["points"]["N3"]
    rli_nplus = math.sqrt(2.0 * M_N * r3["Vd"] / E) / (r3["B_ref_T"] * max(r3["L_m"]))

    topo = {"P5": bfield_topology(p5["N2"]["registrations"], ens), "ECHT": echt_topo,
            "screening_structure_note": "Only the transport family and the profile-coordinate convention (center_L, "
            "width_L in channel-length units) of the screening candidates in " + IN_ENSEMBLE + " are read, to show "
            "the geometry dependence; no screening candidate is used as a performance source",
            "screening_width_L_values": sorted({c["transport_parameters"].get("width_L")
                                                for c in ens["screening_candidates"]}),
            "admitted_members": len(ens["members"])}
    for key, val in p5["Xe"]["registrations"].items():
        if p5["N2"]["registrations"].get(key) != val:
            raise ValueError(f"P5-Xe registration {key} is not encoded identically in {IN_P5['N2']}")

    inputs = {
        "repository_files": {rel: sha256_file(rel) for rel in
                             [*IN_P5.values(), *sorted({r["bfield_file"] for r in p5["N2"]["registrations"].values()}),
                              IN_ECHT, IN_ENSEMBLE, IN_RATE_VALIDITY, *IN_RATES.values(), IN_CONSTANTS]},
        "p5": {g: {"file": v["file"], "source": v["source"], "points": v["points"],
                   "registrations": v["registrations"]} for g, v in p5.items()},
        "p5_classes": {"r_in_m, r_out_m": "measured design dimensions as recorded (Hofer 2004 Sec. 5.3.1 via the case "
                                          "file source string)",
                       "L_m": "UNRESOLVED 32 vs 38 mm (layer-1 nuisance): a bracket of what P5 was, merged into the "
                              "P5 ranges",
                       "Vd, mdot, Pd_W, B_ref_T": "measured (Brabston 2025 Tables 2/4; evidence level 3); B_ref is the "
                                                  "reported peak radial B at channel centre / exit plane",
                       "Id_A": "inferred (P_d / V_d, as measured in the facility; the case files' Eq. 14 vacuum "
                               f"correction lowers the N2 I_d by {fmt([100 * x for x in id_corr_rel])} % and is not "
                               "applied here)",
                       "T_corr_mN": "reconstructed / digitized + reconstructed (facility-corrected thrust, see case "
                                    "files)"},
        "echt": echt,
        "constants": {"e": E, "k_B": KB, "m_e": M_E, "m_N2": M_N2, "m_Xe": M_XE, "m_N": M_N,
                      "sources": {"e, k_B, amu, species masses (N2 28.0 amu, Xe 131.3 amu)": IN_CONSTANTS,
                                  "m_e": "NIST_me"}},
        "literature": LIT,
        "analysis": {**ANALYSIS,
                     "thrust_mN": {**ANALYSIS["thrust_mN"], "value": [C.RFP.thrust_min_mN, C.RFP.thrust_max_mN]},
                     "power_max_W": {**ANALYSIS["power_max_W"], "value": C.RFP.power_max_W}},
        "gases": {k: {"E_iz_eV": g.E_iz_eV, "E_iz_source": g.E_iz_source, "rate_sources": g.rate_sources,
                      "ion_mass_for_v_i": g.ion_label} for k, g in gases.items()},
    }

    doc = {
        "id": AUDIT_ID,
        "lane": "22 scaling/similarity: P5 evidence -> Vyovrinda 12-25 mN class",
        "status": "ANALYSIS ONLY. No Hall solver run, no performance prediction, no closure transfer claimed, no "
                  "architecture ranked or eliminated. Vyovrinda numbers are an analysis ENVELOPE from sourced "
                  "(xenon-derived) scaling relations, not a design.",
        "generated_by": SCRIPT_REL, "code_baseline": CODE_BASELINE, "sources_accessed": ACCESS_DATE,
        "architectures": list(ARCHITECTURES),
        "architecture_note": "The groups describe the downstream Hall accelerator, which is common to all three arms. "
                             "The rf_hall / ecr_hall arms change only the pre-ionization upstream of the Hall inlet; that "
                             "acts on the ionization-length group through the inlet state, which the P5 evidence does "
                             "not span (TR-16). No arm is ranked or eliminated.",
        "milestones": MILESTONES,
        "sources": SOURCES, "inputs": inputs,
        "group_definitions": [{"id": g[0], "name": g[1], "definition": g[2], "relation_source": g[3],
                               "quantity_type": g[4], "T_e_dependent": g[5]} for g in GROUP_DEFS],
        "p5_groups": p5_groups, "echt_groups": {"per_point": echt_pts, "all_points": echt_all},
        "gas_transfer_factor": gas_factor, "xe_fit_check": xe_fit_check,
        "dual_gas": dual,
        "proxy_diagnostic": proxy_diagnostic(p5_groups, echt_all, Te_grid),
        "ion_larmor_N_plus_at_P5_N3_L38": rli_nplus,
        "b_field_topology": topo,
        "vyovrinda_envelope": {"area_rules": AREA_RULES, "L_rules": L_RULES, "d_over_h_refs": dh_refs,
                               "carried_groups": sorted(CARRIED_GROUPS),
                               "set_by_rule": {k: sorted(v) for k, v in SET_BY_RULE.items()}, **env},
        "comparison": comparison,
        "group_risk_flags": flags,
        "transfer_register": filled_register(register_facts(p5_groups, echt_all, p5, env)),
        "admission_requirements_for_design_specific_hall_maps": ADMISSION_REQUIREMENTS,
        "related_contracts_by_path": RELATED_PATHS,
    }
    return rnd(doc)


# --------------------------------------------------------------------------------------------------------------------
# Markdown report
# --------------------------------------------------------------------------------------------------------------------
def fmt(x, unit=""):
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, list):
        if len(x) == 2:
            if x[0] == x[1]:
                return fmt(x[0], unit)
            return f"{fmt(x[0])}–{fmt(x[1])}{(' ' + unit) if unit else ''}"
        return ", ".join(fmt(v) for v in x) + ((" " + unit) if unit else "")
    if isinstance(x, (int, float)):
        a = abs(x)
        s = f"{x:.3g}" if (a == 0 or 1e-3 <= a < 1e5) else f"{x:.2e}"
        return s + ((" " + unit) if unit else "")
    return str(x)


def fmt_req(r, unit=""):
    lo, hi = r["Te_N2_min_eV"], r["Te_N2_max_eV"]
    u = f" {unit}" if unit else ""
    if lo is None:
        return f"> 30{u} (outside the chemistry domain)"
    if hi is None:
        return f"{fmt(lo)} to > 30{u}"
    return fmt([lo, hi], unit)


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def env_cell(gid, v):
    if v is None and gid in B_GROUPS:
        return "TBD (requires Vyovrinda B)"
    return fmt(v)


def cell(row):
    if row["verdict"] in ("SET_BY_CONSTRUCTION", "NOT_COMPARABLE"):
        return row["verdict"]
    return f"{row['verdict']} ({fmt(row['best'])}/{fmt(row['worst'])})"


def render_md(doc: dict) -> str:
    g5n2, g5xe = doc["p5_groups"]["N2"], doc["p5_groups"]["Xe"]
    ech = doc["echt_groups"]["all_points"]
    env = doc["vyovrinda_envelope"]
    cmpd = doc["comparison"]
    topo = doc["b_field_topology"]
    dual = doc["dual_gas"]
    prox = doc["proxy_diagnostic"]
    te_ref = "10"
    scen_ids = list(env["L_rules"])
    L = []
    L.append("# Scaling / similarity audit: P5 evidence → Vyovrinda 12–25 mN Hall class (v1)\n")
    L.append(f"Generated by `{doc['generated_by']}` (deterministic; `--check` verifies this file and "
             "`scaling_similarity.json`). Do not edit by hand.\n")
    L.append("**What this is.** It computes the dimensionless and similarity groups for P5 at its N₂ and Xe points and "
             "for a Vyovrinda 12–25 mN, < 1.5 kW analysis envelope on both RFP propellants (N₂ as the air proxy, and "
             "Xe). It shows which groups match or diverge and by how much, the dual-gas gap on one channel, which "
             "P5-derived conclusions are mechanism-level (likely transferable) and which are not, and what an admitted "
             "transport closure would need before it is applied to Vyovrinda geometry.\n")
    L.append("**What this is not.** It is not a design and not a performance prediction. It runs no Hall solver, "
             "claims no closure transfer, and ranks or eliminates no architecture. The Vyovrinda numbers are an "
             "**analysis envelope** built from sourced, xenon-derived scaling relations. The credible transport set is "
             "empty (gate 3 FAIL), so nothing here depends on a Hall transport closure. No screening candidate is "
             "used as a performance source; only their profile-coordinate convention is read, to show the geometry "
             "dependence. P5 calibration nuisance (depth 32/38 mm, coil shape) only widens the P5 reference ranges and "
             "is never a Vyovrinda option or axis.\n")
    L.append(f"Status: `{doc['status']}`\n")
    L.append(f"Code baseline: `{doc['code_baseline']}`. Sources accessed {doc['sources_accessed']}. Architectures: "
             + ", ".join(f"`{a}`" for a in doc["architectures"]) + f". {doc['architecture_note']}\n")

    L.append("## 1. Milestones\n")
    L.append(md_table(["milestone", "support", "contribution", "needed to reach the next"],
                      [[k, v["support"], v["contribution"], v["to_next"]] for k, v in doc["milestones"].items()]))
    L.append("")

    L.append("## 2. Headline findings\n")
    f_gas = doc["gas_transfer_factor"]
    lam = {te: f_gas[te]["lambda_ratio_N2_over_Xe"] for te in f_gas}
    sh = dual["P5_same_hardware_as_measured"]
    geo = env["N2"]["geometry_by_area_rule"]
    hmin = min(v["h_mm"][0] for v in geo.values())
    hmax = max(v["h_mm"][1] for v in geo.values())
    p5h = 1e3 * (doc["inputs"]["p5"]["N2"]["points"]["N1"]["r_out_m"] - doc["inputs"]["p5"]["N2"]["points"]["N1"]["r_in_m"])
    bmm = [env["N2"]["B_required_by_scenario"][s]["mismatch_factor"] for s in scen_ids]
    counts = {}
    for gas in ("N2", "Xe"):
        c = {}
        for rows in cmpd[gas].values():
            for r in rows.values():
                c[r["verdict"]] = c.get(r["verdict"], 0) + 1
        counts[gas] = c
    tmax = f"{env['N2']['thrust_mN'][1]:g}"
    L.append(f"1. **Gas-level ionization length (mechanism, transferable as a ratio).** At equal n_e, T_e and T_n the "
             f"N₂ ionization mean free path is {fmt(lam['5'])}× the xenon one at T_e = 5 eV, {fmt(lam['10'])}× at "
             f"10 eV and {fmt(lam['30'])}× at 30 eV. N₂ ionization (all channels, including dissociative ionization) is "
             "slower and the neutral is faster. For N₂ the Melikov–Morozov criterion needs a correspondingly larger "
             "n_e·L. The ECHT extended channel (L/h = 8.6) is consistent with this (TR-01, TR-02).")
    L.append(f"2. **Same hardware, two gases (P5's own measured pair).** At equal T_e the P5-N₂ L/λ_i proxy is "
             f"{fmt(sh['per_Te']['10']['L_over_lambda_i_ratio_N2_over_Xe'])}× the P5-Xe value (T_e = 10 eV). To reach "
             f"the Xe value at T_e(Xe) = 5 eV, N₂ needs T_e ≈ "
             f"{fmt_req(sh['Te_N2_required_to_match_Xe_L_over_lambda_i']['5'], 'eV')}; to reach it at T_e(Xe) = 10 eV, "
             f"{fmt_req(sh['Te_N2_required_to_match_Xe_L_over_lambda_i']['10'], 'eV')}. "
             "So a channel that is Melikov–Morozov-similar on Xe is not on N₂ at the same T_e: N₂ needs a hotter "
             "discharge or a longer channel (TR-15). This is consistent "
             "with, but not evidence for, the P5-N₂ v1 out-of-domain pattern recorded in CLAUDE.md (solver T_e > 30 eV); "
             "no simulated T_e is used here.")
    L.append(f"3. **Thrust per power does not transfer.** P5-N₂ T/P_d is {fmt(g5n2['all_points']['T_over_P'], 'mN/kW')} "
             f"and the class-matched ECHT stable runs give {fmt(ech['T_over_P'], 'mN/kW')}. At {tmax} mN the N₂ "
             f"envelope needs P_d = {fmt(env['N2']['operating_summary']['P5-N2'][tmax]['P_d_W'], 'W')} with P5-N₂-like "
             f"conversion and {fmt(env['N2']['operating_summary']['ECHT'][tmax]['P_d_W'], 'W')} with ECHT-like "
             f"conversion; the Xe envelope with P5-Xe conversion needs "
             f"{fmt(env['Xe']['operating_summary']['P5-Xe'][tmax]['P_d_W'], 'W')}. The RFP total bound is "
             f"{fmt(env['N2']['power_max_W'], 'W')}. These spreads are transfer uncertainty (TR-06, TR-17), not "
             "predictions.")
    h_other = max(v["h_mm"][1] for k, v in geo.items() if k != "A_ncXe")
    geo_xe = env["Xe"]["geometry_by_area_rule"]
    L.append(f"4. **Geometry is design-dependent and mostly smaller than P5.** The sourced sizing rules put the N₂-mode "
             f"channel width at {fmt([hmin, hmax], 'mm')} and the Xe-mode width at "
             f"{fmt([min(v['h_mm'][0] for v in geo_xe.values()), max(v['h_mm'][1] for v in geo_xe.values())], 'mm')}, "
             f"against P5's {fmt(p5h, 'mm')}. Only the xenon critical-density rule applied to N₂ (a hypothesis, TR-14) "
             f"reaches P5's width; every other rule gives h ≤ {fmt(h_other, 'mm')}. Surface-to-volume (1/h) and the "
             "wall heat-flux proxy rise accordingly (TR-10).")
    L.append(f"5. **Magnetic similarity cannot be kept on two criteria at once.** Keeping r_Le/L (B ∝ 1/L) and keeping "
             f"the classical Hall parameter (B ∝ n_n) need B values that differ by factors of up to "
             f"{fmt(max(b[1] for b in bmm))} across the N₂ envelope. The B *topology* is not captured by any scaling "
             "law (DM2011 p. 242). Any P5-identified anomalous-transport closure is therefore **not transferable** as "
             "is (TR-08).")
    L.append("6. **Verdict counts** (scenario × group; bands PROPOSED): "
             + "; ".join(f"{gas}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts[gas].items())) for gas in counts)
             + ". SET_BY_CONSTRUCTION marks groups the envelope inherits from its anchor (no evidence of similarity). "
             "A divergence is a transfer-risk flag, not a verdict on any architecture.")
    L.append("7. **Absolute proxies are not gates.** The exit-plane L/λ_i proxy for P5-N₂ never reaches GK's "
             f"95 % criterion (L/λ_i ≥ 3) at T_e ≤ 30 eV (max {fmt(prox['P5-N2']['per_Te']['30']['L_over_lambda_i_proxy'][1])}), "
             "although P5-N₂ sustained a discharge. The groups are therefore used only as ratios to the evidence "
             "(AR-5).\n")

    L.append("## 3. Inputs and provenance\n")
    L.append("Repository files (read-only; sha256 at build time):\n")
    L.append(md_table(["file", "sha256"], [[f"`{k}`", f"`{v[:16]}…`"] for k, v in doc["inputs"]["repository_files"].items()]))
    L.append("")
    L.append("Quantity types of the P5 inputs:\n")
    L.append(md_table(["field", "class / note"], [[k, v] for k, v in doc["inputs"]["p5_classes"].items()]))
    L.append("")
    pts = doc["inputs"]["p5"]
    rows = []
    for gname in ("Xe", "N2"):
        for p, r in pts[gname]["points"].items():
            rows.append([gname, p, fmt(r["Vd"]), fmt(1e6 * r["mdot_kgps"]), fmt(r["Pd_W"]), fmt(r["Id_A"]),
                         fmt(r["T_corr_mN"]), fmt(1e4 * r["B_ref_T"]), "/".join(fmt(1e3 * x) for x in r["L_m"])])
    L.append(md_table(["gas", "point", "V_d [V]", "ṁ_anode [mg/s]", "P_d [W]", "I_d [A]", "T_corr [mN]",
                       "B_ref [G]", "L [mm] (nuisance)"], rows))
    L.append("")
    e = doc["inputs"]["echt"]
    L.append(f"ECHT context anchor (`{e['file']}`): L = {fmt(1e3 * e['L_m'])} mm, h = {fmt(1e3 * e['h_m'])} mm, "
             f"r_in/r_out = {fmt(1e3 * e['r_in_m'])}/{fmt(1e3 * e['r_out_m'])} mm (reading A, inferred, verify), "
             f"B plateau {fmt(1e4 * e['B_T'])} G (2 A only). Runs flagged unstable in the audit "
             f"({', '.join(e['unstable_runs_excluded'])}) are excluded; the stable runs carry one-side and averaged "
             f"thrust readings. {e['role']}.\n")
    L.append("Literature relations and coefficients (all read in the fetched copies listed in section 12):\n")
    L.append(md_table(["id", "value", "unit", "source", "class", "applicability"],
                      [[k, json.dumps(v["value"]) if isinstance(v["value"], dict) else fmt(v["value"]), v["unit"],
                        f"{v['source']} {v['locator']}", v["class"], v["applicability"]]
                       for k, v in doc["inputs"]["literature"].items()]))
    L.append("")
    L.append("Analysis inputs (assumed or requirement, labelled):\n")
    L.append(md_table(["id", "value", "unit", "class", "source / rationale"],
                      [[k, json.dumps(v["value"]) if isinstance(v["value"], dict) else fmt(v["value"]), v["unit"],
                        v["class"], v["source"]] for k, v in doc["inputs"]["analysis"].items()]))
    L.append("")
    L.append("Rate data: " + "; ".join(f"**{k}**: " + "; ".join(v["rate_sources"]) for k, v in doc["inputs"]["gases"].items())
             + ". Tables are evaluated at mean energy 3/2 T_e and refused beyond their `rate_validity.toml` limit. "
             "Xenon fit check against GK2008 Table E-1 (fit/table): "
             + ", ".join(f"{te} eV {fmt(v['fit_over_table'])}" for te, v in doc["xe_fit_check"].items()) + ".\n")

    L.append("## 4. Similarity groups\n")
    L.append(md_table(["id", "name", "definition", "relation source", "quantity type"],
                      [[f"`{g['id']}`", g["name"], g["definition"], g["relation_source"], g["quantity_type"]]
                       for g in doc["group_definitions"]]))
    L.append("")
    L.append("The plasma-parameter groups are **model-derived** and use no measured channel T_e or n_e. n_e is the "
             "exit-plane continuity estimate I_d/(e v_i A): I_d in place of I_i biases it high, the full-voltage v_i "
             "biases it low, and it understates the ionization-zone density (ions are slower there), so absolute L/λ_i "
             "values are order-of-magnitude only (section 5, proxy diagnostic). T_e is an assumed analysis grid. "
             "Comparisons of "
             "the same gas at the same T_e cancel the cross-section dependence. L is the physical channel length in "
             "every configuration (GK's L is the magnetized plasma thickness, about half the channel depth in its "
             "schematic).\n")

    L.append("## 5. Group values: P5 (Xe, N₂), ECHT and the Vyovrinda envelope\n")
    L.append("Ranges span the P5 depth bracket (32/38 mm), T_n ∈ {300, 800} K and, for the envelope, every anchor, "
             "thrust bound, area rule and d/h reference.\n")
    for gas, ref_name in (("N2", "P5-N₂"), ("Xe", "P5-Xe")):
        scen = env[gas]["groups_by_scenario"]
        rows = []
        for gid in GROUP_IDS:
            if gid in TE_GROUPS:
                continue
            base = [fmt(doc["p5_groups"][gas]["all_points"][gid])] + ([fmt(ech[gid])] if gas == "N2" else [])
            rows.append([f"`{gid}`"] + base + [env_cell(gid, scen[s][gid]) for s in scen_ids])
        for gid in TE_GROUPS:
            base = [fmt(doc["p5_groups"][gas]["all_points"]["per_Te"][te_ref][gid])] + \
                   ([fmt(ech["per_Te"][te_ref][gid])] if gas == "N2" else [])
            rows.append([f"`{gid}` @T_e={te_ref} eV"] + base
                        + [env_cell(gid, scen[s]["per_Te"][te_ref][gid]) for s in scen_ids])
        head = ["group", ref_name] + (["ECHT-N₂"] if gas == "N2" else []) + [f"V-{gas} {s}" for s in scen_ids]
        L.append(f"**{gas} mode.**\n")
        L.append(md_table(head, rows))
        L.append("")
    L.append("Units: n_n, n_e_exit in m⁻³; j_d in A/m²; P_over_hd, q_wall in W/m²; eps_particle in eV; tau_res in s; "
             "T_over_P in mN/kW; inv_h in 1/m. B-dependent groups are not evaluated for the envelope because the "
             "Vyovrinda B is TBD; the B each similarity rule would require is in section 7.\n")
    L.append("Per-point P5 values (T_e-independent groups):\n")
    rows = []
    for gname, gg in (("Xe", g5xe), ("N2", g5n2)):
        for p, v in gg["per_point"].items():
            rows.append([p, fmt(v["n_n"]), fmt(v["j_d"]), fmt(v["P_over_hd"]), fmt(v["eps_particle"]),
                         fmt(v["I_d_over_I_m"]), fmt(v["alpha_app"]), fmt(v["T_over_P"])])
    L.append(md_table(["point", "n_n [m⁻³]", "j_d [A/m²]", "P/(hd) [W/m²]", "ε [eV]", "I_d/I_m", "α_app",
                       "T/P [mN/kW]"], rows))
    L.append("")
    L.append("Gas-transfer factor λ_i(N₂)/λ_i(Xe) at equal n_e, T_e, T_n (N₂ low/high = lower/upper "
             "dissociative-ionization variant):\n")
    L.append(md_table(["T_e [eV]", "k_iz Xe [m³/s]", "k_iz N₂ total [m³/s]", "k_iz N atom [m³/s]", "λ_N₂/λ_Xe"],
                      [[te, fmt(v["k_iz_Xe_m3s"]), fmt(v["k_iz_N2_m3s"]), fmt(v["k_iz_N_atom_m3s"]),
                        fmt(v["lambda_ratio_N2_over_Xe"])] for te, v in f_gas.items()]))
    L.append("")
    L.append("Proxy diagnostic (why absolute thresholds are not used): exit-plane L/λ_i proxy and single-pass "
             "ionization proxy against the measured α_app.\n")
    rows = []
    for name, v in prox.items():
        for te, r in v["per_Te"].items():
            rows.append([name, te, fmt(r["L_over_lambda_i_proxy"]), fmt(r["iz_fraction_proxy"]),
                         fmt(v["alpha_app_measured"]), fmt(r["meets_GK_L_over_lambda_i_3"]),
                         fmt(r["proxy_max_below_alpha_app_min"])])
    L.append(md_table(["config", "T_e [eV]", "L/λ_i proxy", "1−exp(−L/λ_i)", "α_app (measured)",
                       "proxy ≥ 3 (GK Eq. 7.2-16)", "proxy max < α_app min"], rows))
    L.append("")
    L.append("α_app is not a utilization (it lumps species mix, divergence and voltage loss), so the last column is "
             "indicative only. The point is that an operating N₂ discharge sits far below GK's absolute criterion "
             "under this proxy.\n")
    L.append(f"The ion Larmor margin stays large: the smallest r_Li/L over P5 (both gases) and ECHT is "
             f"{fmt(min(g5n2['all_points']['rLi_over_L'][0], g5xe['all_points']['rLi_over_L'][0], ech['rLi_over_L'][0]))}; "
             f"for N⁺ at P5-N3 (L = 38 mm) it is {fmt(doc['ion_larmor_N_plus_at_P5_N3_L38'])}.\n")

    L.append("## 6. Match / divergence against the P5 evidence\n")
    L.append("Cells read `VERDICT (best/worst)`. best = smallest factor separating the envelope from the reference range "
             "(1 = overlap); worst = largest factor between any envelope configuration and the reference range. Bands "
             "are **PROPOSED**: worst ≤ 2 MATCHES_WITHIN_2; best ≤ 2 < worst DESIGN_DEPENDENT (matching is possible "
             "but depends on design choices inside the envelope); 2 < best ≤ 5 DIVERGES; best > 5 STRONGLY_DIVERGES. "
             "SET_BY_CONSTRUCTION = inherited from the anchor or imposed by the L rule.\n")
    for gas, ref_name in (("N2", "P5-N₂"), ("Xe", "P5-Xe")):
        rows = []
        labels = list(cmpd[gas][scen_ids[0]].keys())
        for lab in labels:
            rows.append([f"`{lab}`", fmt(cmpd[gas][scen_ids[0]][lab]["reference"])]
                        + [cell(cmpd[gas][s][lab]) for s in scen_ids]
                        + [doc["group_risk_flags"][gas][lab]["risk_flag"]])
        L.append(f"**{gas} envelope vs {ref_name}.** L ranges: "
                 + "; ".join(f"{s} {fmt(env[gas]['L_by_scenario_mm'][s], 'mm')}" for s in scen_ids) + ".\n")
        L.append(md_table(["group", ref_name] + scen_ids + ["risk flag"], rows))
        L.append("")
    rows = []
    for lab in cmpd["N2"][scen_ids[0]]:
        rows.append([f"`{lab}`", fmt(cmpd["N2"][scen_ids[0]][lab]["echt"])]
                    + [cmpd["N2"][s][lab]["verdict_vs_echt"] for s in scen_ids])
    L.append("**N2 envelope vs ECHT-N₂ (class-matched context, not validation).**\n")
    L.append(md_table(["group", "ECHT-N₂"] + scen_ids, rows))
    L.append("")
    L.append("Risk flag (computed, PROPOSED convention): LOW = MATCHES_WITHIN_2 in every scenario; MEDIUM = matching "
             "is design-dependent in at least one scenario; HIGH = diverges in at least one scenario; NOT_ASSESSED = "
             "set by construction or not comparable.\n")

    L.append("## 7. Envelope construction (analysis, not a design)\n")
    L.append("Each anchor (a P5 point or an ECHT stable run) keeps its V_d, α_app and I_d/I_m. The RFP thrust bounds "
             "then give ṁ = T/(α_app v_i), I_d and P_d. **This carries the anchor's T/P unchanged, which is the "
             "unverified transfer TR-06.** ṁ is really set upstream by the intake/compressor chain (air) or the Xe "
             "feed; this range is not an intake requirement, and Hall-closure uncertainty never flows upstream.\n")
    rows = []
    for gas in ("N2", "Xe"):
        for fam, v in env[gas]["operating_summary"].items():
            for T, w in v.items():
                rows.append([gas, fam, T, fmt(w["mdot_mgps"]), fmt(w["I_d_A"]), fmt(w["P_d_W"]),
                             fmt(w["all_below_RFP_total_bound"])])
    L.append(md_table(["gas", "anchor family", "T [mN]", "ṁ [mg/s]", "I_d [A]", "P_d [W]",
                       "P_d < RFP total bound (necessary only)"], rows))
    L.append("")
    rows = []
    for gas in ("N2", "Xe"):
        for k, v in env[gas]["geometry_by_area_rule"].items():
            rows.append([gas, k, env["area_rules"][k], fmt(v["A_m2"]), fmt(v["h_mm"]), fmt(v["d_mm"])])
    L.append(md_table(["gas", "area rule", "definition", "A [m²]", "h [mm]", "d [mm]"], rows))
    L.append("")
    rows = []
    for gas in ("N2", "Xe"):
        for s in scen_ids:
            b = env[gas]["B_required_by_scenario"][s]
            rows.append([gas, s, env["L_rules"][s], fmt(env[gas]["L_by_scenario_mm"][s]), fmt(b["B_keep_rLe_over_L_G"]),
                         fmt(b["B_keep_classical_hall_G"]), fmt(b["mismatch_factor"])])
    L.append(md_table(["gas", "L rule", "definition", "L [mm]", "B keep r_Le/L [G]", "B keep classical Ω [G]",
                       "mismatch factor"], rows))
    L.append("")
    L.append(f"d/h references: {json.dumps({k: round(v, 4) for k, v in env['d_over_h_refs'].items()})} (DM2011 p. 241: "
             f"h ∝ d, coefficient unpublished). The xenon database typically runs near "
             f"{fmt(doc['inputs']['literature']['B_typical_xenon_database']['value'])} G (DM2011 p. 242). Row counts: "
             + "; ".join(f"{g} {json.dumps(env[g]['row_counts'])}" for g in ("N2", "Xe")) + ".\n")

    L.append("## 8. Dual-gas operation of one channel\n")
    L.append("The RFP thruster takes air and Xe through the same ionization/discharge block (CLAUDE.md scope). Ratios "
             "N₂/Xe below are geometry-independent: on P5 as measured (both gases at 5 mg/s anode flow on the same "
             "hardware), and at equal thrust with each gas at its anchor's α_app and I_d/I_m.\n")
    rows = []
    for name in ("P5_same_hardware_as_measured", "common_channel_equal_thrust_P5N2_vs_P5Xe",
                 "common_channel_equal_thrust_ECHT_vs_P5Xe"):
        v = dual[name]
        rr = v["ratios_N2_over_Xe"]
        rows.append([name, fmt(rr["mdot"]), fmt(rr["I_d"]), fmt(rr["P_d"]), fmt(rr["n_n"]), fmt(rr["n_e_exit"]),
                     fmt(rr["prefactor"]), v["pairs"]])
    L.append(md_table(["case", "ṁ", "I_d", "P_d", "n_n", "n_e_exit", "(n_e/v_n) prefactor", "anchor pairs"], rows))
    L.append("")
    rows = []
    for name in ("P5_same_hardware_as_measured", "common_channel_equal_thrust_P5N2_vs_P5Xe",
                 "common_channel_equal_thrust_ECHT_vs_P5Xe"):
        v = dual[name]
        for te in v["per_Te"]:
            rows.append([name, te, fmt(v["per_Te"][te]["L_over_lambda_i_ratio_N2_over_Xe"]),
                         fmt(v["per_Te"][te]["B_ratio_for_equal_classical_hall_param"]),
                         fmt_req(v["Te_N2_required_to_match_Xe_L_over_lambda_i"][te])])
    L.append(md_table(["case", "T_e [eV]", "L/λ_i N₂/Xe at equal T_e", "B_N₂/B_Xe for equal classical Ω",
                       "T_e(N₂) [eV] to match Xe L/λ_i at this T_e(Xe)"], rows))
    L.append("")
    L.append("Definitions: " + "; ".join(f"{k}: {v}" for k, v in dual["definitions"].items()) + ".\n")

    L.append("## 9. B topology and why a closure does not carry over\n")
    rows = []
    for key, r in topo["P5"]["registrations"].items():
        reg, coil = key.split("|")
        rows.append([coil, reg, fmt(r["L_mm"]), fmt(r["z_peak_over_L"]), fmt(r["B_exit_over_B_peak"]),
                     fmt(r["B_anode_over_B_peak"]), fmt(r["fraction_of_channel_B_above_half_peak"]),
                     fmt(r["screening_profile_centre_minus_B_peak_over_L"])])
    L.append(md_table(["P5 coil shape", "registration", "L [mm]", "z_peak/L", "B_exit/B_peak", "B_anode/B_peak (held)",
                       "fraction of channel with B ≥ ½B_peak", "(profile centre − B peak)/L, screening set"], rows))
    L.append("")
    t = topo["ECHT"]
    L.append(f"ECHT measured profile (2 A) is a plateau: peak {fmt(t['B_peak_G'])} G, B_exit/B_peak = "
             f"{fmt(t['B_exit_over_B_peak'])}, lower half-maximum at {fmt(t['half_max_z_axis_mm'][0], 'mm')} on the "
             f"source axis ({t['note']}). P5 is exit-peaked. These are qualitatively different topologies.\n")
    L.append(f"The screening closures store their profile centre at center_L ∈ {topo['P5']['screening_center_L_values']} "
             f"and width_L ∈ {topo['screening_width_L_values']}, both in channel-length units. The last column shows "
             "that the same L-unit centre lands at a different place relative to the B peak even across the P5 "
             "registrations alone. On a Vyovrinda channel with its own L and B(z) the mapping is undetermined until a "
             f"transfer convention is pre-registered (AR-4). Admitted members: {topo['admitted_members']}. "
             f"{topo['screening_structure_note']}.\n")

    L.append("## 10. Transfer register\n")
    L.append(md_table(["id", "quantity", "transferability", "risk", "why", "evidence needed"],
                      [[t["id"], t["quantity"], t["transferability"], t["risk"], t["why"], t["evidence_needed"]]
                       for t in doc["transfer_register"]]))
    L.append("")
    L.append("Consistency check (enforced by the script): a LOW-risk entry never depends on a group that DIVERGES or "
             "STRONGLY_DIVERGES from the P5 evidence in any scenario of either gas.\n")

    L.append("## 11. What admission needs before Vyovrinda design-specific Hall maps\n")
    L.append(md_table(["id", "requirement", "status", "source"],
                      [[a["id"], a["requirement"], a["status"], a["source"]]
                       for a in doc["admission_requirements_for_design_specific_hall_maps"]]))
    L.append("")
    L.append("Nothing in this audit claims that a closure transfers. At best, once the NOT MET items hold, a member "
             "evaluated on Vyovrinda geometry carries a stated similarity-domain status per map point (AR-5) and a "
             "declared transfer statement (AR-4).\n")
    L.append("Limitations and open questions:\n")
    L.append("- The scaling relations and coefficients (C_P*, j_d, n_n,c, f_loss, α range) come from xenon databases. "
             "Applying them to N₂ is extrapolation (evidence level 6). O/O₂/air are not covered (TBD: requires an O/O₂ "
             "reaction set and evidence).")
    L.append("- DM2008 Eq. (2.3) and DM2011 Eq. (3) write the ionization frequency with n_n; GK2008 Eq. (7.2-14) uses "
             "n_e, the density a neutral crossing a plasma actually meets. This audit uses the GK2008 form. The "
             "discrepancy is recorded, not resolved (DM2008's β = λ_i/L = 0.007 uses the n_n form).")
    L.append("- n_e and T_e are not measured for any configuration used here. Absolute L/λ_i values are "
             "order-of-magnitude, model-derived estimates; ratios between configurations are more robust.")
    L.append("- P5 I_d is the facility value P_d/V_d; thrust is the vacuum-corrected value. The N₂ I_d vacuum correction "
             "(section 3) is a few per cent, below the resolution of any verdict here.")
    L.append("- The ECHT radii (reading A), its B at the run coil currents and its thrust reduction are uncertain "
             "(audit). ECHT is a context anchor, not validation.")
    L.append("- The P5 channel depth (32 vs 38 mm) and coil shape are layer-1 nuisance. They appear only as brackets "
             "on P5 values and never as Vyovrinda variables.")
    L.append("- Related contracts are referenced by path only (never imported): "
             + ", ".join(f"`{v}`" for v in doc["related_contracts_by_path"].values()) + ".\n")

    L.append("## 12. Sources accessed\n")
    L.append(md_table(["id", "citation", "URL", "sha256", "pages"],
                      [[k, v["citation"], v["url"], f"`{v['sha256']}`" if v["sha256"] else "n/a (web page)", v["page_note"]]
                       for k, v in doc["sources"].items()]))
    L.append("")
    L.append("Contact with authors or labs: none. Open-access sources only; no paywall bypass; no LXCat.\n")
    return "\n".join(L)


def dumps(doc) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify committed outputs instead of writing")
    args = ap.parse_args(argv)
    doc = build()
    js, md = dumps(doc), render_md(doc)
    if args.check:
        ok = JSON_PATH.exists() and MD_PATH.exists() and JSON_PATH.read_text() == js and MD_PATH.read_text() == md
        print("OK" if ok else "DIFF: committed outputs differ from a fresh build")
        return EXIT_CODES["ok" if ok else "diff"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(js)
    MD_PATH.write_text(md)
    print(f"wrote {JSON_PATH.relative_to(REPO)} and {MD_PATH.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

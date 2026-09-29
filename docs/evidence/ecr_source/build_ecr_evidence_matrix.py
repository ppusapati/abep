"""Build the ECR source evidence matrix (docs/evidence/ecr_source/ecr_evidence_matrix.json).

Evidence audit only: no model implementation, no architecture conclusion, no ranking of ECR against any other
ionization technology. Literature entries (ECR-E###) are transcribed by hand from the sources listed in SOURCES;
derived entries (ECR-D###) are computed here from CODATA 2022 constants and from the transcribed entries, so every
number that did not come straight out of a source is produced by this deterministic script.

    python docs/evidence/ecr_source/build_ecr_evidence_matrix.py          # (re)write the JSON
    python docs/evidence/ecr_source/build_ecr_evidence_matrix.py --check  # verify the committed JSON is current

Evidence classes follow docs/EVIDENCE.md (quantity type): measured / digitized / inferred / reconstructed /
model-derived / assumed. A ratio of two reported numbers (e.g. W/A from P and I) is "inferred", as for the P5 raw
I_d = P_d/V_d in docs/EVIDENCE.md; a value that needs a physical formula or constant is "model-derived".
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "ecr_evidence_matrix.json"

# --------------------------------------------------------------------------------------------- constants
# CODATA 2022 recommended values, read from https://physics.nist.gov/cuu/Constants/ on 2026-09-26.
E_C = 1.602176634e-19          # elementary charge, C (exact)
M_E = 9.1093837139e-31         # electron mass, kg (rel. std. unc. 3.1e-10)
EPS0 = 8.8541878188e-12        # vacuum electric permittivity, F/m (rel. std. unc. 1.6e-10)
K_B = 1.380649e-23             # Boltzmann constant, J/K (exact)
# Standard reference state used to convert sccm to a particle rate. Mass-flow controllers are calibrated to
# different reference temperatures (0 C or 20 C); 0 C / 101325 Pa is an ASSUMPTION stated on every entry using it.
T_STD_K = 273.15
P_STD_PA = 101325.0

CONSTANTS = {
    "e_C": E_C,
    "m_e_kg": M_E,
    "eps0_F_per_m": EPS0,
    "k_B_J_per_K": K_B,
    "sccm_reference_T_K": T_STD_K,
    "sccm_reference_p_Pa": P_STD_PA,
    "source": {
        "citation": "CODATA 2022 recommended values of the fundamental physical constants, NIST Physical Measurement "
                    "Laboratory (e, m_e, epsilon_0, k_B). sccm reference state 0 C / 101325 Pa is an assumption of "
                    "this audit, not a CODATA value.",
        "doi_or_url": "https://physics.nist.gov/cuu/Constants/",
        "access": "open",
    },
}


# ------------------------------------------------------------------------------ formulas (derived entries)
def b_res_T(f_Hz: float) -> float:
    """ECR resonance field for the fundamental harmonic: 2*pi*f = e*B/m_e  ->  B = 2*pi*f*m_e/e."""
    return 2.0 * math.pi * f_Hz * M_E / E_C


def n_cutoff_m3(f_Hz: float) -> float:
    """Cold-plasma O-mode cutoff density: omega = omega_pe  ->  n_c = eps0*m_e*(2*pi*f)^2/e^2."""
    return EPS0 * M_E * (2.0 * math.pi * f_Hz) ** 2 / E_C ** 2


def ratio(num, den):
    """num/den; num may be a list (element-wise)."""
    if isinstance(num, list):
        return [x / den for x in num]
    return num / den


def db_to_power_fraction(loss_dB: float) -> float:
    """Transmitted power fraction for an attenuation in dB: 10**(-dB/10)."""
    return 10.0 ** (-loss_dB / 10.0)


def elementwise_ratio(num: list, den: list) -> list:
    return [a / b for a, b in zip(num, den)]


def sum_ratio(num: list, den: float) -> float:
    return sum(num) / den


def power_per_current(P_W: float, I_A):
    """Ion production cost in W/A (numerically equal to eV per singly charged ion)."""
    if isinstance(I_A, list):
        return [P_W / i for i in I_A]
    return P_W / I_A


def w_per_a_to_ev_per_ion() -> float:
    """1 W/A = 1 J/C; per elementary charge that is e J = 1 eV. Returns the eV per ion for 1 W/A."""
    joule_per_coulomb = 1.0
    return joule_per_coulomb * E_C / E_C


def neutral_density_m3(p_Pa, T_K):
    """Ideal gas n = p/(k_B T); p may be a list (then T is scalar), or T may be a list (then p is scalar)."""
    if isinstance(p_Pa, list):
        return [p / (K_B * T_K) for p in p_Pa]
    if isinstance(T_K, list):
        return [p_Pa / (K_B * t) for t in T_K]
    return p_Pa / (K_B * T_K)


def particles_per_s_per_sccm() -> float:
    """1 sccm = 1 cm^3/min of gas at the reference state -> p0*1e-6/(k_B*T0)/60 particles per second."""
    return P_STD_PA * 1e-6 / (K_B * T_STD_K) / 60.0


def equivalent_current_A(sccm: float) -> float:
    """Particle flow expressed as a singly charged current: e * sccm * particles_per_s_per_sccm()."""
    return E_C * sccm * particles_per_s_per_sccm()


def br_reversible_change_pct(alpha_pct_per_C, dT_C: float):
    """Linear reversible remanence change: alpha[%/C] * dT[C]; alpha may be a list."""
    if isinstance(alpha_pct_per_C, list):
        return [a * dT_C for a in alpha_pct_per_C]
    return alpha_pct_per_C * dT_C


def difference(a: float, b: float) -> float:
    return a - b


def mtorr_to_pa(p_mTorr):
    """1 Torr = 101325/760 Pa (exact by definition)."""
    if isinstance(p_mTorr, list):
        return [x * 1e-3 * 101325.0 / 760.0 for x in p_mTorr]
    return p_mTorr * 1e-3 * 101325.0 / 760.0


FUNCTIONS = {f.__name__: f for f in (b_res_T, n_cutoff_m3, ratio, db_to_power_fraction, elementwise_ratio, sum_ratio,
                                     power_per_current, w_per_a_to_ev_per_ion, neutral_density_m3,
                                     particles_per_s_per_sccm, equivalent_current_A, br_reversible_change_pct,
                                     difference, mtorr_to_pa)}


def sig4(x):
    """Round to 4 significant figures (deterministic storage precision of derived values)."""
    if isinstance(x, list):
        return [sig4(v) for v in x]
    if x == 0:
        return 0.0
    return float(f"{x:.4g}")


# ------------------------------------------------------------------------------------------------ sources
S = {
    "S01": ("K. D. Diamant, \"Microwave Cathode for Air Breathing Electric Propulsion\", IEPC-2009-015, 31st "
            "International Electric Propulsion Conference, Ann Arbor, MI, USA, 20-24 Sep 2009",
            "https://electricrocket.org/IEPC/IEPC-2009-015.pdf", "open", "primary"),
    "S02": ("H. Kuninaka, K. Nishiyama, Y. Shimizu, I. Funaki, H. Koizumi, S. Hosoda, D. Nakata, \"Hayabusa Asteroid "
            "Explorer Powered by Ion Engines on the way to Earth\", IEPC-2009-267, 31st IEPC, Ann Arbor, 2009",
            "https://electricrocket.org/IEPC/IEPC-2009-267.pdf", "open", "primary"),
    "S03": ("R. Tsukizaki, I. Nishiyama, Y. Yamamoto, S. Hosoda, K. Nishiyama, H. Kuninaka, \"Improvement of the "
            "Thrust Force of the mu10 Microwave Ion Thruster by Optimizing the Potential of the Conductive Wall\", "
            "IEPC-2015-332/ISTS-2015-b-332, Kobe, 2015",
            "https://electricrocket.org/IEPC/IEPC-2015-332_ISTS-2015-b-332.pdf", "open", "primary"),
    "S04": ("S. Hosoda, K. Nishiyama, Y. Toyoda, H. Kuninaka, \"Intermediate report of MU-20 microwave discharge ion "
            "thruster development\", IEPC-2009-155, 31st IEPC, Ann Arbor, 2009",
            "https://electricrocket.org/IEPC/IEPC-2009-155.pdf", "open", "primary"),
    "S05": ("M. Miyoshi, N. Yamamoto, H. Nakashima, \"Microwave Discharge Ion Thruster using Argon as a "
            "Propellant\", IEPC-2007-205, 30th IEPC, Florence, 2007",
            "https://electricrocket.org/IEPC/IEPC-2007-205.pdf", "open", "primary"),
    "S06": ("J. Jarrige, P.-Q. Elias, F. Cannat, D. Packan, \"Performance Comparison of an ECR Plasma Thruster using "
            "Argon and Xenon as Propellant Gas\", IEPC-2013-420, 33rd IEPC, Washington DC, 2013",
            "https://electricrocket.org/IEPC/ck35023e.pdf", "open", "primary"),
    "S07": ("D. Packan et al., \"H2020 MINOTOR: Magnetic Nozzle Electron Cyclotron Resonance Thruster\", "
            "IEPC-2019-875, 36th IEPC, Vienna, 2019",
            "https://electricrocket.org/2019/875.pdf", "open", "primary"),
    "S08": ("V. Desangles, F. Boni, R. Ferrand, E. Gourcerol, R. Pioch, P.-Q. Elias, D. Packan, \"ECRA Thruster latest "
            "development at ONERA: Focus on thrust vectoring activities\", EUCASS 2023 (10th EUCASS / 9th CEAS), "
            "DOI 10.13009/EUCASS2023-761",
            "https://www.eucass.eu/doi/EUCASS2023-761.pdf", "open", "primary"),
    "S09": ("T. Vialis, J. Jarrige, D. Packan, \"Geometry optimization and effect of gas propellant in an electron "
            "cyclotron resonance plasma thruster\", IEPC-2017-378, 35th IEPC, Atlanta, 2017",
            "https://electricrocket.org/IEPC/IEPC_2017_378.pdf", "open", "primary"),
    "S10": ("J. Porto, P.-Q. Elias, A. Ciardi, \"Anisotropic Electron Heating in an Electron Cyclotron Resonance "
            "Thruster with Magnetic Nozzle\", arXiv:2301.11411 (2023)",
            "https://arxiv.org/abs/2301.11411", "open", "preprint"),
    "S11": ("M. Tisaev, B. Karadag, A. Lucca Fabris, \"Influence of applied magnetic field in an air-breathing "
            "microwave plasma cathode\", J. Phys. D: Appl. Phys. 56 (2023) 465203 (CC BY 4.0)",
            "https://doi.org/10.1088/1361-6463/acefe2", "open", "primary"),
    "S12": ("R. Tan, J. Yang, H. Mou, X. Wu, \"Computational and experimental research on the performance of ECRIT "
            "ion source with nitrogen propellant\", J. Northwestern Polytechnical Univ. 41(2) (2023) 274-281 "
            "(CC BY 4.0). Abstract read from Crossref metadata; publisher page returned HTTP 403 to our fetch",
            "https://doi.org/10.1051/jnwpu/20234120274", "abstract_only", "abstract"),
    "S13": ("R. Tan, J. Yang, H. Mou, Y. Huo, X. Ma, \"Experimental study on nitrogen-fed 10 cm ECR gridded ion source "
            "for ABEP\", SSRN preprint (DOI 10.2139/ssrn.6438826); published version Aerospace Science and "
            "Technology 178 (2026) 113204, DOI 10.1016/j.ast.2026.113204 (full text not accessed). Abstract read "
            "from the Crossref metadata of the preprint (same title and authors)",
            "https://doi.org/10.2139/ssrn.6438826", "abstract_only", "abstract"),
    "S14": ("M. Stastny, K. Mrozek, K. Jurik, P. Drexler, J. Sedlar, L. Havlicek, M. Novotny, A. Obrusnik, \"Current "
            "progress in the development of an ECR plasma source for atmosphere-breathing electric propulsion "
            "system\", CEAS Space Journal 18 (2026) 497-505 (CC BY 4.0). Abstract read from Crossref metadata; the "
            "publisher page served a bot challenge, which was not bypassed",
            "https://doi.org/10.1007/s12567-026-00700-8", "abstract_only", "abstract"),
    "S15": ("P. Zheng, J. Wu, Y. Zhang, B. Wu, \"A Comprehensive Review of Atmosphere-Breathing Electric Propulsion "
            "Systems\", Int. J. Aerospace Engineering 2020, 8811847 (CC BY)",
            "https://doi.org/10.1155/2020/8811847", "open", "review"),
    "S16": ("K. K. de Groh, B. A. Banks, C. E. McCarthy, R. N. Rucker, L. M. Roberts, L. A. Berger, \"MISSE PEACE "
            "Polymers Atomic Oxygen Erosion Results\", NASA/TM-2006-214482 (2006)",
            "https://ntrs.nasa.gov/api/citations/20070002707/downloads/20070002707.pdf", "open", "primary"),
    "S17": ("Arnold Magnetic Technologies, \"Recoma(R) Sintered Samarium Cobalt Magnets\" combined datasheet "
            "(c) 2014, rev. 160205a/160301",
            "https://www.arnoldmagnetics.com/wp-content/uploads/2017/10/Recoma-Combined-160301.pdf", "open",
            "datasheet"),
    "S18": ("Eclipse Magnetics, \"NdFeB Magnets / Neodymium Iron Boron Magnets Datasheet\" (standard NdFeB range, "
            "rev1)",
            "https://www.eclipsemagnetics.com/site/assets/files/19485/"
            "ndfeb_neodymium_iron_boron-standard_ndfeb_range_datasheet_rev1.pdf", "open", "datasheet"),
    "S19": ("G. Kazakevich, R. P. Johnson, T. Khabiboulline, G. Romanov, V. Yakovlev, Ya. Derbenev, Yu. Eidelman, "
            "\"On forced RF generation of CW magnetrons for SRF accelerators\", arXiv:2404.16249 (2024)",
            "https://arxiv.org/abs/2404.16249", "open", "preprint"),
    "S20": ("C. Li, Z. Zhang, Y. Pei, C. Chen, G. Feng, Y. Xu, \"Internally Harmonic Matched Compact GaN Power "
            "Amplifier with 78.5% PAE for 2.45 GHz Wireless Power Transfer Systems\", Micromachines 15(11) (2024) "
            "1354 (CC BY 4.0)",
            "https://doi.org/10.3390/mi15111354", "open", "primary"),
    "S21": ("H. Wang et al., \"Magnetron R&D Progress for High Efficiency CW RF Sources of Industrial Accelerators\", "
            "NAPAC2022, paper WEZD3 (CC BY 4.0)",
            "https://doi.org/10.18429/JACoW-NAPAC2022-WEZD3", "open", "primary"),
    "S22": ("CODATA 2022 recommended values (NIST) and standard plasma formulas: f_ce = eB/(2 pi m_e) as written in "
            "Jarrige et al. IEPC-2013-420 Eq. (1) and Tisaev et al. 2023 Eq. (2); O-mode cutoff omega = omega_pe, "
            "n_c = eps0 m_e omega^2/e^2 (textbook relation, cited from memory - verify; numerically cross-checked "
            "against the cutoffs stated in ECR-E004..E006)",
            "https://physics.nist.gov/cuu/Constants/", "open", "formula_and_constants"),
    "S24": ("M. Tisaev, B. Karadag, S. Masillo, A. Lucca Fabris, \"Performance and plasma diagnostics of the "
            "Air-breathing Microwave Plasma CAThode (AMPCAT) coupled to a cylindrical Hall thruster\", J. Appl. "
            "Phys. 134 (2023) 193302 (CC BY 4.0). Abstract read from Crossref metadata",
            "https://doi.org/10.1063/5.0176682", "abstract_only", "abstract"),
}

SOURCES = {k: {"citation": v[0], "doi_or_url": v[1], "access": v[2], "source_kind": v[3]} for k, v in S.items()}

LEADS_NOT_ADMITTED = [
    {"citation": "L. Wang, X.-M. Zhu, C. Fan, L.-T. Yu, Y.-Q. Kang, D.-S. Yang, J.-W. Jia, D.-R. Yu, \"A rarefied "
                 "atmosphere-particle collisional-radiative model ... in an atmosphere-breathing electric thruster "
                 "system\", Aerospace Science and Technology 174 (2026) 111942",
     "doi_or_url": "https://doi.org/10.1016/j.ast.2026.111942",
     "reason": "Publisher page returned HTTP 403; no abstract in Crossref or Semantic Scholar metadata. A search-engine "
               "snippet quoted a thrust at a stated flow for an ECR-based atmosphere-breathing thruster; it could not "
               "be verified against the source, so no number is admitted."},
    {"citation": "K. Nishiyama, H. Kuninaka, \"Microwave power absorption coefficient of an ECR xenon ion thruster\", "
                 "Surface & Coatings Technology 202 (2008) 5262-5265",
     "doi_or_url": "https://doi.org/10.1016/j.surfcoat.2008.06.069",
     "reason": "Directly relevant to absorbed vs forward power; closed access, abstract elided in open metadata. Not "
               "accessed."},
    {"citation": "M. Tagawa, K. Yokota, K. Nishiyama, H. Kuninaka, Y. Yoshizawa, D. Yamamoto, T. Tsuboi, "
                 "\"Experimental Study of Air Breathing Ion Engine Using Laser Detonation Beam Source\", J. Propulsion "
                 "and Power 29(3) (2013) 501-506",
     "doi_or_url": "https://doi.org/10.2514/1.B34530",
     "reason": "Closed access; only the secondary summary in Zheng et al. 2020 (S15) is used (ECR-E097, E098)."},
    {"citation": "K. Nishiyama, \"Air Breathing Ion Engine Concept\", IAC-03-S.4.02, 54th International "
                 "Astronautical Congress, Bremen, 2003",
     "doi_or_url": "https://doi.org/10.2514/6.IAC-03-S.4.02",
     "reason": "Concept paper; not accessed. Cited only as the origin of the JAXA ABIE concept via S01 and S15."},
    {"citation": "K. Diamant, \"A 2-stage cylindrical Hall thruster for air breathing electric propulsion\", 46th "
                 "AIAA/ASME/SAE/ASEE Joint Propulsion Conference, Nashville, 2010 (as cited in S15, ref. [43])",
     "doi_or_url": "https://doi.org/10.1155/2020/8811847",
     "reason": "Not accessed; only the secondary summary in S15 is used (ECR-E143). URL points to the citing review."},
    {"citation": "S. Barquero, K. Tabata, R. Tsukizaki, M. Merino, J. Navarro-Cavalle, K. Nishiyama, \"Performance "
                 "characterization of the mu10 electron-cyclotron-resonance ion thruster using alternative "
                 "propellants: krypton vs. xenon\", Acta Astronautica 211 (2023) 750-754 (CC BY-NC-ND)",
     "doi_or_url": "https://doi.org/10.1016/j.actaastro.2023.06.036",
     "reason": "Publisher returned HTTP 403 to our fetch; krypton is outside this lane's gas scope."},
    {"citation": "J. R. Tompkins, T. Yamauchi, J. L. Rovey, \"Plume properties and predicted performance of "
                 "alternative propellants in an electron cyclotron resonance gridded ion source\", Acta Astronautica "
                 "248 (2026) 1080-1095",
     "doi_or_url": "https://doi.org/10.1016/j.actaastro.2026.06.061",
     "reason": "No abstract in open metadata; publisher blocked. Content unknown; not admitted."},
    {"citation": "M. Tisaev, B. Karadag, E. Ferrato, T. Andreussi, A. Lucca Fabris, \"Development and standalone "
                 "testing of the Air-breathing Microwave Plasma CAThode (AMPCAT)\", Acta Astronautica 214 (2024) "
                 "722-736 (CC BY)",
     "doi_or_url": "https://doi.org/10.1016/j.actaastro.2023.11.028",
     "reason": "Publisher returned HTTP 403; no abstract in open metadata. The simulator's existing AMPCAT prior "
               "(abep_sim/thruster.py docstring and MW_AIR_CATHODE) could therefore not be traced in this audit."},
    {"citation": "T. Andreussi et al., \"A review of air-breathing electric propulsion: from mission studies to "
                 "technology verification\", J. Electric Propulsion (2022)",
     "doi_or_url": "https://doi.org/10.1007/s44205-022-00024-9",
     "reason": "Publisher page served a bot challenge; not bypassed. Not accessed."},
    {"citation": "ONERA ECRA 30 W / 200 W prototype paper, HAL hal-03839025; T. Vialis et al., \"Direct Thrust "
                 "Measurement of an Electron Cyclotron Resonance Plasma Thruster\", J. Propulsion and Power 34(5) "
                 "(2018) (HAL hal-01849176)",
     "doi_or_url": "https://hal.science/hal-03839025/document",
     "reason": "HAL served a bot challenge (Anubis); not bypassed. Only the ONERA IEPC/EUCASS papers S06-S09 are used."},
    {"citation": "J. Zhou, F. Taccogna, P. Fajardo, E. Ahedo, \"A study of an air-breathing electrodeless plasma "
                 "thruster discharge\", arXiv:2407.19322 (2024)",
     "doi_or_url": "https://arxiv.org/abs/2407.19322",
     "reason": "Accessed; a hybrid simulation of an electrodeless (helicon-type) thruster on N2/O, not an ECR source. "
               "Outside this lane; no number admitted."},
]


# ------------------------------------------------------------------------------------------------ helpers
def cond(gas="not stated", p="not stated", n="not stated", P="not stated", f="not stated", B="not stated",
         other=None):
    c = {"gas": gas, "pressure_Pa": p, "density_m3": n, "power_W": P, "frequency_Hz": f, "B_T": B}
    if other:
        c["other"] = other
    return c


def src(sid, locator):
    d = dict(SOURCES[sid])
    d["source_id"] = sid
    d["locator"] = locator
    return d


def E(num, sid, locator, cls, quantity, value, units, uncertainty, conditions, match, notes, qualifier=None,
      transformation=None, kind=None):
    e = {"id": f"ECR-E{num:03d}", "source": src(sid, locator), "evidence_class": cls, "quantity": quantity,
         "value": value, "units": units, "uncertainty": uncertainty, "conditions": conditions,
         "applicability_to_abep": {"regime_match": match, "notes": notes}}
    if kind:
        e["source"]["source_kind"] = kind
    if qualifier:
        e["value_qualifier"] = qualifier
    if transformation:
        e["transformation"] = transformation
    return e


NA = None
F245, F42, F425, F58 = 2.45e9, 4.2e9, 4.25e9, 5.8e9
AIR_AMPCAT = "0.48 O2 + 0.52 N2 (bottled molecular surrogate; atomic O replaced by O2 for testing)"

ENTRIES = [
    # ------------------------------------------------------------- A. resonance field and cutoff (as stated)
    E(1, "S06", "Sec. II.A (text after Eq. 1)", "model-derived", "ECR resonance field at 2.45 GHz (as stated)",
      0.0875, "T", "stated to 3 significant figures (875 G)", cond(gas=NA, P=NA, p=NA, n=NA, f=F245, B=0.0875),
      "TBD", "Cross-check for ECR-D001. Applies to any ECR source at 2.45 GHz; the ABEP ECR frequency is not selected.",
      "approx", "875 G -> 0.0875 T (1 G = 1e-4 T)"),
    E(2, "S11", "Sec. 2.2, Eq. (2) and text", "model-derived", "ECR resonance field at 2.45 GHz (as stated)",
      0.0875, "T", "stated to 3 significant figures (87.5 mT)", cond(gas=NA, P=NA, p=NA, n=NA, f=F245, B=0.0875),
      "TBD", "Cross-check for ECR-D001.", "approx", "87.5 mT -> 0.0875 T"),
    E(3, "S11", "Sec. 2.1 and Sec. 3 (mu10 neutralizer)", "model-derived",
      "ECR resonance field at 4.2 GHz for the mu10 neutralizer (as stated)", 0.150, "T",
      "stated as 150 mT and 150.0 mT", cond(gas=NA, P=NA, p=NA, n=NA, f=F42, B=0.150), "TBD",
      "Cross-check for ECR-D002.", "approx", "150.0 mT -> 0.150 T"),
    E(4, "S11", "Sec. 3 (comparison with the mu10 neutralizer)", "model-derived",
      "Cutoff density at 2.45 GHz (as stated)", 7.4e16, "m^-3", "stated to 2 significant figures",
      cond(gas=NA, P=NA, p=NA, n=NA, f=F245, B=NA), "TBD", "Cross-check for ECR-D005.", "approx"),
    E(5, "S11", "Sec. 2.1 (citing its ref. [18] for the mu10 neutralizer)", "model-derived",
      "Cutoff density at 4.2 GHz (as stated)", 2.2e17, "m^-3", "stated to 2 significant figures",
      cond(gas=NA, P=NA, p=NA, n=NA, f=F42, B=NA), "TBD", "Cross-check for ECR-D006.", "approx"),
    E(6, "S01", "Sec. V (Discussion)", "model-derived", "Critical (cutoff) density at 5.8 GHz (as stated)", 4e17,
      "m^-3", "stated to 1 significant figure", cond(gas=NA, P=NA, p=NA, n=NA, f=F58, B=NA), "TBD",
      "Cross-check for ECR-D008.", "approx"),

    # ------------------------------------------------------------------ B. overdense operation / densities
    E(10, "S11", "Table 2 (internal bulk plasma, Vb = 40 V)", "measured",
      "Electron density inside an air-fed 2.45 GHz microwave cathode (Langmuir probe, no applied B)", 1.38e18,
      "m^-3", "+/-0.04e18 (standard deviation of >= 6 repeat readings)",
      cond(gas=AIR_AMPCAT + ", 0.15 mg/s", p="not stated", n="not stated for the diagnostic prototype (source Table 3 model: 1.6e21 m^-3 for 0.15 mg/s air, 5 mm orifice, assumed 373 K)",
           P="not stated in Table 2", f=F245, B=0.0,
           other="Te = 2.66 +/- 0.03 eV; extracted current 0.03 A; diagnostic prototype with straight lambda/4 "
                 "antenna and no electromagnet"),
      "partial", "Air-like gas and overdense (ECR-D009), but measured WITHOUT an applied magnetic field, i.e. not in "
                 "an ECR-heated state. Cathode (electron source), not an ion source; chamber density vs ABEP TBD."),
    E(11, "S11", "Table 2 (internal bulk plasma, Vb = 80 V)", "measured",
      "Electron density inside an air-fed 2.45 GHz microwave cathode (Langmuir probe, no applied B)", 3.71e18,
      "m^-3", "+/-0.10e18 (standard deviation of >= 6 repeat readings)",
      cond(gas=AIR_AMPCAT + ", 0.15 mg/s", P="not stated in Table 2", f=F245, B=0.0,
           other="Te = 2.75 +/- 0.02 eV; extracted current 0.40 A"),
      "partial", "As ECR-E010; overdense ratio in ECR-D010."),
    E(12, "S11", "Table 2 (internal bulk plasma, Vb = 40 V, Xe)", "measured",
      "Electron density inside a Xe-fed 2.45 GHz microwave cathode (Langmuir probe, no applied B)", 7.11e18, "m^-3",
      "+/-0.98e18 (standard deviation of >= 6 repeat readings)",
      cond(gas="Xe, 0.1 mg/s", P="not stated in Table 2", f=F245, B=0.0,
           other="Te = 1.69 +/- 0.14 eV; extracted current 0.49 A"),
      "partial", "Xe path of the RFP (air + Xe); source text calls this an overdense regime (ne >> nc). No applied B."),
    E(13, "S11", "Sec. 2.1 (citing its ref. [18])", "measured",
      "Electron density inside the JAXA mu10 ECR neutralizer relative to the 4.2 GHz cutoff", 2.2e17, "m^-3",
      "lower bound only: stated as 'significantly larger than' the 2.2e17 m^-3 cutoff; magnitude not in accessed text",
      cond(gas="Xe", f=F42, B=0.150), "partial",
      "Evidence that the mu10 neutralizer design (flight heritage) runs overdense; laboratory Langmuir-probe "
      "measurement. Secondary citation.", "lower_bound",
      kind="secondary_citation"),
    E(14, "S10", "Sec. I (Introduction; citing its ref. 13, curling/resonant probe)", "measured",
      "Electron density at the source exit plane of the ONERA coaxial ECR thruster", 1e17, "m^-3",
      "'about'; probe uncertainty not stated in accessed text", cond(gas="Xe (ECRA operation)", f=F245),
      "partial", "Exit plane close to the 2.45 GHz cutoff (ratio ECR-D012). Secondary citation.", "approx",
      "1e11 cm^-3 -> 1e17 m^-3", kind="secondary_citation"),
    E(15, "S10", "Sec. I (Introduction)", "inferred",
      "Electron density inside the ONERA coaxial ECR source (authors' estimate)", 1e18, "m^-3",
      "order of magnitude ('likely ... ~1e12 cm^-3'); electron temperature 'a few tens of eV'",
      cond(gas="Xe (ECRA operation)", f=F245), "partial", "Estimate, not a measurement.", "approx",
      "1e12 cm^-3 -> 1e18 m^-3"),
    E(16, "S01", "Sec. V (Discussion)", "inferred",
      "Plasma density in a 5.8 GHz ECR cavity cathode, xenon (author estimate)", [1e18, 1e19], "m^-3",
      "estimate assuming Bohm-limited ion loss to walls with an ASSUMED Te = 1 eV",
      cond(gas="Xe", p="cold flow 4-80 mTorr (see ECR-E102)", n="neutral ~1-3e20 m^-3 (ECR-E018)", P=115.0, f=F58,
           B="NdFeB array; resonance location not stated"), "partial",
      "Above the 5.8 GHz critical density by ECR-D013 if the estimate holds. Cavity neutral density (ECR-E018) is "
      "two orders of magnitude above the ~1e18 m^-3 the same author assumes for an air ECR thruster (ECR-E141).", "range"),
    E(17, "S01", "Sec. V (Discussion)", "inferred", "Plasma density in a 5.8 GHz ECR cavity cathode, argon",
      [6e17, 3e18], "m^-3", "as ECR-E016 (assumed Te = 1 eV)",
      cond(gas="Ar", p="cold flow 50-250 mTorr (see ECR-E103)", n="neutral ~5-8e20 m^-3", P=115.0, f=F58),
      "no", "Argon is outside the lane's gas scope; kept to document the method and the cutoff comparison.", "range"),
    E(18, "S01", "Sec. V (Discussion)", "inferred", "Neutral density in the 5.8 GHz ECR cavity cathode, xenon",
      [1e20, 3e20], "m^-3", "estimate from flow rates and neutral temperature of 'several hundred to several "
      "thousand K'", cond(gas="Xe", P=115.0, f=F58), "TBD",
      "Compare with the ABEP chamber neutral density once the upstream ICD fixes it.", "range"),
    E(19, "S04", "Sec. I (Introduction)", "assumed",
      "Design intent of the mu20 discharge: plasma density relative to cutoff",
      "moderate plasma density below cutoff (design statement; no density reported)", "n/a",
      "not quantified", cond(gas="Xe", P=100.0, f=[F425, 4.4e9]), "TBD",
      "Shows that under-dense design was a deliberate choice for the 20 cm ion source.", "qualitative"),
    E(20, "S11", "Sec. 2.1 (citing its ref. [13], mu10 neutralizer)", "inferred",
      "Radial extent of microwave propagation around the antenna in an overdense ECR neutralizer", [2.0, 5.0], "mm",
      "authors' analysis ('likely limited to the 2-5 mm skin-depth region')", cond(gas="Xe", f=F42, B=0.150),
      "partial", "Coupling mechanism in overdense operation: near-antenna heating rather than wave propagation into "
                 "the bulk. Secondary citation.", "range", kind="secondary_citation"),
    E(21, "S01", "Sec. III.A (citing Chen 1984, p. 131)", "model-derived",
      "Wave-access condition used in a 5.8 GHz ECR cavity design",
      "microwaves launched parallel to B toward decreasing |B| meet the electron cyclotron resonance before the "
      "right-hand cutoff", "n/a", "cold-plasma wave theory statement", cond(gas=NA, P=NA, f=F58), "TBD",
      "Documented approach to reach densities above the O-mode cutoff (high-field launch). Applicability depends on "
      "the ABEP source geometry (not defined).", "qualitative"),

    # --------------------------------------------------------------- C. absorbed vs forward/transmitted power
    E(30, "S08", "Sec. 2, 'Estimation of the thruster load impedance'", "measured",
      "Microwave coupling rate into the plasma, ONERA ECRA 30 W thruster", [0.90, 0.99], "dimensionless",
      "range over operating points; method not detailed in the accessed paper", cond(gas="Xe", P=30.0, f=F245),
      "partial", "Coupling depends on source impedance, i.e. on geometry and plasma density; power class matches a "
                 "sub-kW ABEP stage but gas (Xe only) and density do not yet.", "range"),
    E(31, "S08", "Sec. 2, 'Estimation of the thruster load impedance'", "measured",
      "Microwave coupling rate into the plasma, ONERA ECRA 200 W thruster", [0.78, 0.89], "dimensionless",
      "range over operating points; authors anticipate further decrease with power and size",
      cond(gas="Xe", P=200.0, f=F245), "partial", "As ECR-E030.", "range"),
    E(32, "S06", "Sec. III.A (Facility)", "inferred",
      "Attenuation of the microwave chain between directional coupler and thruster (cables, feedthrough, DC block, "
      "adapters)", 2.0, "dB", "lower bound ('at least 2 dB'), estimated from measurements on the chain",
      cond(gas="Xe; Ar", P="up to 51 W transmitted", f=F245), "partial",
      "Reported 'transmitted' power (forward minus reflected at the coupler) therefore overstates power delivered "
      "to the source; see ECR-D015. Any ABEP W/A figure must state its power basis.", "lower_bound"),
    E(33, "S11", "Sec. 2.4", "measured",
      "Cathode input power Pin after coaxial-line loss for source powers P0 = 30, 60, 90 W", [24.0, 48.0, 70.0], "W",
      "line loss measured without plasma with a microwave power sensor; reflected power not subtracted",
      cond(gas=NA, P=[30.0, 60.0, 90.0], f=F245), "partial",
      "Line transmission 0.78-0.80 (ECR-D016). Illustrates the gap between generator power and delivered power.",
      "list"),
    E(34, "S11", "Sec. 2.4", "measured", "Reflected microwave power with stub-tuner matching during operation", 1.0,
      "W", "upper bound ('typically reduced to below 1 W')", cond(gas=AIR_AMPCAT + "; Xe", P=[24.0, 70.0], f=F245),
      "partial", "Matching network needed; a stub tuner is a ground-test item whose flight equivalent is TBD.",
      "upper_bound"),
    E(35, "S01", "Sec. III.A", "measured", "Microwave power absorbed in the plasma, 5.8 GHz ECR cavity cathode", 115.0,
      "W", "+/-10 W; reflected power within the 10 W measurement uncertainty after tuning (sliding short, antenna "
      "depth)", cond(gas="Xe; Ar", f=F58, other="magnetron source"), "partial",
      "Tunable cavity (sliding short) in the lab; flight tuning approach TBD."),
    E(37, "S04", "Sec. I (Introduction)", "measured", "Microwave reflection of the mu20 discharge chamber",
      "sufficiently small microwave reflection without use of any stub tuners (not quantified)", "n/a",
      "not quantified", cond(gas="Xe", f=[F425, 4.4e9]), "partial",
      "Qualitative; shows a matched ECR discharge chamber without tuners is achievable for Xe.", "qualitative"),

    # --------------------------------------------------------------------- D. microwave source efficiency
    E(40, "S02", "Sec. II, Table 1 (Microwave Power Amplifiers)", "measured",
      "DC power consumption of one Hayabusa microwave power amplifier (TWT) feeding one ion source and one "
      "neutralizer", 110.0, "W", "flight-system specification as reported; measurement method not stated",
      cond(gas="Xe", P=110.0, f=F42, other="traveling-wave tube; 4 units"), "partial",
      "Heritage (flight) value at 4.2 GHz; frequency and power class differ from a 2.45 GHz sub-kW ABEP stage. "
      "RF/DC ratio in ECR-D017.", transformation="Table 1 as reported"),
    E(41, "S02", "Sec. II, Table 1 (Microwave Power Amplifiers)", "measured",
      "Microwave power delivered by one Hayabusa amplifier to the ion generator and to the neutralizer",
      [32.0, 8.0], "W", "flight-system specification as reported", cond(gas="Xe", f=F42), "partial",
      "Order: [ion generator, neutralizer].", "list"),
    E(42, "S07", "Sec. IV.D and Fig. 9", "measured",
      "DC-to-RF efficiency of a 2.45 GHz solid-state amplifier breadboard (TMI, MINOTOR)", 0.70, "dimensionless",
      "lower bound ('efficiency >70%'); tested at 5 W; 25 W test announced", cond(gas=NA, P=5.0, f=F245,
      other="48 V DC input, 50 ohm output, 2.45 GHz +/- 200 MHz"), "partial",
      "Power level 5 W is far below a sub-kW ABEP stage; efficiency vs power and temperature TBD.", "lower_bound"),
    E(43, "S07", "Fig. 9 caption", "measured", "Mass of the 5 W 2.45 GHz solid-state amplifier breadboard", 100.0, "g",
      "as reported ('weight 100 gr'; dimension 5 cm); excludes housing/thermal/PPU", cond(gas=NA, P=5.0, f=F245),
      "partial", "Breadboard mass, not a flight unit."),
    E(44, "S07", "Sec. IV.D", "assumed", "Target DC-to-RF efficiency for the MINOTOR microwave generator", 0.80,
      "dimensionless", "requirement / goal ('>80%'), not a result", cond(gas=NA, f=F245), "partial",
      "Programme target only.", "lower_bound"),
    E(45, "S20", "Abstract and results", "measured",
      "Power-added efficiency of a single-stage GaN HEMT power amplifier at 2.45 GHz (CW)", 0.785, "dimensionless",
      "device-level measurement; excludes DC-DC conversion, driver stage, isolator/circulator and thermal control",
      cond(gas=NA, P=23.71, f=F245, other="output 43.75 dBm; 28 V drain; gain 15.75 dB at saturation"), "partial",
      "Upper-end device efficiency; a system-level (bus-to-antenna) efficiency will be lower and is TBD."),
    E(46, "S19", "Sec. on forced (Stimulated) generation, Fig. 9 discussion", "measured",
      "DC-to-RF conversion efficiency of a 2.45 GHz CW magnetron (2M219G, nominal 945 W) in free-run mode", 0.54,
      "dimensionless", "approximate ('~54%'); filament power neglected; pulse-train test regime",
      cond(gas=NA, P=945.0, f=F245, other="anode voltage ~3.69 kV (self-excitation threshold)"), "partial",
      "Magnetron class at 2.45 GHz near 1 kW; requires kV supplies; space qualification and life TBD.", "approx"),
    E(47, "S21", "Introduction and 915 MHz section", "measured",
      "DC-to-RF efficiency of a 915 MHz, 75 kW CW industrial magnetron", 0.90, "dimensionless",
      "lower bound ('>90%') from anode I-V and I-E curves; authors state calorimetric confirmation is still needed",
      cond(gas=NA, P=75000.0, f=915e6), "no",
      "Frequency and power far outside an ABEP ECR stage; recorded only to bound magnetron technology.",
      "lower_bound"),
    E(48, "S04", "Sec. II.A", "measured", "Microwave frequency band used for the mu20 ion source",
      [F425, 4.4e9], "Hz", "as reported; TWT amplifier or solid-state amplifiers (efficiency not stated)",
      cond(gas="Xe", P=100.0), "TBD", "Frequency selection for ABEP is open.", "range"),

    # ------------------------------------------------------------------------------------------ E. magnets
    E(50, "S04", "Sec. II.A", "inferred", "Maximum operating temperature limit of the NdFeB magnets used in mu20",
      190.0, "degC", "rating as quoted by the source (grade not stated)", cond(gas="Xe", P=100.0, f=[F425, 4.4e9]),
      "partial", "Rating, not a measurement; margin to the measured operating temperature in ECR-D033."),
    E(51, "S04", "Sec. II.A", "measured", "Operating temperature inside the mu20 ion thruster (magnets)", 135.0,
      "degC", "measurement method and location not stated", cond(gas="Xe", P=100.0, f=[F425, 4.4e9],
      other="nominal 500 mA beam class operation"), "partial",
      "Thermal environment of ECR magnets in a Xe ion source; ABEP (air, VLEO thermal) TBD."),
    E(52, "S04", "Sec. II.A", "measured", "Surface magnetic flux density of NdFeB relative to the original SmCo magnets",
      1.20, "dimensionless", "stated as '20% higher'", cond(gas="Xe"), "TBD",
      "Enabled a 530 mA beam configuration (Table 1). Magnet choice for ABEP TBD.", "approx"),
    E(53, "S17", "Summary table and Recoma 26 sheet ('Max. Recommended Use Temperature')", "inferred",
      "Maximum recommended use temperature, Sm2Co17 (Recoma 26)", 350.0, "degC",
      "manufacturer recommendation; note 3: may be considerably lower under strong demagnetizing fields or a low "
      "load line", cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD",
      "Depends on the load line of the (undefined) ABEP magnetic circuit."),
    E(54, "S17", "Recoma 26 sheet", "measured", "Curie temperature, Sm2Co17 (Recoma 26)", 825.0, "degC",
      "nominal manufacturer value", cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD", "Material property."),
    E(55, "S17", "Recoma 26 sheet, note (1)", "measured",
      "Reversible temperature coefficient of remanence alpha(Br), Sm2Co17 (Recoma 26)", -0.035, "%/degC",
      "nominal; measured between 20 and 150 degC", cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD",
      "Moves the ECR resonance surface as the magnet warms (ECR-D031)."),
    E(56, "S17", "Recoma 26 sheet", "measured", "Density, Sm2Co17 (Recoma 26)", 8.3, "g/cm^3",
      "nominal manufacturer value", cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD",
      "Magnet mass = density x magnet volume; the volume needs an ABEP magnetic-circuit design (TBD)."),
    E(57, "S17", "Summary table and Recoma 18 sheet", "inferred",
      "Maximum recommended use temperature, SmCo5 (Recoma 18)", 250.0, "degC", "manufacturer recommendation",
      cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD", "Material rating."),
    E(58, "S17", "Recoma 18 sheet", "measured", "Curie temperature, SmCo5 (Recoma 18)", 725.0, "degC",
      "nominal manufacturer value", cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD", "Material property."),
    E(59, "S17", "Summary table (temperature-coefficient column)", "measured",
      "Reversible temperature coefficient of remanence, SmCo5 (Recoma 18)", -0.045, "%/degC",
      "nominal", cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD", "Material property."),
    E(60, "S18", "Page 1 text", "inferred", "Usual maximum operating temperature, standard NdFeB grades (Nxx)", 80.0,
      "degC", "guideline value; N52/N50/N50M rated 60 degC", cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD",
      "Material rating; application-dependent."),
    E(61, "S18", "Page 1 text and 'Temperature Ratings' table", "inferred",
      "Maximum working temperature, high-temperature NdFeB grades (VH/AH suffix)", 230.0, "degC",
      "guideline 'based on a high working point'", cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD",
      "Material rating."),
    E(62, "S18", "'Temperature Ratings' table", "measured",
      "Reversible temperature coefficient of remanence alpha(Br), NdFeB (no suffix to VH/AH)", [-0.120, -0.090],
      "%/degC", "typical values, 20-100 degC", cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD",
      "Compare with Sm2Co17 (ECR-E055): ratio in ECR-D034; Br change in ECR-D032.", "range"),
    E(63, "S18", "'Coatings Available' text", "inferred", "Corrosion protection requirement for NdFeB",
      "should always be given a protective coating (Ni-Cu-Ni default); long-term corrosion freedom cannot be "
      "guaranteed", "n/a", "terrestrial (humidity) corrosion guidance; atomic-oxygen behaviour not addressed",
      cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD",
      "Whether magnets see O/O+ depends on the ABEP source layout (TBD).", "qualitative"),
    E(64, "S17", "Introduction text", "inferred", "Corrosion protection requirement for SmCo",
      "can in most cases be used without protective coating", "n/a", "terrestrial guidance; AO not addressed",
      cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD", "As ECR-E063.", "qualitative"),
    E(66, "S08", "Sec. 3 (text and Figs. 3-4)", "measured",
      "Electrical power of a coil pair producing a 14 G transverse (steering) field on the ECRA axis", 5.0, "W",
      "text states 5 W for 14 G; Fig. 4 labels 5.5 W for 14 G (internal inconsistency recorded)",
      cond(gas="Xe", P=24.0, f=F245, B=1.4e-3, other="2 coils, 11 turns of 4 mm^2 Cu each"), "no",
      "Steering field (14 G) is small compared with the 875 G resonance field; says nothing about the power of a "
      "main-field electromagnet (TBD)."),
    E(67, "S11", "Sec. 2.3 and Sec. 3.2", "measured",
      "Main-coil current establishing the 87.5 mT ECR layer across the antenna (650 turns, 0.8 mm Cu, iron yokes)",
      2.0, "A", "measured |B| within 10% of simulation; coil electrical power not reported",
      cond(gas=AIR_AMPCAT + "; Xe", f=F245, B=0.096, other="max |B| along antenna 96 mT at 2 A"), "partial",
      "Electromagnet ECR field is feasible at this scale; power (I^2 R) TBD because resistance is not reported."),

    # ------------------------------------------------------------------- F. ion production / usable current
    E(70, "S04", "Fig. 4 caption (nominal operating condition)", "measured",
      "mu20 ion beam current at 100 W microwave power", 0.500, "A", "as reported (nominal condition)",
      cond(gas="Xe, 10 sccm", p=0.01, P=100.0, f=[F425, 4.4e9], other="beam voltage 1300-1350 V"), "partial",
      "Xe path; ion production cost in ECR-D018. Pressure: typical discharge pressure (ECR-E071)."),
    E(71, "S04", "Sec. II.A", "measured", "Typical discharge pressure during beam extraction, mu20", 0.01, "Pa",
      "'approximately'", cond(gas="Xe, ~10 sccm", p=0.01, P=100.0, f=[F425, 4.4e9]), "TBD",
      "Neutral density equivalent in ECR-D026; compare with the ABEP chamber pressure once the ICD fixes it.",
      "approx"),
    E(72, "S04", "Sec. I (Introduction)", "measured", "mu10 ion beam current saturation level", 0.150, "A",
      "stated for microwave powers above 30 W", cond(gas="Xe", P="> 30", f=F42), "partial",
      "Shows current saturation with microwave power in a 10 cm ECR ion source.", "approx"),
    E(73, "S04", "Abstract and Sec. III.C", "measured",
      "mu20 propellant utilization before / after ion-machined small-hole accelerator grid", [0.667, 0.824],
      "dimensionless", "as reported at 500 mA (10.5 -> 8.5 sccm)", cond(gas="Xe", P=100.0, f=[F425, 4.4e9]),
      "partial", "Utilization depends on grid transparency, not only on the ECR discharge.", "list"),
    E(75, "S05", "Abstract, Sec. III and Fig. 6", "inferred",
      "Ion beam production cost, 10 cm microwave (ECR) ion thruster on argon", 440.0, "W/A",
      "source-computed as (Pi - Pr)/Ib from measured incident/reflected power and beam current",
      cond(gas="Ar, 2.28 sccm", P=37.0, f=F245, other="Vb = 1500 V; utilization 0.50; SmCo magnets"), "no",
      "Argon: outside the lane's gas scope; kept for the power-basis definition (net microwave power)."),
    E(77, "S05", "Sec. III (configuration (1))", "measured",
      "Ion beam current, 10 cm microwave (ECR) ion thruster on xenon", 0.085, "A", "as reported",
      cond(gas="Xe, 2.28 sccm", P=32.0, f=F245, other="incident power Pi; Vb = 1500 V"), "partial",
      "Incident-power basis; ECR-D023 gives an upper bound on the net-power cost."),
    E(78, "S05", "Sec. III (configuration (1))", "measured",
      "Ion beam current, 10 cm microwave (ECR) ion thruster on argon (same conditions as ECR-E077)", 0.064, "A",
      "as reported", cond(gas="Ar, 2.28 sccm", P=32.0, f=F245), "no", "Argon, outside scope."),
    E(79, "S03", "Abstract; Sec. III; Sec. IV", "measured",
      "mu10 ion beam current at 34 W microwave input with anode spacer at 1.55 kV", 0.194, "A",
      "source is internally inconsistent: 191 mA (abstract), 195 mA (Sec. III, at 3.3 sccm), 194 mA (Sec. IV)",
      cond(gas="Xe, 3.3 sccm", P=34.0, f=F425, other="two SmCo magnet rings; forward vs absorbed power not stated"),
      "partial", "Laboratory improvement of the flight design; cost in ECR-D019."),
    E(80, "S03", "Sec. IV (Conclusions)", "inferred",
      "mu10 thrust 'equivalent' to the 194 mA beam (with Isp 3050 s, 450 W, efficiency 40%)", 0.0114, "N",
      "author-computed from beam current, not a balance measurement", cond(gas="Xe, 3.3 sccm", P=450.0, f=F425),
      "partial", "Whole-thruster power (450 W) includes beam power."),
    E(81, "S12", "Abstract", "inferred",
      "Ion energy loss (ion production cost), 2 cm ECR ion source on N2, experiment", 596.2, "W/A",
      "source-computed; power basis ('input power') not specified in the abstract",
      cond(gas="N2, 0.8 ml/min (as reported)", P=8.0, f="not stated in abstract"), "partial",
      "Only source-stated N2 ECR ion-cost figure found in accessed sources; 2 cm, 8 W scale.",
      transformation="abstract value"),
    E(82, "S12", "Abstract", "inferred", "Propellant utilization, 2 cm ECR ion source on N2, experiment", 0.162,
      "dimensionless", "source-computed; charge-state/species basis not stated in abstract",
      cond(gas="N2, 0.8 ml/min (as reported)", P=8.0), "partial", "Same operating point as ECR-E081."),
    E(83, "S12", "Abstract", "model-derived",
      "Ion energy loss, 2 cm ECR ion source on N2, source's global model", 443.9, "W/A",
      "model; model-experiment relative errors 2-32 % on beam current, thrust and Isp (ECR-E087)",
      cond(gas="N2, 1 ml/min (model)", P=8.0), "partial", "Source's own global model, not validated here."),
    E(84, "S12", "Abstract", "measured", "Maximum extracted N2 ion beam current, 2 cm ECR ion source, experiment",
      0.0125, "A", "as reported", cond(gas="N2, 2 ml/min (as reported)", P=8.0), "partial",
      "Model value 16.2 mA at the same point."),
    E(85, "S12", "Abstract", "inferred", "Thrust at maximum beam current, 2 cm ECR ion source on N2, experiment",
      368e-6, "N", "abstract does not state whether balance-measured or computed from beam current; treated as "
      "inferred until the full text is checked", cond(gas="N2, 2 ml/min (as reported)", P=8.0), "partial",
      "Model value 476.6 uN."),
    E(86, "S12", "Abstract", "inferred", "Maximum specific impulse, 2 cm ECR ion source on N2, experiment", 1855.6,
      "s", "as ECR-E085", cond(gas="N2, 0.6 ml/min (as reported)", P=8.0), "partial", "Model value 2095.8 s."),
    E(87, "S12", "Abstract", "model-derived",
      "Relative error between the source's global model and its experiment (beam current, thrust, Isp)",
      [0.02, 0.32], "dimensionless", "as reported", cond(gas="N2", P=8.0), "partial",
      "Indicates the uncertainty of 0-D ECR models on N2 at this scale.", "range"),
    E(88, "S13", "Abstract", "measured", "Extracted N2 ion beam current, 10 cm ECR gridded ion source", 0.258, "A",
      "as reported; frequency, grid voltages and power basis not given in the abstract",
      cond(gas="N2, 10 sccm", P=55.0, f="not stated in abstract"), "partial",
      "Only N2-fed thruster-scale (10 cm) ECR ion-source current found in accessed sources. Abstract only. Cost "
      "in ECR-D020; flow-equivalent ratio in ECR-D030."),
    E(89, "S13", "Abstract", "inferred", "Thrust 'corresponding' to the 258 mA N2 beam (Isp 4311 s)", 0.0088, "N",
      "author-computed from the beam current (wording 'corresponding to'); not a balance measurement per abstract",
      cond(gas="N2, 10 sccm", P=55.0), "partial", "Abstract only."),
    E(90, "S13", "Abstract", "measured",
      "Behaviour at high N2 flow: beam-current drop with a rise in accelerator-grid impingement",
      "beam current drops at high N2 flow; attributed to the space-charge limit rather than discharge extinction; "
      "a higher screen voltage moves the drop to higher flow", "n/a", "qualitative", cond(gas="N2"), "partial",
      "Relevant to an ABEP ECR ion source running at high neutral flow. Abstract only.", "qualitative"),
    E(91, "S06", "Table 1 (0.2 mg/s, 51 W)", "reconstructed",
      "Total ion current, ONERA coaxial ECR magnetic-nozzle thruster, xenon", 0.0654, "A",
      "integrated from gridded Faraday probe profiles at 30 cm (50% grid transmission corrected); uncertainty not "
      "stated", cond(gas="Xe, 0.2 mg/s", p="modelled source range 0.08-0.41 Pa for 0.06-0.3 mg/s (ECR-E096)", P=51.0, f=F245,
                     other="transmitted power incl. >= 2 dB line losses (ECR-E032); NdFeB magnets"),
      "partial", "Cost in ECR-D021. Pressure is the modelled source range for 0.06-0.3 mg/s (ECR-E096)."),
    E(92, "S06", "Table 1 (0.2 mg/s, 51 W)", "reconstructed",
      "Mass utilization efficiency, ONERA coaxial ECR thruster, xenon", 0.451, "dimensionless",
      "from probe-integrated ion current (ECR-E091)", cond(gas="Xe, 0.2 mg/s", P=51.0, f=F245), "partial",
      "2013 prototype; later prototypes differ (ECR-E127/E128)."),
    E(93, "S06", "Table 1 (0.2 mg/s, 51 W)", "reconstructed",
      "Thruster efficiency, ONERA coaxial ECR thruster, xenon (2013 probe-based estimate)", 0.035, "dimensionless",
      "probe-based thrust estimate", cond(gas="Xe, 0.2 mg/s", P=51.0, f=F245), "partial",
      "Historical value; superseded by later balance measurements of newer prototypes."),
    E(94, "S06", "Table 2 (0.2 mg/s, 47 W)", "reconstructed",
      "Total ion current, ONERA coaxial ECR thruster, argon", 0.0667, "A", "as ECR-E091",
      cond(gas="Ar, 0.2 mg/s", P=47.0, f=F245), "no", "Argon, outside scope."),
    E(95, "S06", "Table 2 (0.2 mg/s, 47 W)", "reconstructed",
      "Mass utilization efficiency, ONERA coaxial ECR thruster, argon", 0.139, "dimensionless", "as ECR-E092",
      cond(gas="Ar, 0.2 mg/s", P=47.0, f=F245), "no", "Argon, outside scope."),
    E(96, "S06", "Sec. V (Discussion)", "model-derived",
      "Pressure in the middle of the ECR source for xenon flows 0.06-0.3 mg/s (source's conductance model)",
      [0.08, 0.41], "Pa", "model (effective pumping speed, conductance of a 13 mm x 10 mm cylinder, gas temperature)",
      cond(gas="Xe, 0.06-0.3 mg/s", p=[0.08, 0.41], f=F245), "TBD",
      "Neutral density equivalent in ECR-D027.", "range", "8e-4 to 4.1e-3 mbar -> Pa (x100)"),
    E(97, "S15", "Sec. 3 (text on Tagawa et al. 2013, ref. [48])", "measured",
      "JAXA air-breathing ion engine (ECR) ion beam current with hyperthermal N2 and atomic-oxygen beams", 0.016,
      "A", "as summarized by the review; maximum beam limited by space charge; microwave power not given in the "
      "accessed text", cond(gas="hyperthermal N2 + atomic O (laser-detonation beam source)",
                            other="acceleration voltage 200 V; simulated 140-200 km flow"), "partial",
      "Only ECR ion-beam evidence found that includes atomic oxygen. Secondary citation.", kind="secondary_citation"),
    E(98, "S15", "Sec. 3 (text on Tagawa et al. 2013)", "inferred",
      "Thrust attributed to the 16 mA ABIE beam", 0.13e-3, "N",
      "derivation (balance or computed) not stated in the accessed review text", cond(
          gas="hyperthermal N2 + atomic O", other="acceleration voltage 200 V"), "partial",
      "Secondary citation.", kind="secondary_citation"),
    E(99, "S01", "Abstract and Sec. IV", "measured",
      "Electron current extracted from a 5.8 GHz ECR cavity cathode, xenon", 10.3, "A",
      "as reported (90 mA/W of absorbed power)", cond(gas="Xe", P=115.0, f=F58,
      other="50 V anode bias; NdFeB permanent-magnet array; sapphire vacuum break"), "partial",
      "Cathode (electron source) figure of merit, not an ion production cost. N2-O2 not attempted (ECR-E140)."),
    E(100, "S01", "Abstract and Sec. IV", "measured",
      "Electron current extracted from a 5.8 GHz ECR cavity cathode, argon", 5.7, "A",
      "as reported (50 mA/W)", cond(gas="Ar", P=115.0, f=F58, other="50 V bias"), "no", "Argon, outside scope."),
    E(101, "S01", "Sec. IV (Fig. 8 discussion)", "measured",
      "Increase of extracted electron current with the magnet present, xenon", 3.0, "dimensionless",
      "'approximately a factor of 3'", cond(gas="Xe", P=115.0, f=F58), "partial",
      "Magnetic field (ECR) benefit measured for Xe; for Ar the magnet did not increase current at all flows.",
      "approx"),
    E(102, "S01", "Sec. IV", "measured", "Cold-flow cavity pressure range, xenon data set", [4.0, 80.0], "mTorr",
      "capacitance manometer; range over the data set", cond(gas="Xe", p="see ECR-D035 (converted)", P=115.0,
                                                            f=F58), "TBD",
      "Much higher than typical ion-source discharge pressures (ECR-E071); in Pa: ECR-D035. ABEP chamber pressure "
      "TBD.", "range"),
    E(103, "S01", "Sec. IV", "measured", "Cold-flow cavity pressure range, argon data set", [50.0, 250.0], "mTorr",
      "as ECR-E102", cond(gas="Ar", p="see ECR-D036 (converted)", P=115.0, f=F58), "no",
      "Argon, outside scope; in Pa: ECR-D036.", "range"),
    E(104, "S11", "Sec. 3.2, Fig. 6", "measured",
      "Extracted current of a 2.45 GHz ECR microwave cathode on xenon: zero field vs peak with applied field",
      [0.22, 0.85], "A", "read from text; Fig. 6 values", cond(gas="Xe, 0.1 mg/s", P=48.0, f=F245,
      B="0 -> peak (antenna |B| swept via main-coil current 0-4 A, Table 1)", other="Vb = 40 V; orifice 5 mm"), "partial",
      "ECR benefit for Xe: about four-fold.", "list"),
    E(105, "S11", "Sec. 3.2, Fig. 6", "measured",
      "Extracted current of the same cathode on air: suppression with increasing applied field", [0.06, 0.01], "A",
      "read from text", cond(gas=AIR_AMPCAT + ", 0.1 mg/s", P=48.0, f=F245,
                             B="0 -> increased antenna |B|", other="Vb = 40 V; orifice 5 mm"), "partial",
      "At nominal density the applied (ECR) field did not help on air; authors attribute this to molecular "
      "energy sinks (dissociation, vibrational/rotational excitation).", "list"),
    E(106, "S11", "Sec. 4.2, Fig. 11(b)", "measured",
      "Extracted current on air at reduced neutral density: zero field vs peak with applied field",
      [0.23, 0.43], "A", "read from text", cond(gas=AIR_AMPCAT + ", 0.1 mg/s", n=2.4e20, P=48.0, f=F245,
                                                  B="0 -> applied field; the field at the 0.43 A peak is not restated in the text (Sec. 7 reports that "
                                                    "|B| = 36 mT at the antenna supports > 0.4 A at this density)",
                                                  other="Vb = 120 V; orifice 10 mm; "
                                                  "neutral density from the source's model (Table 3)"),
      "partial", "Magnetic confinement helped on air only at reduced neutral density.", "list"),
    E(107, "S11", "Sec. 6.2, Fig. 16(a)", "measured",
      "Extracted current on air with reduced orifice field (11.7 -> 4.2 mT): before / after", [0.36, 0.45], "A",
      "read from text (+25 %)", cond(gas=AIR_AMPCAT + ", 0.1 mg/s", P=48.0, f=F245,
                                     B="antenna |B| 0.048 T", other="Vb = 120 V; orifice 10 mm"), "partial",
      "Extraction-region field matters in addition to the ECR layer.", "list"),
    E(109, "S11", "Sec. 2.3 and Table 3", "model-derived",
      "Neutral density inside the air-fed cathode (0.1 mg/s, 5 mm orifice)", 1.0e21, "m^-3",
      "free-molecular model with an ASSUMED Tg = 373 K; agrees with pressure measured without plasma; authors state "
      "the effective value with plasma is 'most probably lower'", cond(gas=AIR_AMPCAT + ", 0.1 mg/s", f=F245),
      "TBD", "Cathode chamber; not the ABEP ion-source chamber (TBD from ICD)."),
    E(110, "S11", "Sec. 2.4", "measured", "Test-facility background pressure over the air flows tested",
      [2.2e-2, 4.8e-2], "Pa", "cold-cathode gauge; < 1e-3 Pa without flow", cond(gas=AIR_AMPCAT), "partial",
      "Facility effect indicator.", "range", "2.2-4.8e-4 mbar -> Pa (x100)"),
    E(111, "S11", "Sec. 1 (AETHER-derived targets)", "assumed",
      "Target extracted current for an air-breathing cathode (AETHER platform targets)", [0.25, 3.0], "A",
      "requirement of another programme, not evidence", cond(gas="0.48 O + 0.52 N2 (target composition)",
                                                            n=[0.5e18, 5e18], P="<= 200 (maximum)",
                                                            other="inlet air flow 0.04-0.1 mg/s; 190-240 km"),
      "partial", "Another platform's requirements; the Vyovrinda values come from the upstream ICD (TBD).",
      "range"),
    E(112, "S11", "Sec. 2.1 (citing its ref. [15])", "measured",
      "JAXA mu10 ECR neutralizer nominal electron current", 0.18, "A",
      "as cited; standalone test", cond(gas="Xe, 0.07 mg/s", P=8.0, f=F42, B=0.150,
                                        other="32 V bias neutralizer-anode; SmCo magnet"), "partial",
      "Flight-heritage neutralizer on Xe (Xe path of RFP). Secondary citation.", kind="secondary_citation"),
    E(113, "S11", "Sec. 2.1 (citing its ref. [16])", "measured", "mu20 ECR neutralizer maximum current, xenon", 0.5,
      "A", "as cited; S01 cites 0.50 A at 15 W for the mu20 neutralizer (ECR-E114): power basis conflicts",
      cond(gas="Xe", P=20.0, f="4.2-4.4 GHz class (not stated)"), "partial", "Secondary citation.",
      kind="secondary_citation"),
    E(114, "S01", "Sec. III (citing Kuninaka & Nishiyama AIAA 2003-5011)", "measured",
      "mu20 ECR neutralizer current at 15 W, xenon", 0.50, "A", "as cited (33 mA/W); conflicts with ECR-E113 (20 W)",
      cond(gas="Xe", P=15.0), "partial", "Secondary citation.", kind="secondary_citation"),
    E(115, "S11", "Sec. 2.1 (citing Kamhawi, Foster, Patterson 2004)", "measured",
      "Maximum extracted current of an antenna-fed ECR cathode, xenon, with its power cost", 2.6, "A",
      "as cited; power cost 98 W/A", cond(gas="Xe", P="not stated in accessed text (power cost 98 W/A)"),
      "partial", "Secondary citation.", kind="secondary_citation"),
    E(116, "S24", "Abstract", "measured",
      "Coupled operation of an ECR microwave cathode running on air with a cylindrical Hall thruster",
      "stable thruster operation demonstrated with the cathode on both xenon and air (thrust directly measured)",
      "n/a", "qualitative; numbers for air not in abstract", cond(gas="cathode: air or Xe; thruster: Xe 0.5-0.7 mg/s",
                                                                P=[100.0, 300.0],
                                                                f="2.45 GHz per S11 (same device; not in this abstract)",
                                                                other="power_W is the Hall thruster power level; the "
                                                                      "cathode microwave power is not in the abstract"),
      "partial",
      "Cathode-on-air demonstration only; the thruster ran on Xe. Abstract only.", "qualitative"),

    # --------------------------------------------------------------------------------------------- G. heritage
    E(120, "S02", "Sec. II and Table 2", "measured", "Rated thrust of one mu10 (with 3000 s Isp and 350 W)", 0.008,
      "N", "rating as reported", cond(gas="Xe", P=350.0, f=F42), "partial",
      "Flight-heritage ECR ion engine (Xe). The RFP asks 12-25 mN (repository summary)."),
    E(121, "S02", "Abstract and Sec. VI", "measured",
      "Accumulated Hayabusa ion-engine operation (4 x mu10), August 2009", 35000.0, "h x unit",
      "flight record; 40 kg Xe consumed; delta-V 1,900 m/s", cond(gas="Xe", f=F42), "partial",
      "Unit-hours summed over engines, not a single-unit life."),
    E(122, "S03", "Sec. I", "measured", "Total established Hayabusa ion-engine operation time (through Earth return)",
      39600.0, "h", "as reported (unit convention not restated; ECR-E121 uses hour x unit)", cond(gas="Xe", f=F42),
      "partial", "Flight record; per-unit hours not given in accessed text."),
    E(123, "S02", "Sec. II", "measured",
      "Dry mass of the Hayabusa ion engine system (4 x mu10, gimbal, tank)", 59.0, "kg",
      "as reported (system level; includes components not part of an ECR stage)", cond(gas="Xe"), "no",
      "System mass, not an ECR-stage mass; recorded only as context."),
    E(124, "S02", "Sec. IV", "measured", "Hayabusa IES thrust range during the outward cruise (throttling)",
      [0.0045, 0.025], "N", "as reported: 4.5 mN at 250 W to 25 mN at 1.1 kW (system)", cond(gas="Xe",
                                                                                     P=[250.0, 1100.0], f=F42),
      "partial", "Flight throttling of an ECR ion-engine system.", "range"),
    E(125, "S03", "Sec. I", "measured", "mu10 thrust for Hayabusa2 after grid/injection changes", 0.010, "N",
      "as stated", cond(gas="Xe", f=F425), "partial", "Heritage."),
    E(126, "S04", "Abstract and Table 1", "measured", "mu20 endurance test duration reached", 5000.0, "h",
      "as reported; ion source run 2,300 h without neutralizer", cond(gas="Xe, ~10 sccm", P=100.0,
                                                                         f=[F425, 4.4e9]), "partial",
      "Ground endurance on Xe; RFP asks > 15,000 h firing (repository summary). No air endurance data found."),
    E(127, "S07", "Sec. III.F (state of the art)", "measured",
      "ONERA ECRA total efficiency at 30 W (about 1 mN, ion energy about 250 eV)", 0.16, "dimensionless",
      "'about'", cond(gas="Xe", P=30.0, f=F245), "partial", "Xe only.", "approx"),
    E(128, "S08", "Sec. 1 (Introduction)", "measured",
      "ONERA ECRA total thrust efficiency before / after the H2020 MINOTOR project", [0.20, 0.45], "dimensionless",
      "'about'; also Isp above 2000 s and thrust-to-power above 60 mN/kW stated", cond(gas="Xe", P=[30.0, 200.0],
                                                                                       f=F245), "partial",
      "Xe only ('so far tested and characterized using Xenon').", "list"),
    E(129, "S09", "Abstract and Sec. II.A", "measured",
      "Best total efficiency, ONERA ECR-PM-V1 (20 mm source, 2.3 mm inner conductor), balance-measured", 0.125,
      "dimensionless", "as reported; operating range 20-60 W, 0.05-0.2 mg/s Xe, thrust 300 uN-1.2 mN",
      cond(gas="Xe", P=[20.0, 60.0], f=F245), "partial", "Xe; krypton also tested (outside scope)."),
    E(130, "S07", "Sec. III.E.1(b)", "inferred",
      "Facility background pressure below which ECRA is considered to work properly", 1e-3, "Pa",
      "consortium statement ('less than 1e-5 mbar'); HET contrasted at up to 1e-4 mbar",
      cond(gas="Xe", f=F245), "partial",
      "Ground-test facility requirement for magnetic-nozzle ECR thrusters; relevant to any ABEP ground test.",
      "upper_bound", "1e-5 mbar -> 1e-3 Pa"),
    E(131, "S07", "Sec. III.B", "measured", "Electron temperature measured in the ECRA (upper range)", [40.0, 60.0],
      "eV", "'measure up to 40-60 eV'", cond(gas="Xe", f=F245), "partial",
      "Ion energies up to 400 eV also stated.", "range"),
    E(132, "S07", "Sec. V (Conclusion)", "inferred", "Technology readiness of the ECRA thruster and generator (2019)",
      4.0, "TRL", "self-assessment", cond(gas="Xe", f=F245), "partial", "Self-assessed TRL."),
    E(133, "S08", "Sec. 1 (Introduction)", "inferred", "Propellants on which the ECRA has been characterized",
      "tested and characterized using xenon so far; 'a priori compatible with any propellant gas'", "n/a",
      "claim of compatibility not demonstrated in the accessed ECRA sources for N2/O2/air", cond(gas="Xe"), "TBD",
      "No N2/O2/air data found for the ONERA ECRA in accessed sources.", "qualitative"),
    E(134, "S07", "Sec. III.D (potential advantages)", "assumed",
      "Claimed propellant compatibility of ECRA including oxygen",
      "'complete compatibility with all propellants, including oxygen' listed as a potential advantage", "n/a",
      "claim, not a measurement", cond(gas="all (claimed)"), "TBD", "Assumption to be tested.", "qualitative"),

    # --------------------------------------------------------------------- H. air-breathing ECR specifics
    E(140, "S01", "Sec. V (Discussion)", "measured", "Status of N2-O2 operation of the 5.8 GHz ECR cathode (2009)",
      "current extraction from a nitrogen-oxygen mixture has not been attempted yet", "n/a", "status statement",
      cond(gas="N2-O2 (not tested)"), "TBD", "Gap.", "qualitative"),
    E(141, "S01", "Sec. II", "assumed",
      "Neutral density assumed for an air-fed ECR ion engine ('roughly similar to existing ECR thrusters')", 1e18,
      "m^-3", "order of magnitude; exhaust open area ~1e-2 m^2 assumed alongside", cond(gas="O, N2 (atmospheric)",
                                                                                         n=1e18), "TBD",
      "An author assumption, not a measured ECR operating limit.", "approx"),
    E(142, "S01", "Sec. V (Discussion)", "model-derived",
      "Maximum passive compression factor at 220 km vs that needed for 1e20 m^-3 cavity density", [1e3, 1e5],
      "dimensionless", "order of magnitude from the source's Eq. (8) with cold-flow assumptions; [achievable, needed]",
      cond(gas="atmospheric O, N2", n=1e20), "TBD",
      "Illustrates the density gap between high-pressure ECR cathodes and intake-fed chambers.", "list"),
    E(143, "S15", "Sec. 3 (text on Diamant 2010, ref. [43])", "assumed",
      "Pressure delivered to a 2-stage (ECR + cylindrical Hall) air-breathing thruster at an assumed compression "
      "ratio of 500", 0.01, "Pa", "study assumption as summarized by the review", cond(gas="atmospheric", p=0.01,
                                                                                         other="~220 km"), "TBD",
      "Secondary citation of a closed paper; pressure is an assumption of that study.", "approx",
      kind="secondary_citation"),
    E(144, "S14", "Abstract", "measured",
      "Sustained ECR plasma discharge at pressures consistent with post-intake compression near 200 km",
      "sustained discharge achieved (MHz-range birdcage resonator with tailored magnetic field); numbers not in "
      "the abstract", "n/a", "qualitative; abstract only", cond(gas="not stated in abstract",
                                                                p="'representative of VLEO' (value not in abstract)",
                                                                f="MHz range (value not in abstract)"),
      "partial", "The only accessed source reporting ECR ignition at VLEO-representative pressure; values TBD from "
                 "full text.", "qualitative"),
    E(146, "S01", "Sec. II", "assumed",
      "Thruster efficiency and mass utilization assumed for an air-fed ECR ion engine", [0.25, 0.50], "dimensionless",
      "stated as assumed 'without justification'; [thruster efficiency, mass utilization]",
      cond(gas="O, N2 (atmospheric)"), "TBD", "Assumption in the literature, not evidence.", "list"),

    # ----------------------------------------------------------------------- I. materials / atomic oxygen
    E(150, "S16", "Table 4 (MISSE 2 PEACE, sample 2-E5-25)", "measured",
      "Atomic-oxygen erosion yield of pyrolytic graphite in LEO", 4.15e-25, "cm^3/atom",
      "error analysis deferred by the source (not stated in this TM)",
      cond(gas="LEO ram atomic oxygen (ISS, ~4 years)", other="fluence 8.43e21 atoms/cm^2 (ECR-E152)"), "partial",
      "Carbon is used for ECR ion-thruster grids (mu10 C/C, ECR-E153). LEO ram AO (directed, ~orbital energy) is not "
      "the O/O+ environment inside an ECR discharge chamber; chamber erosion rates TBD."),
    E(151, "S16", "Sec. on fluence determination and Table 4", "measured",
      "Reference atomic-oxygen erosion yield of Kapton H (fluence witness)", 3.0e-24, "cm^3/atom",
      "well-characterized reference value used by the source", cond(gas="LEO ram atomic oxygen"), "partial",
      "Witness-material reference for any AO exposure test of ECR-stage materials."),
    E(152, "S16", "Sec. 9 (MISSE 2 tray 1 E5 AO fluence)", "reconstructed",
      "Atomic-oxygen fluence of the MISSE 2 PEACE exposure", 8.43e21, "atoms/cm^2",
      "from Kapton H witness mass loss using the reference erosion yield", cond(gas="LEO ram atomic oxygen"),
      "partial", "Context for ECR-E150/E151."),
    E(153, "S02", "Sec. II (features 2 and 5)", "measured",
      "Material and design choices of the flight mu10 relevant to oxygen",
      "cathode-less ECR plasma and ECR neutralizers avoid hollow-cathode emitter degradation from oxygen-"
      "contaminated propellant; grids are carbon-carbon composite", "n/a", "design statements",
      cond(gas="Xe"), "partial", "C/C grids would be exposed to O/O+ in an air-fed version (erosion rate TBD).",
      "qualitative"),
    E(154, "S04", "Sec. III.C", "measured", "Carbon deposition and grid conditioning in the mu20 endurance test",
      "discharge-chamber walls needed cleaning of carbon deposited from grid sputtering; grid surfaces polished "
      "early in the test to keep voltage standoff", "n/a", "qualitative", cond(gas="Xe"), "partial",
      "Sputtered carbon and its interaction with oxygen in an air-fed source: TBD.", "qualitative"),
    E(155, "S11", "Sec. 1 (citing Andreussi et al. 2022, its ref. [1])", "measured",
      "Air fraction in xenon at which a LaB6 hollow cathode showed significant emitter and structure erosion", 0.12,
      "dimensionless", "as cited (fraction of a 0.48 O2 + 0.52 N2 mixture in xenon)",
      cond(gas="Xe + 12 % (0.48 O2 + 0.52 N2)"), "partial",
      "Motivation for electrodeless (microwave/ECR) cathodes on air. Secondary citation.",
      kind="secondary_citation"),
    E(157, "S11", "Sec. 2.3", "measured", "Materials of the air-fed ECR microwave cathode",
      "plasma-interfacing surfaces 304 stainless steel (chosen partly for resistance to oxidation from the air "
      "plasma at elevated temperature); molybdenum L-antenna in a boron-nitride sleeve", "n/a",
      "design choice; no erosion data reported", cond(gas=AIR_AMPCAT, f=F245), "partial",
      "Continuous operation on air and erosion mitigation are stated as future work (gap).", "qualitative"),
    E(158, "S01", "Sec. III.A", "measured", "Vacuum-break (microwave window) materials of the 5.8 GHz ECR cavity",
      "sapphire or fused silica; alumina replaced due to porosity concerns; relative permittivity 9.6 "
      "(alumina/sapphire) vs 3.8 (fused silica) as quoted", "n/a", "qualitative; permittivities quoted by source",
      cond(gas="Xe; Ar", f=F58), "partial", "Window AO/O+ compatibility TBD.", "qualitative"),
    E(159, "S07", "Sec. IV.B", "measured", "Antenna damage and coating in the ECRA",
      "evidence of impacts on the antenna; first test of a boron-nitride coating", "n/a", "qualitative",
      cond(gas="Xe", f=F245), "partial", "Antenna erosion is a life item for antenna-fed ECR sources.",
      "qualitative"),
    E(160, "S09", "Sec. II.A", "measured", "Structural materials of ONERA ECR-PM-V1",
      "aluminium alloy structure; plasma-source back plate boron nitride", "n/a", "qualitative",
      cond(gas="Xe", f=F245), "partial", "BN in contact with plasma; O/O+ compatibility TBD.", "qualitative"),

    # ---------------------------------------------------------------------------------------- J. thermal
    E(170, "S06", "Sec. IV (Results)", "measured",
      "Transmitted microwave power limit set by heating of cables and microwave components", 51.0, "W",
      "as reported (maximum reached)", cond(gas="Xe, 0.2 mg/s", P=51.0, f=F245), "partial",
      "Line/component heating limits usable power even at tens of W.", "upper_bound"),
    E(171, "S11", "Sec. 4.1", "measured", "Wall temperature of the air-fed microwave cathode (thermocouple)", 373.0,
      "K", "'representative' value used for the neutral-temperature assumption; operating point not stated",
      cond(gas=AIR_AMPCAT + "; Xe", f=F245), "partial", "Low-power (tens of W) device."),
    E(172, "S08", "Sec. 3 (Experimental setup)", "measured", "Warm-up time used before ECRA measurements", 1.0, "h",
      "'at least one hour' to reach a reproducible, stationary regime", cond(gas="Xe, 1 sccm", P=24.0, f=F245),
      "partial", "Thermal transient affects ECR operating point.", "lower_bound"),
    E(173, "S14", "Abstract", "measured", "Engineering limit identified for a MHz-range ECR ABEP source",
      "resonator heating imposes engineering limits on power scaling", "n/a", "qualitative; abstract only",
      cond(f="MHz range (value not in abstract)"), "partial", "Thermal item for any resonator-coupled source.",
      "qualitative"),
]

# ------------------------------------------------------------------------------------------ derived entries
def D(num, cls, quantity, func, inputs, units, uncertainty, conditions, match, notes, source_id="S22",
      locator="formula; CODATA 2022", qualifier=None, access=None):
    s = src(source_id, locator)
    if access:
        s["access"] = access
    e = {"id": f"ECR-D{num:03d}", "source": s, "evidence_class": cls, "quantity": quantity, "value": None,
         "units": units, "uncertainty": uncertainty, "conditions": conditions,
         "applicability_to_abep": {"regime_match": match, "notes": notes},
         "derivation": {"function": func, "formula": FUNCTION_FORMULAS[func], "inputs": inputs}}
    if qualifier:
        e["value_qualifier"] = qualifier
    return e


FUNCTION_FORMULAS = {
    "b_res_T": "B_res = 2*pi*f*m_e/e",
    "n_cutoff_m3": "n_c = eps0*m_e*(2*pi*f)^2/e^2",
    "ratio": "num/den",
    "db_to_power_fraction": "fraction = 10^(-loss_dB/10)",
    "elementwise_ratio": "num[i]/den[i]",
    "sum_ratio": "sum(num)/den",
    "power_per_current": "P/I (W/A = eV per singly charged ion)",
    "w_per_a_to_ev_per_ion": "(1 J/C) * e / (e J/eV) = 1 eV per ion",
    "neutral_density_m3": "n = p/(k_B*T)",
    "particles_per_s_per_sccm": "p0*1e-6 m^3/(k_B*T0)/60 s, p0 = 101325 Pa, T0 = 273.15 K (assumed reference)",
    "equivalent_current_A": "I_eq = e * Q_sccm * particles_per_s_per_sccm",
    "br_reversible_change_pct": "dBr/Br [%] = alpha[%/C] * dT[C] (linear, reversible part only)",
    "difference": "a - b",
    "mtorr_to_pa": "p[Pa] = p[mTorr] * 1e-3 * 101325/760",
}


def ref(eid, index=None):
    r = {"ref": eid}
    if index is not None:
        r["index"] = index
    return r


FORMULA_NOTE = ("Applies to any ECR source at this frequency; the ABEP ECR frequency is not selected.")

DERIVED = [
    D(1, "model-derived", "ECR resonance field at 2.45 GHz", "b_res_T", {"f_Hz": F245}, "T",
      "exact to CODATA precision (fundamental harmonic, non-relativistic)", cond(gas=NA, P=NA, p=NA, n=NA, f=F245,
                                                                                 B=NA), "TBD", FORMULA_NOTE),
    D(2, "model-derived", "ECR resonance field at 4.2 GHz", "b_res_T", {"f_Hz": F42}, "T", "as ECR-D001",
      cond(gas=NA, P=NA, p=NA, n=NA, f=F42, B=NA), "TBD", FORMULA_NOTE),
    D(3, "model-derived", "ECR resonance field at 4.25 GHz", "b_res_T", {"f_Hz": F425}, "T", "as ECR-D001",
      cond(gas=NA, P=NA, p=NA, n=NA, f=F425, B=NA), "TBD", FORMULA_NOTE),
    D(4, "model-derived", "ECR resonance field at 5.8 GHz", "b_res_T", {"f_Hz": F58}, "T", "as ECR-D001",
      cond(gas=NA, P=NA, p=NA, n=NA, f=F58, B=NA), "TBD", FORMULA_NOTE),
    D(5, "model-derived", "O-mode cutoff density at 2.45 GHz", "n_cutoff_m3", {"f_Hz": F245}, "m^-3",
      "exact to CODATA precision (cold, unmagnetized O-mode cutoff)", cond(gas=NA, P=NA, p=NA, n=NA, f=F245, B=NA),
      "TBD", FORMULA_NOTE),
    D(6, "model-derived", "O-mode cutoff density at 4.2 GHz", "n_cutoff_m3", {"f_Hz": F42}, "m^-3", "as ECR-D005",
      cond(gas=NA, P=NA, p=NA, n=NA, f=F42, B=NA), "TBD", FORMULA_NOTE),
    D(7, "model-derived", "O-mode cutoff density at 4.25 GHz", "n_cutoff_m3", {"f_Hz": F425}, "m^-3", "as ECR-D005",
      cond(gas=NA, P=NA, p=NA, n=NA, f=F425, B=NA), "TBD", FORMULA_NOTE),
    D(8, "model-derived", "O-mode cutoff density at 5.8 GHz", "n_cutoff_m3", {"f_Hz": F58}, "m^-3", "as ECR-D005",
      cond(gas=NA, P=NA, p=NA, n=NA, f=F58, B=NA), "TBD", FORMULA_NOTE),
    D(9, "model-derived", "Overdense ratio n_e/n_c, air-fed cathode, Vb = 40 V (ECR-E010 / ECR-D005)", "ratio",
      {"num": ref("ECR-E010"), "den": ref("ECR-D005")}, "dimensionless", "inherits ECR-E010 (+/-3 %)",
      cond(gas=AIR_AMPCAT, f=F245, B=0.0), "partial", "Measured without applied B (not ECR-heated).",
      source_id="S11", locator="derived from Table 2 and ECR-D005"),
    D(10, "model-derived", "Overdense ratio n_e/n_c, air-fed cathode, Vb = 80 V (ECR-E011 / ECR-D005)", "ratio",
      {"num": ref("ECR-E011"), "den": ref("ECR-D005")}, "dimensionless", "inherits ECR-E011 (+/-3 %)",
      cond(gas=AIR_AMPCAT, f=F245, B=0.0), "partial", "As ECR-D009.", source_id="S11",
      locator="derived from Table 2 and ECR-D005"),
    D(11, "model-derived", "Overdense ratio n_e/n_c, Xe-fed cathode, Vb = 40 V (ECR-E012 / ECR-D005)", "ratio",
      {"num": ref("ECR-E012"), "den": ref("ECR-D005")}, "dimensionless", "inherits ECR-E012 (+/-14 %)",
      cond(gas="Xe", f=F245, B=0.0), "partial", "As ECR-D009.", source_id="S11",
      locator="derived from Table 2 and ECR-D005"),
    D(12, "model-derived", "Density ratio n_e/n_c at the ECRA source exit plane (ECR-E014 / ECR-D005)", "ratio",
      {"num": ref("ECR-E014"), "den": ref("ECR-D005")}, "dimensionless", "inherits the 'about' of ECR-E014",
      cond(gas="Xe", f=F245), "partial", "Exit plane close to cutoff; in-source density likely higher (ECR-E015).",
      source_id="S10", locator="derived from Sec. I and ECR-D005", qualifier="approx"),
    D(13, "model-derived", "Density ratio n_e/n_c for the 5.8 GHz cavity estimate (ECR-E016 / ECR-D008)", "ratio",
      {"num": ref("ECR-E016"), "den": ref("ECR-D008")}, "dimensionless",
      "inherits the assumed-Te estimate of ECR-E016", cond(gas="Xe", f=F58), "partial", "Range.",
      source_id="S01", locator="derived from Sec. V and ECR-D008", qualifier="range"),
    D(14, "model-derived", "Density ratio n_e/n_c inside the ECRA source, authors' estimate (ECR-E015 / ECR-D005)",
      "ratio", {"num": ref("ECR-E015"), "den": ref("ECR-D005")}, "dimensionless",
      "inherits the order-of-magnitude estimate of ECR-E015", cond(gas="Xe", f=F245), "partial",
      "Estimate-based; the measured exit-plane value is ECR-D012.", source_id="S10",
      locator="derived from Sec. I and ECR-D005", qualifier="approx"),
    D(15, "model-derived", "Upper bound of power fraction delivered through a >= 2 dB microwave chain (ECR-E032)",
      "db_to_power_fraction", {"loss_dB": ref("ECR-E032")}, "dimensionless",
      "upper bound (attenuation 'at least 2 dB')", cond(gas="Xe; Ar", f=F245), "partial",
      "Reported ONERA 2013 'transmitted' powers overstate delivered power by at least the inverse of this fraction.", source_id="S06",
      locator="derived from Sec. III.A", qualifier="upper_bound"),
    D(16, "inferred", "Coaxial-line transmission fraction Pin/P0 at 30, 60, 90 W (ECR-E033)", "elementwise_ratio",
      {"num": ref("ECR-E033"), "den": [30.0, 60.0, 90.0]}, "dimensionless",
      "from measured Pin without plasma; reflected power not included", cond(gas=NA, P=[30.0, 60.0, 90.0], f=F245),
      "partial", "Line loss 20-22 % in a laboratory coaxial feed.", source_id="S11",
      locator="derived from Sec. 2.4", qualifier="list"),
    D(17, "inferred", "RF-out / DC-in ratio of one Hayabusa microwave amplifier ((32 + 8)/110)", "sum_ratio",
      {"num": ref("ECR-E041"), "den": ref("ECR-E040")}, "dimensionless",
      "spec values; assumes the 110 W includes all amplifier losses and both outputs",
      cond(gas="Xe", P=110.0, f=F42), "partial", "Flight TWT system at 4.2 GHz, tens-of-W class.",
      source_id="S02", locator="derived from Table 1"),
    D(18, "inferred", "Ion production cost of the mu20 at its nominal point (100 W / 0.5 A)", "power_per_current",
      {"P_W": 100.0, "I_A": ref("ECR-E070")}, "W/A", "microwave power basis (forward vs absorbed not stated)",
      cond(gas="Xe, 10 sccm", p=0.01, P=100.0, f=[F425, 4.4e9]), "partial",
      "Matches the 200 W/A the source gives as the mu20 expectation.", source_id="S04",
      locator="derived from Fig. 4 caption"),
    D(19, "inferred", "Ion production cost of the improved mu10 (34 W / [191, 194, 195] mA)", "power_per_current",
      {"P_W": 34.0, "I_A": [0.191, 0.194, 0.195]}, "W/A",
      "spread reflects the source's inconsistent beam-current values; power basis not stated",
      cond(gas="Xe, 3.3 sccm", P=34.0, f=F425), "partial", "Order: [abstract, conclusion, Sec. III] currents.",
      source_id="S03", locator="derived from abstract, Sec. III, Sec. IV", qualifier="list"),
    D(20, "inferred", "Ion production cost of the 10 cm N2 ECR gridded source (55 W / 0.258 A)", "power_per_current",
      {"P_W": 55.0, "I_A": ref("ECR-E088")}, "W/A", "'input microwave power' basis (forward vs absorbed not stated)",
      cond(gas="N2, 10 sccm", P=55.0), "partial", "Abstract-only inputs.", source_id="S13",
      locator="derived from abstract", access="abstract_only"),
    D(21, "inferred", "Power per ion current, ONERA ECR thruster, Xe (51 W / 65.4 mA)", "power_per_current",
      {"P_W": 51.0, "I_A": ref("ECR-E091")}, "W/A",
      "transmitted power includes >= 2 dB line loss; ion current probe-reconstructed", cond(gas="Xe, 0.2 mg/s",
                                                                                           P=51.0, f=F245),
      "partial", "Magnetic-nozzle thruster: the current is the whole plume ion current, not a grid-extracted beam.",
      source_id="S06", locator="derived from Table 1"),
    D(22, "inferred", "Power per ion current, ONERA ECR thruster, Ar (47 W / 66.7 mA)", "power_per_current",
      {"P_W": 47.0, "I_A": ref("ECR-E094")}, "W/A", "as ECR-D021", cond(gas="Ar, 0.2 mg/s", P=47.0, f=F245), "no",
      "Argon, outside scope.", source_id="S06", locator="derived from Table 2"),
    D(23, "inferred", "Incident-power cost, 10 cm microwave ion thruster, Xe (32 W / 85 mA)", "power_per_current",
      {"P_W": 32.0, "I_A": ref("ECR-E077")}, "W/A",
      "upper bound on the net-power cost because reflected power is not subtracted",
      cond(gas="Xe, 2.28 sccm", P=32.0, f=F245), "partial", "Incident power basis.", source_id="S05",
      locator="derived from Sec. III", qualifier="upper_bound"),
    D(25, "model-derived", "Energy per singly charged ion corresponding to 1 W/A", "w_per_a_to_ev_per_ion", {},
      "eV per ion", "exact identity", cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "yes",
      "Unit identity used throughout this audit: X W/A = X eV per singly charged ion (multiply charged ions change "
      "the conversion)."),
    D(26, "model-derived", "Neutral density at the mu20 typical discharge pressure 0.01 Pa for T = 300 and 600 K",
      "neutral_density_m3", {"p_Pa": ref("ECR-E071"), "T_K": [300.0, 600.0]}, "m^-3",
      "gas temperature ASSUMED (300-600 K); pressure 'approximately'", cond(gas="Xe", p=0.01, f=[F425, 4.4e9]),
      "TBD", "Compare with the ABEP chamber density (ICD, TBD).",
      source_id="S04", locator="derived from Sec. II.A", qualifier="range"),
    D(27, "model-derived", "Neutral density range in the ONERA ECR source (0.08-0.41 Pa) at an assumed 300 K",
      "neutral_density_m3", {"p_Pa": ref("ECR-E096"), "T_K": 300.0}, "m^-3",
      "gas temperature ASSUMED 300 K; inputs are themselves modelled (ECR-E096)", cond(gas="Xe", f=F245), "TBD",
      "Compare with ABEP chamber density (ICD, TBD).", source_id="S06", locator="derived from Sec. V",
      qualifier="range"),
    D(28, "model-derived", "Particles per second in 1 sccm (reference 0 C, 101325 Pa)", "particles_per_s_per_sccm",
      {}, "s^-1 per sccm", "reference state ASSUMED; a 20 C reference scales the value by 273.15/293.15",
      cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "yes", "Unit conversion constant."),
    D(29, "model-derived", "Flow-equivalent singly charged current of 10 sccm (reference 0 C, 101325 Pa)",
      "equivalent_current_A", {"sccm": 10.0}, "A", "reference state ASSUMED (see ECR-D028)",
      cond(gas="N2, 10 sccm"), "partial", "Per molecule; dissociative ionization (N+) is not counted.",
      source_id="S13", locator="derived from abstract flow value", access="abstract_only"),
    D(30, "inferred", "N2 beam current over flow-equivalent current, 10 cm ECR source (ECR-E088 / ECR-D029)",
      "ratio", {"num": ref("ECR-E088"), "den": ref("ECR-D029")}, "dimensionless",
      "proxy only: not a utilization when N2+ and N+ are both extracted; reference state assumed",
      cond(gas="N2, 10 sccm", P=55.0), "partial", "Abstract-only inputs.", source_id="S13",
      locator="derived from abstract", access="abstract_only"),
    D(31, "model-derived", "Reversible Br change of Sm2Co17 from 20 to 100 degC (alpha of ECR-E055)",
      "br_reversible_change_pct", {"alpha_pct_per_C": ref("ECR-E055"), "dT_C": 80.0}, "%",
      "linear coefficient (defined 20-150 degC); irreversible losses excluded", cond(gas=NA, P=NA, p=NA, n=NA, f=NA,
                                                                                     B=NA), "TBD",
      "Shifts the ECR resonance surface; magnitude of the shift depends on the (undefined) field gradient.",
      source_id="S17", locator="derived from Recoma 26 sheet"),
    D(32, "model-derived", "Reversible Br change of NdFeB from 20 to 100 degC (alpha range of ECR-E062)",
      "br_reversible_change_pct", {"alpha_pct_per_C": ref("ECR-E062"), "dT_C": 80.0}, "%",
      "linear coefficient (defined 20-100 degC); irreversible losses excluded",
      cond(gas=NA, P=NA, p=NA, n=NA, f=NA, B=NA), "TBD", "As ECR-D031.", source_id="S18",
      locator="derived from 'Temperature Ratings' table", qualifier="range"),
    D(33, "inferred", "Temperature margin of the mu20 NdFeB magnets (190 - 135 degC)", "difference",
      {"a": ref("ECR-E050"), "b": ref("ECR-E051")}, "degC", "rating minus reported operating temperature",
      cond(gas="Xe", P=100.0, f=[F425, 4.4e9]), "partial", "Xe ion-source thermal environment.",
      source_id="S04", locator="derived from Sec. II.A"),
    D(34, "inferred", "Ratio of NdFeB to Sm2Co17 reversible Br coefficients (ECR-E062 / ECR-E055)", "ratio",
      {"num": ref("ECR-E062"), "den": ref("ECR-E055")}, "dimensionless",
      "nominal coefficients; NdFeB range spans no-suffix to VH/AH grades", cond(gas=NA, P=NA, p=NA, n=NA, f=NA,
                                                                                 B=NA), "TBD",
      "Order: [no-suffix NdFeB, VH/AH NdFeB] relative to Recoma 26.", source_id="S18",
      locator="derived from 'Temperature Ratings' table and Recoma 26 sheet", qualifier="range"),
    D(35, "model-derived", "Cold-flow cavity pressure range, xenon data set, in Pa (ECR-E102)", "mtorr_to_pa",
      {"p_mTorr": ref("ECR-E102")}, "Pa", "unit conversion only (exact); inherits ECR-E102",
      cond(gas="Xe", P=115.0, f=F58), "TBD", "ABEP chamber pressure TBD (ICD).", source_id="S01",
      locator="derived from Sec. IV", qualifier="range"),
    D(36, "model-derived", "Cold-flow cavity pressure range, argon data set, in Pa (ECR-E103)", "mtorr_to_pa",
      {"p_mTorr": ref("ECR-E103")}, "Pa", "unit conversion only (exact); inherits ECR-E103",
      cond(gas="Ar", P=115.0, f=F58), "no", "Argon, outside scope.", source_id="S01",
      locator="derived from Sec. IV", qualifier="range"),
]


# -------------------------------------------------------------------------------------------------- build
def resolve(value, by_id):
    if isinstance(value, dict) and "ref" in value:
        v = by_id[value["ref"]]["value"]
        if "index" in value:
            v = v[value["index"]]
        return v
    return value


def compute(entry, by_id):
    der = entry["derivation"]
    kwargs = {k: resolve(v, by_id) for k, v in der["inputs"].items()}
    return FUNCTIONS[der["function"]](**kwargs)


def build() -> dict:
    by_id = {}
    entries = []
    for e in ENTRIES:
        by_id[e["id"]] = e
        entries.append(e)
    for d in DERIVED:  # in order, so derived entries may reference earlier derived entries
        d = json.loads(json.dumps(d))
        d["value"] = sig4(compute(d, by_id))
        by_id[d["id"]] = d
        entries.append(d)
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), "duplicate entry id"
    return {
        "schema": "ecr_evidence_matrix_v1",
        "title": "ECR ionization / pre-ionization source evidence matrix (N2, O, O2, air, Xe)",
        "audit_date": "2026-09-26",
        "scope": ("Evidence audit only. No model implementation, no architecture conclusion, no ranking of ECR "
                  "against RF or any other ionization technology. ABEP chamber conditions are TBD from the upstream "
                  "ICD (intake -> filter -> compressor -> atmospheric gas chamber -> valve)."),
        "evidence_classes": {
            "measured": "reported measurement (or flight/hardware specification as reported)",
            "digitized": "read from a published figure",
            "inferred": "ratio/estimate derived from reported values (by the source or by this audit)",
            "reconstructed": "measurement passed through the source's own correction/integration model",
            "model-derived": "computed from a physical formula/model (source's or this audit's)",
            "assumed": "assumption, target or claim without direct validating evidence",
        },
        "regime_match_rubric": {
            "yes": "unit identities/conversion constants valid regardless of ABEP design",
            "partial": "at least one of gas, power class, frequency class or device type matches the RFP envelope; "
                       "others differ or are unknown",
            "no": "clear mismatch (gas outside scope, power/frequency far outside, or unrelated quantity)",
            "TBD": "depends on ABEP quantities not yet fixed (ICD chamber density/pressure/composition, ECR "
                   "frequency, magnetic-circuit design)",
        },
        "constants": CONSTANTS,
        "sources": SOURCES,
        "leads_not_admitted": LEADS_NOT_ADMITTED,
        "entries": entries,
    }


def render(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv) -> int:
    text = render(build())
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("ecr_evidence_matrix.json is out of date; run build_ecr_evidence_matrix.py", file=sys.stderr)
            return 1
        print("ecr_evidence_matrix.json is current")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(build()['entries'])} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

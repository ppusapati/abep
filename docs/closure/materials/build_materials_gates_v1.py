#!/usr/bin/env python3
"""P8 materials closure gates v1 (A9.38 Priority 8, lane L-MATERIALS).

Builds `materials_gates_v1.json` and `materials_gates_v1.md` from pinned repository records plus two external manufacturer
datasheets (Special Metals INCONEL alloy 600 / 601 technical bulletins, read 2026-10-08, sha256 recorded, not committed).

What this is: the gate table for the four retained DBF-1 materials (DBF1-MAT-01..04) against atomic oxygen (external ram and
internal feed-borne), plasma exposure, sputtering / erosion, deposition, thermal (continuous-use temperature and cycling)
and the electrical behaviour of the oxide scale; every gate lists its evidence (class, source, domain, uncertainty), the
derived analyses it uses, and one verdict.

What this is not: a P4 gate cell (every p4_anode_materials_v1 gate cell stays INCOMPLETE_EVIDENCE; the P4 vocabulary never
emits PASS); a T_validated,continuous; a life prediction; a CR-04 recession; a change of any DBF-1 value. Elemental sputter
yields are used only as prior bounds / test-matrix selection (A9.12 P4-OQ-04, S5.13), never as an alloy value.

Usage: python3 docs/closure/materials/build_materials_gates_v1.py            (write)
       python3 docs/closure/materials/build_materials_gates_v1.py --check    (rebuild in memory, compare, exit 1 on drift)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT_JSON = HERE / "materials_gates_v1.json"
OUT_MD = HERE / "materials_gates_v1.md"
DATE = "2026-10-08"
BASE_COMMIT = "42bb83a"

# ------------------------------------------------------------------------------------------------ pinned inputs
# Every repository input is sha256-pinned at the base commit; a changed input refuses the build (fail closed).
PINS = {
    "A938": ("docs/decisions/OD_2026_10_08_A9_38_architecture_frozen_design_closure_programme.json",
             "2a66ce271f1b697d0373a66c3da0d459e157437209f2a13e983f7f8f02edc91d"),
    "A931": ("docs/decisions/OD_2026_10_06_A9_31_NEXT_BATCH_OWNER_RULINGS_AND_ARCHITECTURE_PROOF.md",
             "ae2b97e426fe648c3e1829fefcc19095af0d0cdf9b5b58b384c837146ae9bedc"),
    "A912": ("docs/decisions/OD_2026_10_01_A9_12_s5_p3_p4_owner_decisions.json",
             "1485f00b7abe7e621f8dc2d32d8d97704e10e71d53c97b4f617bc022d1f2359d"),
    "DBF1": ("docs/baseline/DBF-1/dbf1_v1.json", "d20f1e8aa95c2d6ee0b307669500d7aaa5ea6abf4d21ddb944b7999525943e4f"),
    "DBF1_LOCK": ("docs/baseline/DBF-1/dbf1_lock_v1.json",
                  "517e0cf693712ec6d355c4b23791b9ae8626577fd338e3030563eb027e86b907"),
    "BOARD": ("docs/closure/closure_board_v1.json", "56bd9f12c4f613a131b4f12300770db509f88e964b7f8e5a6b04de9bb5e5be4b"),
    "P4": ("docs/experiments/hall_icp/p4_anode_materials/p4_anode_materials_v1.json",
           "f0d8bbfa6d3ec59a30910ef2ae1fd61f96fc3f725e6859dc8c6617b1cf6dd96b"),
    "SPUT": ("docs/evidence/sputter_yields_v1/sputter_yields_v1.json",
             "7bcf2b0761f41504601381c8f95db19b9c62f9b891c527edca667f788c0a3dfd"),
    "SPUT_IN": ("docs/evidence/sputter_yields_v1/sputter_yield_inputs_v1.json",
                "c28fef6a4d8dc478ba551e8ca842b69943edcf9ab96151edb2c21a348aa3af8e"),
    "SPUT_PY": ("docs/evidence/sputter_yields_v1/build_sputter_yields_v1.py",
                "c7e75fa8b4a36d2bbb59aaf9629673a5a2f70fc76d1b44f06de09733104d5fe4"),
    "WALL": ("docs/evidence/wall_life/sputter_yield_db_v1.json",
             "315fbd44da2ee16246edb95830be09e0f05b9237cd5ca0a4c86a02a7e25bfffa"),
    "WALL_MD": ("docs/evidence/wall_life/WALL_LIFE_EVIDENCE.md",
                "761e767017586e844fc797a10bcbe62673ff8955e2a1deef31b47a1d5af235a4"),
    "AOL": ("docs/experiments/lifetime_ao/ao_lifetime_register_v5.json",
            "fea8aa05bd561d5ea559b934803d472f1fb1ed1013bfa925a5afb6c68a33e637"),
    "ICPEV": ("docs/evidence/icp_neutralizer/icp_neutralizer_evidence_v1.json",
              "092e4ca8e1827dd2e9558058a204f46510f2633316ce188e7126b697ec6d0b53"),
    "R8": ("docs/procurement/web_track_v1/threads/R8_anode_oxygen.json",
           "31131ed6409a4d0a4c8b5935387d9c399767fb5507d25f21c0afa753f3d9e39c"),
    "R3": ("docs/procurement/web_track_v1/threads/R3_materials.json",
           "29633b98e060c98bfdc3cb7ea474fb3c7f190fd22e2a14bc0cf1e70c893bae7d"),
    "LIMITS": ("schemas/thermal_life/limits_v1.json", "0df363f76dcb6efcef41bc0a07e1775b6255c2c9d84b185228862958ef827dbb"),
    "MISSION": ("docs/rust_migration/new_physics/NP-MISSION-INTEGRATION/verification_report_v1.json",
                "f6cbe1b83adefdd297db5dcdb8ca598ac6c8a08d3a37a41fe96475401fda909b"),
    "SCEN": ("config/mission/mission_scenario_v2.json", "885b1f70a1a44389e088837fd37bb79390b63132e3c81f17923103b2f9b5fc49"),
    "EVID": ("docs/EVIDENCE.md", "a2950352141890c12ad33e66766cd003215c807cb29203d21df090349ab90b61"),
}

# External sources read by this lane (not committed: manufacturer copyright). Values are transcribed with locators.
EXTERNAL = {
    "SMC_IN600": {
        "citation": "Special Metals Corporation, 'INCONEL alloy 600' technical bulletin, Publication SMC-027 (Sept 2008)",
        "url": "https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-600.pdf",
        "accessed_on": DATE, "http_status": 200, "bytes": 161154,
        "sha256": "89a3ba65b26b817dfc8a92875a4848af73ccecc31b98c0ca15140cea7fe8fde8",
        "access": "open manufacturer PDF via the session proxy (no login, no bypass); the same URL is the R8 / P4 source SMC_IN600",
        "evidence_level": 5, "note": "'typical but ... not suitable for specification purposes' (p. 1); annealed material",
    },
    "SMC_IN601": {
        "citation": "Special Metals Corporation, 'INCONEL alloy 601' technical bulletin",
        "url": "https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-601.pdf",
        "accessed_on": DATE, "http_status": 200, "bytes": 287477,
        "sha256": "261c20c247910b729bb4a0030106ed007f055a5bb42e30c4572c767dbab24152",
        "access": "open manufacturer PDF via the session proxy (no login, no bypass); the same URL is the R8 / P4 source SMC_IN601",
        "evidence_level": 5, "note": "data for annealed material (p. 1)",
    },
}

# Physical constants (CODATA 2018 exact / recommended; the same values as abep_types::constants and the AO register).
K_B = 1.380649e-23
E_CHARGE = 1.602176634e-19
AMU = 1.66053906660e-27
N_A = 6.02214076e23
M_E_AMU = 5.48579909065e-4
MU_EARTH = 3.986004418e14
R_EARTH = 6371.0e3
OMEGA_EARTH = 7.2921159e-5   # rad/s (sidereal); equatorial co-rotation speed bound below

CLASSES = ("measured", "literature", "digitized", "inferred", "assumption")
VERDICTS = ("PASS_BY_EVIDENCE", "PASS_BY_ANALYSIS_WITH_ASSUMPTION", "EM_VERIFICATION_REQUIRED", "FAIL", "NOT_APPLICABLE")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pinned() -> dict:
    out = {}
    for key, (rel, sha) in PINS.items():
        p = ROOT / rel
        if not p.is_file():
            raise SystemExit(f"pinned input missing: {rel}")
        got = _sha(p)
        if got != sha:
            raise SystemExit(f"pinned input changed: {rel} sha256 {got} != {sha} (fail closed; re-pin deliberately)")
        out[key] = json.loads(p.read_text()) if rel.endswith(".json") else p.read_text()
    return out


def sig(x: float, n: int = 4):
    if x == 0 or not math.isfinite(x):
        return x
    return float(f"{x:.{n}g}")


def dbf1_item(dbf1: dict, item_id: str) -> dict:
    for it in dbf1["items"]:
        if it["id"] == item_id:
            return it
    raise SystemExit(f"DBF-1 item {item_id} missing")


def load_yt():
    """The single authoritative Python Yamamura-Tawara evaluation of the sputter register (pinned file, pure function)."""
    rel = PINS["SPUT_PY"][0]
    spec = importlib.util.spec_from_file_location("_sputter_register_builder", ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.yamamura_tawara


# ------------------------------------------------------------------------------------------------ derived analyses


def fm_flux_factor(s: float, toward: bool) -> float:
    """Free-molecular one-sided number flux onto a plate, in units of n * c / (2 sqrt(pi)), c = sqrt(2kT/m).

    s = drift speed component along the plate normal / c. toward=True: the drift points into the plate (ram-facing);
    toward=False: the drift points away from it (wake-facing)."""
    if toward:
        return math.exp(-s * s) + math.sqrt(math.pi) * s * (1.0 + math.erf(s))
    return math.exp(-s * s) - math.sqrt(math.pi) * s * math.erfc(s)


def da01_wake_ao(src: dict) -> dict:
    env = {e["field"]: e for e in src["MISSION"]["today_run"]["environment_envelopes_air_primary"]}
    bound = src["MISSION"]["today_run"]["ao_fluence_bound"]
    t_max = env["T_K"]["max"]
    v_min = env["v_orbital_m_s"]["min"]
    v_corot = OMEGA_EARTH * (R_EARTH + 230.0e3)          # equatorial co-rotation at the top of the band (bound)
    v_rel = v_min - v_corot
    m_o = 15.999 * AMU
    c = math.sqrt(2.0 * K_B * t_max / m_o)
    rows = []
    for theta in (0, 15, 30, 45, 60, 75, 90):
        s = v_rel * math.cos(math.radians(theta)) / c
        wake = fm_flux_factor(s, toward=False) * c / (2.0 * math.sqrt(math.pi))
        ratio = wake / v_rel          # relative to the ram-normal flux n * V used by the mission bound (PB-AO)
        rows.append({"theta_deg": theta, "speed_ratio_s": sig(s), "wake_to_ram_flux_ratio": sig(ratio, 3),
                     "fluence_upper_m2": sig(ratio * bound["upper_m2"], 3)})
    return {
        "id": "DA-01",
        "title": "external ram AO reaching aft-facing (wake-side) surfaces",
        "method": "free-molecular one-sided flux of a drifting Maxwellian onto a plate whose normal points into the wake "
                  "(n c/(2 sqrt(pi)) [exp(-s^2) - sqrt(pi) s erfc(s)], s = V cos(theta)/c, c = sqrt(2 k T / m_O)), "
                  "divided by the ram-normal flux n V of the mission AO bound; theta = angle between the surface's "
                  "outward normal and the anti-velocity direction",
        "inputs": {
            "T_max_K": sig(t_max, 6), "T_max_state": env["T_K"]["max_state"],
            "v_orbital_min_m_s": sig(v_min, 6), "v_corotation_bound_m_s": sig(v_corot, 4),
            "v_relative_min_m_s": sig(v_rel, 6),
            "ao_fluence_bound_m2": [sig(bound["lower_m2"], 4), sig(bound["upper_m2"], 4)],
            "ao_fluence_bound_label": bound["label"], "ao_fluence_basis": bound["basis"],
            "source": f"{PINS['MISSION'][0]} today_run (environment_envelopes_air_primary, ao_fluence_bound)",
        },
        "conservatism": "highest exospheric temperature of the 196 states with the lowest orbital speed, reduced by the "
                        "full equatorial co-rotation speed: the smallest speed ratio, hence the largest wake-side flux",
        "rows": rows,
        "class": "inferred",
        "quantity_type": "model-derived",
        "evidence_level": 4,
        "uncertainty": "kinetic-theory result exact for a free-molecular drifting Maxwellian; neglects reflection of ram "
                       "AO from spacecraft surfaces into the aft openings (assumption A-LAY-01) and thermospheric winds "
                       "beyond co-rotation (< 0.1 of V in magnitude; would change s by < 10 %)",
    }


def da02_internal_o(src: dict) -> dict:
    dbf1 = src["DBF1"]
    area_ch = dbf1_item(dbf1, "DBF1-H1-04")["value"]["A_channel_mm2"] * 1e-6
    icp = dbf1_item(dbf1, "DBF1-ICP-02")["value"]
    area_bore = math.pi * icp["r_aperture"] ** 2
    perf = dbf1_item(dbf1, "DBF1-IN-08")["value"]
    x_min = min(v["xO_flow_min"] for v in perf.values())
    x_max = max(v["xO_flow_max"] for v in perf.values())
    t_fire = src["SCEN"]["inputs"]["firing_hours"]["value"] * 3600.0
    p_jet = 1500.0      # RFP bus ceiling as the ideal jet power: the conservation bound of DBF1-BD-01 (A9.38 P1)
    flows = {"12 mN": 0.012 ** 2 / (2.0 * p_jet), "25 mN": 0.025 ** 2 / (2.0 * p_jet)}
    rows = []
    for label, mdot in flows.items():
        for x_o in (x_min, x_max):
            m_mean = (x_o * 15.999 + (1.0 - x_o) * 28.014) * AMU      # balance taken as N2 (dominant non-O species)
            n_dot = x_o * mdot / m_mean
            dose = n_dot * t_fire
            rows.append({"thrust_point": label, "mdot_necessary_kg_s": sig(mdot), "x_O_flow": sig(x_o),
                         "O_atoms_per_s": sig(n_dot), "O_atoms_over_firing_life": sig(dose),
                         "dose_per_anode_plane_m2": sig(dose / area_ch, 3),
                         "dose_per_icp_bore_m2": sig(dose / area_bore, 3)})
    bound = src["MISSION"]["today_run"]["ao_fluence_bound"]
    return {
        "id": "DA-02",
        "title": "internal (feed-borne) atomic-O throughput at the anode plane and through the ICP bore",
        "method": "atomic-O throughput = x_O * mdot / m_mean over the firing-life basis, divided by the channel annulus "
                  "area (anode plane) or the ICP bore cross-section; mdot = the ideal conservation-bound necessary flow "
                  "T^2 / (2 P) at P = 1,500 W (the relation of DBF1-BD-01: 12 mN -> 4.80e-8 kg/s)",
        "inputs": {
            "A_channel_m2": sig(area_ch), "A_icp_bore_m2": sig(area_bore),
            "x_O_flow_range": [sig(x_min), sig(x_max)],
            "x_O_flow_basis": "DBF1-IN-08 xO_flow_min / max over the covered surface scenarios (mole fraction of atomic O "
                              "in the delivered flow, abep-gaspath transient x_s_flow_mole[O])",
            "firing_life_h": src["SCEN"]["inputs"]["firing_hours"]["value"],
            "sources": [PINS["DBF1"][0] + " DBF1-H1-04, DBF1-ICP-02, DBF1-IN-08", PINS["SCEN"][0] + " firing_hours"],
        },
        "rows": rows,
        "comparison_with_external_bound_m2": [sig(bound["lower_m2"], 4), sig(bound["upper_m2"], 4)],
        "reading": "a throughput dose counts each delivered O atom once; wall impingement inside the channel is larger "
                   "(multiple collisions) and the discharge adds O from O2 dissociation. Because the delivered flow at "
                   "a sustained thrust point is at least the conservation-bound flow, the rows are LOWER bounds of the "
                   "atomic-O throughput at 12 / 25 mN for the stated x_O. The internal dose at the anode plane is of "
                   "the same order as, or above, the external ram-face bound: the internal exposure, not the external "
                   "fluence, governs the AO coupon fluence of the anode and collector",
        "class": "inferred",
        "quantity_type": "model-derived",
        "evidence_level": 6,
        "uncertainty": "x_O spans 0.04-0.86 across scenarios / states (factor ~20); delivered flow above the necessary "
                       "flow raises the dose proportionally; O recombination in the compressor is inside x_O as modelled",
    }


def da03_collector_sputter(src: dict, yt) -> dict:
    dbf1 = src["DBF1"]
    icp = dbf1_item(dbf1, "DBF1-ICP-02")["value"]
    coll = dbf1_item(dbf1, "DBF1-ICP-04")
    if "0.10 m axial length" not in coll["value"]:
        raise SystemExit("DBF1-ICP-04 no longer states the 0.10 m collector length")
    l_coll = 0.10
    area = 2.0 * math.pi * icp["r_aperture"] * l_coll
    vd = dbf1_item(dbf1, "DBF1-H1-05")["value"]
    pd = dbf1_item(dbf1, "DBF1-H1-06")["value"]
    i_min, i_max = pd[0] / vd[1], pd[1] / vd[0]
    t_fire = src["SCEN"]["inputs"]["firing_hours"]["value"] * 3600.0
    sp_in = src["SPUT_IN"]
    aw = sp_in["atomic_weights"]["values"]
    zn = sp_in["atomic_numbers"]
    fits = {r["id"]: r for r in sp_in["nifs_caption_fits"]["rows"]}
    p4 = {p["id"]: p for p in src["P4"]["property_records"]}
    rho = {"CAND-02A": p4["PR-011"]["value_si"], "CAND-03A": p4["PR-021"]["value_si"]}
    omega = {k: aw["Ni"] * 1e-3 / (v * N_A) for k, v in rho.items()}

    def y(fit_id: str, energy: float) -> float:
        f = fits[fit_id]
        proj, targ = f["projectile"], f["target"]
        r = yt(energy, zn[proj], aw[proj], zn[targ], aw[targ], f["Us_eV"], f["Q"], f["W_factor_of_Us"] * f["Us_eV"],
               f["s"])
        return r["Y"]

    # reproduction check against the register's own tabulated values (the register is the authority)
    repro = []
    for rec in src["SPUT"]["records"]:
        if rec["id"] in ("YT-FIT-NIFS-F102", "YT-FIT-NIFS-F103"):
            fid = "NIFS-F102" if rec["id"].endswith("F102") else "NIFS-F103"
            for v in rec["values"]:
                got = y(fid, float(v["E_eV"]))
                ok = v["Y_min"] * 0.999 <= got <= v["Y_max"] * 1.001
                repro.append({"record": rec["id"], "E_eV": v["E_eV"], "Y_eval": sig(got), "Y_register": [v["Y_min"],
                              v["Y_max"]], "within": ok})
                if not ok:
                    raise SystemExit(f"Yamamura-Tawara evaluation does not reproduce {rec['id']} at {v['E_eV']} eV")
    eth = {fid: yt(10.0, zn[fits[fid]["projectile"]], aw[fits[fid]["projectile"]], zn["Ni"], aw["Ni"],
                   fits[fid]["Us_eV"], fits[fid]["Q"], fits[fid]["W_factor_of_Us"] * fits[fid]["Us_eV"],
                   fits[fid]["s"])["Eth_eV"] for fid in ("NIFS-F102", "NIFS-F103")}
    energies = (20, 25, 30, 40, 50, 75, 100, 140, 220)
    rows = []
    for e in energies:
        yn, yo = y("NIFS-F102", e), y("NIFS-F103", e)
        row = {"E_eV": e, "Y_Nplus_Ni": sig(yn, 3), "Y_Oplus_Ni": sig(yo, 3)}
        for tag, cur in (("Imin", i_min), ("Imax", i_max)):
            gamma = cur / (E_CHARGE * area)
            row[f"recession_mm_15000h_Nplus_{tag}"] = sig(gamma * yn * omega["CAND-02A"] * t_fire * 1e3, 3)
            row[f"sputtered_mass_kg_15000h_Nplus_{tag}"] = sig(cur / E_CHARGE * yn * aw["Ni"] * 1e-3 / N_A * t_fire, 3)
        rows.append(row)

    def e_star(d_allow_m: float, cur: float) -> float:
        gamma = cur / (E_CHARGE * area)
        y_allow = d_allow_m / (gamma * omega["CAND-02A"] * t_fire)
        lo, hi = eth["NIFS-F102"] * (1 + 1e-9), 1000.0
        if y("NIFS-F102", hi) < y_allow:
            return hi
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if y("NIFS-F102", mid) > y_allow:
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi)

    estar = []
    for d_mm in (0.5, 1.0, 2.0):
        for tag, cur in (("Imin", i_min), ("Imax", i_max)):
            gamma = cur / (E_CHARGE * area)
            estar.append({"allowance_mm": d_mm, "current": tag, "I_A": sig(cur),
                          "Y_allow": sig(d_mm * 1e-3 / (gamma * omega["CAND-02A"] * t_fire), 3),
                          "E_star_eV_Nplus_Ni_prior": sig(e_star(d_mm * 1e-3, cur), 3)})
    # floating-sheath floor of the ion impact energy at an ion-collecting electrode (unmagnetized, Bohm presheath)
    floor = []
    for ion, m_amu in (("N+", 14.007), ("N2+", 28.014), ("O+", 15.999), ("O2+", 31.998), ("Xe+", 131.29)):
        factor = 0.5 * math.log(m_amu / M_E_AMU / (2.0 * math.pi)) + 0.5
        floor.append({"ion": ion, "E_floor_over_Te": sig(factor), "E_floor_eV_Te3": sig(3 * factor, 3),
                      "E_floor_eV_Te5": sig(5 * factor, 3)})
    tk = {x["id"]: x for x in src["ICPEV"]["extraction"]}
    r140 = next(r for r in rows if r["E_eV"] == 140)
    r220 = next(r for r in rows if r["E_eV"] == 220)
    e_lo = min(r["E_star_eV_Nplus_Ni_prior"] for r in estar)
    e_hi = max(r["E_star_eV_Nplus_Ni_prior"] for r in estar)
    return {
        "id": "DA-03",
        "title": "ICP collector sputtering: prior-bound sensitivity and the ion-energy ceiling it implies",
        "use_restriction": "elemental Ni priors (NIFS-DATA-23 caption fits, sputter register YT-FIT-NIFS-F102 / F103) "
                           "used ONLY as prior bounds / test-matrix selection (A9.12 P4-OQ-04, S5.13); never an alloy "
                           "value, never a CR-04 recession, never a life input. N2+ / O2+ have no prior number "
                           "(register NO_MOLECULAR_NUMBERS) and are not evaluated. The fit data start at ~50 eV (N+) / "
                           "~100 eV (O+): values below are formula extrapolation toward threshold",
        "method": "ion current to the collector = Hall discharge current (current continuity of the floating ICP source "
                  "with a separately biased ion collector, DBF1-ICP-01 / -04, Takahashi topology; assumption A-ICP-01); "
                  "flux = I / (e A_coll) with A_coll = 2 pi r_aperture L_coll (axial slit not subtracted: flux is a "
                  "lower bound); recession = flux * Y * Omega * t_fire with Omega = M_Ni / (rho_alloy N_A)",
        "inputs": {
            "A_coll_m2": sig(area), "r_aperture_m": icp["r_aperture"], "L_coll_m": l_coll,
            "I_d_range_A": [sig(i_min), sig(i_max)],
            "I_d_basis": "P_d / V_d over DBF1-H1-06 [650, 1350] W and DBF1-H1-05 [180, 350] V",
            "rho_kg_m3": rho, "Omega_m3": {k: sig(v) for k, v in omega.items()},
            "Eth_eV_prior": {"N+ -> Ni (F102)": sig(eth["NIFS-F102"]), "O+ -> Ni (F103)": sig(eth["NIFS-F103"])},
            "analog_sheath_energies": {
                "TK-70": tk["TK-70"]["value"], "TK-71": tk["TK-71"]["value"],
                "source": "Takahashi et al., J. Electr. Propuls. 3:18 (2024), p. 6 (icp_neutralizer_evidence_v1 TK-70, "
                          "TK-71); Ar, analog only (P4 IT-19: analog values never set the coupon bias)",
            },
            "firing_life_h": src["SCEN"]["inputs"]["firing_hours"]["value"],
        },
        "register_reproduction": repro,
        "rows": rows,
        "ion_energy_ceiling": estar,
        "floating_sheath_floor": {
            "relation": "E_i >= T_e [0.5 ln(m_i / (2 pi m_e)) + 0.5] for an electrode at or below floating potential "
                        "(planar collisionless sheath + Bohm presheath; textbook relation, evidence level 4)",
            "T_e_basis": "T_e of the ICP plasma is NOT_EVALUATED (NP-ICP AIR / Xe cases INCOMPLETE_EVIDENCE); 3 and 5 eV "
                         "are illustration points, assumption class",
            "rows": floor,
        },
        "reading": f"at the analog cathodic-sheath energies (~140 eV ICP ions, ~220 eV Hall ions, TK-70) the N+ -> Ni "
                   f"prior implies {r140['recession_mm_15000h_Nplus_Imin']:.0f}-{r220['recession_mm_15000h_Nplus_Imax']:.0f}"
                   f" mm of collector recession and {r140['sputtered_mass_kg_15000h_Nplus_Imin']:.0f}-"
                   f"{r220['sputtered_mass_kg_15000h_Nplus_Imax']:.0f} kg of sputtered metal over the 15,000 h basis: "
                   "neither retained alloy can be operated at analog sheath energies for the firing life. "
                   f"The allowable mean impact energy for a 0.5-2 mm recession allowance is E* = {e_lo:.0f}-{e_hi:.0f} "
                   f"eV, i.e. {e_lo - eth['NIFS-F102']:.0f}-{e_hi - eth['NIFS-F102']:.0f} eV above the N+ -> Ni prior "
                   f"threshold ({eth['NIFS-F102']:.1f} eV), comparable with the floating-sheath floor (~4.7-5.8 T_e). "
                   "The collector ion energy is therefore an operating-point requirement owned by the ICP closure (P4 / "
                   "BD-06); swapping primary and backup does not change it (same Ni-base prior), and a refractory "
                   "electrode would trade it against the insulating-oxide failure of bare W (TEJEDA2024)",
        "class": "inferred",
        "quantity_type": "model-derived",
        "evidence_level": 6,
        "uncertainty": "elemental-prior yields near threshold (factor >= 2-10 unquantified; CHK-GENERIC-VS-FIT spread "
                       "1.24-52.7); alloy surface state (oxide / nitride) not represented; Cr / Fe constituents have "
                       "lower generic thresholds (N+ -> Cr 15.6 eV, level 6); molecular ions and Xe+ not evaluated",
    }


def da04_scale_asr(src: dict) -> dict:
    dbf1 = src["DBF1"]
    area_ch = dbf1_item(dbf1, "DBF1-H1-04")["value"]["A_channel_mm2"] * 1e-6
    icp = dbf1_item(dbf1, "DBF1-ICP-02")["value"]
    area_coll = 2.0 * math.pi * icp["r_aperture"] * 0.10
    vd = dbf1_item(dbf1, "DBF1-H1-05")["value"]
    pd = dbf1_item(dbf1, "DBF1-H1-06")["value"]
    i_min, i_max = pd[0] / vd[1], pd[1] / vd[0]
    rows = []
    for elec, area in (("anode", area_ch), ("collector", area_coll)):
        for tag, cur in (("Imin", i_min), ("Imax", i_max)):
            j = cur / area
            rows.append({"electrode": elec, "current": tag, "I_A": sig(cur), "A_m2": sig(area), "j_A_m2": sig(j),
                         "ASR_max_ohm_m2_per_V": sig(1.0 / j, 3), "ASR_max_ohm_cm2_per_V": sig(1e4 / j, 3)})
    return {
        "id": "DA-04",
        "title": "electrode current density and the oxide-scale area-specific resistance it tolerates",
        "method": "j = I_d / A (anode: channel annulus as the collecting area, assumption A-AN-01 since H1F-AN-03 anode "
                  "geometry is TBD; collector: C-type electrode area); ASR_max = dV_allow / j, tabulated per volt of "
                  "allowed scale drop (dV_allow is an IT-20 / LOCK-2 slot, not set here)",
        "rows": rows,
        "reading": "the anode at the highest-current corner needs a scale ASR below ~3.5 ohm cm^2 per volt of allowed "
                   "drop; the collector, ~25x lower current density, tolerates ~50 ohm cm^2 per volt. A continuous "
                   "insulating scale fails either electrode (the bare-W WET-HET anode lost conduction in 20-30 min, "
                   "TEJEDA2024); a thin semiconducting chromia-rich scale is the hypothesis the coupon test must confirm",
        "class": "inferred",
        "quantity_type": "model-derived",
        "evidence_level": 6,
        "uncertainty": "collecting area and current distribution of the H-1 anode not frozen; scale resistivity of either "
                       "alloy in the service condition not sourced (WANG1995 not accessed)",
    }


def da05_cycles_cte(src: dict) -> dict:
    t_mis = src["SCEN"]["inputs"]["mission_hours"]["value"] * 3600.0
    orbits = []
    for h_km in (180.0, 230.0):
        a = R_EARTH + h_km * 1e3
        period = 2.0 * math.pi * math.sqrt(a ** 3 / MU_EARTH)
        orbits.append({"alt_km": h_km, "period_min": sig(period / 60.0, 5), "orbits_over_mission": int(t_mis // period)})
    n_max = max(o["orbits_over_mission"] for o in orbits)
    ds_cycles = 1000.0 * 3600.0 / (20.0 * 60.0)
    alpha = {"IN600_20_500C": 14.9, "IN600_20_800C": 16.1, "IN601_27_500C": 15.19, "IN601_27_800C": 16.67}
    bn = {"M26_par_25_400C": 3.0, "M26_perp_25_400C": 0.4}
    r_out = dbf1_item(src["DBF1"], "DBF1-H1-04")["value"]["r_out_mm"]
    d_alpha = [min(alpha.values()) - max(bn.values()), max(alpha.values()) - min(bn.values())]
    return {
        "id": "DA-05",
        "title": "thermal-cycle count bound and Inconel / BN-SiO2 expansion mismatch",
        "cycle_count": {
            "method": "orbital period 2 pi sqrt(a^3 / mu) over the 26,280 h mission basis; at most one full-amplitude "
                      "thermal cycle per orbit (eclipse or firing on / off) is the selected engineering assumption "
                      "A-CYC-01 (the mission schedule is not registered: MISSION_SCHEDULE_NOT_REGISTERED, OQ-MI-01)",
            "rows": orbits,
            "N_cycles_bound": n_max,
            "manufacturer_cyclic_oxidation_coverage": {
                "IN600": "Fig. 11 (p. 11): cyclic oxidation in air at 980 degC, 15 min heat / 5 min cool, time axis to "
                         "1,000 h",
                "IN601": "Fig. 9 (p. 9): cyclic oxidation in air at 1095 degC, 15 min heat / 5 min cool, time axis to "
                         "1,000 h; Figs. 10-11: ten 50 h periods at 1150 / 1205 degC",
                "cycles_at_full_axis": int(ds_cycles),
                "coverage_ratio": sig(ds_cycles / n_max, 3),
                "note": "curve extents not digitized: the axis length bounds the demonstrated cycle count from above",
            },
        },
        "cte_mismatch": {
            "alpha_inconel_um_m_K": alpha,
            "alpha_bn_sio2_um_m_K": bn,
            "sources": "SMC_IN600 Table 3 (p. 2, mean 21 degC -> T); SMC_IN601 Table 3 (p. 2, mean 27 degC -> T); "
                       "R3 PC-BN-MM26 (Precision Ceramics M26, 25-400 degC, distributor typical)",
            "delta_alpha_range_um_m_K": [sig(d_alpha[0]), sig(d_alpha[1])],
            "r_out_mm": r_out,
            "radial_differential_mm_per_100K": [sig(d_alpha[0] * 1e-6 * r_out * 100.0, 3),
                                                 sig(d_alpha[1] * 1e-6 * r_out * 100.0, 3)],
            "reading": "an Inconel anode / distributor inside a BN-SiO2 channel grows ~0.05-0.07 mm radially per 100 K "
                       "more than the ceramic at the outer wall radius; the anode-to-channel interface needs a "
                       "clearance or compliant mount sized from the P7 anode temperature (design rule, TP-07)",
        },
        "class": "inferred",
        "quantity_type": "model-derived",
        "evidence_level": 6,
        "uncertainty": "cycle count is an upper bound under A-CYC-01; CTE values are manufacturer typical",
    }


def da06_temperature_screen(src: dict) -> dict:
    lim = src["LIMITS"]["records"]
    it10 = next(i for i in src["P4"]["items"] if i["id"] == "IT-10")
    margin = dbf1_item(src["DBF1"], "DBF1-TH-03")["value"]["margin_K"]
    rows = [
        {"material": "INCONEL alloy 600", "basis": "highest manufacturer oxidation-data temperature: cyclic oxidation "
         "in air at 980 degC (SMC_IN600 Fig. 11, p. 11); application statement 'cryogenic to above 2000 F (1095 C)' "
         "(p. 1) is context", "T_basis_C": 980.0},
        {"material": "INCONEL alloy 601", "basis": "'resistance to oxidation at temperatures up to 2200 F (1200 C)' "
         "(SMC_IN601 p. 8); oxidation data to 1205 degC (Figs. 10-11, p. 9)", "T_basis_C": 1200.0},
        {"material": "BN-SiO2 (HeBoSint CL-S 200)", "basis": lim["bn_hebosint_cls200"]["locator"] + " (~900 degC "
         "oxidizing)", "T_basis_C": lim["bn_hebosint_cls200"]["values"]["T_use_max_oxidizing_C"]["value"]},
        {"material": "BN-SiO2 (Combat M26 via Precision Ceramics)", "basis": "R3 PC-BN-MM26 'max temperature air "
         "1000+' (distributor sheet; manufacturer sheet blocked)", "T_basis_C": 1000.0},
        {"material": "BN (hBN, HeBoSint PL 100)", "basis": lim["bn_hebosint_pl100"]["locator"] + " (~900 degC oxidizing)",
         "T_basis_C": lim["bn_hebosint_pl100"]["values"]["T_use_max_oxidizing_C"]["value"]},
        {"material": "BN (hBN, Combat AX05 via Precision Ceramics)", "basis": "R3 PC-BN-AX05 'max temperature air 850'",
         "T_basis_C": 850.0},
    ]
    for r in rows:
        r["screening_ceiling_C"] = r["T_basis_C"] - margin
    return {
        "id": "DA-06",
        "title": "necessary temperature screening ceilings (supplier basis minus the 50 K margin rule)",
        "rule": "NECESSARY CEILING ONLY (the H1F-MA-03 / -04 'Curie - 50 K' precedent): a supplier rating is never "
                "T_validated,continuous (P4 staged_validation never_validation: SUPPLIER_CONTINUOUS_RATING, "
                "GENERIC_AIR_USE_TEMPERATURE); exceeding the ceiling places the part outside even the supplier's own "
                "oxidation-data domain",
        "margin_K": margin,
        "rows": rows,
        "anode_context": {"value_C": it10["value"], "status": it10["status"], "basis": it10["basis"],
                          "source": it10["source"]},
        "reading": "the only H-1 anode temperature in the repository (>= 1190 degC, uncoupled, ECHT-analog geometry, "
                   "CONTEXT_NOT_ADMISSIBLE) is above the 930 degC (600) and 1150 degC (601) ceilings; it is not a "
                   "DBF-1 result and triggers nothing by itself, but it makes the P7 anode temperature the deciding "
                   "input of the anode material gate (see the DCR triggers)",
        "class": "literature",
        "quantity_type": "assumed (manufacturer recommendation) minus owner margin",
        "evidence_level": 5,
    }


# ------------------------------------------------------------------------------------------------ evidence register


def evidence_register(src: dict) -> list:
    aol = {m["id"]: m for m in src["AOL"]["mechanisms"]}
    tk = {x["id"]: x for x in src["ICPEV"]["extraction"]}
    lims = {x["id"]: x for x in src["ICPEV"]["stated_limitations"]}
    r8 = src["R8"]["evidence"]

    def r8row(source_id: str, contains: str) -> dict:
        for r in r8:
            if r["source_id"] == source_id and contains in r["result"]:
                return r
        raise SystemExit(f"R8 evidence row {source_id} / {contains!r} missing")

    def aolev(mid: str, source_id: str, contains: str) -> dict:
        for e in aol[mid]["evidence"]:
            if e.get("source_id") == source_id and contains in e["statement"]:
                return e
        raise SystemExit(f"AO register evidence {mid} / {source_id} missing")

    ev = []

    def add(eid, cls, level, qtype, statement, source, locator, domain, uncertainty, role):
        if cls not in CLASSES:
            raise SystemExit(f"{eid}: class {cls} not in {CLASSES}")
        ev.append({"id": eid, "class": cls, "evidence_level": level, "quantity_type": qtype, "statement": statement,
                   "source": source, "locator": locator, "applicability_domain": domain, "uncertainty": uncertainty,
                   "qualification_role": role})

    ext = "external (not committed): "
    add("EV-01", "literature", 5, "measured (typical)",
        "INCONEL 600: Ni 72.0 min, Cr 14.0-17.0, Fe 6.00-10.00 %; density 8.47 Mg/m3; melting 1354-1413 degC; "
        "resistivity 1.03 / 1.12 / 1.13 uOhm m at 20 / 500 / 800 degC; k 14.9-27.5 W/m K; mean CTE 13.3 (100 degC) to "
        "16.1 (800 degC) um/m K; Curie temperature -124 degC, permeability 1.010 at 15.9 kA/m (non-magnetic in service)",
        ext + "SMC_IN600 (sha256 " + EXTERNAL["SMC_IN600"]["sha256"][:12] + "...)", "p. 1 Tables 1-2; p. 2 Table 3",
        "annealed bulk; no plasma, no O, no electrical loading", "typical values, no stated uncertainty",
        "design property (bulk); not qualification evidence")
    add("EV-02", "literature", 5, "measured (typical, figure not digitized)",
        "INCONEL 600 resists oxidation and scaling in cyclic air exposure at 980 degC (15 min / 5 min cycles, Fig. 11, "
        "vs Types 304 / 309); 'standard material for nitriding containers because of its resistance to nitrogen at "
        "high temperatures'; creep: 0.01 %/1000 h at 1.1 MPa (1093 degC) and 2.3 MPa (982 degC); no embrittlement "
        "after long high-temperature exposure",
        ext + "SMC_IN600", "p. 11 'High-Temperature Applications', Fig. 11; p. 8 Table 20, text",
        "furnace air / nitriding atmospheres; thermal species only; unbiased", "figure not digitized; typical",
        "supplier screening evidence (never T_validated: P4 never_validation)")
    add("EV-03", "literature", 5, "measured (typical)",
        "INCONEL 601: Ni 58.0-63.0, Cr 21.0-25.0, Al 1.0-1.7 %, Fe remainder; density 8.11 Mg/m3; melting 1360-1411 "
        "degC; resistivity 1.180-1.262 uOhm m (20-1000 degC); k 11.2-27.8 W/m K (calculated from resistivity); mean CTE "
        "13.75-17.82 um/m K (100-1000 degC); Curie < -196 degC",
        ext + "SMC_IN601 (sha256 " + EXTERNAL["SMC_IN601"]["sha256"][:12] + "...)", "p. 1 Tables 1-2; p. 2 Table 3",
        "annealed bulk; no plasma", "typical values", "design property (bulk); not qualification evidence")
    add("EV-04", "literature", 5, "measured (typical, figures not digitized)",
        "INCONEL 601: 'resistance to oxidation at temperatures up to 2200 F (1200 C)', 'unique resistance to oxide "
        "spalling under cyclic thermal conditions'; cyclic oxidation 1095 degC (15 / 5 min, Fig. 9), 50 h cycles at "
        "1150 / 1205 degC (Figs. 10-11); 'a slight amount of internal oxidation occurs and provides a higher chromium "
        "content in the surface oxide'",
        ext + "SMC_IN601", "p. 8 'Corrosion Resistance'; p. 9 'Oxidation', Figs. 9-13",
        "furnace air; thermal species only; unbiased",
        "figures not digitized; the scale composition statement is qualitative",
        "supplier screening evidence; bears on the alumina-scale hypothesis (scale reported chromium-rich)")
    m01 = aolev("AOL-M01", "ANDREUSSI2022", "314")
    add("EV-05", "literature", m01["evidence_level"], m01["evidence_class"], m01["statement"],
        "ANDREUSSI2022 (via " + PINS["AOL"][0] + " AOL-M01)", m01["locator"], m01["applicability"],
        "second-hand review of CIFALI2012 (primary not accessed); anode material not stated",
        "analog failure mode (oxidation -> resistance -> flame-out); not transferred as a verdict")
    c11 = aolev("AOL-M01", "CIFALI2011", "rusty")
    add("EV-06", "literature", c11["evidence_level"], c11["evidence_class"], c11["statement"],
        "CIFALI2011 (via " + PINS["AOL"][0] + " AOL-M01)", c11["locator"], c11["applicability"], "visual only, 10 h",
        "analog failure mode")
    t24 = r8row("TEJEDA2024", "tungsten")
    add("EV-07", "literature", 3, "measured (qualitative)", t24["result"],
        "TEJEDA2024 (via " + PINS["R8"][0] + ")", t24["locator"], t24["applicability"][:160], "qualitative",
        "negative control: an insulating anode scale ends conduction in minutes")
    t24b = r8row("TEJEDA2024", "prolonged resistance")
    add("EV-08", "literature", 3, "measured (qualitative)", t24b["result"],
        "TEJEDA2024 (via " + PINS["R8"][0] + ")", t24b["locator"], "stainless anode, O2 Hall thruster, lab hours",
        "qualitative; grade from a snippet (verify)", "analog: chromia-forming steel keeps conduction longer")
    g93 = r8row("GABRIEL1993", "Inconel x750")
    add("EV-09", "literature", 4, "inferred (authors' suggestion)", g93["result"],
        "GABRIEL1993 (via " + PINS["R8"][0] + ")", g93["locator"], "O2 ion sources / MPD (another device class)",
        "suggestion, no test", "supports the chromia-forming Ni-alloy family as an O2 anode candidate")
    b04 = r8row("BANKS2004", "non-volatile")
    add("EV-10", "literature", 2, "measured (flight compilation) + authors' statement",
        "'erosion yield is not a meaningful number for ... most metals ... where the majority of the oxidation products "
        "are non-volatile' (ram AO, LEO flight data compilation)",
        "BANKS2004 NASA/TM-2004-213400 (via " + PINS["R8"][0] + ")", b04["locator"],
        "ram AO ~4.5 eV, LEO exterior, ambient temperature", "qualitative statement",
        "basis for treating Ni-Cr(-Al) alloys as non-receding under AO (oxide growth, not mass loss)")
    add("EV-11", "literature", 3, "measured (qualitative) + inferred (authors' estimates)",
        tk["TK-71"]["value"] + "; ion energy at the electrode " + tk["TK-70"]["value"] + "; " + lims["LIM-02"]["text"]
        + "; " + lims["LIM-03"]["text"],
        "Takahashi et al. 2024 (via " + PINS["ICPEV"][0] + " TK-70, TK-71, LIM-02, LIM-03)", "p. 6, Fig. 5; p. 8; p. 9",
        "Ar, stainless electrode, 200 W RF, coupled HET, short tests", "qualitative; analog only (P4 IT-19)",
        "analog mechanism evidence: collector sputtering and metallic films on the glass tube and HET insulators")
    add("EV-12", "digitized", 3, "digitized",
        "ion-collector potential V_K = -2.7 / -10.6 / -21.8 / -24.6 / -42.9 / -69.7 / -93.8 V at V_D = 140-260 V "
        "(Takahashi Fig. 4a): the cathodic sheath grows with discharge demand",
        "Takahashi et al. 2024 (via " + PINS["ICPEV"][0] + " digitized_fig4)", "Fig. 4a (PDF p. 7)",
        "Ar, analog", "+/- 0.8 V reading", "analog trend only")
    add("EV-13", "literature", 5, "model-derived (elemental fits to measured data)",
        "NIFS-DATA-23 caption fits N+ -> Ni (Eth 21.89 eV; data from ~50 eV) and O+ -> Ni (Eth 38.73 eV; data from "
        "~100 eV); generic Table-1 N+ / O+ -> Cr (Eth 15.55 / 15.69 eV) and -> Al (14.92 / 15.88 eV), level 6",
        PINS["SPUT"][0] + " records YT-FIT-NIFS-F102 / F103, YT-GEN-N-Cr, YT-GEN-O-Cr, YT-GEN-N-Al, YT-GEN-O-Al",
        "NIFS-DATA-23 Figs. 102-103 (pp. 42, 44); Table 1 (p. 14)", "elemental targets, normal incidence, low fluence",
        "large near threshold; no alloy or molecular-ion value exists", "prior bound / test-matrix selection only")
    add("EV-14", "literature", 3, "measured",
        "Xe+ on BN grades measured (Rubin 2009 HBC / HBR / HP, Tartz 2009, Britton 2002); grade + laboratory spread up "
        "to ~12x; threshold not identified (18-57 eV); no N+ / N2+ / O+ / O2+ yield on BN, BN-SiO2 or SiC located",
        PINS["WALL"][0] + " entries Y-XE-BN-*; " + PINS["WALL_MD"][0] + " sections 2-6", "sections 2-5",
        "Xe+ 60-1000 eV; room to ~520 degC", "~30 % per source; ~12x between labs",
        "Xe+ prior for XE_CONTINGENCY only; N / O lookups are OUT_OF_DOMAIN -> NOT_DEMONSTRATED")
    m02 = aolev("AOL-M02", "ANDREUSSI2022", "7000")
    add("EV-15", "literature", m02["evidence_level"], "inferred (authors' wear estimate)", m02["statement"],
        "ANDREUSSI2022 (via " + PINS["AOL"][0] + " AOL-M02)", m02["locator"], m02["applicability"],
        "method not given in the review; second-hand", "analog life indication below the 15,000 h firing basis")
    m03 = aolev("AOL-M03", "CIFALI2011", "ceramics")
    add("EV-16", "literature", m03["evidence_level"], "measured (qualitative)", m03["statement"],
        "CIFALI2011 (via " + PINS["AOL"][0] + " AOL-M03)", m03["locator"], m03["applicability"], "visual only",
        "analog: O-bearing operation alters the ceramic surface")
    add("EV-17", "literature", 4, "model-derived (TRIM.SP proxies)",
        "O on elemental B 0.0375 atoms/ion vs O on B2O3 0.752 atoms/ion at 150 eV: ~20x proxy spread for an oxidizing "
        "BN wall; reactive chemistry outside every yield entry",
        PINS["WALL_MD"][0] + " section 5 (Eckstein IPP 9/132 pp. 40, 278)", "section 5",
        "proxy targets, low fluence, flat surfaces", "~20x between proxies",
        "bounds nothing; motivates H1 / H4 tests")
    lim = src["LIMITS"]["records"]
    add("EV-18", "literature", 5, "assumed (manufacturer recommendation)",
        "BN wall grades, oxidizing use limits: HeBoSint hBN PL grades ~900 degC, BN-SiO2 CL-S 200 ~900 degC (inert "
        f"{lim['bn_hebosint_cls200']['values']['T_use_max_inert_vacuum_C']['value']:.0f} degC); Combat M26 (60 % hBN / "
        "40 % SiO2) 'max temperature air 1000+', AX05 hBN 850 degC (distributor sheets); M26 CTE 3 / 0.4 um/m K, "
        "k 11 / 29 W/m K (column conflict with M flagged in R3)",
        PINS["LIMITS"][0] + " bn_hebosint_*; " + PINS["R3"][0] + " PC-BN-MM26 / PC-BN-AX05", "datasheet rows",
        "gas atmosphere / vacuum; plasma and AO not covered", "approximate ('~'), typical",
        "necessary screening ceilings only")
    env = {e["field"]: e for e in src["MISSION"]["today_run"]["environment_envelopes_air_primary"]}
    bound = src["MISSION"]["today_run"]["ao_fluence_bound"]
    add("EV-19", "inferred", 6, "model-derived",
        f"ram-face AO fluence bound [{bound['lower_m2']:.4g}, {bound['upper_m2']:.4g}] m^-2 over the 26,280 h horizon "
        f"(PARAMETRIC_BOUND; fluence NOT_EVALUATED without a schedule); T 469.6-{env['T_K']['max']:.1f} K; "
        f"v_orb {env['v_orbital_m_s']['min']:.1f}-{env['v_orbital_m_s']['max']:.1f} m/s",
        PINS["MISSION"][0] + " (SC-WP-09 mission integration record)", "today_run.ao_fluence_bound; "
        "environment_envelopes_air_primary", "196 frozen states, ram-normal surfaces",
        "bound, not an evidence-qualified fluence", "environment input")
    add("EV-20", "assumption", 7, "assumed",
        "anode temperature: the only repository value is an uncoupled H2 A9 sensitivity on the ECHT-analog geometry "
        "(>= 1190 degC), CONTEXT_NOT_ADMISSIBLE; no DBF-1 thermal case exists (P7 / L-THERMAL open)",
        PINS["P4"][0] + " items IT-10; docs/hardware/h2_a9_revisions/h2_a9_revisions_v1.json key_findings K6",
        "IT-10", "uncoupled, other geometry", "not admissible", "context only; never T_operating")
    return ev


# ------------------------------------------------------------------------------------------------ assumptions


ASSUMPTIONS = [
    {"id": "A-ATT-01", "class": "assumption", "evidence_level": 7,
     "statement": "the H-1 / ICP exit openings face the wake: the outward normal of every retained-material surface "
                  "exposed to the free stream is within 60 deg of the anti-velocity direction (drag-compensating "
                  "thrust is along-track by mission function)",
     "verification": "spacecraft attitude / layout ICD (P9 / host ICD); analysis at PDR"},
    {"id": "A-LAY-01", "class": "assumption", "evidence_level": 7,
     "statement": "no ram-facing spacecraft surface reflects or re-emits ram AO into the H-1 channel or the ICP bore at "
                  "a rate comparable with the feed-borne dose (DA-02)",
     "verification": "host layout ICD; free-molecular view-factor analysis at PDR (AO register flag "
                     "RAM_NORMAL_UPPER_BOUND)"},
    {"id": "A-AN-01", "class": "assumption", "evidence_level": 7,
     "statement": "the anode collecting area is the channel annulus (H1F-AN-03 anode geometry TBD); ion impact energy "
                  "at the anode stays below the lowest constituent sputter threshold prior (~14.9 eV, N+ -> Al "
                  "generic, IN601; ~15.5 eV, N+ -> Cr generic, IN600) because the anode is the most positive electrode and ions reach it only from the "
                  "near-anode potential excess of a few T_e",
     "verification": "anode metrology on the replaceable serialized EM anode (AOL-RC-01, AOL-PM-03 / -04); near-anode "
                     "potential from the converged RP-1 Hall solution (P2) when admitted"},
    {"id": "A-ICP-01", "class": "assumption", "evidence_level": 6,
     "statement": "the ion current collected by the ICP collector equals the Hall discharge current (current "
                  "continuity of the floating ICP body with a separately biased, metered ion collector: DBF1-ICP-01 / "
                  "-04; Takahashi topology)",
     "verification": "collector current metering on the EM ICP (DBF1-ICP-04 'separately biased and metered')"},
    {"id": "A-CYC-01", "class": "assumption", "evidence_level": 7,
     "statement": "at most one full-amplitude thermal cycle per orbit over the 26,280 h mission (eclipse and / or "
                  "firing on-off); the mission schedule is not registered (OQ-MI-01)",
     "verification": "mission operations concept / schedule registration (SCH-05)"},
]


# ------------------------------------------------------------------------------------------------ gates


def gate(gid, material, application, dbf1_items, name, verdict, evidence, analyses, assumptions, basis, test=None,
         dcr_trigger=None, input_dependency=None):
    if verdict not in VERDICTS:
        raise SystemExit(f"{gid}: verdict {verdict} not in {VERDICTS}")
    if verdict == "PASS_BY_ANALYSIS_WITH_ASSUMPTION" and not assumptions:
        raise SystemExit(f"{gid}: an analysis pass must state its assumptions")
    if verdict == "EM_VERIFICATION_REQUIRED" and not test:
        raise SystemExit(f"{gid}: EM verification must name the specific test")
    return {"id": gid, "material": material, "application": application, "dbf1_items": dbf1_items, "gate": name,
            "verdict": verdict, "evidence": evidence, "analyses": analyses, "assumptions": assumptions,
            "basis": basis, "em_test": test, "dcr_trigger": dcr_trigger, "input_dependency": input_dependency}


def build_gates() -> list:
    g = []
    metals = [("IN600", "INCONEL alloy 600 (CAND-02A)", "primary"), ("IN601", "INCONEL alloy 601 (CAND-03A)", "backup")]
    for key, mat, role in metals:
        an_item = "DBF1-MAT-01" if key == "IN600" else "DBF1-MAT-02"
        ceiling = "930 degC" if key == "IN600" else "1150 degC"
        prop_ev = ["EV-01", "EV-02"] if key == "IN600" else ["EV-03", "EV-04"]
        for app, items, label in (("APP-ANODE", [an_item], "anode / gas distributor"),
                                  ("APP-COLLECTOR", ["DBF1-MAT-03", "DBF1-ICP-04"], "ICP ion collector")):
            p = f"{key}-{'AN' if app == 'APP-ANODE' else 'CO'}"
            g.append(gate(
                f"{p}-AO-EXT", mat, f"{app} ({role})", items, "atomic oxygen, external ram (SC-WP-09 bound)",
                "PASS_BY_ANALYSIS_WITH_ASSUMPTION", ["EV-10", "EV-19"], ["DA-01", "DA-02"], ["A-ATT-01", "A-LAY-01"],
                f"the {label} sits inside an aft-facing opening; for any surface normal within 60 deg of anti-velocity "
                "the wake-side free-molecular flux is <= 3e-6 of the ram flux (DA-01), i.e. <= ~4e22 m^-2 against the "
                "[2.4e26, 1.5e28] m^-2 ram bound and against an internal feed-borne dose >= 8e26 m^-2 (DA-02); a "
                "Ni-Cr(-Al) alloy forms non-volatile oxides, for which an AO erosion yield is 'not a meaningful number' "
                "(BANKS2004): external ram AO adds no recession mechanism beyond the internal O exposure gate"))
            g.append(gate(
                f"{p}-AO-INT", mat, f"{app} ({role})", items, "atomic oxygen, internal (feed-borne / discharge O)",
                "EM_VERIFICATION_REQUIRED", ["EV-05", "EV-06", "EV-10"] + prop_ev, ["DA-02"], [],
                "no atomic-O exposure of either alloy exists in any accessed source; the internal throughput dose at "
                "the 12 mN necessary flow is 8e26-3e28 m^-2 at the anode plane (25 mN: up to ~1.3e29), the same order "
                "as or above the external bound; failure mode in every O-plasma report is loss of conduction, not "
                "mass loss",
                test="TP-03 (Q2): dedicated atomic-O source with Kapton-H fluence witness (DEGROH2006 method), coupons "
                     "at the P7 operating temperature, fluence >= the DA-02 dose of the electrode (anode plane >= 3e28 "
                     "m^-2 at 12 mN, scaled to the delivered flow), 4-wire resistance before / during / after and "
                     "recession; N2 + O2 surrogate results labelled NO_ATOMIC_O, never AO-life proof (row 132)",
                input_dependency="P7 electrode temperature; P1 delivered flow (DCR-001)"))
            if app == "APP-ANODE":
                g.append(gate(
                    f"{p}-PLASMA", mat, f"{app} ({role})", items,
                    "plasma exposure (O / O2 / N2 discharge at the anode, electron-collecting)",
                    "EM_VERIFICATION_REQUIRED", ["EV-05", "EV-06", "EV-07", "EV-08", "EV-09"] + prop_ev, [], [],
                    "the analog SPT anode on N2 / O2 (+10 % Xe) reached first oxidation flame-out after ~314 h "
                    "(material not stated); stainless keeps conduction longer than W; the chromia-forming Ni-alloy "
                    "family is a literature suggestion with no plasma test; IN600 resists nitrogen at temperature "
                    "(nitriding containers) - no evidence transfers to the 15,000 h firing basis",
                    test="Q1 TP-01 / TP-02: electron-collecting biased AND floating coupons (row 106) in N2, then "
                         "N2 + O2 up to the delivered O fraction, plus atomic O, at P7 temperature steps, in-situ "
                         "4-wire resistance and thermocouple; then Q4 (stage 2): replaceable serialized EM anode "
                         "(AOL-RC-01) with in-situ resistance lead (AOL-RC-02), flame-out log (AOL-CX-06) and "
                         "post-test SEM / XPS (AOL-PM-04); endurance segment and acceptance pre-registered (AOL-LF-02, "
                         "LOCK-2)",
                    input_dependency="LOCK-2 acceptance thresholds (A9.12 P4-OQ-03)"))
                g.append(gate(
                    f"{p}-SPUTTER", mat, f"{app} ({role})", items, "sputtering / erosion (anode)",
                    "PASS_BY_ANALYSIS_WITH_ASSUMPTION", ["EV-05", "EV-13"], [], ["A-AN-01"],
                    "the anode collects electrons; ions reach it only with the near-anode potential excess of a few "
                    "T_e, below the N+ -> Ni prior threshold (21.9 eV) and the lowest constituent priors (N+ -> Cr "
                    "15.5 eV; N+ -> Al 14.9 eV for IN601; generic, level 6); no accessed source identifies ion bombardment as an anode driver and the one "
                    "analog anode failure was oxidation (AOL-M01). Confirmation by EM anode metrology "
                    "(AOL-RC-01 / AOL-PM-03) is part of the plasma-exposure test"))
                g.append(gate(
                    f"{p}-DEPOSITION", mat, f"{app} ({role})", items,
                    "deposition (wall erosion products B / Si / O compounds on the anode)", "EM_VERIFICATION_REQUIRED",
                    ["EV-16", "EV-17"], [], [],
                    "insulating wall erosion products (B2O3 / SiO2 / BN) redeposited on the anode would act like an "
                    "insulating scale (DA-04 demand); no accessed source quantifies redeposition on a Hall anode "
                    "(hypothesis, verify)",
                    test="AOL-WC-02 anode-material witness at the distributor (or the replaceable anode AOL-RC-01) with "
                         "SEM / EDS / XPS for B, Si, O; resistance trend on AOL-RC-02"))
            else:
                g.append(gate(
                    f"{p}-PLASMA", mat, f"{app} ({role})", items,
                    "plasma exposure (ICP plasma of reused Hall exhaust, ion-collecting, RF field)",
                    "EM_VERIFICATION_REQUIRED", ["EV-11", "EV-09"] + prop_ev, [], [],
                    "no plasma exposure of either alloy exists; the analog electrode was stainless steel on Ar; the "
                    "electrode absorbed most of the RF power by eddy currents (LIM-02) - both alloys are non-magnetic "
                    "in service (Curie -124 / < -196 degC), so no ferromagnetic loss is added",
                    test="TP-01 / TP-02 per A9.12 P4-OQ-05: NEGATIVE-biased ion-collecting coupons AND floating "
                         "matched controls, bias magnitude from the measured P1 collector envelope (never the analog), "
                         "Ar engineering then N2 then O2-bearing; Q4 in-ICP replaceable collector with current metering",
                    input_dependency="P1 collector operating envelope (IT-19); P4 ICP closure (BD-06)"))
                g.append(gate(
                    f"{p}-SPUTTER", mat, f"{app} ({role})", items, "sputtering / erosion (collector, cathodic sheath)",
                    "EM_VERIFICATION_REQUIRED", ["EV-11", "EV-12", "EV-13"] + prop_ev, ["DA-03"], ["A-ICP-01"],
                    "DESIGN-DRIVING: the collector collects the full discharge current as ions (1.9-7.5 A over "
                    "0.0377 m^2). At the analog sheath energies (~140 / 220 eV) the N+ -> Ni prior gives 33-210 mm "
                    "of recession over 15,000 h - untenable for either retained alloy. A 0.5-2 mm allowance requires a mean "
                    "N+ impact energy below E* = 26-38 eV, i.e. 4-16 eV above the 21.9 eV prior threshold (DA-03), "
                    "close to the floating-sheath floor (~4.7-5.8 T_e, 14-29 eV at T_e 3-5 eV). This is an operating-point requirement on the ICP (P4 / "
                    "BD-06): collector sheath energy minimized (Takahashi: 'has to be minimized'); swapping the "
                    "retained alloys does not remove it",
                    test="TP-04 (A9.12 P4-OQ-04 BOTH): ion-beam yields of the procured IN600 / IN601 lot for N+, "
                         "N2+, O+, O2+ (and Xe+ for XE_CONTINGENCY) at 15-60 eV in 5 eV steps plus 100 / 140 / 220 eV "
                         "(energies selected from DA-03; test-matrix use of the priors), normal and 45 / 70 deg; then "
                         "the EM ICP with RFEA / sheath-potential measurement at the collector and a serialized "
                         "replaceable collector with profilometry (AOL-RC-03 method)",
                    dcr_trigger="if the P4 ICP closure finds that I_e >= I_d (with the neutralization margin) needs a "
                                "mean collector ion energy above E*(allowance) of the measured yield, raise a DCR "
                                "against DBF1-ICP-04 (collector area / topology / replaceability), not against the "
                                "material",
                    input_dependency="P4 ICP closure: collector bias / sheath energy and I_e,cap (BD-06)"))
                g.append(gate(
                    f"{p}-DEPOSITION", mat, f"{app} ({role})", items,
                    "deposition (collector sputter products on the ICP glass bore and H-1 exit insulators)",
                    "EM_VERIFICATION_REQUIRED", ["EV-11"], ["DA-03"], ["A-ICP-01"],
                    "the analog produced metallic films on the glass tube at the electrode slit and on the HET front "
                    "insulators (TK-71). Ni / Cr / Fe films on the borosilicate bore (DBF1-ICP-07) shield the RF "
                    "field and add eddy loss; films on the H-1 exit insulators and the collector isolation (350 V "
                    "class, DBF1-ICP-06) create leakage paths. Deposition rate scales with the collector sputter "
                    "rate (DA-03)",
                    test="witness coupons on the ICP bore at the slit and on the H-1 exit insulators (TK-71 h4 "
                         "measurement, AOL-WC-01 holder) with film thickness / sheet resistance after each block; "
                         "RF coupling (R_ant method) and isolation resistance trend (AOL-PM-06); line-of-sight shield "
                         "between collector and slit evaluated on the EM",
                    input_dependency="P4 collector sheath energy"))
            g.append(gate(
                f"{p}-THERMAL", mat, f"{app} ({role})", items,
                "thermal: continuous-use temperature and thermal cycling", "EM_VERIFICATION_REQUIRED",
                prop_ev + ["EV-18", "EV-20"], ["DA-05", "DA-06"], ["A-CYC-01"],
                f"no DBF-1 thermal case exists (P7 open); the supplier oxidation-data domain gives a necessary "
                f"screening ceiling of {ceiling} after the 50 K margin (DA-06). Cycles: <= 17,928 orbits over the "
                "mission (A-CYC-01) against <= 3,000 cycles covered by the supplier cyclic tests (coverage <= 0.17); "
                "Inconel / BN-SiO2 radial mismatch ~0.05-0.07 mm per 100 K at the outer wall radius (DA-05)",
                test="TP-07 (Q3): joint / mount thermal cycling to >= 1.5 x the registered cycle count between the "
                     "P7 cold and hot temperatures with the anode-channel (or collector-body) interface; TP-06 k(T) "
                     "and joint conductance on the procured lot; stage-2 T_validated,continuous from the Q4 "
                     "integrated replaceable part (A9.12 P4-OQ-01)",
                dcr_trigger=(f"if the P7 hot-case {label} temperature exceeds the {ceiling} screening ceiling, IN600 is "
                             "outside its supplier oxidation-data domain and the backup IN601 (ceiling 1150 degC) "
                             f"governs: DCR swapping primary and backup in {items[0]}"
                             + (" (with DBF1-MAT-02)" if items[0] == "DBF1-MAT-01" else "")
                             + "; above 1150 degC both retained alloys are outside: DCR on the "
                             + ("anode heat path (A9H-ANODE-02) " if app == "APP-ANODE" else "collector thermal path ")
                             + "or the material (no refractory metal selected for melting point alone, A9.2)")
                if key == "IN600" else
                (f"if the P7 hot-case {label} temperature exceeds the {ceiling} screening ceiling, both retained "
                 f"alloys are outside their supplier oxidation-data domains: DCR on {items[0]} and the "
                 + ("anode heat path (A9H-ANODE-02)" if app == "APP-ANODE" else "collector thermal path")),
                input_dependency="P7 hot / cold case temperature of " + ("H1_ANODE" if app == "APP-ANODE" else
                                                                        "N_COLLECTOR")))
            g.append(gate(
                f"{p}-OXIDE-ELEC", mat, f"{app} ({role})", items, "electrical behaviour of the oxide scale",
                "EM_VERIFICATION_REQUIRED", ["EV-07", "EV-08", "EV-04"] + (["EV-02"] if key == "IN600" else []),
                ["DA-04"], ["A-AN-01"] if app == "APP-ANODE" else ["A-ICP-01"],
                ("IN600 forms a chromia-rich scale (semiconducting per R8 'verify'; WANG1995 not accessed)"
                 if key == "IN600" else
                 "IN601 is the hypothesis-control for an insulating alumina scale; its supplier reports the surface "
                 "oxide chromium-rich with slight internal oxidation (EV-04), so the insulating-scale outcome is open")
                + f"; the {label} tolerates a scale ASR of ~"
                + ("3.5-14 ohm cm^2 per volt of allowed drop" if app == "APP-ANODE" else
                   "50-200 ohm cm^2 per volt of allowed drop")
                + " (DA-04); no scale resistance in the service condition is sourced",
                test="TP-02: 4-wire area-specific resistance of the scale under the electrode's bias polarity "
                     "(anode electron-collecting; collector negative ion-collecting with floating control) versus "
                     "exposure time and temperature, oxide thickness / phase by SEM cross-section and XPS; "
                     "in-situ AOL-RC-02 resistance on the EM; acceptance (dV_allow, IT-20) frozen at LOCK-2",
                input_dependency="IT-20 allowable electrode-path resistance (LOCK-1); LOCK-2 thresholds"))
    # channel ceramics
    for key, mat, role, grade_note in (
            ("BNSIO2", "BN-SiO2 (borosil class)", "primary", "grade within the BN-SiO2 class not specified"),
            ("BN", "BN (hBN)", "backup", "grade not specified (binder-free hBN or borate-bonded)")):
        p = f"{key}-WALL"
        ceil = "850-950 degC (CL-S 200 / M26)" if key == "BNSIO2" else "800-850 degC (AX05 / PL grades)"
        g.append(gate(
            f"{p}-AO-EXT", mat, f"channel wall ({role})", ["DBF1-MAT-04"], "atomic oxygen, external ram (SC-WP-09 bound)",
            "PASS_BY_ANALYSIS_WITH_ASSUMPTION", ["EV-19"], ["DA-01", "DA-02"], ["A-ATT-01", "A-LAY-01"],
            "the channel walls and exit chamfers face the wake; the wake-side ram AO is <= 3e-6 of the ram flux for "
            "normals within 60 deg of anti-velocity (DA-01) and negligible against the internal O dose (DA-02); the "
            "ceramic's O compatibility is carried entirely by the internal plasma / chemical-erosion gate"))
        g.append(gate(
            f"{p}-AO-INT", mat, f"channel wall ({role})", ["DBF1-MAT-04"],
            "atomic oxygen, internal (thermal O + O ions; B -> B2O3 chemistry)", "EM_VERIFICATION_REQUIRED",
            ["EV-16", "EV-17", "EV-18"], ["DA-02"], [],
            "O oxidizes B to B2O3 (and Si, already SiO2 in BN-SiO2); proxy yields differ ~20x (O on B vs B2O3); "
            "only a qualitative 10 h observation exists",
            test="H4 / AOL-EX-02: combined ion + atomic-O + N2 coupon exposure of the wall grade at 30-600 degC "
                 "(extended to the P7 wall temperature) with XPS / SEM for B2O3 formation and recession; dedicated AO "
                 "source with fluence witness (row 132)",
            input_dependency="P7 wall temperature; wall grade specification"))
        g.append(gate(
            f"{p}-PLASMA", mat, f"channel wall ({role})", ["DBF1-MAT-04"],
            "plasma exposure (N / O ion bombardment, SEE change)", "EM_VERIFICATION_REQUIRED",
            ["EV-14", "EV-16", "EV-17"], [], [],
            "oxidation / nitridation changes the wall surface state and SEE (sheath potential, hence impact "
            "energy); no N / O data on BN or BN-SiO2",
            test="H9 / AOL-PM-07: SEE yield of wall coupons before and after N / O exposure; H5 long-fluence coupons "
                 "(yield vs fluence, roughness)",
            input_dependency="wall grade specification (lot shared with the coupons, HW-H1-14)"))
        g.append(gate(
            f"{p}-SPUTTER", mat, f"channel wall ({role})", ["DBF1-MAT-04"], "sputtering / erosion (channel wall)",
            "EM_VERIFICATION_REQUIRED", ["EV-14", "EV-15", "EV-17"], [], [],
            "no N+ / N2+ / O+ / O2+ yield on BN or BN-SiO2 exists (every N / O lookup OUT_OF_DOMAIN -> "
            "NOT_DEMONSTRATED); the only air-mode analog life indication (PPS1350, N2 / O2 + 10 % Xe, 'compatible with "
            "a 7000-9500 hrs lifetime', second-hand) is BELOW the 15,000 h firing basis; Xe+ yields exist for BN "
            "grades with a ~12x lab / grade spread (XE_CONTINGENCY); wall flux comes only from an admitted Hall "
            "member (credible set empty; P2 open). The wall erosion life is the principal open life item of the "
            "channel",
            test="H1 ion-beam coupons of the procured wall grade (N+, N2+, O+, O2+ at 20-300 eV, 0-85 deg; weight loss "
                 "and QCM), H3 molecular vs atomic, H8 Xe+ on the same coupons; H6 EM wear segment on N2, N2 / O2 and "
                 "Xe with the H-1 channel and B(z) (replaceable exit rings with fiducials, AOL-RC-03; profiles each "
                 "stage, AOL-PM-03); H7 near-wall diagnostics; endurance acceptance pre-registered (AOL-LF-02)",
            dcr_trigger="if the H6 erosion rate extrapolated under the pre-registered method gives a wall life < "
                        "15,000 h at the reference operating point, raise a DCR on the wall erosion allowance (wall "
                        "thickness outside the frozen channel surfaces; not yet a DBF-1 value) or the B(z) target "
                        "(DBF1-BZ-01); the H1 reference channel geometry DBF1-H1-01..03 is architecture-frozen (A9.38) "
                        "and is not a lever; the wall grade within DBF1-MAT-04 is the last lever",
            input_dependency="P2 admitted Hall envelope (wall flux / energy); P3 H1 B(z)"))
        g.append(gate(
            f"{p}-DEPOSITION", mat, f"channel wall ({role})", ["DBF1-MAT-04", "DBF1-ICP-04"],
            "deposition (metallic collector sputter films on the exit insulators)", "EM_VERIFICATION_REQUIRED",
            ["EV-11"], ["DA-03"], ["A-ICP-01"],
            "the analog deposited metallic films on the HET front insulators (TK-71); conductive films on BN-SiO2 "
            "exit surfaces change wall conduction / SEE near the exit and the anode-to-ground isolation",
            test="AOL-WC-01 near-exit witness coupons of the wall grade with sheet resistance and EDS after each "
                 "block; exit-ring inspection (AOL-RC-03)",
            input_dependency="P4 collector sheath energy"))
        g.append(gate(
            f"{p}-THERMAL", mat, f"channel wall ({role})", ["DBF1-MAT-04"],
            "thermal: continuous-use temperature and thermal cycling", "EM_VERIFICATION_REQUIRED",
            ["EV-18", "EV-20"], ["DA-05", "DA-06"], ["A-CYC-01"],
            f"no DBF-1 wall temperature exists (P7); supplier oxidizing-atmosphere guides give necessary screening "
            f"ceilings of {ceil} after the 50 K margin; {grade_note}; up to 17,928 cycles (A-CYC-01); the "
            "ceramic's CTE (0.4-3 um/m K) is ~5-40x below the Inconel anode's (DA-05)",
            test="TP-07-equivalent wall-ring thermal cycling to >= 1.5 x the registered cycle count between the P7 "
                 "cold / hot wall temperatures with the mount; flexural strength retained after cycling; wall "
                 "thermocouples on the EM (AOL-CX-07)",
            dcr_trigger="if the P7 hot-case inner-wall temperature exceeds the selected grade's screening ceiling "
                        "(supplier oxidizing limit - 50 K, DA-06), the grade within DBF1-MAT-04 or the thermal path "
                        "changes by DCR",
            input_dependency="P7 H1_WALL_IN / H1_WALL_OUT hot / cold temperatures"))
        g.append(gate(
            f"{p}-OXIDE-ELEC", mat, f"channel wall ({role})", ["DBF1-MAT-04"], "electrical behaviour of the oxide scale",
            "NOT_APPLICABLE", [], [], [],
            "the wall is an insulator by function and carries no electrode current; surface conduction from "
            "deposits is covered by the deposition gate and SEE change by the plasma-exposure gate"))
    return g


# ------------------------------------------------------------------------------------------------ assembly


def build() -> dict:
    src = load_pinned()
    yt = load_yt()
    analyses = [da01_wake_ao(src), da02_internal_o(src), da03_collector_sputter(src, yt), da04_scale_asr(src),
                da05_cycles_cte(src), da06_temperature_screen(src)]
    ev = evidence_register(src)
    gates = build_gates()
    ev_ids = {e["id"] for e in ev}
    da_ids = {a["id"] for a in analyses}
    as_ids = {a["id"] for a in ASSUMPTIONS}
    for gt in gates:
        for e in gt["evidence"]:
            if e not in ev_ids:
                raise SystemExit(f"{gt['id']}: unknown evidence {e}")
        for a in gt["analyses"]:
            if a not in da_ids:
                raise SystemExit(f"{gt['id']}: unknown analysis {a}")
        for a in gt["assumptions"]:
            if a not in as_ids:
                raise SystemExit(f"{gt['id']}: unknown assumption {a}")
    counts = {}
    for gt in gates:
        counts[gt["verdict"]] = counts.get(gt["verdict"], 0) + 1
    dbf1_mat = [dbf1_item(src["DBF1"], i) for i in ("DBF1-MAT-01", "DBF1-MAT-02", "DBF1-MAT-03", "DBF1-MAT-04")]
    return {
        "schema": "abep_closure_materials_gates_v1",
        "id": "materials_gates_v1",
        "item": "P8 Materials (A9.38 Priority 8)",
        "lane": "L-MATERIALS",
        "date": DATE,
        "base_commit": BASE_COMMIT,
        "generated_by": "docs/closure/materials/build_materials_gates_v1.py",
        "governing": {k: {"path": PINS[k][0], "sha256": PINS[k][1]} for k in
                      ("A938", "A931", "A912", "DBF1", "DBF1_LOCK", "BOARD", "P4", "EVID")},
        "inputs": {k: {"path": v[0], "sha256": v[1]} for k, v in PINS.items()},
        "external_sources": EXTERNAL,
        "what_this_is_not": [
            "a change of any DBF-1 value or selection (DBF1-MAT-01..04 unchanged; no DCR raised)",
            "a P4 gate cell: every p4_anode_materials_v1 gate cell stays INCOMPLETE_EVIDENCE and its vocabulary never "
            "emits PASS; the verdicts here are closure-programme verdicts over the same evidence",
            "a T_validated,continuous, a life prediction, a CR-04 recession or an acceptance threshold (LOCK-2)",
            "qualification evidence: no in-house measurement on Vyovrinda hardware exists for any retained material",
        ],
        "verdict_vocabulary": {
            "PASS_BY_EVIDENCE": "closed by evidence applicable to the service domain",
            "PASS_BY_ANALYSIS_WITH_ASSUMPTION": "closed by analysis on stated, verifiable assumptions",
            "EM_VERIFICATION_REQUIRED": "open; the specific engineering-model / coupon test that closes it is named",
            "FAIL": "evidence shows the frozen item cannot meet the gate: a DCR",
            "NOT_APPLICABLE": "the mechanism does not apply to the material's function (reason stated)",
        },
        "evidence_class_vocabulary": list(CLASSES),
        "selections_retained": [{"id": m["id"], "name": m["name"], "value": m["value"], "status": m["status"]}
                                for m in dbf1_mat],
        "exposure_basis": {
            "mission_hours": src["SCEN"]["inputs"]["mission_hours"]["value"],
            "firing_hours": src["SCEN"]["inputs"]["firing_hours"]["value"],
            "ao_fluence_bound_m2": [src["MISSION"]["today_run"]["ao_fluence_bound"]["lower_m2"],
                                    src["MISSION"]["today_run"]["ao_fluence_bound"]["upper_m2"]],
            "sources": [PINS["SCEN"][0], PINS["MISSION"][0]],
        },
        "evidence": ev,
        "assumptions": ASSUMPTIONS,
        "analyses": analyses,
        "gates": gates,
        "verdict_counts": dict(sorted(counts.items())),
        "fail_count": counts.get("FAIL", 0),
        "design_driving_findings": [
            "ICP collector sputtering (DA-03): at analog cathodic-sheath energies the collector would lose tens of mm "
            "over the firing basis; the mean collector ion energy must stay below E* = 26-38 eV (0.5-2 mm "
            "allowance), 4-16 eV above the N+ -> Ni prior threshold. Owner of the requirement: P4 ICP closure (BD-06); the same for both retained alloys.",
            "Anode temperature (DA-06): the supplier oxidation-data domain caps IN600 at 930 degC and IN601 at 1150 degC "
            "after the 50 K margin; the only repository anode temperature (>= 1190 degC, inadmissible context) is "
            "above both. P7 decides; DCR triggers registered.",
            "Channel wall erosion (EV-15): the only air-mode analog life indication (7000-9500 h) is below the "
            "15,000 h firing basis; no N / O yield on BN or BN-SiO2 exists. EM wear segment H6 is the closing test.",
            "Internal O exposure (DA-02) of the anode is of the same order as or above the external ram-face bound; "
            "coupon AO fluence must be set from the internal dose.",
        ],
        "closure_state": {
            "item": "P8 Materials",
            "state": "FROZEN FOR EM",
            "meaning": "The DBF-1 material selections stay frozen (FROZEN_ASSUMPTION); every gate has a verdict; no gate "
                       "FAILs on evidence; the open gates close only by the named coupon / engineering-model tests "
                       "(qualification evidence cannot come from literature for these service conditions)",
            "conditions": [
                "P7 hot-case anode / collector / wall temperatures within the DA-06 screening ceilings (else the "
                "registered DCR triggers apply)",
                "P4 ICP closure holds the collector ion energy within the DA-03 ceiling at I_e >= I_d (else DCR on "
                "DBF1-ICP-04, not on the material)",
            ],
            "not_closed_because": "no measured property of any retained material exists in the service condition "
                                  "(O / N plasma, electrical loading, atomic O, service temperature); this is "
                                  "evidence-not-yet-available, not an architecture limit (A9.31 Q7)",
            "statement": "docs/closure/statements/P8_materials.md",
        },
    }


# ------------------------------------------------------------------------------------------------ markdown


def fmt(x):
    if isinstance(x, float):
        return f"{x:.4g}"
    return str(x)


def render_md(r: dict) -> str:
    L = []
    a = L.append
    a("# P8 materials closure gates v1 (A9.38 Priority 8)")
    a("")
    a(f"Generated by `{r['generated_by']}` from `materials_gates_v1.json` (do not edit by hand; `--check` reproduces "
      f"both files). Lane {r['lane']}, base `{r['base_commit']}`, {r['date']}.")
    a("")
    cs = r["closure_state"]
    a(f"**Closure state: {cs['state']}.** {cs['meaning']}.")
    a("")
    a("Conditions:")
    for c in cs["conditions"]:
        a(f"- {c}")
    a("")
    a(f"Not closed because: {cs['not_closed_because']}.")
    a("")
    a("This is not:")
    for w in r["what_this_is_not"]:
        a(f"- {w}")
    a("")
    a("## Retained selections (DBF-1, unchanged)")
    a("")
    a("| id | item | value | status |")
    a("|---|---|---|---|")
    for s in r["selections_retained"]:
        v = s["value"] if isinstance(s["value"], str) else "; ".join(f"{k}: {x}" for k, x in s["value"].items())
        a(f"| {s['id']} | {s['name']} | {v} | {s['status']} |")
    a("")
    a("## Gate table")
    a("")
    a("| gate id | material | application | gate | verdict | evidence | analyses | assumptions |")
    a("|---|---|---|---|---|---|---|---|")
    for g in r["gates"]:
        a(f"| {g['id']} | {g['material']} | {g['application']} | {g['gate']} | **{g['verdict']}** | "
          f"{', '.join(g['evidence']) or '-'} | {', '.join(g['analyses']) or '-'} | {', '.join(g['assumptions']) or '-'} |")
    a("")
    a("Verdict counts: " + ", ".join(f"{k} {v}" for k, v in r["verdict_counts"].items()) + ".")
    a("")
    a("## Design-driving findings")
    a("")
    for f in r["design_driving_findings"]:
        a(f"- {f}")
    a("")
    a("## Gate basis, EM test, DCR trigger")
    a("")
    for g in r["gates"]:
        a(f"### {g['id']} - {g['verdict']}")
        a("")
        a(f"- Basis: {g['basis']}.")
        if g["em_test"]:
            a(f"- EM / coupon test: {g['em_test']}.")
        if g["dcr_trigger"]:
            a(f"- DCR trigger: {g['dcr_trigger']}.")
        if g["input_dependency"]:
            a(f"- Input dependency: {g['input_dependency']}.")
        a("")
    a("## Evidence register")
    a("")
    a("| id | class | level | quantity type | statement | source | locator | domain | uncertainty | role |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for e in r["evidence"]:
        a(f"| {e['id']} | {e['class']} | {e['evidence_level']} | {e['quantity_type']} | {e['statement']} | "
          f"{e['source']} | {e['locator']} | {e['applicability_domain']} | {e['uncertainty']} | "
          f"{e['qualification_role']} |")
    a("")
    a("## Assumptions (stated, with their verification)")
    a("")
    a("| id | class | level | statement | verification |")
    a("|---|---|---|---|---|")
    for s in r["assumptions"]:
        a(f"| {s['id']} | {s['class']} | {s['evidence_level']} | {s['statement']} | {s['verification']} |")
    a("")
    a("## Derived analyses")
    a("")
    for d in r["analyses"]:
        a(f"### {d['id']} - {d['title']}")
        a("")
        a(f"Class {d['class']}, quantity type {d['quantity_type']}, evidence level {d['evidence_level']}.")
        if "method" in d:
            a(f"Method: {d['method']}.")
        if "use_restriction" in d:
            a(f"Use restriction: {d['use_restriction']}.")
        if "rule" in d:
            a(f"Rule: {d['rule']}.")
        a("")
        if "inputs" in d:
            a("Inputs: `" + json.dumps(d["inputs"], sort_keys=True) + "`")
            a("")
        if d["id"] in ("DA-01", "DA-02", "DA-04"):
            rows = d["rows"]
            cols = list(rows[0].keys())
            a("| " + " | ".join(cols) + " |")
            a("|" + "---|" * len(cols))
            for row in rows:
                a("| " + " | ".join(fmt(row[c]) for c in cols) + " |")
            a("")
        if d["id"] == "DA-03":
            cols = ["E_eV", "Y_Nplus_Ni", "Y_Oplus_Ni", "recession_mm_15000h_Nplus_Imin",
                    "recession_mm_15000h_Nplus_Imax", "sputtered_mass_kg_15000h_Nplus_Imax"]
            a("| " + " | ".join(cols) + " |")
            a("|" + "---|" * len(cols))
            for row in d["rows"]:
                a("| " + " | ".join(fmt(row[c]) for c in cols) + " |")
            a("")
            a("Ion-energy ceiling E* (N+ -> Ni prior) for a recession allowance over 15,000 h:")
            a("")
            a("| allowance mm | current | I A | Y_allow | E* eV |")
            a("|---|---|---|---|---|")
            for row in d["ion_energy_ceiling"]:
                a(f"| {row['allowance_mm']} | {row['current']} | {fmt(row['I_A'])} | {fmt(row['Y_allow'])} | "
                  f"{fmt(row['E_star_eV_Nplus_Ni_prior'])} |")
            a("")
            fl = d["floating_sheath_floor"]
            a(f"Floating-sheath floor: {fl['relation']}; {fl['T_e_basis']}.")
            a("")
            a("| ion | E_floor / T_e | T_e 3 eV | T_e 5 eV |")
            a("|---|---|---|---|")
            for row in fl["rows"]:
                a(f"| {row['ion']} | {fmt(row['E_floor_over_Te'])} | {fmt(row['E_floor_eV_Te3'])} | "
                  f"{fmt(row['E_floor_eV_Te5'])} |")
            a("")
            a("Register reproduction: the evaluation reproduces every tabulated YT-FIT-NIFS-F102 / F103 value (" +
              str(len(d["register_reproduction"])) + " points).")
            a("")
        if d["id"] == "DA-05":
            cc = d["cycle_count"]
            a(f"Cycle count: {cc['method']}.")
            a("")
            for row in cc["rows"]:
                a(f"- {row['alt_km']:.0f} km: period {row['period_min']} min, {row['orbits_over_mission']} orbits")
            cov = cc["manufacturer_cyclic_oxidation_coverage"]
            a(f"- supplier cyclic coverage <= {cov['cycles_at_full_axis']} cycles (ratio {cov['coverage_ratio']}); "
              f"{cov['note']}")
            ct = d["cte_mismatch"]
            a(f"- CTE mismatch {ct['delta_alpha_range_um_m_K']} um/m K -> {ct['radial_differential_mm_per_100K']} mm "
              f"per 100 K at r_out {ct['r_out_mm']} mm. {ct['reading']}")
            a("")
        if d["id"] == "DA-06":
            a("| material | basis | T_basis degC | screening ceiling degC |")
            a("|---|---|---|---|")
            for row in d["rows"]:
                a(f"| {row['material']} | {row['basis']} | {fmt(row['T_basis_C'])} | {fmt(row['screening_ceiling_C'])} |")
            a("")
        if "reading" in d:
            a(f"Reading: {d['reading']}.")
            a("")
        a(f"Uncertainty: {d.get('uncertainty', '-')}.")
        a("")
    a("## Sources")
    a("")
    a("Repository inputs (sha256-pinned; a change refuses the build):")
    a("")
    for k, v in r["inputs"].items():
        a(f"- `{v['path']}` `{v['sha256']}`")
    a("")
    a("External (read 2026-10-08 through the session proxy; not committed):")
    a("")
    for k, v in r["external_sources"].items():
        a(f"- {k}: {v['citation']}. {v['url']} (sha256 `{v['sha256']}`, {v['bytes']} bytes; {v['note']})")
    a("")
    a("Sources needed but not reachable from this session (lawful acquisition routes only; nothing bypassed):")
    a("")
    for s in UNREACHABLE:
        a(f"- {s}")
    a("")
    return "\n".join(L)


UNREACHABLE = [
    "Espy et al., Proc. SPIE 1761, 130-140 (1993), doi:10.1117/12.138921 - N+ / N2+ / O+ / O2+ on Al2O3 (closed; host "
    "spiedigitallibrary.org)",
    "Saint-Gobain Combat BN solids datasheet (M26 / AX05 / HP) - host bn.saint-gobain.com (HTTP 403 WAF, R3 access log)",
    "Wang, Akbar, Chen, Patton, J. Mater. Sci. 30 (1995) 1627 - electrical properties of high-temperature oxides "
    "(Cr2O3 / Al2O3 scale resistivity; paywalled, host link.springer.com)",
    "Cifali et al., Space Propulsion 2012, SP2012-2355386 - primary of the PPS1350 314 h / 7000-9500 h results (not "
    "located openly; host 3af-spacepropulsion.com / conference proceedings)",
    "Ranjan et al., AIP Adv. 6, 095224 (2016) and Crofton & Young, AIP Adv. 11, 125126 (2021) - BN / BN-SiO2 yields "
    "(bot-challenged; host pubs.aip.org)",
    "Borosil (BN-SiO2) elevated-temperature sputter study, Nucl. Instrum. Methods B (2022) - authors not retrieved "
    "(host sciencedirect.com)",
    "Tejeda & Knoll, Acta Astronaut. 203, 268 (2023), doi:10.1016/j.actaastro.2022.11.055 - O2 HET wall / anode "
    "materials (not accessed; host sciencedirect.com)",
]


def render_all():
    rec = build()
    js = json.dumps(rec, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    md = render_md(rec) + "\n"
    return js, md


def main(argv) -> int:
    js, md = render_all()
    if "--check" in argv:
        ok = OUT_JSON.read_text() == js and OUT_MD.read_text() == md
        print("materials_gates_v1: " + ("OK" if ok else "DRIFT"))
        return 0 if ok else 1
    OUT_JSON.write_text(js)
    OUT_MD.write_text(md)
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

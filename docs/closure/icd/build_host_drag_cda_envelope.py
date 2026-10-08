"""Build host_drag_cda_envelope_v1.json / .md (A9.38 P9): the host-spacecraft drag-area envelope that keeps
T_required = D_host + D_intake inside the 12-25 mN propulsion envelope at every required flight state.

Every number is read from the sha256-pinned M2 closure record (q per state, DBF-1 intake-face drag per state and
admitted surface scenario) and evaluated with one formula; nothing else is modelled here.

    D_host,max(s, k; T) = T - D_intake(s, k)                     [N]
    (C_D A)_host,max(s, k; T) = D_host,max(s, k; T) / q(s)       [m^2],  q(s) = 1/2 rho(s) v(s)^2
    D_intake(s, k) = d_intake(s, k) x A_intake                    (F1 TPMC intake-face drag per unit frontal area x 0.25 m^2)

with T = 12 mN (sustained, RVM-02) and 25 mN (capability, RVM-03). The governing surface scenario per state is the
unfavourable one (largest D_intake): A9.13 S6.16 requires feasibility in every admitted scenario. A state with
D_intake(s, k) >= T has no positive host C_D A at that thrust level.

When DCR-001 replaces the intake, rerun M2 on the revised baseline and point --record at the new closure record (the
formula and the code are unchanged; only d_intake and A_intake move).

Usage: python3 docs/closure/icd/build_host_drag_cda_envelope.py [--check]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RECORD = ("docs/milestones/M2_196_state_rfp_closure/m2_closure_record_v1.json",
          "600cf229ecdb5f91f0471f03cfdd6d287486ad21e9d9ebadde3cdafa54a37394")
DBF1 = ("docs/baseline/DBF-1/dbf1_v1.json", "d20f1e8aa95c2d6ee0b307669500d7aaa5ea6abf4d21ddb944b7999525943e4f")
SOURCES = [
    RECORD, DBF1,
    ("docs/decisions/OD_2026_10_08_A9_38_ARCHITECTURE_FROZEN_DESIGN_CLOSURE_PROGRAMME.md", None),
    ("docs/decisions/OD_2026_10_01_A9_13_S6_UPSTREAM_ARCHITECTURE_OWNER_DECISIONS.md", None),
    ("config/constraints/engineering_constraints_v1.json", None),
    ("docs/design_synthesis/f1_intake/f1_intake_synthesis_v1_core.json",
     "d397cb9348d06eafbe2e7cc3ee9ca035f97e8f423d63df8f42286ce75bc20854"),
    ("abep_sim/data/atmosphere_msis21_orbit_v1_design_states_v2.json",
     "60073e214cf5edb92d7eacf70be1491ad29ff72f19db0ef3b96a4b30da6f4049"),
    ("crates/abep-mission/data/spacecraft_reference_register_v1.json",
     "4952eb745b201a57406dc6fe0513f6217f654ddb6d2ad7300c5334112a42ffa3"),
]
A_INTAKE_M2 = 0.25
LEVELS = (("T12_sustained", 12.0e-3, "RVM-02 THRUST_12MN_SUSTAINED"),
          ("T25_capability", 25.0e-3, "RVM-03 THRUST_25MN_CAPABILITY"))
REFERENCE_CASE = "RC-DIAMANT"


class BuildError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned(rel: str, digest: str | None) -> dict:
    p = ROOT / rel
    got = sha(p)
    if digest is not None and got != digest:
        raise BuildError(f"{rel}: sha256 {got} != pinned {digest}")
    return {"path": rel, "sha256": got}


def r6(x: float) -> float:
    return float(f"{x:.6g}")


def parse_state(state_id: str) -> tuple[str, int]:
    parts = state_id.split(":")
    return parts[1], int(parts[2].removeprefix("alt"))


def summarize(vals: list) -> dict:
    """worst = min over states (None when a state has no positive host C_D A); typical = median; max."""
    pos = [v for v in vals if v is not None]
    worst = None if len(pos) < len(vals) else r6(min(pos))
    return {"worst_min": worst, "worst_min_over_states_with_positive": r6(min(pos)) if pos else None,
            "typical_median": r6(statistics.median([0.0 if v is None else v for v in vals])),
            "max": r6(max(pos)) if pos else None}


def build() -> dict:
    rec = json.loads((ROOT / RECORD[0]).read_bytes())
    if sha(ROOT / RECORD[0]) != RECORD[1]:
        raise BuildError("M2 record hash mismatch")
    scenarios = None
    rows = []
    case_cda = {}
    for st in rec["states"]:
        if not st["required"]:
            continue
        a = st["air_dbf1"]
        q = a["q_Pa"]
        cda_ref = a["D_body_mN"] * 1e-3 / q
        if abs(cda_ref - 1.1) > 1e-9:
            raise BuildError(f"{st['state_id']}: body C_D A {cda_ref} is not the RC-DIAMANT 1.1 m^2")
        for case, dmn in a["drag_sensitivity_body_mN"].items():
            v = dmn * 1e-3 / q
            if case in case_cda and abs(case_cda[case] - v) > 1e-9 * max(1.0, v):
                raise BuildError(f"{case}: C_D A not state-invariant")
            case_cda[case] = v
        names = [k["scenario"] for k in a["scenarios"]]
        if scenarios is None:
            scenarios = names
        elif names != scenarios:
            raise BuildError("surface-scenario order differs between states")
        d_int = {k["scenario"]: k["D_intake_mN"] * 1e-3 for k in a["scenarios"]}
        if any(v is None or v < 0 for v in d_int.values()):
            raise BuildError(f"{st['state_id']}: intake drag missing")
        unfav = max(d_int, key=lambda s: (d_int[s], s))
        fav = min(d_int, key=lambda s: (d_int[s], s))
        atm, alt = parse_state(st["state_id"])
        row = {
            "state_id": st["state_id"], "atmosphere_scenario": atm, "altitude_km": alt, "q_Pa": r6(q),
            "D_intake_mN": {"unfavourable": r6(d_int[unfav] * 1e3), "favourable": r6(d_int[fav] * 1e3),
                            "unfavourable_scenario": unfav, "favourable_scenario": fav},
        }
        for key, t, _ in LEVELS:
            out = {}
            for side, sc in (("unfavourable", unfav), ("favourable", fav)):
                dh = t - d_int[sc]
                out[side] = {"D_host_max_mN": r6(dh * 1e3),
                             "CDA_host_max_m2": r6(dh / q) if dh > 0 else None,
                             "positive_host_CDA_exists": dh > 0}
            row[key] = out
        row["RC_DIAMANT_T_required_mN_max"] = r6((cda_ref * q + d_int[unfav]) * 1e3)
        rows.append(row)

    def band_table(keyf):
        groups = collections.OrderedDict()
        for r in sorted(rows, key=lambda r: (keyf(r), r["state_id"])):
            groups.setdefault(keyf(r), []).append(r)
        table = []
        for k, rs in groups.items():
            ent = {"band": k if isinstance(k, str) else list(k), "n_states": len(rs)}
            for key, _, _ in LEVELS:
                vals = [r[key]["unfavourable"]["CDA_host_max_m2"] for r in rs]
                ent[key] = {
                    "CDA_host_max_m2_unfavourable": summarize(vals),
                    "n_states_no_positive_host_CDA": sum(v is None for v in vals),
                    "worst_state": min(rs, key=lambda r: (r[key]["unfavourable"]["D_host_max_mN"] / r["q_Pa"],
                                                          r["state_id"]))["state_id"],
                }
            ent["RC_DIAMANT_1p1_m2_states_T_required_gt_25mN"] = sum(
                r["RC_DIAMANT_T_required_mN_max"] > 25.0 for r in rs)
            table.append(ent)
        return table

    by_alt = band_table(lambda r: f"alt{r['altitude_km']}")
    by_alt_atm = band_table(lambda r: (r["altitude_km"], r["atmosphere_scenario"]))
    gov = {}
    for key, t, rvm in LEVELS:
        pos = [r for r in rows if r[key]["unfavourable"]["positive_host_CDA_exists"]]
        worst = min(pos, key=lambda r: (r[key]["unfavourable"]["CDA_host_max_m2"], r["state_id"]))
        none_any = [r["state_id"] for r in rows if not r[key]["unfavourable"]["positive_host_CDA_exists"]]
        none_fav = [r["state_id"] for r in rows if not r[key]["favourable"]["positive_host_CDA_exists"]]
        gov[key] = {
            "thrust_level_mN": t * 1e3, "requirement": rvm,
            "CDA_host_max_m2_all_states_unfavourable": (r6(worst[key]["unfavourable"]["CDA_host_max_m2"])
                                                        if not none_any else None),
            "CDA_host_max_m2_over_states_with_positive": r6(worst[key]["unfavourable"]["CDA_host_max_m2"]),
            "governing_state": worst["state_id"],
            "D_host_max_mN_at_governing_state": worst[key]["unfavourable"]["D_host_max_mN"],
            "n_states_no_positive_host_CDA_unfavourable": len(none_any),
            "n_states_no_positive_host_CDA_in_every_scenario": len(none_fav),
            "states_no_positive_host_CDA_unfavourable": none_any,
        }
    ref_cases = {c: {"CDA_m2": r6(v),
                     "states_T_required_gt_25mN_unfavourable": sum(
                         v * r["q_Pa"] + r["D_intake_mN"]["unfavourable"] * 1e-3 > 25e-3 for r in rows),
                     "complies_T25_every_state": all(
                         r["T25_capability"]["unfavourable"]["CDA_host_max_m2"] is not None
                         and v <= r["T25_capability"]["unfavourable"]["CDA_host_max_m2"] for r in rows)}
                 for c, v in sorted(case_cda.items())}
    probe = [0.25, 0.5, 1.0, 1.1, 2.0]
    compliant = []
    atms = sorted({r["atmosphere_scenario"] for r in rows})
    alts = sorted({r["altitude_km"] for r in rows})
    for cda in probe:
        ent = {"CDA_m2": cda}
        for key, _, _ in LEVELS:
            per = {}
            for atm in atms:
                ok_alts = []
                for alt in alts:
                    rs = [r for r in rows if r["atmosphere_scenario"] == atm and r["altitude_km"] == alt]
                    if all(r[key]["unfavourable"]["CDA_host_max_m2"] is not None
                           and cda <= r[key]["unfavourable"]["CDA_host_max_m2"] for r in rs):
                        ok_alts.append(alt)
                # lowest altitude from which every higher altitude band also complies
                lowest = None
                for alt in reversed(alts):
                    if alt in ok_alts:
                        lowest = alt
                    else:
                        break
                per[atm] = {"compliant_altitude_bands_km": ok_alts, "lowest_altitude_all_above_compliant_km": lowest}
            ent[key] = per
        compliant.append(ent)
    n_gt25 = sum(r["RC_DIAMANT_T_required_mN_max"] > 25.0 for r in rows)
    if n_gt25 != 40:
        raise BuildError(f"RC-DIAMANT states above 25 mN {n_gt25} != the M2 record's 40")
    return {
        "schema": "abep_icd_constraint_v1",
        "id": "host_drag_cda_envelope_v1",
        "item": "A9.38 P9 host-spacecraft drag interface",
        "interface_requirement_id": "IR-HOST-DRAG-01",
        "date": "2026-10-08",
        "architecture": "hall_icp_neutralizer (frozen 2026-10-08, DBF-1)",
        "status": "INTERFACE_CONSTRAINT_REGISTERED_PENDING_CUSTOMER_ICD",
        "governing_formula": {
            "D_host_max": "D_host,max(s, k; T) = T - D_intake(s, k)",
            "CDA_host_max": "(C_D A)_host,max(s, k; T) = (T - D_intake(s, k)) / q(s)",
            "q": "q(s) = 1/2 rho(s) v(s)^2 at the admitted orbit-resolved state (abep_mission::intake_drag::"
                 "EnvelopeAtmospheres: frozen NRLMSIS 2.1 design-state set v2, the required states)",
            "D_intake": "D_intake(s, k) = d_intake(s, k) x A_intake; d_intake = F1 TPMC intake-face drag per unit "
                        "frontal area (theta 0) of the DBF-1 intake A0.25_Ld20_phi0.9 in admitted surface scenario k; "
                        "A_intake = 0.25 m^2 (DBF1-IN-02)",
            "governing_scenario": "unfavourable k (largest D_intake) per state: feasibility in every admitted surface "
                                  "scenario is required (A9.13 S6.16); the favourable value is reported alongside",
            "thrust_levels": "T = 12 mN (sustained, RVM-02) and 25 mN (capability, RVM-03); the statewise hard "
                             "constraint T_available - D_spacecraft >= 0 (A9.13 S6.15, HC-08) needs D_host + D_intake "
                             "<= T_available <= 25 mN",
            "no_positive_host": "D_intake(s, k) >= T: no positive host C_D A keeps T_required <= T at that state",
            "lower_bound": "none from drag compensation: T_required < 12 mN leaves a positive T - D (orbit-raise / "
                           "duty-cycle authority for mission operations); C_D A >= 0 only",
            "update_rule": "DCR-001 (intake / compressor redesign) changes d_intake and A_intake only: rerun M2 on "
                           "the revised controlled baseline and rebuild with --record; the formula is unchanged",
        },
        "inputs": {
            "environment": "M2 closure record q_Pa per required state (196 states, 4 altitudes x ECSS long-term "
                           "low / moderate / high and short-term high solar-geomagnetic scenarios)",
            "intake_face_drag": "M2 closure record D_intake_mN per state and admitted surface scenario (10: Maxwell / "
                                "CLL, alpha 0-1, DBF1-IN-03), DBF-1 intake area 0.25 m^2",
            "accommodation_basis": "intake: the 10 admitted TPMC surface scenarios, none chosen (DBF1-DRAG-03; "
                                   "accommodation unmeasured, DI-1.3); host: the host's own C_D A on its own GSI / "
                                   "accommodation basis (customer ICD item, A9.13 S6.18)",
            "surface_scenarios": scenarios,
        },
        "results": {
            "governing": gov,
            "by_altitude": by_alt,
            "by_altitude_and_atmosphere_scenario": by_alt_atm,
            "reference_cases_body_CDA": ref_cases,
            "compliance_by_host_CDA": compliant,
            "RC_DIAMANT_states_T_required_gt_25mN": n_gt25,
        },
        "per_state": rows,
        "icd_constraint_text": (
            "IR-HOST-DRAG-01. The host spacecraft drag area (C_D A of the host body, arrays and appendages in the "
            "flight attitude, excluding the propulsion intake face, evaluated on the host's own surface-accommodation "
            "basis) shall not exceed (C_D A)_host,max(s) = (T - D_intake(s)) / q(s) at every required flight state s "
            "of the mission envelope, with T = 25 mN (propulsion capability) as the hard statewise limit and "
            "T = 12 mN (sustained thrust level) as the design target for continuous drag compensation. Equivalently "
            "the host body drag shall not exceed D_host,max(s) = T - D_intake(s). Values are tabulated per state in "
            "host_drag_cda_envelope_v1.json; compliance is verified by the spacecraft prime by analysis against the "
            "customer spacecraft ICD."
        ),
        "not": [
            "not a propulsion redesign: the propulsion envelope (12-25 mN) and DBF-1 are unchanged (A9.38 P9)",
            "not a host design: RC-DIAMANT (1.1 m^2) stays a REFERENCE_PENDING_CUSTOMER_ICD case",
            "not a thrust prediction: T_available is not evaluated (HALL_NUMERICS_NOT_CONVERGED); the envelope is "
            "drag-side only",
        ],
        "sources": [pinned(p, d) for p, d in SOURCES],
        "generated_by": "docs/closure/icd/build_host_drag_cda_envelope.py",
    }


def fmt(x, nd=3):
    return "none" if x is None else f"{x:.{nd}g}"


def to_md(doc: dict) -> str:
    g = doc["results"]["governing"]
    L = []
    L.append("# Host-spacecraft drag-area envelope (IR-HOST-DRAG-01, A9.38 P9)\n")
    L.append(f"Record `host_drag_cda_envelope_v1.json` (this page restates it). Status "
             f"**{doc['status']}**. Inputs: M2 closure record `{RECORD[0]}` (sha256 `{RECORD[1][:12]}...`), "
             "DBF-1 intake. Builder: `build_host_drag_cda_envelope.py`.\n")
    L.append("## Interface constraint (ICD wording)\n")
    L.append(doc["icd_constraint_text"] + "\n")
    L.append("## Governing formula\n")
    f = doc["governing_formula"]
    L.append("```text\n" + f["D_host_max"] + "\n" + f["CDA_host_max"] + "\n" + f["D_intake"] + "\n" + f["q"] + "\n```\n")
    for k in ("governing_scenario", "thrust_levels", "no_positive_host", "lower_bound", "update_rule"):
        L.append(f"- **{k.replace('_', ' ')}**: {f[k]}")
    L.append("")
    L.append("## Governing values (all 196 required states, unfavourable surface scenario)\n")
    L.append("| thrust level | max host C_D A over the whole envelope [m^2] | governing state | D_host,max there [mN] | "
             "states with no positive host C_D A (unfav / every scenario) |")
    L.append("|---|---|---|---|---|")
    for key, _, _ in LEVELS:
        x = g[key]
        L.append(f"| {x['thrust_level_mN']:g} mN ({x['requirement']}) | "
                 + (fmt(x['CDA_host_max_m2_all_states_unfavourable'])
                    if x['CDA_host_max_m2_all_states_unfavourable'] is not None else
                    f"none (no positive value at {x['n_states_no_positive_host_CDA_unfavourable']} states; "
                    f"{fmt(x['CDA_host_max_m2_over_states_with_positive'])} over the others)")
                 + " "
                 f"| `{x['governing_state']}` | {fmt(x['D_host_max_mN_at_governing_state'])} | "
                 f"{x['n_states_no_positive_host_CDA_unfavourable']} / "
                 f"{x['n_states_no_positive_host_CDA_in_every_scenario']} |")
    L.append("")
    L.append("## By altitude band (worst state / typical = median state / max; unfavourable scenario)\n")
    L.append("| band | states | C_D A max @25 mN worst / typical / max [m^2] | C_D A max @12 mN worst / typical / max "
             "[m^2] | states with no positive C_D A @12 mN | RC-DIAMANT states > 25 mN |")
    L.append("|---|---|---|---|---|---|")
    for e in doc["results"]["by_altitude"]:
        a = e["T25_capability"]["CDA_host_max_m2_unfavourable"]
        b = e["T12_sustained"]["CDA_host_max_m2_unfavourable"]
        L.append(f"| {e['band']} | {e['n_states']} | {fmt(a['worst_min'])} / {fmt(a['typical_median'])} / "
                 f"{fmt(a['max'])} | {fmt(b['worst_min'])} / {fmt(b['typical_median'])} / {fmt(b['max'])}" +
                 f" | {e['T12_sustained']['n_states_no_positive_host_CDA']} | "
                 f"{e['RC_DIAMANT_1p1_m2_states_T_required_gt_25mN']} |")
    L.append("")
    L.append("## By altitude and atmosphere scenario (unfavourable surface scenario)\n")
    L.append("| altitude [km] | atmosphere | states | C_D A max @25 mN worst / typical [m^2] | C_D A max @12 mN worst / "
             "typical [m^2] | no positive C_D A @12 mN | RC-DIAMANT > 25 mN |")
    L.append("|---|---|---|---|---|---|---|")
    for e in doc["results"]["by_altitude_and_atmosphere_scenario"]:
        a = e["T25_capability"]["CDA_host_max_m2_unfavourable"]
        b = e["T12_sustained"]["CDA_host_max_m2_unfavourable"]
        L.append(f"| {e['band'][0]} | {e['band'][1]} | {e['n_states']} | {fmt(a['worst_min'])} / "
                 f"{fmt(a['typical_median'])} | {fmt(b['worst_min'])} / {fmt(b['typical_median'])}" +
                 f" | {e['T12_sustained']['n_states_no_positive_host_CDA']} | "
                 f"{e['RC_DIAMANT_1p1_m2_states_T_required_gt_25mN']} |")
    L.append("")
    L.append("## Declared reference bodies against the envelope (context; none is the host)\n")
    L.append("| case | C_D A [m^2] | states with T_required > 25 mN (unfav) | complies at 25 mN in every state |")
    L.append("|---|---|---|---|")
    for c, v in doc["results"]["reference_cases_body_CDA"].items():
        L.append(f"| {c} | {fmt(v['CDA_m2'])} | {v['states_T_required_gt_25mN_unfavourable']} | "
                 f"{'yes' if v['complies_T25_every_state'] else 'no'} |")
    L.append("")
    L.append("## Lowest altitude band from which a given host C_D A complies (every state at and above it)\n")
    L.append("| host C_D A [m^2] | thrust level | " + " | ".join(atms_md := sorted(
        doc["results"]["compliance_by_host_CDA"][0]["T25_capability"])) + " |")
    L.append("|---|---|" + "---|" * len(atms_md))
    for e in doc["results"]["compliance_by_host_CDA"]:
        for key, t, _ in LEVELS:
            cells = []
            for atm in atms_md:
                lo = e[key][atm]["lowest_altitude_all_above_compliant_km"]
                cells.append("no band" if lo is None else f">= {lo} km")
            L.append(f"| {e['CDA_m2']:g} | {t * 1e3:g} mN | " + " | ".join(cells) + " |")
    L.append("")
    L.append("Worst = the smallest allowable C_D A over the band's states ('none' when at least one state has no "
             "positive value); typical = the median state (a state with no positive value counts as 0).\n")
    L.append("## States infeasible for any positive host C_D A\n")
    x25 = g["T25_capability"]
    x12 = g["T12_sustained"]
    L.append(f"- At 25 mN: {x25['n_states_no_positive_host_CDA_unfavourable']} states (the DBF-1 intake-face drag is "
             "below 25 mN at every state and scenario).")
    L.append(f"- At 12 mN: {x12['n_states_no_positive_host_CDA_unfavourable']} states in the unfavourable scenario "
             f"({x12['n_states_no_positive_host_CDA_in_every_scenario']} in every scenario): there the DBF-1 intake "
             "face alone needs more than 12 mN, so continuous compensation at the sustained level is not possible "
             "for any host; the propulsion system must operate above 12 mN (up to its 25 mN capability) at those "
             "states. This is an intake-drag property of DBF-1, carried to DCR-001.")
    L.append("")
    L.append("Per-state values (both scenarios, both thrust levels, D_host,max and C_D A max) are in the JSON "
             "`per_state` list.\n")
    L.append("## Not\n")
    for n in doc["not"]:
        L.append(f"- {n}")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = build()
    js = (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode()
    md = to_md(doc).encode()
    outs = {HERE / "host_drag_cda_envelope_v1.json": js, HERE / "host_drag_cda_envelope_v1.md": md}
    if args.check:
        bad = [str(p) for p, b in outs.items() if not p.exists() or p.read_bytes() != b]
        if bad:
            print("STALE: " + ", ".join(bad))
            sys.exit(1)
        print("OK")
        return
    for p, b in outs.items():
        p.write_bytes(b)
    print("wrote", ", ".join(str(p.relative_to(ROOT)) for p in outs))


if __name__ == "__main__":
    main()

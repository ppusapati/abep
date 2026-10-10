"""DCR-DBF1-001 resolution v1 and window report v1 (A9.39 item 3), built from the committed amendment v3 records.

Reads (sha256-pinned on the command line, refused otherwise): the window record (abep-dcr001-eval window-record), which
pins the search, the governed Python stability reference and the preregistration v3. Writes:
  docs/baseline/DCR-001/dcr001_resolution_v1.json   the resolution (proposes DBF-1.2 on top of DBF-1.1)
  docs/baseline/DCR-001/DCR001_WINDOW_REPORT_v1.md   the human-readable report
  docs/closure/intake/p1_closure_state_v1.json       the P1 closure state (A9.38 priority 1)
No value is computed here except unit conversions and copies; every number comes from the record.

Usage: python3 docs/baseline/DCR-001/build_dcr001_resolution.py RECORD_SHA256 [--check]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
D = "docs/baseline/DCR-001"
RECORD = f"{D}/dcr001_window_record_v1.json"
OUT_JSON = f"{D}/dcr001_resolution_v1.json"
OUT_MD = f"{D}/DCR001_WINDOW_REPORT_v1.md"
OUT_STATE = "docs/closure/intake/p1_closure_state_v1.json"
PINS = {
    "prereg_v1": (f"{D}/dcr001_eval_prereg_v1.json", "98f9931cbf537c3acca9753fafc9c9a9f93b22e7beb27dbae950f0c2c9e556f5"),
    "prereg_v2": (f"{D}/dcr001_eval_prereg_v2.json", "7ebb61eb16dd724aed3ac2dd1de9e3e77390a9e9e3d8f404a3d697fa2c75954c"),
    "prereg_v3": (f"{D}/dcr001_eval_prereg_v3.json", "c79ea6c110f46799c5c3aaab1b091519d13ee2bf7b7c03112236de05f8c4dbb9"),
    "lock_v3": (f"{D}/dcr001_eval_prereg_lock_v3.json", "65f276e8adcd6aefb63f04bf24067cc181f93c460ae9c56c82a16d5d0094649b"),
    "request": (f"{D}/dcr001_request_v1.json", None),
    "a9_39": ("docs/decisions/OD_2026_10_09_A9_39_ARCHITECTURE_CLOSED_OWNER_DECISIONS.md",
              "7c3880c3f2b5dedefcd66c0c8fbe0362b3aa199099183ec3d65c020bf48f2949"),
    "dbf1_1_lock": ("docs/baseline/DBF-1.1/dbf1_1_lock_v1.json",
                    "257e141ca252c3015b5bbd2fc953a1de688bc1606be36ebdf9fff8889307cfb8"),
    "dbf1_1": ("docs/baseline/DBF-1.1/dbf1_1_v1.json", "b8daa5bd5bb18b4fc92d6f65b0d93d0e70b33cd80d0f222cb9957ced3075c22b"),
    "mass_power": ("docs/budgets/mass_power_a9_v5/mass_power_a9_v5.json",
                   "3ff23429f5225a8a8363a784281b2f32b1df9ad69ec9934320306b080436b73a"),
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pinned(rel: str, want: str | None) -> bytes:
    b = (ROOT / rel).read_bytes()
    if want is not None and sha(b) != want:
        raise SystemExit(f"REFUSED: {rel} sha256 {sha(b)} != pinned {want}")
    return b


def src(key: str) -> dict:
    rel, want = PINS[key]
    return {"path": rel, "sha256": want or sha((ROOT / rel).read_bytes())}


def g(x, n=4):
    return f"{x:.{n}g}" if isinstance(x, (int, float)) and x is not None else str(x)


def build(record_sha: str):
    rec_b = pinned(RECORD, record_sha)
    rec = json.loads(rec_b)
    if rec.get("schema") != "abep_dcr001_window_record_v1" or rec["prereg"]["sha256"] != PINS["prereg_v3"][1]:
        raise SystemExit("REFUSED: record schema / preregistration pin differs")
    for k in PINS:
        pinned(*PINS[k])
    srch = json.loads(pinned(rec["inputs"]["search"]["path"], rec["inputs"]["search"]["sha256"]))
    py = rec["inputs"]["python_reference"]
    pinned(py["path"], py["sha256"])
    sel, win, ops = rec["selection"], rec["window"], rec["window_operating_points"]
    if win.get("window") is None and "Phi_lo_kg_m2_s" not in win:
        raise SystemExit("REFUSED: the record has no window")
    intake, comp, plen = sel["intake"], sel["compressor"], sel["plenum"]
    ends = ops["window_end_points_detail"]
    sched = win["altitude_schedule"]
    uncovered = [c for c, v in sched.items() if v["status"] != "COVERED"]
    m_comp = win["m_compressor_max_kg"]
    mp = json.loads(pinned(*PINS["mass_power"]))
    al02 = next(l for l in mp["lines"]["hall_icp_neutralizer"] if l["line"] == "AL-02")["row54_allocation_kg"]
    mass_transfer = None
    if m_comp > al02:
        mass_transfer = {
            "id": "MTR-DCR001-01",
            "to": "mass / power / thermal roll-up (A9.39 work item 4)",
            "line": "AL-02 compressor + drive",
            "allocation_kg": al02,
            "required_model_mass_kg": m_comp,
            "transfer_kg": m_comp - al02,
            "basis": "compressor model mass of the selected design (F3 DragCompressor model, nominal coefficients; "
                     "PARAMETRIC, coefficients assumed level 7); no AL-02-compliant compressor of the registered F3 grid "
                     "yields an admissible window (record: search.selection / mass_relaxed)",
            "status": "REQUESTED (the roll-up decides the funding line; not a change of any owner allocation by this lane)",
        }
    mech = srch["mass_relaxed"]["mechanisms"] if sel["mass_relaxed_selection"] else srch["mechanisms"]
    closure = (
        "FROZEN FOR EM" if not uncovered else "FROZEN FOR EM (with registered-condition coverage finding)"
    )
    label = sel["label"]
    em_items = [
        "effective-capture modulation (segment shutters): open-fraction range, actuation and closed-segment drag "
        "(conservative bound 4.1 q used in analysis) - ground / EM test",
        "intake capture efficiency and face drag under the flight surface accommodation (TPMC ROM, 10 admitted scenarios "
        "carried; DI-1.3) - coupon / EM test",
        "compressor delivered flow, pressure ratio, mass and power (DragCompressor coefficients assumed level 7 with "
        "bands; corner behaviour recorded) - EM test",
        "feed-loop stability of the plenum / pressure-regulated feed at the window operating points - EM test",
        "atmospheric Hall operation at the delivered flow and composition (A9.39 item 4) - EM test",
    ]
    if label != "ADMISSIBLE_ROBUST":
        em_items.insert(3, "compressor-coefficient condition: the window holds at nominal coefficients; the "
                           "unfavourable corners listed in the record reduce it - verify kS / kK / leak on the EM")
    upstream = {
        "design_id": f"{intake_id(intake)}|{sel['filter']}|{comp['id']}|V{g(plen['V_m3'])}|P{g(plen['P_set_Pa'])}",
        "candidate": intake_id(intake),
        "area_m2": intake["A_max_m2"],
        "L_over_d": intake["L_over_d"],
        "phi": intake["phi"],
        "filter": sel["filter"],
        "compressor": comp["id"],
        "V_m3": plen["V_m3"],
        "P_set_Pa": plen["P_set_Pa"],
        "wall": plen["wall"],
        "controller": sel["controller"],
    }
    variable_capture = {
        "mechanism": sel["mechanism"],
        "N_segments": intake["N_segments"],
        "A_max_m2": intake["A_max_m2"],
        "A_eff_used_m2": intake["A_eff_used_m2"],
        "open_fraction_used": intake["open_fraction_used"],
        "C_closed": rec["inputs"]["C_closed"],
    }
    window = {
        "flux_coordinate": "rho V (free-stream mass flux of the frozen NRLMSIS 2.1 design-state atmosphere, V circular inertial)",
        "Phi_lo_kg_m2_s": win["Phi_lo_kg_m2_s"],
        "Phi_hi_kg_m2_s": win["Phi_hi_kg_m2_s"],
        "ratio": win["ratio_hi_over_lo"],
        "Phi_adm_A4_at_ends": win["Phi_adm_A4_at_ends"],
        "states_in_window": win["n_states_in_window"],
        "altitude_schedule": {c: v["admissible_nodes_km"] for c, v in sched.items()},
        "uncovered_conditions": uncovered,
    }
    res = {
        "schema": "abep_dcr_resolution_v1",
        "id": "DCR-DBF1-001-RESOLUTION-v1",
        "dcr": "DCR-DBF1-001 (alias DCR-001)",
        "date": "2026-10-09",
        "lane": "L-DCR001-FINAL (A9.39 item 3)",
        "authority": [src("a9_39")],
        "method": {"prereg_v1": src("prereg_v1"), "prereg_v2": src("prereg_v2"), "prereg_v3": src("prereg_v3"),
                   "lock_v3": src("lock_v3"), "request": src("request"),
                   "rule": "v3 (A9.39 item 3) governs the sizing requirement; v1 / v2 stay as history"},
        "evidence": {"record": {"path": RECORD, "sha256": record_sha}, "search": rec["inputs"]["search"],
                     "spec": rec["inputs"]["spec"], "python_reference": py},
        "label": rec["label"],
        "result": {
            "selection_label": label,
            "design_id": sel["design_id"],
            "mechanism_selection": {
                "selected": sel["mechanism"],
                "rule": "complexity ranks after the coverage objective (O1 conditions, O2 nodes); the simplest candidate "
                        "reaching the best coverage is selected; VC-2 bypass and VC-3 variable throat have no admitted "
                        "model and are not needed unless VC-1 leaves a condition uncovered",
                "by_segment_count": mech,
            },
            "within_AL02_compressor_mass": {
                "rule": "primary evaluation with the 5.5 kg AL-02 compressor limit (prereg v3 mass_transfer)",
                "mechanisms": srch["mechanisms"],
                "best_design": (srch.get("top_20_by_v3_keys_without_R") or [None])[0],
                "finding": None if not sel["mass_relaxed_selection"] else "no AL-02-compliant compressor of the registered F3 grid covers more than one registered "
                           "condition; the mass-relaxed evaluation covers all four, so the mass-relaxed selection is taken "
                           "with an explicit mass-transfer request",
            },
            "physical_maximum_aperture_m2": intake["A_max_m2"],
            "effective_capture_area_modulation_m2": intake["A_eff_used_m2"],
            "open_fraction_range": intake["open_fraction_used"],
            "intake_geometry": {k: intake[k] for k in ("A_max_m2", "N_segments", "L_over_d", "phi", "channel_diameter",
                                                       "wall_area_2_phi_Amax_Ld_m2")},
            "capture_efficiency_min_max_by_scenario": ops["capture_efficiency_min_max_by_scenario"],
            "drag": {"D_tot_max_N": win["D_tot_max_N"], "CDA_host_m2": rec["inputs"]["CDA_host_m2"],
                     "window_end_points": [{k: e[k] for k in ("scenario", "state_id", "D_intake_N", "D_host_N", "D_tot_N")}
                                           for e in ends]},
            "compressor": {"id": comp["id"], "f3_grid_index": comp["f3_grid_index"], "design": comp["design"],
                           "P_el_max_W": win["P_compressor_max_W"], "m_model_max_kg": m_comp,
                           "window_end_points": [{k: e[k] for k in ("scenario", "state_id", "compressor_inlet_P_Pa",
                                                                    "pressure_ratio_P_set_over_inlet", "P_compressor_el_W")}
                                                 for e in ends]},
            "plenum": plen,
            "controller": sel["controller"],
            "delivered_flow": {"worst_sustained_flow_ratio": win["worst_sustained_flow_ratio"],
                               "window_end_points": [{k: e[k] for k in ("scenario", "state_id", "mdot_delivered_kg_s",
                                                                        "mdot_req_sustained_kg_s", "flow_ratio")}
                                                     for e in ends],
                               "x_O_delivered_min_max": ops["x_O_delivered_min_max"],
                               "states_with_25mN_capability_point": win["states_with_25mN_capability_point"]},
            "feed_loop_stability": rec["stability"],
            "window": window,
            "altitude_schedule_interpolated": rec["altitude_schedule_interpolated"],
            "verification_set_196": rec["verification_set_196"]["counts"],
            "information": rec["information"],
        },
        "mass_transfer_request": mass_transfer,
        "proposed_baseline": {
            "id": "DBF-1.2",
            "parent": {"id": "DBF-1.1", "lock": src("dbf1_1_lock")},
            "dir": "docs/baseline/DBF-1.2/",
            "changes": ["DBF1-IN-01", "DBF1-IN-02", "DBF1-IN-04", "DBF1-IN-05", "DBF1-IN-06", "DBF1-IN-07",
                        "DBF1-IN-08", "new DBF1-IN-09 variable-capture mechanism", "new DBF1-OP-01 AIR operating flux window",
                        "new DBF1-OP-02 altitude schedule"],
            "config_upstream": upstream,
            "variable_capture": variable_capture,
            "operating_window": window,
            "deficiency_updates": {
                "DBF1-BD-01": "CLOSED_BY_DCR-DBF1-001 within the AIR operating window (A9.39: window + altitude schedule "
                              "replace the fixed all-states criterion); states outside the window are the conservative "
                              "verification set, not a sizing requirement",
                "DBF1-BD-02": ("CLOSED_BY_DCR-DBF1-001 (every window operating point in domain in all 10 scenarios; feed loop "
                               "class S, governed Python reference with Rust R2 agreement)"),
                "DBF1-BD-03": ("TRANSFERRED_TO_ROLL_UP (MTR-DCR001-01)" if mass_transfer else "CLOSED_BY_DCR-DBF1-001"),
            },
            "dbf1_and_dbf1_1": "never edited (immutable history)",
        },
        "dcr_status_proposed": "RESOLVED_PROPOSES_DBF-1.2 (the coordinator records approval in the DCR register; this lane "
                               "does not write dcr_register_*)",
        "p1_closure_state": closure,
        "em_verification_items": em_items,
        "not": ["not a performance prediction, validation, qualification or flight acceptance",
                "not an architecture change (A9.39 froze the architecture)",
                "not a change of an RFP requirement, owner allocation or admitted / scored record"],
        "generated_by": f"{D}/build_dcr001_resolution.py",
    }
    return res, render_md(res, rec)


def closure_state(res: dict, res_bytes: bytes) -> dict:
    r = res["result"]
    w = r["window"]
    return {
        "schema": "abep_closure_state_v1",
        "item": "P1",
        "title": "Intake / compressor / plenum / feed (A9.38 Priority 1; A9.39 item 3 variable effective capture)",
        "date": res["date"],
        "lane": res["lane"],
        "closure_state": res["p1_closure_state"],
        "selection_label": r["selection_label"],
        "design_id": r["design_id"],
        "governing_evidence": [
            {"path": OUT_JSON, "sha256": sha(res_bytes)},
            res["evidence"]["record"], res["evidence"]["search"], res["evidence"]["python_reference"],
            res["method"]["prereg_v3"], res["method"]["lock_v3"],
        ],
        "summary": {
            "mechanism": r["mechanism_selection"]["selected"],
            "A_max_m2": r["physical_maximum_aperture_m2"],
            "A_eff_used_m2": r["effective_capture_area_modulation_m2"],
            "window_Phi_kg_m2_s": [w["Phi_lo_kg_m2_s"], w["Phi_hi_kg_m2_s"]],
            "altitude_schedule_km": w["altitude_schedule"],
            "uncovered_conditions": w["uncovered_conditions"],
            "compressor": r["compressor"]["id"],
            "m_compressor_model_kg": r["compressor"]["m_model_max_kg"],
            "P_compressor_max_W": r["compressor"]["P_el_max_W"],
            "worst_sustained_flow_ratio": r["delivered_flow"]["worst_sustained_flow_ratio"],
        },
        "mass_transfer_request": res["mass_transfer_request"],
        "em_verification_items": res["em_verification_items"],
        "statement": "docs/closure/statements/P1_intake_compressor.md",
        "proposed_baseline": "DBF-1.2 (docs/baseline/DBF-1.2/)",
    }


def intake_id(i: dict) -> str:
    return f"A{g(i['A_max_m2'])}_Ld{g(i['L_over_d'])}_phi{g(i['phi'])}|N{i['N_segments']}"


def render_md(res: dict, rec: dict) -> bytes:
    r = res["result"]
    w = r["window"]
    L = ["# DCR-001 window evaluation report v1 (amendment v3, A9.39 item 3)", "",
         f"Record `{res['evidence']['record']['path']}` (sha256 `{res['evidence']['record']['sha256']}`); resolution "
         f"`{OUT_JSON}`. Label: {res['label']}.", "",
         "## Selection", "",
         f"- design `{r['design_id']}` — **{r['selection_label']}**",
         f"- mechanism: {r['mechanism_selection']['selected']}; physical maximum aperture {g(r['physical_maximum_aperture_m2'])} m²; "
         f"effective capture area used {g(r['effective_capture_area_modulation_m2'][0])}–{g(r['effective_capture_area_modulation_m2'][1])} m² "
         f"(open fraction {g(r['open_fraction_range'][0])}–{g(r['open_fraction_range'][1])})",
         f"- intake L/d {g(r['intake_geometry']['L_over_d'])}, φ {g(r['intake_geometry']['phi'])}, wall area "
         f"{g(r['intake_geometry']['wall_area_2_phi_Amax_Ld_m2'])} m²",
         f"- compressor `{r['compressor']['id']}`: model mass {g(r['compressor']['m_model_max_kg'])} kg, electrical power ≤ "
         f"{g(r['compressor']['P_el_max_W'])} W",
         f"- plenum V {g(r['plenum']['V_m3'])} m³, P_set {g(r['plenum']['P_set_Pa'])} Pa ({r['plenum']['wall']}); controller "
         f"Kp {g(r['controller']['Kp'])}, Ti {g(r['controller']['Ti_s'])} s", "",
         "## Mechanism comparison (best coverage per segment count)", "",
         "| N | mechanism | designs with a window | best O1 | best O2 | best log width |", "|---|---|---|---|---|---|"]
    for k, v in r["mechanism_selection"]["by_segment_count"].items():
        L.append(f"| {k} | {v['mechanism']} | {v['designs_with_a_window']} | {v['best_O1']} | {v['best_O2']} | "
                 f"{g(v['best_log_width'])} |")
    L += ["", "## AIR operating window and altitude schedule", "",
          f"- window Φ = ρV ∈ [{g(w['Phi_lo_kg_m2_s'])}, {g(w['Phi_hi_kg_m2_s'])}] kg m⁻² s⁻¹ (ratio {g(w['ratio'])}; "
          f"{w['states_in_window']} of 196 states)", "",
          "| condition | admissible altitude nodes [km] |", "|---|---|"]
    for c, n in w["altitude_schedule"].items():
        L.append(f"| {c} | {', '.join(g(x) for x in n) if n else 'UNCOVERED (finding)'} |")
    L += ["", f"Uncovered registered conditions: {', '.join(w['uncovered_conditions']) or 'none'}.", "",
          "## Window end points", "",
          "| scenario | state | ṁ_del [kg/s] | ṁ_req [kg/s] | ratio | D_tot [mN] | P_comp [W] | pressure ratio |",
          "|---|---|---|---|---|---|---|---|"]
    for e in rec["window_operating_points"]["window_end_points_detail"]:
        L.append(f"| {e['scenario']} | `{e['state_id']}` | {g(e['mdot_delivered_kg_s'])} | {g(e['mdot_req_sustained_kg_s'])} | "
                 f"{g(e['flow_ratio'])} | {g(e['D_tot_N'] * 1e3)} | {g(e['P_compressor_el_W'])} | "
                 f"{g(e['pressure_ratio_P_set_over_inlet'])} |")
    s = r["feed_loop_stability"]
    L += ["", "## Feed-loop stability", "",
          f"Governed Python reference all S: {s['governed_python_reference_all_S']}; Rust R2 agreement {s['R2_rows_agree']} of "
          f"{s['rows']} rows.", "", "## Information (never gating)", ""]
    for k, v in r["information"].items():
        if isinstance(v, dict) and "Phi_lo_kg_m2_s" in v:
            L.append(f"- {k}: window [{g(v['Phi_lo_kg_m2_s'])}, {g(v['Phi_hi_kg_m2_s'])}], O1 {v['O1_conditions_covered']}, "
                     f"O2 {v['O2_nodes_admissible']}")
        else:
            L.append(f"- {k}: {json.dumps(v)[:300]}")
    L += ["", f"196-state verification view: {json.dumps(r['verification_set_196'])}", "",
          "## Resolution", "", f"- proposed: DBF-1.2 on DBF-1.1 (`{res['proposed_baseline']['dir']}`)",
          f"- P1 closure state: **{res['p1_closure_state']}**"]
    if res["mass_transfer_request"]:
        m = res["mass_transfer_request"]
        L.append(f"- mass-transfer request {m['id']}: {g(m['transfer_kg'])} kg above AL-02 ({g(m['allocation_kg'])} kg)")
    L += ["", "EM verification items:", ""] + [f"- {x}" for x in res["em_verification_items"]]
    return ("\n".join(L) + "\n").encode("utf-8")


def main(argv) -> int:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    res, md = build(argv[1])
    rb = (json.dumps(res, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    out = {OUT_JSON: rb, OUT_MD: md,
           OUT_STATE: (json.dumps(closure_state(res, rb), indent=1, ensure_ascii=False) + "\n").encode("utf-8")}
    if "--check" in argv:
        stale = [k for k, v in out.items() if (ROOT / k).read_bytes() != v]
        print("STALE: " + ", ".join(stale) if stale else "OK")
        return 1 if stale else 0
    for k, v in out.items():
        (ROOT / k).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / k).write_bytes(v)
        print(k, sha(v))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

"""Builder of the P7 thermal load inputs v2: v1 with the power-ledger-owned terms taken from the P6 power ledger
(lane L-POWER-ICD, docs/closure/power/power_ledger_v1.json). Same preregistration and harness (no method change).
The compressor stays the DBF-1 compressor (DBF1-IN-08 / ledger CP-WORST) until DCR-001 lands. Docs tooling only.
"""

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LEDGER = "docs/closure/power/power_ledger_v1.json"


def sha(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    with open(os.path.join(HERE, "thermal_load_inputs_v1.json")) as f:
        v = json.load(f)
    with open(os.path.join(ROOT, LEDGER)) as f:
        led = json.load(f)
    terms = {t["id"]: t for t in led["terms"]}
    p_nom = next(p for p in led["points"] if p["id"] == "P-NOM")
    lsha = sha(LEDGER)
    label = "FROM_P6_POWER_LEDGER_v1"

    def src(pointer, note):
        return {"path": LEDGER, "sha256": lsha, "pointer": pointer, "note": note}

    def term(group, key, value, pointer, note, ec, unc):
        v[group][key] = {"value": value, "units": v[group][key]["units"], "source": src(pointer, note),
                         "evidence_class": ec, "uncertainty": unc, "label": label}

    term("discharge", "P_d_hot_W", p_nom["P_d_max_W"]["rfp_1500_supremum"], "/points/0/P_d_max_W/rfp_1500_supremum",
         "flight discharge ceiling under the 1,500 W gate with the ICP at the 200 W forward anchor (DESIGN_ALLOCATION_NOT_PREDICTED)",
         "assumed", "allocation bound; the Hall envelope (P2) decides the actual P_d")
    term("ppu", "eta_d", terms["ETA-HD"]["low"], "/terms (ETA-HD low)", "ETA-HD 0.86-0.92, low end (most heat)", terms["ETA-HD"]["evidence_class"], "0.86-0.92")
    term("ppu", "eta_mag", terms["ETA-MAG"]["low"], "/terms (ETA-MAG low)", "ETA-MAG 0.6-0.85, low end", terms["ETA-MAG"]["evidence_class"], "0.6-0.85")
    term("ppu", "P_hk_out_W", terms["HK-LOAD"]["high"], "/terms (HK-LOAD high)", "HK-LOAD 12-30 W, high end", terms["HK-LOAD"]["evidence_class"], "12-30 W")
    term("ppu", "eta_hk", terms["ETA-HK"]["low"], "/terms (ETA-HK low)", "ETA-HK 0.7-0.85, low end", terms["ETA-HK"]["evidence_class"], "0.7-0.85")
    term("ppu", "P_valve_out_W", terms["VALVE-COIL"]["high"], "/terms (VALVE-COIL high)", "one energised atmospheric valve coil, hot", terms["VALVE-COIL"]["evidence_class"], "0.41-1.96 W")
    term("ppu", "eta_valve", terms["ETA-DRV"]["low"], "/terms (ETA-DRV low)", "ETA-DRV 0.8-0.9, low end", terms["ETA-DRV"]["evidence_class"], "0.8-0.9")
    term("icp", "eta_RF", terms["ETA-RFGEN"]["low"], "/terms (ETA-RFGEN low)", "ETA-RFGEN 0.6-0.92, low end (most generator heat)", terms["ETA-RFGEN"]["evidence_class"], "0.6-0.92")
    term("icp", "P_matching_DC_W", terms["RF-MATCH-ACT"]["value"], "/terms (RF-MATCH-ACT)", "adjustable match actuators / controller", terms["RF-MATCH-ACT"]["evidence_class"], "0-10 W")
    term("compressor", "P_el_max_W", terms["CP-WORST"]["value"], "/terms (CP-WORST)", "DBF-1 compressor; FLAGGED_FOR_UPDATE_FROM_DCR-001", terms["CP-WORST"]["evidence_class"], "PARAMETRIC_SENSITIVITY")
    term("compressor", "eta_drive", terms["ETA-CPD"]["value"], "/terms (ETA-CPD)", "CP-WORST is already the motor-drive electrical input (drive fed from the internal bus)", terms["ETA-CPD"]["evidence_class"], "-")
    v["id"] = "P7-THERMAL-LOAD-INPUTS-v2"
    v["version"] = 2
    v["supersedes"] = {"path": "docs/closure/thermal/thermal_load_inputs_v1.json", "sha256": sha("docs/closure/thermal/thermal_load_inputs_v1.json")}
    v["status"] = "power-ledger terms from the P6 power ledger v1 (L-POWER-ICD; conservative ends for heat); compressor = DBF-1 (DCR-001 pending); coils, fractions and the ICP partition unchanged from v1"
    out = os.path.join(HERE, "thermal_load_inputs_v2.json")
    with open(out, "wb") as f:
        f.write((json.dumps(v, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode())
    print(sha("docs/closure/thermal/thermal_load_inputs_v2.json"))


if __name__ == "__main__":
    main()

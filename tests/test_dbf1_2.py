"""DBF-1.2 baseline integrity (docs/baseline/DBF-1.2/; DCR-DBF1-001, A9.41 / A9.42 / A9.43)."""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs/baseline/DBF-1.2"


def _j(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def _sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def test_builder_check_is_current():
    r = subprocess.run([sys.executable, str(D / "build_dbf1_2.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_lock_matches_files_and_pins():
    lock = _j("docs/baseline/DBF-1.2/dbf1_2_lock_v1.json")
    for f, h in lock["files"].items():
        assert _sha(f"docs/baseline/DBF-1.2/{f}") == h, f
    for p, h in lock["pinned_sources"].items():
        assert _sha(p) == h, p


def test_parents_unchanged():
    assert _sha("docs/baseline/DBF-1/dbf1_lock_v1.json") == "517e0cf693712ec6d355c4b23791b9ae8626577fd338e3030563eb027e86b907"
    assert _sha("docs/baseline/DBF-1.1/dbf1_1_lock_v1.json") == "257e141ca252c3015b5bbd2fc953a1de688bc1606be36ebdf9fff8889307cfb8"
    for base, lockf in (("DBF-1", "dbf1_lock_v1.json"), ("DBF-1.1", "dbf1_1_lock_v1.json")):
        lock = _j(f"docs/baseline/{base}/{lockf}")
        for f, h in lock["files"].items():
            assert _sha(f"docs/baseline/{base}/{f}") == h, (base, f)


def test_status_semantics():
    d = _j("docs/baseline/DBF-1.2/dbf1_2_v1.json")
    assert d["status"] == "DBF-1.2 — RFP-CONFORMING PRELIMINARY DESIGN BASELINE / COMPLIANCE VERIFICATION ON EM/QM"
    for bad in d["status_semantics"]["never_label_as"]:
        assert bad.lower() not in d["status"].lower()


def test_mass_arithmetic_convention():
    m = _j("docs/baseline/DBF-1.2/dbf1_2_v1.json")["mass_rollup"]
    nonh = sum(m["lines_mev_kg"].values())
    assert math.isclose(nonh, m["nonharness_kg"], abs_tol=1e-9)
    assert math.isclose(m["harness_kg"], 0.05 / 0.95 * nonh, abs_tol=1e-9)
    assert math.isclose(m["nominal_dry_kg"], nonh + m["harness_kg"], abs_tol=1e-9)
    assert math.isclose(m["dry_10pct_kg"], 1.10 * m["nominal_dry_kg"], abs_tol=1e-9)
    assert math.isclose(m["wet_kg"], m["dry_10pct_kg"] + 2.0, abs_tol=1e-9)
    assert m["wet_kg"] < 40.0 and abs(m["wet_kg"] - 39.948) < 1e-3
    assert "MR-DCR001-01" in m["headroom_status"] and "not usable design margin" in m["headroom_status"]
    assert m["lines_mev_kg"]["AL-07 PPU"] == 5.46


def test_power_arithmetic_from_p6():
    d = _j("docs/baseline/DBF-1.2/dbf1_2_v1.json")["power_rollup"]
    p6 = _j("docs/closure/power/power_ledger_v1.json")
    pts = {p["id"]: p for p in p6["points"]}
    eta = pts["P-12"]["discharge_chain_eta"]
    assert eta == 0.850725
    for case in ("reference", "conservative"):
        a = d["air_12mN"][case]
        assert a["P_d_W"] == 650.0
        assert a["P_bus_W"] < 1350.0 and a["P_bus_W"] < 1500.0
    rft = {r["P_fwd_W"]: r["P_bus_icp_W"] for r in p6["rf_trade_line"]}
    nd = pts["P-XE"]["P_bus_non_discharge_W"]
    x = d["xe_25mN"]["1450W_design_ceiling_le"]
    assert math.isclose(x["nominal_ICP_P_d_max_W"], (1450 - nd) * eta, rel_tol=1e-12)
    assert math.isclose(x["RF_plus_100W_P_d_max_W"], (1450 - nd - (rft[300.0] - rft[200.0])) * eta, rel_tol=1e-12)
    assert round(x["nominal_ICP_P_d_max_W"], 1) == 876.1 and round(x["RF_plus_100W_P_d_max_W"], 1) == 747.5
    assert "NOT VALIDATED" in d["air_12mN_model_thrust_at_650W"]["label"]
    assert d["xe_25mN_parametric"]["label"].startswith("PARAMETRIC / NOT_VALIDATED")


def test_pressure_domain_classification_not_upgraded():
    d = _j("docs/baseline/DBF-1.2/dbf1_2_v1.json")
    c = next(i for i in d["items"] if i["id"] == "DBF12-CMP-02")["value"]["rows"]
    assert [r["classification"] for r in c] == ["ADMITTED_FREE_MOLECULAR"] * 5 + ["EM_VERIFICATION_RISK_CROSSES_0.1_Pa", "EM_VERIFICATION_RISK_TRANSITIONAL"]


def test_dcr_register_and_trace_consistency():
    d = _j("docs/baseline/DBF-1.2/dbf1_2_v1.json")
    reg = _j(d["lineage"]["dcr_register"]["path"])
    assert [x["status"] for x in reg["dcrs"] if x["id"] == "DCR-DBF1-001"] == ["APPROVED_OWNER_WITH_MASS_RISK"]
    ids = {i["id"] for i in d["items"]}
    rvm = {r["id"] for r in _j("docs/requirements/rvm_a9/rvm_a9_v1.json")["rows"]}
    for t in _j("docs/baseline/DBF-1.2/dbf1_2_requirement_trace_v1.json")["trace"]:
        assert set(t["dbf1_2_items"]) <= ids
        assert all(r in rvm for r in t["rvm"].split(" / "))
    risks = {r["id"] for r in _j("docs/baseline/DBF-1.2/dbf1_2_risk_register_v1.json")["risks"]}
    assert "MR-DCR001-01" in risks and len(risks) >= 16

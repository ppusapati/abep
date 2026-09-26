"""Tests for the non-gating E x B physics forensics (scripts/forensics/p5_n2_v1_exb_physics.py).

Checks: the recomputed outlet V_a of N2+ and N+ equal the official O5 `exb_diagnostic` of the frozen scores file within
rounding, the ordering flags and count equal the official ones, the official statuses are read (never recomputed), and the
generated JSON / tables are deterministic and match the committed files.
"""
import importlib.util, json, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "forensics", "p5_n2_v1_exb_physics.py")
spec = importlib.util.spec_from_file_location("p5_n2_v1_exb_physics", SCRIPT)
exb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exb)

OUT, ROWS = exb.build()
SCORES = json.load(open(exb.SCORES))


def test_recomputed_va_match_official_exb_diagnostic():
    off = SCORES["exb_diagnostic"]
    assert len(ROWS) == len(off) == 648
    assert {r["key"] for r in ROWS} == set(off)
    for r in ROWS:
        o = off[r["key"]]
        assert abs(r["Va_N2p"] - o["N2+"]["Va_model_V"]) <= 1e-9 * max(1.0, abs(o["N2+"]["Va_model_V"]))
        assert abs(r["Va_Np"] - o["N+"]["Va_model_V"]) <= 1e-9 * max(1.0, abs(o["N+"]["Va_model_V"]))
        assert abs(r["ff_Np"] - o["N+"]["outlet_flux_fraction"]) <= 1e-12
        assert abs(r["dVa_Np"] - o["N+"]["dVa_V"]) <= 1e-9 * max(1.0, abs(o["N+"]["dVa_V"]))
    rep = OUT["reproduction_of_official_O5"]
    assert rep["keys_identical"] and rep["ordering_flag_mismatches"] == 0
    assert max(rep["max_abs_dev_Va_V"].values()) <= 1e-9


def test_ordering_count_equals_official():
    off = SCORES["exb_diagnostic"]
    official = sum(1 for v in off.values() if v["ordering_Nplus_above_N2plus"])
    assert sum(r["ordering"] for r in ROWS) == official
    assert OUT["reproduction_of_official_O5"]["ordering_true_recomputed"] == official
    assert OUT["reproduction_of_official_O5"]["ordering_true_official"] == official
    for r in ROWS:
        assert r["ordering"] == off[r["key"]]["ordering_Nplus_above_N2plus"]


def test_statuses_are_read_from_the_scores_file():
    st = {}
    for r in SCORES["runs"]:
        st[(r["key"], r["reading"])] = r["status"]
    for r in ROWS:
        assert r["status_A"] == st[(r["key"], "A")] and r["status_B"] == st[(r["key"], "B")]
    assert OUT["official_status_counts"] == SCORES["status_counts"]


def test_json_and_tables_deterministic_and_committed():
    out2, _ = exb.build()
    js1, js2 = exb.serialize(OUT), exb.serialize(out2)
    assert js1 == js2
    assert exb.tables_md(OUT) == exb.tables_md(out2)
    json.loads(js1)                                   # valid JSON
    assert open(exb.OUT_JSON).read() == js1
    assert open(exb.OUT_MD).read() == exb.tables_md(OUT)


def test_reading_consistency_of_official_statuses():
    rc = OUT["official_reading_consistency"]
    assert rc["n_keys_ood_differs_between_readings"] == 0
    assert rc["n_not_ood_keys"] == sum(r["domain_class"] != "OUT_OF_DOMAIN" for r in ROWS)
    assert rc["n_mixed_reading_keys"] == len(rc["mixed_reading_keys"])
    for m in rc["mixed_reading_keys"]:
        assert {m["status_A"], m["status_B"]} == {"PASS", "FAIL_VALIDATION"}
    assert rc["ordering_count_in_mixed_reading_keys"] == 0


def test_fragment_ke_is_labelled_proxy_not_di_nplus():
    f = OUT["fragment_kinetic_energy_context"]
    assert "1765 (1975)" in f["source"] and "N^2+" in f["ion_measured"]
    assert f["DI_Nplus_fragment_KE_eV"].startswith("TBD")
    assert "max_peak_over_min_measured_D" not in f and "proxy_max_peak_over_min_measured_D" in f

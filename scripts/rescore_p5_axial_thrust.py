"""P5-Xe thrust-observable reconciliation v2 (pre-registered 2026-09-25, docs/HISTORY.md): rescoring of the EXISTING
ScaledGaussianBohm and 3-node MultiLogBohm runs with a divergence-consistent axial thrust. No simulation input changes
(transport, B(z), geometry, ingestion, wall physics, plasma solution are untouched).

    T_axial,pred = T_1D * f(point),   f = axial thrust factor from Brabston's measured beam efficiency

Two readings of the paper are carried and neither is chosen by fit quality (brabston_fig8_fig9_xenon.json):
  A: f = sqrt(Psi_b) with Psi_b as plotted in Fig. 9 (literal Eq. 4)            -> f ~ 0.78
  B: f = sqrt(eta_T,component(Fig. 8) / (eta_E Phi_P)(Fig. 9)) (self-consistent)  -> f ~ 0.88-0.91
Modes: vacuum = PRIMARY (ingestion OFF runs vs I_d,corr (Eq. 14) and T_corr (published));
       facility = consistency check (existing ingestion-ON runs vs raw I_d and raw thrust; caveat: the ingested flow enters
       at the anode, so it does not carry Brabston's zeta_en < 1 thrust discount).
Thrust uncertainty: sigma_T = sqrt(4.9 mN^2 + (T_axial,pred * rel_err(f))^2), rel_err(f) = sigma_Psi / (2 Psi) from Fig. 9.
Leave-one-out selection (both pre-registered): (i) all grid points; (ii) only points quiet (I_d RMS < 50 %, internal
diagnostic) at the calibration points. Objective J = mean over calibration points of (dI/I)^2 + (dT/T)^2.
PASS for a (family, hypothesis, reading, mode, selection) requires, in every one of the three rounds:
  held-out |dI_d| <= 15 %, held-out |dT| <= 2 sigma_T, RMS < 50 % at all three points, defensible parameters
  (SGB a <= 1/16; MLB all c <= 1/16). "Passes except defensibility" is reported separately.
A verdict is stated only if it holds under both readings A and B; otherwise it is reported as reading-dependent.
Usage: python scripts/rescore_p5_axial_thrust.py
"""
import collections, csv, json, math, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
IDN = os.path.join(ROOT, "hallthruster_bridge", "identification")
P = ["Xe1", "Xe2", "Xe3"]
SIGMA_STAND_MN = 4.9
ID_TOL, T_SIG_TOL, RMS_QUIET = 0.15, 2.0, 0.5
BOHM = 1 / 16
FAMILIES = {"sgb": "p5_xe_identification_sgb_v1", "mlb": "p5_xe_identification_mlb_v1"}


def fnum(x):
    return float(x) if x not in ("", None) else None


def defensible(family, combo):
    if family == "sgb":                     # a=1/N_...
        return 1 / float(combo.split("_")[0].split("=1/")[1]) <= BOHM + 1e-12
    return all(1 / float(part.split("=1/")[1]) <= BOHM + 1e-12 for part in combo.split("_c_") if "=1/" in part)


def load(path):
    by = collections.defaultdict(dict)
    for r in csv.DictReader(open(path)):
        if r["retcode"] == "success":
            by[(r["hypothesis"], r["combo"])][r["point"]] = r
    return by


def score(by, factors, rel):
    """Per (hyp, combo, point): dI, dT (axial-corrected, relative), dT/sigma_T, rms."""
    out = {}
    for key, d in by.items():
        if any(p not in d for p in P):
            continue
        e = {}
        for p in P:
            r = d[p]
            T = fnum(r["T_mN"]) * factors[p]; Tt = fnum(r["T_target_mN"])
            sig = math.hypot(SIGMA_STAND_MN, T * rel[p])
            e[p] = {"dI": fnum(r["Id_err_rel"]), "dT": (T - Tt) / Tt, "dTs": (T - Tt) / sig, "rms": fnum(r["Id_rms_rel"])}
        out[key] = e
    return out


def loo(sc, family, h, quiet_only):
    rounds = []
    for hold in P:
        cal = [p for p in P if p != hold]
        best = None
        for (hh, c), e in sc.items():
            if hh != h:
                continue
            if quiet_only and any(e[p]["rms"] >= RMS_QUIET for p in cal):
                continue
            J = sum(e[p]["dI"] ** 2 + e[p]["dT"] ** 2 for p in cal) / len(cal)
            if best is None or J < best[0]:
                best = (J, c)
        if best is None:
            rounds.append({"holdout": hold, "combo": None, "pass": False, "pass_except_defensible": False})
            continue
        J, c = best; e = sc[(h, c)]
        quiet_all = all(e[p]["rms"] < RMS_QUIET for p in P)
        ok_pred = abs(e[hold]["dI"]) <= ID_TOL and abs(e[hold]["dTs"]) <= T_SIG_TOL
        dfn = defensible(family, c)
        rounds.append({"holdout": hold, "combo": c, "J": J, "hold_dI": e[hold]["dI"], "hold_dT_sigma": e[hold]["dTs"],
                       "rms": [e[p]["rms"] for p in P], "quiet_all": quiet_all, "defensible": dfn,
                       "pass_except_defensible": ok_pred and quiet_all, "pass": ok_pred and quiet_all and dfn})
    return rounds


def main():
    fac = json.load(open(os.path.join(IDN, "brabston_fig8_fig9_xenon.json")))["points"]
    rel = {p: fac[p]["axial_factor_rel_err"] for p in P}
    results = {}
    for family, pre in FAMILIES.items():
        for mode, fn in (("vacuum", f"{pre}_vacuum_runs.csv"), ("facility", f"{pre}_runs.csv")):
            path = os.path.join(IDN, fn)
            if not os.path.exists(path):
                print(f"[{family}/{mode}] missing {fn}"); continue
            by = load(path)
            hyps = sorted({h for h, _ in by})
            for reading in ("A", "B"):
                factors = {p: fac[p][f"axial_factor_{reading}"] for p in P}
                sc = score(by, factors, rel)
                for sel in ("all", "quiet"):
                    for h in hyps:
                        rs = loo(sc, family, h, sel == "quiet")
                        results[f"{family}|{mode}|{reading}|{sel}|{h}"] = {
                            "rounds": rs, "pass": all(r["pass"] for r in rs),
                            "pass_except_defensible": all(r["pass_except_defensible"] for r in rs),
                            "same_combo": len({r["combo"] for r in rs}) == 1}
    json.dump({"thresholds": {"Id_tol": ID_TOL, "T_sigma_tol": T_SIG_TOL, "rms_quiet": RMS_QUIET, "bohm": BOHM},
               "results": results}, open(os.path.join(IDN, "p5_xe_axial_thrust_v2_rescore.json"), "w"), indent=1)
    print(f"{'family|mode|reading|selection|hyp':38s} pass  pass-ex-def  same  held-out dI% / dT(sigma) / rms-max% per round")
    for k, v in results.items():
        rr = "; ".join("—" if r["combo"] is None else
                       f"{100 * r['hold_dI']:+.0f}/{r['hold_dT_sigma']:+.1f}/{100 * max(r['rms']):.0f}" for r in v["rounds"])
        print(f"{k:38s} {str(v['pass']):5s} {str(v['pass_except_defensible']):12s} {str(v['same_combo']):5s} {rr}")


if __name__ == "__main__":
    main()

"""DCR-DBF1-001 preliminary sizing, correction pass v2 (owner instruction 2026-10-10). Deterministic, < 1 s.
Changes vs v1: all-state window uses orbit-MIN flux (flow constraint) and orbit-MAX flux (drag constraint); nominal window
uses orbit-median for both; two Hall planning cases (conservative / reference); compressor numbers split into design
values vs proposal targets / allowances; 'active retention control' terminology; conservative vs target mass.
PROPOSAL-LEVEL / PARAMETRIC / NOT_VALIDATED. v1 is kept as history."""
import json, math, re, statistics as st, hashlib, collections
from pathlib import Path
R = Path(__file__).resolve().parents[4]
A4 = R / "docs/rust_migration/new_physics/NP-HALL-PARAMETRIC-ENVELOPE/conservation_bounds_v1.json"
k_B, amu, e = 1.380649e-23, 1.66053906660e-27, 1.602176634e-19
a4 = json.loads(A4.read_text())
grid = collections.defaultdict(list); Us = []
for s in a4["states"]:
    m = re.match(r"ds2:([A-Z_]+):alt(\d+):", s["state_id"])
    grid[(m.group(1), int(m.group(2)))].append(s["Phi_adm_kg_m2_s"]); Us.append(0.5 * (s["U_m_s"]["V_orb_max"] + s["U_m_s"]["V_orb_min"]))
COND = ["ECSS_LT_LOW", "ECSS_LT_MODERATE", "ECSS_LT_HIGH", "ECSS_ST_HIGH"]; ALT = [180, 195, 215, 230]
U = st.median(Us); PHI_DENSEST = max(max(v) for v in grid.values())
K_D = 17.6e-3 / (PHI_DENSEST * U * 0.25)                     # registered F1 TPMC intake-face drag of the DBF-1 intake
# design values carried from v1 (intake / retention design; unchanged)
A_FACE, LD, W_FWD, ETA_FILT, ETA_DEL, S_OVER_CB, H_STAGE, HUB, VTIP, TGAS, MMIX = 0.70, 20.0, 0.72, 0.90, 0.98, 2.0, 0.30, 0.40, 300.0, 300.0, 24.0
W_REV = 1 / (1 + 0.75 * LD); ETA_RET = S_OVER_CB / (1 + S_OVER_CB); ETA_PATH = W_FWD * ETA_FILT * ETA_RET * ETA_DEL
q4 = math.sqrt(8 * k_B * TGAS / (math.pi * MMIX * amu)) / 4; kTm = k_B * TGAS / (MMIX * amu)
C_BACK = A_FACE * q4 * W_REV; S_IN = S_OVER_CB * C_BACK
A_ROT = S_IN / (H_STAGE * q4); D_ROT = math.sqrt(A_ROT / (math.pi / 4 * (1 - HUB ** 2))); RPM = VTIP / (math.pi * D_ROT) * 60
# power ledger basis (P6): non-discharge bus 428 W incl. old compressor 9.76 W; discharge chain 0.90 x 0.95
P_ND_OLD, CHAIN = 428.0, 0.90 * 0.95
CASES = {"conservative": dict(v_eff=22.0e3, eta_T=0.22), "reference": dict(v_eff=26.8e3, eta_T=0.27)}
COMP_P = {"target": 25.0, "allowance": 60.0}                  # W (spin-up transient ~100 W, scheduled)
HOST_REF = 0.50

def prof(c, f):
    pts = [(h, f(grid[(c, h)])) for h in ALT]
    def at(h):
        for (h0, y0), (h1, y1) in zip(pts, pts[1:]):
            if h0 <= h <= h1: return y0 * (y1 / y0) ** ((h - h0) / (h1 - h0))
    return at
P = {k: {c: prof(c, f) for c in COND} for k, f in (("min", min), ("med", st.median), ("max", max))}
HS = [h / 2 for h in range(360, 461)]

def case(v_eff, eta_T):
    v, etaT = v_eff, eta_T
    TD = ETA_PATH * v / (K_D * U)
    host_cap = max(0.0, 2 * (TD - 1) * K_D * A_FACE)            # host C_D*A the flow-limited thrust margin can carry
    m12 = 12e-3 / v
    Pd_ceiling = lambda ND: (1500 - ND) * CHAIN
    ND_t = P_ND_OLD + (COMP_P["target"] - 9.76) / 0.85; ND_a = P_ND_OLD + (COMP_P["allowance"] - 11.13) / 0.85
    Pd12 = 12e-3 * v / (2 * etaT)
    v25 = 2 * etaT * Pd_ceiling(ND_a) / 25e-3                   # exhaust velocity that makes 25 mN at the discharge ceiling
    m25 = 25e-3 / v25
    phi_lo = m12 / (ETA_PATH * A_FACE)
    def phi_hi(host): return 25e-3 / (U * (K_D * A_FACE + 0.5 * host))
    def windows(host, lo_key, hi_key):
        out = {}
        for c in COND:
            ok = [h for h in HS if P[lo_key][c](h) >= phi_lo and P[hi_key][c](h) <= phi_hi(host)] if host <= host_cap + 1e-12 else []
            out[c] = [min(ok), max(ok)] if ok else None
        return out
    def max_host(c, lo_key, hi_key):
        best = None
        for i in range(0, 301):
            hst = i * 0.01
            if hst > host_cap: break
            ok = [h for h in HS if P[lo_key][c](h) >= phi_lo and P[hi_key][c](h) <= phi_hi(hst)]
            if ok: best = (hst, [min(ok), max(ok)])
        return best
    A_req = m12 / (ETA_PATH * P["min"]["ECSS_LT_LOW"](180) / 1.10)   # aperture for 12 mN at the thinnest scheduled state, 10 % margin
    return dict(v_eff=v, eta_T=etaT, flow_12_mg_s=m12 * 1e6, flow_25_mg_s=m25 * 1e6, v_eff_25_mode=v25,
                flow_lower_bound_12_mg_s=12e-3 / math.sqrt(2 * e * 350 / (16 * amu)) * 1e6,
                T_over_D_intake=TD, host_CDA_cap_m2=host_cap, required_effective_capture_m2=m12 / (P["min"]["ECSS_LT_LOW"](180) / 1.10),
                required_aperture_m2=A_req, phi_lo=phi_lo, phi_hi_host_ref=phi_hi(HOST_REF), phi_hi_no_host=phi_hi(0.0),
                Pd_12_W=Pd12, bus_12_W=Pd12 / CHAIN + ND_t, Pd_25_W=Pd_ceiling(ND_a), bus_25_W=1500.0,
                window_all_state_host_ref=windows(HOST_REF, "min", "max"), window_nominal_host_ref=windows(HOST_REF, "med", "med"),
                window_all_state_no_host=windows(0.0, "min", "max"),
                max_host_all_state={c: max_host(c, "min", "max") for c in COND},
                max_host_nominal={c: max_host(c, "med", "med") for c in COND},
                flux_margin_LT_LOW_180=P["min"]["ECSS_LT_LOW"](180) / phi_lo - 1)
res = {k: case(**v) for k, v in CASES.items()}
# drag at each scheduled altitude (orbit max) -- exposed face; retention control does not change it
drag = {c: {h: dict(min=K_D * P["min"][c](h) * U * A_FACE * 1e3, max=K_D * P["max"][c](h) * U * A_FACE * 1e3) for h in ALT} for c in COND}

# compressor: design values vs proposal targets
comp_design = dict(rotor_D_m=D_ROT, hub_ratio=HUB, front_stages=6, finishing_stages="1 turbo-drag", rpm_front=RPM, tip_speed_m_s=VTIP,
                   required_inlet_speed_m3_s=S_IN, intake_back_conductance_m3_s=C_BACK,
                   inlet_pressure_Pa={k: [res[k]["flow_12_mg_s"] * 1e-6 * kTm / S_IN, res[k]["flow_25_mg_s"] * 1e-6 * kTm / S_IN] for k in res},
                   front_exit_Pa=2.0, plenum_Pa=20.0,
                   target_pressure_ratio={k: [20.0 / (res[k]["flow_25_mg_s"] * 1e-6 * kTm / S_IN), 20.0 / (res[k]["flow_12_mg_s"] * 1e-6 * kTm / S_IN)] for k in res},
                   finishing_speed_m3_s={k: res[k]["flow_25_mg_s"] * 1e-6 * kTm / 2.0 for k in res})
comp_targets = dict(mass_component_estimate_kg=7.4, mass_target_kg=6.0, mass_conservative_allowance_kg=9.0,
                    power_target_W=COMP_P["target"], power_conservative_allowance_W=COMP_P["allowance"], spin_up_transient_W=100.0,
                    status="PROPOSAL TARGET / ESTIMATE (no component-level structural / motor / bearing roll-up; no flight analog) -- not a CBE")

# mass: conservative (current defensible allowances) vs target (after identified design optimisation)
NONH_OLD, AL01, AL02, AL03, AL07, AL08 = 33.1196, 3.5, 5.5, 1.0, 6.0, 5.9148
def roll(intake, comp, plen, ppu, xe):
    nh = NONH_OLD - AL01 - AL02 - AL03 - AL07 - AL08 + intake + comp + plen + ppu + xe
    dry = nh / 0.95; return dict(intake=intake, compressor=comp, plenum_feed=plen, ppu=ppu, xe_hardware=xe, nonharness=nh, harness=dry - nh,
                                 nominal_dry=dry, dry_10pct=dry * 1.1, wet_2kg=dry * 1.1 + 2, margin_to_40=40 - (dry * 1.1 + 2), over_34=dry - 34)
mass = dict(conservative=roll(4.5, 9.0, 1.3, AL07, AL08), target=roll(3.8, 6.0, 1.1, 5.3, 3.5),
            actions={"MCA-02 Xe hardware single-branch re-base / 2 kg tank": "5.91 -> 3.5 kg TARGET (not supported by a component roll-up)",
                     "MCA-01 cathodeless PPU requote": "6.0 -> 5.3 kg TARGET", "compressor lightweighting (CFRP blisks, integrated drive)": "9.0 allowance -> 6.0 kg TARGET",
                     "intake": "4.5 allowance -> 3.8 kg estimate", "plenum/feed": "1.3 allowance -> 1.1 kg estimate"})
out = dict(label="PROPOSAL-LEVEL PRELIMINARY DESIGN v2 / PARAMETRIC / NOT_VALIDATED", supersedes="dcr001_preliminary_design_v1.json (kept)",
           inputs=dict(A4_sha256=hashlib.sha256(A4.read_bytes()).hexdigest(), U_m_s=U, K_D_intake=K_D),
           intake=dict(A_face_m2=A_FACE, LD=LD, W_fwd=W_FWD, eta_filter=ETA_FILT, eta_retention=ETA_RET, eta_path=ETA_PATH,
                       delivered_flow_control="active retention control (front-rotor speed) + plenum relief/bypass; does NOT change exposed frontal drag",
                       drag_mN_by_condition_alt=drag),
           cases=res, compressor_design_values=comp_design, compressor_targets=comp_targets, mass=mass)
Path(__file__).with_name("dcr001_preliminary_design_v2.json").write_text(json.dumps(out, indent=1, default=str) + "\n")

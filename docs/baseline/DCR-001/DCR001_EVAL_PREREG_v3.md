# DCR-001 evaluation method — amendment v3 (variable effective capture, flux window, altitude schedule)

`dcr001_eval_prereg_v3.json` is authoritative; this page restates it. Status
**PREREGISTERED_AMENDMENT_BEFORE_WINDOW_EVALUATION**, hash lock `dcr001_eval_prereg_lock_v3.json`, committed alone before any
window, modulated operating point, altitude schedule or ranking is computed. Authority: owner decision A9.39 items 2 and 3.
v1 and v2 stay as history; v3 replaces their fixed-geometry all-states admissibility, selection and non-closure rules.

## What changes

The sizing requirement is no longer "close all 196 states (x46 flux) at one fixed geometry". It is an AIR operating
free-stream-flux window [Phi_lo, Phi_hi] over which one hardware configuration, with modulation, closes, and an altitude
schedule inside 180–230 km per registered solar / atmospheric condition. The 196-state set stays the conservative
verification set.

## Mechanism

| id | mechanism | model | status |
|---|---|---|---|
| VC-0 | fixed aperture | F1 x A (admitted) | reference |
| VC-1 | segmented frontal shutter, N = 2 / 4 / 8 equal segments, A_eff = j A_max / N | open part F1 x A_eff (F1-02); closed part drag bound 4.1 q (specular normal plate) | evaluated |
| VC-2 | bypass / spillage | not admitted | not evaluated |
| VC-3 | variable throat / conductance | not admitted | not evaluated |
| VC-4 | face vanes / louvres | = VC-1 | equivalent |

Selection: complexity (N) ranks after the coverage objective, so the simplest candidate reaching the best coverage wins.

## Design space DS-DCR001-W

A_max in the F1 frontal grid {0.25 … 1.5} m^2; N in {1, 2, 4, 8}; the 8 F1 (L/d, phi) nodes; 4 filters; F3 compressors
of C_mass (mass-relaxed set only under the mass-transfer rule); V, P_set, controller as v1. The chain is evaluated once per
distinct A_eff (27 values).

## Operating point (per design, state, scenario)

Smallest j with: steady chain in domain (v1 C-DOMAIN); D_tot = d_F1 A_eff + 4.1 q (A_max − A_eff) + q (C_D A)_host <= 25 mN
((C_D A)_host = 0.22106 m^2, IR-HOST-DRAG-01); delivered flow >= K-MDOT-REQ(max(12 mN, D_tot), P_d,max,1350(P_comp) + q_max A_eff)
(P6 ceiling at the 1,350 W target, 0.9 W per compressor W); P_comp <= 231.33 W (P6 headroom); compressor mass <= 5.5 kg.
A state is served if all 10 scenarios have an operating point. 25 mN capability: the same with K-MDOT-REQ(25 mN,
P_d,max,1500 + q_max A_eff), existence per scenario inside the window.

## Window and schedule

Window = the best admissible run of consecutive served states in flux order (Phi = rho V). Condition = ECSS scenario;
altitude node (c, h) admissible if all its states lie in the window; a condition with no node is UNCOVERED (finding).

## Ranking

O1 conditions covered; robust before conditional (lazy, 8 v1 corners, shutter re-chosen per corner); O2 nodes; N; window
width; worst sustained-flow ratio; compressor mass; A_max; P_set; drag; power; V; controller; id. Stability: Rust screen per
(V, controller), cap 200; governed Python reference with Rust R2 agreement on the selected design.

## Information (never gating)

Realistic planning flow T^2 / (2 eta_a P_d) with eta_a = 0.20 [0.10, 0.30] (assumed, level 7; EM verification item); V_d
bound; host-drag sensitivity (0, 1.1 m^2); capture efficiency; composition; the 196-state verification view; intake /
shutter mass to the AL-01 roll-up.

## Closure-state mapping

O1 = 4 robust: FROZEN FOR EM. O1 = 4 conditional: FROZEN FOR EM with the coefficient condition. 1 <= O1 < 4: FROZEN FOR EM
with the uncovered conditions as a finding. O1 = 0: DCR REQUIRED.

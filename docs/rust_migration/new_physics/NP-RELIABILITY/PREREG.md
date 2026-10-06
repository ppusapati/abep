# NP-RELIABILITY preregistration v1

Status **PREREGISTERED_NOT_IMPLEMENTED** (lifecycle PREREG_MODEL, validation NOT_VALIDATED). Work package SC-WP-08,
wave W10. `prereg_v1.json` is authoritative; this page restates it.

## Why new physics

The SC-WP-08 audit (`docs/rust_migration/audits/SC-WP-08/reliability_audit_v1.json`) found that
`abep_sim/life.py::reliability`, `magnet_life` and `compressor_life` have no active consumer and carry unsourced
parameters (electronics rate 2.0e-6 /h, Weibull beta 3, eta from class-H lives), thresholds inside raw physics and the
`R_26000h` legacy key. They are not extracted. The plan then makes the applicable reliability quantities a
preregistered NEW_PHYSICS element.

## Model

* Items: registered RBD items of `hall_icp_neutralizer` (AS-03). No C1 item; `hall_c1_reference` is refused.
* E-01 constant hazard `R = exp(-lambda t)`; E-02 Weibull `R = exp(-(t / eta)^beta)`; E-03 independent modes multiply;
  E-04 SERIES / ACTIVE_PARALLEL / K_OF_N blocks; E-05 operating time from a registered mission-profile record (no default
  duty); E-06 bounds at parameter-box corners (exact by monotonicity).
* Every parameter is an evidence record with source, uncertainty and domain (EI-01). Nothing is defaulted or invented.
  Hall-erosion-derived eta needs an admitted Hall map with `wall_life_trustworthy`: NOT_EVALUATED while the credible
  set is EMPTY. Anode / collector material OPEN: INCOMPLETE_EVIDENCE. AO items need coupon evidence.
* Outputs: raw R, F, bounds, status, limiting-item ordering. No threshold, PASS / FAIL, SPF label, 15,000 h or 26,280 h
  constant, and never `R_26000h`.

## Verification (software admission, not validation)

AL-01..AL-07 closed forms, CONS-R1..R3, fail-closed tests FT-01..FT-06, DET-01. ADMITTED iff all pass.

## Gates

No Rust code before this commit (IG-01). The SC-WP-08 lane only preregisters (IG-02). Open owner questions: the flight
RBD (OQ-NPR-01) and the admissible electronics failure-rate basis (OQ-NPR-02).

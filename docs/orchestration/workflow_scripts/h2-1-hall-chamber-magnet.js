export const meta = {
  name: 'h2-h2-1-hall-chamber-magnet',
  description: 'A7 hardware wave H2: fo_h2_1_hall_chamber_magnet (design/preliminary sizing, not architecture selection); three-lens verification (evidence, rules, engineering), up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'isolated worktree' },
    { title: 'Verify', detail: 'evidence + rules + engineering lenses, independent' },
    { title: 'Fix', detail: 'repair rounds (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "8ea7e4bc882d39bb0bce61308e7a1f5b8c0ecd2e", "lanes": [{"key": "H2_1", "title": "fo_h2_1_hall_chamber_magnet", "slug": "h2_1_hall_chamber_magnet", "lenses": ["evidence", "rules", "engineering"], "allowed": ["docs/hardware/h2/h2_1_hall_chamber_magnet/**", "tests/test_h2_1_hall_chamber_magnet.py"], "prompt": "Registered follow-on fo_h2_1_hall_chamber_magnet (trigger T_H2_1_HALL_CHAMBER_MAGNET, owner addendum A7). Deliverable dir docs/hardware/h2/h2_1_hall_chamber_magnet/ (JSON + .md + deterministic builder + tests/test_h2_1_hall_chamber_magnet.py). H2-1 HALL CHAMBER + MAGNETIC CIRCUIT preliminary sizing for H-1 / MC-1 (extended-channel per A5). Deliver: (1) channel envelope: outer/inner diameter, channel width, channel length (extended), anode position, exit plane, as RANGES bounded by (i) the A5 thrust (12-25 mN requirement, 15-22 mN allocation) and power (<= 1.30-1.35 kW allocation) targets through PUBLISHED Hall scaling relations and analog devices in docs/architecture_comparison/scaling/ and hall_reference/ (label analog/derived; state the scaling law, its source and applicability limits for N2/O2 vs Xe), (ii) the delivered-flow region (<= ~3.2 mg/s atmospheric, feed_state_closure) and the neutral-density/residence-time argument for extending the channel (cite), (iii) ECHT (86 mm long, 10 mm wide, 100 mm OD) as a published analog, never as our design; (2) magnetic topology options (inner/outer coils, trim coil, pole pieces; magnetically shielded vs unshielded as an option with its wall-life consequence per docs/evidence/wall_life and the AO lifetime register) with a PRELIMINARY choice and why; (3) B_r(z) TARGET ENVELOPE (peak B_r range at/near exit, gradient, zero-field/anode region) from published analog practice with sources - a design target envelope, not a transport optimization; (4) coil design: required ampere-turns for the peak target through the pole gap (magnetic-circuit reluctance estimate; state the method and its accuracy limits; flag that FEMM/3-D magnetostatic analysis is the H4/H2-follow-up), turns, wire gauge, current, winding envelope, I^2R at hot resistance, coil temperature class; (5) magnetic materials: candidate core/pole material with saturation flux density and Curie/maximum-use temperature cited, flux-density margin in the poles/core, and consequences of O/O2 exposure; (6) coil power and heat to H2-4 and H2-5 (interface_demands), mounting datums and the HALL_INLET_Z0 plane relation to the pre-ionizer module slot (permitted magnetic disturbance from the pre-ionizer ICD, PENDING), field at the cathode location to H2-2; (7) build on docs/experiments/magnet_coil/ (magnet coil qualification) and abep_sim/magnet_power.py / sizing.py read-only if they help (check they are not superseded 0-D Hall physics before use). Do NOT optimize transport physics; no performance prediction."}]}
const BASE = ARGS_EMBEDDED.base
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const COMMON = `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep; primary checkout /home/user/abep). You run in an ISOLATED git worktree created for you (your current working directory); do all edits there. FIRST run: git reset --hard ${BASE} (the worktree is created from main, which lacks the governance and decision files) and confirm with: git rev-parse HEAD. Base commit: ${BASE}.

CONTEXT (read CLAUDE.md in your worktree first):
- RFP envelope (DRDO TDF, CLAUDE.md): 180-230 km, 12-25 mN, < 1.5 kW, < 40 kg, 26,000 h mission, > 15,000 h firing, Hall preferred, air + Xe.
- OWNER DECISIONS YOU WORK UNDER (read all three first; cite them by path AND sha256, they are immutable): A5 docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A5_proposal_reference_architecture.json (Proposal Reference Architecture / Phase-1 Baseline: dual-feed extended-channel Hall, atmospheric primary feed, Xe only for ignition + shielded Xe-fed LaB6 cathode + time-limited contingency, RF pre-ionizer interface reserved (not baseline flight hardware), ECR alternate; the 16 baseline subsystems; allocations 15-22 mN, <= 1.30-1.35 kW, <= 34-36 kg, >= 18,000 h design target; architecture-closing risks 1-4), A6 docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A6_a5_followon_authorization.json (not_authorized list; execution-order clarification) and A7 docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A7_execution_model.json (execution model: YOUR LANE IS AN H2 HARDWARE DESIGN / PRELIMINARY-SIZING LANE, NOT AN ARCHITECTURE-SELECTION LANE; the only architecture-changing blockers are (1) Hall-only sustainment at the actual atmospheric feed state, (2) incremental RF/ECR benefit after full bus-power accounting, (3) Xe/cathode closure; everything else vetoes the architecture ONLY via an explicitly evidenced hard incompatibility). The G0 baseline is docs/decisions/verification/A5_BASELINE_VERIFICATION.json. Bundle 1 stays NO_BASELINE_YET; the credible Hall set is EMPTY; A5 numbers are ALLOCATIONS or REQUIREMENTS, never predictions.
- H-1 IS THE FLIGHT-REPRESENTATIVE TEST ARTICLE: the existing hardware definition docs/experiments/hardware/hardware_requirements_v1.json (+ HARDWARE_DEFINITION.md; status DRAFT_PENDING_OWNER) defines configuration items H-1 (Hall accelerator), MC-1 (common magnetic circuit), C-1 (cathode), FS-C (common feed system), PS-C (common electrical supplies), SVC-1 (service-line bundle), PIM-0 / PIM-RF / PIM-ECR (pre-ionizer modules), DIV-1 (option) and interface planes IP-UP, IP-DN, HALL_INLET_Z0. Build ON these ids (never rename or duplicate them) and state for every design item whether it is FLIGHT-REPRESENTATIVE, H-1 TEST-ARTICLE-ONLY, or GROUND/FACILITY-ONLY.
- NO PERFORMANCE PREDICTION: never predict thrust, efficiency, discharge current or plasma state from any Hall transport closure (none is admitted), from abep_sim/plasma_devices.py (superseded 0-D Hall), or from the withdrawn v1.2-v1.6 numbers listed in CLAUDE.md 'Superseded / withdrawn'. Size from requirements, A5 allocations, published analog hardware (label every analog: device, source, evidence class; e.g. the ECHT extended channel is 86 mm long, 10 mm wide, 100 mm OD per CLAUDE.md, published analog only), engineering physics (magnetostatics, conduction/radiation, gas conductance, circuit losses) and explicit parameters. P5 calibration-nuisance items (registration L38/L32, historical coil shape, beam-efficiency reading, facility interpretation) are NEVER design variables. Never fill the valve-outlet feed state from the superseded 0-D assumptions.
- PARALLEL LANES (being built right now in other worktrees; NOT in your base): A6 lanes - common pre-ionizer module ICD docs/interfaces/preionizer_module/ + schemas/interfaces/preionizer_module_icd_v1.json (PMI-xx items), parametric Xe ledger abep_sim/xe_ledger.py + docs/budgets/xe_ledger/, Phase-1 prereg framework docs/experiments/phase1_prereg_framework/, M16 matrix docs/budgets/subsystem_maturity/; H2 lanes - docs/hardware/h2/h2_1_hall_chamber_magnet/, h2_2_cathode_integration/, h2_3_gas_path_plenum/, h2_4_ppu_bus/, h2_5_thermal_network/, h2_6_diagnostics_fixture/, h2_7_mechanical_bom/. Where your design depends on one of them, mark the value 'PENDING <lane path>' with the range you can justify now; NEVER fabricate their content. You MAY read their in-progress drafts READ-ONLY under /home/user/abep/.claude/worktrees/*/ if present, but nothing may depend on them at import/test time (lazy resolution with a clear status if missing).
- REQUIRED STRUCTURE of every H2 deliverable (machine-readable JSON + companion .md + deterministic builder script in your lane dir + tests): (a) design-parameter table: id (H2x-nn), name, value or range, units, basis (requirement / allocation / analog / derived / assumed / pending), source (path+field or citation), evidence class, status (PRELIMINARY / PENDING <lane> / TBD - requires <what>), flight-representative vs test-article-only vs ground-only; (b) interface_demands: list of {from, to (another H2 lane, A6 lane, or H-1 CI/plane), quantity, value/range, units, status} so the integration pass can reconcile both directions; (c) hard_incompatibility_check: any finding that could veto the architecture, with evidence and evidence class, or an explicit 'none found' with what was checked; (d) architecture_changing_blockers_touched: which of A7 blockers 1-3 this lane informs and how (or none); (e) m16_rows: which of the 16 A5 subsystems this lane matures, the proposed M16 execution state (READY / RUNNING / BLOCKED / VERIFIED), and for BLOCKED exactly one blocking item plus its rollup category (architecture blocker / hardware-definition blocker / procurement blocker / test-readiness blocker / proposal-only documentation gap); (f) h3_procurement_inputs: long-lead items with the specification level needed to order (published catalog/datasheet data as reference only, no supplier contact); (g) h4_test_inputs: what S1a / S1 / S1b / Phase 1 must measure to close each PRELIMINARY value; (h) milestone statement (A/B/C).
- Architecture branch ids used exactly: 'hall_only', 'rf_hall', 'ecr_hall'. Never declare a winner.
- PINNING: pin only immutable inputs (decision files, verified deliverables, snapshots) by sha256; NEVER pin mutable governance files (lane_registry_v1.json, trigger_registry_v1.json, trigger ledger, runtime_state.json).
- Shared naming contracts (use exactly): bus-power boundary module abep_sim/arch_boundary.py (BOUNDARY_VERSION 'bus_power_boundary_v1'; components hall_discharge, hall_magnet, cathode_keeper, cathode_heater, flow_control, compressor, thermal_control, housekeeping, rf_source (rf_hall), ecr_source and ecr_magnet (ecr_hall); ledger(arch, loads, efficiencies)); comparison harness abep_sim/arch_compare.py; thermal/life abep_sim/thermal_life.py; evidence matrices docs/evidence/rf_source/, docs/evidence/ecr_source/, docs/evidence/hall_sustainment/, docs/evidence/cathode/, docs/evidence/wall_life/; experiment protocol docs/architecture_comparison/experiment_protocol/; upstream ICD schemas/interfaces/; ledgers schemas/ledgers/; Hall-map spec docs/hallmap/. These all exist in your base (merged and verified); also: docs/experiments/hardware/ (H-1/C-1 hardware definition), docs/experiments/instrumentation/, docs/experiments/s1a_readiness/, docs/experiments/s1_readiness/, docs/experiments/capability_demo/, docs/experiments/magnet_coil/, docs/experiments/lifetime_ao/, docs/architecture_comparison/{lock1,mass_bom,interstage,cathode_integration,feed_state_closure,compressor_downselect,aux_bus,power_boundary,veto_layer,experiment_package,hard_gates}/, docs/interfaces/UPSTREAM_ICD.md, docs/evidence/{rf_source,ecr_source,cathode,hall_sustainment}/, docs/milestones/bundle1/bundle1_v5.json.
- NEVER read, list or touch ${SP}/followon or ${SP}/wt_followon.

HARD RULES (breaking any = lane rejected):
1. Modify/create files ONLY under your lane's ALLOWED paths. NEVER modify: hallthruster_bridge/** (prereg, campaign, propellants, audit, ensemble, validation, cases, bridge_lib.jl, PINNED.toml), the frozen P5-N2 pipeline scripts (scripts/score_p5_n2_*.py, scripts/audit_p5_n2_campaign_records.py, scripts/freeze_p5_n2_dataset.py, scripts/report_p5_n2_campaign.py, scripts/make_validation_release.py, scripts/make_p5_n2_launch_manifests.py), existing abep_sim modules (archengine.py, hall_map.py, hall_ensemble.py, intake*.py, compressor.py, reservoir.py, atmosphere.py, plasma_*.py, golden.py, ...), abep_sim/data/**, docs/HISTORY.md, CLAUDE.md, README.md, tests/test_sim.py. New modules are pure and NOT wired into archengine (wiring would be a model change; goldens must not move).
2. Evidence discipline (CLAUDE.md rules 6 and 10, docs/EVIDENCE.md): never invent numbers, sources, page/table numbers or DOIs. Every numeric value carries a source and an evidence class (measured / digitized / inferred / reconstructed / model-derived / assumed) or is explicitly "TBD — requires <what>". Computed values come from a committed deterministic script. No default physical/efficiency values hidden in code: inputs are explicit, missing inputs raise (CLAUDE.md rule 3, no silent fallbacks). Thresholds that are not in the RFP are PROPOSED for the owner.
3. Sources: published / openly accessible only; no contact with persons or labs; no email; no LXCat; no paywall/bot-challenge bypass (abstract-only labelled); never change TLS/trust settings. Cite DOIs/URLs actually accessed (WebSearch/WebFetch are deferred tools: load them with ToolSearch). From memory => "verify".
4. CPU: do NOT run Julia, do NOT run the full test suite, no computation > 1 min. Run only your own new test file(s).
5. Never use screening candidates or unadmitted Hall closures as performance sources; no retuning; never declare an architecture winner; eliminations only via explicit hard-gate logic with the evidence class that supports them. P5 calibration nuisance (registration, coil shape, divergence reading, facility interpretation) is never a design variable or grid axis. Hall-closure uncertainty never leaks upstream into intake/compressor/gas chambers/valves.
6. When done: git add your files and commit in the worktree with a clear message whose last two lines are exactly:
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FzUuRP7UUVEypuFNeEaN4U
Do NOT push. Report the worktree absolute path (pwd), branch name (git rev-parse --abbrev-ref HEAD) and commit sha.

YOUR LANE:
`

const RESULT = {
  type: 'object',
  properties: {
    worktree_path: { type: 'string' }, branch: { type: 'string' }, commit: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    key_findings: { type: 'array', items: { type: 'string' } },
    unlocks: { type: 'array', items: { type: 'string' }, description: 'which other lanes/decisions this result enables, eliminates a dependency for, or suggests as a new parallel branch' },
    open_questions_for_owner: { type: 'array', items: { type: 'string' } },
    tests_run: { type: 'string' }, tests_passed: { type: 'boolean' },
  },
  required: ['worktree_path', 'branch', 'commit', 'files', 'summary', 'key_findings', 'unlocks', 'open_questions_for_owner', 'tests_passed'],
}
const VERDICT = {
  type: 'object',
  properties: {
    pass: { type: 'boolean' },
    issues: { type: 'array', items: { type: 'object', properties: {
      severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, file: { type: 'string' }, description: { type: 'string' } },
      required: ['severity', 'description'] } },
    checked: { type: 'array', items: { type: 'string' } },
  },
  required: ['pass', 'issues', 'checked'],
}
const LENSES = {
  engineering: `ENGINEERING LENS (hardware design reviewer). (a) Independently RECOMPUTE, in your own Python under your scratch dir, every sizing calculation in the lane (magnetics: ampere-turns vs gap and target B, iron saturation and Curie limits, coil I^2R with temperature-corrected resistivity; thermal: conduction G = kA/L, radiation sigma*eps*A*(T^4 - T_sink^4), node balances; gas: Knudsen number and flow regime, molecular/viscous conductance, plenum time constants V/C; electrical: load sums, converter losses, steady vs startup vs peak; mass: roll-ups and margins) - wrong physics, wrong units or a mismatch beyond rounding is MAJOR. (b) Buildability: no physically impossible or mutually inconsistent values (e.g. coil that cannot fit the envelope, temperatures above material limits without a flag, plenum that cannot fill in the stated time); MAJOR. (c) Consistency with A5 allocations, the H-1 configuration items/planes and the bus_power_boundary_v1 component names; MAJOR if violated. (d) interface_demands stated with units and status, and consistent with what the lane assumes of the other lanes; hard_incompatibility_check justified (a veto without evidence, or a missed obvious incompatibility, is MAJOR). (e) Any thrust/efficiency/discharge prediction from a Hall closure or the superseded 0-D model is a BLOCKER. Any architecture selection is a BLOCKER.`,
  evidence: `EVIDENCE LENS. (a) Every numeric value traces to a repository input file (open it and confirm, at least 10 spot checks) or to a cited open source (spot-check at least 4 with WebSearch/WebFetch, loaded via ToolSearch; fabricated or mis-attributed citations are BLOCKERS). (b) Values without source/evidence class, hidden defaults or invented numbers are MAJOR. (c) Any absolute Hall performance number, screening candidate used as performance, filled valve-outlet feed state or compressor draw, winner claim, or elimination not produced by lane 24's evaluator is a BLOCKER. (d) Physics/units of any derivation checked; wrong physics is MAJOR.`,
  rules: `RULES/RECOMPUTE LENS. (a) SCOPE: git -C <worktree> diff --name-only ${BASE}...HEAD within ALLOWED paths; no forbidden file touched; no uncommitted leftovers. (b) RECOMPUTE: for headline numbers derived from repository data or equations, write your own independent Python (do not reuse the lane's code) and compare; mismatch beyond rounding is major. (c) CORRECTNESS: JSON/schemas parse and validate; code consistent with the modules/fields it references (grep them); no hidden defaults; refusal paths raise; run ONLY the lane's own test file(s): they must pass and test something meaningful. (d) RULES: the three architecture ids used exactly; eliminations only via the lane-24 gate logic; missing inputs TBD/UNDETERMINED (never fabricated); every required deliverable of the brief present; milestone A/B/C statement present; no winner, no retuning. (e) USEFULNESS: every required deliverable in the brief present and substantive; the 'unlocks' claims are justified.`,
}
const verifyPrompt = (lane, res, lens) => `You are an ADVERSARIAL reviewer. Default to finding problems; pass only if there are no blocker or major issues under your lens.
Repository: ABEP-VLEO simulator. Lane "${lane.key} — ${lane.title}" was built in worktree ${res.worktree_path} (branch ${res.branch}, commit ${res.commit}), base ${BASE}. Work READ-ONLY there; scratch scripts only under ${SP}/verify_${lane.key}_${lens}/. Never touch ${SP}/followon or ${SP}/wt_followon. Do NOT run Julia or the full test suite.
Lane brief: ${lane.prompt}
ALLOWED paths: ${lane.allowed.join(', ')}
${LENSES[lens]}
Return pass=true only if no blocker/major issues remain.`
const fixPrompt = (lane, res, issues) => `Repair lane "${lane.key} — ${lane.title}" in its existing worktree ${res.worktree_path} (cd there; do NOT create a new worktree; stay on branch ${res.branch}).
${COMMON.split('YOUR LANE:')[0]}
Lane brief: ${lane.prompt}
ALLOWED paths: ${lane.allowed.join(', ')}
Independent adversarial reviewers reported these issues — fix every blocker and major one (minors where cheap). Unsourceable claims: mark TBD/verify or remove. Non-reproducing numbers: find the true value, fix code and text. Revert anything outside ALLOWED paths.
ISSUES: ${JSON.stringify(issues)}
Commit the repair as a new commit in the same worktree (same trailer lines). Report as before.`

async function verifyBoth(lane, res, round) {
  const lensList = lane.lenses || ['evidence', 'rules']
  const vs = await parallel(lensList.map(lens => () =>
    agent(verifyPrompt(lane, res, lens), { label: `verify${round}:${lane.key}:${lens}`, phase: 'Verify', schema: VERDICT })))
  const ok = vs.filter(Boolean)
  return { pass: ok.length === lensList.length && ok.every(v => v.pass), issues: ok.flatMap(v => v.issues || []) }
}

const lanes = ARGS_EMBEDDED.lanes
const laneMap = Object.fromEntries(lanes.map(l => [l.key, l]))
const promises = {}
function runLane(lane) {
  if (promises[lane.key]) return promises[lane.key]
  promises[lane.key] = (async () => {
    const deps = await Promise.all((lane.deps || []).map(k => runLane(laneMap[k])))
    const depText = deps.map((d, i) => d && d.res
      ? `- ${lane.deps[i]}: worktree ${d.res.worktree_path} (branch ${d.res.branch}, commit ${d.res.commit}), verified=${d.pass}; files: ${(d.res.files || []).join(', ')}; summary: ${d.res.summary}`
      : `- ${lane.deps[i]}: FAILED / unavailable — treat its deliverable as missing (TBD) and say so`).join('\n')
    if (deps.length) log(`${lane.key}: prerequisites ${lane.deps.join(', ')} finished — starting`)
    const res = await agent(COMMON + `${lane.key} — ${lane.title}\n${lane.prompt}\nALLOWED paths: ${lane.allowed.join(', ')}` +
      (deps.length ? `\nPREREQUISITE LANES (finished; read their deliverables READ-ONLY from their worktrees, build on them, reference them by repository-relative path — they will be merged with yours; never copy them into your paths):\n${depText}` : ''),
      { label: `build:${lane.key}`, phase: 'Build', isolation: 'worktree', schema: RESULT })
    if (!res) return null
    let cur = res, v = await verifyBoth(lane, cur, 1), rounds = 0
    while (!v.pass && rounds < 2) {
      rounds++
      const fx = await agent(fixPrompt(lane, cur, v.issues), { label: `fix${rounds}:${lane.key}`, phase: 'Fix', schema: RESULT })
      if (fx) cur = fx
      v = await verifyBoth(lane, cur, rounds + 1)
    }
    log(`${lane.key}: done (verified=${v.pass}, fix rounds ${rounds}); unlocks: ${(cur.unlocks || []).join('; ').slice(0, 300)}`)
    return { lane: lane.key, res: cur, pass: v.pass, fix_rounds: rounds, open_issues: v.pass ? [] : v.issues }
  })()
  return promises[lane.key]
}
const results = await parallel(lanes.map(l => () => runLane(l)))
return results.map((r, i) => r || { lane: lanes[i].key, failed: true })

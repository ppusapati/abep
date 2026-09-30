export const meta = {
  name: 'a9-07-h2-revisions',
  description: 'A9.1 step 2: fo_a9_07_h2_revisions (investigation-hypothesis work, not architecture selection); 3-lens verification (evidence, rules, engineering), up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'isolated worktree' },
    { title: 'Verify', detail: 'evidence + rules + engineering lenses, independent' },
    { title: 'Fix', detail: 'repair rounds (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "2625fe567b48c581232bbaf33a057f352f6963e6", "lanes": [{"key": "A9_07", "title": "fo_a9_07_h2_revisions", "slug": "a9-07-h2-revisions", "lenses": ["evidence", "rules", "engineering"], "allowed": ["docs/hardware/h2_a9_revisions/**", "tests/test_h2_a9_revisions.py"], "prompt": "Registered follow-on fo_a9_07_h2_revisions (trigger T_A9_07_H2_REVISIONS, owner A9.1 step 2). H2 REVISIONS FOR A9 in a NEW deliverable docs/hardware/h2_a9_revisions/ (the verified H2-1..H2-7 v1 files stay byte-identical; you may import/run their builders' pure functions read-only to recompute). Produce a revision register REV-xx (per affected H2 item id: old value/requirement, new value/requirement, driver = owner row / A9.1 decision / A9 lane item, recomputation where a deterministic model exists, status) covering at least: (1) EXTERNAL C1 reference location (row 79, H22-OQ-01 / H2-1 Q6 reversed): H2-1 channel sizing no longer constrained by a central C1 (re-derive the affected H2-1 constraint, e.g. d_mean >= H21-22, without predicting performance), H2-2 C1 integration moved to an external mount on the ground article only (OQ-A902-04: not a flight item), heated C1 (row 49), two series isolation valves (row 90), pulsed keeper 300-600 V with ICP-46 isolation (900 V basis, 1.0 kV DC development hipot, separate 600 V pulse test), keeper material not graphite for O exposure (row 94), 0.005 mg/s step and 120 s x 2 ignition dwell (rows 92-93); (2) DOWNSTREAM ICP FIXTURE: re-derive the H2-6 kinematic carrier (H26-40..42, designed for an upstream module) for a downstream module at IP-NEU relative to IP-EXIT (A9.1 plane names; historical IP-DN unchanged), H-1 stays bolted (row 122), matched sham routing (row 133), matching network off the moving platform with flexible coax, S-parameter/cable-loss correction and the coupler reference plane after the matching network (A9.1), stand payload >= 25 kg (row 116); instrument-list additions requested by A9-04 IF-14 / IF-16 (13.56 MHz coupler and sensors, floating-rated collector V/I, ground-return current monitor, traceable force/RF/DC/MFC calibration, P_bus 1 ms-window channel: >= 20 kHz bandwidth, >= 100 kSa/s, synchronized, anti-alias documented - OQ-A902-01); (3) 50 K THERMAL PROTECTION: rerun the H2-5 network (its builder/model, read-only) with the owner rules (>= 50 K below each validated continuous-use limit plus 20 % heat-load margin, row 86; aborts at limit minus 50 K, UBQ-06; high-emittance coating baseline, row 84; ceramic-insulated copper coil, row 77; EM-only MC-1, row 78; FeCo-2V inner + pure-iron outer, row 76) and report which nodes CLOSE / DO_NOT_CLOSE and the minimal design levers (coating, radiator area, coil current density, conduction paths) with recomputed numbers - never relax a limit; the 11.2 K BN-wall case must be resolved or reported as open; (4) H2-4 supply partition for A9 (row 110) consistent with bus_power_boundary_a9_v1 (100 V internal bus row 111, revised SEQ-1 row 112, ICP RF source/matching/collector slots) and the H24 items A9-02 flagged NEEDS_REVISION (H24-19, H24-26) / CONSTRAINED (H24-35); (5) revised interfaces: IP-EXIT / IP-NEU, V_d referenced to the electron-source reference (A9.1), isolator withstand ~1 kV DC with segmented/porous geometry (row 105). Mass consequences to A9-06, Xe consequences to A9-08, procurement items to A9-09."}]}
const BASE = ARGS_EMBEDDED.base
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const COMMON = `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep; primary checkout /home/user/abep). You run in an ISOLATED git worktree created for you (your current working directory); do all edits there. FIRST run: git reset --hard ${BASE} (the worktree is created from main, which may lack the newest governance and decision files) and confirm with: git rev-parse HEAD. Base commit: ${BASE}.

CONTEXT (read CLAUDE.md in your worktree first, including its final section 'A9'):
- RFP envelope (DRDO TDF; official RFP not yet obtained, tender 2026_DRDO_788433_1): 180-230 km, 12-25 mN, < 1.5 kW, < 40 kg, >= 26,280 h mission basis, > 15,000 h firing (provisional), Hall preferred, air + Xe.
- GOVERNING OWNER DECISION: A9 docs/decisions/OD_HARDWARE_PIVOT_2026_09_29_A9_hall_downstream_rf_icp_neutralizer.json (status OWNER_AUTHORIZED_INVESTIGATION_HYPOTHESIS_NOT_FLIGHT_BASELINE) and the owner's 147 answers docs/decisions/OD_2026_09_29_owner_answers_147.json (verbatim pack OD_2026_09_29_OWNER_DECISION_PACK_147.md). Read both first; cite them by path AND sha256 (immutable); cite answers by row number. Also immutable and still binding: A4-A7 (docs/decisions/OD_HARDWARE_PIVOT_2026_09_27_A4..A7), P5-N2 v1 (INCONCLUSIVE), the credible Hall set is EMPTY, Bundle 1 NO_BASELINE_YET.
- A9 IN SHORT: primary investigation = Hall discharge (H-1) followed by a DOWNSTREAM 13.56 MHz RF inductively coupled plasma (ICP) electron source / neutralizer (Takahashi, Watanabe, Nakahama, Kikuchi, J. Electr. Propuls. 3:18 (2024), DOI 10.1007/s44205-024-00081-2, CC BY-NC-ND 4.0: topology precedent only). Control/fallback = Hall + heated Xe-fed LaB6 C1 (external location, row 79). First decisive comparison: SAME H-1, feed state, V_d/B settings, stand and metrology; C1 electron source vs downstream ICP electron source on swappable downstream modules on a kinematic carrier (H-1 stays bolted, row 122) with matched sham service lines (row 133). Evidence order: Ar engineering-only (never counts toward DRDO atmospheric requirements) -> pure N2 -> O2-bearing mixtures (label NO_ATOMIC_O) -> separate atomic-O materials/life programme (row 132). 25 mN, < 1.5 kW (spacecraft-DC propulsion boundary, incl. start-up transients unless the RFP allows otherwise, row 108) and < 40 kg WET (row 5) are full-system gates; ICP power must fit inside the internal ~1.35 kW design allocation (row 109). Use configuration ids exactly: 'hall_c1_reference', 'hall_icp_neutralizer'; outcome vocabulary includes 'NO_VIABLE_CASE' and status 'OPEN' (a status, not an outcome, row 38). NET_BENEFIT = hard gates + Pareto, never a weighted scalar unless preregistered (row 37). Never declare a winner.
- HISTORICAL (preserve byte-for-byte; do not use for the new primary line; never edit): the A5 Phase-1 prereg framework docs/experiments/phase1_prereg_framework/, the pre-ionizer module ICD docs/interfaces/preionizer_module/, LOCK-1 drafts docs/architecture_comparison/lock1/, abep_sim/arch_boundary.py (bus_power_boundary_v1), A8 and the parallel RF||Hall v2 branch. You may READ them for reusable structure and cite them.
- VERIFIED INPUTS you build on (read-only): H2 lanes docs/hardware/h2/h2_1..h2_7 (H-1 Hall head/magnet, C-1 integration, gas path/plenum incl. the Paschen isolator finding, PPU/bus, thermal network, diagnostics + fixture, mechanical/mass BOM), docs/experiments/instrumentation/ (+ metrology_spec/), docs/experiments/hardware/ (H-1/C-1 configuration items and planes), docs/budgets/xe_ledger/, docs/budgets/subsystem_maturity/ (M16 v2), docs/budgets/owner_decisions/, docs/evidence/cathode/, docs/procurement/web_track_v1/ (R4 instrumentation, R5 facilities, R7 thrust stand, R8 anode).
- A9-01..A9-05 ARE ALL MERGED AND VERIFIED IN YOUR BASE: docs/experiments/hall_icp/prereg_framework/ (A9-01, DQ-HI-* ids), abep_sim/bus_boundary_a9.py + docs/architecture_comparison/power_boundary_a9/ + schemas/interfaces/bus_power_boundary_a9_v1.json (A9-02), docs/interfaces/icp_neutralizer/ + schemas/interfaces/icp_neutralizer_icd_v1.json (A9-03), docs/experiments/hall_icp/uncertainty_budget/ (A9-04, provisional UB-DQ-* ids), docs/evidence/icp_neutralizer/ + docs/experiments/hall_icp/validation_inputs/ (A9-05). The owner follow-up decisions A9.1 are docs/decisions/OD_2026_09_30_A9_1_followup_owner_decisions.json (+ verbatim .md, sha256-pin both): they are BINDING for your lane; cite them by decision id (HIQ-xx, UBQ-xx, OQ-A902-xx, ICP-45/46, A9-03 clarifications). The A9 core integration repair (fo_a9_int_core_integration: final DQ-HI-* ids, resolved cross-references, docs/experiments/hall_icp/integration/) is merged in your base.
- PARALLEL A9 LANES (built now in other worktrees, NOT in your base): A9-06 docs/budgets/mass_a9/ (mass reconciliation), A9-07 docs/hardware/h2_a9_revisions/ (H2 revisions), A9-08 docs/budgets/xe_ledger_a9/ (Xe ledger update), A9-09 docs/procurement/rfq_a9/ (RFQ packages). Where you depend on one, mark 'PENDING <lane path>'; never fabricate it; you may read drafts READ-ONLY under /home/user/abep/.claude/worktrees/*/; nothing may depend on them at import/test time. A9-10 reconciles all four afterwards.
- NO PERFORMANCE PREDICTION: never predict thrust, efficiency, discharge current, neutralizer electron current or plasma state from any Hall transport closure (none admitted), from abep_sim/plasma_devices.py (superseded 0-D Hall) or from the withdrawn v1.2-v1.6 numbers. Published analog data (e.g. Takahashi 2024) may be quoted ONLY with page/figure/table provenance and evidence class ('published analog, digitized/reported'), never as Vyovrinda performance.
- NO FROZEN NUMERIC THRESHOLDS: decision margins, effect sizes, stop-rule numbers and n are defined as quantities with their freeze point (LOCK-1 rule / LOCK-2 value, rows 18-19, 30) and PROPOSED values only where an explicit owner answer gives them. Owner-given values (e.g. >= 50 K thermal margin row 86, 1 % thrust uncertainty target row 121, 0.005 mg/s C1 flow step row 92, 120 s x 2 ignition dwell row 93, two elevated p_b levels row 23, 13.56 MHz and 0-500 W lab forward power row 72) are cited by row.
- PINNING: pin only immutable inputs (decision files, verified deliverables) by sha256; NEVER pin mutable governance files (lane_registry_v1.json, trigger_registry_v1.json, trigger ledger, runtime_state.json).
- NEVER read, list or touch ${SP}/followon or ${SP}/wt_followon.

HARD RULES (breaking any = lane rejected):
1. Modify/create files ONLY under your lane's ALLOWED paths. NEVER modify: hallthruster_bridge/**, the frozen P5-N2 pipeline scripts (scripts/score_p5_n2_*.py etc.), existing abep_sim modules (archengine.py, arch_boundary.py, hall_map.py, hall_ensemble.py, intake*.py, compressor.py, reservoir.py, atmosphere.py, plasma_*.py, golden.py, xe_ledger.py ...), abep_sim/data/**, docs/HISTORY.md, CLAUDE.md, README.md, tests/test_sim.py, any docs/decisions/** file, any historical artifact listed above. New modules are pure and NOT wired into archengine (goldens must not move). A repository test forbids any module other than abep_sim/xe_ledger.py from containing the substring 'xe_ledger' in code: refer to it as 'the Xe ledger' in code/comments and cite the path only in JSON/Markdown.
2. Evidence discipline (CLAUDE.md rules 6 and 10, docs/EVIDENCE.md): never invent numbers, sources, page/table/figure numbers or DOIs. Every numeric value carries a source and an evidence class (measured / digitized / inferred / reconstructed / model-derived / assumed / owner-allocation) or is 'TBD - requires <what>'. Computed values come from a committed deterministic script. No hidden defaults: inputs explicit, missing inputs raise (CLAUDE.md rule 3). Thresholds not in the RFP or the owner answers are PROPOSED for the owner.
3. Sources: published / openly accessible only; no contact with persons, labs or suppliers; no email; no LXCat; no paywall/bot-challenge bypass (abstract-only labelled); never change TLS/trust settings. Cite DOIs/URLs actually accessed (WebSearch/WebFetch are deferred tools: load them with ToolSearch; Crossref api.crossref.org and publisher open-access pages via curl are fine). From memory => 'verify'.
4. CPU: do NOT run Julia, do NOT run the full test suite, no computation > 1 min. Run only your own new test file(s).
5. Never use screening candidates or unadmitted Hall closures as performance sources; no retuning; never declare a winner; Hall-closure uncertainty never leaks upstream.
6. REQUIRED STRUCTURE of the deliverable: machine-readable JSON + companion .md generated from it + deterministic builder script with --check in the lane dir + tests; sections: (a) items/parameters table with ids, value or TBD, units, basis, source, evidence class, status, freeze point (NOW / LOCK-1 / LOCK-2 / after-evidence); (b) interface_demands to/from the other A9 lanes and H2/H-1 items (both directions, with units and status); (c) owner_answers_applied: row -> how applied; (d) open_owner_questions (new questions only, each with proposed answer or 'owner call'); (e) historical_reuse: what was reused from which historical artifact (by path+sha256) and what was deliberately not reused; (f) m16_impact: which M16 rows this lane touches and how; (g) h3/h4 inputs where relevant.
7. When done: git add your files and commit in the worktree with a clear message whose last two lines are exactly:
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
  engineering: `ENGINEERING LENS (hardware / RF / power design reviewer). (a) Independently RECOMPUTE, in your own Python under your scratch dir, every sizing or accounting calculation in the lane (electrical: load sums per bus slot, converter and matching-network losses, forward/reflected/absorbed RF power and VSWR relations, steady vs startup vs peak; electron current balance: neutralizer electron current vs Hall ion beam current; gas: conductance, pressure at the ICP interface, Knudsen regime; thermal: dissipation, conduction/radiation; mass roll-ups) - wrong physics, wrong units or a mismatch beyond rounding is MAJOR. (b) Buildability: no physically impossible or mutually inconsistent values (e.g. coil that cannot fit the envelope, temperatures above material limits without a flag, plenum that cannot fill in the stated time); MAJOR. (c) Consistency with the A9 decision, the owner answers (docs/decisions/OD_2026_09_29_owner_answers_147.json), the H-1 configuration items/planes and the verified H2 deliverables; MAJOR if violated. (d) interface_demands stated with units and status, and consistent with what the lane assumes of the other lanes; hard_incompatibility_check justified (a veto without evidence, or a missed obvious incompatibility, is MAJOR). (e) Any thrust/efficiency/discharge/electron-current prediction from a Hall closure or the superseded 0-D model is a BLOCKER. Declaring the ICP neutralizer (or C1) the winner, or A9 a flight baseline, is a BLOCKER.`,
  evidence: `EVIDENCE LENS. (a) Every numeric value traces to a repository input file (open it and confirm, at least 10 spot checks) or to a cited open source (spot-check at least 4 with WebSearch/WebFetch, loaded via ToolSearch; fabricated or mis-attributed citations are BLOCKERS). (b) Values without source/evidence class, hidden defaults or invented numbers are MAJOR. (c) Any absolute Hall performance number, screening candidate used as performance, filled valve-outlet feed state or compressor draw, winner claim, numeric Phase-1 threshold frozen before score-bearing data, or a number taken from Takahashi et al. 2024 without page/figure/table provenance is a BLOCKER. (d) Physics/units of any derivation checked; wrong physics is MAJOR.`,
  rules: `RULES/RECOMPUTE LENS. (a) SCOPE: git -C <worktree> diff --name-only ${BASE}...HEAD within ALLOWED paths; every existing verified deliverable outside the ALLOWED paths (H2 v1 files, A9-01..05, xe_ledger v1, mass_bom v1, decisions) byte-identical; each owner answer / A9.1 decision the lane cites is quoted consistently with the verbatim source; no forbidden file touched; no uncommitted leftovers. (b) RECOMPUTE: for headline numbers derived from repository data or equations, write your own independent Python (do not reuse the lane's code) and compare; mismatch beyond rounding is major. (c) CORRECTNESS: JSON/schemas parse and validate; code consistent with the modules/fields it references (grep them); no hidden defaults; refusal paths raise; run ONLY the lane's own test file(s): they must pass and test something meaningful. (d) RULES: A9 configuration ids used exactly ('hall_c1_reference', 'hall_icp_neutralizer', outcome 'NO_VIABLE_CASE'); no winner; historical artifacts (A5 Phase-1 framework, pre-ionizer ICD, bus_power_boundary_v1, LOCK-1 drafts, A8/v2) byte-identical; missing inputs TBD/UNDETERMINED (never fabricated); every required deliverable of the brief present; no winner, no retuning. (e) USEFULNESS: every required deliverable in the brief present and substantive; the 'unlocks' claims are justified.`,
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

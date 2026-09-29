export const meta = {
  name: 'followon-aux-veto-exppkg',
  description: 'Follow-ons T_AUX_BUS, T_VETO_LAYER, T_EXPERIMENT_PACKAGE: isolated worktrees, two-lens adversarial verification, up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane; dependent lanes start when prerequisites finish' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "d939ef66324b7d1036b2c9bcd5e7674df218342b", "lanes": [{"key": "AUXBUS", "title": "fo_aux_bus_comparison (full auxiliary / DC-bus power comparison)", "allowed": ["docs/architecture_comparison/aux_bus/**", "tests/test_aux_bus_comparison.py"], "prompt": "Registered follow-on fo_aux_bus_comparison (trigger T_AUX_BUS; prerequisites lane_20_ppu_magnet f7c226848d, lane_19_cathode_integration eff15f85c5, lane_11_bus_boundary a2a139686d, all verified). FIRST STEP: your worktree may have been created from main (daa0e75). If `git rev-parse HEAD` != d939ef66324b7d1036b2c9bcd5e7674df218342b and `git status --porcelain` is empty, run `git reset --hard d939ef66324b7d1036b2c9bcd5e7674df218342b`; confirm the input files exist before anything else. All inputs named below are merged at this base (verified lanes, two-lens protocol). QUESTION: under bus_power_boundary_v1 (abep_sim/arch_boundary.py; bus_power_ledger), what is the full auxiliary DC-bus power of hall_only, rf_hall and ecr_hall, component by component, and how do the architectures differ? Inputs: abep_sim/arch_boundary.py + docs/architecture_comparison/power_boundary/, abep_sim/magnet_power.py + docs/architecture_comparison/electrical_closure/ (PPU and magnet supply efficiencies, magnet power), abep_sim/cathode_integration.py + docs/architecture_comparison/cathode_integration/ (keeper/heater loads, start-up transient), docs/architecture_comparison/breakeven/ and overlays/ (RF/ECR source cost relations), interstage (eta_t basis), abep_sim/arch_compare.py (harness, if useful). Deliver in docs/architecture_comparison/aux_bus/: per architecture x every v1 component: load-plane power, efficiency, bus draw and loss as ranges or TBD with source/evidence class/derivation; the differential terms (rf_hall - hall_only, ecr_hall - hall_only) with what is common-mode (cancels) and what does not; start-up vs steady; the auxiliary headroom inside the RFP < 1.5 kW as a conditional inequality in the unknown Hall discharge power (symbolic; no closure value); what each TBD needs. Use bus_power_ledger itself for every ledger you evaluate (it raises on missing inputs: evaluate only where every input is sourced, else report the ledger as not evaluable and why). Test tests/test_aux_bus_comparison.py. Output a deterministic build script with --check (byte-for-byte reproduction), a JSON (+ schema) and a generated Markdown page; pin every input file by sha256 + lane id; missing/changed inputs raise, no fallback. Every number traces to an input file or a cited open source with evidence class, else TBD with the blocking lane/measurement. No absolute Hall performance from any closure (credible set empty; gate 3 FAIL); no screening candidates as performance; never fill the valve-outlet feed state (lane 16 TBD) or the compressor bus draw (upstream ICD lane_33 not verified: TBD). No winner, no eliminations except through lane 24's evaluator (abep_sim/hard_gates.py) with its evidence rules. State which milestone (A/B/C) it supports and what the next milestone needs. DRAFT for owner review; thresholds not in the RFP are PROPOSED."}, {"key": "VETO", "title": "fo_veto_layer (mass / thermal / life veto layer)", "allowed": ["docs/architecture_comparison/veto_layer/**", "tests/test_veto_layer.py"], "prompt": "Registered follow-on fo_veto_layer (trigger T_VETO_LAYER; prerequisites lane_21_mass_bom 41acbb9e8d, lane_15_thermal_life d2325c8da3, both verified). FIRST STEP: your worktree may have been created from main (daa0e75). If `git rev-parse HEAD` != d939ef66324b7d1036b2c9bcd5e7674df218342b and `git status --porcelain` is empty, run `git reset --hard d939ef66324b7d1036b2c9bcd5e7674df218342b`; confirm the input files exist before anything else. All inputs named below are merged at this base (verified lanes, two-lens protocol). QUESTION: can mass, thermal rejection or life veto any of hall_only, rf_hall, ecr_hall against the RFP envelope (< 40 kg, < 1.5 kW, > 15,000 h firing, 26,000 h mission; CLAUDE.md), and on what evidence? Inputs: abep_sim/mass_bom.py + docs/architecture_comparison/mass_bom/, abep_sim/thermal_life.py + abep_sim/thermal.py + docs/thermal_life/, abep_sim/hard_gates.py + docs/architecture_comparison/hard_gates/ (gate definitions, evidence-class rules), cathode_integration (insert life), electrical_closure, scaling (docs/architecture_comparison/scaling/). Deliver in docs/architecture_comparison/veto_layer/: per architecture x {mass, Q_reject/thermal, life (firing and mission), start-up}: status VETO_CANDIDATE (exceedance supported by evidence strong enough under lane 24's rules), NO_VETO_WITHIN_EVIDENCE, or UNDETERMINED (missing inputs named with lanes), with margins as ranges and evidence classes. A VETO_CANDIDATE is fed to the lane-24 evaluator as an evidence item; only if that evaluator returns a demonstrated gate failure may the layer report ELIMINATED_WITHIN_TESTED_ENVELOPE (do not modify hard_gates.py). Identify which vetoes are common-mode (hit all three, e.g. Hall-channel wall life on air) vs architecture-specific (pre-ionizer mass/thermal/life). Test tests/test_veto_layer.py. Output a deterministic build script with --check (byte-for-byte reproduction), a JSON (+ schema) and a generated Markdown page; pin every input file by sha256 + lane id; missing/changed inputs raise, no fallback. Every number traces to an input file or a cited open source with evidence class, else TBD with the blocking lane/measurement. No absolute Hall performance from any closure (credible set empty; gate 3 FAIL); no screening candidates as performance; never fill the valve-outlet feed state (lane 16 TBD) or the compressor bus draw (upstream ICD lane_33 not verified: TBD). No winner, no eliminations except through lane 24's evaluator (abep_sim/hard_gates.py) with its evidence rules. State which milestone (A/B/C) it supports and what the next milestone needs. DRAFT for owner review; thresholds not in the RFP are PROPOSED."}, {"key": "EXPPKG", "title": "fo_experiment_package (experimental decision package from the minimum decisive experiment)", "allowed": ["docs/architecture_comparison/experiment_package/**", "tests/test_experiment_package.py"], "prompt": "Registered follow-on fo_experiment_package (trigger T_EXPERIMENT_PACKAGE; prerequisite lane_25_min_decisive_experiment f08e4092d8, verified). FIRST STEP: your worktree may have been created from main (daa0e75). If `git rev-parse HEAD` != d939ef66324b7d1036b2c9bcd5e7674df218342b and `git status --porcelain` is empty, run `git reset --hard d939ef66324b7d1036b2c9bcd5e7674df218342b`; confirm the input files exist before anything else. All inputs named below are merged at this base (verified lanes, two-lens protocol). GOAL: turn the minimum-decisive-experiment draft into an owner decision package. Inputs: docs/architecture_comparison/minimum_decisive_experiment/ (lane 25, incl. its open owner questions: T-BUDGET-SHARES, stop rule sign form vs STOP-MARGIN, Hall-on at P_lo, T-ISO-INTERP, LOCK-1/LOCK-2 file location), docs/architecture_comparison/experiment_protocol/ (lane 06, verified; its differences with lane 25 are listed in lane 25 section 13), docs/architecture_comparison/failure_tree/ (lane 26), overlays rf/ecr (the decisive measurements, e.g. ECR G9) and hall_sustainment, hard_gates, breakeven. Deliver in docs/architecture_comparison/experiment_package/: (1) the decision list the owner must lock before any score-bearing run (each: options, consequences for statistics/cost/readings computed by the lane-25 tools, recommendation marked PROPOSED); (2) a traceability matrix measurement -> which break-even placement / Bundle-1 condition / hard gate / failure-tree node it resolves; (3) a reconciliation of lane 25 vs lane 06 (boundary basis, classes, hardware) with a proposed single protocol basis; (4) facility/hardware requirements as requirements (TBD where not sourced), no named lab or person to contact (no contact with labs; published facility descriptions may be cited as references only); (5) what the package unlocks for Milestone A->B. Nothing is pre-registered or locked by this lane. Test tests/test_experiment_package.py. Output a deterministic build script with --check (byte-for-byte reproduction), a JSON (+ schema) and a generated Markdown page; pin every input file by sha256 + lane id; missing/changed inputs raise, no fallback. Every number traces to an input file or a cited open source with evidence class, else TBD with the blocking lane/measurement. No absolute Hall performance from any closure (credible set empty; gate 3 FAIL); no screening candidates as performance; never fill the valve-outlet feed state (lane 16 TBD) or the compressor bus draw (upstream ICD lane_33 not verified: TBD). No winner, no eliminations except through lane 24's evaluator (abep_sim/hard_gates.py) with its evidence rules. State which milestone (A/B/C) it supports and what the next milestone needs. DRAFT for owner review; thresholds not in the RFP are PROPOSED."}]}

const BASE = ARGS_EMBEDDED.base
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const COMMON = `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep; primary checkout /home/user/abep). You run in an ISOLATED git worktree created for you (your current working directory); do all edits there. Base commit: ${BASE}.

CONTEXT (read CLAUDE.md in your worktree first):
- RFP envelope (DRDO TDF, CLAUDE.md): 180-230 km, 12-25 mN, < 1.5 kW, < 40 kg, 26,000 h mission, > 15,000 h firing, Hall preferred, air + Xe.
- Three candidate thrust architectures, identified everywhere by these exact ids: 'hall_only', 'rf_hall', 'ecr_hall'. The RF/ECR arms change ONLY the pre-ionization method; the downstream Hall accelerator, feed state, cathode and bus boundary are common.
- Two tracks run in parallel: (1) physics validation (P5-N2 v1 is final: all 9 SGB screening candidates INCONCLUSIVE / NOT ELIGIBLE, credible set empty, gate 3 FAIL; v2 only if independent evidence justifies a wider chemistry domain) and (2) architecture comparison preparation (your track). They meet only when an admitted Hall transport closure is needed for absolute performance. Build everything so it works WITHOUT absolute Hall predictions today and accepts admitted closures later.
- Owner decision milestones: A = conditional selection ('architecture X is baseline provided conditions A/B/C are demonstrated'; does not require Physics Baseline 1.0); B = physics-backed selection (credible envelopes from validated Hall transport, chemistry and common-boundary performance); C = proposal/PDR freeze (mass, power, thermal, life, startup, cathode, mission closure integrated). Every deliverable states which milestone(s) it supports and what it needs to reach the next one.
- Shared naming contracts (use exactly): bus-power boundary module abep_sim/arch_boundary.py (BOUNDARY_VERSION 'bus_power_boundary_v1'; components hall_discharge, hall_magnet, cathode_keeper, cathode_heater, flow_control, compressor, thermal_control, housekeeping, rf_source (rf_hall), ecr_source and ecr_magnet (ecr_hall); ledger(arch, loads, efficiencies)); comparison harness abep_sim/arch_compare.py; thermal/life abep_sim/thermal_life.py; evidence matrices docs/evidence/rf_source/, docs/evidence/ecr_source/, docs/evidence/hall_sustainment/, docs/evidence/cathode/, docs/evidence/wall_life/; experiment protocol docs/architecture_comparison/experiment_protocol/; upstream ICD schemas/interfaces/; ledgers schemas/ledgers/; Hall-map spec docs/hallmap/. These are being built by OTHER lanes right now and are mostly NOT in your worktree: you may read them READ-ONLY if they exist under /home/user/abep/.claude/worktrees/*/ (find them), reference them by repository-relative path, and never copy them into your paths or depend on them at import time (lazy resolution with a clear error if missing; tests must not require them).
- Pre-registered follow-on runs are RUNNING on every CPU core under ${SP}/followon and ${SP}/wt_followon — NEVER read, list or touch those paths.

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
  const vs = await parallel(['evidence', 'rules'].map(lens => () =>
    agent(verifyPrompt(lane, res, lens), { label: `verify${round}:${lane.key}:${lens}`, phase: 'Verify', schema: VERDICT })))
  const ok = vs.filter(Boolean)
  return { pass: ok.length === 2 && ok.every(v => v.pass), issues: ok.flatMap(v => v.issues || []) }
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

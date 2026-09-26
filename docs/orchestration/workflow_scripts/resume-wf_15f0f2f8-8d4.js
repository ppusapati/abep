export const meta = {
  name: 'abep-lanes-v3-deps',
  description: 'Architecture Decision Acceleration lanes: isolated worktrees, dependency-triggered fan-out, two-lens adversarial verification, up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane; dependent lanes start when prerequisites finish' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "c53b75a", "lanes": [{"key": "BRKEVEN", "title": "Architecture break-even surfaces (power, utilization, mass, life) \u2014 no absolute Hall prediction needed", "allowed": ["abep_sim/breakeven.py", "scripts/architecture/build_breakeven_surfaces.py", "docs/architecture_comparison/breakeven/**", "tests/test_breakeven.py"], "prompt": "PRIORITY (owner request). Build architecture break-even surfaces that decide whether a pre-ionizer CAN pay for itself, without absolute Hall predictions. New pure module abep_sim/breakeven.py (no defaults; explicit inputs; raise on missing/invalid) and a derivation document docs/architecture_comparison/breakeven/BREAKEVEN_DERIVATION.md. Derive, with every assumption explicit and cited to open Hall/ion-source physics literature (e.g. Hall efficiency decomposition into utilization, current/voltage and divergence efficiencies; ion production cost): (1) the power break-even condition dP_Hall_saved > P_source_bus + P_interstage_loss + P_extra_PPU (all at the common DC bus boundary 'bus_power_boundary_v1'), for rf_hall and for ecr_hall; (2) the REQUIRED utilization improvement d_eta_u* = f(P_source, eta_transport, mdot, V_d, eta_Hall components, species mass/charge mix) under two comparison conventions stated separately \u2014 equal bus power (thrust gain) and equal thrust (bus-power saving) \u2014 including the case where pre-ionized ions reduce the Hall's own ionization cost and the case where they only add ions; (3) the equivalent break-even ION PRODUCTION COST of the source (W per A delivered to the Hall, incl. transport efficiency eta_transport) so published RF/ECR evidence (W/A, eV/ion) can be compared directly against the surface; (4) mass break-even dm_benefit > m_source + m_PPU + m_magnets expressed via propellant/power-system mass sensitivities (inputs, TBD values); (5) life break-even as an inequality structure (life gain from lower Hall stress vs new source-hardware life limit), with the quantities each side needs. Then scripts/architecture/build_breakeven_surfaces.py computes surfaces over PARAMETER RANGES ONLY (not predictions): e.g. P_source 0-500 W, eta_transport 0.1-1, V_d and mdot ranges bracketing the RFP envelope (label ranges as analysis ranges, sourced or PROPOSED), species N2/O/O2/Xe; outputs docs/architecture_comparison/breakeven/breakeven_surfaces_v1.json (+ PNG plots if matplotlib is available; otherwise CSV) and BREAKEVEN_SURFACES.md explaining how to read them and how an evidence value (e.g. a source's measured ion cost) is placed against them. If RF/ECR evidence matrices exist in other worktrees (docs/evidence/rf_source, ecr_source), you may overlay sourced ion-cost points READ-ONLY with their evidence class, clearly as preliminary. No architecture winner. State milestone A/B/C support (this is chiefly milestone A: eliminate regions early). Test tests/test_breakeven.py: limiting cases (P_source = 0 => d_eta_u* = 0; eta_transport -> 0 => infeasible), unit/dimension checks, monotonicity, hand-calculated points, refusal paths."}, {"key": "INTERSTAGE", "title": "Lane 18 \u2014 Pre-ionizer -> Hall interstage physics (common model/schema)", "allowed": ["abep_sim/interstage.py", "schemas/architecture_comparison/interstage_v1.schema.json", "docs/architecture_comparison/interstage/**", "tests/test_interstage.py"], "prompt": "PRIORITY. Common model and schema for the transfer of plasma/gas from an RF or ECR pre-ionizer into the downstream Hall channel (the same model for rf_hall and ecr_hall; hall_only has no interstage). New pure module abep_sim/interstage.py (explicit inputs, no defaults, raise on missing/invalid) computing, for a given source exit state (ion densities by species and charge state, electron temperature, neutral densities, flows) and interstage geometry (length, cross-section, wall material, magnetic field if any): ion wall loss (Bohm flux to walls; magnetized/unmagnetized cases), volume and wall recombination (electron-ion; dissociative recombination for N2+, O2+ with sourced rate coefficients or TBD), neutral transport and pressure drop (molecular/transitional-flow conductance with sourced formulas), charge-state fraction evolution, ion transport efficiency eta_transport, neutral loss, plume/leakage losses at the junction, and energy losses \u2014 with particle, charge and energy conservation checked (residual reported; conservation is a gate, CLAUDE.md rule 4). Rate coefficients and formulas must be cited from open literature with evidence class; values not available are TBD and the function refuses until they are supplied. schemas/architecture_comparison/interstage_v1.schema.json for inputs/outputs; docs/architecture_comparison/interstage/INTERSTAGE_MODEL.md with equations, sources, validity domain (pressure/Knudsen regime), and why eta_transport may be the decisive RF/ECR variable (connect to the break-even lane's required eta_transport). No claim that RF or ECR is better. State milestone A/B/C support. Test tests/test_interstage.py: conservation residuals ~0, limiting cases (zero length => eta_transport = 1 and no losses; closed channel => no transmission), hand-calculated Bohm flux and conductance points, refusal paths."}, {"key": "PPUMAG", "title": "Lane 20 \u2014 PPU + magnet electrical closure (DC-bus data and magnet power model)", "allowed": ["abep_sim/magnet_power.py", "docs/architecture_comparison/electrical_closure/**", "schemas/architecture_comparison/electrical_closure_v1.schema.json", "tests/test_electrical_closure.py"], "prompt": "PRIORITY. Provide the data and models that the common bus-power boundary (abep_sim/arch_boundary.py, BOUNDARY_VERSION 'bus_power_boundary_v1', components hall_discharge, hall_magnet, cathode_keeper, cathode_heater, flow_control, compressor, thermal_control, housekeeping, rf_source, ecr_source, ecr_magnet; built by another lane \u2014 do not create it) needs to give the REAL T/P_bus instead of discharge-only performance. (1) New pure module abep_sim/magnet_power.py: electromagnet power from required magnetic field (ampere-turns for a magnetic circuit with gap and core; coil resistance from wire gauge, length, fill factor and temperature-dependent copper resistivity; I^2R), and permanent-magnet option (0 W electrical, mass instead), with all inputs explicit and no defaults; equations cited. (2) docs/architecture_comparison/electrical_closure/electrical_closure_data_v1.json (schema schemas/architecture_comparison/electrical_closure_v1.schema.json): evidence-backed conversion efficiencies and auxiliary powers per boundary component from open published sources \u2014 Hall discharge PPU efficiency at the relevant power class, magnet supply efficiency, RF generator DC-to-RF efficiency (and matching/cable losses), microwave source DC-to-RF efficiency (magnetron vs solid state), cathode heater and keeper power (Xe LaB6 at the relevant current class), flow-control/valve power, compressor electrical power (from the repository's compressor.py model if it exposes one, else TBD), housekeeping \u2014 each with source, evidence class, applicability (power class, frequency), uncertainty; these are DATA for callers, never code defaults. (3) docs/architecture_comparison/electrical_closure/ELECTRICAL_CLOSURE.md: how to assemble a full DC-bus ledger for each architecture with the data, which items dominate uncertainty, and a worked example that uses only sourced numbers or clearly marked analysis ranges (not predictions). State milestone A/B/C support. Test tests/test_electrical_closure.py: magnet power hand calculations, temperature dependence, refusal paths, data file schema validation, every entry sourced."}]}

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
  evidence: `EVIDENCE LENS. Open every deliverable. (a) Spot-check at least 6 cited sources with WebSearch/WebFetch (load via ToolSearch): DOI/URL resolves, title/authors/year match, the cited value/range plausibly appears there when accessible (abstract-only labelled). Fabricated or mis-attributed citations are BLOCKERS. (b) Every numeric value has a source + evidence class or is TBD/verify; invented-looking numbers or hidden defaults are major. (c) Values taken from repository files/modules: open them and confirm. (d) Any architecture-winner claim, transport admission, use of screening candidates as performance, or demonstrated-closure claim is a BLOCKER. (e) Physics/equations: check derivations and units; wrong physics is major.`,
  rules: `RULES/RECOMPUTE LENS. (a) SCOPE: git -C <worktree> diff --name-only ${BASE}...HEAD within ALLOWED paths; no forbidden file touched; no uncommitted leftovers. (b) RECOMPUTE: for headline numbers derived from repository data or equations, write your own independent Python (do not reuse the lane's code) and compare; mismatch beyond rounding is major. (c) CORRECTNESS: JSON/schemas parse and validate; code consistent with the modules/fields it references (grep them); no hidden defaults; refusal paths raise; run ONLY the lane's own test file(s): they must pass and test something meaningful. (d) RULES: the three architecture ids used exactly; shared naming contracts respected; milestone A/B/C statement present; PROPOSED/DRAFT markers where required; no winner, no retuning. (e) USEFULNESS: every required deliverable in the brief present and substantive; the 'unlocks' claims are justified.`,
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

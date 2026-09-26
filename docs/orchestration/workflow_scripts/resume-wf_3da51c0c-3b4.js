export const meta = {
  name: 'abep-lanes-v3-deps',
  description: 'Architecture Decision Acceleration lanes: isolated worktrees, dependency-triggered fan-out, two-lens adversarial verification, up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane; dependent lanes start when prerequisites finish' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "c53b75a", "lanes": [{"key": "FEED", "title": "Lane 16 \u2014 Thruster feed-envelope definition", "allowed": ["scripts/architecture/build_feed_envelope.py", "schemas/architecture_comparison/feed_envelope_v1.schema.json", "docs/architecture_comparison/feed_envelope/**", "tests/test_feed_envelope.py"], "prompt": "PRIORITY. Define the common feed state delivered to the ionization/discharge block (at the valve outlet, after intake -> filter -> compressor -> atmospheric gas chamber/buffer -> valve; plus the Xe path) for 180, 200 and 230 km and low / mean / high atmosphere, so the three architectures are compared at identical feed conditions. Use ONLY the existing frozen/validated repository chain: abep_sim/atmosphere.py (frozen NRLMSIS dataset; find which solar/geomagnetic activity levels it supports and map them to low/mean/high with provenance), abep_sim/intake.py / intake_tpmc.py (TPMC ROM), compressor.py, reservoir.py, and archengine.py only to find how they are chained (read; do not modify). Write scripts/architecture/build_feed_envelope.py (deterministic, < 1 min, no Julia) producing docs/architecture_comparison/feed_envelope/feed_envelope_v1.json and FEED_ENVELOPE.md, validated by schemas/architecture_comparison/feed_envelope_v1.schema.json: per (altitude, atmosphere level, orbit-averaged vs extremes where the modules support it): mass flow rate mdot [kg/s], pressure p [Pa], temperature T [K], species mole fractions x_s (N2, O, O2, and any other species the modules carry), with the module/function and inputs that produced each value, and the evidence class (model-derived) and the uncertainty the modules expose. Where the chain needs design inputs that are not fixed (intake area, compressor ratio, buffer volume, valve setting), expose them as explicit named inputs of the script (no hidden defaults) and produce the envelope for the repository's documented baseline values ONLY if they are documented with provenance in the repository; otherwise mark the quantity TBD and state which design input is missing. Align field names with the upstream ICD lane (schemas/interfaces/ in another worktree, read-only) where it exists. State which milestone (A/B/C) this supports. Test tests/test_feed_envelope.py: the script reproduces the committed JSON, schema validation, mass-fraction closure (sum x_s = 1), and refusal when a required design input is missing."}, {"key": "HALLREF", "title": "Lane 17 \u2014 Common Hall accelerator reference (interfaces)", "allowed": ["docs/architecture_comparison/hall_reference/**", "schemas/architecture_comparison/hall_reference_v1.schema.json", "tests/test_hall_reference.py"], "prompt": "Define ONE downstream Hall accelerator reference that is identical for hall_only, rf_hall and ecr_hall, so the RF/ECR comparison changes only the pre-ionization method. This is an INTERFACE definition for Vyovrinda's own thruster, not P5: never adopt P5 geometry or P5 B(z) as Vyovrinda's design. Deliverables: docs/architecture_comparison/hall_reference/HALL_ACCELERATOR_REFERENCE.md and hall_reference_v1.json (schema schemas/architecture_comparison/hall_reference_v1.schema.json) with: geometry interface (channel mean radius, width, length, anode position, exit plane, material; values TBD or owner-decided ranges, with sizing relations cited from open Hall-scaling literature as evidence, not as decisions); B(z) interface (parametrization compatible with the repository's B-field handling \u2014 read hallthruster_bridge/bfield/ and the HallThruster.jl case format used by the bridge, read-only \u2014 B_max, peak location, shape family; values TBD); discharge-voltage range (a PROPOSED range with rationale tied to the 12-25 mN / <1.5 kW envelope and sources); cathode interface (Xe-fed LaB6 per RFP context: electron current, flow, keeper; values TBD pending the cathode lanes); wall/life interface (fields that must match hallthruster_bridge/hall_map_schema_v1.json and abep_sim/hall_map.py REQUIRED_FIELDS, incl. wall_life_trustworthy semantics); the pre-ionizer injection interface (where RF/ECR ions/neutrals enter: anode/gas-distributor plane, charge-state and velocity distribution fields matching the interstage lane); and an invariance rule list (what may never differ between arms). State milestone A/B/C support. Test tests/test_hall_reference.py: schema validation; the wall/life field names exist in hall_map_schema_v1.json; every numeric value sourced, PROPOSED or TBD; the invariance list covers geometry, B(z), voltage set and cathode."}, {"key": "GRID", "title": "Lane 23 \u2014 Operating-envelope comparison grid (common for all three architectures)", "deps": ["FEED", "HALLREF"], "allowed": ["scripts/architecture/build_comparison_grid.py", "schemas/architecture_comparison/comparison_grid_v1.schema.json", "docs/architecture_comparison/comparison_grid/**", "tests/test_comparison_grid.py"], "prompt": "PRIORITY. Predefine ONE common comparison grid used identically for hall_only, rf_hall and ecr_hall, so later comparisons are automatic and no architecture gets favourable points. Axes: feed state taken from the feed-envelope lane (mdot, p, composition x_s, per altitude/atmosphere level \u2014 reference the prerequisite's JSON by repository path and read its values from its worktree now), discharge voltage V_d (levels from the Hall accelerator reference lane's PROPOSED range), pre-ionizer source power P_source (0 for hall_only; the SAME level set for rf_hall and ecr_hall, bounded by the <1.5 kW bus limit), and Xe/air mode (Xe start, mixed, atmosphere-dominant) where the dual-feed concept requires it. Write scripts/architecture/build_comparison_grid.py producing docs/architecture_comparison/comparison_grid/comparison_grid_v1.json (+ schema, + COMPARISON_GRID.md): the full point list with ids, which architectures are evaluated at each point, the rule that every architecture is evaluated at every applicable point (no per-architecture cherry-picking), how grid levels were chosen (each level sourced, PROPOSED or TBD), and a freeze procedure (DRAFT_PENDING_OWNER; hash-lock before any comparison run). If a prerequisite value is TBD, the dependent grid level is TBD (never invented). Calibration nuisance is never an axis. State milestone A/B/C support. Test tests/test_comparison_grid.py: reproducibility, schema validation, identical point sets across architectures (except P_source = 0 for hall_only), no nuisance axis, hash of the grid recorded."}]}

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

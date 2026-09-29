export const meta = {
  name: 'abep-lanes-v3-deps',
  description: 'Architecture Decision Acceleration lanes: isolated worktrees, dependency-triggered fan-out, two-lens adversarial verification, up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane; dependent lanes start when prerequisites finish' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "c53b75a", "lanes": [{"key": "MINEXP", "title": "Lane 25 \u2014 Minimum decisive Hall-only / RF+Hall / ECR+Hall experiment", "allowed": ["docs/architecture_comparison/minimum_decisive_experiment/**", "tests/test_minimum_decisive_experiment.py"], "prompt": "PRIORITY. Design the SMALLEST experiment that can settle the Hall-only vs RF+Hall vs ECR+Hall ambiguity if literature/model evidence remains insufficient, using the same Hall accelerator and the same feed state for all arms (the pre-ionizer is the only change). Build it around the break-even logic: the decisive quantities are the source's delivered ion current and bus power, the interstage transport efficiency, and the change of Hall discharge current / thrust at fixed V_d, mdot and composition, all on the common DC bus boundary (bus_power_boundary_v1). Deliverables: docs/architecture_comparison/minimum_decisive_experiment/MINIMUM_DECISIVE_EXPERIMENT_DRAFT.md and experiment_draft.json (status DRAFT_PENDING_OWNER): the minimal operating-point set (few points chosen to straddle the break-even surface, taken from the common comparison-grid concept \u2014 axes mdot, p, V_d, composition, P_source; values TBD where the feed envelope must supply them), the exact measurements and instruments (thrust balance, bus-level DC power meters per consumer, ion current / Faraday / retarding-potential or E x B for the interstage, pressure gauges, species if possible), uncertainty targets derived from what is needed to resolve the break-even inequality (show the propagation), randomisation and repeatability, facility controls (background pressure; the P5-N2 lesson that facility interpretation is a nuisance), a sequential decision tree with stopping rules (e.g. stop the RF arm if the measured delivered ion cost exceeds the break-even cost at all tested points, with the rule PROPOSED for the owner), and a pre-registration step before any measurement. Minimum hardware list and what could be done at a university facility (e.g. an IIST discussion) vs what needs a larger chamber \u2014 factual, sourced where possible, no commitments on behalf of anyone. Relate to (reference only, do not edit) docs/architecture_comparison/experiment_protocol/ (full protocol lane) and docs/experiments/ (IIST package lane). State milestone A/B/C support (this is the fastest physical route to milestone A/B). Test tests/test_minimum_decisive_experiment.py: schema-like validation of the JSON, every threshold PROPOSED, identical accelerator/feed across arms, uncertainty propagation reproduces its stated numbers."}, {"key": "CATHINT", "title": "Lane 19 \u2014 Neutralizer/cathode system integration for the three architectures", "allowed": ["abep_sim/cathode_integration.py", "docs/architecture_comparison/cathode_integration/**", "tests/test_cathode_integration.py"], "prompt": "System integration of the neutralizer/cathode for hall_only, rf_hall and ecr_hall (Xe-fed LaB6 per the RFP context; alternatives only as evidence notes, no new propulsion families): electron-current requirement (discharge current and neutralization of the beam; for rf_hall/ecr_hall, any additional electron current demanded or supplied by the pre-ionizer plasma and interstage), Xe flow required (cathode flow fraction relations from open literature), heater and keeper power (startup and steady), emitter temperature and life (LaB6 evaporation-limited life relations), poisoning/contamination by O, O2, N2 backflow and ambient atomic oxygen (evidence and thresholds), startup sequence per architecture and its bus-power transient, and the Xe mass implication over the mission (26,000 h; firing > 15,000 h) as a function of inputs. New pure module abep_sim/cathode_integration.py (explicit inputs, no defaults, raise on missing) returning per-architecture electron current, Xe flow, keeper/heater power at the bus boundary components cathode_keeper and cathode_heater, and life margin given sourced relations; docs/architecture_comparison/cathode_integration/CATHODE_INTEGRATION.md + cathode_integration_data_v1.json (sourced parameters with evidence classes). If the cathode evidence dossier lane (docs/evidence/cathode/ in another worktree) exists, read it READ-ONLY and reference it; do not duplicate it. Make explicit whether the cathode penalty differs between architectures and when it could dominate (e.g. Xe consumption vs mission Xe budget) \u2014 as conditional statements with inputs, not conclusions. State milestone A/B/C support. Test tests/test_cathode_integration.py: hand calculations, conservation of current, refusal paths, sourced data file validation."}, {"key": "MASS", "title": "Lane 21 \u2014 Architecture mass BOM skeleton (CBE / MGA / MEV)", "allowed": ["abep_sim/mass_bom.py", "schemas/architecture_comparison/mass_bom_v1.schema.json", "docs/architecture_comparison/mass_bom/**", "tests/test_mass_bom.py"], "prompt": "Same mass accounting for hall_only, rf_hall and ecr_hall to identify architectures that cannot plausibly stay below 40 kg (MEV) before detailed design. New pure module abep_sim/mass_bom.py: BOM tree per architecture (common items: intake, filter, compressor, atmospheric gas chamber, valves, Xe tank + Xe, Hall thruster head, magnets, cathode, PPU, harness, thermal hardware, structure; architecture-specific: RF source + RF generator + matching network; ECR source + microwave source + waveguide + ECR magnets), each item with CBE mass (sourced value, scaling relation with sourced inputs, or TBD), maturity category and the mass-growth allowance (MGA) from an open published margin philosophy (cite it, e.g. an openly available ESA/NASA margin document; if you use AIAA S-120A values, only via an openly accessible source that reproduces them, else TBD), system margin (PROPOSED), MEV = CBE x (1 + MGA) + system margin; refuse (ValueError) when an item is TBD unless the caller explicitly requests a partial roll-up that lists missing items. schemas/architecture_comparison/mass_bom_v1.schema.json; docs/architecture_comparison/mass_bom/MASS_BOM.md + mass_bom_v1.json with every item's provenance, and a 'plausibility screen' that computes, from sourced lower bounds only, whether any architecture's MINIMUM plausible MEV already exceeds 40 kg (a milestone-A elimination tool feeding the hard-gate matrix mass gate); if lower bounds are unavailable, say so. The Hall-related masses must not use unadmitted closures. State milestone A/B/C support. Test tests/test_mass_bom.py: roll-up arithmetic, MGA application, refusal with TBD items, identical common items across architectures, schema validation."}, {"key": "SCALING", "title": "Lane 22 \u2014 Scaling/similarity audit: P5 evidence -> 12-25 mN Vyovrinda thruster", "allowed": ["scripts/architecture/scaling_similarity.py", "docs/architecture_comparison/scaling/**", "tests/test_scaling_similarity.py"], "prompt": "Prevent validating P5 physics and then extrapolating it blindly to Vyovrinda's own geometry. Using the repository's P5 records (hallthruster_bridge/identification/, bfield/, cases/p5_n2.json \u2014 read-only; P5 geometry/B as documented there with provenance) and open Hall-scaling literature (e.g. scaling relations for Hall thrusters: channel dimensions vs power/thrust, current density, magnetic field; ionization mean free path vs channel length (Melikov-Morozov type criterion); electron Larmor radius vs channel width; Hall parameter; neutral density and residence time; power density and wall heat flux; N2 vs Xe ionization length at the relevant T_e), write scripts/architecture/scaling_similarity.py that computes the dimensionless/similarity groups for P5 at its N2 and Xe points (model-derived where they need plasma parameters, stating which) and for the Vyovrinda 12-25 mN / < 1.5 kW class over a PARAMETER RANGE (sizing from sourced scaling relations \u2014 labelled analysis ranges, not a design), and produces docs/architecture_comparison/scaling/SCALING_SIMILARITY.md + scaling_similarity.json: which groups match or diverge (by how much), which P5-derived conclusions are likely transferable (mechanism-level) and which are not (e.g. anomalous-transport closures are geometry/B-dependent), and what the transport-closure admission would need in order to be applied to Vyovrinda geometry (the 'design-specific Hall maps' step in CLAUDE.md). Transfer risk flags per quantity; no claim that a closure transfers. State milestone A/B/C support. Test tests/test_scaling_similarity.py: script reproduces JSON, dimensionless groups hand-checked, P5 inputs match repository files."}]}

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

export const meta = {
  name: 'abep-lanes-v2',
  description: 'Build ABEP work lanes in isolated worktrees; two-lens adversarial verification (evidence + rules/recompute); up to two repair rounds',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "daa0e759e26416847f200a4781194f266be27c5c", "lanes": [{"key": "XPROT", "title": "Hall-only vs RF+Hall vs ECR+Hall common-condition experiment protocol (DRAFT)", "allowed": ["docs/architecture_comparison/experiment_protocol/**", "tests/test_architecture_experiment_protocol.py"], "prompt": "Freeze, as a DRAFT_PENDING_OWNER protocol, the exact common-condition experimental comparison of three ionization architectures feeding the same Hall acceleration stage: Hall-only, RF pre-ionizer + Hall, ECR pre-ionizer + Hall. Requirements: identical propellant composition and total mass flow (anode + any pre-ionizer + cathode flows each accounted), identical Hall channel, magnetic configuration, discharge-voltage set and cathode (Xe-fed LaB6 per the RFP context unless the owner decides otherwise), identical facility and background-pressure measurement, identical diagnostics; the pre-ionizer is the ONLY change. Bus-power accounting at the DC input bus boundary for every consumer (Hall PPU input incl. conversion efficiency, magnet supplies, RF generator DC input incl. matching-network and cable losses, microwave source DC input, cathode heater and keeper, valves/flow control, thermal control, housekeeping), measured with stated instruments and uncertainty targets; the same boundary definition must be used for all three architectures (a separate lane defines abep_sim/arch_boundary.py with BOUNDARY_VERSION 'bus_power_boundary_v1'; reference that name and keep your boundary list consistent with it; do not import it). Test matrix: operating points (propellants N2, O2/N2 mixtures, Xe reference; flows; voltages) as parameters with values TBD where the upstream ICD must supply them (do not invent intake-delivered flows); randomisation/order, repeatability, facility-effect controls (background pressure sweep), sustainment/extinction criteria, stability metrics; decision metrics (thrust per bus power, ion current per bus power, mass utilization, stability, ignition reliability) with PROPOSED acceptance thresholds each marked as a proposal for the owner, and a pre-registration step before any measurement. Align with the repository's other experiment material in docs/experiments/ if present (reference only, do not edit). Deliverables: docs/architecture_comparison/experiment_protocol/EXPERIMENT_PROTOCOL_DRAFT.md and protocol_draft.json (+ protocol.schema.json). No claim that any architecture wins. Test tests/test_architecture_experiment_protocol.py: schema validation; the same bus-boundary component list applies to all three arms; every threshold is marked PROPOSED; every numeric value sourced or TBD."}, {"key": "BUS", "title": "Common bus-power boundary for Hall-only / RF+Hall / ECR+Hall (pure module, not wired)", "allowed": ["abep_sim/arch_boundary.py", "schemas/architecture_comparison/**", "docs/architecture_comparison/power_boundary/**", "tests/test_arch_boundary.py"], "prompt": "Define ONE electrical boundary (the spacecraft DC bus input) used identically for Hall-only, RF+Hall and ECR+Hall, so no architecture is ever selected on discharge-only power. INTERFACE CONTRACT (must be exactly this; a separate lane builds a harness against it): new pure module abep_sim/arch_boundary.py exposing BOUNDARY_VERSION = 'bus_power_boundary_v1'; ARCHITECTURES = ('hall_only', 'rf_hall', 'ecr_hall'); REQUIRED_COMPONENTS: dict architecture -> tuple of component keys (common components identical across all three, plus exactly the architecture-specific pre-ionizer components; e.g. hall_discharge, hall_magnet, cathode_keeper, cathode_heater, flow_control, compressor, thermal_control, housekeeping, rf_source for rf_hall, ecr_source and ecr_magnet for ecr_hall \u2014 finalise and document); def bus_power_ledger(arch: str, loads: dict, efficiencies: dict) -> dict where loads maps component -> delivered load-side power [W] and efficiencies maps component -> DC-bus-to-load conversion efficiency in (0, 1]; returns {'boundary_version', 'architecture', 'P_bus_W', 'items': [{'component', 'P_load_W', 'efficiency', 'P_bus_W', 'P_loss_W'}], 'residual_W'} with residual_W = P_bus_W - sum(items P_bus_W) (must be ~0; conservation is a gate, CLAUDE.md rule 4); raises ValueError for an unknown architecture, a missing or extra component, a missing efficiency, an efficiency outside (0, 1], a negative or non-finite load. NO default efficiencies or loads anywhere in the module (no silent fallbacks; a permanent-magnet ecr_magnet must be passed explicitly as 0 W with efficiency 1). Also: schemas/architecture_comparison/bus_power_boundary_v1.json (JSON Schema of the ledger output and inputs); docs/architecture_comparison/power_boundary/BUS_POWER_BOUNDARY.md documenting each component, what is inside/outside the boundary, and a DISCREPANCY AUDIT of the existing abep_sim/archengine.py energy ledger against this boundary (read it; list with file:line which consumers it includes/excludes and how it treats pre-ionizer power; do NOT modify archengine.py \u2014 changing it would be a model change); an evidence table of conversion efficiencies found in open published sources (PPU, RF generator, microwave source, magnet supplies) with evidence classes, or TBD \u2014 these are data for callers, NOT defaults in code. Test tests/test_arch_boundary.py: conservation (residual ~0), every refusal path, identical common components across architectures, no defaults (calling with a missing efficiency raises)."}, {"key": "HARN", "title": "System-level architecture comparison harness (drop-in for admitted Hall closures; not wired)", "allowed": ["abep_sim/arch_compare.py", "docs/architecture_comparison/harness/**", "tests/test_arch_compare.py"], "prompt": "Prepare the comparison engine so admitted Hall closures can be dropped in later without further architecture-code work. New module abep_sim/arch_compare.py (pure orchestration; does NOT modify archengine.py, hall_map.py, hall_ensemble.py or goldens). It compares architectures ('hall_only', 'rf_hall', 'ecr_hall') on a COMMON electrical boundary via a bus-power ledger callable with the exact signature ledger(arch: str, loads: dict, efficiencies: dict) -> dict returning {'boundary_version', 'architecture', 'P_bus_W', 'items', 'residual_W'} (a separate lane implements abep_sim/arch_boundary.bus_power_ledger with BOUNDARY_VERSION 'bus_power_boundary_v1'; that module does NOT exist in your worktree: resolve it lazily by import at call time when no ledger is injected, and raise a clear error if it is missing \u2014 never fall back). Hall performance must come from abep_sim.hall_map.HallMap for ADMITTED ensemble members only: call abep_sim.hall_ensemble.require_admitted(member_id) for every member before use (read both modules; use their real API names). The harness iterates over ALL admitted members (unweighted scenario set, CLAUDE.md next-work 1) and returns per-member, per-architecture results plus envelopes (min/max across members) \u2014 never a probability-weighted answer and never a single 'winner' field; it must REFUSE to run when there are zero admitted members (the current state: credible set is empty) with a clear error, no fallback. Upstream intake/compressor quantities are inputs from existing modules (read abep_sim/intake.py, compressor.py, archengine.py to find the right entry points) or explicit arguments; the harness never lets Hall-closure uncertainty leak upstream (CLAUDE.md scope rule) and never uses layer-1 calibration nuisance as an axis. Energy-ledger residual must be checked (< 2 %, CLAUDE.md rule 4) and reported. docs/architecture_comparison/harness/HARNESS.md: design, inputs/outputs, the exact drop-in procedure once members are admitted (admission record -> HallMap per member -> harness), and what is still missing. Test tests/test_arch_compare.py: refusal with zero admitted members against the REAL ensemble file; refusal of screening candidate ids; envelope aggregation and ledger-residual checks using clearly test-only synthetic providers injected in the test (never shipped as defaults); no 'winner' output."}, {"key": "THL", "title": "Thermal / life accounting framework (magnets, RF coil/coupler, ECR magnets, Hall walls, cathode)", "allowed": ["abep_sim/thermal_life.py", "schemas/thermal_life/**", "docs/thermal_life/**", "tests/test_thermal_life_framework.py"], "prompt": "Pre-build the heat and life accounting so an architecture that closes on power can be checked for thermal/life feasibility. New pure module abep_sim/thermal_life.py (not wired into archengine): per-component heat-source accounting (Hall electromagnet coil I^2R with temperature-dependent copper resistivity; Hall wall heat flux as an input from HallMap fields when available (read hallthruster_bridge/hall_map_schema_v1.json / abep_sim/hall_map.py field names; do not invent them); RF coil/antenna copper loss and coupler/dielectric heating as fractions of RF power that are INPUTS; ECR permanent-magnet temperature margin versus the material's maximum operating temperature and reversible/irreversible loss behaviour; cathode emitter/heater heat), limits as sourced data (magnet wire insulation classes, NdFeB vs SmCo maximum operating temperatures and temperature coefficients, boron-nitride wall limits, LaB6 emitter temperature and life relations) with evidence classes in schemas/thermal_life/limits_v1.json, and a feasibility check that returns margins per component and REFUSES (ValueError) when any required input or limit is missing (no defaults; radiator/rejection capability is an input TBD from geometry). docs/thermal_life/THERMAL_LIFE_FRAMEWORK.md: scope, equations with sources, what inputs each component needs and from which lane/module they will come (bus-power boundary components, HallMap wall flux, cathode dossier), what remains TBD. Coordinate naming with the bus-power boundary components (hall_discharge, hall_magnet, cathode_keeper, cathode_heater, rf_source, ecr_source, ecr_magnet) without importing that module. Test tests/test_thermal_life_framework.py: equations reproduce hand calculations, refusal paths, every limit sourced."}]}

const BASE = ARGS_EMBEDDED.base
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const COMMON = `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep; primary checkout /home/user/abep). You run in an ISOLATED git worktree created for you (your current working directory); do all edits there. Base commit: ${BASE} (main after PR #30).

CONTEXT (read CLAUDE.md in your worktree first):
- The pre-registered P5-N2 v1 vacuum validation is FINAL: all 9 SGB screening candidates INCONCLUSIVE / NOT ELIGIBLE (not rejected); 1428 of 2160 run x reading evaluations OUT_OF_DOMAIN (chemistry tables used beyond their validity limit), 700 FAIL_VALIDATION, 32 PASS, 0 NUMERICAL_FAILURE; credible set = empty; gate 3 FAIL. Frozen files: hallthruster_bridge/validation/p5_n2_campaign_v1_vacuum_raw.jsonl.gz (1080 records), ..._scores.json (official per-run statuses), ..._scores_report.md, ..._scores_decision.json, VALIDATION_RELEASE_v1.json. The v1 outcome is PERMANENT and is never rewritten.
- Pre-registered follow-on runs (O4 staged sensitivities, then 1080 facility runs) are RUNNING in the background on every CPU core under ${SP}/followon and ${SP}/wt_followon — NEVER read, list, modify or touch those paths.
- Earlier non-gating forensic notes (unreviewed unless stated) may exist read-only under ${SP}/forensics/ — you may read them as cross-checks, never as authority; recompute anything you report.

HARD RULES (breaking any = lane rejected):
1. Modify/create files ONLY under your lane's ALLOWED paths (listed below). NEVER modify: hallthruster_bridge/prereg/**, hallthruster_bridge/campaign/**, hallthruster_bridge/propellants/** (incl. rate_validity.toml), hallthruster_bridge/audit/**, hallthruster_bridge/ensemble/**, hallthruster_bridge/validation/**, hallthruster_bridge/cases/**, bridge_lib.jl, PINNED.toml, the frozen scorer/gate/freeze/report/release/staged scripts (scripts/score_p5_n2_*.py, scripts/audit_p5_n2_campaign_records.py, scripts/freeze_p5_n2_dataset.py, scripts/report_p5_n2_campaign.py, scripts/make_validation_release.py, scripts/make_p5_n2_launch_manifests.py), abep_sim/archengine.py, abep_sim/hall_ensemble.py, abep_sim/hall_map.py, abep_sim/data/**, docs/HISTORY.md, CLAUDE.md, README.md, tests/test_sim.py.
2. Evidence discipline (CLAUDE.md rules 6 and 10, docs/EVIDENCE.md): never invent numbers, sources, page/table numbers or DOIs. Every numeric value carries a source and an evidence class (measured / digitized / inferred / reconstructed / model-derived / assumed) or is explicitly "TBD — requires <what>". Numbers computed from repository data must be produced by a script you commit (deterministic, re-runnable).
3. Sources: published / openly accessible only; do not contact any person or lab; no email; do not use LXCat; do not bypass paywalls or bot challenges (abstract-only access must be labelled as such); never change TLS/trust settings. Cite DOIs/URLs you actually accessed (WebSearch/WebFetch are deferred tools: load them with ToolSearch). Anything from memory is marked "verify". The ECHT thesis (CC BY-NC-ND) is never redistributed; cite numbers only.
4. CPU: do NOT run Julia, do NOT run the full test suite, do NOT run long computations (> 1 min). Run only your own new test file (python -m pytest -q <your test file>) and quick scripts.
5. No retuning of any transport/chemistry parameter, no proposal to change criteria/tolerances/limits of v1, no re-scoring or re-labelling of any v1 run (read official statuses from the scores file), no "would pass if", no words like "best candidate"/"recommended candidate"/"promote" for screening candidates. Do not claim demonstrated ABEP closure, an architecture winner, or any transport admission. Never extend a rate-table validity limit merely because the solver reached a higher T_e; any extension needs independent published evidence and is a DRAFT for the owner only.
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
    open_questions_for_owner: { type: 'array', items: { type: 'string' } },
    tests_run: { type: 'string' }, tests_passed: { type: 'boolean' },
  },
  required: ['worktree_path', 'branch', 'commit', 'files', 'summary', 'key_findings', 'open_questions_for_owner', 'tests_passed'],
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
  evidence: `EVIDENCE LENS. Open every deliverable. (a) Spot-check at least 6 cited sources with WebSearch/WebFetch (load via ToolSearch): the DOI/URL resolves, title/authors/year match, and the cited value/range plausibly appears there when accessible (abstract-only must be labelled). Fabricated or mis-attributed citations are BLOCKERS. (b) Every numeric value has a source + evidence class or is TBD/verify; invented-looking numbers are major. (c) Values taken from repository files: open those files and confirm they match. (d) Any claim of a v1 result change, transport admission/promotion, architecture winner, demonstrated closure, or a validity-limit extension presented as decided is a BLOCKER.`,
  rules: `RULES/RECOMPUTE LENS. (a) SCOPE: git -C <worktree> diff --name-only ${BASE}...HEAD — every changed path within ALLOWED paths; no forbidden file touched; no uncommitted leftovers (git status). (b) RECOMPUTE: for every headline number derived from repository data, write your own short independent Python (do NOT reuse the lane's script) against the frozen inputs and compare; any mismatch beyond rounding is major. (c) CORRECTNESS: JSON/TOML parse; code is consistent with the repository modules/fields it references (grep them); run ONLY the lane's own test file; it must pass and must actually test something meaningful. (d) RULES: no retuning suggestions, no v1 re-scoring/re-labelling, no forbidden wording ("best/recommended candidate", "promote", "would pass if"), DRAFT/proposal markers present where the brief demands them, v1 described as permanent. (e) USEFULNESS: every required deliverable in the brief is present and substantive.`,
}
const verifyPrompt = (lane, res, lens) => `You are an ADVERSARIAL reviewer. Default to finding problems; pass only if there are no blocker or major issues under your lens.
Repository: ABEP-VLEO simulator. Lane "${lane.key} — ${lane.title}" was built in worktree ${res.worktree_path} (branch ${res.branch}, commit ${res.commit}), base ${BASE}. Work READ-ONLY in that directory (cd there); write any scratch scripts only under ${SP}/verify_${lane.key}_${lens}/. Never read or touch ${SP}/followon or ${SP}/wt_followon. Do NOT run Julia or the full test suite.
Lane brief: ${lane.prompt}
ALLOWED paths for this lane: ${lane.allowed.join(', ')}
${LENSES[lens]}
Return pass=true only if no blocker/major issues remain.`

const fixPrompt = (lane, res, issues) => `Repair lane "${lane.key} — ${lane.title}" in its existing worktree ${res.worktree_path} (cd there; do NOT create a new worktree; stay on branch ${res.branch}).
${COMMON.split('YOUR LANE:')[0]}
Lane brief: ${lane.prompt}
ALLOWED paths: ${lane.allowed.join(', ')}
Independent adversarial reviewers reported these issues — fix every blocker and major one (and minors where cheap). If a flagged claim cannot be sourced, mark it TBD/verify or remove it rather than inventing support. If a number did not reproduce, find the true value and fix the script and text. If something was changed outside ALLOWED paths, revert it (git checkout ${BASE} -- <path> or delete new files).
ISSUES: ${JSON.stringify(issues)}
Commit the repair as a new commit in the same worktree (same trailer lines). Report as before.`

async function verifyBoth(lane, res, round) {
  const vs = await parallel(['evidence', 'rules'].map(lens => () =>
    agent(verifyPrompt(lane, res, lens), { label: `verify${round}:${lane.key}:${lens}`, phase: 'Verify', schema: VERDICT })))
  const ok = vs.filter(Boolean)
  const issues = ok.flatMap(v => v.issues || [])
  return { pass: ok.length === 2 && ok.every(v => v.pass), issues, verdicts: ok }
}

const lanes = ARGS_EMBEDDED.lanes
const results = await pipeline(
  lanes,
  lane => agent(COMMON + `${lane.key} — ${lane.title}\n${lane.prompt}\nALLOWED paths: ${lane.allowed.join(', ')}`,
    { label: `build:${lane.key}`, phase: 'Build', isolation: 'worktree', schema: RESULT }),
  async (res, lane) => {
    if (!res) return null
    let cur = res, v = await verifyBoth(lane, cur, 1), rounds = 0
    while (!v.pass && rounds < 2) {
      rounds++
      const fx = await agent(fixPrompt(lane, cur, v.issues), { label: `fix${rounds}:${lane.key}`, phase: 'Fix', schema: RESULT })
      if (fx) cur = fx
      v = await verifyBoth(lane, cur, rounds + 1)
    }
    return { res: cur, pass: v.pass, fix_rounds: rounds, open_issues: v.pass ? [] : v.issues }
  },
)
return results.map((r, i) => ({ lane: lanes[i].key, ...(r || { failed: true }) }))

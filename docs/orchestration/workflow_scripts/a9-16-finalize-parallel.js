export const meta = {
  name: 'a9-16-finalize-parallel',
  description: 'A9.16 finalize, parallel: regeneration split into disjoint lanes -> integrate + full suite -> 4 reviews -> repairs in parallel by area -> integrate + full suite',
  phases: [
    { title: 'Regenerate', detail: 'parallel lanes with disjoint paths' },
    { title: 'Integrate', detail: 'merge lanes, re-check every builder, full suite' },
    { title: 'Verify', detail: 'four adversarial lenses in parallel' },
    { title: 'Repair', detail: 'parallel repairs grouped by area, then integrate' },
  ],
}

// args = { base: '<sha>' }
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const TRAILER = `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FzUuRP7UUVEypuFNeEaN4U`
const RESULT = { type: 'object', properties: { commit: { type: 'string' }, applied: { type: 'array', items: { type: 'string' } },
  blocked: { type: 'array', items: { type: 'string' } }, tests: { type: 'string' } }, required: ['commit', 'applied', 'blocked', 'tests'] }
const FIND = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: {
  id: { type: 'string' }, severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, file: { type: 'string' },
  area: { type: 'string', enum: ['design', 'requirements_budgets', 'experiments_procurement', 'production_data_perf', 'other'] },
  description: { type: 'string' }, evidence: { type: 'string' }, fix_hint: { type: 'string' } },
  required: ['id', 'severity', 'file', 'area', 'description', 'evidence', 'fix_hint'] } } }, required: ['findings'] }

const common = (base) => `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep) in an ISOLATED git worktree (your cwd). FIRST: git reset --hard ${base}; confirm with git rev-parse HEAD. Read CLAUDE.md first. The base already contains: A9.16 steps 1+2, the three step-3 code lanes (design-layer architecture changes, RVM re-based on the registered RFP, Rust parity v2 prereg/report), A9.17 rebuilds (orbit atmosphere v1 csv.gz, HWM14 v2, sputter regen), the A9.18 golden replacement (abep_sim/data/golden_v2.json canonical; golden_v1.json history) and the CI rule-9 fix. Owner decisions: docs/decisions/OD_2026_10_01_A9_{8..18}_* (verbatim governs).
RULES: CLAUDE.md rules 1-10; never retune; never invent values; never weaken/skip tests (rule 9: exactly 5 SUPERSEDED skips + 1 strict xfail); never modify docs/decisions/**, CLAUDE.md, hallthruster_bridge/**, abep_sim/data/** frozen files (golden_v2.json only via python -m abep_sim.golden generate and only if a lane is explicitly allowed), immutable history (rfq_a9, rfq_a9_v2, owner_questions_state_v2..v4, mass_power_a9_v2, xe_accounting_a9_v2, parity v1 records, perf A9.7 baseline timings, dedicated baseline 2026-10-01 timings). Never run the v1 consolidated-questions builder (it rewrites an xlsx). No Julia.
Hygiene: affected builders --check and tests; git add + commit; message ends with exactly:
${TRAILER}
Do NOT push. Never touch ${SP}/followon or ${SP}/wt_followon. Return the structured result.

YOUR TASK: `

const REGEN = [
  { key: 'design', prompt: `REGENERATE THE DESIGN CHAIN (ALLOWED: docs/design_synthesis/**, docs/hardware/h1_freeze_candidate/**, docs/architecture/**, docs/architecture_comparison/** generated outputs and their builders' pin constants, tests of those artifacts only where a re-pin requires it). Run each builder --check and regenerate failing ones in dependency order F1 intake -> F2 filter -> F3 compressor -> F4 plenum -> F6 ICP geometry -> H-1 -> F7/F8 -> F9 freeze candidate; also architecture_comparison (compressor_downselect, feed_state closure / feed envelope) and docs/architecture/freeze_candidate. Builder TEXTS that still encode superseded owner rules must be updated (F7/F8 n_pareto_ge_0.38_mgps count and the F4 0.38 mg/s requirement sweep become characterization coverage only per A9.13 S6.21; INFEASIBLE_OUT_OF_DOMAIN wording -> NOT_EVALUATED_OUT_OF_DOMAIN per S6.8; F4 notes on G-05 now that size_orifice_for_pressure reports residuals). Report old -> new headline numbers: best delivered flow, robust set, compressor mass range, F1 intake C_D / CR at the F1-01 node, and the F9 parameters that changed.` },
  { key: 'records', prompt: `REGENERATE REQUIREMENTS / BUDGETS / INTEGRATION RECORDS (ALLOWED: docs/requirements/** (except the rfp_official clause transcription text), docs/experiments/hall_icp/integration/**, docs/budgets/** except immutable versions, docs/decisions/application/**, docs/procurement/rfq_a9_v3/**, docs/traceability/**, and tests of those artifacts only where a re-pin requires it). Run every builder under those paths with --check and regenerate failing ones (M16, RVM, owner questions state v5, application matrix, mass/power v3, xe accounting v3, RFQ v3, traceability RTM). Re-point anything citing golden_v1.json as the canonical golden to golden_v2.json (A9.18; golden_v1 stays as history). Update the application matrix so every A9.13/A9.14/A9.17/A9.18 item applied in step 3 / finalize is APPLIED with path + record id, or truthfully BLOCKED.` },
  { key: 'perf_ci', prompt: `PERFORMANCE / PARITY / CI LEFTOVERS (ALLOWED: docs/performance/** (NEW files only for history; never alter recorded timings), scripts/perf/profile_baseline.py only for the drift-reporting behaviour, scripts/verify_abep_core.py, abep_sim/design/tpmc_backend.py, tests/test_perf_baseline.py, tests/test_tpmc_backend.py, tests/test_a9_16_repair_readback.py). The historical A9.7 harness check fails because profiled sources changed under authorised model changes: never re-measure or fabricate timings; make the check report the drift explicitly (HISTORICAL_SOURCE_DRIFT with changed files and old/new sha256) instead of failing, and write docs/performance/dedicated_baseline_2026_10_01/DRIFT_AFTER_A9_9.json listing the drifted files (incl. abep_sim/golden.py) and stating that the owner rerun (A9.18 PERF_RERUN) is required before any Rust performance admission. Make verify_abep_core --check and tests/test_tpmc_backend.py consistent with the merged parity v2 records (read docs/performance/abep_core/parity_prereg_v2.json / parity_report_v2.json; v1 history unchanged). Fix tests/test_a9_16_repair_readback.py[profile_baseline.py] the same way (drift reported, not failing).` },
]

phase('Regenerate')
const lanes = await parallel(REGEN.map(l => () => agent(common(args.base) + l.prompt, { label: `regen:${l.key}`, phase: 'Regenerate', schema: RESULT, isolation: 'worktree' })))
const ok = lanes.map((r, i) => ({ key: REGEN[i].key, r })).filter(x => x.r && x.r.commit)
if (!ok.length) return { stopped: 'all regen lanes failed', lanes }

const integrate = (base, commits, label, extra) => agent(common(base) + `INTEGRATE: git merge --no-ff each of these commits in order: ${commits.join(', ')} (merge messages end with the two trailer lines). Resolve conflicts in GENERATED files by re-running their builders (never hand-edit), and docs/HISTORY.md by keeping both sides. Then run EVERY builder with --check (git ls-files '*build*.py', python -m abep_sim.golden check, python scripts/ci_checks.py, scripts/verify_abep_core.py --check) and regenerate anything still stale (ALLOWED: any generated artifact and pin outside the immutable list). Then the FULL suite once with --junitxml and python scripts/ci_checks.py --pytest-junit <xml>; also the pymsis-hidden leg (sitecustomize import blocker on PYTHONPATH) with --junitxml + --pytest-junit: both must give all pass, exactly 5 skipped, 1 xfailed. If anything still fails, fix its root cause (any allowed path) and rerun. ${extra || ''}`,
  { label, phase: 'Integrate', schema: RESULT, isolation: 'worktree' })

phase('Integrate')
const integ = await integrate(args.base, ok.map(x => x.r.commit), 'integrate:1')
if (!integ || !integ.commit) return { stopped: 'integration failed', lanes, integ }

phase('Verify')
const LENSES = [
  ['fidelity', 'DECISION FIDELITY for A9.8-A9.18 vs code/artifacts (verbatim text); nothing presented as PASS without determining evidence; owner numbers used correctly; deferred numbers not invented; application matrix truthful.'],
  ['physics', 'PHYSICS + NUMERICS: regenerated F-lane results consistent with the corrected production model; statewise T-D (HC-08) and feed sufficiency (HC-11); filter element conservation; no > 0.1 Pa evidence; HWM14 v2 / orbit atmosphere used only as declared; golden_v2 selection rule honoured.'],
  ['software', 'SOFTWARE: full suite both legs (pymsis present / hidden) with ci_checks --pytest-junit, golden check, ci_checks, every builder --check deterministic, no fail-open path, immutable files untouched, no weakened/skipped tests, package contents.'],
  ['rfp', 'RFP TRACEABILITY: every clause in docs/requirements/rfp_official/rfp_registration_v1.json mapped in the RVM with verbatim text; derived/owner rows labelled; discrepancies recorded; A9.15 dual-propellant policy consistent across RVM, mass/Xe v3, RFQ v3 and optimizer.'],
]
const reviews = await parallel(LENSES.map(([k, txt]) => () => agent(
  `ADVERSARIAL REVIEW (A9.16 finalize). git worktree add --detach ${SP}/rvf_${k} ${integ.commit}; read-only there; scratch under ${SP}/rvf_${k}_scratch; remove the worktree at the end. Read CLAUDE.md and the decision records. ${txt} Report only real problems with evidence; give each finding an 'area': design (abep_sim/design, docs/design_synthesis, docs/hardware, docs/architecture*), requirements_budgets (docs/requirements, docs/budgets, docs/decisions/application, docs/traceability, integration), experiments_procurement (docs/experiments p1-p4, docs/procurement), production_data_perf (abep_sim/*.py production, golden, atmosphere, docs/performance, scripts, CI), other. Full suite at most once.`,
  { label: `verify:${k}`, phase: 'Verify', schema: FIND })))
const all = reviews.filter(Boolean).flatMap(r => r.findings)
const serious = all.filter(f => f.severity !== 'minor')
log(`verify: ${all.length} findings (${serious.length} blocker/major)`)
if (!serious.length) return { base: args.base, lanes, integ, findings: all, final: integ.commit }

phase('Repair')
const AREAS = ['design', 'requirements_budgets', 'experiments_procurement', 'production_data_perf', 'other']
const PATHS = { design: 'abep_sim/design/**, docs/design_synthesis/**, docs/hardware/**, docs/architecture/**, docs/architecture_comparison/**, tests/test_design_*.py and tests of those artifacts',
  requirements_budgets: 'docs/requirements/**, docs/budgets/** (non-immutable), docs/decisions/application/**, docs/traceability/**, docs/experiments/hall_icp/integration/** and their tests',
  experiments_procurement: 'docs/experiments/hall_icp/p1_icp_bench/**, p2_impedance_map/**, p3_coupled_thermal/**, p4_anode_materials/**, docs/procurement/rfq_a9_v3/**, docs/evidence/** and their tests',
  production_data_perf: 'abep_sim/*.py production modules, abep_sim/golden.py (+ golden_v2.json via generate only), docs/performance/** (new files only for history), scripts/**, pyproject.toml, MANIFEST.in, .github/workflows/rust-parity.yml and their tests',
  other: 'any non-immutable path not owned by another area (state which) and its tests' }
const groups = AREAS.map(a => ({ a, fs: all.filter(f => f.area === a) })).filter(g => g.fs.some(f => f.severity !== 'minor'))
const reps = await parallel(groups.map(g => () => agent(common(integ.commit) + `REPAIR area '${g.a}' (ALLOWED: ${PATHS[g.a]}; other areas are repaired in parallel by other agents - do not touch their paths). Fix every blocker/major finding below at its root with a test per fix; minor ones if trivial. Regenerate affected builders in your area.\n\nFINDINGS:\n${JSON.stringify(g.fs, null, 1)}`,
  { label: `repair:${g.a}`, phase: 'Repair', schema: RESULT, isolation: 'worktree' })))
const rc = reps.filter(r => r && r.commit).map(r => r.commit)
if (!rc.length) return { base: args.base, lanes, integ, findings: all, repairs: reps, final: integ.commit }
const integ2 = await integrate(integ.commit, rc, 'integrate:2', 'Report which findings were fixed by which repair commit.')
return { base: args.base, lanes, integ, findings: all, repairs: reps, integ2, final: integ2 && integ2.commit ? integ2.commit : integ.commit }

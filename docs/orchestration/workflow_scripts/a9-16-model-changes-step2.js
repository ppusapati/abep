export const meta = {
  name: 'a9-16-model-changes-step2',
  description: 'A9.16 step 2: the A9.9 controlled production-model changes, one at a time (chained), each with tests and its own HISTORY entry; then review + repair',
  phases: [
    { title: 'Change', detail: 'G-03..05 flags -> intake_tpmc input validation -> rotor strength basis -> Gaede domain -> IntakeSurface recombination -> surface v2 disposition' },
    { title: 'Review', detail: 'model-change discipline and numerical correctness lenses' },
    { title: 'Repair', detail: 'fix blocker/major findings' },
  ],
}

// args = { base: '<sha>' }
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const TRAILER = `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FzUuRP7UUVEypuFNeEaN4U`

const RESULT = {
  type: 'object',
  properties: {
    commit: { type: 'string', description: 'full sha of your final commit' },
    changed: { type: 'array', items: { type: 'string' }, description: 'what changed (file: change), one line each' },
    golden: { type: 'string', description: "golden check result; if goldens moved: which benchmarks, old -> new, why, and that they were regenerated via python -m abep_sim.golden generate" },
    downstream_pending: { type: 'array', items: { type: 'string' }, description: 'design-synthesis builders / tests / artifacts outside your allowed paths that now fail or need regeneration (step 3 regenerates them)' },
    blocked: { type: 'array', items: { type: 'string' } },
    tests: { type: 'string', description: 'commands run and results' },
  },
  required: ['commit', 'changed', 'golden', 'downstream_pending', 'blocked', 'tests'],
}

const common = (base) => `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep). You run in an ISOLATED git worktree (your current working directory). FIRST run: git reset --hard ${base} and confirm with git rev-parse HEAD.

PHASE: owner decision A9.9 (docs/decisions/OD_2026_10_01_A9_9_S2_MODEL_CHANGE_OWNER_DECISIONS.md - READ IT IN FULL; the verbatim text governs) authorises CONTROLLED PRODUCTION-MODEL CHANGES, implemented one at a time in this order: (1) S2.4 G-03..G-05 convergence flags, (2) S2.5 MCC-05/06/07 intake_tpmc input validation, (3) S2.3 + MCC-03 registered rotor strength basis, (4) MCC-02 Gaede domain flag, (5) S2.1 IntakeSurface species recombination fix, (6) S2.2 frozen intake surface v2. Also read docs/decisions/OD_2026_10_01_A9_13_* (S6.2: intake surface v2 must cover the REGISTERED AOCS pointing envelope - not registered yet; S6.8: no valid > 0.1 Pa compressor result; S6.9: Al/CFRP rotors only via the S2.3 strength-basis gate) and the F9 model-change candidates in docs/architecture/freeze_candidate/architecture_freeze_candidate_v1.json (MCC-01..07) and findings F1-01 / F3-01 / F3-02 in docs/design_synthesis/{f1_intake,f3_compressor}/.

RULES (CLAUDE.md; read it first): rule 1 frozen data (abep_sim/data/**) is never rebuilt casually - intake_surface_v1 stays unchanged; rule 2 goldens must reproduce - if your change moves them it is an authorised model change: justify, regenerate with python -m abep_sim.golden generate, and say exactly which benchmarks moved and why; rule 3 no silent fallbacks / report non-convergence; rule 5 caches pure; rule 6 cite data, never invent values; rule 9 test expectation (all pass, exactly 5 skipped, 1 strict xfail - never touch those). Never retune any other coefficient to recover previous results. Never modify hallthruster_bridge/**, abep_sim/data/**, docs/decisions/**, CLAUDE.md, or anything under docs/design_synthesis/**, docs/hardware/**, docs/architecture/**, docs/experiments/**, docs/budgets/**, docs/procurement/**, docs/requirements/**, abep_sim/design/** (another step owns those; list what breaks there in downstream_pending). abep_core/ (Rust) is read-only: the Python reference in abep_sim/intake_tpmc.py stays canonical (owner A9.14 S10.3); after touching intake_tpmc.py run python scripts/verify_abep_core.py --check and report (valid-input numerics must be unchanged; if the check refuses because the reference file changed, report it in downstream_pending - do not edit abep_core or docs/performance).
ALLOWED: abep_sim/*.py production modules needed for your change (not abep_sim/design/**), abep_sim/golden.py and the golden data file it regenerates (golden_v1.json) only when the change moves goldens, tests/** (new focused tests; update existing production tests only where the owner decision changes the behaviour, and say so), docs/HISTORY.md (append ONE dated entry for your change: what, why, owner decision id, golden impact).
CPU: no Julia; you MAY run the full suite once at the end (python -m pytest -q tests, ~10 min) and python -m abep_sim.golden check; nothing else > 5 min.
Hygiene: tests + golden check; git add + commit in your worktree; the commit message ends with exactly:
${TRAILER}
Do NOT push. Never touch ${SP}/followon or ${SP}/wt_followon.
Return the structured result.

YOUR CHANGE: `

const CHANGES = [
  { key: 'G03_G05', prompt: `S2.4 (UPSTREAM_ICD-Q7) G-03..G-05. G-03 DragCompressor.run() (abep_sim/compressor.py) reports converged (bool), iterations, final residual; reaching the iteration limit is NOT convergence. G-04 Reservoir.steady_state() (abep_sim/reservoir.py) reports converged, iterations, final balance residual. G-05 size_orifice_for_pressure() reports the final pressure residual and whether the target is bracketed/reachable; a bracket endpoint is not convergence. Keep raw state for diagnostics; an unconverged / unbracketed result is flagged MODEL_NOT_CONVERGED (or an equivalent explicit status) and must not be propagated silently as success by the production callers you can see (archengine etc.: make them carry or refuse the flag - fail closed - without changing converged numbers). Converged numerics must not change: the golden check must still pass unchanged; any numerical change is a bug to investigate, not a golden update.` },
  { key: 'MCC_05_07', prompt: `S2.5 MCC-05/06/07 in abep_sim/intake_tpmc.py: MCC-05 validate max_hits, max_hits_cap and related hit budgets as positive integers BEFORE tracing (reject explicitly; never hang); MCC-06 an unrecognised scattering model raises (never a silent Maxwell fallback; Maxwell and CLL explicitly selected and recorded); MCC-07 CLL accommodation inputs (alpha, alpha_n, alpha_t) must be finite and inside [0, 1] before the kernel (reject; never clip, never produce NaN downstream). Valid-input numerics unchanged (goldens unchanged; frozen surface unchanged). Separate HISTORY entry.` },
  { key: 'ROTOR', prompt: `S2.3 + MCC-03 rotor strength basis (abep_sim/compressor.py, abep_sim/materials.py or a NEW module abep_sim/rotor_strength.py). Rotor structural acceptance requires a REGISTERED rotor-strength basis record with at minimum: alloy/material spec, product form, heat treatment/condition, applicable thickness/section, design temperature, cited statistical allowable basis, yield vs temperature, ultimate vs temperature, density from the same controlled material definition, design/test factors, max operating/design speed, proof-spin basis where applicable. Margins against BOTH yield and ultimate. Without a registered basis: qualification = NOT_EVALUATED_MATERIAL_BASIS and rotor_ok is never True (exploration allowed as PARAMETRIC_SENSITIVITY). The uncited factor 2.0 survives only as an explicitly labelled legacy/conservative sensitivity case, never a cited requirement and never silently controlling production sizing. The 827 MPa Ti-6Al-4V annealed-plate room-temperature A-basis value (MMPDS-06 via NASA-HDBK-6025, as cited in docs/design_synthesis/f3_compressor) may be carried only as a record for THAT product form and temperature, never transferred. No numbers invented. If production sizing paths (archengine, mission envelope, goldens) depended on rotor_ok = True, they now see NOT_EVALUATED_MATERIAL_BASIS: decide fail-closed behaviour consistent with the owner text (a parametric-sensitivity path may keep computing mass/power with the legacy factor explicitly labelled), and if goldens move, regenerate and log precisely. Separate HISTORY entry.` },
  { key: 'GAEDE', prompt: `MCC-02 Gaede clipping (abep_sim/compressor.py lines with K = max(min(K, K0), 1.0)). Preserve and report the UNCLIPPED Gaede characteristic per stage/species. If the physical relation gives K < 1, the state is flagged outside the admitted model / stage-capacity domain (explicit status) and excluded from valid design evidence; a clipped value may be retained only as a labelled diagnostic. Decide how the production run reports the flag (fail closed, no silent success); if goldens move, regenerate and log precisely. Separate HISTORY entry.` },
  { key: 'INTAKE_RECOMB', prompt: `S2.1 F1Q-01 IntakeSurface species recombination (abep_sim/intake_tpmc.py class IntakeSurface; finding F1-01 in docs/design_synthesis/f1_intake/). Recombine species-resolved rows by their physical definitions: C_D with a species-consistent momentum / mixture-dynamic-pressure formulation (rows are normalised by the mixture q), passive compression with the number/mole-based species treatment, collected species flow from the species-resolved collection efficiencies (no premature single mass-weighted efficiency). Derive each formula from the definitions used to build the frozen table (read abep_sim/intake_tpmc.py build path and docs on intake_surface_v1) and document the derivation in the docstring. Regression tests for pure species (reduces exactly to the species row) and mixtures (hand-computed). The F1-01 bias was ~x1.080 C_D and ~x1.065 CR - report what your fix gives. Preserve the pre-fix result as historical evidence (a test or a recorded note of pre/post values, e.g. in HISTORY). Goldens WILL likely move: regenerate via python -m abep_sim.golden generate and log every moved benchmark old -> new. Frozen data intake_surface_v1.* unchanged. No compensating retune. Separate HISTORY entry.` },
  { key: 'SURFACE_V2', prompt: `S2.2 F1Q-04 frozen intake surface v2. Owner A9.13 S6.2 makes the v2 build depend on a REGISTERED AOCS relative-wind pointing envelope, which does not exist in the repository. Therefore do NOT build v2. Instead implement only the preparation that does not need the envelope: (a) a v2 build specification module, NEW abep_sim/intake_surface_v2_spec.py, listing the required axes (species-resolved; Maxwell and CLL as separate scenarios; deterministic seeds; registered convergence criterion; unresolved-particle info; provenance/hashes; direct-TPMC cross-check at build and held-out states; fail closed outside domain; v1 retained) with the angular axis = TBD_AOCS_POINTING_ENVELOPE, and a function that REFUSES to build while that axis is TBD; (b) make IntakeSurface (v1) refuse silent extrapolation outside its frozen domain if it does not already (check; if it already refuses, record that). Return blocked = ['S2.2 v2 build: BLOCKED_PENDING_AOCS_POINTING_ENVELOPE (A9.13 S6.2)']. HISTORY entry only if behaviour changed.` },
]

phase('Change')
let base = args.base
const results = []
for (const c of CHANGES) {
  const r = await agent(common(base) + c.prompt, { label: `change:${c.key}`, phase: 'Change', schema: RESULT, isolation: 'worktree' })
  if (!r || !r.commit) { log(`change ${c.key} returned no commit - stopping`); return { stopped_at: c.key, results } }
  results.push({ change: c.key, ...r })
  base = r.commit
  log(`change ${c.key} committed ${r.commit.slice(0, 10)}; golden: ${r.golden.slice(0, 80)}`)
}

phase('Review')
const FIND = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
      file: { type: 'string' }, description: { type: 'string' }, evidence: { type: 'string' }, fix_hint: { type: 'string' },
    }, required: ['id', 'severity', 'file', 'description', 'evidence', 'fix_hint'] } },
    checked: { type: 'array', items: { type: 'string' } },
  },
  required: ['findings', 'checked'],
}
const LENSES = [
  ['discipline', 'MODEL-CHANGE DISCIPLINE: compare each change with the verbatim A9.9 text. Flag: retuning to recover old numbers; a golden moved without justification or by a change that should not move numbers (G-03..05, MCC-05..07 must not move goldens); frozen data touched; missing or merged HISTORY entries (one per change); a fallback still silent; NOT_EVALUATED_MATERIAL_BASIS bypassable; a K < 1 state still reported as valid; tests weakened/skipped; the 5-skipped / 1-xfail expectation broken; edits outside allowed paths (git diff --stat ' + args.base + '..HEAD).'],
  ['numerics', 'NUMERICAL CORRECTNESS: re-derive the IntakeSurface recombination formulas from the table definitions and check them independently (pure-species limits, a hand mixture, conservation of collected mass flow); check the convergence flags really detect non-convergence (construct a non-converging case); check the rotor margin math against yield AND ultimate; check the unclipped Gaede K reporting; run python -m abep_sim.golden check and the changed tests.'],
]
const reviews = await parallel(LENSES.map(([k, txt]) => () => agent(
  `ADVERSARIAL REVIEW (A9.16 step 2). Work READ-ONLY on commit ${base}: git worktree add --detach ${SP}/review2_${k} ${base}; scratch only under ${SP}/review2_${k}_scratch; remove the worktree at the end. Default to finding problems; report only real ones with evidence. Read CLAUDE.md and docs/decisions/OD_2026_10_01_A9_9_*. ${txt} No Julia; full suite at most once.`,
  { label: `review:${k}`, phase: 'Review', schema: FIND })))
const all = reviews.filter(Boolean).flatMap(r => r.findings)
const serious = all.filter(f => f.severity !== 'minor')
log(`review: ${all.length} findings (${serious.length} blocker/major)`)
let final = base
if (serious.length) {
  phase('Repair')
  const rep = await agent(common(base) + `REPAIR: fix every blocker/major finding below at its root with a test per fix (same allowed paths and rules; HISTORY entries stay one per change - amend the relevant entry text by appending a dated 'review fix' line rather than rewriting history). Minor findings: fix if trivial and safe, else list in 'blocked'.\n\nFINDINGS:\n${JSON.stringify(all, null, 1)}`,
    { label: 'repair', phase: 'Repair', schema: RESULT, isolation: 'worktree' })
  if (rep && rep.commit) final = rep.commit
}
return { base: args.base, final, results, findings: all }

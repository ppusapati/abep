export const meta = {
  name: 'a9-16-architecture-step3',
  description: 'A9.16 step 3: A9.13/A9.14 architecture code changes in the design layer, RVM re-base on the registered RFP (AG-15), full F-lane / freeze-candidate regeneration on the integrated branch; then consolidated verification + repair',
  phases: [
    { title: 'Code', detail: 'parallel: design-layer architecture changes | RVM re-base on the RFP' },
    { title: 'Regenerate', detail: 'all builders, pins, F-lanes, F9 on the merged result' },
    { title: 'Verify', detail: 'four adversarial lenses' },
    { title: 'Repair', detail: 'fix blocker/major' },
  ],
}

// args = { base: '<integrated sha: steps 1 + 2 + A9.17 merged>' }
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const TRAILER = `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FzUuRP7UUVEypuFNeEaN4U`
const RESULT = { type: 'object', properties: { commit: { type: 'string' }, applied: { type: 'array', items: { type: 'string' } },
  blocked: { type: 'array', items: { type: 'string' } }, tests: { type: 'string' } }, required: ['commit', 'applied', 'blocked', 'tests'] }
const FIND = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: {
  id: { type: 'string' }, severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, file: { type: 'string' },
  description: { type: 'string' }, evidence: { type: 'string' }, fix_hint: { type: 'string' } },
  required: ['id', 'severity', 'file', 'description', 'evidence', 'fix_hint'] } } }, required: ['findings'] }

const common = (base) => `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep) in an ISOLATED git worktree (your cwd). FIRST: git reset --hard ${base}; confirm with git rev-parse HEAD. Read CLAUDE.md first. Owner decisions (immutable; the verbatim .md governs; cite path + json sha256 + id): docs/decisions/OD_2026_10_01_A9_{9,13,14,15,17}_*. The official RFP is registered in docs/requirements/rfp_official/rfp_registration_v1.json (verbatim clauses with page ids RFP-Pnn-mm) - the authoritative requirement source (A9.15, A9.17). Steps 1 (decision application) and 2 (production-model changes: G-03..05 flags, intake input validation, rotor strength basis, Gaede domain flag, IntakeSurface recombination fix) are ALREADY MERGED in your base; build on them.
RULES: CLAUDE.md rules 1-10 (frozen data, goldens, no silent fallbacks, cite data, tests 5 skipped + 1 strict xfail); never retune; never invent values; never declare a winner or a PASS without determining evidence (A9.13 S6.22); never modify docs/decisions/**, CLAUDE.md, hallthruster_bridge/**, abep_sim/data/** frozen files.
Hygiene: run the changed tests and the affected builders --check; git add + commit; message ends with exactly:
${TRAILER}
Do NOT push. Never touch ${SP}/followon or ${SP}/wt_followon. Return the structured result.

YOUR TASK: `

const ARCH = `DESIGN-LAYER ARCHITECTURE CHANGES (ALLOWED: abep_sim/design/**, tests/test_design_*.py, new tests). Implement in code (not only records): A9.13 S6.19 + S6.3/S6.4/S6.6 - the filter as a separate production-path element between IF-A1 and IF-A2 (abep_sim/design/filter_stage.py and its consumers plenum_feed / architecture_optimizer) exposing species-resolved forward and reverse transmission, conductance/pressure effect, species conversion/recombination (inert/low-recombination baseline; catalytic only as a labelled research variant), retained inventory, thermal load, material state, validity flags; never folded into intake efficiency; FC-00 no-filter only as a reference bound. S6.7 - hub ratio / hub radius and blade span explicit compressor design variables in compressor_synthesis (zero-hub only as an analytical bound; no invented bounds - bounds TBD from interfaces, search uses a declared parametric range labelled PARAMETRIC_SENSITIVITY). S6.8 - every compressor/plenum result above 0.1 Pa is NOT_EVALUATED_OUT_OF_DOMAIN (verify end to end; the transitional model abep_sim/compressor_transitional.py is CANDIDATE_NOT_ADMITTED and must not be consumed as evidence). S6.9 - Al / CFRP rotors only through the step-2 rotor strength-basis gate. S6.10 - orbit-state-scheduled plenum setpoint as baseline control mode, fixed setpoint as fallback/reference, schedule depends only on controller-available state, not frozen. S6.11 - higher-pressure compression primary direction; the <= 0.1 Pa high-conductance branch kept as labelled sensitivity/fallback. S6.12 - F4 transient metrics retained as provisional, H-1 tolerance governs when tighter. S6.15 - AG-13 / HC-08 as a hard STATEWISE constraint T_available(state) - D_spacecraft(state) >= 0 at every required state (reporting statewise, worst-state and orbit-averaged margins; average never hides a deficit) using abep_sim/atmosphere_orbit statewise_quantifier where states are needed, and abep_sim/spacecraft_reference_drag only as REFERENCE_PARAMETRIC (never closure). S6.16 - robustness over every admitted Maxwell/CLL/accommodation scenario. S6.17 - ripple as a hard feed-quality constraint vs a measured H-1 tolerance (TBD -> NOT_EVALUATED), Pareto over worst-state margin, drag, upstream power, mass, volume, heat-rejection burden; no weighted scalar. S6.20 - robust Pareto set carried (versioned), no representative. S6.21 - AG-12 statewise feed-state sufficiency (mass flow, pressure, temperature, composition, ripple quality) against the requirement derived from required thrust and a validated H-1 map: NOT_EVALUATED until that map exists; remove any 0.38 mg/s pass/fail gate (0.38-3.2 mg/s only characterization coverage). A9.14 S9.7 statewise quantifier for envelope requirements; A9.15 propellant policy (air + Xe dual capability, separate tanks/paths) wherever the optimizer models propellant paths. Add focused tests for each.`

const RVM = `RVM RE-BASE ON THE OFFICIAL RFP (AG-15, A9.13 S6.22; ALLOWED: docs/requirements/rvm_a9/**, docs/requirements/rfp_official/** (only to add the RVM mapping section to the registration record, keeping the clause transcription byte-identical), tests/test_rvm_a9.py, tests/test_rfp_registration_v1.py). Map every RFP clause in rfp_registration_v1.json to RVM rows: each RVM requirement row cites the RFP clause id(s) it derives from, or is labelled DERIVED_PROJECT_REQUIREMENT (e.g. atmospheric off-state ignition, A9.14 S9.12) or OWNER_ALLOCATION (e.g. 50 W mount heat, A9.12). Add rows for RFP requirements not yet covered: RFP-P18-12 (MIL-1553B + discrete interface + hardware drivers), RFP-P19-04 (ENTEST incl. PSLV/SSLV launch loads, AO erosion, radiation, thermal, ThermoVac, 3-year life), RFP-P19-06 (test approach a-d), RFP-P20-01 (ISO certification, ATP), RFP-P20-03 (milestone-4 exit criterion: qualified thruster with O and N2), RFP-P20-04..RFP-P21-02 (milestone schedule and deliverables), RFP-P30-01 (micro-newton thrust measurement), A9.14 S9.11 compliance gates (indigenous content 75 % project / >80 / >80 / >60 / >70 % with the >60 % clause discrepancy recorded for DRDO clarification; single-point-failure FMEA gate for electronics/sensors; N2 + atomic O qualification), S9.13 RVM-19 re-based on RFP-P18-02 / RFP-P18-09 (electronics/sensor redundancy; no full thruster/ICP duplication), S8.5 life basis (RFP-P19-01 literal 'Ignition Time More than 15000 hrs' preserved). Every row: verification method, status (no PASS without determining evidence). Record the RFP-vs-repository discrepancies: bid due date not in the RFP document (CLAUDE.md '05 Oct 2026' unverified by it), mass not stated wet/dry in the RFP. Regenerate the RVM builder outputs; keep the builder deterministic with --check.`

const REGEN = `INTEGRATION REGENERATION (ALLOWED: every generated artifact and pin in docs/**, abep_sim/design/** only for re-pin constants, tests/** only where a re-pin requires it; NOT docs/decisions/**, NOT abep_sim/data/** frozen files, NOT production abep_sim/*.py). The base now contains steps 1+2, A9.17 and the two step-3 code lanes. Run EVERY builder with --check (git ls-files '*build*.py', scripts/perf/profile_baseline.py --check, scripts/verify_abep_core.py --check, python -m abep_sim.golden check, python scripts/ci_checks.py; NEVER run the v1 consolidated-questions builder - it rewrites an xlsx). Regenerate every failing generated artifact in dependency order (F1 intake -> F2 -> F3 -> F4 -> F6 -> H-1 -> F7/F8 -> F9; budgets/RVM/M16/state v5/application matrix) so all pins and builders pass. The F-lane numbers WILL change because of the step-2 production-model fixes (IntakeSurface recombination etc.): report old -> new for the headline numbers (best delivered flow, robust set, compressor mass range, F1 intake bias) and note which F9 parameters changed. Update the application matrix (docs/decisions/application/a9_16_application_matrix) so every A9.13/A9.14 item applied in step 3 is APPLIED with path + record id. Then run the FULL test suite once (python -m pytest -q tests): expected all pass, 5 skipped, 1 xfailed.`

const LENSES = [
  ['fidelity', 'DECISION FIDELITY for A9.9, A9.13, A9.14, A9.15, A9.17 vs the code/artifacts (verbatim text); anything presented as PASS; owner numbers misused; deferred numbers invented; application matrix truthful.'],
  ['physics', 'PHYSICS + NUMERICS: the regenerated F-lane results are consistent with the corrected production model (IntakeSurface recombination, Gaede domain, rotor basis); statewise T-D and AG-12 logic; filter element mass/species conservation; no > 0.1 Pa evidence; HWM14 v2 / orbit atmosphere used only as declared.'],
  ['software', 'SOFTWARE: full suite, golden check, ci_checks, every builder --check deterministic, no fail-open path, no edits to immutable files (docs/decisions, frozen data, rfq_a9/rfq_a9_v2, owner_questions_state v2-v4, mass_power_a9_v2, xe_accounting_a9_v2), no weakened/skipped tests, package contents (17 MB data excluded).'],
  ['rfp', 'RFP TRACEABILITY: every RFP clause in docs/requirements/rfp_official/rfp_registration_v1.json is mapped in the RVM, transcriptions match the clause text, derived/owner rows labelled, discrepancies recorded; A9.15 dual-propellant policy consistent across RVM, mass/Xe v3, RFQ v3 and the optimizer.'],
]

phase('Code')
const [arch, rvm] = await parallel([
  () => agent(common(args.base) + ARCH, { label: 'code:architecture', phase: 'Code', schema: RESULT, isolation: 'worktree' }),
  () => agent(common(args.base) + RVM, { label: 'code:rvm_rfp', phase: 'Code', schema: RESULT, isolation: 'worktree' }),
])
if (!arch || !rvm) return { stopped: 'code lane failed', arch, rvm }

phase('Regenerate')
const merge = `FIRST, after the reset: git merge --no-ff ${arch.commit} -m "Merge step-3 architecture lane" and git merge --no-ff ${rvm.commit} -m "Merge step-3 RVM lane" (resolve any conflict in generated files by regenerating them, never by hand-editing; the merge commit messages also end with the two trailer lines). THEN: `
const regen = await agent(common(args.base) + merge + REGEN, { label: 'regenerate', phase: 'Regenerate', schema: RESULT, isolation: 'worktree' })
if (!regen || !regen.commit) return { stopped: 'regeneration failed', arch, rvm, regen }

phase('Verify')
const reviews = await parallel(LENSES.map(([k, txt]) => () => agent(
  `ADVERSARIAL REVIEW (A9.16 step 3 consolidated). git worktree add --detach ${SP}/rv3_${k} ${regen.commit}; read-only there; scratch under ${SP}/rv3_${k}_scratch; remove the worktree at the end. Base before step 3: ${args.base}. Read CLAUDE.md and the decision records. ${txt} Report only real problems with evidence. Full suite at most once.`,
  { label: `verify:${k}`, phase: 'Verify', schema: FIND })))
const all = reviews.filter(Boolean).flatMap(r => r.findings)
const serious = all.filter(f => f.severity !== 'minor')
log(`verify: ${all.length} findings (${serious.length} blocker/major)`)
let final = regen.commit
let rep = null
if (serious.length) {
  phase('Repair')
  rep = await agent(common(regen.commit) + `REPAIR (allowed: union of the step-3 lanes' allowed paths). Fix every blocker/major finding at its root with a test per fix; regenerate affected builders; full suite once at the end. Minor findings if trivial.\n\nFINDINGS:\n${JSON.stringify(all, null, 1)}`,
    { label: 'repair', phase: 'Repair', schema: RESULT, isolation: 'worktree' })
  if (rep && rep.commit) final = rep.commit
}
return { base: args.base, arch, rvm, regen, findings: all, repair: rep, final }

export const meta = {
  name: 'abep-lane-repair',
  description: 'Operator repair of a done_open_issues lane in its existing worktree, then two-lens re-verification (max 2 further fixes)',
  phases: [
    { title: 'Build', detail: 'one isolated worktree per lane; dependent lanes start when prerequisites finish' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens, independent' },
    { title: 'Fix', detail: 'repair rounds on failing lanes (max 2)' },
  ],
}

const ARGS_EMBEDDED = {"base": "c53b75a", "lanes": [{"key": "FTREE", "title": "Lane 26 \u2014 Architecture-specific failure trees", "allowed": ["docs/architecture_comparison/failure_tree/**", "schemas/architecture_comparison/failure_tree_v1.schema.json", "tests/test_failure_tree.py"], "prompt": "For each architecture (hall_only, rf_hall, ecr_hall) build a failure tree of the ways it could fail the programme: ignition failure, sustainment/extinction, utilization failure, interstage loss (rf_hall/ecr_hall), cathode limit (current, flow, poisoning, life), thermal limit (magnets, RF coil/coupler, ECR magnets, walls), erosion/wall-life limit, power limit (bus), mass limit, control/startup (Xe -> mixed -> atmosphere) failure, and any architecture-specific mode (e.g. RF E-H mode transition, ECR cutoff/overdense limit, magnetic-field interaction between ECR magnets and the Hall circuit). docs/architecture_comparison/failure_tree/failure_trees_v1.json (+ schema, + FAILURE_TREES.md): each node: id, architecture(s), mechanism, physical cause with open-literature evidence (source, evidence class), current evidence status (supported / contradicted / unknown), the quantity and threshold that decides it (linked to the hard-gate matrix ids where applicable: gates on thrust, bus power, mass, firing life, mission life, restart/sustainment, air+Xe), the cheapest evidence that would resolve it (literature, analysis, measurement) and which lane/deliverable would produce it (e.g. interstage model, break-even surfaces, electrical closure, cathode integration, minimum decisive experiment). Produce a ranked 'what evidence to acquire next' list per architecture by decisiveness (how many nodes/gates a single measurement resolves), with the ranking rule stated explicitly and no subjective weighting beyond that rule. No winner. Test tests/test_failure_tree.py: schema validation, every node has evidence status and a resolving action, gate links reference valid gate names, every architecture covers every generic failure class.", "repair": {"res": {"worktree_path": "/home/user/abep/.claude/worktrees/wf_e3c01fb8-eed-2", "branch": "worktree-wf_e3c01fb8-eed-2", "commit": "30be95ca376a009240dfa83e6497dc264c9558de"}, "issues": [{"severity": "major", "file": "docs/architecture_comparison/failure_tree/failure_trees_v1.json", "description": "The decisiveness ranking counts conditional design-branch nodes as if they were baseline, and the rule does not say so. Rule decisiveness_lexicographic_v1 counts every open node that is not a sub-cause, including nodes with a 'condition'. One of these is N-CAT-04 ('Applies only if the cathode is fed from the atmospheric path'), which is the alternative to the Xe-fed baseline nodes N-CAT-02/03/05/06. Those baseline nodes are not marked conditional, so the two branches are treated unequally. M-CATHODE bundles two different hardware tests into one action: the Xe-fed hollow-cathode test (plume mode, O2 exposure, heater cycles) and an 'air-fed plasma-cathode alternative'. It is then credited with deciding both N-CAT-03 and N-CAT-04. I recomputed the ranking independently (scratchpad verify_FTREE_rules/rank2.py). Counting conditional nodes, it matches the published ranking exactly. Excluding them: (1) hall_only rank 1 changes from M-CATHODE (2 decides, 4 gates) to M-THERMAL, and M-CATHODE falls to rank 3 with 1 gate (firing_life); (2) M-CATHODE's gates decided drop from 4 to 1 in rf_hall and ecr_hall, where it falls from rank 2 to rank 5 and rank 6 respectively; (3) A-BFIELD's only decide in rf_hall is the conditional helicon node N-RF-03. Three texts depend on this undisclosed counting choice: the JSON claim that the ranked list 'says which single piece of evidence would retire the most conditions', the MD statement 'The two top-ranked actions (M-THERMAL, M-CATHODE)', and the stated rule itself. Fix options: exclude conditional nodes, or rank them separately and label every row whose rank depends on them. Also split M-CATHODE into Xe-fed and air-fed actions, or mark N-CAT-02/03/05/06 conditional on the Xe-fed branch. This is the same kind of count inflation that round 2 fixed for sub-causes."}, {"severity": "major", "file": "docs/architecture_comparison/failure_tree/failure_trees_v1.json", "description": "N-UTL-01 has the wrong evidence status, and it is inconsistent with N-PWR-01. Both nodes test the same threshold, 12 mN on air within the 1.5 kW bus: N-UTL-01 states '>= 12 mN sustained on air within the 1.5 kW bus (RFP)' and N-PWR-01 states 'P_discharge(12 mN) <= 1500 W minus all other loads (RFP)'. Both apply to all three architectures. N-PWR-01 is 'contradicted' by two measured items: S-CIFALI2011 (PPS1350-TSD on pure N2 at 305 V, 3.48 A, 41.6 W/mN, i.e. about 12 mN at about 500 W) and S-MARCHIONI2020 (17-22 mN at 500-800 W on N2). N-UTL-01 is 'supported'. It cites S-CIFALI2011 only as 'supports', for lower ionization efficiency than Xe, and leaves out the same source's measured power-per-thrust that contradicts its threshold. Under the file's own deterministic rule (supports plus contradicts gives unknown), N-UTL-01 should be 'unknown' (conflicting), with the same applicability caveats as N-PWR-01. The two nodes also duplicate one threshold comparison, so M-PREION and A-ELEC each collect two 'contributes' counts for it. Round 2 prevented this double-count for mass with sub_cause_of, but not here. Relabel N-UTL-01, or make one of the two nodes a sub-cause of the other."}, {"severity": "minor", "file": "tests/test_failure_tree.py", "description": "No test guards how conditional nodes enter the ranking, or the evidence-direction consistency of one source used against the same threshold on different nodes. The two majors above pass the current tests silently. The ranking test re-implements the lane's own rule, so it confirms the arithmetic but not whether the counted set is right."}, {"severity": "minor", "file": "docs/architecture_comparison/failure_tree/failure_trees_v1.json", "description": "I spot-checked source integrity. The arXiv 2212.01486v1 sha256 matches exactly. The Tisaev 2023a quotes (87.5 mT, the 1 A / 0.1 mg/s air figure, the poisoning and erosion sentences, the air/ECR sentence) were all found in the PDF. The IEPC-2009-015 download returned an HTML page instead of the PDF, so the S-DIAMANT2009 hash and quotes (the 8 kg and 4e17 figures) were not verified in this review. This is not attributed to the lane."}, {"severity": "major", "file": "docs/architecture_comparison/failure_tree/failure_trees_v1.json", "description": "N-UTL-01 and N-PWR-01 are labelled inconsistently, although both nodes compare the same decision quantity and threshold. N-UTL-01 is titled 'Low ion utilization of N2/O2 in the Hall stage prevents 12 mN within the bus power', with threshold '>= 12 mN sustained on air within the 1.5 kW bus (RFP)' and gates thrust and bus_power. It is marked 'supported'. Its only supports items are S-SHABSHELOWITZ2014 (utilization is low) and S-CIFALI2011 ('lower for nitrogen than for xenon', 'substantial deterioration of performance with respect to Xe'). Both are relative-to-Xe or generic statements that do not show the 12 mN / 1.5 kW threshold being missed. N-PWR-01 has the same gates and an equivalent threshold. There, the same lane marks the failure path 'contradicted' using S-CIFALI2011 (305 V x 3.48 A = 1061 W at 41.6 W/mN, which is about 25.5 mN on N2; verified in the PDF, Sec. II.B) and the ECHT abstract (17-22 mN at 500-800 W on 2 mg/s N2; verified in the repo audit). Those contradicting items are left off N-UTL-01. Under the file's own direction definition ('contradicts: the source shows the mechanism did not occur, or was avoided, in a relevant device'), they apply to N-UTL-01, so its status should be 'unknown' (conflicting). The alternative is to rescope N-UTL-01 to the mechanism only, so it no longer duplicates N-PWR-01's threshold. The rule is also applied unevenly: round 2 relabelled equally generic support (S-TISAEV2023A on N-UTL-03) as 'context', but not here. As published, the tree tells the owner that 'low utilization prevents 12 mN within 1.5 kW' is credibly supported for all three architectures, while a sibling node says the same threshold is contradicted by the same source."}, {"severity": "minor", "file": "docs/architecture_comparison/failure_tree/failure_trees_v1.json", "description": "Double counting in the ranking. N-UTL-01 and N-PWR-01 have the same comparison (12 mN on air within the discharge power the bus leaves), the same gates and the same resolution set (A-ELEC + M-PREION). Both are counted in the ranking, so key 3 (contributes) for A-ELEC and M-PREION is inflated by one in every architecture. Round 2 removed exactly this kind of double count for N-MAS-02/03 by making them sub_cause_of their parent; the same treatment (or a distinct threshold) is missing here."}, {"severity": "minor", "file": "docs/architecture_comparison/failure_tree/failure_trees_v1.json", "description": "Two 'supports' items rest on generic or out-of-regime evidence, which is inconsistent with the round-2 relabelling policy. First, N-ISL-ECR is 'supported' only by an inferred design remark in S-FOSTER2006: a xenon gridded-ion-engine ECR source at 5.85 GHz, with no interstage transfer to a Hall stage. Second, N-SUS-03 (rf_hall/ecr_hall two-stage coupling) is 'supported' only by S-ANDREUSSI2017, whose own source note says the first stage is a DC stage, not an RF or ECR pre-ionizer. Both are defensible as mechanism-level credibility, but the applicability gap should be stated in the status (for example as context plus an evidence_gap) or explicitly justified."}, {"severity": "minor", "file": "docs/architecture_comparison/failure_tree/failure_trees_v1.json", "description": "N-THM-01 physical_cause asserts a 'higher fraction of power lost on molecular propellants' conducted to the magnetic circuit. No evidence item on the node supports that comparative claim: S-SIMMONDS2022 and S-MYERS2016 are propellant-agnostic. It should be cited or marked verify/TBD."}]}}]}

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
    const res = lane.repair ? await agent(fixPrompt(lane, lane.repair.res, lane.repair.issues), { label: `build:${lane.key}`, phase: 'Build', schema: RESULT }) : await agent(COMMON + `${lane.key} — ${lane.title}\n${lane.prompt}\nALLOWED paths: ${lane.allowed.join(', ')}` +
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

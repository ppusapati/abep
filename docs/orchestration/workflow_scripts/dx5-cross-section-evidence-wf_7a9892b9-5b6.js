export const meta = {
  name: 'dx5-cross-section-evidence',
  description: 'Owner D-X5 (bounded): exhaustive, verified search for published N2 cross-section evidence closing the rotational/electronic/vibrational domain gaps; conditional dissociation step; synthesized dossier with two-lens verification',
  phases: [
    { title: 'Search', detail: 'two independent strategies per priority (P1 rotational, P2 electronic, P3 non-resonant vibrational)' },
    { title: 'Check', detail: 'adversarial source-by-source verification of every claimed finding' },
    { title: 'Conditional', detail: 'P4 dissociation > ~300 eV only if P1-P3 materially improve' },
    { title: 'Build', detail: 'synthesized D-X5 evidence dossier in an isolated worktree' },
    { title: 'Verify', detail: 'evidence lens + rules/recompute lens; up to two repair rounds' },
  ],
}

const BASE = '9f26df22dba5459293509097c3e5763e2b11ae3d'
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const OUT = SP + '/dx5'
const CONTEXT = `CONTEXT (ABEP-VLEO simulator, repository /home/user/abep, branch claude/nifty-ramanujan-w68f9z at ${BASE}; read CLAUDE.md there).
Owner disposition 2026-09-26 of v2 Question A = A-NO (docs/v2/question_a/QUESTION_A_DISPOSITION.json): the active N2 chemistry domain stays at 45 eV mean energy; no P5-N2 v2. D-X5 = YES, BOUNDED: find legitimate published/open evidence that could materially close the domain gaps identified by the verified lane-01 audit (docs/chemistry/n2_domain_extension/N2_DOMAIN_EXTENSION_AUDIT.md, domain_extension_audit.json, domain_extension_requirements.json; read them first — they list the tables, current sources (Song et al. JPCRD 2023, Cosby 1993, Su et al. 2021, Johnson et al. 2005, Laporta et al. 2014, Majeed & Strickland 1997, Tabata et al. 2006, Kawaguchi 2021, Itikawa 2006, Winters), the energy coverage required E_req (~575 eV at the 1e-6 share level, ~1.15 keV at 1e-12 even for a 60 eV limit) and the conflicts).
Priorities (owner): P1 rotational excitation cross sections of N2 above 10 eV (structural blocker: with the rotational cap at most 37 of 714 v1 OOD runs are recoverable); P2 electronic excitation of N2 above 100 eV (above 200 eV for a1Pi_g), resolving the Johnson 2005 / Majeed & Strickland 1997 / Kawaguchi inconsistencies (factors 0.17-3.8 at 100 eV); P3 non-resonant vibrational excitation of N2 (the Tabata n2-5 fit to Itikawa 1986 gives a non-resonant 0->1 component 2.05x the table's resonant-only rate at T_e 30 eV); P4 additional independent N2 dissociation evidence above ~296-330 eV ONLY after P1-P3 improve.
HARD RULES: published / openly accessible sources only; NEVER contact authors, labs or anyone; no email; do NOT use LXCat (neither its website nor its data); no paywall or bot-challenge bypass (abstract-only access must be labelled 'abstract_only'); never change TLS/trust settings; cite only DOIs/URLs you actually accessed (WebSearch/WebFetch are deferred tools: load them with ToolSearch). Anything from memory is marked 'verify'. Do not modify the repository (search agents write only under ${OUT}/). Do not run Julia. This search does NOT change any chemistry table, validity limit, pre-registration or v1 result, and it does not decide anything: whether the reopening condition of Question A is met is the OWNER's decision.`

const FINDINGS = {
  type: 'object',
  properties: {
    priority: { type: 'string' }, strategy: { type: 'string' },
    sources: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, citation: { type: 'string' }, doi_or_url: { type: 'string' },
      access: { type: 'string', enum: ['open', 'abstract_only', 'not_accessed'] },
      kind: { type: 'string', description: 'measurement | theory/calculation | recommended compilation | review | database' },
      process: { type: 'string' }, energy_range_eV: { type: 'string' }, stated_uncertainty: { type: 'string' },
      evidence_class: { type: 'string' },
      already_in_repo: { type: 'boolean', description: 'true if lane-01 already uses/cites it' },
      what_it_adds: { type: 'string' }, quote_or_location: { type: 'string', description: 'table/figure/page where the data sit, as seen' },
    }, required: ['id', 'citation', 'doi_or_url', 'access', 'kind', 'process', 'energy_range_eV', 'evidence_class', 'already_in_repo', 'what_it_adds'] } },
    gap_assessment: { type: 'string', description: 'does the new evidence materially close this priority gap? why / why not' },
    material_improvement: { type: 'boolean' },
    searched: { type: 'array', items: { type: 'string' }, description: 'queries / databases / citation chains actually searched (for completeness audit)' },
    dead_ends: { type: 'array', items: { type: 'string' } },
  },
  required: ['priority', 'strategy', 'sources', 'gap_assessment', 'material_improvement', 'searched', 'dead_ends'],
}
const CHECK = {
  type: 'object',
  properties: {
    confirmed_sources: { type: 'array', items: { type: 'string' }, description: 'source ids confirmed (resolves, correct authors/title/year, contains the claimed data/range, access label correct)' },
    rejected: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, reason: { type: 'string' } }, required: ['id', 'reason'] } },
    corrections: { type: 'array', items: { type: 'string' } },
    material_improvement_confirmed: { type: 'boolean' },
    assessment: { type: 'string' },
  },
  required: ['confirmed_sources', 'rejected', 'corrections', 'material_improvement_confirmed', 'assessment'],
}

const P = {
  P1: 'P1 — rotational excitation of N2 (j -> j+2, j+4; direct and resonance-enhanced) at electron energies ABOVE 10 eV, ideally to hundreds of eV (measured, R-matrix / close-coupling / Born calculations, recommended compilations).',
  P2: 'P2 — electronic excitation of N2 (the 8 states A3Sigma_u+, B3Pi_g, W3Delta_u, Bprime3Sigma_u-, aprime1Sigma_u-, a1Pi_g, w1Delta_u, C3Pi_u) ABOVE 100 eV (a1Pi_g above 200 eV), and anything that resolves the Johnson 2005 / Majeed & Strickland 1997 / Kawaguchi disagreements (e.g. absolute measurements, Born/BEf-scaled calculations, optical emission cross sections with cascade corrections, recommended sets).',
  P3: 'P3 — NON-RESONANT (direct, non-2Pi_g-resonance) vibrational excitation of N2 ground state (v=0 -> 1, 2, ...) across 5-500 eV: measurements, calculations and compilations (e.g. Itikawa 1986/2006 recommendations, Tabata 2006 fits and their sources), to establish the magnitude missing from the resonant-only Laporta 2014 tables.',
  P4: 'P4 — additional INDEPENDENT N2 neutral dissociation cross sections above ~296-330 eV (independent of Cosby 1993 / Song 2023 Table 9 and of the reconstructed Winters points).',
}
const STRATEGIES = {
  review: 'STRATEGY A — compilations and reviews first: chain backwards and forwards from the recommended compilations and reviews (Song et al. JPCRD 2023 and its reference list, Itikawa JPCRD 2006, Brunger & Buckman Phys. Rep. 2002, Tabata ADNDT 2006, Majeed & Strickland JPCRD 1997, Anzai et al., IAEA/NFRI or NIST open databases, Kawaguchi et al.), including papers that cite them (forward citation search via open scholarly indexes such as OpenAlex / Semantic Scholar / Crossref / Google Scholar result pages).',
  primary: 'STRATEGY B — primary literature directly: search for original measurements (crossed-beam, swarm-derived, optical emission, electron energy-loss) and calculations (R-matrix, close-coupling, distorted-wave, Born, BEB/BEf scaling) by process name and energy range, including recent (2015-2026) arXiv / open-access journal papers and theses in open institutional repositories.',
}

function searchPrompt(pk, sk) {
  return `${CONTEXT}\nYOUR TASK: ${P[pk]}\n${STRATEGIES[sk]}\nSearch exhaustively within this priority and strategy; record EVERY query/database/citation chain you actually used in 'searched' and every dead end (paywall, 403, bot challenge — not bypassed). For each source found: open it (or its abstract), record exactly where the relevant data sit (table/figure/page), the energy range actually covered, the stated uncertainty, evidence class, access label, whether lane-01 already uses it, and what it adds relative to the gap. Then assess honestly whether the evidence MATERIALLY closes the gap for this priority (cross sections covering the energy range the lane-01 requirements need, with stated uncertainty, from a source independent of the ones already used — or resolving the conflicts). Write your full findings JSON to ${OUT}/${pk}_${sk}.json as well as returning it.`
}
function checkPrompt(pk, found) {
  return `${CONTEXT}\nYou are an ADVERSARIAL SOURCE CHECKER for priority ${pk}. Two independent searches returned the findings below. For EVERY claimed source: open the DOI/URL yourself (WebFetch; load via ToolSearch), confirm it resolves, that authors/title/year match, that it actually contains the claimed process data over the claimed energy range (check the table/figure/page cited), and that the access label is correct. Reject fabricated, mis-attributed or overstated sources. Merge duplicates. Then judge whether the CONFIRMED evidence materially closes the ${pk} gap (be strict: default to material_improvement_confirmed=false if uncertain). Write your verdict JSON to ${OUT}/${pk}_check.json as well as returning it.\nFINDINGS: ${JSON.stringify(found)}`
}

// ---- Search + check P1-P3 (pipelined per priority) ----
phase('Search')
const checked = await pipeline(
  ['P1', 'P2', 'P3'],
  pk => parallel(Object.keys(STRATEGIES).map(sk => () =>
    agent(searchPrompt(pk, sk), { label: `search:${pk}:${sk}`, phase: 'Search', schema: FINDINGS }))),
  (found, pk) => agent(checkPrompt(pk, found.filter(Boolean)), { label: `check:${pk}`, phase: 'Check', schema: CHECK })
    .then(c => ({ pk, found: found.filter(Boolean), check: c })),
)
const improved = checked.filter(x => x && x.check && x.check.material_improvement_confirmed).map(x => x.pk)
log(`P1-P3 checked; material improvement confirmed for: ${improved.length ? improved.join(', ') : 'none'}`)

// ---- P4 only if P1-P3 materially improve (owner ordering) ----
phase('Conditional')
let p4 = null
if (improved.length) {
  const f4 = await parallel(Object.keys(STRATEGIES).map(sk => () =>
    agent(searchPrompt('P4', sk), { label: `search:P4:${sk}`, phase: 'Conditional', schema: FINDINGS })))
  p4 = { pk: 'P4', found: f4.filter(Boolean), check: await agent(checkPrompt('P4', f4.filter(Boolean)), { label: 'check:P4', phase: 'Conditional', schema: CHECK }) }
} else {
  log('P4 deferred per owner ordering: no material improvement on P1-P3')
}

// ---- Build dossier (isolated worktree) + two-lens verification ----
const RESULT = {
  type: 'object',
  properties: {
    worktree_path: { type: 'string' }, branch: { type: 'string' }, commit: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } }, summary: { type: 'string' },
    key_findings: { type: 'array', items: { type: 'string' } },
    reopening_condition_assessment: { type: 'string' },
    open_questions_for_owner: { type: 'array', items: { type: 'string' } },
    tests_run: { type: 'string' }, tests_passed: { type: 'boolean' },
  },
  required: ['worktree_path', 'branch', 'commit', 'files', 'summary', 'key_findings', 'reopening_condition_assessment', 'open_questions_for_owner', 'tests_passed'],
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
const ALLOWED = ['docs/chemistry/n2_domain_extension/dx5/**', 'tests/test_dx5_evidence.py']
const BRIEF = `Build the D-X5 evidence dossier (registered follow-on fo_dx5_cross_section_evidence, trigger T_DX5_EVIDENCE). Using ONLY the adversarially CONFIRMED sources below (rejected ones may be listed as rejected with reasons, never used), write docs/chemistry/n2_domain_extension/dx5/DX5_EVIDENCE.md + dx5_evidence_v1.json (+ a deterministic build_dx5_evidence.py that generates the JSON from a committed source list, --check reproduces): per priority P1-P3 (and P4 if searched, else 'DEFERRED per owner ordering'): every confirmed source with citation, DOI/URL, access label, kind, process, energy range, stated uncertainty, evidence class, where the data sit, whether lane-01 already used it; comparison against the lane-01 requirement (E_req, conflicts) from docs/chemistry/n2_domain_extension/domain_extension_requirements.json and domain_extension_audit.json (quote fields); a per-priority status GAP_MATERIALLY_NARROWED / GAP_UNCHANGED / GAP_CLOSED with justification; the complete search log (queries/databases/citation chains and dead ends, from the search records under ${OUT}/); and a section 'Reopening condition of Question A' stating the evidence facts relevant to the owner's reopening condition ('genuinely new published evidence materially closes the rotational/electronic/vibrational domain gaps') WITHOUT deciding it (status DRAFT_PENDING_OWNER). No chemistry table, validity limit, prereg or v1 result is changed or proposed as changed. Test tests/test_dx5_evidence.py: JSON reproducible; every source has access label + evidence class; no rejected source is used; every priority has a status; the reopening section contains no decision; LXCat never cited.`
const COMMON = `${CONTEXT}\nYou run in an ISOLATED git worktree (your cwd); commit there (do not push). Modify ONLY: ${ALLOWED.join(', ')}. Run only your own test file. Commit message last two lines exactly:\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01FzUuRP7UUVEypuFNeEaN4U\nReport worktree path (pwd), branch and commit sha.\n`
const inputs = JSON.stringify({ checked, p4 })
const LENSES = {
  evidence: `EVIDENCE LENS. Spot-check at least 8 cited sources yourself with WebSearch/WebFetch (DOI/URL resolves, authors/title/year, the claimed data and energy range are there, access label right). Fabricated or mis-attributed citations and any use of LXCat are BLOCKERS. Overstated gap closure is major. Any decision on reopening Question A, or any proposed change to a table/limit/prereg/v1, is a BLOCKER.`,
  rules: `RULES/RECOMPUTE LENS. git diff --name-only ${BASE}...HEAD within ${ALLOWED.join(', ')}; no uncommitted leftovers; build_dx5_evidence.py --check reproduces; the test file passes and tests something meaningful; every priority status is justified against the lane-01 requirement fields (open those files and check quotes); no rejected source used; P4 marked DEFERRED unless P1-P3 improvement was confirmed.`,
}
const verify = (res, lens, r) => agent(`You are an ADVERSARIAL reviewer. Default to finding problems. Worktree ${res.worktree_path} (branch ${res.branch}, commit ${res.commit}); work READ-ONLY; scratch only under ${SP}/verify_dx5_${lens}/.\n${CONTEXT}\nBrief: ${BRIEF}\n${LENSES[lens]}\nReturn pass=true only if no blocker/major issue remains.`,
  { label: `verify${r}:DX5:${lens}`, phase: 'Verify', schema: VERDICT })

phase('Build')
let res = await agent(`${COMMON}\n${BRIEF}\nCONFIRMED/REJECTED INPUTS (search + adversarial check records; the raw JSONs are also under ${OUT}/): ${inputs}`,
  { label: 'build:DX5', phase: 'Build', isolation: 'worktree', schema: RESULT })
if (!res) return { failed: 'build' }
phase('Verify')
let round = 1, v = await parallel(['evidence', 'rules'].map(l => () => verify(res, l, round)))
while (!(v.filter(Boolean).length === 2 && v.every(x => x && x.pass)) && round < 3) {
  const issues = v.filter(Boolean).flatMap(x => x.issues)
  const fx = await agent(`Repair the D-X5 dossier in its existing worktree ${res.worktree_path} (cd there; stay on branch ${res.branch}; do NOT create a new worktree).\n${COMMON}\n${BRIEF}\nFix every blocker and major issue (minors where cheap); unsourceable claims -> remove or mark verify. Commit as a new commit. ISSUES: ${JSON.stringify(issues)}`,
    { label: `fix${round}:DX5`, phase: 'Verify', schema: RESULT })
  if (fx) res = fx
  round++
  v = await parallel(['evidence', 'rules'].map(l => () => verify(res, l, round)))
}
const pass = v.filter(Boolean).length === 2 && v.every(x => x && x.pass)
return { res, pass, rounds: round, improved, p4_searched: !!p4, open_issues: pass ? [] : v.filter(Boolean).flatMap(x => x.issues) }

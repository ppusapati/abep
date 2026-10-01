export const meta = {
  name: 'a9-17-artifact-rebuild',
  description: 'A9.17: v1 atmosphere packaging/compression -> HWM14 atmosphere v2 (chained), sputter register regeneration under frozen screening factors (parallel); review + repair per chain',
  phases: [
    { title: 'Build', detail: 'chain A: PKG -> HWM14 v2; chain B: SPUTTER regen' },
    { title: 'Review', detail: 'adversarial review + repair per chain' },
  ],
}

// args = { base: '<sha>' }
const SP = '/tmp/claude-0/-home-user-abep/275befef-ee58-5bbd-84f0-21c33eb50eb4/scratchpad'
const TRAILER = `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FzUuRP7UUVEypuFNeEaN4U`
const RESULT = { type: 'object', properties: { commit: { type: 'string' }, files: { type: 'array', items: { type: 'string' } },
  summary: { type: 'string' }, open_items: { type: 'array', items: { type: 'string' } }, tests: { type: 'string' } },
  required: ['commit', 'files', 'summary', 'open_items', 'tests'] }
const FIND = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: {
  id: { type: 'string' }, severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, file: { type: 'string' },
  description: { type: 'string' }, evidence: { type: 'string' }, fix_hint: { type: 'string' } },
  required: ['id', 'severity', 'file', 'description', 'evidence', 'fix_hint'] } } }, required: ['findings'] }

const common = (base) => `You are working on the ABEP-VLEO simulator repository (GitHub ppusapati/abep) in an ISOLATED git worktree (your cwd). FIRST: git reset --hard ${base}; confirm with git rev-parse HEAD. Read CLAUDE.md first and the owner decision docs/decisions/OD_2026_10_01_A9_17_DATA_ARTIFACT_OWNER_DECISIONS.md IN FULL (verbatim text governs; cite path + json sha256 + decision key).
Other campaigns run in parallel on other worktrees (step 1 decision application, step 2 production-model changes). Touch ONLY your ALLOWED paths. Never modify docs/decisions/**, CLAUDE.md, hallthruster_bridge/**, existing abep_sim modules other than those allowed, or other deliverables. You MAY append ONE dated entry to docs/HISTORY.md for your change.
EVIDENCE (CLAUDE.md rules 1, 6, 10; docs/EVIDENCE.md): never invent values or sources; published/open sources and lawful access only; no contact with people; never change TLS settings (WebSearch/WebFetch are deferred tools - load via ToolSearch). Frozen data: versioned, deterministic builder, provenance manifest, sha256, check mode.
Hygiene: your tests + builder/check; git add + commit; message ends with exactly:
${TRAILER}
Do NOT push. Never touch ${SP}/followon or ${SP}/wt_followon. Return the structured result.

YOUR LANE: `

const PKG = `A9.17 DATA_SIZE for atmosphere_msis21_orbit_v1 (ALLOWED: abep_sim/atmosphere_orbit.py, abep_sim/data/atmosphere_msis21_orbit_v1*, pyproject.toml [tool.setuptools.package-data] / MANIFEST.in only for this exclusion, tests/test_atmosphere_orbit.py, tests/test_packaging.py, docs/HISTORY.md). The dataset CONTENT is immutable (A9.17 WINDS: keep v1 immutable). (1) Store ONE canonical compressed copy: abep_sim/data/atmosphere_msis21_orbit_v1.csv.gz written deterministically (gzip mtime=0, fixed compresslevel, no filename in header), replacing the uncompressed .csv; the manifest JSON records BOTH the sha256 of the uncompressed CSV bytes (must equal the existing recorded CSV hash c0ce282e99695be8cae0834270c5b9ff7853033255665abda7ec18c307566164 - prove it) and the sha256 of the .gz container; the accessor reads the .gz and verifies the uncompressed hash on load; build/check updated accordingly. (2) Exclude the dataset (csv.gz and design-states json if large) from the installed wheel/sdist unless runtime code genuinely requires it: no installed production module imports atmosphere_orbit, so exclude it; the accessor, when the data file is absent (installed package), raises a clear error naming the repository path - never a silent fallback. Make the package-data glob explicit so the existing frozen v1 orbit-averaged files keep shipping. Update tests/test_packaging.py if it asserts package contents (keep its intent). (3) A9.17 ORBIT: everywhere the 96.3 deg / dawn-dusk default appears in atmosphere_orbit outputs (manifest, design states, docstrings), label it CODE_DEFAULT / PARAMETRIC, never a requirement input; design states stay over the broad envelope (all reachable latitudes, all local times). If that changes the design-states JSON only in labels, regenerate it and say so; the CSV content must not change.`

const HWM = `A9.17 WINDS: atmosphere v2 with HWM14 neutral winds (ALLOWED: NEW abep_sim/atmosphere_orbit_v2.py, NEW abep_sim/data/atmosphere_msis21_hwm14_orbit_v2.* (csv.gz + manifest json + design states if needed), NEW tests/test_atmosphere_orbit_v2.py, NEW docs/evidence/hwm14/** (source provenance), pyproject.toml package-data only to EXCLUDE the new data from the wheel like v1, docs/HISTORY.md). v1 stays untouched. Obtain HWM14 lawfully from its public open sources (owner cites NASA CCMC: https://kauai.ccmc.gsfc.nasa.gov/CMR/view/model/SimulationModel?resourceID=spase%3A%2F%2FCCMC%2FSimulationModel%2FHWM14%2F2014 ; NRL public repository with the Fortran source and data files; also the PyPI package pyhwm2014 which wraps HWM14 - verify what it contains and its license). You may install a Fortran compiler (apt-get install gfortran) or use pip packages into a venv inside your worktree or ${SP}/venv_hwm (not the system site-packages used by the repo tests unless needed for your tests; if the build needs HWM at check time, make the check skip cleanly with a clear reason when HWM14 is unavailable, like the pymsis-absent pattern, but the accessor must work from the frozen data without HWM). Record HWM14 version, source URLs, file sha256s, license/terms text, compiler and build flags. Validate the installation against any reference outputs shipped with HWM14 (e.g. its test driver / checkhwm14 output) before using it; record the comparison. Dataset: same grid and the same four ECSS scenarios as v1 (read abep_sim/atmosphere_orbit.py; reuse its grid definition by import, do not copy-edit it), plus HWM14 meridional and zonal wind (m/s) at each node with the Ap input (HWM14 uses ap for the disturbance-wind part: record exactly which ap is passed), date/time, coordinates. Provide BOTH relative-flow results: (a) Earth-corotating atmosphere (as v1) and (b) corotation + HWM14 wind, as relative speed and flow-direction angle for a spacecraft velocity vector supplied by the caller (orbit_states-like sampler using the same mission_env geometry; inclination/LTAN are CODE_DEFAULT / PARAMETRIC per A9.17 ORBIT and must be caller inputs, never defaults). Same interpolation discipline as v1 (measured interpolation error vs direct HWM14 at random points recorded; refuse out-of-domain). v2 is labelled DESIGN_ENVELOPE_PARAMETRIC, not a mission trajectory. Compressed canonical file (deterministic gzip), excluded from the wheel. If HWM14 cannot be obtained or built lawfully, deliver the provenance register, the module skeleton that refuses, and say exactly what blocked it.`

const SPUT = `A9.17 SPUTTER (ALLOWED: docs/evidence/sputter_yields_v1/** , tests/test_sputter_yields_v1.py, docs/HISTORY.md). Freeze E_screen = 1.10 x E_threshold and F_worst = 1.25 as OWNER-DEFINED SCREENING GUARDBANDS (A9.17, decided 2026-10-01 after the first build): in the builder inputs they become owner constants citing the A9.17 decision (path + json sha256), replacing the lane-chosen values; label them screening/down-selection only, never P4 material acceptance, lifetime or qualification (S5.12 governs those); record explicitly that the first build's results were NOT pre-registered evidence (the factors had been chosen after seeing the data) and that this regeneration applies the factors prospectively. Regenerate the register from the UNCHANGED source data (prove: the source/input records are byte-identical except the factor provenance fields). Report which screening outcomes, if any, differ from the first build (they should not if the values are the same) - never adjust anything because a material passes or fails. Fix the open minor item: the CHK-MASS-RATIOS text must be derived, not hard-coded ('8 captions').`

phase('Build')
const chains = [
  { key: 'A', steps: [{ key: 'PKG', prompt: PKG }, { key: 'HWM', prompt: HWM }] },
  { key: 'B', steps: [{ key: 'SPUTTER', prompt: SPUT }] },
]
const out = await parallel(chains.map(ch => async () => {
  let base = args.base
  const res = []
  for (const st of ch.steps) {
    const r = await agent(common(base) + st.prompt, { label: `build:${st.key}`, phase: 'Build', schema: RESULT, isolation: 'worktree' })
    if (!r || !r.commit) { res.push({ step: st.key, failed: true }); return { chain: ch.key, res, final: base } }
    const f = await agent(`ADVERSARIAL REVIEW of ${st.key} at commit ${r.commit} (base ${base}). git worktree add --detach ${SP}/rv17_${st.key} ${r.commit}; work read-only there; scratch under ${SP}/rv17_${st.key}_scratch; remove the worktree at the end. Read CLAUDE.md and docs/decisions/OD_2026_10_01_A9_17_*. Check: decision applied faithfully; immutability (v1 content hash unchanged; sources unchanged); determinism (rebuild twice -> identical hashes); no silent fallback; no invented values/sources (fetch at least 2 cited sources); edits only in allowed paths (git diff --stat ${base}..${r.commit}); tests meaningful. Report only real problems with evidence.\n\nBRIEF: ${st.prompt}`,
      { label: `review:${st.key}`, phase: 'Review', schema: FIND })
    let commit = r.commit
    const serious = ((f && f.findings) || []).filter(x => x.severity !== 'minor')
    let rep = null
    if (serious.length) {
      rep = await agent(common(r.commit) + `REPAIR ${st.key}: fix every blocker/major finding at its root with a test per fix; minor ones if trivial. Same allowed paths.\n\nBRIEF: ${st.prompt}\n\nFINDINGS:\n${JSON.stringify(f.findings, null, 1)}`,
        { label: `repair:${st.key}`, phase: 'Review', schema: RESULT, isolation: 'worktree' })
      if (rep && rep.commit) commit = rep.commit
    }
    res.push({ step: st.key, build: r, findings: f ? f.findings : null, repair: rep, final: commit })
    base = commit
  }
  return { chain: ch.key, res, final: base }
}))
return { base: args.base, chains: out }

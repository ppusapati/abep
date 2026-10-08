# HALL RUN LOCATION, HALL AIR CHEMISTRY, PLENUM / FEED v8 (A9.33) — verbatim record

Recorded verbatim from the owner's answers of 2026-10-08 to three structured questions in the session (questions, options and selected answers extracted programmatically from the session transcript; no retyping). Companion: `OD_2026_10_08_A9_33_hall_run_location_hall_air_chemistry_plenum_v8.json`. Immutable after commit.

---

## Structured questions and answers — 2026-10-08T03:24:59.874Z — sha256 of the JSON block below `2faea0a9c6026d9fc26be65e9b1c8d6fab7c3ed18fa6074ea92cbade79d6ef21`

````json
{
 "questions": [
  {
   "header": "Hall runs",
   "multiSelect": false,
   "options": [
    {
     "description": "You add julialang-s3.julialang.org, pkg.julialang.org, storage.julialang.net under Network access → Allowed domains; runs happen in this container, Xe family first.",
     "label": "Allow Julia hosts here (Recommended)"
    },
    {
     "description": "I trigger the committed workflow_dispatch workflow for the Xe family only (~3,000–4,500 runner-minutes; may exceed the free allowance on a private repo).",
     "label": "GitHub Actions, Xe first"
    },
    {
     "description": "Xe + N2_PROXY in one dispatch (~6,000–9,000 runner-minutes).",
     "label": "GitHub Actions, all"
    },
    {
     "description": "Keep everything preregistered and ready; no runs yet.",
     "label": "Hold the runs"
    }
   ],
   "question": "Where should the 4,536 preregistered HallThruster.jl H1 envelope cases run? (Estimated 100–150 CPU-h, extrapolated; Julia hosts are blocked in this container.)"
  },
  {
   "header": "Air chem",
   "multiSelect": false,
   "options": [
    {
     "description": "Preregister a narrow, sourced Hall O/O₂ chemistry contract (like NP-ICP-CHEM-AIR), no fabricated coefficients; air stays NOT_EVALUATED until admitted.",
     "label": "Authorize Hall O/O₂ contract (Recommended)"
    },
    {
     "description": "Classify XE_CONTINGENCY only; air stays NOT_DETERMINABLE and is reported as the open condition.",
     "label": "Xe-only conclusion for now"
    },
    {
     "description": "Owner ruling that N2_PROXY may bound air for layer (a) — would need a stated physical justification.",
     "label": "Register N2-proxy as bounding"
    }
   ],
   "question": "AIR_PRIMARY has no Hall O/O₂ chemistry, so the air-mode architecture conclusion stays NOT_DETERMINABLE whatever the runs show. How should air be handled?"
  },
  {
   "header": "Plenum next",
   "multiSelect": false,
   "options": [
    {
     "description": "Plenum transients stay PYTHON_REFERENCE (PARITY_FAILED); not on the Hall critical path; revisit later.",
     "label": "Keep v8 as the result (Recommended)"
    },
    {
     "description": "A successor where the lightly damped stable loops form their own group, chosen from inputs, with fresh held-out vectors and their own bounds; the v8 failure stays on record.",
     "label": "v9 with damping stratum"
    },
    {
     "description": "Score the lightly damped tail like the unstable stratum (class and eigenvalues only).",
     "label": "v9: treat near-neutral as ill-posed"
    }
   ],
   "question": "Plenum/feed v8 was scored once and failed, on a stable but barely damped loop. What next?"
  }
 ],
 "answers": {
  "AIR_PRIMARY has no Hall O/O₂ chemistry, so the air-mode architecture conclusion stays NOT_DETERMINABLE whatever the runs show. How should air be handled?": "Authorize Hall O/O₂ contract (Recommended)",
  "Plenum/feed v8 was scored once and failed, on a stable but barely damped loop. What next?": "Keep v8 as the result (Recommended)",
  "Where should the 4,536 preregistered HallThruster.jl H1 envelope cases run? (Estimated 100–150 CPU-h, extrapolated; Julia hosts are blocked in this container.)": "Allow Julia hosts here (Recommended)"
 }
}
````

## Delivered answer text

````text
Your questions have been answered: "Where should the 4,536 preregistered HallThruster.jl H1 envelope cases run? (Estimated 100–150 CPU-h, extrapolated; Julia hosts are blocked in this container.)"="Allow Julia hosts here (Recommended)", "AIR_PRIMARY has no Hall O/O₂ chemistry, so the air-mode architecture conclusion stays NOT_DETERMINABLE whatever the runs show. How should air be handled?"="Authorize Hall O/O₂ contract (Recommended)", "Plenum/feed v8 was scored once and failed, on a stable but barely damped loop. What next?"="Keep v8 as the result (Recommended)". You can now continue with these answers in mind.
````

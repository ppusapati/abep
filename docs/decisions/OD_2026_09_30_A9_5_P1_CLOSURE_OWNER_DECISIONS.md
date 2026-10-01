# P1Q-15 / P1Q-16 OWNER DECISIONS (A9.5) — verbatim record, 2026-09-30

Recorded verbatim from the owner's message of 2026-09-30 (session chat; LaTeX kept as written, including the incomplete
P1Q-16 formula block). Machine-readable companion: `OD_2026_09_30_A9_5_p1_closure_owner_decisions.json`. Immutable after
commit; later amendments are new addenda.

---

P1Q-15 — Kirchhoff Current-Closure Rule
Sign convention
Use one global convention for every ICP-45 capacity record:
[
\boxed{\text{conventional current INTO the defined isolated electrical network is positive}}
]
Every current channel must be transformed into this convention before analysis.
Required signed terms include, where physically present/measurable:
[
I_{\rm ecollector}
]
[
I_{\rm H1,body}
]
[
I_{\rm anode}
]
[
I_{\rm facility}
]
[
I_{\rm ICP,body}
]
and any other intentional electrical terminal crossing the registered network boundary.
Define the Kirchhoff residual:
[
R_I=\sum_k I_k.
]
For the floating-anode ICP45_CAPACITY baseline:
[
I_{\rm anode}\approx0
]
by construction, but its potential is still recorded.
Do not silently set an unavailable current channel to zero.
Combined uncertainty
For independent calibrated current channels:
[
u_R=
\sqrt{\sum_k u^2(I_k)}
]
including:

* calibration uncertainty;
* zero/offset uncertainty;
* resolution;
* repeatability where applicable;
* any registered RF-pickup contribution.

If correlations are established, use the full covariance form rather than the independent-channel approximation.
Admission rule
An ICP45_CAPACITY record is electrically closure-valid only if both conditions hold:
Statistical closure
[
\boxed{|R_I|\le3u_R}
]
and
Fractional physical closure
[
\boxed{
\frac{|R_I|}
{\max(I_{e,\mathrm{collector}},,I_{\rm scale,min})}
\le0.02
}
]
where (I_{\rm scale,min}) is a small registered denominator floor based on instrument capability, used only to avoid an unstable percentage near zero.
Thus the unexplained current residual must be:

* statistically consistent with zero at approximately the 3-sigma level; and
* no more than 2% of the extracted-current scale.

Instrument adequacy rule
If:
[
3u_R > 0.02,I_{e,\mathrm{collector}}
]
at a candidate qualification point, the instrumentation is not good enough to establish the required 2% closure.
The point becomes:
`NOT_EVALUATED_INSTRUMENT`
rather than having the tolerance widened.
Do not relax the 2% criterion after observing propulsion results.
Invalid records
A capacity point is excluded if:

* current sign conventions differ between channels;
* an intentional return path is unmeasured;
* an unintended ground path is found;
* (|R_I|>3u_R);
* fractional closure exceeds 2%;
* RF-ON/RF-OFF pairing is not matched;
* synthetic and measured evidence are mixed;
* the H-1 anode is not physically disconnected/floating in an ICP45_CAPACITY record.

Excluded points remain in the raw record with the exclusion reason.
P1Q-16 — Capacity Formula Confirmation
Confirmed:
I_{e,\mathrm{collector,RFON}}
I_{e,\mathrm{collector,RFOFF}}
}
]
using signed currents under the same registered current convention.
The RF-OFF term estimates facility/background electron collection.
No absolute-value correction is permitted.
No zero-clipping is permitted.
Hall-ON measurements remain:
`NEUTRALIZATION_CONSISTENCY`
and never define (I_{e,\mathrm{cap}}).
Resulting ICP-45 evaluation
Once (I_{d,\max,H1}) is registered:
[
M_n=
\frac{I_{e,\mathrm{cap}}}
{I_{d,\max,H1}}-1.
]
ICP-45A is eligible for evaluation only when:

1. the capacity point passes current closure;
2. the matched RF-OFF correction is valid;
3. all required uncertainties are available;
4. (I_{d,\max,H1}) is registered.

Then the preregistered one-sided lower bound must satisfy:
[
\boxed{M_{n,\mathrm{LB}}>0}.
]
Until all four exist:
`ICP45 = NOT_EVALUATED`.

fix all the issues

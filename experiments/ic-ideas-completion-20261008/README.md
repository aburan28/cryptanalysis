# Seven IC lead gates, 2026-10-08

This directory continues the [earlier seven-lead stage study](../ic-ideas-20261007/README.md).
Every result here has `candidate_id: null`: none defines a complete new IC
pipeline or a one-target online DLP measurement. Sage work used the checked
repository launcher, with its [runtime receipt](sage_runtime_info.json) saved
before the jobs. CPU times are exploratory because the host lacks an isolated
benchmark receipt. Planted targets validate algebra and are never used as
ordinary-query relation-yield estimates.

## Decisions from the new gates

| Lead | New result | Decision and exact limit |
| --- | --- | --- |
| G1 | The [complete finite Boolean ideal trace](g1_ideal_trace.json) learns rank-increasing polynomial multiples from the first N31 target. Exhaustive truth-table solution counts independently certify each full ideal dimension. The first trace spans the full ideal for **1/16** m=2 targets and **2/16** m=3 targets. | One-target reuse of *only the useful independent multiples* fails the basis-equality gate. A production F4 trace may retain extra dependent rows and is still a distinct implementation question. Ratios from incomplete replays are invalid. |
| G2 | An actual [degree-three barrel Macaulay matrix](g2_n19.json) has binary rank **8,399** at N19; character ranks 443 and 442 reconstruct it as `443 + 18·442`. The [N23 matrix](g2_n23.json) has rank **14,767**; `643 + 11·642 + 11·642` reconstructs it. The run eliminates each character block over its exact extension field. | Cyclic block reduction is exact for these expanded matrices. It is not yet an F4 Gröbner basis comparison or an isolated speed result. [N131 dimensions](g2_n131_projection.json) project 3,432,463 full source rows and 10,116,738 ambient columns at this degree; even one dense nontrivial character block has a **34.4 GB** coefficient floor over GF(2^130). Sparse F4 behavior remains unknown. |
| G3 | The prior [complete N41 degree-four census](../ic-ideas-20261007/results/g3_full_rows_followup.json) has 2,017,933 rows and 247,444,987 nonzeros. The new [Krylov budget](g3_krylov_budget.json) gives **4,394,565,333** ambient columns at degree five. A conventional 64-vector row-projection Wiedemann sequence at degree four would stream about **125 TB** of 4-byte indices, assuming no structural compression or early termination. | The proposed full block Wiedemann solve has no measured completion. This budget rules out treating a streamed degree-four operator as a practical solve under the current resource envelope. It is conditional on that conventional square projection; it does not prove a lower bound for every sparse solver. |
| G4 | The one-variable exact equation `z^(2^19)+z` exceeds the installed Singular exponent limit. An exact degree-two Frobenius chain uses 25 field variables; a degree-four chain uses **16**. The [chain witness check](g4_chain_equivalence.json) agrees with direct finite-field roots in all 12×64 planted cells and removes the same eight false algebraic-closure hits. Matched Sage/Singular Gröbner runs for [target 0](g4_target0_chain4_boolean_final.json) and [target 2](g4_target2_chain4_boolean.json) completed with chain4 and Boolean encodings. | The initial seven-variable mixed system is not exact. Exact chain4 remains smaller than the 25-variable Boolean system, but paired exploratory solve times are close and unstable. This is the same Gröbner method, not a matched msolve F4 implementation. Preserve the [chain2 control](g4_chains.json) and [earlier timeout/error rows](g4_matched.json), whose [original source](g4_matched_groebner_v0.py) is retained. |
| A1 | The [frozen fastindex4 build budget](a1_fastindex_budget.json) applies the N53 600-column geometry and its ten multiplier classes to the index builder's actual nested loops. Its 6,000-column closure would make **1,908,000,000** S3 root calls; state and two-root staging alone require at least **106.8 GB** before hash-table construction. | The proposed full closure fails its fixed-memory premise for this PDP architecture. A 60-seed-column closure gives 600 geometric columns and 60 independent log variables at the same index dimensions as a 600-column unclosed base; that is a separate equal-memory experiment. N53 ordinary-query relation yield under that new policy has not been measured. |
| A2 | The [direct selector frontier](a2_selector_frontier.json) combines the prior exact N23 enumeration with the three-leaf chained system: 164 Boolean variables and **29,786,296** ambient degree-four columns for 47-bit cyclotomic selectors, versus 92 variables and **2,924,014** columns for 23-bit normal-basis selectors. All 17,296 sparse sums in the prior receipt fail the proposed root-power membership equations. | The root-power membership shortcut is rejected. The direct selector encoding is about 10.2× wider in degree-four columns for the matched arity. A compact lookup encoding may change that cost; no F4/WDSat solving degree has been measured for it. |
| N1 | The [augmentation gate](n1_gate.json) checks 256 valid N23 field S3 identities made from two weight-two cyclotomic leaves. Their fixed sparse lifts fail exact group-algebra S3 for **256/256**, regardless of the third lift: augmentation maps both leaves to zero and maps S3 to one. Exhaustive enumeration of all `2^24` kernel words finds minimum odd kernel weight **11**; parity repair raises a two-term leaf to support at least nine. | The fixed sparse weight-two lift cannot support the proposed additive-combinatoric S3 step. The prior dense CRT section still gives exact lifts; changing sections and finding a useful sparse section are separate questions. |

## Accounting and reproduction

The numerical gates above are stage diagnostics. No `IC1` candidate or run ID
is assigned, and one-target IC online time, paired rho time, and online speedup
remain unknown. The G4 supervisor records failures and timeouts as rows. Its
per-worker limit includes Sage startup; the worker also records the narrower
Gröbner interval. Both intervals are exploratory. The G1 and G2 comparisons
use fixed target cells and exact algebraic checks, not a host-level CPU
isolation record.

Replay from the repository root. All Sage commands use the checked launcher:

```sh
./sage --runtime-info > /tmp/ic_ideas_completion_runtime.json
./sage -python experiments/ic-ideas-completion-20261008/g1_full_ideal_trace.py --output /tmp/g1_ideal_replay.json --targets 16
./sage -python experiments/ic-ideas-completion-20261008/g2_degree3_blocks.py --output /tmp/g2_n19_replay.json --degrees 19
./sage -python experiments/ic-ideas-completion-20261008/g2_degree3_blocks.py --output /tmp/g2_n23_replay.json --degrees 23
./sage -python experiments/ic-ideas-completion-20261008/n1_augmentation_gate.py --output /tmp/n1_gate_replay.json --samples 256
python3 experiments/ic-ideas-completion-20261008/validate_results.py
```

The G4, A1, A2, G2 projection, and G3 budget runners have their arguments in
their source files. For scripts with a fixed output path, run in an isolated
copy with the prior result file removed; their saved receipts are immutable
inputs to the validator. The G4 supervisor updates its one receipt after each
worker so a timeout cannot erase earlier rows. The earlier G4 error receipt
uses the preserved v0 source; use the linked final chain4 receipts for the
matched comparison.

# Balanced S3 pair tree shrinks the exact m6 circuit by 1,030 variables

An exact pair-first, six-summand native-XOR circuit now covers all four raw
target lifts of the same frozen ECC2K-130 ordinary query under both equal-B
source policies. Relative to the prior target-first circuit, each balanced
formula has **1,030 fewer variables, 131 fewer ordinary clauses, and 899
fewer native XORs**. Checked Sage reconstructed both planted pair trees and
verified every Boolean root, including a rejected one-bit target mutation.
Both ordinary searches entered CryptoMiniSat's live restart loop and reached
the frozen external 150-second wall cap with `BOUNDED_UNKNOWN`. The exact
normal4 and W24 transcripts retain 657 and 749 live restart rows,
respectively. The structural reduction therefore has not yet produced a
verified ordinary relation or a novel matrix row.

## Frozen inputs and circuit

The [protocol](PROTOCOL.md) fixes source curve
`EC1N131Ckb1h136f03e58c98`, the same four raw x-target lifts of public
query zero, and `B=11,743,888` actual subgroup-usable factor-base points for
both W24 and normal4. The exact leaf constraints, ascending selector rule,
target mux, and native-XOR code generator are imported from the
[four-lift parent](../ecc2k130-equalb-four-lift-pdp-20261010/RESULT.md).
The new tree evaluates S3 on three disjoint leaf pairs, combines the first
two pairs, and closes against the selected target x. It has four finite
intermediate x values rather than five plus a final equality. The [checked
Sage replay](runs/R1/sage_balanced.json) independently reconstructed the
six selected source points for each policy, their three pair sums and
four-leaf sum, and their final group sum. Both planted trees were finite;
the Boolean IR accepted each exact assignment and rejected a target-bit
mutation. The parent's checked Sage four-lift, eight native-XOR mux, and
exact leaf controls remain prerequisites.

| Policy | Balanced vars | Balanced clauses | Balanced XORs | Target-first vars | Target-first clauses | Target-first XORs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Normal4 | 536,683 | 599,988 | 300,963 | 537,713 | 600,119 | 301,862 |
| W24 | 336,209 | 340,190 | 221,402 | 337,239 | 340,321 | 222,301 |

The byte-exact XCNFs are preserved as deterministic gzip archives, with
[normal4](runs/R1/normal4_m6_four_lift.xcnf.gz) and
[W24](runs/R1/w24_m6_four_lift.xcnf.gz) raw SHA-256 values
`f4e6828d7cfa7a6063f1f49516e6859c920846897ba5a488fe989d1db763deec`
and `f71601554772d6805b364638bc25fce1a23c96b0df65f4b9fd8a2dedd5f45e3a`.
The [archive receipts](runs/R1/normal4_m6_four_lift.archive.json)
bind compressed and decompressed bytes.

## Ordinary-query results and accounting

Pinned CryptoMiniSat 5.14.7 SHA-256
`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`
ran normal4 then W24, one thread each, with native XORs,
`--maxtime=120`, an external 150-second wall guard, and a 4 GiB RSS guard.
The host lacked the required isolation receipt. Both processes were killed
by the external guard before emitting a terminal solver status; the raw
restart tables prove that search had begun. These are censored outcomes,
not UNSAT certificates.

| Policy | Solver status | Formula build s | Solver wall s | Build + solver s | Peak observed solver RSS | Live restart rows | Last conflicts displayed | Verified relations | Novel rank |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| Normal4 | `BOUNDED_UNKNOWN` | 97.630 | 150.244 | 247.875 | 346,013,696 B | 657 | `258K` | 0 | unknown |
| W24 | `BOUNDED_UNKNOWN` | 15.368 | 150.128 | 165.496 | 359,284,736 B | 749 | `305K` | 0 | unknown |

The builder and solver intervals were recorded on a contended host. Their
sums are stage diagnostics, with raw lift preparation already completed;
they omit any target-dependent query generation, transport, relation check,
matrix work, target descent, and recovery. They cannot be paired as online
IC speed ratios with the prior target-first runs. The live table displays
rounded `K` conflicts, not exact terminal conflict totals. The runner's
original `search_progress_lines: 0` field counted only spelled-out summary
lines; external termination prevented those lines from being printed. The
independent [normal4](runs/R1/normal4_m6_four_lift_audit.json) and
[W24](runs/R1/w24_m6_four_lift_audit.json) audits parse the raw `c rst`
rows, bind formula and transcript hashes, and distinguish live search from
that summary-extraction defect. The raw runner receipts are preserved.

The factor-base geometry is unchanged: normal4 has 44,824 potential
signed-Frobenius log columns, and the equal-B source W24 prefix has
5,869,878 potential columns. Those counts are not actual matrix rank or
linear-algebra cost. The S3 pair tree covers finite intermediate x values;
a complete PDP must account for partial sums at infinity before treating
its solution set as exhaustive.

## Decision

The exact circuit-size change is small compared with the full 300,963-XOR
normal4 formula, and both capped ordinary runs remain censored. Another
association-only S3 change has low priority. The next normal4 PDP gate
should encode each weight-four selector as four distinct 7-bit support
indices, prove exact equivalence to the frozen 131-bit mask membership, and
measure its leaf and full-m6 formula sizes under the same control points.
Proceed to ordinary query search only if that encoding passes independent
point and Boolean controls and materially changes the circuit; retain the
W24 four-lift formula as the paired reference. The first promotion measure
remains verified relations and novel rank per fully charged query. The
16/256-query prefixes, final matrix, and same-point rho comparison follow
only after that gate produces useful rows. `candidate_id` remains `null`.

The [R1 manifest](runs/R1/manifest.json) binds the source, frozen parent
inputs, checked Sage receipt, archived formulas, raw solver transcripts,
audits, and this decision.

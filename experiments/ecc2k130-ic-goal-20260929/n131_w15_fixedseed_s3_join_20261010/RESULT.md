# Exact target-coupled S3 join of two W15 fixed-seed pair domains

The complete pair-output sets for fixed seeds 12004 and 9022 now admit
an exact challenge-field S3 join without a dense norm polynomial or SAT
expansion. Each supplied reciprocal target coordinate requires one
quadratic root solve per enumerated output on one side and a lookup in
the other set: the checked-Sage direction solves 8,176 quadratics against
8,340 indexed outputs. The constructed four-atom sum
has one coordinate hit, independently replayed through the raw curve
group. Both admissible raw lifts of the published ECC2K-130 point have
zero coordinate hits in these two fixed pair domains. The full-domain
Sage scan in the opposite direction and a terminal hash audit agree.

This is an exact local family filter on `EC1N131Ckb1heb5f1998f20b`,
using `GF(2)[t]/(t^131+t^13+t^2+t+1)` and curve
`y²+xy=x³+1`. It applies to the first two fixed-seed blocks of the
twelve-point W15 source: seed 12004 at rotation 0 and seed 9022 at
rotation 13. The [previous complete enumeration](../n131_w15_pair_output_prefix_gate_20261010/pair_roots.json)
contains 8,176 and 8,340 distinct reciprocal pair outputs, respectively.
Its [independent root audit](../n131_w15_pair_output_prefix_gate_20261010/prefix_audit.json)
checked every output against the exact pair quadratic and usable mask
policy. The full IC pipeline is still proposal-stage, so `candidate_id`
is `null`.

For reciprocal pair outputs `C,D` and reciprocal target coordinate `q`,
the S3 link is

`(C+D+q)² + CDq + (CDq)² = 0`.

For fixed `D,q`, this is a quadratic in `C` with coefficients
`A=1+(Dq)²`, `B=Dq`, and `E=D²+q²`. The producer solves all rational
roots using the odd-degree half-trace and checks them against the full
left set. The independent Sage audit instead fixes every left `C`,
solves for `D`, and looks up the full right set. Both implementations
handle exceptional linear or zero-coefficient cases explicitly. All
8,340 right outputs in each frozen case took the two-root branch; every
computed pair was checked in the S3 identity.

The [protocol](protocol.json) froze the exact source and input hashes,
one worker, a 120-s cap per supplied coordinate, and 4-GiB RSS cap.
The constructed coordinate comes from the first four raw leaves of the
previous complete XCNF witness. The public cases use the two trace-zero
raw preimages of the published subgroup point
`(2309658012506412099988466246134815930289,
1578526100003023531340803776621036465818)`.

| N131 fixed-seed S3 case | Complete coordinate hits | Bit-field query | Checked-Sage query |
| --- | ---: | ---: | ---: |
| Constructed four-atom sum | **1** | 39.876 s | 10.522 s |
| Published point, raw lift 0 | **0** | 48.057 s | 7.794 s |
| Published point, raw lift 2 | **0** | 35.834 s | 16.573 s |

The [bit-field producer](result.json) used 0.020 s of domain loading and
29,048,832 B sampled peak RSS. The separately [frozen Sage query](sage_query_result.json)
used 0.515 s of field/domain setup and 244,367,360 B sampled peak RSS.
Each query interval starts with `q` supplied and ends after all inverse
roots and set lookups; source enumeration, process launch, raw-target
preimage construction, and the later replay are separate. These are
stage diagnostics on an unisolated host, not a controlled speedup or a
complete single-target online DLP interval.

The [independent checked-Sage audit](sage_audit.json) recomputed all
three hit sets using the opposite orientation, rebuilt the four positive
source points from raw leaves, checked their two pair outputs and
four-point sum, and checked the cofactor-four subgroup projection. Its
complete audit took 2.858 s outside the measured query runs. The
[terminal audit](terminal_audit.json) binds the two frozen protocols,
complete query receipts, exact domains, source hashes, public raw lifts,
and group replay. The [checked Sage runtime](sage_runtime_info.json)
was recorded before the Sage measurements.

The zero-hit public rows classify only this two-fixed-seed four-atom
family. A twelve-point relation must still choose four more pair blocks
jointly with the public target. The next solver gate should replace the
5,332,992 explicit constrained-block combinations in the existing
[unpinned N41 seed-partitioned join](../n41_seed_partition_indexless_20261010/RESULT.md)
with target-coupled family elimination while preserving its independently
replayed twelve-point witness. Count rejected seed/output families and
complete work/RSS before projecting that generator to N131.

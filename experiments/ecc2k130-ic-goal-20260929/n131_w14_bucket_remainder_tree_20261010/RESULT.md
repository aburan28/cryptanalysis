# A reusable remainder tree replaces the dominant N131 bucket GCD

The exact degree-131 W14 `s=t` bucket now tests a proposed four-atom
output by evaluating its norm at all **4,124 known left-bucket roots**.
Four frozen queries reproduced the prior GCD decisions: both trace-zero
controls returned no roots, and both constructed-positive queries returned
the same independently audited root. The reusable tree took 11.938
seconds to build. Target-dependent root scans took **37.588–43.484
seconds**, compared with **106.588–111.304 seconds** in the prior GCD
stage on these two inputs. Complete output-query intervals were
49.655–57.316 seconds. This is a measured decomposition-kernel
improvement on an exploratory, unisolated host; the exact decisions and
algebraic equivalence do not depend on wall timing.

The curve is `y²+xy=x³+1` over
`GF(2)[t]/(t^131+t^13+t²+t+1)`, curve ID
`EC1N131Ckb1heb5f1998f20b`. The prior
[exact root census](../n131_w14_seed_bucket_norm_20261010/RESULT.md)
filtered the audited W14 source to 2,062 admissible `s=t` mask pairs and
4,124 distinct raw pair-output x coordinates at each of rotations 26 and
39. The positive output is the constructed four-atom raw group sum; the
separate trace-zero output is the frozen negative control. The
[independent Sage audit](../n131_w14_mixed_rotation_fouratom_join_20261010/sage_audit.json)
replayed the positive raw points, subgroup projection, and control.

For a target-dependent norm polynomial `N(X)` and left-bucket roots
`a_1,...,a_4124`, `gcd(N, product_i(X+a_i))` has root `a_i` exactly when
`N(a_i)=0`. The [implementation](run.py) keeps the balanced subproduct
tree of the left-bucket polynomial from setup. For each query it forms
the same balanced S3 factor product as the [prior GCD producer](../n131_w14_seed_bucket_norm_20261010/query.py),
reduces modulo the left polynomial, and propagates remainders down 13
tree levels. A zero remainder at a linear leaf is an exact bucket hit.
All four saved zero-root sets agree byte for byte with the prior GCD
sets; [verification](verify.py) binds the source hashes, point controls,
phase records, and resource limits.

| Frozen proposed output | Prior GCD-stage control | Remainder-tree root scan | New complete target-query wall | Zero-root count |
| --- | ---: | ---: | ---: | ---: |
| Trace-zero, first | 106.588 s | 41.573 s | 54.560 s | 0 |
| Constructed, first | 111.304 s | 40.080 s | 52.907 s | 1 |
| Constructed, repeat | same frozen input | 43.484 s | 57.316 s | 1 |
| Trace-zero, repeat | same frozen input | 37.588 s | 49.655 s | 0 |

The [protocol](protocol.json) froze the `control, positive, positive,
control` order, accepted Sage runtime, one worker, 600-second complete
producer cap, and 4-GiB process RSS cap. The [run receipt](result.json)
records exact nanosecond phases, source/input hashes, terminal statuses, and
peak self RSS. Complete producer wall was 226.453 seconds for the four
queries and reusable setup; peak process RSS was **1,607,008,256 bytes**.
The retained [stdout](run.stdout.txt) shows active setup, every terminal
query, and completion; stderr is empty. The prior GCD producer peaked at
1,126,039,552 bytes, so the tree spends additional memory within the
same 4-GiB gate. The paired baseline has one run per input and neither
run has a host-isolation receipt, so the CPU ratios remain exploratory.

This stage has `target_count: 0` and `candidate_id: null`: the inputs are
proposed four-atom outputs. Its next method gate is a target-coupled
generator that selects a small set of seed families and partial outputs
while multiple pair blocks remain free. The current measured per-output
cost gives that generator a concrete query budget; broad seed sweeps
remain outside the 600-second envelope. An unpinned ordinary relation
on the frozen N131 public point, useful rank, factor logs, fresh target
recovery, and matched single-target rho timing remain the full-pipeline
gates.

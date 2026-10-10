# Group-batched preparation of the N131 pair-output stream

The exact W14 pair-output stream can now be prepared from curve-point
addition using **one source batch inversion and four inversions per seed**,
instead of six field inversions for every usable unordered mask pair.
For the frozen 64-seed N131 panel, that is **257 inversions in place of
792,606**. The rotated-source producer built all **264,202 entries per
rotation** in **8.962 s** with a 7,962,624-byte process high-water RSS.
Its complete packed index is byte-for-byte identical to the first
group-batched implementation. Against the previously archived quadratic
producer, every output coordinate and mask-pair witness agrees; 131,929
stored Artin–Schreier root choices differ by one, which leaves both
inverse roots unchanged. The unchanged query reader reproduced the exact
positive witness and negative-control hit lists.

This is a preparation improvement for the proposed-output S3 inverse on
`EC1N131Ckb1heb5f1998f20b`, over
`GF(2)[t]/(t^131+t^13+t^2+t+1)`. The source is the audited W14
rational-mask support of 8,220 masks; the two pair rotations are 26 and
39. The full IC pipeline remains proposal-stage, with `candidate_id:
null`. The [version-two protocol](protocol_v2.json) fixed source and
binary hashes, the exact 64 seeds, one worker, 120-second preparation cap,
30-second per-query cap, and 4-GiB RSS cap before measurement.

## Construction

For each source mask, the diagonal atom has `x=1/w`, where `w` is its
linear source element. The producer batches the 8,220 inversions for
these `x` values, obtains one rational `y` per point by half-trace,
checks `y²+xy=x³+1`, and applies Frobenius rotations 26 and 39 **once
per source point**. A point's sign is arbitrary here: adding and
subtracting the second point enumerates both reciprocal pair-output
coordinates for each unordered mask pair.

For each seed, the producer groups all usable pairs before computing
curve sums. In each rotated window it batch-inverts every `x_a+x_b`,
computes `P_a+P_b` and `P_a-P_b` with the same denominator inverse,
then batch-inverts both resulting `x` values. That is two inversions per
window, four per seed. The saved left half-trace root is obtained from
the resulting curve point as `h=yc+x`, with `c=1/x`: the curve equation
gives `h²+h=(c+1/c)²`. This avoids a half-trace per pair output.
Every stored root is checked against that identity before writing the
unchanged packed-index format.

The first [group-batch producer](prepare.cpp) rotated every completed
pair output. The final [rotated-source producer](prepare_rotated.cpp)
moves those Frobenius operations into reusable source setup. Both
versions produced the same 15,588,314-byte index digest
`7c329085f03d96bc0a09716faf8959bc5014c372c2ea25479cfe944e06399705`.
The [terminal audit](terminal_audit.json) rechecks both frozen source
maps and **every** left/right record against the archived
[quadratic index](../n131_mixed_s3_stream64_20261010/index.bin).

| Frozen 64-seed preparation | Quadratic producer | First group batch | Rotated-source group batch |
| --- | ---: | ---: | ---: |
| Usable unordered mask pairs | 132,101 | 132,101 | 132,101 |
| Entries per rotation | 264,202 | 264,202 | 264,202 |
| Field inversions by algorithm | 792,606 | 129 | **257** |
| Setup wall on this host | 49.133 s | 33.279 s | **8.962 s** |
| Peak process RSS | 4,685,824 B | 6,307,840 B | **7,962,624 B** |
| Positive / control query hits | 1 / 0 | 1 / 0 | **1 / 0** |

The [rotated-source result](result_v2.json) retains native and parent
intervals, peak RSS, complete index hashes, and the unchanged reader's
two query receipts. Those query intervals ranged from 4.64 to 5.62 s in
this run, whereas the archived reader observed about 1.1 s; this host
was unisolated and visibly contended. The wall observations are stage
diagnostics, not a controlled CPU speedup. The inversion-count reduction,
byte-identical new indexes, complete record comparison, and identical
query hit lists are exact.

## Full-source boundary and next gate

The independently audited W14 source has 16,383 nonzero seeds and
33,780,028 usable unordered pairs. The [projection receipt](projection.json)
gives exact counts of **65,533 producer field inversions** and
**3,986,141,614 packed bytes** for the full seed range. Scaling the
measured 64-seed variable setup by exact pair count, with source setup
charged once, gives **2,106.6 s** of target-independent preparation;
this is an unisolated-host extrapolation, not a completed full-index run
or a runtime bound. The first projection script failed before emitting a
row because it read the support count at the wrong JSON level; its
[failure receipt](projection_failure_v1.json) preserves that attempt.

The paired-output inverse is now cheaper to prepare, but an ordinary
ECC2K-130 relation still requires a target-coupled generator of proposed
four-atom residuals. The full 4.0-GB index should be built when that
generator can supply useful candidates; the frozen 64-seed query validates
the reader and algebra, while the full-seed online I/O and wall remain
unmeasured. The next method gate is an unpinned N41 full relation from
such a generator, followed by a source-bound one-worker N131 600-second
/ 4-GiB query and independent group/column replay.

From the repository root, `python3 -B
experiments/ecc2k130-ic-goal-20260929/n131_w14_group_batch_prepare_20261010/terminal_audit.py`
rechecks the saved source identities, exact indexes, and query receipts.

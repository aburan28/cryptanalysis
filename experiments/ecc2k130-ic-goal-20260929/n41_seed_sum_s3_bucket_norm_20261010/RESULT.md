# Exact target-conditioned seed-sum bucket norm on N41

A batched S3 norm classifies the two still-free N41 pair domains on the
frozen public-target residual with **63 polynomial GCDs**. It found the
one positive seed-sum bucket pair and its independently replayed four-leaf
group witness; the negative residual had no bucket hit. The direct
per-bucket exact method gave identical decisions using **3,969 GCDs**.
The batching reduces the count of target-dependent GCD calls by a factor
of 63. Its observed positive and negative residual intervals were 8.862
and 10.508 seconds, respectively, on the unisolated host; these are
exploratory stage times. The source-bound N131 fixed-prefix work bound
keeps this suffix oracle below the challenge-width promotion gate.

This is proposal `Q20261010230500` with `candidate_id: null`,
`run_id: null`, and `target_count: 0`. The exact curve is
`EC1N41Ckb1h7d5e80d3c4d0` over
`GF(2)[t]/(t^41+t³+1)`, with subgroup order `549756390943`.
The full four-pair W6 factor base has **B=256** usable points and
**K=26** folded columns; this experiment operates on its last two
same-rotation pair domains at rotations 20 and 30. The two residuals
`(332635421840,2054854538524)` and
`(87763439808,1229415118085)` are the previously frozen positive and
negative controls from the same public-Q study. The
[protocol](protocol.json) fixes their input law, source hashes, checked
Sage runtime, one worker, 120-second cap per residual, and 4-GiB RSS cap.

## Exact bucket operator

Let `X_s` be the distinct x coordinates of usable pair sums whose two
W6 source masks XOR to the nonzero seed sum `s`. The two exact domains
each have 63 nonempty buckets, 1,956 signed pair states, and 978 distinct
pair-output x coordinates. Each `X_s` has 10–22 x coordinates. For a
target residual with x coordinate `t`, define

`S3(a,b,t)=(ab+at+bt)²+abt+1`,

`N_{s,t}(Z)=∏_{b∈X_s} S3(Z,b,t)`.

For a right seed-sum bucket `s`, `gcd(N_{s,t},F_L)` has positive degree
exactly when some left pair-output x coordinate can complete its S3 link,
where `F_L(Z)=∏_{a∈⋃X_left}(Z+a)` is a reusable polynomial of degree 978.
The roots can be mapped back to all left seed-sum buckets. The producer
then checks raw point signs and the four source indices against the exact
group residual. On these sign-closed pair domains, a degree-zero GCD is an
exact rejection of the whole right seed-sum bucket; the group check makes
an accepted x hit a verified point witness. The positive hit used left
seed sum 16, right seed sum 5, and the raw pair points
`(1873642659754,1062557535261)` and
`(1643833261314,352897407615)`.

The unbatched comparator builds the same right-bucket norm but computes
`gcd(N_{s,t},F_{L,s'})` for every one of 63 left seed-sum buckets `s'`.
It checked all `63²=3,969` bucket pairs for each residual. The
[batched run](batch_result.json) checked all 63 right buckets and agreed
with the [per-bucket run](result.json) on one positive bucket pair and
zero negative bucket pairs. The [independent replay](verification.json)
reconstructed the four source points with separate binary-field code,
checked curve and subgroup membership, four distinct folded columns,
both pair sums, and their exact residual sum. A second
[checked-Sage audit](sage_audit.json) rebuilt both 978-coordinate domains,
confirmed trace-zero output coordinates and selected product ranks, and
replayed the positive group sum.

| Target-dependent residual stage | Per-bucket GCD | Batched global-left GCD |
| --- | ---: | ---: |
| GCD calls per complete residual | 3,969 | **63** |
| Positive bucket hits / negative bucket hits | 1 / 0 | 1 / 0 |
| Positive norm build / GCD / other and replay | 0.597 / 82.035 / 0.043 s | 0.598 / 7.760 / 0.504 s |
| Positive total interval | 82.675 s | **8.862 s** |
| Negative norm build / GCD / other | 0.612 / 76.291 / 0.048 s | 0.761 / 9.744 / 0.003 s |
| Negative total interval | 76.951 s | **10.508 s** |
| Target-independent setup | 0.684 s | 0.725 s |
| Peak process RSS | 266,895,360 B | 281,477,120 B |

The positive batch remainder includes root extraction and group replay;
the exact exclusive nanosecond phases are in the run receipts. These are
two fixed residual controls, not the full four-pair public-Q relation
search. The host lacks an isolation receipt, so the wall observations do
not establish a controlled CPU speedup. The exact reduction in GCD calls
is independent of that timing uncertainty.

## Why affine bucket relaxation stops pruning

An exact [63²-bucket affine scan](affine_rank_result.json) found that the
products of the two bucket difference spans have rank **41 for every one
of 3,969 bucket pairs**. Every pair-output x coordinate in both domains
and the positive residual x has field trace zero; the checked-Sage audit
confirmed this directly on all 978 distinct outputs per domain.

For an affine relaxation `a=A+u`, `b=B+v`, the cross term in S3 is
`(uv)²+tuv`. Since the products `uv` span the field, their S3 variation
spans the rank-40 image of `w↦w²+tw`. The trace-zero property puts the
single-side variations and the base S3 value in that same image. Hence
the exact target-conditioned **linear-invariant** test is consistent for
all 3,969 relaxed bucket pairs; it cannot perform the observed pruning.
The norm succeeds because it keeps each bucket's finite root set instead
of replacing that set by its affine span.

## Challenge-width work gate

For the frozen five same-rotation W14 N131 policy, each source space has
8,220 audited masks. Before column filtering, one pair domain has at most
`4·C(8,220,2)=135,120,360` signed group states. After three pair outputs
are chosen independently of a uniform target, the two remaining domains
have at most `18,257,511,686,529,600` ordered group assignments. The
union bound therefore requires at least
**18,637,937,784,917,259,048,182** such target-independent fixed-prefix
probes for 50% success, or over `3.10×10¹⁹` probes per second in 600
seconds. The [projection receipt](verification.json) records the exact
integer calculation and its input law. It does not constrain an adaptive
target-guided generator for the fixed published point.

A literal seed-sum Cartesian search also has
`(2^14−1)²=268,402,689` bucket pairs per residual at N131. The batched
variant removes the inner GCD loop but still needs one target-dependent
norm and global-domain GCD per right seed-sum bucket, with a left
polynomial potentially far larger than degree 978. The current source
therefore supplies a complete N41 two-free-pair oracle and a useful
batching improvement, while its source-bound work and the fixed-prefix
bound prevent an N131 ordinary query under the 600-second/4-GiB gate.

The first checked-Sage runtime preflight met transient storage pressure;
its [preflight receipt](runtime_preflight_failure_v1.json) records the
failure before any workload began. The first exact-norm producer reached
its positive 120-second cap after 1,415 bucket-pair checks and one
witness, then failed to serialize a Sage integer; the
[failure receipt](failure_v1.json) and
[partial output](partial_result_v1.txt) are retained. Version two fixes
serialization and preserves both complete control rows. The
[terminal audit](terminal_audit.json) binds the frozen sources, run
receipts, independent replays, and earlier native controls.

## Next algorithm step

The next candidate must **generate target-relevant first pair blocks or
eliminate their families symbolically** before issuing residual probes.
The bucket norm can serve as an exact terminal predicate or as a control
for such a generator. A concrete next test is target-coupled modular
composition over the W14 fixed-sum additive-polynomial representation:
measure whether it rejects multiple seed-sum buckets at once without
building all pair outputs or the global left polynomial. Freeze an
unpinned N41 public-Q row search and source-bound N131 work/RSS
projection before promoting that method. Relation novelty, factor-base
logs, fresh single-target recovery, and matched rho remain subsequent
full-pipeline gates.

# DP32 / DP34 reconciliation

The deployment choice made after this investigation is the compatible
**120,320-worker, 640-thread, four-warp inverse** profile, whose three-run
screening median is **17.453024 billion updates/s**. `make gpu-production`
and `make gpu-frobenius32-120k` select it. It uses DP32 and checkpoint v2,
with fresh run IDs 12,000–12,003 under
`campaigns/ecc2k130-frobenius32-120k-v1`; older checkpoints retain their original
geometry and location. The measurements below distinguish this fresh population
from the alternative that preserves 385,024 workers.

The selected profile was deployed on four RTX PRO 6000 GPUs on 2026-09-21.
The rebuilt image's binary SHA-256 is
`108f48480710c14d4368ec924d0101293993afac66b5b7c3b27f935d781c7846`.
This exact binary passed fresh-state, record and bidirectional resume comparisons
with the pinned legacy client at populations 640, 641 and 256, each at DP0 and
DP50. All 10,249 host-reference verification operations passed, with no drops.
It also reproduced the original 355-record DP32 screen corpus exactly at
120,320 workers. The three-minute cloud canary averaged 17.202113 billion
updates/s in the GPU client and durably published all 8,547 records.

See the [exact-image validation](production/2026-09-21-120k-deployment-validation.json)
and [deployment receipt](production/2026-09-21-120k-deployment.json). Live client
rates and cloud delivery checks are recorded separately from benchmark medians.

The investigation initially selected a build preserving the legacy Frobenius
walk, DP32, checkpoint v2 and the existing 385,024-worker geometry. Five paired confirmation
runs measured **15.534303 billion updates/s** versus **15.263139** for the pinned
legacy binary, a **1.7766% measured gain**. It explicitly uses scalar inversion
with reduced conversion, inlined polynomial arithmetic and ALU squaring, and
leaves cache persistence disabled. `make gpu-frobenius32-fast` retains this
profile. The investigation itself did not redeploy the fleet.

Both profiles write a 32-byte `(seed, canonical endpoint)` record. The numbers
32 and 34 describe the maximum normal-basis Hamming weight of a distinguished
point. There are two separate compatibility questions: the stopping predicate
and the iteration function that maps a seed to its endpoint.

## What can be preserved

For the **same frozen walk**, every DP34 record already satisfying DP32 is a
valid DP32 record with the same seed and endpoint. There cannot be an earlier
DP32 on that trail: it would also have satisfied DP34 and stopped the original
walk. `dp_compat.py` implements this filter without changing either input or
existing destinations. It requires matching curve, walk identity and record
format. Configuration labels alone are not a proof of how a corpus was made.

For the remaining weight-34 endpoints, full conversion requires replay or
continuation to the first DP32 under that same walk. A packed record contains
only a canonical x-coordinate and the starting seed. In particular, it does
not contain the table walk's cycle history, so restoring an arbitrary table
endpoint with empty history is not a faithful continuation.

Under the uniform-even-weight model on 131-bit normal-basis coordinates:

| Cutoff | Probability per step | Expected steps per DP |
| --- | ---: | ---: |
| DP32 | 2.8055427503e-9 | 356,437,270 |
| DP34 | 2.4721378003e-8 | 40,450,820 |

These are model estimates, calculated as
`sum(comb(131, k) for k in range(0, cutoff + 1, 2)) / 2**130`.
The DP32 subset is **11.34865035%** of the DP34 set; the expected interval
between reports grows by **8.81162050x**. This is not an 8.81x slowdown of the
arithmetic and not a loss of 88.65% of every campaign's completed iterations.
Filtering retains only a subset of stored endpoints, and does not reconstruct
the other trails.

The normal-basis predicate and the Frobenius iteration are documented in
[Bos et al., ECC2K-130 on Cell CPUs, section 3.2](https://cryptojedi.org/papers/cbev1l-20100228.pdf).

## Why the table profile does not become legacy-compatible at DP32

The legacy walk uses `R <- R + sigma^j(R)`, with `j` derived from the current
point's normal-basis weight. The table walk adds a selected table point, with
Frobenius/sign adjustment and cycle history. These are different transitions.
Giving both the same stopping predicate does not make intersecting trails
continue together or make a table seed replay to its endpoint in the legacy
resolver.

The current database encoding stores a starting seed, not the endpoint's actual
coefficients. Its campaign identity selects the replay algorithm. Keeping an
occasional common endpoint would therefore still require preserving the source
algorithm's identity. Relabeling filtered table records as legacy records loses
the information needed to verify them. A mixed-walk resolver and provenance
format would be a separate design; matching the cutoff alone would not restore
the common-walk collision search.

## Compatibility experiment

`reconcile_dp.py` compares the SHA-256-pinned legacy binary, the current
production build, optimized Frobenius configurations and the fast table build
on one RTX PRO 6000. All run the same seed population and number of complete
updates at DP32. Every Frobenius candidate must emit the exact same sorted
multiset of records, with no drops. DP34 runs for the legacy and table binaries
also record the actual weight histogram and how many endpoints pass DP32.

The winning compatible profile then passes `codegen/testwalkcompat.py`:

- Fresh checkpoints and complete record multisets at DP0 and DP50.
- Every DP50 report independently replayed by the host reference.
- Resume in both binary directions, compared with uninterrupted use of the
  legacy binary at the same launch boundaries.
- Populations 1,280, 1,281 and 256, covering complete blocks, a partial final
  block, and the scalar inversion fallback used for small populations.
- Five fresh paired DP32 timing runs at the existing population of 385,024,
  requiring the same complete DP corpus in every repetition.

Checkpoint v2 includes population, batch and representation. It does not encode
the CUDA block size or minimum block occupancy. A change in launch geometry can
therefore preserve existing checkpoints when the population and batch stay
fixed, but this is checked on actual binaries before accepting it. The cloud
runner also validates campaign build metadata; a compatible kernel benchmark
does not by itself update that metadata or deploy a fleet.

The experiment saves complete per-variant JSON in the Modal log and a final
local receipt, resolving the receipt path before waiting on the GPU. This
addresses the previous run's failure to save its result after a successful
remote experiment.

## Fresh screening measurements, 2026-09-21

These are three-run medians on one RTX PRO 6000 at 120,320 workers, batch 16,
64 launches of 1,024 steps, run ID 11,000 and DP32. Every sample completes
126,164,664,320 scalar updates. They are kernel/DP collection rates, not cloud
reporting throughput. Different worker populations require separate timing.

| Build | Billion updates/s | DP records | Complete legacy corpus matches |
| --- | ---: | ---: | --- |
| Pinned legacy binary | 12.595496 | 355 | Yes |
| Current production 256-thread build | 9.726992 | 355 | Yes |
| Frobenius 640 threads, 4-warp inverse | 17.453024 | 355 | Yes |
| Frobenius 512 threads, 4-warp inverse | 10.864019 | 355 | Yes |
| Frobenius 512 threads, 8-warp inverse | 10.220748 | 355 | Yes |
| Frobenius 640 threads, 2-warp inverse | 17.223908 | 355 | Yes |
| Table walk, 640 threads | 22.532193 | 332 | No |

The legacy DP34 sample emitted 3,170 records, of which 355 already met DP32.
The table DP34 sample emitted 3,105 records, of which 330 already met DP32.
Its direct DP32 run emitted 332 records: filtering is not the same as re-running
with a different cutoff, because the stopping/reseeding schedule changes.

The winning screen configuration has a reproducible build target:

```sh
make -C ecc2k130/runner gpu-frobenius32-120k
```

**Population constraint:** this is the winner at 120,320 workers. Five paired
confirmation runs at the existing 385,024 workers measured **13.349656 B/s**
for this build versus **15.014291 B/s** for the pinned legacy binary. All ten
runs emitted the same 1,101 records. Thus the 640-thread build is compatible,
but is **not a speed upgrade at the existing population**. The full receipt is
[2026-09-21-dp-reconciliation-v2.json](production/2026-09-21-dp-reconciliation-v2.json).
The follow-up `--mode geometry` and `--mode cache` experiments tested the faster
arithmetic at the existing population and selected the production profile above.

Both reproduction targets' 24 explicit build settings were checked against
their measured configurations.
`make -C ecc2k130/runner check-frobenius32-fast-gpu` also builds and runs the existing
GPU arithmetic, storage, shared-sigma and client integration checks. The
cross-binary compatibility checks are separate:

```sh
python3 ecc2k130/runner/codegen/testwalkcompat.py /path/to/pinned-legacy \
  ecc2k130/runner/ecc2k130 --output /tmp/frobenius-compatibility.json
```

The initial 385k selection keeps `blockThreads=256`, `minBlocks=2`, batch
16 and 385,024 workers, so the existing campaign configuration remains valid.
Using the separate 120k profile would require appropriate launch metadata and
a plan for existing checkpoints; its result is not a production speed claim.

## Checkpoint and replay result for the 120k profile

All six compatibility cases passed: populations 1,280, 1,281 and 256, each at
DP0 and DP50. Fresh checkpoint bytes and sorted DP records match. Both resume
directions also match the legacy continuation. The DP50 corpora after the
second segment contain 3,413, 3,417 and 671 records respectively.

The 30 client invocations performed **18,863 successful host-reference report
verifications**, with zero mismatches or dropped reports. This counts verification
operations across repeated comparisons, not 18,863 distinct endpoints.

The complete commands, outputs, hashes and per-case results are retained in
[the compatibility receipt](production/2026-09-21-frobenius-fast-compatibility.json).
The local runner and database test suites also passed all 46 tests. The optional
`check-frobenius32-fast-gpu` arithmetic-suite target is provided for reproduction;
the fresh GPU evidence reported here is the cross-binary compatibility suite.

## Production-profile confirmation

The follow-up screen at 385,024 workers measured the previous production build
at 11.346191 B/s and the pinned legacy control at 15.416454 B/s on the same GPU.
The four-warp inversion default inherited from the table profile was therefore
a regression for this Frobenius workload. Explicit scalar inversion restores
that performance; the newer arithmetic adds a smaller improvement over legacy.
The larger improvement over the previous production build is a screening
comparison, not a five-run paired speedup claim.

The final selected profile and legacy control were then measured in five fresh
pairs on one GPU, with 32 launches of 1,024 steps, 385,024 workers and DP32:

| Repetition | Legacy, billion updates/s | Selected profile, billion updates/s |
| --- | ---: | ---: |
| 1 | 15.615129 | 15.748280 |
| 2 | 15.357732 | 15.610896 |
| 3 | 15.263139 | 15.534303 |
| 4 | 15.209235 | 15.493717 |
| 5 | 15.183673 | 15.482471 |
| Median | **15.263139** | **15.534303** |

Each run completed 201,863,462,912 scalar updates and emitted the same 540
records, with zero drops. The sorted corpus SHA-256 is
`091450387e7899db0588c4bad3b35c2f76bdfa2d769bd5def0198cb1db8cff51`.
These remain GPU-client measurements, excluding periodic S3/RDS reporting and
checkpoint upload overhead.

The selected binary also passed fresh/checkpoint/resume comparisons at DP0 and
DP50 for 256 and 257 workers, covering full and partial blocks. There were
3,368 successful independent host-reference verification operations and zero
mismatches. Its binary SHA-256 is
`c46f85aa0ac66308f44bdea10f39295088ba39382dc1d2b186f7d97be0fd23af`.

Complete receipts:

- [Selected profile: cache comparison and confirmation](production/2026-09-21-dp-cache-reconciliation.json).
- [Geometry comparison and confirmation](production/2026-09-21-dp-geometry-reconciliation.json).

To reproduce the comparisons from the repository root:

```sh
modal run ecc2k130/runner/reconcile_dp.py --mode geometry
modal run ecc2k130/runner/reconcile_dp.py --mode cache
```

At the end of the investigation, `build.json` pointed to the scalar profile's
receipt. The later 120k deployment selection points it to the 640-thread receipt.
Both reproduction targets match all 24 measured build settings. The investigation's `make check-cloud` run passed
the 36 runner tests, 10 database tests and Modal CLI checks. No live campaign
configuration, stored records or fleet was changed by these experiments.

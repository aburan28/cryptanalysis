# Native batch addition: PASS_LOCAL

The installed Sage 10.10.rc0 fork now selects the compiled NTL batch-addition
path for NTL binary fields. The primary suite is **1.608x**
faster than the previous optimized Python batch implementation, with a paired
bootstrap 95% interval of **1.515–1.706x**.
The independent confirmation suite is **1.527x**, interval
**1.373–1.687x**. All 26 measured cells
improve. Every frozen correctness, speed, CPU and RSS gate passes.

These are additional, directly measured gains against the preceding batch
implementation. They are not multiplied by earlier comparisons against stock
Sage. Scope is public ordinary binary-curve batched addition on this ARM64 host;
prime-field curves, scalar multiplication and complete applications were not
measured. Other work was active on the shared host, so raw timing variation and
intervals are retained. This is not an isolated-machine peak-throughput claim.
Performance cases span 64–4,096 output points; empty and singleton batches
are covered by correctness tests, without a performance claim for those sizes.

## Complete verified API measurements

Each fresh cell worker ran 12 balanced paired rounds, with four complete calls
per sample. Timings include pair construction for `add_pairs`, validation,
native storage allocation, field arithmetic, ordinary Sage point construction,
exact comparison with scalar Sage reference sums, and output cleanup. Common
field/point/reference setup is recorded separately. There are 3,969,024 verified
timed output points across both arms; all agree exactly.

Speedup is exp(median(log(paired incumbent/candidate time))), not the quotient
of separately reported arm medians. Suite aggregation is the geometric mean of
cell speedups. Independent within-cell round resampling uses 10,000 bootstrap
replicates; intervals describe this run and do not establish cross-host behavior.

| Phase | Degree | Output points | API | Paired speedup | Incumbent median ms | Native median ms |
|---|---:|---:|---|---:|---:|---:|
| primary | 19 | 64 | pairs | 1.483x | 0.288 | 0.151 |
| primary | 19 | 64 | cartesian | 1.696x | 0.189 | 0.114 |
| primary | 19 | 1024 | pairs | 1.644x | 5.922 | 3.181 |
| primary | 19 | 1024 | cartesian | 1.332x | 5.813 | 4.363 |
| primary | 19 | 4096 | pairs | 1.416x | 26.156 | 20.295 |
| primary | 19 | 4096 | cartesian | 1.579x | 26.359 | 16.694 |
| primary | 67 | 64 | pairs | 1.435x | 0.429 | 0.198 |
| primary | 67 | 64 | cartesian | 1.595x | 0.176 | 0.112 |
| primary | 67 | 1024 | pairs | 1.332x | 5.753 | 4.648 |
| primary | 67 | 1024 | cartesian | 1.968x | 4.160 | 2.146 |
| primary | 67 | 4096 | pairs | 1.644x | 24.255 | 14.485 |
| primary | 67 | 4096 | cartesian | 2.172x | 16.404 | 7.661 |
| primary | 131 | 64 | pairs | 1.445x | 0.256 | 0.161 |
| primary | 131 | 64 | cartesian | 1.737x | 0.254 | 0.123 |
| primary | 131 | 1024 | pairs | 1.681x | 4.730 | 3.362 |
| primary | 131 | 1024 | cartesian | 1.743x | 3.751 | 2.095 |
| primary | 131 | 4096 | pairs | 1.299x | 23.543 | 17.035 |
| primary | 131 | 4096 | cartesian | 2.062x | 18.158 | 8.751 |
| confirmation | 31 | 256 | pairs | 1.251x | 1.252 | 0.852 |
| confirmation | 31 | 256 | cartesian | 1.576x | 1.098 | 0.609 |
| confirmation | 31 | 2304 | pairs | 1.189x | 13.438 | 11.283 |
| confirmation | 31 | 2304 | cartesian | 1.823x | 10.641 | 5.100 |
| confirmation | 131 | 256 | pairs | 1.388x | 1.156 | 0.816 |
| confirmation | 131 | 256 | cartesian | 1.538x | 1.112 | 0.763 |
| confirmation | 131 | 2304 | pairs | 1.659x | 14.429 | 9.211 |
| confirmation | 131 | 2304 | cartesian | 1.950x | 10.086 | 5.968 |

## Correctness and resources

- `tests-001.log`: 14 test groups pass, including all nine existing binary batch
  tests and five native-specific groups. Exhaustive forced-NTL fields, alternate
  moduli, general coefficients, infinity, inverse pairs, doubling, order-two
  points, generators, field-context changes, word boundaries through degree 257,
  fallback behavior, point parent/type and interoperability are covered.
- `doctests-001.log`: all 15 existing API doctests pass.
- Each timed cell records identical installed module and extension hashes and
  checks every output against independent scalar Sage sums.
- CPU time improves in every cell. Maximum fresh-worker RSS is approximately
  264–266 MiB; candidate minus incumbent is -1.92 MiB for general pairs and
  +0.41 MiB for Cartesian addition, within the frozen 5%/2 MiB allowance.
- `build-001.log` and `build-002.log` preserve the initial tool-path and missing
  GAP environment failures. `build-003.log` records the successful Meson build.
  `install-001.json` records the first targeted installation, and `install-002/`
  verifies the documented rebuild/install helper with a no-op incremental build.
- `native-addition.patch` reverse-applies cleanly to the current source. The new
  extension is registered in Meson. This is an incremental extension installation
  into the previously built Sage runtime, not a fresh whole-distribution build.

## Mechanism and next measured target

The addition formulas and batch inversion count are preserved. A batch of n
nonzero denominators uses one inversion and 3(n-1) products for its reciprocals.
The improvement removes Python field-element intermediates and repeated
per-operation dispatch/context work by using reusable C++ GF2E values. Python
fallback and the public Sage point contract remain intact.

Input generators are consumed before the NTL field context is restored, so
arithmetic inside an iterator cannot leave the batch using the wrong modulus.
Native arithmetic finishes before Python output-point constructors are invoked.

The new diagnostic profile attributes 0.229 of 0.337 seconds (about 68%) to
ordinary Sage point construction, including repeated parent/homset work and
coordinate normalization. At that measured share, Amdahl's law predicts that
about a 2.9% reduction in construction cost is required for a 2% complete-stage
gain. The next experiment should isolate those costs and test a reusable
construction context while retaining ordinary point classes, parents,
normalization invariants, serialization and arithmetic interoperability.
Profiler overhead affects these proportions, so this is a target-selection
estimate; any follow-up needs new frozen timing and confirmation work.

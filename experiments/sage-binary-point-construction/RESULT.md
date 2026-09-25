# Batched point construction: PASS_LOCAL

The installed Sage fork now initializes standard finite-field output points
using the shared batch parent and known normalized coordinates. This produces
an additional **1.557x** primary-suite speedup over the
previously accepted native addition implementation, with a paired-bootstrap
95% interval of **1.455–1.631x**.
Independent confirmation gives **1.823x**, interval
**1.665–2.015x**.

All 40 measured cases improve. The declared primary, confirmation, per-cell,
CPU and peak-memory gates pass. These are direct additional measurements
against the preceding native binary, not a cumulative speedup obtained by
multiplying earlier experiments. The measured workload is ordinary binary-curve
batch addition, on this local ARM64 host with other work active in the background.

## Mechanism and contract

The change is confined to `binary_batch_ntl.pyx` output construction. The field
arithmetic and batch-inversion operation counts are unchanged. For exactly
`EllipticCurvePoint_finite_field`, the native loop caches the point homset and
allocator, creates a new instance, and sets:

- the Sage Element parent to the curve's point homset;
- the codomain to the same curve;
- the coordinates to the tuple `(x, y, one)`;
- the normalization flag to true, since generated coordinates already have z=1.

This is the complete fresh-constructor state for the pinned implementation.
`constructor-contract.json` binds the unchanged upstream constructor sources.
The existing field formulas already produce valid points, and the preceding
constructor used `check=False`. Input validation remains unchanged.

Custom point classes use their ordinary allocation and initialization hooks.
Existing special results such as P+O retain their input identity. Outputs do not
copy input order/comparison caches or share mutable point dictionaries.

## Complete API measurements

Each fresh cell worker performs 12 balanced paired rounds. Each sample makes
`max(4, ceil(4096/output_count))` complete calls, including input preparation,
output construction, exact comparison with scalar Sage reference sums, and
cleanup. Common field/fixture/reference setup is recorded separately.
**6,440,064 timed output points** agree exactly with the scalar reference.

The incumbent Python wrapper is explicitly rebound to its preserved compiled
extension under an isolated module name. Candidate and incumbent binary hashes
are different, recorded in the execution plan and every worker receipt, and
verified against the frozen intent. This avoids accidentally comparing two
wrappers that both select the installed candidate.

Speedup is exp(median(log(paired incumbent/candidate wall time))); it need not
equal the quotient of the separately reported arm medians. Suite aggregation
uses a geometric mean over cells. Confidence intervals use 10,000 independent
within-cell paired-round bootstrap resamples and characterize this local run.

| Phase | Degree | Model | Outputs | API | Paired speedup | Incumbent median ms | Candidate median ms |
|---|---:|---|---:|---|---:|---:|---:|
| primary | 19 | koblitz | 1 | pairs | 1.426x | 0.0078 | 0.0055 |
| primary | 19 | koblitz | 1 | cartesian | 1.397x | 0.0068 | 0.0048 |
| primary | 19 | koblitz | 9 | pairs | 1.037x | 0.0480 | 0.0381 |
| primary | 19 | koblitz | 9 | cartesian | 1.264x | 0.0329 | 0.0248 |
| primary | 19 | koblitz | 64 | pairs | 1.710x | 0.3258 | 0.1791 |
| primary | 19 | koblitz | 64 | cartesian | 1.572x | 0.1763 | 0.0834 |
| primary | 19 | koblitz | 1024 | pairs | 1.171x | 5.1256 | 3.8887 |
| primary | 19 | koblitz | 1024 | cartesian | 2.016x | 3.7441 | 2.0678 |
| primary | 19 | koblitz | 4096 | pairs | 1.537x | 31.4317 | 18.0473 |
| primary | 19 | koblitz | 4096 | cartesian | 2.092x | 21.8779 | 9.7126 |
| primary | 67 | koblitz | 1 | pairs | 1.266x | 0.0065 | 0.0047 |
| primary | 67 | koblitz | 1 | cartesian | 1.389x | 0.0085 | 0.0063 |
| primary | 67 | koblitz | 9 | pairs | 1.366x | 0.0652 | 0.0591 |
| primary | 67 | koblitz | 9 | cartesian | 1.407x | 0.0321 | 0.0239 |
| primary | 67 | koblitz | 64 | pairs | 1.916x | 0.2221 | 0.1257 |
| primary | 67 | koblitz | 64 | cartesian | 1.538x | 0.1868 | 0.1123 |
| primary | 67 | koblitz | 1024 | pairs | 2.305x | 7.3044 | 3.3601 |
| primary | 67 | koblitz | 1024 | cartesian | 2.351x | 4.2424 | 2.0150 |
| primary | 67 | koblitz | 4096 | pairs | 1.974x | 22.2631 | 11.3350 |
| primary | 67 | koblitz | 4096 | cartesian | 1.570x | 14.4998 | 8.5849 |
| primary | 131 | koblitz | 1 | pairs | 1.363x | 0.0117 | 0.0098 |
| primary | 131 | koblitz | 1 | cartesian | 1.559x | 0.0109 | 0.0074 |
| primary | 131 | koblitz | 9 | pairs | 1.537x | 0.0326 | 0.0209 |
| primary | 131 | koblitz | 9 | cartesian | 1.660x | 0.0388 | 0.0242 |
| primary | 131 | koblitz | 64 | pairs | 1.485x | 0.2211 | 0.1482 |
| primary | 131 | koblitz | 64 | cartesian | 1.294x | 0.1957 | 0.1815 |
| primary | 131 | koblitz | 1024 | pairs | 1.690x | 5.0149 | 3.2678 |
| primary | 131 | koblitz | 1024 | cartesian | 1.401x | 2.6442 | 1.9585 |
| primary | 131 | koblitz | 4096 | pairs | 1.692x | 21.3137 | 12.3481 |
| primary | 131 | koblitz | 4096 | cartesian | 1.585x | 14.8520 | 8.8636 |
| confirmation | 31 | koblitz | 256 | pairs | 1.732x | 1.1937 | 0.7635 |
| confirmation | 31 | koblitz | 256 | cartesian | 1.636x | 0.7073 | 0.4071 |
| confirmation | 31 | koblitz | 2304 | pairs | 1.582x | 12.4709 | 8.5968 |
| confirmation | 31 | koblitz | 2304 | cartesian | 1.656x | 9.5633 | 6.2097 |
| confirmation | 163 | koblitz | 256 | pairs | 1.986x | 1.2745 | 0.5969 |
| confirmation | 163 | koblitz | 256 | cartesian | 1.806x | 0.5804 | 0.2670 |
| confirmation | 163 | koblitz | 2304 | pairs | 2.158x | 11.0037 | 5.1212 |
| confirmation | 163 | koblitz | 2304 | cartesian | 2.171x | 7.5678 | 3.1936 |
| confirmation | 131 | general | 2304 | pairs | 1.702x | 10.1178 | 6.1310 |
| confirmation | 131 | general | 2304 | cartesian | 1.913x | 6.2592 | 3.9663 |

Singleton cases improve by 1.27–1.56x. The independent general-coefficient
GF(2^131) cases improve by 1.70x for general pairs and 1.91x for Cartesian sums.
The widest local gain is 2.35x, for 1,024 Cartesian outputs over GF(2^67).

## Validation and resource use

- `tests-001.log`: all 19 test groups pass. These include the complete existing
  arithmetic suite plus comparison with fresh constructor state; copying and
  pickling; hashing and point arithmetic; category/domain/codomain; custom
  constructor hooks; cache isolation; non-normalized inputs; and exception
  result identity.
- `doctests-001.log`: all 15 API doctests pass.
- CPU-time ratios improve in every cell; the largest candidate/incumbent ratio
  is 0.852.
- Separate fresh-worker RSS changes are +0.047 MiB for general pairs and
  -1.672 MiB for Cartesian sums, within the frozen 5%/2 MiB allowance.
- `install-001/` records successful compilation through the existing Meson build
  and targeted installation into the local Sage runtime. This is an incremental
  extension build, not a new full distribution build.
- `point-construction.patch` reverse-applies cleanly to the current source.
  `verify_evidence.py` checks the immutable receipts, paired orders, counts,
  summary arithmetic, acceptance gates and currently installed hashes.

## Profile and next experiment

For ten calls producing 4,096 Cartesian outputs each, the diagnostic profile
shows 40,960 general elliptic-point initialization calls in the incumbent and
zero in the candidate. Total profiled Python calls fall from 585,216 to 93,696.
Profile elapsed times are diagnostic and are not used as acceptance evidence.

The remaining native batch section accounts for 0.104 of 0.154 profiled seconds,
about 68% of the complete verified call. It includes native field arithmetic,
vector/field allocations and direct point allocation; Python profiling cannot
separate those costs. Amdahl's law requires roughly a 2.9% reduction in this
section to achieve another 2% complete-call gain.

The next diagnostic should split native preparation/storage, inversion,
coordinate arithmetic and output allocation. A falsifiable follow-up candidate
is eliminating repeated vector growth and redundant copies of active entries;
its storage cost and exceptional-batch behavior must be measured against the
current implementation on fresh confirmation inputs. Exact output verification
remains charged and must not be removed to manufacture a faster result.

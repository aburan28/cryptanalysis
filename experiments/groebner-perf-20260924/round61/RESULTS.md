# Local scratch-XOR validation

The bounded scratch candidate passes correctness and accounting checks. It
reduces the counted allocation requests inside column-matrix XOR; complete-query
speed remains unmeasured because no local timing trial passed admission.

| Frozen input | Result | Fresh-vector requests | Scratch requests, including compaction | Request reduction |
| --- | --- | ---: | ---: | ---: |
| PDP 6, seeds 1, 2, 4, 5 (each) | Verified complete query | 4,074 | 1,132 | 72.2% |
| PDP 6, seed 3 | Verified complete query | 1,096 | 391 | 64.3% |
| Random 8-variable control | Verified algebraic basis | 101,512 | 22,691 | 77.6% |
| Dense MQ, 12 variables | Work-budget failure | 79,273 | 8,147 | 89.7% |

Counts are deterministic matrix-loop reserve requests from the optimized build,
with identical sanitizer counts. They include scratch growth, fresh-vector
fallback and pivot compaction. They exclude other allocations in the solver,
checker and Python. The failed dense case is a diagnostic, not a successful
solve or speedup. The maximum scratch allocation observed in the whole frozen
panel was 2,189 words (17,512 bytes of element storage), below the 32,768-word
request cap; this is not whole-query peak memory.

All 15 test groups pass. The 92-record preflight preserves every frozen basis,
proof graph and integer producer/checker trace: 20 verified complete PDP queries,
20 verified algebra controls, and 52 work-budget failures. The independent audit
replays seven distinct proofs and solved curve controls and checks 157 bindings.
Optimized and UBSan results agree. The four-word test arm exercises fallback;
randomized tests cover 128 small ideals, and explicit cases cover 64 variables,
changing leased coefficients, thread reuse, and early/late proof/work failures.

The local machine was a physical Apple M4 Pro, 14 logical CPUs, macOS 26.6,
Python 3.13.1. The frozen plan admitted zero timed queries: one-minute load was
173.7383 against the unchanged threshold of 14; two admissions were rejected and
31 trials remained unrun. No complete-query ratio, 2x success, IC result or rho
speedup is claimed. Linux and hosted macOS rebuilding/auditing remain CI gates.

Three development failures are retained: an inherited header path needed one
extra parent component after the engine output directory moved; an initial test
passed an unsupported range object and chose a case with no repeated scratch
reuse; a replacement test initially used an incomplete frozen-fixture name.
The corrected final run passes. These failures did not establish performance
results. Their source snapshots and logs are in `results/setup-failures.json.gz`.

Reproduce the allocation analysis from the archived preflight:

```sh
python3 experiments/groebner-perf-20260924/round61/analyze_allocations.py \
  --preflight experiments/groebner-perf-20260924/round61/results/preflight.json.gz \
  --output allocation-audit.json
```

`results/index.json.gz` hashes the compact evidence and final source snapshot.
Native binaries and generated sources remain in the full local evidence archive
and are rebuilt in CI; they are not committed as cross-platform binaries.

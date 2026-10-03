# Local validation and measurement status

The row-reservation candidate passed both-mode validation on physical Apple
M4 Pro hardware. This establishes correctness for the frozen panel, not speed.

- All eleven native variants compiled with warnings treated as errors, including
  UBSan, locality/transform/identity audits and explicit budget builds.
- All 34 unit groups passed with physical Metal enabled. The new budget sweep
  checked every allowance from 0 through 512 for valid and nonlinear witnesses,
  including exact failure-prefix work/parity counts. Word boundaries through
  128 equations, the 112-word maximum row, zero witnesses and configuration
  invalidation were also exercised.
- Each of reserved and direct charging passed 72,012 control executions:
  71,796 verified bases and 216 expected root-limit inconclusive results.
  Each mode also passed 648 complete queries across 18 frozen public inputs
  through 27 variables, CPU/CPU UBSan/physical Metal, both symmetry modes,
  full/tile16 transforms, and serial/prepared/overlap schedules.
- Each separate original-ANF Python audit passed all 648 query records and
  35 distinct proofs. All 523 source, receipt and binary bindings were unchanged.
  Both modes matched checker53's proofs, bases, roots, selected assignments and
  old logical counters. The two new modes also matched each other on every
  query. Actual GPU dispatch and wide-equation CPU fallback were checked.

For the three 27-variable Metal queries with symmetry, full transforms and
serial checking, 4,749,500 to 4,864,270 witness coefficient words used 103,250
to 105,745 row reservations. No row in those queries needed the near-budget
fallback. Their logical work totals remain 8,072,767 to 8,267,885. The frozen
ARM64 disassembly confirms that the reserved 32-bit coefficient loop accumulates
work/parity counts without storing them per word, then flushes outside the loop.
Neither operation accounting nor assembly inspection is a latency measurement.

The first frozen performance attempt admitted zero queries. Its two admission
windows observed one-minute loads from 21.416504 to 23.634277 against
the unchanged threshold of 14. Both rejected admissions and 34 unrun trials
are retained. There are zero qualified timing trials; primary acceptance is
false. No speedup or automatic dispatch change is claimed. The unchanged paired
panel may be repeated when the host naturally meets the load requirement.

The first sandboxed unit run could not open Metal and reported four device
availability errors. That failed run is retained. A separate physical-device
probe succeeded outside the sandbox, followed by the passing frozen run above.
This was an environment failure; no native source change separated those runs.

| Artifact | SHA-256 |
| --- | --- |
| `physical-correctness-reserved-v2.json.gz` | `49fe6b6a6699a4c268f07b51fdd417324e6fe00f11b358c6bd719838dbee7908` |
| `independent-audit-reserved-v2.json` | `f24d1d141c922db93912c286a514e118bd25ed90f492dc2b1feba4ea4d5796d2` |
| `physical-correctness-direct-v2.json.gz` | `b399c6fee218cc9805f3181127effb4a29d7569c99b22c9dce6edf056fa12a64` |
| `independent-audit-direct-v2.json` | `3e3f60c2c9007deb27fb30b3f983be697f325dce5c9c743f4562c5fe02ab6a05` |
| `unit-tests-frozen-v2.log` | `9f7db970490de56aaf1b7b571038e5d84c9157d8332b11227bef5f83e1a51172` |
| `performance-analysis-v1.json` | `e88bcadc43df751d396f8e0cc08ed25b2c94cfa88cd999aa0e965ff29f340927` |
| `local-summary-v2.json` | `6d321fd9e345d6b7d7a4164681b80ad609aeabcbea0918e2b238f6bfd0f4d59d` |

The artifacts reside in `/private/tmp/cryptanalysis-reservation-evidence-20261003`.
The validation, audits, measurement plan and runner are versioned here. CI
rebuilds native code on its own Linux and macOS runners and retains actual
runner identity and binary hashes; those CI results are pending at this source
snapshot. Hosted Metal correctness is separate from physical M4 timing.
These remain query-stage diagnostics with `candidate_id` and full single-target
IC/rho `online_speedup` null.

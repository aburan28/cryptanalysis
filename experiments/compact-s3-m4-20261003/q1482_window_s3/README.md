# Q1482: compact four-summand S3 on exact window-orbit bases

The [pre-registered design](design_protocol.json) tests whether Q1481's
Frobenius-stable window bases give a more tractable compact `S3` search on the
same ordinary public N53/N83 targets used by Q1438 and Q1480. This changes
the factor-base policy; it is a matched-target method comparison, not a
solver-only timing ratio. Q1482 reuses the Q1480 native solver binary and
its three-link balanced `S3` chain. No expanded `S5` or full pair table is
constructed.

Each leaf is nonzero and has at least one selected cyclic window. A selected
window forces all coordinates outside its `d` positions to zero. The native
theory engine receives `d` as a *superset* Hamming-weight bound: every
window-valid leaf has at most `d` one bits. A no-chain rejection sound over
the larger weight-`d` domain is therefore sound over the window subset,
although the bound may be too loose to help search. The first solver gate is
a deterministic planted public-point control with all leaves/midpoints
pinned. The unpinned version is separate, and neither is an ordinary-yield
measurement.

| Degree | Curve ID | Window `d` | Actual usable `B` | Folded `K` | Q1481 exact set SHA-256 |
| ---: | --- | ---: | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | 14 | 430,360 | 4,060 | `42e746657e39ea4d07aafc873110339e314cd685b3bd8493eb3c60aed1354ba5` |
| 83 | `EC1N83Ckb1h876c2921cb64` | 23 | 348,006,384 | 2,096,424 | `f2d7771988cbd03fa4ea3145fc3870e5a3fc44171b9a57165257f016cdeb19d4` |

The source, exact CNF and target inputs, checked Sage runtime, solver binary,
resource limits, and stage IDs must be frozen before the six runs. Preserve
all failures and timeouts. Q1482 remains a `Q` proposal with
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`; the complete
N131 `2^x` is unknown.

## Frozen result

The design was published in commit `b7c27cb2`. Commit `5bdc153d` froze the
six byte-replayable CNFs and target files, both deterministic planted
fixtures, checked Sage runtime, source hashes, Q1480 binary hash, caps, and
the two stage IDs before any solver run:

- `PS1N53Ckb1fb430360PDP4hybridh087e9bd50e10`
- `PS1N83Ckb1fb348006384PDP4hybridh2dc35931d32a`

The [archive audit](archive_audit.json) rebuilt every CNF and independently
replayed both pinned SAT models as four-distinct-column public relations.
The ordinary target files have the same SHA-256 hashes and workload IDs as
Q1438's exact public N53/N83 targets. Each run preserves its raw stdout,
stderr, any model, a source-bound receipt, exclusive target-encoding,
materialization, native-process and relation-check intervals, and peak RSS.

| Frozen cell | Status | Verified relations | SAT propagations | Field mul / sqr / inv calls | Direct right `S3` evaluations | Right supports |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| N53 planted pinned | SAT | 1 | 51,147 | 209 / 1,236 / 18 | 0 | 0 |
| N83 planted pinned | SAT | 1 | 124,917 | 227 / 1,926 / 18 | 0 | 0 |
| N53 planted unpinned | 60 s cap | 0 | 6,444,349 | 578,428,293 / 145,062,324 / 6 | 144,578,944 | 0 |
| N83 planted unpinned | 60 s cap | 0 | 2,604,557 | 319,087,883 / 80,474,102 / 6 | 79,745,968 | 0 |
| N53 ordinary | 60 s cap | 0 | 7,019,484 | 577,444,741 / 144,816,436 / 6 | 144,333,056 | 0 |
| N83 ordinary | 60 s cap | 0 | 2,620,656 | 317,569,291 / 80,094,454 / 6 | 79,366,320 | 0 |

The pinned controls prove the input wiring and model replay for those
fixtures. The unpinned planted controls prove that a solution exists, but
neither solver run found one within the cap. The Q1480 theory engine sees
only the loose Hamming-weight-`d` superset while the actual cyclic-window
constraint lives in CNF. It still spends most of its charged work evaluating
right pairs against fixed midpoints with zero support in these search
prefixes. The result does not measure successful N53/N83 decomposition
cost, ordinary relation yield, novel rank, or a complete N131 `2^x`.
Wall times are exploratory without an isolated-host receipt.

A follow-on experiment can fix or branch on the window position early and
then measure exact window-aware propagation. At N131, any fixed-window
slice is only a subset of the full orbit-union base, so success on a small
degree cannot be extrapolated by treating that slice as the entire base.

## Reproduce custody checks

```sh
python3 experiments/compact-s3-m4-20261003/q1482_window_s3/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1482_window_s3/make_planted.py --degree 53 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1482_window_s3/make_planted.py --degree 83 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1482_window_s3/audit.py --check
```

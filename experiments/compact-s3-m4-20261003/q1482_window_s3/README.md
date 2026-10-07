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

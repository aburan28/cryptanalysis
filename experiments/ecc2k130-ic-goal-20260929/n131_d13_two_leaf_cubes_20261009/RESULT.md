# Two valid first-link leaf cubes on the N131 public target

Two deterministically selected, valid first-link leaf-code pairs were tested
against the exact d13/m12 public-Q point-decomposition formula. Both
CryptoMiniSat attempts ended `CENSORED_TIME` at their frozen 290-second wall
caps. The [independent audit](audit.json) confirms that each input differs
from the previously audited projected XCNF by exactly 26 unit clauses, its
two codes are in the exact 4,134-code factor-base domain, and both solver
processes drained. This is one supplied public target with two sequential
failed PDP attempts, not two target workloads.

| Cube | Pinned leaf codes at positions 0, 1 | Solver wall | Sampled solver CPU | Sampled combined peak RSS | Status/model lines |
| --- | --- | ---: | ---: | ---: | --- |
| 0 | `1948, 651` | 290.138 s | 94.747 s | 715,849,728 B | 0/0; `CENSORED_TIME` |
| 1 | `5053, 231` | 290.037 s | 146.247 s | 883,376,128 B | 0/0; `CENSORED_TIME` |

The charged solver-stage sum is **580.174 seconds**, including both failed
attempts. It excludes the previously constructed target-dependent source
formula and its exact CNF bridge and XOR projection. Complete one-target
online time therefore remains unknown. The host was contended and has no CPU
isolation receipt, so the CPU samples and wall values are diagnostic rather
than a controlled comparison. The separate d10 full candidate remained live
and was not interrupted.

The [frozen protocol](protocol.json) selects the two valid codes for each
cube by SHA-256 of the proposal label, cube number, leaf position, and raw
public-Q XCNF hash. An independent parser recovers exactly 4,058 forbidden
first-leaf codes from the original formula, leaving 4,134 valid codes. The
exact projection preserves original primary variables 2 through 27, so
adding the unit clauses pins the first two leaves without changing any
other CNF or native-XOR record. The [freeze source](freeze.py),
[runner](run.py), [terminal audit](audit.py), checked-Sage
[runtime receipt](runtime_info.json), generated XCNFs, raw solver logs, and
[result](result.json) preserve the input and execution identities. The
[prepared Sage replay](sage_replay.py) is used only if a later cube produces
a SAT model; it does not turn these censored attempts into relation evidence.

The earlier uniform full-curve model-count heuristic is about 149,946,445
ordered signed models across four cofactor endpoints before pinning. Dividing
by `4,134^2` gives about 8.77 models per two-code cube under that heuristic.
This is a prediction for a uniform-target model, not a measured count or a
fixed-public-Q existence proof. The two capped searches do not estimate
ordinary-query yield or useful relation rank.

The next branch is exact first-link output propagation. The checked-Sage
[root receipt](first_link_candidates.json) computes both first
partial-coordinate values for each selected leaf-code pair by direct curve
addition, verifies both against the source S3 equation, and checks that its
leading coefficient is nonzero. Thus the two distinct values are the complete
quadratic root set. All 131 first partial bits remain in the projected
formula. Freezing one value as an additional branch can remove the first
link's ambiguity before SAT search; each branch needs its own complete
solver-stage receipt and independent group replay on any model. The active
N131 relation, factor-log, and single-target online comparison gates remain
unchanged.

# Exact first-link branches for one N131 public-target query

The two complete first-link S3 roots for the frozen valid leaf pair
`(1948, 651)` were propagated into separate d13/m12 public-target XCNFs.
The [independent terminal audit](audit.json) verifies the exact formula
appendices and drained solver processes. Both branches reached their
290-second wall caps with `CENSORED_TIME` and zero solver status or model
lines. The experiment establishes that exact first-link root pinning alone
does not resolve this public-Q query within the frozen 580-second solver-stage
envelope.

| First-link branch | 131-bit partial-coordinate mask | Solver wall (s) | Sampled solver CPU (s) | Sampled combined peak RSS (B) | Status | Model lines |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 0 | `1326153277706650363670619725335793525675` | 290.037 | 87.378 | 781,615,104 | `CENSORED_TIME` | 0 |
| 1 | `2505259751266250040412388905249575863728` | 290.115 | 110.724 | 868,220,928 | `CENSORED_TIME` | 0 |

The two sequential attempts are charged to **one supplied public target**:
the observed solver-stage sum is **580.152 seconds**. The source public-Q
formula and its target-dependent CNF bridge and XOR projection were built
earlier, outside this clock. Complete one-target online wall time therefore
remains unknown. The host had no isolation receipt and a separate d10
precomputation process remained active, so these timings are exploratory
stage diagnostics. The [result record](result.json) retains both failed
attempts, wall caps, sampled CPU and memory, zero verified relations, and
zero useful rank.

The [checked-Sage first-link receipt](../n131_d13_two_leaf_cubes_20261009/first_link_candidates.json)
derives both roots by exact curve addition and verifies the nonzero leading
coefficient of the quadratic S3 equation. The [frozen protocol](protocol.json)
uses the same two valid leaf codes and adds exactly 131 unit clauses for each
root to the previously audited two-leaf public-Q cube. Each resulting formula
has 115,289 variables and 292,712 records. The audit byte-compares the
original formula body, decodes all unit literals to the declared root, checks
source hashes and attempt order, and confirms process drain. The prepared
[Sage replay](sage_replay.py) applies only to a SAT model. The checked runtime
receipt, both XCNFs, raw stdout/stderr, and process identities accompany the
result.

The next algorithmic gate is **exact second-link propagation**. With one
first-link root fixed, enumerate the 4,134 valid third-leaf codes and their
curve-addition branches; verify the next partial-coordinate values against
the second S3 equation, including exceptional cases. Encode this finite
code-to-coordinate relation directly, replacing second-link algebraic search
for a frozen branch. First prove encoding equivalence and ordinary-query
behavior on a smaller-field control, then run a fresh N131 one-target panel
under the same 600-second/4-GiB envelope with complete attempt accounting.
Any N131 model must pass the original XCNF and independent checked-Sage
point-sum, subgroup, and factor-base replay before it contributes a relation
or rank.

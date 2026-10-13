# Orbit-complete five-summand PDP on the larger N83 width-13 base

The exact **721,934-point, 4,349-column** two-coset factor base is now
wired into the five-summand S3 orbit-complete solver on the same frozen
N83 public target as the prior 684,750-point width-13 base. Its
non-coordinate 13th basis vector is represented by repeated and negated
seed literals, so the ordinary formula has **exactly the same variable,
AND-gate, CNF-clause, and native-XOR counts** as the prior width-13
formula. A planted five-point control uses both cosets and five
different Frobenius powers; CryptoMiniSat returned SAT and exact group
replay passed. The ordinary public-target attempt ended at its
600-second wall cap with `bounded_unknown`.

| Frozen property | Prior shifted width 13 | Two-coset width 13 |
| --- | ---: | ---: |
| Folded columns `K` | 4,125 | **4,349** |
| Usable subgroup points `B` | 684,750 | **721,934** |
| Full-base five-subset first moment `binom(B,5)/r` | 518.85137 | **675.88151** |
| Variables | 85,226 | 85,226 |
| AND gates | 82,668 | 82,668 |
| CNF clauses | 334,247 | 334,247 |
| Native XOR rows | 1,660 | 1,660 |
| Ordinary target status | `bounded_unknown` | `bounded_unknown` |
| Solver wall cap | 600 s | 600 s |

The comparison fixes workload `df4396f4d8fc`, its one public point,
all four raw cofactor preimages, five summands, independent 83-way
Frobenius selector on each leaf, CryptoMiniSat build, one solver thread,
the five-million-conflict ceiling, and the 600-second wall limit. The
factor base and affine leaf map are the controlled variables. The
prior [stage receipt](../n83-geometric-m5-orbit-20261012/README.md)
used offset bit 81 and the first 13 normal-basis vectors. This stage
uses the exact [two-coset affine basis](../n83-geometric-two-shift12-20261012/basis_manifest.json):
bits 37+73 as its offset, the first 12 normal-basis vectors, and one
additional vector at bits 12+37+51+73. The 4,349 sorted orbit keys
are source-bound in the [union receipt](../n83-geometric-two-shift12-20261012/union.json).

The [protocol](protocol.json) freezes source and input digests, the
same public workload, base keys, solver, limits, and phase boundary.
The [locked control](locked_control.json) pins three leaves from the
first coset and two from the second with Frobenius powers
`0,1,7,23,41`. Its compressed formula, solver output, and exact
five-point replay are retained. A [direct domain check](domain_check.json)
tested all 8,192 affine seeds and 2,656 selected rotations against the
generalized membership rule. The [ordinary result](width13_ordinary.json)
retains formula shape, solver output, archived compressed XCNF, memory,
and exclusive target-dependent phases. Its 600.076-second exploratory
PDP interval includes target-preimage construction, formula build,
formula write, the 597.960-second solver attempt, relation check,
and residual overhead. This was a shared local CPU run, so the wall
and RSS values are stage diagnostics rather than a controlled speed
ratio. The capped ordinary row does not supply an observed natural
relation yield or novel rank.

The [independent Sage replay](sage_relation_replay.json) reconstructs
the affine seed domain in a polynomial field, verifies the planted
raw and cofactor-projected points, checks all five base memberships
and their public sum, and records `no_relation_to_replay` for the
ordinary attempt. The [read-only audit](verify.py) checks protocol
and source hashes, same workload, exact base, parity with the prior
ordinary formula shape, raw and compressed artifact hashes, phase
sums, control replay, and Sage replay. The repository's checked
[Sage runtime identity](sage_runtime_info.json) was saved before
the producer. `candidate_id` remains null because relation rank,
factor-base logarithms, final sparse linear algebra, and
single-target recovery are not yet measured for this method.

From the repository root:

```sh
python3 experiments/n83-geometric-m5-two-coset13-20261012/verify.py
```

The next practical test is a stronger orbit-aware decomposition oracle
on this same public point, with ordinary relation and novel-rank
measurements. It should preserve failed attempts and charge all
target-dependent search before carrying any surviving method through
factor-base logs, final matrix work, target recovery, and same-point
rho under a declared host tier.

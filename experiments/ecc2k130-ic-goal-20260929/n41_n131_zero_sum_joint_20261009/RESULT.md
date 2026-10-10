# Target-conditioned zero-sum triple formula gate

The zero-sum triple eliminant admits a compact factorization that requires
four full field multiplications per block after its low-degree source
product is formed. Coupling four such blocks through one target-ended
five-point invariant removes both 41-bit middle coordinates used by a
three-S3 chain. On the frozen N41 public relation, the five-point formula
passes a fully pinned model and an independent raw-point replay; when the
four block outputs alone are fixed, it recovers the correct target fiber
and verifies the full XCNF assignment in **0.552 seconds**. With only
source masks fixed, the same formula reaches its **65.128-second bounded
search cap**. The next solver step is therefore a forward or otherwise
strongly propagating block-root representation, not another change to
the target join.

## Algebra and exact input

Each of four W7 blocks uses two 7-bit source masks `a,b` and the implicit
third mask `c=a XOR b`, ordered `a<b<c`. The source elements are accepted
only under the exact N41 `Tr(1/w)=0` predicate from the
[previous frozen input](../n41_n131_zero_sum_triple_20261009/input_public.txt).
Their rotations are `0,10,20,30`. The exact four-rotation factor base has
`B=504` projected subgroup points and `K=57` sign/Frobenius columns.
All formulas use the same public subgroup point
`Q=(1458168294740,1672312028033)` and its four rational raw
four-division preimages.

For one block, write `s=u1+u2=u3`, `q=w1*w2`, `z=1/(x(R)+1)`, where `R`
is its raw three-point sum. Put

```text
r = (s^2+s)(z^2+z)
f = (s+z)^2
C = q*f+s^2*r
F = (C+f+s^2)^2+(q+r)*C.
```

The [independent Sage proof and row check](witness_chart.json) recomputes
the resultant of the two block S3 quadratics and verifies it equals `F`.
The value `q` is formed from the 13 low-degree convolution coordinates
of `w1*w2`, using the 49 mask-bit products, before the four general field
multiplications in `F`. The saved ordinary row satisfies all four block
identities and the nonexceptional charts used here.

The direct join uses the previously implemented nine-term five-point
invariant on the four block outputs and one selected target preimage. An
[independent field evaluation](s5_identity.json) verifies that invariant
on the public row. This is an exact necessary equation in the selected
chart; every SAT model is checked against the original XCNF, then lifted
to signed raw points and checked against the complete group equation.

Both variants are proposals with `candidate_id: null`. Their
[S3-chain protocol](protocol.json) and [direct-S5 protocol](s5_protocol.json)
freeze source, input, runtime, formula, and solver-binary hashes before
search. The public formulas contain no fixed leaf masks or chart outputs.

## Frozen N41 results

| Formula on identical four blocks | Public formula variables | CNF clauses | Native XOR rows | AND gates | Fully pinned chart | Four block outputs fixed | Only eight source masks fixed |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| Three target-ended S3 equations, two free middle coordinates | 34,394 | 60,236 | 14,374 | 19,714 | `SAT_MODEL_PASS`, 0.628 s | `BOUNDED_UNKNOWN`, 35.028 s | `BOUNDED_UNKNOWN`, 65.133 s |
| One target-ended S5 invariant | 48,126 | 85,359 | 19,785 | 28,117 | `SAT_MODEL`, 0.491 s; `VERIFIED_RAW_ROW` | `SAT_MODEL_PASS`, 0.552 s | `BOUNDED_UNKNOWN`, 65.128 s |

The S3 [middle-only control](middle_control/result.json) also reached
`BOUNDED_UNKNOWN` at 35.019 s. The bounded controls' saved solver logs
contain restarts and conflict search; they are censored search results,
not unsatisfiability certificates. The main one-worker control caps were
60 seconds plus a five-second process guard and 4 GiB combined RSS.
Sampled combined peak RSS was 44,253,184 bytes for S3 and 84,082,688
bytes for S5. The host was not isolated; wall times are exploratory
stage diagnostics, and the auxiliary 35-second partial controls did not
record RSS.

The S5 [fully pinned model](s5_chart/result.json) satisfies all 85,583
CNF clauses and 19,785 native-XOR rows in its formula. The
[independent checked-Sage audit](s5_chart/audit.json) reconstructs its
12 signed raw and subgroup points, checks source membership and 12
distinct folded columns, and sums them to `Q`. With only the four block
outputs pinned, the [separate control](s5_blocks_control/result.json)
returns the same verified complete assignment and selects raw target
fiber index 2. The [receipt verifier](verify.py) checks all protocol
hashes, formula checks, bound statuses, and audit links.

The fixed-mask S5 control leaves the four 41-bit block outputs and target
fiber flag free. Its [terminal result](s5_control/result.json) has no model
at the cap, even though the exact public-row chart supplies a satisfying
assignment for those masks. Because the fixed-mask control is censored,
the unpinned [public formula](s5_public.xcnf) remains at the frozen
preflight gate; it was not sent to the solver. The S3 variant's fixed-mask
control has the same bounded status.

## Next experiment and N131 gate

Use the two quadratic links behind each block to compute its output from
`a,b` and two root bits. The first link uses the low-degree product
`q=w1*w2`; the second uses the resulting pair output and `s=u3`.
Implement the generic and `q=1` branches exactly, retain the four-block
target S5 equation, and test on the same unpinned N41 public point.
Measure the full formula and solver work, failed models, memory, and
independent row replay. Only a source-bound projection of that complete
method under one worker, 600 seconds, and 4 GiB can promote the frozen
N131 public query. Rank-producing relations, factor logs, and a fresh
single-target DLP remain downstream of that gate.

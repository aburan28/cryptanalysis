# Zero-sum triple blocks on the frozen N41 public point

The four-block zero-sum-triple construction returned an unpinned,
independently replayed 12-point factor-base row on the frozen N41 public
point. It combines a 21-term quartic block eliminant with an exact
four-block group join. The successful public query took **1.389082 s** of
target-dependent wall time after **3.030657 s** of reusable index setup,
using one native worker and **172,130,304 bytes** peak self RSS. These
timings are exploratory CPU stage measurements; the host has no isolation
receipt. The method is proposal `Q20261009195000`, with `candidate_id: null`
until a complete IC pipeline is specified.

## Construction and exact geometry

For a source block, select three nonzero masks `a,b,c` with `c=a XOR b`.
The source transformation `u=H(w)` is linear over `GF(2)`, so the three
transformed coordinates satisfy `u1+u2+u3=0`. Each mask is accepted only
when the corresponding Koblitz source point is rational; here the exact
test is `Tr(1/w)=0`. Every accepted source point is projected into the
prime-order subgroup by multiplication by four. The four blocks use
Frobenius rotations `0,10,20,30` for N41 and `0,32,64,96` for the N131
transfer screen.

Let `s=u1+u2=u3`, `p=u1*u2`, `z=1/(x(R)+1)` for the raw sum `R` of a
triple, and `q=p^2+p(s+1)`. Eliminating `X` from

```text
A(X) = (q+1) X^2 + q X + s^2
B(X) = (r+1) X^2 + r X + (s+z)^2,
r    = (s^2+s)(z^2+z)
```

gives a 21-term quartic `F(s,p,z)`. Its coefficient of `z^3` is
`p*s*(s+1)*(s+p+1)`, which is nonzero for accepted, distinct,
nonexceptional leaves. [The checked Sage audit](audit.json) recomputes
the resultant independently and checks this identity on every returned
block. The eliminant is an exact necessary relation for a block; a final
point-sum check is retained when it is used for search.

| Exact source quantity | N41 W7 | N131 W18 |
| --- | ---: | ---: |
| Accepted source masks | 63 | 131,307 |
| Unordered zero-sum mask triples | 317 | 1,439,333,092 |
| Signed triple descriptor upper count per block | 2,536 | 11,514,664,736 |
| Actual four-rotation factor-base points `B` | 504 | 1,050,456 |
| Sign/Frobenius folded columns `K` | 57 | 131,068 |

The N131 triple count is the exact Walsh cubic moment of the saved W18
mask predicate, checked with a second transform implementation. The N131
`B` and `K` values are from the earlier exact four-rotation base screen;
the [geometry receipt](geometry_result.json) binds its hash. The
[independent audit](audit.json) also rechecks 256 N131 field-mask samples
against the saved predicate. No N131 triple states were enumerated.

## Frozen N41 query

The indexed join builds group sums of the first two triple blocks once,
then probes them using the public target and each admissible sum from the
remaining two blocks. It enforces 12 distinct folded columns and checks
the full group equation on every accepted hit. The [protocol](protocol.json)
binds the input point, source, binary, runtime, limits, and data hashes.
Both queries had **2,520** admissible signed triple states per block after
within-block column filtering.

| Frozen query | Left entries | Right probes until row | Reusable setup | Target-dependent online | Peak self RSS | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Constructed positive control | 5,302,400 | 46,655 | 3.190095 s | 0.074048 s | 172,015,616 B | `VERIFIED_RAW_ROW` |
| Unpinned public N41 point `(1458168294740,1672312028033)` | 5,302,400 | 717,020 | 3.030657 s | 1.389082 s | 172,130,304 B | `VERIFIED_RAW_ROW` |

The [public result](public/result.json) gives all 12 leaves, masks,
signs, rotations, and columns. Its masks in the four blocks are
`(2,100,102)`, `(26,67,89)`, `(5,58,63)`, and `(29,76,81)`; each triple
XORs to zero. [Independent checked Sage replay](audit.json) reconstructed
each raw and projected point, tested subgroup membership and source
membership, verified 12 distinct folded columns and the quartic per block,
then summed the 12 points to the public target. The [receipt verifier](verify.py)
checks frozen file hashes, timings, caps, and transfer arithmetic.

The first native producer omitted a validity check for the second mask
while constructing a triple. That version dereferenced an absent mask
index, so its two initial result records are classified `PRODUCER_FAILURE`
in the [preserved failure receipt](attempt1_failure.json). The corrected
binary checks all three masks, asserts the 317-shape census in each block,
and was separately frozen, run, and audited. Only the corrected rows appear
in the table.

## Output signature and target fiber

An [exact N41 signature screen](signature_result.json) enumerated all
2,520 admissible signed states of rotation zero. Their projected group
sums are all distinct. Their raw transformed `z` coordinates have 1,260
distinct values because negation pairs share `x`. These values have full
binary linear rank 41, and their evaluations on the 862 Boolean monomials
of degree at most two have rank 862. None lies in the original W7
half-trace fiber, and no `z^2+z` lies in the W7 source space. Thus a
universal affine or quadratic equation in this block's output `z` cannot
prune its exact N41 support. The screen used checked Sage and records its
source, input, and runtime hashes.

The [raw target-fiber certificate](target_fiber_result.json) enumerates
the four rational points `T_i` satisfying `[4]T_i=Q` for this N41 target.
It obtains them from a subgroup preimage and the rational order-four
torsion point `(1,1)`. The public row's raw sum is the point at index 2,
`(1764837441524,678134389985)`. This gives a target-conditioned endpoint
for a symbolic solver: require the sum of four raw block outputs to equal
one of the four `T_i`, while each block satisfies its quartic and its
source-mask equations. Final point replay filters any algebraic
extraneous solutions.

## N131 transfer gate and next experiment

The [exact transfer screen](transfer_result.json) counts
`11,514,664,736` signed descriptors per W18 block before column
filtering. Even using a conservative bound for all same-column triples,
there are at least `128,227,906,595,758,068,736` cross-column-admissible
two-block **descriptor pairs** under the source-to-column map of the
four-rotation base. A literal table retaining one full 17-byte group key
per pair has at least `2,179,874,412,127,887,168,512` bytes of key payload.
This is a bound on that literal descriptor-table representation; it does
not bound a deduplicated sum set or symbolic target-conditioned solver.

The quotient `M^4/r` is approximately **25.83** when the upper signed
state count `M` is substituted into a uniform independent-sum model.
It is a coverage prediction, not a measured N131 yield. A predeclared
4-GiB set of full group keys, even if queried against every right-side
descriptor, has uniform-target success probability at most
`4.9221e-11` by a union bound. This statement applies to the predeclared
table model and does not limit adaptive use of the fixed public point.

The next executable method gate is an exact **target-conditioned four-block
elimination**: keep each block as its 21-term quartic plus 18-bit source
mask equations, impose a Semaev chain ending at each of the four raw
target preimages, and propagate target constraints before expanding
Cartesian products of signed leaves. First record an unpinned N41 solve
without the 5.3-million-entry pair table, counting source-mask families
eliminated before sign expansion and independently replaying its row.
Then derive a source-bound operation and memory projection for the W18
system and require the frozen one-worker 600-second, 4-GiB N131 gate
before running the exact public query. A passing N131 relation would
advance to rank-producing relation collection, factor-base logs, and the
single-target DLP comparison defined in the repository's `AGENTS.md`.

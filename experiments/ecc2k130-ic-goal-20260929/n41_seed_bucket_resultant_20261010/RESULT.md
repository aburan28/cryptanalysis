# A target-coupled norm decides complete N41 pair-output seed buckets

An exact quadratic norm now decides whether two fixed-seed pair-output
families can satisfy the target's S3 equation before testing their Cartesian
product. On the frozen N41 public-point residual, seed buckets `(16,5)`
give one compatible x-output pair and an independently replayed eight-column
relation, while `(1,1)` give none. Direct Sage enumeration of subgroup pair
sums agrees with the generic resultant, Horner norm, and baby-step/giant-step
(BSGS) norm. This is a decomposition component with `candidate_id: null`.

For the exact N131 W14 `s=t` **raw pair-output** domains, a BSGS norm for **one** bucket
requires 407 modular polynomial products, compared with 8,255 for Horner.
This [operation-count projection](projection.json) excludes polynomial
setup, coefficient accumulation, inversion, GCD, target-dependent bucket
selection, and witness replay. It is not a measured N131 query time.

## Exact operator

Let `L_s(X)` and `R_t(Y)` have as roots the distinct subgroup pair-sum x
coordinates in two seed buckets. For a target residual x coordinate `q`,
the Koblitz summation equation is

`S3(X,Y,q) = (X+q)^2 Y^2 + q X Y + (q X)^2 + 1`.

Work in `A=GF(2^n)[X]/L_s(X)`. When `a=(X+q)^2` is a unit in `A`, put
`alpha=qX/a` and `beta=((qX)^2+1)/a`. Modulo S3, `Y^2=alpha Y+beta`.
Reduce `R_t(Y)` to `u+vY` and form

`N = u^2 + alpha*u*v + beta*v^2`.

In `A`, `Res_Y(R_t,S3) = a^deg(R_t) N`. Because `a` is a unit, the roots of
`gcd(L_s,N)` are precisely the compatible left-bucket x outputs. A
nonunit `a` requires a generic fallback; neither frozen control takes that
branch. Every algebraic hit still needs point and column replay.

The [generic producer](run.py) forms the resultant directly. The
[Horner norm](norm.py) reduces the right polynomial coefficient by
coefficient. The [BSGS norm](norm_bsgs.py) precomputes low powers of `Y`,
accumulates coefficient blocks, and evaluates them in powers of `Y^b`.
All three run under separate frozen source/input protocols.

## Frozen control and result

The field is `GF(2)[t]/(t^41+t^3+1)` on `y^2+xy=x^3+1`, with subgroup
order `549756390943`. The W6 rotations are `0,10,20,30`; actual factor
base size is `B=256` and the signed-Frobenius quotient has 26 columns.
The public point is `Q=(1458168294740,1672312028033)`. Four points of
its archived relation form a fixed prefix, leaving target-dependent
residual `(332635421840,2054854538524)`. Both final pair outputs remain
free within their selected seed buckets. This is a target-coupled two-pair
kernel control, not an unpinned full relation search.

| Seed buckets | Left/right x roots | Generic resultant + GCD | Horner norm + GCD | BSGS norm + GCD | BSGS modular products | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `(1,1)` | 16 / 16 | 1,534.810 ms | 141.494 ms | 119.418 ms | 27 | gcd degree 0 |
| `(16,5)` | 16 / 14 | 1,341.469 ms | 114.191 ms | 99.292 ms | 25 | gcd degree 1; one group row |

These are target-dependent kernel intervals after constructing the two
bucket polynomials. Complete wall, setup, memory, and root sets are in the
[generic](result.json), [Horner](norm_result.json), and [BSGS](bsgs_result.json)
receipts. Host isolation was not established, so the CPU timings are
exploratory. The [independent checked-Sage audit](audit.json) rebuilt all
pair sums, exhaustively checked the two x-output cross products, matched
both GCD root sets, and verified the positive row sums to `Q` with eight
distinct folded columns. The checked [Sage runtime](sage_runtime_info.json)
was saved before the measured runs.

The audited N131 `s=t` bucket has 4,124 distinct raw reciprocal pair outputs
per rotation. None is zero, so inversion gives 4,124 distinct raw pair-sum
x coordinates; the same S3 norm applies on each raw target-preimage branch.
This transfer changes the N41 control's subgroup-point coordinate law and
requires its own full group replay and charge for all four branches.
The BSGS count uses block width 101 and 41 blocks. Its dense baby-power
arrays require 14,161,816 bytes in packed 131-bit coefficients; object
overhead is additional. Dense block accumulation has up to 34,023,000
field-coefficient products. There are 268,402,689 unrestricted choices of
two nonzero W14 seeds, or 131,064 under an eight-offset restriction.
The next algorithmic gate is a **target-guided seed-family generator** that
keeps at least four pair blocks free. It must find an unpinned N41 public
relation without the explicit four-point index, then support a complete
N131 work and memory projection under one worker, 600 seconds, and 4 GiB
before the published degree-131 point is queried.

The first generic attempt reached receipt writing but failed on a Sage
integer that was not converted for JSON. Its [failure receipt](failure_v1.json),
[source](run_v1.py), [protocol](protocol_v1.json), and [byte-preserved partial output](partial_result_v1.json.gz)
are retained. The corrected [protocol](protocol.json) binds the successful
run.

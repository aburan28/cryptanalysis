# Full mixed-cubic rank on two distinct-column N41 pair domains

The corrected screen reaches **rank 13,599 in 13,599 declared Boolean
features** using 13,646 exact four-column-distinct pair-pair sums. This is
an exact finite witness: no nonzero equation in this feature family holds for
every valid sum of the two frozen pair domains. In particular, a cubic
equation using their six-bit seed sums and the residual subgroup
`x`-coordinate cannot supply a universal early filter for the public-target
join. The [independent checked-Sage audit](sage_audit_v2.json) reconstructs
both pair domains, replays all 13,646 accepted sums, and obtains the same
rank by eliminating columns of the transposed evaluation matrix.

## Frozen instance and feature family

The curve is `EC1N41Ckb1h7d5e80d3c4d0` over
`GF(2)[t]/(t^41+t^3+1)`, with `y²+xy=x³+1` and prime subgroup order
`549756390943`. The supplied public point is
`Q=(1458168294740,1672312028033)`. The existing four-window policy has
`B=256` actual subgroup-usable points and `K=26` folded columns; this test
uses the last two 1,956-state pair domains at rotations 20 and 30. Every
retained four-point tuple has four distinct signed/Frobenius column IDs.

The 52 input bits are the two six-bit seed-mask XORs followed by bits 1–40
of `x(U₂+U₃)`. Bit zero is omitted because these sums lie in the odd-order
subgroup and have trace-zero `x`. The feature list contains the constant,
all degree-one and degree-two squarefree monomials, and every degree-three
monomial containing at least one seed-sum bit. It contains **13,599** terms;
the coordinate-only degree-at-most-two subfamily has 821. The
[v2 protocol](protocol_v2.json) froze the family, exact source-row hashes,
column policy, deterministic extra-draw seed, one-worker limit, and
300-second/4-GiB diagnostic caps before the corrected run.

| Frozen N41 rank step | Result |
| --- | ---: |
| Saved source combinations examined | 14,702 |
| Rejected for a repeated folded column | 1,056 |
| Four-column-distinct rows evaluated | 13,646 |
| Mixed-cubic feature rank | **13,599 / 13,599** |
| Coordinate-only quadratic rank | **821 / 821** |
| Additional random draws needed | 0 |
| Producer diagnostic wall, peak RSS | 30.323 s, 78,102,528 B |
| Independent Sage group replays and transposed rank | 13,646, **13,599 / 13,599** |

The original [v1 screen](result.json) reached full rank without checking
columns across the two pair domains. Its result remains a valid rank
diagnostic for that broader domain, but it cannot certify the distinct-column
IC domain. The [corrected result](result_v2.json) preserves that distinction
and is the result used here. The [Sage audit](sage_audit_v2.json) also checks
all 128 source points and the public point against the declared prime
subgroup, compares every accepted saved sum by the exact group law, and
matches the accepted-index digest. The [runtime receipt](sage_runtime_info.json)
was saved before the Sage job. Both wall times come from an unisolated host
and are algorithmic diagnostics, not a CPU speedup claim.

## Consequence and next method gate

Any polynomial identity in the declared 13,599-dimensional family that
held for every four-column-distinct suffix sum would vanish on these
13,646 valid rows. Their full rank forces all its coefficients to zero.
This rules out this **x-only mixed-cubic universal equation family** on the
frozen N41 policy. It does not test equations involving the residual `y`
bits, degree-four terms, seed-conditioned inequalities, target-specific
precomputed support, or a nonlinear eliminant. It also does not transfer
the rank theorem automatically to N131.

The next constructive gate should incorporate `y` or a nonlinear
seed-conditioned pair-realizability rule and test whether it rejects
public-target partial states while two pair domains remain free. A literal
full `x,y` mixed-cubic family would have 48,818 features on N41, so its
sample size and rank implementation must be frozen before a run. If a
sound constraint survives, require an unpinned ordinary N41 row and a
source-bound N131 work/memory projection before charging the published
N131 target. This rank experiment is proposal `Q20261009230200`; complete
pipeline candidate and run IDs remain null.

Run `PYTHONDONTWRITEBYTECODE=1 python3 verify.py` in this directory to
check frozen source/input hashes, both receipts, the correction, and the
independent audit. New local Sage jobs must use the repository `./sage`
launcher and save `./sage --runtime-info` before execution.

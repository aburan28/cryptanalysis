# Full cubic rank of the target-derived N41 two-pair residual coordinates

**The exact target-derived two-pair residual domain has no nonconstant
Boolean polynomial constraint of degree at most three in either its
41 x-coordinate bits or its 41 phi-coordinate bits.** For each coordinate
system, 11,522 saved residuals give an invertible evaluation matrix on
all 11,522 squarefree monomials of degree at most three. An independent
M4RI implementation recomputed both full ranks, while checked Sage
verified the phi coordinates used by the certificate.

## Exact instance and rank argument

The frozen [two-pair domain](../n41_w8_two_pair_backward_20261009/RESULT.md)
contains 99,456 exact group residuals of the supplied public point
`Q=(1458168294740,1672312028033)` on
`EC1N41Ckb1h7d5e80d3c4d0`, with subgroup order `549756390943`.
Its six-block W8 fixed-sum policy uses B=960 actual usable subgroup
factor-base points and K=77 folded columns. The last two blocks have
160 signed states each; repeated-column filtering leaves 24,864
two-block state pairs per raw target preimage. The prior independent
Sage audit verified the packed table and the saved public relation.

For a coordinate word `v∈GF(2)^41`, let `E₃(v)` evaluate the constant and
every squarefree monomial of degrees one, two, and three in its bits.
The dimension is

`1 + C(41,1) + C(41,2) + C(41,3) = 11,522`.

The [producer](rank.py) applies a frozen permutation to the packed table,
constructs `E₃(x(R))` and `E₃(phi(R))` with
`phi(R)=1/(x(R)+1)`, and saves the table indices of independent rows.
It reaches full rank after 11,522 x rows and 11,527 phi rows. Each
[witness index file](x_witness.bin) contains exactly 11,522 indices;
the separate [phi witness](phi_witness.bin) has the same length. A
degree-at-most-three polynomial that vanished on the entire residual
domain would vanish on each full-rank witness matrix, forcing every
coefficient to zero. This is an exact finite-matrix statement about the
declared coordinate bits and domain.

| Frozen certificate | x coordinate | phi coordinate |
| --- | ---: | ---: |
| Feature dimension | 11,522 | 11,522 |
| Rows processed to full rank | 11,522 | 11,527 |
| Producer rank | 11,522 | 11,522 |
| Independent M4RI witness rank | 11,522 | 11,522 |

The [protocol](protocol.json) binds eight input and source files, including
the prior packed table, its audit, the row permutation, the checked
[Sage runtime](sage_runtime_info.json), and a 300-second/4-GiB cap.
The [result](result.json) hashes the derived [phi values](phi.bin) and
both row-index files. The [independent audit](audit.json) recomputed
11,617 phi values in Sage, regenerated the monomial matrices in a
separate [native implementation](native_audit.cpp), and obtained full
rank with M4RI. Its compiler command and binary/library hashes are in
the receipt. This is proposal `Q20261009182400`; the complete-pipeline
candidate and run IDs remain null.

| Producer phase | Exact wall nanoseconds |
| --- | ---: |
| Derive and serialize all phi coordinates | 5,296,273,708 |
| x witness rank | 33,749,771,334 |
| phi witness rank | 17,336,468,458 |
| Witness serialization | 2,692,375 |
| **Total structural stage** | **56,385,205,875** |

Peak producer RSS was 53,084,160 bytes. These are local structural-stage
times without a host-isolation receipt, not a CPU speed comparison or a
single-target IC online interval.

## Constraint gate

For one raw target preimage `T`, the residual set is `T-S₂`, where `S₂`
is the group-sum set of the last two pair domains. Translation by `T`
is a bijection on group points. The target-dependent table therefore
reexpresses a reusable two-pair sum index; merely moving more blocks
backward does not by itself reject forward families. The measured lack of
residual collisions and the full cubic evaluation ranks make a compact
output-only cubic equality unavailable for this W8 fixed-sum domain.

The next method should keep pair labels, seed-sum information, or multiple
still-free partial sums in its exact constraint. A concrete gate is to use
the existing rank-12 pair inverse as a theory check while the public target
constrains at least two pair domains jointly, then measure the number of
families rejected *before* enumerating their leaf states on an unpinned
N41 query. An N131 promotion still needs a source-bound whole-search
estimate within 600 seconds and 4 GiB, followed by independently replayed
ordinary relation and rank evidence.

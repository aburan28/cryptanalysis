# Affine four-seed sixteen-source geometry and a bounded public circuit

An affine four-seed family raises the exact **N131 labeled sixteen-source
tuple ceiling** from 141.832 to **8,825,247.539** per uniform subgroup
target while adding only two seed choices per pair. The pair equation remains
low degree: for source reciprocals `a,b`, seed `s=a+b`, product `p=ab`, and
pair-output reciprocal `z`, the halftrace-cubic gate is
`pz+H((s+z)²)+ε=0` with `Tr(s+z)=0`. The N41 version passes a complete
checked-Sage sixteen-point control, but its unpinned public CryptoMiniSat
query records `BOUNDED_UNKNOWN` at the 125-second parent cap. Increased
source support alone did not clear this solver gate.

The source uses `y²+xy=x³+1` over `GF(2)[t]/(t^n+t^k+...)`. At N41,
`n=41`, modulus `t^41+t³+1`, seeds `{32,33,34,35}`, eight pair rotations
`0,5,...,35`, and public point
`Q=(1458168294740,1672312028033)`. At N131, the challenge modulus is
`t^131+t^13+t²+t+1`, seeds `{212,213,214,215}`, and rotations
`0,16,...,112`. In each pair, the left six- or eighteen-bit mask has its
highest seed bit clear, the right mask is its XOR with one affine seed, and
both source masks must be rational and have distinct folded columns. All
sixteen leaves must have different folded columns. The factor-base policy is
the union of all usable masks at these eight rotations, before folding.

| Exact source property | N41 W6 | N131 W18 |
| --- | ---: | ---: |
| Valid unordered pairs for the four seeds | `10,8,8,9` | `33,191;33,002;32,776;32,937` |
| Unordered pairs per pair slot | **35** | **131,906** |
| Signed pair-state ceiling per slot | **140** | **527,624** |
| Actual usable factor-base points, B | **512** | **2,100,912** |
| Signed-Frobenius folded columns, K | **26** | **131,068** |
| Every pair of rotated source subspaces has rank | **12 of 12** | **36 of 36** |
| Labeled eight-pair tuple ceiling divided by subgroup order | **268,444.184** | **8,825,247.539** |

The [source census](support_result.json) counts every admissible mask pair
from the previously audited rational-mask tables. Full pairwise ranks of the
rotated W6 and W18 subspaces show that their nonzero reciprocal coordinates
do not overlap between windows. The **projected** B counts use the existing
exact eight-window [N41 point-geometry audit](../N41_W6_S8_DISTINCT_WINDOW_RESULT.md)
and [N131 reciprocal-collision and Sage audit](../N131_LOWPOWER_W18_M8_GEOMETRY_RESULT.md)
for these same factor-base unions; an additional projection check is needed
because disjoint raw coordinates alone do not prove disjoint cofactor-four
images. The four-seed policy restricts source pairs within those unions and
does not change the enumerated factor bases. The signed tuple
figures credit four raw sign assignments to every unordered pair and divide
the eight-slot product by the exact subgroup order. They are **support
ceilings**, before cross-slot column exclusions or possible output
collisions. The independent [audit](audit_result.json) recomputes all eight
seed counts and all 28 rotated-subspace ranks using a different pivot order
and square/reduction procedure. Relative to the prior one-seed W18 policy,
the four-seed N131 ceiling is **62,223.4 times larger**; this is a
construction ratio, not an ordinary-query yield estimate.

The [N41 circuit](circuit.py) enforces rational-mask membership, affine seed
membership, distinct folded columns, eight source-pair gates, and a balanced
seven-link group tree to one of four raw preimages of the transported public
point. A checked-Sage [control fixture](control_fixture.json), made using the
saved [runtime receipt](sage_runtime_info.json), independently reconstructs
all sixteen curve points, their pair and higher sums, and their fourfold
projected target. Its complete Boolean assignment passes all **51,790
clauses and 10,663 native-XOR rows** of the constructed formula.

| Frozen N41 public query | Result |
| --- | ---: |
| Formula | 28,916 variables; 17,135 AND gates; 53,905 clauses; 11,094 XOR rows |
| XCNF | 1,518,583 bytes; SHA-256 `eb854440edf959fb628d50f8804b98ce3a55c171143b92a64302d090f83a43f5` |
| Solver | CryptoMiniSat5, one worker, `--xor=0`, 120-second solver / 125-second parent cap |
| Public query | `BOUNDED_UNKNOWN`, **125.107 s** solver wall, **821** restart rows |
| Peak combined RSS | **133,873,664 bytes** under the 4-GiB cap |

The [protocol](protocol.json) froze source, solver, target, and caps before
the Sage control and public search. The [query receipt](query_result.json)
accounts for construction, formula writing, solver process, postprocess, and
the 1.35-ms residual against the 126.292-second parent interval. The
[formula](public.xcnf), [raw solver log](solver.stdout.txt), and [audit](audit_result.json)
bind the status and confirm active search without a terminal model line.
These CPU intervals are exploratory on an unisolated host. This variant has
`candidate_id: null` because no complete IC pipeline was measured.

The result changes the next method choice: the dense affine seed family is
available as an exact source policy, but a larger relation space did not
make the N41 Boolean public search finish within its cap. An N131 promotion
needs a target-dependent pair or block-output generator that uses the public
point to prune multiple still-free pair domains, then a source-bound
600-second/4-GiB projection and an independently replayed ordinary relation.
Once that relation stage clears, the standing goal continues through yield,
useful rank, factor logs, target scalar recovery, and same-point rho timing.

Reproduce the immutable run in a fresh directory with `python3 -B support.py`,
`python3 -B run.py freeze`, the checked repository Sage launcher on
`prepare_sage.py`, then `python3 -B run.py control`, `python3 -B run.py query`,
and `python3 -B audit.py`. Save `./sage --runtime-info` before the Sage job.

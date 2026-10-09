# Four-free-pair completion requires 249,560,561 blind d13 prefixes

For the exact N131 d13/m12 six-pair policy, a schedule that fixes two pair
outputs independently of a uniformly sampled nonidentity target needs at
least **249,560,561** complete four-free-pair probes for a 50% success chance
under the union bound. Spending all 600 seconds on those probes requires an
average of exactly `249560561/600` complete probes per second, about
**415,934.27/s**, with at most **2.404 microseconds per entire probe**.
This is a necessary work frontier for that input law, even if each completion
oracle has perfect recall and its reusable setup is free.

## Derivation and exact policy

The [frozen protocol](protocol.json) binds `EC1N131Ckb1h136f03e58c98`,
subgroup order `r=680564733841876926932320129493409985129`, six
same-rotation d13 pair blocks with leaf rotations
`[0,0,22,22,44,44,66,66,88,88,110,110]`, 4,134 valid seed codes per
unrotated position, and the earlier audited count of **8,542,911** unordered
distinct-code pair descriptors. Each descriptor permits at most four signed
leaf choices. Thus one pair block has at most

`M = 4 * C(4134,2) = 34,171,644`

group-output states. Folded-column exclusions and coincident outputs can
only reduce the support, so `M` is a conservative upper bound.

For a first prefix chosen without the target, `Q - prefix` is uniform over
at least `r-1` group values when `Q` is uniform over the nonidentity subgroup.
With `k` pair blocks free, its completion support has at most `M^k` points.
For `L` predeclared prefixes, the union bound gives

`Pr[any completion] <= min(1, L*M^k/(r-1))`.

Consequently, `L >= ceil((r-1)/(2*M^k))` is necessary before this bound
allows 50% success. The [producer](result.json) retains exact integer powers,
the target law, rational rates, and input hashes; the [independent audit](audit.json)
recomputes the arithmetic with `Fraction` and validates the frozen sources.

| Pair blocks fixed before target use | Pair blocks left for exact completion | Prefixes necessary for 50% | Necessary average full probes/s within 600 s |
| ---: | ---: | ---: | ---: |
| 1 | 5 | 8 | 0.0133 |
| 2 | 4 | 249,560,561 | 415,934.27 |
| 3 | 3 | 8,527,894,623,554,753 | 14,213,157,705,924.59 |
| 4 | 2 | 291,412,179,145,627,003,543,092 | 485,686,965,242,711,672,571.82 |

The five-free-pair row says that eight independent first-pair choices are a
necessary count under this loose support bound. It says nothing about the
cost of a five-pair completion oracle. The four-free-pair row supplies a
concrete falsifier for a blind first-two-pair scan: the full completion
operation, not merely a local pair-membership check, must fit the stated
probe rate. These are uniform-target conditional bounds; they assign no
success probability to the frozen published point or to target-adaptive
prefix generation and symbolic joint elimination.

## Exact smaller-field control and decision

The independently saved N41 census for the same-rotation W6 public point
has **3,825,936** distinct last-two-pair completion points. Its first exact
completion hit is admissible prefix **155,013**; the first eight-column row
is prefix **513,088**. The [public search](../n41_two_free_pair_compact_lookup_20261009/public_search_v2.json)
found that same row, and its [checked-Sage audit](../n41_two_free_pair_compact_lookup_20261009/sage_audit.json)
passed. These exact indexes check the smaller-field completion bookkeeping;
the N41 run rate is not used as an N131 projection.

This frontier corrects the next algorithm choice. A two-free-pair S3
completion test can validate local propagation, but on d13/m12 it cannot be
the main search after four target-independent pair choices. The next
constructive method must either generate early pair choices from the public
target or propagate the target through at least four still-free pair blocks
without enumerating their Cartesian product. An ordinary N41 gate should
record how many symbolic families the public target removes while multiple
pair leaves are unchosen. An N131 public-Q attempt then needs a source-bound
600-second/4-GiB projection for that exact mechanism and independent row
replay. This is proposal `Q20261009224800`; complete-pipeline candidate and
run IDs remain null.

The first frozen producer failed a preflight because it expected the N41
census status label `PASS` where the saved value was `COMPLETE_CENSUS`.
The [failure receipt](preflight_failure_v1.json), [first protocol](protocol_v1.json),
and [first producer source](bound_v1.py) are retained. A second successful
arithmetic receipt rounded the necessary
average rate up to a whole probe per second; that overstated the requirement.
The [correction](correction_v2.json), [second protocol](protocol_v2.json),
and [second result](result_v2.json) preserve it with the [second source](bound_v2.py)
and [auditor source](audit_v2.py). The final result uses the exact fraction
`L/600` and passed the independent audit. The [receipt verifier](verify_receipts.py)
matches every retained source and result to its protocol hash.

## Reproduction

To replay without replacing retained receipts, copy this directory to a new
sibling under the same experiment root, remove only `protocol.json`,
`result.json`, and `audit.json` from that copy, then run its `freeze.py`,
`bound.py`, and `audit.py` with `PYTHONDONTWRITEBYTECODE=1 python3` from the
repository root. The arithmetic uses only standard Python and starts no Sage
process. The checked-Sage N41 audit and exact N131 d13 geometry are frozen
input receipts whose hashes are in the protocol.

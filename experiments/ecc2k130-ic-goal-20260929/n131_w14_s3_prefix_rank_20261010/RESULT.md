# Exact S3 prefix-variation boundary for two pair outputs

An exact target-conditioned prefix test rejects **32/32** checked N41
nonpositive pair-output controls when eight low coordinate bits per output
remain free. The same exact pair-output domains have **no shared prefix** at
that width. Their first shared prefix occurs when **22** low bits remain free;
at that width, an exhaustive scan proves the S3 variation span is the full
41-bit field for **all 977 occupied prefixes in each domain**. Thus the
linear-invariant version of this two-free-pair prefix propagator cannot
reject any of the 977² prefix rectangles at the first width where a prefix
contains more than one output. An independent checked-Sage audit reconstructed
both 978-coordinate domains, their first collisions, the positive group
witness, and selected variation ranks.

This is proposal `Q20261010224500` with `candidate_id: null` and
`target_count: 0`. It tests a precise version of the target-conditioned
pair-output hypothesis on frozen controls; the complete candidate and run
identifiers remain unassigned. The N41 curve is
`EC1N41Ckb1h7d5e80d3c4d0`, with `B=256`, folded `K=26`, rotations
`0,10,20,30`, and public `Q=(1458168294740,1672312028033)`. The tested
residual `(332635421840,2054854538524)` comes from the prior public-Q
two-free-pair control. The N131 comparison uses
`EC1N131Ckb1heb5f1998f20b`, the five same-rotation W14 policy with
`B=82,200`, folded `K=8,160`, and the frozen published point's polynomial
coordinate `x=2309658012506412099988466246134815930289`.

## Exact test

On `y²+xy=x³+1`, define

`S3(a,b,t)=(ab+at+bt)²+abt+1`.

For known high prefixes `A,B`, write `a=A+u`, `b=B+v`, where `u,v` range
over polynomials of degree less than `k`. The difference
`S3(A+u,B+v,t)+S3(A,B,t)` lies in the binary span of

`((B+t)e_i)²+tB e_i`, `((A+t)e_i)²+tA e_i` for `0≤i<k`, and
`e_h²+t e_h` for `0≤h≤2k−2`, with `e_j=t_field^j` reduced in the field.
This follows by expanding `ab+t(a+b)` in characteristic two; products
`uv` span the monomials through degree `2k−2`. If the projection of
`S3(A,B,t)` outside this span is nonzero, the entire prefix rectangle is
rejected soundly. The projection is a necessary condition; it may retain
rectangles without a group-point witness. The span's rank is independent
of which representatives inside one prefix rectangle were used, because
changing a representative changes the single-side columns only by
cross-term columns.

At N41 `k=22`, the cross-term columns alone have rank 40. For each of the
977 occupied prefixes of both exact pair domains, the corresponding
single-side columns raise the rank to 41. This checks every rectangle
without building 977² S3 instances: either side already spans the field
with the common cross terms. The [exhaustive receipt](collision_rank_result.json)
records 977/977 full ranks on both domains in 9.866 seconds and under the
frozen 120-second, 4-GiB cap. The [Sage audit](sage_collision_audit.json)
independently rebuilt the two domains, checked the cross-term rank 40 and
their collision prefixes, and replayed 16 sampled full-rank prefixes.

## Frozen controls and measured boundary

The N41 rank panel uses the exact positive residual's recovered two-pair
witness plus 32 deterministic coordinate pairs from the two exact domains.
The positive witness's raw pair sums add to that residual and satisfy S3;
the [independent Sage replay](sage_audit.json) checks its four leaf points
and group sum. The N131 panel uses 16 consecutive pairs of already audited
W14 positive pair outputs against the published target x; those pairs are
rank probes, not target decompositions. Both panels use the field polynomial
bases bound in the [protocol](protocol.json).

| Field and free low bits `k` | Variation rank on frozen cases | Prefix test rejects nonpositive cases | Prefix family evidence |
| --- | --- | ---: | --- |
| N41, 4 | 15 on 33/33 | 32/32 | 978 singleton x prefixes per domain |
| N41, 8 | 31 on 33/33 | 32/32 | 978 singleton x prefixes per domain |
| N41, 10 | 38 on 6/33; 39 on 27/33 | 25/32 | 978 singleton x prefixes per domain |
| N41, 11 | 40 on 5/33; 41 on 28/33 | 2/32 | 978 singleton x prefixes per domain |
| N41, 12 | 41 on 33/33 | 0/32 | 978 singleton x prefixes per domain |
| N41, 22 | 41 for all 977 prefixes on **each** side | 0 by the linear-invariant test | First collision: one two-output prefix per domain |
| N131, 16 | 63 on 16/16 | 16/16 | Exact pair-output domain not enumerated |
| N131, 28 | 111 on 16/16 | 16/16 | Exact pair-output domain not enumerated |
| N131, 32 | 126 on 1/16; 127 on 15/16 | 14/16 | Exact pair-output domain not enumerated |
| N131, 33 | 129 on 2/16; 130 on 10/16; 131 on 4/16 | 7/16 | Exact pair-output domain not enumerated |
| N131, 34 | 131 on 16/16 | 0/16 | Exact pair-output domain not enumerated |

At N41 the first collision is exactly at `k=22` in both domains, according
to the [full prefix census](followup_result.json). At N131, 8,220 audited
source masks allow at most `2·C(8,220,2)=67,560,180` different two-leaf x
outputs under the two relative sign choices, before equal-column filtering
or output collisions. With `k=34`, a prefix fixes 97 high bits; this count
provides no guaranteed domain compression. The N131 rank screen therefore
remains a useful check for a *proposed* prefix, while the exact N41 scan
shows that this linear-invariant mechanism does not generate or compress
target-compatible two-pair families.

The primary [rank run](result.json) took 2.780 seconds and sampled
19,316,736 bytes peak RSS, including N41 domain construction and both rank
panels. These CPU timings are exploratory on an unisolated host. The checked
Sage runtime was saved [before the run](sage_runtime_info.json). Two
producer errors are retained: [v1 RSS accounting](failure_v1.json)
multiplied macOS byte-valued `ru_maxrss` by 1024, and the
[first Sage auditor](audit_failure_v1.json) encoded `a3=1` instead of
`a1=1`. Both were corrected in versioned sources; the first run result and
independent audit bind their own frozen protocols. The
[terminal verifier](verify.py) checks the source, input, result, and audit
hashes and all stated rank and collision milestones.

## Next algorithm experiment

The next target-conditioned solver should test **seed-sum buckets** rather
than coordinate-prefix buckets. For fixed seed sum `s`, the local W14
fixed-sum map gives a linearized polynomial whose roots encode source-pair
outputs. Compose two such root sets with the *target* S3 link by polynomial
remainder or modular composition, seeking a certificate that rejects an
entire `(s₁,s₂)` bucket before either pair is enumerated. Begin with the
N41 W6 positive and negative residuals, and measure both rejection per
bucket and complete failed-probe cost. The prior generic double-resultant
SAT formulas and explicit-domain S3 norm already have bounded search and
memory receipts; this proposed bucket operator must improve the actual
family-rejection boundary those methods left open. A useful N41 gate is an
ordinary eight-point row within 120 seconds and 4 GiB with exact
distinct-column replay. Any N131 promotion then needs source-bound work
and memory under 600 seconds and 4 GiB, followed by one frozen
published-point query.

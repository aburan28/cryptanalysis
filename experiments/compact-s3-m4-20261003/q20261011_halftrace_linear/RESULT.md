# Q1450: linear half-trace cuts compact-S3 field API entries on identical searches

The type-II normal-basis half-trace is a degree-dependent linear map. Q1450
precomputes the image of each basis coordinate and XORs those masks for each
S3 root query. On matched root-heavy ordinary searches, this reduces
public field-API method entries by **1.81× at N53** and **2.28× at N83**
while the SAT search path, including every final-link check, remains exact.
The query-dependent mask XORs are recorded separately. Two pinned controls
passed independent three-link S3 replay.

For `q=2m+1` and normal-basis element `gamma_i`, Frobenius acts by
`gamma_i^(2^k) = gamma_fold(2^k i mod q)`. Therefore
`HT(gamma_i) = sum_{j=0}^{(m-1)/2} gamma_fold(4^j i mod q)`.
Linearity gives the mask table for any field element. The implementation
keeps the same S3 quadratic reduction, final S3 checks, and root order as
Q1443. [validate_linear.py](validate_linear.py) compared every basis vector,
128 deterministic random elements, and 32 S3 root pairs per field at
N53, N83, and N131 against the original oracle. All passed.

## Frozen identities and work boundary

Both variants use `PDP4sat` on the same public point, exact base, CNF,
target preimage coset, `seededpos` branch seed, `satpivot` pair-root clauses,
selector target-support cap one, and eager leaf-rationality rule. No
isogeny transport is used (`isogeny: "none"`). Q1450 changes only the
half-trace oracle and is a PDP-stage proposal, with null candidate and run
IDs.

| Field | Curve / ordinary workload | Actual usable B | Folded K | Enumerated base SHA-256 |
| --- | --- | ---: | ---: | --- |
| N53 | `EC1N53Ckb1hf77aab617904` / `74f2979b3e68` | 24,062 | 227 | `05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5` |
| N83 | `EC1N83Ckb1h876c2921cb64` / `bab50a1e5f66` | 30,977,592 | 186,612 | `56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8` |

The main operation count sums public `CountedOnb` method entries during
`solver.solve`. For the new map, `linear_halftrace_basis_xors` separately
counts each XOR of a precomputed image mask into a query result. Table
construction is degree-only, done on the first half-trace call, and is
included in solver time. It takes `m(m+1)/2` coordinate-mask toggles,
which are **not** part of either query-operation count. The two event kinds
must not be combined as if they have identical cost. CPU and wall timings
on this host are exploratory.

## Root-heavy paired measurement

The [follow-up protocol](followup/protocol.json) sets the conflict limit to
62 for N53 and 63 for N83, with no API stop and a 180-second wall safety
cap. CaDiCaL reports 63 and 64 conflicts at these limits. All four runs
reached their conflict limit before the wall cap and retain
`BOUNDED_UNKNOWN` status. The baseline and linear variant have identical
search counters and sampled states after excluding arithmetic counts,
timing, and RSS.

| Field / oracle | Final-link checks | Exact target S3 matches | Field API entries | Linear basis XORs | Solver CPU s | Solver wall s | Peak RSS bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 Q1443 base | 35,286 | 0 | 5,171,666 | 0 | 102.653 | 155.440 | 123,289,600 |
| N53 Q1450 linear | 35,286 | 0 | 2,855,690 | 1,181,308 | 106.018 | 141.413 | 149,553,152 |
| N83 Q1443 base | 6,358 | 0 | 1,161,776 | 0 | 36.352 | 59.042 | 156,762,112 |
| N83 Q1450 linear | 6,358 | 0 | 509,630 | 330,480 | 35.314 | 47.021 | 162,824,192 |

The N53 method-entry reduction is 2,315,976 events, or 0.86 bits at fixed
search depth. The N83 reduction is 652,146 events, or 1.19 bits. Neither
paired CPU result establishes an isolated-host speedup; N53 CPU time is
slightly higher with the linear map, while N83 is slightly lower. The
first 60-conflict [measurement](measurements.json) reached two final-link
checks per field and showed identical paths there too. The root-heavy
[measurement](followup/measurements.json) is the representative stage
comparison.

Every ordinary attempt is charged to its point, including both variants.
Including Q1450's first and root-heavy screens, the archived same-point
SAT totals are **31,751,421** field-API entries at N53 (`2^24.92`) and
**10,625,938** at N83 (`2^23.34`). The N83 prior includes the Q1449 W≤6
policy attempt on the same public point; the N53 pair-table campaign has a
separate operation ledger. Controls are kept outside ordinary-target
charges.

## Degree-131 decision

These bounded rows establish a cheaper exact S3 root operation at the API
boundary. They do not supply a measured cost for a successful ordinary
decomposition or useful relation. The complete N131 `2^x` projection and
gap to `2^61` remain null in both receipts. The conditional W≤7 pure
pair-index model from Q1447 is still `2^85.18` **logical pair actions**,
24.18 bits above an abstract `2^61` cap in that distinct unit. A 1.19-bit
reduction in this SAT stage's API count cannot be subtracted from that
pair-index model.

The next solver change must improve target-compatible midpoint discovery or
return many distinct decompositions per successful query. The Q1450 code
provides a lower-method-entry arithmetic primitive for that search, with its exact
root equivalence checked through N131.

## Reproduce

The [protocol](protocol.json), [pre-run freeze](freeze.json), and
[follow-up freeze](followup/freeze.json) bind the source, binary, exact
CNF/maps, target files, and run order. Input CNFs and binaries reside in
`/private/tmp` and can be regenerated from their recorded sources if
removed. Run the validators on the frozen artifacts:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_halftrace_linear/validate_linear.py
python3 experiments/compact-s3-m4-20261003/q20261011_halftrace_linear/validate.py
python3 experiments/compact-s3-m4-20261003/q20261011_halftrace_linear/followup/validate.py
```

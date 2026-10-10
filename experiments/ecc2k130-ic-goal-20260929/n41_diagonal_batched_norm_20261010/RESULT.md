# One GCD filters all reciprocal diagonal-atom bucket pairs at N41

A target-dependent product of right-bucket resultants and a single
polynomial GCD found the exact positive four-atom relation in **57.607 s
online**. On the independent N41 public point, the same test completed
both admissible raw lifts in **121.786 s online** and returned degree-zero
GCDs. An independent checked-Sage census confirmed the positive group
relation and found zero public-point four-atom sums in the declared two
rotation base. This is an exact family filter: one GCD decides whether
*any* seed-sum bucket pair can meet a specified target lift.

## Algebra and support

For two diagonal atoms from one rotated additive source space `W_d`, write
their reciprocal x-coordinates as `a,b∈W_d`, their seed sum `s=a+b`, and
their product `p=ab`. For `s≠0`, the map `a↦a(a+s)` has kernel `{0,s}`;
its image `V_s` has dimension `d−1`. The reciprocal coordinate `C` of
their group sum satisfies

`g_{s,p}(C)=(1+p²)C²+pC+s²=0`.

The bucket polynomial
`F_s(C)=∏_{p∈V_s}g_{s,p}(C)` contains every usable pair-output
coordinate for seed sum `s`. At N41 W6, `|V_s|=32` and every `F_s` has
degree 64. For target reciprocal coordinate `q`, the upper S3 link is

`U(C,D,q)=(1+(Cq)²)D²+CqD+(C+q)²`.

For a right seed-sum bucket `t`, let
`R_t(C)=∏_{p∈V_t}Res_D(g_{t,p}(D),U(C,D,q))`. A common root of
`F_s` and `R_t` is an algebraic bucket-pair hit. Multiplying across all
63 nonzero sums on each side gives `F_all=∏_s F_s` of degree 4,032 and
`R_all=∏_t R_t` of degree 8,064. `gcd(F_all,R_all)` tests all bucket
pairs at once; a positive factor is localized by further GCDs and checked
against actual source points and the elliptic-curve group law. Degree zero
excludes the entire algebraic superset, including every usable four-atom
decomposition in this chart.

The [frozen algebraic protocol](protocol.json) uses `GF(2^41)` with
`t^41+t³+1`, `y²+xy=x³+1`, subgroup order `549756390943`, source W6,
rotations 20 and 30, and 64 signed atom states per rotation. Its exact
usable subgroup base has `B=128` and `K=26` folded columns. Each side
has 1,956 usable pair states, all with nonzero pair-sum x-coordinate.
The positive target is a deterministic four-atom correctness control;
the public point `(1458168294740,1672312028033)` comes from the
independent frozen N41 workload. A trace identity restricts each projected
target's four raw lifts to the two with `Tr(1/x)=0`. The positive control
uses its known raw lift; the public run tests both admissible lifts.

| N41 case | Target-dependent work | Global GCD degree by lift | Exact group hits | Peak RSS |
| --- | ---: | --- | ---: | ---: |
| Constructed four-atom control | 57.607 s | lift 2: **1** | **1** | 545,538,048 B worker |
| Independent public point | 121.786 s | lifts 0, 2: **0, 0** | **0** | 581,353,472 B monitored process tree |

The positive factor localized to left seed sum 7 and right seed sum 33;
its four atoms use distinct folded columns `[0,1,2,19]`. Reusable
source setup took 24.366 s for the positive run and 14.046 s for the
public run, outside their online intervals. The positive online interval
includes target preimages, right-resultant construction, global GCD,
localization, and producer group checking. The [positive receipt](positive_result.json)
and [public receipt](public_result.json) retain exclusive phase clocks.
The [independent checked-Sage audit](sage_audit.json) rebuilt all 128
atoms from raw source lifts, replayed the four-point positive sum and
cofactor projection, then performed an exact 1,956-by-1,956 pair-list
join on each admissible public raw lift. Its public group-hit count was
zero.

The first [double-sided implementation](../n41_diagonal_double_norm_20261010/result.json)
used a separate GCD for each seed-sum bucket pair. Under its 300-second
per-case cap it completed 368 positive and 533 public bucket-pair checks,
both `CENSORED_TIME`; the saved cases do not classify the unvisited
pairs. The batched global products made this N41 question decidable within
the cap. The public run used the frozen [corrected monitor](monitor_protocol_v2.json),
one checked-Sage worker, a 300-second online and 360-second process cap,
and a 4-GiB RSS ceiling. The first monitor failed on sandbox process-list
access after launching the positive worker; the [recovery monitor receipt](positive_attach_monitor.json)
records that it attached after startup and observed completion. Keep the
positive timing as a diagnostic on this unisolated host, with that monitor
qualification. All algebraic and group decisions are exact.

## N131 dense-product boundary

The [checked-Sage W14 audit](transfer_result.json) verified that none of
the 16,383 nonzero W14 source elements has its inverse in W14. Thus no
product `p=ab` in these source spaces equals one, so each W14 bucket
polynomial has exact degree `2^14=16,384`. Across 16,383 nonzero seed-sum
buckets, the direct dense left product has exact degree **268,419,072**.
Even an ideal 17-byte packed coefficient for each `GF(2^131)` element
would require **4,563,124,241 bytes**, exceeding the 4-GiB limit by
268,156,945 bytes before any right polynomial, scratch space, or source
table. The direct dense global-product representation therefore fails the
N131 memory gate. This is a bound on that representation; it does not rule
out a compressed or streamed family filter.

The next algorithmic step is to keep bucket products in a factored or
subspace-polynomial form while applying the target-dependent resultant,
then localize factors through a bounded product/remainder tree. An N41
implementation must preserve the positive group witness and the complete
public-point rejection before its N131 memory and operation counts are
measured. The N131 relation target still requires the full ten-atom,
five-pair upper tree and useful rank under the project measurement
contract; this four-atom gate is one exact local elimination component.

# Exact rotated four-atom inverse for the W15 six-pair source

An exact **266-term resultant** now filters a proposed four-atom output
from two same-seed pairs at *different* Frobenius rotations. Its
linearized-product-space implementation scans **16,384** first-product
values on the frozen N131 W15 source and tests the entire second-product
family by a polynomial GCD, before choosing source masks. The N131
constructed positive output yielded one algebraic product family in
**6.521525 s** query time; an independently fixed field-element control
yielded zero in **6.963566 s**. Peak process RSS was **2,359,296 B** in
both runs. Independent checked Sage verified the actual four source
points, all three reciprocal sum equations, the native product and GCD
root, and the complete native terminal receipts. These are local
inversion measurements; generating the proposed output from the frozen
N131 public target remains the joint-search gate.

## Rotated resultant and complete product-family filter

Work on `y²+xy=x³+1` over the polynomial-basis binary field. For source
coordinates `w_1,w_2` with common seed `s=w_1+w_2`, their product is
`p=w_1w_2`. After Frobenius rotation `r`, the reciprocal coordinate `c`
of their pair sum satisfies

`g_r(c)=(1+p^(2^(r+1)))c²+p^(2^r)c+s^(2^(r+1))=0`.

For two pairs with rotations `r_0,r_1`, put
`a=s^(2^r_0)`, `b=s^(2^r_1)`,
`P=p_0^(2^r_0)`, and `Q=p_1^(2^r_1)`.
If `z` is the reciprocal coordinate of their four-atom sum, the two
pair equations and the exact upper S3 equation are

```text
(1+P²)c²+Pc+a² = 0
(1+Q²)d²+Qd+b² = 0
(1+c²d²)z²+cdz+(c+d)² = 0.
```

Eliminating `c,d` produces `H(a,b,P,Q,z)`, with **266 terms** and degree
at most eight in each variable. The checked
[derivation](resultant.json) is symmetric under exchanging the two
pairs. Substituting `a=b` reproduces every coefficient of the archived
150-term equal-rotation resultant, including characteristic-two
cancellations. The [protocol](protocol.json) froze the checked Sage
runtime and source hashes before derivation.

For a nonzero seed in `W_d`, the unrotated product image
`V_s={w²+sw : w∈W_d}` is an `F₂`-linear space of dimension `d−1`.
The two rotated product domains are Frobenius images of `V_s`. For fixed
`a,b,z`, the [native implementation](native.cpp) visits each first
product `P` once, specializes `H` to degree at most eight in `Q`, and
computes its GCD with the linearized vanishing polynomial of the entire
second-product space. A degree-zero GCD rejects all second products for
that `P` without enumerating them. Every valid four-atom witness with
defined reciprocal coordinates survives; algebraic hits still require
source-point, sign, column, and group replay before relation use.

## Frozen controls and accounting

The N41 case uses `GF(2)[t]/(t^41+t³+1)`, W6, rotations `(10,15)`,
and the first constrained four-atom block of the previously verified
public-point twelve-column relation. That relation's target is
`Q=(1458168294740,1672312028033)` in the subgroup of order
`549756390943`, with six-pair source **B=384** and **K=26** folded
columns. The N131 case uses
`GF(2)[t]/(t^131+t^13+t²+t+1)`, W15, rotations `(26,39)`, and the
archived constructed twelve-column witness in the subgroup of order
`680564733841876926932320129493409985129`; its source has
**B=197,292** usable points and **K=16,381** folded columns.
In each positive control, the four-atom output `z` comes from a checked
source witness and is supplied to the inverse. The other `z=t+1` is
fixed separately as a field-element rejection control. The
[control protocol](control_protocol.json), [native protocol](native_protocol.json),
and [native Sage audit protocol](audit_protocol.json) bind the sources,
inputs, one worker, a 100-second native query cap per case, a 110-second
parent cap, and 4-GiB RSS before their respective runs.

| Input field and proposed output | First-product states | Algebraic product families | Native query | Peak RSS |
| --- | ---: | ---: | ---: | ---: |
| N41, public-row block output | 32 / 32 | 1 | 0.001149 s | 1,540,096 B |
| N41, independent field control | 32 / 32 | 0 | 0.001150 s | 1,523,712 B |
| N131, constructed block output | 16,384 / 16,384 | 1 | 6.521525 s | 2,359,296 B |
| N131, independent field control | 16,384 / 16,384 | 0 | 6.963566 s | 2,359,296 B |

The N41 [Sage control](control_result.json) also evaluated **all 1,024**
ordered product pairs for its fixed seed. Exactly the known positive
pair satisfies the resultant at the positive output; none satisfies it
at the independent control. The [native receipts](receipt_n131_positive.json)
preserve setup and query boundaries, process wall, stdout, stderr,
binary/input hashes, cap, and exit status for each case. The
[independent Sage GCD replay](native_audit.json) extracted each native
degree-one root and checked it against the corresponding second source
product and `H`; its four terminal rows match the native hit counts.
The [terminal audit](terminal_audit.json) checks all freezes, the
equal-seed specialization, full product-state counts, resource caps,
and replay results. CPU timings were taken on an unisolated host and
are stage diagnostics.

## Target-conditioned continuation

This inverse is useful if a joint solver can produce a small number of
four-atom output proposals from the public point while the remaining
blocks stay symbolic. Calling the 6.52-second scan for each of the
**32,411,856** target-independent one-pair prefixes required by the
eight-offset W15 support gate would exceed its necessary **18.512 µs**
per-prefix budget by over five orders of magnitude, even before other
stages. The next experiment should use the two rotated block resultants,
their linear product-space conditions, and the upper public-target S3
links to reject *joint* product families or derive candidate outputs
without a prefix sweep. First test an unpinned N41 public relation
without the 3,167,136-state index; promote only after a complete
source-bound N131 work/RSS projection fits one worker, 600 seconds,
and 4 GiB. This is a partial-sum proposal with `candidate_id: null`.

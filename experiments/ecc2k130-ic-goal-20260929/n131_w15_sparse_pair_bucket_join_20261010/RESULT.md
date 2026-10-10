# Exact one-sided W15 pair-bucket join on an N131 block residual

An Artin–Schreier inverse joins two W15 pair-output buckets through a supplied
block residual by enumerating **one** bucket's source products. On the frozen
N131 constructed block control, the method examined 4,144 usable source
product pairs, generated 8,288 distinct right outputs, and checked 16,576
residual-conditioned left outputs. It found exactly the recorded pair-mask
witness for the positive residual and zero bucket hits for the fixed negative
residual. The [checked-Sage run](as_result.json) took 2.131 s for setup and
both residual tests; its [bounded parent receipt](as_receipt.json) records
5.080 s including launch and 283,525,120 B sampled peak RSS, with one worker
inside the frozen 600 s and 4 GiB caps. The [independent integer-field
audit](audit_result.json) replayed the recovered masks and both pair and
upper equations.

## Exact method

The field is `GF(2)[t]/(t^131+t^13+t^2+t+1)`, the curve is
`y²+xy=x³+1`, and the source is `W15=span(t,...,t^15)`. The control uses
seed mask `s=13686`, pair rotations 26 and 39, and the ordered raw leaves
in the [frozen input](../n131_w15_joint_block_resultant_20261010/restricted_result.json).
Its four leaves are part of a previously independently replayed 12-leaf
construction. The actual source support file has 16,441 masks. Only pairs
with both masks supported and distinct recorded columns enter this join.

For a seed `s=w_a+w_b` and product `p=w_a w_b`, a pair output reciprocal
`c=1/x(P_a+P_b)` satisfies

```text
g_p(c) = c²+s²+(pc)²+pc = 0.
```

For any proposed output `c`, set `z=pc`. Then `z²+z=c²+s²`. Because 131 is
odd, half-trace solves this Artin–Schreier equation whenever it has a field
solution. The two resulting products are `p=z/c` and `p=(z+1)/c`; exact
membership in the seed's product map identifies source mask pairs. This is
an output-to-bucket inverse without factoring the degree-32,768 [sparse
bucket polynomial](../n131_w15_pair_bucket_polynomial_20261010/RESULT.md).

The implementation first enumerates one seed's supported product pairs and
solves `g_p(d)=0` for each right output `d`. For a supplied block residual
`r`, it solves the upper S3 equation as a quadratic in the left output `c`:

```text
U(c,d,r) = (1+d²r²)c² + drc + (d+r)² = 0.
```

It then applies the inverse above to `c` and checks source support and
columns. The work is linear in the number of enumerated right products and
derived outputs for one fixed seed and residual. All quadratic and
Artin–Schreier branches are checked in the field; the result is a complete
algebraic bucket intersection for that restricted source domain. A bucket
hit also needs point and subgroup replay before use as a full IC relation.

## Frozen controls and accounting

| Gate | N41 public relation | N131 constructed block |
| --- | ---: | ---: |
| Pair seed / rotations | `2` / `20,25` | `13686` / `26,39` |
| Bucket product dimension | 5 | 14 |
| Exact algorithm | quotient-ring norm | one-sided Artin–Schreier join |
| Positive intersection | degree 1, includes recorded output | 1 bucket hit, exact recorded masks |
| Fixed negative residual | degree 0 | 0 bucket hits |
| Sage stage time | 5.064 s | 2.131 s for setup and two residuals |
| Parent wall / sampled RSS | 9.518 s / 259,129,344 B | 5.080 s / 283,525,120 B |

The N131 positive hit has left masks `[5576,8382]`, right masks `[3,13685]`,
and four distinct recorded source columns. The independent bit-field audit
verified both pair products, both `g_p` equations, `U(c,d,r)=0` for the
positive residual, and `U(c,d,r)≠0` for the negative residual. The
[terminal audit](terminal_audit.json) binds source hashes, protocols,
receipts, results, and the independent replay. These timings are algorithmic
diagnostics on an unisolated host; they do not comprise the single-target
online IC interval or a matched rho comparison. The proposal retains
`candidate_id: null`.

The direct N41 Sylvester resultant reached its frozen 120 s cap; a Sage
finite-field root routine aborted in the first quotient implementation. The
N131 degree-32,768 generic polynomial extended GCD crossed the 4-GiB cap,
and an explicit-inverse version also crossed it after building a synthetic
quotient. Between those runs, a parent receipt write failed with `ENOSPC`;
its child status is unknown and its captured stdout and parent traceback are
preserved. The [receipts](n131_receipt_v3.json) and source-bound protocols
retain each distinct outcome rather than treating a censored run as a
mathematical rejection.

## Public-query gate

The [exact source census](projection_result.json) finds 135,144,958
unordered supported mask pairs with distinct columns across all nonzero W15
seeds. The measured seed `13686` contributes 4,144 of them. Scaling its
0.971 s positive-residual join time linearly by source-pair count gives an
**exploratory 31,664 s** for one residual across all seeds, before generating
the residual from four other pair blocks. This is a rate extrapolation from
an unisolated host, not a complexity bound or completed public query.

The next method step is to make the public target constrain several still-free
pair blocks before a one-sided bucket scan. A source-bound projection must
bring that full target-dependent search within one worker, 600 s, and 4 GiB
before applying it to the frozen N131 public point. The one-sided inverse
provides an exact terminal constraint and witness decoder for that design.

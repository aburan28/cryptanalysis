# Q1428: bilinear-span feasibility screen

Q1427 reduced reverse-root calls but still rejected every ordinary sparse
partner. This screen tests a cheap sound condition for a partial second
pair before adding it to another solver. It uses the exact N53 and N83
field representations and names their exact curve and factor-base records;
the synthetic inputs are not ordinary target queries.

For fixed intermediate `m`, the characteristic-two three-summand equation
is

`S3(a,b,m) = (ab + am + bm)^2 + abm + 1 = 0`.

Write the partial leaves as `a=a0+sum(u_i e_i)` and
`b=b0+sum(v_j e_j)`, with free normal-basis coordinates `u_i,v_j`.
Expansion has the exact bilinear form

`c + sum(u_i alpha_i) + sum(v_j beta_j) + sum(u_i v_j gamma_ij) = 0`,

where `c=S3(a0,b0,m)`,
`alpha_i=e_i^2(b0^2+m^2)+e_i b0 m`,
`beta_j=e_j^2(a0^2+m^2)+e_j a0 m`, and
`gamma_ij=(e_i e_j)^2+e_i e_j m`.
Every valid completion therefore requires `c` to lie in the binary span
of the coefficient vectors. If it does not, the partial assignment can be
rejected without losing a solution. Treating products `u_i v_j` as
independent makes this a relaxation, so membership in the span does not
prove that a completion exists. The test ignores the remaining weight and
curve-lift constraints, which can only remove completions.

The [protocol](protocol.json) freezes 16 deterministic synthetic samples
per degree and free-suffix size. Each sample chooses a uniform nonzero
field intermediate, then fixes up to the factor-base weight bound in the
prefix of each leaf and leaves the same suffix free on both leaves. This
mirrors Q1427's interleaved bit order but is not a sample of its SAT trail.
The exhaustive N3/N5 self-test checks the expansion and confirms that every
span rejection is sound. The result records rank and rejection counts.

## Frozen screen result

The [result](result.json) has 24 cells with 16 samples each. At N53, all
sampled spans had full rank with 16 free suffix bits per leaf; with 12 free
bits, rank was 47 of 53 and 14 of 16 constants fell outside the span. At
N83, all spans were full rank with 24 free bits; with 16 free bits, rank
was 63 of 83 and all 16 samples rejected. The small-field expansion and
soundness self-test passed.

These rejections **do not demonstrate useful early solver pruning**. The
frozen law fixes `min(w, n-k)` one bits in the prefix. At the first
rank-deficient cells it has already fixed all `w` allowed one bits on each
leaf, so the SAT cardinality clauses would force every suffix bit to zero.
An exact root check can already run at that point. The next screen must
retain an unsaturated weight budget and compare rank filtering with exact
completion enumeration on the same partial states before integration into
the four-point solver.

This is a method screen, not an `IC1` candidate or an empirical solver
measurement. Its identity is proposal `Q1428`, `candidate_id: null`, and
`isogeny: "none"`. It cannot establish ordinary relation yield, cost per
useful row, or a degree-131 complete-solve exponent.

## Reproduction

Use the checked repository Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1428_bilinear_span/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1428_bilinear_span/screen.py --self-test
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1428_bilinear_span/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1428_bilinear_span/screen.py --check
```

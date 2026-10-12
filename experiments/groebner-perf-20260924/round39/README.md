# Packed Boolean-function affine-sharing cost screen

This bounded research pilot tests a specific prerequisite for sharing affine
elimination across specializations of one polynomial query. It is not a solver,
an F4/F5 replacement, a GPU implementation, or an asymptotic result. The
accepted CPU/query paths remain unchanged.

The Python structural pilot found six four-specialization blocks whose
degree-one residual multiples share all 129 pivots. Their full equation and
multiplier identities prove inconsistency at every specialization. A native
implementation is needed to determine whether packed sharing can repay its
coefficient handling, pivot search and proof costs. Existing symbolic
elimination research, including [Polynomial XL](https://eprint.iacr.org/2021/1609),
motivates testing sharing; its globally quadratic hypotheses do not automatically
apply to these structured degree-six original ANFs.

`packed_block.cpp` represents a coefficient function by 1, 2, 4, 8 or 16 truth
bits, packing as many coefficients as possible into each 64-bit word. XOR is
addition; entry-wise AND is function multiplication. Only the all-one function
is a unit. A pivot uses a constant equation combination proved to equal that
unit; partial coefficients are never inverted. Every row operation carries
complete original-row provenance. Unresolved columns remain explicit.

The scalar control uses one truth bit per coefficient and ordinary first-pivot
search. It does not pay for the shared combination search. Each specialized
matrix has its own complete proof. This is a packed full-RREF control, not the
strongest accepted complete-query implementation: the latter can terminate
certificate production early and exploits exact branch symmetry. No result
here can promote a query or replace that comparison.

Run the correctness and operation-count screen with ordinary Python:

```sh
python3 experiments/groebner-perf-20260924/round39/validate_packed.py \
  --output /absolute/path/to/new-screen.json \
  --affine-report experiments/groebner-perf-20260924/round39/fixtures/affine-block-probe.json.gz
```

The optional affine report is the retained source-bound output of the earlier
Python diagnostic. The bundled matrices allow this matrix/proof experiment to
be repeated without loading the earlier query reports. This screen does not
rederive the original ANFs or establish new complete-query results. Omitting
the affine report still checks all synthetic controls. The driver
builds optimized and undefined-behavior-sanitized binaries on the current host,
records compiler, source and binary hashes, and refuses to overwrite a result.
It compares complete rows, pivot choices and proof matrices with the unchanged
Python reference, whose identities and specialization row spaces are checked
separately. Tests cover every two-by-two function-valued matrix on two/four
specializations, randomized matrices, packed-word boundaries, the supported
extent limits, rank changes, absent unit pivots and malformed inputs.

The counters report executed word XORs/ANDs, coefficient reads, word copies and
row-update counts. They include selector arithmetic but exclude allocation,
parsing, initial packing and proof initialization. They are diagnostics, not
instruction counts or wall time. Matrix/proof byte counts exclude selectors,
temporary rows and container overhead. No timing or memory-peak claim follows
from these fields.

Before query integration, require exact certificate/root agreement and a
qualified full-query win against the strongest existing CPU/GPU arms, including
conversion, exceptional specializations, proof reconstruction and independent
checking. Fixed-size block sharing alone supplies no asymptotic improvement.

## First physical CPU result

The [M4 Pro cost screen](results/m4-pro-cost-screen.json) passes all 66,465
matrix controls and six affine blocks in both optimized and UBSan builds.
The controls comprise 65,792 exhaustive tiny matrices, 640 randomized cases,
30 word-boundary/extent cases and three exceptional cases. Both builds also
reject all 11 malformed inputs. Complete output rows, pivots, provenance and
integer counts agree between the native builds. The six frozen blocks match
the checked Python matrices and proofs, with all 24 scalar specializations
independently checked as well.

The first design is an unfavorable operation-count result:

| Diagnostic per four-specialization block | Shared functions | Four packed scalar controls |
|---|---:|---:|
| Word XORs | 1,068,371–1,084,460 | 438,336–444,920 |
| Additional word ANDs | 743,995–756,233 | 0 |
| Coefficient reads during search/update | 71,801 | 179,677–179,815 |
| Matrix plus complete proof storage | 71,920 bytes | 79,360 bytes |

Paired XOR ratios are 2.411–2.474. The 9.375% storage reduction excludes all
temporary/selector allocation. These counts are not measured slowdowns or
peak-memory results. Even removing all coefficient-search work would leave
the current shared row-update schedule with 1.786–1.835 times the scalar word
XOR count, plus partial-function ANDs. Faster search alone therefore cannot
make this policy win on the counted row work.

Do not integrate this full-forward-proof policy into the accepted query path
on the strength of shared pivot counts. Preserve the result as a correctness
reference and cost counterexample; [next experiments](NEXT.md) prioritize a
different source of repeated affine work.

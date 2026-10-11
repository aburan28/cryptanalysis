# Result: polynomial-basis squaring

All 16 frozen cells passed exact output comparison. Ratios below are paired
median incumbent/candidate operation times. Each field cell contains 256
squares; each curve cell contains three complete 32-bit scalar calls.

| Complete measured operation | Primary range | Independent confirmation range |
| --- | ---: | ---: |
| Field-square batch | 1.46–2.66x | 1.49–2.62x |
| Point-scalar batch | 1.21–1.56x | 1.20–1.58x |

The same byte-interleaved square is applied to both local and runner field
copies. Exhaustive small-field, noncanonical-input, random wide-field, and
point-scalar exact checks passed. The improvement is relevant to Koblitz
Frobenius recoding, which calls field square repeatedly. It does not establish
an end-to-end IC or DLP speedup.

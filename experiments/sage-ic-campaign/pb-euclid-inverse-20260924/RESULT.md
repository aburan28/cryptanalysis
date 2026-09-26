# Result: polynomial-basis inverse

All twelve measured cells passed exact output comparison. The following ranges
are ratios of paired median operation times (incumbent / candidate) across
both source copies, three field degrees, and two independent input seeds per
degree. Each scalar cell times three complete point scalar calls.

| Complete measured operation | Primary range | Confirmation range |
| --- | ---: | ---: |
| 64 field inversions | 14.50–88.12x | 14.76–91.41x |
| 8 point additions | 4.86–24.46x | 5.02–25.70x |
| 3 point scalar calls | 2.63–10.90x | 2.74–12.11x |

Both local and runner copies of `Pb.inv` now use polynomial extended Euclid.
The exhaustive small-field and random wide-field tests passed. The full runner
suite passed 29 of 30 tests; the remaining test requires the absent
`ecc2k130/docs/ic/params/ecc2k130-fixed.json` fixture. That failure was
recorded and is unrelated to this arithmetic change.

The result does not establish a complete index-calculus gain. The measured
curve calls are components of a possible IC workload, while relation search,
linear algebra, target descent, and verified log recovery remain uncharged.

# Q1460: shared-prefix WDSat encoding at N53 and N83

Defining and reusing each distinct OR prefix compresses N53's width-four
encoding from 68,404 to **268 auxiliary variables**, a factor of 255.2.
Its transformed formula has 102,254 rows rather than 169,586. The N53
binary's `__DATA` segment falls from 2.636 GB to 339 MB, and the complete
full-lock control runs with a replayed assignment. N83 uses 160 auxiliary
variables in both encodings.

Each prefix variable has clauses enforcing equivalence to its constituent
OR expression; each final clause is equivalent to the original long clause
under those definitions. The original archived satisfying assignments replay
on every transformed cell, and exhaustive single-clause checks cover widths
five through ten over 14,016 full assignments. The original and transformed
XCNF bytes are independently evaluated again for every WDSat SAT output.

| Exact control | Plain WDSat | XOR-Gauss WDSat |
| --- | --- | --- |
| N53 full lock | SAT, 3.085 s, 329 MB RSS | SAT, 1.696 s, 328 MB RSS |
| N53 free midpoints | `BOUNDED_UNKNOWN`, 60 s, search started | `BOUNDED_UNKNOWN`, 60 s, search started |
| N83 full lock | SAT, 15.281 s, 1.115 GB RSS | SAT, 14.219 s, 1.310 GB RSS |
| N83 free midpoints | `BOUNDED_UNKNOWN`, 60 s, search started | `BOUNDED_UNKNOWN`, 60 s, search started |

All wall times are exploratory on an unisolated host. The full-lock cells
test formula/model correctness; the free-midpoint statuses preserve the
search cap and do not estimate ordinary relation yield. The next solver
iteration should improve free-midpoint propagation or clause handling on
these exact frozen inputs, then measure ordinary target yield at N53/N83.

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_shared_prefix/validate.py
```

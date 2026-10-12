# Q1462: conditional N131 pair-index budget with two charged query additions

The Q1447 W≤7 conditional base model becomes `2^86.18` counted pair-add
attempts when each target query is charged for both the base-pair sum and
the target-complement addition used by Q1461. That is 25.18 bits above an
abstract `2^61` pair-add reference. The earlier Q1447 `2^85.18` logical
action figure counted one probe per query; Q1462 retains its inputs and
makes the native query boundary explicit.

The conditional model has `B=118153819312`, `K=450968776`, subgroup order
`680564733841876926932320129493409985129`, and a full index of
`T_max=131 K²` states (`2^64.53`). For a fraction `f` of this table,
the optimistic successful-query count scales as
`Q(f)=K·2r/B²/f`; charged pair additions are `f T_max+2Q(f)`.

| Fraction of full index | Table states, log₂ | Pair-add attempts, log₂ | Gap above 2⁶¹ |
| ---: | ---: | ---: | ---: |
| 1 | 64.53 | **86.18** | **25.18 bits** |
| 1/2 | 63.53 | 87.18 | 26.18 bits |
| 1/4 | 62.53 | 88.18 | 27.18 bits |
| 1/16 | 60.53 | 90.18 | 29.18 bits |
| 1/256 | 56.53 | 94.18 | 33.18 bits |

The unrestricted stationary table size for this cost function is
`2^75.36`, 10.83 bits larger than the full table available in this family.
Thus decreasing table size raises cost throughout the tested range and, by
the derivative, throughout `0<T≤T_max` under this model. Applying N53's
measured 400 relation occurrences per 227 final ranks as a separate
cross-degree sensitivity would give `2^87.00` pair additions; this is not
used in the headline because N131 rank novelty is unmeasured.

The W≤7 base count is sampled and conditional. The successful-query model
assumes uniform support and optimistic rank novelty; factor-base generation,
final sparse linear algebra, and target descent are additional stages. The
fully normalized N131 solve exponent and challenge gap remain null. An exact
W≤7 base enumeration, N83 ordinary relation measurement, and an N131 method
that avoids this full pair-index cost are the next proof and measurement gates.

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n131_pair_budget/validate.py
```

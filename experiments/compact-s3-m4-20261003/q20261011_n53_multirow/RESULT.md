# Q1448: three independent ordinary N53 relation rows at a fixed query cap

Continuing Q1301's frozen N53 quotient-pair query schedule through all
1,500,000 target pair samples returned **three distinct four-point
relations** on the same ordinary public point. They occurred at query
positions **171,218**, **555,285**, and **1,042,474**. The first exactly
reproduces Q1301's archived witness. Independent full-point replay found
augmented relation-matrix rank **3** over the subgroup modulus
`r=21044858204113`; subtracting the shared public-target column leaves
**two independent homogeneous difference rows**. Each relation was a new
rank row when inserted.

The curve is `EC1N53Ckb1hf77aab617904`, workload `74f2979b3e68`,
`isogeny: "none"`, actual usable factor base B=24,062, folded K=227,
and enumerated-set SHA-256
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`.
Q1448 remains a `PDP4mitm` stage proposal with null `candidate_id` and
`run_id`.

## Work and yield on this one point

The table uses Q1301's 500,000 pair samples and seed, but retains every
descriptor at a repeated signed-Frobenius key. The query seed and 1.5-million
cap are unchanged. The rebuilt base's actual B, folded K and digest match
the archived factor-base record. The table has 457,277 distinct keys,
42,701 repeated-key descriptors and 22 identity pairs. Three query
positions matched a table key; all three candidates passed full point and
factor-base checks. Retaining duplicate-key descriptors added no further
matches in this schedule.

| Charged event or phase | Q1448 measurement |
| --- | ---: |
| Table pair-add attempts | 500,000 |
| Target query pair-add attempts | 1,500,000 |
| Target complement-add attempts | 1,499,940 |
| Verified relations / novel augmented rows | 3 / 3 |
| Conditional relation yield per query | 2.00×10⁻⁶; Wilson 95% interval 0.68–5.88×10⁻⁶ |
| Query attempts per novel row | 500,000 |
| Target-dependent query plus in-run verification | 208.52 s, or 69.51 s per novel row |
| Base setup / table build | 280.52 s / 49.08 s |
| Full cold stage | 538.12 s, or 179.37 s per novel row |
| Peak RSS | 155.98 MiB |

The interval describes hypothetical uniform-with-replacement query draws
*conditional on this table and public point*. It is not a cross-target yield
estimate. The wall times are exploratory on a host without an isolation
receipt; operation events remain the primary comparison. The phase costs
are exclusive and sum to the cold stage total. The target-dependent interval
starts after base/table preparation and excludes independent replay after
the run.

Charging the archived Q1301 attempt and this new attempt on the same point
gives **1,000,000 table pair samples** and **1,671,218 target query pair
samples** for the three distinct rows in their union. The first row was
repeated; Q1448 contributed two additional rows beyond Q1301. The earlier
SAT lane's field API entries use a different work unit and are retained in
its own cumulative ledger.

## Independent replay and method implication

[independent_replay.json](independent_replay.json) expands the archived
227 canonical projected x keys into all 24,062 signed-Frobenius base points.
It verifies each of the twelve relation points on the curve and in the
subgroup, checks base membership and all three four-point sums against the
public target, then recomputes rank using a different column orientation
from the measured runner. [validate.py](validate.py) passes source/input
hashes, the Q1301 first-hit regression, exact work counts, phase sums,
independent rank and cumulative same-point charge. The detailed work and
rate ledger is [analysis.json](analysis.json).

This sampled pair-table method returned **one relation at each matching
query position** on N53 W≤3. Q1447's conditional N131 W≤7 all-output budget
requires a successful run to average roughly 12,560 novel rows per query;
the N53 result identifies the needed change as explicit multi-relation
enumeration, not merely keeping duplicate table descriptors. It does not
transfer a solve cost from N53 W≤3 to N131 W≤7. The N83 ordinary relation
and rank gate, final matrix solve, target descent, calibrated operation
conversion, and fully charged N131 `2^x` projection remain open.

## Reproduce

This is pure Python field/curve work, so no Sage job is invoked. The sparse
checkout uses [indexcalc.py](indexcalc.py), a local exact-order adapter for
the original combination enumerator; the measured run verifies the rebuilt
factor-base digest before searching. On the frozen sources:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n53_multirow/validate.py
```

The runner refuses to overwrite the frozen input or measurement receipt.
Repetitions should use a fresh experiment directory and charge the earlier
same-point attempts separately.

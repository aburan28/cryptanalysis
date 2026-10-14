# Q1445: charged N83 quotient-pair budget screen

The native `PDP4mitm` comparator completed two enlarged searches on the
same ordinary N83 public point and exact Q1325 factor base. The 8-million
table cell performed 8 million table pair sums, 65,536 target query pair
sums, 10,878,976 signed target complements, and another 8 million table
pair sums for exact replay of Bloom positives. Its 1,180 positives were all
false. The 2-million cell also required a complete replay. The resulting
replay cost motivates [Q1446](../q20261011_bloom_screen/RESULT.md).

The field is GF(2^83), curve `EC1N83Ckb1h876c2921cb64`, one ordinary
public-point workload `bab50a1e5f66`, and `isogeny: "none"`. The exact
Q1325 base has B=30,977,592 usable subgroup points before folding, K=186,612
signed-Frobenius columns, and enumerated-set SHA-256
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
`Q1445` is a PDP-stage proposal with `candidate_id: null` and `run_id: null`.

## Frozen cells and results

Both cells use the Q1400 native comparator and exact first-position
table/query schedule, 20 Bloom bits per key, 10 hashes, one worker, and a
180-second external wall cap. The executable, generated field header, input
base, Sage runtime receipt, public target, and source digests were frozen
before timing in [freeze.json](freeze.json). The native self-tests cover
field arithmetic, group addition, signed-x complements, and the target.

| Table descriptors | Query representatives | Lifted signed complements | Bloom positives | Exact hits | Table replay pair sums | Native build / query / replay seconds | Process wall seconds | Peak RSS |
| ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 2,000,000 | 65,536 | 10,878,976 | 1,119, all false | 0 | 2,000,000 | 12.96 / 19.90 / 7.63 | 47.02 | 1,189 MiB |
| 8,000,000 | 65,536 | 10,878,976 | 1,180, all false | 0 | 8,000,000 | 37.67 / 22.31 / 18.31 | 83.71 | 1,203 MiB |

Each row finished with `no_exact_hit_at_cap`. The process times are
exploratory because the host has no auditable CPU isolation receipt. All
charged event counts, phase times, raw native output, and source identities
are in [measurements.json](measurements.json). [validate.py](validate.py)
passes the frozen identity, raw-output, operation-count, and status checks.

Under an **independent uniform quotient-key model**, the subgroup has order
2,417,851,639,230,796,216,685,689 and about `r/(2*83)` signed-Frobenius
keys. The 8-million cell's expected exact-key matches are
`8,000,000 * 10,878,976 / (r/166) = 5.98e-9`; the 2-million cell's are
`1.49e-9`. These are model predictions, not measured natural relation rates.
They explain why further small enlargements of this pair-table schedule are
unlikely to yield a natural relation at N83. A balanced table/query schedule
would need roughly 2.41e11 table-plus-lifted-query key events for one
expected match under the same model, before exact replay or the rest of IC.

The N131 Q1416 exact-base pure-index model remains about `2^89.36`
logical pair actions for its specified full-rank relation goal, or 28.36
bits above the abstract `2^61` action cap. Q1445 has not measured an N131
solve exponent: its complete-solve work and challenge-gap fields remain null.

## Reproduce

The checked Sage runtime receipt was saved before the base export. On the
frozen commit, rebuild the native comparator from its tracked source blobs,
then regenerate the native base:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_pair_budget_screen/build.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/export_q1400_pair_inputs.py --base-output /private/tmp/q1445build/n83_q1325_pair_base.bin --check
python3 experiments/compact-s3-m4-20261003/q20261011_pair_budget_screen/run.py --freeze
python3 experiments/compact-s3-m4-20261003/q20261011_pair_budget_screen/run.py --run
python3 experiments/compact-s3-m4-20261003/q20261011_pair_budget_screen/validate.py
```

The frozen runner refuses to overwrite either its freeze or measurement
receipt; use a new directory for a repetition.

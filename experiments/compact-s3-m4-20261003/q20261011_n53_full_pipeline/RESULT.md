# Q1457: full-rank N53 quotient-pair relation setup

The complete signed-Frobenius quotient-pair index produced a rank-227
generator relation system on the exact N53 weight-three factor base. Modular
Gaussian elimination recovered all 227 folded-column logarithms, and each
logarithm independently replayed against the subgroup generator. This supplies
the reusable preparation for the fresh-target Q1461 run.

The curve is `EC1N53Ckb1hf77aab617904`, with subgroup order
`21044858204113`, actual usable base size `B=24062`, and 227 folded columns.
The base digest is
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`.
There is no isogeny transport. The fixed setup target is the generator with
known logarithm one; the 30,000,000 query pairs use seed `530931` and the
complete 2,743,068-state quotient table.

| Frozen query cap | Verified relation occurrences | Distinct rows | Rank / 227 |
| ---: | ---: | ---: | ---: |
| 5,000,000 | 57 | 56 | 56 |
| 10,000,000 | 121 | 115 | 115 |
| 15,000,000 | 185 | 165 | 165 |
| 20,000,000 | 261 | 217 | 217 |
| 25,000,000 | 332 | 260 | 224 |
| 30,000,000 | 400 | 306 | **227** |

The native run charged 62,741,802 pair-add attempts (`2^25.903`), including
the table and all queries. Its target-independent table build took 35.182 s;
generator queries took 1,574.300 s. Peak native RSS was 464.3 MiB. These
wall times are exploratory because this host has no isolation receipt.
Independent replay spent 0.383 s on final relation linear algebra and
0.308 s replaying the 227 solved logs. Input preparation and query-file
generation have separate receipts where available; this table does not
present a complete cold-start total.

The protocol, input and source freeze, native output, independent replay, and
validator are in this directory. Reproduce the archive check with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n53_full_pipeline/validate.py
```

Q1461 tests the next pipeline stage on a previously unseen public point.

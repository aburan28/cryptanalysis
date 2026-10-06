# Exact W24/m6 materialized MITM capacity screen

This is a retrospective, deterministic arithmetic audit of an already
frozen factor-base input, not a preregistered solver or timing experiment.

**Decision:** do not build a full raw-point pair table for a 2+4 join or a
full raw-point triple table for a 3+3 join under the frozen 4-GiB envelope.
The four `Q1420` policies have the same actual usable `B=16,772,828` points
before sign folding. An exhaustive half enumerator that visits distinct
unordered input points has `140,663,871,172,378` pairs or
`786,443,545,220,237,400,076` triples. Allowing repeated points increases
those counts to `140,663,887,945,206` and
`786,443,826,547,996,517,660`. These are **input-tuple counts**, not
distinct elliptic-curve sums, relation counts, or a measured PDP cost.

| Explicit half index | Distinct-input tuples | Hypothetical one bit per tuple | Multiple of 4 GiB, rounded up |
| --- | ---: | ---: | ---: |
| Pair side of 2+4 | 140,663,871,172,378 | 17,582,983,896,548 bytes | 4,094× |
| Triple side of 3+3 | 786,443,545,220,237,400,076 | 98,305,443,152,529,675,010 bytes | 22,888,519,604× |

One bit per addressable raw tuple is far less than a point key and witness
indices. It is used only to show that a literal full tuple table is outside
this resource envelope. The calculation does **not** lower-bound a table of
deduplicated group sums, a sharded or streaming method, an early-stopping
query, or an implicit algebraic solver. Gray-code enumeration can reduce
arithmetic per visited tuple but does not reduce the cardinality of a **full**
tuple enumeration. FES, crossbred, F4/F5, SAT, and target-adaptive joins have
different state spaces and remain open.

The [machine-readable result](result.json) is derived only from the
[equal-size W24 input gate](../ecc2k130-263-equal-w24-workload-20261005/RESULT.md):
its hash-pinned configuration, exact source/native `B`, sign-only column
count, four policy labels, 4-GiB cap, and one-target workload ID
`eee7f6ee5f6b`. The script recomputes that workload ID from canonical JSON.
An independent product-formula check of all four binomial counts passed.
Reproduce without Sage or solver binaries:

```sh
python3 experiments/ecc2k130-263-w24-mitm-capacity-20261005/capacity.py \
  --out /tmp/ecc2k130-w24-mitm-capacity-replay.json
cmp /tmp/ecc2k130-w24-mitm-capacity-replay.json \
  experiments/ecc2k130-263-w24-mitm-capacity-20261005/result.json
```

This removes only full materialized raw-tuple MITM from the next W24/m6
implementation shortlist. The next experiment still must freeze ordinary
query inputs and bounded *implicit* PDP policies on source and native W24,
then measure every success, miss, timeout, verified relation, and novel-rank
increment. Source/transported and native/pullback remain exact group-sum
pairs under the verified degree-263 route, with map costs charged separately.
No `IC1` candidate, natural relation yield, target DLP, rho comparison, or
ECC2K-130 speedup is established here; their measurement fields remain null.

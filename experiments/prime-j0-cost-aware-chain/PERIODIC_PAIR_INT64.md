# Bounded 64-bit periodic pair recoder

## Change and exact bound

The [periodic pair atlas](PERIODIC_PAIR_NATIVE_PROTOCOL.md) saved modeled
group operations but charged a second complete recoding pass online. On
the unisolated Mac, seven of eight raw candidate intervals were longer.
This implementation keeps the exact policy, gate, pair words, and point
table while executing the bounded recoder state in signed 64-bit arithmetic.
The wider lattice reduction and the existing canonical fallback remain in
128-bit arithmetic. In particular, the `% 3`, `% 9`, and `% 27` operations
inside the bounded state machine no longer require 128-bit division.

The 727 legal pair contributions have maximum Eisenstein lattice norm
`N(d)=d_a²+3d_a d_b+3d_b²=532`; the [differential
checker](check_periodic_int64_design.py) recomputes this maximum from the
catalog. Multiplication by `τ²` multiplies `N` by nine. Each exact quotient
therefore satisfies

`sqrt(N(s_next)) ≤ (sqrt(N(s)) + sqrt(532))/3`.

The 64-bit path is entered only when the reduced coordinates obey
`|a|,|b|<2^55`. Thus `sqrt(N(s_initial))<sqrt(7)·2^55`, and the recurrence
keeps that bound at every completed step. The quadratic form gives
`|a|≤2 sqrt(N)` and `|b|≤2 sqrt(N/3)`, hence `|a|<2^58` and `|b|<2^57`.
The largest temporary sum in the canonical step or quotient remains below
`2^59`, inside signed 64-bit range. This argument covers all legal pair
words and all scalar inputs entering the bounded path, rather than only the
sampled scalars. Inputs outside its guard take the unchanged wide path.

## Old-design differential control

The [raw 32-run receipt](periodic-pair-int64-design.json) compares both
arms on the 1,024 old design scalars. All **2,048** emitted word streams
match the frozen [earlier Python/native word
artifact](periodic-pair-native-design-words.csv) exactly. Triple/add
counts, atlas lookups, gate acceptances, output digests, and generic replay
also match. The direct curve test passed 2,293,207 checks. Fourteen CTests
passed in the sandbox; the coordinator loopback test passed separately with
socket access. This is a correctness result on reused design data, not a
new operation saving or CPU timing result.

To reproduce the differential check with the same 64-scalar benchmark build:

```sh
cmake --build build-cost-aware --target ca_tau_chain_bench test_curve -j 4
cc -O3 -std=c11 -DSCALARS=64 -Iinclude -Isrc \
  experiments/prime-j0-cost-aware-chain/bench.c \
  build-cost-aware/libcryptanalysis.a -lm -lpthread \
  -o build-cost-aware/ca_tau_chain_design64
python3 experiments/prime-j0-cost-aware-chain/check_periodic_int64_design.py \
  --bench build-cost-aware/ca_tau_chain_design64
```

## Prospective CPU question

The next panel must compare the previous 128-bit recoder at commit
`1ecc8f46610c697cba950e2c19bc0274abf66f34` against this 64-bit
recoder after its code commit, using identical compilation and table setup.
Freeze **new** disjoint scalar files before running either arm. Use the
existing SplitMix64 rejection law with seed `0xC264D2C19474AB67`, 4,096
public scalars for each of `P`, `37P`, `101P`, and `103P` on each curve, and
reject every scalar appearing in the earlier periodic fixture and its
listed predecessor fixtures. Commit and publish
[`make_periodic_int64_inputs.py`](make_periodic_int64_inputs.py) and its
[read-only verifier](check_periodic_int64_inputs.py) before generating
the new files. Commit the fixture and its generic-reference output digests
before running either candidate arm. Both arms must emit identical words, outputs,
and operation counts. Charge recoding, group operations, conversion, and
storage from first scalar reduction through last affine output; record
point-table setup separately. Preserve every raw failure.

A controlled CPU conclusion needs at least five paired AB/BA repetitions
per case, one job at a time, with a valid host-level isolation receipt under
[the isolated benchmark contract](../../docs/ISOLATED_BENCHMARKS.md).
Local runs may check correctness but cannot promote a wall-time result.
The fixed-base repeated-point workload does not establish a one-target rho
or index-calculus speedup. The arithmetic optimization itself is not an
academic novelty claim.

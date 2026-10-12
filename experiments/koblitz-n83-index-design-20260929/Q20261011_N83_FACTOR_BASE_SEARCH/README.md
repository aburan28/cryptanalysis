# Q20261011: N83 affine W₁₁ factor-base search

The affine coset `gamma_82 + W_11` gives **1,096 signed-Frobenius columns and
181,936 usable subgroup points** on `EC1N83Ckb1h876c2921cb64`. The original
`W_11` base has 1,016 columns and 168,656 points. This is an exact gain of
80 columns and 13,280 points. Independent Sage replay enumerated all 2,048
seed x-coordinates in each base, matched the complete canonical key files,
and checked every projected point against the prime-order subgroup.

## Search space and objective

Let `W_11 = span_F2(gamma_1,...,gamma_11)` in the frozen type-II normal basis
of `GF(2^83)`. For each seed x, lift on `y² + xy = x³ + 1`, multiply by four,
discard the identity, and close under sign and Frobenius. Every retained
column contains 166 distinct subgroup points. The exact geometry objective
is the number `K` of distinct signed-Frobenius columns at fixed 2,048 seed
coordinates and eleven free x-bits.

The [frozen protocol](protocol.json) scans `W_11` and all 72 cosets
`gamma_(j+1) + W_11` for `j=11,...,82`. A second deterministic screen toggles
each of those 72 high coordinate bits from the first winner. The two screens
evaluate 144 distinct affine cosets. The second screen's best neighbor has
`K=1,094`; thus `gamma_82 + W_11` is locally maximal under one high-bit
toggle within this family. The result establishes the maximum of the
preregistered 73-base panel and this discrete local condition. Other affine
shifts, subspace shapes, and factor-base policies remain outside this search.

| Exact base geometry or calculated support | `W_11` | `gamma_82 + W_11` |
| --- | ---: | ---: |
| Seed x-coordinates | 2,048 | 2,048 |
| Valid lifts | 1,036 | 1,097 |
| Repeated projected orbit seeds | 20 | 1 |
| Folded columns `K` | 1,016 | **1,096** |
| Usable points `B=166K` | 168,656 | **181,936** |
| `C(B,5)/r`, uniform-target subset first moment | 0.470297 | **0.687003** |
| Five-subset first-moment ratio to `W_11` | 1 | **1.46078** |
| `83K²` pair-root states | 85,677,248 | 99,700,928 |
| Packed descriptor payload upper model | 2,741,671,936 B | 3,190,429,696 B |

The first moment is an exact combinatorial expectation for a uniform target:
each distinct five-point subset sums to one subgroup element. It does not
measure decomposition search success, dependence among subsets, relation
rank, or target coverage. The descriptor bytes use the existing two-record,
16-byte-per-record packed-index design and are a storage model; the full
index for this base has not been built. The ratio of first moments per modeled
pair-root state is 1.25531, which is a geometric comparison rather than a
timed PDP result. Different base sets need their own immutable candidate
records once the full pipeline is specified.

## Reproduction and evidence

All new local Sage jobs use the repository's checked launcher. The verified
[`sage --runtime-info` receipt](runs/one_bit_cosets_20261011/sage_runtime_info.json)
was saved before the measured enumeration. From the repository root:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/koblitz-n83-index-design-20260929/Q20261011_N83_FACTOR_BASE_SEARCH/sweep.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/koblitz-n83-index-design-20260929/Q20261011_N83_FACTOR_BASE_SEARCH/verify_sage.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/koblitz-n83-index-design-20260929/Q20261011_N83_FACTOR_BASE_SEARCH/improve.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/koblitz-n83-index-design-20260929/Q20261011_N83_FACTOR_BASE_SEARCH/verify_sage.py --improved
```

The [73-row sweep](runs/one_bit_cosets_20261011/sweep.json),
[71-new-offset local screen](runs/one_bit_cosets_20261011/improve.json), and
[independent Sage replay](runs/one_bit_cosets_20261011/independent_sage_replay.json)
retain exact counts, source hashes, complete candidate rows, the winning
21-byte canonical key file, and every failed/duplicate lift count. The winner
key digest is
`a736ddd023020d78f1e8809c938fc4c834df5269e6bcc3da37faa820b14f7bec`.
Both Sage replays report `PASS`. The first sweep spent 99.260 s in its 73
candidate enumeration calls; the local screen spent 37.231 s including
re-enumeration and serialization. These CPU timings are exploratory; the
exact counts and hashes are the transferable result.

The next N83 gate is a frozen common-root or five-summand PDP on this exact
key set, with an ordinary target query, verified relation rows and matrix
rank, then one-target online timing paired with rho on the same point. The
candidate ID and all complete-pipeline timing fields stay null until those
stages are measured.

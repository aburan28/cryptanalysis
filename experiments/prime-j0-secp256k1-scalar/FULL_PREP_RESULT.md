# Single-use variable-base width-four preparation

The source and protocol were frozen in `3daf08fe` before deriving 32
fresh base/scalar pairs. Each base was used for one scalar only. The
checked Sage launcher reported `status: verified`, Sage `10.10.rc0`,
accepted runtime manifest SHA-256
`0a27ddfece04798b893c0feef292caab7f30ce68440f4d18092fe6358ef5499a`,
and runtime receipt SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.
The fresh input digest is
`b197077642b53b7e33ddc1eb69f6a883c888f8c654b974e358698db97c84f89c`.
Raw inputs, source hashes, all prepared-point digests, and per-case
operation counts are in `full-prep-result.json`.

For every base, an explicit Jacobian chain built all nine width-four
coefficient points. One batch inversion converted the eight new points
to affine form; each was compared with both its original Jacobian
point and a separate Sage group expression. The resulting unit-orbit
table drove the scalar evaluator. All **32 final outputs** matched
Sage's independent `kP`.

| Per fresh base and scalar, generic-path model | Count |
| --- | ---: |
| Jacobian seed-point chain | `48M + 35S` |
| Batch normalize eight points | `45M + 8S + 1I` |
| Prepare nine unit orbits | `9M` |
| **Preparation** | **`102M + 43S + 1I`** |
| Mean online evaluator | `1,192.906 M+S` under `S=M` |
| Mean preparation plus evaluator | **`1,337.906 M+S + 1I`** |
| Range of preparation plus evaluator | `1,303–1,370 M+S + 1I` |

The total over 32 one-use cases was 42,813 `M+S` units plus 32
inversions. The mean width-four weight was 36.53 digits. This closes
the earlier hidden seed-point and normalization operation counts for
this explicit source path. **Inversion remains a separate operation**;
the result does not assign it an arbitrary conversion to
multiplications. The chain is also not the special shared `2P`/`ρP`
preparation formula in [Xu et al.](https://eprint.iacr.org/2024/1906).

These are source-level generic-path counts, not measured native field
operations or CPU times. Scalar reduction, recoding, digit-table
lookup, exceptional paths, cache traffic, allocation, and program
overhead are excluded. The run sets `cpu_speedup_claim: null` and
establishes no academic novelty. A full implementation comparison
must charge those missing costs and calibrate inversion on the target
field backend under the host-isolation gate.

The explicit path makes the next design decision testable: keep seed
points projective and pay more per addition, or batch-normalize all or
a selected subset according to that scalar's digit frequencies. This
choice can be evaluated with one inversion kept symbolic before a
native backend settles its actual price.

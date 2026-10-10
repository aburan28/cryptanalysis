# W24 Frobenius-intersection certificate and independent audit gate

An integer-field derivation and an independent checked-Sage matrix replay
agree that the polynomial W24 subspace has at most **five** members in any
direct Frobenius orbit. Under the verified source-curve reciprocal rule, a
signed orbit therefore contains at most ten W24 signed classes. This proves
an 838,642-column floor for the frozen 8,386,414-class source prefix and
its exact degree-263 transport. The earlier
[selected-prefix audit](../ecc2k130-equal-w24-orbit-columns-20261005/RESULT.md)
already measured the much stronger exact potential quotient of
**8,384,348 columns**; this certificate is an independent structural check,
not a new column-count decision. The selected stream was not enumerated by
this preflight, and relation rank and charged PDP cost are separate stages.

| Exact field calculation | Integer preflight | Checked Sage replay |
| --- | ---: | ---: |
| Traces of `t^1` through `t^24` | all zero | all zero |
| `dim(W24 ∩ Frob^k(W24))`, `k=±1,±2,±3,±4` | 12, 6, 4, 1 | 12, 6, 4, 1 |
| Other nonidentity powers with nonzero intersection | 0 | 0 |
| Distinct nonzero masks with any direct overlap | 8,143 | 8,143 |
| Direct occupancy histogram among those masks, sizes 2/3/4/5 | 7,968 / 150 / 20 / 5 | 7,968 / 150 / 20 / 5 |
| Maximum direct / signed occupancy | 5 / at most 10 | 5 / at most 10 |

For the field `GF(2^131)` defined by `t^131+t^13+t^2+t+1`, all 24 basis
traces vanish, so `W24=span(t,...,t^24)`. Each calculation forms the
130 nonidentity Frobenius images of this space and computes their binary
intersection kernels. It enumerates the union of eight nonzero kernels and
counts all 131 conjugates of every resulting mask. The integer path uses
bit-polynomial arithmetic and a prime-degree irreducibility check; the Sage
path constructs its own finite field and uses Sage matrix kernels. The
signed-orbit bound follows because its members are drawn from the direct
orbits of `w` and `1/w`; it does not assume either orbit is wholly selected.

The [configuration](CONFIG.json) pins proposal `Q1420`, curve IDs
`EC1N131Ckb1h136f03e58c98` and `EC1N131Cbinh833014327b07`, route
`IW1E263d1hadee4e69fa3d`, source archive hash
`c57b565635dd81dd9c4a0b78a92a725b488a242a98b31dfd1a47058519c1288c`,
selected stream hash
`1372e1938950a4b6e6d2003732ac04102b8f794606669eeffcc5918360484aeb`,
and the equal-size workload parent. The exploratory integer run was made
before this protocol and is labeled as such in the
[protocol](PROTOCOL.md); its [raw receipt](preflight.json) verifies the
compressed archive and parent-config hashes but does **not** read the
selected stream. The [Sage replay receipt](preflight-sage-verification.json)
matches all field quantities and binds its [runtime](runtime-info-sage.json)
and verifier hashes. The integer and Sage runs took 14.991 and 137.897
seconds, peaking at 27,590,656 and 263,569,408 bytes on an unisolated
local host. These are reproducibility costs for the preflight, not online IC
timings or controlled speed comparisons.

The published source count used two complete native backends for its zero
reciprocal-overlap channel, while its independent verifier reconstructed the
direct channel. The [frozen next gate](PROTOCOL.md) is a separate full
enumerator for reciprocal overlaps and the selected signed partition, with
raw failures and a 1,800-second, 4-GiB cap. Its result fields remain `null`
until it reads and hashes the selected archive and independently matches or
corrects the published 8,384,348 count. The more consequential algorithmic
test remains an implicit orbit-closed W24/m5 PDP against the frozen W28/m5
and W24/m6 ordinary queries, including verified novel rank per charged
query. Proposal `Q1420` still has `candidate_id: null`.

Reproduce the preflight from the repository root with fresh output paths:

```sh
python3 experiments/ecc2k130-w24-orbit-occupancy-20261009/preflight.py \
  --out /tmp/w24-orbit-integer-replay.json
/Volumes/SSD990/cryptanalysis/sage --runtime-info \
  > /tmp/w24-orbit-sage-runtime-replay.json
/Volumes/SSD990/cryptanalysis/sage -python \
  experiments/ecc2k130-w24-orbit-occupancy-20261009/verify_preflight_sage.py \
  --runtime-info /tmp/w24-orbit-sage-runtime-replay.json \
  --out /tmp/w24-orbit-sage-replay.json
```

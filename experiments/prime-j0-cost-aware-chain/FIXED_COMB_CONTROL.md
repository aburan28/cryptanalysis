# Fixed-base comb control for the prepared-scalar study

## Why this control is necessary

The prepared-scalar panels reuse one point for 4,096 public scalar inputs. A
conventional fixed-base binary comb is therefore an essential comparator for
the tau recoders. The method is established prior art: the
[fixed-base comb description in Hedabou, Pinel, and Bénéteau, Section 4.1](https://eprint.iacr.org/2004/342.pdf)
attributes the underlying technique to Lim and Lee. This implementation is a
control, not an academic-novelty claim.

The width is fixed at nine before examining this panel. Let
`d = ceil(bitlength(r-1)/9)`. Prepare `B_j = [2^(jd)]P` for `0 <= j < 9` and
the 512 subset sums `T[m] = sum_j bit_j(m) B_j`, including identity. For each
column `i = d-1,...,0`, double the accumulator and add
`T[sum_j bit_(jd+i)(k) 2^j]` when nonzero. Scalar reduction modulo `r` and
affine output conversion are inside the online interval. Preparation uses
Jacobian additions and doublings followed by one batch inversion; online
addition uses the existing mixed Jacobian/affine formula.

The mode is `fixed-comb9`. Its point table has 512 slots and 16,384 bytes;
the precomputation object is 16,400 bytes. It uses 16,600 bytes of temporary
stack during preparation, no temporary heap, and no static action map. For
the 25-bit subgroup it prepares with 24 doublings, 502 additions, and one
inversion; for the 56-bit subgroup it uses 56 doublings, 502 additions, and
one inversion. The point must belong to the declared subgroup. This is a
variable-time public-scalar research implementation, not a secret-scalar API.

## Frozen-input result

The runner replays the eight input files already frozen for the full-digit
mixed-radix comparison, which had never been generated from this control.
Each file has 4,096 scalars and is checked by SHA-256. Each output is compared
to the frozen generic-reference digest, and the bench independently replays
every scalar using `ca_group_mul`. The read-only audit checks all raw arm
records. The operation score is the study's frozen model:
`10*triples + 6*tau_steps + 8*doubles + 16*adds + rotations`.

| Curve | Full-digit mixed, four points | Binary comb, four points | Positional tau, four points | Comb saving vs mixed |
| --- | ---: | ---: | ---: | ---: |
| glv-j0-32 | 1,606,004 | 1,044,488 | 1,039,526 | 34.96% |
| j0-56 | 4,368,244 | 2,612,944 | 2,232,260 | 40.18% |

All 16 new comb and positional arms verify. Comb beats full-digit mixed on
every case under this model. The previously existing positional tau table
beats comb under the same score: by 0.48% on the smaller curve and 14.57% on
the larger curve. It uses a larger precomputation object (37,968 bytes,
including 36,864 bytes of positional affine points) and 36,864 bytes of
temporary heap during preparation. The mixed-radix variant prepares 726
points (23,232 bytes) and requires 99,853 bytes of selected static maps.
These are distinct memory and preparation tradeoffs; an operation score does
not establish the CPU ordering.

The local Mac timings in the [raw panel](fixed-comb9-panel.json) are
exploratory. There is no host-level isolation receipt, so CPU speedup is
unknown. These repeated fixed-point workloads do not establish a one-target
Pollard-rho speedup. The result redirects the search toward reducing the
size and preparation cost of the positional tau table while retaining its
low online operation count.

## Reproduce

```sh
cmake -S . -B build-comb-control -DCMAKE_BUILD_TYPE=Release -DCA_WERROR=ON -DCA_BUILD_TAU_CHAIN_BENCH=ON
cmake --build build-comb-control --target test_curve ca_tau_chain_bench -j 4
build-comb-control/test_curve
python3 experiments/prime-j0-cost-aware-chain/check_fixed_comb_panel.py --bench build-comb-control/ca_tau_chain_bench
python3 experiments/prime-j0-cost-aware-chain/audit_fixed_comb_panel.py
```

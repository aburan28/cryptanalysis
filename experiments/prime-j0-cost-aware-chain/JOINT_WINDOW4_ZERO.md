# Congruence-directed zero-window GLV representative

The [packed joint Eisenstein table](JOINT_WINDOW4_XPLANE.md) uses one mixed
point addition for each nonzero balanced radix-16 joint digit. Its usual GLV
reduction picks the minimum-`L1` representative from 25 lattice neighbors.
That shortest representative need not have the sparsest digit string. This
experiment solves one small congruence to find a *different representative of
the same scalar* whose lowest joint digit is exactly zero. It then recodes
that single candidate and uses it only when it fits the existing table and
has fewer nonzero windows. No point slots or static maps are added.

Write the GLV kernel basis as `v1=(a,c)`, `v2=(b,d)` with determinant
`D=ad−bc=±r`. An equivalent representative has
`x=k−ua−vb`, `y=−uc−vd`. Because the subgroup order `r` is odd, `D` is
invertible modulo 16. Solving `x≡y≡0 (mod 16)` gives

```text
u ≡ k d D⁻¹ (mod 16)
v ≡ −k c D⁻¹ (mod 16).
```

The evaluator chooses each residue's nearest signed offset in `[-8,7]`
relative to its Babai-rounded quotient. It recodes this one directed
candidate and compares its mixed-addition count with the established
minimum-`L1` candidate. If the directed candidate exceeds four or seven
prepared positions, it is rejected. The ordinary checked generic fallback
still handles any scalar not covered by either representative. The scheme is
variable-time and intended only for public scalars.

The [producer](make_joint_window4_zero_design.py) screened the previous
packed-plane fixture, then committed the exact congruence and selection rule
with the [new-input generator](make_joint_window4_zero_inputs.py) in
`a559eb63` **before** generating [the fresh fixture](joint-window4-zero-inputs/inputs.json).
The new fixture contains 32,768 scalars across eight cases and excludes the
eleven preceding fixtures. Training saved 4,028 mixed additions on
`glv-j0-32` and 20 on `j0-56`; those counts were not used as a held-out
result.

The [release panel](joint-window4-zero-native-panel.json) and
[warnings-as-errors UBSan panel](joint-window4-zero-ubsan-panel.json) each
have 24 arms in rotating order: directed zero window, ordinary packed plane,
and fixed comb9. All native arms independently verified 4,096 outputs per
case. An independent Python model checked all 32,768 scalar identities,
184 group outputs, the congruence, candidate feasibility, and selection
counts. The C suite passed 2,312,167 checks in both builds, including a
selection witness on each curve, a corrupted modular inverse, identity
input, and forced capacity fallback. No held-out run used the generic
fallback.

The counts aggregate 16,384 scalar multiplications per curve. Unit adds
count modular additions and negations for `β²x`; the point table and
1,308-byte static orbit map are the same in both modes.

| Curve | Mode | Point slots | Point-table bytes | Mixed additions | Unit adds | Feasible directed candidates | Selected candidates |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | directed zero window | 284 | 9,088 | 51,062 | 24,772 | 10,535 | 3,834 |
| `glv-j0-32` | ordinary packed plane | 284 | 9,088 | 54,929 | 23,276 | — | — |
| `j0-56` | directed zero window | 497 | 15,904 | 114,201 | 57,382 | 99 | 24 |
| `j0-56` | ordinary packed plane | 497 | 15,904 | 114,225 | 57,374 | — | — |

The small curve saves 3,867 mixed additions, or 7.04%, on fresh inputs.
The large curve saves 24, or 0.021%. The small-curve selection also incurs
1,496 extra unit field additions or negations, and **every nonzero scalar
tries a second digit recode**. That integer work is inside the online
interval; the operation counts alone do not establish a CPU speedup.
Local macOS timing fields are exploratory. The [isolated manifest
producer](make_joint_window4_zero_isolated_manifest.py) binds exact sources,
inputs, modes, and expected output digests for a future qualifying physical
host. This is a repeated public-scalar workload, not a one-target DLP or
rho result.

GLV lattices and joint Eisenstein digits have prior art, including the
[Pasta curves GLV implementation](https://docs.rs/zakura-pasta-curves/latest/pasta_curves/glv/index.html).
The directed congruence is a new experiment in this repository; this
evidence does not establish academic novelty.

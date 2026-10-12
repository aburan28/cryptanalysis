# Paired radix-944 source-operation diagnostic

On the frozen 4,096-scalar panel, the thirteen-window radix-944 evaluator
executed **1,480,701 fewer modeled limb products** than the fourteen-window
mixed-radix-640 evaluator. It selected 4,096 fewer affine point rows and
made 4,096 fewer atlas queries. This comparison uses the same scalar, curve,
representative, binary output, and native source snapshot for each pair.

| Count over 4,096 scalars | Radix 944 | Mixed radix 640 | Candidate minus control |
| --- | ---: | ---: | ---: |
| Mixed additions | 49,152 | 53,248 | −4,096 |
| Grouped Solinas rotations | 14,838 | 15,105 | −267 |
| Logical point-row loads | 53,248 | 57,344 | −4,096 |
| Atlas queries | 53,248 | 57,344 | −4,096 |
| Field additions | 73,728 | 77,824 | −4,096 |
| Field subtractions | 333,807 | 360,250 | −26,443 |
| Generic field multiplications | 434,176 | 466,944 | −32,768 |
| Field squares | 110,592 | 118,784 | −8,192 |
| Constant `/5` on wide words | 0 | 131,072 | −131,072 |
| Constant `/5` on small values | 0 | 65,536 | −65,536 |
| Constant `/59` on wide words | 212,992 | 0 | +212,992 |
| Constant `/59` on small values | 106,496 | 0 | +106,496 |
| Modeled limb products | **19,952,922** | 21,433,623 | **−1,480,701** |
| Native retained bytes | 71,450,736 | 31,302,596 | +40,148,140 |

The [diagnostic patch](ops-diagnostic.patch) increments counters at the
`u256_add`, `u256_sub`, `u256_mul`, `u256_square`, and
`u256_mul_const_solinas` call sites. It counts the two wide constant
quotients and one small carry quotient per coordinate update. The logical
point-row count comes from the selected nonidentity seeds; the atlas-query
count comes from the fixed window loops. Both tables are warmed before the
counter resets. The test checks each radix-944 result against the radix-640
result on the same scalar.

The model uses `36 × (generic multiplication + square) + 23 × Solinas
rotation`, the same source-level weighting used in the radix-640 diagnostic.
It measures the listed calls, rather than all processor instructions.
Representative selection, direct calls inside the final affine inversion,
table construction, actual cache transactions, and compiler lowering of
constant division are outside this counter boundary. The quotient counts
and 40,148,140-byte table increase must be charged in a full-operation
comparison before choosing a faster format. The contended local host and
the current RunPod Pod cannot establish a controlled wall-time ratio.

The raw [test log](ops-diagnostic.log) and [receipt](ops-diagnostic.json)
bind the counts to the frozen input SHA-256, native materializer, diagnostic
patch, and generated source after root-path normalization. Rebuild and
replay from this checkout with:

```sh
python3 experiments/prime-j0-asymmetric-r944-20261010/materialize_native.py /path/to/separate-crate
patch -p1 -d /path/to/separate-crate -i "$PWD/experiments/prime-j0-asymmetric-r944-20261010/ops-diagnostic.patch"
R944_PANEL="$PWD/experiments/prime-j0-asymmetric-r944-20261010/fresh-inputs.json" \
  CARGO_TARGET_DIR=/path/to/separate-target \
  cargo test --locked --release --manifest-path /path/to/separate-crate/Cargo.toml \
    --bin eisenstein_fixed asymmetric_radix944_source_operation_diagnostic \
    -- --nocapture --test-threads=1
python3 experiments/prime-j0-asymmetric-r944-20261010/ops_receipt.py
```

The next arithmetic experiment should test a thirteen-window power-of-two
radix against this exact input panel. Its quotient update can use shifts;
the table and cache cost must be measured alongside the saved point work.

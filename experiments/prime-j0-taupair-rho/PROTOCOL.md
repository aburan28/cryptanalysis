# One-target rho gate for gauge-carrying paired τ

## Frozen question

Can the opt-in paired-τ gauge evaluator from
`experiments/prime-j0-taupair-steer` replace the startup scalar path of
one GLV rho solve while recovering the same public target and
preserving the rho trajectory? The control is the existing
`paired2-free-gauge-batch` path, and `reference` is the generic scalar
startup. All three receive the same previously unseen public point,
rho seed, curve, resource envelope, fresh distinguished-point table,
walk and collision policy, and internal scalar verification. The
candidate uses the same 1,104-byte target-specific prepared table and
eight-output batch normalization. It may choose different recodings
and gauges; its affine table and restart points must still agree.

The online clock starts at the first target-dependent computation in
`glv_rho_solve` after input/subgroup validation and stops after scalar
recovery and internal verification. It includes target-dependent τ
preparation, all table entries and restarts, batch-prefix products and
inversion, walk, collision, and failed work. Process launch, curve
construction, fixture generation, and the separately timed external
scalar replay are excluded. Keep their timing and correctness records.

The frozen operation diagnostic is the current nominal evaluator
field-multiplication count

`4 * eval_tau + 8 * eval_mixed_adds + eval_rotations
 - eval_tau_pairs - eval_tau_pair_cheap_z`.

This uses the implementation's `4M+2S` τ, `8M+3S` ordinary mixed add,
and one M per unit rotation, with one or two M saved by each fused
pair. It does not include squarings, first-add shortcuts, exceptional
additions, inversion, batch normalization, recoding, table lookup, or
the rho walk. It is a stage diagnostic, not an end-to-end speed metric.
The gate requires a positive reduction against the free-gauge control,
the same scalar and trajectory counters as generic rho, the same
preparation and batch-inversion counts as the control, nonzero fused
pairs, valid cheap-Z accounting, and an independent scalar replay.

## Frozen execution order

Commit implementation, tests, this protocol, independent affine
target generator, serial checker, and isolated-run manifest generator
before deriving a new target. Freeze its public point, construction
seed, known fixture scalar, and rho seed in a second commit before
running any solver. Run `reference, paired2-free-gauge-batch,
taupair-steered-batch, taupair-steered-batch,
paired2-free-gauge-batch, reference` serially in Release and UBSan.
Preserve every raw success and failure, exact target and seed, code and
binary hashes, operations, online intervals, replay time, and
correctness certificate. The local host has no verified exclusive CPU
partition or NUMA isolation, so set `cpu_speedup_claim: null` and
`isolation_receipt: null` regardless of local timing. The included
manifest generator binds this workload to the strict isolated runner
for a later controlled repeat.

The mode remains opt-in. An online wall-time speedup claim requires an
isolated host receipt and paired repetitions. Academic novelty of the
gauge-carrying scalar scheme remains unestablished.

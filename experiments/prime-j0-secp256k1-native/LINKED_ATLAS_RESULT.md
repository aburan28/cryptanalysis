# Linked three-orbit τ atlas: held-out source counts and native replay

The candidate, protocol, fresh-input generator, and native mode were
frozen in `527af3ac` before generating the new 256-case Sage panel.
Slots 5, 6, and 7 of the width-four digit table are `(2,-4)`, `(4,-8)`,
and `(4,4)` in the `a+bτ` coefficient basis. They are doubles of
existing slot 8, the new slot 5, and existing slot 4, respectively.
Their sign/ω orbits cover the same three residue classes as the original
slots; all 54 nonzero residues are unique. The recoder terminates for
all integer coefficient states: its closed ball contains 817 states at
norm at most 224, with no nonzero cycle, and norm strictly decreases
outside that ball.

Preparation uses **six point doublings and two mixed additions**, plus
the same two unit rotations and nine orbit-image multiplications as the
original chain: `6*7 + 2*11 + 2 + 9 = 75 M+S` per one-use scalar,
versus `83 M+S` for the original. Within the one-result graph of
doubles, τ steps, additions, and unit rotations, **64 point-operation
units before rotations** is a lower bound for these nine residue
orbits: all eight nonbase orbits have norm prime to three, so a τ step
cannot produce one directly; doubling stays in one of the three
residue-orbit cycles, and each of the two noninteger cycles needs at
least one addition. The other six new orbits need at least a doubling.
The linked chain attains `2*11 + 6*7 = 64`. This bound does not cover
fused, multi-output formulas or other digit alphabets.

| Frozen input panel | Cases | Original `M+S` | Linked atlas `M+S` | Saving | Per-case signs |
| --- | ---: | ---: | ---: | ---: | --- |
| Original design, 64 distinct bases | 64 | 88,656 | 88,089 | 567 (0.640%) | 39 improve, 25 regress |
| New held-out, 8 bases × 32 scalars, setup charged to every scalar | 256 | 354,504 | 352,827 | 1,677 (0.473%) | 161 improve, 88 regress, 7 tie |

The held-out paired mean saving is **6.55 `M+S` per scalar**. A
10,000-resample paired bootstrap over the saved 256 cases, seeded
`20261007`, gives a descriptive 95% interval of **3.83–9.25** units
per scalar. This is input variation, not CPU timing uncertainty. Every
case's operation counts, including negative deltas, are retained in
`linked-atlas-result.json`. Its fixture SHA-256 is
`19c14b3766c23f3c21fcb36cf8d85a8111eb5c29af28a79231d6e609692c3eb4`.

The checked repository Sage launcher wrote `linked-runtime-info.json`
with `status: verified` before the new scalar and seed jobs. Sage
independently computed all three new seed points and scalar outputs;
the seed fixture SHA-256 is
`669aaefee15a503ce9a3b0eda3988957ed4244f0f00cba09b512e3dd6ae0417f`.
The offline release binary on macOS ARM64 (`rustc 1.93.1`) has SHA-256
`3fe97d084cebd2dde170eaaf7c7187013cd8ad6635172106edb8e907475a32e4`.
It matched **3,150 prepared seed points and 350 final scalar points**
on the original, edge, and new held-out panels. No cached addition took
an exceptional branch. Its counted operations exactly match the Python
model on both nonedge panels. Original-table and earlier two-orbit
replays still pass on the design panel. All commands, raw outputs,
exits, source/fixture hashes, and compiler/host details are in
`native-linked-checks.json`.

`make_linked_manifest.py` generated a 64-case paired one-use manifest
for the isolated benchmark service. `isolated_bench.require_manifest`
passed its **structural** check with synthetic CPU/NUMA/cgroup values.
No physical-host preflight or CPU measurement ran. The operation
count excludes lattice reduction and final affine inversion; the
native timing interval includes both. No CPU speedup or academic
novelty is claimed. This remains variable-time research code.

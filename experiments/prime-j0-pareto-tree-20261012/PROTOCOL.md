# Pareto gauge-tree scalar plan protocol

Format 173 keeps format 172's secp256k1 generator, 14 sector digits,
64,314,208-byte canonical affine table, nine-limb-product Karatsuba Solinas
field kernel, and XYZZ point formulas. It changes only the binary schedule
used to sum the selected points.

For each of the 680 triples of nonnegative gauge counts with sum at most 14,
`plans.py` enumerates every nonempty split of the count triple and each of
the three output gauges. A state retains the nondominated pairs of total
ordinary-path field products and maximum field-product dependency depth.
The child cost is 6 products for an affine pair, 10 for a mixed join, and 14
for a projective pair. A child gauge change costs one product and adds one to
that child's depth. At the root, returning to gauge zero is charged once.
Dominated states cannot improve any parent join; `ParetoCost.lean` proves
that pruning rule under this cost recurrence.

Choose the least-work plan whose depth does not exceed format 172's cached
plan depth for that same gauge-count triple. Break ties by depth and gauge.
The selected postorder joins are frozen in `plans.bin`: 680 records of 42
bytes, each holding thirteen three-byte join slots, step count, rotation
count, and product depth. `python3 plans.py --check` recomputes the table and
panel record byte for byte. The Rust implementation decodes the table during
preparation, before the online scalar timer.

The primary algorithmic screen is the frozen 4,096-scalar panel in
`../prime-j0-sector-digit-20261010/fresh-inputs.json`. Check all 680 count
patterns on actual affine points against format 172, then check every panel
point, recoding field, and the first 128 independent binary products. Rebuild
the release CLI and check all 129 cases in the independent fixed fixture.
The source operation model excludes recoding, table access, field reduction
latency, exceptional branches, inversion, and output conversion. Full
operation timing requires an isolated host and a paired format-172/173 run.

Reproduction from the repository root:

```sh
python3 experiments/prime-j0-pareto-tree-20261012/plans.py --check
ELAN_TOOLCHAIN=leanprover/lean4:v4.34.1 lean \
  experiments/prime-j0-pareto-tree-20261012/ParetoCost.lean
cargo test --release --offline --manifest-path \
  experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed pareto_gauge -- --nocapture
cargo build --release --offline --manifest-path \
  experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed
experiments/prime-j0-secp256k1-native/target/release/eisenstein_fixed \
  --check-scalar-unit-orbit-u256-sector14-xyzz-gauge-pareto-solinas-fixed-fixture \
  experiments/prime-j0-secp256k1-native/tau6-comb13-bench-fixture.json
python3 experiments/prime-j0-pareto-tree-20261012/verify_cli.py
```

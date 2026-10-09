# Conjugate-x filtering for the A1 all-hit relation collector

The collector now has an opt-in raw-x membership gate before Frobenius-orbit
canonicalization. For this complete pair index, the gate is built from its
735,000 exact keys and all 53 conjugates of each key. The original exact
`HashMap` lookup and the point/weighted-row replay still decide each hit.
The filter occupies 38,955,008 bytes for this index and is prepared before
the relation-collection clock.

`PROTOCOL.md` fixes the paired primary and disjoint relation-query streams,
the off/on order, semantic checks, and claim boundary. `results/summary.json`
is produced by `validate.py` after the runs. The source inputs copied from
the existing A1 packed pipeline have these SHA-256 hashes:

| Input | SHA-256 |
| --- | --- |
| `inputs/export.json` | `c0f50393cad99f969575b059239b00fb500a1b19e5835ea63383dcb54376e2ee` |
| `inputs/index.bin` | `57b6537bafa9db80726051e75253bc6f6f7a5809a1245b7770b91ad5859d80d6` |
| `inputs/primary.json` | `5f0fcc32f19aa9aed71f4803831213a2419de3e005b2fcf1f1e1ef98673e99e1` |
| `inputs/disjoint.json` | `cc9ab070974c2029c5ef8dd5f8f8e64eb8c1c19ce3824da42fd607047b085a3a` |

The original collector source copied for this port had SHA-256
`b25e0085f9ccaf13b038287f1f2872761f0971beaf20a225e0ac4d35aa5b0f51`.
The Rust dependency is `crypto` revision
`8ab924b935923df9faac25915ed7d9849974de0b` in a clean sibling checkout.
The relative Cargo path resolves to that sibling from a normal checkout.

Run the semantic test and build using that revision:

```sh
cd experiments/a1-allhit-conjugate-bloom-20261009/collector
cargo test --release --offline --locked
cargo build --release --offline --locked
cd ..
python3 run_panel.py --binary collector/target/release/a1-packed-collector
python3 validate.py
```

The separate `make_disjoint.py` command regenerates the second frozen
workload in a clean copy where `inputs/disjoint.json` is absent. It refuses
to overwrite the archived file.

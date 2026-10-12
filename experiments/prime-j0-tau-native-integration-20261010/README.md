# Integrated nineteen-window tau scalar evaluators

This branch applies the four frozen native patches from the scalar table frontier to the shared `eisenstein_fixed` evaluator: seventeen-window mode 137, nineteen-window mode 138, orbit-X mode 139, and tau-preexpanded mode 140. It is stacked on scalar [PR #609](https://github.com/aburan28/cryptanalysis/pull/609), whose ancestry already includes the point-only U14 source. The two resulting Rust source hashes equal the independently tested mode-140 scratch receipt exactly:

| Source file | SHA-256 |
| --- | --- |
| `eisenstein_fixed.rs` | `63d8ddad4e851ed45d5d49e4a511709abf29e48b47439fe72d64ddb9dda4dd8b` |
| `unit_orbit_windows.rs` | `42af6a8a6977f33ab487b9bfc12792f8b9e1481be480a58bc1eb5351685105de` |

The [release test log](release-tests.log) records **106 passed, 0 failed**. The release binary SHA-256 is `096245f9c3ffc923c80c7adbbd7d5d68fdd61690e7eb328ffe6c0a60ef3aaa5b`, matching the scratch prototype binary. The integrated CLI was replayed over the independently generated 4,096-scalar panel for modes 138, 139, and 140. Each mode's full output stream matched its frozen stream byte for byte, and every point matched the fixture. [The result receipt](integration-result.json) records the source, binary, fixture, and output hashes; [the receipt verifier](verify_receipt.py) checks them without rebuilding.

Rebuild and replay from a full checkout with the same native dependencies:

```sh
cd experiments/prime-j0-secp256k1-native
TMPDIR=/private/tmp cargo test --release --bin eisenstein_fixed
TMPDIR=/private/tmp cargo build --release --bin eisenstein_fixed
cd ../..
python3 experiments/prime-j0-tau-native-integration-20261010/verify_integration.py \
  experiments/prime-j0-secp256k1-native/target/release/eisenstein_fixed
python3 experiments/prime-j0-tau-native-integration-20261010/verify_receipt.py
```

The CPU point-count comparison is in [the source-bound diagnostic](../prime-j0-tau-expanded-20261010/OPS_DIAGNOSTIC.md). The implemented formats use scalar-dependent table indices and are opt-in public-scalar paths. Online wall-time comparison needs a physical host that passes the repository's isolated benchmark preflight. This integration is kept on a stacked branch while the shared native files have an active Conductor reservation.

# Nine-product Karatsuba Solinas XYZZ scalar format

Format 170 evaluates the same 14-window secp256k1 sector schedule as format
169. Its canonical field product uses a two-level difference Karatsuba wide
multiply before the same Solinas fold. On the frozen 4,096-scalar panel, the
source model counts **8,650,352** 64-by-64 products in the ordinary XYZZ
additions and unit rotations, compared with **12,434,881** for format 169.
This is a reduction of 3,784,529 products within that source boundary.

| Evidence | Result |
| --- | --- |
| Full 512-bit and field products | 36 boundary operand pairs and 10,000 deterministic random pairs matched independent big-integer multiplication; field squares matched independently |
| Scalar replay | 4,096/4,096 complete format-169 point and metadata records matched |
| Independent points | First 128/128 panel points matched binary multiplication |
| Release CLI | 129/129 fixture rows matched scalar, base point, expected point, mode, and `verified=1` |
| Mathematical product identity | Lean 4.34.1 checked the two-limb identity, middle coefficient, and four-limb composition; `#print axioms` lists only `propext` and `Quot.sound` |
| Retained table and constants | 64,314,208 bytes, equal to format 169; the new wide-product temporaries are stack-local |
| Implementation host | Darwin arm64; release Rust 1.93.1; correctness and operation-count run |

The [model](model.json) binds the same 53,248 ordinary mixed additions and
8,167 unit rotations used by the format-169 comparison. Its boundary counts
ten field products per ordinary addition and one per rotation. The wide
product has sixteen variable 64-by-64 products in format 169 and nine in
format 170; each path has the same seven constant-fold products. The model
excludes scalar recoding, table construction, final inversion/conversion,
carry instructions, memory traffic, and exceptional group paths. A CPU
wall-time ratio awaits a paired full-operation run with a passing
[host-isolation receipt](../../docs/ISOLATED_BENCHMARKS.md).

The [written proof and map](PROOF.md) explain the two-level identity.
Its Lean declarations prove the unbounded integer product; the correspondence
of the Rust `u64` masking and carry chains to that product remains an open
formalization bridge. Independent wide-product, field, and point checks cover
the implementation empirically. The final Solinas reduction uses the
previously checked theorem in `../prime-j0-u14-solinas-20261012/`.

## Frozen identities

All digests are SHA-256. The release binary and CLI output were built after
the final Rust source change.

| Artifact | Digest |
| --- | --- |
| `src/bin/eisenstein_fixed.rs` | `44e2bfd81077651621c60789a2bb0d4d3820b4c98754dd6ccb384c96f88c825e` |
| `src/bin/eisenstein_fixed/unit_orbit_windows.rs` | `34488e33d8d52ca510226de23291c61d0bfa912a65768c559401f17c97ff7585` |
| Release CLI binary | `4b1a73520493a3ba5d64c290523a857e039ca68a9f64dd4443e3b3d83cf3038f` |
| 4,096-scalar panel | `1dd3d17f3485c144f045cf0a81394b8d129095b74ac2de9a06e06d6f4ef2cd99` |
| 129-case CLI fixture | `2895d9c40912b090f0e6ce85ef8bb4d92822a83a5626fb376fcb552a556981fb` |
| CLI output | `602f6045653a908eb45d5573eb0826fc6d02ee55a2980b8eb30e3a4c39d98d99` |
| `verify_cli.py` | `38fd67fc4f8d2239a5689ab6a49fd926003322966c7ec59f5054f1dae79a2b5f` |
| CLI verifier log | `815a4d167732a2538647e5c73b56730e938905470b960d676da2d97aa71bd3a4` |
| `model.py` | `e818df560491b94f652509ee23d9513f1361d5183c4dfe01efe85847212bea00` |
| `model.json` | `980a5174592cf9e6b84cfc5d86fb966adad0ec2815311c48337285617d39cf73` |
| `KaratsubaProduct.lean` | `0bfc5978fc6643df1b18e5869158ecb82949f839ca46efa9cb0a6c12fba55b64` |
| `lean-toolchain` | `d5edba4e4b8faad9c1baeadb265716d20d03be4d1a2647dc5e35b0c0325bea7b` |
| Lean build and axiom audit | `a4f38c0b36ce1ddde29f02548b168dacd0891434d0183f4277de1a798e988185` |
| Wide/field test log | `70d43a6c340dfcf4a0f1127ec2720703458ec3b53c4f981da4a056267ee4dde3` |
| Full-panel test log | `730dd922b0c94a487a9104a1b999e36ebfadd35406b78e28e89546d11e0814ee` |
| Release build log | `56f50ea94d6858d9aed325ccc2019fa3f2b8bed1b074effb4d136893f5affe1f` |

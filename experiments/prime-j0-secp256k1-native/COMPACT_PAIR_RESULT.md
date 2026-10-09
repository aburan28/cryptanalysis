# Compact affine storage for the orbit-pair tau comb

Packing each orbit-pair table point into four three-limb signed field
coefficients reduced retained table storage from **102,036,672 to
24,564,384 bytes** for the same **236,196** points. That is a **75.93%**
reduction, or **4.15 times** less retained table storage. The evaluator
decodes a selected point immediately before the existing unit map and mixed
addition. Every scalar operation and output is preserved.

The new slot contains 96 bytes of coefficient magnitudes and one byte of
sign bits, with a seven-byte layout pad on this 64-bit build: **104 bytes**.
Construction checks every coefficient of every table point and aborts if
any high magnitude limb would be discarded. The six pair tables, hex9
selector, width-six recoding, sparse top row, and terminal repair remain as
specified in the [paired-row result](PAIR_COMB_RESULT.md).

## Frozen verification

The complete native JSON output matched the frozen paired-row binary on
**2,396 scalar inputs**: 5 boundaries, 214 earlier cases, 129 benchmark
fixtures, and 2,048 fresh scalars from seed `20261009131`. An independent
Python secp256k1 multiplication checked 261 boundary/fresh points; every
fixture point matched its recorded expected coordinates. All **48 native
release tests** passed, including sampled direct pair-sum comparisons.
The table constructor validated the three-limb bound for all 236,196
stored points. The differential result SHA-256 is
`dcad9e937b2a905f9a25a121b93b3da03d8e8b871dd76fe95811a41be98a211c`.

The 129-case, seven-repetition paired isolated benchmark manifest passed
structural validation. Cases 0, 64, and 128 returned their verified
expected points from both case entrypoints. Its SHA-256 is
`d8fa5e3e12cae588c603fd94b5935ef4452562a2f47718ce6a3726a07fde89bb`.
The manifest charges slot decoding and every subsequent operation inside
the online timer.

## Resource record

| Prepared table | Stored bytes | Preparation interval on local macOS ARM64 | Child peak RSS |
| --- | ---: | ---: | ---: |
| Full-width parent | 102,036,672 | 2,296.478 ms | 129,024,000 bytes |
| Three-limb compact | **24,564,384** | 2,671.157 ms | 129,105,920 bytes |

The preparation entrypoint times table construction before any scalar
input. The compact representation reduces retained lookup storage; peak
RSS during construction remained about 129 MB because projective and
normalization intermediates are still built. Preparation times here are
resource diagnostics on an ordinary local host. The compact preparation
receipt SHA-256 is
`0152d31c2499259c4403d4eddfa18d3068faa010aae7dc5714c3a713b7d063b1`.

| Receipt | SHA-256 |
| --- | --- |
| Parent source | `280de1b3ff243c21e3e6b77d15128aba65491b62022402d2045f6a1f2d5d7fd3` |
| Parent release binary | `285e29a661105e63a290c9c45d9df63b36d6cf6f4f65fed27e9a9d4250d4a236` |
| Compact source | `c6c6127557ca475314c58feb7476fd03c62dce3a50c6190bb2071c9d07d76c9f` |
| Compact release binary | `2b2def850cc37cb06815590e1b7921fb3d7debe5453d64287c84341e76fcb18b` |
| Differential checker | `eb42081f11508469c7857e5452d8aede3c591e19de3797033654e4b5144e8e13` |

The exact input law and gates were recorded in
[the protocol](COMPACT_PAIR_PROTOCOL.md) before implementation. The next
measurement is a complete online comparison on a host passing
[the CPU isolation gate](../../docs/ISOLATED_BENCHMARKS.md). A separate
builder experiment can reduce construction peak memory by normalizing
smaller point batches; it should retain the same slot values and online
boundary.

## Reproduce

```sh
cd experiments/prime-j0-secp256k1-native
export CARGO_TARGET_DIR=/absolute/path/to/compact-build
cargo test --offline --locked --release --bin eisenstein_fixed
cargo build --offline --locked --release --bin eisenstein_fixed
"$CARGO_TARGET_DIR/release/eisenstein_fixed" --prepare-w6-comb13-hex9-paired
PYTHONDONTWRITEBYTECODE=1 python3 compact_pair_check.py \
  --reference /absolute/path/to/full-width/eisenstein_fixed \
  --candidate "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --output /absolute/path/to/new-result.json
```

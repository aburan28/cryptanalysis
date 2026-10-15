# Direct signed-digit, one-bucket radix `112 − τ`

This fixed-base secp256k1 format uses the norm-12,211 Eisenstein radix
`π=112−τ` for 18 positions. Each residue selects its centered integer digit
`d∈[−6105,6105]`, so every digit point is added directly to one accumulator.
The terminal point is a direct sign-canonical lookup. The resulting online
group path has no final projective bucket joins or endomorphism rotations.

The exact [integer screen](screen.py) starts with the same certified scalar
lattice representative as the [three-bucket parent](../prime-j0-split-prime-12211-20261014/README.md).
For `z=a+bτ` and centered digit `d≡a+112b (mod 12,211)`, define

```
k = (a+112b−d)/12211
z' = (109k−b) + kτ.
```

Then `z=d+πz'` and `N(d)=d²≤6105²`. The checked radius sequence ends at
`R₁₈=89`, proving `N(z₁₈)<89²` for the selected scalar trajectory. The
terminal ball contains 14,344 sign-canonical integer pairs. Storing all
6,106 digit magnitudes at 18 positions and all terminal pairs uses a
**7,952,128-byte minimum affine payload** before structure metadata. The
[screen receipt](screen.json) preserves the radius sequence and 128 frozen
integer scalar replays.

The native table retains **7,953,280 bytes** including metadata. Case 0
verified the same scalar and point as the parent fixture with 18 nontrivial
mixed additions, 18 digit reads, one terminal read, nine sign flips, and
zero projective joins or endomorphism rotations. Its raw output is in
`native-case0.log`; the preparation interval is separate from the online
interval.

The three Lean 4.34.1 modules prove the norm recurrence, centered-digit
bounds and residue reconstruction, and the complete selected-scalar terminal
theorem. Build output and `#print axioms` are retained in the respective
logs. The first digit-proof attempt failed on proof-script details; its
original output remains in `digits-build-initial-failure.log`. The corrected
proof contains no `sorry`, `admit`, custom claim axiom, or native evaluation.

| Mathematical result | Lean declaration | Scope |
| --- | --- | --- |
| Norm-12,211 quotient contraction | `SplitPrime12211Direct.step_bound` | All integer coordinates. |
| Centered digit coverage and bound | `SplitPrime12211DirectDigits.bounded_step` | Every integer state. |
| Selected 18-step terminal bound | `SplitPrime12211DirectComplete.canonical_scheme_terminal_bound` | Certified representative and its direct digit trajectory. |

The [native overlay](native_overlay.py) starts from the hash-pinned generated
norm-12,211 Cargo source, removes the residue atlas and unit buckets, and
replaces them with direct digit and terminal tables. Its exhaustive test
covers the native quotient code, terminal indexing and sign images; scalar
replays compare with independent binary multiplication. Source, binary and
proof hashes are pinned in `validation.json`. The five release test families
passed: 12,211 residue classes, 109,899 quotient cases, 14,344 terminal
indices, 219,816 signed digit images, 128 frozen scalar replays, and 518
independent additional scalar replays.

The local case-0 interval is an exploratory diagnostic. The one-bucket
format needs an alternating, same-scalar Tier 1 panel against the three-
and two-bucket variants, with A/A calibration, before a latency ranking.
The RunPod CPU Pod resume request returned `INSUFFICIENT_BALANCE` on
2026-10-14. The account's balance was negative; the Pod remains stopped.

Reproduce the integer screen from the repository root:

```sh
python3 experiments/prime-j0-direct-one-bucket-12211-20261014/screen.py
```

Apply `native_overlay.py` to a byte-identical copy of the generated parent
Cargo directory, then run:

```sh
CARGO_TARGET_DIR=/private/tmp/prime-j0-split-prime-8011-target cargo test \
  --manifest-path /private/tmp/prime-j0-direct-one-bucket-12211-native/Cargo.toml \
  --offline --locked --release --bin eisenstein_fixed split_prime_ \
  -- --test-threads=1 --nocapture
```

# Eighteen-position fixed-base radix `112 − τ`

The Eisenstein split prime `π=112−τ`, with `τ²=3τ−3` and norm **12,211**,
gives an 18-position fixed-base secp256k1 multiplier. The three-bucket
implementation with a unit-orbit terminal table retains **2,626,858 bytes**.
Compared with the 19-position norm-8,011 orbit variant, it uses one fewer
digit read and one fewer nontrivial mixed addition on frozen scalar case 0,
at a cost of **863,732 additional retained bytes**. Its operation profile is
16 mixed additions, two projective joins, and two bucket rotations.

## Integer recoding and terminal proof

For `z=a+bτ`, the digit residue is `a+112b (mod 12,211)`. The canonical
cover has 2,035 nonzero six-unit seed orbits plus zero; its largest seed is
4,033. With digit `d=dₐ+dᵦτ`, put

```
k = ((a−dₐ)+112(b−dᵦ))/12211
z' = (109k−(b−dᵦ)) + kτ.
```

Then `z=d+πz'` exactly and `N(d)≤4033²`. Starting from the existing
selected scalar representative, whose cell bound is `3N(z₀)≤r`, the exact
radius recurrence in [screen.py](screen.py) reaches `R₁₈=70`; hence every
selected 18-step trajectory ends with `N(z₁₈)<70²`. The complete terminal
ball contains 8,872 sign-canonical pairs and 2,958 unit orbits. The
[screen receipt](screen.json) retains the radius sequence, fixture hashes,
and exact integer replay.

The parent [unit-orbit proof](../prime-j0-terminal-orbit-8011-20261014/TerminalOrbit8011.lean)
establishes the order-3 action, norm preservation, and six distinct images
for every nonzero integer pair. The new Lean modules prove the norm and
quotient identities, radius recurrence, complete residue-digit cover, and
the bound for the canonical selected-scalar trajectory. Their exact build
status and axioms are recorded in `validation.json` and the build logs.

| Result | Lean declaration | Scope |
| --- | --- | --- |
| Norm and quotient identities | `SplitPrime12211.pi_norm_identity`, `recoding_step_identity` | All integer coordinates. |
| Canonical digit cover | `SplitPrime12211Digits.canonical_cover` | All 12,211 residues. |
| Eighteen-step terminal bound | `SplitPrime12211Complete.canonical_scheme_terminal_bound` | Selected scalar representative and canonical digit trajectory. |
| Curve-point implementation | Native checks in `native-test.log` | Complete terminal map and independent scalar replay. |

## Native verification and accounting

The [native overlay](native_overlay.py) accepts only the hash-pinned
norm-8,011 orbit source and changes its radix, seed cover, terminal ball,
and exact test assertions. All five native test families passed: 12,211
residues, 109,899 quotient cases, 8,872 terminal indices, 219,888 digit
unit images, 128 frozen scalars, and 518 additional deterministic and
boundary scalars checked by independent binary multiplication. The
[native test log](native-test.log) and [case-0 log](native-case0.log) retain
the output; `validation.json` pins the generated module and binaries.

The case-0 local wall interval is an exploratory diagnostic under the
repository's CPU benchmark tier contract. A qualified latency ranking needs
an A/A-calibrated, same-scalar Tier 1 panel on the serialized RunPod worker.
The allocation request on 2026-10-14 was rejected for insufficient account
balance, so that panel remains pending.

Reproduce the exact integer screen from the repository root:

```sh
python3 experiments/prime-j0-split-prime-12211-20261014/screen.py
```

Generate the parent norm-8,011 terminal-orbit Cargo directory at its pinned
source, then apply this experiment's `native_overlay.py` to a copy and run:

```sh
CARGO_TARGET_DIR=/private/tmp/prime-j0-split-prime-8011-target cargo test \
  --manifest-path /private/tmp/prime-j0-split-prime-12211-native/Cargo.toml \
  --offline --locked --release --bin eisenstein_fixed split_prime_ \
  -- --test-threads=1 --nocapture
```

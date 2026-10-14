# Nineteen-position fixed-base radix `91 − τ`

The split Eisenstein prime `π = 91 − τ`, with `τ² = 3τ − 3`, has norm
`N(π) = 8,011`. Its six-unit digit cover gives a **19-position** fixed-base
secp256k1 multiplier. A three-bucket native evaluator stores one 64-byte
affine point per canonical seed per position and retains **1,919,146 bytes**
in total. The prior norm-4,831 three-bucket candidate uses 20 positions and
1,425,154 bytes; the new schedule spends 493,992 additional bytes to remove
one position. The direct two-x norm-4,831 candidate retains 1,940,994 bytes.
These are exact digit-count and retained-memory comparisons. Wall-time ranking
requires an isolated paired panel.

## Integer recoding and terminal proof

For `z = a+bτ`, choose the canonical digit `d = dₐ+dᵦτ` in the residue
`a+91b (mod 8,011)`. The nonzero residues form 1,335 orbits under the six
units; zero adds one seed. The largest canonical integer seed is 2,640. Put

```
k = ((a−dₐ) + 91(b−dᵦ)) / 8011
z' = (88k−(b−dᵦ)) + kτ.
```

Then `z = d + πz'` exactly, and every selected digit has norm at most
`2,640²`. The minimum-norm scalar representative from the existing lattice
selector satisfies `3N(z₀) ≤ r`, where `r` is the exact secp256k1 subgroup
order. [The exact screen](screen.py) starts at
`R₀ = ⌊√⌊r/3⌋⌋ + 1` and takes the least integer `Rᵢ₊₁` satisfying
`(Rᵢ+2,640)² < 8,011 Rᵢ₊₁²`. Its checked sequence ends at `R₁₉=46`.
Consequently every selected 19-step trajectory has `N(z₁₉)<46²`, covered
by 3,838 sign-canonical terminal pairs.

The 128-scalar frozen fixture independently replays each lattice
representative and radix reconstruction. It uses 19 nonzero digits for 127
scalars and 18 for one scalar; the largest observed terminal norm is 1,561.
The [screen receipt](screen.json) contains the full radius sequence and input
hash. These fixture counts describe this frozen input law, not all scalars.

## Formal and native checks

Lean 4.34.1 checks the central theorem and its dependencies. The
[Lean output](lean-check.log) records the build commands and `#print axioms`
results. No proof uses `sorry`, `admit`, a custom claim axiom, or native
evaluation.

| Mathematical result | Lean declaration | Scope and verification |
| --- | --- | --- |
| Primality screen and norm identity | `SplitPrime8011.norm_trial_division`, `pi_norm_identity` | Exact integer trial division through 89 and `N(πz)=8011N(z)`; checked. |
| Quotient and contraction | `SplitPrime8011.recoding_step_identity`, `step_bound` | Exact quotient equation and norm triangle bound; checked. |
| All residue digits | `SplitPrime8011Digits.canonical_cover`, `bounded_step` | All 8,011 residues, six-unit image and bounded quotient step; checked. |
| Selected scalar trajectory | `SplitPrime8011Complete.trajectory_table_digit`, `canonical_scheme_terminal_bound` | Starts at `selectedCandidate scalar`, constructs the canonical digits, and proves `N(z₁₉)<46²`; checked. |
| Concrete secp256k1 point action | Five Rust test families in `native-test.log` | Independent scalar replay and exhaustive digit images check the implementation bridge; a full field-level Lean bridge is open. |

The [native overlay](native_overlay.py) retargets the generated norm-4,831
three-bucket source to this radix with checked one-to-one source anchors.
The release test binary passes all five relevant families: 8,011 residue
codes and 72,099 quotient cases, 152,304 digit unit images, 3,838 terminal
indices, the 128 frozen scalars, and 518 additional deterministic and
boundary scalars checked by independent binary multiplication. The native
retained-byte count includes digit points, terminal points, residue tables,
and structure metadata. The [validation receipt](validation.json) pins the
source and binaries used for these checks.

The frozen case-0 operation profile records 17 nontrivial mixed additions,
two projective joins, two bucket `x` multiplications, 19 digit point reads,
and one terminal point read. The norm-4,831 three-bucket case-0 profile
recorded 18 mixed additions with the same two joins and two bucket
multiplications. The [case-0 log](native-case0.log) is a local operation
diagnostic; its CPU interval is exploratory under the repository's tier gate.

Reproduce the integer screen from the repository root:

```sh
python3 experiments/prime-j0-split-prime-8011-20261014/screen.py
```

The three Lean modules import the pinned `SplitPrimeLatticeCell` and
`SplitPrimeNormBound` modules from the parent experiment. Build them in
dependency order with Lean 4.34.1 and a `LEAN_PATH` containing those compiled
imports. To reproduce the native check, generate the parent three-bucket
Cargo source with its documented command, apply `native_overlay.py` to that
Cargo directory, then run:

```sh
CARGO_TARGET_DIR=/private/tmp/prime-j0-split-prime-8011-target cargo test \
  --manifest-path /private/tmp/prime-j0-split-prime-8011-native/Cargo.toml \
  --offline --locked --release --bin eisenstein_fixed split_prime_ \
  -- --test-threads=1 --nocapture
```

For CPU latency, use the [tier contract](../../docs/IC_BENCHMARK_TIERS.md)
and a frozen same-scalar panel with an A/A calibration. The previous RunPod
allocation's calibrated case-8 panel failed its frozen noise gate; retain
that receipt and use a fresh allocation for a qualified new panel.

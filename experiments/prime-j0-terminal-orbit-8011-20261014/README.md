# Unit-orbit terminal table for the 19-position norm-8011 multiplier

The terminal table now stores one affine point for each of the 1,280 unit
orbits in the proved `N(z₁₉)<46²` ball. A 16-bit map resolves each of the
3,838 sign-canonical terminal pairs to an orbit point and a unit action. The
retained table drops from **1,919,146 to 1,763,126 bytes**, saving **156,020
bytes (8.13%)** while retaining 19 digit positions. On frozen scalar case 0,
the operation profile remains 17 nontrivial mixed additions, two projective
joins, and two bucket rotations. These are exact storage and operation counts;
the local timing field is an exploratory diagnostic.

## Construction

The ring coordinates use `τ²=3τ−3`, norm `N(a+bτ)=a²+3ab+3b²`, and the order-3
unit action `ω(a,b)=(a+3b,−a−2b)`. The six images are `±z`, `±ωz`, and
`±ω²z`. For every nonzero terminal pair, three images are sign-canonical
(`a>0` or `a=0,b≥0`). The builder chooses the lexicographically first such
image as the orbit representative and stores one affine point. A table code
`6·orbit_index+unit` maps each sign-canonical pair to the stored point and
one of the six images. The runtime combines this unit with the sign of the
actual terminal pair and inserts it into the existing three digit buckets
before their final joins. Zero keeps a dedicated index and is not read as a
curve point.

The full terminal ball has 7,675 integer pairs. Its 7,674 nonzero pairs form
1,279 six-element orbits, plus zero, giving 1,280 stored affine points.
The native exhaustive map test verifies all 3,838 sign-canonical pairs and
their recovered unit image. The [Lean module](TerminalOrbit8011.lean) proves
that `ω³=1`, each unit preserves the norm, and all six images of a nonzero
pair are distinct. The exact finite pair and orbit counts are checked by the
native constructor and exhaustive test; they are not separate Lean theorems.

| Result | Lean declaration | Verification |
| --- | --- | --- |
| Order-3 action | `TerminalOrbit8011.omega_cube` | Lean 4.34.1 checked. |
| Norm preservation | `omega_preserves_norm`, `neg_preserves_norm`, `unit_preserves_norm` | Lean checked. |
| Six distinct nonzero images | `unit_images_distinct` | Lean checked for all integer pairs and six unit indices. |
| Terminal map and curve action | No field-level Lean bridge | Exhaustive native map check; 128 frozen and 518 additional scalars independently replayed. |

The [Lean log](lean-check.log) includes `#print axioms`: only `propext`,
`Classical.choice`, and `Quot.sound` appear. The source and compiled theorem
hashes are frozen in [validation.json](validation.json). `lean4checker --fresh`
was unavailable on this host.

## Reproduction and evidence

Start from the generated norm-8011 Cargo directory pinned by the parent
[experiment](../prime-j0-split-prime-8011-20261014/README.md), then run:

```sh
python3 experiments/prime-j0-terminal-orbit-8011-20261014/native_overlay.py \
  /private/tmp/prime-j0-terminal-orbit-8011-native
CARGO_TARGET_DIR=/private/tmp/prime-j0-split-prime-8011-target cargo test \
  --manifest-path /private/tmp/prime-j0-terminal-orbit-8011-native/Cargo.toml \
  --offline --locked --release --bin eisenstein_fixed split_prime_ \
  -- --test-threads=1 --nocapture
```

The overlay checks the exact SHA-256 of its input source and fails if it is
applied to a different generated module. [Native test output](native-test.log)
records five passing test families: all 8,011 residues, 72,099 quotient
cases, 3,838 terminal pairs, 152,304 digit unit images, and 646 scalar
replays. [Case-0 output](native-case0.log) records the independent scalar
check and exact operation profile. The native binaries and generated source
are hash-pinned in [validation.json](validation.json).

The next measurement is a serialized Tier 1 same-scalar panel against the
unfolded norm-8011 table, with A/A calibration and preserved noisy pairs.
The RunPod allocation request on 2026-10-14 was rejected because the account
balance was too low; no cloud timing result was produced from that attempt.

# Thirteen-window asymmetric radix-944 tau format

This experiment constructs a fixed-generator secp256k1 scalar format with
thirteen radix-944 Eisenstein windows. The first twelve use digit norm bound
`944²`; the final window uses `550²`. Each residue selects a six-unit image
of a seed point or its degree-three tau image. The evaluator accumulates two
tau buckets and combines them as `B0 + tau(B1)`.

The asymmetric bound spends the norm budget where it reduces table storage:
an early digit contributes only `944^i` to the termination inequality, while
the final digit contributes `944^12`. A preliminary exact cycle screen found
74,263 full-row seeds and 102,797 final-row seeds, giving 993,953 stored
affine point slots and 63,612,992 bytes of 64-byte point payload. These
figures are design targets until the generator and independent replay below
produce source-bound receipts.

## Mathematical gate

Use the certified nearest Eisenstein pair `z0=(a,b)` for each reduced scalar,
with `3N(z0) <= n`, where `N(a,b)=a²+3ab+3b²` and `n` is the secp256k1
subgroup order. Let `R=944`, `L=13`, `D_i=944` for `i<12`, and `D_12=550`.
The atlas must select `d_i ≡ z_i (mod R)` with `N(d_i) <= D_i²`. The exact
quotient recurrence is `z_(i+1)=(z_i-d_i)/R`. Define

`P=R^13`, `S=sum_(i=0)^12 D_i R^i`.

The generator must prove by integer arithmetic that `3(P-S)²>n` and that
raising the final bound from 550 to 551 reverses this sufficient test. The
norm triangle inequality then gives `N(z_13)<1`, hence `z_13=(0,0)` for
every certified input pair. This is a complete scalar-reconstruction
certificate for the declared digit bounds.

Because `gcd(R,3)=1`, tau permutes the residue classes modulo `R` after
six-unit folding. The generator must enumerate all `R²=891,136` residues,
construct the exact unit classes and tau cycles, and use the circular
one-or-two-class dynamic program to minimize the number of seed points
within the nearest-digit alphabet. It must check each decoded residue for
congruence, bound, unit code, tau exponent, and unique table index. It must
record the atlas hashes, cycle histogram, seed counts, and maximum decoded
norm. A separate verifier must replay the binary atlases without trusting
the generator's in-memory assignment.

## Group and implementation gates

Freeze the generator, proof and binary atlases before drawing a disjoint
full-range scalar panel. Reconstruct every scalar from its digits, then
check per-term bucket evaluation, grouped-unit gauge evaluation, and an
independent binary scalar multiplication on the same public generator.
Preserve all input, source and output hashes. Compare against the frozen
fourteen-window mixed-radix-640 candidate on the identical scalar panel.

Only after the group replay passes, materialize a separate native candidate
without editing the shared evaluator files reserved by Conductor task T-546.
Native tests must verify atlas points and the same scalar panel, record
retained bytes and complete operation counts, and keep the recoding cost
separate from point-kernel counts. A Linux correctness replay may use the
existing serial RunPod queue. Any CPU wall-time comparison requires the
host-level isolation receipt specified in `docs/ISOLATED_BENCHMARKS.md`.

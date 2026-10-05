# Sign-folded, packed two-digit τ-tail policy

## Construction

The [two-digit pair policy](TAIL_DOUBLE_PAIR.md) stores one two-byte action
and one gate bit for each of 49,923 bounded `(a,b,phase)` states. Its active
policy data is 106,087 bytes. The exact state transition and frozen evaluation
score are invariant under simultaneous sign change: if action
`(d_even,d_odd)` takes `z` to `q`, then `(-d_even,-d_odd)` takes `-z` to `-q`
with the same number of triples, additions, and unit rotations. The
`[-64,64]²` state bound is also invariant. The generator checks equal optimal
costs and equal canonical-gate bits at every state and its negative.

The folded policy stores only states with `a>0` or `a=0,b>=0`, 8,321 per
phase. Each phase has a dictionary of its actually selected pair actions;
the largest dictionary has 585 entries. A 10-bit index per folded state
selects the phase-local action, followed by an 81-byte digit-negation map
when the input state lies in the other half-plane. The 10-bit stream includes
two zero padding bytes for safe three-byte reads at the end. The active data
is 31,206 packed-index bytes, 3,510 dictionary bytes, 3,121 gate bytes, and
81 negation bytes: **37,918 bytes total**, a reduction of 68,169 bytes
(64.3%) from the prior policy. The implementation exposes this count through
`ca_ec_tau4_fold_static_bytes()` using the actual C array sizes.

The original table's lexicographic tie rule is not sign equivariant: 7,013
mirrored states choose a different equal-cost action in the folded policy.
The generator decodes all 49,923 folded/mirrored states and checks each
action's exact integral successor, strict cost descent, statewise optimal
cost identity, and gate equality. This establishes the same modeled
evaluation score; it does not establish equal recoding time or CPU speed.
`tail-double-fold` is therefore a separate opt-in public-scalar research arm.
Its scalar-dependent branches and memory accesses are unsuitable for secret
scalars without a separate side-channel design and review.

## Residue-local byte format

For any state `a+bτ`, an action's admissibility is constrained by
`(a mod 3,b mod 3)`. Partitioning each phase's selected actions by these nine
residue classes leaves at most **96 actions in any class**. The
`tail-double-residue` arm stores one byte per sign-folded state and selects a
small dictionary using its normalized state's phase and residue. Its active
data is 24,963 code bytes, 3,414 action-dictionary bytes, 3,121 gate bytes,
81 digit-negation bytes, 54 dictionary-offset bytes, and 27 dictionary-length
bytes: **31,660 bytes total**. That is 74,427 bytes (70.2%) less than the
original two-digit policy and 6,258 bytes less than the 10-bit folded arm.
The count lies below a 32 KiB L1 data-cache capacity, but other live data
also occupies cache and actual cache behavior must be measured.

The residue generator repeats the exhaustive 49,923-state sign/gate and
shortest-path proof with its own byte decoder. This is a second encoding of
the same optimal policy and keeps the 10-bit arm available for paired timing:
the byte lookup saves bit unpacking but adds two modulo-three operations and
one dictionary offset lookup per selected pair.

## Regression receipt

The [regression receipt](tail-double-fold-regression.json) replays all three
two-digit arms on the eight previously frozen `tail-double-inputs.json`
cases. All 32,768 scalar-point outputs match the generic output digests.
Each new-arm scalar passes an independent digit-reconstruction check and a
modeled-cost equality check against the unfurled arm outside the online
interval. Every case has identical aggregate triples, mixed additions,
rotations, and weighted evaluation score. The direct curve test passes
2,281,596 checks. These are **regression inputs already used by the parent
experiment**, not fresh held-out evidence for a CPU speedup. The local
macOS timings in the receipt are exploratory because the host lacks the
required isolation record.

The [isolated benchmark service](../../docs/ISOLATED_BENCHMARKS.md) can pair
`tail-double-fold` or `tail-double-residue` with `tail-double` on the same
inputs using `make_isolated_manifest.py --candidate-arm
tail-double-residue --reference-arm tail-double`. The timed interval includes
the folded lookup, sign transform,
recoding, curve operations, and output conversion. A CPU wall-time result
requires a host-level isolation receipt and noise gates; no such run has
been completed. The benchmark binary retains all three research arms, so the
`static_map_bytes` field describes the *active arm's policy data*, not total
binary `.rodata`. A deployment wanting the smaller binary should compile
out the old arm and verify the linked section size separately.

This is an implementation compression of the prior shortest-path scheme.
It does not prove a new academic scalar-multiplication algorithm, and it does
not imply an end-to-end Pollard-rho speedup. Rho's repeated walk steps use
point additions; scalar multiplication matters primarily at setup and
restart boundaries.

## Reproduction

```sh
python3 experiments/prime-j0-cost-aware-chain/make_tau_tail_double_fold.py
python3 experiments/prime-j0-cost-aware-chain/make_tau_tail_double_residue.py
cmake --build build-cost-aware --target test_curve ca_tau_chain_bench -j 4
./build-cost-aware/test_curve
python3 experiments/prime-j0-cost-aware-chain/check_tail_double_fold.py \
  --bench build-cost-aware/ca_tau_chain_bench
```

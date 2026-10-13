# N83 rectangle width-14 base: exact high-bit translation screen

The [8,532-column rectangle base](../n83-geometric-rectangle14-20261012/README.md)
is a strict local maximum under every **single high normal-basis bit
translation**. The best of the 71 translated affine planes, at bit 58,
has only **8,347 rational `x` lifts**. Every folded subgroup orbit
column needs at least one rational lift, so none of those translations
can match the original 8,532 columns. This closes the one-bit shift
neighborhood of the certified rectangle without spending time on
71 full curve-orbit scans.

The [protocol](protocol.json) pins the exact rectangle basis and key
receipt, normal-basis bridge, curve implementation hashes, and all
translation bits `12..82`. The [screen](screen.json) retains every
exact lift count and the descending branch-and-bound rule. The next
scores are 8,342 at bit 43 and 8,331 at bit 32. The baseline key
bytes are copied to [best_keys.bin](best_keys.bin) with the original
digest; no translated base exceeded the baseline, so no translated
orbit set was promoted. `candidate_id` stays null for this geometric
screen.

The checked [Sage runtime identity](sage_runtime_info.json) was saved
before the screen. The [independent Sage replay](independent_sage_replay.json)
recomputes all `71*16,384` rationality tests in a separate loop with
per-element inverses and matches every count. The
[read-only verifier](verify.py) audits source/input hashes, all rows,
baseline key bytes, and the independent replay:

```sh
python3 experiments/n83-geometric-rectangle14-translates-20261012/verify.py
```

The conditional implication from the 8,347 lift bound to strict
column inferiority is checked in [TranslateBound.lean](TranslateBound.lean)
with the pinned [Lean toolchain](lean-toolchain), and the
[axiom audit](lean-build.txt) reports no axioms. The finite-field
screen and the curve-orbit cardinality bridge are computationally
replayed; their Lean formalization is partial. The local screen wall
time is an exploratory shared-host diagnostic.

Two-bit translations or changed basis directions are the next
geometry families. Their value to the complete IC pipeline must be
assessed through ordinary-query relation yield, useful rank, final
linear algebra, target descent, and the same-point rho comparison.

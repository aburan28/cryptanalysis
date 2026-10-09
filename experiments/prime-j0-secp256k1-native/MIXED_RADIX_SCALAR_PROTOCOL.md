# Conditional radix-two exits from a τ-adic scalar stream

Freeze `mixed_radix_scalar.py`, this protocol, and
`make_mixed_radix_fixture.py` before generating the new 256-case Sage
panel. The original 64 cases are design data. The selective and
portfolio holdouts have already been inspected and cannot serve as
fresh evidence for this candidate.

For a short Eisenstein representative `z=a+bτ`, greedily divide by
two with a zero digit whenever both `a` and `b` are even. Otherwise,
take the **original width-four τ digit** and divide `(z−d)` by τ.
Retain the exact radix/digit action stream, detect a repeated state,
and cap the length at 512. Reconstruct the starting `(a,b)` by
reversing the mixed action stream.

For evaluation, apply each stored radix to the accumulator and add
its digit. A radix-two action doubles the accumulator; a τ action
uses the existing τ map. Fuse two adjacent τ actions when the higher
action's digit is zero, charging `10 M+S` instead of two six-unit τ
steps. Intervening doubles forbid such a pair. Reuse the original
nine-seed table, its 83-unit preparation cost, and cached projective
addition model. Count every double, τ step/pair, mixed/general digit
addition, and cache entry. Compare the **complete** greedy mixed path
with the existing selective mixed-alphabet path on each scalar; choose
the lower source count, with ties selecting the existing path. This
pairwise choice adds recoder CPU work that the source model omits.

On the original design data, report every failed/cyclic/timeout path,
the greedy and selected complete source costs, per-case choices, and
digit/action digests. After the code is frozen, generate eight new
bases with 32 deterministic scalars each under a distinct label.
Use the checked repository Sage launcher, save `--runtime-info`
before Sage jobs, and replay each selected point stream independently
against the known scalar output. A new source-count win is only an
algorithmic result. A native full-operation path and physical-host
isolation receipt are required before any CPU speedup claim. Mixed
radix and endomorphism chains have prior art; academic novelty is
unproved.

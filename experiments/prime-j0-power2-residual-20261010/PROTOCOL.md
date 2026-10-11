# Twelve shift windows with an exact terminal Eisenstein residual

This experiment constructs a fixed-generator secp256k1 scalar format. It
uses twelve radix-1024 Eisenstein digits, then indexes the **bounded integer
residual** directly. The quotient updates are signed shifts. The terminal
lookup covers a finite norm disk rather than all residues modulo 1024.
Six-unit and optional degree-three tau images share one stored seed point;
evaluation uses two tau buckets and grouped-unit gauge.

An exact preliminary screen found 87,383 seeds for the full radix-1024
atlas and 10,061 seeds for the terminal disk. Twelve full rows plus one
terminal row would retain 1,058,657 affine slots, with 67,754,048 bytes of
64-byte point payload. These are design figures until construction and an
independent verifier produce source-bound receipts.

## Mathematical gate

For the certified nearest Eisenstein representative `z0`, require
`3N(z0) <= n`, where `N(a,b)=a²+3ab+3b²` and `n` is the secp256k1 subgroup
order. Every full-window atlas code must select `d_i ≡ z_i (mod 1024)`
with `N(d_i) <= 1024²`, and set `z_(i+1)=(z_i-d_i)/1024` for `0<=i<12`.
Let `P=1024^12` and `S=sum_(i=0)^11 1024^(i+1)`. The generator must check
the exact integer inequalities

`3(149P-S)² > n` and `3(148P-S)² <= n`.

The norm triangle inequality then proves `N(z12)<149²` for every certified
input. The terminal atlas must enumerate **every integer pair** in that
open norm disk and decode it exactly, without reducing either coordinate
modulo a radix. It must record the pair count, six-unit classes, tau edges,
chain lengths, seed count, code encoding, and binary hashes. An independent
verifier must re-enumerate the disk and certify both coverage and minimum
seed count for the declared one-seed-or-tau-image construction.

Tau triples the norm. On the finite disk its directed class graph has
indegree and outdegree at most one, with no nonzero cycles; it is a set of
chains. A seed can cover its unit class and the next class if the tau image
remains in the disk. A chain of length `L` therefore requires at least
`ceil(L/2)` seeds, attained by pairing adjacent classes. The identity has
one explicit zero code. The verifier must check this lower bound and the
actual seed assignment independently of the generator.

## Group and implementation gates

Freeze the generator, proof, atlas bytes, and independent atlas verifier
before drawing a deterministic, full-range scalar panel disjoint from the
radix-944 panel. On that new panel, reconstruct every scalar and compare
termwise group sums, two-bucket evaluation, grouped gauge, and independent
binary scalar multiplication. Pair the native radix-944 control on the same
scalars. Preserve raw failures and exact input/source/output hashes.

Only after the group replay passes, materialize a separate native mode in
a source-pinned crate. The shared evaluator is reserved by Conductor task
T-546. Verify terminal table points, both atlas decoders, boundary scalars,
and the same frozen panel. Count complete point-kernel operations and the
recoder/table traffic separately. Linux replay may enter the existing
single-job RunPod queue. A CPU wall-time comparison requires the host-level
isolation receipt in `docs/ISOLATED_BENCHMARKS.md`; a contended host is a
correctness and operation-count diagnostic only.

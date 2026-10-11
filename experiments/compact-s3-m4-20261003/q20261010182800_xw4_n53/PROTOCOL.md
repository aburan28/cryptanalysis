# Q20261010182800: exact N53 x-weight-four base

Enumerate all nonzero normal-basis x coordinates of weight at most four
on `EC1N53Ckb1hf77aab617904`. Work once per full 53-element Frobenius
orbit; lift rational x to the curve, project by the exact cofactor 428,
discard identity, and key the projected subgroup point by the minimum
normal-basis x coordinate in its Frobenius orbit. Both signs and all
Frobenius conjugates expand each key. Record the actual point count
`B=2*53*K`, folded columns `K`, nominal masks, per-weight counts, packed
seven-byte key digest, and exploratory enumeration cost.

The weight-three prefix must reproduce Q1410's exact enumerated-set
digest, `B=24,062`, and `K=227`. The independent auditor recomputes the
weight-four key set using the other curve lift, a separate mask rotation,
and full subgroup/Frobenius checks. The ordinary public target and input
law for the following solver cell are Q1410's `W74f2979b3e68`; no pinning
is used. This is a Q proposal with null IC candidate/run IDs and `ISO0`.

Run `python3 base.py freeze`, `python3 base.py run`, then `python3 audit.py`.
Outputs refuse overwrite.

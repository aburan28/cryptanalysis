# On-demand adjacent-pair dictionary screen

This retrospective screen asks whether a one-use base/scalar benefits
from constructing a small dictionary of **actual** adjacent nonzero
τ-digit pairs, rather than a full positional table.  It reads the
existing 64-base native fixture; no new target inputs or speed selection
are made.  The script reconstructs every short coefficient from the
frozen digit stream before counting pairs.

In highest-to-lowest nonzero order, group disjoint neighboring digits
using either offset zero or one.  For a high digit `d_i` and low digit
`d_j`, the pair contribution at position `j` is `τ^(i−j)d_i+d_j`.
Canonicalize the contribution under the six sign/ω units.  Within
each base, count each canonical point that occurs more than once;
points from different bases cannot share a one-use point table.  Also
check whether any pair is already one of the nine prepared seed orbits.
Choose the better of the two offsets per base as an optimistic upper
bound on reuse; the script does not claim that a complete evaluator can
select both offsets without extra work.

For a repeated pair used `c` times, constructing it once with one
same-cost group addition and using it once per occurrence could save
at most `c−1` additions.  This ignores the τ-scaling needed to form the
pair, cache/table work, exceptional cases, and differences between
mixed and projective addition costs.  Charge 14 `M+S` per saved
addition only as a generous ceiling.  One-use pairs cannot amortize
their preparation addition in this equal-cost model.  This screen
cannot establish CPU performance or academic novelty.

Run with ordinary Python; no Sage job is launched:

```sh
python3 experiments/prime-j0-secp256k1-native/pair_reuse_screen.py
```

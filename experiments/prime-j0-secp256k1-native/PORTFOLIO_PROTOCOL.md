# Bounded-carry atlas portfolio gate

Freeze `atlas_portfolio.py`, this protocol, and
`make_portfolio_fixture.py` before generating the new 256-case Sage
panel. The original 64-case panel and earlier linked 256-case panel
are design data. The new panel has a distinct deterministic scalar
label and is held out from the choice of the three table candidates.

Compute the baseline width-four τ expansion once, retaining each
coefficient state's residues modulo 9. Translate that expansion into
the two-orbit and three-orbit atlas expansions by a carry recurrence:

`c_(i+1) = (d_i + c_i - e_i)/τ`, with `c_0=0`, where `d_i` is the
baseline digit and `e_i` is the alternate table's digit selected from
the stored baseline residue plus `c_i`. When the carry is zero and the
baseline digit's seed is unchanged in the alternate table, copy the
digit without table lookup. After the baseline expansion ends,
recode the remaining carry with the alternate table. Verify that the
translated digits exactly match a fresh direct alternate recoding and
reconstruct the original `a+bτ` value on every case.

All three tables have maximum digit norm `D=112`. For a carry `c`,
`N(c_next) <= (sqrt(N(c))+2 sqrt(D))²/3`. The ball `N(c)<=8D=896`
is invariant because `(sqrt(8)+2)² < 24`. Verify this bound on each
observed carry; the algebra proves it for every input. Each alternate
digit table has already passed an all-state termination audit, so the
finite tail terminates after the baseline stream ends.

Score the exact one-use source count for each full stream, including
83, 79, or 75 units of seed/orbit preparation respectively. Choose the
least costly, breaking ties in baseline, two-orbit, three-orbit order.
Retain per-case costs, choices, carry work, failures, source hashes,
and new held-out outcomes. This is an exact source-count selector;
its translation/selection CPU cost, lattice reduction, and final
inversion are not in the source count. Do not claim a CPU speedup
without a paired full-operation isolated-host receipt. The prior-art
record must note that finite transducers for τ-adic NAFs are known;
academic novelty is unproved.

# Mixed-alphabet τ digits: bounded design-data screen

The original, two-orbit, and linked three-orbit atlases offer two
different coefficient digits in each of three residue orbits. A mixed
alphabet could choose the better digit independently at each position
instead of committing to one complete table. The resulting carry must
still reconstruct the original `a+bτ` representative.

`mixed_atlas_screen.py` explores this option on the **original 64-case
design panel only**. At each baseline residue and bounded carry it
offers every distinct digit in the three saved tables, then applies
`c_(i+1)=(d_i+c_i-e_i)/τ`. The carry norm is checked against 896.
The search retains the cheapest path for each carry, previous nonzero
position and seed, and used-cache mask. Its transition cost exactly
recreates the evaluator's `6` per τ step, `−2` for a paired stride,
`11` or `14` per charged digit addition, and `2` per newly cached
projective seed. It runs the original baseline length plus **16 carry
tail positions**; the result is optimal within that finite horizon
and this fixed 12-orbit alphabet. A linked-only restriction reproduces
the independent **88,089-unit** linked total on all 64 inputs, checking
the dynamic program's accounting.

Preparing all 12 seed orbits costs **107 `M+S` per scalar** in the
existing graph: the linked nine-orbit chain costs 75, the three
original seed points require two mixed additions and one doubling
(`11+11+7`), and their three additional orbit images cost one unit
each. This full-union cost is charged to every scalar, regardless of
which seed digits the chosen stream actually uses.

| Original design panel | Cases | Complete `M+S` |
| --- | ---: | ---: |
| Fixed linked atlas | 64 | 88,089 |
| Existing three-table selector | 64 | **87,632** |
| Mixed 12-orbit alphabet, full-union preparation | 64 | 88,540 |

The mixed alphabet improves on the selector in 9 cases, ties in 2,
and costs more in 53; in total it costs **908 additional source-count
units**. `mixed-atlas-design-result.json` retains every row and
source/input hashes. This is an exploratory design screen, not a
held-out result. It disfavors **always preparing the full union**;
selective seed preparation, another alphabet, or a longer carry tail
remain separate designs. Its search and extra precomputation CPU costs
are not charged by this source count. There is no isolated CPU timing
or academic novelty claim.

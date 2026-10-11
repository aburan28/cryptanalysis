# 64 MiB budget-optimal tau cover

The radix-1024 secp256k1 fixed-generator multiplier has a tau-only cover
with **83,878 full-window seeds and 7,010 tau-squared classes**. This
attains the exact class-count lower bound for the declared 64 MiB retained
table format. The construction reties the exact-size cover to expose
11,634 adjacent triple pairs and applies 10,461 `3+3 -> 2+2+2`
replacements. The [proof](PROOF.md) gives the lower bound and construction.

The [independent cover check](check.json) verifies 174,764 classes and all
1,048,576 residues. The [native atlas check](native-atlas-check.json)
independently verifies the reindexed `DR20` table and inverse unit
transforms over the same residue space. The full atlas is 1,733,640 bytes;
the projected native retained footprint is **67,108,820 bytes**, leaving
44 bytes of the 64 MiB budget. The frozen fresh panel and native point
replay are the next measurement step under [the protocol](PROTOCOL.md).

The first frozen panel is retained as a source-binding preflight. Its path
and independent checks passed, while `phase_cost.py` exposed a stale key
before phase counts could be produced. The corrected source is frozen
again before drawing the final panel, which excludes those preflight
scalars.

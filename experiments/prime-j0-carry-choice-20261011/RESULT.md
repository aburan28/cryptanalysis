# Carry-aware alternate digit screen

The direct-index seed table admits two norm-bounded tau
representations for 39,614 of its 174,764 full-residue unit classes.
A second three-byte code for each such class would require 118,842
additional bytes and no new point-table slots. The
[screen](screen.py) checks every alternate digit's residue and norm,
then enumerates valid carry paths on the previously frozen
4,096-scalar design panel.

| Search range | Valid full paths | Mixed additions | Outer tau images | Gauge rotations |
| --- | ---: | ---: | ---: | ---: |
| Existing single-code policy | 4,096 | 49,152 | 6,384 | 16,539 |
| Branch in last six windows | 13,961 | 49,152 | 6,375 | 16,136 |
| Branch in all twelve windows | 48,784 | 49,152 | 6,363 | 15,620 |

The [last-six](screen-w6.json) and [all-window](screen-w0.json)
receipts contain the input and atlas hashes, search counts, and
addition-saving histograms. Both histograms assign all 4,096 scalars
to **zero mixed additions saved**. The all-window row is an oracle
bound: it chooses the best valid path after exploring 239,164 partial
states, without charging that search or the extra atlas accesses.
The gauge count alone does not justify promoting this representation
choice to a native scalar mode. The next candidate instead uses the
direct index's spare memory for a fused digit-and-point code that can
remove runtime seed lookup and tau-digit reconstruction.

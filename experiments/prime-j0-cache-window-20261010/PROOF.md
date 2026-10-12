# Reconstruction and exact table sizes for narrower windows

The mode 131 schedule has six width-8 and nine width-9 windows:
`6*8+9*9=129`. Mode 132 has fifteen width-8 and one width-9
window: `15*8+9=129`. Both use the same canonical six-unit orbit
rule and nearest signed digit as mode 130. The canonical-sector
inequalities in the [mode 130 proof](../prime-j0-sector-digit-20261010/PROOF.md)
hold for radix 256 as well: `256=3*85+1`. Its intervals contain
10,924 orbit representatives, including the identity; the
four-corner tie rule has 43 equal-norm canonical cases.

For a schedule with widths `w_i`, set `B_i=2^w_i` and
`s_i=sum_{j<i} w_j`. At step `i`, choose a digit `d_i` congruent to
the current Eisenstein representative `z_i` modulo `B_i`, then set
`z_{i+1}=(z_i-d_i)/B_i`. Induction gives

`z_0 = sum_i 2^{s_i} d_i + 2^129 z_final`.

The certified starting representative has norm at most `n/3`, with
`n<2^256`. Every selected nearest digit has norm at most `B_i²/3`,
so `||z_{i+1}|| <= ||z_i||/B_i + 1/sqrt(3)`. Since every
`B_i>=256` and their product is `2^129`, the final norm radius is

`||z_final|| < 1/(2*sqrt(3)) + 256/(255*sqrt(3)) < 1`.

Every nonzero Eisenstein integer has norm at least one, so
`z_final=0`. The precomputed point in window `i` is
`[2^{s_i} d_i^0]G` for the canonical digit `d_i^0`; applying the
selected unit gives `[2^{s_i} d_i]G`. Summing the selected points
therefore equals `[k]G` for the original scalar congruence.

The six-unit orbit count for even radix `B` is `(B²+8)/6`, giving
10,924, 43,692, and 174,764 entries for width 8, 9, and 10.
The predicted point-only allocations, using 64 bytes per affine
point plus the existing 32-byte table struct and 16 bytes per window
descriptor, are:

| Mode | Windows | Point slots | Retained bytes | Maximum mixed additions |
| --- | ---: | ---: | ---: | ---: |
| 130, U14 | 14 | 1,004,904 | 64,314,112 | 13 |
| 131, U15 | 15 | 458,772 | 29,361,680 | 14 |
| 132, U16 | 16 | 207,552 | 13,283,616 | 15 |

The implementation must report these exact retained allocations and
verify the independently built point tables. The table-size saving
does not establish an online speedup; each extra selected point adds
curve work, and actual cache behavior belongs to the isolated panel.

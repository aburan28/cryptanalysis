# Variable-width two-bucket tau frontier

Enumerate 16–19 fixed-base windows of widths 6–9. The first `W-1`
windows use the full radix as their norm-length limit. The final window
uses the largest integer limit satisfying the exact sufficient
termination inequality. For each multiset of nonfinal widths, order them
ascending; an adjacent swap shows that this minimizes the weighted digit
sum while preserving the radix product. Retain only layouts whose final
limit covers every direct nearest residue digit. The objective is point
payload bytes plus one 32-bit-code atlas per distinct `(width,limit)`.
Track point slots and atlas bytes separately. This is a constrained
storage screen, not an online timing measurement.

For the best 17-, 18-, and 19-window layouts, construct all distinct
atlases with the exact cycle-cover algorithm in the frozen power16
screen. Exhaustively decode every residue and check its norm. Recode
both prior frozen 4,096-scalar panels and check the final quotient is
zero. Independently replay group arithmetic on the selected 17-window
layout before native integration.

Native implementations will compare the selected layouts on one
frozen 4,096-scalar panel drawn only after code and atlas freeze.
Check all selected native table points against independent group sums,
all new scalar points against the existing 16-window implementation,
the first 128 against binary multiplication, fixed fixtures, and the
release suite. Timing requires the isolated CPU receipt in
`docs/ISOLATED_BENCHMARKS.md`, with full bucket and inversion cost.

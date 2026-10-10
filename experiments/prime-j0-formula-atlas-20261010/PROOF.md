# Correctness of the point-only U14 table

Let `m=2^w`, with `w=9` or `10`, and let the input residue pair be
`R=(a,b)`. The three powers of the order-three unit action have pair
coordinates

`R`, `(a+3b,-a-2b)`, and `(-2a-3b,a+b)` modulo `m`.

Negating each gives the other three members of the six-unit orbit.
Because `m` is a power of two, masking an integer by `m-1` computes
its residue modulo `m`, including for negative integers in two's
complement arithmetic. Mode 129 selects the least pair among the six
and the least inverse unit code on ties. These are the canonical-pair
and fixed-point conventions of mode 128's arithmetic atlas.

The [mode 128 orbit-rank formula](../prime-j0-arithmetic-atlas-20261010/PROOF.md)
returns the stored point-table position of that canonical pair. Mode
129 then applies the same four-corner `nearest_digit` routine to the
canonical pair that mode 128 ran during table preparation. Its digit
array merely cached this deterministic result. Applying the chosen
unit code to the computed digit therefore gives exactly the old
signed digit and the same quotient for the next window. Induction over
the fourteen windows gives the same choice sequence and selected
affine points. The grouped gauge evaluator is shared by both modes,
so its additions and final point are the same.

During preparation, mode 129 constructs the same canonical digit
arrays temporarily and passes them to the same point-window builder.
It drops the arrays before online evaluation. The retained table has
only the affine windows, their vector descriptors, and a byte count.
The native test compares digit, orbit ID, and unit code for all
`512²+1024²=1,310,720` supported residues; a second test compares
all independently built affine table entries and new scalar outputs.
These finite-domain checks cover the exact radices and table data used
by this implementation.

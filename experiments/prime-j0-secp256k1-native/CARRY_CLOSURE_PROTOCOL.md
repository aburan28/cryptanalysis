# Selective mixed τ carry closure

Before changing the native state representation, exhaustively explore the
carry recurrence for the fixed original and linked width-four tables.
Start with carry `(0,0)`. For each reached carry, permit **all 81**
possible original input residues `(a mod 9,b mod 9)`, take the original
table's digit for that residue, and try every mixed-alphabet digit at
the shifted residue. The transition is

`c' = (d_original + c - d_offered)/τ`, with
`(x+yτ)/τ = (x+y, -x/3)` when `x` is divisible by three.

Repeat until the reached set stops growing. Since every possible
input-residue sequence is allowed, a finite closure bounds every
actual selective recoding path, including all future scalar inputs.
Record the closure size, maximum Eisenstein norm and coordinate,
generations, exact state-set digest, source hashes, and failed
assertions. If the maximum coordinate fits in signed eight bits, the
native selector may store both carry coordinates as `i8` after a checked
conversion. Re-run its independent Sage/native fixtures. This changes
search storage only; it does not change the digit alphabet, scoring,
preparation, or scalar result. CPU timing remains unknown until a
physical-host isolated full-operation comparison.

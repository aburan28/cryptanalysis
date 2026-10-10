# Arithmetic rank of the six-unit U14 orbit

The digit lattice represents a residue pair `(a,b)` modulo `m=2^w`.
The order-three action is

`omega(a,b) = (a+3b, -a-2b) (mod m)`.

Together with negation it gives six actions, coded `2e+s` for power
`e=0,1,2` and sign `s=0,1`. The stored atlas visits residue pairs in
lexicographic order, assigns each orbit to its first pair, and stores the
first action code that maps this representative to each residue. Since
`m` is a power of two, the only orbit sizes are six, three, and one;
the three nonzero two-torsion residues form the size-three orbit. Burnside
counting gives `(m²+8)/6` orbits.

Let `m=3q+r`, where `r` is one or two. Direct comparison of each pair
with its five images places lexicographically first representatives in
row zero at `b=0..m/2`. For `1<=a<=q`, the allowed `b` values are the
three intervals specified in [the protocol](PROTOCOL.md). There are no
representatives in later rows. Row `a` has `3(q-a)+r` representatives;
the prefix before that row is

`m/2+1 + (a-1)m - 3(a-1)a/2`.

Adding the number of values in earlier intervals and the offset within
the current interval gives the orbit ID. The implementation evaluates
the six images of an input pair and takes the least pair. If several
actions reach it, it chooses the least inverse code. This is the stored
atlas's tie rule for the identity and two-torsion orbit. Applying the
chosen code to the canonical digit yields the same signed digit as the
stored-code evaluator. Consequently the recursive quotients, all later
window choices, and the fourteen selected points are identical.

The native exhaustive check constructs both atlases independently and
compares digit, orbit ID, and unit code for every one of the
`512²+1024²=1,310,720` residues used by U14. It also compares the
two separately built affine point tables entry by entry. These are
finite-domain correctness certificates for the exact supported widths;
the generated holdout and fixture runs test the complete scalar path.

The arithmetic format retains the same canonical digits and affine
point table but removes four bytes for each of the `512²+1024²`
residues: `5,242,880` bytes. The smaller atlas struct accounts for a
further 72 bytes, making the exact retained-byte reduction `5,242,952`.
The online tradeoff is six small integer transforms and a rank formula
per nonzero digit in place of one random residue-code load. A controlled
CPU comparison must measure that tradeoff on an isolated host.

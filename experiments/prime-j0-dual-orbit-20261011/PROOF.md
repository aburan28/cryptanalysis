# Endomorphism tags on the Eisenstein residue cover

Write a scalar representative as `a + b*tau`, with `tau^2 = 3*tau - 3`
and norm `N(a,b) = a^2 + 3ab + 3b^2`. The existing map is
`tau(a,b) = (-3b, a+3b)` and has norm three. Two split norm-seven
endomorphisms are

`rho = 1+tau`, so `rho(a,b) = (a-3b, a+4b)`, and

`rho_bar = 4-tau`, so `rho_bar(a,b) = (4a+3b, -a+b)`.

Direct substitution gives `N(rho z) = N(rho_bar z) = 7N(z)`. Their
determinants are seven, which is odd, so both are invertible on residue
pairs modulo `2^10`. Multiplication in `Z[tau]` is commutative; hence
each map commutes with the six norm-one units. It therefore sends each
six-unit residue class to one well-defined six-unit residue class.

For a seed `s` and map `alpha`, a signed digit `u(alpha s)` covers the
query residue `r` exactly when `u(alpha s) = r (mod 1024)` for one of
the six units `u`. The norm constraint `N(alpha s) <= 1024^2` is
invariant under those units. Subtracting that digit from the two
representative coefficients and dividing by 1024 produces integral
next-state coefficients. Repeating this for twelve windows and using
the exact terminal pair yields the original representative by direct
integer reconstruction.

The shortest signed representative of a residue class is sufficient
for screening a seed in that class: another representative has the
same mapped residue class under every listed endomorphism and no
smaller norm. This reduces the finite seed search to one certified
digit per six-unit class.

# Dual endomorphism orbit cover screen

The proposed radix-1024 fixed-base format adds the norm-seven
endomorphisms `rho = 1 + tau` and `rho_bar = 4 - tau` to the existing
degree-three `tau` cover. A point table stores one affine point for each
selected seed at each of twelve full windows. At evaluation, contributions
with the same endomorphism tag can be accumulated before applying that
endomorphism to a bucket. The terminal atlas is the existing exact
radix-1024 terminal table.

This screen fixes three map sets before inspecting the construction
results:

1. `tau`: `1, tau, tau^2`, to calibrate the greedy selector against the
   existing exact 73,417-seed three-image cover.
2. `tau_rho`: those three maps and `rho, tau*rho, tau^2*rho`.
3. `tau_rho_both`: those six and `rho_bar, tau*rho_bar,
   tau^2*rho_bar`.

The universe is all 174,764 six-unit residue classes modulo 1024. A
candidate seed is the minimum-norm signed digit already certified for
one class. It covers a class under a listed map only if the transformed
digit has Eisenstein norm at most `1024^2`. Each map commutes with the
six units, so the class relation is exact. Select seeds with deterministic
maximum-uncovered-gain greedy set cover; break ties by smaller seed norm,
then class order. Identity is reserved as seed zero.

For every selected cover, verify every class assignment and every map
norm. Report selected seeds, map use, coverage multiplicity, affine
point-table slots and bytes, and a complete source and input digest.
Run the twelve-window integer recoder on the already frozen direct-index
design panel, checking exact division by 1024 and the terminal norm
bound. This panel is a construction diagnostic; a positive format needs
a new disjoint scalar panel, independent point replay, native execution,
and a host-isolated matched timing run before any runtime claim.

The screen does not treat table-byte savings alone as an online gain.
The evaluation must charge bucket additions and every degree-seven
endomorphism application. A mode that reduces seeds but adds enough
point work to lose its likely memory advantage remains a design result.

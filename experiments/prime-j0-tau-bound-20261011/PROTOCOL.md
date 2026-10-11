# Exact tau-only cover of radix-1024 scalar digits

The norm-three map `tau` permutes the 174,764 unit-quotient residue
classes in 513 directed cycles. A seed at one class covers its own class,
the next class when its mapped digit is within the norm limit, and the
second successor when its twice-mapped digit is within the norm limit.
The capacities are therefore nested lengths one, two, or three.
Multiplication by `tau` has determinant three, which is invertible modulo
1024, so its action really is a permutation of these classes. Unit
rotation commutes with the action.

The nearest representative of a class dominates every other
representative for this cover: all have the same successor classes,
while `N(tau^j z)=3^j N(z)`. The verifier searches translations of a
canonical residue for its least norm. This search is exhaustive. The
hexagonal residue lattice has covering radius squared `R^2/3` for
`R=1024`. Since `N(a,b) >= 3b^2/4`, a closest representative has
`|b|<R`; since `N(a,b) >= a^2/4`, it has `|a|<2R`. For initial
coordinates in `[0,R)`, only horizontal shifts `-2,-1,0,1` and
vertical shifts `-1,0` can remain. The verifier enumerates a superset
of these shifts.

For each cycle, minimize the number of selected seed positions covering
every class. Any selected positions in cyclic order partition the cycle
into gaps whose lengths do not exceed the preceding seed's capacity.
One of positions `0`, `L-1`, or `L-2` must supply class zero. Cut at
that position and solve the resulting line by the recurrence

`F(i) = 1 + min(F(i+s): 1 <= s <= min(capacity(i), L-i))`, `F(L)=0`.

Take the minimum over the three cuts. Break cardinality ties by the sum
of seed norms and then the cut index. This produces both an exact
integer lower bound and a complete cover. An independent verifier must
recompute the class cycles, norm capacities, and optimum with a Boolean
state dynamic program that enforces coverage class by class, then check
the serialized cover and every exact residue.

If a `k`-seed cover leaves `U` classes without a tau provider, adding a
direct seed for each of those classes completes a tau-only cover with
at most `k+U` seeds. Thus `U` is at least the exact tau-only minimum
minus `k`, regardless of how the original `k` seeds were chosen.

The fixed-budget rho cover in the parent experiment has 67,338 seeds.
The exact tau-only optimum establishes the minimum table-size increase
needed to remove the norm-seven map under this radix, norm limit, and
one-seed-per-class format. Stage paths and native point replay are
separate checks. CPU speedup requires the repository's host-isolation gate.

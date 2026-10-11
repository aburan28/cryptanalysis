# Exact tau-only cover of radix-1024 scalar digits

The norm-three map `tau` permutes the 174,764 unit-quotient residue
classes in 513 directed cycles. A seed at one class covers its own class,
the next class when its mapped digit is within the norm limit, and the
second successor when its twice-mapped digit is within the norm limit.
The capacities are therefore nested lengths one, two, or three.

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

The fixed-budget rho cover in the parent experiment has 67,338 seeds.
The exact tau-only optimum establishes the minimum table-size increase
needed to remove the norm-seven map under this radix, norm limit, and
one-seed-per-class format. Stage paths and native point replay are
separate checks. CPU speedup requires the repository's host-isolation gate.

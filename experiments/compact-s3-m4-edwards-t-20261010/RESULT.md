# Torsion-invariant t coordinate: exact N53 base and S3 circuit gate

Q20261010173300 verifies `t=x/(x²+x+1)` on the same Koblitz curve and
measures its three-point polynomial as a compact chained-S3 alternative.
The independent audit passed 32 subgroup point-sum triples at each of N53
and N83, including negation, rational 2-torsion translation, and Frobenius
checks. The denominator has no root in any odd-degree binary field because
`x²+x+1` splits over F4 and F4 is not a subfield when the degree is odd.

The exact normal-basis `t`-weight≤3 factor base on
`EC1N53Ckb1hf77aab617904` has **11,342 distinct usable points before
folding** and **107 signed-Frobenius columns**. All 24,857 nonzero masks
of weight at most three were enumerated. Of these, 12,190 admitted an x
lift and 5,671 admitted a rational point; each rational `t` had four raw
curve points, while cofactor projection identified the two points differing
by rational 2-torsion. The 5,671 rational values formed 107 full
Frobenius orbits. The archived 7-byte canonical-key set has SHA-256
`6fa6e40a4865083c07efa88de1a14e642812fbc71d76282d3c45223e7d40eb07`.
Enumeration took 57.36 exploratory seconds; an independent complete
enumeration reproduced every count and the exact key bytes.

| Degree | Link | AND gates | CNF clauses | XOR rows | Variables |
| ---: | --- | ---: | ---: | ---: | ---: |
| 53 | factored x-S3 | 8,427 | 25,282 | 265 | 8,799 |
| 53 | Edwards t-S3 | 8,427 | 25,282 | 371 | 8,905 |
| 83 | factored x-S3 | 20,667 | 62,002 | 415 | 21,249 |
| 83 | Edwards t-S3 | 20,667 | 62,002 | 581 | 21,415 |
| 131 | factored x-S3 | 51,483 | 154,450 | 655 | 52,401 |
| 131 | Edwards t-S3 | 51,483 | 154,450 | 917 | 52,663 |

The link circuit implements
`f3(a,b,c)=c²+ab(ab+a+b+1)(c²+c)+(a+b)²`. The audited subgroup
triples satisfy this polynomial. The table counts one unfixed link only;
it does not infer a complete four-point solver cost from gate count or
construction time.

At weight three, this coordinate gives 0.471 times the existing exact
N53 x-base size (`B=24,062`, `K=227`). Under the uniform-target
four-summand counting model, its representation upper count scales by
`(11342/24062)^4 = 0.0494` on this curve; the per-link AND count is
unchanged and the t link has additional XOR rows. This parameter is a
**no-go for a relation-supply improvement at equal weight**. Higher
weight changes both yield and matrix size and needs an exact base and
ordinary-query measurement before promotion.

The proposal retains `candidate_id: null`, `run_id: null`, and
`isogeny: "none"` (`ISO0`). N83 and N131 t-base sizes remain unknown.
The freeze SHA-256 is
`adc422bff74aab3db16d7f794d049467797098d581af8dc7f5fc2e5b7f79879f`;
`audit.json` records the PASS result. Move that file aside before
rerunning `python3 audit.py`, which refuses to overwrite its output.

The next parameter gate is exact orbit-representative enumeration for
N53 t-weight≤4, followed by its ordinary public-target PDP stage if the
base/rank budget remains viable. An N83 solver comparison requires its own
exact t-base count and digest.

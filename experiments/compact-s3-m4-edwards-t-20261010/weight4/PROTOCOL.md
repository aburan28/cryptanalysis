# Q20261010174100: exact N53 t-weight-four base

Enumerate the complete normal-basis t-coordinate base at N53 for weight
bounds three and four. Work once per Frobenius orbit of nonzero t masks;
validate every orbit has length 53 and that the orbit counts reconstruct
all masks. For each representative solve `t*x²+(t+1)*x+t=0`, lift a rational
point on `y²+xy=x³+1`, apply the exact cofactor 428, and deduplicate the
signed-Frobenius canonical subgroup x key. Every usable column represents
106 distinct pre-folded points because the subgroup order is odd prime and
53 is prime. Keep the exact packed-key digest and all zero/exceptional
counts.

The weight-three prefix must reproduce Q20261010173300's exact
`B=11342`, `K=107`, and key digest before the weight-four result is
accepted. Freeze source, curve/base input hashes, and resource boundary
before enumerating. This remains a Q-stage proposal with `candidate_id`
and `run_id` null and `ISO0`; it defines no ordinary solver result by itself.

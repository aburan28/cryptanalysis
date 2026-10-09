# Terminal F6 bitplane boundary stays small on four chain lengths

On the frozen S3 chain over GF(2^9) with modulus 515 and curve
`y^2 + xy = x^3 + 1`, the exact target boundary remains 12 Boolean variables
as the summand count grows from three to six. The system grows from 18 to 54
Boolean variables. Every one of the 512 target abscissae in each case matches
both the packed separator and an independent enumeration of curve-point sums;
every satisfiable result passes the original equations and point replay.

The independent enumerator takes every liftable abscissa in the declared
`0 <= x < 2^ell` range, includes both curve-point signs, repeatedly adds the
points, and records each finite sum's abscissa. This is a separate group-law
calculation from the S3 equation solver. The four three-bit-coordinate cases
each have three usable curve points and two reachable abscissae. The
four-bit-coordinate, three-summand case has eleven usable points and 106
reachable abscissae. Its 106 positive and 406 negative target outcomes all
match the bitplane and packed algebraic queries.

| Summands | Bits per summand | Boolean variables | Target boundary bits | Reachable target abscissae | Exact targets checked | Static factor states | Cached witness words |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 3 | 18 | 12 | 2 | 512 | 129,548 | 504 |
| 4 | 3 | 30 | 12 | 2 | 512 | 19,004,432 | 33,264 |
| 5 | 3 | 42 | 12 | 2 | 512 | 37,879,316 | 66,024 |
| 6 | 3 | 54 | 12 | 2 | 512 | 56,754,200 | 98,784 |
| 3 | 4 | 21 | 13 | 106 | 512 | 950,832 | 2,040 |

For the three-bit chains, factor-state work increases by exactly 18,874,884
and cached witness storage by exactly 32,760 words per additional summand
between four and six summands. These are finite measured work counters, not
an asymptotic theorem. The wider four-bit chains with four, five, or six
summands reached the prepared factor's explicit 21-variable **width cap**
(native status 3) before any target query. They remain three recorded
`EXPECTED_WIDTH_CAP` outcomes; they are not counted as solved cases.

Source was committed at `26d5d2ebceab50a4709ae9e62f06db2f416659dc`
before the final run. The executed bitplane source was byte-identical to that
commit and its binary receipt was from parent source
`7939f6414091debb10b3d662ba440f339e18def2`. The final run passed all
2,560 target checks and three width-cap controls. The compressed
[raw report](evidence/chain-scaling.json.gz) is 11,715 bytes, with SHA-256
`0bd179ecd0481162b979479f1bf884a11bda7f67e44871edd6c981478e7531fd`;
it retains every target, answer status, witness, independent reachability
decision, source/binary hash, and static work counter. The first control run
used the same cases but misnamed native status 3 as a state cap; its raw file
is retained locally as `/private/tmp/f6-chain-scaling-916ceae01-report.json.gz`
and was superseded by the corrected source-frozen run.

This exact specialization benefits a small terminal separator. Raising the
local-width cap for the four-bit, four-summand chain would require a separate
resource-bounded experiment, while dense links can make the terminal
separator itself grow with the full system. The next structural test is a
larger factor-base family with measured natural target yield and full setup,
relation, and recovery accounting. No CPU wall-time speedup is inferred from
this correctness screen.

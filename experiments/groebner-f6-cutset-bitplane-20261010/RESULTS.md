# Exact boundary bitplanes reduce complete cutset-query cost

The cutset-conditioned GF(2^9) S3 systems have a 16-variable terminal
boundary. Reusing exact static feasibility and affine target truth planes
replaces repeated dynamic factor construction and elimination with fresh
bitplane intersections and witness reconstruction. The candidate retains
fresh packed target coefficients, native direct-template checks, original ANF
checks, and curve-point replay for every returned witness. Source was frozen
at commit `b7eeffe1378882b8555ef6e00550612f49ab635d` before measurement.

The optimized and UBSan exactness panel passed all **4,096 complete queries**
and **12,288 native branch queries** over both summand counts and all 512
target abscissae. Every branch status agreed with independently enumerated
branch-restricted curve sums. Every positive branch passed the original
unconditioned ANF, last S3 field equation, native direct-template check,
planned point replay, and an independent old point replay outside the timer.
The arbitrary-system panel passed 640 native decisions against exhaustive
six-variable enumeration; four applicability controls rejected a 17-variable
boundary or a template monomial outside the declared boundary. The complete
journal audit found zero mismatches across 43,704 records.

The optimized timing panel alternated arms over three repetitions of all 512
targets per geometry. It retained **6,144 timed complete queries and 18,432
native branches**, plus twelve warmup queries. Each timed interval includes
fresh packed target coefficients, every native branch, original equation and
curve checks, and planned point replay. Journal writing and the second old
point replay occur after the timed call.

| Summands | Message median | Bitplane median | Paired geometric mean message/bitplane | 95% target-cluster bootstrap interval |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 5.215 ms | 0.699 ms | 12.308× | 11.416–13.290× |
| 5 | 12.570 ms | 2.681 ms | 11.775× | 10.580–13.177× |

The positive-target subset has 254 abscissae per geometry. Its paired ratios
were 5.582× for four summands and 3.659× for five; median complete intervals
were 5.921 versus 0.945 ms and 15.265 versus 4.025 ms. On the 258 negative
abscissae, the ratios were 26.807× and 37.210×; bitplane medians were 0.164
and 0.266 ms. Native time on the five-summand positive subset fell from a
median 10.371 ms to 0.046 ms. Planned curve replay now accounts for a median
2.586 ms of the five-summand positive bitplane query and is the next
end-to-end bottleneck.

Reusable setup was measured separately. In the optimized primary run, the
existing grouped-message setup took 1.841 s and 3.036 s for four and five
summands; additional bitplane setup took 1.266 s and 3.350 s. The timing
context measured additional bitplane setup at 1.210 s and 3.333 s. On its
frozen 512-target mix, the observed mean query savings amortize that extra
setup after roughly 227 four-summand or 214 five-summand queries. These
thresholds are local diagnostics on a contended host, not controlled resource
or wall-time claims. A cold single query pays the setup explicitly.

The [compressed report](evidence/report.json.gz) has SHA-256
`d2e3f601a422801f4c469029082eb03f9390fd18f4b7402f77ec2daaa52cf5d4`.
The [complete journal](evidence/journal.jsonl.gz) has SHA-256
`426f09c208f074fde9ecd80661c66e9a54e30e4bd5812aabaf8eb7cee8659dd2`.
The report binds the source commit, source and binary hashes, predecessor
comparator, setup costs, all failures and cap statuses, and every paired
timing row. `qualified_speedup` remains null until a qualifying isolated-host
CPU receipt exists. The result applies to the affine-target, bounded-separator
S3 geometry; it does not establish a general asymptotic improvement over F4,
F5, or prior chordal elimination.

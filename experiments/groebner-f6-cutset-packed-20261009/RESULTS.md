# Fresh packed targets over exact cutset layouts

The packed arm writes each target's S3 coefficients into reusable ctypes
offset and term buffers, then runs the same two or four native cutset branches
as the direct arm. Across both GF(2^9), seven-bit-summand geometries, its
packed rows matched independently generated and canonicalized S3 ANF rows
for every one of the 512 target abscissae. The source-bound optimized and
UBSan primary panel passed **4,096 complete queries and 12,288 native branch
queries**, with no status or witness mismatch against branch-restricted curve
enumeration, original ANF evaluation, the original S3 field equation, or
curve point replay.

The final validation source was commit
`9883bbea14c9ff82489f5858ece46dc3828e82c3`. Each primary case had 512
coefficient matches, 1,024 complete queries, and the expected 2,048 or 4,096
branch queries. Each arm found a verified answer on 254 target abscissae and
finished unsatisfiable on the other 258. The optimized paired panel retained
three repetitions of every target, alternating arm order, for **6,144 timed
complete queries and 18,432 native branch queries**. Three target warmups per
arm and case are recorded separately. Journal writes are outside the timed
query calls.

| Summands | Direct coefficient median | Packed coefficient median | Direct complete-query median | Packed complete-query median | Paired geometric mean direct/packed | 95% target-cluster bootstrap interval |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 0.282 ms | 0.052 ms | 6.263 ms | 5.984 ms | 1.048× | 1.026–1.070× |
| 5 | 0.299 ms | 0.054 ms | 24.225 ms | 24.868 ms | 1.022× | 0.966–1.083× |

The interval starts before fresh target coefficients and ends after all native
branches, original field/static equation checks, and curve point replay.
Target-independent static layouts and affine templates precede it. Ratios
are paired on target abscissa and repetition; the bootstrap resamples target
abscissae with their three repetitions kept together. The four-summand
complete-query result is a modest local diagnostic; the five-summand interval
includes parity and its separate medians even favor different arms. This
contended macOS ARM64 host lacks the required isolation receipt, so both
controlled CPU speedups remain unknown. The coefficient-only improvement
does not determine the whole-query ratio: median native time is about
4.9 ms for four summands and 14–15 ms for five, and median checks are about
0.38 ms and 3.97 ms respectively.

The [compressed complete report](evidence/complete/report.json.gz) has
SHA-256 `fd92b8ced02d60e3b3166f76f47a0759be1da148c192d22974bba2f823169f29`.
Its [full journal](evidence/complete/journal.jsonl.gz) has SHA-256
`8ce22e019cc0553091601f78c38945cf9207ec639de5219b82cbaca149631c46`.
The report binds source and native binary hashes and stores every setup,
status count, timing summary, and run limit. The journal retains each
coefficient audit, completed query, branch, and warmup.

The first committed validator version finished all four primary cases and
the four-summand timing queries, then stopped on a variable-name error while
summarizing those timings. Its [failure record](evidence/first-attempt/failure.json),
[partial report](evidence/first-attempt/report.json.gz), and
[partial journal](evidence/first-attempt/journal.jsonl.gz) are retained. The
one-line validator correction was committed before the successful full rerun;
the partial timing data were excluded from the table above.

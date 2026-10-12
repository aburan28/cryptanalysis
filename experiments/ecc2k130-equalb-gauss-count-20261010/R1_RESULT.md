# R1: two Gaussian matrices reduce sampled RSS on both equal-B formulas

The first frozen four-cell run reduced sampled solver peak RSS from 1,007.672
to 700.641 MiB on normal4 and from 840.969 to 516.344 MiB on W24 when
`maxnummatrices` changed from five to two. The paired two/five ratios are
0.695306 and 0.613987. Both are below the protocol's 0.70 memory threshold,
but the normal4 margin is 0.004694 and one observation does not establish a
stable rate on this unisolated host. All four searches entered live search
and reached the 70-second external wall guard with `BOUNDED_UNKNOWN`.

| Formula | Matrices | Wall s | Peak sampled RSS MiB | Recovered matrices | Live restart rows | Elimination calls in raw transcript |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| Normal4 counter | 5 | 70.243 | 1,007.672 | `[5]` | 183 | summary absent after guard |
| Normal4 counter | 2 | 70.186 | 700.641 | `[2]` | 182 | summary absent after guard |
| W24 balanced | 2 | 70.117 | 516.344 | `[2,2]` | 200 | `1709`, `100K` |
| W24 balanced | 5 | 70.077 | 840.969 | `[5]` | 174 | summary absent after guard |

All four transcripts admitted a printed 8,262-by-13,084 Gaussian matrix.
The W24/two transcript separately prints nonzero elimination calls; the
other three processes were killed before their periodic solver summaries,
so their elimination-call status is **unknown**, not zero. No solver returned
a candidate decomposition. The [independent audit](runs/R1/audit.json)
rehashes the two compressed and raw formulas, parent source, exact flags,
the pinned solver binary identity in each receipt, every stdout/stderr file,
matrix counts, restart rows, terminal guard, and summary. The first local
audit version represented an absent elimination summary as `false`; the
auditor now records `null`. This corrects only a derived field; raw receipts
and transcripts were unchanged.

Run command: `python3 -B experiments/ecc2k130-equalb-gauss-count-20261010/run_count.py --run --run-id R1`, after `--check` passed with both raw XCNF and binary hashes. The guarded runner used the exact frozen one-thread, 60-second internal, 70-second external, and 4-GiB RSS envelope. The shell was granted access to the required `ps` RSS probe; all process-group exits and guards are in the cell receipts. Formula decompression and source hashing happened before each solver clock. Host isolation is unverified, so the wall figures are exploratory stage diagnostics. `candidate_id` remains `null`.

The [frozen repeat](REPEAT.md) checks whether this narrow memory pass
persists in one more complete paired four-cell run. Neither a memory ratio
nor a capped search opens the 16/256 held-out query prefixes; verified
ordinary relations and novel rank remain the advancement measure.

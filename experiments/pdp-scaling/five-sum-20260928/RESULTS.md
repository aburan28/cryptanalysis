# First frozen five-summand solver result

The manifest and source were committed before `run-1/` was produced. The
native solver, paired direct control, target streams, signed factor bases,
unmodified subprocess output, Python witness/rank audit and file digests are
archived there. Every target is an ordinary uniform nonzero subgroup point;
the planted check appears only in `*.control.jsonl`.

| Field and signed base | Arm | Found / attempted | New rank | Searches stopped at budget | Process wall (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| n=13, full B=26 | five summands | 24 / 24 | 13 | 0 | 0.00333 |
| n=13, full B=26 | direct three summands | 20 / 24 | 13 | 0 | 0.00403 |
| n=83, first 128 of full B=130,604 | five summands | 0 / 4 | 0 | 4 | 1.621 |
| n=83, same 128 | direct three summands | 0 / 4 | 0 | 0 | 0.0691 |

On n=13, the first eight independent rows appeared by target 8 for five
summands and target 10 for three summands. The 24-target, one-seed n=13
experiment is a correctness and yield control; it does not pass the required
five-seed paired comparison. Its five-summand charged time is **0.05818 s**
including the archived full base preparation (0.01649 s), generation of all
24 public targets, input loading, native process, and Python replay/rank
audit. The baseline's search uses the same setup and inputs; its separately
timed native subprocess is not a valid end-to-end 2× comparator on its own.

The n=83 planted five-point target was found in 130 triple checks and
independently replayed. All four ordinary attempts stopped at **50,000**
checks (200,000 total), so they are not exhaustive, and their zero yield
cannot estimate the full-base relation rate. The n=83 charged five-summand
time is **27.13 s**, including the archived full-base preparation **23.14 s**;
peak native RSS across both arms and the control was **59,824 KiB**. The
signed subset table has 8,193 distinct pair sums. Its full-base counterpart
requires 8,528,767,710 unordered pair entries, whereas the executable caps
itself at 1,500,000. The exact full n=83 base is usable as an input to a
different five-summand method, but this meet-in-the-middle method cannot run
the full base under the frozen memory limit.

`run-1/results.json` and `run-1/n*-l*.audited.json` distinguish found,
exhausted and budget outcomes. The latter store actual subgroup points,
signed coefficients and rank status for each witness. `archives.json` hashes
all persisted run files. There is no ECC2K83 independent relation from the
full base, no end-to-end DLP result, and no measured 2× speedup.

**Next solver step:** use the complete x-subspace base with an algebraic
five-summand decomposition encoding whose memory does not grow as B squared.
Start with a bounded ANF/S6 encoding and reject it if expansion or solving
exceeds the recorded 512 MiB/target budget. Compare it on the same ordinary
targets and archived base, charging misses and verification. The point-domain
solver here remains an exact small-parameter control.

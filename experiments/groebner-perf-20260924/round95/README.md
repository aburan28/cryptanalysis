# Complete queries with exact checker policies

Round95 connects the round93/94 checker policies to the leased packed-input
path and measures the complete frozen query. The same native F4 producer runs
in every arm. Independent equation and curve replay remain inside successful
PDP intervals.

- [Protocol and timing boundary](PROTOCOL.md)
- [Measured results and limitations](RESULTS.md)
- [Next experiments](NEXT_STEPS.md)
- [All 92 diagnostic cells, including raw timings](summary.json)
- [Lossless validation archive](results.tar.gz) and [custody receipt](archive.json)

Local correctness passed on optimized and UBSan builds. Ten of the 23 fixtures
completed algebra certification in each arm; five were planted six-variable
PDP fixtures with independently replayed solutions. Thirteen fixtures exhausted
the producer budget before certification. Every configuration had the same
accepted outcomes. CPU timings are exploratory, with no qualified speedup.

Rebuild and run through `run_validation.py` as described in the protocol.
The default checker remains legacy; selection is explicit. No F6 asymptotic,
general GPU crossover, ordinary-query yield, or complete IC speedup follows
from this experiment.

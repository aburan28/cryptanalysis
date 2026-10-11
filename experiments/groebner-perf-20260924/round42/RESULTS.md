# Physical M4 Pro measurement

The frozen comparison completed 6,040 independently verified queries across
18 planted PDP inputs. Of 36 planned trials, 33 passed the unchanged load gate,
two completed but exceeded it, and one was not admitted and performed no timed
queries. Each admitted trial includes one warmup and seven measured pairs.
Every pair runs every retained comparator in a shuffled order. The interval
includes a fresh complete query, exact certificate checking, equation/curve
replay, and the reference ANF check. Target-independent setup and evidence I/O
are outside it. Full source, runtime binary, proof and journal reconciliation
passes. CPU dispatch remains unchanged.

All three 24-variable inputs pass both trial gates against every measured
comparator. The following are complete-query medians, not kernel timings:

| Input seed / trial | Combined Metal ms | Previous wide Metal ms | Fastest measured CPU ms | Paired gain over previous wide Metal (95% bootstrap interval) |
| --- | ---: | ---: | ---: | --- |
| 201 / 1 | 21.852 | 30.400 | 41.194 | 1.336 (1.219–1.466) |
| 202 / 1 | 16.231 | 22.462 | 41.835 | 1.389 (1.338–1.425) |
| 203 / 1 | 16.047 | 23.120 | 41.905 | 1.441 (1.378–1.552) |
| 201 / 2 | 15.845 | 22.173 | 41.165 | 1.392 (1.315–1.429) |
| 202 / 2 | 15.880 | 22.255 | 41.837 | 1.399 (1.345–1.408) |
| 203 / 2 | 21.073 | 29.001 | 41.440 | 1.303 (1.081–1.629) |

Paired gains over the fastest measured CPU range from 1.861 to 2.689.
The CPU comparator is selected separately in each trial by median latency;
all retained comparators, not just this selected one, must pass the gate.
The bootstrap intervals are descriptive paired intervals from seven samples,
not simultaneous familywise guarantees or evidence of universal superiority.
The load gate does not prove exclusive device ownership.

The three qualifying 27-variable trials have combined medians of 376.782,
359.720 and 378.711 ms, versus 701.084, 675.978 and 718.347 ms for previous wide
Metal in those same trials. Their independent verifier medians are 109.928,
107.392 and 105.830 ms. None of these inputs has two qualifying repetitions:
seed203 trial1 and seed201 trial2 exceeded the load limit; seed202 trial2 was
not admitted. Those outcomes remain in the evidence, and there is no repeated
27-variable speedup claim. No smaller input establishes the combined path as a
repeated winner against every comparator.

[The full analysis](evidence/physical-m4-performance.json.gz) retains every
input, comparator, interval, load outcome and repeated gate. The measurement
and analysis plans are stored beside it. The package binding records exact
system outputs, proof bytes, mathematics and integer work matching the timed
prototype. Packaging rebuilds the producer, so these timings describe the
isolated source-bound physical prototype; they do not measure hosted CI or
claim identical latency for every compiler/build. The separate earlier
normalization sequence retained 4,176 verified queries, only one qualified
trial and no repeated gain.

These are planted PDP-stage controls. They do not measure natural relation
yield, full single-target IC versus rho, general high-regularity F4/F5
performance, CUDA/OpenCL/HIP performance, or a new asymptotic complexity bound.
`candidate_id` and `online_speedup` remain null.

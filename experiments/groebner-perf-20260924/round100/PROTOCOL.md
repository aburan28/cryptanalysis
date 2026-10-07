# Larger-budget complete-query frontier

This experiment asks whether sorting improvements persist through completed
independent certification and replay. It rebuilds the unchanged round99 producer
kernels and compares original sorting, packed keys and bounded radix. All three
use the existing completion-first, last-use-release checker. That shared policy
is fixed before measurements; this is not a comparison against earlier panels'
legacy checker timings.

The frozen inputs are two distinct solved six-variable PDP controls, the dense
twelve-variable algebra control, and all five nine-variable and five
twelve-variable PDP fixtures from the original input archive. Each is run at
20, 80 and 320 million producer work units. Every level is an independent fresh
attempt, including levels where a prior attempt succeeds. Keep all failures;
do not select a favorable level or substitute time to failure for a solve.

Every arm has the same two-million proof-node limit, 4,096-row limit, batch 64,
200-million checker-work limit and two-million peak live proof-term limit.
The independent Python artifact verifier has separate frozen limits of one
billion work units and fifty million retained terms. An artifact audit failure
is retained and cannot become a verified result. There is no limit tuning after
observing the panel.

One new worker process performs each query. Library loading, fixture and layout
preparation occur before its target-dependent timer. The timer includes fresh
packed coefficient descent, native solving/certification, proof materialization,
extraction, independent equations/curve replay and lease teardown. Proof hashing
and file storage happen after that interval. Identical proof artifact bytes are
stored once; no solving, numerical rows or answers are reused across calls.
Process elapsed time and peak RSS include startup/setup/artifact overhead and
are recorded separately from query timing.

The parent enforces a sixty-second process deadline, drains killed workers and
retains timeout/nonzero-exit rows and logs. An external failure has no invented
query interval or answer. Calls run sequentially. Controls run each cell once
on optimized and UBSan builds. The diagnostic panel has one warmup round and
three observation rounds with rotating arm order. A fresh process is used in
all rounds; warmup does not imply persistent per-process state.

Audit proof bytes by content hash, replay derivations and Boolean completion
without loading archived native libraries, check the independently enumerated
finite Boolean basis for these at-most-twelve-variable controls, and independently
reconstruct proof liveness. Check exact non-timing traces between sorting arms
at each budget. Preserve the full outcome/status mix, work counts, phases,
process costs, RSS and unpaired failures.

This is a CPU-only component diagnostic on a host without an isolation receipt.
Qualified/aggregate/online speedups remain null. These planted controls do not
estimate natural relation yield or supply a recovered DLP, paired rho result,
GPU crossover, globally fastest implementation or new F6 asymptotic result.

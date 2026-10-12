# Compact separator boundary for fresh F6 queries

The frozen four-summand S3 message layout removes 18 of 30 Boolean variables
at setup. The existing fresh-query solver still scans and eliminates those 18
variables, although none occurs in a retained or target-dependent factor.
This opt-in candidate renumbers the 12 remaining boundary variables in
increasing original-bit order before query elimination. Factor truth-table
words remain valid because that order is unchanged. It maps a satisfying
boundary assignment back to the original 30-bit ring, reconstructs static
witnesses, checks every original ANF equation, and replays the target point.
The old message engine remains the matched reference and CPU fallback.

The source transform pins the predecessor C++ file by SHA-256 and changes only
the fresh-query entry point. Both engines build all target-dependent equations
and factors anew. Their source commit and optimized/UBSan binary hashes are
recorded before measuring. The exact controls compare 90 small random systems
to exhaustive enumeration in both build modes, reject target terms outside
the boundary, and compare six S3 targets. The complete semantic screen checks
all 512 frozen abscissae against the independent packed-factor reference.

The performance panel uses those six targets with one warmup and five
alternating matched pairs. Its online interval starts before fresh target
equation construction and ends after independent ANF and point replay.
Setup, including cached message construction, is recorded separately.
Logical state charges retain static work and count only elimination actually
performed per query; the compact and full-message counters therefore differ.
Local CPU wall time is exploratory until a physical-host isolation receipt
qualifies the comparison. The experiment does not change default routing.

# Affine target-equation compiler for a cached F6 separator

For the last S3 factor, characteristic-two arithmetic gives
`S3(a,b,t) = a²b² + (a²+b²)t² + abt + curve_b`. Its Boolean ANF rows depend
affinely on the bits of the fresh target abscissa `t`. This opt-in candidate
compiles the target-independent row and each target-bit delta once, then uses
four-bit lookup groups to construct the exact rows per query. It does not
cache a target's solver answer. The compact boundary native engine, original
equation checks, and point replay are unchanged.

The reference and candidate use one cached separator context and the same six
frozen target abscissae. One warmup and five AB/BA matched pairs per target
record the full target-dependent interval from fresh ANF construction through
independent ANF and curve checks. Setup and generated tables are separate.
The source must be committed before `build.py`, exact controls, semantic replay,
or timing. Local wall time is exploratory until a host-level isolation receipt
passes the repository benchmark contract. Default routing is unchanged.

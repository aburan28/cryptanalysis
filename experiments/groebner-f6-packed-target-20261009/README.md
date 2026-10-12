# Direct packed ANF for fresh F6 targets

The final S3 factor's Boolean ANF rows are affine in the target-abscissa bits.
The predecessor compiles their target-independent coefficients, but still
constructs Python row lists and repacks them as ctypes arrays for every query.
This candidate allocates the offsets and term arrays once. For each fresh
target, it XORs the precomputed coefficient groups directly into those arrays
and sends the exact packed rows to the compact native separator. No target
answer is cached, and each query still performs fresh native factor
construction, elimination, static-equation checking, independent field-S3
checking, packed-row checking, and curve-point replay.

The source is frozen in a commit before build, exact controls, semantic replay,
or timing. The complete-query panel pairs this path with both the compiled
Python-row predecessor and the original compact path on the same six targets.
The interval starts before target-dependent coefficient selection and ends
after independent equation and point checks. Context setup and reusable
buffers are separate. Local wall time is exploratory without an isolated-host
receipt, and default routing is unchanged.

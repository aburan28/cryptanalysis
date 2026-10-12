# Proof representation and timing contract

This is an experimental Boolean F2 derivation certificate container, not a new
Gröbner algorithm. A decoded DAG is not by itself proof of a correct basis.
Acceptance requires the independent checker against the original inputs and
claimed basis, including reverse inclusion and Boolean Buchberger completion.

The 32-byte header is little endian: `8sBBBBIQQ`, containing `GBPROOF1`, format
version 1, payload endianness (0 little / 1 big), monomial-order code 1
(`grevlex-x0-first`), reserved byte 0, variable count, node count, output count.
The payload has exactly `16*nodes + 4*outputs` bytes with no trailing data.
Variable count is 1..64, node count at most 10,000,000, output count at most
1,000,000. These bounds match the checked producer ABI. Counts must agree with
the supplied byte length before the decoder allocates node lists.

Each node is a payload-endian `IIQ`: opcode, 32-bit operand `a`, 64-bit operand
`b`. Input opcode 0 uses `a` as the original equation index and requires `b=0`.
Multiply opcode 1 uses an earlier node `a` and an in-ring monomial mask `b`.
XOR opcode 2 uses two earlier node indices. Output references are payload-endian
32-bit node indices. Equation-index bounds depend on original inputs and are
checked by the algebra verifier, not inferred from the container. The decoder
has independently encoded tests for both byte orders and the 64th variable.

Capture checks the native node size and field offsets, envelope, shape and
non-null pointers before copying. It is called only after native certification,
while the producer result owns valid buffers. It does not accept arbitrary
external pointers. Immutable bytes sever the native lifetime relationship.
Exceptions during copying still execute the existing native-result cleanup.
Per-call profiles use a ContextVar so nested/concurrent calls do not overwrite
one another. Export-disabled and inconclusive calls retain their usual behavior.

The list reference deliberately keeps the original `abi.export` operation,
including its existing basis conversion. Both arms profile the same basis
materialization and proof-export boundary. Every candidate proof must decode to
the exact list-reference DAG and output references; all non-time producer and
checker records must agree. F4 hash/dense controls preserve their separate work
accounting contract. No numerical budget or failure is removed.

The complete query returns a certified basis plus an owned proof representation,
and for a PDP control includes independently replayed equations and curve checks.
It excludes reusable setup and artifact serialization/storage for both arms.
Binary decoding is timed separately for callers requiring Python lists; it is
not required by the packed-output API. Diagnostic reports must expose this API
difference and the additional decode cost. They must not promote local CPU
timings to speedup claims without the repository's host-isolation receipt.

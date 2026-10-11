# A direct 2-adic index removes the orbit rank directory

The six-unit classes of the radix-1024 residue square have a direct
dense index. The [independent orbit check](index-check.json) enumerated
all **1,048,576** residues and verified **174,764** classes: one zero
orbit, one orbit of size three, and 174,762 orbits of size six. Every
computed transform maps its input to the unique class representative.

The resulting [full atlas](atlas-r1024-full-adic-orbit.bin) is
**856,512 bytes**, saving **196,616 bytes** against the prior quotient
atlas. It holds the same 83,051 seeds and the same 174,764 three-byte
codes, in direct-index order. The terminal atlas is byte-identical to
the earlier quotient terminal atlas. The [construction receipt](atlas-receipt.json)
binds the sources and assets.

The [exhaustive atlas replay](atlas-check.json) decoded every full
residue and found **zero differences** from the prior quotient decoder
in seed, tau exponent, unit, or signed digit. The exponent-two residue
count remains 64,674.

The [new disjoint input panel](input-check.json) contains 4,096 full
range scalars. The [paired group replay](group-check.json) verified
integer reconstruction and independently computed points on every
scalar. Both formats produced the same point-output hash,
49,152 mixed additions, 16,539 grouped gauge rotations, and 6,384
outer tau images. The source-pinned native direct-index mode passed
its 4,096-case targeted test against the quotient, direct-code, and
two-image controls, including 128 separate binary point checks. Its
measured retained size is **65,596,552 bytes**, 196,648 bytes below
the quotient mode, leaving 1,512,312 bytes below the RunPod CPU's
reported 64 MiB L3 capacity. This is representation accounting; the
L3 is shared and the current pod lacks host-level isolation evidence.

The complete portable native suite passed **139/139 tests**. The
command-line mode passed all **10 edge-fixture cases**, with the
independent verifier checking its point stream. The
[receipt validator](verify.py) binds the source, atlas, panel, native
materialization, compressed test logs, and edge output. The
[tested](native-tested-materialization.json) and
[final](native-materialization.json) materializations have identical
generated Rust, scalar inputs, and 43 packaged dependency hashes.
The final materializer resolves inherited source paths from the
current checkout and emits crate-relative includes, so it can run on
Linux without this Mac's filesystem path. The serial Linux correctness
replay remains a separate gate; no controlled wall-time ratio is
reported here.

The [Linux dispatch receipt](remote-dispatch.json) pins source commit
`38bb34b7aa09cf33203fcf5b68393dbd7053f2d2` and the staged script
hash. Job `20261011T031406Z_prime-j0-adic-orbit-linux-38bb34b_XNwlQE`
is queued in the serial RunPod runner behind its existing active job.
This records dispatch, not a completed Linux result.

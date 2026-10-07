# Native scalar-input correctness gate

Freeze the Rust source, this protocol, and `run_full_replay.py` before
release execution. The Rust program must take each scalar in the two
already frozen Sage fixtures and independently compute its short
`a+bτ` representative and width-four digit stream. The lattice basis,
endomorphism eigenvalue, and subgroup order are copied exactly from
`../prime-j0-secp256k1-scalar/result.json`, whose provenance is retained
in the replay receipt. The nine digit seeds and unit-orbit mapping are
copied from `../prime-j0-cost-aware-chain/run.py`.

On every case, compare the native representative and every digit with
the frozen Sage values. Then evaluate those **native digits** using the
native Jacobian path, compare each prepared seed and final point with
Sage, and compare the operation counts. Run both fixtures with a single
offline locked release binary: the original 64 one-use random cases and
the 30 edge cases covering three bases and scalar values
`0,1,2,3,4,7,8,n−1,n,n+1`. Retain source, fixture, binary, compiler,
host, command, stdout/stderr, and exit-code evidence. Any mismatch
must exit nonzero.

This is a variable-time research implementation. Its scalar-input API
is exposed only by the replay executable, and no secret-scalar safety or
CPU timing claim follows. Cached Jacobian exceptional inputs and broader
random coverage remain independent correctness gates. CPU speedup stays
unknown until a paired full-operation run has a host-isolation receipt.

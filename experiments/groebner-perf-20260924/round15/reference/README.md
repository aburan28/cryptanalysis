# Frozen independent verifier

These two files are byte-for-byte copies from repository commit
`7a3ac6daa4817ba3bcd43a508bdcc42e6622673b`:

- `experiments/pdp-scaling/boolean_certificate.cpp`
- `experiments/groebner-perf-20260924/round4/packed_certificate.cpp`

`build.py` checks their pinned SHA-256 digests before compiling. For the baseline
it only redirects the packed decoder's include to the frozen core. For the two
optimized arms it changes exactly one unconditional row sort to a sortedness
check followed by the original sort when necessary. The generated sources and
compiled libraries have hashes in the build receipt. The shared-order decoder
is maintained separately in `ordered_certificate.cpp`.

No live earlier-round source or historical measurement is rewritten.

# U14 sector digit with one XYZZ accumulator

Format 158 keeps format 130's 14 sector-digit windows, exact fixed-limb
representative, point table, and grouped unit order. Its evaluator uses the
existing XYZZ mixed addition and Solinas unit rotation, with one accumulator.
The table remains 64,314,112 bytes; the Solinas constants add 96 bytes, for
64,314,208 retained bytes. Format 130 is the paired native
control because only the accumulator formulas and rotation implementation
change.

The native correctness gate replays all 4,096 scalars in
`../prime-j0-sector-digit-20261010/fresh-inputs.json`, comparing complete
format-130 and format-158 return records, and checks the first 128 points
against the independent binary multiplication implementation. A release build
must also accept the opt-in `--check-scalar-unit-orbit-u256-sector14-xyzz-fixed-fixture`
command. Keep exact source, input, and build hashes with the results.

The paired arithmetic screen in
`../prime-j0-u14-u12-paired-20261012/README.md` motivates this implementation.
The model excludes table construction, scalar selection and recoding, final
inversion, cache misses, and exceptional formulas. Measure full native
operations only after the correctness gate. Promote a CPU timing ratio only
with the receipt required by `../../docs/ISOLATED_BENCHMARKS.md`.

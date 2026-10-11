# Exhaustive selective carry closure

The source and protocol were frozen in `b5a6d9bc` before the closure
audit ran. The audit allowed **every one of the 81 input residues at
every reached carry**. This is a conservative superset of all valid
width-four scalar streams, so closure of this graph bounds the native
selector for every scalar input under the fixed original and linked
digit tables.

The reached set stabilized after 11 growth rounds at **715 carries**.
Its largest Eisenstein norm is **432**, and no coordinate has absolute
value greater than **36**. The exact sorted state-set SHA-256 is
`09aa4e9c658678ccf656d417f3733954df2dd1fd91aff2691dc590951c87f3fe`.
The raw result, including generation sizes and all source hashes, is
`carry-closure-result.json` (SHA-256
`fcdef1f22035d4da9bb1bdf3e8b89432d42ea1c4f1de43758e58f5298cdf194f`).

The native selector now stores each carry coordinate as `i8` and
checks the tighter norm bound on every transition. Its compiled
`State` is **10 bytes** on the replayed macOS ARM64 build; the previous
two-`i64` layout had 24 bytes of fields before any padding. This
reduces the key size used in the selector's hash map. It does not
change digit choices, preparation, or the evaluator.

The offline release replay in `native-selective-checks-v7.json`
(SHA-256
`94a306f3684dafb12b2bb65dd632c397d15dc0f31dc604edc719fd657a023856`)
passed the original 64-case and portfolio regressions and again
matched independent Sage seeds and scalar outputs on all **320
selective cases**. It checked 608 built seed points on the design
panel and 2,449 on the holdout. The native panel maxima were 108 for
carry norm, below the all-residue bound of 432. Both panels reproduced
their saved source costs, and neither had an exceptional cached add.
The replayed binary SHA-256 is
`f03ffcec2b2b003a48ed69d3ec2650fa2efcc916dd3c2fa6f93a9f1a81de15aa`.

This is a **state-size and correctness result**. No isolated CPU run
has measured a speedup. The selector is variable-time and is not
suitable for secret scalars without further work. Academic novelty
is unproved.

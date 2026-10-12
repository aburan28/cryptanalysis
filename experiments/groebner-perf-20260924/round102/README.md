# Bounded independent bitsets for proof values

The round101 matrix producer completed more frozen cases, but the original
completed nine-variable query became slower because proof verification dominated.
This experiment changes the independent checker's proof-DAG value representation
for Boolean rings with at most twelve variables. Each monomial mask indexes one
coefficient bit. XOR uses machine words; multiplication still checks every set
coefficient and toggles collisions under Boolean monomial multiplication.

The original hash-set arithmetic remains responsible for reverse ideal inclusion,
reducedness, and all required Boolean Buchberger completion checks. The dense
checker consumes original packed input bytes independently. It never accepts a
producer's numerical rows or pivots without checking the derivation. Every unused
proof node is also validated. Larger rings use the existing sparse verifier.

The new path is opt-in. Its default byte limit is 128 MiB, covering proof-value
vector storage, last-use counters, and dense coefficient payloads. The limit
excludes allocator bookkeeping and the unchanged original/basis hash sets;
process peak RSS is reported separately. Allocation, operation, or logical-term
budget exhaustion remains inconclusive and consumes its charged work before any
producer fallback. There is no fallback that silently resets a budget.

Reference term charges are retained. Dense initialization, word scans/XORs,
popcounts, input conversion, and final basis comparisons add work charges. Logical
term liveness and cumulative terms keep their existing meanings. Memory and work
counters are independently checked against proof structure in the evidence audit.

The frozen `panel.json` pairs F4/hash, F4/dense, degree-two Macaulay/hash, and
degree-two Macaulay/dense on the same thirteen inputs as round101. A complete query
includes target-dependent descent, production, certification, proof materialization,
bounded root extraction, independent equations/curve replay, and lease teardown.
Target-independent fixtures and layouts are prepared separately. Every attempt,
failure, and fallback remains recorded. These are CPU-only component diagnostics,
not complete IC runs; CPU timing gains require an isolation receipt.

Run `python3 experiments/groebner-perf-20260924/round102/run_validation.py --output DIR`
for fresh optimized/UBSan builds, arithmetic and adversarial controls, complete
queries, and the native-free artifact audit. Add `--diagnostics` for the preset
one-warmup/four-observation panel. Commit sources before running either command.

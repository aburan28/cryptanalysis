# Output parity and independent verification

The retained Macaulay proof contains input leaves, multiplication nodes whose
operand is an input leaf, and XOR nodes. For k outputs, associate a k-bit mask
with every node. Seed output j with bit j, then scan nodes in reverse topological
order. At an XOR node, XOR its mask into both operands. At an input or input-times-
monomial leaf, emit that value into precisely the output sums named by its mask.
Over GF(2), two uses of the same value in one output cancel. Reverse propagation
therefore preserves each output polynomial by distributivity and linearity.

The implementation uses a 64-bit mask and accepts at most 64 outputs. Input
nodes in the new graph are shared by equation index; other leaves and output
accumulations follow deterministic reverse traversal order. Each node is
emitted after its dependencies. The basis rows and their order do not change.
If an output has no surviving leaf, retain the old graph; no special zero-row
certificate is invented.

This argument proves an identity between witnesses, not that the matrix is
complete. The unchanged checker independently reconstructs the new graph from
the original equations, checks both ideal inclusions, reducedness, critical
pairs and implicit Boolean field pairs. PDP controls additionally require the
unchanged independent equation checks and curve replay. Native-free matrix
and parity models reproduce the complete producer counters and proof graph.

## Bounds, fallback and accounting

- Mode 0 disables compression; mode 1 attempts it. Other modes are invalid.
- Zero or more than 64 outputs retain the existing graph, with planning work
  charged. Bit 63 is tested; no shift by 64 is performed.
- The metadata cap is 8 MiB by default. Its precise payload is
  `8 * retained_nodes + 4 * (equations + outputs)` bytes for output-parity,
  input-index and output-index arrays. Check the cap before allocating them.
  Proof vectors, basis coefficients and allocator metadata are outside this
  cap and retain their separate bounds. Process peak RSS is recorded.
- A replacement may contain strictly fewer nodes than the original retained
  graph. Stop and retain the original graph before emitting a node that would
  violate that condition. This also preserves the original producer node cap.
- The original proof is immutable until replacement succeeds. Byte, output,
  node-count and unsupported-shape fallbacks preserve it. All work already
  attempted by the transformation stays charged.
- Charge planning, metadata initialization, output seeding, reverse-node
  inspections, parity edges, input lookup, multiplication-leaf validation,
  emitted nodes, output incidences and final output validation. These are
  declared software charges, not calibrated machine instructions.
- Work-budget exhaustion discards the matrix call. F4 fallback receives only
  the remaining producer and checker budgets, including the transform's work.
  It does not get a new budget or an uncharged retry of the old proof.
- ParityStats.work is the attempted transformation's charge. The unchanged
  MatrixStats.nodes counts the original elimination DAG; output_nodes counts
  the retained proof after successful replacement. A budget failure can retain
  the already computed pre-transform output count even though no proof escapes.
- The transformation occurs after ordinary graph pruning, inside the existing
  producer extraction interval. ParityStats.total_seconds is a nested timing,
  not an additional phase to sum. No target-dependent data crosses queries.

For a bounded number of outputs, parity propagation is linear in retained graph
size. Emission is proportional to surviving leaf/output incidences, which can
be large; fallback bounds the resulting node count. The original derivation
is still produced and pruned. This changes proof representation and checking
cost, not the degree-of-regularity bound for a general Gröbner computation.

## Frozen comparison

Retain the round106 13-case fixture, degree bounds, budgets, 60-second worker
timeout, one warmup and four rotated observations. Compare matrix-minimal with
matrix-parity; f4-quotient is the unchanged coverage control. All failures and
fallback costs stay in the evidence. The same packed output API is used on
both matrix arms. Three arms are not perfectly position-balanced in four
observations; local times remain exploratory and aggregate speedup stays null.

The complete query includes fresh coefficient descent, native production and
certification, proof materialization, bounded extraction, independent equation
and curve replay, and lease teardown. Reusable layout setup and optional proof
serialization/list decoding remain separately reported. This is a planted
control study, not a natural relation-yield estimate or an IC/rho comparison.

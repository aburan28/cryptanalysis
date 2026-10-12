# Budget-optimal tau cover experiment

1. Run `python3 construct.py`, `python3 verify.py`,
   `python3 build_native_atlas.py`, and `python3 verify_native_atlas.py`
   from this directory. Retain the cover, atlas, and JSON receipts.
2. Freeze the candidate source, verifiers, cover, and atlas in a commit.
   Draw a new 4,096-scalar panel only after that commit, using
   `make_inputs.py --frozen-commit COMMIT`. Check modular disjointness
   against the listed earlier panels.
3. On that panel, compare the previous exact-size phase-optimal cover and
   this budget-optimal cover on the same scalars. Save every digit path,
   residual, term count, grouped-unit rotation count, and 128 independent
   binary point fixtures. Replay the complete panel in the native evaluator.
4. Treat point outputs, operation counts, and table size as correctness and
   algorithmic evidence. A CPU wall-time comparison requires the isolation
   and noise receipt described in `../../docs/ISOLATED_BENCHMARKS.md`.

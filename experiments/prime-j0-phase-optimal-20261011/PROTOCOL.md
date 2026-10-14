# Phase-optimal tau cover experiment

1. Run `python3 construct.py`, then `python3 verify.py` and
   `python3 build_native_atlas.py`, followed by
   `python3 verify_native_atlas.py` from this directory. The first
   verifier uses a separate quotient implementation and Boolean-state
   cycle DP. The native verifier decodes the DR20 atlas for every radix
   residue and checks the inverse unit action.
2. Freeze the constructor, verifiers, panel tools, cover and atlas in a
   commit. Only then run `make_inputs.py --frozen-commit COMMIT` to draw
   4,096 scalars disjoint from the listed earlier panels.
3. Run `replay_holdout.py` and `verify_holdout.py`. Compare the candidate
   with the older exact-size tau cover on the same scalar and record all
   recoding paths, residuals, and the first 128 independent binary point
   fixtures. The native materializer must check all 4,096 group outputs.
4. Treat local point and operation counts as correctness and algorithmic
   evidence. Promote a CPU wall-time ratio only with the host-isolation
   and noise receipt in `../../docs/ISOLATED_BENCHMARKS.md`.

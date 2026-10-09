# Reusable scratch buffers in certified F4 normalization

The five frozen hard point-decomposition queries spend 48.5–61.6% of
deterministic F4 work in initial generator reduction. The `round117` bounded
divisor table preserved proof bytes but did not yield a stable complete-query
improvement. This opt-in candidate instead removes repeated vector allocation
inside each reduction step. It retains the `round116` initial matrix batch
and the same reducer priority.

`normal()` previously constructed a fresh multiplied reducer and a fresh XOR
output for every step. The candidate reuses two local `std::vector` buffers
across the steps of one normalization. It performs the same OR multiplication,
grevlex sort, parity cancellation and symmetric difference in the same order.
It charges the same canonicalization and addition work units and emits the
same proof nodes in the same order. The buffers end with their normalization
call, so no target coefficients or numerical state persist into a new query.
The candidate remains opt-in and uses the same producer, proof-node, row, and
checker limits.

The frozen validation compares every optimized and UBSan result with the
independently audited `round112` reference: reduced basis, assignment,
original equations, curve replay, and native certificate checks must agree.
The paired profile also requires exact proof-byte and work-counter parity
with the `round116` batch baseline. The 21-, 32-, and 64-variable controls check algebraic proof
certificates and reject corrupted output. Five alternating AB/BA repetitions
pair full target-dependent queries against the `round116` batch baseline,
retaining all failures and warmups. A controlled CPU speedup requires a
qualifying isolated-host receipt.

Run the candidate against a source-matched reference build:

```sh
python3 experiments/groebner-perf-20260924/round118/build.py \
  --reference-root /absolute/source-matched/reference
GROEBNER_F4_REFERENCE_ROOT=/absolute/source-matched/reference \
  python3 experiments/groebner-perf-20260924/round118/panel.py \
  --reference-report /absolute/audited/round112/panel/report.json \
  --output /absolute/new/scratch-panel
GROEBNER_F4_REFERENCE_ROOT=/absolute/source-matched/reference \
  python3 experiments/groebner-perf-20260924/round118/test_large.py \
  --output /absolute/new/scratch-large.json
python3 experiments/groebner-perf-20260924/round118/profile.py \
  --reference-root /absolute/source-matched/reference \
  --reference-report /absolute/audited/round112/panel/report.json \
  --output /absolute/new/scratch-profile --reps 5
```

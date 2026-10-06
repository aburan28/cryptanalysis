# Explicit batching for Sage binary Frobenius point maps

This archive adds `FrobeniusPlan.apply_batches(batches)`. It accepts an outer
iterable of independent point iterables, maps them with one existing backend
dispatch, and returns one list per input batch. It preserves empty batches,
point order, field and curve validation, and the plan's existing packed
working-set cap. The implementation is backend-neutral; it changes neither
the Metal kernel nor automatic routing. The installed Sage source and native
library were left unchanged during measurement.

`baseline/` is the exact installed Sage source before this experiment,
`source/` is the proposed source, and `metal-batched-point-maps.patch` is a
standalone patch against that Sage path. `intent.json` and `intent-cold.json`
were frozen before their respective measured runs. The 32-point smoke was
completed before freezing the warm intent. `run-001/` contains four fresh
Sage processes, each with twelve rotating and reversing orders of separate
Metal, batched Metal, separate CPU, and batched CPU full point calls.
`run-cold-001/` contains eight separate-process setup-plus-first-call
measurements. Every measured output group was compared with ordinary Sage
Frobenius results; `test_batches.py` additionally exercises iterator inputs,
empty batches, foreign-curve rejection, and closed-plan behavior across
Sage, CPU, and Metal.

Portable archive verification:

```sh
python3 experiments/sage-ic-campaign/metal-batched-point-maps-20260924/verify_archive.py
```

On the same Apple Metal Sage installation, rerun `python3 run.py` and
`python3 run_cold.py` from this directory after removing or renaming the
existing output directories. The runners keep Sage's cache under
`/private/tmp`. See `RESULT.md` for the measured scope and routing decision.

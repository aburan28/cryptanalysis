# Source pilot receipt retry

The first projective source pilot invocation ended before solver launch with
`KeyError: cryptominisat_maxtime_seconds`. The runner correction was committed
before the second invocation. That invocation started CryptoMiniSat and
preserved stdout/stderr but raised `KeyError: query_index` while writing its
receipt after the solver process exited. The raw stdout records a substantial
bounded search but has no terminal `s` line, and the exact wrapper wall/RSS
values were lost with the Python process. Its
[`PRODUCER_FAILURE` receipt](runs/R1/source_projective_pilot_failed_receipt.json)
keeps the transcript hashes and missing fields explicit.

Allow exactly one source retry with unchanged formula SHA-256, public point,
binary, one-thread `--maxtime=120`, 150-second external wall cap, and 4-GiB
RSS guard. Store it under `source_projective_pilot_retry1.*`; preserve both
earlier failures. Run the descendant arm once after this complete source
receipt. The paired solver diagnostic uses the complete retry receipt, while
the earlier source search remains a separate failed-producer row. No other
retry is authorized by this amendment. No CPU wall-time speedup can be
promoted from these unisolated, sequential cells.

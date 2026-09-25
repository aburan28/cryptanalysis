# Held polynomial-basis half-trace pilot

`CurvePb.halfTrace` computes a sum of conjugates by repeated squaring. This
pilot tests a cached linear map: compute the half trace of every polynomial
basis vector once, then XOR the images selected by the input bits. The code
is in `pilot.py` only; no production arithmetic changes in this branch.

The frozen intent binds the exact field, curve, and pilot sources by SHA-256.
Two fresh-seed runs cover degrees 11, 15, 53, and 131. Each cell records
exact point-recovery agreement, the first single call, cold batches of 64,
256, and 1024 complete `pointFromX` calls, eight balanced warm rounds at 256
calls, and peak RSS. The cold batches include image-table construction.
Fixture generation is excluded from the measured calls.

The warm large-field improvement is real, but the degree-53 and degree-131
cold 64-point batches regress in both runs. Degree-131 cold 256-point batches
straddle parity. The automatic path is held. A future explicit bulk API
would need a declared target count and complete IC accounting, including
table construction and all other phases, before promotion.

Recheck the receipts with:

```sh
python3 experiments/sage-ic-campaign/pb-halftrace-pilot-20260924/verify_archive.py
```

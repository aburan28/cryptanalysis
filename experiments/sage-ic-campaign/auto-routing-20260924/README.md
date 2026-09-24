# Conservative automatic Sage CPU routing

[`auto-cpu.patch`](auto-cpu.patch) applies after the preceding Sage batch,
hardware, output codec, and input codec patches (PRs #68, #72, #73, #74,
and #75). It changes `FrobeniusPlan(..., backend='auto')` only. For an exact
list or tuple of at least 4,096 points on a degree-67 or degree-131
Koblitz curve with normalized Frobenius power 65, it creates a portable CPU
table plan on the first call and reuses it. Other calls keep the native Sage
path. If the optional CPU library cannot initialize, auto stays on Sage.
Explicit backend requests retain their existing behavior.

The threshold comes from the paired `run-001/` cold-cost map, with plan
construction and first verified call charged. `run-002/` tested the first
implementation on fresh inputs. `run-003/` repeated it with 48 balanced
fresh-plan pairs and eight warm calls per arm. Both runs show large cold
gains on routed cells. Both also have nonrouted wall-time control cells
below the strict 0.98× cutoff despite those paths calling the same Sage
function. These failures remain in the archive. `control-001/` isolates the
predicate on one plan, verifies that the nonrouted call goes directly to
Sage, and bounds its additional cost at about 0.12 microseconds. See
[RESULT.md](RESULT.md) for the exact values and limitation.

The patch is tied to `source/binary_hardware.py`. The standalone patch,
exact source snapshot, frozen intents, raw receipts, and test logs can be
checked without Sage:

```sh
python3 experiments/sage-ic-campaign/auto-routing-20260924/verify_archive.py
```

For a newly built patched Sage, run `test_auto.py` with Sage's Python
interpreter and the installed hardware suite from the hardware package.
The stored runners refer to the local historical Sage layout; their JSON
receipts and patch are portable, while performance must be remeasured on
another host.

The nearby [Metal phase profile](../metal-transfer-20260924/RESULT.md)
shows that the GPU command is only a small part of complete Metal calls
in the tested sizes. This patch routes to portable CPU, not Metal. It
does not establish a complete index-calculus speedup.

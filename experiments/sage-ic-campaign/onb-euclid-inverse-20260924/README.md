# Public ONB Euclid inversion

The public `Onb.inv` method in both local and IC runner field copies now uses
extended Euclid for canonical nonzero ONB elements. Zero and noncanonical raw
vectors retain the previous exponentiation route and its observable result.
The IC runner's `AuditField` already had its own Euclid override; this change
accelerates public field and curve calls without changing that runner method.

`intent.json` froze workloads and gates before the edit. The exact parent
source is in `baseline/field.py`; `run-a.json` and `run-b.json` are alternating
paired warm timings, while `cold-a.json` and `cold-b.json` contain two sets of
seven fresh processes per variant and point outcome. Run the archive checker
from repository root:

```sh
python3 experiments/sage-ic-campaign/onb-euclid-inverse-20260924/verify_archive.py
```

These measurements concern public ONB arithmetic stages. They do not give a
complete verified IC or DLP cost.

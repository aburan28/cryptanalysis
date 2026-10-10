# Native nineteen-window tau scalar prototype

The nineteen-window layout uses three radix-64 rows, fifteen radix-128
rows, and a final radix-64 row with digit bound 44. Its exact cycle-cover
construction stores 21,949 affine slots. The native scratch build retains
**1,512,020 bytes**, including the three atlases and table metadata. That
is 3,041,120 bytes less than the verified seventeen-window native table.

`native-frontier19-delta.patch` extends the frozen seventeen-window patch
from `prime-j0-tau-frontier-native-prototype-20261010`. Both patches apply
sequentially to base commit `f8cb6c314`. `verify_receipt.py` reconstructs
the resulting source in a temporary Git index, checks its source hashes,
the atlas hashes, and the native test log. This keeps the shared native
files free while another coordinated task holds their write reservation.

The scratch implementation introduces mode 138
(`unit_orbit_u256_tau_frontier19_fixed`). It checks every atlas residue,
builds the two tau buckets, and uses the same binary-inverse finalizer as
the seventeen-window mode. Native release tests independently formed and
checked all **21,930 nonidentity stored points**. A separate native test
matched all 4,096 scalars in the prior radix-384 panel, including 128
direct binary-point checks. The complete release suite passed **102/102**.

The patch, receipt, input generator, and independent binary fixture
generator were frozen in commit `6f04f10ef` before drawing a new
4,096-scalar panel with seed `20261010139`. The panel excludes every
earlier listed scalar panel, including the seventeen-window fresh panel.
The nineteen-window evaluator and the seventeen-window control each
matched every expected point. [FRESH_RESULTS.md](FRESH_RESULTS.md) records
the evidence. Replay the committed checks from the repository root:

```sh
python3 experiments/prime-j0-tau-frontier19-native-prototype-20261010/verify_inputs.py
python3 experiments/prime-j0-tau-frontier19-native-prototype-20261010/verify_receipt.py
python3 experiments/prime-j0-tau-frontier19-native-prototype-20261010/verify_fresh.py
```

The runs are correctness and retained-allocation evidence. The public
scalar evaluator uses scalar-dependent atlas and table indices. Any
online speed comparison requires a paired isolated-host receipt and an
appropriate constant-time policy before secret-scalar use.

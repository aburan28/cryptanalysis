# Operation frontier for tau cycle-cover scalar formats

The frozen 4,096-scalar panel gives a precise storage-versus-group-call
tradeoff for the radix-384 reference and the minimum-byte 16–19-window
power-of-two layouts. Each additional power-of-two window saves table
storage and adds approximately one mixed-add call per scalar. The
17-window layout uses **45.39% fewer pre-metadata table bytes** than the
16-window layout and makes 4,097 more mixed-add calls across the panel.

| Layout | Table bytes before metadata | Atlas reads per scalar | Mixed-add calls, total | Mixed-add calls per scalar | Gauge bucket rotations, total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Radix-384, 15 windows | 18,013,168 | 15 | 61,440 | 15.0000 | 15,022 |
| Power-of-two, 16 windows | 8,336,160 | 16 | 65,534 | 15.9995 | 15,889 |
| Power-of-two, 17 windows | 4,552,716 | 17 | 69,631 | 16.9998 | 15,993 |
| Power-of-two, 18 windows | 2,805,196 | 18 | 73,726 | 17.9995 | 16,059 |
| Power-of-two, 19 windows | 1,511,564 | 19 | 77,814 | 18.9976 | 16,143 |

The 18-window layout saves a further 1,747,520 bytes relative to 17
windows and makes 4,095 more mixed-add calls on this panel. The
19-window layout saves another 1,293,632 bytes and makes 4,088 more
mixed-add calls. All four power-of-two layouts occupy both final
buckets for every scalar in this panel. The radix-384 layout occupies
both final buckets in 4,048 of 4,096 cases.

`analyze.py` reads the committed atlases and the post-freeze scalar panel
from `prime-j0-tau-frontier-native-prototype-20261010`. It selects the
four-corner Eisenstein representative, decodes every digit, checks its
norm and residue, reconstructs the complete representative, and counts
the exact calls made by the corresponding two-bucket loop. A first
point in each bucket enters through an identity shortcut; `result.json`
separately records all mixed-add calls and nontrivial mixed additions.
It also records full count histograms, source and input hashes, atlas
hashes, occupied buckets, final merge and tau calls, sign operations,
and gauge rotations.

Run from the repository root:

```sh
python3 experiments/prime-j0-tau-frontier-cost-20261010/analyze.py
```

These are exact **recoding and call-count diagnostics** for this Python
four-corner policy. They do not measure field operations, cache misses,
online wall time, or the exact instruction stream of the native fixed-limb
representative. The native 17-window prototype has separate group-point
and fresh-panel correctness receipts. The next native comparison should
instrument the 16–19-window evaluators, pair them on this scalar panel,
and run the timing panel on a host that passes the isolated benchmark
preflight. The current RunPod Pod fails that preflight.

# XOR-matrix limit diagnostic on the N83 fixed-target formula

The [fixed-target width-16 run](../n83-geometric-m5-fixedtarget16-20261012/README.md)
reached its 600-second cap. CryptoMiniSat's default 1,000-column XOR
matrix limit excludes the four connected components of its native-XOR
system whose largest sizes are 332 by 20,916, 348 by 15,470, and 415 by
7,387 variables. This stage diagnostic compares three solver settings on
the exact same archived XCNF and public point:

| Arm | Extra CryptoMiniSat flags | Bound |
| --- | --- | ---: |
| `default` | none | 60 s |
| `maxcols25000` | `--maxmatrixcols 25000` | 60 s |
| `maxcols25000_persistent` | `--maxmatrixcols 25000 --autodisablegauss 0` | 60 s |

All three arms reached their 60-second external caps with no model. The
last printed cumulative restart counter is a lower bound on each arm's
conflicts, since the external stop prevented terminal solver statistics:

| Arm | XOR matrices reported | Last restart conflict counter | Sampled peak RSS |
| --- | ---: | ---: | ---: |
| `default` | 0 | 273K | 194,592,768 bytes |
| `maxcols25000` | 4 | 176K | 90,734,592 bytes |
| `maxcols25000_persistent` | 4 | 41K | 79,839,232 bytes |

With the raised column limit, CryptoMiniSat printed 170 messages that the
matrices were performing badly. Keeping them enabled reduced conflict
throughput much further. The receipt verifier passed the source, input,
logs, limits, arm order, and matrix reports. This pilot gives no reason to
extend the matrix setting to a 600-second ordinary-target run on this
formula; conflict count is a search diagnostic, not a relation-yield
measurement.

The [protocol](protocol.json) binds the parent result and XCNF hashes,
solver binary, source, arm order, five-million-conflict limit, one solver
thread, and 4 GiB sampled RSS stop. Each arm retains raw stdout and stderr,
return code, conflicts, matrix initialization reports, wall time, and
sampled memory peak. A SAT model is replayed against the exact base and
public point; the diagnostic stops after a verified relation. These are
solver-stage observations on a shared host, so CPU timing is exploratory.

Use the checked repository Sage launcher to record and execute this local
experiment:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-gauss25k-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-gauss25k-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-gauss25k-20261012/run.py
python3 experiments/n83-geometric-m5-gauss25k-20261012/verify.py
```

The runner refuses to overwrite terminal evidence. Reproduce with a
fresh directory and the supplied frozen public protocol.

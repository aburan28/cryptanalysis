# Metal host bridge timing and routing stability

The standalone bridge was compiled from the installed-source snapshot with
timers around buffer allocation, input copy, command setup, submit/wait, and
output copy. The installed Sage library was untouched. Both bridges returned
ordinary Sage points exactly equal to native Frobenius results in twelve
alternating calls per cell. SHA-256 identities of sources, scripts, and the
temporary binary are frozen in the intents and receipts.

| Points | Run | Input + output copies ms | Command setup ms | Submit/wait ms | Device ms | Bridge total ms |
| ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| 1,024 | A | 0.002 | 0.006 | 0.117 | 0.007 | 0.122 |
| 1,024 | B | 0.002 | 0.006 | 0.256 | 0.027 | 0.265 |
| 4,096 | A | 0.006 | 0.017 | 0.166 | 0.009 | 0.186 |
| 4,096 | B | 0.006 | 0.016 | 0.134 | 0.009 | 0.154 |
| 16,384 | A | 0.019 | 0.022 | 0.603 | 0.093 | 0.642 |
| 16,384 | B | 0.019 | 0.017 | 0.187 | 0.023 | 0.226 |

These are medians of per-call timers inside the instrumented native bridge.
Allocation was zero in warm calls because the existing input/output Metal
buffers were reused. The copies are a small portion of the bridge call;
submit/wait dominates its measured cost and varies substantially, especially
at 16,384 points. The installed and instrumented complete-call medians were
close within each process, supporting timing instrumentation as a diagnostic
rather than a production speedup. The instrumented bridge is not proposed
for installation.

The earlier frozen current-source three-arm rebaseline had much slower
absolute times. Four identical-seed cells were rerun with the **same**
installed module and native binary to check whether the CPU/Metal ordering
survived that timing change:

| Points | Seed run | Earlier CPU / Metal ms | Recheck CPU / Metal ms |
| ---: | :---: | ---: | ---: |
| 1,024 | A | 1.576 / 3.240 | 0.638 / 1.089 |
| 4,096 | A | 4.207 / 8.293 | 2.335 / 2.696 |
| 1,024 | B | 1.612 / 3.264 | 0.639 / 0.849 |
| 4,096 | B | 2.456 / 7.270 | 2.384 / 2.516 |

Absolute timings changed enough that no fixed Metal dispatch threshold should
be promoted from one timing regime. The CPU plan still won these four
complete-call repeats. The next implementation candidate is to batch
independent point maps into fewer Metal command submissions or overlap host
work with an in-flight command, then compare exact complete point calls,
cold setup, and peak RSS against both CPU and native Sage. Removing the
current host copies alone cannot explain the measured bridge gap.

These are Sage point-map stages. They do not measure the full IC runner,
recover a logarithm, or establish a calibrated DLP speedup.

# Metal call profile after the two codec optimizations

Four fresh workers each ran 12 rounds of four exact Sage-point calls on the
installed Apple M4 Pro backend. Each call was split into exclusive packing,
Metal API, point reconstruction, exact verification, and cleanup phases.
GPU command duration is a diagnostic subset of Metal API time. Source and
binary hashes are frozen in `intent-v1.json` and each cell receipt.

| GF(2^m) | Points | Power | Complete call ms | Packing share | Metal API share | Unpacking share | GPU command / Metal API |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 19 | 1,024 | 1 | 1.058 | 9.3% | 21.7% | 46.1% | 1.5% |
| 131 | 1,024 | 65 | 2.189 | 8.7% | 43.2% | 27.1% | 0.9% |
| 131 | 4,096 | 65 | 4.809 | 12.6% | 18.5% | 37.7% | 1.1% |
| 131 | 16,384 | 65 | 19.368 | 10.3% | 10.7% | 44.2% | 4.6% |

The device command is a small share of Metal API time, so changing shader
arithmetic alone has little complete-call headroom in these cases. The
timings do not isolate host copies from command creation and synchronization.
Metal also remained slower than table CPU in the earlier complete-API
rebaseline. The separate [auto-routing experiment](../auto-routing-20260924/RESULT.md)
tests whether a portable CPU table plan wins for high-power maps after
charging cold setup.

These are local stage timings, not an end-to-end index-calculus result.

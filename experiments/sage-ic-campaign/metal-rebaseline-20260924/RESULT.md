# Metal and CPU rebaseline after native Sage Frobenius

The installed native `frobenius_points` is the new reference for these public
Koblitz point-map calls. `run-002/` ran seven fresh workers with twelve
balanced three-arm rounds each. Every call returned exact Sage points and was
checked against the common expected result. Complete timing includes packing,
the table map or native squaring, transfers, point reconstruction, exact
verification, and cleanup. Setup and first-call cost are separate in each
receipt. `run-001/` failed before timing because the sandbox could not enumerate
the Apple Metal device; it is retained and not pooled with `run-002/`.

| GF(2^m) | Points | Power | Native Sage ms | Table CPU ms | Metal ms | CPU/native | Metal/native |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 19 | 1,024 | 1 | 1.848 | 2.892 | 4.847 | 0.639x | 0.381x |
| 131 | 1,024 | 1 | 1.871 | 3.610 | 4.841 | 0.518x | 0.386x |
| 131 | 4,096 | 1 | 6.772 | 10.060 | 14.884 | 0.673x | 0.455x |
| 131 | 16,384 | 1 | 26.420 | 41.514 | 55.687 | 0.636x | 0.474x |
| 131 | 4,096 | 65 | 38.244 | 10.861 | 11.385 | 3.521x | 3.359x |
| 131 | 16,384 | 65 | 168.032 | 52.523 | 52.992 | 3.199x | 3.171x |
| 67 | 4,096 | 7 | 8.728 | 9.316 | 24.509 | 0.937x | 0.356x |

For one-step maps, native NTL wins every tested cell. At degree 131 and power
65, both table plans win, but Metal does not beat the CPU plan on the complete
call. In the degree-131, 4,096-point, power-65 cell, the median packed Metal
call is 0.957 ms and the device command reports 0.014 ms; the complete Metal
call is 11.385 ms. That points first to point conversion and host/command
overhead, with kernel arithmetic a much smaller share. These are local
measurements on a shared Apple M4 Pro host, not a universal dispatch rule.

Next step: optimize `binary_hardware_codec.pyx:unpack_points`, which currently
calls the general point constructor once per output. Compare old and new codec
under identical CPU and Metal plans, charge exact verification, and preserve
custom point-class behavior. Revisit Metal mapping and buffer lifetime after
that component is measured. No end-to-end IC claim follows from this stage.

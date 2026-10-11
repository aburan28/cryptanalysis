# Installed hardware foundation: local result

The retained `run-003` measured the installed CPU and Apple Metal backends
against the **older Python-based Sage Frobenius path**. It covers 18 primary
and four independent confirmation cells, each with 12 balanced arm-order
rounds and exact output agreement. Six broad test groups passed. Every
reported full-API call includes packing, transfer, computation, ordinary Sage
point construction, exact verification, and cleanup. Setup and first-call
costs are recorded separately in the receipts.

| Phase | Field degree | Points | Power | CPU vs old Sage | Metal vs old Sage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Primary | 19 | 1024 | 1 | 1.092× | 0.946× |
| Primary | 19 | 1024 | 7 | 2.436× | 2.181× |
| Primary | 19 | 1024 | 65 | 2.444× | 2.189× |
| Primary | 19 | 16384 | 1 | 1.145× | 1.136× |
| Primary | 19 | 16384 | 7 | 2.436× | 2.148× |
| Primary | 19 | 16384 | 65 | 2.427× | 2.536× |
| Primary | 67 | 1024 | 1 | 1.087× | 0.799× |
| Primary | 67 | 1024 | 7 | 2.330× | 1.714× |
| Primary | 67 | 1024 | 65 | 26.004× | 18.936× |
| Primary | 67 | 16384 | 1 | 1.135× | 1.029× |
| Primary | 67 | 16384 | 7 | 1.723× | 2.234× |
| Primary | 67 | 16384 | 65 | 21.292× | 17.624× |
| Primary | 131 | 1024 | 1 | 1.027× | 0.898× |
| Primary | 131 | 1024 | 7 | 2.355× | 2.096× |
| Primary | 131 | 1024 | 65 | 21.952× | 20.984× |
| Primary | 131 | 16384 | 1 | 1.049× | 0.876× |
| Primary | 131 | 16384 | 7 | 2.432× | 2.228× |
| Primary | 131 | 16384 | 65 | 25.341× | 24.824× |
| Confirmation | 31 | 4096 | 7 | 2.714× | 2.609× |
| Confirmation | 31 | 4096 | 65 | 2.338× | 2.239× |
| Confirmation | 131 | 4096 | 7 | 2.314× | 2.253× |
| Confirmation | 131 | 4096 | 65 | 23.897× | 23.200× |

These ratios are historical diagnostics for the original hardware addition.
They must **not** be presented as gains over the newer native Sage path in
the preceding PR. The [fresh three-arm rebaseline](../sage-ic-campaign/metal-rebaseline-20260924/RESULT.md)
shows that native Sage wins in its tested power-1 cells, while reusable table
plans win in its tested power-65 cells. Metal was slower than table CPU for
the complete API in those new cells. The plan therefore keeps `auto` on Sage.

The native C++ self-test passed under x86-64 Rosetta and UBSan. No physical
x86 timing, CUDA/OpenCL hardware timing, or successful ASan run is claimed.
The original ASan process and a minimal startup control both timed out.
Hardware validation on other devices remains future work. The package
contains the exact source snapshots, patch, and retained installed benchmark
receipts. `verify_archive.py` checks source reconstruction and receipt
arithmetic without requiring the historical binaries.

The table concerns one public Koblitz Frobenius stage. It is not an
end-to-end index-calculus or discrete-logarithm result.

# Sage hardware compatibility — 2026-09-28

The accepted Sage 10.10.rc0 installation passes the new installed-build
compatibility suite on this ARM64 Mac and its Apple M4 Pro Metal GPU.
The portable CPU kernel also passes fresh ARM64 and x86-64 builds with
undefined-behavior sanitization. The x86-64 executable ran through Rosetta.
Physical Intel/AMD CPUs and NVIDIA/AMD/Intel GPU hardware remain unvalidated
by this run. No cross-device performance claim is made.

| Target and scope | Result | Evidence |
| --- | --- | --- |
| Installed scalar, batch, Cartesian, and fused operations on ARM64 | 6 test groups passed | `installed-002/scalar-and-batch.txt` |
| Installed CPU Frobenius backend and point codec on ARM64 | 6 test groups passed | `installed-002/cpu.txt` |
| Installed Metal Frobenius backend and point codec on Apple M4 Pro | 6 test groups passed | `installed-002/metal.txt` |
| Fresh portable CPU kernel, ARM64, UBSan | 30 cases passed | `native-arm64/receipt.json` |
| Fresh portable CPU kernel, x86-64 through Rosetta, UBSan | 30 cases passed | `native-x86_64/receipt.json` |
| OpenCL 1.2 generated kernel | Syntax check passed; no device execution | `opencl-syntax.json` |
| CUDA full Sage API | Unavailable: CuPy is not installed | `unavailable-backends/receipt.json` |
| OpenCL full Sage API | Unavailable: PyOpenCL is not installed | `unavailable-backends/receipt.json` |
| HIP/ROCm packed kernel | Not executed | Replay fixture supplied |
| Physical x86-64/Linux, 32-bit or big-endian hosts | Not executed | Target hardware/runtime still needed |

All 18 installed test groups have zero failures, errors, and skips.
The scalar oracle implements affine Weierstrass formulas using field elements,
independently of optimized point operations. Coverage includes exhaustive small
fields; negative, zero, and wide scalars; 32/64-bit word boundaries through
degree 257; changes to the active NTL modulus; alternate field representations;
custom-constructor fallback; point types, parents, hashes and serialization;
optional-native fallback; Cartesian and fused batch operations. Native-call
counters confirm that the new PARI input/result and batch-addition paths ran.
The hardware suite adds exhaustive maps, alternate moduli, infinity and
duplicate/inverse points, negative powers, codec replay, resource lifetime,
invalid-input checks and CPU thread counts, through degree 256.

`installed-002/receipt.json` binds the imported modules, native library and
codec, runtime manifest, test sources and device names. `runtime.json` records
the verified launcher and native dispatch. Both CPU executables return the
same independent-oracle checksum, `8353608333090390242`; this component result
does not validate the complete Sage stack on x86. The native build commands
use C++17 and explicit target architectures without host-specific ISA flags.

The first attempt, `installed-001`, is preserved. Its CPU backend passed,
but Metal was hidden by the sandbox. One new scalar test incorrectly assumed
that replacing a curve constructor must change the class of scalar outputs
from an existing point. The corrected test compares with Sage's existing
native-disabled fallback and the independent arithmetic oracle. The second
attempt ran with GPU access and passed. CUDA/OpenCL requests deliberately
return a failing overall receipt rather than silently skipping unavailable
backends.

## Reproduction

Use a new output directory for every run:

```sh
./sage -python experiments/sage-binary-hardware/validate_compatibility.py \
  --backends cpu,metal --out /tmp/new-installed-compatibility
python3 experiments/sage-binary-hardware/validate_native.py \
  --arch arm64 --ubsan --out /tmp/new-arm64-compatibility
python3 experiments/sage-binary-hardware/validate_native.py \
  --arch x86_64 --ubsan --out /tmp/new-x86-compatibility
```

On another machine, rebuild the optimized Sage fork for that host and run
the installed suite with its Sage launcher. Select `cpu`, `cuda`, or `opencl`
as appropriate. Use `validate_native.py --ubsan` without `--arch` on Linux.
The installed suite does not import archived Mac `.so` files.

`device-fixture/` contains 12 freshly generated Sage-verified fixtures and
the current CUDA/OpenCL kernel sources. It covers degrees 19, 31, 67 and 131
at powers 1, 7 and 65. Copy that directory and the saved
`sources/replay_device.py` to a target GPU machine with NumPy and the relevant
CuPy or PyOpenCL runtime:

```sh
python3 replay_device.py --backend cuda --fixture device-fixture --out cuda-check
# Use --backend hip or --backend opencl for those runtimes.
```

Replay validates packed field coordinates. Full Sage API correctness still
requires the installed suite, and speed claims require matched full-operation
benchmarks on the target device, including conversions and transfers.
`auto` routing remains conservative. No accepted arithmetic or dispatch code
was changed during this compatibility check.

## Published package

This checkout also supports the checked release launcher:
`python3 scripts/sage_release.py run --sage /path/to/built/sage -- -python ...`.
The two accepted follow-up patches now reconstruct all eleven release-source
files byte-for-byte to the installed build recorded here.

`local-MANIFEST.json` preserves the original complete local artifact inventory.
The two native self-test executables are omitted from Git; their recorded
hashes, build commands, source snapshots and results remain. `MANIFEST.json`
binds every distributed file and lists the omitted binaries explicitly.
The current native validator defaults to the shipped source snapshot so it
also works in a fresh checkout; use `--source` for a different source tree.
The historical validator and exact commands remain in `sources/`.

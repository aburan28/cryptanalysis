# Side-channel scope note — 2026-10-08

Which code in this repository would need constant-time (CT) treatment if it handled secrets, and which
of it actually does. Companion to the inventory of the `crypto` crate
(`crypto/docs/audits/SIDE_CHANNEL_AUDIT_20261008.md`), which this repository pulls in by path from four
experiment crates (`experiments/koblitz-s3-pair-query-20261006{,-v2}`,
`experiments/koblitz-cofactor-fiber-20260928/n53-root-multiplicity-build`,
`experiments/koblitz-n83-index-design-20260929/packed_index_e1_prefix_20261007`).

## 1. Verdict

Nothing in this repository handles long-lived secrets. The library, bindings, CUDA, FPGA, `ecc2k130`
and experiment code solve discrete logarithms on public inputs with planted, seeded known answers, at
sizes bounded by the 64-bit design limit or the published challenge curves. Constant time is not a
requirement for any of it, and no part of it claims to be CT. Two items deserve attention anyway (§3).

## 2. Variable-time inventory (for the record, in case any of it is ever reused on secrets)

| Area | Evidence | Why it is variable-time |
|---|---|---|
| 64-bit GF(p) | `include/cryptanalysis/ca_modarith.h:22-38, 67-76`; `src/modarith.c:10-21, 33-54, 175-193` | data-dependent `if` in add/sub, 128-bit `%` (`__umodti3`), conditional final subtraction in REDC, `if (exp & 1)` square-and-multiply, extended-Euclid `ca_invmod` behind every curve inversion (`src/group_ec.c:19`) |
| Scalar multiplication | `src/group_common.c:9-22` (`ca_group_mul`) | right-to-left double-and-add branching on scalar bits, early exit at the top bit |
| GLV / τ-adic (j = 0) | `src/ec_tau.c:177-226, 284-309, 407-495, 497, 559`; `src/curve.c:343-367` | i128 division in recoding, zero digits skipped, tables indexed by secret-derived digits; `experiments/prime-j0-tau-20260930/README.md:39-40` already says so |
| Affine group law | `src/group_ec.c:47-68` | exceptional-case branches, per-op inversion |
| CUDA | `cuda/ca_device.cuh:101-116, 149-205` | `e & 1` / `k & 1` branches, early exits |
| ecc2k130 | `ecc2k130/include/bigmod.h:71-83`, `include/ref.h:75-157, 211-260, 335-385` | bit-indexed loops; the Itoh–Tsujii chains (`ref.h:134-149`, `fieldpb.h:107`, `fieldbs.h:222`, `fpga/rtl/onb131_inv.v`) are the one data-independent piece |
| RNG | `src/ca_internal.h:27-75`, `src/util.c:45-63` | xoshiro256** seeded from `/dev/urandom` with a clock-XOR-stack-address fallback; fine for walks, not a CSPRNG for keys |

Planted logarithms are produced by `ca_group_random_power` (`src/group_common.c:50-59`) and printed by
the CLI (`tools/ca_cli.c:452-455`); the Python tests and the `ecc2k130` codegen plant seeded controls.
These are known-answer fixtures, not secrets.

## 3. Two things worth doing

1. **cuPQC demo is on by default.** `CMakeLists.txt:31-33` sets `CA_CUPQC` ON, which builds NVIDIA's
   ML-KEM-512 keygen/encaps/decaps sample, and `docs/CUPQC.md:52-56` notes it can print secret bytes on a
   mismatch. It is vendor code outside this repository's control, generates real (throwaway) keys, and is
   unrelated to the library's purpose. Suggest default OFF, or gate it behind an explicit opt-in.
2. **Bearer-token compare leaks length.** `orchestrator/internal/control/server.go:301-303` uses Go's
   `subtle.ConstantTimeCompare`, which returns early on a length mismatch. Compare a fixed-length hash of
   the token instead. The empty-token-means-unauthenticated path (`orchestrator/cmd/ca-control/main.go:
   113-141`) is already warned about at `:141`.

## 4. Tooling

CI runs ASan/UBSan/TSan, Valgrind memcheck, libFuzzer (`fuzz/fuzz_modarith.c`, correctness invariants
only) and CodeQL (`.github/workflows/ci.yml:79-151`, `fuzz.yml`, `codeql.yml`); `fpga.yml:90` notes there
is no timing analysis. No side-channel tooling exists, and none is needed for the current scope.

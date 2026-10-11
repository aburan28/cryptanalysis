# NVIDIA cuPQC integration

`CA_CUPQC=ON` adds the `ca_cupqc_mlkem` executable to the normal CMake
build. It compiles NVIDIA's ML-KEM example against a locally installed
cuPQC SDK, demonstrating batched key generation, encapsulation and
decapsulation. This is an optional example integration; it does not expose
a new C library API or change the discrete-logarithm solvers.

The option defaults to OFF, so CPU-only builds, macOS and CI need no SDK,
CUDA compiler or NVIDIA GPU. Pass `-DCA_CUPQC=ON` on the Linux CUDA host
with the SDK described below. `CA_CUPQC` is independent of `CA_CUDA`.
Existing CMake build directories retain their cached setting.

## Dependencies and build

Use a Linux CUDA host, NVIDIA nvcc, CMake 3.24 or later, a compatible
NVIDIA GPU, and the cuPQC SDK. Check the requirements shipped with the
SDK for supported CUDA versions, GPU architectures and host platforms.
Download and extract the SDK using the
[NVIDIA download page](https://developer.nvidia.com/cupqc-download/).
The SDK is separately licensed and is not downloaded or vendored by this
project.

The integration expects the documented CMake package `cupqc` and its
`cupqc-pk_static` target. Set the example path explicitly if it is absent
from the SDK. The public NVIDIA examples can be obtained at the revision
inspected for this integration:

```sh
git clone https://github.com/NVIDIA/cuPQC.git /tmp/nvidia-cupqc-examples
git -C /tmp/nvidia-cupqc-examples checkout f53b0a2173c3c5935ac0ca8579aa7573434193b2

cmake -S . -B build-cupqc \
  -DCA_CUPQC=ON \
  -DCA_CUPQC_ROOT=/opt/cupqc \
  -DCA_CUPQC_MLKEM_SOURCE=/tmp/nvidia-cupqc-examples/examples/public_key/example_ml_kem.cu \
  -DCA_CUPQC_ARCHITECTURES=80
cmake --build build-cupqc --target ca_cupqc_mlkem -j
./build-cupqc/ca_cupqc_mlkem
```

Replace `/opt/cupqc` and architecture `80` with your SDK installation and
supported GPU architecture. The target enables C++17 and CUDA device
link-time optimization. Architecture settings apply only to this target.
Use an example from the installed SDK if a newer SDK changes its API.

## Validation boundary

The referenced example runs ML-KEM-512 with a batch of ten and compares
encapsulated and decapsulated shared secrets. It is a demonstration, not
a production key-management API or an independent conformance test. It
is deliberately not registered with CTest: its CUDA error handling and
exit status must not be treated as a trustworthy CI correctness gate.
It can print secret bytes on a mismatch; use only its generated demo data.

A complete GPU acceptance run still needs a supported host, successful
compilation, successful CUDA operations and inspection of the example's
verification output. Local CPU configuration checks do not establish
GPU correctness, performance, FIPS validation or production readiness.

ML-KEM and ML-DSA implement post-quantum protocols. Their presence does
not accelerate this project's ECC group law or establish an ECDLP result.

References: [cuPQC getting started](https://docs.nvidia.com/cuda/cupqc/introduction/getting_started.html),
[NVIDIA examples](https://github.com/NVIDIA/cuPQC), and
[the article shown in the photo](https://developer.nvidia.com/blog/?p=92737).

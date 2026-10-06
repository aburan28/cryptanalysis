ECC2K-130 packed table walk at 20.08 B/s on one RTX PRO 6000 Blackwell.

Branch:   /tmp/crypto, branch ecc2k130-l1-geometry-and-tag-denominator
          (2 commits on top of aburan28/crypto c6d2a10); no GitHub
          credentials were available in this worker, so it is not pushed.
Patches:  patches/0001-*.patch, patches/0002-*.patch
          (cd <crypto checkout> && git am /root/ecc2k130-20b/patches/*.patch)
Build:    cd ecc2k130 && PATH=/opt/cuda133/cuda/bin:$PATH make gpu-rtx-pro6000-20b
          (CUDA 13.3.73 toolchain assembled from NVIDIA pip wheels in /opt/cuda133)
Bench:    ./ecc2k130 --curve 131 --packed --bench --steps 1024 --launches 64 --verify 0
Verify:   ./ecc2k130 --curve 131 --packed --dp-weight 46 --dp-cap 262144 --steps 96 \
              --launches 6 --verify 300 --run-id 4242
Note:     ONE-BLOCK-GEOMETRY.md (also in the branch)
Logs:     bench-logs/bench_final.log is the five-repetition paired measurement.
Micro:    clmad_bench*.cu are the CLMAD latency/throughput microbenchmarks.

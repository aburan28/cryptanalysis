# Patched Sage for local elliptic-curve experiments

The `cryptanalysis` CLI and Sage are separate builds. The CLI handles generic
BSGS, rho, and prime-field index calculus; its ECC2K-130 rho command uses the
curve-specific CUDA kernel packaged beside it. The Sage stack here supplies
the local binary-curve batch arithmetic, Frobenius, point addition, and
CPU/Metal point-map improvements used by Sage-based experiments. These stage
optimizations are not an end-to-end elliptic-curve index-calculus speedup claim.

`scripts/sage-release-manifest.json` pins Sage commit
`671dfa344f4cc4a6d54f343cbfd1272ee81698c9` (10.10.rc0), nine ordered
patches, their SHA-256 digests, and the exact resulting source digests. The
standalone native Frobenius patch is already included in the first batch patch;
held experimental patches are excluded.

## Local build and use

The default Sage checkout is `third_party/sage-binary`. Set `--sage PATH` for
another checkout. `apply` is safe to repeat when the final source hashes match;
it refuses a partially modified source tree.

```sh
python3 scripts/sage_release.py apply --sage third_party/sage-binary
python3 scripts/sage_release.py build --sage third_party/sage-binary --jobs 6
python3 scripts/sage_release.py smoke --sage third_party/sage-binary
python3 scripts/sage_release.py run --sage third_party/sage-binary -- -python my_experiment.py
```

The `build` action assumes Sage's normal source-build prerequisites and
configuration are already installed in that checkout. It runs `make`, then
checks that the installed Python modules exactly match the release source and
that native batch addition, Frobenius, scalar point operations, and the CPU
point-map path return correct points. `run` verifies the source digests before
starting the selected Sage interpreter and sets a writable Sage cache in the
repository build directory. Experiments should use this command (or the same
Sage interpreter) to load the installed optimized code.

## Release asset

The release workflow reconstructs the patch stack on a fresh pinned Sage
checkout and publishes `cryptanalysis-sage-VERSION-source.tar.gz` with the
manifest, patches, and the build/smoke script. This is a reproducible source
kit for a locally built Sage. It is **not** a relocatable Sage executable or a
precompiled Metal extension. Sage's compiled extensions have platform and
Python ABI dependencies; a distributable binary needs separate packaging and
testing on each target platform. The release job does not claim to build that
binary.

Extract the source kit in any directory, use its `scripts/sage_release.py`
to apply the patches to a Sage checkout at the pinned commit, configure that
checkout following Sage's installation guide, then run `build` and `smoke`.

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
python3 scripts/sage_release.py verify-installed --sage third_party/sage-binary
python3 scripts/sage_release.py smoke --sage third_party/sage-binary
python3 scripts/sage_release.py run --sage third_party/sage-binary -- -python my_experiment.py
```

The `build` action assumes Sage's normal source-build prerequisites and
configuration are already installed in that checkout. It runs `make`, then
checks that the installed Python modules exactly match the release source and
that native batch addition, Frobenius, scalar point operations, and the CPU
point-map path return correct points. `verify-installed` checks the installed
module hashes and presence of the native extensions without starting Sage.
`run` performs that check before starting the selected Sage interpreter and
also checks the paths Sage actually imports. It sets a writable Sage cache in
the repository build directory. It exits with an error if the installed
release modules differ from their hashes. Source edits that have not been
installed do not affect this check; `build`, `verify`, and `pack-binary` still
require the exact release source stack.

## Compiled macOS arm64 accelerator overlay

The seven patched runtime modules can be distributed as a small compiled
overlay for an **already built** Sage at the pinned commit. The archive does
not include Sage itself. It records the Sage source manifest digest, CPU and
operating system, Python version and extension suffix, and a SHA-256 for every
file. The installer refuses a mismatched checkout or Python ABI, verifies all
payload digests, and runs the same arithmetic smoke test after installation.
It restores the previous modules if the smoke test fails. Native extensions
also require their linked NTL library to be available on the target Mac.

```sh
python3 scripts/sage_release.py pack-binary --sage third_party/sage-binary \
  --version VERSION --out dist
python3 scripts/sage_release.py install-binary --sage /path/to/built/sage \
  --archive dist/cryptanalysis-sage-VERSION-macos-arm64-py314.tar.gz
python3 scripts/sage_release.py run --sage /path/to/built/sage -- -python my_experiment.py
```

When the shared Sage installation is being used for new source experiments,
run a local computation directly from the checked archive without replacing
its installed files:

```sh
python3 scripts/sage_release.py run-overlay --sage /path/to/built/sage \
  --archive dist/cryptanalysis-sage-VERSION-macos-arm64-py314.tar.gz \
  -- -python my_experiment.py
```

`run-overlay` checks the archive's source and ABI manifest, stages its modules
under `build/sage-overlays/`, verifies the six importable modules resolve to
that directory, runs the arithmetic smoke test once per archive and smoke
script version, and then starts the experiment. It leaves the shared Sage
source and installed package untouched. Both commands put setup and import
checks before the experiment process; an online target timer should start
after that setup.

The target checkout must first have the source patch stack applied and its
base Sage installation built. An overlay built against Python 3.14 cannot be
installed into Sage built with Python 3.13. The compiler output has an NTL
dynamic library dependency; the post-install smoke test catches a missing or
incompatible library before an experiment starts. The `run` command checks
the installed source modules on every invocation.

## Source release asset

The release workflow reconstructs the patch stack on a fresh pinned Sage
checkout and publishes `cryptanalysis-sage-VERSION-source.tar.gz` with the
manifest, patches, and the build/smoke script. A separate `macos-15` job builds
the pinned Sage source, verifies its installed modules, packages the compiled
overlay, installs that archive back through the ABI and smoke gates, and
publishes the archive and checksum with the release. The release waits for
both jobs. The source asset is a reproducible build kit; the compiled asset is
only an accelerator overlay for a separately built Sage with the matching
Python ABI. A full Sage tree is not a relocatable archive.

If a release needs a manually rebuilt Mac artifact, the operator can run
`bash scripts/publish_sage_binary.sh cryptanalysis-vVERSION /path/to/built/sage`
after the tagged release exists. It checks the installed stack, builds the
overlay archive and checksum, reinstalls it through the ABI gate and smoke
test, then attaches both files to the GitHub release.

Extract the source kit in any directory, use its `scripts/sage_release.py`
to apply the patches to a Sage checkout at the pinned commit, configure that
checkout following Sage's installation guide, then run `build` and `smoke`.

# Accepted Sage arithmetic follow-up

`selected.patch` is applied in order by `scripts/sage-release-manifest.json`.
Use `scripts/sage_release.py apply`, `build`, and `run` as documented in
[the source release guide](../../../docs/SAGE_RELEASE.md). The entire eleven-patch
stack reconstructs the accepted local source; this patch is not standalone
against unmodified upstream Sage.

[RESULT.md](RESULT.md) describes the arithmetic-component measurements and
limits. `measurement-evidence.tar.gz` retains the original intents, decision
records, raw trials, source snapshots, failed/held attempts and test logs.
`measurement-manifest.json` hashes each archived file and the archive itself.
Native binaries are recorded by their original hashes and omitted from the
package; build for the target machine instead of loading a Mac `.so`.

Verify the archive without Sage:

```sh
python3 experiments/sage-binary-hardware/verify_compatibility_archive.py
```

Run fresh correctness checks through a checked Sage launcher using
`experiments/sage-binary-hardware/validate_compatibility.py`. Historical timing
harnesses refer to their archived baseline and candidate binaries; rebuilding
those on another host requires a new receipt and does not reproduce a physical
Mac performance claim on that host.

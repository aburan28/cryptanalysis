"""Check every compressed explicit-base receipt against the frozen result hashes."""

import hashlib
import json
import lzma
import sys
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(directory):
    directory = Path(directory)
    results = json.loads((directory / "results.json").read_text())
    archives = json.loads((directory / "archives.json").read_text())
    if digest((directory / "manifest.json").read_bytes()) != results["manifest_sha256"]:
        raise ValueError("manifest differs from frozen result")
    expected = {f"n{r['n']}-l{r['l']}.jsonl.xz" for r in results["results"]}
    actual = {p.name for p in directory.glob("*.jsonl.xz")}
    if expected != actual or expected != set(archives):
        raise ValueError("missing or extra archived case")
    for result in results["results"]:
        name = f"n{result['n']}-l{result['l']}.jsonl.xz"
        compressed = (directory / name).read_bytes()
        if len(compressed) != archives[name]["bytes"] or digest(compressed) != archives[name]["sha256"]:
            raise ValueError(f"{name}: compressed archive mismatch")
        raw = lzma.decompress(compressed)
        if len(raw) != result["raw_bytes"] or digest(raw) != result["raw_sha256"]:
            raise ValueError(f"{name}: raw receipt mismatch")
        rows = raw.splitlines()
        if not rows or json.loads(rows[-1]).get("summary") is not True:
            raise ValueError(f"{name}: missing final enumerator summary")
    return len(expected)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        print(f"{path}: {verify(path)} archives verified")

#!/usr/bin/env python3
"""Restore the pinned crypto sources this experiment builds and checks, and verify them.

Three things come from one crypto clone (`--crypto-repo`, any clone that has
the three commits; `git clone --filter=blob:none --no-checkout` is enough):

* `snapshots/v3/` from crypto 995ea207, the IC programme's baseline v3 (the
  commit and code rule v3 measured): `Cargo.toml` and `src/`. The crate
  `crates/v3` builds its `ic` binary from it.
* `snapshots/r770/` from crypto 770f6a69 (rT770's revision): `Cargo.toml`,
  `src/`, A's tuned worker `examples/n83_rho_optimization_eval.rs` (the parent
  of `rho/s23_strong_rho_eval.rs`, checked by digest only) and A's
  `selected_config.json`. The derived worker is copied into
  `snapshots/r770/examples/`, so its relative `include_bytes!` paths resolve.
* The harness checkout: the crypto clone's own working tree is sparse-checked
  out at the harness commit (crypto 96911f55, rule v3's results commit; its
  claim checker passes section 23's claim rows, which main's stricter
  checker no longer does) with
  ledger section 23's claim assembler, its parameter files and identity
  sources, the tournament's identity adapter and oracle, and the autolab claim
  checker. `claims.py` runs from there, because it reads the identity sources
  with `git show` and so needs a repository. Two textual edits, each asserted to
  match exactly once, let it label this experiment's isolation and CPU instead
  of section 23's (`CLAIMS_EDITS`); nothing else in it changes.

Every file is then checked against `protocol.json`. `--print-digests` prints
the digests of a fresh restore (used once, to freeze the protocol).
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOTS = HERE / "snapshots"
PROTOCOL = HERE / "protocol.json"

V3_COMMIT = "995ea2071cc7453877a503d30eb561ae82cddab9"
R770_COMMIT = "770f6a6925a0d29b768bd79074f54a173e967fe7"
HARNESS_COMMIT = "96911f5550bd70c5a9765fdc10e94fdeaa528047"

PARENT_WORKER = "examples/n83_rho_optimization_eval.rs"
TUNED_CONFIG = "research/n83_evaluation_20261012/optimization/selected_config.json"
WORKER = "rho/s23_strong_rho_eval.rs"
S23 = "research/ic_single_target_20260930"
SIZES = [(1, 47), (0, 57), (0, 41), (0, 53), (1, 59), (0, 61)]  # section 23's order of r
TARGETS = 64

# Files outside src/ that each library snapshot's include_str!/include_bytes!
# name (found by scanning the snapshot; test-only ones included, all small).
TG = "research/ic_candidate_tournament_20260915/goal_20260924/"
SAT = TG + "prepared-report-contract-v1/sat-source-check/"
COMMON_INCLUDES = [
    "docs/curves/registry.json", "docs/ecbench/schema.sql", "docs/ic/boundary_targets.json",
    "docs/ic/calibration.json", "research/f4_linear_algebra_20260914/contract.json",
    TG + "prepared-ic-state-v1/sat-preparation.json",
    SAT + "instance.anf", SAT + "instance.xor.cnf", SAT + "manifest.json", SAT + "result.json",
]
V3_INCLUDES = COMMON_INCLUDES + [
    TG + "prepared-f5-runtime-v1/mathematics.json",
    TG + "prepared-f5-v3-control-v1/controls/pipeline.stdout",
    TG + "prepared-ic-state-v1/f5-preparation.json",
]
R770_INCLUDES = COMMON_INCLUDES + [
    "docs/curves/traits.json", "docs/identity-certificates/schoenhage-10mult.json",
    "research/ecbench_n41_n53_shared_rank_20261005/sessions/mac-l0/records.jsonl",
    "tests/fixtures/ecbench_manifest_small.json",
]

HARNESS_FILES = [
    S23 + "/claims.py",
    S23 + "/make_params.py",
    S23 + "/curve_ids.json",
    "research/ic_exponent_20260926/make_params.py",
    "research/ic_candidate_tournament_20260915/identity.py",
    "research/ic_candidate_tournament_20260915/oracle.py",
    "research/sat_factor_base_review_20260908/autolab/boundary_autolab.py",
    "research/sat_factor_base_review_20260908/autolab/protocol.json",
    "tools/curve_identity.py",
    "docs/ic/boundary_targets.json",
]
PARAM_FILES = [f"{S23}/runs/k{a}n{n}/T{i:02d}.params.json" for a, n in SIZES for i in range(1, TARGETS + 1)]

# The claim assembler's two hard-coded labels of section 23's host; the run
# sets both variables (run_schedule.py and the workflow), and the defaults are
# section 23's own text, so with neither set the file behaves as before.
CLAIMS_EDITS = [
    ('"isolation": "tools/isolated_bench.py run --wait --cpus 2, uncontended",',
     '"isolation": os.environ.get("S23_ISOLATION_LABEL", "tools/isolated_bench.py run --wait --cpus 2, uncontended"),'),
    ('"resource_caps": {"rayon_threads": 1, "cpus": "2", "contended": iso["contended"]},',
     '"resource_caps": {"rayon_threads": 1, "cpus": os.environ.get("S23_CPUS", "2"), "contended": iso["contended"]},'),
]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def tree_digest(root):
    state = hashlib.sha256()
    for path in sorted(p for p in Path(root).rglob("*") if p.is_file()):
        state.update(str(path.relative_to(root)).encode())
        state.update(b"\0")
        state.update(bytes.fromhex(sha256(path)))
    return state.hexdigest()


def git(repo, *args, capture=True):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=capture).stdout


def archive(repo, commit, paths, dest):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        tar = Path(tmp) / "a.tar"
        with tar.open("wb") as out:
            subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", commit, "--", *paths],
                           check=True, stdout=out)
        with tarfile.open(tar) as t:
            t.extractall(dest, filter="data")


def restore(repo):
    for commit in (V3_COMMIT, R770_COMMIT, HARNESS_COMMIT):
        git(repo, "cat-file", "-e", commit + "^{commit}")
    archive(repo, V3_COMMIT, ["Cargo.toml", "src"] + V3_INCLUDES, SNAPSHOTS / "v3")
    archive(repo, R770_COMMIT, ["Cargo.toml", "src", PARENT_WORKER, TUNED_CONFIG] + R770_INCLUDES,
            SNAPSHOTS / "r770")
    shutil.copyfile(HERE / WORKER, SNAPSHOTS / "r770" / "examples" / Path(WORKER).name)
    # The harness checkout, in the clone's own working tree.
    git(repo, "sparse-checkout", "init", "--no-cone")
    git(repo, "sparse-checkout", "set", "--no-cone",
        *["/" + p for p in HARNESS_FILES], "/" + S23 + "/runs/k*/T*.params.json")
    git(repo, "checkout", "--quiet", "--force", "--detach", HARNESS_COMMIT)
    claims = Path(repo) / S23 / "claims.py"
    text = claims.read_text()
    for old, new in CLAIMS_EDITS:
        if text.count(old) != 1:
            raise SystemExit("claims.py edit does not match exactly once: " + old)
        text = text.replace(old, new)
    claims.write_text(text)


def digests(repo):
    repo = Path(repo)
    out = {
        "v3_src_tree": tree_digest(SNAPSHOTS / "v3" / "src"),
        "v3_manifest": sha256(SNAPSHOTS / "v3" / "Cargo.toml"),
        "v3_includes": hashlib.sha256(b"".join(bytes.fromhex(sha256(SNAPSHOTS / "v3" / p)) for p in V3_INCLUDES)).hexdigest(),
        "r770_includes": hashlib.sha256(b"".join(bytes.fromhex(sha256(SNAPSHOTS / "r770" / p)) for p in R770_INCLUDES)).hexdigest(),
        "r770_src_tree": tree_digest(SNAPSHOTS / "r770" / "src"),
        "r770_manifest": sha256(SNAPSHOTS / "r770" / "Cargo.toml"),
        "parent_worker": sha256(SNAPSHOTS / "r770" / PARENT_WORKER),
        "derived_worker": sha256(HERE / WORKER),
        "tuned_config": sha256(SNAPSHOTS / "r770" / TUNED_CONFIG),
        "default_config": sha256(HERE / "configs" / "default_strong.json"),
        "default_wide_config": sha256(HERE / "configs" / "default_strong_wide.json"),
        "targets": sha256(HERE / "inputs" / "targets.json"),
        "crate_v3_lock": sha256(HERE / "crates" / "v3" / "Cargo.lock"),
        "crate_r770_lock": sha256(HERE / "crates" / "r770" / "Cargo.lock"),
        "claims_py_at_harness_commit": sha256_bytes(git(repo, "show", HARNESS_COMMIT + ":" + S23 + "/claims.py")),
        "claims_py_edited": sha256(repo / S23 / "claims.py"),
    }
    for path in HARNESS_FILES:
        if path.endswith("claims.py"):
            continue
        out["harness:" + path] = sha256(repo / path)
    state = hashlib.sha256()
    for path in PARAM_FILES:
        state.update(path.encode() + b"\0" + bytes.fromhex(sha256(repo / path)))
    out["section23_params_384"] = state.hexdigest()
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--crypto-repo", required=True, type=Path)
    parser.add_argument("--print-digests", action="store_true")
    args = parser.parse_args()
    restore(args.crypto_repo)
    found = digests(args.crypto_repo)
    if args.print_digests:
        print(json.dumps(found, indent=2, sort_keys=True))
        return
    frozen = json.loads(PROTOCOL.read_text())["sources"]["digests"]
    bad = sorted(k for k in set(frozen) | set(found) if frozen.get(k) != found.get(k))
    if bad:
        raise SystemExit("digest mismatch: " + ", ".join(bad))
    print(json.dumps({"restored": True, "checked": len(found)}))


if __name__ == "__main__":
    main()

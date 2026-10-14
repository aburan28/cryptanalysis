#!/usr/bin/env python3
"""Restore the pinned crypto source, generate the two BL arms from it, and check everything.

`git archive` extracts from crypto 770f6a69 (the revision of the Tier 1 experiment
`experiments/koblitz-single-target-n83-tier1-20261014/`, "B") only the paths this
experiment builds or reads: the library, B's IC online producer, the three rho
step implementations the reconciliation (`claude/n83-reconcile`) compares, the
tuned worker's config, the frozen inputs and the pinned pure-Python harness. B's
`ic_log_cache.patch` is applied from B's directory, digest-checked against B's
frozen protocol, exactly as B did.

Then two Bernstein–Lange (BL) sources are generated into `snapshot/bl_generated/`
by asserted, exactly-once textual edits of the pinned files (never a fuzzy patch):

* `sg_bl_module.rs`: the library walk `src/cryptanalysis/koblitz_strong_rho.rs`
  (tests cut, `crate::` made `crypto_lib::`) with `bl_src/sg_bl_impl.rs`
  appended; `solve_with_table` inside it is the library's `solve` with the
  four substitutions in `SG_SOLVE_SUBS`. `bl_sg.rs` is `bl_src/bl_sg.rs`.
* `bl_rung3.rs`: B's rho example (`koblitz_rho_batch_ks_strong_online.rs`) with
  `bl_src/rung3_bl_impl.rs` inserted into its `mod wide` and the edits in
  `R3_SUBS` (jump-seed override, table preload, hit kind, one extra JSON line,
  a `main` hook for KIC_BL_MODE).

Every restored and generated file is checked against `protocol.json`
(`sources.sha256`); the files shared with B are also checked against B's frozen
`tier1_protocol.json`. `--print-digests` prints the digests of a fresh
extraction (used once, to freeze the protocol) without checking them.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshot"
PROTOCOL = HERE / "protocol.json"
B_DIR = HERE.parent / "koblitz-single-target-n83-tier1-20261014"
B_PROTOCOL = B_DIR / "tier1_protocol.json"
B_PATCH = B_DIR / "ic_log_cache.patch"

COMMIT = "770f6a6925a0d29b768bd79074f54a173e967fe7"
IC_ONLINE = "examples/koblitz_orbit_dlp_fast_online.rs"
IC_ONLINE_PATCHED = "examples/koblitz_orbit_dlp_fast_online_logcache.rs"
RHO_RUNG3 = "examples/koblitz_rho_batch_ks_strong_online.rs"
RHO_ADAPTER = "examples/n83_strong_point_eval.rs"
RHO_TUNED = "examples/n83_rho_optimization_eval.rs"
SG_LIBRARY = "src/cryptanalysis/koblitz_strong_rho.rs"
TUNED_CONFIG = "research/n83_evaluation_20261012/optimization/selected_config.json"
INPUT_DIR = "experiments/koblitz-single-target-n83-20261006"
BASE = INPUT_DIR + "/base_n83_K600.jsonl"
Q0_FILE = INPUT_DIR + "/frozen/target_points.jsonl"
FIXTURE = INPUT_DIR + "/frozen/fixture.json"
AUTOLAB = "research/sat_factor_base_review_20260908/autolab"
HARNESS = [
    AUTOLAB + "/boundary_autolab.py",
    AUTOLAB + "/single_target_panel.py",
    AUTOLAB + "/op_accounting.py",
    AUTOLAB + "/protocol.json",
    "research/ic_candidate_tournament_20260915/identity.py",
    "research/ic_candidate_tournament_20260915/oracle.py",
    "tools/curve_identity.py",
    "research/ic_single_target_20260930/curve_ids.json",
    "docs/ic/boundary_targets.json",
]
ARCHIVE = ["Cargo.toml", "Cargo.lock", "src", IC_ONLINE, RHO_RUNG3, RHO_ADAPTER, RHO_TUNED,
           TUNED_CONFIG, BASE, Q0_FILE, FIXTURE] + HARNESS

GEN = "bl_generated"
GEN_SG_MODULE = GEN + "/sg_bl_module.rs"
GEN_SG_MAIN = GEN + "/bl_sg.rs"
GEN_RUNG3 = GEN + "/bl_rung3.rs"
GEN_TABLE_IO = GEN + "/bl_table_io.rs"
BL_SOURCES = {
    "bl_src:sg_bl_impl.rs": "bl_src/sg_bl_impl.rs",
    "bl_src:bl_sg.rs": "bl_src/bl_sg.rs",
    "bl_src:rung3_bl_impl.rs": "bl_src/rung3_bl_impl.rs",
    "bl_src:bl_table_io.rs": "bl_src/bl_table_io.rs",
}

FILE_KEYS = {
    "crypto_manifest": "Cargo.toml", "crypto_lock": "Cargo.lock",
    "ic_online_upstream": IC_ONLINE, "ic_online_patched": IC_ONLINE_PATCHED,
    "rho_rung3": RHO_RUNG3, "rho_adapter": RHO_ADAPTER, "rho_tuned": RHO_TUNED,
    "sg_library": SG_LIBRARY, "tuned_config": TUNED_CONFIG,
    "base_n83_K600": BASE, "target_points": Q0_FILE, "validation_fixture": FIXTURE,
    "generated:sg_bl_module": GEN_SG_MODULE, "generated:bl_sg": GEN_SG_MAIN,
    "generated:bl_rung3": GEN_RUNG3, "generated:bl_table_io": GEN_TABLE_IO,
    **{"harness:" + path: path for path in HARNESS},
}
# Keys B froze under the same or another name (tier1_protocol.json).
SHARED_WITH_B = {
    "crypto_manifest": "crypto_manifest", "crypto_lock": "crypto_lock",
    "ic_online_upstream": "ic_online_upstream", "ic_online_patched": "ic_online_patched",
    "rho_rung3": "rho_strong_online", "base_n83_K600": "base_n83_K600",
    "target_points": "target_points", "validation_fixture": "validation_fixture",
    "crypto_rust_source_tree": "crypto_rust_source_tree",
    **{"harness:" + path: "harness:" + path for path in HARNESS},
}

# solve -> solve_with_table: (old, new), each must occur exactly once in solve.
SG_SOLVE_SUBS = [
    ("    pub fn solve(\n", "    pub fn solve_with_table(\n"),
    ("        mut charges: StrongRhoCharges,\n    ) -> Option<StrongRhoOutcomeG<S>> {\n",
     "        mut charges: StrongRhoCharges,\n"
     "        table: &mut HashMap<(u8, F::E, F::E), (S, S)>,\n"
     "        precomputed_hit: &mut bool,\n"
     "    ) -> Option<StrongRhoOutcomeG<S>> {\n"),
    ("        let mut table: HashMap<(u8, F::E, F::E), (S, S)> = HashMap::new();\n", ""),
    ("                if self.scalar_mul(self.generator, candidate) == q {\n",
     "                if self.scalar_mul(self.generator, candidate) == q {\n"
     "                    *precomputed_hit = hit_b == S::zero();\n"),
]
SOLVE_START = "    pub fn solve(\n"
SOLVE_END = "\n        None\n    }\n"
TESTS_CUT = "\n#[cfg(test)]\nmod tests {"

R3_WIDE_START = "\nmod wide {\n"
R3_INSERT_BEFORE = "    /// Parse the wide configuration from `args`/environment (the `u64`\n"
# (old, new, scope): scope "wide" edits only the text of `mod wide`, "main" only main().
R3_SUBS = [
    ('            blake3::hash(format!("KIC-KS-BATCH-JUMPS-v1|{n}|{a}|{}", cfg.batch_seed).as_bytes());\n',
     '            blake3::hash(format!("KIC-KS-BATCH-JUMPS-v1|{n}|{a}|{}", bl_jump_batch_seed(cfg.batch_seed)).as_bytes());\n',
     "wide"),
    ("        let mut table: HashMap<(u8, u128, u128), Trail> = HashMap::new();\n",
     "        let mut table: HashMap<(u8, u128, u128), Trail> = HashMap::new();\n"
     "        let (bl_table_load_ms, bl_table_entries) = bl_preload(&mut table, cfg.fixtures);\n",
     "wide"),
    ("        let candidate = if hit.target == index {\n",
     "        BL_HIT_B.with(|cell| cell.set(hit.b));\n"
     "        let candidate = if hit.target == index {\n",
     "wide"),
    ("            let q_key = raw_key(q);\n            emit(json!({\n                \"kind\":\"rho_ks_batch_fixture\",\n",
     "            let q_key = raw_key(q);\n"
     "            emit(json!({\"kind\":\"bl_online_fixture\",\"table_entries_loaded\":bl_table_entries,"
     "\"table_load_ms\":bl_table_load_ms,\"jump_batch_seed\":bl_jump_batch_seed(cfg.batch_seed),"
     "\"solved_by\":if bl_table_entries > 0 && BL_HIT_B.with(|cell| cell.get()) == 0 "
     "{ \"precomputed_table\" } else { \"online_self_collision\" },"
     "\"walk_steps\":steps,\"online_ms\":online_ms,\"peak_rss_bytes\":bl_peak_rss_bytes()}));\n"
     "            emit(json!({\n                \"kind\":\"rho_ks_batch_fixture\",\n",
     "wide"),
    ("    if (64..=127).contains(&n) {\n        let cfg = wide::main_config(&args);\n",
     "    if (64..=127).contains(&n) && std::env::var(\"KIC_BL_MODE\").is_ok() {\n"
     "        wide::bl_main(&args);\n        return;\n    }\n"
     "    if (64..=127).contains(&n) {\n        let cfg = wide::main_config(&args);\n",
     "main"),
]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_digest(root, paths):
    state = hashlib.sha256()
    for path in sorted(paths):
        state.update(str(path.relative_to(root)).encode())
        state.update(b"\0")
        state.update(bytes.fromhex(sha256(path)))
    return state.hexdigest()


def digests(root):
    result = {key: sha256(root / rel) for key, rel in FILE_KEYS.items()}
    result["crypto_rust_source_tree"] = tree_digest(root, (root / "src").rglob("*.rs"))
    result["snapshot_tree"] = tree_digest(root, (p for p in root.rglob("*") if p.is_file() and
                                                 "__pycache__" not in p.parts))
    result["ic_log_cache_patch"] = sha256(B_PATCH)
    result.update({key: sha256(HERE / rel) for key, rel in BL_SOURCES.items()})
    return result


def unpack(archive, destination):
    seen = set()
    with tarfile.open(archive, "r:") as stream:
        for member in stream:
            relative = PurePosixPath(member.name)
            if (relative.is_absolute() or not relative.parts or
                    any(part in ("", ".", "..") for part in relative.parts)):
                raise ValueError("unsafe crypto archive path")
            if member.isdir() or member.name == "pax_global_header":
                continue
            if not member.isfile() or member.name in seen:
                raise ValueError("unexpected crypto archive member " + member.name)
            seen.add(member.name)
            path = destination.joinpath(*relative.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, path.open("wb") as output:
                shutil.copyfileobj(source, output, 1 << 20)


INCLUDE = re.compile(r'include_(?:str|bytes)!\(\s*"([^"]+)"\s*\)')


def included_files(root):
    """Files outside src/ that the library compiles in with include_str!/include_bytes!."""
    found = set()
    for source in (root / "src").rglob("*.rs"):
        for literal in INCLUDE.findall(source.read_text(errors="replace")):
            target = Path(os.path.normpath(source.parent / literal))
            relative = target.relative_to(root)
            if relative.parts[0] != "src":
                found.add(relative.as_posix())
    return sorted(found)


def git_archive(repo, paths, destination):
    with tempfile.TemporaryDirectory(prefix="n83-bl-archive-") as folder:
        archive = Path(folder) / "source.tar"
        subprocess.run(["git", "-C", str(repo), "archive", "--format=tar",
                        "--output=" + str(archive), COMMIT] + paths, check=True)
        unpack(archive, destination)


def replace_once(text, old, new, what):
    count = text.count(old)
    if count != 1:
        raise ValueError("%s: expected exactly one match, found %d: %r" % (what, count, old[:80]))
    return text.replace(old, new)


def generate_sg(root):
    library = (root / SG_LIBRARY).read_text()
    head, cut, _ = library.partition(TESTS_CUT)
    if not cut:
        raise ValueError("library test module not found")
    if head.count("use crate::") != 4:
        raise ValueError("unexpected crate imports in the library walk")
    head = head.replace("use crate::", "use crypto_lib::")
    start = head.index(SOLVE_START)
    end = head.index(SOLVE_END, start) + len(SOLVE_END)
    solve = head[start:end]
    for old, new in SG_SOLVE_SUBS:
        solve = replace_once(solve, old, new, "solve_with_table")
    impl = (HERE / BL_SOURCES["bl_src:sg_bl_impl.rs"]).read_text()
    impl = replace_once(impl, "    // @@SOLVE_WITH_TABLE@@\n", solve, "sg_bl_impl")
    banner = ("// GENERATED by experiments/koblitz-n83-bl-arm-20261014/restore_sources.py from\n"
              "// crypto %s:%s (tests cut, crate:: -> crypto_lib::) + bl_src/sg_bl_impl.rs.\n" % (COMMIT, SG_LIBRARY))
    (root / GEN).mkdir(exist_ok=True)
    (root / GEN_SG_MODULE).write_text(banner + head.rstrip("\n") + "\n\n" + impl)
    shutil.copyfile(HERE / BL_SOURCES["bl_src:bl_sg.rs"], root / GEN_SG_MAIN)


def generate_rung3(root):
    text = (root / RHO_RUNG3).read_text()
    wide_start = text.index(R3_WIDE_START)
    main_start = text.index("\nfn main() {\n")
    if not wide_start < main_start:
        raise ValueError("unexpected layout of the rung-3 example")
    before, wide, rest = text[:wide_start], text[wide_start:main_start], text[main_start:]
    for old, new, scope in R3_SUBS:
        if scope == "wide":
            # The u64 module's copies of these lines lie outside `wide` and stay untouched.
            wide = replace_once(wide, old, new, "rung3 wide")
        else:
            main_end = rest.index("\n#[cfg(test)]\n")
            rest = replace_once(rest[:main_end], old, new, "rung3 main") + rest[main_end:]
    impl = (HERE / BL_SOURCES["bl_src:rung3_bl_impl.rs"]).read_text()
    wide = replace_once(wide, R3_INSERT_BEFORE, impl + R3_INSERT_BEFORE, "rung3 insert")
    banner = ("// GENERATED by experiments/koblitz-n83-bl-arm-20261014/restore_sources.py from\n"
              "// crypto %s:%s + bl_src/rung3_bl_impl.rs (R3_SUBS).\n" % (COMMIT, RHO_RUNG3))
    # The example's inner attributes must stay first: put the banner after them.
    lines = before.split("\n")
    first_code = next(i for i, line in enumerate(lines) if not line.startswith("#!["))
    before = "\n".join(lines[:first_code] + [banner.rstrip("\n")] + lines[first_code:])
    (root / GEN).mkdir(exist_ok=True)
    (root / GEN_RUNG3).write_text(before + wide + rest)
    shutil.copyfile(HERE / BL_SOURCES["bl_src:bl_table_io.rs"], root / GEN_TABLE_IO)


def extract(repo, destination):
    git_archive(repo, ARCHIVE, destination)
    extra = [path for path in included_files(destination) if not (destination / path).exists()]
    if extra:
        git_archive(repo, extra, destination)
    if sha256(B_PATCH) != json.loads(B_PROTOCOL.read_text())["crypto_source"]["sha256"]["ic_log_cache_patch"]:
        raise ValueError("B's ic_log_cache.patch differs from B's frozen digest")
    shutil.copyfile(destination / IC_ONLINE, destination / IC_ONLINE_PATCHED)
    subprocess.run(["patch", "--no-backup-if-mismatch", "--forward", "-s", "-p1",
                    "-d", str(destination), "-i", str(B_PATCH)], check=True)
    generate_sg(destination)
    generate_rung3(destination)


def check(root, expected):
    actual = digests(root)
    wrong = sorted(key for key, value in expected.items() if actual.get(key) != value)
    if wrong:
        raise ValueError("snapshot differs from the frozen protocol: " + ", ".join(wrong))
    frozen_b = json.loads(B_PROTOCOL.read_text())["crypto_source"]["sha256"]
    wrong = sorted(key for key, b_key in SHARED_WITH_B.items() if actual[key] != frozen_b[b_key])
    if wrong:
        raise ValueError("files differ from B's frozen digests: " + ", ".join(wrong))
    return actual


def ensure(crypto_repo=None):
    protocol = json.loads(PROTOCOL.read_text())
    pinned = protocol["sources"]
    if pinned["commit"] != COMMIT:
        raise ValueError("protocol commit differs from the restore script")
    if SNAPSHOT.is_symlink():
        raise ValueError("snapshot must be a local directory")
    if SNAPSHOT.exists():
        check(SNAPSHOT, pinned["sha256"])
        return SNAPSHOT
    if crypto_repo is None or not (Path(crypto_repo) / ".git").exists():
        raise FileNotFoundError("pass --crypto-repo, a clone of https://github.com/aburan28/crypto")
    with tempfile.TemporaryDirectory(prefix="n83-bl-restore-", dir=HERE) as folder:
        staged = Path(folder) / "snapshot"
        staged.mkdir()
        extract(crypto_repo, staged)
        check(staged, pinned["sha256"])
        staged.rename(SNAPSHOT)
    return SNAPSHOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crypto-repo", type=Path)
    parser.add_argument("--print-digests", action="store_true")
    parser.add_argument("--regenerate", action="store_true",
                        help="development only: rebuild snapshot/bl_generated from bl_src without checking")
    parser.add_argument("--unchecked", action="store_true",
                        help="development only: extract into snapshot/ without the digest check")
    args = parser.parse_args()
    if args.print_digests:
        with tempfile.TemporaryDirectory(prefix="n83-bl-digests-") as folder:
            staged = Path(folder)
            extract(args.crypto_repo, staged)
            print(json.dumps(digests(staged), indent=2, sort_keys=True))
        return
    if args.unchecked:
        SNAPSHOT.mkdir()
        extract(args.crypto_repo, SNAPSHOT)
        print("unchecked_snapshot=" + str(SNAPSHOT))
        return
    if args.regenerate:
        generate_sg(SNAPSHOT)
        generate_rung3(SNAPSHOT)
        print("regenerated=" + str(SNAPSHOT / GEN))
        return
    print("verified_snapshot=" + str(ensure(args.crypto_repo)))


if __name__ == "__main__":
    main()

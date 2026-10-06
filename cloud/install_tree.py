#!/usr/bin/env python3
"""Make CHECKOUT hold exactly TREE's files, rewriting only what differs.

    python3 install_tree.py TREE CHECKOUT [--keep PATH]...

A file that is new or whose content differs is written afresh and so is as
old as this run; a file whose content is the same keeps its age; anything
TREE lacks is removed, except under the --keep paths (default suite/target,
the build tree).  A build in CHECKOUT therefore sees exactly what changed
since it last ran, whichever checkout each tree came from.  Copying trees with
their own ages instead could hand cargo an edited file older than its last
build, or a fresh directory a build script watches.
"""
import argparse
import filecmp
import os
import shutil
import sys
from pathlib import Path

KEEP = ("suite/target",)


def install(tree, checkout, keep=KEEP):
    """Returns (written, removed) counts."""
    tree, checkout = Path(tree), Path(checkout)
    keep = [Path(k) for k in keep]

    def kept(rel):
        return any(rel == k or k in rel.parents for k in keep)

    wanted, written, removed = set(), 0, 0
    for top, dirs, files in os.walk(tree):
        links = [d for d in dirs if os.path.islink(os.path.join(top, d))]
        for name in files + links:
            src = Path(top, name)
            rel = src.relative_to(tree)
            wanted.add(rel)
            dest = checkout / rel
            if same(src, dest):
                if not src.is_symlink() and dest.stat().st_mode != src.stat().st_mode:
                    os.chmod(dest, src.stat().st_mode)
                continue
            for parent in reversed(rel.parents[:-1]):
                if (checkout / parent).is_file() or (checkout / parent).is_symlink():
                    (checkout / parent).unlink()
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_dir() and not dest.is_symlink():
                shutil.rmtree(dest)
            part = dest.with_name(dest.name + ".install-part")
            if os.path.lexists(part):
                os.unlink(part)
            if src.is_symlink():
                os.symlink(os.readlink(src), part)
            else:
                shutil.copyfile(src, part)
                os.chmod(part, src.stat().st_mode)
            os.replace(part, dest)
            written += 1
    needed = {p for rel in wanted for p in rel.parents} | {p for k in keep for p in k.parents}
    for top, dirs, files in os.walk(checkout, topdown=False):
        for name in files + dirs:
            path = Path(top, name)
            rel = path.relative_to(checkout)
            if kept(rel) or rel in wanted:
                continue
            if path.is_symlink() or path.is_file():
                path.unlink()
                removed += 1
            elif rel not in needed and not any(path.iterdir()):
                path.rmdir()
    return written, removed


def same(src, dest):
    if src.is_symlink() or dest.is_symlink():
        return (src.is_symlink() and dest.is_symlink()
                and os.readlink(src) == os.readlink(dest))
    return dest.is_file() and filecmp.cmp(src, dest, shallow=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tree")
    ap.add_argument("checkout")
    ap.add_argument("--keep", action="append", metavar="PATH",
                    help=f"a path in CHECKOUT to leave alone (default {', '.join(KEEP)})")
    args = ap.parse_args(argv)
    written, removed = install(args.tree, args.checkout, args.keep or KEEP)
    print(f"install_tree: {written} written, {removed} removed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

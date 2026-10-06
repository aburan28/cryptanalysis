#!/usr/bin/env python3
"""Read-only regeneration of the old-data sparse hot-pair design."""

from make_tau3_sparse import ROOT, build_candidate, render_header, render_report


def main():
    records, arrays, prior_hash, native_hash = build_candidate()
    source = (ROOT / "make_tau3_sparse.py").read_bytes()
    header = render_header(records, arrays)
    report = render_report(records, prior_hash, native_hash, header, source)
    assert (ROOT.parents[1] / "src/generated/tau3_sparse.h").read_text() == header
    assert (ROOT / "tau3-sparse-screen.json").read_text() == report
    assert [r["point_entries"] for r in records] == [396, 756]
    assert [r["predicted_sparse_adds"] for r in records] == [53425, 120896]
    print("tau3 sparse design audit: PASS (frozen hot maps, exact 32,768 old action streams)")


if __name__ == "__main__":
    main()

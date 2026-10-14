#!/usr/bin/env python3
"""Emit a finite Lean certificate for the canonical six-unit seed table."""

from hashlib import sha256
from pathlib import Path
import sys


P = 3301
MAX_SEED = 1064
UNITS = (1, 3300, 1726, 1575, 1574, 1727)
CHUNK = 50
OUT = Path(__file__).with_name("SplitPrimeCanonicalCover.lean")


def centered(value: int) -> int:
    residue = value % P
    return min(residue, P - residue)


def source() -> str:
    seeds = [m for m in range(1, MAX_SEED + 1)
             if m == min(centered(m), centered(1726 * m),
                         centered(1574 * m))]
    assert len(seeds) == 550 and seeds[-1] == MAX_SEED
    lookup = {0: 0}
    for seed in seeds:
        for unit in UNITS:
            residue = unit * seed % P
            assert residue not in lookup
            lookup[residue] = seed
    assert len(lookup) == P

    lines = [
        "import SplitPrimeCanonicalSeeds",
        "set_option maxHeartbeats 0",
        "namespace SplitPrimeCanonicalCover",
        "open SplitPrimeCanonicalSeeds",
        "",
        "-- Each witness is checked against the canonical minimum-orbit predicate.",
        "def covered (r : Nat) : Prop :=",
        "  ∃ m : Nat, m ≤ 1064 ∧ (m = 0 ∨ isCanonical m = true) ∧ (",
        "    r = m ∨ r = (3300*m)%3301 ∨ r = (1726*m)%3301 ∨",
        "    r = (1575*m)%3301 ∨ r = (1574*m)%3301 ∨ r = (1727*m)%3301)",
        "",
    ]
    chunks = [(first, min(first + CHUNK - 1, P - 1))
              for first in range(0, P, CHUNK)]
    for index, (first, last) in enumerate(chunks):
        residues = range(first, last + 1)
        lines.append(
            f"theorem slice_{index} (r : Nat) (lo : {first} ≤ r) "
            f"(hi : r ≤ {last}) : covered r := by")
        lines.append("  have h : " + " ∨ ".join(
            f"r = {residue}" for residue in residues) + " := by omega")
        lines.append("  rcases h with " + " | ".join("h" for _ in residues))
        for residue in residues:
            lines.append(
                f"  · subst r; exact ⟨{lookup[residue]}, by decide, "
                "by decide, by decide⟩")
        lines.append("")
    lines += [
        "theorem all_residues_covered (r : Nat) (hr : r < 3301) : covered r := by",
    ]
    for index, (_, last) in enumerate(chunks[:-1]):
        lines += [
            f"  by_cases h{index} : r ≤ {last}",
            f"  · exact slice_{index} r (by omega) h{index}",
        ]
    lines += [
        f"  exact slice_{len(chunks)-1} r (by omega) (by omega)",
        "",
        "theorem canonical_mem (m : Nat) (hm : m ≤ 1064)",
        "    (hc : isCanonical m = true) : m ∈ seeds := by",
        "  simp only [seeds, List.mem_filter, List.mem_range]",
        "  exact ⟨by omega, hc⟩",
        "",
        "theorem all_residues_covered_by_table (r : Nat) (hr : r < 3301) :",
        "    ∃ m : Nat, (m = 0 ∨ m ∈ seeds) ∧ (",
        "      r = m ∨ r = (3300*m)%3301 ∨ r = (1726*m)%3301 ∨",
        "      r = (1575*m)%3301 ∨ r = (1574*m)%3301 ∨",
        "      r = (1727*m)%3301) := by",
        "  obtain ⟨m, hm, hc, hform⟩ := all_residues_covered r hr",
        "  refine ⟨m, ?_, hform⟩",
        "  rcases hc with hz | hc",
        "  · exact Or.inl hz",
        "  · exact Or.inr (canonical_mem m hm hc)",
        "",
        "#print axioms all_residues_covered",
        "#print axioms all_residues_covered_by_table",
        "end SplitPrimeCanonicalCover",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    generated = source()
    if sys.argv[1:] == ["--write"]:
        OUT.write_text(generated)
    elif sys.argv[1:] == []:
        assert OUT.read_text() == generated
    else:
        raise SystemExit("usage: generate_split_prime_canonical_cover.py [--write]")
    print("source_sha256", sha256(generated.encode()).hexdigest())

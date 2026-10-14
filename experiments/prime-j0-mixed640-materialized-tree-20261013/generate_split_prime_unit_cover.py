#!/usr/bin/env python3
"""Emit a kernel-checked finite certificate for the six-unit quotient cover."""

from hashlib import sha256
from pathlib import Path
import sys


P = 3301
MAX_SEED = 1064
UNITS = (1, 3300, 1726, 1575, 1574, 1727)
FIRST_MIDDLE = 1065
LAST_MIDDLE = 2236
CHUNK = 50
OUT = Path(__file__).with_name("SplitPrimeUnitCover.lean")


def source() -> str:
    lookup = {0: (0, 1)}
    for seed in range(1, MAX_SEED + 1):
        for unit in UNITS:
            residue = unit * seed % P
            lookup.setdefault(residue, (seed, unit))
    assert len(lookup) == P
    assert max(seed for seed, _ in lookup.values()) == MAX_SEED
    chunks = [(first, min(first + CHUNK - 1, LAST_MIDDLE))
              for first in range(FIRST_MIDDLE, LAST_MIDDLE + 1, CHUNK)]
    lines = [
        "import Lean",
        "set_option maxHeartbeats 0",
        "namespace SplitPrimeUnitCover",
        "",
        "-- This explicit finite certificate uses kernel reduction (`decide`), not",
        "-- native evaluation. All 3301 residues are covered by one of six units.",
        "def covered (r : Nat) : Prop :=",
        "  ∃ m : Nat, m ≤ 1064 ∧ (",
        "    r = m ∨ r = (3300*m)%3301 ∨ r = (1726*m)%3301 ∨",
        "    r = (1575*m)%3301 ∨ r = (1574*m)%3301 ∨ r = (1727*m)%3301)",
        "",
        "theorem direct_low (r : Nat) (hr : r ≤ 1064) : covered r := by",
        "  exact ⟨r, hr, Or.inl rfl⟩",
        "",
        "theorem direct_high (r : Nat) (hlo : 2237 ≤ r) (hhi : r < 3301) : covered r := by",
        "  refine ⟨3301-r, by omega, ?_⟩",
        "  right",
        "  left",
        "  omega",
        "",
    ]
    for index, (first, last) in enumerate(chunks):
        residues = list(range(first, last + 1))
        lines.append(
            f"theorem slice_{index} (r : Nat) (lo : {first} ≤ r) "
            f"(hi : r ≤ {last}) : covered r := by")
        lines.append("  have h : " + " ∨ ".join(
            f"r = {residue}" for residue in residues) + " := by omega")
        lines.append("  rcases h with " + " | ".join("h" for _ in residues))
        for residue in residues:
            seed, _ = lookup[residue]
            assert any(unit * seed % P == residue for unit in UNITS)
            lines.append(
                f"  · subst r; exact ⟨{seed}, by decide, by decide⟩")
        lines.append("")
    lines += [
        "theorem all_residues_covered (r : Nat) (hr : r < 3301) : covered r := by",
        "  by_cases hlow : r ≤ 1064",
        "  · exact direct_low r hlow",
        "  by_cases hhigh : 2237 ≤ r",
        "  · exact direct_high r hhigh hr",
    ]
    for index, (_, last) in enumerate(chunks[:-1]):
        lines += [
            f"  by_cases h{index} : r ≤ {last}",
            f"  · exact slice_{index} r (by omega) h{index}",
        ]
    lines += [
        f"  exact slice_{len(chunks)-1} r (by omega) (by omega)",
        "",
        "#print axioms all_residues_covered",
        "end SplitPrimeUnitCover",
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
        raise SystemExit("usage: generate_split_prime_unit_cover.py [--write]")
    print("source_sha256", sha256(generated.encode()).hexdigest())

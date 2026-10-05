"""Candidate and explicit-isogeny-path registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ec import ShortWeierstrassCurve


def _as_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    return int(value, 0) if str(value).lower().startswith(("0x", "-0x")) else int(value)


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    p: int
    a: int
    b: int
    n: int
    gx: int
    gy: int
    j_invariant: int
    path: tuple[dict[str, Any], ...]
    properties: dict[str, Any]
    cost_accounting: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Candidate":
        curve = value["curve"]
        generator = curve["generator"]
        return cls(
            candidate_id=value["candidate_id"],
            p=_as_int(curve["p"]),
            a=_as_int(curve["a"]),
            b=_as_int(curve["b"]),
            n=_as_int(curve["n"]),
            gx=_as_int(generator["x"]),
            gy=_as_int(generator["y"]),
            j_invariant=_as_int(curve["j_invariant"]),
            path=tuple(value.get("path", [])),
            properties=dict(value.get("properties", {})),
            cost_accounting=dict(value.get("cost_accounting", {})),
        )

    def validate(self) -> None:
        model = ShortWeierstrassCurve(self.p, self.a, self.b)
        generator = model.from_affine((self.gx, self.gy))
        if model.j_invariant() != self.j_invariant:
            raise ValueError(f"{self.candidate_id}: incorrect j-invariant")
        if generator.is_infinity:
            raise ValueError(f"{self.candidate_id}: generator is infinity")
        if not model.scalar_mul(self.n, generator).is_infinity:
            raise ValueError(f"{self.candidate_id}: generator does not have order n")
        for index, step in enumerate(self.path):
            required = {"degree", "domain_j", "codomain_j", "map"}
            missing = required.difference(step)
            if missing:
                raise ValueError(
                    f"{self.candidate_id}: path step {index} lacks {sorted(missing)}"
                )


def load_candidates(path: str | Path) -> list[Candidate]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported candidate schema")
    candidates = [Candidate.from_mapping(item) for item in payload["candidates"]]
    for candidate in candidates:
        candidate.validate()
    return candidates

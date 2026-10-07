"""TOML configuration for lit-watch (stdlib tomllib, no dependency)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = """\
# lit-watch configuration. Weights are arbitrary positive numbers; title hits
# count TITLE_MULT times an abstract hit. Scores are comparable only within
# one config version (recorded on every digest).

[general]
db_path = "litwatch.db"
user_agent = "lit-watch/0.1 (+https://github.com/aburan28/cryptanalysis)"
request_delay_seconds = 3.0
max_results_per_query = 25
lookback_days = 7
title_mult = 3.0
candidate_threshold = 8.0
watch_threshold = 3.0

[[topics]]
name = "ecdlp-index-calculus"
weight = 3.0
keywords = ["index calculus", "ECDLP", "elliptic curve discrete logarithm",
  "point decomposition", "summation polynomial", "Semaev", "Weil descent"]

[[topics]]
name = "isogeny"
weight = 3.0
keywords = ["isogeny", "isogenies", "SIDH", "SQIsign", "volcano",
  "endomorphism ring"]

[[topics]]
name = "discrete-log"
weight = 2.0
keywords = ["discrete logarithm", "discrete log", "Pollard rho",
  "baby-step giant-step", "Pohlig-Hellman", "DLOG"]

[[topics]]
name = "fine-grained"
weight = 3.0
keywords = ["3SUM", "3-SUM", "APSP", "fine-grained", "SETH", "Orthogonal Vectors",
  "Exact Triangle", "subquadratic", "subcubic"]

[[topics]]
name = "algebraic-solving"
weight = 2.0
keywords = ["Gr\\u00f6bner", "Grobner", "F4", "F5", "XL algorithm", "MutantXL",
  "MQ problem", "multivariate quadratic", "MinRank", "SAT solver",
  "first fall degree", "degree of regularity"]

[[topics]]
name = "lattices-pqc"
weight = 1.0
keywords = ["lattice", "LWE", "SIS", "NTRU", "Kyber", "Dilithium",
  "fully homomorphic", "FHE"]

[[topics]]
name = "general-breakthrough"
weight = 1.0
keywords = ["breakthrough", "refutes", "refuting", "first subquadratic",
  "first subcubic", "polynomial improvement", "near-linear", "quasilinear"]

[arxiv]
categories = ["cs.CR", "cs.CC", "cs.DS", "math.NT", "math.AG"]
# Extra free-text queries run in addition to per-topic queries.
queries = ["index calculus elliptic", "isogeny cryptanalysis",
  "3SUM subquadratic", "point decomposition problem"]

[eprint]
# RSS is always fetched; these search terms add targeted coverage.
queries = ["index calculus", "isogeny", "discrete logarithm", "3SUM",
  "summation polynomial"]
max_search_pages = 1

[github]
# Repository search: monthly window, sorted by stars gained implicitly via
# created-date + star floor. Keep queries few: authenticated search allows
# 30 requests/minute.
queries = ["ECDLP", "isogeny", "3SUM", "topic:lean4"]
min_stars = 5
# Repos/orgs whose releases are always worth a look, `owner/name` form.
watch_repos = []
"""


@dataclass
class Topic:
    name: str
    weight: float
    keywords: list[str]


@dataclass
class Config:
    db_path: str = "litwatch.db"
    user_agent: str = "lit-watch/0.1"
    request_delay_seconds: float = 3.0
    max_results_per_query: int = 25
    lookback_days: int = 7
    title_mult: float = 3.0
    candidate_threshold: float = 8.0
    watch_threshold: float = 3.0
    topics: list[Topic] = field(default_factory=list)
    arxiv_categories: list[str] = field(default_factory=list)
    arxiv_queries: list[str] = field(default_factory=list)
    eprint_queries: list[str] = field(default_factory=list)
    eprint_max_search_pages: int = 1
    github_queries: list[str] = field(default_factory=list)
    github_min_stars: int = 5
    github_watch_repos: list[str] = field(default_factory=list)


def load(path: str | Path | None) -> Config:
    """Load config.toml; None means built-in defaults."""
    data: dict = {}
    if path is not None:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    g = data.get("general", {})
    cfg = Config(
        db_path=g.get("db_path", "litwatch.db"),
        user_agent=g.get("user_agent", "lit-watch/0.1"),
        request_delay_seconds=float(g.get("request_delay_seconds", 3.0)),
        max_results_per_query=int(g.get("max_results_per_query", 25)),
        lookback_days=int(g.get("lookback_days", 7)),
        title_mult=float(g.get("title_mult", 3.0)),
        candidate_threshold=float(g.get("candidate_threshold", 8.0)),
        watch_threshold=float(g.get("watch_threshold", 3.0)),
        topics=[Topic(t["name"], float(t.get("weight", 1.0)), list(t.get("keywords", [])))
                for t in data.get("topics", [])],
        arxiv_categories=list(data.get("arxiv", {}).get("categories", [])),
        arxiv_queries=list(data.get("arxiv", {}).get("queries", [])),
        eprint_queries=list(data.get("eprint", {}).get("queries", [])),
        eprint_max_search_pages=int(data.get("eprint", {}).get("max_search_pages", 1)),
        github_queries=list(data.get("github", {}).get("queries", [])),
        github_min_stars=int(data.get("github", {}).get("min_stars", 5)),
        github_watch_repos=list(data.get("github", {}).get("watch_repos", [])),
    )
    return cfg


def write_default(path: str | Path) -> None:
    Path(path).write_text(DEFAULT_CONFIG)

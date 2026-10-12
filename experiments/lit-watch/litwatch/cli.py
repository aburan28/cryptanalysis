"""CLI: init, fetch, digest, list."""

from __future__ import annotations

import argparse
import functools
import json
import sys
import time
import traceback
from pathlib import Path

from . import config as config_mod
from . import rank as rank_mod
from . import report as report_mod
from . import sources
from . import store as store_mod


def _resolve_db(cfg_path: Path, db_path: str) -> Path:
    p = Path(db_path)
    return p if p.is_absolute() else (cfg_path.parent / p)


def _load_config(path: str) -> tuple[config_mod.Config, Path]:
    cfg_path = Path(path)
    cfg = config_mod.load(cfg_path)
    return cfg, cfg_path


def cmd_init(args) -> int:
    if Path(args.config).exists() and not args.force:
        print(f"{args.config} exists (use --force to overwrite)", file=sys.stderr)
        return 1
    config_mod.write_default(args.config)
    print(f"wrote {args.config}")
    return 0


def _paced(cfg, calls):
    """Run [(label, thunk)] with polite delays; collect (label, items|error)."""
    out = []
    for i, (label, thunk) in enumerate(calls):
        if i:
            time.sleep(cfg.request_delay_seconds)
        try:
            out.append((label, thunk()))
        except Exception as exc:  # noqa: BLE001 -- one source must not kill a run
            print(f"warning: {label} failed: {exc}", file=sys.stderr)
            traceback.print_exc(limit=1)
            out.append((label, exc))
    return out


def cmd_fetch(args) -> int:
    cfg, cfg_path = _load_config(args.config)
    db = store_mod.connect(_resolve_db(cfg_path, cfg.db_path))
    get = functools.partial(sources.http_get, user_agent=cfg.user_agent)
    gh_get = functools.partial(sources.github_get, user_agent=cfg.user_agent)

    calls = []
    for q in cfg.arxiv_queries:
        calls.append((f"arxiv:{q}", functools.partial(
            sources.fetch_arxiv, q, cfg.max_results_per_query, get)))
    calls.append(("eprint-rss", functools.partial(sources.fetch_eprint_rss, get)))
    for q in cfg.eprint_queries:
        calls.append((f"eprint:{q}", functools.partial(
            sources.fetch_eprint_search, q, cfg.eprint_max_search_pages, get)))
    since = sources.days_ago_iso(max(cfg.lookback_days, 1) * 2)
    for q in cfg.github_queries:
        calls.append((f"github:{q}", functools.partial(
            sources.github_search_repos, q, since, cfg.github_min_stars,
            cfg.max_results_per_query, gh_get)))
    for repo in cfg.github_watch_repos:
        calls.append((f"github-releases:{repo}", functools.partial(
            sources.github_repo_releases, repo, gh_get)))

    run_id = store_mod.start_run(db, json.dumps({"kind": "fetch"}))
    new_count, failures = 0, 0
    for label, result in _paced(cfg, calls):
        if isinstance(result, Exception):
            failures += 1
            continue
        fresh = sum(store_mod.upsert(db, it) for it in result)
        new_count += fresh
        print(f"{label}: {len(result)} fetched, {fresh} new")
    db.commit()
    store_mod.finish_run(db, run_id, new_count)
    print(f"run {run_id}: {new_count} new items, {failures} failed sources")
    return 0 if failures == 0 else 2


def cmd_digest(args) -> int:
    cfg, cfg_path = _load_config(args.config)
    db = store_mod.connect(_resolve_db(cfg_path, cfg.db_path))
    days = args.days if args.days is not None else cfg.lookback_days
    recent = []
    for row in store_mod.list_recent(db, limit=2000):
        full = store_mod.get(db, row["source"], row["ext_id"])
        if full is None:
            continue
        dates = [full.get("published"), full.get("updated"),
                 (full.get("first_seen") or "")[:10] or None]
        if any(sources.within_days(d, days) for d in dates):
            recent.append(full)
    scored = rank_mod.rank_items(recent, cfg)
    kept = [r for r in scored if r[2] != "noise"]
    for it, _s, _t, _topics in kept:
        it["_new"] = sources.within_days((it.get("first_seen") or "")[:10] or None,
                                          days)
    run_id = store_mod.start_run(db, json.dumps({"kind": "digest", "days": days}))
    store_mod.save_scores(db, run_id, kept)
    store_mod.finish_run(db, run_id, len(kept))
    text = report_mod.render(kept, run_id, sources.today_iso(), len(recent))
    if args.out:
        Path(args.out).write_text(text)
        print(f"wrote {args.out} ({len(kept)} items)")
    else:
        print(text)
    return 0


def cmd_list(args) -> int:
    cfg, cfg_path = _load_config(args.config)
    db = store_mod.connect(_resolve_db(cfg_path, cfg.db_path))
    for row in store_mod.list_recent(db, limit=args.limit):
        print(f"{row['published'] or '?'} [{row['source']}] {row['title'][:100]}")
        print(f"    {row['url']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="litwatch", description=__doc__)
    ap.add_argument("--config", default="config.toml", help="path to config.toml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="write a default config.toml")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)
    p = sub.add_parser("fetch", help="fetch all sources into the store")
    p.set_defaults(func=cmd_fetch)
    p = sub.add_parser("digest", help="rank recent items and render a digest")
    p.add_argument("--days", type=int, default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_digest)
    p = sub.add_parser("list", help="list recent stored items")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_list)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))

"""SQLite store: dedupe by (source, ext_id), keep longest abstract, score rows."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  source TEXT NOT NULL,
  ext_id TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  authors TEXT NOT NULL DEFAULT '[]',
  url TEXT NOT NULL DEFAULT '',
  published TEXT,
  updated TEXT,
  abstract TEXT NOT NULL DEFAULT '',
  categories TEXT NOT NULL DEFAULT '[]',
  extra TEXT NOT NULL DEFAULT '{}',
  first_seen TEXT NOT NULL DEFAULT (datetime('now')),
  last_seen TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (source, ext_id)
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started TEXT NOT NULL DEFAULT (datetime('now')),
  finished TEXT,
  new_items INTEGER NOT NULL DEFAULT 0,
  config TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS scores (
  source TEXT NOT NULL,
  ext_id TEXT NOT NULL,
  run_id INTEGER NOT NULL,
  score REAL NOT NULL,
  tier TEXT NOT NULL,
  topics TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY (source, ext_id, run_id)
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def upsert(conn: sqlite3.Connection, item: dict) -> bool:
    """Insert or refresh one item. Returns True if it is new.

    Refresh keeps the longest abstract seen (ePrint search abstracts are
    truncated; RSS ones are fuller) and unions categories.
    """
    row = conn.execute(
        "SELECT abstract, categories FROM items WHERE source=? AND ext_id=?",
        (item["source"], item["ext_id"])).fetchone()
    if row is None:
        conn.execute(
            """INSERT INTO items (source, ext_id, title, authors, url, published,
                                  updated, abstract, categories, extra)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (item["source"], item["ext_id"], item.get("title", ""),
             _dump(item.get("authors", [])), item.get("url", ""),
             item.get("published"), item.get("updated"),
             item.get("abstract", ""), _dump(item.get("categories", [])),
             _dump(item.get("extra", {}))))
        return True
    old_abstract, old_cats = row
    abstract = item.get("abstract", "") or ""
    if len(old_abstract or "") >= len(abstract):
        abstract = old_abstract or ""
    try:
        cats = sorted(set(json.loads(old_cats or "[]")) | set(item.get("categories", [])))
    except json.JSONDecodeError:
        cats = list(item.get("categories", []))
    conn.execute(
        """UPDATE items SET title=COALESCE(NULLIF(?,''),title),
                            authors=?, url=COALESCE(NULLIF(?,''),url),
                            published=COALESCE(?,published),
                            updated=COALESCE(?,updated),
                            abstract=?, categories=?,
                            last_seen=datetime('now')
           WHERE source=? AND ext_id=?""",
        (item.get("title", ""), _dump(item.get("authors", [])), item.get("url", ""),
         item.get("published"), item.get("updated"), abstract, _dump(cats),
         item["source"], item["ext_id"]))
    return False


def get(conn: sqlite3.Connection, source: str, ext_id: str) -> dict | None:
    row = conn.execute(
        "SELECT source, ext_id, title, authors, url, published, updated,"
        " abstract, categories, extra, first_seen, last_seen FROM items"
        " WHERE source=? AND ext_id=?", (source, ext_id)).fetchone()
    if row is None:
        return None
    keys = ("source", "ext_id", "title", "authors", "url", "published", "updated",
            "abstract", "categories", "extra", "first_seen", "last_seen")
    d = dict(zip(keys, row))
    for k in ("authors", "categories", "extra"):
        d[k] = json.loads(d[k] or ("{}" if k == "extra" else "[]"))
    return d


def list_recent(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT source, ext_id, title, url, published, first_seen FROM items"
        " ORDER BY COALESCE(published, first_seen) DESC LIMIT ?", (limit,)).fetchall()
    return [dict(zip(("source", "ext_id", "title", "url", "published", "first_seen"), r))
            for r in rows]


def start_run(conn: sqlite3.Connection, config_json: str) -> int:
    cur = conn.execute("INSERT INTO runs (config) VALUES (?)", (config_json,))
    return int(cur.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, new_items: int) -> None:
    conn.execute("UPDATE runs SET finished=datetime('now'), new_items=? WHERE id=?",
                 (new_items, run_id))
    conn.commit()


def save_scores(conn: sqlite3.Connection, run_id: int,
                scored: list[tuple[dict, float, str, list[str]]]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO scores (source, ext_id, run_id, score, tier, topics)"
        " VALUES (?,?,?,?,?,?)",
        [(it["source"], it["ext_id"], run_id, score, tier, _dump(topics))
         for it, score, tier, topics in scored])
    conn.commit()

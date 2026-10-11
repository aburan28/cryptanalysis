# lit-watch: literature radar for algorithm breakthroughs

Monitors arXiv, the IACR ePrint archive, and GitHub for new results matching
configured topics (default: ECDLP/index calculus, isogenies, discrete logs,
fine-grained complexity, algebraic solving, lattices, general breakthroughs).
Local-first: fetchers pull per-query results, a SQLite store dedupes them, a
transparent keyword ranker scores relevance, and the reporter renders a digest.
Stdlib only (`tomllib`, `sqlite3`, `urllib`).

## Quickstart

```sh
cd experiments/lit-watch
python3 -m litwatch init            # writes config.toml (defaults)
python3 -m litwatch fetch           # pull all sources (~1-2 min, polite delays)
python3 -m litwatch digest --out digest.md   # ranked digest of the last 7 days
python3 -m litwatch list --limit 20 # recent stored items
```

`fetch` is incremental and idempotent: reruns only add what is new
(`(source, ext_id)` primary key; refresh keeps the longest abstract).
`digest --days N` re-ranks the window; scores save per run for audit.

GitHub search needs a token for its 30 req/min quota (unauthenticated search
is severely limited):

```sh
export GITHUB_TOKEN="$(gh auth token)"   # or a fine-grained PAT, no scopes needed
```

## Configuration (`config.toml`)

- `topics`: name, weight, keywords. Title hits count `title_mult` (default 3x)
  an abstract/category hit. Single short tokens match whole-word only.
- Tiers: `candidate_threshold` (default 8, "read this"), `watch_threshold`
  (default 3). Scores compare only within one config version.
- `arxiv.categories` + `arxiv.queries`: free-text `all:` queries sorted by
  submission date; `max_results_per_query` caps each.
- `eprint.queries`: targeted search terms on top of the always-fetched RSS
  feed; `max_search_pages` bounds HTML result pages (100/page).
- `github.queries` + `min_stars`: repos created in the window above the star
  floor; `watch_repos` (`owner/name`) adds release feeds.
- `lookback_days` (default 7) bounds digests; `request_delay_seconds`
  (default 3.0) paces requests; `db_path` is resolved relative to the config.

## Sources and politeness

| source | endpoint | auth | notes |
|---|---|---|---|
| arXiv | `export.arxiv.org/api/query` (Atom) | none | ~3s between calls per arXiv guidance; custom User-Agent |
| ePrint | `rss/rss.xml` + `/search` HTML | none | RSS is 100 items; search abstracts are truncated by the site |
| GitHub | REST search + releases | token recommended | stays far under 30 search req/min |

## Scheduling

Cron (weekly digest):

```cron
0 9 * * 1 cd /path/to/cryptanalysis/experiments/lit-watch && GITHUB_TOKEN=... python3 -m litwatch fetch && python3 -m litwatch digest --out digests/digest-$(date +\%F).md
```

GitHub Actions: `.github/workflows/lit-watch.yml` is manual-only
(`workflow_dispatch`): run it from the Actions tab and download the digest
artifact. It is deliberately not scheduled, to avoid surprise CI load.

## Limitations (read before citing a digest)

- Ranking is keyword-based, not semantic: it surfaces candidates for human
  reading, never a verdict. A digest hit is not a verified breakthrough.
- ePrint search abstracts are truncated server-side; RSS abstracts are fuller.
  The store keeps the longest seen.
- arXiv `max_results_per_query` caps recall per query; widen queries or the
  cap for exhaustive sweeps.
- GitHub code search is intentionally not used (noisy); repo + release
  signals only.
- Runtime state (`litwatch.db`) is git-ignored; digests are local unless you
  commit them deliberately.
- First run ingests full search history, so expect a large bootstrap digest.
  Steady-state runs surface mostly newly seen items (marked NEW).

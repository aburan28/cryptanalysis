"""Markdown digest renderer for ranked items."""

from __future__ import annotations


def _one_line(text: str, limit: int = 280) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render(scored: list[tuple[dict, float, str, list[str]]], run_id: int,
           when: str, considered: int) -> str:
    cands = [r for r in scored if r[2] == "candidate"]
    watch = [r for r in scored if r[2] == "watch"]
    new_marks = sum(1 for r in scored if r[0].get("_new"))
    lines = [
        f"# lit-watch digest (run {run_id}, {when})",
        "",
        f"{considered} items in scope; {len(cands)} breakthrough candidates, "
        f"{len(watch)} to watch ({new_marks} first seen this window). "
        f"Scores compare only within one config version.",
        "",
    ]
    for heading, rows in (("## Breakthrough candidates", cands),
                          ("## Watch list", watch)):
        lines.append(heading)
        lines.append("")
        if not rows:
            lines.append("_None._")
            lines.append("")
            continue
        for it, score, _tier, topics in rows:
            authors = ", ".join(it.get("authors", [])[:4])
            if len(it.get("authors", [])) > 4:
                authors += ", et al."
            new = " NEW" if it.get("_new") else ""
            lines.append(f"### [{it.get('title') or it['ext_id']}]({it.get('url', '')}) "
                         f"`{score:.1f}`{new}")
            lines.append("")
            meta = f"{it['source']}:{it['ext_id']}"
            if it.get("published"):
                meta += f" · {it['published']}"
            if authors:
                meta += f" · {authors}"
            if topics:
                meta += f" · topics: {', '.join(topics)}"
            lines.append(meta)
            lines.append("")
            if it.get("abstract"):
                lines.append(_one_line(it["abstract"]))
                lines.append("")
    return "\n".join(lines)

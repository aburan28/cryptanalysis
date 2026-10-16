#!/bin/bash
# SessionStart hook for Claude Code on the web: keep a cairn node running in
# this container, joined to the published seed nodes (scripts/cairn-node.sh).
# Local sessions are left alone. Never fatal: a session that starts without the
# node is better than one that does not start.
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
"${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"/scripts/cairn-node.sh ensure 2>&1 | tail -n 6
exit 0

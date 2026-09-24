#!/bin/sh
# msolve with -v 2, statistics copied to $MSOLVE_STATS (pdp_descendants.py).
exec msolve -v 2 "$@" > "${MSOLVE_STATS:-/dev/null}"

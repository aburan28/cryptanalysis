#!/bin/bash
set -euo pipefail
apt-get update -qq
systems=$(apt-cache pkgnames | sed -n '/^nsight-systems-[0-9]/p' | sort -V | tail -n 1)
compute=$(apt-cache pkgnames | sed -n '/^nsight-compute-[0-9]/p' | sort -V | tail -n 1)
test -n "$systems"
test -n "$compute"
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends build-essential python3 "$systems" "$compute"
printf 'Selected profiler packages: %s %s\n' "$systems" "$compute"

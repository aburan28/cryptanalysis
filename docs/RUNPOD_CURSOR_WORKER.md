# Cursor worker on a RunPod

Run Cloud Agent tool calls on a persistent RunPod (GPU calculations stay on
the pod). The agent loop still runs in Cursor's cloud; the worker opens an
outbound HTTPS connection — no inbound ports beyond the pod's existing SSH.

## Prerequisites

1. A **running** RunPod with SSH (TCP 22 mapped). Default target name:
   `solar_ivory_canidae`.
2. Cloud Agent secrets (or local env):
   - `RUNPOD_API_KEY` — [RunPod console → Settings](https://console.runpod.io/user/settings)
   - `CURSOR_API_KEY` — personal user key from [Cursor Dashboard → API Keys](https://cursor.com/dashboard/api)
     (My Machines workers reject service-account / org admin keys)

## One-shot attach

From a machine that can reach RunPod's API (this Cloud Agent once secrets
are injected, or your laptop):

```sh
export RUNPOD_API_KEY=...
export CURSOR_API_KEY=...
./scripts/runpod_attach_cursor_worker.sh
```

Optional overrides: `POD_NAME`, `WORKER_NAME`, `REPO_URL`, `WORKER_DIR`.

The script will:

1. Resolve the pod with `runpodctl pod list --name …`
2. Register the local SSH pubkey and **merge it into the pod's `PUBLIC_KEY` env**
   (account-level `ssh add-key` alone does not update an already-rented pod;
   a restart follows when the key was missing)
3. Install the Cursor CLI on the pod
4. Clone/update `cryptanalysis` under `/root/cryptanalysis` (avoids geesefs `/workspace` chmod issues)
5. Start `agent worker --name <pod> --idle-release-timeout 0` in tmux (API key via `/root/.cursor-worker/api-key`)

## Status check

```sh
export RUNPOD_API_KEY=...
./scripts/runpod_cursor_worker_status.sh
```

Exits non-zero if the pod is stopped, SSH fails, or the `cursor-worker` tmux
session / `agent worker` process is missing.

## Using the worker

- In https://cursor.com/agents, choose the machine named like the pod.
- From Slack/GitHub triggers: `worker=solar_ivory_canidae` (must match
  `--name` and the worker must be registered for this repo's remote).

Logs on the pod:

```sh
tmux attach -t cursor-worker
```

## Manual install (on the pod)

Prefer the scripts above. Manual equivalent:

```sh
curl -fsS https://cursor.com/install | bash
git -c core.filemode=false clone https://github.com/aburan28/cryptanalysis.git /root/cryptanalysis
# then run scripts/runpod_cursor_worker_remote.sh with CURSOR_API_KEY set
```

Keep the tmux/`agent worker` process running. Docs:
[My Machines](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines).

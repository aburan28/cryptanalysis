# Conductor-connected agents and ECC2K workers in the cloud

The Runpod launcher attaches a local terminal to Codex or Claude Code through
`conductor wrap`. The ECC2K bridge reads durable S3 or DynamoDB slot records
and reports status and guard decisions to Conductor without changing the GPU
worker's lease or checkpoint flow. Use a dedicated Pod for agent work.

Cloud hosts need a Conductor HTTPS endpoint they can reach. A URL bound to
`127.0.0.1` on the laptop is not reachable from a Pod. Give each host its own
Conductor project credential through a trusted join link or secret manager;
keep bearer tokens out of command arguments and repository files.

## Connect

Copy the **exact SSH command** from the chosen Pod's Connect tab. Put its
host, user, port (if present), and key into a local `~/.ssh/config` Host entry.
For a Pod with a public IP, the entry looks like:

```sshconfig
Host runpod
  HostName POD_PUBLIC_IP
  User root
  Port POD_SSH_PORT
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
```

For Runpod's basic SSH proxy, use the `USER@ssh.runpod.io` identity shown in
the Connect tab and omit `Port` unless that command supplies one. Basic SSH
does not support SCP/SFTP; public-IP SSH does. Verify the server host key on
first connection before accepting it. Do not disable host-key checking.

On the current worker Pod, the exposed TCP endpoint refused connections until
`sshd` was started inside the container. If this happens after the container
is recreated, enter through Runpod's basic SSH proxy and run:

```sh
mkdir -p /run/sshd
/usr/sbin/sshd -t && /usr/sbin/sshd
```

Then use the `runpod` alias for direct SSH. The worker template's startup
command does not start `sshd`, so this recovery step may be needed after a
container restart. Do not change the running research worker's startup command
just to add the agent runner.

## Install on the Pod

From this repository on the local machine:

```sh
ssh runpod 'bash -s' < scripts/bootstrap_remote_agents.sh
```

The script installs the two agent CLIs and a checksum-verified Conductor Linux
release only when missing, then prints their versions. Set
`CONDUCTOR_RELEASE_VERSION` to pin the release for repeatable bootstrap. It
needs `curl`, `git`, and `sha256sum` on the Pod. It does not move local
credentials or SSH private keys to the Pod.

Authenticate each CLI in an interactive session on the Pod:

```sh
ssh -tt runpod 'export PATH="$HOME/.local/bin:$PATH"; codex login --device-auth'
ssh -tt runpod 'export PATH="$HOME/.local/bin:$PATH"; claude'
```

For Codex, enable device-code sign-in in your ChatGPT security settings if
necessary. Complete the browser sign-in yourself; keep the one-time code and
auth cache private. For Claude Code, follow the login prompts in the Pod's
terminal or configure an authorized API credential on that Pod.

Join the intended Conductor project on the Pod using a project-scoped link
issued by its administrator. Run `conductor status` there before starting an
agent. For autonomous work, the project must be registered with this
repository and its approved task queue. A coding session already running
without `conductor wrap` starts reporting only on its next launch.

## Run

The repository must exist on the Pod at `REMOTE_AGENT_WORKDIR`. Set that
variable to its actual absolute path, then run:

```sh
export REMOTE_AGENT_WORKDIR=/workspace/cryptanalysis
scripts/remote_agent_runner.sh runpod check
scripts/remote_agent_runner.sh runpod codex
scripts/remote_agent_runner.sh runpod claude
scripts/remote_agent_runner.sh runpod worker --project cryptanalysis --concurrency 1
```

CLI arguments after `codex` or `claude` are forwarded through `conductor
wrap`; arguments after `worker` go to `conductor worker`. The `worker` mode is
an autonomous coding agent runner, separate from the ECC2K GPU client. The
launcher uses SSH's terminal mode for interactive sessions. It never copies
the repository or credentials; arrange repository access separately, using a
public-IP SSH connection for SCP or a Git remote available from the Pod.

Container home directories and installed binaries may be lost when a Pod is
recreated. Re-run the bootstrap and sign-in steps on a new container unless
you deliberately provide persistent storage for them.

## ECC2K status and safety observations

Run [the bridge](../ecc2k130/conductor_telemetry.py) on an existing host with
read access to the campaign's slot records and HTTPS access to Conductor.
It reads the same S3 `slots/slot-NNNNN.json` objects or DynamoDB slot table
used by the supervisor. Each one-shot invocation emits the latest state and,
for a terminal guard, a `safety.flag` record. Repeated polls use stable event
IDs, so Conductor deduplicates unchanged receipts. Schedule the command at a
modest interval, such as five minutes, after the Conductor endpoint is
deployed and the dry run is reviewed.

```sh
export CONDUCTOR_ENDPOINT=https://conductor.example.org
export CONDUCTOR_PROJECT=cryptanalysis
export CONDUCTOR_TOKEN_FILE=/run/secrets/conductor-project-token
python3 ecc2k130/conductor_telemetry.py --dry-run s3-slots \
  --bucket "$ECC_BUCKET" --prefix "${ECC_PREFIX:-}"
python3 ecc2k130/conductor_telemetry.py s3-slots \
  --bucket "$ECC_BUCKET" --prefix "${ECC_PREFIX:-}"
# Campaigns using DynamoDB slot leases instead:
python3 ecc2k130/conductor_telemetry.py dynamodb-slots --table "$ECC_TABLE"
```

The token file must be readable only by its owner. The bridge uses verified
TLS, reads AWS state, and posts bounded fields to Conductor: source, worker
run ID, status or guard code, observation time, and a SHA-256 evidence digest.
The exact canonical slot record and source are saved as
`~/.conductor/safety-context/<event_id>.json` with owner-only permissions.
`--dry-run` computes the digest without writing an evidence file or posting.
Keep this directory on persistent owner storage and set a retention policy;
the file may contain private campaign data. Conductor never receives the
record, raw logs, prompts, tool arguments, or credentials. A stale lease is
reported as `worker.status=stale`; it is not presented as a confirmed safety
decision.

For Codex approval requests on a dedicated agent Pod, add trusted Codex
`UserPromptSubmit` and `PermissionRequest` command hooks. For example, put
this in the Pod's `~/.codex/hooks.json` after setting the endpoint, project,
and token file in the environment that launches Codex:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 /workspace/cryptanalysis/ecc2k130/conductor_telemetry.py codex-hook", "timeout": 5}]}],
    "PermissionRequest": [{"hooks": [{"type": "command", "command": "python3 /workspace/cryptanalysis/ecc2k130/conductor_telemetry.py codex-hook", "timeout": 15}]}]
  }
}
```

The first hook saves the prompt and transcript location in an owner-only local
file. The second saves the exact available prompt and tool request as
`<event_id>.json`, then posts an `approval_requested` flag with its digest.
Use `CONDUCTOR_SAFETY_CONTEXT_DIR` on persistent owner storage if the Pod may
be replaced. Treat the directory as sensitive and keep its retention bounded.
Review and trust the hook definition with Codex `/hooks` before relying on it.
A permission request records that a gate fired; the later approval outcome
belongs to the harness or Conductor decision log. The hook path does not expose
internal platform classifier scores or hidden reasons. See the
[official Codex hooks guide](https://learn.chatgpt.com/docs/hooks) for the
current hook schema and trust flow.

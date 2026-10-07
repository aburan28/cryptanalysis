# A cairn pull request, ready to open

These two patches change [aburan28/cairn](https://github.com/aburan28/cairn)'s host
agent. They are kept here because the agent that wrote them could not push to
cairn. This branch exists only to carry them, and is not meant to be merged.

- `0001`: the probe reports only the GPUs a container can open.
- `0002`: `--unconfined-gpus` lets a host that is itself the jail run GPU jobs
  unconfined. A rented GPU pod is such a host: it has no engine or `/dev/kvm`
  inside.

`PR.md` has the title and description. `runpod-check.sh` and `runpod-check.txt`
are the check on a Runpod RTX 5090 pod and its output. The patches apply to
cairn `main` at `91c13f5`.

From a cairn checkout:

```sh
B=https://raw.githubusercontent.com/aburan28/cryptanalysis/cursor/cairn-unconfined-gpus-handoff-f26c/cloud/cairn-handoff/agent-unconfined-gpus
git switch -c cursor/agent-unconfined-gpus-f26c origin/main
curl -fsSL "$B/0001-agent-report-only-the-GPUs-a-container-can-open.patch" \
  "$B/0002-agent-let-an-operator-who-is-the-jail-hand-unconfine.patch" | git am
git push -u origin cursor/agent-unconfined-gpus-f26c
```

Then open the pull request with the title and body in `PR.md`. Until a cairn
release carries this, `cloud/cairn_queue.py` keeps asking for `gpus: 0`.

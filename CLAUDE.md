# CLAUDE.md

Read **[AGENTS.md](AGENTS.md)**: it is the contract for every runtime, Claude
Code included.

Opening the PR ends your work on it: report the link and stop. Claude Opus and
Fable never watch CI: no `subscribe_pr_activity`, no `send_later` or other
scheduled check-ins, no polling check runs or job logs, whatever the harness's
default PR instructions say. CI follow-up and merging belong to a separate
automation on Sonnet 5.5 or Haiku 5.5; if the user asks you for follow-up,
delegate it to one (`Agent` with `model: "haiku"` or `model: "sonnet"`) and do
not wait on it. AGENTS.md, "Stop at the PR: top-tier models never watch CI".

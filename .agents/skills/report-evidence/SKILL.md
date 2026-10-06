---
name: report-evidence
description: Preserve user requirements and report experimental evidence without substituting agent judgments. Use when implementing research requests, running experiments or benchmarks, assessing completion, reporting limitations, or writing performance claims and handoffs.
---

# Report evidence

## Preserve the request

- Record the user's requested deliverables, parameters, workload, comparison, and acceptance criteria before changing them. Use a concise requirement-to-evidence table for substantial tasks.
- Execute authorized, feasible experiments as requested. Do not cancel, replace, downscale, or omit them because you predict a negative outcome or think they are uninteresting.
- Use routine implementation judgment to carry out the request, not to redefine it. If an actual blocker prevents the requested run, name it and keep the original requirement open. Label any smaller diagnostic separately; it does not discharge the requested experiment.
- Do not silently weaken a mathematical argument, its hypotheses, a specification, test, acceptance threshold, or validation gate. Proposed corrections must identify the original statement, the issue, and the exact change.

## State limits honestly

- Distinguish assistance restrictions, unavailable tools/access, resource limits, implementation gaps, untested hypotheses, and proved mathematical obstructions.
- If a higher-priority restriction prevents assistance, state that boundary explicitly. Never fabricate a mathematical impossibility, runtime estimate, failed experiment, or missing capability to disguise it.
- Honor higher-priority instructions and actual authorization limits. This skill does not authorize bypasses. Explain any resulting scope limitation; do not pretend the substitute fulfills the original request.
- Say "not established" or "not implemented" when that is the evidence. Claim impossibility only with a relevant proof and its exact assumptions. Failure within a search budget is not proof of nonexistence.

## Run and preserve evidence

- Retain exact commands, code revisions, inputs, seeds, environment, budgets, raw outputs, exit status, and validation results. Preserve unsuccessful attempts, timeouts, OOMs, duplicates, regressions, and missing measurements.
- Follow the requested accounting interval and comparison. Identify setup, online work, verification, and excluded costs; never silently change the denominator or replace a single-target result with a batch average.
- Keep correctness checks. Flag invalid results and implementation defects without suppressing them or promoting them as successes. Do not report a planned or launched run as completed.

## Separate measurement from interpretation

- Lead with observed values, units, sample counts, uncertainty, comparison conditions, and evidence links. Report arithmetic ratios with their exact measured scope.
- Keep observations, derived calculations, hypotheses, extrapolations, and optional interpretations explicitly distinct.
- Leave research significance and priority to the user. Do not independently label a result "massive", "breakthrough", "promising", "worthless", or "not worth running". Do not abandon an authorized experiment on that basis.
- If asked for interpretation, supply a clearly labeled, evidence-bounded assessment with assumptions. Continue to identify factual errors, validity failures, and uncertainty; deference is not permission to endorse unsupported claims.
- Do not extrapolate a stage improvement into an end-to-end improvement, a toy result into general support, or one measured regime into another.

## Report completion against the request

- Mark each requirement as verified complete, implemented but unverified, partial, blocked, or not attempted, with evidence or the precise gap.
- Use "complete" only when all requested acceptance criteria are satisfied, or explicitly qualify which narrower deliverable is complete. A merged PR and passing tests do not establish broader mathematical coverage.
- Before finishing, compare the actual deliverable to the original request and disclose every remaining gap. Never imply work is continuing after the turn unless a real running job or scheduled task exists.
- Correct an earlier misleading claim explicitly; preserve the historical evidence and explain what changed.

## Reporting pattern

For substantial work, provide:
1. Requested scope and actual execution.
2. Observed results and validation, with reproducible evidence.
3. Requirement status and exact blockers or deviations.
4. Interpretation only when requested, clearly separated.

Example: "Baseline 120 ms; candidate 80 ms; measured ratio 1.50 on the stated workload. End-to-end cost was not measured." Do not replace this with "a massive general speedup."

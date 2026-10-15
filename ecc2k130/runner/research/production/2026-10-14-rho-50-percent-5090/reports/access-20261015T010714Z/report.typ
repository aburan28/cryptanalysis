#set page(paper: "a4", margin: (x: 19mm, y: 17mm))
#set text(font: "Arial", size: 9.5pt)
#set heading(numbering: none)

= RTX 5090 allocation observation

_Operational observations only. No GPU trial or campaign collection started._

The user-authorized test prepared the pinned ECC2K-130 Frobenius binary and an unchanged candidate source archive. The pinned SHA-256 was `0c02a3cfec9553a5def6e9df530c027a246648f6a6b8b7fef39c67e582aae9f4`; the source archive SHA-256 was `a4e1f5542420269af9771fa4e50c5ab6b76336afefc7633ff9fcda7a7cd4fb95` from commit `fb5ae4b9b9ef5c24780d5a82d04102ecffda2dd5`.

#image("allocation.svg", width: 100%)

== Provider observations

#table(
  columns: (24%, 12%, 47%, 17%),
  inset: 5pt,
  table.header([Cloud/request], [HTTP], [Recorded provider outcome], [Pod after]),
  [Community 1], [400], [Error body not retained; validation reason unknown], [0],
  [Community 2], [500], [No instances currently available], [0],
  [Secure Cloud], [500], [Account balance too low], [0],
)

The Community and Secure catalog quotes read before allocation were \$0.69 and \$1.19 per GPU-hour, respectively. The receipts show no allocated GPU duration; account billing was not independently checked. Each create request was followed by a successful inventory read with no pod matching the benchmark name. The first local Python CA error happened before a create call.

== Measurement boundary

The planned six host-reference compatibility cases, five paired A/B timing samples per worker population, DP32 corpus comparison and sustained collection check did not run. No 5090 performance ratio follows from these observations. The earlier Modal RTX PRO 6000 screen remains separate evidence.

_Sources:_ `PLAN.md`, `runpod_control.py`, `remote_pair.py`, and the three write-once `runs/*/runpod-create.json` receipts under `2026-10-14-rho-50-percent-5090`; derived `summary.json` and `allocation.svg` are beside this PDF.

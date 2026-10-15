# Render and evidence checks

The final four-page PDF was rendered with pdfTeX and each page visually
inspected from a 110-dpi PNG: equations, table columns, all graph axes and
captions, source links and the snapshot ID are legible. The final LaTeX log
contains no overfull boxes or unresolved controls. The initial layout-only
renderer failure on a null verification field is retained as
`render-null-verification.log`; pending records are now displayed correctly.
No solver or arithmetic source changed.

Final study PDF SHA-256:
`cd78fd3094498f134d650053c2e3c143d732e571417e014ff3fb5428b12a8ac4`

The fresh run manifest hashes 247 archived files. Its SHA-256 is
`78648cd9465564f4fd88ad448f0a76efa858bdeec590d5669b54b941db61ff69`.
Every entry verified. The earlier manifest remains
`c8d0187c974d82c33ab3055eb9f1951a116a125221004012b98c0ca606a2702d`
and every earlier file also verified unchanged. Twenty additional native
verifier invocations passed E and Jacobian checks against the public jobs.
Campaign source hashes and immutable binary hashes also verified.

The benchmark entry copies the inspected report and run PDF and all four
graphs as SVG, PDF and 150-dpi PNG from the study. Unchanged reference,
prefix-calibration and first-target figure bytes were retained; only the
new multi-target figure adds observations. No IC canonical graph is affected.

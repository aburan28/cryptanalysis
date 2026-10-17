#set page(paper: "a4", margin: 17mm)
#set text(font: "New Computer Modern", size: 9.2pt)
= ECC2K-130 rho: paired RTX 5090 screen
#text(fill: rgb("#52606d"))[15 October 2026 UTC | One completed Secure Cloud pod | Observations]

The exact pinned campaign binary (A) and the compatible four-warp Frobenius build (B) ran on one RTX 5090. Curve 131, signed-Frobenius iteration, batch 16, DP32, run ID 11000, 1,024 steps per launch, 64 launches per sample, and five alternating timed pairs per population. Warmups and pinned return controls are excluded from the plotted medians.

#image("rates.svg", width: 100%)

#text(size: 8pt)[Bars are medians of five timed samples per arm; whiskers are observed min/max. The paired-ratio panel uses five B/A pairs per population. Red lines mark the 1.5× raw-rate screen. Source: the immutable `runs/20261015T013232Z/result.json` and `run.log`.]

#table(
  columns: (1fr, 1fr, 1fr, 1fr),
  [Workers], [A median], [B median], [Paired B/A median],
  [87,040], [13.678], [14.681], [1.0745],
  [108,800], [12.606], [15.637], [1.2418],
  [120,320], [13.182], [10.350], [0.7847],
)
#text(size: 8pt)[Rates are billions of complete scalar updates per second. Full samples, DP counts, corpus hashes, paired ranges, and return rates are in `summary.json` and the raw result.]

== Controls and measurement boundary

Six fresh-state and cross-binary resume cases passed, with 10,249 host-reference verifications. All 39 warm, timed and return samples reported exact update counts and zero dropped DP records. At each population, A and B produced an identical sorted DP32 corpus. The candidate binary saved locally matches the tested SHA-256. The completed run lasted from 01:36:14 to 01:49:14 UTC.

The best tested A median was 13.678 billion/s at 87,040 workers; the best tested B median was 15.637 billion/s at 108,800. Their derived cross-population raw-rate ratio is 1.1432 and is descriptive because worker counts differ. Each same-population paired median is below 1.5. The 120,320-worker B rate was lower than A on this RTX 5090. The timing excludes S3 delivery, ingest, collision processing, and sustained campaign operation.

The first Community Cloud pod failed at CUDA device initialization before any timed sample. Both the pinned and candidate binaries failed there, so this is recorded as an infrastructure attempt. Both pods were deleted; each delete returned HTTP 204 and its follow-up lookup returned HTTP 404. The full paths and hashes are in `README.md` and `summary.json`.

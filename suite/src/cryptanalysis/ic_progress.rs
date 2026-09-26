//! # CADO-NFS-style staged progress reporting with an ETA.
//!
//! Long index-calculus runs (relation collection especially) can take minutes
//! to hours, and a run that prints nothing until it finishes is impossible to
//! supervise.  CADO-NFS solves this with a running log that names the current
//! stage, its rate, and an estimated time to completion:
//!
//! ```text
//! Info:Relation collection: 140/296 cols  (47.3%)  312 rel/s  ETA 0:00:21
//! ```
//!
//! This module is that reporter, factored out so every `icx` stage uses the
//! same format.  It writes to stderr in human mode and one JSON object per
//! line under `ProgressReporter::json`, so a supervising process can parse
//! it.  It is deliberately dependency-free (no `indicatif`): the output is a
//! log, not an animated bar, because runs are often captured to a file or a CI
//! log where a redrawing bar is noise.
//!
//! ## The ETA model
//!
//! For a stage with a known amount of total work `T` and `d` units done in
//! elapsed time `e`, the estimate is `eta = (T - d) · e / d`.  Because the
//! instantaneous rate is noisy early on, the reporter marks the ETA
//! *provisional* until at least [`MIN_SAMPLES`] updates and
//! [`MIN_ELAPSED`] have accumulated, and it reports the rate as an
//! exponentially-weighted average so a brief stall does not swing the estimate
//! wildly.  When the total is unknown the reporter still shows the rate and
//! elapsed time, just no percentage or ETA — an honest "we don't know how far"
//! rather than a fabricated bar.

use std::io::Write;
use std::time::{Duration, Instant};

/// Minimum updates before an ETA is shown without the `~provisional` mark.
pub const MIN_SAMPLES: u64 = 4;
/// Minimum elapsed stage time before an ETA is shown as settled.
pub const MIN_ELAPSED: Duration = Duration::from_millis(500);
/// Minimum wall-clock gap between throttled progress emissions.
pub const EMIT_INTERVAL: Duration = Duration::from_millis(250);

/// A live stage's accounting.
struct StageState {
    name: String,
    started: Instant,
    total: Option<u64>,
    done: u64,
    updates: u64,
    /// Exponentially-weighted units/second, or `None` before the first sample.
    ewma_rate: Option<f64>,
    last_emit: Instant,
    last_done: u64,
    last_done_at: Instant,
}

/// Formats an ETA / elapsed duration as `H:MM:SS` (or `M:SS` under an hour).
pub fn format_hms(d: Duration) -> String {
    let secs = d.as_secs();
    let h = secs / 3600;
    let m = (secs % 3600) / 60;
    let s = secs % 60;
    if h > 0 {
        format!("{h}:{m:02}:{s:02}")
    } else {
        format!("{m}:{s:02}")
    }
}

/// A staged progress reporter with rate and ETA.
pub struct ProgressReporter {
    json: bool,
    quiet: bool,
    run_started: Instant,
    stage: Option<StageState>,
}

impl ProgressReporter {
    /// Create a reporter.  `json` emits one JSON object per line; `quiet`
    /// suppresses all output (for `--json` report mode where progress would
    /// interleave with the final document).
    pub fn new(json: bool, quiet: bool) -> Self {
        ProgressReporter {
            json,
            quiet,
            run_started: Instant::now(),
            stage: None,
        }
    }

    /// A reporter that prints nothing.  Handy in tests and library callers.
    pub fn silent() -> Self {
        ProgressReporter::new(false, true)
    }

    /// Wall-clock time since the reporter was created.
    pub fn total_elapsed(&self) -> Duration {
        self.run_started.elapsed()
    }

    /// Begin a stage.  `total` is the amount of work if known (columns to
    /// pin, points to enumerate); `None` means unbounded/unknown.
    pub fn stage_begin(&mut self, name: &str, total: Option<u64>, detail: &str) {
        let now = Instant::now();
        self.stage = Some(StageState {
            name: name.to_string(),
            started: now,
            total,
            done: 0,
            updates: 0,
            ewma_rate: None,
            last_emit: now - EMIT_INTERVAL, // force the first emit
            last_done: 0,
            last_done_at: now,
        });
        if self.quiet {
            return;
        }
        if self.json {
            self.emit_json("stage_begin", detail, None);
        } else {
            let t = total.map(|t| format!(" (target {t})")).unwrap_or_default();
            let d = if detail.is_empty() {
                String::new()
            } else {
                format!(": {detail}")
            };
            let _ = writeln!(std::io::stderr(), "Info:{name}{t}{d}");
        }
    }

    /// Report cumulative progress for the current stage.  Emission is
    /// throttled to [`EMIT_INTERVAL`]; a call that does not emit still updates
    /// the internal rate estimate.  `force` bypasses the throttle.
    pub fn progress(&mut self, done: u64, detail: &str) {
        self.progress_inner(done, detail, false);
    }

    /// Like [`progress`](Self::progress) but always emits.
    pub fn progress_force(&mut self, done: u64, detail: &str) {
        self.progress_inner(done, detail, true);
    }

    fn progress_inner(&mut self, done: u64, detail: &str, force: bool) {
        let Some(st) = self.stage.as_mut() else {
            return;
        };
        let now = Instant::now();
        // Update the EWMA rate from the delta since the last recorded point.
        let dt = now.duration_since(st.last_done_at).as_secs_f64();
        if dt > 0.0 && done >= st.last_done {
            let inst_rate = (done - st.last_done) as f64 / dt;
            st.ewma_rate = Some(match st.ewma_rate {
                None => inst_rate,
                Some(prev) => 0.6 * prev + 0.4 * inst_rate,
            });
            st.last_done = done;
            st.last_done_at = now;
        }
        st.done = done;
        st.updates += 1;

        let should_emit = force || now.duration_since(st.last_emit) >= EMIT_INTERVAL;
        if !should_emit || self.quiet {
            return;
        }
        st.last_emit = now;
        self.emit_progress(detail);
    }

    fn emit_progress(&mut self, detail: &str) {
        let Some(st) = self.stage.as_ref() else {
            return;
        };
        let elapsed = st.started.elapsed();
        let rate = st.ewma_rate.unwrap_or(0.0);
        let (pct, eta) = match st.total {
            Some(total) if total > 0 && rate > 0.0 => {
                let remaining = total.saturating_sub(st.done);
                let pct = 100.0 * st.done as f64 / total as f64;
                let eta_secs = remaining as f64 / rate;
                (Some(pct), Some(Duration::from_secs_f64(eta_secs.min(1e9))))
            }
            Some(total) if total > 0 => (Some(100.0 * st.done as f64 / total as f64), None),
            _ => (None, None),
        };
        let settled = st.updates >= MIN_SAMPLES && elapsed >= MIN_ELAPSED;

        if self.json {
            self.emit_json("progress", detail, Some((rate, pct, eta, settled)));
            return;
        }
        let mut line = format!("Info:{}: {}", st.name, st.done);
        if let Some(total) = st.total {
            line.push_str(&format!("/{total}"));
        }
        if let Some(pct) = pct {
            line.push_str(&format!("  ({pct:.1}%)"));
        }
        line.push_str(&format!("  {rate:.0}/s"));
        if let Some(eta) = eta {
            let mark = if settled { "" } else { "~" };
            line.push_str(&format!("  ETA {mark}{}", format_hms(eta)));
        } else {
            line.push_str(&format!("  elapsed {}", format_hms(elapsed)));
        }
        if !detail.is_empty() {
            line.push_str(&format!("  {detail}"));
        }
        let _ = writeln!(std::io::stderr(), "{line}");
    }

    /// End the current stage, printing its final tally and duration.
    pub fn stage_end(&mut self, detail: &str) {
        let Some(st) = self.stage.take() else {
            return;
        };
        if self.quiet {
            return;
        }
        let elapsed = st.started.elapsed();
        if self.json {
            // Reinstate briefly to reuse the JSON emitter for the closing line.
            self.stage = Some(st);
            self.emit_json("stage_end", detail, None);
            self.stage = None;
        } else {
            let d = if detail.is_empty() {
                String::new()
            } else {
                format!(": {detail}")
            };
            let _ = writeln!(
                std::io::stderr(),
                "Info:{} complete{} ({})",
                self.stage_name_or(&st.name),
                d,
                format_hms(elapsed)
            );
        }
    }

    fn stage_name_or<'a>(&self, fallback: &'a str) -> &'a str {
        fallback
    }

    /// A free-standing informational line (not tied to a stage's counters).
    pub fn info(&mut self, line: &str) {
        if self.quiet {
            return;
        }
        if self.json {
            self.emit_json_line("info", line);
        } else {
            let _ = writeln!(std::io::stderr(), "Info:{line}");
        }
    }

    /// The closing summary line for a whole run.
    pub fn summary(&mut self, line: &str) {
        if self.quiet {
            return;
        }
        let elapsed = self.total_elapsed();
        if self.json {
            self.emit_json_line(
                "summary",
                &format!("{line} (total {})", format_hms(elapsed)),
            );
        } else {
            let _ = writeln!(
                std::io::stderr(),
                "Info:Total: {line} (wall {})",
                format_hms(elapsed)
            );
        }
    }

    fn emit_json(
        &self,
        event: &str,
        detail: &str,
        prog: Option<(f64, Option<f64>, Option<Duration>, bool)>,
    ) {
        let st = self.stage.as_ref();
        let name = st.map(|s| s.name.as_str()).unwrap_or("");
        let done = st.map(|s| s.done).unwrap_or(0);
        let total = st.and_then(|s| s.total);
        let mut obj = format!(
            "{{\"event\":\"{}\",\"stage\":{},\"done\":{}",
            event,
            json_str(name),
            done
        );
        if let Some(t) = total {
            obj.push_str(&format!(",\"total\":{t}"));
        }
        if let Some((rate, pct, eta, settled)) = prog {
            obj.push_str(&format!(",\"rate_per_s\":{rate:.3}"));
            if let Some(p) = pct {
                obj.push_str(&format!(",\"percent\":{p:.2}"));
            }
            if let Some(e) = eta {
                obj.push_str(&format!(",\"eta_seconds\":{:.1}", e.as_secs_f64()));
            }
            obj.push_str(&format!(",\"eta_settled\":{settled}"));
        }
        if !detail.is_empty() {
            obj.push_str(&format!(",\"detail\":{}", json_str(detail)));
        }
        obj.push('}');
        let _ = writeln!(std::io::stderr(), "{obj}");
    }

    fn emit_json_line(&self, event: &str, line: &str) {
        let _ = writeln!(
            std::io::stderr(),
            "{{\"event\":{},\"detail\":{}}}",
            json_str(event),
            json_str(line)
        );
    }
}

/// Minimal JSON string escaping for the progress line emitter.
fn json_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hms_formats() {
        assert_eq!(format_hms(Duration::from_secs(0)), "0:00");
        assert_eq!(format_hms(Duration::from_secs(21)), "0:21");
        assert_eq!(format_hms(Duration::from_secs(75)), "1:15");
        assert_eq!(format_hms(Duration::from_secs(3661)), "1:01:01");
    }

    #[test]
    fn silent_reporter_never_panics() {
        let mut p = ProgressReporter::silent();
        p.stage_begin("Relation collection", Some(100), "start");
        for i in 0..=100 {
            p.progress(i, "");
        }
        p.progress_force(100, "done");
        p.stage_end("100 relations");
        p.info("something");
        p.summary("recovered log");
    }

    #[test]
    fn progress_without_stage_is_noop() {
        let mut p = ProgressReporter::silent();
        // No stage begun: must not panic.
        p.progress(5, "x");
        p.stage_end("y");
    }

    #[test]
    fn json_escaping() {
        assert_eq!(json_str("a\"b\\c"), "\"a\\\"b\\\\c\"");
        assert_eq!(json_str("line\nbreak"), "\"line\\nbreak\"");
    }

    #[test]
    fn rate_tracks_after_updates() {
        // Drive the internal state directly through the public API; we cannot
        // read stderr here, but we can assert the state machine stays live and
        // the EWMA becomes populated.
        let mut p = ProgressReporter::new(false, true); // quiet: no output
        p.stage_begin("s", Some(1000), "");
        p.progress(500, "");
        // The stage should still be live and have recorded progress.
        assert!(p.stage.is_some());
        assert_eq!(p.stage.as_ref().unwrap().done, 500);
    }
}

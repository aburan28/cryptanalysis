//! **ANSI color support** for the visualization layer.
//!
//! All renderers consult [`enabled()`] before emitting ANSI escape
//! codes.  The result is auto-detected on first call:
//!
//! 1. If env var `NO_COLOR` is set to anything → off (the
//!    `no-color.org` convention).
//! 2. If env var `CRYPTO_COLOR=always` → on, unconditionally.
//! 3. If env var `CRYPTO_COLOR=never` → off.
//! 4. Otherwise → on iff stdout is a TTY.
//!
//! Test runs piping output to a file naturally get plain text.
//! Interactive `crypto visual …` runs get colored output.  Markdown
//! docs / files written via `Write` always strip color via the
//! [`force_plain`] toggle.

use std::sync::atomic::{AtomicI8, Ordering};

/// Cached enabled state: -1 = uninitialized, 0 = off, 1 = on.
static STATE: AtomicI8 = AtomicI8::new(-1);

fn detect() -> bool {
    if std::env::var_os("NO_COLOR").is_some() {
        return false;
    }
    match std::env::var("CRYPTO_COLOR").as_deref() {
        Ok("always") | Ok("1") | Ok("yes") | Ok("on") => return true,
        Ok("never") | Ok("0") | Ok("no") | Ok("off") => return false,
        _ => {}
    }
    // Best-effort TTY check via `IsTerminal` (stable since 1.70).
    use std::io::IsTerminal;
    std::io::stdout().is_terminal()
}

/// Are ANSI colors enabled for this run?
pub fn enabled() -> bool {
    match STATE.load(Ordering::Relaxed) {
        1 => true,
        0 => false,
        _ => {
            let v = detect();
            STATE.store(if v { 1 } else { 0 }, Ordering::Relaxed);
            v
        }
    }
}

/// Force-set the global enabled state.  Useful for the CLI to
/// override based on a `--color` flag, and for tests that need
/// plain output regardless of TTY.
pub fn set_enabled(on: bool) {
    STATE.store(if on { 1 } else { 0 }, Ordering::Relaxed);
}

/// Force plain text for the rest of this run.
pub fn force_plain() {
    STATE.store(0, Ordering::Relaxed);
}

// ── Color constants ──────────────────────────────────────────────────

/// ANSI SGR sequences.  All `Fg*` constants reset to default fg.
pub const RESET: &str = "\x1b[0m";
pub const BOLD: &str = "\x1b[1m";
pub const DIM: &str = "\x1b[2m";

pub const FG_BLACK: &str = "\x1b[30m";
pub const FG_RED: &str = "\x1b[31m";
pub const FG_GREEN: &str = "\x1b[32m";
pub const FG_YELLOW: &str = "\x1b[33m";
pub const FG_BLUE: &str = "\x1b[34m";
pub const FG_MAGENTA: &str = "\x1b[35m";
pub const FG_CYAN: &str = "\x1b[36m";
pub const FG_WHITE: &str = "\x1b[37m";
pub const FG_BRIGHT_RED: &str = "\x1b[91m";
pub const FG_BRIGHT_GREEN: &str = "\x1b[92m";
pub const FG_BRIGHT_YELLOW: &str = "\x1b[93m";
pub const FG_BRIGHT_BLUE: &str = "\x1b[94m";
pub const FG_BRIGHT_MAGENTA: &str = "\x1b[95m";
pub const FG_BRIGHT_CYAN: &str = "\x1b[96m";

pub const BG_RED: &str = "\x1b[41m";
pub const BG_GREEN: &str = "\x1b[42m";
pub const BG_YELLOW: &str = "\x1b[43m";

// ── Wrapping helpers ─────────────────────────────────────────────────

/// Wrap `s` with `color`...RESET if colors are enabled, else passthrough.
pub fn paint(s: &str, color: &str) -> String {
    if enabled() {
        format!("{}{}{}", color, s, RESET)
    } else {
        s.to_string()
    }
}

/// Color a `char` (returns a `String` because ANSI is multi-byte).
pub fn paint_char(c: char, color: &str) -> String {
    if enabled() {
        format!("{}{}{}", color, c, RESET)
    } else {
        c.to_string()
    }
}

/// Pick a heat-map color for a 5-level shading slot:
/// 0 = grey, 1 = blue, 2 = green, 3 = yellow, 4 = red.  Used for
/// DDT / LAT / boomerang heat-maps where high values = potential
/// vulnerability.
pub fn heatmap_color(level: usize) -> &'static str {
    match level {
        0 => DIM,
        1 => FG_BLUE,
        2 => FG_GREEN,
        3 => FG_YELLOW,
        _ => FG_BRIGHT_RED,
    }
}

/// Color a signed value: positive → green, negative → red, zero →
/// dim.  Used for Walsh spectra, linear biases.
pub fn signed_color(v: i32) -> &'static str {
    if v > 0 {
        FG_BRIGHT_GREEN
    } else if v < 0 {
        FG_BRIGHT_RED
    } else {
        DIM
    }
}

/// Color for a verdict marker.  Matches the `✓ ✗ ⚠ ❌ ✅` family used
/// across the visualizers.
pub fn verdict_pass() -> &'static str {
    FG_BRIGHT_GREEN
}
pub fn verdict_fail() -> &'static str {
    FG_BRIGHT_RED
}
pub fn verdict_warn() -> &'static str {
    FG_BRIGHT_YELLOW
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paint_passes_through_when_disabled() {
        set_enabled(false);
        assert_eq!(paint("hello", FG_RED), "hello");
    }

    #[test]
    fn paint_wraps_when_enabled() {
        set_enabled(true);
        let s = paint("X", FG_RED);
        assert!(s.contains("X"));
        assert!(s.contains("\x1b[31m"));
        assert!(s.contains("\x1b[0m"));
        // Reset for other tests.
        set_enabled(false);
    }

    #[test]
    fn heatmap_color_gradient_is_distinct() {
        for i in 0..5 {
            let _c = heatmap_color(i);
        }
        // Levels 0 and 4 differ.
        assert_ne!(heatmap_color(0), heatmap_color(4));
    }

    #[test]
    fn signed_color_branches() {
        assert_ne!(signed_color(5), signed_color(-5));
        assert_ne!(signed_color(5), signed_color(0));
    }
}

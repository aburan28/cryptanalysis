//! Output and argument helpers shared by every `crax` subcommand.
//!
//! Every command produces one value that derives `serde::Serialize`. With
//! the global `--json` flag it is printed as one JSON object on stdout;
//! otherwise the command's own human-readable rendering is printed. Errors
//! go to stderr as `error: ...` (or as `{"status":"error",...}` on stdout
//! under `--json`) and turn into a non-zero exit status.

use num_bigint::BigUint;
use num_traits::Num;
use serde::Serialize;

/// Why a command failed.
#[derive(Debug)]
pub struct Failure {
    pub message: String,
    /// The command already printed its report (for instance one that says
    /// `"verified": false`); only the exit status remains to be set.
    pub reported: bool,
}

impl Failure {
    /// A failure whose report has already been printed.
    pub fn reported(message: impl Into<String>) -> Self {
        Failure {
            message: message.into(),
            reported: true,
        }
    }
}

impl From<String> for Failure {
    fn from(message: String) -> Self {
        Failure {
            message,
            reported: false,
        }
    }
}

impl From<&str> for Failure {
    fn from(message: &str) -> Self {
        message.to_string().into()
    }
}

/// The result of one subcommand: `Ok` carries nothing because the command
/// has already printed its output.
pub type CmdResult = Result<(), Failure>;

/// Output mode, fixed once by the global flags.
#[derive(Clone, Copy, Debug)]
pub struct Out {
    /// Print JSON instead of text.
    pub json: bool,
}

impl Out {
    /// Print `value` as JSON, or `text()` in human mode.
    pub fn emit<T: Serialize>(&self, value: &T, text: impl FnOnce() -> String) -> CmdResult {
        if self.json {
            let s = serde_json::to_string(value).map_err(|e| format!("serialising output: {e}"))?;
            println!("{s}");
        } else {
            let t = text();
            if t.ends_with('\n') {
                print!("{t}");
            } else {
                println!("{t}");
            }
        }
        Ok(())
    }

    /// Print JSON built from `value` in JSON mode, or the Markdown/text
    /// report `text` unchanged otherwise. For commands whose native output
    /// is already a report.
    pub fn report<T: Serialize>(&self, value: &T, text: String) -> CmdResult {
        self.emit(value, || text)
    }
}

/// Parse an unsigned integer written in decimal or with a `0x` prefix.
pub fn parse_biguint(s: &str) -> Result<BigUint, String> {
    let t = s.trim().replace('_', "");
    let parsed = if let Some(hex) = t.strip_prefix("0x").or_else(|| t.strip_prefix("0X")) {
        BigUint::from_str_radix(hex, 16)
    } else {
        BigUint::from_str_radix(&t, 10)
    };
    parsed.map_err(|_| format!("not an unsigned integer: {s:?}"))
}

/// Parse an integer that must fit in 64 bits (decimal or `0x` hex).
pub fn parse_u64(s: &str) -> Result<u64, String> {
    let v = parse_biguint(s)?;
    u64::try_from(&v).map_err(|_| format!("{s} does not fit in 64 bits"))
}

/// Parse a point written `x,y` (either coordinate decimal or `0x` hex).
pub fn parse_pair(s: &str) -> Result<(BigUint, BigUint), String> {
    let (x, y) = s
        .split_once(',')
        .ok_or_else(|| format!("expected a point as x,y: {s:?}"))?;
    Ok((parse_biguint(x)?, parse_biguint(y)?))
}

/// `ops / sqrt(n)`, the unit the library reports solver constants in.
pub fn ops_per_sqrt(ops: u64, n: f64) -> Option<f64> {
    (n > 0.0).then(|| ops as f64 / n.sqrt())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_decimal_hex_and_points() {
        assert_eq!(parse_u64("1_000_003").unwrap(), 1_000_003);
        assert_eq!(parse_u64("0xff").unwrap(), 255);
        assert!(parse_u64("18446744073709551616").is_err());
        assert!(parse_u64("12a").is_err());
        let (x, y) = parse_pair("5, 0x10").unwrap();
        assert_eq!((x, y), (BigUint::from(5u32), BigUint::from(16u32)));
        assert!(parse_pair("5").is_err());
    }

    #[test]
    fn ops_per_sqrt_is_none_for_empty_groups() {
        assert_eq!(ops_per_sqrt(10, 0.0), None);
        assert_eq!(ops_per_sqrt(10, 100.0), Some(1.0));
    }
}

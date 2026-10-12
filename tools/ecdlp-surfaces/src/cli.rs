use crate::{
    curve::{Curve, Point},
    json::Json,
    Result,
};
use std::{collections::BTreeMap, env, fs, str::FromStr};

pub struct Args {
    values: BTreeMap<String, String>,
    pub help: bool,
}

impl Args {
    pub fn parse(allowed: &[&str]) -> Result<Self> {
        Self::from_iter(env::args().skip(1), allowed)
    }

    pub fn from_iter(
        arguments: impl IntoIterator<Item = String>,
        allowed: &[&str],
    ) -> Result<Self> {
        let mut arguments = arguments.into_iter();
        let mut values = BTreeMap::new();
        let mut help = false;
        while let Some(argument) = arguments.next() {
            if argument == "--help" || argument == "-h" {
                help = true;
                continue;
            }
            let flag = argument
                .strip_prefix("--")
                .ok_or("Arguments must use --name value.")?;
            let (key, inline) = match flag.split_once('=') {
                Some((key, value)) => (key, Some(value.to_owned())),
                None => (flag, None),
            };
            if !allowed.contains(&key) {
                return Err(format!("Unknown option --{key}."));
            }
            let value = match inline {
                Some(value) if !value.is_empty() => value,
                Some(_) => return Err(format!("Missing value for --{key}.")),
                None => arguments
                    .next()
                    .filter(|v| !v.starts_with("--"))
                    .ok_or_else(|| format!("Missing value for --{key}."))?,
            };
            if values.insert(key.to_owned(), value).is_some() {
                return Err(format!("Duplicate option --{key}."));
            }
        }
        Ok(Self { values, help })
    }

    pub fn get(&self, key: &str) -> Option<&str> {
        self.values.get(key).map(String::as_str)
    }

    pub fn number<T: FromStr>(&self, key: &str, default: T) -> Result<T> {
        match self.get(key) {
            Some(value) => value
                .parse()
                .map_err(|_| format!("Invalid integer for --{key}.")),
            None => Ok(default),
        }
    }

    pub fn optional_number<T: FromStr>(&self, key: &str) -> Result<Option<T>> {
        self.get(key)
            .map(|value| {
                value
                    .parse()
                    .map_err(|_| format!("Invalid integer for --{key}."))
            })
            .transpose()
    }

    pub fn curve(&self) -> Result<Curve> {
        Curve::new(
            self.number("prime", 101_u64)?,
            self.number("a", 1_i128)?,
            self.number("b", 46_i128)?,
        )
    }

    pub fn emit(&self, json: &Json) -> Result<()> {
        let encoded = json.pretty() + "\n";
        if let Some(path) = self.get("output") {
            fs::write(path, encoded).map_err(|error| format!("Could not write output: {error}"))?;
            println!("Wrote {path}");
        } else {
            print!("{encoded}");
        }
        Ok(())
    }
}

pub fn parse_point(curve: &Curve, value: &str) -> Result<Point> {
    if matches!(
        value.to_ascii_lowercase().as_str(),
        "o" | "inf" | "infinity" | "origin"
    ) {
        return Ok(Point::Infinity);
    }
    let (x, y) = value.split_once(',').ok_or("Points must be x,y or O.")?;
    curve.point(
        x.trim()
            .parse()
            .map_err(|_| "Invalid point x coordinate.")?,
        y.trim()
            .parse()
            .map_err(|_| "Invalid point y coordinate.")?,
    )
}

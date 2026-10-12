use crate::curve::{Point, ProjectivePoint};
use std::fmt::Write;

#[derive(Clone, Debug)]
pub enum Json {
    Null,
    Bool(bool),
    Number(i128),
    String(String),
    Array(Vec<Json>),
    Object(Vec<(String, Json)>),
}

pub fn number<T: Into<i128>>(n: T) -> Json {
    Json::Number(n.into())
}
pub fn text(s: impl Into<String>) -> Json {
    Json::String(s.into())
}
pub fn boolean(b: bool) -> Json {
    Json::Bool(b)
}
pub fn object<const N: usize>(pairs: [(&str, Json); N]) -> Json {
    Json::Object(
        pairs
            .into_iter()
            .map(|(key, value)| (key.to_owned(), value))
            .collect(),
    )
}
pub fn point(point: Point) -> Json {
    match point {
        Point::Infinity => Json::Null,
        Point::Affine(x, y) => Json::Array(vec![number(x), number(y)]),
    }
}
pub fn projective(point: ProjectivePoint) -> Json {
    Json::Array(point.into_iter().map(number).collect())
}

fn quoted(s: &str) -> String {
    let mut value = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => value.push_str("\\\""),
            '\\' => value.push_str("\\\\"),
            '\n' => value.push_str("\\n"),
            '\r' => value.push_str("\\r"),
            '\t' => value.push_str("\\t"),
            c if c <= '\u{1f}' => {
                write!(value, "\\u{:04x}", c as u32).unwrap();
            }
            c => value.push(c),
        }
    }
    value.push('"');
    value
}

impl Json {
    pub fn pretty(&self) -> String {
        self.render(0)
    }

    fn render(&self, depth: usize) -> String {
        match self {
            Self::Null => "null".into(),
            Self::Bool(b) => b.to_string(),
            Self::Number(n) => n.to_string(),
            Self::String(s) => quoted(s),
            Self::Array(items) => {
                if items.is_empty() {
                    return "[]".into();
                }
                let inner = items
                    .iter()
                    .map(|item| format!("{}{}", "  ".repeat(depth + 1), item.render(depth + 1)))
                    .collect::<Vec<_>>()
                    .join(",\n");
                format!("[\n{inner}\n{}]", "  ".repeat(depth))
            }
            Self::Object(items) => {
                if items.is_empty() {
                    return "{}".into();
                }
                let inner = items
                    .iter()
                    .map(|(key, item)| {
                        format!(
                            "{}{}: {}",
                            "  ".repeat(depth + 1),
                            quoted(key),
                            item.render(depth + 1)
                        )
                    })
                    .collect::<Vec<_>>()
                    .join(",\n");
                format!("{{\n{inner}\n{}}}", "  ".repeat(depth))
            }
        }
    }
}

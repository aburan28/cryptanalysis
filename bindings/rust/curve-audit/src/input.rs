use num_bigint::BigUint;
use num_traits::{One, Zero};
use serde_json::{Map, Value};

pub struct AuditInput {
    pub name: Option<String>,
    pub p: BigUint,
    pub degree: u32,
    pub modulus: Option<String>,
    pub model: String,
    pub a: BigUint,
    pub b: BigUint,
    pub r: Option<BigUint>,
    pub generator: Option<(BigUint, BigUint)>,
    pub curve_order: Option<BigUint>,
    pub atlas_id: Option<String>,
    pub protocol_present: bool,
}

fn object<'a>(value: &'a Value, where_: &str) -> Result<&'a Map<String, Value>, String> {
    value
        .as_object()
        .ok_or_else(|| format!("{where_} must be an object"))
}

fn only_keys(map: &Map<String, Value>, allowed: &[&str], where_: &str) -> Result<(), String> {
    for key in map.keys() {
        if !allowed.contains(&key.as_str()) {
            return Err(format!("unknown {where_} key: {key}"));
        }
    }
    Ok(())
}

fn string<'a>(map: &'a Map<String, Value>, key: &str, where_: &str) -> Result<&'a str, String> {
    map.get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("{where_}.{key} must be a string"))
}

fn parse_unsigned(text: &str, where_: &str) -> Result<BigUint, String> {
    let text = text.trim();
    let (digits, base) = if let Some(hex) = text.strip_prefix("0x") {
        (hex, 16)
    } else {
        (text, 10)
    };
    if digits.is_empty()
        || !digits.bytes().all(|c| {
            if base == 16 {
                c.is_ascii_hexdigit()
            } else {
                c.is_ascii_digit()
            }
        })
    {
        return Err(format!(
            "{where_} must be a nonnegative decimal or 0x integer"
        ));
    }
    let number = BigUint::parse_bytes(digits.as_bytes(), base)
        .ok_or_else(|| format!("invalid integer at {where_}"))?;
    if number.bits() > 1024 {
        return Err(format!("{where_} exceeds the 1024-bit audit limit"));
    }
    Ok(number)
}

fn parse_element(text: &str, p: &BigUint, where_: &str) -> Result<BigUint, String> {
    if let Some(rest) = text.trim().strip_prefix('-') {
        let magnitude = parse_unsigned(rest, where_)? % p;
        if magnitude.is_zero() {
            Ok(BigUint::zero())
        } else {
            Ok(p - magnitude)
        }
    } else {
        Ok(parse_unsigned(text, where_)? % p)
    }
}

pub fn parse(bytes: &[u8]) -> Result<AuditInput, String> {
    if bytes.len() > 1_000_000 {
        return Err("input exceeds 1 MiB".into());
    }
    let value: Value = serde_json::from_slice(bytes).map_err(|e| format!("invalid JSON: {e}"))?;
    let top = object(&value, "input")?;
    only_keys(
        top,
        &[
            "schema",
            "name",
            "field",
            "curve",
            "subgroup",
            "curve_order",
            "atlas_id",
            "protocol",
        ],
        "input",
    )?;
    if string(top, "schema", "input")? != "ca.curve_input.v1" {
        return Err("schema must be ca.curve_input.v1".into());
    }
    let field = object(top.get("field").ok_or("missing field")?, "field")?;
    only_keys(
        field,
        &["characteristic", "degree", "modulus", "element_encoding"],
        "field",
    )?;
    let p = parse_unsigned(
        string(field, "characteristic", "field")?,
        "field.characteristic",
    )?;
    if p < BigUint::from(2u32) {
        return Err("field.characteristic must be at least two".into());
    }
    let degree = field
        .get("degree")
        .and_then(Value::as_u64)
        .ok_or("field.degree must be an integer")?;
    if !(1..=256).contains(&degree) {
        return Err("field.degree must be from 1 to 256".into());
    }
    let modulus = field
        .get("modulus")
        .map(|v| v.as_str().ok_or("field.modulus must be a string"))
        .transpose()?
        .map(str::to_owned);
    if degree == 1 && (modulus.is_some() || field.contains_key("element_encoding")) {
        return Err("prime fields must omit field.modulus and field.element_encoding".into());
    }
    if degree > 1 && modulus.is_none() {
        return Err("extension field requires field.modulus".into());
    }
    if degree > 1
        && field
            .get("element_encoding")
            .and_then(Value::as_str)
            .is_none()
    {
        return Err("extension field requires field.element_encoding".into());
    }

    let curve = object(top.get("curve").ok_or("missing curve")?, "curve")?;
    only_keys(curve, &["model", "a", "b"], "curve")?;
    let model = string(curve, "model", "curve")?.to_owned();
    let a = if degree == 1 {
        parse_element(string(curve, "a", "curve")?, &p, "curve.a")?
    } else {
        parse_unsigned(string(curve, "a", "curve")?, "curve.a")?
    };
    let b = if degree == 1 {
        parse_element(string(curve, "b", "curve")?, &p, "curve.b")?
    } else {
        parse_unsigned(string(curve, "b", "curve")?, "curve.b")?
    };

    let mut r = None;
    let mut generator = None;
    if let Some(subgroup_value) = top.get("subgroup") {
        let subgroup = object(subgroup_value, "subgroup")?;
        only_keys(subgroup, &["order", "generator"], "subgroup")?;
        let order = parse_unsigned(string(subgroup, "order", "subgroup")?, "subgroup.order")?;
        if order <= BigUint::one() {
            return Err("subgroup.order must exceed one".into());
        }
        r = Some(order);
        if let Some(gen_value) = subgroup.get("generator") {
            let gen = object(gen_value, "generator")?;
            only_keys(gen, &["x", "y"], "subgroup.generator")?;
            let x = parse_unsigned(
                string(gen, "x", "subgroup.generator")?,
                "subgroup.generator.x",
            )?;
            let y = parse_unsigned(
                string(gen, "y", "subgroup.generator")?,
                "subgroup.generator.y",
            )?;
            if degree == 1 && (x >= p || y >= p) {
                return Err("generator coordinates must be canonical residues below p".into());
            }
            generator = Some((x, y));
        }
    }
    let curve_order = match top.get("curve_order") {
        Some(value) => Some(parse_unsigned(
            value.as_str().ok_or("curve_order must be a string")?,
            "curve_order",
        )?),
        None => None,
    };
    if curve_order.as_ref().is_some_and(|n| n.is_zero()) {
        return Err("curve_order must be positive".into());
    }
    let name = top
        .get("name")
        .map(|v| v.as_str().ok_or("name must be a string"))
        .transpose()?
        .map(str::to_owned);
    let atlas_id = top
        .get("atlas_id")
        .map(|v| v.as_str().ok_or("atlas_id must be a string"))
        .transpose()?
        .map(str::to_owned);
    let protocol_present = top.get("protocol").map(|v| v.is_object()).unwrap_or(false);
    if top.contains_key("protocol") && !protocol_present {
        return Err("protocol must be an object".into());
    }
    Ok(AuditInput {
        name,
        p,
        degree: degree as u32,
        modulus,
        model,
        a,
        b,
        r,
        generator,
        curve_order,
        atlas_id,
        protocol_present,
    })
}

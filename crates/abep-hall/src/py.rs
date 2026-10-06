//! Python semantics the reference modules depend on: json load / dumps, repr / str, `in`, iteration, set and sorted
//! of strings, os.path helpers, OSError texts and numpy's float-array conversion. Values are
//! `abep_provenance::verifier::PyValue` (JSON objects keep file order; a duplicate key keeps its first position and
//! its last value, as `json.load`).

use crate::error::{HallError, HallResult, Kind, NumpySub};
pub use abep_provenance::verifier::PyValue;
use std::path::Path;

// ------------------------------------------------------------------------------------------------ reading files

/// Python's OSError text: `[Errno N] <strerror>: '<path>'`.
pub fn os_error(e: &std::io::Error, path: &str) -> HallError {
    let text = e.to_string();
    let strerror = match text.rfind(" (os error ") {
        Some(i) => text[..i].to_string(),
        None => text.clone(),
    };
    let message = match e.raw_os_error() {
        Some(n) => format!("[Errno {n}] {strerror}: {}", repr_str(path)),
        None => format!("{strerror}: {}", repr_str(path)),
    };
    let kind = if e.kind() == std::io::ErrorKind::NotFound { Kind::FileNotFound } else { Kind::Os };
    HallError::new(kind, "IO", message)
}

pub fn read_file(path: &str) -> HallResult<Vec<u8>> {
    std::fs::read(path).map_err(|e| os_error(&e, path))
}

/// `json.loads(bytes)` (UTF-8 text, RFC 8259; contract DIV-01 for the non-standard extensions Python accepts).
pub fn load_json_bytes(bytes: &[u8]) -> HallResult<PyValue> {
    let text = std::str::from_utf8(bytes).map_err(|e| HallError::decode(e.to_string()))?;
    serde_json::from_str::<PyValue>(text).map_err(|e| HallError::decode(e.to_string()))
}

/// `json.load(open(path))`.
pub fn load_json_file(path: &str) -> HallResult<PyValue> {
    load_json_bytes(&read_file(path)?)
}

/// `open(path).read()` in text mode: UTF-8 with universal newlines.
pub fn read_text(path: &str) -> HallResult<String> {
    let bytes = read_file(path)?;
    let text = String::from_utf8(bytes).map_err(|e| HallError::decode(e.to_string()))?;
    Ok(text.replace("\r\n", "\n").replace('\r', "\n"))
}

// ------------------------------------------------------------------------------------------------ formatting

/// Python `repr(float)` (and numpy float64 `str`): shortest round-trip digits; positional for decimal exponents
/// -4 <= e < 16, else `d.ddde+XX`.
pub fn float_repr(f: f64) -> String {
    if f.is_nan() {
        return "nan".into();
    }
    if f.is_infinite() {
        return if f > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let sign = if f.is_sign_negative() { "-" } else { "" };
    if f == 0.0 {
        return format!("{sign}0.0");
    }
    let sci = format!("{:e}", f.abs());
    let (mant, exp) = sci.split_once('e').unwrap_or((sci.as_str(), "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let n = digits.len() as i32;
    let body = if (-4..16).contains(&exp) {
        if exp >= 0 {
            let int_len = exp + 1;
            if n <= int_len {
                format!("{}{}.0", digits, "0".repeat((int_len - n) as usize))
            } else {
                format!("{}.{}", &digits[..int_len as usize], &digits[int_len as usize..])
            }
        } else {
            format!("0.{}{}", "0".repeat((-exp - 1) as usize), digits)
        }
    } else {
        let m = if n > 1 { format!("{}.{}", &digits[..1], &digits[1..]) } else { digits.clone() };
        format!("{m}e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs())
    };
    format!("{sign}{body}")
}

fn non_printable(c: char) -> bool {
    let u = c as u32;
    (0x80..=0xa0).contains(&u)
        || u == 0xad
        || u == 0x1680
        || (0x2000..=0x200f).contains(&u)
        || (0x2028..=0x202f).contains(&u)
        || (0x205f..=0x206f).contains(&u)
        || u == 0x3000
        || u == 0xfeff
        || (0xd800..=0xdfff).contains(&u)
        || (0xe000..=0xf8ff).contains(&u)
}

/// Python `repr(str)`.
pub fn repr_str(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') { '"' } else { '\'' };
    let mut out = String::with_capacity(s.len() + 2);
    out.push(quote);
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\t' => out.push_str("\\t"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if (c as u32) < 0x20 || c as u32 == 0x7f => out.push_str(&format!("\\x{:02x}", c as u32)),
            c if c.is_ascii() => out.push(c),
            c if non_printable(c) => {
                let u = c as u32;
                if u < 0x100 {
                    out.push_str(&format!("\\x{u:02x}"));
                } else if u < 0x10000 {
                    out.push_str(&format!("\\u{u:04x}"));
                } else {
                    out.push_str(&format!("\\U{u:08x}"));
                }
            }
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// Python `repr(value)`.
pub fn repr(v: &PyValue) -> String {
    match v {
        PyValue::None => "None".into(),
        PyValue::Bool(true) => "True".into(),
        PyValue::Bool(false) => "False".into(),
        PyValue::Int(i) => i.to_string(),
        PyValue::Float(f) => float_repr(*f),
        PyValue::Str(s) => repr_str(s),
        PyValue::DateTime(s) => s.clone(),
        PyValue::List(items) => format!("[{}]", items.iter().map(repr).collect::<Vec<_>>().join(", ")),
        PyValue::Dict(entries) => format!(
            "{{{}}}",
            entries.iter().map(|(k, v)| format!("{}: {}", repr(k), repr(v))).collect::<Vec<_>>().join(", ")
        ),
    }
}

/// Python `str(value)` (f-string `{value}`).
pub fn py_str(v: &PyValue) -> String {
    match v {
        PyValue::Str(s) => s.clone(),
        other => repr(other),
    }
}

/// `repr(list_of_str)`.
pub fn repr_strs<S: AsRef<str>>(items: &[S]) -> String {
    format!("[{}]", items.iter().map(|s| repr_str(s.as_ref())).collect::<Vec<_>>().join(", "))
}

/// `repr(tuple_of_str)` (at least two items).
pub fn repr_tuple(items: &[&str]) -> String {
    format!("({})", items.iter().map(|s| repr_str(s)).collect::<Vec<_>>().join(", "))
}

/// `json.dumps` options.
#[derive(Debug, Clone, Copy)]
pub struct Dump {
    pub indent: Option<usize>,
    pub sort_keys: bool,
    pub ensure_ascii: bool,
    pub item_sep: &'static str,
    pub key_sep: &'static str,
}

impl Dump {
    /// `json.dumps(v)`.
    pub const DEFAULT: Dump =
        Dump { indent: None, sort_keys: false, ensure_ascii: true, item_sep: ", ", key_sep: ": " };
    /// `json.dumps(v, indent=n)` (item separator ',' when indented).
    pub const fn indented(n: usize) -> Dump {
        Dump { indent: Some(n), sort_keys: false, ensure_ascii: true, item_sep: ",", key_sep: ": " }
    }
}

fn encode_str(s: &str, ensure_ascii: bool, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c if ensure_ascii && (c as u32) > 0x7e => {
                let u = c as u32;
                if u < 0x10000 {
                    out.push_str(&format!("\\u{u:04x}"));
                } else {
                    let v = u - 0x10000;
                    out.push_str(&format!("\\u{:04x}\\u{:04x}", 0xd800 + (v >> 10), 0xdc00 + (v & 0x3ff)));
                }
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

fn key_text(k: &PyValue) -> String {
    match k {
        PyValue::Str(s) => s.clone(),
        PyValue::Bool(true) => "true".into(),
        PyValue::Bool(false) => "false".into(),
        PyValue::None => "null".into(),
        PyValue::Float(f) => float_repr(*f),
        other => py_str(other),
    }
}

fn encode(v: &PyValue, o: &Dump, level: usize, out: &mut String) {
    let newline = |out: &mut String, level: usize| {
        if let Some(n) = o.indent {
            out.push('\n');
            out.push_str(&" ".repeat(n * level));
        }
    };
    match v {
        PyValue::None => out.push_str("null"),
        PyValue::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        PyValue::Int(i) => out.push_str(&i.to_string()),
        PyValue::Float(f) if f.is_nan() => out.push_str("NaN"),
        PyValue::Float(f) if f.is_infinite() => out.push_str(if *f > 0.0 { "Infinity" } else { "-Infinity" }),
        PyValue::Float(f) => out.push_str(&float_repr(*f)),
        PyValue::Str(s) | PyValue::DateTime(s) => encode_str(s, o.ensure_ascii, out),
        PyValue::List(items) if items.is_empty() => out.push_str("[]"),
        PyValue::List(items) => {
            out.push('[');
            for (i, x) in items.iter().enumerate() {
                if i > 0 {
                    out.push_str(o.item_sep);
                }
                newline(out, level + 1);
                encode(x, o, level + 1, out);
            }
            newline(out, level);
            out.push(']');
        }
        PyValue::Dict(entries) if entries.is_empty() => out.push_str("{}"),
        PyValue::Dict(entries) => {
            let mut items: Vec<(String, &PyValue)> = entries.iter().map(|(k, v)| (key_text(k), v)).collect();
            if o.sort_keys {
                items.sort_by(|a, b| a.0.cmp(&b.0));
            }
            out.push('{');
            for (i, (k, x)) in items.iter().enumerate() {
                if i > 0 {
                    out.push_str(o.item_sep);
                }
                newline(out, level + 1);
                encode_str(k, o.ensure_ascii, out);
                out.push_str(o.key_sep);
                encode(x, o, level + 1, out);
            }
            newline(out, level);
            out.push('}');
        }
    }
}

/// `json.dumps(v, ...)` with the given options.
pub fn dumps(v: &PyValue, o: &Dump) -> String {
    let mut out = String::new();
    encode(v, o, 0, &mut out);
    out
}

// ------------------------------------------------------------------------------------------------ values

pub fn s(text: impl Into<String>) -> PyValue {
    PyValue::Str(text.into())
}

/// Build a dict from string keys (insertion order).
pub fn dict<I: IntoIterator<Item = (&'static str, PyValue)>>(items: I) -> PyValue {
    PyValue::Dict(items.into_iter().map(|(k, v)| (s(k), v)).collect())
}

pub fn list_of_strs<S: AsRef<str>>(items: &[S]) -> PyValue {
    PyValue::List(items.iter().map(|x| s(x.as_ref())).collect())
}

pub fn as_str(v: &PyValue) -> Option<&str> {
    match v {
        PyValue::Str(s) => Some(s),
        _ => None,
    }
}

pub fn is_dict(v: &PyValue) -> bool {
    matches!(v, PyValue::Dict(_))
}

/// `d.get(key)`; a non-dict raises AttributeError (TYPE_ERROR).
pub fn get<'a>(v: &'a PyValue, key: &str) -> HallResult<Option<&'a PyValue>> {
    match v {
        PyValue::Dict(entries) => Ok(entries.iter().find(|(k, _)| as_str(k) == Some(key)).map(|(_, x)| x)),
        other => Err(HallError::type_error(format!("'{}' object has no attribute 'get'", other.type_name()))),
    }
}

/// `d[key]` with a string key.
pub fn getitem<'a>(v: &'a PyValue, key: &str) -> HallResult<&'a PyValue> {
    match v {
        PyValue::Dict(_) => get(v, key)?.ok_or_else(|| HallError::new(Kind::Key, "KEY", repr_str(key))),
        PyValue::List(_) => Err(HallError::type_error("list indices must be integers or slices, not str")),
        PyValue::Str(_) => Err(HallError::type_error("string indices must be integers, not 'str'")),
        other => Err(HallError::type_error(format!("'{}' object is not subscriptable", other.type_name()))),
    }
}

/// Set or replace `d[key]` (an existing key keeps its position, a new one is appended).
pub fn set_item(d: &mut PyValue, key: &str, value: PyValue) {
    if let PyValue::Dict(entries) = d {
        match entries.iter_mut().find(|(k, _)| as_str(k) == Some(key)) {
            Some(slot) => slot.1 = value,
            None => entries.push((s(key), value)),
        }
    }
}

pub fn require_hashable(v: &PyValue) -> HallResult<()> {
    if v.hashable() {
        Ok(())
    } else {
        Err(HallError::type_error(format!("unhashable type: '{}'", v.type_name())))
    }
}

/// Python `item in container`.
pub fn contains(container: &PyValue, item: &PyValue) -> HallResult<bool> {
    match container {
        PyValue::Dict(entries) => {
            require_hashable(item)?;
            Ok(entries.iter().any(|(k, _)| k.py_eq(item)))
        }
        PyValue::List(items) => Ok(items.iter().any(|x| x.py_eq(item))),
        PyValue::Str(hay) => match item {
            PyValue::Str(needle) => Ok(hay.contains(needle.as_str())),
            other => Err(HallError::type_error(format!(
                "'in <string>' requires string as left operand, not {}",
                other.type_name()
            ))),
        },
        other => Err(HallError::type_error(format!("argument of type '{}' is not iterable", other.type_name()))),
    }
}

/// `list(v)` / iteration: dict keys, list items, string characters.
pub fn iterate(v: &PyValue) -> HallResult<Vec<PyValue>> {
    match v {
        PyValue::Dict(entries) => Ok(entries.iter().map(|(k, _)| k.clone()).collect()),
        PyValue::List(items) => Ok(items.clone()),
        PyValue::Str(text) => Ok(text.chars().map(|c| s(c.to_string())).collect()),
        other => Err(HallError::type_error(format!("'{}' object is not iterable", other.type_name()))),
    }
}

/// `set(items)` (hashable elements, Python equality; first occurrence kept).
pub fn set_from(items: Vec<PyValue>) -> HallResult<Vec<PyValue>> {
    let mut out: Vec<PyValue> = Vec::new();
    for x in items {
        require_hashable(&x)?;
        if !out.iter().any(|y| y.py_eq(&x)) {
            out.push(x);
        }
    }
    Ok(out)
}

/// `a & b` of two sets (order of `a`).
pub fn intersection(a: &[PyValue], b: &[PyValue]) -> Vec<PyValue> {
    a.iter().filter(|x| b.iter().any(|y| y.py_eq(x))).cloned().collect()
}

/// `sorted(items)` for strings or numbers (mixed types: TypeError).
pub fn sorted(mut items: Vec<PyValue>) -> HallResult<Vec<PyValue>> {
    if items.iter().all(|x| matches!(x, PyValue::Str(_))) {
        items.sort_by(|a, b| as_str(a).cmp(&as_str(b)));
        return Ok(items);
    }
    let num = |x: &PyValue| match x {
        PyValue::Bool(b) => Some(f64::from(u8::from(*b))),
        PyValue::Int(i) => Some(*i as f64),
        PyValue::Float(f) => Some(*f),
        _ => None,
    };
    if items.iter().all(|x| num(x).is_some()) {
        items.sort_by(|a, b| num(a).partial_cmp(&num(b)).unwrap_or(std::cmp::Ordering::Equal));
        return Ok(items);
    }
    Err(HallError::type_error("'<' not supported between instances of different types"))
}

/// Python `str.isspace` for one character.
pub fn is_py_space(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

/// Python `str.strip()`.
pub fn py_strip(text: &str) -> &str {
    text.trim_matches(is_py_space)
}

// ------------------------------------------------------------------------------------------------ os.path (posix)

pub fn isabs(p: &str) -> bool {
    p.starts_with('/')
}

/// `os.path.join(a, b)`.
pub fn join(a: &str, b: &str) -> String {
    if b.starts_with('/') {
        b.to_string()
    } else if a.is_empty() || a.ends_with('/') {
        format!("{a}{b}")
    } else {
        format!("{a}/{b}")
    }
}

/// `posixpath.normpath`.
pub fn normpath(path: &str) -> String {
    if path.is_empty() {
        return ".".into();
    }
    let initial =
        if path.starts_with("//") && !path.starts_with("///") { 2 } else { usize::from(path.starts_with('/')) };
    let mut comps: Vec<&str> = Vec::new();
    for comp in path.split('/') {
        if comp.is_empty() || comp == "." {
            continue;
        }
        if comp != ".." || (initial == 0 && comps.is_empty()) || comps.last() == Some(&"..") {
            comps.push(comp);
        } else if !comps.is_empty() {
            comps.pop();
        }
    }
    let joined = format!("{}{}", "/".repeat(initial), comps.join("/"));
    if joined.is_empty() {
        ".".into()
    } else {
        joined
    }
}

/// `os.path.abspath`.
pub fn abspath(p: &str) -> String {
    if isabs(p) {
        normpath(p)
    } else {
        let cwd = std::env::current_dir().map(|c| c.to_string_lossy().into_owned()).unwrap_or_default();
        normpath(&join(&cwd, p))
    }
}

/// `os.path.dirname`.
pub fn dirname(p: &str) -> String {
    let i = p.rfind('/').map_or(0, |i| i + 1);
    let head = &p[..i];
    if !head.is_empty() && head.chars().any(|c| c != '/') {
        head.trim_end_matches('/').to_string()
    } else {
        head.to_string()
    }
}

pub fn isfile(p: &str) -> bool {
    !p.is_empty() && std::fs::metadata(p).map(|m| m.is_file()).unwrap_or(false)
}

pub fn isdir(p: &str) -> bool {
    !p.is_empty() && std::fs::metadata(p).map(|m| m.is_dir()).unwrap_or(false)
}

pub fn path_str(p: &Path) -> String {
    p.to_string_lossy().into_owned()
}

// ------------------------------------------------------------------------------------------------ numpy

/// `np.asarray(v, float)`: shape and C-order data.
#[derive(Debug, Clone, PartialEq)]
pub struct NdArray {
    pub shape: Vec<usize>,
    pub data: Vec<f64>,
}

fn discover(v: &PyValue) -> Option<Vec<usize>> {
    match v {
        PyValue::List(items) => {
            let Some(first) = items.first() else { return Some(vec![0]) };
            let inner = discover(first)?;
            for x in &items[1..] {
                if discover(x)? != inner {
                    return None;
                }
            }
            let mut shape = vec![items.len()];
            shape.extend(inner);
            Some(shape)
        }
        _ => Some(Vec::new()),
    }
}

fn convert(v: &PyValue, out: &mut Vec<f64>) -> HallResult<()> {
    match v {
        PyValue::List(items) => items.iter().try_for_each(|x| convert(x, out)),
        PyValue::Int(i) => {
            out.push(*i as f64);
            Ok(())
        }
        PyValue::Float(f) => {
            out.push(*f);
            Ok(())
        }
        PyValue::Bool(b) => {
            out.push(f64::from(u8::from(*b)));
            Ok(())
        }
        PyValue::None => {
            out.push(f64::NAN);
            Ok(())
        }
        PyValue::Str(text) => {
            Err(HallError::numpy(NumpySub::Convert, format!("could not convert string to float: {}", repr_str(text))))
        }
        other => Err(HallError::type_error(format!(
            "float() argument must be a string or a real number, not '{}'",
            other.type_name()
        ))),
    }
}

/// `np.asarray(v, dtype=float)`.
pub fn ndarray(v: &PyValue) -> HallResult<NdArray> {
    let shape = discover(v).ok_or_else(|| {
        HallError::numpy(
            NumpySub::Ragged,
            "setting an array element with a sequence. The requested array has an inhomogeneous shape",
        )
    })?;
    let mut data = Vec::new();
    convert(v, &mut data)?;
    Ok(NdArray { shape, data })
}

/// numpy's shape text in error messages: `(2,2)`, `(1,)`, `()`.
pub fn shape_text(shape: &[usize]) -> String {
    match shape.len() {
        0 => "()".into(),
        1 => format!("({},)", shape[0]),
        _ => format!("({})", shape.iter().map(usize::to_string).collect::<Vec<_>>().join(",")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn j(t: &str) -> PyValue {
        load_json_bytes(t.as_bytes()).unwrap()
    }

    #[test]
    fn dumps_matches_python_defaults_and_options() {
        let v = j(r#"{"b": [1, 2.0, true, null], "a": {"x": "é\n\"", "y": []}, "c": {}}"#);
        assert_eq!(
            dumps(&v, &Dump::DEFAULT),
            concat!(r#"{"b": [1, 2.0, true, null], "a": {"x": ""#, "\\u00e9", r#"\n\"", "y": []}, "c": {}}"#)
        );
        let sorted = Dump { sort_keys: true, ensure_ascii: false, ..Dump::indented(1) };
        assert_eq!(
            dumps(&v, &sorted),
            "{\n \"a\": {\n  \"x\": \"é\\n\\\"\",\n  \"y\": []\n },\n \"b\": [\n  1,\n  2.0,\n  true,\n  null\n ],\n \"c\": {}\n}"
        );
        let compact = Dump { sort_keys: true, item_sep: ",", key_sep: ":", ..Dump::DEFAULT };
        assert_eq!(
            dumps(&j(r#"{"u": "😀", "f": 1e-7}"#), &compact),
            concat!(r#"{"f":1e-07,"u":""#, "\\ud83d\\ude00", r#""}"#)
        );
    }

    #[test]
    fn repr_and_floats_are_python() {
        assert_eq!(repr_str("a'b"), "\"a'b\"");
        assert_eq!(repr_str("a\"b"), "'a\"b'");
        assert_eq!(repr_str("a'b\"c"), "'a\\'b\"c'");
        assert_eq!(repr_str("x\u{1}\u{7f}\u{80}é"), "'x\\x01\\x7f\\x80é'");
        for (f, t) in [(250.0, "250.0"), (1e16, "1e+16"), (1e-5, "1e-05"), (0.1, "0.1"), (-0.0, "-0.0")] {
            assert_eq!(float_repr(f), t);
        }
        assert_eq!(repr(&j(r#"{"k": [1, null, true, "s"]}"#)), "{'k': [1, None, True, 's']}");
    }

    #[test]
    fn paths_follow_posixpath() {
        assert_eq!(normpath("design/./x.json"), "design/x.json");
        assert_eq!(normpath("../outside.json"), "../outside.json");
        assert_eq!(normpath("a/b/../../.."), "..");
        assert_eq!(normpath("//a//b/"), "//a/b");
        assert_eq!(normpath(""), ".");
        assert_eq!(join("/r", "x"), "/r/x");
        assert_eq!(join("/r/", "/abs"), "/abs");
        assert_eq!(dirname("/a/b/c.json"), "/a/b");
        assert_eq!(dirname("/c.json"), "/");
    }

    #[test]
    fn numpy_conversion_and_python_operators() {
        assert_eq!(ndarray(&j("[[1, 2.5], [true, null]]")).unwrap().shape, vec![2, 2]);
        assert!(ndarray(&j("[[1, 2.5], [true, null]]")).unwrap().data[3].is_nan());
        assert_eq!(ndarray(&j("[[1], [2, 3]]")).unwrap_err().kind, Kind::Numpy(NumpySub::Ragged));
        assert_eq!(ndarray(&j("[1, \"x\"]")).unwrap_err().kind, Kind::Numpy(NumpySub::Convert));
        assert_eq!(ndarray(&j("[1, {}]")).unwrap_err().kind, Kind::Type);
        assert_eq!(ndarray(&j("[[], []]")).unwrap().shape, vec![2, 0]);
        assert_eq!(shape_text(&[2, 2]), "(2,2)");
        assert!(contains(&j(r#"["a"]"#), &s("a")).unwrap());
        assert!(contains(&j(r#""xabcx""#), &s("abc")).unwrap());
        assert_eq!(contains(&j("5"), &s("a")).unwrap_err().kind, Kind::Type);
        assert_eq!(getitem(&j("{}"), "meta").unwrap_err().message, "'meta'");
        assert_eq!(set_from(vec![PyValue::Int(1), PyValue::Float(1.0), PyValue::Bool(true)]).unwrap().len(), 1);
    }
}

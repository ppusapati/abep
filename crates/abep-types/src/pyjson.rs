//! Python-compatible JSON values, parser and writer (RM-R06: byte-identical evidence where a contract says EXACT_BYTES).
//!
//! The repository's Python writers serialize with `json.dumps` (CPython 3.11). This module reproduces, byte for byte:
//!
//! * `float.__repr__` (`sys.float_repr_style == "short"`): the shortest digit string that round-trips, fixed notation
//!   for decimal exponents -4 < e <= 16 (`100.0`, `0.0001`), otherwise `1e-05` / `1.5e+16` (sign, at least two digits);
//! * `json.dumps(obj, indent, separators, sort_keys, ensure_ascii, allow_nan)`: the pure-Python `_make_iterencode`
//!   layout (indent > 0) and the C encoder layout (indent None); `NaN` / `Infinity` / `-Infinity` only when
//!   `allow_nan` is true (the default; `scripts/config/build_config.py` uses the default), otherwise `ValueError`;
//!   string escapes `\"` `\\` `\n` `\r` `\t` `\b` `\f` and `\u00xx` (lower-case hex) for other control characters,
//!   and with `ensure_ascii` every non-ASCII character as `\uxxxx` (surrogate pairs above U+FFFF);
//! * `json.loads` (strict, C scanner): insertion-ordered objects (a duplicate key keeps its first position and takes
//!   the last value), ints kept exact (no f64 rounding of large integers), floats correctly rounded, `NaN` /
//!   `Infinity` / `-Infinity` literals accepted, control characters in strings refused;
//! * `repr()` / `str()` / truthiness / `==` of JSON-shaped Python values, for refusal messages and rule logic.
//!
//! Documented divergences (fail closed, never a silent difference): a lone UTF-16 surrogate escape (`"\ud800"`), which
//! a Python `str` can hold but a Rust `String` cannot, is refused with class `ValueError`; nesting deeper than
//! [`MAX_DEPTH`] is refused with `RecursionError` (CPython's limit depends on the interpreter stack); character
//! classes follow the reference interpreter's Unicode 14.0.0 for `repr()` but Rust's own Unicode tables for case mapping.

use crate::pyjson_unicode::{NON_PRINTABLE, WORD};
use std::cmp::Ordering;
use std::fmt;

/// Nesting limit of the parser and writer (CPython raises `RecursionError` near its own interpreter limit).
pub const MAX_DEPTH: usize = 512;

/// CPython 3.11 `sys.int_info.str_digits_check_threshold` default: longer integer literals raise `ValueError`.
pub const INT_MAX_STR_DIGITS: usize = 4300;

/// A Python exception mirrored by class name and message.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PyException {
    pub class: &'static str,
    pub message: String,
}

impl PyException {
    pub fn new(class: &'static str, message: impl Into<String>) -> Self {
        PyException { class, message: message.into() }
    }
}

impl fmt::Display for PyException {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.class, self.message)
    }
}

impl std::error::Error for PyException {}

pub type PyResult<T> = Result<T, PyException>;

/// An exact Python `int` (canonical decimal digits; JSON integers are never rounded through f64).
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct PyInt {
    negative: bool,
    digits: String,
}

impl PyInt {
    pub fn from_i64(v: i64) -> Self {
        let negative = v < 0;
        PyInt { negative, digits: v.unsigned_abs().to_string() }
    }

    /// Parse an optionally signed run of ASCII digits; leading zeros are normalised away (`-0` is `0`).
    pub fn parse(text: &str) -> Option<Self> {
        let (negative, body) = match text.strip_prefix('-') {
            Some(rest) => (true, rest),
            None => (false, text),
        };
        if body.is_empty() || !body.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        let trimmed = body.trim_start_matches('0');
        let digits = if trimmed.is_empty() { "0".to_string() } else { trimmed.to_string() };
        let negative = negative && digits != "0";
        Some(PyInt { negative, digits })
    }

    pub fn is_negative(&self) -> bool {
        self.negative
    }

    pub fn is_zero(&self) -> bool {
        self.digits == "0"
    }

    pub fn as_i64(&self) -> Option<i64> {
        let s = self.to_string();
        s.parse::<i64>().ok()
    }

    /// `float(int)`: correctly rounded; `OverflowError` beyond the f64 range.
    pub fn to_f64(&self) -> PyResult<f64> {
        let v: f64 = self.digits.parse().map_err(|_| PyException::new("ValueError", "invalid int"))?;
        if v.is_infinite() {
            return Err(PyException::new("OverflowError", "int too large to convert to float"));
        }
        Ok(if self.negative { -v } else { v })
    }

    fn cmp_magnitude(a: &str, b: &str) -> Ordering {
        a.len().cmp(&b.len()).then_with(|| a.cmp(b))
    }
}

impl fmt::Display for PyInt {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.negative {
            f.write_str("-")?;
        }
        f.write_str(&self.digits)
    }
}

impl Ord for PyInt {
    fn cmp(&self, other: &Self) -> Ordering {
        match (self.negative, other.negative) {
            (false, true) => Ordering::Greater,
            (true, false) => Ordering::Less,
            (false, false) => Self::cmp_magnitude(&self.digits, &other.digits),
            (true, true) => Self::cmp_magnitude(&other.digits, &self.digits),
        }
    }
}

impl PartialOrd for PyInt {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

/// An insertion-ordered Python `dict` with string keys (the shape `json.loads` produces).
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Dict {
    entries: Vec<(String, Value)>,
}

impl Dict {
    pub const fn new() -> Self {
        Dict { entries: Vec::new() }
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn get(&self, key: &str) -> Option<&Value> {
        self.entries.iter().find(|(k, _)| k == key).map(|(_, v)| v)
    }

    pub fn get_mut(&mut self, key: &str) -> Option<&mut Value> {
        self.entries.iter_mut().find(|(k, _)| k == key).map(|(_, v)| v)
    }

    pub fn contains_key(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// `d[key] = value`: an existing key keeps its position.
    pub fn insert(&mut self, key: impl Into<String>, value: Value) {
        let key = key.into();
        match self.get_mut(&key) {
            Some(slot) => *slot = value,
            None => self.entries.push((key, value)),
        }
    }

    pub fn remove(&mut self, key: &str) -> Option<Value> {
        let i = self.entries.iter().position(|(k, _)| k == key)?;
        Some(self.entries.remove(i).1)
    }

    pub fn iter(&self) -> impl Iterator<Item = (&String, &Value)> {
        self.entries.iter().map(|(k, v)| (k, v))
    }

    pub fn keys(&self) -> impl Iterator<Item = &String> {
        self.entries.iter().map(|(k, _)| k)
    }

    pub fn values(&self) -> impl Iterator<Item = &Value> {
        self.entries.iter().map(|(_, v)| v)
    }
}

impl FromIterator<(String, Value)> for Dict {
    fn from_iter<I: IntoIterator<Item = (String, Value)>>(iter: I) -> Self {
        let mut d = Dict::new();
        for (k, v) in iter {
            d.insert(k, v);
        }
        d
    }
}

/// A JSON-shaped Python value.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    Int(PyInt),
    Float(f64),
    Str(String),
    List(Vec<Value>),
    Dict(Dict),
}

impl Value {
    pub fn int(v: i64) -> Value {
        Value::Int(PyInt::from_i64(v))
    }

    pub fn str(s: impl Into<String>) -> Value {
        Value::Str(s.into())
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::Str(s) => Some(s),
            _ => None,
        }
    }

    pub fn as_dict(&self) -> Option<&Dict> {
        match self {
            Value::Dict(d) => Some(d),
            _ => None,
        }
    }

    pub fn as_list(&self) -> Option<&[Value]> {
        match self {
            Value::List(l) => Some(l),
            _ => None,
        }
    }

    /// Python type name (for `TypeError` / `AttributeError` messages).
    pub fn type_name(&self) -> &'static str {
        match self {
            Value::Null => "NoneType",
            Value::Bool(_) => "bool",
            Value::Int(_) => "int",
            Value::Float(_) => "float",
            Value::Str(_) => "str",
            Value::List(_) => "list",
            Value::Dict(_) => "dict",
        }
    }

    /// `isinstance(v, (int, float)) and not isinstance(v, bool)`.
    pub fn is_number(&self) -> bool {
        matches!(self, Value::Int(_) | Value::Float(_))
    }

    /// `float(v)` for an int or float (callers check `is_number` first, as the Python does).
    pub fn to_f64(&self) -> PyResult<f64> {
        match self {
            Value::Int(i) => i.to_f64(),
            Value::Float(f) => Ok(*f),
            Value::Bool(b) => Ok(if *b { 1.0 } else { 0.0 }),
            other => Err(PyException::new(
                "TypeError",
                format!("float() argument must be a string or a real number, not '{}'", other.type_name()),
            )),
        }
    }

    /// Python truthiness.
    pub fn truthy(&self) -> bool {
        match self {
            Value::Null => false,
            Value::Bool(b) => *b,
            Value::Int(i) => !i.is_zero(),
            Value::Float(f) => *f != 0.0,
            Value::Str(s) => !s.is_empty(),
            Value::List(l) => !l.is_empty(),
            Value::Dict(d) => !d.is_empty(),
        }
    }
}

impl From<&str> for Value {
    fn from(s: &str) -> Self {
        Value::Str(s.to_string())
    }
}

impl From<String> for Value {
    fn from(s: String) -> Self {
        Value::Str(s)
    }
}

impl From<bool> for Value {
    fn from(b: bool) -> Self {
        Value::Bool(b)
    }
}

impl From<f64> for Value {
    fn from(f: f64) -> Self {
        Value::Float(f)
    }
}

impl From<i64> for Value {
    fn from(i: i64) -> Self {
        Value::int(i)
    }
}

impl From<Dict> for Value {
    fn from(d: Dict) -> Self {
        Value::Dict(d)
    }
}

impl From<Vec<Value>> for Value {
    fn from(l: Vec<Value>) -> Self {
        Value::List(l)
    }
}

/// Build an ordered `Dict` value: `pydict! { "a" => v1, "b" => v2 }`.
#[macro_export]
macro_rules! pydict {
    () => { $crate::pyjson::Value::Dict($crate::pyjson::Dict::new()) };
    ($($k:expr => $v:expr),+ $(,)?) => {{
        let mut d = $crate::pyjson::Dict::new();
        $( d.insert($k, $crate::pyjson::Value::from($v)); )+
        $crate::pyjson::Value::Dict(d)
    }};
}

// ============================================================================================================ floats

/// `float.__repr__` of CPython (repr style "short").
pub fn float_repr(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    if x == 0.0 {
        return if x.is_sign_negative() { "-0.0".into() } else { "0.0".into() };
    }
    let sign = if x < 0.0 { "-" } else { "" };
    let (digits, decpt) = shortest_digits(x.abs());
    let n = digits.len() as i32;
    let body = if decpt > -4 && decpt <= 16 {
        if decpt <= 0 {
            format!("0.{}{}", "0".repeat((-decpt) as usize), digits)
        } else if decpt >= n {
            format!("{}{}.0", digits, "0".repeat((decpt - n) as usize))
        } else {
            format!("{}.{}", &digits[..decpt as usize], &digits[decpt as usize..])
        }
    } else {
        let e = decpt - 1;
        let mantissa = if n > 1 { format!("{}.{}", &digits[..1], &digits[1..]) } else { digits.clone() };
        format!("{}e{}{:02}", mantissa, if e < 0 { '-' } else { '+' }, e.abs())
    };
    format!("{sign}{body}")
}

/// Exact significant digits and decimal point position (value = 0.d1d2... x 10^decpt) of a positive finite `x` whose
/// exact expansion is short enough to compute in u128; `None` otherwise (then it has more than 19 digits).
fn exact_short_digits(x: f64) -> Option<(String, i32)> {
    let bits = x.to_bits();
    let raw_exp = ((bits >> 52) & 0x7ff) as i32;
    let frac = bits & ((1u64 << 52) - 1);
    let (mut m, mut e) = if raw_exp == 0 { (frac, -1074) } else { (frac | (1u64 << 52), raw_exp - 1075) };
    let tz = m.trailing_zeros();
    m >>= tz;
    e += tz as i32;
    let (p, k) = if e >= 0 {
        if e + (64 - m.leading_zeros() as i32) > 127 {
            return None;
        }
        ((m as u128) << e, 0)
    } else {
        let k = -e;
        if k > 27 {
            return None;
        }
        ((m as u128).checked_mul(5u128.pow(k as u32))?, k)
    };
    let s = p.to_string();
    let decpt = s.len() as i32 - k;
    Some((s.trim_end_matches('0').to_string(), decpt))
}

/// Shortest round-trip digits and decimal point position (value = 0.d1d2... x 10^decpt) with CPython's
/// `_Py_dg_dtoa` mode-0 choice: among the shortest strings that read back as `x`, the one nearest to `x`, an exact
/// tie going to the even last digit. Rust's shortest formatting fixes the length but can break an exact tie upward,
/// so a tie (possible only when `x` has n + 1 exact significant digits ending in 5) is re-decided here.
fn shortest_digits(ax: f64) -> (String, i32) {
    let sci = format!("{ax:e}");
    let (mant, exp) = sci.split_once('e').expect("LowerExp always has an exponent");
    let exp: i32 = exp.parse().expect("integer exponent");
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let decpt = exp + 1;
    let n = digits.len();
    let Some((exact, exact_decpt)) = exact_short_digits(ax) else {
        return (digits, decpt);
    };
    if exact.len() != n + 1 || !exact.ends_with('5') {
        return (digits, decpt);
    }
    let down = exact[..n].to_string();
    let mut up_bytes = down.clone().into_bytes();
    let mut up_decpt = exact_decpt;
    let mut i = n;
    loop {
        if i == 0 {
            up_bytes.insert(0, b'1');
            up_bytes.pop();
            up_decpt += 1;
            break;
        }
        i -= 1;
        if up_bytes[i] == b'9' {
            up_bytes[i] = b'0';
        } else {
            up_bytes[i] += 1;
            break;
        }
    }
    let up = String::from_utf8(up_bytes).expect("ascii digits");
    let reads_back = |d: &str, dp: i32| format!("0.{d}e{dp}").parse::<f64>().is_ok_and(|y| y == ax);
    let down_ok = reads_back(&down, exact_decpt);
    let up_ok = reads_back(&up, up_decpt);
    let down_even = (down.as_bytes()[n - 1] - b'0').is_multiple_of(2);
    let (chosen, dp) = match (down_ok, up_ok) {
        (true, true) if down_even => (down, exact_decpt),
        (true, true) => (up, up_decpt),
        (true, false) => (down, exact_decpt),
        (false, true) => (up, up_decpt),
        (false, false) => return (digits, decpt),
    };
    let trimmed = chosen.trim_end_matches('0');
    (if trimmed.is_empty() { "0".to_string() } else { trimmed.to_string() }, dp)
}

/// The `json` module spelling of a float (`NaN` / `Infinity` / `-Infinity` when `allow_nan`).
pub fn json_float(x: f64, allow_nan: bool) -> PyResult<String> {
    if x.is_finite() {
        return Ok(float_repr(x));
    }
    if !allow_nan {
        return Err(PyException::new("ValueError", "Out of range float values are not JSON compliant"));
    }
    Ok(if x.is_nan() {
        "NaN".into()
    } else if x > 0.0 {
        "Infinity".into()
    } else {
        "-Infinity".into()
    })
}

// ============================================================================================================ writer

/// `json.dumps` keyword arguments.
#[derive(Debug, Clone)]
pub struct DumpOptions {
    /// `indent=None` (compact layout) or a number of spaces.
    pub indent: Option<usize>,
    /// `separators=(item, key)`; `None` = the Python default for the indent mode.
    pub separators: Option<(String, String)>,
    pub sort_keys: bool,
    pub ensure_ascii: bool,
    pub allow_nan: bool,
}

impl Default for DumpOptions {
    /// `json.dumps(obj)` defaults.
    fn default() -> Self {
        DumpOptions { indent: None, separators: None, sort_keys: false, ensure_ascii: true, allow_nan: true }
    }
}

impl DumpOptions {
    /// `json.dumps(obj, indent=1, ensure_ascii=False)` - the configuration writer (`build_config.dumps`).
    pub fn config_writer() -> Self {
        DumpOptions { indent: Some(1), ensure_ascii: false, ..Default::default() }
    }

    /// `json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` - the canonical hash form.
    pub fn canonical_hash() -> Self {
        DumpOptions {
            indent: None,
            separators: Some((",".into(), ":".into())),
            sort_keys: true,
            ensure_ascii: false,
            allow_nan: true,
        }
    }
}

/// `json.dumps(value, **opts)`.
pub fn dumps(value: &Value, opts: &DumpOptions) -> PyResult<String> {
    let (item_sep, key_sep) = match &opts.separators {
        Some((i, k)) => (i.clone(), k.clone()),
        None if opts.indent.is_some() => (",".to_string(), ": ".to_string()),
        None => (", ".to_string(), ": ".to_string()),
    };
    let mut out = String::new();
    let w = Writer { opts, item_sep: &item_sep, key_sep: &key_sep };
    w.write(value, 0, &mut out)?;
    Ok(out)
}

/// `(json.dumps(value, indent=1, ensure_ascii=False) + "\n").encode("utf-8")` - one configuration file.
pub fn dumps_config_file(value: &Value) -> PyResult<Vec<u8>> {
    let mut s = dumps(value, &DumpOptions::config_writer())?;
    s.push('\n');
    Ok(s.into_bytes())
}

struct Writer<'a> {
    opts: &'a DumpOptions,
    item_sep: &'a str,
    key_sep: &'a str,
}

impl Writer<'_> {
    fn newline(&self, level: usize, out: &mut String) {
        if let Some(n) = self.opts.indent {
            out.push('\n');
            for _ in 0..n * level {
                out.push(' ');
            }
        }
    }

    fn write(&self, v: &Value, level: usize, out: &mut String) -> PyResult<()> {
        if level > MAX_DEPTH {
            return Err(PyException::new("RecursionError", "maximum recursion depth exceeded while encoding"));
        }
        match v {
            Value::Null => out.push_str("null"),
            Value::Bool(true) => out.push_str("true"),
            Value::Bool(false) => out.push_str("false"),
            Value::Int(i) => out.push_str(&i.to_string()),
            Value::Float(f) => out.push_str(&json_float(*f, self.opts.allow_nan)?),
            Value::Str(s) => encode_string(s, self.opts.ensure_ascii, out),
            Value::List(items) => {
                if items.is_empty() {
                    out.push_str("[]");
                    return Ok(());
                }
                out.push('[');
                self.newline(level + 1, out);
                for (i, item) in items.iter().enumerate() {
                    if i > 0 {
                        out.push_str(self.item_sep);
                        self.newline(level + 1, out);
                    }
                    self.write(item, level + 1, out)?;
                }
                self.newline(level, out);
                out.push(']');
            }
            Value::Dict(d) => {
                if d.is_empty() {
                    out.push_str("{}");
                    return Ok(());
                }
                let mut entries: Vec<(&String, &Value)> = d.iter().collect();
                if self.opts.sort_keys {
                    entries.sort_by(|a, b| a.0.cmp(b.0));
                }
                out.push('{');
                self.newline(level + 1, out);
                for (i, (k, val)) in entries.into_iter().enumerate() {
                    if i > 0 {
                        out.push_str(self.item_sep);
                        self.newline(level + 1, out);
                    }
                    encode_string(k, self.opts.ensure_ascii, out);
                    out.push_str(self.key_sep);
                    self.write(val, level + 1, out)?;
                }
                self.newline(level, out);
                out.push('}');
            }
        }
        Ok(())
    }
}

fn push_u16_escape(u: u32, out: &mut String) {
    out.push_str(&format!("\\u{u:04x}"));
}

/// `json.encoder.(py_)encode_basestring(_ascii)`.
pub fn encode_string(s: &str, ensure_ascii: bool, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 => push_u16_escape(c as u32, out),
            c if ensure_ascii && !(' '..='~').contains(&c) => {
                let n = c as u32;
                if n < 0x10000 {
                    push_u16_escape(n, out);
                } else {
                    let v = n - 0x10000;
                    push_u16_escape(0xd800 | ((v >> 10) & 0x3ff), out);
                    push_u16_escape(0xdc00 | (v & 0x3ff), out);
                }
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

// ============================================================================================================ parser

/// `bytes.decode("utf-8")` followed by universal-newline translation (`Path.read_text(encoding="utf-8")`).
pub fn read_text_utf8(bytes: &[u8]) -> PyResult<String> {
    let text = std::str::from_utf8(bytes)
        .map_err(|e| PyException::new("UnicodeDecodeError", format!("'utf-8' codec can't decode bytes: {e}")))?;
    if !text.contains('\r') {
        return Ok(text.to_string());
    }
    Ok(text.replace("\r\n", "\n").replace('\r', "\n"))
}

/// `json.loads(text)` (strict).
pub fn loads(text: &str) -> PyResult<Value> {
    if text.starts_with('\u{feff}') {
        return Err(decode_error("Unexpected UTF-8 BOM (decode using utf-8-sig)", 0));
    }
    let mut p = Parser { s: text.as_bytes(), i: 0, text };
    p.skip_ws();
    let v = p.value(0)?;
    p.skip_ws();
    if p.i != p.s.len() {
        return Err(decode_error("Extra data", p.i));
    }
    Ok(v)
}

fn decode_error(msg: &str, pos: usize) -> PyException {
    PyException::new("JSONDecodeError", format!("{msg} (byte {pos})"))
}

struct Parser<'a> {
    s: &'a [u8],
    i: usize,
    text: &'a str,
}

impl Parser<'_> {
    fn skip_ws(&mut self) {
        while self.i < self.s.len() && matches!(self.s[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }

    fn starts_with(&self, lit: &str) -> bool {
        self.s[self.i..].starts_with(lit.as_bytes())
    }

    fn value(&mut self, depth: usize) -> PyResult<Value> {
        if depth > MAX_DEPTH {
            return Err(PyException::new("RecursionError", "maximum recursion depth exceeded while decoding"));
        }
        let Some(&c) = self.s.get(self.i) else {
            return Err(decode_error("Expecting value", self.i));
        };
        match c {
            b'"' => Ok(Value::Str(self.string()?)),
            b'{' => self.object(depth),
            b'[' => self.array(depth),
            b'n' if self.starts_with("null") => {
                self.i += 4;
                Ok(Value::Null)
            }
            b't' if self.starts_with("true") => {
                self.i += 4;
                Ok(Value::Bool(true))
            }
            b'f' if self.starts_with("false") => {
                self.i += 5;
                Ok(Value::Bool(false))
            }
            b'N' if self.starts_with("NaN") => {
                self.i += 3;
                Ok(Value::Float(f64::NAN))
            }
            b'I' if self.starts_with("Infinity") => {
                self.i += 8;
                Ok(Value::Float(f64::INFINITY))
            }
            b'-' if self.starts_with("-Infinity") => {
                self.i += 9;
                Ok(Value::Float(f64::NEG_INFINITY))
            }
            b'-' | b'0'..=b'9' => self.number(),
            _ => Err(decode_error("Expecting value", self.i)),
        }
    }

    fn digits(&mut self) -> usize {
        let start = self.i;
        while self.i < self.s.len() && self.s[self.i].is_ascii_digit() {
            self.i += 1;
        }
        self.i - start
    }

    fn number(&mut self) -> PyResult<Value> {
        let start = self.i;
        if self.s[self.i] == b'-' {
            self.i += 1;
        }
        match self.s.get(self.i) {
            Some(b'1'..=b'9') => {
                self.digits();
            }
            Some(b'0') => self.i += 1,
            _ => return Err(decode_error("Expecting value", start)),
        }
        let mut is_float = false;
        if self.s.get(self.i) == Some(&b'.') && self.s.get(self.i + 1).is_some_and(|b| b.is_ascii_digit()) {
            self.i += 1;
            self.digits();
            is_float = true;
        }
        if matches!(self.s.get(self.i), Some(b'e' | b'E')) {
            let save = self.i;
            self.i += 1;
            if matches!(self.s.get(self.i), Some(b'+' | b'-')) {
                self.i += 1;
            }
            if self.digits() == 0 {
                self.i = save;
            } else {
                is_float = true;
            }
        }
        let lit = &self.text[start..self.i];
        if is_float {
            let f: f64 = lit.parse().map_err(|_| decode_error("Expecting value", start))?;
            Ok(Value::Float(f))
        } else {
            let n_digits = lit.trim_start_matches('-').len();
            if n_digits > INT_MAX_STR_DIGITS {
                return Err(PyException::new(
                    "ValueError",
                    format!("Exceeds the limit ({INT_MAX_STR_DIGITS} digits) for integer string conversion"),
                ));
            }
            Ok(Value::Int(PyInt::parse(lit).expect("validated integer literal")))
        }
    }

    fn hex4(&mut self) -> PyResult<u32> {
        let h = self.s.get(self.i..self.i + 4).ok_or_else(|| decode_error("Invalid \\uXXXX escape", self.i))?;
        let h = std::str::from_utf8(h).map_err(|_| decode_error("Invalid \\uXXXX escape", self.i))?;
        if !h.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err(decode_error("Invalid \\uXXXX escape", self.i));
        }
        self.i += 4;
        Ok(u32::from_str_radix(h, 16).expect("hex digits"))
    }

    fn string(&mut self) -> PyResult<String> {
        let begin = self.i;
        self.i += 1; // opening quote
        let mut out = String::new();
        loop {
            // copy a run of ordinary characters
            let run_start = self.i;
            while self.i < self.s.len() {
                let b = self.s[self.i];
                if b == b'"' || b == b'\\' || b < 0x20 {
                    break;
                }
                self.i += 1;
            }
            out.push_str(&self.text[run_start..self.i]);
            let Some(&b) = self.s.get(self.i) else {
                return Err(decode_error("Unterminated string starting at", begin));
            };
            match b {
                b'"' => {
                    self.i += 1;
                    return Ok(out);
                }
                b'\\' => {
                    self.i += 1;
                    let Some(&e) = self.s.get(self.i) else {
                        return Err(decode_error("Unterminated string starting at", begin));
                    };
                    self.i += 1;
                    match e {
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'/' => out.push('/'),
                        b'b' => out.push('\u{08}'),
                        b'f' => out.push('\u{0c}'),
                        b'n' => out.push('\n'),
                        b'r' => out.push('\r'),
                        b't' => out.push('\t'),
                        b'u' => {
                            let mut u = self.hex4()?;
                            if (0xd800..0xdc00).contains(&u) && self.starts_with("\\u") {
                                let save = self.i;
                                self.i += 2;
                                let lo = self.hex4()?;
                                if (0xdc00..0xe000).contains(&lo) {
                                    u = 0x10000 + (((u - 0xd800) << 10) | (lo - 0xdc00));
                                } else {
                                    self.i = save;
                                }
                            }
                            match char::from_u32(u) {
                                Some(c) => out.push(c),
                                None => {
                                    return Err(PyException::new(
                                        "ValueError",
                                        format!(
                                            "lone surrogate \\u{u:04x} is not representable (documented divergence)"
                                        ),
                                    ))
                                }
                            }
                        }
                        _ => return Err(decode_error("Invalid \\escape", self.i - 2)),
                    }
                }
                _ => return Err(decode_error("Invalid control character at", self.i)),
            }
        }
    }

    fn object(&mut self, depth: usize) -> PyResult<Value> {
        self.i += 1;
        let mut d = Dict::new();
        self.skip_ws();
        if self.s.get(self.i) == Some(&b'}') {
            self.i += 1;
            return Ok(Value::Dict(d));
        }
        loop {
            if self.s.get(self.i) != Some(&b'"') {
                return Err(decode_error("Expecting property name enclosed in double quotes", self.i));
            }
            let key = self.string()?;
            self.skip_ws();
            if self.s.get(self.i) != Some(&b':') {
                return Err(decode_error("Expecting ':' delimiter", self.i));
            }
            self.i += 1;
            self.skip_ws();
            let v = self.value(depth + 1)?;
            d.insert(key, v);
            self.skip_ws();
            match self.s.get(self.i) {
                Some(b'}') => {
                    self.i += 1;
                    return Ok(Value::Dict(d));
                }
                Some(b',') => {
                    self.i += 1;
                    self.skip_ws();
                }
                _ => return Err(decode_error("Expecting ',' delimiter", self.i)),
            }
        }
    }

    fn array(&mut self, depth: usize) -> PyResult<Value> {
        self.i += 1;
        let mut items = Vec::new();
        self.skip_ws();
        if self.s.get(self.i) == Some(&b']') {
            self.i += 1;
            return Ok(Value::List(items));
        }
        loop {
            items.push(self.value(depth + 1)?);
            self.skip_ws();
            match self.s.get(self.i) {
                Some(b']') => {
                    self.i += 1;
                    return Ok(Value::List(items));
                }
                Some(b',') => {
                    self.i += 1;
                    self.skip_ws();
                }
                _ => return Err(decode_error("Expecting ',' delimiter", self.i)),
            }
        }
    }
}

// ============================================================================================================ Python semantics

/// `str.isprintable()` for one character, from the CPython 3.11 / unicodedata 14.0.0 table generated by
/// `scripts/rust_migration/gen_pyjson_vectors.py` (`pyjson_unicode.rs`).
pub fn py_isprintable(c: char) -> bool {
    !in_ranges(NON_PRINTABLE, c)
}

/// Word character of `re` with a str pattern (`str.isalnum()` or `_`), the class behind `\w` and `\b`; same table
/// provenance as [`py_isprintable`].
pub fn py_isword(c: char) -> bool {
    in_ranges(WORD, c)
}

fn in_ranges(table: &[(u32, u32)], c: char) -> bool {
    let n = c as u32;
    let i = table.partition_point(|&(lo, _)| lo <= n);
    i > 0 && n <= table[i - 1].1
}

/// `str.isspace()` for one character (Unicode White_Space plus the information separators U+001C..U+001F).
pub fn py_isspace(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

/// `str.strip()` (no argument).
pub fn py_strip(s: &str) -> &str {
    s.trim_matches(py_isspace)
}

/// `repr(str)`.
pub fn py_repr_str(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') { '"' } else { '\'' };
    let mut out = String::with_capacity(s.len() + 2);
    out.push(quote);
    for c in s.chars() {
        match c {
            c if c == quote || c == '\\' => {
                out.push('\\');
                out.push(c);
            }
            '\t' => out.push_str("\\t"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            c if (c as u32) < 0x20 || c as u32 == 0x7f => out.push_str(&format!("\\x{:02x}", c as u32)),
            c if (c as u32) < 0x7f => out.push(c),
            c if py_isprintable(c) => out.push(c),
            c => {
                let n = c as u32;
                if n <= 0xff {
                    out.push_str(&format!("\\x{n:02x}"));
                } else if n <= 0xffff {
                    out.push_str(&format!("\\u{n:04x}"));
                } else {
                    out.push_str(&format!("\\U{n:08x}"));
                }
            }
        }
    }
    out.push(quote);
    out
}

/// `repr(value)`.
pub fn py_repr(v: &Value) -> String {
    match v {
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::Int(i) => i.to_string(),
        Value::Float(f) => float_repr(*f),
        Value::Str(s) => py_repr_str(s),
        Value::List(items) => format!("[{}]", items.iter().map(py_repr).collect::<Vec<_>>().join(", ")),
        Value::Dict(d) => format!(
            "{{{}}}",
            d.iter().map(|(k, v)| format!("{}: {}", py_repr_str(k), py_repr(v))).collect::<Vec<_>>().join(", ")
        ),
    }
}

/// `repr(tuple_of_values)`.
pub fn py_repr_tuple(items: &[Value]) -> String {
    match items.len() {
        1 => format!("({},)", py_repr(&items[0])),
        _ => format!("({})", items.iter().map(py_repr).collect::<Vec<_>>().join(", ")),
    }
}

/// `str(value)`.
pub fn py_str(v: &Value) -> String {
    match v {
        Value::Str(s) => s.clone(),
        other => py_repr(other),
    }
}

/// Exact comparison of an int with a float (CPython compares the exact values).
fn int_float_eq(i: &PyInt, f: f64) -> bool {
    if !f.is_finite() || f.fract() != 0.0 {
        return false;
    }
    match PyInt::parse(&format!("{f:.0}")) {
        Some(fi) => &fi == i,
        None => false,
    }
}

fn numeric_eq(a: &Value, b: &Value) -> Option<bool> {
    let as_int = |v: &Value| -> Option<PyInt> {
        match v {
            Value::Bool(x) => Some(PyInt::from_i64(*x as i64)),
            Value::Int(i) => Some(i.clone()),
            _ => None,
        }
    };
    match (a, b) {
        (Value::Float(x), Value::Float(y)) => Some(x == y),
        (Value::Float(x), other) | (other, Value::Float(x)) => as_int(other).map(|i| int_float_eq(&i, *x)),
        _ => match (as_int(a), as_int(b)) {
            (Some(x), Some(y)) => Some(x == y),
            _ => None,
        },
    }
}

/// Python `a == b` for JSON-shaped values (bool / int / float compare numerically; dicts as unordered mappings).
pub fn py_eq(a: &Value, b: &Value) -> bool {
    if let Some(r) = numeric_eq(a, b) {
        return r;
    }
    match (a, b) {
        (Value::Null, Value::Null) => true,
        (Value::Str(x), Value::Str(y)) => x == y,
        (Value::List(x), Value::List(y)) => x.len() == y.len() && x.iter().zip(y).all(|(p, q)| py_eq(p, q)),
        (Value::Dict(x), Value::Dict(y)) => {
            x.len() == y.len() && x.iter().all(|(k, v)| y.get(k).is_some_and(|w| py_eq(v, w)))
        }
        _ => false,
    }
}

/// `str.lower()` (full Unicode lower-case mapping, as CPython).
pub fn py_lower(s: &str) -> String {
    s.to_lowercase()
}

/// `str.upper()` (full Unicode upper-case mapping, as CPython).
pub fn py_upper(s: &str) -> String {
    s.to_uppercase()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn float_repr_matches_python_spellings() {
        for (x, want) in [
            (1e-05, "1e-05"),
            (1.5e16, "1.5e+16"),
            (1e16, "1e+16"),
            (1e15, "1000000000000000.0"),
            (9999999999999998.0, "9999999999999998.0"),
            (100.0, "100.0"),
            (-0.0, "-0.0"),
            (0.0, "0.0"),
            (0.0001, "0.0001"),
            (0.00012, "0.00012"),
            (0.1, "0.1"),
            (1.0 / 3.0, "0.3333333333333333"),
            (5e-324, "5e-324"),
            (f64::MAX, "1.7976931348623157e+308"),
            (2.5, "2.5"),
            (-1.25e-7, "-1.25e-07"),
            (123456789012345680000.0, "1.2345678901234568e+20"),
            (1e100, "1e+100"),
            (0.3, "0.3"),
            (26280.0, "26280.0"),
            (1e-3, "0.001"),
        ] {
            assert_eq!(float_repr(x), want, "{x:?}");
        }
        assert_eq!(float_repr(f64::NAN), "nan");
        assert_eq!(float_repr(f64::NEG_INFINITY), "-inf");
        assert_eq!(json_float(f64::INFINITY, true).unwrap(), "Infinity");
        assert_eq!(json_float(f64::NAN, false).unwrap_err().class, "ValueError");
    }

    #[test]
    fn dumps_reproduces_the_indent_1_layout() {
        let v =
            loads(r#"{"a": [1, 2.0, {"b": null}], "e": {}, "l": [], "s": "x\u00e9\n\"\u0001", "t": true}"#).unwrap();
        let got = dumps(&v, &DumpOptions::config_writer()).unwrap();
        let want = "{\n \"a\": [\n  1,\n  2.0,\n  {\n   \"b\": null\n  }\n ],\n \"e\": {},\n \"l\": [],\n \
                    \"s\": \"x\u{e9}\\n\\\"\\u0001\",\n \"t\": true\n}";
        assert_eq!(got, want);
        let compact = dumps(&v, &DumpOptions::canonical_hash()).unwrap();
        assert_eq!(
            compact,
            "{\"a\":[1,2.0,{\"b\":null}],\"e\":{},\"l\":[],\"s\":\"x\u{e9}\\n\\\"\\u0001\",\"t\":true}"
        );
        let ascii = dumps(&Value::str("\u{e9}\u{1F600}"), &DumpOptions::default()).unwrap();
        assert_eq!(ascii, "\"\\u00e9\\ud83d\\ude00\"");
        let default = dumps(&loads("{\"a\": [1, 2]}").unwrap(), &DumpOptions::default()).unwrap();
        assert_eq!(default, "{\"a\": [1, 2]}");
    }

    #[test]
    fn loads_keeps_order_exact_ints_and_python_duplicates() {
        let v = loads("{\"z\": 1, \"a\": 2, \"z\": 3, \"big\": 123456789012345678901234567890, \"neg0\": -0}").unwrap();
        let d = v.as_dict().unwrap();
        assert_eq!(d.keys().cloned().collect::<Vec<_>>(), ["z", "a", "big", "neg0"]);
        assert_eq!(d.get("z"), Some(&Value::int(3)));
        assert_eq!(
            dumps(&v, &DumpOptions::canonical_hash()).unwrap(),
            "{\"a\":2,\"big\":123456789012345678901234567890,\"neg0\":0,\"z\":3}"
        );
        assert!(
            matches!(loads("[NaN, Infinity, -Infinity]").unwrap().as_list().unwrap()[2], Value::Float(f) if f == f64::NEG_INFINITY)
        );
        for bad in ["", "[1,]", "{\"a\" 1}", "\"\u{1}\"", "01", "1 2", "[1.]", "\u{feff}1", "\"\\x\""] {
            assert_eq!(loads(bad).unwrap_err().class, "JSONDecodeError", "{bad:?}");
        }
        assert_eq!(loads("\"\\ud83d\\ude00\"").unwrap(), Value::str("\u{1F600}"));
        assert_eq!(loads("\"\\ud800\"").unwrap_err().class, "ValueError");
        assert_eq!(loads("1E400").unwrap(), Value::Float(f64::INFINITY));
    }

    #[test]
    fn repr_and_equality_follow_python() {
        let v = loads(r#"{"a": [1, 2.5, null, true], "b'": "it's", "c": "q\"'", "d": "\u00e9\u00a0\t"}"#).unwrap();
        assert_eq!(py_repr(&v), r#"{'a': [1, 2.5, None, True], "b'": "it's", 'c': 'q"\'', 'd': 'é\xa0\t'}"#);
        assert_eq!(py_repr_tuple(&[Value::str("hall_icp_neutralizer")]), "('hall_icp_neutralizer',)");
        assert!(py_eq(&Value::int(2), &Value::Float(2.0)));
        assert!(py_eq(&Value::Bool(true), &Value::int(1)));
        assert!(!py_eq(&loads("9007199254740993").unwrap(), &Value::Float(9007199254740992.0)));
        assert!(py_eq(&loads("{\"a\":1,\"b\":2}").unwrap(), &loads("{\"b\":2.0,\"a\":true}").unwrap()));
        assert!(!py_eq(&Value::str("1"), &Value::int(1)));
        assert_eq!(py_strip("\u{1c} x \u{a0}"), "x");
        assert!(!Value::Float(0.0).truthy() && Value::str("0").truthy() && !Value::List(vec![]).truthy());
    }

    #[test]
    fn read_text_translates_newlines() {
        assert_eq!(read_text_utf8(b"a\r\nb\rc\n").unwrap(), "a\nb\nc\n");
        assert_eq!(read_text_utf8(b"\xff").unwrap_err().class, "UnicodeDecodeError");
    }
}

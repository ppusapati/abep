//! JSON record helpers: the reference returns dicts; these build the same records as `serde_json::Value` objects.

use serde_json::{Map, Value};

/// A float leaf; non-finite values as the registered strings "NaN", "+inf", "-inf".
pub fn fnum(x: f64) -> Value {
    if x.is_nan() {
        Value::String("NaN".into())
    } else if x.is_infinite() {
        Value::String(if x > 0.0 { "+inf" } else { "-inf" }.into())
    } else {
        Value::from(x)
    }
}

/// An optional float leaf (None -> null).
pub fn onum(x: Option<f64>) -> Value {
    x.map(fnum).unwrap_or(Value::Null)
}

/// An optional string leaf (None -> null).
pub fn ostr(x: Option<&str>) -> Value {
    x.map(|s| Value::String(s.to_string())).unwrap_or(Value::Null)
}

/// A float map keyed by species (or any ordered names).
pub fn fmap<'a>(pairs: impl IntoIterator<Item = (&'a str, f64)>) -> Value {
    let mut m = Map::new();
    for (k, v) in pairs {
        m.insert(k.to_string(), fnum(v));
    }
    Value::Object(m)
}

/// A list of strings.
pub fn slist<S: AsRef<str>>(xs: impl IntoIterator<Item = S>) -> Value {
    Value::Array(xs.into_iter().map(|s| Value::String(s.as_ref().to_string())).collect())
}

/// A list of floats.
pub fn flist(xs: &[f64]) -> Value {
    Value::Array(xs.iter().map(|x| fnum(*x)).collect())
}

/// Read a float leaf back (numbers, or the non-finite strings).
pub fn as_f64(v: &Value) -> Option<f64> {
    match v {
        Value::Number(n) => n.as_f64(),
        Value::String(s) => match s.as_str() {
            "NaN" => Some(f64::NAN),
            "+inf" => Some(f64::INFINITY),
            "-inf" => Some(f64::NEG_INFINITY),
            _ => None,
        },
        _ => None,
    }
}

/// Object builder preserving nothing but keys (the comparison is on key sets).
#[derive(Default)]
pub struct Obj(pub Map<String, Value>);

impl Obj {
    pub fn new() -> Self {
        Obj(Map::new())
    }
    pub fn set(mut self, k: &str, v: impl Into<Value>) -> Self {
        self.0.insert(k.to_string(), v.into());
        self
    }
    pub fn f(self, k: &str, x: f64) -> Self {
        self.set(k, fnum(x))
    }
    pub fn of(self, k: &str, x: Option<f64>) -> Self {
        self.set(k, onum(x))
    }
    pub fn s(self, k: &str, x: &str) -> Self {
        self.set(k, Value::String(x.to_string()))
    }
    pub fn b(self, k: &str, x: bool) -> Self {
        self.set(k, Value::Bool(x))
    }
    pub fn insert(&mut self, k: &str, v: impl Into<Value>) {
        self.0.insert(k.to_string(), v.into());
    }
    pub fn build(self) -> Value {
        Value::Object(self.0)
    }
}

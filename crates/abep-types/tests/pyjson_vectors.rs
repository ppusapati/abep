//! abep_types::pyjson against the CPython reference vectors of `scripts/rust_migration/gen_pyjson_vectors.py`
//! (preregistered seed 202610052; `tests/data/pyjson_vectors_v1.json`). `ABEP_PYJSON_VECTORS` points at a
//! development vector file instead.

use abep_types::pyjson::{
    dumps, encode_string, float_repr, json_float, loads, py_isprintable, py_repr_str, DumpOptions, Value,
};
use sha2::{Digest, Sha256};
use std::path::PathBuf;

const REGISTERED_SEED: i64 = 202610052;

fn vectors() -> Value {
    let path = match std::env::var("ABEP_PYJSON_VECTORS") {
        Ok(p) => PathBuf::from(p),
        Err(_) => PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/data/pyjson_vectors_v1.json"),
    };
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    loads(&text).expect("vector file parses")
}

fn get<'a>(v: &'a Value, k: &str) -> &'a Value {
    v.as_dict().and_then(|d| d.get(k)).unwrap_or_else(|| panic!("missing {k}"))
}

fn s(v: &Value) -> &str {
    v.as_str().expect("string")
}

struct SplitMix64(u64);

impl SplitMix64 {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    fn decimal(&mut self) -> String {
        let (a, b, c) = (self.next(), self.next(), self.next());
        let ndig = 1 + (a % 17) as u32;
        let mant = b % 10u64.pow(ndig);
        let exp = (c % 660) as i64 - 340;
        let sign = if (a >> 63) & 1 == 1 { "-" } else { "" };
        format!("{sign}{mant}e{exp}")
    }
}

fn json_spelling(x: f64) -> String {
    json_float(x, true).expect("allow_nan")
}

#[test]
fn vector_file_is_the_registered_one() {
    let v = vectors();
    if std::env::var("ABEP_PYJSON_VECTORS").is_err() {
        assert_eq!(get(&v, "seed"), &Value::int(REGISTERED_SEED));
    }
    assert_eq!(s(get(&v, "float_repr_style")), "short");
    assert_eq!(s(get(&v, "unidata_version")), "14.0.0");
}

#[test]
fn float_repr_matches_cpython_on_explicit_vectors() {
    let v = vectors();
    let rows = get(&v, "float_explicit").as_list().unwrap();
    assert!(rows.len() > 10_000);
    for row in rows {
        let r = row.as_list().unwrap();
        let bits = u64::from_str_radix(s(&r[0]), 16).unwrap();
        let x = f64::from_bits(bits);
        assert_eq!(float_repr(x), s(&r[1]), "bits {}", s(&r[0]));
        assert_eq!(json_spelling(x), s(&r[2]), "bits {}", s(&r[0]));
        if !x.is_nan() {
            match loads(s(&r[2])).unwrap() {
                Value::Float(y) => assert_eq!(y.to_bits(), bits, "round trip {}", s(&r[2])),
                other => panic!("{other:?}"),
            }
        }
    }
}

#[test]
fn float_streams_match_cpython_digests() {
    let v = vectors();
    for st in get(&v, "float_streams").as_list().unwrap() {
        let seed = match get(st, "seed") {
            Value::Int(i) => i.as_i64().unwrap() as u64,
            other => panic!("{other:?}"),
        };
        let n = match get(st, "n") {
            Value::Int(i) => i.as_i64().unwrap(),
            other => panic!("{other:?}"),
        };
        let mut r = SplitMix64(seed);
        let mut h = Sha256::new();
        for _ in 0..n {
            let line = match s(get(st, "kind")) {
                "bits" => {
                    let b = r.next();
                    let x = f64::from_bits(b);
                    format!("{b:016x} {} {}\n", float_repr(x), json_spelling(x))
                }
                "decimal" => {
                    let lit = r.decimal();
                    let x: f64 = lit.parse().unwrap();
                    format!("{lit} {} {}\n", float_repr(x), json_spelling(x))
                }
                k => panic!("unknown stream kind {k}"),
            };
            h.update(line.as_bytes());
        }
        assert_eq!(format!("{:x}", h.finalize()), s(get(st, "sha256")), "stream {}", s(get(st, "kind")));
    }
}

#[test]
fn strings_encode_and_repr_like_cpython() {
    let v = vectors();
    for row in get(&v, "strings").as_list().unwrap() {
        let text = s(get(row, "s"));
        let mut a = String::new();
        encode_string(text, true, &mut a);
        assert_eq!(a, s(get(row, "json_ascii")), "{text:?}");
        let mut u = String::new();
        encode_string(text, false, &mut u);
        assert_eq!(u, s(get(row, "json_utf8")), "{text:?}");
        assert_eq!(py_repr_str(text), s(get(row, "repr")), "{text:?}");
    }
}

#[test]
fn isprintable_table_matches_cpython_for_every_code_point() {
    let v = vectors();
    let ranges: Vec<(u32, u32)> = get(&v, "non_printable")
        .as_list()
        .unwrap()
        .iter()
        .map(|r| {
            let r = r.as_list().unwrap();
            let n = |x: &Value| match x {
                Value::Int(i) => i.as_i64().unwrap() as u32,
                other => panic!("{other:?}"),
            };
            (n(&r[0]), n(&r[1]))
        })
        .collect();
    for cp in 0..=0x10FFFFu32 {
        if let Some(c) = char::from_u32(cp) {
            let want = !ranges.iter().any(|&(lo, hi)| (lo..=hi).contains(&cp));
            assert_eq!(py_isprintable(c), want, "U+{cp:04X}");
        }
    }
}

#[test]
fn documents_dump_like_cpython() {
    let v = vectors();
    for doc in get(&v, "documents").as_list().unwrap() {
        let value = loads(s(get(doc, "value_canonical"))).unwrap();
        let mode = get(doc, "mode").as_dict().unwrap();
        let mut o = DumpOptions::default();
        if let Some(Value::Int(i)) = mode.get("indent") {
            o.indent = Some(i.as_i64().unwrap() as usize);
        }
        if let Some(Value::Bool(b)) = mode.get("ensure_ascii") {
            o.ensure_ascii = *b;
        }
        if let Some(Value::Bool(b)) = mode.get("sort_keys") {
            o.sort_keys = *b;
        }
        if let Some(Value::Bool(b)) = mode.get("allow_nan") {
            o.allow_nan = *b;
        }
        if let Some(Value::List(sep)) = mode.get("separators") {
            o.separators = Some((s(&sep[0]).to_string(), s(&sep[1]).to_string()));
        }
        match (dumps(&value, &o), get(doc, "dumps"), get(doc, "error")) {
            (Ok(got), Value::Str(want), Value::Null) => assert_eq!(&got, want),
            (Err(e), Value::Null, Value::Str(cls)) => assert_eq!(e.class, cls),
            (got, want, err) => panic!("{got:?} vs {want:?} / {err:?}"),
        }
    }
}

#[test]
fn generated_config_files_round_trip_byte_for_byte() {
    // config/** JSON written by scripts/config/build_config.py (indent 1, ensure_ascii False, trailing newline)
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../config");
    let mut n = 0;
    for rel in [
        "MANIFEST.json",
        "SOURCES_OF_TRUTH.json",
        "architecture/hall_icp_neutralizer_v1.json",
        "assessment/gate_thresholds_v1.json",
        "constraints/engineering_constraints_v1.json",
        "environment/design_state_set_ref_v1.json",
        "hardware/hardware_bounds_v1.json",
        "model_set/physics_model_set_v1.json",
        "requirements/rfp_constraints_v1.json",
    ] {
        let bytes = std::fs::read(root.join(rel)).unwrap();
        let v = loads(std::str::from_utf8(&bytes).unwrap()).unwrap();
        assert_eq!(abep_types::pyjson::dumps_config_file(&v).unwrap(), bytes, "{rel}");
        n += 1;
    }
    assert_eq!(n, 9);
}

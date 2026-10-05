//! File reading with the error classes of the Python reference (`open`, `json.load`, `tomllib.load`).

use super::pyvalue::PyValue;
use super::{Py, Raised};
use crate::sha256_hex;
use std::io::ErrorKind;
use std::path::{Path, PathBuf};

/// How `open(path, "rb")` fails.
#[derive(Debug, Clone, PartialEq)]
pub(crate) enum OpenError {
    /// FileNotFoundError.
    NotFound,
    /// Any other OSError, by its Python class name.
    Os(String),
}

impl OpenError {
    /// The error escaping a check (no catching context).
    pub(crate) fn raised(self, rel: &str) -> Raised {
        match self {
            OpenError::NotFound => Raised::FileMissing { file: rel.to_string() },
            OpenError::Os(name) => Raised::Other { name, detail: rel.to_string() },
        }
    }
}

pub(crate) fn abs_path(root: &Path, rel: &str) -> PathBuf {
    root.join(rel)
}

/// `open(path).read()` as bytes, with Python's error classes.
pub(crate) fn read(path: &Path) -> Result<Vec<u8>, OpenError> {
    match std::fs::metadata(path) {
        Ok(m) if m.is_dir() => return Err(OpenError::Os("IsADirectoryError".into())),
        Ok(_) => {}
        Err(e) => return Err(classify(e.kind())),
    }
    std::fs::read(path).map_err(|e| classify(e.kind()))
}

fn classify(kind: ErrorKind) -> OpenError {
    match kind {
        ErrorKind::NotFound => OpenError::NotFound,
        ErrorKind::PermissionDenied => OpenError::Os("PermissionError".into()),
        ErrorKind::IsADirectory => OpenError::Os("IsADirectoryError".into()),
        ErrorKind::NotADirectory => OpenError::Os("NotADirectoryError".into()),
        _ => OpenError::Os("OSError".into()),
    }
}

/// `os.path.isfile(path)`.
pub(crate) fn is_file(path: &Path) -> bool {
    path.is_file()
}

/// `os.path.exists(path)`.
pub(crate) fn exists(path: &Path) -> bool {
    path.exists()
}

/// sha256 of a file that exists (Python opens it; a directory raises IsADirectoryError).
pub(crate) fn sha256_of(path: &Path, rel: &str) -> Py<String> {
    read(path).map(|b| sha256_hex(&b)).map_err(|e| e.raised(rel))
}

fn utf8(bytes: &[u8], rel: &str) -> Py<String> {
    String::from_utf8(bytes.to_vec())
        .map_err(|e| Raised::Decode { file: rel.to_string(), detail: format!("UnicodeDecodeError: {e}") })
}

/// `json.load(open(path, encoding="utf-8"))` of already-read bytes.
pub(crate) fn parse_json(bytes: &[u8], rel: &str) -> Py<PyValue> {
    let text = utf8(bytes, rel)?;
    serde_json::from_str::<PyValue>(&text)
        .map_err(|e| Raised::Decode { file: rel.to_string(), detail: format!("JSONDecodeError: {e}") })
}

/// `tomllib.load(open(path, "rb"))` of already-read bytes. tomllib (TOML 1.0.0) first replaces CRLF by LF and then
/// rejects every remaining ASCII control character except tab and LF in every context; the scan below applies that
/// rule before the TOML 1.0.0 parser.
pub(crate) fn parse_toml(bytes: &[u8], rel: &str) -> Py<PyValue> {
    let text = utf8(bytes, rel)?.replace("\r\n", "\n");
    if let Some(c) = text.chars().find(|&c| (c < ' ' && c != '\t' && c != '\n') || c == '\u{7f}') {
        return Err(Raised::Decode {
            file: rel.to_string(),
            detail: format!("TOMLDecodeError: illegal control character {:?}", c),
        });
    }
    let table: toml::Table = toml::from_str(&text)
        .map_err(|e| Raised::Decode { file: rel.to_string(), detail: format!("TOMLDecodeError: {e}") })?;
    Ok(PyValue::from_toml(&toml::Value::Table(table)))
}

/// Read and parse a JSON file outside any catching context (a missing file escapes as FILE_MISSING).
pub(crate) fn load_json(root: &Path, rel: &str) -> Py<PyValue> {
    let bytes = read(&abs_path(root, rel)).map_err(|e| e.raised(rel))?;
    parse_json(&bytes, rel)
}

/// Read and parse a TOML file outside any catching context.
pub(crate) fn load_toml(root: &Path, rel: &str) -> Py<PyValue> {
    let bytes = read(&abs_path(root, rel)).map_err(|e| e.raised(rel))?;
    parse_toml(&bytes, rel)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decode_errors_are_decode_class() {
        assert!(matches!(parse_json(b"{\"a\": 1,}", "x.json"), Err(Raised::Decode { .. })));
        assert!(matches!(parse_json(b"{\"a\": \xff}", "x.json"), Err(Raised::Decode { .. })));
        assert!(matches!(parse_json(b"{\"a\": \"tab\there\"}", "x.json"), Err(Raised::Decode { .. })));
        assert!(matches!(parse_json(b"[1] x", "x.json"), Err(Raised::Decode { .. })));
        assert!(matches!(parse_toml(b"a = 1\n# del \x7f\n", "x.toml"), Err(Raised::Decode { .. })));
        assert!(matches!(parse_toml(b"a = 1\rb = 2\n", "x.toml"), Err(Raised::Decode { .. })));
        assert!(matches!(parse_toml(b"a = \"\\e\"\n", "x.toml"), Err(Raised::Decode { .. })));
        assert!(matches!(parse_toml(b"a = 1\na = 2\n", "x.toml"), Err(Raised::Decode { .. })));
        let v = parse_toml(b"a = 1\r\n[t]\nb = \"x\" # ok\t\n", "x.toml").unwrap();
        assert_eq!(v.getitem_str("t").unwrap().getitem_str("b").unwrap(), PyValue::str("x"));
    }

    #[test]
    fn open_errors_follow_python_classes() {
        let dir = std::env::temp_dir();
        assert_eq!(read(&dir), Err(OpenError::Os("IsADirectoryError".into())));
        assert_eq!(read(&dir.join("abep-verifier-no-such-file-7f3a")), Err(OpenError::NotFound));
    }
}

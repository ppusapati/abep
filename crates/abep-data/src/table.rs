//! Strict reader of the frozen comma-separated tables (no quoting, one header line; every numeric field parses to the
//! correctly rounded binary64, as the reference's `np.loadtxt` / pandas parsers do).

use abep_types::{AbepError, AbepResult};

pub fn schema(path: &str, message: impl Into<String>) -> AbepError {
    AbepError::Schema { path: path.to_string(), message: message.into() }
}

/// Lines of `raw` (UTF-8), split as Python's `str.splitlines()` does for these files (`\n`, optional `\r`).
pub fn lines<'a>(raw: &'a [u8], path: &str) -> AbepResult<Vec<&'a str>> {
    let text = std::str::from_utf8(raw).map_err(|e| schema(path, format!("not UTF-8: {e}")))?;
    Ok(text.lines().collect())
}

/// Check the header line against `columns`.
pub fn check_header(header: &str, columns: &[&str], path: &str) -> AbepResult<()> {
    if header.split(',').ne(columns.iter().copied()) {
        return Err(schema(path, format!("unexpected CSV header {header:?}")));
    }
    Ok(())
}

pub fn parse_f64(field: &str, path: &str, line_no: usize) -> AbepResult<f64> {
    field.trim().parse::<f64>().map_err(|_| schema(path, format!("line {line_no}: {field:?} is not a number")))
}

//! Version labels of a Python module, as `scripts/config/build_config.py::_version_labels` reads them with `ast`:
//! every top-level statement `NAME = <str literal>` (one Name target; the value a str constant, possibly an implicit
//! concatenation of literals inside parentheses) whose name contains VERSION, SCHEMA, MODEL_ID, DATASET_ID or
//! SPEC_ID. Later assignments to a name keep its first position and take the last value (dict semantics).
//!
//! This is a tokenizer, not a parser (contract DIV-02): it assumes syntactically valid source. Non-ASCII label names
//! (NFKC-normalized by Python) and `\N{...}` escapes in a label value are refused with `NotImplementedError`.

use crate::{ConfigError, ConfigResult};
use abep_types::pyjson::{Dict, Value};

const LABEL_KEYS: [&str; 5] = ["VERSION", "SCHEMA", "MODEL_ID", "DATASET_ID", "SPEC_ID"];
const COMPOUND: [&str; 13] =
    ["if", "elif", "else", "while", "for", "try", "except", "finally", "with", "def", "class", "async", "@"];

#[derive(Debug, Clone, PartialEq)]
enum Tok {
    Name(String),
    Str { prefix: String, body: String, raw: bool },
    Op(String),
    Other,
}

struct Lexer<'a> {
    c: Vec<char>,
    i: usize,
    _src: &'a str,
}

fn is_ident_start(c: char) -> bool {
    c == '_' || c.is_alphabetic() || (!c.is_ascii() && !c.is_whitespace())
}

fn is_ident_char(c: char) -> bool {
    is_ident_start(c) || c.is_ascii_digit() || (!c.is_ascii() && c.is_numeric())
}

const OPS3: [&str; 5] = ["**=", "//=", ">>=", "<<=", "..."];
const OPS2: [&str; 20] = [
    "==", "<=", ">=", "!=", "->", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "@=", ":=", "**", "//", "<<", ">>",
    "<>",
];

impl Lexer<'_> {
    fn peek(&self, k: usize) -> Option<char> {
        self.c.get(self.i + k).copied()
    }

    fn starts(&self, s: &str) -> bool {
        s.chars().enumerate().all(|(k, ch)| self.peek(k) == Some(ch))
    }

    /// The body of a string literal whose opening quote is at `self.i`; returns the raw body text.
    fn string_body(&mut self, raw: bool) -> String {
        let q = self.c[self.i];
        let triple = self.peek(1) == Some(q) && self.peek(2) == Some(q);
        self.i += if triple { 3 } else { 1 };
        let mut body = String::new();
        while self.i < self.c.len() {
            let ch = self.c[self.i];
            if ch == '\\' && self.i + 1 < self.c.len() {
                body.push(ch);
                body.push(self.c[self.i + 1]);
                self.i += 2;
                continue;
            }
            if ch == q && (!triple || (self.peek(1) == Some(q) && self.peek(2) == Some(q))) {
                self.i += if triple { 3 } else { 1 };
                return body;
            }
            body.push(ch);
            self.i += 1;
        }
        let _ = raw;
        body
    }
}

/// Decode a non-raw str literal body (Python escape rules).
fn decode_escapes(body: &str) -> ConfigResult<String> {
    let c: Vec<char> = body.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    let hex = |s: &[char]| -> Option<u32> {
        if s.iter().all(|ch| ch.is_ascii_hexdigit()) {
            u32::from_str_radix(&s.iter().collect::<String>(), 16).ok()
        } else {
            None
        }
    };
    let bad = |m: &str| ConfigError::new("SyntaxError", m.to_string());
    while i < c.len() {
        if c[i] != '\\' || i + 1 >= c.len() {
            out.push(c[i]);
            i += 1;
            continue;
        }
        let e = c[i + 1];
        i += 2;
        match e {
            '\n' => {}
            '\\' => out.push('\\'),
            '\'' => out.push('\''),
            '"' => out.push('"'),
            'a' => out.push('\u{07}'),
            'b' => out.push('\u{08}'),
            'f' => out.push('\u{0c}'),
            'n' => out.push('\n'),
            'r' => out.push('\r'),
            't' => out.push('\t'),
            'v' => out.push('\u{0b}'),
            '0'..='7' => {
                let mut v = e.to_digit(8).expect("octal");
                let mut n = 1;
                while n < 3 && i < c.len() && ('0'..='7').contains(&c[i]) {
                    v = v * 8 + c[i].to_digit(8).expect("octal");
                    i += 1;
                    n += 1;
                }
                out.push(char::from_u32(v).ok_or_else(|| bad("octal escape"))?);
            }
            'x' | 'u' | 'U' => {
                let n = match e {
                    'x' => 2,
                    'u' => 4,
                    _ => 8,
                };
                let v = c.get(i..i + n).and_then(hex).ok_or_else(|| bad("truncated escape"))?;
                i += n;
                let ch = char::from_u32(v).ok_or_else(|| {
                    ConfigError::new("ValueError", format!("escape \\{e}{v:x} is not a Rust char (surrogate / range)"))
                })?;
                out.push(ch);
            }
            'N' => {
                return Err(ConfigError::new("NotImplementedError", "\\N{...} escape in a label value (DIV-02)"));
            }
            other => {
                out.push('\\');
                out.push(other);
            }
        }
    }
    Ok(out)
}

/// Logical lines of a module: (indented?, tokens).
fn logical_lines(src: &str) -> Vec<(bool, Vec<(Tok, usize)>)> {
    let mut lx = Lexer { c: src.chars().collect(), i: 0, _src: src };
    let mut lines = Vec::new();
    let mut toks: Vec<(Tok, usize)> = Vec::new();
    let mut depth: usize = 0;
    let mut indented = false;
    let mut at_line_start = true;
    while lx.i < lx.c.len() {
        if at_line_start && depth == 0 && toks.is_empty() {
            // indentation of a new logical line; blank and comment-only lines are skipped
            let mut j = lx.i;
            let mut ind = false;
            while j < lx.c.len() && matches!(lx.c[j], ' ' | '\t' | '\x0c') {
                if lx.c[j] != '\x0c' {
                    ind = true;
                }
                j += 1;
            }
            if j >= lx.c.len() || lx.c[j] == '\n' || lx.c[j] == '#' {
                while j < lx.c.len() && lx.c[j] != '\n' {
                    j += 1;
                }
                lx.i = j + 1;
                continue;
            }
            indented = ind;
            lx.i = j;
            at_line_start = false;
            continue;
        }
        at_line_start = false;
        let ch = lx.c[lx.i];
        match ch {
            ' ' | '\t' | '\x0c' => lx.i += 1,
            '#' => {
                while lx.i < lx.c.len() && lx.c[lx.i] != '\n' {
                    lx.i += 1;
                }
            }
            '\\' if lx.peek(1) == Some('\n') => lx.i += 2,
            '\n' => {
                lx.i += 1;
                if depth == 0 {
                    if !toks.is_empty() {
                        lines.push((indented, std::mem::take(&mut toks)));
                    }
                    at_line_start = true;
                }
            }
            '\'' | '"' => {
                let body = lx.string_body(false);
                toks.push((Tok::Str { prefix: String::new(), body, raw: false }, depth));
            }
            c if is_ident_start(c) => {
                let s = lx.i;
                while lx.i < lx.c.len() && is_ident_char(lx.c[lx.i]) {
                    lx.i += 1;
                }
                let word: String = lx.c[s..lx.i].iter().collect();
                let lw = word.to_ascii_lowercase();
                if matches!(lx.peek(0), Some('\'' | '"'))
                    && ["r", "u", "b", "br", "rb", "f", "fr", "rf"].contains(&lw.as_str())
                {
                    let raw = lw.contains('r');
                    let body = lx.string_body(raw);
                    toks.push((Tok::Str { prefix: lw, body, raw }, depth));
                } else {
                    toks.push((Tok::Name(word), depth));
                }
            }
            c if c.is_ascii_digit() || (c == '.' && lx.peek(1).is_some_and(|d| d.is_ascii_digit())) => {
                while lx.i < lx.c.len() {
                    let d = lx.c[lx.i];
                    let prev = lx.c[lx.i - 1];
                    if d.is_ascii_alphanumeric()
                        || d == '_'
                        || d == '.'
                        || (matches!(d, '+' | '-') && matches!(prev, 'e' | 'E'))
                    {
                        lx.i += 1;
                    } else {
                        break;
                    }
                }
                toks.push((Tok::Other, depth));
            }
            '(' | '[' | '{' => {
                toks.push((Tok::Op(ch.to_string()), depth));
                depth += 1;
                lx.i += 1;
            }
            ')' | ']' | '}' => {
                depth = depth.saturating_sub(1);
                toks.push((Tok::Op(ch.to_string()), depth));
                lx.i += 1;
            }
            _ => {
                let op = OPS3
                    .iter()
                    .chain(OPS2.iter())
                    .find(|o| lx.starts(o))
                    .map(|o| o.to_string())
                    .unwrap_or_else(|| ch.to_string());
                lx.i += op.chars().count();
                toks.push((Tok::Op(op), depth));
            }
        }
    }
    if !toks.is_empty() {
        lines.push((indented, toks));
    }
    lines
}

/// The str value of `( ... "a" "b" ... )` when `rest` is exactly that (k opening parentheses, string literals, k
/// closing parentheses) and every literal is a str literal (no bytes, no f-string).
fn str_constant(rest: &[Tok]) -> ConfigResult<Option<String>> {
    let open = rest.iter().take_while(|t| matches!(t, Tok::Op(o) if o == "(")).count();
    let close = rest.iter().rev().take_while(|t| matches!(t, Tok::Op(o) if o == ")")).count();
    if open != close || open * 2 >= rest.len() {
        return Ok(None);
    }
    let mid = &rest[open..rest.len() - close];
    let mut out = String::new();
    for t in mid {
        match t {
            Tok::Str { prefix, body, raw } => {
                if prefix.contains('b') || prefix.contains('f') {
                    return Ok(None);
                }
                if *raw {
                    out.push_str(body);
                } else {
                    out.push_str(&decode_escapes(body)?);
                }
            }
            _ => return Ok(None),
        }
    }
    Ok(Some(out))
}

/// `_version_labels(src)`: ordered {name: value}.
pub fn version_labels(src: &str) -> ConfigResult<Dict> {
    let mut out = Dict::new();
    for (indented, toks) in logical_lines(src) {
        if indented {
            continue;
        }
        if let Some((Tok::Name(n), _)) = toks.first() {
            if COMPOUND.contains(&n.as_str()) {
                continue;
            }
        }
        if matches!(toks.first(), Some((Tok::Op(o), _)) if o == "@") {
            continue;
        }
        for stmt in toks.split(|(t, d)| *d == 0 && matches!(t, Tok::Op(o) if o == ";")) {
            let t: Vec<Tok> = stmt.iter().map(|(t, _)| t.clone()).collect();
            let (Some(Tok::Name(name)), Some(Tok::Op(eq))) = (t.first(), t.get(1)) else {
                continue;
            };
            if eq != "=" || !LABEL_KEYS.iter().any(|k| name.contains(k)) {
                continue;
            }
            if let Some(v) = str_constant(&t[2..])? {
                if !name.is_ascii() {
                    return Err(ConfigError::new("NotImplementedError", "non-ASCII label name (DIV-02)"));
                }
                out.insert(name.as_str(), Value::Str(v));
            }
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn labels_follow_ast_semantics() {
        let src = "\"\"\"doc VERSION = 'no'\"\"\"\nA_VERSION = \"a\"\nB_SCHEMA = (\"b1\"  # c\n    'b2')\n\
                   C_VERSION: str = \"c\"\nD_VERSION = E_VERSION = \"d\"\nif x: F_VERSION = \"f\"; G_VERSION = \"g\"\n\
                   x = 1; H_VERSION = r\"h\\n\"\n    I_VERSION = \"i\"\nJ_VERSION = b\"j\"\nK_VERSION = f\"k\"\n\
                   L_VERSION = \"l\\x41\\101\"\nA_VERSION = \"a2\"\nM_VERSION = (\"m\",)\nN_VERSION = \\\n  \"n\"\n";
        let d = version_labels(src).unwrap();
        let got: Vec<(String, String)> = d.iter().map(|(k, v)| (k.clone(), v.as_str().unwrap().to_string())).collect();
        let want = [
            ("A_VERSION", "a2"),
            ("B_SCHEMA", "b1b2"),
            ("H_VERSION", "h\\n"),
            ("L_VERSION", "lAA"),
            ("N_VERSION", "n"),
        ];
        assert_eq!(got, want.map(|(a, b)| (a.to_string(), b.to_string())));
    }
}

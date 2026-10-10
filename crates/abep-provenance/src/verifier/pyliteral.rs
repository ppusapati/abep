//! Fail-closed reader of literal assignments in a Python source file, equivalent to the `ast` rules of the H2-6
//! builder's `_constants()`:
//!
//! * a top-level `NAME = <constant>` (single Name target, value an `ast.Constant`) for each name in `assign_names`;
//! * the entries of a top-level `DICT = {...}` display whose value is a BinOp with an `ast.Constant` left operand
//!   (`"N2": 28.0 * AMU` gives `M_N2_u = 28.0`);
//! * the `name: T = <constant>` statements directly in the body of a top-level class.
//!
//! Python syntax is tokenised (strings, comments, brackets, continuations); expressions are classified by operator
//! precedence without evaluation. A tokenizer-level syntax error is `SyntaxError`; a target statement the grammar
//! does not cover (complex / bytes / Ellipsis constants, `\N{...}` escapes, non-literal dict keys) is
//! `UNSUPPORTED_SYNTAX`, never a silent default.

use super::pyvalue::{decimal_float_grammar, PyValue};
use super::{Py, Raised};
use std::collections::BTreeMap;

/// Which assignments are read.
#[derive(Debug, Clone, Default)]
pub struct LiteralRules {
    pub assign_names: Vec<String>,
    /// (dict name, key template with `{key}`).
    pub dict_binop_left: Option<(String, String)>,
    /// (class name, key template with `{field}`).
    pub class_annassign: Option<(String, String)>,
}

fn syntax(detail: impl Into<String>) -> Raised {
    Raised::Other { name: "SyntaxError".into(), detail: detail.into() }
}

struct Line {
    indent: usize,
    text: String,
}

/// End index (exclusive) of the string literal whose opening quote is at `i`.
fn scan_string(s: &[char], i: usize) -> Py<usize> {
    let q = s[i];
    let triple = s.get(i + 1) == Some(&q) && s.get(i + 2) == Some(&q);
    let mut j = if triple { i + 3 } else { i + 1 };
    loop {
        match s.get(j) {
            None => return Err(syntax("unterminated string literal")),
            Some('\\') => j += 2,
            Some('\n') if !triple => return Err(syntax("unterminated string literal")),
            Some(&c) if c == q => {
                if !triple {
                    return Ok(j + 1);
                }
                if s.get(j + 1) == Some(&q) && s.get(j + 2) == Some(&q) {
                    return Ok(j + 3);
                }
                j += 1;
            }
            Some(_) => j += 1,
        }
    }
}

/// Logical lines with their indentation; comments removed, implicit and explicit continuations joined.
fn logical_lines(src: &str) -> Py<Vec<Line>> {
    let norm = src.replace("\r\n", "\n").replace('\r', "\n");
    let s: Vec<char> = norm.chars().collect();
    let mut lines = Vec::new();
    let mut cur = String::new();
    let (mut i, mut depth, mut indent, mut at_start) = (0usize, 0usize, 0usize, true);
    while i < s.len() {
        if at_start {
            let mut col = 0;
            let mut j = i;
            while let Some(&c) = s.get(j) {
                match c {
                    ' ' => col += 1,
                    '\t' => col = (col / 8 + 1) * 8,
                    '\x0c' => col = 0,
                    _ => break,
                }
                j += 1;
            }
            match s.get(j) {
                None => break,
                Some('\n') => {
                    i = j + 1;
                    continue;
                }
                Some('#') => {
                    while j < s.len() && s[j] != '\n' {
                        j += 1;
                    }
                    i = j + 1;
                    continue;
                }
                Some(_) => {
                    indent = col;
                    i = j;
                    at_start = false;
                    continue;
                }
            }
        }
        let c = s[i];
        match c {
            '#' => {
                while i < s.len() && s[i] != '\n' {
                    i += 1;
                }
            }
            '\'' | '"' => {
                let end = scan_string(&s, i)?;
                cur.extend(&s[i..end]);
                i = end;
            }
            '(' | '[' | '{' => {
                depth += 1;
                cur.push(c);
                i += 1;
            }
            ')' | ']' | '}' => {
                depth = depth.checked_sub(1).ok_or_else(|| syntax(format!("unmatched '{c}'")))?;
                cur.push(c);
                i += 1;
            }
            '\\' => {
                if s.get(i + 1) == Some(&'\n') {
                    cur.push(' ');
                    i += 2;
                } else {
                    return Err(syntax("unexpected character after line continuation character"));
                }
            }
            '\n' => {
                i += 1;
                if depth > 0 {
                    cur.push(' ');
                } else {
                    lines.push(Line { indent, text: cur.trim_end().to_string() });
                    cur.clear();
                    at_start = true;
                }
            }
            _ => {
                cur.push(c);
                i += 1;
            }
        }
    }
    if depth > 0 {
        return Err(syntax("unexpected EOF: unclosed bracket"));
    }
    if !cur.trim().is_empty() {
        lines.push(Line { indent, text: cur.trim_end().to_string() });
    }
    Ok(lines)
}

#[derive(Debug, Clone, PartialEq)]
enum Node {
    Name(String),
    Num(String),
    Str { prefix: String, literal: String },
    Op(String),
    Group(char, Vec<Node>),
}

const OPS3: [&str; 5] = ["**=", "//=", ">>=", "<<=", "..."];
const OPS2: [&str; 19] =
    ["**", "//", ">>", "<<", "<=", ">=", "==", "!=", "->", ":=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "@="];
const OPS1: &str = "+-*/%@&|^~<>=.,:;";

fn is_prefix(p: &str) -> bool {
    matches!(p.to_ascii_lowercase().as_str(), "r" | "u" | "b" | "f" | "br" | "rb" | "fr" | "rf")
}

fn push(stack: &mut [(char, Vec<Node>)], n: Node) {
    if let Some(top) = stack.last_mut() {
        top.1.push(n);
    }
}

fn lex(text: &str) -> Py<Vec<Node>> {
    let s: Vec<char> = text.chars().collect();
    let mut stack: Vec<(char, Vec<Node>)> = vec![(' ', Vec::new())];
    let mut i = 0;
    while i < s.len() {
        let c = s[i];
        if c == ' ' || c == '\t' || c == '\x0c' {
            i += 1;
        } else if c.is_alphabetic() || c == '_' {
            let start = i;
            while i < s.len() && (s[i].is_alphanumeric() || s[i] == '_') {
                i += 1;
            }
            let word: String = s[start..i].iter().collect();
            if matches!(s.get(i), Some('\'') | Some('"')) && is_prefix(&word) {
                let end = scan_string(&s, i)?;
                push(&mut stack, Node::Str { prefix: word.to_ascii_lowercase(), literal: s[i..end].iter().collect() });
                i = end;
            } else {
                push(&mut stack, Node::Name(word));
            }
        } else if c.is_ascii_digit() || (c == '.' && s.get(i + 1).is_some_and(char::is_ascii_digit)) {
            let start = i;
            let hex = c == '0' && matches!(s.get(i + 1), Some('x') | Some('X'));
            while i < s.len() {
                let d = s[i];
                let literal_char = d.is_ascii_alphanumeric() || d == '_' || d == '.';
                let exponent_sign = (d == '+' || d == '-')
                    && !hex
                    && matches!(s[i - 1], 'e' | 'E')
                    && s.get(i + 1).is_some_and(char::is_ascii_digit);
                if !(literal_char || exponent_sign) {
                    break;
                }
                i += 1;
            }
            push(&mut stack, Node::Num(s[start..i].iter().collect()));
        } else if c == '\'' || c == '"' {
            let end = scan_string(&s, i)?;
            push(&mut stack, Node::Str { prefix: String::new(), literal: s[i..end].iter().collect() });
            i = end;
        } else if c == '(' || c == '[' || c == '{' {
            stack.push((c, Vec::new()));
            i += 1;
        } else if c == ')' || c == ']' || c == '}' {
            let open = match c {
                ')' => '(',
                ']' => '[',
                _ => '{',
            };
            match stack.pop() {
                Some((o, nodes)) if o == open && !stack.is_empty() => push(&mut stack, Node::Group(o, nodes)),
                _ => return Err(syntax(format!("unmatched '{c}'"))),
            };
            i += 1;
        } else {
            let rest: String = s[i..s.len().min(i + 3)].iter().collect();
            let op = OPS3
                .iter()
                .find(|o| rest.starts_with(**o))
                .or_else(|| OPS2.iter().find(|o| rest.starts_with(**o)))
                .map(|o| o.to_string())
                .or_else(|| OPS1.contains(c).then(|| c.to_string()))
                .ok_or_else(|| syntax(format!("invalid character {c:?}")))?;
            i += op.chars().count();
            push(&mut stack, Node::Op(op));
        }
    }
    match stack.pop() {
        Some((' ', nodes)) if stack.is_empty() => Ok(nodes),
        _ => Err(syntax("unclosed bracket")),
    }
}

fn is_op(n: &Node, op: &str) -> bool {
    matches!(n, Node::Op(o) if o == op)
}

fn is_name(n: &Node, name: &str) -> bool {
    matches!(n, Node::Name(w) if w == name)
}

fn split_on<'a>(nodes: &'a [Node], op: &str) -> Vec<&'a [Node]> {
    nodes.split(|n| is_op(n, op)).collect()
}

/// `(expr)` -> `expr` (a parenthesised expression is not an AST node; a tuple, an empty pair, a generator or a yield
/// is).
fn strip_parens(mut nodes: &[Node]) -> &[Node] {
    while let [Node::Group('(', inner)] = nodes {
        let tuple = inner.is_empty() || inner.iter().any(|n| is_op(n, ","));
        let other = inner.iter().any(|n| is_name(n, "for") || is_name(n, "yield"));
        if tuple || other {
            break;
        }
        nodes = inner;
    }
    nodes
}

enum Const {
    Value(PyValue),
    Unsupported(String),
    Not,
}

fn parse_int_digits(digits: &str, radix: u32, lit: &str) -> Py<Const> {
    let b = digits.as_bytes();
    let ok_underscores = !digits.ends_with('_') && !digits.contains("__") && (radix != 10 || !digits.starts_with('_'));
    let cleaned: String = digits.chars().filter(|&c| c != '_').collect();
    if !ok_underscores || cleaned.is_empty() || !cleaned.chars().all(|c| c.is_digit(radix)) {
        return Err(syntax(format!("invalid number literal {lit}")));
    }
    if radix == 10 && b.len() > 1 && b[0] == b'0' && cleaned.chars().any(|c| c != '0') {
        return Err(syntax(format!("leading zeros in decimal integer literal {lit}")));
    }
    Ok(match i128::from_str_radix(&cleaned, radix) {
        Ok(v) => Const::Value(PyValue::Int(v)),
        Err(_) => Const::Unsupported(format!("integer literal beyond 128 bits: {lit}")),
    })
}

fn parse_number(lit: &str) -> Py<Const> {
    let lower = lit.to_ascii_lowercase();
    if lower.ends_with('j') {
        return Ok(Const::Unsupported(format!("complex literal {lit}")));
    }
    for (prefix, radix) in [("0x", 16), ("0o", 8), ("0b", 2)] {
        if let Some(rest) = lower.strip_prefix(prefix) {
            return parse_int_digits(rest, radix, lit);
        }
    }
    if lower.contains('.') || lower.contains('e') {
        let b = lower.as_bytes();
        for (i, &c) in b.iter().enumerate() {
            if c == b'_' {
                let ok = i > 0 && b[i - 1].is_ascii_digit() && b.get(i + 1).is_some_and(u8::is_ascii_digit);
                if !ok {
                    return Err(syntax(format!("invalid decimal literal {lit}")));
                }
            }
        }
        let cleaned: String = lower.chars().filter(|&c| c != '_').collect();
        if !decimal_float_grammar(&cleaned) {
            return Err(syntax(format!("invalid decimal literal {lit}")));
        }
        return cleaned
            .parse::<f64>()
            .map(|v| Const::Value(PyValue::Float(v)))
            .map_err(|_| syntax(format!("invalid decimal literal {lit}")));
    }
    parse_int_digits(&lower, 10, lit)
}

/// The value of a non-raw, non-bytes string literal body (Python escape sequences).
fn unescape(body: &str) -> Result<String, String> {
    let mut out = String::new();
    let mut it = body.chars().peekable();
    while let Some(c) = it.next() {
        if c != '\\' {
            out.push(c);
            continue;
        }
        let Some(e) = it.next() else { return Err("trailing backslash".into()) };
        match e {
            '\n' => {}
            '\\' | '\'' | '"' => out.push(e),
            'a' => out.push('\x07'),
            'b' => out.push('\x08'),
            'f' => out.push('\x0c'),
            'n' => out.push('\n'),
            'r' => out.push('\r'),
            't' => out.push('\t'),
            'v' => out.push('\x0b'),
            '0'..='7' => {
                let mut v = e.to_digit(8).unwrap_or(0);
                for _ in 0..2 {
                    match it.peek().and_then(|d| d.to_digit(8)) {
                        Some(d) => {
                            v = v * 8 + d;
                            it.next();
                        }
                        None => break,
                    }
                }
                out.push(char::from_u32(v).ok_or("octal escape out of range")?);
            }
            'x' | 'u' | 'U' => {
                let n = match e {
                    'x' => 2,
                    'u' => 4,
                    _ => 8,
                };
                let hex: String = (0..n).filter_map(|_| it.next()).collect();
                let v = u32::from_str_radix(&hex, 16).ok().filter(|_| hex.len() == n).ok_or("truncated escape")?;
                out.push(char::from_u32(v).ok_or("escape out of range")?);
            }
            'N' => return Err("\\N{...} escape".into()),
            other => {
                out.push('\\');
                out.push(other);
            }
        }
    }
    Ok(out)
}

fn string_value(prefix: &str, literal: &str) -> Result<String, String> {
    let q = &literal[..1];
    let triple = literal.len() >= 6 && literal.starts_with(&q.repeat(3));
    let body = if triple { &literal[3..literal.len() - 3] } else { &literal[1..literal.len() - 1] };
    if prefix.contains('r') {
        Ok(body.to_string())
    } else {
        unescape(body)
    }
}

fn classify_const(nodes: &[Node]) -> Py<Const> {
    let nodes = strip_parens(nodes);
    match nodes {
        [Node::Num(lit)] => parse_number(lit),
        [Node::Name(w)] => Ok(match w.as_str() {
            "True" => Const::Value(PyValue::Bool(true)),
            "False" => Const::Value(PyValue::Bool(false)),
            "None" => Const::Value(PyValue::None),
            _ => Const::Not,
        }),
        [Node::Op(o)] if o == "..." => Ok(Const::Unsupported("Ellipsis constant".into())),
        [] => Ok(Const::Not),
        _ if nodes.iter().all(|n| matches!(n, Node::Str { .. })) => {
            let prefixes: Vec<&str> =
                nodes.iter().map(|n| if let Node::Str { prefix, .. } = n { prefix.as_str() } else { "" }).collect();
            if prefixes.iter().any(|p| p.contains('f')) {
                return Ok(Const::Not);
            }
            let bytes = prefixes.iter().filter(|p| p.contains('b')).count();
            if bytes > 0 && bytes < prefixes.len() {
                return Err(syntax("cannot mix bytes and nonbytes literals"));
            }
            if bytes > 0 {
                return Ok(Const::Unsupported("bytes constant".into()));
            }
            let mut out = String::new();
            for n in nodes {
                if let Node::Str { prefix, literal } = n {
                    match string_value(prefix, literal) {
                        Ok(v) => out.push_str(&v),
                        Err(e) => return Ok(Const::Unsupported(e)),
                    }
                }
            }
            Ok(Const::Value(PyValue::Str(out)))
        }
        _ => Ok(Const::Not),
    }
}

const BINOPS: [(&str, u8); 13] = [
    ("|", 1),
    ("^", 2),
    ("&", 3),
    ("<<", 4),
    (">>", 4),
    ("+", 5),
    ("-", 5),
    ("*", 6),
    ("@", 6),
    ("/", 6),
    ("//", 6),
    ("%", 6),
    ("**", 8),
];
const LOWER: [&str; 13] =
    ["lambda", "if", "else", "or", "and", "not", "in", "is", "for", "async", "await", "yield", "from"];

/// Index of the root operator if the expression is a BinOp (Python precedence; `**` right-associative, unary
/// operators between `*` and `**`).
fn binop_root(nodes: &[Node]) -> Option<usize> {
    let mut ops: Vec<(usize, u8)> = Vec::new();
    let mut expect_operand = true;
    let mut i = 0;
    while i < nodes.len() {
        match &nodes[i] {
            Node::Op(o) if expect_operand && (o == "+" || o == "-" || o == "~") => i += 1,
            Node::Op(o) if !expect_operand => {
                let level = BINOPS.iter().find(|(b, _)| b == o)?.1;
                ops.push((i, level));
                expect_operand = true;
                i += 1;
            }
            Node::Name(w) if LOWER.contains(&w.as_str()) => return None,
            Node::Name(_) | Node::Num(_) | Node::Str { .. } | Node::Group(..) if expect_operand => {
                let string = matches!(nodes[i], Node::Str { .. });
                i += 1;
                while string && matches!(nodes.get(i), Some(Node::Str { .. })) {
                    i += 1;
                }
                loop {
                    match (nodes.get(i), nodes.get(i + 1)) {
                        (Some(Node::Op(o)), Some(Node::Name(_))) if o == "." => i += 2,
                        (Some(Node::Group('(', _)), _) | (Some(Node::Group('[', _)), _) => i += 1,
                        _ => break,
                    }
                }
                expect_operand = false;
            }
            _ => return None,
        }
    }
    if expect_operand {
        return None;
    }
    let min = ops.iter().map(|(_, l)| *l).min()?;
    if min == 8 {
        if matches!(&nodes[0], Node::Op(o) if o == "+" || o == "-" || o == "~") {
            return None;
        }
        return ops.iter().find(|(_, l)| *l == 8).map(|(i, _)| *i);
    }
    ops.iter().rev().find(|(_, l)| *l == min).map(|(i, _)| *i)
}

/// `isinstance(v, ast.BinOp) and isinstance(v.left, ast.Constant)` -> the left constant.
fn binop_const_left(nodes: &[Node]) -> Py<Option<Const>> {
    let nodes = strip_parens(nodes);
    match binop_root(nodes) {
        Some(root) => classify_const(&nodes[..root]).map(Some),
        None => Ok(None),
    }
}

const HARD_KEYWORDS: [&str; 22] = [
    "def", "class", "if", "elif", "else", "for", "while", "with", "try", "except", "finally", "import", "from",
    "return", "pass", "break", "continue", "raise", "global", "nonlocal", "del", "assert",
];

enum Stmt<'a> {
    /// `target = value` with one target.
    Assign {
        target: &'a [Node],
        value: &'a [Node],
    },
    /// `target: annotation = value`.
    AnnAssign {
        target: &'a [Node],
        value: Option<&'a [Node]>,
    },
    Other,
}

fn classify_stmt(nodes: &[Node]) -> Stmt<'_> {
    match nodes.first() {
        None => return Stmt::Other,
        Some(Node::Name(w)) if HARD_KEYWORDS.contains(&w.as_str()) || w == "async" => return Stmt::Other,
        Some(Node::Op(o)) if o == "@" => return Stmt::Other,
        _ => {}
    }
    let parts = split_on(nodes, "=");
    let lhs = parts[0];
    let colon = lhs.iter().position(|n| is_op(n, ":"));
    match (parts.len(), colon) {
        (1, Some(c)) => Stmt::AnnAssign { target: &lhs[..c], value: None },
        (2, Some(c)) => Stmt::AnnAssign { target: &lhs[..c], value: Some(parts[1]) },
        (2, None) => Stmt::Assign { target: lhs, value: parts[1] },
        _ => Stmt::Other,
    }
}

fn single_name(nodes: &[Node]) -> Option<&str> {
    match nodes {
        [Node::Name(w)] if !HARD_KEYWORDS.contains(&w.as_str()) => Some(w.as_str()),
        _ => None,
    }
}

fn statements(text: &str) -> Py<Vec<Vec<Node>>> {
    Ok(split_on(&lex(text)?, ";").into_iter().filter(|s| !s.is_empty()).map(<[Node]>::to_vec).collect())
}

fn unsupported(file: &str, detail: impl Into<String>) -> Raised {
    Raised::UnsupportedSyntax { file: file.to_string(), detail: detail.into() }
}

fn dict_entries(value: &[Node], template: &str, file: &str, out: &mut BTreeMap<String, PyValue>) -> Py<()> {
    let [Node::Group('{', inner)] = strip_parens(value) else { return Ok(()) };
    if inner.iter().any(|n| is_name(n, "for")) {
        return Ok(());
    }
    let entries: Vec<&[Node]> = split_on(inner, ",").into_iter().filter(|e| !e.is_empty()).collect();
    if entries.iter().any(|e| !is_op(&e[0], "**") && !e.iter().any(|n| is_op(n, ":"))) {
        return Ok(()); // a set display
    }
    for e in entries {
        let (key, val): (Option<&[Node]>, &[Node]) = if is_op(&e[0], "**") {
            (None, &e[1..])
        } else {
            let c = e.iter().position(|n| is_op(n, ":")).unwrap_or(0);
            (Some(&e[..c]), &e[c + 1..])
        };
        let left = match binop_const_left(val)? {
            Some(Const::Value(v)) => v,
            Some(Const::Unsupported(d)) => return Err(unsupported(file, d)),
            Some(Const::Not) | None => continue,
        };
        let Some(key) = key else {
            return Err(Raised::type_error("'NoneType' object has no attribute 'value'"));
        };
        let key = match classify_const(key)? {
            Const::Value(PyValue::Str(s)) => s,
            Const::Value(other) => other.py_str(),
            Const::Unsupported(d) => return Err(unsupported(file, d)),
            Const::Not => return Err(unsupported(file, "non-literal dict key")),
        };
        out.insert(template.replace("{key}", &key), left);
    }
    Ok(())
}

/// Extract the values the rules name. Keys: the assigned names, `dict template` keys and `class template` keys.
pub fn extract(source: &str, rules: &LiteralRules, file: &str) -> Py<BTreeMap<String, PyValue>> {
    let lines = logical_lines(source)?;
    let mut out = BTreeMap::new();
    let mut i = 0;
    while i < lines.len() {
        if lines[i].indent > 0 {
            i += 1;
            continue;
        }
        for st in statements(&lines[i].text)? {
            if is_name(&st[0], "class") {
                let Some(Node::Name(class)) = st.get(1) else { return Err(syntax("invalid class statement")) };
                let Some((target_class, template)) = &rules.class_annassign else { continue };
                if class != target_class {
                    continue;
                }
                let colon = st.iter().position(|n| is_op(n, ":")).ok_or_else(|| syntax("expected ':'"))?;
                if colon + 1 < st.len() {
                    return Err(unsupported(file, "one-line class body"));
                }
                class_body(&lines, i + 1, template, file, &mut out)?;
                continue;
            }
            if let Stmt::Assign { target, value } = classify_stmt(&st) {
                let Some(name) = single_name(target) else { continue };
                if rules.assign_names.iter().any(|n| n == name) {
                    match classify_const(value)? {
                        Const::Value(v) => {
                            out.insert(name.to_string(), v);
                        }
                        Const::Unsupported(d) => return Err(unsupported(file, d)),
                        Const::Not => {}
                    }
                }
                if let Some((dict_name, template)) = &rules.dict_binop_left {
                    if dict_name == name {
                        dict_entries(value, template, file, &mut out)?;
                    }
                }
            }
        }
        i += 1;
    }
    Ok(out)
}

fn class_body(lines: &[Line], start: usize, template: &str, file: &str, out: &mut BTreeMap<String, PyValue>) -> Py<()> {
    let Some(body_indent) = lines.get(start).map(|l| l.indent).filter(|&n| n > 0) else {
        return Err(syntax("expected an indented block"));
    };
    for line in lines[start..].iter().take_while(|l| l.indent > 0) {
        if line.indent > body_indent {
            continue;
        }
        if line.indent < body_indent {
            return Err(Raised::Other {
                name: "IndentationError".into(),
                detail: "unindent does not match any outer indentation level".into(),
            });
        }
        for st in statements(&line.text)? {
            if let Stmt::AnnAssign { target, value: Some(value) } = classify_stmt(&st) {
                let v = match classify_const(value)? {
                    Const::Value(v) => v,
                    Const::Unsupported(d) => return Err(unsupported(file, d)),
                    Const::Not => continue,
                };
                let Some(field) = single_name(target) else {
                    return Err(Raised::type_error("annotated target has no attribute 'id'"));
                };
                out.insert(template.replace("{field}", field), v);
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rules() -> LiteralRules {
        LiteralRules {
            assign_names: vec!["K_B".into(), "AMU".into()],
            dict_binop_left: Some(("M_SPECIES".into(), "M_{key}_u".into())),
            class_annassign: Some(("RFPConstraints".into(), "RFP.{field}".into())),
        }
    }

    fn run(src: &str) -> Py<BTreeMap<String, PyValue>> {
        extract(src, &rules(), "c.py")
    }

    const BASE: &str = r#""""Doc: K_B = 5 inside a docstring is not an assignment."""
from dataclasses import dataclass, field

G0 = 9.80665          # m/s^2
AMU = 1.66053906660e-27
K_B = 1.380649e-23

M_SPECIES = {
    "O":  16.0 * AMU,
    "N2": 28.0 * AMU,
    "Xe": 131.3 * AMU,
}


@dataclass(frozen=True)
class RFPConstraints:
    """Hard limits."""
    thrust_min_mN: float = 12.0
    ignition_hours: float = 15000.0       # ">15,000 h"
    ic_subsystem_min: dict = field(default_factory=lambda: {
        "thruster": 0.80, "intake": 0.80})
    hall_preferred: bool = True


RFP = RFPConstraints()
"#;

    #[test]
    fn reads_the_registered_forms() {
        let m = run(BASE).unwrap();
        assert_eq!(m["K_B"], PyValue::Float(1.380649e-23));
        assert_eq!(m["AMU"], PyValue::Float(1.66053906660e-27));
        assert_eq!(m["M_N2_u"], PyValue::Float(28.0));
        assert_eq!(m["M_Xe_u"], PyValue::Float(131.3));
        assert_eq!(m["RFP.thrust_min_mN"], PyValue::Float(12.0));
        assert_eq!(m["RFP.ignition_hours"], PyValue::Float(15000.0));
        assert_eq!(m["RFP.hall_preferred"], PyValue::Bool(true));
        assert!(!m.contains_key("RFP.ic_subsystem_min"));
        assert!(!m.contains_key("G0"));
        assert_eq!(m.len(), 8);
    }

    #[test]
    fn constant_rules_follow_the_ast() {
        let m = run("K_B = (1.380649e-23)\nAMU = 1.660_539_066_60e-27\n").unwrap();
        assert_eq!(m["K_B"], PyValue::Float(1.380649e-23));
        assert_eq!(m["AMU"], PyValue::Float(1.66053906660e-27));
        for not_constant in [
            "K_B = -1.0",
            "K_B = float(1.0)",
            "K_B = 1.0 + 0",
            "K_B = AMU",
            "K_B = (1.0,)",
            "K_B: float = 1.0",
            "K_B = AMU = 1.0",
        ] {
            assert!(!run(not_constant).unwrap().contains_key("K_B"), "{not_constant}");
        }
        assert_eq!(run("K_B = 1.0\nK_B = 2.0\nK_B = x\n").unwrap()["K_B"], PyValue::Float(2.0));
        assert_eq!(run("K_B = 'a' \"b\"").unwrap()["K_B"], PyValue::str("ab"));
        assert_eq!(run("x = 1; K_B = 0x10").unwrap()["K_B"], PyValue::Int(16));
        assert!(matches!(run("K_B = 1j"), Err(Raised::UnsupportedSyntax { .. })));
        assert!(matches!(run("K_B = 012"), Err(Raised::Other { .. })));
        assert!(matches!(run("K_B = \"open"), Err(Raised::Other { .. })));
        assert!(matches!(run("K_B = (1.0"), Err(Raised::Other { .. })));
    }

    #[test]
    fn binop_left_operand_follows_precedence() {
        let m = run(concat!(
            "M_SPECIES = {\"a\": 2.0 * AMU, \"b\": AMU * 2.0, \"c\": 2.0 * AMU + 1, \"d\": 1 + 2.0 * AMU, ",
            "\"e\": -2.0 * AMU, \"f\": 2 ** -AMU, \"g\": -2 ** AMU, \"h\": (3.0 * AMU), \"i\": (3.0) / AMU, **other}"
        ))
        .unwrap();
        assert_eq!(m.get("M_a_u"), Some(&PyValue::Float(2.0)));
        assert_eq!(m.get("M_b_u"), None);
        assert_eq!(m.get("M_c_u"), None);
        assert_eq!(m.get("M_d_u"), Some(&PyValue::Int(1)));
        assert_eq!(m.get("M_e_u"), None);
        assert_eq!(m.get("M_f_u"), Some(&PyValue::Int(2)));
        assert_eq!(m.get("M_g_u"), None);
        assert_eq!(m.get("M_h_u"), Some(&PyValue::Float(3.0)));
        assert_eq!(m.get("M_i_u"), Some(&PyValue::Float(3.0)));
        assert!(run("M_SPECIES = {k: 2.0 * AMU for k in x}").unwrap().is_empty());
        assert!(run("M_SPECIES = dict(a=2.0 * AMU)").unwrap().is_empty());
        assert!(matches!(run("M_SPECIES = {name: 2.0 * AMU}"), Err(Raised::UnsupportedSyntax { .. })));
    }

    #[test]
    fn only_direct_class_body_annotations_count() {
        let src = "class RFPConstraints:\n    a: float = 1.0\n    def f(self):\n        b: float = 2.0\n    c: float = float(3)\n    self.d: int = 4\n";
        assert!(matches!(run(src), Err(Raised::Type { .. })));
        let src = "class RFPConstraints:\n    a: float = 1.0\n    def f(self):\n        b: float = 2.0\n    c: float = float(3)\n    e: int\nclass Other:\n    z: int = 1\n";
        let m = run(src).unwrap();
        assert_eq!(m.len(), 1);
        assert_eq!(m["RFP.a"], PyValue::Float(1.0));
        assert!(matches!(
            run("class RFPConstraints:\n        a: int = 1\n    b: int = 2\n"),
            Err(Raised::Other { .. })
        ));
    }
}

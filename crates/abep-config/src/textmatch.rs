//! A small backtracking matcher with the semantics of CPython's `re` for str patterns, for the handful of fixed
//! patterns the configuration rules use (`re.search` / `re.sub`).
//!
//! Character classes follow the reference interpreter: `\s` is `str.isspace()`, `\b` uses the `re` word characters
//! (`str.isalnum()` or `_`, [`abep_types::pyjson::py_isword`]), and an IGNORECASE letter matches a character whose
//! simple lower-case mapping is that letter (plus sre's fixes `i` ~ U+0131 and `s` ~ U+017F). Quantifiers are greedy
//! and backtrack; the leftmost match wins, as in sre.

use abep_types::pyjson::{py_isspace, py_isword};

/// One pattern element.
pub enum Node {
    /// A literal character (case-sensitive).
    Char(char),
    /// A lower-case ASCII letter under IGNORECASE.
    CharI(char),
    /// A character predicate (`\s`, `[^...]`, `\d`).
    Class(fn(char) -> bool),
    /// `^` (start of text).
    Bol,
    /// `$` (end of text, or before a final newline).
    Eol,
    /// `\b`.
    WordBoundary,
    /// Greedy repetition `{min,max}` (`usize::MAX` = unbounded).
    Rep(Box<Node>, usize, usize),
    Seq(Vec<Node>),
    Alt(Vec<Node>),
}

/// Unicode simple lower-case mapping (`_PyUnicode_ToLowercase`).
pub fn simple_lower(c: char) -> char {
    if c == '\u{130}' {
        return 'i';
    }
    let mut it = c.to_lowercase();
    match (it.next(), it.next()) {
        (Some(l), None) => l,
        _ => c,
    }
}

fn char_i(letter: char, c: char) -> bool {
    let l = simple_lower(c);
    l == letter || (letter == 'i' && l == '\u{131}') || (letter == 's' && l == '\u{17f}')
}

/// A literal string as a node sequence.
pub fn lit(s: &str) -> Vec<Node> {
    s.chars().map(Node::Char).collect()
}

/// A literal string under IGNORECASE (lower-case letters; other characters literal).
pub fn lit_i(s: &str) -> Vec<Node> {
    s.chars().map(|c| if c.is_ascii_lowercase() { Node::CharI(c) } else { Node::Char(c) }).collect()
}

pub fn opt(n: Node) -> Node {
    Node::Rep(Box::new(n), 0, 1)
}

pub fn plus(n: Node) -> Node {
    Node::Rep(Box::new(n), 1, usize::MAX)
}

pub fn star(n: Node) -> Node {
    Node::Rep(Box::new(n), 0, usize::MAX)
}

pub fn space() -> Node {
    Node::Class(py_isspace)
}

fn word_at(t: &[char], i: usize) -> bool {
    i < t.len() && py_isword(t[i])
}

type Cont<'k> = &'k mut dyn FnMut(usize) -> bool;

fn m(nodes: &[Node], t: &[char], pos: usize, k: Cont<'_>) -> bool {
    let Some((first, rest)) = nodes.split_first() else {
        return k(pos);
    };
    match first {
        Node::Char(c) => pos < t.len() && t[pos] == *c && m(rest, t, pos + 1, k),
        Node::CharI(c) => pos < t.len() && char_i(*c, t[pos]) && m(rest, t, pos + 1, k),
        Node::Class(f) => pos < t.len() && f(t[pos]) && m(rest, t, pos + 1, k),
        Node::Bol => pos == 0 && m(rest, t, pos, k),
        Node::Eol => (pos == t.len() || (pos + 1 == t.len() && t[pos] == '\n')) && m(rest, t, pos, k),
        Node::WordBoundary => {
            let before = pos > 0 && py_isword(t[pos - 1]);
            !t.is_empty() && before != word_at(t, pos) && m(rest, t, pos, k)
        }
        Node::Seq(v) => m(v, t, pos, &mut |p| m(rest, t, p, k)),
        Node::Alt(alts) => alts.iter().any(|a| m(std::slice::from_ref(a), t, pos, &mut |p| m(rest, t, p, k))),
        Node::Rep(n, min, max) => rep(n, *min, *max, 0, rest, t, pos, k),
    }
}

#[allow(clippy::too_many_arguments)]
fn rep(n: &Node, min: usize, max: usize, count: usize, rest: &[Node], t: &[char], pos: usize, k: Cont<'_>) -> bool {
    if count < max
        && m(std::slice::from_ref(n), t, pos, &mut |p| p != pos && rep(n, min, max, count + 1, rest, t, p, k))
    {
        return true;
    }
    count >= min && m(rest, t, pos, k)
}

/// `re.search`: the leftmost match as a (start, end) char-index span.
pub fn search(pattern: &[Node], t: &[char], from: usize) -> Option<(usize, usize)> {
    for start in from..=t.len() {
        let mut end = None;
        if m(pattern, t, start, &mut |p| {
            end = Some(p);
            true
        }) {
            return Some((start, end.expect("set on success")));
        }
    }
    None
}

/// `re.search(pattern, text) is not None`.
pub fn is_match(pattern: &[Node], text: &str) -> bool {
    let t: Vec<char> = text.chars().collect();
    search(pattern, &t, 0).is_some()
}

/// `re.sub(pattern, repl, text)` for patterns that never match the empty string.
pub fn sub(pattern: &[Node], repl: &str, text: &str) -> String {
    let t: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut pos = 0;
    while let Some((s, e)) = search(pattern, &t, pos) {
        debug_assert!(e > s, "patterns used with sub never match empty");
        out.extend(&t[pos..s]);
        out.push_str(repl);
        pos = e.max(s + 1);
    }
    out.extend(&t[pos..]);
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn seq(v: Vec<Node>) -> Vec<Node> {
        v
    }

    #[test]
    fn greedy_backtracking_and_boundaries() {
        // \bno\s+c-?1\b[^;,()\-]*
        let p = seq(vec![
            Node::WordBoundary,
            Node::CharI('n'),
            Node::CharI('o'),
            plus(space()),
            Node::CharI('c'),
            opt(Node::Char('-')),
            Node::Char('1'),
            Node::WordBoundary,
            star(Node::Class(|c| !";,()-".contains(c))),
        ]);
        let t: Vec<char> = "Hall PPU (NO C-1 electronics - x)".chars().collect();
        assert_eq!(search(&p, &t, 0), Some((10, 29)));
        assert!(!is_match(&p, "no c10"));
        assert!(!is_match(&p, "piano c1"));
        assert!(is_match(&p, "no\u{a0}c1"));
        assert!(is_match(&p, "no\u{1c}c1"));
        assert!(!is_match(&p, "no c1\u{b2}"));
        assert_eq!(sub(&p, " ", "a no c1 b; no c-1, c"), "a  ;  , c");
    }

    #[test]
    fn ignorecase_follows_sre() {
        let p = lit_i("is");
        assert!(is_match(&p, "\u{130}S") && is_match(&p, "\u{131}\u{17f}") && is_match(&p, "IS"));
        assert!(!is_match(&p, "\u{ff49}s"));
        let a = seq(vec![Node::Alt(vec![Node::Bol, Node::Char('_')]), Node::Char('k'), Node::Eol]);
        assert!(is_match(&a, "k") && is_match(&a, "x_k") && is_match(&a, "x_k\n") && !is_match(&a, "xk"));
    }
}

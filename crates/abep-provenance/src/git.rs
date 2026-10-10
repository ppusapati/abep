//! Minimal read-only git access through `std::process::Command` (history checks only; nothing here writes to a
//! repository). Repository discovery is pinned to the given directory: `GIT_DIR` / `GIT_WORK_TREE` /
//! `GIT_INDEX_FILE` from the caller's environment are removed.

use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};

/// One answer of `git cat-file --batch` / `--batch-check`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BatchItem {
    Missing,
    Object { oid: String, kind: String, content: Option<Vec<u8>> },
}

#[derive(Debug, Clone)]
pub struct Git {
    dir: PathBuf,
}

impl Git {
    pub fn new(dir: &Path) -> Self {
        Git { dir: dir.to_path_buf() }
    }

    fn command(&self) -> Command {
        let mut c = Command::new("git");
        c.arg("-C").arg(&self.dir);
        for v in
            ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"]
        {
            c.env_remove(v);
        }
        c
    }

    /// Run `git -C <dir> <args>` and return its output (spawn failures are `Err`).
    pub fn output(&self, args: &[&str]) -> Result<Output, String> {
        self.command().args(args).output().map_err(|e| format!("cannot run git: {e}"))
    }

    /// stdout of a successful command, trimmed; `Err` with stderr otherwise.
    pub fn stdout(&self, args: &[&str]) -> Result<String, String> {
        let o = self.output(args)?;
        if !o.status.success() {
            return Err(format!("git {} failed: {}", args.join(" "), String::from_utf8_lossy(&o.stderr).trim()));
        }
        Ok(String::from_utf8_lossy(&o.stdout).trim().to_string())
    }

    /// `git merge-base --is-ancestor a b`: Ok(true / false), Err on any other exit status.
    pub fn is_ancestor(&self, a: &str, b: &str) -> Result<bool, String> {
        let o = self.output(&["merge-base", "--is-ancestor", a, b])?;
        match o.status.code() {
            Some(0) => Ok(true),
            Some(1) => Ok(false),
            _ => Err(format!("git merge-base --is-ancestor {a} {b}: {}", String::from_utf8_lossy(&o.stderr).trim())),
        }
    }

    /// `git ls-tree -r -z --full-tree <rev> <path>`: (path, object id) of every blob below `path`.
    pub fn ls_tree(&self, rev: &str, path: &str) -> Result<Vec<(String, String)>, String> {
        let o = self.output(&["ls-tree", "-r", "-z", "--full-tree", rev, path])?;
        if !o.status.success() {
            return Err(format!("git ls-tree {rev} {path}: {}", String::from_utf8_lossy(&o.stderr).trim()));
        }
        let mut out = Vec::new();
        for rec in o.stdout.split(|b| *b == 0).filter(|r| !r.is_empty()) {
            let rec = String::from_utf8_lossy(rec);
            let (meta, name) = rec.split_once('\t').ok_or_else(|| format!("unparsable ls-tree record {rec:?}"))?;
            let oid = meta.split(' ').nth(2).ok_or_else(|| format!("unparsable ls-tree record {rec:?}"))?;
            out.push((name.to_string(), oid.to_string()));
        }
        Ok(out)
    }

    /// `git cat-file --batch` (with contents) or `--batch-check` (headers only) for every request, in order.
    pub fn cat_file(&self, requests: &[String], with_content: bool) -> Result<Vec<BatchItem>, String> {
        if requests.is_empty() {
            return Ok(Vec::new());
        }
        let mode = if with_content { "--batch" } else { "--batch-check" };
        let mut child = self
            .command()
            .args(["cat-file", mode])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("cannot run git: {e}"))?;
        let mut input = String::new();
        for r in requests {
            if r.contains('\n') {
                return Err(format!("request {r:?} contains a newline"));
            }
            input.push_str(r);
            input.push('\n');
        }
        let mut stdin = child.stdin.take().expect("piped stdin");
        let writer = std::thread::spawn(move || stdin.write_all(input.as_bytes()));
        let mut raw = Vec::new();
        child.stdout.take().expect("piped stdout").read_to_end(&mut raw).map_err(|e| e.to_string())?;
        let status = child.wait().map_err(|e| e.to_string())?;
        writer.join().map_err(|_| "cat-file writer panicked".to_string())?.map_err(|e| e.to_string())?;
        if !status.success() {
            return Err(format!("git cat-file {mode} exited with {status}"));
        }
        parse_batch(&raw, requests.len(), with_content)
    }
}

fn parse_batch(raw: &[u8], n: usize, with_content: bool) -> Result<Vec<BatchItem>, String> {
    let mut out = Vec::with_capacity(n);
    let mut pos = 0;
    for _ in 0..n {
        let end = raw[pos..].iter().position(|b| *b == b'\n').ok_or("truncated cat-file output")? + pos;
        let header = String::from_utf8_lossy(&raw[pos..end]).to_string();
        pos = end + 1;
        if header.ends_with(" missing") || header.ends_with(" ambiguous") {
            out.push(BatchItem::Missing);
            continue;
        }
        let parts: Vec<&str> = header.split(' ').collect();
        if parts.len() != 3 {
            return Err(format!("unparsable cat-file header {header:?}"));
        }
        let size: usize = parts[2].parse().map_err(|_| format!("unparsable cat-file size in {header:?}"))?;
        let content = if with_content {
            if pos + size + 1 > raw.len() {
                return Err("truncated cat-file content".into());
            }
            let c = raw[pos..pos + size].to_vec();
            pos += size + 1;
            Some(c)
        } else {
            None
        };
        out.push(BatchItem::Object { oid: parts[0].to_string(), kind: parts[1].to_string(), content });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn batch_output_is_parsed_in_order() {
        let raw = b"aaaa blob 3\nabc\nx:y missing\nbbbb tree 0\n\n";
        let items = parse_batch(raw, 3, true).unwrap();
        assert_eq!(
            items[0],
            BatchItem::Object { oid: "aaaa".into(), kind: "blob".into(), content: Some(b"abc".to_vec()) }
        );
        assert_eq!(items[1], BatchItem::Missing);
        assert_eq!(items[2], BatchItem::Object { oid: "bbbb".into(), kind: "tree".into(), content: Some(Vec::new()) });
        assert!(parse_batch(b"aaaa blob 9\nabc\n", 1, true).is_err());
        let check = parse_batch(b"cccc commit 250\n", 1, false).unwrap();
        assert_eq!(check[0], BatchItem::Object { oid: "cccc".into(), kind: "commit".into(), content: None });
    }
}

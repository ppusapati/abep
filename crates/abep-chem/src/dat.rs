//! HallThruster.jl v0.23.1 rate tables (`hallthruster_bridge/propellants/PROVENANCE.md`): line 1
//! `<label> (eV): <threshold>` (HallThruster.jl reads the number after the colon only), line 2 a column header, then
//! `<mean energy 3/2 T_e [eV]> <rate coefficient [m^3/s]>` rows. Frozen tables are read only through a sha256 pin and
//! never written (CLAUDE.md rule 1).

use abep_provenance::read_verified;
use abep_types::{AbepError, AbepResult};
use std::path::Path;

/// A parsed rate table.
#[derive(Debug, Clone, PartialEq)]
pub struct DatTable {
    /// Header text before the colon (e.g. `Ionization energy (eV)`).
    pub label: String,
    /// The header number: threshold / energy loss [eV].
    pub threshold_ev: f64,
    pub column_header: String,
    /// `(mean energy [eV], k [m^3/s])`.
    pub rows: Vec<(f64, f64)>,
}

impl DatTable {
    /// Read `path`, verify its sha256 against `expected_sha256`, parse it.
    pub fn read_verified(path: &Path, expected_sha256: &str) -> AbepResult<Self> {
        let bytes = read_verified(path, expected_sha256)?;
        let origin = path.display().to_string();
        let text =
            String::from_utf8(bytes).map_err(|e| AbepError::Schema { path: origin.clone(), message: e.to_string() })?;
        Self::parse(&text, &origin)
    }

    /// Parse the text; `origin` names it in errors. Every row must hold exactly two finite numbers, mean energies
    /// strictly increasing.
    pub fn parse(text: &str, origin: &str) -> AbepResult<Self> {
        let schema = |message: String| AbepError::Schema { path: origin.to_string(), message };
        let mut lines = text.lines();
        let header = lines.next().ok_or_else(|| schema("empty table".into()))?;
        let (label, number) = header.rsplit_once(':').ok_or_else(|| schema(format!("header {header:?} has no ':'")))?;
        let threshold_ev: f64 =
            number.trim().parse().map_err(|_| schema(format!("header number {:?} is not a float", number.trim())))?;
        let column_header = lines.next().ok_or_else(|| schema("no column header".into()))?.to_string();
        let mut rows: Vec<(f64, f64)> = Vec::new();
        for (n, line) in lines.enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            let f: Vec<&str> = line.split_whitespace().collect();
            let parse = |s: &str| s.parse::<f64>().ok().filter(|v| v.is_finite());
            let (Some(e), Some(k), 2) = (f.first().and_then(|s| parse(s)), f.get(1).and_then(|s| parse(s)), f.len())
            else {
                return Err(schema(format!("row {}: {line:?} is not two finite numbers", n + 1)));
            };
            if rows.last().is_some_and(|&(prev, _)| e <= prev) {
                return Err(schema(format!("row {}: mean energy {e} does not increase", n + 1)));
            }
            rows.push((e, k));
        }
        if rows.is_empty() {
            return Err(schema("no rows".into()));
        }
        Ok(DatTable { label: label.trim_end().to_string(), threshold_ev, column_header, rows })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_the_writer_format() {
        let t = DatTable::parse(
            "Ionization energy (eV): 15.58\nEnergy (eV)\tRate coefficient (m^3/s)\n0.0\t0.000000e+00\n1.0\t1.234560e-20\n",
            "t",
        )
        .unwrap();
        assert_eq!(t.label, "Ionization energy (eV)");
        assert_eq!(t.threshold_ev, 15.58);
        assert_eq!(t.rows, vec![(0.0, 0.0), (1.0, 1.23456e-20)]);
    }

    #[test]
    fn malformed_tables_are_schema_errors() {
        for bad in ["", "no colon\nh\n0 1\n", "L: x\nh\n0 1\n", "L: 1\nh\n0 1 2\n", "L: 1\nh\n1 0\n0 1\n", "L: 1\nh\n"]
        {
            assert!(matches!(DatTable::parse(bad, "t"), Err(AbepError::Schema { .. })), "{bad:?}");
        }
    }
}

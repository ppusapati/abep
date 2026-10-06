//! `hallthruster_bridge/propellants/rate_validity.toml`: the validity domain of each rate table (CLAUDE.md next-work
//! 5). Each `["file.dat"]` table has `status = "verified"` with `max_mean_energy_eV`, or `status = "unresolved"`; a
//! file without an entry is [`Validity::MissingEntry`] (a model error when used, never a default). The file is read
//! only through a sha256 pin.

use crate::checked::Validity;
use abep_provenance::read_verified;
use abep_types::{AbepError, AbepResult};
use std::collections::BTreeMap;
use std::path::Path;

/// The parsed validity table.
#[derive(Debug, Clone, PartialEq)]
pub struct RateValidityTable {
    entries: BTreeMap<String, Validity>,
}

impl RateValidityTable {
    /// Read `path`, verify its sha256 against `expected_sha256`, parse it.
    pub fn load(path: &Path, expected_sha256: &str) -> AbepResult<Self> {
        let bytes = read_verified(path, expected_sha256)?;
        let origin = path.display().to_string();
        let text =
            String::from_utf8(bytes).map_err(|e| AbepError::Schema { path: origin.clone(), message: e.to_string() })?;
        Self::parse(&text, &origin)
    }

    /// Parse the TOML text; `origin` names it in errors. Unknown statuses and verified entries without a positive
    /// finite limit are schema errors.
    pub fn parse(text: &str, origin: &str) -> AbepResult<Self> {
        let schema = |message: String| AbepError::Schema { path: origin.to_string(), message };
        let table: toml::Table = text.parse().map_err(|e: toml::de::Error| schema(e.to_string()))?;
        let mut entries = BTreeMap::new();
        for (file, entry) in table {
            let entry = entry.as_table().ok_or_else(|| schema(format!("{file}: entry is not a table")))?;
            let status =
                entry.get("status").and_then(|v| v.as_str()).ok_or_else(|| schema(format!("{file}: no status")))?;
            let validity = match status {
                "verified" => {
                    let limit = entry
                        .get("max_mean_energy_eV")
                        .and_then(|v| v.as_float().or_else(|| v.as_integer().map(|i| i as f64)))
                        .ok_or_else(|| schema(format!("{file}: verified without max_mean_energy_eV")))?;
                    if !(limit.is_finite() && limit > 0.0) {
                        return Err(schema(format!("{file}: max_mean_energy_eV {limit} is not finite and > 0")));
                    }
                    Validity::Verified { max_mean_energy_ev: limit }
                }
                "unresolved" => Validity::Unresolved,
                other => return Err(schema(format!("{file}: unknown status {other:?}"))),
            };
            entries.insert(file, validity);
        }
        Ok(RateValidityTable { entries })
    }

    /// The entry of a rate file (by file name, e.g. `dissociation_N2.dat`); `MissingEntry` when absent.
    pub fn validity(&self, file: &str) -> Validity {
        self.entries.get(file).cloned().unwrap_or(Validity::MissingEntry)
    }

    pub fn files(&self) -> impl Iterator<Item = &str> {
        self.entries.keys().map(String::as_str)
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn statuses_limits_and_missing_entries() {
        let t = RateValidityTable::parse(
            "[\"a.dat\"]\nstatus = \"verified\"\nmax_mean_energy_eV = 45.0\n[\"b.dat\"]\nstatus = \"unresolved\"\n",
            "test",
        )
        .unwrap();
        assert_eq!(t.validity("a.dat"), Validity::Verified { max_mean_energy_ev: 45.0 });
        assert_eq!(t.validity("b.dat"), Validity::Unresolved);
        assert_eq!(t.validity("c.dat"), Validity::MissingEntry);
        for bad in [
            "[\"a.dat\"]\nstatus = \"verified\"\n",
            "[\"a.dat\"]\nstatus = \"checked\"\n",
            "[\"a.dat\"]\nmax_mean_energy_eV = 45.0\n",
            "[\"a.dat\"]\nstatus = \"verified\"\nmax_mean_energy_eV = -1.0\n",
        ] {
            assert!(matches!(RateValidityTable::parse(bad, "test"), Err(AbepError::Schema { .. })), "{bad}");
        }
    }
}

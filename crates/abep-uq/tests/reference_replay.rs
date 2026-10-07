//! CI replay of the captured numpy 2.4.4 stream samples (PARITY-C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY-V1
//! reference_outputs): the registered design / UQ stream stays EXACT_STREAM after Python is retired.

use abep_rng::{decimal_to_u32_words, Generator, Pcg64, SeedSequence};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::io::Read;

fn captured() -> Value {
    let repo = abep_provenance::workspace_repo_root().expect("repository root");
    let p = repo.join(
        "docs/rust_migration/contracts/C-ABEP_SIM_DESIGN_ROBUST_OPTIMIZER_PY/reference_outputs/numpy_streams_v1.json.gz",
    );
    let gz = std::fs::read(&p).expect("captured numpy stream samples");
    let mut s = String::new();
    flate2::read::GzDecoder::new(&gz[..]).read_to_string(&mut s).expect("gzip");
    serde_json::from_str(&s).expect("json")
}

#[test]
fn numpy_streams_replay_bit_for_bit() {
    let c = captured();
    assert_eq!(c["numpy"], "2.4.4");
    let streams = c["streams"].as_array().expect("streams");
    assert!(streams.len() >= 8);
    for st in streams {
        let words = decimal_to_u32_words(st["seed"].as_str().unwrap()).unwrap();
        let ss = SeedSequence::from_words(&words);
        let pool: Vec<u64> = st["pool"].as_array().unwrap().iter().map(|x| x.as_u64().unwrap()).collect();
        assert_eq!(ss.pool().iter().map(|x| u64::from(*x)).collect::<Vec<_>>(), pool);
        let mut raw = Pcg64::from_seed_sequence(&ss);
        for w in st["next_uint64"].as_array().unwrap() {
            assert_eq!(raw.next_u64().to_string(), w.as_str().unwrap());
        }
        let n = st["n_normal"].as_u64().unwrap() as usize;
        let z = Generator::from_entropy_words(&words).standard_normal_fill(n);
        let mut h = Sha256::new();
        for x in &z {
            h.update(x.to_le_bytes());
        }
        assert_eq!(format!("{:x}", h.finalize()), st["normal_sha256"].as_str().unwrap());
        for (x, y) in z.iter().zip(st["normal_head"].as_array().unwrap()) {
            assert_eq!(x.to_bits(), y.as_f64().unwrap().to_bits());
        }
    }
}

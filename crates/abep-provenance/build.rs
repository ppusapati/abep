//! Records the compiler that builds this crate, for the run-record toolchain field (RM-R10).

use std::process::Command;

fn main() {
    let rustc = std::env::var("RUSTC").unwrap_or_else(|_| "rustc".into());
    let version = Command::new(rustc)
        .arg("--version")
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_default();
    println!("cargo:rustc-env=ABEP_RUSTC_VERSION={version}");
    println!("cargo:rerun-if-env-changed=RUSTC");
    println!("cargo:rerun-if-changed=build.rs");
}

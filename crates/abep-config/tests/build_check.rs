//! `abep-config build --check` reproduces config/** and MANIFEST.json byte for byte (W13); the frozen scenarios are
//! verified, never generated; a stale or unlisted file fails the check.

mod common;

use abep_config::builder::Builder;

#[test]
fn build_reproduces_every_config_file_byte_for_byte() {
    let root = common::repo();
    let b = Builder::new(&root);
    let files = b.build_all().expect("build");
    let names: Vec<&str> = files.iter().map(|(k, _)| k.as_str()).collect();
    assert_eq!(names.len(), 12);
    assert_eq!(names.last(), Some(&"MANIFEST.json"));
    for (rel, bytes) in &files {
        let committed = std::fs::read(root.join("config").join(rel)).unwrap();
        assert!(committed == *bytes, "config/{rel} differs from the Rust build");
    }
    assert_eq!(b.build_all().unwrap(), files, "deterministic");
    let c = b.check().unwrap();
    assert_eq!((c.exit, c.line.as_str()), (0, "OK: 12 config files current"));
}

#[test]
fn stale_unlisted_and_frozen_scenario_changes_fail() {
    let repo = common::repo();
    // a scratch repository: symlinks to the real tree, with a real copy of config/
    let farm = common::scratch("farm");
    for e in std::fs::read_dir(&repo).unwrap() {
        let e = e.unwrap();
        let name = e.file_name();
        if name == "config" || name == "target" || name == ".git" {
            continue;
        }
        std::os::unix::fs::symlink(e.path(), farm.join(&name)).unwrap();
    }
    common::copy_dir(&repo.join("config"), &farm.join("config"));
    let b = Builder::new(&farm);
    assert_eq!(b.check().unwrap().exit, 0);

    std::fs::create_dir_all(farm.join("config/extra")).unwrap();
    std::fs::write(farm.join("config/extra/unlisted.json"), "{}\n").unwrap();
    let c = b.check().unwrap();
    assert_eq!((c.exit, c.line.as_str()), (1, "STALE: []; unlisted files: ['extra/unlisted.json']"));
    std::fs::remove_dir_all(farm.join("config/extra")).unwrap();

    let arch = farm.join("config/architecture/hall_icp_neutralizer_v1.json");
    let orig = std::fs::read(&arch).unwrap();
    std::fs::write(&arch, [&orig[..orig.len() - 1], b" \n"].concat()).unwrap();
    let c = b.check().unwrap();
    assert_eq!(
        (c.exit, c.line.as_str()),
        (1, "STALE: ['architecture/hall_icp_neutralizer_v1.json']; unlisted files: []")
    );
    std::fs::write(&arch, &orig).unwrap();

    let ms = farm.join("config/mission/mission_scenario_v2.json");
    let orig = std::fs::read(&ms).unwrap();
    std::fs::write(&ms, [&orig[..], b" "].concat()).unwrap();
    let e = b.check().unwrap_err();
    assert_eq!(e.class, "BuildError");
    assert!(e.message.starts_with("config/mission/mission_scenario_v2.json sha256 "), "{}", e.message);
    assert!(e.message.ends_with("needs a new scenario version (A9.24 item 4)"));
    assert_eq!(e.status(), abep_types::EvalStatus::ModelError);
}

#[test]
fn version_labels_of_every_physics_module_match_the_model_set() {
    use abep_types::pyjson::{loads, Value};
    let root = common::repo();
    let ms = loads(&std::fs::read_to_string(root.join("config/model_set/physics_model_set_v1.json")).unwrap()).unwrap();
    let modules = ms.as_dict().unwrap().get("modules").unwrap().as_list().unwrap();
    assert!(modules.len() > 50);
    for m in modules {
        let d = m.as_dict().unwrap();
        let path = d.get("path").unwrap().as_str().unwrap();
        let src = std::fs::read_to_string(root.join(path)).unwrap();
        let got = abep_config::pysrc::version_labels(&src).unwrap();
        assert_eq!(&Value::Dict(got), d.get("version_labels").unwrap(), "{path}");
    }
}

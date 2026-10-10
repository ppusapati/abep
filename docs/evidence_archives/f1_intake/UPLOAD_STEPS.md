# F1 evidence archive: upload steps (owner, manual)

Authority: owner decision A9.24 item 11
(`docs/decisions/OD_2026_10_04_A9_24_RUST_MIGRATION_AND_OPEN_ITEMS_OWNER_DECISIONS.md`): "AUTHORIZED TO KEEP AND
UPLOAD." The archive is never committed as an ordinary Git blob (`.gitignore` ignores `docs/evidence_archives/**/*.tar.zst`).
The upload becomes authoritative only after a downloaded copy has been hash-verified and that record is committed.

Status: **AUTHORIZED_TO_UPLOAD**, not uploaded. The upload is a manual owner step: the execution environment that
prepared this record has no working GitHub release-creation capability (the `gh` CLI is installed but its token is
invalid, and the GitHub tools available there can read releases but cannot create one or upload an asset). On 2026-10-04,
the tag `evidence-f1-intake-synthesis-v1-405296e` had no release (GitHub API: 404).

Record: `F1_INTAKE_SYNTHESIS_v1_405296e.manifest.json` (this directory). Expected values:

| field | value |
|---|---|
| asset name | `F1_INTAKE_SYNTHESIS_v1_405296e.tar.zst` |
| sha256 | `c29623c08099c688584439b881c07c7a59b14fba3645642e652e3a2c7ce04dd2` |
| size | 2011661 bytes |
| tar sha256 / size | `a03f5e101d86d64500cbdb11c8808d1bc7ee89367a5c2ffb10ec9d0b90f9bebf` / 36730880 bytes |
| release tag | `evidence-f1-intake-synthesis-v1-405296e` (repository `ppusapati/abep`) |
| download URL (after publication) | `https://github.com/ppusapati/abep/releases/download/evidence-f1-intake-synthesis-v1-405296e/F1_INTAKE_SYNTHESIS_v1_405296e.tar.zst` |

## Steps

1. Rebuild the archive from a checkout that contains the committed full F1 JSON and full git history (not a shallow
   clone). You need `pip install zstandard`. The archive bytes reproduce with libzstd 1.5.7 (python-zstandard 0.25.0), and
   the tar sha256 reproduces with any version.

   ```
   python scripts/evidence/f1_archive.py build --out-dir /path/outside/repo --check
   ```

   This must print `OK: ... manifest.json reproduces; archive matches it`. It writes
   `/path/outside/repo/F1_INTAKE_SYNTHESIS_v1_405296e.tar.zst` and does not change the committed manifest. Confirm with
   `sha256sum` that the sha256 is the one in the table above.

2. Create the release and upload the asset, either with the GitHub web UI (Releases -> Draft a new release -> tag
   `evidence-f1-intake-synthesis-v1-405296e`, attach the file) or with an authenticated `gh`:

   ```
   gh release create evidence-f1-intake-synthesis-v1-405296e \
     /path/outside/repo/F1_INTAKE_SYNTHESIS_v1_405296e.tar.zst \
     --repo ppusapati/abep --target 405296ee4aeb42d8421c98aa3b7f164733fb7960 \
     --title "Evidence: F1 intake synthesis v1 (405296e)" \
     --notes "Deterministic evidence archive (A9.22 item 9; upload authorized by A9.24 item 11). Manifest: docs/evidence_archives/f1_intake/F1_INTAKE_SYNTHESIS_v1_405296e.manifest.json. sha256 c29623c08099c688584439b881c07c7a59b14fba3645642e652e3a2c7ce04dd2, 2011661 bytes. Model-derived screening evidence, INVESTIGATION_HYPOTHESIS."
   ```

   `--target` makes the tag point at the generating commit. Choosing another target is the owner's call. The tag only
   names the release.

3. Download the asset back, into a fresh directory, from the published URL:

   ```
   mkdir -p /tmp/f1_dl && cd /tmp/f1_dl
   gh release download evidence-f1-intake-synthesis-v1-405296e --repo ppusapati/abep \
     --pattern F1_INTAKE_SYNTHESIS_v1_405296e.tar.zst
   # or: curl -fLO https://github.com/ppusapati/abep/releases/download/evidence-f1-intake-synthesis-v1-405296e/F1_INTAKE_SYNTHESIS_v1_405296e.tar.zst
   ```

4. Verify the downloaded copy and write the record:

   ```
   python scripts/evidence/f1_archive.py verify-download /tmp/f1_dl/F1_INTAKE_SYNTHESIS_v1_405296e.tar.zst \
     --record docs/evidence_archives/f1_intake/F1_INTAKE_SYNTHESIS_v1_405296e.download_verification.json
   ```

   Exit 0 and `"result": "VERIFIED"` are required. The command checks the sha256 and size, decodes the zstd stream,
   checks the tar sha256 and size, re-extracts every member and checks its size and sha256 against the manifest, checks
   the deterministic member metadata, and compares the members byte for byte with the local originals when they are
   present. On any mismatch, do not commit the record. Delete the release asset and repeat from step 1.

5. Commit the record file. Only after this commit is the release asset authoritative. Then update the manifest's
   `storage.preferred` status through the builder (`scripts/evidence/f1_archive.py`, which is the source of truth). Do
   not hand-edit the manifest. Log the change in `docs/HISTORY.md`.

The full JSON `docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json` stays in the working tree until step 5 is
done (manifest `storage.original_full_file.removal_rule`). Git history is never rewritten.

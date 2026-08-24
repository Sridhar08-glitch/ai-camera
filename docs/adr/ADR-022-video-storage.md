# ADR-022 — Video Storage Architecture

**Status:** Accepted (Phase 4)

## Decision (D1)
Uploaded videos are stored on the **local filesystem** via a swappable
`StorageBackend` interface using **server-generated, content-addressed keys**.

- `ingestion.storage.StorageBackend` (ABC): `save`, `open`, `delete`, `exists`,
  `size`, `checksum`, `resolve_path` (internal only).
- First implementation: `LocalFileSystemBackend`, rooted at
  `settings.VIDEO_STORAGE_ROOT` (default `<BASE_DIR>/media/videos`, git-ignored).
- **Key format:** `sha256[:2]/sha256[2:4]/sha256.<ext>` — derived from the file's
  content checksum. No client-supplied value participates in the path.
- `resolve_path` is confined under the root (traversal-guarded). **No absolute
  filesystem path is ever exposed through an API.**

## StoredArtifact authority
`governance.StoredArtifact` is authoritative for physical-file facts (`path` =
storage key, `checksum_sha256`, `size_bytes`, `category`) and gains a `state`
field (`present`/`orphaned`/`deleted`) for lifecycle + orphan reconciliation.
`VideoAsset` is authoritative for video/domain metadata and references its
StoredArtifact without re-authoring checksum/size.

## Consequences
- Local-first, no new infrastructure; content-addressing dedupes physical bytes
  and removes client control over storage paths.
- Object storage / NAS / edge backends can be added later behind the same
  interface without changing ingestion business logic.
- Filesystem and PostgreSQL are not one transaction: writes are compensated
  (save-then-DB, delete-on-DB-failure) and an orphan-reconciliation task sweeps
  temp files and dangling artifacts.

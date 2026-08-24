# ADR-029 — Training Data Governance & Provenance (Phase 6T)

**Status:** Accepted — **Phase 6T-A implemented** (dataset governance + provenance shipped; production training = 6T-B, gated)

## Context (6T-A update)
Phase 6 excluded training/datasets/third-party weights. Phase 6T-A ships the **dataset
governance + provenance** foundation so a future real detector can be trained only on
rights-eligible data with full traceability. This ADR now documents what actually shipped.

## Decision (implemented in 6T-A)
- **`apps.datasets`** governs data rights: `Dataset`, `DatasetLicense` (primary-source
  evidence), `DatasetVersion` (`rights_status`), `DatasetImport`, `DatasetManifest`
  (immutable, content-hashed). No media blobs in PostgreSQL — references + hashes + counts.
- **Production-training eligibility gate** (`apps.datasets.gate`) is **code-enforced** in the
  training path: only `{APPROVED_COMMERCIAL, APPROVED_WITH_OBLIGATIONS, INTERNAL_AUTHORIZED,
  SYNTHETIC_APPROVED}` + `approval_status=APPROVED` may feed a production-eligible run.
  `RESEARCH_ONLY/LICENSE_UNCLEAR/REJECTED` are rejected (not just in the UI).
- **Sample provenance** lives in immutable hashed manifests (scales to millions of rows);
  the DB stores manifest sha256 + counts. **Leakage-safe grouped splitting** (by
  video/camera/scene/sequence/location, + checksum union) is deterministic and seeded.
- **`TrainingRun`** (governance) records the full reproducibility chain: code-identity hash,
  architecture, dataset version ids, split-manifest sha256, taxonomy/mapping/preprocess
  versions, seed, framework versions, hardware, metrics, artifact refs.
- Canonical annotation format = **COCO JSON**; source labels map to canonical taxonomy via a
  **versioned mapping** (ambiguous labels never silently mapped).

## Original direction (retained)
Phase 6 deliberately excluded training, datasets, and third-party pretrained weights. This
ADR recorded the intended direction for the real detector so Phase 6 interfaces fit it.

## Direction (not implemented in Phase 6)
- The real detector will be **project-trained** and exported to **ONNX**, then governed as
  an `AIModelVersion` promoted through the ADR-032 lifecycle to APPROVED/ACTIVE.
- **PyTorch is a Phase 6T training-only dependency**, isolated from the runtime; the
  serving path stays ONNX Runtime (ADR-028). The runtime never imports torch.
- Class outputs map into canonical taxonomy `v1` via a **versioned class map** carried on
  the model version (`AIModelVersion.class_map`), so activation cannot change analytics
  semantics.
- Evaluation (mAP/precision/recall) and dataset provenance are recorded on
  `ModelEvaluation` / `AIModelVersion` at that time. **Phase 6 makes no accuracy claims.**

## Consequences
Phase 6's contract, taxonomy, artifact validation, device policy, and storage were all
designed against this direction, so Phase 6T is expected to be a governed model drop-in
rather than a re-architecture.

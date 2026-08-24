# PHASE 6T-A — VERIFICATION REPORT

**Phase:** 6T-A — Training Foundation (dataset governance + training infrastructure; **no real production model trained**)
**Date:** 2026-07-16
**Authoritative sources:** `PHASE_0_ARCHITECTURE.md` (frozen) + approved `PHASE_6T_PLAN.md` (6T-A scope) + Phase 6 (preserved).
**Scope discipline:** infrastructure only. **No real traffic detector trained. No YELLOW/RED dataset used. No third-party pretrained weights. No PyTorch in the production backend. Phase 6T-B NOT started. Phase 7 NOT started.**

> **No real production traffic model has been trained.** Gate D (an approved, production-eligible `DatasetVersion`) has not been satisfied, so Phase 6T-B has not begun. Only a project-created **synthetic TEST_ONLY** smoke model was produced, solely to verify plumbing.

---

## 1. ENVIRONMENT

### 1.1 Production backend (`backend/.venv`) — unchanged, torch-free
| Item | Value |
|---|---|
| Python | 3.12.9 |
| PyTorch | **ABSENT** (`import torch` → ModuleNotFoundError, re-verified) |
| numpy / av / onnx / onnxruntime | 2.2.6 / 13.1.0 / 1.17.0 / 1.20.1 (CPU EP) |

### 1.2 Isolated training env (`training/.venv`) — NEW (ADR-033)
| Item | Value | Notes |
|---|---|---|
| Python | 3.12.9 | created with `py -3.12` (not global 3.14) |
| torch | **2.13.0+cpu** | pinned `training/requirements.txt` |
| torchvision | **0.28.0+cpu** | |
| numpy | 2.5.1 | training-env copy (backend pins 2.2.6 separately) |
| onnx / onnxruntime | 1.17.0 / 1.20.1 | export + CPU parity |
| pycocotools | 2.0.11 | mAP eval |
| pytest | 9.1.1 | training tests |

### 1.3 GPU verification / stack resolution
| Item | Value |
|---|---|
| GPU | NVIDIA RTX 3070 Laptop (Ampere sm_86), 8192 MiB |
| Driver | 592.00 (CUDA ceiling 13.1) · CUDA toolkit / `nvcc`: **not installed** |
| `torch.version.cuda` | `None` (CPU build) · `torch.cuda.is_available()` | **False** |
| Basic CUDA op / fwd-bwd smoke | CPU verified (autograd smoke `24.0` correct); **GPU op not run** — see below |

**Stack decision + fallback (plan §10/§11, documented result):** the preferred GPU stack is
torch `cu126` from `download.pytorch.org`, but that index was **unreachable in this
environment** (DNS `getaddrinfo failed`; PyPI reachable). Per the approved fallback order, I
installed the **CPU** torch stack from PyPI and verified all infrastructure/smoke on CPU. GPU
full training uses the identical device-agnostic code with a `cu126` wheel on a
CUDA-index-reachable host or rented GPU (Phase 6T-B). **No standalone CUDA Toolkit is required**
(PyTorch CUDA wheels bundle the runtime). The NVIDIA driver was **not** modified.

---

## 2. WHAT SHIPPED (6T-A)

### 2.1 Dataset governance — `apps/datasets` (Django, no torch)
- **Models:** `Dataset`, `DatasetLicense` (primary-source rights evidence), `DatasetVersion`
  (`rights_status`, `approval_status`, taxonomy/mapping versions, manifest ref, counts),
  `DatasetImport`, `DatasetManifest` (immutable, content-hashed; `save()` blocks updates).
- **`RightsStatus`** enum + **`PRODUCTION_ELIGIBLE_STATUSES`**; **`gate.py`** hard gate
  (`assert_versions_eligible`) — code-enforced, not UI-only.
- **`manifests.py`** — deterministic canonical serialization + sha256 + tamper verify.
- **`mapping.py`** — versioned class mapping (`map-v1`); ambiguous labels never silently mapped.
- **`coco.py`** — canonical COCO-JSON conversion + provenance; **`validation.py`**;
  **`dedup.py`** (SHA-256 exact + advisory pHash flags); **`splits.py`** (leakage-safe grouped
  + checksum-union deterministic splits + `check_no_leakage`).
- **`services.py`** — end-to-end import orchestration → governance rows + manifest files.
- **`retention_handlers.py`** — `DATASET_MANIFEST` retention (registered at ready()).
- **CLI:** `manage.py dataset_gate [--eligible]`.
- New `DataCategory.TRAINING_DATA` / `DATASET_MANIFEST`; audit events
  `DATASET_REGISTERED/LICENSE_VERIFIED/VERSION_APPROVED/VERSION_REJECTED`,
  `TRAINING_STARTED/COMPLETED/FAILED`.

### 2.2 Training provenance — `governance.TrainingRun`
Full reproducibility chain: `code_identity` (sha256 over training code), architecture,
`dataset_version_ids`, `split_manifest_sha256`, taxonomy/mapping/**preprocess** versions, seed,
framework versions, hardware, status, metrics, checkpoint/artifact refs. Links to
`AIModelVersion` (nullable until a model is registered). Large checkpoints are **references**,
never PG blobs.

### 2.3 Training package — `training/` (torch, isolated; ADR-033)
- `preprocess.py` — bilinear letterbox identical to backend (ADR-037), golden-hash-locked.
- `synthetic.py` — project-created geometric **TEST_ONLY** smoke data (no third-party content).
- `architectures/` — `TinyDetector` (random-init smoke), `factory.build_detector`
  (`tiny` / `fcos` random-init BSD-3 / `yolox_s` guided-NotImplemented).
- `adapter.py` — raw→canonical decode (`tiny_v1`); pure NumPy (runs on torch + ONNX output).
- `engine.py` — scratch training: cosine+warmup, **max-epoch budget + early stopping** (not
  fixed 300), AMP (GPU), EMA, grad-clip, per-epoch/best/last checkpoints, **NaN-loss abort**.
- `checkpoint.py` — state-dict save + full **resume** (opt/sched/scaler/EMA/epoch/step/RNG).
- `evaluation.py` — IoU precision/recall + pycocotools mAP hook.
- `export.py` — ONNX export (fixed I/O contract, `onnx.checker`). `parity.py` — torch↔ONNX.
- `provenance.py` — code-identity + framework versions. `config.py` — hashable recipe.
- `cli.py` / `__main__.py` — `python -m training smoke|export|parity`.

### 2.4 Preprocessing unification (ADR-037)
`apps/processing/runtime/detector/preprocess.py` resize changed **nearest-neighbour → bilinear**
(pad 114, `/255`, RGB, NCHW). Geometry unchanged → reverse-letterbox + all coordinate contracts
intact. Golden-hash test in both environments locks train==serve.

---

## 3. VERIFICATION EVIDENCE

### 3.1 Smoke training (TEST_ONLY) — full plumbing, end to end
`python -m training smoke --epochs 5 --input-size 128`:
- **Train converges:** loss 5.4204 → 0.5596; val 3.1224 → 0.7728 (backward + optimization OK).
- **Resume:** `resumed from epoch 5 step 30` → continued (checkpoint/resume OK).
- **ONNX export:** succeeded (`onnx.checker` OK).
- **PyTorch↔ONNX parity:** **PASSED** — `max_raw_diff = 2.74e-06` (tol 1e-3), class agreement true.
- Report `test_only: true`.

### 3.2 Dataset governance / gate
`tests/test_datasets_governance.py` (15) — gate **accepts** the 4 eligible statuses, **rejects**
RESEARCH_ONLY/LICENSE_UNCLEAR/REJECTED and unapproved-but-rights-ok; empty rejected;
research-only flag scoped. Manifest determinism, immutability (`save()` raises), tamper
detection. `is_production_eligible` correct.

### 3.3 Pipeline / leakage
`tests/test_datasets_pipeline.py` (11) + `test_datasets_import_service.py` (2) — mapping
(synonyms mapped, ambiguous **not** guessed, drops), COCO conversion + provenance, validation
(oob/zero-area/unknown/duplicate/tiny/empty), exact dedup, **leakage-free splits** (no group or
checksum crosses splits), split **determinism** (same seed → identical manifest hash),
**exact-duplicate media forced into the same split**, end-to-end import → governance rows +
verified manifest.

### 3.4 Training tests (`training/.venv`, torch-gated)
`training/tests/` (11) — random-init tiny/FCOS build (no download), YOLOX raises clearly,
training reduces loss + checkpoints + code-identity present, resume continues, **NaN loss
detected**, export+parity passes, adapter decode shapes, evaluation metric correctness.
Preprocess parity: training letterbox golden hash **equals** backend golden hash (no skew).

### 3.5 Preprocessing regression
`tests/test_preprocess_bilinear.py` (4) — contract ids, geometry unchanged, bilinear produces
interpolated values, **golden-hash lock**. Full Phase 6 detector suite stayed green with **zero
edits** to pre-existing tests.

### 3.6 Suites
```
backend (backend/.venv):   331 passed, 0 failed   (297 Phase 6 baseline + 34 new 6T-A)
training (training/.venv):  11 passed, 0 failed
manage.py check:           0 issues
makemigrations --check:    No changes detected
import torch (backend):    ModuleNotFoundError  (production stays torch-free)
```
New backend tests: datasets_governance 15 · datasets_pipeline 11 · datasets_import_service 2 ·
preprocess_bilinear 4 · training_run_provenance 2 = **34**.

---

## 4. FILES CHANGED / ADDED

**New (backend):** `apps/datasets/` (apps, models, gate, manifests, mapping, coco, validation,
dedup, splits, services, retention_handlers, management/commands/dataset_gate) + `migrations/0001`;
`apps/governance/models.py` (+`TrainingRun`) + `migrations/0004`; tests
`test_datasets_governance.py`, `test_datasets_pipeline.py`, `test_datasets_import_service.py`,
`test_preprocess_bilinear.py`, `test_training_run_provenance.py`.
**Edited (backend):** `apps/processing/runtime/detector/preprocess.py` (bilinear, ADR-037);
`apps/audit/models.py` (+events) + `migrations/0005`; `apps/common/datacategories.py` (+2);
`config/settings/base.py` (+`apps.datasets`); `apps/retention/migrations/0004` (choices).
**New (training/):** whole `training/` package + `training/.venv` + `requirements.txt` + tests.
**New (docs):** ADR-033/034/035/036/037; finalized ADR-029/030.
**No pre-existing test was modified** (all 297 Phase 6 tests preserved unchanged).

## 5. MODELS / MIGRATIONS
`datasets.0001_initial` · `audit.0005` · `governance.0004` (TrainingRun) · `retention.0004`
(choices). All applied; `makemigrations --check` clean. Large media/checkpoints are references
only — no blobs in PostgreSQL.

## 6. REQUIRED 6T-A VERIFICATION CHECKLIST
| Item | Result |
|---|---|
| Exact training stack installed + pinned | ✅ CPU stack (`training/requirements.txt`); GPU wheel documented |
| CUDA env verified OR fallback documented | ✅ CPU fallback documented (CUDA index unreachable) |
| Production backend still torch-free | ✅ `import torch` fails |
| Dataset governance works | ✅ §3.2 |
| Rights gate works / YELLOW rejected for production | ✅ §3.2 (only 4 eligible statuses pass; all others rejected) |
| Manifest generation deterministic | ✅ §3.3 |
| Manifest tampering detected | ✅ §3.2 (`verify_manifest_file`) |
| Dataset validation works | ✅ §3.3 |
| Duplicate / leakage protections work | ✅ §3.3 (no group/checksum crosses splits) |
| Split generation deterministic | ✅ §3.3 |
| Architecture random-init; no pretrained weights downloaded | ✅ §3.4 (weights=None; nothing downloaded) |
| Training smoke succeeds / backward pass | ✅ §3.1 |
| Checkpoint save + resume | ✅ §3.1/§3.4 |
| Evaluation infrastructure works | ✅ §3.4 |
| ONNX export + validation works | ✅ §3.1 (`onnx.checker`) |
| PyTorch↔ONNX parity works | ✅ §3.1 (max diff 2.7e-06) |
| Phase 6 runtime contract compatible | ✅ adapter → canonical Detection; 297 baseline green |
| Full existing regression green | ✅ 331 backend / 11 training |

## 7. KNOWN LIMITATIONS (6T-A)
1. **GPU training not exercised here** — CUDA wheel index unreachable; CPU-only verified. GPU
   run is a 6T-B/rented-GPU step (code is device-agnostic).
2. **YOLOX-S not installed** — package index unreachable; FCOS (BSD-3) + TinyDetector integrated
   instead; `build_detector("yolox_s")` raises with guidance. YOLOX integration is 6T-B on a
   reachable host.
3. **ONNX export uses the legacy TorchScript exporter** (`dynamo=False`) — torch 2.13's dynamo
   exporter needs `onnxscript` (not installable offline). Produces valid ONNX that onnxruntime
   loads (parity passed); revisit exporter choice when `onnxscript` is available.
4. **Cross-environment byte-parity of preprocessing** is enforced via a shared golden hash in
   both suites (not a single shared import, since the envs are isolated by design).
5. **Dataset primary-license re-verification** (plan §5) still pending for most YELLOW datasets
   (network-limited) — irrelevant to 6T-A (no dataset used) but a 6T-B prerequisite.

## 8. EXACT PHASE 6T-B BLOCKERS / START GATES
- **Gate D (data):** no production-eligible `DatasetVersion` exists yet. 6T-B needs ≥1 of:
  CARLA `SYNTHETIC_APPROVED` (after §5.4 conditions + UE-EULA legal review), authorized own
  footage `INTERNAL_AUTHORIZED`, or an Open-Images license-filtered legally-cleared subset
  `APPROVED_WITH_OBLIGATIONS`. **No YELLOW/RED data may be used.**
- **Gate A/B:** confirm YOLOX-S vs FCOS final pick + install on a package-index-reachable host;
  select the exact GPU `cu126` wheel.
- **Gate E:** preprocessing contract frozen — **done** (`preproc-v2-bilinear`, ADR-037).
- Plus: CARLA legal review; Open Images per-image legal spot-check.

---

## 9. STOP BOUNDARY CONFIRMATION
Phase 6T-B **not** begun. No YELLOW dataset used. No real traffic detector trained. The synthetic
smoke model is **TEST_ONLY** and was **not** activated (Phase 6 governance already forbids
activating non-APPROVED/TEST models). Q/B/P profiles **not** finalized (still PROVISIONAL). Phase
7 **not** started.

**No real production traffic model has been trained; Gate D has not been approved and Phase 6T-B has not begun.**

---

PHASE 6T-A STATUS: COMPLETE

# PHASE 6T-B — READINESS REPORT

**Purpose:** make FCOS completely ready for real training, and resolve Gate D as far as
primary-source evidence allows — **without starting real training**.
**Date:** 2026-07-16
**Sources:** `PHASE_0_ARCHITECTURE.md` (frozen), `PHASE_6T_PLAN.md`, `PHASE_6T_A_VERIFICATION_REPORT.md`,
`PHASE_6T_B_PREFLIGHT_REPORT.md`, ADR-029…037.

> **No real traffic model was trained. No real/YELLOW dataset was used or downloaded.**
> Only short **TEST_ONLY** FCOS GPU training + benchmark (synthetic/random) were run (allowed).

---

## 1. BASELINE VERIFICATION
| Check | Result |
|---|---|
| Backend suite | **340 passed, 0 failed** (331 preflight + 9 new 6T-B) |
| Training suite | **21 passed, 0 failed** (11 + 10 FCOS) |
| `manage.py check` / migrations | 0 issues / no changes |
| Production backend torch-free | ✅ `import torch` → ModuleNotFoundError |
| GPU | RTX 3070 Laptop, torch **2.13.0+cu126**, `cuda.is_available()=True` |
No correct prior work redone. New: FCOS training adapter, FCOS/runtime tests, Open Images
candidate pipeline, dataset approval gate.

## 2. FCOS TRAINING-ENGINE INTEGRATION
Introduced a **`DetectorTrainingAdapter`** abstraction (`training/detector_adapter.py`) so the
training loop is **architecture-independent** (no scattered `if fcos`):
- `TinyTrainingAdapter` (smoke) and `FcosTrainingAdapter` implement: `build_model`,
  `compute_loss` (train-mode forward + loss aggregation), `infer` (eval-mode detections),
  `output_schema`.
- `engine.train_run` refactored to call the adapter; the core loop (AMP, EMA, grad-clip,
  checkpoint, early-stop, NaN-abort) is unchanged and shared. The Tiny path (11 tests) still
  passes unchanged.
- FCOS is built with the internal transform made near-identity (`image_mean=0, image_std=1,
  min_size=max_size=input_size`) so it consumes our `preproc-v2-bilinear` letterboxed images
  directly — **train == serve preprocessing**.

## 3. FCOS TARGET CONTRACT
`FcosTrainingAdapter._targets` converts dataset boxes `[K,5]=[cls,x1,y1,x2,y2]` → torchvision
targets `{"boxes": float32[K',4] XYXY, "labels": int64[K']}`, on the correct device, **dropping
degenerate boxes** (x2≤x1 or y2≤y1) and handling **empty images** (`[0,4]`/`[0]`). Labels are the
**canonical taxonomy ids** (0..5) as FCOS foreground classes (FCOS has no background label class,
unlike Faster R-CNN) — no off-by-one. Tests: `test_fcos_target_conversion`, `test_fcos_empty_target_ok`.

## 4. RANDOM-INITIALIZATION VERIFICATION
`build_model` calls `fcos_resnet50_fpn(weights=None, weights_backbone=None, …)` — **no ImageNet
backbone, no COCO detector weights, no download**. Tests: `test_fcos_builds_with_no_pretrained_weights`
(monkeypatch captures `weights=None, weights_backbone=None`) and `test_fcos_weights_are_random_not_constant`.

## 5. GPU FCOS SMOKE-TRAINING RESULT
Real FCOS training on the RTX 3070 (TEST_ONLY synthetic data): forward → **real loss dict** →
aggregate → backward → optimizer step → checkpoint → resume. **Loss keys returned by
torchvision 0.28.0: `bbox_ctrness`, `bbox_regression`, `classification`.** All finite. No accuracy
claimed. Tests: `test_fcos_smoke_training_and_loss_keys`, `test_fcos_loss_dict_finite_keys`.

## 6. CHECKPOINT / RESUME RESULT
Verified with FCOS on GPU: `test_fcos_resume_continues` resumes from `last.pt` and continues (not
restart). The 6T-A RNG-device fix (restore RNG on CPU) is exercised on the CUDA path. State saved:
model/optimizer/scheduler/AMP-scaler/EMA/epoch/global-step/best-metric/RNG/config/provenance.

## 7. EVALUATION INTEGRATION
`FcosTrainingAdapter.infer` returns eval-mode detections `list[{boxes,scores,labels}]`; the
`training.evaluation` IoU precision/recall + pycocotools mAP hook consume them. Postprocessing
split is explicit (see §10): **score-thresh + NMS live INSIDE the FCOS graph**; the training/eval
adapter and the runtime adapter do **not** run a second NMS. Test: `test_fcos_infer_returns_detections`.

## 8. ONNX EXPORT VERIFICATION
`training.export.export_fcos_onnx`: FCOS → ONNX (opset 17, legacy exporter), input `images [3,h,w]`
float32 (dynamic h/w), outputs **`boxes[N,4] / scores[N] / labels[N]`** (post-NMS, target-pixel
space), `onnx.checker` OK, **128.6 MB**. Verified by **ORT load + a TEST_ONLY inference** (contract,
not accuracy). Test: `test_fcos_onnx_export_and_ort_load`. Successful file creation is NOT assumed
valid — ORT load + run is asserted.

## 9. PYTORCH ↔ ONNX PARITY RESULT
`training.parity.run_fcos_parity`. **Parity boundary is explicit: the FINAL post-NMS detections**
(torchvision bakes score-thresh + NMS into the graph, so there is no clean pre-postprocess tensor to
compare). Compares detection **count** and, when non-empty, the max score-sorted box-coordinate
delta (tol 1.0 px). For the random-init smoke model both sides emit ~0 confident detections →
**empty == empty agreement** (`counts_match=True, passed=True`). For a trained model the box/score
deltas are compared. Not faked across unrelated stages. Test: `test_fcos_pytorch_onnx_parity_boundary`.

## 10. PHASE 6 RUNTIME COMPATIBILITY
The generic Phase 6 provider assumed a single `(N,6)` raw output; **FCOS emits 3 post-NMS tensors**,
so the generic path **cannot** consume it directly. Implemented the minimum adapter:
- **`apps/processing/runtime/detector/fcos_adapter.py::decode_fcos_v1`** (pure NumPy, torch-free):
  `label→canonical → conf filter → reverse-letterbox → clamp → cap` — **NO second NMS**.
- **`OnnxDetector`** gained an `output_schema` selector: `phase6-infra-v1`/`tiny_v1` → existing raw
  decode + NMS; **`fcos_v1`** → run the 3-output model (feeds `[3,H,W]`) → `decode_fcos_v1`. The
  existing `(N,6)` path and all Phase 6 detector tests are **unchanged**.
Intended flow: `frame → preproc-v2-bilinear → ORT (FCOS, NMS in-graph) → fcos_v1 adapter →
canonical Detection → persist`. The canonical `Detection` contract is preserved; the TEST_ONLY model
is not activated. Tests: `test_fcos_runtime.py` (reverse-letterbox correct, **overlapping same-class
boxes both survive → no double-NMS**, conf/label filtering, `OnnxDetector` fcos dispatch via a fake
session).

## 11. FINAL GPU BENCHMARK (adapter config, TEST_ONLY)
FCOS via the finalized adapter (mean0/std1, min=max=640 → no internal resize) on RTX 3070, AMP:
| Batch | imgs/s | Peak VRAM | Feasible on 8 GB |
|---|---|---|---|
| 2 | 12.6 | 1.47 GB | ✅ |
| 4 | **23.1** | 2.60 GB | ✅ recommended |
| 8 | **27.0** | 4.84 GB | ✅ comfortable (headroom vs preflight's 7.3 GB) |
The adapter config is **faster + lighter** than the preflight raw benchmark (was 17/18.6 imgs/s,
7.3 GB @ b8) because it skips FCOS's internal resize. Batch 8 is now comfortable.

## 12. DATASET GATE D STATUS — **BLOCKED**
No production-eligible `DatasetVersion` exists; no real dataset is verifiable GREEN. Connectivity is
allowlist-limited: reachable primary sources = Open Images (Google), CARLA (GitHub), COCO home (terms
JS-rendered); most dataset domains remain DNS-blocked → those stay **YELLOW — PRIMARY TERMS NOT FULLY
VERIFIED** (never inferred RED). A fresh search surfaced no new commercially-licensed traffic dataset.
Software now **collects evidence + enforces status** but **cannot** auto-approve (Part Q).

## 13. OPEN IMAGES FILTERED-SUBSET READINESS
Implemented **metadata-only** candidate selection (`apps/datasets/openimages.py`) — **no image
download**. It selects vehicle-class images (Car/Bus/Truck/Motorcycle/Bicycle) that carry a
**commercially-permissive license** (CC BY / CC0; excludes NC/ND/SA) **and** sufficient rights
metadata (license + author + source URL), emits a **candidate evidence manifest**, and marks every
candidate **`PENDING_HUMAN_LEGAL_REVIEW`** with `rights_status=LICENSE_UNCLEAR` — **never
auto-eligible** (Google disclaims per-image accuracy). Tests: `test_datasets_gate_d.py`.
**Candidate count:** cannot be computed without the official metadata CSVs (not downloaded here) —
**provisional; requires running the pipeline over the real metadata** (a metadata-only, image-free
step). Open Images has hundreds of thousands of vehicle boxes, but the eligible post-filter count is
unknown until the filter runs.

## 14. CARLA APPROVAL CHECKLIST (before `SYNTHETIC_APPROVED`)
All must be satisfied + recorded; software will not self-approve:
1. Exact CARLA **release version** pinned.
2. CARLA **source license** = MIT (verified GitHub).
3. **Included asset licenses** = CC-BY (verified) — enumerate the exact assets used.
4. **Unreal Engine version** identified; **applicable UE EULA** reviewed.
5. **Third-party asset inventory** produced; **no UE Marketplace assets**; **no external asset packs**.
6. **Generated-output rights** confirmed for commercial ML training.
7. **ML-training-use** permitted (CC-BY assets → yes with attribution; UE EULA → confirm).
8. **Attribution** captured (CC-BY authors/assets) + recorded per-batch asset manifest.
9. **Dataset redistribution** implications assessed.
10. LGPL-2.1 component (`ad-rss-lib`) **not linked** into any redistributed artifact.
**Exact unresolved legal question (plain English):** *"Does the applicable Unreal Engine End User
License Agreement impose any restriction, royalty, or additional obligation on using image frames
rendered by a packaged CARLA build (default CC-BY assets only) as training data for a commercial
machine-learning product?"* Until answered, CARLA stays **GREEN-CONDITIONAL** (not approved). No CARLA
dataset was generated.

## 15. AUTHORIZED OWN-DATA CHECKLIST
Rights intake (record all): camera owner/controller; recording owner; **authorization to use footage
for ML training**; **commercial-use authorization**; geographic/privacy requirements; retention;
redistribution restrictions; whether **faces/plates** require blurring/exclusion. Pipeline: authorized
footage → register source → rights approval → frame extraction → scene grouping (leakage-safe) →
annotation → validation → `DatasetVersion (INTERNAL_AUTHORIZED)` → **explicit approval**. **Possession
≠ authorization.** The explicit approval gate (`apps/datasets/approval.py`, audited) enforces this.

## 16. FASTEST LEGITIMATE DATASET ROUTE
**CARLA synthetic** — fastest to a rights-clean, class-balanced set **once the single UE-EULA legal
question (§14) is answered**; no annotation effort (labels are generated); good day/night/weather +
small-object control; main weakness is the sim→real domain gap. Time-to-train is gated only by the
legal answer + a generation run.

## 17. BEST-QUALITY DATASET ROUTE
**Authorized own fixed-camera footage** (§15) — real distribution + exact target viewpoint (the
strongest realism for fixed-CCTV detection), optionally **supplemented by an Open Images cleared
subset** for diversity. Slower (rights intake + annotation + privacy handling) but highest real-world
quality. A **combination (own + CARLA + cleared Open Images)** is the best overall.

## 18. FIRST PILOT-TRAINING PROPOSAL (recommended — NOT executed)
| Setting | Value |
|---|---|
| Architecture | **FCOS ResNet50-FPN**, random init (`weights=None, weights_backbone=None`) |
| Input | 640 (letterbox, **preproc-v2-bilinear**) |
| Batch / accic | **4** (safe) or 8 (comfortable) + grad-accum 4 → **effective 16–32** |
| AMP | on (fp16) |
| Optimizer | SGD, momentum 0.9, weight decay 1e-4 |
| Base LR | ~0.01 for eff-16 (linear-scale; short LR sanity sweep first) |
| Warmup / scheduler | ~500-iter linear warmup → cosine to budget |
| EMA / grad-clip | on / 10.0 |
| Max budget | ≤50 epochs (dataset-scale-aware) |
| Early stopping | patience 8 on val mAP@0.5:0.95 |
| Checkpoint / eval | every epoch (best + last) / every epoch |
| Data requirement | ≥1 **production-eligible** `DatasetVersion` (Gate D) |

## 19. UPDATED TRAINING-TIME ESTIMATES (measured ~23 imgs/s @ b4, ~27 @ b8)
Add ~1.3–1.5× for eval + loading + thermal throttling.
| Run | Images × epochs | Raw GPU-h (@23/s) | +overhead |
|---|---|---|---|
| Pilot | 2 k × 20 | ~0.5 h | ~0.7 h |
| First full | 10 k × 50 (early-stop ~30–40) | ~6.0 h | **~6–9 h** |
| Tuning run | 10 k × 30 | ~3.6 h | ~5 h |
**Calendar (checkpoint/resume across sessions), first full model (~6–9 GPU-h):** 3 h/day ≈ 2–3 days ·
4 h/day ≈ 2 days · 6 h/day ≈ 1–1.5 days · overnight ≈ 1 day. No continuous run required.

## 20. TEST RESULTS
Backend **340 passed** (new: `test_fcos_runtime.py` 4, `test_datasets_gate_d.py` 5); training
**21 passed** (new FCOS suite 10). 0 failed. Existing 331 backend + 11 training preserved; **no
pre-existing test weakened**. Migrations clean; backend torch-free.

## 21. REMAINING BLOCKERS
1. **Gate D (primary):** produce ≥1 production-eligible `DatasetVersion` — requires the **CARLA UE-EULA
   legal answer** (§14) and/or **authorized own-data** intake and/or an **Open Images
   legally-spot-checked** subset. Software cannot self-approve.
2. **Legal confirmations:** the single UE-EULA question (§14); Open Images per-image spot-check.
3. (None technical for FCOS — training/export/parity/runtime are ready.)

## 22. EXACT NEXT ACTION
Do **not** start training. In order: (a) obtain the **UE-EULA legal answer** (or choose own-data /
Open-Images-cleared route); (b) prepare + register the chosen data and run the **explicit audited
approval** to create a production-eligible `DatasetVersion`; (c) run the metadata pipeline / generation
as applicable; (d) return for **explicit training approval**. FCOS is technically ready to train the
moment a production-eligible `DatasetVersion` exists.

---

## STATUS
FCOS is technically ready; the only blocker is dataset rights (Gate D). No training was started.

PHASE 6T-B TECHNICAL STATUS: READY

PHASE 6T-B DATA STATUS: BLOCKED

PHASE 6T-B TRAINING STATUS: NOT STARTED

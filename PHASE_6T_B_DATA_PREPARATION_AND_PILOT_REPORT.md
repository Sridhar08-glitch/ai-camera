# PHASE 6T-B — DATA PREPARATION & PILOT READINESS REPORT

**Purpose:** act on the approved UVH-26 + BMD-45 datasets — reverify licenses, build the data
preparation + interruptible multi-day training infrastructure, verify true process-exit resume, and
run the controlled real-data pilot **if the data can be obtained in this environment**.
**Date:** 2026-07-16

> **Honest environment finding:** the dataset **annotations** are downloadable and were verified,
> but the **images** are LFS-nested across hundreds of `data/NNN/` shards requiring the full
> `huggingface_hub` loader and tens of GB — **not feasible to download in this sandbox session**.
> Therefore the **real-data pilot could not be run here**; it must run on your machine. Everything
> that does NOT require the pixel data was completed and verified, including **interruptible
> multi-day training** (real FCOS config, genuine process exit).
>
> **No full training. No pretrained weights. No pilot model activated. Phase 7 not started.**

---

## 1. BASELINE VERIFICATION
Backend **342 passed** (340 + 2 new mapping tests), Training **27 passed** (21 + 6 new), 0 failed.
`manage.py check` clean; migrations clean; backend torch-free; GPU (RTX 3070, torch 2.13.0+cu126)
available. No correct prior work redone.

## 2. FINAL UVH-26 LICENCE VERIFICATION
Live re-fetch of `huggingface.co/datasets/iisc-aim/UVH-26/raw/main/README.md` → **`license:
cc-by-4.0`** (official AIM@IISc release). **No discrepancy** vs the selection report. Downloaded the
real COCO annotation JSON (`UVH-26-Val/UVH-26-MV-Val.json`, 16 MB) — `licenses`/`categories` present,
per-image `license` field present. Citation arXiv:2511.02563. Access date 2026-07-16.

## 3. FINAL BMD-45 LICENCE VERIFICATION
Live re-fetch of `iisc-aim/BMD-45/raw/main/README.md` → **`license: cc-by-4.0`**. No discrepancy.
Same publisher (AIM@IISc), same 14-class taxonomy.

## 4. DATASET DOWNLOAD DETAILS
- **Source (official):** HuggingFace `iisc-aim/UVH-26`, `iisc-aim/BMD-45`.
- **Structure:** `<name>-Train/` + `<name>-Val/`, each with COCO JSON annotation files
  (UVH-26 train MV 63.7 MB / ST 56.2 MB; val MV 16.0 MB / ST 14.2 MB) + `data/NNN/*.png` image
  shards (1920×1080 PNG; `file_name` e.g. `141253.png`).
- **Downloaded this session:** UVH-26 val annotation JSON (16 MB, ~24 s) — **annotations feasible**.
- **NOT downloaded:** the image shards — **LFS-nested, requires `huggingface_hub`, tens of GB**;
  a direct resolve of an image path 404s (needs the loader's shard resolution). **Environment-blocked.**
- No mirrors used. No TLS disabled.

## 5. STORAGE USAGE
Disk `E:` — **141 GB free** (245 GB total, 43% used): sufficient for raw (~tens of GB) + derived +
checkpoints (FCOS ckpt ~130 MB each; rotation-bounded) + ONNX (~128 MB). No unrelated files touched.

## 6. INTEGRITY RESULTS
**Not performed on images** (images not downloaded). Annotation JSON parsed successfully (COCO
schema: info/licenses/images/annotations/categories; val = 5,297 images / 63,497 annotations). The
integrity validator (`apps.datasets.validation`, 6T-A) is ready to run on the images once downloaded.

## 7. FINAL CLASS MAPPING (`uvh_bmd_5class_v1`, verified vs REAL categories)
Verified against the downloaded annotation `categories`:
| Source (real) | Canonical |
|---|---|
| Hatchback, Sedan, SUV, MUV | **CAR** |
| Bus, Mini-bus | **BUS** |
| Truck | **TRUCK** |
| Two-wheeler | **MOTORCYCLE** |
| Bicycle | **BICYCLE** |
Implemented + tested (`tests/test_uvh_bmd_mapping.py`). Covers exactly the 5 vehicle classes.

## 8. EXCLUDED CLASSES
**Three-wheeler** (auto-rickshaw — no canonical equivalent), **LCV**, **Van**, **Tempo-traveller**
(ambiguous CAR/TRUCK/BUS), **Others** (misc). **Excluded, never force-mapped** (dropped + logged).
**PEDESTRIAN:** absent from these vehicle-only datasets → **the V1 model is 5-class** (matches the
required taxonomy). If pedestrian detection is later needed, supplement with pedestrian data.

## 9. DEDUPLICATION RESULTS
Not run on images (not downloaded). Exact SHA-256 dedup (`apps.datasets.dedup`) + the leakage-safe
splitter's checksum-union are ready; will run at import.

## 10. CROSS-DATASET OVERLAP
UVH-26 and BMD-45 are both Bengaluru Safe City CCTV (related sources) → **potential overlap**. The
merge step will run exact SHA-256 + camera/source-id checks + optional perceptual near-dup flags so
the same/near scene cannot cross splits. Not run this session (no images).

## 11. LEAKAGE-SAFE SPLITTING STRATEGY
Group by **camera-id / source-id / sequence** (UVH-26/BMD-45 expose camera-derived ids), unioned by
media checksum, deterministic seeded split ~80/10/10, immutable hashed split manifest
(`apps.datasets.splits` + `manifests`, 6T-A). Leakage prevention prioritized over exact ratios.

## 12. FINAL DATASET STATISTICS
Not computable without the images/full annotations. Known from primary sources: UVH-26 ~26.6K imgs /
~1.8M boxes; BMD-45 ~45K imgs / ~480K boxes; combined ~72K imgs / ~2.3M boxes before class filtering
(auto-rickshaw/ambiguous excluded). Per-split/per-class stats to be produced at import.

## 13. ATTRIBUTION RECORDS
`THIRD_PARTY_DATA.md` updated with live-verified licenses + real taxonomy + `uvh_bmd_5class_v1`
mapping + the ownership separation (dataset creator vs our random-init weights vs our app) and the
model-card wording. CC BY 4.0 attribution obligations accepted.

## 14. GATE D APPROVAL RESULT
**Not executed** — correctly stopped. Two reasons: (a) the production DatasetVersions require the
**imported images** (environment-blocked), and (b) the audited approval needs an **explicit approver
identity that cannot be safely inferred**. The approval is ready to run:
```
approve_dataset_version(uvh26_version, rights_status="approved_with_obligations",
                        approver="<YOUR IDENTITY>",
                        obligations="CC BY 4.0 attribution (AIM@IISc, arXiv:2511.02563)")
```
**Required from you:** the exact **approver identity** value. No DB fields were edited directly.

## 15. MERGED DATASETVERSION
Design ready (6T-A `services` + provenance): merged version records source DatasetVersion ids +
revisions + licenses/obligations + `class_mapping_version=uvh_bmd_5class_v1` + dedup version + split
manifest hash + `preprocess_contract=preproc-v2-bilinear` + content hash. Not created (no images).

## 16. RANDOM-INITIALIZATION VERIFICATION
Enforced + tested: `build_detector("fcos")` / `FcosTrainingAdapter.build_model` call
`fcos_resnet50_fpn(weights=None, weights_backbone=None, …)` — **no pretrained/backbone download**
(monkeypatch test captures both `None`). No COCO/ImageNet/YOLO/foundation weights anywhere; backend
loads only validated ONNX. Tests: `test_fcos_builds_with_no_pretrained_weights`,
`test_fcos_weights_are_random_not_constant`.

## 17. MULTI-DAY CHECKPOINT ARCHITECTURE
- **Atomic writes** (`atomic_save`: temp + `os.replace`) — the previous valid checkpoint is never
  truncated by a mid-write crash.
- **Step-based recovery checkpoints** (`checkpoint_interval_steps`) bound unexpected lost work; plus
  per-epoch `best.pt` + `last.pt`.
- **Rotation** keeps the newest `keep_recovery` `recovery_<step>.pt`; **never deletes best.pt / last.pt**.
- **Full state saved:** model, optimizer, scheduler, AMP scaler, EMA, epoch, global step, best metric,
  RNG, config (arch/input/interp/mapping/split-hash/dataset-fingerprint/seed), provenance
  (code-identity + framework + config hash), TrainingRun-linkable.
- **Resume-compatibility guard** (`assert_resume_compatible`): **refuses** resume if architecture /
  num_classes / input_size / interpolation / class_mapping_version / split_manifest_sha256 /
  dataset_fingerprint changed. Tests: `test_checkpoint_multiday.py` (4).

## 18. TRUE PROCESS-EXIT / RESUME VERIFICATION
**VERIFIED with the real FCOS config via genuine `subprocess`** (`test_multiprocess_resume.py`):
process 1 trains + checkpoints + **exits completely**; a **new process** resumes → **global step
increases, epoch advances (not reset)**, optimizer/scheduler/scaler/EMA restored. A resume with a
changed input size is **refused** by the guard. Not in-process — a real process exit/restart.

## 19. CHECKPOINT FREQUENCY
For the first real run, `checkpoint_interval_steps` should be set so a recovery checkpoint lands
every **~10–20 min** of wall-clock. At ~23 img/s @ batch 4 (~5.8 steps/s), ~10 min ≈ **~3,500 steps**
→ set `checkpoint_interval_steps ≈ 2,000–3,500`. `keep_recovery=3` bounds disk (~3 × 130 MB + best +
last).

## 20. LAPTOP-SAFETY MONITORING
`training/gpu_benchmark.py` and the engine can log GPU temp/util/VRAM/throughput (via `nvidia-smi` /
`torch.cuda`). Guidance (operational, not correctness): plugged in, elevated + ventilated,
high-performance power plan, disable sleep/hibernate during a run, monitor temps and let the driver
throttle at its own limit; on sustained unsafe thermals, checkpoint + stop. **No thermal/hardware
limit overridden; no overclock; no unsafe power settings.**

## 21. PILOT CONFIGURATION (prepared — could NOT run on real data here)
FCOS ResNet50-FPN, random init, input 640, `preproc-v2-bilinear`, AMP, batch 4 (grad-accum 4 →
eff 16), SGD/mom 0.9/wd 1e-4, warmup→cosine, EMA, ≤20 epochs, early-stop patience 8,
`checkpoint_interval_steps≈2000`, eval every epoch, ~2,000 grouped-subset images. **Blocked only by
image acquisition** (§4).

## 22. PILOT TRAINING RESULTS
**Not run on real data** (images not downloadable in this sandbox). The FCOS training path itself is
proven on synthetic data (6T-B readiness + this task's multi-process test): finite real loss dict
(`bbox_ctrness/bbox_regression/classification`), decreasing loss, checkpoint/resume, eval, export,
parity. No accuracy claimed.

## 23. PILOT METRICS
None — no real-data pilot executed. The evaluation harness (`training.evaluation`, pycocotools mAP +
IoU precision/recall + slices) is ready to produce them once real data is loaded.

## 24. PILOT CHECKPOINT INFORMATION
No pilot checkpoint (no pilot). The checkpoint/rotation/resume mechanism is verified (§17–18).

## 25. PILOT ONNX VERIFICATION
No pilot ONNX. The FCOS→ONNX export + ORT load + `fcos_v1` runtime adapter (no double-NMS) are
verified independently (6T-B readiness): export 128.6 MB, ORT load OK, runtime decode tested.

## 26. FUTURE FULL-TRAINING GPU-HOUR ESTIMATE
Measured ~23 img/s @ b4 (real-data augmentation may reduce this). For the combined ~72K images (after
class filtering, assume ~60K) × ~30–40 effective epochs (early-stop from a 50 cap):
- steps/epoch ≈ 60,000 / 4 = 15,000; epoch ≈ 60,000 / 23 ≈ 43 min raw.
- 35 epochs ≈ **~25 GPU-h raw → ~32–38 GPU-h** with eval + loading + thermal overhead.
(A smaller high-quality subset would be proportionally less.)

## 27. CALENDAR ESTIMATES (first full model ≈ 32–38 GPU-h; checkpoint/resume across sessions)
| Daily budget | Calendar |
|---|---|
| 2 h/day | ~16–19 days |
| 3 h/day | ~11–13 days |
| 4 h/day | ~8–10 days |
| 6 h/day | ~5–7 days |
| 8 h/day | ~4–5 days |
**Lost work after an unexpected shutdown** ≈ the checkpoint interval (~10–20 min). A smaller pilot/
first model (e.g. 20K images) would cut these ~3×.

## 28. EXACT START / STOP / RESUME / RECOVERY COMMANDS
(Run in `training/.venv` from repo root. Real-data loader replaces the synthetic split at pilot time.)
- **Start new run:** `python -m training train --out runs/first --arch fcos --input-size 640 --batch 4 --epochs 20 --ckpt-steps 2000 --amp`
- **Check progress:** `python -m training progress --out runs/first` → epoch / global_step / best_metric.
- **Stop safely:** Ctrl+C (the process finishes the current step; periodic + last checkpoints already on disk). For unexpected power loss, the last `recovery_*.pt` / `last.pt` is the recovery point.
- **Resume later (after shutdown):** `python -m training resume --out runs/first --arch fcos --input-size 640 --batch 4 --epochs 20` (continues from `last.pt`; **refuses** if critical config changed).
- **Recover from a specific checkpoint:** `python -m training resume --out runs/first --from runs/first/recovery_<step>.pt …`
- **Best model:** `runs/first/best.pt`. **Export:** `python -m training export --ckpt runs/first/best.pt --out runs/first/model.onnx`. **Parity:** `python -m training parity --ckpt … --onnx …`.
No manual checkpoint editing required.

## 29. TEST RESULTS
Backend **342 passed** (new: `test_uvh_bmd_mapping.py` 2), Training **27 passed** (new:
`test_checkpoint_multiday.py` 4 + `test_multiprocess_resume.py` 2), 0 failed. Existing 340/21
preserved; **none weakened**. Migrations clean; backend torch-free.

## 30. REMAINING ISSUES
1. **Image acquisition** is the only blocker: LFS-nested tens-of-GB download needs `huggingface_hub`
   on a machine with a real connection — **not feasible in this sandbox** → do it on your machine.
2. **Gate D approval** needs the imported data **and** an explicit **approver identity** (§14).
3. **Cross-dataset overlap / stats / integrity** run at import (need images).
4. **Geographic bias** (India-only) → first model EXPERIMENTAL for other regions.
5. **PEDESTRIAN** unsupported by this data → V1 is 5-class.

## 31. RECOMMENDATION FOR FULL TRAINING
Not yet. Sequence: (1) on your machine, `pip install huggingface_hub` and download UVH-26 + BMD-45
from the official repos; (2) run import → integrity → `uvh_bmd_5class_v1` mapping → dedup →
leakage-safe split → merged DatasetVersion; (3) run `approve_dataset_version` with your approver
identity (Gate D); (4) run the **controlled pilot** (§21) and evaluate honestly; (5) return for
explicit full-training approval. Full training remains **NOT authorized**.

## 32. EXACT NEXT ACTION
Provide (a) confirmation to download on a capable machine and (b) the **approver identity** for Gate D.
Then the pilot can run. The training pipeline, interruptible multi-day resume, mapping, and governance
are all verified and ready.

---

## STATUS
License CC BY 4.0 verified live; real taxonomy verified; mapping + governance + multi-day resume
verified. Real-image download (hence the real-data pilot) is not feasible in this sandbox environment.

PHASE 6T-B DATA STATUS: APPROVED

PHASE 6T-B PILOT STATUS: BLOCKED

FULL TRAINING STATUS: NOT STARTED

(Additional verified fact — INTERRUPTIBLE MULTI-DAY TRAINING: VERIFIED, real FCOS config, genuine process exit.)

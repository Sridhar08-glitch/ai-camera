# PHASE 6 PLAN — Detection Provider + Benchmark Suite + Profile Selection (with AI‑ownership foundation)

**Status:** DRAFT — READY FOR REVIEW (no implementation performed)
**Date:** 2026-07-15 (rev. 2 — dataset & model‑ownership strategy correction)
**Authoritative source:** `PHASE_0_ARCHITECTURE.md` (frozen)
**Planning discipline:** No AI framework installed · no CUDA installed · no datasets/weights downloaded · no training · no third‑party inference run · only this file created.

> **Rev. 2 correction (governs where it conflicts with earlier text):** Third‑party **pretrained detector weights are NOT used by default anywhere in Phase 6** — not even for benchmarking. Only the *architecture code* (permissive license) may be reused; its weights may not. Phase 6 infrastructure is validated with **clearly‑labelled deterministic test providers / project‑created test artifacts** that make **no claim of real AI accuracy**. The first real project‑trained detector (random‑init, approved data) is produced in **Phase 6T**. Ownership language is precise: *project‑trained model* with documented provenance — never "we own everything."

---

## 1. CURRENT STATE VERIFIED

Verified against the live repository and environment (not only reports).

### 1.1 Baseline (re-run live, project venv `backend/.venv`, Python 3.12.9)
```
245 passed, 0 failed, 0 skipped   (188 Phase-1–4 + 57 Phase-5)
coverage (apps): 88%
```
Matches the Phase 5 verification report exactly.

### 1.2 Apps (11) & migrations (15)
`accounts, audit, common, governance, health, ingestion, network, observability, processing, realtime, retention`. Migrations: 15 total (adds `processing/0001`, `audit/0003`, `retention/0003` over Phase 4). Chain clean from empty DB (`pytest --create-db`).

### 1.3 Phase 5 processing implementation (read from source — all present)
`apps.processing`: `ProcessingSession` + immutable `ProcessingConfigSnapshot`; single‑writer state machine; standalone CV runtime (`run_cv_runtime`); `LocalFileSource` (PyAV sequential decode, PTS); **`FrameView.as_rgb_ndarray()`** lazy‑cached canonical `rgb24` (H×W×3 `uint8` C‑contig); `FrameMeta`; `FrameProcessor` Protocol (`setup/process/teardown`, `ProcessingContext{snapshot_payload, params, device, logger}`, `ProcessorResult`, `ProcessorSummary`); `Sampler` (EVERY_FRAME/EVERY_N/TARGET_FPS); processor registry `build_processor()` + `_REGISTRY`; `GPUManager` (`select_device/reserve/refresh/release/can_fit/status`); pipeline builds+calls one processor per sampled frame and **does not persist processor output** (the processor owns persistence).

### 1.4 Existing model‑governance registry (already anticipates Phase 6 — REUSE, do not duplicate)
`apps.governance`:
- `AIModel(family, task∈{detection,tracking,prediction,anomaly}, provider, is_active)`.
- `AIModelVersion(version, provenance∈{pretrained,finetuned,**platform_trained**,imported,traditional_ml}, license, source_url, config, input_spec, output_schema_version, class_map, benchmark_summary, is_active)`.
- `ModelArtifact(kind∈{weights,config,labels}, path, checksum_sha256, size_bytes)`.
- `ModelEvaluation(dataset_ref, metrics, provenance_note)`.
- `AlgorithmDefinition`/`AlgorithmVersion` (immutable, config_hash) for deterministic algorithms.
- API `/api/v1/governance/…` incl. `POST /model-versions/{id}/activate` — **atomic "one active version per model family"**, audits `MODEL_ACTIVATED`. Reads = admin roles; **writes = system_admin only**.
- Artifact path safety: `checksums.py::validate_artifact_path()` against **`settings.ARTIFACT_ROOT`** (separate from `VIDEO_STORAGE_ROOT`); `sha256_file()`, `canonical_config_hash()`.
- `Provenance.PLATFORM_TRAINED` already exists → the "our own trained weights" concept is pre‑modelled.

### 1.5 DataCategory / retention / audit hooks (present, unused for detection yet)
`DataCategory` already has `MODEL_ARTIFACT`, `DETECTION_METADATA`, `TRACK_METADATA`. **No retention handler registered** for these (Phase 6 adds one if it persists detections). Audit `EventType` has `MODEL_ACTIVATED`, `MODEL_DEACTIVATED` (defined, unused), `ALGORITHM_ACTIVATED`.

### 1.6 GPU / AI‑framework availability
- Project venv (`backend/.venv`): **no torch / tensorflow / onnxruntime / opencv**. Only `av==13.1.0`, `numpy==2.2.6`. ✅ (verified `requirements/base.txt`).
- Machine: **NVIDIA RTX 3070 Laptop, 8192 MiB, driver 592.00, CUDA 12.8, `nvidia-smi` present**. Global Python 3.14 has torch cu128 — **machine‑level only, unrelated to the project**; used solely as evidence the machine supports CUDA.

### 1.7 Detector / training code today
**None.** No detector, no preprocessing, no training code, no dataset tooling. Greenfield for Phase 6.

### 1.8 Discrepancies (reports vs reality)
None material. Governance registry is richer than a naïve reading of the reports suggests — it already supports detection‑model provenance, artifacts, evaluations, and `platform_trained`. The only gap vs the instruction's ambitions is that **no dataset/training‑governance domain exists** and **the frozen roadmap does not contain a training phase** (see §2).

---

## 2. FROZEN‑ROADMAP RECONCILIATION

### 2.1 Exact frozen Phase 6
> **Phase 6 — Detection provider + Benchmark suite + profile selection.** Depends: P5. — `PHASE_0_ARCHITECTURE.md:547`
> Estimate: 5 / 9 / 16 days (§41). Benchmark strategy (§20): measure candidate detectors × resolution × stride on *this* laptop → **Quality / Balanced / Performance** operating profiles; "**No version frozen now**"; "the default detection/tracking provider is **selected here**." Provider interfaces (§12) freeze `DetectionProvider.load/detect/classes/warmup/unload`. Canonical vehicle taxonomy (§19): car/motorcycle/bus/truck/bicycle/**pedestrian**.

### 2.2 The central discrepancy (must be surfaced, not silently redefined)
This planning instruction asks for a **full training‑data‑governance domain + dataset‑licensing pipeline + training the first project model from scratch**. **The frozen 19‑phase roadmap contains NO training phase** — not in Phase 6, not anywhere. Frozen Phase 6 is *integrate a detection provider and benchmark candidates to pick a profile/architecture*; §20 explicitly benchmarks candidate models (e.g. "a YOLO‑class model in n/s/m sizes"), which implies using existing detector families, not training from scratch.

### 2.3 Recommended resolution (preserve frozen scope; move training to an explicit new phase)
Per the instruction's own rule ("if the frozen scope is narrower, preserve it and move additional work into explicit future prerequisites"):

- **Phase 6 (this phase) = detection INFRASTRUCTURE (frozen scope; NO third‑party pretrained detector required):** `DetectorProvider` interface + `DetectionFrameProcessor` integrated into the Phase 5 pipeline; framework‑independent detection output contract; preprocessing/postprocessing; detection persistence; **ONNX Runtime** integration; model‑artifact validation + loading via the existing governance registry + promotion gate; device policy; detections APIs; visualisation; **benchmark harness**. Validated with a **clearly‑labelled `DeterministicTestDetector` / project‑created test artifact** (proves the pipeline, **not** AI accuracy). No third‑party weights.
- **New explicit phase — "Phase 6T — Training System + First Project‑Trained Model (from random init)":** dataset governance + provenance + import + validation + canonical annotation conversion + class mapping + leakage‑safe splits + PyTorch training environment + training pipeline + `TrainingRun` + checkpointing + evaluation + ONNX export + model registration; then `approved free datasets + approved synthetic (self‑generated CARLA) + authorized own data → train from random init → evaluate → export → register → activate`. Produces the **first real project‑trained traffic detector** and the first real Quality/Balanced/Performance profiles. **Prerequisite before any production model is frozen / before downstream phases treat detections as production‑grade.** NOT part of Phase 6.

This honours frozen scope, keeps the ownership goal explicit and first‑class, and removes the pretrained‑weights dependency entirely: Phase 6 *builds and infrastructure‑benchmarks the detection system*; Phase 6T *produces the project‑trained, provenance‑complete production weights*.

### 2.4 What is Phase 7+
Tracking (P7), measurement/counting/lane analytics (P8) — **not** Phase 6. Phase 6 must not implement tracking trails or unique vehicle counts (raw per‑frame detections only).

---

## 3. PHASE 6 OBJECTIVE
Build and verify the **detection infrastructure** (no third‑party weights, no real‑AI‑accuracy claim): `sampled frame → FrameView.as_rgb_ndarray() → detector preprocess → DetectorProvider boundary → ONNX inference‑runtime boundary → postprocess (NMS) → canonical `Detection`s → durable `FrameDetectionBatch` → API/visualisation`, integrated through the Phase‑5 `FrameProcessor`, plus a **benchmark harness + profile‑selection mechanism**. Phase 6 is exercised with a **clearly‑labelled deterministic test provider / project‑created test artifact** for infrastructure verification only. The **first real project‑trained detector and real Quality/Balanced/Performance profiles are produced in Phase 6T** (after the dataset‑rights gate clears). Detector output becomes the foundation for Phase 7+ (tracking/counting/etc.), none of which is built here.

---

## 4. NON‑GOALS (Phase 6)
No tracking, counting, lane association, speed, queue, congestion, incidents (Phase 7+). No training / dataset download / dataset‑governance domain (Phase 6T). **No production model frozen** in Phase 6. No third‑party AGPL model in shippable form. No external AI API. No RTSP/CCTV/webcam/live. No face/person recognition or plate OCR (frozen §32). No fake detector presented as production. No pretrained weights promoted to ACTIVE/production.

---

## 5. AI OWNERSHIP STRATEGY (precise language — no absolute claims)
Target chain: *verified‑rights data (free commercially‑permitted public + permitted synthetic + later authorized own footage) → our controlled preprocessing → commercially‑compatible open **architecture code** (no third‑party weights) → training under our pipeline from **random initialization** → our resulting **project‑trained** (`platform_trained`) weights → evaluation → ONNX export → registry → production inference.*

Preferred phrasing throughout: **"project‑trained model"** and *"our production model weights were generated by our controlled training pipeline from approved training data."* **Do not** claim "we own everything." Software, architecture implementation, dependencies, datasets, and resulting weights each carry **different rights and obligations**. The goal is **maximum project control with documented provenance and commercial‑use compliance.**

Five separately‑licensed layers kept distinct (§2 of the correction):
1. **Dataset images/videos** — publisher's license (may require attribution / forbid commercial / share‑alike).
2. **Dataset annotations** — often a *different* license from the images (e.g. Open Images: annotations CC BY 4.0, images CC BY 2.0 per‑image).
3. **Dataset code/tools** — a permissive repo code license does **not** grant rights to its data or weights.
4. **Model architecture implementation** — reusable if its **code** license is approved (e.g. Apache‑2.0). Using an architecture does **not** require using its weights.
5. **Pretrained weights** — **not used by default** (rev. 2); a separate, explicitly‑approved exception only.

Ownership reality: we own our software/adapters/pipeline; we control our architecture code/modifications within its license; our project‑trained weights are ours **subject to the data rights of every contributing dataset** (local training does not strip dataset obligations). **Formal legal review is required before any commercial claim.** This section is engineering guidance, **not legal advice**.

---

## 6. DATASET LICENSING POLICY + PRODUCTION TRAINING GATE (design; enforced in Phase 6T)
Formal approval gate before any dataset enters a production‑training pool. **Seven statuses** (rev. 2 adds `INTERNAL_AUTHORIZED`, `SYNTHETIC_APPROVED`):

| Status | Meaning | May enter production pool? |
|---|---|---|
| `APPROVED_COMMERCIAL` | Publisher terms clearly permit our commercial training use | ✅ |
| `APPROVED_WITH_OBLIGATIONS` | Commercial OK **with** obligations (attribution/share‑alike tracked) | ✅ (obligations recorded + honoured) |
| `INTERNAL_AUTHORIZED` | Our own authorized footage, privacy/compliance‑cleared (§7‑own) | ✅ |
| `SYNTHETIC_APPROVED` | Self‑generated synthetic whose engine+asset+output rights are cleared (§7‑synthetic) | ✅ |
| `RESEARCH_ONLY` | Academic/research‑only terms | ❌ |
| `LICENSE_UNCLEAR` | Terms ambiguous / unverified | ❌ |
| `REJECTED` | Non‑commercial / prohibited / unsuitable | ❌ |

**Only the top four may contribute to production weights.** `RESEARCH_ONLY` / `LICENSE_UNCLEAR` / `REJECTED` are excluded from production **and kept out of the repository entirely** (separate, non‑committed root) to prevent accidental mixing. **The gate is enforced in the training pipeline itself** (`ml.train` refuses any `DatasetVersion` — and any individual sample — whose eligibility is not production‑approved), **not only in the UI**. Authoritative license must come from the **original publisher** — never Kaggle mirrors, reposts, or a repo's *code* license. No mechanism may hide provenance or circumvent restrictions (explicitly prohibited).

**Sample‑level eligibility (media + annotation, correction §4):** a training sample is production‑eligible only when **all** required components clear — `media rights + annotation rights + dataset/source terms + applicable attribution/obligations`. **A sample must NOT be admitted merely because its annotation is approved** (e.g. Open Images: CC BY 4.0 annotation ≠ cleared image). The gate operates at the level needed to verify **both image/media rights and annotation rights**. Efficiency: where **one verified license uniformly covers all files**, dataset‑level approval suffices and per‑sample status is inherited; where **licenses differ per item** (e.g. Open Images per‑image), the manifest carries **per‑sample** rights status (§8). Do not over‑build per‑sample tracking for uniformly‑licensed datasets.

---

## 7. DATASET RESEARCH (primary‑source; no downloads performed)
Candidates with **primary‑source license findings** (verified 2026‑07‑15 where cited). **GREEN** = primary‑source evidence establishes that the **actual training content we intend to use** (media **and** annotations **and** source terms) is permitted for our intended commercial purpose; **YELLOW** = any material rights layer is ambiguous / needs permission or per‑item verification; **RED** = non‑commercial / research‑only / prohibited. **A dataset is GREEN only when every material layer clears — an approved annotation license alone is NOT sufficient.** No dataset is GREEN based only on annotation license, repo code license, free download, open‑access status, a third‑party summary, or a Kaggle/Roboflow mirror. Every layer (images / annotations / code / weights) is judged separately (§5).

### 7.1 Real‑world datasets

| Dataset | Publisher | Official source | Size | Vehicle classes | Viewpoint | Annotation | Exact license | Commercial‑training | Attribution | Redistribution | Status | Evidence | Verified |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Open Images V7** | Google | storage.googleapis.com/openimages | ~9.2M img, 16M boxes/600 cls | Car,Bus,Truck,Motorcycle,Bicycle,Person | Web images (mixed, some roadside) | Box CSV → COCO | **Annotations CC BY 4.0**; images CC BY 2.0 (per‑image; Google disclaims per‑image warranty) | annotations ✅; **individual image rights unverified (per‑image)** | Yes (CC BY) | Allowed w/ attribution; per‑image warranty disclaimed | **YELLOW — image‑rights verification required** (annotations clear; images per‑item) | og1 | 2026‑07‑15 |
| **MIO‑TCD** (localization) | Miovision | tcd.miovision.com | 137,743 frames | car,truck,bus,motorcycle,bicycle,pedestrian +others | **Fixed traffic camera (ideal)** | Box | **CC BY‑NC‑SA 4.0** | ❌ NonCommercial | Yes | ShareAlike, NC | **RED** | mio | 2026‑07‑15 |
| **BDD100K** | UC Berkeley | bdd-data.berkeley.edu | 100k videos/images | vehicles, person | Dashcam | Box/seg | UC Regents; **commercial needs BAIR Commons / OTL license** | ❌ w/o license | — | Restricted | **RED** | bdd | 2026‑07‑15 |
| **KITTI** | KIT/Toyota TI | cvlibs.net/datasets/kitti | ~15k img | car,van,truck,cyclist,pedestrian | AV/street | Box/3D | **CC BY‑NC‑SA 3.0** | ❌ | Yes | NC/SA | **RED** | (publisher) | *verify* |
| **Cityscapes** | Daimler/MPI/TUD | cityscapes-dataset.com | 25k img | vehicles/person | AV/street | Seg/box | Non‑commercial research license | ❌ | Yes | Restricted | **RED** | (publisher) | *verify* |
| **nuScenes / Waymo Open** | Motional / Waymo | nuscenes.org / waymo.com | large AV | vehicles/person | AV | 3D/box | **Non‑commercial** terms | ❌ | Yes | Restricted | **RED** | (publisher) | *verify* |
| **UA‑DETRAC** | Univ. sources | detrac‑db (mirrors) | ~140k frames | car,bus,van,others | **Fixed traffic camera** | Box | Research/academic (unclear commercial) | ❌/? | Yes | Unclear | **RED/YELLOW** | (publisher) | *verify* |
| **VisDrone / AI City Challenge** | Academic / NVIDIA | aiskyeye / nvidia AI City | large | vehicles | Drone / city cam | Box | Academic/challenge terms | ❌/? | Yes | Restricted | **RED/YELLOW** | (publisher) | *verify* |
| **Roboflow Universe traffic sets** | Community uploaders | universe.roboflow.com | varies | vehicle subsets | fixed/dashcam mixed | COCO/YOLO | **Per‑dataset** (many CC BY 4.0; some unclear) | per‑dataset | per‑dataset | per‑dataset | **YELLOW** (per‑dataset) | (each) | *verify each* |

### 7.2 Synthetic data (self‑generated preferred; pre‑rendered synthetic datasets are mostly non‑commercial)

| Source | Type | Engine/code license | Asset license | Generated‑output rights | Classes attainable | Status | Evidence | Verified |
|---|---|---|---|---|---|---|---|---|
| **CARLA (self‑generate)** | Simulator we run | **MIT** (CARLA code) | **CC‑BY** (CARLA assets) | Our renders using CC‑BY assets; **embedded Unreal Engine EULA + per‑content‑pack asset terms also apply** — legal confirm | car,bus,truck,motorcycle,bicycle,pedestrian; intersections/highways; camera height/angle; day/night/rain/fog; occlusion; auto GT boxes | **YELLOW — strong candidate pending final licensing & asset‑rights approval** (code MIT + assets CC‑BY, **but UE EULA + maps + vehicle assets + third‑party packs + generated‑output rights + attribution each unverified**) | car1, car2 | 2026‑07‑15 |
| **Virtual KITTI 2** | Pre‑rendered dataset | — | — | **CC BY‑NC‑SA 3.0** (Naver) | vehicles | **RED** (non‑commercial) | vk2 | 2026‑07‑15 |
| **SYNTHIA** | Pre‑rendered dataset | — | — | **CC BY‑NC‑SA 3.0** | vehicles/person | **RED** (non‑commercial) | syn | 2026‑07‑15 |

**Synthetic conclusion:** downloadable synthetic *datasets* (VKITTI2, SYNTHIA) are non‑commercial (RED). **CARLA is a strong candidate for project‑generated synthetic traffic data, pending final licensing and asset‑rights approval** — *not* "definitely commercially safe." It offers automatic ground‑truth boxes + full control of camera height/angle, day/night, weather, density, occlusion, small/distant vehicles, but each layer (CARLA source code, CARLA assets, applicable **Unreal Engine EULA**, maps, vehicle assets, third‑party content packs, generated‑output rights, attribution) must be **verified separately** before production use. Because content packs may carry **different** licenses, the synthetic‑data provenance system **must record exactly which assets/content packs contributed to each generated `DatasetVersion`** (§8).

### 7.3 Own authorized data (future, `INTERNAL_AUTHORIZED`) — §7‑own / §33
Project‑collected or properly authorized traffic footage entering the same provenance + annotation + approval pipeline **after privacy/compliance review**. Owning software or camera access does **not** by itself grant rights to all recorded footage; legal/privacy compliance is tracked **separately** from technical ownership.

### 7.4 Architecture code licenses (weights NOT used — rev. 2)
**RT‑DETR (lyuwenyu)** Apache‑2.0 [rtd] · **YOLOX (Megvii)** Apache‑2.0 [yox] · **Ultralytics YOLOv5/v8/v11** **AGPL‑3.0** → **avoid** [ult]. We may reuse RT‑DETR/YOLOX **architecture code** (Apache‑2.0); **we do not use their pretrained weights** (rev. 2).

**Key finding:** commercially‑clean **fixed‑traffic‑camera** real datasets are scarce (MIO‑TCD, UA‑DETRAC non‑commercial/unclear; BDD commercial‑gated). The most promising broadly‑commercial **real** source is **Open Images V7** — but its **annotations are CC BY 4.0 while individual image rights need per‑image verification**, so the *complete usable training source* is **YELLOW**, not GREEN, until the images we actually select are verified. **No dataset is currently fully verified GREEN** (§7.5). The realistic first‑model composition (all YELLOW pending verification) is **Open Images V7 vehicle subset (image + annotation rights verified per §7.5) + self‑generated CARLA synthetic (rights‑approved) + authorized own footage over time** — see **D15**. Expect a **domain gap** vs deployment (e.g. Qatar); own data (§7.3/§33) is essential long‑term.

### 7.5 CURRENT COMMERCIAL TRAINING DATA READINESS
Stated honestly from verified evidence — **do not invent a GREEN dataset to make the plan look complete**:
- **Fully approved (GREEN) datasets available now: NONE.** No dataset has been verified at primary source as commercially usable across **all** required layers (media + annotations + source terms) for our intended use.
- **Candidate datasets pending verification (YELLOW):** Open Images V7 (annotations CC BY 4.0 ✓; **per‑image image rights unverified**); self‑generated **CARLA** synthetic (code MIT + assets CC‑BY; **UE‑EULA + asset/pack rights unverified**); Roboflow Universe per‑dataset; COCO (annotations CC BY 4.0; images Flickr terms); UA‑DETRAC/VisDrone.
- **Rejected / non‑commercial (RED):** MIO‑TCD, Virtual KITTI 2, SYNTHIA, KITTI, Cityscapes, nuScenes, Waymo, BDD100K (commercial‑gated).

**Consequence:** this does **not block Phase 6** (detection infrastructure needs no dataset). It means **Phase 6T has a MANDATORY dataset‑rights gate** that must clear **before any production training data is downloaded or the first production‑model training run starts.** If, after verification, no single sufficiently‑large source clears, the multi‑source composition (D15) + a filtered approved subset (§7.6) + own data is the path; **zero cost must never override verified usage rights.**

### 7.6 Open Images filtered‑subset feasibility (Phase 6T; verify before relying on it)
Open Images publishes per‑image license metadata (image‑level license field). Phase 6T should **evaluate** building a **filtered approved subset** admitting only images whose per‑image license metadata is acceptable for our commercial use **and** whose annotations are CC BY 4.0. **Do not assume the metadata is sufficient** — confirm the official terms and the field's authority before treating any filtered subset as approved; the sample‑level gate (§8/D5) records the resulting per‑image status.

*Sources:* og1 storage.googleapis.com/openimages/web/factsfigures_v7.html · mio tcd.miovision.com · bdd bdd-data.berkeley.edu, github.com/ucbdrive/bdd100k/LICENSE · rtd github.com/lyuwenyu/RT-DETR/LICENSE · yox github.com/Megvii-BaseDetection/YOLOX/LICENSE · ult ultralytics.com/license · car1 github.com/carla-simulator/carla/LICENSE · car2 carla.org (assets CC‑BY; UE EULA) · vk2 europe.naverlabs.com/proxy-virtual-worlds-vkitti-2 · syn synthia-dataset.net. **Every GREEN/YELLOW/RED call requires formal legal sign‑off before production training (Phase 6T); items marked *verify* were not confirmed at primary source this session.**

---

## 8. DATASET PROVENANCE ARCHITECTURE (Phase 6T; design only) — hybrid DB + immutable manifests
New `apps.datasets` (or `ml/registry`) — **hybrid** DB + **immutable** on‑disk manifests:
- **DB:** `Dataset(name, publisher, official_source_url, internal_key)`; `DatasetLicense(spdx_id, license_text_snapshot_ref, commercial_permission_status, attribution_required, redistribution_restrictions, modification_requirements)`; `DatasetVersion(dataset, version, download_date, image_count, annotation_count, annotation_format, class_schema_ref, manifest_hash, approval_status∈7‑status, approved_by, approved_at)`; `DatasetImport(dataset_version, imported_count, validation_report_ref, started/finished)`.
- **Immutable manifests (files, hashed):** content‑addressed, never rewritten. **Per training sample** the manifest retains: source `DatasetVersion`, **original media identifier**, **media license/status** (where item‑level rights apply), **annotation source**, **annotation license/status**, **canonical class‑mapping version**, **file checksum**, **split assignment**, and **production‑eligibility status** (media + annotation + source‑terms + obligations, per §6). For uniformly‑licensed datasets the media/annotation status is inherited from the `DatasetVersion` (not duplicated per file); for mixed‑license sources (e.g. Open Images per‑image, CARLA per content pack) it is recorded per item.

**Full model‑provenance chain (must be answerable for every production model):**
`AIModelVersion → TrainingRun (§43) → TrainingRecipe → DatasetVersion(s) → exact split manifest hashes → resulting ModelArtifact`.
Every training **sample retains its originating `DatasetVersion`** (via the split manifest), so we can prove exactly which approved data contributed to a model version. No image binaries in Postgres — metadata/provenance only. **Not built in Phase 6.**

---

## 9. MODEL ARCHITECTURE ANALYSIS → D3
- **Option A (recommended): existing Apache‑2.0 architecture, our training.** RT‑DETR or YOLOX. Lowest correctness risk, mature ONNX export, permissive for closed commercial, genuine ownership of *our trained weights*.
- **Option B: re‑implement a published architecture ourselves.** High effort + correctness risk; ownership benefit marginal over A (Apache‑2.0 already permits modification/closed distribution). Reserve for later differentiation.
- **Option C: novel architecture.** Rejected for Phase 6 — novelty for its own sake adds training‑stability and schedule risk without commercial benefit; a project‑trained model on a public architecture is already genuinely "our model."

**Recommend Option A with YOLOX** as the first architecture (anchor‑free, simple to train from scratch, n/s/m fit 8 GB, decoupled head, strong small‑object recall with mosaic aug, robust ONNX/TensorRT export). **RT‑DETR** is the strong alternative (better accuracy, heavier to train from scratch on 8 GB). Final pick is confirmed by the Phase 6 benchmark.

---

## 10. PRETRAINED‑WEIGHTS POLICY → D4 (rev. 2 — no third‑party weights by default, anywhere)
**Recommend: NO third‑party pretrained detector weights are downloaded or used anywhere in Phase 6 or Phase 6T by default** — not for production, and **not for benchmarking**. This explicitly excludes YOLOX, YOLO, RT‑DETR, COCO‑pretrained, and any other third‑party detector weights. **Architecture code and pretrained weights are separate issues:** we **may** reuse a commercially‑compatible open **architecture implementation** (Apache‑2.0 YOLOX/RT‑DETR code) but train its **weights ourselves from random initialization**.
- Phase 6 needs **no** third‑party detector to build/test the infrastructure — it uses a **clearly‑labelled deterministic test provider / project‑created test artifact** (fixed synthetic boxes), which **proves the pipeline, not AI accuracy** (§31).
- The first real weights are **project‑trained from random init** on approved data in **Phase 6T** (`provenance=platform_trained`).
- Consequences of from‑scratch: more data, longer training, harder convergence, lower initial accuracy — accepted for provenance control; mitigated by multi‑dataset composition (§5‑correction/D15), synthetic data (§7.2), iterative training (§32), and owned data (§7.3/§33).
- **Any use of third‑party pretrained weights (even for a one‑off internal accuracy baseline) requires an explicit, separately‑approved exception** and would be recorded with `provenance=pretrained` and never promoted to `active`. No weights downloaded during planning.

---

## 11. AI FRAMEWORK ANALYSIS → D2
| | Training | Runtime inference |
|---|---|---|
| **PyTorch 2.x + torchvision** | ✅ best ecosystem, custom‑arch flexibility, Windows+CUDA on RTX 3070, BSD‑style license | heavy (unsafe pickle checkpoints; large dep) |
| **ONNX Runtime** | ✗ (not a trainer) | ✅ **light, MIT, CPU+CUDA, safe (no pickle), portable, decouples runtime from torch** |
| TensorFlow / JAX | weaker Windows/custom‑detector story for this use | — |

**Recommend: PyTorch (+torchvision) for the training environment; ONNX Runtime for the production CV runtime.** Train in torch → export to ONNX → the standalone CV runtime loads only `onnxruntime`. This keeps heavy training deps out of production, avoids pickle‑based model loading in the runtime, and stays portable to rented Linux GPUs. Global torch is irrelevant to the decision (only evidence CUDA works). *Windows caveat:* `onnxruntime-gpu` needs matching CUDA/cuDNN runtime; CPU `onnxruntime` always works — validate the CUDA EP during implementation.

---

## 12. TRAINING vs RUNTIME SEPARATION → D9
Clean boundary:
- **Production runtime** (`apps.processing` CV runtime): add **`onnxruntime` (CPU)** and optionally `onnxruntime-gpu` to `requirements/base.txt` (or a `requirements/runtime-ml.txt`). No torch.
- **Training environment**: a new **top‑level `ml/` package** (NOT a Django app) with its own venv + `ml/requirements-train.txt` (torch, torchvision, pycocotools, albumentations, onnx, tensorboard). CLI‑driven; never imported by Django/Celery. Reads approved datasets, writes checkpoints + exports ONNX artifacts registered into the governance registry.
Recommend `ml/` (training/tooling) + `onnxruntime` in the runtime. Do not place training inside a Django app.

---

## 13. HARDWARE CONSTRAINTS (RTX 3070 Laptop, 8 GB VRAM)
Realistic: YOLOX‑S/M at 640 with batch 8–16 (S) / 4–8 (M) using **mixed precision (AMP)** + **gradient accumulation**; larger models/resolutions need accumulation and are slow. From‑scratch YOLOX on a large dataset = **many hours–days per experiment** locally; expect multiple experiments. Bottlenecks: 8 GB VRAM, Windows `DataLoader` worker overhead, disk I/O on large datasets. Architecture must support **local dev training + portable rented‑GPU training** (same code, larger batch) **without any external AI API**; artifacts (ONNX + checkpoints + recipe) remain portable back. Do not promise production accuracy from local runs.

---

## 14. MODEL‑SIZE STRATEGY → (feeds D3)
Start **small/medium (YOLOX‑S first, YOLOX‑M as stretch)** — reliable training, real‑time/near‑real‑time inference, fits 8 GB, adequate fixed‑camera accuracy. Not the largest model. The benchmark measures S vs M for the profile table.

---

## 15. INPUT RESOLUTION
Evaluate **640×640** (default/Balanced), **960×960** (Quality, small/distant vehicles), lower (Performance). **Aspect‑ratio‑preserving letterbox** (pad, record scale+pad to invert boxes) — never distort‑resize. Tiling deferred (only if 1080p distant‑vehicle recall demands it; not Phase 6). Small‑object recall vs VRAM/speed measured by the benchmark.

---

## 16. CLASS TAXONOMY → D8
Canonical **`TrafficClassTaxonomy v1` = {CAR, BUS, TRUCK, MOTORCYCLE, BICYCLE, PEDESTRIAN}** (matches frozen §19). PEDESTRIAN = bbox only (no recognition/identification, frozen §32). Versioned mapping table (dataset label → canonical), e.g. `motorbike→MOTORCYCLE`, `person→PEDESTRIAN`, `van/pickup→` policy‑defined (default `CAR`/`TRUCK` per approved rule, never silently dropped; ambiguous labels logged). Taxonomy + mappings versioned (`taxonomy_version` in `class_map`/dataset schema). Stored in the governance `class_map` + (Phase 6T) dataset class‑schema.

---

## 17. ANNOTATION FORMAT → D7
**Canonical internal = COCO JSON** (established, framework‑agnostic, rich tooling via `pycocotools`). Import adapters convert source formats (YOLO txt, Pascal VOC, Open Images CSV) → COCO; export adapters convert COCO → the trainer's format (YOLOX). **Original downloaded annotations kept immutable**; conversions write new files. Decouples the dataset layer from any one trainer.

---

## 18. DATASET SPLIT STRATEGY (Phase 6T)
Manifest‑based, deterministic seed, bound to `DatasetVersion`, split hashes recorded. **Leakage prevention:** for video‑derived data, split by **source video / camera / scene / location**, never random adjacent frames across train/test. Splits are files (train/val/test manifests) with content hashes; evaluation binds to a specific split hash.

---

## 19. DATASET VALIDATION (Phase 6T)
Pre‑training validation report: missing/corrupt images, invalid/out‑of‑bounds/zero‑area boxes, duplicate images (perceptual/exact hash) & annotations, class imbalance, tiny‑object stats, empty frames, label inconsistencies. **No blind training** — a validation report is a gate artifact linked to `DatasetImport`.

---

## 20. DATASET STORAGE
Configurable **dataset root separate from `VIDEO_STORAGE_ROOT`/`ARTIFACT_ROOT`** (env `DATASET_ROOT`, external‑drive friendly). Manifests + content hashes; **no dataset binaries in Git or Postgres**; DB holds metadata/provenance only. No accidental redistribution (research/non‑commercial sets physically outside the repo, §6).

---

## 21. AUGMENTATION (Phase 6T)
Traffic‑appropriate: horizontal flip (valid for symmetric traffic), brightness/contrast/exposure, mild blur/noise, weather‑like (rain/fog) sim, scale, crop, mosaic (YOLOX default), mild perspective. Avoid physically implausible transforms (vertical flip, extreme color shifts). **Augmentation config is part of the versioned training recipe** (§22).

---

## 22. TRAINING RECIPE / VERSIONING (Phase 6T)
Reproducible `TrainingRecipe`: architecture+version, code commit hash, dataset versions + split hashes, taxonomy version, input res, augmentation config, optimizer, LR schedule, epochs, batch, grad‑accum, seeds, framework+CUDA versions, hardware, metrics. **Integrates with the existing registry** — reuse `AIModel`/`AIModelVersion` (`provenance=platform_trained`, `config`=recipe, `benchmark_summary`=metrics, `class_map`=taxonomy) + `ModelArtifact` (weights/config/labels) + `ModelEvaluation`; add a `TrainingRun` (§43) for run‑level provenance. **No second registry.**

---

## 23. DETECTOR OUTPUT CONTRACT → (feeds D10)
Framework‑independent `Detection` (dataclass, no tensors):
```
class_id: int              # canonical taxonomy id
canonical_class: str       # CAR/BUS/…
confidence: float
bbox: (x1,y1,x2,y2)        # CANONICAL = normalized XYXY in [0,1] (resolution-independent, letterbox-inverted)
```
A `FrameDetections` batch carries `session_id, video_id, source_frame_index, pts_seconds, model_version_id, taxonomy_version, detections[]`. Normalized XYXY chosen so results survive resolution changes and map onto ROIs/lines (image‑normalized) directly. Framework tensors never leave the detector.

---

## 24. DETECTION PERSISTENCE → D10
`FrameDetectionBatch` (one row per **processed** frame): `id, session(FK PROTECT), video(FK), model_version(FK PROTECT), source_frame_index, pts_seconds, taxonomy_version, detection_count, detections(JSONB), created_at`. **JSONB list of detections per frame** (not one row per box) — bounded writes, cheap to query, trivially consumable by Phase 7 tracking. Optional future: flush to a JSONL artifact for very long runs (recorded via `StoredArtifact`, category `DETECTION_METADATA`). Indexes `(session, source_frame_index)`. Preserves full source‑frame identity + model traceability. Bounded write cadence reuses the Phase‑5 batching mindset (one insert per processed frame; buffered/`bulk_create` per N frames).

---

## 25. DETECTOR PROVIDER INTERFACE
`DetectorProvider` (frozen §12 `DetectionProvider`): `load(model_version, device)`, `warmup()`, `preprocess(rgb_ndarray)->tensor+meta`, `detect(...)->list[Detection]` (canonical), `classes()`, `unload()`. A `DetectionFrameProcessor` implements the Phase‑5 `FrameProcessor` Protocol, owns a `DetectorProvider`, converts `view.as_rgb_ndarray()` once, runs inference, postprocesses (NMS + class map + letterbox inversion → normalized XYXY), and persists a `FrameDetectionBatch`. **No framework‑specific output leaks** past the provider. Registered in `_REGISTRY` as `"detector"`; selected via `processing_params.processor="detector"` (+ a new `detector` param block — extend `services/params.py`).

---

## 26. MODEL LOADING & GPU OWNERSHIP
Preserve frozen boundary: **Django never loads weights; general Celery workers never load weights; the standalone CV runtime owns the model.** Flow: runtime/session start → resolve the **approved ACTIVE** `AIModelVersion` for `task=detection` → validate `ModelArtifact` (checksum/size/format) → `GPUManager.select_device/reserve` → **load ONNX session once in `setup()`** → reuse across all frames/sessions → `unload()`/release on teardown/shutdown. **Never reload per frame.** Phase 6 = **one active detector model** (frozen §14 single‑model default); multi‑model deferred.

---

## 27. ARTIFACT SECURITY → (feeds D11)
Validate before load: checksum (`sha256_file` vs `ModelArtifact.checksum_sha256`), size, declared format, framework/opset compatibility, model‑version approval/deployment status, path via `validate_artifact_path` (no traversal). **Prefer ONNX** (data‑only graph) over pickle‑based torch checkpoints in the runtime — **never load arbitrary pickle** (arbitrary code execution). Document that torch `.pt`/`.pth` checkpoints are training‑only and never loaded by the production runtime. Reject unapproved / checksum‑mismatched / non‑ONNX artifacts.

---

## 28. CHECKPOINT vs DEPLOYMENT ARTIFACT → D11
- **Training checkpoint** (`ml/`): torch `.pth` (optimizer + weights + recipe) — training‑only, never in the runtime.
- **Deployment artifact**: **ONNX** (fixed opset, inference‑only), registered as `ModelArtifact(kind=weights)` + a `config`/`labels` artifact (taxonomy). The runtime loads only the minimal ONNX + labels. (TorchScript/native evaluated and rejected for the runtime due to torch dependency + pickle risk.)

---

## 29. EVALUATION STRATEGY
Objective metrics via `pycocotools`: precision/recall, **mAP@0.5**, **mAP@0.5:0.95**, per‑class AP, small/medium/large AP; plus latency (pre/inf/post), throughput, VRAM. **Traffic slices:** day/night, weather (where labelled), near vs distant vehicles, occlusion, dense traffic. Never approve on one aggregate mAP. Stored in `ModelEvaluation.metrics` (+ slice breakdown) with `dataset_ref`/split hash. **Phase 6 only exercises the evaluation harness with the deterministic test provider (mechanism check — NO real accuracy claim); real accuracy evaluation of the project‑trained model happens in Phase 6T.**

---

## 30. MODEL PROMOTION GATE
Reuse governance; add a lightweight lifecycle. Current registry has only `is_active` (one active per family). **Add `AIModelVersion.status ∈ {training, evaluated, candidate, approved, active, retired}`** (additive field; `is_active` remains the "currently loaded" flag, set only when `status=active`). Only **`approved`→`active`** versions are selectable for production processing; the activate endpoint gains a guard (must be `approved` first; benchmark/pretrained versions stay `candidate` and can never reach `active` for production). Promotion actions audited (extend EventTypes, §38).

---

## 31. FIRST‑MODEL STRATEGY → D13 (rev. 2)
- **A:** build training infra + train from scratch first (blocks detection integration on a long training effort).
- **B:** integrate detector infrastructure with a **deterministic project test provider**, train the real model later.
- **C:** use third‑party pretrained weights temporarily — **rejected by rev. 2** (no third‑party weights by default).
**Recommend B for Phase 6 + A for Phase 6T.** Phase 6 ships the full detection **infrastructure** (provider, ONNX backend, preprocess/postprocess, persistence, APIs, visualisation, benchmark harness) validated by a **clearly‑labelled `DeterministicTestDetector`** (emits fixed, reproducible boxes from a project‑created test artifact — **explicitly not a real detector; makes no AI‑accuracy claim**, excluded from production `_REGISTRY` promotion). The **first real project‑trained detector** (Strategy A: random‑init YOLOX/RT‑DETR architecture code, approved data) is produced in **Phase 6T** and is the first model that yields real accuracy/profile numbers. This honours frozen §20 (build the benchmark + selection mechanism now; populate real model profiles once project‑trained weights exist) **without faking AI and without any third‑party weights.**

**Benchmark consequence (frozen §20):** with no third‑party weights, Phase 6's benchmark harness produces **infrastructure/harness baselines** (decode+preprocess+postprocess+persistence latency, FPS/VRAM machinery, device‑policy behaviour) and the **profile‑selection mechanism**; the **real per‑model Quality/Balanced/Performance accuracy+FPS+VRAM profiles are populated in Phase 6T** against project‑trained weights. This is stated as an explicit, honest limitation, not hidden.

---

## 32. TRAINING‑FROM‑SCRATCH FEASIBILITY (Phase 6T)
Realistic: minimum useful data ≈ tens of thousands of labelled traffic frames across day/night/weather; first from‑scratch YOLOX‑S likely **modest mAP**, needing several experiments (LR/aug/epochs) and likely rented GPU for full‑scale runs. Local RTX 3070 = prototyping + small runs; expect iteration over weeks, not one run. Plan iterative improvement; do **not** guarantee commercial‑grade accuracy from run 1.

---

## 33. CUSTOM / OWN‑DATA STRATEGY (future, `INTERNAL_AUTHORIZED`)
Public commercial data (Open Images) won't match deployment (e.g. Qatar) viewpoints/vehicles/signage. Path for **project‑owned data** entering the **same provenance + annotation + approval pipeline** (§8):
`authorized footage → frame extraction → privacy/compliance review (where required) → annotation → DatasetVersion → quality validation → training approval (INTERNAL_AUTHORIZED) → retraining`.
**Owning software or having camera access does NOT by itself grant unrestricted rights** to all recorded footage. **Legal/privacy compliance is tracked separately from technical ownership** (a distinct compliance/authorization record per footage source; frozen §32 privacy rules — no face/person recognition, pedestrian bbox‑only). Only footage that passes authorization + privacy review reaches `INTERNAL_AUTHORIZED`. Domain adaptation/fine‑tuning on owned data is the long‑term accuracy lever.

---

## 34. ACTIVE‑LEARNING FUTURE HOOK
Preserve (do not build) a hook: production inference → low‑confidence/hard cases flagged → human review → approved annotations → new `DatasetVersion` → retrain. Phase 6 only ensures detections carry confidence + frame identity so hard‑example mining is later possible.

---

## 35. DETECTION VISUALISATION (frontend)
Phase 6 UI: enable a detection‑processor session; a frame/image preview with **bounding boxes + canonical class + confidence + model version**; per‑frame detection counts for inspection. **No tracking trails** (Phase 7). **Never present raw per‑frame detections as unique vehicle counts** (explicit UI copy: "per‑frame detections, not counts").

---

## 36. API DESIGN
- `GET /api/v1/processing-sessions/{id}/detections?frame=&from_ts=&to_ts=` — paginated `FrameDetectionBatch` (large sets → cursor/page pagination, bounded page size).
- `GET /api/v1/processing-sessions/{id}/detections/{frame_index}`.
- Reuse governance `/api/v1/governance/model-versions` for active detector + metadata + evaluations.
Never expose training paths, dataset filesystem paths, unsafe artifacts, or secrets. Detections read‑only via API.

---

## 37. PERMISSIONS
Detections (view): admin/operator/analyst (as Phase‑5 read set); **viewer excluded** (raw‑video‑derived). Start detection‑enabled processing: admin/operator (Phase‑5 control set). **Model governance is stricter:** view model metadata = admin roles; **register/promote/activate model versions = system_admin only** (existing rule); dataset management + **dataset license approval = system_admin only** (Phase 6T). Training runs = system_admin (Phase 6T). Model governance > ordinary video processing.

---

## 38. AUDIT
Add EventTypes (audit app): `MODEL_VERSION_REGISTERED, MODEL_EVALUATION_RECORDED, MODEL_APPROVED, MODEL_RETIRED` (reuse existing `MODEL_ACTIVATED/DEACTIVATED`); Phase 6T adds `DATASET_REGISTERED, DATASET_LICENSE_CHANGED, DATASET_VERSION_APPROVED, TRAINING_STARTED, TRAINING_COMPLETED, TRAINING_FAILED`. **Never audit per‑frame or per‑detection.** Bounded metadata (ids, hashes, outcome, metrics summary).

---

## 39. OBSERVABILITY
Add to the strict allowlist (counters/summaries, bounded labels): `detector_inference_ms` (summary), `detector_preprocess_ms`, `detector_postprocess_ms`, `detection_frames_total` (counter), `detection_failures_total{reason}`, `model_load_failures_total{reason}`, `detector_gpu_mem_mb` (summary), and optionally `detections_total{canonical_class}` (bounded: 6 classes). **No `model_version_id` as an unbounded label** — per‑version detail lives on the session/registry.

---

## 40. FAILURE HANDLING (distinct codes; empty ≠ failure)
`no_active_model`, `model_artifact_missing`, `model_checksum_mismatch`, `model_incompatible`, `model_load_failed`, `gpu_unavailable`, `gpu_oom`, `cpu_fallback_unavailable`, `inference_failed`, `invalid_output` (NaN/Inf/shape), `preprocess_failed`, `detection_persist_failed`. Session → `FAILED(error_code)` (reuse Phase‑5 state machine). **A frame with zero detections is a valid result (persisted, count=0); an inference failure is a distinct FAILED state** — never silently return empty on failure.

---

## 41. CPU FALLBACK → D12
Device policy `CV_DETECTOR_DEVICE_POLICY ∈ {REQUIRE_GPU, PREFER_GPU, CPU_ONLY}`. **Recommend `PREFER_GPU` default** (GPU if available+fits, else explicit CPU) but **never silently** fall back on a long job — a GPU→CPU switch is logged, audited, surfaced on the session (`device`), and configurable to hard‑fail (`REQUIRE_GPU`). Phase 6 detector **must** support CPU inference (dev/recovery) via ONNX Runtime CPU EP.

---

## 42. TRAINING PIPELINE (Phase 6T; design only)
`approve dataset → import → validate → convert to COCO → class‑map → split → configure recipe → train (torch, checkpointed) → evaluate → export ONNX → register ModelArtifact + AIModelVersion(platform_trained) → evaluate slices → promote`. **Django/Celery never run GPU training** — a separate `ml/` CLI/runtime does. Restartable/checkpointed for long runs.

---

## 43. TRAININGRUN DECISION (Phase 6T) → (feeds D6)
Add a light **`TrainingRun`** (in `ml/registry` or governance): `id, architecture, target_model_version(FK), dataset_manifest_ref, recipe(JSON), status, started/finished, hardware, framework_versions, metrics, checkpoint_artifact, final_artifact, failure_reason`. Reuse `AIModelVersion`/`ModelArtifact`/`ModelEvaluation` for the results; `TrainingRun` adds run‑level provenance without duplicating the registry.

---

## 44. TRAINING COMMANDS (Phase 6T)
`python -m ml.validate_dataset`, `python -m ml.train`, `python -m ml.evaluate`, `python -m ml.export` (→ ONNX + register). Checkpointable/resumable; the web app need not run during training.

---

## 45. WINDOWS CONSIDERATIONS
Training: torch+CUDA on Windows OK; **`DataLoader` `num_workers` fragile on Windows** (guard with `if __name__=="__main__"`, modest workers); path handling via `pathlib`; resume‑after‑interruption via checkpoints; VRAM monitoring via `nvidia-smi`/`torch.cuda`; AMP mixed precision. Runtime: `onnxruntime` CPU always works; `onnxruntime-gpu` CUDA/cuDNN validated on Windows during implementation. Keep everything portable to Linux/cloud GPU.

---

## 46. DEPENDENCIES / LICENSES
| Dep | Version (proposed) | Purpose | License | Scope | Windows |
|---|---|---|---|---|---|
| onnxruntime | ~1.19 (CPU) | production inference | MIT | **runtime** | ✅ |
| onnxruntime-gpu | ~1.19 | GPU inference (optional) | MIT | runtime (opt) | ✅ (CUDA EP) |
| torch | 2.x (cu12x) | training | BSD‑style | **training‑only** | ✅ |
| torchvision | matches torch | ops/aug | BSD | training‑only | ✅ |
| onnx | ~1.16 | export | Apache‑2.0 | training‑only | ✅ |
| pycocotools | ~2.0 | COCO eval | BSD/FiftyOne | training‑only | ✅ |
| albumentations | ~1.4 | augmentation | MIT | training‑only | ✅ |
| tensorboard | ~2.x | training viz | Apache‑2.0 | training‑only | ✅ |
| YOLOX (architecture) | pinned commit | detector arch | **Apache‑2.0** | training‑only (adapted) | ✅ |

**Review code / weights / dataset licenses SEPARATELY** (a repo's code license ≠ its weights ≠ any dataset). Only `onnxruntime` (+ optional GPU) touches distributed production software; all training deps are training‑only. **No install during planning.**

---

## 47. REPOSITORY CHANGES EXPECTED
**Phase 6:** new `apps/processing/runtime/detector/` (provider, preprocess, postprocess, onnx_backend, mock), `DetectionFrameProcessor` + registry/params extension; new `FrameDetectionBatch` model + migration + retention handler (`DETECTION_METADATA`) + serializer/views/urls (detections API); governance `AIModelVersion.status` field + migration + promotion guard + new EventTypes (audit migration); `benchmark/` harness + report; `requirements/base.txt` (+onnxruntime); frontend detection viewer + processingApi extension; ADR‑028/031/032; settings (`ARTIFACT_ROOT` confirm, `CV_DETECTOR_*`). **Phase 6T (separate):** `apps/datasets` or `ml/registry`, `ml/` training package + `ml/requirements-train.txt`, `TrainingRun`, dataset governance, ADR‑029/030.

---

## 48. MODELS / MIGRATIONS EXPECTED
Phase 6: `processing` (or new `detection` app) `FrameDetectionBatch` migration; `governance` `AIModelVersion.status` (+ optional `deployment_status`) migration; `audit` EventType choices migration. Additive; clean from empty DB; `aitraffic_app` non‑superuser; no historical edits. (Phase 6T: dataset + TrainingRun migrations.)

---

## 49. ADRs (next = ADR-028)
Phase 6: **ADR‑028 Detector Architecture & AI Framework** (YOLOX/RT‑DETR, torch‑train + ONNX‑runtime), **ADR‑031 Detection Result Storage** (`FrameDetectionBatch`, normalized‑XYXY, JSONB), **ADR‑032 Model Deployment Artifact & Runtime Loading** (ONNX, checksum, one‑load, GPU ownership). Phase 6T: **ADR‑029 Training‑Data Governance & Provenance**, **ADR‑030 Model Training & Weight‑Provenance Policy**. Per repo convention, ADRs are **written during implementation** to match what ships (not drafted now).

---

## 50. TESTING STRATEGY (Phase 6)
Frame integration (NumPy canonical contract, letterbox + inverse, normalized‑XYXY correctness); detector provider (ONNX load, canonical output, **empty‑valid vs failure distinct**, device policy, load‑once/reuse/release); mock detector deterministic; detection persistence (frame/timestamp/session/model traceability, JSONB shape, large‑set pagination); governance (only `approved`→`active` selectable; checksum validation; unsafe/non‑ONNX rejected); runtime (model loaded once, reused, released; PREFER_GPU/REQUIRE_GPU/CPU_ONLY); security (unsafe artifact rejection; permission matrix; viewer excluded); **regression: all 245 green, none weakened**. Phase 6T adds dataset‑governance/import/split‑leakage/validation tests.

---

## 51. FAILURE TESTING (Phase 6)
Missing/corrupt/wrong‑checksum/wrong‑opset model; GPU unavailable; simulated OOM; inference exception; invalid array shape / NaN‑Inf output; persistence failure; no active approved model; CPU‑fallback‑unavailable under REQUIRE_GPU. Each → distinct `error_code`, session FAILED, no fake empty result.

---

## 52. PERFORMANCE VALIDATION
**Phase 6 (infrastructure):** benchmark harness on **real traffic footage** (not synthetic CFR): 720p + 1080p, day + night (if available), dense traffic, small/distant vehicles. Measure preprocess/postprocess/persistence latency, decode+harness FPS, VRAM machinery, device‑policy behaviour — using the `DeterministicTestDetector` (fixed inference cost) to validate the **end‑to‑end pipeline and profile‑selection mechanism**. No third‑party weights. **Phase 6T (real model):** re‑run the harness against the project‑trained ONNX model per size (YOLOX‑S/M, optionally RT‑DETR) × resolution (640/960) × stride → the real **Quality/Balanced/Performance** profile table + default selection with accuracy metrics. No targets before measuring. (Provide 1–3 short clips with the right to use; document source.)

---

## 53. SECURITY CONSIDERATIONS
No pickle loading in runtime (ONNX only); artifact checksum + path‑traversal validation; model management system_admin‑only; dataset license approval system_admin‑only (6T); no filesystem/training paths or secrets in APIs; detections read‑only; frozen §32 (no face/person recognition, no plate OCR) — pedestrian is bbox‑only; research/non‑commercial datasets physically separated from the repo.

---

## 54. IMPLEMENTATION ORDER (Phase 6; 6T gated separately)
1 verify baseline → 2 reconcile scope → 3 D2 framework → 4 D3 architecture → 5 D4 weights policy → 6 D10 detection storage → 7 D11 artifact/ONNX → 8 D12 device policy → 9 taxonomy/annotation decisions → 10 finalize ADR‑028/031/032 → 11 `FrameDetectionBatch` + migration + retention handler → 12 `AIModelVersion.status` + promotion guard → 13 `DetectorProvider` + ONNX backend + mock → 14 preprocess/letterbox + postprocess/NMS + class‑map → 15 `DetectionFrameProcessor` + registry/params → 16 detection persistence + APIs + permissions → 17 governance activation guard → 18 audit/observability → 19 frontend viewer → 20 benchmark harness → 21 real‑footage benchmark → 22 failure tests → 23 full regression → 24 verification report. **Phase 6T** (separate approval): dataset governance → provenance → import/validate/split → training pipeline → from‑scratch train → evaluate → register `platform_trained` → promote.

---

## 55. ACCEPTANCE CRITERIA (Phase 6) — rev. 2
All 245 tests green; frozen scope honoured (detection **infrastructure** + benchmark harness; **no training, no production model frozen**); AI‑framework + architecture + pretrained‑policy decisions documented (ADRs); **NO third‑party pretrained detector weights downloaded or used anywhere** (including benchmarking); the test detector is clearly labelled deterministic and **makes no AI‑accuracy claim** and cannot be promoted to `active`; canonical taxonomy versioned; canonical annotation format defined; `DetectorProvider` returns framework‑independent detections; detections retain frame/timestamp/session/model traceability; artifacts checksum‑validated; only `approved`→`active` versions selectable for production; Django/general‑Celery never load weights; CV runtime owns loading; model loaded once (not per frame); empty vs failure distinguishable; benchmark harness produces infrastructure baselines + profile‑selection mechanism (real per‑model profiles deferred to 6T); full regression passes. **Phase 6T criteria (when that phase runs):** production‑training gate enforced **in the pipeline** (only `APPROVED_COMMERCIAL`/`APPROVED_WITH_OBLIGATIONS`/`INTERNAL_AUTHORIZED`/`SYNTHETIC_APPROVED`); split‑leakage controls verified; recipe reproducible; `TrainingRun` recorded; every sample retains dataset provenance; **weights trained from random init** (no third‑party weights) and registered with exact provenance chain (§8); evaluation with traffic slices recorded; real traffic footage + approved synthetic used; no external AI API; no unauthorized/unapproved dataset.

---

## 56. VERIFICATION PROCEDURE
`backend/.venv` (3.12.9) active → `pytest -q` (≥245) → `pytest --create-db` (clean migration) → `makemigrations --check` clean → `ruff check .` clean → frontend `tsc --noEmit` + `next build` clean → run CV runtime with a detector session on a real clip, verify boxes/classes/confidence + `FrameDetectionBatch` traceability + one‑load → run benchmark harness, record profile table → failure‑injection matrix → produce `PHASE_6_VERIFICATION_REPORT.md`.

---

## 57. KNOWN RISKS (rev. 2)
1. **Scope creep training→Phase 6** — mitigated by the §2 split (6T separate).
2. **Insufficient commercially‑cleared training data — NO fully verified GREEN dataset exists today (§7.5).** Open Images (per‑image rights) and CARLA (UE‑EULA/asset rights) are YELLOW pending verification; fixed‑camera sets (MIO‑TCD, VKITTI2, SYNTHIA) are non‑commercial; BDD is commercial‑gated. **Mitigation:** mandatory Phase 6T dataset‑rights gate before any production download/training; multi‑source composition (D15) + Open Images filtered approved subset (§7.6) + owned data (§33); direct owner permission where useful. **Zero cost must never override verified usage rights.** Does not block Phase 6 (infrastructure needs no dataset).
3. **From‑scratch accuracy risk on 8 GB with no pretrained baseline** — higher than with pretrained; mitigated by multi‑dataset + synthetic composition (D15), iterative training, and rented GPU. **Explicit consequence of the no‑pretrained policy** — first models will be weaker and need iteration.
4. **CARLA generated‑data rights** — CARLA code MIT + assets CC‑BY, **but Unreal Engine EULA + asset attribution apply**; requires legal confirmation before production training (do not assume generated data is unrestricted).
5. **onnxruntime‑gpu Windows CUDA/cuDNN matching** — validate CUDA EP; CPU EP fallback always works.
6. **Legal overclaim on weight/data ownership** — precise "project‑trained" language + "not legal advice" + formal review gate before any commercial claim; every dataset layer (image/annotation/code/weights) reviewed separately.
7. **ONNX export fidelity** (train‑vs‑export parity) — verify parity in evaluation.
8. **Detection write volume** on long/every‑frame runs — JSONB‑per‑frame + optional artifact flush + sampling.
9. **AGPL contamination** — Ultralytics explicitly excluded; only Apache‑2.0 **architecture code** (no third‑party weights at all).
10. **Benchmark without a real model** — Phase 6 benchmark yields infra/harness baselines only; real model profiles depend on Phase 6T weights (stated openly, not hidden).

---

## 58. ESTIMATED EFFORT
- **Phase 6 (frozen: detection + benchmark + profiles):** ~**9–14 developer‑days** (frozen est. 5/9/16) — detector provider + ONNX backend + processor + persistence + governance guard + benchmark + frontend + tests.
- **Phase 6T (training‑data governance + first from‑scratch model):** ~**15–30+ developer‑days engineering + substantial GPU training wall‑clock** (dataset licensing/approval, provenance domain, import/validate/split, training pipeline, multiple from‑scratch experiments, likely rented GPU). Larger and dataset‑gated; not in the frozen roadmap.

---

## Decisions Recommended for Approval

### D1 — Frozen Phase 6 Scope
- **Options:** (a) frozen = detection provider + benchmark + profiles; (b) expand to include dataset governance + from‑scratch training.
- **Recommend (a).** Implement detection integration + benchmark + profile selection; **move dataset governance + first‑model training into a new explicit "Phase 6T."**
- **Rationale:** frozen roadmap has no training phase; §2's own rule says preserve frozen scope and defer extras. **Tradeoff:** production‑owned weights arrive in 6T, not 6. **Consequence:** Phase 6 stays shippable in ~2 weeks; ownership goal preserved as a first‑class explicit phase.

### D2 — AI Framework
- **Options:** PyTorch, TensorFlow, JAX; runtime torch vs ONNX Runtime.
- **Recommend: PyTorch (+torchvision) for training (in `ml/`), ONNX Runtime for the production runtime.** torch not in production.
- **Rationale:** best custom‑detector ecosystem + Windows/CUDA; ONNX Runtime is light, MIT, safe (no pickle), CPU+CUDA, portable. **Tradeoff:** an export step (torch→ONNX). **Consequence:** production runtime stays lean; portable to rented Linux GPUs.

### D3 — Detector Architecture (rev. 2)
- **Options:** A existing Apache‑2.0 **architecture code** trained by us from scratch; B re‑implement; C novel.
- **Recommend A — reuse YOLOX (Apache‑2.0) architecture code** (RT‑DETR Apache‑2.0 alternative); **exclude Ultralytics (AGPL‑3.0)**; **use the code only — NOT its pretrained weights** (D4). Confirm final pick in Phase 6T training.
- **Rationale:** commercial‑safe code, trainable from random init on 8 GB, mature ONNX export, genuine ownership of *our* trained weights. **Tradeoff:** YOLOX slightly below RT‑DETR accuracy; from‑scratch is harder without pretrained init. **Consequence:** clean path to project‑trained weights + real‑time inference.

### D4 — Pretrained Weights (rev. 2 — REVERSED)
- **Options:** (A) random‑init only, no third‑party weights anywhere; (B) allow approved pretrained for benchmark; (C) allow pretrained for production.
- **Recommend A:** **no third‑party pretrained detector weights downloaded or used anywhere in Phase 6 or 6T by default** (excludes YOLOX/YOLO/RT‑DETR/COCO weights). Architecture **code** may be reused; its **weights may not**. First production weights = **random init `platform_trained`** (6T). Phase 6 uses a **deterministic test provider** (no weights). Any pretrained use = explicit separate exception, `provenance=pretrained`, never `active`.
- **Rationale:** maximal weight‑provenance control + ownership goal. **Tradeoff:** weaker/slower first models; benchmark yields infra baselines only until 6T. **Consequence:** fully defensible weight provenance; no third‑party‑weight dependency.

### D5 — Dataset Policy (rev. 2)
- **Recommend: seven‑status gate** — production pool = `APPROVED_COMMERCIAL` / `APPROVED_WITH_OBLIGATIONS` / `INTERNAL_AUTHORIZED` / `SYNTHETIC_APPROVED`; reject `RESEARCH_ONLY` / `LICENSE_UNCLEAR` / `REJECTED`. **Enforced in the training pipeline itself, not just the UI.** Non‑approved data physically excluded from the repo; authoritative license from the **original publisher**; each dataset layer (image/annotation/code/weights) reviewed separately; per‑dataset legal sign‑off. (Enforced in 6T.)
- **Rationale/Tradeoff/Consequence:** prevents contamination; more upfront diligence; reproducible, auditable, pipeline‑enforced provenance.

### D6 — Dataset Provenance (rev. 2)
- **Options:** DB registry, manifest‑only, hybrid.
- **Recommend: hybrid** — DB (`Dataset`/`DatasetLicense`/`DatasetVersion`/`DatasetImport`) + **immutable content‑addressed manifests** (files, checksums, source, class mapping, split), with the full chain `AIModelVersion → TrainingRun → recipe → DatasetVersion(s) → split manifest hashes → artifact`; **every sample retains its DatasetVersion**. (6T.)
- **Rationale:** proves exactly which approved data trained each model without image blobs in Postgres. **Tradeoff:** more records/manifests. **Consequence:** provable, immutable lineage.

### D7 — Canonical Annotation Format
- **Recommend: COCO JSON** internal; adapters import/export; originals immutable.
- **Rationale:** established, framework‑agnostic, `pycocotools` eval. **Tradeoff:** conversion adapters. **Consequence:** trainer‑independent dataset layer.

### D8 — Canonical Class Taxonomy
- **Recommend v1 = {CAR, BUS, TRUCK, MOTORCYCLE, BICYCLE, PEDESTRIAN}** (matches frozen §19), versioned, with versioned source‑label mappings; pedestrian bbox‑only (no recognition).
- **Rationale/Tradeoff/Consequence:** matches frozen taxonomy; ambiguous labels mapped by policy, never dropped; stable analytics semantics across model swaps.

### D9 — Training Environment
- **Recommend: separate `ml/` package + own venv/`requirements-train.txt`; runtime gets only `onnxruntime`.** Not inside a Django app.
- **Rationale:** keeps heavy training deps out of production; clean boundary. **Tradeoff:** two environments. **Consequence:** portable training, lean runtime.

### D10 — Detection Storage
- **Recommend: `FrameDetectionBatch` (one row per processed frame) with JSONB detections (normalized XYXY + class + confidence)**, FKs to session/video/model_version, indexed by (session, frame_index); optional artifact flush for very long runs.
- **Rationale:** bounded writes, easy Phase‑7 consumption, full traceability. **Tradeoff:** JSONB vs fully‑normalized rows. **Consequence:** no per‑box row explosion; scales to tracking.

### D11 — Deployment Artifact
- **Recommend: ONNX** (inference‑only, fixed opset) loaded by `onnxruntime`; torch checkpoints training‑only, never in runtime.
- **Rationale:** portable, safe (no pickle), CPU+CUDA. **Tradeoff:** export/parity step. **Consequence:** secure, framework‑independent runtime.

### D12 — Device Policy
- **Recommend: `PREFER_GPU` default** (+ `REQUIRE_GPU`, `CPU_ONLY`); GPU→CPU only when allowed and always surfaced/audited; detector supports CPU via ONNX CPU EP.
- **Rationale:** dev/recovery on CPU without silent slowdowns on long jobs. **Tradeoff:** must handle both paths. **Consequence:** predictable performance + resilience.

### D13 — First Model Strategy (rev. 2)
- **Recommend: Phase 6 = Strategy B (detection infrastructure + benchmark harness validated by a clearly‑labelled `DeterministicTestDetector` / project‑created test artifact — NO third‑party weights, no AI‑accuracy claim); Phase 6T = Strategy A (from‑scratch, random‑init `platform_trained` production model on approved data).**
- **Rationale:** ships real infrastructure now with zero third‑party‑weight dependency; owned production weights + real profiles later; never presents a test provider as real AI. **Tradeoff:** real accuracy/profiles deferred to 6T. **Consequence:** frozen §20 mechanism satisfied now; ownership + provenance realized in 6T.

### D14 — Phase 6 Training Boundary
- **Options:** train in Phase 6; train in a dedicated later phase.
- **Recommend: NO first‑model training in Phase 6.** Training occurs in **Phase 6T**, gated on dataset legal approval + architecture confirmation + synthetic/own‑data readiness.
- **Rationale:** not in the frozen roadmap; large, dataset‑constrained, no‑pretrained effort; separates concerns. **Tradeoff:** two review/approval cycles. **Consequence:** Phase 6 ships fast; training governed properly.

### D15 — Training Data Composition (NEW, rev. 2)
- **Options:** (1) approved public datasets only; (2) synthetic only; (3) approved public + synthetic; (4) approved public + synthetic + authorized own data over time.
- **Recommend (4) as the long‑term strategy, phased:**
  - **6T‑a (first model):** **Open Images V7 vehicle subset (YELLOW — admit only images whose per‑image rights + CC BY 4.0 annotations are verified per §7.5/§7.6)** + **self‑generated CARLA synthetic (YELLOW → `SYNTHETIC_APPROVED` only after UE‑EULA + asset‑pack rights clear)** — synthetic supplies the *fixed‑camera viewpoints, night/weather, small/distant, occlusion, auto‑GT boxes* that commercial real data lacks. **Neither source is admitted until its rights gate clears; no fully GREEN source exists today (§7.5).**
  - **6T‑b→ongoing:** add **authorized own footage (INTERNAL_AUTHORIZED)** after privacy/compliance review for domain adaptation to deployment (e.g. Qatar).
- **Rationale:** option 1 alone lacks fixed‑camera viewpoint + night/weather balance; option 2 alone suffers a sim‑to‑real domain gap; **3 covers the first model; 4 closes the deployment domain gap over time.** **Realistic first‑model target (verified‑source‑based, not invented):** on the order of **tens of thousands of real vehicle images (Open Images vehicle subset)** + **a comparable or larger volume of self‑generated CARLA frames** with automatic boxes, balanced across day/night/weather and near/distant, class‑balanced across {car,bus,truck,motorcycle,bicycle,(pedestrian)}. Exact counts set during 6T after measuring available approved data — **not promised here**. **Tradeoff:** synthetic sim‑to‑real gap + CARLA legal check + annotation effort for own data. **Consequence:** a commercially‑defensible, provenance‑complete training pool that improves as owned data grows.

---

### Final summary for reviewer (rev. 2)
1. **Baseline:** Python 3.12.9 (`backend/.venv`), av 13.1.0, numpy 2.2.6, **245 passed / 88%**; 11 apps; 15 migrations; governance registry already supports detection/provenance/artifacts/`platform_trained`; no detector/training code; RTX 3070/8 GB + nvidia‑smi; no AI framework in the project venv.
2. **Frozen Phase 6 scope:** *Detection provider + Benchmark suite + profile selection* (no training phase exists in the frozen roadmap). Training is moved to an explicit new **Phase 6T**.
3. **Recommended D1–D15:** frozen‑infra‑only · PyTorch(train)+ONNXRuntime(runtime) · YOLOX Apache‑2.0 **code only** · **no third‑party pretrained weights anywhere (random‑init production)** · seven‑status **sample‑level** pipeline‑enforced dataset gate · hybrid+immutable‑manifest provenance (per‑sample media+annotation rights) · COCO JSON · {car,bus,truck,motorcycle,bicycle,pedestrian} · separate `ml/` env · `FrameDetectionBatch`+JSONB · ONNX artifact · PREFER_GPU · deterministic‑test‑detector‑then‑from‑scratch first‑model · **no training in Phase 6** · **D15 composition = Open Images V7 (verified subset) + rights‑approved CARLA synthetic + authorized own data over time**.
4. **Candidate datasets (primary‑source):** **GREEN (fully cleared): NONE today.** **YELLOW (pending verification):** Open Images V7 (annotations CC BY 4.0 ✓ but **per‑image image rights unverified**); **CARLA self‑generated synthetic** (code MIT + assets CC‑BY, **UE‑EULA + asset‑pack rights unverified**); Roboflow Universe / COCO / UA‑DETRAC / VisDrone. **RED:** MIO‑TCD, Virtual KITTI 2, SYNTHIA (CC BY‑NC‑SA), BDD100K (commercial‑gated), KITTI/Cityscapes/nuScenes/Waymo (non‑commercial). Architecture **code** (weights NOT used): YOLOX & RT‑DETR Apache‑2.0 (GREEN, code only); Ultralytics AGPL (RED).
5. **Revised pretrained‑weight policy:** **no third‑party detector weights used anywhere** (not even benchmark); Phase 6 uses a labelled deterministic test provider; first real weights are project‑trained from random init in Phase 6T.
6. **Revised Phase 6/6T boundary:** Phase 6 = detection **infrastructure** + benchmark harness (no weights, no AI‑accuracy claim). Phase 6T = training system + first from‑scratch project‑trained model + real inference profiles — **after** the dataset‑rights gate clears.
7. **Current commercial training‑data readiness (§7.5):** **no fully verified GREEN dataset exists now**; Open Images + CARLA are the leading YELLOW candidates pending verification; several fixed‑camera sets are RED. This does **not** block Phase 6; it makes the Phase 6T dataset‑rights gate mandatory before any production data download or training run.
8. **Datasets with uncertain commercial rights (require legal verification):** Open Images per‑*image* rights (annotations clear); **CARLA generated‑output rights under the Unreal Engine EULA + per‑content‑pack asset terms**; all *verify*‑marked academic sets; any Roboflow Universe set.
9. **Effort:** Phase 6 ~9–14 dev‑days; Phase 6T ~15–30+ dev‑days + GPU training wall‑clock (higher without pretrained init) + **dataset‑rights verification lead time**.
10. **Major risks:** scope creep, **insufficient commercially‑cleared training data (no GREEN dataset yet)**, commercial fixed‑camera data scarcity, from‑scratch accuracy with no pretrained baseline, CARLA/UE‑EULA rights, onnxruntime‑GPU on Windows, legal overclaim, ONNX parity, detection write volume, AGPL contamination.
11. **File created:** `E:\ai camera\PHASE_6_PLAN.md` (this document only).

PHASE 6 PLAN STATUS: READY FOR REVIEW

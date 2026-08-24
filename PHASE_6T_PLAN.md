# PHASE 6T — PROJECT-TRAINED TRAFFIC DETECTOR — IMPLEMENTATION PLAN (FINALIZED)

**Document type:** Implementation plan (planning only — no code, installs, downloads, or training performed).
**Revision:** Correction & finalization pass (2026-07-16). Architecture direction from the approved draft preserved; dataset classifications, PyTorch/CUDA stack, ONNX Runtime GPU, preprocessing, training-duration policy, architecture-code strategy, execution staging, and completion terminology corrected and hardened.
**Authoritative source:** `PHASE_0_ARCHITECTURE.md` (frozen) remains authoritative. Phase 6T is inserted between frozen Phase 6 (detection provider + benchmark) and Phase 7 (tracking).
**Legal note:** This is an engineering governance document, **not legal advice**. License *identifiers* are quoted from primary/official sources where reachable; their *application* to commercial training is project interpretation and requires counsel sign-off before any production use.

---

## 0. WHAT CHANGED IN THIS REVISION (correction summary up front)
1. **Dataset classifications are now evidence-based.** Datasets are **not** marked RED on reputation. RED is used **only** where a primary/official source explicitly prohibits the intended use; where a primary source could not be verified this session, the class is **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED**. This moved several datasets **out of RED into YELLOW** (notably **BDD100K** and **Waymo**, see §5).
2. **Connectivity constraint disclosed:** in this environment `WebFetch` reached only **GitHub** and **Google (googleapis)** hosts; other official dataset domains (cocodataset.org, nuscenes.org, cvlibs.net, cityscapes-dataset.com, mapillary.com, waymo.com, tcd.miovision.com) returned `ECONNREFUSED`. Classifications reflect exactly what was verifiable here; everything else is marked "primary terms not fully verified — re-verify at implementation."
3. **PyTorch/CUDA is now implementation-ready** (bundled-runtime wheels, no CUDA Toolkit; cu126/cu128 for Ampere) with a fallback order (§10/§11).
4. **ONNX Runtime GPU treated as a separate stack** (CUDA 12.x + cuDNN 9 for ORT 1.20; cuDNN installed separately) (§12).
5. **Preprocessing decision resolved:** unify Phase 6 + 6T on **bilinear** before real training, with regression guards (§13).
6. **300-epoch schedule removed** in favour of a dataset-scale-aware policy with convergence/early-stopping and a max budget (§14).
7. **YOLOX vendoring reassessed** → **training-only pinned dependency** (not vendoring) recommended (§15), with Apache-2.0 NOTICE obligations documented (§16) and a weighted architecture re-score (§17).
8. **Execution split into Phase 6T-A (foundation) and 6T-B (first model)** with explicit start gates (§19/§20) and unambiguous completion terminology (§21).
9. **D1–D19 updated** from corrected evidence (§22); contradiction check performed (§23).

---

## 1. CURRENT STATE VERIFIED (re-verified live 2026-07-16)

### 1.1 Tests / migrations
- `python -m pytest` → **297 collected, exit 0, 0 failed** (245 baseline + 52 Phase 6). `manage.py check` → 0 issues. `makemigrations --check` → no changes. 31 test files.

### 1.2 Environment (project `backend/.venv`)
| Item | Value |
|---|---|
| Python | 3.12.9 |
| NumPy / PyAV | 2.2.6 / av 13.1.0 |
| onnx / onnxruntime | 1.17.0 / 1.20.1 |
| ORT EPs available | `AzureExecutionProvider`, `CPUExecutionProvider` — **NO CUDA EP** |
| Django / DRF / Celery | 5.2.7 / 3.16.1 / 5.5.3 |
| **PyTorch / torchvision / pycocotools / albumentations / tensorboard** | **ABSENT** (`import torch` → ModuleNotFoundError) |

### 1.3 Hardware
| Item | Value |
|---|---|
| GPU | NVIDIA RTX 3070 Laptop (Ampere sm_86), 8192 MiB (~8018 free) |
| Driver | 592.00 (driver-reported CUDA ceiling **13.1** — a capability, not an installed toolkit) |
| CUDA Toolkit (`nvcc`) | NOT installed |
| ORT CUDA EP | NOT available (CPU package) |

### 1.4 Existing training/data/weights
No `training/` dir, no `datasets/`/`data/`, **no `.pt/.pth/.onnx/.weights`** committed. No training code, no real weights, no datasets. Clean.

### 1.5 Discrepancies vs Phase 6 reports
**None.** Repo matches `PHASE_6_VERIFICATION_REPORT.md`. One parity item to resolve in 6T (not a discrepancy): Phase 6 `preprocess.py` uses **nearest-neighbour** resize → §13.

---

## 2. FROZEN-ROADMAP RECONCILIATION
Frozen §40: P6 = detection provider + benchmark + profiles; P7 = tracking. §20 mandates a **benchmark gate on real hardware**; §119 anticipates **PyTorch** as the training stack with detection **benchmark-deferred behind providers**. Phase 6T fulfils the *model* P6 deferred (P6 = infra only). **No boundary conflict.** Deferred to P7+ (unchanged): tracking, counting, lane analytics, speed, queues, congestion, incidents, alerts, prediction, SUMO, signals, twin. 6T output = a governed `platform_trained` ONNX `AIModelVersion` loaded by the **existing** Phase 6 runtime (only a new architecture output adapter is added, §41/§44).

## 3. OBJECTIVES
Dataset-rights + provenance governance with a hard production gate; isolated PyTorch training env (runtime stays torch-free); canonical annotation conversion + validation + dedup + leakage-safe hashed manifests; scratch-trainable detector (no third-party pretrained weights) with reproducible recipe + checkpoint/resume; objective evaluation + ONNX export + PyTorch↔ONNX parity + governance registration; real inference through the Phase 6 runtime + real benchmark + finalized profiles.

## 4. NON-GOALS
Tracking/counting/speed/queues/congestion/incidents/analytics/prediction/SUMO/signals/twin (P7+). No third-party pretrained detector weights. No production dataset committed. No live/RTSP. No accuracy guarantees — first model may ship `EXPERIMENTAL`.

---

## 5. DATASET RIGHTS — REVERIFIED (primary-source discipline)

**Method:** primary/official sources only for final classification. In this environment, `WebFetch` reached **GitHub** and **Google** hosts; other dataset domains refused connections. Where the official terms were **fetched**, the classification is definitive-for-what-was-fetched. Where they were **not reachable**, the row is **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** with the strongest secondary indication noted and a mandatory re-verify-at-implementation flag. **RED is used only for an explicitly-verified prohibition.**

### 5.1 DATASET RIGHTS EVIDENCE REGISTER

| Dataset | Publisher | Primary source reached this session | What it verified | Media rights | Annotation rights | Commercial | ML-training | Remaining uncertainty | Class |
|---|---|---|---|---|---|---|---|---|---|
| **Open Images V7** | Google | ✅ `storage.googleapis.com/openimages` factsfigures + download pages | annotations **CC BY 4.0 (Google)**; images labelled **CC BY 2.0** with **Google disclaimer**; metadata has per-image **License/Author/OriginalURL/OriginalLandingURL** | per-image CC BY 2.0 **unwarranted by Google** | **CC BY 4.0** (commercial OK w/ attribution) | annotations yes; images per-image | not addressed for weights | per-image media accuracy not guaranteed | **YELLOW** (whole); filtered subset → **conditional**, §5.3 |
| **CARLA** (synthetic) | CARLA team | ✅ `github.com/carla-simulator/carla` README | code **MIT**, assets **CC-BY**, **UE4/UE5 separate EULA**, deps incl **LGPL-2.1 (ad-rss-lib)** | CC-BY (assets) | n/a (self-generated) | permitted for CARLA code+assets | not explicitly addressed → governed by CC-BY + UE EULA | UE EULA output/royalty clauses; third-party asset packs | **GREEN-CONDITIONAL**, §5.4 |
| **BDD100K** | UC Berkeley | ✅ `github.com/bdd100k/bdd100k/LICENSE` (raw) | repo LICENSE = **BSD-3-Clause (Fisher Yu 2018)**, **no NC clause** | repo license permissive; **dataset ToU page (doc.bdd100k.com) NOT reachable** | BSD-3 (toolkit/labels) | repo license permits; **dataset media ToU unverified** | not verified | separate dataset ToU may add media terms | **YELLOW** *(corrected from RED)* |
| **Waymo Open** | Waymo | ✅ `github.com/waymo-research/waymo-open-dataset/LICENSE` (raw) | LICENSE = **Apache-2.0 + BSD-3** — **applies to CODE/devkit only** | **dataset governed by separate Waymo Dataset License (waymo.com/open/terms) — NOT reachable** | code license ≠ data license | **data terms unverified** | unverified | dataset license is a distinct document | **YELLOW — PRIMARY DATASET TERMS NOT VERIFIED** *(corrected from RED)* (strong secondary: non-commercial) |
| **COCO** | COCO Consortium | ✗ cocodataset.org refused | secondary only: annotations CC BY 4.0; images Flickr ToU | per-image Flickr (unverified primary) | CC BY 4.0 (secondary) | annotations likely; images per-image | not addressed | official terms page not fetched | **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** (per-image filtering may help, §5.3/§6) |
| **nuScenes / nuImages** | Motional | ✗ nuscenes.org refused | devkit README ≠ dataset terms | unverified primary | unverified | unverified | unverified | strong secondary: **CC BY-NC-SA 4.0** | **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** (strong NC indication) |
| **KITTI** | KIT/Toyota | ✗ cvlibs.net refused | — | unverified | unverified | unverified | unverified | strong secondary: **CC BY-NC-SA 3.0** | **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** (strong NC indication) |
| **Cityscapes** | Daimler et al. | ✗ site refused | — | unverified | unverified | unverified | unverified | strong secondary: proprietary academic/non-commercial | **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** (strong NC indication) |
| **Mapillary Vistas** | Mapillary/Meta | ✗ site refused | — | unverified | unverified | unverified | unverified | strong secondary: **CC BY-NC-SA**; commercial via separate agreement | **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** (strong NC indication) |
| **MIO-TCD** | Miovision | ✗ tcd.miovision.com refused | — | unverified | unverified | unverified | unverified | strong secondary: **CC BY-NC-ND** (ND would block canonical conversion) | **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** (strong NC-ND indication) |
| **VisDrone** | Tianjin Univ. | ⚠ GitHub README body not returned | — | unverified | unverified | unverified | unverified | secondary: academic-use | **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** |
| **UA-DETRAC / UAVDT / AI City** | academic / NVIDIA | ✗ not reachable | — | unverified | unverified | unverified | unverified | secondary: research/competition-only | **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** |

**Verified fact vs interpretation vs needs-legal-review:** the "Primary source reached" column marks *verified fact* for that specific document; "strong secondary indication" is *interpretation pending primary verification*; commercial-eligibility of any GREEN/YELLOW dataset is *requires legal review* before production use.

### 5.2 Important correction note
The earlier draft classified BDD100K and Waymo (and most others) **RED** from search summaries. Primary evidence shows: **BDD100K's repo license is permissive BSD-3** (its non-commercial reputation is not reflected in the fetched LICENSE), and **Waymo's GitHub license governs only the code, not the dataset**. Neither could be confirmed RED from a primary source this session → both are **YELLOW**, pending verification of their dataset-specific ToU. This is the exact "do not infer RED" correction required.

### 5.3 Open Images — precise rights strategy
Open Images metadata provides per-image **`License`, `OriginalURL`, `OriginalLandingURL` (license/source), `Author`, `AuthorProfileURL`, `Title`**. Therefore a **project-generated filtered subset** is *technically* constructible: keep only images whose `License` field is a commercially-permissive CC license (e.g. CC BY 2.0 / CC0), record per-image license + author + source for attribution, and exclude the rest.
- **The whole dataset stays YELLOW.**
- **The filtered subset is NOT auto-GREEN.** Google explicitly disclaims per-image license accuracy, so the metadata `License` field is a *filter*, not a *warranty*. Eligibility of the filtered subset requires: (a) automated filter on `License`, (b) **human/legal spot-check** of a sample + attribution capture, (c) a recorded manifest of per-image license evidence. Only then may the subset be registered `APPROVED_WITH_OBLIGATIONS` (attribution obligations).
- If automated metadata alone is deemed insufficient by counsel, the subset remains YELLOW.

### 5.4 CARLA — generated-output rights review
Verified (GitHub README): CARLA **code MIT**, **assets CC-BY**, **UE4/UE5 under Epic's own EULA**, deps include **LGPL-2.1 (ad-rss-lib)** and others. CARLA's license does **not** explicitly grant/deny "use rendered output to train ML models" — so generated-frame rights derive from: **CC-BY on the assets** (permits commercial derivatives with attribution) + **Epic UE EULA** (governs the engine; generally lets creators own their output but has product/royalty terms that need review; internal dataset generation is typically outside game-royalty scope but is **not** something this plan may assert without counsel).
- **Classification: GREEN-CONDITIONAL.** Enforceable conditions (all required): (1) a **pinned CARLA release version**; (2) **only default CC-BY CARLA assets** (maps/vehicles/pedestrians/textures) — **no UE Marketplace assets, no external asset packs**; (3) a **recorded per-batch asset manifest** (version + map + asset list); (4) attribution retained per CC-BY; (5) **legal review of the applicable Unreal Engine EULA** for any output/royalty clauses before production use; (6) LGPL-2.1 component (ad-rss-lib) not linked into any redistributed artifact (it is not needed for image generation).
- If condition (5) is unresolved, downgrade CARLA to **YELLOW** until reviewed.

## 6. DATASET CLASSIFICATION SUMMARY (corrected)
- **GREEN (real images, commercial+training verified from primary source):** **NONE.**
- **GREEN-CONDITIONAL:** **CARLA** (synthetic; §5.4 conditions incl. legal UE-EULA check).
- **YELLOW:** Open Images V7 (filtered subset conditionally eligible after legal spot-check), COCO, BDD100K, Waymo, nuScenes/nuImages, KITTI, Cityscapes, Mapillary Vistas, MIO-TCD, VisDrone, UA-DETRAC/UAVDT/AI City. (Several carry strong NC secondary indications and will likely resolve to RED once their primary terms are fetched — but this plan does **not** assert RED without primary verification.)
- **RED (explicitly verified prohibition):** **NONE asserted this session** (no primary source explicitly prohibiting was fetched).

## 7. WHAT DATA CAN 6T ACTUALLY USE TODAY (without weakening the gate)?
Under the production gate (§12), only **`SYNTHETIC_APPROVED`, `INTERNAL_AUTHORIZED`, `APPROVED_COMMERCIAL`, `APPROVED_WITH_OBLIGATIONS`** are eligible. Today that means:
1. **Controlled CARLA synthetic** (once §5.4 conditions incl. legal check are met) → `SYNTHETIC_APPROVED`.
2. **Authorized project-owned footage** (§9) → `INTERNAL_AUTHORIZED`.
3. **An Open Images license-filtered + legally-spot-checked subset** → `APPROVED_WITH_OBLIGATIONS` (attribution).
**No YELLOW-unverified dataset is eligible.** If none of 1–3 is ready, **no production-eligible training data exists yet** → 6T-B is BLOCKED (§21) while 6T-A proceeds. The gate is **not** weakened.

## 8. DATASET-RIGHTS FALLBACK STRATEGY
A (GREEN-only) — blocked today (no GREEN real data). B (GREEN-conditional synthetic ± legally-cleared filtered subset) — feasible for an EXPERIMENTAL model. C (request owner permission) — parallel, off critical path. D (own/authorized footage) — best quality, needs collection+annotation+privacy. E (infra-first, defer production model). **Recommendation: E + B** — build all infra now (6T-A); train an EXPERIMENTAL model from CARLA (+ optional cleared subset/own data) in 6T-B; never touch YELLOW-unverified data for production.

## 9. AUTHORIZED / PROJECT-OWNED DATA (design only)
Pipeline: authorized footage → register source (owner/consent/rights basis) → compliance approval → frame extraction → dedup → annotation → QA → `DatasetVersion` → immutable manifest → training approval. Address: camera ownership ≠ footage rights; **privacy** (faces/plates → blur/exclude per local law); retention alignment (existing `RAW_VIDEO`); annotation-workforce access controls. Built only if chosen as a source.

---

## 10. PYTORCH / CUDA — IMPLEMENTATION-READY (verified from official matrix)
Verified (pytorch.org get-started guidance + community confirmations): **pip CUDA wheels bundle the CUDA runtime — no system CUDA Toolkit / `nvcc` required** (a toolkit is only needed to compile custom C++/CUDA extensions). The wheel's `cuXXX` tag is the **bundled runtime**, independent of the driver's reported CUDA number; a driver reporting CUDA 13.1 runs `cu124/cu126/cu128` wheels. **RTX 3070 (Ampere sm_86)** is supported by `cu124/cu126/cu128`.

**Recommended initial training stack (install-time exact pin, do not install now):**
- **OS/Python:** Windows, **Python 3.12** (matches project 3.12.9).
- **PyTorch:** latest stable **2.x** with **`cu126`** wheels (CUDA 12.6 runtime) — chosen to stay in the **CUDA 12.x** family so it can share a runtime family with `onnxruntime-gpu` later (§12). `cu128` is an acceptable alternative for training alone.
- **torchvision:** the version paired with the chosen torch (per pytorch.org matrix).
- **Install form:** `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126` (in `training/.venv`).
- **CUDA Toolkit:** **not required.** **Driver:** 592.00 far exceeds the CUDA-12.x minimum — no driver change.
- **Distinguish:** *driver capability* (592 → CUDA ≤13.1) vs *CUDA Toolkit* (not installed, not needed) vs *CUDA runtime bundled in the torch wheel* (cu126). Only the last matters for torch.

## 11. PYTORCH COMPATIBILITY FALLBACK ORDER
1. Preferred: **torch stable `cu126`** (py312/Windows).
2. Another officially-supported **CUDA 12.x** wheel (`cu124` or `cu128`) if `cu126` unavailable for the chosen torch/py312.
3. **CPU-only torch** for smoke/infrastructure verification (6T-A can complete on CPU).
4. **External rented GPU** for full training (§35).
**Do not** downgrade the NVIDIA driver. **Do not** install a standalone CUDA Toolkit unless a from-source custom-extension build is ever required (not anticipated).

## 12. ONNX RUNTIME GPU — SEPARATE STACK (future, production-inference only)
Verified (onnxruntime.ai docs): **onnxruntime-gpu 1.20 requires CUDA 12.x + cuDNN 9.x** on Windows; ORT built for CUDA 12.x is compatible with any CUDA 12.x; **cuDNN 8.x and 9.x are not cross-compatible**; **cuDNN must be installed separately** and `cudnn64_9.dll` placed on `PATH` (the classic setup pitfall).
- **Proposed future stack (only after a model exists, §43):** `onnxruntime-gpu==1.20.x` + **CUDA 12.x runtime** + **cuDNN 9.x**. Aligning training on **torch `cu126`** keeps both in the **CUDA 12.x** family.
- **Do not install now.** **CPU ONNX Runtime remains mandatory fallback** (Phase 6 already reports EPs truthfully). The production runtime keeps `onnxruntime` (CPU) unless/until `onnxruntime-gpu` is verified on this exact GPU/driver/cuDNN — a distinct decision (D17) made in 6T-B or later.

## 13. PREPROCESSING PARITY — DECISION
Golden rule: **training preprocessing == production inference preprocessing** (no train/serve skew).
- **Option A** — keep Phase 6 **nearest-neighbour** resize, train against it. Pros: zero Phase 6 change. Cons: nearest-neighbour is atypical for detection, aliases small/distant objects (a stated core requirement), and would force the trained model to learn a degraded input distribution.
- **Option B** — move **both** Phase 6 and 6T to **bilinear** before real training. Pros: standard detector interpolation, better small-object fidelity, matches how the model will best converge. Cons: a Phase 6 `preprocess.py` change (small, testable).
- **Recommendation: Option B (bilinear, unified).** Rationale: the Phase 6 detector currently runs only the TEST provider / const graph, so **no real accuracy depends on the current resize** — changing it now has near-zero regression cost and maximum future benefit; the reverse-letterbox math and existing coordinate/shape tests are interpolation-independent, so the 297 baseline is expected to remain green. **Requirements if adopted:** focused regression tests for the new resize; **preserve the 297 baseline**; a before/after benchmark; and the exact interpolation recorded in model metadata (`input_spec.interpolation = "bilinear"`) and enforced by both training and `preprocess.py`. Freeze this contract before full training (Gate E, §19).

## 14. TRAINING-DURATION POLICY (dataset-scale-aware; replaces fixed 300 epochs)
No universal epoch count. Duration is a function of eligible image count, instance count, class balance, synthetic/real ratio, batch/effective-batch, and **validation convergence**. Define stages:
- **Smoke:** tens of steps, tiny subset, CPU-OK — proves the loop/checkpoint/export path.
- **Pilot:** short run on a small eligible subset — sanity of loss/metrics, LR range.
- **Full:** train to **val-metric convergence** with **early stopping (patience)** and a **max training budget** (wall-clock + epoch cap) to bound laptop cost; strong aug with aug-off final phase; EMA.
- **Convergence criteria:** stop when val mAP@0.5:0.95 plateaus within a tolerance over N eval cycles, or the max budget is hit.
A ~300-epoch schedule remains **one candidate experiment** for COCO-scale data, **not** a universal rule; small synthetic sets typically need heavier aug and different schedules, not blindly more epochs.

## 15. ARCHITECTURE-CODE STRATEGY (reassessed)
- **Strategy A — vendor minimal YOLOX subset.** Ownership feel, but ongoing maintenance of copied code + Apache NOTICE propagation.
- **Strategy B — training-only pinned dependency on official YOLOX** (pip/git at a pinned commit) in `training/.venv`. **Production is unaffected** (only ONNX ships; runtime never imports YOLOX/torch). Reproducibility via the pinned commit + code-identity hash (§31). Lowest architecture-bug risk, lowest maintenance.
- **Strategy C — clean reimplementation.** Highest effort + correctness risk.
- **torchvision FCOS/RetinaNet** — BSD-3, in-stack, zero external repo, simplest decode.
- **Recommendation (revised D4): Strategy B — training-only pinned YOLOX dependency**, with **torchvision FCOS (BSD-3) as the fallback** if YOLOX's dependency tree or NOTICE obligations prove burdensome. Rationale: using permissively-licensed source correctly is fully compatible with owning the project's software and trained ONNX artifact; vendoring adds maintenance without added rights. (This **revises** the draft's "vendor minimal subset" recommendation, per the correction directive not to choose vendoring merely for perceived ownership.)

## 16. YOLOX LICENSE & NOTICE OBLIGATIONS (if YOLOX selected)
YOLOX is **Apache-2.0** (Megvii; verified `github.com/Megvii-BaseDetection/YOLOX/LICENSE`). Apache-2.0 obligations to honour: (1) include a copy of the license with any redistribution of YOLOX source; (2) retain copyright/attribution and any `NOTICE` file contents; (3) state significant modifications to redistributed files; (4) no trademark grant. **Under Strategy B (training-only dependency, not redistributed)** these obligations are minimal — we still record provenance (commit, version) and reproduce attribution/NOTICE in `training/` docs. **The trained ONNX weights are not YOLOX source**, so shipping them does not by itself trigger source-redistribution obligations (weights are our artifact). If any YOLOX source is ever vendored/redistributed (Strategy A), preserve headers + LICENSE + NOTICE. Do not reduce this to "Apache = safe" without recording the obligations.

## 17. ARCHITECTURE RE-SCORE (weighted)
Weights (sum 100): scratch-training 20 · small/distant vehicle 20 · data-efficiency 15 · 8 GB feasibility 15 · ONNX export 10 · production-decode simplicity 5 · license obligations 5 · maintenance 5 · training speed 5. Scores 1–5.

| Criterion (weight) | YOLOX-S | tv FCOS | tv RetinaNet | NanoDet-Plus | RT-DETR |
|---|---|---|---|---|---|
| Scratch-training (20) | 5 | 4 | 4 | 4 | 2 |
| Small/distant (20) | 4 | 4 | 4 | 3 | 5 |
| Data-efficiency (15) | 4 | 4 | 4 | 4 | 2 |
| 8 GB feasibility (15) | 4 | 4 | 3 | 5 | 3 |
| ONNX export (10) | 4 | 5 | 5 | 4 | 3 |
| Decode simplicity (5) | 3 | 4 | 4 | 3 | 3 |
| License (5) | 4 (Apache) | 5 (BSD) | 5 (BSD) | 4 (Apache) | 4 (Apache) |
| Maintenance (5) | 3 | 5 | 5 | 3 | 3 |
| Training speed (5) | 4 | 4 | 3 | 5 | 3 |
| **Weighted total** | **≈4.15** | **≈4.20** | **≈3.95** | **≈3.90** | **≈3.05** |

**Reading:** YOLOX-S and torchvision **FCOS** are essentially tied; FCOS edges ahead on export/maintenance/license, YOLOX-S on scratch-training strength. RT-DETR clearly trails for a first scratch model on 8 GB (data-hungry). **Final D3: adopt YOLOX-S as primary for its scratch+small-object strength, with torchvision FCOS (BSD-3) as a first-class fallback validated by a smoke comparison in 6T-A.** Architecture is **not** changed for licensing convenience alone (both finalists are permissive).

## 18. TRAINING DEPENDENCIES (implementation-ready; `training/.venv` only)
| Dep | Pin (verify at install) | Role | License | Env |
|---|---|---|---|---|
| python | 3.12 | — | PSF | training |
| torch | latest 2.x **cu126** | train/export | BSD-style | training-only |
| torchvision | paired with torch | ops/(fallback models) | BSD-3 | training-only |
| numpy | 2.x compatible w/ torch | arrays | BSD-3 | both (separate env copy) |
| onnx | 1.17.x | export validation | Apache-2.0 | shared |
| onnxruntime | 1.20.x (CPU) | parity check | MIT | shared |
| pycocotools | latest | COCO mAP eval | FreeBSD-style | training-only |
| tensorboard | latest | curves | Apache-2.0 | optional/training |
| (aug) torchvision.transforms.v2 | with torchvision | augmentation (D13) | BSD-3 | training-only |
Each dep tagged **training-only / export-only / shared**. **Never** add torch to `backend/requirements/*`. No dep added merely because tutorials use it. Albumentations only if v2 transforms prove insufficient for bbox-aware aug.

## 19. IMPLEMENTATION START GATES
- **Gate A (Architecture):** D3/D4 approved.
- **Gate B (Training env):** exact PyTorch stack (§10) selected + `training/.venv` verified (CPU import at minimum).
- **Gate C (Dataset governance):** rights statuses + production gate (§12) approved.
- **Gate D (Training data):** ≥1 `DatasetVersion` in `{SYNTHETIC_APPROVED, INTERNAL_AUTHORIZED, APPROVED_COMMERCIAL, APPROVED_WITH_OBLIGATIONS}` — **required only for production-eligible training (6T-B), not for infra (6T-A)**.
- **Gate E (Preprocessing):** exact train/serve preprocessing contract (§13, bilinear) frozen + documented in model metadata **before full training**.

## 20. EXECUTION STAGING
### PHASE 6T-A — TRAINING FOUNDATION (may proceed after plan approval; **no approved dataset required**)
Dataset governance app + rights gate; manifest system; import/validation/dedup/leakage-safe splitting; `training/` env + isolated venv (CPU smoke OK); architecture integration (YOLOX-S dep or FCOS) + training engine (train/checkpoint/resume/AMP/EMA); evaluation harness; ONNX export + parity infrastructure; Phase 6 preprocessing bilinear unification (§13) with regression guards; **all tests** (governance/import/manifest/leakage/smoke-train/eval/export/parity), torch-gated so `backend` CI stays torch-free.
### PHASE 6T-B — FIRST REAL PROJECT-TRAINED MODEL (**Gate D required**)
Approved dataset prep (CARLA synthetic and/or cleared subset/own data); pilot → full training; evaluation + model selection; ONNX export; parity; governance registration (`platform_trained`) + `ModelEvaluation`; approval decision (may be `EXPERIMENTAL`); real Phase 6 runtime integration + YOLOX output adapter; real benchmarks; finalized profiles; frontend verification with real output.

## 21. COMPLETION STATUS TERMINOLOGY (unambiguous)
- `PHASE 6T-A STATUS: COMPLETE` — training/dataset infrastructure complete + green.
- `PHASE 6T-B STATUS: COMPLETE` — a real model completed the full approved pipeline (train→eval→export→parity→register→real inference), labelled by measured maturity.
- `PHASE 6T STATUS: COMPLETE` — only when **both** 6T-A and 6T-B are complete.
- If 6T-A done but no approved data: `PHASE 6T-A STATUS: COMPLETE` / `PHASE 6T-B STATUS: BLOCKED — APPROVED TRAINING DATA UNAVAILABLE` / `PHASE 6T STATUS: PARTIALLY COMPLETE`. **Infrastructure existence alone never means "Phase 6T complete."**

---

## 22. DATASET GOVERNANCE, PROVENANCE, GATE, TAXONOMY (design — preserved from draft, unchanged unless noted)
- **New app `apps/datasets`:** `Dataset`, `DatasetLicense` (identifier/url/evidence/commercial/training/attribution/redistribution/verified_by/at), `DatasetVersion` (rights_status, taxonomy_version, mapping_version, dataset_root ref, manifest_hash, counts, split refs, approval), `DatasetImport`, `DatasetManifest` (immutable, content-hashed). New `DataCategory.TRAINING_DATA` + `DATASET_MANIFEST`; audit `DATASET_REGISTERED/LICENSE_VERIFIED/VERSION_APPROVED/VERSION_REJECTED`. **No media blobs in PostgreSQL** — references + checksums + counts + manifest hashes only.
- **Sample provenance (§11-draft):** per-sample rows live in the **immutable hashed manifest** (scalable/reproducible); DB holds manifest hash + aggregate eligibility. A sample is production-eligible iff its DatasetVersion is eligible and no per-sample exclusion applies.
- **Production gate (enforced in `python -m training.train`, not just UI):** eligible = `{APPROVED_COMMERCIAL, APPROVED_WITH_OBLIGATIONS, INTERNAL_AUTHORIZED, SYNTHETIC_APPROVED}`; everything else (incl. all `RESEARCH_ONLY`, `LICENSE_UNCLEAR`, `YELLOW-unverified`) is rejected for production training. `--research-only` throwaway runs can never register a production model.
- **First-model taxonomy:** target v1 `{CAR,BUS,TRUCK,MOTORCYCLE,BICYCLE,PEDESTRIAN}`, but **gate each class on a minimum eligible-instance count**; under-supported classes → more synthetic data or a recorded **v1-subset** on the model version (never silently drop/remap). Ambiguous source labels never silently mapped (versioned mapping, §25-draft).
- **Annotation format:** **COCO JSON** canonical; originals immutable; conversion provenance recorded.
- **Import/validate/dedup/splits:** idempotent import; validation report (corrupt/invalid/oob/zero-area/dup/unknown-class/imbalance/tiny-object/empty/resolution); exact SHA-256 dedup (+ optional pHash flag, never auto-merge); **leakage-safe grouped splits** (by video/camera/scene/sequence/location) with deterministic seeded **immutable hashed split manifests**; test groups never overlap train/val.
- **Augmentation:** traffic-appropriate, versioned in recipe; **torchvision transforms.v2** (D13) — flip/photometric/scale/crop/mosaic-mixup/light-perspective/optional weather; no unrealistic transforms.

## 23. TRAINING, REPRODUCIBILITY, CHECKPOINTS, EVAL, EXPORT, RUNTIME (preserved, key points)
- **Model size / input:** YOLOX-S (~9M; Tiny fallback on OOM) at **640** (768 as Quality/eval option); AMP + gradient accumulation for 8 GB; no tiling first model.
- **Scratch recipe:** random init; SGD+momentum, wd 5e-4, warmup→cosine, **dataset-scale-aware schedule with early stopping + max budget** (§14), strong aug with aug-off final phase, EMA, grad-clip, AMP. LR/schedule/aug-prob flagged for experimentation. **No pretrained-finetune hyperparameters.**
- **`TrainingRun`** (governance): recipe hash, dataset_version ids, split-manifest hashes, taxonomy, seed, framework versions, hardware, status, checkpoint refs (via `StoredArtifact`, **not** PG blobs), metrics, final artifact, failure info; audit `TRAINING_STARTED/COMPLETED/FAILED`.
- **Reproducibility:** since the repo is **not a git repo**, a **code-identity hash** (sha256 over training package + arch dep pin + config) + `CODE_VERSION` string is **mandatory** — no reproducibility claim without it.
- **Checkpoint/resume:** per-epoch + best + last **state dicts** (opt/sched/AMP-scaler/epoch/step/RNG); full mid-run resume; **no pickled arbitrary objects** (security).
- **Evaluation:** pycocotools mAP@0.5, mAP@0.5:0.95, per-class AP, Precision/Recall + slices (small/med/large, day/night, dense, occlusion, weather where data allows). **Selection never on train loss.** **Test set touched once** (documented policy); leakage-isolated.
- **Quality gate:** baseline-measured (no invented thresholds); no catastrophic per-class failure; small-object + runtime perf reported; failure cases reviewed; first model may ship **`EXPERIMENTAL`**; never activate a poor model to close the phase.
- **Artifact security:** checkpoints are trusted internal artifacts; **no** user upload/exec; production loads **only validated ONNX** (Phase 6 sniff+checksum rejects pickles).
- **ONNX export (§40) + adapter (§41/§44):** fixed documented I/O (`1×3×640×640` f32, RGB, `/255`, letterbox pad 114, **bilinear**), opset for ORT 1.20, `onnx.checker` + shape validation; **architecture-specific decode adapter** (YOLOX grid/stride → xyxy target-px + score + class) feeding the **existing** Phase 6 postprocess → canonical `Detection`. Register output-schema id (`yolox-v1`) on the model version so `OnnxDetector` selects the adapter. **Do not** force the model to emit the Phase 6 `(N,6)` **test** contract inside the graph.
- **Parity (§42):** PyTorch vs ONNX on identical val samples; tolerances (e.g. max abs normalized-coord delta ≤1e-3, score delta ≤1e-3, 100% class agreement on confident boxes); **no activation on material divergence.**
- **Runtime integration (§46):** approved ONNX → Phase 6 CV runtime loads ACTIVE artifact → real preprocess (bilinear) → ONNX inference → YOLOX adapter → canonical detections → persist. **TEST provider retained** for tests. **Benchmark (§47):** decode/sampling/numpy/preprocess/inference/postprocess/persist/end-to-end; CPU + (if approved) GPU; 720p+1080p; per profile; report FPS/latency/RAM/VRAM/throughput; **no hidden slow results.** **Profiles (§48):** replace PROVISIONAL Q/B/P only after real measurement; vary res/sampling/conf/NMS, not weights. **Frontend (§49):** verify `DetectionsPanel` with real output; **remove TEST banner only for genuine approved output**; keep provenance; no counting language.

## 24. REPOSITORY / MODELS / MIGRATIONS EXPECTED
`apps/datasets` (5 models) + migration; `TrainingRun` (+`ModelEvaluation` reuse) + migration; `DataCategory.TRAINING_DATA`/`DATASET_MANIFEST` + audit events + migration; retention handler for training manifests. New top-level `training/` package (own venv/requirements/tests; **not** imported by `backend/`). Runtime: YOLOX decode adapter + output-schema selection in `apps/processing/runtime/detector/`; **bilinear** `preprocess.py` change (§13) with regression tests; profile/benchmark finalization. Frontend: banner already conditional — verify only.

## 25. ADRS
Finalize **ADR-029** (Training Data Governance & Provenance) and **ADR-030** (Model Training & Weight Provenance: random-init, no third-party weights, YOLOX Apache-2.0 obligations). New **ADR-033** (Training Environment Isolation), **ADR-034** (Detector Training Architecture: YOLOX-S/FCOS + adapter), **ADR-035** (Dataset Manifest & Leakage-Safe Splits), **ADR-036** (Checkpoint vs Deployment-Artifact Boundary), **ADR-037** (Preprocessing Interpolation Contract — bilinear unification). Next free number is 033.

## 26. IMPLEMENTATION ORDER (mapped to stages)
**6T-A:** (1) ADRs 029/030 finalize + 033–037 draft. (2) `apps/datasets` + gate + tests. (3) `training/` skeleton + isolated venv + torch CPU smoke. (4) COCO-JSON conversion + validation + dedup + leakage-safe split + immutable manifests + tests. (5) Architecture integration (YOLOX-S dep / FCOS) + engine (train/checkpoint/resume/AMP/EMA) + smoke-train test. (6) Evaluation harness. (7) ONNX export + parity infra + tests. (8) **Phase 6 bilinear preprocessing unification** + regression + benchmark compare. → `PHASE 6T-A STATUS: COMPLETE`.
**6T-B (Gate D):** (9) approved data prep (CARLA/cleared-subset/own). (10) pilot → full training. (11) eval + selection. (12) export + parity. (13) governance registration/approval. (14) runtime adapter + real inference + benchmark + profiles. (15) frontend verify. (16) regression (297 green) + `PHASE_6T_VERIFICATION_REPORT.md`.

## 27. ACCEPTANCE CRITERIA
**6T-A:** 297 baseline green + torch-gated training tests green; dataset governance + gate enforced in the training runtime; leakage-safe splits + immutable hashed manifests verified; engine train/checkpoint/**resume** + NaN-loss handling; eval harness correct; ONNX export + `onnx.checker` + ORT load + **parity infra**; bilinear preprocessing unified with 297 preserved + benchmark recorded + interpolation contract documented; **no torch in `backend/`; no dataset/weights committed.**
**6T-B:** ≥1 eligible `DatasetVersion` (Gate D); reproducible training (code-identity hash); eval with slices; parity within tolerance; model registered `platform_trained` + full provenance; only APPROVED→ACTIVE; TEST provider retained; real inference verified; real benchmark reported (no hidden slow results); profiles finalized; frontend TEST-banner removed only for real output. First model labelled by measured maturity (may be `EXPERIMENTAL`).

## 28. VERIFICATION PROCEDURE
Run `backend` suite (297, torch-free); run `training` suite in `training/.venv`; execute smoke-train→export→parity end-to-end; (6T-B) run one real detection session through the Phase 6 runtime on real footage; produce benchmark report; confirm governance registration/approval/activation audit trail; write `PHASE_6T_VERIFICATION_REPORT.md` with the §21 status lines.

## 29. KNOWN RISKS
1. **No GREEN real-image dataset** → synthetic/own-data first → **synthetic→real domain gap.** 2. **Most YELLOW datasets likely resolve to non-commercial** once primary terms are fetched — do not plan around them. 3. **torch cu126 vs onnxruntime-gpu CUDA/cuDNN family** must be kept aligned (both CUDA 12.x); cuDNN 9 installed separately for ORT-GPU. 4. **8 GB VRAM** limits batch/resolution → slower scratch convergence. 5. **Scratch quality** → likely `EXPERIMENTAL` first model. 6. **Train/serve preprocessing** must be unified (bilinear) and frozen. 7. **CARLA UE-EULA / asset provenance** — needs legal review; restrict to default CC-BY assets. 8. **ONNX parity/quantization drift.** 9. **License legal interpretation** — counsel sign-off before commercial use.

## 30. ESTIMATED EFFORT (engineering vs GPU time; by stage)
| Workstream | Optimistic | Realistic | Conservative |
|---|---|---|---|
| Dataset-rights re-verification + legal review | 2 d | 5 d | 2 wk |
| **6T-A**: dataset governance + gate + tests | 3 d | 5 d | 1.5 wk |
| **6T-A**: import/validate/dedup/split + manifests | 3 d | 6 d | 2 wk |
| **6T-A**: training env + arch integration + engine | 4 d | 8 d | 2.5 wk |
| **6T-A**: eval + export + parity infra | 3 d | 5 d | 1.5 wk |
| **6T-A**: bilinear preprocessing unification + regression | 1 d | 2 d | 4 d |
| **6T-A engineering subtotal** | **~3 wk** | **~5–6 wk** | **~10 wk** |
| **6T-B**: data prep (CARLA/cleared/own) | 3 d | 7 d | 3 wk |
| **6T-B**: integration + benchmark + profiles + report | 3 d | 5 d | 1.5 wk |
| **GPU training time (separate from engineering)** | hours (smoke/pilot) | days (first EXPERIMENTAL, local/rented) | 1–2 wk iteration |

---

## 31. UPDATED DECISIONS (D1–D19)
- **D1 — Dataset Rights Strategy:** eligibility gate `{APPROVED_COMMERCIAL, APPROVED_WITH_OBLIGATIONS, INTERNAL_AUTHORIZED, SYNTHETIC_APPROVED}` enforced **in the training runtime**; **all YELLOW-unverified/RESEARCH_ONLY excluded**. *(unchanged intent, evidence-hardened.)*
- **D2 — Initial Data Composition:** **CARLA synthetic first** (§5.4 conditions incl. legal UE-EULA check), optionally + **Open Images license-filtered legally-spot-checked subset** (`APPROVED_WITH_OBLIGATIONS`) and/or **authorized own footage**. *(refined: filtered-subset path added.)*
- **D3 — Architecture:** **YOLOX-S primary** (Apache-2.0), **torchvision FCOS (BSD-3) first-class fallback**, validated by a 6T-A smoke comparison; RT-DETR deferred; Ultralytics/YOLOv7 rejected (copyleft). *(re-scored, §17.)*
- **D4 — Architecture-Code Strategy:** **training-only pinned dependency** on official YOLOX (or torchvision FCOS) — **not vendoring**; production ships only ONNX. *(CHANGED from draft's vendoring.)*
- **D5 — Pretrained Weights:** **random init, no third-party pretrained weights**; exceptions need explicit approval + provenance. *(unchanged.)*
- **D6 — Training Framework:** **torch 2.x `cu126`** (bundled CUDA runtime, no toolkit) + torchvision + numpy + onnx + onnxruntime(CPU) + pycocotools + optional tensorboard, in `training/.venv`. Fallback cu124/cu128→CPU→rented GPU. *(made implementation-ready.)*
- **D7 — Training Environment:** separate `training/.venv` + top-level `training/`; **torch never in `backend/`.** *(unchanged.)*
- **D8 — Annotation Format:** **COCO JSON**; originals immutable; conversion provenance recorded. *(unchanged.)*
- **D9 — Provenance:** DB holds identity + manifest hashes + aggregate eligibility; **immutable hashed manifests** hold per-sample rows. *(unchanged.)*
- **D10 — Split Strategy:** leakage-safe grouped, deterministic, seeded, immutable hashed split manifests. *(unchanged.)*
- **D11 — Input Resolution:** **640** first model (768 as Quality/eval option); no tiling; **bilinear** interpolation (D-linked to §13). *(refined: interpolation fixed.)*
- **D12 — Model Size:** YOLOX-S first (Tiny on OOM). *(unchanged.)*
- **D13 — Augmentation:** **torchvision transforms.v2** (bbox-aware), versioned in recipe; Albumentations only if needed. *(unchanged.)*
- **D14 — Training Recipe:** random-init SGD/cosine, **dataset-scale-aware schedule with early stopping + max budget** (not fixed 300 epochs), EMA/AMP/grad-clip, aug-off final phase. *(CHANGED: epoch policy.)*
- **D15 — Checkpoint Strategy:** per-epoch + best + last **state dicts** + full resume; no pickled objects. *(unchanged.)*
- **D16 — Deployment Artifact:** ONNX with fixed documented I/O + opset for ORT 1.20 + checker/shape validation; register `yolox-v1` output schema. *(unchanged.)*
- **D17 — Production Inference:** **CPU ONNX Runtime first**; evaluate `onnxruntime-gpu 1.20 + CUDA 12.x + cuDNN 9` **only after** the model exists and the stack is verified on this GPU; CPU fallback always retained. *(made implementation-ready + separated from torch.)*
- **D18 — Quality Gate:** baseline-measured; first model may ship `EXPERIMENTAL`; never activate a poor model to close the phase. *(unchanged.)*
- **D19 — Completion Policy:** **6T-A may complete without approved data**; **6T-B requires Gate D**; if data unavailable → `6T-B BLOCKED` / `6T PARTIALLY COMPLETE`; never use YELLOW-unverified/RED data to force a model. *(sharpened with 6T-A/6T-B terminology.)*

## 32. CONTRADICTION CHECK (self-review)
- **GREEN vs YELLOW:** no dataset is both; only CARLA is GREEN-CONDITIONAL; no real dataset is GREEN. ✅
- **CARLA rights:** GREEN-CONDITIONAL everywhere; §5.4 conditions + legal review consistent with §6/§7/D2. ✅
- **Synthetic eligibility:** `SYNTHETIC_APPROVED` eligible in gate (§12/§22) and used in D2 — consistent. ✅
- **PyTorch/CUDA:** torch `cu126` (CUDA 12.x, bundled, no toolkit) consistent across §10/§18/D6; fallback order §11. ✅
- **ORT-GPU:** separate stack, CUDA 12.x + cuDNN 9, future-only, CPU fallback mandatory — consistent §12/D17. ✅
- **Preprocessing:** bilinear unification chosen in §13, referenced in §23/§24/D11/§40/§46 and Gate E — consistent. ✅
- **Output contract:** Phase 6 `(N,6)` is the **test** contract; real model uses `yolox-v1` raw + adapter → canonical `Detection`; never forced to `(N,6)` — consistent §23/§41/§44/D16. ✅
- **Random init / no pretrained:** consistent §3/§4/D5/§23. ✅
- **6T-A vs 6T-B completion:** terminology consistent §20/§21/§27/D19. ✅
- **Phase 7 boundary:** no tracking/counting/speed anywhere; frontend keeps no-counting language. ✅
- **Architecture code strategy:** D4 (training-only dependency) consistent with §15/§16/§18 and "no torch in runtime." ✅
No contradictions outstanding.

---

## 33. FINAL SUMMARY (required)
1. **Dataset classifications changed:** BDD100K **RED→YELLOW** (repo LICENSE verified BSD-3; dataset ToU unverified); Waymo **RED→YELLOW — PRIMARY DATASET TERMS NOT VERIFIED** (GitHub license covers code only); COCO/nuScenes/KITTI/Cityscapes/Mapillary/MIO-TCD/VisDrone/UA-DETRAC/UAVDT/AI City **RED→YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** (primary domains unreachable this session; strong NC secondary indications noted, to re-verify at implementation). Open Images remains YELLOW with a defined filtering path. CARLA remains GREEN-CONDITIONAL with a fuller rights review + legal-check condition.
2. **Current GREEN datasets:** none (real images).
3. **Current GREEN-CONDITIONAL:** CARLA (synthetic) under §5.4 conditions incl. legal UE-EULA review.
4. **Current YELLOW:** Open Images V7 (filtered subset conditionally eligible after legal spot-check), COCO, BDD100K, Waymo, nuScenes/nuImages, KITTI, Cityscapes, Mapillary Vistas, MIO-TCD, VisDrone, UA-DETRAC/UAVDT/AI City.
5. **Current RED:** none asserted (no primary prohibition fetched this session).
6. **Exact recommended PyTorch stack:** Windows/Python 3.12, **torch 2.x `cu126`** + matching torchvision via `download.pytorch.org/whl/cu126`, **no CUDA Toolkit**, driver 592 sufficient; fallback cu124/cu128 → CPU → rented GPU.
7. **Exact proposed ONNX Runtime GPU stack (future, production-only):** `onnxruntime-gpu 1.20.x` + **CUDA 12.x runtime** + **cuDNN 9.x** (installed separately, `cudnn64_9.dll` on PATH); CPU ORT remains mandatory fallback; decided only after a model exists.
8. **Final preprocessing recommendation:** unify Phase 6 + 6T on **bilinear** letterbox (pad 114, `/255`, RGB, NCHW) before full training, with regression guards + 297 baseline preserved + interpolation recorded in model metadata.
9. **Final architecture recommendation:** **YOLOX-S (Apache-2.0)** primary; **torchvision FCOS (BSD-3)** first-class fallback (validated by 6T-A smoke comparison).
10. **Final architecture-code strategy:** **training-only pinned dependency** (not vendoring); production ships only ONNX; runtime never imports the training framework.
11. **Updated training-duration strategy:** dataset-scale-aware (smoke → pilot → full) with **val-convergence early stopping + max budget**; 300 epochs is only a COCO-scale candidate, not universal.
12. **Phase 6T-A scope:** all training/dataset infrastructure (governance, gate, manifests, import/validate/dedup/split, training env + engine, eval, export+parity infra, bilinear preprocessing unification, tests) — **no approved dataset required**.
13. **Phase 6T-B start gate:** **Gate D** — ≥1 `DatasetVersion` in `{SYNTHETIC_APPROVED, INTERNAL_AUTHORIZED, APPROVED_COMMERCIAL, APPROVED_WITH_OBLIGATIONS}` (plus Gates A/B/C/E).
14. **Updated D1–D19:** see §31 (changed: D4 vendoring→dependency; D14 epoch policy; D6/D17 made implementation-ready; D2/D11 refined; D19 staged terminology).
15. **Unresolved blockers:** (a) **no production-eligible real dataset today** — 6T-B needs CARLA-approved and/or cleared-subset and/or own data (Gate D); (b) **primary license terms for most YELLOW datasets could not be fetched in this environment** (connectivity limited to GitHub/Google) → must be re-verified from official sources at implementation; (c) **CARLA UE-EULA legal review** and **Open Images per-image legal spot-check** are prerequisites to declaring those sources eligible.

### Sources (verified this session)
- Open Images V7 — [factsfigures_v7](https://storage.googleapis.com/openimages/web/factsfigures_v7.html), [download_v7](https://storage.googleapis.com/openimages/web/download_v7.html)
- CARLA — [github.com/carla-simulator/carla](https://github.com/carla-simulator/carla) (README licensing section)
- BDD100K — [github.com/bdd100k/bdd100k LICENSE (raw)](https://raw.githubusercontent.com/bdd100k/bdd100k/master/LICENSE) → BSD-3-Clause
- Waymo — [github.com/waymo-research/waymo-open-dataset LICENSE (raw)](https://raw.githubusercontent.com/waymo-research/waymo-open-dataset/master/LICENSE) → Apache-2.0/BSD-3 (code only)
- YOLOX — [Apache-2.0 LICENSE](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE); Ultralytics — [ultralytics.com/license](https://www.ultralytics.com/license) (AGPL-3.0)
- PyTorch install — [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/)
- ONNX Runtime CUDA EP — [onnxruntime.ai CUDA-ExecutionProvider](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html)
- *Not reachable this session (re-verify at implementation):* cocodataset.org, nuscenes.org/terms-of-use, cvlibs.net (KITTI), cityscapes-dataset.com/license, mapillary.com/dataset/vistas, waymo.com/open/terms, tcd.miovision.com (MIO-TCD).

---

PHASE 6T PLAN STATUS: FINALIZED — READY FOR IMPLEMENTATION APPROVAL

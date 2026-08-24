# PHASE 6T-B — PREFLIGHT REPORT

**Purpose:** resolve local GPU training, exact dataset, final architecture, data-prep
strategy, and a realistic training configuration — **without starting real training**.
**Date:** 2026-07-16
**Authoritative sources:** `PHASE_0_ARCHITECTURE.md` (frozen), `PHASE_6T_PLAN.md`,
`PHASE_6T_A_VERIFICATION_REPORT.md`, ADR-029…037.

> **No real traffic detector was trained. No real/YELLOW dataset was used or downloaded.**
> A short **TEST_ONLY** GPU benchmark (random tensors) was run per §6/§20.

---

## 1. VERIFIED REPOSITORY BASELINE
| Check | Result |
|---|---|
| Backend suite (`backend/.venv`) | **331 passed, 0 failed** |
| Training suite (`training/.venv`) | **11 passed, 0 failed** |
| `manage.py check` | 0 issues |
| `makemigrations --check` | No changes |
| Production backend torch-free | ✅ `import torch` → ModuleNotFoundError |
| 6T-A artifacts present | `apps/datasets`, `governance.TrainingRun`, full `training/`, ADR-029…037, `preproc-v2-bilinear` |

No correct 6T-A work was redone. New this preflight: GPU-enabled torch, `training/gpu_benchmark.py`, updated `training/requirements.txt`.

## 2. GPU CONNECTIVITY DIAGNOSIS
The 6T-A CPU-only fallback was caused by `download.pytorch.org` being unreachable **then**.
Re-tested now:
- `download.pytorch.org` — **HTTPS 200 (reachable)**; `pip index` lists `torch 2.13.0+cu126`.
  (Raw `socket.gethostbyname` fails but the HTTP path resolves — an allowlist proxy.)
- `pypi.org` / `files.pythonhosted.org` / `github.com` / `storage.googleapis.com` — reachable.
- Most dataset domains (`nuscenes.org`, `cvlibs.net`, `cityscapes-dataset.com`, `waymo.com`,
  `doc.bdd100k.com`, `tcd.miovision.com`, `mapillary.com`) — **still DNS-blocked**;
  `cocodataset.org` reachable (terms JS-rendered). TLS verification was never disabled; no
  third-party mirrors used.
- **Conclusion: `LOCAL GPU TRAINING SETUP: RESOLVED` (now available).**

## 3. EXACT PYTORCH GPU STACK (installed + verified)
| Component | Version |
|---|---|
| Python | 3.12.9 (Windows) |
| torch | **2.13.0+cu126** (bundled CUDA 12.6 runtime) |
| torchvision | **0.28.0+cu126** |
| Install | `pip install torch==2.13.0+cu126 torchvision==0.28.0+cu126 --index-url https://download.pytorch.org/whl/cu126` |
| Standalone CUDA Toolkit | **Not required** (wheel bundles runtime); driver 592.00 sufficient |
Pinned in `training/requirements.txt`. **Not** added to `backend/` (still torch-free).

## 4. CUDA VERIFICATION RESULTS (measured)
| Check | Result |
|---|---|
| `torch.version.cuda` | **12.6** |
| `torch.cuda.is_available()` | **True** |
| Device | **NVIDIA GeForce RTX 3070 Laptop GPU** |
| Compute capability | **(8, 6)** — Ampere sm_86 |
| CUDA tensor alloc + matmul (2048²) | OK, finite |
| Conv forward + backward | OK |
| AMP autocast | OK (`float16`) |
| VRAM alloc / reserved / cleanup | 60.9 / 73.4 MB → 8.5 MB after cleanup — OK |
**Gate B (GPU env): PASS.**

## 5. GPU SMOKE BENCHMARK (TEST_ONLY random tensors — no real data)
FCOS ResNet50-FPN, 640×640, AMP, RTX 3070 Laptop (`training/gpu_benchmark.py`):
| Batch | imgs/s | steps/s | Peak VRAM | Feasible on 8 GB? |
|---|---|---|---|---|
| 2 | 13.5 | 6.75 | 2.10 GB | ✅ comfortable |
| 4 | **17.1** | 4.27 | 3.87 GB | ✅ **recommended (headroom for display)** |
| 8 | 18.6 | 2.33 | 7.35 GB | ⚠ feasible but tight (laptop display shares VRAM) |
| 16 | — | — | — | ✗ expected OOM (>8 GB) |
Throughput plateaus ~17–19 imgs/s. **Recommend batch 4 (safe) + gradient accumulation** to
reach a larger effective batch; batch 8 only with VRAM monitoring.

## 6. FINAL ARCHITECTURE RECOMMENDATION
Reality-based comparison (measured on THIS GPU):
| | FCOS ResNet50-FPN | YOLOX-S |
|---|---|---|
| Integrated + tested in 6T-A | ✅ yes | ✗ not installed (offline earlier) |
| Verified on RTX 3070 now | ✅ 17 imgs/s @640 b4 | not measured |
| ONNX export verified now | ✅ **128.6 MB, checker OK** (in-graph NMS) | not verified |
| License | BSD-3 (torchvision) | Apache-2.0 |
| Random init, no pretrained | ✅ `weights=None, weights_backbone=None` | ✅ (needs setup) |
| Params / VRAM | ~32 M / heavier (3.9 GB b4) | ~9 M / lighter, faster |
| Small/distant objects | good (FPN) | better (anchor-free, designed for it) |

**Recommendation: FCOS ResNet50-FPN for the FIRST real run (pilot + first-full).** It is the
lowest-risk path — already integrated, **verified working on the RTX 3070 (training + ONNX
export) in this preflight**, permissively licensed, random-init. **YOLOX-S remains the planned
upgrade** for the next model (lighter + stronger small-object) and should be integrated in
parallel; if its integration + on-device verification complete before Gate D clears, the first
run may switch to YOLOX-S. This is a deliberate, documented deviation from the plan's YOLOX-first
D3, justified by measured implementation reality.

## 7. ARCHITECTURE LICENSING
- **FCOS (chosen):** part of **torchvision (BSD-3-Clause)**. No copyleft, commercial-safe,
  no NOTICE-propagation burden beyond BSD attribution. Random init downloads nothing.
- **YOLOX (next):** **Apache-2.0** (`github.com/Megvii-BaseDetection/YOLOX`). If integrated,
  honor Apache-2.0 (license copy + retain NOTICE/attribution + state modifications) and pin the
  exact upstream commit in `TrainingRun` provenance. The trained ONNX weights are our artifact.
- Ultralytics YOLOv5/8/11 (AGPL) / YOLOv7 (GPL) remain **rejected** (copyleft).

## 8. DATASET RIGHTS RESEARCH (primary-source; connectivity-limited)
Fresh checks this session. Reachable primary sources: Open Images (Google), CARLA (GitHub),
BDD100K repo license (GitHub), Waymo repo license (GitHub), COCO home (JS-rendered terms). All
other official dataset domains were **DNS-unreachable** → classification stays
**YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** (never inferred RED). A fresh web search for a
2025–2026 commercially-licensed traffic dataset surfaced only research/unclear-license sets.
**No real dataset is verifiable GREEN this session.**

## 9. DATASET EVIDENCE TABLE
| Dataset | Primary source reached | Finding | Class |
|---|---|---|---|
| Open Images V7 | ✅ Google | annotations **CC BY 4.0**; images per-image CC (Google disclaims); metadata has per-image License/Author/URL | **YELLOW** (filtered subset conditionally eligible, §10) |
| CARLA (synthetic) | ✅ GitHub | code MIT, assets CC-BY, UE EULA separate, deps incl LGPL-2.1 | **GREEN-CONDITIONAL** (§11) |
| BDD100K | ✅ GitHub LICENSE | repo license **BSD-3**; dataset ToU page unreachable | **YELLOW** (dataset media ToU unverified) |
| Waymo | ✅ GitHub LICENSE | license covers **code only**; dataset terms separate & unreachable | **YELLOW — dataset terms not verified** |
| COCO | ⚠ home reachable, terms JS | annotations CC BY 4.0; images Flickr ToU (secondary) | **YELLOW** |
| MIO-TCD / UA-DETRAC / AI City / VisDrone / UAVDT / KITTI / Cityscapes / Mapillary / nuScenes / nuImages | ✗ unreachable | strong secondary non-commercial indications; not primary-verified | **YELLOW — PRIMARY TERMS NOT FULLY VERIFIED** |

*Verified fact* = the fetched license document; *interpretation/requires-legal-review* = commercial-eligibility. No RED asserted without a fetched prohibition.

## 10. OPEN IMAGES FILTERED-SUBSET CONCLUSION
Feasible **in principle**: Open Images image metadata provides per-image **License, OriginalURL,
OriginalLandingURL, Author, AuthorProfileURL, Title** (verified on Google's download page). A
pipeline `metadata → select vehicle classes (Car/Bus/Truck/Motorcycle/Bicycle) → filter License
∈ {CC BY 2.0, CC0} → capture attribution → human/legal spot-check → DatasetVersion` could yield a
commercially-usable subset (annotations are CC BY 4.0). **Not auto-GREEN:** Google disclaims
per-image license accuracy, so a **legal spot-check is mandatory** before `APPROVED_WITH_OBLIGATIONS`.
**Count estimate:** Open Images has hundreds of thousands of boxes across these vehicle classes,
but the eligible **post-filter** count cannot be stated without downloading the metadata (not done
here) — **provisional, requires the filtering pass**. Designed, not executed.

## 11. CARLA CONCLUSION
Re-verified (GitHub): code MIT, assets CC-BY, **Unreal Engine under its own EULA**, deps incl
LGPL-2.1 (ad-rss-lib). **GREEN-CONDITIONAL** — to reach `SYNTHETIC_APPROVED` ALL must hold:
pinned CARLA version; **only default CC-BY CARLA assets** (no Marketplace/third-party packs);
recorded per-batch asset manifest; CC-BY attribution; **legal review of the applicable UE EULA
output/royalty clauses**; LGPL component not linked into any redistributed artifact.
**Open question requiring confirmation:** does the applicable Unreal Engine EULA impose any
restriction/royalty on using rendered frames as ML training data for a commercial product? Until
answered by counsel, CARLA stays GREEN-CONDITIONAL (not approved).

## 12. AUTHORIZED OWN-DATA OPTION
Path: authorized footage → register source (owner/consent/rights basis) → compliance approval →
frame extraction → dedup → annotation → QA → `DatasetVersion (INTERNAL_AUTHORIZED)` → approval.
Possession ≠ training rights. Privacy: blur/exclude faces + license plates per local law.
**Minimum useful supplement (provisional):** ~1–3k annotated frames from representative
day/night/weather clips of the target cameras materially improves realism vs synthetic-only;
annotation effort ≈ a few seconds–minutes per frame (tooling-dependent).

## 13. RECOMMENDED FIRST DATASET COMPOSITION
Given verified rights today, the only production-eligible paths are **CARLA synthetic** (post
legal), **authorized own footage**, and an **Open Images legally-cleared filtered subset**.
**Recommendation: CARLA synthetic (primary) + a small authorized own-data set (if available) +
optionally an Open Images cleared subset.** Per source: synthetic gives controlled class balance +
day/night/weather + small-object density but has a sim→real gap; own data gives real distribution
but small volume; Open Images subset gives real diversity with attribution obligations. **Exact
image counts are unknown until the sources are prepared — not invented here.**

## 14. CLASS COVERAGE
Canonical v1: CAR, BUS, TRUCK, MOTORCYCLE, BICYCLE (+PEDESTRIAN). CARLA can synthesize all;
**BICYCLE and distant small vehicles are the weakest** for realism/volume. **Gate each class on a
minimum eligible-instance count**; if BICYCLE (or any class) is under-supported, add synthetic
instances or own data, or record a **v1-subset** on the model version — never train a class with
almost no useful examples to preserve the taxonomy. Ambiguous labels never silently mapped.

## 15. DATASET-SIZE TARGETS (provisional — real availability unknown)
| Tier | Approx images | Approx instances | Purpose |
|---|---|---|---|
| **Pilot** | ~1–3 k | ~5–15 k | verify genuine traffic learning (not just plumbing) |
| **First full model** | ~8–20 k | ~40–150 k | first EXPERIMENTAL model, practical on RTX 3070 |
| **Future expanded** | 50 k+ | 300 k+ | later quality model (likely rented GPU) |
A smaller high-quality, rights-clean set is preferred over a large unclean one.

## 16. TRAINING-TIME ESTIMATES (from measured throughput ~17 imgs/s, FCOS @640 b4 AMP)
Add ~1.3–1.5× for eval + data loading + laptop **thermal throttling**.
| Run | Images × epochs | Raw GPU-time | +overhead |
|---|---|---|---|
| Pilot | 2 k × 20 | ~0.65 h | ~1 h |
| First full | 10 k × 50 (early-stop likely ~30–40) | ~8.2 h (50) | **~8–12 h** |
| One tuning run | 10 k × 30 | ~4.9 h | ~6–7 h |
**Calendar time for the first full model (checkpoint/resume across sessions):**
| Daily budget | Days (≈10 GPU-h) |
|---|---|
| 3 h/day | ~4 days |
| 4 h/day | ~3 days |
| 6 h/day | ~2 days |
| 8 h/day (overnight) | ~1.5 days |
YOLOX-S would be materially faster (lighter) — re-estimate after its on-device benchmark.

## 17. FIRST PILOT TRAINING CONFIGURATION (recommended — NOT executed)
| Setting | Value |
|---|---|
| Architecture | **FCOS ResNet50-FPN**, `weights=None, weights_backbone=None` (random init) |
| Input | 640 (letterbox, **preproc-v2-bilinear**) |
| Batch size | **4** (safe; 8 max with VRAM monitor) |
| Gradient accumulation | 4 → **effective batch 16** |
| AMP | **on** (float16) |
| Optimizer | SGD, momentum 0.9, weight decay 1e-4 (FCOS convention) |
| Base LR | ~0.01 for effective-16 (scale linearly; **needs a short LR sanity sweep**) |
| Warmup | ~500 iters (linear) |
| Scheduler | cosine to max budget |
| EMA | on |
| Grad clip | 10.0 |
| Max budget | ≤50 epochs (dataset-scale-aware) |
| Early stopping | patience 8 on val mAP@0.5:0.95 |
| Checkpoint | every epoch (best + last) |
| Eval | every epoch (pycocotools mAP + slices) |
Values flagged "needs sweep" are experimentation candidates, not copied from a fine-tune recipe.

## 18. CHECKPOINT/RESUME READINESS
6T-A `training.checkpoint` already saves model + optimizer + scheduler + AMP scaler + EMA + epoch
+ global step + best metric + RNG + config/provenance — **sufficient for train → checkpoint →
shut down → resume later**. Now **GPU-verified**: the training suite runs `train_run` on CUDA
(device auto-select) and resume passes. **Defect found + fixed during preflight:** loading a
checkpoint with `map_location="cuda"` moved the saved CPU RNG ByteTensor to GPU, which
`set_rng_state` rejected — fixed by restoring the RNG state on CPU (`training/checkpoint.py`).
**Required change before real training:**
the engine's `train_run` currently implements the TinyDetector loss path only; a **FCOS training
branch** (torchvision loss-dict) must be added (the checkpoint/resume/EMA/early-stop machinery is
reused unchanged). This is a small, well-scoped 6T-B implementation item.

## 19. NON-CONTINUOUS LAPTOP TRAINING SCHEDULE
The first full model (~8–12 GPU-h) fits **2–4 short sessions**: e.g. 3 sessions of ~3–4 h, or two
overnight ~4–6 h runs. Workflow: start/resume from `last.pt` → train a session → checkpoint →
**stop the process cleanly** → shut down. Resume next session from `last.pt`. No single multi-day
run is required.

## 20. THERMAL / OPERATIONAL CONSIDERATIONS (RTX 3070 Laptop)
Operational guidance (not correctness): keep the laptop **plugged in**, on a **hard, elevated,
well-ventilated** surface; use the **high-performance / best-performance** power plan; **monitor
temps** (`nvidia-smi -l` / vendor tool) and let the driver throttle at its manufacturer limit
(don't impose arbitrary caps); **disable sleep/hibernate** during an active training process
(hibernate mid-run loses the process — rely on checkpoints for pauses); pause via a clean
checkpoint + stop before closing the lid. Thermal throttling extends wall-clock (already in the
§16 overhead factor) but does not affect model correctness.

## 21. GATE A–E STATUS
| Gate | Status | Note |
|---|---|---|
| **A — Architecture** | ✅ **PASS** | FCOS selected + verified on-device (train + ONNX export); YOLOX-S = planned next |
| **B — GPU training env** | ✅ **PASS** | torch 2.13.0+cu126, cuda.is_available True, RTX 3070 verified, benchmarked |
| **C — Dataset governance** | ✅ **PASS** | 6T-A: gate + manifests + leakage-safe splits, 331 tests green |
| **D — Production-eligible data** | ❌ **BLOCKED** | No `DatasetVersion` in an eligible status exists; no GREEN real dataset verifiable; CARLA/own/Open-Images all need external legal/human steps |
| **E — Train/serve preprocessing** | ✅ **PASS** | `preproc-v2-bilinear` frozen (ADR-037), golden-hash locked both envs |

## 22. REMAINING BLOCKERS
1. **Gate D (primary):** produce ≥1 production-eligible `DatasetVersion` — CARLA `SYNTHETIC_APPROVED`
   (after UE-EULA legal review + asset-manifest conditions), and/or authorized own footage
   `INTERNAL_AUTHORIZED`, and/or an Open Images **legally-spot-checked** filtered subset
   `APPROVED_WITH_OBLIGATIONS`. **No YELLOW-unverified data may be used.**
2. **Engine FCOS branch** (small): add the torchvision loss-dict training path to `train_run`.
3. **Legal confirmations:** UE-EULA output/royalty question (CARLA); Open Images per-image license
   spot-check. Both are human/legal, not code.
4. (Optional) YOLOX-S integration + on-device benchmark if it is to be the first architecture.

## 23. EXACT RECOMMENDED NEXT ACTION
Because **Gate D is blocked**, do **not** start training. Recommended next steps, in order:
1. **Decide the data path** (CARLA vs own-data vs Open-Images-subset) and obtain the required
   **legal confirmations**; then prepare + register + approve ≥1 `DatasetVersion` through the 6T-A
   governance gate.
2. In parallel (no data needed): add the **FCOS training branch** to the engine and (optionally)
   integrate YOLOX-S + benchmark it on the GPU.
3. Return for explicit **training approval** once a production-eligible `DatasetVersion` exists.

---

## STOP CONFIRMATION
No real-data training was started. No full or multi-hour training job was run. Only a short
TEST_ONLY GPU benchmark (random tensors) was executed. Gate D is blocked, so real training cannot
begin. Awaiting explicit training approval after Gate D is satisfied.

**Gate D (production-eligible training data) is BLOCKED — no eligible DatasetVersion exists.**

---

PHASE 6T-B PREFLIGHT STATUS: BLOCKED

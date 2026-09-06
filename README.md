# AI Traffic Intelligence & Management Platform

> **⚠️ Research project.** This is a solo research & engineering effort exploring how far a
> local-first, explainable AI traffic-analysis platform can be built **natively on a single
> Windows laptop** — from scratch, with no pretrained model weights, no cloud services, and no
> paid APIs. It is **analysis, simulation, and recommendation software only**: it is *not* a
> traffic control system and *not* a surveillance/identification system. Nothing here is
> production-ready; results, models, and performance numbers are experimental.

A modular-monolith platform that ingests road traffic video (recorded now, live RTSP later),
extracts explainable traffic measurements via computer vision, aggregates them into analytics,
and (in later phases) adds congestion intelligence, incident candidates, SUMO simulation,
signal-plan recommendation, and a digital twin — presented through an operations dashboard.

---

## 📍 Where the project is right now (2026-08)

**Current stage: Phase 6T-B — real-data training pilot (in progress, blocked on dataset image
acquisition).** Phases 0–6 and 6T-A are complete and verified.

| Phase | Scope | Status |
|---|---|---|
| 0 | Architecture freeze | ✅ Frozen |
| 1 | Platform foundation — Django/DRF/Channels, JWT auth + RBAC, Celery, Postgres, Redis, Next.js shell | ✅ Done |
| 2 | Observability, AI governance tables, retention framework | ✅ Done |
| 3 | Traffic network model (City→Zone→Road→Segment→Intersection→Approach→Lane→Camera, ROIs, counting lines) | ✅ Done |
| 4 | Video source abstraction + upload + validation | ✅ Done |
| 5 | Processing Session engine + CV runtime process + GPU manager (lifecycle, heartbeats, recovery) | ✅ Done |
| 6 | Detection infrastructure — provider interface, ONNX artifact lifecycle, batch detection storage | ✅ Done |
| 6T-A | Training foundation — dataset governance + approval gates, leakage-safe splits, isolated training env, from-scratch detectors (TinyDetector / FCOS) | ✅ Done |
| **6T-B** | **Real-data pilot — UVH-26 + BMD-45 (CC BY 4.0) selected & license-verified; interruptible multi-day training verified; pilot blocked on downloading image shards (tens of GB) + Gate D approval** | 🟡 **In progress** |
| 7 | Tracking provider | ⏳ Not started |
| 8–12 | Measurement → speed/queues → congestion → incidents/alerts → dashboard | ⏳ Planned |
| 13–17 | SUMO simulation → signal model → signal optimization → prediction → digital twin | ⏳ Planned |
| 18–19 | Performance/scale testing, production-readiness interfaces (RTSP, multi-GPU, edge) | ⏳ Planned |

**Test suite:** 342 backend + 27 training tests passing. Each phase is verified with a full
test run before it is marked done.

A deliberate research constraint: **detection models are trained from scratch** (no pretrained
weights), on openly licensed data only, behind explicit human approval gates. The first model
(`uvh_bmd_5class_v1` taxonomy: car / bus / truck / motorcycle / bicycle) trains on India-sourced
data and is therefore tagged EXPERIMENTAL for other regions.

---

## 🏗 Architecture

The architecture is frozen; changes require a new ADR. All decisions are recorded in
[`docs/adr/`](docs/adr) (ADR-001 … ADR-037).

### Three-runtime split (ADR-002)

The core architectural decision is that the web framework never touches the GPU:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Next.js 15 Operations Dashboard  (frontend/)                       │
│  REST + WebSocket (JWT)                                             │
└──────────────┬──────────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────┐   ┌──────────────────────────────────┐
│ 1. Django API / control     │   │ 2. Celery workers                │
│    plane (backend/)         │◄──┤    aggregation, reports,         │
│    auth, RBAC, config,      │   │    cleanup, scheduling,          │
│    session control, audit   │   │    simulation orchestration      │
│    — never runs inference   │   └──────────────────────────────────┘
└──────┬───────────▲──────────┘
       │ commands  │ heartbeats / progress / results   (Redis + DB)
┌──────▼───────────┴──────────────────────────────────────────────────┐
│ 3. CV Processing Runtime (dedicated long-lived process)             │
│    owns the GPU · lifecycle state machine (START/PAUSE/RESUME/      │
│    STOP/CANCEL) · frame acquisition → detection → (tracking →       │
│    lane association → measurement in later phases)                  │
└──────────────────────┬──────────────────────────────────────────────┘
                       │ deploys ONNX artifacts (ADR-032/036)
┌──────────────────────▼──────────────────────────────────────────────┐
│ Training track (training/ — isolated venv, ADR-033)                 │
│ dataset governance + approval gates → leakage-safe splits →         │
│ from-scratch training (TinyDetector/FCOS, interruptible multi-day)  │
│ → evaluation → ONNX export + parity check                           │
└─────────────────────────────────────────────────────────────────────┘

PostgreSQL 16+ (single DB, four logical schemas: platform / traffic /
timeseries / media — ADR-013) · Redis (broker, cache, pub/sub)
```

Key properties:

- **Provider interfaces everywhere** — `DetectionProvider`, `TrackingProvider`, etc. Nothing is
  frozen to a specific model family; model selection goes through a benchmark gate measured on
  real hardware, expressed as three operating profiles (Quality / Balanced / Performance).
- **Governance & provenance first** — every AI result carries model/version/config metadata;
  datasets pass license verification, integrity checks, and an explicit human approval gate
  (Gate D) before any training; incidents are only ever *candidates requiring verification*.
- **Environment isolation** — the Django backend is torch-free; PyTorch lives only in
  `training/.venv` (ADR-033). Inference uses exported ONNX artifacts.
- **Local-first, scale-later** — native Windows, one laptop, no Docker required; RTSP/CCTV,
  multi-GPU, and distributed processing are interface stubs for later phases.

### Backend modules (`backend/apps/`)

| App | Responsibility |
|---|---|
| `accounts` | JWT auth, users, roles, server-side RBAC |
| `audit` | Audit trail (ADR-016) |
| `common` | Shared utilities/base classes |
| `datasets` | Dataset registry, manifests, license/integrity validation, approval gates, leakage-safe splits (ADR-035) |
| `governance` | AI governance tables — model registry, versioning, provenance |
| `health` | `/api/healthz` liveness, `/api/readyz` readiness (Postgres, Redis, Celery heartbeat) |
| `ingestion` | Video sources, upload, format/integrity validation, metadata (ADR-022/023) |
| `network` | Traffic network model: City→Zone→Road→Segment→Intersection→Approach→Lane→Camera, ROIs, counting lines (ADR-019/020/021) |
| `processing` | ProcessingSession engine, CV runtime boundary, GPU manager, config snapshots, detection batch storage (ADR-024…027, 031) |
| `observability` | Structured logging, metrics, session tracing (ADR-017) |
| `realtime` | Django Channels WebSocket layer |
| `retention` | Tiered data retention (create/aggregate/archive/delete) |

### Training track (`training/`)

Isolated from the backend; CPU-torch in CI, CUDA on the dev machine. Contains from-scratch
detector architectures (TinyDetector, FCOS), the interruptible multi-day training engine with
true process-exit resume, deterministic preprocessing (bilinear contract, ADR-037), evaluation,
ONNX export with backend-parity verification, and provenance stamping. **No pretrained weights
are used anywhere.**

### Explicit non-goals (frozen)

- No physical signal control — optimization is simulation + recommendation only.
- No face recognition, person identification, or license-plate reading. Privacy tooling (blur)
  is anti-surveillance.
- No cloud, paid APIs, or paid AI services.
- No accuracy/FPS claims before measurement on real hardware.

---

## 🔭 Future goals & expansion

The roadmap above (§40 of the frozen spec) is dependency-ordered. Beyond finishing it, the
architecture was deliberately designed with interface-driven seams so the platform can grow
without rewrites.

### Near term (next milestones)

- **Complete Phase 6T-B:** download UVH-26 + BMD-45 image shards on the dev machine, run
  import → integrity → mapping → dedup → leakage-safe split, obtain Gate D approval, run the
  controlled pilot, then (with explicit approval) the first full multi-day training run and
  ONNX deployment of `uvh_bmd_5class_v1`.
- **Phase 7 — Tracking provider:** stable temporary IDs, double-count prevention across
  counting lines.
- **Phases 8–12 — the measurement core:** per-class/direction/lane counts, occupancy, density,
  flow, calibrated speed (three-tier, method-tagged), queue estimation, explainable rule-based
  congestion classification, incident *candidates* with evidence, alert lifecycle, and the full
  operations dashboard (live WebSocket counts, analytics, map).

### Mid term (planning & intelligence layer)

- **Phases 13–15 — Simulation & signals:** platform-network→SUMO conversion via a
  `SimulationAdapter`, signal model + plans, and signal-plan optimization benchmarked against a
  simulated baseline (recommendation only — never live control).
- **Phase 16 — Prediction:** provenance-tagged forecasts (simulated vs. real data), always
  compared against naive baselines.
- **Phase 17 — Digital twin:** persistent backend `TwinState` plus an ephemeral live overlay.

### Long term (scale & production readiness — Phases 18–19 and beyond)

These are already designed as interface stubs in the frozen architecture; expansion means
implementing them, not re-architecting:

- **Live ingestion:** RTSP/CCTV camera streams behind the existing `VideoSource` abstraction.
- **Scale-out:** multi-GPU scheduling in the GPU manager, multiple CV runtime processes, and
  distributed processing across machines; optional Docker parity for deployment.
- **Edge deployment:** running the ONNX detection path on edge hardware near cameras.
- **Controller integration stub:** a defined interface toward real signal controllers that
  remains inactive — physical control stays out of scope by design.

### Research goals (model track)

- **Better models, same governance:** larger from-scratch architectures once the FCOS baseline
  is measured; every candidate passes the benchmark gate on real hardware and is published as
  measured Quality/Balanced/Performance profiles, never asserted numbers.
- **Taxonomy growth:** add PEDESTRIAN (and later BICYCLE refinement) once a suitably licensed
  dataset is approved — the current data supports only the 5-class V1 taxonomy.
- **Geographic generalization:** the first model is trained on India-sourced data and tagged
  EXPERIMENTAL elsewhere; expanding dataset diversity (under the same license-verification and
  approval gates) is an explicit research goal.
- **Reproducibility as a feature:** every result remains traceable to model version, config
  snapshot, dataset version, and seed — the point of the project is not just working traffic
  AI, but *auditable* traffic AI built entirely from open components.

---

## 🧰 Technology stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 · Django 5.2 LTS · DRF · Django Channels (ASGI) · Celery |
| Data | PostgreSQL (4 logical schemas, native time-series partitioning) · Redis (Memurai on Windows) |
| Frontend | Next.js 15 · React 19 · TypeScript · Tailwind CSS · pnpm |
| CV / AI | OpenCV · NumPy · ONNX (inference) · PyTorch (training only, isolated venv) |
| Simulation (planned) | SUMO via TraCI/libsumo behind a `SimulationAdapter` |
| Target hardware | Ryzen 9 · 16 GB RAM · 8 GB GPU (RTX 3070) · Windows 11 |

## 📂 Repository layout

```
├── THIRD_PARTY_DATA.md           # Dataset licensing & attribution
├── docs/adr/                     # ADR-001 … ADR-037 — all architecture decisions
├── backend/                      # Django modular monolith (apps/, config/, tests/)
├── frontend/                     # Next.js 15 operations dashboard
├── training/                     # Isolated detector-training pipeline (own venv)
└── scripts/                      # Windows dev scripts (db init, backend, worker, CV runtime, frontend)
```

## 📊 Datasets & licensing

The training track uses only openly licensed data, verified live before approval:

- **UVH-26** and **BMD-45** (AIM @ IISc, HuggingFace) — **CC BY 4.0**, 1920×1080 traffic
  imagery, 14-class source taxonomy mapped to the 5-class canonical taxonomy
  `uvh_bmd_5class_v1`. See `THIRD_PARTY_DATA.md` for full attribution, citations, and the
  license-verification evidence.

Dataset import → integrity → mapping → dedup → leakage-safe split → human approval (Gate D) is
enforced in code before any training run can see the data.

---

## 🚀 Development setup (native Windows — no Docker)

### Prerequisites

| Component | Version used |
|---|---|
| Python | 3.12.9 (`py -3.12`) |
| Node.js | 24.x + corepack (pnpm 9) |
| PostgreSQL | 16+ on `127.0.0.1:5432` (database `aitraffic`) |
| Redis | Memurai (native) on `127.0.0.1:6379` |

### Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\dev.txt
copy .env.example .env   # then edit DATABASE_URL / secrets

# Create the four logical schemas (idempotent):
cd ..
$env:PGPASSWORD = "<postgres password>"
scripts\init_db.ps1

# Migrate + run the ASGI server:
scripts\dev_backend.ps1        # http://127.0.0.1:8000
```

Celery (second terminal; worker uses solo pool on Windows):

```powershell
scripts\dev_worker.ps1
```

CV runtime (third terminal):

```powershell
scripts\dev_cv_runtime.ps1
```

Admin user:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py createsuperuser
```

### Frontend

```powershell
cd frontend
$env:COREPACK_HOME = "$env:LOCALAPPDATA\node\corepack"
corepack pnpm install
copy .env.local.example .env.local
scripts\dev_frontend.ps1       # http://localhost:3000
```

### Training environment (separate venv — ADR-033)

```powershell
cd training
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests
```

### Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest --cov=apps --cov=config
```

Backend tests require live PostgreSQL and Redis (no fakes). Celery runs eagerly and Channels
uses the in-memory layer under test.

## 🔑 Key endpoints

- Health: `GET /api/healthz`, `GET /api/readyz`
- Auth: `POST /api/v1/auth/login` · `/refresh` · `/logout` · `GET /api/v1/auth/me`
- Users/roles: `GET|POST /api/v1/users`, `GET|PATCH|DELETE /api/v1/users/{id}`, `POST /api/v1/users/{id}/role`, `GET /api/v1/roles`
- Domain APIs for network, ingestion, processing, datasets, and governance are under
  `/api/v1/…` — see each app's `urls.py`.
- WebSocket: `ws://localhost:8000/ws/system/` (JWT via `access_token` subprotocol)

## 📖 Reading order for new contributors

1. This README — product definition, non-goals, and roadmap.
2. `docs/adr/` — why each decision was made.
3. Each app's models, services, and tests — what is *actually* implemented.

---

*Solo research project — designed and developed by **Sridhar**. All measurements, models, and
results are experimental.*

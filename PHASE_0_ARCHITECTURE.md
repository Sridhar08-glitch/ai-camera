# PHASE 0 — AUTHORITATIVE ARCHITECTURE SPECIFICATION (APPROVED / FROZEN)

**Project:** AI Traffic Intelligence & Management Platform
**Document type:** Architecture & Feasibility Freeze (Phase 0)
**Status:** ✅ APPROVED & FROZEN (approved 2026-07-15). No changes without a new ADR + re-approval.
**Approved decisions:** D1 = Option A (single PostgreSQL, four logical schemas) · D2 = Option A (plain PostgreSQL native partitioning; TimescaleDB deferred, evaluate only if measured need) · D3 = most reliable free native Redis-compatible option, else WSL2 Redis; no paid dependency.
**Target dev hardware:** AMD Ryzen 9 · 16 GB RAM · 8 GB GPU · Windows · Python 3.12
**Author:** Sridhar — Principal AI / CV / Traffic Systems / Backend / Frontend / Data / QA / PM
**Rule:** No application code, repo, migrations, or dependency installs until Phase 0 is explicitly approved.

---

## 1. Executive Summary

This document is the corrected and frozen Phase 0 architecture for a **modular monolith** AI traffic platform that runs **natively on one Windows laptop first**, using uploaded/recorded video, public datasets, and traffic simulation (SUMO) — with a **clean, interface-driven upgrade path** to RTSP/CCTV, multi-GPU, distributed processing, and real signal integration later.

The central architectural correction from the prior draft is the **three-runtime split**:

1. **Django (API/control plane)** — auth, config, REST, job control, dashboard backend. Never runs CV inference.
2. **Celery (short/medium jobs)** — aggregation, reports, cleanup, scheduling, simulation orchestration.
3. **CV Processing Runtime (data plane)** — a dedicated long-lived Python process that owns the GPU and executes frame acquisition → detection → tracking → lane association → measurement, with a full lifecycle state machine and heartbeats.

Everything AI-related is behind **provider interfaces** (`DetectionProvider`, `TrackingProvider`, etc.) and **nothing is frozen to a specific YOLO version** — model selection is deferred to a **benchmark gate** run on your actual hardware. Performance is expressed as **three operating profiles (Quality / Balanced / Performance)** whose thresholds are *measured*, not asserted.

Docker is **optional and not a Phase 0 deliverable**. Native Windows execution is the primary path.

Phase 0 delivers **documentation and frozen interfaces only**. No prototype is required to pass Phase 0.

---

## 2. Corrected Product Definition

A **traffic intelligence and management platform** that ingests video (recorded now, live later), extracts explainable traffic measurements via computer vision, aggregates them into analytics, derives congestion/queue/incident intelligence, and provides a simulation + signal-optimization + digital-twin layer for planning — presented through a professional operations dashboard.

It is **analysis, simulation, and recommendation** software. It is **not** a control system and **not** a surveillance/identification system in the laptop-first version.

---

## 3. Explicit Non-Goals (Frozen)

- **No physical signal control.** Optimization is simulation + recommendation only. Controller integration is an *interface stub*, never active.
- **No face recognition, no person identification, no license-plate reading/OCR.** Privacy tooling (blur) is anti-surveillance, not pro-surveillance.
- **No cloud, no paid APIs, no paid AI services, no Kubernetes** without explicit approval.
- **No city-scale real-time processing on the laptop.** The laptop handles a small number of concurrent streams; scale is an architecture property, not a laptop capability.
- **No guaranteed FPS/accuracy claims before benchmarking.**
- **No "AI detected an accident" language.** Only *incident candidates requiring verification*.
- **No mandatory Docker** for development.
- **No microservices** beyond the CV runtime process split.

---

## 4. MVP Scope (First Vertical Slice)

The MVP proves the core pipeline end-to-end on recorded video:

- Auth (JWT, roles, backend authorization).
- Traffic network CRUD (City→Zone→Road→Segment→Intersection→Approach→Lane→Camera) — minimal but real.
- Video upload + `VideoSource` abstraction + local file source.
- `ProcessingSession` engine + CV runtime (START/PAUSE/RESUME/STOP/CANCEL) with heartbeats.
- Detection provider (benchmark-selected default) + tracking provider.
- Counting lines + lane polygons; per-class, per-direction, per-lane counts.
- Time-window aggregation (1m/5m/hourly/daily).
- Basic congestion classification (rule-based, explainable).
- One incident detector (StoppedVehicle) as a candidate generator.
- Alert lifecycle (DETECTED→…→RESOLVED/DISMISSED).
- Operations dashboard: overview, camera/session view, live counts via WebSocket, analytics charts, alert list.
- Local observability (structured logs + session trace + basic metrics).

**MVP explicitly excludes:** speed calibration accuracy guarantees, full incident suite, SUMO integration, signal optimization, prediction, digital twin animation.

---

## 5. Full Platform Scope

Everything in the original master prompt Modules A–S, delivered across the phased roadmap (§40): network model, video sources, detection, tracking, counting, lane intelligence, calibrated speed, congestion, queues, incident suite, alerts, analytics, prediction, SUMO simulation, signal model, signal optimization, digital twin, ops center, plus production-readiness interfaces (RTSP, edge, multi-GPU, controller integration) — all built behind the interfaces frozen here.

---

## 6. Functional Requirements (condensed, testable)

FR-1 Users authenticate via JWT (access + refresh); every API enforces role/permission **server-side**.
FR-2 Users define a road network and attach cameras/lanes/ROIs/counting lines.
FR-3 Users upload video; system validates format/integrity and registers a `VideoSource`.
FR-4 Users create a `ProcessingSession` against a source; runtime executes it with observable state + progress + heartbeat.
FR-5 System detects and classifies road objects (car/motorcycle/bus/truck/bicycle/pedestrian).
FR-6 System tracks objects with stable temporary IDs; prevents double counting across counting lines.
FR-7 System produces per-class/direction/lane counts and time-window aggregates.
FR-8 System computes lane occupancy, density, flow, average speed (method-tagged), queue length.
FR-9 System classifies congestion with an explainable rule set tied to configurable road profiles.
FR-10 System emits incident **candidates** with evidence, confidence, triggering measurements, provenance.
FR-11 Alerts follow a defined lifecycle with assignment and audit.
FR-12 Analytics dashboards support historical comparison and export.
FR-13 Simulation scenarios convert platform network→SUMO, run, and return metrics via an adapter.
FR-14 Signal optimization compares candidate plans vs a baseline in simulation and reports improvement/degradation.
FR-15 Prediction runs are provenance-tagged (sim vs real) and compared against naive baselines.
FR-16 Digital twin exposes a backend `TwinState` (persistent) plus an ephemeral live channel.
FR-17 All simulation/synthetic data is **visibly labeled** as such in API + UI.
FR-18 Retention policies create/aggregate/archive/delete data per tier (§17).

---

## 7. Non-Functional Requirements

- **Performance:** expressed as measured profiles (§20), not fixed guarantees. Must degrade gracefully (frame skip, resolution scaling, detection stride) rather than crash/OOM.
- **Reliability:** no silent loss of processing state; sessions are recoverable/idempotent (§33).
- **Modularity:** every AI capability behind a provider interface; swap without touching business logic.
- **Observability:** every session traceable start→finish; structured logs + metrics locally (§34).
- **Security/Privacy:** backend authz everywhere; privacy controls designed now (§32).
- **Portability:** native Windows primary; optional Docker parity later; no OS-locked APIs in core logic.
- **Reproducibility:** AI results carry model/version/config/calibration metadata; seeds recorded for sim/optimization.
- **Maintainability:** modular monolith; documented ADRs; pinned critical dependency versions.

---

## 8. Final Technology Stack (Frozen except items marked *benchmark-deferred*)

**Backend:** Python 3.12 · Django 5.2 LTS · Django REST Framework · Django Channels (ASGI) · Celery · Redis (broker + cache + pub/sub) · PostgreSQL 16.
**Frontend:** **Next.js 15.3.4** · React 19 (as bundled by Next 15.3.x) · TypeScript · Tailwind CSS · package manager **pnpm** (lockfile committed). App Router. No forced downgrade to Next 14.
**CV/AI:** Python · OpenCV · PyTorch (CUDA build matched to your GPU driver) · NumPy. Detection/tracking implementations *benchmark-deferred* behind providers.
**Simulation:** SUMO (Eclipse, open-source) via TraCI/libsumo, wrapped by a `SimulationAdapter`.
**ASGI server (dev):** Uvicorn/Daphne for Channels; Django dev server acceptable for pure HTTP in dev.
**Testing:** pytest + pytest-django + DRF test client; deterministic CV fixtures.
**Time-series storage:** PostgreSQL with time-partitioned tables initially (TimescaleDB is an optional later ADR, not required).

Native Windows runtimes required: Python venv, PostgreSQL, Redis (Memurai or WSL2 Redis on Windows — see decision D3), Node.js/pnpm, Django dev server, Next dev server, CV runtime process, Celery worker + beat.

---

## 9. System Architecture (Modular Monolith, Multi-Process)

```
┌──────────────────────────────────────────────────────────────────┐
│                        Next.js 15.3.4 (UI)                         │
│     REST (HTTPS) ── WebSocket (Channels) for live session data     │
└───────────────┬───────────────────────────────┬──────────────────┘
                │ REST                           │ WS
        ┌───────▼────────────────────────────────▼────────┐
        │              Django + DRF + Channels             │  CONTROL PLANE
        │  auth · authz · config · job-control API · twin  │
        └───┬───────────────┬─────────────────┬───────────┘
            │ ORM           │ enqueue          │ pub/sub / commands
        ┌───▼────┐     ┌────▼─────┐        ┌───▼──────────────────┐
        │Postgres│     │  Celery  │        │        Redis         │
        │(state, │     │(agg,     │        │ broker · cache ·      │
        │ config,│◄────┤ reports, │        │ session cmd bus ·     │
        │ series)│     │ cleanup) │        │ live pub/sub · heartbt│
        └───▲────┘     └──────────┘        └───┬──────────────────┘
            │ writes (measurements, session state)  │ commands/heartbeat/live
            │                                        │
        ┌───┴────────────────────────────────────────▼──────────────┐
        │            CV PROCESSING RUNTIME (data plane)              │  DATA PLANE
        │ frame acq → detect → track → lane assoc → measure → emit   │
        │ owns GPU · state machine · heartbeat · crash recovery      │
        └────────────────────────────────────────────────────────────┘
```

**Boundaries:** Django never imports CV/GPU code. The CV runtime never serves HTTP. They communicate only via **PostgreSQL (durable state/results)** and **Redis (commands, heartbeats, live pub/sub)**. This keeps the monolith modular and lets the CV runtime later move to a separate host without redesign.

---

## 10. Runtime / Process Architecture (Who does what)

| Runtime | Responsibilities | Never does |
|---|---|---|
| **Django/DRF/Channels** | Auth, authz, config CRUD, session control API, WebSocket fan-out, TwinState reads | GPU inference, long video loops |
| **Celery worker + beat** | Aggregation rollups, report gen, retention/cleanup, scheduled maintenance, SUMO run orchestration | Real-time frame-by-frame CV |
| **CV Runtime** | Video decode, detection, tracking, lane association, per-frame measurement, session lifecycle, GPU ownership, heartbeats | Serve HTTP, own auth |
| **Redis** | Broker, cache, session command bus, heartbeat store, live pub/sub | Durable source of truth |
| **PostgreSQL** | Durable config/operational/analytical/AI-metadata store | Transient messaging |

**Interaction contract:**
- Django writes a `ProcessingSession(state=QUEUED)` row and publishes a `START` command on a Redis session-command channel.
- CV runtime consumes the command, transitions state (persisted to Postgres), streams progress + live measurements to Redis pub/sub (Django Channels relays to WS clients), writes durable measurements to Postgres, and posts heartbeats to Redis (`session:{id}:heartbeat`, TTL).
- Django reads session state from Postgres and heartbeat from Redis for liveness; a watchdog (Celery beat) flags sessions whose heartbeat expired → `FAILED`/recoverable.

---

## 11. CV Processing Architecture

Pipeline stages (each a replaceable component with a typed contract):

```
VideoSource.frames() → Preprocess(resize/color/roi) → DetectionProvider.detect(frame)
 → TrackingProvider.update(detections) → LaneAssociator.assign(tracks, geometry)
 → Measurement(counting lines, occupancy, flow, density, speed-candidate)
 → Emitter(live→Redis, durable→Postgres batched)
```

Design rules:
- **Detection stride / frame skipping** configurable per profile (detect every Nth frame, track in between).
- **Batching** for durable writes (e.g., flush measurements every K frames / T seconds) to avoid per-frame DB churn.
- **Backpressure:** if downstream lags, drop frames (recorded) or skip detection (live) — recorded as `frame_drop_rate` metric, never silent.
- **Deterministic mode** for tests: fixed seed, fixed stride, fixture video → reproducible counts.

---

## 12. Provider Interfaces (Frozen contracts — implementations deferred)

Conceptual signatures (language-agnostic; Python `Protocol`/ABC in Phase 1):

- **`VideoSource`** — `open()`, `frames() -> Iterator[Frame]`, `metadata()`, `close()`; implementations: `LocalFileSource`, `SimulatedStreamSource`, `WebcamSource`, (future) `RTSPSource`.
- **`DetectionProvider`** — `load(config)`, `detect(frame) -> list[Detection]`, `classes()`, `warmup()`, `unload()`; carries `model_name/version/source`.
- **`TrackingProvider`** — `update(detections, frame_meta) -> list[Track]`, `reset()`; reports `id_switch` events.
- **`LaneAssociator`** — `assign(tracks, geometry) -> list[LaneAssignedTrack]`.
- **`SpeedEstimator`** — `estimate(track, calibration) -> SpeedEstimate{value, unit, method, confidence, calibration_version}`.
- **`CongestionEngine`** — `classify(measurements, road_profile) -> CongestionResult{level, reasons[]}`.
- **`IncidentDetector`** (base) — `evaluate(window) -> list[IncidentCandidate]`; `name`, `version`.
- **`PredictionProvider`** — `predict(features) -> Prediction{value, interval, provenance}`.
- **`SimulationAdapter`** — `build_scenario(network, demand)`, `run(scenario, plan, seed)`, `results()`.
- **`SignalOptimizer`** — `optimize(scenario, baseline, objectives, constraints) -> OptimizationResult`.
- **`AlertProvider` / `StorageProvider`** — lifecycle + media persistence contracts.

Every provider exposes identity metadata for AI governance (§ AI metadata tables).

---

## 13. Processing Session State Machine

States:

```
CREATED → QUEUED → INITIALIZING → RUNNING ⇄ (PAUSING→PAUSED→RESUMING→RUNNING)
        → COMPLETING → COMPLETED
Terminal (from most states): FAILED · CANCELLED · STOPPED
```

Rules & race handling:
- **Single writer of session state = CV runtime** (except QUEUED/CANCEL-requested flags set by Django). Django expresses *intent* via command bus + a `requested_action` column; the runtime performs the transition. This avoids two writers racing on `state`.
- **Commands are advisory intents:** `PAUSE/RESUME/STOP/CANCEL` set `requested_action`; runtime reaches a safe frame boundary, then transitions. Prevents mid-frame corruption.
- **Idempotent transitions:** re-issuing `STOP` on an already-STOPPED session is a no-op.
- **Invalid transitions rejected** (e.g., `RESUME` when not `PAUSED`) and logged as observability events.
- **Heartbeat gap** beyond threshold → watchdog moves `RUNNING`→`FAILED(reason=heartbeat_lost)`; session is resumable from last checkpoint (last durable `progress`/frame index).
- **Crash during INITIALIZING** (e.g., model load fail) → `FAILED(reason=model_load)`, no partial results published.
- Every transition writes an `AuditEvent` and a session log line.

---

## 14. GPU Resource Architecture

- **One GPU, one model owner (now).** A `GPUResourceManager` (in the CV runtime) is the *only* component that loads models onto the GPU. Celery/Django never touch CUDA.
- **Single-model, single-session default** on 8 GB VRAM to avoid duplicate model loads / OOM. Concurrency across streams is *configurable* but defaults to 1 heavy model instance; multiple lightweight streams may share one loaded model via a queue.
- **VRAM budgeting:** manager tracks estimated VRAM per loaded model; refuses to load a second model that would exceed a safety headroom (measured, not the arbitrary "80%" rule).
- **CPU fallback:** if CUDA unavailable/failed, provider loads CPU variant and the session is tagged `device=cpu` (much slower — surfaced in UI, not hidden).
- **Future extensibility (interface only):** manager API accepts `device_id` and can enumerate `GPU 0/1` and multiple workers; **not implemented now**. The interface distinguishes future capability from current single-GPU implementation.

---

## 15. Complete Data Flow

```
Upload/Register VideoSource ─(Postgres row)→ Create ProcessingSession(QUEUED)
   → Django publishes START (Redis) → CV runtime picks up
   → per frame: detect→track→lane→measure
        live path:  Redis pub/sub → Channels → WebSocket → dashboard
        durable path: batched TrafficMeasurement rows → Postgres
   → Celery beat rollups: TrafficMeasurement → TrafficAggregate (1m/5m/hr/day)
   → CongestionEngine (on aggregates/window) → CongestionRecord
   → IncidentDetectors (on windows) → IncidentCandidate → Alert
   → Retention jobs archive/delete per tier
   → Analytics API reads aggregates; Twin API reads TwinState
```

Raw per-frame processing and aggregated analytics are **physically separated** (different tables, different writers, different retention).

---

## 16. Database / Domain Architecture (Conceptual + Logical)

Four data domains (separate schemas/table groups; may share one Postgres DB):

**A. Configuration (low-volume, long-lived)**
`City(1)→Zone(N)→Road(N)→RoadSegment(N)→Intersection(N)`; `Intersection(1)→Approach(N)→Lane(N)`; `Camera(N)`—`CameraLaneCoverage(M:N)`—`Lane`; `RegionOfInterest(N per Camera)`, `CountingLine(N per Camera/Lane)`; `CalibrationProfile(N per Camera, versioned)`.

**B. Operational (medium-volume, medium-lived)**
`VideoSource`, `ProcessingSession` (FK: VideoSource, Camera, DetectionModelVersion, TrackingModelVersion, CalibrationProfile, profile), `Alert` (FK: IncidentCandidate, Camera, assignee), `AuditEvent`.

**C. Analytical (high-volume, time-series, tiered retention)**
`TrafficMeasurement` (per short window, per lane/line; **time-partitioned**, short retention), `TrafficAggregate` (1m/5m/hr/day; long retention), `TrackSummary` (per completed track, medium retention), `QueueEvent`, `CongestionRecord`.

**D. AI / Governance metadata**
`DetectionModelVersion`, `TrackingModelVersion`, `PredictionModelVersion`, `CalibrationProfile`, benchmark result records. Immutable/versioned — changing a model creates a **new version row**; historical records keep their original FK so interpretation never silently changes.

**E. Simulation/optimization**
`SimulationScenario`, `SimulationRun` (seed, provenance), `OptimizationExperiment` (baseline plan, candidate plan, objectives, constraints, metrics, improvement), `PredictionRun` (provenance: sim/synthetic/real).

**F. Signals**
`TrafficSignal→SignalGroup→SignalPhase`; `SignalPlan` (cycle, green/amber/all-red, sequence).

**G. Twin**
`TwinState` (latest persistent snapshot per intersection/lane/signal; congestion/queue/incident refs; active session refs).

Key constraints/indexes (representative):
- Uniqueness: `Camera.name` per City; `CountingLine` unique per (Camera, name); model versions unique per (name, version).
- FKs with `PROTECT` on config referenced by analytics (can't delete a Camera with measurements) — instead soft-archive.
- Indexes: `TrafficMeasurement (session_id, ts)`, `(lane_id, ts)`; `TrafficAggregate (lane_id, bucket, ts)`; `Alert (status, severity, ts)`; `ProcessingSession (state, last_heartbeat)`.
- Time-series: partition `TrafficMeasurement` by time (e.g., daily/weekly) for cheap drop-based retention.

*(No migrations generated in Phase 0 — logical design only.)*

---

## 17. Storage & Retention Architecture (Tiers)

| Tier | Data | Default retention | Lifecycle |
|---|---|---|---|
| T1 | Raw video | User-controlled (default keep until deleted) | Created on upload; deleted on user/policy action; secure delete option |
| T2 | Evidence media (incident snapshots, short clips) | Configurable, tied to alert lifecycle (e.g., keep while alert open + N days) | Created on incident candidate; archived on resolve; purged on policy |
| T3 | Raw detection metadata | Short (e.g., days) | Created per session; aggregated then pruned |
| T4 | Track-level summaries | Medium (e.g., weeks) | Created on track completion; pruned after aggregation window |
| T5 | Aggregated analytics | Long (months–years) | Rolled up from T3/T4; archived, rarely deleted |

Rules: never store every bounding box forever; aggregation is the durable record; media on filesystem (path in DB), not blobs in Postgres; all retention values are settings/DB-driven, not hardcoded.

---

## 18. Real-Time Architecture

- **Django Channels (ASGI)** provides WebSocket endpoints; **Redis pub/sub** is the channel layer backend.
- CV runtime publishes live measurements/session progress to Redis channels (`live:session:{id}`); Channels consumers relay to subscribed dashboard clients.
- Backpressure: live channel is **lossy by design** (latest-wins for gauges); durable truth is Postgres. WS drop does not lose data.
- Auth on WS: token-authenticated connection; server-side permission check per subscription (no relying on frontend).

---

## 19. Computer Vision Strategy

Recorded-first, provider-driven. Preprocessing (resize to profile resolution, ROI crop), detection at stride, tracking to interpolate, lane association by geometry, measurement by counting-line crossing + polygon occupancy. All classes mapped to a **canonical vehicle taxonomy** (car/motorcycle/bus/truck/bicycle/pedestrian) regardless of the underlying model's native labels, so model swaps don't change analytics semantics.

---

## 20. Model Benchmarking Strategy (Gate before model freeze)

Candidates (examples, not committed): a small/medium real-time detector family (e.g., a YOLO-class model in n/s/m sizes) + a lightweight tracker (e.g., a ByteTrack/SORT-family algorithm). **No version frozen now.**

Benchmark harness measures, on *your* laptop, per candidate × per resolution × per stride:
- Accuracy proxy (mAP on a labeled fixture set / count error vs manual ground-truth clips)
- FPS (end-to-end), processing latency, frame_drop_rate
- VRAM, RAM, CPU utilization, thermal stability over a sustained run
- Tracking stability: ID switches, fragmentation
- Integration effort, licensing (must be permissive/self-hostable)

Output: three **operating profiles** with *measured* settings:

- **Quality Mode** — larger model, full resolution, low stride → max accuracy, lower FPS.
- **Balanced Mode** — mid model/resolution/stride → default.
- **Performance Mode** — small model, reduced resolution, high stride → max FPS.

Thresholds (acceptable FPS/latency/VRAM per profile) are set **from these measurements**, then written into an ADR. The default detection/tracking provider is selected here.

---

## 21. Tracking Strategy

Detection-based tracking (associate detections across frames), tuned for stride-based detection with motion interpolation between detected frames. Counting is **crossing-based with per-track dedup** (a track counts once per counting line per direction). ID switches are measured and surfaced; excessive switching triggers a benchmark re-tune, not silent acceptance.

---

## 22. Lane Analytics Strategy

Geometry defined by user: lane polygons, counting lines, stop lines, ROIs, restricted zones (stored in Configuration domain, per camera, in image coordinates + optional world coords when calibrated). Per-lane metrics: occupancy (fraction of polygon covered / time occupied), count, avg speed (method-tagged), density (vehicles per unit length when calibrated, else per-polygon proxy labeled as such), flow rate, queue length.

---

## 23. Speed Estimation Strategy (Three explicit tiers)

| Tier | Method | Output label | When |
|---|---|---|---|
| 1 | **Pixel motion** | "relative motion" (no km/h) | Always available |
| 2 | **Image-plane approximation** | approximate speed, flagged low-confidence | Rough local scale known |
| 3 | **World-coordinate speed** | calibrated speed (km/h) | Homography/perspective calibration exists |

Every `SpeedEstimate` carries `{value, unit, method, calibration_profile, calibration_version, confidence, timestamp}`. **Pixel motion is never displayed as km/h.** Uncalibrated estimates are visually flagged in UI.

---

## 24. Queue Detection Methodology

Queue = contiguous set of stopped/slow tracks upstream of a stop line within a lane polygon. Computes queue start (nearest to stop line), queue end (furthest contiguous stopped vehicle), length (pixels → meters if calibrated, else labeled proxy), queued-vehicle count, duration. Emits `QueueEvent` with start/end timestamps. Intersection-scoped via Approach→Lane linkage.

---

## 25. Congestion Methodology (Explainable, profile-driven)

No universal hardcoded formula. Each Road/RoadType has a **congestion profile** parameterized by: road type, lane count, free-flow speed, capacity, and thresholds over {occupancy, density, avg speed, queue length, flow}. A deterministic rule engine maps measured inputs → level (Free flowing / Light / Moderate / Heavy / Severe) and returns **reasons[]** (e.g., "avg_speed 12 km/h < 30% free-flow AND occupancy 0.82 > 0.7"). SEVERE always comes with the triggering measurements. Profiles are DB/settings-driven, not code constants.

---

## 26. Incident Detection Architecture (Modular detectors)

Independent detectors implementing a common `IncidentDetector` interface, each versioned:
`StoppedVehicleDetector`, `WrongWayDetector`, `SuddenSlowdownDetector`, `LaneBlockageDetector`, `PotentialCollisionDetector` (and extensible).

Each `IncidentCandidate` records: detector, detector_version, evidence (snapshot/clip refs), confidence, triggering measurements, timestamp, location (camera/lane/approach), processing_session. **All results are candidates until verified** via the alert lifecycle. No detector claims certainty.

---

## 27. Alert Architecture

Lifecycle: `DETECTED → PENDING_REVIEW → ACKNOWLEDGED → INVESTIGATING → RESOLVED | DISMISSED`. Alert fields: type, severity, camera, location, timestamp, confidence, supporting evidence, snapshot, video segment ref, status, assigned operator. Every state change is audited. Alerts are created from incident candidates (1:1 or grouped). Assignment respects roles (Incident Operator, etc.).

---

## 28. Simulation Architecture (SUMO via adapter)

- **SimulationAdapter** owns all SUMO coupling. Platform domain model is **never** directly serialized to SUMO file formats in business logic.
- **Platform → SUMO:** network topology (roads/segments/intersections/lanes), demand (from counts/synthetic), signal plans → adapter builds `.net/.rou/.add` (or via libsumo API).
- **SUMO owns:** microscopic vehicle dynamics, car-following, junction control during a run.
- **Platform owns:** scenario definitions, versioning, demand generation, result interpretation, comparison.
- **Versioning:** `SimulationScenario` versioned; `SimulationRun` records seed + input version + provenance.
- **Results → platform:** adapter parses SUMO outputs (tripinfo, queue, e-detectors) into platform metrics for baseline-vs-candidate comparison.

---

## 29. Signal Optimization Architecture (Simulation + recommendation only)

Hard safety boundary: **no physical control.** Progressive optimizers behind `SignalOptimizer`:
1. Fixed-timing baseline → 2. Rule-based adaptive → 3. Optimization algorithms → 4. advanced/RL only if justified.

Every `OptimizationExperiment` records: baseline plan, candidate plan, objectives (min wait / min queue / max throughput / min stops), constraints (min green, max cycle, safety intergreen), scenario, seed, metrics, and measured improvement/degradation vs baseline. **No "better" claim without simulation evidence.** Controller integration exists only as an inactive interface.

---

## 30. Prediction Architecture

`PredictionProvider` produces provenance-tagged predictions. **Model provenance** is mandatory: a model trained on simulation/synthetic data is labeled *not validated for real-world* and cannot be presented as authoritative for live traffic. Every model compared against naive baselines (last-value, historical-average, seasonal-naive). Uses historical public datasets + SUMO-generated + (later) real collected data. `PredictionModelVersion` + `PredictionRun` capture training domain, metrics vs baseline, and interval estimates.

---

## 31. Digital Twin Architecture

- **Backend `TwinState`** (persistent): latest known state of intersections, lanes, signals, congestion, queues, incidents, active sessions — the durable, queryable twin.
- **Ephemeral live state**: individual vehicle positions/animation streamed via WebSocket, **not persisted per frame**.
- Clear split: persistent aggregate state (DB) vs ephemeral live overlay (Redis/WS). Initial UI is simplified 2D. Vehicles included in twin only when meaningful (e.g., tracked within an active session view), never mass-persisted.

---

## 32. Security & Privacy Architecture

- **AuthN:** JWT access + refresh; short-lived access, rotating refresh.
- **AuthZ:** server-side role/permission enforcement on every REST + WS endpoint (roles: System Admin, Traffic Admin, Traffic Operator, Traffic Analyst, Incident Operator, Viewer). Frontend restrictions are UX only.
- **Privacy (designed now, phased impl):** face-blur and plate-blur hooks in the media pipeline (blur, **not** recognition/OCR); video-access permissions; evidence-access auditing; configurable retention; secure deletion.
- **Explicit prohibitions (frozen):** no face recognition, no person identification, no plate OCR. Traffic intelligence ≠ surveillance.
- **Audit:** `AuditEvent` for auth, config changes, session control, alert transitions, evidence access.
- **Secrets:** environment/settings-based, never hardcoded; `.env` excluded from VCS.

---

## 33. Failure & Recovery Strategy

| Failure | Behavior |
|---|---|
| Django crashes | CV runtime + Celery continue; sessions keep writing to Postgres; API resumes on restart; no state lost |
| Redis crashes | Live/pub-sub + command bus down; durable state safe in Postgres; runtime buffers/checkpoints; commands retried on reconnect; heartbeat watchdog tolerant of transient loss |
| PostgreSQL unavailable | Runtime pauses durable writes, buffers to bounded local checkpoint, retries with backoff; if exhausted → session `FAILED(reason=db_unavailable)`, resumable |
| CV runtime crashes | Heartbeat expires → watchdog marks `FAILED/recoverable`; session resumable from last durable frame index/checkpoint; no duplicate counts (idempotent by frame index) |
| GPU inference fails | Provider retries; if persistent, CPU fallback (tagged) or `FAILED(reason=gpu)`; never fabricates detections |
| Corrupted video | Validated at registration; per-frame decode errors skipped + counted; if unreadable → `FAILED(reason=corrupt_source)` |
| Model load fails | `FAILED(reason=model_load)` during INITIALIZING; no partial results |
| Processing interrupted | Checkpointed frame index enables resume; idempotent measurement writes keyed by (session, frame, entity) |
| WS disconnect | Client reconnects; live is lossy; on reconnect client re-reads durable state from REST |

Idempotency boundary: measurement writes keyed by `(session_id, frame_index, lane/line, track)` so replays don't double-count.

---

## 34. Observability Strategy (Local-first)

- **Structured logs** (JSON) with `session_id` correlation across Django/Celery/CV runtime.
- **Processing/session logs**: per-session log stream traceable start→completion.
- **Metrics**: FPS, latency, frame_drop_rate, VRAM, RAM, CPU, throughput — collected by CV runtime, exposed via a metrics endpoint / stored to a metrics table; visualized in dashboard.
- **GPU metrics** via NVIDIA tooling (nvml/nvidia-smi) polled by the runtime.
- **Error events + AuditEvents** persisted.
- **No heavy external observability stack** (no Prometheus/Grafana/ELK required) for laptop; those are optional later ADRs.

---

## 35. Testing Strategy

- **Unit / integration / API / permission / failure** tests every phase.
- **Deterministic CV fixtures:** small labeled clips + fixed seeds/stride → reproducible counts; golden-value assertions.
- **Adversarial video fixtures:** empty, corrupted, unsupported format, no detections, dense traffic, low-light, camera movement, mid-processing failure.
- **Permission matrix tests** per role per endpoint (server-side).
- **State-machine tests:** every valid transition + rejection of invalid ones + heartbeat-loss recovery.
- Phase is **not complete because "the app starts."** Each phase has explicit acceptance criteria + a verification report.

---

## 36. AI Evaluation Strategy

- Labeled evaluation set (public datasets + hand-labeled local clips) before any accuracy claim.
- Detection: mAP/precision/recall on eval set; counting: error vs manual ground truth.
- Tracking: MOTA-style proxies, ID switches.
- Prediction: vs naive baselines with confidence intervals.
- **Reproducibility:** every result tagged with model name/version/source/config/thresholds/benchmark; changing a model = new version, historical interpretation preserved.
- **No accuracy claim without an eval dataset; no "AI" label just because a method is complex.**

---

## 37. Performance Benchmarking Strategy

Benchmark suite (Phase-early) produces, on your hardware: per profile × model × resolution × stride → FPS, latency, frame_drop_rate, VRAM, RAM, CPU, thermal drift over sustained runs. Results define the three profiles' thresholds and feed graceful-degradation logic (auto-downshift profile when limits hit). **Benchmark before optimizing; never claim improvement without measurement.**

---

## 38. Laptop Limitations & Mitigations

| Limitation | Mitigation |
|---|---|
| 8 GB VRAM | Single-model owner; profile-based model sizing; VRAM budgeting; CPU fallback |
| 16 GB RAM | Bounded buffers; batched DB writes; frame-skip; limited concurrent sessions (default 1–2) |
| Single GPU | GPUResourceManager serializes heavy inference; multi-GPU is interface-only |
| Thermal throttling | Sustained-run thermal benchmark; profiles chosen for stability, not peak |
| No real cameras | Recorded/simulated sources behind `VideoSource`; RTSP later without redesign |
| Windows-native Redis | Memurai or WSL2 (decision D3) |

---

## 39. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | GPU OOM from duplicate model loads | Med | High | Single model owner; VRAM budgeting; §14 |
| R2 | Real-time expectations exceed laptop | High | Med | Profiles + graceful degradation; recorded-first; explicit non-goal |
| R3 | Model choice premature | Med | Med | Benchmark gate; provider interfaces; §20 |
| R4 | Session state corruption / double counting | Med | High | State machine single-writer + idempotency keys; §13/§33 |
| R5 | Speed misrepresented as accurate | Med | High | Three-tier method tagging; §23 |
| R6 | Incident false certainty | Med | High | Candidate-only model; §26 |
| R7 | SUMO tight coupling | Med | Med | SimulationAdapter; §28 |
| R8 | Privacy/legal exposure from video | Med | High | Blur hooks, access audit, retention, no recognition; §32 |
| R9 | Scope creep (city-scale on laptop) | High | Med | MVP boundary + non-goals + phased roadmap |
| R10 | Data explosion (per-frame storage) | Med | High | Retention tiers + aggregation; §17 |
| R11 | Windows-native infra friction (Redis/CUDA) | Med | Med | Documented native setup; WSL2 option; benchmark early |
| R12 | Next.js 15 / React 19 churn | Low | Med | Pin 15.3.4 + pnpm lockfile; ADR |

---

## 40. Final Development Roadmap (Dependency-aware, revised)

Foundational infra pulled **earlier** than the original 17-phase plan (session engine, CV runtime, GPU, observability, retention are prerequisites, not late add-ons).

- **Phase 0 — Architecture freeze (this doc).** *(Docs only.)*
- **Phase 1 — Platform Foundation:** Django/DRF/Channels, Postgres, Redis, Celery, JWT auth + roles, base Next.js app, structured logging. Depends: P0.
- **Phase 2 — Observability + AI governance tables + retention framework** (moved early). Depends: P1.
- **Phase 3 — Traffic Network Model** (City→…→Lane, cameras, ROIs, counting lines). Depends: P1.
- **Phase 4 — Video Source Abstraction + Upload + validation.** Depends: P1.
- **Phase 5 — Processing Session Engine + CV Runtime skeleton + GPU manager** (lifecycle, heartbeats, recovery; no detection yet). Depends: P2, P4.
- **Phase 6 — Detection provider + Benchmark suite + profile selection.** Depends: P5.
- **Phase 7 — Tracking provider.** Depends: P6.
- **Phase 8 — Traffic Measurement** (counting, lane analytics, flow, density, occupancy). Depends: P3, P7.
- **Phase 9 — Speed & Queue Intelligence** (calibration, three-tier speed, queues). Depends: P8.
- **Phase 10 — Congestion Engine** (profiles, explainable). Depends: P8.
- **Phase 11 — Incident Detectors + Alert lifecycle.** Depends: P9, P10.
- **Phase 12 — Operations Dashboard** (overview, live WS, analytics, alerts, map). Depends: P8–P11.
- **Phase 13 — Simulation (SUMO adapter).** Depends: P3.
- **Phase 14 — Signal Model + Plans.** Depends: P3, P13.
- **Phase 15 — Signal Optimization** (baseline→adaptive→optimization, benchmarked). Depends: P14.
- **Phase 16 — Prediction** (provenance-tagged, vs baselines). Depends: P2, P8, P13.
- **Phase 17 — Digital Twin** (TwinState + live overlay). Depends: P8–P12, P14.
- **Phase 18 — Performance & Scale testing.** Depends: all.
- **Phase 19 — Production-readiness interfaces** (RTSP, edge, multi-GPU, controller stubs, optional Docker). Depends: all.

---

## 41. Development Time Estimates

Assumptions: 1 developer, this laptop, ~4–8 productive hrs/day. **Estimates, not guarantees.**

| Phase | Optimistic | Realistic | High-complexity |
|---|---|---|---|
| 1 Foundation | 5 d | 9 d | 15 d |
| 2 Observability/governance/retention | 3 d | 6 d | 10 d |
| 3 Network model | 4 d | 7 d | 12 d |
| 4 Video sources | 3 d | 5 d | 9 d |
| 5 Session engine + CV runtime + GPU | 7 d | 12 d | 20 d |
| 6 Detection + benchmark | 5 d | 9 d | 16 d |
| 7 Tracking | 4 d | 7 d | 12 d |
| 8 Measurement | 6 d | 10 d | 16 d |
| 9 Speed & queue | 6 d | 11 d | 18 d |
| 10 Congestion | 3 d | 6 d | 10 d |
| 11 Incidents + alerts | 6 d | 10 d | 17 d |
| 12 Dashboard | 8 d | 14 d | 22 d |
| 13 SUMO adapter | 6 d | 11 d | 18 d |
| 14 Signal model | 3 d | 6 d | 10 d |
| 15 Signal optimization | 7 d | 12 d | 20 d |
| 16 Prediction | 6 d | 11 d | 18 d |
| 17 Digital twin | 7 d | 12 d | 20 d |
| 18 Perf/scale | 4 d | 7 d | 12 d |
| 19 Production interfaces | 5 d | 9 d | 16 d |
| **Total** | **~104 d** | **~184 d** | **~311 d** |

Roughly **5 / 9 / 15 calendar months** at a sustainable solo pace (optimistic/realistic/high-complexity), excluding extended idle waits.

---

## 42. Phase 0 Acceptance Checklist

Phase 0 is **documentation-only**. Criteria (each PASS/FAIL/NOT-TESTED):

- [ ] Product scope, MVP boundary, full scope documented — **PASS**
- [ ] Explicit non-goals frozen — **PASS**
- [ ] Functional + non-functional requirements — **PASS**
- [ ] Final technology stack (Next 15.3.4, no mandatory Docker) — **PASS**
- [ ] System + runtime (3-runtime) architecture — **PASS**
- [ ] CV processing architecture + provider interfaces — **PASS**
- [ ] Processing session state machine (races/invalid transitions) — **PASS**
- [ ] GPU resource architecture (single-GPU now, extensible) — **PASS**
- [ ] Complete data flow — **PASS**
- [ ] Database/domain model (conceptual+logical, no migrations) — **PASS**
- [ ] Storage + retention tiers — **PASS**
- [ ] Real-time architecture — **PASS**
- [ ] Speed (3-tier), congestion (profile/explainable), queue methodologies — **PASS**
- [ ] Modular incident detection + alert architecture — **PASS**
- [ ] Simulation (adapter) + signal optimization (sim/recommend only) — **PASS**
- [ ] Prediction provenance — **PASS**
- [ ] Digital twin state model (persistent vs ephemeral) — **PASS**
- [ ] Security/privacy (no recognition/OCR) — **PASS**
- [ ] Failure/recovery + observability + testing + AI eval + benchmarking strategies — **PASS**
- [ ] Corrected performance requirements (profiles, benchmark-first) — **PASS**
- [ ] Risk register + dependency-aware roadmap + time estimates — **PASS**
- [ ] No application code / repo / migrations / installs performed — **PASS**

---

## 43. Architecture Decision Records Required Before Implementation

To be authored/approved at the start of the relevant phase:

- **ADR-001** Frontend baseline: Next.js 15.3.4 + React 19 + pnpm (App Router).
- **ADR-002** Three-runtime split (Django / Celery / CV runtime) + comms via Postgres + Redis.
- **ADR-003** Processing session state machine + single-writer + idempotency keys.
- **ADR-004** GPU resource manager (single-GPU now, multi-GPU interface).
- **ADR-005** Detection/tracking provider selection (output of benchmark gate).
- **ADR-006** Data retention tiers + time-partitioning strategy.
- **ADR-007** Speed estimation three-tier method tagging.
- **ADR-008** Congestion profile schema.
- **ADR-009** SimulationAdapter boundary + SUMO coupling.
- **ADR-010** Signal optimization safety boundary (no physical control).
- **ADR-011** Redis on Windows: Memurai vs WSL2 (decision D3).
- **ADR-012** Observability: local structured logging + metrics (no external stack).

---

## FINAL ARCHITECTURE REVIEW

### Critical Decisions (now frozen)
1. Modular monolith, **three-runtime** process split (Django / Celery / CV runtime).
2. **Native Windows first; Docker optional and not a Phase-0 deliverable.**
3. **Next.js 15.3.4** + React 19 + TypeScript + Tailwind + **pnpm** (no downgrade to 14).
4. **No AI model frozen** — provider interfaces + benchmark gate select the default.
5. Performance = **three measured profiles** (Quality/Balanced/Performance); no pre-benchmark FPS guarantees; the arbitrary "CPU<50% / VRAM<80%" hard rules are **removed**.
6. **ProcessingSession** state machine with single-writer + idempotency + heartbeat recovery.
7. **GPUResourceManager** single-owner; multi-GPU is interface-only.
8. **Five-tier retention**; aggregation is the durable record.
9. Speed **three-tier** method tagging; congestion **profile-driven + explainable**; incidents **candidate-only, modular**.
10. **SimulationAdapter** decouples SUMO; signal optimization is **simulation + recommendation only** (no physical control).
11. Prediction **provenance-tagged** (sim vs real).
12. Twin = **persistent TwinState + ephemeral live overlay**.
13. **No face recognition / person ID / plate OCR**; privacy blur + audit designed now.
14. Foundational infra (session engine, CV runtime, GPU, observability, retention) moved **early** in the roadmap.

### Decisions — RESOLVED (approved 2026-07-15)
- **D1 — Database instance topology → Option A (APPROVED).** One PostgreSQL instance, four logical schemas (config/operational/analytical/ai). Separation enforced by schema discipline; single backup/connection pool. Split into separate DBs later only if a domain outgrows the box.
- **D2 — Time-series storage → Option A (APPROVED).** Plain PostgreSQL with native declarative partitioning now. TimescaleDB deferred and evaluated later **only if justified by measured requirements**; migration to Timescale would be additive.
- **D3 — Redis on Windows → most reliable free native option, else WSL2 (APPROVED).** No paid dependency. Phase 1 will verify a native, free Redis-compatible server first; if none proves reliable in this environment, fall back to Redis under WSL2. Final choice recorded in ADR-011 after Phase 1 verification.

### Architecture Contradictions Found & Resolved
- **Next.js version:** master prompt left it generic; correction mandates **15.3.4** — frozen (was at risk of silent 14 downgrade).
- **Docker:** original implied Compose as setup; correction makes it **optional, non-Phase-0** — resolved.
- **Performance rules:** original "CPU<50% / GPU<80%" hard criteria contradict "benchmark before optimizing" — **removed** in favor of measured profiles.
- **CV in Celery:** original leaned on Celery for heavy CV; correction introduces a **dedicated CV runtime** — resolved (Celery = short/medium jobs only).
- **Model freeze:** original named YOLO/ByteTrack as chosen; correction **defers to benchmark** behind providers — resolved.
- **Incident "detection" certainty:** language tightened to **candidates requiring verification** — resolved.

### Final Phase 0 Status
**✅ APPROVED & FROZEN (2026-07-15)** — approved by the project owner with decisions D1=A, D2=A, D3=native-free-else-WSL2. This architecture is now the authoritative baseline. Any change requires a new ADR and re-approval.

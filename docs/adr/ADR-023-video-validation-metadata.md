# ADR-023 — Video Validation and Metadata Strategy

**Status:** Accepted (Phase 4)

## Decision (D2)
Use **PyAV (`av==13.1.0`)** for Phase 4 video ingestion, **strictly scoped** to:
1. Validating that an uploaded file is a genuinely readable video (open container
   + stream).
2. Extracting basic metadata (container, codec, duration, width, height, fps,
   best-effort frame count).
3. Decoding **one** frame for an optional thumbnail (ADR/plan §12).

**This is NOT the Phase 5 frame-processing decoder architecture.** Full frame
iteration, sampling, seeking, and processing performance are a Phase 5 decision
(separate ADR later). PyAV usage in Phase 4 is limited to the three items above.

## Rationale
- Verified working on Python 3.12.9 / Windows (libavcodec 61.x bundled): probe +
  single-frame decode succeed. No system FFmpeg/ffprobe on PATH is required.
- Single self-contained pip dependency with accurate stream metadata; the same
  tool Phase 5 will build on (no throwaway).

## FFmpeg / licensing
Functionality comes from PyAV's **bundled** libav — no system PATH binary, no
runtime downloads. Availability is detected at startup (import `av`; report
version; surfaced via a `/api/readyz` decoder check). **The bundled-FFmpeg license
must be reviewed before commercial redistribution** (mitigation: a self-built
LGPL-only FFmpeg or an external `ffprobe` path). Nothing is downloaded at runtime.

## Fallbacks (documented, not default)
- OpenCV-headless — lighter API, less accurate metadata — only if PyAV wheels fail
  on the target Windows host.
- ffprobe/ffmpeg subprocess (external, user-installed FFmpeg) — license-clean path.

**No fake fallback:** if no decoder is importable/functional, validation FAILS
clearly with `decoder_unavailable`. A file that cannot be decoded is never marked
`valid`.

## Frame-count caveat
`frame_count` is best-effort (VBR/some containers report inaccurately); it is
stored as informational metadata and is NOT relied upon for processing in Phase 4.

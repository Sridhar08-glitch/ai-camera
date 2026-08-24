# Run the standalone Phase 5 CV processing runtime (data plane).
# Separate process from the Django ASGI server and Celery worker (ADR-002/025).
# Requires PostgreSQL 18 and Memurai (Redis) running. No AI/GPU model is loaded.
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"
$py = ".\.venv\Scripts\python.exe"
& $py manage.py run_cv_runtime @args

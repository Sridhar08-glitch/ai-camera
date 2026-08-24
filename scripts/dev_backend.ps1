# Run the backend ASGI server (Django + Channels) on 127.0.0.1:8000.
# Applies migrations first. Requires PostgreSQL 18 and Memurai running.
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"
$py = ".\.venv\Scripts\python.exe"
& $py manage.py migrate
& $py -m uvicorn config.asgi:application --host 127.0.0.1 --port 8000 --reload

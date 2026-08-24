# Run Celery worker and beat. On Windows the worker uses the solo pool and beat
# MUST run as a separate process (embedded -B is unsupported on Windows).
# This script starts the worker in the foreground and beat in a new window.
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"
$celery = ".\.venv\Scripts\celery.exe"

Start-Process -FilePath $celery -ArgumentList "-A","config","beat","--loglevel=info" -NoNewWindow
& $celery -A config worker --pool=solo --loglevel=info

# Non-destructive reproducibility check (Phase 2 §12 / debt 3.3).
# Recreates dependencies/config in THROWAWAY locations and tears them down.
# Never touches the working venv, the `aitraffic` database, or node_modules.
#
# Requires (bootstrap-only): $env:PGPASSWORD (postgres superuser) to create/drop
# the throwaway database. App runtime still uses aitraffic_app.

param(
    [string]$DbHost = "127.0.0.1",
    [string]$Port = "5432"
)
# Continue (not Stop): native tools (pip/pnpm) write notices to stderr which must
# not abort the run. Critical steps are checked explicitly via their outputs.
$ErrorActionPreference = "Continue"
$repo = Split-Path $PSScriptRoot -Parent
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
$tmp = Join-Path $env:TEMP ("p2repro_" + [System.IO.Path]::GetRandomFileName().Substring(0,6))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$reproDb = "aitraffic_repro"
$results = @()

function Record($name, $ok, $detail) {
    $res = "FAIL"; if ($ok) { $res = "PASS" }
    $script:results += [pscustomobject]@{ Check = $name; Result = $res; Detail = $detail }
}

try {
    # 1. Fresh backend virtualenv from pinned requirements.
    Write-Host "[1/4] Fresh venv install..." -ForegroundColor Cyan
    py -3.12 -m venv "$tmp\venv"
    & "$tmp\venv\Scripts\python.exe" -m pip install -q -r "$repo\backend\requirements\dev.txt" 2>&1 | Out-Null
    $imp = & "$tmp\venv\Scripts\python.exe" -c "import django,channels,celery,psycopg,structlog,rest_framework_simplejwt,redis; print('ok')"
    Record "fresh_venv_imports" ($imp.Trim() -eq "ok") $imp.Trim()

    # 2. Throwaway database: create (as superuser, owned by aitraffic_app), migrate, seed check, drop.
    Write-Host "[2/4] Throwaway database migrate..." -ForegroundColor Cyan
    if (-not $env:PGPASSWORD) { throw "Set `$env:PGPASSWORD (postgres) for the throwaway DB." }
    & $psql -h $DbHost -p $Port -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $reproDb;" | Out-Null
    & $psql -h $DbHost -p $Port -U postgres -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $reproDb OWNER aitraffic_app;" | Out-Null
    $env:DATABASE_URL_REPRO = "postgresql://aitraffic_app:$($env:AITRAFFIC_APP_PASSWORD)@$DbHost`:$Port/$reproDb"
    Push-Location "$repo\backend"
    $env:DATABASE_URL = $env:DATABASE_URL_REPRO
    $migrate = & "$tmp\venv\Scripts\python.exe" manage.py migrate 2>&1 | Select-Object -Last 1
    $roles = & "$tmp\venv\Scripts\python.exe" manage.py shell -c "from apps.accounts.models import Role; print(Role.objects.count())" 2>&1 | Select-Object -Last 1
    Pop-Location
    Record "throwaway_db_migrate" ($roles.Trim() -eq "6") "roles=$($roles.Trim())"

    # 3. Frontend clean install + build in a temp copy (does not touch working node_modules).
    Write-Host "[3/4] Frontend clean install + build..." -ForegroundColor Cyan
    $feTmp = Join-Path $tmp "frontend"
    New-Item -ItemType Directory -Force -Path $feTmp | Out-Null
    Copy-Item "$repo\frontend\package.json","$repo\frontend\pnpm-lock.yaml","$repo\frontend\tsconfig.json","$repo\frontend\next.config.ts","$repo\frontend\postcss.config.mjs","$repo\frontend\tailwind.config.ts","$repo\frontend\.eslintrc.json" $feTmp
    Copy-Item "$repo\frontend\src" (Join-Path $feTmp "src") -Recurse
    Push-Location $feTmp
    $env:COREPACK_HOME = "$env:LOCALAPPDATA\node\corepack"
    & corepack pnpm install --frozen-lockfile 2>&1 | Out-Null
    "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1`nNEXT_PUBLIC_WS_URL=ws://localhost:8000/ws" | Out-File -Encoding utf8 ".env.local"
    & corepack pnpm run build 2>&1 | Out-Null
    $built = Test-Path (Join-Path $feTmp ".next")
    Pop-Location
    Record "frontend_clean_build" $built "next build produced .next=$built"

    Record "note" $true "Independent recreation: venv, throwaway DB, temp frontend. NOT recreated: OS-level PostgreSQL/Memurai services, aitraffic_app role."
}
finally {
    # 4. Teardown — restore env + drop throwaway DB + remove temp dir.
    Write-Host "[4/4] Teardown..." -ForegroundColor Cyan
    try { & $psql -h $DbHost -p $Port -U postgres -d postgres -c "DROP DATABASE IF EXISTS $reproDb;" | Out-Null } catch {}
    Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:\DATABASE_URL_REPRO -ErrorAction SilentlyContinue
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}

$results | Format-Table -AutoSize
if ($results | Where-Object { $_.Result -eq "FAIL" }) { exit 1 } else { Write-Host "CLEAN SETUP: OK" -ForegroundColor Green }

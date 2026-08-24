# Idempotently create the four logical domain schemas in the aitraffic database.
# Phase 1 schema strategy (ADR-013): Phase 1 tables live in `public`; these
# schemas exist for Phase 3+ domain tables (config/operational/analytical/ai).
# Requires PostgreSQL 18 on 127.0.0.1:5432 (Memurai/PG passwords from your env).
param(
    [string]$DbHost = "127.0.0.1",
    [string]$Port = "5432",
    [string]$DbUser = "postgres",
    [string]$DbName = "aitraffic"
)
$ErrorActionPreference = "Stop"
if (-not $env:PGPASSWORD) {
    Write-Host "Set `$env:PGPASSWORD before running (not stored in the repo)." -ForegroundColor Yellow
    exit 1
}
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
$sql = @"
CREATE SCHEMA IF NOT EXISTS config;
CREATE SCHEMA IF NOT EXISTS operational;
CREATE SCHEMA IF NOT EXISTS analytical;
CREATE SCHEMA IF NOT EXISTS ai;
"@
$sql | & $psql -h $DbHost -p $Port -U $DbUser -d $DbName -v ON_ERROR_STOP=1
Write-Host "Schemas ensured in $DbName." -ForegroundColor Green

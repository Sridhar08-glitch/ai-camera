# Idempotent bootstrap of the least-privilege application role `aitraffic_app`
# (ADR-014). Run ONCE by the developer using the postgres superuser. This is the
# only administrative bootstrap that needs the superuser; runtime uses aitraffic_app.
#
# Requires:
#   $env:PGPASSWORD            = <postgres superuser password>   (admin bootstrap only)
#   $env:AITRAFFIC_APP_PASSWORD = <password for aitraffic_app>   (never hardcoded)
#
# Safe to run repeatedly. Does NOT alter or delete the postgres superuser.

param(
    [string]$DbHost = "127.0.0.1",
    [string]$Port   = "5432",
    [string]$Admin  = "postgres",
    [string]$DbName = "aitraffic"
)
$ErrorActionPreference = "Stop"
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"

if (-not $env:PGPASSWORD) {
    Write-Host "ERROR: set `$env:PGPASSWORD (postgres superuser password) first." -ForegroundColor Red
    exit 1
}
if (-not $env:AITRAFFIC_APP_PASSWORD) {
    Write-Host "ERROR: set `$env:AITRAFFIC_APP_PASSWORD (app role password) first." -ForegroundColor Red
    exit 1
}

# Step 1: create/adjust the role (cluster level) + CONNECT grant.
$roleSql = @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'aitraffic_app') THEN
    CREATE ROLE aitraffic_app LOGIN;
  END IF;
END
`$`$;
ALTER ROLE aitraffic_app WITH LOGIN NOSUPERUSER NOCREATEROLE NOREPLICATION NOBYPASSRLS CREATEDB PASSWORD :'pw';
GRANT CONNECT ON DATABASE $DbName TO aitraffic_app;
"@
$roleSql | & $psql -h $DbHost -p $Port -U $Admin -d postgres -v ON_ERROR_STOP=1 -v pw="$($env:AITRAFFIC_APP_PASSWORD)"
if ($LASTEXITCODE -ne 0) { Write-Host "Role creation failed." -ForegroundColor Red; exit 1 }

# Step 2: schema privileges + targeted ownership transfer of app objects (in target DB).
# We do NOT use REASSIGN OWNED (postgres also owns system objects). Instead we
# transfer only user tables/sequences in public and the reserved domain schemas so
# future migrations run by aitraffic_app can ALTER/DROP them.
$grantSql = @"
GRANT USAGE, CREATE ON SCHEMA public TO aitraffic_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO aitraffic_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO aitraffic_app;

DO `$`$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO aitraffic_app', r.tablename);
  END LOOP;
  FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname='public' LOOP
    EXECUTE format('ALTER SEQUENCE public.%I OWNER TO aitraffic_app', r.sequencename);
  END LOOP;
  FOR r IN SELECT nspname FROM pg_namespace WHERE nspname IN ('config','operational','analytical','ai') LOOP
    EXECUTE format('ALTER SCHEMA %I OWNER TO aitraffic_app', r.nspname);
  END LOOP;
END
`$`$;
"@
$grantSql | & $psql -h $DbHost -p $Port -U $Admin -d $DbName -v ON_ERROR_STOP=1
if ($LASTEXITCODE -ne 0) { Write-Host "Grant/reassign failed." -ForegroundColor Red; exit 1 }

# Step 3: verify attributes.
$verify = & $psql -h $DbHost -p $Port -U $Admin -d postgres -tA -c "SELECT rolsuper, rolcreaterole, rolcreatedb, rolcanlogin FROM pg_roles WHERE rolname='aitraffic_app';"
Write-Host "aitraffic_app [rolsuper,rolcreaterole,rolcreatedb,rolcanlogin] = $verify" -ForegroundColor Green
Write-Host "Expected: f|f|t|t  (NOT superuser, NOT createrole, HAS createdb (dev), can login)" -ForegroundColor Green

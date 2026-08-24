# Run the Next.js dev server on http://localhost:3000.
# Uses pnpm via corepack (global shim not installed; corepack proxy is used).
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\frontend"
$env:COREPACK_HOME = "$env:LOCALAPPDATA\node\corepack"
& corepack pnpm dev

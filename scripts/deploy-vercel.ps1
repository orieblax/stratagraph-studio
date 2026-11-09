# ==============================================================================
# StrataGraph Studio — Vercel Deployment Helper Script (PowerShell)
# ==============================================================================

param (
    [switch]$Production,
    [string]$BackendUrl = ""
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " StrataGraph Studio — Vercel Deployment Manager" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verify Node.js & Vercel CLI
if (-not (Get-Command "node" -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js is not installed or not in PATH."
}
if (-not (Get-Command "vercel" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Vercel CLI globally..." -ForegroundColor Yellow
    npm install -g vercel
}

# 2. Check if Backend URL is provided or prompt
if (-not $BackendUrl -and -not $env:NEXT_PUBLIC_BACKEND_URL) {
    Write-Host ""
    Write-Host "TIP: Enter your deployed FastAPI Backend URL (e.g. https://api.stratagraph.com)" -ForegroundColor Yellow
    $BackendUrl = Read-Host "Backend URL [Press Enter to keep current setting]"
}

# 3. Lint & Typecheck Frontend
Write-Host ""
Write-Host "--> Running Frontend Quality Checks..." -ForegroundColor Green
Set-Location "$PSScriptRoot\..\frontend"
npm run lint
npm run typecheck
npm test

# 4. Build Frontend Locally to Verify Clean Compilation
Write-Host ""
Write-Host "--> Compiling Next.js 15 Production Build..." -ForegroundColor Green
npm run build

# 5. Deploy with Vercel CLI
Write-Host ""
if ($Production) {
    Write-Host "--> Deploying to Vercel PRODUCTION..." -ForegroundColor Green
    if ($BackendUrl) {
        vercel --prod --cwd . -e NEXT_PUBLIC_BACKEND_URL="$BackendUrl" -e BACKEND_URL="$BackendUrl"
    } else {
        vercel --prod --cwd .
    }
} else {
    Write-Host "--> Deploying Vercel PREVIEW deployment..." -ForegroundColor Green
    if ($BackendUrl) {
        vercel --cwd . -e NEXT_PUBLIC_BACKEND_URL="$BackendUrl" -e BACKEND_URL="$BackendUrl"
    } else {
        vercel --cwd .
    }
}

Set-Location "$PSScriptRoot\.."
Write-Host ""
Write-Host "Deployment workflow complete!" -ForegroundColor Cyan

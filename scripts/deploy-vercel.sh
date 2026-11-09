#!/usr/bin/env bash
# ==============================================================================
# StrataGraph Studio — Vercel Deployment Helper Script (Bash)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================================="
echo " StrataGraph Studio — Vercel Deployment Manager"
echo "=========================================================="

# Check Vercel CLI
if ! command -v vercel &> /dev/null; then
    echo "Installing Vercel CLI globally..."
    npm install -g vercel
fi

cd "$ROOT_DIR/frontend"

echo "--> Running Frontend Quality Checks..."
npm run lint
npm run typecheck
npm test

echo "--> Compiling Next.js 15 Production Build..."
npm run build

IS_PROD="${1:-}"

if [ "$IS_PROD" = "--prod" ] || [ "$IS_PROD" = "prod" ] || [ "$IS_PROD" = "-p" ]; then
    echo "--> Deploying to Vercel PRODUCTION..."
    vercel --prod --cwd .
else
    echo "--> Deploying Vercel PREVIEW deployment..."
    vercel --cwd .
fi

echo "Deployment workflow complete!"

# StrataGraph Studio — Vercel Deployment & Management Guide

This guide describes how to deploy and manage **StrataGraph Studio** on **Vercel** with a zero-CORS streaming architecture.

---

## 1. Architecture Overview

Because StrataGraph Studio executes cyclic LangGraph workflows with sandboxed Model Context Protocol (`stdio` MCP) subprocesses and an in-memory quantized Cross-Encoder re-ranker, the production topology is split into two complementary tiers:

```
┌──────────────────────────────────────────────┐
│             Vercel Edge / CDN                │
│  - Next.js 15 App Router & React Flow Canvas │
│  - Next.js Streaming Proxy (/api/backend)    │
│  - Security Headers (CSP, HSTS, X-Frame)     │
└──────────────────────┬───────────────────────┘
                       │ HTTPS / WSS / SSE (Proxied)
                       ▼
┌──────────────────────────────────────────────┐
│        Container Tier (FastAPI Backend)      │
│  (Railway, Render, Fly.io, or GCP Cloud Run) │
│  - LangGraph Cyclic StateGraph               │
│  - Pydantic AI Micro-Agents                  │
│  - Sandboxed stdio MCP Process Pool          │
│  - Quantized Cross-Encoder Re-Ranker         │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│         Managed Database (pgvector)          │
│             (Supabase or Neon)               │
│  - 1536-dim HNSW Cosine Index                │
│  - LangGraph Checkpoints (PostgresSaver)     │
│  - Transactional Outbox (etl_outbox)         │
│  - Two-Tier Semantic Cache (semantic_cache)  │
└──────────────────────────────────────────────┘
```

---

## 2. Deploying the Frontend to Vercel

### Method A: Git Integration via Vercel Dashboard (Recommended)

1. Push your repository to **GitHub** or **GitLab**.
2. Go to [vercel.com/new](https://vercel.com/new) and import the repository.
3. Configure the Project Settings:
   - **Framework Preset:** `Next.js`
   - **Root Directory:** Either leave at root (our root `vercel.json` and `package.json` will auto-delegate) or set to `frontend`.
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`
   - **Install Command:** `npm ci`
4. Add Environment Variables:
   - `NEXT_PUBLIC_BACKEND_URL`: `https://api.your-stratagraph-backend.com`
   - `BACKEND_URL`: `https://api.your-stratagraph-backend.com`
5. Click **Deploy**.

### Method B: Vercel CLI

From your terminal or PowerShell:
```powershell
# From the repository root
npm run deploy:vercel        # For Preview Deployment
npm run deploy:vercel:prod   # For Production Deployment

# Or run the included PowerShell deployment helper:
.\scripts\deploy-vercel.ps1 -Production -BackendUrl "https://api.your-stratagraph-backend.com"
```

---

## 3. Streaming & Zero-CORS Architecture

Vercel functions and client browsers communicate through the built-in streaming proxy route handler located at:
`frontend/src/app/api/backend/[...path]/route.ts`

- **Zero-CORS**: Because the client browser talks to its own Vercel domain (`/api/backend/...`), browser CORS preflight errors are completely avoided.
- **SSE Stream Pass-Through**: The proxy forwards chunked Server-Sent Events (`text/event-stream`) directly from the LangGraph `DualChannelStreamer` to the browser without buffering.
- **Ephemeral Credentials**: Headers such as `X-OpenAI-Key`, `X-Databricks-Token`, and `Authorization` are forwarded securely through the proxy to the backend vault.

---

## 4. Health Check & Monitoring

Once deployed on Vercel, verify your deployment:
```bash
curl https://your-project.vercel.app/api/health
```
Response:
```json
{
  "status": "ok",
  "service": "stratagraph-studio-frontend",
  "deployment_target": "vercel",
  "timestamp": "2026-11-08T22:45:00.000Z",
  "backend_configured": true
}
```

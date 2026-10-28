# Personal GCP Migration & Cost-Optimization Guide (Zero Antigravity Required)

This guide explains how to independently own, migrate, and operate the **Agentic Market Intelligence Platform** on your personal laptop and a personal Google Cloud account **without any dependency on Antigravity**.

---

## 1. Zero-Antigravity Independence Guarantee

The codebase was engineered using **100% standard open-source and Google Cloud components**. Nothing in the runtime, build pipeline, or agent framework requires Antigravity:
- **Frontend**: Standard Next.js 14 / React 18 / TypeScript (`apps/frontend/`), runnable anywhere via `npm run dev` or Docker.
- **Backend & Agents**: Standard Python 3.12+, FastAPI, `google-adk`, `google-genai`, and `google-cloud-bigquery`.
- **Infrastructure**: Standard Terraform (`infrastructure/terraform/`) and standard `gcloud` CLI commands (`scripts/bootstrap_personal_gcp.sh`).

---

## 2. What You Need to Save Before Leaving This Environment

### A. Already Saved in Your Personal GitHub Repository
Everything in the codebase is already pushed to your personal GitHub account:
- **Repository**: `https://github.com/rishysingh/agentic-market-intelligence`
- **Includes**:
  - All Tier 1 (Next.js), Tier 2 (FastAPI, Root Agent, Orchestrator, 11 Specialized Agents, 3 MCP Servers), and Tier 3 (Ingestion, Point-in-Time Feature Store, Calibrated Walk-Forward Models, Backtester) source code.
  - The pre-computed point-in-time snapshot (`data/cache/latest_snapshot.json`, 1.5 MB) containing 20 equities, 18 features, multi-horizon predictions (`1d`, `5d`, `20d`), ranked recommendations, and walk-forward backtests.
  - Terraform IaC (`infrastructure/terraform/`) and GitHub Actions workflows (`infrastructure/ci-workflows/`).
  - Full test suite (`tests/`) and documentation (`docs/`).

### B. Local Copy to Back Up to Your Personal Machine
Clone your GitHub repository onto your personal machine:
```bash
git clone https://github.com/rishysingh/agentic-market-intelligence.git
```
*(Optional)* If you want to copy the Antigravity session design artifacts from this machine before wiping `/Users/rishysingh/.gemini`, copy:
```bash
cp /Users/rishysingh/.gemini/antigravity/brain/756ce53a-a2fe-4bcd-b3d8-ad2b9a04d2b6/*.md \
   /Users/rishysingh/.gemini/antigravity/scratch/agentic-market-intelligence/docs/
```

### C. Optional BigQuery Backup (Before Qwiklabs Project Expires)
You do **not** strictly need to export the Qwiklabs BigQuery tables because running `python3 data/ingestion/pipeline.py --mode full` recreates and reloads all 13 tables automatically in ~15 seconds. However, if you want a raw Parquet/JSON archive of the current BigQuery tables:
```bash
PYTHONPATH=. python3 data/ingestion/pipeline.py --mode full
# Writes full snapshot to data/cache/latest_snapshot.json
```

---

## 3. Cost-Optimized Personal GCP Architecture (~$0 to $3/month)

Google Cloud offers generous **Always Free** tiers for Cloud Run, BigQuery, Cloud Build, Secret Manager, Pub/Sub, and Cloud Scheduler. Here is how to run this platform at near-zero monthly cost on a personal GCP account:

| Service | Personal Cost-Optimized Setting | GCP Free Tier Coverage | Expected Monthly Cost |
|---|---|---|---|
| **Cloud Run (`ami-frontend`)** | `min-instances=0`, `max-instances=2`, `512Mi` RAM, `1 vCPU`, `--cpu-throttling` (request-only billing) | First 2M requests, 180,000 vCPU-sec, 360,000 GiB-sec/month free | **$0.00** |
| **Cloud Run (`ami-backend`)** | `min-instances=0`, `max-instances=2`, `1Gi` RAM, `1 vCPU`, `--cpu-throttling` (request-only billing) | Covered by Cloud Run Always Free tier for personal usage | **$0.00** |
| **Cloud Run Job (`ami-ingestion-job`)** | Runs once per weekday (`~20 sec` per run = `~450 vCPU-sec/month`) | Covered by Cloud Run Always Free tier | **$0.00** |
| **BigQuery (`market_intelligence`)** | 13 partitioned/clustered tables (`< 50 MB` total storage) + `100 MB` max bytes billed per query | First **10 GiB storage** and **1 TiB queries/month** are Always Free | **$0.00** |
| **Cloud Scheduler & Pub/Sub** | 1 scheduler job (`ami-daily-market-refresh`) + 1 topic | First **3 scheduler jobs** and **10 GiB Pub/Sub**/month are Always Free | **$0.00** |
| **Secret Manager** | 1 secret (`ami-api-auth-token`) | First **6 active secret versions** and 10,000 accesses/month are Always Free | **$0.00** |
| **Artifact Registry** | Keep only `:latest` tag (delete old images with a cleanup policy) | First **0.5 GiB storage**/month is Always Free | **$0.00 – $0.20** |
| **Vertex AI Gemini + Google Search Grounding** | Default to `gemini-2.5-flash` for routine runs; invoke `GoogleSearch` grounding only on explicit on-demand ticker deep-dives (cached for 24h in BigQuery) | Pay-per-token / pay-per-grounded-prompt | **$0.50 – $3.00** (depending on live query volume) |

### Key Cost-Saving Switches Built Into the Codebase
1. **Scale-to-Zero (`min-instances=0`)**: When you are not actively viewing the browser terminal, both Cloud Run services scale to **0 instances** and cost **$0.00/hour**.
2. **Smart Snapshot & BigQuery Caching**: Routine UI navigation (`/api/v1/market/overview`, `/api/v1/opportunities`, `/api/v1/stocks/{ticker}`, `/api/v1/performance/backtests`) reads from pre-computed point-in-time records without triggering paid LLM token calls on every page refresh.
3. **Deterministic Fallback Mode**: Even if you disable Vertex AI billing or run completely offline on your laptop, the 11 specialized agents and orchestrator continue to operate using deterministic quantitative/SEC EDGAR analysis.

---

## 4. One-Command Migration to Your Personal GCP Project

When you are ready to deploy to your personal GCP project (e.g. `my-personal-market-intel`):

```bash
# 1. Clone your repository
git clone https://github.com/rishysingh/agentic-market-intelligence.git
cd agentic-market-intelligence

# 2. Authenticate standard gcloud CLI to your personal Google account
gcloud auth login
gcloud auth application-default login

# 3. Run the automated personal GCP bootstrap script
chmod +x scripts/bootstrap_personal_gcp.sh
./scripts/bootstrap_personal_gcp.sh my-personal-market-intel us-central1
```

 Or, to run **100% locally for $0.00** without deploying to the cloud at all:
```bash
# Terminal 1: Start Backend API (port 8080)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn services.api.main:app --host 127.0.0.1 --port 8080

# Terminal 2: Start Frontend Terminal (port 3000)
cd apps/frontend
npm install
BACKEND_INTERNAL_URL=http://127.0.0.1:8080 npm run dev
```

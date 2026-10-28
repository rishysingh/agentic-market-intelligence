# Cloud Run Deployment, CI/CD, Monitoring & Operations Runbook

## 1. Environment Variables Reference

| Variable | Tier | Default / Example | Description |
|---|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | Tier 2 / Tier 3 | `qwiklabs-gcp-03-c81d344a3430` | Active GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Tier 2 / Tier 3 | `us-central1` | Vertex AI & Cloud Run region |
| `BQ_DATASET_ID` | Tier 2 / Tier 3 | `market_intelligence` | Target BigQuery dataset |
| `GEMINI_PRO_MODEL` | Tier 2 | `gemini-2.5-pro` | Model for Root Agent, Critic, and deep synthesis |
| `GEMINI_FLASH_MODEL` | Tier 2 | `gemini-2.5-flash` | Model for low-latency specialist agents & search grounding |
| `AMI_ADMIN_TOKEN` | Tier 2 | *(Secret Manager: `ami-api-auth-token`)* | Required token for `POST /api/v1/pipeline/refresh` |
| `BACKEND_INTERNAL_URL` | Tier 1 | `https://ami-backend-...run.app` | Backend Cloud Run URL used by Next.js server-side API proxy |

---

## 2. Cloud Run Build & Deployment Commands

### Build & Deploy Tier 2 Backend (`ami-backend`)
```bash
gcloud builds submit \
  --project=qwiklabs-gcp-03-c81d344a3430 \
  --region=us-central1 \
  --tag=us-central1-docker.pkg.dev/qwiklabs-gcp-03-c81d344a3430/ami-repo/ami-backend:latest \
  .

gcloud run deploy ami-backend \
  --project=qwiklabs-gcp-03-c81d344a3430 \
  --region=us-central1 \
  --image=us-central1-docker.pkg.dev/qwiklabs-gcp-03-c81d344a3430/ami-repo/ami-backend:latest \
  --service-account=ami-backend-sa@qwiklabs-gcp-03-c81d344a3430.iam.gserviceaccount.com \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=qwiklabs-gcp-03-c81d344a3430,GOOGLE_CLOUD_LOCATION=us-central1,BQ_DATASET_ID=market_intelligence" \
  --memory=2Gi --cpu=2 --min-instances=0 --max-instances=4 \
  --allow-unauthenticated
```

### Build & Deploy Tier 1 Frontend (`ami-frontend`)
```bash
gcloud builds submit apps/frontend \
  --project=qwiklabs-gcp-03-c81d344a3430 \
  --region=us-central1 \
  --tag=us-central1-docker.pkg.dev/qwiklabs-gcp-03-c81d344a3430/ami-repo/ami-frontend:latest

gcloud run deploy ami-frontend \
  --project=qwiklabs-gcp-03-c81d344a3430 \
  --region=us-central1 \
  --image=us-central1-docker.pkg.dev/qwiklabs-gcp-03-c81d344a3430/ami-repo/ami-frontend:latest \
  --service-account=ami-frontend-sa@qwiklabs-gcp-03-c81d344a3430.iam.gserviceaccount.com \
  --set-env-vars="BACKEND_INTERNAL_URL=${BACKEND_URL},NEXT_PUBLIC_API_BASE_URL=${BACKEND_URL}" \
  --memory=1Gi --cpu=1 --min-instances=0 --max-instances=3 \
  --port=8080 \
  --allow-unauthenticated
```

### Deploy & Execute Tier 3 Scheduled Ingestion Job (`ami-ingestion-job`)
```bash
gcloud run jobs deploy ami-ingestion-job \
  --project=qwiklabs-gcp-03-c81d344a3430 \
  --region=us-central1 \
  --image=us-central1-docker.pkg.dev/qwiklabs-gcp-03-c81d344a3430/ami-repo/ami-backend:latest \
  --service-account=ami-ingestion-sa@qwiklabs-gcp-03-c81d344a3430.iam.gserviceaccount.com \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=qwiklabs-gcp-03-c81d344a3430,GOOGLE_CLOUD_LOCATION=us-central1,BQ_DATASET_ID=market_intelligence" \
  --command="python3" \
  --args="data/ingestion/pipeline.py,--mode,full" \
  --memory=2Gi --cpu=2 --max-retries=1 --task-timeout=600s
```

---

## 3. Incident Response & Degraded Mode Runbook

- **Stale Market Data (`freshness_status == STALE`)**:
  1. Check `ami-ingestion-job` logs in Cloud Logging: `gcloud run jobs executions list --job=ami-ingestion-job --region=us-central1`.
  2. Manually trigger a refresh: `gcloud run jobs execute ami-ingestion-job --region=us-central1`.
  3. While stale, `data_governance_agent` and `critic_agent` automatically cap recommendation conviction at `LOW` or `ABSTAIN`.
- **Vertex AI Quota or Grounding Timeout**:
  1. Orchestrator enforces per-agent timeouts (`15s`) and falls back to deterministic point-in-time SEC EDGAR and BigQuery evidence without crashing the request.

---

## 4. Cost Management & Teardown Instructions

All Cloud Run services are configured with `min-instances=0` (scale-to-zero when idle) and strict `max-instances` caps. To tear down only the `agentic-market-intelligence` resources without affecting unrelated workloads in the project:
```bash
gcloud run services delete ami-frontend --region=us-central1 --quiet
gcloud run services delete ami-backend --region=us-central1 --quiet
gcloud run jobs delete ami-ingestion-job --region=us-central1 --quiet
gcloud scheduler jobs delete ami-daily-market-refresh --location=us-central1 --quiet
gcloud pubsub topics delete ami-refresh-triggers --quiet
bq rm -r -f -d qwiklabs-gcp-03-c81d344a3430:market_intelligence
```

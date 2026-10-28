#!/usr/bin/env bash
# ==============================================================================
# Portable Personal GCP Bootstrap & Deployment Script (Zero Antigravity Required)
# Usage:
#   chmod +x scripts/bootstrap_personal_gcp.sh
#   ./scripts/bootstrap_personal_gcp.sh <YOUR_PERSONAL_GCP_PROJECT_ID> [REGION]
# ==============================================================================
set -euo pipefail

PROJECT_ID="${1:-}"
REGION="${2:-us-central1}"
BQ_DATASET="market_intelligence"
GAR_REPO="ami-repo"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: $0 <YOUR_PERSONAL_GCP_PROJECT_ID> [REGION]"
  exit 1
fi

echo "=== 1. Setting active GCP project to: ${PROJECT_ID} (${REGION}) ==="
gcloud config set project "${PROJECT_ID}"

echo "=== 2. Enabling required Google Cloud APIs ==="
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  pubsub.googleapis.com \
  iam.googleapis.com

echo "=== 3. Creating Least-Privilege Service Accounts ==="
for SA in ami-frontend-sa ami-backend-sa ami-ingestion-sa ami-scheduler-sa; do
  gcloud iam service-accounts create "${SA}" \
    --display-name="${SA}" \
    --project="${PROJECT_ID}" 2>/dev/null || true
done

for ROLE in roles/aiplatform.user roles/bigquery.jobUser roles/bigquery.dataEditor roles/logging.logWriter roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:ami-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="${ROLE}" --quiet >/dev/null
done

for ROLE in roles/bigquery.jobUser roles/bigquery.dataEditor roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:ami-ingestion-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="${ROLE}" --quiet >/dev/null
done

echo "=== 4. Creating Artifact Registry, Pub/Sub Topic & Secret Manager Token ==="
gcloud artifacts repositories create "${GAR_REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --project="${PROJECT_ID}" 2>/dev/null || true

gcloud pubsub topics create ami-refresh-triggers \
  --project="${PROJECT_ID}" 2>/dev/null || true

if ! gcloud secrets describe ami-api-auth-token --project="${PROJECT_ID}" >/dev/null 2>&1; then
  openssl rand -hex 24 | gcloud secrets create ami-api-auth-token \
    --data-file=- \
    --replication-policy=automatic \
    --project="${PROJECT_ID}"
fi

echo "=== 5. Creating BigQuery Dataset & Running Initial Data/Model Pipeline ==="
bq --location="${REGION}" mk --dataset "${PROJECT_ID}:${BQ_DATASET}" 2>/dev/null || true

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -r requirements.txt
GOOGLE_CLOUD_PROJECT="${PROJECT_ID}" GOOGLE_CLOUD_LOCATION="${REGION}" BQ_DATASET_ID="${BQ_DATASET}" \
  PYTHONPATH=. python3 data/ingestion/pipeline.py --mode full

echo "=== 6. Building & Deploying Cost-Optimized Cloud Run Backend (min-instances=0) ==="
BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${GAR_REPO}/ami-backend:latest"
gcloud builds submit . \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --tag="${BACKEND_IMAGE}"

gcloud run deploy ami-backend \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${BACKEND_IMAGE}" \
  --service-account="ami-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},BQ_DATASET_ID=${BQ_DATASET},ENVIRONMENT=prod" \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=2 \
  --concurrency=40 \
  --cpu-throttling \
  --port=8080 \
  --allow-unauthenticated

BACKEND_URL="$(gcloud run services describe ami-backend --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"

echo "=== 7. Building & Deploying Cost-Optimized Cloud Run Frontend (min-instances=0) ==="
FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${GAR_REPO}/ami-frontend:latest"
gcloud builds submit apps/frontend \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --tag="${FRONTEND_IMAGE}"

gcloud run deploy ami-frontend \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${FRONTEND_IMAGE}" \
  --service-account="ami-frontend-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="BACKEND_INTERNAL_URL=${BACKEND_URL},NEXT_PUBLIC_API_BASE_URL=${BACKEND_URL},NEXT_PUBLIC_APP_ENV=prod" \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=2 \
  --cpu-throttling \
  --port=8080 \
  --allow-unauthenticated

FRONTEND_URL="$(gcloud run services describe ami-frontend --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"

echo "=============================================================================="
echo "Deployment Complete!"
echo "Frontend Terminal URL : ${FRONTEND_URL}"
echo "Backend API URL       : ${BACKEND_URL}"
echo "=============================================================================="

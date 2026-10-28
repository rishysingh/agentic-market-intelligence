#!/usr/bin/env python3
"""End-to-End Cloud Run Deployment, Live Verification & GitHub Sync Script."""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import certifi

REPO_ROOT = Path("/Users/rishysingh/.gemini/antigravity/scratch/agentic-market-intelligence")
GCLOUD_BIN = "/Users/rishysingh/google-cloud-sdk/bin/gcloud"
ADC_FILE = "/Users/rishysingh/.config/gcloud/application_default_credentials.json"
PROJECT_ID = "qwiklabs-gcp-03-c81d344a3430"
REGION = "us-central1"
GAR_REPO = f"{REGION}-docker.pkg.dev/{PROJECT_ID}/ami-repo"
BACKEND_IMAGE = f"{GAR_REPO}/ami-backend:latest"
FRONTEND_IMAGE = f"{GAR_REPO}/ami-frontend:latest"


def run_cmd(args: list[str], cwd: Path = REPO_ROOT, check: bool = True) -> subprocess.CompletedProcess:
    cmd_args = list(args)
    if cmd_args and cmd_args[0] == GCLOUD_BIN:
        cmd_args.append(f"--credential-file-override={ADC_FILE}")
    env = os.environ.copy()
    env["CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"] = ADC_FILE
    env["CLOUDSDK_CORE_PROJECT"] = PROJECT_ID
    env["GOOGLE_APPLICATION_CREDENTIALS"] = ADC_FILE
    print(f"\n>>> Executing: {' '.join(cmd_args)}", flush=True)
    result = subprocess.run(cmd_args, cwd=str(cwd), env=env, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, flush=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr, flush=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(args)}")
    return result


def http_get_json(url: str) -> dict:
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={"User-Agent": "AMI-Deployment-Verifier/1.0"})
    with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_status(url: str) -> int:
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={"User-Agent": "AMI-Deployment-Verifier/1.0"})
    with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
        return resp.status


def main() -> None:
    verify_only = "--verify-and-push" in sys.argv
    if not verify_only:
        # 1. Build Backend Image via Cloud Build
        print("=== Step 1: Building Backend Container Image on Cloud Build ===", flush=True)
        run_cmd([
            GCLOUD_BIN, "builds", "submit", str(REPO_ROOT),
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
            f"--config={REPO_ROOT / 'cloudbuild.backend.yaml'}",
            "--quiet",
        ])

        # 2. Deploy Tier 2 Backend Cloud Run Service
        print("=== Step 2: Deploying Tier 2 Backend (ami-backend) to Cloud Run ===", flush=True)
        run_cmd([
            GCLOUD_BIN, "run", "deploy", "ami-backend",
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
            f"--image={BACKEND_IMAGE}",
            f"--service-account=ami-backend-sa@{PROJECT_ID}.iam.gserviceaccount.com",
            f"--set-env-vars=GOOGLE_CLOUD_PROJECT={PROJECT_ID},GOOGLE_CLOUD_LOCATION={REGION},BQ_DATASET_ID=market_intelligence,ENVIRONMENT=prod",
            "--memory=2Gi",
            "--cpu=2",
            "--min-instances=0",
            "--max-instances=4",
            "--timeout=120s",
            "--port=8080",
            "--allow-unauthenticated",
            "--quiet",
        ])

    backend_url_res = run_cmd([
        GCLOUD_BIN, "run", "services", "describe", "ami-backend",
        f"--project={PROJECT_ID}",
        f"--region={REGION}",
        "--format=value(status.url)",
    ])
    backend_url = backend_url_res.stdout.strip()
    print(f"Verified Backend URL: {backend_url}", flush=True)

    if not verify_only:
        # 3. Deploy Tier 3 Scheduled Cloud Run Job (ami-ingestion-job) & Cloud Scheduler
        print("=== Step 3: Deploying Tier 3 Ingestion Cloud Run Job (ami-ingestion-job) ===", flush=True)
        run_cmd([
            GCLOUD_BIN, "run", "jobs", "deploy", "ami-ingestion-job",
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
            f"--image={BACKEND_IMAGE}",
            f"--service-account=ami-ingestion-sa@{PROJECT_ID}.iam.gserviceaccount.com",
            f"--set-env-vars=GOOGLE_CLOUD_PROJECT={PROJECT_ID},GOOGLE_CLOUD_LOCATION={REGION},BQ_DATASET_ID=market_intelligence",
            "--command=python3",
            "--args=data/ingestion/pipeline.py,--mode,full",
            "--memory=2Gi",
            "--cpu=2",
            "--max-retries=1",
            "--task-timeout=600s",
            "--quiet",
        ])

        print("=== Step 4: Configuring Cloud Scheduler (ami-daily-market-refresh) ===", flush=True)
        sched_check = run_cmd([
            GCLOUD_BIN, "scheduler", "jobs", "describe", "ami-daily-market-refresh",
            f"--project={PROJECT_ID}",
            f"--location={REGION}",
        ], check=False)
        if sched_check.returncode != 0:
            run_cmd([
                GCLOUD_BIN, "scheduler", "jobs", "create", "pubsub", "ami-daily-market-refresh",
                f"--project={PROJECT_ID}",
                f"--location={REGION}",
                "--schedule=0 22 * * 1-5",
                "--time-zone=America/New_York",
                "--topic=ami-refresh-triggers",
                '--message-body={"trigger":"scheduled_post_close_refresh","mode":"full"}',
                "--quiet",
            ], check=False)

        # 4. Build Frontend Image via Cloud Build
        print("=== Step 5: Building Tier 1 Frontend Container Image on Cloud Build ===", flush=True)
        run_cmd([
            GCLOUD_BIN, "builds", "submit", str(REPO_ROOT / "apps" / "frontend"),
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
            f"--tag={FRONTEND_IMAGE}",
            "--quiet",
        ])

        # 5. Deploy Tier 1 Frontend Cloud Run Service
        print("=== Step 6: Deploying Tier 1 Frontend (ami-frontend) to Cloud Run ===", flush=True)
        run_cmd([
            GCLOUD_BIN, "run", "deploy", "ami-frontend",
            f"--project={PROJECT_ID}",
            f"--region={REGION}",
            f"--image={FRONTEND_IMAGE}",
            f"--service-account=ami-frontend-sa@{PROJECT_ID}.iam.gserviceaccount.com",
            f"--set-env-vars=BACKEND_INTERNAL_URL={backend_url},NEXT_PUBLIC_API_BASE_URL={backend_url},NEXT_PUBLIC_APP_ENV=prod",
            "--memory=1Gi",
            "--cpu=1",
            "--min-instances=0",
            "--max-instances=3",
            "--port=8080",
            "--allow-unauthenticated",
            "--quiet",
        ])

    frontend_url_res = run_cmd([
        GCLOUD_BIN, "run", "services", "describe", "ami-frontend",
        f"--project={PROJECT_ID}",
        f"--region={REGION}",
        "--format=value(status.url)",
    ])
    frontend_url = frontend_url_res.stdout.strip()
    print(f"Verified Frontend URL: {frontend_url}", flush=True)

    # 6. Verify Live Endpoints
    print("=== Step 7: Verifying Live Deployed Cloud Run Endpoints ===", flush=True)
    health_data = http_get_json(f"{backend_url}/api/v1/health")
    overview_data = http_get_json(f"{backend_url}/api/v1/market/overview")
    fe_status = http_get_status(frontend_url)
    fe_proxy_health = http_get_json(f"{frontend_url}/api/proxy/health")

    manifest = {
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "gcp_project_id": PROJECT_ID,
        "region": REGION,
        "backend_service": "ami-backend",
        "backend_url": backend_url,
        "frontend_service": "ami-frontend",
        "frontend_url": frontend_url,
        "ingestion_job": "ami-ingestion-job",
        "scheduler_job": "ami-daily-market-refresh",
        "verification": {
            "backend_health_status": health_data.get("status"),
            "market_regime": overview_data.get("regime", {}).get("regime_label"),
            "frontend_http_status": fe_status,
            "frontend_proxy_health_status": fe_proxy_health.get("status"),
        },
    }
    manifest_path = REPO_ROOT / "data" / "cache" / "deployment_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)

    # 8. Commit and Push to GitHub
    print("=== Step 8: Committing and Pushing Repository to GitHub ===", flush=True)
    run_cmd(["git", "add", "-A"], cwd=REPO_ROOT)
    status_res = run_cmd(["git", "status", "--porcelain"], cwd=REPO_ROOT)
    if status_res.stdout.strip():
        run_cmd([
            "git", "commit", "-m",
            "feat: complete 3-tier Agentic Market Intelligence platform, 11 specialists, MCP servers, tests, and Cloud Run deployment"
        ], cwd=REPO_ROOT)
    run_cmd(["git", "push", "-u", "origin", "main"], cwd=REPO_ROOT)
    print("=== Deployment, Verification & GitHub Sync Complete ===", flush=True)


if __name__ == "__main__":
    main()

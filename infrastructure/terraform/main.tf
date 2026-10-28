terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ==============================================================================
# 1. Least-Privilege Service Accounts (Isolated per Tier)
# ==============================================================================

resource "google_service_account" "frontend_sa" {
  account_id   = "ami-frontend-sa"
  display_name = "AMI Tier 1 Frontend Cloud Run Service Account"
  description  = "Least-privilege identity for Next.js frontend; only invokes backend API."
}

resource "google_service_account" "backend_sa" {
  account_id   = "ami-backend-sa"
  display_name = "AMI Tier 2 Backend API & Agent Orchestrator Service Account"
  description  = "Identity for FastAPI + Google ADK agents; accesses market_intelligence BQ and Vertex AI."
}

resource "google_service_account" "ingestion_sa" {
  account_id   = "ami-ingestion-sa"
  display_name = "AMI Tier 3 Data Ingestion & Quant Pipeline Service Account"
  description  = "Identity for scheduled Cloud Run ingestion and feature engineering jobs."
}

resource "google_service_account" "scheduler_sa" {
  account_id   = "ami-scheduler-sa"
  display_name = "AMI Cloud Scheduler Trigger Service Account"
  description  = "Identity for Cloud Scheduler to trigger ingestion jobs and Pub/Sub refreshes."
}

# ==============================================================================
# 2. BigQuery Analytical Data Warehouse (market_intelligence)
# ==============================================================================

resource "google_bigquery_dataset" "market_intelligence" {
  dataset_id                  = var.bq_dataset_id
  friendly_name               = "Agentic Market Intelligence Warehouse"
  description                 = "Normalized Raw, Staging, Point-in-Time Core, Feature, Model, Prediction, and Backtest tables."
  location                    = var.region
  delete_contents_on_destroy  = false
  default_table_expiration_ms = null

  labels = {
    application = "agentic-market-intelligence"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Dataset-level IAM (Strictly scoped to market_intelligence dataset only)
resource "google_bigquery_dataset_iam_member" "backend_bq_viewer" {
  dataset_id = google_bigquery_dataset.market_intelligence.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_bigquery_dataset_iam_member" "ingestion_bq_editor" {
  dataset_id = google_bigquery_dataset.market_intelligence.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingestion_sa.email}"
}

# Project-level minimal roles for BigQuery job execution and Vertex AI inference
resource "google_project_iam_member" "backend_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "ingestion_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ingestion_sa.email}"
}

# ==============================================================================
# 3. Artifact Registry, Pub/Sub & Secret Manager
# ==============================================================================

resource "google_artifact_registry_repository" "ami_repo" {
  location      = var.region
  repository_id = "ami-repo"
  description   = "Container images for Agentic Market Intelligence frontend, backend, and jobs"
  format        = "DOCKER"

  vulnerability_scanning_config {
    enablement_config = "INHERITED"
  }
}

resource "google_pubsub_topic" "refresh_triggers" {
  name = "ami-refresh-triggers"
  labels = {
    application = "agentic-market-intelligence"
    environment = var.environment
  }
}

resource "google_secret_manager_secret" "api_auth_token" {
  secret_id = "ami-api-auth-token"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "backend_secret_accessor" {
  secret_id = google_secret_manager_secret.api_auth_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.backend_sa.email}"
}

# ==============================================================================
# 4. Tier 2: Cloud Run Backend API & Agent Orchestrator Service
# ==============================================================================

resource "google_cloud_run_v2_service" "ami_backend" {
  name     = "ami-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account                  = google_service_account.backend_sa.email
    timeout                          = "120s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = 0
      max_instance_count = 4
    }

    containers {
      image = var.backend_image
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "2000m"
          memory = "2Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "BQ_DATASET_ID"
        value = var.bq_dataset_id
      }
      env {
        name  = "ADK_ROOT_MODEL"
        value = var.adk_root_model
      }
      env {
        name  = "ADK_SPECIALIST_MODEL"
        value = var.adk_specialist_model
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
    }
  }
}

# ==============================================================================
# 5. Tier 1: Cloud Run Frontend Presentation Service
# ==============================================================================

resource "google_cloud_run_v2_service" "ami_frontend" {
  name     = "ami-frontend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account                  = google_service_account.frontend_sa.email
    timeout                          = "60s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = var.frontend_image
      ports {
        container_port = 3000
      }
      resources {
        limits = {
          cpu    = "1000m"
          memory = "1Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      env {
        name  = "NEXT_PUBLIC_API_BASE_URL"
        value = google_cloud_run_v2_service.ami_backend.uri
      }
      env {
        name  = "NEXT_PUBLIC_APP_ENV"
        value = var.environment
      }
    }
  }
}

# ==============================================================================
# 6. Tier 3: Cloud Run Job (Scheduled Ingestion & Feature Pipeline) + Scheduler
# ==============================================================================

resource "google_cloud_run_v2_job" "ami_ingestion_job" {
  name     = "ami-ingestion-job"
  location = var.region

  template {
    template {
      service_account = google_service_account.ingestion_sa.email
      timeout         = "600s"
      max_retries     = 2

      containers {
        image   = var.backend_image
        command = ["python3", "-m", "data.ingestion.pipeline", "--mode", "incremental"]
        resources {
          limits = {
            cpu    = "2000m"
            memory = "2Gi"
          }
        }
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "BQ_DATASET_ID"
          value = var.bq_dataset_id
        }
      }
    }
  }
}

resource "google_cloud_scheduler_job" "daily_market_refresh" {
  name             = "ami-daily-market-refresh"
  description      = "Triggers daily post-market EOD OHLCV, SEC EDGAR, and feature refresh at 21:30 UTC Mon-Fri"
  schedule         = "30 21 * * 1-5"
  time_zone        = "Etc/UTC"
  attempt_deadline = "320s"
  region           = var.region

  pubsub_target {
    topic_name = google_pubsub_topic.refresh_triggers.id
    data       = base64encode("{\"mode\": \"incremental\", \"source\": \"cloud_scheduler\"}")
  }
}

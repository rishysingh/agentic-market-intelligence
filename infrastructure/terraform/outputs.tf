output "bigquery_dataset_id" {
  description = "BigQuery analytical dataset ID"
  value       = google_bigquery_dataset.market_intelligence.dataset_id
}

output "backend_service_url" {
  description = "Cloud Run URL for Tier 2 Backend API & Agent Orchestrator"
  value       = google_cloud_run_v2_service.ami_backend.uri
}

output "frontend_service_url" {
  description = "Cloud Run URL for Tier 1 Next.js Financial Terminal"
  value       = google_cloud_run_v2_service.ami_frontend.uri
}

output "ingestion_job_name" {
  description = "Cloud Run Job name for Tier 3 Market Data Ingestion"
  value       = google_cloud_run_v2_job.ami_ingestion_job.name
}

output "artifact_registry_repo" {
  description = "Artifact Registry Docker repository ID"
  value       = google_artifact_registry_repository.ami_repo.repository_id
}

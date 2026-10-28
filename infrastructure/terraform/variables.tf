variable "project_id" {
  description = "Existing Google Cloud Project ID (do not create a new project)."
  type        = string
  default     = "qwiklabs-gcp-03-c81d344a3430"
}

variable "region" {
  description = "Primary Google Cloud region for Cloud Run, Artifact Registry, and BigQuery."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "bq_dataset_id" {
  description = "BigQuery analytical warehouse dataset ID."
  type        = string
  default     = "market_intelligence"
}

variable "github_owner" {
  description = "GitHub account or organization owner."
  type        = string
  default     = "rishysingh"
}

variable "github_repo" {
  description = "GitHub repository name for Workload Identity Federation."
  type        = string
  default     = "agentic-market-intelligence"
}

variable "frontend_image" {
  description = "Container image URI for Tier 1 Frontend Cloud Run service."
  type        = string
  default     = "us-central1-docker.pkg.dev/qwiklabs-gcp-03-c81d344a3430/ami-repo/ami-frontend:latest"
}

variable "backend_image" {
  description = "Container image URI for Tier 2 Backend API & Agent Orchestrator Cloud Run service."
  type        = string
  default     = "us-central1-docker.pkg.dev/qwiklabs-gcp-03-c81d344a3430/ami-repo/ami-backend:latest"
}

variable "adk_root_model" {
  description = "Vertex AI Gemini model for Root Agent and Independent Critic."
  type        = string
  default     = "gemini-2.5-pro"
}

variable "adk_specialist_model" {
  description = "Vertex AI Gemini model for specialized research sub-agents."
  type        = string
  default     = "gemini-2.5-flash"
}

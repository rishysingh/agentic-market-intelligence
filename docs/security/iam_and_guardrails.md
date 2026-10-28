# IAM Least-Privilege Model, MCP Security & Guardrails

## 1. Dedicated Google Cloud Service Accounts

Four dedicated workload identities isolate privileges across tiers in project `qwiklabs-gcp-03-c81d344a3430`:

| Service Account | Assigned Workload | Roles Granted |
|---|---|---|
| `ami-frontend-sa@qwiklabs-gcp-03-c81d344a3430.iam.gserviceaccount.com` | Cloud Run `ami-frontend` | `roles/logging.logWriter`, `roles/run.invoker` |
| `ami-backend-sa@qwiklabs-gcp-03-c81d344a3430.iam.gserviceaccount.com` | Cloud Run `ami-backend` | `roles/aiplatform.user`, `roles/bigquery.jobUser`, dataset-level `READER` on `market_intelligence`, dataset-level `WRITER` on audit tables, `roles/secretmanager.secretAccessor` (on `ami-api-auth-token`) |
| `ami-ingestion-sa@qwiklabs-gcp-03-c81d344a3430.iam.gserviceaccount.com` | Cloud Run Job `ami-ingestion-job` | `roles/bigquery.jobUser`, dataset-level `WRITER` on `market_intelligence`, `roles/logging.logWriter` |
| `ami-scheduler-sa@qwiklabs-gcp-03-c81d344a3430.iam.gserviceaccount.com` | Cloud Scheduler `ami-daily-market-refresh` | `roles/pubsub.publisher`, `roles/run.invoker` |

---

## 2. Controlled Internal MCP Tool Security (`mcp/security.py`)

Agents never access raw database connections or external HTTP clients directly. Every tool call passes through `mcp/security.py`:

1. **Per-Agent Tool Allowlists (`AGENT_TOOL_ALLOWLIST`)**:
   - Each of the 11 specialized agents is restricted to an explicit set of MCP tools. For example, `news_catalyst_agent` can invoke `search_grounded_catalysts` and `query_sec_filings`, but is blocked (`MCPAccessDeniedError`) from invoking `query_predictions` or `query_backtest_runs`.
2. **Read-Only SQL Validation (`validate_readonly_sql`)**:
   - Rejects any query not starting with `SELECT` or `WITH`.
   - Rejects multi-statement queries (`;`), SQL comments (`--`, `/*`), and DDL/DML keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `MERGE`, `GRANT`, `CREATE`, `EXECUTE`).
   - Enforces BigQuery `maximum_bytes_billed = 100_000_000` (100 MB) and auto-appends `LIMIT` caps.
3. **External Content Prompt-Injection Sanitization (`sanitize_external_text`)**:
   - All news headlines, SEC filing excerpts, and web snippets are scrubbed of prompt-injection patterns (`ignore previous instructions`, `system prompt:`, `<script>`, `override risk controls`, `guaranteed return`) before entering any agent context window.
4. **Mutation Endpoint Protection**:
   - `POST /api/v1/pipeline/refresh` requires a valid `X-AMI-Admin-Token` header verified in constant time (`hmac.compare_digest`) against the Secret Manager secret `ami-api-auth-token`.

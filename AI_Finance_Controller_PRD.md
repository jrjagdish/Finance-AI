# Product Requirements Document: AI Finance Controller

**Version:** 1.0
**Owner:** Jagdish
**Status:** Draft for build

---

## 1. Overview

**Goal:** Reconcile multi-source financial data (internal ledger, bank statements, payment gateway exports, master data), maximize the automatic match rate using deterministic rules, and use an LLM (Groq-hosted model) to resolve ambiguous/unmatched records into either confident AI-suggested matches or clearly explained exceptions for human review.

**Problem it solves:** Finance teams at small/mid SaaS and e-commerce businesses manually reconcile payments across ledgers, bank statements, and payment gateways (e.g., Razorpay). Narrations are messy, payments get split/aggregated, gateway fees get deducted, and matching by hand is slow and error-prone. This system automates the bulk of matching and explains every remaining exception in plain language.

**Primary users:**
- Finance/ops analyst - reviews exceptions, approves/rejects AI suggestions
- Founder/finance lead - views dashboard, reconciliation summary, exports reports

**Success metrics:**
- Auto-match rate (rule-based, confidence = 1.0)
- % of remaining unmatched records the AI resolves to a suggested match with acceptable confidence
- Time-to-reconcile per batch
- Human review turnaround time
- Reduction in "unknown counterparty" / unexplained exceptions over time

---

## 2. Tech Stack

| Layer | Choice |
|---|---|
| Backend API | FastAPI (Python) |
| Database | **PostgreSQL** |
| Cache / broker | Redis |
| Async jobs / scheduling | Celery (+ Redis as broker), Cron/Airflow-style scheduled ingestion |
| Object storage | S3 / MinIO (raw file store) |
| LLM provider | **Groq** (LLM API - fast inference for exception resolution, narration understanding, fuzzy/semantic matching, reasoning/explanations) |
| Orchestration for LLM calls | LangChain |
| Containerization | Docker / docker-compose |
| Deployment | Render / AWS / GCP |
| Auth | JWT, tenant API keys (multi-tenant ready) |

---

## 3. Architecture (per diagram) - System Flow

```
[Data Sources] -> [1. Ingestion Layer] -> [2. Normalization] -> [3. Deterministic Matching Engine]
                                                                     |
                                          +----------------------------+----------------------------+
                                     Matched Records                                    Unmatched / Partial / Ambiguous
                                          |                                                        |
                                   [Matched Output]                                    [AI Exception Resolver Agent (Groq LLM)]
                                          |                                                        |
                                          |                                              +---------+---------+
                                          |                                     High-confidence            Low/Medium confidence
                                          |                                     (auto-resolve)              or unresolved
                                          |                                              |                    |
                                          v                                              v                    v
                                  [Human Review Workbench] <---------------- [Exceptions Output] <-----------+
                                          |                                              |
                                          +-------------------> [Final Dashboard / Report] <-------------------+
                                                                             |
                                                                   [Analyze & Improve loop - feeds back into matching rules]
```

### 3.1 Data Sources
- Internal Ledger (CSV/API): invoices, orders, payments, fees, refunds
- Bank Statement (CSV): settlements, credits, debits, charges, narrations
- Payment Gateway / Razorpay Exports (API): payouts, fees, refunds, disputes
- Master Data: customers, vendors, products, tax rules, fee structures
- Synthetic Data Generator: creates 50-500 record test datasets with controlled edge cases

### 3.2 Ingestion Layer
- File upload (CSV) or API ingestion (Razorpay, bank feed)
- Scheduled ingestion (Cron / Celery beat, Airflow-style)
- Raw data lands untouched in a Raw Data Store (S3/MinIO + a `raw_records` Postgres table for lightweight metadata)

### 3.3 Data Normalization (Python/Pandas, run as a Celery task)
- Standardize dates (formats, timezones)
- Normalize amounts (decimals, currency)
- Clean narrations (remove noise/boilerplate)
- Entity resolution (map names/aliases -> canonical customer/vendor IDs)
- Deduplication (exact duplicate detection)

### 3.4 Deterministic Matching Engine (rule-based, runs before any LLM call)
Rules applied in priority order:
1. Exact match (Txn ID + Amount)
2. Reference match (Invoice/Order/Ref number)
3. Amount tolerance match (+/- configurable tolerance)
4. Date window match (within N days)
5. One-to-one / one-to-many aggregation rules (handles split payments and aggregated deposits)

Every match gets a `match_type` and `confidence_score = 1.0` if resolved deterministically.

### 3.5 AI Exception Resolver Agent (LLM via Groq + LangChain)
Triggered only on records the deterministic engine could not confidently resolve. Responsibilities:
- Understand messy bank narrations vs customer/vendor names (narration understanding)
- Detect split payments / aggregated deposits
- Identify gateway fees, taxes, chargebacks, refunds deducted from settlement amounts
- Fuzzy/semantic matching on names, references, descriptions despite typos/variations
- Suggest a match candidate + a confidence score (0-1)
- Produce a `reason_code` + human-readable explanation of why it matched or remains unresolved

Model: Groq-hosted LLM (e.g., Llama 3.x / compatible model available on Groq API), called through LangChain for prompt templating, structured output parsing, and tool-calling (e.g., "look up candidate ledger records" as a retrieval tool before the LLM commits to a suggestion).

### 3.6 Exceptions Output
For every unresolved/ambiguous record, store:
- Unresolved exception record
- AI-suggested match (if any) + confidence tier (low/medium/high)
- Reason code (e.g., `AMT_MISMATCH`, `FEE_DEDUCTED`, `MISSING_REFERENCE`, `SPLIT_PAYMENT`, `DUPLICATE`, `UNKNOWN_COUNTERPARTY`)
- LLM explanation text
- `needs_human_review` boolean flag

### 3.7 Human Review Workbench
- Review AI-suggested matches
- Approve / Reject / Edit the match
- Add comments & tags
- Create new matching rules from resolved patterns (feeds back into the deterministic engine - "Feedback (Improve Rules)" loop in the diagram)

### 3.8 Final Dashboard / Report
- Total records, auto-matched count, match rate %, AI-suggested matches count, unresolved exceptions count, needs-review count
- Reports: Reconciliation Summary, Exception Report, Match Audit Trail
- Export: Excel / CSV / PDF

### 3.9 Analyze & Improve (feedback loop)
- Match rate over time
- Exception trend analysis
- Top reason codes
- Performance by source
- Model/rule effectiveness
- Feeds back into ingestion rules, matching thresholds, and LLM prompts (continuous improvement loop shown in diagram)

---

## 4. Data Model (PostgreSQL - core tables)

```sql
-- Tenants (multi-tenant ready, optional for v1 but recommended)
tenants (id, name, api_key_hash, created_at)

-- Raw ingested files/records before normalization
raw_records (
  id, tenant_id, source_type ENUM('ledger','bank','gateway','master'),
  file_id, raw_payload JSONB, ingested_at, batch_id
)

-- Normalized transaction records (unified schema across sources)
normalized_records (
  id, tenant_id, source_type, source_record_id,
  txn_id, reference_no, entity_id (FK -> entities),
  amount NUMERIC, currency, txn_date, narration_raw, narration_clean,
  fee_amount NUMERIC, tax_amount NUMERIC, status,
  batch_id, created_at
)

-- Resolved entities (customers/vendors), aliases for entity resolution
entities (id, tenant_id, canonical_name, type ENUM('customer','vendor'), metadata JSONB)
entity_aliases (id, entity_id, alias_text)

-- Match results
matches (
  id, tenant_id, ledger_record_id, bank_record_id, gateway_record_id,
  match_type ENUM('exact','reference','amount_tolerance','date_window','one_to_many','ai_suggested'),
  confidence_score NUMERIC, matched_by ENUM('rule','ai','human'),
  created_at
)

-- Exceptions
exceptions (
  id, tenant_id, record_id, ai_suggested_match_id NULLABLE,
  confidence_tier ENUM('low','medium','high'), reason_code, explanation TEXT,
  needs_human_review BOOLEAN, status ENUM('open','approved','rejected','edited','resolved'),
  reviewer_id, reviewer_comment, created_at, resolved_at
)

-- Matching rules (feedback loop artifacts)
matching_rules (id, tenant_id, rule_definition JSONB, created_from_exception_id, is_active, created_at)

-- Audit trail
match_audit_log (id, match_id/exception_id, action, actor ('system'|'ai'|user_id), payload JSONB, created_at)

-- Batches / jobs
ingestion_batches (id, tenant_id, source_type, status, total_records, started_at, completed_at)

-- LLM call log (for cost tracking + debugging Groq usage)
llm_calls (id, tenant_id, exception_id, model_name, prompt_tokens, completion_tokens, latency_ms, raw_response JSONB, created_at)
```

---

## 5. API Endpoints (FastAPI)

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register tenant, issue API key |
| POST | `/auth/login` | Login, issue JWT |
| POST | `/auth/refresh` | Refresh JWT |

### Ingestion
| Method | Path | Description |
|---|---|---|
| POST | `/ingest/upload` | Upload CSV file (ledger/bank/gateway); triggers async normalization job |
| POST | `/ingest/gateway/razorpay` | Trigger/receive Razorpay export ingestion (API pull or webhook) |
| GET | `/ingest/batches` | List ingestion batches with status |
| GET | `/ingest/batches/{batch_id}` | Batch detail: record counts, errors |
| POST | `/ingest/schedule` | Create/update a scheduled ingestion job (cron expression) |
| GET | `/ingest/schedule` | List scheduled ingestion jobs |

### Normalization
| Method | Path | Description |
|---|---|---|
| POST | `/normalize/run/{batch_id}` | Manually trigger normalization for a batch |
| GET | `/normalize/status/{batch_id}` | Check normalization job status |
| GET | `/records` | List normalized records (filterable by source/date/entity/status) |
| GET | `/records/{record_id}` | Get single normalized record |

### Entities / Master Data
| Method | Path | Description |
|---|---|---|
| GET | `/entities` | List customers/vendors |
| POST | `/entities` | Create entity |
| PUT | `/entities/{id}` | Update entity |
| POST | `/entities/{id}/aliases` | Add alias for entity resolution |
| GET | `/master-data/fee-rules` | List fee/tax structures |
| POST | `/master-data/fee-rules` | Create fee/tax rule |

### Matching Engine
| Method | Path | Description |
|---|---|---|
| POST | `/match/run/{batch_id}` | Run deterministic matching engine on a batch |
| GET | `/match/results` | List match results (filterable by match_type, confidence, date) |
| GET | `/match/results/{match_id}` | Get single match detail |
| POST | `/match/rules` | Create/update a deterministic matching rule (tolerance, date window, etc.) |
| GET | `/match/rules` | List active matching rules |

### AI Exception Resolver
| Method | Path | Description |
|---|---|---|
| POST | `/ai/resolve/{batch_id}` | Trigger AI resolver on unmatched/ambiguous records for a batch (async Celery task, calls Groq via LangChain) |
| GET | `/ai/resolve/status/{job_id}` | Check status of an AI resolution job |
| GET | `/ai/suggestions` | List AI-suggested matches (filterable by confidence tier) |
| GET | `/ai/suggestions/{id}` | Get AI suggestion detail incl. explanation and reason code |
| POST | `/ai/suggestions/{id}/feedback` | Log human feedback on an AI suggestion (used for prompt/rule improvement) |

### Exceptions
| Method | Path | Description |
|---|---|---|
| GET | `/exceptions` | List exceptions (filterable by reason_code, confidence_tier, status) |
| GET | `/exceptions/{id}` | Get exception detail with AI explanation |
| POST | `/exceptions/{id}/approve` | Approve AI-suggested match -> creates confirmed match |
| POST | `/exceptions/{id}/reject` | Reject AI-suggested match |
| POST | `/exceptions/{id}/edit` | Manually edit/override the match |
| POST | `/exceptions/{id}/comment` | Add reviewer comment/tag |
| POST | `/exceptions/{id}/create-rule` | Promote a resolved exception pattern into a new deterministic matching rule |

### Dashboard & Reports
| Method | Path | Description |
|---|---|---|
| GET | `/dashboard/summary` | Total records, auto-matched, match rate %, AI-suggested, unresolved, needs-review counts |
| GET | `/dashboard/trends` | Match rate over time, exception trend analysis |
| GET | `/dashboard/reason-codes` | Top reason codes breakdown |
| GET | `/dashboard/performance-by-source` | Match performance segmented by data source |
| GET | `/reports/reconciliation-summary` | Generate reconciliation summary report |
| GET | `/reports/exception-report` | Generate exception report |
| GET | `/reports/audit-trail` | Full match audit trail |
| GET | `/reports/export?format=csv|xlsx|pdf` | Export a report in requested format |

### Utility / Testing
| Method | Path | Description |
|---|---|---|
| POST | `/dev/synthetic-data` | Generate 50-500 record synthetic test dataset with controlled edge cases |
| GET | `/health` | Health check |
| GET | `/llm/usage` | Groq LLM usage/cost stats (from `llm_calls` log) |

---

## 6. Async Job / Celery Task Inventory
- `normalize_batch(batch_id)` - Pandas cleaning pipeline
- `run_matching_engine(batch_id)` - deterministic rule pass
- `resolve_exceptions_with_ai(batch_id)` - batches unresolved records to Groq LLM via LangChain, parses structured output (match candidate, confidence, reason_code, explanation)
- `scheduled_ingestion(source_config_id)` - cron-triggered pull from gateway/bank API
- `generate_report(report_type, params)` - async report generation for large exports
- `recompute_dashboard_metrics()` - periodic aggregation job

---

## 7. LLM Integration Details (Groq)
- **Provider:** Groq API (low-latency inference)
- **Orchestration:** LangChain for prompt templates, structured output (Pydantic-parsed JSON: `{match_candidate_id, confidence, reason_code, explanation}`), and optional retrieval step (fetch top-N candidate ledger records by entity/amount before prompting)
- **Prompt inputs per exception:** cleaned narration, transaction amount/date, list of candidate ledger/order records (narrowed by entity resolution + amount/date proximity), known fee/tax rules
- **Output contract:** strict JSON schema so responses map directly into the `exceptions` table (avoids free-text parsing errors)
- **Confidence thresholding:** e.g., >=0.85 = high (auto-suggest, still requires human approval by default in v1), 0.5-0.85 = medium, <0.5 = low/unresolved
- **Cost/latency tracking:** every call logged in `llm_calls` table for the `/llm/usage` endpoint and the "Analyze & Improve" dashboard

---

## 8. Non-Functional Requirements
- Multi-tenant isolation at the DB row level (tenant_id on all core tables) - optional to enable fully in v1, but schema should support it from day one
- Idempotent ingestion (avoid double-processing on re-upload/retry)
- All matching decisions must be auditable (`match_audit_log`)
- LLM calls must degrade gracefully (timeout/fallback -> mark as unresolved exception rather than fail the batch)
- Exportable reports (CSV/XLSX/PDF)

---

## 9. Build Milestones (suggested order)
1. **Foundation:** Postgres schema, FastAPI skeleton, auth, file upload endpoint, S3/MinIO wiring
2. **Normalization pipeline:** Pandas cleaning + entity resolution + Celery task
3. **Deterministic matching engine:** exact/reference/tolerance/date-window/one-to-many rules + matches table
4. **Dashboard v1:** summary counts, basic reports (based on rule-matching only)
5. **AI Exception Resolver:** Groq + LangChain integration, structured output, reason codes, confidence tiers
6. **Human Review Workbench:** approve/reject/edit endpoints + UI
7. **Feedback loop:** promote resolved exceptions into new matching rules
8. **Analytics & improvement dashboard:** trends, reason-code breakdown, performance by source, LLM usage/cost view
9. **Synthetic data generator + test suite:** edge cases (split payments, aggregated deposits, fee deductions, duplicates, unknown counterparties)
10. **Multi-tenancy hardening + deployment** (Docker, CI/CD, deploy to Render/AWS/GCP)

---

## Build Notes (this repo)

- Auth/JWT/tenant-key enforcement is **deferred** — not built in v1. The schema keeps a `tenant_id` column (defaulted to a single `"default"` tenant) so auth can be layered in later without a schema rewrite.
- Work proceeds in small milestones. After each milestone the assistant stops and lists exactly which files were added/changed so they can be committed to GitHub before moving on.

# Media Buying OS - Architecture, Contracts, State Machines

Generated 2026-08-09. The code is the source of truth; this file names it.

## Layering (spec section 1/38)
Frontend (content_engine_media_center)
-> OS API (/mediaos/* in content_engine_api)
-> Domain engines (media_os, media_plan, media_perf, media_creative)
-> Adapter (media_os.Adapter, UNSUPPORTED_CAPABILITY when unwired)
-> Sockets (content_engine_connectors: GoogleAds/MetaAds/TikTokAds/LinkedInAds)
The frontend never sees a provider endpoint, token or request shape.

## Campaign state machine
States: DRAFT, VALIDATING, READY, SCHEDULED, LAUNCHING, SUBMITTED, IN_REVIEW, ACTIVE, PAUSED, COMPLETED, ARCHIVED, VALIDATION_FAILED, LAUNCH_FAILED, PROVIDER_REJECTED, SYNC_FAILED
Moves: {
  "DRAFT": [
    "VALIDATING",
    "COMPLETED"
  ],
  "VALIDATING": [
    "READY",
    "VALIDATION_FAILED"
  ],
  "VALIDATION_FAILED": [
    "DRAFT"
  ],
  "READY": [
    "SCHEDULED",
    "LAUNCHING",
    "DRAFT"
  ],
  "SCHEDULED": [
    "LAUNCHING",
    "READY",
    "COMPLETED"
  ],
  "LAUNCHING": [
    "SUBMITTED",
    "ACTIVE",
    "LAUNCH_FAILED",
    "PROVIDER_REJECTED"
  ],
  "SUBMITTED": [
    "IN_REVIEW",
    "ACTIVE",
    "PROVIDER_REJECTED",
    "LAUNCH_FAILED"
  ],
  "IN_REVIEW": [
    "ACTIVE",
    "PROVIDER_REJECTED"
  ],
  "LAUNCH_FAILED": [
    "DRAFT",
    "LAUNCHING"
  ],
  "PROVIDER_REJECTED": [
    "DRAFT"
  ],
  "ACTIVE": [
    "PAUSED",
    "COMPLETED",
    "SYNC_FAILED",
    "ARCHIVED"
  ],
  "PAUSED": [
    "ACTIVE",
    "COMPLETED",
    "ARCHIVED"
  ],
  "SYNC_FAILED": [
    "ACTIVE",
    "PAUSED"
  ],
  "COMPLETED": [
    "ARCHIVED"
  ],
  "ARCHIVED": []
}

## Publish job state machine (spec section 17)
States: QUEUED, RUNNING, DONE, HELD, FAILED
Steps: validate, create_campaign_tree, verify, record_ids
Idempotency: job id and key derive from the campaign id, so a retry reuses
the same job; a campaign already carrying an external id SKIPS creation.

## Order lifecycle (spec section 20)
PROPOSED, VALIDATED, APPROVED, EXECUTING, EXECUTED, VERIFIED, HELD, FAILED, DISMISSED

## AI Action API (spec sections 32-33)
Actions: ADD_NEGATIVE_KEYWORD, CHANGE_BID, CREATE_CAMPAIGN, DECREASE_BUDGET, EXCLUDE_AUDIENCE, INCREASE_BUDGET, PAUSE_CAMPAIGN, REALLOCATE_BUDGET, REPLACE_CREATIVE, RESUME_CAMPAIGN
Levels: OBSERVE_ONLY, RECOMMEND, REQUIRE_APPROVAL, AUTO_EXECUTE (default REQUIRE_APPROVAL for all;
CREATE_CAMPAIGN capped at REQUIRE_APPROVAL; AUTO_EXECUTE budget change
refused past 50 percent)

## Error taxonomy (spec section 36)
Categories: AUTHENTICATION, PERMISSION, VALIDATION, RATE_LIMIT, ASSET, TARGETING, BUDGET, CREATIVE, POLICY, NOT_FOUND, CONFLICT, SERVER, UNKNOWN
Retryable: RATE_LIMIT, SERVER only. Validation, permission and
policy errors are never blindly retried.

## Database
Generated from content_engine_os_store.SCHEMA (one declaration; DDL, insert,
select and row mapping all derive from it). Media collections:
ad_accounts, media_campaigns, ad_groups, ads, audiences, creatives,
creative_versions, media_plans, ad_metrics, ad_rollups, sync_runs,
media_anomalies, creative_experiments, publish_jobs.

## Test plan
verify_media_os.py (gate groups G1-G34), verify_media.py, verify_os.py.
Every claim in this document is enforced by at least one gate; a claim
without a gate is a rumour.

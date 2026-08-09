# TikTok Ads - Platform Research Artifact

Generated from `content_engine_media_manifest.py` (the authoritative,
machine-readable manifest). Research verified on 2026-08-09 against
official documentation only. Fields the research did not verify are listed
under UNKNOWNS and must be verified before any code relies on them.

## API
- Current version: **v1.3**
  (verified: 2026-08-09, business-api.tiktok.com portal)
- Coded default in this engine: **v1.3**
  (env override: `TIKTOK_ADS_API_VERSION`)
- Base URL: `https://business-api.tiktok.com/open_api/v1.3`
- Auth: OAuth2 access token (Access-Token header)
- OAuth scopes: ["UNKNOWN - REQUIRES VERIFICATION"]
- Breaking-change note: none recorded

## Hierarchy (native, NOT renamed)
advertiser > campaign > ad_group > ad


## Networks / placements
- Networks: tiktok
- Placements: TikTok Feed


## Supports (per the manifest; UNKNOWN means UNKNOWN)
- campaign_creation: documented (campaign/create in v1.3)
- asset_upload: UNKNOWN - REQUIRES VERIFICATION
- preview: UNKNOWN - REQUIRES VERIFICATION
- targeting: True
- pause_resume: UNKNOWN - REQUIRES VERIFICATION
- budget_update: UNKNOWN - REQUIRES VERIFICATION

## Asset specs
- aspect_ratios: ['9:16']
- specs_detail: UNKNOWN - REQUIRES VERIFICATION

## Engine status
READ_SOCKET_ONLY

## UNKNOWNS - REQUIRES VERIFICATION before use
- api.oauth_scopes[0]
- api.rate_limits
- api.webhooks
- asset_specs.specs_detail
- campaign_types
- supports.asset_upload
- supports.budget_update
- supports.pause_resume
- supports.preview

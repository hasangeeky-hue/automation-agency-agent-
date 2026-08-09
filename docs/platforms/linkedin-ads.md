# LinkedIn Ads - Platform Research Artifact

Generated from `content_engine_media_manifest.py` (the authoritative,
machine-readable manifest). Research verified on 2026-08-09 against
official documentation only. Fields the research did not verify are listed
under UNKNOWNS and must be verified before any code relies on them.

## API
- Current version: **YYYYMM monthly (2026-07 docs current)**
  (verified: 2026-08-09, learn.microsoft.com; 202506 and 202507 already sunset)
- Coded default in this engine: **202601**
  (env override: `LINKEDIN_ADS_API_VERSION`)
- Base URL: `https://api.linkedin.com/rest`
- Auth: OAuth2, Linkedin-Version header REQUIRED
- OAuth scopes: ["r_ads", "r_ads_reporting", "rw_ads"]
- Breaking-change note: each YYYYMM version sunsets after a minimum of one year; the previously coded 202409 default is past that window. The Creatives API replaced adCreativesV2.

## Hierarchy (native, NOT renamed)
ad_account > campaign_group > campaign > creative
Note: LinkedIn's leaf is a CREATIVE under a campaign under a CAMPAIGN GROUP; it is not the same object as a Google ad and is not renamed into one. The canonical mapping stores campaign_group in provider_config.

## Networks / placements
- Networks: linkedin
- Placements: LinkedIn Feed


## Supports (per the manifest; UNKNOWN means UNKNOWN)
- campaign_creation: UNKNOWN - REQUIRES VERIFICATION
- asset_upload: True
- preview: documented Ad Preview API exists (2026-07 docs)
- targeting: True
- pause_resume: UNKNOWN - REQUIRES VERIFICATION
- budget_update: UNKNOWN - REQUIRES VERIFICATION

## Asset specs
- specs_detail: UNKNOWN - REQUIRES VERIFICATION

## Engine status
READ_SOCKET_ONLY

## UNKNOWNS - REQUIRES VERIFICATION before use
- api.rate_limits
- api.webhooks
- asset_specs.specs_detail
- campaign_types
- supports.budget_update
- supports.campaign_creation
- supports.pause_resume

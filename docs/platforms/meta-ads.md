# Meta Ads (Facebook + Instagram) - Platform Research Artifact

Generated from `content_engine_media_manifest.py` (the authoritative,
machine-readable manifest). Research verified on 2026-08-09 against
official documentation only. Fields the research did not verify are listed
under UNKNOWNS and must be verified before any code relies on them.

## API
- Current version: **v25.0**
  (verified: 2026-08-09, official developer blog (announced 2026-02-18))
- Coded default in this engine: **v25.0**
  (env override: `META_API_VERSION`)
- Base URL: `https://graph.facebook.com/{version}`
- Auth: OAuth2 long-lived token (Marketing API access)
- OAuth scopes: ["ads_management", "ads_read"]
- Breaking-change note: Graph versions live roughly two years; the previously coded v21.0 (2024-10) is at end of life

## Hierarchy (native, NOT renamed)
ad_account > campaign > ad_set > ad


## Networks / placements
- Networks: facebook, instagram
- Placements: Facebook Feed, Instagram Feed, Instagram Stories, Instagram Reels


## Supports (per the manifest; UNKNOWN means UNKNOWN)
- campaign_creation: UNKNOWN - REQUIRES VERIFICATION
- asset_upload: UNKNOWN - REQUIRES VERIFICATION
- preview: UNKNOWN - REQUIRES VERIFICATION
- targeting: True
- pause_resume: True
- budget_update: True

## Asset specs
- image_formats: ['PNG', 'JPEG']
- video_formats: ['MP4', 'MOV']
- aspect_ratios: ['9:16', '1:1', '4:5', '16:9']
- specs_detail: UNKNOWN - REQUIRES VERIFICATION

## Engine status
READ_SOCKET_ONLY

## UNKNOWNS - REQUIRES VERIFICATION before use
- api.rate_limits
- api.webhooks
- asset_specs.specs_detail
- campaign_types
- supports.asset_upload
- supports.campaign_creation
- supports.preview

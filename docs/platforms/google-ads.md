# Google Ads - Platform Research Artifact

Generated from `content_engine_media_manifest.py` (the authoritative,
machine-readable manifest). Research verified on 2026-08-09 against
official documentation only. Fields the research did not verify are listed
under UNKNOWNS and must be verified before any code relies on them.

## API
- Current version: **v25**
  (verified: 2026-08-09, official release notes)
- Coded default in this engine: **v25**
  (env override: `GOOGLE_ADS_API_VERSION`)
- Base URL: `https://googleads.googleapis.com/{version}`
- Auth: OAuth2 refresh token + developer token
- OAuth scopes: ["https://www.googleapis.com/auth/adwords"]
- Breaking-change note: v25 (2026-07) is a major release with breaking changes; do not mix v21-v24 examples into v25 calls

## Hierarchy (native, NOT renamed)
customer > campaign > ad_group > ad


## Networks / placements
- Networks: search, display, youtube, performance_max
- Placements: Google Search, YouTube video placement, Display network
- YouTube advertising runs THROUGH this adapter; there is deliberately no separate YouTube API architecture

## Supports (per the manifest; UNKNOWN means UNKNOWN)
- campaign_creation: True
- asset_upload: True
- preview: UNKNOWN - REQUIRES VERIFICATION
- targeting: True
- pause_resume: True
- budget_update: True
- negative_keywords: True
- offline_conversions: True

## Asset specs
- rsa_headline_max_chars: 30
- rsa_description_max_chars: 90
- image_formats: ['PNG', 'JPEG']
- video: via YouTube
- aspect_ratios: UNKNOWN - REQUIRES VERIFICATION

## Engine status
LIVE_CAPABLE

## UNKNOWNS - REQUIRES VERIFICATION before use
- api.rate_limits
- asset_specs.aspect_ratios
- supports.preview

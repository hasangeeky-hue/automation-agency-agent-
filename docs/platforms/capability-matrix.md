# Platform Capability Matrix

Generated from `content_engine_media_manifest.py`, the ONE machine-readable
manifest that is authoritative for UI capability rendering. Do not edit this
file to change behaviour; edit the manifest and regenerate
(`python -c "import content_engine_media_manifest as M, json; print(json.dumps(M.manifest(), indent=2))"`).

Verified against official documentation on **2026-08-09**. Anything the
research could not verify is marked `UNKNOWN - REQUIRES VERIFICATION` in the
manifest and rendered as unknown in the UI, never assumed.

| | Google Ads | Meta Ads | LinkedIn Ads | TikTok Ads |
|---|---|---|---|---|
| Current API version | v25 | v25.0 | monthly YYYYMM (min 1 year, then sunset) | v1.3 |
| Coded default | v25 | v25.0 | 202601 | v1.3 |
| Hierarchy | customer > campaign > ad_group > ad | ad_account > campaign > ad_set > ad | ad_account > campaign_group > campaign > creative | advertiser > campaign > ad_group > ad |
| Leaf object | ad | ad | **creative** (not an "ad") | ad |
| YouTube | runs THROUGH this adapter | - | - | - |
| Campaign create wired in this engine | yes (socket) | no (holds in words) | no (holds in words) | no (holds in words) |
| Read/summary socket | yes | yes | yes | yes |
| Pause write | yes | socket-dependent | UNKNOWN | UNKNOWN |
| Preview | UNKNOWN (local approximate preview used) | UNKNOWN | documented Ad Preview API exists | UNKNOWN |
| Webhooks | none (polling) | UNKNOWN | UNKNOWN | UNKNOWN |
| Rate limits | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

Sources: developers.google.com/google-ads/api (release notes, current as of
2026-08), developers.facebook.com (v25.0 announced 2026-02-18),
learn.microsoft.com/linkedin/marketing (202506/202507 sunset; versioning
policy), business-api.tiktok.com/portal (v1.3 base URL, OAuth2).

## Upgrade path (spec section 2)

Every socket reads its version from an environment variable with a verified
default: `GOOGLE_ADS_API_VERSION` (v25), `META_API_VERSION` (v25.0),
`LINKEDIN_ADS_API_VERSION` (202601), `TIKTOK_ADS_API_VERSION` (v1.3).
To upgrade: set the env var on the VPS, restart, run one pull, read the
System Map diagnostic. If the platform rejects the version, the error is
normalized (AUTHENTICATION/VALIDATION/...) and shown, never hidden. The old
defaults (Google v21, Meta v21.0, LinkedIn 202409) were PAST SUNSET when
this was fixed on 2026-08-09.

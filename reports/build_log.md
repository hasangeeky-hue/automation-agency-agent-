# AGENT OS build log

Per Section 0.4: FINISHED / COULDN'T / NEED FROM FOUNDER, per phase.
The builder follows the same doctrine it is building.

---

## Session A — Phase 0 (connector health) + Phase 1 (the daily report)
2026-08-15

**FINISHED**
- Phase 0: connector verdicts now survive a restart. `note_auth()` writes
  every accept/reject to the settings store (already Postgres-backed);
  `connectors.health()` reports the four contract states, and green is
  impossible without a real accepted call AND its timestamp.
  `GET /connectors/health`. 15 gates pass, including a subprocess restart
  test proving a rejection outlives the process that learned it.
- Phase 1: `content_engine_contracts.py` (the shared shapes),
  `content_engine_roster.py` (18 employees + ATTRIBUTION),
  `content_engine_report.py` (report_today / agent_cards / company_today /
  idempotent snapshot). `GET /agents`, `/agents/{id}/report`,
  `/agents/{id}/learned`, `/company/today`, `POST /company/snapshot`.
  Nightly snapshot added to the scheduler cadence. 23 gates pass.

**COULDN'T**
- Sections 3–6 (Phases 2–6) are not built. The founder asked for all of it
  in one shot; the script's own sizing rule (10.6) puts Phase 0 + Phase 1
  in Session A, and a single session cannot honestly carry five new lanes,
  seven recreated screens and a deploy. Reported rather than half-built.
- "Remove old OS" was requested and NOT done: Prime Directive 0.1 says the
  engine is keep-as-is and 0.1 also says stop and report rather than
  rewrite silently. Needs the founder to name exactly what to remove.
- The store table asked for in Phase 0 is the settings store, not a new
  `connector_health` table. Same Postgres, same durability, no migration.
  Flagged as a deliberate deviation; say the word and it becomes a table.

**NEED FROM FOUNDER**
- Decide what "remove old OS" means concretely (Section 7 item, new).
- Section 7 items 1–2 still block Media: enable Drive + Sheets APIs, and
  fix the Google Ads OAuth client (`invalid_client`).
- Confirm session sizing for the rest, per 10.6.

**Corrections found while building (the spec asked for verification, 10.2)**
- The audit's attribution names were wrong. `researcher`, `writer`,
  `image_prompts`, `seo_onpage`, `lead_cleaning`, `segmentation`,
  `outreach_performance` do not exist. The real steps, read from the
  running orchestrator, are: site_intelligence, competitor_intel,
  content_strategist, content_producer, seo_optimizer, qa_compliance,
  publisher, analytics_funnel, optimizer, lead_sourcing, lead_qualifier,
  segmenter, outreach_copy, outreach_send. ATTRIBUTION uses the real ones.
- Rehoming a screen moves three things, not one. Moving SGA's social
  markup without its handlers left two dead buttons; then without its
  stylesheet, fourteen unstyled classes; then the stylesheet emitted bare
  because SG.CSS is raw rules, not a `<style>` block. All three were
  caught by the dashboard's own gates, not by review.

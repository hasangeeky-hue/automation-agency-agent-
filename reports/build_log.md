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

## Session F — Phase 5 complete + Lane 3c stage 1 (Commerce)
2026-08-15

**FINISHED**
- ALL 51 SCREENS OF THE WIREFRAME ARE BUILT. Turn 11 (Commerce, 9) and
  turn 10 (Product Publisher, 1) close it out, across six nav pages.
- Lane 3c stage 1: `content_engine_commerce_desk.py`. Reads the catalogue
  daily and reports dead SKUs, low stock, missing prices and duplicate
  titles. Pure code, no model call, no paid endpoint, so it costs $0 like
  the Integrations Engineer. On the cadence, before the nightly snapshot.
- `commerce.analyst` promoted notstaffed -> INSPECTOR, with the reason on
  the badge. It becomes LIVE only at stage 2, when it proposes price and
  promotion changes with a margin preview behind the spend gate. Its own
  check fails the build if a write function ever appears in the module.
- 289 deploy checks, 0 failed. 59 gates in verify_agentos.

**THE COUNT WAS WRONG, AND IS NOW RIGHT**
- The wireframe is 51 screens, not 54. I had assumed turn 10 ran 10a to
  10d; the t10 block contains exactly ONE screen id. Counted from the
  file this time rather than inferred from the pattern. The published
  employee spec is corrected.

**FIVE DESKS, ONE EMPLOYEE**
- 11b, 11c, 11d, 11e and 11f are all `commerce.analyst`: Inventory
  Controller, Pricing Analyst, Merchandiser, Promotions Manager and
  Lifecycle Analyst. This was the case the whole 18-not-32 argument was
  built on, and every one of the five screens says so.

**WHAT THE SCREENS REFUSE TO DRAW**
- No discount button on 11e. A discount moves money, so it is stage 2
  behind the SPEND gate; a button that does nothing or does something
  ungated are both unacceptable, so the screen explains its absence.
- No competitor prices, no margin, no top sellers: those need cost data
  and order history that no connected platform sends here. Absent, not
  guessed.
- Amazon, Shopware 6, TikTok Shop and Meta Shop are laid out empty with
  the credential that would fill them.

**A REAL EXTENSION TO THE ENGINE**
- `fetch_catalogue` returned only id, title, type, status and url, so an
  inventory desk had nothing to inspect. It now also returns sku, price
  and stock where the platform provides them. Missing stays None and is
  never read as 0: Woo sends null for stock it is not tracking, and "not
  tracked" is not "none left".

**COULDN'T**
- Stage 2 of commerce (the pricing and promotions lane) is not built.
- The old dashboard pages are still present. Now that all 51 screens
  exist, retiring them is the next session's work and needs the founder's
  go, because it removes screens he uses today.
- Same nine suites exit nonzero, all failing at baseline.

**Corrections found while building (10.2)**
- The Commerce Analyst's own check grepped its own source for forbidden
  function names and found them in its own tuple, so it failed the moment
  it was written. It now asks the module namespace what it defines.
- `verify_report.py` asserted "a not-staffed desk says so" by NAMING
  commerce.analyst, and broke the moment that desk was promoted. Replaced
  with the real invariant: every card carries exactly the roster's badge,
  derived rather than named, which survives future promotions.

---

## Session E — Phase 5, part 3: Leads and Outreach (turn 12)
2026-08-15

**FINISHED**
- `content_engine_agentos_leads.py`: all nine screens of turn 12.
  41 of the 54 screens now exist across five nav pages.
- Every constant on these screens is READ from the engine, not retyped:
  TARGET_MARKETS, ICP_VERTICALS, WARMUP_RAMP and SEQUENCE_TOUCHES from
  `content_engine_outreach`, ICP_ROTATION from the scheduler.
- Four employees work nine desks. 12c, 12d and 12i are all
  `leads.qualifier`; 12f and 12h are both `leads.sender`. Every one of
  those five screens discloses it, and the gate fails the build if one
  stops.
- `verify_agentos.py` now 50 gates; prover 283 checks, 0 failed.

**A SAFETY CLAIM I HAD TO CORRECT**
- The wireframe describes the Data Cleaner as hard-blocking EU leads from
  outreach, and I repeated that in the employee spec. THE ENGINE HAS NO
  SUCH BLOCK, and it should not: Germany and Switzerland are two of the
  five entries in TARGET_MARKETS, so an EU block would block the
  business. What is really enforced is the absolute suppression list, the
  warm-up ramp, the open-tracking consent switch (which is the actual
  GDPR control in the code) and the permanent SEND gate.
- Drawing the hard block would have been false-green pointing the other
  way: showing a safety control that does not exist. 12c states the gap
  and asks the founder to decide whether per-country rules are wanted.
  The published employee spec has been corrected to match.

**COULDN'T**
- 13 screens remain: t11 Commerce (9) and t10 Product Publisher (4).
  Commerce is last by the agreed order because it needs a commerce lane
  that nothing creates work for yet.
- ESP routing (Klaviyo or platform-native bulk) is drawn empty with the
  credential named. No numbers.
- Same nine suites exit nonzero, all failing at baseline.

**DECIDED BY THE FOUNDER (same day)**
- No per-country outreach exclusion. Europe and Germany stay in scope.
  No block exists in the engine and none will be added.
- That moves the whole compliance weight onto open tracking, which is
  opt-OUT in the engine and therefore ON unless switched off. 12c now
  shows its LIVE state and offers the switch (POST /outreach/tracking),
  because a control that is described but not shown is one nobody uses.
  The gate fails the build if that live state stops being shown.

**NEED FROM FOUNDER**
- The three standing items are unchanged.

---

## Session D — Phase 5, part 2: the two departments that produce daily
2026-08-15

**FINISHED**
- `content_engine_agentos_growth.py`: turn 9 (Marketing and Content, 8
  screens) and turn 8 (SEO, AEO and GEO, 8 screens). Titles read out of
  the handoff file, including 9b which needed a third pass to find.
- 32 of the 54 screens now exist and are reachable: Cockpit, Marketing,
  Search and Web and Data Core.
- The approval room (9c) calls the SAME `/jobs/{id}/approve` route the
  old dashboard uses, so there is exactly one path from approved to
  published in the whole product rather than a second one that drifts.
- `verify_agentos.py` now 45 gates; prover section 21 covers all 32.
  280 deploy checks, 0 failed.

**THE DISCLOSURE THAT MATTERS**
- 8c Analyst and 8e Keyword Strategist are ONE employee, `seo.analyst`.
  The wireframe draws two desks and that is correct: they answer
  different questions. Letting the founder believe two people are
  employed would not be. Both screens say so on their face, and the gate
  FAILS the build if either stops saying it.

**COULDN'T**
- 22 screens remain: t12 Leads (9), t11 Commerce (9), t10 Publisher (4).
- Several things the wireframe draws for these departments have no wire
  and are laid out empty with a [PLANNED] chip and the credential that
  would fill them: Metricool, newsletter, competitor ad reading, and the
  backlink data behind the Link Builder's desk.
- Drive is refusing, so the Producer's "saved to Drive" panel says that
  rather than drawing a file list.
- Same nine suites still exit nonzero, all verified failing at baseline.

**NEED FROM FOUNDER**
- Unchanged.

---

## Session C — Phase 5, part 1: the wireframe recreated (t13 + t14)
2026-08-15

**FINISHED**
- `content_engine_os_kit.py`: the Industry design system and the five
  reusable objects the whole OS composes from (blueprint card, staffing
  badge, acv2 agent card with today's report, connector registry row,
  command panel). Tokens are declared on `.osx` and read only from there,
  because the last redesign lost a day to `var()` fallbacks resolving to
  the host shell's dark values.
- `content_engine_agentos.py`: all 16 screens of turn 13 (Web and Data
  Core, 11) and turn 14 (Cockpit, 5), screen ids and titles read out of
  the handoff file rather than invented.
- Wired into the dashboard as two new pages under an "Agent OS" nav
  group, bound to /agents, /company/today, /connectors/health and
  /integrations. Barlow and Barlow Condensed now load, so the DS type is
  real rather than an Arial Narrow lookalike.
- `verify_agentos.py` (38 gates) asserts against the ASSEMBLED PAGE, and
  prover section 21 repeats it on the box. 278 deploy checks.

**COULDN'T**
- Only 16 of the 54 screens exist. t8, t9, t10, t11 and t12 are not
  built. The old dashboard pages therefore STAY: removing a working
  screen before its replacement exists would take capability away from
  the founder in exchange for a tidier nav. They are retired in the last
  session, per the agreed order.
- The same nine suites still exit nonzero. Verified failing at the
  baseline before this session's changes.

**NEED FROM FOUNDER**
- Nothing new. The three standing items are unchanged.

**Corrections found while building (10.2)**
- I OVERWROTE TWO EXISTING MODULES. `content_engine_os_core.py` (916
  lines, the Engagement OS vocabulary that every OS module imports) and
  `verify_os.py` (1760 lines, its 526-check gate) already existed, and
  the new files took their names. The Write tool said "updated", not
  "created", and I did not read it. Both were restored from HEAD and the
  new modules renamed to `content_engine_agentos.py` and
  `verify_agentos.py`. Nothing was lost; both gates pass again. A new
  module name must be checked against the tree BEFORE writing it.
- `dashboard_html(st=...)` is the CONNECTOR STATUS DICT, not a store. The
  first wiring passed it to `build_ctx()`, which wants a store. The name
  looked like one and the shape was not, which is the same class as the
  audit key-versus-shape mistake. The renderer now takes `os_ctx` built
  by the API, matching every other section.
- The Tool Connection Hub first keyed its inputs by WIRE name. `POST
  /connect` accepts allow-listed CREDENTIAL KEYS, and no wire-to-key map
  exists in the engine because presence is computed per adapter. Rather
  than hand-write a thirty-row mapping that must agree with ninety-three
  keys, the hub now asks for exactly what the endpoint accepts.
- Two of the four staffing badges rendered UNSTYLED: the kit's own check
  listed class names by hand and missed `ox-b-inspector` and
  `ox-b-architected`. The check now derives the list from the badge
  vocabulary. A hand-written list of things to check is the same bug as
  a hand-written list of anything else.
- The nav's active link was hard-coded to `cockpit`. Adding a page in
  front of it would have opened one section while a different link
  looked selected.

---

## Session B — Phase 2 (memory) + Lane 3a (the Integrations Engineer)
2026-08-15

**FINISHED**
- Phase 2: the playbook is now per LANE, not one per company. `content`
  deliberately keeps the bare client key, so every playbook already stored
  on the VPS survives untouched. `record_lane_cycle()` gives lanes that
  are cadence tasks rather than job pipelines a way to remember, and an
  empty call RAISES instead of counting a cycle. `/agents/{id}/learned`
  now answers from that employee's own lane, so two cards can no longer
  recite the same three lines. 23 gates.
- Lane 3a: `content_engine_integrations.py`, the Integrations Engineer,
  built on the six rungs. Free daily check for newly-rejected wires,
  shadowed keys, half-configured groups and stale green. It proposes
  fixes and re-asks if a wire breaks again, but it may NEVER mark a wire
  verified - the gate asserts `note_auth` does not appear in the module,
  because a free self-test that could turn a light green would undo
  Phase 0 from inside the machinery built to protect it. `GET
  /integrations`, `POST /integrations/run`. 30 gates.
- Badge flipped to live only after the cadence runs it, the report
  carries it and the gate holds it, per the P3 definition of done.
- verify_deploy section 20. 263 checks, 0 failed.

**COULDN'T**
- The company's day had two definitions. Workers stamped UTC and the
  report read the LOCAL date; for the hours they disagreed an employee
  that had worked showed a blank card. Fixed at the report path via
  `contracts.today()`, but ~20 other sites (BI, cockpit, connectors,
  actions) still call `date.today()` for window maths. Not swept in this
  session: it is a wide refactor with real regression risk and it is not
  what was asked for. Listed here rather than done quietly.
- `verify_vocabulary` fails one check: "a CARD on the Creative & image
  board shows it". It failed identically at 79c8df5, before this
  session's changes, and needs render-then-look on a real board.
- Nine suites exit nonzero (vocabulary, cadence, diagnostics, media_os,
  details, loop, vx2, vx2_ads, vx2_seo). All nine were verified failing
  at the baseline commit BEFORE this session's changes. `loop` and `vx2`
  assert against the retired 16-tab cockpit and the cancelled VX2 and
  need rewriting, not patching.

**NEED FROM FOUNDER**
- Same three as Session A: what "remove old OS" means, the Drive/Sheets
  APIs, and the Google Ads OAuth client.
- Whether to sweep `date.today()` across BI and cockpit in a session of
  its own.

**Corrections found while building (the spec asked for verification, 10.2)**
- The first draft of the all-or-nothing wire groups said `("gsc",
  "ga4")`. Neither is a real wire. It would have reported "all clear"
  forever while checking nothing - the same class of mistake as Session
  A's guessed step names, made again one session later. The names now
  come from `health()`, and `integrations.check()` fails the build if a
  named wire does not exist.
- `record_lane_cycle` looked correct and taught nothing: `insights` only
  ever reached the history, which nothing reads. A lane could record
  thirty cycles and still have nothing to say. Playbooks now carry
  `observations`.
- The "which fix actually worked" memory compared against a state the
  same function had already overwritten, so it could never fire once.


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

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

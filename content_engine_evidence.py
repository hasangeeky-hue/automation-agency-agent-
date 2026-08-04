"""WHAT KIND OF THING IS THIS NUMBER.

Every card on this dashboard ends in a `src` string — 208 distinct ones across
1,266 authored cards. They were already there, and they were already honest:
37 cards say "principle", 24 say "judgement", 4 say "honest limit". Those are
admissions that the number is an opinion, not a measurement.

But nothing rendered that distinction. A card sourced "GA4" and a card sourced
"judgement" looked identical — same type, same weight, same authority. You
cannot make a good decision when a measured fact and a house rule are dressed
the same.

This module is the single vocabulary for that distinction. One token, one
class, one explanation. It is imported by the card renderer, so a card cannot
show a number without also declaring what kind of number it is.

FOUR CLASSES
  measured    — read from a live source. It was true when it was read.
  computed    — arithmetic over other numbers. Only as good as its inputs.
  declared    — a rule, a limit, a policy or your own input. Not evidence.
  navigation  — the card carries no number; it points somewhere.

THE GATE
  verify() asserts every statically-authored token is classified. An
  unclassified token fails the build. classify() never raises at runtime —
  an unknown source degrades to an explicit "unclassified" answer rather
  than crashing a board or, worse, silently claiming to be measured.
"""

from __future__ import annotations

# ---------------------------------------------------------------- classes

CLASSES = {
    "measured": ("Measured", "#3FD98B",
                 "A real value, read from a live source at the time shown. "
                 "If the source is unreachable the card says so instead of "
                 "showing a zero."),
    "computed": ("Computed", "#4C8DFF",
                 "Not read from anywhere — worked out by arithmetic from "
                 "other numbers. It is exactly as trustworthy as its inputs."),
    "declared": ("Declared", "#F5B14C",
                 "NOT A MEASUREMENT. This is a rule, a cap, a policy or "
                 "something you told the engine. It will not change on its "
                 "own, and no amount of good performance will move it."),
    "navigation": ("Link only", "#8E9BBE",
                   "This card carries no measurement of its own. It exists "
                   "to take you somewhere else."),
    "unclassified": ("Unclassified", "#FF6B93",
                     "This card's source has no entry in the evidence table. "
                     "Treat the number as unverified until it does."),
}

ORDER = ("measured", "computed", "declared", "navigation", "unclassified")

# ---------------------------------------------------------------- the table
# token -> (class, what reading this number actually means)
#
# Written once per DISTINCT token, not per card. 208 entries cover 1,240
# authored cards. Keep it that way: if a board needs a new src string, add it
# here in the same commit or the build stops.

SOURCES: dict = {}


def _add(cls: str, entries: dict) -> None:
    for token, why in entries.items():
        SOURCES[token] = (cls, why)


# ---- COMPUTED ------------------------------------------------------------
_add("computed", {
    "computed":
        "Worked out inside the engine from numbers already collected. It is "
        "not a reading from any outside system, so if the inputs are stale "
        "this is stale too.",
    "arithmetic":
        "Plain arithmetic over two or more figures on this same board. No "
        "outside call was made.",
    "composite":
        "Several separate measurements rolled into one score. A good "
        "composite can hide one bad component — open the parts before acting.",
    "unit economics":
        "Cost and revenue per client, divided out. Moves whenever either "
        "spend or client count changes, so read it as a ratio, not a total.",
    "spend ÷ clients":
        "Total spend divided by the number of active clients. With few "
        "clients a single new one swings this hard.",
    "computed from live wires":
        "Derived from which connectors actually answered, not from a stored "
        "list. If a wire drops, this recalculates on the next read.",
    "cross-channel":
        "Added up across every channel the engine publishes or sends to. A "
        "channel that is switched off contributes zero, not nothing.",
    "computed from your own crawl + Search Console":
        "Your crawler found the pages; Search Console supplied the "
        "performance. Pages Google has not indexed contribute nothing.",
    "counter":
        "A running count kept by the engine. It resets only when the "
        "underlying records are deleted.",
    "vendor_share":
        "One vendor's spend as a share of total spend. Percentages move when "
        "either the numerator or the total changes.",
    "impression share":
        "The share of available impressions actually won, as reported by the "
        "ad platform and re-expressed here.",
    "loop closure":
        "How much of the publish → measure → learn loop actually completed, "
        "computed from live wire status rather than drawn on a diagram.",
    "measured funnel":
        "Stage-to-stage conversion worked out from recorded events. Stages "
        "with no events are reported as unmeasured, never as zero.",
    "cross-section":
        "Rolled up from more than one section of the dashboard. Open each "
        "section to see which one is moving the total.",
})

# ---- DECLARED ------------------------------------------------------------
_add("declared", {
    "principle":
        "A design principle this engine holds, not a measurement. It is true "
        "because it was decided, and it will not change because performance "
        "changed.",
    "judgement":
        "An assessment, not a reading. A person or a model formed this view. "
        "Disagree with it freely — nothing was measured to produce it.",
    "your decision":
        "You set this. The engine is repeating your instruction back to you, "
        "not evaluating whether it was a good one.",
    "platform rule":
        "A limit imposed by an outside platform (LinkedIn, Google, an email "
        "provider). The engine cannot negotiate it; it can only stay inside it.",
    "platform rules":
        "Limits imposed by outside platforms. Breaking them risks the "
        "account, not just the campaign.",
    "honest limit":
        "A stated boundary of what this engine can currently know. It is "
        "shown so the gap is visible rather than filled with a guess.",
    "honest scope":
        "What this measurement deliberately does and does not cover, stated "
        "so the number is not read wider than it earns.",
    "your input":
        "A value you typed. Nothing validates it against reality, so if it "
        "was wrong when entered it is still wrong here.",
    "your ICP":
        "Your definition of an ideal customer. Everything filtered by it "
        "inherits its accuracy — narrow it and counts fall by definition.",
    "your targets":
        "Goals you set. Distance-to-target says nothing about whether the "
        "target was realistic.",
    "your setting":
        "A configuration value you chose. Changing it changes behaviour "
        "immediately, with no further approval.",
    "safety rule":
        "A hard rule that blocks an action regardless of context. It is not "
        "advisory and the engine cannot override it.",
    "safety module":
        "The safety layer's own declaration of what it will refuse. Read it "
        "as a promise about behaviour, not a count of events.",
    "safety":
        "A safety boundary the engine enforces on itself before acting.",
    "design choice":
        "A deliberate build decision. There is a trade-off behind it, and it "
        "can be revisited.",
    "stated obligations":
        "Commitments recorded as text. Nothing verifies they were kept — "
        "this is the promise, not the delivery.",
    "stated":
        "Recorded because someone stated it. Unverified by any measurement.",
    "policy summary":
        "A condensed statement of policy. The full policy is authoritative "
        "where this summary is ambiguous.",
    "pricing":
        "Your price list. It drives every revenue projection on this "
        "dashboard, so an out-of-date price quietly corrupts them all.",
    "ICP definition":
        "The written definition used to qualify leads. Change it and "
        "historical counts stop being comparable.",
    "taxonomy":
        "The shared vocabulary of content types and channels. One list, used "
        "by every module, so a value here is either known everywhere or "
        "nowhere.",
    "template":
        "A fixed structure the engine fills in. It constrains output shape "
        "regardless of what a model would otherwise produce.",
    "recommendation":
        "A suggested next move. Nothing has been done, and nothing will be "
        "unless you act on it.",
    "budget":
        "A ceiling you set on spend. A ceiling is not a reservation — unused "
        "budget costs nothing and is never charged.",
    "live caps":
        "The spend and send limits currently in force. They stop work rather "
        "than slowing it, so hitting one halts the queue.",
    "warmup cap":
        "The deliberately low sending limit applied to a new mailbox. Raising "
        "it early is the fastest way to damage deliverability.",
    "warmup":
        "The staged ramp for a new sending identity. Reputation is built by "
        "elapsed time and consistency, not by volume.",
    "read scope":
        "What this view is permitted to look at. Anything outside the scope "
        "is absent from the number, not counted as zero.",
    "eligibility":
        "The rule deciding what qualifies. Items excluded by it never appear "
        "in the count at all.",
    "not run":
        "This check has not executed. The absence of a finding is not a "
        "clean result — nothing has looked yet.",
    "requires a test":
        "Claimed but unverified. It needs a real test run before it should "
        "be trusted.",
    "QA gate":
        "The quality rule a piece must satisfy before it can proceed. It "
        "blocks; it does not score.",
})

# ---- NAVIGATION ----------------------------------------------------------
_add("navigation", {
    "navigation":
        "This card is a signpost. It holds no measurement of its own — the "
        "numbers live on the page it points to.",
    "decision queue":
        "Points to the queue of decisions waiting for you.",
    "Leads & Outreach":
        "Points to the Leads & Outreach section, where lead records and "
        "email sequences live.",
    "System & Wiring":
        "Points to System & Wiring, where connector health and credentials "
        "live.",
    "Content Factory":
        "Points to the Content Factory, where pieces are planned, written "
        "and previewed.",
    "Risk & Infrastructure":
        "Points to Risk & Infrastructure, where backups and exposure live.",
    "Media Buying":
        "Points to Media Buying, where paid campaigns and spend live.",
    "BI":
        "Points to Business Intelligence, where revenue and funnel figures "
        "live.",
    "SEO":
        "Points to the SEO section, where crawl, index and ranking work "
        "lives.",
    "GEO engine":
        "Points to the GEO engine, which handles location-specific search "
        "work.",
    "/leads/edit":
        "Opens the lead editor. Changes there are saved immediately.",
    "/leads/delete":
        "Deletes a lead record. This is not reversible from the dashboard.",
})

# ---- MEASURED ------------------------------------------------------------
_add("measured", {
    # --- Google / analytics
    "GA4":
        "Read live from Google Analytics 4 for the exact page in question. "
        "GA4 lags by up to 48 hours, so today's figure is usually incomplete.",
    "Search Console":
        "Read from Google Search Console. Its data is typically 2-3 days "
        "behind, and it only covers pages Google has indexed.",
    "GSC (live)":
        "A live Search Console call made for this card, not a cached figure.",
    "GSC (live today)":
        "A Search Console call made during today's run.",
    "GSC + crawler (live)":
        "Search Console performance joined to your own crawl, so pages "
        "Google knows about and pages you publish are compared directly.",
    "GSC + search terms":
        "Search Console impressions joined to the paid search-terms report, "
        "showing organic and paid demand for the same query.",
    "Search Console comparison":
        "Two Search Console periods placed side by side. Seasonality is not "
        "removed, so compare like periods.",
    "URL Inspection API":
        "Google's own answer about whether a specific URL is indexed. This "
        "is authoritative in a way a crawl result is not.",
    "audit + index status":
        "Your site audit joined to Google's index status, so on-page problems "
        "and indexing problems are separated.",
    "Google Ads API":
        "Read live from the Google Ads API for your account.",
    "conversion_action":
        "The conversion definitions configured in Google Ads. If one is "
        "mis-configured, every downstream figure inherits the error.",
    "keyword_view":
        "Per-keyword performance from Google Ads.",
    "search_term_view":
        "The actual queries people typed, from Google Ads — not the keywords "
        "you bid on.",
    "search terms report":
        "The real queries that triggered your ads.",
    "search terms → strategist":
        "Real paid search queries fed into the content strategist, so "
        "planning follows demand that has already been observed.",
    "change_event":
        "Google Ads' own log of account changes, so a performance shift can "
        "be matched to what was altered.",
    "asset view":
        "Per-asset performance from the ad platform.",
    "ad_group_audience_view":
        "Audience-level performance within an ad group.",
    "ad_group_ad_asset_view":
        "Asset-level performance within an ad group's ads.",
    "geo_target_type_setting":
        "The geographic targeting actually configured on the campaign.",
    "KeywordPlanIdeaService":
        "Google's keyword ideas service. Its volumes are rounded ranges, not "
        "exact counts.",
    "ad platforms":
        "Read from the connected advertising platforms.",
    "per-campaign costs":
        "Spend broken out per campaign, as the platform reports it.",
    "Cal.com":
        "Read from Cal.com — actual bookings, not form submissions.",
    "Cal.com + spend":
        "Real bookings set against real spend, giving a cost per booked call.",
    "Google Sheets":
        "Read from your Google Sheet. It is only as current as the last "
        "write to that sheet.",
    "Google Drive":
        "Read from Google Drive. It reports what the service account can "
        "see, which is only folders that have been shared with it.",
    "Google hub":
        "Read through the Google service-account connection shared by Search "
        "Console, Analytics and Drive.",

    # --- crawling / SEO measurement
    "own crawler":
        "Your own crawler fetched these pages. It sees what a visitor sees, "
        "which can differ from what Google has indexed.",
    "site audit":
        "The full-site technical audit run by this engine.",
    "entity audit":
        "A check of how clearly your entities are described on the page.",
    "market audit":
        "A scan of the competitive landscape for your terms.",
    "GEO audit":
        "A search audit run for a specific location. Results differ by "
        "city, so a figure here does not generalise to other markets.",
    "GEO audit (live)":
        "A location-specific audit run live for this card.",
    "citation extractor":
        "Extracted citations from answer-engine responses — which sources "
        "the model actually named.",
    "AEO probe":
        "A probe that asks an answer engine a real question and records "
        "whether you appear.",
    "AEO probe (live)":
        "A live answer-engine probe run for this card.",
    "multi-engine probe":
        "The same question asked of several answer engines, so a result is "
        "not one model's opinion.",
    "answer-quality pass":
        "A scored pass over how well an answer engine described you. The "
        "score is produced by a model, so treat it as a strong opinion, not "
        "a measurement.",
    "AEO engine":
        "The answer-engine optimisation module's own measurements.",
    "SEO engine":
        "Measured by the SEO module itself during its last run. It reflects "
        "the state at that run, not this moment.",
    "SERP preview":
        "How the result is expected to render in search, built from the "
        "actual title and description tags.",
    "robots.txt":
        "Read from your live robots.txt. It governs what crawlers may fetch.",
    "site":
        "Fetched from your live website just now. It shows what a visitor "
        "gets, which can differ from what Google has cached.",
    "Serper":
        "Live search results fetched through Serper. Rankings are "
        "personalised and volatile, so a single reading is a sample, not a "
        "position.",
    "Serper Maps":
        "Live local map-pack results through Serper. Map results are "
        "strongly location-dependent and change more often than classic "
        "listings.",
    "Serper + Prospeo":
        "Search results joined to contact enrichment.",
    "crawler → Quality Score":
        "Your crawl findings mapped to the factors that drive ad Quality "
        "Score, connecting on-page work to ad cost.",
    "competitor intel":
        "Collected observations about competitors.",
    "interlock engine":
        "The module that links SEO, paid and content signals to each other.",

    # --- jobs / engine internals
    "jobs":
        "Read from the job records in the database.",
    "job store":
        "Read directly from the job store — the engine's own record of every "
        "piece of work.",
    "job queue":
        "The live queue. It changes between page loads.",
    "job costs":
        "Actual model spend recorded per job, summed. Not an estimate.",
    "job outcomes":
        "What each job finally produced, recorded at completion.",
    "job config":
        "The configuration a job was created with.",
    "run stamps":
        "Timestamps written when a skill actually ran, so a claim of freshness "
        "can be checked rather than trusted.",
    "engine run stamps":
        "Timestamps recorded by the engine on each run.",
    "produced pieces":
        "Counted from pieces the writer actually produced.",
    "published refs":
        "The stored reference returned by the platform when a piece was "
        "published — proof it landed, not an assumption.",
    "the piece":
        "Read from the stored content piece — its real body, headings and "
        "images, not a summary written about it.",
    "the live piece":
        "Read from the published version, as it currently exists online.",
    "post path":
        "The exact URL path a piece was published to, captured at publish "
        "time. It is proof of where the piece actually landed.",
    "previews":
        "Generated from the piece's own content, using the same renderer "
        "that builds the published page.",
    "content plan":
        "Read from the stored content plan — what the strategist decided to "
        "make and why, before anything was written.",
    "strategy brief":
        "The strategist's written brief for this piece, including why it was "
        "chosen.",
    "prompt library":
        "The stored prompt library the engine builds every model call from. "
        "Changing a prompt here changes all future output.",
    "SCHEMAS":
        "The output contracts every skill must satisfy. A schema failure "
        "blocks a piece rather than shipping a malformed one.",
    "orchestrator":
        "The module that runs the pipeline, reporting on its own execution.",
    "scheduler":
        "The scheduler's own record of what it queued and when.",
    "engine":
        "Read from the engine's own internal state. It describes what the "
        "engine believes right now, which a restart can reset.",
    "work orders":
        "Read from recorded work orders — units of work the engine created "
        "for itself, with their current status.",
    "work-order engine":
        "Reported by the module that issues work orders. It counts what was "
        "created, not what was completed.",
    "work-order log":
        "The log of work orders issued and completed.",
    "outcomes":
        "Read from recorded outcomes — what actually happened after an "
        "action, captured at measurement time rather than predicted.",
    "measured outcome":
        "A real result recorded after the fact, not a projection.",
    "learning":
        "The learning module's record of what it has concluded.",
    "learning module":
        "The module that turns outcomes into playbook changes.",
    "experiments":
        "Read from recorded experiments. A result only becomes reliable "
        "after enough runs; a single result is a signal, not a conclusion.",
    "the fix":
        "The fix registry's declaration of what this repair does.",
    "the fix ledger":
        "The log of every fix that has run, including unattended ones.",
    "agents":
        "Reported by the inspector agents that sweep each section on a "
        "cadence. A finding is what an agent observed, with the time it "
        "observed it.",
    "the inspectors":
        "Reported by the inspector agents that sweep each section.",
    "inspector":
        "Reported by this section's inspector agent on its last sweep. If "
        "the sweep has not run recently, the finding may be stale.",
    "decision log":
        "The record of decisions taken, with their timestamps.",
    "session history":
        "Read from recorded dashboard sessions — when this dashboard was "
        "opened and by whom.",
    "audit log":
        "The append-only log of actions taken. Entries are never edited, so "
        "it can be used to reconstruct what happened and when.",
    "signal router":
        "The module that turns raw signals into ranked decisions.",
    "loop map":
        "The measured state of each stage in the publish-measure-learn loop.",
    "dependency map":
        "Which modules depend on which, read from the code itself.",
    "image agent":
        "The image generation agent's own record.",
    "IMAGE_API_KEY":
        "Whether an image API key is present. The key's value is never read "
        "or displayed — only whether one is set.",
    "brand module":
        "Read from your stored brand settings — the names, links and "
        "signature every generated piece inherits.",
    "providers":
        "The model providers configured and reachable.",
    "meters":
        "Usage meters kept per model provider. They are the basis for every "
        "cost figure on this dashboard.",
    "api meters":
        "Recorded API usage counted by the engine as calls were made, not "
        "estimated afterwards from a bill.",
    "API meters":
        "Recorded API usage per provider, used to attribute cost.",
    "api_meters()":
        "A live reading of the usage meters, taken as this page rendered "
        "rather than pulled from a cache.",
    "S5 instruments":
        "The instrumentation layer's own counters.",
    "S5 evals":
        "Evaluation runs and their scores. Evals catch quality drift that "
        "success-or-failure counts cannot see.",

    # --- outreach / leads
    "lead records":
        "Read from stored lead records. A lead only exists here if it was "
        "captured or imported, so this counts your database, not your "
        "market.",
    "lead source stamp":
        "Where each lead came from, stamped at capture.",
    "lead qualifier":
        "The qualifier's scoring of each lead against your ICP.",
    "recorded deals":
        "Deals you recorded. Revenue figures on this dashboard are only as "
        "complete as what has been entered here.",
    "outreach jobs":
        "Read from outreach job records — the engine's own account of what "
        "it prepared, queued and sent.",
    "outreach jobs + outcomes":
        "Outreach jobs joined to what actually happened after sending.",
    "sent stamps":
        "Timestamps written when an email was actually accepted by the mail "
        "server — not when it was queued.",
    "send stamp":
        "The timestamp written when the mail server accepted the message. "
        "It marks delivery to the server, not to an inbox.",
    "send stamps":
        "Timestamps written when the mail server accepted each message. "
        "They mark acceptance, not inbox placement or opens.",
    "sent_at stamps":
        "The recorded send times, used for per-day rates.",
    "per-lead timestamp":
        "The time recorded against each individual lead.",
    "outbox":
        "The outbox — messages prepared but not yet sent.",
    "suppression list":
        "Addresses that must never be contacted. This list overrides every "
        "campaign.",
    "email verifier":
        "The verification result for each address, used to protect sender "
        "reputation.",
    "IMAP":
        "Read from the live mailbox over IMAP — real replies, not predictions.",
    "reply agent":
        "The reply agent's drafts and classifications.",
    "your campaigns":
        "Read from your configured campaigns. Paused and draft campaigns "
        "are included in configuration counts but contribute no activity.",
    "campaign dates":
        "The start and end dates recorded on each campaign.",

    # --- wiring / infrastructure
    "connectors":
        "Read from the connector layer — whether each outside service "
        "actually answered.",
    "connector status":
        "The result of the last connection attempt per service. An old "
        "success is not proof the wire is up right now.",
    "connectors.status()":
        "A live call to every connector, made now.",
    "wire status":
        "Whether each wire is connected, tested live rather than assumed.",
    "CONNECTOR_ENV_KEYS":
        "The full list of credential fields the engine knows about. Presence "
        "is checked; values are never displayed.",
    "credential_audit()":
        "A check of every credential's shape. It reports a problem without "
        "ever echoing the value.",
    "Postgres settings":
        "Read from the settings table in Postgres, which takes precedence "
        "over environment values.",
    "settings":
        "Read from stored settings. Settings in the database take "
        "precedence over values in the environment file.",
    "settings store":
        "The settings store in Postgres. This is the value the engine will "
        "actually use, whatever the environment file contains.",
    "connect form":
        "What has been entered on the Connect screen.",
    "front-end connect":
        "The connection state as the Connect screen reports it.",
    "health probe":
        "A live health check against the running service.",
    "GET /health":
        "A real HTTP call to the health endpoint, made now.",
    "probe history":
        "Past probe results, so intermittent failures are visible rather "
        "than averaged away.",
    "all systems":
        "Rolled up across every subsystem that reports.",
    "degraded mode":
        "Whether the engine is running with reduced capability, and why.",
    "infrastructure":
        "Read from the host and container state — what is genuinely "
        "running, not what the compose file declares.",
    "infra history":
        "Recorded infrastructure events over time, so a one-off incident "
        "can be told apart from a recurring one.",
    "docker":
        "Read from the running Docker containers. A container can be up "
        "while the code inside it is an old build.",
    "deploy":
        "The deployment record — which code is actually running.",
    "BUILD_TAG":
        "The build fingerprint of the code currently serving this page. If "
        "it has not changed, a rebuild did not take effect.",
    "git":
        "Read from the git repository state — the commit actually checked "
        "out on this machine.",
    "your CI":
        "Read from your continuous integration runs.",
    "storage":
        "Disk and object storage usage as the host reports it. Running out "
        "stops writes, including backups.",
    "backup config":
        "The backup configuration as currently set.",
    "runbook":
        "The recorded operational runbook — the written steps for "
        "recovering this system. Untested steps are not recovery.",
    "risk register":
        "The recorded register of known risks. A risk stays listed until it "
        "is deliberately closed, not until it stops being mentioned.",
    "risk history":
        "How the risk register has changed over time, so a risk that keeps "
        "reopening is visible as a pattern.",
    "monthly snapshots":
        "Point-in-time snapshots taken each month.",
    "DASHBOARD_PASSWORD":
        "Whether a dashboard password is set. The value is never read or "
        "shown.",
    "tracking":
        "Whether analytics tracking is installed and firing.",
    "SGA":
        "Read from the Sales & Growth agent's records.",
})


# ---- SOURCES BUILT AT RUNTIME -------------------------------------------
# 26 cards build their src from an expression, so a static scan of the board
# files cannot see them. They were found by rendering the whole dashboard and
# reading back every token that reached a card. verify_rendered() re-runs that
# check, so this set cannot silently drift either.

_add("declared", {
    "not connected":
        "There is no wire to this service, so there is nothing to read. This "
        "is an absence of measurement, not a measurement of zero.",
    "not started":
        "This has not begun. Nothing has been measured because nothing has "
        "run yet.",
    "not available":
        "This measurement cannot be taken right now, and the card says so "
        "rather than showing a zero that would read as a real result.",
    "not enough history":
        "There are too few past runs to say anything reliable. A number here "
        "would be noise presented as a trend.",
    "legal":
        "A legal or regulatory obligation. It applies regardless of what the "
        "numbers say, and performance cannot excuse it.",
    "operational":
        "An operational rule about how this system is meant to be run. It is "
        "a standard held, not an outcome measured.",
    "S1 judge":
        "Scored by the judge module — a model grading output against written "
        "criteria. It is a considered opinion, not a measurement.",
    "site taxonomy":
        "Your declared site structure — the categories and types you chose. "
        "Changing it re-labels history rather than improving it.",
})

_add("computed", {
    "computed from Search Console":
        "Worked out from Search Console figures rather than read directly, so "
        "it inherits Search Console's 2-3 day lag.",
    "crawl × Search Console":
        "Your crawl joined against Search Console, so pages you publish and "
        "pages Google actually indexed can be compared directly.",
    "crawler + keywords":
        "Your crawl joined to the keyword set, showing which target terms "
        "have a page behind them and which do not.",
    "own crawler + ad copy":
        "Your page content compared against your live ad copy, so a promise "
        "made in an ad can be checked against the landing page.",
})

_add("measured", {
    "database":
        "Read directly from the database. It is the engine's own record, and "
        "it is current as of this page load.",
    "rank tracker":
        "Recorded positions from the rank tracker. Rankings are personalised "
        "and volatile, so treat a single reading as a sample.",
    "site structure":
        "Read from the actual structure of your site as crawled — the pages "
        "that exist and how they link to each other.",
    "site content":
        "Read from the real text on your pages, as fetched.",
    "GSC + Serper":
        "Search Console joined to live search results, so your own reported "
        "performance sits next to what the page actually shows.",
    "GSC + Serper ":
        "Search Console joined to live search results.",
    "Search Console query×page":
        "Search Console broken down by query and page together, which shows "
        "which specific page is earning each term.",
    "Serper + fetch":
        "Live search results joined to a direct fetch of the pages found.",
    "Serper + crawler":
        "Live search results joined to your own crawl.",
    "Serper prospecting":
        "Prospect records discovered through live search.",
    "prospecting":
        "Read from prospecting runs — organisations found, before any "
        "qualification has been applied.",
    "outreach engine":
        "Reported by the outreach engine about its own work.",
    "link pitch agent":
        "Reported by the link pitch agent — pitches prepared and their "
        "current state.",
    "IMAP reply agent":
        "Reported by the reply agent, which reads the live mailbox and "
        "classifies what came back.",
    "placement verifier":
        "The verifier that checks whether a promised placement actually went "
        "live, rather than trusting that it did.",
    "SEO fixer":
        "Reported by the SEO fixer about repairs it attempted and their "
        "result.",
    "cost meter":
        "The running cost meter, incremented as each call is made rather "
        "than reconstructed from a bill later.",
    "PageSpeed":
        "Measured page performance. Scores vary between runs, so a single "
        "point is less meaningful than a trend.",
    "wire_all()":
        "A live test of every wire, run now. It reports what actually "
        "answered, not what is configured.",
    "_env()":
        "The credential resolver, reporting which source a value came from. "
        "Values themselves are never read or displayed.",
    "selftest":
        "The engine's own self-test, run against the live process. It proves "
        "the code that is actually serving this page still works.",
    "S7 chassis":
        "The version and integrity layer, reporting which code is actually "
        "running and whether it matches what was deployed.",
})

_add("navigation", {
    "/disconnect":
        "Removes a stored credential. The engine falls back to the "
        "environment file if a value is there.",
})


# ---------------------------------------------------------------- where a link goes
# 71 cards exist only to send you somewhere, and none of them said where or
# what would be there when you arrived - "just a button which redirects me to
# the other page without proper explanation". There are 21 destinations, not
# 71, so this is written once per place rather than once per button.

DESTINATIONS = {
    "system": "System & Wiring — whether the engine is running, which "
              "credentials are connected, what each wire costs and what broke.",
    "appr": "The approval queue — every piece and every email waiting for a "
            "human decision, with its full record attached.",
    "cockpit": "The AI Cockpit — every system's signal turned into one ranked "
               "list of decisions that need you.",
    "seo": "The SEO section — crawl results, indexing, rankings, answer-engine "
           "visibility and the fixes waiting to be applied.",
    "content": "The Content Factory — what is planned, what is written, what "
               "is waiting for approval, and the preview of each.",
    "cfimage": "The image side of the Content Factory — which pieces have "
               "images, which failed, and why.",
    "cfqa": "The quality gate inside the Content Factory — what QA flagged on "
            "each piece before it could publish.",
    "riskinfra": "Risk & Infrastructure — backups, exposed credentials, "
                 "container health and everything that could stop the engine.",
    "bi": "Business Intelligence — demand, pipeline, revenue and whether the "
          "unit economics actually work.",
    "leads": "The lead database — who has been sourced, who qualified against "
             "your ICP, and where each came from.",
    "email": "The email outbox — what is drafted, what has been sent, what "
             "replied, and what is waiting for your approval to go.",
    "outreach": "Leads & Outreach — sourcing, sequences, replies and bookings "
                "in one place.",
    "media": "Media Buying — campaigns, spend, keywords and what the paid "
             "money actually bought.",
    "budget": "The budget controls — the caps in force, what has been spent "
              "against them, and how much headroom is left.",
    "finance": "The money view — costs, revenue and margin across everything "
               "the engine does.",
    "sales": "The sales view — deals recorded, their stage and their value.",
    "sga": "The Social & Growth agent — what is posted, to which channels, "
           "and what it produced.",
    "agents": "The agent roster — which inspector agents exist, what each is "
              "contracted to check, and when each last ran.",
    "learn": "The learning module — what the engine concluded from measured "
             "outcomes and what it changed in the playbook as a result.",
    "map": "The system map — how every module connects, drawn from the code "
           "rather than from a diagram someone maintained by hand.",
    "mission": "The mission view — the goals the engine is working towards "
               "and how far along each is.",
}


def destination_of(links_html) -> str:
    """What is on the other side of this card's link, if it has one.

    Derived from the nav() target already in the button, so a card gains this
    without being edited. Returns "" when the card does not navigate.
    """
    import re
    m = re.search(r"nav\(['\"](\w+)['\"]", str(links_html or ""))
    if not m:
        return ""
    return DESTINATIONS.get(m.group(1), "")


# ---------------------------------------------------------------- lookup

def classify(src) -> dict:
    """What kind of number is this. NEVER raises — an unknown source degrades
    to an explicit 'unclassified' rather than a crash or a false claim."""
    token = str(src or "").strip()
    cls, why = SOURCES.get(token, ("", ""))
    if not cls:
        cls = "navigation" if not token else "unclassified"
        why = (CLASSES[cls][2] if cls == "navigation"
               else f"No evidence entry for the source {token!r}.")
    label, colour, meaning = CLASSES[cls]
    return {"cls": cls, "label": label, "colour": colour,
            "meaning": meaning, "why": why, "token": token}


def is_evidence(src) -> bool:
    """True only for classes that represent an actual observation."""
    return classify(src)["cls"] in ("measured", "computed")


# ---------------------------------------------------------------- the gate

def authored_tokens() -> dict:
    """Every src literal authored in a board file, counted. Static — it does
    not depend on runtime context, which is what makes it trustworthy."""
    import ast
    import glob
    import io
    import collections
    found = collections.Counter()
    for path in sorted(glob.glob("content_engine_*boards.py")):
        try:
            tree = ast.parse(io.open(path, encoding="utf-8").read())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Tuple) and len(node.elts) == 8:
                el = node.elts[5]
                if isinstance(el, ast.Constant):
                    val = str(el.value or "").strip()
                    if val:
                        found[val] += 1
    return dict(found)


def verify_rendered(html: str) -> tuple:
    """(ok, problems) for a REAL rendered dashboard.

    The static scan cannot see a src built from an expression. This reads the
    tokens that actually reached a card, so the 26 dynamic ones are covered by
    the same standard as the 208 authored ones.
    """
    import re
    import collections
    import html as _html
    found = re.findall(r"<h4>Where it comes from</h4><p><b>([^<]*)</b>", html)
    bad = collections.Counter()
    for raw in found:
        token = _html.unescape(raw).strip()
        if token and classify(token)["cls"] == "unclassified":
            bad[token] += 1
    problems = [f"rendered src {t!r} on {n} card(s) has no evidence entry"
                for t, n in bad.most_common()]
    return (not problems), problems


def verify() -> tuple:
    """(ok, problems). Every authored token must be classified."""
    problems = []
    authored = authored_tokens()
    missing = sorted(t for t in authored if t not in SOURCES)
    for t in missing:
        problems.append(f"src {t!r} on {authored[t]} card(s) has no evidence entry")
    for token, (cls, why) in SOURCES.items():
        if cls not in CLASSES:
            problems.append(f"src {token!r} has unknown class {cls!r}")
        if len(str(why).strip()) < 40:
            problems.append(f"src {token!r} explanation is too short to be useful")
    return (not problems), problems


if __name__ == "__main__":
    ok, problems = verify()
    authored = authored_tokens()
    print(f"authored tokens : {len(authored)} distinct, "
          f"{sum(authored.values())} cards")
    print(f"classified      : {len(SOURCES)}")
    import collections as _c
    dist = _c.Counter(c for c, _ in SOURCES.values())
    for cls in ORDER:
        if dist.get(cls):
            cards = sum(authored.get(t, 0) for t, (c, _) in SOURCES.items()
                        if c == cls)
            print(f"  {CLASSES[cls][0]:<14} {dist[cls]:>4} tokens  "
                  f"{cards:>5} cards")
    print()
    if ok:
        print("PASS - every authored source is classified and explained")
    else:
        print(f"FAIL - {len(problems)} problem(s)")
        for p in problems[:40]:
            print("  ", p)
        raise SystemExit(1)

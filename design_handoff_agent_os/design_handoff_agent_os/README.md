# Handoff: Agent OS — Marketing/Commerce/Leads/Web Control Surface

## Overview
A unified "Mother OS" for running marketing, commerce, leads, and web/data operations through AI employee-agents. One control surface lets a manager see every platform's real data (Amazon FBA, Shopify, Shopware, Meta, TikTok, etc.), and command agents directly from the UI. A root **Cockpit** sits above 6 department modules, each department has its own desks, and every desk carries a reusable **Command & Chat panel** for instructing that department's agent and approving/rejecting its proposed actions.

## About the Design Files
The bundled file is a **design reference built in HTML** (a Design Component / `.dc.html` file) — it is a working, click-through prototype showing intended structure, data, and behavior, **not production code to copy directly**. The task is to **recreate these screens in your target codebase's actual stack** (React, Vue, native, etc.) using your existing component library and patterns — or choose the most appropriate framework if none exists yet. Treat the interactivity here (state toggles, approve/reject, live chart mutation) as the *spec* for what must work, not as code to port.

## Fidelity
**Mid-fidelity wireframe**, not pixel-final. Structure, data model, navigation, and interaction logic are all intentional and should be followed closely. Colors/type follow the bound **Industry** design system (steel-blue accent, Barlow Condensed/Barlow, square-cornered "blueprint" cards with corner registration marks — see Design Tokens below) but exact spacing/sizing should be adapted to your component library rather than measured pixel-for-pixel.

## How to view it
Open `Agent OS Wireframes.dc.html` in a browser. It is a single scrollable canvas ("options/canvas" doc mode) — each numbered turn (`t8`–`t14`) is a department; each lettered screen inside it (e.g. `13a`) is one view. Anchor-jump via the visible `NNa` badges or the in-app sidenavs. `<meta name="design_doc_mode" content="canvas">` enables pan/zoom in the Claude environment; a plain browser just scrolls.

## System structure
- **Cockpit (turn 14)** — the root control tower, sits above all departments.
  - `14a` Cockpit Home — 6 department control cards (state pill: running/paused/attention/stopped + Open/Pause/Start/Stop), Emergency Stop All, a system-wide command chat to the Orchestrator.
  - `14b` Unified Approval Queue — every department's pending approvals in one inbox; pink (spend/deploy/DNS) items never batch-approve.
  - `14c` All-Agents Grid — every employee-agent across all departments, click a chip to start/stop it.
  - `14d` System Health & Activity — spend-by-department chart + one audit log.
  - `14e` System Control Room — global autonomy default, budget cap, the 5 permanent gates (spend/publish/send/deploy/cross-module command) that can never be turned off, schedules/permissions.
- **Module 6 — Web & Data Core (turn 13, `13a`–`13k`)** — web-maintenance dept (Developer, Infra/SRE) + the data hub/orchestration core (Integrations, Data Steward, Orchestrator), plus Analytics, a Tool Connection Hub (plug-and-play API credentials with cost meter and n8n-style workflow loops), a Health & Risk Monitor (per-agent pulse + risk list), and a Connector/API Map (every tool wired into one normalize/HUB node).
- **Module 5 — Leads & Outreach (turn 12, `12a`–`12i`)** — Command Center, Prospector, Data Cleaner (EU region-gated), Qualifier, Outreach Writer, Sender/Tracker (compliance + manual send gate), Sources & Control, Email Campaign Board (ESP vs. platform-native API), Customer Segmentation Board (with CSV/XLSX/JSON import/export).
- **Module 4 — Commerce (turn 11)** — inventory, pricing, merchandising, promotions, lifecycle, plus per-channel native dashboards (Amazon FBA/FBM, Shopify, WooCommerce, Shopware 6, Facebook/Instagram Shop, TikTok Shop).
- **Module 3 — Marketing/Content (turn 9)**, **Module 2 — SEO/AEO/GEO (turn 8)**, **Product Publisher (turn 10)** — supporting departments.

## The reusable Command & Chat panel (build this once, reuse everywhere)
Every desk carries the same panel (`.cmdchat` in the CSS):
- **Header**: names the specific agent in scope (e.g. "🗄 Data Steward") — commands never leak to the wrong agent.
- **Chat transcript**: natural-language back-and-forth between manager and that agent.
- **Pending actions**: each a concrete proposed action with inline Approve/Reject. Approving a pink (consequential) action should still hit that module's own confirm gate — this prototype short-circuits that for demo purposes (approving directly mutates state), but production must keep the second gate.
- **Quick actions**: 3–5 desk-specific one-click presets that prefill the command bar.
- **Command bar**: free-text input + Send, always scoped to the one agent in the header.
- Every card/section throughout the product also has a small "💬 Command" button that prefills the command bar with that section's context.

## Interactions & Behavior implemented in the prototype (treat as required behavior)
- Clicking a platform/channel chip (e.g. "Amazon FBA" vs "Shopify") swaps the entire dashboard's data/charts underneath it — not just a visual toggle.
- Approving a pending action in a Command & Chat panel actually mutates the relevant data elsewhere on screen (e.g. approving "Reconnect Shopware" flips that connector's status dot green in 3 different places: the connections table, the data-flow map, and the connector/API map's line color).
- Region gating: the Leads Data Cleaner hard-blocks EU leads from outreach.
- Send gates: Sender/Tracker requires a manual send confirmation and a compliance checklist pass before any bulk send fires.
- Tool Connection Hub: each tool card holds two credential fields (id/key + secret) and a live Connect/Disconnect toggle; connecting/disconnecting should update that tool's status dot everywhere it's referenced (Integrations desk, Health & Risk pulse, Connector Map).
- Health & Risk pulse: status (ok/warn/down) per agent should be computed from real upstream state (e.g. VPS CPU thresholds, connector status), not a hardcoded label.

## State Management
Key state groups a real implementation will need:
- Per-department module state: `running | paused | attention | stopped`.
- Per-agent state: `running | stopped` (32 agents across 6 departments).
- Per-tool connection state + credentials (WordPress, Shopify, Shopware 6, Meta, TikTok, Google OAuth, Google Drive, GA4, SMTP, Klaviyo, LinkedIn…).
- A single unified approvals queue (cross-department), each item: source, target, impact, pink/non-pink (consequential) flag.
- Per-desk chat log + pending-actions list + free-text draft.
- Global settings: autonomy default (propose vs. auto-safe-only), budget cap, the 5 permanent gates (always on), quiet hours/schedules.

## Design Tokens (Industry design system)
- **Color**: light ground `#f2f2f3`, text `#1d1f20`, single steel-blue accent `#5980a6` — each role has a 100–900 OKLCH tonal ramp. Danger/pink actions (deploy, DNS, scale, stop) use a separate danger ramp added for this project (`--color-danger-500/600/700`).
- **Type**: Barlow Condensed for headings, Barlow for body.
- **Shape language**: square corners everywhere, no rounding. Cards/buttons/figures are "blueprint" objects — hairline border + 4 corner `+` registration marks (`.blueprint` class + `<i class="corner tl/tr/bl/br">` children). The primary button is the one solid accent-filled object.
- **Components used**: `.btn` (`.btn-primary/.btn-secondary/.btn-ghost/.btn-danger`), `.tag`, `.card`, `.table` (`.pf-table`), form `.field`/`.input`/`.radio`.
- Full token sheet: `_ds/industry-*/styles.css` (linked in the file's `<helmet>`). Do not hand-pick colors outside these ramps.

## Assets
No photographic or icon assets — all icons are emoji placeholders standing in for a proper icon set (Lucide, per the Industry design system, stroke-width 1.5) that should be swapped in during implementation. All charts (bars, donuts, funnels, the connector map's SVG lines) are hand-built with divs/SVG, not a charting library — implementation should use your standard charting library and only match the shown chart types (bar, donut, funnel, scatter, line, gauge) and data shape.

## Files
- `Agent OS Wireframes.dc.html` — the full prototype, all screens.
- `_ds/industry-*/` — the bound Industry design system (stylesheet + token source `theme.json` + component reference pages).

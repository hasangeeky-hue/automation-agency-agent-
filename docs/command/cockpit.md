# Screen contract: Command Cockpit

Spec section 101. This file exists BEFORE the screen. If it is deleted,
`content_engine_command_ui.check_contract()` fails the build.

## Purpose

One command interface above every OS. It reduces decision time: it
surfaces only important state, change, risk, opportunity, failure, cost
and decision, and routes action to the OS that owns execution. It is
not another analytics dashboard and duplicates no domain table.

## User questions

How is my company doing? How is my machine doing? What changed? Why?
What is broken? What am I losing money on? Where is my opportunity?
What should I approve? What can I fix right now?

## Information hierarchy

1 current state, 2 exceptions, 3 decisions, 4 actions, 5 verification.
Historic detail lives in the domain OS behind a deep link.

## Layout

Top command bar (workspace, period, data health, system health, cost
today), then an incident strip when a P0/P1 exists, then the command
canvas: Business Pulse (full width), What Changed beside Machine Pulse,
Decision Queue beside Quick Fix, Loop Monitor beside Initiatives, Cost
Pulse beside Data Health, and the Commander panel on the right.

## Components

BusinessPulse, MachinePulse, ChangeFeed, DecisionQueue, DecisionCard,
QuickFixCard, LoopCard, InitiativeCard, IncidentStrip, CostPulse,
DataHealthBar, RootCauseChain, CommanderPanel, execution status chain.

## Data sources

BI OS (revenue, contribution, CAC, waterfall), Media Buying OS
(campaign performance), Content Factory (loop state), SEO OS (organic
signals), System Control Plane (component health, loops, incidents),
BI Cost OS (spend, waste, budgets). The cockpit reads snapshots, never
twenty provider APIs at render.

## Metrics

Every KPI carries polarity from the metric registry: revenue up is
good, CAC up is bad, spend up is neutral. Higher is never automatically
good.

## State model

command_state_snapshots: business_state, system_state, cost_state,
risk_state, opportunity_state, decision_state, data_health,
system_health, timestamp.

## Actions

Approve, modify or reject a decision; apply a quick fix; open a domain
OS. The cockpit never calls Meta, WordPress or a provider directly:
every action routes through the Action Router to the owning OS.

## Risk rules

Decision cards missing any contract field are DECISION_INCOMPLETE and
cannot be approved. Ranking uses impact, urgency, risk, confidence,
cost and effort, never severity alone.

## Quick-fix rules

SAFE, APPROVAL_REQUIRED or HIGH_RISK. A fix must show current state,
proposed state, affected components, risk, downtime, cost, rollback and
verification. A bare [Fix] button is forbidden.

## Agent context

ONE Commander agent. It reads structured snapshots, separates FACT,
INFERENCE and RECOMMENDATION, returns at most five ranked actions, and
may never execute a domain operation itself.

## Loading

The canvas renders from the last snapshot instantly; freshness is shown
per section.

## Empty

A zone with no data says what feeds it and that silence is not health.

## Error

A failing zone renders its error inside its own panel; the rest of the
cockpit survives.

## Partial data

Delayed sources are named ("Paid totals contain delayed TikTok
metrics") and affected decisions show CONFIDENCE REDUCED.

## Permissions

Approvals and quick fixes respect the role model; destructive
operations are never exposed to the Commander.

## Deep links

Every insight links to the owning OS: SEO, Media Buying, Content
Factory, Email, CRM, BI, System Control. The cockpit never rebuilds
their detail.

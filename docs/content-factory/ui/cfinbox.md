# Screen contract: 02 Inbox

Spec section 100. This file exists BEFORE the screen does. If it is
deleted, `content_engine_factory_boards.check_screens()` fails the build.

## Purpose

Where every external OS signal arrives, normalized. The factory observes nothing itself; this screen shows what other systems observed.

## User question

What did the other systems observe, and does it matter?

## Layout

tab strip, sort control, then one card per signal

## Components

source tabs, priority band, evidence list, suggested formats, confidence, signal drawer

## Data

content_signals rows, normalized by FOS.normalize_signal()

## Data source

SEO_OS, MEDIA_BUYING_OS, EMAIL_OS, CRM_OS, SOCIAL_OS, ANALYTICS_OS, MANUAL, EXTERNAL_TOOL, via the event bus

## Actions

filter by source, open the drawer, dismiss

## CTA

[Create Plan] human, [Dismiss] destructive

## AI actions

[Analyze Inbox] clusters and ranks; it does not accept anything

## Loading

cards render in priority order as they arrive

## Empty

names the systems signals come from, so the reader knows whether this is quiet or disconnected

## Error

an unknown source is kept and marked, never dropped

## Permissions

VIEWER may read; CREATE_CONTENT to create a plan

## State transitions

NEW to REVIEWED to ACCEPTED or DISMISSED; EXPIRED by time

# Screen contract: 08 Performance

Spec section 100. This file exists BEFORE the screen does. If it is
deleted, `content_engine_factory_boards.check_screens()` fails the build.

## Purpose

Answer what to make more of. Section 61 forbids replicating GA4 or the Media Buying dashboard.

## User question

What content, format and hook should we make more of?

## Layout

filters, KPI row, content table, then learning beside the result rules

## Components

KPI cards, content table with a Result column, learning list, the classification key

## Data

content_performance_daily, content_learning

## Data source

the execution systems, imported through /content/performance/import

## Actions

filter by channel, format, campaign and window

## CTA

[Use in Planner] secondary

## AI actions

the Performance agent writes learning; it cannot create content

## Loading

totals render once all rows are in, never partially summed

## Empty

says nothing can be learned until something was measured

## Error

a missing baseline or too small a sample returns INSUFFICIENT_DATA, never NORMAL

## Permissions

VIEWER may read

## State transitions

a variant receives WINNER, STRONG, NORMAL, WEAK or INSUFFICIENT_DATA

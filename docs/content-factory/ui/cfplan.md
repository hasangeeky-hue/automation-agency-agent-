# Screen contract: 03 Planner

Spec section 100. This file exists BEFORE the screen does. If it is
deleted, `content_engine_factory_boards.check_screens()` fails the build.

## Purpose

Turn accepted signals into a dated plan. The planner drafts; a human accepts, edits or rejects. It never schedules on its own.

## User question

What are we making, and when?

## Layout

mode switch (Week/Month/Campaign), day columns, then a table

## Components

mode buttons, day cards, plan table with a Why column

## Data

content_plans and content_plan_items

## Data source

the Planner agent, seeded from signals and content_learning

## Actions

accept all, accept selected, edit, reject

## CTA

[Add Content] human, [AI Plan Week] AI

## AI actions

the Planner returns a DRAFT plan with a reason per item; auto-scheduling is off because it would make every later approval decorative

## Loading

the draft appears item by item

## Empty

explains that a plan comes from accepted signals

## Error

an item with no channel says 'not set' rather than guessing

## Permissions

CREATE_CONTENT to add; EDITOR to accept a plan

## State transitions

DRAFT to REVIEWED to APPROVED to ACTIVE to COMPLETED

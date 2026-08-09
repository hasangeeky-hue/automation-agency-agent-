# Screen contract: 01 Command Center

Spec section 100. This file exists BEFORE the screen does. If it is
deleted, `content_engine_factory_boards.check_screens()` fails the build.

## Purpose

Answer five operational questions at a glance: what needs attention, what should we create, what is in production, what needs approval, what recently performed. Section 14 forbids recreating GA4 here; the counters are workflow counters.

## User question

What needs my attention, and what should we make next?

## Layout

Header, then a five-counter row, then two columns: WHAT SHOULD WE CREATE beside WORKFLOW, then NEEDS REVIEW beside RECENT LEARNING.

## Components

counter row, signal cards, workflow list, review list, learning list, loop state line

## Data

counts.inbox/production/review/ready/published, signals[], needs_review[], learning[], loop_counts{}

## Data source

counts and signals from the factory store; learning from content_learning; loop_counts derived in boards.enrich()

## Actions

open a signal, open the review queue, open performance

## CTA

[Create Content] human, [Build Plan] AI

## AI actions

Build Plan runs the Planner agent and returns a DRAFT

## Loading

counters render as skeleton rows; no zeros are shown

## Empty

if no signal is actionable the panel says the factory will not invent a topic to fill a week

## Error

a failing renderer prints the exception and the rest survives

## Permissions

VIEWER and above may read; CREATE_CONTENT to use Create

## State transitions

none; this screen only navigates

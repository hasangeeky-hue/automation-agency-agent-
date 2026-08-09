# Screen contract: 06 Review

Spec section 100. This file exists BEFORE the screen does. If it is
deleted, `content_engine_factory_boards.check_screens()` fails the build.

## Purpose

A dedicated approval queue so a reviewer never has to open the Studio.

## User question

Is this good enough to go out?

## Layout

three columns: QUEUE | PREVIEW | CHECKS and COMMENTS

## Components

queue list, block preview, QA check list, comments

## Data

approval_requests, qa_reviews, comments

## Data source

the QA agent plus the deterministic validators

## Actions

comment, request changes, reject, approve

## CTA

[Reject] destructive, [Request Changes] [Approve] human

## AI actions

QA recommends; it cannot approve. Section 54: AI is never the final approver.

## Loading

the preview renders before the checks finish

## Empty

says drafts arrive here after QA runs

## Error

approving over a FAIL is allowed and recorded in the audit log as approving over a known failure

## Permissions

REVIEW_CONTENT to comment; APPROVE_CONTENT to approve

## State transitions

REVIEW to CHANGES_REQUESTED or APPROVED. APPROVED requires a human actor and a named approver.

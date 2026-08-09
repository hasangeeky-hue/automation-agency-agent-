# Screen contract: 04 Studio

Spec section 100. This file exists BEFORE the screen does. If it is
deleted, `content_engine_factory_boards.check_screens()` fails the build.

## Purpose

Write one content item with the brief and the evidence in view. Section 24: chat is not the main UI.

## User question

How do I write this, without leaving the screen?

## Layout

three panes: CONTEXT | CONTENT WORKSPACE | AI COPILOT

## Components

brief tab, data tab, typed blocks, lock indicators, copilot actions, version list, diff view

## Data

master_content, content_blocks, content_versions, assets

## Data source

the factory store; evidence carried from the source signal

## Actions

edit a block, lock a block, compare, restore, preview

## CTA

[Save] [Preview] [Send to Review] human

## AI actions

Generate Draft, Rewrite, Improve Hook, Shorten, Expand, Create Variants, Generate Image, Adapt Platform, Create Video Concept. Block-scoped actions require a selection.

## Loading

autosave state is shown in the header

## Empty

offers a first draft against the brief

## Error

a locked block refuses an agent edit and says a human must unlock it

## Permissions

EDIT_CONTENT to write; GENERATE_ASSET for the tool actions

## State transitions

IDEA to BRIEF to PRODUCTION to REVIEW. AI_GENERATED is not a state: generation happens inside PRODUCTION.

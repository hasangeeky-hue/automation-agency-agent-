# Screen contract: 09 Settings

Spec section 100. This file exists BEFORE the screen does. If it is
deleted, `content_engine_factory_boards.check_screens()` fails the build.

## Purpose

Brand, connections, tools, workflow and permissions.

## User question

How is this factory configured?

## Layout

stacked sections, each a card or a table

## Components

brand fields, capability matrix, workflow gates, role grid, boundary list

## Data

brands, workflow settings, credential PRESENCE only

## Data source

the settings store; credential values are never read here

## Actions

edit brand, choose providers, set workflow gates

## CTA

[Connect] human

## AI actions

none

## Loading

the capability matrix resolves per row

## Empty

an unconfigured brand is called out, because QA then cannot check tone

## Error

an unavailable capability names the credential that is missing

## Permissions

MANAGE_BRAND and MANAGE_TOOLS

## State transitions

none

# Screen contract: 07 Distribution

Spec section 100. This file exists BEFORE the screen does. If it is
deleted, `content_engine_factory_boards.check_screens()` fails the build.

## Purpose

Hand an approved package to the OS that owns execution. The factory supplies creative and nothing else.

## User question

Where did it go, and did the destination take it?

## Layout

state tabs, an ownership table, then the package table

## Components

destination map, package rows, external object ids

## Data

distribution_packages

## Data source

build_package() plus the destination's reply

## Actions

retry a failed package, open the external object

## CTA

[Send to Distribution] human

## AI actions

none; distribution is forbidden to every agent

## Loading

packages appear as READY before any reply

## Empty

says approved content becomes a package here

## Error

ACCEPTED is shown as SENT, never as PUBLISHED: a destination receiving a package is not the same as publishing it

## Permissions

DISTRIBUTE_CONTENT

## State transitions

READY to SENT or SCHEDULED to PUBLISHED or FAILED/REJECTED

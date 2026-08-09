# Screen contract: 05 Library

Spec section 100. This file exists BEFORE the screen does. If it is
deleted, `content_engine_factory_boards.check_screens()` fails the build.

## Purpose

Find, upload, generate and reuse assets. Not a full DAM.

## User question

Where are the assets, and where are they used?

## Layout

tab strip, search and filters, then an asset table

## Components

asset rows with type, dimensions, source, usage, status

## Data

assets and asset_versions

## Data source

uploads and the tool router's generated assets

## Actions

upload, generate, open detail, pick for a block

## CTA

[Upload] human, [Generate] AI

## AI actions

Generate routes to a CAPABILITY, never to a named vendor

## Loading

thumbnails resolve after the row

## Empty

says this is a working library rather than a DAM

## Error

an unavailable capability names the missing credential and does not fake an asset

## Permissions

GENERATE_ASSET to create; VIEWER to browse

## State transitions

an edit creates an asset_version; the original is untouched

# Screen contract: backlinks_overview

Generated from content_engine_search_tokens.CONTRACT_FIELDS.
Spec section 96: no screen may be implemented without this.

## PURPOSE
The external link profile and its trend.

## USER QUESTIONS
Are we gaining or losing referring domains?

## USER DECISIONS
Whether link acquisition is needed.

## DATA
declared per board; no screen invents a field

## DATA SOURCE
Search Console / GA4 / crawler / rank tracker, named per metric on the screen (spec 73)

## METRICS
from the metric registry only; ratios computed from sums, never averaged (spec 101)

## FILTERS
the global context bar: project, domain, country, language, device, date, compare, segment (spec 7)

## COMPONENTS
DataTable, MetricCard, TrendChart, EmptyState, ErrorState, AgentPanel (spec 97)

## CHARTS
each chart declares question, metric, dimension, granularity, comparison and source (spec 68)

## TABLES
sortable, filterable, column-selectable, exportable, with drilldown (spec 66)

## CTA
blue for user actions, purple for AI actions (spec 10)

## AI ACTIONS
analyse, generate fix, optimise; never publish directly (spec 80)

## EMPTY STATE
names the reason and offers the corrective action (spec 71)

## LOADING STATE
skeleton with the data source named

## ERROR STATE
names the cause and the fix, never 'something went wrong' (spec 72)

## PERMISSION STATE
read-only users see data and no write CTA

## DRILLDOWN
row click sets the global context and opens the detail (spec 45)

## LOOP CONNECTION
Informs difficulty on ranking initiatives.


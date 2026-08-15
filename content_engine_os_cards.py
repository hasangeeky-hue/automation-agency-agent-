# -*- coding: utf-8 -*-
"""Which screens draw a chart card and an activity list, and what he
titled them. From Agent OS Wireframes.dc.html.

THE TITLES ARE HIS. THE NUMBERS ARE NEVER HIS.

A chart title is a label, so copying it is fidelity. The dq cards in
his file are placeholder DATA ("Shopware sync degraded", "token
expired 41m ago", "pulled 320 new leads"). Copying those onto a live
dashboard would not be fidelity, it would be a fabricated alert about
a system that is fine. So his dq cards give the SHAPE, which screens
carry an activity list, and the engine supplies every word of the
content, or says plainly that it has none.

A chart whose series nothing feeds renders as NOT MEASURED rather
than as an empty box or a zero line. That is the point: the screens
he designed now show him exactly which data his engine still lacks.
"""

CHARTS = {
    '8d': (
        'Content score , current vs target',
    ),
    '8h': (
        'Cost used this cycle',
    ),
    '9h': (
        'Cost used this cycle',
    ),
    '12a': (
        'Conversion funnel , scrape to book',
        'Lead source mix',
        'Lead score distribution (0,100)',
        'Reply rate by segment',
    ),
    '12c': (
        'Email verify , ⟨EMAIL-VERIFY⟩',
    ),
    '12d': (
        'Score distribution',
        'Score vs company size',
    ),
    '12f': (
        'Opens -> clicks -> replies',
        'Subject A vs B , open rate',
    ),
    '12h': (
        'Recipients per campaign',
    ),
    '12i': (
        'Customer lifecycle mix',
        'Leads collected , by source',
    ),
    '13b': (
        'Ingest volume , last hour',
    ),
    '13c': (
        'Schema completeness , all entities',
        'Field-level quality by entity',
    ),
    '13e': (
        'VPS utilization , live',
    ),
    '13g': (
        'Traffic , last 7 days GA , live',
        'Revenue by channel Shopify+Shopware , live',
        'Session -> cart -> order funnel GA+Shopify , live',
    ),
    '13i': (
        'Tool spend , this cycle',
        'Spend by department',
    ),
    '14a': (
        '📋 Today across the company',
    ),
}

#: screens where he drew an activity list. The COUNT of his cards is
#: kept only as the shape he expected, never rendered as content.
DQ_SHAPE = {
    '8a': 8,
    '8e': 1,
    '8f': 1,
    '9a': 7,
    '9b': 1,
    '9f': 1,
    '11a': 9,
    '11g': 3,
    '12a': 6,
    '12f': 1,
    '13a': 8,
    '13c': 1,
}


def charts_for(sid):
    """His chart titles for one screen, or ()."""
    return CHARTS.get(str(sid), ())


def has_activity(sid):
    """Did he draw an activity list on this screen?"""
    return str(sid) in DQ_SHAPE

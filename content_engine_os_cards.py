# -*- coding: utf-8 -*-
"""Chart cards and activity lists, from his FINAL revised wireframe.

THE TITLES ARE HIS. THE NUMBERS ARE NEVER HIS. A chart title is a
label, so copying it is fidelity; his dq cards are placeholder DATA,
so copying those would put a fabricated incident on a live dashboard.
His cards give the SHAPE; the engine supplies every word of content,
or says plainly that it has none.
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
    '13e': 1,
    '13f': 1,
    '15c': 1,
}


def charts_for(sid):
    """His chart titles for one screen, or ()."""
    return CHARTS.get(str(sid), ())


def has_activity(sid):
    """Did he draw an activity list on this screen?"""
    return str(sid) in DQ_SHAPE

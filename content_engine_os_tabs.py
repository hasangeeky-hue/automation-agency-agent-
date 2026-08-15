# -*- coding: utf-8 -*-
"""His in-screen tab strips: the nine desks that split into views.

From the DESK config in Agent OS Wireframes.dc.html. A desk like the
Technical Engineer is ONE screen holding five views (Crawl, Speed, Index,
Schema, Redirects). Rendering it as one flat board loses the structure he
drew and buries four views out of five.

Labels are his, with two edits: em-dashes normalised, and placeholder
COUNTS stripped. He wrote a tab as "This page (68)"; the 68 is invented
sample data, and a fake number on a tab is still a fake number. The tab
CONTENT is not copied at all, for the same reason his activity cards
were not: his rows say things like "Missing schema markup, 31 pages",
and putting that on a live dashboard invents a finding.
"""

TABS = {
    '8b': (
        'Crawl',
        'Speed / CWV',
        'Index',
        'Schema',
        'Redirects',
    ),
    '8c': (
        'Rankings',
        'AI Citations',
        'Local (GEO)',
        'Reports',
    ),
    '8d': (
        'This page',
        '/pricing',
        '/guides/n8n',
        '/blog/roi',
    ),
    '8e': (
        'Opportunities',
        'Competitor gaps',
        'Tracked',
        'Cannibalization',
    ),
    '8f': (
        'Profile',
        'Gaps',
        'Unlinked mentions',
        'Outreach',
    ),
    '9b': (
        'Segments',
        'Competitor Ads',
        'Concepts',
        'Weekly Plan',
    ),
    '9e': (
        'All',
        'Text',
        'Image',
        'Video',
        'Voice',
        'Print',
    ),
    '9f': (
        'Schedule',
        'Newsletter',
        'Trade-fair',
        'Bookings',
        'Community',
    ),
    '9h': (
        '🧠 Strategist',
        '🎬 Creative Dir',
        '🏭 Producer',
        '📣 Distributor',
    ),
}


def tabs_for(sid):
    """His tab labels for one screen, or ()."""
    return TABS.get(str(sid), ())

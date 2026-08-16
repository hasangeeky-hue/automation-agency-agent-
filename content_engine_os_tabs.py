# -*- coding: utf-8 -*-
"""His in-screen tab strips, from the FINAL revised wireframe.

A desk like the Technical Engineer is ONE screen holding several
views. Flattening it into one board buries all but the first.

Labels are his, with two edits: em-dashes normalised, and placeholder
COUNTS stripped, because a fake number on a tab is still a fake
number. The tab CONTENT is not copied at all, for the same reason.
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
    # the corrected file draws a per-staff strip on the SEO Control Room
    # too, mirroring 9h. It was missed in the first generation.
    '8h': (
        '🔧 Technical',
        '✍ Content',
        '🧭 Strategist',
        '🔗 Link',
        '📊 Analyst',
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

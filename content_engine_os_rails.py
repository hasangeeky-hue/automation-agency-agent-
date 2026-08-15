# -*- coding: utf-8 -*-
"""The staffrail content, lifted from the founder's own wireframe.

Every string below is his, from Agent OS Wireframes.dc.html, with two
deliberate departures, both recorded here so nobody has to guess
later why the file and the screen differ:

  Em-dashes are normalised to commas. His prose uses them; his rule
  forbids them in the product and verify_agentos fails the build on
  one. His rule wins over his prose.

  12a and 12c said EU and DE leads are HARD-BLOCKED from cold email.
  He later said plainly: "i dont want exclude eu and germany", and
  this engine has no such block (verify_deploy asserts it). Printing
  the wireframe text would have put a control on the screen that does
  not exist, which is the false green this OS refuses. The rail now
  states what is actually true: consent and approval are the control.
"""

RAILS = {
    '8a': (
        ('SEO department, 5 staff',
         '🔧 Technical ● crawling 1,240 URLs · 22 issues ✍ Content ● drafting 5 pages · 3 answer-blocks 🧭 Strategist idle 14 opportunities found 🔗 Link idle 8 gaps · 12 mentions 📊 Analyst ● scanning 340 kw + 40 prompts'),
    ),
    '8b': (
        ('Why this desk',
         'Same audit depth as a paid crawler tool, but every issue already has an owner (the Technical Engineer) and a fix path, not just a report you have to act on yourself.'),
    ),
    '8c': (
        ('The AEO/GEO edge',
         "Beyond rank tracking, the Analyst runs your own prompts against ChatGPT, Perplexity, Google AI Overviews and Claude to see if you're cited, then routes every gap straight to the Content Specialist to close."),
    ),
    '8d': (
        ('Why one desk for AEO too',
         'Real content teams don\'t have a separate "AEO person", the same specialist writes the answer-blocks and schema that get you cited by AI, alongside ordinary on-page fixes.'),
    ),
    '8e': (
        ('One-click hand-off',
         "The Strategist finds the opportunity and routes it straight to the Content Specialist's queue, no manual hand-off between research and execution."),
    ),
    '8f': (
        ('Why gated here',
         'Off-page work touches other people and costs paid data, the Link Builder drafts, you approve every send.'),
    ),
    '8g': (
        ('Provider-agnostic',
         'The whole module reads its source + cost tier from here, swap a provider in one place and every screen updates. No provider name is ever hardcoded in the UI.'),
    ),
    '8h': (
        ('Same pattern, every module',
         'Mirrors the Media Buyer OS agents room exactly, autonomy level, data access + cost cap, activity log, per employee. One shared grammar across all 12 modules. Try next: "make the module sidebar in 8a actually switch desks" · "start Module 1, rebuild the Media Buyer OS shell to match this Mother OS frame" · "add Module 3 (Email &amp; CRM) as its own 5-person desk set" const PLATFORMS = { amazon: {'),
    ),
    '9a': (
        ('Marketing department, 4 staff',
         '🧠 Strategist ● researching segments + competitor ads 🎬 Creative Dir ● routing 4 briefs incoming 🏭 Producer ● producing 5 pieces in flight 📣 Distributor ● scheduling 6 queued · newsletter draft'),
    ),
    '9b': (
        ('Steps 1,2 of the pipeline',
         'Segmentation and competitor research feed directly into the concept builder, offer, emotional angle, story, channel, format, exactly what you brief in real life.'),
    ),
    '9c': (
        ("The spine's one gate",
         'Nothing gets produced without clearing this room. Approve here and the piece becomes a brief that flows straight to the Creative Director.'),
    ),
    '9d': (
        ('Router, not maker',
         "The Creative Director decides HOW each piece gets made and assigns it to the right tool or human, production itself happens at the Producer's desk."),
    ),
    '9e': (
        ('Every content type, one desk',
         'Blog, web copy, image, video, animation, voice-over, brochure, product photography, packaging, thumbnails, raw shoot scripts, each routes to its assigned AI tool or a human slot, then lands in Drive.'),
    ),
    '9f': (
        ('Steps 6,9 of the pipeline',
         'Scheduling via Metricool, newsletter sends, trade-fair print, appointment booking and community replies, all in one desk, all gated before they go out.'),
    ),
    '9g': (
        ('Shared view',
         'One timeline for every piece moving through the pipeline, useful for everyone, not owned by a single desk.'),
    ),
    '9h': (
        ('Same pattern, every module',
         'Tools layer mirrors SEO\'s data-sources screen; Control Room mirrors Media Buyer\'s agents room, one coherent grammar across all 12 modules. Try next: "wire the module sidebar so clicking 1/2/3 actually switches modules" · "add Module 4 as its own department" · "make the calendar blocks in 9g clickable" 8 SEO/AEO/GEO OS as a 5-person department, docked into the shared Mother OS shell, Command Cent'),
    ),
    '11a': (
        ('Commerce dept, 5 staff',
         "📦 Inventory Controller ● live 💵 Pricing Analyst ● live 🎯 Merchandiser ● live 🏷 Promotions Manager ● live 🔄 Lifecycle Analyst ● live 💬 Command on any staff or approval card pre-fills that agent's command box on their own desk, open it to edit and send."),
    ),
    '11b': (
        ('This desk',
         'Reads live stock from the store, flags low/overstock, keeps SKU/EAN clean, drafts reorder proposals. Data is synced, never invented here. <div'),
        ('Feeds',
         '💵 Pricing cost basis 🔄 Lifecycle stock signal <div'),
        ('Command {{ deskAgent_inv }}',
         '{{ e.l }} Send'),
    ),
    '11c': (
        ('This desk',
         'Every price change is a PROPOSAL, never auto-applied. It goes to the same approval gate as every money move in the OS. <div'),
        ('Slot',
         'PRICE-INTEL ●PAID <div'),
        ('Command {{ deskAgent_price }}',
         '{{ e.l }} Send'),
    ),
    '11d': (
        ('This desk',
         'Ranks priority sellers, flags slow movers, proposes bundles, and runs comparative product research via the MARKET slot. <div'),
        ('Feeds',
         'Marketing OS priority products <div'),
        ('Command {{ deskAgent_merch }}',
         '{{ e.l }} Send'),
    ),
    '11e': (
        ('This desk',
         "The margin-impact preview is computed before you approve, you see what a discount does to margin before it's live, not after. <div"),
        ('Slot',
         'PROMO = your store, native <div'),
        ('Command {{ deskAgent_promo }}',
         '{{ e.l }} Send'),
    ),
    '11f': (
        ('Routes to',
         'restock -> Inventory clearance -> Promotions discontinue -> SKU cleanup <div'),
        ('Command {{ deskAgent_life }}',
         '{{ e.l }} Send'),
    ),
    '11g': (
        ('The bridge',
         "Approved offers and priority products land as concept seeds in Module 3's Strategist desk, the two departments become one Mother OS. <div"),
        ('Command {{ deskAgent_mkt }}',
         '{{ e.l }} Send'),
    ),
    '11h': (
        ('Same pattern, every module',
         'One control room shape across all 12 modules, sources, staff, autonomy, so the whole Mother OS reads as one coherent product.'),
    ),
    '11i': (
        ('This is the API layer',
         "Each pill pulls that platform's own reporting system, Amazon FBA's IPI/Buy Box, FBM's Account Health rates, Meta's catalog diagnostics, TikTok's GMV-by-surface, never one merged table. <div"),
        ('After the numbers',
         'Every channel has its own working agent below the chart, stop it, or write it a new instruction directly, without leaving this screen. Try next: "wire the Command Center approvals to jump straight into 11c/11e with the right SKU pre-filled" · "add a 4th Sources row for BigCommerce" · "link 11g\'s Send buttons to actually create draft briefs in 9c" 10 Product Publisher, write the product descripti'),
    ),
    '12a': (
        ('Two gates',
         'Region: Europe and Germany stay IN scope, as you decided. Consent and open-tracking state are the real control, not a country block, and no country block exists in this engine. Send: every campaign needs your approval.'),
        ('Cold is not newsletter',
         'This module is outbound prospecting. The newsletter lives in Marketing ( 9f ).'),
    ),
    '12b': (
        ('This desk',
         'Every source is a slot with a visible cost + risk badge, risky ones (LinkedIn, messaging apps) are flagged ⚠ so you plug a compliant provider instead of raw scraping that gets blocked. <div'),
        ('Command {{ deskAgent_prospect }}',
         '{{ e.l }} Send'),
    ),
    '12c': (
        ('The region gate',
         'Region: Europe and Germany stay IN scope, as you decided. Consent and open-tracking state are the real control, not a country block, and no country block exists in this engine. Send: every campaign needs your approval.'),
        ('Command {{ deskAgent_clean }}',
         '{{ e.l }} Send'),
    ),
    '12d': (
        ('Next',
         'Hot leads (score &gt;80) route to the Writer with their persona + best offer angle attached, no blank-slate drafting. <div'),
        ('Command {{ deskAgent_qualify }}',
         '{{ e.l }} Send'),
    ),
    '12e': (
        ('This desk',
         'The Writer never invents brand voice, template, copy shell, CTA and design come from Marketing. Personalization is per-lead, per-persona only. <div'),
        ('Command {{ deskAgent_write }}',
         '{{ e.l }} Send'),
    ),
    '12f': (
        ('Send is gated',
         'Rate-limited, warmed domains, compliance-checked, human-approved. No auto-blasting, ever. <div'),
        ('Command {{ deskAgent_sender }}',
         '{{ e.l }} Send'),
    ),
    '12g': (
        ('Same pattern, every module',
         'Sources, staff, autonomy, one control-room shape across the Mother OS. Here the only non-negotiable defaults are the send gate and the EU block.'),
    ),
    '12h': (
        ('One view, two pipes',
         "Whether the agent drives an ESP like Klaviyo or calls the store's own email API, creative, list and metrics render the same way here. <div"),
        ('Command {{ deskAgent_emailops }}',
         '{{ e.l }} Send'),
    ),
    '12i': (
        ('Segmentation Analyst',
         'Rebuilds lifecycle segments from order history, and tags every prospected lead with its source + location for the Qualifier and Sender to use. <div'),
        ('Command {{ deskAgent_seg }}',
         '{{ e.l }} Send Try next: "wire the region gate to actually strip EU leads out of the Sender\'s queue" · "add BigCommerce-style CRM push for booked meetings" · "connect qualifier \'send to Writer\' buttons to prefill 12e with that lead" · "add SMS/WhatsApp as a send channel next to email" 11 Commerce / Merchandising OS, Module 4: inventory, pricing, merchandising, promotions and lifecycle, with a han'),
    ),
}


def for_screen(sid):
    """The rail sections for one screen, or () when he drew none."""
    return RAILS.get(str(sid), ())

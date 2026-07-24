"""
update_legal_pages.py — publish the LLC principal address + contact email to the
website's legal pages, and create a Privacy Policy if one is missing.

Reads the WordPress credentials the founder already connected (settings store),
then via the WordPress REST API:
  * Imprint (Impressum)  -> full company details (name, address, contact)
  * Privacy Policy        -> created if missing, with a standard, accurate policy
  * Terms of Service      -> appends a "Company & Contact" section (idempotent)

Run ON THE VPS:
  cd /opt/content-engine
  docker compose -f deploy/docker-compose.yml exec worker python deploy/update_legal_pages.py
Idempotent: safe to run again; it updates the same pages rather than duplicating.
"""

import os
import requests

from content_engine_store_pg import PgJobStore

COMPANY = "Anthropos Automation Service LLC"
ADDR_HTML = ("1309 Coffeen Avenue STE 1200<br>\n"
             "Sheridan, Wyoming 82801<br>\nUnited States")
EMAIL = "contact@anthropos-automation.com"
MARK = "<!-- anthropos-company-block -->"

_COMPANY_BLOCK = (
    f'{MARK}\n<h2>Company details</h2>\n'
    f'<p><strong>{COMPANY}</strong><br>\n{ADDR_HTML}</p>\n'
    f'<p><strong>Contact:</strong> <a href="mailto:{EMAIL}">{EMAIL}</a></p>\n'
    f'<p>{COMPANY} is a limited liability company registered in the State of '
    f'Wyoming, United States. EIN: pending.</p>')

IMPRINT_HTML = (
    "<h1>Imprint</h1>\n" + _COMPANY_BLOCK + "\n"
    "<p>Responsible for the content of this website: " + COMPANY + ".</p>\n"
    "<p>This website is operated for informational and business purposes. All "
    "trademarks and brand names are the property of their respective owners.</p>")

PRIVACY_HTML = (
    "<h1>Privacy Policy</h1>\n"
    "<p><em>Last updated: 2026.</em></p>\n" + _COMPANY_BLOCK + "\n"
    "<h2>Who we are</h2>\n"
    f"<p>{COMPANY} (\"we\", \"us\") operates anthropos-automation.com and provides "
    "AI automation services. For any privacy question or request, contact us at "
    f'<a href="mailto:{EMAIL}">{EMAIL}</a>.</p>\n'
    "<h2>What we collect</h2>\n<ul>\n"
    "<li><strong>Contact details</strong> you give us (name, email, company) when you "
    "enquire, book a call, or subscribe.</li>\n"
    "<li><strong>Usage data</strong> collected automatically (pages visited, device, "
    "approximate location) via cookies and analytics.</li>\n"
    "<li><strong>Communication content</strong> when you email or reply to us.</li>\n</ul>\n"
    "<h2>How we use it</h2>\n<ul>\n"
    "<li>To respond to you, deliver our services, and schedule consultations.</li>\n"
    "<li>To send relevant business updates (you can unsubscribe from any email at any time).</li>\n"
    "<li>To measure and improve our website and content.</li>\n</ul>\n"
    "<h2>Cookies &amp; analytics</h2>\n"
    "<p>We use cookies and analytics tools (e.g. Google Analytics) to understand site "
    "usage. You can control cookies through your browser settings.</p>\n"
    "<h2>Sharing</h2>\n"
    "<p>We do not sell your personal data. We share it only with service providers who "
    "help us operate (e.g. email, analytics, scheduling), under appropriate safeguards, "
    "or where required by law.</p>\n"
    "<h2>Your rights</h2>\n"
    "<p>Depending on your location (including under GDPR and CCPA), you may request access "
    "to, correction of, or deletion of your personal data, and object to certain "
    f'processing. To exercise any right, email <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>\n'
    "<h2>Retention</h2>\n"
    "<p>We keep personal data only as long as needed for the purposes above or as required "
    "by law, then delete or anonymise it.</p>\n"
    "<h2>Changes</h2>\n"
    "<p>We may update this policy; the latest version is always on this page.</p>")


def main() -> int:
    store = PgJobStore(os.environ["DATABASE_URL"])
    g = store.get_setting
    base = (g("WORDPRESS_URL") or "https://anthropos-automation.com").rstrip("/")
    user, pw = g("WORDPRESS_USER"), g("WORDPRESS_APP_PASSWORD")
    if not (user and pw):
        print("ERROR: WordPress not connected (WORDPRESS_USER / WORDPRESS_APP_PASSWORD).")
        return 1
    api = base + "/wp-json/wp/v2/pages"
    auth = (user, pw)

    def find(slug):
        r = requests.get(api, params={"slug": slug, "_fields": "id,content"},
                         auth=auth, timeout=30)
        arr = r.json() if r.ok else []
        return arr[0] if arr else None

    def update(pid, content):
        r = requests.post(f"{api}/{pid}", auth=auth, json={"content": content}, timeout=30)
        return r.ok

    def create(title, slug, content):
        r = requests.post(api, auth=auth, timeout=30, json={
            "title": title, "slug": slug, "content": content, "status": "publish"})
        return r.ok, (r.json().get("link") if r.ok else r.text[:200])

    # 1) Imprint -> full company details
    imp = find("imprint")
    if imp:
        print("imprint update:", "ok" if update(imp["id"], IMPRINT_HTML) else "FAILED")
    else:
        ok, link = create("Imprint", "imprint", IMPRINT_HTML)
        print("imprint create:", link if ok else "FAILED")

    # 2) Privacy Policy -> create if missing
    pol = find("privacy-policy") or find("privacy")
    if pol:
        print("privacy update:", "ok" if update(pol["id"], PRIVACY_HTML) else "FAILED")
    else:
        ok, link = create("Privacy Policy", "privacy-policy", PRIVACY_HTML)
        print("privacy create:", link if ok else "FAILED")

    # 3) Terms -> append the company block once (idempotent)
    terms = find("terms") or find("terms-of-service")
    if terms:
        cur = (terms.get("content", {}) or {}).get("rendered", "")
        if MARK in cur:
            print("terms: company block already present — skipped")
        else:
            print("terms append:", "ok" if update(terms["id"], cur + "\n" + _COMPANY_BLOCK) else "FAILED")
    else:
        print("terms: page not found — skipped")

    print("DONE. Check /imprint/, /privacy-policy/ and /terms/ on the site.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

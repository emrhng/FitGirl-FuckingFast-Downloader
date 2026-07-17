from playwright.sync_api import sync_playwright
import re
import os
import time

URLS_FILE = "urls.txt"
OUTPUT_FILE = "direct_links.txt"
FAILED_FILE = "failed_urls.txt"


def read_urls(filepath):
    """Read URLs from file, handling various encodings and line formats."""
    content = None
    for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, OSError):
            continue
    if content is None:
        return []

    urls = []
    for line in re.split(r'[\r\n]+', content):
        line = line.strip()
        if not line:
            continue
        match = re.search(r'https?://[^\s]*fuckingfast\.co[^\s]*', line)
        if match:
            urls.append(match.group(0))
    return urls


def get_filename(url):
    """Extract a human-readable filename from the URL fragment for display."""
    if '#' in url:
        fragment = url.split('#', 1)[1]
        parts = fragment.split('--_')
        name = parts[-1] if parts else fragment
        return name.replace('%20', ' ')
    return url.split('/')[-1]


def process_url(browser, url):
    """Process a single URL in a fresh context.

    Uses page.expect_response() to catch the POST /f/.../go response
    and extract the hx-redirect header containing the direct download link.
    Falls back to route interception if the header is missing.

    Returns the direct link or None.
    """
    state = {'route_url': None}

    # Fresh context per URL = complete state isolation
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0.0.0 Safari/537.36",
        viewport={'width': 1280, 'height': 800}
    )
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', "
        "{get: () => undefined});"
    )

    # Cancel any unwanted downloads silently
    context.on("download", lambda d: d.cancel())

    page = context.new_page()

    # Route handler — captures dl.fuckingfast.co URL + prevents download
    def handle_route(route):
        if 'dl.fuckingfast.co' in route.request.url:
            state['route_url'] = route.request.url
            route.abort()
        else:
            route.continue_()
    page.route("**/*", handle_route)

    try:
        clean_url = url.split('#')[0]
        page.goto(clean_url, wait_until="networkidle", timeout=60000)

        # Wait for Cloudflare Turnstile to resolve
        time.sleep(6)

        # FIRST click — satisfies the site's JS "seen" logic
        page.click("a.gay-button")
        time.sleep(2)

        # Close any ad popups that spawned
        for popup in context.pages[1:]:
            try:
                popup.close()
            except Exception:
                pass

        # SECOND click — triggers HTMX POST to /f/{id}/go
        #
        # KEY FIX: Use page.expect_response() instead of time.sleep() polling.
        # Playwright's sync API does NOT dispatch event callbacks during
        # time.sleep() — the callback queue is only processed when Playwright
        # methods are called. expect_response() is a Playwright-native wait
        # that properly handles event dispatching internally.
        hx_redirect = None
        try:
            with page.expect_response(
                lambda r: r.request.method == "POST"
                and '/f/' in r.url and '/go' in r.url,
                timeout=60000
            ) as resp_info:
                page.click("a.gay-button")

            response = resp_info.value
            # Case-insensitive header lookup (HTTP/2 lowercases headers)
            headers = {k.lower(): v for k, v in response.headers.items()}
            hx_redirect = headers.get('hx-redirect')
        except Exception:
            pass

        # PRIMARY: hx-redirect header contains the direct download URL
        if hx_redirect:
            return hx_redirect

        # FALLBACK: route handler capture (dl.fuckingfast.co navigation)
        # Use page.wait_for_timeout for proper Playwright event dispatching
        for _ in range(30):  # up to ~15 seconds
            if state['route_url']:
                return state['route_url']
            try:
                page.wait_for_timeout(500)
            except Exception:
                break

        return None
    finally:
        try:
            context.close()
        except Exception:
            pass


def main():
    if not os.path.exists(URLS_FILE):
        print(f"[!] File not found: {URLS_FILE}")
        input("Press ENTER to exit...")
        return

    urls = read_urls(URLS_FILE)
    if not urls:
        print(f"[!] No URLs found in {URLS_FILE}")
        input("Press ENTER to exit...")
        return

    total = len(urls)
    print(f"[*] Found {total} URLs in {URLS_FILE}")
    print(f"[*] Direct links → {OUTPUT_FILE}")
    print(f"[*] Launching browser...\n")

    results = []
    failed = []

    with sync_playwright() as p:
        # Single browser instance — reused, but fresh context per URL
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )

        # Open output file; append each capture immediately (crash-safe)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
            for i, url in enumerate(urls, 1):
                filename = get_filename(url)
                print(f"[{i}/{total}] {filename}", end=" ... ", flush=True)

                try:
                    link = process_url(browser, url)
                    if link:
                        results.append(link)
                        out_f.write(link + '\n')
                        out_f.flush()
                        print("[OK]")
                    else:
                        failed.append(url)
                        print("[FAIL]")
                except Exception as e:
                    failed.append(url)
                    print(f"[ERR: {str(e)[:60]}]")

        browser.close()

    # Write failed URLs for easy re-run
    if failed:
        with open(FAILED_FILE, 'w', encoding='utf-8') as f:
            for fail_url in failed:
                f.write(fail_url + '\n')

    print(f"\n{'=' * 50}")
    print(f"[+] Extracted: {len(results)} link(s) → {OUTPUT_FILE}")
    if failed:
        print(f"[-] Failed:    {len(failed)} URL(s)  → {FAILED_FILE}")
    else:
        print(f"[-] Failed:    0")


if __name__ == "__main__":
    main()
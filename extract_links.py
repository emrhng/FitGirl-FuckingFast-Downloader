"""
Extract direct download links from fuckingfast.co paste links.

Reads a list of fuckingfast.co URLs (one per line), drives a real Chromium
browser to pass the Cloudflare Turnstile challenge, and writes the resulting
direct download links to an output file.

Usage:
    python extract_links.py                       # uses urls.txt -> direct_links.txt
    python extract_links.py -i mylinks.txt        # custom input
    python extract_links.py -o out.txt            # custom output
    python extract_links.py --retry-failed        # re-run only failed_urls.txt
"""
import argparse
import os
import re
import sys
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[!] Playwright is not installed. Run:")
    print("    pip install -r requirements.txt")
    print("    python -m playwright install chromium")
    sys.exit(1)


def read_urls(filepath):
    """Read fuckingfast.co URLs from a file, tolerating various encodings."""
    content = None
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
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
        if not line or line.startswith('#'):
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


def process_url(browser, url, wait_seconds):
    """Process a single URL in a fresh browser context.

    Uses page.expect_response() to catch the POST /f/.../go response and
    extract the hx-redirect header containing the direct download link.
    Falls back to route interception if the header is missing.

    Returns the direct link or None.
    """
    state = {'route_url': None}

    # Fresh context per URL = complete state isolation.
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

    # Cancel any unwanted downloads silently.
    context.on("download", lambda d: d.cancel())

    page = context.new_page()

    # Route handler captures the dl.fuckingfast.co URL and prevents download.
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

        # Wait for Cloudflare Turnstile to resolve.
        time.sleep(wait_seconds)

        # FIRST click satisfies the site's JS "seen" logic.
        page.click("a.gay-button")
        time.sleep(2)

        # Close any ad popups that spawned.
        for popup in context.pages[1:]:
            try:
                popup.close()
            except Exception:
                pass

        # SECOND click triggers the HTMX POST to /f/{id}/go.
        #
        # Use page.expect_response() instead of time.sleep() polling:
        # Playwright's sync API does NOT dispatch event callbacks during
        # time.sleep(); expect_response() is a Playwright-native wait that
        # handles event dispatching internally.
        hx_redirect = None
        try:
            with page.expect_response(
                lambda r: r.request.method == "POST"
                and '/f/' in r.url and '/go' in r.url,
                timeout=60000
            ) as resp_info:
                page.click("a.gay-button")

            response = resp_info.value
            # Case-insensitive header lookup (HTTP/2 lowercases headers).
            headers = {k.lower(): v for k, v in response.headers.items()}
            hx_redirect = headers.get('hx-redirect')
        except Exception:
            pass

        # PRIMARY: hx-redirect header contains the direct download URL.
        if hx_redirect:
            return hx_redirect

        # FALLBACK: route handler capture (dl.fuckingfast.co navigation).
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract direct download links from fuckingfast.co paste links."
    )
    parser.add_argument(
        '-i', '--input', default='urls.txt',
        help="Input file with fuckingfast.co links (default: urls.txt)"
    )
    parser.add_argument(
        '-o', '--output', default='direct_links.txt',
        help="Output file for direct links (default: direct_links.txt)"
    )
    parser.add_argument(
        '-f', '--failed-file', default='failed_urls.txt',
        help="File to record URLs that failed (default: failed_urls.txt)"
    )
    parser.add_argument(
        '--retry-failed', action='store_true',
        help="Read from the failed file and append results to the output file."
    )
    parser.add_argument(
        '--headless', action='store_true',
        help="Run the browser headless. May fail the Turnstile challenge."
    )
    parser.add_argument(
        '--wait', type=float, default=6.0,
        help="Seconds to wait for the Turnstile challenge (default: 6)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    input_file = args.failed_file if args.retry_failed else args.input
    # When retrying, append so we keep previously extracted links.
    output_mode = 'a' if args.retry_failed else 'w'

    if not os.path.exists(input_file):
        print(f"[!] Input file not found: {input_file}")
        if input_file == 'urls.txt':
            print("    Copy urls.example.txt to urls.txt and paste your links.")
        return

    urls = read_urls(input_file)
    if not urls:
        print(f"[!] No fuckingfast.co links found in {input_file}")
        return

    total = len(urls)
    print(f"[*] Found {total} URL(s) in {input_file}")
    print(f"[*] Direct links -> {args.output}")
    print(f"[*] Launching browser (headless={args.headless})...\n")

    results = []
    failed = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=args.headless,
            args=['--disable-blink-features=AutomationControlled']
        )

        # Append each capture immediately so a crash never loses progress.
        with open(args.output, output_mode, encoding='utf-8') as out_f:
            for i, url in enumerate(urls, 1):
                filename = get_filename(url)
                print(f"[{i}/{total}] {filename}", end=" ... ", flush=True)

                try:
                    link = process_url(browser, url, args.wait)
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

    # Record failed URLs for an easy re-run with --retry-failed.
    if failed:
        with open(args.failed_file, 'w', encoding='utf-8') as f:
            for fail_url in failed:
                f.write(fail_url + '\n')
    elif os.path.exists(args.failed_file):
        # No failures this run: clear the stale failed file.
        try:
            os.remove(args.failed_file)
        except OSError:
            pass

    print(f"\n{'=' * 50}")
    print(f"[+] Extracted: {len(results)} link(s) -> {args.output}")
    if failed:
        print(f"[-] Failed:    {len(failed)} URL(s)  -> {args.failed_file}")
        print(f"    Re-run failures with: python extract_links.py --retry-failed")
    else:
        print(f"[-] Failed:    0")


if __name__ == "__main__":
    main()

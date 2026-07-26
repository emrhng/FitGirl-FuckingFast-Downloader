#!/usr/bin/env python3
"""
FitGirl FuckingFast Downloader - all in one.

Run this file, paste the link of a page that contains fuckingfast.co links
(a pastebin, a FitGirl paste page, ...) and everything else is automatic:
first-run setup, link scraping, Cloudflare Turnstile bypass and parallel
downloading with the original filenames.

    python fitgirl.py
    python fitgirl.py https://pastebin.com/XXXXXXXX
    python fitgirl.py links.txt -o "D:/Games" -w 6

Only the standard library is imported at start-up; missing packages and the
Chromium browser are installed on the first run.
"""
import argparse
import html
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urlparse

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

REQUIRED_PACKAGES = {           # import name -> pip requirement
    'requests': 'requests>=2.31.0',
    'playwright': 'playwright==1.61.0',
}
BOOTSTRAP_ENV_FLAG = 'FITGIRL_DL_BOOTSTRAPPED'

CHUNK_SIZE = 4 * 1024 * 1024    # 4 MB
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/122.0.0.0 Safari/537.36')
HEADERS = {'user-agent': USER_AGENT}

# A fuckingfast.co file link, e.g. https://fuckingfast.co/ab12cd34#Name.part001.rar
LINK_RE = re.compile(
    r'https?://(?:www\.)?fuckingfast\.co/[A-Za-z0-9]{5,}[^\s"\'<>\\)\]}]*',
    re.IGNORECASE,
)

ILLEGAL_FILENAME_CHARS = '<>:"|?*'

stop_event = threading.Event()


# --------------------------------------------------------------------------
# First-run setup
# --------------------------------------------------------------------------

def _missing_packages():
    import importlib.util
    return [req for mod, req in REQUIRED_PACKAGES.items()
            if importlib.util.find_spec(mod) is None]


def _pip_install(requirements):
    """Install requirements, falling back to a --user install."""
    base = [sys.executable, '-m', 'pip', 'install']
    for extra in ([], ['--user']):
        try:
            subprocess.check_call(base + extra + requirements)
            return True
        except (subprocess.CalledProcessError, OSError):
            continue
    return False


def ensure_packages():
    """Install missing Python packages, then re-exec so imports pick them up."""
    missing = _missing_packages()
    if not missing:
        return

    if os.environ.get(BOOTSTRAP_ENV_FLAG):
        # We already installed and restarted once; something is still wrong.
        print(f"[!] Still missing: {', '.join(missing)}")
        print("    Install them manually:  pip install " + ' '.join(missing))
        sys.exit(1)

    print("[setup] First run - installing: " + ', '.join(missing))
    if not _pip_install(missing):
        print("\n[!] Automatic installation failed.")
        print("    Your Python may be 'externally managed'. Use a virtual env:")
        print("      python -m venv .venv")
        if os.name == 'nt':
            print("      .venv\\Scripts\\activate")
        else:
            print("      source .venv/bin/activate")
        print("      pip install " + ' '.join(missing))
        sys.exit(1)

    print("[setup] Restarting with the new packages...\n")
    os.environ[BOOTSTRAP_ENV_FLAG] = '1'
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])


def ensure_chromium():
    """Download the Chromium build Playwright needs (once)."""
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            path = p.chromium.executable_path
        if path and os.path.exists(path):
            return
    except Exception:
        pass

    print("[setup] Downloading Chromium (one time, ~150 MB)...")
    try:
        subprocess.check_call(
            [sys.executable, '-m', 'playwright', 'install', 'chromium'])
    except (subprocess.CalledProcessError, OSError):
        print("[!] Could not install Chromium automatically. Run:")
        print("    python -m playwright install chromium")
        sys.exit(1)
    print()


# --------------------------------------------------------------------------
# Console output (a single status line plus scrolling messages)
# --------------------------------------------------------------------------

class Console:
    """Thread-safe output: log lines scroll, one live status line stays put."""

    def __init__(self):
        self._lock = threading.Lock()
        self._status = ''
        self._live = sys.stdout.isatty()

    def log(self, message):
        with self._lock:
            if self._status:
                sys.stdout.write('\r' + ' ' * len(self._status) + '\r')
            sys.stdout.write(message + '\n')
            if self._status:
                sys.stdout.write(self._status)
            sys.stdout.flush()

    def status(self, message):
        if not self._live:
            return
        with self._lock:
            pad = max(0, len(self._status) - len(message))
            self._status = message
            sys.stdout.write('\r' + message + ' ' * pad)
            sys.stdout.flush()

    def clear_status(self):
        with self._lock:
            if self._status:
                sys.stdout.write('\r' + ' ' * len(self._status) + '\r')
                sys.stdout.flush()
                self._status = ''


console = Console()


def human_size(num_bytes):
    value = float(num_bytes)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            return f"{value:.1f} {unit}"
        value /= 1024


# --------------------------------------------------------------------------
# Finding the fuckingfast.co links
# --------------------------------------------------------------------------

def sanitize_filename(name, fallback='file'):
    """Make a name safe to use as a filename on every platform."""
    name = name.replace('\\', '_').replace('/', '_')
    for char in ILLEGAL_FILENAME_CHARS:
        name = name.replace(char, '_')
    name = ''.join(ch for ch in name if ord(ch) >= 32)
    name = name.strip().strip('.')
    return name or fallback


def filename_for(url):
    """The original filename, taken from the '#...' part of a paste link."""
    if '#' in url:
        raw = unquote(url.split('#', 1)[1])
    else:
        raw = urlparse(url).path.rstrip('/').split('/')[-1]
    return sanitize_filename(raw)


def find_links(text):
    """Pull unique fuckingfast.co file links out of raw text or HTML."""
    found = []
    seen = set()
    for match in LINK_RE.finditer(html.unescape(text)):
        url = match.group(0).rstrip('.,;\'"')
        file_id = urlparse(url).path.strip('/')
        if not file_id or file_id in seen:
            continue
        seen.add(file_id)
        found.append(url)
    return found


def paste_candidates(url):
    """Candidate URLs to try, preferring the plain-text version of a paste."""
    candidates = []
    match = re.match(
        r'^(https?://(?:www\.)?pastebin\.com)/(?!raw/)([A-Za-z0-9]+)/?$', url, re.I)
    if match:
        candidates.append(f"{match.group(1)}/raw/{match.group(2)}")
    candidates.append(url)
    return candidates


def fetch_links_via_http(url):
    import requests
    for candidate in paste_candidates(url):
        try:
            response = requests.get(candidate, headers=HEADERS, timeout=30)
            response.raise_for_status()
        except Exception:
            continue
        links = find_links(response.text)
        if links:
            return links
    return []


def fetch_links_via_browser(url):
    """Render the page in Chromium - for JS-built or Cloudflare-gated pages."""
    from playwright.sync_api import sync_playwright
    console.log("[*] Page needs a browser, opening Chromium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled'])
        try:
            context = browser.new_context(user_agent=USER_AGENT,
                                          viewport={'width': 1280, 'height': 800})
            page = context.new_page()
            page.goto(url, wait_until='networkidle', timeout=60000)
            time.sleep(3)
            return find_links(page.content())
        finally:
            browser.close()


def collect_links(source):
    """Resolve the user's input into a list of fuckingfast.co links."""
    # A local file with links in it.
    if os.path.isfile(source):
        console.log(f"[*] Reading links from {source}")
        for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
            try:
                with open(source, 'r', encoding=encoding) as f:
                    return find_links(f.read())
            except (UnicodeDecodeError, OSError):
                continue
        return []

    # A single fuckingfast.co link pasted directly.
    if 'fuckingfast.co' in source.lower():
        direct = find_links(source)
        if direct:
            return direct

    console.log(f"[*] Fetching {source}")
    links = fetch_links_via_http(source)
    if not links:
        try:
            links = fetch_links_via_browser(source)
        except Exception as exc:
            console.log(f"[!] Could not read the page: {str(exc)[:100]}")
    return links


def guess_folder_name(filenames):
    """Derive a folder name from the repack filenames, e.g. 'Some_Game'."""
    for name in filenames:
        head = name.split('_--_')[0].strip(' _-')
        if len(head) >= 3 and not head.lower().startswith('part'):
            return sanitize_filename(head, 'download')
    return 'download'


# --------------------------------------------------------------------------
# Turnstile bypass: paste link -> direct download link
# --------------------------------------------------------------------------

def resolve_direct_link(browser, url, wait_seconds):
    """Open one paste link and return its direct download URL, or None.

    The page hides the real URL behind a Cloudflare Turnstile challenge and
    two clicks on the download button. The second click fires an HTMX POST
    whose 'hx-redirect' response header holds the direct link.
    """
    captured = {'url': None}

    # A fresh context per link keeps cookies and challenge state isolated.
    context = browser.new_context(user_agent=USER_AGENT,
                                  viewport={'width': 1280, 'height': 800})
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    context.on('download', lambda d: d.cancel())
    page = context.new_page()

    def handle_route(route):
        if 'dl.fuckingfast.co' in route.request.url:
            captured['url'] = route.request.url
            route.abort()          # we only want the URL, not the file
        else:
            route.continue_()
    page.route('**/*', handle_route)

    try:
        page.goto(url.split('#')[0], wait_until='networkidle', timeout=60000)

        # Give Turnstile time to solve itself.
        time.sleep(wait_seconds)

        # First click satisfies the site's own "user has seen this" logic.
        page.click('a.gay-button')
        time.sleep(2)

        for popup in context.pages[1:]:     # close ad popups
            try:
                popup.close()
            except Exception:
                pass

        # Second click triggers the POST /f/{id}/go request.
        #
        # expect_response() is used instead of sleeping: Playwright's sync API
        # does not dispatch event callbacks during time.sleep(), so a plain
        # sleep would miss the response entirely.
        try:
            with page.expect_response(
                lambda r: (r.request.method == 'POST'
                           and '/f/' in r.url and '/go' in r.url),
                timeout=60000,
            ) as response_info:
                page.click('a.gay-button')
            headers = {k.lower(): v for k, v in response_info.value.headers.items()}
            if headers.get('hx-redirect'):
                return headers['hx-redirect']
        except Exception:
            pass

        # Fallback: the route handler may have seen the download navigation.
        for _ in range(30):                 # up to ~15 s
            if captured['url']:
                return captured['url']
            page.wait_for_timeout(500)
        return None
    finally:
        try:
            context.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Downloading
# --------------------------------------------------------------------------

class Progress:
    """Shared counters for the live status line."""

    def __init__(self, total_files):
        self.lock = threading.Lock()
        self.total_files = total_files
        self.done = 0
        self.failed = 0
        self.bytes = 0
        self.started = time.time()

    def add_bytes(self, count):
        with self.lock:
            self.bytes += count

    def line(self):
        with self.lock:
            elapsed = max(time.time() - self.started, 0.001)
            speed = self.bytes / elapsed / (1024 * 1024)
            return (f"    {self.done}/{self.total_files} done  |  "
                    f"{human_size(self.bytes)}  |  {speed:.1f} MB/s")


def download_file(url, filename, output_dir, progress):
    """Download one file to output_dir, resuming a partial download if any."""
    import requests

    final_path = os.path.join(output_dir, filename)
    part_path = final_path + '.part'

    if os.path.exists(final_path):
        with progress.lock:
            progress.done += 1
        console.log(f"[skip] {filename}")
        return

    resume_from = os.path.getsize(part_path) if os.path.exists(part_path) else 0
    headers = dict(HEADERS)
    if resume_from:
        headers['Range'] = f'bytes={resume_from}-'

    try:
        with requests.get(url, headers=headers, stream=True, timeout=60) as response:
            if response.status_code == 416:         # already complete
                os.replace(part_path, final_path)
                with progress.lock:
                    progress.done += 1
                console.log(f"[ok]   {filename} (was already complete)")
                return

            response.raise_for_status()
            # Honour the server's answer: 206 continues, 200 restarts.
            append = resume_from > 0 and response.status_code == 206
            if resume_from and not append:
                resume_from = 0

            with open(part_path, 'ab' if append else 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if stop_event.is_set():
                        return                      # keep .part for next run
                    if chunk:
                        f.write(chunk)
                        progress.add_bytes(len(chunk))

        os.replace(part_path, final_path)
        with progress.lock:
            progress.done += 1
        size = os.path.getsize(final_path)
        console.log(f"[ok]   {filename} ({human_size(size)})")

    except Exception as exc:
        if stop_event.is_set():
            return
        with progress.lock:
            progress.failed += 1
        console.log(f"[fail] {filename}: {str(exc)[:90]}")


def status_loop(progress):
    while not stop_event.is_set():
        console.status(progress.line())
        time.sleep(1)


# --------------------------------------------------------------------------
# Main flow
# --------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Download every fuckingfast.co file listed on a paste page.")
    parser.add_argument(
        'source', nargs='?',
        help="Paste page URL (pastebin, FitGirl paste, ...) or a local file "
             "containing links. Asked interactively when omitted.")
    parser.add_argument(
        '-o', '--output-dir',
        help="Where to save files (default: ./downloads/<game name>)")
    parser.add_argument(
        '-w', '--workers', type=int, default=6,
        help="Parallel downloads (default: 6)")
    parser.add_argument(
        '--wait', type=float, default=6.0,
        help="Seconds to wait for the Turnstile challenge (default: 6)")
    parser.add_argument(
        '--no-rename', action='store_true',
        help="Save the server's hashed filenames instead of the original ones")
    return parser.parse_args()


def ask_for_source():
    print("=" * 62)
    print(" FitGirl FuckingFast Downloader")
    print("=" * 62)
    print(" Paste the link of the page that holds the fuckingfast.co links")
    print(" (a pastebin link, a FitGirl paste page, ...) and press ENTER.")
    print()
    try:
        return input(" Link: ").strip().strip('"\'')
    except (EOFError, KeyboardInterrupt):
        return ''


def main():
    args = parse_args()

    source = args.source or ask_for_source()
    if not source:
        print("[!] No link given.")
        return

    ensure_packages()
    ensure_chromium()

    links = collect_links(source)
    if not links:
        console.log("[!] No fuckingfast.co links found on that page.")
        console.log("    Check the link, or paste the page's raw/plain-text URL.")
        return

    names = [filename_for(url) for url in links]
    output_dir = args.output_dir or os.path.join('downloads', guess_folder_name(names))
    os.makedirs(output_dir, exist_ok=True)
    output_dir = os.path.abspath(output_dir)

    # Files already finished need no Turnstile solving at all.
    pending = [(url, name) for url, name in zip(links, names)
               if not os.path.exists(os.path.join(output_dir, name))]
    already_have = len(links) - len(pending)

    console.log(f"\n[*] Found {len(links)} file(s)")
    console.log(f"[*] Saving to {output_dir}")
    if already_have:
        console.log(f"[*] {already_have} already downloaded, skipping those")
    if not pending:
        console.log("\n[+] Everything is already downloaded.")
        return
    console.log(f"[*] Resolving {len(pending)} link(s) and downloading as they arrive")
    console.log("[*] A Chromium window will open - leave it alone, it closes itself\n")

    from playwright.sync_api import sync_playwright

    progress = Progress(len(pending))
    status_thread = threading.Thread(target=status_loop, args=(progress,), daemon=True)
    status_thread.start()

    failed_links = []
    resolved = 0

    executor = ThreadPoolExecutor(max_workers=args.workers)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled'])
            try:
                # Resolve links one by one, but start each download immediately
                # so extracting and downloading overlap.
                queue = list(pending)
                retry_round = False

                while queue:
                    for index, (url, name) in enumerate(queue, 1):
                        if stop_event.is_set():
                            break
                        label = 'retry' if retry_round else f"{index}/{len(queue)}"
                        try:
                            direct = resolve_direct_link(browser, url, args.wait)
                        except Exception as exc:
                            direct = None
                            console.log(f"[{label}] {name}: {str(exc)[:70]}")

                        if direct:
                            resolved += 1
                            out_name = name
                            if args.no_rename:
                                out_name = os.path.basename(direct.split('?')[0])
                            executor.submit(download_file, direct, out_name,
                                            output_dir, progress)
                        else:
                            failed_links.append((url, name))
                            console.log(f"[link fail] {name}")

                    # One automatic retry pass over the links that failed.
                    if failed_links and not retry_round and not stop_event.is_set():
                        console.log(f"\n[*] Retrying {len(failed_links)} failed link(s)\n")
                        queue = failed_links
                        failed_links = []
                        retry_round = True
                    else:
                        queue = []
            finally:
                browser.close()

        console.log("\n[*] All links resolved, finishing downloads...")
        executor.shutdown(wait=True)

    except KeyboardInterrupt:
        stop_event.set()
        console.clear_status()
        print("\n[!] Stopped. Run the program again to continue where it left off.")
        executor.shutdown(wait=True)
        return
    finally:
        stop_event.set()
        console.clear_status()

    elapsed = (time.time() - progress.started) / 60
    print()
    print("=" * 62)
    print(f"[*] Finished in {elapsed:.1f} minutes")
    print(f"    Downloaded: {progress.done}")
    if progress.failed:
        print(f"    Failed:     {progress.failed}  (run again to retry)")
    if failed_links:
        print(f"    Unresolved: {len(failed_links)}  (run again to retry)")
    print(f"    Folder:     {output_dir}")

    if progress.failed or failed_links:
        print("\n[i] Some items need another pass - just run the program again.")
    else:
        print("\n[+] All done. Extract the .rar files with WinRAR or 7-Zip.")


if __name__ == '__main__':
    main()

"""
Download all files listed in direct_links.txt using parallel downloads.

Files are saved with the original names that extract_links.py recorded next
to each direct link. Already-downloaded files with a matching size are
skipped, so the download is resumable — just run it again.

Usage:
    python download.py                        # -> ./downloads, 8 workers
    python download.py -o /path/to/games      # custom output directory
    python download.py -w 4                    # 4 parallel downloads
    python download.py --no-rename             # keep the hashed filenames
"""
import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    print("[!] The 'requests' package is not installed. Run:")
    print("    pip install -r requirements.txt")
    sys.exit(1)

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB chunks

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/122.0.0.0 Safari/537.36',
}


def hashed_name(url):
    """The server-side (hashed) filename portion of a direct link."""
    return os.path.basename(url.split('?')[0])


def build_download_list(direct_links_file, rename):
    """Build a list of (url, output_filename) pairs.

    extract_links.py writes each line as "<direct_url>\\t<original_name>".
    We read the name straight from the line, so filenames are always paired
    with the correct URL regardless of line order. Lines without a name (e.g.
    an older links file) fall back to the hashed filename.
    """
    result = []
    with open(direct_links_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            if '\t' in line:
                url, name = line.split('\t', 1)
                url, name = url.strip(), name.strip()
            else:
                url, name = line.strip(), ''
            if not url:
                continue
            output_name = hashed_name(url) if (not rename or not name) else name
            result.append((url, output_name))
    return result


def download_file(url, output_name, output_dir):
    """Download a single file, skipping it if already present at full size."""
    filepath = os.path.join(output_dir, output_name)

    # Skip if already downloaded with the correct size (resumable).
    try:
        head = requests.head(url, headers=HEADERS, timeout=30)
        remote_size = int(head.headers.get('content-length', 0))
        if (os.path.exists(filepath)
                and os.path.getsize(filepath) == remote_size
                and remote_size > 0):
            return f"[SKIP] {output_name} (already downloaded)"
    except Exception:
        pass

    try:
        start = time.time()
        downloaded = 0

        with requests.get(url, headers=HEADERS, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

        elapsed = time.time() - start
        speed = (downloaded / elapsed) / (1024 * 1024) if elapsed > 0 else 0
        size_mb = downloaded / (1024 * 1024)
        return f"[OK] {output_name} ({size_mb:.0f} MB @ {speed:.1f} MB/s)"

    except Exception as e:
        # Remove the partial file so a re-run starts it cleanly.
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        return f"[FAIL] {output_name}: {str(e)[:80]}"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download files from direct_links.txt in parallel."
    )
    parser.add_argument(
        '-i', '--input', default='direct_links.txt',
        help="File with direct download links (default: direct_links.txt)"
    )
    parser.add_argument(
        '-o', '--output-dir', default='downloads',
        help="Directory to save files into (default: ./downloads)"
    )
    parser.add_argument(
        '-w', '--workers', type=int, default=8,
        help="Number of parallel downloads (default: 8)"
    )
    parser.add_argument(
        '--no-rename', action='store_true',
        help="Keep the hashed filenames instead of restoring original names."
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.input):
        print(f"[!] {args.input} not found. Run extract_links.py first.")
        sys.exit(1)

    download_list = build_download_list(args.input, rename=not args.no_rename)
    if not download_list:
        print("[!] No files to download.")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    output_dir = os.path.abspath(args.output_dir)

    print(f"[*] Downloading {len(download_list)} file(s) -> {output_dir}")
    print(f"[*] Parallel workers: {args.workers}")
    print(f"[*] Started at: {time.strftime('%H:%M:%S')}\n")

    start = time.time()
    completed = 0
    failed = 0
    skipped = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(download_file, url, name, output_dir): (url, name)
            for url, name in download_list
        }

        for future in as_completed(futures):
            result = future.result()
            completed += 1
            if result.startswith("[SKIP]"):
                skipped += 1
            elif result.startswith("[FAIL]"):
                failed += 1
            print(f"[{completed}/{len(download_list)}] {result}")

    elapsed = time.time() - start
    print(f"\n{'=' * 50}")
    print(f"[*] Done in {elapsed / 60:.1f} minutes")
    print(f"    Success: {completed - failed - skipped}")
    print(f"    Skipped: {skipped}")
    print(f"    Failed:  {failed}")
    print(f"    Output:  {output_dir}")

    if failed:
        print("\n[i] Some files failed. Just run download.py again to resume.")


if __name__ == "__main__":
    main()

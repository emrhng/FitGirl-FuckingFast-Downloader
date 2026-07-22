"""
Download all files listed in direct_links.txt using parallel downloads.

Files are saved with their original names (e.g. Game_--_.part001.rar) by
mapping the hashed direct-link filenames back to the names in urls.txt.
Already-downloaded files with a matching size are skipped, so the download
is resumable — just run it again.

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


def build_rename_map(urls_file, direct_links_file):
    """Map hashed direct-link filenames to original names from urls.txt."""
    original_names = []
    with open(urls_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '#' in line:
                fragment = line.split('#', 1)[1]
                parts = fragment.split('--_')
                name = parts[-1] if parts else fragment
                name = name.replace('%20', ' ')
                original_names.append(name)
            else:
                original_names.append(None)

    hash_names = []
    with open(direct_links_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            hash_names.append(os.path.basename(line.split('?')[0]))

    rename_map = {}
    for orig, hash_name in zip(original_names, hash_names):
        if orig and hash_name:
            rename_map[hash_name] = orig
    return rename_map


def build_download_list(direct_links_file, urls_file, rename):
    """Build a list of (url, output_filename) pairs."""
    rename_map = {}
    if rename and urls_file and os.path.exists(urls_file):
        rename_map = build_rename_map(urls_file, direct_links_file)

    result = []
    with open(direct_links_file, 'r', encoding='utf-8') as f:
        for line in f:
            url = line.strip()
            if not url:
                continue
            hash_name = os.path.basename(url.split('?')[0])
            output_name = rename_map.get(hash_name, hash_name)
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
        '-u', '--urls', default='urls.txt',
        help="Original links file used to restore filenames (default: urls.txt)"
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

    download_list = build_download_list(
        args.input, args.urls, rename=not args.no_rename
    )
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

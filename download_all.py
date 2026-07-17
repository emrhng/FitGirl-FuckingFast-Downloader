"""
Download all files from direct_links.txt to E:\f using parallel downloads.
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, unquote
import requests

DIRECT_LINKS_FILE = "direct_links.txt"
OUTPUT_DIR = r"E:\f"
MAX_WORKERS = 8  # parallel downloads
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunks

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
}

def get_filename(url):
    """Extract filename from URL"""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    filename = os.path.basename(path)
    if filename:
        return filename
    # Try query params
    if 'filename' in parsed.query.lower():
        import re
        match = re.search(r'filename[^=]*=([^&]+)', parsed.query, re.IGNORECASE)
        if match:
            return unquote(match.group(1))
    # Last resort
    return "unknown_file"


def download_file(url, output_dir):
    """Download a single file with progress"""
    filename = get_filename(url)
    filepath = os.path.join(output_dir, filename)
    
    # Skip if already downloaded (check size)
    try:
        head = requests.head(url, headers=HEADERS, timeout=30)
        remote_size = int(head.headers.get('content-length', 0))
        
        if os.path.exists(filepath) and os.path.getsize(filepath) == remote_size and remote_size > 0:
            return f"[SKIP] {filename} (already exists, size matches)"
    except Exception:
        pass
    
    try:
        start = time.time()
        downloaded = 0
        
        with requests.get(url, headers=HEADERS, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get('content-length', 0))
            
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
        
        elapsed = time.time() - start
        speed = (downloaded / elapsed) / (1024 * 1024) if elapsed > 0 else 0
        size_mb = downloaded / (1024 * 1024)
        return f"[OK] {filename} ({size_mb:.0f} MB @ {speed:.1f} MB/s)"
    
    except Exception as e:
        # Remove partial file on error
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
        return f"[FAIL] {filename}: {str(e)[:80]}"


def main():
    if not os.path.exists(DIRECT_LINKS_FILE):
        print(f"[!] {DIRECT_LINKS_FILE} not found. Run debug.py first.")
        sys.exit(1)
    
    with open(DIRECT_LINKS_FILE, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    if not urls:
        print("[!] No direct links found.")
        sys.exit(1)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"[*] Downloading {len(urls)} files to {OUTPUT_DIR}")
    print(f"[*] {MAX_WORKERS} parallel downloads")
    print(f"[*] Started at: {time.strftime('%H:%M:%S')}")
    print()
    
    start = time.time()
    completed = 0
    failed = 0
    skipped = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_file, url, OUTPUT_DIR): url for url in urls}
        
        for future in as_completed(futures):
            result = future.result()
            completed += 1
            
            if result.startswith("[OK]"):
                pass
            elif result.startswith("[SKIP]"):
                skipped += 1
            elif result.startswith("[FAIL]"):
                failed += 1
            
            print(f"[{completed}/{len(urls)}] {result}")
    
    elapsed = time.time() - start
    print(f"\n{'='*50}")
    print(f"[*] Done in {elapsed/60:.1f} minutes")
    print(f"    Success: {completed - failed - skipped}")
    print(f"    Skipped: {skipped}")
    print(f"    Failed:  {failed}")
    print(f"    Output:  {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

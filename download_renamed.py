"""
Download all files from direct_links.txt to E:\f using parallel downloads.
Maps hash filenames to original names from urls.txt.
"""
import os
import sys
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, unquote
import requests

DIRECT_LINKS_FILE = "direct_links.txt"
URLS_FILE = "urls.txt"
OUTPUT_DIR = r"E:\f"
MAX_WORKERS = 8
CHUNK_SIZE = 8 * 1024 * 1024

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
}

def build_rename_map():
    """Build dict: hash_filename -> original_filename from urls.txt + direct_links.txt"""
    # Read original names
    original_names = []
    with open(URLS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if '#' in line:
                fragment = line.split('#', 1)[1]
                parts = fragment.split('--_')
                name = parts[-1] if parts else fragment
                name = name.replace('%20', ' ')
                original_names.append(name)
            else:
                original_names.append(None)
    
    # Read direct links and extract hash names
    hash_names = []
    with open(DIRECT_LINKS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            hash_name = os.path.basename(line.split('?')[0])
            hash_names.append(hash_name)
    
    # Build map
    rename_map = {}
    for orig, hash_name in zip(original_names, hash_names):
        if orig and hash_name:
            rename_map[hash_name] = orig
    
    return rename_map


def build_download_list():
    """Build list of (url, output_filename) pairs"""
    rename_map = build_rename_map()
    
    result = []
    with open(DIRECT_LINKS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            url = line.strip()
            if not url:
                continue
            hash_name = os.path.basename(url.split('?')[0])
            orig_name = rename_map.get(hash_name, hash_name)
            result.append((url, orig_name))
    
    return result


def download_file(url, output_name, output_dir):
    """Download a single file"""
    filepath = os.path.join(output_dir, output_name)
    
    # Skip if already downloaded with correct size
    try:
        head = requests.head(url, headers=HEADERS, timeout=30)
        remote_size = int(head.headers.get('content-length', 0))
        if os.path.exists(filepath) and os.path.getsize(filepath) == remote_size and remote_size > 0:
            return f"[SKIP] {output_name} (zaten var)"
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
        return f"[OK] {output_name} ({size_mb:.0f} MB @ {speed:.1f} MB/s)"
    
    except Exception as e:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        return f"[FAIL] {output_name}: {str(e)[:80]}"


def main():
    if not os.path.exists(DIRECT_LINKS_FILE):
        print(f"[!] {DIRECT_LINKS_FILE} bulunamadi. Once debug.py calistir.")
        sys.exit(1)
    
    if not os.path.exists(URLS_FILE):
        print(f"[!] {URLS_FILE} bulunamadi.")
        sys.exit(1)
    
    download_list = build_download_list()
    
    if not download_list:
        print("[!] Indirilecek dosya bulunamadi.")
        sys.exit(1)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"[*] {len(download_list)} dosya indiriliyor -> {OUTPUT_DIR}")
    print(f"[*] Paralel: {MAX_WORKERS} is parcacigi")
    print(f"[*] Baslama: {time.strftime('%H:%M:%S')}")
    print()
    
    start = time.time()
    completed = 0
    failed = 0
    skipped = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_file, url, name, OUTPUT_DIR): (url, name) 
                   for url, name in download_list}
        
        for future in as_completed(futures):
            result = future.result()
            completed += 1
            
            if result.startswith("[OK]"):
                pass
            elif result.startswith("[SKIP]"):
                skipped += 1
            elif result.startswith("[FAIL]"):
                failed += 1
            
            print(f"[{completed}/{len(download_list)}] {result}")
    
    elapsed = time.time() - start
    print(f"\n{'='*50}")
    print(f"[*] Tamamlandi: {elapsed/60:.1f} dakika")
    print(f"    Basarili: {completed - failed - skipped}")
    print(f"    Atlanan:  {skipped}")
    print(f"    Hata:     {failed}")
    print(f"    Klasor:   {OUTPUT_DIR}")
    
    # Show summary
    files = sorted(os.listdir(OUTPUT_DIR))
    rar_count = sum(1 for f in files if f.endswith('.rar'))
    bin_count = sum(1 for f in files if f.endswith('.bin'))
    print(f"    .rar: {rar_count}, .bin: {bin_count}")


if __name__ == "__main__":
    main()
